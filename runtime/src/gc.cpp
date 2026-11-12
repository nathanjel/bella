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

#include <map>
#include <string_view>

namespace bella {
namespace {
struct GcState {
    bool enabled = true;
    int threshold[3] = {2000, 10, 10};
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
Ref g_isenabled(Args) { return Ref::steal(boolean(state().enabled)); }
Ref g_enable(Args) {
    state().enabled = true;
    return none_ref();
}
Ref g_disable(Args) {
    state().enabled = false;
    return none_ref();
}
Ref g_get_threshold(Args) {
    const GcState& s = state();
    Ref a = int_from_i64(s.threshold[0]), b = int_from_i64(s.threshold[1]), c = int_from_i64(s.threshold[2]);
    return tuple_new({a.get(), b.get(), c.get()});
}
Ref g_set_threshold(Args a) {
    state().threshold[c_int(a.pos(0))] = c_int(a.pos(1));
    return none_ref();
}
Ref g_get_debug(Args) { return int_from_i64(state().debug); }
Ref g_set_debug(Args a) {
    state().debug = c_int(a.pos(0));
    return none_ref();
}
using Primitive = Ref (*)(Args);
const std::map<std::string_view, Primitive>& primitives() {
    static const std::map<std::string_view, Primitive> table{
        {"garbage", g_garbage}, {"callbacks", g_callbacks}, {"isenabled", g_isenabled}, {"enable", g_enable}, {"disable", g_disable},
        {"get_threshold", g_get_threshold}, {"set_threshold", g_set_threshold}, {"get_debug", g_get_debug}, {"set_debug", g_set_debug},
    };
    return table;
}
}  // namespace

bool gc_is_enabled() { return state().enabled; }

Ref i_gc(Obj, Args a) {                          // _gc(name, ...)
    return primitives().at(as_str(a.pos(0))->text)(Args{a.data + 1, a.npos - 1, nullptr, 0});
}
}  // namespace bella
