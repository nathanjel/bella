"""Reference model of attribute lookup, instance storage and inline caches.

What is modelled (design document, section 3, as revised by review rounds two and three):

* A ``RefClass`` has an MRO, class attributes (plain values, descriptors, slot markers), a
  ``version`` that every mutation of the class or any base bumps, and a layout: real
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
* ``Site`` holds up to N immutable ``CacheEntry`` records keyed by class, class version,
  interned name (and, for the found object, its class and version), each kind with its own
  validity predicate. Every cached read is checked against the generic path by comparing the
  *plans* both select before any user code runs (the selected plan then runs once); a
  disagreement raises ``ModelError`` -- the model refuses to be unsound silently.
* Lifetimes are not modelled: ``CacheEntry.found`` is documented as borrowed (owned by the
  class) but is an ordinary Python reference here; the C++ header owes that property.

What is not modelled yet: ``__setattr__``/``__delattr__``/``__getattribute__`` overrides,
``__class__`` assignment, dict-mode (runtime-created) classes, and setattr caching. Each is a
TODO with a conformance case first.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


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
    ) -> None:
        self.name = name
        self.bases = tuple(bases)
        self.mro: tuple[RefClass, ...] = tuple(_c3(self))
        self.attrs: dict[str, Any] = dict(attrs or {})
        self.version = 0
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

    # -- lookup along the MRO -----------------------------------------------------------------
    def lookup(self, name: str) -> tuple[Any, RefClass] | None:
        for c in self.mro:
            if name in c.attrs:
                return c.attrs[name], c
        return None

    # -- mutation: every change bumps this class and all subclasses -------------------------
    def set_attr(self, name: str, value: Any) -> None:
        self.attrs[name] = value
        self.bump()

    def del_attr(self, name: str) -> None:
        if name not in self.attrs:
            raise AttributeError(name)
        del self.attrs[name]
        self.bump()

    def bump(self) -> None:
        self.version += 1
        for s in self.subclasses:
            s.bump()

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
    def __init__(self, cls: RefClass) -> None:
        self.cls = cls
        self.inline: dict[str, Any] = {n: UNSET for n in cls.slot_fields + cls.promoted_fields}
        self.order: list[str] = []          # first-assignment order of __dict__-backed names
        self.dict: dict[str, Any] | None = None
        self.exposed = False

    def __repr__(self) -> str:
        return f"<RefObject of {self.cls.name}>"


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
    cls: RefClass
    version: int
    name: str
    kind: str
    found: Any = None                 # borrowed: the class owns it (section 15, finding 3)
    found_cls: RefClass | None = None
    found_version: int = 0


class Site:
    """One call site: up to N immutable entries, then megamorphic."""

    N = 4

    def __init__(self) -> None:
        self.entries: list[CacheEntry] = []
        self.megamorphic = False
        self.hits = 0
        self.misses = 0

    def find(self, cls: RefClass, name: str) -> CacheEntry | None:
        for e in self.entries:
            if e.cls is cls and e.name == name:
                return e
        return None

    def install(self, entry: CacheEntry) -> None:
        if self.megamorphic:
            return
        self.entries = [e for e in self.entries if not (e.cls is entry.cls and e.name == entry.name)]
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
        # depend on the class and version of whatever object the class lookup found, because a
        # non-data descriptor can become a data descriptor through a change to its own class
        # alone (promotion), and then it must win over the instance value. Plain values cannot
        # change their descriptor status, so only model objects create the dependency. The same
        # holds for a plain class attribute whose own class later gains __get__ (C-3-11).
        dep: tuple[RefClass | None, int] = (found.cls, found.cls.version) if isinstance(found, RefObject) else (None, 0)
        # CPython's slot_tp_getattr_hook looks __getattr__ up before running the generic lookup and
        # calls it when that lookup raises AttributeError for any reason (C-3-09).
        hook_hit = cls.lookup("__getattr__")
        hook = hook_hit[0] if hook_hit is not None else None

        # 1. data descriptor on the class (slots are data descriptors)
        if hit is not None and is_data_descriptor(found):
            if isinstance(found, SlotDescriptor):
                return _Plan(SLOT, None, obj.inline[name], hook), CacheEntry(cls, version, name, SLOT)
            assert isinstance(found, RefObject)
            if found.cls.lookup("__get__") is None:
                # data descriptor without __get__: instance storage wins, then the descriptor itself
                present, v = self._instance_storage(obj, name)
                return _Plan(_UNCACHED_VALUE, None, v if present else found, hook), None
            return (_Plan(DATA_DESCRIPTOR, found, None, hook),
                    CacheEntry(cls, version, name, DATA_DESCRIPTOR, found, found.cls, found.cls.version))

        # 2. instance storage
        present, v = self._instance_storage(obj, name)
        if present:
            kind = FIELD if (not obj.exposed and name in cls.promoted_fields) else INSTANCE_DICT
            return _Plan(kind, None, v, hook), CacheEntry(cls, version, name, kind, None, dep[0], dep[1])

        # 3. non-data descriptor or plain class attribute
        if hit is not None:
            if is_descriptor(found):
                assert isinstance(found, RefObject)
                return (_Plan(NON_DATA_DESCRIPTOR, found, None, hook),
                        CacheEntry(cls, version, name, NON_DATA_DESCRIPTOR, found, found.cls, found.cls.version))
            return _Plan(CLASS_ATTR, found, found, hook), CacheEntry(cls, version, name, CLASS_ATTR, found, dep[0], dep[1])

        # 4. __getattr__, or AttributeError
        if hook is not None:
            return _Plan(GETATTR_HOOK, hook, None, None), CacheEntry(cls, version, name, GETATTR_HOOK, hook)
        return _Plan(_RAISE, None, None, None), None

    # ---- cached lookup: validity predicates per kind ------------------------------------
    def _plan_cached(self, obj: RefObject, name: str, site: Site) -> _Plan | None:
        """The plan the cache alone selects, or None when no valid entry applies. Runs no user code."""
        cls = obj.cls
        e = site.find(cls, name)
        if e is None or e.version != cls.version:
            return None
        if e.found_cls is not None and e.found_version != e.found_cls.version:
            return None                 # the found object's own class changed (gained __get__ or __set__)
        hook_hit = cls.lookup("__getattr__")
        hook = hook_hit[0] if hook_hit is not None else None   # covered by the class version
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
        try:
            if plan.kind == _RAISE:
                raise AttributeError(name)
            if plan.kind == GETATTR_HOOK:
                return plan.found(obj, name)
            if plan.kind in (DATA_DESCRIPTOR, NON_DATA_DESCRIPTOR):
                return self._call_get(plan.found, obj)
            if plan.kind == SLOT and plan.value is UNSET:
                raise AttributeError(name)
            return plan.value
        except AttributeError:
            if plan.hook is None:
                raise
            return plan.hook(obj, name)

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
        cls = obj.cls
        hit = cls.lookup(name)
        if hit is not None:
            found, _ = hit
            if isinstance(found, SlotDescriptor):
                obj.inline[name] = value
                return
            if is_data_descriptor(found):
                setter = found.cls.lookup("__set__")
                if setter is None:
                    raise AttributeError("__set__")      # data descriptor with only __delete__
                setter[0](found, obj, value)
                return
        if obj.exposed:
            assert obj.dict is not None
            obj.dict[name] = value
            return
        if name in cls.promoted_fields:
            if obj.inline[name] is UNSET:
                obj.order.append(name)
            obj.inline[name] = value
            return
        if not cls.has_dict:
            raise AttributeError(f"'{cls.name}' object has no attribute '{name}' and no __dict__ for setting new attributes")
        if obj.dict is None:
            obj.dict = {}
        if name not in obj.dict:
            obj.order.append(name)
        obj.dict[name] = value

    def delattr(self, obj: RefObject, name: str) -> None:
        cls = obj.cls
        hit = cls.lookup(name)
        if hit is not None:
            found, _ = hit
            if isinstance(found, SlotDescriptor):
                if obj.inline[name] is UNSET:
                    raise AttributeError(name)
                obj.inline[name] = UNSET
                return
            if is_data_descriptor(found):
                deleter = found.cls.lookup("__delete__")
                if deleter is None:
                    raise AttributeError("__delete__")
                deleter[0](found, obj)
                return
        if obj.exposed:
            assert obj.dict is not None
            if name not in obj.dict:
                raise AttributeError(name)
            del obj.dict[name]
            return
        if name in cls.promoted_fields and obj.inline[name] is not UNSET:
            obj.inline[name] = UNSET
            obj.order.remove(name)
            return
        if obj.dict is not None and name in obj.dict:
            del obj.dict[name]
            obj.order.remove(name)
            return
        raise AttributeError(name)

    def expose_dict(self, obj: RefObject) -> dict[str, Any]:
        """vars(obj) / obj.__dict__: migrate promoted fields once; stable identity afterwards."""
        cls = obj.cls
        if not cls.has_dict:
            raise AttributeError(f"'{cls.name}' object has no attribute '__dict__'")
        if obj.exposed:
            assert obj.dict is not None
            return obj.dict
        d: dict[str, Any] = {}
        for name in obj.order:
            if name in cls.promoted_fields:
                d[name] = obj.inline[name]
                obj.inline[name] = UNSET            # inline slot is dead from now on
            else:
                assert obj.dict is not None
                d[name] = obj.dict[name]
        obj.dict = d
        obj.order = []
        obj.exposed = True
        return d

    def set_dict(self, obj: RefObject, d: Any) -> None:
        """obj.__dict__ = d: exposes first, then installs d (which may be shared)."""
        if not obj.cls.has_dict:
            raise AttributeError(f"'{obj.cls.name}' object has no attribute '__dict__'")
        if not isinstance(d, dict):
            raise TypeError("__dict__ must be set to a dictionary")
        self.expose_dict(obj)
        obj.dict = d


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
