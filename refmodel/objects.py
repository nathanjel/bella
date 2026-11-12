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
  ``obj.__dict__ = d`` is ordinary and releases them in insertion order. An exposed dict is an
  ordinary ``dict`` to the program (step 3a.3): a key that is not exactly a ``str`` and
  ``popitem`` make it ordinary, as does ``clear`` unless its values are still embedded in the live
  object it was exposed from; ``copy`` is split too (all measured on 3.15.2,
  ``refmodel/tests/test_cases.py::test_an_exposed_dict_stays_split_as_cpythons``). A store keeps the new
  value before it releases the old one; a class mutation takes the new version before it
  releases the old attribute (``type_setattro``).
* Which dict an instance has is its class's (``RefClass.dict_kind``; C-3-59, measured on 3.15.2). ``inline``: the
  values in the object, as above (CPython's managed dict with inline values: a program's class, a subclass of a built-in
  type of fixed size). ``shared``: a dict of its own that shares the class's keys, made at the first write, the first
  delete or when asked for (a managed dict with no inline values: the subclass of an ``int`` or a ``tuple``, whose size
  varies); a delete of a missing name joins no keys there, and ``clear`` makes that dict ordinary. ``plain``: an ordinary
  dict made the same way (a type written in C with its own dict slot and whatever derives from it: exceptions,
  ``partial``, ``SimpleNamespace``, ``OrderedDict``, the ``io`` classes); a program never deletes it.
* ``del obj.__dict__`` (C-3-58; the author's decision of 2026-11-11): the object has no dict and its inline values are
  gone, and the first thing asked of its instance storage decides what it gets (``RefObject.dropped``,
  ``Runtime.del_dict``): an ordinary dict for a plain read, one that shares the class's keys for a write, a delete or
  its ``__dict__``; a lookup the class answers alone (a data descriptor, a slot) leaves it as it is. CPython also tells
  a method call's load from a plain one (``_PyObject_GetMethod`` asks nothing of the instance), which neither the model
  nor the compiler does: deviation D-23.
* ``CacheEntry.found`` is borrowed: it holds no count. The model checks the property the C++
  header relies on: no entry that a live class's version still validates names an object that
  dies, and no cached lookup reads a dead ``found``.

* Weak references and resurrection (step 3c, Objects/weakrefobject.c, PEP 442): an object's
  ``weakrefs`` are its list in CPython's order (the basic reference first, then the others, the
  newest first); ``dealloc`` runs the finaliser holding one count, and a count left over means the
  object lives on with its weak references, its finaliser spent; otherwise the list is cleared and
  the callbacks run, each with its reference held, before any slot or the dict is released.

* The cycle collector (step 3c): ``GcState`` keeps CPython's three generations of tracked objects
  (every counted object from its creation, as in CPython); each object has its type's ``traverse``
  and ``gc_clear``; ``refmodel/collector.py`` is Python/gc.c over them.

What is not modelled yet: ``__setattr__``/``__delattr__``/``__getattribute__`` overrides,
``__class__`` assignment, dict-mode (runtime-created) classes, setattr caching, and classes as
counted objects (a class dies only by ``RefClass.dispose``; its cycles are the collector's, spec
D-04, and C-3-12 waits for them). Each is a TODO with a conformance case first.
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

SHARED_KEYS_MAX = 30          # SHARED_KEYS_MAX_SIZE (Objects/dictobject.c): a class's shared keys have thirty places


# ---------------------------------------------------------------------------------------------
# Lifetimes
# ---------------------------------------------------------------------------------------------

class GcList:
    """One of the cycle collector's lists (a ring of PyGC_Head in Python/gc.c): its objects in order. A tracked object
    is in exactly one list; ``GcState.where`` says which."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.items: dict[int, Any] = {}

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self) -> Any:
        return iter(list(self.items.values()))

    def first(self) -> Any:
        return next(iter(self.items.values()))

    def __repr__(self) -> str:
        return f"<GcList {self.name} {len(self.items)}>"


class GcState:
    """The collector's state (GCState, Python/gc.c, CPython 3.15.2: the three generations, not 3.14's incremental
    collector): which objects are tracked and in which generation, in the order they were tracked, and the counts that
    schedule a collection. The algorithm is refmodel/collector.py's; this is what the objects need while they live.
    Every model object that is a counted object of its own is tracked from its creation to its death, as an instance of
    a class, a dict and a weak reference are in CPython; a dict that stands for the values an object keeps in itself
    is not an object, and is not tracked."""

    NUM_GENERATIONS = 3

    def __init__(self) -> None:
        self.generations = [GcList(f"generation {i}") for i in range(self.NUM_GENERATIONS)]
        self.thresholds = [2000, 10, 10]          # _PyGC_InitState
        self.counts = [0, 0, 0]
        self.enabled = True
        self.collecting = False
        self.scheduled = False                    # _PY_GC_SCHEDULED_BIT: run at the next look
        self.long_lived_total = 0
        self.long_lived_pending = 0
        self.where: dict[int, GcList] = {}

    def link(self, obj: Any) -> None:
        """A new object (_PyObject_GC_Link, then _PyObject_GC_TRACK): it is counted toward the first generation's
        threshold, which, once passed, schedules a collection for the next look (_Py_ScheduleGC), and it is tracked."""
        self.counts[0] += 1
        if self.counts[0] > self.thresholds[0] and self.enabled and self.thresholds[0] and not self.collecting:
            self.scheduled = True
        self.track(obj)

    def is_tracked(self, obj: Any) -> bool:
        return id(obj) in self.where

    def track(self, obj: Any) -> None:
        """_PyObject_GC_TRACK: at the end of the first generation."""
        if self.is_tracked(obj):
            raise ModelError(f"{obj!r} tracked twice")
        self.append(obj, self.generations[0])

    def untrack(self, obj: Any) -> None:
        """PyObject_GC_UnTrack: out of whatever list holds it, a collection's own lists included; nothing if it is not
        tracked."""
        lst = self.where.pop(id(obj), None)
        if lst is not None:
            del lst.items[id(obj)]

    def free(self, obj: Any) -> None:
        """PyObject_GC_Del: the object's memory goes, and it no longer counts toward the threshold."""
        self.untrack(obj)
        if self.counts[0] > 0:
            self.counts[0] -= 1

    def append(self, obj: Any, lst: GcList) -> None:
        lst.items[id(obj)] = obj
        self.where[id(obj)] = lst

    def move(self, obj: Any, lst: GcList) -> None:
        """gc_list_move: out of its list, to the end of `lst`."""
        self.untrack(obj)
        self.append(obj, lst)

    def merge(self, src: GcList, dst: GcList) -> None:
        """gc_list_merge: every object of `src`, in order, to the end of `dst`."""
        for obj in list(src.items.values()):
            self.move(obj, dst)


class Heap:
    """What the lifetime checks need to see: the live classes (whose versions validate cache
    entries), the sites, and the deaths of tagged objects, in order; and the collector's lists."""

    def __init__(self) -> None:
        # held weakly: the registry must not keep a dead class alive (C-3-12)
        self.classes: weakref.WeakSet[RefClass] = weakref.WeakSet()
        self.sites: weakref.WeakSet[Site] = weakref.WeakSet()
        self.deaths: list[Any] = []
        self.gc = GcState()

    def died(self, obj: RefObject) -> None:
        """RL-20: an entry a live class still validates never names an object that dies."""
        live = {c.version for c in self.classes}
        for site in self.sites:
            for e in site.entries:
                if e.found is obj and e.version in live:
                    raise ModelError(f"a valid cache entry for {e.name!r} names {obj!r}, which dies")


HEAP = Heap()


def _counted(v: Any) -> bool:
    """A value that is a counted object of the model's (a class is not one yet, nor an int or a tag)."""
    return isinstance(v, (RefObject, RefDict, RefWeak))


def incref(v: Any) -> None:
    if isinstance(v, (RefObject, RefDict, RefWeak)):
        if not v.alive:
            raise ModelError(f"a reference to a dead {v!r} was taken")
        v.refs += 1


def decref(v: Any) -> None:
    if isinstance(v, (RefObject, RefDict, RefWeak)):
        if v.refs <= 0:
            raise ModelError(f"{v!r} released more often than it was held")
        v.refs -= 1
        if v.refs == 0:
            v.dealloc()


class RefDict(dict[Any, Any]):
    """An instance dict as an object of its own: counted, shareable, outliving its owner.
    ``split`` is the class whose shared keys it uses (a dict made by exposure), or None for an
    ordinary dict; it decides the order in which the values are released when the dict dies.
    ``owner`` is the live object whose inline values this dict's values are (CPython 3.13+'s
    materialised dict), until the object dies or gets another dict: ``clear`` keeps such a dict
    split, and makes any other one ordinary."""

    def __init__(self, items: Any = (), split: RefClass | None = None) -> None:
        super().__init__(items)
        self.split = split
        self.owner: RefObject | None = None
        self.refs = 0
        self.alive = True
        self.heap = HEAP

    def made(self) -> RefDict:
        """The dict is an object of the program's from now on (a dict made by exposure, a copy, a new dict given to an
        object): CPython tracks every dict from its creation (3.14+, GH-127010)."""
        self.heap.gc.link(self)
        return self

    def __hash__(self) -> int:  # type: ignore[override]
        return id(self)

    def __eq__(self, other: object) -> bool:
        return self is other

    def note_key(self, name: str) -> None:
        """A new key of a split dict joins its class's shared keys, while there is room."""
        if self.split is not None and not self.split.note_key(name):
            self.split = None             # the keys are full: the dict becomes an ordinary one

    def _release_order(self) -> list[Any]:
        order = list(self)
        if self.split is not None:
            ranked = [k for k in self.split.keys if k in self]
            order = ranked + [k for k in self if k not in ranked]
        return order

    def dealloc(self) -> None:
        self.heap.gc.untrack(self)          # dict_dealloc: PyObject_GC_UnTrack first
        self.alive = False
        values = [self[k] for k in self._release_order()]
        self.clear()
        for v in values:
            decref(v)
        self.heap.gc.free(self)

    def traverse(self) -> list[Any]:
        """dict_traverse: the values in the table's order (a split table's in its keys' order), and for a table whose
        keys are not all str, each entry's value, then its key."""
        out: list[Any] = []
        str_keys = all(type(k) is str for k in self)
        for k in self._release_order():
            out.append(self[k])
            if not str_keys:
                out.append(k)
        return [v for v in out if _counted(v)]

    def gc_clear(self) -> None:
        """dict_tp_clear: PyDict_Clear, what the program's clear() does."""
        self.clear_()

    # ---- the program's operations on the dict (vars(obj)[k] = v, ...), measured on 3.15.2 ----
    def store(self, key: Any, value: Any) -> None:
        if self.split is not None:
            if type(key) is not str:
                self.split = None           # insertdict on a split table: a combined one first
            elif key not in self:
                self.note_key(key)
        old = self.get(key)
        incref(value)
        self[key] = value
        decref(old)

    def put(self, key: Any, value: Any) -> None:
        """insertdict for a dict's own data (a built-in base's payload): a new key's count is taken
        with the value's; a present key keeps its key, and its old value is released last."""
        old = self.get(key, UNSET)
        if old is UNSET:
            incref(key)
        incref(value)
        self[key] = value
        decref(old)

    def delete(self, key: Any) -> None:
        decref(self.pop(key))               # a split dict stays split

    def popitem_(self) -> tuple[Any, Any]:
        self.split = None                   # dict_popitem makes a split table combined first
        return self.popitem()               # the caller takes the value's count

    def clear_(self) -> None:
        values = [self[k] for k in self._release_order()]
        if self.owner is None:
            self.split = None               # detached values: the table becomes empty and combined
        self.clear()
        for v in values:
            decref(v)

    def copy_(self) -> RefDict:
        d = RefDict(self, split=self.split).made()
        for v in d.values():
            incref(v)
        return d

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
        native: tuple[str, ...] | None = None,
        dict_kind: str | None = None,
        base_weaklist: bool | None = None,
    ) -> None:
        self.name = name
        self.bases = tuple(bases)
        self.mro: tuple[RefClass, ...] = tuple(_c3(self))
        self.attrs: dict[str, Any] = dict(attrs or {})
        for v in self.attrs.values():
            incref(v)
        self.dict_view: dict[str, Any] | None = None     # class_dict
        self.version = VERSIONS.issue()
        # the shared keys of its instances' dicts, in CPython's order: the compiler's sorted
        # __static_attributes__, then each name the first time any instance stores it
        # A class has thirty places (dk_usable, _PyDict_NewKeysForClass): each key takes one, and so does each instance made
        # while more than one is left (_PyObject_InitInlineValues: "it will shrink by one before each new object"). A class
        # that has made some thirty instances therefore takes no new name, and an instance that stores one gets an ordinary
        # dict (found by the Hypothesis machine on 2026-11-11, once an operation made instances fast enough; measured).
        self.keys: list[str] = []
        self.keys_left = SHARED_KEYS_MAX
        for name in sorted(static_attributes):
            self.note_key(name)
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
        own_weak = (slots is None) or ("__weakref__" in slots)
        self.has_weakref: bool = own_weak or any(b.has_weakref for b in self.bases)
        own_slots = tuple(s for s in (self.slots or ()) if s not in ("__dict__", "__weakref__"))
        for s in own_slots:
            if s in self.attrs:
                raise ValueError(f"{s!r} in __slots__ conflicts with class variable")
        for s in sorted(own_slots):                # type_new_slots sorts them; tp_members' order is the dict's
            self.attrs[s] = SlotDescriptor(s)
        inherited_slots = tuple(dict.fromkeys(n for c in reversed(self.mro) for n in c._own_slot_names()))
        self.slot_fields = inherited_slots
        for p in self.promoted:
            if p in self.slot_fields:
                raise ValueError(f"promoted field {p!r} collides with a slot")
        self.promoted_fields = tuple(dict.fromkeys(n for c in reversed(self.mro) for n in c.promoted))
        # Which dict an instance has (type_new_descriptors, type_ready_managed_dict, ensure_nonmanaged_dict): "inline",
        # "shared" or "plain", as the module's account says. A class that says nothing has that of the nearest class in
        # its MRO that is not inline (its solid base's: class E(Mixin, Exception) is laid out as an exception).
        if dict_kind is None:
            dict_kind = next((c.dict_kind for c in self.mro[1:] if c.dict_kind != "inline"), "inline")
        if dict_kind not in ("inline", "shared", "plain"):
            raise ValueError(f"no such kind of dict: {dict_kind!r}")
        if dict_kind != "inline" and self.promoted_fields:
            raise ValueError("promoted fields are values kept in the object: an inline class's only")
        self.dict_kind: str = dict_kind
        # A built-in type's C fields (BaseException's args, __traceback__, __cause__, ...): stored in
        # the object, never in its __dict__, reached through the type's own descriptors, and released
        # in the order of the type's clear function, which names the place of the dict ("__dict__").
        # A class that declares none has that of the nearest class in its MRO that does (its solid
        # base: class E(Mixin, Exception) is laid out as an exception); object's is the dict alone.
        # "__payload__" is the built-in's own data (a dict's entries: decision 2026-11-03, a
        # subclass of a built-in type is that type's object), which its dealloc releases last.
        self.native_declared = native is not None
        if native is not None:
            self.native: tuple[str, ...] = tuple(native)
            for n in self.native:
                if n not in ("__dict__", "__payload__"):
                    self.attrs.setdefault(n, SlotDescriptor(n))
        else:
            self.native = next((c.native for c in self.mro[1:] if c.native_declared), ("__dict__",))
        self.native_fields = tuple(n for n in self.native if n not in ("__dict__", "__payload__"))
        # A built-in base that keeps its own weak reference list (set's tp_weaklistoffset): subtype_dealloc leaves the weak
        # references to the base's dealloc, which clears them after the slots and the dict, before its own data (set_dealloc).
        # A class that says nothing has its MRO's (inherited with the layout).
        self.base_weaklist: bool = base_weaklist if base_weaklist is not None else any(c.base_weaklist for c in self.mro[1:])
        for n in self.native_fields:
            if n in self.slot_fields or n in self.promoted:
                raise ValueError(f"{n!r} is a field of a built-in base")

    def set_mro(self, mro: list[RefClass]) -> None:
        """A metaclass's mro() (mro_internal): every lookup walks it, under a new version."""
        self.mro = tuple(mro)
        self.version = VERSIONS.issue()

    def _own_slot_names(self) -> tuple[str, ...]:
        return tuple(s for s in (self.slots or ()) if s != "__dict__")

    def note_key(self, name: str) -> bool:
        """Records `name` in the shared keys; False when they are full and it is not there."""
        if name in self.keys:
            return True
        if self.keys_left <= 0:
            return False
        self.keys.append(name)
        self.keys_left -= 1
        return True

    # -- lookup along the MRO -----------------------------------------------------------------
    def lookup(self, name: str) -> tuple[Any, RefClass] | None:
        for c in self.mro:
            if name in c.attrs:
                return c.attrs[name], c
        return None

    # -- mutation: every change gives this class and all subclasses new versions --------------
    def class_dict(self) -> dict[str, Any]:
        """The dict behind views of `__dict__`, made at the first one. CPython's class has one dict;
        here it holds a second count of each value, always dropped before attrs' own, so attrs
        alone decides when a value dies and no finaliser can tell the two apart."""
        if self.dict_view is None:
            self.dict_view = dict(self.attrs)
            for v in self.dict_view.values():
                incref(v)
        return self.dict_view

    def set_attr(self, name: str, value: Any) -> None:
        """type_setattro: the new value stored and the class modified before the old value is
        released, so a finaliser it runs already sees the new version."""
        old = self.attrs.get(name)
        incref(value)
        self.attrs[name] = value
        self.bump()
        if self.dict_view is not None:
            incref(value)
            stale = self.dict_view.get(name)
            self.dict_view[name] = value
            decref(stale)
        decref(old)

    def del_attr(self, name: str) -> None:
        if name not in self.attrs:
            raise AttributeError(name)
        old = self.attrs.pop(name)
        self.bump()
        if self.dict_view is not None:
            decref(self.dict_view.pop(name))
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
        if self.dict_view is not None:
            for v in self.dict_view.values():
                decref(v)
            self.dict_view = None

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
        self.inline: dict[str, Any] = {n: UNSET for n in cls.slot_fields + cls.native_fields + cls.promoted_fields}
        self.order: list[str] = []          # first-assignment order of __dict__-backed names
        self.dict: RefDict | None = None    # before exposure: the attributes not promoted; after: the object's __dict__
        self.exposed = False
        self.dropped = False                # del obj.__dict__ took its dict: the next thing asked decides what it gets (Runtime.del_dict)
        if cls.has_dict and cls.dict_kind == "inline" and cls.keys_left > 1:
            cls.keys_left -= 1              # an instance with its values in it takes one of the class's places, while more than one is left
        self.refs = 0
        self.alive = True
        self.finalized = False              # PEP 442: its finaliser has run (finalize, or dealloc)
        self.weakrefs: list[RefWeak] = []   # CPython's order: the basic reference, then the newest first
        self.tag = tag                      # a tagged object's finaliser logs its tag (the oracle compares the logs)
        self.heap = cls.heap
        # a built-in base's own data: a dict subclass's instance is a dict (its entries here)
        self.payload: RefDict | None = RefDict() if "__payload__" in cls.native else None
        self.heap.gc.link(self)             # every instance of a class is tracked (type_new_alloc: Py_TPFLAGS_HAVE_GC)

    def has_finalizer(self) -> bool:
        """tp_finalize: a class with __del__; a tagged object stands for one whose __del__ logs its tag."""
        return self.tag is not None or self.cls.lookup("__del__") is not None

    def clear_weakrefs(self) -> None:
        """PyObject_ClearWeakRefs: the basic references go first, with no callback; each of the rest is
        cleared, and held while the object is given no chance to be reached through it; a reference
        already dying has no callback called; then the callbacks in list order, and the holds are
        released last to first, as the tuple that holds them in the C is."""
        while self.weakrefs and self.weakrefs[0].basic:
            self.weakrefs.pop(0).target = None
        pending: list[tuple[RefWeak, Any]] = []
        for w in self.weakrefs:
            w.target = None
            callback, w.callback = w.callback, None
            if w.refs > 0:
                incref(w)
                pending.append((w, callback))
        self.weakrefs = []
        for w, callback in pending:
            if callback is not None:
                callback(w)
        for w, _ in reversed(pending):
            decref(w)

    def finalize(self) -> None:
        """PEP 442: a finaliser runs once, whether the object's last count went or the collector
        (at exit, the modules' objects while the namespaces are whole) ran it first."""
        if self.finalized:
            return
        self.finalized = True
        if self.tag is not None:
            self.heap.deaths.append(self.tag)
        fin = self.cls.lookup("__del__")
        if fin is not None:
            fin[0](self)

    def dealloc(self) -> None:
        """subtype_dealloc's order: the finaliser, the __slots__ of the most-derived class first
        (each class's sorted by name, as type_new stores them), then the built-in base's clear
        function (BaseException_clear: the dict, args, the traceback, the cause, the context), in
        which the dict means the __dict__-backed values in the class's shared-keys order, or the
        dict's release once it is an object of its own (measured on 3.15.2). The collector's
        tracking: untracked first, tracked again around the finaliser (a resurrected object is in
        the first generation again, at its end), freed last."""
        gc = self.heap.gc
        gc.untrack(self)
        if self.has_finalizer():
            gc.track(self)
            if not self.finalized:              # PyObject_CallFinalizerFromDealloc: the call holds a count
                self.refs = 1
                self.finalize()
                self.refs -= 1
                if self.refs > 0:               # resurrected: it lives on, with its weak references
                    return
            gc.untrack(self)
        self.alive = False
        self.heap.died(self)
        if not self.cls.base_weaklist:
            self.clear_weakrefs()
        self._clear_contents(late_weakrefs=self.cls.base_weaklist)
        gc.free(self)

    def traverse(self) -> list[Any]:
        """subtype_traverse: each class's __slots__ in the base chain (traverse_slots, in member order: sorted), then
        the managed dict (PyObject_VisitManagedDict: the dict when there is one, GH-130327, else the values the object
        keeps, in its class's keys' order), then the type (not a counted object in the model), then the built-in base's
        own traverse (BaseException_traverse: the dict, args, notes, the traceback, the cause, the context, in the order
        its clear function has them; dict_traverse for a dict's entries)."""
        out: list[Any] = []
        for c in self.cls.mro:
            for name in sorted(c._own_slot_names()):
                out.append(self.inline.get(name, UNSET))
        for name in self.cls.native:
            if name == "__dict__":
                out.extend(self._dict_referents())
            elif name == "__payload__":
                assert self.payload is not None
                str_keys = all(type(k) is str for k in self.payload)
                for k, v in self.payload.items():
                    out.append(v)
                    if not str_keys:
                        out.append(k)
            else:
                out.append(self.inline[name])
        return [v for v in out if _counted(v)]

    def _dict_referents(self) -> list[Any]:
        if self.exposed:
            return [self.dict]
        held: dict[str, Any] = {n: v for n, v in self.inline.items() if n in self.cls.promoted_fields and v is not UNSET}
        if self.dict is not None:
            held.update(self.dict)
        return [held[k] for k in self.cls.keys if k in held] + [held[k] for k in self.order if k in held and k not in self.cls.keys]

    def gc_clear(self) -> None:
        """subtype_clear: each class's __slots__ in the base chain (clear_slots), the managed dict
        (PyObject_ClearManagedDict: the values the object keeps, in its keys' order, or the dict let go of, detached
        from the object first), then the built-in base's clear function. No finaliser, no weak reference: the
        collector has seen to those."""
        self._clear_contents()

    def _clear_contents(self, late_weakrefs: bool = False) -> None:
        for c in self.cls.mro:
            for name in sorted(c._own_slot_names()):     # CPython sorts each class's slots (type_new)
                v = self.inline.get(name, UNSET)
                self.inline[name] = UNSET
                decref(v)
        for name in self.cls.native:
            if name == "__dict__":
                self._release_dict()
            elif name == "__payload__":
                assert self.payload is not None
                if late_weakrefs:                   # the base's dealloc: its weak references, then its own data
                    self.clear_weakrefs()
                items, self.payload = list(self.payload.items()), RefDict()
                for k, v in items:             # dict_dealloc and PyDict_Clear: the entries in order, each key first
                    decref(k)
                    decref(v)
            else:
                v, self.inline[name] = self.inline[name], UNSET
                decref(v)

    def _release_dict(self) -> None:
        if self.exposed:
            d, self.dict = self.dict, None
            self.exposed = False            # no dict and no values: what a dealloc after the collector's clear finds
            assert d is not None
            if d.owner is self:
                d.owner = None              # its values are detached from the dead object
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


class RefWeak:
    """A weak reference: a count of its own and a target it does not count. `target` is None once the
    target has died; `basic` is the one reference of an object with no callback, which is shared."""

    def __init__(self, target: RefObject, callback: Any) -> None:
        self.target: RefObject | None = target
        self.callback = callback
        self.basic = callback is None
        self.refs = 0
        self.alive = True
        self.heap = target.heap
        self.heap.gc.link(self)             # a weak reference is a tracked object (its callback is a reference)

    def __call__(self) -> RefObject | None:
        return self.target

    def dealloc(self) -> None:
        """weakref_dealloc: untracked, it leaves its target's list, and its callback is never called."""
        self.heap.gc.untrack(self)
        self.alive = False
        self.unlink()
        self.heap.gc.free(self)

    def unlink(self) -> None:
        """clear_weakref: out of its target's list, its callback dropped (_PyWeakref_ClearRef keeps the callback)."""
        self.clear_ref()
        self.callback = None

    def clear_ref(self) -> None:
        """_PyWeakref_ClearRef: out of its target's list, the target forgotten; the callback stays."""
        if self.target is not None:
            self.target.weakrefs.remove(self)
            self.target = None

    def traverse(self) -> list[Any]:
        """gc_traverse: the callback, a Python callable here and not a counted object of the model's."""
        return []

    def gc_clear(self) -> None:
        """gc_clear: clear_weakref_lock_held, then the callback released."""
        self.unlink()


def weak_ref(target: RefObject, callback: Any = None) -> RefWeak:
    """get_or_create_weakref: a new count on the shared basic reference if there is one; else a new
    one, the basic at the head of the list and any other right after it, so the newest comes first."""
    if not target.cls.has_weakref:
        raise TypeError(f"cannot create weak reference to '{target.cls.name}' object")
    if callback is None and target.weakrefs and target.weakrefs[0].basic:
        incref(target.weakrefs[0])
        return target.weakrefs[0]
    w = RefWeak(target, callback)
    incref(w)
    if w.basic or not target.weakrefs or not target.weakrefs[0].basic:
        target.weakrefs.insert(0, w)
    else:
        target.weakrefs.insert(1, w)
    return w


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
    def _settle(obj: RefObject, split: bool) -> None:
        """The object gets a dict of its own, its values not the object's: one that shares the class's keys, or an
        ordinary one. An object whose dict was deleted gets it at the first thing asked of its instance storage: ordinary
        when that is a plain read (_PyObject_MaterializeManagedDict with the inline values invalid: PyDict_New), sharing
        when it is a write, a delete or its __dict__ (ensure_managed_dict: new_dict_with_shared_keys). An object of a class
        that keeps no values in the object gets it at the first write, delete or __dict__, of its class's kind
        (ensure_nonmanaged_dict), and a read asks for none. No user code runs and nothing is released."""
        d = RefDict(split=obj.cls if split else None).made()
        d.refs = 1
        obj.dict = d
        obj.exposed = True
        obj.dropped = False

    def _unshare(self, obj: RefObject) -> None:
        """A name the class's keys cannot take is stored on an object whose values are in it: they move into an ordinary
        dict of the object's own, in the order they were stored (store_instance_attr_lock_held: make_dict_from_instance_
        attributes, then insertdict's resize into a combined table, which marks the inline values invalid)."""
        d = self.expose_dict(obj)
        d.split = None
        d.owner = None

    @staticmethod
    def _instance_storage(obj: RefObject, name: str) -> tuple[bool, Any]:
        """(present, value) for the *__dict__-backed* storage of `name` (never slots). This is the plain read that
        reaches the instance: an object whose dict was deleted gets an ordinary one here."""
        if obj.dropped:
            Runtime._settle(obj, split=False)
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
        if obj.dropped:
            self._settle(obj, split=True)
        elif not obj.exposed and cls.has_dict and cls.dict_kind != "inline":
            self._settle(obj, split=cls.dict_kind == "shared")
        elif not obj.exposed and cls.has_dict:
            stored = obj.inline[name] is not UNSET if name in cls.promoted_fields else obj.dict is not None and name in obj.dict
            if not stored and not cls.note_key(name):
                self._unshare(obj)          # the class's keys take no more names: an ordinary dict from here on
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
        # a delete through the object's inline values inserts the name into the shared keys before it
        # finds the attribute missing (_PyObject_StoreInstanceAttribute): a failed `del obj.y` moves y
        # in the release order of every later instance (found by the Hypothesis machine, measured on
        # 3.15.2). Once the dict is detached from the object (obj.__dict__ = d, the same dict too:
        # _PyObject_SetManagedDict), a delete goes through the dict and a missing name is just missing
        # (found by the machine again, 2026-11-07); so is the dict a dropped object gets here, whose values are its own
        if obj.dropped:
            self._settle(obj, split=True)
        elif not obj.exposed and cls.has_dict and cls.dict_kind != "inline":
            self._settle(obj, split=cls.dict_kind == "shared")     # _PyObjectDict_SetItem makes the dict before it finds the name missing
        if obj.exposed:
            assert obj.dict is not None
            if obj.dict.owner is obj:
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
        if not cls.has_dict:
            raise AttributeError(f"'{cls.name}' object has no attribute '{name}' and no __dict__ for setting new attributes")
        raise AttributeError(name)

    def expose_dict(self, obj: RefObject) -> RefDict:
        """vars(obj) / obj.__dict__: migrate promoted fields once; stable identity afterwards. The
        dict is an object of its own from here on, held by the object (one count), split: it
        shares the class's keys, so it releases its values in key order (3.13+'s materialised
        dict shares the instance's inline values)."""
        cls = obj.cls
        if not cls.has_dict:
            raise AttributeError(f"'{cls.name}' object has no attribute '__dict__'")
        if obj.dropped:
            self._settle(obj, split=True)
        elif not obj.exposed and cls.dict_kind != "inline":
            self._settle(obj, split=cls.dict_kind == "shared")
        if obj.exposed:
            assert obj.dict is not None
            return obj.dict
        d = RefDict(split=cls).made()
        for name in obj.order:                       # the references move: no count changes
            if name in cls.promoted_fields:
                d[name] = obj.inline[name]
                obj.inline[name] = UNSET            # inline slot is dead from now on
            else:
                assert obj.dict is not None
                d[name] = obj.dict[name]
        d.refs = 1
        d.owner = obj
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
            d = RefDict(d).made()                    # an ordinary dict: insertion order
            for v in d.values():
                incref(v)
        self.expose_dict(obj)
        old = obj.dict
        assert old is not None
        if old.owner is obj:
            old.owner = None                # replaced: its values are detached from obj
        incref(d)
        obj.dict = d
        decref(old)

    def drop_dict(self, obj: RefObject) -> None:
        """A C type's own `Py_CLEAR(self->dict)` (partial.__setstate__ given no dict): the object has no dict again,
        as when it was made, until an attribute is set or its __dict__ is asked for. What it held goes as the dict it
        was (exposed first), released after the object let go of it. Also `del obj.__dict__` of an instance whose
        class keeps a shared dict and no values in the object (del_dict sends it here). Not that of an inline class's
        instance, which is del_dict's own."""
        if not obj.cls.has_dict:
            raise AttributeError(f"'{obj.cls.name}' object has no attribute '__dict__'")
        decref(self._let_go(obj))

    def _let_go(self, obj: RefObject) -> RefDict:
        """The object holds no dict and no inline values; what it held is the caller's to release, as the dict it was."""
        self.expose_dict(obj)
        old = obj.dict
        assert old is not None
        if old.owner is obj:
            old.owner = None                # its values are detached from obj
        obj.dict = None
        obj.exposed = False
        return old

    def del_dict(self, obj: RefObject) -> None:
        """del obj.__dict__ of an instance whose class keeps its values in the object (subtype_setdict,
        _PyObject_SetManagedDict(obj, NULL): set_dict_inline_values, or _PyDict_DetachFromObject once the dict is an
        object). The inline values are invalid and there is no dict from before anything is released, so a finaliser
        that runs meanwhile already meets the dropped object; what it held goes as the dict it was. What it gets next
        is `_settle`'s: nothing until something is asked of its instance storage. Again, with none, changes nothing."""
        if not obj.cls.has_dict:
            raise AttributeError(f"'{obj.cls.name}' object has no attribute '__dict__'")
        if obj.cls.dict_kind == "plain":
            raise TypeError("cannot delete __dict__")      # PyObject_GenericSetDict: a C type's own dict slot is never deleted
        if obj.cls.dict_kind == "shared":
            self.drop_dict(obj)                 # no inline values to mark invalid: no dict again, as when it was made
            return
        if obj.dropped:
            return
        old = self._let_go(obj)
        obj.dropped = True
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
