// bella/object.hpp -- the object model: values, counting, classes, instance storage and inline
// caches, written from the reference model (refmodel/objects.py), rule for rule (TODO task 3).
//
// Single-threaded first, as task 3 says: plain counters, no atomics, no collector. The design's
// biased counting (design section 3) comes with threads; classes are never freed here (the cycle
// collector frees them later: a class's MRO holds itself, spec D-04), only disposed.
//
// What the model states, and this header implements:
//  * Attribute lookup in Python's order: data descriptor on the class (slots are data
//    descriptors), instance storage (promoted inline field or instance dict, or the dict alone
//    once exposed), non-data descriptor or class attribute, __getattr__, AttributeError.
//  * Lookup as a plan chosen before any user code runs, executed once (C-3-09, C-3-10).
//  * Class versions from one process-wide counter, never reissued (review log D-1, C-3-12).
//  * Inline caches: up to N immutable entries per site keyed by version and name; each kind has
//    its validity check; an entry's `found` is BORROWED (RL-20).
//  * Lifetimes (C-9-08): counted objects and dicts; an object dies at zero with CPython 3.15.2's
//    order: finaliser, __slots__ (most-derived class first, each class's sorted), then the instance attributes in the
//    class's shared-keys order (sorted __static_attributes__, then first store or attempted
//    delete by any instance); a split dict releases in key order, an ordinary one in insertion
//    order. A store keeps the new value before it releases the old one; a class mutation takes a
//    new version before it releases the old attribute, which is what makes a borrowed `found` safe.
//
// The checking mode (heap().checking) does what the model does on every operation: a cached read
// also runs the generic lookup and the two plans must agree (ModelError otherwise), and a death
// that an entry a live class still validates names is a ModelError. heap().quarantine keeps dead
// objects' memory so that a read through a stale pointer is caught instead of undefined.
// runtime/tests/object_differential.py runs this header against CPython and the model.
#pragma once
#include <algorithm>
#include <cstdint>
#include <functional>
#include <memory>
#include <optional>
#include <span>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

namespace bella {

struct AttributeError : std::runtime_error {
    using std::runtime_error::runtime_error;
};
struct TypeError : std::runtime_error {
    using std::runtime_error::runtime_error;
};
struct ModelError : std::logic_error {         // an invariant of the model failed (the checking mode)
    using std::logic_error::logic_error;
};

struct Object;
struct ClassObject;
struct Str;
struct DictObject;
struct Instance;
struct Site;

// ---- Obj: a tagged word: a 63-bit integer immediate (value << 1 | 1), an Object*, or Unset (0) ----
class Obj {
    std::uintptr_t w_ = 0;
    constexpr explicit Obj(std::uintptr_t w) : w_(w) {}
public:
    constexpr Obj() = default;                                         // Unset: an empty slot or field
    static constexpr Obj unset() { return Obj{}; }
    static constexpr Obj small(std::int64_t v) { return Obj{(static_cast<std::uintptr_t>(v) << 1) | 1u}; }
    static Obj of(const Object* p) { return Obj{reinterpret_cast<std::uintptr_t>(p)}; }
    constexpr bool is_unset() const { return w_ == 0; }
    constexpr bool is_small() const { return (w_ & 1u) != 0; }
    constexpr bool is_object() const { return w_ != 0 && (w_ & 1u) == 0; }
    constexpr std::int64_t small_value() const { return static_cast<std::int64_t>(w_) >> 1; }
    Object* object() const { return reinterpret_cast<Object*>(w_); }
    friend constexpr bool operator==(Obj, Obj) = default;
};

// ---- the header: no virtual functions; a dying object is dispatched on its kind ----
enum class Kind : std::uint8_t {
    Str, Dict, Class, Instance, Function, SlotDescriptor, Marker,
    // the runtime's own objects (bella/runtime.hpp): their deaths go through destroyer(kind)
    Singleton, Bool, BigInt, Float, Tuple, List, Cell, PyFunction, Builtin, Method, Module,
    Range, Iterator, Traceback, Native, GetSet, Slice, Proxy, Set, DictView, Super, IntInstance, FloatInstance, Complex, ComplexInstance, Generator, LazyImport, AbcData, Bytes, ByteArray, CodeKind, KindCount
};
// HAS_ATTRIBUTES: an object of a built-in kind whose class is a subclass of the program's, with that
// class's attribute storage beside the built-in's data (DictInstance)
enum Flag : std::uint16_t { IMMORTAL = 1u << 0, DEAD = 1u << 1, DICT_EXPOSED = 1u << 2, HAS_ATTRIBUTES = 1u << 3, FINALIZED = 1u << 4, FROZEN_DICT = 1u << 5, HAS_WEAKREFS = 1u << 6, WEAK_REFERENCE = 1u << 7 };

struct Object {
    ClassObject* cls = nullptr;
    std::uint32_t refs = 0;          // single-threaded count; biased counting comes with threads
    std::uint16_t flags = 0;
    Kind kind;
    explicit Object(Kind k) : kind(k) {}
    Object(const Object&) = delete;
    Object& operator=(const Object&) = delete;
    bool alive() const { return (flags & DEAD) == 0; }
};

// ---- the heap: what the checks see (live classes validate entries; sites hold them) ----
// A weak reference (RefWeak, Objects/weakrefobject.c): the record of an object flagged WEAK_REFERENCE.
// Any object can be one, so that a class of the runtime's can present it, with a subclass's storage
// or without. The lists are off to the side: the header has no room for one, and few objects have any.
enum class WeakKind : std::uint8_t { BasicRef, BasicProxy, Other };
struct WeakRecord {
    Object* holder;                             // the reference object; it has its own count
    Object* target;                             // not counted; null once the target has died
    std::uintptr_t callback;                    // an Obj's word, owned; 0: none or already taken
    WeakKind kind;
};
struct Heap {
    std::vector<ClassObject*> classes;          // live classes
    std::vector<Site*> sites;
    bool checking = false;
    bool quarantine = false;
    std::vector<Object*> graveyard;             // quarantined dead objects
    std::function<void(Object*)> on_death;      // called as an object dies, after its finaliser
    std::unordered_map<const Object*, std::vector<WeakRecord*>> weak_lists;   // a target's, in CPython's order
    std::unordered_map<const Object*, WeakRecord*> weak_records;              // a holder's
};
inline Heap& heap() {
    static Heap h;
    return h;
}

void dealloc(Object* o);

// The runtime registers how each of its kinds dies (releases what it holds, in CPython's order,
// then frees itself); the object model's own kinds die in dealloc below.
using Destroyer = void (*)(Object*);
inline Destroyer& destroyer(Kind k) {
    static Destroyer table[static_cast<std::size_t>(Kind::KindCount)] = {};
    return table[static_cast<std::size_t>(k)];
}

inline void incref(Object* o) {
    if (o->flags & IMMORTAL) return;
    if (o->flags & DEAD) throw ModelError("a reference to a dead object was taken");
    ++o->refs;
}
inline void decref(Object* o) {
    if (o->flags & IMMORTAL) return;
    if (o->refs == 0) throw ModelError("an object released more often than it was held");
    if (--o->refs == 0) dealloc(o);
}
inline void incref(Obj v) {
    if (v.is_object()) incref(v.object());
}
inline void decref(Obj v) {
    if (v.is_object()) decref(v.object());
}

// An owning handle for a value: the caller's reference to what an operation returns.
class Ref {
    Obj v_;
public:
    Ref() = default;
    static Ref steal(Obj v) { Ref r; r.v_ = v; return r; }       // takes a reference already counted
    static Ref share(Obj v) { incref(v); return steal(v); }
    Ref(const Ref& o) : v_(o.v_) { incref(v_); }
    Ref(Ref&& o) noexcept : v_(std::exchange(o.v_, Obj{})) {}
    Ref& operator=(Ref o) noexcept { std::swap(v_, o.v_); return *this; }
    ~Ref() { if (v_.is_object()) decref(v_); }
    Obj get() const { return v_; }
    Obj release() { return std::exchange(v_, Obj{}); }
};

ClassObject* builtin_class(const char* name);

// ---- strings: interned, immortal (attribute names) ----
// ---- str: PEP 393 storage (spec decision 3, D-13): Latin-1, UCS-2 or UCS-4 code units per string,
// O(1) indexing; `text` is the UTF-8 copy (lone surrogates in the generalised form, as CPython's
// "surrogatepass"), which names, messages and output use. Interned strings are immortal. ----
struct Str : Object {
    std::string text;                 // UTF-8
    std::string units;                // `width` bytes per code point, little-endian
    std::size_t length = 0;           // code points
    std::uint8_t width = 1;           // PEP 393 kind: 1, 2 or 4
    bool ascii = true;
    mutable std::int64_t hash = -1;   // -1: not computed yet (as CPython's)
    explicit Str(std::string utf8, bool immortal = true) : Object(Kind::Str), text(std::move(utf8)) {
        cls = builtin_class("str");
        if (immortal) flags |= IMMORTAL;
        index();
    }
    Str(std::u32string_view cps, bool immortal) : Object(Kind::Str) {
        cls = builtin_class("str");
        if (immortal) flags |= IMMORTAL;
        for (char32_t c : cps) append_utf8(text, c);
        index();
    }
    char32_t at(std::size_t i) const {
        switch (width) {
            case 1: return static_cast<unsigned char>(units[i]);
            case 2: return static_cast<char32_t>(static_cast<unsigned char>(units[2 * i]) |
                                                 static_cast<unsigned char>(units[2 * i + 1]) << 8);
            default: {
                char32_t c = 0;
                for (int k = 3; k >= 0; --k) c = (c << 8) | static_cast<unsigned char>(units[4 * i + k]);
                return c;
            }
        }
    }
    static void append_utf8(std::string& out, char32_t c) {
        if (c < 0x80) out += static_cast<char>(c);
        else if (c < 0x800) { out += static_cast<char>(0xC0 | (c >> 6)); out += static_cast<char>(0x80 | (c & 0x3F)); }
        else if (c < 0x10000) {
            out += static_cast<char>(0xE0 | (c >> 12)); out += static_cast<char>(0x80 | ((c >> 6) & 0x3F));
            out += static_cast<char>(0x80 | (c & 0x3F));
        } else {
            out += static_cast<char>(0xF0 | (c >> 18)); out += static_cast<char>(0x80 | ((c >> 12) & 0x3F));
            out += static_cast<char>(0x80 | ((c >> 6) & 0x3F)); out += static_cast<char>(0x80 | (c & 0x3F));
        }
    }
private:
    void index() {
        std::u32string cps;
        for (std::size_t i = 0; i < text.size();) {
            auto b = static_cast<unsigned char>(text[i]);
            int n = b < 0x80 ? 1 : b < 0xE0 ? 2 : b < 0xF0 ? 3 : 4;
            char32_t c = n == 1 ? b : n == 2 ? (b & 0x1F) : n == 3 ? (b & 0x0F) : (b & 0x07);
            for (int k = 1; k < n && i + k < text.size(); ++k) c = (c << 6) | (static_cast<unsigned char>(text[i + k]) & 0x3F);
            cps.push_back(c);
            i += n;
        }
        length = cps.size();
        char32_t top = 0;
        for (char32_t c : cps) top = std::max(top, c);
        ascii = top < 0x80;
        width = top < 0x100 ? 1 : top < 0x10000 ? 2 : 4;
        if (ascii) { units = text; return; }
        units.reserve(length * width);
        for (char32_t c : cps)
            for (int k = 0; k < width; ++k) units += static_cast<char>((c >> (8 * k)) & 0xFF);
    }
};
inline const Str* intern(std::string_view s) {
    static std::unordered_map<std::string, std::unique_ptr<Str>> table;
    auto it = table.find(std::string(s));
    if (it == table.end()) {
        it = table.emplace(std::string(s), std::make_unique<Str>(std::string(s))).first;
        it->second->cls = builtin_class("str");
    }
    return it->second.get();
}

// ---- an insertion-ordered map from interned names to values (counts are the owner's business) ----
class NameMap {
    std::vector<std::pair<const Str*, Obj>> entries_;          // nullptr key: a deleted entry
    std::unordered_map<const Str*, std::size_t> index_;
public:
    const Obj* find(const Str* k) const {
        auto it = index_.find(k);
        return it == index_.end() ? nullptr : &entries_[it->second].second;
    }
    bool contains(const Str* k) const { return index_.contains(k); }
    // Stores v; returns the value it replaced (Unset if the name is new, which goes to the end).
    Obj set(const Str* k, Obj v) {
        auto it = index_.find(k);
        if (it != index_.end()) return std::exchange(entries_[it->second].second, v);
        index_.emplace(k, entries_.size());
        entries_.emplace_back(k, v);
        return Obj{};
    }
    // Removes k; returns its value, Unset if absent.
    Obj pop(const Str* k) {
        auto it = index_.find(k);
        if (it == index_.end()) return Obj{};
        auto& e = entries_[it->second];
        Obj v = e.second;
        e = {nullptr, Obj{}};
        index_.erase(it);
        return v;
    }
    std::vector<std::pair<const Str*, Obj>> items() const {
        std::vector<std::pair<const Str*, Obj>> out;
        for (const auto& e : entries_) if (e.first != nullptr) out.push_back(e);
        return out;
    }
    std::size_t size() const { return index_.size(); }
    std::vector<std::pair<const Str*, Obj>> take_all() {      // empties the map, in insertion order
        auto out = items();
        entries_.clear();
        index_.clear();
        return out;
    }
};

// ---- shared keys: the per-class key order of split dicts (refmodel RefClass.keys) ----
inline constexpr std::size_t SHARED_KEYS_MAX = 30;      // SHARED_KEYS_MAX_SIZE, Objects/dictobject.c
struct SharedKeys {
    std::vector<const Str*> names;
    bool contains(const Str* n) const { return std::find(names.begin(), names.end(), n) != names.end(); }
    // Records n; false when the keys are full and n is not there.
    bool note(const Str* n) {
        if (contains(n)) return true;
        if (names.size() >= SHARED_KEYS_MAX) return false;
        names.push_back(n);
        return true;
    }
};

// ---- the dict: one type for every dict, an instance's __dict__ included (refmodel RefDict) ----
// CPython's compact dict (Objects/dictobject.c): an index table probed with the perturbation
// scheme over entries in insertion order, resized to the smallest power of two above three times
// the entries in use. Keys compare by identity, then by hash and ==, through the runtime's hooks
// (without the runtime: a str by its text, anything else by identity). A dict made by exposing an
// instance's __dict__ is split: `split` is its class's shared keys, and its values die in their
// order; `embedded` is the live object whose values it holds. The rules for when a split dict
// becomes ordinary are measured on 3.15.2 (refmodel RefDict.store, popitem_, clear_, copy_).
struct DictObject : Object {
    struct Entry { std::int64_t hash; Obj key; Obj value; };   // key Unset: deleted
    std::vector<Entry> entries;
    std::vector<std::int64_t> indices;           // -1 empty, -2 dummy, else an entry index
    std::size_t used = 0;
    std::uint64_t version = 0;                   // changes on every mutation
    std::uint64_t layout = 0;                    // changes when the table is rebuilt: a lookup restarts
    std::shared_ptr<SharedKeys> split;           // the class keys it shares, or null: an ordinary dict
    const Object* embedded = nullptr;            // the live object whose values these are (exposure)
    std::int64_t frozen_hash = -1;               // a frozendict's hash once asked (ma_hash); -1: not yet
    DictObject();
    void note_key(const Str* n) {
        if (split && !split->note(n)) split.reset();   // the keys are full: an ordinary dict from now on
    }
};

// A key's hash and ==, which may run Python code (the runtime's hash_of and keys_equal).
using KeyHashHook = std::int64_t (*)(Obj key);
using KeyEqHook = bool (*)(Obj a, Obj b);
inline KeyHashHook& key_hash_hook() {
    static KeyHashHook hook = nullptr;
    return hook;
}
inline KeyEqHook& key_eq_hook() {
    static KeyEqHook hook = nullptr;
    return hook;
}

namespace detail {
constexpr std::int64_t DKIX_EMPTY = -1, DKIX_DUMMY = -2;
constexpr int PERTURB_SHIFT = 5;
inline bool is_str(Obj v) { return v.is_object() && v.object()->kind == Kind::Str; }
inline bool is_exact_str_key(Obj v) { return is_str(v) && !(v.object()->flags & HAS_ATTRIBUTES); }   // PyUnicode_CheckExact: a split table holds no other
inline std::int64_t key_hash(Obj k) {
    if (key_hash_hook() != nullptr) return key_hash_hook()(k);
    if (k.is_small()) return k.small_value() == -1 ? -2 : k.small_value();
    if (is_str(k)) return static_cast<std::int64_t>(std::hash<std::string>{}(static_cast<const Str*>(k.object())->text) >> 1);
    return static_cast<std::int64_t>(reinterpret_cast<std::uintptr_t>(k.object()) >> 4);
}
inline bool key_eq(Obj a, Obj b) {
    if (key_eq_hook() != nullptr) return key_eq_hook()(a, b);
    return is_str(a) && is_str(b) && static_cast<const Str*>(a.object())->text == static_cast<const Str*>(b.object())->text;
}
inline std::size_t usable(const DictObject* d) { return d->indices.size() * 2 / 3; }

// The index slot where `key` is, or where it would go, and its entry index (or DKIX_EMPTY). A
// comparison that changed the table or the entry starts the lookup again, as CPython does
// (DKIX_KEY_CHANGED).
inline std::pair<std::size_t, std::int64_t> probe(DictObject* d, Obj key, std::int64_t hash) {
restart:
    std::size_t mask = d->indices.size() - 1;
    auto perturb = static_cast<std::uint64_t>(hash);
    std::size_t i = static_cast<std::size_t>(hash) & mask;
    std::optional<std::size_t> free_slot;
    for (;;) {
        std::int64_t ix = d->indices[i];
        if (ix == DKIX_EMPTY) return {free_slot.value_or(i), DKIX_EMPTY};
        if (ix == DKIX_DUMMY) {
            if (!free_slot) free_slot = i;
        } else {
            auto& e = d->entries[static_cast<std::size_t>(ix)];
            if (e.key == key) return {i, ix};
            if (e.hash == hash) {
                std::uint64_t layout = d->layout;
                Obj start = e.key;
                incref(start);
                bool eq;
                try {
                    eq = key_eq(start, key);
                } catch (...) {
                    decref(start);
                    throw;
                }
                bool same = d->layout == layout && static_cast<std::size_t>(ix) < d->entries.size() &&
                            d->entries[static_cast<std::size_t>(ix)].key == start;
                decref(start);
                if (!same) {
                    if (d->indices.empty()) return {0, DKIX_EMPTY};
                    goto restart;
                }
                if (eq) return {i, ix};
            }
        }
        perturb >>= PERTURB_SHIFT;
        i = (i * 5 + static_cast<std::size_t>(perturb) + 1) & mask;
    }
}

// dictresize to calculate_log2_keysize(minsize): the smallest power of two at least minsize, and 8
inline void rebuild(DictObject* d, std::size_t minsize) {
    std::size_t size = 8;
    while (size < minsize) size <<= 1;
    std::vector<DictObject::Entry> live;
    for (auto& e : d->entries) if (!e.key.is_unset()) live.push_back(e);
    d->entries = std::move(live);
    d->indices.assign(size, DKIX_EMPTY);
    ++d->layout;
    std::size_t mask = size - 1;
    for (std::size_t ix = 0; ix < d->entries.size(); ++ix) {
        auto perturb = static_cast<std::uint64_t>(d->entries[ix].hash);
        std::size_t i = static_cast<std::size_t>(d->entries[ix].hash) & mask;
        while (d->indices[i] != DKIX_EMPTY) {
            perturb >>= PERTURB_SHIFT;
            i = (i * 5 + static_cast<std::size_t>(perturb) + 1) & mask;
        }
        d->indices[i] = static_cast<std::int64_t>(ix);
    }
}

// find_empty_slot: the first index slot on hash's probe sequence that holds no entry (empty or a
// dummy); no key is compared
inline std::size_t find_empty_slot(const DictObject* d, std::int64_t hash) {
    std::size_t mask = d->indices.size() - 1;
    auto perturb = static_cast<std::uint64_t>(hash);
    std::size_t i = static_cast<std::size_t>(hash) & mask;
    while (d->indices[i] >= 0) {
        perturb >>= PERTURB_SHIFT;
        i = (i * 5 + static_cast<std::size_t>(perturb) + 1) & mask;
    }
    return i;
}

// insert_combined_dict: a key the lookup did not find goes at the end, at the slot the lookup
// found, or after a resize (to three times the entries in use) at the first free one; the key's
// count is taken here, value's is the caller's
inline void insert_new(DictObject* d, Obj key, std::int64_t hash, Obj value, std::size_t slot) {
    if (d->split) d->note_key(static_cast<const Str*>(key.object()));
    if (d->entries.size() >= usable(d)) {
        rebuild(d, d->used * 3);
        slot = find_empty_slot(d, hash);
    }
    incref(key);
    d->indices[slot] = static_cast<std::int64_t>(d->entries.size());
    d->entries.push_back({hash, key, value});
    ++d->used;
}
}  // namespace detail

// The value stored under key (borrowed), or Unset.
inline Obj dict_find(DictObject* d, Obj key, std::int64_t hash) {
    if (d->indices.empty()) return Obj{};
    auto [slot, ix] = detail::probe(d, key, hash);
    return ix >= 0 ? d->entries[static_cast<std::size_t>(ix)].value : Obj{};
}
inline Obj dict_find(DictObject* d, Obj key) { return dict_find(d, key, detail::key_hash(key)); }

// Stores value under key (insertdict), moving in one count of value the caller holds once the
// lookup has succeeded; a lookup that raises takes nothing. Returns the value it replaced with
// its count (Unset if the key is new, which goes to the end). A key that is not a str makes a
// split dict ordinary; a new str key joins its shared keys while there is room.
inline Obj dict_put(DictObject* d, Obj key, std::int64_t hash, Obj value) {
    if (d->split && !detail::is_exact_str_key(key)) d->split.reset();
    if (d->indices.empty()) detail::rebuild(d, 0);
    auto [slot, ix] = detail::probe(d, key, hash);
    ++d->version;
    if (ix >= 0) return std::exchange(d->entries[static_cast<std::size_t>(ix)].value, value);
    detail::insert_new(d, key, hash, value, slot);
    return Obj{};
}
// d[key] = value: the new value is stored before the old one is released; when the lookup raises,
// the count taken for the store is given back before the error goes on (refmodel RefDict.store)
inline void dict_store(DictObject* d, Obj key, std::int64_t hash, Obj value) {
    incref(value);
    Obj old;
    try {
        old = dict_put(d, key, hash, value);
    } catch (...) {
        decref(value);
        throw;
    }
    decref(old);
}
// dict.setdefault(key, dflt): one lookup; a missing key is inserted where it was looked for
// (dict_setdefault_ref_lock_held). Returns the value now under key, borrowed.
inline Obj dict_setdefault(DictObject* d, Obj key, std::int64_t hash, Obj dflt) {
    if (d->split && !detail::is_exact_str_key(key)) d->split.reset();
    if (d->indices.empty()) detail::rebuild(d, 0);
    auto [slot, ix] = detail::probe(d, key, hash);
    if (ix >= 0) return d->entries[static_cast<std::size_t>(ix)].value;
    ++d->version;
    incref(dflt);
    detail::insert_new(d, key, hash, dflt, slot);
    return dflt;
}
// dictresize(estimate_log2_keysize(n)), before a bulk insert of n entries (the caller's condition)
inline void dict_resize_estimate(DictObject* d, std::size_t n) { detail::rebuild(d, (n * 3 + 1) / 2); }
inline std::size_t dict_usable(const DictObject* d) { return detail::usable(d); }
inline void dict_store(DictObject* d, Obj key, Obj value) { dict_store(d, key, detail::key_hash(key), value); }

// Removes key and releases the key; returns its value with its count, or Unset when absent.
inline Obj dict_pop(DictObject* d, Obj key, std::int64_t hash) {
    if (d->indices.empty()) return Obj{};
    auto [slot, ix] = detail::probe(d, key, hash);
    if (ix < 0) return Obj{};
    auto& e = d->entries[static_cast<std::size_t>(ix)];
    d->indices[slot] = detail::DKIX_DUMMY;
    Obj k = std::exchange(e.key, Obj{});
    Obj v = std::exchange(e.value, Obj{});
    --d->used;
    ++d->version;
    decref(k);
    return v;
}
inline Obj dict_pop(DictObject* d, Obj key) { return dict_pop(d, key, detail::key_hash(key)); }

// dict_popitem: the last entry, found by its index and removed with nothing compared (lookdict_index);
// its key and value, with their counts. The table must hold an entry and not be split.
inline std::pair<Obj, Obj> dict_take_last(DictObject* d) {
    std::size_t ix = d->entries.size();
    while (d->entries[ix - 1].key.is_unset()) --ix;
    --ix;
    auto& e = d->entries[ix];
    std::size_t mask = d->indices.size() - 1;
    auto perturb = static_cast<std::uint64_t>(e.hash);
    std::size_t i = static_cast<std::size_t>(e.hash) & mask;
    while (d->indices[i] != static_cast<std::int64_t>(ix)) {
        perturb >>= 5;
        i = (i * 5 + perturb + 1) & mask;
    }
    d->indices[i] = detail::DKIX_DUMMY;
    std::pair<Obj, Obj> out{std::exchange(e.key, Obj{}), std::exchange(e.value, Obj{})};
    d->entries.resize(ix);
    --d->used;
    ++d->version;
    return out;
}

// Empties d; returns its keys and values, with their counts, in insertion order.
inline std::vector<std::pair<Obj, Obj>> dict_take_all(DictObject* d) {
    std::vector<std::pair<Obj, Obj>> out;
    for (auto& e : d->entries)
        if (!e.key.is_unset()) out.emplace_back(e.key, e.value);
    d->entries.clear();
    d->indices.clear();
    d->used = 0;
    ++d->version;
    ++d->layout;
    return out;
}

namespace detail {
// Releases what a dict held: a split dict's values in its shared keys' order (then any value
// under a name the keys could not take), then the keys; an ordinary dict's entries in order, each
// key before its value.
inline void release_entries(std::vector<std::pair<Obj, Obj>> items, const SharedKeys* split) {
    if (split == nullptr) {
        for (auto& [k, v] : items) {
            decref(k);
            decref(v);
        }
        return;
    }
    std::vector<Obj> order;
    for (const Str* name : split->names)
        for (auto& [k, v] : items)
            if (k.object() == name && !v.is_unset()) { order.push_back(v); v = Obj{}; }
    for (auto& [k, v] : items) if (!v.is_unset()) order.push_back(std::exchange(v, Obj{}));
    for (Obj v : order) decref(v);
    for (auto& [k, v] : items) decref(k);
}
}  // namespace detail

// dict.clear(): a split dict stays split only while its values are embedded in the live object
// it was exposed from.
inline void dict_clear(DictObject* d) {
    auto split = d->split;
    if (d->embedded == nullptr) d->split.reset();
    detail::release_entries(dict_take_all(d), split.get());
}
// dict.popitem()'s first step: a split dict becomes ordinary.
inline void dict_unsplit(DictObject* d) { d->split.reset(); }
// clone_combined_dict_keys (and copy_values for a split dict): `to`, empty, takes from's table as
// it stands, deleted entries and all; no key is compared. A split dict's copy shares its keys.
inline void dict_clone_into(DictObject* to, const DictObject* from) {
    to->entries = from->entries;
    for (auto& e : to->entries)
        if (!e.key.is_unset()) {
            incref(e.key);
            incref(e.value);
        }
    to->indices = from->indices;
    to->used = from->used;
    to->split = from->split;
    ++to->version;
    ++to->layout;
}

// ---- native functions: what a class attribute holds where the model holds a Python callable ----
struct Function : Object {
    std::function<Obj(std::span<const Obj>)> fn;     // returns a new reference
    explicit Function(std::function<Obj(std::span<const Obj>)> f);
};

struct SlotDescriptor : Object {                     // a real __slots__ member: a data descriptor
    const Str* name;
    ClassObject* owner = nullptr;                    // the class it was made for: what it says it applies to
    explicit SlotDescriptor(const Str* n);
};

struct Marker : Object {                             // an opaque value tests produce and compare by text
    std::string text;
    explicit Marker(std::string t);
};

// ---- class versions: one process-wide counter, never reissued (review log D-1) ----
inline constexpr std::uint64_t NO_VERSION = 0;
struct VersionCounter {
    std::uint64_t next = 1;
    std::uint64_t limit = ~std::uint64_t{0};
    std::uint64_t issue() {
        if (next > limit || next == 0) return NO_VERSION;
        return next++;
    }
};
inline VersionCounter& versions() {
    static VersionCounter v;
    return v;
}

// ---- classes (refmodel RefClass) ----
struct ClassObject : Object {
    std::string name;
    std::string qualname;                        // __qualname__ (the name unless the class body set one)
    bool heap_type = false;                      // a class a program made (Py_TPFLAGS_HEAPTYPE)
    std::vector<ClassObject*> bases;
    std::vector<ClassObject*> mro;               // C3, self first
    std::vector<ClassObject*> subclasses;
    NameMap attrs;                               // owns one count of each value
    std::uint64_t version = NO_VERSION;
    std::optional<std::vector<const Str*>> slots;    // as declared; nullopt: no __slots__
    std::vector<const Str*> promoted;            // this class's own promoted fields
    std::vector<const Str*> slot_fields;         // inherited, in MRO-reversed declaration order
    std::vector<const Str*> promoted_fields;
    // a built-in type's C fields (BaseException's args, __traceback__, __cause__, ...), in the order
    // its clear function releases them, "__dict__" marking the dict's place; a class that declares
    // none has that of the nearest class in its MRO that does; empty, as object's: the dict alone
    // (refmodel RefClass.native)
    std::vector<const Str*> native;
    std::size_t name_prefix = 0;                 // a type whose tp_name is dotted: __name__ is what follows the prefix
    bool native_declared = false;
    std::vector<const Str*> native_fields;
    std::unordered_map<const Str*, std::uint32_t> field_index;   // slot fields, native fields, then promoted fields
    bool has_dict = false;
    bool has_weakref = false;                    // room for weak references (RefClass.has_weakref)
    bool dict_without_getset = false;            // _thread._local: a subclass still gets a __dict__ of its own to show
    bool sequence_slots = false;                 // a C type written in Python, with sq_concat and sq_item and no number slots
    bool weak_proxy = false;                     // weakref.ProxyType and its kin: attribute access goes to the target
    std::uint8_t collection_flags = 0;           // a program's class: Py_TPFLAGS_SEQUENCE, Py_TPFLAGS_MAPPING (what match and __flags__ read)
    bool abstract = false;                       // Py_TPFLAGS_IS_ABSTRACT: set by __abstractmethods__, not inherited
    bool mapping_getitem = false;                // a C type written in Python whose __getitem__ is mp_subscript alone: no sq_item
    bool disallow_instantiation = false;         // Py_TPFLAGS_DISALLOW_INSTANTIATION, of a C type written in Python
    bool forwards_attributes = false;            // types.GenericAlias's tp_getattro (getattr_impl), inherited
    bool final_type = false;                     // a built-in type a class cannot derive from (no Py_TPFLAGS_BASETYPE)
    // attrs as a dict, made when a program first asks for a view of __dict__ (class_dict) and kept
    // equal to attrs from then on; its counts are dropped first, so attrs decides when a value dies
    DictObject* dict_view = nullptr;
    std::shared_ptr<SharedKeys> keys;
    ClassObject() : Object(Kind::Class) { flags |= IMMORTAL; }

    std::vector<const Str*> own_slot_names() const {
        std::vector<const Str*> out;
        if (slots) for (const Str* s : *slots) if (s != intern("__dict__") && s != intern("__weakref__")) out.push_back(s);
        return out;
    }
    // lookup along the MRO: (found, owner) or nullopt
    std::optional<std::pair<Obj, ClassObject*>> lookup(const Str* n) const {
        for (ClassObject* c : mro)
            if (const Obj* v = c->attrs.find(n)) return std::pair{*v, c};
        return std::nullopt;
    }
    bool has(const char* n) const { return lookup(intern(n)).has_value(); }
    void bump() {
        version = versions().issue();
        for (ClassObject* s : subclasses) s->bump();
    }
    // type_setattro: the new value stored and the class modified before the old one is released
    // RefClass.set_mro: a metaclass's mro(): what every lookup walks from now on, a new version as for an attribute
    void set_mro(std::vector<ClassObject*> m) {
        mro = std::move(m);
        version = versions().issue();
    }
    void set_attr(const Str* n, Obj v) {
        incref(v);
        Obj old = attrs.set(n, v);
        bump();
        if (dict_view != nullptr) dict_store(dict_view, Obj::of(n), v);
        decref(old);
    }
    void del_attr(const Str* n) {
        if (!attrs.contains(n)) throw AttributeError(n->text);
        Obj old = attrs.pop(n);
        bump();
        if (dict_view != nullptr) decref(dict_pop(dict_view, Obj::of(n)));
        decref(old);
    }
    void unregister() {
        for (ClassObject* b : bases) std::erase(b->subclasses, this);
        std::erase(heap().classes, this);
    }
    // The class dies: it leaves the live classes, then releases its attributes in order.
    void dispose() {
        unregister();
        for (auto& [k, v] : attrs.take_all()) decref(v);
        if (dict_view != nullptr) decref(Obj::of(std::exchange(dict_view, nullptr)));
    }
};

// the builtin classes of the objects this header makes: immortal, no attributes
inline ClassObject* builtin_class(const char* name) {
    static std::unordered_map<std::string, std::unique_ptr<ClassObject>> made;
    auto& c = made[name];
    if (!c) {
        c = std::make_unique<ClassObject>();
        c->name = name;
        c->qualname = name;                      // a built-in type's __qualname__ is its name
        c->mro = {c.get()};
    }
    return c.get();
}
inline DictObject::DictObject() : Object(Kind::Dict) { cls = builtin_class("dict"); }
inline Function::Function(std::function<Obj(std::span<const Obj>)> f) : Object(Kind::Function), fn(std::move(f)) {
    cls = builtin_class("function");
}
inline SlotDescriptor::SlotDescriptor(const Str* n) : Object(Kind::SlotDescriptor), name(n) {
    cls = builtin_class("member_descriptor");
}
inline Marker::Marker(std::string t) : Object(Kind::Marker), text(std::move(t)) { cls = builtin_class("marker"); }

// C3 linearisation (the algorithm CPython uses)
inline std::vector<ClassObject*> c3(ClassObject* cls) {
    std::vector<std::vector<ClassObject*>> seqs{{cls}};
    for (ClassObject* b : cls->bases) seqs.push_back(b->mro);
    seqs.push_back(cls->bases);
    std::vector<ClassObject*> out;
    for (;;) {
        std::erase_if(seqs, [](const auto& s) { return s.empty(); });
        if (seqs.empty()) return out;
        ClassObject* head = nullptr;
        for (const auto& s : seqs) {
            bool in_tail = std::any_of(seqs.begin(), seqs.end(), [&](const auto& t) {
                return std::find(t.begin() + 1, t.end(), s.front()) != t.end();
            });
            if (!in_tail) { head = s.front(); break; }
        }
        if (head == nullptr) throw TypeError("inconsistent MRO");
        out.push_back(head);
        for (auto& s : seqs) if (!s.empty() && s.front() == head) s.erase(s.begin());
    }
}

struct ClassSpec {
    std::string name;
    std::vector<ClassObject*> bases = {};
    std::optional<std::vector<std::string>> slots = std::nullopt;
    std::vector<std::string> promoted = {};
    std::vector<std::pair<std::string, Obj>> attrs = {};
    std::vector<std::string> static_attributes = {};
    std::optional<std::vector<std::string>> native = std::nullopt;   // a built-in type's C fields (RefClass native)
};

// RefClass.__init__
inline ClassObject* make_class(const ClassSpec& spec) {
    auto* c = new ClassObject();
    c->cls = builtin_class("type");
    c->name = spec.name;
    c->qualname = spec.name;
    c->bases = spec.bases;
    c->mro = c3(c);
    for (auto& [k, v] : spec.attrs) {
        incref(v);
        c->attrs.set(intern(k), v);
    }
    c->version = versions().issue();
    for (ClassObject* b : c->bases) b->subclasses.push_back(c);
    if (spec.slots) {
        c->slots.emplace();
        for (const auto& s : *spec.slots) c->slots->push_back(intern(s));
    }
    for (const auto& p : spec.promoted) c->promoted.push_back(intern(p));
    bool own_dict = !spec.slots || std::find(spec.slots->begin(), spec.slots->end(), "__dict__") != spec.slots->end();
    c->has_dict = own_dict || std::any_of(c->bases.begin(), c->bases.end(), [](ClassObject* b) { return b->has_dict; });
    bool own_weak = !spec.slots || std::find(spec.slots->begin(), spec.slots->end(), "__weakref__") != spec.slots->end();
    c->has_weakref = own_weak || std::any_of(c->bases.begin(), c->bases.end(), [](ClassObject* b) { return b->has_weakref; });
    c->forwards_attributes = std::any_of(c->bases.begin(), c->bases.end(), [](ClassObject* b) { return b->forwards_attributes; });
    {
        auto own = c->own_slot_names();
        for (const Str* s : own)
            if (c->attrs.contains(s)) throw ModelError("'" + s->text + "' in __slots__ conflicts with class variable");
        // type_new_slots sorts them, and tp_members' order is the class dict's (code points: UTF-8's order)
        std::sort(own.begin(), own.end(), [](const Str* x, const Str* y) { return x->text < y->text; });
        for (const Str* s : own) {
            auto* d = new SlotDescriptor(s);
            d->owner = c;
            incref(d);
            c->attrs.set(s, Obj::of(d));
        }
    }
    auto add_unique = [](std::vector<const Str*>& out, const Str* n) {
        if (std::find(out.begin(), out.end(), n) == out.end()) out.push_back(n);
    };
    for (auto it = c->mro.rbegin(); it != c->mro.rend(); ++it)
        for (const Str* s : (*it)->own_slot_names()) add_unique(c->slot_fields, s);
    for (const Str* p : c->promoted)
        if (std::find(c->slot_fields.begin(), c->slot_fields.end(), p) != c->slot_fields.end())
            throw ModelError("promoted field '" + p->text + "' collides with a slot");
    for (auto it = c->mro.rbegin(); it != c->mro.rend(); ++it)
        for (const Str* p : (*it)->promoted) add_unique(c->promoted_fields, p);
    if (spec.native) {
        c->native.clear();
        for (const auto& n : *spec.native) c->native.push_back(intern(n));
        c->native_declared = true;
    } else {
        for (std::size_t k = 1; k < c->mro.size(); ++k)
            if (c->mro[k]->native_declared) {
                c->native = c->mro[k]->native;
                break;
            }
    }
    for (const Str* n : c->native)
        if (n != intern("__dict__")) {
            auto in = [n](const std::vector<const Str*>& v) { return std::find(v.begin(), v.end(), n) != v.end(); };
            if (in(c->slot_fields) || in(c->promoted_fields)) throw ModelError("'" + n->text + "' is a field of a built-in base");
            c->native_fields.push_back(n);
        }
    std::uint32_t i = 0;
    for (const Str* s : c->slot_fields) c->field_index[s] = i++;
    for (const Str* n : c->native_fields) c->field_index[n] = i++;
    for (const Str* p : c->promoted_fields) c->field_index[p] = i++;
    c->keys = std::make_shared<SharedKeys>();
    std::vector<std::string> statics = spec.static_attributes;
    std::sort(statics.begin(), statics.end());
    for (const auto& n : statics) c->keys->note(intern(n));
    heap().classes.push_back(c);
    return c;
}

// ---- instances (refmodel RefObject) ----
struct Instance : Object {
    std::vector<Obj> fields;                    // by the class's field_index; Unset: absent
    DictObject* dict = nullptr;                 // before exposure: the names not promoted; after: the __dict__
    std::vector<const Str*> order;              // first-assignment order of __dict__-backed names (insertion_order)
    std::int64_t tag = -1;                      // tests log the deaths of tagged objects
    explicit Instance(ClassObject* c) : Object(Kind::Instance) {
        cls = c;
        fields.assign(c->field_index.size(), Obj{});
    }
    bool exposed() const { return (flags & DICT_EXPOSED) != 0; }
    Obj& field(const Str* n) { return fields[cls->field_index.at(n)]; }
    bool has_field(const Str* n) const { return cls->field_index.contains(n); }
};
inline Instance* new_instance(ClassObject* c) { return new Instance(c); }

// An instance of a program's subclass of dict (decision 2026-11-03: a subclass of a built-in type is
// that type's object): a dict, its entries its own, with the subclass's attribute storage beside them,
// as Instance has it (refmodel RefObject with a payload). The attribute machinery below takes either.
struct DictInstance : DictObject {
    std::vector<Obj> fields;
    DictObject* dict = nullptr;
    std::vector<const Str*> order;
    std::int64_t tag = -1;
    explicit DictInstance(ClassObject* c) {
        cls = c;
        flags |= HAS_ATTRIBUTES;
        fields.assign(c->field_index.size(), Obj{});
    }
    bool exposed() const { return (flags & DICT_EXPOSED) != 0; }
    Obj& field(const Str* n) { return fields[cls->field_index.at(n)]; }
    bool has_field(const Str* n) const { return cls->field_index.contains(n); }
};
// An instance of a program's subclass of int: its value and the subclass's attribute storage. The
// value is an immediate's, or, beyond them, limbs and a sign (value is then 0; bigint.cpp reads them).
// It is no object, so it dies as an instance does (decision 2026-11-03).
struct IntInstance : Object {
    std::int64_t value;
    std::vector<std::uint64_t> limbs;
    bool negative = false;
    std::vector<Obj> fields;
    DictObject* dict = nullptr;
    std::vector<const Str*> order;
    std::int64_t tag = -1;
    IntInstance(ClassObject* c, std::int64_t v) : Object(Kind::IntInstance), value(v) {
        cls = c;
        flags |= HAS_ATTRIBUTES;
        fields.assign(c->field_index.size(), Obj{});
    }
    bool exposed() const { return (flags & DICT_EXPOSED) != 0; }
    Obj& field(const Str* n) { return fields[cls->field_index.at(n)]; }
    bool has_field(const Str* n) const { return cls->field_index.contains(n); }
};
// A float, and an instance of a program's subclass of float: as IntInstance, with a value that is the same
// field in both.
struct Float : Object {
    double value;
    explicit Float(double v) : Object(Kind::Float), value(v) {}
};
struct FloatInstance : Float {
    std::vector<Obj> fields;
    DictObject* dict = nullptr;
    std::vector<const Str*> order;
    std::int64_t tag = -1;
    FloatInstance(ClassObject* c, double v) : Float(v) {
        kind = Kind::FloatInstance;
        cls = c;
        flags |= HAS_ATTRIBUTES;
        fields.assign(c->field_index.size(), Obj{});
    }
    bool exposed() const { return (flags & DICT_EXPOSED) != 0; }
    Obj& field(const Str* n) { return fields[cls->field_index.at(n)]; }
    bool has_field(const Str* n) const { return cls->field_index.contains(n); }
};
// A tuple, and an instance of a program's subclass of tuple. Its kind stays Tuple, as PyTuple_Check says
// yes of it; what only an exact tuple does asks is_exact_tuple, and what a subclass may override asks first.
struct Tuple : Object {                          // owns one count of each item
    std::vector<Obj> items;
    Tuple();
};
struct TupleInstance : Tuple {
    std::vector<Obj> fields;
    DictObject* dict = nullptr;
    std::vector<const Str*> order;
    std::int64_t tag = -1;
    explicit TupleInstance(ClassObject* c) {
        cls = c;
        flags |= HAS_ATTRIBUTES;
        fields.assign(c->field_index.size(), Obj{});
    }
    bool exposed() const { return (flags & DICT_EXPOSED) != 0; }
    Obj& field(const Str* n) { return fields[cls->field_index.at(n)]; }
    bool has_field(const Str* n) const { return cls->field_index.contains(n); }
};
// An instance of a program's subclass of str: kind stays Str, as PyUnicode_Check says yes of it, and the attribute storage is beside the
// text. What reads the text needs no change; what only an exact str does asks is_exact_str; what a subclass may override asks first.
struct StrInstance : Str {
    std::vector<Obj> fields;
    DictObject* dict = nullptr;
    std::vector<const Str*> order;
    std::int64_t tag = -1;
    StrInstance(ClassObject* c, std::string text) : Str(std::move(text), false) {
        cls = c;
        flags |= HAS_ATTRIBUTES;
        fields.assign(c->field_index.size(), Obj{});
    }
    bool exposed() const { return (flags & DICT_EXPOSED) != 0; }
    Obj& field(const Str* n) { return fields[cls->field_index.at(n)]; }
    bool has_field(const Str* n) const { return cls->field_index.contains(n); }
};
// A complex, and an instance of a program's subclass of complex: as Float and FloatInstance.
struct Complex : Object {
    double real, imag;
    Complex(double r, double i) : Object(Kind::Complex), real(r), imag(i) {}
};
struct ComplexInstance : Complex {
    std::vector<Obj> fields;
    DictObject* dict = nullptr;
    std::vector<const Str*> order;
    std::int64_t tag = -1;
    ComplexInstance(ClassObject* c, double r, double i) : Complex(r, i) {
        kind = Kind::ComplexInstance;
        cls = c;
        flags |= HAS_ATTRIBUTES;
        fields.assign(c->field_index.size(), Obj{});
    }
    bool exposed() const { return (flags & DICT_EXPOSED) != 0; }
    Obj& field(const Str* n) { return fields[cls->field_index.at(n)]; }
    bool has_field(const Str* n) const { return cls->field_index.contains(n); }
};
inline bool has_attributes(const Object* o) { return (o->flags & HAS_ATTRIBUTES) != 0; }

inline bool is_instance(Obj v) { return v.is_object() && v.object()->kind == Kind::Instance; }
// Python's rule: an object whose type has __get__ is a descriptor (a function, a property, an
// instance of a class with __get__); with __set__ or __delete__ too, a data descriptor.
inline bool is_descriptor(Obj found) {
    return found.is_object() && found.object()->cls != nullptr && found.object()->cls->has("__get__");
}
inline bool is_data_descriptor(Obj found) {
    if (found.is_object() && found.object()->kind == Kind::SlotDescriptor) return true;
    return found.is_object() && found.object()->cls != nullptr &&
           (found.object()->cls->has("__set__") || found.object()->cls->has("__delete__"));
}
// A finaliser written in Python is called by the runtime, which reports what it raises as
// unraisable: a death never propagates an exception (review 2026-11-03, A9-4).
using FinalizerHook = void (*)(Obj fn, Obj self);
inline FinalizerHook& finalizer_hook() {
    static FinalizerHook hook = nullptr;
    return hook;
}

// Whether the exception being handled is an AttributeError the runtime raised for Python code
// (a property or a __get__ written in Python), so that __getattr__ is tried as for this header's
// own AttributeError. Called inside a catch block.
using AttributeErrorHook = bool (*)();
inline AttributeErrorHook& attribute_error_hook() {
    static AttributeErrorHook hook = nullptr;
    return hook;
}

// A name nothing in the class or the instance provides. The runtime refuses it (bella::NotImplemented)
// when a built-in class in the MRO has it in CPython and the runtime lacks it yet: CPython would
// have found it, and neither __getattr__ nor AttributeError is the answer. Without the runtime,
// this header's classes have no built-in names.
using MissingNameHook = void (*)(Obj obj, const Str* name);
inline MissingNameHook& missing_name_hook() {
    static MissingNameHook hook = nullptr;
    return hook;
}

// How slot_tp_getattr_hook calls the __getattr__ it found (CPython's call_attribute), for the
// runtime's kinds of callable: a function or method descriptor with the object and the name,
// another descriptor bound first and called with the name, anything else with the name alone.
// Returns a new reference. Without it, this header's functions and instances are all there is.
using CallAttributeHook = Obj (*)(Obj hook, Obj obj, Obj name);
inline CallAttributeHook& call_attribute_hook() {
    static CallAttributeHook hook = nullptr;
    return hook;
}

// The runtime (bella/runtime.hpp) calls every other kind of callable; returns a new reference.
using CallHook = Obj (*)(Obj fn, std::span<const Obj> args);
inline CallHook& call_hook() {
    static CallHook hook = nullptr;
    return hook;
}
inline Obj call(Obj fn, std::initializer_list<Obj> args) {
    if (fn.is_object() && fn.object()->kind == Kind::Function) {
        std::vector<Obj> a(args);
        return static_cast<Function*>(fn.object())->fn(a);
    }
    if (call_hook() != nullptr) return call_hook()(fn, std::span<const Obj>(args.begin(), args.size()));
    throw TypeError("object is not callable");
}

// ---- inline caches (refmodel CacheEntry, Site) ----
enum class Plan : std::uint8_t {
    DataDescriptor, Slot, Field, InstanceDict, ClassAttr, NonDataDescriptor, GetAttrHook, UncachedValue, Raise
};
struct CacheEntry {                // immutable once installed
    std::uint64_t version;         // names the class and its state: no class pointer is kept
    const Str* name;
    Plan kind;
    Obj found;                     // BORROWED: the class owns it while version matches (RL-20)
    std::uint64_t found_version;   // the version of found's class at plan time; 0: found cannot change status
    std::uintptr_t cls_hint;       // the class's address as a number: install replaces its older entries; never read
};
struct Site {
    static constexpr std::size_t N = 4;
    std::vector<CacheEntry> entries;
    bool megamorphic = false;
    std::uint64_t hits = 0, misses = 0;
    Site() { heap().sites.push_back(this); }
    ~Site() { std::erase(heap().sites, this); }
    Site(const Site&) = delete;
    Site& operator=(const Site&) = delete;
    const CacheEntry* find(std::uint64_t version, const Str* name) const {
        if (version == NO_VERSION) return nullptr;
        for (const auto& e : entries) if (e.version == version && e.name == name) return &e;
        return nullptr;
    }
    void install(const CacheEntry& e) {
        if (megamorphic) return;
        std::erase_if(entries, [&](const CacheEntry& x) { return x.cls_hint == e.cls_hint && x.name == e.name; });
        if (entries.size() >= N) {
            megamorphic = true;
            entries.clear();
            return;
        }
        entries.push_back(e);
    }
};

// The operation a lookup selects, decided without running user code (refmodel _Plan).
struct LookupPlan {
    Plan kind;
    Obj found;                     // what it calls or returns
    Obj value;                     // the value it reads without running user code
    Obj hook;                      // the __getattr__ fallback, looked up beforehand
    bool operator==(const LookupPlan&) const = default;
};

// ---- the attribute machinery (refmodel Runtime) ----
namespace detail {
// (present, value) for the __dict__-backed storage of a name (never slots)
template <class T>
inline std::pair<bool, Obj> instance_storage(T* obj, const Str* name) {
    if (obj->exposed()) {
        Obj v = dict_find(obj->dict, Obj::of(name));
        return v.is_unset() ? std::pair{false, Obj{}} : std::pair{true, v};
    }
    if (std::find(obj->cls->promoted_fields.begin(), obj->cls->promoted_fields.end(), name) != obj->cls->promoted_fields.end()) {
        Obj v = obj->field(name);
        if (!v.is_unset()) return {true, v};
    }
    if (obj->dict != nullptr)
        if (Obj v = dict_find(obj->dict, Obj::of(name)); !v.is_unset()) return {true, v};
    return {false, Obj{}};
}
template <class T>
inline bool is_promoted(T* obj, const Str* name) {
    const auto& p = obj->cls->promoted_fields;
    return std::find(p.begin(), p.end(), name) != p.end();
}
inline Obj hook_of(ClassObject* c) {
    auto h = c->lookup(intern("__getattr__"));
    return h ? h->first : Obj{};
}
}  // namespace detail

// Python's lookup order; the plan, and the entry to cache (if any)
template <class T>
inline std::pair<LookupPlan, std::optional<CacheEntry>> plan_generic(T* obj, const Str* name) {
    ClassObject* cls = obj->cls;
    std::uint64_t version = cls->version;
    auto hit = cls->lookup(name);
    Obj found = hit ? hit->first : Obj{};
    // an entry that resolves to instance storage still depends on the version of found's class:
    // a non-data descriptor can become a data descriptor through its own class alone
    std::uint64_t found_version = is_instance(found) ? found.object()->cls->version : NO_VERSION;
    bool cacheable = version != NO_VERSION && (found_version != NO_VERSION || !is_instance(found));
    auto entry = [&](Plan k, Obj f = Obj{}) -> std::optional<CacheEntry> {
        if (!cacheable) return std::nullopt;
        return CacheEntry{version, name, k, f, found_version, reinterpret_cast<std::uintptr_t>(cls)};
    };
    Obj hook = detail::hook_of(cls);       // slot_tp_getattr_hook looks __getattr__ up first (C-3-09)
    if (hit && is_data_descriptor(found)) {
        if (found.object()->kind == Kind::SlotDescriptor)
            return {{Plan::Slot, Obj{}, obj->field(name), hook}, entry(Plan::Slot)};
        if (!found.object()->cls->has("__get__")) {
            auto [present, v] = detail::instance_storage(obj, name);
            return {{Plan::UncachedValue, Obj{}, present ? v : found, hook}, std::nullopt};
        }
        return {{Plan::DataDescriptor, found, Obj{}, hook}, entry(Plan::DataDescriptor, found)};
    }
    if (auto [present, v] = detail::instance_storage(obj, name); present) {
        Plan k = (!obj->exposed() && detail::is_promoted(obj, name)) ? Plan::Field : Plan::InstanceDict;
        return {{k, Obj{}, v, hook}, entry(k, found)};
    }
    if (hit) {
        if (is_descriptor(found)) return {{Plan::NonDataDescriptor, found, Obj{}, hook}, entry(Plan::NonDataDescriptor, found)};
        return {{Plan::ClassAttr, found, found, hook}, entry(Plan::ClassAttr, found)};
    }
    if (!hook.is_unset()) return {{Plan::GetAttrHook, hook, Obj{}, Obj{}}, entry(Plan::GetAttrHook, hook)};
    return {{Plan::Raise, Obj{}, Obj{}, Obj{}}, std::nullopt};
}

// The plan the cache alone selects; nullopt when no valid entry applies. Runs no user code.
template <class T>
inline std::optional<LookupPlan> plan_cached(T* obj, const Str* name, const Site& site) {
    ClassObject* cls = obj->cls;
    const CacheEntry* e = site.find(cls->version, name);
    if (e == nullptr) return std::nullopt;
    if (e->found.is_object() && !e->found.object()->alive())
        throw ModelError("a valid entry for '" + name->text + "' reads a dead borrowed found");
    // found's class is read only now, after the version matched: the class still owns found
    if (e->found_version != NO_VERSION && e->found.object()->cls->version != e->found_version) return std::nullopt;
    Obj hook = detail::hook_of(cls);       // covered by the class version
    if ((e->kind == Plan::Slot || e->kind == Plan::Field) && !obj->has_field(name))
        throw ModelError("unsound cache: '" + name->text + "' cached as a field for a layout without it");
    switch (e->kind) {
        case Plan::Slot:
            return LookupPlan{Plan::Slot, Obj{}, obj->field(name), hook};
        case Plan::Field: {
            if (obj->exposed()) return std::nullopt;
            Obj v = obj->field(name);
            if (v.is_unset()) return std::nullopt;
            return LookupPlan{Plan::Field, Obj{}, v, hook};
        }
        case Plan::InstanceDict:
            if (obj->dict != nullptr)
                if (Obj v = dict_find(obj->dict, Obj::of(name)); !v.is_unset()) return LookupPlan{Plan::InstanceDict, Obj{}, v, hook};
            return std::nullopt;
        case Plan::DataDescriptor:
            return LookupPlan{Plan::DataDescriptor, e->found, Obj{}, hook};
        default:
            break;
    }
    // ClassAttr / NonDataDescriptor / GetAttrHook: no instance storage may shadow the name
    if (detail::instance_storage(obj, name).first) return std::nullopt;
    switch (e->kind) {
        case Plan::ClassAttr: return LookupPlan{Plan::ClassAttr, e->found, e->found, hook};
        case Plan::NonDataDescriptor: return LookupPlan{Plan::NonDataDescriptor, e->found, Obj{}, hook};
        case Plan::GetAttrHook: return LookupPlan{Plan::GetAttrHook, e->found, Obj{}, Obj{}};
        default: throw ModelError("unknown cache kind");
    }
}

// Execution: the only place user code runs. Returns a new reference. The plan's objects are owned
// while user code runs, as CPython's lookups take strong references (_PyType_LookupRef): the
// __getattr__ hook from the lookup until the operation ends; a descriptor, and its __get__, while
// __get__ runs (released as it returns or raises, before the hook is tried). Cache entries stay
// borrowed: these are the operation's own references (review 2026-11-02, A8-1).
template <class T>
inline Ref call_attribute(Obj hook, T* obj, const Str* name) {
    if (call_attribute_hook() != nullptr) return Ref::steal(call_attribute_hook()(hook, Obj::of(obj), Obj::of(name)));
    if (hook.is_object() && hook.object()->kind == Kind::Instance) {
        ClassObject* hc = hook.object()->cls;
        if (auto get = hc->lookup(intern("__get__"))) {
            Ref bound = Ref::steal(call(get->first, {hook, Obj::of(obj), Obj::of(obj->cls)}));
            return Ref::steal(call(bound.get(), {Obj::of(name)}));
        }
        if (auto c = hc->lookup(intern("__call__"))) return Ref::steal(call(c->first, {hook, Obj::of(name)}));
        throw TypeError("'" + hc->name + "' object is not callable");
    }
    return Ref::steal(call(hook, {Obj::of(obj), Obj::of(name)}));
}

template <class T>
inline Ref execute(const LookupPlan& plan, T* obj, const Str* name) {
    Ref hook = Ref::share(plan.hook);
    try {
        switch (plan.kind) {
            case Plan::Raise:
                if (missing_name_hook() != nullptr) missing_name_hook()(Obj::of(obj), name);
                throw AttributeError(name->text);
            case Plan::GetAttrHook: {
                if (missing_name_hook() != nullptr) missing_name_hook()(Obj::of(obj), name);
                Ref fn = Ref::share(plan.found);
                return call_attribute(fn.get(), obj, name);
            }
            case Plan::DataDescriptor:
            case Plan::NonDataDescriptor: {
                Ref desc = Ref::share(plan.found);
                Ref get = Ref::share(plan.found.object()->cls->lookup(intern("__get__"))->first);
                return Ref::steal(call(get.get(), {desc.get(), Obj::of(obj), Obj::of(obj->cls)}));
            }
            case Plan::Slot:
                if (plan.value.is_unset()) throw AttributeError(name->text);
                return Ref::share(plan.value);
            default:
                return Ref::share(plan.value);
        }
    } catch (const AttributeError&) {
        if (hook.get().is_unset()) throw;
    } catch (...) {
        if (hook.get().is_unset() || attribute_error_hook() == nullptr || !attribute_error_hook()()) throw;
    }
    // the AttributeError is dropped before the hook runs, as slot_tp_getattr_hook's PyErr_Clear
    // does: its traceback, and what that holds, die first
    return call_attribute(hook.get(), obj, name);
}

template <class T>
inline Ref getattr(T* obj, const Str* name, Site* site = nullptr) {
    if (site != nullptr) {
        if (auto cached = plan_cached(obj, name, *site)) {
            ++site->hits;
            if (heap().checking) {
                auto [plan, _] = plan_generic(obj, name);
                if (!(plan == *cached)) throw ModelError("unsound cache: '" + name->text + "' cached plan differs from the generic plan");
            }
            return execute(*cached, obj, name);
        }
        auto [plan, entry] = plan_generic(obj, name);
        if (plan.kind != Plan::Raise) {       // a lookup that finds nothing is not a cache event
            ++site->misses;
            if (entry) site->install(*entry);
        }
        return execute(plan, obj, name);
    }
    return execute(plan_generic(obj, name).first, obj, name);
}

// Every store keeps the new value before it releases the old one.
template <class T>
inline void setattr(T* obj, const Str* name, Obj value) {
    ClassObject* cls = obj->cls;
    if (auto hit = cls->lookup(name)) {
        Obj found = hit->first;
        if (found.is_object() && found.object()->kind == Kind::SlotDescriptor) {
            incref(value);
            Obj old = std::exchange(obj->field(name), value);
            decref(old);
            return;
        }
        if (is_data_descriptor(found)) {
            auto setter = found.object()->cls->lookup(intern("__set__"));
            if (!setter) throw AttributeError("__set__");            // a data descriptor with only __delete__
            Ref desc = Ref::share(found);                            // owned while __set__ runs
            Ref fn = Ref::share(setter->first);
            decref(call(fn.get(), {desc.get(), Obj::of(obj), value}));
            return;
        }
    }
    if (obj->exposed()) {                        // a new name joins a split dict's keys (dict_put)
        dict_store(obj->dict, Obj::of(name), value);
        return;
    }
    if (detail::is_promoted(obj, name)) {
        Obj& slot = obj->field(name);
        if (slot.is_unset()) {
            obj->order.push_back(name);
            cls->keys->note(name);
        }
        incref(value);
        Obj old = std::exchange(slot, value);
        decref(old);
        return;
    }
    if (!cls->has_dict)
        throw AttributeError("'" + cls->name + "' object has no attribute '" + name->text + "' and no __dict__ for setting new attributes");
    if (obj->dict == nullptr) {
        obj->dict = new DictObject();
        obj->dict->split = cls->keys;
        incref(obj->dict);
    }
    if (dict_find(obj->dict, Obj::of(name)).is_unset()) {
        obj->order.push_back(name);
        cls->keys->note(name);
    }
    dict_store(obj->dict, Obj::of(name), value);
}

template <class T>
inline void delattr(T* obj, const Str* name) {
    ClassObject* cls = obj->cls;
    if (auto hit = cls->lookup(name)) {
        Obj found = hit->first;
        if (found.is_object() && found.object()->kind == Kind::SlotDescriptor) {
            Obj& slot = obj->field(name);
            if (slot.is_unset()) throw AttributeError(name->text);
            decref(std::exchange(slot, Obj{}));
            return;
        }
        if (is_data_descriptor(found)) {
            auto deleter = found.object()->cls->lookup(intern("__delete__"));
            if (!deleter) throw AttributeError("__delete__");
            Ref desc = Ref::share(found);                            // owned while __delete__ runs
            Ref fn = Ref::share(deleter->first);
            decref(call(fn.get(), {desc.get(), Obj::of(obj)}));
            return;
        }
    }
    // a delete through the object's inline values inserts the name into the shared keys before it finds the attribute missing
    // (_PyObject_StoreInstanceAttribute); once the dict is detached from the object (obj.__dict__ = d, _PyObject_SetManagedDict), a
    // delete goes through the dict and a missing name is just missing (refmodel Runtime.delattr)
    if (obj->exposed()) {
        if (obj->dict->embedded == obj) obj->dict->note_key(name);
        Obj old = dict_pop(obj->dict, Obj::of(name));
        if (old.is_unset()) throw AttributeError(name->text);
        decref(old);
        return;
    }
    if (cls->has_dict) cls->keys->note(name);
    if (detail::is_promoted(obj, name) && !obj->field(name).is_unset()) {
        Obj old = std::exchange(obj->field(name), Obj{});
        std::erase(obj->order, name);
        decref(old);
        return;
    }
    if (obj->dict != nullptr && !dict_find(obj->dict, Obj::of(name)).is_unset()) {
        Obj old = dict_pop(obj->dict, Obj::of(name));
        std::erase(obj->order, name);
        decref(old);
        return;
    }
    if (!cls->has_dict)
        throw AttributeError("'" + cls->name + "' object has no attribute '" + name->text + "' and no __dict__ for setting new attributes");
    throw AttributeError(name->text);
}

// vars(obj) / obj.__dict__: the promoted fields migrate once; stable identity afterwards. The dict
// is an object of its own from here on (one count held by the object), split: it shares the
// class's keys. Returns a new reference.
template <class T>
inline Ref expose_dict(T* obj) {
    ClassObject* cls = obj->cls;
    if (!cls->has_dict) throw AttributeError("'" + cls->name + "' object has no attribute '__dict__'");
    if (obj->exposed()) return Ref::share(Obj::of(obj->dict));
    auto* d = new DictObject();
    for (const Str* name : obj->order) {         // the references move: no count changes
        Obj v = detail::is_promoted(obj, name) ? std::exchange(obj->field(name), Obj{}) : dict_pop(obj->dict, Obj::of(name));
        dict_put(d, Obj::of(name), detail::key_hash(Obj::of(name)), v);
    }
    d->split = cls->keys;                        // split from here on, as the class's keys
    d->embedded = obj;                           // its values are the object's while it lives
    if (obj->dict != nullptr) decref(obj->dict); // the overflow dict, emptied
    incref(d);
    obj->dict = d;
    obj->order.clear();
    obj->flags |= DICT_EXPOSED;
    return Ref::share(Obj::of(d));
}

// obj.__dict__ = d: exposes first, then installs d (which may be shared); the old dict is released
// after the new one is held.
template <class T>
inline void set_dict(T* obj, DictObject* d) {
    if (!obj->cls->has_dict) throw AttributeError("'" + obj->cls->name + "' object has no attribute '__dict__'");
    expose_dict(obj);
    DictObject* old = obj->dict;
    if (old->embedded == obj) old->embedded = nullptr;   // its values are detached from obj
    incref(d);
    obj->dict = d;
    decref(old);
}

// ---- deaths ----
namespace detail {
// RL-20: an entry a live class still validates never names an object that dies
inline void check_not_named(Object* o) {
    for (Site* s : heap().sites)
        for (const CacheEntry& e : s->entries) {
            if (!(e.found.is_object() && e.found.object() == o)) continue;
            for (ClassObject* c : heap().classes)
                if (c->version == e.version)
                    throw ModelError("a valid cache entry for '" + e.name->text + "' names an object that dies");
        }
}
inline void bury(Object* o) {
    if (heap().quarantine) heap().graveyard.push_back(o);
    else {
        switch (o->kind) {
            case Kind::Instance: delete static_cast<Instance*>(o); break;
            case Kind::Dict:
                if (has_attributes(o)) delete static_cast<DictInstance*>(o);
                else delete static_cast<DictObject*>(o);
                break;
            case Kind::IntInstance: delete static_cast<IntInstance*>(o); break;
            case Kind::FloatInstance: delete static_cast<FloatInstance*>(o); break;
            case Kind::ComplexInstance: delete static_cast<ComplexInstance*>(o); break;
            case Kind::Str: delete static_cast<StrInstance*>(o); break;   // an exact str's death is its destroyer's
            case Kind::Tuple: delete static_cast<TupleInstance*>(o); break;   // an exact tuple's death is its destroyer's
            case Kind::Function: delete static_cast<Function*>(o); break;
            case Kind::SlotDescriptor: delete static_cast<SlotDescriptor*>(o); break;
            case Kind::Marker: delete static_cast<Marker*>(o); break;
            default: break;          // strings and classes are not freed here
        }
    }
}
}  // namespace detail

// Frees what the quarantine kept (between test worlds, when no stale entry can be read any more).
inline void empty_graveyard() {
    auto dead = std::move(heap().graveyard);
    heap().graveyard.clear();
    bool saved = std::exchange(heap().quarantine, false);
    for (Object* o : dead) detail::bury(o);
    heap().quarantine = saved;
}

// subtype_dealloc's order: the finaliser, the __slots__ of the most-derived class first (each
// class's sorted by name, as type_new stores them), then the __dict__-backed values in the class's shared-keys
// order, or the dict's release once it is an object of its own.
namespace detail {
// A dying instance's __dict__-backed values in the class's key order, or the dict's own release
// once it is an object of its own (RefObject._release_dict).
template <class T>
inline void release_instance_dict(T* obj) {
    if (obj->exposed()) {
        DictObject* d = std::exchange(obj->dict, nullptr);
        if (d->embedded == obj) d->embedded = nullptr;   // its values are detached from the dead object
        decref(d);
    } else {
        std::vector<std::pair<const Str*, Obj>> held;
        std::vector<Obj> keys;
        for (const Str* p : obj->cls->promoted_fields)
            if (!obj->field(p).is_unset()) held.emplace_back(p, std::exchange(obj->field(p), Obj{}));
        if (obj->dict != nullptr) {
            for (auto& [k, v] : dict_take_all(obj->dict)) {
                held.emplace_back(static_cast<const Str*>(k.object()), v);
                keys.push_back(k);
            }
            DictObject* d = std::exchange(obj->dict, nullptr);
            decref(d);
        }
        // the class's key order, then any name the keys could not take, in insertion order
        std::vector<std::pair<const Str*, Obj>> ranked;
        if (obj->cls->keys)               // a C++ type's instance (object()) shares no keys
            for (const Str* k : obj->cls->keys->names)
                for (auto& [n, v] : held) if (n == k && !v.is_unset()) { ranked.emplace_back(n, v); v = Obj{}; }
        for (const Str* n : obj->order)
            for (auto& [m, v] : held) if (m == n && !v.is_unset()) { ranked.emplace_back(m, v); v = Obj{}; }
        for (auto& [n, v] : ranked) decref(v);
        for (Obj k : keys) decref(k);
    }
}
}  // namespace detail

// ---- weak references ----
inline FinalizerHook& weakref_callback_hook() {  // handle_callback: runs it, and reports what it raises
    static FinalizerHook hook = nullptr;
    return hook;
}
inline std::vector<WeakRecord*>* weak_list(const Object* target) {
    if (!(target->flags & HAS_WEAKREFS)) return nullptr;
    auto it = heap().weak_lists.find(target);
    return it == heap().weak_lists.end() ? nullptr : &it->second;
}
inline WeakRecord* weak_record(const Object* holder) {
    if (!(holder->flags & WEAK_REFERENCE)) return nullptr;
    auto it = heap().weak_records.find(holder);
    return it == heap().weak_records.end() ? nullptr : it->second;
}
// the shared reference of that kind, if the object has one (get_basic_refs)
inline Object* weak_basic(const Object* target, WeakKind kind) {
    auto* list = weak_list(target);
    if (list == nullptr) return nullptr;
    for (WeakRecord* r : *list) {
        if (r->kind == kind) return r->holder;
        if (r->kind == WeakKind::Other) break;
    }
    return nullptr;
}
// insert_weakref: the basic reference at the head, the basic proxy after it, any other after those
inline void weak_link(Object* holder, Object* target, Obj callback, WeakKind kind) {
    auto* record = new WeakRecord{holder, target, reinterpret_cast<std::uintptr_t>(callback.is_unset() ? nullptr : callback.object()), kind};
    if (!callback.is_unset()) incref(callback);
    holder->flags |= WEAK_REFERENCE;
    target->flags |= HAS_WEAKREFS;
    heap().weak_records[holder] = record;
    auto& list = heap().weak_lists[target];
    auto at = list.begin();
    if (kind != WeakKind::BasicRef) {
        while (at != list.end() && (*at)->kind == WeakKind::BasicRef) ++at;
        if (kind == WeakKind::Other)
            while (at != list.end() && (*at)->kind == WeakKind::BasicProxy) ++at;
    }
    list.insert(at, record);
}
inline void weak_unlink(WeakRecord* r) {          // clear_weakref_lock_held: out of its target's list
    if (r->target == nullptr) return;
    auto it = heap().weak_lists.find(r->target);
    if (it != heap().weak_lists.end()) {
        std::erase(it->second, r);
        if (it->second.empty()) {
            r->target->flags &= static_cast<std::uint16_t>(~HAS_WEAKREFS);
            heap().weak_lists.erase(it);
        }
    }
    r->target = nullptr;
}
// weakref_dealloc: a reference that dies leaves the list, and its callback is released, never called
inline void weak_holder_dies(Object* holder) {
    auto it = heap().weak_records.find(holder);
    if (it == heap().weak_records.end()) return;
    WeakRecord* r = it->second;
    heap().weak_records.erase(it);
    weak_unlink(r);
    std::uintptr_t callback = std::exchange(r->callback, 0);
    delete r;
    if (callback != 0) decref(Obj::of(reinterpret_cast<const Object*>(callback)));
}
// PyObject_ClearWeakRefs (RefObject.clear_weakrefs): the basic references with no callback; each of
// the rest cleared and held, unless it is dying; the callbacks in list order; the holds last to first
inline void clear_weakrefs(Object* target) {
    std::vector<WeakRecord*> list = std::move(heap().weak_lists[target]);
    heap().weak_lists.erase(target);
    target->flags &= static_cast<std::uint16_t>(~HAS_WEAKREFS);
    std::vector<std::pair<Object*, std::uintptr_t>> pending;
    for (WeakRecord* r : list) {
        r->target = nullptr;
        if (r->kind != WeakKind::Other) continue;
        std::uintptr_t callback = std::exchange(r->callback, 0);
        if (r->holder->refs > 0) {
            incref(r->holder);
            pending.emplace_back(r->holder, callback);
        } else if (callback != 0) {
            decref(Obj::of(reinterpret_cast<const Object*>(callback)));
        }
    }
    for (auto& [holder, callback] : pending) {
        if (callback == 0) continue;
        Obj fn = Obj::of(reinterpret_cast<const Object*>(callback));
        if (weakref_callback_hook() != nullptr) weakref_callback_hook()(fn, Obj::of(holder));
        else decref(call(fn, {Obj::of(holder)}));
    }
    for (auto it = pending.rbegin(); it != pending.rend(); ++it) {   // the C's tuple dies: its items last to first
        if (it->second != 0) decref(Obj::of(reinterpret_cast<const Object*>(it->second)));
        decref(it->first);
    }
}

namespace detail {
// subtype_dealloc's part for an object with a class's attribute storage: the finaliser, the slots
// of the most-derived class first, then the built-in base's clear function (its fields, the dict
// at its place); a built-in kind's own data is the caller's to release after (RefObject.dealloc)
// The collector's finalize_garbage for one object (RefObject.finalize): alive and named, it runs the
// finaliser now, and its death will not run it again (PEP 442).
template <class T>
inline void finalize_once(T* obj) {
    if (obj->flags & FINALIZED) return;
    obj->flags |= FINALIZED;
    if (auto fin = obj->cls->lookup(intern("__del__"))) {
        Ref fn = Ref::share(fin->first);
        if (finalizer_hook() != nullptr) finalizer_hook()(fn.get(), Obj::of(obj));
        else decref(call(fn.get(), {Obj::of(obj)}));
    }
}

// Returns false when the finaliser left a count: the object lives on, its finaliser spent (PEP 442).
template <class T>
inline bool release_attributes(T* obj) {
    auto fin = (obj->flags & FINALIZED) ? std::nullopt : obj->cls->lookup(intern("__del__"));
    obj->flags |= FINALIZED;
    if (fin) {
        obj->refs = 1;                          // held by the finaliser's call, so it cannot die again
        Ref fn = Ref::share(fin->first);
        if (finalizer_hook() != nullptr) finalizer_hook()(fn.get(), Obj::of(obj));
        else decref(call(fn.get(), {Obj::of(obj)}));
        fn = Ref{};
        if (--obj->refs != 0) return false;
    }
    obj->flags |= DEAD;
    if (heap().on_death) heap().on_death(obj);
    if (heap().checking) detail::check_not_named(obj);
    if (obj->flags & HAS_WEAKREFS) clear_weakrefs(obj);
    for (ClassObject* c : obj->cls->mro) {
        // each class's slots sorted by name, as CPython sorts them when it makes the class
        auto names = c->own_slot_names();
        std::sort(names.begin(), names.end(), [](const Str* a, const Str* b) { return a->text < b->text; });
        for (const Str* s : names) decref(std::exchange(obj->field(s), Obj{}));
    }
    // the built-in base's clear function: its fields, the dict at its place (RefObject.dealloc)
    if (obj->cls->native.empty()) detail::release_instance_dict(obj);
    for (const Str* n : obj->cls->native) {
        if (n == intern("__dict__")) detail::release_instance_dict(obj);
        else decref(std::exchange(obj->field(n), Obj{}));
    }
    return true;
}
}  // namespace detail

inline void dealloc(Object* o) {
    switch (o->kind) {
        case Kind::Instance:
            if (!detail::release_attributes(static_cast<Instance*>(o))) return;
            if (o->flags & WEAK_REFERENCE) weak_holder_dies(o);
            detail::bury(o);
            return;
        case Kind::IntInstance:
            if (!detail::release_attributes(static_cast<IntInstance*>(o))) return;
            if (o->flags & WEAK_REFERENCE) weak_holder_dies(o);
            detail::bury(o);
            return;
        case Kind::FloatInstance:
            if (!detail::release_attributes(static_cast<FloatInstance*>(o))) return;
            if (o->flags & WEAK_REFERENCE) weak_holder_dies(o);
            detail::bury(o);
            return;
        case Kind::ComplexInstance:
            if (!detail::release_attributes(static_cast<ComplexInstance*>(o))) return;
            if (o->flags & WEAK_REFERENCE) weak_holder_dies(o);
            detail::bury(o);
            return;
        case Kind::Dict: {
            auto* d = static_cast<DictObject*>(o);
            if (has_attributes(o) && !detail::release_attributes(static_cast<DictInstance*>(o))) return;   // then dict_dealloc
            d->flags |= DEAD;
            auto split = std::move(d->split);
            detail::release_entries(dict_take_all(d), split.get());
            detail::bury(o);
            return;
        }
        case Kind::Str:
            if (has_attributes(o)) {                 // subtype_dealloc; a str has nothing of its own to let go
                auto* s = static_cast<StrInstance*>(o);
                if (!detail::release_attributes(s)) return;
                if (o->flags & WEAK_REFERENCE) weak_holder_dies(o);
                detail::bury(o);
                return;
            }
            [[fallthrough]];
        case Kind::Tuple:
            if (o->kind == Kind::Tuple && has_attributes(o)) {   // subtype_dealloc, then tuple_dealloc's items, last to first
                auto* t = static_cast<TupleInstance*>(o);
                if (!detail::release_attributes(t)) return;
                if (o->flags & WEAK_REFERENCE) weak_holder_dies(o);
                for (auto it = t->items.rbegin(); it != t->items.rend(); ++it) decref(std::exchange(*it, Obj{}));
                detail::bury(o);
                return;
            }
            [[fallthrough]];
        default:
            if (o->flags & HAS_WEAKREFS) clear_weakrefs(o);
            if (o->flags & WEAK_REFERENCE) weak_holder_dies(o);
            if (Destroyer d = destroyer(o->kind)) {
                o->flags |= DEAD;
                d(o);
                return;
            }
            o->flags |= DEAD;
            if (heap().checking) detail::check_not_named(o);
            detail::bury(o);
            return;
    }
}

}  // namespace bella
