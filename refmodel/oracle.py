"""Paired worlds: the reference model next to real CPython classes with the same definitions.

Every operation is applied to both sides and the outcomes compared. Promotion (which
attributes the compiler keeps inline) exists only on the model side; that it is invisible
from the CPython side is exactly the property under test.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from refmodel.objects import ModelError, RefClass, RefObject, Runtime, Site, make_descriptor_class

NAMES: tuple[str, ...] = ("x", "y", "z", "s", "t", "w", "cv", "g1", "attr", "k")

Outcome = tuple[str, Any]   # ("value", v) | ("error", "AttributeError") | ("dict", [(k, v), ...])


class Mismatch(AssertionError):
    pass


def _outcome(fn: Any) -> Outcome:
    try:
        return ("value", fn())
    except ModelError:
        raise
    except Exception as exc:  # noqa: BLE001 -- the exception class is the observable
        return ("error", type(exc).__name__)


@dataclass
class DescriptorPair:
    index: int
    data: bool
    model: RefObject
    model_cls: RefClass
    real: Any
    real_cls: type
    store_m: dict[int, Any] = field(default_factory=dict)
    store_r: dict[int, Any] = field(default_factory=dict)


class World:
    """A model world and a CPython world built from the same class definitions."""

    def __init__(self) -> None:
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
        self.objects: list[tuple[RefObject, Any]] = [
            (RefObject(A), RA()), (RefObject(A), RA()),
            (RefObject(B), RB()), (RefObject(B), RB()),
            (RefObject(S), RS()), (RefObject(T), RT()), (RefObject(E), RE()), (RefObject(G), RG()),
        ]
        # one inline cache per literal-name call site, plus one computed-name site
        self.sites: dict[str, Site] = {name: Site() for name in NAMES}
        self.sites["<computed>"] = Site()
        self.descriptors: list[DescriptorPair] = []
        self.log: list[tuple[Any, ...]] = []

    # ---- descriptor factory ----------------------------------------------------------------
    def make_descriptor(self, data: bool) -> DescriptorPair:
        idx = len(self.descriptors)
        store_m: dict[int, Any] = {}
        store_r: dict[int, Any] = {}

        def get_m(desc: RefObject, obj: RefObject, owner: RefClass) -> Any:
            return store_m.get(id(obj), ("DESC", idx))

        def set_m(desc: RefObject, obj: RefObject, value: Any) -> None:
            store_m[id(obj)] = value

        model_cls = make_descriptor_class(f"Desc{idx}", get_m, set_m if data else None)
        model = RefObject(model_cls)

        class DescR:
            def __get__(self, obj: Any, owner: Any = None) -> Any:
                if obj is None:
                    return ("DESC-CLASS", idx)
                return store_r.get(id(obj), ("DESC", idx))

        if data:
            def __set__(self: Any, obj: Any, value: Any) -> None:
                store_r[id(obj)] = value
            DescR.__set__ = __set__  # type: ignore[attr-defined]

        pair = DescriptorPair(idx, data, model, model_cls, DescR(), DescR, store_m, store_r)
        self.descriptors.append(pair)
        return pair

    # ---- operations ------------------------------------------------------------------------
    def op_get(self, obj_i: int, name: str, computed: bool = False) -> tuple[Outcome, Outcome]:
        m, r = self.objects[obj_i]
        site = self.sites["<computed>" if computed else name]
        return _outcome(lambda: self.rt.getattr(m, name, site)), _outcome(lambda: getattr(r, name))

    def op_set(self, obj_i: int, name: str, value: int) -> tuple[Outcome, Outcome]:
        m, r = self.objects[obj_i]
        return _outcome(lambda: self.rt.setattr(m, name, value)), _outcome(lambda: setattr(r, name, value))

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

    def op_set_class_attr(self, cls_i: int, name: str, value: int) -> tuple[Outcome, Outcome]:
        mc, rc = self.classes[cls_i]
        return _outcome(lambda: mc.set_attr(name, value)), _outcome(lambda: setattr(rc, name, value))

    def op_del_class_attr(self, cls_i: int, name: str) -> tuple[Outcome, Outcome]:
        mc, rc = self.classes[cls_i]
        return _outcome(lambda: mc.del_attr(name)), _outcome(lambda: delattr(rc, name))

    def op_install_descriptor(self, cls_i: int, name: str, data: bool) -> tuple[Outcome, Outcome]:
        mc, rc = self.classes[cls_i]
        pair = self.make_descriptor(data)
        return _outcome(lambda: mc.set_attr(name, pair.model)), _outcome(lambda: setattr(rc, name, pair.real))

    def op_promote_descriptor(self, desc_i: int) -> tuple[Outcome, Outcome]:
        """Add __set__ to a descriptor's *class*: it becomes a data descriptor without any
        change to the classes that hold it (review round three, finding 3)."""
        pair = self.descriptors[desc_i]

        def set_m(desc: RefObject, obj: RefObject, value: Any) -> None:
            pair.store_m[id(obj)] = value

        def set_r(self_: Any, obj: Any, value: Any) -> None:
            pair.store_r[id(obj)] = value

        def model() -> None:
            pair.model_cls.set_attr("__set__", set_m)

        def real() -> None:
            pair.real_cls.__set__ = set_r  # type: ignore[attr-defined]

        return _outcome(model), _outcome(real)

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

    def sweep(self) -> None:
        """Compare every attribute of every object, through that name's inline cache."""
        for i, (m, r) in enumerate(self.objects):
            for name in NAMES:
                site = self.sites[name]
                om = _outcome(lambda: self.rt.getattr(m, name, site))
                orr = _outcome(lambda: getattr(r, name))
                if om != orr:
                    raise Mismatch(f"sweep obj{i}.{name}: model {om!r} != cpython {orr!r}\nlog:\n"
                                   + "\n".join(map(repr, self.log)))

    # ---- random operation source --------------------------------------------------------
    def random_op(self, rng: random.Random) -> tuple[Any, ...]:
        n_obj = len(self.objects)
        roll = rng.random()
        if roll < 0.30:
            return ("get", rng.randrange(n_obj), rng.choice(NAMES), rng.random() < 0.2)
        if roll < 0.58:
            return ("set", rng.randrange(n_obj), rng.choice(NAMES), rng.randrange(100))
        if roll < 0.68:
            return ("del", rng.randrange(n_obj), rng.choice(NAMES))
        if roll < 0.76:
            return ("expose", rng.randrange(n_obj))
        if roll < 0.80:
            src = rng.randrange(n_obj) if rng.random() < 0.6 else None
            return ("replace_dict", rng.randrange(n_obj), src)
        if roll < 0.86:
            return ("set_class_attr", rng.randrange(len(self.classes)), rng.choice(NAMES), rng.randrange(100))
        if roll < 0.89:
            return ("del_class_attr", rng.randrange(len(self.classes)), rng.choice(NAMES))
        if roll < 0.94:
            return ("install_descriptor", rng.randrange(len(self.classes)), rng.choice(NAMES), rng.random() < 0.5)
        if self.descriptors and roll < 0.97:
            return ("promote_descriptor", rng.randrange(len(self.descriptors)))
        if self.descriptors:
            return ("demote_descriptor", rng.randrange(len(self.descriptors)))
        return ("get", rng.randrange(n_obj), rng.choice(NAMES), False)
