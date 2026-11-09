// runtime/src/core.cpp -- the builtin types, their objects' deaths, strings, tuples, lists, the
// dict, hashing, exceptions and frame records (bella/runtime.hpp).
#include "bella/runtime.hpp"

#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <random>

namespace bella {

// ---- the builtin types ----
std::vector<ClassObject*>& builtin_types() {
    static std::vector<ClassObject*> all;
    return all;
}
ClassObject* builtin_type(const char* name, std::vector<ClassObject*> bases) {
    ClassObject* c = builtin_class(name);
    builtin_types().push_back(c);
    c->final_type = cpython_has("final", name);
    c->has_weakref = cpython_has("weakref", name);
    c->bases = bases;
    c->mro = {c};
    for (ClassObject* b : bases)
        for (ClassObject* m : b->mro)
            if (std::find(c->mro.begin(), c->mro.end(), m) == c->mro.end()) c->mro.push_back(m);
    c->cls = builtin_class("type");
    return c;
}

Types& types() {
    static Types t = [] {
        Types x{};
        x.object = builtin_type("object", {});
        x.type = builtin_type("type", {x.object});
        x.int_ = builtin_type("int", {x.object});
        x.bool_ = builtin_type("bool", {x.int_});
        x.float_ = builtin_type("float", {x.object});
        x.complex_ = builtin_type("complex", {x.object});
        x.generator = builtin_type("generator", {x.object});
        x.str = builtin_type("str", {x.object});
        x.none = builtin_type("NoneType", {x.object});
        x.notimplemented = builtin_type("NotImplementedType", {x.object});
        x.ellipsis = builtin_type("ellipsis", {x.object});
        x.tuple = builtin_type("tuple", {x.object});
        x.list = builtin_type("list", {x.object});
        x.dict = builtin_type("dict", {x.object});
        x.frozendict = builtin_type("frozendict", {x.object});
        x.cell = builtin_type("cell", {x.object});
        x.function = builtin_type("function", {x.object});
        x.builtin = builtin_type("builtin_function_or_method", {x.object});
        x.method = builtin_type("method", {x.object});
        x.range = builtin_type("range", {x.object});
        x.range_iterator = builtin_type("range_iterator", {x.object});
        x.longrange_iterator = builtin_type("longrange_iterator", {x.object});
        x.tuple_iterator = builtin_type("tuple_iterator", {x.object});
        x.list_iterator = builtin_type("list_iterator", {x.object});
        x.list_reverseiterator = builtin_type("list_reverseiterator", {x.object});
        x.str_iterator = builtin_type("str_ascii_iterator", {x.object});
        x.dict_keyiterator = builtin_type("dict_keyiterator", {x.object});
        x.module = builtin_type("module", {x.object});
        x.traceback = builtin_type("traceback", {x.object});
        x.code = builtin_type("code", {x.object});
        x.method_descriptor = builtin_type("method_descriptor", {x.object});
        x.classmethod_descriptor = builtin_type("classmethod_descriptor", {x.object});
        x.wrapper_descriptor = builtin_type("wrapper_descriptor", {x.object});
        x.method_wrapper = builtin_type("method-wrapper", {x.object});
        x.builtin_method = builtin_type("builtin_method", {x.builtin});
        x.getset_descriptor = builtin_type("getset_descriptor", {x.object});
        // a __slots__ member's type (object.hpp's SlotDescriptor): made a type here, or type(d) has
        // no class of its own (found while verifying RL-228's round)
        x.member_descriptor = builtin_type("member_descriptor", {x.object});
        x.super_ = builtin_type("super", {x.object});
        x.lazy_import = builtin_type("lazy_import", {x.object});
        x.mappingproxy = builtin_type("mappingproxy", {x.object});
        x.slice = builtin_type("slice", {x.object});
        x.bytes = builtin_type("bytes", {x.object});
        x.bytearray = builtin_type("bytearray", {x.object});
        x.bytes_iterator = builtin_type("bytes_iterator", {x.object});
        x.bytearray_iterator = builtin_type("bytearray_iterator", {x.object});
        x.memoryview = builtin_type("memoryview", {x.object});
        x.iterator = builtin_type("iterator", {x.object});
        x.set = builtin_type("set", {x.object});
        x.frozenset = builtin_type("frozenset", {x.object});
        x.set_iterator = builtin_type("set_iterator", {x.object});
        x.dict_reversekeyiterator = builtin_type("dict_reversekeyiterator", {x.object});
        x.dict_reversevalueiterator = builtin_type("dict_reversevalueiterator", {x.object});
        x.dict_reverseitemiterator = builtin_type("dict_reverseitemiterator", {x.object});
        x.dict_keys = builtin_type("dict_keys", {x.object});
        x.dict_values = builtin_type("dict_values", {x.object});
        x.dict_items = builtin_type("dict_items", {x.object});
        x.dict_valueiterator = builtin_type("dict_valueiterator", {x.object});
        x.dict_itemiterator = builtin_type("dict_itemiterator", {x.object});
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
Proxy::Proxy(Obj given) : Object(Kind::Proxy), of(nullptr), mapping(Ref::share(given)) { cls = types().mappingproxy; }
Method::Method(Obj f, Obj s) : Object(Kind::Method), func(f), self(s) {
    cls = types().method;
    incref(func);
    incref(self);
}
Range::Range(std::int64_t a, std::int64_t b, std::int64_t c) : Object(Kind::Range), start(a), stop(b), step(c) {
    cls = types().range;
    using Wide = __int128;                       // two 64-bit bounds can be 2**64 apart
    Wide n = 0;
    if (c > 0 && a < b) n = (Wide{b} - a - 1) / c + 1;
    else if (c < 0 && a > b) n = (Wide{a} - b - 1) / -Wide{c} + 1;
    length = static_cast<std::int64_t>(n);       // range_from_ints makes sure that it fits
}
Iterator::Iterator(Of o, Obj s) : Object(Kind::Iterator), of(o), seq(s) {
    switch (o) {
        case RangeIt: cls = types().range_iterator; break;
        case LongRangeIt: cls = types().longrange_iterator; break;
        case TupleIt: cls = types().tuple_iterator; break;
        case ListIt: cls = types().list_iterator; break;
        case ListRevIt: cls = types().list_reverseiterator; break;
        case StrIt: cls = types().str_iterator; break;
        case BytesIt: cls = is_kind(s, Kind::ByteArray) ? types().bytearray_iterator : types().bytes_iterator; break;
        case DictRevKeysIt: cls = types().dict_reversekeyiterator; break;
        case DictRevValuesIt: cls = types().dict_reversevalueiterator; break;
        case DictRevItemsIt: cls = types().dict_reverseitemiterator; break;
        case DictKeysIt: cls = types().dict_keyiterator; break;
        case DictValuesIt: cls = types().dict_valueiterator; break;
        case DictItemsIt: cls = types().dict_itemiterator; break;
        case SeqIt: cls = types().iterator; break;
        case SetIt: cls = types().set_iterator; break;
    }
    incref(seq);
}
DictView::DictView(Obj d, Which w) : Object(Kind::DictView), which(w), dict(d) {
    cls = w == Keys ? types().dict_keys : w == Values ? types().dict_values : types().dict_items;
    incref(dict);
}
PyFunction::PyFunction(const Code* c, Ref (*e)(PyFunction*, Args), Module* m)
    : Object(Kind::PyFunction), code(c), entry(e), module(m) {
    cls = types().function;
    incref(static_cast<Object*>(m));
    // func_new_impl: __module__ is the globals' __name__ as it stands now; a module that renames itself afterwards
    // (importlib renames _frozen_importlib) leaves its functions' __module__ as it was (review G15 range: importlib)
    if (Obj n = dict_get(m->dict, Obj::of(intern("__name__"))); !n.is_unset()) module_name = Ref::share(n);
}
Module::Module(const char* n) : Object(Kind::Module), name(str_new(n)), dict(new Dict) {
    cls = types().module;
    flags |= IMMORTAL;                           // phase 1: modules live as long as the program
    incref(dict);
    all_modules().push_back(this);
}
Module::Module(Dict* globals, Dict* given_builtins) : Object(Kind::Module), name(str_new("<string>")), dict(globals) {
    cls = types().module;
    incref(dict);
    if (given_builtins != builtins_module()->dict) {
        builtins = given_builtins;
        incref(builtins);
    }
}
void forget_module(const Module* m) { std::erase(all_modules(), m); }
std::vector<Module*>& all_modules() {
    static std::vector<Module*> made;
    return made;
}
LazyImport::LazyImport() : Object(Kind::LazyImport) { cls = types().lazy_import; }
CodeObject::CodeObject(const Code* c) : Object(Kind::CodeKind), code(c) { cls = types().code; }
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
    destroyer(Kind::Cell) = [](Object* o) { decref(std::exchange(static_cast<Cell*>(o)->value, Obj{})); destroy<Cell>(o); };
    destroyer(Kind::Module) = [](Object* o) {     // a staged text's: the program's modules are immortal
        auto* m = static_cast<Module*>(o);
        Dict* d = std::exchange(m->dict, nullptr);
        Dict* b = std::exchange(m->builtins, nullptr);
        Dict* l = std::exchange(m->locals, nullptr);
        decref(d);
        if (b != nullptr) decref(b);
        if (l != nullptr) decref(l);
        m->name = Ref{};
        destroy<Module>(o);
    };
    destroyer(Kind::PyFunction) = [](Object* o) {
        auto* f = static_cast<PyFunction*>(o);     // func_clear's order: its globals first
        decref(static_cast<Object*>(f->module));
        f->closure_tuple = Ref{};
        f->defaults = Ref{};
        f->kwdefaults = Ref{};
        f->doc = Ref{};
        f->dict = Ref{};
        for (Ref& c : f->closure) c = Ref{};
        f->annotate = Ref{};
        f->annotations = Ref{};
        f->type_params = Ref{};
        f->name = Ref{};
        f->qualname = Ref{};
        destroy<PyFunction>(o);
    };
    destroyer(Kind::Super) = [](Object* o) {
        auto* su = static_cast<SuperObject*>(o);   // super_dealloc: obj, type, obj_type
        decref(std::exchange(su->obj, Obj{}));
        decref(std::exchange(su->type, Obj{}));
        decref(std::exchange(su->obj_type, Obj{}));
        destroy<SuperObject>(o);
    };
    destroyer(Kind::LazyImport) = [](Object* o) { destroy<LazyImport>(o); };   // lazy_import_clear: its Refs
    destroyer(Kind::Builtin) = [](Object* o) { decref(std::exchange(static_cast<Builtin*>(o)->self, Obj{})); destroy<Builtin>(o); };
    destroyer(Kind::Method) = [](Object* o) {
        auto* m = static_cast<Method*>(o);         // method_dealloc: the function, then self
        decref(std::exchange(m->func, Obj{}));
        decref(std::exchange(m->self, Obj{}));
        destroy<Method>(o);
    };
    destroyer(Kind::Range) = [](Object* o) { destroy<Range>(o); };
    destroyer(Kind::BigInt) = [](Object* o) { destroy<BigInt>(o); };
    destroyer(Kind::Float) = [](Object* o) { destroy<Float>(o); };
    destroyer(Kind::Complex) = [](Object* o) { destroy<Complex>(o); };
    destroyer(Kind::Generator) = [](Object* o) { gen_die(o); };
    destroyer(Kind::Iterator) = [](Object* o) { decref(std::exchange(static_cast<Iterator*>(o)->seq, Obj{})); destroy<Iterator>(o); };
    destroyer(Kind::DictView) = [](Object* o) { decref(std::exchange(static_cast<DictView*>(o)->dict, Obj{})); destroy<DictView>(o); };
    destroyer(Kind::CodeKind) = [](Object* o) { destroy<CodeObject>(o); };
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
// The empty string and the one-character Latin-1 strings are one object each (unicode_empty,
// the latin1 singletons), the literals among them too
Ref str_new(std::string_view utf8) {
    if (utf8.empty() || (utf8.size() == 1 && static_cast<unsigned char>(utf8[0]) < 0x80) ||
        (utf8.size() == 2 && (static_cast<unsigned char>(utf8[0]) == 0xC2 || static_cast<unsigned char>(utf8[0]) == 0xC3)))
        return Ref::share(Obj::of(intern(utf8)));
    return own(new Str(std::string(utf8), false));
}
Ref str_from_codepoints(std::u32string_view cps) {
    if (cps.empty() || (cps.size() == 1 && cps[0] < 0x100)) {
        std::string utf8;
        if (!cps.empty()) Str::append_utf8(utf8, cps[0]);
        return Ref::share(Obj::of(intern(utf8)));
    }
    return own(new Str(cps, false));
}
const Str* as_str(Obj v) {
    if (!v.is_object() || v.object()->kind != Kind::Str) return nullptr;
    return static_cast<const Str*>(v.object());
}

// ---- tuples and lists ----
namespace {
Ref empty_tuple() {                              // the empty tuple is one object, as CPython's
    static Tuple* t = [] {
        auto* e = new Tuple;
        e->flags |= IMMORTAL;
        return e;
    }();
    return Ref::share(Obj::of(t));
}
}  // namespace
Ref tuple_new(std::initializer_list<Obj> items) {
    if (items.size() == 0) return empty_tuple();
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
    if (items.empty()) return empty_tuple();
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

// CPython's hash
std::int64_t full_hash(Obj v) {
    if (v.is_small()) return hash_small(v.small_value());
    Object* o = v.object();
    switch (o->kind) {
        case Kind::IntInstance:                  // an int subclass: its value's hash, unless it has its own
            if (type_lookup(o->cls, intern("__hash__")) == type_lookup(types().int_, intern("__hash__"))) return big_hash(v);
            break;
        case Kind::BigInt: return big_hash(v);
        case Kind::FloatInstance:                // as an int subclass's
            if (type_lookup(o->cls, intern("__hash__")) != type_lookup(types().float_, intern("__hash__"))) break;
            return float_hash(v);
        case Kind::Float: return float_hash(v);
        case Kind::ComplexInstance:              // as a float subclass's
            if (type_lookup(o->cls, intern("__hash__")) != type_lookup(types().complex_, intern("__hash__"))) break;
            return complex_hash(v);
        case Kind::Complex: return complex_hash(v);
        case Kind::Dict:                         // a frozendict, unless its class has its own
            if ((o->flags & FROZEN_DICT) != 0 && type_lookup(o->cls, intern("__hash__")) == type_lookup(types().frozendict, intern("__hash__")))
                return frozendict_hash(v);
            break;
        case Kind::Bool: return static_cast<BoolObject*>(o)->value ? 1 : 0;
        case Kind::Str:
            if (has_attributes(o) && type_lookup(o->cls, intern("__hash__")) != type_lookup(types().str, intern("__hash__"))) break;
            return str_hash(static_cast<Str*>(o));
        case Kind::Bytes: {                      // bytes_hash: the same SipHash as a str of the same units
            auto* b = static_cast<BytesObject*>(o);
            if (b->hash == -1) {
                if (b->data.empty()) b->hash = 0;
                else {
                    auto h = static_cast<std::int64_t>(siphash13(secret().k0, secret().k1,
                        reinterpret_cast<const unsigned char*>(b->data.data()), b->data.size()));
                    b->hash = h == -1 ? -2 : h;
                }
            }
            return b->hash;
        }
        case Kind::DictView:                     // keys and items views are unhashable; values views hash by identity
            if (static_cast<DictView*>(o)->which != DictView::Values) raise_new("TypeError", "unhashable type: '" + type_of(v)->name + "'");
            [[fallthrough]];
        case Kind::Class:                        // a metaclass's own __hash__ decides, as an instance's class's does
            if (has_python_type(v) && type_lookup(type_of(v), intern("__hash__")) != type_lookup(types().object, intern("__hash__")))
                break;
            [[fallthrough]];
        case Kind::Singleton:
            if (o == NONE) return 0xfca86420;    // none_hash: a constant since 3.12
            [[fallthrough]];
        case Kind::PyFunction:
        case Kind::Builtin: {
            if (o->kind == Kind::Builtin && !static_cast<Builtin*>(o)->self.is_unset()) {   // meth_hash
                auto* b = static_cast<Builtin*>(o);
                auto h = pointer_hash(b->self.is_object() ? b->self.object() : nullptr) ^ pointer_hash(b->written.get().is_object() ? static_cast<const void*>(b->written.get().object()) : reinterpret_cast<const void*>(b->fn));
                return h == -1 ? -2 : h;
            }
            // object.__hash__: the address rotated by 4 bits (_Py_HashPointer)
            auto h = pointer_hash(o);
            return h == -1 ? -2 : h;
        }
        case Kind::Method: {                     // method_hash: its object's address, and its function's hash
            auto* m = static_cast<Method*>(o);
            auto h = pointer_hash(m->self.is_object() ? m->self.object() : nullptr) ^ hash_of(m->func);
            return h == -1 ? -2 : h;
        }
        case Kind::Set: {                        // frozenset_hash_impl; a set's __hash__ is None, below
            auto* so = static_cast<SetObject*>(o);
            if (!so->frozen) break;
            auto shuffle = [](std::uint64_t h) { return ((h ^ 89869747UL) ^ (h << 16)) * 3644798167UL; };
            std::uint64_t hash = 0;
            for (const auto& e : so->table) hash ^= shuffle(static_cast<std::uint64_t>(e.hash));
            if ((so->table.size() - so->fill) & 1) hash ^= shuffle(0);
            if ((so->fill - so->used) & 1) hash ^= shuffle(static_cast<std::uint64_t>(-1));
            hash ^= (static_cast<std::uint64_t>(so->used) + 1) * 1927868237UL;
            hash ^= (hash >> 11) ^ (hash >> 25);
            hash = hash * 69069U + 907133923UL;
            if (hash == static_cast<std::uint64_t>(-1)) hash = 590923713UL;
            return static_cast<std::int64_t>(hash);
        }
        case Kind::Range: {                      // range_hash: as (len, start, step), None where they do not matter
            Ref n = range_length_big(v), start = range_field(v, 0), step = range_field(v, 2);
            std::int64_t len = -1;
            int_fits_i64(n.get(), len);
            Ref t = tuple_new({n.get(), len == 0 ? None() : start.get(), len == 0 || len == 1 ? None() : step.get()});
            return hash_of(t.get());
        }
        case Kind::Slice: {                      // slice_hash: tuplehash's mixing over the three, no length
            auto* s = static_cast<SliceObject*>(o);
            constexpr std::uint64_t P1 = 11400714785074694791ULL, P2 = 14029467366897019727ULL, P5 = 2870177450012600261ULL;
            std::uint64_t acc = P5;
            for (Obj part : {s->start, s->stop, s->step}) {
                acc += static_cast<std::uint64_t>(hash_of(part)) * P2;
                acc = rotl(acc, 31);
                acc *= P1;
            }
            if (acc == static_cast<std::uint64_t>(-1)) return 1546275796;
            return static_cast<std::int64_t>(acc);
        }
        case Kind::Tuple:
            if (has_attributes(o) && type_lookup(o->cls, intern("__hash__")) != type_lookup(types().tuple, intern("__hash__"))) break;
            return tuple_hash(static_cast<Tuple*>(o));
        case Kind::CodeKind: {                   // code_hash mixes the bytecode, which only CPython's code object has
            if (static_cast<CodeObject*>(o)->staged != nullptr)
                throw NotImplemented("hash() of a code object a staged compile() made (code_hash: its bytecode, E-02)");
            auto h = pointer_hash(o);            // a function's: one code object per code record, whose == is identity
            return h == -1 ? -2 : h;
        }
        default:
            break;
    }
    // a class's __hash__ (None when it defines __eq__ alone); a C++ type without one is unhashable
    Obj h = type_lookup(type_of(v), intern("__hash__"));
    if (!h.is_unset() && h != None()) {
        Ref r = call_special(v, "__hash__", {});
        if (!is_int(r.get())) raise_new("TypeError", "__hash__ method should return an integer");
        // slot_tp_hash: what fits a hash is the hash, so x.__hash__() returning hash(y) hashes as y; beyond that, long_hash
        std::int64_t x;
        return int_fits_i64(r.get(), x) ? x : big_hash(r.get());
    }
    raise_new("TypeError", "unhashable type: '" + type_of(v)->name + "'");
}
}  // namespace
std::uint64_t keyed_hash(std::uint64_t key, const unsigned char* src, std::size_t len) { return siphash13(key, 0, src, len); }   // _Py_KeyedHash

std::int64_t tuple_hash(const Tuple* t) {
    // tuplehash: xxHash's mixing, as Objects/tupleobject.c
    const auto& items = t->items;
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
std::int64_t str_hash(const Str* s) {             // unicode_hash, whatever a subclass says
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
std::int64_t hash_of(Obj v) {
    std::int64_t h = full_hash(v);
    return h == -1 ? -2 : h;                     // -1 is reserved for errors
}

// frozendict_hash: the pairs' hashes as a tuple's, mixed as a frozenset's, so the order does not
// matter; cached. A value may be a frozendict, so the descent is guarded: CPython's guard is the C
// stack, whose size no program can know, and this one is at a depth that fits a stack of 8 MB.
std::int64_t frozendict_hash(Obj v) {
    auto* d = static_cast<Dict*>(v.object());
    if (d->frozen_hash != -1) return d->frozen_hash;
    constexpr std::uint64_t P1 = 11400714785074694791ULL, P2 = 14029467366897019727ULL, P5 = 2870177450012600261ULL;
    static int depth = 0;
    if (depth >= 10000) raise_new("RecursionError", "maximum recursion depth exceeded while hashing a frozendict");
    struct Depth {
        Depth() { ++depth; }
        ~Depth() { --depth; }
    } guard;
    std::uint64_t hash = 0;
    for (std::size_t i = 0; i < d->entries.size(); ++i) {
        const auto& e = d->entries[i];
        if (e.key.is_unset()) continue;
        std::uint64_t acc = P5;
        for (auto lane : {static_cast<std::uint64_t>(e.hash), static_cast<std::uint64_t>(hash_of(e.value))}) {
            acc += lane * P2;
            acc = rotl(acc, 31);
            acc *= P1;
        }
        acc += 2 ^ (P5 ^ 3527539UL);
        if (acc == static_cast<std::uint64_t>(-1)) acc = 1546275796;
        hash ^= ((acc ^ 89869747UL) ^ (acc << 16)) * 3644798167UL;
    }
    hash ^= (static_cast<std::uint64_t>(d->used) + 1) * 1927868237UL;
    hash ^= (hash >> 11) ^ (hash >> 25);
    hash = hash * 69069U + 907133923UL;
    if (hash == static_cast<std::uint64_t>(-1)) hash = 590923713UL;
    d->frozen_hash = static_cast<std::int64_t>(hash);
    return d->frozen_hash;
}

// ---- the dict: object.hpp's compact dict, with Python's hash and == for its keys ----
namespace {
bool keys_equal(Obj a, Obj b) {
    if (a == b) return true;
    if (is_exact_str(a) && is_exact_str(b)) return as_str(a)->text == as_str(b)->text;   // unicode_eq; a subclass's __eq__ may have a say
    Ref r = compare(CmpOp::Eq, a, b);
    return truth(r.get());
}
const bool key_hooks_installed = (key_hash_hook() = hash_of, key_eq_hook() = keys_equal, true);
}  // namespace

Ref dict_new() { return own(new Dict); }
Ref frozendict_empty(ClassObject* cls) {
    DictObject* d;
    if (cls == types().frozendict) {
        d = new Dict;
        d->cls = cls;
    } else {
        d = new DictInstance(cls);
    }
    d->flags |= FROZEN_DICT;
    return own(d);
}

std::string fully_qualified_name(const ClassObject* c) {
    if (const Obj* mod = c->attrs.find(intern("__module__")))
        if (const Str* ms = as_str(*mod); ms != nullptr && ms->text != "builtins" && ms->text != "__main__")
            return ms->text + "." + c->qualname;
    return c->qualname;
}
namespace {
std::int64_t container_hash(Obj key, const char* as) {
    try {
        return hash_of(key);
    } catch (const PyError& e) {
        if (type_of(e.exc.get()) != exception_class("TypeError")) throw;
        Ref text = str_of(e.exc.get());
        raise_new("TypeError", "cannot use '" + fully_qualified_name(type_of(key)) + "' as a " + as + " (" +
                                   as_str(text.get())->text + ")");
    }
}
}  // namespace
std::int64_t dict_key_hash(Obj key, const Dict* into) {
    return container_hash(key, into != nullptr && (into->flags & FROZEN_DICT) != 0 ? "frozendict key" : "dict key");
}
std::int64_t set_key_hash(Obj key) { return container_hash(key, "set element"); }

Obj dict_get(Dict* d, Obj key) {
    std::int64_t hash = dict_key_hash(key, d);    // hashed even when the table is empty (A9-16)
    return dict_find(d, key, hash);
}
void dict_set(Dict* d, Obj key, Obj value) { dict_store(d, key, dict_key_hash(key, d), value); }
void dict_set_hashed(Dict* d, Obj key, std::int64_t hash, Obj value) { dict_store(d, key, hash, value); }
bool dict_del(Dict* d, Obj key) {
    Obj v = dict_pop(d, key, dict_key_hash(key));
    if (v.is_unset()) return false;
    decref(v);
    return true;
}

// ---- exceptions ----
namespace {
// BaseException_clear's order, the dict first; AttributeError_clear and NameError_clear release
// their own fields before it (Objects/exceptions.c, 3.15.2)
std::vector<std::string> exception_fields(std::initializer_list<std::string> own) {
    std::vector<std::string> out(own);
    for (const char* n : {"__dict__", "args", "__traceback__", "__cause__", "__context__", "__suppress_context__"}) out.push_back(n);
    return out;
}
struct ExceptionClasses {
    std::unordered_map<std::string, ClassObject*> by_name;
    ClassObject* make(const char* name, const char* base, std::optional<std::vector<std::string>> native = std::nullopt) {
        std::vector<ClassObject*> bases;
        if (base != nullptr) bases.push_back(by_name.at(base));
        ClassObject* c = make_class({.name = name, .bases = bases, .native = std::move(native)});
        c->has_weakref = cpython_has("weakref", name);
        if (base == nullptr) {                     // BaseException derives from object
            c->bases = {types().object};
            c->mro = {c, types().object};
        } else {
            c->mro = {c};
            for (ClassObject* m : bases[0]->mro) c->mro.push_back(m);
        }
        c->has_dict = true;                        // no __module__ in its dict: a static type's comes from tp_name (type_module)
        by_name[name] = c;
        return c;
    }
    ExceptionClasses() {
        // phase 1, step 3a: in C++ until classes compile (step 3a.2 moves them to the prelude)
        make("BaseException", nullptr, exception_fields({}));
        for (const char* n : {"Exception", "KeyboardInterrupt", "GeneratorExit"}) make(n, "BaseException");
        for (auto [n, b] : std::initializer_list<std::pair<const char*, const char*>>{
                 {"ArithmeticError", "Exception"}, {"ZeroDivisionError", "ArithmeticError"},
                 {"OverflowError", "ArithmeticError"}, {"AssertionError", "Exception"},
                 {"AttributeError", "Exception"}, {"LookupError", "Exception"}, {"IndexError", "LookupError"},
                 {"KeyError", "LookupError"}, {"NameError", "Exception"}, {"UnboundLocalError", "NameError"},
                 {"RuntimeError", "Exception"}, {"NotImplementedError", "RuntimeError"},
                 {"RecursionError", "RuntimeError"}, {"MemoryError", "Exception"}, {"ReferenceError", "Exception"}, {"TypeError", "Exception"},
                 {"ValueError", "Exception"}, {"ImportError", "Exception"}, {"ModuleNotFoundError", "ImportError"},
                 {"ImportCycleError", "ImportError"},
                 {"UnicodeError", "ValueError"}, {"UnicodeEncodeError", "UnicodeError"},
                 {"UnicodeDecodeError", "UnicodeError"}, {"UnicodeTranslateError", "UnicodeError"},
                 {"OSError", "Exception"}, {"BlockingIOError", "OSError"}, {"ConnectionError", "OSError"}, {"ChildProcessError", "OSError"},
                 {"BrokenPipeError", "ConnectionError"}, {"ConnectionAbortedError", "ConnectionError"}, {"ConnectionRefusedError", "ConnectionError"},
                 {"ConnectionResetError", "ConnectionError"}, {"FileExistsError", "OSError"}, {"FileNotFoundError", "OSError"}, {"IsADirectoryError", "OSError"},
                 {"NotADirectoryError", "OSError"}, {"InterruptedError", "OSError"}, {"PermissionError", "OSError"}, {"ProcessLookupError", "OSError"},
                 {"TimeoutError", "OSError"}, {"SyntaxError", "Exception"}, {"IndentationError", "SyntaxError"}, {"TabError", "IndentationError"},
                 {"_IncompleteInputError", "SyntaxError"}, {"StopAsyncIteration", "Exception"}, {"EOFError", "Exception"}, {"PythonFinalizationError", "RuntimeError"},
                 {"FloatingPointError", "ArithmeticError"}, {"SystemError", "Exception"}, {"BufferError", "Exception"}, {"Warning", "Exception"},
                 {"UserWarning", "Warning"}, {"DeprecationWarning", "Warning"}, {"PendingDeprecationWarning", "Warning"}, {"SyntaxWarning", "Warning"},
                 {"RuntimeWarning", "Warning"}, {"FutureWarning", "Warning"}, {"ImportWarning", "Warning"}, {"UnicodeWarning", "Warning"}, {"BytesWarning", "Warning"},
                 {"EncodingWarning", "Warning"}, {"ResourceWarning", "Warning"}}) {
            std::optional<std::vector<std::string>> own;
            if (std::string_view(n) == "AttributeError") own = exception_fields({"obj", "name"});
            if (std::string_view(n) == "NameError") own = exception_fields({"name"});
            if (std::string_view(n) == "ImportError") own = exception_fields({"msg", "name", "path", "name_from"});
            if (std::string_view(n) == "OSError") own = exception_fields({"errno", "strerror", "filename", "filename2", "written"});
            if (std::string_view(n) == "SyntaxError") own = exception_fields({"msg", "filename", "lineno", "offset", "text", "end_lineno", "end_offset", "print_file_and_line", "_metadata"});
            if (std::string_view(n).starts_with("Unicode") && std::string_view(n) != "UnicodeError")
                own = exception_fields({"encoding", "object", "start", "end", "reason"});
            make(n, b, own);
        }
        make("SystemExit", "BaseException", exception_fields({"code"}));
        make("StopIteration", "Exception", exception_fields({"value"}));
        // PyBaseExceptionGroupObject: msg, excs (a tuple), excs_str (the repr of a sequence that was no list or tuple); its
        // subclass ExceptionGroup is a heap type made by type() at start-up (types.cpp), as PyErr_NewException makes it
        make("BaseExceptionGroup", "BaseException", exception_fields({"msg", "excs", "excs_str"}));
    }
};
ExceptionClasses& exceptions() {
    static ExceptionClasses e;
    return e;
}

Ref new_exception(ClassObject* c, Ref args) {
    auto* e = new_instance(c);
    Ref r = own(e);
    set_exception_field(r.get(), "args", args.get());
    return r;
}
}  // namespace

ClassObject* exception_class(const char* name) { return exceptions().by_name.at(name); }
std::vector<ClassObject*> exception_classes() {
    std::vector<ClassObject*> out;
    for (auto& [n, c] : exceptions().by_name) out.push_back(c);
    return out;
}

bool is_exception_instance(Obj v) {
    return is_kind(v, Kind::Instance) && is_subclass(v.object()->cls, exception_class("BaseException"));
}
Obj exception_field(Obj exc, const char* name) { return static_cast<Instance*>(exc.object())->field(intern(name)); }
void set_exception_field(Obj exc, const char* name, Obj value) {
    incref(value);
    decref(std::exchange(static_cast<Instance*>(exc.object())->field(intern(name)), value));
}

namespace {
std::vector<Obj>& handled() {                    // the exceptions being handled, innermost last
    static std::vector<Obj> stack;
    return stack;
}
}  // namespace

std::vector<Obj>& handled_exceptions() { return handled(); }
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
    // _PyErr_SetObject: an exception raised while another is handled takes it as its context
    // (PEP 3134), replacing any it had; a link back to the new exception along the handled one's
    // chain is cut first, so that no cycle is made, while a cycle already there is left alone
    // (Floyd's walk, Python/errors.c)
    if (!handled().empty() && is_exception_instance(exc)) {
        Ref handling = Ref::share(handled().back());
        if (handling.get() != exc) {
            Obj o = handling.get(), slow = o;
            bool toggle = false;
            for (Obj ctx = exception_field(o, "__context__"); !ctx.is_unset(); ctx = exception_field(o, "__context__")) {
                if (ctx == exc) {
                    set_exception_field(o, "__context__", Obj{});
                    break;
                }
                o = ctx;
                if (o == slow) break;                // a cycle already there: every link was checked
                if (toggle) slow = exception_field(slow, "__context__");
                toggle = !toggle;
            }
            set_exception_field(exc, "__context__", handling.get());
        }
    }
    throw PyError{Ref::share(exc)};
}

void reraise() {
    if (handled().empty()) raise_new("RuntimeError", "No active exception to reraise");
    throw PyError{Ref::share(handled().back()), detail::BARE_RAISE};   // records nothing here (RL-221)
}

Obj unsupported_constant(const char* what) { throw NotImplemented(what); }
Obj str_constant_cps(std::initializer_list<char32_t> cps) {
    return Obj::of(new Str(std::u32string_view(cps.begin(), cps.size()), true));
}

void raise_new(const char* type, const std::string& message) {
    Ref msg = str_new(message);
    Ref exc = new_exception(exception_class(type), tuple_new({msg.get()}));
    if (is_subclass(exception_class(type), exception_class("ImportError"))) set_exception_field(exc.get(), "msg", msg.get());
    raise(exc.get());
}

bool is_subclass(ClassObject* c, ClassObject* base) {
    return std::find(c->mro.begin(), c->mro.end(), base) != c->mro.end();
}

namespace {
bool is_exception_class(Obj v) {                 // PyExceptionClass_Check
    return is_kind(v, Kind::Class) && is_subclass(static_cast<ClassObject*>(v.object()), exception_class("BaseException"));
}
// calling an exception class with no arguments, as do_raise does (Python/ceval.c)
Ref instantiate(Obj cls) {
    Ref made = invoke(cls, {});
    if (!is_exception_instance(made.get())) {
        Ref shown = repr_of(cls), got = repr_of(Obj::of(type_of(made.get())));
        raise_new("TypeError", "calling " + as_str(shown.get())->text + " should have returned an instance of BaseException, not " +
                                   as_str(got.get())->text);
    }
    return made;
}
}  // namespace

void raise_type(Obj value, Obj cause, bool has_cause) {
    // do_raise: the exception made or taken first, then the cause: an exception class is called,
    // an instance taken, None clears it; anything else is a TypeError. Either way the cause sets
    // __suppress_context__ (PyException_SetCause).
    Ref exc;
    if (is_exception_class(value)) exc = instantiate(value);
    else if (is_exception_instance(value)) exc = Ref::share(value);
    else raise_new("TypeError", "exceptions must derive from BaseException");
    if (has_cause) {
        Ref fixed;
        if (is_exception_class(cause)) fixed = instantiate(cause);
        else if (is_exception_instance(cause)) fixed = Ref::share(cause);
        else if (cause != None()) raise_new("TypeError", "exception causes must derive from BaseException");
        set_exception_field(exc.get(), "__suppress_context__", boolean(true));
        set_exception_field(exc.get(), "__cause__", fixed.get());
    }
    raise(exc.get());
}

bool exception_matches(Obj exc, Obj spec) {
    // CHECK_EXC_MATCH: the clause's types are checked before any is matched; a tuple's items must
    // each be an exception class (_PyEval_CheckExceptTypeValid), then PyErr_GivenExceptionMatches
    static const char* const CANNOT_CATCH = "catching classes that do not inherit from BaseException is not allowed";
    if (is_kind(spec, Kind::Tuple)) {
        auto& items = static_cast<Tuple*>(spec.object())->items;
        for (Obj s : items)
            if (!is_exception_class(s)) raise_new("TypeError", CANNOT_CATCH);
        for (Obj s : items)
            if (is_subclass(type_of(exc), static_cast<ClassObject*>(s.object()))) return true;
        return false;
    }
    if (!is_exception_class(spec)) raise_new("TypeError", CANNOT_CATCH);
    return is_subclass(type_of(exc), static_cast<ClassObject*>(spec.object()));
}

Obj traceback_of(Obj exc) { return is_exception_instance(exc) ? exception_field(exc, "__traceback__") : Obj{}; }

namespace {
std::uint64_t frame_ids = 0;                     // a frame's id, given on its first record: never reused

// prepends (code, line) for frame `id` to exc's traceback, as PyTraceBack_Here does
Traceback* add_entry(Obj exc, const Code& code, int line, std::uint64_t id) {
    Obj prev = traceback_of(exc);
    auto* tb = new Traceback(&code, line, Ref::share(prev.is_unset() ? None() : prev));
    tb->frame = id;
    Ref held = own(tb);
    set_exception_field(exc, "__traceback__", held.get());
    return tb;
}
}  // namespace

void detail::arrive(const Code& code, int line, std::uint64_t& id, PyError& e) noexcept {
    try {
        if (!code.shown) {                       // no frame in CPython: the caller records the call
            e.recorded = 0;
            return;
        }
        if (id == 0) id = ++frame_ids;
        if (e.recorded == id) return;            // re-raised by this frame
        if (e.recorded != BARE_RAISE && is_kind(e.exc.get(), Kind::Instance)) add_entry(e.exc.get(), code, line, id);
        e.recorded = id;
    } catch (...) {
        // a frame record that cannot be made loses the entry, never the exception
    }
}

void detail::record_frame(const Code& code, int line, std::uint64_t& id, Ref* const* locals, std::size_t n) noexcept {
    try {
        Obj exc = raising();
        auto* err = static_cast<PyError*>(const_cast<void*>(raising_owner()));
        if (!is_kind(exc, Kind::Instance) || err == nullptr) return;
        std::uint64_t rec = err->recorded;
        err->recorded = 0;                       // the caller records the call
        if (!code.shown) return;
        Traceback* entry = nullptr;
        if (rec == BARE_RAISE || (id != 0 && rec == id)) {
            // recorded at one of this frame's catches (or re-raised bare): its newest entry for
            // this frame, if the traceback still has one, takes the locals
            for (Obj t = traceback_of(exc); id != 0 && is_kind(t, Kind::Traceback); t = static_cast<Traceback*>(t.object())->next.get())
                if (static_cast<Traceback*>(t.object())->frame == id) {
                    entry = static_cast<Traceback*>(t.object());
                    break;
                }
        } else {
            if (id == 0) id = ++frame_ids;
            entry = add_entry(exc, code, line, id);
        }
        if (entry != nullptr)
            for (std::size_t i = 0; i < n; ++i) entry->locals.push_back(std::move(*locals[i]));
    } catch (...) {
        // a frame record that cannot be made loses the entry, never the exception
    }
}

}  // namespace bella
