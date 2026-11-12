"""Paired worlds: the reference model next to real CPython classes with the same definitions.

Every operation is applied to both sides and the outcomes compared. Promotion (which
attributes the compiler keeps inline) exists only on the model side; that it is invisible
from the CPython side is exactly the property under test.

One class slot holds a class created while the program runs: ``recreate_class`` drops it with
its two instances and creates another variant (a different layout or lookup kind), so the
sites hold entries for a dead class when the new one is read through them (review log D-1).

Lifetimes (task 3): a value may be a *tagged* object, whose death both sides log (a model
finaliser, a CPython ``__del__``); descriptors are tagged too and are held only by the classes
they are installed in, so replacing one kills it while cache entries may still name it (RL-20).
``drop`` lets an object die and puts a fresh one of the same class in its place. After every
operation the two death logs must be equal, in order.

Cycles (step 3c, ``World(cycles=True)``): a value may also be one of the program's objects, so
objects hold each other and a dropped object can live on in a cycle; ``collect`` runs a collection
of one generation on both sides (CPython's automatic collector is off while such a world lives,
and both sides start with a full collection, so each object is in the same generation on both).
The deaths a collection causes are compared as a multiset: the specification leaves the order of
a group's finalisers unspecified (section 9, D-04). A value that is one of the program's objects
reads back as its place in the program's list, or "elsewhere" once dropped.
"""
from __future__ import annotations

import functools
import gc
import random
import weakref
from dataclasses import dataclass, field
from typing import Any

from refmodel import collector
from refmodel import objects as O
from refmodel.objects import ModelError, RefClass, RefObject, RefWeak, Runtime, Site, decref, incref, weak_ref, make_descriptor_class

NAMES: tuple[str, ...] = ("x", "y", "z", "s", "t", "w", "cv", "g1", "attr", "k")
RUNTIME_CLASS = 8                     # index in World.classes of the class recreate_class replaces
RUNTIME_OBJECTS = (10, 11)            # indices in World.objects of its instances
RUNTIME_VARIANTS = 5

Outcome = tuple[str, Any]   # ("value", v) | ("error", "AttributeError") | ("dict", [(k, v), ...])


class Mismatch(AssertionError):
    pass


class Tagged:
    """A CPython value whose death is logged, the counterpart of a tagged model object."""

    def __init__(self, tag: str, log: list[Any]) -> None:
        self.tag = tag
        self._log = log

    def __del__(self) -> None:
        self._log.append(self.tag)


CURRENT: World | None = None             # the world whose program objects _norm names


def _norm(v: Any) -> Any:
    """Tagged values compare by tag on both sides, an object that revives by its number, and one of the
    program's objects by its place in the program's list."""
    if hasattr(v, "revival"):
        return ("R", v.revival)
    if isinstance(v, (RefObject, Tagged)) and getattr(v, "tag", None) is not None:
        return ("T", v.tag)
    if CURRENT is not None and (isinstance(v, RefObject) or type(v) in CURRENT.real_classes):
        return ("O", CURRENT.which(v))
    if isinstance(v, (list, tuple)):
        return type(v)(_norm(x) for x in v)
    return v


def _outcome(fn: Any) -> Outcome:
    try:
        return ("value", _norm(fn()))
    except ModelError:
        raise
    except Exception as exc:  # noqa: BLE001 -- the exception class is the observable
        return ("error", type(exc).__name__)


@dataclass
class DescriptorPair:
    """A descriptor's two classes and stores. The descriptor objects themselves are held only by
    the classes they are installed in, so they die when replaced."""
    index: int
    data: bool
    model_cls: RefClass
    real_cls: type
    store_m: dict[int, Any] = field(default_factory=dict)
    store_r: dict[int, Any] = field(default_factory=dict)


class World:
    """A model world and a CPython world built from the same class definitions."""

    def __init__(self, cycles: bool = False) -> None:
        global CURRENT
        CURRENT = self
        self.cycles = cycles
        if cycles:
            gc.disable()                          # collections on CPython's side only when an operation asks
        O.HEAP = self.heap = O.Heap()
        self.real_deaths: list[Any] = []
        self.deaths_compared = 0
        self.last: tuple[Outcome, Outcome] | None = None
        self.last_deaths: list[Any] = []
        self.tags = 0
        self.tracked_m = RefClass("Tracked")
        self.weaks: list[tuple[RefWeak, Any]] = []
        self.weaks_m: list[RefWeak] = []
        self.weaks_r: list[Any] = []
        self.weak_numbers = 0
        self.revivals = 0
        self.kept_m: list[RefObject] = []
        self.kept_r: list[Any] = []
        self.reviver_weaks: list[tuple[RefWeak, Any]] = []
        self.rt = Runtime()
        # ---- model classes -----------------------------------------------------------------
        A = RefClass("A", promoted=("x", "y"), attrs={"cv": 10})
        B = RefClass("B", (A,), promoted=("z",))
        S = RefClass("S", (A,), slots=("s",))          # inherits __dict__ from A
        T = RefClass("T", slots=("t",))                # no __dict__ at all
        E = RefClass("E", (T,), slots=())              # __slots__ = () under a slotted base: still no __dict__

        def model_getattr_hook(obj: RefObject, name: str) -> Any:
            if name.startswith("g"):
                return ("G", name)
            raise AttributeError(name)

        G = RefClass("G", attrs={"__getattr__": model_getattr_hook})
        X = RefClass("X", dict_kind="plain")           # a C type's own dict slot, and what derives from it: an ordinary dict
        N = RefClass("I", dict_kind="shared")          # no values in the object: a dict of its own that shares the keys
        N.has_weakref = False                          # nor room for a weak reference (tp_itemsize)

        # ---- real classes ------------------------------------------------------------------
        class RA:
            cv = 10

        class RB(RA):
            pass

        class RS(RA):
            __slots__ = ("s",)

        class RT:
            __slots__ = ("t",)

        class RE(RT):
            __slots__ = ()

        class RG:
            def __getattr__(self, name: str) -> Any:
                if name.startswith("g"):
                    return ("G", name)
                raise AttributeError(name)

        class RX(Exception):
            pass

        class RI(int):
            pass

        self.classes: list[tuple[RefClass, type]] = [(A, RA), (B, RB), (S, RS), (T, RT), (E, RE), (G, RG), (X, RX), (N, RI)]
        self.classes.append(self._make_runtime_class(0))
        R, RR = self.classes[RUNTIME_CLASS]
        self.objects: list[tuple[RefObject, Any]] = [
            (RefObject(A), RA()), (RefObject(A), RA()),
            (RefObject(B), RB()), (RefObject(B), RB()),
            (RefObject(S), RS()), (RefObject(T), RT()), (RefObject(E), RE()), (RefObject(G), RG()),
            (RefObject(X), RX()), (RefObject(N), RI()),
            (RefObject(R), RR()), (RefObject(R), RR()),
        ]
        for m, _ in self.objects:
            incref(m)                                  # the program's variables hold them
        self.real_classes: weakref.WeakSet[type] = weakref.WeakSet(rc for _, rc in self.classes)
        if cycles:                                     # every object in the oldest generation on both sides
            collector.collect(self.heap, 2)
            gc.collect()
        # one inline cache per literal-name call site, plus one computed-name site
        self.sites: dict[str, Site] = {name: Site() for name in NAMES}
        self.sites["<computed>"] = Site()
        self.descriptors: list[DescriptorPair] = []
        self.log: list[tuple[Any, ...]] = []

    # ---- runtime-created classes (review log D-1) ------------------------------------------
    def which(self, v: Any) -> Any:
        """One of the program's objects as its place in the program's list, from either side."""
        for i, pair in enumerate(self.objects):
            if v is pair[0] or v is pair[1]:
                return i
        return "elsewhere"

    def close(self) -> None:
        """CPython's automatic collector back on after a world with cycles."""
        if self.cycles:
            gc.enable()

    def _make_runtime_class(self, variant: int) -> tuple[RefClass, type]:
        """A new model class and a new CPython class on every call, in one of five shapes."""
        A, RA = self.classes[0]
        if variant == 0:
            class R0:
                __slots__ = ("x", "k")                  # unsorted: CPython releases k first (A8-10)
            return RefClass("R0", slots=("x", "k")), R0
        if variant == 1:
            class R1:
                __slots__ = ("x",)
            return RefClass("R1", slots=("x",)), R1
        if variant == 2:
            class R2:
                x = 7
            return RefClass("R2", promoted=("y",), attrs={"x": 7}), R2
        if variant == 3:
            class R3(RA):                                  # type: ignore[misc,valid-type]  # a runtime subclass
                pass
            return RefClass("R3", (A,), promoted=("k",)), R3

        def model_hook(obj: RefObject, name: str) -> Any:
            if name in ("x", "k"):
                return ("R4", name)
            raise AttributeError(name)

        class R4:
            def __getattr__(self, name: str) -> Any:
                if name in ("x", "k"):
                    return ("R4", name)
                raise AttributeError(name)
        return RefClass("R4", attrs={"__getattr__": model_hook}), R4

    # ---- descriptor factory ----------------------------------------------------------------
    # ---- values ------------------------------------------------------------------------------
    def value(self, v: Any) -> tuple[Any, Any]:
        """An operation's value on both sides: an int, or a fresh tagged object for ("T", tag),
        held by the caller (one count on the model side) until the operation returns."""
        if isinstance(v, tuple) and v[0] == "T":
            vm = RefObject(self.tracked_m, tag=v[1])
            incref(vm)
            return vm, Tagged(v[1], self.real_deaths)
        if isinstance(v, tuple) and v[0] == "O":           # one of the program's objects
            m, r = self.objects[v[1]]
            incref(m)
            return m, r
        return v, v

    def new_tag(self) -> tuple[str, str]:
        self.tags += 1
        return ("T", f"t{self.tags}")

    @staticmethod
    def _store_m(store: dict[int, Any], key: int, value: Any) -> None:
        old = store.get(key)
        incref(value)
        store[key] = value
        decref(old)

    def make_descriptor(self, data: bool) -> tuple[DescriptorPair, RefObject, Any]:
        idx = len(self.descriptors)
        store_m: dict[int, Any] = {}
        store_r: dict[int, Any] = {}

        def get_m(desc: RefObject, obj: RefObject, owner: RefClass) -> Any:
            return store_m.get(id(obj), ("DESC", idx))

        def set_m(desc: RefObject, obj: RefObject, value: Any) -> None:
            self._store_m(store_m, id(obj), value)

        model_cls = make_descriptor_class(f"Desc{idx}", get_m, set_m if data else None)
        model = RefObject(model_cls, tag=f"d{idx}")
        deaths = self.real_deaths

        class DescR:
            def __get__(self, obj: Any, owner: Any = None) -> Any:
                if obj is None:
                    return ("DESC-CLASS", idx)
                return store_r.get(id(obj), ("DESC", idx))

            def __del__(self) -> None:
                deaths.append(f"d{idx}")

        if data:
            def __set__(self: Any, obj: Any, value: Any) -> None:
                store_r[id(obj)] = value
            DescR.__set__ = __set__  # type: ignore[attr-defined]

        pair = DescriptorPair(idx, data, model_cls, DescR, store_m, store_r)
        self.descriptors.append(pair)
        return pair, model, DescR()

    # ---- operations ------------------------------------------------------------------------
    def op_get(self, obj_i: int, name: str, computed: bool = False) -> tuple[Outcome, Outcome]:
        m, r = self.objects[obj_i]
        site = self.sites["<computed>" if computed else name]
        return _outcome(lambda: self.rt.getattr(m, name, site)), _outcome(lambda: getattr(r, name))

    def op_set(self, obj_i: int, name: str, value: Any) -> tuple[Outcome, Outcome]:
        m, r = self.objects[obj_i]
        vm, vr = self.value(value)
        out = _outcome(lambda: self.rt.setattr(m, name, vm)), _outcome(lambda: setattr(r, name, vr))
        decref(vm)                                     # the caller's temporary ends with the operation
        return out

    def op_drop(self, obj_i: int) -> tuple[Outcome, Outcome]:
        """The program drops its object: it dies, with what it holds; a fresh instance of the same
        class takes its place. The descriptor stores forget it first, on both sides alike."""
        m, r = self.objects[obj_i]
        self._forget(m, r)
        self.objects[obj_i] = (RefObject(m.cls), type(r)())
        incref(self.objects[obj_i][0])
        decref(m)
        del m, r
        return ("value", None), ("value", None)

    def op_churn(self, obj_i: int, times: int) -> tuple[Outcome, Outcome]:
        """The object dropped and replaced that many times: each instance a class makes takes one of the places its
        shared keys have, so that after some thirty the class takes no new name (C-3-60)."""
        for _ in range(times):
            self.op_drop(obj_i)
        return ("value", None), ("value", None)

    def op_weak_new(self, obj_i: int, with_callback: bool) -> tuple[Outcome, Outcome]:
        """A weak reference to an object of the program's, kept by the program: which one it is, since
        a reference with no callback is shared, or that this class has no room for one."""
        m, r = self.objects[obj_i]
        number = self.weak_numbers
        self.weak_numbers += 1
        log_m, log_r = self.heap.deaths, self.real_deaths

        def callback_m(w: RefWeak) -> None:
            log_m.append(("cb", number, w() is None))

        def callback_r(w: Any) -> None:
            log_r.append(("cb", number, w() is None))

        def known(found: Any, side: int) -> int:
            for i, pair in enumerate(self.weaks):
                if pair[side] is found:
                    return i
            return -1

        def model() -> int:
            w = weak_ref(m, callback_m if with_callback else None)
            i = known(w, 0)
            if i >= 0:
                decref(w)
                return i
            self.weaks_m.append(w)
            return -1

        def real() -> int:
            w = weakref.ref(r, callback_r if with_callback else None)
            i = known(w, 1)
            if i >= 0:
                return i
            self.weaks_r.append(w)
            return -1

        om, orr = _outcome(model), _outcome(real)
        if om == ("value", -1) and orr == ("value", -1):
            self.weaks.append((self.weaks_m.pop(), self.weaks_r.pop()))
        return om, orr

    def op_weak_call(self, weak_i: int) -> tuple[Outcome, Outcome]:
        """What it resolves to: which of the program's objects, or nothing."""
        if weak_i >= len(self.weaks):
            return ("value", None), ("value", None)
        wm, wr = self.weaks[weak_i]

        def which(found: Any, side: int) -> Any:
            if found is None:
                return "dead"
            for i, pair in enumerate(self.objects):
                if pair[side] is found:
                    return i
            return "elsewhere"
        return ("value", which(wm(), 0)), ("value", which(wr(), 1))

    def op_weak_drop(self, weak_i: int) -> tuple[Outcome, Outcome]:
        """The program drops it: a reference that dies never has its callback called."""
        if weak_i >= len(self.weaks):
            return ("value", None), ("value", None)
        wm, wr = self.weaks.pop(weak_i)
        decref(wm)
        del wm, wr
        return ("value", None), ("value", None)

    def op_revive(self, obj_i: int, name: str, tagged: tuple[str, str]) -> tuple[Outcome, Outcome]:
        """An attribute holds a new object whose finaliser keeps it, with a tagged value of its own. Its
        finaliser runs once; its weak reference, its value and its death wait for the second release."""
        m, r = self.objects[obj_i]
        tag = tagged[1]
        number = self.revivals
        self.revivals += 1
        log_m, log_r, kept_m, kept_r = self.heap.deaths, self.real_deaths, self.kept_m, self.kept_r

        def fin_m(obj: RefObject) -> None:
            log_m.append(("fin", number))
            incref(obj)
            kept_m.append(obj)

        class Real:
            __slots__ = ("value", "__weakref__")
            revival = number

            def __del__(self) -> None:
                log_r.append(("fin", number))
                kept_r.append(self)

        cm = RefClass("Reviver", slots=("value", "__weakref__"), attrs={"__del__": fin_m})
        vm = RefObject(cm)
        vm.revival = number  # type: ignore[attr-defined]
        incref(vm)
        held = RefObject(self.tracked_m, tag=tag)
        incref(held)
        vr = Real()
        vr.value = Tagged(tag, self.real_deaths)  # type: ignore[attr-defined]
        self.rt.setattr(vm, "value", held)
        decref(held)
        self.reviver_weaks.append((weak_ref(vm), weakref.ref(vr)))
        om = _outcome(functools.partial(self.rt.setattr, m, name, vm))
        decref(vm)
        orr = _outcome(functools.partial(setattr, r, name, vr))
        del vr
        return om, orr

    def op_release_kept(self) -> tuple[Outcome, Outcome]:
        """The second release: no finaliser now, and the weak reference goes before the value."""
        kept_m, self.kept_m[:] = list(self.kept_m), []
        for v in reversed(kept_m):                 # list_clear: last to first
            decref(v)
        del kept_m
        self.kept_r.clear()
        return (("value", [w[0]() is None for w in self.reviver_weaks]),
                ("value", [w[1]() is None for w in self.reviver_weaks]))

    def _forget(self, m: RefObject, r: Any) -> None:
        for pair in self.descriptors:
            decref(pair.store_m.pop(id(m), None))
            pair.store_r.pop(id(r), None)

    def op_del(self, obj_i: int, name: str) -> tuple[Outcome, Outcome]:
        m, r = self.objects[obj_i]
        return _outcome(lambda: self.rt.delattr(m, name)), _outcome(lambda: delattr(r, name))

    def op_expose(self, obj_i: int) -> tuple[Outcome, Outcome]:
        m, r = self.objects[obj_i]

        def model() -> Any:
            d1 = self.rt.expose_dict(m)
            d2 = self.rt.expose_dict(m)
            return ("stable", d1 is d2, list(d1.items()))

        def real() -> Any:
            d1 = r.__dict__
            d2 = r.__dict__
            return ("stable", d1 is d2, list(d1.items()))

        return _outcome(model), _outcome(real)

    def op_replace_dict(self, obj_i: int, src_i: int | None) -> tuple[Outcome, Outcome]:
        m, r = self.objects[obj_i]

        def model() -> Any:
            if src_i is None:
                self.rt.set_dict(m, {})
            else:
                sm, _ = self.objects[src_i]
                self.rt.set_dict(m, self.rt.expose_dict(sm))
            return None

        def real() -> Any:
            if src_i is None:
                r.__dict__ = {}
            else:
                _, sr = self.objects[src_i]
                r.__dict__ = sr.__dict__
            return None

        return _outcome(model), _outcome(real)

    def op_del_dict(self, obj_i: int, then: str, name: str, value: Any, probe: Any) -> tuple[Outcome, Outcome]:
        """del obj.__dict__, and the first thing asked of the object after it, as one operation: the sweep that follows
        every operation is a plain read, which would settle every dropped object the same way. `then` is "none" (the
        next thing decides), "get", "set", "del" or "expose". With a probe (name, tag, name, tag) two tagged values are
        then stored under the two names and the dict is deleted again, so that the order in which they die says which
        dict the object had: the one that shares the class's keys, or an ordinary one."""
        m, r = self.objects[obj_i]
        vm, vr = self.value(value)

        def model() -> Any:
            self.rt.del_dict(m)
            if then == "get":
                first = _outcome(lambda: self.rt.getattr(m, name, self.sites[name]))
            elif then == "set":
                first = _outcome(lambda: self.rt.setattr(m, name, vm))
            elif then == "del":
                first = _outcome(lambda: self.rt.delattr(m, name))
            elif then == "expose":
                first = _outcome(lambda: len(self.rt.expose_dict(m)))
            else:
                first = ("value", None)
            if probe is not None:
                for n, tag in (probe[:2], probe[2:]):
                    v = RefObject(self.tracked_m, tag=tag[1])
                    incref(v)
                    try:
                        self.rt.setattr(m, n, v)
                    finally:
                        decref(v)
                self.rt.del_dict(m)
            return first

        def real() -> Any:
            del r.__dict__
            if then == "get":
                first = _outcome(lambda: getattr(r, name))
            elif then == "set":
                first = _outcome(lambda: setattr(r, name, vr))
            elif then == "del":
                first = _outcome(lambda: delattr(r, name))
            elif then == "expose":
                first = _outcome(lambda: len(r.__dict__))
            else:
                first = ("value", None)
            if probe is not None:
                for n, tag in (probe[:2], probe[2:]):
                    setattr(r, n, Tagged(tag[1], self.real_deaths))
                del r.__dict__
            return first

        out = _outcome(model), _outcome(real)
        decref(vm)
        return out

    def op_probe(self, obj_i: int, delete_first: bool, probe: Any) -> tuple[Outcome, Outcome]:
        """Which kind of dict the class's instances have, asked of fresh ones (name, name, four tags). The object is
        dropped; on the one that takes its place two tagged values are stored under the two names, and it is dropped;
        on the next the same names are stored in the other order, and it is dropped too. An ordinary dict lets the
        values go in the order they were stored both times; one that shares the class's keys lets them go in the keys'
        order, which is not the stored order one of the two times. With `delete_first` the second name is deleted from
        the first fresh instance before anything is stored: a delete that fails joins the class's keys where the values
        are kept in the object, and joins none where the dict is the object's own."""
        n1, n2, t1, t2, t3, t4 = probe
        self.op_drop(obj_i)
        outcomes_m: list[Outcome] = []
        outcomes_r: list[Outcome] = []
        if delete_first:
            om, orr = self.op_del(obj_i, n2)
            outcomes_m.append(om)
            outcomes_r.append(orr)
        for stores in (((n1, t1), (n2, t2)), ((n2, t3), (n1, t4))):
            om, orr = self._store_tagged(obj_i, stores)
            outcomes_m.append(om)
            outcomes_r.append(orr)
            self.op_drop(obj_i)
        return ("value", outcomes_m), ("value", outcomes_r)

    def _store_tagged(self, obj_i: int, stores: Any) -> tuple[Outcome, Outcome]:
        """Fresh tagged values stored under names, each held by the object alone once it is stored."""
        m, r = self.objects[obj_i]

        def model() -> None:
            for n, tag in stores:
                v = RefObject(self.tracked_m, tag=tag[1])
                incref(v)
                try:
                    self.rt.setattr(m, n, v)
                finally:
                    decref(v)

        def real() -> None:
            for n, tag in stores:
                setattr(r, n, Tagged(tag[1], self.real_deaths))

        return _outcome(model), _outcome(real)

    def probe_names(self, rng: random.Random, obj_i: int) -> tuple[Any, ...]:
        """Two names and two tags for a probe: names the class's keys already hold, the later one stored first, when
        there are two (only then do the two kinds of dict release them in different orders); any two otherwise."""
        known = [k for k in self.objects[obj_i][0].cls.keys if k in NAMES]
        first, second = rng.choice(NAMES), rng.choice(NAMES)
        if len(known) >= 2 and rng.random() < 0.8:
            a, b = sorted(rng.sample(range(len(known)), 2))
            first, second = known[b], known[a]
        return (first, self.new_tag(), second, self.new_tag())

    def op_set_class_attr(self, cls_i: int, name: str, value: Any) -> tuple[Outcome, Outcome]:
        mc, rc = self.classes[cls_i]
        vm, vr = self.value(value)
        out = _outcome(lambda: mc.set_attr(name, vm)), _outcome(lambda: setattr(rc, name, vr))
        decref(vm)
        return out

    def op_del_class_attr(self, cls_i: int, name: str) -> tuple[Outcome, Outcome]:
        mc, rc = self.classes[cls_i]
        return _outcome(lambda: mc.del_attr(name)), _outcome(lambda: delattr(rc, name))

    def op_install_descriptor(self, cls_i: int, name: str, data: bool) -> tuple[Outcome, Outcome]:
        mc, rc = self.classes[cls_i]
        _, model, real = self.make_descriptor(data)
        incref(model)                                  # the caller's reference, until the operation returns
        out = _outcome(lambda: mc.set_attr(name, model)), _outcome(lambda: setattr(rc, name, real))
        decref(model)                                  # the classes hold them now
        return out

    def op_promote_descriptor(self, desc_i: int) -> tuple[Outcome, Outcome]:
        """Add __set__ to a descriptor's *class*: it becomes a data descriptor without any
        change to the classes that hold it (review round three, finding 3)."""
        pair = self.descriptors[desc_i]

        def set_m(desc: RefObject, obj: RefObject, value: Any) -> None:
            self._store_m(pair.store_m, id(obj), value)

        def set_r(self_: Any, obj: Any, value: Any) -> None:
            pair.store_r[id(obj)] = value

        def model() -> None:
            pair.model_cls.set_attr("__set__", set_m)

        def real() -> None:
            pair.real_cls.__set__ = set_r  # type: ignore[attr-defined]

        return _outcome(model), _outcome(real)

    def op_recreate_class(self, variant: int) -> tuple[Outcome, Outcome]:
        """Drop the runtime-created class and its instances, then create a new class (review log
        D-1). The old model class dies before the new one exists: no cache entry refers to it and
        its bases forget it. Its only cycle is its own MRO, which this method clears in place of
        the cycle collector (a full collection per operation makes the Hypothesis run five times
        slower), so reference counting frees it at once and the new class usually takes its
        memory and its id, as C-3-12 shows CPython does. The descriptor stores forget the dropped
        instances, whose ids the new instances may take as well."""
        assert RUNTIME_CLASS == len(self.classes) - 1 and RUNTIME_OBJECTS == (len(self.objects) - 2, len(self.objects) - 1)
        old, old_r = self.classes.pop()
        for _ in RUNTIME_OBJECTS:
            m, r = self.objects.pop()
            self._forget(m, r)
            decref(m)
            del m, r
        # the class is cyclic garbage in CPython (D-04: collected at an unspecified time): both
        # sides release its attributes now, in its dictionary's order, and drop it
        for name in [n for n in vars(old_r) if n in old.attrs]:
            delattr(old_r, name)
        old.dispose()
        old.mro = ()
        del old, old_r
        mc, rc = self._make_runtime_class(variant)
        self.classes.append((mc, rc))
        self.objects += [(RefObject(mc), rc()) for _ in RUNTIME_OBJECTS]
        for m, _ in self.objects[-len(RUNTIME_OBJECTS):]:
            incref(m)
        return ("value", mc.name), ("value", rc.__name__)

    def op_ring(self, classes: tuple[int, ...], name: str, extra: str, tags: tuple[Any, ...], weaks: tuple[Any, ...],
                reviver: str | None, hold: int | None) -> tuple[Outcome, Outcome]:
        """A cycle the program lets go of (step 3c): new objects of the given classes, each holding the next through
        `name` and its tag through `extra`; a weak reference to each where `weaks` says (True: with a callback, False:
        without), kept by the program; if `reviver` names an attribute, the first object holds there an object whose
        finaliser keeps it and which holds the second object, so that a collection finalises the group and finds it
        resurrected; if `hold` is an object of the program's, that object holds the first through `name`, so that the
        ring lives until it lets go. Each assignment's outcome, on both sides."""
        n = len(classes)
        ms: list[RefObject] = []
        rs: list[Any] = []
        for c in classes:
            mc, rc = self.classes[c]
            ms.append(RefObject(mc))
            incref(ms[-1])
            rs.append(rc())
        out_m: list[Outcome] = []
        out_r: list[Outcome] = []

        def both(fm: Any, fr: Any) -> None:
            out_m.append(_outcome(fm))
            out_r.append(_outcome(fr))

        def stored(m: RefObject, attr: str) -> bool:
            """Not through one of the world's data descriptors: their stores are keyed by id() and forget only the
            program's objects, while these die in a collection and their ids are taken again."""
            found = m.cls.lookup(attr)
            if found is not None and isinstance(found[0], RefObject) and O.is_data_descriptor(found[0]):
                out_m.append(("skipped", attr))
                out_r.append(("skipped", attr))
                return False
            return True

        for k in range(n):
            if stored(ms[k], name):
                both(functools.partial(self.rt.setattr, ms[k], name, ms[(k + 1) % n]), functools.partial(setattr, rs[k], name, rs[(k + 1) % n]))
        for k, tag in enumerate(tags):
            if not stored(ms[k], extra):
                continue
            vm, vr = self.value(tag)
            both(functools.partial(self.rt.setattr, ms[k], extra, vm), functools.partial(setattr, rs[k], extra, vr))
            decref(vm)
            del vm, vr
        for k, kind in enumerate(weaks):
            if kind is not None:
                self._ring_weak(ms[k], rs[k], kind, both)
        if reviver is not None:
            number = self.revivals
            self.revivals += 1
            log_m, log_r, kept_m, kept_r = self.heap.deaths, self.real_deaths, self.kept_m, self.kept_r

            def fin_m(obj: RefObject) -> None:
                log_m.append(("fin", number))
                incref(obj)
                kept_m.append(obj)

            class Real:
                __slots__ = ("value", "__weakref__")
                revival = number

                def __del__(self) -> None:
                    log_r.append(("fin", number))
                    kept_r.append(self)

            cm = RefClass("Reviver", slots=("value", "__weakref__"), attrs={"__del__": fin_m})
            vm = RefObject(cm)
            vm.revival = number  # type: ignore[attr-defined]
            incref(vm)
            vr = Real()
            self.rt.setattr(vm, "value", ms[1 % n])
            vr.value = rs[1 % n]  # type: ignore[attr-defined]
            self.reviver_weaks.append((weak_ref(vm), weakref.ref(vr)))
            if stored(ms[0], reviver):
                both(functools.partial(self.rt.setattr, ms[0], reviver, vm), functools.partial(setattr, rs[0], reviver, vr))
            decref(vm)
            del vm, vr
        if hold is not None:
            hm, hr = self.objects[hold]
            both(functools.partial(self.rt.setattr, hm, name, ms[0]), functools.partial(setattr, hr, name, rs[0]))
        for m in reversed(ms):                     # CPython's side lets go of its list last to first (list_dealloc)
            decref(m)
        del ms, rs
        return ("value", out_m), ("value", out_r)

    def _ring_weak(self, m: RefObject, r: Any, with_callback: bool, both: Any) -> None:
        """A weak reference to a ring's object on each side, kept by the program; its callback logs its number."""
        number = self.weak_numbers
        self.weak_numbers += 1
        log_m, log_r = self.heap.deaths, self.real_deaths

        def callback_m(w: RefWeak) -> None:
            log_m.append(("cb", number, w() is None))

        def callback_r(w: Any) -> None:
            log_r.append(("cb", number, w() is None))

        got: list[Any] = []

        def model() -> None:
            got.append(weak_ref(m, callback_m if with_callback else None))

        def real() -> None:
            got.append(weakref.ref(r, callback_r if with_callback else None))

        both(model, real)
        if len(got) == 2:
            self.weaks.append((got[0], got[1]))
        elif got and isinstance(got[0], RefWeak):
            decref(got[0])

    def op_collect(self, generation: int) -> tuple[Outcome, Outcome]:
        """gc.collect(generation) on both sides; what dies is compared as a multiset (apply). The number found is not
        compared: CPython's includes the oracle's own garbage (the classes op_revive makes)."""
        collector.collect(self.heap, generation)
        gc.collect(generation)
        return ("value", None), ("value", None)

    def op_demote_descriptor(self, desc_i: int) -> tuple[Outcome, Outcome]:
        """Remove __set__ from a descriptor's class: a data descriptor becomes non-data, so
        instance storage it used to hide becomes visible again."""
        pair = self.descriptors[desc_i]
        return (_outcome(lambda: pair.model_cls.del_attr("__set__")),
                _outcome(lambda: delattr(pair.real_cls, "__set__")))

    # ---- comparison ------------------------------------------------------------------------
    def apply(self, op: tuple[Any, ...]) -> None:
        self.log.append(op)
        kind, *args = op
        m, r = getattr(self, f"op_{kind}")(*args)
        if m != r:
            raise Mismatch(f"{op}: model {m!r} != cpython {r!r}\nlog:\n" + "\n".join(map(repr, self.log)))
        if kind == "collect":                      # a group's order is unspecified (D-04): the same deaths, any order
            self.heap.deaths.sort(key=repr)
            self.real_deaths.sort(key=repr)
        if self.heap.deaths != self.real_deaths:
            raise Mismatch(f"{op}: deaths in the model {self.heap.deaths} != in cpython {self.real_deaths}\nlog:\n"
                           + "\n".join(map(repr, self.log)))
        self.deaths_compared += len(self.real_deaths)
        self.last = (m, r)                         # for a third implementation run in lockstep
        self.last_deaths = list(self.real_deaths)
        self.heap.deaths.clear()
        self.real_deaths.clear()

    def sweep(self) -> None:
        """Compare every attribute of every object, through that name's inline cache."""
        for i, (m, r) in enumerate(self.objects):
            for name in NAMES:
                site = self.sites[name]
                om = _outcome(functools.partial(self.rt.getattr, m, name, site))
                orr = _outcome(functools.partial(getattr, r, name))
                if om != orr:
                    raise Mismatch(f"sweep obj{i}.{name}: model {om!r} != cpython {orr!r}\nlog:\n"
                                   + "\n".join(map(repr, self.log)))

    def real_sweep(self) -> list[Outcome]:
        """CPython's side of a sweep, in its order: every object, every name."""
        return [_outcome(functools.partial(getattr, r, name)) for _, r in self.objects for name in NAMES]

    # ---- random operation source --------------------------------------------------------
    def random_op(self, rng: random.Random) -> tuple[Any, ...]:
        n_obj = len(self.objects)
        if self.cycles:
            roll = rng.random()
            if roll < 0.06:
                return ("collect", rng.choice((0, 0, 1, 2)))
            if roll < 0.10:
                return ("drop", rng.randrange(n_obj))     # what a cycle holds lives on
            if roll < 0.16:
                k = rng.choice((1, 1, 2, 3, 4))
                classes = tuple(rng.choice([c for c in range(len(self.classes)) if c != RUNTIME_CLASS]) for _ in range(k))
                tags = tuple(self.new_tag() for _ in range(k))
                weaks = tuple(rng.choice((None, None, True, False)) for _ in range(k))
                reviver = rng.choice(NAMES) if rng.random() < 0.25 else None
                hold = rng.randrange(RUNTIME_OBJECTS[0]) if rng.random() < 0.3 else None
                return ("ring", classes, rng.choice(NAMES), rng.choice(NAMES), tags, weaks, reviver, hold)
        roll = rng.random()
        if roll < 0.03:
            return ("recreate_class", rng.randrange(RUNTIME_VARIANTS))
        if roll < 0.035:
            return ("drop", rng.randrange(n_obj))
        if roll < 0.05:
            return ("churn", rng.randrange(n_obj), rng.randrange(12, 36))
        if roll < 0.09:
            return ("weak_new", rng.randrange(n_obj), rng.random() < 0.6)
        if roll < 0.11:
            return ("weak_call", rng.randrange(8))
        if roll < 0.12:
            return ("weak_drop", rng.randrange(8))
        if roll < 0.135:
            return ("revive", rng.randrange(n_obj), rng.choice(NAMES), self.new_tag())
        if roll < 0.15:
            return ("release_kept",)
        if roll < 0.18:
            obj_i = rng.randrange(n_obj)
            then = rng.choice(("none", "none", "get", "get", "get", "set", "set", "del", "expose"))
            value = self.new_tag() if then == "set" and rng.random() < 0.6 else rng.randrange(100)
            probe = self.probe_names(rng, obj_i) if rng.random() < 0.7 else None
            return ("del_dict", obj_i, then, rng.choice(NAMES), value, probe)
        if roll < 0.215:
            first, second = rng.sample(NAMES, 2)
            return ("probe", rng.randrange(n_obj), rng.random() < 0.5, (first, second, self.new_tag(), self.new_tag(), self.new_tag(), self.new_tag()))
        if roll < 0.30:
            return ("get", rng.randrange(n_obj), rng.choice(NAMES), rng.random() < 0.2)
        if roll < 0.58:
            value = self.new_tag() if rng.random() < 0.4 else rng.randrange(100)
            if self.cycles and rng.random() < 0.3:
                # one of the program's objects: objects hold each other; not one of the runtime-created class's,
                # which recreate_class drops with its class (the oracle stands in for the collector there)
                return ("set", rng.randrange(n_obj), rng.choice(NAMES), ("O", rng.randrange(RUNTIME_OBJECTS[0])))
            return ("set", rng.randrange(n_obj), rng.choice(NAMES), value)
        if roll < 0.68:
            return ("del", rng.randrange(n_obj), rng.choice(NAMES))
        if roll < 0.76:
            return ("expose", rng.randrange(n_obj))
        if roll < 0.80:
            src = rng.randrange(n_obj) if rng.random() < 0.6 else None
            return ("replace_dict", rng.randrange(n_obj), src)
        if roll < 0.86:
            value = self.new_tag() if rng.random() < 0.4 else rng.randrange(100)
            return ("set_class_attr", rng.randrange(len(self.classes)), rng.choice(NAMES), value)
        if roll < 0.89:
            return ("del_class_attr", rng.randrange(len(self.classes)), rng.choice(NAMES))
        if roll < 0.94:
            return ("install_descriptor", rng.randrange(len(self.classes)), rng.choice(NAMES), rng.random() < 0.5)
        if self.descriptors and roll < 0.97:
            return ("promote_descriptor", rng.randrange(len(self.descriptors)))
        if self.descriptors:
            return ("demote_descriptor", rng.randrange(len(self.descriptors)))
        return ("get", rng.randrange(n_obj), rng.choice(NAMES), False)
