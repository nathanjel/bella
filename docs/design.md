# Python → C++26 converter: design document and build plan

Oct 29, 2026 · @Marcin Gałczyński

## 1. Goals and non-goals

The converter takes annotated, lint-clean Python and produces readable C++26 that a reviewer could maintain by hand, runs faster because of what the passes prove, and computes exactly what CPython computes for every construct it admits. Five requirements changed after the feasibility review, and four of them simplify the design.

| Requirement | Status | Consequence |
| --- | --- | --- |
| Hide the Python source | Dropped | Generated C++ keeps Python identifiers, carries docstrings and comments as `//` lines, and ships a source map; no hashed names, no stripping beyond a normal release build. An optimised native binary is already impractical to reverse into Python |
| `int` behaves exactly as in Python | Hard requirement | Tagged 63-bit immediates with heap bigints, floor division, exact int-to-float comparison, CPython's hash formula and digit limit (section 6) |
| `__getattr__`, class mutation, runtime-created classes | Admitted as tiers | Literal attribute names resolve at compile time; computed names go through a per-class field table (name to offset) and a side table; a method slot written anywhere becomes an indirect call (sections 3, 4, 7) |
| Dynamism still excluded | Only `eval`, `exec` and `compile` of source strings, and frame or bytecode introspection | Compile-time error with file and line; an embedded-CPython island remains available for a package that needs them |
| A proof per pass | Hard requirement | Every IR has an executable semantics; every pass has a specification and one of four discharge methods; fused fast paths are checked against the unfused stack (sections 8, 9) |
| Annotated input | Hard requirement | ruff plus a strict type checker define the input language; the compiler refuses what they refuse (section 2) |

Goals carried over unchanged from the [feasibility study](https://claude.ai/artifact/A8j484xiYfh9VveHh1wod1): closed-world compilation with a typed interface per package, no global stop in memory management, no GIL, precompiled binaries for dependencies, MIT/BSD for everything linked into shipped artefacts (tools and test-only dependencies may carry other licences), C++26 on the newest GCC with no fallback profile (Clang is not targeted until its reflection ships; section 10.3).

Non-goals: a drop-in replacement for CPython; running unmodified C-extension packages outside the island; protection against reverse engineering beyond what any native build provides.

Readable output is a design goal rather than a by-product because it is cheap and pays twice: the generated C++ is debuggable with ordinary tools, and a team can later decide to maintain a module in C++ and retire its Python original.

## 2. Input contract: annotated Python, enforced before the compiler runs

Requiring annotations turns the type oracle from an inference engine into a checker, which is both faster and sound: a program that passes ruff with the rules below and a strict type checker has a known static type for every expression, so the compiler never guesses a type; boxed paths remain wherever the proven runtime class is weaker than the declared type (the guards described below), never as insurance against a guess. Enforcement runs as a pre-commit hook and again as the compiler's first stage; the compiler refuses what the linters refuse, so the dialect is defined by a configuration file rather than by prose.

| Rule family | ruff selector or tool | What it enforces | What the compiler gains |
| --- | --- | --- | --- |
| Annotations everywhere | `ANN001`-`ANN206` | Every parameter and return annotated | Precise types at every call boundary; the package interface file is derived from signatures, not inferred |
| No `Any` | `ANN401`; checker `disallow_any_explicit`, `disallow_any_generics` | `Any` banned; `object` must be written where boxing is intended | No boxed residue enters through signatures; `object` marks the places that box on purpose |
| No blanket ignores | `PGH003`, `PGH004` | `# type: ignore` only with a code | The checker's verdict can be trusted |
| No source-string execution | `S102` (`exec`), `S307` (`eval`) | The two hard dialect errors | Caught before compilation, with file and line |
| No star imports | `F403`, `F405` | `from m import *` | Static import graph |
| Global rebinding (advisory) | `PLW0603` | Flags `global x` followed by assignment | Advice only: the dialect admits `global` assignment (spec, section 3), so this rule is recommended for application code and never part of the input contract |
| Literal attribute names | `B009`, `B010` | `getattr(o, "x")` rewritten as `o.x` | More accesses resolve at compile time |
| Final where meant | `@final`, `Final` (checker-enforced) | Classes, methods and constants never overridden or rebound | Devirtualisation and constant folding without a whole-program proof |
| Dialect tiers (custom AST linter `bella-lint`, because ruff has no plugin API) | computed-name `getattr`/`setattr`/`delattr`, `__getattribute__`, `__setattr__`, `__class__` assignment, three-argument `type()`, `import_module` with a non-literal name, `__dict__` writes, `sys._getframe`, `inspect` frame functions | Not errors except the frame functions | Each use is reported with the tier it will land in and the cost, so the author decides knowingly (section 7) |

Checker configuration: mypy `--strict` with `disallow_any_explicit` and `warn_unreachable`, or pyrefly or ty in strict mode; all three are MIT. The exact checker and ruff versions are pinned in bella.toml and recorded in the artefact key, as is the CPython reference build (3.15.2 for dialect v0.4). `TypedDict` compiles to a struct, `Protocol` to a concept, `Literal` and `Enum` to `enum class`, `NewType` to a distinct wrapper type.

What annotations do not give, and the passes still compute: aliasing and ownership (escape analysis), integer ranges (range analysis), thread-locality, the full set of attributes an instance will ever carry (closed-world collection of every assignment), and which class slots are ever written (monkey-patch detection). Annotations are declarations, not proofs: int admits bool and subclasses, a float parameter may receive an int, stubs and ignores can be wrong, and permissively compiled dependencies hand over unverified values. The IR therefore keeps three things apart: the declared type, the proven runtime class, and the chosen representation. A native representation is used only where the proven class allows it, and every boundary where it does not (entry from permissive code, values from the island, casts, ignored errors) gets a guard that branches to the boxed path rather than raising. Annotations settle the type half of the problem; the ownership half stays with the compiler.

Two conventions in application code feed the passes directly and are worth recommending: `@dataclass(slots=True)` or an explicit `__slots__` declares the layout (no widening needed), and `Final` on module constants lets them fold at compile time. Neither is required.

## 3. Object model: the C++ draft

The runtime has two worlds. Statically typed values (`int64_t`, `double`, `py::Int`, `std::vector<T>`, generated structs) are what the compiler uses wherever the oracle gave a type; the boxed world below is the uniform representation for `object`, mixed containers, dynamic attributes and function values. The draft makes five choices, each for a reason: no C++ virtual functions (dispatch goes through the class object's slot table so that `__class__` assignment and monkey-patching stay possible); a tagged 64-bit `Obj` word so that small integers never allocate even inside boxed containers; a 24-byte header laid out for biased reference counting; a per-class field table that maps an attribute name to a byte offset, which is what makes computed-name access and `__getattr__` cheap; and an inline overflow pointer in every class without \_\_slots\_\_, null until the first undeclared attribute, so that no shared table sits on the attribute path (decision of 2026-10-30, section 12).

```cpp
// runtime/object.hpp  -- draft v5: review round three, then review log D-1; C++26 on the newest GCC
#include <atomic>
#include <cstdint>
#include <span>
#include <vector>

namespace py {

struct Object; struct ClassObject; struct Str; struct Dict; struct Shape; struct Cell; struct KwArgs; struct BaseException;

// ---- Obj: a tagged 64-bit word, either a 63-bit integer immediate or an Object* ----
class Obj {
  std::uintptr_t w_;
public:
  static Obj from_small(std::int64_t v) noexcept { return Obj{(static_cast<std::uintptr_t>(v) << 1) | 1u}; }
  static Obj from_ptr(Object* p) noexcept;                 // increments the count (see incref)
  bool         is_small() const noexcept { return w_ & 1u; }
  std::int64_t small()    const noexcept { return static_cast<std::int64_t>(w_) >> 1; }
  Object*      ptr()      const noexcept { return reinterpret_cast<Object*>(w_); }
  ClassObject* cls()      const noexcept;                  // &int_class for immediates
};

// ---- Header: 24 bytes. Every location another thread may read while this one writes is atomic. ----
enum Flag : std::uint32_t {
  IMMORTAL      = 1u << 0,  // never freed: None, True, False, interned strs, module objects (D-19)
  GC_TRACKED    = 1u << 1,  // set per object: the class may form cycles, or an instance dict was attached
  COLOR_MASK    = 3u << 2,  // trial-deletion colour, written only by the collector thread
  BUFFERED      = 1u << 4,  // already in a candidate buffer
  DICT_EXPOSED  = 1u << 5,  // __dict__ was exposed or replaced: promoted fields now live in the dict, inline slots are dead
};

struct ObjHeader {
  std::atomic<ClassObject*>  cls;     // __class__ assignment: release store; readers: acquire load
  std::uint32_t              owner;   // id of the allocating thread; written once
  std::uint32_t              local;   // count used by the owner thread; non-atomic by construction (collector access: section 14)
  std::atomic<std::uint32_t> shared;  // count used by every other thread
  std::atomic<std::uint32_t> flags;   // fetch_or / fetch_and, relaxed
};
static_assert(sizeof(ObjHeader) == 24);

struct Object : ObjHeader {};         // no virtual functions, by design

// Instances whose class layout inherits a __dict__ (spec, section 3) derive from this; the slot sits at offset 24.
// Two kinds of inline field exist above it: real __slots__ fields, which never appear in __dict__, and promoted
// fields, the attributes CPython would keep in __dict__ that the compiler keeps inline until the dict is exposed.
struct DynamicObject : Object {
  std::atomic<Dict*> dict;  // null until the first undeclared write or the first __dict__ exposure; created by CAS.
                            // Exposure (vars(obj), obj.__dict__, obj.__dict__ = d) migrates every promoted field into an
                            // ordinary dict, sets DICT_EXPOSED, and from then on promoted attributes go through the dict.
                            // The dict is an ordinary object: it outlives its owner if referenced, may be shared by two
                            // objects, and holds no pointer back into the owner, so the owner is finalised on schedule.
};

// ---- Ref<T>: intrusive, biased-counted handle; the only way to hold an Object ----
template <class T> class Ref { /* incref on copy, decref on destruction, as in v1 */ };

inline void incref(Object* o) noexcept {
  if (o->flags.load(std::memory_order_relaxed) & IMMORTAL) return;
  if (o->owner == this_thread_id()) ++o->local;
  else o->shared.fetch_add(1, std::memory_order_relaxed);
}
void decref(Object* o) noexcept;  // merges local and shared on zero; destruction cascades synchronously (spec, section 9)

// ---- Protocol results that are richer than a C++ bool ----
enum class CompareOp : std::uint8_t { Lt, Le, Eq, Ne, Gt, Ge };
struct IterStep {                       // the internal advance operation used by for, comprehensions and yield from
  enum : std::uint8_t { Yielded, Finished } kind;
  Obj value;                            // yielded value, or StopIteration.value on Finished
  Ref<BaseException> stop;              // the StopIteration instance when __next__ raised one (subclass, args, identity
                                        // preserved); null when a compiled iterator finished without creating one.
};                                      // Python-visible next(it) re-raises stop if present, else raises StopIteration(value);
                                        // every other exception propagates as a C++ exception and never becomes a step.

// ---- Protocol slots: one atomic function pointer per dunder; every writer bumps the class version ----
template <class F> using Slot = std::atomic<F*>;
struct Slots {
  Slot<Obj(Object*, std::span<const Obj>, const KwArgs*)> call;
  Slot<Obj(Object*, const Str*)>          getattr;     // full lookup; callers keep inline caches
  Slot<void(Object*, const Str*, Obj)>    setattr;
  Slot<Obj(Object*, Obj)>                 getitem;
  Slot<Obj(Object*)>                      iter;
  Slot<IterStep(Object*)>                 next;
  Slot<bool(Object*)>                     truth;       // __bool__ must return bool, else TypeError is thrown here
  Slot<std::size_t(Object*)>              len;
  Slot<std::int64_t(Object*)>             hash;        // the reduced hash, as hash() returns it
  Slot<Obj(Object*, Obj, CompareOp)>      richcompare; // returns any object or NotImplemented; truth is taken only
                                                       // where the operation needs it (if, while, filter, sort)
  Slot<bool(Object*, Obj)>                eq_bool;     // fast path, present only when the class's __eq__ is proved to return bool
  Slot<Str*(Object*)>                     repr;
  Slot<Obj(Object*, Obj)>                 add;         // one entry per dunder of the data model
  Slot<void(Object*)>                     dealloc;
  Slot<void(Object*, void(*)(Obj))>       trace;       // for the cycle collector; also walks the instance dict
};

// ---- Field table: how a computed name reaches a static field (the address delta) ----
enum class TypeTag : std::uint8_t { Obj, Int, Float, Bool, Str, Ref };
struct FieldEntry {
  std::uint64_t name_hash;   // hash of the interned attribute name
  const Str*    name;
  std::uint32_t offset;      // byte offset from the object base; the slot holds Unset until first assignment
  TypeTag       tag;
  bool          promoted;    // true: a __dict__ attribute kept inline (migrates on exposure); false: a real __slots__ field
};

// ---- Class versions: one process-wide counter (review log D-1, 2026-11-01), as CPython's type version tags ----
// A new class and every mutation of a class or any base take a number never issued before, so a version names one class
// in one state and a class created at a dead class's address cannot match the dead class's cache entries (C-3-12).
// 0 is never a version: after 2^64 - 1 numbers the counter stays at 0, and a class that takes it is never cached again.
inline std::atomic<std::uint64_t> next_class_version{1};
inline std::uint64_t new_class_version() noexcept {
  std::uint64_t v = next_class_version.load(std::memory_order_relaxed);
  do { if (v == 0) return 0; }
  while (!next_class_version.compare_exchange_weak(v, v + 1, std::memory_order_relaxed));
  return v;
}

// ---- Class object: one per Python class, created at module initialisation (reference-counted, D-19) or at runtime ----
enum ClassFlag : std::uint32_t {
  HAS_INSTANCE_DICT = 1u << 0, HAS_GETATTR = 1u << 1, HAS_GETATTRIBUTE = 1u << 2, HAS_SETATTR = 1u << 3,
  CYCLE_FREE = 1u << 4, DICT_MODE = 1u << 5, MAY_RECEIVE_COMPUTED_WRITES = 1u << 6,
};
struct ClassObject : Object {
  const Str*                    name;
  std::span<ClassObject*>       mro;            // C3 order, self first; immutable after creation
  std::span<ClassObject*>       subclasses;     // direct subclasses; each takes a new version when this class does; a
                                                //   dying class leaves its bases' lists
  std::span<const FieldEntry>   fields;         // sorted by name_hash; empty in dict mode
  std::span<std::atomic<void*>> methods;        // one slot per method name, index fixed in the closed world
  Slots                         slots;
  std::atomic<std::uint64_t>    version;        // new_class_version() at creation and on every mutation of this class or
                                                //   any base; caches compare it; 0: never cached
  std::atomic<Dict*>            class_attrs;    // attributes added to the class after definition; lazy; owns the values
  Shape*                        root_shape;     // non-null only for dict-mode classes
  std::size_t                   instance_size;
  std::uint32_t                 cflags;
};
Ref<Object> class_dict_view(ClassObject*);      // Cls.__dict__: a read-only mapping proxy; writes raise TypeError
// Compiled code and layouts are immortal metadata; class objects themselves are ordinary objects collected by the cycle
// collector when unreachable. In the threaded runtime a replaced class attribute is retired under RCU, never freed
// while a reader may hold a cache entry that names it (section 14).

// ---- Builtins (sketch) ----
struct Str : Object { std::size_t nbytes; std::int64_t hash; std::uint32_t sflags; char data[]; };  // PEP 393 kinds per string (decision 3)
struct BigInt : Object { std::uint32_t nlimbs; bool negative; std::uint64_t limbs[]; };
struct ListObject  : Object { std::vector<Obj> items; };
template <class T> struct TypedList : Object { std::vector<T> items; };
struct DictObject  : Object { CompactDict<Obj, Obj> map; };     // also the instance dict after exposure: an ordinary dict
struct TupleObject : Object { std::size_t n; Obj items[]; };
struct FunctionObject : Object {                                 // created at module initialisation, reference-counted
  Obj (*entry)(std::span<const Obj> args, const KwArgs* kw, Cell* const* closure);   // the immortal compiled code
  std::span<Cell*> closure; std::vector<Obj> defaults; std::span<const Str*> kwnames; // defaults are owned: del f releases them
};
struct DynObject : DynamicObject { Shape* shape; Obj* values; };   // instance of a class created at runtime

// ---- Attribute access: Python's order at every tier, with cache entries that say when they are valid ----
struct ICacheEntry {            // immutable metadata once published; a call site holds up to N of these behind one
                                //   std::atomic<const ICacheEntry*> stored with release and loaded with acquire;
                                //   beyond N entries the site is megamorphic and always takes the generic path
  std::uint64_t  version;       // the class and its state: versions are never reissued (D-1), so no class pointer is kept
  std::uintptr_t cls_hint;      // the class's address as a number: an install replaces this class's older entries by it;
                                //   never dereferenced and never part of validity
  const Str*    name;           // interned; literal sites have one name, computed-name sites key on it
  Shape*        shape;          // dict-mode instances only
  enum Kind : std::uint8_t { DataDescriptor, Field, InstanceDict, ClassAttr, GetAttrHook, ShapeSlot } kind;
  std::uint32_t offset; TypeTag tag;
  const Object* found;          // BORROWED: what the class lookup found (for Field and InstanceDict, the class-level object
                                //   the instance storage shadows); the class owns it, and the entry is valid only while
                                //   version matches, so a replaced attribute is never read through a stale entry
  std::uint64_t found_version;  // the version of found's class: catches a descriptor whose own class gained or lost
};                              //   __set__ without touching this class; 0: found cannot change its status
// An entry is used only if version equals the object's class version (never 0), and then, if found_version is not 0,
// found->cls->version equals found_version: read only after the first check, when the class still owns found and found
// holds its class (D-1); reading the class through found also sees a __class__ assignment to found. Then, by kind:
//   Field          : the inline slot is not Unset and DICT_EXPOSED is clear; otherwise the slow path
//   ClassAttr      : no instance storage shadows the name: the promoted inline field for name (if declared) is Unset,
//                    and the instance dict is null or has no entry for name
//   GetAttrHook    : same instance-storage check as ClassAttr
//   InstanceDict   : the dict pointer is non-null; probe by the cached hash; a miss falls back to the generic lookup
//   ShapeSlot      : the instance's shape pointer equals shape
//   DataDescriptor : nothing further; found is called
Obj  getattr_generic(Object* self, const Str* name, std::atomic<const ICacheEntry*>* ic);
// order: data descriptor on the class (MRO) -> instance storage (promoted field or instance dict, or the dict alone
//        once DICT_EXPOSED) -> non-data descriptor or class attribute -> __getattr__ -> AttributeError
void setattr_generic(Object* self, const Str* name, Obj v, std::atomic<const ICacheEntry*>* ic);
// order: a __setattr__ override replaces everything; otherwise data descriptor with __set__ -> real __slots__ field
//        -> promoted field (or the dict once DICT_EXPOSED) -> instance dict (created by CAS, sets GC_TRACKED)
Ref<Dict> expose_dict(DynamicObject* self);     // vars(obj) / obj.__dict__: migrates promoted fields, sets DICT_EXPOSED, returns the dict
void      set_dict(DynamicObject* self, Dict* d); // obj.__dict__ = d: exposes first, then installs d (shared or new); the old dict lives on
} // namespace py
```

How `obj.name` is resolved, decided at compile time per access:

1. Python's order comes first, at every tier: a data descriptor found on the class along the MRO (a `property`, a slot descriptor) wins over instance storage; then instance storage (a declared field or an instance-dictionary entry); then a non-data descriptor or plain class attribute; then `__getattr__`; then `AttributeError`. Every shortcut below is a proof that the earlier steps cannot apply.
2. Class known, no data descriptor for `name` in the closed world, `name` a declared field, `DICT_EXPOSED` clear: a direct load or store at the known offset; the C++ compiler sees `p->x`. A declared field holds the `Unset` sentinel until it is first assigned; a read of `Unset` takes the slow path (class attribute, `__getattr__`, `AttributeError`), which is also how `del obj.x` behaves. Real `__slots__` fields never migrate; promoted fields (the attributes CPython would keep in `__dict__`) migrate into the dictionary when it is exposed.
3. Class known, `name` not a field, class defines `__getattr__`: if the class can receive computed-name writes anywhere in the program (`MAY_RECEIVE_COMPUTED_WRITES`), the instance dictionary is checked first (a null test, then a probe); otherwise a direct call of the generated `__getattr__`. If the class defines `__getattribute__`, every access on it is a call, which the compiler knows per class.
4. Class known, `name` not a field, no `__getattr__`: if any code in the program assigns `obj.name` on this class under a literal name, the field has already been added to the layout (layout widening); otherwise the instance dictionary is consulted and `AttributeError` raised on a miss.
5. Class unknown, or name computed: the call site holds up to N immutable cache entries behind one atomic pointer loaded with acquire. An entry is keyed by the class version, the interned name and, for dict-mode instances, the shape; the version alone identifies the class, because versions are never reissued (Class versions, below). It also records the version of the found object's class, read through the found object, so a descriptor whose own class gains or loses `__set__` invalidates the entry even though the containing class did not change. The entry's kind carries a validity check beyond those: an `Unset` or exposed field, a promoted inline field or instance-dictionary entry that would shadow a cached class attribute, a missing instance dictionary. The found object is a borrowed reference owned by the class: every entry is invalid the moment the class version moves, so a replaced attribute is never read through a stale entry, and the class releases the old attribute on replacement (under RCU in the threaded runtime), so cache entries never prolong a Python object's life. A mutation of a class gives it and every subclass a new version (the closed world enumerates subclasses; a runtime-created subclass registers with its bases and leaves them when it dies); a site that needs more than N entries goes megamorphic and always takes the generic path.
6. Computed writes follow the same order as literal ones: a `__setattr__` override if the class has one, else a data descriptor's `__set__`, then a real `__slots__` field, then a promoted field, then the instance dictionary. Nothing writes to the dictionary directly.
7. `vars(obj)` and `obj.__dict__` expose the instance dictionary: on first exposure the object's promoted fields migrate into an ordinary `dict`, `DICT_EXPOSED` is set, and from then on those attributes go through the dictionary; the result is a real `dict` with stable identity (`vars(obj) is vars(obj)`, `type(vars(obj)) is dict`) and an independent lifetime, so it stays usable after `del obj` while `obj` is finalised on schedule. `obj.__dict__ = d` exposes first, then installs `d`, which may already be another object's dictionary; the previous dictionary lives on for whoever holds it. `Cls.__dict__` is a read-only mapping proxy. `__class__` assignment uses CPython's layout-compatibility criterion (section 13, finding 4).

**Class versions (2026-11-01, review log D-1).** Versions come from one process-wide 64-bit counter, as CPython's type version tags do, not from a counter per class. With per-class counters starting at 0, a class created where a dead class used to be would carry the dead class's number, and a site still holding the dead class's entry would accept it: a field offset from another layout, or a `found` freed with the old class. Conformance case C-3-12 reads one attribute through one call site on twelve classes that die in turn, and CPython 3.15.2 places ten of them at the same address. Measured on 3.15.2 through `tp_version_tag`: two new classes took consecutive tags, a modification sets a class's tag to 0 and the next lookup assigns the next number (to every subclass as well), and a class created at a dead class's address got a fresh tag.

A number that is never reissued has three consequences. An entry keeps no class pointer, only `cls_hint`, the class's address as an integer, which decides which older entry an install replaces and nothing else. The found object's class is reached through `found`, and only after the class version matched: the class then still owns `found`, `found` holds its class, and reading the class through `found` also notices a `__class__` assignment to it. And 0 is never a version: the counter issues 2^64 − 1 numbers, after which a class that needs a new one takes 0 and is never cached again, as CPython does when its tags run out. CPython also stops giving one class new tags after 1000 modifications, to ration a 32-bit space; Bella sets no such limit, since one number per nanosecond lasts 584 years. The reference model adopted the counter first (`VersionCounter` in `refmodel/objects.py`; the oracle's `recreate_class` operation drops a runtime-created class and creates another): with versions tied to the class address instead, its self-check served a dead class's entry to the class born at its address on the first seed, and reported it.

Undeclared attributes live in a per-instance dictionary slot (decision of 2026-10-30, section 12). An instance has the slot exactly when its class's layout inherits a `__dict__`: `object` and the other built-in bases provide none, a class defined without `__slots__` adds one, and a class with `__slots__` adds one only if `'__dict__'` is listed, so a fully slotted hierarchy has none and a class with `__slots__ = ()` under an unslotted base keeps the base's. Such classes derive from `DynamicObject` and carry one atomic pointer at offset 24, null until the first undeclared write or the first exposure of `__dict__`, created by compare-and-swap. Inline fields come in two kinds: real `__slots__` fields, which never appear in `__dict__`, and promoted fields, the attributes CPython would keep in `__dict__` that the compiler keeps inline for speed until the dictionary is exposed, at which point they migrate into it and the object routes those attributes through the dictionary. The dictionary is an ordinary object with its own lifetime: it survives `del obj`, two objects may share one, and it holds no pointer back into its owner; attaching it sets `GC_TRACKED` so that a reference stored there can still close a collectable cycle.

The header (2026-11-02, task 3). `runtime/include/bella/object.hpp` is written from the reference model, rule for rule, single-threaded first: a 16-byte header with a plain count (biased counting comes with threads), classes disposed but not freed (the cycle collector frees them later), instance storage and dictionaries in standard containers (the compact layouts are phase-2 work). It implements the lookup plans, the versioned caches with borrowed `found`, and the lifetimes the model states: a store keeps the new value before it releases the old one, a class mutation takes a new version before it releases the old attribute, and a dying instance runs its finaliser, then releases its `__slots__` (most-derived class first, each class's sorted by name as `type_new` stores them; review log RL-178) and then its instance attributes in the class's shared-keys order, which the class keeps beside each instance's own insertion order (case C-9-08). While user code runs, a lookup owns what it found, as CPython's `_PyType_LookupRef` does: the `__getattr__` hook until the operation ends, a descriptor and its method while that method runs (review log RL-169; the cache entries stay borrowed). Its checking mode compares every cached read with the generic lookup and fails when an object dies while an entry a live class still validates names it. `make object-test` runs the reference model's random programs three ways in lockstep, on the model, on CPython and on the header (through a thin `ctypes` binding), and compares every outcome, every death and every attribute after every operation, also under AddressSanitizer and UBSan, and user code that empties the class it runs from, without the quarantine, under the same sanitizers. The draft above stays the target for the threaded runtime.

## 4. The object model at work: seven cases

Each case shows the Python as the author writes it and the C++ the converter emits; the emitted code is what a reviewer will read, so it keeps the Python names.

**Case 1: a frozen dataclass.** The common case, and the one that reaches native speed.

```python
@dataclass(slots=True)
class Point:
    x: int
    y: int
    def norm2(self) -> int:
        return self.x * self.x + self.y * self.y
```

```cpp
// geometry/point.cppm -- generated from geometry/point.py
export module geometry.point;
import py.runtime;
export namespace geometry::point {

struct Point final : py::Object {
  py::Int x;                                   // offset 24
  py::Int y;                                   // offset 32
  static py::ClassObject cls_;                 // fields {x, y}; methods {norm2}; eq, hash, repr from dataclass
  py::Int norm2() const {             // final and never reassigned anywhere: direct, inlinable
    return py::int_add(py::int_mul(x, x), py::int_mul(y, y));
  }
};
inline py::Ref<Point> make_Point(py::Int x, py::Int y) { return py::alloc<Point>(&Point::cls_, x, y); }

}  // namespace geometry::point
```

A call `p.norm2()` becomes `p->norm2()` and `p.x` becomes `p->x`. When range analysis proves `x` and `y` stay within 30 bits in a given loop (so the sum of the two squares stays below 2^61), that loop gets a specialised `int64_t` version of `norm2` with no overflow checks; the obligation is discharged by Z3 at build time (section 9).

**Case 2: `__getattr__`, literal and computed names.**

```python
class Settings:
    def __init__(self, raw: dict[str, str]) -> None:
        self._raw = raw
    def __getattr__(self, name: str) -> str:
        try:
            return self._raw[name]
        except KeyError:
            raise AttributeError(name) from None

s = Settings(load())
host = s.host            # literal name
port = getattr(s, key)   # computed name
```

```cpp
struct Settings final : py::DynamicObject {                // no __slots__: carries the instance-dict slot at offset 24
  py::Ref<py::TypedDict<py::Str, py::Str>> _raw;
  static py::ClassObject cls_;                          // cflags: HAS_GETATTR
  py::Ref<py::Str> __getattr__(const py::Str* name) {
    if (auto* v = _raw->map.find(name)) return *v;      // try/except KeyError lowered to find
    throw py::AttributeError(name);
  }
};
// s.host: 'host' is not a field; a computed-name setattr may have stored it, so instance storage is checked before __getattr__
auto host = s->dict.load(std::memory_order_acquire) ? py::dict_get_or_getattr(s.get(), py::intern("host"))
                                      : s->__getattr__(py::intern("host"));
// getattr(s, key): computed name, one slow path, no dialect error
static std::atomic<const py::ICacheEntry*> ic_17{nullptr};   // keyed by the class version and the interned name
auto port = py::getattr_generic(s.get(), key.get(), &ic_17);   // fields (none) -> class attrs -> side -> __getattr__
```

**Case 3: an attribute assigned outside `__init__`, and one assigned under a computed name.**

```python
class Node:
    def __init__(self, value: int) -> None:
        self.value = value
        self.next: Node | None = None

n = Node(1)
n.visited = True          # literal name, assigned in another module
setattr(n, flag_name, 1)  # computed name
```

```cpp
struct Node : py::DynamicObject {                 // no __slots__: atomic instance-dict slot at offset 24, null until needed
  py::Int            value;
  py::Ref<Node>      next;      // None is a distinct immortal object; the handle holds its address
  py::Unset<py::Bool> visited;  // added by layout widening: every literal name ever assigned to a Node is a field;
                                // reading it while unset raises AttributeError, so behaviour is unchanged
  static py::ClassObject cls_;  // GC_TRACKED: Node -> Node can form a cycle
};
// setattr(n, flag_name, 1): a computed name takes the generic path: __setattr__ override, data descriptor,
// declared field, then the instance dictionary (created by CAS on first use; sets GC_TRACKED)
static std::atomic<const py::ICacheEntry*> ic_23{nullptr};
py::setattr_generic(n.get(), flag_name.get(), py::Obj::from_small(1), &ic_23);
```

**Case 4: a monkey-patched method.** The closed world contains a write to `Point.norm2`, so that one slot becomes writable and its calls become indirect; nothing else about `Point` changes.

```python
def fast_norm2(self: Point) -> int:
    return self.x * self.x + self.y * self.y
Point.norm2 = fast_norm2
```

```cpp
Point::cls_.methods[Point::SLOT_norm2] = reinterpret_cast<void*>(&fast_norm2);
// every call site of norm2 on a Point, or on a subclass that did not override it:
auto r = reinterpret_cast<py::Int (*)(Point*)>(p->cls->methods[Point::SLOT_norm2])(p.get());
```

**Case 5: a class created at runtime.** The oracle has typed `r` as `object`, so every access is a shape lookup through an inline cache, the same cost as a JavaScript property.

```python
Rec = type("Rec", (), {"kind": "r"})
r = Rec()
r.a = 1
```

```cpp
auto Rec = py::make_class(py::intern("Rec"), /*bases*/ {}, /*namespace*/ ns);   // DICT_MODE, root_shape set
auto r = py::alloc<py::DynObject>(Rec.get());
static std::atomic<const py::ICacheEntry*> ic_42{nullptr};   // ShapeSlot entries for a dict-mode instance
py::setattr_generic(r.get(), py::intern("a"), py::Obj::from_small(1), &ic_42);  // shape transition {} -> {a}
```

**Case 6: a mixed container and a function used as a value.** Integers stay unboxed inside `Obj`, and a module-level `def` is one immortal `FunctionObject`.

```python
handlers: list[Callable[[int], None]] = []
handlers.append(on_tick)
items: list[object] = [1, "a", Point(1, 2)]
```

```cpp
auto handlers = py::make<py::TypedList<py::Ref<py::FunctionObject>>>();
handlers->items.push_back(on_tick_fn);
auto items = py::make<py::ListObject>();
items->items = { py::Obj::from_small(1), py::Obj(py::intern("a")), py::Obj(make_Point(1, 2)) };
```

**Case 7: `__class__` assignment.** Allowed exactly when CPython allows it: both classes have the same layout. Dispatch goes through `cls->slots`, so swapping the class pointer is the whole operation.

```python
class Draft(Doc): ...
class Published(Doc): ...
d.__class__ = Published
```

```cpp
py::set_class(d.get(), &Published::cls_);   // compares the two field tables (at compile time when both classes are known);
                                            // raises TypeError on a layout mismatch, as CPython does
```

What the seven cases show together: the first case runs at C++ speed because the compiler proved everything; each later case gives up exactly one thing (an inline call, a direct load, a static layout) and keeps the rest, and no case changes what the program computes.

## 5. Object layout at a glance

&#91;embedded content: object layout · instance, class object, side table, dict-mode object\]

The left column is what generated code touches on every access; the right column is consulted only on a miss, and the dict-mode object at the bottom is the one shape a class created at runtime can take.

## 6. `int` exactly as Python

`py::Int` is an 8-byte value type, never null and never an `Object`: it lives inline in struct fields, vectors and `Obj` words, and only the overflow representation (`BigInt`) is heap-allocated. Every observable behaviour of CPython's `int` is kept; speed comes from the 63-bit fast path and from range analysis, never from changing the semantics.

| Python behaviour that programs observe | Implementation |
| --- | --- |
| Unbounded magnitude; results never wrap | 63-bit immediate; on overflow the operation promotes to `BigInt` (64-bit limbs on a copy of SEL's bn (MIT, the author's own; decision of 2026-11-02): schoolbook multiplication below 32 words and Karatsuba above, Knuth's algorithm D and Barrett division, divide-and-conquer decimal conversion); results shrink back to immediates when they fit |
| `bool` is a subclass of `int`: `True + True == 2`, `type(True) is bool` | `py::Bool` is a distinct static type that widens to `Int` in arithmetic; boxed, `True` and `False` are immortal objects of class `bool`, never int immediates |
| `//`, `%`, `divmod` round toward minus infinity; `ZeroDivisionError` | Helpers below; the zero check is elided only where range analysis proves the divisor nonzero |
| `/` is true division and returns `float`; `2 ** -1` returns `float`; `pow(a, b, m)` is modular | Lowered per protocol; int-to-float conversion correctly rounded for large ints (CPython's algorithm), `OverflowError` above the double range |
| Mixed `int`/`float` comparison is exact: `2**53 + 1 == 2.0**53` is `False` | Comparison through the float's exact integer decomposition, not through converting the int to `double` |
| `hash(n) == n % (2**61 - 1)` with the sign kept; `hash(-1) == -2` | Same formula, so persisted hashes and user `__hash__` methods agree with CPython |
| `str(n)` and `int(s)` at any size; underscores; bases 2 to 36; `sys.set_int_max_str_digits` (default 4300) | Divide-and-conquer conversion; the digit limit kept as a runtime setting for compatibility |
| Bitwise operators act on an infinite two's-complement representation; `~x == -x - 1` | Machine-word fast path; bigint path with sign handling |
| `int` subclasses (`IntEnum`, user classes) | Boxed `IntObject` carrying a `cls`; arithmetic unboxes and returns plain `int`, as CPython does |
| No overflow ever, and speed where it is provable | Range analysis proves a value stays within 63 bits (loop counters, `len`, indices, bounded arithmetic); such variables become `int64_t`; each proof is checked by Z3 at build time (section 9) |

```cpp
// runtime/int.hpp -- draft
class Int {
  std::uintptr_t w_;                     // bit 0 = 1: 63-bit immediate; bit 0 = 0: BigInt*
public:
  static constexpr std::int64_t kMin = -(std::int64_t{1} << 62);
  static constexpr std::int64_t kMax =  (std::int64_t{1} << 62) - 1;
  static Int from_small(std::int64_t v) noexcept { return Int{(static_cast<std::uintptr_t>(v) << 1) | 1u}; }
  static Int raw(std::int64_t tagged) noexcept { return Int{static_cast<std::uintptr_t>(tagged)}; }
  bool is_small() const noexcept { return w_ & 1u; }
  std::int64_t small() const noexcept { return static_cast<std::int64_t>(w_) >> 1; }
};

inline Int int_add(Int a, Int b) {
  if (a.is_small() & b.is_small()) {     // (2x+1) + (2y+1) - 1 = 2(x+y)+1: one add, one overflow check
    std::int64_t r;
    if (!__builtin_add_overflow(static_cast<std::int64_t>(a.w_), static_cast<std::int64_t>(b.w_) - 1, &r))
      return Int::raw(r);
  }
  return bigint::add(a, b);              // allocates; normalises back to an immediate when it fits
}

inline Int int_floordiv(Int a, Int b) {
  if (a.is_small() & b.is_small()) {
    const std::int64_t x = a.small(), y = b.small();
    if (y == 0) throw ZeroDivisionError("integer division or modulo by zero");
    if (x == Int::kMin && y == -1) return bigint::floordiv(a, b);   // quotient 2^62 leaves the tagged range
    std::int64_t q = x / y;
    const std::int64_t r = x % y;
    if (r != 0 && ((r < 0) != (y < 0))) --q;   // floor toward minus infinity
    return Int::from_small(q);           // fits once the kMin / -1 case is excluded above
  }
  return bigint::floordiv(a, b);
}

inline Int int_mod(Int a, Int b) {
  if (a.is_small() & b.is_small()) {
    const std::int64_t x = a.small(), y = b.small();
    if (y == 0) throw ZeroDivisionError("integer division or modulo by zero");
    std::int64_t r = x % y;
    if (r != 0 && ((r < 0) != (y < 0))) r += y;  // sign follows the divisor
    return Int::from_small(r);
  }
  return bigint::mod(a, b);
}

// Specialisation the compiler emits only when the certificate covers every intermediate and the result:
// x, y in [-2^30, 2^30) keeps each square below 2^60 and the sum below 2^61. The earlier claim of
// [-2^31, 2^31) overflowed int64_t at the sum; it is kept in section 13 as the example Z3 must reject.
inline std::int64_t norm2_fast(std::int64_t x, std::int64_t y) noexcept { return x * x + y * y; }
```

The literal `0x7FFF_FFFF_FFFF_FFFF + 1` and a loop that doubles a counter a hundred times both produce the same digits as CPython; the first takes the bigint path immediately, the second promotes on the 62nd iteration. Multiplication uses `__builtin_mul_overflow` on the untagged values; shifts, powers and bitwise operators follow the same shape. The bigint layer is a copy of SEL's bn (decision of 2026-11-02; licence entry L-05 settled as own code): Bella owns the copy and changes it freely, starting with entry points that write into the object's own limbs, and its header names SEL's commit and every change, so that fixes can be carried back. The Python layer on top (floor division and modulo, two's-complement bitwise operators, three-argument pow, the hash modulo 2^61 - 1, to\_bytes and from\_bytes, correctly rounded conversion to float, the digit limit) is Bella's.

`float` (decisions of 2026-11-02). The digits come from libstdc++'s `std::to_chars` (shortest, and with a precision) and `std::from_chars`. On the pinned GCC 16.2.0 they matched CPython 3.15.2 on about 3.2 million printing cases and 1.5 million parsing cases, and differed only where an out-of-range input makes `from_chars` report an error and Python returns an infinity or a zero, which the wrapper supplies. Both sides are fixed by a specification (the shortest string that reads back, the nearest when several qualify; correct rounding for a precision), so only a bug can make them differ; `make float-diff` reruns the differential in the image, and every GCC bump must pass it. Python's own layer (`repr`'s layout rule, `format`, `round`, `float.hex`, the parser's spellings) is ported. CPython's `dtoa.c` was not taken. The alternative kept on record, and the fallback if the differential ever fails or licence entry L-09 (libstdc++) is refused, is Bella's own Schubfach and Eisel–Lemire on the `bn` copy. The `math` functions CPython takes from the platform C library call glibc's libm, linked dynamically, so they return what CPython returns on the same machine (spec section 6, v0.13).

## 7. Dynamic features as tiers, not errors

The feasibility study was wrong to list `__getattr__` and class mutation next to `eval`: they do not need the interpreter, only a lookup table, and the closed world lets the compiler compute exactly which classes and which slots need one. Every row below keeps CPython's observable behaviour; the tier number is the cost, and `bella-lint` reports it at the line that incurs it.

| Feature | Tier | Mechanism | Cost per use |
| --- | --- | --- | --- |
| `obj.name` with a literal name, declared field | 0 | Direct load or store at a known offset | None |
| Literal name first assigned outside `__init__`, anywhere in the program | 0 | Layout widening: the field is added to the class, unset until assigned | One optional field per instance |
| `__getattr__` | 1 | Direct call on literal-name misses; part of the generic path for computed names | One call |
| `Cls.method = f`, `setattr(Cls, "literal", v)` | 1 | That method slot becomes writable; calls through it are indirect | One indirect call instead of an inlined one |
| `obj.__class__ = Other` | 1 | `set_class` with a field-table equality check | One check |
| `__getattribute__`, `__setattr__`, `__delattr__` overrides | 2 | Every access on that class becomes a call to the override | One call per access on that class |
| `getattr`/`setattr`/`delattr` with a computed name | 2 | Inline cache keyed by class version, then Python's order: data descriptor on the class, declared field (name hash to offset), overflow dictionary, class attribute along the MRO, `__getattr__` | Cache hit: typed load; miss: binary search plus a hash probe |
| `setattr(Cls, computed, v)`, `Cls.__dict__` writes | 2 | Class-level overflow dict; literal lookups on that class carry a guard | One dict probe on a miss |
| `vars(obj)`, `obj.__dict__` reads | 2 | `__dict__` is a real `dict` with stable identity, materialised once into the object's dictionary slot; entries for declared fields read and write the inline slots; `obj.__dict__ = d` installs `d` and detaches the inline fields for that object; `Cls.__dict__` is a read-only mapping proxy | One dictionary per object, materialised once; detached objects pay a dictionary probe per access |
| `importlib.import_module(computed)`, `__import__` | 2 | Registry of compiled modules; `ModuleNotFoundError` outside the closed world | One hash probe |
| `globals()[name]`, `locals()` reads | 2 | Module globals have a name-to-offset table like fields; `locals()` inside a function returns a fresh mutable dictionary whose writes do not affect the variables (PEP 667) | One probe or one snapshot |
| `type(name, bases, ns)`; a class body that depends on runtime values | 3 | `DynObject` with hidden classes (shapes) and inline caches | One shape lookup per access, cached |
| Stateful multiple inheritance with a non-primary base | 3 | Flattened layout; methods of non-primary bases instantiated per concrete class (deducing `this`) | Larger binary, no runtime cost |
| `eval`, `exec`, `compile` on source strings; `sys._getframe`, `inspect.currentframe`, code objects, bytecode, `f_locals` | excluded | Compile-time error with file and line; a package that needs them goes to the embedded-CPython island | Not applicable |

Why the closed world makes this sound: the compiler sees every write to every class, every literal attribute name, every `__class__` assignment and every `import_module` call in the program, so frozen is a per-class and per-slot fact it proves, never a promise the author makes. Only computed names escape that analysis, and they fall back to tables that do what CPython does on every access anyway.

Why the overflow dictionary is safe: it is owned by its object, created by compare-and-swap, freed with the object, and traced by the collector once attached; there is no address-keyed table and nothing to evict. The cost of the decision is 8 bytes per instance of every class without `__slots__`, which is what CPython pays too.

What an author gains by staying in tiers 0 and 1: the C++ output reads like hand-written C++ with plain members and direct calls, which is the readability goal of section 1 in practice.

## 8. IR levels and the pass framework

The pipeline is built the nanopass way: many small passes, each from one formally defined language to the next, with the traversal boilerplate generated from the language definitions so that a pass contains only the rules that change something. This is the structure the Chez Scheme compiler uses, and it is what makes a proof per pass tractable: a pass that touches three node kinds has three proof cases, not a whole-tree induction.

| Level | Grammar | Invariant added at this level | Executable semantics |
| --- | --- | --- | --- |
| L0 lossless tree | Python 3.15 syntax with positions, comments and tokens | None | CPython itself |
| L1 PyCore | Desugared Python | No comprehensions, `with`, decorators, f-strings, chained comparisons, `match`; every protocol call explicit (`Iter`, `Next`, `Truth`, `GetAttr`); staged class and module bodies replaced by their snapshots | `eval1`, a reference interpreter in plain Python |
| L2 Typed IR | ANF with explicit types | Every expression carries a type from the oracle (phase 1, decision of 2026-11-02: a type slot on every place, always object; the oracle's types are a marked gap until phase 2, when a pass produces Fact.TYPES); `object` is the only boxed type; every operation is a named protocol op | `eval2` |
| L3 Ownership IR | L2 plus ownership, thread and cycle facts | Every allocation has an owner class (value, unique, local-shared, cross-thread, immortal); every object type is marked cycle-capable or cycle-free; every handle carries its thread class | `eval3`, which also checks the facts at runtime (an escaping value marked local aborts the run) |
| L4 C++ intent IR | A C++ program as a tree | Resolved types, no dangling references, every construct printable as idiomatic C++26 | Print, compile with GCC or Clang, run |

Each level is a set of Python dataclasses generated from a grammar file, with a well-formedness predicate `wf_i` (scoping, typing, the invariant column above) and a structural-equality and pretty-printer pair, so that any tree can be dumped, diffed and re-parsed. The grammars are the specification of the compiler; they are reviewed before the passes are written.

L2 v1 (decisions of 2026-11-02; `docs/l2.md`). Names come in six kinds decided statically, as CPython's symbol table decides them; expressions are in A-normal form in Python's evaluation order; every operation is a named protocol operation. Reference drops are `release` statements at the points CPython drops them (an operation's operands after it, last evaluated first; a frame's locals in reverse slot order). The exception edge is a rule, not statements: the live temporaries die newest first, which C++ unwinding gives. `eval2` runs L2 on host objects, every temporary in one slot that `release` deletes, so the host's reference counting runs finalisers where L2 says; a checking mode asks the host's `gc.get_referrers` at every release whether `eval2` itself still holds the object, `eval2` unwinds explicitly, and a generated probe covers each kind of release point. `eval2` is the first level exact about lifetimes: the lifetime cases compare it with CPython directly, and `eval1` keeps no finaliser traces. Exceptions are C++ exceptions, as section 12 decided; a throw costs about 1.7 µs against CPython's 0.2 µs for a raise (measured in the image), so the runtime never throws for a miss it expects (the end of an iterator, `getattr` with a default, `dict.get`), and a phase-2 pass rewrites the common try-and-catch idioms. Each function has a frame record on the C++ stack (its code and current line); during unwinding a guard declared after the locals appends the frame to the traceback and moves the locals into it, so they die with the traceback, as in CPython.

Every pass is registered with a specification record, and the pass manager will not run a pass whose record is incomplete:

```python
@dataclass(frozen=True)
class PassSpec:
    name: str
    source: Level              # input language
    target: Level              # output language (same level for analysis passes)
    requires: frozenset[Fact]  # facts that must be present on the input (types, ranges, escape, ...)
    produces: frozenset[Fact]  # facts this pass adds
    invalidates: frozenset[Fact]
    obligations: tuple[Obligation, ...]
    discharge: Discharge       # one of the four rungs of section 9
    status: Literal["stated", "tested", "validated", "proved"]

@dataclass(frozen=True)
class Obligation:
    kind: Literal["wf", "semantics", "fact_sound", "terminates"]
    statement: str             # e.g. "for all x: wf_1(x) implies wf_2(P(x))"
```

The four obligation kinds, stated once and instantiated per pass:

1. Well-formedness: `wf_i(x)` implies `wf_i+1(P(x))`.
2. Semantic preservation: `eval_i+1(P(x), input)` is observationally equal to `eval_i(x, input)`. Observational equality is defined by the dialect: same output, same return value, same exception class and message, same sequence of effects on the inputs. It declares `id()` values, the timing of finalisers for cyclic objects, and dictionary memory layout unobservable.
3. Fact soundness, for analysis passes: every fact recorded holds on every execution (a range contains every value the variable takes; an object marked thread-local is never touched by another thread).
4. Termination: a measure that decreases on every rewrite step.

The pass manager builds a dependency graph from `requires`, `produces` and `invalidates`, so the order of passes is derived, not hand-maintained, and a new pass slots in by declaring its facts. Example records: the range pass requires types, produces ranges, invalidates nothing, and is discharged by translation validation; the desugaring of `with` requires nothing, produces nothing, and is discharged by a mechanised proof because its rule is small and its semantics (exception suppression by `__exit__`) is easy to get subtly wrong.

## 9. Proof ladder, composition, and fusion

A formal proof per pass is affordable only if "proof" is graded: every pass must reach the first rung before it ships, optimising passes must reach the second, and the small semantic passes climb to the fourth over the life of the project. The rung a pass sits on is recorded in its `PassSpec.status`, and the build prints the ladder so the proof debt is visible.

| Rung | Method | Applies to | Tooling | What it costs |
| --- | --- | --- | --- | --- |
| 1 Tested | Executable semantics plus differential testing: random well-formed `L_i` programs generated and shrunk by Hypothesis; `eval_i(x)` compared with `eval_i+1(P(x))` under the observational-equality definition; a conformance corpus derived from CPython's own test suite checks `eval1` against CPython | Every pass | Hypothesis (MPL-2.0, a test dependency never linked into the output); the reference interpreters | Days per pass |
| 2 Validated | Translation validation: each compilation emits a certificate for the pass's claims and a checker verifies it with Z3 (MIT) before the result is used; a failed check discards that function's optimisation, falls back to the conservative lowering, and logs a compiler bug | Range analysis, bounds-check elimination, overflow-check elimination, escape facts under a conservative points-to model, devirtualisation (a syntactic absence of slot writes) | Z3 through its Python bindings; one SMT query per function, bounded by a timeout | Weeks per pass, then milliseconds per build |
| 3 Checked | Verified checker, unverified pass: the pass emits a witness that a small, separately proved checker validates | Cycle-freedom classification (witness: a topological order of the type graph), C3 linearisation (witness: the order, checked against the C3 definition), module initialisation order | A few hundred lines per checker | Days per checker |
| 4 Proved | Mechanised proof of the pass itself, the CompCert and CakeML way: the pass and both semantics defined in a proof assistant, the theorem proved, the implementation extracted or transliterated and kept in differential testing against the Python one | Desugaring rules (`with`, comprehensions, chained comparisons), exception lowering, closure conversion, ANF conversion | Lean 4 (decision of 2026-10-30; a tool, so its licence is not constrained); a formal core calculus modelled on the tested Python semantics of Politz et al. ("Python: the full monty") | Months per pass |

Why this order and not a verified compiler from day one: CompCert took a decade for a language with a 300-page semantics and no dynamic typing; Python has no official formal semantics at all. The ladder gives a tested pipeline at rung 1 on the first day (every pass is checked against an executable oracle; testing is evidence, not proof), makes the optimisations the only place where a wrong proof could change results and guards exactly those with per-build validation, and spends mechanisation where it buys the most: the small rules whose errors are subtle rather than loud.

Composition. Observational equality is transitive, so the whole pipeline preserves semantics if each pass does; the pipeline's proof is the conjunction of the pass proofs and no separate argument is needed. What is not a pass needs obligations of its own: the runtime library (a conformance suite against CPython), the emitter (sequencing and well-formedness, section 13), staging (the recorded-input contract of section 10.2), plugins (their conformance suites), and the C++ compiler, which is trusted as CompCert's assembler is trusted; a bug there is found by the differential test of the final binary against CPython, which stays in CI permanently.

Fusion and scheduling, done last. Once passes are individually at rung 1 or higher and the per-pass compile-time profile exists, adjacent passes that are pure traversals with no fact invalidation between them can be fused into one traversal (desugaring with symbol resolution; protocol resolution with truthiness lowering; range analysis with bounds-check elimination). A fused pass carries one extra obligation, equivalence to the sequence it replaces, discharged at rung 1 against the unfused stack, which is kept as the oracle in CI. The pass manager chooses the order from the fact graph and fuses only where the profile shows a gain, so the optimal stack is measured, not designed; it is never built before the individual passes have their proofs, because fusing unproved passes only makes their errors harder to localise.

## 10. Memory, concurrency, libraries, build: what carries over

The [feasibility study](https://claude.ai/artifact/A8j484xiYfh9VveHh1wod1) sections 6 to 9 stand as written; this section records only what the five changes alter in them.

| Area | Carried over unchanged | Changed by this document |
| --- | --- | --- |
| Memory (study, section 6) | Five tiers: static ownership, arenas, non-atomic counting, biased counting with immortal and deferred objects, concurrent trial-deletion cycle collection over candidate roots; mimalloc; growth governor | Revised after review round one (section 13): deferred counting is dropped, stack references are always counted, and functions, classes and modules created at initialisation are immortal instead, so no stack scanning is ever needed. Cycle tracking is per object as well as per class: a side-table or overflow write that stores a reference sets `GC_TRACKED` on the object, so a scalar-only class can still form a collectable cycle. Destruction cascades synchronously, as in CPython, so refcount-triggered finaliser timing is exact; deferral is allowed only for classes proven free of finalisers and weak references. One collector thread processes the union of all threads' candidate buffers; under memory pressure the escalation is a bounded all-thread handshake, so the claim is no global stop in steady state. Safepoints are polled at loop back-edges and calls; blocking calls leave the epoch on entry and rejoin on return |
| Concurrency (study, section 7) | Per-object critical sections elided by thread-locality; hazard pointers and RCU for the runtime's tables; `threading` on `std::jthread`; finalisers queued to the owning thread | Revised after review rounds one and two: every location one thread may write while another reads is a `std::atomic`. Pointers to published immutable structures (inline-cache entries, class objects, instance dictionaries) are stored with release and loaded with acquire, because a relaxed load of the pointer does not make the pointee's fields visible; counts and flags use relaxed read-modify-write. Inline-cache entries are never freed: a call site holds at most N and goes megamorphic beyond that, which bounds memory without a reclamation protocol. A reader holding an entry whose class has just been mutated is conjectured to observe a legitimate interleaving; that claim stays unproven until the phase-4 snapshot protocol is specified (section 14), and memory safety comes from replaced attributes being retired under RCU. Still open for phase 4 (section 14): collector access to an owner thread's non-atomic local count, re-homing objects whose owner thread exited, and reconciling synchronous finalisation with finalisers queued to the owning thread. Class-level overflow dicts are one more runtime table under hazard pointers |
| Libraries (study, section 8) | Four package classes, typed interface files, module units, LTO, the embedded 3.15t island | Revised after review round one: exported classes keep a stable layout. Only fields declared inside their own package are inline; attributes added by another package go to the overflow pointer or the side table (tier 2), so precompiled binaries and the offsets compiled into them stay valid, and `bella-lint` reports when application code adds attributes to a library class. An optional whole-program mode re-specialises dependencies from retained IR and keys its cache on the widening facts, invalidating dependants transitively. The bridge is version-specific (section 13, finding 8). CPython 3.15 gives free-threaded builds a stable ABI (PEP 803, `abi3t`), which makes a stable-ABI bridge possible; the version-specific bridge stays the baseline until the bridge's API needs are known, and the choice is made before phase 3 |
| C++ feature map (study, section 9) | As written | Readable output adds `std::source_location`-free source maps (a sidecar file, no runtime cost) and keeps Python identifiers; reflection in the runtime now generates `__repr__`, `__eq__`, hashing and keyword binding for the hand-written classes only |
| Performance (study, section 11) | As written | No change: dropping source hiding costs nothing at runtime |
| Licensing (study, section 12) | As written | Hypothesis (MPL-2.0) is a test-time dependency only; Lean 4 is the proof assistant; tools and test-only dependencies may carry licences other than MIT/BSD (decision of 2026-10-30) |

One build-level consequence of readable output: generated C++ is checked in to the user's repository as a build artefact that reviewers can diff, which makes compiler regressions visible in code review rather than only in benchmarks, and lets a CI stage build from the committed C++ without running the converter (decision of 2026-10-30).

## 10.1 Dependency policy and the island

The compiler chooses the strategy for every dependency once per lockfile change, from `bella.toml`, and prints a ledger of what it chose and why; the author overrides per package, and `island = "forbid"` makes the build fail instead of quietly embedding CPython. The choice is per package and never per function: two implementations of one package would mean two incompatible object representations inside one program.

Default rule, in order: pure Python compiles; a registered intent mapping maps; a ctypes or cffi ABI binding links the C library directly; everything else goes to the island. Mappings are versioned packages of their own (`bella-map-numpy`), pinned to the mapped package's API version and tested differentially against the real package under CPython with the same harness as the compiler itself, so third parties can contribute them.

```toml
[island]
mode = "forbid"              # "allow" (default) prints the ledger; "forbid" fails the build
topology = "subinterpreter"  # default when allowed: "single" | "subinterpreter" | "process"

[packages.numpy]
strategy = "map"             # bella-map-numpy, version-pinned

[packages.pandas]
strategy = "island"
topology = "process"         # bulk, batched calls; keeps its GIL out of the main process
workers = 2

[packages.pyyaml]
strategy = "compile"
prefer_pure = true           # compile the pure-Python fallback instead of islanding the C accelerator
```

The avoidance ladder, cheapest first:

1. Forbid the island and read the ledger. Most non-numeric applications (command-line tools, services on httpx or requests, json, re, sqlite, logging, asyncio) touch only stdlib C modules, which have mappings, and build island-free.
2. Prefer pure fallbacks. Many packages ship a pure-Python implementation beside an optional C accelerator (PyYAML, msgpack, markupsafe, simplejson); the compiled fallback is usually faster than the accelerator was under CPython.
3. Map thin wrappers. Packages whose C core wraps a C library (sqlite3, zstd, lxml over libxml2, psycopg over libpq, numpy over BLAS and LAPACK) get a shim onto the same library, small compared to the package; numpy's commonly used subset (ndarray, slicing, broadcasting, ufuncs, reductions, matmul, random, basic linalg) is a multi-month mapping, as Codon's compiled NumPy showed.
4. Island what remains: pandas, torch, PyO3-based packages (pydantic-core, orjson), Cython-generated giants, numba, gevent. Their coupling to the CPython API is too deep to map. Emulating the C API on the converter's own runtime, PyPy's cpyext approach, is ruled out: PyPy and GraalPy each spent years on it, it stays slow and fragile, and HPy was created because of that pain.

Clusters. Island packages are partitioned into clusters, the connected components of their import graph: pandas imports numpy and shares its arrays, so they must share an interpreter, while an unrelated crypto package need not. One extension without free-threading support anywhere in a cluster re-enables the GIL for that whole cluster's interpreter. Mitigations therefore act per cluster, and there are three topologies:

&#91;embedded content: island topologies · in-process, per-cluster subinterpreters, separate process\]

Subinterpreters are one process and one address space, not multiple processes; what they multiply is heaps. Topology A has two heaps, B has one heap per cluster plus the compiled program's, and C has the same count spread over processes. The two-heaps problem exists in all three: references crossing a boundary are proxies in both directions (pointer proxies in A and B, integer handles in C), a cycle that spans two heaps is collectable by neither collector and is treated as a root, so such cycles leak, and anything that crosses is marked escaped and loses arena allocation and non-atomic counting. Islands never reference each other, so the shape is always a star around the compiled program.

| Topology | Heaps and address space | GIL scope | Call cost | What it needs | Isolation |
| --- | --- | --- | --- | --- | --- |
| A. One interpreter in-process | One process; compiled heap plus one island heap | One GIL for the whole island as soon as any extension lacks free-threading support | About 0.3 µs per scalar call; buffers zero-copy through the buffer protocol | One pinned 3.15t minor and its full C API, so the bridge is rebuilt per Python release; 3.15's `abi3t` (PEP 803) is the stable-ABI option to revisit before phase 3 (section 10) | None: an extension crash kills the program |
| B. One subinterpreter per cluster, in-process | One process; compiled heap plus one heap per cluster (per-interpreter allocator state and `sys.modules`; a package used by two clusters is loaded twice) | Per interpreter: a legacy extension re-enables the GIL only for its own cluster | About 0.3 µs plus a thread-state switch; every OS thread that calls a cluster needs one thread state per interpreter, created lazily | Every extension in the cluster must support a per-interpreter GIL (multi-phase init and the `Py_mod_multiple_interpreters` slot); numpy declared no sub-interpreter support for years, so check each package | None against crashes |
| C. One process per cluster, or k processes | One address space per island; references are integer handles, never pointers | Irrelevant: every process owns its GIL, and k processes give real parallelism for a GIL-bound package | 5 to 20 µs per call (futex wake and context switch); scalars serialised; arrays zero-copy through shared-memory segments the island allocates into | A small RPC layer with a reverse channel for callbacks; 50 to 200 ms spawn per process at start-up | Full: crashes, memory, even the Python version |

Recommended defaults: B for clusters whose extensions all support per-interpreter GILs, C for bulk-call clusters that would otherwise bring a GIL into the process (pandas, torch inference), A only when the whole island is free-threading-ready. The policy file can pin any of them per cluster.

What the island costs whenever it is used, regardless of topology: per-call overhead that makes element-wise calls in a loop a performance bug (`bella-lint` flags an island call inside a loop); results typed only as well as the package's stubs, so a loose stub turns values into boxed island handles downstream; libpython plus the package's shared objects in the artefact, pinned to one 3.15t minor; stack traces split at the boundary; and one PSF-licensed component in the build. The ledger exists so that none of this is a surprise.

```
package    strategy   detail                         call sites        note
numpy      map        bella-map-numpy 2.3.1         14                0 crossings
pandas     island     process x2 (cluster: pandas)   3                 all in batch functions
pyyaml     compile    pure fallback                  -                 -
orjson     island     subinterpreter (cluster: orjson)  41             12 inside loops  <- warning
```

## 10.2 Extension model

The core compiler knows no package and no framework. Everything package-specific is a plugin against the same pass framework, with the same `PassSpec` records and the same proof ladder, so adding support for a library or a framework never touches the core. Five generic mechanisms carry that; none of them names a framework.

**1. Intent plugins.** One plugin kind with two flavours, both versioned packages (`bella-plugin-<name>`) installed per project and listed in the dependency ledger:

- Library mappings lower calls into a package's API onto a C++ library or onto a facility the runtime already has (an array package onto `mdspan`, `linalg` and its own vendored BSD kernels; an event-loop package onto the runtime's libuv loop).
- Specialisation passes rewrite a framework's definition-time dynamism into tier-0 code once staging has made its registries static: a class whose field list is fixed after bootstrap becomes a struct with typed fields and an unrolled constructor; a configuration object becomes compile-time constants; a template file becomes a render function whose attribute names are literals.

```toml
# bella-plugin-<name>/plugin.toml
[plugin]
name = "<name>"
targets = "<package>>=2.1,<2.4"     # version range of the package this plugin understands
kind = "mapping"                    # or "specialisation"
passes = ["ndarray-lowering", "ufunc-fusion"]   # each with a PassSpec (section 8)
conformance = "tests/vs_cpython"   # differential tests against the real package under CPython
license = "BSD-3-Clause"
```

A plugin's passes declare the facts they require and produce, so the pass manager schedules them like any other pass, and each one sits on a rung of the proof ladder (section 9); a specialisation pass that cannot show its rewrite is observationally equal is not loaded.

**2. Staging entrypoints.** Frameworks build their registries at import time behind a bootstrap call. `bella.toml` declares such calls, and the compiler runs them in the host CPython before taking the snapshot:

```toml
[staging]
entrypoints = ["<framework>.setup", "myapp.bootstrap:configure"]
```

Rules: an entrypoint runs in a sandbox that records every external input it touches (environment variables, files, the clock, randomness, sockets) and fails the build on any input not declared in bella.toml; declared inputs are hashed into the artefact key, so a value frozen at build time is a stated build-profile decision rather than an accident. Running the entrypoint twice catches nondeterminism, not environment dependence; the recorded inputs do that. Whatever an entrypoint cannot run under these rules stays runtime-initialised. The snapshot is the closure of classes, descriptors, registries and constants reachable from the imported modules after the entrypoints return, which is why definition-time mutation of classes is harmless: staging sees the final state.

**3. Permissive mode for dependencies.** The annotated-input contract of section 2 binds the user's own code. Third-party code compiles with stubs for its interface (typeshed, the package's `.pyi` files, or a `*-stubs` package) and inference inside; unannotated internals land in whatever tiers they earn. The ledger reports every dependency's tier profile (the share of attribute accesses and calls at tiers 0, 1, 2 and 3), so the priority list for writing plugins is measured, not guessed: packages whose tier-2 and tier-3 accesses dominate CPU get specialisation passes; packages whose calls dominate wall time and have a C counterpart get mappings.

**4. Runtime-facility mappings.** The runtime exposes its facilities under stable names (event loop, regex engine, JSON, hashing, compression, SQLite, BLAS and LAPACK, `mdspan` and `simd`) so that a mapping can target one by name instead of shipping another library. A package that is itself a binding to the same library the runtime uses becomes a thin alias; a package with an optional C accelerator and a pure fallback takes `prefer_pure` and compiles the fallback.

**5. Coverage before speed.** The phase order of section 11 follows from the first four: the object model, staging and the tier machinery are what every real program exercises, so they are built and proved first, and the typed fast path comes second. The first external release is therefore a compiler that runs whole dynamic programs correctly, boxed, without CPython and without a GIL; the second makes them fast.

## 10.3 Backend: C++26 source on GCC, and the compiler-as-a-library question

Decision of 2026-10-30: the primary backend stays C++26 source compiled by GCC 16, with no C++23 fallback profile and no Clang target for now. A compiler-as-a-library backend (libgccjit) is reserved for a possible JIT tier later; it is not how programs are built.

Why C++ source rather than driving GCC through libgccjit. libgccjit is GCC's JIT and ahead-of-time library, the backend of Emacs native-comp and of rustc\_codegen\_gcc; it accepts a C-level program (types, functions, blocks, expressions) and never runs the C++ front end. The four lowerings the design delegates to the C++ front end would therefore become passes of our own, each with proofs, and the C++26 features the project wants would become unreachable.

| What the C++ front end does for the design | What a libgccjit backend would need instead |
| --- | --- |
| Templates and monomorphisation (`std::vector<T>`, ranges, concepts) | An instantiation pass of our own over a C-level IR |
| Coroutines (`std::generator`, `co_await`, frame elision) | A state-machine lowering of our own for generators and async |
| RAII: destructors on every exit path, the basis of counting correctness | Explicit `decref` on every path including unwinding, the error class CPython's own C code is known for |
| Exceptions: tables, personality routine, handler matching | Try/catch support was built for libgccjit by the rustc\_codegen\_gcc project; availability in a given upstream GCC release has to be checked |
| The standard library and the C++26 features (reflection, `std::simd`, `std::linalg`, `std::execution` when it lands) | Not reachable: they live in the front end and in library headers |
| Readable, reviewable output (section 1) | None: only GIMPLE dumps or a reproducer that rebuilds the context |
| Cross-inlining of runtime primitives (`int_add`, `incref`) into generated code | Only through LTO across object files, or by re-emitting the primitives through the library |

What libgccjit would buy: no text round-trip and no C++ parsing or template instantiation at build time, which is the dominant compile-time cost on the source route; and in-process compilation, which is what a JIT tier needs.

Licence: [libgccjit is GPLv3 without the GCC Runtime Library Exception](https://inbox.sourceware.org/jit/1421717715.4255.73.camel@surprise), by its maintainer's statement, so anything linked against it must be GPLv3-compatible. For an MIT-licensed compiler that means a separate GPL-licensed helper process behind a pipe, never a linked library. MIT-licensed alternatives at the same C level (MIR, QBE) have the same feature gap.

Where it fits later: a JIT tier for call sites that stay megamorphic at runtime, or an in-process `exec` once the compiler is self-hosted and ships inside the binary. The IR design keeps that door open: a C-level IR below the C++ intent IR can be added without touching the levels above it.

GCC 16 as the only toolchain. The language side of C++26 is largely there (reflection behind `-freflection`, contracts behind `-fcontracts`, pack indexing, expansion statements, `=delete("reason")`), so generated code may use it freely. The library side is partial: libstdc++ has no `std::execution` yet, [the `std::hazard_pointer` implementation was submitted for review in August 2026](https://gcc.gnu.org/pipermail/libstdc++/2026-August/067526.html) (GCC 17 at the earliest), while `std::simd` ships in libstdc++ 16 itself (namespace `std::simd`, `std::simd::vec<T>`, per P3287 and P3441; `make probes`, 2026-11-01). The runtime wraps these behind its own interfaces (a libuv scheduler, xenium for hazard pointers) and swaps the standard versions in as libstdc++ ships them; generated code never sees the difference. Compile time on the source route is kept in hand by C++20 modules for the runtime, built module interfaces per package, cached package binaries, `-O1` developer builds, and LTO on release builds only.

The phase 5 gate changes accordingly: every optimising pass at rung 2 of the proof ladder or higher; "GCC and Clang agree" is dropped.

## 10.4 The phase-1 library: import guards and the `codeop` shim

The phase-1 library is the dependency closure that `tools/closure.py` computes from `manifest.toml` against the pinned standard library (spec, section 7). Two decisions of 2026-11-01 fix how the closure reads import guards (review log D-3) and how `traceback` gets `codeop` (review log D-4).

Import guards (D-3). Every import gets exactly one class, in this order of precedence:

| Class | Where the import stands | Closure | When the target is outside the manifest |
| --- | --- | --- | --- |
| dead | Under a guard that is false on the target: constants, the module's own `__name__`, and `sys.platform`, `os.name` and membership in `sys.builtin_module_names` from the manifest's `[platform]` table, directly or through a module-level name bound once to them | Not followed, never compiled | Nothing to declare; the lock lists the import with its line |
| optional | Inside `try`/`except ImportError` or `with suppress(ImportError)` | Followed if in the manifest | `[omissions]`: ImportError at runtime, as if not installed |
| lazy | Inside a function body, guarded or not | Followed if in the manifest | `[lazy_unsupported]`: that function is unsupported in phase 1 |
| guarded | At module level under a guard the build cannot evaluate, or in an exception handler | Always followed | An error: the module is required |
| eager | At module level, unguarded or under a true guard | Always followed | An error: the module is required |

Before D-3, every guarded import was one class, "conditional", and could be declared an omission. An `if` inside a function then became a silent ImportError at runtime, although spec section 7 calls only ImportError-guarded imports optional. Now an omission means exactly what CPython does when a module is not installed. A platform test is decided at build time from facts that the tool checks against the interpreter it runs on (the pinned build on Linux). A name the module binds twice, deletes, binds inside a loop or `try`, or that a function declares `global`, is not assumed inside functions, and a star import may rebind any public name. On 3.15.2 the closure finds 14 dead import edges: an `if _false:` block in codecs and the Windows branches of `os`, `shutil`, `encodings` and `_colorize`, `uuid`'s non-Linux branch and `heapq`'s `__main__` block. Twelve entries left `[omissions]`: six were platform branches or `__main__` blocks, and six named imports that 3.15.2 no longer makes. `logging`'s `pickle` import, inside `Logger.__reduce__`, moved to `[lazy_unsupported]`.

The unit of `[lazy_unsupported]` is the function (the author's decision, 2026-11-01): calling a function that contains an import of a module outside the manifest raises with the milestone name, whichever path the call would take. So `copy.copy(logger)` is refused in phase 1, because it runs `Logger.__reduce__`, although that path imports `pickle` only for a logger that is not the registered one. Refusing at the import statement when it runs would admit more programs, but it would make support depend on the path a run takes, and the manifest could no longer say which APIs a phase-1 program may call.

**The closure on 3.15.2 (2026-11-01).** `make closure` passes on the pin: 175 modules (112 compiled, 37 mapped, 19 core, 7 shims). The Docker image computes the same `closure.lock.json` byte for byte, so CI now requires the committed lock to match. Four mechanisms closed the manifest without approximating:

- **`first-use` edges** for PEP 810 lazy imports (16 in the phase-1 library). They are followed as required, as spec section 7 says. `__lazy_modules__` is read per imported module, with the value it has at that statement (measured on 3.15.2), and any other form than a literal assigned at module level is an error. The lock is an inventory: the compiler takes each binding's laziness from the import statement itself.
- **`[replaced]`** names functions an adaptation replaces, whose imports do not count. The first was `traceback._find_incompatible_extension_module` (the others are at this section's end). It would import `importlib.resources.readers`, and through it `zipfile`, to look for extension modules built for another Python version; in a closed world it returns None.
- **`[dynamic]`** records a review of every import with a computed name, one key per site (`"<function>: <name expression>"`): eight sites in six modules, all closed-world lookups at runtime. Only `encodings.search_function` must find something, the ten phase-1 codecs. Neither half of the tool could see them: there is no static import, and they load at interpreter start-up, which the observation subtracts.
- **Consistency checks.** A module may have one status, and `[omissions]` or `[lazy_unsupported]` may not name a module the manifest provides. Nine entries broke this: `_decimal`, `_datetime`, `_hashlib` and `_uuid` were both mapped and omitted; `random`'s `_sha2`, `pathlib`'s `pwd` and `grp`, and `locale`'s `_locale` were omitted although mapped; `_thread` was core and a shim. Spec section 7 decided each one (`decimal` and `datetime` via their Python versions, the `locale` subset needs `_locale`), and the licence rule decided `_hashlib` (OpenSSL is Apache-2.0).

New in 3.15 and now listed: `_py_warnings`, `pathlib._os` and `_missing_stdlib_info` (compiled), `math.integer` (mapped with `math`), `_types` (core) and `annotationlib`. That last one is a shim, because its FORWARDREF and STRING formats rebuild functions from `__code__` (E-02, E-07), and its users need it at staging. Since decision S-1 (2026-11-01, `docs/staging.md`) the compiler generates, for each `__annotate__`, a second entry point that evaluates the same expressions against the globals and cells it is given. The shim, CPython's own module with eight marked changes in `runtime/shims/annotationlib.py`, calls it where CPython rebuilds the function, so FORWARDREF and STRING are CPython's. The same holds for PEP 695 evaluate functions. The entry point needs the L2 grammar to express name loads through a given mapping. Its generator is prototyped in `pipeline/staging/annotations.py` and checked against CPython's bytecode and outputs for every annotate and evaluate function of the closure. A second shim, runtime/shims/\_collections\_abc.py (decision P-2, 2026-11-02), takes the generator, coroutine, async-generator and frame-locals-proxy types from \_types instead of making the objects at import. The closure tool scans the shims' own source, whose imports run, and `ast.unparse`, which the shim's FORWARDREF and STRING call, is \[P1\] (`_ast_unparse` compiled). Omitted: `compression.zstd`, `fcntl`, and the Windows-only `_winapi` and `nt`, which are absent on the target. Unsupported: `Path.as_uri` and `Path.from_uri` (`ast.unparse` was, until decision S-1 made it \[P1\]). The lock lists every function `[lazy_unsupported]` refuses, for the runtime to use.

**After review (2026-11-01, review log RL-52 to RL-70).** Two reviews of the same day reproduced the lock byte for byte and found gaps in the tool, each now fixed with a test:

- Modules seen only by the runtime observation are traversed like any other.
- A module missing on this machine no longer excuses an import. The Windows-only `_winapi` and `nt` became omissions, and `os.add_dll_directory` is proved dead, because a star import from a built-in module binds only what that module exports.
- A handler around a `def` no longer makes the imports in its body optional.
- Every edge is accounted for, whatever reached its target first.
- The observation blocks the omitted modules, so their importers take the phase-1 fallbacks.
- Dotted dynamic targets reach their parent packages.
- A nested helper's import refuses the function a program names.

`_hmac` is now mapped: omitting it made `hmac.digest` reject a buffer key for no licence reason. Decided the same day: annotations are \[P1\] at runtime (review log D-5), and the `annotationlib` shim serves them through the compiler-generated `__annotate__`; only CPython's `__code__` fallbacks stay \[P2+\] (case C-3-13). The `hashlib` gaps, the archive formats and the codec subset are registered as deviation D-20 (D-6); providing `pbkdf2_hmac` and `scrypt` in the runtime is a later task.

The `codeop` shim (D-4). `traceback` imports `codeop` at module level (3.15.2 `traceback.py`, line 13), and E-08 excludes `codeop` because it compiles source text (E-01). The calls sit in one method, `TracebackException._find_keyword_typos` (lines 1458 and 1507). When it formats a `SyntaxError`, it recompiles the offending lines with `codeop.compile_command` to test whether a keyword in place of a misspelled name fixes them, and if so the message ends "Did you mean 'while'?". Measured on 3.15.2:

| The `SyntaxError` | Its `_metadata` | `compile_command` calls | Last line printed |
| --- | --- | --- | --- |
| Raised by the parser, `compile("whille x: ...")` | Set by the parser | 2 | `SyntaxError: invalid syntax. Did you mean 'while'?` |
| Built by the program, `SyntaxError("invalid syntax", (...))` | None | 0 | `SyntaxError: invalid syntax` |
| Built by the program, `_metadata` assigned by hand | Set by the program | 2 | `SyntaxError: invalid syntax. Did you mean 'while'?` |
| As above, with a `compile_command` that raises a catchable error | Set by the program | 1, which raises | `SyntaxError: invalid syntax`: the suggestion is silently lost |

A compiled program has no parser at runtime, so the first row cannot occur, and the second needs no `codeop`. Only the third reaches it, by assigning a private attribute. Three answers were possible. Un-excluding `codeop` would put a parser in the runtime, which E-01 rules out. Compiling `traceback` without its import would change what the module binds (`traceback.codeop` would be missing), an unregistered divergence. A shim keeps E-08 intact, and it was chosen.

The shim exposes `codeop`'s whole public surface, so `traceback`, and anything that reaches `traceback.codeop`, sees the names CPython has: `PyCF_ONLY_AST` (1024), `PyCF_DONT_IMPLY_DEDENT` (512) and `PyCF_ALLOW_INCOMPLETE_INPUT` (16384) with CPython's values, and `compile_command`, `Compile` and `CommandCompiler`. Calling or instantiating any of the three stops the program with the E-08 refusal. The refusal must not be a Python exception. `traceback` calls `_find_keyword_typos` inside `suppress(Exception)`, so a catchable error would be swallowed, and the program would print the message without CPython's suggestion (the last row): a silent divergence. It is a runtime refusal of the kind `bella::NotImplemented` already is, a C++ exception that no `except` clause sees. It names E-08 rather than a milestone, because the exclusion is permanent. A program's own `import codeop` stays a compile-time error, so only `traceback` brings the shim into the closure. The manifest records the shim under `[phase1.shim]` and the dependency under `[adaptations]`.

**The replaced functions and the running stack (2026-11-13; the sentence on the running stack moved here from the specification on 2026-11-14, the author's decision: the specification says what a program sees, this document how).** `[replaced]` has grown with the functions that read a frame object (E-02), each replaced by what the runtime has in its place, the rest of the module being CPython's code: `traceback`'s walk of a traceback's frames and `StackSummary`'s reading of them (an entry stands for its frame: file, line and function, D-06), `clear_frames` (the entry gives up the locals it holds), `logging.Logger.findCaller` (the call sites the compiler supplies), `unittest`'s `TestResult._is_relevant_tb_level` (the globals of the entry's module), and `traceback.extract_stack`, `format_stack` and `print_stack`. Those three, asked for the running stack, take it from the frame chain the runtime keeps (`__bella_stack__`: a frame and the line it is at for each frame a traceback would show, the asking frame's first, as `walk_stack` gives them), where CPython asks `sys._getframe`; a frame given is walked as CPython walks it. `re._compiler._bytes_to_codes` is replaced for another reason (it casts a memoryview).

**The frame a signal handler is given (2026-11-15; specification E-02 and the Development row).** `check_signals` makes one frame object for the handlers of an arrival (`runtime/src/signals.cpp`, `frame_argument`): a `FrameObject` that points at the frame record of the frame the signal interrupted and shares a flag with the pass, which the pass clears when its handlers are done. While the flag is set, `__bella_stack__(f)` walks the frame chain from that record (the replaced `traceback.extract_stack`), and `repr()` reads its line; once it is cleared both stop by name, since the records it pointed at have gone on or are gone.

**The names of the frame that raised (2026-11-15).** `traceback._compute_suggestion_error` is `[replaced]` by CPython's own text with its reads of `tb_frame` exchanged for `__bella_traceback_names__` (`runtime/src/call.cpp`): the locals, globals and builtins of the frame an entry stands for. Locals come from the code record's table (`Code::frame_slots`) over the frame's variables while it runs (the frame chain is searched for the entry's frame id), or over the variables the entry of the exception that left the frame took over. The entries of one frame share a `FrameLink` naming the entry that has them, so the first of two exceptions a frame saw can be read while the second lives. It owns nothing: lifetimes are as D-12 left them.

**A program without `warnings` (2026-11-15; specification D-27).** CPython's C imports two modules for itself and does without them when the import fails: `warnings` when a warning is shown, `io` when its source line is read. The runtime makes those two imports through one primitive (`_bella_import_if_held`, `runtime/src/imports.cpp`) that, for the length of the call, lets the registry answer "not found" for that one name where it otherwise stops by name; nothing else reads the flag, so a program's own import of a module it does not hold stops as before. The C's printing is `runtime/prelude/_warnings.py` (`_show_warning`, `_display_source_line`, `_find_source_file`), and the encoding of the source file comes from CPython's file tokenizer, written in `runtime/src/tokenizer.cpp` beside the readline tokenizer over the same lexer text (`_find_source_encoding`).

**The runtime's own report of an exception (2026-11-19; specification D-28).** The report of an uncaught exception, of `sys.excepthook` and of the unraisable hook is `print_traceback` (`runtime/src/call.cpp`), written after `traceback`'s format: the entries, the lines between chained exceptions, a group's box, the notes. It imports nothing, and it does not have `traceback`'s rules for the last line (`TracebackException.__init__` with `_compute_suggestion_error`, the cross-language table and the words for a missing module of the standard library), so its last line is the class and `str()` of the exception. The author chose to leave it so (`docs/DECISIONS.md`, 2026-11-19): no library code runs on the way out of a failing program, and a program that holds `traceback` prints the same report as one that does not. CPython's `_PyErr_Display` asks `traceback` first and prints with its C (`print_exception`) when the import fails; that C prints what the runtime prints for every exception that is not a group and has no notes, which is how the harness shows the deviation on CPython (`conformance/harness.py`, `_no_traceback_module`; the staging replay blocks the same import for a case that declares D-28).

**What the environment said at the start (2026-11-20; the specification's Environment paragraph, C-8-16).** The runtime reads the variables it honours once, into one record (`StartUp`, `runtime/src/core.cpp`: `start_up()`), at the first use, which is the first statement of `run_main` unless a hash was asked for earlier. The record is CPython's configuration cut to what a compiled program has: `buffered_stdio` (`PYTHONUNBUFFERED`, read as `_Py_get_env_flag` reads a flag), the hash seed (`config_init_hash_seed`), `int_max_str_digits` (`config_init_int_max_str_digits`) and `cpu_count` (`config_init_cpu_count`), each parsed as the C parses it (`_Py_GetEnv`: a variable set to nothing is not set; `_Py_str_to_int`: `strtol`'s number, nothing after it, within an `int`). A value the C refuses ends the process there as `Py_ExitStatusException` ends CPython: `Fatal Python error: <the C function>: <its words>`, `Python runtime state: preinitialized` and an empty line on descriptor 2, status 1, the seed before the digits before the count (measured). What the program does to its environment afterwards changes nothing, as in CPython. The record's readers: the hash secret and `sys.flags.hash_randomization`; the limit of digits and `sys.flags.int_max_str_digits` (`sys.set_int_max_str_digits` puts a new flags object in `sys`, as `_PySys_SetFlagObj` does, so the one a program kept says what it said); `os.cpu_count()` and `sys._get_cpu_count_config()`, from which `os.py` decides what `process_cpu_count` is; and `create_stdio`, which without buffering opens the two writers over the raw file with `write_through` and no line buffering, leaves standard input its buffer, and makes the C library's three streams unbuffered (`config_init_stdio`). A literal is the one thing a limit of digits reaches that a compiled program did at its build: CPython compiles a main program at each start, and its parser refuses the first decimal integer literal longer than the limit (`_PyPegen_number_token`). So the build notes the main program's decimal literals of more than 640 digits, the least a limit can be, with their lines and the lines' text (`pipeline/build.py`, `long_literals`: the tokenizer's NUMBER tokens, digits counted without underscores; a literal of zeros, of another base, a float and an imaginary number are not limited), the main unit hands the table over (`set_long_literals`), and the start, where the main module's body would be compiled, raises the parser's `SyntaxError` for the first one longer than the limit (`refuse_long_literal`, `runtime/src/call.cpp`; case C-8-18, RL-555). An imported module has no such table: its literals are as CPython has them from the module's cached code.

**The native stack (2026-11-21; RL-624, C-8-20).** An object dies inside the dealloc of what held it, and compiled calls are native calls, so three things grow the native stack with a program's data or depth: letting go of a chain of objects, a walk of nested data inside one call of the runtime's (the hash of a tuple of tuples, a repr, a comparison), and a program's own recursion. The third has the counter of D-17. For the first two the runtime had nothing, and a linked list of some tens of thousands of nodes ended the program when it was dropped. CPython 3.14 and later looks at the stack pointer for both, and the runtime does what it does. The bounds are read once, when the program starts (`measure_native_stack`, `runtime/src/core.cpp`: `pthread_getattr_np`), into `detail::stack_watch` (`runtime/include/bella/object.hpp`): a soft limit that keeps back a quarter of the stack or 192 KiB, whichever is less (CPython keeps 32 KiB; an exception raised from compiled code and what its handler does take more), and two marks above it, 2 and 4 of CPython's units of 16 KiB. `decref` goes through `dealloc_or_later`, which is `_Py_Dealloc`: below the first mark an object that can hold others is put off, nothing of it run, its finaliser included (`deposit`: the flag `PUT_OFF` and the thread's list), and a dealloc that ends at or above the second mark lets everything put off go, the last first, from there (`destroy_later`), which may put more off. A weak reference does not reach an object that is put off (`weak_target`: its count is 0, as `_Py_TryIncref` fails in CPython). Below the depth at which the stack is short nothing changes, so the order of deaths is the nesting's, as in CPython; past it the order is the machine's on both sides, and what holds is that every object dies once. The model has the same two tests on a count of deallocs in flight (`Heap.stack_room`, `_dealloc` in `refmodel/objects.py`), and the header takes that count in place of the stack where a test sets `stack_watch.room`, which is how the two are compared in lockstep (part 9 of `runtime/tests/object_state`). The walks raise: `check_native_stack(where)` is `_Py_EnterRecursiveCall` in `tuple_hash`, `repr_of`, `str_of` and `compare`, a RecursionError with CPython's words (`Stack overflow (used N kB) while hashing a tuple`), and `enter_frame` has the same test for a program that raised its recursion limit past what the stack holds, where CPython's own frames are on the heap and its recursion goes on. The counter of D-17 counts the frames CPython has (RL-632): a `FrameGuard` whose code is shown. The helper of an inlined comprehension and a function of a prelude, which stands for a C function, are frames of the compiled program's alone; they take the look at the native stack (`enter_hidden_frame`) and no count, so a recursion through `map`, a property or a comprehension reaches the depth it reaches under CPython, and a prelude's walk of nested data is bounded by the stack and not by the limit of Python calls. The cost on the path of every death is one compare of the frame's address with a global, and one of a count with zero.

**What a prelude asks of a type, and an exception the runtime sends on (2026-11-21; RL-644, RL-645, RL-650).** A prelude stands for C, and the C reads a type's slots from the type. Python code cannot do that by itself: `type(x).__mro__` and `vars(klass)` are attribute reads on a class, which its metaclass answers first. So the three lookups are the runtime's and every prelude has them: `_has_slot(value, name)` (a slot's presence: `PyIndex_Check`, `PyMapping_Check`, `PyIter_Check`, a `tp_as_` field; it binds nothing), `_type_lookup(value, name, absent)` (`_PyType_Lookup`: what the type has, unbound) and `_lookup_special(value, name)` (`_PyObject_LookupSpecial`: bound, in a tuple, or `()`); no prelude walks an MRO itself. A fourth, `_raise_as_is(exc)`, is for an error that was pending while the C did something else and then returned: the prelude catches it, does that work after its handler has ended (so that a finaliser the work runs sees no handled exception, as under CPython), and sends the same exception on with the context it had. In the runtime's C++ the matching rule is `rethrow(e)`: a catch block that names its `PyError` and sends it on never uses a bare `throw;`, because work done in the block may have raised and caught another exception, which took the mark of the exception in flight with it, and the frames the first then leaves would record nothing. Both rules are held by tests that read the sources (`pipeline/tests/test_review_2026_11_21_a30.py`). A type test follows the same line: where the C asks `PyUnicode_Check`, `PyLong_Check` or `PyObject_TypeCheck`, a prelude writes `issubclass(type(x), T)`, never `isinstance(x, T)`, which falls back on the object's `__class__`; `isinstance` stands only where the C calls `PyObject_IsInstance` (RL-655, `pipeline/tests/test_type_checks.py`). And once the type is tested, the C reads the object's own data through the concrete API, which calls nothing of its class: a prelude takes the data once, `_own_data(x)` for a str, bytes, int, float or tuple (the exact base object with the same data, for an instance of a subclass) and `_buffer_bytes(x)` for the octets of a bytes or a bytearray, and reads a list, a dict or a bytearray, which the C reads as they are at each turn, by the base type's own methods (`list.__len__`, `list.__getitem__`, `dict.__contains__`, `bytearray.__setitem__`). What is made of a C string later is a plain str; what the C keeps as the object it was given (a `TextIOWrapper`'s errors, a type alias's parameters, a `struct` cache key) stays that object (RL-698, `pipeline/tests/test_subclass_data.py`). The other half of the rule (review A32): reading the data does not make the object a copy. What the C hands on or gives back is the object it was given: a decoder receives the chunk a buffer returned, `IncrementalNewlineDecoder.decode` and `TextIOWrapper.read()` give back the str they were given where they change nothing, and a cache of the C's that is keyed by the object is keyed by the object. And where the C formats a message, a note or a second try with an error pending or cleared, the prelude has left its handler first (`_raise_as_is`, `_raise_noted` in `_json`), so that a `__repr__` of the program's sees what was handled around the call (`pipeline/tests/test_review_2026_11_22_a32.py`). Review A33 added three things to the rule. An error the C holds as pending is not a handled one: `PyErr_FormatUnraisable`, `_PyErr_FormatNote` and the `fail:` label of a function that puts state back all run with the error taken off the thread, so a prelude catches the error, lets its `except` clause end and only then makes the report, adds the note or restores, and an error of that second step has the first as its context (`_PyErr_ChainExceptions1`): a file's finaliser, an `atexit` callback, a codec's failure, the JSON encoder's notes, `TextIOWrapper.tell`. The text of a repr is its characters: `PyUnicode_FromFormat`'s `%R` and `%S` and `PyUnicodeWriter_WriteRepr` read what `PyObject_Repr` or `PyObject_Str` returned and call nothing of it, while Python's `"text" + repr(x)` is the `__radd__` of a str subclass's instance, if that is what a `__repr__` returned. So a prelude takes the text with `_repr_text(x)` and `_str_text(x)` (the runtime's, in every prelude; an exact str) and calls `repr()` itself only where the C writes the result with `PyUnicodeWriter_WriteStr`, which is `str()` of it and so does call a subclass's `__str__` (the repr of an ast node, the arguments of a generic alias): `_str_text(repr(x))` (`pipeline/tests/test_repr_text.py`). And a value the C parses into a C integer is that integer from then on: a decoder's flag is converted where the C converts it (`i`: an int or an `__index__`, within the type; `K`: the low 64 bits, with a warning past them), shifted and packed in the type's width, and handed back as a plain int (`TextIOWrapper`'s cookie, `IncrementalNewlineDecoder`'s state). A type whose allocator is object's in CPython checks its arguments as `object_new` does (`_object_new_args`, by `_class_lookup(cls, name, absent)`, which is `_type_lookup` for a class itself), and a C type's deallocator is no `__del__` a program can call: what it frees is held in an object of the prelude's own that has the finaliser (zlib's `_Stream`, as `_sre`'s `_BufferHold`), and where the deallocator only lets go of what the struct holds, in an order, the order of the class's fields is that order and no code is needed (a tee's data link: the iterator, the values by index in a dict, the next link; `pipeline/tests/test_tee_dealloc.py`) (`pipeline/tests/test_review_2026_11_22_a33.py`). Review A34 took the rule to three more things a prelude did in Python. The name of a type: `type(x).__name__` is an attribute of a class, which its metaclass answers first, and the C reads `tp_name`; the runtime gives the names (`_tp_name(x)`; `_type_name(x)` and `_class_name(cls)`, which are `_PyType_Name`, the part after the last dot that a repr shows; `_type_fullname(x)` and `_class_fullname(cls)` for `%T` and `%N`), and a name a program supplied is its characters where the C formats it with `%U` (`_own_data`). A chained error's context: `_set_context(error, first)` stores the field as `PyException_SetContext` does, where `error.__context__ = first` is an attribute assignment a `__setattr__` of the class takes. And an iterator the C holds: `it = iter(x)` followed by `for item in it` asks the iterator for an iterator a second time, so a prelude that needs the iterator before its loop takes it with `_tp_iter(x)`, which hands back one of CPython's own iterators as it is and wraps an iterator of a class of the program's in a generator that calls its `__next__` alone. Each of the three has a rule in the source (`pipeline/tests/test_review_2026_11_22_a34.py`). Review A35 added what the C lets go of and when. An item of a loop: the C has `Py_DECREF(item)` at the end of its loop's body, before it asks for the next, and a Python `for` keeps the item in its variable across the next `__next__`; so the wrapper `_tp_iter` gives hands the item on and keeps nothing, a prelude's loop over an iterator of the program's ends each turn with `del`, a loop of the runtime's steps with `next_after(item, it)`, and where the C does something between the last item and letting go of the iterator the prelude holds the iterator and asks it with `next()` (`pipeline/tests/test_item_lifetime.py`). A type is compared by identity (`cls is T`, a loop over the MRO), never with `in`, which is `==` and so a metaclass's `__eq__`; `tp_flags` and a type's names come from type's own getters where the runtime has no primitive for them. A field the C overwrites without `Py_DECREF` is a count never given back (`_io_call("leak", obj)`), not an assignment that releases. And the classes the C makes by calling `type` (`PyErr_NewException`'s, `io.UnsupportedOperation`) are classes like any other when they die: the runtime gives a prelude class a dealloc of its own only where the class has fields of its own, and the model and the header refuse one over a built-in base with fields, which would end before the base's (`pipeline/tests/test_exception_release.py`, `pipeline/tests/test_review_2026_11_22_a35.py`). Review A36 walked the ways out that A35's sweeps had not. A consumer that fails lets go of what it holds in the C's order and with the error pending, which in a prelude means outside any `except` or `finally` (a handler is open in both, and a finaliser would see the wrong handled exception): the prelude keeps the error in a variable, leaves the handler, lets go, and sends it on with `_raise_as_is`; in the runtime a guard object's destructor holds the order (`Taken` for an unpacking, `Turn` for a pair of a dict, `Merge` for a mapping's keys), and `PySequence_Tuple` is one function, `sequence_tuple`, with its two orders. The sequence protocol is the runtime's where Python's spelling is another operation: `_sequence_size(x)` for `PySequence_Size`, which a dict has not, `_sequence_concat` for `PySequence_Concat`. A type's `tp_new` is a state of the class and has a history (`ClassObject::slot_tp_new`): the lookup of `__new__` at the time of a call does not say what CPython's slot holds after the name was stored and deleted again. And a field of the C that can hold any object, None too, needs a marker for NULL that is not None (`TextIOWrapper`'s buffer) (`pipeline/tests/test_review_2026_11_22_a36.py`). Review A37 added the other half of the slots: the argument checks the clinic generates refuse keywords only for a class that has the type's `tp_init` (in a `__new__`) or the type's `tp_new` (in an `__init__`), so a prelude asks `_tp_init_is(cls, base)` or `_tp_new_is(cls, base)`, never `cls is T` alone and never `cls.__init__`, which is an attribute of a class; a built-in's `__new__` of another type stored in a class is not the class's allocator (`stored_new_wrapper`); and a class of the program's over a mapping type has a sequence's length, since the slot is filled from the `__len__` it finds. Where CPython calls code of the program's with an exception set, which no prelude can do, the case stops by name (`pipeline/tests/test_review_2026_11_22_a37.py`). Review A38 added three sentences to the rule. What a class has under a special name is called as the slot calls it: a function, or an unbound method of a built-in type, with the object first, and that method checks that the object is of its type; anything else through its own `__get__`, so a bound built-in or a built-in function gets the arguments alone (`type_call` for `__init__`, as `call_special` for the others). A conversion that can run code of the program's is clean-up like any other: where the C takes the error off first (`_PyIO_trap_eintr` reads the errno after `PyErr_GetRaisedException`), the prelude does it after the handler (`_interrupted`). And a flag a prelude keeps for "this field is not NULL" is set with the field's first store and never cleared by a second `__init__`, which stores over fields that are there (`pipeline/tests/test_review_2026_11_22_a38.py`).

**The compiler's warnings at each start (2026-11-21; the author's decision on RL-572, C-8-19, D-29).** The same compile warns. CPython's tokenizer, parser and code generator give a `SyntaxWarning` for what they find doubtful in the main program's text (`warn_invalid_escape_sequence`, `verify_end_of_number`, `codegen_check_compare`, `codegen_assert`, `check_caller`, `check_subscripter`, `check_index`), each through `PyErr_WarnExplicitObject` with the file, the line, the module `__main__` and no registry, so each is shown under the filters a program starts with, before the first statement, at every start. None of those rules is written a second time: the build compiles the main program's bytes with the host, which is the pinned CPython, under a recorder (`compiler_warnings`, `pipeline/build.py`: `compile(..., dont_inherit=True, optimize=0)`), and the main unit holds what came out, category, message and line, in the order given (`set_compiler_warnings`). The start, where the long literals are looked at, calls the `_warnings` prelude's `warn_explicit` for each (`as_compiled_at_each_start`, `runtime/src/call.cpp`); that is the port of the C machinery, so `warnings` is imported for the first one and prints through `linecache`, as CPython has it. The function called is the prelude's own as it was when `_warnings` was made (`warning_function`, `runtime/src/imports.cpp`), not what the module's name says at that moment: CPython's parser calls the C function, and a `warnings.py` of the program's, imported for the first warning, may have put another under the name before the second (RL-615); the runtime's other warnings of its own (the tokenizer's, the import system's, an unclosed file's) call the kept functions too. A program whose text warns therefore holds `warnings` whether or not its imports reach it (`find_program_modules(program, also=("warnings",))`): the fallback of D-27 is for a program whose text CPython's compiler has nothing to say about. A literal past the limit ends CPython's compile where its parser meets it. What CPython has warned of by then is not the first so many of the whole compile's warnings: the parser's end at the literal, and CPython then reads the rest of the text with its tokenizer alone, to look for a tokenizer's error (`_PyPegen_tokenize_full_source_to_check_for_errors`), which gives the tokenizer's warnings of the rest (a number that runs into a keyword, `\{` in an f-string) and none of the parser's or the code generator's. So that list is asked of the host too, for each literal a limit can reach (`warned_when_refused`: the text compiled under a limit which that literal is the first to pass, the line of the `SyntaxError` checked), and the literal's row points at its own (RL-611). CPython reads the limit when its parser meets each literal, and what shows a warning before that may change it (a `warnings.py` of the program's own, imported for the first one); where each literal stands among the warnings is not noted, so a start whose limit is another after a warning than before it, in a text with such a literal, stops by name (RL-605). Filters that make such a warning an error cannot be there at a start yet (`PYTHONWARNINGS` is not read); CPython's compiler would put a `SyntaxError` with other words in its place, and the start stops by name if it ever meets that. `return`, `break` and `continue` out of a `finally` block never get this far: the build refuses them (D-10). The switch `--syntax-warnings=off` (`BELLA_SYNTAX_WARNINGS`; `build(..., syntax_warnings=False)`) leaves the table out and does not add `warnings`, and that is all it does; the note of a program's last binary is per switch as it is per fidelity. The host's own warnings, which every parse and compile of the build would print, several a text, are silenced inside `build()`; a build that does not run the program says each warning once (`_say_compiler_warnings`): the main program's first, before anything can refuse the text, so that the warnings CPython's compiler gave until an error of its own are said too (RL-601), then those of the program's other modules in the order the build found them, which is where an imported module's are seen: CPython gives them when it first compiles the module, in the order its imports run, and a compiled program never. The note is the build's own: its lines are read by the host, whatever a `tokenize.py` of the program's would do to CPython's. The file a warning names is the name CPython has for the program (`run_filename`: `_Py_abspath`, the current directory and the path as given, nothing normalised; RL-606), which is the main module's `__file__` and the name in its code objects. The harness records a warning's line with `<cases>` for the directory where the file is in the cases' directory (`mask_stderr`), so that the recording of a case whose own text warns does not depend on where the repository is and still differs from a line with the bare name (RL-622); any other path is compared as written (RL-608).

**The encoding of the standard streams (2026-11-20; D-15 as narrowed, C-8-17).** `PYTHONIOENCODING` is parsed where the streams are made, as `config_init_stdio_encoding` parses it (the text before the first colon and the text after it; an encoding alone makes the errors `strict`), and its bytes are text as the file system's are. Then, as `init_stdio_encoding` does, the encoding is replaced by the name its codec has for itself: the registry is asked (`_codecs.py`'s lookup, after the registry's own start), so `latin-1` is `iso8859-1` and `UTF8` is `utf-8`. What fails there, or while one of the three streams is made (`init_sys_streams`), ends the process as `Py_ExitStatusException` ends CPython once its core is up (`fatal_while_starting`, `runtime/src/call.cpp`): `Fatal Python error: init_stdio_encoding: failed to get the Python codec name of the stdio encoding` and `Python runtime state: core initialized` on descriptor 2; the exception, printed by the runtime's plain printer through a text stream made for the purpose over descriptor 2, which stands for the preliminary `sys.stderr` CPython has until the real one exists; and, the exception having no traceback, an empty line and `Current thread 0x... [name] (most recent call first):` with the thread's number and the name the system has for it; status 1. A codec outside the phase-1 set is not in the closed world, so the registry does not find it and the program ends the same way (D-20). One residue stops by name: a name that is not ASCII makes 3.15's `encodings` warn through `warnings`, which a program that does not hold the module cannot import.

**A slot a class declares again (2026-11-20; RL-541, RL-563; case C-3-78).** CPython makes a member for every declaration of a slot, each with its own offset, so `class F(D)` that lists a name `D` lists has two cells for it: the name reads the cell of the member the lookup finds (`F`'s, while `F` has it), and `D`'s member reads `D`'s cell, by itself, through `super()` and under any name a class has it. The model and the header keyed a slot by its name, so the two shared one. Now a class's layout has, beside the cell of each name (`field_index`: the nearest declaring class's), a cell for each declaration behind it (`RefClass.shadowed_fields`, `ClassObject::shadowed`: the declaring class, the name, the place), and everything that reaches a slot through its declaration asks `slot_cell(obj, owner, name)` (`_cell_of` in the model): a member's read, store and delete, and the release of an object's slots, which goes class by class down the MRO and so lets go of the most derived class's cell of a name first. An entry of the inline cache reads by the name looked up and holds no place, so a member is cached only when its cell is the name's: one found by the name because the nearer class's member was deleted or replaced is read through the generic path each time. A class with no slot declared again has an empty list and pays one test of it on the generic path. A member also applies only to objects of its class (`member_applies`, CPython's `descr_check`): one that a class which does not derive from the member's has under a name is a TypeError for a read, a store and a delete, where the lookup used to take it for a slot of the object. The runtime's own types declare a field once (their fields are reached by name, `state_index`); `hide_slots` refuses a family that would not. A field of a built-in base is the same kind of declaration: a class over `Exception` with a slot `args` has the slot as the name's cell and `BaseException`'s own `args` behind it, with no class to name (an owner of null), reached by the exception's C code (`exception_field`) and by the base's descriptor (RL-564). What a class adds to its layout (`__dict__`, `__weakref__`, and a getset for each) is asked of its best base alone, as `type_new_slots` asks it, and `__base__` is that base (RL-566, RL-575).

**The order of a display's stores (2026-11-22; RL-825; case C-3-79).** `a, b = x, y` in a function stores `b` first under CPython, so what `b` held is let go of before what `a` held. The compiler emits `BUILD_TUPLE n, UNPACK_SEQUENCE n` for a tuple display assigned to n targets; for n of 2 or 3 the optimizer replaces the pair by `SWAP n`, and `apply_static_swaps` then removes the swap by exchanging the first of the n stores that follow with the last, which it may do where those are `STORE_FAST` of different names on one line. So the order is a property of the statement's shape and of the names' kinds: one target (tuple or list syntax) of two or three different names on one line, a tuple display of as many items with no star, and every name a fast local (in `co_varnames`, not in `co_cellvars`); a cell, a global, a `nonlocal`, an attribute or a subscript among the targets, four names, a list display, a nested or starred target, a chained assignment and a statement at module or class level all store in the order written. The shape is the frontend's to see (`L.Assign.swapped`, from the `ast` node, before any name is resolved); the kinds are level 2's (`pipeline/l2/resolve.py`), where the lowering reverses the stores, and eval1, which has no scopes of its own, asks the same resolver. Nothing else moves: the values are evaluated left to right as before.

**The order of a pattern's stores (2026-11-22; case C-3-80; `pipeline/l1/captures.py`).** A `match` case's captures are stored once its whole pattern has matched, and under CPython the order of those stores follows the pattern's shape: `[a, [b, c]]` stores `b`, `c`, then `a`, and `{"x": a, **rest}` stores `rest` first. The code generator leaves each captured value on the stack, rotated under what the stack held at that moment (SWAPs), and emits the stores at the end in the order of capture; the optimizer then removes the SWAPs that stand right before the stores by exchanging the stores themselves (`swaptimize`, `apply_static_swaps`), as far as it can: only `STORE_FAST` and `POP_TOP` are moved, only within one line, and not past any other instruction. So the order depends on three things: the pattern (what is emitted between the last instruction the optimizer cannot move and the stores), the lines it is written on (`[a,` and the mapping on the next line keeps the order of capture), and which names are fast locals (a global or a cell among them stops the exchanges part of the way; at module and class level nothing is exchanged). The port has those two halves. The frontend runs the code generator's bookkeeping over the pattern (`capture_plan`: `pc->on_top`, `pc->stores`, the rotation counts of each kind of pattern) and keeps what stands before the stores, SWAPs and POP_TOPs with their lines, on the statement that stores the names (`L.Assign.captures`: a tuple of the names from a display of the temporaries). Level 2 knows the names' kinds, so the lowering, and eval1 through the same resolver, run the optimizer's two functions over that and the stores (`store_order`) and store in the order that comes out; the compiled program makes no tuple for it. An or-pattern stores in its first alternative's order (the others rotate into it before they join). The port is compared with what the reference interpreter compiles, for 1,500 generated patterns in four kinds of scope (`pipeline/tests/test_match_stores.py`), and the case holds 41 shapes with objects that say when they go. Not covered by this: where a pattern's own temporaries are let go of between those stores (the tuple of a mapping pattern's keys, the subject where the last case consumes it), which is in TODO.md.

**A generator expression's iterable and iterator (2026-11-22; RL-488; case C-3-81).** CPython 3.15 calls a generator expression's code with the iterable of its first `for`. That value is the code's first variable, `.0`, for as long as the generator has its frame, and the code itself calls `GET_ITER` on it before `RETURN_GENERATOR`, so the iterator exists from the moment the expression is evaluated and is a value of the frame's stack, with no name. Three things follow that a program can see: a temporary iterable lives as long as the generator's frame; `locals()` in the expression shows the iterable; and the iterator is let go of when the loop ends, before the frame's variables, and first of all when a generator that did not finish is given up (`_PyFrame_ClearLocals` goes down the stack and then the variables, last to first). The frontend's helper `<genexpr>` is a generator function, which cannot do anything before the generator is made, so it takes both: the iterable as its first parameter (public name `.0`) and the iterator as a second, under a name of the compiler's own. The outermost loop is a loop over a ready iterator (`L.For.iterator`), and its load of that name moves the value out of the variable (`resolve.moved_on_use`, as for a decorator's value): from then on the loop's temporary is the only reference, and a generator not yet started has the iterator in the last of its two variables, which is the first to go. The call is the intrinsic `genexpr(helper, iterable)`, which calls `iter()` and then the helper; a failing `iter()` shows no frame of the expression, as under CPython, where the frame is not yet complete. The other comprehensions are given the iterator alone, as before, and CPython's too let go of the iterable at once. Their iterator outlives the comprehension's last item in the compiled program, because the helper's caller holds its argument for the call: that is RL-695.

**The stack the program runs on (2026-11-22; the author's answer B to Question 28; case C-8-21; `runtime/src/core.cpp`, `on_main_stack`).** A compiled call is a native call, about 690 bytes of stack for a small function, and a walk of nested data through a prelude takes 4 to 8 KiB a level; CPython keeps the frames of Python calls on the heap. On the 8 MiB a shell gives, a program that raised its recursion limit stopped near 12 000 calls and `json.dumps` of a list nested 1 500 deep was a RecursionError. The program therefore runs on a stack of the policy's size, `[platform] main_stack_mib` of the nearest `bella.toml` above it, 256 MiB where there is no policy; the build puts the number in the main unit. At the start `run_main` reserves that much address space with no memory behind it (`mmap`, `PROT_NONE`, then the part above a megabyte made readable and writable with `MAP_NORESERVE`), switches the thread onto it (`makecontext`, `swapcontext`) and runs the program there; memory is taken as the stack is used. The thread is still the process's first, so its native id is the process id and signals arrive as before. The stack watch (`measure_native_stack`, RL-624) is given the new bounds, and the old ones again when the program has returned and the process's own way out runs. The switch back keeps the signal mask the program left, not the one saved at the start. The process's hard limit on its stack is kept: the size is no more than it allows, and where that is no more than the stack the process has, nothing is switched. A plain `ulimit -s` in a shell sets the hard limit too, which is how a test runs a program on a small stack (C-8-20); the soft limit alone, every shell's default, is not a bound. What remains is in D-17: past what the stack holds a raised limit or deep data meets a RecursionError that CPython does not raise. The author's note with the decision: such stack growth may flag a deeper design issue, to be analysed later (TODO.md, Later).

**The order in which a built-in type lets go of what it holds (2026-11-21; RL-565, RL-577; `pipeline/tests/test_release_order.py`).** An object on no cycle dies with its last reference, and what it holds dies in the order of its type's dealloc function, which a value with a `__del__` and the callback of a weak reference let a program see. For a class of a program's that is `subtype_dealloc`: the finaliser, the weak references, each class's slots, the dict. A type written in C has its own function, and for an object of a class that derives from such a type `subtype_dealloc` lets go of the deriving classes' slots and of a dict those classes added, then calls the type's dealloc; it clears the weak references itself only when the list is not the type's own. The model states a type's dealloc as `RefClass(release=...)`: the names of its fields in order, with `__weakref__` where it clears its weak references and `__dict__` where it lets go of its dict; the header has `ClassObject::release` and, for each class, `dealloc_base`, the nearest class of its MRO that has one, so an object's end tests one pointer. `note_prelude_class` gives every type CPython writes in C (one it writes in Python has `__firstlineno__` in the names table and dies as a class does) the common order: the weak references, the fields as the classes declare them, the dict. A type whose C does otherwise says so in `__release__` (`BytesIO`, `StringIO` and `OrderedDict` let go of their dict before the weak references), and the order of a type's `__slots__` is the order of its dealloc (`map`: the iterators, then the function; `property`: getter, setter, deleter, doc, name). The sweep holds all of it: an object of each type with values that record their deaths, and three deriving classes over 34 of the types, compared with CPython row by row.

**The state of a built-in type the prelude writes (2026-11-20; RL-507, the author's decision; cases C-3-76 and C-3-77).** CPython keeps what such a type needs for its own work in the fields of a C struct; the prelude's class declares them as `__slots__`. Where the class is presented as CPython's type (`note_prelude_class`, `runtime/src/call.cpp`), every slot it declares becomes a field of the type's own: `hide_slots` (`object.hpp`; the model's `RefClass(hidden=...)`) moves the field's place from `field_index` to `state_index`, in the class and in every class that derives from it so far, so that a class of a program's may have a slot, an attribute or a property of the same name, which is another cell or none at all. A field that is no member of CPython's type (the names table decides) loses its descriptor and has no name from then on: no lookup finds it, and `getattr`, `hasattr`, `vars()` and a program's `self._count = ...` go where CPython sends them. A field CPython's type does show (`partial.func`, a stream's `_finalizing`) keeps its descriptor (`members`), which reads the field's cell by its own name, under whatever name a class has it (`member_cell`, the plan `State`); the class says in `__readonly__` which members have `Py_READONLY` and in `__boolean__` which are a `Py_T_BOOL`, and a store or a delete through such a member, by the name, by `object.__setattr__` or by the member itself, is refused as `PyMember_SetOne` refuses it (`check_member_store`). The field stays where it is in the object; a class with such fields lets go of them in the order it declares them, which stands for the order of the C type's clear function (`partial_clear`: the function, the arguments, the keywords), where a class of a program's lets go of its slots by name. The type's own code reaches a field through `rt::state_get`, `state_set` and `state_del` (`runtime/src/ops.cpp`): for an object whose type has a field of that name they read or store the cell and ask no class (no `__setattr__`, `__delattr__`, `__getattr__`, no attribute of a class that derives), and for any other object they are `getattr`, `setattr` and `delattr`. The emitter writes them, in the prelude's units only, for an attribute of any name a prelude class declares as a slot (`pipeline/build.py` `prelude_state`, `pipeline/backend/cpp.py` `Emitter.state`): the prelude's text stays `self._count`. Where the name is a value a native module's prelude calls `_bella_state_get` and `_bella_state_set`, which are in those modules' private namespaces alone: the bootstrap, whose globals a program can reach through a function of importlib's, has neither. A C function of the type that is no method of CPython's type is a function of the prelude's module, not a private method of the class. The cost is at the build: the read of a field is one lookup in a small table where it was a walk of the classes and a descriptor. What the struct holds before `__init__` has run is the allocator's business: `tp_alloc` zeroes it, and a type whose `tp_new` is object's has no `__new__` of its own to set anything (BufferedReader, BufferedWriter, BufferedRandom, BufferedRWPair, IncrementalNewlineDecoder, TextIOWrapper). The prelude's class says what the zeroed struct is in `__alloc__(self)`. `note_prelude_class` takes the function out of the class (it is no name of the type) and keeps it beside it, and `object.__new__` calls it for each object it makes of the type or of a class that derives from it, base first (`allocated_state`, `runtime/src/call.cpp`; asked only for a class with fields of a C type, so a class of a program's pays nothing). So `io.BufferedReader.__new__ is object.__new__`, `object.__new__(cls)` gives the object every method answers as never initialised, and the allocator's own check of its arguments is object's (`pipeline/tests/test_allocated_state.py`).

## 11. Build plan

&#91;embedded content: roadmap · 6 phases, each closed by a measured gate\]

Each band is a phase closed by its gate; the gate is a measurement, not a review, and a phase that misses it does not hand over. Coverage comes before speed: phase 1 compiles programs in the constrained first dialect (section 13) correctly in the boxed representation, single-threaded and without CPython, which is already a product; phase 2 adds the typed fast path and ownership. This order supersedes the phase list in the feasibility study, for a target-agnostic reason: every real program carries dynamic residue, so the object model, staging and tiers prove more early than the typed subset does.

| Workstream | Builds | Busiest phases |
| --- | --- | --- |
| A. Frontend and passes (Python) | Lossless parse, symbol tables, staging, desugaring, oracle integration, the L1 to L4 grammars and passes, the pass manager, the C++ emitter | 1, 2, 5 |
| B. Runtime (C++26) | Object model, `Int`, `Str`, containers, counting, side table, cycle collector, thread support, the `std::execution` scheduler over libuv | 1, 2, 4 |
| C. Libraries and build | Intent mappings for the stdlib, interface files, module units, the artefact cache, the embedded-CPython bridge, packaging | 3 |
| D. Verification | IR grammars and well-formedness predicates, reference interpreters, Hypothesis generators, the conformance corpus, Z3 certificates and checkers, mechanised proofs | 0, 2, 5, and continuous |
| E. Dialect and tooling | ruff configuration, `bella-lint`, the dialect specification, migration guides, generated-code style | 0, 3 |

Team and effort. Three to four engineers: one compiler engineer owning A and the pass manager, one or two runtime engineers owning B, one owning C, with D shared between the compiler engineer and a part-time verification specialist who takes over for the rung-4 proofs. Calendar time is 33 months at that size, which is 8 to 11 engineer-years before specialist help, both provisional until the dependency-closed manifest and the first complete compilation path exist (section 14); the feasibility study's 3 to 5 did not include the proof ladder, the tiered dynamism or the corrections of section 13.

Phase 0 deliverables, in order, because they are the ones that de-risk everything after them:

1. The dialect specification: observational equality (section 8), the excluded list (section 7), the tier table, and the ruff plus checker configuration (section 2).
2. The L1 grammar and `eval1`, then a conformance corpus of 200 to 500 CPython test functions run under both, with every divergence filed as a dialect decision.
3. The L2, L3 and L4 grammars with their well-formedness predicates, the `PassSpec` registry and the pass manager, before any pass exists.
4. The Hypothesis generator for well-formed L1 and L2 programs, with shrinking, and the differential runner that compares levels.
5. `bella-lint` with the tier reports, run on three real codebases the team picks as targets, so the tier distribution of real programs is known before the object model is built.

External milestones: after phase 1, programs in the constrained dialect compiled boxed, single-threaded and CPython-free (a Nuitka-class product on a native runtime); after phase 2, the typed fast path (a mypyc or Pythran replacement with readable output); after phase 3, whole applications with C-extension packages in the island; after phase 4, the GIL-free threaded runtime; after phase 5, the proof ladder at rung 2 or higher for every optimising pass.

Phase 1 in increments (2026-11-01, review log D-2, D-7 and D-10). Each increment is the closure of its target programs and is closed by a gate on its own slice of the manifest. The author picked six target programs on 2026-11-01, an easy and a tricky one for each shape (`targets/`, `docs/targets.md`). Phase 1 is the easy three, staged one program at a time, each with its own gate: 1a.1 is what `cli_easy_slugs` reaches, 1a.2 what `service_easy_tokens` adds, 1a.3 what `data_easy_sales` adds, and 1c is the rest of the manifest. The tricky three follow phase 1 (D-7): tomlkit needs stateful multiple inheritance with built-in bases, and pycodestyle and mistune need function metadata at runtime and the other items of `docs/targets.md` section 5, which a module closure does not measure. Calling their place in phase 1 a change of order rather than scope was therefore wrong. Their recordings stay as oracles and their closures are still computed, and the increment that was 1b is gone. A target's closure is the inventory of what may run. What is compiled for it was measured in Gate 0 task 4 (D-10; docs/measurements.md, 2026-11-02: the first target runs 7 to 11 per cent of its closure's code objects) and decided by the author (P-1): the whole closure. A statement the pipeline does not lower yet compiles to a refusal where it would run, the build lists those statements, and a gate requires its target to reach none of them. Compiling only what the closed world reaches stays an optimisation for when compile time or binary size needs it. Constructs come into the pipeline as desugaring passes onto a small L1 core, each tested against CPython on what a program observes (author, 2026-11-02): Bella lowers Python, it does not carry CPython's runtime. In library modules a global the compiler cannot see bound is a runtime lookup with CPython's semantics (P-3, 2026-11-02; enum.global\_enum binds re's flags from enum). The author's direction for later: a whole-program pass, once the closed world is known, that glues the modules' globals into one application-wide object with fixed slots, so that most global accesses become slot accesses and only what stays truly dynamic is looked up. Decided 2026-11-02: phase 1 has no such pass; each module keeps a dict, and every global read site caches the dict's key version and an index, with the builtins' version for the fallback, as CPython's LOAD\_GLOBAL\_MODULE does. The pass comes in phase 2, with the module's dict as a view over the fields rather than a dict the fields migrate into on exposure: 15 modules of the closure expose their own globals (os, hashlib, typing, and re through enum.global\_enum, among them), and dataclasses exposes the dict of every module that defines a dataclass, so migration would leave the pass little to speed up. The view keeps the dict's insertion order and mutation counter, and is written in refmodel/objects.py first. The first program already reaches `enum` (`re`'s flags are an `IntFlag`), and the second `typing` (itsdangerous's `Generic` bases), so staging belongs to 1a.1. Two prerequisites come first. Before the first program relies on staging, staging is prototyped on one `@dataclass` and one `namedtuple` with observable definition-time effects, and the prototype decides between stage-time exec keyed by call site and source hash, and compiler intrinsics for the known users. The prototype (2026-11-01, `docs/staging.md`) chose stage-time exec, keyed by call site and text, with literal `namedtuple` calls also made at build time. Intrinsics covered no `dataclasses` text and missed a computed `namedtuple` in `inspect`, and they would copy 516 lines of `dataclasses.py` for each CPython version. Every \[P1\] case and the three phase-1 targets print CPython's output under a replay model that has no `exec`. Before the object header is written, lifetimes are made explicit: retain and release points in the L2 grammar, checked by `eval2` against CPython's finaliser traces (`eval1` keeps none, since L1 says nothing about lifetimes; decision of 2026-11-02), and lifetimes in the reference model (review log RL-20, RL-49). The documents are consolidated after Gate 0: sections 3 to 10 are rewritten around the final decisions, sections 13 to 15 stay as history, review history lives in `docs/reviews/review-log.md` from 2026-11-01 on, and each `PassSpec` status names its evidence.

## 12. Decisions (resolved 2026-10-30)

All nine were settled by the author on 2026-10-30; the fourth column holds the decisions, and the rest of the document now reflects them: the compiler is written in Python; undeclared attributes live in a per-instance overflow dictionary rather than a shared table (sections 3, 4, 5, 7); `__getattribute__` is admitted; the toolchain is the newest GCC at C++26; Lean 4 is the proof assistant and tools may be non-MIT; exceptions cross module boundaries (the local `std::expected` lowering inside a function stays, since it never crosses one); CPython's digit limit and other defaults are kept wherever a change would risk compatibility; test-only dependencies may be non-MIT; generated C++ is committed, which also lets CI build without running the converter. The dialect specification's seventeen decisions were taken the same day (spec, section 12): among them a recursion counter, PEP 393 strings, Linux x86-64 and aarch64 only, exception message text free for now, and the project name Bella under MIT; tool and file names follow the name (bella.toml, bella-lint, bella-plugin-\<name>), renamed throughout on 2026-10-30.

| Decision | Options | Marcin Comment | Recommendation |
| --- | --- | --- | --- |
| Implementation language of the compiler | Python (the oracle checkers, `ast`, Hypothesis and the nanopass tooling are all Python; self-hosting becomes a milestone and a benchmark) or Rust (faster passes, harder oracle integration) | I accept python - it should make it easier for experiments and learning | Python for the passes, C++ for the runtime; self-hosting the compiler in phase 3 as a stretch goal |
| Default placement of undeclared attributes | Global side table (zero per-instance cost) or inline overflow pointer (8 bytes per instance, faster) | Considering the fact that we expect lock-minimal design, one shared table could be a concurrency problem. Let's go for inline overflow | Per class, chosen by the compiler from the closed world (section 3); the global table is the fallback for runtime-created classes |
| `__getattribute__` admission | Admit at tier 2 or exclude | Admit | Admit; it costs one call per access on that class and nothing elsewhere |
| Minimum C++ toolchain | Resolved 2026-10-30: GCC 16 only, C++26 only; the compiler-as-a-library route (libgccjit) evaluated in section 10.3 | newest GCC - it will take some time before this is ready and surely GCC will be only improving it's c++26 support | Generated code and runtime both target GCC 16 at `-std=c++26`; library gaps (`std::execution`, `std::hazard_pointer`) are wrapped inside the runtime; Clang becomes a target only when its reflection and libc++ catch up |
| Proof assistant for rung 4 | Isabelle (BSD-3) or Lean 4 (Apache-2.0, tool only) | If lean-4 is considered better, use that; Tooling non mit/bsd is OK | Isabelle if the MIT/BSD rule applies to tools; otherwise Lean 4 for its tooling |
| Cross-module error convention | C++ exceptions everywhere, or `std::expected` across module boundaries with exceptions inside | I vote for exceptions everywhere | Exceptions everywhere for fidelity to Python; `std::expected` only where a pass proves local handling |
| Digit limit for `int` to string | Keep CPython's 4300 default, or unlimited | I am leaning towards keeping the defaults, items that risk compatibiliyt issues should be ruled out if possible | Keep the default and the `sys` setter, for compatibility |
| Hypothesis as a test dependency | Accept MPL-2.0 for test-only code, or write a generator in-house | Accept non mit/bsd for test only code | Accept; it never ships in any artefact |
| Generated C++ in the user's repository | Commit it as a reviewed build artefact, or treat it as a build product only | commit, also to speed up the build pipeline execution&#32; | Commit it: readable output pays off only if someone reads it |

## 13. Review round one: findings and resolutions

An external review of both documents (2026-10-30; probes run against CPython 3.14.8 and GCC 16.2.1) found ten issues. All ten are accepted; the table records what changed and where, and the paragraphs after it carry the rules that did not fit a cell. The reviewer's one recommendation not adopted is a C++23 baseline: the GCC 16 and C++26 decision of section 10.3 stands as a stated bet, and it is now a row in the risk register.

| # | Finding | Resolution | Applied in |
| --- | --- | --- | --- |
| 1 | Plain pointer stores to method slots, class pointers, header flags and shared inline caches are C++ data races; hardware atomicity does not make them valid | Every location one thread may write while another reads is a `std::atomic` (relaxed loads, release stores): `cls`, `flags`, method slots, class version tags. Inline caches hold a pointer to an immutable entry published by a release store and validated by class version. Runtime-created classes are reclaimed under RCU. The section 3 draft is to be rewritten with these types in round two | Section 10 (concurrency row), section 3 resolution list |
| 2 | Deferred counting needs stack accounting, so "no stack scanning" was contradicted; side-table references break cycle-freedom; deferred destruction breaks finaliser timing; cross-thread cycles need one collector; epochs stall when a thread stops reaching safepoints | Deferred counting dropped (static functions, classes, modules are immortal); `GC_TRACKED` set per object when a side or overflow write stores a reference; synchronous cascade with deferral only for classes proven free of finalisers and weak references; one collector thread over all candidate buffers, bounded all-thread handshake under pressure ("no global stop in steady state"); safepoints at back-edges and calls, blocking calls leave the epoch | Section 10 (memory row); synchronous collector moved into phase 1, because the dialect needs cycle collection for any boxed program; concurrent collector in phase 4 |
| 3 | Checker acceptance is not a proof of runtime class or layout (`int` admits `bool` and subclasses; `float` accepts `int`; stubs, casts, ignores, permissive dependencies) | Declared type, proven runtime class and chosen representation kept apart in the IR; native representations only on proven classes; guards at every unproven boundary branch to the boxed path instead of raising | Section 2 |
| 4 | Lookup order was wrong (fields before data descriptors, class attributes before instance storage); the direct `__getattr__` call bypassed instance writes; `{cls, offset, tag}` caches cannot see computed names, shape changes or class mutation; `vars()` must be live; widened-table equality is not CPython's `__class__` criterion | Python's order restored at every tier; instance storage checked before `__getattr__` where computed writes are possible; class version tags; live proxy `__dict__`; CPython's layout-compatibility rule for `__class__` assignment | Sections 3 and 4, case 2 |
| 5 | `(-(2**62)) // -1` retagged to a wrong negative; `norm2_fast(-2**31, -2**31)` overflowed `int64_t`; `noexcept` on a function that can allocate | `kMin / -1` promotes to bigint; the range example corrected to 30 bits and the wrong 31-bit claim kept below as the canonical certificate Z3 must reject; `noexcept` removed where promotion can allocate | Sections 4 and 6 |
| 6 | `sorted(key=)` as a projection sort, read-only slices as `span`, chained comparisons, `with`/`finally` as destructors, and C++ argument order are not generally equivalent | Effect facts added to the requirements of optimising passes: single evaluation, source-unmutated-during-live-range, suppression and replacement, left-to-right order (rules below) | This section; study section 4 superseded where it conflicts |
| 7 | Running staging twice detects nondeterminism, not environment dependence; eager dependency-order initialisation changes import semantics | Recorded-input sandbox with declared inputs hashed into the artefact key; `import` lowered to `ensure_init` at its program point with CPython's module state machine (rules below) | Section 10.2; study section 3, pass 3 superseded |
| 8 | The free-threaded 3.14 build supports neither the Limited API nor the stable ABI; mapped numpy next to islanded pandas needs a defined array protocol | Bridge built against the full C API of one pinned 3.15t minor (3.14t until 2026-11-01), rebuilt per release; PEP 803's `abi3t` (3.15) reopens a stable-ABI bridge, kept as an option until the bridge's API needs are known; array boundary protocol specified below | Section 10.1; study section 8 |
| 9 | Widening a dependency's layout from application code invalidates its precompiled binary and every consumer's offsets | Exported layouts are stable; cross-package attribute additions go to overflow or side storage (tier 2) with a lint report; whole-program re-specialisation from retained IR is an optional mode with widening facts in the cache key | Section 10 (libraries row) |
| 10 | "Sound-by-construction" overstated testing; composition also depends on runtime, staging, plugins and emission; 3 to 4 engineers over 33 months is 8 to 11 engineer-years, not 6 to 8; phase 1 cannot be GIL-free and single-threaded at once; figures are hypotheses | Wording corrected; obligations added for runtime, emitter, staging and plugins; effort restated; phase 1 is single-threaded; speed, bridge-latency and scaling figures are labelled hypotheses to be measured on named workloads. The drawings are embedded objects that a markdown export omits | Sections 9 and 11 |

Effect facts required by optimising passes (finding 6). A lowering may replace a Python operation only when the facts it needs are proved, and the pass declares them in its `PassSpec`:

- Single evaluation: `sorted(key=f)` computes `f` once per element and is stable, so it lowers to a stable sort over cached keys, never to a projection; chained comparisons bind each operand to a temporary once.
- Unmutated source: a slice becomes a `std::span` only when the source is proved unmutated during the span's whole live range; otherwise it copies, as Python does.
- Suppression and replacement: `with` lowers to explicit control flow (`try`, a `catch` that calls `__exit__` and rethrows unless it returned true, the normal-exit call), and `finally` to explicit control flow that handles replacement exceptions with `__context__` chaining and control transfers out of the block. An RAII guard is used only when `__exit__` is proved never to suppress and never to raise.
- Left-to-right order: the typed IR is in ANF, so every effectful subexpression is already bound in order; the emitter carries the obligation never to re-nest effectful expressions into one C++ expression, because C++ argument evaluation order is unspecified.

Module initialisation (finding 7). `import m` lowers to `ensure_init(m)` at the point where the statement executes, not hoisted; a module is absent, initialising or initialised; a partially initialised module is visible during a cycle with exactly CPython's behaviour (attributes defined so far are readable, the rest raise `ImportError`); an exception during initialisation propagates to the importer and leaves the module absent. Conditional and function-local imports therefore keep their meaning.

Array boundary protocol (finding 8). A mapped array crosses into the island as a `memoryview` over its buffer with shape, strides and dtype, converted there with `np.asarray`; an island array crosses back as a pinned view whose proxy keeps the `PyObject` alive until the compiled side releases it. Numeric dtypes only; object arrays never cross. The exporting side keeps the backing memory alive until every importing proxy is released, which the ledger reports as a crossing with a lifetime.

The constrained first dialect (phase 1). In scope: modules with the state machine above; functions, closures, defaults, keyword arguments; classes with single inheritance, properties, static and class methods, descriptors by Python's rules, `__getattr__`, computed-name access through the side table; dataclasses, enums and namedtuples through staging; exact `int`, `float`, `str`, `bytes`, `list`, `tuple`, `dict`, `set`; exceptions with chaining, `finally` and `with` by explicit control flow; generators, comprehensions, `match`, f-strings; the pure-Python standard library compiled, plus mappings for `math`, `itertools`, `collections`, `functools`, `json` and `re`. Out of scope until later milestones: threads (the runtime is single-threaded and `threading` fails with a clear message), `async`, runtime-created classes and non-stageable metaclasses, `__class__` assignment, stateful multiple inheritance, `__getattribute__`, the island, the concurrent collector, and every native representation beyond what a trivial proof allows. Everything in scope runs boxed and exact; speed is phase 2's job.

The certificate Z3 must reject (finding 5), kept as the standing example: the claim "`x` and `y` in `[-2^31, 2^31)` make `x*x + y*y` safe in `int64_t`" is false at the sum (`2^62 + 2^62 = 2^63`); the correct precondition is `[-2^30, 2^30)`. A translation-validation checker that accepts the first claim is broken; this is conformance clause C-9-1, the first test the validator must fail.

## 14. Review round two: findings and resolutions

The same reviewer read all three documents (2026-10-30; CPython 3.14.8 sources and GCC with UBSan). They closed six of round one's findings at the design level, including the corrected arithmetic, which matched CPython on 1,156 floor-division and modulo cases. Eight findings remain, all accepted; the table says what changed and where, and the lists after it carry the revised gate and the protocols that stay open.

| # | Finding | Resolution | Applied in |
| --- | --- | --- | --- |
| 1 | The phase-1 library list was not closed over its own dependencies (`logging` needs `threading`, `traceback` and `sys._getframe`; `argparse` needs `gettext`; `_pydecimal` needs `contextvars`; `unittest` needs `traceback`; `copy` needs `copyreg`), and `gc.collect()` was promised in phase 1 while the collector sat in phase 2 | The phase-1 set is a dependency-closed manifest: single-threaded `threading` shim, single-threaded `contextvars`, `copyreg`, `gettext` with the C/UTF-8 `locale` subset, `traceback` formatting from source maps, compile-time call-site information for `logging.findCaller`; the build fails if the closure grows. The synchronous cycle collector moved into phase 1 | Spec section 7; roadmap; section 13 finding 2 |
| 2 | Making every snapshotted object immortal contradicted synchronous finalisation of module-level objects | Staging now yields frozen definitions (classes, functions, constants: immortal, D-19) and a runtime plan: effect statements compile and run at module initialisation with ordinary ownership; `sys.modules` visibility begins when initialisation starts | Spec sections 8 and 9; D-19 |
| 3 | Cache entries lacked the attribute name and instance shape; shadowing, deletion, base-class mutation and dict-mode shapes were unspecified; computed writes bypassed descriptors and fields | Entries keyed by class, version, interned name and shape, with a validity predicate per kind; base mutation bumps every subclass version; N entries then megamorphic; `setattr_generic` follows override, data descriptor, field, dictionary; examples corrected | Section 3 code and list; section 4 cases 2, 3, 5 |
| 4 | A per-access proxy breaks `vars(obj) is vars(obj)`, `type(vars(obj)) is dict` and `obj.__dict__ = d`; `Cls.__dict__` must be read-only; `__slots__ = ()` under a base without slots still has a dict | The dictionary slot holds a real `dict` materialised once; `obj.__dict__ = d` installs `d` and sets `DICT_DETACHED`; mapping proxy for classes; dictionary presence by CPython's MRO rule | Sections 3 and 7; spec section 3 |
| 5 | The `eq` slot returned `bool`, but `__eq__` may return any object or `NotImplemented`; the `next` slot dropped `StopIteration.value` | `richcompare` returns an object, `eq_bool` exists only where the class's `__eq__` is proved to return `bool`; `IterStep` carries the yielded or returned value and other exceptions propagate | Section 3 code |
| 6 | Specification rules differed from CPython: partially initialised modules, builtins fall-through for unbound globals, `locals()`, the cyclic finalisation sequence, NaN hashing, over-broad unobservability of addresses | All corrected as conformance clauses; address-derived values are compared up to a consistent renaming; identity-derived hashes are exempt in value but required stable and consistent with `==` | Spec sections 2, 3, 8, 9, 11 |
| 7 | Relaxed loads do not publish an entry's fields; collector access to local counts, snapshot consistency, entry reclamation and finaliser queuing were unreconciled | Acquire loads for published pointers; entries never freed and N-bounded; stale entries after class mutation are a legitimate interleaving with safety from immortality or RCU; the remaining protocols are recorded as open for phase 4 below, not as resolved | Section 10 concurrency row |
| 8 | Competing instructions: section 2 wording, `PLW0603` against admitted `global`, the 3.14t stable ABI in the topology table, obsolete side-table and cache types in examples, "every builtin", a test suite that does not exist, an unpinned reference build | All corrected in place; CPython 3.14.8, ruff and the checker are pinned in `bella.toml` and the artefact key; C-9-1 named as the validator's first clause | Sections 2, 4, 10.1, 13; spec sections 1 and 3 |

Gate 0, revised to the reviewer's four requirements: (1) a dependency-closed phase-1 manifest listing supported APIs and the adaptations they need; (2) executable conformance cases for every finding above, with intentional deviations separated from defects; (3) the generic object model corrected as code, not prose, covering dictionaries, descriptors, protocol results, lifetimes and cache validity; (4) one complete compilation path exercised on the three named programs with a pinned GCC and libstdc++ and feature probes. The effort and calendar estimates of section 11 stay provisional until (1) and (4) exist.

Open for phase 4, recorded rather than resolved: how the collector reads an owner thread's non-atomic `local` count (merge at the safepoint handshake, or make `local` a relaxed atomic and measure); re-homing objects whose owner thread has exited (CPython sets the owner to none at thread exit so later counting is atomic); a consistent class, version and descriptor snapshot under concurrent class mutation (entries are immutable, so the only race is version staleness, which is conjectured to be a legitimate interleaving and remains unproven); and finalisers queued to the owning thread against synchronous finalisation on the dropping thread (proposal: finalise synchronously when the dropping thread is the owner, queue otherwise, and declare the resulting timing thread-dependent, as it is in CPython).

The reviewer's positions on the pending decisions, for the record: the recursion counter, PEP 393 strings, Linux-first scope and a truthful implementation identity; and set iteration order matched only for value-hashed elements, which the spec's D-05 now says.

## 15. Review round three: findings and resolutions

The reviewer re-read all three documents against the pinned CPython 3.14.8 and closed the round-two items (cache keys, rich comparison, iterator values, dictionary identity, name binding, import errors, the phase-1 collector, acquire/release publication, the pinned reference build and the recorded decisions). Seven findings remain, all accepted; the table says what changed and where.

| # | Finding | Resolution | Applied in |
| --- | --- | --- | --- |
| 1 | The cyclic finalisation sequence was reversed: PEP 442 clears weak references and runs their callbacks first, then finalisers, then checks resurrection; a resurrected group lives on with dead weak references | Sequence corrected and both cases named for the conformance corpus | Spec section 9 |
| 2 | A field-backed `__dict__` cannot outlive its owner, be replaced while the old one stays usable, or be shared by two objects; the `__slots__` presence rule was wrong (`object` has no `__slots__` attribute yet a slotted subclass has no dict) | Exposure migrates promoted fields into an ordinary dictionary with its own lifetime (`DICT_EXPOSED`); real `__slots__` fields never migrate; sharing and replacement follow; dictionary presence restated as inherited layout capability | Section 3 (code, list, placement); spec section 3 |
| 3 | Cache validity missed inline-field shadowing of a class attribute and a descriptor whose own class gains `__set__`; never-freed entries holding owning references retained replaced descriptors | `ClassAttr`/`GetAttrHook` entries check promoted inline fields as well as the dictionary; entries record the found object's class and version; the found object is a borrowed reference owned by the class, released on replacement (RCU in the threaded runtime), so entries never extend a Python object's life | Section 3 code and list |
| 4 | `IterStep` kept `StopIteration.value` but lost the exception's subclass, arguments and identity, which Python-visible `next()` exposes | `IterStep` carries the original `StopIteration` instance when one was raised; the internal advance operation is separate from Python-visible `next()`, which re-raises it or constructs a fresh `StopIteration(value)` | Section 3 code |
| 5 | Splitting definition statements from effect statements by statement kind ignores defaults, decorators, class bodies and hooks, which have effects and own objects; an immortal function retained its default's resource | Staging restated as a compile-time dry run yielding code and layouts only; every definition-time expression executes at runtime creating reference-counted functions and classes; D-19 narrowed to module objects | Spec sections 8, 9, 11; section 3 code |
| 6 | D-08 risked exempting structured exception payloads and ignored programs that branch on `str(exc)` | Exemption narrowed to runtime-generated wording; user arguments, `KeyError` keys, `OSError` fields, `StopIteration.value`, `UnicodeError` fields and `name` attributes stay observable; programs depending on exempt wording are outside the guarantee and `bella-lint` flags them; harness masks wording per exception type | Spec sections 2, 10, 11 |
| 7 | The manifest was still open (`statistics` needs `bisect`; `collections` needs `keyword` and `reprlib`; `shutil` optionally imports `bz2` and `lzma`); textual conflicts remained (`threading` rejected and shimmed, `contextvars` and `copyreg` listed twice, `locals()` read-only in the tier table, `overflow` in examples, superseded mechanisms in the study) | `bisect`, `keyword`, `reprlib` added to phase 1; optional-import policy stated (runtime `ImportError`, recorded in the manifest); conflicts removed; the feasibility study marked historical | Spec sections 3, 7; sections 4, 7; study, section 1 |

The reviewer's next deliverable, adopted as the content of Gate 0's first increment: correct the cyclic-finalisation contract (done above); implement a reference model, in executable form, of dictionary exposure and replacement and of cache invalidation; add the demonstrated lifetime, descriptor and iterator-exception cases to the conformance corpus; produce the actual phase-1 dependency closure from the pinned standard library rather than by inspection; and run one complete compilation path against those cases. The phase-4 deferrals stand, and the stale class-version claim is recorded as a conjecture until the snapshot protocol exists.

## Sources and references

The verified facts about C++26, free-threaded CPython and the licences of candidate components are in the [feasibility study](https://claude.ai/artifact/A8j484xiYfh9VveHh1wod1), sections 9, 12 and Sources, looked up on 2026-10-28. The references below are the well-known project pages behind this document's design choices; they were not re-fetched today.

- [ruff rules](https://docs.astral.sh/ruff/rules/) — the `ANN`, `PGH`, `S102`/`S307`, `F403`/`F405`, `PLW0603`, `B009`/`B010` selectors
- [PEP 703, Making the Global Interpreter Lock optional](https://peps.python.org/pep-0703/) — biased reference counting, immortal and deferred objects, per-object critical sections
- [Nanopass framework](https://nanopass.org/) — many small passes over formally defined languages, used by Chez Scheme
- [Python: the full monty (Politz et al., 2013)](https://cs.brown.edu/research/plt/dl/lambda-py/) — a core calculus for Python tested against CPython's test suite
- [Z3 theorem prover](https://github.com/Z3Prover/z3) — MIT; translation-validation checks
- [Hypothesis](https://hypothesis.readthedocs.io/) — property-based testing with shrinking; MPL-2.0, test-time only

Added with review round one (links supplied by the reviewer, not re-fetched here): [Python descriptor guide](https://docs.python.org/3.14/howto/descriptor.html) (lookup order); [free-threading extension guide, Limited API section](https://docs.python.org/3.14/howto/free-threading-extensions.html#limited-c-api-and-stable-abi); [mypyc: differences from Python](https://mypyc.readthedocs.io/en/latest/differences_from_python.html) (runtime checks at boundaries); [Python sorting guide](https://docs.python.org/3.14/howto/sorting.html) (stability, key evaluation); [C++ standard draft, data races](https://eel.is/c++draft/intro.races).
