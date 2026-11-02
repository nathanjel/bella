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
"""
from __future__ import annotations

import functools
import random
from dataclasses import dataclass, field
from typing import Any

from refmodel import objects as O
from refmodel.objects import ModelError, RefClass, RefObject, Runtime, Site, decref, incref, make_descriptor_class

NAMES: tuple[str, ...] = ("x", "y", "z", "s", "t", "w", "cv", "g1", "attr", "k")
RUNTIME_CLASS = 6                     # index in World.classes of the class recreate_class replaces
RUNTIME_OBJECTS = (8, 9)              # indices in World.objects of its instances
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


def _norm(v: Any) -> Any:
    """Tagged values compare by tag on both sides."""
    if isinstance(v, (RefObject, Tagged)) and getattr(v, "tag", None) is not None:
        return ("T", v.tag)
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

    def __init__(self) -> None:
        O.HEAP = self.heap = O.Heap()
        self.real_deaths: list[Any] = []
        self.deaths_compared = 0
        self.tags = 0
        self.tracked_m = RefClass("Tracked")
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

        self.classes: list[tuple[RefClass, type]] = [(A, RA), (B, RB), (S, RS), (T, RT), (E, RE), (G, RG)]
        self.classes.append(self._make_runtime_class(0))
        R, RR = self.classes[RUNTIME_CLASS]
        self.objects: list[tuple[RefObject, Any]] = [
            (RefObject(A), RA()), (RefObject(A), RA()),
            (RefObject(B), RB()), (RefObject(B), RB()),
            (RefObject(S), RS()), (RefObject(T), RT()), (RefObject(E), RE()), (RefObject(G), RG()),
            (RefObject(R), RR()), (RefObject(R), RR()),
        ]
        for m, _ in self.objects:
            incref(m)                                  # the program's variables hold them
        # one inline cache per literal-name call site, plus one computed-name site
        self.sites: dict[str, Site] = {name: Site() for name in NAMES}
        self.sites["<computed>"] = Site()
        self.descriptors: list[DescriptorPair] = []
        self.log: list[tuple[Any, ...]] = []

    # ---- runtime-created classes (review log D-1) ------------------------------------------
    def _make_runtime_class(self, variant: int) -> tuple[RefClass, type]:
        """A new model class and a new CPython class on every call, in one of five shapes."""
        A, RA = self.classes[0]
        if variant == 0:
            class R0:
                __slots__ = ("k", "x")
            return RefClass("R0", slots=("k", "x")), R0
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
        if self.heap.deaths != self.real_deaths:
            raise Mismatch(f"{op}: deaths in the model {self.heap.deaths} != in cpython {self.real_deaths}\nlog:\n"
                           + "\n".join(map(repr, self.log)))
        self.deaths_compared += len(self.real_deaths)
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

    # ---- random operation source --------------------------------------------------------
    def random_op(self, rng: random.Random) -> tuple[Any, ...]:
        n_obj = len(self.objects)
        roll = rng.random()
        if roll < 0.03:
            return ("recreate_class", rng.randrange(RUNTIME_VARIANTS))
        if roll < 0.05:
            return ("drop", rng.randrange(n_obj))
        if roll < 0.30:
            return ("get", rng.randrange(n_obj), rng.choice(NAMES), rng.random() < 0.2)
        if roll < 0.58:
            value = self.new_tag() if rng.random() < 0.4 else rng.randrange(100)
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
