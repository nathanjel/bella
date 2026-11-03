// runtime/src/call.cpp -- the call protocol and argument binding, function objects, names and
// modules, the C++ builtins, sys and its streams, the intrinsics, and the program's start and end
// (bella/runtime.hpp).
#include "bella/runtime.hpp"

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <string_view>
#include <unistd.h>
#include <unordered_map>
#include <unordered_set>

namespace bella {

namespace {
int& recursion_depth() {
    static int depth = 0;
    return depth;
}
constexpr int RECURSION_LIMIT = 1000;            // sys.getrecursionlimit()'s default (spec D-17)

std::unordered_map<ClassObject*, NativeFn>& constructors() {
    static std::unordered_map<ClassObject*, NativeFn> table;
    return table;
}

Ref positional_only(Args a, const char* name, std::size_t lo, std::size_t hi) {
    if (a.nkw != 0) raise_new("TypeError", std::string(name) + "() takes no keyword arguments");
    if (a.npos < lo || a.npos > hi) {
        std::string expected = lo == hi ? std::to_string(lo) : "from " + std::to_string(lo) + " to " + std::to_string(hi);
        raise_new("TypeError", std::string(name) + "() takes " + expected + " positional argument" + (hi == 1 ? "" : "s") +
                                   " but " + std::to_string(a.npos) + " were given");
    }
    return Ref{};
}

// CPython's argument checks by calling convention; each message is CPython's for that kind.
void no_keywords(Args a, const std::string& qualname) {
    if (a.nkw != 0) raise_new("TypeError", qualname + "() takes no keyword arguments");
}
void noargs(Args a, const std::string& qualname) {                     // METH_NOARGS
    no_keywords(a, qualname);
    if (a.npos != 0) raise_new("TypeError", qualname + "() takes no arguments (" + std::to_string(a.npos) + " given)");
}
void onearg(Args a, const std::string& qualname) {                     // METH_O
    no_keywords(a, qualname);
    if (a.npos != 1) raise_new("TypeError", qualname + "() takes exactly one argument (" + std::to_string(a.npos) + " given)");
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
void clinic(Args a, const std::string& name, const std::string& qualname, std::size_t lo, std::size_t hi) {
    no_keywords(a, qualname);
    check_positional(a, name, lo, hi);
}
}  // namespace

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
                    raise_new("TypeError", "unbound method " + (b->owner ? b->owner->name + "." : "") + b->name + "() needs an argument");
                if (b->owner != nullptr && !isinstance(a.pos(0), b->owner))
                    raise_new("TypeError", "descriptor '" + b->name + "' for '" + b->owner->name + "' objects doesn't apply to a '" +
                                               type_of(a.pos(0))->name + "' object");
                return b->fn(a.pos(0), Args{a.data + 1, a.npos - 1, a.kwnames, a.nkw});
            }
            return b->fn(b->self, a);
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
    } else if (args.npos > n) {
        std::size_t ndefaults = fn->defaults.get().is_unset() ? 0 : static_cast<Tuple*>(fn->defaults.get().object())->items.size();
        std::size_t given_kwonly = 0;
        for (std::size_t k = 0; k < args.nkw; ++k)
            for (std::size_t j = n; j < n + nkwonly; ++j)
                if (args.kwnames[k]->text == c.varnames[j]) ++given_kwonly;
        std::string takes = ndefaults ? "from " + std::to_string(n - ndefaults) + " to " + std::to_string(n) : std::to_string(n);
        std::string plural = (ndefaults == 0 && n == 1) ? "" : "s";
        std::string kwpart = given_kwonly ? " positional argument" + std::string(args.npos == 1 ? "" : "s") + " (and " +
                                                std::to_string(given_kwonly) + " keyword-only argument" +
                                                (given_kwonly == 1 ? "" : "s") + ")"
                                          : "";
        raise_new("TypeError", who + " takes " + takes + " positional argument" + plural + " but " +
                                   std::to_string(args.npos) + (given_kwonly ? kwpart : (args.npos == 1 ? " was" : " were")) +
                                   " given");
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
            if (kwdict == nullptr) raise_new("TypeError", who + " got an unexpected keyword argument '" + name->text + "'");
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
    // defaults for the positional parameters not given
    std::size_t ndefaults = 0;
    std::vector<Obj>* defaults = nullptr;
    if (!fn->defaults.get().is_unset()) {
        defaults = &static_cast<Tuple*>(fn->defaults.get().object())->items;
        ndefaults = defaults->size();
    }
    std::vector<std::string> missing;
    for (std::size_t i = args.npos; i < n; ++i) {
        if (!slot[i]->get().is_unset()) continue;
        if (i >= n - ndefaults) *slot[i] = Ref::share((*defaults)[i - (n - ndefaults)]);
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
        if (free)
            raise_new("NameError", std::string("cannot access free variable '") + name +
                                       "' where it is not associated with a value in enclosing scope");
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
    bella::setattr(static_cast<Instance*>(exc.get().object()), intern("name"), Obj::of(name));
    raise(exc.get());
}
}  // namespace

Ref load_global(Module* m, const Str* name) {
    Obj v = dict_get(m->dict, Obj::of(name));
    if (v.is_unset()) v = dict_get(builtins_module()->dict, Obj::of(name));
    if (v.is_unset()) {
        refuse_absent_global(name);
        raise_name_error(name);
    }
    return Ref::share(v);
}
Ref load_name(Obj ns, Module* m, const Str* name) {
    Ref v = mapping_get(ns, Obj::of(name));      // a class namespace may be any mapping (__prepare__)
    if (!v.get().is_unset()) return v;
    return load_global(m, name);
}
void store_name(Obj ns, const Str* name, Ref value) { mapping_set(ns, Obj::of(name), value.get()); }
void store_global(Module* m, const Str* name, Ref value) { dict_set(m->dict, Obj::of(name), value.get()); }
void delete_name(Obj ns, const Str* name) {
    if (is_kind(ns, Kind::Dict)) {
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
Stream& stream_of(Obj self) { return static_cast<Native*>(self.object())->tag == 2 ? err_stream() : out_stream(); }

Ref textio_write(Obj self, Args a) {
    onearg(a, "TextIOWrapper.write");
    const Str* s = as_str(a.pos(0));
    if (s == nullptr) raise_new("TypeError", "write() argument must be str, not " + type_of(a.pos(0))->name);
    stream_of(self).write(s->text);
    return Ref::steal(Obj::small(static_cast<std::int64_t>(s->length)));
}
Ref textio_flush(Obj self, Args a) {
    noargs(a, "TextIOWrapper.flush");
    stream_of(self).flush();
    return none_ref();
}

// ---- the C++ builtins ----
Ref b_len(Obj, Args a) {
    onearg(a, "len");
    Obj v = a.pos(0);
    if (const Str* s = as_str(v)) return Ref::steal(Obj::small(static_cast<std::int64_t>(s->length)));
    if (is_kind(v, Kind::Tuple)) return Ref::steal(Obj::small(static_cast<std::int64_t>(static_cast<Tuple*>(v.object())->items.size())));
    if (is_kind(v, Kind::List)) return Ref::steal(Obj::small(static_cast<std::int64_t>(static_cast<List*>(v.object())->items.size())));
    if (is_kind(v, Kind::Dict)) return Ref::steal(Obj::small(static_cast<std::int64_t>(static_cast<Dict*>(v.object())->used)));
    if (is_kind(v, Kind::DictView))
        return Ref::steal(Obj::small(static_cast<std::int64_t>(static_cast<Dict*>(static_cast<DictView*>(v.object())->dict.object())->used)));
    if (is_kind(v, Kind::Range)) return Ref::steal(Obj::small(static_cast<Range*>(v.object())->length));
    bool has = false;
    Ref r = call_special(v, "__len__", {}, &has);
    if (has) return Ref::steal(Obj::small(length_value(r.get())));     // as truth takes it (A9-14)
    raise_new("TypeError", "object of type '" + type_of(v)->name + "' has no len()");
}
Ref b_repr(Obj, Args a) {
    onearg(a, "repr");
    return repr_of(a.pos(0));
}
Ref b_format(Obj, Args a) {
    clinic(a, "format", "format", 1, 2);
    Obj spec = a.npos > 1 ? a.pos(1) : Obj{};
    const Str* s = spec.is_unset() ? nullptr : as_str(spec);
    if (!spec.is_unset() && s == nullptr)
        raise_new("TypeError", "format() argument 2 must be str, not " + type_of(spec)->name);
    if (is_kind(a.pos(0), Kind::Instance))
        return call_special(a.pos(0), "__format__", {spec.is_unset() ? str_new("").get() : spec});
    if (s != nullptr && s->length != 0) throw NotImplemented("format() with a format specification");
    return str_of(a.pos(0));
}
Ref b_isinstance(Obj, Args a) {
    clinic(a, "isinstance", "isinstance", 2, 2);
    ClassObject* c = type_of(a.pos(0));
    auto check = [&](Obj spec) {
        if (!is_kind(spec, Kind::Class))
            raise_new("TypeError", "isinstance() arg 2 must be a type, a tuple of types, or a union");
        return std::find(c->mro.begin(), c->mro.end(), static_cast<ClassObject*>(spec.object())) != c->mro.end();
    };
    Obj spec = a.pos(1);
    if (is_kind(spec, Kind::Tuple)) {
        for (Obj s : static_cast<Tuple*>(spec.object())->items) if (check(s)) return Ref::steal(boolean(true));
        return Ref::steal(boolean(false));
    }
    return Ref::steal(boolean(check(spec)));
}
Ref attr_name(Obj v, const char* who) {
    const Str* s = as_str(v);
    if (s == nullptr) raise_new("TypeError", std::string(who) + "(): attribute name must be string, not '" + type_of(v)->name + "'");
    return Ref::share(Obj::of(intern(s->text)));
}
bool is_attribute_error(const PyError& e) { return isinstance(e.exc.get(), exception_class("AttributeError")); }
Ref b_getattr(Obj, Args a) {
    if (a.nkw != 0) raise_new("TypeError", "getattr() takes no keyword arguments");
    if (a.npos < 2 || a.npos > 3) raise_new("TypeError", "getattr expected 2 or 3 arguments, got " + std::to_string(a.npos));
    Ref n = attr_name(a.pos(1), "getattr");
    if (a.npos == 2) return getattr(a.pos(0), static_cast<const Str*>(n.get().object()));
    try {
        return getattr(a.pos(0), static_cast<const Str*>(n.get().object()));
    } catch (const PyError& e) {
        if (!is_attribute_error(e)) throw;
        return Ref::share(a.pos(2));
    }
}
Ref b_hasattr(Obj, Args a) {
    clinic(a, "hasattr", "hasattr", 2, 2);
    Ref n = attr_name(a.pos(1), "hasattr");
    try {
        getattr(a.pos(0), static_cast<const Str*>(n.get().object()));
        return Ref::steal(boolean(true));
    } catch (const PyError& e) {
        if (!is_attribute_error(e)) throw;
        return Ref::steal(boolean(false));
    }
}
Ref b_setattr(Obj, Args a) {
    clinic(a, "setattr", "setattr", 3, 3);
    Ref n = attr_name(a.pos(1), "setattr");
    setattr(a.pos(0), static_cast<const Str*>(n.get().object()), a.pos(2));
    return none_ref();
}
Ref b_delattr(Obj, Args a) {
    clinic(a, "delattr", "delattr", 2, 2);
    Ref n = attr_name(a.pos(1), "delattr");
    delattr(a.pos(0), static_cast<const Str*>(n.get().object()));
    return none_ref();
}
Ref b_issubclass(Obj, Args a) {
    clinic(a, "issubclass", "issubclass", 2, 2);
    if (!is_kind(a.pos(0), Kind::Class)) raise_new("TypeError", "issubclass() arg 1 must be a class");
    auto* c = static_cast<ClassObject*>(a.pos(0).object());
    auto check = [&](Obj spec) {
        if (!is_kind(spec, Kind::Class))
            raise_new("TypeError", "issubclass() arg 2 must be a class, a tuple of classes, or a union");
        return is_subclass(c, static_cast<ClassObject*>(spec.object()));
    };
    if (is_kind(a.pos(1), Kind::Tuple)) {
        for (Obj s : static_cast<Tuple*>(a.pos(1).object())->items) if (check(s)) return Ref::steal(boolean(true));
        return Ref::steal(boolean(false));
    }
    return Ref::steal(boolean(check(a.pos(1))));
}
Ref b_id(Obj, Args a) {
    onearg(a, "id");
    Obj v = a.pos(0);
    return Ref::steal(Obj::small(static_cast<std::int64_t>(v.is_small() ? (static_cast<std::uint64_t>(v.small_value()) << 1) | 1
                                                                        : reinterpret_cast<std::uintptr_t>(v.object()) >> 1)));
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
    if (items.empty()) raise_new("IndexError", "pop from empty list");
    std::int64_t i = a.npos ? index_value(a.pos(0)) : -1;          // bool and __index__, before any change (A9-11)
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
Ref list_insert_m(Obj self, Args a) {
    clinic(a, "insert", "list.insert", 2, 2);
    auto& items = list_self(self)->items;
    std::int64_t i = index_value(a.pos(0));
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
        if (!v.is_small() && !is_kind(v, Kind::Bool) &&
            (!is_kind(v, Kind::Instance) || type_lookup(type_of(v), intern("__index__")).is_unset()))
            raise_new("TypeError", "slice indices must be integers or have an __index__ method");
        std::int64_t x = index_value(v);
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
Ref list_remove_m(Obj self, Args a) {
    onearg(a, "list.remove");
    std::int64_t i = list_find(self, a.pos(0));
    if (i < 0) raise_new("ValueError", "list.remove(x): x not in list");
    auto& items = list_self(self)->items;
    Obj old = items[static_cast<std::size_t>(i)];
    items.erase(items.begin() + i);
    decref(old);
    return none_ref();
}
Ref list_count_m(Obj self, Args a) {
    onearg(a, "list.count");
    std::int64_t n = 0;
    for (Obj x : std::vector<Obj>(list_self(self)->items)) {
        Ref hold = Ref::share(x);
        if (x == a.pos(0) || truth(compare(CmpOp::Eq, x, a.pos(0)).get())) ++n;
    }
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
Ref getitem_m(Obj self, Args a) { dunder_args(self, a, "__getitem__", 1); return getitem(self, a.pos(0)); }
Ref setitem_m(Obj self, Args a) { dunder_args(self, a, "__setitem__", 2); setitem(self, a.pos(0), a.pos(1)); return none_ref(); }
Ref contains_m(Obj self, Args a) { dunder_args(self, a, "__contains__", 1); return compare(CmpOp::In, a.pos(0), self); }
Ref iter_m(Obj self, Args a) { dunder_args(self, a, "__iter__", 0); return iter(self); }
Dict* dict_self(Obj self) { return static_cast<Dict*>(self.object()); }   // the descriptor checked the receiver
Ref dict_get_m(Obj self, Args a) {
    clinic(a, "get", "dict.get", 1, 2);
    Obj v = dict_get(dict_self(self), a.pos(0));
    return !v.is_unset() ? Ref::share(v) : a.npos > 1 ? Ref::share(a.pos(1)) : none_ref();
}
Ref dict_pop_m(Obj self, Args a) {
    clinic(a, "pop", "dict.pop", 1, 2);
    Obj v = dict_get(dict_self(self), a.pos(0));
    if (v.is_unset()) {
        if (a.npos > 1) return Ref::share(a.pos(1));
        Ref exc = invoke(Obj::of(exception_class("KeyError")), {a.pos(0)});
        raise(exc.get());
    }
    Ref out = Ref::share(v);
    dict_del(dict_self(self), a.pos(0));
    return out;
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

Ref dict_clear_m(Obj self, Args a) {
    noargs(a, "dict.clear");
    dict_clear(dict_self(self));
    return none_ref();
}
Ref dict_copy_m(Obj self, Args a) {
    noargs(a, "dict.copy");
    Ref out = dict_new();
    dict_copy_into(static_cast<Dict*>(out.get().object()), dict_self(self));
    return out;
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
    auto it = std::find_if(d->entries.rbegin(), d->entries.rend(), [](auto& e) { return !e.key.is_unset(); });
    Ref key = Ref::share(it->key);
    Obj value = dict_pop(d, key.get(), it->hash);
    Ref v = Ref::steal(value);
    return tuple_new({key.get(), v.get()});
}
Ref dict_setdefault_m(Obj self, Args a) {
    clinic(a, "setdefault", "dict.setdefault", 1, 2);
    Dict* d = dict_self(self);
    std::int64_t hash = hash_of(a.pos(0));
    Obj v = dict_find(d, a.pos(0), hash);
    if (!v.is_unset()) return Ref::share(v);
    Obj dflt = a.npos > 1 ? a.pos(1) : None();
    dict_store(d, a.pos(0), hash, dflt);
    return Ref::share(dflt);
}
}  // namespace

void dict_update_arg(Obj self, Obj arg) {           // a mapping (keys()), else an iterable of pairs
    Dict* d = static_cast<Dict*>(self.object());
    if (is_kind(arg, Kind::Dict) || !type_lookup(type_of(arg), intern("keys")).is_unset()) {
        dict_update(self, arg);
        return;
    }
    Ref it = iter(arg);
    for (std::int64_t i = 0;; ++i) {
        Ref item = for_next(it.get());
        if (is_end(item)) break;
        Ref pair = iter(item.get());
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
Ref dict_fromkeys_m(Obj cls, Args a) {          // a classmethod: cls is dict
    clinic(a, "fromkeys", "dict.fromkeys", 1, 2);
    if (cls.object() != Obj::of(types().dict).object()) throw NotImplemented("dict.fromkeys on a subclass of dict");
    Ref out = dict_new();
    Obj value = a.npos > 1 ? a.pos(1) : None();
    Ref it = iter(a.pos(0));
    for (;;) {
        Ref k = for_next(it.get());
        if (is_end(k)) break;
        dict_set(static_cast<Dict*>(out.get().object()), k.get(), value);
    }
    return out;
}

Ref b_iter(Obj, Args a) {
    clinic(a, "iter", "iter", 1, 2);
    if (a.npos == 2) throw NotImplemented("iter(callable, sentinel)");
    return iter(a.pos(0));
}
Ref b_next(Obj, Args a) {
    clinic(a, "next", "next", 1, 2);
    if (!is_kind(a.pos(0), Kind::Iterator))
        raise_new("TypeError", "'" + type_of(a.pos(0))->name + "' object is not an iterator");
    Ref v = for_next(a.pos(0));
    if (!is_end(v)) return v;
    if (a.npos > 1) return Ref::share(a.pos(1));
    Ref exc = invoke(Obj::of(exception_class("StopIteration")), {});
    raise(exc.get());
}
Ref b_hash(Obj, Args a) {
    onearg(a, "hash");
    return Ref::steal(Obj::small(hash_of(a.pos(0))));
}
Ref b_abs(Obj, Args a) {                      // PyNumber_Absolute: the int's own, else __abs__ (A9-22)
    onearg(a, "abs");
    Obj v = a.pos(0);
    if (v.is_small()) return v.small_value() < 0 ? unary_neg(v) : Ref::share(v);
    if (is_kind(v, Kind::Bool)) return Ref::steal(Obj::small(static_cast<BoolObject*>(v.object())->value ? 1 : 0));
    bool has = false;
    Ref r = call_special(v, "__abs__", {}, &has);
    if (has) return r;
    raise_new("TypeError", "bad operand type for abs(): '" + type_of(v)->name + "'");
}
Ref b_callable(Obj, Args a) {
    onearg(a, "callable");
    Kind k = a.pos(0).is_object() ? a.pos(0).object()->kind : Kind::Bool;
    bool yes = k == Kind::PyFunction || k == Kind::Builtin || k == Kind::Method || k == Kind::Class || k == Kind::Function;
    if (k == Kind::Instance) yes = a.pos(0).object()->cls->has("__call__");
    return Ref::steal(boolean(yes));
}
Ref b_ord(Obj, Args a) {
    onearg(a, "ord");
    const Str* s = as_str(a.pos(0));
    if (s == nullptr) raise_new("TypeError", "ord() expected string of length 1, but " + type_of(a.pos(0))->name + " found");
    if (s->length != 1)
        raise_new("TypeError", "ord() expected a character, but string of length " + std::to_string(s->length) + " found");
    return Ref::steal(Obj::small(static_cast<std::int64_t>(s->at(0))));
}
Ref b_chr(Obj, Args a) {
    onearg(a, "chr");
    Obj v = a.pos(0);
    if (!v.is_small()) raise_new("TypeError", "'" + type_of(v)->name + "' object cannot be interpreted as an integer");
    std::int64_t c = v.small_value();
    if (c < 0 || c > 0x10FFFF) raise_new("ValueError", "chr() arg not in range(0x110000)");
    return str_from_codepoints(std::u32string(1, static_cast<char32_t>(c)));
}

// constructors of the C++ types
Ref c_str(Obj, Args a) {
    if (a.nkw != 0) throw NotImplemented("str() with keywords (encoding, errors)");
    if (a.npos > 1) throw NotImplemented("str(bytes, encoding)");
    return a.npos == 0 ? str_new("") : str_of(a.pos(0));
}
Ref c_bool(Obj, Args a) {
    clinic(a, "bool", "bool", 0, 1);
    return Ref::steal(boolean(a.npos == 1 && truth(a.pos(0))));
}
Ref c_range(Obj, Args a) {
    clinic(a, "range", "range", 1, 3);
    std::int64_t v[3] = {0, 0, 1};
    for (std::size_t i = 0; i < a.npos; ++i) {
        Obj x = a.pos(i);
        if (x.is_small()) v[i] = x.small_value();
        else if (is_kind(x, Kind::Bool)) v[i] = static_cast<BoolObject*>(x.object())->value;
        else raise_new("TypeError", "'" + type_of(x)->name + "' object cannot be interpreted as an integer");
    }
    if (a.npos == 1) { v[1] = v[0]; v[0] = 0; }
    if (v[2] == 0) raise_new("ValueError", "range() arg 3 must not be zero");
    return own(new Range(v[0], v[1], v[2]));
}
Ref c_tuple(Obj, Args a) {
    clinic(a, "tuple", "tuple", 0, 1);
    if (a.npos == 0) return tuple_new({});
    if (is_kind(a.pos(0), Kind::Tuple)) return Ref::share(a.pos(0));
    Ref l = list_new({});
    list_extend(l.get(), a.pos(0));
    return list_to_tuple(l.get());
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
    Ref it = iter(a.pos(0));
    std::size_t i = 0;
    for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get()), ++i) {
        const Str* s = as_str(v.get());
        if (s == nullptr)
            raise_new("TypeError", "sequence item " + std::to_string(i) + ": expected str instance, " +
                                       type_of(v.get())->name + " found");
        if (i > 0) out += sep->text;
        out += s->text;
    }
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
    Types& t = types();
    for (auto [name, cls, ctor] : std::initializer_list<std::tuple<const char*, ClassObject*, NativeFn>>{
             {"str", t.str, c_str}, {"type", t.type, nullptr}, {"bool", t.bool_, c_bool}, {"range", t.range, c_range},
             {"tuple", t.tuple, c_tuple}, {"list", t.list, c_list}, {"int", t.int_, nullptr},
             {"object", t.object, nullptr}, {"dict", t.dict, nullptr}, {"float", t.float_, nullptr}}) {
        put(d, name, Obj::of(cls));
        if (ctor != nullptr) constructors()[cls] = ctor;
    }
    for (const char* n : {"BaseException", "Exception", "SystemExit", "KeyboardInterrupt", "GeneratorExit",
                          "ArithmeticError", "ZeroDivisionError", "OverflowError", "AssertionError", "AttributeError",
                          "LookupError", "IndexError", "KeyError", "NameError", "UnboundLocalError", "RuntimeError",
                          "NotImplementedError", "RecursionError", "StopIteration", "TypeError", "ValueError",
                          "ImportError", "ModuleNotFoundError", "UnicodeError"})
        put(d, n, Obj::of(exception_class(n)));
    put(d, "None", None());
    put(d, "True", boolean(true));
    put(d, "False", boolean(false));
    put(d, "NotImplemented", Obj::of(NOTIMPLEMENTED));
    put(d, "Ellipsis", Obj::of(ELLIPSIS));
    put_builtin(d, "len", b_len);
    put_builtin(d, "repr", b_repr);
    put_builtin(d, "format", b_format);
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
    put(d, "slice", Obj::of(t.slice));
    put(d, "set", Obj::of(t.set));
    put(d, "frozenset", Obj::of(t.frozenset));
    method(t.str, "join", str_join);
    for (ClassObject* c : {t.list, t.tuple, t.str, t.dict}) {
        method(c, "__getitem__", getitem_m);
        method(c, "__contains__", contains_m);
        method(c, "__iter__", iter_m);
    }
    method(t.list, "append", list_append_m);
    method(t.list, "extend", list_extend_m);
    method(t.list, "pop", list_pop_m);
    method(t.list, "__len__", list_len_m);
    method(t.list, "clear", list_clear_m);
    method(t.list, "insert", list_insert_m);
    method(t.list, "index", list_index_m);
    method(t.list, "remove", list_remove_m);
    method(t.list, "count", list_count_m);
    method(t.list, "reverse", list_reverse_m);
    method(t.list, "copy", list_copy_m);
    method(t.list, "__setitem__", setitem_m);
    method(t.dict, "__setitem__", setitem_m);
    method(t.dict, "__len__", dict_len_m);
    method(t.dict, "get", dict_get_m);
    method(t.dict, "pop", dict_pop_m);
    method(t.dict, "keys", dict_keys_m);
    method(t.dict, "items", dict_items_m);
    method(t.dict, "values", dict_values_m);
    for (ClassObject* v : {t.dict_keys, t.dict_values, t.dict_items}) {
        method(v, "__len__", view_len_m);
        method(v, "__iter__", view_iter_m);
        if (v != t.dict_values) method(v, "__contains__", view_contains_m);
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
    }
    method(t.textio, "write", textio_write);
    method(t.textio, "flush", textio_flush);
    put(d, "__name__", m->name.get());
    return m;
}

Module* make_sys(int argc, char** argv) {
    auto* m = new Module("sys");
    Dict* d = m->dict;
    auto* out = new Native(types().textio);
    out->tag = 1;
    Ref o = own(out);
    put(d, "stdout", o.get());
    put(d, "__stdout__", o.get());
    auto* err = new Native(types().textio);
    err->tag = 2;
    Ref e = own(err);
    put(d, "stderr", e.get());
    put(d, "__stderr__", e.get());
    Ref args = list_new({});
    for (int i = 0; i < argc; ++i) {
        Ref s = str_new(argv[i]);
        list_append(args.get(), s.get());
    }
    put(d, "argv", args.get());
    // no maxsize: CPython's is 2**63 - 1, beyond the immediates, so it is refused until big ints
    return m;
}

std::unordered_map<std::string, Module*>& native_modules() {
    static std::unordered_map<std::string, Module*> table;
    return table;
}

// ---- names CPython has and the runtime lacks yet ----
#include "cpython_names.inc"

const CPythonName* cpython_find(std::string_view scope, std::string_view name) {
    std::string key;
    key.reserve(scope.size() + 1 + name.size());
    key.append(scope).append(":").append(name);
    auto it = std::lower_bound(std::begin(CPYTHON_NAMES), std::end(CPYTHON_NAMES), std::string_view(key),
                               [](const CPythonName& e, std::string_view k) { return e.key < k; });
    return it != std::end(CPYTHON_NAMES) && it->key == key ? &*it : nullptr;
}
bool cpython_has(std::string_view scope, std::string_view name) { return cpython_find(scope, name) != nullptr; }
std::unordered_set<const ClassObject*>& prelude_classes() {     // the prelude's builtins (property, ...)
    static std::unordered_set<const ClassObject*> classes;
    return classes;
}
void refuse_in(const std::vector<ClassObject*>& mro, const Str* name) {
    for (const ClassObject* c : mro)
        if ((!c->heap_type || prelude_classes().contains(c)) && cpython_has(c->name, name->text))
            throw NotImplemented(c->name + "." + name->text + " (CPython has it; the runtime does not yet)");
}
}  // namespace

void refuse_absent_attribute(Obj obj, const Str* name) {
    if (is_kind(obj, Kind::Module)) {
        auto* m = static_cast<Module*>(obj.object());
        const std::string& mod = as_str(m->name.get())->text;
        auto it = native_modules().find(mod);
        if (it != native_modules().end() && it->second == m && cpython_has(mod, name->text))
            throw NotImplemented(mod + "." + name->text + " (CPython has it; the runtime does not yet)");
    }
    if (is_kind(obj, Kind::Class)) refuse_in(static_cast<ClassObject*>(obj.object())->mro, name);
    refuse_in(type_of(obj)->mro, name);
}
std::string_view cpython_attribute_kind(const ClassObject* owner, std::string_view name) {
    const CPythonName* e = cpython_find(owner->name, name);
    return e != nullptr ? e->kind : std::string_view{};
}
bool presents_as_builtin(Obj f) { return is_kind(f, Kind::PyFunction) && f.object()->cls == types().builtin; }
bool immutable_type(const ClassObject* c) { return !c->heap_type || prelude_classes().contains(c); }
void refuse_unimplemented_operator(const char* scope, Obj a, const std::string& sym, Obj b) {
    auto name = [](Obj v) { return is_kind(v, Kind::Instance) ? std::string("instance") : type_of(v)->name; };
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
Module* new_module(const char* name) {
    auto* m = new Module(name);
    put(m->dict, "__name__", m->name.get());
    return m;
}

namespace {
Dict* intrinsics() {                           // what the prelude gives the runtime, not the program
    static Dict* d = [] {
        auto* x = new Dict;
        x->flags |= IMMORTAL;
        return x;
    }();
    return d;
}
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
    if (is_kind(v, Kind::Tuple)) return Ref::share(v);
    // _Py_Check_ArgsIterable: an __iter__, or a sequence's __getitem__
    if (type_lookup(type_of(v), intern("__iter__")).is_unset() && type_lookup(type_of(v), intern("__getitem__")).is_unset() &&
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

void register_intrinsics() {
    static bool done = false;
    if (done) return;
    done = true;
    for (auto [name, fn] : std::initializer_list<std::pair<const char*, NativeFn>>{
             {"special", i_special}, {"set_add", i_set_add}, {"map_add", i_map_add}, {"unpack", i_unpack},
             {"call_args_tuple", i_call_args_tuple}}) {
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
    if (v.is_unset()) throw NotImplemented(std::string("the intrinsic '") + name + "'");
    return Ref::share(v);
}

// ---- the intrinsics L2 calls by name (Runtime ops) ----
Ref runtime_call(const char* intrinsic, Obj ns, Module* m, std::initializer_list<Obj> args,
                 std::initializer_list<const Str*> kwnames, std::initializer_list<Obj> kwvalues) {
    std::string_view name(intrinsic);
    std::vector<Obj> a(args);
    if (name == "import_name") {
        const Str* mod = as_str(a.at(0));
        auto it = native_modules().find(mod->text);
        if (it == native_modules().end()) throw NotImplemented("importing '" + mod->text + "' (step 3b: compiled imports)");
        return Ref::share(Obj::of(it->second));
    }
    if (name == "import_from") {
        const Str* attr = as_str(a.at(1));
        Obj v = dict_get(static_cast<Module*>(a.at(0).object())->dict, Obj::of(attr));
        if (v.is_unset())
            raise_new("ImportError", "cannot import name '" + attr->text + "' from '" +
                                         as_str(static_cast<Module*>(a.at(0).object())->name.get())->text + "'");
        return Ref::share(v);
    }
    (void)ns;
    (void)m;
    Ref f = builtin(intrinsic);
    std::size_t npos = a.size();
    a.insert(a.end(), kwvalues.begin(), kwvalues.end());
    std::vector<const Str*> names(kwnames);
    return invoke(f.get(), Args{a.data(), npos, names.data(), names.size()});
}

// ---- frames ----
void detail::enter_frame() {
    if (++recursion_depth() > RECURSION_LIMIT) {
        --recursion_depth();
        raise_new("RecursionError", "maximum recursion depth exceeded");
    }
}
void detail::leave_frame() noexcept { --recursion_depth(); }

// ---- the program ----
namespace {
void print_traceback(Obj exc);
}  // namespace

void report_unraisable(const std::string& context, const PyError& e) {
    err_stream().write(context + ":\n");
    print_traceback(e.exc.get());
}

namespace {
void print_traceback(Obj exc) {
    Stream& err = err_stream();
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
    ClassObject* c = type_of(exc);
    std::string name = c->name;
    if (const Obj* mod = c->attrs.find(intern("__module__")))
        if (const Str* ms = as_str(*mod); ms != nullptr && ms->text != "builtins" && ms->text != "__main__")
            name = ms->text + "." + name;
    Ref text = str_of(exc);
    const Str* s = as_str(text.get());
    err.write(s->length == 0 ? name + "\n" : name + ": " + s->text + "\n");
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

// at exit, __main__'s globals are released in insertion order (measured on 3.15.2)
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

int run_main(int argc, char** argv, ModuleBody main_body, std::initializer_list<ModuleBody> prelude) {
    int status = 0;
    try {
        try {
            native_modules()["builtins"] = builtins_module();
            native_modules()["sys"] = make_sys(argc, argv);
            init_types();
            for (ModuleBody body : prelude) {
                // each prelude module runs as `builtins` (its classes say so in __module__); its
                // __all__ goes into builtins, its __intrinsics__ to the runtime only, and its
                // __type_methods__ onto the C++ types (the containers' repr). It is given the
                // runtime's primitives it needs (_dict_next), which no program can name.
                Module* pm = new_module("builtins");
                {
                    Ref walk = own(new Builtin("_dict_next", i_dict_next));
                    put(pm->dict, "_dict_next", walk.get());
                }
                body(pm);
                Obj all = dict_get(pm->dict, Obj::of(intern("__all__")));
                if (!all.is_unset())
                    for (Obj n : static_cast<List*>(all.object())->items) {
                        Obj v = dict_get(pm->dict, n);
                        if (is_kind(v, Kind::Class)) prelude_classes().insert(static_cast<ClassObject*>(v.object()));
                        if (is_kind(v, Kind::PyFunction)) v.object()->cls = types().builtin;   // print is a builtin
                        dict_set(builtins_module()->dict, n, v);
                    }
                Obj intr = dict_get(pm->dict, Obj::of(intern("__intrinsics__")));
                if (!intr.is_unset())
                    for (Obj n : static_cast<List*>(intr.object())->items) dict_set(intrinsics(), n, dict_get(pm->dict, n));
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
            Module* main = new_module("__main__");
            put(main->dict, "__builtins__", Obj::of(builtins_module()));
            main_body(main);
            clear_module(main);
        } catch (const PyError& e) {
            if (type_of(e.exc.get()) == exception_class("SystemExit")) {
                Ref args = getattr(e.exc.get(), intern("args"));
                auto& items = static_cast<Tuple*>(args.get().object())->items;
                Obj code = items.empty() ? None() : items[0];
                if (code == None()) status = 0;
                else if (code.is_small()) status = static_cast<int>(code.small_value());
                else {
                    Ref text = str_of(code);
                    err_stream().write(as_str(text.get())->text + "\n");
                    status = 1;
                }
            } else {
                print_traceback(e.exc.get());
                status = 1;
            }
        }
    } catch (const NotImplemented& e) {
        out_stream().flush();
        err_stream().write(std::string("bella: not implemented: ") + e.what() + "\n");
        err_stream().flush();
        return 70;
    }
    out_stream().flush();
    err_stream().flush();
    return status;
}

}  // namespace bella
