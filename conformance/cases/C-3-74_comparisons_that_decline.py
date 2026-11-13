# clause: C-3-74
# spec: section 3 (the data model: rich comparisons; what a type has of its own), section 6 (builtins: bool)
# status: P1
# source: Objects/namespaceobject.c (namespace_richcompare), Objects/genericaliasobject.c (ga_richcompare), Objects/weakrefobject.c
#         (weakref_richcompare), Python/context.c (context_tp_richcompare), Objects/typevarobject.c (paramspecattr_richcompare),
#         Objects/boolobject.c (bool_invert), Objects/typeobject.c (slotdefs: one tp_richcompare is six names)
"""A type with a comparison of its own has all six names, whatever the comparison answers. These six compare for == and !=
only: asked by name for an ordering they decline (NotImplemented), and the operator then says the two cannot be ordered.
A namespace's == and != are its dict's. `~` on a bool is the int's, after a DeprecationWarning that a filter can make an
error; int's own `__invert__` given a bool does not warn."""
import contextvars
import operator
import types
import typing
import warnings
import weakref
from collections.abc import Callable

NAMES = ("__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__")
ORDERINGS = (operator.lt, operator.le, operator.gt, operator.ge)


class K:
    pass


class Space(types.SimpleNamespace):
    pass


def attempt(thunk: Callable[[], object]) -> str:
    try:
        result = thunk()
    except Exception as exc:  # noqa: BLE001  # which exception, by class
        return type(exc).__name__
    return ascii(result)


k = K()
P = typing.ParamSpec("P")
Q = typing.ParamSpec("Q")
SAMPLES: list[tuple[str, object, object, object]] = [
    ("a namespace", types.SimpleNamespace(a=1), types.SimpleNamespace(a=1), types.SimpleNamespace(a=2)),
    ("a weak reference", weakref.ref(k), weakref.ref(k), weakref.ref(K)),
    ("a context", contextvars.copy_context(), contextvars.copy_context(), contextvars.Context()),
    ("a ParamSpec's args", P.args, P.args, Q.args),  # type: ignore[attr-defined]
    ("a ParamSpec's kwargs", P.kwargs, P.kwargs, Q.kwargs),  # type: ignore[attr-defined]
    ("a generic alias", list[int], list[int], list[str]),
]
def show(label: str, one: object, same: object, other: object) -> None:
    kind = type(one)
    own = vars(kind)
    print(label + ":", [name for name in NAMES if name in own], sorted({type(own[name]).__name__ for name in NAMES if name in own}), own["__lt__"].__objclass__ is kind)
    print("    by name:", [(own[name](one, same), own[name](one, other), own[name](one, 5)) for name in NAMES])
    print("    by operator:", one == same, one != same, one == other, one != other, one == 5, one != 5, [attempt(lambda op=op: op(one, same)) for op in ORDERINGS],  # type: ignore[misc]
          attempt(lambda: one < 5), attempt(lambda: 5 >= one))  # type: ignore[operator]
    print("    refused:", attempt(lambda: own["__lt__"](one)), attempt(lambda: own["__ge__"](one, same, same)), attempt(lambda: own["__gt__"](5, one)),
          attempt(lambda: own["__le__"]()), own["__lt__"].__doc__, own["__ge__"].__doc__)


for sample in SAMPLES:
    show(*sample)
space = Space(a=1)
plain = types.SimpleNamespace(a=1)
print("a namespace's subclass:", space == plain, plain == space, space != plain, plain.__ne__(space), space.__ne__(Space(a=2)), space.__lt__(plain), "__ne__" in vars(Space),
      types.SimpleNamespace(a=[1]) != types.SimpleNamespace(a=[1]), types.SimpleNamespace(a=float("nan")) == types.SimpleNamespace(a=float("nan")),
      types.SimpleNamespace().__ne__(types.SimpleNamespace()), attempt(lambda: types.SimpleNamespace.__ne__(1, plain)))
dead = weakref.ref(K())
print("a weak reference that is dead:", dead() is None, dead == dead, dead != dead, dead == weakref.ref(k), dead.__lt__(dead), dead.__ne__(weakref.ref(K())), attempt(lambda: dead < dead))  # type: ignore[operator]
print("what a generic alias answers through its origin:", attempt(lambda: list[int].__lt__([1])), list[int].__lt__([], [1]), type(list[int]).__lt__(list[int], list[int]),  # type: ignore[call-arg, operator]
      attempt(lambda: list[int].__lt__(list[int])))  # type: ignore[call-arg, operator]

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    flags = (~True, ~False, True.__invert__(), bool.__invert__(False), operator.invert(True), operator.inv(False))
    quiet = (int.__invert__(True), ~int(True), ~1, (not True), True ^ True, ~(True + 0))
print("~ on a bool:", flags, [type(flag).__name__ for flag in flags], quiet, [w.category.__name__ for w in caught], len({str(w.message) for w in caught}),
      str(caught[0].message).startswith("Bitwise inversion '~' on bool is deprecated and will be removed in Python 3.16."), caught[0].lineno == caught[1].lineno,
      type(vars(bool)["__invert__"]).__name__, vars(bool)["__invert__"].__doc__, bool.__invert__.__objclass__ is bool)  # type: ignore[attr-defined]
with warnings.catch_warnings():
    warnings.simplefilter("error")
    print("as an error:", attempt(lambda: ~True), attempt(lambda: True.__invert__()), attempt(lambda: ~1), attempt(lambda: int.__invert__(False)))
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    print("refused:", attempt(lambda: bool.__invert__(5)), attempt(lambda: True.__invert__(1)), attempt(lambda: bool.__invert__()), len(caught))  # type: ignore[arg-type, call-arg]
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("default")
    for _ in range(3):
        repeated = ~True
    print("by default, once for a place:", repeated, len(caught))
