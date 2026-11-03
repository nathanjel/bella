// runtime/src/set.cpp -- set and frozenset: CPython 3.15.2's table (Objects/setobject.c), so that
// iteration order and the __eq__ calls a lookup makes are CPython's (spec D-05).
#include "bella/runtime.hpp"

namespace bella {

namespace {
constexpr std::size_t MINSIZE = 8;
constexpr int LINEAR_PROBES = 9;
constexpr int PERTURB_SHIFT = 5;

bool active(const SetObject::Entry& e) { return !e.key.is_unset(); }
bool dummy(const SetObject::Entry& e) { return e.key.is_unset() && e.hash == -1; }
bool empty(const SetObject::Entry& e) { return e.key.is_unset() && e.hash == 0; }

// set_insert_clean: a key known absent, into a table without dummies
void insert_clean(std::vector<SetObject::Entry>& table, Obj key, std::int64_t hash) {
    std::size_t mask = table.size() - 1;
    auto perturb = static_cast<std::size_t>(hash);
    std::size_t i = static_cast<std::size_t>(hash) & mask;
    for (;;) {
        if (empty(table[i])) { table[i] = {key, hash}; return; }
        if (i + LINEAR_PROBES <= mask)
            for (int j = 1; j <= LINEAR_PROBES; ++j)
                if (empty(table[i + j])) { table[i + j] = {key, hash}; return; }
        perturb >>= PERTURB_SHIFT;
        i = (i * 5 + 1 + perturb) & mask;
    }
}

void resize(SetObject* s, std::size_t minused) {
    std::size_t newsize = MINSIZE;
    while (newsize <= minused) newsize <<= 1;
    std::vector<SetObject::Entry> old = std::move(s->table);
    s->table.assign(newsize, SetObject::Entry{});
    s->fill = s->used;
    for (auto& e : old)
        if (active(e)) insert_clean(s->table, e.key, e.hash);
}

// keys equal as set_add_entry and set_lookkey compare them; nullopt when the table changed under
// the comparison (restart)
bool equal(Obj stored, Obj key) {
    if (stored == key) return true;
    const Str* a = as_str(stored);
    const Str* b = as_str(key);
    if (a != nullptr && b != nullptr && type_of(stored) == types().str && type_of(key) == types().str)
        return a->text == b->text;
    Ref hold = Ref::share(stored);
    Ref r = compare(CmpOp::Eq, stored, key);
    return truth(r.get());
}

// the entry holding key, or the end of the table
std::size_t lookkey(SetObject* s, Obj key, std::int64_t hash) {
restart:
    std::size_t mask = s->table.size() - 1;
    std::size_t i = static_cast<std::size_t>(hash) & mask;
    auto perturb = static_cast<std::size_t>(hash);
    for (;;) {
        int probes = (i + LINEAR_PROBES <= mask) ? LINEAR_PROBES : 0;
        for (std::size_t k = i;; ++k) {
            auto& e = s->table[k];
            if (empty(e)) return s->table.size();
            if (active(e) && e.hash == hash) {
                Obj startkey = e.key;
                std::size_t size = s->table.size();
                bool eq = equal(startkey, key);
                if (s->table.size() != size || s->table[k].key != startkey) goto restart;
                if (eq) return k;
            }
            if (probes-- == 0) break;
        }
        perturb >>= PERTURB_SHIFT;
        i = (i * 5 + 1 + perturb) & mask;
    }
}
}  // namespace

SetObject::SetObject(bool frozen_set) : Object(Kind::Set), table(MINSIZE), frozen(frozen_set) {
    cls = frozen ? types().frozenset : types().set;
}

void set_add(Obj setv, Obj key) { set_add_hashed(setv, key, set_key_hash(key)); }

// set_add_entry. The table takes its count of the key only when it stores it: a comparison that
// raises leaves nothing behind (review 2026-11-03, A9-8); the caller holds the key meanwhile.
void set_add_hashed(Obj setv, Obj key, std::int64_t hash) {
    auto* s = static_cast<SetObject*>(setv.object());
restart:
    std::size_t mask = s->table.size() - 1;
    std::size_t i = static_cast<std::size_t>(hash) & mask;
    std::size_t freeslot = SIZE_MAX;
    auto perturb = static_cast<std::size_t>(hash);
    for (;;) {
        int probes = (i + LINEAR_PROBES <= mask) ? LINEAR_PROBES : 0;
        for (std::size_t k = i;; ++k) {
            auto& e = s->table[k];
            if (empty(e)) {
                incref(key);
                if (freeslot != SIZE_MAX) {
                    ++s->used;
                    s->table[freeslot] = {key, hash};
                    return;
                }
                ++s->fill;
                ++s->used;
                e = {key, hash};
                if (s->fill * 5 < mask * 3) return;
                resize(s, s->used > 50000 ? s->used * 2 : s->used * 4);
                return;
            }
            if (active(e) && e.hash == hash) {
                Obj startkey = e.key;
                std::size_t size = s->table.size();
                bool eq = equal(startkey, key);
                if (eq) return;
                if (s->table.size() != size || s->table[k].key != startkey) goto restart;
            } else if (dummy(e) && freeslot == SIZE_MAX) {
                freeslot = k;
            }
            if (probes-- == 0) break;
        }
        perturb >>= PERTURB_SHIFT;
        i = (i * 5 + 1 + perturb) & mask;
    }
}

bool set_contains(SetObject* s, Obj key) { return lookkey(s, key, set_key_hash(key)) < s->table.size(); }

bool set_discard(SetObject* s, Obj key) {
    std::size_t k = lookkey(s, key, set_key_hash(key));
    if (k >= s->table.size()) return false;
    Obj old = s->table[k].key;
    s->table[k] = {Obj{}, -1};
    --s->used;
    decref(old);
    return true;
}

namespace {
// set_merge_lock_held: one resize up front; into an empty table of the same size with no dummies
// the slots are copied where they are, into another empty table inserted clean in table order,
// else added one by one with the stored hashes (A9-15). The first fast path decides the order of
// colliding keys, which a reinsertion would not reproduce.
void set_merge(SetObject* so, SetObject* other) {
    if (other == so || other->used == 0) return;
    if ((so->fill + other->used) * 5 >= (so->table.size() - 1) * 3) resize(so, (so->used + other->used) * 2);
    if (so->fill == 0 && so->table.size() == other->table.size() && other->fill == other->used) {
        for (std::size_t i = 0; i < other->table.size(); ++i)
            if (active(other->table[i])) {
                incref(other->table[i].key);
                so->table[i] = other->table[i];
            }
        so->fill = other->fill;
        so->used = other->used;
        return;
    }
    if (so->fill == 0) {
        so->fill = so->used = other->used;
        for (auto& e : other->table)
            if (active(e)) {
                incref(e.key);
                insert_clean(so->table, e.key, e.hash);
            }
        return;
    }
    for (std::size_t i = 0; i < other->table.size(); ++i) {
        if (!active(other->table[i])) continue;
        Ref key = Ref::share(other->table[i].key);
        set_add_hashed(Obj::of(so), key.get(), other->table[i].hash);
    }
}
}  // namespace

void set_update(Obj setv, Obj iterable) {
    if (is_kind(iterable, Kind::Set)) {
        set_merge(static_cast<SetObject*>(setv.object()), static_cast<SetObject*>(iterable.object()));
        return;
    }
    if (is_kind(iterable, Kind::Dict)) {          // set_update_dict_keys: the dict's stored hashes
        std::vector<std::pair<Ref, std::int64_t>> entries;
        for (auto& e : static_cast<Dict*>(iterable.object())->entries)
            if (!e.key.is_unset()) entries.emplace_back(Ref::share(e.key), e.hash);
        for (auto& [k, h] : entries) set_add_hashed(setv, k.get(), h);
        return;
    }
    Ref it = iter(iterable);
    for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get())) set_add(setv, v.get());
}

// ---- set algebra and comparisons, as Objects/setobject.c computes them: the order keys go in
// decides the result's iteration order ----
namespace {
SetObject* as_set(Obj v) { return static_cast<SetObject*>(v.object()); }
Ref new_set_like(Obj model) { return own(new SetObject(as_set(model)->frozen)); }   // make_new_set_basetype
Ref copy_set(Obj so) {
    Ref r = new_set_like(so);
    set_merge(as_set(r.get()), as_set(so));
    return r;
}
bool contains_entry(SetObject* s, Obj key, std::int64_t hash) { return lookkey(s, key, hash) < s->table.size(); }
bool discard_entry(SetObject* s, Obj key, std::int64_t hash) {
    std::size_t k = lookkey(s, key, hash);
    if (k >= s->table.size()) return false;
    Obj old = s->table[k].key;
    s->table[k] = {Obj{}, -1};
    --s->used;
    decref(old);
    return true;
}
void clear_set(SetObject* s) {                   // set_clear_internal: emptied first, then released in table order
    std::vector<SetObject::Entry> old = std::move(s->table);
    s->table.assign(MINSIZE, SetObject::Entry{});
    s->fill = s->used = 0;
    for (auto& e : old) if (active(e)) decref(e.key);
}
// set_next over a live table: each key held while user code may run
template <class F>
void each_entry(SetObject* s, F f) {
    for (std::size_t pos = 0; pos < s->table.size(); ++pos) {
        if (!active(s->table[pos])) continue;
        Ref key = Ref::share(s->table[pos].key);
        if (!f(key.get(), s->table[pos].hash)) return;
    }
}
Ref intersection(Obj sov, Obj otherv) {
    if (sov == otherv) return copy_set(sov);
    Ref result = new_set_like(sov);
    SetObject *so = as_set(sov), *other = as_set(otherv);
    if (other->used > so->used) std::swap(so, other);
    each_entry(other, [&](Obj key, std::int64_t hash) {
        if (contains_entry(so, key, hash)) set_add_hashed(result.get(), key, hash);
        return true;
    });
    return result;
}
void difference_update(Obj sov, Obj otherv) {
    if (sov == otherv) return clear_set(as_set(sov));
    each_entry(as_set(otherv), [&](Obj key, std::int64_t hash) {
        discard_entry(as_set(sov), key, hash);
        return true;
    });
}
Ref difference(Obj sov, Obj otherv) {
    SetObject *so = as_set(sov), *other = as_set(otherv);
    if ((so->used >> 2) > other->used) {
        Ref r = copy_set(sov);
        difference_update(r.get(), otherv);
        return r;
    }
    Ref result = new_set_like(sov);
    each_entry(so, [&](Obj key, std::int64_t hash) {
        if (!contains_entry(other, key, hash)) set_add_hashed(result.get(), key, hash);
        return true;
    });
    return result;
}
void symmetric_difference_update(Obj sov, Obj otherv) {
    if (sov == otherv) return clear_set(as_set(sov));
    each_entry(as_set(otherv), [&](Obj key, std::int64_t hash) {
        if (!discard_entry(as_set(sov), key, hash)) set_add_hashed(sov, key, hash);
        return true;
    });
}
Ref symmetric_difference(Obj sov, Obj otherv) {
    Ref result = new_set_like(sov);
    set_merge(as_set(result.get()), as_set(otherv));
    symmetric_difference_update(result.get(), sov);
    return result;
}
bool issubset(SetObject* so, SetObject* other) {
    if (so->used > other->used) return false;
    bool all = true;
    each_entry(so, [&](Obj key, std::int64_t hash) { return all = contains_entry(other, key, hash); });
    return all;
}
}  // namespace

Ref set_binary(BinOp op, Obj a, Obj b) {
    if (!is_kind(a, Kind::Set) || !is_kind(b, Kind::Set)) return Ref::steal(Obj::of(NOTIMPLEMENTED));
    switch (op) {
        case BinOp::Or: {
            Ref r = copy_set(a);
            set_merge(as_set(r.get()), as_set(b));
            return r;
        }
        case BinOp::And: return intersection(a, b);
        case BinOp::Sub: return difference(a, b);
        case BinOp::Xor: return symmetric_difference(a, b);
        default: return Ref::steal(Obj::of(NOTIMPLEMENTED));
    }
}
Ref set_inplace(BinOp op, Obj a, Obj b) {         // a set's own; a frozenset has none (the binary operator then)
    if (!is_kind(a, Kind::Set) || as_set(a)->frozen || !is_kind(b, Kind::Set)) return Ref::steal(Obj::of(NOTIMPLEMENTED));
    switch (op) {
        case BinOp::Or: set_merge(as_set(a), as_set(b)); break;
        case BinOp::And: {                       // set_intersection_update: the bodies are swapped
            Ref tmp = intersection(a, b);
            SetObject *so = as_set(a), *t = as_set(tmp.get());
            std::swap(so->table, t->table);
            std::swap(so->fill, t->fill);
            std::swap(so->used, t->used);
            break;
        }
        case BinOp::Sub: difference_update(a, b); break;
        case BinOp::Xor: symmetric_difference_update(a, b); break;
        default: return Ref::steal(Obj::of(NOTIMPLEMENTED));
    }
    return Ref::share(a);
}
Ref set_compare(CmpOp op, Obj v, Obj w) {         // set_richcompare
    if (!is_kind(v, Kind::Set) || !is_kind(w, Kind::Set)) return Ref::steal(Obj::of(NOTIMPLEMENTED));
    SetObject *a = as_set(v), *b = as_set(w);
    switch (op) {
        case CmpOp::Eq: return Ref::steal(boolean(a->used == b->used && issubset(a, b)));
        case CmpOp::Ne: return Ref::steal(boolean(!(a->used == b->used && issubset(a, b))));
        case CmpOp::Le: return Ref::steal(boolean(issubset(a, b)));
        case CmpOp::Ge: return Ref::steal(boolean(issubset(b, a)));
        case CmpOp::Lt: return Ref::steal(boolean(a->used < b->used && issubset(a, b)));
        case CmpOp::Gt: return Ref::steal(boolean(a->used > b->used && issubset(b, a)));
        default: return Ref::steal(Obj::of(NOTIMPLEMENTED));
    }
}

Ref build_set(std::initializer_list<Obj> items) {
    Ref s = own(new SetObject(false));
    for (Obj v : items) set_add(s.get(), v);
    return s;
}

namespace {
SetObject* set_self(Obj v) { return static_cast<SetObject*>(v.object()); }
void no_kw(Args a, const char* who) {
    if (a.nkw != 0) raise_new("TypeError", std::string(who) + "() takes no keyword arguments");
}
Ref set_new_fn(Obj, Args a) {                   // __new__(cls, iterable=()): the class comes first
    no_kw(a, "set");
    if (a.npos > 2) raise_new("TypeError", "set expected at most 1 argument, got " + std::to_string(a.npos - 1));
    bool frozen = static_cast<ClassObject*>(a.pos(0).object()) == types().frozenset;
    Ref s = own(new SetObject(frozen));
    if (a.npos == 2) set_update(s.get(), a.pos(1));
    return s;
}
void one_argument(Args a, const char* who) {        // METH_O's check (A9-3)
    no_kw(a, who);
    if (a.npos != 1)
        raise_new("TypeError", std::string("set.") + who + "() takes exactly one argument (" + std::to_string(a.npos) + " given)");
}
Ref set_add_m(Obj self, Args a) {
    one_argument(a, "add");
    set_add(self, a.pos(0));
    return none_ref();
}
Ref set_discard_m(Obj self, Args a) {
    one_argument(a, "discard");
    set_discard(set_self(self), a.pos(0));
    return none_ref();
}
Ref set_remove_m(Obj self, Args a) {
    one_argument(a, "remove");
    if (!set_discard(set_self(self), a.pos(0))) {
        Ref exc = invoke(Obj::of(exception_class("KeyError")), {a.pos(0)});
        raise(exc.get());
    }
    return none_ref();
}
Ref set_update_m(Obj self, Args a) {
    no_kw(a, "update");
    for (std::size_t i = 0; i < a.npos; ++i) set_update(self, a.pos(i));
    return none_ref();
}
Ref set_len_m(Obj self, Args a) {
    dunder_args(self, a, "__len__", 0);
    return Ref::steal(Obj::small(static_cast<std::int64_t>(set_self(self)->used)));
}
Ref set_contains_m(Obj self, Args a) {
    dunder_args(self, a, "__contains__", 1);
    return Ref::steal(boolean(set_contains(set_self(self), a.pos(0))));
}
Ref set_iter_m(Obj self, Args a) {
    dunder_args(self, a, "__iter__", 0);
    return iter(self);
}
}  // namespace

void init_sets() {
    Types& t = types();
    for (ClassObject* c : {t.set, t.frozenset}) {
        auto add = [&](const char* name, NativeFn fn, Binding b = Binding::Method) {
            auto* f = new Builtin(name, fn, Obj{}, b);
            f->owner = c;
            f->flags |= IMMORTAL;
            c->attrs.set(intern(name), Obj::of(f));
        };
        add("__new__", set_new_fn, Binding::Function);
        add("__len__", set_len_m);
        add("__contains__", set_contains_m);
        add("__iter__", set_iter_m);
        if (c == t.set) {
            add("add", set_add_m);
            add("discard", set_discard_m);
            add("remove", set_remove_m);
            add("update", set_update_m);
        }
    }
    destroyer(Kind::Set) = [](Object* o) {
        auto* s = static_cast<SetObject*>(o);       // set_dealloc: the table in order
        for (auto& e : s->table)
            if (!e.key.is_unset()) decref(std::exchange(e.key, Obj{}));
        delete s;
    };
}

}  // namespace bella
