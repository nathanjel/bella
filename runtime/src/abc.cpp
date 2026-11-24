// _abc (Modules/_abc.c): what abc.ABCMeta calls.
//
// The registry and the two caches hold weak references to classes, as CPython's do (_add_to_weak_set: each with a callback,
// `_destroy`, that takes it out of its set when the class dies), so an ABC holds nothing of what it has registered or cached:
// the exit's collections see that. A look-up (_in_weak_set) asks with a weak reference to the object, which for a class is the
// one its bases' lists of subclasses hold in CPython, so its hash is the class's computed once and kept; each entry of that
// hash is then compared by its target's __eq__ (weakref_richcompare). For a class that is done here without making the
// reference; for anything else (an instance's __class__ may say anything) the reference is made as CPython makes it.
// COLLECTION_FLAGS are checked but have no reader until `match` is compiled (TODO.md).
#include <unordered_map>
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
        if (type_of(e.exc.get()) != exception_class("TypeError")) rethrow(e);
        Ref text = str_of(e.exc.get());
        raise_new("TypeError", "cannot use 'weakref.ReferenceType' as a set element (" + as_str(text.get())->text + ")");
    }
}

// PyWeakref_NewRef's type, weakref.ReferenceType: _weakref's (runtime/prelude/_weakref.py), from the namespace its prelude runs
// in, which no program reaches. CPython's type is there from the start; here the module is made for it if it was not, as the
// import system makes a built-in module (_imp.create_builtin), and an import of it later finds that one (D-30: sys.modules
// has it only then)
Obj reference_type() {
    static Obj type;
    if (type.is_unset()) {
        if (native_module_made("_weakref") == nullptr) {
            Obj name = Obj::of(N("_weakref"));
            i_bella_create_builtin(Obj{}, Args{&name, 1, nullptr, 0});
        }
        for (Module* h : hidden_modules())
            if (as_str(h->name.get())->text == "_weakref") type = dict_get(h->dict, Obj::of(N("ReferenceType")));
        if (!is_kind(type, Kind::Class)) throw NotImplemented("_abc's weak references without _weakref's type");
    }
    return type;
}

// weakref_hash of a class's basic reference: the class's hash the first time it is asked for, kept from then on (the reference
// lives as long as the class, held by its bases' lists of subclasses); one that raises is not kept
std::int64_t class_reference_hash(Obj cls) {
    static std::unordered_map<const Object*, std::int64_t> kept;
    if (auto it = kept.find(cls.object()); it != kept.end()) return it->second;
    std::int64_t hash = reference_hash(cls);
    kept.emplace(cls.object(), hash);
    return hash;
}

// A metaclass whose __hash__ and __eq__ are object's: hashing or comparing its classes runs no code of the program's. `type`
// cannot be changed; another is asked again when its version says it changed (a class's version moves with every change
// to it or its bases)
bool plain_metaclass(ClassObject* meta) {
    if (meta == types().type) return true;
    static const ClassObject* last = nullptr;
    static std::uint64_t last_version = 0;
    static bool last_plain = false;
    if (meta == last && meta->version == last_version) return last_plain;
    static const Str* const eq = N("__eq__");
    static const Str* const hash = N("__hash__");
    last_plain = type_lookup(meta, eq) == type_lookup(types().object, eq) && type_lookup(meta, hash) == type_lookup(types().object, hash);
    last = meta;
    last_version = meta->version;
    return last_plain;
}

bool in_weak_set(const Ref& set, Obj obj) {      // _in_weak_set
    if (set.get().is_unset()) return false;
    auto* s = static_cast<SetObject*>(set.get().object());
    if (s->used == 0 || !supports_weakrefs(obj)) return false;   // PyWeakref_NewRef's TypeError is "not in it"
    if (!is_kind(obj, Kind::Class)) {            // the object's basic reference if it has one, else a new one (PySet_Contains)
        Ref ref = invoke(reference_type(), {obj});
        return set_contains(s, ref.get());
    }
    // set_lookkey with the class's basic reference: weakref_richcompare of each entry of its hash, a dead entry equal only to itself.
    // A metaclass that keeps object's __hash__ and __eq__ runs nothing for either: its hash needs no keeping, and the class
    // itself compares equal (object_richcompare) with no call
    bool plain = plain_metaclass(type_of(obj));
    return set_contains_by(s, plain ? hash_of(obj) : class_reference_hash(obj), [obj, plain](Obj stored) {
        Object* target = weak_target(weak_record(stored.object()));
        if (target == nullptr) return false;
        if (plain && target == obj.object()) return true;
        Ref held = Ref::share(Obj::of(target));
        Ref r = compare(CmpOp::Eq, held.get(), obj);
        return truth(r.get());
    });
}

Ref destroy(Obj self, Args a) {                  // _destroy (METH_O, bound to a reference to its set): the dead reference out of it
    onearg(a, "_destroy");
    Object* set = weak_target(weak_record(self.object()));
    if (set == nullptr) return none_ref();
    Ref held = Ref::share(Obj::of(set));
    set_discard(static_cast<SetObject*>(set), a.pos(0));
    return none_ref();
}

void add_to_weak_set(Ref& set, Obj obj) {        // _add_to_weak_set: a reference with a callback, added as any key is (its hash)
    if (set.get().is_unset()) set = own(new SetObject(false));
    Ref held = Ref::share(set.get());
    Ref wr = invoke(reference_type(), {held.get()});                // PyWeakref_NewRef(set, NULL)
    Ref callback = own(new Builtin("_destroy", destroy, wr.get()));   // PyCFunction_NewEx(&_destroy_def, wr, NULL)
    Ref ref = invoke(reference_type(), {obj, callback.get()});
    callback = Ref{};
    set_add(held.get(), ref.get());
}

void clear_weak_set(const Ref& set) {            // PySet_Clear of a set made, which stays the set its references' callbacks name
    if (!set.get().is_unset()) set_clear(static_cast<SetObject*>(set.get().object()));
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
        if (!isinstance(e.exc.get(), exception_class("TypeError"))) rethrow(e);
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
        for (Ref key = for_next(it.get()); !is_end(key); key = next_after(key, it.get())) {
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

// subclasscheck_check_registry: the true answer found, else false. A frozenset copy: a check can register, a callback take
// an entry out; a reference whose class has gone is passed over
bool in_registry(AbcData* data, Obj subclass) {
    if (in_weak_set(data->registry, subclass)) return true;
    if (data->registry.get().is_unset()) return false;
    Ref registered = own(new SetObject(true));
    set_update(registered.get(), data->registry.get());
    const auto& table = static_cast<SetObject*>(registered.get().object())->table;
    for (std::size_t i = 0; i < table.size(); ++i) {
        if (table[i].key.is_unset()) continue;
        Object* target = weak_target(weak_record(table[i].key.object()));   // PyWeakref_GetRef
        if (target == nullptr) continue;
        Ref key = Ref::share(Obj::of(target));
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
        clear_weak_set(data->negative_cache);
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
    clear_weak_set(data_of(impl)->registry);
    return none_ref();
}

Ref a_reset_caches(Obj, Args a) {
    onearg(a, "_abc._reset_caches");
    Ref impl = get_impl(a.pos(0));
    clear_weak_set(data_of(impl)->cache);
    clear_weak_set(data_of(impl)->negative_cache);   // also the second cache
    return none_ref();
}

Ref a_get_dump(Obj, Args a) {
    onearg(a, "_abc._get_dump");
    Ref impl = get_impl(a.pos(0));
    AbcData* data = data_of(impl);
    Ref sets[3];
    int i = 0;
    for (const Ref* held : {&data->registry, &data->cache, &data->negative_cache}) {   // PySet_New of each: shallow copies
        sets[i] = own(new SetObject(false));
        if (!held->get().is_unset()) set_update(sets[i].get(), held->get());
        ++i;
    }
    return tuple_new({sets[0].get(), sets[1].get(), sets[2].get(), Obj::small(static_cast<std::int64_t>(data->negative_cache_version))});
}

Ref a_get_cache_token(Obj, Args a) {
    noargs(a, "_abc.get_cache_token");
    return Ref::steal(Obj::small(static_cast<std::int64_t>(invalidation_counter)));
}

}  // namespace

void fill_abc(Module* m) {
    destroyer(Kind::AbcData) = [](Object* o) { detail::free_object(static_cast<AbcData*>(o)); };
    detail::traverser(Kind::AbcData) = [](Object* o, std::vector<Object*>& out) {   // abc_data_traverse (its type is immortal)
        auto* d = static_cast<AbcData*>(o);
        detail::visit(d->registry.get(), out);
        detail::visit(d->cache.get(), out);
        detail::visit(d->negative_cache.get(), out);
    };
    detail::clearer(Kind::AbcData) = [](Object* o) {   // abc_data_clear
        auto* d = static_cast<AbcData*>(o);
        d->registry = Ref{};
        d->cache = Ref{};
        d->negative_cache = Ref{};
    };
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
