// _abc (Modules/_abc.c): what abc.ABCMeta calls.
//
// CPython's three sets hold weak references to classes; here they hold the classes, until step 3c
// (confirmed by the author, 2026-11-04). No class dies before the collector exists, so what a
// program can see differs only where a reference itself would show: _get_dump refuses a set with
// entries, and a metaclass's __hash__ runs at each look-up where CPython's reference keeps the first
// answer. COLLECTION_FLAGS are checked but have no reader until `match` is compiled (TODO.md).
#include <utility>

#include "bella/runtime.hpp"

namespace bella {
namespace {

const Str* N(const char* s) { return intern(s); }

struct AbcData : Object {                        // _abc_data: a set is made at its first entry
    Ref registry;
    Ref cache;
    Ref negative_cache;
    std::uint64_t negative_cache_version;
    AbcData(ClassObject* c, std::uint64_t version) : Object(Kind::AbcData), negative_cache_version(version) { cls = c; }
};

std::uint64_t invalidation_counter = 0;          // abc_invalidation_counter

ClassObject*& abc_data_type() {
    static ClassObject* c = nullptr;
    return c;
}

Ref abc_data_new(Obj self, Args a) {             // takes and ignores any other arguments
    ClassObject* cls = new_wrapper_class(a, static_cast<ClassObject*>(self.object()));
    return own(new AbcData(cls, invalidation_counter));
}

Ref get_impl(Obj self) {                         // _get_impl
    Ref impl = getattr(self, N("_abc_impl"));
    if (type_of(impl.get()) != abc_data_type()) raise_new("TypeError", "_abc_impl is set to a wrong type");
    return impl;
}
AbcData* data_of(const Ref& impl) { return static_cast<AbcData*>(impl.get().object()); }

// tp_weaklistoffset: what PyWeakref_NewRef takes. A class whose every base declares __slots__ has
// no room for one; __weakref__ in __slots__ is refused until step 3c.
bool supports_weakrefs(Obj v) {
    if (!v.is_object()) return false;
    switch (v.object()->kind) {
        case Kind::Class: case Kind::PyFunction: case Kind::Builtin: case Kind::Method: case Kind::Module: case Kind::Set:
            return true;
        default:
            break;
    }
    for (const ClassObject* c : type_of(v)->mro)
        if (c->heap_type && !c->slots) return true;
    return false;
}

// hash(weakref.ref(c)) is c's, and a set of references words an unhashable one after the reference
std::int64_t reference_hash(Obj obj) {
    try {
        return hash_of(obj);
    } catch (const PyError& e) {
        if (type_of(e.exc.get()) != exception_class("TypeError")) throw;
        Ref text = str_of(e.exc.get());
        raise_new("TypeError", "cannot use 'weakref.ReferenceType' as a set element (" + as_str(text.get())->text + ")");
    }
}

bool in_weak_set(const Ref& set, Obj obj) {      // _in_weak_set
    if (set.get().is_unset()) return false;
    auto* s = static_cast<SetObject*>(set.get().object());
    if (s->used == 0 || !supports_weakrefs(obj)) return false;   // PyWeakref_NewRef's TypeError is "not in it"
    return set_contains_hashed(s, obj, reference_hash(obj));
}

void add_to_weak_set(Ref& set, Obj obj) {        // _add_to_weak_set: only ever a class, which any reference can name
    std::int64_t hash = reference_hash(obj);
    if (set.get().is_unset()) set = own(new SetObject(false));
    set_add_hashed(set.get(), obj, hash);
}

bool is_abstract(Obj value) {                    // _PyObject_IsAbstract
    Ref v = optional_getattr(value, N("__isabstractmethod__"));
    return !v.get().is_unset() && truth(v.get());
}

Ref call_method(Obj self, const char* name, std::initializer_list<Obj> args) {   // PyObject_CallMethod*
    Ref bound = getattr(self, N(name));
    return invoke(bound.get(), args);
}

Ref mapping_items(Obj ns) {                      // PyMapping_Items, method_output_as_list
    Ref out = call_method(ns, "items", {});
    Ref it;
    try {
        it = iter(out.get());
    } catch (const PyError& e) {
        if (!isinstance(e.exc.get(), exception_class("TypeError"))) throw;
        raise_new("TypeError", type_of(ns)->name + ".items() must return an iterable, not " + type_of(out.get())->name);
    }
    Ref items = list_new({});
    list_extend(items.get(), it.get());
    return items;
}

std::vector<Obj>& sequence_items(const Ref& seq) {
    return is_kind(seq.get(), Kind::List) ? static_cast<List*>(seq.get().object())->items : static_cast<Tuple*>(seq.get().object())->items;
}

void compute_abstract_methods(Obj self) {
    Ref abstracts = own(new SetObject(true));
    // Stage 1: direct abstract methods; a list, as __isabstractmethod__ can change the namespace
    Ref ns = getattr(self, N("__dict__"));
    Ref items = mapping_items(ns.get());
    for (std::size_t pos = 0; pos < sequence_items(items).size(); ++pos) {
        Ref it = sequence_fast(sequence_items(items)[pos], "items() returned non-iterable");
        if (sequence_items(it).size() != 2) raise_new("TypeError", "items() returned item which size is not 2");
        Ref key = Ref::share(sequence_items(it)[0]);
        if (is_abstract(sequence_items(it)[1])) set_add(abstracts.get(), key.get());
    }
    // Stage 2: inherited abstract methods, those still abstract here
    Ref bases = getattr(self, N("__bases__"));
    if (!is_kind(bases.get(), Kind::Tuple)) raise_new("TypeError", "__bases__ is not tuple");
    for (std::size_t pos = 0; pos < sequence_items(bases).size(); ++pos) {
        Ref base_abstracts = optional_getattr(sequence_items(bases)[pos], N("__abstractmethods__"));
        if (base_abstracts.get().is_unset()) continue;
        Ref it = iter(base_abstracts.get());
        for (Ref key = for_next(it.get()); !is_end(key); key = for_next(it.get())) {
            const Str* name = as_str(key.get());
            if (name == nullptr) raise_new("TypeError", "attribute name must be string, not '" + type_of(key.get())->name + "'");
            Ref value = optional_getattr(self, intern(name->text));
            if (value.get().is_unset()) continue;
            if (is_abstract(value.get())) set_add(abstracts.get(), key.get());
        }
    }
    setattr(self, N("__abstractmethods__"), abstracts.get());
}

Ref a_abc_init(Obj, Args a) {
    onearg(a, "_abc._abc_init");
    Obj self = a.pos(0);
    compute_abstract_methods(self);
    Ref data = own(new AbcData(abc_data_type(), invalidation_counter));
    setattr(self, N("_abc_impl"), data.get());
    // __abc_tpflags__: taken from the class's own dict; the bits say how `match` treats the class
    if (is_kind(self, Kind::Class)) {
        auto* c = static_cast<ClassObject*>(self.object());
        const Obj* found = c->attrs.find(N("__abc_tpflags__"));
        if (found == nullptr) return none_ref();
        Ref flags = Ref::share(*found);
        c->del_attr(N("__abc_tpflags__"));
        constexpr std::int64_t SEQUENCE = 1 << 5, MAPPING = 1 << 6;
        if (flags.get().is_small() && (flags.get().small_value() & (SEQUENCE | MAPPING)) == (SEQUENCE | MAPPING))
            raise_new("TypeError", "__abc_tpflags__ cannot be both Py_TPFLAGS_SEQUENCE and Py_TPFLAGS_MAPPING");
        if (flags.get().is_small()) c->collection_flags |= static_cast<std::uint8_t>(flags.get().small_value() & (SEQUENCE | MAPPING));
    }
    return none_ref();
}

Ref a_abc_register(Obj, Args a) {
    clinic(a, "_abc_register", "_abc._abc_register", 2, 2);
    Obj self = a.pos(0);
    Obj subclass = a.pos(1);
    if (!is_kind(subclass, Kind::Class)) raise_new("TypeError", "Can only register classes");
    if (object_issubclass(subclass, self)) return Ref::share(subclass);   // already a subclass
    // Subtle: test for cycles *after* testing for "already a subclass", so X.register(X) is a no-op
    if (object_issubclass(self, subclass)) raise_new("RuntimeError", "Refusing to create an inheritance cycle");
    Ref impl = get_impl(self);
    add_to_weak_set(data_of(impl)->registry, subclass);
    ++invalidation_counter;                      // the negative caches are out of date
    if (is_kind(self, Kind::Class))              // Set Py_TPFLAGS_SEQUENCE or Py_TPFLAGS_MAPPING flag
        if (std::uint8_t flag = collection_flags_of(static_cast<ClassObject*>(self.object())); flag != 0)
            set_collection_flag_recursive(static_cast<ClassObject*>(subclass.object()), flag);
    return Ref::share(subclass);
}

Ref a_abc_instancecheck(Obj, Args a) {
    clinic(a, "_abc_instancecheck", "_abc._abc_instancecheck", 2, 2);
    Obj self = a.pos(0);
    Obj instance = a.pos(1);
    Ref impl = get_impl(self);
    Ref subclass = optional_getattr(instance, N("__class__"));
    if (subclass.get().is_unset()) subclass = Ref::share(Obj::of(type_of(instance)));   // gh-153772: as isinstance()
    if (in_weak_set(data_of(impl)->cache, subclass.get())) return Ref::steal(boolean(true));
    Obj subtype = Obj::of(type_of(instance));
    if (subtype == subclass.get()) {
        if (data_of(impl)->negative_cache_version == invalidation_counter &&
            in_weak_set(data_of(impl)->negative_cache, subclass.get()))
            return Ref::steal(boolean(false));
        return call_method(self, "__subclasscheck__", {subclass.get()});
    }
    // a subclass check can change the instance's actual type
    Ref held = Ref::share(subtype);
    Ref result = call_method(self, "__subclasscheck__", {subclass.get()});
    if (truth(result.get())) return result;
    return call_method(self, "__subclasscheck__", {held.get()});
}

bool is_subtype(Obj derived, Obj base) {         // PyType_IsSubtype: pointers along derived's MRO
    for (const ClassObject* c : static_cast<ClassObject*>(derived.object())->mro)
        if (Obj::of(const_cast<ClassObject*>(c)) == base) return true;
    return false;
}

// subclasscheck_check_registry: the true answer found, else false. A copy: a check can register.
bool in_registry(AbcData* data, Obj subclass) {
    if (in_weak_set(data->registry, subclass)) return true;
    if (data->registry.get().is_unset()) return false;
    std::vector<Ref> registered;
    for (const auto& e : static_cast<SetObject*>(data->registry.get().object())->table)
        if (!e.key.is_unset()) registered.push_back(Ref::share(e.key));
    for (const Ref& key : registered) {
        if (object_issubclass(subclass, key.get())) {
            add_to_weak_set(data->cache, subclass);
            return true;
        }
    }
    return false;
}

Ref a_abc_subclasscheck(Obj, Args a) {
    clinic(a, "_abc_subclasscheck", "_abc._abc_subclasscheck", 2, 2);
    Obj self = a.pos(0);
    Obj subclass = a.pos(1);
    if (!is_kind(subclass, Kind::Class)) raise_new("TypeError", "issubclass() arg 1 must be a class");
    Ref impl = get_impl(self);
    AbcData* data = data_of(impl);
    // 1. the cache
    if (in_weak_set(data->cache, subclass)) return Ref::steal(boolean(true));
    // 2. the negative cache; it may have to be forgotten
    if (data->negative_cache_version < invalidation_counter) {
        data->negative_cache = Ref{};
        data->negative_cache_version = invalidation_counter;
    } else if (in_weak_set(data->negative_cache, subclass)) {
        return Ref::steal(boolean(false));
    }
    // 3. the hook
    Ref ok = call_method(self, "__subclasshook__", {subclass});
    if (ok.get() == boolean(true)) {
        add_to_weak_set(data->cache, subclass);
        return Ref::steal(boolean(true));
    }
    if (ok.get() == boolean(false)) {
        add_to_weak_set(data->negative_cache, subclass);
        return Ref::steal(boolean(false));
    }
    if (ok.get() != Obj::of(NOTIMPLEMENTED))
        raise_new("AssertionError", "__subclasshook__ must return either False, True, or NotImplemented");
    // 4. a direct subclass
    if (is_subtype(subclass, self)) {
        add_to_weak_set(data->cache, subclass);
        return Ref::steal(boolean(true));
    }
    // 5. a subclass of a registered class
    if (in_registry(data, subclass)) return Ref::steal(boolean(true));
    // 6. a subclass of a subclass
    Ref subclasses = call_method(self, "__subclasses__", {});
    if (!is_kind(subclasses.get(), Kind::List)) raise_new("TypeError", "__subclasses__() must return a list");
    for (std::size_t pos = 0; pos < sequence_items(subclasses).size(); ++pos) {
        Ref scls = Ref::share(sequence_items(subclasses)[pos]);
        if (object_issubclass(subclass, scls.get())) {
            add_to_weak_set(data->cache, subclass);
            return Ref::steal(boolean(true));
        }
    }
    add_to_weak_set(data->negative_cache, subclass);
    return Ref::steal(boolean(false));
}

Ref a_reset_registry(Obj, Args a) {
    onearg(a, "_abc._reset_registry");
    Ref impl = get_impl(a.pos(0));
    data_of(impl)->registry = Ref{};
    return none_ref();
}

Ref a_reset_caches(Obj, Args a) {
    onearg(a, "_abc._reset_caches");
    Ref impl = get_impl(a.pos(0));
    data_of(impl)->cache = Ref{};
    data_of(impl)->negative_cache = Ref{};
    return none_ref();
}

Ref a_get_dump(Obj, Args a) {
    onearg(a, "_abc._get_dump");
    Ref impl = get_impl(a.pos(0));
    AbcData* data = data_of(impl);
    Ref sets[3];
    int i = 0;
    for (const Ref* held : {&data->registry, &data->cache, &data->negative_cache}) {
        if (!held->get().is_unset() && static_cast<SetObject*>(held->get().object())->used != 0)
            throw NotImplemented("_abc._get_dump of a set with entries: they are weak references (step 3c)");
        sets[i++] = own(new SetObject(false));
    }
    return tuple_new({sets[0].get(), sets[1].get(), sets[2].get(), Obj::small(static_cast<std::int64_t>(data->negative_cache_version))});
}

Ref a_get_cache_token(Obj, Args a) {
    noargs(a, "_abc.get_cache_token");
    return Ref::steal(Obj::small(static_cast<std::int64_t>(invalidation_counter)));
}

}  // namespace

void fill_abc(Module* m) {
    destroyer(Kind::AbcData) = [](Object* o) { delete static_cast<AbcData*>(o); };
    ClassObject* c = builtin_type("_abc._abc_data", {types().object});
    c->heap_type = true;                         // PyType_FromModuleAndSpec: a program can set its attributes
    c->name_prefix = 5;
    c->qualname = "_abc_data";
    c->attrs.set(N("__module__"), Obj::of(intern("_abc")));
    c->attrs.set(N("__doc__"), Obj::of(intern("Internal state held by ABC machinery.")));
    auto* make = new Builtin("__new__", abc_data_new, Obj::of(c), Binding::Function);
    make->owner = c;
    make->flags |= IMMORTAL;
    c->attrs.set(N("__new__"), Obj::of(make));
    abc_data_type() = c;
    Dict* d = m->dict;
    dict_set(d, Obj::of(N("__doc__")), Obj::of(intern("Module contains faster C implementation of abc.ABCMeta")));
    for (auto [name, fn] : std::initializer_list<std::pair<const char*, NativeFn>>{
             {"get_cache_token", a_get_cache_token}, {"_abc_init", a_abc_init}, {"_reset_registry", a_reset_registry},
             {"_reset_caches", a_reset_caches}, {"_get_dump", a_get_dump}, {"_abc_register", a_abc_register},
             {"_abc_instancecheck", a_abc_instancecheck}, {"_abc_subclasscheck", a_abc_subclasscheck}}) {
        Ref f = own(new Builtin(name, fn));
        dict_set(d, Obj::of(N(name)), f.get());
    }
}

}  // namespace bella
