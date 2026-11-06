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

NativeFn new_slot(ClassObject* c) {              // tp_new, as far as the runtime can tell it apart
    Obj f = type_lookup(c, N("__new__"));
    return is_kind(f, Kind::Builtin) ? static_cast<Builtin*>(f.object())->fn : nullptr;
}
ClassObject* static_base(ClassObject* c) {
    while (!is_kind(type_lookup(c, N("__new__")), Kind::Builtin) && !c->bases.empty()) c = tp_base(c);
    return c;
}
}  // namespace

// tp_new_wrapper's checks of T.__new__(cls, ...) (Objects/typeobject.c): the class it is given
ClassObject* new_wrapper_class(Args a, const ClassObject* type) {
    if (a.npos < 1) raise_new("TypeError", type->name + ".__new__(): not enough arguments");
    ClassObject* sub = as_class(a.pos(0));
    if (sub == nullptr)
        raise_new("TypeError", type->name + ".__new__(X): X is not a type object (" + type_of(a.pos(0))->name + ")");
    if (!is_subclass(sub, const_cast<ClassObject*>(type)))
        raise_new("TypeError", type->name + ".__new__(" + sub->name + "): " + sub->name + " is not a subtype of " + type->name);
    // tp_new_wrapper's staticbase: past the classes whose __new__ is Python's, the type whose tp_new
    // this must be, or the call would skip a built-in base's own (object.__new__(dict))
    ClassObject* staticbase = static_base(sub);
    if (new_slot(staticbase) != new_slot(const_cast<ClassObject*>(type)))
        raise_new("TypeError", type->name + ".__new__(" + sub->name + ") is not safe, use " + staticbase->name + ".__new__()");
    return sub;
}

namespace {

// A built-in type's __new__ as CPython makes it (tp_new_wrapper): a function bound to the type
void new_method(ClassObject* c, NativeFn fn) {
    auto* f = new Builtin("__new__", fn, Obj::of(c), Binding::Function);
    f->owner = c;
    f->flags |= IMMORTAL;
    c->attrs.set(N("__new__"), Obj::of(f));
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

void check_member_applies(const SlotDescriptor* d, Obj obj) {   // descr_check
    if (!isinstance(obj, d->owner))
        raise_new("TypeError", "descriptor '" + d->name->text + "' for '" + d->owner->name + "' objects doesn't apply to a '" + type_of(obj)->name + "' object");
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
            case Kind::SlotDescriptor: {             // member_get
                auto* d = static_cast<SlotDescriptor*>(o);
                if (is_none(obj)) return Ref::share(found);
                check_member_applies(d, obj);
                Ref out;
                with_attribute_storage(obj, [&](auto* inst) {
                    Obj v = inst->field(d->name);
                    if (v.is_unset()) raise_attribute_error(obj, d->name, "'" + fully_qualified_name(type_of(obj)) + "' object has no attribute '" + d->name->text + "'");
                    out = Ref::share(v);
                });
                return out;
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
Ref get_native(Obj self, Args a) {             // __get__ of the C++ descriptors (wrap_descr_get)
    if (a.nkw != 0) raise_new("TypeError", "wrapper __get__() takes no keyword arguments");
    if (a.npos < 1) raise_new("TypeError", "__get__ expected at least 1 argument, got 0");
    if (a.npos > 2) raise_new("TypeError", "__get__ expected at most 2 arguments, got " + std::to_string(a.npos));
    Obj obj = a.pos(0);
    Obj type = a.npos > 1 ? a.pos(1) : None();
    if (is_none(obj) && is_none(type)) raise_new("TypeError", "__get__(None, None) is invalid");
    return descr_get(self, obj, type);
}
// a member is a __slots__ member (object.hpp's) or a C++ getset presented as one
std::string descriptor_text(Obj self) {
    if (is_kind(self, Kind::SlotDescriptor)) return static_cast<SlotDescriptor*>(self.object())->name->text;
    return static_cast<GetSet*>(self.object())->name;
}
ClassObject* descriptor_owner(Obj self) {
    if (is_kind(self, Kind::SlotDescriptor)) return static_cast<SlotDescriptor*>(self.object())->owner;
    return static_cast<GetSet*>(self.object())->owner;
}
Ref descriptor_name(Obj self) { return str_new(descriptor_text(self)); }
Ref descriptor_objclass(Obj self) { return Ref::share(Obj::of(descriptor_owner(self))); }
Ref descriptor_qualname(Obj self) {              // descr_get_qualname: the type's qualified name, a dot, its own
    Ref owner = getattr(Obj::of(descriptor_owner(self)), N("__qualname__"));
    return str_new(as_str(owner.get())->text + "." + descriptor_text(self));
}
// descr_setcheck: a getset's __set__ and __delete__ take what its __get__ takes
void check_descriptor_applies(Obj self, Obj obj) {
    ClassObject* owner = descriptor_owner(self);
    if (!isinstance(obj, owner))
        raise_new("TypeError", "descriptor '" + descriptor_text(self) + "' for '" + owner->name + "' objects doesn't apply to a '" + type_of(obj)->name + "' object");
}
Ref getset_set(Obj self, Args a) {
    arity(a, "__set__", 2, 2);
    if (is_kind(self, Kind::SlotDescriptor)) {   // member_set: the field itself, whatever the class's __setattr__ does
        auto* d = static_cast<SlotDescriptor*>(self.object());
        check_member_applies(d, a.pos(0));
        with_attribute_storage(a.pos(0), [&](auto* inst) {
            incref(a.pos(1));
            decref(std::exchange(inst->field(d->name), a.pos(1)));
        });
        return none_ref();
    }
    auto* g = static_cast<GetSet*>(self.object());
    check_descriptor_applies(self, a.pos(0));
    if (g->set == nullptr) {
        if (g->cls == types().member_descriptor) raise_new("AttributeError", "readonly attribute");
        raise_new("AttributeError", std::string("attribute '") + g->name + "' of '" + g->owner->name + "' objects is not writable");
    }
    g->set(a.pos(0), a.pos(1));
    return none_ref();
}
Ref getset_delete(Obj self, Args a) {
    if (a.nkw != 0) raise_new("TypeError", "wrapper __delete__() takes no keyword arguments");
    if (a.npos != 1) raise_new("TypeError", "expected 1 argument, got " + std::to_string(a.npos));   // wrap_descr_delete
    if (is_kind(self, Kind::SlotDescriptor)) {
        auto* d = static_cast<SlotDescriptor*>(self.object());
        check_member_applies(d, a.pos(0));
        with_attribute_storage(a.pos(0), [&](auto* inst) {
            if (inst->field(d->name).is_unset()) raise_attribute_error(a.pos(0), d->name, d->name->text);
            decref(std::exchange(inst->field(d->name), Obj{}));
        });
        return none_ref();
    }
    auto* g = static_cast<GetSet*>(self.object());
    check_descriptor_applies(self, a.pos(0));
    if (g->set == nullptr) {                     // getset_set: no setter, for storing and deleting alike
        if (g->cls == types().member_descriptor) raise_new("AttributeError", "readonly attribute");
        raise_new("AttributeError", std::string("attribute '") + g->name + "' of '" + g->owner->name + "' objects is not writable");
    }
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
        refuse_shadowed(cls->mro, 0, name);
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
        raise_new("TypeError", "cannot set '" + name->text + "' attribute of immutable type '" + cls->name + "'");
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
    if (!found.is_unset()) refuse_shadowed(c->mro, 0, name);
    if (obj == None() && is_kind(found, Kind::Builtin)) {   // descr_get's None means no instance; here it is the instance
        auto* b = static_cast<Builtin*>(found.object());
        if (b->self.is_unset() && b->binding == Binding::Method) {
            Ref bound = own(new Builtin(b->name, b->fn, obj));
            static_cast<Builtin*>(bound.get().object())->owner = b->owner;
            return bound;
        }
    }
    if (obj == None() && is_kind(found, Kind::GetSet)) return static_cast<GetSet*>(found.object())->get(obj);
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
    if (cpython_attribute_kind(cls, "__new__").empty())   // no tp_new of its own on object: Py_TPFLAGS_DISALLOW_INSTANTIATION
        raise_new("TypeError", "cannot create '" + cls->name + "' instances");
    throw NotImplemented("creating an instance of the built-in type '" + cls->name + "' (CPython has it; the runtime does not yet)");
}

// solid_base and best_base (Objects/typeobject.c): the layout a class extends is the nearest class
// with a shape of its own (slots, or a built-in's data); tp_base is the base whose solid base is the
// most derived of the bases'
ClassObject* solid_base(ClassObject* c) {
    if (c == types().object) return c;
    auto slots = c->own_slot_names();
    bool own_slots = std::any_of(slots.begin(), slots.end(), [](const Str* s) { return s->text != "__dict__"; });
    // shape_differs: an exception type shares its base's C struct unless it adds fields
    bool exception = is_subclass(c, exception_class("BaseException"));
    bool own_shape = exception ? (c == exception_class("BaseException") || (!c->heap_type && c->native != c->bases[0]->native))
                               : !c->heap_type;
    if (own_shape || own_slots) return c;
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
    if (!cls->heap_type && cls != types().object && new_slot(cls) == new_slot(types().object)) {  // the runtime has no __new__ of its own for it
        if (cpython_attribute_kind(cls, "__new__").empty()) refuse_construction(cls);
        raise_new("TypeError", "object.__new__(" + cls->name + ") is not safe, use " + cls->name + ".__new__()");
    }
    new_wrapper_class(a, types().object);        // tp_new_wrapper's check, before the arguments'
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
    if (cls->has("__getattribute__") && type_lookup(cls, N("__getattribute__")) != type_lookup(types().object, N("__getattribute__")) &&
        !is_kind(type_lookup(cls, N("__getattribute__")), Kind::Builtin))   // _thread._local's is no program's
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
    if (cls == types().type && a.npos != 3) raise_new("TypeError", "type() takes 1 or 3 arguments");
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

namespace {
// pmerge's error (set_mro_error): the classes at the heads of the lists left when the merge stops,
// each once, in list order
std::string mro_conflict(const std::vector<ClassObject*>& bases) {
    std::vector<std::vector<ClassObject*>> lists;
    for (ClassObject* b : bases) lists.push_back(b->mro);
    lists.push_back(bases);
    std::vector<std::size_t> at(lists.size(), 0);
    for (;;) {
        ClassObject* head = nullptr;
        for (std::size_t i = 0; i < lists.size() && head == nullptr; ++i) {
            if (at[i] >= lists[i].size()) continue;
            ClassObject* candidate = lists[i][at[i]];
            bool in_tail = false;
            for (std::size_t j = 0; j < lists.size() && !in_tail; ++j)
                in_tail = at[j] < lists[j].size() && std::find(lists[j].begin() + static_cast<std::ptrdiff_t>(at[j]) + 1, lists[j].end(), candidate) != lists[j].end();
            if (!in_tail) head = candidate;
        }
        if (head == nullptr) break;
        for (std::size_t i = 0; i < lists.size(); ++i)
            if (at[i] < lists[i].size() && lists[i][at[i]] == head) ++at[i];
    }
    std::vector<ClassObject*> seen;
    std::string names;
    for (std::size_t i = 0; i < lists.size(); ++i) {
        if (at[i] >= lists[i].size() || std::find(seen.begin(), seen.end(), lists[i][at[i]]) != seen.end()) continue;
        seen.push_back(lists[i][at[i]]);
        names += (names.empty() ? "" : ", ") + lists[i][at[i]]->name;
    }
    return names;
}
// mro_invoke with a custom metaclass: its mro(), a sequence made a tuple and checked (mro_check), is
// the class's MRO (RefClass.set_mro)
void mro_invoke(ClassObject* c) {
    Ref result = call_special(Obj::of(c), "mro", {});
    Ref it = iter(result.get());
    std::vector<ClassObject*> mro;
    std::vector<Ref> held;
    for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get())) {
        if (!is_kind(v.get(), Kind::Class))
            raise_new("TypeError", c->name + ".mro() returned a non-class ('" + type_of(v.get())->name + "')");
        ClassObject* b = static_cast<ClassObject*>(v.get().object());
        if (!is_subclass(solid_base(c), solid_base(b)))
            raise_new("TypeError", c->name + ".mro() returned base with unsuitable layout ('" + b->name + "')");
        mro.push_back(b);
        held.push_back(std::move(v));
    }
    if (mro.empty()) raise_new("TypeError", "type MRO must not be empty");
    c->set_mro(std::move(mro));
}
}  // namespace

Ref first_weakref(Obj self) {                     // subtype_getweakref: the head of the list
    if (!type_of(self)->has_weakref) raise_new("AttributeError", "This object has no __weakref__");
    if (auto* list = weak_list(self.object()); list != nullptr && !list->empty()) return Ref::share(Obj::of(list->front()->holder));
    return none_ref();
}
GetSet* weakref_getset() {                        // CPython's belongs to object, whichever class it is put in
    static GetSet* g = [] {
        auto* d = new GetSet("__weakref__", types().object, first_weakref, nullptr);
        d->flags |= IMMORTAL;
        return d;
    }();
    return g;
}

Ref type_new(ClassObject* meta, Obj name_obj, Obj bases_obj, Obj ns_obj, Args kw) {
    const Str* name = as_str(name_obj);
    if (name == nullptr) raise_new("TypeError", "type.__new__() argument 1 must be str, not " + type_of(name_obj)->name);
    if (!is_kind(bases_obj, Kind::Tuple))
        raise_new("TypeError", "type.__new__() argument 2 must be tuple, not " + type_of(bases_obj)->name);
    if (!is_kind(ns_obj, Kind::Dict))
        raise_new("TypeError", "type.__new__() argument 3 must be dict or frozendict, not " + type_of(ns_obj)->name);
    if (name->text.find('\0') != std::string::npos) raise_new("ValueError", "type name must not contain null characters");
    {                                            // best_base: one instance layout must extend the others
        ClassObject* winner = nullptr;
        for (Obj b : static_cast<Tuple*>(bases_obj.object())->items) {
            ClassObject* bc = as_class(b);
            if (bc == nullptr) continue;         // "bases must be types", below
            ClassObject* candidate = solid_base(bc);
            if (winner == nullptr || is_subclass(candidate, winner)) winner = candidate;
            else if (!is_subclass(winner, candidate)) raise_new("TypeError", "multiple bases have instance lay-out conflict");
        }
    }
    std::vector<ClassObject*> bases;
    for (Obj b : static_cast<Tuple*>(bases_obj.object())->items) {
        ClassObject* bc = as_class(b);
        if (bc == nullptr) raise_new("TypeError", "bases must be types");
        if (std::find(bases.begin(), bases.end(), bc) != bases.end())       // A9-9
            raise_new("TypeError", "duplicate base class " + bc->name);
        if (bc->final_type) raise_new("TypeError", "type '" + bc->name + "' is not an acceptable base type");
        if (!bc->heap_type && bc != types().object && bc != types().type && bc != types().dict && bc != types().frozendict && bc != types().int_ && bc != types().float_ &&
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
        bool base_dict = std::any_of(bases.begin(), bases.end(), [](ClassObject* b) { return b->has_dict && !b->dict_without_getset; });
        for (Ref& item : items) {
            const Str* s = as_str(item.get());
            if (s == nullptr) raise_new("TypeError", "__slots__ items must be strings, not '" + type_of(item.get())->name + "'");
            if (!s->ascii) throw NotImplemented("a __slots__ name beyond ASCII (identifier rules need the Unicode database)");
            bool ident = !s->text.empty() && !std::isdigit(static_cast<unsigned char>(s->text[0])) &&
                         std::all_of(s->text.begin(), s->text.end(), [](char c) { return std::isalnum(static_cast<unsigned char>(c)) || c == '_'; });
            if (!ident) raise_new("TypeError", "__slots__ must be identifiers");
            if (s->text == "__weakref__") {          // may_add_weak: no base with room
                bool base_weak = std::any_of(bases.begin(), bases.end(), [](ClassObject* b) { return b->has_weakref; });
                if (base_weak || std::find(slots.begin(), slots.end(), "__weakref__") != slots.end())
                    raise_new("TypeError", "__weakref__ slot disallowed: we already got one");
                slots.push_back(s->text);
                continue;
            }
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
        // an int subclass's instances have a variable size: only __dict__ may be a slot
        bool int_based = std::any_of(bases.begin(), bases.end(), [](ClassObject* b) { return is_subclass(b, types().int_); });
        if (int_based && std::any_of(slots.begin(), slots.end(), [](const std::string& n) { return n != "__dict__" && n != "__weakref__"; }))
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
    // type_new_set_module: __module__ from the globals of the frame calling type() (a class statement's
    // namespace has its own)
    Ref module_name;
    if (dict_get(ns, Obj::of(N("__module__"))).is_unset())
        if (detail::FrameRecord* frame = detail::current_frame(); frame != nullptr && frame->module != nullptr) {
            module_name = Ref::share(dict_get(frame->module->dict, Obj::of(N("__name__"))));
            if (!module_name.get().is_unset()) spec.attrs.emplace_back("__module__", module_name.get());
        }
    ClassObject* c = nullptr;
    try {
        c = make_class(spec);
    } catch (const bella::TypeError&) {                     // the C3 merge failed (A9-9)
        raise_new("TypeError", "Cannot create a consistent method resolution order (MRO) for bases " + mro_conflict(bases));
    }
    c->cls = meta;
    c->qualname = qualname;
    c->heap_type = true;
    bool base_has_dict = std::any_of(bases.begin(), bases.end(), [](ClassObject* b) { return b->has_dict && !b->dict_without_getset; });
    // type_ready's order: the getsets (__dict__, __weakref__) and only then the members. The room for weak
    // references comes by itself unless the object has a variable size, as an int's has; a slot asks for it there
    std::vector<std::pair<const Str*, Ref>> members;
    for (auto& [k, v] : c->attrs.items())
        if (is_kind(v, Kind::SlotDescriptor)) members.emplace_back(k, Ref::steal(c->attrs.pop(k)));
    bool slots_refuse_dict = c->slots && std::any_of(bases.begin(), bases.end(), [](ClassObject* b) { return b->dict_without_getset; }) &&
                             std::find(c->slots->begin(), c->slots->end(), N("__dict__")) == c->slots->end();
    c->dict_without_getset = slots_refuse_dict;
    if (c->has_dict && !base_has_dict && !slots_refuse_dict && !c->attrs.contains(N("__dict__")))    // the class body's stands
        c->attrs.set(N("__dict__"), Obj::of(instance_dict_getset()));
    bool base_has_weak = std::any_of(bases.begin(), bases.end(), [](ClassObject* b) { return b->has_weakref; });
    bool asked_weak = c->slots && std::find(c->slots->begin(), c->slots->end(), N("__weakref__")) != c->slots->end();
    if (!base_has_weak && !asked_weak && std::any_of(bases.begin(), bases.end(), [](ClassObject* b) { return is_subclass(b, types().int_); }))
        c->has_weakref = false;
    if (c->has_weakref && !base_has_weak && !c->attrs.contains(N("__weakref__")))
        c->attrs.set(N("__weakref__"), Obj::of(weakref_getset()));
    // A metaclass's mro() is the first code that can see the class, and may keep a view of its dict:
    // from here each insertion goes through set_attr.
    if (meta != types().type) mro_invoke(c);
    for (auto& [k, v] : members)
        if (!c->attrs.contains(k)) c->set_attr(k, v.get());
    if (!c->attrs.contains(N("__doc__"))) c->set_attr(N("__doc__"), None());   // type_dict_set_doc: after the getsets
    if (has_eq && !has_hash) c->set_attr(N("__hash__"), None());               // type_ready_set_hash: then __hash__
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
    // type_new_set_names: __set_name__, in the order of the class's attributes; what it raises gets a note
    for (auto& [k, v] : c->attrs.items()) {
        bool found = false;
        Ref hold = Ref::share(v);
        try {
            Ref r = call_special(v, "__set_name__", {Obj::of(c), Obj::of(k)}, &found);
        } catch (const PyError& e) {
            Ref key = repr_of(Obj::of(k));
            add_note(e.exc.get(), "Error calling __set_name__ on '" + type_of(v)->name + "' instance " + as_str(key.get())->text + " in '" + c->name + "'");
            throw;
        }
    }
    // __init_subclass__ of the class after this one in the MRO (super(type, type)), bound to the new class
    auto own_place = std::find(c->mro.begin(), c->mro.end(), c);
    if (own_place == c->mro.end())               // a metaclass's mro() left the class out: supercheck
        raise_new("TypeError", "super(type, obj): obj (type " + c->name + ") is not an instance or subtype of type (" + c->name + ").");
    for (std::size_t i = static_cast<std::size_t>(own_place - c->mro.begin()) + 1; i < c->mro.size(); ++i) {
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
// list_new, tuple_new, unicode_new, bool_new: an instance of the type, its arguments its constructor's
// (a list fills itself in __init__, so __new__ ignores them)
Ref builtin_new_m(Obj self, Args a) {
    ClassObject* type = as_class(self);
    ClassObject* cls = new_wrapper_class(a, type);
    if (cls == types().list) return list_new({});
    return invoke(Obj::of(cls), Args{a.data + 1, a.npos - 1, a.kwnames, a.nkw});
}
Ref dict_new_m(Obj, Args a) {
    ClassObject* cls = new_wrapper_class(a, types().dict);
    if (cls == types().dict) return dict_new();
    return own(new DictInstance(cls));
}
// frozendict_new: filled here, since nothing can fill it later (a program's __init__ cannot)
Ref frozendict_new_m(Obj, Args a) {
    ClassObject* cls = new_wrapper_class(a, types().frozendict);
    if (a.npos > 2) raise_new("TypeError", "frozendict expected at most 1 argument, got " + std::to_string(a.npos - 1));
    Ref self = frozendict_empty(cls);
    if (a.npos == 2) dict_update_arg(self.get(), a.pos(1));
    for (std::size_t i = 0; i < a.nkw; ++i) dict_set(static_cast<Dict*>(self.get().object()), Obj::of(a.kwnames[i]), a.kw(i));
    return self;
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
Ref int_ref(std::int64_t v) { return int_from_i64(v); }
// PyLong_FromString on an ASCII str: whitespace around it (Py_ISSPACE), a sign, the base's prefix,
// single underscores between digits; a ValueError names the base given and the string's repr
template <class Invalid>
Ref int_from_text(const std::string& t, std::int64_t base, Invalid invalid) {
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
    int limit = max_str_digits();
    if (!binary_base && digits > 640 && limit > 0 && digits > static_cast<std::size_t>(limit))
        raise_new("ValueError", "Exceeds the limit (" + std::to_string(limit) + " digits) for integer string conversion: value has " +
                                    std::to_string(digits) + " digits; use sys.set_int_max_str_digits() to increase the limit");
    std::string clean;
    clean.reserve(digits);
    for (std::size_t k = start; k < end; ++k)
        if (t[k] != '_') clean += t[k];
    Ref value = int_from_digits(negative, clean, static_cast<int>(b));
    if (error_if_nonzero && !int_is_zero(value.get())) {
        invalid();
    }
    return value;
}

Ref int_from_str(const Str* s, std::int64_t base) {
    if (!s->ascii) throw NotImplemented("int() of a str beyond ASCII (its digits and spaces need the Unicode database)");
    return int_from_text(s->text, base, [&]() -> Ref {
        Ref r = repr_of(Obj::of(s));
        const Str* rs = as_str(r.get());
        std::u32string shown;                       // %.200R: the repr, cut at 200 code points
        for (std::size_t k = 0; k < std::min<std::size_t>(rs->length, 200); ++k) shown += rs->at(k);
        Ref cut = str_from_codepoints(shown);
        raise_new("ValueError", "invalid literal for int() with base " + std::to_string(base) + ": " + as_str(cut.get())->text);
    });
}
// PyLong_FromString on a bytes-like object's octets: ASCII digits and spaces, and a message showing it
Ref int_from_bytes(Obj x, std::int64_t base) {
    const std::string b = bytes_data(x);
    bool usable = std::none_of(b.begin(), b.end(), [](char c) { auto u = static_cast<unsigned char>(c); return u >= 0x80 || (u >= 0x1C && u <= 0x1F); });
    auto invalid = [&]() -> Ref {
        Ref copy = bytes_new(b);                 // shown as bytes, whichever it was
        Ref r = bytes_repr(copy.get());
        const Str* rs = as_str(r.get());
        std::u32string shown;
        for (std::size_t k = 0; k < std::min<std::size_t>(rs->length, 200); ++k) shown += rs->at(k);
        Ref cut = str_from_codepoints(shown);
        raise_new("ValueError", "invalid literal for int() with base " + std::to_string(base) + ": " + as_str(cut.get())->text);
    };
    if (!usable) invalid();
    return int_from_text(b, base, invalid);
}
// PyNumber_Long: an int as itself (a subclass's value as an exact int), __int__, __index__, a str
Ref number_long(Obj x) {
    if (x.is_small() || is_kind(x, Kind::BigInt)) return Ref::share(x);
    bool python = is_kind(x, Kind::Instance) || is_subclass_instance(x) || has_python_type(x);
    if (python && !type_lookup(type_of(x), N("__int__")).is_unset() &&
        !(is_subclass_instance(x) && !overrides_builtin(x, "__int__"))) {
        Ref r = call_special(x, "__int__", {});
        if (!is_int(r.get()))
            raise_new("TypeError", fully_qualified_name(type_of(x)) + ".__int__() must return an int, not " +
                                       fully_qualified_name(type_of(r.get())));
        if (!r.get().is_small() && !is_kind(r.get(), Kind::BigInt))   // CPython copies a strict subclass's value with a DeprecationWarning
            throw NotImplemented("__int__ returning an instance of a subclass of int (a DeprecationWarning in CPython)");
        return r;
    }
    if (is_int(x)) return big_plain(x);           // a bool, an int subclass's instance: nb_int, an exact copy
    if (is_float(x)) return int_from_double(float_value(x));   // float_int, its nb_int
    if (python && !type_lookup(type_of(x), N("__index__")).is_unset()) return int_index_of(x);
    if (const Str* s = as_str(x)) return int_from_str(s, 10);
    if (is_bytes_like(x)) return int_from_bytes(x, 10);
    raise_new("TypeError", "int() argument must be a string, a bytes-like object or a real number, not '" + type_of(x)->name + "'");
}

// int.__new__(cls, x=0, /, base=10) (long_new_impl; a subclass's instance carries the value,
// long_subtype_new)
Ref int_new_m(Obj, Args a) {
    ClassObject* cls = new_wrapper_class(a, types().int_);
    std::size_t npos = a.npos - 1;
    if (npos + a.nkw > 2) {                      // long_vectorcall for int itself; a subclass's goes through long_new
        if (a.nkw == 0 && cls == types().int_) raise_new("TypeError", "int expected at most 2 arguments, got " + std::to_string(npos));
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
        std::int64_t b = clipped_index(base);         // PyNumber_AsSsize_t(obase, NULL)
        if ((b != 0 && b < 2) || b > 36) raise_new("ValueError", "int() base must be >= 2 and <= 36, or 0");
        const Str* s = as_str(x);
        if (s == nullptr && !is_bytes_like(x)) raise_new("TypeError", "int() can't convert non-string with explicit base");
        value = s != nullptr ? int_from_str(s, b) : int_from_bytes(x, b);
    }
    if (cls == types().int_) return value;
    if (value.get().is_small()) return own(new IntInstance(cls, value.get().small_value()));
    auto* big = static_cast<BigInt*>(value.get().object());
    auto* instance = new IntInstance(cls, 0);
    instance->limbs = big->limbs;
    instance->negative = big->negative;
    return own(instance);
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
// merge_class_dict: a class's names and its bases', for dir(). A built-in type has CPython's whole
// list in the names table, where the runtime has only those it has written; __weakref__ is a name
// every class has that makes room for it, though its dict has none until step 3c (RL-323).
void merge_class_dict(Obj names, Obj aclass) {
    auto* d = static_cast<Dict*>(names.object());
    if (ClassObject* c = as_class(aclass)) {
        std::vector<std::string_view> table;
        if (immutable_type(c)) table = cpython_names_of(std::string_view(c->name).substr(c->name_prefix));
        for (std::string_view n : table) dict_set(d, Obj::of(intern(n)), None());
        if (c == types().type) dict_set(d, Obj::of(N("__abstractmethods__")), None());   // left out of the table: most classes raise
        if (table.empty())
            for (auto& [k, v] : c->attrs.items()) dict_set(d, Obj::of(k), None());
        for (ClassObject* base : c->bases) merge_class_dict(names, Obj::of(base));
        return;
    }
    Ref classdict = optional_getattr(aclass, N("__dict__"));   // an object a lying __class__ names
    if (!classdict.get().is_unset()) dict_update(names, classdict.get());
    Ref bases = optional_getattr(aclass, N("__bases__"));
    if (bases.get().is_unset()) return;
    Ref it = iter(bases.get());
    for (Ref base = for_next(it.get()); !is_end(base); base = for_next(it.get())) merge_class_dict(names, base.get());
}
Ref dict_keys_list(Obj names) {
    Ref out = list_new({});
    auto* d = static_cast<Dict*>(names.object());
    for (const auto& e : d->entries)
        if (!e.key.is_unset()) list_append(out.get(), e.key);
    return out;
}
Ref object_dir(Obj self, Args a) {               // object___dir___impl
    noargs(a, "object.__dir__");
    // the prelude's property keeps in its dict what CPython keeps in C fields
    Ref dict = immutable_type(type_of(self)) && !type_of(self)->dict_without_getset ? Ref{} : optional_getattr(self, N("__dict__"));
    Ref names = is_dict(dict.get()) ? dict_copy(static_cast<Dict*>(dict.get().object())) : dict_new();
    Ref itsclass = optional_getattr(self, N("__class__"));
    if (!itsclass.get().is_unset()) merge_class_dict(names.get(), itsclass.get());
    return dict_keys_list(names.get());
}
Ref type_dir(Obj self, Args a) {                 // type___dir___impl
    noargs(a, "type.__dir__");
    Ref names = dict_new();
    merge_class_dict(names.get(), self);
    return dict_keys_list(names.get());
}
Ref object_subclasshook(Obj, Args a) {
    onearg(a, "object.__subclasshook__");
    return Ref::steal(Obj::of(NOTIMPLEMENTED));
}
// type.__subclasses__: the direct subclasses, oldest first. A built-in type's answer names the
// interpreter's own classes too, which a compiled program does not have.
Ref type_subclasses(Obj self, Args a) {
    ClassObject* c = as_class(self);
    noargs(a, c->qualname + ".__subclasses__");
    if (!c->heap_type) throw NotImplemented("the subclasses of the built-in type '" + c->name + "': CPython's list names its own classes");
    Ref l = list_new({});
    for (ClassObject* s : c->subclasses) list_append(l.get(), Obj::of(s));
    return l;
}
Ref type_mro(Obj self, Args a) {
    arity(a, "mro", 0, 0);
    Ref l = list_new({});
    for (ClassObject* m : c3(as_class(self))) list_append(l.get(), Obj::of(m));
    return l;
}
Ref type_repr(Obj self, Args) { return type_repr_of(self); }

// object's methods
void one_argument(Args a, const char* name) {    // wrap_binaryfunc: check_num_args
    if (a.nkw != 0) raise_new("TypeError", std::string("wrapper ") + name + "() takes no keyword arguments");
    if (a.npos != 1) raise_new("TypeError", "expected 1 argument, got " + std::to_string(a.npos));
}
Ref object_eq(Obj self, Args a) {
    one_argument(a, "__eq__");
    return Ref::steal(self == a.pos(0) ? boolean(true) : Obj::of(NOTIMPLEMENTED));
}
Ref object_ne(Obj self, Args a) {             // inverts __eq__ unless it returned NotImplemented
    one_argument(a, "__ne__");
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
Ref object_init_subclass(Obj self, Args a) {
    if (a.nkw != 0) raise_new("TypeError", as_class(self)->name + ".__init_subclass__() takes no keyword arguments");
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
        } catch (const bella::AttributeError& e) {
            raise_attribute_error(self, intern(n->text), std::string(e.what()).find(' ') == std::string::npos
                                                             ? "'" + type_of(self)->name + "' object has no attribute '" + n->text + "'"
                                                             : std::string(e.what()));
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
        } catch (const bella::AttributeError& e) {
            raise_delete_failed(self, intern(n->text), e.what());
        }
    });
    return none_ref();
}
Ref object_format(Obj self, Args a) {
    onearg(a, "object.__format__");
    const Str* spec = as_str(a.pos(0));
    if (spec == nullptr) raise_new("TypeError", "__format__() argument must be str, not " + (a.pos(0) == None() ? std::string("None") : type_of(a.pos(0))->name));
    if (spec->length != 0)
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
    } else if (!is_dict(d)) {
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
Ref type_name(Obj self) { return str_new(self_class(self)->name.substr(self_class(self)->name_prefix)); }
// check_set_special_type_attr: a delete is refused first, then a store to an immutable type
void check_special(ClassObject* c, Obj v, const char* name) {
    if (immutable_type(c)) raise_new("TypeError", std::string("cannot set '") + name + "' attribute of immutable type '" + c->name + "'");
    if (v.is_unset()) raise_new("TypeError", std::string("cannot delete '") + name + "' attribute of type '" + c->name + "'");
}
void set_type_name(Obj self, Obj v) {
    ClassObject* c = self_class(self);
    check_special(c, v, "__name__");
    const Str* s = as_str(v);
    if (s == nullptr) raise_new("TypeError", "can only assign string to " + c->name + ".__name__, not '" + type_of(v)->name + "'");
    c->name = s->text;
    c->name_prefix = 0;
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
    if (!c->heap_type) {                         // a built-in type's module: its tp_name's prefix, else builtins
        const Obj* m = c->attrs.find(N("__module__"));
        return m != nullptr && as_str(*m) != nullptr ? Ref::share(*m) : str_new("builtins");
    }
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
    if (!c->heap_type)                           // type_get_doc: a static type's tp_doc
        if (Obj d = cpython_doc(c->name); d != None()) return Ref::share(d);
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
Ref fn_module(Obj self) {                        // set from the globals when made; func.__module__ may be rebound
    if (!fn_of(self)->module_name.get().is_unset()) return fn_of(self)->module_name;
    Obj n = dict_get(fn_of(self)->module->dict, Obj::of(N("__name__")));
    return n.is_unset() ? none_ref() : Ref::share(n);
}
void set_fn_module(Obj self, Obj v) { fn_of(self)->module_name = v.is_unset() ? none_ref() : Ref::share(v); }
Ref fn_defaults(Obj self) { return fn_of(self)->defaults.get().is_unset() ? none_ref() : fn_of(self)->defaults; }
Ref fn_kwdefaults(Obj self) { return fn_of(self)->kwdefaults.get().is_unset() ? none_ref() : fn_of(self)->kwdefaults; }
Ref fn_annotate(Obj self) { return fn_of(self)->annotate.get().is_unset() ? none_ref() : fn_of(self)->annotate; }
void set_fn_annotate(Obj self, Obj v) {          // function___annotate___set_impl
    if (v.is_unset()) raise_new("TypeError", "__annotate__ cannot be deleted");
    if (v != None() && !callable_check(v)) raise_new("TypeError", "__annotate__ must be callable or None");
    fn_of(self)->annotate = Ref::share(v);
}
Ref fn_type_params(Obj self) { return fn_of(self)->type_params.get().is_unset() ? tuple_new({}) : fn_of(self)->type_params; }
void set_fn_type_params(Obj self, Obj v) {       // function___type_params___set_impl
    if (v.is_unset() || !is_kind(v, Kind::Tuple)) raise_new("TypeError", "__type_params__ must be set to a tuple");
    fn_of(self)->type_params = Ref::share(v);
}
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
    if (b->home != nullptr) return Ref::share(Obj::of(b->home));
    if (b->self.is_unset() && b->binding == Binding::Function && b->owner != nullptr &&
        cpython_attribute_kind(b->owner, b->name) == "builtin_function_or_method")
        return Ref::share(Obj::of(b->owner));                       // object.__new__.__self__ is object
    return b->self.is_unset() ? none_ref() : Ref::share(b->self);
}
Ref builtin_qualname(Obj self) {                 // meth_get__qualname__
    Ref name = builtin_name(self);
    Ref bound = builtin_self(self);
    if (bound.get() == None() || is_kind(bound.get(), Kind::Module)) return name;
    Obj owner = is_kind(bound.get(), Kind::Class) ? bound.get() : Obj::of(type_of(bound.get()));
    Ref qualname = getattr(owner, N("__qualname__"));
    return str_new(as_str(qualname.get())->text + "." + as_str(name.get())->text);
}
Ref builtin_module(Obj self) {                   // m_module: None for a method, and once deleted
    if (is_kind(self, Kind::PyFunction)) return fn_module(self);    // the prelude's print
    auto* b = static_cast<Builtin*>(self.object());
    return b->module_name.get().is_unset() ? none_ref() : Ref::share(b->module_name.get());
}
void set_builtin_module(Obj self, Obj value) {
    if (is_kind(self, Kind::PyFunction)) {
        set_fn_module(self, value);
        return;
    }
    static_cast<Builtin*>(self.object())->module_name = value.is_unset() ? Ref{} : Ref::share(value);
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
// mappingproxy reads a dict: a key is hashed, whether it could be an attribute's name or not
Ref proxy_getitem(Obj self, Args a) {
    arity(a, "__getitem__", 1, 1);
    dict_key_hash(a.pos(0));
    const Str* k = as_str(a.pos(0));
    if (k != nullptr)
        if (const Obj* v = proxied(self)->attrs.find(intern(k->text))) return Ref::share(*v);
    Ref exc = invoke(Obj::of(exception_class("KeyError")), {a.pos(0)});
    raise(exc.get());
}
Ref proxy_contains(Obj self, Args a) {
    arity(a, "__contains__", 1, 1);
    dict_key_hash(a.pos(0));
    const Str* k = as_str(a.pos(0));
    return Ref::steal(boolean(k != nullptr && proxied(self)->attrs.contains(intern(k->text))));
}
Ref proxy_get(Obj self, Args a) {
    arity(a, "get", 1, 2);
    dict_key_hash(a.pos(0));
    const Str* k = as_str(a.pos(0));
    if (k != nullptr)
        if (const Obj* v = proxied(self)->attrs.find(intern(k->text))) return Ref::share(*v);
    return a.npos > 1 ? Ref::share(a.pos(1)) : none_ref();
}
Ref proxy_len(Obj self, Args) { return Ref::steal(Obj::small(static_cast<std::int64_t>(proxied(self)->attrs.size()))); }
// What a program reaches through the proxy's dict: the class's dict, live (ClassObject::dict_view)
Obj class_dict(Obj self) {
    ClassObject* c = proxied(self);
    if (c->dict_view == nullptr) {
        Ref d = dict_new();
        for (auto& [k, v] : c->attrs.items()) dict_set(static_cast<Dict*>(d.get().object()), Obj::of(k), v);
        c->dict_view = static_cast<Dict*>(d.release().object());
    }
    return Obj::of(c->dict_view);
}
Ref proxy_mapping_call(Obj self, const char* name) {   // mappingproxy_keys and the others: the mapping's own method
    Ref f = getattr(class_dict(self), N(name));
    return invoke(f.get(), {});
}
Ref proxy_keys(Obj self, Args a) { noargs(a, "mappingproxy.keys"); return proxy_mapping_call(self, "keys"); }
Ref proxy_values(Obj self, Args a) { noargs(a, "mappingproxy.values"); return proxy_mapping_call(self, "values"); }
Ref proxy_items(Obj self, Args a) { noargs(a, "mappingproxy.items"); return proxy_mapping_call(self, "items"); }
Ref proxy_copy(Obj self, Args a) { noargs(a, "mappingproxy.copy"); return proxy_mapping_call(self, "copy"); }
Ref proxy_iter(Obj self, Args a) { dunder_args(self, a, "__iter__", 0); return iter(class_dict(self)); }
Ref proxy_repr(Obj self, Args a) {
    dunder_args(self, a, "__repr__", 0);
    Ref text = repr_of(class_dict(self));
    return str_new("mappingproxy(" + as_str(text.get())->text + ")");
}
Ref proxy_str(Obj self, Args a) { dunder_args(self, a, "__str__", 0); return str_of(class_dict(self)); }
Ref proxy_hash(Obj self, Args a) {               // mappingproxy_hash: the mapping's, and a dict has none
    dunder_args(self, a, "__hash__", 0);
    return Ref::steal(Obj::small(hash_of(class_dict(self))));
}
// mappingproxy_richcompare: the mapping against the other, for == and != only
Ref proxy_eq(Obj self, Args a) { dunder_args(self, a, "__eq__", 1); return compare(CmpOp::Eq, class_dict(self), a.pos(0)); }
Ref proxy_ne(Obj self, Args a) { dunder_args(self, a, "__ne__", 1); return compare(CmpOp::Ne, class_dict(self), a.pos(0)); }

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
Ref exception_new(Obj self, Args a) {
    ClassObject* cls = new_wrapper_class(a, as_class(self));
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
void set_args(Obj self, Args a) {                // BaseException_init's args
    std::vector<Obj> items;
    for (std::size_t i = 0; i < a.npos; ++i) {
        incref(a.pos(i));
        items.push_back(a.pos(i));
    }
    Ref args = tuple_steal(std::move(items));
    set_exception_field(self, "args", args.get());
}
Ref exception_init(Obj self, Args a) {
    if (a.nkw != 0) raise_new("TypeError", type_of(self)->name + "() takes no keyword arguments");
    set_args(self, a);
    return none_ref();
}
// AttributeError_init, NameError_init: "|$OO:AttributeError" and "|$O:NameError"
Ref attribute_error_init(Obj self, Args a) {
    set_args(self, a);
    Obj name, obj;
    for (std::size_t k = 0; k < a.nkw; ++k) {
        std::string_view n = a.kwnames[k]->text;
        if (n == "name") name = a.kw(k);
        else if (n == "obj") obj = a.kw(k);
        else unexpected_keyword("AttributeError()", a.kwnames[k], {"name", "obj"});
    }
    set_exception_field(self, "name", name);
    set_exception_field(self, "obj", obj);
    return none_ref();
}
Ref name_error_init(Obj self, Args a) {
    set_args(self, a);
    Obj name;
    for (std::size_t k = 0; k < a.nkw; ++k) {
        if (a.kwnames[k]->text == "name") name = a.kw(k);
        else unexpected_keyword("NameError()", a.kwnames[k], {"name"});
    }
    set_exception_field(self, "name", name);
    return none_ref();
}
// SystemExit_init, and the member: no argument leaves it unset (None); one is that argument, more the args
Ref system_exit_init(Obj self, Args a) {
    if (a.nkw != 0) raise_new("TypeError", type_of(self)->name + "() takes no keyword arguments");
    set_args(self, a);
    if (a.npos == 1) set_exception_field(self, "code", a.pos(0));
    else if (a.npos > 1) set_exception_field(self, "code", exception_field(self, "args"));
    return none_ref();
}
Ref system_exit_code_get(Obj self) { Obj v = exception_field(self, "code"); return v.is_unset() ? none_ref() : Ref::share(v); }
void system_exit_code_set(Obj self, Obj v) { set_exception_field(self, "code", v); }
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
    set_args(self, a);
    Obj name, path, name_from;
    for (std::size_t k = 0; k < a.nkw; ++k) {
        std::string_view n = a.kwnames[k]->text;
        Obj* slot = n == "name" ? &name : n == "path" ? &path : n == "name_from" ? &name_from : nullptr;
        if (slot == nullptr) unexpected_keyword("ImportError()", a.kwnames[k], {"name", "path", "name_from"});
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
    if (is_exact_dict(mapping)) dict_set(static_cast<Dict*>(mapping.object()), key, value);
    else setitem(mapping, key, value);
}

Ref load_classdict(Obj mapping, Module* m, const Str* name) {
    Ref v = mapping_get(mapping, Obj::of(name));
    if (!v.get().is_unset()) return is_kind(v.get(), Kind::LazyImport) ? lazy_reify(v.get(), name, mapping) : v;
    return load_global(m, name);
}
Ref load_classdict_free(Obj mapping, const Str* name, const Ref& cell, const char* text) {
    Ref v = mapping_get(mapping, Obj::of(name));
    if (!v.get().is_unset()) return is_kind(v.get(), Kind::LazyImport) ? lazy_reify(v.get(), name, mapping) : v;
    return load_deref(cell, text, true);      // LOAD_DEREF does not resolve a lazy import
}

// ---- the builtin types' attributes ----
// a built-in's types.SimpleNamespace in Python (bootstrap.py): CPython's type says `types.SimpleNamespace`
// in its messages (tp_name), and its __dict__ is a read-only member
namespace {
void readonly_dict(Obj, Obj) { raise_new("AttributeError", "readonly attribute"); }
Module*& bootstrap_of_types() {
    static Module* m = nullptr;
    return m;
}
Ref bootstrap_call(const char* name, Obj arg) {
    return invoke(dict_get(bootstrap_of_types()->dict, Obj::of(N(name))), {arg});
}
Ref ga_parameters(Obj self) { return bootstrap_call("_ga_parameters", self); }
Ref ga_unpacked_tuple_args(Obj self) { return bootstrap_call("_ga_unpacked_tuple_args", self); }
Ref class_getitem(Obj self, Args a) {            // Py_GenericAlias as a built-in type's __class_getitem__
    onearg(a, as_class(self)->qualname + ".__class_getitem__");
    return generic_alias(self, a.pos(0));
}
}  // namespace
Ref generic_alias(Obj origin, Obj args) {
    return invoke(dict_get(bootstrap_of_types()->dict, Obj::of(N("GenericAlias"))), {origin, args});
}
void present_as_c_types(Module* bootstrap) {
    bootstrap_of_types() = bootstrap;
    Obj ns = dict_get(bootstrap->dict, Obj::of(N("SimpleNamespace")));
    if (!is_kind(ns, Kind::Class)) return;
    auto* c = static_cast<ClassObject*>(ns.object());
    c->name = "types.SimpleNamespace";
    c->name_prefix = 6;
    c->attrs.set(N("__dict__"), Obj::of(new GetSet("__dict__", c, instance_dict, readonly_dict)));
    auto* ga = static_cast<ClassObject*>(dict_get(bootstrap->dict, Obj::of(N("GenericAlias"))).object());
    ga->name = "types.GenericAlias";
    ga->name_prefix = 6;
    ga->forwards_attributes = true;
    note_prelude_class(ga);
    ga->has_weakref = cpython_has("weakref", "GenericAlias");
    auto* ga_iterator = static_cast<ClassObject*>(dict_get(bootstrap->dict, Obj::of(N("generic_alias_iterator"))).object());
    note_prelude_class(ga_iterator);
    ga_iterator->final_type = true;
    getset(ga, "__parameters__", ga_parameters);
    getset(ga, "__typing_unpacked_tuple_args__", ga_unpacked_tuple_args);
    for (ClassObject* t : builtin_types())
        if (cpython_has(t->name, "__class_getitem__")) method(t, "__class_getitem__", class_getitem, Binding::ClassMethod);
}

// What a class statement leaves that a type written in C does not have; the layout is held elsewhere
Ref instance_dict_of(Obj self) { return instance_dict_getset()->get(self); }
Ref int_from_number(Obj x) { return number_long(x); }
void forget_python_origin(ClassObject* c) {
    for (const char* n : {"__slots__", "__firstlineno__", "__static_attributes__", "__weakref__"})   // a C type's list has no getset
        if (c->attrs.contains(N(n))) c->del_attr(N(n));
}
// A class the prelude writes for a type a built-in module has in C: its tp_name, its place in the
// names table, what the table says it cannot be (a base), its docstring and its __class_getitem__.
void present_native_class(ClassObject* c, const std::string& module) {
    std::string short_name = c->name;
    c->name = module + "." + short_name;
    c->name_prefix = module.size() + 1;
    note_prelude_class(c);
    c->final_type = cpython_has("final", c->name);
    forget_python_origin(c);
    c->has_weakref = cpython_has("weakref", short_name);
    if (Obj doc = cpython_doc(short_name); doc != None()) c->set_attr(N("__doc__"), doc);
    if (cpython_has(short_name, "__class_getitem__")) method(c, "__class_getitem__", class_getitem, Binding::ClassMethod);
}

// _PyErr_FormatNote / BaseException.add_note: appended to __notes__, made a list if absent
void add_note(Obj exc, const std::string& text) {
    Ref note = str_new(text);
    Ref notes = optional_getattr(exc, N("__notes__"));
    if (notes.get().is_unset() || !is_kind(notes.get(), Kind::List)) {
        notes = list_new({note.get()});
        setattr(exc, N("__notes__"), notes.get());
        return;
    }
    list_append(notes.get(), note.get());
}

// Python/suggestions.c: levenshtein_distance's costs, _Py_CalculateSuggestions' choice
namespace {
std::size_t edit_cost(std::string_view a, std::string_view b) {
    constexpr std::size_t MOVE = 2, CASE = 1;
    auto lower = [](char c) { return c >= 'A' && c <= 'Z' ? static_cast<char>(c + 32) : c; };
    std::vector<std::size_t> row(b.size() + 1);
    for (std::size_t j = 0; j <= b.size(); ++j) row[j] = j * MOVE;
    for (std::size_t i = 0; i < a.size(); ++i) {
        std::size_t diag = row[0];
        row[0] = (i + 1) * MOVE;
        for (std::size_t j = 0; j < b.size(); ++j) {
            std::size_t sub = a[i] == b[j] ? 0 : lower(a[i]) == lower(b[j]) ? CASE : MOVE;
            std::size_t best = std::min({diag + sub, row[j] + MOVE, row[j + 1] + MOVE});
            diag = row[j + 1];
            row[j + 1] = best;
        }
    }
    return row[b.size()];
}
}  // namespace
std::string keyword_suggestion(const std::string& name, const std::vector<std::string>& known) {
    std::string suggestion;
    std::size_t best = SIZE_MAX;
    for (const std::string& it : known) {
        if (it == name) continue;
        std::size_t limit = std::min((name.size() + it.size() + 3) * 2 / 6, best == SIZE_MAX ? SIZE_MAX : best - 1);
        std::size_t cost = edit_cost(name, it);
        if (cost > limit) continue;
        if (suggestion.empty() || cost < best) {
            suggestion = it;
            best = cost;
        }
    }
    return suggestion;
}
void unexpected_keyword(const std::string& who, const Str* name, std::initializer_list<const char*> known) {
    std::string suggestion = keyword_suggestion(name->text, std::vector<std::string>(known.begin(), known.end()));
    raise_new("TypeError", who + " got an unexpected keyword argument '" + name->text + "'" +
                               (!suggestion.empty() ? ". Did you mean '" + suggestion + "'?" : ""));
}

void init_types() {
    static bool done = false;
    if (done) return;
    done = true;
    Types& t = types();
    init_sets();
    init_bytes();
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
    method(t.frozendict, "__new__", frozendict_new_m, Binding::Function);
    method(t.int_, "__new__", int_new_m, Binding::Function);
    for (ClassObject* c : {t.list, t.tuple, t.str, t.bool_}) new_method(c, builtin_new_m);
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
    method(t.type, "__subclasses__", type_subclasses);
    method(t.object, "__subclasshook__", object_subclasshook, Binding::ClassMethod);
    method(t.object, "__dir__", object_dir);
    method(t.object, "__getattribute__", object_getattribute);
    method(t.type, "__dir__", type_dir);
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
    for (ClassObject* c : {t.function, t.method_descriptor, t.classmethod_descriptor, t.getset_descriptor, t.member_descriptor}) method(c, "__get__", get_native);
    for (ClassObject* c : {t.getset_descriptor, t.member_descriptor}) {
        method(c, "__set__", getset_set);
        method(c, "__delete__", getset_delete);
        auto member = [&](const char* name, Ref (*get)(Obj)) {   // descr_members: read-only members
            auto* g = new GetSet(name, c, get, nullptr);
            g->cls = t.member_descriptor;
            c->attrs.set(N(name), Obj::of(g));
        };
        member("__name__", descriptor_name);
        member("__objclass__", descriptor_objclass);
        c->attrs.set(N("__qualname__"), Obj::of(new GetSet("__qualname__", c, descriptor_qualname, nullptr)));   // descr_getset
    }
    // functions, methods, cells
    getset(t.function, "__name__", fn_name, set_fn_name);
    getset(t.function, "__qualname__", fn_qualname, set_fn_qualname);
    getset(t.function, "__doc__", fn_doc, set_fn_doc);
    getset(t.function, "__module__", fn_module, set_fn_module);
    static_cast<GetSet*>(t.function->attrs.find(N("__module__"))->object())->deletable = true;
    getset(t.function, "__defaults__", fn_defaults);
    getset(t.function, "__kwdefaults__", fn_kwdefaults);
    getset(t.function, "__type_params__", fn_type_params, set_fn_type_params);
    static_cast<GetSet*>(t.function->attrs.find(N("__type_params__"))->object())->deletable = true;
    getset(t.function, "__annotate__", fn_annotate, set_fn_annotate);
    static_cast<GetSet*>(t.function->attrs.find(N("__annotate__"))->object())->deletable = true;
    getset(t.function, "__dict__", fn_dict);
    getset(t.method, "__func__", method_func);
    method(t.method, "__new__", method_new, Binding::Function);
    getset(t.method, "__self__", method_self);
    getset(t.builtin, "__name__", builtin_name);
    getset(t.builtin, "__self__", builtin_self);
    getset(t.builtin, "__qualname__", builtin_qualname);
    {
        auto* g = new GetSet("__module__", t.builtin, builtin_module, set_builtin_module);
        g->deletable = true;
        t.builtin->attrs.set(N("__module__"), Obj::of(g));
    }
    getset(t.cell, "cell_contents", cell_contents_get, cell_contents_set);
    // mappingproxy, slice
    method(t.mappingproxy, "__getitem__", proxy_getitem);
    method(t.mappingproxy, "__contains__", proxy_contains);
    method(t.mappingproxy, "get", proxy_get);
    method(t.mappingproxy, "__len__", proxy_len);
    method(t.mappingproxy, "keys", proxy_keys);
    method(t.mappingproxy, "values", proxy_values);
    method(t.mappingproxy, "items", proxy_items);
    method(t.mappingproxy, "copy", proxy_copy);
    method(t.mappingproxy, "__iter__", proxy_iter);
    method(t.mappingproxy, "__repr__", proxy_repr);
    method(t.mappingproxy, "__str__", proxy_str);
    method(t.mappingproxy, "__hash__", proxy_hash);
    method(t.mappingproxy, "__eq__", proxy_eq);
    method(t.mappingproxy, "__ne__", proxy_ne);
    method(t.slice, "__new__", slice_new, Binding::Function);
    for (auto [name, get] : std::initializer_list<std::pair<const char*, Ref (*)(Obj)>>{{"start", slice_start}, {"stop", slice_stop}, {"step", slice_step}}) {
        auto* m = new GetSet(name, t.slice, get, nullptr);   // PyMemberDef in CPython, as range's are
        m->cls = t.member_descriptor;
        t.slice->attrs.set(N(name), Obj::of(m));
    }
    // exceptions
    ClassObject* base = exception_class("BaseException");
    for (ClassObject* c : exception_classes())   // each type CPython gives a __new__ of its own, its name in the errors
        if (c == base || cpython_has(c->name, "__new__")) new_method(c, exception_new);
    method(base, "__init__", exception_init);
    method(exception_class("AttributeError"), "__init__", attribute_error_init);
    method(exception_class("NameError"), "__init__", name_error_init);
    method(exception_class("SystemExit"), "__init__", system_exit_init);
    deletable_getset(exception_class("SystemExit"), "code", system_exit_code_get, system_exit_code_set);
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
