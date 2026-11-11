// runtime/src/call.cpp -- the call protocol and argument binding, function objects, names and
// modules, the C++ builtins, sys and its streams, the intrinsics, and the program's start and end
// (bella/runtime.hpp).
#include "bella/runtime.hpp"

#include <charconv>
#include <cmath>
#include <cstring>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <string_view>
#include <fcntl.h>
#include <unistd.h>
#include <unordered_map>
#include <cstdint>
#include <unordered_set>

namespace bella {

int& recursion_limit() {                         // D-17: sys.setrecursionlimit's; 1000 is CPython's default
    static int limit = 1000;
    return limit;
}
namespace {
int& recursion_depth() {
    static int depth = 0;
    return depth;
}

std::unordered_map<ClassObject*, NativeFn>& constructors() {
    static std::unordered_map<ClassObject*, NativeFn> table;
    return table;
}

}  // namespace

bool is_attribute_error(const PyError& e) { return isinstance(e.exc.get(), exception_class("AttributeError")); }

Ref positional_only(Args a, const char* name, std::size_t lo, std::size_t hi) {
    if (a.nkw != 0) raise_new("TypeError", std::string(name) + "() takes no keyword arguments");
    if (a.npos < lo || a.npos > hi) {
        std::string expected = lo == hi ? std::to_string(lo) : "from " + std::to_string(lo) + " to " + std::to_string(hi);
        raise_new("TypeError", std::string(name) + "() takes " + expected + " positional argument" + (hi == 1 ? "" : "s") +
                                   " but " + std::to_string(a.npos) + " were given");
    }
    return Ref{};
}

namespace {
// CPython's argument checks by calling convention; each message is CPython's for that kind.
void no_keywords(Args a, const std::string& qualname) {
    if (a.nkw != 0) raise_new("TypeError", qualname + "() takes no keyword arguments");
}
void check_positional(Args a, const std::string& name, std::size_t lo, std::size_t hi) {   // _PyArg_CheckPositional
    auto plural = [](std::size_t n) { return n == 1 ? " argument" : " arguments"; };
    if (a.npos < lo)
        raise_new("TypeError", name + " expected " + (lo == hi ? "" : "at least ") + std::to_string(lo) + plural(lo) +
                                   ", got " + std::to_string(a.npos));
    if (a.npos > hi)
        raise_new("TypeError", name + " expected " + (lo == hi ? "" : "at most ") + std::to_string(hi) + plural(hi) +
                                   ", got " + std::to_string(a.npos));
}
}  // namespace
void noargs(Args a, const std::string& qualname) {
    no_keywords(a, qualname);
    if (a.npos != 0) raise_new("TypeError", qualname + "() takes no arguments (" + std::to_string(a.npos) + " given)");
}
void onearg(Args a, const std::string& qualname) {
    no_keywords(a, qualname);
    if (a.npos != 1) raise_new("TypeError", qualname + "() takes exactly one argument (" + std::to_string(a.npos) + " given)");
}
void clinic(Args a, const std::string& name, const std::string& qualname, std::size_t lo, std::size_t hi) {
    no_keywords(a, qualname);
    check_positional(a, name, lo, hi);
}

// A special method's arguments, worded as CPython words them for the receiver's type: a slot
// wrapper ("expected 0 arguments, got 1"), or a method (METH_O, METH_NOARGS) named by its type.
void dunder_args(Obj self, Args a, const char* name, std::size_t n) {
    ClassObject* t = type_of(self);
    if (cpython_attribute_kind(t, name) == "wrapper_descriptor") {
        if (a.nkw != 0) raise_new("TypeError", std::string("wrapper ") + name + "() takes no keyword arguments");
        if (a.npos == n) return;
        if (std::string_view(name) == "__setitem__") check_positional(a, name, n, n);
        raise_new("TypeError", "expected " + std::to_string(n) + (n == 1 ? " argument" : " arguments") + ", got " +
                                   std::to_string(a.npos));
    }
    std::string qualname = t->name + "." + name;
    if (n == 0) noargs(a, qualname);
    else if (n == 1) onearg(a, qualname);
    else clinic(a, name, qualname, n, n);
}

namespace {

std::string quoted_list(const std::vector<std::string>& names) {
    std::string out;
    for (std::size_t i = 0; i < names.size(); ++i) {
        if (i > 0) out += names.size() == 2 ? " and " : (i + 1 == names.size() ? ", and " : ", ");
        out += "'" + names[i] + "'";
    }
    return out;
}
}  // namespace

// ---- calls ----
Ref invoke(Obj f, Args a) {
    if (!f.is_object()) raise_new("TypeError", "'int' object is not callable");
    Object* o = f.object();
    switch (o->kind) {
        case Kind::PyFunction: {
            auto* fn = static_cast<PyFunction*>(o);
            return fn->entry(fn, a);
        }
        case Kind::Builtin: {
            auto* b = static_cast<Builtin*>(o);
            if (b->self.is_unset() && b->binding != Binding::Function) {
                // an unbound method descriptor called directly (str.join(sep, items)): self first,
                // an instance of the method's type (review 2026-11-03, A9-2)
                if (a.npos == 0)
                {
                    if (b->owner != nullptr && (b->binding == Binding::ClassMethod || cpython_attribute_kind(b->owner, b->name) == "wrapper_descriptor"))   // wrapperdescr_call, classmethoddescr_call
                        raise_new("TypeError", "descriptor '" + b->name + "' of '" + b->owner->name + "' object needs an argument");
                    raise_new("TypeError", "unbound method " + (b->owner ? b->owner->name.substr(b->owner->name_prefix) + "." : "") + b->name + "() needs an argument");
                }
                if (b->binding == Binding::ClassMethod && b->owner != nullptr) {   // classmethoddescr_call: bound to the first argument, a type
                    check_classmethod_type(b, a.pos(0));
                    return call_builtin(b, a.pos(0), Args{a.data + 1, a.npos - 1, a.kwnames, a.nkw});
                }
                if (b->owner != nullptr && !isinstance(a.pos(0), b->owner)) {
                    if (cpython_attribute_kind(b->owner, b->name) == "wrapper_descriptor")   // wrapperdescr_call
                        raise_new("TypeError", "descriptor '" + b->name + "' requires a '" + b->owner->name + "' object but received a '" +
                                                   type_of(a.pos(0))->name + "'");
                    raise_new("TypeError", "descriptor '" + b->name + "' for '" + b->owner->name + "' objects doesn't apply to a '" +
                                               type_of(a.pos(0))->name + "' object");
                }
                return call_builtin(b, a.pos(0), Args{a.data + 1, a.npos - 1, a.kwnames, a.nkw});
            }
            return call_builtin(b, b->self, a);
        }
        case Kind::Method: {
            auto* m = static_cast<Method*>(o);
            std::vector<Obj> data;
            data.reserve(a.npos + a.nkw + 1);
            data.push_back(m->self);
            for (std::size_t i = 0; i < a.npos + a.nkw; ++i) data.push_back(a.data[i]);
            Obj func = m->func;
            incref(func);
            Ref hold = Ref::steal(func);           // the method may die while its function runs
            return invoke(func, Args{data.data(), a.npos + 1, a.kwnames, a.nkw});
        }
        case Kind::Class: {
            auto* c = static_cast<ClassObject*>(o);
            // a metaclass's own __call__ (slot_tp_call): it makes the instances
            if (ClassObject* meta = type_of(Obj::of(c)); meta->heap_type) {
                Obj call = type_lookup(meta, intern("__call__"));
                if (call != type_lookup(types().type, intern("__call__"))) {
                    Ref held = Ref::share(call);
                    Ref bound = descr_get(held.get(), Obj::of(c), Obj::of(meta));
                    return invoke(bound.get(), a);
                }
            }
            auto it = constructors().find(c);       // a C++ type's own constructor
            if (it != constructors().end()) return it->second(Obj::of(c), a);
            return type_call(c, a);
        }
        case Kind::Function: {
            if (a.nkw != 0) throw NotImplemented("keywords to a native test function");
            std::vector<Obj> data(a.data, a.data + a.npos);
            return Ref::steal(static_cast<Function*>(o)->fn(data));
        }
        default:
            break;
    }
    // __call__ as found on the type and bound through its descriptor, never an instance attribute
    // of that name (review 2026-11-03, A9-10)
    if (Obj call = type_lookup(type_of(f), intern("__call__")); !call.is_unset()) {
        Ref hold = Ref::share(call);
        if (is_kind(call, Kind::PyFunction)) {
            std::vector<Obj> data{f};
            data.insert(data.end(), a.data, a.data + a.npos + a.nkw);
            return invoke(call, Args{data.data(), a.npos + 1, a.kwnames, a.nkw});
        }
        Ref bound = descr_get(call, f, Obj::of(type_of(f)));
        return invoke(bound.get(), a);
    }
    raise_new("TypeError", "'" + type_of(f)->name + "' object is not callable");
}

Ref invoke(Obj f, std::initializer_list<Obj> pos) { return invoke(f, Args{pos.begin(), pos.size(), nullptr, 0}); }

Ref invoke_kw(Obj f, std::initializer_list<Obj> pos, std::initializer_list<const Str*> names,
              std::initializer_list<Obj> values) {
    std::vector<Obj> data(pos);
    data.insert(data.end(), values.begin(), values.end());
    std::vector<const Str*> kw(names);
    return invoke(f, Args{data.data(), pos.size(), kw.data(), kw.size()});
}

Ref call_ex(Obj f, Obj args, Obj kwargs) {
    std::vector<Obj> data;
    if (is_kind(args, Kind::Tuple)) data = static_cast<Tuple*>(args.object())->items;
    else throw NotImplemented("CALL_FUNCTION_EX with positional arguments that are not a tuple");
    std::vector<const Str*> names;
    if (!kwargs.is_unset()) {
        if (!is_kind(kwargs, Kind::Dict)) throw NotImplemented("CALL_FUNCTION_EX with keywords that are not a dict");
        for (auto& e : static_cast<Dict*>(kwargs.object())->entries) {
            if (e.key.is_unset()) continue;
            const Str* k = as_str(e.key);
            if (k == nullptr) raise_new("TypeError", "keywords must be strings");
            if (!is_exact_str(e.key)) throw NotImplemented("a subclass of str as a keyword's name (CPython has it; the runtime does not yet)");
            names.push_back(k);
            data.push_back(e.value);
        }
    }
    std::size_t npos = data.size() - names.size();
    return invoke(f, Args{data.data(), npos, names.data(), names.size()});
}

// The protocol object.hpp calls through (descriptors, __getattr__, finalisers): a new reference.
namespace {
Obj hook_call(Obj fn, std::span<const Obj> args) { return invoke(fn, Args{args.data(), args.size(), nullptr, 0}).release(); }
const bool call_hook_installed = (call_hook() = hook_call, true);
}  // namespace

// ---- functions and argument binding (CPython's initialize_locals) ----
Ref make_function(const Code& code, Ref (*entry)(PyFunction*, Args), Module* m, Obj defaults, Obj kwdefaults,
                  std::initializer_list<Obj> closure, Obj annotate) {
    auto* f = new PyFunction(&code, entry, m);
    Ref r = own(f);
    if (!defaults.is_unset()) f->defaults = Ref::share(defaults);
    if (!kwdefaults.is_unset()) f->kwdefaults = Ref::share(kwdefaults);
    for (Obj c : closure) f->closure.push_back(Ref::share(c));
    if (!annotate.is_unset()) f->annotate = Ref::share(annotate);
    f->name = str_new(code.name);
    f->qualname = str_new(code.qualname);
    f->doc = code.doc != nullptr ? str_new(code.doc) : none_ref();     // A9-23
    return r;
}

void bind(PyFunction* fn, Args args, std::initializer_list<Ref*> params) {
    const Code& c = *fn->code;
    std::vector<Ref*> slot(params);
    auto n = static_cast<std::size_t>(c.argcount);
    auto nkwonly = static_cast<std::size_t>(c.kwonlyargcount);
    std::string who = std::string(c.qualname) + "()";
    std::size_t varargs_slot = n + nkwonly;
    std::size_t varkw_slot = varargs_slot + (c.varargs ? 1 : 0);
    Dict* kwdict = nullptr;
    if (c.varkw) {
        *slot[varkw_slot] = dict_new();
        kwdict = static_cast<Dict*>(slot[varkw_slot]->get().object());
    }
    std::size_t take = std::min(args.npos, n);
    for (std::size_t i = 0; i < take; ++i) *slot[i] = Ref::share(args.pos(i));
    if (c.varargs) {
        std::vector<Obj> extra;
        for (std::size_t i = take; i < args.npos; ++i) {
            incref(args.pos(i));
            extra.push_back(args.pos(i));
        }
        *slot[varargs_slot] = tuple_steal(std::move(extra));
    }
    std::vector<std::string> posonly_as_kw;
    for (std::size_t k = 0; k < args.nkw; ++k) {
        const Str* name = args.kwnames[k];
        Obj value = args.kw(k);
        std::size_t found = SIZE_MAX;
        for (std::size_t j = 0; j < n + nkwonly; ++j)
            if (name->text == c.varnames[j]) { found = j; break; }
        if (found != SIZE_MAX && found < static_cast<std::size_t>(c.posonlyargcount)) {
            if (kwdict == nullptr) { posonly_as_kw.push_back(name->text); continue; }
            found = SIZE_MAX;
        }
        if (found == SIZE_MAX) {
            if (kwdict == nullptr) {             // ceval's kw_fail: _Py_CalculateSuggestions over the keyword-capable parameters
                std::vector<std::string> possible(c.varnames.begin() + c.posonlyargcount, c.varnames.begin() + static_cast<std::ptrdiff_t>(n + nkwonly));
                std::string suggestion = keyword_suggestion(name->text, possible);
                raise_new("TypeError", who + " got an unexpected keyword argument '" + name->text + "'" +
                                           (suggestion.empty() ? "" : ". Did you mean '" + suggestion + "'?"));
            }
            dict_set(kwdict, Obj::of(name), value);
            continue;
        }
        if (!slot[found]->get().is_unset())
            raise_new("TypeError", who + " got multiple values for argument '" + name->text + "'");
        *slot[found] = Ref::share(value);
    }
    if (!posonly_as_kw.empty()) {
        std::string list;
        for (std::size_t i = 0; i < posonly_as_kw.size(); ++i) list += (i ? ", '" : "'") + posonly_as_kw[i] + "'";
        raise_new("TypeError", who + " got some positional-only arguments passed as keyword arguments: " + list);
    }
    // initialize_locals: the keywords' errors come before too many positional arguments (RL-303)
    if (!c.varargs && args.npos > n) {
        std::size_t ndefaults = fn->defaults.get().is_unset() ? 0 : static_cast<Tuple*>(fn->defaults.get().object())->items.size();
        std::size_t given_kwonly = 0;
        for (std::size_t k = 0; k < args.nkw; ++k)
            for (std::size_t j = n; j < n + nkwonly; ++j)
                if (args.kwnames[k]->text == c.varnames[j]) ++given_kwonly;
        // too_many_positional's atleast: co_argcount - defcount, which is negative when __defaults__ was given more than there are parameters
        std::string takes = ndefaults ? "from " + std::to_string(static_cast<std::int64_t>(n) - static_cast<std::int64_t>(ndefaults)) + " to " + std::to_string(n) : std::to_string(n);
        std::string plural = (ndefaults == 0 && n == 1) ? "" : "s";
        std::string kwpart = given_kwonly ? " positional argument" + std::string(args.npos == 1 ? "" : "s") + " (and " +
                                                std::to_string(given_kwonly) + " keyword-only argument" +
                                                (given_kwonly == 1 ? "" : "s") + ")"
                                          : "";
        // too_many_positional: the keyword-only clause, then was or were (A10-13)
        raise_new("TypeError", who + " takes " + takes + " positional argument" + plural + " but " +
                                   std::to_string(args.npos) + kwpart + (args.npos == 1 && !given_kwonly ? " was" : " were") +
                                   " given");
    }
    // defaults for the positional parameters not given
    std::size_t ndefaults = 0;
    std::vector<Obj>* defaults = nullptr;
    if (!fn->defaults.get().is_unset()) {
        defaults = &static_cast<Tuple*>(fn->defaults.get().object())->items;
        ndefaults = defaults->size();
    }
    std::vector<std::string> missing;
    // initialize_locals' m = co_argcount - defcount, signed: defaults line up with the last parameters, and those past the first are never reached
    const std::int64_t first_default = static_cast<std::int64_t>(n) - static_cast<std::int64_t>(ndefaults);
    for (std::size_t i = args.npos; i < n; ++i) {
        if (!slot[i]->get().is_unset()) continue;
        if (static_cast<std::int64_t>(i) >= first_default) *slot[i] = Ref::share((*defaults)[static_cast<std::size_t>(static_cast<std::int64_t>(i) - first_default)]);
        else missing.push_back(c.varnames[i]);
    }
    if (!missing.empty())
        raise_new("TypeError", who + " missing " + std::to_string(missing.size()) + " required positional argument" +
                                   (missing.size() == 1 ? "" : "s") + ": " + quoted_list(missing));
    for (std::size_t j = n; j < n + nkwonly; ++j) {
        if (!slot[j]->get().is_unset()) continue;
        Obj d = fn->kwdefaults.get().is_unset() ? Obj{} : dict_get(static_cast<Dict*>(fn->kwdefaults.get().object()),
                                                                   Obj::of(intern(c.varnames[j])));
        if (!d.is_unset()) *slot[j] = Ref::share(d);
        else missing.push_back(c.varnames[j]);
    }
    if (!missing.empty())
        raise_new("TypeError", who + " missing " + std::to_string(missing.size()) + " required keyword-only argument" +
                                   (missing.size() == 1 ? "" : "s") + ": " + quoted_list(missing));
}

// ---- names ----
Ref load_fast(const Ref& slot, const char* name) {
    if (slot.get().is_unset())
        raise_new("UnboundLocalError", std::string("cannot access local variable '") + name +
                                           "' where it is not associated with a value");
    return Ref::share(slot.get());
}
Ref load_deref(const Ref& cell, const char* name, bool free) {
    Obj v = static_cast<Cell*>(cell.get().object())->value;
    if (v.is_unset()) {
        if (free) {                              // format_exc_check_arg: a NameError carries the name
            Ref msg = str_new(std::string("cannot access free variable '") + name +
                              "' where it is not associated with a value in enclosing scope");
            Ref exc = invoke(Obj::of(exception_class("NameError")), {msg.get()});
            set_exception_field(exc.get(), "name", Obj::of(intern(name)));
            raise(exc.get());
        }
        raise_new("UnboundLocalError", std::string("cannot access local variable '") + name +
                                           "' where it is not associated with a value");
    }
    return Ref::share(v);
}
void store_deref(const Ref& cell, Ref value) {
    auto* c = static_cast<Cell*>(cell.get().object());
    Obj old = std::exchange(c->value, value.release());
    decref(old);
}
void delete_deref(const Ref& cell, const char* name) {
    auto* c = static_cast<Cell*>(cell.get().object());
    if (c->value.is_unset())
        raise_new("UnboundLocalError", std::string("cannot access local variable '") + name +
                                           "' where it is not associated with a value");
    decref(std::exchange(c->value, Obj{}));
}
void delete_fast(Ref& slot, const char* name) {
    if (slot.get().is_unset())
        raise_new("UnboundLocalError", std::string("cannot access local variable '") + name +
                                           "' where it is not associated with a value");
    slot = Ref{};
}

namespace {
[[noreturn]] void raise_name_error(const Str* name) {      // NameError.name is the missing name
    Ref msg = str_new("name '" + name->text + "' is not defined");
    Ref exc = invoke(Obj::of(exception_class("NameError")), {msg.get()});
    set_exception_field(exc.get(), "name", Obj::of(name));
    raise(exc.get());
}
}  // namespace

// A lazy import found by a load is resolved, and the namespace it was found in gets the result
// (_PyEval_LoadGlobalStackRef, _PyEval_LoadName)
Ref load_global(Module* m, const Str* name) {
    Dict* ns = m->dict;
    Obj v = dict_get(ns, Obj::of(name));
    if (v.is_unset()) {
        ns = m->builtins != nullptr ? m->builtins : builtins_module()->dict;
        v = dict_get(ns, Obj::of(name));
    }
    if (v.is_unset()) {
        if (m->builtins == nullptr) refuse_absent_global(name);
        raise_name_error(name);
    }
    if (is_kind(v, Kind::LazyImport)) return lazy_reify(v, name, Obj::of(ns));
    return Ref::share(v);
}
Ref load_name(Obj ns, Module* m, const Str* name) {
    Ref v = mapping_get(ns, Obj::of(name));      // a class namespace may be any mapping (__prepare__)
    if (!v.get().is_unset()) return is_kind(v.get(), Kind::LazyImport) ? lazy_reify(v.get(), name, ns) : v;
    return load_global(m, name);
}
void store_name(Obj ns, const Str* name, Ref value) { mapping_set(ns, Obj::of(name), value.get()); }
void store_global(Module* m, const Str* name, Ref value) { dict_set(m->dict, Obj::of(name), value.get()); }
void delete_name(Obj ns, const Str* name) {
    if (is_exact_dict(ns)) {                         // DELETE_NAME: an exact dict's, else __delitem__
        if (!dict_del(static_cast<Dict*>(ns.object()), Obj::of(name)))
            raise_new("NameError", "name '" + name->text + "' is not defined");
        return;
    }
    try {
        delitem(ns, Obj::of(name));
    } catch (const PyError& e) {
        if (!isinstance(e.exc.get(), exception_class("KeyError"))) throw;
        raise_new("NameError", "name '" + name->text + "' is not defined");
    }
}
void delete_global(Module* m, const Str* name) {
    if (!dict_del(m->dict, Obj::of(name))) raise_new("NameError", "name '" + name->text + "' is not defined");
}

// ---- sys.stdout and sys.stderr: UTF-8 text streams over file descriptors 1 and 2 ----
namespace {
struct Stream {
    int fd;
    std::string buffer;
    bool line_buffered;
    void write(std::string_view s) {
        buffer.append(s);
        if (buffer.size() > (1u << 16) || (line_buffered && s.find('\n') != std::string_view::npos)) flush();
    }
    void flush() {
        std::size_t done = 0;
        while (done < buffer.size()) {
            ssize_t n = ::write(fd, buffer.data() + done, buffer.size() - done);
            if (n <= 0) break;
            done += static_cast<std::size_t>(n);
        }
        buffer.clear();
    }
};
Stream& out_stream() {
    static Stream s{1, {}, isatty(1) != 0};
    return s;
}
Stream& err_stream() {
    static Stream s{2, {}, true};
    return s;
}
}  // namespace

// ---- sys.stdout and sys.stderr as the program has them: what CPython's reports and flushes go through ----
namespace {
Obj std_stream(const char* name) {               // Unset when sys has no such name
    Module* sys = native_module_named("sys");
    if (sys == nullptr) return Obj{};
    return dict_get(sys->dict, Obj::of(intern(name)));
}
}  // namespace
void write_stderr(const std::string& text) {
    Obj f = std_stream("stderr");
    if (f.is_unset()) { err_stream().write(text); return; }   // "lost sys.stderr": the C stream has it
    if (f == None()) return;
    try {
        Ref s = str_new(text);
        Ref w = getattr(f, intern("write"));
        invoke(w.get(), {s.get()});
    } catch (const PyError&) {
    }
}
bool flush_std_stream(const char* name, bool report) {   // a closed file is left alone, as file_is_closed says
    Obj f = std_stream(name);
    if (f.is_unset() || f == None()) return true;
    try {
        bool closed = false;
        try {                                    // file_is_closed: no `closed`, or one that cannot be tested, means open (A13 #2)
            Ref c = getattr(f, intern("closed"));
            closed = truth(c.get());
        } catch (const PyError&) {
        }
        if (closed) return true;
        Ref fl = getattr(f, intern("flush"));
        invoke(fl.get(), {});
        return true;
    } catch (const PyError& e) {
        if (report) report_unraisable(std::string("Exception ignored while flushing sys.") + name, e);
        return false;
    }
}
// pythonrun.c's flush_io, once the main module has run (before an uncaught exception's report, RL-227): sys.stderr, then sys.stdout,
// each flushed whatever its `closed` says, a failure cleared; Py_FinalizeEx's flush_std_files follows, so a replacement stream's flush
// runs twice as CPython runs it (A13 #2)
void flush_io() {
    for (const char* name : {"stderr", "stdout"}) {
        Obj f = std_stream(name);
        if (f.is_unset() || f == None()) continue;
        try {
            Ref fl = getattr(f, intern("flush"));
            invoke(fl.get(), {});
        } catch (const PyError&) {
        }
    }
}
namespace {
struct ErrSink {                                 // the report's writer: sys.stderr
    void write(std::string_view s) { write_stderr(std::string(s)); }
    void flush() { flush_std_stream("stderr"); }
};
}  // namespace
namespace {

// ---- the C++ builtins ----
bool overrides_builtin_len(Obj v) { return is_subclass_instance(v) && overrides_builtin(v, "__len__"); }
Ref b_len(Obj, Args a) {
    onearg(a, "len");
    Obj v = a.pos(0);
    if (const Str* s = as_str(v); s != nullptr && !overrides_builtin_len(v)) return Ref::steal(Obj::small(static_cast<std::int64_t>(s->length)));
    if (is_kind(v, Kind::Tuple) && !overrides_builtin_len(v)) return Ref::steal(Obj::small(static_cast<std::int64_t>(static_cast<Tuple*>(v.object())->items.size())));
    if (is_kind(v, Kind::List) && !overrides_builtin_len(v)) return Ref::steal(Obj::small(static_cast<std::int64_t>(static_cast<List*>(v.object())->items.size())));
    if (is_kind(v, Kind::Dict) && !overrides_builtin_len(v))
        return Ref::steal(Obj::small(static_cast<std::int64_t>(static_cast<Dict*>(v.object())->used)));
    if (is_kind(v, Kind::DictView))
        return Ref::steal(Obj::small(static_cast<std::int64_t>(static_cast<Dict*>(static_cast<DictView*>(v.object())->dict.object())->used)));
    if (is_kind(v, Kind::Range)) {
        std::int64_t n;
        Ref length = range_length_big(v);
        if (!int_fits_i64(length.get(), n)) raise_new("OverflowError", "Python int too large to convert to C ssize_t");
        return length;
    }
    if (is_bytes_like(v)) return Ref::steal(Obj::small(static_cast<std::int64_t>(bytes_data(v).size())));
    bool has = false;
    Ref r = call_special(v, "__len__", {}, &has);
    if (has) return int_from_i64(length_value(r.get()));     // as truth takes it (A9-14)
    raise_new("TypeError", "object of type '" + type_of(v)->name + "' has no len()");
}
Ref b_repr(Obj, Args a) {
    onearg(a, "repr");
    return repr_of(a.pos(0));
}
Ref b_format(Obj, Args a) {
    clinic(a, "format", "format", 1, 2);
    Obj spec = a.npos > 1 ? a.pos(1) : Obj{};
    const Str* s = spec.is_unset() ? intern("") : as_str(spec);
    if (s == nullptr) raise_new("TypeError", "format() argument 2 must be str, not " + (spec == None() ? std::string("None") : type_of(spec)->name));
    return object_format(a.pos(0), s);
}
Ref b_ascii(Obj, Args a) {
    onearg(a, "ascii");
    return ascii_of(a.pos(0));
}
// isinstance and issubclass (Objects/abstract.c): an exact type first, type's own check for a
// class whose metaclass is type, a tuple's items in turn, else the metaclass's __instancecheck__
// or __subclasscheck__, called bound to the class
bool object_recursive_isinstance(Obj inst, Obj cls) {
    if (is_kind(cls, Kind::Class) && Obj::of(type_of(inst)) == cls) return true;
    if (is_kind(cls, Kind::Class) && type_of(cls) == types().type) return real_isinstance(inst, cls);
    if (is_union(cls)) {                         // its args, as a tuple
        Ref args = getattr(cls, intern("__args__"));
        return object_recursive_isinstance(inst, args.get());
    }
    if (is_kind(cls, Kind::Tuple)) {
        for (Obj item : static_cast<Tuple*>(cls.object())->items)
            if (object_recursive_isinstance(inst, item)) return true;
        return false;
    }
    if (Obj checker = type_lookup(type_of(cls), intern("__instancecheck__")); !checker.is_unset()) {
        Ref c = Ref::share(checker);
        Ref bound = descr_get(c.get(), cls, Obj::of(type_of(cls)));
        Ref r = invoke(bound.get(), {inst});
        return truth(r.get());
    }
    return real_isinstance(inst, cls);
}
}  // namespace
bool instance_of(Obj inst, Obj cls) { return object_recursive_isinstance(inst, cls); }
bool object_issubclass(Obj derived, Obj cls) {
    if (is_kind(cls, Kind::Class) && type_of(cls) == types().type) return derived == cls || real_issubclass(derived, cls);
    if (is_union(cls)) {                         // its args, as a tuple
        Ref args = getattr(cls, intern("__args__"));
        return object_issubclass(derived, args.get());
    }
    if (is_kind(cls, Kind::Tuple)) {
        for (Obj item : static_cast<Tuple*>(cls.object())->items)
            if (object_issubclass(derived, item)) return true;
        return false;
    }
    if (Obj checker = type_lookup(type_of(cls), intern("__subclasscheck__")); !checker.is_unset()) {
        Ref c = Ref::share(checker);
        Ref bound = descr_get(c.get(), cls, Obj::of(type_of(cls)));
        Ref r = invoke(bound.get(), {derived});
        return truth(r.get());
    }
    return real_issubclass(derived, cls);
}
namespace {
// check_class: an object with a tuple __bases__ is a class to these checks (the abstract
// protocol, which the runtime does not have yet); anything else is not
void check_class(Obj v, const char* message) {
    Ref bases;
    try {
        bases = getattr(v, intern("__bases__"));
    } catch (const PyError& e) {
        if (!is_attribute_error(e)) throw;
    }
    if (!is_kind(bases.get(), Kind::Tuple)) raise_new("TypeError", message);
    throw NotImplemented("isinstance and issubclass with an object that is not a class but has __bases__");
}
}  // namespace

// _PyObject_RealIsInstance (object_isinstance): the type's MRO, or a proxy's __class__
bool real_isinstance(Obj inst, Obj cls) {
    if (!is_kind(cls, Kind::Class)) check_class(cls, "isinstance() arg 2 must be a type, a tuple of types, or a union");
    auto* c = static_cast<ClassObject*>(cls.object());
    if (isinstance(inst, c)) return true;
    Ref icls;
    try {
        icls = getattr(inst, intern("__class__"));
    } catch (const PyError& e) {
        if (!is_attribute_error(e)) throw;
    }
    return is_kind(icls.get(), Kind::Class) && icls.get() != Obj::of(type_of(inst)) &&
           is_subclass(static_cast<ClassObject*>(icls.get().object()), c);
}
// recursive_issubclass: two classes by their MROs; anything else must be a class first
bool real_issubclass(Obj derived, Obj cls) {
    if (is_kind(cls, Kind::Class) && is_kind(derived, Kind::Class))
        return is_subclass(static_cast<ClassObject*>(derived.object()), static_cast<ClassObject*>(cls.object()));
    if (!is_kind(derived, Kind::Class)) check_class(derived, "issubclass() arg 1 must be a class");
    check_class(cls, "issubclass() arg 2 must be a class, a tuple of classes, or a union");
    return false;
}

namespace {
Ref b_isinstance(Obj, Args a) {
    clinic(a, "isinstance", "isinstance", 2, 2);
    return Ref::steal(boolean(object_recursive_isinstance(a.pos(0), a.pos(1))));
}
Ref attr_name(Obj v) {
    const Str* s = as_str(v);
    if (s == nullptr) raise_new("TypeError", "attribute name must be string, not '" + type_of(v)->name + "'");
    if (!is_exact_str(v) && (type_lookup(type_of(v), intern("__hash__")) != type_lookup(types().str, intern("__hash__")) ||
                             type_lookup(type_of(v), intern("__eq__")) != type_lookup(types().str, intern("__eq__"))))
        throw NotImplemented("an attribute name of a subclass of str with a __hash__ or __eq__ of its own (CPython has it; the runtime does not yet)");
    return Ref::share(Obj::of(intern(s->text)));
}
Ref b_getattr(Obj, Args a) {
    if (a.nkw != 0) raise_new("TypeError", "getattr() takes no keyword arguments");
    if (a.npos < 2 || a.npos > 3) raise_new("TypeError", "getattr expected 2 or 3 arguments, got " + std::to_string(a.npos));
    Ref n = attr_name(a.pos(1));
    if (a.npos == 2) return getattr(a.pos(0), static_cast<const Str*>(n.get().object()));
    Ref v = optional_getattr(a.pos(0), static_cast<const Str*>(n.get().object()));
    return v.get().is_unset() ? Ref::share(a.pos(2)) : v;
}
Ref b_hasattr(Obj, Args a) {
    clinic(a, "hasattr", "hasattr", 2, 2);
    Ref n = attr_name(a.pos(1));
    Ref v = optional_getattr(a.pos(0), static_cast<const Str*>(n.get().object()));
    return Ref::steal(boolean(!v.get().is_unset()));
}
Ref b_setattr(Obj, Args a) {
    clinic(a, "setattr", "setattr", 3, 3);
    Ref n = attr_name(a.pos(1));
    if (as_str(a.pos(1)) != nullptr && !is_exact_str(a.pos(1)))   // CPython's dict keeps the object as its key
        throw NotImplemented("storing an attribute by a name of a subclass of str (CPython has it; the runtime does not yet)");
    setattr(a.pos(0), static_cast<const Str*>(n.get().object()), a.pos(2));
    return none_ref();
}
Ref b_delattr(Obj, Args a) {
    clinic(a, "delattr", "delattr", 2, 2);
    Ref n = attr_name(a.pos(1));
    delattr(a.pos(0), static_cast<const Str*>(n.get().object()));
    return none_ref();
}
Ref b_issubclass(Obj, Args a) {
    clinic(a, "issubclass", "issubclass", 2, 2);
    return Ref::steal(boolean(object_issubclass(a.pos(0), a.pos(1))));
}
Ref b_id(Obj, Args a) {
    onearg(a, "id");
    Obj v = a.pos(0);
    return Ref::steal(Obj::small(static_cast<std::int64_t>(v.is_small() ? (static_cast<std::uint64_t>(v.small_value()) << 1) | 1
                                                                        : reinterpret_cast<std::uintptr_t>(v.object()) >> 1)));
}
Ref b_globals(Obj, Args a) {                     // globals(): the calling frame's module's namespace
    noargs(a, "globals");                        // METH_NOARGS
    detail::FrameRecord* f = detail::current_frame();
    if (f == nullptr) throw NotImplemented("globals() outside any frame");
    return Ref::share(Obj::of(f->module->dict));
}
Ref b_vars(Obj, Args a) {
    clinic(a, "vars", "vars", 0, 1);
    if (a.npos == 0) throw NotImplemented("vars() without an argument (the calling frame's locals)");
    try {
        return getattr(a.pos(0), intern("__dict__"));
    } catch (const PyError& e) {
        if (!is_attribute_error(e)) throw;
        raise_new("TypeError", "vars() argument must have __dict__ attribute");
    }
}

// list, dict and tuple methods the prelude and programs call
List* list_self(Obj self) { return static_cast<List*>(self.object()); }
Ref list_append_m(Obj self, Args a) { onearg(a, "list.append"); list_append(self, a.pos(0)); return none_ref(); }
Ref list_extend_m(Obj self, Args a) { onearg(a, "list.extend"); list_extend(self, a.pos(0)); return none_ref(); }
Ref list_pop_m(Obj self, Args a) {
    clinic(a, "pop", "list.pop", 0, 1);
    auto& items = list_self(self)->items;
    std::int64_t i = a.npos ? ssize_arg(a.pos(0)) : -1;          // the argument converted first (A9-11, G9 2.10)
    if (items.empty()) raise_new("IndexError", "pop from empty list");
    if (i < 0) i += static_cast<std::int64_t>(items.size());
    if (i < 0 || i >= static_cast<std::int64_t>(items.size())) raise_new("IndexError", "pop index out of range");
    Obj v = items[static_cast<std::size_t>(i)];
    items.erase(items.begin() + i);
    return Ref::steal(v);
}
Ref list_clear_m(Obj self, Args a) {
    noargs(a, "list.clear");
    std::vector<Obj> old = std::move(list_self(self)->items);   // list_clear: emptied first, then released
    list_self(self)->items.clear();
    for (auto it = old.rbegin(); it != old.rend(); ++it) decref(*it);
    return none_ref();
}
// list___init__: keywords refused when the type's __new__ is list's own (a subclass with a __new__ of its own may take
// them, and they are then ignored), at most one argument; the list emptied, then extended by it
Ref list_init_m(Obj self, Args a) {
    if (a.nkw != 0 && type_lookup(type_of(self), intern("__new__")) == type_lookup(types().list, intern("__new__")))
        raise_new("TypeError", "list() takes no keyword arguments");
    if (a.npos > 1) raise_new("TypeError", "list expected at most 1 argument, got " + std::to_string(a.npos));
    std::vector<Obj> old = std::move(list_self(self)->items);   // list_clear: emptied first, then released
    list_self(self)->items.clear();
    for (auto it = old.rbegin(); it != old.rend(); ++it) decref(*it);
    if (a.npos == 1) list_extend(self, a.pos(0));
    return none_ref();
}
Ref list_insert_m(Obj self, Args a) {
    clinic(a, "insert", "list.insert", 2, 2);
    auto& items = list_self(self)->items;
    std::int64_t i = ssize_arg(a.pos(0));
    std::int64_t n = static_cast<std::int64_t>(items.size());
    if (i < 0) i = std::max<std::int64_t>(0, i + n);
    if (i > n) i = n;
    incref(a.pos(1));
    items.insert(items.begin() + i, a.pos(1));
    return none_ref();
}
std::int64_t list_find(Obj self, Obj v) {
    auto& items = list_self(self)->items;
    for (std::size_t i = 0; i < items.size(); ++i) {
        Obj x = items[i];
        if (x == v) return static_cast<std::int64_t>(i);
        Ref hold = Ref::share(x);
        if (truth(compare(CmpOp::Eq, x, v).get())) return static_cast<std::int64_t>(i);
    }
    return -1;
}
Ref list_index_m(Obj self, Args a) {              // list_index_impl: start and stop as slice indices
    clinic(a, "index", "list.index", 1, 3);
    auto& items = list_self(self)->items;
    auto bound = [&](std::size_t k, std::int64_t dflt) {
        if (a.npos <= k) return dflt;
        Obj v = a.pos(k);
        if (!is_int(v) && (!is_kind(v, Kind::Instance) || type_lookup(type_of(v), intern("__index__")).is_unset()))
            raise_new("TypeError", "slice indices must be integers or have an __index__ method");
        std::int64_t x = clipped_index(v);
        auto n = static_cast<std::int64_t>(items.size());
        if (x < 0) x = std::max<std::int64_t>(x + n, 0);
        return x;
    };
    std::int64_t start = bound(1, 0), stop = bound(2, static_cast<std::int64_t>(items.size()));
    for (std::int64_t i = start; i < stop && i < static_cast<std::int64_t>(items.size()); ++i) {
        Ref v = Ref::share(items[static_cast<std::size_t>(i)]);
        if (v.get() == a.pos(0) || truth(compare(CmpOp::Eq, v.get(), a.pos(0)).get())) return Ref::steal(Obj::small(i));
    }
    raise_new("ValueError", "list.index(x): x not in list");
}
// list_remove_impl: each item held while it is compared, against the list as it is then; the
// match deletes the slice [i, i+1) of the list as it is after the comparison, which __eq__ may
// have shortened (list_ass_slice clamps it; G9 2.1)
Ref list_remove_m(Obj self, Args a) {
    onearg(a, "list.remove");
    auto& items = list_self(self)->items;
    for (std::size_t i = 0; i < items.size(); ++i) {
        Ref item = Ref::share(items[i]);
        bool eq = item.get() == a.pos(0) || truth(compare(CmpOp::Eq, item.get(), a.pos(0)).get());
        item = Ref{};
        if (eq) {
            if (i < items.size()) {
                Obj old = items[i];
                items.erase(items.begin() + static_cast<std::ptrdiff_t>(i));
                decref(old);
            }
            return none_ref();
        }
    }
    raise_new("ValueError", "list.remove(x): x not in list");
}
Ref list_count_m(Obj self, Args a) {             // list_count_impl: the live list, each item held (G9 2.3)
    onearg(a, "list.count");
    auto& items = list_self(self)->items;
    std::int64_t n = 0;
    for (std::size_t i = 0; i < items.size(); ++i) {
        Ref item = Ref::share(items[i]);
        if (item.get() == a.pos(0) || truth(compare(CmpOp::Eq, item.get(), a.pos(0)).get())) ++n;
    }
    return Ref::steal(Obj::small(n));
}
Ref tuple_index_m(Obj self, Args a) {             // tuple_index_impl: start and stop as slice indices
    clinic(a, "index", "tuple.index", 1, 3);
    const auto& items = static_cast<Tuple*>(self.object())->items;
    auto n = static_cast<std::int64_t>(items.size());
    auto bound = [&](std::size_t k, std::int64_t dflt) {
        if (a.npos <= k) return dflt;
        Obj v = a.pos(k);
        if (!is_int(v) && type_lookup(type_of(v), intern("__index__")).is_unset())
            raise_new("TypeError", "slice indices must be integers or have an __index__ method");
        return clipped_index(v);
    };
    std::int64_t start = bound(1, 0), stop = bound(2, n);
    if (start < 0) start = std::max<std::int64_t>(start + n, 0);
    if (stop < 0) stop += n;
    else if (stop > n) stop = n;
    for (std::int64_t i = start; i < stop; ++i) {
        Obj v = items[static_cast<std::size_t>(i)];
        if (v == a.pos(0) || truth(compare(CmpOp::Eq, v, a.pos(0)).get())) return Ref::steal(Obj::small(i));
    }
    raise_new("ValueError", "tuple.index(x): x not in tuple");
}
Ref tuple_getnewargs_m(Obj self, Args a) {        // tuple___getnewargs___impl: the items as a tuple, an exact one itself
    noargs(a, "tuple.__getnewargs__");
    Ref whole = is_exact_tuple(self) ? Ref::share(self) : tuple_copy(static_cast<Tuple*>(self.object())->items);
    return tuple_new({whole.get()});
}
Ref tuple_count_m(Obj self, Args a) {             // tuple_count_impl
    onearg(a, "tuple.count");
    std::int64_t n = 0;
    for (Obj v : static_cast<Tuple*>(self.object())->items)
        if (v == a.pos(0) || truth(compare(CmpOp::Eq, v, a.pos(0)).get())) ++n;
    return Ref::steal(Obj::small(n));
}
Ref list_reverse_m(Obj self, Args a) {
    noargs(a, "list.reverse");
    std::reverse(list_self(self)->items.begin(), list_self(self)->items.end());
    return none_ref();
}
Ref list_copy_m(Obj self, Args a) {
    noargs(a, "list.copy");
    Ref l = list_new({});
    for (Obj x : list_self(self)->items) list_append(l.get(), x);
    return l;
}
Ref list_len_m(Obj self, Args a) { dunder_args(self, a, "__len__", 0); return Ref::steal(Obj::small(static_cast<std::int64_t>(list_self(self)->items.size()))); }
// the built-in types' own methods do the built-in's operation, never a subclass's override, which
// may call them (dict.__getitem__(self, k) inside a __getitem__)
Ref getitem_m(Obj self, Args a) {
    dunder_args(self, a, "__getitem__", 1);
    if (is_kind(self, Kind::List)) return list_subscript(self, a.pos(0));
    return is_kind(self, Kind::Dict) ? dict_subscript(self, a.pos(0)) : getitem(self, a.pos(0));
}
Ref setitem_m(Obj self, Args a) {
    dunder_args(self, a, "__setitem__", 2);
    if (is_kind(self, Kind::Dict)) dict_set(static_cast<Dict*>(self.object()), a.pos(0), a.pos(1));
    else if (is_kind(self, Kind::List)) list_ass_subscript(self, a.pos(0), a.pos(1));
    else setitem(self, a.pos(0), a.pos(1));
    return none_ref();
}
Ref dict_delitem_m(Obj self, Args a) {
    dunder_args(self, a, "__delitem__", 1);
    if (!dict_del(static_cast<Dict*>(self.object()), a.pos(0))) {
        Ref exc = invoke(Obj::of(exception_class("KeyError")), {a.pos(0)});
        raise(exc.get());
    }
    return none_ref();
}
Ref contains_m(Obj self, Args a) {
    dunder_args(self, a, "__contains__", 1);
    if (is_kind(self, Kind::Dict)) return Ref::steal(boolean(!dict_get(static_cast<Dict*>(self.object()), a.pos(0)).is_unset()));
    if (is_kind(self, Kind::List)) return Ref::steal(boolean(list_contains(self, a.pos(0))));
    return compare(CmpOp::In, a.pos(0), self);
}
Ref iter_m(Obj self, Args a) {
    dunder_args(self, a, "__iter__", 0);
    if (is_kind(self, Kind::List)) return own(new Iterator(Iterator::ListIt, self));   // list_iter: the items, whatever a subclass says
    return is_kind(self, Kind::Dict) ? dict_iter(self) : iter(self);
}
Dict* dict_self(Obj self) { return static_cast<Dict*>(self.object()); }   // the descriptor checked the receiver
Ref dict_get_m(Obj self, Args a) {
    clinic(a, "get", "dict.get", 1, 2);
    Obj v = dict_get(dict_self(self), a.pos(0));
    return !v.is_unset() ? Ref::share(v) : a.npos > 1 ? Ref::share(a.pos(1)) : none_ref();
}
Ref dict_pop_m(Obj self, Args a) {             // pop_lock_held: an empty dict hashes nothing; one lookup
    clinic(a, "pop", "dict.pop", 1, 2);
    Dict* d = dict_self(self);
    Obj v = d->used == 0 ? Obj{} : dict_pop(d, a.pos(0), dict_key_hash(a.pos(0)));
    if (v.is_unset()) {
        if (a.npos > 1) return Ref::share(a.pos(1));
        Ref exc = invoke(Obj::of(exception_class("KeyError")), {a.pos(0)});
        raise(exc.get());
    }
    return Ref::steal(v);
}
Ref dict_len_m(Obj self, Args a) { dunder_args(self, a, "__len__", 0); return Ref::steal(Obj::small(static_cast<std::int64_t>(dict_self(self)->used))); }
Ref dict_keys_m(Obj self, Args a) {
    noargs(a, "dict.keys");
    return own(new DictView(self, DictView::Keys));
}
Ref dict_items_m(Obj self, Args a) {
    noargs(a, "dict.items");
    return own(new DictView(self, DictView::Items));
}
Ref dict_values_m(Obj self, Args a) {
    noargs(a, "dict.values");
    return own(new DictView(self, DictView::Values));
}
Ref dict_reversed_m(Obj self, Args a) {
    noargs(a, "dict.__reversed__");
    return dict_reversed(self, 0);
}
Ref view_reversed_m(Obj self, Args a) {
    noargs(a, type_of(self)->name + ".__reversed__");
    auto* view = static_cast<DictView*>(self.object());
    return dict_reversed(view->dict, view->which == DictView::Keys ? 0 : view->which == DictView::Values ? 1 : 2);
}
// frozendict's own names for what it shares with dict: the receiver's check and the messages say so
Ref frozendict_get_m(Obj self, Args a) {
    clinic(a, "get", "frozendict.get", 1, 2);
    Obj v = dict_get(static_cast<Dict*>(self.object()), a.pos(0));
    return !v.is_unset() ? Ref::share(v) : a.npos > 1 ? Ref::share(a.pos(1)) : none_ref();
}
Ref frozendict_keys_m(Obj self, Args a) {
    noargs(a, "frozendict.keys");
    return own(new DictView(self, DictView::Keys));
}
Ref frozendict_items_m(Obj self, Args a) {
    noargs(a, "frozendict.items");
    return own(new DictView(self, DictView::Items));
}
Ref frozendict_values_m(Obj self, Args a) {
    noargs(a, "frozendict.values");
    return own(new DictView(self, DictView::Values));
}
Ref frozendict_reversed_m(Obj self, Args a) {
    noargs(a, "frozendict.__reversed__");
    return dict_reversed(self, 0);
}
Ref frozendict_copy_m(Obj self, Args a) {        // frozendict_copy_impl
    noargs(a, "frozendict.copy");
    return is_exact_frozendict(self) ? Ref::share(self) : frozendict_copy(self);
}
Ref frozendict_getnewargs_m(Obj self, Args a) {  // frozendict_getnewargs: (dict(self),)
    noargs(a, "frozendict.__getnewargs__");
    Ref plain = invoke(Obj::of(types().dict), {self});
    return tuple_new({plain.get()});
}
Ref c_frozendict(Obj, Args a) {                  // frozendict_vectorcall
    if (a.npos > 1) raise_new("TypeError", "frozendict expected at most 1 argument, got " + std::to_string(a.npos));
    if (a.npos == 1 && a.nkw == 0 && is_exact_frozendict(a.pos(0))) return Ref::share(a.pos(0));
    Ref self = frozendict_empty(types().frozendict);
    if (a.npos == 1) dict_update_arg(self.get(), a.pos(0));
    for (std::size_t i = 0; i < a.nkw; ++i) dict_set(static_cast<Dict*>(self.get().object()), Obj::of(a.kwnames[i]), a.kw(i));
    return self;
}
Ref view_len_m(Obj self, Args a) {
    dunder_args(self, a, "__len__", 0);
    return Ref::steal(Obj::small(static_cast<std::int64_t>(static_cast<Dict*>(static_cast<DictView*>(self.object())->dict.object())->used)));
}
Ref view_iter_m(Obj self, Args a) {
    dunder_args(self, a, "__iter__", 0);
    return iter(self);
}
Ref view_contains_m(Obj self, Args a) {
    dunder_args(self, a, "__contains__", 1);
    return compare(CmpOp::In, a.pos(0), self);
}
Ref view_mapping(Obj self) {                     // dictview_mapping: a mappingproxy over the dict (3.10)
    return own(new Proxy(static_cast<DictView*>(self.object())->dict));
}

Ref dict_clear_m(Obj self, Args a) {
    noargs(a, "dict.clear");
    dict_clear(dict_self(self));
    return none_ref();
}
Ref dict_copy_m(Obj self, Args a) {
    noargs(a, "dict.copy");
    return dict_copy(dict_self(self));
}
Ref dict_popitem_m(Obj self, Args a) {          // the last entry; a split dict becomes ordinary first
    noargs(a, "dict.popitem");
    Dict* d = dict_self(self);
    if (d->used == 0) {
        Ref msg = str_new("popitem(): dictionary is empty");
        Ref exc = invoke(Obj::of(exception_class("KeyError")), {msg.get()});
        raise(exc.get());
    }
    dict_unsplit(d);
    auto [key, value] = dict_take_last(d);      // by index: nothing is compared (RL-298)
    Ref k = Ref::steal(key), v = Ref::steal(value);
    return tuple_new({k.get(), v.get()});
}
Ref dict_setdefault_m(Obj self, Args a) {      // one lookup, the insert where it ended (A10-6)
    clinic(a, "setdefault", "dict.setdefault", 1, 2);
    Dict* d = dict_self(self);
    std::int64_t hash = dict_key_hash(a.pos(0));
    return Ref::share(dict_setdefault(d, a.pos(0), hash, a.npos > 1 ? a.pos(1) : None()));
}
}  // namespace

void dict_update_arg(Obj self, Obj arg) {           // a mapping (keys()), else an iterable of pairs
    Dict* d = static_cast<Dict*>(self.object());
    // dict_update_arg: PyObject_GetOptionalAttr(arg, keys): a __getattr__ is asked, and what it raises
    // that is no AttributeError goes on
    if (is_kind(arg, Kind::Dict) || !optional_getattr(arg, intern("keys")).get().is_unset()) {
        dict_update(self, arg);
        return;
    }
    Ref it = iter(arg);
    for (std::int64_t i = 0;; ++i) {
        Ref item = for_next(it.get());
        if (is_end(item)) break;
        // PySequence_Fast(item, "object is not iterable"), and the note _PyErr_FormatNote adds
        Ref pair;
        try {
            pair = iter(item.get());
        } catch (const PyError& e) {
            if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
            Ref msg = str_new("object is not iterable");
            Ref exc = invoke(Obj::of(exception_class("TypeError")), {msg.get()});
            Ref note = str_new("Cannot convert dictionary update sequence element #" + std::to_string(i) + " to a sequence");
            Ref notes = list_new({note.get()});
            setattr(exc.get(), intern("__notes__"), notes.get());
            raise(exc.get());
        }
        std::vector<Ref> kv;
        for (;;) {
            Ref x = for_next(pair.get());
            if (is_end(x)) break;
            kv.push_back(std::move(x));
        }
        if (kv.size() != 2)
            raise_new("ValueError", "dictionary update sequence element #" + std::to_string(i) + " has length " +
                                        std::to_string(kv.size()) + "; 2 is required");
        dict_set(d, kv[0].get(), kv[1].get());
    }
}

namespace {
Ref dict_update_m(Obj self, Args a) {           // dict_update_arg, then the keywords
    if (a.npos > 1) raise_new("TypeError", "update expected at most 1 argument, got " + std::to_string(a.npos));
    Dict* d = dict_self(self);
    if (a.npos == 1) dict_update_arg(self, a.pos(0));
    for (std::size_t i = 0; i < a.nkw; ++i) dict_set(d, Obj::of(a.kwnames[i]), a.kw(i));
    return none_ref();
}
// _PyDict_FromKeys, for dict and for frozendict. A class that makes a frozendict gets a copy filled
// and called with it, since what it made cannot be changed: cls(fd)
Ref fromkeys_impl(Obj cls, Args a) {
    Obj value = a.npos > 1 ? a.pos(1) : None(), src = a.pos(0);
    Ref out;
    bool need_copy = false;
    if (cls == Obj::of(types().frozendict)) {
        out = frozendict_empty(types().frozendict);
    } else {
        out = invoke(cls, {});
        if (is_frozendict(out.get())) {
            need_copy = true;
            Ref copy = frozendict_empty(types().frozendict);
            dict_update_arg(copy.get(), out.get());
            out = std::move(copy);
        }
    }
    auto done = [&]() -> Ref { return need_copy ? invoke(cls, {out.get()}) : std::move(out); };
    if (!is_exact_dict(out.get()) && !is_exact_frozendict(out.get())) {   // a subclass's: PyObject_SetItem
        Ref it = iter(src);
        for (Ref k = for_next(it.get()); !is_end(k); k = for_next(it.get())) setitem(out.get(), k.get(), value);
        return out;
    }
    auto* d = static_cast<Dict*>(out.get().object());
    // dict_dict_fromkeys and dict_set_fromkeys: an exact dict's or set's keys with their stored
    // hashes, after one resize, read from the live table; anything else is iterated and hashed
    if (is_kind(src, Kind::Dict) && !is_subclass_instance(src)) {
        auto* from = static_cast<Dict*>(src.object());
        dict_resize_estimate(d, from->used);
        for (std::size_t pos = 0; pos < from->entries.size(); ++pos) {
            if (from->entries[pos].key.is_unset()) continue;
            std::int64_t hash = from->entries[pos].hash;
            Ref k = Ref::share(from->entries[pos].key);
            dict_set_hashed(d, k.get(), hash, value);
        }
        return done();
    }
    if (is_kind(src, Kind::Set)) {
        auto* from = static_cast<SetObject*>(src.object());
        dict_resize_estimate(d, from->used);
        for (std::size_t pos = 0; pos < from->table.size(); ++pos) {
            if (from->table[pos].key.is_unset()) continue;
            std::int64_t hash = from->table[pos].hash;
            Ref k = Ref::share(from->table[pos].key);
            dict_set_hashed(d, k.get(), hash, value);
        }
        return done();
    }
    Ref it = iter(src);
    for (;;) {
        Ref k = for_next(it.get());
        if (is_end(k)) break;
        dict_set(d, k.get(), value);
    }
    return done();
}
Ref dict_fromkeys_m(Obj cls, Args a) {          // a classmethod: cls is dict or a subclass
    clinic(a, "fromkeys", "dict.fromkeys", 1, 2);
    return fromkeys_impl(cls, a);
}
Ref frozendict_fromkeys_m(Obj cls, Args a) {
    clinic(a, "fromkeys", "frozendict.fromkeys", 1, 2);
    return fromkeys_impl(cls, a);
}

Ref b_iter(Obj, Args a) {
    clinic(a, "iter", "iter", 1, 2);
    if (a.npos == 2) return invoke(builtin("_callable_iterator").get(), {a.pos(0), a.pos(1)});
    return iter(a.pos(0));
}
Ref b_next(Obj, Args a) {
    clinic(a, "next", "next", 1, 2);
    if (!is_kind(a.pos(0), Kind::Iterator)) {    // builtin_next: the __next__ the type has, even None
        if (type_lookup(type_of(a.pos(0)), intern("__next__")).is_unset())
            raise_new("TypeError", "'" + type_of(a.pos(0))->name + "' object is not an iterator");
        try {
            return call_special(a.pos(0), "__next__", {});
        } catch (const PyError& e) {
            if (a.npos < 2 || !isinstance(e.exc.get(), exception_class("StopIteration"))) throw;
            return Ref::share(a.pos(1));
        }
    }
    Ref v = for_next(a.pos(0));
    if (!is_end(v)) return v;
    if (a.npos > 1) return Ref::share(a.pos(1));
    Ref exc = invoke(Obj::of(exception_class("StopIteration")), {});
    raise(exc.get());
}
Ref b_hash(Obj, Args a) {
    onearg(a, "hash");
    return int_from_i64(hash_of(a.pos(0)));
}
Ref b_abs(Obj, Args a) {                      // PyNumber_Absolute: the int's own, else __abs__ (A9-22)
    onearg(a, "abs");
    Obj v = a.pos(0);
    if (v.is_small()) return v.small_value() < 0 ? unary_neg(v) : Ref::share(v);
    if (is_kind(v, Kind::Bool)) return Ref::steal(Obj::small(static_cast<BoolObject*>(v.object())->value ? 1 : 0));
    if (is_kind(v, Kind::BigInt) || (is_kind(v, Kind::IntInstance) && !overrides_builtin(v, "__abs__"))) return big_absolute(v);   // an int subclass: int's abs, as an exact int
    bool has = false;
    Ref r = call_special(v, "__abs__", {}, &has);
    if (has) return r;
    raise_new("TypeError", "bad operand type for abs(): '" + type_of(v)->name + "'");
}
Ref sys_exception(Obj, Args a) {                  // sys_exception_impl: what is being handled, innermost first
    noargs(a, "sys.exception");
    const auto& stack = handled_exceptions();
    return stack.empty() ? none_ref() : Ref::share(stack.back());
}
Ref sys_exc_info(Obj, Args a) {                   // sys_exc_info_impl: (type, value, traceback)
    noargs(a, "sys.exc_info");
    const auto& stack = handled_exceptions();
    if (stack.empty()) return tuple_new({None(), None(), None()});
    Obj exc = stack.back();
    Ref tb = getattr(exc, intern("__traceback__"));
    return tuple_new({Obj::of(type_of(exc)), exc, tb.get()});
}
void print_traceback(Obj exc);
// Python/errors.c's UnraisableHookArgs, the structseq sys.unraisablehook is called with: made by the prelude at start-up
// (bootstrap.py's _bella_sys_surface), kept here since no module holds it
Ref& unraisable_args_type() {
    static Ref type;
    return type;
}
void write_unraisable(Obj type, Obj value, Obj tb, Obj message, Obj object);
Ref sys_unraisablehook(Obj, Args a) {             // sys_unraisablehook: the default hook, which takes that type alone (METH_O)
    onearg(a, "sys.unraisablehook");
    Obj given = a.pos(0);
    Obj wanted = unraisable_args_type().get();
    if (wanted.is_unset() || !given.is_object() || Obj::of(type_of(given)) != wanted)
        raise_new("TypeError", "sys.unraisablehook argument type must be UnraisableHookArgs");
    auto& items = static_cast<Tuple*>(given.object())->items;
    write_unraisable(items[0], items[1], items[2], items[3], items[4]);
    return none_ref();
}
Ref sys_excepthook(Obj, Args a) {                 // sys_excepthook_impl: PyErr_Display on stderr, for an exception with its traceback
    clinic(a, "excepthook", "sys.excepthook", 3, 3);
    Obj value = a.pos(1);
    if (!is_kind(value, Kind::Instance) || !is_subclass(type_of(value), exception_class("BaseException")))
        throw NotImplemented("sys.excepthook with a value that is no exception instance");
    Obj tb = a.pos(2);                           // _PyErr_Display: a traceback given for a value that has none becomes the value's
    if (is_kind(tb, Kind::Traceback) && traceback_of(value).is_unset()) set_exception_field(value, "__traceback__", tb);
    print_traceback(value);
    return none_ref();
}
Ref sys_getrecursionlimit(Obj, Args a) {
    noargs(a, "sys.getrecursionlimit");
    return int_from_i64(recursion_limit());
}
Ref sys_setrecursionlimit(Obj, Args a) {          // sys_setrecursionlimit_impl
    onearg(a, "sys.setrecursionlimit");
    Ref index = int_index_of(a.pos(0));
    std::int64_t limit = 0;
    if (!int_fits_i64(index.get(), limit) || limit > INT32_MAX || limit < INT32_MIN) raise_new("OverflowError", "Python int too large to convert to C int");
    if (limit < 1) raise_new("ValueError", "recursion limit must be greater or equal than 1");
    if (recursion_depth() >= limit)
        raise_new("RecursionError", "cannot set the recursion limit to " + std::to_string(limit) + " at the recursion depth " + std::to_string(recursion_depth()) + ": the limit is too low");
    recursion_limit() = static_cast<int>(limit);
    return none_ref();
}
double& switch_interval() {
    static double value = 0.005;
    return value;
}
Ref sys_getswitchinterval(Obj, Args a) {
    noargs(a, "sys.getswitchinterval");
    return float_ref(switch_interval());
}
Ref sys_setswitchinterval(Obj, Args a) {          // sys_setswitchinterval_impl: nothing switches yet, and the value is kept
    onearg(a, "sys.setswitchinterval");
    double interval = float_as_double(a.pos(0));
    if (interval <= 0.0) raise_new("ValueError", "switch interval must be strictly positive");
    switch_interval() = interval;
    return none_ref();
}
Ref sys_is_finalizing(Obj, Args a) {
    noargs(a, "sys.is_finalizing");
    return Ref::steal(boolean(shutting_down()));
}
Ref sys_getdefaultencoding(Obj, Args a) {
    noargs(a, "sys.getdefaultencoding");
    return Ref::share(Obj::of(intern("utf-8")));
}
Ref sys_getsizeof(Obj, Args a) {                  // sys_getsizeof, _PySys_GetSizeOf: the value is the runtime's own (the specification's "unobservable value")
    if (a.npos + a.nkw == 0) raise_new("TypeError", "getsizeof() missing required argument 'object' (pos 1)");
    if (a.npos + a.nkw > 2) raise_new("TypeError", "getsizeof() takes at most 2 arguments (" + std::to_string(a.npos + a.nkw) + " given)");
    Obj object = a.npos > 0 ? a.pos(0) : Obj{}, fallback = a.npos > 1 ? a.pos(1) : Obj{};
    for (std::size_t k = 0; k < a.nkw; ++k) {
        const std::string& name = a.kwnames[k]->text;
        if (name == "object") object = a.kw(k);
        else if (name == "default") fallback = a.kw(k);
    }
    if (object.is_unset()) raise_new("TypeError", "getsizeof() missing required argument 'object' (pos 1)");
    for (std::size_t k = 0; k < a.nkw; ++k)
        if (a.kwnames[k]->text != "object" && a.kwnames[k]->text != "default") unexpected_keyword("getsizeof()", a.kwnames[k], {"object", "default"});
    Obj method = object.is_object() ? type_lookup(type_of(object), intern("__sizeof__")) : Obj{};
    if (method.is_unset()) return int_from_i64(64);
    try {
        bool has = false;
        Ref size = call_special(object, "__sizeof__", {}, &has);
        if (!is_int(size.get())) raise_new("TypeError", "an integer is required");   // PyLong_AsSsize_t
        std::int64_t fits = 0;
        if (!int_fits_i64(size.get(), fits)) raise_new("OverflowError", "Python int too large to convert to C ssize_t");
        if (fits < 0) raise_new("ValueError", "__sizeof__() should return >= 0");
        return big_binary(BinOp::Add, size.get(), int_from_i64(16).get());
    } catch (const PyError& e) {                 // a TypeError, when a default was given, is the default
        if (fallback.is_unset() || !isinstance(e.exc.get(), exception_class("TypeError"))) throw;
    }
    return Ref::share(fallback);
}
Ref sys_audit(Obj, Args a) {                      // sys_audit: no hook can be added yet (sys.addaudithook stops by name), so no event is looked at
    if (a.nkw != 0) raise_new("TypeError", "sys.audit() takes no keyword arguments");
    if (a.npos == 0) raise_new("TypeError", "audit expected at least 1 argument, got 0");
    const Str* event = as_str(a.pos(0));
    if (event == nullptr) raise_new("TypeError", "audit() argument 1 must be str, not " + type_of(a.pos(0))->name);
    Ref encode = getattr(a.pos(0), intern("encode"));    // the argument's conversion: a surrogate fails it
    invoke(encode.get(), {});
    if (event->text.find('\0') != std::string::npos) raise_new("ValueError", "embedded null character");
    return none_ref();
}
Ref sys_get_cpu_count_config(Obj, Args a) {       // -X cpu_count and PYTHON_CPU_COUNT are an interpreter's; a compiled program has no such option
    noargs(a, "sys._get_cpu_count_config");
    return int_from_i64(-1);
}
Ref sys_getfilesystemencoding(Obj, Args a) {      // UTF-8 mode, as PEP 686 has it for the pin: no locale changes it here
    noargs(a, "sys.getfilesystemencoding");
    return Ref::share(Obj::of(intern("utf-8")));
}
Ref sys_getfilesystemencodeerrors(Obj, Args a) {
    noargs(a, "sys.getfilesystemencodeerrors");
    return Ref::share(Obj::of(intern("surrogateescape")));
}
Ref sys_intern(Obj, Args a) {                     // sys_intern_impl: the str every equal one gives; a str subclass's cannot be
    onearg(a, "sys.intern");
    const Str* s = as_str(a.pos(0));
    if (s == nullptr) raise_new("TypeError", "intern() argument must be str, not " + fully_qualified_name(type_of(a.pos(0))));
    if (!is_exact_str(a.pos(0))) raise_new("TypeError", "can't intern " + type_of(a.pos(0))->name);
    return Ref::share(Obj::of(intern(std::string_view(s->text))));
}
}  // namespace
// the module of the function that called: sentinelobject.c's caller(); the prelude has no frames of CPython's
Ref i_bella_caller_module(Obj, Args) {
    detail::FrameRecord* f = detail::current_frame();
    while (f != nullptr && !f->code->shown) f = f->caller;
    if (f == nullptr) return none_ref();
    if (f->code->module_rebound) throw NotImplemented("sentinel() in a function whose __module__ was rebound");
    Obj name = dict_get(f->module->dict, Obj::of(intern("__name__")));
    return name.is_unset() ? none_ref() : Ref::share(name);
}
namespace {
Ref sys_getframemodulename(Obj, Args a) {         // sys__getframemodulename_impl: the function's __module__ at that depth
    std::vector<Obj> given;
    if (a.npos > 1 || a.npos + a.nkw > 1) raise_new("TypeError", "_getframemodulename() takes at most 1 argument (" + std::to_string(a.npos + a.nkw) + " given)");
    Obj depth_arg = a.npos == 1 ? a.pos(0) : a.nkw == 1 ? a.kw(0) : Obj::small(0);
    if (a.nkw == 1 && a.kwnames[0]->text != "depth") throw NotImplemented("_getframemodulename() with an unexpected keyword argument (the suggestion in its message)");
    std::int64_t depth = clipped_index(depth_arg);
    detail::FrameRecord* f = detail::current_frame();
    while (f != nullptr && !f->code->shown) f = f->caller;
    while (f != nullptr && depth-- > 0) {
        f = f->caller;
        while (f != nullptr && !f->code->shown) f = f->caller;
    }
    if (f == nullptr) return none_ref();
    if (f->code->module_rebound) throw NotImplemented("sys._getframemodulename of a frame whose function's __module__ was rebound");
    Obj name = dict_get(f->module->dict, Obj::of(intern("__name__")));
    return name.is_unset() ? none_ref() : Ref::share(name);
}
bool is_callable(Obj v) {                        // PyCallable_Check: tp_call, which slot_tp_call fills for a class that defines __call__
    Kind k = v.is_object() ? v.object()->kind : Kind::Bool;
    bool yes = k == Kind::PyFunction || k == Kind::Builtin || k == Kind::Method || k == Kind::Class || k == Kind::Function;
    if (k == Kind::Instance || (!yes && is_subclass_instance(v))) yes = v.object()->cls->has("__call__");   // a built-in's subclass too
    return yes;
}
Ref b_callable(Obj, Args a) {
    onearg(a, "callable");
    return Ref::steal(boolean(is_callable(a.pos(0))));
}
Ref b_ord(Obj, Args a) {
    onearg(a, "ord");
    if (is_bytes_like(a.pos(0))) {
        const std::string& b = bytes_data(a.pos(0));
        if (b.size() != 1) raise_new("TypeError", "ord() expected a character, but string of length " + std::to_string(b.size()) + " found");
        return Ref::steal(Obj::small(static_cast<unsigned char>(b[0])));
    }
    const Str* s = as_str(a.pos(0));
    if (s == nullptr) raise_new("TypeError", "ord() expected string of length 1, but " + type_of(a.pos(0))->name + " found");
    if (s->length != 1)
        raise_new("TypeError", "ord() expected a character, but string of length " + std::to_string(s->length) + " found");
    return Ref::steal(Obj::small(static_cast<std::int64_t>(s->at(0))));
}
Ref b_chr(Obj, Args a) {
    onearg(a, "chr");
    Ref value = int_index_of(a.pos(0));          // PyLong_AsLongAndOverflow: an int, a bool, or __index__
    std::int64_t c;
    if (!int_fits_i64(value.get(), c) || c < 0 || c > 0x10FFFF) raise_new("ValueError", "chr() arg not in range(0x110000)");
    return str_from_codepoints(std::u32string(1, static_cast<char32_t>(c)));
}

// constructors of the C++ types
Ref c_str(Obj, Args a) {                         // unicode_new_impl
    if (a.nkw == 0 && a.npos > 3) raise_new("TypeError", "str expected at most 3 arguments, got " + std::to_string(a.npos));   // unicode_vectorcall
    if (a.npos + a.nkw > 3) raise_new("TypeError", std::string("str() takes at most 3 ") + (a.npos == 0 ? "keyword " : "") + "arguments (" + std::to_string(a.npos + a.nkw) + " given)");   // unicode_new, past it
    Obj x = a.npos > 0 ? a.pos(0) : Obj{}, encoding = a.npos > 1 ? a.pos(1) : Obj{}, errors = a.npos > 2 ? a.pos(2) : Obj{};
    for (std::size_t k = 0; k < a.nkw; ++k) {
        const Str* name = a.kwnames[k];
        Obj* slot = name == intern("object") ? &x : name == intern("encoding") ? &encoding : name == intern("errors") ? &errors : nullptr;
        if (slot == nullptr) unexpected_keyword("str()", name, {"object", "encoding", "errors"});
        if (!slot->is_unset())
            raise_new("TypeError", "argument for str() given by name ('" + name->text + "') and position (" +
                                       std::to_string(name == intern("object") ? 1 : name == intern("encoding") ? 2 : 3) + ")");
        *slot = a.kw(k);
    }
    if (!encoding.is_unset() && as_str(encoding) == nullptr)
        raise_new("TypeError", "str() argument 'encoding' must be str, not " + type_of(encoding)->name);
    if (!errors.is_unset() && as_str(errors) == nullptr)
        raise_new("TypeError", "str() argument 'errors' must be str, not " + type_of(errors)->name);
    if (x.is_unset()) return str_new("");
    if (encoding.is_unset() && errors.is_unset()) return str_of(x);
    if (as_str(x) != nullptr) raise_new("TypeError", "decoding str is not supported");
    return str_from_bytes(x, encoding, errors);
}
Ref c_memoryview(Obj, Args) { throw NotImplemented("[P2+] memoryview and the buffer protocol (spec section 3)"); }
Ref c_bool(Obj, Args a) {
    clinic(a, "bool", "bool", 0, 1);
    return Ref::steal(boolean(a.npos == 1 && truth(a.pos(0))));
}
Ref c_range(Obj, Args a) {
    clinic(a, "range", "range", 1, 3);
    // range_from_array: PyNumber_Index on start, stop, step in that order
    Ref start = a.npos == 1 ? Ref::steal(Obj::small(0)) : int_index_of(a.pos(0));
    Ref stop = int_index_of(a.pos(a.npos == 1 ? 0 : 1));
    Ref step = a.npos == 3 ? int_index_of(a.pos(2)) : Ref::steal(Obj::small(1));
    return range_from_ints(start.get(), stop.get(), step.get());
}
Ref c_tuple(Obj, Args a) {
    clinic(a, "tuple", "tuple", 0, 1);
    if (a.npos == 0) return tuple_new({});
    if (is_exact_tuple(a.pos(0))) return Ref::share(a.pos(0));
    // PySequence_Tuple: the iterator's items, with no length hint (3.15)
    std::vector<Obj> items;
    Ref it = iter(a.pos(0));
    try {
        for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get())) items.push_back(v.release());
    } catch (...) {
        for (Obj v : items) decref(v);
        throw;
    }
    return tuple_steal(std::move(items));
}
Ref c_list(Obj, Args a) {
    clinic(a, "list", "list", 0, 1);
    Ref l = list_new({});
    if (a.npos == 1) list_extend(l.get(), a.pos(0));
    return l;
}

Ref str_join(Obj self, Args a) {
    onearg(a, "str.join");
    const Str* sep = as_str(self);
    std::string out;
    Ref it;
    try {                                       // PySequence_Fast(seq, "can only join an iterable")
        it = iter(a.pos(0));
    } catch (const PyError& e) {
        if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
        raise_new("TypeError", "can only join an iterable");
    }
    std::size_t i = 0;
    Ref first;
    for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get()), ++i) {
        const Str* s = as_str(v.get());
        if (s == nullptr)
            raise_new("TypeError", "sequence item " + std::to_string(i) + ": expected str instance, " +
                                       type_of(v.get())->name + " found");
        if (i > 0) out += sep->text;
        else first = Ref::share(v.get());
        out += s->text;
    }
    if (i == 1 && is_exact_str(first.get())) return first;   // /* Fast path: only one item */
    return str_new(out);
}

void put(Dict* d, const char* name, Obj v) { dict_set(d, Obj::of(intern(name)), v); }
void put_builtin(Dict* d, const char* name, NativeFn fn) {
    Ref b = own(new Builtin(name, fn));
    put(d, name, b.get());
}
void method(ClassObject* c, const char* name, NativeFn fn) {
    auto* b = new Builtin(name, fn, Obj{}, Binding::Method);
    b->owner = c;
    b->flags |= IMMORTAL;
    c->attrs.set(intern(name), Obj::of(b));
}

Module* make_builtins() {
    auto* m = new Module("builtins");
    Dict* d = m->dict;
    put(d, "__name__", m->name.get());           // PyModule_New's names, as for sys
    put(d, "__doc__", cpython_doc("builtins"));
    for (const char* n : {"__package__", "__loader__", "__spec__"}) put(d, n, None());
    Types& t = types();
    for (auto [name, cls, ctor] : std::initializer_list<std::tuple<const char*, ClassObject*, NativeFn>>{
             {"str", t.str, c_str}, {"type", t.type, nullptr}, {"bool", t.bool_, c_bool}, {"range", t.range, c_range},
             {"tuple", t.tuple, c_tuple}, {"list", t.list, c_list}, {"int", t.int_, nullptr},
             {"object", t.object, nullptr}, {"dict", t.dict, nullptr}, {"frozendict", t.frozendict, c_frozendict}, {"float", t.float_, nullptr}, {"complex", t.complex_, nullptr},
             {"bytes", t.bytes, nullptr}, {"bytearray", t.bytearray, nullptr}, {"memoryview", t.memoryview, c_memoryview}}) {
        put(d, name, Obj::of(cls));
        if (ctor != nullptr) constructors()[cls] = ctor;
    }
    for (const char* n : {"BaseException", "Exception", "SystemExit", "KeyboardInterrupt", "GeneratorExit",
                          "ArithmeticError", "ZeroDivisionError", "OverflowError", "AssertionError", "AttributeError",
                          "LookupError", "IndexError", "KeyError", "NameError", "UnboundLocalError", "RuntimeError",
                          "NotImplementedError", "RecursionError", "MemoryError", "ReferenceError", "StopIteration", "TypeError", "ValueError",
                          "ImportError", "ModuleNotFoundError", "ImportCycleError", "UnicodeError", "UnicodeEncodeError",
                          "UnicodeDecodeError", "UnicodeTranslateError", "OSError", "BlockingIOError", "ConnectionError", "ChildProcessError",
                          "BrokenPipeError", "ConnectionAbortedError", "ConnectionRefusedError", "ConnectionResetError", "FileExistsError", "FileNotFoundError",
                          "IsADirectoryError", "NotADirectoryError", "InterruptedError", "PermissionError", "ProcessLookupError", "TimeoutError", "SyntaxError",
                          "IndentationError", "TabError", "_IncompleteInputError", "StopAsyncIteration", "EOFError", "PythonFinalizationError", "FloatingPointError",
                          "SystemError", "BufferError", "Warning", "UserWarning", "DeprecationWarning", "PendingDeprecationWarning", "SyntaxWarning", "RuntimeWarning",
                          "FutureWarning", "ImportWarning", "UnicodeWarning", "BytesWarning", "EncodingWarning", "ResourceWarning"})
        put(d, n, Obj::of(exception_class(n)));
    put(d, "EnvironmentError", Obj::of(exception_class("OSError")));
    put(d, "IOError", Obj::of(exception_class("OSError")));
    put(d, "None", None());
    put(d, "True", boolean(true));
    put(d, "False", boolean(false));
    put(d, "NotImplemented", Obj::of(NOTIMPLEMENTED));
    put(d, "Ellipsis", Obj::of(ELLIPSIS));
    put_builtin(d, "len", b_len);
    put_builtin(d, "eval", b_eval);
    put_builtin(d, "exec", b_exec);
    put_builtin(d, "compile", b_compile);
    put_builtin(d, "sorted", b_sorted);
    fill_int_builtins(d);
    put_builtin(d, "repr", b_repr);
    put_builtin(d, "format", b_format);
    put_builtin(d, "ascii", b_ascii);
    put_builtin(d, "isinstance", b_isinstance);
    put_builtin(d, "iter", b_iter);
    put_builtin(d, "next", b_next);
    put_builtin(d, "hash", b_hash);
    put_builtin(d, "abs", b_abs);
    put_builtin(d, "callable", b_callable);
    put_builtin(d, "ord", b_ord);
    put_builtin(d, "chr", b_chr);
    put_builtin(d, "getattr", b_getattr);
    put_builtin(d, "hasattr", b_hasattr);
    put_builtin(d, "setattr", b_setattr);
    put_builtin(d, "delattr", b_delattr);
    put_builtin(d, "issubclass", b_issubclass);
    put_builtin(d, "id", b_id);
    put_builtin(d, "vars", b_vars);
    put_builtin(d, "__import__", b_import);
    put_builtin(d, "__lazy_import__", b_lazy_import);
    put_builtin(d, "dir", b_dir);
    put_builtin(d, "globals", b_globals);
    put(d, "slice", Obj::of(t.slice));
    put(d, "super", Obj::of(t.super_));
    put(d, "set", Obj::of(t.set));
    put(d, "frozenset", Obj::of(t.frozenset));
    method(t.str, "join", str_join);
    auto* maketrans = new Builtin("maketrans", str_maketrans_m, Obj{}, Binding::Function);   // a static method
    maketrans->owner = t.str;
    maketrans->flags |= IMMORTAL;
    t.str->attrs.set(intern("maketrans"), Obj::of(maketrans));
    for (auto [n, fn] : std::initializer_list<std::pair<const char*, NativeFn>>{
             {"find", str_find_m}, {"rfind", str_rfind_m}, {"index", str_index_m}, {"rindex", str_rindex_m},
             {"count", str_count_m}, {"isascii", str_isascii_m}, {"startswith", str_startswith_m}, {"endswith", str_endswith_m},
             {"partition", str_partition_m}, {"rpartition", str_rpartition_m}, {"split", str_split_m},
             {"rsplit", str_rsplit_m}, {"strip", str_strip_m}, {"lstrip", str_lstrip_m}, {"rstrip", str_rstrip_m},
             {"replace", str_replace_m}, {"lower", str_lower_m}, {"casefold", str_casefold_m}, {"upper", str_upper_m}, {"swapcase", str_swapcase_m}, {"capitalize", str_capitalize_m}, {"title", str_title_m}, {"isalpha", str_isalpha_m}, {"isalnum", str_isalnum_m}, {"isdigit", str_isdigit_m}, {"isdecimal", str_isdecimal_m}, {"isnumeric", str_isnumeric_m}, {"isspace", str_isspace_m}, {"isprintable", str_isprintable_m}, {"isidentifier", str_isidentifier_m}, {"islower", str_islower_m}, {"isupper", str_isupper_m}, {"istitle", str_istitle_m}, {"center", str_center_m}, {"ljust", str_ljust_m}, {"rjust", str_rjust_m}, {"zfill", str_zfill_m}, {"removeprefix", str_removeprefix_m}, {"removesuffix", str_removesuffix_m}, {"splitlines", str_splitlines_m}, {"expandtabs", str_expandtabs_m}, {"translate", str_translate_m},
             {"__getnewargs__", str_getnewargs_m}, {"__str__", str_str_m}, {"format", str_format_m}, {"format_map", str_format_map_m},
             {"__format__", str_format_dunder}})
        method(t.str, n, fn);
    for (ClassObject* c : {t.list, t.dict, t.frozendict}) {      // tuple's and str's are slot wrappers (slots.cpp)
        method(c, "__getitem__", getitem_m);
        method(c, "__contains__", contains_m);
        method(c, "__iter__", iter_m);
    }
    // the mutable containers and the keys and items views are unhashable: __hash__ is None in their
    // dicts (PyObject_HashNotImplemented), so object.__hash__ is not found (found while fixing A10-7)
    for (ClassObject* c : {t.list, t.dict, t.set, t.dict_keys, t.dict_items}) {
        incref(None());
        decref(c->attrs.set(intern("__hash__"), None()));
    }
    method(t.list, "__init__", list_init_m);
    method(t.list, "append", list_append_m);
    method(t.list, "extend", list_extend_m);
    method(t.list, "pop", list_pop_m);
    method(t.list, "__len__", list_len_m);
    method(t.list, "clear", list_clear_m);
    method(t.list, "insert", list_insert_m);
    method(t.list, "index", list_index_m);
    method(t.list, "remove", list_remove_m);
    method(t.list, "count", list_count_m);
    method(t.tuple, "index", tuple_index_m);
    method(t.tuple, "count", tuple_count_m);
    method(t.tuple, "__getnewargs__", tuple_getnewargs_m);
    method(t.list, "reverse", list_reverse_m);
    method(t.list, "copy", list_copy_m);
    method(t.list, "__setitem__", setitem_m);
    method(t.dict, "__setitem__", setitem_m);
    method(t.dict, "__len__", dict_len_m);
    method(t.dict, "__delitem__", dict_delitem_m);
    method(t.dict, "get", dict_get_m);
    method(t.dict, "pop", dict_pop_m);
    method(t.dict, "keys", dict_keys_m);
    method(t.dict, "items", dict_items_m);
    method(t.dict, "values", dict_values_m);
    method(t.dict, "__reversed__", dict_reversed_m);
    method(t.frozendict, "__len__", dict_len_m);
    method(t.frozendict, "get", frozendict_get_m);
    method(t.frozendict, "keys", frozendict_keys_m);
    method(t.frozendict, "items", frozendict_items_m);
    method(t.frozendict, "values", frozendict_values_m);
    method(t.frozendict, "__reversed__", frozendict_reversed_m);
    method(t.frozendict, "copy", frozendict_copy_m);
    method(t.frozendict, "__getnewargs__", frozendict_getnewargs_m);
    for (ClassObject* v : {t.dict_keys, t.dict_values, t.dict_items}) {
        method(v, "__len__", view_len_m);
        method(v, "__iter__", view_iter_m);
        method(v, "__reversed__", view_reversed_m);
        v->attrs.set(intern("mapping"), Obj::of(new GetSet("mapping", v, view_mapping, nullptr)));
        if (v != t.dict_values) {
            method(v, "__contains__", view_contains_m);
            method(v, "isdisjoint", dictview_isdisjoint_m);
        }
    }
    method(t.dict, "clear", dict_clear_m);
    method(t.dict, "copy", dict_copy_m);
    method(t.dict, "popitem", dict_popitem_m);
    method(t.dict, "setdefault", dict_setdefault_m);
    method(t.dict, "update", dict_update_m);
    {
        auto* b = new Builtin("fromkeys", dict_fromkeys_m, Obj{}, Binding::ClassMethod);
        b->owner = t.dict;
        b->flags |= IMMORTAL;
        t.dict->attrs.set(intern("fromkeys"), Obj::of(b));
        auto* f = new Builtin("fromkeys", frozendict_fromkeys_m, Obj{}, Binding::ClassMethod);
        f->owner = t.frozendict;
        f->flags |= IMMORTAL;
        t.frozendict->attrs.set(intern("fromkeys"), Obj::of(f));
    }
    return m;
}

// sys.exit(status=None, /): PyErr_SetObject(SystemExit, status): None makes it with no argument,
// a tuple with its items, anything else with itself
Ref sys_exit(Obj, Args a) {
    clinic(a, "exit", "sys.exit", 0, 1);
    Obj status = a.npos == 1 ? a.pos(0) : None();
    Obj cls = Obj::of(exception_class("SystemExit"));
    Ref exc;
    if (status == None()) {
        exc = invoke(cls, std::initializer_list<Obj>{});
    } else if (is_kind(status, Kind::Tuple)) {
        auto& items = static_cast<Tuple*>(status.object())->items;
        exc = invoke(cls, Args{items.data(), items.size()});
        set_exception_field(exc.get(), "args", status);   // _PyErr_CreateException calls with the tuple itself: it is args, and code when it has more than one
        if (items.size() > 1) set_exception_field(exc.get(), "code", status);
    } else {
        exc = invoke(cls, {status});
    }
    raise(exc.get());
}

Module* make_sys(int argc, char** argv) {
    auto* m = new Module("sys");
    Dict* d = m->dict;
    // PyModule_New's names;
    // importlib._bootstrap._setup gives the module its spec and loader
    put(d, "__name__", m->name.get());
    put(d, "__doc__", cpython_doc("sys"));
    for (const char* n : {"__package__", "__loader__", "__spec__"}) put(d, n, None());
    // stdin, stdout and stderr come when _io has: create_stdio, at the start
    Ref args = list_new({});
    for (int i = 0; i < argc; ++i) {
        Ref s = str_new(argv[i]);
        list_append(args.get(), s.get());
    }
    put(d, "argv", args.get());
    {
        Ref original = list_new({});
        for (Obj v : static_cast<List*>(args.get().object())->items) list_append(original.get(), v);
        put(d, "orig_argv", original.get());
    }
    put_builtin(d, "exit", sys_exit);
    put_builtin(d, "intern", sys_intern);
    put_builtin(d, "exc_info", sys_exc_info);
    put_builtin(d, "exception", sys_exception);
    put_builtin(d, "excepthook", sys_excepthook);
    put(d, "__excepthook__", dict_get(d, Obj::of(intern("excepthook"))));
    put_builtin(d, "unraisablehook", sys_unraisablehook);
    put(d, "__unraisablehook__", dict_get(d, Obj::of(intern("unraisablehook"))));
    put_builtin(d, "_getframemodulename", sys_getframemodulename);
    put(d, "maxsize", int_from_i64(INT64_MAX).get());
    put_builtin(d, "getrecursionlimit", sys_getrecursionlimit);
    put_builtin(d, "setrecursionlimit", sys_setrecursionlimit);
    put_builtin(d, "getswitchinterval", sys_getswitchinterval);
    put_builtin(d, "setswitchinterval", sys_setswitchinterval);
    put_builtin(d, "is_finalizing", sys_is_finalizing);
    put_builtin(d, "getdefaultencoding", sys_getdefaultencoding);
    put_builtin(d, "getsizeof", sys_getsizeof);
    put(d, "hexversion", int_from_i64(51315440).get());
    put(d, "api_version", int_from_i64(1013).get());
    put(d, "maxunicode", int_from_i64(1114111).get());
    put(d, "byteorder", Obj::of(intern("little")));
    put(d, "float_repr_style", Obj::of(intern("short")));
    put(d, "platlibdir", Obj::of(intern("lib")));
    put(d, "abiflags", Obj::of(intern("")));
    put(d, "dont_write_bytecode", Ref::steal(boolean(false)).get());
    put(d, "pycache_prefix", None());
    if (!stdlib_dir().empty()) put(d, "_stdlib_dir", str_new(stdlib_dir()).get());   // the build's interpreter's (main_unit)
    {   // sys.path_importer_cache: the closed world's registry stands for the path finders (decision 2026-11-03), so no path entry
        // is ever looked up or cached; linecache reads it for a file it cannot find (_read_from_archive)
        Ref cache = dict_new();
        put(d, "path_importer_cache", cache.get());
    }
    put(d, "version", str_new("3.15.2 (bella) [GCC " __VERSION__ "]").get());
    put(d, "copyright", cpython_doc("sys.copyright"));
    {
        Ref empty = list_new({});
        put(d, "warnoptions", empty.get());
        Ref options = dict_new();
        put(d, "_xoptions", options.get());
        std::string executable(4096, '\0');         // D-21: there is no installation; a program is where it is
        ssize_t got = readlink("/proc/self/exe", executable.data(), executable.size());
        executable.resize(got < 0 ? 0 : static_cast<std::size_t>(got));
        std::string prefix = executable;
        for (int i = 0; i < 2; ++i) prefix = prefix.substr(0, prefix.empty() ? 0 : std::min(prefix.rfind('/'), prefix.size()));
        Ref exe = str_new(executable), root = str_new(prefix);
        put(d, "executable", exe.get());
        for (const char* n : {"prefix", "base_prefix", "exec_prefix", "base_exec_prefix"}) put(d, n, root.get());
    }
    put(d, "platform", Obj::of(intern("linux")));
    put_builtin(d, "audit", sys_audit);
    put_builtin(d, "_get_cpu_count_config", sys_get_cpu_count_config);
    {                                            // the pin's: a name here says CPython has it, and an import of one the runtime lacks stops by name
        std::vector<Obj> names;
        for (std::string_view n : cpython_names_of("builtin_module")) names.push_back(Obj::of(intern(std::string(n))));
        Ref t = tuple_steal(std::move(names));
        put(d, "builtin_module_names", t.get());
    }
    put_builtin(d, "getfilesystemencoding", sys_getfilesystemencoding);
    put_builtin(d, "getfilesystemencodeerrors", sys_getfilesystemencodeerrors);
    fill_int_sys(d);
    return m;
}

std::unordered_map<std::string, Module*>& native_modules() {
    static std::unordered_map<std::string, Module*> table;
    return table;
}

// ---- names CPython has and the runtime lacks yet ----
#include "cpython_names.inc"

// the table knows a built-in type by its tp_name, which is the runtime's name for it
std::string_view table_name(const ClassObject* c) { return c->name; }
const CPythonName* cpython_find(std::string_view scope, std::string_view name) {
    std::string key;
    key.reserve(scope.size() + 1 + name.size());
    key.append(scope).append(":").append(name);
    auto it = std::lower_bound(std::begin(CPYTHON_NAMES), std::end(CPYTHON_NAMES), std::string_view(key),
                               [](const CPythonName& e, std::string_view k) { return e.key < k; });
    return it != std::end(CPYTHON_NAMES) && it->key == key ? &*it : nullptr;
}
std::unordered_set<const ClassObject*>& prelude_classes() {     // the prelude's builtins (property, ...)
    static std::unordered_set<const ClassObject*> classes;
    return classes;
}
void refuse_in(const std::vector<ClassObject*>& mro, const Str* name) {
    for (const ClassObject* c : mro) {
        if ((!c->heap_type || prelude_classes().contains(c)) && cpython_has(table_name(c), name->text))
            throw NotImplemented(c->name + "." + name->text + " (CPython has it; the runtime does not yet)");
        if (c->heap_type)                        // a class of the import system's two modules: its own names are the table's too
            if (std::string scope = bootstrap_class_scope(c); !scope.empty() && cpython_has(scope, name->text))
                throw NotImplemented(scope + "." + name->text + " (CPython has it; the runtime does not yet)");
    }
}
}  // namespace
bool callable_object(Obj v) { return is_callable(v); }
std::string& stdlib_dir() {                      // sys._stdlib_dir: where the pin's standard library is, as the build found it
    static std::string dir;
    return dir;
}
void set_stdlib_dir(const char* dir) { stdlib_dir() = dir; }

void adopt_functions(Module* m) {
    Obj name = dict_get(m->dict, Obj::of(intern("__name__")));
    auto& entries = m->dict->entries;
    for (auto& e : entries) {
        if (e.key.is_unset() || !is_kind(e.value, Kind::Builtin)) continue;
        auto* b = static_cast<Builtin*>(e.value.object());
        if (b->owner != nullptr || !b->self.is_unset() || b->home != nullptr) continue;
        b->home = m;
        b->module_name = Ref::share(name);
    }
}
Obj cpython_doc(std::string_view name) {
    auto it = std::lower_bound(std::begin(CPYTHON_DOCS), std::end(CPYTHON_DOCS), name,
                               [](const CPythonDoc& e, std::string_view k) { return e.name < k; });
    if (it == std::end(CPYTHON_DOCS) || it->name != name) return None();
    return Obj::of(intern(it->text));
}

std::optional<std::string_view> cpython_type_text(std::string_view scope, const ClassObject* c) {
    const CPythonName* e = cpython_find(scope, table_name(c));
    if (e == nullptr) return std::nullopt;
    return e->kind;
}
std::optional<std::int64_t> cpython_type_number(std::string_view scope, const ClassObject* c) {
    const CPythonName* e = cpython_find(scope, table_name(c));
    if (e == nullptr) return std::nullopt;
    std::int64_t value = 0;
    std::from_chars(e->kind.data(), e->kind.data() + e->kind.size(), value);
    return value;
}
std::optional<std::string_view> cpython_doc_text(std::string_view name) {
    auto it = std::lower_bound(std::begin(CPYTHON_DOCS), std::end(CPYTHON_DOCS), name,
                               [](const CPythonDoc& e, std::string_view k) { return e.name < k; });
    if (it == std::end(CPYTHON_DOCS) || it->name != name) return std::nullopt;
    return it->text;
}

bool cpython_has(std::string_view scope, std::string_view name) { return cpython_find(scope, name) != nullptr; }
void note_prelude_class(const ClassObject* c) { prelude_classes().insert(c); }
std::vector<std::string_view> cpython_names_of(std::string_view scope) {   // its rows, in the table's order
    std::string prefix = std::string(scope) + ":";
    std::vector<std::string_view> out;
    auto it = std::lower_bound(std::begin(CPYTHON_NAMES), std::end(CPYTHON_NAMES), std::string_view(prefix),
                               [](const CPythonName& row, std::string_view key) { return row.key < key; });
    for (; it != std::end(CPYTHON_NAMES) && it->key.starts_with(prefix); ++it) out.push_back(it->key.substr(prefix.size()));
    return out;
}
// A name found on a later class of the MRO that an earlier built-in type has its own of in CPython:
// a base's method would be the wrong answer (`(5).__lt__` is not object's), so it is refused (RL-310).
void refuse_shadowed(const std::vector<ClassObject*>& mro, std::size_t from, const Str* name) {
    for (std::size_t i = from; i < mro.size(); ++i) {
        const ClassObject* c = mro[i];
        if (c->attrs.contains(name)) return;
        if ((!c->heap_type || prelude_classes().contains(c)) && cpython_has(table_name(c), name->text))
            throw NotImplemented(c->name + "." + name->text + " (CPython has it; the runtime does not yet)");
    }
}
void refuse_absent_attribute(Obj obj, const Str* name) {
    if (is_kind(obj, Kind::Module)) {
        auto* m = static_cast<Module*>(obj.object());
        const std::string& mod = as_str(m->name.get())->text;
        auto it = native_modules().find(mod);
        bool tabled = (it != native_modules().end() && it->second == m) || is_bootstrap_prelude(m);   // its names are the table's
        if (tabled && cpython_has(mod, name->text))
            throw NotImplemented(mod + "." + name->text + " (CPython has it; the runtime does not yet)");
    }
    if (is_kind(obj, Kind::Class)) refuse_in(static_cast<ClassObject*>(obj.object())->mro, name);
    refuse_in(type_of(obj)->mro, name);
}
void refuse_absent_data_descriptor(Obj obj, const Str* name) {
    for (const ClassObject* c : type_of(obj)->mro) {
        if (c->heap_type) continue;              // the prelude's classes keep their fields as they choose
        std::string_view kind = cpython_attribute_kind(c, name->text);
        if (kind == "member_descriptor" || kind == "getset_descriptor")
            throw NotImplemented(c->name + "." + name->text + " (CPython has it; the runtime does not yet)");
    }
}
std::string_view cpython_attribute_kind(const ClassObject* owner, std::string_view name) {
    if (!c_type(owner)) return {};               // a program's class named after a built-in is not that built-in
    const CPythonName* e = cpython_find(table_name(owner), name);
    return e != nullptr ? e->kind : std::string_view{};
}
bool presents_as_builtin(Obj f) { return is_kind(f, Kind::PyFunction) && f.object()->cls == types().builtin; }
bool c_type(const ClassObject* c) { return !c->heap_type || prelude_classes().contains(c); }
bool immutable_type(const ClassObject* c) {      // Py_TPFLAGS_IMMUTABLETYPE: every static type, and a type of CPython's whose flags say so (ast's node classes do not)
    if (!c_type(c)) return false;
    auto flags = cpython_type_number("flags", c);
    return !flags || (*flags & (1 << 8)) != 0;
}
void refuse_unimplemented_operator(const char* scope, Obj a, const std::string& sym, Obj b) {
    // an instance, or the built-in type under its class: a program's classes have no row, whatever their names
    auto name = [](Obj v) {
        if (is_kind(v, Kind::Instance)) return std::string("instance");
        for (const ClassObject* c : type_of(v)->mro)
            if (!c->heap_type) return c->name;
        return type_of(v)->name;
    };
    if (cpython_has(scope, name(a) + sym + name(b)))
        throw NotImplemented("'" + type_of(a)->name + "' " + sym + " '" + type_of(b)->name + "' (CPython has it; the runtime does not yet)");
}
void refuse_absent_global(const Str* name) {
    if (cpython_has("builtins", name->text) || cpython_has("globals", name->text))
        throw NotImplemented("the name '" + name->text + "' (CPython has it; the runtime does not yet)");
}

Module* builtins_module() {
    static Module* m = make_builtins();
    return m;
}
// PyModule_New: module_init_dict's names first, as every module's namespace starts
void note_native_module(const char* name, Module* m) { native_modules()[name] = m; }
Module* native_module_named(const std::string& name) {
    auto it = native_modules().find(name);
    return it == native_modules().end() ? nullptr : it->second;
}
std::string_view native_module_name(const Module* m) {
    for (const auto& [name, module] : native_modules())
        if (module == m) return name;
    return {};
}
Module* new_module(const char* name) {
    auto* m = new Module(name);
    put(m->dict, "__name__", m->name.get());
    for (const char* n : {"__doc__", "__package__", "__loader__", "__spec__"}) put(m->dict, n, None());
    return m;
}

namespace {
}  // namespace
Dict* intrinsics() {                           // what the prelude gives the runtime, not the program
    static Dict* d = [] {
        auto* x = new Dict;
        x->flags |= IMMORTAL;
        return x;
    }();
    return d;
}
namespace {
}  // namespace

namespace {
// the L1 intrinsics that are helpers of the runtime's own (eval2's intrinsic_value)
Ref i_special(Obj, Args a) {                    // _PyObject_LookupSpecial, as the with statement uses it
    positional_only(a, "special", 2, 2);
    Obj obj = a.pos(0);
    const Str* name = as_str(a.pos(1));
    Obj found = type_lookup(type_of(obj), intern(name->text));
    if (found.is_unset())
        raise_new("TypeError", "'" + type_of(obj)->name + "' object does not support the context manager protocol");
    Obj get = type_lookup(type_of(found), intern("__get__"));
    if (get.is_unset() && !is_kind(found, Kind::PyFunction)) return Ref::share(found);
    if (is_kind(found, Kind::PyFunction)) return own(new Method(found, obj));
    return invoke(get, {found, obj, Obj::of(type_of(obj))});
}
}  // namespace
Ref i_lookup_special(Obj, Args a) {              // _PyObject_LookupSpecial: the bound method in a tuple, or ()
    positional_only(a, "_lookup_special", 2, 2);
    const Str* name = intern(as_str(a.pos(1))->text);
    Obj found = type_lookup(type_of(a.pos(0)), name);
    if (found.is_unset()) {
        refuse_absent_attribute(a.pos(0), name);  // CPython's type has it and the runtime lacks it: never "absent"
        return tuple_new({});
    }
    Ref bound = descr_get(found, a.pos(0), Obj::of(type_of(a.pos(0))));
    return tuple_new({bound.get()});
}
// _frame(n) for the _warnings prelude (setup_context): the n-th frame above the one that called into the prelude, as
// (globals, filename, lineno), or None past the outermost; a prelude's own frames are not on the chain, as C functions' are not
Ref i_warnings_frame(Obj, Args a) {
    positional_only(a, "_frame", 1, 1);
    std::int64_t depth = index_value(a.pos(0));
    detail::FrameRecord* f = detail::current_frame();
    while (f != nullptr && !f->code->shown) f = f->caller;
    while (f != nullptr && depth-- > 0) {
        f = f->caller;
        while (f != nullptr && !f->code->shown) f = f->caller;
    }
    if (f == nullptr) return none_ref();
    Ref filename = str_new(f->code->filename);
    return tuple_new({Obj::of(f->module->dict), filename.get(), Obj::small(f->line)});
}
Ref i_number_index(Obj, Args a) {                // PyNumber_Index
    positional_only(a, "_number_index", 1, 1);
    return int_index_of(a.pos(0));
}
Ref i_dict_next(Obj, Args a) {                   // PyDict_Next: (next position, key, value) or None
    positional_only(a, "_dict_next", 2, 2);
    if (!is_kind(a.pos(0), Kind::Dict)) raise_new("TypeError", "_dict_next() needs a dict");
    auto* d = static_cast<Dict*>(a.pos(0).object());
    for (std::int64_t i = index_value(a.pos(1)); i >= 0 && static_cast<std::size_t>(i) < d->entries.size(); ++i) {
        auto& e = d->entries[static_cast<std::size_t>(i)];
        if (!e.key.is_unset()) return tuple_new({Obj::small(i + 1), e.key, e.value});
    }
    return none_ref();
}

// PyFloat_Pack2/4/8 and PyFloat_Unpack2/4/8 (Objects/floatobject.c) for a prelude: the IEEE 754 binary16, binary32 and binary64
// forms of a double, on a platform whose doubles are little-endian IEEE (x86-64, aarch64). Pack2 is the C's software path, Pack4
// its cast with the overflow test and the NaN payload fix, Pack8 a copy.
namespace {
std::uint64_t double_bits(double x) { std::uint64_t v; std::memcpy(&v, &x, 8); return v; }
double bits_double(std::uint64_t v) { double x; std::memcpy(&x, &v, 8); return x; }

std::uint16_t float_pack2(double x) {
    unsigned sign; int e; std::uint16_t bits;
    if (x == 0.0) { sign = std::copysign(1.0, x) == -1.0; e = 0; bits = 0; }
    else if (std::isinf(x)) { sign = x < 0.0; e = 0x1f; bits = 0; }
    else if (std::isnan(x)) {
        sign = std::copysign(1.0, x) == -1.0; e = 0x1f;
        std::uint64_t v = double_bits(x) & 0xffc0000000000ULL;
        bits = static_cast<std::uint16_t>(v >> 42);           // the NaN's type and payload
        if (!bits) bits |= (1 << 9);                           // a qNaN when there is no payload
    } else {
        sign = x < 0.0;
        if (sign) x = -x;
        double f = std::frexp(x, &e);
        if (f < 0.5 || f >= 1.0) raise_new("SystemError", "frexp() result out of range");
        f *= 2.0; e--;                                         // f in [1.0, 2.0)
        if (e >= 16) raise_new("OverflowError", "float too large to pack with e format");
        else if (e < -25) { f = 0.0; e = 0; }                  // |x| < 2**-25: zero
        else if (e < -14) { f = std::ldexp(f, 14 + e); e = 0; } // |x| < 2**-14: gradual underflow
        else { e += 15; f -= 1.0; }
        f *= 1024.0;
        bits = static_cast<std::uint16_t>(f);                  // truncated, then rounded to even
        if ((f - bits > 0.5) || ((f - bits == 0.5) && (bits % 2 == 1))) {
            ++bits;
            if (bits == 1024) { bits = 0; ++e; if (e == 31) raise_new("OverflowError", "float too large to pack with e format"); }
        }
    }
    return static_cast<std::uint16_t>(bits | (e << 10) | (sign << 15));
}

std::uint32_t float_pack4(double x) {
    float y = static_cast<float>(x);
    if (std::isinf(y) && !std::isinf(x)) raise_new("OverflowError", "float too large to pack with f format");
    std::uint32_t u32; std::memcpy(&u32, &y, 4);
    if (std::isnan(x)) {                                       // a sNaN's payload survives the conversion
        std::uint64_t v = double_bits(x);
        if ((v & (1ULL << 51)) == 0 && (u32 & 0x3fffff)) u32 &= ~(1u << 22);
        if (v & (1ULL << 63)) u32 |= (1u << 31);
        u32 -= (u32 & 0x3fffff);
        u32 += static_cast<std::uint32_t>((v & 0x7ffffffffffffULL) >> 29);
        if ((v & (1ULL << 51)) == 0 && (u32 & 0x3fffff)) u32 &= ~(1u << 22);
    }
    return u32;
}

double float_unpack2(std::uint16_t bits) {
    unsigned sign = (bits >> 15) & 1; int e = (bits >> 10) & 0x1f; unsigned f = bits & 0x3ff;
    if (e == 0x1f) {
        if (f == 0) return sign ? -INFINITY : INFINITY;
        std::uint64_t v = sign ? 0xfff0000000000000ULL : 0x7ff0000000000000ULL;
        return bits_double(v + (static_cast<std::uint64_t>(f) << 42));
    }
    double x = static_cast<double>(f) / 1024.0;
    if (e == 0) e = -14; else { x += 1.0; e -= 15; }
    x = std::ldexp(x, e);
    return sign ? -x : x;
}

double float_unpack4(std::uint32_t u32) {
    float x; std::memcpy(&x, &u32, 4);
    if (std::isnan(x) && (u32 & (1u << 22)) == 0) {           // a sNaN float stays a sNaN double
        double y = x;
        return bits_double(double_bits(y) & ~(1ULL << 51));
    }
    return x;
}
}  // namespace

Ref i_float_pack(Obj, Args a) {                  // (x, size, little_endian[, cast]) -> the size bytes of PyFloat_Pack{2,4,8};
    positional_only(a, "_float_pack", 3, 4);     // cast: the C's (float)x of np_float_complex, no overflow test, no NaN fix
    double x = float_as_double(a.pos(0));
    std::int64_t size = index_value(a.pos(1));
    bool le = truth(a.pos(2));
    bool cast = a.npos > 3 && truth(a.pos(3));
    std::uint64_t v; int n;
    if (size == 2) { v = float_pack2(x); n = 2; }
    else if (size == 4 && cast) { float y = static_cast<float>(x); std::uint32_t u32; std::memcpy(&u32, &y, 4); v = u32; n = 4; }
    else if (size == 4) { v = float_pack4(x); n = 4; }
    else if (size == 8) { v = double_bits(x); n = 8; }
    else raise_new("ValueError", "_float_pack() size must be 2, 4 or 8");
    std::string out(static_cast<std::size_t>(n), '\0');
    for (int i = 0; i < n; ++i) {
        unsigned char byte = static_cast<unsigned char>((v >> (8 * i)) & 0xff);
        out[static_cast<std::size_t>(le ? i : n - 1 - i)] = static_cast<char>(byte);
    }
    return bytes_new(out);
}

Ref i_float_unpack(Obj, Args a) {                // (data, little_endian[, cast]) -> the float of PyFloat_Unpack{2,4,8}, by the
    positional_only(a, "_float_unpack", 2, 3);   // data's length; cast: the C's (double)float of nu_float_complex, a sNaN quieted
    if (!is_kind(a.pos(0), Kind::Bytes)) raise_new("TypeError", "_float_unpack() needs bytes");
    const std::string& data = bytes_data(a.pos(0));
    bool le = truth(a.pos(1));
    bool cast = a.npos > 2 && truth(a.pos(2));
    int n = static_cast<int>(data.size());
    if (n != 2 && n != 4 && n != 8) raise_new("ValueError", "_float_unpack() needs 2, 4 or 8 bytes");
    std::uint64_t v = 0;
    for (int i = 0; i < n; ++i) {
        unsigned char byte = static_cast<unsigned char>(data[static_cast<std::size_t>(le ? i : n - 1 - i)]);
        v |= static_cast<std::uint64_t>(byte) << (8 * i);
    }
    if (n == 2) return float_ref(float_unpack2(static_cast<std::uint16_t>(v)));
    if (n == 4 && cast) { float y; std::uint32_t u32 = static_cast<std::uint32_t>(v); std::memcpy(&y, &u32, 4); return float_ref(static_cast<double>(y)); }
    if (n == 4) return float_ref(float_unpack4(static_cast<std::uint32_t>(v)));
    return float_ref(bits_double(v));
}
namespace {
Ref i_set_add(Obj, Args a) {
    positional_only(a, "set_add", 2, 2);
    set_add(a.pos(0), a.pos(1));
    return none_ref();
}
Ref i_map_add(Obj, Args a) {
    positional_only(a, "map_add", 3, 3);
    setitem(a.pos(0), a.pos(1), a.pos(2));
    return none_ref();
}
Ref i_unpack(Obj, Args a) {                     // unpack_iterable(value, before, after): a list
    positional_only(a, "unpack", 3, 3);
    std::int64_t before = a.pos(1).small_value(), after = a.pos(2).small_value();
    std::size_t n = static_cast<std::size_t>(before + (after >= 0 ? after + 1 : 0));
    std::vector<Ref> targets(n);
    unpack(a.pos(0), targets, after >= 0 ? static_cast<int>(before) : -1);
    Ref l = list_new({});
    for (Ref& t : targets) list_append(l.get(), t.get());
    return l;
}
Obj missing_sentinel() {
    static Obj m = own(new_instance(types().object)).release();
    return m;
}
Ref i_call_args_tuple(Obj, Args a) {             // _MAKE_CALLARGS_A_TUPLE: f(*value)
    positional_only(a, "call_args_tuple", 1, 1);
    Obj v = a.pos(0);
    if (is_exact_tuple(v)) return Ref::share(v);
    // _Py_Check_ArgsIterable: an __iter__, or a sequence's __getitem__
    if (type_lookup(type_of(v), intern("__iter__")).is_unset() && !has_sq_item(v) &&
        !is_kind(v, Kind::List) && !is_kind(v, Kind::Dict) && !is_kind(v, Kind::Set) && !is_kind(v, Kind::Range) &&
        !is_kind(v, Kind::Iterator) && !is_kind(v, Kind::DictView) && as_str(v) == nullptr)
        raise_new("TypeError", "Value after * must be an iterable, not " + type_of(v)->name);
    std::vector<Ref> items;
    Ref it = iter(v);
    for (;;) {
        Ref x = for_next(it.get());
        if (is_end(x)) break;
        items.push_back(std::move(x));
    }
    std::vector<Obj> objs;
    for (auto& r : items) objs.push_back(r.release());
    return tuple_steal(std::move(objs));
}

Ref i_super(Obj, Args a) {                       // zero-argument super() in a function
    positional_only(a, "super", 3, 3);
    return zero_argument_super(a.pos(0), a.pos(1), a.pos(2));
}

void register_intrinsics() {
    static bool done = false;
    if (done) return;
    done = true;
    for (auto [name, fn] : std::initializer_list<std::pair<const char*, NativeFn>>{
             {"special", i_special}, {"set_add", i_set_add}, {"map_add", i_map_add}, {"unpack", i_unpack},
             {"call_args_tuple", i_call_args_tuple}, {"super", i_super}}) {
        Ref b = own(new Builtin(name, fn));
        dict_set(intrinsics(), Obj::of(intern(name)), b.get());
    }
    dict_set(intrinsics(), Obj::of(intern("missing")), missing_sentinel());
}
}  // namespace

Ref builtin(const char* name) {
    register_intrinsics();
    Obj v = dict_get(intrinsics(), Obj::of(intern(name)));
    if (v.is_unset()) v = dict_get(builtins_module()->dict, Obj::of(intern(name)));
    if (v.is_unset()) {                          // PEP 695's intrinsics are _typing's (Objects/typevarobject.c), imported at first use
        for (const char* pep695 : {"type_params", "generic_class", "typealias", "set_type_params"})
            if (std::string_view(name) == pep695) {
                Ref module_name = str_new("_typing");
                import_module_level(module_name.get(), Obj{}, Obj{}, Obj{}, 0);   // its __intrinsics__ register themselves
                v = dict_get(intrinsics(), Obj::of(intern(name)));
            }
    }
    if (v.is_unset()) throw NotImplemented(std::string("the intrinsic '") + name + "'");
    return Ref::share(v);
}

// ---- the intrinsics L2 calls by name (Runtime ops) ----
Ref runtime_call(const char* intrinsic, Obj ns, Module* m, std::initializer_list<Obj> args,
                 std::initializer_list<const Str*> kwnames, std::initializer_list<Obj> kwvalues) {
    std::string_view name(intrinsic);
    std::vector<Obj> a(args);
    if (name == "import_name") return import_name(a.at(0), a.at(1), a.at(2), a.at(3), m, ns);
    if (name == "import_from") return import_from(a.at(0), intern(as_str(a.at(1))->text));
    if (name == "import_star") {
        import_star(a.at(0), ns);
        return none_ref();
    }
    if (name == "setup_annotations") {           // SETUP_ANNOTATIONS (bytecodes.c): PyMapping_GetOptionalItem on the namespace, then a
        Obj key = Obj::of(intern("__annotations__"));   // new dict stored unless one was found; an exact dict is asked without running code
        bool found;
        if (is_kind(ns, Kind::Dict)) found = !dict_get(static_cast<Dict*>(ns.object()), key).is_unset();
        else {
            try {
                getitem(ns, key);
                found = true;
            } catch (const PyError& e) {
                if (!isinstance(e.exc.get(), exception_class("KeyError"))) throw;
                found = false;
            }
        }
        if (!found) {
            Ref fresh = dict_new();
            setitem(ns, key, fresh.get());
        }
        return none_ref();
    }
    Ref f = builtin(intrinsic);
    std::size_t npos = a.size();
    a.insert(a.end(), kwvalues.begin(), kwvalues.end());
    std::vector<const Str*> names(kwnames);
    return invoke(f.get(), Args{a.data(), npos, names.data(), names.size()});
}

// ---- frames ----
void detail::enter_frame() {
    if (++recursion_depth() > recursion_limit()) {
        --recursion_depth();
        raise_new("RecursionError", "maximum recursion depth exceeded");
    }
}
void detail::leave_frame() noexcept { --recursion_depth(); }
detail::FrameRecord*& detail::current_frame() {
    static FrameRecord* f = nullptr;
    return f;
}

// ---- the program ----
namespace {
void print_traceback(Obj exc);
}  // namespace

namespace {
// write_unraisable_exc_file, the default hook's work on sys.stderr (nothing when sys has none, or None): a first line from
// the message and the object, then the report of the exception. CPython hands the value to the traceback module
// (_print_exception_bltin) and falls back on the class's name and the value's text when that fails, as it does for a value
// that is no exception; here the runtime's own report stands for the module's
void write_unraisable(Obj type, Obj value, Obj tb, Obj message, Obj object) {
    Obj file = std_stream("stderr");
    if (file.is_unset() || file == None()) return;
    bool said = !message.is_unset() && message != None();
    if (!object.is_unset() && object != None()) {
        std::string head = "Exception ignored in: ";
        if (said) {
            Ref text = str_of(message);
            head = as_str(text.get())->text + ": ";
        }
        try {
            Ref shown = repr_of(object);
            head += as_str(shown.get())->text;
        } catch (const PyError&) {
            head += "<object repr() failed>";
        }
        write_stderr(head + "\n");
    } else if (said) {
        Ref text = str_of(message);
        write_stderr(as_str(text.get())->text + ":\n");
    }
    if (is_exception_instance(value)) {
        print_traceback(value);
        return;
    }
    if (value.is_unset() || value == None()) {   // traceback.print_exception(None)
        write_stderr("NoneType: None\n");
        return;
    }
    // a value that is no exception: the traceback given, then `module.qualname: str(value)`
    if (!tb.is_unset() && tb != None()) throw NotImplemented("sys.unraisablehook's report of a traceback given beside a value that is no exception");
    if (type.is_unset() || type == None()) return;
    if (!is_kind(type, Kind::Class)) throw NotImplemented("sys.unraisablehook with an exc_type that is no class (CPython 3.15.2 crashes there)");
    Ref text = str_of(value);
    write_stderr(fully_qualified_name(static_cast<ClassObject*>(type.object())) + ": " + as_str(text.get())->text + "\n");
}
// format_unraisable_v: sys.unraisablehook(UnraisableHookArgs(class, exception, traceback, message, None)). An exception with
// no traceback gets one of the frame that is running, if any. No hook, or None for one, is the default hook; a hook that
// raises (SystemExit too) or cannot be called is reported by the default hook itself, as the object, with its own exception
void format_unraisable(const std::string* context, Obj exc) {
    Ref type = Ref::share(Obj::of(type_of(exc)));
    Ref tb = Ref::share(traceback_of(exc));
    if (!is_kind(tb.get(), Kind::Traceback)) {
        tb = none_ref();
        if (detail::FrameRecord* frame = detail::current_frame(); frame != nullptr && is_exception_instance(exc)) {
            tb = own(new Traceback(frame->code, frame->line, Ref{}));   // _PyTraceBack_FromFrame(NULL, frame), then PyException_SetTraceback
            set_exception_field(exc, "__traceback__", tb.get());
        }
    }
    Ref message = context != nullptr ? str_new(*context) : none_ref();
    auto sys = native_modules().find("sys");
    Obj hook = sys != native_modules().end() && sys->second != nullptr ? dict_get(sys->second->dict, Obj::of(intern("unraisablehook"))) : Obj{};
    if (hook.is_unset() || hook == None() || unraisable_args_type().get().is_unset()) {
        write_unraisable(type.get(), exc, tb.get(), message.get(), None());
        return;
    }
    Ref held = Ref::share(hook);                 // the hook may replace itself
    try {
        Ref fields = tuple_new({type.get(), exc, tb.get(), message.get(), None()});
        Ref args = invoke(unraisable_args_type().get(), {fields.get()});
        invoke(held.get(), {args.get()});
    } catch (const PyError& failed) {            // sys.unraisablehook failed: log its error using default hook
        Obj raised = failed.exc.get();
        Ref failure = str_new("Exception ignored in sys.unraisablehook");
        Obj its = traceback_of(raised);
        write_unraisable(Obj::of(type_of(raised)), raised, is_kind(its, Kind::Traceback) ? its : None(), failure.get(), held.get());
    }
}
}  // namespace
void report_unraisable(const std::string& context, const PyError& e) { format_unraisable(&context, e.exc.get()); }
void report_unraisable(const std::string& context, Obj exc) { format_unraisable(&context, exc); }
void report_unraisable(Obj exc) { format_unraisable(nullptr, exc); }

namespace {
// What the report reads of an exception, by attribute access as traceback.TracebackException
// does; `__notes__` may be absent (getattr(exc, '__notes__', None)).
Ref report_attr(Obj exc, const char* name) {
    try {
        return getattr(exc, intern(name));
    } catch (const PyError& e) {
        if (is_attribute_error(e) && std::string_view(name) == "__notes__") return none_ref();
        throw NotImplemented(std::string("the report of an uncaught exception whose ") + name + " raises");
    }
}

// One exception of the report: its traceback, then `Type: message`.
void print_one(ErrSink& err, Obj exc) {
    Obj tb = traceback_of(exc);
    if (is_kind(tb, Kind::Traceback)) {
        err.write("Traceback (most recent call last):\n");
        for (Obj t = tb; is_kind(t, Kind::Traceback); t = static_cast<Traceback*>(t.object())->next.get()) {
            auto* e = static_cast<Traceback*>(t.object());
            // file and line only (spec D-06: release builds carry no source text)
            err.write(std::string("  File \"") + e->code->filename + "\", line " + std::to_string(e->line) + ", in " +
                      e->code->name + "\n");
        }
    }
    // format_exception_only: the type's __qualname__, its module unless __main__ or builtins, and
    // _safe_string(exc, 'exception'): a str() that raises anything shows as <exception str() failed>
    std::string name = fully_qualified_name(type_of(exc));
    if (const Obj* mod = type_of(exc)->attrs.find(intern("__module__")); mod != nullptr && as_str(*mod) == nullptr)
        name = "<unknown>." + type_of(exc)->qualname;     // TracebackException: a __module__ that is no str
    std::string text;
    try {
        Ref str = str_of(exc);
        text = as_str(str.get())->text;
    } catch (const PyError&) {
        text = "<exception str() failed>";
    }
    err.write(text.empty() ? name + "\n" : name + ": " + text + "\n");
}

// The report CPython prints (traceback.TracebackException, compact): the chain first, oldest
// first, each link introduced by why it is there: an explicit cause, or the context unless
// suppressed; an exception already in the chain ends it (RL-226).
void print_traceback(Obj exc) {
    static const char* const CAUSE = "\nThe above exception was the direct cause of the following exception:\n\n";
    static const char* const CONTEXT = "\nDuring handling of the above exception, another exception occurred:\n\n";
    ClassObject* base = exception_class("BaseException");
    auto is_exception = [&](Obj v) { return is_kind(v, Kind::Instance) && is_subclass(type_of(v), base); };
    std::vector<std::pair<const char*, Ref>> chain;     // (why the next one is shown, the exception)
    std::unordered_set<const Object*> seen;
    for (Ref e = Ref::share(exc); !e.get().is_unset();) {
        seen.insert(e.get().object());
        if (is_exception_group(e.get()))             // TracebackException's nested format (the `+-+---- 1 ----` boxes): not written yet
            throw NotImplemented("the traceback of an uncaught exception group (its nested format)");
        if (report_attr(e.get(), "__notes__").get() != None())
            throw NotImplemented("the __notes__ of an uncaught exception (PEP 678)");
        Ref cause = report_attr(e.get(), "__cause__");
        Ref context = report_attr(e.get(), "__context__");
        Ref suppress = report_attr(e.get(), "__suppress_context__");
        const char* why = nullptr;
        Ref next;
        bool has_cause = is_exception(cause.get()) && !seen.contains(cause.get().object());
        if (has_cause) {
            why = CAUSE;
            next = std::move(cause);
        } else if (is_exception(context.get()) && !truth(suppress.get()) && !seen.contains(context.get().object())) {
            why = CONTEXT;
            next = std::move(context);
        }
        chain.emplace_back(why, std::move(e));
        e = std::move(next);
    }
    ErrSink err;
    for (auto it = chain.rbegin(); it != chain.rend(); ++it) {
        if (it->first != nullptr) err.write(it->first);
        print_one(err, it->second.get());
    }
    err.flush();
}

// a finaliser's exception is reported and dropped; the exception being propagated, if any,
// stays the one frame records attach to (A9-4)
void call_finalizer(Obj fn, Obj self) {
    Obj saved = detail::raising();
    const void* owner = detail::raising_owner();
    try {
        Ref r = invoke(fn, {self});
    } catch (const PyError& e) {
        Ref text = repr_of(fn);
        report_unraisable("Exception ignored while calling deallocator " + as_str(text.get())->text, e);
    } catch (const NotImplemented& e) {          // a refusal in a finaliser still stops the program
        out_stream().flush();
        err_stream().write(std::string("bella: not implemented: ") + e.what() + "\n");
        err_stream().flush();
        std::_Exit(70);
    }
    detail::raising() = saved;
    detail::raising_owner() = owner;
}
const bool finalizer_hook_installed = (finalizer_hook() = call_finalizer, true);
// handle_callback: what a weak reference's callback raises is reported, and goes no further
void call_weakref_callback(Obj fn, Obj holder) {
    Obj saved = detail::raising();
    const void* owner = detail::raising_owner();
    try {
        Ref r = invoke(fn, {holder});
    } catch (const PyError& e) {
        Ref text = repr_of(fn);
        report_unraisable("Exception ignored while calling weakref callback " + as_str(text.get())->text, e);
    } catch (const NotImplemented& e) {          // a refusal in a callback still stops the program
        out_stream().flush();
        err_stream().write(std::string("bella: not implemented: ") + e.what() + "\n");
        err_stream().flush();
        std::_Exit(70);
    }
    detail::raising() = saved;
    detail::raising_owner() = owner;
}
const bool weakref_hook_installed = (weakref_callback_hook() = call_weakref_callback, true);

// finalize_modules at exit. sys's special names go; sys.modules is emptied; then the collector
// (_PyGC_CollectNoFail) finds the modules' namespaces in cycles (a dict holds a function holding the
// dict) and runs every finaliser with the namespaces whole, so a __del__ reads its globals (RL-281).
// Until the cycle collector exists (step 3c) a walk from the namespaces stands for it: what it reaches
// is finalised, in the order found (D-07: unspecified), and only then are the namespaces cleared.
// Modules are immortal here (D-19), so their namespaces are cleared in place, sys.modules' first.
namespace {
template <class T>
void attribute_values(T* inst, std::vector<Obj>& todo) {
    for (Obj v : inst->fields) todo.push_back(v);
    if (inst->dict != nullptr) todo.push_back(Obj::of(inst->dict));
}
void finalizable_from(const std::vector<Module*>& roots, std::vector<Ref>& found, std::unordered_set<Object*>& seen) {
    std::vector<Obj> todo;
    for (Module* m : roots) todo.push_back(Obj::of(m->dict));
    for (std::size_t next = 0; next < todo.size(); ++next) {
        Obj v = todo[next];
        if (!v.is_object() || !seen.insert(v.object()).second) continue;
        Object* o = v.object();
        if (o->kind == Kind::Class || o->cls != nullptr) todo.push_back(Obj::of(o->cls));
        switch (o->kind) {
            case Kind::Instance:
                attribute_values(static_cast<Instance*>(o), todo);
                found.push_back(Ref::share(v));
                break;
            case Kind::IntInstance:
                attribute_values(static_cast<IntInstance*>(o), todo);
                found.push_back(Ref::share(v));
                break;
            case Kind::FloatInstance:
                attribute_values(static_cast<FloatInstance*>(o), todo);
                found.push_back(Ref::share(v));
                break;
            case Kind::ComplexInstance:
                attribute_values(static_cast<ComplexInstance*>(o), todo);
                found.push_back(Ref::share(v));
                break;
            case Kind::Dict:
                if (has_attributes(o)) {
                    attribute_values(static_cast<DictInstance*>(o), todo);
                    found.push_back(Ref::share(v));
                }
                for (auto& e : static_cast<Dict*>(o)->entries) {
                    todo.push_back(e.key);
                    todo.push_back(e.value);
                }
                break;
            case Kind::Class:
                for (auto& [k, value] : static_cast<ClassObject*>(o)->attrs.items()) todo.push_back(value);
                break;
            case Kind::Str:
                if (has_attributes(o)) {
                    attribute_values(static_cast<StrInstance*>(o), todo);
                    found.push_back(Ref::share(v));
                }
                break;
            case Kind::Tuple:
                if (has_attributes(o)) {
                    attribute_values(static_cast<TupleInstance*>(o), todo);
                    found.push_back(Ref::share(v));
                }
                for (Obj x : static_cast<Tuple*>(o)->items) todo.push_back(x);
                break;
            case Kind::List:
                if (has_attributes(o)) {
                    attribute_values(static_cast<ListInstance*>(o), todo);
                    found.push_back(Ref::share(v));
                }
                for (Obj x : static_cast<List*>(o)->items) todo.push_back(x);
                break;
            case Kind::Set:
                for (auto& e : static_cast<SetObject*>(o)->table) todo.push_back(e.key);
                break;
            case Kind::Cell:
                todo.push_back(static_cast<Cell*>(o)->value);
                break;
            case Kind::PyFunction: {
                auto* f = static_cast<PyFunction*>(o);
                for (const Ref* r : {&f->defaults, &f->kwdefaults, &f->annotate, &f->dict}) todo.push_back(r->get());
                for (const Ref& r : f->closure) todo.push_back(r.get());
                break;
            }
            case Kind::Method:
                todo.push_back(static_cast<Method*>(o)->func);
                todo.push_back(static_cast<Method*>(o)->self);
                break;
            case Kind::Builtin:
                todo.push_back(static_cast<Builtin*>(o)->self);
                break;
            case Kind::Slice: {
                auto* sl = static_cast<SliceObject*>(o);
                for (Obj x : {sl->start, sl->stop, sl->step}) todo.push_back(x);
                break;
            }
            case Kind::DictView:
                todo.push_back(static_cast<DictView*>(o)->dict);
                break;
            case Kind::Iterator:
                todo.push_back(static_cast<Iterator*>(o)->seq);
                break;
            case Kind::Super: {
                auto* su = static_cast<SuperObject*>(o);
                for (Obj x : {su->type, su->obj, su->obj_type}) todo.push_back(x);
                break;
            }
            case Kind::Proxy:
                if (static_cast<Proxy*>(o)->of != nullptr) todo.push_back(Obj::of(static_cast<Proxy*>(o)->of));
                else todo.push_back(static_cast<Proxy*>(o)->mapping.get());
                break;
            case Kind::Module:                   // every module of the program's is a root already; the runtime's own (sys with its
                break;                           // standard streams, builtins) stay alive until the end, as CPython's do
            default:
                break;
        }
    }
}
void clear_module(Module* m) {
    for (std::size_t i = 0; i < m->dict->entries.size(); ++i) {
        Dict::Entry& e = m->dict->entries[i];
        if (e.key.is_unset() || e.value == None()) continue;
        if (const Str* k = as_str(e.key); k != nullptr && k->text == "__builtins__") continue;
        Obj old = std::exchange(e.value, None());
        decref(old);
    }
}
}  // namespace
void clear_modules(const std::unordered_set<Module*>& runtime_own) {
    // The finalisers run in sys.modules' order, __main__'s first (finalize_remove_modules, measured on 3.15.2); the namespaces are
    // then cleared the other way round (finalize_modules_clear_weaklist), the last module imported first, so that what the
    // program's modules use while they go (the standard streams, their codec) is still whole; one no longer in sys.modules goes first
    std::vector<Module*> order;
    std::unordered_set<Module*> seen(runtime_own);
    Dict* modules = sys_modules();
    for (std::size_t i = 0; i < modules->entries.size(); ++i) {
        Obj v = modules->entries[i].value;
        if (modules->entries[i].key.is_unset() || !is_kind(v, Kind::Module)) continue;
        auto* m = static_cast<Module*>(v.object());
        if (seen.insert(m).second) order.push_back(m);
    }
    std::vector<Module*> clearing;
    for (Module* m : all_modules())
        if (seen.insert(m).second) {
            order.push_back(m);
            clearing.push_back(m);
        }
    for (auto it = order.rbegin(); it != order.rend(); ++it)
        if (std::find(clearing.begin(), clearing.end(), *it) == clearing.end()) clearing.push_back(*it);
    // finalize_modules_delete_special: what a finaliser sees of sys from here on
    Module* sys = native_modules()["sys"];
    for (const char* n : {"path", "argv", "ps1", "ps2", "last_exc", "last_type", "last_value", "last_traceback",
                          "__interactivehook__", "meta_path"})
        put(sys->dict, n, None());
    for (auto [name, original] : std::initializer_list<std::pair<const char*, const char*>>{{"stdin", "__stdin__"}, {"stdout", "__stdout__"}, {"stderr", "__stderr__"}})
        put(sys->dict, name, dict_get(sys->dict, Obj::of(intern(original))));
    shutting_down() = true;
    dict_clear(modules);                         // finalize_clear_modules_dict; the modules live on (D-19)
    std::vector<Ref> found;
    std::unordered_set<Object*> reached;
    finalizable_from(order, found, reached);
    // handle_weakrefs: a reference with a callback to what the collector found is cleared first; one it
    // found too never has its callback called, and one without a callback lasts until the object is freed
    std::vector<std::pair<Ref, Ref>> callbacks;
    for (Object* target : reached) {
        auto* list = weak_list(target);
        if (list == nullptr) continue;
        std::vector<WeakRecord*> records = *list;
        for (WeakRecord* r : records) {
            if (r->callback == 0) continue;
            Ref fn = Ref::steal(Obj::of(reinterpret_cast<const Object*>(std::exchange(r->callback, 0))));
            weak_unlink(r);
            if (!reached.contains(r->holder) && r->holder->refs > 0) callbacks.emplace_back(Ref::share(Obj::of(r->holder)), std::move(fn));
        }
    }
    for (auto& [holder, fn] : callbacks) call_weakref_callback(fn.get(), holder.get());
    callbacks.clear();
    for (Ref& r : found)
        with_attribute_storage(r.get(), [](auto* inst) { detail::finalize_once(inst); });
    found.clear();
    for (Module* m : clearing) clear_module(m);
}

// _Py_HandleSystemExitAndKeyboardInterrupt: the exit status a SystemExit asks for: its `code`
// attribute (a subclass may have its own), read as parse_exit_code reads it: None is 0, an int that
// int truncated to a C int; anything else is printed, as is the exception if it has no such
// attribute, and is 1. Nothing that goes wrong printing it changes that.
int exit_status(Obj exc) {
    Ref code;
    try {
        code = getattr(exc, intern("code"));
    } catch (const PyError&) {
    }
    if (!code.get().is_unset()) {
        if (code.get() == None()) return 0;
        // parse_exit_code: (int)PyLong_AsLongLong, and -1 for what that cannot hold
        std::int64_t value;
        if (is_int(code.get())) return int_fits_i64(code.get(), value) ? static_cast<int>(value) : -1;
    }
    try {
        Ref text = str_of(code.get().is_unset() ? exc : code.get());
        write_stderr(as_str(text.get())->text);
    } catch (const PyError&) {
    }
    write_stderr("\n");
    return 1;
}

// CPython's main module (pymain_run_file, add_main_module): module_init_dict's names, then
// __builtins__ (the module), __file__, and the loader replacing the None in __loader__
Module* make_main(const char* main_file) {
    Module* main = new_module("__main__");
    put(main->dict, "__builtins__", Obj::of(builtins_module()));
    Ref file = str_new(main_file);
    put(main->dict, "__file__", file.get());
    dict_set(sys_modules(), Obj::of(intern("__main__")), Obj::of(main));
    return main;
}
}  // namespace

int run_main(int argc, char** argv, ModuleBody main_body, const char* main_file, const char* program_dir,
             std::initializer_list<PreludeModule> prelude, std::span<const ModuleEntry> modules) {
    int status = 0;
    std::unordered_set<Module*> runtime_own;
    try {
        try {
            set_locale_from_environment();   // _PyPreConfig: the LC_CTYPE locale, before anything reads the environment
            native_modules()["builtins"] = builtins_module();
            Module* sys = make_sys(argc, argv);
            native_modules()["sys"] = sys;
            init_types();
            init_imports(sys);
            register_modules(modules, program_dir);
            runtime_own = {builtins_module(), sys};
            Module* bootstrap = nullptr;
            Module* external = nullptr;
            ModuleBody external_body = nullptr;
            for (const PreludeModule& pm_entry : prelude) {
                // each prelude module runs as the module it names: `builtins` (its classes say so in
                // __module__) or `_frozen_importlib` (bootstrap.py). Its __all__ goes into builtins,
                // its __intrinsics__ to the runtime only, and its __type_methods__ onto the C++ types
                // (the containers' repr). It is given the runtime's primitives it needs (_dict_next,
                // and bootstrap.py's), which no program can name.
                Module* pm = new_module(pm_entry.name);
                runtime_own.insert(pm);
                {
                    Ref walk = own(new Builtin("_dict_next", i_dict_next));
                    put(pm->dict, "_dict_next", walk.get());
                    Ref lookup = own(new Builtin("_lookup_special", i_lookup_special));
                    put(pm->dict, "_lookup_special", lookup.get());
                    Ref index = own(new Builtin("_number_index", i_number_index));
                    put(pm->dict, "_number_index", index.get());
                    Ref sequence = own(new Builtin("_sequence_check", i_sequence_check));
                    put(pm->dict, "_sequence_check", sequence.get());
                    Ref tp_name = own(new Builtin("_tp_name", i_tp_name));
                    put(pm->dict, "_tp_name", tp_name.get());
                    Ref alloc = own(new Builtin("_bella_new_instance", i_bella_new_instance));
                    put(pm->dict, "_bella_new_instance", alloc.get());
                    Ref unpack = own(new Builtin("_unpack_keywords", i_unpack_keywords));   // _PyArg_UnpackKeywords, as every prelude has it
                    put(pm->dict, "_unpack_keywords", unpack.get());
                }
                if (std::string_view(pm_entry.name) == "_frozen_importlib") {
                    bootstrap = pm;
                    set_bootstrap_module(pm);
                    for (auto [n, fn] : std::initializer_list<std::pair<const char*, NativeFn>>{
                             {"_bella_find", i_bella_find}, {"_bella_exec", i_bella_exec},
                             {"_bella_is_builtin", i_bella_is_builtin}, {"_bella_create_builtin", i_bella_create_builtin}, {"_bella_refuse", i_bella_refuse},
                             {"_bella_import_warning", i_bella_import_warning}, {"_bella_set_lazy_attributes", i_bella_set_lazy_attributes},
                             {"_bella_shutting_down", i_bella_shutting_down}, {"_bella_ga_get", i_bella_ga_get}, {"_bella_caller_module", i_bella_caller_module},
                             {"_bella_structseq_finish", i_bella_structseq_finish}, {"_bella_structseq_make", i_bella_structseq_make}, {"_bella_pickle_layout", i_bella_pickle_layout}, {"_bella_no_tp_new", i_bella_no_tp_new},
                             {"_bella_tp_name_of", i_bella_tp_name_of}, {"_bella_instance_dict", i_bella_instance_dict}, {"_bella_structseq_hidden", i_bella_structseq_hidden},
                             {"_bella_keyword_suggestion", i_keyword_suggestion}}) {
                        Ref b = own(new Builtin(n, fn));
                        put(pm->dict, n, b.get());
                    }
                }
                if (std::string_view(pm_entry.name) == "_frozen_importlib_external") {   // bootstrap_external.py: _set_bootstrap_module's work, its primitives
                    put(pm->dict, "_bootstrap", Obj::of(bootstrap));
                    for (auto [n, fn] : std::initializer_list<std::pair<const char*, NativeFn>>{{"_bella_refuse", i_bella_refuse}, {"_cpython_table", i_cpython_table}}) {
                        Ref b = own(new Builtin(n, fn));
                        put(pm->dict, n, b.get());
                    }
                }
                if (std::string_view(pm_entry.name) == "_frozen_importlib_external") {
                    // its body reads the build's constants through int and str methods, which init_bigint and the others install
                    // after this loop: it runs then (below); the module is in sys.modules from here, as CPython's frozen one is
                    external = pm;
                    set_external_module(pm);
                    external_body = pm_entry.body;
                    dict_set(sys_modules(), Obj::of(intern(pm_entry.name)), Obj::of(pm));
                    put(bootstrap->dict, "_bootstrap_external", Obj::of(pm));
                    continue;
                }
                pm_entry.body(pm);
                if (std::string_view(pm_entry.name) == "_frozen_importlib")   // in sys.modules, as CPython's frozen module is: importlib's package imports it by name
                    dict_set(sys_modules(), Obj::of(intern(pm_entry.name)), Obj::of(pm));
                Obj all = dict_get(pm->dict, Obj::of(intern("__all__")));
                if (!all.is_unset())
                    for (Obj n : static_cast<List*>(all.object())->items) {
                        Obj v = dict_get(pm->dict, n);
                        if (is_kind(v, Kind::Class)) {
                            prelude_classes().insert(static_cast<ClassObject*>(v.object()));
                            forget_python_origin(static_cast<ClassObject*>(v.object()));
                            static_cast<ClassObject*>(v.object())->has_weakref = cpython_has("weakref", static_cast<ClassObject*>(v.object())->name);
                        }
                        if (is_kind(v, Kind::PyFunction)) v.object()->cls = types().builtin;   // print is a builtin
                        dict_set(builtins_module()->dict, n, v);
                    }
                if (Obj hidden = dict_get(pm->dict, Obj::of(intern("__hidden_classes__"))); !hidden.is_unset())
                    for (Obj n : static_cast<List*>(hidden.object())->items) {
                        auto* c = static_cast<ClassObject*>(dict_get(pm->dict, n).object());
                        const Obj* own_module = c->attrs.find(intern("__module__"));   // a type of another module's (string.templatelib.Template)
                        if (own_module != nullptr && as_str(*own_module) != nullptr && as_str(*own_module)->text != "builtins") {
                            present_native_class(c, as_str(*own_module)->text);
                        } else {
                            prelude_classes().insert(c);
                            forget_python_origin(c);
                            present_methods(c);
                            c->final_type = cpython_has("final", c->name);
                            c->has_weakref = cpython_has("weakref", c->name);
                        }
                        c->disallow_instantiation = cpython_attribute_kind(c, "__new__").empty();
                    }
                Obj intr = dict_get(pm->dict, Obj::of(intern("__intrinsics__")));
                if (!intr.is_unset())
                    for (Obj n : static_cast<List*>(intr.object())->items) dict_set(intrinsics(), n, dict_get(pm->dict, n));
                if (!all.is_unset())                 // now that the builtins have what a class's __new__ is wrapped in, and the runtime
                    for (Obj n : static_cast<List*>(all.object())->items)   // the prelude's own descriptor class (_GetSet)
                        if (Obj v = dict_get(pm->dict, n); is_kind(v, Kind::Class)) {
                            present_methods(static_cast<ClassObject*>(v.object()));
                            present_builtin_class(static_cast<ClassObject*>(v.object()));
                        }
                Obj tm = dict_get(pm->dict, Obj::of(intern("__type_methods__")));
                if (is_kind(tm, Kind::Dict))
                    for (auto& e : static_cast<Dict*>(tm.object())->entries) {
                        if (e.key.is_unset()) continue;
                        Obj cls = is_kind(e.key, Kind::Class) ? e.key : dict_get(builtins_module()->dict, e.key);   // a type, or a builtin's name
                        for (auto& m : static_cast<Dict*>(e.value.object())->entries)
                            if (!m.key.is_unset())
                                static_cast<ClassObject*>(cls.object())->set_attr(intern(as_str(m.key)->text), m.value);
                    }
            }
            init_slots();
            init_bigint();
            init_float();
            init_complex();
            init_generator();
            if (external != nullptr) {
                external_body(external);         // bootstrap_external.py, now that int and str have their methods
                // sys.meta_path: the finders the import system stands for, as CPython's _install and _install_external_importers
                // list them; the closed world's registry does their search, and a program reads the list (importlib.invalidate_caches)
                // but may not change it (E-04). sys.path_hooks stays absent: CPython's holds zipimport's class, which phase 1 lacks
                Ref finders = list_new({dict_get(bootstrap->dict, Obj::of(intern("BuiltinImporter"))), dict_get(bootstrap->dict, Obj::of(intern("FrozenImporter"))),
                                        dict_get(external->dict, Obj::of(intern("PathFinder")))});
                put(sys->dict, "meta_path", finders.get());
            }
            for (ClassObject* c : builtin_types())    // every file's methods made, those that are slot wrappers say so
                for (auto& [name, v] : c->attrs.items())
                    if (is_kind(v, Kind::Builtin)) {
                        auto* b = static_cast<Builtin*>(v.object());
                        if (b->self.is_unset() && b->binding == Binding::Method && cpython_attribute_kind(c, name->text) == "wrapper_descriptor") {
                            b->cls = types().wrapper_descriptor;
                            if (b->owner == nullptr) b->owner = c;
                        }
                    }
            adopt_functions(builtins_module());
            adopt_functions(native_modules()["sys"]);
            auto own_doc = [](ClassObject* c) {       // the built-in types' docstrings, as their own
                if (!c->attrs.contains(intern("__doc__")))
                    if (Obj doc = cpython_doc("type:" + c->name); doc != None() && !as_str(doc)->text.empty()) c->set_attr(intern("__doc__"), doc);
            };
            for (ClassObject* c : builtin_types()) own_doc(c);
            for (ClassObject* c : exception_classes()) own_doc(c);
            if (bootstrap != nullptr) present_as_c_types(bootstrap);
            if (bootstrap != nullptr) {                   // sys's named tuples, which are made in Python
                char buffer[64] = "";
                confstr(_CS_GNU_LIBPTHREAD_VERSION, buffer, sizeof buffer);
                std::int64_t randomized = 1;              // config.use_hash_seed == 0 || config.hash_seed != 0
                if (const char* seed = std::getenv("PYTHONHASHSEED"); seed != nullptr && *seed != '\0' && std::string_view(seed) != "random" && std::strtoul(seed, nullptr, 10) == 0) randomized = 0;
                Ref version = str_new(buffer), flag = int_from_i64(randomized);
                Ref surface = invoke(dict_get(bootstrap->dict, Obj::of(intern("_bella_sys_surface"))), {version.get(), flag.get()});
                auto* sys_dict = native_modules()["sys"]->dict;
                Ref names = list_new({});
                for (std::string_view n : cpython_names_of("stdlib")) list_append(names.get(), Obj::of(intern(std::string(n))));
                Ref stdlib = invoke(Obj::of(types().frozenset), {names.get()});
                put(sys_dict, "stdlib_module_names", stdlib.get());
                for (auto& e : static_cast<Dict*>(surface.get().object())->entries) {
                    if (e.key.is_unset()) continue;
                    if (as_str(e.key)->text == "_bella_unraisable_args") unraisable_args_type() = Ref::share(e.value);   // no module's
                    else dict_set(sys_dict, e.key, e.value);
                }
            }
            // importlib._bootstrap._setup: the built-in modules' specs and loaders
            {
                Ref names = tuple_new({Obj::of(intern("builtins")), Obj::of(intern("sys"))});
                Ref setup = builtin("_setup");
                invoke(setup.get(), {names.get()});
            }
            ensure_codecs();                     // _PyCodec_InitRegistry: the registry, then `encodings` imported, which registers its search
            invoke(codec_hooks().start.get(), {});
            {                                    // init_set_builtins_open: builtins.open is _io.open
                Ref io_name = str_new("_io");
                import_module_level(io_name.get(), Obj{}, Obj{}, Obj{}, 0);
                if (!io_hooks().open.get().is_unset()) put(builtins_module()->dict, "open", io_hooks().open.get());
            }
            {                                    // create_stdio: the three descriptors as _io objects; one that is not open is None (is_valid_fd)
                auto* sys_dict = native_modules()["sys"]->dict;
                // config_init_stdio_encoding: PYTHONIOENCODING is "encoding[:errors]"; an encoding alone makes the errors strict, and
                // what it leaves unset is UTF-8 (D-15) with surrogateescape; stderr's errors are always backslashreplace
                std::string encoding = "utf-8", errors = "surrogateescape";
                if (const char* opt = std::getenv("PYTHONIOENCODING"); opt != nullptr && *opt != '\0') {
                    std::string_view given(opt);
                    std::size_t colon = given.find(':');
                    std::string_view enc = given.substr(0, colon), err = colon == std::string_view::npos ? std::string_view{} : given.substr(colon + 1);
                    if (!enc.empty()) {
                        encoding = std::string(enc);
                        errors = "strict";
                    }
                    if (!err.empty()) errors = std::string(err);
                }
                auto make = [&](int fd, const char* name, const char* mode, const std::string& errs) -> Ref {
                    if (fcntl(fd, F_GETFD) < 0) return none_ref();
                    Ref fdo = int_from_i64(fd), n = str_new(name), m = str_new(mode), enc = str_new(encoding), e = str_new(errs);
                    return invoke(io_hooks().std_stream.get(), {fdo.get(), n.get(), m.get(), enc.get(), e.get()});
                };
                Ref in = make(0, "<stdin>", "rb", errors);
                put(sys_dict, "stdin", in.get());
                put(sys_dict, "__stdin__", in.get());
                Ref out = make(1, "<stdout>", "wb", errors);
                put(sys_dict, "stdout", out.get());
                put(sys_dict, "__stdout__", out.get());
                Ref err = make(2, "<stderr>", "wb", "backslashreplace");
                put(sys_dict, "stderr", err.get());
                put(sys_dict, "__stderr__", err.get());
            }
            hide_bootstrap_names();              // start-up is over: what the two import-system modules hold beyond CPython's names
            Module* main = make_main(main_file);
            if (bootstrap != nullptr) {
                Obj loader_class = dict_get(bootstrap->dict, Obj::of(intern("SourceFileLoader")));
                Ref file = str_new(main_file);
                Ref loader = invoke(loader_class, {Obj::of(intern("__main__")), file.get()});
                put(main->dict, "__loader__", loader.get());
            }
            main_body(main);
            flush_io();
        } catch (const PyError& e) {
            flush_io();                          // before the report (RL-227)
            if (isinstance(e.exc.get(), exception_class("SystemExit"))) {
                status = exit_status(e.exc.get());
            } else {
                // _PyErr_PrintEx, as Py_RunMain calls it: sys.last_exc and its three older names, then sys.excepthook(class,
                // exception, traceback). Without a hook CPython says so and writes the report; a hook that raises is reported
                // with the original after it, and one that exits gives the status (handle_system_exit)
                Obj raised = e.exc.get();
                Ref kind = Ref::share(Obj::of(type_of(raised)));
                Obj its = traceback_of(raised);
                Ref tb = is_kind(its, Kind::Traceback) ? Ref::share(its) : none_ref();
                auto* sys_dict = native_modules()["sys"]->dict;
                put(sys_dict, "last_exc", raised);
                put(sys_dict, "last_type", kind.get());
                put(sys_dict, "last_value", raised);
                put(sys_dict, "last_traceback", tb.get());
                status = 1;
                Ref hook = Ref::share(dict_get(sys_dict, Obj::of(intern("excepthook"))));
                if (hook.get().is_unset()) {
                    write_stderr("sys.excepthook is missing\n");
                    print_traceback(raised);
                } else {
                    try {
                        invoke(hook.get(), {kind.get(), raised, tb.get()});
                    } catch (const PyError& failed) {
                        if (isinstance(failed.exc.get(), exception_class("SystemExit"))) {
                            status = exit_status(failed.exc.get());
                        } else {
                            write_stderr("Error in sys.excepthook:\n");
                            print_traceback(failed.exc.get());
                            write_stderr("\nOriginal exception was:\n");
                            print_traceback(raised);
                        }
                    }
                }
            }
        }
        // Py_FinalizeEx, on every way out of the program but a refusal. First make_pre_finalization_calls, while the
        // program is whole: threading._shutdown if threading is among sys.modules (wait_for_thread_shutdown; what it
        // raises is reported as ignored), then atexit's handlers (_PyAtExit_Call: the prelude's, there once atexit was
        // imported). One round is all: a handler's own registration goes with the list, and no thread is left to wait for.
        // Then flush_std_files, whose failure is exit status 120 (reported as an exception ignored), and the modules'
        // globals go (spec section 9)
        if (sys_modules() != nullptr) {
            try {
                if (Obj threading = dict_get(sys_modules(), Obj::of(intern("threading"))); !threading.is_unset()) {
                    Ref shutdown = getattr(threading, intern("_shutdown"));
                    invoke(shutdown.get(), {});
                }
            } catch (const PyError& e) {
                report_unraisable("Exception ignored on threading shutdown", e);
            }
            if (Obj handlers = dict_get(intrinsics(), Obj::of(intern("_atexit_call"))); !handlers.is_unset()) invoke(handlers, {});
            if (!flush_std_stream("stdout", true)) status = 120;
            if (!flush_std_stream("stderr", false)) status = 120;
            clear_modules(runtime_own);
            if (!flush_std_stream("stdout", true)) status = 120;   // again, for what the finalisers printed
            if (!flush_std_stream("stderr", false)) status = 120;
        }
    } catch (const NotImplemented& e) {
        try {
            flush_std_stream("stdout");
        } catch (const NotImplemented&) {
        }
        err_stream().write(std::string("bella: not implemented: ") + e.what() + "\n");
        err_stream().flush();
        return 70;
    }
    out_stream().flush();
    err_stream().flush();
    return status;
}

}  // namespace bella
