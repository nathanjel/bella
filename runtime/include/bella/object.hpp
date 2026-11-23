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
#include <new>
#include <unordered_map>
#include <unordered_set>
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
    Range, Iterator, Traceback, Native, GetSet, Slice, Proxy, Set, DictView, Super, IntInstance, FloatInstance, Complex, ComplexInstance, Generator, LazyImport, AbcData, Bytes, ByteArray, CodeKind, Frame, KindCount
};
// HAS_ATTRIBUTES: an object of a built-in kind whose class is a subclass of the program's, with that
// class's attribute storage beside the built-in's data (DictInstance)
enum Flag : std::uint16_t { IMMORTAL = 1u << 0, DEAD = 1u << 1, DICT_EXPOSED = 1u << 2, HAS_ATTRIBUTES = 1u << 3, FINALIZED = 1u << 4, FROZEN_DICT = 1u << 5, HAS_WEAKREFS = 1u << 6, WEAK_REFERENCE = 1u << 7, DICT_DROPPED = 1u << 8,
                            PUT_OFF = 1u << 9,     // its count is 0 and its dealloc waits for room on the native stack (detail::dealloc_or_later)
                            BUFFERED = 1u << 10,   // a candidate root of the cycle collector: in its buffer, once (detail::possible_root)
                            TOMBSTONE = 1u << 11,  // what is left of an object that died while buffered: its header, freed when the buffer is walked
                            LISTED = 1u << 12 };   // in one of a running collection's lists, which it leaves when it dies

// The kinds the cycle collector tracks: an object that can hold others (Py_TPFLAGS_HAVE_GC). A plain number, text or code object
// holds nothing that dies with it; an object of a built-in kind with a class's attribute storage beside its data (HAS_ATTRIBUTES)
// is tracked too (detail::holds_others).
constexpr bool container_kind(Kind kind) {
    switch (kind) {
        case Kind::Str: case Kind::Singleton: case Kind::Bool: case Kind::BigInt: case Kind::Float: case Kind::Range:
        case Kind::Complex: case Kind::Bytes: case Kind::ByteArray: case Kind::CodeKind: case Kind::Marker:
            return false;
        default:
            return true;
    }
}
// How many objects of the tracked kinds live: the quarter rule of the collector's schedule reads it after a collection.
inline constinit std::size_t containers_alive = 0;

struct Object {
    ClassObject* cls = nullptr;
    std::uint32_t refs = 0;          // single-threaded count; biased counting comes with threads
    std::uint16_t flags = 0;
    Kind kind;
    explicit Object(Kind k) : kind(k) {
        if (container_kind(k)) ++containers_alive;
    }
    ~Object() {
        if (container_kind(kind)) --containers_alive;
    }
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

// ---- the native stack (RL-624; Heap.margin, _dealloc in the model; _Py_Dealloc, _Py_RecursionLimit_GetMargin in CPython) ----
// An object dies inside the dealloc of what held it, so a chain of objects is a chain of deallocs on the native stack, as
// long as the chain: a linked list of some tens of thousands of nodes would not fit. CPython (3.14 and later) looks at the
// stack pointer in _Py_Dealloc: where the margin above the stack's soft limit is nearly used (less than 2 of its units of
// 16 KiB) an object that can hold others is put off, nothing of it run, and a dealloc that ends with room again (4 units
// or more) lets everything put off go, the last first, from there. Below that depth nothing changes: the order is the
// nesting's. The bounds are the thread's, measured when the program starts (measure_native_stack, runtime/src/core.cpp); a
// program of the object model's own tests has none and is never short, unless it says how many deallocs fit (`room`), which
// is the model's `stack_room` and what the lockstep test sets on both sides.
namespace detail {
struct StackWatch {
    const char* soft_limit = nullptr;            // below it a recursion of the runtime's own raises RecursionError (check_native_stack)
    const char* deposit_below = nullptr;         // the soft limit and 2 units: a margin of less than 2
    const char* destroy_from = nullptr;          // the soft limit and 4 units: a margin of 4 or more
    int room = -1;                               // the tests': how many deallocs fit inside one another; -1: the stack says
    int depth = 0;                               // deallocs in flight, counted under `room` only
    std::uint32_t later = 0;                     // how many are put off
};
inline constinit StackWatch stack_watch = {};
inline std::vector<Object*>& put_off() {         // the last put there is the first to go (tstate->delete_later)
    static std::vector<Object*> list;
    return list;
}
inline bool holds_others(Kind kind, std::uint16_t flags) {   // Py_TPFLAGS_HAVE_GC: a plain number, text or code object holds nothing that dies with it
    return (flags & HAS_ATTRIBUTES) != 0 || container_kind(kind);
}
inline void deposit(Object* o) {                 // _PyTrash_thread_deposit_object
    o->flags |= PUT_OFF;
    put_off().push_back(o);
    ++stack_watch.later;
}
inline void destroy_later() {                    // _PyTrash_thread_destroy_chain: each from here, which may put more off
    StackWatch& w = stack_watch;
    while (w.later != 0) {
        Object* o = put_off().back();
        put_off().pop_back();
        --w.later;
        o->flags &= static_cast<std::uint16_t>(~PUT_OFF);
        if (w.room >= 0) ++w.depth;
        dealloc(o);
        if (w.room >= 0) --w.depth;
    }
}
[[gnu::noinline]] inline void dealloc_counted(Object* o) {   // the same two tests on the tests' count of deallocs in flight
    StackWatch& w = stack_watch;
    int margin = w.room - w.depth;
    bool holds = holds_others(o->kind, o->flags);
    if (margin < 2 && holds) return deposit(o);
    ++w.depth;
    dealloc(o);
    --w.depth;
    if (w.later != 0 && margin >= 4 && holds) destroy_later();
}
inline void dealloc_or_later(Object* o) {        // _Py_Dealloc
    StackWatch& w = stack_watch;
    if (w.room >= 0) [[unlikely]] return dealloc_counted(o);
    const char* here = static_cast<const char*>(__builtin_frame_address(0));
    Kind kind = o->kind;
    std::uint16_t flags = o->flags;
    if (here < w.deposit_below && holds_others(kind, flags)) [[unlikely]] return deposit(o);
    dealloc(o);
    if (w.later != 0 && here >= w.destroy_from && holds_others(kind, flags)) [[unlikely]] destroy_later();
}
}  // namespace detail

// ---- the cycle collector's buffer (refmodel/objects.py GcState; trial deletion over candidate roots, the author's decision of
// 2026-11-14). A release that leaves a tracked object's count above nought makes it a candidate root, once, at the end of the
// buffer: only such an object can have become the way into a group that nothing outside holds. A collection takes them all
// (detail::collect, below). The header has no room for an object's place in the buffer, so one that dies while buffered is
// destroyed then and there, as any other is, and what is left of it, its header as a TOMBSTONE, is freed when the buffer is
// walked next, or compacted once half of it is tombstones. A collection's own lists name objects too (LISTED), which leave
// them as they die. ----
namespace detail {
struct GcList {                                  // one of a collection's lists (a ring of PyGC_Head in gc.c): its objects in order
    std::vector<Object*> items;                  // nullptr: one that left
    std::size_t first_at = 0, size = 0;
};
struct Collector {
    std::vector<Object*> candidates;             // in the order buffered
    std::size_t tombstones = 0;                  // among the candidates
    std::int64_t thresholds[3] = {2000, 10, 10}; // gc.get_threshold(): the first is the buffer's size; the others are kept
    bool enabled = true, collecting = false, scheduled = false;   // scheduled: a collection at the next look
    std::size_t alive_after = 0;                 // tracked objects after the last collection: the quarter rule
    std::int64_t collections = 0, collected = 0; // gc.get_stats()'s numbers, the runtime's own
    std::int64_t candidates_total = 0;           // and its candidates and the time taken, summed (gc.cpp's run_collection)
    double duration_total = 0.0;
    std::unordered_map<const Object*, std::pair<GcList*, std::size_t>> where;   // a LISTED object's list and place
    volatile int* breaker = nullptr;             // the runtime's eval breaker word: set with `scheduled` (_Py_ScheduleGC)
    std::size_t roots = 0;                       // the last collection's roots: gc.callbacks' "candidates"
};
inline Collector& collector() {
    static Collector c;
    return c;
}
inline void free_tombstone(Object* o) {
    o->~Object();
    ::operator delete(static_cast<void*>(o));
}
inline void compact_buffer() {                   // the tombstones go, the candidates keep their order
    Collector& c = collector();
    std::size_t kept = 0;
    for (Object* o : c.candidates) {
        if (o->flags & TOMBSTONE) free_tombstone(o);
        else c.candidates[kept++] = o;
    }
    c.candidates.resize(kept);
    c.tombstones = 0;
}
[[gnu::noinline]] inline void possible_root(Object* o) {
    if (o->flags & (DEAD | PUT_OFF)) return;     // dying: not a root
    o->flags |= BUFFERED;
    Collector& c = collector();
    c.candidates.push_back(o);
    std::size_t live = c.candidates.size() - c.tombstones;
    if (c.enabled && c.thresholds[0] > 0 && !c.collecting && live > static_cast<std::size_t>(c.thresholds[0]) && 4 * live > c.alive_after) {
        c.scheduled = true;
        if (c.breaker != nullptr) *c.breaker = 1;
    }
}
inline void released_above_nought(Object* o) {   // a count lowered by hand (a finaliser's own, after it revived the object)
    if (!(o->flags & BUFFERED) && holds_others(o->kind, o->flags)) possible_root(o);
}
inline void unlist(Object* o) {                  // out of the collection's list that holds it
    Collector& c = collector();
    auto it = c.where.find(o);
    if (it == c.where.end()) return;
    auto [list, at] = it->second;
    c.where.erase(it);
    list->items[at] = nullptr;
    --list->size;
    o->flags &= static_cast<std::uint16_t>(~LISTED);
}
// The end of an object's memory: what the buffer names is left as a tombstone, its destructor run now as any other's.
template <class T>
inline void free_object(T* o) {
    if (o->flags & LISTED) [[unlikely]] unlist(o);
    if (o->flags & BUFFERED) [[unlikely]] {
        o->~T();
        Object* tomb = new (static_cast<void*>(o)) Object(Kind::Marker);
        tomb->flags = DEAD | BUFFERED | TOMBSTONE;
        Collector& c = collector();
        ++c.tombstones;
        if (c.tombstones > 4096 && 2 * c.tombstones > c.candidates.size()) compact_buffer();
        return;
    }
    delete o;
}
}  // namespace detail

inline void decref(Object* o) {
    if (o->flags & IMMORTAL) return;
    if (o->refs == 0) throw ModelError("an object released more often than it was held");
    if (--o->refs == 0) detail::dealloc_or_later(o);
    else if (!(o->flags & BUFFERED) && detail::holds_others(o->kind, o->flags)) [[unlikely]] detail::possible_root(o);
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
    // A class has thirty places (dk_usable, _PyDict_NewKeysForClass): each key takes one, and so does each instance made while
    // more than one is left (_PyObject_InitInlineValues: "it will shrink by one before each new object"). A class that has made
    // some thirty instances therefore takes one more name and then none (refmodel RefClass.keys_left; C-3-60).
    std::size_t left = SHARED_KEYS_MAX;
    bool contains(const Str* n) const { return std::find(names.begin(), names.end(), n) != names.end(); }
    // Records n; false when no place is left and n is not there.
    bool note(const Str* n) {
        if (contains(n)) return true;
        if (left == 0) return false;
        names.push_back(n);
        --left;
        return true;
    }
    void instance_made() {
        if (left > 1) --left;
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
    bool readonly = false;                           // PyMemberDef's Py_READONLY: no store and no delete through the member
    bool boolean = false;                            // a Py_T_BOOL member: True and False alone, and never deleted (the runtime's check)
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
// Which dict an instance has (CPython 3.15.2: type_new_descriptors, type_ready_managed_dict, ensure_nonmanaged_dict; refmodel
// RefClass.dict_kind). Inline: its values in the object until the dict is asked for (a managed dict with inline values: a
// program's class, a subclass of a built-in type of fixed size). Shared: a dict of its own that shares the class's keys, made
// at the first write, the first delete or when asked for (a managed dict with no inline values: an int's or a tuple's
// subclass). Plain: an ordinary dict made the same way (a type written in C with its own dict slot, and what derives from it).
enum class DictKind : std::uint8_t { Inline, Shared, Plain };
struct ClassObject : Object {
    std::string name;
    std::string qualname;                        // __qualname__ (the name unless the class body set one)
    bool heap_type = false;                      // a class a program made (Py_TPFLAGS_HEAPTYPE)
    std::vector<ClassObject*> bases;
    std::vector<ClassObject*> mro;               // C3, self first
    // tp_bases and tp_mro as objects (RefClass.bases, .mro): one each until replaced. bases_tuple is the tuple the class was
    // made with or the one assigned to __bases__; either is made at the first read when the class has none yet (a C++ type,
    // a class with no bases: a new (object,)), and the MRO's is dropped when the hierarchy's bases are assigned (mro_hierarchy)
    Obj bases_tuple;                             // owned, or unset
    Obj mro_tuple;                               // owned, or unset
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
    // A built-in type's fields that have no name (RefClass.hidden; RL-507): slots it declares that have no descriptor in
    // the class. `hidden` is this class's own, `hidden_fields` the MRO's, and `state_index` their places in an instance's
    // fields, apart from field_index: a class that derives from the type may have a slot or a kept attribute of the name.
    std::unordered_set<const Str*> hidden;
    std::vector<const Str*> hidden_fields;
    std::unordered_map<const Str*, std::uint32_t> state_index;
    // The slots a nearer class of the MRO declares again (RefClass.shadowed_fields; RL-541): CPython makes a member for
    // each declaration, each with a cell. The name's cell (field_index) is the nearest declaring class's; a declaration
    // behind it keeps a cell at a place of its own, which that class's member alone reads.
    struct ShadowedSlot {                        // owner null: a field of the built-in base under a slot's name (RL-564)
        ClassObject* owner;
        const Str* name;
        std::uint32_t place;
        bool operator==(const ShadowedSlot&) const = default;
    };
    std::vector<ShadowedSlot> shadowed;
    // A built-in type's dealloc (RefClass.release; RL-565): the order in which it lets go of what its struct holds, by the
    // names of its fields, its own and its built-in bases', with __weakref__ where it clears its weak references and
    // __dict__ where it lets go of its dict, if it has them. An object of a class that derives from the type lets go of
    // that class's slots and of a dict that class added first, and then this runs. `dealloc_base` is the nearest class
    // of the MRO that has one: the class itself, a base, or null (a class over object, or over a type of the header's own).
    std::optional<std::vector<const Str*>> release;
    bool release_has_weak = false, release_has_dict = false;
    ClassObject* dealloc_base = nullptr;
    std::size_t field_count() const { return field_index.size() + state_index.size() + shadowed.size(); }
    bool has_dict = false;
    DictKind dict_kind = DictKind::Inline;       // which dict an instance has; a class that says nothing has its solid base's
    bool has_weakref = false;                    // room for weak references (RefClass.has_weakref)
    bool dict_without_getset = false;            // _thread._local: a subclass still gets a __dict__ of its own to show
    bool sequence_slots = false;                 // a C type written in Python, with sq_concat and sq_item and no number slots
    bool weak_proxy = false;                     // weakref.ProxyType and its kin: attribute access goes to the target
    std::uint8_t collection_flags = 0;           // a program's class: Py_TPFLAGS_SEQUENCE, Py_TPFLAGS_MAPPING (what match and __flags__ read)
    bool abstract = false;                       // Py_TPFLAGS_IS_ABSTRACT: set by __abstractmethods__, not inherited
    bool mapping_getitem = false;                // a C type written in Python whose __getitem__ is mp_subscript alone: no sq_item
    bool disallow_instantiation = false;         // Py_TPFLAGS_DISALLOW_INSTANTIATION, of a C type written in Python
    bool slot_tp_new = false;                    // tp_new is slot_tp_new: a class of the program's for which a __new__ that is no
                                                 // built-in's wrapper was ever found (update_one_slot keeps it; runtime/src/types.cpp)
    bool stored_new_wrapper = false;             // the name __new__ finds a built-in's wrapper stored in a class of the program's,
                                                 // which CPython's slot ignores: the allocator is the built-in base's (RL-841)
    bool forwards_attributes = false;            // types.GenericAlias's tp_getattro (getattr_impl), inherited
    bool struct_sequence = false;                // Objects/structseq.c's type: structseq_dealloc's order of release (RL-593)
    bool slots_ordered = false;                  // its own slots stand in the order type_new's sort of the name objects left them (RL-588)
    std::uint32_t repeated_slots = 0;            // names its own __slots__ has more than once: CPython makes a cell for each, which
                                                 // nothing can reach and only the size test of the default pickling state sees (RL-591)
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
        for (Obj* t : {&bases_tuple, &mro_tuple})
            if (!t->is_unset()) decref(std::exchange(*t, Obj{}));
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
    std::optional<DictKind> dict_kind = std::nullopt;                // which dict an instance has; nullopt: the solid base's
    std::vector<std::string> hidden = {};                            // of its slots, the fields with no name (RefClass hidden)
    std::vector<std::string> members = {};                           // of the hidden, those the type shows (RefClass members)
    std::vector<std::string> readonly = {};                          // of its slots, the read-only members (RefClass readonly)
    std::optional<std::vector<std::string>> release = std::nullopt;  // a built-in type's dealloc order (RefClass release)
    bool slots_ordered = false;                                      // the slots are in the order type_new's sort left them (RefClass slots_ordered)
    std::uint32_t repeated_slots = 0;                                // how many times its __slots__ names a slot again (RL-591)
};

// RefClass(release=...), also for a class that exists (the prelude's, presented as CPython's after its class statement):
// the class and every class that derives from it so far find their nearest dealloc again.
inline void set_release(ClassObject* c, std::vector<const Str*> order) {
    static const Str* const weak = intern("__weakref__");
    static const Str* const dict = intern("__dict__");
    std::vector<const Str*> named, fields = c->hidden_fields;
    for (const Str* n : order)
        if (n != weak && n != dict) named.push_back(n);
    std::sort(named.begin(), named.end());
    std::sort(fields.begin(), fields.end());
    if (named != fields) throw ModelError("a built-in type's dealloc names each of its fields once: '" + c->name + "'");
    // over a built-in base with fields the type's dealloc would end with the base's: refused, not half done (the model)
    if (!c->native_fields.empty()) throw ModelError("a dealloc of its own over a built-in base with fields is not written: '" + c->name + "'");
    c->release_has_weak = std::find(order.begin(), order.end(), weak) != order.end();
    c->release_has_dict = std::find(order.begin(), order.end(), dict) != order.end();
    c->release = std::move(order);
    std::vector<ClassObject*> todo{c};
    while (!todo.empty()) {
        ClassObject* k = todo.back();
        todo.pop_back();
        k->dealloc_base = nullptr;
        for (ClassObject* m : k->mro)
            if (m->release) {
                k->dealloc_base = m;
                break;
            }
        for (ClassObject* sub : k->subclasses) todo.push_back(sub);
    }
}

// RefClass(hidden=...), for a class that exists: the built-in types the prelude writes are made by its class statements
// and presented as CPython's afterwards, and this is part of that. The fields keep their places, in the class and in every
// class that derives from it so far, so objects made before are as they were; the descriptors go, under new versions.
// Before any class of a program derives from it.
inline void hide_slots(ClassObject* c, const std::vector<const Str*>& names, const std::vector<const Str*>& members = {},
                       const std::vector<const Str*>& readonly = {}, const std::vector<const Str*>& boolean = {}) {
    std::vector<ClassObject*> todo{c}, family;
    while (!todo.empty()) {
        ClassObject* k = todo.back();
        todo.pop_back();
        if (std::find(family.begin(), family.end(), k) != family.end()) continue;
        family.push_back(k);
        for (ClassObject* sub : k->subclasses) todo.push_back(sub);
    }
    for (const Str* n : names) {
        if (c->hidden.contains(n)) continue;
        auto own = c->own_slot_names();
        if (std::find(own.begin(), own.end(), n) == own.end()) throw ModelError("a hidden field is one of the class's own __slots__");
        c->hidden.insert(n);
        // a member CPython's type shows keeps its descriptor (RefClass members), which reads the field's cell from now on
        bool shown = std::find(members.begin(), members.end(), n) != members.end();
        if (const Obj* d = c->attrs.find(n); d != nullptr && d->is_object() && d->object()->kind == Kind::SlotDescriptor) {
            if (!shown) c->del_attr(n);
            else {
                static_cast<SlotDescriptor*>(d->object())->readonly = std::find(readonly.begin(), readonly.end(), n) != readonly.end();
                static_cast<SlotDescriptor*>(d->object())->boolean = std::find(boolean.begin(), boolean.end(), n) != boolean.end();
            }
        }
        for (ClassObject* k : family) {
            // another class of the family that declares the name shares the cell, as a field of one name does: hidden
            // there too. The runtime's own types declare a field once; one declared again before this, with a cell of
            // its own behind the name's, is not a state this can make of it
            for (const auto& behind : k->shadowed)
                if (behind.name == n) throw ModelError("a field of a built-in type that a class of its family declared again: '" + n->text + "'");
            auto at = k->field_index.find(n);
            if (at == k->field_index.end()) continue;
            k->state_index[n] = at->second;
            k->field_index.erase(at);
            std::erase(k->slot_fields, n);
            k->hidden_fields.push_back(n);
            auto theirs = k->own_slot_names();
            if (k != c && std::find(theirs.begin(), theirs.end(), n) != theirs.end()) {
                k->hidden.insert(n);
                if (const Obj* d = k->attrs.find(n); d != nullptr && d->is_object() && d->object()->kind == Kind::SlotDescriptor) k->del_attr(n);
            }
        }
    }
}

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
        for (const auto& h : spec.hidden) {
            if (std::find(own.begin(), own.end(), intern(h)) == own.end()) throw ModelError("a hidden field is one of the class's own __slots__");
            c->hidden.insert(intern(h));
        }
        auto listed = [](const std::vector<std::string>& names, const Str* s) { return std::find(names.begin(), names.end(), s->text) != names.end(); };
        for (const auto& m : spec.members)
            if (!c->hidden.contains(intern(m))) throw ModelError("a member is one of the class's hidden fields");
        for (const auto& r : spec.readonly)
            if (std::find(own.begin(), own.end(), intern(r)) == own.end()) throw ModelError("a read-only member is one of the class's own __slots__");
        for (const Str* s : own)
            if (c->attrs.contains(s) && (!c->hidden.contains(s) || listed(spec.members, s)))
                throw ModelError("'" + s->text + "' in __slots__ conflicts with class variable");
        // type_new_slots sorts them, and tp_members' order is the class dict's (code points: UTF-8's order); names that were
        // sorted as objects, by a str subclass's own __lt__, come in that order (RL-588)
        c->slots_ordered = spec.slots_ordered;
        c->repeated_slots = spec.repeated_slots;
        if (!spec.slots_ordered) std::sort(own.begin(), own.end(), [](const Str* x, const Str* y) { return x->text < y->text; });
        for (const Str* s : own) {
            if (c->hidden.contains(s) && !listed(spec.members, s)) continue;   // a field of the C struct: no member of the type
            auto* d = new SlotDescriptor(s);
            d->owner = c;
            d->readonly = listed(spec.readonly, s);
            incref(d);
            c->attrs.set(s, Obj::of(d));
        }
    }
    auto add_unique = [](std::vector<const Str*>& out, const Str* n) {
        if (std::find(out.begin(), out.end(), n) == out.end()) out.push_back(n);
    };
    for (auto it = c->mro.rbegin(); it != c->mro.rend(); ++it)
        for (const Str* s : (*it)->own_slot_names()) add_unique((*it)->hidden.contains(s) ? c->hidden_fields : c->slot_fields, s);
    for (const Str* p : c->promoted)
        if (std::find(c->slot_fields.begin(), c->slot_fields.end(), p) != c->slot_fields.end())
            throw ModelError("promoted field '" + p->text + "' collides with a slot");
    for (auto it = c->mro.rbegin(); it != c->mro.rend(); ++it)
        for (const Str* p : (*it)->promoted) add_unique(c->promoted_fields, p);
    if (spec.dict_kind) {
        c->dict_kind = *spec.dict_kind;
    } else {
        for (std::size_t k = 1; k < c->mro.size(); ++k)
            if (c->mro[k]->dict_kind != DictKind::Inline) {
                c->dict_kind = c->mro[k]->dict_kind;
                break;
            }
    }
    if (c->dict_kind != DictKind::Inline && !c->promoted_fields.empty())
        throw ModelError("promoted fields are values kept in the object: an inline class's only");
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
            if (in(c->promoted_fields)) throw ModelError("'" + n->text + "' is a field of a built-in base");
            c->native_fields.push_back(n);
        }
    std::uint32_t i = 0;
    for (const Str* h : c->hidden_fields) c->state_index[h] = i++;      // first: a field keeps its place in every class that derives
    for (const Str* s : c->slot_fields) c->field_index[s] = i++;
    for (const Str* n : c->native_fields)                // one under a slot's name has its cell behind the slot's, below
        if (!c->field_index.contains(n)) c->field_index[n] = i++;
    for (const Str* p : c->promoted_fields) c->field_index[p] = i++;
    {   // a declaration that a nearer class repeats: a cell of its own, the base-most first (RefClass.shadowed_fields)
        std::unordered_map<const Str*, const ClassObject*> nearest;
        std::vector<std::pair<ClassObject*, const Str*>> behind;
        for (ClassObject* k : c->mro)
            for (const Str* s : k->own_slot_names()) {
                if (k->hidden.contains(s)) continue;
                if (nearest.try_emplace(s, k).first->second != k && std::find(behind.begin(), behind.end(), std::pair{k, s}) == behind.end())
                    behind.emplace_back(k, s);
            }
        for (auto it = behind.rbegin(); it != behind.rend(); ++it) c->shadowed.push_back({it->first, it->second, i++});
        // a slot under the name of a field of the built-in base (class E(Exception): __slots__ = ("args",)): the base's field
        // is a declaration behind the name's, with no class to name
        for (const Str* n : c->native_fields)
            if (std::find(c->slot_fields.begin(), c->slot_fields.end(), n) != c->slot_fields.end()) c->shadowed.push_back({nullptr, n, i++});
    }
    if (spec.release) {
        std::vector<const Str*> order;
        for (const auto& n : *spec.release) order.push_back(intern(n));
        set_release(c, std::move(order));
    } else {
        for (ClassObject* m : c->mro)
            if (m->release) {
                c->dealloc_base = m;
                break;
            }
    }
    c->keys = std::make_shared<SharedKeys>();
    std::vector<std::string> statics = spec.static_attributes;
    std::sort(statics.begin(), statics.end());
    for (const auto& n : statics) c->keys->note(intern(n));
    heap().classes.push_back(c);
    return c;
}

// ---- instances (refmodel RefObject) ----
// An instance that keeps its values in it takes one of the places its class's shared keys have (SharedKeys::instance_made).
inline void instance_made(ClassObject* c) {
    if (c->has_dict && c->dict_kind == DictKind::Inline && c->keys) c->keys->instance_made();
}
struct Instance : Object {
    std::vector<Obj> fields;                    // by the class's field_index; Unset: absent
    DictObject* dict = nullptr;                 // before exposure: the names not promoted; after: the __dict__
    std::vector<const Str*> order;              // first-assignment order of __dict__-backed names (insertion_order)
    std::int64_t tag = -1;                      // tests log the deaths of tagged objects
    explicit Instance(ClassObject* c) : Object(Kind::Instance) {
        cls = c;
        instance_made(c);
        fields.assign(c->field_count(), Obj{});
    }
    bool exposed() const { return (flags & DICT_EXPOSED) != 0; }
    Obj& field(const Str* n) { return fields[cls->field_index.at(n)]; }
    Obj& state(const Str* n) { return fields[cls->state_index.at(n)]; }
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
        instance_made(c);
        flags |= HAS_ATTRIBUTES;
        fields.assign(c->field_count(), Obj{});
    }
    bool exposed() const { return (flags & DICT_EXPOSED) != 0; }
    Obj& field(const Str* n) { return fields[cls->field_index.at(n)]; }
    Obj& state(const Str* n) { return fields[cls->state_index.at(n)]; }
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
        instance_made(c);
        flags |= HAS_ATTRIBUTES;
        fields.assign(c->field_count(), Obj{});
    }
    bool exposed() const { return (flags & DICT_EXPOSED) != 0; }
    Obj& field(const Str* n) { return fields[cls->field_index.at(n)]; }
    Obj& state(const Str* n) { return fields[cls->state_index.at(n)]; }
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
        instance_made(c);
        flags |= HAS_ATTRIBUTES;
        fields.assign(c->field_count(), Obj{});
    }
    bool exposed() const { return (flags & DICT_EXPOSED) != 0; }
    Obj& field(const Str* n) { return fields[cls->field_index.at(n)]; }
    Obj& state(const Str* n) { return fields[cls->state_index.at(n)]; }
    bool has_field(const Str* n) const { return cls->field_index.contains(n); }
};
// A tuple, and an instance of a program's subclass of tuple. Its kind stays Tuple, as PyTuple_Check says
// yes of it; what only an exact tuple does asks is_exact_tuple, and what a subclass may override asks first.
struct Tuple : Object {                          // owns one count of each item
    std::vector<Obj> items;
    // ob_hash (CPython 3.14 and later): tuple_hash's answer once it has one, -1 until then, so the items are asked for their
    // hashes once however often the tuple is hashed or looked up (RL-574, C-6-24). What uses a tuple again with other items
    // forgets it (_PyTuple_Recycle: the prelude's _tuple_set)
    mutable std::int64_t hash = -1;
    Tuple();
};
struct TupleInstance : Tuple {
    std::vector<Obj> fields;
    DictObject* dict = nullptr;
    std::vector<const Str*> order;
    std::int64_t tag = -1;
    explicit TupleInstance(ClassObject* c) {
        cls = c;
        instance_made(c);
        flags |= HAS_ATTRIBUTES;
        fields.assign(c->field_count(), Obj{});
    }
    bool exposed() const { return (flags & DICT_EXPOSED) != 0; }
    Obj& field(const Str* n) { return fields[cls->field_index.at(n)]; }
    Obj& state(const Str* n) { return fields[cls->state_index.at(n)]; }
    bool has_field(const Str* n) const { return cls->field_index.contains(n); }
};
// A list, and an instance of a program's subclass of list (C-3-51): as Tuple and TupleInstance, its kind stays List, as
// PyList_Check says yes of it; what only an exact list does asks is_exact_list, and what a subclass may override asks first.
struct List : Object {                           // owns one count of each item
    std::vector<Obj> items;
    List();
};
struct ListInstance : List {
    std::vector<Obj> fields;
    DictObject* dict = nullptr;
    std::vector<const Str*> order;
    std::int64_t tag = -1;
    explicit ListInstance(ClassObject* c) {
        cls = c;
        instance_made(c);
        flags |= HAS_ATTRIBUTES;
        fields.assign(c->field_count(), Obj{});
    }
    bool exposed() const { return (flags & DICT_EXPOSED) != 0; }
    Obj& field(const Str* n) { return fields[cls->field_index.at(n)]; }
    Obj& state(const Str* n) { return fields[cls->state_index.at(n)]; }
    bool has_field(const Str* n) const { return cls->field_index.contains(n); }
};
struct SetObject : Object {
    struct Entry {
        Obj key;                                 // Unset: empty (hash 0) or a dummy (hash -1)
        std::int64_t hash = 0;
    };
    std::vector<Entry> table;
    std::size_t fill = 0, used = 0;
    std::size_t finger = 0;                      // where set.pop looks next
    bool frozen;
    explicit SetObject(bool frozen_set);
};
// An instance of a program's subclass of set or frozenset (decision 2026-11-03: a subclass of a built-in type is that type's
// object): kind Set, flag HAS_ATTRIBUTES, the attribute storage beside the table. set itself keeps a weak reference list, so the
// instance's weak references are cleared by set_dealloc, after its slots and its dict (subtype_dealloc leaves them to the base).
struct SetInstance : SetObject {
    std::vector<Obj> fields;
    DictObject* dict = nullptr;
    std::vector<const Str*> order;
    std::int64_t tag = -1;
    SetInstance(ClassObject* c, bool frozen_set) : SetObject(frozen_set) {
        cls = c;
        instance_made(c);
        flags |= HAS_ATTRIBUTES;
        fields.assign(c->field_count(), Obj{});
    }
    bool exposed() const { return (flags & DICT_EXPOSED) != 0; }
    Obj& field(const Str* n) { return fields[cls->field_index.at(n)]; }
    Obj& state(const Str* n) { return fields[cls->state_index.at(n)]; }
    bool has_field(const Str* n) const { return cls->field_index.contains(n); }
};
struct BytesObject : Object {                    // bytes and bytearray: their octets; a bytearray's change
    std::string data;
    std::int64_t hash = -1;                      // a bytes's, once computed
    std::int64_t exports = 0;                    // a bytearray's ob_exports: while it is not 0 it cannot change size (re's scanner holds one)
    BytesObject(Kind k, std::string d);
};
// An instance of a program's subclass of bytes or bytearray: its kind stays the base's, flag HAS_ATTRIBUTES, the attribute storage
// beside the octets. bytes has an item size, so its subclass gets no weak reference unless asked and no slots but __dict__.
struct BytesInstance : BytesObject {
    std::vector<Obj> fields;
    DictObject* dict = nullptr;
    std::vector<const Str*> order;
    std::int64_t tag = -1;
    BytesInstance(ClassObject* c, Kind k, std::string d) : BytesObject(k, std::move(d)) {
        cls = c;
        instance_made(c);
        flags |= HAS_ATTRIBUTES;
        fields.assign(c->field_count(), Obj{});
    }
    bool exposed() const { return (flags & DICT_EXPOSED) != 0; }
    Obj& field(const Str* n) { return fields[cls->field_index.at(n)]; }
    Obj& state(const Str* n) { return fields[cls->state_index.at(n)]; }
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
        instance_made(c);
        flags |= HAS_ATTRIBUTES;
        fields.assign(c->field_count(), Obj{});
    }
    bool exposed() const { return (flags & DICT_EXPOSED) != 0; }
    Obj& field(const Str* n) { return fields[cls->field_index.at(n)]; }
    Obj& state(const Str* n) { return fields[cls->state_index.at(n)]; }
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
        instance_made(c);
        flags |= HAS_ATTRIBUTES;
        fields.assign(c->field_count(), Obj{});
    }
    bool exposed() const { return (flags & DICT_EXPOSED) != 0; }
    Obj& field(const Str* n) { return fields[cls->field_index.at(n)]; }
    Obj& state(const Str* n) { return fields[cls->state_index.at(n)]; }
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

// What a class has under a special name, called as a method of `self` (CPython's lookup_method and its unbound call, which
// slot_tp_descr_set uses for __set__ and __delete__): a function, or a method of a built-in type, is given `self` first;
// anything else is bound by its own __get__, if it has one, and called with the rest alone (`__set__ = staticmethod(f)`
// calls f(obj, value): review A39, RL-878). __get__ itself is not called this way: slot_tp_descr_get calls what the type
// has under the name as it is. The kinds are the runtime's to tell, which installs the hook; in this header's own tests
// every callable is a function. Returns a new reference.
using CallMethodHook = Obj (*)(Obj fn, Obj self, std::span<const Obj> rest);
inline CallMethodHook& call_method_hook() {
    static CallMethodHook hook = nullptr;
    return hook;
}
inline Obj call_method(Obj fn, Obj self, std::initializer_list<Obj> rest) {
    if (call_method_hook() != nullptr && !(fn.is_object() && fn.object()->kind == Kind::Function))
        return call_method_hook()(fn, self, std::span<const Obj>(rest.begin(), rest.size()));
    std::vector<Obj> a{self};
    a.insert(a.end(), rest.begin(), rest.end());
    if (fn.is_object() && fn.object()->kind == Kind::Function) return static_cast<Function*>(fn.object())->fn(a);
    if (call_hook() != nullptr) return call_hook()(fn, std::span<const Obj>(a.data(), a.size()));
    throw TypeError("object is not callable");
}

// ---- inline caches (refmodel CacheEntry, Site) ----
enum class Plan : std::uint8_t {
    DataDescriptor, Slot, Field, InstanceDict, ClassAttr, NonDataDescriptor, GetAttrHook, UncachedValue, Raise,
    State                          // a member whose cell is a field of the built-in type's own (RefClass members)
};
// The cell of the slot `name` that `owner` declares (refmodel _cell_of): in the object's state when the class keeps it as a
// field of the built-in type's own; at a place of the declaration's own when a nearer class of the object's MRO declares the
// name again; among the object's fields, by the name, in every other case (no owner: a built-in's native field).
inline const ClassObject::ShadowedSlot* slot_behind(const ClassObject* cls, const ClassObject* owner, const Str* name) {
    for (const auto& s : cls->shadowed)              // empty for all but a class with a slot declared again
        if (s.owner == owner && s.name == name) return &s;
    return nullptr;
}
template <class T>
inline Obj& slot_cell(T* obj, const ClassObject* owner, const Str* name) {
    if (owner != nullptr && owner->hidden.contains(name)) return obj->state(name);
    if (!obj->cls->shadowed.empty())
        if (const auto* behind = slot_behind(obj->cls, owner, name)) return obj->fields[behind->place];
    return obj->field(name);
}
// The cell a member reads and stores: its own declaration's, whatever name a class has the member under (_member_cells)
inline bool member_in_state(const SlotDescriptor* d) { return d->owner != nullptr && d->owner->hidden.contains(d->name); }
template <class T>
inline Obj& member_cell(T* obj, const SlotDescriptor* d) { return slot_cell(obj, d->owner, d->name); }
// descr_check: a member applies to the objects of its class and of the classes that derive from it. One that a class which
// is neither has under a name is a TypeError for a read, a store and a delete alike (RL-563)
inline void member_applies(const ClassObject* cls, const SlotDescriptor* d) {
    if (d->owner == nullptr || d->owner == cls || std::find(cls->mro.begin(), cls->mro.end(), d->owner) != cls->mro.end()) return;
    throw TypeError("descriptor '" + d->name->text + "' for '" + d->owner->name + "' objects doesn't apply to a '" + cls->name + "' object");
}
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
// The object gets a dict of its own, its values not the object's: one that shares the class's keys, or an ordinary one.
// An object whose dict was deleted (del_dict) gets it at the first thing asked of its instance storage: ordinary when that
// is a plain read (_PyObject_MaterializeManagedDict with the inline values invalid: PyDict_New), sharing when it is a write,
// a delete or its __dict__ (ensure_managed_dict: new_dict_with_shared_keys). An object of a class that keeps no values in the
// object gets it at the first write, delete or __dict__, of its class's kind (ensure_nonmanaged_dict), and a read asks for
// none. No user code runs and nothing is released (refmodel Runtime._settle).
template <class T>
inline void settle(T* obj, bool split) {
    auto* d = new DictObject();
    if (split) d->split = obj->cls->keys;
    incref(d);
    obj->dict = d;
    obj->flags = static_cast<decltype(obj->flags)>((obj->flags | DICT_EXPOSED) & ~DICT_DROPPED);
}
// (present, value) for the __dict__-backed storage of a name (never slots). This is the plain read that reaches the
// instance, so a dropped object gets its ordinary dict here; the two flags are one test for every other object.
template <class T>
inline std::pair<bool, Obj> instance_storage(T* obj, const Str* name) {
    if (obj->flags & (DICT_EXPOSED | DICT_DROPPED)) {
        if (obj->flags & DICT_DROPPED) settle(obj, false);
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
        if (found.object()->kind == Kind::SlotDescriptor) {
            // which cell is the class's matter, so the version covers it and the entry holds the kind alone. A member the
            // class has under another name reads its own cell and is not cached: an entry reads the cell of the name looked
            // up. Nor is the member of a declaration that a nearer class repeats, found by the name once the nearer one's
            // is gone from its class
            auto* d = static_cast<SlotDescriptor*>(found.object());
            member_applies(cls, d);
            Plan k = member_in_state(d) ? Plan::State : Plan::Slot;
            bool by_name = d->name == name && (cls->shadowed.empty() || slot_behind(cls, d->owner, d->name) == nullptr);
            return {{k, Obj{}, member_cell(obj, d), hook}, by_name ? entry(k) : std::nullopt};
        }
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
    if (((e->kind == Plan::Slot || e->kind == Plan::Field) && !obj->has_field(name)) || (e->kind == Plan::State && !obj->cls->state_index.contains(name)))
        throw ModelError("unsound cache: '" + name->text + "' cached as a field for a layout without it");
    switch (e->kind) {
        case Plan::Slot:
            return LookupPlan{Plan::Slot, Obj{}, obj->field(name), hook};
        case Plan::State:
            return LookupPlan{Plan::State, Obj{}, obj->state(name), hook};
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
                // slot_tp_descr_get calls what the type has under __get__ as it is, the descriptor first: no method lookup
                // (`__get__ = print` prints the three; unlike __set__ and __delete__ below)
                return Ref::steal(call(get.get(), {desc.get(), Obj::of(obj), Obj::of(obj->cls)}));
            }
            case Plan::Slot:
            case Plan::State:
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

template <class T>
inline Ref expose_dict(T* obj);
namespace detail {
// A name the class's keys cannot take is stored on an object whose values are in it: they move into an ordinary dict of the
// object's own, in the order they were stored (store_instance_attr_lock_held: make_dict_from_instance_attributes, then
// insertdict's resize into a combined table, which marks the inline values invalid; refmodel Runtime._unshare).
template <class T>
inline void unshare(T* obj) {
    expose_dict(obj);
    obj->dict->split.reset();
    obj->dict->embedded = nullptr;
}
}  // namespace detail

// Every store keeps the new value before it releases the old one.
// Runtime.state_get, state_set and state_del: a built-in type's own field (RL-507), with no lookup and no hook of any
// class. The value read is borrowed; one never stored, or deleted, is an AttributeError of the name alone.
template <class T>
inline Obj state_get(T* obj, const Str* name) {
    Obj v = obj->state(name);
    if (v.is_unset()) throw AttributeError(name->text);
    return v;
}
template <class T>
inline void state_set(T* obj, const Str* name, Obj value) {
    incref(value);
    decref(std::exchange(obj->state(name), value));      // the new value is kept before the old one is let go
}
template <class T>
inline void state_del(T* obj, const Str* name) {
    Obj old = obj->state(name);
    if (old.is_unset()) throw AttributeError(name->text);
    obj->state(name) = Obj{};
    decref(old);
}

template <class T>
inline void setattr(T* obj, const Str* name, Obj value) {
    ClassObject* cls = obj->cls;
    if (auto hit = cls->lookup(name)) {
        Obj found = hit->first;
        if (found.is_object() && found.object()->kind == Kind::SlotDescriptor) {
            auto* d = static_cast<SlotDescriptor*>(found.object());
            member_applies(cls, d);
            if (d->readonly) throw AttributeError("readonly attribute");
            incref(value);
            Obj old = std::exchange(member_cell(obj, d), value);
            decref(old);
            return;
        }
        if (is_data_descriptor(found)) {
            auto setter = found.object()->cls->lookup(intern("__set__"));
            if (!setter) throw AttributeError("__set__");            // a data descriptor with only __delete__
            Ref desc = Ref::share(found);                            // owned while __set__ runs
            Ref fn = Ref::share(setter->first);
            decref(call_method(fn.get(), desc.get(), {Obj::of(obj), value}));
            return;
        }
    }
    if (obj->flags & (DICT_EXPOSED | DICT_DROPPED)) {   // a new name joins a split dict's keys (dict_put)
        if (obj->flags & DICT_DROPPED) detail::settle(obj, true);
        dict_store(obj->dict, Obj::of(name), value);
        return;
    }
    if (detail::is_promoted(obj, name)) {
        Obj& slot = obj->field(name);
        if (slot.is_unset()) {
            if (!cls->keys->note(name)) {            // no place left for the name: an ordinary dict from here on
                detail::unshare(obj);
                dict_store(obj->dict, Obj::of(name), value);
                return;
            }
            obj->order.push_back(name);
        }
        incref(value);
        Obj old = std::exchange(slot, value);
        decref(old);
        return;
    }
    if (!cls->has_dict)
        throw AttributeError("'" + cls->name + "' object has no attribute '" + name->text + "' and no __dict__ for setting new attributes");
    if (obj->dict == nullptr) {
        if (cls->dict_kind != DictKind::Inline) {    // no values in the object: a dict of its own from the first write on
            detail::settle(obj, cls->dict_kind == DictKind::Shared);
            dict_store(obj->dict, Obj::of(name), value);
            return;
        }
        obj->dict = new DictObject();
        obj->dict->split = cls->keys;
        incref(obj->dict);
    }
    if (dict_find(obj->dict, Obj::of(name)).is_unset()) {
        if (!cls->keys->note(name)) {                // no place left for the name: an ordinary dict from here on
            detail::unshare(obj);
            dict_store(obj->dict, Obj::of(name), value);
            return;
        }
        obj->order.push_back(name);
    }
    dict_store(obj->dict, Obj::of(name), value);
}

template <class T>
inline void delattr(T* obj, const Str* name) {
    ClassObject* cls = obj->cls;
    if (auto hit = cls->lookup(name)) {
        Obj found = hit->first;
        if (found.is_object() && found.object()->kind == Kind::SlotDescriptor) {
            auto* d = static_cast<SlotDescriptor*>(found.object());
            member_applies(cls, d);
            if (d->readonly) throw AttributeError("readonly attribute");
            Obj& slot = member_cell(obj, d);
            if (slot.is_unset()) throw AttributeError(name->text);
            decref(std::exchange(slot, Obj{}));
            return;
        }
        if (is_data_descriptor(found)) {
            auto deleter = found.object()->cls->lookup(intern("__delete__"));
            if (!deleter) throw AttributeError("__delete__");
            Ref desc = Ref::share(found);                            // owned while __delete__ runs
            Ref fn = Ref::share(deleter->first);
            decref(call_method(fn.get(), desc.get(), {Obj::of(obj)}));
            return;
        }
    }
    // a delete through the object's inline values inserts the name into the shared keys before it finds the attribute missing
    // (_PyObject_StoreInstanceAttribute); once the dict is detached from the object (obj.__dict__ = d, _PyObject_SetManagedDict), a
    // delete goes through the dict and a missing name is just missing (refmodel Runtime.delattr); so is the dict a dropped object
    // gets here, whose values are its own
    if (obj->flags & DICT_DROPPED) detail::settle(obj, true);
    else if (obj->dict == nullptr && cls->has_dict && cls->dict_kind != DictKind::Inline)   // _PyObjectDict_SetItem makes the dict before it finds the name missing
        detail::settle(obj, cls->dict_kind == DictKind::Shared);
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
    if (obj->flags & DICT_DROPPED) detail::settle(obj, true);
    else if (obj->dict == nullptr && cls->dict_kind != DictKind::Inline) detail::settle(obj, cls->dict_kind == DictKind::Shared);
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

// A C type's own `Py_CLEAR(self->dict)` (partial.__setstate__ given no dict): the object has no dict again, as when it
// was made, until an attribute is set or its __dict__ is asked for. What it held goes as the dict it was (exposed
// first), released after the object let go of it (refmodel Runtime.drop_dict). Also `del obj.__dict__` of an instance whose
// class keeps a shared dict and no values in the object (del_dict sends it here). Not that of an inline class's instance,
// which is del_dict's own.
template <class T>
inline void drop_dict(T* obj) {
    if (!obj->cls->has_dict) throw AttributeError("'" + obj->cls->name + "' object has no attribute '__dict__'");
    expose_dict(obj);
    DictObject* old = std::exchange(obj->dict, nullptr);
    if (old->embedded == obj) old->embedded = nullptr;   // its values are detached from obj
    obj->flags = static_cast<decltype(obj->flags)>(obj->flags & ~DICT_EXPOSED);
    decref(old);
}

// del obj.__dict__ of an instance whose class keeps its values in the object (subtype_setdict, _PyObject_SetManagedDict(obj,
// NULL)): the object is without its dict and its inline values before anything is released, so a finaliser that runs meanwhile
// already meets the dropped object; what it held goes as the dict it was. What it gets next is settle's: nothing until
// something is asked of its instance storage. Again, with none, changes nothing. A C type's own dict slot is never deleted
// (PyObject_GenericSetDict), and an object with no values in it has no dict again, as when it was made (refmodel
// Runtime.del_dict; C-3-58, C-3-59).
template <class T>
inline void del_dict(T* obj) {
    if (!obj->cls->has_dict) throw AttributeError("'" + obj->cls->name + "' object has no attribute '__dict__'");
    if (obj->cls->dict_kind == DictKind::Plain) throw TypeError("cannot delete __dict__");
    if (obj->cls->dict_kind == DictKind::Shared) {
        drop_dict(obj);
        return;
    }
    if (obj->flags & DICT_DROPPED) return;
    expose_dict(obj);
    DictObject* old = std::exchange(obj->dict, nullptr);
    if (old->embedded == obj) old->embedded = nullptr;   // its values are detached from obj
    obj->flags = static_cast<decltype(obj->flags)>((obj->flags & ~DICT_EXPOSED) | DICT_DROPPED);
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
    if (o->flags & LISTED) unlist(o);            // a dead object leaves a collection's list, kept in the quarantine or not
    if (heap().quarantine) heap().graveyard.push_back(o);
    else {
        switch (o->kind) {
            case Kind::Instance: free_object(static_cast<Instance*>(o)); break;
            case Kind::Dict:
                if (has_attributes(o)) free_object(static_cast<DictInstance*>(o));
                else free_object(static_cast<DictObject*>(o));
                break;
            case Kind::IntInstance: free_object(static_cast<IntInstance*>(o)); break;
            case Kind::FloatInstance: free_object(static_cast<FloatInstance*>(o)); break;
            case Kind::ComplexInstance: free_object(static_cast<ComplexInstance*>(o)); break;
            case Kind::Str: free_object(static_cast<StrInstance*>(o)); break;   // an exact str's death is its destroyer's
            case Kind::Tuple: free_object(static_cast<TupleInstance*>(o)); break;   // an exact tuple's death is its destroyer's
            case Kind::List: free_object(static_cast<ListInstance*>(o)); break;     // an exact list's death is its destroyer's
            case Kind::Set: free_object(static_cast<SetInstance*>(o)); break;       // an exact set's death is its destroyer's
            case Kind::Bytes:
            case Kind::ByteArray: free_object(static_cast<BytesInstance*>(o)); break;   // an exact one's death is its destroyer's
            case Kind::Function: free_object(static_cast<Function*>(o)); break;
            case Kind::SlotDescriptor: free_object(static_cast<SlotDescriptor*>(o)); break;
            case Kind::Marker: free_object(static_cast<Marker*>(o)); break;
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
        obj->flags &= static_cast<std::uint16_t>(~DICT_EXPOSED);   // no dict and no values: what a dealloc after the collector's clear finds
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
// What a weak reference reaches: nothing once its target has died, and nothing while the target's dealloc is put off
// (its count is 0: _Py_TryIncref fails, and PyWeakref_GetRef answers that the object is gone)
inline Object* weak_target(const WeakRecord* r) {
    return r == nullptr || r->target == nullptr || (r->target->flags & PUT_OFF) ? nullptr : r->target;
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

// Returns false when the finaliser left a count: the object lives on, its finaliser spent (PEP 442). `base_weak`: the built-in base
// keeps its own weak reference list (set's), which its dealloc clears after the slots and the dict, so they are left to the caller.
template <class T>
inline bool release_attributes(T* obj, bool base_weak = false) {
    auto fin = (obj->flags & FINALIZED) ? std::nullopt : obj->cls->lookup(intern("__del__"));
    obj->flags |= FINALIZED;
    if (fin) {
        obj->refs = 1;                          // held by the finaliser's call, so it cannot die again
        Ref fn = Ref::share(fin->first);
        if (finalizer_hook() != nullptr) finalizer_hook()(fn.get(), Obj::of(obj));
        else decref(call(fn.get(), {Obj::of(obj)}));
        fn = Ref{};
        if (--obj->refs != 0) {                  // revived: it lives on, and the release left it above nought (a candidate)
            released_above_nought(obj);
            return false;
        }
    }
    obj->flags |= DEAD;
    if (heap().on_death) heap().on_death(obj);
    if (heap().checking) detail::check_not_named(obj);
    // the weak references go before everything unless the list is the built-in base's own, which its dealloc clears
    ClassObject* base = obj->cls->dealloc_base;
    if (!base_weak && (base == nullptr || !base->release_has_weak) && (obj->flags & HAS_WEAKREFS)) clear_weakrefs(obj);
    for (ClassObject* c : obj->cls->mro) {
        if (c == base) break;
        // each class's slots sorted by name, as CPython sorts them when it makes the class; a built-in type's fields in the
        // order it declares them, which is its clear function's (RefClass._release_order)
        auto names = c->own_slot_names();
        if (c->hidden.empty() && !c->slots_ordered) std::sort(names.begin(), names.end(), [](const Str* a, const Str* b) { return a->text < b->text; });
        for (const Str* s : names) decref(std::exchange(slot_cell(obj, c, s), Obj{}));
    }
    if (base != nullptr) {                       // the built-in type's own dealloc, in its order (RefObject._clear_contents)
        static const Str* const weak = intern("__weakref__");
        static const Str* const dict = intern("__dict__");
        if (!base->release_has_dict) detail::release_instance_dict(obj);     // a dict a deriving class added: gone before it runs
        for (const Str* n : *base->release) {
            if (n == weak) {
                if (obj->flags & HAS_WEAKREFS) clear_weakrefs(obj);
            } else if (n == dict) detail::release_instance_dict(obj);
            else decref(std::exchange(obj->state(n), Obj{}));
        }
        return true;
    }
    // the built-in base's clear function: its fields, the dict at its place (RefObject.dealloc)
    if (obj->cls->native.empty()) detail::release_instance_dict(obj);
    for (const Str* n : obj->cls->native) {
        if (n == intern("__dict__")) detail::release_instance_dict(obj);
        else decref(std::exchange(slot_cell(obj, nullptr, n), Obj{}));
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
                if (t->cls->struct_sequence) {   // structseq_dealloc: every field, the first one first, those past the visible ones after them (RL-593)
                    Obj past = std::exchange(t->fields[0], Obj{});
                    if (!detail::release_attributes(t)) return;
                    for (Obj& item : t->items) decref(std::exchange(item, Obj{}));
                    if (past.is_object()) {
                        if (past.object()->refs == 1 && past.object()->kind == Kind::Tuple)
                            for (Obj& item : static_cast<Tuple*>(past.object())->items) decref(std::exchange(item, Obj{}));
                        decref(past);
                    }
                    detail::bury(o);
                    return;
                }
                if (!detail::release_attributes(t)) return;
                if (o->flags & WEAK_REFERENCE) weak_holder_dies(o);
                for (auto it = t->items.rbegin(); it != t->items.rend(); ++it) decref(std::exchange(*it, Obj{}));
                detail::bury(o);
                return;
            }
            [[fallthrough]];
        case Kind::List:
            if (o->kind == Kind::List && has_attributes(o)) {    // subtype_dealloc, then list_dealloc's items, last to first
                auto* l = static_cast<ListInstance*>(o);
                if (!detail::release_attributes(l)) return;
                if (o->flags & WEAK_REFERENCE) weak_holder_dies(o);
                std::vector<Obj> items = std::move(l->items);   // list_dealloc reads ob_item as it was
                for (auto it = items.rbegin(); it != items.rend(); ++it) decref(*it);
                detail::bury(o);
                return;
            }
            [[fallthrough]];
        case Kind::Bytes:
        case Kind::ByteArray:
            if ((o->kind == Kind::Bytes || o->kind == Kind::ByteArray) && has_attributes(o)) {   // subtype_dealloc, then the octets
                auto* b = static_cast<BytesInstance*>(o);
                if (!detail::release_attributes(b)) return;
                if (o->flags & WEAK_REFERENCE) weak_holder_dies(o);
                detail::bury(o);
                return;
            }
            [[fallthrough]];
        case Kind::Set:
            if (o->kind == Kind::Set && has_attributes(o)) {     // subtype_dealloc, then set_dealloc: the weak references, the table in order
                auto* s = static_cast<SetInstance*>(o);
                if (!detail::release_attributes(s, true)) return;
                if (o->flags & HAS_WEAKREFS) clear_weakrefs(o);
                if (o->flags & WEAK_REFERENCE) weak_holder_dies(o);
                auto table = std::move(s->table);
                for (auto& e : table)
                    if (!e.key.is_unset()) decref(e.key);
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

// ---- the cycle collector (refmodel/collector.py, rule for rule): trial deletion over the buffer's candidates, then gc.c's
// sequence for what it found. What a kind holds is its traverse (`traverser`, for the runtime's kinds; the object model's own
// below); a traverse names exactly the counted references the kind's release lets go of, the tracked ones among them: one
// too many would free what lives, one too few only keeps a group. What breaks a kind's cycles is its clear (`clearer`). ----
namespace detail {
using Traverser = void (*)(Object*, std::vector<Object*>&);
inline Traverser& traverser(Kind k) {
    static Traverser table[static_cast<std::size_t>(Kind::KindCount)] = {};
    return table[static_cast<std::size_t>(k)];
}
using Clearer = void (*)(Object*);
inline Clearer& clearer(Kind k) {
    static Clearer table[static_cast<std::size_t>(Kind::KindCount)] = {};
    return table[static_cast<std::size_t>(k)];
}
inline bool walked(const Object* o) {            // tracked, alive and counted: what a collection walks
    return holds_others(o->kind, o->flags) && !(o->flags & (IMMORTAL | DEAD | PUT_OFF | TOMBSTONE)) && o->refs > 0;
}
inline void visit(Obj v, std::vector<Object*>& out) {
    if (v.is_object() && walked(v.object())) out.push_back(const_cast<Object*>(v.object()));
}
inline void visit_dict_entries(const DictObject* d, std::vector<Object*>& out) {   // dict_traverse: each value, then its key
    for (const auto& e : d->entries)
        if (!e.key.is_unset()) {
            visit(e.value, out);
            visit(e.key, out);
        }
}
// subtype_traverse (RefObject.traverse): each class's slots in the MRO, in the order its release lets them go; then the
// built-in base's fields: the dict (the dict object once exposed, else the values the object keeps, in its class's keys'
// order and then in insertion order) and its own named fields
template <class T>
inline void visit_attributes(T* obj, std::vector<Object*>& out) {
    static const Str* const dict = intern("__dict__");
    for (ClassObject* c : obj->cls->mro) {
        auto names = c->own_slot_names();
        if (c->hidden.empty() && !c->slots_ordered) std::sort(names.begin(), names.end(), [](const Str* a, const Str* b) { return a->text < b->text; });
        for (const Str* s : names) visit(slot_cell(obj, c, s), out);
    }
    auto dict_values = [&] {
        if (obj->exposed()) {
            if (obj->dict != nullptr) visit(Obj::of(obj->dict), out);
            return;
        }
        std::vector<std::pair<const Str*, Obj>> held;
        for (const Str* p : obj->cls->promoted_fields)
            if (!obj->field(p).is_unset()) held.emplace_back(p, obj->field(p));
        if (obj->dict != nullptr)
            for (const auto& e : obj->dict->entries)
                if (!e.key.is_unset()) held.emplace_back(static_cast<const Str*>(e.key.object()), e.value);
        if (obj->cls->keys)
            for (const Str* k : obj->cls->keys->names)
                for (auto& [n, v] : held) if (n == k && !v.is_unset()) { visit(v, out); v = Obj{}; }
        for (const Str* n : obj->order)
            for (auto& [m, v] : held) if (m == n && !v.is_unset()) { visit(v, out); v = Obj{}; }
    };
    if (obj->cls->native.empty()) dict_values();
    for (const Str* n : obj->cls->native) {
        if (n == dict) dict_values();
        else visit(slot_cell(obj, nullptr, n), out);
    }
}
inline void visit_callback(Object* holder, std::vector<Object*>& out) {   // a weak reference's gc_traverse: its callback
    auto it = heap().weak_records.find(holder);
    if (it != heap().weak_records.end() && it->second->callback != 0) visit(Obj::of(reinterpret_cast<const Object*>(it->second->callback)), out);
}
inline void children_of(Object* o, std::vector<Object*>& out) {
    out.clear();
    switch (o->kind) {
        case Kind::Instance: visit_attributes(static_cast<Instance*>(o), out); break;
        case Kind::IntInstance: visit_attributes(static_cast<IntInstance*>(o), out); break;
        case Kind::FloatInstance: visit_attributes(static_cast<FloatInstance*>(o), out); break;
        case Kind::ComplexInstance: visit_attributes(static_cast<ComplexInstance*>(o), out); break;
        case Kind::Dict:
            if (has_attributes(o)) visit_attributes(static_cast<DictInstance*>(o), out);
            visit_dict_entries(static_cast<DictObject*>(o), out);
            break;
        case Kind::Str:
            if (has_attributes(o)) visit_attributes(static_cast<StrInstance*>(o), out);
            break;
        case Kind::Tuple:
            if (has_attributes(o)) visit_attributes(static_cast<TupleInstance*>(o), out);
            for (Obj v : static_cast<Tuple*>(o)->items) visit(v, out);
            break;
        case Kind::List:
            if (has_attributes(o)) visit_attributes(static_cast<ListInstance*>(o), out);
            for (Obj v : static_cast<List*>(o)->items) visit(v, out);
            break;
        case Kind::Set:
            if (has_attributes(o)) visit_attributes(static_cast<SetInstance*>(o), out);
            for (const auto& e : static_cast<SetObject*>(o)->table) visit(e.key, out);
            break;
        case Kind::Bytes:
        case Kind::ByteArray:
            if (has_attributes(o)) visit_attributes(static_cast<BytesInstance*>(o), out);
            break;
        default:
            if (Traverser tr = traverser(o->kind)) tr(o, out);
            break;
    }
    if (o->flags & WEAK_REFERENCE) visit_callback(o, out);
}

// subtype_clear (RefObject.gc_clear): the slots up to the built-in base, then the base's own fields and the dict at their
// places; no finaliser and no weak reference, which the collector has seen to
template <class T>
inline void clear_attributes(T* obj) {
    static const Str* const weak = intern("__weakref__");
    static const Str* const dict = intern("__dict__");
    ClassObject* base = obj->cls->dealloc_base;
    for (ClassObject* c : obj->cls->mro) {
        if (c == base) break;
        auto names = c->own_slot_names();
        if (c->hidden.empty() && !c->slots_ordered) std::sort(names.begin(), names.end(), [](const Str* a, const Str* b) { return a->text < b->text; });
        for (const Str* s : names) decref(std::exchange(slot_cell(obj, c, s), Obj{}));
    }
    if (base != nullptr) {
        if (!base->release_has_dict) release_instance_dict(obj);
        for (const Str* n : *base->release) {
            if (n == weak) continue;
            if (n == dict) release_instance_dict(obj);
            else decref(std::exchange(obj->state(n), Obj{}));
        }
        return;
    }
    if (obj->cls->native.empty()) release_instance_dict(obj);
    for (const Str* n : obj->cls->native) {
        if (n == dict) release_instance_dict(obj);
        else decref(std::exchange(slot_cell(obj, nullptr, n), Obj{}));
    }
}
inline void clear_object(Object* o) {            // tp_clear
    switch (o->kind) {
        case Kind::Instance: clear_attributes(static_cast<Instance*>(o)); break;
        case Kind::IntInstance: clear_attributes(static_cast<IntInstance*>(o)); break;
        case Kind::FloatInstance: clear_attributes(static_cast<FloatInstance*>(o)); break;
        case Kind::ComplexInstance: clear_attributes(static_cast<ComplexInstance*>(o)); break;
        case Kind::Dict:                         // subtype_clear, then dict_tp_clear: PyDict_Clear
            if (has_attributes(o)) clear_attributes(static_cast<DictInstance*>(o));
            dict_clear(static_cast<DictObject*>(o));
            break;
        case Kind::Str:
            if (has_attributes(o)) clear_attributes(static_cast<StrInstance*>(o));
            break;
        case Kind::Tuple:                        // a tuple has no clear of its own
            if (has_attributes(o)) clear_attributes(static_cast<TupleInstance*>(o));
            break;
        case Kind::List: {                       // subtype_clear, then list_clear: the items, last to first
            if (has_attributes(o)) clear_attributes(static_cast<ListInstance*>(o));
            std::vector<Obj> items = std::move(static_cast<List*>(o)->items);
            static_cast<List*>(o)->items.clear();
            for (auto it = items.rbegin(); it != items.rend(); ++it) decref(*it);
            break;
        }
        case Kind::Set: {                        // subtype_clear, then set_clear_internal: the table in order
            if (has_attributes(o)) clear_attributes(static_cast<SetInstance*>(o));
            auto* s = static_cast<SetObject*>(o);
            auto table = std::move(s->table);
            s->table.assign(8, SetObject::Entry{});
            s->fill = s->used = s->finger = 0;
            for (auto& e : table)
                if (!e.key.is_unset()) decref(e.key);
            break;
        }
        case Kind::Bytes:
        case Kind::ByteArray:
            if (has_attributes(o)) clear_attributes(static_cast<BytesInstance*>(o));
            break;
        default:
            if (Clearer cl = clearer(o->kind)) cl(o);
            break;
    }
    if (o->flags & WEAK_REFERENCE) {             // a weak reference's gc_clear: out of its target's list, the callback released
        auto it = heap().weak_records.find(o);
        if (it != heap().weak_records.end()) {
            weak_unlink(it->second);
            std::uintptr_t callback = std::exchange(it->second->callback, 0);
            if (callback != 0) decref(Obj::of(reinterpret_cast<const Object*>(callback)));
        }
    }
}

// A collection's lists (GcList, refmodel/objects.py GcState.move/merge): an object is in one at most, LISTED while it is.
inline void list_append(Object* o, GcList& to) {
    Collector& c = collector();
    o->flags |= LISTED;
    c.where[o] = {&to, to.items.size()};
    to.items.push_back(o);
    ++to.size;
}
inline void list_move(Object* o, GcList& to) {
    unlist(o);
    list_append(o, to);
}
inline Object* list_first(GcList& l) {
    while (l.first_at < l.items.size() && l.items[l.first_at] == nullptr) ++l.first_at;
    return l.first_at < l.items.size() ? l.items[l.first_at] : nullptr;
}
inline std::vector<Object*> list_items(const GcList& l) {
    std::vector<Object*> out;
    for (Object* o : l.items) if (o != nullptr) out.push_back(o);
    return out;
}
inline bool in_list(const Object* o, const GcList& l) {
    auto it = collector().where.find(o);
    return it != collector().where.end() && it->second.first == &l;
}
inline void list_merge(GcList& from, GcList& to) {
    for (Object* o : list_items(from)) list_move(o, to);
}
inline void list_release(GcList& l) {
    for (Object* o : list_items(l)) unlist(o);
}

// mark_gray, scan and collect_white from the roots (collector.trial_deletion): what nothing outside holds, in the order taken
inline void trial_deletion(const std::vector<Object*>& roots, GcList& unreachable) {
    enum class Color : std::uint8_t { Gray, Black, White, Taken };
    struct Mark { std::int64_t count; Color color; };
    std::unordered_map<Object*, Mark> marks;
    std::vector<Object*> kids, stack;
    for (Object* root : roots) {                 // mark_gray: each reference among the reached lessens a count once
        if (marks.contains(root)) continue;
        marks[root] = {static_cast<std::int64_t>(root->refs), Color::Gray};
        stack.assign(1, root);
        while (!stack.empty()) {
            Object* o = stack.back();
            stack.pop_back();
            children_of(o, kids);
            for (Object* k : kids) {
                auto [it, fresh] = marks.try_emplace(k, Mark{static_cast<std::int64_t>(k->refs), Color::Gray});
                --it->second.count;
                if (fresh) stack.push_back(k);
            }
        }
    }
    auto scan_black = [&](Object* from) {        // held from outside: it and all it reaches get their counts back
        marks[from].color = Color::Black;
        std::vector<Object*> todo{from}, sub;
        while (!todo.empty()) {
            Object* o = todo.back();
            todo.pop_back();
            children_of(o, sub);
            for (Object* k : sub) {
                Mark& m = marks[k];
                ++m.count;
                if (m.color != Color::Black) {
                    m.color = Color::Black;
                    todo.push_back(k);
                }
            }
        }
    };
    for (Object* root : roots) {                 // scan
        stack.assign(1, root);
        while (!stack.empty()) {
            Object* o = stack.back();
            stack.pop_back();
            Mark& m = marks[o];
            if (m.color != Color::Gray) continue;
            if (m.count > 0) {
                scan_black(o);
            } else {
                m.color = Color::White;
                children_of(o, kids);
                stack.insert(stack.end(), kids.rbegin(), kids.rend());
            }
        }
    }
    for (Object* root : roots) {                 // collect_white: from each root, in the order a walk first meets them
        stack.assign(1, root);
        while (!stack.empty()) {
            Object* o = stack.back();
            stack.pop_back();
            Mark& m = marks[o];
            if (m.color != Color::White) continue;
            m.color = Color::Taken;
            list_move(o, unreachable);
            children_of(o, kids);
            stack.insert(stack.end(), kids.rbegin(), kids.rend());
        }
    }
}

// gc.c's update_refs, subtract_refs and move_unreachable over a collection's own list (collector.deduce_unreachable): `base`
// keeps what is reachable from outside it, in the order the scan keeps it; the rest moves to `unreachable`, in order
inline void deduce_unreachable(GcList& base, GcList& unreachable) {
    std::unordered_map<Object*, std::int64_t> refs;
    std::vector<Object*> order = list_items(base), kids;
    for (Object* o : order) {
        if (o->refs == 0) throw ModelError("an object is in a collection's list with no count");
        refs[o] = o->refs;
    }
    for (Object* o : order) {
        children_of(o, kids);
        for (Object* k : kids)
            if (auto it = refs.find(k); it != refs.end()) --it->second;
    }
    std::vector<Object*> kept;
    for (std::size_t i = 0; i < order.size(); ++i) {
        Object* o = order[i];
        if (in_list(o, unreachable)) continue;
        if (refs[o] > 0) {
            children_of(o, kids);
            for (Object* k : kids) {
                auto it = refs.find(k);
                if (it == refs.end()) continue;
                if (in_list(k, unreachable)) {   // visit_reachable: back to the end, scanned again
                    unlist(k);
                    order.push_back(k);
                    it->second = 1;
                } else if (it->second == 0) {
                    it->second = 1;
                }
            }
            refs.erase(o);
            kept.push_back(o);
        } else {
            list_move(o, unreachable);
        }
    }
    for (Object* o : kept) list_move(o, base);
}

inline void call_weak_callback(Obj fn, Object* holder) {
    if (weakref_callback_hook() != nullptr) weakref_callback_hook()(fn, Obj::of(holder));
    else decref(call(fn, {Obj::of(holder)}));
}
// Every weak reference with a callback to an unreachable object is cleared, the callback kept; each that is not itself
// unreachable is held and has its callback called, in order, then is released; one that lives on joins `old`. The number
// of those that died meanwhile.
inline std::int64_t handle_weakref_callbacks(GcList& unreachable, GcList& old) {
    GcList to_call;
    for (Object* op : list_items(unreachable)) {
        if (!(op->flags & HAS_WEAKREFS)) continue;
        auto lit = heap().weak_lists.find(op);
        if (lit == heap().weak_lists.end()) continue;
        std::vector<WeakRecord*> records = lit->second;
        for (WeakRecord* r : records) {
            if (r->callback == 0) continue;
            weak_unlink(r);                      // _PyWeakref_ClearRef: the target forgotten, the callback kept
            if (in_list(r->holder, unreachable)) continue;
            incref(r->holder);
            list_move(r->holder, to_call);
        }
    }
    std::int64_t freed = 0;
    while (Object* holder = list_first(to_call)) {
        auto it = heap().weak_records.find(holder);
        std::uintptr_t callback = it != heap().weak_records.end() ? it->second->callback : 0;
        if (callback != 0) {
            Ref fn = Ref::share(Obj::of(reinterpret_cast<const Object*>(callback)));
            call_weak_callback(fn.get(), holder);
        }
        decref(holder);                          // `holder` is only a key from here: it may have died
        if (in_list(holder, to_call)) list_move(holder, old);
        else ++freed;
    }
    list_release(to_call);
    return freed;
}
// Each object's finaliser, in order, once in its life, the object held (collector.finalize_garbage)
inline void finalize_garbage(GcList& collectable) {
    GcList seen;
    static const Str* const del = intern("__del__");
    while (Object* op = list_first(collectable)) {
        list_move(op, seen);
        if ((op->flags & FINALIZED) || !holds_others(op->kind, op->flags) || op->cls == nullptr || !op->cls->lookup(del)) continue;
        incref(op);
        switch (op->kind) {
            case Kind::Instance: finalize_once(static_cast<Instance*>(op)); break;
            case Kind::IntInstance: finalize_once(static_cast<IntInstance*>(op)); break;
            case Kind::FloatInstance: finalize_once(static_cast<FloatInstance*>(op)); break;
            case Kind::ComplexInstance: finalize_once(static_cast<ComplexInstance*>(op)); break;
            default:
                if (has_attributes(op)) {
                    switch (op->kind) {
                        case Kind::Dict: finalize_once(static_cast<DictInstance*>(op)); break;
                        case Kind::Str: finalize_once(static_cast<StrInstance*>(op)); break;
                        case Kind::Tuple: finalize_once(static_cast<TupleInstance*>(op)); break;
                        case Kind::List: finalize_once(static_cast<ListInstance*>(op)); break;
                        case Kind::Set: finalize_once(static_cast<SetInstance*>(op)); break;
                        case Kind::Bytes: case Kind::ByteArray: finalize_once(static_cast<BytesInstance*>(op)); break;
                        default: break;
                    }
                }
                break;
        }
        decref(op);
    }
    list_merge(seen, collectable);
}
// No unreachable object is weakly referenced any more, and no callback runs; an unreachable weak reference is cleared too
inline void clear_unreachable_weakrefs(GcList& unreachable) {
    for (Object* op : list_items(unreachable)) {
        if (op->flags & WEAK_REFERENCE)
            if (auto it = heap().weak_records.find(op); it != heap().weak_records.end()) weak_unlink(it->second);
        if (op->flags & HAS_WEAKREFS) {
            auto lit = heap().weak_lists.find(op);
            if (lit == heap().weak_lists.end()) continue;
            std::vector<WeakRecord*> records = lit->second;
            for (WeakRecord* r : records) weak_unlink(r);
        }
    }
}
// Each object's clear, the object held; one that is still first afterwards lives on and joins `old`
inline void delete_garbage(GcList& collectable, GcList& old) {
    while (Object* op = list_first(collectable)) {
        if (op->refs == 0) throw ModelError("an object of a collection's garbage with no count");
        incref(op);
        clear_object(op);
        bool kept = list_first(collectable) == op;
        if (kept) list_move(op, old);
        decref(op);
    }
}
}  // namespace detail

// A collection (collector.collect): full whatever generation is asked; the number found. One asked for while one runs finds 0.
inline std::int64_t collect_cycles() {
    detail::Collector& c = detail::collector();
    if (c.collecting) return 0;
    c.collecting = true;
    struct Done {
        ~Done() { detail::collector().collecting = false; }
    } done;
    c.scheduled = false;                          // the buffer the schedule counted is taken now
    std::vector<Object*> roots;
    for (Object* o : c.candidates) {
        o->flags &= static_cast<std::uint16_t>(~BUFFERED);
        if (o->flags & TOMBSTONE) detail::free_tombstone(o);
        else if (detail::walked(o)) roots.push_back(o);
    }
    c.candidates.clear();
    c.tombstones = 0;
    c.roots = roots.size();
    detail::GcList survivors, unreachable, final;
    detail::trial_deletion(roots, unreachable);
    roots.clear();
    std::int64_t collected = detail::handle_weakref_callbacks(unreachable, survivors);
    detail::finalize_garbage(unreachable);
    detail::deduce_unreachable(unreachable, final);   // handle_resurrected_objects: what is reachable again stays in `unreachable`
    detail::list_merge(unreachable, survivors);
    detail::clear_unreachable_weakrefs(final);
    collected += static_cast<std::int64_t>(final.size);
    detail::delete_garbage(final, survivors);
    for (detail::GcList* l : {&survivors, &unreachable, &final}) detail::list_release(*l);
    c.alive_after = containers_alive;
    ++c.collections;
    c.collected += collected;
    return collected;
}
// The runtime's look: the collection the buffer scheduled, if the collector is enabled (collector.look)
inline std::int64_t collector_look() {
    detail::Collector& c = detail::collector();
    if (!c.scheduled) return 0;
    c.scheduled = false;
    if (!c.enabled) return 0;
    return collect_cycles();
}

}  // namespace bella
