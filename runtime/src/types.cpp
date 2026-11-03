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
    auto* e = static_cast<Instance*>(exc.get().object());
    bella::setattr(e, N("name"), Obj::of(name));
    bella::setattr(e, N("obj"), obj);
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
    raise_attribute_error(Obj::of(cls), name, "type object '" + cls->name + "' has no attribute '" + name->text + "'");
}

void type_setattr(ClassObject* cls, const Str* name, Obj value) {
    ClassObject* meta = type_of(Obj::of(cls));
    Obj meta_attr = type_lookup(meta, name);
    if (!meta_attr.is_unset() && is_kind(meta_attr, Kind::GetSet)) {
        auto* g = static_cast<GetSet*>(meta_attr.object());
        if (g->set == nullptr)
            raise_new("AttributeError", std::string("attribute '") + g->name + "' of 'type' objects is not writable");
        g->set(Obj::of(cls), value);
        return;
    }
    if (immutable_type(cls))
        raise_new("TypeError", "cannot set '" + name->text + "' attribute of immutable type '" + cls->name + "'");
    cls->set_attr(name, value);                  // the new version before the old value dies (type_setattro)
}

void type_delattr(ClassObject* cls, const Str* name) {
    if (immutable_type(cls))
        raise_new("TypeError", "cannot delete '" + name->text + "' attribute of immutable type '" + cls->name + "'");
    if (!cls->attrs.contains(name))
        raise_attribute_error(Obj::of(cls), name, "type object '" + cls->name + "' has no attribute '" + name->text + "'");
    cls->del_attr(name);
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

Ref object_new(Obj, Args a) {
    if (a.npos < 1) raise_new("TypeError", "object.__new__(): not enough arguments");
    ClassObject* cls = as_class(a.pos(0));
    if (cls == nullptr) raise_new("TypeError", "object.__new__(X): X is not a type object (" + type_of(a.pos(0))->name + ")");
    if (!cls->heap_type && cls != types().object) {         // tp_new_wrapper's check, before the arguments'
        if (cpython_attribute_kind(cls, "__new__").empty()) refuse_construction(cls);
        raise_new("TypeError", "object.__new__(" + cls->name + ") is not safe, use " + cls->name + ".__new__()");
    }
    bool excess = a.npos > 1 || a.nkw > 0;
    if (excess) {
        if (type_lookup(cls, N("__new__")) != object_new_fn())
            raise_new("TypeError", "object.__new__() takes exactly one argument (the type to instantiate)");
        if (type_lookup(cls, N("__init__")) == object_init_fn()) raise_new("TypeError", cls->name + "() takes no arguments");
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
            raise_new("TypeError", cls->qualname + ".__init__() takes exactly one argument (the instance to initialize)");
    }
    return none_ref();
}
}  // namespace

Ref type_call(ClassObject* cls, Args a) {
    if (cls == types().type && a.npos == 1 && a.nkw == 0) return Ref::share(Obj::of(observed_type(a.pos(0))));
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
        if (!bc->heap_type && bc != types().object && !is_subclass(bc, exception_class("BaseException")))
            throw NotImplemented("subclassing the built-in type '" + bc->name + "'");
        bases.push_back(bc);
    }
    if (bases.empty()) bases.push_back(types().object);
    auto* ns = static_cast<Dict*>(ns_obj.object());
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
    if (meta == nullptr || !is_subclass(meta, types().type))
        raise_new("TypeError", "type.__new__(X): X is not a type object");
    if (a.npos == 2 && meta == types().type && a.nkw == 0) return Ref::share(Obj::of(type_of(a.pos(1))));
    if (a.npos != 4) raise_new("TypeError", "type.__new__() takes exactly 3 arguments (" + std::to_string(a.npos - 1) + " given)");
    if (meta != types().type) throw NotImplemented("metaclasses other than type (step 3a.2: super)");
    return type_new(meta, a.pos(1), a.pos(2), a.pos(3), Args{a.data + a.npos, 0, a.kwnames, a.nkw});
}
Ref type_init(Obj, Args) { return none_ref(); }
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
Ref object_setattr(Obj, Args a) {
    arity(a, "__setattr__", 3, 3);
    const Str* n = as_str(a.pos(1));
    if (n == nullptr) raise_new("TypeError", "attribute name must be string, not '" + type_of(a.pos(1))->name + "'");
    if (!is_kind(a.pos(0), Kind::Instance)) throw NotImplemented("object.__setattr__ on a C++ type's object");
    try {
        bella::setattr(static_cast<Instance*>(a.pos(0).object()), intern(n->text), a.pos(2));
    } catch (const bella::AttributeError&) {
        raise_attribute_error(a.pos(0), intern(n->text), "'" + type_of(a.pos(0))->name + "' object has no attribute '" + n->text + "'");
    }
    return none_ref();
}
Ref object_delattr(Obj, Args a) {
    arity(a, "__delattr__", 2, 2);
    const Str* n = as_str(a.pos(1));
    if (n == nullptr) raise_new("TypeError", "attribute name must be string, not '" + type_of(a.pos(1))->name + "'");
    delattr(a.pos(0), intern(n->text));
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
    if (!is_kind(self, Kind::Instance)) throw NotImplemented("__dict__ of a C++ type's object");
    return expose_dict(static_cast<Instance*>(self.object()));
}
void set_instance_dict(Obj self, Obj d) {
    if (d.is_unset()) {                          // del obj.__dict__: the dict is detached; the object starts afresh
        Ref fresh = dict_new();
        set_dict(static_cast<Instance*>(self.object()), static_cast<DictObject*>(fresh.get().object()));
        return;
    }
    if (!is_kind(d, Kind::Dict))
        raise_new("TypeError", "__dict__ must be set to a dictionary, not a '" + type_of(d)->name + "'");
    set_dict(static_cast<Instance*>(self.object()), static_cast<DictObject*>(d.object()));
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
void set_type_name(Obj self, Obj v) {
    ClassObject* c = self_class(self);
    if (immutable_type(c)) raise_new("TypeError", "cannot set '__name__' attribute of immutable type '" + c->name + "'");
    const Str* s = as_str(v);
    if (s == nullptr) raise_new("TypeError", "can only assign string to " + c->name + ".__name__, not '" + type_of(v)->name + "'");
    c->name = s->text;
}
Ref type_qualname(Obj self) { return str_new(self_class(self)->qualname); }
void set_type_qualname(Obj self, Obj v) {
    ClassObject* c = self_class(self);
    if (immutable_type(c)) raise_new("TypeError", "cannot set '__qualname__' attribute of immutable type '" + c->name + "'");
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
void set_type_module(Obj self, Obj v) { type_setattr(self_class(self), N("__module__"), v); }
Ref type_doc(Obj self) {
    ClassObject* c = self_class(self);
    if (const Obj* d = c->attrs.find(N("__doc__"))) return descr_get(*d, None(), self);
    return none_ref();
}
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
    if (a.npos < 1) raise_new("TypeError", "BaseException.__new__(): not enough arguments");
    ClassObject* cls = as_class(a.pos(0));
    if (cls == nullptr || !is_subclass(cls, exception_class("BaseException")))
        raise_new("TypeError", "BaseException.__new__(X): X is not a subtype of BaseException");
    auto* e = new_instance(cls);
    Ref r = own(e);
    std::vector<Obj> items;
    for (std::size_t i = 1; i < a.npos; ++i) {
        incref(a.pos(i));
        items.push_back(a.pos(i));
    }
    Ref args = tuple_steal(std::move(items));
    bella::setattr(e, N("args"), args.get());
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
    bella::setattr(static_cast<Instance*>(self.object()), N("args"), args.get());
    return none_ref();
}
Ref exception_str(Obj self, Args) {
    Ref args = getattr(self, N("args"));
    if (!is_kind(args.get(), Kind::Tuple)) return str_of(args.get());
    auto& items = static_cast<Tuple*>(args.get().object())->items;
    if (items.empty()) return str_new("");
    if (items.size() == 1) return str_of(items[0]);
    return repr_of(args.get());
}
Ref key_error_str(Obj self, Args a) {             // KeyError_str: one argument shows as its repr
    Ref args = getattr(self, N("args"));
    if (is_kind(args.get(), Kind::Tuple) && static_cast<Tuple*>(args.get().object())->items.size() == 1)
        return repr_of(static_cast<Tuple*>(args.get().object())->items[0]);
    return exception_str(self, a);
}
Ref exception_repr(Obj self, Args) {
    // BaseException_repr: Name(repr(arg)) for one argument, Name + repr(args) otherwise
    Ref args = getattr(self, N("args"));
    auto& items = static_cast<Tuple*>(args.get().object())->items;
    Ref inner = items.size() == 1 ? repr_of(items[0]) : repr_of(args.get());
    std::string text = as_str(inner.get())->text;
    return str_new(type_of(self)->name + (items.size() == 1 ? "(" + text + ")" : text));
}
Ref exception_with_traceback(Obj self, Args a) {
    arity(a, "with_traceback", 1, 1);
    bella::setattr(static_cast<Instance*>(self.object()), N("__traceback__"), a.pos(0));
    return Ref::share(self);
}
}  // namespace

// ---- namespaces ----
Obj cell_contents(const Ref& cell) { return static_cast<Cell*>(cell.get().object())->value; }

Ref mapping_get(Obj mapping, Obj key) {
    if (is_kind(mapping, Kind::Dict)) {
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
void mapping_set(Obj mapping, Obj key, Obj value) {
    if (is_kind(mapping, Kind::Dict)) dict_set(static_cast<Dict*>(mapping.object()), key, value);
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
    method(t.type, "__prepare__", type_prepare, Binding::ClassMethod);
    method(t.type, "mro", type_mro);
    method(t.type, "__repr__", type_repr);
    getset(t.type, "__name__", type_name, set_type_name);
    getset(t.type, "__qualname__", type_qualname, set_type_qualname);
    getset(t.type, "__module__", type_module, set_type_module);
    getset(t.type, "__doc__", type_doc);
    getset(t.type, "__dict__", type_dict);
    getset(t.type, "__mro__", type_mro_attr);
    getset(t.type, "__bases__", type_bases);
    getset(t.type, "__base__", type_base);
    getset(t.type, "__flags__", type_flags);
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
    for (const char* n : {"__cause__", "__context__", "__traceback__"}) value(base, n, None());
    base->attrs.set(N("__dict__"), Obj::of(instance_dict_getset()));
    value(base, "__suppress_context__", boolean(false));
    for (const char* n : {"name", "obj"}) value(exception_class("AttributeError"), n, None());
    value(exception_class("NameError"), "name", None());
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
