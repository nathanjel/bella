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
* The state of a built-in type that is written in Python (RL-507; the author's decision of 2026-11-20): a field of
  CPython's C struct has no name, so a class may declare some of its ``__slots__`` *hidden*
  (``RefClass(hidden=...)``). A hidden field is kept in the object and released as the slot it is declared as, but the
  class has no descriptor for it: no lookup by name finds it, ``getattr``, ``setattr`` and ``delattr`` under that
  name are the object's own business (its ``__dict__``, a slot or a property of a class that derives from the type),
  and only the type's own code reaches the field, through ``Runtime.state_get``, ``state_set`` and ``state_del``,
  which run no hook of any class. A hidden field and a program's attribute of the same name are two things. Some
  fields of the struct CPython's type does show, as members (``partial.func``): ``RefClass(members=...)`` names those
  of the hidden fields whose descriptor the class keeps. A program reads such a member by its name as it reads any
  slot, unless a class that derives from the type has its own attribute, slot or class attribute of the name, which
  then shadows the member and still leaves the type's own code its field. A member may be read-only
  (``RefClass(readonly=...)``, PyMemberDef's Py_READONLY): a store or a delete through it is an AttributeError, and
  the type's own code stores the field as ever. A class with hidden fields releases its slots in the order it
  declares them, which stands for the order of the C type's clear function (``partial_clear``: the function, the
  arguments, the keywords); any other class releases its own sorted by name, as CPython sorts ``__slots__``.
* ``CacheEntry.found`` is borrowed: it holds no count. The model checks the property the C++
  header relies on: no entry that a live class's version still validates names an object that
  dies, and no cached lookup reads a dead ``found``.

* Weak references and resurrection (step 3c, Objects/weakrefobject.c, PEP 442): an object's
  ``weakrefs`` are its list in CPython's order (the basic reference first, then the others, the
  newest first); ``dealloc`` runs the finaliser holding one count, and a count left over means the
  object lives on with its weak references, its finaliser spent; otherwise the list is cleared and
  the callbacks run, each with its reference held, before any slot or the dict is released.

* The cycle collector (step 3c): ``GcState`` keeps the tracked objects (every counted object from its
  creation, as in CPython) and the candidate roots, the objects a release left with a count above
  nought (the author's decision of 2026-11-14: trial deletion over candidate roots, no generations);
  each object has its type's ``traverse`` and ``gc_clear``; ``refmodel/collector.py`` is the
  collector over them.

What is not modelled yet: ``__setattr__``/``__delattr__``/``__getattribute__`` overrides,
``__class__`` assignment, dict-mode (runtime-created) classes, setattr caching, and a class's
metaclass as a counted object. Each is a TODO with a conformance case first.

A class is a counted object (C-3-12, 2026-11-24; D-19): its creator holds it, its instances hold it
(``RefObject.cls``), and it holds its bases, its MRO (itself first) and its attributes, so it dies in
a collection, by ``RefClass.traverse``, ``gc_clear`` and ``dealloc`` (type_traverse, type_clear,
type_dealloc). ``RefClass(static=True)`` stands for a built-in type: immortal.
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

    __slots__ = ("name", "owner", "readonly")

    def __init__(self, name: str, owner: RefClass | None = None, readonly: bool = False) -> None:
        self.name = name
        self.owner = owner                  # the class that declares the slot; None: a built-in's native field
        self.readonly = readonly            # PyMemberDef's Py_READONLY: no store and no delete through the member

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
    """The collector's state for trial deletion over candidate roots (the author's decision of 2026-11-14): which objects
    are tracked, which are candidates, and what schedules a collection; the algorithm is refmodel/collector.py's. Every
    model object that is a counted object of its own is tracked from its creation to its death, as an instance of a class,
    a dict and a weak reference are in CPython (a dict that stands for the values an object keeps in itself is not an
    object, and is not tracked). A collection's own lists (the unreachable objects, the callbacks to call, the survivors)
    are ``GcList``s, and ``where`` says which one holds an object while a collection runs.

    A candidate is a tracked object that a release left with a count above nought: only such an object can have become
    the way into a group that nothing outside holds. The buffer keeps each once, in the order buffered, until a collection
    takes them all as its roots; an object that dies leaves it. A collection is scheduled, for the next look, when the
    candidates are more than the first threshold and more than a quarter of the objects that were tracked after the
    last collection (the decision's rule: a structure whose count drops often is a candidate at every collection, and a
    fixed size would walk a growing heap again and again)."""

    def __init__(self) -> None:
        self.tracked: dict[int, Any] = {}
        self.candidates: dict[int, Any] = {}
        self.thresholds = [2000, 10, 10]          # gc.get_threshold(): the first is the buffer's size; the others are kept
        self.enabled = True
        self.collecting = False
        self.scheduled = False                    # a collection at the next look
        self.alive_after = 0                      # tracked objects after the last collection: the quarter rule
        self.collections = 0                      # gc.get_stats()'s numbers, the runtime's own (decided 2026-11-14)
        self.collected = 0
        self.where: dict[int, GcList] = {}

    def link(self, obj: Any) -> None:
        """A new object (_PyObject_GC_Link, then _PyObject_GC_TRACK): it is tracked. Making objects schedules nothing."""
        self.track(obj)

    def is_tracked(self, obj: Any) -> bool:
        return id(obj) in self.tracked

    def track(self, obj: Any) -> None:
        if self.is_tracked(obj):
            raise ModelError(f"{obj!r} tracked twice")
        self.tracked[id(obj)] = obj

    def untrack(self, obj: Any) -> None:
        """PyObject_GC_UnTrack: no longer tracked, and out of a collection's list if one holds it; nothing if it is not
        tracked. A candidate that is untracked stays buffered: a root that is not tracked when the collection comes is
        not taken."""
        self.tracked.pop(id(obj), None)
        self.unlist(obj)

    def possible_root(self, obj: Any) -> None:
        """A release that left the object a count above nought: a candidate, once, at the end of the buffer."""
        if not self.is_tracked(obj) or id(obj) in self.candidates:
            return
        self.candidates[id(obj)] = obj
        if (self.enabled and self.thresholds[0] and not self.collecting and len(self.candidates) > self.thresholds[0]
                and 4 * len(self.candidates) > self.alive_after):
            self.scheduled = True

    def free(self, obj: Any) -> None:
        """PyObject_GC_Del: the object's memory goes, and with it its place in the buffer."""
        self.untrack(obj)
        self.candidates.pop(id(obj), None)

    def count(self) -> tuple[int, int, int]:
        """gc.get_count(), the runtime's own numbers in CPython's shape: the candidates, and two noughts."""
        return (len(self.candidates), 0, 0)

    def unlist(self, obj: Any) -> None:
        lst = self.where.pop(id(obj), None)
        if lst is not None:
            del lst.items[id(obj)]

    def append(self, obj: Any, lst: GcList) -> None:
        lst.items[id(obj)] = obj
        self.where[id(obj)] = lst

    def move(self, obj: Any, lst: GcList) -> None:
        """gc_list_move: out of its list, to the end of `lst`."""
        self.unlist(obj)
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
        # _Py_Dealloc's look at the native stack (CPython 3.14 and later; RL-624). `stack_room` is how many deallocs fit
        # inside one another before the stack's margin is nearly used, None for a stack that is never short;
        # `dealloc_depth` counts those in flight; `delete_later` has the objects whose end was put off, each with
        # whether the collector tracked it, the last put there the first to go.
        self.stack_room: int | None = None
        self.dealloc_depth = 0
        self.delete_later: list[tuple[Any, bool]] = []

    def margin(self) -> int:
        """_Py_RecursionLimit_GetMargin: how far the native stack is from its soft limit, in the unit of _Py_Dealloc's
        two tests. In CPython that is the machine's (the stack pointer against a limit taken at the thread's start);
        here it is the room less the deallocs in flight."""
        return 1 << 30 if self.stack_room is None else self.stack_room - self.dealloc_depth

    def died(self, obj: Any) -> None:
        """RL-20: an entry a live class still validates never names an object that dies."""
        live = {c.version for c in self.classes}
        for site in self.sites:
            for e in site.entries:
                if e.found is obj and e.version in live:
                    raise ModelError(f"a valid cache entry for {e.name!r} names {obj!r}, which dies")


HEAP = Heap()


def _counted(v: Any) -> bool:
    """A value that is a counted object of the model's: an object, a dict, a weak reference, or a class a program made (a
    static type, an int or a tag is not one)."""
    return isinstance(v, (RefObject, RefDict, RefWeak)) or (isinstance(v, RefClass) and not v.static)


def incref(v: Any) -> None:
    if _counted(v):
        if not v.alive:
            raise ModelError(f"a reference to a dead {v!r} was taken")
        v.refs += 1


def decref(v: Any) -> None:
    if _counted(v):
        if v.refs <= 0:
            raise ModelError(f"{v!r} released more often than it was held")
        v.refs -= 1
        if v.refs == 0:
            _dealloc(v)
        else:
            v.heap.gc.possible_root(v)    # left above nought: a candidate root of the cycle collector


def _dealloc(v: Any) -> None:
    """_Py_Dealloc. An object dies inside the dealloc of what held it, so a chain of objects is a chain of deallocs on
    the native stack, as long as the chain. Where the stack's margin is nearly used (less than 2), the object is put
    off (_PyTrash_thread_deposit_object: untracked if it was tracked, at the front of the thread's list) and nothing of
    it runs yet, its finaliser included; a dealloc that ends with room again (a margin of 4 or more) lets everything
    put off go, the last first, each from there (_PyTrash_thread_destroy_chain), which may put more off. So a chain
    of any length ends, and below the depth at which the stack is short nothing changes: the order is the nesting's."""
    heap = v.heap
    margin = heap.margin()
    if margin < 2:
        tracked = heap.gc.is_tracked(v)
        if tracked:
            heap.gc.untrack(v)
        v.put_off = True                # its count is 0: a weak reference no longer reaches it (_Py_TryIncref fails)
        heap.delete_later.append((v, tracked))
        return
    heap.dealloc_depth += 1
    try:
        v.dealloc()
    finally:
        heap.dealloc_depth -= 1
    if heap.delete_later and margin >= 4:
        while heap.delete_later:
            later, tracked = heap.delete_later.pop()
            later.put_off = False
            if tracked:
                heap.gc.track(later)
            heap.dealloc_depth += 1
            try:
                later.dealloc()
            finally:
                heap.dealloc_depth -= 1


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

def _clear_weak_list(obj: Any) -> None:
    """PyObject_ClearWeakRefs, of an object or a class: the basic references go first, with no callback; each of the
    rest is cleared, and held while the object is given no chance to be reached through it; a reference already dying
    has no callback called; then the callbacks in list order, and the holds are released last to first, as the tuple
    that holds them in the C is."""
    while obj.weakrefs and obj.weakrefs[0].basic:
        obj.weakrefs.pop(0).target = None
    pending: list[tuple[RefWeak, Any]] = []
    for w in obj.weakrefs:
        w.target = None
        callback, w.callback = w.callback, None
        if w.refs > 0:
            incref(w)
            pending.append((w, callback))
    obj.weakrefs = []
    for w, callback in pending:
        if callback is not None:
            callback(w)
    for w, _ in reversed(pending):
        decref(w)


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


def _layout_order(cls: RefClass, mro_hook: bool) -> tuple[RefClass, ...]:
    """The order a class's layout is read in (its slots, hidden and promoted fields, dict kind, native fields): C3's. CPython
    reads the layout along tp_base's chain, which gives the same fields wherever C3 has an order, since only one base may
    have a layout ("multiple bases have instance lay-out conflict"). A metaclass's mro() may give an order where C3 has
    none: then the bases' orders, each class once."""
    try:
        return tuple(_c3(cls))
    except TypeError:
        if not mro_hook:
            raise
        return (cls, *dict.fromkeys(c for b in cls.bases for c in b.mro))


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
        hidden: tuple[str, ...] = (),
        members: tuple[str, ...] = (),
        readonly: tuple[str, ...] = (),
        release: tuple[str, ...] | None = None,
        slots_ordered: bool = False,
        static: bool = False,
        mro_hook: bool = False,
    ) -> None:
        self.name = name
        # type_new sorts a class's slot names as objects (PyList_Sort), which for plain strs is their order by code point.
        # A name that is an instance of a str subclass has its own __lt__ asked, and that decides: the slots are then
        # given in the order that sort left them, and the members and the release follow it (RL-588)
        self.slots_ordered = slots_ordered
        # tp_bases and tp_mro are objects, one each until they are replaced: `__bases__` is the tuple the class was made
        # with (type_new keeps the one it is given; a class with none gets a new (object,) of its own, which the model
        # leaves out with object itself), and `__mro__` the tuple mro_internal made
        self.bases = tuple(bases)
        # A metaclass's mro() gives the MRO (mro_internal, which type_ready calls with tp_mro still NULL): until set_mro
        # the class has none, so `__mro__` is None and a lookup finds nothing, it holds no count of one, and it is not among
        # its bases' subclasses (type_ready_add_subclasses comes after). Its layout is read in C3's order all the same
        # (RL-940)
        self.mro_hook = mro_hook
        self.mro: tuple[RefClass, ...] = _layout_order(self, mro_hook)
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
        if not mro_hook:
            for b in self.bases:
                b.subclasses.append(self)
        # A class is a counted object (C-3-12; D-19: "classes ... are reference-counted like any other"). type_new returns
        # a new reference, its creator's, and the class holds tp_bases and tp_mro, whose first entry is the class itself,
        # so a class never dies by its count alone: the collector frees it (traverse, gc_clear, dealloc below). Each of its
        # instances holds it too (PyType_GenericAlloc). A static type (one of CPython's built-in types) is immortal and
        # holds nothing counted.
        self.static: bool = static
        if static and not all(b.static for b in self.bases):
            raise ValueError("a static type derives from static types only")
        self.refs = 0 if static else 1
        self.alive = True
        self.put_off = False
        self.cleared = False                     # type_clear ran: no dict and no tp_mro, so a lookup finds nothing
        self.weakrefs: list[RefWeak] = []        # type's instances are weakly referenceable (tp_weaklistoffset)
        # the classes tp_mro holds a count of: all of the MRO until type_clear, then all but the class itself (below)
        self.mro_held: tuple[RefClass, ...] = () if static or mro_hook else self.mro
        if not static:
            self.heap.gc.link(self)              # type_new: a heap type is tracked from its allocation
            for c in self.mro_held:
                incref(c)
            for b in self.bases:
                incref(b)
        self.slots = tuple(slots) if slots is not None else None
        self.promoted = tuple(promoted)
        # inherited layout capability (spec, section 3)
        own_dict = (slots is None) or ("__dict__" in slots)
        self.has_dict: bool = own_dict or any(b.has_dict for b in self.bases)
        own_weak = (slots is None) or ("__weakref__" in slots)
        self.has_weakref: bool = own_weak or any(b.has_weakref for b in self.bases)
        own_slots = tuple(s for s in (self.slots or ()) if s not in ("__dict__", "__weakref__"))
        # the fields of a built-in type's C struct: slots with no name in the class (the module's account)
        self.hidden: frozenset[str] = frozenset(hidden)
        if not self.hidden <= set(own_slots):
            raise ValueError("a hidden field is one of the class's own __slots__")
        self.members: frozenset[str] = frozenset(members)      # of the hidden fields, those CPython's type shows
        if not self.members <= self.hidden:
            raise ValueError("a member is one of the class's hidden fields")
        for s in own_slots:
            if s in self.attrs and (s not in self.hidden or s in self.members):
                raise ValueError(f"{s!r} in __slots__ conflicts with class variable")
        for s in (own_slots if slots_ordered else sorted(own_slots)):   # type_new_slots sorts them; tp_members' order is the dict's
            if s not in self.hidden or s in self.members:
                self.attrs[s] = SlotDescriptor(s, self, s in readonly)
        if not set(readonly) <= set(own_slots):
            raise ValueError("a read-only member is one of the class's own __slots__")
        self.slot_fields = tuple(dict.fromkeys(n for c in reversed(self.mro) for n in c._own_slot_names() if n not in c.hidden))
        self.hidden_fields = tuple(dict.fromkeys(n for c in reversed(self.mro) for n in c._own_slot_names() if n in c.hidden))
        # A class that declares a slot one of its bases declares makes a second member with a cell of its own
        # (type_new_descriptors: a member for each declaration, each at its own offset; RL-541). The name's cell is that
        # of the nearest class of the MRO that declares it, which is where the lookup finds a member while every class
        # has its own; a declaration behind it keeps a cell that its own member alone reads.
        nearest: dict[str, RefClass] = {}
        behind: list[tuple[RefClass, str]] = []
        for c in self.mro:
            for n in c._own_slot_names():
                if n in c.hidden or n == "__weakref__":
                    continue
                if nearest.setdefault(n, c) is not c:
                    behind.append((c, n))
        self.shadowed_fields: tuple[tuple[RefClass | None, str], ...] = tuple(dict.fromkeys(reversed(behind)))
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
        # A built-in type's dealloc (tp_dealloc of a type written in C; RL-565 and the sweep of 2026-11-20): the order in
        # which it lets go of what its struct holds, by the names of its fields, its own and its built-in bases', with
        # "__weakref__" where it clears its list of weak references and "__dict__" where it lets go of its dict, if it
        # has them. An object of a class that derives from the type lets go of that class's slots and of a dict that class
        # added first (subtype_dealloc), and then the type's dealloc runs; the weak references go before everything only
        # when the list is not the type's own.
        self.release: tuple[str, ...] | None = tuple(release) if release is not None else None
        if self.release is not None and sorted(n for n in self.release if n not in ("__dict__", "__weakref__")) != sorted(self.hidden_fields):
            raise ValueError("a built-in type's dealloc names each of its fields once")
        # A dealloc of its own over a built-in base that has fields (an exception type whose struct adds to its base's)
        # would end with the base's dealloc. No type of the runtime's is one, so it is refused, not half done: the type's
        # dealloc alone would leave the base's fields held. A class the C makes by calling type (io.UnsupportedOperation,
        # those of PyErr_NewException) is another matter: it has no dealloc of its own, and its objects die as any class's
        # over that base do (subtype_dealloc, then the base's clear function).
        if self.release is not None and self.native_fields:
            raise ValueError("a dealloc of its own over a built-in base with fields is not written")
        self.dealloc_base: RefClass | None = next((c for c in self.mro if c.release is not None), None)
        # A slot under the name of a field of the built-in base (class E(Exception): __slots__ = ("args",)) is the name's
        # cell. The base's field is a declaration behind it, as a base class's slot of the name is, with no class to name:
        # the built-in's own reads and stores reach it, and so does the base's descriptor (RL-564).
        self.shadowed_fields += tuple((None, n) for n in self.native_fields if n in self.slot_fields)
        for n in self.native_fields:
            if n in self.promoted_fields:
                raise ValueError(f"{n!r} is a field of a built-in base")
        if mro_hook:                             # the layout is read: no MRO until the metaclass's mro() gives one
            self.mro = ()

    def set_mro(self, mro: list[RefClass]) -> None:
        """A metaclass's mro() (mro_internal): every lookup walks it, under a new version. A class made for its metaclass's
        mro() joins its bases' subclasses now (type_ready_add_subclasses)."""
        self._hold_mro(tuple(mro))
        self.version = VERSIONS.issue()
        if self.mro_hook:
            self.mro_hook = False
            for b in self.bases:
                b.subclasses.append(self)

    def _hold_mro(self, mro: tuple[RefClass, ...]) -> None:
        """tp_mro replaced (Py_XSETREF): the new tuple's classes held, the old tuple's let go of, last to first."""
        self.mro = mro
        if self.static or self.cleared:
            return
        old, self.mro_held = self.mro_held, mro
        for c in mro:
            incref(c)
        for c in reversed(old):
            decref(c)

    def _own_slot_names(self) -> tuple[str, ...]:
        return tuple(s for s in (self.slots or ()) if s != "__dict__")

    def _release_order(self) -> tuple[str, ...]:
        """Its own slots in the order an object lets go of them: a built-in type's fields as it declares them (its clear
        function's order), a class's __slots__ sorted by name (type_new sorts them)."""
        own = self._own_slot_names()
        return own if self.hidden or self.slots_ordered else tuple(sorted(own))

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
        if self.cleared:                         # find_name_in_mro with no tp_mro: nothing
            return None
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

    def reassign_bases(self, bases: tuple[RefClass, ...]) -> None:
        """type_set_bases with the bases the class has (typing's NamedTuple does it to every class it makes): each MRO in
        its hierarchy is computed again and comes out as it was, so what changes is the rest of type_set_bases_unlocked.
        The class leaves every base's subclasses and joins them again, now last (remove_all_subclasses, then
        add_all_subclasses), and it and its subclasses are modified. Other bases would change what lookups walk: not
        modelled, and the runtime refuses them."""
        if bases != self.bases:
            raise ModelError("__bases__ assigned other bases than the class has")
        self.bases = bases                       # tp_bases is the tuple assigned, the very object
        self._mro_hierarchy()
        for b in self.bases:
            b.subclasses.remove(self)
        for b in self.bases:
            b.subclasses.append(self)
        self.bump()

    def _mro_hierarchy(self) -> None:
        """mro_hierarchy: the class's MRO computed again (mro_internal makes a new tuple, equal to the old one when the bases
        are the same), then each subclass's, in the order of its base's subclasses."""
        self._hold_mro(tuple(_c3(self)))
        for s in list(self.subclasses):
            s._mro_hierarchy()

    def leave_bases(self) -> None:
        """Its bases' lists of subclasses forget it (tp_subclasses holds weak references: a collection clears them with
        the class's other weak references without callbacks, and type_dealloc's remove_all_subclasses takes the
        entries out): they stop propagating versions to it, and __subclasses__() no longer lists it."""
        for b in self.bases:
            if self in b.subclasses:
                b.subclasses.remove(self)

    def unregister(self) -> None:
        """The class is dying: its bases stop propagating versions to it. Cache entries need no
        cleanup, since its versions are never issued again (review log D-1)."""
        self.leave_bases()
        self.heap.classes.discard(self)

    def _release_dict(self) -> None:
        """The dict's values let go of in its order (PyDict_Clear, dict_dealloc); the view's second counts first, so that
        attrs alone decides when a value dies (class_dict)."""
        values = list(self.attrs.values())
        self.attrs.clear()
        if self.dict_view is not None:
            view = list(self.dict_view.values())
            self.dict_view.clear()               # emptied in place: a mappingproxy holds the dict, not the class (C-3-82)
            self.dict_view = None
            for v in view:
                decref(v)
        for v in values:
            decref(v)

    def traverse(self) -> list[Any]:
        """type_traverse: tp_dict (its values in its order, a str-keyed dict's traverse; the view's second counts with
        them), tp_mro's classes and tp_bases'. The model has no tuple objects for the two: the classes in them are visited
        as the tuples would visit them. tp_base is not a count of the model's."""
        if self.static:
            return []
        out = list(self.attrs.values()) + (list(self.dict_view.values()) if self.dict_view is not None else [])
        out += list(self.mro_held) + list(self.bases)
        return [v for v in out if _counted(v)]

    def gc_clear(self) -> None:
        """type_clear: the class modified first (PyType_Modified: no entry is valid for it or a subclass from here), its
        dict cleared, then tp_mro let go of. Of tp_mro's counts the class's own goes here, which is the cycle; the others,
        its bases' and their bases', at its dealloc, after its last object's end, which walks the MRO's layout (tp_base's
        chain in CPython, which type_dealloc lets go of; tp_bases holds every class of it until then, so nothing a program
        sees tells the two apart)."""
        self.bump()
        self._release_dict()
        if not self.cleared:
            self.cleared = True
            own = [c for c in self.mro_held if c is self]
            self.mro_held = tuple(c for c in self.mro_held if c is not self)
            for c in own:
                decref(c)

    def has_finalizer(self) -> bool:
        return False                             # type has no tp_finalize

    def clear_weakrefs(self) -> None:
        _clear_weak_list(self)

    def dealloc(self) -> None:
        """type_dealloc: untracked, out of its bases' subclasses (remove_all_subclasses) and of the live classes, its weak
        references cleared, then tp_dict let go of (empty after a collection's clear), tp_bases and tp_mro (each a
        tuple's dealloc: last to first), and freed."""
        gc = self.heap.gc
        gc.untrack(self)
        self.unregister()
        self.alive = False
        self.heap.died(self)
        self.clear_weakrefs()
        self._release_dict()
        for b in reversed(self.bases):
            decref(b)
        self.cleared = True
        held, self.mro_held = self.mro_held, ()
        for c in reversed(held):
            decref(c)
        gc.free(self)

    def dispose(self) -> None:
        """The program lets go of a class it made (its creator's count). What CPython's collector does to a class that
        nothing else holds, whose only cycle is its MRO, is done in place, as a collection would (type_clear, then the
        count's end): a full collection at every such step would make the model's Hypothesis run five times slower. A
        class an object of its own still holds lives on, whole."""
        decref(self)
        if self.alive and not self.cleared and self.refs == 1:     # tp_mro's own count alone
            incref(self)
            self.gc_clear()
            decref(self)

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

def _cell_of(obj: RefObject, owner: RefClass | None, name: str) -> tuple[dict[Any, Any], Any]:
    """Where the object keeps the slot `name` that `owner` declares, as the cells and the key among them: in its state
    when the class keeps it as a field of the built-in type's own (a member CPython's type shows: partial's func); in a
    cell of the declaration's own when a class nearer in the object's MRO declares the name again; among the inline
    values, under the name, in every other case (None: a built-in's native field)."""
    if owner is not None and name in owner.hidden:
        return obj.state, name
    if (owner, name) in obj.shadowed:
        return obj.shadowed, (owner, name)
    return obj.inline, name


def _member_cells(obj: RefObject, member: SlotDescriptor) -> tuple[dict[Any, Any], Any]:
    """Where a member reads and stores: the cell of its own declaration, whatever name a class has the member under.
    A member applies to the objects of its class and of the classes that derive from it (descr_check): one a class
    that is neither has under a name is a TypeError for a read, a store and a delete alike (RL-563)."""
    if member.owner is not None and member.owner not in obj.cls.mro:
        raise TypeError(f"descriptor '{member.name}' for '{member.owner.name}' objects doesn't apply to a '{obj.cls.name}' object")
    return _cell_of(obj, member.owner, member.name)


class _SlotsOf:
    """The cells of one class's own slots in an object: a hidden one is in the object's state, one that a nearer class
    declares again in a cell of this declaration's own, any other among its inline values."""

    def __init__(self, obj: RefObject, c: RefClass) -> None:
        self.obj, self.c = obj, c

    def get(self, name: str, default: Any) -> Any:
        cells, key = _cell_of(self.obj, self.c, name)
        return cells.get(key, default)

    def set(self, name: str, value: Any) -> None:
        cells, key = _cell_of(self.obj, self.c, name)
        cells[key] = value


class RefObject:
    def __init__(self, cls: RefClass, tag: Any = None) -> None:
        incref(cls)                         # PyType_GenericAlloc: an object of a heap type holds its type
        self.cls = cls
        self.inline: dict[str, Any] = {n: UNSET for n in cls.slot_fields + cls.native_fields + cls.promoted_fields}
        self.state: dict[str, Any] = {n: UNSET for n in cls.hidden_fields}     # a built-in type's fields that have no name
        self.exports = 0                    # a bytearray's ob_exports: the holds on its octets (buffers, below)
        # the cells of the slots a nearer class declares again: each its declaring class's and the name
        self.shadowed: dict[tuple[RefClass | None, str], Any] = {k: UNSET for k in cls.shadowed_fields}
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

    def set_class(self, cls: RefClass) -> None:
        """object_set_class between two classes whose instances have one layout and no dict (annotationlib's
        _Stringifier and ForwardRef share their __slots__; the runtime does it for its annotationlib shim only, since a
        program's __class__ assignment is [P2+]): every field stays where it is and every lookup from now on walks the
        new class, whose versions no cache entry of the old one can match. Other layouts (an instance dict to hand over,
        compatible_for_assignment's checks) are not modelled."""
        old = self.cls
        same = ((cls.slot_fields, cls.native_fields, cls.promoted_fields, cls.hidden_fields, cls.shadowed_fields)
                == (old.slot_fields, old.native_fields, old.promoted_fields, old.hidden_fields, old.shadowed_fields))
        if not same or cls.has_dict or old.has_dict or cls.has_weakref != old.has_weakref or cls.bases != old.bases:
            raise ModelError(f"__class__ from {old.name} to {cls.name}: another layout")
        incref(cls)                         # object_set_class: the new type held, then the old one let go of
        self.cls = cls
        decref(old)

    def has_finalizer(self) -> bool:
        """tp_finalize: a class with __del__; a tagged object stands for one whose __del__ logs its tag."""
        return self.tag is not None or self.cls.lookup("__del__") is not None

    def clear_weakrefs(self) -> None:
        _clear_weak_list(self)

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
                if self.refs > 0:               # resurrected: it lives on, with its weak references, and the release
                    gc.possible_root(self)      # of the finaliser's count left it above nought: a candidate
                    return
            gc.untrack(self)
        self.alive = False
        self.heap.died(self)
        base = self.cls.dealloc_base
        if not self.cls.base_weaklist and (base is None or base.release is None or "__weakref__" not in base.release):
            self.clear_weakrefs()
        self._clear_contents(late_weakrefs=self.cls.base_weaklist, dying=True)
        gc.free(self)
        decref(self.cls)                    # subtype_dealloc: the type last, after the object's memory

    def traverse(self) -> list[Any]:
        """subtype_traverse: each class's __slots__ in the base chain (traverse_slots, in member order: sorted), then
        the managed dict (PyObject_VisitManagedDict: the dict when there is one, GH-130327, else the values the object
        keeps, in its class's keys' order), then the type (a heap type's objects hold it), then the built-in base's own
        traverse (BaseException_traverse: the dict, args, notes, the traceback, the cause, the context, in the order its
        clear function has them; dict_traverse for a dict's entries). A built-in base with fields of its own has the dict
        too, so the type comes before it."""
        out: list[Any] = []
        for c in self.cls.mro:
            for name in c._release_order():
                out.append(self._slots_of(c).get(name, UNSET))
        if self.cls.native_fields:
            out.append(self.cls)
        for name in self.cls.native:
            if name == "__payload__" and not self.cls.native_fields:
                out.append(self.cls)
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
                cells, key = _cell_of(self, None, name)
                out.append(cells[key])
        if not self.cls.native_fields and "__payload__" not in self.cls.native:
            out.append(self.cls)                # object's layout: the managed dict, then the type
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

    def _slots_of(self, c: RefClass) -> _SlotsOf:
        """Where the object keeps the slots a class of its MRO declares: by name, the hidden ones apart."""
        return _SlotsOf(self, c)

    def _clear_contents(self, late_weakrefs: bool = False, dying: bool = False) -> None:
        base = self.cls.dealloc_base
        for c in self.cls.mro:
            if c is base:
                break
            for name in c._release_order():              # CPython sorts each class's slots (type_new)
                kept = self._slots_of(c)
                v = kept.get(name, UNSET)
                kept.set(name, UNSET)
                decref(v)
        if base is not None:                             # the built-in type's own dealloc, in its order
            assert base.release is not None
            if "__dict__" not in base.release:           # a dict a deriving class added: gone before the type's dealloc runs
                self._release_dict()
            for name in base.release:
                if name == "__weakref__":
                    if dying:                            # the collector's clear has seen to them already
                        self.clear_weakrefs()
                elif name == "__dict__":
                    self._release_dict()
                else:
                    v, self.state[name] = self.state[name], UNSET
                    decref(v)
            return
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
                cells, key = _cell_of(self, None, name)
                v, cells[key] = cells[key], UNSET
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

    def __init__(self, target: RefObject | RefClass, callback: Any) -> None:
        self.target: RefObject | RefClass | None = target
        self.callback = callback
        self.basic = callback is None
        self.refs = 0
        self.alive = True
        self.heap = target.heap
        self.heap.gc.link(self)             # a weak reference is a tracked object (its callback is a reference)

    def __call__(self) -> RefObject | RefClass | None:
        if self.target is not None and getattr(self.target, "put_off", False):
            return None                 # PyWeakref_GetRef on an object whose dealloc is put off: gone
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


def weak_ref(target: RefObject | RefClass, callback: Any = None) -> RefWeak:
    """get_or_create_weakref: a new count on the shared basic reference if there is one; else a new
    one, the basic at the head of the list and any other right after it, so the newest comes first.
    A class can always be referred to (type's objects have a list)."""
    if isinstance(target, RefObject) and not target.cls.has_weakref:
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
# Buffers: an exporter's holds, and the views that share them (Objects/memoryobject.c)
# ---------------------------------------------------------------------------------------------
#
# A memoryview of an object does not hold the object itself: it holds a managed buffer, the one hold on the object's
# octets (`_PyManagedBufferObject`, whose master Py_buffer holds the object and counts as one of its exports), and every
# view made of that view, a slice too, shares the same managed buffer (mbuf_add_view: one more view registered). The
# hold ends when the last view registered on it is released or dies (`_memory_release`: `--mbuf->exports == 0` is
# `mbuf_release`): the exporter's count goes down by one (a bytearray may change its size again once it is nought) and
# the exporter is let go of, so it can die there, before the view's own end goes on. A released view answers nothing.
#
# The model has the managed buffer as an object that only unreleased views hold: the master's release is its death.
# CPython's managed buffer lives on until the last view referring to it, released or not, is gone, which nothing a
# program sees can tell from this: what it does after the master's release is free memory.

class RefManagedBuffer(RefObject):
    """A managed buffer: `obj` is the exporter, while the master is held. Its end is mbuf_release: PyBuffer_Release of
    the master, the exporter's count of exports first (bytearray_releasebuffer), then the exporter let go of."""

    def _clear_contents(self, late_weakrefs: bool = False, dying: bool = False) -> None:
        exporter = self.state["obj"]
        if isinstance(exporter, RefObject):
            exporter.exports -= 1
        super()._clear_contents(late_weakrefs, dying)


def buffer_classes(heap: Heap) -> tuple[RefClass, RefClass]:
    """The two classes of a world's buffers: the managed buffer and the memoryview, each with its one field."""
    mbuf = RefClass("managedbuffer", slots=("obj",), hidden=("obj",), release=("obj",), heap=heap, static=True)
    view = RefClass("memoryview", slots=("mbuf",), hidden=("mbuf",), release=("mbuf",), heap=heap, static=True)
    return mbuf, view


def view_new(classes: tuple[RefClass, RefClass], source: RefObject, is_view: bool) -> RefObject:
    """memoryview(source), a new reference's worth of object (the caller holds it): for an exporter a new managed buffer
    (PyObject_GetBuffer: one more export), for a view one more view of its managed buffer (mbuf_add_view; a slice is
    made the same way). A released view refuses (CHECK_RELEASED)."""
    mbuf_cls, view_cls = classes
    if is_view:
        mbuf = source.state["mbuf"]
        if mbuf is UNSET:
            raise ValueError("operation forbidden on released memoryview object")
    else:
        mbuf = RefManagedBuffer(mbuf_cls)
        incref(source)
        mbuf.state["obj"] = source
        source.exports += 1
    view = RefObject(view_cls)
    incref(mbuf)
    view.state["mbuf"] = mbuf
    return view


def view_release(view: RefObject) -> None:
    """memoryview.release(): nothing for a view released already; else the view's hold on its managed buffer goes,
    which is the master's release where it was the last view (_memory_release)."""
    mbuf, view.state["mbuf"] = view.state["mbuf"], UNSET
    decref(mbuf)


def resize_check(exporter: RefObject) -> None:
    """bytearray's _canresize: a bytearray with an export cannot change its size."""
    if exporter.exports > 0:
        raise BufferError("Existing exports of data: object cannot be re-sized")


# ---------------------------------------------------------------------------------------------
# Inline caches
# ---------------------------------------------------------------------------------------------

DATA_DESCRIPTOR = "DataDescriptor"
SLOT = "Slot"
STATE = "State"                  # a member whose cell is a field of the built-in type's own (RefClass.members)
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
                # which cell is the class's matter (the member's owner is of its MRO), so the version covers it and the
                # entry holds the kind alone: no entry names a class or anything that does
                cells, key = _member_cells(obj, found)
                kind = STATE if cells is obj.state else SLOT
                # a member a class has under another name (`saved = partial.args`) reads its own cell and is not cached:
                # an entry is found by the name looked up, and reads the cell of that name. So is the member of a
                # declaration that a nearer class repeats, found by the name because the nearer class's is gone
                return _Plan(kind, None, cells[key], hook), (entry(kind) if key == name else None)
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
        if (e.kind in (SLOT, FIELD) and name not in obj.inline) or (e.kind == STATE and name not in obj.state):
            # the C++ analogue reads a field offset from another layout (review log RL-23)
            raise ModelError(f"unsound cache: {name} cached as {e.kind} for a layout without that field")
        if e.kind == SLOT:
            return _Plan(SLOT, None, obj.inline[name], hook)
        if e.kind == STATE:
            return _Plan(STATE, None, obj.state[name], hook)
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
                if plan.kind in (SLOT, STATE) and plan.value is UNSET:
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

    # ---- a built-in type's own fields (RL-507): no lookup, no hook, no descriptor ----
    def has_state(self, obj: RefObject, name: str) -> bool:
        return name in obj.cls.hidden_fields

    def state_get(self, obj: RefObject, name: str) -> Any:
        """The type's own read of its field; one never stored, or deleted, is an AttributeError of the name alone, as
        a member's is."""
        v = obj.state[name]
        if v is UNSET:
            raise AttributeError(name)
        return v

    def state_set(self, obj: RefObject, name: str, value: Any) -> None:
        old = obj.state[name]
        incref(value)
        obj.state[name] = value
        decref(old)

    def state_del(self, obj: RefObject, name: str) -> None:
        old = obj.state[name]
        if old is UNSET:
            raise AttributeError(name)
        obj.state[name] = UNSET
        decref(old)

    def setattr(self, obj: RefObject, name: str, value: Any) -> None:
        """Every store keeps the new value before it releases the old one."""
        cls = obj.cls
        hit = cls.lookup(name)
        if hit is not None:
            found, _ = hit
            if isinstance(found, SlotDescriptor):
                cells, key = _member_cells(obj, found)       # the member's own cell: a class may have it under another name
                if found.readonly:
                    raise AttributeError("readonly attribute")
                old = cells[key]
                incref(value)
                cells[key] = value
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
                cells, key = _member_cells(obj, found)
                if found.readonly:
                    raise AttributeError("readonly attribute")
                old = cells[key]
                if old is UNSET:
                    raise AttributeError(name)
                cells[key] = UNSET
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
