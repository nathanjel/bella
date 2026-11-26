// runtime/src/core.cpp -- the builtin types, their objects' deaths, strings, tuples, lists, the
// dict, hashing, exceptions and frame records (bella/runtime.hpp).
#include <pthread.h>
#include "bella/runtime.hpp"

#include <algorithm>
#include <cerrno>
#include <climits>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <limits>
#include <random>
#include <string>

#include <signal.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <ucontext.h>
#include <unistd.h>

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
        x.str_ascii_iterator = builtin_type("str_ascii_iterator", {x.object});
        x.str_iterator = builtin_type("str_iterator", {x.object});
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
        x.memoryview = nullptr;                  // runtime/prelude/memoryview.py's class, once the prelude has run (call.cpp)
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
Proxy::Proxy(Obj given) : Object(Kind::Proxy), mapping(Ref::share(given)) { cls = types().mappingproxy; }
Proxy::Proxy(ClassObject* immortal) : Object(Kind::Proxy), of(immortal) { cls = types().mappingproxy; }
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
    if (o == DictItemsIt || o == DictRevItemsIt) result = tuple_new({None(), None()}).release();   // dictiter_new: PyTuple_Pack(2, Py_None, Py_None)
    switch (o) {
        case RangeIt: cls = types().range_iterator; break;
        case LongRangeIt: cls = types().longrange_iterator; break;
        case TupleIt: cls = types().tuple_iterator; break;
        case ListIt: cls = types().list_iterator; break;
        case ListRevIt: cls = types().list_reverseiterator; break;
        case StrIt: {                            // unicode_iter: the ASCII iterator for a compact ASCII str, which a subclass's instance is not
            auto* str = static_cast<Str*>(s.object());
            cls = str->cls == types().str && str->ascii ? types().str_ascii_iterator : types().str_iterator;
            break;
        }
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
    hold_globals(m);                             // func_globals
    // func_new_impl: __module__ is the globals' __name__ as it stands now; a module that renames itself afterwards
    // (importlib renames _frozen_importlib) leaves its functions' __module__ as it was (review G15 range: importlib)
    if (Obj n = dict_get(m->dict, Obj::of(intern("__name__"))); !n.is_unset()) module_name = Ref::share(n);
}
Module::Module(const char* n) : Module(n, false) {}
namespace {
std::unordered_map<std::uint64_t, Module*>& live_modules() {   // the counted modules alive, by serial number
    static std::unordered_map<std::uint64_t, Module*> table;
    return table;
}
std::uint64_t module_serials = 0;
}  // namespace
Module* live_module(std::uint64_t serial) {
    auto it = live_modules().find(serial);
    return it == live_modules().end() ? nullptr : it->second;
}
Module::Module(const char* n, bool counted) : Object(Kind::Module), name(str_new(n)), dict(new Dict) {
    cls = types().module;
    incref(dict);
    if (counted) {
        serial = ++module_serials;
        live_modules()[serial] = this;
        return;
    }
    flags |= IMMORTAL;                           // the runtime's own: it lives as long as the program
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
void forget_module(const Module* m) {
    std::erase(all_modules(), m);
    hidden_modules().push_back(const_cast<Module*>(m));
    note_runtime_namespace(m);
}
namespace {
std::unordered_set<const Module*>& runtime_namespaces() {
    static std::unordered_set<const Module*> made;
    return made;
}
}  // namespace
void note_runtime_namespace(const Module* m) { runtime_namespaces().insert(m); }
bool runtime_namespace(const Module* m) { return runtime_namespaces().contains(m); }
std::vector<Module*>& hidden_modules() {
    static std::vector<Module*> made;
    return made;
}
std::vector<Module*>& all_modules() {
    static std::vector<Module*> made;
    return made;
}
LazyImport::LazyImport() : Object(Kind::LazyImport) { cls = types().lazy_import; }
CodeObject::CodeObject(const Code* c) : Object(Kind::CodeKind), code(c) { cls = types().code; }
FrameObject::FrameObject(const Code* c, Module* m) : Object(Kind::Frame), code(c), module(m) {
    static ClassObject* const frame_class = no_instances_yet("frame");
    cls = frame_class;
}
Traceback::Traceback(const Code* c, int l, Ref nx) : Object(Kind::Traceback), code(c), line(l), next(std::move(nx)) {
    cls = types().traceback;
}

// ---- deaths, in CPython's orders (measured on 3.15.2: a tuple or list releases its items last
// to first, a dict its entries in order, each key before its value) ----
namespace {
template <class T>
void destroy(Object* o) { detail::free_object(static_cast<T*>(o)); }   // a tombstone while the collector's buffer names it

void release_backwards(std::vector<Obj>& items) {
    for (auto it = items.rbegin(); it != items.rend(); ++it) decref(std::exchange(*it, Obj{}));
}

// A module's own holds on its namespace (md_dict; a staged text's builtins and locals with it), let go of when it dies or a
// collection clears it (module_dealloc, module_clear). Its holders keep the way to the namespace through it; with none, the way
// goes before the namespace's count does, which may run anything
void let_go_of_namespace(Module* m) {
    if (!m->holds_namespace) return;
    m->holds_namespace = false;
    Dict* d = m->dict;
    Dict* b = m->builtins;
    Dict* l = std::exchange(m->locals, nullptr);  // a text's locals: the record's alone (RL-945)
    if (m->holders == 0) {
        m->dict = nullptr;
        m->builtins = nullptr;
    }
    if (d != nullptr) decref(d);
    if (b != nullptr) decref(b);
    if (l != nullptr) decref(l);
}
void free_module(Module* m) {                    // what was left of a dead module, once nothing finds its namespace through it
    forget_filled(m);
    m->name = Ref{};
    destroy<Module>(m);
}
}  // namespace

void hold_counted_globals(Module* m) {
    if (m->dict == nullptr) throw ModelError("a module's namespace taken as globals through a module that has no way to it");
    ++m->holders;
    incref(m->dict);
    if (m->builtins != nullptr) incref(m->builtins);
}
void release_counted_globals(Module* m) {
    if (m->holders <= 0) throw ModelError("a module's namespace let go of by more holders than held it");
    Dict* d = m->dict;
    Dict* b = m->builtins;
    if (--m->holders == 0 && !m->holds_namespace) {
        m->dict = nullptr;
        m->builtins = nullptr;
        if (m->flags & DEAD) free_module(m);
    }
    decref(d);                                   // func_clear's order: the globals, then the builtins
    if (b != nullptr) decref(b);
}

namespace {

bool register_deaths() {
    destroyer(Kind::Str) = [](Object* o) { delete static_cast<Str*>(o); };
    destroyer(Kind::Tuple) = [](Object* o) { release_backwards(static_cast<Tuple*>(o)->items); destroy<Tuple>(o); };
    destroyer(Kind::List) = [](Object* o) { release_backwards(static_cast<List*>(o)->items); destroy<List>(o); };
    destroyer(Kind::Cell) = [](Object* o) { decref(std::exchange(static_cast<Cell*>(o)->value, Obj{})); destroy<Cell>(o); };
    destroyer(Kind::Module) = [](Object* o) {     // module_dealloc, its weak references cleared by now: its namespace let go of,
        auto* m = static_cast<Module*>(o);        // and its memory, unless what holds the namespace as its globals finds it here
        if (m->serial != 0) live_modules().erase(m->serial);
        bool kept = m->holders > 0;
        if (kept && (o->flags & LISTED)) detail::unlist(o);   // out of a collection's lists, as freed memory is
        let_go_of_namespace(m);
        if (!kept) free_module(m);                // (a holder that let go meanwhile has freed it: m->holders was not 0)
    };
    destroyer(Kind::PyFunction) = [](Object* o) {
        auto* f = static_cast<PyFunction*>(o);     // func_clear's order: its globals first, then __module__ (RL-579)
        if (Module* m = std::exchange(f->module, nullptr)) release_globals(m);
        f->module_name = Ref{};
        f->defaults = Ref{};
        f->kwdefaults = Ref{};
        f->doc = Ref{};
        f->dict = Ref{};
        f->closure_tuple = Ref{};                  // func_closure is a tuple: its cells go last one first (RL-586)
        for (auto c = f->closure.rbegin(); c != f->closure.rend(); ++c) *c = Ref{};
        f->annotations = Ref{};
        f->annotate = Ref{};
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
    destroyer(Kind::Iterator) = [](Object* o) {  // dictiter_dealloc: the dict, then the pair it kept
        auto* it = static_cast<Iterator*>(o);
        decref(std::exchange(it->seq, Obj{}));
        decref(std::exchange(it->result, Obj{}));
        destroy<Iterator>(o);
    };
    destroyer(Kind::DictView) = [](Object* o) { decref(std::exchange(static_cast<DictView*>(o)->dict, Obj{})); destroy<DictView>(o); };
    destroyer(Kind::CodeKind) = [](Object* o) { destroy<CodeObject>(o); };
    destroyer(Kind::Frame) = [](Object* o) {     // frame_dealloc: the values it owns (a class body's namespace, then the rest, last
        auto* f = static_cast<FrameObject*>(o);  // first), then f_back; f_funcobj, which holds its globals, first of all
        f->module.reset();
        f->ns = Ref{};
        for (auto it = f->values.rbegin(); it != f->values.rend(); ++it) *it = Ref{};
        f->back = Ref{};
        destroy<FrameObject>(o);
    };
    destroyer(Kind::Traceback) = [](Object* o) {
        auto* t = static_cast<Traceback*>(o);      // tb_dealloc: the deeper entries, then the frame (its function's globals last)
        t->next = Ref{};
        t->frame_obj = Ref{};
        t->module.reset();
        destroy<Traceback>(o);
    };
    destroyer(Kind::Native) = [](Object* o) { destroy<Native>(o); };
    destroyer(Kind::Slice) = [](Object* o) {
        auto* s = static_cast<SliceObject*>(o);
        decref(std::exchange(s->step, Obj{}));              // slice_dealloc's order: the step, the start, the stop
        decref(std::exchange(s->start, Obj{}));
        decref(std::exchange(s->stop, Obj{}));
        destroy<SliceObject>(o);
    };
    destroyer(Kind::Proxy) = [](Object* o) { destroy<Proxy>(o); };
    return true;
}
const bool deaths_registered = register_deaths();

// ---- what each kind holds, for the cycle collector (object.hpp's traverser and clearer; CPython's tp_traverse and tp_clear) ----
// A traverse names the counted references the kind's release lets go of; a kind CPython gives no tp_clear has none here: a
// cycle through it is broken by clearing another of its members.
void visit_ref(const Ref& r, std::vector<Object*>& out) { detail::visit(r.get(), out); }
// A namespace whose module sys.modules holds under its own name is reachable from outside (sys.modules is the interpreter's,
// a root), and so is all it reaches: the collector does not walk it, from the module or from what holds it as its globals.
// Trial deletion finds the same groups in the same order (what the walk leaves out is held from outside), without walking the
// program's whole module graph from every function among its candidates (refmodel/objects.py: RefModule.rooted). The look-up
// runs no code of the program's: an exact str's, in the table the import system keeps (writes to it are E-04)
namespace {
// What an exact str names in a dict, found along lookdict's probe and compared as unicode_eq compares, or Unset; Unset too where
// the probe meets a key of the same hash that is not an exact str, whose == would be the program's code
Obj exact_str_get(const Dict* d, const Str* key) {
    if (d->indices.empty()) return Obj{};
    std::int64_t hash = hash_of(Obj::of(key));   // an exact str's: its text's, kept
    std::size_t mask = d->indices.size() - 1;
    auto perturb = static_cast<std::uint64_t>(hash);
    for (std::size_t i = static_cast<std::size_t>(hash) & mask;; i = (i * 5 + static_cast<std::size_t>(perturb) + 1) & mask) {
        std::int64_t ix = d->indices[i];
        if (ix == detail::DKIX_EMPTY) return Obj{};
        if (ix >= 0) {
            const auto& e = d->entries[static_cast<std::size_t>(ix)];
            if (!e.key.is_unset() && e.hash == hash) {
                if (e.key.object() == key) return e.value;
                if (!is_exact_str(e.key)) return Obj{};
                if (name_arg(e.key)->text == key->text) return e.value;
            }
        }
        perturb >>= detail::PERTURB_SHIFT;
    }
}
}  // namespace
bool rooted_namespace(const Module* m) {
    if (m->serial == 0 || (m->flags & DEAD) || !m->holds_namespace) return false;
    Dict* modules = sys_modules();
    if (modules == nullptr) return false;
    Obj name = exact_str_get(m->dict, intern("__name__"));
    if (!name.is_object() || !is_exact_str(name)) return false;
    Obj held = exact_str_get(modules, as_str(name));
    return held.is_object() && held.object() == m;
}
// What a function, a frame object or a traceback entry holds of its module: what hold_globals took, its namespace (func_globals)
// and a staged text's builtins; nothing of an immortal module, nor of one whose namespace is rooted
void visit_globals(const Module* m, std::vector<Object*>& out) {
    if (m == nullptr || (m->flags & IMMORTAL) || rooted_namespace(m)) return;
    if (m->dict != nullptr) detail::visit(Obj::of(m->dict), out);
    if (m->builtins != nullptr) detail::visit(Obj::of(m->builtins), out);
}
bool register_traversals() {
    using detail::visit;
    detail::traverser(Kind::Cell) = [](Object* o, std::vector<Object*>& out) { visit(static_cast<Cell*>(o)->value, out); };
    detail::clearer(Kind::Cell) = [](Object* o) { decref(std::exchange(static_cast<Cell*>(o)->value, Obj{})); };
    detail::traverser(Kind::PyFunction) = [](Object* o, std::vector<Object*>& out) {   // func_traverse's order
        auto* f = static_cast<PyFunction*>(o);
        visit_globals(f->module, out);           // its globals
        visit_ref(f->module_name, out);
        visit_ref(f->defaults, out);
        visit_ref(f->kwdefaults, out);
        visit_ref(f->doc, out);
        visit_ref(f->name, out);
        visit_ref(f->dict, out);
        visit_ref(f->closure_tuple, out);
        for (const Ref& c : f->closure) visit_ref(c, out);
        visit_ref(f->annotations, out);
        visit_ref(f->annotate, out);
        visit_ref(f->type_params, out);
        visit_ref(f->qualname, out);
    };
    detail::clearer(Kind::PyFunction) = [](Object* o) {   // func_clear's order: its globals first
        auto* f = static_cast<PyFunction*>(o);
        if (Module* m = std::exchange(f->module, nullptr)) release_globals(m);
        f->module_name = Ref{};
        f->defaults = Ref{};
        f->kwdefaults = Ref{};
        f->doc = Ref{};
        f->dict = Ref{};
        f->closure_tuple = Ref{};
        for (auto c = f->closure.rbegin(); c != f->closure.rend(); ++c) *c = Ref{};
        f->annotations = Ref{};
        f->annotate = Ref{};
        f->type_params = Ref{};
        f->name = str_new("");                   // func_name and func_qualname: the empty string
        f->qualname = str_new("");
    };
    detail::traverser(Kind::Builtin) = [](Object* o, std::vector<Object*>& out) {   // meth_traverse: m_self, m_module
        auto* b = static_cast<Builtin*>(o);
        visit(b->self, out);
        visit_ref(b->module_name, out);
        visit_ref(b->written, out);
    };
    detail::traverser(Kind::Method) = [](Object* o, std::vector<Object*>& out) {
        auto* m = static_cast<Method*>(o);
        visit(m->func, out);
        visit(m->self, out);
    };
    detail::traverser(Kind::Module) = [](Object* o, std::vector<Object*>& out) {    // module_traverse: md_dict, unless rooted
        auto* m = static_cast<Module*>(o);
        if (!m->holds_namespace || rooted_namespace(m)) return;
        if (m->dict != nullptr) visit(Obj::of(m->dict), out);
        if (m->builtins != nullptr) visit(Obj::of(m->builtins), out);
        if (m->locals != nullptr && m->locals != m->dict) visit(Obj::of(m->locals), out);
    };
    detail::clearer(Kind::Module) = [](Object* o) { let_go_of_namespace(static_cast<Module*>(o)); };   // module_clear
    detail::traverser(Kind::Iterator) = [](Object* o, std::vector<Object*>& out) {  // dictiter_traverse, listiter_traverse
        auto* it = static_cast<Iterator*>(o);
        visit(it->seq, out);
        visit(it->result, out);
    };
    detail::traverser(Kind::DictView) = [](Object* o, std::vector<Object*>& out) { visit(static_cast<DictView*>(o)->dict, out); };
    detail::traverser(Kind::LazyImport) = [](Object* o, std::vector<Object*>& out) {
        auto* l = static_cast<LazyImport*>(o);
        visit_ref(l->builtins, out);
        visit_ref(l->from, out);
        visit_ref(l->attr, out);
    };
    detail::clearer(Kind::LazyImport) = [](Object* o) {
        auto* l = static_cast<LazyImport*>(o);
        l->builtins = Ref{};
        l->from = Ref{};
        l->attr = Ref{};
    };
    detail::traverser(Kind::Super) = [](Object* o, std::vector<Object*>& out) {
        auto* su = static_cast<SuperObject*>(o);
        visit(su->obj, out);
        visit(su->type, out);
        visit(su->obj_type, out);
    };
    detail::traverser(Kind::Traceback) = [](Object* o, std::vector<Object*>& out) {   // tb_traverse: the next entry, then the frame
        auto* t = static_cast<Traceback*>(o);
        visit_ref(t->next, out);
        visit_ref(t->frame_obj, out);
        visit_globals(t->module.module(), out);
    };
    detail::clearer(Kind::Traceback) = [](Object* o) {   // tb_clear: the next entry, then the frame (its locals, last first)
        auto* t = static_cast<Traceback*>(o);
        t->next = Ref{};
        t->frame_obj = Ref{};
    };
    detail::traverser(Kind::Frame) = [](Object* o, std::vector<Object*>& out) {   // frame_traverse: f_back, then the frame it owns
        auto* f = static_cast<FrameObject*>(o);  // (_PyFrame_Traverse: f_locals, the function's globals, the values in order)
        visit_ref(f->back, out);
        visit_ref(f->ns, out);
        visit_globals(f->module.module(), out);
        for (const Ref& r : f->values) visit_ref(r, out);
    };
    detail::clearer(Kind::Frame) = [](Object* o) {   // frame_tp_clear: the values, last first, then f_locals; f_back stays
        detail::clear_frame_values(static_cast<FrameObject*>(o));
    };
    detail::traverser(Kind::Slice) = [](Object* o, std::vector<Object*>& out) {
        auto* s = static_cast<SliceObject*>(o);
        visit(s->start, out);
        visit(s->stop, out);
        visit(s->step, out);
    };
    detail::traverser(Kind::Proxy) = [](Object* o, std::vector<Object*>& out) { visit_ref(static_cast<Proxy*>(o)->mapping, out); };
    detail::traverser(Kind::Generator) = [](Object* o, std::vector<Object*>& out) {   // gen_traverse: its names, its frame, its exc_state
        auto* g = static_cast<Generator*>(o);
        visit_ref(g->name, out);
        visit_ref(g->qualname, out);
        if (g->state != GenState::Finished) {
            visit_ref(g->resumed.frame_obj, out);
            visit_ref(g->function, out);
            for (const Ref& r : g->slots) visit_ref(r, out);
            visit_ref(g->sent, out);
            visit_ref(g->pending, out);
            visit_ref(g->delegate, out);
            visit_ref(g->delegate_shown, out);
            for (const auto& e : g->errors) if (e) visit_ref(e->exc, out);
        }
        for (Obj e : g->handled) visit(e, out);
    };
    return true;
}
const bool traversals_registered = register_traversals();
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
const Str* name_arg(Obj v) {                     // the str a prelude hands a primitive: anything else stops by name, never a null read (RL-1033)
    const Str* s = as_str(v);
    if (s == nullptr) throw NotImplemented("a primitive of the runtime handed a '" + type_of(v)->name + "' object where it takes a str");
    return s;
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

// ---- what the environment said at the start (Python/initconfig.c, Python/preconfig.c) ----
namespace {
// Py_ExitStatusException of a _PyStatus_ERR before the interpreter exists: fatal_error writes to descriptor 2 and exit(1)
[[noreturn]] void refuse_to_start(const char* function, const char* message) {
    std::string text = std::string("Fatal Python error: ") + function + ": " + message + "\nPython runtime state: preinitialized\n\n";
    for (std::size_t done = 0; done < text.size();) {
        ssize_t n = ::write(2, text.data() + done, text.size() - done);
        if (n <= 0) break;
        done += static_cast<std::size_t>(n);
    }
    std::_Exit(1);
}
const char* environment(const char* name) {     // _Py_GetEnv: a variable set to nothing is a variable not set
    const char* value = std::getenv(name);
    return value != nullptr && *value != '\0' ? value : nullptr;
}
bool str_to_int(const char* text, int& out) {    // _Py_str_to_int: strtol's number and nothing after it, within an int
    char* end = nullptr;
    errno = 0;
    long value = std::strtol(text, &end, 10);
    if (*end != '\0' || errno == ERANGE || value < INT_MIN || value > INT_MAX) return false;
    out = static_cast<int>(value);
    return true;
}
StartUp read_start_up() {
    StartUp s;
    if (const char* text = environment("PYTHONUNBUFFERED")) {     // _Py_get_env_flag: text and a number below zero count as 1
        int flag = 0;
        if (!str_to_int(text, flag) || flag < 0) flag = 1;
        s.buffered_stdio = flag < 1;
    }
    // A seed that cannot be taken is told of before the other two (measured on 3.15.2; case C-8-16)
    if (const char* text = environment("PYTHONHASHSEED"); text != nullptr && std::strcmp(text, "random") != 0) {   // config_init_hash_seed
        char* end = nullptr;
        errno = 0;
        unsigned long seed = std::strtoul(text, &end, 10);
        if (*end != '\0' || seed > 4294967295UL || (errno == ERANGE && seed == ULONG_MAX))
            refuse_to_start("config_init_hash_seed", "PYTHONHASHSEED must be \"random\" or an integer in range [0; 4294967295]");
        s.use_hash_seed = true;
        s.hash_seed = seed;
    }
    if (const char* text = environment("PYTHONINTMAXSTRDIGITS")) {   // config_init_int_max_str_digits; 640 is _PY_LONG_MAX_STR_DIGITS_THRESHOLD
        int digits = 0;
        if (!str_to_int(text, digits) || (digits != 0 && digits < 640))
            refuse_to_start("config_init_int_max_str_digits", "PYTHONINTMAXSTRDIGITS: invalid limit; must be >= 640 or 0 for unlimited.");
        s.int_max_str_digits = digits;
    }
    if (const char* text = environment("PYTHON_CPU_COUNT")) {        // config_init_cpu_count; its words are the option's
        int count = -1;
        if (std::strcmp(text, "default") != 0 && (!str_to_int(text, count) || count < 1))
            refuse_to_start("config_init_cpu_count", "-X cpu_count=n option: n is missing or an invalid number, n must be greater than 0");
        s.cpu_count = count;
    }
    return s;
}
}  // namespace
const StartUp& start_up() {
    static const StartUp s = read_start_up();
    return s;
}

// ---- hashing: CPython's functions (Python/pyhash.c, Objects/longobject.c) ----
namespace {
constexpr std::uint64_t HASH_MODULUS = (std::uint64_t{1} << 61) - 1;

// SipHash-1-3 keyed by the process's secret (spec D-14), as Python/pyhash.c
struct HashSecret {
    std::uint64_t k0 = 0, k1 = 0;
    HashSecret() {
        unsigned char key[24] = {};
        const StartUp& config = start_up();
        if (config.use_hash_seed) {
            unsigned long seed = config.hash_seed;
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
        case Kind::Bytes: {                      // bytes_hash: the same SipHash as a str of the same units; a subclass's own, below
            if (has_attributes(o) && type_lookup(o->cls, intern("__hash__")) != type_lookup(types().bytes, intern("__hash__"))) break;
            return bytes_hash(v);
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
        case Kind::Set: {                        // frozenset_hash_impl; a set's __hash__ is None, below; a subclass's own, below
            auto* so = static_cast<SetObject*>(o);
            if (!so->frozen) break;
            if (has_attributes(o) && type_lookup(o->cls, intern("__hash__")) != type_lookup(types().frozenset, intern("__hash__"))) break;
            return frozenset_hash(v);
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

std::int64_t bytes_hash(Obj v) {                 // bytes_hash: the same SipHash as a str of the same units, whatever a subclass says
    auto* b = static_cast<BytesObject*>(v.object());
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
std::int64_t frozenset_hash(Obj v) {             // frozenset_hash_impl, whatever a subclass says
    auto* so = static_cast<SetObject*>(v.object());
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

// ---- the native stack (RL-624) ----
namespace {
const char*& native_stack_top() {
    static const char* top = nullptr;
    return top;
}
struct StackRegion {
    void* low = nullptr;
    std::size_t size = 0;
};
StackRegion& program_stack() {                   // the stack on_main_stack made for the program, while the program is on it
    static StackRegion region;
    return region;
}
std::size_t& wanted_main_stack() {               // the policy's main_stack_mib, in bytes (pipeline/build.py main_unit hands it over)
    static std::size_t bytes = std::size_t{256} << 20;
    return bytes;
}
bool process_stack(void*& low, std::size_t& size) {   // the stack the process gave its first thread
    pthread_attr_t attr;
    if (pthread_getattr_np(pthread_self(), &attr) != 0) return false;
    bool known = pthread_attr_getstack(&attr, &low, &size) == 0 && low != nullptr && size != 0;
    pthread_attr_destroy(&attr);
    return known;
}
}  // namespace
void measure_native_stack() {
    void* low = program_stack().low;
    std::size_t size = program_stack().size;
    if (low == nullptr && !process_stack(low, size)) return;   // unknown: nothing is ever short, as before there was a watch
    {
        // CPython's soft limit is two of its margins (16 KiB each) above the stack's end. An exception raised from compiled
        // code, and what its handler then does, take more native stack than a bytecode loop's, so the part kept back here
        // is larger; the two marks of dealloc are CPython's, 2 and 4 margins above the soft limit
        constexpr std::size_t margin = std::size_t{1} << 14;
        const char* base = static_cast<const char*>(low);
        std::size_t kept_back = std::min<std::size_t>(size / 4, 12 * margin);
        detail::StackWatch& w = detail::stack_watch;
        w.soft_limit = base + kept_back;
        w.deposit_below = w.soft_limit + 2 * margin;
        w.destroy_from = w.soft_limit + 4 * margin;
        native_stack_top() = base + size;
    }
}

// ---- the stack the program runs on (decision 16 as the author changed it with Question 28, 2026-11-22) ----
// A compiled call is a native call, so how deep a program recurses is how much native stack it has; CPython keeps the
// frames of Python calls on the heap. The program therefore runs on a stack of the policy's size (`main_stack_mib` in
// bella.toml, 256 MiB where it says nothing) and not on the 8 MiB a shell gives: address space reserved at the start and
// memory only as the program uses it, with the thread it runs on still the process's first (its id is the process's).
// The process's hard limit on its stack is kept: the size is no more than `ulimit -Hs` says (a plain `ulimit -s` in a
// shell sets it), and where that leaves no more than the stack the process already has, the program stays on it.
namespace {
struct MainStackEntry {
    int (*body)(void*);
    void* arg;
    int result = 0;
    std::exception_ptr error;
    ucontext_t back;
};
void enter_main_stack(unsigned low, unsigned high) {
    auto* entry = reinterpret_cast<MainStackEntry*>((static_cast<std::uintptr_t>(high) << 32) | low);
    try {
        entry->result = entry->body(entry->arg);
    } catch (...) {
        entry->error = std::current_exception();   // nothing unwinds past the first frame of a made stack
    }
    // Going back restores the signal mask the first stack was left with. The mask is the program's to set: what it blocked
    // stays blocked on the process's way out (a SIGINT it left pending must not arrive there), so the mask to go back to
    // is the one it has now
    pthread_sigmask(SIG_SETMASK, nullptr, &entry->back.uc_sigmask);
}
}  // namespace
void set_main_stack_mib(std::size_t mib) {       // the build keeps the policy's number to 1 TiB; no number may wrap here (RL-885)
    constexpr std::size_t most = std::numeric_limits<std::size_t>::max() >> 20;
    wanted_main_stack() = std::min(mib, most) << 20;
}
int on_main_stack(int (*body)(void*), void* arg) {
#if defined(__SANITIZE_ADDRESS__)
    return body(arg);                            // a sanitizer keeps its own account of the stack it started on
#else
    std::size_t want = wanted_main_stack();
    rlimit limit{};
    if (getrlimit(RLIMIT_STACK, &limit) == 0 && limit.rlim_max != RLIM_INFINITY) want = std::min<std::size_t>(want, limit.rlim_max);
    void* have_low = nullptr;
    std::size_t have = 0;
    if (!process_stack(have_low, have) || want <= have) return body(arg);
    const std::size_t page = static_cast<std::size_t>(sysconf(_SC_PAGESIZE));
    want = (want + page - 1) / page * page;
    const std::size_t guard = std::size_t{1} << 20;   // below the stack, never readable: what runs past the watch ends there
    void* region = mmap(nullptr, guard + want, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE | MAP_STACK, -1, 0);
    if (region == MAP_FAILED) return body(arg);  // no address space for it: the stack the process has
    void* low = static_cast<char*>(region) + guard;
    MainStackEntry entry{body, arg, 0, nullptr, {}};
    ucontext_t there;
    if (mprotect(low, want, PROT_READ | PROT_WRITE) != 0 || getcontext(&there) != 0) {
        munmap(region, guard + want);
        return body(arg);
    }
    there.uc_stack.ss_sp = low;
    there.uc_stack.ss_size = want;
    there.uc_link = &entry.back;
    auto at = reinterpret_cast<std::uintptr_t>(&entry);
    makecontext(&there, reinterpret_cast<void (*)()>(enter_main_stack), 2, static_cast<unsigned>(at), static_cast<unsigned>(at >> 32));
    program_stack() = {low, want};
    swapcontext(&entry.back, &there);            // returns when the program has returned
    program_stack() = {};
    measure_native_stack();                      // what runs after the program (the process's way out) is on the first stack again
    munmap(region, guard + want);
    if (entry.error) std::rethrow_exception(entry.error);
    return entry.result;
#endif
}
void native_stack_overflow(const char* where) {   // _Py_CheckRecursiveCall's words
    const char* here = static_cast<const char*>(__builtin_frame_address(0));
    long used = native_stack_top() != nullptr ? static_cast<long>((native_stack_top() - here) / 1024) : 0;
    raise_new("RecursionError", "Stack overflow (used " + std::to_string(used) + " kB)" + where);
}

std::int64_t tuple_hash(const Tuple* t) {
    // tuplehash: xxHash's mixing, as Objects/tupleobject.c, and kept in the tuple once it is known (ob_hash). An item whose
    // __hash__ raises leaves nothing kept: the next call asks every item again
    if (t->hash != -1) return t->hash;
    check_native_stack(" while hashing a tuple");   // tuple_hash's _Py_EnterRecursiveCall: an item may be a tuple, and so on down
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
    if (acc == static_cast<std::uint64_t>(-1)) acc = 1546275796;
    t->hash = static_cast<std::int64_t>(acc);
    return t->hash;
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
    if (is_exact_str(a) && is_exact_str(b)) return name_arg(a)->text == name_arg(b)->text;   // unicode_eq; a subclass's __eq__ may have a say
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

// A class's module as type_module answers it: its dict's entry, or, for a static type, which has none, its tp_name's
// prefix ("" where there is neither)
std::string module_text(const ClassObject* c) {
    if (const Obj* mod = c->attrs.find(intern("__module__")))
        if (const Str* ms = as_str(*mod)) return ms->text;
    if (c_type(c)) return c->name_prefix > 0 ? c->name.substr(0, c->name_prefix - 1) : "builtins";
    return {};
}
std::string fully_qualified_name(const ClassObject* c) {
    std::string module = module_text(c);
    if (!module.empty() && module != "builtins" && module != "__main__") return module + "." + c->qualname;
    return c->qualname;
}
namespace {
std::int64_t container_hash(Obj key, const char* as) {
    try {
        return hash_of(key);
    } catch (const PyError& e) {
        if (type_of(e.exc.get()) != exception_class("TypeError")) rethrow(e);
        Ref text = str_of(e.exc.get());
        raise_new("TypeError", "cannot use '" + fully_qualified_name(type_of(key)) + "' as a " + as + " (" +
                                   name_arg(text.get())->text + ")");
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
        ClassObject* c = make_class({.name = name, .bases = bases, .native = std::move(native), .static_type = true});
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
            if (std::string_view(n) == "SyntaxError") own = exception_fields({"msg", "filename", "lineno", "offset", "end_lineno", "end_offset", "text", "print_file_and_line", "_metadata"});   // SyntaxError_clear's order (RL-827)
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
// The exception's own field, as the C reads its struct: a slot a deriving class has under the name is another cell (RL-564)
Obj exception_field(Obj exc, const char* name) { return slot_cell(static_cast<Instance*>(exc.object()), nullptr, intern(name)); }
void set_exception_field(Obj exc, const char* name, Obj value) {
    incref(value);
    decref(std::exchange(slot_cell(static_cast<Instance*>(exc.object()), nullptr, intern(name)), value));
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

void reraise_as_is(Obj exc) {                    // RERAISE of a value: no context taken, no entry for this frame
    throw PyError{Ref::share(exc), detail::BARE_RAISE};
}

Ref handled_exception() {                        // sys.exception(): the exception being handled, None for none
    return handled().empty() ? none_ref() : Ref::share(handled().back());
}

void set_handled_exception(Obj exc) {             // PyErr_SetHandledException: the innermost handler's exception replaced
    if (handled().empty()) return;
    incref(exc);
    Obj old = std::exchange(handled().back(), exc);
    decref(old);
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

bool is_subclass(ClassObject* c, ClassObject* base) {   // PyType_IsSubtype: is_subtype_with_mro
    if (c->mro.empty()) [[unlikely]] {           // no tp_mro yet, while a metaclass's mro() runs (RL-940): the tp_base chain
        for (ClassObject* a = c; a != types().object; a = best_base_of(a))   // (type_is_subtype_base_chain)
            if (a == base) return true;
        return base == types().object;
    }
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
        raise_new("TypeError", "calling " + name_arg(shown.get())->text + " should have returned an instance of BaseException, not " +
                                   name_arg(got.get())->text);
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

void check_except_type_valid(Obj spec) {         // _PyEval_CheckExceptTypeValid: a class, or a tuple whose items each are one
    static const char* const CANNOT_CATCH = "catching classes that do not inherit from BaseException is not allowed";
    if (is_kind(spec, Kind::Tuple)) {
        for (Obj s : static_cast<Tuple*>(spec.object())->items)
            if (!is_exception_class(s)) raise_new("TypeError", CANNOT_CATCH);
        return;
    }
    if (!is_exception_class(spec)) raise_new("TypeError", CANNOT_CATCH);
}

bool exception_matches(Obj exc, Obj spec) {
    // CHECK_EXC_MATCH: the clause's types are checked before any is matched (_PyEval_CheckExceptTypeValid), then
    // PyErr_GivenExceptionMatches
    check_except_type_valid(spec);
    if (is_kind(spec, Kind::Tuple)) {
        for (Obj s : static_cast<Tuple*>(spec.object())->items)
            if (is_subclass(type_of(exc), static_cast<ClassObject*>(s.object()))) return true;
        return false;
    }
    return is_subclass(type_of(exc), static_cast<ClassObject*>(spec.object()));
}

Obj traceback_of(Obj exc) { return is_exception_instance(exc) ? exception_field(exc, "__traceback__") : Obj{}; }

namespace {
std::uint64_t frame_ids = 0;                     // a frame's id, given on its first record: never reused

// an entry for frame `f` at its line now, `next` deeper: it holds the frame's frame object (PyTraceBack_Here, tb_create_raw)
Ref make_entry(detail::FrameRecord& f, Ref next) {
    if (f.id == 0) f.id = ++frame_ids;
    Ref held = own(new Traceback(f.code, f.line, std::move(next)));
    auto* tb = static_cast<Traceback*>(held.get().object());
    tb->frame = f.id;
    tb->frame_obj = Ref::share(detail::frame_object(f));
    if (f.module != nullptr) tb->module = GlobalsRef(f.module);
    return held;
}
// prepends the frame's entry to exc's traceback, as PyTraceBack_Here does
void add_entry(Obj exc, detail::FrameRecord& f) {
    Obj prev = traceback_of(exc);
    Ref held = make_entry(f, Ref::share(prev.is_unset() ? None() : prev));
    set_exception_field(exc, "__traceback__", held.get());
}
}  // namespace

Obj detail::frame_object(FrameRecord& f) {
    if (f.frame_obj.get().is_unset()) f.frame_obj = own(new FrameObject(f.code, f.module));
    return f.frame_obj.get();
}

void traceback_from_current_frame(Obj exc) {     // _PyTraceBack_FromFrame(NULL, f) as exc's traceback: one entry, the frame's line now
    detail::FrameRecord* f = detail::current_frame();
    if (f == nullptr) return;
    Ref held = make_entry(*f, none_ref());
    set_exception_field(exc, "__traceback__", held.get());
}

void detail::arrive(FrameRecord& f, PyError& e) noexcept {
    try {
        if (!f.code->shown) {                    // no frame in CPython: the caller records the call
            e.recorded = 0;
            return;
        }
        if (f.id == 0) f.id = ++frame_ids;
        if (e.recorded == f.id) return;          // re-raised by this frame
        if (e.recorded != BARE_RAISE && is_kind(e.exc.get(), Kind::Instance)) add_entry(e.exc.get(), f);
        e.recorded = f.id;
    } catch (...) {
        // a frame record that cannot be made loses the entry, never the exception
    }
}

void detail::record_frame(FrameRecord& f) noexcept {
    try {
        Obj exc = raising();
        auto* err = static_cast<PyError*>(const_cast<void*>(raising_owner()));
        if (!is_kind(exc, Kind::Instance) || err == nullptr) return;
        std::uint64_t rec = err->recorded;
        err->recorded = 0;                       // the caller records the call
        if (!f.code->shown) return;
        // recorded at one of this frame's catches, or re-raised bare: its entry is in the traceback already (or in the one of
        // the error this one was made of: PEP 479's RuntimeError, whose StopIteration has the generator's; RL-876)
        if (rec == BARE_RAISE || (f.id != 0 && rec == f.id)) return;
        add_entry(exc, f);
    } catch (...) {
        // a frame record that cannot be made loses the entry, never the exception
    }
}

// frame_tp_clear's loop: each slot from the top cleared in place, its value released before the next is cleared, so a
// finaliser one of them runs still finds the slots below it (a suggestion reads them) and a clear it starts releases them;
// the stack pointer goes down after the loop, then f_locals (RL-917)
void detail::clear_frame_values(FrameObject* f) noexcept {
    for (std::size_t i = f->values.size(); i-- > 0;) {
        if (i >= f->values.size()) continue;     // a clear the finaliser started has taken the rest already
        Ref value = std::move(f->values[i]);
    }
    f->values.clear();
    Ref ns = std::move(f->ns);
}

void detail::take_ownership(FrameObject* f, Ref* const* values, std::size_t n, Obj ns, FrameRecord* back) noexcept {
    try {
        f->values.reserve(f->values.size() + n);
    } catch (...) {
        return;                                  // no room: the values die where they are, as they would with no frame object
    }
    for (std::size_t i = 0; i < n; ++i) f->values.push_back(std::move(*values[i]));
    if (!ns.is_unset()) f->ns = Ref::share(ns);
    f->owned = true;
    if (back != nullptr) {
        try {
            f->back = Ref::share(frame_object(*back));
        } catch (...) {
            // "Memory error here. Nothing we can do about it"
        }
    }
}

// _PyFrame_ClearExceptCode for a frame that has a frame object: one held by nothing else dies first, and the frame's values
// then die where they are (_PyFrame_ClearLocals, the variables' destructors); one held by something else (a traceback's entry,
// a frame object of a frame this one called, as f_back) takes them, and f_back is the caller's. A generator's resume that ends
// at a yield hands the frame on (clear_gen_frame comes only at its end); the generator's slots after its variables die with
// clear_frame (an exception that leaves has popped them, and a return has none). A generator's frame has no f_back:
// clear_gen_frame sets frame->previous to NULL before it clears the frame, so take_ownership finds no frame before it (RL-912)
void detail::frame_ends(FrameRecord& f, Ref* const* locals, std::size_t n, bool unwinding) noexcept {
    if (f.resumed != nullptr) {
        f.resumed->id = f.id;
        if (!unwinding && *f.resumed_pc != GEN_RETURNED) {
            f.resumed->frame_obj = std::move(f.frame_obj);
            return;
        }
    }
    if (f.frame_obj.get().is_unset()) return;
    Ref held = std::move(f.frame_obj);
    if (held.get().object()->refs > 1) {
        // f_locals: a class body's namespace, or the locals a staged text's top level ran with, which only its record held
        // (RL-945); a module's frame has its globals for locals, which its frame object holds as its globals already
        Obj ns = f.ns;
        if (ns.is_unset() && f.module != nullptr && f.module->locals != nullptr && std::string_view(f.code->name) == "<module>")
            ns = Obj::of(f.module->locals);
        take_ownership(static_cast<FrameObject*>(held.get().object()), locals, n, ns, f.resumed != nullptr ? nullptr : f.caller);
    }
}

}  // namespace bella
