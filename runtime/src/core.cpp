// runtime/src/core.cpp -- the builtin types, their objects' deaths, strings, tuples, lists, the
// dict, hashing, exceptions and frame records (bella/runtime.hpp).
#include "bella/runtime.hpp"

#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <random>

namespace bella {

// ---- the builtin types ----
namespace {
ClassObject* builtin_type(const char* name, std::vector<ClassObject*> bases) {
    ClassObject* c = builtin_class(name);
    c->bases = bases;
    c->mro = {c};
    for (ClassObject* b : bases)
        for (ClassObject* m : b->mro)
            if (std::find(c->mro.begin(), c->mro.end(), m) == c->mro.end()) c->mro.push_back(m);
    c->cls = builtin_class("type");
    return c;
}
}  // namespace

Types& types() {
    static Types t = [] {
        Types x{};
        x.object = builtin_type("object", {});
        x.type = builtin_type("type", {x.object});
        x.int_ = builtin_type("int", {x.object});
        x.bool_ = builtin_type("bool", {x.int_});
        x.float_ = builtin_type("float", {x.object});
        x.str = builtin_type("str", {x.object});
        x.none = builtin_type("NoneType", {x.object});
        x.notimplemented = builtin_type("NotImplementedType", {x.object});
        x.ellipsis = builtin_type("ellipsis", {x.object});
        x.tuple = builtin_type("tuple", {x.object});
        x.list = builtin_type("list", {x.object});
        x.dict = builtin_type("dict", {x.object});
        x.cell = builtin_type("cell", {x.object});
        x.function = builtin_type("function", {x.object});
        x.builtin = builtin_type("builtin_function_or_method", {x.object});
        x.method = builtin_type("method", {x.object});
        x.range = builtin_type("range", {x.object});
        x.range_iterator = builtin_type("range_iterator", {x.object});
        x.tuple_iterator = builtin_type("tuple_iterator", {x.object});
        x.list_iterator = builtin_type("list_iterator", {x.object});
        x.str_iterator = builtin_type("str_ascii_iterator", {x.object});
        x.dict_keyiterator = builtin_type("dict_keyiterator", {x.object});
        x.module = builtin_type("module", {x.object});
        x.traceback = builtin_type("traceback", {x.object});
        x.textio = builtin_type("TextIOWrapper", {x.object});
        x.method_descriptor = builtin_type("method_descriptor", {x.object});
        x.classmethod_descriptor = builtin_type("classmethod_descriptor", {x.object});
        x.getset_descriptor = builtin_type("getset_descriptor", {x.object});
        x.mappingproxy = builtin_type("mappingproxy", {x.object});
        x.slice = builtin_type("slice", {x.object});
        x.iterator = builtin_type("iterator", {x.object});
        x.set = builtin_type("set", {x.object});
        x.frozenset = builtin_type("frozenset", {x.object});
        x.set_iterator = builtin_type("set_iterator", {x.object});
        return x;
    }();
    return t;
}

Singleton* const NONE = new Singleton(types().none, "None");
Singleton* const NOTIMPLEMENTED = new Singleton(types().notimplemented, "NotImplemented");
Singleton* const ELLIPSIS = new Singleton(types().ellipsis, "Ellipsis");
BoolObject* const TRUE = new BoolObject(types().bool_, true);
BoolObject* const FALSE = new BoolObject(types().bool_, false);

ClassObject* type_of(Obj v) {
    if (v.is_small()) return types().int_;
    if (v.is_unset()) throw std::logic_error("type_of: an unset value");
    return v.object()->cls;
}

Tuple::Tuple() : Object(Kind::Tuple) { cls = types().tuple; }
List::List() : Object(Kind::List) { cls = types().list; }
Cell::Cell() : Object(Kind::Cell) { cls = types().cell; }
Builtin::Builtin(std::string n, NativeFn f, Obj s, Binding b) : Object(Kind::Builtin), name(std::move(n)), fn(f), self(s), binding(b) {
    cls = !s.is_unset() || b == Binding::Function ? types().builtin
          : b == Binding::Method                  ? types().method_descriptor
                                                  : types().classmethod_descriptor;
    incref(self);
}
GetSet::GetSet(const char* n, ClassObject* o, Ref (*g)(Obj), void (*s)(Obj, Obj))
    : Object(Kind::GetSet), name(n), owner(o), get(g), set(s) { cls = types().getset_descriptor; flags |= IMMORTAL; }
SliceObject::SliceObject(Obj a, Obj b, Obj c) : Object(Kind::Slice), start(a), stop(b), step(c) {
    cls = types().slice;
    incref(start);
    incref(stop);
    incref(step);
}
Proxy::Proxy(ClassObject* c) : Object(Kind::Proxy), of(c) { cls = types().mappingproxy; }
Method::Method(Obj f, Obj s) : Object(Kind::Method), func(f), self(s) {
    cls = types().method;
    incref(func);
    incref(self);
}
Range::Range(std::int64_t a, std::int64_t b, std::int64_t c) : Object(Kind::Range), start(a), stop(b), step(c) {
    cls = types().range;
    if (c > 0) length = a < b ? (b - a - 1) / c + 1 : 0;
    else length = a > b ? (a - b - 1) / -c + 1 : 0;
}
Iterator::Iterator(Of o, Obj s) : Object(Kind::Iterator), of(o), seq(s) {
    switch (o) {
        case RangeIt: cls = types().range_iterator; break;
        case TupleIt: cls = types().tuple_iterator; break;
        case ListIt: cls = types().list_iterator; break;
        case StrIt: cls = types().str_iterator; break;
        case DictKeysIt: cls = types().dict_keyiterator; break;
        case SeqIt: cls = types().iterator; break;
        case SetIt: cls = types().set_iterator; break;
    }
    incref(seq);
}
PyFunction::PyFunction(const Code* c, Ref (*e)(PyFunction*, Args), Module* m)
    : Object(Kind::PyFunction), code(c), entry(e), module(m) { cls = types().function; }
Dict::Dict() : Object(Kind::PyDict) { cls = types().dict; }
Module::Module(const char* n) : Object(Kind::Module), name(str_new(n)), dict(new Dict) {
    cls = types().module;
    flags |= IMMORTAL;                           // phase 1: modules live as long as the program
    incref(dict);
}
Traceback::Traceback(const Code* c, int l, Ref nx) : Object(Kind::Traceback), code(c), line(l), next(std::move(nx)) {
    cls = types().traceback;
}

// ---- deaths, in CPython's orders (measured on 3.15.2: a tuple or list releases its items last
// to first, a dict its entries in order, each key before its value) ----
namespace {
template <class T>
void destroy(Object* o) { delete static_cast<T*>(o); }

void release_backwards(std::vector<Obj>& items) {
    for (auto it = items.rbegin(); it != items.rend(); ++it) decref(std::exchange(*it, Obj{}));
}

bool register_deaths() {
    destroyer(Kind::Str) = [](Object* o) { delete static_cast<Str*>(o); };
    destroyer(Kind::Tuple) = [](Object* o) { release_backwards(static_cast<Tuple*>(o)->items); destroy<Tuple>(o); };
    destroyer(Kind::List) = [](Object* o) { release_backwards(static_cast<List*>(o)->items); destroy<List>(o); };
    destroyer(Kind::PyDict) = [](Object* o) {
        auto* d = static_cast<Dict*>(o);
        for (auto& e : d->entries) {
            decref(std::exchange(e.key, Obj{}));
            decref(std::exchange(e.value, Obj{}));
        }
        destroy<Dict>(o);
    };
    destroyer(Kind::Cell) = [](Object* o) { decref(std::exchange(static_cast<Cell*>(o)->value, Obj{})); destroy<Cell>(o); };
    destroyer(Kind::PyFunction) = [](Object* o) {
        auto* f = static_cast<PyFunction*>(o);     // func_clear's order
        f->defaults = Ref{};
        f->kwdefaults = Ref{};
        f->doc = Ref{};
        f->dict = Ref{};
        for (Ref& c : f->closure) c = Ref{};
        f->annotate = Ref{};
        f->name = Ref{};
        f->qualname = Ref{};
        destroy<PyFunction>(o);
    };
    destroyer(Kind::Builtin) = [](Object* o) { decref(std::exchange(static_cast<Builtin*>(o)->self, Obj{})); destroy<Builtin>(o); };
    destroyer(Kind::Method) = [](Object* o) {
        auto* m = static_cast<Method*>(o);         // method_dealloc: the function, then self
        decref(std::exchange(m->func, Obj{}));
        decref(std::exchange(m->self, Obj{}));
        destroy<Method>(o);
    };
    destroyer(Kind::Range) = [](Object* o) { destroy<Range>(o); };
    destroyer(Kind::Iterator) = [](Object* o) { decref(std::exchange(static_cast<Iterator*>(o)->seq, Obj{})); destroy<Iterator>(o); };
    destroyer(Kind::Traceback) = [](Object* o) {
        auto* t = static_cast<Traceback*>(o);      // tb_dealloc: the deeper entries, then this frame
        t->next = Ref{};
        for (auto it = t->locals.rbegin(); it != t->locals.rend(); ++it) *it = Ref{};
        destroy<Traceback>(o);
    };
    destroyer(Kind::Native) = [](Object* o) { destroy<Native>(o); };
    destroyer(Kind::Slice) = [](Object* o) {
        auto* s = static_cast<SliceObject*>(o);
        decref(std::exchange(s->start, Obj{}));
        decref(std::exchange(s->stop, Obj{}));
        decref(std::exchange(s->step, Obj{}));
        destroy<SliceObject>(o);
    };
    destroyer(Kind::Proxy) = [](Object* o) { destroy<Proxy>(o); };
    return true;
}
const bool deaths_registered = register_deaths();
}  // namespace

// ---- strings ----
Ref str_new(std::string_view utf8) { return own(new Str(std::string(utf8), false)); }
Ref str_from_codepoints(std::u32string_view cps) { return own(new Str(cps, false)); }
const Str* as_str(Obj v) {
    if (!v.is_object() || v.object()->kind != Kind::Str) return nullptr;
    return static_cast<const Str*>(v.object());
}

// ---- tuples and lists ----
Ref tuple_new(std::initializer_list<Obj> items) {
    auto* t = new Tuple;
    for (Obj v : items) {
        incref(v);
        t->items.push_back(v);
    }
    return own(t);
}
Ref tuple_copy(std::span<const Obj> items) {
    std::vector<Obj> v(items.begin(), items.end());
    for (Obj x : v) incref(x);
    return tuple_steal(std::move(v));
}
Ref tuple_steal(std::vector<Obj> items) {
    auto* t = new Tuple;
    t->items = std::move(items);
    return own(t);
}
Ref list_new(std::initializer_list<Obj> items) {
    auto* l = new List;
    for (Obj v : items) {
        incref(v);
        l->items.push_back(v);
    }
    return own(l);
}

// ---- hashing: CPython's functions (Python/pyhash.c, Objects/longobject.c) ----
namespace {
constexpr std::uint64_t HASH_MODULUS = (std::uint64_t{1} << 61) - 1;

// SipHash-1-3 keyed by the process's secret (spec D-14), as Python/pyhash.c
struct HashSecret {
    std::uint64_t k0 = 0, k1 = 0;
    HashSecret() {
        unsigned char key[24] = {};
        const char* env = std::getenv("PYTHONHASHSEED");
        if (env != nullptr && std::strcmp(env, "random") != 0) {
            unsigned long seed = std::strtoul(env, nullptr, 10);
            if (seed != 0) {                       // lcg_urandom, Python/bootstrap_hash.c
                std::uint32_t x = static_cast<std::uint32_t>(seed);
                for (unsigned char& b : key) {
                    x *= 214013;
                    x += 2531011;
                    b = static_cast<unsigned char>((x >> 16) & 0xff);
                }
            }                                      // 0: randomisation off, the key stays zero
        } else {
            std::random_device rd;
            for (unsigned char& b : key) b = static_cast<unsigned char>(rd());
        }
        std::memcpy(&k0, key, 8);
        std::memcpy(&k1, key + 8, 8);
    }
};
const HashSecret& secret() {
    static HashSecret s;
    return s;
}

inline std::uint64_t rotl(std::uint64_t x, int b) { return (x << b) | (x >> (64 - b)); }
std::uint64_t siphash13(std::uint64_t k0, std::uint64_t k1, const unsigned char* src, std::size_t len) {
    std::uint64_t b = static_cast<std::uint64_t>(len) << 56;
    std::uint64_t v0 = k0 ^ 0x736f6d6570736575ULL, v1 = k1 ^ 0x646f72616e646f6dULL;
    std::uint64_t v2 = k0 ^ 0x6c7967656e657261ULL, v3 = k1 ^ 0x7465646279746573ULL;
    auto round = [&] {
        v0 += v1; v1 = rotl(v1, 13); v1 ^= v0; v0 = rotl(v0, 32);
        v2 += v3; v3 = rotl(v3, 16); v3 ^= v2;
        v0 += v3; v3 = rotl(v3, 21); v3 ^= v0;
        v2 += v1; v1 = rotl(v1, 17); v1 ^= v2; v2 = rotl(v2, 32);
    };
    while (len >= 8) {
        std::uint64_t m;
        std::memcpy(&m, src, 8);
        v3 ^= m;
        round();
        v0 ^= m;
        src += 8;
        len -= 8;
    }
    std::uint64_t t = 0;
    for (std::size_t i = 0; i < len; ++i) t |= static_cast<std::uint64_t>(src[i]) << (8 * i);
    b |= t;
    v3 ^= b;
    round();
    v0 ^= b;
    v2 ^= 0xff;
    round(); round(); round();
    return (v0 ^ v1) ^ (v2 ^ v3);
}

std::int64_t hash_small(std::int64_t v) {
    // long_hash: the value modulo 2**61 - 1, with the sign; -1 is reserved for errors
    std::uint64_t a = v < 0 ? static_cast<std::uint64_t>(-(v + 1)) + 1 : static_cast<std::uint64_t>(v);
    auto h = static_cast<std::int64_t>(a % HASH_MODULUS);
    if (v < 0) h = -h;
    return h == -1 ? -2 : h;
}
}  // namespace

std::int64_t hash_of(Obj v) {
    if (v.is_small()) return hash_small(v.small_value());
    Object* o = v.object();
    switch (o->kind) {
        case Kind::Bool: return static_cast<BoolObject*>(o)->value ? 1 : 0;
        case Kind::Str: {
            auto* s = static_cast<Str*>(o);
            if (s->hash == -1) {
                if (s->length == 0) s->hash = 0;
                else {
                    auto h = static_cast<std::int64_t>(siphash13(secret().k0, secret().k1,
                        reinterpret_cast<const unsigned char*>(s->units.data()), s->units.size()));
                    s->hash = h == -1 ? -2 : h;
                }
            }
            return s->hash;
        }
        case Kind::Singleton:
        case Kind::PyFunction:
        case Kind::Builtin:
        case Kind::Class: {
            // object.__hash__: the address rotated by 4 bits (_Py_HashPointer)
            auto p = reinterpret_cast<std::uintptr_t>(o);
            auto h = static_cast<std::int64_t>((p >> 4) | (p << 60));
            return h == -1 ? -2 : h;
        }
        case Kind::Tuple: {
            // tuplehash: xxHash's mixing, as Objects/tupleobject.c
            const auto& items = static_cast<Tuple*>(o)->items;
            constexpr std::uint64_t P1 = 11400714785074694791ULL, P2 = 14029467366897019727ULL,
                                    P5 = 2870177450012600261ULL;
            std::uint64_t acc = P5;
            for (Obj item : items) {
                auto lane = static_cast<std::uint64_t>(hash_of(item));
                acc += lane * P2;
                acc = rotl(acc, 31);
                acc *= P1;
            }
            acc += items.size() ^ (P5 ^ 3527539UL);
            if (acc == static_cast<std::uint64_t>(-1)) return 1546275796;
            return static_cast<std::int64_t>(acc);
        }
        default:
            break;
    }
    // a class's __hash__ (None when it defines __eq__ alone); a C++ type without one is unhashable
    Obj h = type_lookup(type_of(v), intern("__hash__"));
    if (!h.is_unset() && h != None()) {
        Ref r = call_special(v, "__hash__", {});
        if (r.get().is_small()) {
            std::int64_t x = r.get().small_value();
            return x == -1 ? -2 : x;
        }
        if (is_kind(r.get(), Kind::Bool)) return static_cast<BoolObject*>(r.get().object())->value ? 1 : 0;
        raise_new("TypeError", "__hash__ method should return an integer");
    }
    raise_new("TypeError", "unhashable type: '" + type_of(v)->name + "'");
}

// ---- the dict: CPython's compact dict (Objects/dictobject.c): an index table probed with the
// perturbation scheme, entries in insertion order, resized to the smallest power of two above
// three times the entries in use. Keys compare by identity, then by hash and ==. ----
namespace {
constexpr std::int64_t DKIX_EMPTY = -1, DKIX_DUMMY = -2;
constexpr int PERTURB_SHIFT = 5;

bool keys_equal(Obj a, Obj b) {
    if (a == b) return true;
    const Str* sa = as_str(a);
    const Str* sb = as_str(b);
    if (sa != nullptr && sb != nullptr) return sa->text == sb->text;
    Ref r = compare(CmpOp::Eq, a, b);
    return truth(r.get());
}

// the index slot where `key` is, or where it would go; the entry index (or DKIX_EMPTY)
std::pair<std::size_t, std::int64_t> probe(Dict* d, Obj key, std::int64_t hash) {
    std::size_t mask = d->indices.size() - 1;
    auto perturb = static_cast<std::uint64_t>(hash);
    std::size_t i = static_cast<std::size_t>(hash) & mask;
    std::optional<std::size_t> free_slot;
    for (;;) {
        std::int64_t ix = d->indices[i];
        if (ix == DKIX_EMPTY) return {free_slot.value_or(i), DKIX_EMPTY};
        if (ix == DKIX_DUMMY) {
            if (!free_slot) free_slot = i;
        } else {
            auto& e = d->entries[static_cast<std::size_t>(ix)];
            if (e.key == key) return {i, ix};
            if (e.hash == hash) {
                std::uint64_t version = d->version;
                Obj k = e.key;
                incref(k);
                bool eq = keys_equal(k, key);
                decref(k);
                if (d->version != version) raise_new("RuntimeError", "dictionary changed size during iteration");
                if (eq) return {i, ix};
            }
        }
        perturb >>= PERTURB_SHIFT;
        i = (i * 5 + static_cast<std::size_t>(perturb) + 1) & mask;
    }
}

void resize(Dict* d, std::size_t minsize) {
    std::size_t size = 8;
    while (size <= minsize) size <<= 1;
    std::vector<Dict::Entry> live;
    for (auto& e : d->entries) if (!e.key.is_unset()) live.push_back(e);
    d->entries = std::move(live);
    d->indices.assign(size, DKIX_EMPTY);
    std::size_t mask = size - 1;
    for (std::size_t ix = 0; ix < d->entries.size(); ++ix) {
        auto perturb = static_cast<std::uint64_t>(d->entries[ix].hash);
        std::size_t i = static_cast<std::size_t>(d->entries[ix].hash) & mask;
        while (d->indices[i] != DKIX_EMPTY) {
            perturb >>= PERTURB_SHIFT;
            i = (i * 5 + static_cast<std::size_t>(perturb) + 1) & mask;
        }
        d->indices[i] = static_cast<std::int64_t>(ix);
    }
}
std::size_t usable(const Dict* d) { return d->indices.size() * 2 / 3; }
}  // namespace

Ref dict_new() { return own(new Dict); }

Obj dict_get(Dict* d, Obj key) {
    if (d->indices.empty()) return Obj{};
    auto [slot, ix] = probe(d, key, hash_of(key));
    return ix >= 0 ? d->entries[static_cast<std::size_t>(ix)].value : Obj{};
}

void dict_set(Dict* d, Obj key, Obj value) {
    std::int64_t hash = hash_of(key);
    if (d->indices.empty()) resize(d, 0);
    auto [slot, ix] = probe(d, key, hash);
    incref(value);
    if (ix >= 0) {
        Obj old = std::exchange(d->entries[static_cast<std::size_t>(ix)].value, value);
        ++d->version;
        decref(old);                               // after the new value is in place
        return;
    }
    if (d->entries.size() >= usable(d)) {
        resize(d, d->used * 3);
        slot = probe(d, key, hash).first;
    }
    incref(key);
    d->indices[slot] = static_cast<std::int64_t>(d->entries.size());
    d->entries.push_back({hash, key, value});
    ++d->used;
    ++d->version;
}

bool dict_del(Dict* d, Obj key) {
    if (d->indices.empty()) return false;
    auto [slot, ix] = probe(d, key, hash_of(key));
    if (ix < 0) return false;
    auto& e = d->entries[static_cast<std::size_t>(ix)];
    d->indices[slot] = DKIX_DUMMY;
    Obj k = std::exchange(e.key, Obj{});
    Obj v = std::exchange(e.value, Obj{});
    --d->used;
    ++d->version;
    decref(k);
    decref(v);
    return true;
}

// ---- exceptions ----
namespace {
struct ExceptionClasses {
    std::unordered_map<std::string, ClassObject*> by_name;
    ClassObject* make(const char* name, const char* base) {
        std::vector<ClassObject*> bases;
        if (base != nullptr) bases.push_back(by_name.at(base));
        ClassObject* c = make_class({.name = name, .bases = bases});
        if (base == nullptr) {                     // BaseException derives from object
            c->bases = {types().object};
            c->mro = {c, types().object};
        } else {
            c->mro = {c};
            for (ClassObject* m : bases[0]->mro) c->mro.push_back(m);
        }
        c->has_dict = true;
        c->set_attr(intern("__module__"), Obj::of(intern("builtins")));
        by_name[name] = c;
        return c;
    }
    ExceptionClasses() {
        // phase 1, step 3a: in C++ until classes compile (step 3a.2 moves them to the prelude)
        make("BaseException", nullptr);
        for (const char* n : {"Exception", "SystemExit", "KeyboardInterrupt", "GeneratorExit"}) make(n, "BaseException");
        for (auto [n, b] : std::initializer_list<std::pair<const char*, const char*>>{
                 {"ArithmeticError", "Exception"}, {"ZeroDivisionError", "ArithmeticError"},
                 {"OverflowError", "ArithmeticError"}, {"AssertionError", "Exception"},
                 {"AttributeError", "Exception"}, {"LookupError", "Exception"}, {"IndexError", "LookupError"},
                 {"KeyError", "LookupError"}, {"NameError", "Exception"}, {"UnboundLocalError", "NameError"},
                 {"RuntimeError", "Exception"}, {"NotImplementedError", "RuntimeError"},
                 {"RecursionError", "RuntimeError"}, {"StopIteration", "Exception"}, {"TypeError", "Exception"},
                 {"ValueError", "Exception"}, {"ImportError", "Exception"}, {"ModuleNotFoundError", "ImportError"},
                 {"UnicodeError", "ValueError"}})
            make(n, b);
    }
};
ExceptionClasses& exceptions() {
    static ExceptionClasses e;
    return e;
}

Ref new_exception(ClassObject* c, Ref args) {
    auto* e = new_instance(c);
    Ref r = own(e);
    setattr(e, intern("args"), args.get());
    return r;
}
}  // namespace

ClassObject* exception_class(const char* name) { return exceptions().by_name.at(name); }

namespace {
std::vector<Obj>& handled() {                    // the exceptions being handled, innermost last
    static std::vector<Obj> stack;
    return stack;
}
}  // namespace

Handling::Handling(const Ref& exc) {
    incref(exc.get());
    handled().push_back(exc.get());
}
Handling::~Handling() {
    Obj e = handled().back();
    handled().pop_back();
    decref(e);
}

void raise(Obj exc) {
    // a new exception raised while another is handled records it as its context (PEP 3134)
    if (!handled().empty() && handled().back() != exc && is_kind(exc, Kind::Instance)) {
        auto* inst = static_cast<Instance*>(exc.object());
        auto [present, ctx] = detail::instance_storage(inst, intern("__context__"));
        if (!present || ctx == None()) setattr(inst, intern("__context__"), handled().back());
    }
    detail::raising() = exc;
    throw PyError{Ref::share(exc)};
}

void reraise() {
    if (handled().empty()) raise_new("RuntimeError", "No active exception to reraise");
    Obj exc = handled().back();
    detail::raising() = exc;
    throw PyError{Ref::share(exc)};
}

Obj unsupported_constant(const char* what) { throw NotImplemented(what); }
Obj str_constant_cps(std::initializer_list<char32_t> cps) {
    return Obj::of(new Str(std::u32string_view(cps.begin(), cps.size()), true));
}

void raise_new(const char* type, const std::string& message) {
    Ref msg = str_new(message);
    Ref exc = new_exception(exception_class(type), tuple_new({msg.get()}));
    raise(exc.get());
}

bool is_subclass(ClassObject* c, ClassObject* base) {
    return std::find(c->mro.begin(), c->mro.end(), base) != c->mro.end();
}

void raise_type(Obj value, Obj cause, bool has_cause) {
    ClassObject* base = exception_class("BaseException");
    Ref exc;
    if (is_kind(value, Kind::Class) && is_subclass(static_cast<ClassObject*>(value.object()), base)) {
        exc = invoke(value, {});
    } else if (is_kind(value, Kind::Instance) && is_subclass(value.object()->cls, base)) {
        exc = Ref::share(value);
    } else {
        raise_new("TypeError", "exceptions must derive from BaseException");
    }
    if (has_cause) {
        Obj c = cause;
        Ref made;
        if (is_kind(c, Kind::Class)) {
            made = invoke(c, {});
            c = made.get();
        }
        setattr(static_cast<Instance*>(exc.get().object()), intern("__cause__"), c);
        setattr(static_cast<Instance*>(exc.get().object()), intern("__suppress_context__"), boolean(true));
    }
    raise(exc.get());
}

bool exception_matches(Obj exc, Obj spec) {
    ClassObject* c = type_of(exc);
    if (is_kind(spec, Kind::Tuple)) {
        for (Obj s : static_cast<Tuple*>(spec.object())->items)
            if (exception_matches(exc, s)) return true;
        return false;
    }
    if (!is_kind(spec, Kind::Class) || !is_subclass(static_cast<ClassObject*>(spec.object()), exception_class("BaseException")))
        raise_new("TypeError", "catching classes that do not inherit from BaseException is not allowed");
    return is_subclass(c, static_cast<ClassObject*>(spec.object()));
}

Obj traceback_of(Obj exc) {
    if (!is_kind(exc, Kind::Instance)) return Obj{};
    auto [present, v] = detail::instance_storage(static_cast<Instance*>(exc.object()), intern("__traceback__"));
    return present ? v : Obj{};
}

void detail::record_frame(const Code& code, int line, Ref* const* locals, std::size_t n) noexcept {
    try {
        Obj exc = raising();
        if (!is_kind(exc, Kind::Instance)) return;
        Obj prev = traceback_of(exc);
        auto* tb = new Traceback(&code, line, Ref::share(prev.is_unset() ? None() : prev));
        for (std::size_t i = 0; i < n; ++i) tb->locals.push_back(std::move(*locals[i]));
        Ref held = own(tb);
        setattr(static_cast<Instance*>(exc.object()), intern("__traceback__"), held.get());
    } catch (...) {
        // a frame record that cannot be made loses the entry, never the exception
    }
}

}  // namespace bella
