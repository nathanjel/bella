"""Reference model of attribute lookup, instance storage and inline caches.

What is modelled (design document, section 3, as revised by review rounds two and three):

* A ``RefClass`` has an MRO, class attributes (plain values, descriptors, slot markers), a
  ``version`` and a layout. Versions come from one process-wide counter (review log D-1): a new
  class and every mutation of a class or any of its bases take a number never issued before, so
  a version names one class in one state, and a class created after another died can never
  match the dead one's cache entries. 0 is no version: a class that gets it is never cached. The
  layout has real
  ``__slots__`` fields (reachable only through their slot descriptor) and *promoted* fields
  (attributes CPython would keep in ``__dict__`` that the compiler keeps inline until the
  dictionary is exposed). Whether instances have a ``__dict__`` is an inherited layout
  capability: ``object`` provides none; a class defined without ``__slots__`` adds one; a class
  with ``__slots__`` adds one only if ``'__dict__'`` is listed.
* A ``RefObject`` keeps inline values, an optional instance dictionary (a plain ``dict``, so
  identity, sharing and an independent lifetime come for free), an ``exposed`` flag, and the
  first-assignment order of its attributes (CPython keeps the same per-object record in
  ``_PyDictValues.insertion_order``; without it ``vars(obj)`` could not reproduce insertion
  order after promotion).
* ``Runtime.getattr/setattr/delattr`` implement Python's order: data descriptor, instance
  storage, non-data descriptor or class attribute, ``__getattr__``, ``AttributeError``.
* ``Site`` holds up to N immutable ``CacheEntry`` records keyed by class version and interned
  name; the version alone identifies the class, so an entry holds no reference to it. An entry
  also records the version of the found object's class, read through the found object, and each
  kind has its own validity predicate. Every cached read is checked against the generic path
  by comparing the *plans* both select before any user code runs (the selected plan then runs
  once); a disagreement raises ``ModelError`` -- the model refuses to be unsound silently.
* Lifetimes (task 3, RL-20, RL-49): ``RefObject`` and ``RefDict`` carry reference counts; every
  holder (an instance field, an instance dict, a class attribute, a program variable) owns one,
  and an object dies when its count reaches zero, with CPython's order (measured on 3.15.2):
  its finaliser, then its ``__slots__`` (the most-derived class's first, each class's sorted by
  name, as CPython sorts them when it makes the class), then its ``__dict__``-backed values in the *class's* shared-keys order
  (``RefClass.keys``: the sorted ``__static_attributes__``, then each name in the order any
  instance first stored it), or, once the dict is a separate object, the dict's release. A
  dict made by exposure stays split and releases its values in key order; a dict installed by
  ``obj.__dict__ = d`` is ordinary and releases them in insertion order. A store keeps the new
  value before it releases the old one; a class mutation takes the new version before it
  releases the old attribute (``type_setattro``).
* ``CacheEntry.found`` is borrowed: it holds no count. The model checks the property the C++
  header relies on: no entry that a live class's version still validates names an object that
  dies, and no cached lookup reads a dead ``found``.

What is not modelled yet: ``__setattr__``/``__delattr__``/``__getattribute__`` overrides,
``__class__`` assignment, dict-mode (runtime-created) classes, setattr caching, weak references,
and classes as counted objects (a class dies only by ``RefClass.dispose``; its cycles are the
collector's, spec D-04). Each is a TODO with a conformance case first.
"""
from __future__ import annotations

import weakref
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

NO_VERSION = 0


class _Unset:
    __slots__ = ()

    def __repr__(self) -> str:
        return "<UNSET>"


UNSET = _Unset()


class ModelError(AssertionError):
    """A model-internal invariant failed (for example an unsound cache hit)."""


class SlotDescriptor:
    """Marker for a real ``__slots__`` member; a data descriptor by construction."""

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"<slot {self.name}>"


# ---------------------------------------------------------------------------------------------
# Class versions (review log D-1, 2026-11-01)
# ---------------------------------------------------------------------------------------------

class VersionCounter:
    """The one source of class versions, shared by every class in the process.

    A per-class counter starting at 0 lets a class created at a dead class's address match the
    dead class's cache entries (review log RL-23); one counter that never reissues a number makes
    a version name exactly one class in one state, as CPython's type version tags do. The runtime's
    counter is 64 bits and issues 2**64 - 1 versions; past them a class gets NO_VERSION and is
    never cached again (CPython does the same when its tags run out). ``limit`` exists so that a
    test can reach that state.
    """

    def __init__(self, limit: int = 2**64 - 1) -> None:
        self.next = 1
        self.limit = limit

    def issue(self) -> int:
        if self.next > self.limit:
            return NO_VERSION
        version = self.next
        self.next += 1
        return version


VERSIONS = VersionCounter()

SHARED_KEYS_MAX = 30          # SHARED_KEYS_MAX_SIZE (Objects/dictobject.c): a split dict holds at most 30 keys


# ---------------------------------------------------------------------------------------------
# Lifetimes
# ---------------------------------------------------------------------------------------------

class Heap:
    """What the lifetime checks need to see: the live classes (whose versions validate cache
    entries), the sites, and the deaths of tagged objects, in order."""

    def __init__(self) -> None:
        # held weakly: the registry must not keep a dead class alive (C-3-12)
        self.classes: weakref.WeakSet[RefClass] = weakref.WeakSet()
        self.sites: weakref.WeakSet[Site] = weakref.WeakSet()
        self.deaths: list[Any] = []

    def died(self, obj: RefObject) -> None:
        """RL-20: an entry a live class still validates never names an object that dies."""
        live = {c.version for c in self.classes}
        for site in self.sites:
            for e in site.entries:
                if e.found is obj and e.version in live:
                    raise ModelError(f"a valid cache entry for {e.name!r} names {obj!r}, which dies")


HEAP = Heap()


def incref(v: Any) -> None:
    if isinstance(v, (RefObject, RefDict)):
        if not v.alive:
            raise ModelError(f"a reference to a dead {v!r} was taken")
        v.refs += 1


def decref(v: Any) -> None:
    if isinstance(v, (RefObject, RefDict)):
        if v.refs <= 0:
            raise ModelError(f"{v!r} released more often than it was held")
        v.refs -= 1
        if v.refs == 0:
            v.dealloc()


class RefDict(dict[str, Any]):
    """An instance dict as an object of its own: counted, shareable, outliving its owner.
    ``split`` is the class whose shared keys it uses (a dict made by exposure), or None for an
    ordinary dict; it decides the order in which the values are released when the dict dies."""

    def __init__(self, items: Any = (), split: RefClass | None = None) -> None:
        super().__init__(items)
        self.split = split
        self.refs = 0
        self.alive = True

    def __hash__(self) -> int:  # type: ignore[override]
        return id(self)

    def __eq__(self, other: object) -> bool:
        return self is other

    def note_key(self, name: str) -> None:
        """A new key of a split dict joins its class's shared keys, while there is room."""
        if self.split is not None and not self.split.note_key(name):
            self.split = None             # the keys are full: the dict becomes an ordinary one

    def dealloc(self) -> None:
        self.alive = False
        order = list(self)
        if self.split is not None:
            ranked = [k for k in self.split.keys if k in self]
            order = ranked + [k for k in self if k not in ranked]
        values = [self[k] for k in order]
        self.clear()
        for v in values:
            decref(v)

    def __repr__(self) -> str:
        return f"<RefDict {dict.__repr__(self)}>"


# ---------------------------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------------------------

def _c3(cls: RefClass) -> list[RefClass]:
    """C3 linearisation (the same algorithm CPython uses)."""
    seqs = [[cls]] + [list(b.mro) for b in cls.bases] + [list(cls.bases)]
    result: list[RefClass] = []
    while True:
        seqs = [s for s in seqs if s]
        if not seqs:
            return result
        for seq in seqs:
            head = seq[0]
            if not any(head in s[1:] for s in seqs):
                break
        else:
            raise TypeError("inconsistent MRO")
        result.append(head)
        for seq in seqs:
            if seq[0] is head:
                del seq[0]


class RefClass:
    def __init__(
        self,
        name: str,
        bases: tuple[RefClass, ...] = (),
        *,
        slots: tuple[str, ...] | None = None,
        promoted: tuple[str, ...] = (),
        attrs: dict[str, Any] | None = None,
        static_attributes: tuple[str, ...] = (),
        heap: Heap | None = None,
    ) -> None:
        self.name = name
        self.bases = tuple(bases)
        self.mro: tuple[RefClass, ...] = tuple(_c3(self))
        self.attrs: dict[str, Any] = dict(attrs or {})
        for v in self.attrs.values():
            incref(v)
        self.version = VERSIONS.issue()
        # the shared keys of its instances' dicts, in CPython's order: the compiler's sorted
        # __static_attributes__, then each name the first time any instance stores it
        self.keys: list[str] = sorted(static_attributes)[:SHARED_KEYS_MAX]
        self.heap = heap if heap is not None else HEAP
        self.heap.classes.add(self)
        self.subclasses: list[RefClass] = []
        for b in self.bases:
            b.subclasses.append(self)
        self.slots = tuple(slots) if slots is not None else None
        self.promoted = tuple(promoted)
        # inherited layout capability (spec, section 3)
        own_dict = (slots is None) or ("__dict__" in slots)
        self.has_dict: bool = own_dict or any(b.has_dict for b in self.bases)
        own_slots = tuple(s for s in (self.slots or ()) if s != "__dict__")
        for s in own_slots:
            if s in self.attrs:
                raise ValueError(f"{s!r} in __slots__ conflicts with class variable")
            self.attrs[s] = SlotDescriptor(s)
        inherited_slots = tuple(dict.fromkeys(n for c in reversed(self.mro) for n in c._own_slot_names()))
        self.slot_fields = inherited_slots
        for p in self.promoted:
            if p in self.slot_fields:
                raise ValueError(f"promoted field {p!r} collides with a slot")
        self.promoted_fields = tuple(dict.fromkeys(n for c in reversed(self.mro) for n in c.promoted))

    def _own_slot_names(self) -> tuple[str, ...]:
        return tuple(s for s in (self.slots or ()) if s != "__dict__")

    def note_key(self, name: str) -> bool:
        """Records `name` in the shared keys; False when they are full and it is not there."""
        if name in self.keys:
            return True
        if len(self.keys) >= SHARED_KEYS_MAX:
            return False
        self.keys.append(name)
        return True

    # -- lookup along the MRO -----------------------------------------------------------------
    def lookup(self, name: str) -> tuple[Any, RefClass] | None:
        for c in self.mro:
            if name in c.attrs:
                return c.attrs[name], c
        return None

    # -- mutation: every change gives this class and all subclasses new versions --------------
    def set_attr(self, name: str, value: Any) -> None:
        """type_setattro: the new value stored and the class modified before the old value is
        released, so a finaliser it runs already sees the new version."""
        old = self.attrs.get(name)
        incref(value)
        self.attrs[name] = value
        self.bump()
        decref(old)

    def del_attr(self, name: str) -> None:
        if name not in self.attrs:
            raise AttributeError(name)
        old = self.attrs.pop(name)
        self.bump()
        decref(old)

    def bump(self) -> None:
        self.version = VERSIONS.issue()
        for s in self.subclasses:
            s.bump()

    def unregister(self) -> None:
        """The class is dying: its bases stop propagating versions to it. Cache entries need no
        cleanup, since its versions are never issued again (review log D-1)."""
        for b in self.bases:
            b.subclasses.remove(self)
        self.heap.classes.discard(self)

    def dispose(self) -> None:
        """The class dies (the collector frees it: its MRO holds itself): it leaves the live
        classes first, so no entry is valid for it, then releases its attributes in its
        dictionary's order (type_dealloc clears tp_dict)."""
        self.unregister()
        values = list(self.attrs.values())
        self.attrs.clear()
        for v in values:
            decref(v)

    def __repr__(self) -> str:
        return f"<RefClass {self.name} v{self.version}>"


# Descriptor protocol on model objects: class attrs named __get__/__set__/__delete__ hold
# Python callables  fn(descriptor_obj, obj, [value])  operating on model objects.

def is_descriptor(found: Any) -> bool:
    return isinstance(found, RefObject) and found.cls.lookup("__get__") is not None


def is_data_descriptor(found: Any) -> bool:
    if isinstance(found, SlotDescriptor):
        return True
    return isinstance(found, RefObject) and (
        found.cls.lookup("__set__") is not None or found.cls.lookup("__delete__") is not None
    )


# ---------------------------------------------------------------------------------------------
# Objects
# ---------------------------------------------------------------------------------------------

class RefObject:
    def __init__(self, cls: RefClass, tag: Any = None) -> None:
        self.cls = cls
        self.inline: dict[str, Any] = {n: UNSET for n in cls.slot_fields + cls.promoted_fields}
        self.order: list[str] = []          # first-assignment order of __dict__-backed names
        self.dict: RefDict | None = None    # before exposure: the attributes not promoted; after: the object's __dict__
        self.exposed = False
        self.refs = 0
        self.alive = True
        self.tag = tag                      # a tagged object's death is logged (the oracle compares the logs)
        self.heap = cls.heap

    def dealloc(self) -> None:
        """subtype_dealloc's order: the finaliser, the __slots__ of the most-derived class first
        (each class's sorted by name, as type_new stores them), then the __dict__-backed values in the class's
        shared-keys order, or the dict's release once it is an object of its own."""
        fin = self.cls.lookup("__del__")
        if fin is not None:
            fin[0](self)
        self.alive = False
        if self.tag is not None:
            self.heap.deaths.append(self.tag)
        self.heap.died(self)
        for c in self.cls.mro:
            for name in sorted(c._own_slot_names()):     # CPython sorts each class's slots (type_new)
                v = self.inline.get(name, UNSET)
                self.inline[name] = UNSET
                decref(v)
        if self.exposed:
            d, self.dict = self.dict, None
            decref(d)
            return
        held: dict[str, Any] = {n: v for n, v in self.inline.items() if n in self.cls.promoted_fields and v is not UNSET}
        if self.dict is not None:
            held.update(self.dict)
        ranked = [k for k in self.cls.keys if k in held] + [k for k in self.order if k in held and k not in self.cls.keys]
        for n in self.cls.promoted_fields:
            self.inline[n] = UNSET
        self.dict = None
        for k in ranked:
            decref(held[k])

    def __repr__(self) -> str:
        return f"<RefObject of {self.cls.name}" + (f" {self.tag}>" if self.tag is not None else ">")


# ---------------------------------------------------------------------------------------------
# Inline caches
# ---------------------------------------------------------------------------------------------

DATA_DESCRIPTOR = "DataDescriptor"
SLOT = "Slot"
FIELD = "Field"
INSTANCE_DICT = "InstanceDict"
CLASS_ATTR = "ClassAttr"
NON_DATA_DESCRIPTOR = "NonDataDescriptor"
GETATTR_HOOK = "GetAttrHook"
_UNCACHED_VALUE = "UncachedValue"   # data descriptor without __get__: storage or the descriptor itself
_RAISE = "Raise"                     # nothing found and no __getattr__


@dataclass(frozen=True)
class _Plan:
    """The operation a lookup selects: its kind, the object it calls or returns, the value it
    reads without running user code, and the __getattr__ fallback looked up beforehand."""

    kind: str
    found: Any = None
    value: Any = None
    hook: Any = None

    def same_as(self, other: _Plan) -> bool:
        return (self.kind == other.kind and _same(self.found, other.found) and _same(self.value, other.value)
                and self.hook is other.hook)


@dataclass(frozen=True)
class CacheEntry:
    """Immutable once installed. ``version`` names the class and its state (review log D-1), so
    no class reference is kept; ``cls_hint`` is the class's identity as a plain number, used only
    to replace that class's older entries on install, never to validate. ``found`` is what the
    class lookup found (also for instance-storage kinds, where it is the shadowed class-level
    object); ``found_version`` is the version of its class at plan time, or NO_VERSION when its
    descriptor status cannot change. The check reads ``found.cls.version`` only after the class
    version matched: the class still owns ``found``, and ``found`` holds its own class."""

    version: int
    name: str
    kind: str
    found: Any = None                 # borrowed: the class owns it (section 15, finding 3)
    found_version: int = NO_VERSION
    cls_hint: int = 0


class Site:
    """One call site: up to N immutable entries, then megamorphic."""

    N = 4

    def __init__(self, heap: Heap | None = None) -> None:
        self.entries: list[CacheEntry] = []
        self.megamorphic = False
        self.hits = 0
        self.misses = 0
        (heap if heap is not None else HEAP).sites.add(self)

    def find(self, version: int, name: str) -> CacheEntry | None:
        if version == NO_VERSION:
            return None
        for e in self.entries:
            if e.version == version and e.name == name:
                return e
        return None

    def install(self, entry: CacheEntry) -> None:
        if self.megamorphic:
            return
        self.entries = [e for e in self.entries if not (e.cls_hint == entry.cls_hint and e.name == entry.name)]
        if len(self.entries) >= self.N:
            self.megamorphic = True
            self.entries = []
            return
        self.entries.append(entry)


# ---------------------------------------------------------------------------------------------
# Runtime: the attribute machinery
# ---------------------------------------------------------------------------------------------

class Runtime:
    """Attribute operations on model objects, with Python's semantics and Bella's caches."""

    # ---- helpers -------------------------------------------------------------------------
    @staticmethod
    def _instance_storage(obj: RefObject, name: str) -> tuple[bool, Any]:
        """(present, value) for the *__dict__-backed* storage of `name` (never slots)."""
        if obj.exposed:
            assert obj.dict is not None
            if name in obj.dict:
                return True, obj.dict[name]
            return False, None
        if name in obj.cls.promoted_fields:
            v = obj.inline[name]
            if v is not UNSET:
                return True, v
        if obj.dict is not None and name in obj.dict:
            return True, obj.dict[name]
        return False, None

    @staticmethod
    def _call_get(found: RefObject, obj: RefObject) -> Any:
        get = found.cls.lookup("__get__")
        assert get is not None
        return get[0](found, obj, obj.cls)

    @staticmethod
    def _call_attribute(hook: Any, obj: RefObject, name: str) -> Any:
        """How slot_tp_getattr_hook calls the __getattr__ it found (CPython's call_attribute): a
        function, a method descriptor, with the object and the name; another descriptor bound by
        its __get__, then called with the name; any other callable with the name alone (found
        while verifying the compiled programs of review 2026-11-03)."""
        if not isinstance(hook, RefObject):
            return hook(obj, name)
        get = hook.cls.lookup("__get__")
        if get is not None:
            bound = get[0](hook, obj, obj.cls)
            return bound(name)
        call = hook.cls.lookup("__call__")
        if call is None:
            raise TypeError(f"'{hook.cls.name}' object is not callable")
        return call[0](hook, name)

    # ---- lookup as a plan ------------------------------------------------------------------
    # Review 2026-11-01 (astra-low-01 finding 4, gemini-4-argon-high bugs 2.1.1-2.1.3): lookup is
    # split into a *plan* -- which operation Python's order selects, decided without running any
    # user code -- and its *execution*. The cache is checked by comparing the plan it selects
    # with the generic plan, so __get__ and __getattr__ run exactly once per read (C-3-10), and
    # entries are stamped with the versions seen when the plan was made, before user code can
    # mutate a class.

    def _plan_generic(self, obj: RefObject, name: str) -> tuple[_Plan, CacheEntry | None]:
        """Python's lookup order. Returns the plan and the entry to cache (or None)."""
        cls = obj.cls
        version = cls.version
        hit = cls.lookup(name)
        found, _owner = hit if hit else (None, None)
        # Finding (refmodel, 2026-10-31): an entry that resolves to *instance storage* must still
        # depend on the version of the class of whatever object the class lookup found, because a
        # non-data descriptor can become a data descriptor through a change to its own class
        # alone (promotion), and then it must win over the instance value. Plain values cannot
        # change their descriptor status, so only model objects create the dependency. The same
        # holds for a plain class attribute whose own class later gains __get__ (C-3-11).
        found_version = found.cls.version if isinstance(found, RefObject) else NO_VERSION
        cacheable = version != NO_VERSION and (found_version != NO_VERSION or not isinstance(found, RefObject))

        def entry(kind: str, cached_found: Any = None) -> CacheEntry | None:
            if not cacheable:
                return None
            return CacheEntry(version, name, kind, cached_found, found_version, id(cls))
        # CPython's slot_tp_getattr_hook looks __getattr__ up before running the generic lookup and
        # calls it when that lookup raises AttributeError for any reason (C-3-09).
        hook_hit = cls.lookup("__getattr__")
        hook = hook_hit[0] if hook_hit is not None else None

        # 1. data descriptor on the class (slots are data descriptors)
        if hit is not None and is_data_descriptor(found):
            if isinstance(found, SlotDescriptor):
                return _Plan(SLOT, None, obj.inline[name], hook), entry(SLOT)
            assert isinstance(found, RefObject)
            if found.cls.lookup("__get__") is None:
                # data descriptor without __get__: instance storage wins, then the descriptor itself
                present, v = self._instance_storage(obj, name)
                return _Plan(_UNCACHED_VALUE, None, v if present else found, hook), None
            return _Plan(DATA_DESCRIPTOR, found, None, hook), entry(DATA_DESCRIPTOR, found)

        # 2. instance storage
        present, v = self._instance_storage(obj, name)
        if present:
            kind = FIELD if (not obj.exposed and name in cls.promoted_fields) else INSTANCE_DICT
            return _Plan(kind, None, v, hook), entry(kind, found)

        # 3. non-data descriptor or plain class attribute
        if hit is not None:
            if is_descriptor(found):
                assert isinstance(found, RefObject)
                return _Plan(NON_DATA_DESCRIPTOR, found, None, hook), entry(NON_DATA_DESCRIPTOR, found)
            return _Plan(CLASS_ATTR, found, found, hook), entry(CLASS_ATTR, found)

        # 4. __getattr__, or AttributeError
        if hook is not None:
            return _Plan(GETATTR_HOOK, hook, None, None), entry(GETATTR_HOOK, hook)
        return _Plan(_RAISE, None, None, None), None

    # ---- cached lookup: validity predicates per kind ------------------------------------
    def _plan_cached(self, obj: RefObject, name: str, site: Site) -> _Plan | None:
        """The plan the cache alone selects, or None when no valid entry applies. Runs no user code."""
        cls = obj.cls
        e = site.find(cls.version, name)    # the version alone names the class (review log D-1)
        if e is None:
            return None
        if isinstance(e.found, RefObject) and not e.found.alive:
            raise ModelError(f"the entry for {name!r} is valid but its borrowed found {e.found!r} is dead")
        if e.found_version != NO_VERSION and e.found.cls.version != e.found_version:
            return None                 # the found object's own class changed (gained __get__ or __set__)
        hook_hit = cls.lookup("__getattr__")
        hook = hook_hit[0] if hook_hit is not None else None   # covered by the class version
        if e.kind in (SLOT, FIELD) and name not in obj.inline:
            # the C++ analogue reads a field offset from another layout (review log RL-23)
            raise ModelError(f"unsound cache: {name} cached as {e.kind} for a layout without that field")
        if e.kind == SLOT:
            return _Plan(SLOT, None, obj.inline[name], hook)
        if e.kind == FIELD:
            if obj.exposed:
                return None
            v = obj.inline[name]
            return _Plan(FIELD, None, v, hook) if v is not UNSET else None
        if e.kind == INSTANCE_DICT:
            if obj.dict is not None and name in obj.dict:
                return _Plan(INSTANCE_DICT, None, obj.dict[name], hook)
            return None
        if e.kind == DATA_DESCRIPTOR:
            return _Plan(DATA_DESCRIPTOR, e.found, None, hook)
        # ClassAttr / NonDataDescriptor / GetAttrHook: no instance storage may shadow the name
        present, _ = self._instance_storage(obj, name)
        if present:
            return None
        if e.kind == CLASS_ATTR:
            return _Plan(CLASS_ATTR, e.found, e.found, hook)
        if e.kind == NON_DATA_DESCRIPTOR:
            return _Plan(NON_DATA_DESCRIPTOR, e.found, None, hook)
        if e.kind == GETATTR_HOOK:
            return _Plan(GETATTR_HOOK, e.found, None, None)
        raise ModelError(f"unknown cache kind {e.kind}")

    # ---- execution: the only place user code runs ---------------------------------------
    def _execute(self, plan: _Plan, obj: RefObject, name: str) -> Any:
        """The plan's objects are owned while user code runs, as CPython's lookups take strong
        references (_PyType_LookupRef): the __getattr__ hook from the lookup until the operation
        ends, a descriptor while its __get__ runs (released as it returns or raises, before the
        hook is tried). Cache entries stay borrowed; these are the operation's own references
        (review 2026-11-02, A8-1; the order measured on 3.15.2)."""
        hook = plan.hook
        incref(hook)
        try:
            try:
                if plan.kind == _RAISE:
                    raise AttributeError(name)
                if plan.kind == GETATTR_HOOK:
                    return self._call_attribute(plan.found, obj, name)
                if plan.kind in (DATA_DESCRIPTOR, NON_DATA_DESCRIPTOR):
                    found = plan.found
                    incref(found)
                    try:
                        return self._call_get(found, obj)
                    finally:
                        decref(found)
                if plan.kind == SLOT and plan.value is UNSET:
                    raise AttributeError(name)
                return plan.value
            except AttributeError:
                if hook is None:
                    raise
            # the AttributeError is dropped before the hook runs, as slot_tp_getattr_hook's
            # PyErr_Clear does: its traceback, and what that holds, die first
            return self._call_attribute(hook, obj, name)
        finally:
            decref(hook)

    # ---- public operations ---------------------------------------------------------------
    def getattr(self, obj: RefObject, name: str, site: Site | None = None) -> Any:
        plan, entry = self._plan_generic(obj, name)
        if site is not None:
            cached = self._plan_cached(obj, name, site)
            if cached is not None:
                site.hits += 1
                if not cached.same_as(plan):
                    raise ModelError(f"unsound cache: {name} cached plan {cached} but generic plan {plan}")
            elif plan.kind != _RAISE:        # a lookup that finds nothing is not a cache event
                site.misses += 1
                if entry is not None:
                    site.install(entry)
        return self._execute(plan, obj, name)

    def setattr(self, obj: RefObject, name: str, value: Any) -> None:
        """Every store keeps the new value before it releases the old one."""
        cls = obj.cls
        hit = cls.lookup(name)
        if hit is not None:
            found, _ = hit
            if isinstance(found, SlotDescriptor):
                old = obj.inline[name]
                incref(value)
                obj.inline[name] = value
                decref(old)
                return
            if is_data_descriptor(found):
                setter = found.cls.lookup("__set__")
                if setter is None:
                    raise AttributeError("__set__")      # data descriptor with only __delete__
                setter[0](found, obj, value)
                return
        if obj.exposed:
            d = obj.dict
            assert d is not None
            old = d.get(name)
            incref(value)
            if name not in d:
                d.note_key(name)
            d[name] = value
            decref(old)
            return
        if name in cls.promoted_fields:
            old = obj.inline[name]
            if old is UNSET:
                obj.order.append(name)
                cls.note_key(name)
            incref(value)
            obj.inline[name] = value
            decref(old)
            return
        if not cls.has_dict:
            raise AttributeError(f"'{cls.name}' object has no attribute '{name}' and no __dict__ for setting new attributes")
        if obj.dict is None:
            obj.dict = RefDict(split=cls)
        old = obj.dict.get(name)
        if name not in obj.dict:
            obj.order.append(name)
            cls.note_key(name)
        incref(value)
        obj.dict[name] = value
        decref(old)

    def delattr(self, obj: RefObject, name: str) -> None:
        cls = obj.cls
        hit = cls.lookup(name)
        if hit is not None:
            found, _ = hit
            if isinstance(found, SlotDescriptor):
                old = obj.inline[name]
                if old is UNSET:
                    raise AttributeError(name)
                obj.inline[name] = UNSET
                decref(old)
                return
            if is_data_descriptor(found):
                deleter = found.cls.lookup("__delete__")
                if deleter is None:
                    raise AttributeError("__delete__")
                deleter[0](found, obj)
                return
        # a delete through a split dict inserts the name into the shared keys before it finds the
        # attribute missing (_PyObject_StoreInstanceAttribute): a failed `del obj.y` moves y in the
        # release order of every later instance (found by the Hypothesis machine, measured on 3.15.2)
        if obj.exposed:
            assert obj.dict is not None
            obj.dict.note_key(name)
            if name not in obj.dict:
                raise AttributeError(name)
            decref(obj.dict.pop(name))
            return
        if cls.has_dict:
            cls.note_key(name)
        if name in cls.promoted_fields and obj.inline[name] is not UNSET:
            old = obj.inline[name]
            obj.inline[name] = UNSET
            obj.order.remove(name)
            decref(old)
            return
        if obj.dict is not None and name in obj.dict:
            old = obj.dict.pop(name)
            obj.order.remove(name)
            decref(old)
            return
        raise AttributeError(name)

    def expose_dict(self, obj: RefObject) -> RefDict:
        """vars(obj) / obj.__dict__: migrate promoted fields once; stable identity afterwards. The
        dict is an object of its own from here on, held by the object (one count), split: it
        shares the class's keys, so it releases its values in key order (3.13+'s materialised
        dict shares the instance's inline values)."""
        cls = obj.cls
        if not cls.has_dict:
            raise AttributeError(f"'{cls.name}' object has no attribute '__dict__'")
        if obj.exposed:
            assert obj.dict is not None
            return obj.dict
        d = RefDict(split=cls)
        for name in obj.order:                       # the references move: no count changes
            if name in cls.promoted_fields:
                d[name] = obj.inline[name]
                obj.inline[name] = UNSET            # inline slot is dead from now on
            else:
                assert obj.dict is not None
                d[name] = obj.dict[name]
        d.refs = 1
        obj.dict = d
        obj.order = []
        obj.exposed = True
        return d

    def set_dict(self, obj: RefObject, d: Any) -> None:
        """obj.__dict__ = d: exposes first, then installs d (which may be shared); the old dict
        is released after the new one is held."""
        if not obj.cls.has_dict:
            raise AttributeError(f"'{obj.cls.name}' object has no attribute '__dict__'")
        if not isinstance(d, dict):
            raise TypeError("__dict__ must be set to a dictionary")
        if not isinstance(d, RefDict):
            d = RefDict(d)                           # an ordinary dict: insertion order
            for v in d.values():
                incref(v)
        self.expose_dict(obj)
        old = obj.dict
        incref(d)
        obj.dict = d
        decref(old)


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, (RefObject, RefClass, dict)) or isinstance(b, (RefObject, RefClass, dict)):
        return a is b
    return bool(a == b)


# ---------------------------------------------------------------------------------------------
# Convenience for building descriptor classes in tests
# ---------------------------------------------------------------------------------------------

def make_descriptor_class(
    name: str,
    get: Callable[[RefObject, RefObject, RefClass], Any],
    set_: Callable[[RefObject, RefObject, Any], None] | None = None,
) -> RefClass:
    attrs: dict[str, Any] = {"__get__": get}
    if set_ is not None:
        attrs["__set__"] = set_
    return RefClass(name, (), attrs=attrs)
