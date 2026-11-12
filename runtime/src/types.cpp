// runtime/src/types.cpp -- classes (bella/runtime.hpp): the builtin types' attributes as getset
// and method descriptors, type.__new__ and calling a class, attribute access on classes and on the
// C++ types' objects, and special-method dispatch. CPython's Objects/typeobject.c is the reference
// for each rule; the order of effects follows it.
#include <unordered_set>
#include "bella/runtime.hpp"

#include <algorithm>
#include <charconv>
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

const void* new_slot(ClassObject* c) {           // tp_new, as far as the runtime can tell it apart
    Obj f = type_lookup(c, N("__new__"));
    if (!is_kind(f, Kind::Builtin)) return nullptr;
    auto* b = static_cast<Builtin*>(f.object());
    return b->written.get().is_object() ? static_cast<const void*>(b->written.get().object()) : reinterpret_cast<const void*>(b->fn);
}
ClassObject* static_base(ClassObject* c) {
    while (!is_kind(type_lookup(c, N("__new__")), Kind::Builtin) && !c->bases.empty()) c = tp_base(c);
    return c;
}
// Which dict a class's instances have (object.hpp's DictKind; C-3-59), as CPython's own flags and offsets say of the nearest
// type written in C along tp_base (the names table's rows). That type has a dict slot of its own (tp_dictoffset): an ordinary
// dict, for it and for what derives from it, unless its flags say the dict is managed. It has none, and a class added one: a
// managed dict, whose values are in the object unless the object's size varies (heapflags: without Py_TPFLAGS_INLINE_VALUES,
// an int's or a tuple's subclass). A type the table has no row for keeps its values in the object, as every class did before.
DictKind dict_kind_of(ClassObject* c) {
    constexpr std::int64_t INLINE_VALUES = 1 << 2, MANAGED_DICT = 1 << 4;
    if (!c->has_dict) return DictKind::Inline;
    ClassObject* base = c;
    while (!c_type(base)) base = tp_base(base);
    if (base->dict_without_getset) return DictKind::Plain;   // _thread._local: the thread's dict of the object is an ordinary one (_ldict)
    auto managed = [](std::int64_t flags) { return (flags & INLINE_VALUES) ? DictKind::Inline : DictKind::Shared; };
    std::int64_t dictoffset = 0;
    if (auto text = cpython_type_text("offsets", base)) std::from_chars(text->data(), text->data() + text->find(','), dictoffset);
    if (dictoffset != 0) {
        auto flags = cpython_type_number("flags", base);
        if (!flags) return DictKind::Inline;
        return (*flags & MANAGED_DICT) ? managed(*flags) : DictKind::Plain;
    }
    if (base == c) return DictKind::Inline;      // a dict the runtime's own writing of the type has, and CPython's type does not
    auto flags = cpython_type_number("heapflags", base);
    return flags && (*flags & MANAGED_DICT) ? managed(*flags) : DictKind::Inline;
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
    if (b == Binding::Method && cpython_attribute_kind(c, name) == "wrapper_descriptor") f->cls = types().wrapper_descriptor;
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
        if (b->owner != nullptr && b->cls != types().wrapper_descriptor && b->cls != types().method_wrapper &&
            cpython_attribute_kind(b->owner, b->name) == "wrapper_descriptor")   // made some other way than method(): no such object yet
            throw NotImplemented("the type of " + b->owner->name + "." + b->name + ", a slot wrapper in CPython");
    }
    return type_of(v);
}

// wrapper_call and the slot's wrap_*: what a slot wrapper checks before the method runs, for a method written in Python
static void wrapper_checks(const std::string& name, Args a) {
    if (name == "__init__" || name == "__call__") return;   // PyWrapperFlag_KEYWORDS, and any number of arguments
    if (a.nkw != 0) raise_new("TypeError", "wrapper " + name + "() takes no keyword arguments");
    static const std::unordered_set<std::string_view> unary{"__iter__", "__next__", "__repr__", "__str__", "__hash__", "__len__", "__bool__", "__neg__", "__pos__",
                                                            "__abs__", "__invert__", "__int__", "__float__", "__index__", "__del__"};
    static const std::unordered_set<std::string_view> ternary{"__setitem__", "__setattr__", "__set__"};
    static const std::unordered_set<std::string_view> variable{"__get__", "__pow__", "__rpow__", "__ipow__"};
    if (variable.contains(name)) return;
    if (ternary.contains(name)) {                // wrap_sq_setitem and the others: PyArg_UnpackTuple
        if (a.npos != 2) raise_new("TypeError", name + " expected 2 arguments, got " + std::to_string(a.npos));
        return;
    }
    std::size_t expected = unary.contains(name) ? 0 : 1;
    if (a.npos != expected)
        raise_new("TypeError", "expected " + std::to_string(expected) + " argument" + (expected == 1 ? "" : "s") + ", got " + std::to_string(a.npos));
}
Ref call_builtin(Builtin* b, Obj self, Args a) {
    Obj written = b->written.get();
    if (written.is_unset()) return b->fn(self, a);
    if (b->cls == types().wrapper_descriptor || b->cls == types().method_wrapper) wrapper_checks(b->name, a);
    if (self.is_unset()) {                       // a __new__: tp_new_wrapper's checks, then the type as the first argument
        new_wrapper_class(a, b->owner);
        return invoke(written, a);
    }
    auto data = with_first(self, a);
    return invoke(written, Args{data.data(), a.npos + 1, a.kwnames, a.nkw});
}
void check_classmethod_type(const Builtin* b, Obj type) {
    if (!is_kind(type, Kind::Class))
        raise_new("TypeError", "descriptor '" + b->name + "' for type '" + b->owner->name + "' needs a type, not a '" + type_of(type)->name + "' as arg 2");
    if (!is_subclass(static_cast<ClassObject*>(type.object()), b->owner))
        raise_new("TypeError", "descriptor '" + b->name + "' requires a subtype of '" + b->owner->name + "' but received '" + static_cast<ClassObject*>(type.object())->name + "'");
}
// A method bound to its receiver: what binding makes of a descriptor, in the kind CPython makes
static Ref bind_builtin(Builtin* b, Obj receiver) {
    Ref bound = own(new Builtin(b->name, b->fn, receiver));
    auto* made = static_cast<Builtin*>(bound.get().object());
    made->owner = b->owner;                      // how it presents itself
    made->written = b->written;
    if (b->cls == types().wrapper_descriptor) made->cls = types().method_wrapper;
    if (b->bound_cmethod) made->cls = types().builtin_method;
    return bound;
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
                if (b->binding == Binding::ClassMethod) {
                    Obj bound_to = is_none(type) ? Obj::of(type_of(obj)) : type;
                    if (b->owner != nullptr) check_classmethod_type(b, bound_to);
                    return bind_builtin(b, bound_to);
                }
                if (is_none(obj)) return Ref::share(found);
                if (b->owner != nullptr && !isinstance(obj, b->owner))       // method_check (A9-2)
                    raise_new("TypeError", "descriptor '" + b->name + "' for '" + b->owner->name + "' objects doesn't apply to a '" +
                                               type_of(obj)->name + "' object");
                return bind_builtin(b, obj);
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
// member_get_doc / getset_get_doc: the def's doc, None for none. One the runtime's own definition does not carry is the names
// table's, recorded from CPython's type (`member:<tp_name>.<name>`, an empty row for None): a struct sequence's fields, a C
// type's members. A program's own __slots__ member has none (case C-3-56).
Ref descriptor_doc(Obj self) {
    const char* own = is_kind(self, Kind::SlotDescriptor) ? nullptr : static_cast<GetSet*>(self.object())->doc;
    if (own != nullptr) return *own == '\0' ? none_ref() : str_new(own);
    ClassObject* owner = descriptor_owner(self);
    std::string name = descriptor_text(self);
    if (!c_type(owner)) return none_ref();
    Obj recorded = cpython_doc("member:" + owner->name + "." + name);
    if (recorded == None()) throw NotImplemented(type_of(self)->name + ".__doc__ of '" + name + "' (CPython has it; the runtime does not yet)");
    return as_str(recorded)->text.empty() ? none_ref() : Ref::share(recorded);
}
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
            if (inst->field(d->name).is_unset()) raise_new("AttributeError", d->name->text);   // PyMember_SetOne: the name, and nothing held
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
        if (b->self.is_unset() && b->binding == Binding::Method) return bind_builtin(b, obj);
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
    if (cls->disallow_instantiation) raise_new("TypeError", "cannot create '" + cls->name + "' instances");
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
    if (cls->disallow_instantiation) raise_new("TypeError", "cannot create '" + cls->name + "' instances");
    if (cls == types().type && a.npos == 1 && a.nkw == 0) return Ref::share(Obj::of(observed_type(a.pos(0))));
    if (cls == types().type && a.npos != 3) raise_new("TypeError", "type() takes 1 or 3 arguments");
    if (cls == types().super_) return super_call(a);                  // super's own vectorcall
    Obj new_attr = type_lookup(cls, N("__new__"));
    if (new_attr.is_unset()) raise_new("TypeError", "cannot create '" + cls->name + "' instances");
    if (new_attr == object_new_fn() && (!cls->heap_type || cls->disallow_instantiation) && cls != types().object) refuse_construction(cls);
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
                         ? call_builtin(static_cast<Builtin*>(init.object()), obj.get(), a)
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
        d->doc = "list of weak references to the object";   // subtype_getsets_full's
        d->flags |= IMMORTAL;
        return d;
    }();
    return g;
}

Ref type_new(ClassObject* meta, Obj name_obj, Obj bases_obj, Obj ns_obj, Args kw) {
    const Str* name = as_str(name_obj);
    if (name == nullptr) raise_new("TypeError", "type.__new__() argument 1 must be str, not " + type_of(name_obj)->name);
    if (!is_exact_str(name_obj)) throw NotImplemented("a class named by a subclass of str (CPython has it; the runtime does not yet)");
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
        if (!bc->heap_type && bc != types().object && bc != types().type && bc != types().dict && bc != types().frozendict && bc != types().str && bc != types().int_ && bc != types().complex_ && bc != types().tuple && bc != types().list && bc != types().float_ && bc != types().set && bc != types().frozenset && bc != types().bytes && bc != types().bytearray &&
            bc != types().module &&              // a class statement over ModuleType (importlib.util._LazyModule): instances and __class__ assignment stop by name
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
        if (k != nullptr && !is_exact_str(e.key)) throw NotImplemented("a subclass of str as a name in a class's namespace (CPython has it; the runtime does not yet)");
        if (k == nullptr) throw NotImplemented("a class namespace with a key that is not a str");
        if (k->text == "__qualname__") {
            const Str* q = as_str(e.value);
            if (q == nullptr) raise_new("TypeError", "type __qualname__ must be a str, not " + type_of(e.value)->name);
            if (!is_exact_str(e.value)) throw NotImplemented("a subclass of str as a class's __qualname__ (CPython keeps the object; the runtime keeps text)");
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
            if (!is_identifier(s)) raise_new("TypeError", "__slots__ must be identifiers");   // valid_identifier
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
        // an int's or a bytes's subclass has instances of a variable size: only __dict__ and __weakref__ may be slots
        for (ClassObject* variable : {types().int_, types().bytes}) {
            bool based = std::any_of(bases.begin(), bases.end(), [&](ClassObject* b) { return is_subclass(b, variable); });
            if (based && std::any_of(slots.begin(), slots.end(), [](const std::string& n) { return n != "__dict__" && n != "__weakref__"; }))
                raise_new("TypeError", "arbitrary __slots__ not supported for subtype of '" + variable->name + "'");
        }
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
    if (!static_cast<Tuple*>(bases_obj.object())->items.empty()) {   // type_new keeps the tuple it is given as tp_bases
        incref(bases_obj);
        c->bases_tuple = bases_obj;
    }
    c->dict_kind = dict_kind_of(c);
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
    if (!base_has_weak && !asked_weak && std::any_of(bases.begin(), bases.end(), [](ClassObject* b) { return is_subclass(b, types().int_) || is_subclass(b, types().tuple) || is_subclass(b, types().bytes); }))   // tp_itemsize
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
    // inherit_patma_flags: the first base in the MRO with either
    for (std::size_t i = 1; i < c->mro.size() && c->collection_flags == 0; ++i) c->collection_flags = collection_flags_of(c->mro[i]);
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
    // type_new_get_bases: a base that is no type but has __mro_entries__ is the class statement's business (types.new_class)
    for (Obj b : static_cast<Tuple*>(a.pos(2).object())->items)
        if (!is_kind(b, Kind::Class) && !optional_getattr(b, N("__mro_entries__")).get().is_unset())
            raise_new("TypeError", "type() doesn't support MRO entry resolution; use types.new_class()");
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
    if (is_subclass(cls, types().list)) return own(new ListInstance(cls));   // PyType_GenericNew: empty, whatever the arguments
    return invoke(Obj::of(cls), Args{a.data + 1, a.npos - 1, a.kwnames, a.nkw});
}
Ref tuple_new_m(Obj, Args a) {                   // tuple_new_impl, and tuple_subtype_new for a subclass
    ClassObject* cls = new_wrapper_class(a, types().tuple);
    Args rest{a.data + 1, a.npos - 1, a.kwnames, a.nkw};
    Ref made = invoke(Obj::of(types().tuple), rest);
    if (cls == types().tuple) return made;
    auto* instance = new TupleInstance(cls);
    Ref r = own(instance);
    for (Obj v : static_cast<Tuple*>(made.get().object())->items) {
        incref(v);
        instance->items.push_back(v);
    }
    return r;
}
Ref str_new_m(Obj, Args a) {                     // unicode_new, unicode_subtype_new: the text of what str() gives, in a new one
    ClassObject* cls = new_wrapper_class(a, types().str);
    Args rest{a.data + 1, a.npos - 1, a.kwnames, a.nkw};
    if (rest.npos + rest.nkw > 3) raise_new("TypeError", std::string("str() takes at most 3 ") + (rest.npos == 0 ? "keyword " : "") + "arguments (" + std::to_string(rest.npos + rest.nkw) + " given)");   // not through unicode_vectorcall
    Ref made = invoke(Obj::of(types().str), rest);
    if (cls == types().str) return made;
    return own(new StrInstance(cls, as_str(made.get())->text));
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
    // PyLong_FromUnicodeObject: the text as _PyUnicode_TransformDecimalAndSpaceToASCII has it, the message the str itself
    std::string transformed;
    return int_from_text(decimal_and_space_to_ascii(s, transformed), base, [&]() -> Ref {
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
        if (a.kwnames[k]->text != "base") unexpected_keyword("int()", a.kwnames[k], {"base"});
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
        if (c_type(c)) table = cpython_names_of(c->name);
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
    // the prelude's property keeps in its dict what CPython keeps in C fields: the dict shows only where CPython's type has a __dict__
    // (ast.AST's getset, functools.partial's member), or where a subclass of the program's gets one of its own
    auto shows_dict = [](const ClassObject* c) {
        if (!c_type(c) || c->dict_without_getset) return true;
        for (const ClassObject* k : c->mro)
            if (c_type(k) && !cpython_attribute_kind(k, "__dict__").empty()) return true;
        return false;
    };
    Ref dict = shows_dict(type_of(self)) ? optional_getattr(self, N("__dict__")) : Ref{};
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
Ref object_str(Obj self, Args) { return repr_unchecked(self); }   // object_str: tp_repr itself; PyObject_Str checks what comes back
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
            raise_set_failed(self, intern(n->text), e.what());
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
    if (d.is_unset()) {                          // del obj.__dict__ (subtype_setdict): the object has none, and what is asked next decides (C-3-58)
        with_attribute_storage(self, [](auto* inst) { del_dict(inst); });   // by the class's kind of dict (C-3-59)
        return;
    }
    if (!is_dict(d)) raise_new("TypeError", "__dict__ must be set to a dictionary, not a '" + type_of(d)->name + "'");
    with_attribute_storage(self, [&](auto* inst) { set_dict(inst, static_cast<DictObject*>(d.object())); });
}

// the getset a class that adds an instance dict gets as its __dict__ (type_new)
GetSet* instance_dict_getset() {
    static GetSet* g = [] {
        auto* gs = new GetSet("__dict__", types().object, instance_dict, set_instance_dict);
        gs->deletable = true;
        gs->doc = "dictionary for instance variables";       // subtype_getsets_full's
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
    if (!is_exact_str(v)) throw NotImplemented("a subclass of str as a class's __qualname__ (CPython keeps the object; the runtime keeps text)");
    c->qualname = s->text;
}
Ref type_module(Obj self) {
    ClassObject* c = self_class(self);
    if (c_type(c)) {                     // a C type's module: its tp_name's prefix, else builtins
        const Obj* m = c->attrs.find(N("__module__"));
        if (m != nullptr && as_str(*m) != nullptr) return Ref::share(*m);
        return str_new(c->name_prefix > 0 ? c->name.substr(0, c->name_prefix - 1) : "builtins");
    }
    if (const Obj* m = c->attrs.find(N("__module__"))) return Ref::share(*m);
    raise_attribute_error(self, N("__module__"), "__module__");
}
void set_type_module(Obj self, Obj v) {          // type_set_module: the class's own __module__
    ClassObject* c = self_class(self);
    check_special(c, v, "__module__");
    c->set_attr(N("__module__"), v);
}
// type_get_annotate, type_set_annotate, type_get_annotations, type_set_annotations: a class's annotations live in its dict as
// __annotate_func__ (what the class body stored) and __annotations_cache__ (what reading them, or a store, left); a static type has neither
Ref type_annotate(Obj self) {
    ClassObject* c = self_class(self);
    if (!c->heap_type) raise_new("AttributeError", "type object '" + c->name + "' has no attribute '__annotate__'");
    const Obj* a = c->attrs.find(N("__annotate__"));
    if (a == nullptr) a = c->attrs.find(N("__annotate_func__"));
    if (a != nullptr) return descr_get(*a, None(), self);
    c->set_attr(N("__annotate_func__"), None());
    return none_ref();
}
void set_type_annotate(Obj self, Obj v) {
    ClassObject* c = self_class(self);
    if (v.is_unset()) raise_new("TypeError", "cannot delete __annotate__ attribute");
    if (immutable_type(c)) raise_new("TypeError", "cannot set '__annotate__' attribute of immutable type '" + c->name + "'");
    if (v != None() && !callable_check(v)) raise_new("TypeError", "__annotate__ must be callable or None");
    c->set_attr(N("__annotate_func__"), v);
    if (v != None() && c->attrs.contains(N("__annotations_cache__"))) c->del_attr(N("__annotations_cache__"));
}
Ref type_annotations(Obj self) {
    ClassObject* c = self_class(self);
    if (!c->heap_type) raise_new("AttributeError", "type object '" + c->name + "' has no attribute '__annotations__'");
    const Obj* a = c->attrs.find(N("__annotations__"));      // from __future__ import annotations stores the dict itself
    if (a == nullptr) a = c->attrs.find(N("__annotations_cache__"));
    if (a != nullptr) return descr_get(*a, None(), self);
    Ref annotate = getattr(self, N("__annotate__"));
    Ref annotations;
    if (callable_check(annotate.get())) {
        annotations = invoke(annotate.get(), {int_from_i64(1).get()});
        if (!is_kind(annotations.get(), Kind::Dict))
            raise_new("TypeError", "__annotate__() must return a dict, not " + type_of(annotations.get())->name);
    } else {
        annotations = dict_new();
    }
    c->set_attr(N("__annotations_cache__"), annotations.get());
    return annotations;
}
void set_type_annotations(Obj self, Obj v) {
    ClassObject* c = self_class(self);
    if (immutable_type(c)) raise_new("TypeError", "cannot set '__annotations__' attribute of immutable type '" + c->name + "'");
    if (c->attrs.contains(N("__annotations__"))) {           // the dict itself is in the class: it is what changes
        if (v.is_unset()) c->del_attr(N("__annotations__"));
        else c->set_attr(N("__annotations__"), v);
        if (c->attrs.contains(N("__annotations_cache__"))) c->del_attr(N("__annotations_cache__"));
    } else if (!v.is_unset()) {
        c->set_attr(N("__annotations_cache__"), v);
    } else if (c->attrs.contains(N("__annotations_cache__"))) {
        c->del_attr(N("__annotations_cache__"));
    } else {
        raise_new("AttributeError", "__annotations__");
    }
    for (const char* n : {"__annotate_func__", "__annotate__"})
        if (c->attrs.contains(N(n))) c->del_attr(N(n));
}
Ref type_doc(Obj self) {
    ClassObject* c = self_class(self);
    if (c_type(c))                               // type_get_doc: a static type's tp_doc (the names table's type: scope), whatever its dict holds (property's member)
        if (Obj d = cpython_doc("type:" + c->name); d != None() && !as_str(d)->text.empty()) return Ref::share(d);
    if (const Obj* d = c->attrs.find(N("__doc__"))) return descr_get(*d, None(), self);
    return none_ref();
}
// type_set_doc: a class's own __doc__, after check_set_special_type_attr
void set_type_doc(Obj self, Obj value) {
    ClassObject* c = self_class(self);
    check_special(c, value, "__doc__");
    c->set_attr(N("__doc__"), value);
}
// type_set_bases: check_set_special_type_attr, then type_check_new_bases's checks of the tuple and of each item in order. The
// bases the class has (typing's NamedTuple assigns them to every class it makes) give every MRO of its hierarchy again as it was,
// and leave the rest of type_set_bases_unlocked to see: the class leaves each base's subclasses and joins them again, last, and
// it and its subclasses are modified (RefClass.reassign_bases). Other bases change what every lookup walks, and a metaclass's
// own mro() would run: both stop by name.
void set_type_bases(Obj self, Obj v) {
    ClassObject* c = self_class(self);
    check_special(c, v, "__bases__");
    if (!is_kind(v, Kind::Tuple))
        raise_new("TypeError", "can only assign tuple to " + c->name + ".__bases__, not " + type_of(v)->name);
    const auto& items = static_cast<Tuple*>(v.object())->items;
    if (items.empty()) raise_new("TypeError", "can only assign non-empty tuple to " + c->name + ".__bases__, not ()");
    std::vector<ClassObject*> given;
    for (Obj item : items) {
        ClassObject* b = as_class(item);
        if (b == nullptr) raise_new("TypeError", c->name + ".__bases__ must be tuple of classes, not '" + type_of(item)->name + "'");
        if (is_subclass(b, c)) raise_new("TypeError", "a __bases__ item causes an inheritance cycle");
        given.push_back(b);
    }
    std::vector<ClassObject*> had = c->bases.empty() ? std::vector<ClassObject*>{types().object} : c->bases;
    if (given != had) throw NotImplemented("assigning a class's __bases__ other bases than it has (a new MRO for every lookup)");
    std::vector<ClassObject*> hierarchy{c};
    for (std::size_t i = 0; i < hierarchy.size(); ++i) {
        ClassObject* meta = type_of(Obj::of(hierarchy[i]));
        if (meta != types().type) {
            auto found = meta->lookup(N("mro"));
            if (found && found->second != types().type)
                throw NotImplemented("assigning __bases__ in a hierarchy whose metaclass '" + meta->name + "' defines mro() (mro_internal calls it)");
        }
        hierarchy.insert(hierarchy.end(), hierarchy[i]->subclasses.begin(), hierarchy[i]->subclasses.end());
    }
    incref(v);                                   // tp_bases is the tuple assigned, the very object
    if (!c->bases_tuple.is_unset()) decref(c->bases_tuple);
    c->bases_tuple = v;
    for (ClassObject* h : hierarchy)              // mro_hierarchy: each MRO made again, a new tuple equal to the old one
        if (!h->mro_tuple.is_unset()) decref(std::exchange(h->mro_tuple, Obj{}));
    for (ClassObject* b : c->bases) std::erase(b->subclasses, c);
    for (ClassObject* b : c->bases) b->subclasses.push_back(c);
    c->bump();
}
Ref type_dict(Obj self) { return own(new Proxy(self_class(self))); }
Ref type_mro_attr(Obj self) {                    // tp_mro: one tuple until the hierarchy's bases are assigned
    ClassObject* c = self_class(self);
    if (c->mro_tuple.is_unset()) {
        std::vector<Obj> items;
        for (ClassObject* m : c->mro) items.push_back(Obj::of(m));
        c->mro_tuple = tuple_copy(items).release();
    }
    return Ref::share(c->mro_tuple);
}
Ref type_bases(Obj self) {                       // tp_bases: the tuple the class was made with or assigned, else one made once
    ClassObject* c = self_class(self);
    if (c->bases_tuple.is_unset()) {
        std::vector<Obj> items;
        for (ClassObject* b : c->bases) items.push_back(Obj::of(b));
        if (items.empty() && c != types().object) items.push_back(Obj::of(types().object));
        c->bases_tuple = tuple_copy(items).release();
    }
    return Ref::share(c->bases_tuple);
}
Ref type_base(Obj self) {
    ClassObject* c = self_class(self);
    if (c == types().object) return none_ref();
    return Ref::share(Obj::of(c->bases.empty() ? types().object : c->bases[0]));
}
// type.__flags__. A type written in C has the pin's, from the names table. A program's class has what a class that says nothing has
// on its first base written in C (the table's heapflags:), less the dict and the weak reference its __slots__ leave out, with its
// collection and abstract bits; a __call__ of its own takes the vectorcall away (update_one_slot).
Ref type_flags(Obj self) {
    ClassObject* c = self_class(self);
    if (c_type(c)) {
        auto flags = cpython_type_number("flags", c);
        if (!flags) throw NotImplemented("the __flags__ of '" + c->name + "' (CPython has it; the runtime does not yet)");
        return int_from_i64(*flags);
    }
    ClassObject* base = c;
    while (!c_type(base)) base = tp_base(base);
    auto inherited = cpython_type_number("heapflags", base);
    if (!inherited) throw NotImplemented("the __flags__ of a subclass of '" + base->name + "' (CPython has it; the runtime does not yet)");
    constexpr std::int64_t INLINE_VALUES = 1 << 2, MANAGED_WEAKREF = 1 << 3, MANAGED_DICT = 1 << 4, COLLECTION = (1 << 5) | (1 << 6), VECTORCALL = 1 << 11, ABSTRACT = 1 << 20;
    std::int64_t flags = *inherited;
    if (!c->has_dict) flags &= ~(MANAGED_DICT | INLINE_VALUES);
    if (!c->has_weakref) flags &= ~MANAGED_WEAKREF;
    flags = (flags & ~COLLECTION) | c->collection_flags;
    if (c->abstract) flags |= ABSTRACT;
    if (type_lookup(c, N("__call__")) != type_lookup(base, N("__call__"))) flags &= ~VECTORCALL;
    return int_from_i64(flags);
}
// type.__dictoffset__ and __weakrefoffset__ (tp_dictoffset, tp_weaklistoffset): a C type's from the table; a class adds a managed dict (-1)
// where its base has none, and a managed weak reference (-32) where its base has none and is not variable-sized (type_new_alloc's rule)
std::pair<std::int64_t, std::int64_t> type_offsets(ClassObject* c) {
    if (c_type(c)) {
        auto text = cpython_type_text("offsets", c);
        if (!text) throw NotImplemented("the __dictoffset__ and __weakrefoffset__ of '" + c->name + "' (CPython has it; the runtime does not yet)");
        std::int64_t d = 0, w = 0;
        auto comma = text->find(',');
        std::from_chars(text->data(), text->data() + comma, d);
        std::from_chars(text->data() + comma + 1, text->data() + text->size(), w);
        return {d, w};
    }
    auto [d, w] = type_offsets(tp_base(c));
    if (d == 0 && c->has_dict) d = -1;
    if (w == 0 && c->has_weakref && !cpython_has("itemsize", static_base(c)->name)) w = -32;
    return {d, w};
}
Ref type_dictoffset(Obj self) { return int_from_i64(type_offsets(self_class(self)).first); }
Ref type_weakrefoffset(Obj self) { return int_from_i64(type_offsets(self_class(self)).second); }
}  // namespace
void drop_instance_dict(Obj self) { with_attribute_storage(self, [](auto* inst) { drop_dict(inst); }); }
std::uint8_t collection_flags_of(const ClassObject* c) {
    if (!c_type(c)) return c->collection_flags;
    auto flags = cpython_type_number("flags", c);
    return flags ? static_cast<std::uint8_t>(*flags & ((1 << 5) | (1 << 6))) : 0;
}
void set_collection_flag_recursive(ClassObject* child, std::uint8_t flag) {
    if (c_type(child) || child->collection_flags == flag) return;
    child->collection_flags = flag;
    for (ClassObject* grandchild : child->subclasses) set_collection_flag_recursive(grandchild, flag);
}
namespace {

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
void set_fn_doc(Obj self, Obj v) { fn_of(self)->doc = Ref::share(v.is_unset() ? None() : v); }   // a member: deleted, it reads None
Ref fn_module(Obj self) {                        // set from the globals' __name__ when made (func_new_impl); func.__module__ may be rebound
    if (!fn_of(self)->module_name.get().is_unset()) return fn_of(self)->module_name;
    return none_ref();                           // a function made in a namespace without __name__
}
void set_fn_module(Obj self, Obj v) {
    fn_of(self)->module_name = v.is_unset() ? none_ref() : Ref::share(v);
    fn_of(self)->code->module_rebound = true;
}
Ref fn_defaults(Obj self) { return fn_of(self)->defaults.get().is_unset() ? none_ref() : fn_of(self)->defaults; }
Ref fn_kwdefaults(Obj self) { return fn_of(self)->kwdefaults.get().is_unset() ? none_ref() : fn_of(self)->kwdefaults; }
Ref fn_globals(Obj self) { return Ref::share(Obj::of(fn_of(self)->module->dict)); }
Ref fn_builtins(Obj self) {
    Module* m = fn_of(self)->module;
    return Ref::share(Obj::of(m->builtins != nullptr ? m->builtins : builtins_module()->dict));
}
void set_fn_defaults(Obj self, Obj v) {          // func_set_defaults: None and del mean none at all
    if (!v.is_unset() && v != None() && !is_kind(v, Kind::Tuple)) raise_new("TypeError", "__defaults__ must be set to a tuple object");
    fn_of(self)->defaults = v.is_unset() || v == None() ? Ref{} : Ref::share(v);
}
void set_fn_kwdefaults(Obj self, Obj v) {        // func_set_kwdefaults
    if (!v.is_unset() && v != None() && !is_kind(v, Kind::Dict)) raise_new("TypeError", "__kwdefaults__ must be set to a dict object");
    fn_of(self)->kwdefaults = v.is_unset() || v == None() ? Ref{} : Ref::share(v);
}
Ref fn_annotate(Obj self) { return fn_of(self)->annotate.get().is_unset() ? none_ref() : fn_of(self)->annotate; }
void set_fn_annotate(Obj self, Obj v) {          // function___annotate___set_impl: a callable forgets the dict made so far
    if (v.is_unset()) raise_new("TypeError", "__annotate__ cannot be deleted");
    if (v != None() && !callable_check(v)) raise_new("TypeError", "__annotate__ must be callable or None");
    fn_of(self)->annotate = Ref::share(v);
    if (v != None()) fn_of(self)->annotations = Ref{};
}
Ref fn_annotations(Obj self) {                   // function___annotations___get_impl and func_get_annotation_dict
    PyFunction* f = fn_of(self);
    if (f->annotations.get().is_unset()) {
        Obj annotate = f->annotate.get();
        if (annotate.is_unset() || annotate == None() || !callable_check(annotate)) f->annotations = dict_new();
        else {
            Ref made = invoke(annotate, {Obj::small(1)});
            if (!is_kind(made.get(), Kind::Dict)) raise_new("TypeError", "__annotate__() must return a dict, not " + type_of(made.get())->name);
            f->annotations = made;
        }
    }
    return f->annotations;
}
void set_fn_annotations(Obj self, Obj v) {       // function___annotations___set_impl: None or a deletion clears, a dict is kept; __annotate__ goes
    if (!v.is_unset() && v != None() && !is_kind(v, Kind::Dict)) raise_new("TypeError", "__annotations__ must be set to a dict object");
    fn_of(self)->annotations = v.is_unset() || v == None() ? Ref{} : Ref::share(v);
    fn_of(self)->annotate = Ref{};
}
}  // namespace
namespace {
// function.__code__ and __closure__, and the code object's names and counts (specification E-02 as narrowed in v0.14): one code
// object per Code record, made at the first read, so that two reads compare equal as CPython's do; the bytecode side has no row here
// and stops by name through the names table
Ref fn_code(Obj self) {
    const Code* c = fn_of(self)->code;
    if (c->object.get().is_unset()) c->object = own(new CodeObject(c));
    return c->object;
}
void set_fn_code(Obj, Obj v) {                   // func_set_code: a delete is refused; a store needs the bytecode side (E-02, E-07)
    if (v.is_unset() || !is_kind(v, Kind::CodeKind)) raise_new("TypeError", "__code__ must be set to a code object");
    throw NotImplemented("function.__code__ assignment (E-07: a function from a code object)");
}
Ref fn_closure(Obj self) {                       // the function's closure tuple, one object (A14 #7)
    PyFunction* f = fn_of(self);
    if (f->closure.empty()) return none_ref();
    if (f->closure_tuple.get().is_unset()) {
        Ref items = list_new({});
        for (const Ref& r : f->closure) list_append(items.get(), r.get());
        f->closure_tuple = list_to_tuple(items.get());
    }
    return f->closure_tuple;
}
const Code* code_of(Obj self) { return static_cast<CodeObject*>(self.object())->code; }
Ref names_tuple(const std::vector<const char*>& names) {
    Ref items = list_new({});
    for (const char* n : names) list_append(items.get(), Obj::of(intern(n)));
    return list_to_tuple(items.get());
}
Ref co_name(Obj self) { return str_new(code_of(self)->name); }
Ref co_qualname(Obj self) { return str_new(code_of(self)->qualname); }
Ref co_filename(Obj self) { return str_new(code_of(self)->filename); }
Ref co_firstlineno(Obj self) { return int_from_i64(code_of(self)->first_line); }
Ref co_argcount(Obj self) { return int_from_i64(code_of(self)->argcount); }
Ref co_posonlyargcount(Obj self) { return int_from_i64(code_of(self)->posonlyargcount); }
Ref co_kwonlyargcount(Obj self) { return int_from_i64(code_of(self)->kwonlyargcount); }
Ref co_nlocals(Obj self) { return int_from_i64(static_cast<std::int64_t>(code_of(self)->varnames.size())); }
Ref co_varnames(Obj self) { return names_tuple(code_of(self)->varnames); }
Ref co_cellvars(Obj self) { return names_tuple(code_of(self)->cellvars); }
Ref co_freevars(Obj self) { return names_tuple(code_of(self)->freevars); }
Ref co_flags(Obj self) { return int_from_i64(code_of(self)->flags); }
Ref fn_type_params(Obj self) { return fn_of(self)->type_params.get().is_unset() ? tuple_new({}) : fn_of(self)->type_params; }
void set_fn_type_params(Obj self, Obj v) {       // function___type_params___set_impl
    if (v.is_unset() || !is_kind(v, Kind::Tuple)) raise_new("TypeError", "__type_params__ must be set to a tuple");
    fn_of(self)->type_params = Ref::share(v);
}
Ref fn_dict(Obj self) {
    if (fn_of(self)->dict.get().is_unset()) fn_of(self)->dict = dict_new();
    return fn_of(self)->dict;
}
void set_fn_dict(Obj self, Obj d) {              // PyObject_GenericSetDict: any dict, and no deleting
    if (d.is_unset()) raise_new("TypeError", "cannot delete __dict__");
    if (!is_dict(d)) raise_new("TypeError", "__dict__ must be set to a dictionary, not a '" + type_of(d)->name + "'");
    fn_of(self)->dict = Ref::share(d);
}
Ref method_func(Obj self) { return Ref::share(static_cast<Method*>(self.object())->func); }
Ref cell_new_m(Obj, Args a) {                    // cell_new: types.CellType(), empty, or types.CellType(contents)
    new_wrapper_class(a, types().cell);
    Args r = rest(a);
    if (r.nkw != 0) raise_new("TypeError", "cell() takes no keyword arguments");
    if (r.npos > 1) raise_new("TypeError", "cell expected at most 1 argument, got " + std::to_string(r.npos));
    return make_cell(r.npos == 1 ? r.pos(0) : Obj{});
}
Ref method_new(Obj, Args a) {                    // method(func, obj): any callable bound to obj
    new_wrapper_class(a, types().method);
    Args r = rest(a);
    arity(r, "method", 2, 2);
    if (!callable_check(r.pos(0))) raise_new("TypeError", "first argument must be callable");
    if (is_none(r.pos(1))) raise_new("TypeError", "instance must not be None");
    return own(new Method(r.pos(0), r.pos(1)));
}
Ref method_self(Obj self) { return Ref::share(static_cast<Method*>(self.object())->self); }
Ref method_doc(Obj self) { return getattr(static_cast<Method*>(self.object())->func, N("__doc__")); }   // method_get_doc: the function's, not the type's
Ref builtin_name(Obj self) {
    if (is_kind(self, Kind::PyFunction)) return static_cast<PyFunction*>(self.object())->name;     // the prelude's
    return str_new(static_cast<Builtin*>(self.object())->name);
}
Ref builtin_self(Obj self) {
    if (is_kind(self, Kind::PyFunction)) {       // the prelude's: print.__self__, posix.stat.__self__
        Ref module = fn_module(self);
        if (module.get() == None()) return none_ref();   // the error handlers of _codecs: made with no module and no self
        if (const Str* s = as_str(module.get()))
            if (Module* home = native_module_named(s->text)) return Ref::share(Obj::of(home));
        return Ref::share(Obj::of(builtins_module()));
    }
    auto* b = static_cast<Builtin*>(self.object());
    if (b->home != nullptr) return Ref::share(Obj::of(b->home));
    if (b->self.is_unset() && b->binding == Binding::Function && b->owner != nullptr &&
        cpython_attribute_kind(b->owner, b->name) == "builtin_function_or_method")
        return Ref::share(Obj::of(b->owner));                       // object.__new__.__self__ is object
    return b->self.is_unset() ? none_ref() : Ref::share(b->self);
}
Ref builtin_objclass(Obj self) {                 // wrapper_objclass, descr_get's member
    auto* b = static_cast<Builtin*>(self.object());
    if (b->owner == nullptr) throw NotImplemented("__objclass__ of a method that does not know its type");
    return Ref::share(Obj::of(b->owner));
}
Ref builtin_descr_qualname(Obj self) {           // descr_get_qualname, wrapper_qualname: the type's, a dot, its own
    auto* b = static_cast<Builtin*>(self.object());
    Ref owner = builtin_objclass(self);
    Ref qualname = getattr(owner.get(), N("__qualname__"));
    return str_new(as_str(qualname.get())->text + "." + b->name);
}
Ref builtin_module(Obj self);
Ref builtin_doc(Obj self) {                      // from the table, for the ones written in Python as for those in C++; a method's waits
    if (is_kind(self, Kind::Builtin)) {
        auto* b = static_cast<Builtin*>(self.object());
        if (b->cls == types().builtin_method) return none_ref();   // a bound METH_METHOD (builtin_method): CPython 3.15.2 answers None
        // a method the prelude writes with a docstring: the C's ml_doc as CPython shows it (one without: the C may have one, so it stops below)
        if (Obj written = b->written.get(); is_kind(written, Kind::PyFunction) && fn_doc(written).get() != None()) return fn_doc(written);
    }
    Ref module = builtin_module(self), name = builtin_name(self);
    const Str* m = as_str(module.get());
    if (as_str(name.get())->text == "__new__") {     // tp_new's builtin, bound to its type: the table's new:<tp_name> row
        Ref bound = builtin_self(self);
        if (is_kind(bound.get(), Kind::Class))
            if (auto text = cpython_doc_text("new:" + static_cast<ClassObject*>(bound.get().object())->name)) {
                if (text->empty()) return none_ref();
                return Ref::share(Obj::of(intern(std::string(*text))));
            }
    }
    if (m != nullptr || module.get() == None())      // the table's rows are <__module__>.<__name__>, "" for None (the error handlers of _codecs)
        if (auto text = cpython_doc_text((m == nullptr ? "" : m->text) + "." + as_str(name.get())->text)) {
            if (text->empty()) return none_ref();
            return Ref::share(Obj::of(intern(std::string(*text))));
        }
    throw NotImplemented("builtin_function_or_method.__doc__ of '" + as_str(name.get())->text + "' (CPython has it; the runtime does not yet)");
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
void cell_contents_set(Obj self, Obj v) {       // cell_set_contents: a delete empties the cell
    auto* c = static_cast<Cell*>(self.object());
    if (!v.is_unset()) incref(v);
    Obj old = std::exchange(c->value, v);
    if (!old.is_unset()) decref(old);
}

// mappingproxy over a class's own attributes
ClassObject* proxied(Obj self) { return static_cast<Proxy*>(self.object())->of; }
Obj proxy_mapping(Obj self) { return static_cast<Proxy*>(self.object())->mapping.get(); }
Ref proxy_new(Obj, Args a) {                     // mappingproxy_new_impl
    ClassObject* cls = new_wrapper_class(a, types().mappingproxy);
    (void)cls;
    std::size_t npos = a.npos - 1;
    if (npos + a.nkw > 1) raise_new("TypeError", "mappingproxy() takes at most 1 argument (" + std::to_string(npos + a.nkw) + " given)");
    Obj mapping = npos == 1 ? a.pos(1) : Obj{};
    if (a.nkw == 1 && a.kwnames[0]->text == "mapping") mapping = a.kw(0);
    if (mapping.is_unset()) raise_new("TypeError", "mappingproxy() missing required argument 'mapping' (pos 1)");
    if (!is_mapping(mapping) || is_kind(mapping, Kind::List) || is_kind(mapping, Kind::Tuple))
        raise_new("TypeError", "mappingproxy() argument must be a mapping, not " + type_of(mapping)->name);
    return own(new Proxy(mapping));
}
// mappingproxy reads a dict: a key is hashed, whether it could be an attribute's name or not
Ref proxy_getitem(Obj self, Args a) {
    arity(a, "__getitem__", 1, 1);
    if (proxied(self) == nullptr) return getitem(proxy_mapping(self), a.pos(0));
    dict_key_hash(a.pos(0));
    const Str* k = as_str(a.pos(0));
    if (k != nullptr)
        if (const Obj* v = proxied(self)->attrs.find(intern(k->text))) return Ref::share(*v);
    Ref exc = invoke(Obj::of(exception_class("KeyError")), {a.pos(0)});
    raise(exc.get());
}
Ref proxy_contains(Obj self, Args a) {
    arity(a, "__contains__", 1, 1);
    if (proxied(self) == nullptr) return compare(CmpOp::In, a.pos(0), proxy_mapping(self));
    dict_key_hash(a.pos(0));
    const Str* k = as_str(a.pos(0));
    return Ref::steal(boolean(k != nullptr && proxied(self)->attrs.contains(intern(k->text))));
}
Ref proxy_get(Obj self, Args a) {
    arity(a, "get", 1, 2);
    if (proxied(self) == nullptr) {              // mappingproxy_get: the mapping's own
        Ref f = getattr(proxy_mapping(self), N("get"));
        return a.npos > 1 ? invoke(f.get(), {a.pos(0), a.pos(1)}) : invoke(f.get(), {a.pos(0), None()});
    }
    dict_key_hash(a.pos(0));
    const Str* k = as_str(a.pos(0));
    if (k != nullptr)
        if (const Obj* v = proxied(self)->attrs.find(intern(k->text))) return Ref::share(*v);
    return a.npos > 1 ? Ref::share(a.pos(1)) : none_ref();
}
Ref proxy_len(Obj self, Args) {
    if (proxied(self) == nullptr) return call_special(proxy_mapping(self), "__len__", {});
    return Ref::steal(Obj::small(static_cast<std::int64_t>(proxied(self)->attrs.size())));
}
// What a program reaches through the proxy's dict: the class's dict, live (ClassObject::dict_view)
Obj class_dict(Obj self) {
    ClassObject* c = proxied(self);
    if (c == nullptr) return proxy_mapping(self);
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
// ---- OSError (Objects/exceptions.c) ----
ClassObject* os_error() { return exception_class("OSError"); }
// oserror_use_init: a subclass with an __init__ of its own and OSError's __new__ gets its arguments there
bool oserror_use_init(const ClassObject* type) {
    auto* c = const_cast<ClassObject*>(type);
    return type_lookup(c, N("__init__")) != type_lookup(os_error(), N("__init__")) && type_lookup(c, N("__new__")) == type_lookup(os_error(), N("__new__"));
}
struct OsArgs {
    Obj myerrno, strerror, filename, filename2;
};
OsArgs oserror_parse_args(std::span<const Obj> args) {   // ignored on this platform, the fourth: winerror
    OsArgs out;
    if (args.size() >= 2 && args.size() <= 5) {
        out.myerrno = args[0];
        out.strerror = args[1];
        if (args.size() > 2) out.filename = args[2];
        if (args.size() > 4) out.filename2 = args[4];
    }
    return out;
}
bool number_check(Obj v) {                       // PyNumber_Check
    ClassObject* c = type_of(v);
    return is_complex(v) || !type_lookup(c, N("__index__")).is_unset() || !type_lookup(c, N("__int__")).is_unset() || !type_lookup(c, N("__float__")).is_unset();
}
void oserror_init(Obj self, std::span<const Obj> args, const OsArgs& given) {
    Ref kept = tuple_copy(args);
    if (!given.filename.is_unset() && given.filename != None()) {
        if (type_of(self) == exception_class("BlockingIOError") && number_check(given.filename)) {   // its third argument: the characters written
            std::int64_t written = index_value(given.filename, "ValueError");
            Ref value = int_from_i64(written);
            set_exception_field(self, "written", value.get());
        } else {
            set_exception_field(self, "filename", given.filename);
            if (!given.filename2.is_unset() && given.filename2 != None()) set_exception_field(self, "filename2", given.filename2);
            if (args.size() >= 2 && args.size() <= 5) kept = tuple_copy(args.subspan(0, 2));   // only the first two, for compatibility
        }
    }
    if (!given.myerrno.is_unset()) set_exception_field(self, "errno", given.myerrno);
    if (!given.strerror.is_unset()) set_exception_field(self, "strerror", given.strerror);
    set_exception_field(self, "args", kept.get());
}
ClassObject* errno_class(std::int64_t code) {    // errnomap
    switch (code) {
        case EAGAIN: case EALREADY: case EINPROGRESS: return exception_class("BlockingIOError");
        case EPIPE: case ESHUTDOWN: return exception_class("BrokenPipeError");
        case ECHILD: return exception_class("ChildProcessError");
        case ECONNABORTED: return exception_class("ConnectionAbortedError");
        case ECONNREFUSED: return exception_class("ConnectionRefusedError");
        case ECONNRESET: return exception_class("ConnectionResetError");
        case EEXIST: return exception_class("FileExistsError");
        case ENOENT: return exception_class("FileNotFoundError");
        case EISDIR: return exception_class("IsADirectoryError");
        case ENOTDIR: return exception_class("NotADirectoryError");
        case EINTR: return exception_class("InterruptedError");
        case EACCES: case EPERM: return exception_class("PermissionError");
        case ESRCH: return exception_class("ProcessLookupError");
        case ETIMEDOUT: return exception_class("TimeoutError");
        default: return nullptr;
    }
}
Ref oserror_new(Obj, Args a) {                   // OSError_new
    ClassObject* type = new_wrapper_class(a, os_error());
    std::span<const Obj> args(a.data + 1, a.npos - 1);
    OsArgs given;
    bool use_init = oserror_use_init(type);
    if (!use_init) {
        if (a.nkw != 0) raise_new("TypeError", type->name + "() takes no keyword arguments");
        given = oserror_parse_args(args);
        std::int64_t code = 0;
        if (!given.myerrno.is_unset() && is_int(given.myerrno) && type == os_error() && int_fits_i64(given.myerrno, code))
            if (ClassObject* found = errno_class(code)) type = found;
    }
    Ref self = own(new_instance(type));
    if (!use_init) {
        oserror_init(self.get(), args, given);
    } else {
        Ref empty = tuple_new({});
        set_exception_field(self.get(), "args", empty.get());
    }
    return self;
}
Ref oserror_init_m(Obj self, Args a) {           // OSError_init: all done in __new__, unless a subclass said otherwise
    if (!oserror_use_init(type_of(self))) return none_ref();
    if (a.nkw != 0) raise_new("TypeError", type_of(self)->name + "() takes no keyword arguments");
    std::span<const Obj> args(a.data, a.npos);
    oserror_init(self, args, oserror_parse_args(args));
    return none_ref();
}
Ref or_none(Obj v) { return v.is_unset() ? none_ref() : Ref::share(v); }
std::string shown_str(Obj v) { Ref s = str_of(v); return as_str(s.get())->text; }
std::string shown_repr(Obj v) { Ref s = repr_of(v); return as_str(s.get())->text; }
Ref exception_str(Obj self, Args);
Ref exception_args(Obj self);
void no_wrapper_args(Args a, const char* name) {  // wrapper_call, check_num_args
    if (a.nkw != 0) raise_new("TypeError", std::string("wrapper ") + name + "() takes no keyword arguments");
    if (a.npos != 0) raise_new("TypeError", "expected 0 arguments, got " + std::to_string(a.npos));
}
Ref oserror_str(Obj self, Args a) {              // OSError_str
    no_wrapper_args(a, "__str__");
    Obj filename = exception_field(self, "filename"), filename2 = exception_field(self, "filename2");
    Obj myerrno = exception_field(self, "errno"), strerror = exception_field(self, "strerror");
    if (!filename.is_unset()) {
        std::string head = "[Errno " + shown_str(or_none(myerrno).get()) + "] " + shown_str(or_none(strerror).get()) + ": " + shown_repr(filename);
        if (!filename2.is_unset()) head += " -> " + shown_repr(filename2);
        return str_new(head);
    }
    if (!myerrno.is_unset() && !strerror.is_unset()) return str_new("[Errno " + shown_str(myerrno) + "] " + shown_str(strerror));
    return exception_str(self, a);
}
Ref oserror_reduce(Obj self, Args a) {           // OSError_reduce
    noargs(a, "OSError.__reduce__");
    Ref args = exception_args(self);
    Obj filename = exception_field(self, "filename"), filename2 = exception_field(self, "filename2");
    auto& items = static_cast<Tuple*>(args.get().object())->items;
    if (items.size() == 2 && !filename.is_unset()) {
        if (!filename2.is_unset()) args = tuple_new({items[0], items[1], filename, None(), filename2});
        else args = tuple_new({items[0], items[1], filename});
    }
    Ref cls = Ref::share(Obj::of(type_of(self)));
    bool has_dict = false;
    with_attribute_storage(self, [&](auto* inst) { has_dict = inst->dict != nullptr || inst->exposed() || !inst->order.empty(); });
    if (has_dict) {
        Ref d = getattr(self, N("__dict__"));
        return tuple_new({cls.get(), args.get(), d.get()});
    }
    return tuple_new({cls.get(), args.get()});
}
bool instance_dict_made(Obj self) {              // self->dict != NULL
    bool has_dict = false;
    with_attribute_storage(self, [&](auto* inst) { has_dict = inst->dict != nullptr || inst->exposed() || !inst->order.empty(); });
    return has_dict;
}
Ref exception_reduce(Obj self, Args a) {         // BaseException___reduce___impl: (type, args) or, with a dict made, (type, args, dict)
    noargs(a, "BaseException.__reduce__");
    Ref cls = Ref::share(Obj::of(type_of(self)));
    Obj args = exception_field(self, "args");
    Ref shown = args.is_unset() ? none_ref() : Ref::share(args);
    if (!args.is_unset() && instance_dict_made(self)) {
        Ref d = getattr(self, N("__dict__"));
        return tuple_new({cls.get(), shown.get(), d.get()});
    }
    return tuple_new({cls.get(), shown.get()});
}
Ref fields_state(Obj self, std::initializer_list<std::pair<const char*, const char*>> fields) {   // ImportError_getstate, AttributeError_getstate
    bool any = false;                            // (key, field): the dict's copy with the fields set, the dict, or None
    for (auto [key, field] : fields) any = any || !exception_field(self, field).is_unset();
    if (any) {
        Ref state = instance_dict_made(self) ? dict_copy(static_cast<Dict*>(getattr(self, N("__dict__")).get().object())) : dict_new();
        for (auto [key, field] : fields)
            if (Obj v = exception_field(self, field); !v.is_unset()) dict_set(static_cast<Dict*>(state.get().object()), Obj::of(N(key)), v);
        return state;
    }
    if (instance_dict_made(self)) return getattr(self, N("__dict__"));
    return none_ref();
}
Ref import_error_reduce(Obj self, Args a) {      // ImportError_reduce: (type, args) or (type, args, state)
    noargs(a, "ImportError.__reduce__");
    Ref state = fields_state(self, {{"name", "name"}, {"path", "path"}, {"name_from", "name_from"}});
    Ref cls = Ref::share(Obj::of(type_of(self)));
    Ref args = or_none(exception_field(self, "args"));
    if (state.get() == None()) return tuple_new({cls.get(), args.get()});
    return tuple_new({cls.get(), args.get(), state.get()});
}
Ref attribute_error_getstate(Obj self, Args a) { // AttributeError_getstate: name and args, never obj (GH-103352)
    noargs(a, "AttributeError.__getstate__");
    return fields_state(self, {{"name", "name"}, {"args", "args"}});
}
Ref attribute_error_reduce(Obj self, Args a) {   // AttributeError_reduce: (type, args, state)
    noargs(a, "AttributeError.__reduce__");
    Ref state = fields_state(self, {{"name", "name"}, {"args", "args"}});
    Ref cls = Ref::share(Obj::of(type_of(self)));
    Ref args = or_none(exception_field(self, "args"));
    return tuple_new({cls.get(), args.get(), state.get()});
}
Ref exception_setstate(Obj self, Args a) {       // BaseException___setstate___impl: each item set as an attribute, in the dict's order
    onearg(a, "BaseException.__setstate__");
    Obj state = a.pos(0);
    if (state == None()) return none_ref();
    if (!is_kind(state, Kind::Dict)) raise_new("TypeError", "state is not a dictionary");
    auto* d = static_cast<Dict*>(state.object());
    for (std::size_t pos = 0; pos < d->entries.size(); ++pos) {   // PyDict_Next, live
        if (d->entries[pos].key.is_unset()) continue;
        Ref key = Ref::share(d->entries[pos].key), value = Ref::share(d->entries[pos].value);
        if (as_str(key.get()) == nullptr) raise_new("TypeError", "attribute name must be string, not '" + type_of(key.get())->name + "'");
        setattr(self, as_str(key.get()), value.get());
    }
    return none_ref();
}
Ref traceback_lineno(Obj self) { return int_from_i64(static_cast<Traceback*>(self.object())->line); }
Ref traceback_next(Obj self) {                   // tb_next_get: the entry one call deeper, or None
    Obj next = static_cast<Traceback*>(self.object())->next.get();
    return is_kind(next, Kind::Traceback) ? Ref::share(next) : none_ref();
}
// traceback_tb_next_set_impl: None or another entry, and no loop. A relinked traceback is the program's: the runtime gives a frame's
// locals to the newest entry of that frame it still finds by walking the links (record_frame), as CPython's frame stays with the
// entry that holds it
void traceback_next_set(Obj self, Obj value) {
    if (value.is_unset()) raise_new("TypeError", "can't delete tb_next attribute");
    if (value != None() && !is_kind(value, Kind::Traceback))
        raise_new("TypeError", "expected traceback object, got '" + type_of(value)->name + "'");
    for (Obj cursor = value; is_kind(cursor, Kind::Traceback); cursor = static_cast<Traceback*>(cursor.object())->next.get())
        if (cursor.object() == self.object()) raise_new("ValueError", "traceback loop detected");
    static_cast<Traceback*>(self.object())->next = Ref::share(value);
}
Ref oserror_written_get(Obj self) {
    Obj v = exception_field(self, "written");
    if (v.is_unset()) raise_new("AttributeError", "characters_written");
    return Ref::share(v);
}
void oserror_written_set(Obj self, Obj v) {
    if (v.is_unset()) {
        if (exception_field(self, "written").is_unset()) raise_new("AttributeError", "characters_written");
        set_exception_field(self, "written", Obj{});
        return;
    }
    Ref value = int_from_i64(index_value(v, "ValueError"));
    set_exception_field(self, "written", value.get());
}
// _Py_T_OBJECT members: unset reads None, and del unsets. Named as the field, by template
template <const char* const& Name>
Ref member_get(Obj self) { return or_none(exception_field(self, Name)); }
template <const char* const& Name>
void member_set(Obj self, Obj v) { set_exception_field(self, Name, v); }
#define BELLA_FIELD(ident, text) constexpr const char* const ident = text;
BELLA_FIELD(F_ERRNO, "errno") BELLA_FIELD(F_STRERROR, "strerror") BELLA_FIELD(F_FILENAME, "filename") BELLA_FIELD(F_FILENAME2, "filename2")
BELLA_FIELD(F_MSG, "msg") BELLA_FIELD(F_LINENO, "lineno") BELLA_FIELD(F_OFFSET, "offset") BELLA_FIELD(F_TEXT, "text") BELLA_FIELD(F_END_LINENO, "end_lineno")
BELLA_FIELD(F_END_OFFSET, "end_offset") BELLA_FIELD(F_PRINT, "print_file_and_line") BELLA_FIELD(F_METADATA, "_metadata")
#undef BELLA_FIELD
// ---- BaseExceptionGroup (Objects/exceptions.c, 3.15.2) ----
bool is_exception_class(Obj v) {                 // PyExceptionClass_Check
    return is_kind(v, Kind::Class) && is_subclass(static_cast<ClassObject*>(v.object()), exception_class("BaseException"));
}
ClassObject*& exception_group_slot() {
    static ClassObject* c = nullptr;
    return c;
}
std::string short_type_name(ClassObject* c) {     // _PyType_Name: tp_name after its last dot
    auto dot = c->name.rfind('.');
    return dot == std::string::npos ? c->name : c->name.substr(dot + 1);
}
std::string tp_name_of(Obj v) { return is_none(v) ? "None" : type_of(v)->name; }   // _PyArg_BadArgument's words
Ref beg_new(Obj self, Args a) {                  // BaseExceptionGroup_new: PyArg_ParseTuple(args, "UO:BaseExceptionGroup.__new__")
    ClassObject* cls = new_wrapper_class(a, as_class(self));
    std::size_t given = a.npos - 1;              // the keywords are BaseException_init's to refuse
    if (given != 2) raise_new("TypeError", "BaseExceptionGroup.__new__() takes exactly 2 arguments (" + std::to_string(given) + " given)");
    Obj message = a.pos(1), sequence = a.pos(2);
    if (as_str(message) == nullptr) raise_new("TypeError", "BaseExceptionGroup.__new__() argument 1 must be str, not " + tp_name_of(message));
    if (!is_sequence(sequence)) raise_new("TypeError", "second argument (exceptions) must be a sequence");
    Ref excs_str;                                // saved in case a custom sequence is mutated
    if (!is_subclass(type_of(sequence), types().list) && !is_subclass(type_of(sequence), types().tuple)) excs_str = repr_of(sequence);
    Ref excs = invoke(Obj::of(types().tuple), {sequence});   // PySequence_Tuple
    const auto& items = static_cast<Tuple*>(excs.get().object())->items;
    if (items.empty()) raise_new("ValueError", "second argument (exceptions) must be a non-empty sequence");
    bool nested_base_exceptions = false;
    Obj exception = Obj::of(exception_class("Exception"));
    for (std::size_t i = 0; i < items.size(); ++i) {
        if (!is_exception_instance(items[i])) raise_new("ValueError", "Item " + std::to_string(i) + " of second argument (exceptions) is not an exception");
        if (!instance_of(items[i], exception)) nested_base_exceptions = true;
    }
    ClassObject* group = exception_group_slot();
    if (cls == group) {
        if (nested_base_exceptions) raise_new("TypeError", "Cannot nest BaseExceptions in an ExceptionGroup");
    } else if (cls == exception_class("BaseExceptionGroup")) {
        if (!nested_base_exceptions) cls = group;  // all nested exceptions are Exception subclasses: an ExceptionGroup
    } else if (nested_base_exceptions && is_subclass(cls, exception_class("Exception"))) {   // a subclass of the program's
        raise_new("TypeError", "Cannot nest BaseExceptions in '" + cls->name + "'");
    }
    auto* e = new_instance(cls);                 // BaseException_new: args is the positional arguments
    Ref r = own(e);
    std::vector<Obj> args;
    for (std::size_t i = 1; i < a.npos; ++i) {
        incref(a.pos(i));
        args.push_back(a.pos(i));
    }
    Ref args_tuple = tuple_steal(std::move(args));
    set_exception_field(r.get(), "args", args_tuple.get());
    set_exception_field(r.get(), "msg", message);
    set_exception_field(r.get(), "excs", excs.get());
    if (!excs_str.get().is_unset()) set_exception_field(r.get(), "excs_str", excs_str.get());
    return r;
}
Ref beg_str(Obj self, Args a) {                  // "%S (%zd sub-exception%s)"
    no_wrapper_args(a, "__str__");
    Ref text = str_of(exception_field(self, "msg"));
    std::size_t n = static_cast<Tuple*>(exception_field(self, "excs").object())->items.size();
    return str_new(as_str(text.get())->text + " (" + std::to_string(n) + " sub-exception" + (n > 1 ? "s" : "") + ")");
}
Ref beg_repr(Obj self, Args a) {                 // "%s(%R, %U)": self.exceptions shown as self.args[1] was, a list as a list
    no_wrapper_args(a, "__repr__");
    Ref exceptions_str;
    if (Obj saved = exception_field(self, "excs_str"); !saved.is_unset()) {
        exceptions_str = Ref::share(saved);
    } else {
        Obj excs = exception_field(self, "excs");
        Obj args = exception_field(self, "args");
        bool as_list = is_kind(args, Kind::Tuple) && static_cast<Tuple*>(args.object())->items.size() == 2 &&
                       is_subclass(type_of(static_cast<Tuple*>(args.object())->items[1]), types().list);
        if (as_list) {
            Ref list = invoke(Obj::of(types().list), {excs});
            exceptions_str = repr_of(list.get());
        } else {
            exceptions_str = repr_of(excs);
        }
    }
    Ref message = repr_of(exception_field(self, "msg"));
    return str_new(short_type_name(type_of(self)) + "(" + as_str(message.get())->text + ", " + as_str(exceptions_str.get())->text + ")");
}
Ref beg_message_get(Obj self) { return or_none(exception_field(self, "msg")); }
Ref beg_exceptions_get(Obj self) { return or_none(exception_field(self, "excs")); }
Ref beg_derive(Obj self, Args a) {               // BaseExceptionGroup.derive(excs, /): a BaseExceptionGroup of the same message
    onearg(a, "BaseExceptionGroup.derive");
    return invoke(Obj::of(exception_class("BaseExceptionGroup")), {exception_field(self, "msg"), a.pos(0)});
}
enum class Matcher { ByType, ByPredicate, InstanceIds };
struct SplitMatcher {                            // exceptiongroup_split_recursive's matcher_type and matcher_value
    Matcher type;
    Obj value;
    const std::unordered_set<const Object*>* ids = nullptr;   // InstanceIds: the leaves wanted (a set of PyLong ids in the C)
};
Matcher matcher_type(Obj value) {                // get_matcher_type
    if (callable_object(value) && !is_kind(value, Kind::Class)) return Matcher::ByPredicate;
    if (is_exception_class(value)) return Matcher::ByType;
    if (is_kind(value, Kind::Tuple) && !is_subclass_instance(value)) {
        bool all = true;
        for (Obj item : static_cast<Tuple*>(value.object())->items) all = all && is_exception_class(item);
        if (all) return Matcher::ByType;
    }
    raise_new("TypeError", "expected an exception type, a tuple of exception types, or a callable (other than a class)");
}
bool split_matches(Obj exc, const SplitMatcher& m) {   // exceptiongroup_split_check_match
    if (m.type == Matcher::ByType) return exception_matches(exc, m.value);   // PyErr_GivenExceptionMatches
    if (m.type == Matcher::InstanceIds) return !is_exception_group(exc) && m.ids->contains(exc.object());   // a leaf, by identity
    Ref answer = invoke(m.value, {exc});
    return truth(answer.get());
}
Ref beg_subset(Obj orig, Obj excs) {             // exceptiongroup_subset: orig.derive(excs) with orig's metadata, Unset for no excs
    if (static_cast<List*>(excs.object())->items.empty()) return Ref{};
    Ref derive = getattr(orig, N("derive"));
    Ref eg = invoke(derive.get(), {excs});
    if (!is_exception_group(eg.get())) raise_new("TypeError", "derive must return an instance of BaseExceptionGroup");
    if (Obj tb = exception_field(orig, "__traceback__"); !tb.is_unset()) set_exception_field(eg.get(), "__traceback__", tb);
    set_exception_field(eg.get(), "__context__", exception_field(orig, "__context__"));   // PyException_SetContext
    set_exception_field(eg.get(), "__cause__", exception_field(orig, "__cause__"));       // PyException_SetCause: suppress_context = 1
    set_exception_field(eg.get(), "__suppress_context__", boolean(true));
    Ref notes = optional_getattr(orig, N("__notes__"));
    if (!notes.get().is_unset() && is_sequence(notes.get())) {   // a copy, so the parts have notes lists of their own
        Ref copy = invoke(Obj::of(types().list), {notes.get()});
        setattr(eg.get(), N("__notes__"), copy.get());
    }
    return eg;
}
struct SplitDepth {                              // _Py_EnterRecursiveCall(" in exceptiongroup_split_recursive")
    static int& depth() {
        static int d = 0;
        return d;
    }
    SplitDepth() {
        if (++depth() > recursion_limit()) {
            --depth();
            // CPython's limit here is its C stack's, which no program can reproduce: the nesting is refused past Python's
            throw NotImplemented("an exception group nested deeper than the recursion limit (CPython's limit there is the C stack's)");
        }
    }
    ~SplitDepth() { --depth(); }
};
std::pair<Ref, Ref> split_recursive(Obj exc, const SplitMatcher& m, bool construct_rest) {   // exceptiongroup_split_recursive
    if (split_matches(exc, m)) return {Ref::share(exc), Ref{}};   // a full match
    if (!is_exception_group(exc)) return {Ref{}, construct_rest ? Ref::share(exc) : Ref{}};   // a leaf and no match
    Ref match_list = list_new({});               // a partial match
    Ref rest_list = construct_rest ? list_new({}) : Ref{};
    Ref excs = Ref::share(exception_field(exc, "excs"));
    for (Obj e : static_cast<Tuple*>(excs.get().object())->items) {
        Ref inner = Ref::share(e);
        std::pair<Ref, Ref> part;
        {
            SplitDepth guard;
            part = split_recursive(inner.get(), m, construct_rest);
        }
        if (!part.first.get().is_unset()) list_append(match_list.get(), part.first.get());
        if (!part.second.get().is_unset()) list_append(rest_list.get(), part.second.get());
    }
    Ref match = beg_subset(exc, match_list.get());
    Ref rest = construct_rest ? beg_subset(exc, rest_list.get()) : Ref{};
    return {std::move(match), std::move(rest)};
}
Ref beg_split(Obj self, Args a) {                // BaseExceptionGroup.split(matcher_value, /) -> (match, rest)
    onearg(a, "BaseExceptionGroup.split");
    Matcher type = matcher_type(a.pos(0));
    auto [match, rest] = split_recursive(self, SplitMatcher{type, a.pos(0)}, true);
    return tuple_new({match.get().is_unset() ? None() : match.get(), rest.get().is_unset() ? None() : rest.get()});
}
Ref beg_subgroup(Obj self, Args a) {             // BaseExceptionGroup.subgroup(matcher_value, /) -> match
    onearg(a, "BaseExceptionGroup.subgroup");
    Matcher type = matcher_type(a.pos(0));
    auto parts = split_recursive(self, SplitMatcher{type, a.pos(0)}, false);
    return parts.first.get().is_unset() ? none_ref() : std::move(parts.first);
}
}  // namespace

// ---- except* (Python/ceval.c: CHECK_EG_MATCH, _PyEval_ExceptionGroupMatch; Objects/exceptions.c: _PyExc_PrepReraiseStar,
// exception_group_projection, is_same_exception_metadata), what the frontend's desugaring of try/except* calls ----
std::pair<Ref, Ref> eg_match(Obj exc_value, Obj match_type) {   // (rest, match)
    // _PyEval_CheckExceptStarTypeValid: the except clause's check, then no exception group type (PyObject_IsSubclass)
    check_except_type_valid(match_type);
    bool group = false;
    if (is_kind(match_type, Kind::Tuple)) {
        for (Obj item : static_cast<Tuple*>(match_type.object())->items)
            if (object_issubclass(item, Obj::of(exception_class("BaseExceptionGroup")))) {
                group = true;
                break;
            }
    } else {
        group = object_issubclass(match_type, Obj::of(exception_class("BaseExceptionGroup")));
    }
    if (group) raise_new("TypeError", "catching ExceptionGroup with except* is not allowed. Use except instead.");
    if (exc_value == None()) return {none_ref(), none_ref()};
    if (exception_matches(exc_value, match_type)) {   // a full match of the exception itself
        if (is_exception_group(exc_value)) return {none_ref(), Ref::share(exc_value)};
        // a bare exception, wrapped: _PyExc_CreateExceptionGroup("", (exc,)), its traceback this frame's (_PyTraceBack_FromFrame)
        Ref excs = tuple_new({exc_value});
        Ref msg = str_new("");
        Ref wrapped = invoke(Obj::of(exception_class("BaseExceptionGroup")), {msg.get(), excs.get()});
        traceback_from_current_frame(wrapped.get());
        return {none_ref(), std::move(wrapped)};
    }
    if (is_exception_group(exc_value)) {             // a partial match: split, as the instance's split method does it
        Ref split = getattr(exc_value, intern("split"));
        Ref pair = invoke(split.get(), {match_type});
        if (!is_kind(pair.get(), Kind::Tuple) || is_subclass_instance(pair.get()))   // PyTuple_CheckExact
            raise_new("TypeError", type_of(exc_value)->name + ".split must return a tuple, not " + type_of(pair.get())->name);
        auto& items = static_cast<Tuple*>(pair.get().object())->items;
        if (items.size() < 2)                         // longer tuples allowed, for backwards compatibility
            raise_new("TypeError", type_of(exc_value)->name + ".split must return a 2-tuple, got tuple of size " + std::to_string(items.size()));
        return {Ref::share(items[1]), Ref::share(items[0])};
    }
    return {Ref::share(exc_value), none_ref()};
}

namespace {
void leaf_ids(Obj exc, std::unordered_set<const Object*>& ids) {   // collect_exception_group_leaf_ids
    if (exc == None()) return;
    if (!is_exception_group(exc)) {
        ids.insert(exc.object());
        return;
    }
    Ref excs = Ref::share(exception_field(exc, "excs"));
    for (Obj e : static_cast<Tuple*>(excs.get().object())->items) {
        SplitDepth guard;                            // _Py_EnterRecursiveCall(" in collect_exception_group_leaf_ids")
        leaf_ids(e, ids);
    }
}
bool same_metadata(Obj e1, Obj e2) {              // is_same_exception_metadata: the notes field is never set in 3.15, so equal
    for (const char* f : {"__traceback__", "__cause__", "__context__"})
        if (exception_field(e1, f) != exception_field(e2, f)) return false;
    return true;
}
}  // namespace

Ref prep_reraise_star(Obj orig, Obj excs) {      // _PyExc_PrepReraiseStar: what the statement re-raises, None for nothing
    auto& items = static_cast<List*>(excs.object())->items;
    if (items.empty()) return none_ref();
    if (!is_exception_group(orig)) return Ref::share(items[0]);   // a bare exception, wrapped: one clause ran at most
    Ref raised = list_new({});
    std::vector<Obj> reraised;
    std::vector<Ref> snapshot;                   // the list's items, held while derive and the comparisons run
    for (Obj e : items) snapshot.push_back(Ref::share(e));
    for (const Ref& e : snapshot) {
        if (e.get() == None()) continue;
        if (same_metadata(e.get(), orig)) reraised.push_back(e.get());
        else list_append(raised.get(), e.get());
    }
    // exception_group_projection: orig's part made of the reraised groups' leaves, with orig's nesting (derive)
    std::unordered_set<const Object*> ids;
    for (Obj e : reraised) leaf_ids(e, ids);
    auto parts = split_recursive(orig, SplitMatcher{Matcher::InstanceIds, Obj{}, &ids}, false);
    Ref reraised_eg = parts.first.get().is_unset() ? none_ref() : std::move(parts.first);
    auto& got = static_cast<List*>(raised.get().object())->items;
    if (got.empty()) return reraised_eg;
    if (reraised_eg.get() != None()) list_append(raised.get(), reraised_eg.get());
    if (got.size() > 1) {
        Ref msg = str_new("");
        return invoke(Obj::of(exception_class("BaseExceptionGroup")), {msg.get(), raised.get()});   // _PyExc_CreateExceptionGroup
    }
    return Ref::share(got[0]);
}

namespace {
// ---- SyntaxError ----
Ref syntax_error_init(Obj self, Args a) {        // SyntaxError_init
    if (a.nkw != 0) raise_new("TypeError", type_of(self)->name + "() takes no keyword arguments");
    set_args(self, a);
    if (a.npos >= 1) set_exception_field(self, "msg", a.pos(0));
    if (a.npos == 2) {
        Ref info = invoke(Obj::of(types().tuple), {a.pos(1)});
        auto& items = static_cast<Tuple*>(info.get().object())->items;
        if (items.size() < 4) raise_new("TypeError", "function takes at least 4 arguments (" + std::to_string(items.size()) + " given)");
        if (items.size() > 7) raise_new("TypeError", "function takes at most 7 arguments (" + std::to_string(items.size()) + " given)");
        set_exception_field(self, "filename", items[0]);
        set_exception_field(self, "lineno", items[1]);
        set_exception_field(self, "offset", items[2]);
        set_exception_field(self, "text", items[3]);
        set_exception_field(self, "end_lineno", items.size() > 4 ? items[4] : Obj{});
        set_exception_field(self, "end_offset", items.size() > 5 ? items[5] : Obj{});
        set_exception_field(self, "_metadata", items.size() > 6 ? items[6] : Obj{});
        if (items.size() == 5) raise_new("TypeError", "end_offset must be provided when end_lineno is provided");
    }
    return none_ref();
}
Ref syntax_error_str(Obj self, Args a) {         // SyntaxError_str
    no_wrapper_args(a, "__str__");
    Obj filename = exception_field(self, "filename"), lineno = exception_field(self, "lineno"), msg = exception_field(self, "msg");
    std::string base;
    bool has_file = !filename.is_unset() && as_str(filename) != nullptr;
    if (has_file) {                              // my_basename
        const std::string& whole = as_str(filename)->text;
        std::size_t slash = whole.rfind('/');
        base = slash == std::string::npos ? whole : whole.substr(slash + 1);
    }
    bool have_lineno = !lineno.is_unset() && (lineno.is_small() || is_kind(lineno, Kind::BigInt));
    std::string shown = shown_str(or_none(msg).get());
    if (!has_file && !have_lineno) return str_new(shown);
    std::int64_t line = -1;
    if (have_lineno && !int_fits_i64(lineno, line)) line = -1;   // PyLong_AsLongAndOverflow: -1 on overflow
    if (has_file && have_lineno) return str_new(shown + " (" + base + ", line " + std::to_string(line) + ")");
    if (has_file) return str_new(shown + " (" + base + ")");
    return str_new(shown + " (line " + std::to_string(line) + ")");
}
// none_new, notimplemented_new, ellipsis_new: the one there is, and no arguments
template <int Which>
Ref singleton_new(Obj, Args a) {
    ClassObject* owner = Which == 0 ? types().none : Which == 1 ? types().notimplemented : types().ellipsis;
    new_wrapper_class(a, owner);
    if (a.npos > 1 || a.nkw != 0) raise_new("TypeError", std::string(Which == 0 ? "NoneType" : Which == 1 ? "NotImplementedType" : "EllipsisType") + " takes no arguments");
    return Ref::share(Which == 0 ? None() : Which == 1 ? Obj::of(NOTIMPLEMENTED) : Obj::of(ELLIPSIS));
}
// StopIteration_init, and the member: its first argument, or None
Ref stop_iteration_init(Obj self, Args a) {
    if (a.nkw != 0) raise_new("TypeError", type_of(self)->name + "() takes no keyword arguments");
    set_args(self, a);
    set_exception_field(self, "value", a.npos > 0 ? a.pos(0) : None());
    return none_ref();
}
Ref stop_iteration_value_get(Obj self) { Obj v = exception_field(self, "value"); return v.is_unset() ? none_ref() : Ref::share(v); }
void stop_iteration_value_set(Obj self, Obj v) { set_exception_field(self, "value", v); }
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
Ref exception_add_note(Obj self, Args a) {        // BaseException.add_note: __notes__ as the instance answers for it, a list made when it has none
    arity(a, "add_note", 1, 1);
    Obj note = a.pos(0);
    if (as_str(note) == nullptr) raise_new("TypeError", "add_note() argument must be str, not " + type_of(note)->name);
    Ref notes = optional_getattr(self, N("__notes__"));
    if (notes.get().is_unset()) {
        notes = list_new({});
        setattr(self, N("__notes__"), notes.get());
    } else if (!is_kind(notes.get(), Kind::List)) {
        raise_new("TypeError", "Cannot add note: __notes__ is not a list");
    }
    list_append(notes.get(), note);
    return none_ref();
}
Ref field_or_none(Obj self, const char* name) {
    Obj v = exception_field(self, name);
    return v.is_unset() ? none_ref() : Ref::share(v);
}
Ref exception_args_get(Obj self) { return exception_args(self); }
void exception_args_set(Obj self, Obj v) {          // PySequence_Tuple
    if (v.is_unset()) raise_new("TypeError", "args may not be deleted");
    Ref t;
    if (is_exact_tuple(v)) {                         // a subclass is iterated, as anything else is (review F17 #12)
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
    if (is_kind(mapping, Kind::Proxy) && proxied(mapping) != nullptr) {
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
Ref sentinel_name_get(Obj self) { return getattr(self, N("_s_name")); }
Ref sentinel_module_get(Obj self) {
    Ref v = optional_getattr(self, N("_s_module"));
    if (v.get().is_unset()) raise_attribute_error(self, N("__module__"), "'sentinel' object has no attribute '__module__'");
    return v;
}
void sentinel_module_set(Obj self, Obj v) {
    if (!v.is_unset()) setattr(self, N("_s_module"), v);
    else if (optional_getattr(self, N("_s_module")).get().is_unset()) raise_attribute_error(self, N("__module__"), "__module__");
    else delattr(self, N("_s_module"));
}
Ref union_name(Obj) { return str_new("Union"); }
Ref union_origin(Obj) { return Ref::share(Obj::of(types().union_)); }
Ref union_parameters(Obj self) { return bootstrap_call("_union_parameters", self); }
Ref class_getitem(Obj self, Args a) {            // Py_GenericAlias as a built-in type's __class_getitem__
    onearg(a, as_class(self)->qualname + ".__class_getitem__");
    return generic_alias(self, a.pos(0));
}
}  // namespace
bool is_exception_group(Obj v) { return is_kind(v, Kind::Instance) && is_subclass(type_of(v), exception_class("BaseExceptionGroup")); }
ClassObject* exception_group_class() { return exception_group_slot(); }
Ref generic_alias(Obj origin, Obj args) {
    return invoke(dict_get(bootstrap_of_types()->dict, Obj::of(N("GenericAlias"))), {origin, args});
}
void forget_python_origin(ClassObject* c);
static void object_method_written(Module* bootstrap, const char* name, const char* written);
void present_as_c_types(Module* bootstrap) {
    bootstrap_of_types() = bootstrap;
    Obj ns = dict_get(bootstrap->dict, Obj::of(N("SimpleNamespace")));
    if (!is_kind(ns, Kind::Class)) return;
    auto* c = static_cast<ClassObject*>(ns.object());
    c->name = "types.SimpleNamespace";
    c->name_prefix = 6;
    c->attrs.set(N("__dict__"), Obj::of(new GetSet("__dict__", c, instance_dict, readonly_dict)));
    note_prelude_class(c);
    present_methods(c);
    auto* ga = static_cast<ClassObject*>(dict_get(bootstrap->dict, Obj::of(N("GenericAlias"))).object());
    ga->name = "types.GenericAlias";
    ga->name_prefix = 6;
    ga->forwards_attributes = true;
    note_prelude_class(ga);
    present_methods(ga);
    ga->has_weakref = cpython_has("weakref", "types.GenericAlias");
    auto* ga_iterator = static_cast<ClassObject*>(dict_get(bootstrap->dict, Obj::of(N("generic_alias_iterator"))).object());
    note_prelude_class(ga_iterator);
    present_methods(ga_iterator);
    ga_iterator->final_type = true;
    getset(ga, "__parameters__", ga_parameters);
    getset(ga, "__typing_unpacked_tuple_args__", ga_unpacked_tuple_args);
    for (ClassObject* t : builtin_types())
        if (cpython_has(t->name, "__class_getitem__")) method(t, "__class_getitem__", class_getitem, Binding::ClassMethod);
    auto* un = static_cast<ClassObject*>(dict_get(bootstrap->dict, Obj::of(N("Union"))).object());
    un->name = "typing.Union";
    un->name_prefix = 7;
    note_prelude_class(un);
    un->final_type = cpython_has("final", un->name);
    un->has_weakref = cpython_has("weakref", "typing.Union");
    un->disallow_instantiation = true;
    present_methods(un);
    un->mapping_getitem = true;
    forget_python_origin(un);
    getset(un, "__name__", union_name);
    getset(un, "__qualname__", union_name);
    getset(un, "__origin__", union_origin);
    getset(un, "__parameters__", union_parameters);
    types().union_ = un;
    auto* se = static_cast<ClassObject*>(dict_get(bootstrap->dict, Obj::of(N("sentinel"))).object());
    note_prelude_class(se);
    se->final_type = cpython_has("final", "sentinel");
    se->has_weakref = cpython_has("weakref", "sentinel");
    forget_python_origin(se);
    present_methods(se);
    se->del_attr(N("__module__"));
    if (Obj doc = cpython_doc("type:sentinel"); doc != None()) se->set_attr(N("__doc__"), doc);
    for (auto [name, get, set] : std::initializer_list<std::tuple<const char*, Ref (*)(Obj), void (*)(Obj, Obj)>>{
             {"__name__", sentinel_name_get, nullptr}, {"__module__", sentinel_module_get, sentinel_module_set}}) {
        auto* g = new GetSet(name, se, get, set);
        g->cls = types().member_descriptor;
        g->deletable = set != nullptr;
        se->attrs.set(N(name), Obj::of(g));
    }
    dict_set(builtins_module()->dict, Obj::of(N("sentinel")), Obj::of(se));
    object_method_written(bootstrap, "__reduce_ex__", "_object_reduce_ex");
    object_method_written(bootstrap, "__reduce__", "_object_reduce");
    object_method_written(bootstrap, "__getstate__", "_object_getstate");
    auto* builder = static_cast<ClassObject*>(dict_get(bootstrap->dict, Obj::of(N("_UnionBuilder"))).object());
    note_prelude_class(builder);
}
Ref type_or(Obj a, Obj b) {
    Ref fn = Ref::share(dict_get(bootstrap_of_types()->dict, Obj::of(N("_union_type_or"))));
    return invoke(fn.get(), {a, b});
}
Ref i_present_c_class(Obj, Args a) {             // (cls, module): named for the module, made by the module's functions alone
    positional_only(a, "_present", 4, 4);        // (cls, module, its __getitem__ is mp_subscript alone, its METH_METHOD methods)
    ClassObject* c = as_class(a.pos(0));
    present_native_class(c, as_str(a.pos(1))->text);
    c->disallow_instantiation = true;
    c->mapping_getitem = truth(a.pos(2));
    for (Obj n : static_cast<Tuple*>(a.pos(3).object())->items)
        if (const Obj* m = c->attrs.find(intern(as_str(n)->text)); m != nullptr && is_kind(*m, Kind::Builtin)) static_cast<Builtin*>(m->object())->bound_cmethod = true;
    return none_ref();
}
Ref i_bella_new_instance(Obj, Args a) {
    positional_only(a, "_bella_new_instance", 1, 1);
    ClassObject* c = as_class(a.pos(0));
    if (c == nullptr) raise_new("TypeError", "_bella_new_instance(X): X is not a type object (" + type_of(a.pos(0))->name + ")");
    return own(new_instance(c));
}

// What a class statement leaves that a type written in C does not have; the layout is held elsewhere
Ref instance_dict_of(Obj self) { return instance_dict_getset()->get(self); }
Ref int_from_number(Obj x) { return number_long(x); }
void present_native_class(ClassObject* c, const std::string& module);
// Objects/structseq.c, under bootstrap.py's _bella_structseq: the fields of the sequence are the tuple's, those past it a
// tuple in the one slot the class declares; a member reads either, by the field's place
namespace {
Tuple* structseq_past(Obj self) { return static_cast<Tuple*>(static_cast<TupleInstance*>(self.object())->fields[0].object()); }
template <std::size_t I>
Ref structseq_member(Obj self) {
    auto& items = static_cast<Tuple*>(self.object())->items;
    return Ref::share(I < items.size() ? items[I] : structseq_past(self)->items[I - items.size()]);
}
template <std::size_t... I>
constexpr std::array<Ref (*)(Obj), sizeof...(I)> structseq_members(std::index_sequence<I...>) { return {structseq_member<I>...}; }
}  // namespace
Ref i_bella_structseq_finish(Obj, Args a) {      // (cls, module, fields, has_new)
    positional_only(a, "_bella_structseq_finish", 4, 4);
    static constexpr auto members = structseq_members(std::make_index_sequence<32>{});
    auto* c = as_class(a.pos(0));
    present_native_class(c, as_str(a.pos(1))->text);
    c->del_attr(N("_s_past"));
    c->disallow_instantiation = !truth(a.pos(3));
    auto& fields = static_cast<List*>(a.pos(2).object())->items;
    for (std::size_t i = 0; i < fields.size(); ++i) {
        if (fields[i] == None()) continue;
        const Str* name = intern(as_str(fields[i])->text);
        auto* g = new GetSet(name->text.c_str(), c, members.at(i), nullptr);
        g->cls = types().member_descriptor;
        c->attrs.set(name, Obj::of(g));
    }
    return none_ref();
}
Ref i_bella_structseq_make(Obj, Args a) {        // (cls, items, past), lists: PyStructSequence_New and the filling
    positional_only(a, "_bella_structseq_make", 3, 3);
    auto* made = new TupleInstance(as_class(a.pos(0)));
    Ref r = own(made);
    for (Obj v : static_cast<List*>(a.pos(1).object())->items) {
        incref(v);
        made->items.push_back(v);
    }
    Ref past = tuple_copy(static_cast<List*>(a.pos(2).object())->items);
    made->fields[0] = past.release();
    return r;
}
Ref i_bella_structseq_hidden(Obj, Args a) {
    positional_only(a, "_bella_structseq_hidden", 1, 1);
    return Ref::share(Obj::of(structseq_past(a.pos(0))));
}
Ref i_structseq(Obj, Args a) { return invoke(dict_get(bootstrap_of_types()->dict, Obj::of(N("_bella_structseq"))), a); }
// The methods of a C type the prelude writes in Python are what the names table says, as a built-in type's own are, so that
// type(), repr(), binding and the receiver's check see one kind of thing; what runs is the prelude's function. The file's other
// functions, which have no row, stay as they are: they are its own.
Ref i_bella_pickle_layout(Obj, Args a) {         // _PyObject's itemsize and basicsize tests, by the first type written in C
    positional_only(a, "_bella_pickle_layout", 1, 1);
    ClassObject* c = as_class(a.pos(0));
    while (!c_type(c) && !c->bases.empty()) c = tp_base(c);   // a subclass has its base's C fields (property's, staticmethod's)
    return int_from_i64(cpython_has("itemsize", c->name) ? 2 : cpython_has("state", c->name) ? 1 : 0);
}
Ref i_bella_no_tp_new(Obj, Args a) {             // tp_new is NULL: a static type with object for its base and no __new__ of its own
    positional_only(a, "_bella_no_tp_new", 1, 1);
    for (ClassObject* c : as_class(a.pos(0))->mro) {
        if (c == types().object) return Ref::steal(boolean(false));
        if (c->heap_type && !c_type(c)) continue;
        if (!cpython_attribute_kind(c, "__new__").empty()) return Ref::steal(boolean(false));
        if (auto flags = cpython_type_number("flags", c); flags && (*flags & (1 << 9))) continue;   // a heap type of CPython's (PyType_FromSpec): tp_new inherited
        if (tp_base(c) == types().object) return Ref::steal(boolean(true));
    }
    return Ref::steal(boolean(false));
}
Ref i_bella_tp_name_of(Obj, Args a) {
    positional_only(a, "_bella_tp_name_of", 1, 1);
    return str_new(as_class(a.pos(0))->name);
}
Ref i_bella_instance_dict(Obj, Args a) {         // the dict, or None when it is empty or there is none (_PyObject_IsInstanceDictEmpty)
    positional_only(a, "_bella_instance_dict", 1, 1);
    Obj self = a.pos(0);
    bool empty = true;
    if (!with_attribute_storage(self, [&](auto* inst) { empty = inst->order.empty() && inst->dict == nullptr; })) return none_ref();
    if (empty) return none_ref();
    Ref d = instance_dict_of(self);
    return truth(d.get()) ? d : none_ref();
}
// object's methods that are written in bootstrap.py
static void object_method_written(Module* bootstrap, const char* name, const char* written) {
    auto* b = new Builtin(name, nullptr, Obj{}, Binding::Method);
    b->owner = types().object;
    b->written = Ref::share(dict_get(bootstrap->dict, Obj::of(intern(written))));
    b->flags |= IMMORTAL;
    types().object->attrs.set(intern(name), Obj::of(b));
}
// A property the prelude writes where the C has a member or a getset: the descriptor the names table says, reading it. GetSet has a plain
// function, so a pool of them, each with the Python getter of its place
namespace {
std::vector<Ref>& python_getters() {
    static std::vector<Ref> pool;
    return pool;
}
template <std::size_t I>
Ref python_getter(Obj self) { return invoke(python_getters()[I].get(), {self}); }
template <std::size_t... I>
constexpr std::array<Ref (*)(Obj), sizeof...(I)> python_getter_table(std::index_sequence<I...>) { return {python_getter<I>...}; }
constexpr auto PYTHON_GETTERS = python_getter_table(std::make_index_sequence<256>{});
std::vector<Ref>& python_setters() {
    static std::vector<Ref> pool;
    return pool;
}
std::vector<Ref>& python_deleters() {           // beside each setter: what a deletion calls, None where the prelude wrote none
    static std::vector<Ref> pool;
    return pool;
}
template <std::size_t I>
void python_setter(Obj self, Obj value) {
    if (value.is_unset()) {
        if (python_deleters()[I].get() == None()) raise_new("AttributeError", "cannot delete attribute");
        invoke(python_deleters()[I].get(), {self});
        return;
    }
    invoke(python_setters()[I].get(), {self, value});
}
template <std::size_t... I>
constexpr std::array<void (*)(Obj, Obj), sizeof...(I)> python_setter_table(std::index_sequence<I...>) { return {python_setter<I>...}; }
constexpr auto PYTHON_SETTERS = python_setter_table(std::make_index_sequence<48>{});
}  // namespace
static Ref generic_new(Obj self, Args a) {        // PyType_GenericNew, under tp_new_wrapper: the arguments are __init__'s
    return own(new_instance(new_wrapper_class(a, as_class(self))));
}
void present_methods(ClassObject* c) {
    if (!c->attrs.contains(N("__new__")) && cpython_attribute_kind(c, "__new__") == "builtin_function_or_method") new_method(c, generic_new);   // its type has a tp_new of its own
    Obj staticmethod = dict_get(builtins_module()->dict, Obj::of(N("staticmethod")));
    Obj classmethod = dict_get(builtins_module()->dict, Obj::of(N("classmethod")));
    for (auto& [name, v] : c->attrs.items()) {
        std::string_view kind = cpython_attribute_kind(c, name->text);
        if (is_kind(v, Kind::Builtin)) {         // one the file's C++ made for it
            auto* made = static_cast<Builtin*>(v.object());
            if (made->self.is_unset() && made->binding == Binding::Method && kind == "wrapper_descriptor") made->cls = types().wrapper_descriptor;
            continue;
        }
        // a property, or the _GetSet that property, staticmethod and classmethod write their own members with (builtins.py)
        Obj property = dict_get(builtins_module()->dict, Obj::of(N("property")));
        Obj own_getset = dict_get(intrinsics(), Obj::of(N("_GetSet")));
        if (((!property.is_unset() && type_of(v) == as_class(property)) || (!own_getset.is_unset() && type_of(v) == as_class(own_getset))) &&
            (kind == "member_descriptor" || kind == "getset_descriptor")) {
            Ref getter = getattr(v, N("fget")), setter = getattr(v, N("fset")), deleter = getattr(v, N("fdel"));
            if (getter.get() == None()) throw NotImplemented("a prelude's property with no getter: " + name->text);
            if (setter.get() == None() && deleter.get() != None()) throw NotImplemented("a prelude's property with a deleter and no setter: " + name->text);
            if (python_getters().size() == PYTHON_GETTERS.size()) throw NotImplemented("more properties in the prelude than the pool of getters holds");
            if (setter.get() != None() && python_setters().size() == PYTHON_SETTERS.size()) throw NotImplemented("more property setters in the prelude than the pool holds");
            auto* g = new GetSet(name->text.c_str(), c, PYTHON_GETTERS[python_getters().size()], setter.get() == None() ? nullptr : PYTHON_SETTERS[python_setters().size()]);
            python_getters().push_back(std::move(getter));
            if (setter.get() != None()) {
                g->deletable = deleter.get() != None();   // the C setter is given NULL: what it does then is the prelude's deleter
                python_setters().push_back(std::move(setter));
                python_deleters().push_back(std::move(deleter));
            }
            if (kind == "member_descriptor") g->cls = types().member_descriptor;
            if (!own_getset.is_unset() && type_of(v) == as_class(own_getset)) g->doc = "";   // the three types' C gives its members and getsets no doc
            decref(c->attrs.set(name, Obj::of(g)));
            continue;
        }
        Ref written;
        Binding binding = Binding::Method;
        if (is_kind(v, Kind::PyFunction) && (kind == "wrapper_descriptor" || kind == "method_descriptor")) {
            written = Ref::share(v);
        } else if (!staticmethod.is_unset() && type_of(v) == as_class(staticmethod) && kind == "builtin_function_or_method") {
            written = getattr(v, N("__func__"));
            binding = Binding::Function;
        } else if (!classmethod.is_unset() && type_of(v) == as_class(classmethod) && kind == "classmethod_descriptor") {
            written = getattr(v, N("__func__"));
            binding = Binding::ClassMethod;
        } else {
            continue;
        }
        auto* b = new Builtin(name->text, nullptr, Obj{}, binding);
        b->owner = c;
        b->written = std::move(written);
        b->flags |= IMMORTAL;
        if (kind == "wrapper_descriptor") b->cls = types().wrapper_descriptor;
        decref(c->attrs.set(name, Obj::of(b)));
    }
    present_descriptor_kinds(c);
}
void forget_python_origin(ClassObject* c) {
    for (const char* n : {"__slots__", "__firstlineno__", "__static_attributes__", "__weakref__"})   // a C type's list has no getset
        if (c->attrs.contains(N(n))) c->del_attr(N(n));
}
// PyObject_GenericSetDict, the __dict__ of a C type with a tp_dictoffset (staticmethod, classmethod): any dict, and never none
static void set_generic_dict(Obj self, Obj d) {
    if (d.is_unset()) raise_new("TypeError", "cannot delete __dict__");
    set_instance_dict(self, d);
}
// A C++ getset is the kind of descriptor CPython's type has under that name, a member (PyMemberDef) or a getset (PyGetSetDef):
// the names table decides, where a file's own choice differed. And a C type whose __dict__ is its own descriptor in CPython
// (BaseException's and staticmethod's getset, PyObject_GenericGetDict and PyObject_GenericSetDict) has its own here, not the
// one every class with a dict shares: its __objclass__ is the type, it takes any dict, and it is never deleted (case C-3-56).
void present_descriptor_kinds(ClassObject* c) {
    c->dict_kind = dict_kind_of(c);              // the dict its instances have is CPython's type's too (C-3-59)
    if (const Obj* d = c->attrs.find(N("__dict__")); d != nullptr && *d == Obj::of(instance_dict_getset()) && cpython_attribute_kind(c, "__dict__") == "getset_descriptor") {
        getset(c, "__dict__", instance_dict, set_generic_dict);
        static_cast<GetSet*>(c->attrs.find(N("__dict__"))->object())->deletable = true;   // the setter is asked, and refuses
    }
    for (auto& [name, v] : c->attrs.items())
        if (is_kind(v, Kind::GetSet) && v != Obj::of(instance_dict_getset())) {
            std::string_view kind = cpython_attribute_kind(c, name->text);
            if (kind == "member_descriptor") v.object()->cls = types().member_descriptor;
            else if (kind == "getset_descriptor") v.object()->cls = types().getset_descriptor;
        }
}
// A class of builtins.py (property, staticmethod, classmethod) as the static type it is in CPython: no __module__ of its own
// (tp_name says it), tp_doc as its __doc__ unless a member has that name, the __dict__ that C declares, and Py_GenericAlias
void present_builtin_class(ClassObject* c) {
    if (c->attrs.contains(N("__module__")) && !cpython_has(c->name, "__module__")) c->del_attr(N("__module__"));
    if (cpython_attribute_kind(c, "__doc__") == "str")
        if (Obj doc = cpython_doc("type:" + c->name); doc != None() && !as_str(doc)->text.empty()) c->set_attr(N("__doc__"), doc);
    present_descriptor_kinds(c);
    if (cpython_has(c->name, "__class_getitem__") && !c->attrs.contains(N("__class_getitem__"))) method(c, "__class_getitem__", class_getitem, Binding::ClassMethod);
}
// A class the prelude writes for a type a built-in module has in C: its tp_name, its place in the
// names table, what the table says it cannot be (a base), its docstring and its __class_getitem__.
void present_native_class(ClassObject* c, const std::string& module) {
    std::string short_name = c->name;
    const Obj* own_module = c->attrs.find(N("__module__"));
    std::string says = own_module != nullptr && as_str(*own_module) != nullptr ? as_str(*own_module)->text : module;
    if (says != "builtins" && !cpython_has("shortname", says + "." + short_name)) {
        c->name = module + "." + short_name;     // tp_name: "module.Name" for a static type and a spec's; the bare name for a type of
        c->name_prefix = module.size() + 1;      // builtins (NoDefaultType) and one C made with type() (ast's nodes, io.UnsupportedOperation)
    }
    note_prelude_class(c);
    c->final_type = cpython_has("final", c->name);
    forget_python_origin(c);
    if (c->attrs.contains(N("__dict__")) && cpython_attribute_kind(c, "__dict__").empty())   // a managed dict without a __dict__ (typing.TypeVar)
        c->del_attr(N("__dict__"));
    present_methods(c);
    c->has_weakref = cpython_has("weakref", c->name);
    if (Obj doc = cpython_doc("type:" + c->name); doc != None())   // the type's own doc; an empty row says CPython has None
        c->set_attr(N("__doc__"), as_str(doc)->text.empty() ? None() : doc);
    if (cpython_has(c->name, "__class_getitem__") && !c->attrs.contains(N("__class_getitem__")))   // Py_GenericAlias, unless the class has its own
        method(c, "__class_getitem__", class_getitem, Binding::ClassMethod);
    // a C type whose + is sq_concat (and * sq_repeat) has __add__ and no __radd__ in CPython: the right operand's __radd__ goes first
    // (binary_op1 tries nb_add on both sides before concatenation); deque, Template (G13 #2)
    if (cpython_has(c->name, "__add__") && !cpython_has(c->name, "__radd__")) c->sequence_slots = true;
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

// Python/suggestions.c: levenshtein_distance and _Py_CalculateSuggestions, over the names' UTF-8
namespace {
constexpr std::size_t MAX_CANDIDATE_ITEMS = 750, MAX_STRING_SIZE = 40, MOVE_COST = 2, CASE_COST = 1;
std::size_t substitution_cost(char a, char b) {
    if ((a & 31) != (b & 31)) return MOVE_COST;  // not the same, not a case flip
    if (a == b) return 0;
    if ('A' <= a && a <= 'Z') a = static_cast<char>(a + ('a' - 'A'));
    if ('A' <= b && b <= 'Z') b = static_cast<char>(b + ('a' - 'A'));
    return a == b ? CASE_COST : MOVE_COST;
}
// max_cost + 1 for "more than max_cost", as the C answers when it gives up early
std::size_t levenshtein_distance(std::string_view a, std::string_view b, std::size_t max_cost) {
    while (!a.empty() && !b.empty() && a.front() == b.front()) {   // trim away common affixes
        a.remove_prefix(1);
        b.remove_prefix(1);
    }
    while (!a.empty() && !b.empty() && a.back() == b.back()) {
        a.remove_suffix(1);
        b.remove_suffix(1);
    }
    if (a.empty() || b.empty()) return (a.size() + b.size()) * MOVE_COST;
    if (a.size() > MAX_STRING_SIZE || b.size() > MAX_STRING_SIZE) return max_cost + 1;
    if (b.size() < a.size()) std::swap(a, b);    // prefer the shorter buffer
    if ((b.size() - a.size()) * MOVE_COST > max_cost) return max_cost + 1;
    std::size_t buffer[MAX_STRING_SIZE];
    std::size_t tmp = MOVE_COST;
    for (std::size_t i = 0; i < a.size(); ++i) {
        buffer[i] = tmp;
        tmp += MOVE_COST;
    }
    std::size_t result = 0;
    for (std::size_t b_index = 0; b_index < b.size(); ++b_index) {
        char code = b[b_index];
        std::size_t distance = result = b_index * MOVE_COST;
        std::size_t minimum = SIZE_MAX;
        for (std::size_t index = 0; index < a.size(); ++index) {
            std::size_t substitute = distance + substitution_cost(code, a[index]);
            distance = buffer[index];
            std::size_t insert_delete = std::min(result, distance) + MOVE_COST;
            result = std::min(insert_delete, substitute);
            buffer[index] = result;
            if (result < minimum) minimum = result;
        }
        if (minimum > max_cost) return max_cost + 1;   // everything in this row is too big
    }
    return result;
}
}  // namespace
std::string keyword_suggestion(const std::string& name, const std::vector<std::string>& known) {
    if (known.size() >= MAX_CANDIDATE_ITEMS) return "";
    std::string suggestion;
    bool found = false;
    std::size_t best = SIZE_MAX;                 // PY_SSIZE_T_MAX: no match beaten yet
    for (const std::string& it : known) {
        if (it == name) continue;
        // no more than 1/3 of the involved characters should need changed; don't take matches already beaten
        std::size_t max_distance = std::min((name.size() + it.size() + 3) * MOVE_COST / 6, best - 1);
        std::size_t current = levenshtein_distance(name, it, max_distance);
        if (current > max_distance) continue;
        if (!found || current < best) {
            suggestion = it;
            best = current;
            found = true;
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
    for (ClassObject* c : {t.list, t.str, t.bool_}) new_method(c, builtin_new_m);
    new_method(t.tuple, tuple_new_m);
    new_method(t.str, str_new_m);
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
    getset(t.type, "__annotations__", type_annotations, set_type_annotations);
    static_cast<GetSet*>(t.type->attrs.find(N("__annotations__"))->object())->deletable = true;
    getset(t.type, "__annotate__", type_annotate, set_type_annotate);
    static_cast<GetSet*>(t.type->attrs.find(N("__annotate__"))->object())->deletable = true;   // the setter refuses the delete itself
    getset(t.type, "__dict__", type_dict);
    getset(t.type, "__mro__", type_mro_attr);
    getset(t.type, "__bases__", type_bases, set_type_bases);
    getset(t.type, "__base__", type_base);
    for (auto [name, get] : std::initializer_list<std::pair<const char*, Ref (*)(Obj)>>{
             {"__flags__", type_flags}, {"__dictoffset__", type_dictoffset}, {"__weakrefoffset__", type_weakrefoffset}}) {
        auto* g = new GetSet(name, t.type, get, nullptr);
        g->cls = t.member_descriptor;
        t.type->attrs.set(N(name), Obj::of(g));
    }
    for (const char* n : {"__name__", "__qualname__", "__module__", "__doc__", "__bases__"})
        static_cast<GetSet*>(t.type->attrs.find(N(n))->object())->deletable = true;
    // descriptors' own __get__ (and a getset's __set__ and __delete__)
    for (ClassObject* c : {t.function, t.method_descriptor, t.classmethod_descriptor, t.wrapper_descriptor, t.getset_descriptor, t.member_descriptor}) method(c, "__get__", get_native);
    for (ClassObject* c : {t.method_descriptor, t.classmethod_descriptor, t.wrapper_descriptor, t.method_wrapper}) {   // descr_members, descr_getset, wrapper_getsets
        auto member = [&](const char* name, Ref (*get)(Obj)) {
            auto* g = new GetSet(name, c, get, nullptr);
            if (c != t.method_wrapper) g->cls = t.member_descriptor;
            c->attrs.set(N(name), Obj::of(g));
        };
        member("__name__", builtin_name);
        member("__objclass__", builtin_objclass);
        getset(c, "__qualname__", builtin_descr_qualname);
        if (c == t.method_descriptor || c == t.classmethod_descriptor) getset(c, "__doc__", builtin_doc);   // method_get_doc: the ml_doc
    }
    getset(t.method_wrapper, "__self__", builtin_self);
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
        c->attrs.set(N("__doc__"), Obj::of(new GetSet("__doc__", c, descriptor_doc, nullptr)));                // member_get_doc, getset_get_doc
    }
    // functions, methods, cells
    getset(t.function, "__name__", fn_name, set_fn_name);
    getset(t.function, "__qualname__", fn_qualname, set_fn_qualname);
    getset(t.function, "__doc__", fn_doc, set_fn_doc);
    getset(t.function, "__module__", fn_module, set_fn_module);
    static_cast<GetSet*>(t.function->attrs.find(N("__module__"))->object())->deletable = true;
    for (auto [name, get] : std::initializer_list<std::pair<const char*, Ref (*)(Obj)>>{{"__globals__", fn_globals}, {"__builtins__", fn_builtins}}) {
        auto* m = new GetSet(name, t.function, get, nullptr);
        m->cls = types().member_descriptor;
        t.function->attrs.set(N(name), Obj::of(m));
    }
    for (auto [name, get, set] : std::initializer_list<std::tuple<const char*, Ref (*)(Obj), void (*)(Obj, Obj)>>{
             {"__defaults__", fn_defaults, set_fn_defaults}, {"__kwdefaults__", fn_kwdefaults, set_fn_kwdefaults}}) {
        auto* g = new GetSet(name, t.function, get, set);
        g->deletable = true;
        t.function->attrs.set(N(name), Obj::of(g));
    }
    getset(t.function, "__type_params__", fn_type_params, set_fn_type_params);
    getset(t.function, "__code__", fn_code, set_fn_code);
    static_cast<GetSet*>(t.function->attrs.find(N("__code__"))->object())->deletable = true;   // the setter refuses the delete itself
    getset(t.function, "__closure__", fn_closure);
    for (auto [name, get] : std::initializer_list<std::pair<const char*, Ref (*)(Obj)>>{
             {"co_name", co_name}, {"co_qualname", co_qualname}, {"co_filename", co_filename}, {"co_firstlineno", co_firstlineno},
             {"co_argcount", co_argcount}, {"co_posonlyargcount", co_posonlyargcount}, {"co_kwonlyargcount", co_kwonlyargcount},
             {"co_nlocals", co_nlocals}, {"co_varnames", co_varnames}, {"co_cellvars", co_cellvars}, {"co_freevars", co_freevars},
             {"co_flags", co_flags}}) {
        auto* g = new GetSet(name, t.code, get, nullptr);     // members of the code object (code_memberlist)
        g->cls = t.member_descriptor;
        t.code->attrs.set(N(name), Obj::of(g));
    }
    static_cast<GetSet*>(t.function->attrs.find(N("__type_params__"))->object())->deletable = true;
    getset(t.function, "__annotate__", fn_annotate, set_fn_annotate);
    getset(t.function, "__annotations__", fn_annotations, set_fn_annotations);
    static_cast<GetSet*>(t.function->attrs.find(N("__annotations__"))->object())->deletable = true;
    static_cast<GetSet*>(t.function->attrs.find(N("__annotate__"))->object())->deletable = true;
    getset(t.function, "__dict__", fn_dict, set_fn_dict);
    // a delete reaches the setter, which says what it wants: func_set_name and func_set_qualname refuse a NULL as they
    // refuse what is no str, and PyObject_GenericSetDict says the dict cannot be deleted (case C-3-54)
    for (const char* name : {"__name__", "__qualname__", "__dict__", "__doc__"}) static_cast<GetSet*>(t.function->attrs.find(N(name))->object())->deletable = true;
    getset(t.method, "__func__", method_func);
    method(t.method, "__new__", method_new, Binding::Function);
    getset(t.method, "__self__", method_self);
    getset(t.method, "__doc__", method_doc);
    getset(t.builtin, "__name__", builtin_name);
    getset(t.builtin, "__self__", builtin_self);
    getset(t.builtin, "__qualname__", builtin_qualname);
    getset(t.builtin, "__doc__", builtin_doc);
    {
        auto* g = new GetSet("__module__", t.builtin, builtin_module, set_builtin_module);
        g->deletable = true;
        t.builtin->attrs.set(N("__module__"), Obj::of(g));
    }
    method(t.cell, "__new__", cell_new_m, Binding::Function);
    getset(t.cell, "cell_contents", cell_contents_get, cell_contents_set);
    static_cast<GetSet*>(t.cell->attrs.find(N("cell_contents"))->object())->deletable = true;   // del empties the cell
    // mappingproxy, slice
    method(t.mappingproxy, "__new__", proxy_new, Binding::Function);
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
    {
        auto* lineno = new GetSet("tb_lineno", t.traceback, traceback_lineno, nullptr);
        t.traceback->attrs.set(N("tb_lineno"), Obj::of(lineno));
        auto* next = new GetSet("tb_next", t.traceback, traceback_next, traceback_next_set);
        next->deletable = true;                  // so that a deletion reaches the setter's TypeError, not "not writable"
        t.traceback->attrs.set(N("tb_next"), Obj::of(next));
        ClassObject* os = os_error();
        method(os, "__new__", oserror_new, Binding::Function);
        method(os, "__init__", oserror_init_m);
        method(os, "__str__", oserror_str);
        method(os, "__reduce__", oserror_reduce);
        auto member = [](ClassObject* c, const char* name, Ref (*g)(Obj), void (*s)(Obj, Obj)) {
            auto* d = new GetSet(name, c, g, s);
            d->cls = types().member_descriptor;
            d->deletable = true;
            c->attrs.set(N(name), Obj::of(d));
        };
        member(os, "errno", member_get<F_ERRNO>, member_set<F_ERRNO>);
        member(os, "strerror", member_get<F_STRERROR>, member_set<F_STRERROR>);
        member(os, "filename", member_get<F_FILENAME>, member_set<F_FILENAME>);
        member(os, "filename2", member_get<F_FILENAME2>, member_set<F_FILENAME2>);
        deletable_getset(os, "characters_written", oserror_written_get, oserror_written_set);
        ClassObject* sy = exception_class("SyntaxError");
        method(sy, "__init__", syntax_error_init);
        method(sy, "__str__", syntax_error_str);
        member(sy, "msg", member_get<F_MSG>, member_set<F_MSG>);
        member(sy, "filename", member_get<F_FILENAME>, member_set<F_FILENAME>);
        member(sy, "lineno", member_get<F_LINENO>, member_set<F_LINENO>);
        member(sy, "offset", member_get<F_OFFSET>, member_set<F_OFFSET>);
        member(sy, "text", member_get<F_TEXT>, member_set<F_TEXT>);
        member(sy, "end_lineno", member_get<F_END_LINENO>, member_set<F_END_LINENO>);
        member(sy, "end_offset", member_get<F_END_OFFSET>, member_set<F_END_OFFSET>);
        member(sy, "print_file_and_line", member_get<F_PRINT>, member_set<F_PRINT>);
        member(sy, "_metadata", member_get<F_METADATA>, member_set<F_METADATA>);
        new_method(t.none, singleton_new<0>);
        new_method(t.notimplemented, singleton_new<1>);
        new_method(t.ellipsis, singleton_new<2>);
    }
    method(exception_class("StopIteration"), "__init__", stop_iteration_init);
    deletable_getset(exception_class("StopIteration"), "value", stop_iteration_value_get, stop_iteration_value_set);
    static_cast<GetSet*>(exception_class("StopIteration")->attrs.find(N("value"))->object())->cls = types().member_descriptor;
    method(base, "__str__", exception_str);
    method(base, "__repr__", exception_repr);
    method(base, "with_traceback", exception_with_traceback);
    method(base, "__reduce__", exception_reduce);
    method(base, "__setstate__", exception_setstate);
    method(exception_class("ImportError"), "__reduce__", import_error_reduce);
    method(exception_class("AttributeError"), "__reduce__", attribute_error_reduce);
    method(exception_class("AttributeError"), "__getstate__", attribute_error_getstate);
    method(base, "add_note", exception_add_note);
    method(exception_class("KeyError"), "__str__", key_error_str);
    {   // BaseExceptionGroup's slots, members and methods; ExceptionGroup a heap type over it and Exception
        ClassObject* beg = exception_class("BaseExceptionGroup");
        new_method(beg, beg_new);
        method(beg, "__init__", exception_init);    // BaseExceptionGroup_init: no keywords, then BaseException_init
        method(beg, "__str__", beg_str);
        method(beg, "__repr__", beg_repr);
        method(beg, "derive", beg_derive);
        method(beg, "split", beg_split);
        method(beg, "subgroup", beg_subgroup);
        method(beg, "__class_getitem__", class_getitem, Binding::ClassMethod);
        for (auto [name, get, doc] : std::initializer_list<std::tuple<const char*, Ref (*)(Obj), const char*>>{
                 {"message", beg_message_get, "exception message"}, {"exceptions", beg_exceptions_get, "nested exceptions"}}) {
            auto* m = new GetSet(name, beg, get, nullptr);   // PyMemberDef, Py_READONLY: "readonly attribute"
            m->cls = t.member_descriptor;
            m->doc = doc;
            beg->attrs.set(N(name), Obj::of(m));
        }
        // create_exception_group_class: PyErr_NewException("builtins.ExceptionGroup", (BaseExceptionGroup, Exception), NULL)
        Ref name = str_new("ExceptionGroup");
        Ref bases = tuple_new({Obj::of(beg), Obj::of(exception_class("Exception"))});
        Ref ns = dict_new();
        Ref module = str_new("builtins");
        dict_set(static_cast<Dict*>(ns.get().object()), Obj::of(N("__module__")), module.get());
        Ref made = invoke(Obj::of(t.type), {name.get(), bases.get(), ns.get()});
        made.get().object()->flags |= IMMORTAL;
        exception_group_slot() = static_cast<ClassObject*>(made.get().object());
        dict_set(builtins_module()->dict, Obj::of(N("BaseExceptionGroup")), Obj::of(beg));
        dict_set(builtins_module()->dict, Obj::of(N("ExceptionGroup")), made.get());
    }
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
