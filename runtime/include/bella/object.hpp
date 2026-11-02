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
    Singleton, Bool, BigInt, Float, Tuple, List, PyDict, Cell, PyFunction, Builtin, Method, Module,
    Range, Iterator, Traceback, Native, KindCount
};
enum Flag : std::uint16_t { IMMORTAL = 1u << 0, DEAD = 1u << 1, DICT_EXPOSED = 1u << 2 };

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
struct Heap {
    std::vector<ClassObject*> classes;          // live classes
    std::vector<Site*> sites;
    bool checking = false;
    bool quarantine = false;
    std::vector<Object*> graveyard;             // quarantined dead objects
    std::function<void(Object*)> on_death;      // called as an object dies, after its finaliser
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
        if (immortal) flags |= IMMORTAL;
        index();
    }
    Str(std::u32string_view cps, bool immortal) : Object(Kind::Str) {
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

// ---- the instance dict as an object of its own (refmodel RefDict) ----
struct DictObject : Object {
    NameMap map;
    std::shared_ptr<SharedKeys> split;           // the class keys it shares, or null: an ordinary dict
    DictObject();
    void note_key(const Str* n) {
        if (split && !split->note(n)) split.reset();   // the keys are full: an ordinary dict from now on
    }
};

// ---- native functions: what a class attribute holds where the model holds a Python callable ----
struct Function : Object {
    std::function<Obj(std::span<const Obj>)> fn;     // returns a new reference
    explicit Function(std::function<Obj(std::span<const Obj>)> f);
};

struct SlotDescriptor : Object {                     // a real __slots__ member: a data descriptor
    const Str* name;
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
    std::vector<ClassObject*> bases;
    std::vector<ClassObject*> mro;               // C3, self first
    std::vector<ClassObject*> subclasses;
    NameMap attrs;                               // owns one count of each value
    std::uint64_t version = NO_VERSION;
    std::optional<std::vector<const Str*>> slots;    // as declared; nullopt: no __slots__
    std::vector<const Str*> promoted;            // this class's own promoted fields
    std::vector<const Str*> slot_fields;         // inherited, in MRO-reversed declaration order
    std::vector<const Str*> promoted_fields;
    std::unordered_map<const Str*, std::uint32_t> field_index;   // slot fields, then promoted fields
    bool has_dict = false;
    std::shared_ptr<SharedKeys> keys;
    ClassObject() : Object(Kind::Class) { flags |= IMMORTAL; }

    std::vector<const Str*> own_slot_names() const {
        std::vector<const Str*> out;
        if (slots) for (const Str* s : *slots) if (s != intern("__dict__")) out.push_back(s);
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
    void set_attr(const Str* n, Obj v) {
        incref(v);
        Obj old = attrs.set(n, v);
        bump();
        decref(old);
    }
    void del_attr(const Str* n) {
        if (!attrs.contains(n)) throw AttributeError(n->text);
        Obj old = attrs.pop(n);
        bump();
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
    }
};

// the builtin classes of the objects this header makes: immortal, no attributes
inline ClassObject* builtin_class(const char* name) {
    static std::unordered_map<std::string, std::unique_ptr<ClassObject>> made;
    auto& c = made[name];
    if (!c) {
        c = std::make_unique<ClassObject>();
        c->name = name;
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
};

// RefClass.__init__
inline ClassObject* make_class(const ClassSpec& spec) {
    auto* c = new ClassObject();
    c->cls = builtin_class("type");
    c->name = spec.name;
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
    for (const Str* s : c->own_slot_names()) {
        if (c->attrs.contains(s)) throw ModelError("'" + s->text + "' in __slots__ conflicts with class variable");
        auto* d = new SlotDescriptor(s);
        incref(d);
        c->attrs.set(s, Obj::of(d));
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
    std::uint32_t i = 0;
    for (const Str* s : c->slot_fields) c->field_index[s] = i++;
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

inline bool is_instance(Obj v) { return v.is_object() && v.object()->kind == Kind::Instance; }
inline bool is_descriptor(Obj found) {
    return is_instance(found) && found.object()->cls->has("__get__");
}
inline bool is_data_descriptor(Obj found) {
    if (found.is_object() && found.object()->kind == Kind::SlotDescriptor) return true;
    return is_instance(found) && (found.object()->cls->has("__set__") || found.object()->cls->has("__delete__"));
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
inline std::pair<bool, Obj> instance_storage(Instance* obj, const Str* name) {
    if (obj->exposed()) {
        const Obj* v = obj->dict->map.find(name);
        return v ? std::pair{true, *v} : std::pair{false, Obj{}};
    }
    if (std::find(obj->cls->promoted_fields.begin(), obj->cls->promoted_fields.end(), name) != obj->cls->promoted_fields.end()) {
        Obj v = obj->field(name);
        if (!v.is_unset()) return {true, v};
    }
    if (obj->dict != nullptr)
        if (const Obj* v = obj->dict->map.find(name)) return {true, *v};
    return {false, Obj{}};
}
inline bool is_promoted(Instance* obj, const Str* name) {
    const auto& p = obj->cls->promoted_fields;
    return std::find(p.begin(), p.end(), name) != p.end();
}
inline Obj hook_of(ClassObject* c) {
    auto h = c->lookup(intern("__getattr__"));
    return h ? h->first : Obj{};
}
}  // namespace detail

// Python's lookup order; the plan, and the entry to cache (if any)
inline std::pair<LookupPlan, std::optional<CacheEntry>> plan_generic(Instance* obj, const Str* name) {
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
inline std::optional<LookupPlan> plan_cached(Instance* obj, const Str* name, const Site& site) {
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
                if (const Obj* v = obj->dict->map.find(name)) return LookupPlan{Plan::InstanceDict, Obj{}, *v, hook};
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
inline Ref execute(const LookupPlan& plan, Instance* obj, const Str* name) {
    Ref hook = Ref::share(plan.hook);
    try {
        switch (plan.kind) {
            case Plan::Raise:
                throw AttributeError(name->text);
            case Plan::GetAttrHook: {
                Ref fn = Ref::share(plan.found);
                return Ref::steal(call(fn.get(), {Obj::of(obj), Obj::of(name)}));
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
        return Ref::steal(call(hook.get(), {Obj::of(obj), Obj::of(name)}));
    }
}

inline Ref getattr(Instance* obj, const Str* name, Site* site = nullptr) {
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
inline void setattr(Instance* obj, const Str* name, Obj value) {
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
    if (obj->exposed()) {
        DictObject* d = obj->dict;
        incref(value);
        if (!d->map.contains(name)) d->note_key(name);
        Obj old = d->map.set(name, value);
        decref(old);
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
    if (!obj->dict->map.contains(name)) {
        obj->order.push_back(name);
        cls->keys->note(name);
    }
    incref(value);
    Obj old = obj->dict->map.set(name, value);
    decref(old);
}

inline void delattr(Instance* obj, const Str* name) {
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
    // a delete through a split dict inserts the name into the shared keys before it finds the
    // attribute missing (_PyObject_StoreInstanceAttribute)
    if (obj->exposed()) {
        obj->dict->note_key(name);
        Obj old = obj->dict->map.pop(name);
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
    if (obj->dict != nullptr && obj->dict->map.contains(name)) {
        Obj old = obj->dict->map.pop(name);
        std::erase(obj->order, name);
        decref(old);
        return;
    }
    throw AttributeError(name->text);
}

// vars(obj) / obj.__dict__: the promoted fields migrate once; stable identity afterwards. The dict
// is an object of its own from here on (one count held by the object), split: it shares the
// class's keys. Returns a new reference.
inline Ref expose_dict(Instance* obj) {
    ClassObject* cls = obj->cls;
    if (!cls->has_dict) throw AttributeError("'" + cls->name + "' object has no attribute '__dict__'");
    if (obj->exposed()) return Ref::share(Obj::of(obj->dict));
    auto* d = new DictObject();
    d->split = cls->keys;
    for (const Str* name : obj->order) {         // the references move: no count changes
        if (detail::is_promoted(obj, name)) {
            d->map.set(name, std::exchange(obj->field(name), Obj{}));
        } else {
            d->map.set(name, *obj->dict->map.find(name));
        }
    }
    if (obj->dict != nullptr) {                  // the overflow map's references moved into d
        obj->dict->map.take_all();
        decref(obj->dict);
    }
    incref(d);
    obj->dict = d;
    obj->order.clear();
    obj->flags |= DICT_EXPOSED;
    return Ref::share(Obj::of(d));
}

// obj.__dict__ = d: exposes first, then installs d (which may be shared); the old dict is released
// after the new one is held.
inline void set_dict(Instance* obj, DictObject* d) {
    if (!obj->cls->has_dict) throw AttributeError("'" + obj->cls->name + "' object has no attribute '__dict__'");
    expose_dict(obj);
    DictObject* old = obj->dict;
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
inline void release_split(std::vector<std::pair<const Str*, Obj>> items, const SharedKeys* keys) {
    std::vector<Obj> order;
    if (keys != nullptr)
        for (const Str* k : keys->names)
            for (auto& [n, v] : items)
                if (n == k && !v.is_unset()) { order.push_back(v); v = Obj{}; }
    for (auto& [n, v] : items) if (!v.is_unset()) order.push_back(v);
    for (Obj v : order) decref(v);
}
inline void bury(Object* o) {
    if (heap().quarantine) heap().graveyard.push_back(o);
    else {
        switch (o->kind) {
            case Kind::Instance: delete static_cast<Instance*>(o); break;
            case Kind::Dict: delete static_cast<DictObject*>(o); break;
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
inline void dealloc(Object* o) {
    switch (o->kind) {
        case Kind::Instance: {
            auto* obj = static_cast<Instance*>(o);
            if (auto fin = obj->cls->lookup(intern("__del__"))) {
                obj->refs = 1;                          // held by the finaliser's call, so it cannot die again
                Ref fn = Ref::share(fin->first);
                decref(call(fn.get(), {Obj::of(obj)}));
                fn = Ref{};
                if (obj->refs != 1) throw ModelError("resurrection by a finaliser is not modelled yet");
                obj->refs = 0;
            }
            obj->flags |= DEAD;
            if (heap().on_death) heap().on_death(obj);
            if (heap().checking) detail::check_not_named(obj);
            for (ClassObject* c : obj->cls->mro) {
                // each class's slots sorted by name, as CPython sorts them when it makes the class
                auto names = c->own_slot_names();
                std::sort(names.begin(), names.end(), [](const Str* a, const Str* b) { return a->text < b->text; });
                for (const Str* s : names) decref(std::exchange(obj->field(s), Obj{}));
            }
            if (obj->exposed()) {
                DictObject* d = std::exchange(obj->dict, nullptr);
                decref(d);
            } else {
                std::vector<std::pair<const Str*, Obj>> held;
                for (const Str* p : obj->cls->promoted_fields)
                    if (!obj->field(p).is_unset()) held.emplace_back(p, std::exchange(obj->field(p), Obj{}));
                if (obj->dict != nullptr) {
                    for (auto& item : obj->dict->map.take_all()) held.push_back(item);
                    DictObject* d = std::exchange(obj->dict, nullptr);
                    decref(d);
                }
                // the class's key order, then any name the keys could not take, in insertion order
                std::vector<std::pair<const Str*, Obj>> ranked;
                for (const Str* k : obj->cls->keys->names)
                    for (auto& [n, v] : held) if (n == k && !v.is_unset()) { ranked.emplace_back(n, v); v = Obj{}; }
                for (const Str* n : obj->order)
                    for (auto& [m, v] : held) if (m == n && !v.is_unset()) { ranked.emplace_back(m, v); v = Obj{}; }
                for (auto& [n, v] : ranked) decref(v);
            }
            detail::bury(o);
            return;
        }
        case Kind::Dict: {
            auto* d = static_cast<DictObject*>(o);
            d->flags |= DEAD;
            auto split = std::move(d->split);
            detail::release_split(d->map.take_all(), split.get());
            detail::bury(o);
            return;
        }
        default:
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
