// runtime/src/types.cpp -- classes (bella/runtime.hpp): the builtin types' attributes as getset
// and method descriptors, type.__new__ and calling a class, attribute access on classes and on the
// C++ types' objects, and special-method dispatch. CPython's Objects/typeobject.c is the reference
// for each rule; the order of effects follows it.
#include "bella/runtime.hpp"

#include <algorithm>
#include <cctype>

namespace bella {

Obj type_lookup(ClassObject* c, const Str* name) {
    auto hit = c->lookup(name);
    return hit ? hit->first : Obj{};
}
bool isinstance(Obj v, ClassObject* c) { return is_subclass(type_of(v), c); }

namespace {
const Str* N(const char* s) { return intern(s); }
GetSet* instance_dict_getset();
bool is_none(Obj v) { return v == None(); }

ClassObject* as_class(Obj v);
ClassObject* tp_base(ClassObject* c);

// tp_new_wrapper's checks of T.__new__(cls, ...) (Objects/typeobject.c): the class it is given
ClassObject* new_wrapper_class(Args a, const ClassObject* type) {
    if (a.npos < 1) raise_new("TypeError", type->name + ".__new__(): not enough arguments");
    ClassObject* sub = as_class(a.pos(0));
    if (sub == nullptr)
        raise_new("TypeError", type->name + ".__new__(X): X is not a type object (" + type_of(a.pos(0))->name + ")");
    if (!is_subclass(sub, const_cast<ClassObject*>(type)))
        raise_new("TypeError", type->name + ".__new__(" + sub->name + "): " + sub->name + " is not a subtype of " + type->name);
    return sub;
}

void method(ClassObject* c, const char* name, NativeFn fn, Binding b = Binding::Method) {
    auto* f = new Builtin(name, fn, Obj{}, b);
    f->owner = c;
    f->flags |= IMMORTAL;                        // owned by the type, which lives as long as the program
    c->attrs.set(N(name), Obj::of(f));
}
void getset(ClassObject* c, const char* name, Ref (*g)(Obj), void (*s)(Obj, Obj) = nullptr) {
    c->attrs.set(N(name), Obj::of(new GetSet(name, c, g, s)));
}
void value(ClassObject* c, const char* name, Obj v) {
    incref(v);
    Obj old = c->attrs.set(N(name), v);
    decref(old);
}
ClassObject* as_class(Obj v) { return is_kind(v, Kind::Class) ? static_cast<ClassObject*>(v.object()) : nullptr; }

std::vector<Obj> with_first(Obj first, Args a) {
    std::vector<Obj> data;
    data.reserve(a.npos + a.nkw + 1);
    data.push_back(first);
    for (std::size_t i = 0; i < a.npos + a.nkw; ++i) data.push_back(a.data[i]);
    return data;
}
Ref call_with_first(Obj f, Obj first, Args a) {
    auto data = with_first(first, a);
    return invoke(f, Args{data.data(), a.npos + 1, a.kwnames, a.nkw});
}
Args rest(Args a) { return Args{a.data + 1, a.npos - 1, a.kwnames, a.nkw}; }
bool callable_check(Obj v) {
    if (!v.is_object()) return false;
    Kind k = v.object()->kind;
    return k == Kind::PyFunction || k == Kind::Builtin || k == Kind::Method || k == Kind::Class || k == Kind::Function ||
           !type_lookup(type_of(v), intern("__call__")).is_unset();
}
void no_keywords(Args a, const char* who) {
    if (a.nkw != 0) raise_new("TypeError", std::string(who) + " takes no keyword arguments");
}
void arity(Args a, const char* who, std::size_t lo, std::size_t hi) {
    no_keywords(a, who);
    if (a.npos < lo || a.npos > hi) {
        std::string n = lo == hi ? std::to_string(lo) : "from " + std::to_string(lo) + " to " + std::to_string(hi);
        raise_new("TypeError", std::string(who) + " expected " + n + " argument" + (hi == 1 ? "" : "s") + ", got " +
                                   std::to_string(a.npos));
    }
}
}  // namespace

// ---- descriptors ----
// type(found).__get__(found, obj, type), with the C++ descriptors' own rules inline; obj is None
// when the attribute is read from the class
ClassObject* observed_type(Obj v) {
    if (is_kind(v, Kind::Builtin)) {
        auto* b = static_cast<Builtin*>(v.object());
        if (b->owner != nullptr && cpython_attribute_kind(b->owner, b->name) == "wrapper_descriptor")
            throw NotImplemented("the type of " + b->owner->name + "." + b->name + ", a slot wrapper in CPython");
    }
    return type_of(v);
}

Ref descr_get(Obj found, Obj obj, Obj type) {
    if (found.is_object()) {
        Object* o = found.object();
        switch (o->kind) {
            case Kind::PyFunction:
                return is_none(obj) || presents_as_builtin(found) ? Ref::share(found) : own(new Method(found, obj));
            case Kind::Builtin: {
                auto* b = static_cast<Builtin*>(o);
                if (!b->self.is_unset() || b->binding == Binding::Function) return Ref::share(found);
                Ref bound;
                if (b->binding == Binding::ClassMethod) {
                    bound = own(new Builtin(b->name, b->fn, is_none(type) ? Obj::of(type_of(obj)) : type));
                } else {
                    if (is_none(obj)) return Ref::share(found);
                    if (b->owner != nullptr && !isinstance(obj, b->owner))       // method_check (A9-2)
                        raise_new("TypeError", "descriptor '" + b->name + "' for '" + b->owner->name + "' objects doesn't apply to a '" +
                                                   type_of(obj)->name + "' object");
                    bound = own(new Builtin(b->name, b->fn, obj));
                }
                static_cast<Builtin*>(bound.get().object())->owner = b->owner;   // how it presents itself
                return bound;
            }
            case Kind::GetSet: {
                auto* g = static_cast<GetSet*>(o);
                if (is_none(obj)) return Ref::share(found);
                if (!isinstance(obj, g->owner))
                    raise_new("TypeError", std::string("descriptor '") + g->name + "' for '" + g->owner->name +
                                               "' objects doesn't apply to a '" + type_of(obj)->name + "' object");
                return g->get(obj);
            }
            default:
                break;
        }
    }
    if (found.is_small()) return Ref::share(found);
    Obj get = type_lookup(type_of(found), N("__get__"));
    if (get.is_unset()) return Ref::share(found);
    return invoke(get, {found, obj, type});
}

namespace {
Ref get_native(Obj self, Args a) {             // __get__ of the C++ descriptors
    arity(a, "__get__", 1, 2);
    Obj obj = a.pos(0);
    Obj type = a.npos > 1 ? a.pos(1) : None();
    if (is_none(obj) && is_none(type)) raise_new("TypeError", "__get__(None, None) is invalid");
    return descr_get(self, obj, type);
}
Ref getset_set(Obj self, Args a) {
    arity(a, "__set__", 2, 2);
    auto* g = static_cast<GetSet*>(self.object());
    if (g->set == nullptr)
        raise_new("AttributeError", std::string("attribute '") + g->name + "' of '" + g->owner->name + "' objects is not writable");
    g->set(a.pos(0), a.pos(1));
    return none_ref();
}
Ref getset_delete(Obj self, Args a) {
    arity(a, "__delete__", 1, 1);
    auto* g = static_cast<GetSet*>(self.object());
    if (g->deletable) {
        g->set(a.pos(0), Obj{});
        return none_ref();
    }
    raise_new("AttributeError", std::string("cannot delete attribute '") + g->name + "' of '" + g->owner->name + "' objects");
}
}  // namespace

// ---- attribute errors carry name and obj (CPython 3.10+) ----
void raise_attribute_error(Obj obj, const Str* name, const std::string& message) {
    Ref exc = invoke(Obj::of(exception_class("AttributeError")), {str_new(message).get()});
    set_exception_field(exc.get(), "name", Obj::of(name));
    set_exception_field(exc.get(), "obj", obj);
    raise(exc.get());
}

// ---- attribute access on classes (type_getattro) ----
Ref type_getattr(ClassObject* cls, const Str* name) {
    ClassObject* meta = type_of(Obj::of(cls));
    Obj meta_attr = type_lookup(meta, name);
    if (!meta_attr.is_unset() && is_data_descriptor(meta_attr)) return descr_get(meta_attr, Obj::of(cls), Obj::of(meta));
    Obj attr = type_lookup(cls, name);
    if (!attr.is_unset()) {
        Ref hold = Ref::share(attr);
        return descr_get(attr, None(), Obj::of(cls));
    }
    if (!meta_attr.is_unset()) return descr_get(meta_attr, Obj::of(cls), Obj::of(meta));
    refuse_absent_attribute(Obj::of(cls), name);
    // a metaclass's __getattr__ (slot_tp_getattr_hook): after type.__getattribute__ found nothing
    if (meta->heap_type)
        if (Obj hook = type_lookup(meta, N("__getattr__")); !hook.is_unset()) {
            Ref h = Ref::share(hook);
            Ref bound = descr_get(h.get(), Obj::of(cls), Obj::of(meta));
            return invoke(bound.get(), {Obj::of(name)});
        }
    raise_attribute_error(Obj::of(cls), name, "type object '" + cls->name + "' has no attribute '" + name->text + "'");
}

namespace {
Obj type_method(const char* name) { return type_lookup(types().type, N(name)); }
// a metaclass's own __setattr__ or __delattr__ (one that is not type's): it decides
bool meta_overrides(ClassObject* meta, const char* name) {
    return meta->heap_type && type_lookup(meta, N(name)) != type_method(name);
}
// a data descriptor of the metaclass sets or deletes (PyObject_GenericSetAttr's first step)
bool meta_descriptor_store(ClassObject* cls, const Str* name, Obj value) {
    ClassObject* meta = type_of(Obj::of(cls));
    Obj meta_attr = type_lookup(meta, name);
    if (meta_attr.is_unset()) return false;
    if (is_kind(meta_attr, Kind::GetSet)) {
        auto* g = static_cast<GetSet*>(meta_attr.object());
        if (g->set == nullptr || (value.is_unset() && !g->deletable))
            raise_new("AttributeError", std::string("attribute '") + g->name + "' of 'type' objects is not writable");
        g->set(Obj::of(cls), value);
        return true;
    }
    if (!is_data_descriptor(meta_attr)) return false;
    Ref desc = Ref::share(meta_attr);
    Obj f = type_lookup(type_of(meta_attr), N(value.is_unset() ? "__delete__" : "__set__"));
    if (f.is_unset()) raise_new("AttributeError", value.is_unset() ? "__delete__" : "__set__");
    if (value.is_unset()) invoke(f, {desc.get(), Obj::of(cls)});
    else invoke(f, {desc.get(), Obj::of(cls), value});
    return true;
}
}  // namespace

// type.__setattr__ (type_setattro): a metaclass's data descriptor, else the class's own dict
void type_setattr_generic(ClassObject* cls, const Str* name, Obj value) {
    if (meta_descriptor_store(cls, name, value)) return;
    if (type_lookup(type_of(Obj::of(cls)), name).is_unset()) refuse_absent_data_descriptor(Obj::of(cls), name);
    if (immutable_type(cls))
        raise_new("TypeError", "cannot set '" + name->text + "' attribute of immutable type '" + cls->name + "'");
    cls->set_attr(name, value);                  // the new version before the old value dies (type_setattro)
}
void type_setattr(ClassObject* cls, const Str* name, Obj value) {
    ClassObject* meta = type_of(Obj::of(cls));
    if (meta_overrides(meta, "__setattr__")) {
        call_special(Obj::of(cls), "__setattr__", {Obj::of(name), value});
        return;
    }
    type_setattr_generic(cls, name, value);
}

void type_delattr_generic(ClassObject* cls, const Str* name) {
    if (meta_descriptor_store(cls, name, Obj{})) return;
    if (type_lookup(type_of(Obj::of(cls)), name).is_unset()) refuse_absent_data_descriptor(Obj::of(cls), name);
    if (immutable_type(cls))
        raise_new("TypeError", "cannot delete '" + name->text + "' attribute of immutable type '" + cls->name + "'");
    if (!cls->attrs.contains(name))
        raise_attribute_error(Obj::of(cls), name, "type object '" + cls->name + "' has no attribute '" + name->text + "'");
    cls->del_attr(name);
}
void type_delattr(ClassObject* cls, const Str* name) {
    if (meta_overrides(type_of(Obj::of(cls)), "__delattr__")) {
        call_special(Obj::of(cls), "__delattr__", {Obj::of(name)});
        return;
    }
    type_delattr_generic(cls, name);
}

// ---- attribute access on the C++ types' objects (PyObject_GenericGetAttr) ----
Ref generic_getattr(Obj obj, const Str* name) {
    ClassObject* c = type_of(obj);
    Obj found = type_lookup(c, name);
    if (!found.is_unset() && is_data_descriptor(found)) return descr_get(found, obj, Obj::of(c));
    if (is_kind(obj, Kind::Module)) {
        Obj v = dict_get(static_cast<Module*>(obj.object())->dict, Obj::of(name));
        if (!v.is_unset()) return Ref::share(v);
    }
    if (is_kind(obj, Kind::PyFunction) && !presents_as_builtin(obj)) {
        auto* f = static_cast<PyFunction*>(obj.object());
        if (!f->dict.get().is_unset()) {
            Obj v = dict_get(static_cast<Dict*>(f->dict.get().object()), Obj::of(name));
            if (!v.is_unset()) return Ref::share(v);
        }
    }
    if (!found.is_unset()) return descr_get(found, obj, Obj::of(c));
    if (is_kind(obj, Kind::Method))                  // method_getattro: the function's attributes
        return getattr(static_cast<Method*>(obj.object())->func, name);
    refuse_absent_attribute(obj, name);
    if (is_kind(obj, Kind::Module))
        raise_attribute_error(obj, name, "module '" + as_str(static_cast<Module*>(obj.object())->name.get())->text +
                                             "' has no attribute '" + name->text + "'");
    raise_attribute_error(obj, name, "'" + c->name + "' object has no attribute '" + name->text + "'");
}

// ---- special methods ----
Ref call_special(Obj v, const char* name, std::initializer_list<Obj> args, bool* found) {
    Obj f = type_lookup(type_of(v), N(name));
    if (found != nullptr) *found = !f.is_unset();
    if (f.is_unset()) return Ref{};
    std::vector<Obj> data{v};
    data.insert(data.end(), args.begin(), args.end());
    Ref hold = Ref::share(f);                    // the method may be replaced while it runs
    if ((is_kind(f, Kind::PyFunction) && !presents_as_builtin(f)) || (is_kind(f, Kind::Builtin) && static_cast<Builtin*>(f.object())->self.is_unset() &&
                                         static_cast<Builtin*>(f.object())->binding == Binding::Method))
        return invoke(f, Args{data.data(), data.size(), nullptr, 0});
    Ref bound = descr_get(f, v, Obj::of(type_of(v)));
    return invoke(bound.get(), Args{data.data() + 1, data.size() - 1, nullptr, 0});
}

// ---- calling a class (type_call), object.__new__ and object.__init__ ----
namespace {
Obj object_new_fn() { return type_lookup(types().object, N("__new__")); }
Obj object_init_fn() { return type_lookup(types().object, N("__init__")); }

// A built-in type the runtime cannot construct yet: CPython constructs it (its own __new__), or
// says "cannot create"; either way object.__new__ is not the answer (RL-220).
[[noreturn]] void refuse_construction(const ClassObject* cls) {
    throw NotImplemented("creating an instance of the built-in type '" + cls->name + "'" +
                         (cpython_attribute_kind(cls, "__new__").empty() ? "" : " (CPython has it; the runtime does not yet)"));
}

// solid_base and best_base (Objects/typeobject.c): the layout a class extends is the nearest class
// with a shape of its own (slots, or a built-in's data); tp_base is the base whose solid base is the
// most derived of the bases'
ClassObject* solid_base(ClassObject* c) {
    if (c == types().object) return c;
    bool own_shape = (!c->heap_type) || !c->own_slot_names().empty();
    if (own_shape) return c;
    return solid_base(c->bases.empty() ? types().object : tp_base(c));
}
ClassObject* tp_base(ClassObject* c) {
    ClassObject *base = nullptr, *winner = nullptr;
    for (ClassObject* b : c->bases) {
        ClassObject* s = solid_base(b);
        if (winner == nullptr || is_subclass(s, winner)) {
            winner = s;
            base = b;
        }
    }
    return base != nullptr ? base : types().object;
}

Ref object_new(Obj, Args a) {
    if (a.npos < 1) raise_new("TypeError", "object.__new__(): not enough arguments");
    ClassObject* cls = as_class(a.pos(0));
    if (cls == nullptr) raise_new("TypeError", "object.__new__(X): X is not a type object (" + type_of(a.pos(0))->name + ")");
    if (!cls->heap_type && cls != types().object) {         // tp_new_wrapper's check, before the arguments'
        if (cpython_attribute_kind(cls, "__new__").empty()) refuse_construction(cls);
        raise_new("TypeError", "object.__new__(" + cls->name + ") is not safe, use " + cls->name + ".__new__()");
    }
    if (is_subclass(cls, types().dict) || is_subclass(cls, types().int_)) {   // a built-in base makes it
        // tp_new_wrapper's staticbase: past the classes whose __new__ is Python's (slot_tp_new)
        ClassObject* staticbase = cls;
        while (!is_kind(type_lookup(staticbase, N("__new__")), Kind::Builtin) && !staticbase->bases.empty())
            staticbase = tp_base(staticbase);
        raise_new("TypeError", "object.__new__(" + cls->name + ") is not safe, use " + staticbase->name + ".__new__()");
    }
    bool excess = a.npos > 1 || a.nkw > 0;
    if (excess) {
        if (type_lookup(cls, N("__new__")) != object_new_fn())
            raise_new("TypeError", "object.__new__() takes exactly one argument (the type to instantiate)");
        if (type_lookup(cls, N("__init__")) == object_init_fn()) raise_new("TypeError", cls->name + "() takes no arguments");
    }
    if (cls->abstract) {                          // "', '".join(sorted(cls.__abstractmethods__))
        const Obj* methods = cls->attrs.find(N("__abstractmethods__"));
        if (methods == nullptr) raise_attribute_error(Obj::of(cls), N("__abstractmethods__"), "__abstractmethods__");
        std::vector<std::string> names;
        Ref it = iter(*methods);
        for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get())) {
            const Str* n = as_str(v.get());
            if (n == nullptr) throw NotImplemented("sorting abstract methods that are not all str");
            names.push_back(n->text);
        }
        std::sort(names.begin(), names.end());       // code point order: the UTF-8 bytes' order
        std::string joined;
        for (const auto& n : names) joined += (joined.empty() ? "" : "', '") + n;
        raise_new("TypeError", "Can't instantiate abstract class " + cls->name + " without an implementation for abstract method" +
                                   (names.size() > 1 ? "s" : "") + " '" + joined + "'");
    }
    if (cls->has("__getattribute__") && type_lookup(cls, N("__getattribute__")) != type_lookup(types().object, N("__getattribute__")))
        throw NotImplemented("[P2+] a class that overrides __getattribute__ (spec section 3)");
    return own(new_instance(cls));
}

Ref object_init(Obj self, Args a) {
    if (a.npos > 0 || a.nkw > 0) {
        ClassObject* cls = type_of(self);
        if (type_lookup(cls, N("__init__")) != object_init_fn())
            raise_new("TypeError", "object.__init__() takes exactly one argument (the instance to initialize)");
        if (type_lookup(cls, N("__new__")) == object_new_fn())
            raise_new("TypeError", cls->name + ".__init__() takes exactly one argument (the instance to initialize)");
    }
    return none_ref();
}
}  // namespace

Ref type_call(ClassObject* cls, Args a) {
    if (cls == types().type && a.npos == 1 && a.nkw == 0) return Ref::share(Obj::of(observed_type(a.pos(0))));
    if (cls == types().super_) return super_call(a);                  // super's own vectorcall
    Obj new_attr = type_lookup(cls, N("__new__"));
    if (new_attr.is_unset()) raise_new("TypeError", "cannot create '" + cls->name + "' instances");
    if (new_attr == object_new_fn() && !cls->heap_type && cls != types().object) refuse_construction(cls);
    Ref new_fn = descr_get(new_attr, None(), Obj::of(cls));
    Ref obj = call_with_first(new_fn.get(), Obj::of(cls), a);
    if (!isinstance(obj.get(), cls)) return obj;
    ClassObject* t = type_of(obj.get());
    Obj init = type_lookup(t, N("__init__"));
    if (!init.is_unset()) {
        Ref result;
        if ((is_kind(init, Kind::PyFunction) && !presents_as_builtin(init)) || is_kind(init, Kind::Builtin)) {
            Ref hold = Ref::share(init);
            result = is_kind(init, Kind::Builtin) && static_cast<Builtin*>(init.object())->binding == Binding::Method
                         ? static_cast<Builtin*>(init.object())->fn(obj.get(), a)
                         : call_with_first(init, obj.get(), a);
        } else {
            Ref bound = descr_get(init, obj.get(), Obj::of(t));
            result = invoke(bound.get(), a);
        }
        if (!is_none(result.get()))
            raise_new("TypeError", "__init__() should return None, not '" + type_of(result.get())->name + "'");
    }
    return obj;
}

// ---- type.__new__ (type_new_impl) ----
namespace {
std::string mangle(const std::string& cls, const std::string& name) {
    if (name.size() < 2 || name.compare(0, 2, "__") != 0 || (name.size() >= 4 && name.compare(name.size() - 2, 2, "__") == 0) ||
        name.find('.') != std::string::npos)
        return name;
    std::size_t i = cls.find_first_not_of('_');
    if (i == std::string::npos) return name;
    return "_" + cls.substr(i) + name;
}

Ref type_new(ClassObject* meta, Obj name_obj, Obj bases_obj, Obj ns_obj, Args kw) {
    const Str* name = as_str(name_obj);
    if (name == nullptr) raise_new("TypeError", "type.__new__() argument 1 must be str, not " + type_of(name_obj)->name);
    if (!is_kind(bases_obj, Kind::Tuple))
        raise_new("TypeError", "type.__new__() argument 2 must be tuple, not " + type_of(bases_obj)->name);
    if (!is_kind(ns_obj, Kind::Dict))
        raise_new("TypeError", "type.__new__() argument 3 must be dict, not " + type_of(ns_obj)->name);
    std::vector<ClassObject*> bases;
    for (Obj b : static_cast<Tuple*>(bases_obj.object())->items) {
        ClassObject* bc = as_class(b);
        if (bc == nullptr) raise_new("TypeError", "bases must be types");
        if (std::find(bases.begin(), bases.end(), bc) != bases.end())       // A9-9
            raise_new("TypeError", "duplicate base class " + bc->name);
        if (!bc->heap_type && bc != types().object && bc != types().type && bc != types().dict && bc != types().int_ &&
            !is_subclass(bc, exception_class("BaseException")))
            throw NotImplemented("subclassing the built-in type '" + bc->name + "'");
        bases.push_back(bc);
    }
    if (bases.empty()) bases.push_back(types().object);
    Ref ns_copy;
    if (is_subclass_instance(ns_obj)) ns_copy = dict_copy(static_cast<Dict*>(ns_obj.object()));   // type_new: PyDict_Copy
    auto* ns = static_cast<Dict*>((ns_copy.get().is_unset() ? ns_obj : ns_copy.get()).object());
    ClassSpec spec{.name = name->text, .bases = bases};
    std::string qualname = name->text;
    Obj classcell, classdictcell;
    std::vector<std::pair<const Str*, Obj>> entries;   // borrowed from ns, which outlives this call
    bool has_eq = false, has_hash = false;
    for (auto& e : ns->entries) {
        if (e.key.is_unset()) continue;
        const Str* k = as_str(e.key);
        if (k == nullptr) throw NotImplemented("a class namespace with a key that is not a str");
        if (k->text == "__qualname__") {
            const Str* q = as_str(e.value);
            if (q == nullptr) raise_new("TypeError", "type __qualname__ must be a str, not " + type_of(e.value)->name);
            qualname = q->text;
            continue;
        }
        if (k->text == "__classcell__") { classcell = e.value; continue; }
        if (k->text == "__classdictcell__") { classdictcell = e.value; continue; }
        has_eq |= k->text == "__eq__";
        has_hash |= k->text == "__hash__";
        entries.emplace_back(k, e.value);
    }
    // __slots__: a str or an iterable of str; private names mangled; __dict__ and __weakref__ special
    Obj slots_value = dict_get(ns, Obj::of(N("__slots__")));
    if (!slots_value.is_unset()) {
        std::vector<std::string> slots;
        std::vector<Ref> items;
        if (as_str(slots_value) != nullptr) items.push_back(Ref::share(slots_value));
        else {
            Ref it = iter(slots_value);
            for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get())) items.push_back(std::move(v));
        }
        // type_new_visit_slots: identifiers; __dict__ once and only where no base has a dict;
        // a repeated ordinary name is accepted (CPython makes it twice, the last one wins)
        bool base_dict = std::any_of(bases.begin(), bases.end(), [](ClassObject* b) { return b->has_dict; });
        for (Ref& item : items) {
            const Str* s = as_str(item.get());
            if (s == nullptr) raise_new("TypeError", "__slots__ items must be strings, not '" + type_of(item.get())->name + "'");
            if (!s->ascii) throw NotImplemented("a __slots__ name beyond ASCII (identifier rules need the Unicode database)");
            bool ident = !s->text.empty() && !std::isdigit(static_cast<unsigned char>(s->text[0])) &&
                         std::all_of(s->text.begin(), s->text.end(), [](char c) { return std::isalnum(static_cast<unsigned char>(c)) || c == '_'; });
            if (!ident) raise_new("TypeError", "__slots__ must be identifiers");
            if (s->text == "__weakref__") throw NotImplemented("__weakref__ in __slots__ (step 3c: weak references)");
            if (s->text == "__dict__") {
                if (base_dict || std::find(slots.begin(), slots.end(), "__dict__") != slots.end())
                    raise_new("TypeError", "__dict__ slot disallowed: we already got one");
                slots.push_back(s->text);
                continue;
            }
            std::string m = mangle(name->text, s->text);
            for (auto& [k, v] : entries)
                if (k->text == m) raise_new("ValueError", "'" + s->text + "' in __slots__ conflicts with class variable");
            if (std::find(slots.begin(), slots.end(), m) == slots.end()) slots.push_back(m);   // A9-18
        }
        // an int subclass's instances have a variable size: only __dict__ (and __weakref__) may be slots
        bool int_based = std::any_of(bases.begin(), bases.end(), [](ClassObject* b) { return is_subclass(b, types().int_); });
        if (int_based && std::any_of(slots.begin(), slots.end(), [](const std::string& n) { return n != "__dict__"; }))
            raise_new("TypeError", "arbitrary __slots__ not supported for subtype of 'int'");
        spec.slots = slots;
    }
    for (auto& [k, v] : entries) spec.attrs.emplace_back(k->text, v);
    if (Obj sa = dict_get(ns, Obj::of(N("__static_attributes__"))); is_kind(sa, Kind::Tuple))
        for (Obj s : static_cast<Tuple*>(sa.object())->items)
            if (const Str* t = as_str(s)) spec.static_attributes.push_back(t->text);
    // __new__ is a static method, __init_subclass__ and __class_getitem__ class methods
    std::vector<Ref> wrapped;                    // held until make_class takes its counts
    for (auto& [k, v] : spec.attrs) {
        const char* wrapper = k == "__new__" ? "staticmethod"
                              : k == "__init_subclass__" || k == "__class_getitem__" ? "classmethod" : nullptr;
        if (wrapper != nullptr && is_kind(v, Kind::PyFunction) && !presents_as_builtin(v)) {
            wrapped.push_back(invoke(builtin(wrapper).get(), {v}));
            v = wrapped.back().get();
        }
    }
    if (dict_get(ns, Obj::of(N("__doc__"))).is_unset()) spec.attrs.emplace_back("__doc__", None());
    if (has_eq && !has_hash) spec.attrs.emplace_back("__hash__", None());
    ClassObject* c = nullptr;
    try {
        c = make_class(spec);
    } catch (const bella::TypeError&) {                     // the C3 merge failed (A9-9)
        std::string names;
        for (ClassObject* b : bases) names += (names.empty() ? "" : ", ") + b->name;
        raise_new("TypeError", "Cannot create a consistent method resolution order (MRO) for bases " + names);
    }
    c->cls = meta;
    c->qualname = qualname;
    c->heap_type = true;
    bool base_has_dict = std::any_of(bases.begin(), bases.end(), [](ClassObject* b) { return b->has_dict; });
    if (c->has_dict && !base_has_dict) c->attrs.set(N("__dict__"), Obj::of(instance_dict_getset()));
    if (!classcell.is_unset()) {
        if (!is_kind(classcell, Kind::Cell))
            raise_new("TypeError", "__classcell__ must be a nonlocal cell, not " + type_of(classcell)->name);
        auto* cell = static_cast<Cell*>(classcell.object());
        decref(std::exchange(cell->value, Obj::of(c)));
    }
    if (!classdictcell.is_unset() && is_kind(classdictcell, Kind::Cell)) {
        auto* cell = static_cast<Cell*>(classdictcell.object());
        Ref proxy = own(new Proxy(c));
        decref(std::exchange(cell->value, proxy.release()));
    }
    // __set_name__, in the order of the class's attributes
    for (auto& [k, v] : c->attrs.items()) {
        bool found = false;
        Ref hold = Ref::share(v);
        Ref r = call_special(v, "__set_name__", {Obj::of(c), Obj::of(k)}, &found);
    }
    // __init_subclass__ of the next class in the MRO, bound to the new class
    for (std::size_t i = 1; i < c->mro.size(); ++i) {
        Obj f = c->mro[i]->attrs.find(N("__init_subclass__")) ? *c->mro[i]->attrs.find(N("__init_subclass__")) : Obj{};
        if (f.is_unset()) continue;
        Ref bound = descr_get(f, None(), Obj::of(c));
        invoke(bound.get(), kw);
        break;
    }
    return Ref::share(Obj::of(c));
}

Ref type_new_builtin(Obj, Args a) {                 // type.__new__(meta, name, bases, ns, **kw)
    if (a.npos < 1) raise_new("TypeError", "type.__new__(): not enough arguments");
    ClassObject* meta = as_class(a.pos(0));
    if (meta == nullptr) raise_new("TypeError", "type.__new__(X): X is not a type object (" + type_of(a.pos(0))->name + ")");
    if (!is_subclass(meta, types().type))
        raise_new("TypeError", "type.__new__(" + meta->name + "): " + meta->name + " is not a subtype of type");
    if (a.npos == 2 && meta == types().type && a.nkw == 0) return Ref::share(Obj::of(type_of(a.pos(1))));
    if (a.npos != 4) raise_new("TypeError", "type.__new__() takes exactly 3 arguments (" + std::to_string(a.npos - 1) + " given)");
    if (!is_kind(a.pos(2), Kind::Tuple))
        raise_new("TypeError", "type.__new__() argument 2 must be tuple, not " + type_of(a.pos(2))->name);
    // _PyType_CalculateMetaclass: the most derived of meta and the bases' metaclasses; another
    // metaclass with a __new__ of its own makes the class instead (type_new_get_bases)
    ClassObject* winner = meta;
    for (Obj b : static_cast<Tuple*>(a.pos(2).object())->items) {
        ClassObject* t = type_of(b);
        if (is_subclass(winner, t)) continue;
        if (is_subclass(t, winner)) {
            winner = t;
            continue;
        }
        raise_new("TypeError", "metaclass conflict: the metaclass of a derived class must be a (non-strict) subclass "
                               "of the metaclasses of all its bases");
    }
    if (winner != meta) {
        Obj winner_new = type_lookup(winner, N("__new__"));
        if (winner_new != type_lookup(types().type, N("__new__"))) {
            std::vector<Obj> data{Obj::of(winner)};
            data.insert(data.end(), a.data + 1, a.data + a.npos + a.nkw);
            Ref f = descr_get(winner_new, None(), Obj::of(winner));
            return invoke(f.get(), Args{data.data(), a.npos, a.kwnames, a.nkw});
        }
        meta = winner;
    }
    return type_new(meta, a.pos(1), a.pos(2), a.pos(3), Args{a.data + a.npos, 0, a.kwnames, a.nkw});
}
Ref type_init(Obj, Args a) {                       // type_init: one argument or three; keywords only with three
    if (a.npos == 1 && a.nkw != 0) raise_new("TypeError", "type.__init__() takes no keyword arguments");
    if (a.npos != 1 && a.npos != 3) raise_new("TypeError", "type.__init__() takes 1 or 3 arguments");
    return none_ref();
}
// type.__abstractmethods__: the class's own entry; setting it makes the class abstract or not
// (type_set_abstractmethods), deleting it clears the flag; type itself has none
Ref type_abstractmethods_get(Obj self) {
    ClassObject* c = as_class(self);
    const Obj* v = c == types().type ? nullptr : c->attrs.find(N("__abstractmethods__"));
    if (v == nullptr) raise_attribute_error(self, N("__abstractmethods__"), "__abstractmethods__");
    return Ref::share(*v);
}
void type_abstractmethods_set(Obj self, Obj value) {
    ClassObject* c = as_class(self);
    if (value.is_unset()) {
        if (!c->attrs.contains(N("__abstractmethods__")))
            raise_attribute_error(self, N("__abstractmethods__"), "__abstractmethods__");
        c->del_attr(N("__abstractmethods__"));
        c->abstract = false;
        return;
    }
    bool abstract = truth(value);
    c->set_attr(N("__abstractmethods__"), value);
    c->abstract = abstract;
}
// dict.__new__ (dict_new): an empty dict of the class, a subclass's with its attribute storage
// (decision 2026-11-03); its arguments are __init__'s
Ref dict_new_m(Obj, Args a) {
    ClassObject* cls = new_wrapper_class(a, types().dict);
    if (cls == types().dict) return dict_new();
    return own(new DictInstance(cls));
}
// dict.__init__ (dict_update_common): one positional argument, a mapping or pairs, then the
// keywords, each inserted directly (a subclass's __setitem__ is not called)
Ref dict_init_m(Obj self, Args a) {
    if (a.npos > 1) raise_new("TypeError", "dict expected at most 1 argument, got " + std::to_string(a.npos));
    if (a.npos == 1) dict_update_arg(self, a.pos(0));
    for (std::size_t i = 0; i < a.nkw; ++i) dict_set(static_cast<Dict*>(self.object()), Obj::of(a.kwnames[i]), a.kw(i));
    return none_ref();
}
// ---- int() (long_new_impl, PyNumber_Long, PyLong_FromString) ----
Ref int_ref(std::int64_t v) {                     // an exact int within the immediates (the bn port: the rest)
    if (v < SMALL_MIN || v > SMALL_MAX) throw NotImplemented("BigInt: a result left the 63-bit immediate range");
    return Ref::steal(Obj::small(v));
}
// PyLong_FromString on an ASCII str: whitespace around it (Py_ISSPACE), a sign, the base's prefix,
// single underscores between digits; a ValueError names the base given and the string's repr
Ref int_from_str(const Str* s, std::int64_t base) {
    if (!s->ascii) throw NotImplemented("int() of a str beyond ASCII (its digits and spaces need the Unicode database)");
    const std::string& t = s->text;
    auto invalid = [&]() -> Ref {
        Ref r = repr_of(Obj::of(s));
        const Str* rs = as_str(r.get());
        std::u32string shown;                       // %.200R: the repr, cut at 200 code points
        for (std::size_t k = 0; k < std::min<std::size_t>(rs->length, 200); ++k) shown += rs->at(k);
        Ref cut = str_from_codepoints(shown);
        raise_new("ValueError", "invalid literal for int() with base " + std::to_string(base) + ": " + as_str(cut.get())->text);
    };
    auto space = [](char c) { return c == ' ' || (c >= '\t' && c <= '\r'); };
    std::size_t i = 0, n = t.size();
    while (i < n && space(t[i])) ++i;
    bool negative = false;
    if (i < n && (t[i] == '+' || t[i] == '-')) negative = t[i++] == '-';
    std::int64_t b = base;
    bool error_if_nonzero = false;
    auto lower = [](char c) { return static_cast<char>(c | 0x20); };
    if (b == 0) {
        if (i >= n || t[i] != '0') b = 10;
        else if (i + 1 < n && lower(t[i + 1]) == 'x') b = 16;
        else if (i + 1 < n && lower(t[i + 1]) == 'o') b = 8;
        else if (i + 1 < n && lower(t[i + 1]) == 'b') b = 2;
        else {
            error_if_nonzero = true;               // an old octal literal: valid only as zero
            b = 10;
        }
    }
    if (i + 1 < n && t[i] == '0' && ((b == 16 && lower(t[i + 1]) == 'x') || (b == 8 && lower(t[i + 1]) == 'o') ||
                                     (b == 2 && lower(t[i + 1]) == 'b'))) {
        i += 2;
        if (i < n && t[i] == '_') ++i;             // one underscore allowed here
    }
    auto digit = [](char c) -> int {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'a' && c <= 'z') return c - 'a' + 10;
        if (c >= 'A' && c <= 'Z') return c - 'A' + 10;
        return 37;
    };
    std::size_t start = i, digits = 0;
    if (i < n && t[i] == '_') invalid();          // a leading underscore
    char prev = 0;
    while (i < n && (digit(t[i]) < b || t[i] == '_')) {
        if (t[i] == '_' && prev == '_') invalid();
        if (t[i] != '_') ++digits;
        prev = t[i++];
    }
    if (prev == '_' || i == start) invalid();     // a trailing underscore, or no digits
    std::size_t end = i;
    while (i < n && space(t[i])) ++i;
    if (i != n) invalid();                          // anything else after the digits (a NUL included)
    bool binary_base = (b & (b - 1)) == 0;
    if (!binary_base && digits > 640 && digits > 4300)
        raise_new("ValueError", "Exceeds the limit (4300 digits) for integer string conversion: value has " + std::to_string(digits) +
                                    " digits; use sys.set_int_max_str_digits() to increase the limit");
    __int128 v = 0;
    for (std::size_t k = start; k < end; ++k) {
        if (t[k] == '_') continue;
        v = v * b + digit(t[k]);
        if (v > (static_cast<__int128>(1) << 62)) throw NotImplemented("BigInt: int() of a str beyond the 63-bit immediate range");
    }
    if (error_if_nonzero && v != 0) {
        base = 0;
        invalid();
    }
    return int_ref(static_cast<std::int64_t>(negative ? -v : v));
}

// PyNumber_Long: an int as itself (a subclass's value as an exact int), __int__, __index__, a str
Ref number_long(Obj x) {
    std::int64_t v;
    if (x.is_small()) return Ref::share(x);
    bool python = is_kind(x, Kind::Instance) || is_subclass_instance(x) || has_python_type(x);
    if (python && !type_lookup(type_of(x), N("__int__")).is_unset() &&
        !(is_subclass_instance(x) && !overrides_builtin(x, "__int__"))) {
        Ref r = call_special(x, "__int__", {});
        if (!as_int(r.get(), v))
            raise_new("TypeError", fully_qualified_name(type_of(x)) + ".__int__() must return an int, not " +
                                       fully_qualified_name(type_of(r.get())));
        if (!r.get().is_small())                 // CPython copies a strict subclass's value with a DeprecationWarning
            throw NotImplemented("__int__ returning an instance of a subclass of int (a DeprecationWarning in CPython)");
        return int_ref(v);
    }
    if (as_int(x, v)) return int_ref(v);          // a bool, an int subclass's instance: nb_int, an exact copy
    if (python && !type_lookup(type_of(x), N("__index__")).is_unset()) return int_ref(index_value(x));
    if (const Str* s = as_str(x)) return int_from_str(s, 10);
    if (is_kind(x, Kind::Float)) throw NotImplemented("int() of a float");
    raise_new("TypeError", "int() argument must be a string, a bytes-like object or a real number, not '" + type_of(x)->name + "'");
}

// int.__new__(cls, x=0, /, base=10) (long_new_impl; a subclass's instance carries the value,
// long_subtype_new)
Ref int_new_m(Obj, Args a) {
    ClassObject* cls = new_wrapper_class(a, types().int_);
    std::size_t npos = a.npos - 1;
    if (npos + a.nkw > 2) {
        if (a.nkw == 0) raise_new("TypeError", "int expected at most 2 arguments, got " + std::to_string(npos));
        raise_new("TypeError", "int() takes at most 2 arguments (" + std::to_string(npos + a.nkw) + " given)");
    }
    Obj x = npos >= 1 ? a.pos(1) : Obj{}, base = npos >= 2 ? a.pos(2) : Obj{};
    for (std::size_t k = 0; k < a.nkw; ++k) {
        if (a.kwnames[k]->text != "base") raise_new("TypeError", "int() got an unexpected keyword argument '" + a.kwnames[k]->text + "'");
        base = a.kw(k);
    }
    Ref value;
    if (x.is_unset()) {
        if (!base.is_unset()) raise_new("TypeError", "int() missing string argument");
        value = int_ref(0);
    } else if (base.is_unset()) {
        value = number_long(x);
    } else {
        std::int64_t b = index_value(base);
        if ((b != 0 && b < 2) || b > 36) raise_new("ValueError", "int() base must be >= 2 and <= 36, or 0");
        const Str* s = as_str(x);
        if (s == nullptr) raise_new("TypeError", "int() can't convert non-string with explicit base");
        value = int_from_str(s, b);
    }
    if (cls == types().int_) return value;
    return own(new IntInstance(cls, value.get().small_value()));
}

Ref type_call_m(Obj self, Args a) {                // type.__call__: what calling the class does
    return type_call(as_class(self), a);
}
Ref type_setattr_m(Obj self, Args a) {
    arity(a, "__setattr__", 2, 2);
    const Str* n = as_str(a.pos(0));
    if (n == nullptr) raise_new("TypeError", "attribute name must be string, not '" + type_of(a.pos(0))->name + "'");
    type_setattr_generic(as_class(self), intern(n->text), a.pos(1));
    return none_ref();
}
Ref type_delattr_m(Obj self, Args a) {
    arity(a, "__delattr__", 1, 1);
    const Str* n = as_str(a.pos(0));
    if (n == nullptr) raise_new("TypeError", "attribute name must be string, not '" + type_of(a.pos(0))->name + "'");
    type_delattr_generic(as_class(self), intern(n->text));
    return none_ref();
}
Ref type_instancecheck_m(Obj self, Args a) {       // type.__instancecheck__: _PyObject_RealIsInstance
    arity(a, "__instancecheck__", 1, 1);
    return Ref::steal(boolean(real_isinstance(a.pos(0), self)));
}
Ref type_subclasscheck_m(Obj self, Args a) {       // type.__subclasscheck__: _PyObject_RealIsSubclass
    arity(a, "__subclasscheck__", 1, 1);
    return Ref::steal(boolean(real_issubclass(a.pos(0), self)));
}
Ref type_prepare(Obj, Args) { return dict_new(); }
Ref type_mro(Obj self, Args a) {
    arity(a, "mro", 0, 0);
    Ref l = list_new({});
    for (ClassObject* m : c3(as_class(self))) list_append(l.get(), Obj::of(m));
    return l;
}
Ref type_repr(Obj self, Args) { return repr_of(self); }

// object's methods
Ref object_eq(Obj self, Args a) {
    arity(a, "__eq__", 1, 1);
    return Ref::steal(self == a.pos(0) ? boolean(true) : Obj::of(NOTIMPLEMENTED));
}
Ref object_ne(Obj self, Args a) {             // inverts __eq__ unless it returned NotImplemented
    arity(a, "__ne__", 1, 1);
    Ref r = call_special(self, "__eq__", {a.pos(0)});
    if (r.get() == Obj::of(NOTIMPLEMENTED)) return r;
    return Ref::steal(boolean(!truth(r.get())));
}
Ref object_notimplemented(Obj, Args) { return Ref::steal(Obj::of(NOTIMPLEMENTED)); }
Ref object_hash(Obj self, Args) {
    // CPython rotates the address by 4 bits (_Py_HashPointer); the value depends on the address in
    // both, so only its consistency is observable: the address shifted by 4 fits a small int
    auto p = reinterpret_cast<std::uintptr_t>(self.object());
    return Ref::steal(Obj::small(static_cast<std::int64_t>(p >> 4)));
}
Ref object_repr(Obj self, Args) {
    ClassObject* c = type_of(self);
    std::string mod;
    if (const Obj* m = c->attrs.find(N("__module__")))
        if (const Str* ms = as_str(*m); ms != nullptr && ms->text != "builtins") mod = ms->text + ".";
    char buf[32];
    std::snprintf(buf, sizeof buf, "%p", static_cast<void*>(self.object()));
    return str_new("<" + mod + c->qualname + " object at " + buf + ">");
}
Ref object_str(Obj self, Args) { return repr_of(self); }
Ref object_init_subclass(Obj, Args a) {
    if (a.nkw != 0) raise_new("TypeError", "__init_subclass__() takes no keyword arguments");
    return none_ref();
}
// object.__setattr__ and __delattr__ are slot wrappers: bound like methods, the object as self
// (found while compiling super(), which binds them: super().__setattr__(k, v))
Ref object_setattr(Obj self, Args a) {
    arity(a, "__setattr__", 2, 2);
    const Str* n = as_str(a.pos(0));
    if (n == nullptr) raise_new("TypeError", "attribute name must be string, not '" + type_of(a.pos(0))->name + "'");
    if (!is_kind(self, Kind::Instance) && !is_subclass_instance(self)) throw NotImplemented("object.__setattr__ on a C++ type's object");
    if (type_lookup(type_of(self), intern(n->text)).is_unset()) refuse_absent_data_descriptor(self, intern(n->text));
    with_attribute_storage(self, [&](auto* inst) {
        try {
            bella::setattr(inst, intern(n->text), a.pos(1));
        } catch (const bella::AttributeError&) {
            raise_attribute_error(self, intern(n->text), "'" + type_of(self)->name + "' object has no attribute '" + n->text + "'");
        }
    });
    return none_ref();
}
Ref object_delattr(Obj self, Args a) {
    arity(a, "__delattr__", 1, 1);
    const Str* n = as_str(a.pos(0));
    if (n == nullptr) raise_new("TypeError", "attribute name must be string, not '" + type_of(a.pos(0))->name + "'");
    if (!is_kind(self, Kind::Instance) && !is_subclass_instance(self)) throw NotImplemented("object.__delattr__ on a C++ type's object");
    if (type_lookup(type_of(self), intern(n->text)).is_unset()) refuse_absent_data_descriptor(self, intern(n->text));
    with_attribute_storage(self, [&](auto* inst) {
        try {
            bella::delattr(inst, intern(n->text));
        } catch (const bella::AttributeError&) {
            raise_attribute_error(self, intern(n->text), "'" + type_of(self)->name + "' object has no attribute '" + n->text + "'");
        }
    });
    return none_ref();
}
Ref object_format(Obj self, Args a) {
    arity(a, "__format__", 1, 1);
    const Str* spec = as_str(a.pos(0));
    if (spec != nullptr && spec->length != 0)
        raise_new("TypeError", "unsupported format string passed to " + type_of(self)->name + ".__format__");
    return str_of(self);
}

Ref class_of(Obj self) { return Ref::share(Obj::of(observed_type(self))); }
void set_class_of(Obj, Obj) { throw NotImplemented("[P2+] __class__ assignment (spec section 3)"); }
Ref instance_dict(Obj self) {
    Ref out;
    if (!with_attribute_storage(self, [&](auto* inst) { out = expose_dict(inst); }))
        throw NotImplemented("__dict__ of a C++ type's object");
    return out;
}
void set_instance_dict(Obj self, Obj d) {
    Ref fresh;
    if (d.is_unset()) {                          // del obj.__dict__: the dict is detached; the object starts afresh
        fresh = dict_new();
        d = fresh.get();
    } else if (!is_kind(d, Kind::Dict)) {
        raise_new("TypeError", "__dict__ must be set to a dictionary, not a '" + type_of(d)->name + "'");
    }
    with_attribute_storage(self, [&](auto* inst) { set_dict(inst, static_cast<DictObject*>(d.object())); });
}

// the getset a class that adds an instance dict gets as its __dict__ (type_new)
GetSet* instance_dict_getset() {
    static GetSet* g = [] {
        auto* gs = new GetSet("__dict__", types().object, instance_dict, set_instance_dict);
        gs->deletable = true;
        return gs;
    }();
    return g;
}

// type's getsets
ClassObject* self_class(Obj self) { return as_class(self); }
Ref type_name(Obj self) { return str_new(self_class(self)->name); }
// check_set_special_type_attr: a delete is refused first, then a store to an immutable type
void check_special(ClassObject* c, Obj v, const char* name) {
    if (v.is_unset()) raise_new("TypeError", std::string("cannot delete '") + name + "' attribute of type '" + c->name + "'");
    if (immutable_type(c)) raise_new("TypeError", std::string("cannot set '") + name + "' attribute of immutable type '" + c->name + "'");
}
void set_type_name(Obj self, Obj v) {
    ClassObject* c = self_class(self);
    check_special(c, v, "__name__");
    const Str* s = as_str(v);
    if (s == nullptr) raise_new("TypeError", "can only assign string to " + c->name + ".__name__, not '" + type_of(v)->name + "'");
    c->name = s->text;
}
Ref type_qualname(Obj self) { return str_new(self_class(self)->qualname); }
void set_type_qualname(Obj self, Obj v) {
    ClassObject* c = self_class(self);
    check_special(c, v, "__qualname__");
    const Str* s = as_str(v);
    if (s == nullptr) raise_new("TypeError", "can only assign string to " + c->name + ".__qualname__, not '" + type_of(v)->name + "'");
    c->qualname = s->text;
}
Ref type_module(Obj self) {
    ClassObject* c = self_class(self);
    if (!c->heap_type) return str_new("builtins");
    if (const Obj* m = c->attrs.find(N("__module__"))) return Ref::share(*m);
    raise_attribute_error(self, N("__module__"), "__module__");
}
void set_type_module(Obj self, Obj v) {          // type_set_module: the class's own __module__
    ClassObject* c = self_class(self);
    check_special(c, v, "__module__");
    c->set_attr(N("__module__"), v);
}
Ref type_doc(Obj self) {
    ClassObject* c = self_class(self);
    if (const Obj* d = c->attrs.find(N("__doc__"))) return descr_get(*d, None(), self);
    return none_ref();
}
// type_set_doc: a class's own __doc__, after check_set_special_type_attr
void set_type_doc(Obj self, Obj value) {
    ClassObject* c = self_class(self);
    check_special(c, value, "__doc__");
    c->set_attr(N("__doc__"), value);
}
// __bases__ is settable in CPython (type_set_bases, with its layout checks); not here yet
void set_type_bases(Obj, Obj) { throw NotImplemented("assigning a class's __bases__"); }
Ref type_dict(Obj self) { return own(new Proxy(self_class(self))); }
Ref type_mro_attr(Obj self) {
    std::vector<Obj> items;
    for (ClassObject* m : self_class(self)->mro) items.push_back(Obj::of(m));
    return tuple_copy(items);
}
Ref type_bases(Obj self) {
    std::vector<Obj> items;
    for (ClassObject* b : self_class(self)->bases) items.push_back(Obj::of(b));
    if (items.empty() && self_class(self) != types().object) items.push_back(Obj::of(types().object));
    return tuple_copy(items);
}
Ref type_base(Obj self) {
    ClassObject* c = self_class(self);
    if (c == types().object) return none_ref();
    return Ref::share(Obj::of(c->bases.empty() ? types().object : c->bases[0]));
}
Ref type_flags(Obj self) { return Ref::steal(Obj::small(self_class(self)->heap_type ? (1 << 9) : 0)); }

// function, method and cell attributes
PyFunction* fn_of(Obj self) { return static_cast<PyFunction*>(self.object()); }
Ref fn_name(Obj self) { return fn_of(self)->name; }
void set_fn_name(Obj self, Obj v) {
    if (as_str(v) == nullptr) raise_new("TypeError", "__name__ must be set to a string object");
    fn_of(self)->name = Ref::share(v);
}
Ref fn_qualname(Obj self) { return fn_of(self)->qualname; }
void set_fn_qualname(Obj self, Obj v) {
    if (as_str(v) == nullptr) raise_new("TypeError", "__qualname__ must be set to a string object");
    fn_of(self)->qualname = Ref::share(v);
}
Ref fn_doc(Obj self) { return fn_of(self)->doc; }
void set_fn_doc(Obj self, Obj v) { fn_of(self)->doc = Ref::share(v); }
Ref fn_module(Obj self) {
    Obj n = dict_get(fn_of(self)->module->dict, Obj::of(N("__name__")));
    return n.is_unset() ? none_ref() : Ref::share(n);
}
Ref fn_defaults(Obj self) { return fn_of(self)->defaults.get().is_unset() ? none_ref() : fn_of(self)->defaults; }
Ref fn_kwdefaults(Obj self) { return fn_of(self)->kwdefaults.get().is_unset() ? none_ref() : fn_of(self)->kwdefaults; }
Ref fn_annotate(Obj self) { return fn_of(self)->annotate.get().is_unset() ? none_ref() : fn_of(self)->annotate; }
Ref fn_dict(Obj self) {
    if (fn_of(self)->dict.get().is_unset()) fn_of(self)->dict = dict_new();
    return fn_of(self)->dict;
}
Ref method_func(Obj self) { return Ref::share(static_cast<Method*>(self.object())->func); }
Ref method_new(Obj, Args a) {                    // method(func, obj): any callable bound to obj
    new_wrapper_class(a, types().method);
    Args r = rest(a);
    arity(r, "method", 2, 2);
    if (!callable_check(r.pos(0))) raise_new("TypeError", "first argument must be callable");
    if (is_none(r.pos(1))) raise_new("TypeError", "instance must not be None");
    return own(new Method(r.pos(0), r.pos(1)));
}
Ref method_self(Obj self) { return Ref::share(static_cast<Method*>(self.object())->self); }
Ref builtin_name(Obj self) {
    if (is_kind(self, Kind::PyFunction)) return static_cast<PyFunction*>(self.object())->name;     // the prelude's
    return str_new(static_cast<Builtin*>(self.object())->name);
}
Ref builtin_self(Obj self) {
    if (is_kind(self, Kind::PyFunction)) return Ref::share(Obj::of(builtins_module()));             // print.__self__
    auto* b = static_cast<Builtin*>(self.object());
    if (b->self.is_unset() && b->binding == Binding::Function && b->owner != nullptr &&
        cpython_attribute_kind(b->owner, b->name) == "builtin_function_or_method")
        return Ref::share(Obj::of(b->owner));                       // object.__new__.__self__ is object
    return b->self.is_unset() ? none_ref() : Ref::share(b->self);
}
Ref cell_contents_get(Obj self) {
    Obj v = static_cast<Cell*>(self.object())->value;
    if (v.is_unset()) raise_new("ValueError", "Cell is empty");
    return Ref::share(v);
}
void cell_contents_set(Obj self, Obj v) {
    auto* c = static_cast<Cell*>(self.object());
    incref(v);
    decref(std::exchange(c->value, v));
}

// mappingproxy over a class's own attributes
ClassObject* proxied(Obj self) { return static_cast<Proxy*>(self.object())->of; }
Ref proxy_getitem(Obj self, Args a) {
    arity(a, "__getitem__", 1, 1);
    const Str* k = as_str(a.pos(0));
    if (k != nullptr)
        if (const Obj* v = proxied(self)->attrs.find(intern(k->text))) return Ref::share(*v);
    Ref exc = invoke(Obj::of(exception_class("KeyError")), {a.pos(0)});
    raise(exc.get());
}
Ref proxy_contains(Obj self, Args a) {
    arity(a, "__contains__", 1, 1);
    const Str* k = as_str(a.pos(0));
    return Ref::steal(boolean(k != nullptr && proxied(self)->attrs.contains(intern(k->text))));
}
Ref proxy_get(Obj self, Args a) {
    arity(a, "get", 1, 2);
    const Str* k = as_str(a.pos(0));
    if (k != nullptr)
        if (const Obj* v = proxied(self)->attrs.find(intern(k->text))) return Ref::share(*v);
    return a.npos > 1 ? Ref::share(a.pos(1)) : none_ref();
}
Ref proxy_len(Obj self, Args) { return Ref::steal(Obj::small(static_cast<std::int64_t>(proxied(self)->attrs.size()))); }
Ref proxy_keys(Obj self, Args) {
    Ref l = list_new({});
    for (auto& [k, v] : proxied(self)->attrs.items()) list_append(l.get(), Obj::of(k));
    return l;
}
Ref proxy_iter(Obj self, Args a) {
    Ref keys = proxy_keys(self, a);
    return iter(keys.get());
}

// slices
Ref slice_new(Obj, Args a) {                   // __new__(cls, ...): the class comes first
    new_wrapper_class(a, types().slice);
    Args r = rest(a);
    arity(r, "slice", 1, 3);
    Obj start = r.npos > 1 ? r.pos(0) : None(), stop = r.npos > 1 ? r.pos(1) : r.pos(0), step = r.npos > 2 ? r.pos(2) : None();
    return own(new SliceObject(start, stop, step));
}
Ref slice_start(Obj self) { return Ref::share(static_cast<SliceObject*>(self.object())->start); }
Ref slice_stop(Obj self) { return Ref::share(static_cast<SliceObject*>(self.object())->stop); }
Ref slice_step(Obj self) { return Ref::share(static_cast<SliceObject*>(self.object())->step); }

// BaseException: args from __new__ and __init__, str() and repr()
Ref exception_new(Obj, Args a) {
    ClassObject* cls = new_wrapper_class(a, exception_class("BaseException"));
    auto* e = new_instance(cls);
    Ref r = own(e);
    std::vector<Obj> items;
    for (std::size_t i = 1; i < a.npos; ++i) {
        incref(a.pos(i));
        items.push_back(a.pos(i));
    }
    Ref args = tuple_steal(std::move(items));
    set_exception_field(r.get(), "args", args.get());
    return r;
}
Ref exception_init(Obj self, Args a) {
    if (a.nkw != 0) raise_new("TypeError", type_of(self)->name + "() takes no keyword arguments");
    std::vector<Obj> items;
    for (std::size_t i = 0; i < a.npos; ++i) {
        incref(a.pos(i));
        items.push_back(a.pos(i));
    }
    Ref args = tuple_steal(std::move(items));
    set_exception_field(self, "args", args.get());
    return none_ref();
}
// what BaseException_str, KeyError_str and BaseException_repr read: the args field itself
Ref exception_args(Obj self) {
    Obj v = exception_field(self, "args");
    return v.is_unset() ? tuple_new({}) : Ref::share(v);
}
Ref exception_str(Obj self, Args) {
    Ref args = exception_args(self);
    if (!is_kind(args.get(), Kind::Tuple)) return str_of(args.get());
    auto& items = static_cast<Tuple*>(args.get().object())->items;
    if (items.empty()) return str_new("");
    if (items.size() == 1) return str_of(items[0]);
    return repr_of(args.get());
}
Ref key_error_str(Obj self, Args a) {             // KeyError_str: one argument shows as its repr
    Ref args = exception_args(self);
    if (is_kind(args.get(), Kind::Tuple) && static_cast<Tuple*>(args.get().object())->items.size() == 1)
        return repr_of(static_cast<Tuple*>(args.get().object())->items[0]);
    return exception_str(self, a);
}
Ref exception_repr(Obj self, Args) {
    // BaseException_repr: Name(repr(arg)) for one argument, Name + repr(args) otherwise
    Ref args = exception_args(self);
    auto& items = static_cast<Tuple*>(args.get().object())->items;
    Ref inner = items.size() == 1 ? repr_of(items[0]) : repr_of(args.get());
    std::string text = as_str(inner.get())->text;
    return str_new(type_of(self)->name + (items.size() == 1 ? "(" + text + ")" : text));
}
// BaseException's getset and member descriptors (Objects/exceptions.c): each checks what it is
// given, with CPython's words; none may be deleted
void exception_traceback_set(Obj self, Obj v) {
    if (v.is_unset()) raise_new("TypeError", "__traceback__ may not be deleted");
    if (!is_kind(v, Kind::Traceback) && !is_none(v)) raise_new("TypeError", "__traceback__ must be a traceback or None");
    set_exception_field(self, "__traceback__", is_none(v) ? Obj{} : v);
}
Ref exception_with_traceback(Obj self, Args a) {
    arity(a, "with_traceback", 1, 1);
    exception_traceback_set(self, a.pos(0));
    return Ref::share(self);
}
Ref field_or_none(Obj self, const char* name) {
    Obj v = exception_field(self, name);
    return v.is_unset() ? none_ref() : Ref::share(v);
}
Ref exception_args_get(Obj self) { return exception_args(self); }
void exception_args_set(Obj self, Obj v) {          // PySequence_Tuple
    if (v.is_unset()) raise_new("TypeError", "args may not be deleted");
    Ref t;
    if (is_kind(v, Kind::Tuple)) {
        t = Ref::share(v);
    } else {
        Ref it = iter(v);
        std::vector<Obj> items;
        for (Ref x = for_next(it.get()); !is_end(x); x = for_next(it.get())) items.push_back(x.release());
        t = tuple_steal(std::move(items));
    }
    set_exception_field(self, "args", t.get());
}
Ref exception_traceback_get(Obj self) { return field_or_none(self, "__traceback__"); }
Ref exception_context_get(Obj self) { return field_or_none(self, "__context__"); }
void exception_context_set(Obj self, Obj v) {
    if (v.is_unset()) raise_new("TypeError", "__context__ may not be deleted");
    if (!is_none(v) && !is_exception_instance(v))
        raise_new("TypeError", "exception context must be None or derive from BaseException");
    set_exception_field(self, "__context__", is_none(v) ? Obj{} : v);
}
Ref exception_cause_get(Obj self) { return field_or_none(self, "__cause__"); }
void exception_cause_set(Obj self, Obj v) {         // PyException_SetCause sets __suppress_context__
    if (v.is_unset()) raise_new("TypeError", "__cause__ may not be deleted");
    if (!is_none(v) && !is_exception_instance(v))
        raise_new("TypeError", "exception cause must be None or derive from BaseException");
    set_exception_field(self, "__suppress_context__", boolean(true));
    set_exception_field(self, "__cause__", is_none(v) ? Obj{} : v);
}
Ref exception_suppress_get(Obj self) {
    Obj v = exception_field(self, "__suppress_context__");
    return Ref::share(v.is_unset() ? boolean(false) : v);
}
void exception_suppress_set(Obj self, Obj v) {      // a Py_T_BOOL member
    if (v.is_unset()) raise_new("TypeError", "can't delete numeric/char attribute");
    if (!is_kind(v, Kind::Bool)) raise_new("TypeError", "attribute value type must be bool");
    set_exception_field(self, "__suppress_context__", v);
}
// AttributeError's name and obj, NameError's name: _Py_T_OBJECT members (None when absent; del clears)
// ImportError (Objects/exceptions.c): msg, name, path and name_from are members; __init__ takes
// the last three by keyword only, and msg is the one argument when there is exactly one
Ref import_error_init(Obj self, Args a) {
    std::vector<Obj> items;
    for (std::size_t i = 0; i < a.npos; ++i) {
        incref(a.pos(i));
        items.push_back(a.pos(i));
    }
    Ref args = tuple_steal(std::move(items));
    set_exception_field(self, "args", args.get());
    Obj name, path, name_from;
    for (std::size_t k = 0; k < a.nkw; ++k) {
        std::string_view n = a.kwnames[k]->text;
        Obj* slot = n == "name" ? &name : n == "path" ? &path : n == "name_from" ? &name_from : nullptr;
        if (slot == nullptr)        // CPython's message may suggest a keyword (_Py_CalculateSuggestions)
            throw NotImplemented("ImportError() with an unexpected keyword argument (the suggestion in its message)");
        *slot = a.kw(k);
    }
    set_exception_field(self, "name", name);
    set_exception_field(self, "path", path);
    set_exception_field(self, "name_from", name_from);
    set_exception_field(self, "msg", a.npos == 1 ? a.pos(0) : Obj{});
    return none_ref();
}
Ref import_error_str(Obj self, Args a) {          // ImportError_str: msg when it is exactly a str
    Obj msg = exception_field(self, "msg");
    if (!msg.is_unset() && is_kind(msg, Kind::Str) && type_of(msg) == types().str) return Ref::share(msg);
    return exception_str(self, a);
}
Ref import_error_repr(Obj self, Args a) {         // ImportError_repr: BaseException's, then name= and path=
    Obj name = exception_field(self, "name"), path = exception_field(self, "path");
    if (name.is_unset() && path.is_unset()) return exception_repr(self, a);
    Ref base = exception_repr(self, a);
    std::string text = as_str(base.get())->text;
    text.pop_back();
    Ref args = exception_args(self);
    bool hasargs = !static_cast<Tuple*>(args.get().object())->items.empty();
    if (!name.is_unset()) {
        if (hasargs) text += ", ";
        text += "name=" + as_str(repr_of(name).get())->text;
        hasargs = true;
    }
    if (!path.is_unset()) {
        if (hasargs) text += ", ";
        text += "path=" + as_str(repr_of(path).get())->text;
    }
    return str_new(text + ")");
}
Ref import_msg_get(Obj self) { return field_or_none(self, "msg"); }
void import_msg_set(Obj self, Obj v) { set_exception_field(self, "msg", v); }
Ref import_path_get(Obj self) { return field_or_none(self, "path"); }
void import_path_set(Obj self, Obj v) { set_exception_field(self, "path", v); }
Ref import_name_from_get(Obj self) { return field_or_none(self, "name_from"); }
void import_name_from_set(Obj self, Obj v) { set_exception_field(self, "name_from", v); }
Ref exception_name_get(Obj self) { return field_or_none(self, "name"); }
void exception_name_set(Obj self, Obj v) { set_exception_field(self, "name", v); }
Ref exception_obj_get(Obj self) { return field_or_none(self, "obj"); }
void exception_obj_set(Obj self, Obj v) { set_exception_field(self, "obj", v); }
void deletable_getset(ClassObject* c, const char* name, Ref (*g)(Obj), void (*s)(Obj, Obj)) {
    auto* d = new GetSet(name, c, g, s);
    d->deletable = true;
    c->attrs.set(N(name), Obj::of(d));
}
}  // namespace

// ---- namespaces ----
Obj cell_contents(const Ref& cell) { return static_cast<Cell*>(cell.get().object())->value; }

Ref mapping_get(Obj mapping, Obj key) {
    if (is_kind(mapping, Kind::Dict) && !is_subclass_instance(mapping)) {   // PyDict_CheckExact: else __getitem__
        Obj v = dict_get(static_cast<Dict*>(mapping.object()), key);
        return v.is_unset() ? Ref{} : Ref::share(v);
    }
    if (is_kind(mapping, Kind::Proxy)) {
        const Str* k = as_str(key);
        if (k == nullptr) return Ref{};
        const Obj* v = proxied(mapping)->attrs.find(intern(k->text));
        return v ? Ref::share(*v) : Ref{};
    }
    try {
        return getitem(mapping, key);
    } catch (const PyError& e) {
        if (!isinstance(e.exc.get(), exception_class("KeyError"))) throw;
        return Ref{};
    }
}
void mapping_set(Obj mapping, Obj key, Obj value) {          // STORE_NAME: an exact dict's, else __setitem__
    if (is_kind(mapping, Kind::Dict) && !is_subclass_instance(mapping)) dict_set(static_cast<Dict*>(mapping.object()), key, value);
    else setitem(mapping, key, value);
}

Ref load_classdict(Obj mapping, Module* m, const Str* name) {
    Ref v = mapping_get(mapping, Obj::of(name));
    if (!v.get().is_unset()) return v;
    return load_global(m, name);
}
Ref load_classdict_free(Obj mapping, const Str* name, const Ref& cell, const char* text) {
    Ref v = mapping_get(mapping, Obj::of(name));
    if (!v.get().is_unset()) return v;
    return load_deref(cell, text, true);
}

// ---- the builtin types' attributes ----
void init_types() {
    static bool done = false;
    if (done) return;
    done = true;
    Types& t = types();
    init_sets();
    init_super();
    // object
    method(t.object, "__new__", object_new, Binding::Function);
    method(t.object, "__init__", object_init);
    method(t.object, "__eq__", object_eq);
    method(t.object, "__ne__", object_ne);
    for (const char* n : {"__lt__", "__le__", "__gt__", "__ge__"}) method(t.object, n, object_notimplemented);
    method(t.object, "__hash__", object_hash);
    method(t.object, "__repr__", object_repr);
    method(t.object, "__str__", object_str);
    method(t.object, "__format__", object_format);
    method(t.object, "__setattr__", object_setattr);
    method(t.object, "__delattr__", object_delattr);
    method(t.object, "__init_subclass__", object_init_subclass, Binding::ClassMethod);
    getset(t.object, "__class__", class_of, set_class_of);
    value(t.object, "__doc__", str_new("The base class of the class hierarchy.").get());
    // type
    method(t.type, "__new__", type_new_builtin, Binding::Function);
    method(t.type, "__init__", type_init);
    method(t.type, "__call__", type_call_m);
    method(t.dict, "__new__", dict_new_m, Binding::Function);
    method(t.int_, "__new__", int_new_m, Binding::Function);
    method(t.dict, "__init__", dict_init_m);
    {
        auto* g = new GetSet("__abstractmethods__", t.type, type_abstractmethods_get, type_abstractmethods_set);
        g->deletable = true;
        t.type->attrs.set(N("__abstractmethods__"), Obj::of(g));
    }
    method(t.type, "__setattr__", type_setattr_m);
    method(t.type, "__delattr__", type_delattr_m);
    method(t.type, "__instancecheck__", type_instancecheck_m);
    method(t.type, "__subclasscheck__", type_subclasscheck_m);
    t.type->has_dict = true;                      // a class's __dict__ is type's getset: a metaclass adds none
    method(t.type, "__prepare__", type_prepare, Binding::ClassMethod);
    method(t.type, "mro", type_mro);
    method(t.type, "__repr__", type_repr);
    getset(t.type, "__name__", type_name, set_type_name);
    getset(t.type, "__qualname__", type_qualname, set_type_qualname);
    getset(t.type, "__module__", type_module, set_type_module);
    getset(t.type, "__doc__", type_doc, set_type_doc);
    getset(t.type, "__dict__", type_dict);
    getset(t.type, "__mro__", type_mro_attr);
    getset(t.type, "__bases__", type_bases, set_type_bases);
    getset(t.type, "__base__", type_base);
    getset(t.type, "__flags__", type_flags);
    for (const char* n : {"__name__", "__qualname__", "__module__", "__doc__", "__bases__"})
        static_cast<GetSet*>(t.type->attrs.find(N(n))->object())->deletable = true;
    // descriptors' own __get__ (and a getset's __set__ and __delete__)
    for (ClassObject* c : {t.function, t.method_descriptor, t.classmethod_descriptor, t.getset_descriptor}) method(c, "__get__", get_native);
    method(t.getset_descriptor, "__set__", getset_set);
    method(t.getset_descriptor, "__delete__", getset_delete);
    // functions, methods, cells
    getset(t.function, "__name__", fn_name, set_fn_name);
    getset(t.function, "__qualname__", fn_qualname, set_fn_qualname);
    getset(t.function, "__doc__", fn_doc, set_fn_doc);
    getset(t.function, "__module__", fn_module);
    getset(t.function, "__defaults__", fn_defaults);
    getset(t.function, "__kwdefaults__", fn_kwdefaults);
    getset(t.function, "__annotate__", fn_annotate);
    getset(t.function, "__dict__", fn_dict);
    getset(t.method, "__func__", method_func);
    method(t.method, "__new__", method_new, Binding::Function);
    getset(t.method, "__self__", method_self);
    getset(t.builtin, "__name__", builtin_name);
    getset(t.builtin, "__self__", builtin_self);
    getset(t.cell, "cell_contents", cell_contents_get, cell_contents_set);
    // mappingproxy, slice
    method(t.mappingproxy, "__getitem__", proxy_getitem);
    method(t.mappingproxy, "__contains__", proxy_contains);
    method(t.mappingproxy, "get", proxy_get);
    method(t.mappingproxy, "__len__", proxy_len);
    method(t.mappingproxy, "keys", proxy_keys);
    method(t.mappingproxy, "__iter__", proxy_iter);
    method(t.slice, "__new__", slice_new, Binding::Function);
    getset(t.slice, "start", slice_start);
    getset(t.slice, "stop", slice_stop);
    getset(t.slice, "step", slice_step);
    // exceptions
    ClassObject* base = exception_class("BaseException");
    method(base, "__new__", exception_new, Binding::Function);
    method(base, "__init__", exception_init);
    method(base, "__str__", exception_str);
    method(base, "__repr__", exception_repr);
    method(base, "with_traceback", exception_with_traceback);
    method(exception_class("KeyError"), "__str__", key_error_str);
    base->attrs.set(N("__dict__"), Obj::of(instance_dict_getset()));
    deletable_getset(base, "args", exception_args_get, exception_args_set);
    deletable_getset(base, "__traceback__", exception_traceback_get, exception_traceback_set);
    deletable_getset(base, "__context__", exception_context_get, exception_context_set);
    deletable_getset(base, "__cause__", exception_cause_get, exception_cause_set);
    deletable_getset(base, "__suppress_context__", exception_suppress_get, exception_suppress_set);
    deletable_getset(exception_class("AttributeError"), "name", exception_name_get, exception_name_set);
    deletable_getset(exception_class("AttributeError"), "obj", exception_obj_get, exception_obj_set);
    deletable_getset(exception_class("NameError"), "name", exception_name_get, exception_name_set);
    {
        ClassObject* ie = exception_class("ImportError");
        method(ie, "__init__", import_error_init);
        method(ie, "__str__", import_error_str);
        method(ie, "__repr__", import_error_repr);
        deletable_getset(ie, "msg", import_msg_get, import_msg_set);
        deletable_getset(ie, "name", exception_name_get, exception_name_set);
        deletable_getset(ie, "path", import_path_get, import_path_set);
        deletable_getset(ie, "name_from", import_name_from_get, import_name_from_set);
    }
    // object.hpp asks whether an exception the runtime raised is an AttributeError (a property or
    // __get__ in Python raising it), so that __getattr__ is tried
    attribute_error_hook() = [] {
        try {
            throw;
        } catch (const PyError& e) {
            return isinstance(e.exc.get(), exception_class("AttributeError"));
        } catch (...) {
            return false;
        }
    };
    // call_attribute: function and method descriptors take the object; other descriptors are
    // bound; any other callable gets the name alone
    missing_name_hook() = refuse_absent_attribute;
    call_attribute_hook() = [](Obj hook, Obj obj, Obj name) -> Obj {
        bool method = (is_kind(hook, Kind::PyFunction) && !presents_as_builtin(hook)) || is_kind(hook, Kind::Function) ||
                      (is_kind(hook, Kind::Builtin) && static_cast<Builtin*>(hook.object())->self.is_unset() &&
                       static_cast<Builtin*>(hook.object())->binding == Binding::Method);
        if (method) return invoke(hook, {obj, name}).release();
        if (!type_lookup(type_of(hook), intern("__get__")).is_unset()) {
            Ref bound = descr_get(hook, obj, Obj::of(type_of(obj)));
            return invoke(bound.get(), {name}).release();
        }
        return invoke(hook, {name}).release();
    };
}

}  // namespace bella
