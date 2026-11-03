// super objects, as Objects/typeobject.c (3.15.2) makes them: super(type, obj) looks a name up in
// the MRO of obj's type, after `type`, and binds what it finds with obj (none when obj is that
// type: a class) and obj's type (super_getattro, _PySuper_LookupDescr, do_super_lookup).
#include "bella/runtime.hpp"

namespace bella {

SuperObject::SuperObject() : Object(Kind::Super) { cls = types().super_; }

namespace {
SuperObject* su_of(Obj v) { return static_cast<SuperObject*>(v.object()); }
const char* name_or_null(Obj cls) { return cls.is_unset() ? "NULL" : static_cast<ClassObject*>(cls.object())->name.c_str(); }

// supercheck: obj a class that is a subtype of type (a classmethod's super: the class itself), an
// instance of type (its type), or an object whose __class__ is a subtype of type (a proxy)
Obj supercheck(ClassObject* type, Obj obj) {
    if (is_kind(obj, Kind::Class) && is_subclass(static_cast<ClassObject*>(obj.object()), type)) return obj;
    if (is_subclass(type_of(obj), type)) return Obj::of(type_of(obj));
    Ref class_attr;
    try {
        class_attr = getattr(obj, intern("__class__"));
    } catch (const PyError& e) {
        if (!isinstance(e.exc.get(), exception_class("AttributeError"))) throw;
    }
    if (is_kind(class_attr.get(), Kind::Class) && class_attr.get() != Obj::of(type_of(obj)) &&
        is_subclass(static_cast<ClassObject*>(class_attr.get().object()), type))
        return class_attr.get();             // held by the class's own count while the super lives
    bool is_type = is_kind(obj, Kind::Class);
    raise_new("TypeError", std::string("super(type, obj): obj (") + (is_type ? "type " : "instance of ") +
                               (is_type ? static_cast<ClassObject*>(obj.object())->name : type_of(obj)->name) +
                               ") is not an instance or subtype of type (" + type->name + ").");
}

// super_init_impl with a type: obj None is NULL; checked, then the three fields set
void init_fields(SuperObject* su, Obj type, Obj obj) {
    if (obj == None()) obj = Obj{};
    Obj obj_type;
    if (!obj.is_unset()) obj_type = supercheck(static_cast<ClassObject*>(type.object()), obj);
    for (auto [field, v] : {std::pair{&su->type, type}, std::pair{&su->obj, obj}, std::pair{&su->obj_type, obj_type}}) {
        incref(v);
        decref(std::exchange(*field, v));
    }
}

Ref make_super(Obj type, Obj obj) {
    Ref su = own(new SuperObject());
    init_fields(su_of(su.get()), type, obj);
    return su;
}

// super.__new__: an empty super (PyType_GenericNew takes any arguments)
Ref super_new_m(Obj, Args a) {
    if (a.npos < 1 || !is_kind(a.pos(0), Kind::Class) || a.pos(0).object() != types().super_)
        throw NotImplemented("super.__new__ for a class other than super");
    return own(new SuperObject());
}
// super.__init__ called on its own (Argument Clinic's checks, worded as super_init's)
Ref super_init_m(Obj self, Args a) {
    if (a.nkw != 0) raise_new("TypeError", "super() takes no keyword arguments");
    if (a.npos > 2) raise_new("TypeError", "super() takes at most 2 arguments (" + std::to_string(a.npos) + " given)");
    if (a.npos == 0) throw NotImplemented("super() without arguments outside a call the compiler sees (it reads the calling frame)");
    if (!is_kind(a.pos(0), Kind::Class)) raise_new("TypeError", "super() argument 1 must be type, not " + type_of(a.pos(0))->name);
    init_fields(su_of(self), a.pos(0), a.npos > 1 ? a.pos(1) : Obj{});
    return none_ref();
}
Ref super_repr_m(Obj self, Args) {
    SuperObject* su = su_of(self);
    if (!su->obj_type.is_unset())
        return str_new(std::string("<super: <class '") + name_or_null(su->type) + "'>, <" + name_or_null(su->obj_type) + " object>>");
    return str_new(std::string("<super: <class '") + name_or_null(su->type) + "'>, NULL>");
}
// super_descr_get: an unbound super is bound to obj; anything else is itself
Ref super_get_m(Obj self, Args a) {
    if (a.npos < 1 || a.npos > 2) raise_new("TypeError", "expected 1 or 2 arguments, got " + std::to_string(a.npos));
    SuperObject* su = su_of(self);
    Obj obj = a.pos(0);
    if (obj == None() || !su->obj.is_unset()) return Ref::share(self);
    return make_super(su->type, obj);
}
Ref field_or_none(Obj v) { return v.is_unset() ? none_ref() : Ref::share(v); }
Ref super_thisclass(Obj self) { return field_or_none(su_of(self)->type); }
Ref super_self(Obj self) { return field_or_none(su_of(self)->obj); }
Ref super_self_class(Obj self) { return field_or_none(su_of(self)->obj_type); }
void readonly(Obj, Obj) { raise_new("AttributeError", "readonly attribute"); }
}  // namespace

// super(...) (super_vectorcall): no keywords, at most two arguments, the first a type
Ref super_call(Args a) {
    if (a.nkw != 0) raise_new("TypeError", "super() takes no keyword arguments");
    if (a.npos > 2) raise_new("TypeError", "super() expected at most 2 arguments, got " + std::to_string(a.npos));
    if (a.npos == 0) throw NotImplemented("super() without arguments outside a call the compiler sees (it reads the calling frame)");
    if (!is_kind(a.pos(0), Kind::Class)) raise_new("TypeError", "super() argument 1 must be a type, not " + type_of(a.pos(0))->name);
    return make_super(a.pos(0), a.npos > 1 ? a.pos(1) : Obj{});
}

// super() with no arguments in a function (super_init_without_args): the frontend hands over the
// `super` the function sees, its __class__ cell and its first argument (or `missing`); a `super`
// that is not the builtin is called with no arguments (eval1's zero_arg_super)
Ref zero_argument_super(Obj super_name, Obj class_cell, Obj first) {
    if (super_name != Obj::of(types().super_)) return invoke(super_name, {});
    Ref missing = builtin("missing");
    if (first == missing.get()) raise_new("RuntimeError", "super(): no arguments");
    if (class_cell == missing.get() || !is_kind(class_cell, Kind::Cell)) raise_new("RuntimeError", "super(): __class__ cell not found");
    Obj cls = static_cast<Cell*>(class_cell.object())->value;
    if (cls.is_unset()) raise_new("RuntimeError", "super(): empty __class__ cell");
    if (!is_kind(cls, Kind::Class)) raise_new("RuntimeError", "super(): __class__ is not a type (" + type_of(cls)->name + ")");
    return make_super(cls, first);
}

// super_getattro: __class__ is the super object's own; any other name is looked up in the MRO of
// __self_class__ after __thisclass__, in each class's own dict, and bound; if none has it, or the
// super is unbound, the super object's own attributes
Ref super_getattr(Obj self, const Str* name) {
    SuperObject* su = su_of(self);
    if (name == intern("__class__") || su->obj_type.is_unset()) return generic_getattr(self, name);
    Ref start = Ref::share(su->obj_type), obj = Ref::share(su->obj), thisclass = Ref::share(su->type);
    auto* type = static_cast<ClassObject*>(start.get().object());
    std::vector<ClassObject*> mro = type->mro;          // kept: a lookup may replace the class's MRO
    std::size_t i = 0;
    while (i + 1 < mro.size() && Obj::of(mro[i]) != thisclass.get()) ++i;
    for (++i; i < mro.size(); ++i) {
        if (const Obj* found = mro[i]->attrs.find(name)) {
            Ref res = Ref::share(*found);
            // only an instance-mode super passes its object (SF #743627)
            return descr_get(res.get(), obj.get() == start.get() ? None() : obj.get(), start.get());
        }
    }
    return generic_getattr(self, name);
}

void init_super() {
    ClassObject* c = types().super_;
    auto add = [c](const char* name, NativeFn fn, Binding b = Binding::Method) {
        auto* f = new Builtin(name, fn, Obj{}, b);
        f->owner = c;
        f->flags |= IMMORTAL;
        c->attrs.set(intern(name), Obj::of(f));
    };
    add("__new__", super_new_m, Binding::Function);
    add("__init__", super_init_m);
    add("__repr__", super_repr_m);
    add("__get__", super_get_m);
    for (auto [name, get] : std::initializer_list<std::pair<const char*, Ref (*)(Obj)>>{
             {"__thisclass__", super_thisclass}, {"__self__", super_self}, {"__self_class__", super_self_class}}) {
        auto* g = new GetSet(name, c, get, readonly);
        g->deletable = true;
        c->attrs.set(intern(name), Obj::of(g));
    }
}

}  // namespace bella
