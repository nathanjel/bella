// runtime/src/gc.cpp -- the collector's state (bella/runtime.hpp): the interpreter's GCState as Modules/gcmodule.c reads and
// sets it (Python/gc.c, _PyGC_InitState, PyGC_Enable, PyGC_Disable, PyGC_IsEnabled), under runtime/prelude/gc.py. CPython
// 3.15.2. Automatic collection on, the thresholds 2000, 10 and 10, no debugging flags, and the two lists the interpreter makes
// at start (_PyGC_Init: garbage and callbacks), which the module only adds. The cycle collector itself is step 3c's: until it
// is here, the functions that need it stop by name in the prelude, after their arguments are checked.
//
// The primitives are one function, `_gc(name, ...)`, as signals.cpp's `_signals` is; the prelude has checked the arguments in
// the C's words.
//   "garbage", "callbacks" -> the interpreter's list      "isenabled" -> bool       "enable", "disable"
//   "get_threshold" -> (t0, t1, t2)                       "set_threshold" (generation, value)
//   "get_debug" -> int                                    "set_debug" (flags)
#include "bella/runtime.hpp"

#include <chrono>
#include <map>
#include <string_view>

namespace bella {
namespace {
struct GcState {                                 // what the module keeps beside the collector's own state (object.hpp)
    int debug = 0;
    Obj garbage, callbacks;                      // each holds its count to the end (no static destructor runs after the program)
};
GcState& state() {
    static GcState s;
    return s;
}
int c_int(Obj v) {                               // the prelude gave an int in a C int's range
    std::int64_t out = 0;
    int_fits_i64(v, out);
    return static_cast<int>(out);
}
Ref g_list(Obj& slot) {
    if (slot.is_unset()) slot = list_new({}).release();
    return Ref::share(slot);
}
Ref g_garbage(Args) { return g_list(state().garbage); }
Ref g_callbacks(Args) { return g_list(state().callbacks); }
Ref g_isenabled(Args) { return Ref::steal(boolean(detail::collector().enabled)); }
Ref g_enable(Args) {
    detail::collector().enabled = true;
    return none_ref();
}
Ref g_disable(Args) {
    detail::collector().enabled = false;
    return none_ref();
}
Ref g_get_threshold(Args) {
    const auto& t = detail::collector().thresholds;
    Ref a = int_from_i64(t[0]), b = int_from_i64(t[1]), c = int_from_i64(t[2]);
    return tuple_new({a.get(), b.get(), c.get()});
}
Ref g_set_threshold(Args a) {
    detail::collector().thresholds[c_int(a.pos(0))] = c_int(a.pos(1));
    return none_ref();
}
Ref g_get_debug(Args) { return int_from_i64(state().debug); }
Ref g_set_debug(Args a) {
    state().debug = c_int(a.pos(0));
    return none_ref();
}
// invoke_gc_callback: each of gc.callbacks with the phase and the numbers, the runtime's own (D-04), held while it runs;
// what one raises is reported and the rest are called
void invoke_callbacks(const char* phase, std::int64_t collected, double duration) {
    Obj list = state().callbacks;
    if (list.is_unset() || static_cast<List*>(list.object())->items.empty()) return;
    Ref info = dict_new();
    auto put = [&](const char* k, Ref v) { dict_set(static_cast<Dict*>(info.get().object()), Obj::of(intern(k)), v.get()); };
    put("generation", int_from_i64(2));
    put("collected", int_from_i64(collected));
    put("uncollectable", int_from_i64(0));
    put("candidates", int_from_i64(static_cast<std::int64_t>(detail::collector().roots)));
    put("duration", float_ref(duration));
    Ref phase_obj = str_new(phase);
    for (std::size_t i = 0; i < static_cast<List*>(list.object())->items.size(); ++i) {
        Ref cb = Ref::share(static_cast<List*>(list.object())->items[i]);
        try {
            Ref r = invoke(cb.get(), {phase_obj.get(), info.get()});
        } catch (const PyError& e) {
            report_unraisable("Exception ignored while calling GC callback ", cb.get(), e);
        }
    }
}
}  // namespace

// gc_collect_main: none while one runs; the callbacks before and after; the debugging flags stop by name (their output is
// CPython's list of its objects)
std::int64_t run_collection() {
    if (detail::collector().collecting) return 0;
    if (state().debug != 0) throw NotImplemented("gc's debugging flags (gc.set_debug) at a collection");
    invoke_callbacks("start", 0, 0.0);
    auto began = std::chrono::steady_clock::now();
    std::int64_t n = collect_cycles();
    double took = std::chrono::duration<double>(std::chrono::steady_clock::now() - began).count();
    detail::collector().candidates_total += static_cast<std::int64_t>(detail::collector().roots);
    detail::collector().duration_total += took;
    invoke_callbacks("stop", n, took);
    return n;
}
void run_scheduled_collection() {                // _Py_RunGC at a look: the collection the buffer scheduled, if enabled
    detail::Collector& c = detail::collector();
    if (!c.scheduled) return;
    c.scheduled = false;
    if (!c.enabled) return;
    run_collection();
}
namespace {
Ref g_collect(Args) { return int_from_i64(run_collection()); }
Ref g_get_count(Args) {                          // the runtime's own counts in CPython's shape: the candidates, two noughts
    const detail::Collector& c = detail::collector();
    Ref a = int_from_i64(static_cast<std::int64_t>(c.candidates.size() - c.tombstones)), z = int_from_i64(0);
    return tuple_new({a.get(), z.get(), z.get()});
}
Ref g_get_stats(Args) {                          // each generation's counters, in CPython's shape: every collection is a full one
    const detail::Collector& c = detail::collector();
    Ref out = list_new({});
    for (int g = 0; g < 3; ++g) {
        Ref d = dict_new();
        auto put = [&](const char* k, std::int64_t v) { Ref x = int_from_i64(v); dict_set(static_cast<Dict*>(d.get().object()), Obj::of(intern(k)), x.get()); };
        put("collections", g == 2 ? c.collections : 0);
        put("collected", g == 2 ? c.collected : 0);
        put("uncollectable", 0);
        put("candidates", g == 2 ? c.candidates_total : 0);
        Ref took = float_ref(g == 2 ? c.duration_total : 0.0);
        dict_set(static_cast<Dict*>(d.get().object()), Obj::of(intern("duration")), took.get());
        list_append(out.get(), d.get());
    }
    return out;
}
Ref g_is_finalized(Args a) {                     // PyObject_GC_IsFinalized: a tracked object whose finaliser has run
    Obj v = a.pos(0);
    bool yes = v.is_object() && detail::holds_others(v.object()->kind, v.object()->flags) && (v.object()->flags & FINALIZED) != 0;
    return Ref::steal(boolean(yes));
}
using Primitive = Ref (*)(Args);
const std::map<std::string_view, Primitive>& primitives() {
    static const std::map<std::string_view, Primitive> table{
        {"garbage", g_garbage}, {"callbacks", g_callbacks}, {"isenabled", g_isenabled}, {"enable", g_enable}, {"disable", g_disable},
        {"get_threshold", g_get_threshold}, {"set_threshold", g_set_threshold}, {"get_debug", g_get_debug}, {"set_debug", g_set_debug},
        {"collect", g_collect}, {"get_count", g_get_count}, {"get_stats", g_get_stats}, {"is_finalized", g_is_finalized},
    };
    return table;
}
}  // namespace

bool gc_is_enabled() { return detail::collector().enabled; }

Ref i_gc(Obj, Args a) {                          // _gc(name, ...)
    return primitives().at(as_str(a.pos(0))->text)(Args{a.data + 1, a.npos - 1, nullptr, 0});
}
}  // namespace bella
