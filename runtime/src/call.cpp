// runtime/src/call.cpp -- the call protocol and argument binding, function objects, names and
// modules, the C++ builtins, sys and its streams, the intrinsics, and the program's start and end
// (bella/runtime.hpp).
#include "bella/runtime.hpp"

#include <algorithm>
#include <cstdio>
#include <unistd.h>
#include <unordered_map>

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
            for (ClassObject* k : c->mro) {
                auto it = constructors().find(k);
                if (it != constructors().end()) return it->second(Obj::of(c), a);
            }
            throw NotImplemented("calling the class '" + c->name + "' (step 3a.2: classes)");
        }
        case Kind::Function: {
            if (a.nkw != 0) throw NotImplemented("keywords to a native test function");
            std::vector<Obj> data(a.data, a.data + a.npos);
            return Ref::steal(static_cast<Function*>(o)->fn(data));
        }
        case Kind::Instance:
            throw NotImplemented("calling instances of user classes (step 3a.2)");
        default:
            break;
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
        if (!is_kind(kwargs, Kind::PyDict)) throw NotImplemented("CALL_FUNCTION_EX with keywords that are not a dict");
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
    f->doc = none_ref();
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

Ref load_global(Module* m, const Str* name) {
    Obj v = dict_get(m->dict, Obj::of(name));
    if (v.is_unset()) v = dict_get(builtins_module()->dict, Obj::of(name));
    if (v.is_unset()) raise_new("NameError", "name '" + name->text + "' is not defined");
    return Ref::share(v);
}
Ref load_name(Obj ns, Module* m, const Str* name) {
    if (!is_kind(ns, Kind::PyDict)) throw NotImplemented("a class namespace that is not a dict (__prepare__)");
    Obj v = dict_get(static_cast<Dict*>(ns.object()), Obj::of(name));
    if (!v.is_unset()) return Ref::share(v);
    return load_global(m, name);
}
void store_name(Obj ns, const Str* name, Ref value) {
    if (!is_kind(ns, Kind::PyDict)) throw NotImplemented("a class namespace that is not a dict (__prepare__)");
    dict_set(static_cast<Dict*>(ns.object()), Obj::of(name), value.get());
}
void store_global(Module* m, const Str* name, Ref value) { dict_set(m->dict, Obj::of(name), value.get()); }
void delete_name(Obj ns, const Str* name) {
    if (!dict_del(static_cast<Dict*>(ns.object()), Obj::of(name)))
        raise_new("NameError", "name '" + name->text + "' is not defined");
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
    positional_only(a, "write", 1, 1);
    const Str* s = as_str(a.pos(0));
    if (s == nullptr) raise_new("TypeError", "write() argument must be str, not " + type_of(a.pos(0))->name);
    stream_of(self).write(s->text);
    return Ref::steal(Obj::small(static_cast<std::int64_t>(s->length)));
}
Ref textio_flush(Obj self, Args a) {
    positional_only(a, "flush", 0, 0);
    stream_of(self).flush();
    return none_ref();
}

// ---- the C++ builtins ----
Ref b_len(Obj, Args a) {
    positional_only(a, "len", 1, 1);
    Obj v = a.pos(0);
    if (const Str* s = as_str(v)) return Ref::steal(Obj::small(static_cast<std::int64_t>(s->length)));
    if (is_kind(v, Kind::Tuple)) return Ref::steal(Obj::small(static_cast<std::int64_t>(static_cast<Tuple*>(v.object())->items.size())));
    if (is_kind(v, Kind::List)) return Ref::steal(Obj::small(static_cast<std::int64_t>(static_cast<List*>(v.object())->items.size())));
    if (is_kind(v, Kind::PyDict)) return Ref::steal(Obj::small(static_cast<std::int64_t>(static_cast<Dict*>(v.object())->used)));
    if (is_kind(v, Kind::Range)) return Ref::steal(Obj::small(static_cast<Range*>(v.object())->length));
    if (is_kind(v, Kind::Instance)) throw NotImplemented("len() of instances of user classes (step 3a.2)");
    raise_new("TypeError", "object of type '" + type_of(v)->name + "' has no len()");
}
Ref b_repr(Obj, Args a) {
    positional_only(a, "repr", 1, 1);
    return repr_of(a.pos(0));
}
Ref b_format(Obj, Args a) {
    positional_only(a, "format", 1, 2);
    Obj spec = a.npos > 1 ? a.pos(1) : Obj{};
    const Str* s = spec.is_unset() ? nullptr : as_str(spec);
    if (!spec.is_unset() && s == nullptr)
        raise_new("TypeError", "format() argument 2 must be str, not " + type_of(spec)->name);
    if (s != nullptr && s->length != 0) throw NotImplemented("format() with a format specification");
    return str_of(a.pos(0));
}
Ref b_isinstance(Obj, Args a) {
    positional_only(a, "isinstance", 2, 2);
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
Ref b_iter(Obj, Args a) {
    positional_only(a, "iter", 1, 1);
    return iter(a.pos(0));
}
Ref b_next(Obj, Args a) {
    positional_only(a, "next", 1, 2);
    if (!is_kind(a.pos(0), Kind::Iterator))
        raise_new("TypeError", "'" + type_of(a.pos(0))->name + "' object is not an iterator");
    Ref v = for_next(a.pos(0));
    if (!is_end(v)) return v;
    if (a.npos > 1) return Ref::share(a.pos(1));
    Ref exc = invoke(Obj::of(exception_class("StopIteration")), {});
    raise(exc.get());
}
Ref b_hash(Obj, Args a) {
    positional_only(a, "hash", 1, 1);
    return Ref::steal(Obj::small(hash_of(a.pos(0))));
}
Ref b_abs(Obj, Args a) {
    positional_only(a, "abs", 1, 1);
    Ref neg = compare(CmpOp::Lt, a.pos(0), Obj::small(0));
    return truth(neg.get()) ? unary_neg(a.pos(0)) : unary_pos(a.pos(0));
}
Ref b_callable(Obj, Args a) {
    positional_only(a, "callable", 1, 1);
    Kind k = a.pos(0).is_object() ? a.pos(0).object()->kind : Kind::Bool;
    bool yes = k == Kind::PyFunction || k == Kind::Builtin || k == Kind::Method || k == Kind::Class || k == Kind::Function;
    if (k == Kind::Instance) yes = a.pos(0).object()->cls->has("__call__");
    return Ref::steal(boolean(yes));
}
Ref b_ord(Obj, Args a) {
    positional_only(a, "ord", 1, 1);
    const Str* s = as_str(a.pos(0));
    if (s == nullptr) raise_new("TypeError", "ord() expected string of length 1, but " + type_of(a.pos(0))->name + " found");
    if (s->length != 1)
        raise_new("TypeError", "ord() expected a character, but string of length " + std::to_string(s->length) + " found");
    return Ref::steal(Obj::small(static_cast<std::int64_t>(s->at(0))));
}
Ref b_chr(Obj, Args a) {
    positional_only(a, "chr", 1, 1);
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
Ref c_type(Obj, Args a) {
    if (a.npos == 1 && a.nkw == 0) return Ref::share(Obj::of(type_of(a.pos(0))));
    throw NotImplemented("type(name, bases, dict) (step 3a.2)");
}
Ref c_bool(Obj, Args a) {
    positional_only(a, "bool", 0, 1);
    return Ref::steal(boolean(a.npos == 1 && truth(a.pos(0))));
}
Ref c_range(Obj, Args a) {
    positional_only(a, "range", 1, 3);
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
    positional_only(a, "tuple", 0, 1);
    if (a.npos == 0) return tuple_new({});
    if (is_kind(a.pos(0), Kind::Tuple)) return Ref::share(a.pos(0));
    Ref l = list_new({});
    list_extend(l.get(), a.pos(0));
    return list_to_tuple(l.get());
}
Ref c_list(Obj, Args a) {
    positional_only(a, "list", 0, 1);
    Ref l = list_new({});
    if (a.npos == 1) list_extend(l.get(), a.pos(0));
    return l;
}
Ref c_exception(Obj cls, Args a) {
    if (a.nkw != 0) raise_new("TypeError", static_cast<ClassObject*>(cls.object())->name + "() takes no keyword arguments");
    std::vector<Obj> items;
    for (std::size_t i = 0; i < a.npos; ++i) {
        incref(a.pos(i));
        items.push_back(a.pos(i));
    }
    auto* e = new_instance(static_cast<ClassObject*>(cls.object()));
    Ref r = own(e);
    Ref args = tuple_steal(std::move(items));
    setattr(e, intern("args"), args.get());
    return r;
}

Ref str_join(Obj self, Args a) {
    positional_only(a, "join", 1, 1);
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
    auto* b = new Builtin(name, fn);
    incref(b);
    c->attrs.set(intern(name), Obj::of(b));
}

Module* make_builtins() {
    auto* m = new Module("builtins");
    Dict* d = m->dict;
    Types& t = types();
    for (auto [name, cls, ctor] : std::initializer_list<std::tuple<const char*, ClassObject*, NativeFn>>{
             {"str", t.str, c_str}, {"type", t.type, c_type}, {"bool", t.bool_, c_bool}, {"range", t.range, c_range},
             {"tuple", t.tuple, c_tuple}, {"list", t.list, c_list}, {"int", t.int_, nullptr},
             {"object", t.object, nullptr}, {"dict", t.dict, nullptr}, {"float", t.float_, nullptr}}) {
        put(d, name, Obj::of(cls));
        if (ctor != nullptr) constructors()[cls] = ctor;
    }
    ClassObject* base = exception_class("BaseException");
    constructors()[base] = c_exception;
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
    method(t.str, "join", str_join);
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
    put(d, "maxsize", Obj::small((std::int64_t{1} << 62) - 1));
    return m;
}

std::unordered_map<std::string, Module*>& native_modules() {
    static std::unordered_map<std::string, Module*> table;
    return table;
}
}  // namespace

Module* builtins_module() {
    static Module* m = make_builtins();
    return m;
}
Module* new_module(const char* name) {
    auto* m = new Module(name);
    put(m->dict, "__name__", m->name.get());
    return m;
}

Ref builtin(const char* name) {
    Obj v = dict_get(builtins_module()->dict, Obj::of(intern(name)));
    if (v.is_unset()) throw NotImplemented(std::string("the intrinsic '") + name + "'");
    return Ref::share(v);
}

// ---- the intrinsics L2 calls by name (Runtime ops) ----
Ref runtime_call(const char* intrinsic, Obj ns, Module* m, std::initializer_list<Obj> args) {
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
    return invoke(f.get(), Args{a.data(), a.size(), nullptr, 0});
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
            for (ModuleBody body : prelude) {
                Module* pm = new_module("bella.prelude");
                body(pm);
                Obj all = dict_get(pm->dict, Obj::of(intern("__all__")));
                if (!all.is_unset())
                    for (Obj n : static_cast<List*>(all.object())->items)
                        dict_set(builtins_module()->dict, n, dict_get(pm->dict, n));
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
