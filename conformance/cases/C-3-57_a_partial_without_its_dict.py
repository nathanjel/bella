# clause: C-3-57
# spec: section 3
# status: P1
# source: Modules/_functoolsmodule.c (partial_setstate, partial_reduce, partial_new), Objects/object.c (PyObject_GenericGetDict, PyObject_GenericSetDict)
"""A partial without its dict: one given no dict by __setstate__ has none, as when it was made (__reduce__ says None,
and another partial unwraps it), until an attribute is set or its __dict__ is asked for; the dict it had goes as it
was, and whoever holds it keeps it. The __dict__ of a C type that has its own is never deleted by a program."""
# ruff: noqa: E501
import functools
from collections.abc import Callable


class V:
    def __init__(self, n: str) -> None:
        self.n = n

    def __del__(self) -> None:
        print("gone", self.n)


class S:
    __slots__ = ("a",)


class Sub(functools.partial[int]):
    pass


def failed(f: Callable[[], object]) -> str:
    try:
        f()
    except Exception as e:
        return type(e).__name__
    return "no error"


def add(a: int, b: int) -> int:
    return a + b


P = functools.partial
r = P(add, 1)
print(r.__reduce__()[2][3], P(r).func is add)
r.n = 1  # type: ignore[attr-defined]
print(r.__reduce__()[2][3], P(r).func is r)
r.__setstate__((add, (1,), None, None))  # type: ignore[attr-defined]
print(r.__reduce__()[2][3], P(r).func is add, failed(lambda: r.n), r(2))  # type: ignore[attr-defined]
print(vars(r), r.__reduce__()[2][3], P(r).func is r)
r.__setstate__((add, (1,), None, None))  # type: ignore[attr-defined]
print(failed(lambda: delattr(r, "__dict__")), r.__reduce__()[2][3], P(r).func is add)
r.__setstate__((add, (1,), None, None))  # type: ignore[attr-defined]
print(r.__reduce__()[2][3], P(r).func is add)
print("-- the dict it had")
r.__setstate__((add, (1,), {"k": V("k")}, {"m": V("m"), "l": V("l")}))  # type: ignore[attr-defined]
state = vars(r)
print(list(state), r.m.n, r.keywords["k"].n)  # type: ignore[attr-defined]
r.__setstate__((add, (2,), None, None))  # type: ignore[attr-defined]
print("set", list(state), state["l"].n, r.__reduce__()[2][3], failed(lambda: r.m), r(2), r.keywords)  # type: ignore[attr-defined]
del state
print("-- nobody held this one")
r.m = V("m2")  # type: ignore[attr-defined]
r.l = V("l2")  # type: ignore[attr-defined]
r.__setstate__((add, (2,), None, None))  # type: ignore[attr-defined]
print("-- a subclass")
s = Sub(add, 1)
s.n = V("s n")  # type: ignore[attr-defined]
print(failed(lambda: delattr(s, "__dict__")), list(vars(s)), P(s).func is s)
s.__setstate__((add, (1,), None, None))  # type: ignore[attr-defined]
print(s.__reduce__()[2][3], P(s).func is add, Sub(s).func is add, type(Sub(s)).__name__)
print("-- what has no dict, and what never loses it")
print(failed(lambda: delattr(S(), "__dict__")), failed(lambda: delattr(add, "__dict__")), failed(lambda: delattr(ValueError(), "__dict__")), failed(lambda: delattr(S, "__dict__")), failed(lambda: delattr(P(add), "__dict__")))
print("end")
