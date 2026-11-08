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
                if (freeslot != SIZE_MAX) {      // the last dummy it passed (set_add_entry_takeref)
                    if (!dummy(s->table[freeslot])) {
                        decref(key);
                        goto restart;
                    }
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
            } else if (dummy(e)) {
                freeslot = k;
            }
            if (probes-- == 0) break;
        }
        perturb >>= PERTURB_SHIFT;
        i = (i * 5 + 1 + perturb) & mask;
    }
}

namespace {
// set_contains, set_remove, set_discard: a set as the key is looked for as a frozenset of its items
template <class F>
auto with_set_key(Obj key, F f) {
    try {
        return f(key, set_key_hash(key));
    } catch (const PyError& e) {
        if (!is_kind(key, Kind::Set) || !isinstance(e.exc.get(), exception_class("TypeError"))) throw;
    }
    Ref tmp = own(new SetObject(true));
    set_update(tmp.get(), key);
    return f(tmp.get(), set_key_hash(tmp.get()));
}
}  // namespace

bool set_contains_hashed(SetObject* s, Obj key, std::int64_t hash) { return lookkey(s, key, hash) < s->table.size(); }
bool set_contains(SetObject* s, Obj key) {
    return with_set_key(key, [s](Obj k, std::int64_t hash) { return lookkey(s, k, hash) < s->table.size(); });
}

bool set_discard(SetObject* s, Obj key) {
    return with_set_key(key, [s](Obj kv, std::int64_t hash) {
    std::size_t k = lookkey(s, kv, hash);
    if (k >= s->table.size()) return false;
    Obj old = s->table[k].key;
    s->table[k] = {Obj{}, -1};
    --s->used;
    decref(old);
    return true;
    });
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
    if (is_kind(iterable, Kind::Dict) && !is_subclass_instance(iterable)) {   // PyDict_CheckExact: its stored hashes
        // set_update_dict_lock_held: one big resize at the start, which decides the table
        auto* so = static_cast<SetObject*>(setv.object());
        std::size_t incoming = static_cast<Dict*>(iterable.object())->used;
        if ((so->fill + incoming) * 5 >= (so->table.size() - 1) * 3) resize(so, (so->used + incoming) * 2);
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
    s->finger = 0;
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
// the iterable's side of set_intersection: stops once the result is as large as so
Ref intersection_any(Obj sov, Obj otherv) {
    if (sov == otherv || is_kind(otherv, Kind::Set)) return intersection(sov, otherv);
    Ref result = new_set_like(sov);
    SetObject* so = as_set(sov);
    Ref it = iter(otherv);
    for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get())) {
        std::int64_t hash = hash_of(v.get());    // PyObject_Hash, in its plain words
        if (contains_entry(so, v.get(), hash)) {
            set_add_hashed(result.get(), v.get(), hash);
            if (as_set(result.get())->used >= so->used) break;
        }
    }
    return result;
}
// set_contains_key and set_discard_key: a set as a key is an error here, as `in` does not make it
bool contains_key(SetObject* s, Obj key) { return contains_entry(s, key, set_key_hash(key)); }
void difference_update(Obj sov, Obj otherv) {    // set_difference_update_internal
    if (sov == otherv) return clear_set(as_set(sov));
    SetObject* so = as_set(sov);
    if (is_kind(otherv, Kind::Set)) {
        Ref other = (as_set(otherv)->used >> 3) > so->used ? intersection(sov, otherv) : Ref::share(otherv);
        each_entry(as_set(other.get()), [&](Obj key, std::int64_t hash) {
            discard_entry(so, key, hash);
            return true;
        });
    } else {
        Ref it = iter(otherv);
        for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get())) discard_entry(so, v.get(), set_key_hash(v.get()));
    }
    if (so->fill - so->used <= (so->table.size() - 1) / 4) return;    // more than a quarter are dummies: resized away
    resize(so, so->used > 50000 ? so->used * 2 : so->used * 4);
}
bool plain_dict(Obj v) { return is_exact_dict(v) || is_exact_frozendict(v); }   // PyAnyDict_CheckExact
Ref copy_and_difference(Obj sov, Obj otherv) {
    Ref r = copy_set(sov);
    difference_update(r.get(), otherv);
    return r;
}
Ref difference(Obj sov, Obj otherv) {            // set_difference_untracked
    SetObject* so = as_set(sov);
    std::size_t other_size = 0;
    if (is_kind(otherv, Kind::Set)) other_size = as_set(otherv)->used;
    else if (plain_dict(otherv)) other_size = static_cast<Dict*>(otherv.object())->used;
    else return copy_and_difference(sov, otherv);
    if ((so->used >> 2) > other_size) return copy_and_difference(sov, otherv);
    Ref result = new_set_like(sov);
    each_entry(so, [&](Obj key, std::int64_t hash) {
        bool found = is_kind(otherv, Kind::Set) ? contains_entry(as_set(otherv), key, hash)
                                                : !dict_find(static_cast<Dict*>(otherv.object()), key, hash).is_unset();
        if (!found) set_add_hashed(result.get(), key, hash);
        return true;
    });
    return result;
}
void symmetric_difference_update_set(Obj sov, SetObject* other) {
    each_entry(other, [&](Obj key, std::int64_t hash) {
        if (!discard_entry(as_set(sov), key, hash)) set_add_hashed(sov, key, hash);
        return true;
    });
}
void symmetric_difference_update(Obj sov, Obj otherv) {
    if (sov == otherv) return clear_set(as_set(sov));
    if (plain_dict(otherv)) {                    // set_symmetric_difference_update_dict: _PyDict_Next, live
        auto* d = static_cast<Dict*>(otherv.object());
        for (std::size_t pos = 0; pos < d->entries.size(); ++pos) {
            if (d->entries[pos].key.is_unset()) continue;
            Ref key = Ref::share(d->entries[pos].key);
            std::int64_t hash = d->entries[pos].hash;
            if (!discard_entry(as_set(sov), key.get(), hash)) set_add_hashed(sov, key.get(), hash);
        }
        return;
    }
    if (is_kind(otherv, Kind::Set)) return symmetric_difference_update_set(sov, as_set(otherv));
    Ref other = new_set_like(sov);
    set_update(other.get(), otherv);
    symmetric_difference_update_set(sov, as_set(other.get()));
}
Ref symmetric_difference(Obj sov, Obj otherv) {  // set_symmetric_difference_impl
    Ref result = new_set_like(sov);
    set_update(result.get(), otherv);
    symmetric_difference_update_set(result.get(), as_set(sov));
    return result;
}
bool issubset(SetObject* so, SetObject* other) {
    if (so->used > other->used) return false;
    bool all = true;
    each_entry(so, [&](Obj key, std::int64_t hash) { return all = contains_entry(other, key, hash); });
    return all;
}
void swap_bodies(SetObject* a, SetObject* b) {   // set_swap_bodies; a finger stays where it is
    std::swap(a->table, b->table);
    std::swap(a->fill, b->fill);
    std::swap(a->used, b->used);
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
            swap_bodies(as_set(a), as_set(tmp.get()));
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

// ---- the set operations of dict keys and items views (Objects/dictobject.c) ----
namespace {
bool contains(Obj container, Obj item) { return truth(compare(CmpOp::In, item, container).get()); }   // PySequence_Contains
std::size_t view_len(Obj v) { return static_cast<Dict*>(static_cast<DictView*>(v.object())->dict.object())->used; }
Ref dictviews_to_set(Obj self) {                 // PySet_New(self), the keys view of an exact dict read as the dict (its hashes)
    Ref result = own(new SetObject(false));
    Obj source = self;
    if (is_kind(self, Kind::DictView) && static_cast<DictView*>(self.object())->which == DictView::Keys &&
        is_exact_dict(static_cast<DictView*>(self.object())->dict))
        source = static_cast<DictView*>(self.object())->dict;
    set_update(result.get(), source);
    return result;
}
Ref dictview_intersect(Obj self, Obj other) {    // _PyDictView_Intersect
    if (!set_like_view(self)) std::swap(self, other);
    std::size_t len_self = view_len(self);
    if (is_kind(other, Kind::Set) && !as_set(other)->frozen && !is_subclass_instance(other) && len_self <= as_set(other)->used)
        return intersection_any(other, self);    // other.intersection(self): the keys of self that other holds
    if (set_like_view(other) && view_len(other) > len_self) std::swap(self, other);
    Ref result = own(new SetObject(false));
    Ref it = iter(other);
    for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get()))
        if (contains(self, v.get())) set_add(result.get(), v.get());
    return result;
}
bool all_contained_in(Obj self, Obj other) {
    Ref it = iter(self);
    for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get()))
        if (!contains(other, v.get())) return false;
    return true;
}
}  // namespace
Ref dictview_binary(BinOp op, Obj a, Obj b) {    // dictviews_sub, _PyDictView_Intersect, dictviews_or, dictviews_xor: a set
    if (op == BinOp::And) return dictview_intersect(a, b);
    Ref result = dictviews_to_set(a);
    if (op == BinOp::Sub) difference_update(result.get(), b);
    else if (op == BinOp::Or) set_update(result.get(), b);
    else symmetric_difference_update(result.get(), b);
    return result;
}
Ref dictview_compare(CmpOp op, Obj self, Obj other) {   // dictview_richcompare: against a set, a frozenset or a keys or items view
    if (!is_kind(other, Kind::Set) && !set_like_view(other)) return Ref::steal(Obj::of(NOTIMPLEMENTED));
    std::size_t len_self = view_len(self);
    std::size_t len_other = is_kind(other, Kind::Set) ? as_set(other)->used : view_len(other);
    bool ok = false;
    switch (op) {
        case CmpOp::Eq: ok = len_self == len_other && all_contained_in(self, other); break;
        case CmpOp::Ne: ok = !(len_self == len_other && all_contained_in(self, other)); break;
        case CmpOp::Lt: ok = len_self < len_other && all_contained_in(self, other); break;
        case CmpOp::Le: ok = len_self <= len_other && all_contained_in(self, other); break;
        case CmpOp::Gt: ok = len_self > len_other && all_contained_in(other, self); break;
        case CmpOp::Ge: ok = len_self >= len_other && all_contained_in(other, self); break;
        default: return Ref::steal(Obj::of(NOTIMPLEMENTED));
    }
    return Ref::steal(boolean(ok));
}
Ref dictview_isdisjoint_m(Obj self, Args a) {    // dictviews_isdisjoint
    onearg(a, type_of(self)->name + ".isdisjoint");
    Obj other = a.pos(0);
    if (other == self) return Ref::steal(boolean(view_len(self) == 0));
    if (is_kind(other, Kind::Set) || set_like_view(other)) {   // the shorter is iterated, when the other side is cheap to ask
        std::size_t len_other = is_kind(other, Kind::Set) ? as_set(other)->used : view_len(other);
        if (len_other > view_len(self)) std::swap(self, other);
    }
    Ref it = iter(other);
    for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get()))
        if (contains(self, v.get())) return Ref::steal(boolean(false));
    return Ref::steal(boolean(true));
}

Ref build_folded_set(std::initializer_list<Obj> items) {   // BUILD_SET 0, a frozenset constant, SET_UPDATE
    Ref constant = own(new SetObject(true));
    for (Obj v : items) set_add(constant.get(), v);
    Ref out = own(new SetObject(false));
    set_update(out.get(), constant.get());
    return out;
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
Ref set_new_fn(Obj, Args a) {                   // set_new: the arguments are __init__'s
    new_wrapper_class(a, types().set);
    return own(new SetObject(false));
}
Ref set_init_m(Obj self, Args a) {              // set_init
    no_kw(a, "set");
    if (a.npos > 1) raise_new("TypeError", type_of(self)->name + " expected at most 1 argument, got " + std::to_string(a.npos));
    if (set_self(self)->fill != 0) clear_set(set_self(self));
    if (a.npos == 1) set_update(self, a.pos(0));
    return none_ref();
}
Ref frozenset_new_fn(Obj, Args a) {             // frozenset_new, make_new_frozenset
    new_wrapper_class(a, types().frozenset);
    no_kw(a, "frozenset");
    if (a.npos > 2) raise_new("TypeError", "frozenset expected at most 1 argument, got " + std::to_string(a.npos - 1));
    if (a.npos == 2 && is_kind(a.pos(1), Kind::Set) && set_self(a.pos(1))->frozen) return Ref::share(a.pos(1));
    Ref s = own(new SetObject(true));
    if (a.npos == 2) set_update(s.get(), a.pos(1));
    return s;
}
std::string named(Obj self, const char* name) { return type_of(self)->name + "." + name; }
Ref set_copy_m(Obj self, Args a) {              // set_copy_impl, frozenset_copy_impl
    noargs(a, named(self, "copy"));
    return set_self(self)->frozen ? Ref::share(self) : copy_set(self);
}
Ref set_clear_m(Obj self, Args a) {
    noargs(a, named(self, "clear"));
    clear_set(set_self(self));
    return none_ref();
}
Ref set_pop_m(Obj self, Args a) {               // set_pop_impl
    noargs(a, named(self, "pop"));
    SetObject* so = set_self(self);
    if (so->used == 0) raise_new("KeyError", "pop from an empty set");
    std::size_t mask = so->table.size() - 1, i = so->finger & mask;
    while (!active(so->table[i])) i = i == mask ? 0 : i + 1;
    Obj key = so->table[i].key;
    so->table[i] = {Obj{}, -1};
    --so->used;
    so->finger = i + 1;
    return Ref::steal(key);
}
void many(Obj self, Args a, const char* name) { // METH_FASTCALL with *others
    if (a.nkw != 0) raise_new("TypeError", named(self, name) + "() takes no keyword arguments");
}
Ref set_union_m(Obj self, Args a) {             // set_union_impl
    many(self, a, "union");
    Ref result = copy_set(self);
    for (std::size_t i = 0; i < a.npos; ++i)
        if (a.pos(i) != self) set_update(result.get(), a.pos(i));
    return result;
}
Ref intersection_multi(Obj self, Args a) {      // set_intersection_multi_impl
    if (a.npos == 0) return copy_set(self);
    Ref result = Ref::share(self);
    for (std::size_t i = 0; i < a.npos; ++i) result = intersection_any(result.get(), a.pos(i));
    return result;
}
Ref set_intersection_m(Obj self, Args a) {
    many(self, a, "intersection");
    return intersection_multi(self, a);
}
Ref set_intersection_update_m(Obj self, Args a) {
    many(self, a, "intersection_update");
    Ref tmp = intersection_multi(self, a);
    if (tmp.get() != self) swap_bodies(set_self(self), set_self(tmp.get()));
    return none_ref();
}
Ref set_difference_m(Obj self, Args a) {        // set_difference_multi_impl
    many(self, a, "difference");
    if (a.npos == 0) return copy_set(self);
    Ref result = difference(self, a.pos(0));
    for (std::size_t i = 1; i < a.npos; ++i) difference_update(result.get(), a.pos(i));
    return result;
}
Ref set_difference_update_m(Obj self, Args a) {
    many(self, a, "difference_update");
    for (std::size_t i = 0; i < a.npos; ++i) difference_update(self, a.pos(i));
    return none_ref();
}
Ref set_symmetric_difference_m(Obj self, Args a) {
    onearg(a, named(self, "symmetric_difference"));
    return symmetric_difference(self, a.pos(0));
}
Ref set_symmetric_difference_update_m(Obj self, Args a) {
    onearg(a, named(self, "symmetric_difference_update"));
    symmetric_difference_update(self, a.pos(0));
    return none_ref();
}
Ref set_isdisjoint_m(Obj self, Args a) {        // set_isdisjoint_impl
    onearg(a, named(self, "isdisjoint"));
    Obj other = a.pos(0);
    SetObject* so = set_self(self);
    if (other == self) return Ref::steal(boolean(so->used == 0));
    if (is_kind(other, Kind::Set)) {
        SetObject* o = set_self(other);
        if (o->used > so->used) std::swap(so, o);
        bool disjoint = true;
        each_entry(o, [&](Obj key, std::int64_t hash) { return disjoint = !contains_entry(so, key, hash); });
        return Ref::steal(boolean(disjoint));
    }
    Ref it = iter(other);
    for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get()))
        if (contains_key(so, v.get())) return Ref::steal(boolean(false));
    return Ref::steal(boolean(true));
}
Ref set_issubset_m(Obj self, Args a) {          // set_issubset_impl
    onearg(a, named(self, "issubset"));
    if (!is_kind(a.pos(0), Kind::Set)) {
        Ref tmp = intersection_any(self, a.pos(0));
        return Ref::steal(boolean(set_self(tmp.get())->used == set_self(self)->used));
    }
    return Ref::steal(boolean(issubset(set_self(self), set_self(a.pos(0)))));
}
Ref set_issuperset_m(Obj self, Args a) {        // set_issuperset_impl
    onearg(a, named(self, "issuperset"));
    if (is_kind(a.pos(0), Kind::Set)) return Ref::steal(boolean(issubset(set_self(a.pos(0)), set_self(self))));
    Ref it = iter(a.pos(0));
    for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get()))
        if (!contains_key(set_self(self), v.get())) return Ref::steal(boolean(false));
    return Ref::steal(boolean(true));
}
template <BinOp op>
Ref set_inplace_m(Obj self, Args a) {           // __ior__ and its kin: nb_inplace_or
    const char* name = op == BinOp::Or ? "__ior__" : op == BinOp::And ? "__iand__" : op == BinOp::Sub ? "__isub__" : "__ixor__";
    dunder_args(self, a, name, 1);
    return set_inplace(op, self, a.pos(0));
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
        add("__new__", c == t.set ? set_new_fn : frozenset_new_fn, Binding::Function);
        add("copy", set_copy_m);
        add("union", set_union_m);
        add("intersection", set_intersection_m);
        add("difference", set_difference_m);
        add("symmetric_difference", set_symmetric_difference_m);
        add("isdisjoint", set_isdisjoint_m);
        add("issubset", set_issubset_m);
        add("issuperset", set_issuperset_m);
        add("__len__", set_len_m);
        add("__contains__", set_contains_m);
        add("__iter__", set_iter_m);
        if (c == t.set) {
            add("add", set_add_m);
            add("discard", set_discard_m);
            add("remove", set_remove_m);
            add("update", set_update_m);
            add("__init__", set_init_m);
            add("clear", set_clear_m);
            add("pop", set_pop_m);
            add("intersection_update", set_intersection_update_m);
            add("difference_update", set_difference_update_m);
            add("symmetric_difference_update", set_symmetric_difference_update_m);
            add("__ior__", set_inplace_m<BinOp::Or>);
            add("__iand__", set_inplace_m<BinOp::And>);
            add("__isub__", set_inplace_m<BinOp::Sub>);
            add("__ixor__", set_inplace_m<BinOp::Xor>);
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
