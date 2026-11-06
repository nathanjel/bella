"""Subclasses of tuple, compiled, against CPython: the messages, which case C-3-40 does not compare, a finaliser's order
and what the standard library's namedtuple text needs of one."""
from __future__ import annotations

from pipeline.tests.test_review_2026_11_03 import same

MESSAGES = r"""
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e)
class T(tuple):
    pass
class Slotless(tuple):
    __slots__ = ()
class New(tuple):
    def __new__(cls, a, b):
        return tuple.__new__(cls, (a, b))
class BadLen(tuple):
    def __len__(self):
        return "a"
class NegLen(tuple):
    def __len__(self):
        return -1
class BadBool(tuple):
    def __bool__(self):
        return 1
class NoneBool(tuple):
    __bool__ = None
class NoHash(tuple):
    __hash__ = None
class BadHash(tuple):
    def __hash__(self):
        return "a"
class EqOnly(tuple):
    def __eq__(self, other):
        return True
class BadIter(tuple):
    def __iter__(self):
        return 1
class NoIter(tuple):
    __iter__ = None
class NoContains(tuple):
    __contains__ = None
class BadRepr(tuple):
    def __repr__(self):
        return 1
class Weak(tuple):
    __slots__ = ("__weakref__", "x")
t = T((1, 2, 3))
for fn in (lambda: t[5], lambda: t[-9], lambda: t["a"], lambda: t[1.5], lambda: t.nothing, lambda: T(1), lambda: T(None), lambda: T(1, 2), lambda: T(x=1), lambda: T([1], x=1), lambda: tuple.__new__(), lambda: tuple.__new__(1), lambda: tuple.__new__(int), lambda: tuple.__new__(object), lambda: tuple.__new__(T, 1), lambda: tuple.__new__(T, 1, 2), lambda: tuple.__new__(T, x=1), lambda: tuple.__new__(tuple, 1, 2), lambda: tuple.__new__(tuple, x=1), lambda: New(1), lambda: New((1, 2)), lambda: Slotless(1),
           lambda: t + [1], lambda: [1] + t, lambda: t + 1, lambda: 1 + t, lambda: t * "a", lambda: t * 1.5, lambda: t - t, lambda: t / 2, lambda: -t, lambda: ~t, lambda: t % 2, lambda: t ** 2, lambda: t < 1, lambda: 1 < t, lambda: t * 2**70, lambda: t & t,
           lambda: tuple.__add__(t, [1]), lambda: tuple.__add__(1, t), lambda: tuple.__len__(1), lambda: tuple.__len__(), lambda: tuple.__len__(t, 1), lambda: tuple.__getitem__([1], 0), lambda: tuple.__getitem__(t), lambda: tuple.__iter__(1), lambda: tuple.__repr__(1), lambda: tuple.__hash__(1), lambda: tuple.__hash__(t, 1), lambda: tuple.count(1, 1), lambda: tuple.count(t), lambda: tuple.index(t, 9), lambda: tuple.index(t), lambda: tuple.__contains__(1, 1), lambda: tuple.__eq__(1, t), lambda: tuple.__getnewargs__(1), lambda: tuple.__getnewargs__(t, 1), lambda: t.__getnewargs__(1), lambda: tuple.__mul__(t, "a"), lambda: tuple.__rmul__(t, "a"),
           lambda: setattr((), "x", 1), lambda: delattr(t, "y"), lambda: t.y, lambda: setattr(Slotless(), "x", 1), lambda: vars(Slotless()), lambda: Slotless().__dict__, lambda: setattr(t, "__dict__", 1), lambda: delattr(Slotless(), "x"),
           lambda: type("X", (tuple, list), {}), lambda: type("X", (list, tuple), {}), lambda: type("X", (tuple, int), {}), lambda: type("X", (tuple, dict), {}), lambda: type("X", (tuple, str), {}), lambda: type("X", (T, tuple), {}), lambda: type("X", (tuple, T), {}), lambda: type("B", (tuple,), {"__slots__": ("x",)})((1,)).x, lambda: type("B", (T,), {"__slots__": ("__weakref__",)}),
           lambda: len(BadLen()), lambda: len(NegLen()), lambda: bool(BadLen()), lambda: bool(NegLen()), lambda: bool(BadBool()), lambda: bool(NoneBool()), lambda: not BadBool(), lambda: hash(NoHash()), lambda: {NoHash()}, lambda: hash(BadHash()), lambda: hash(EqOnly()), lambda: iter(BadIter()), lambda: list(BadIter()), lambda: [*BadIter()], lambda: iter(NoIter()), lambda: list(NoIter()), lambda: [*NoIter()], lambda: print(*NoIter()), lambda: 1 in NoContains(), lambda: repr(BadRepr()), lambda: str(BadRepr()), lambda: f"{BadRepr()}", lambda: tuple.__repr__(BadRepr((1,))),
           lambda: Weak((1,)).x, lambda: setattr(Weak((1,)), "y", 1), lambda: Weak.__dict__["x"], lambda: type(Weak.__dict__["x"]).__name__, lambda: hasattr(Weak((1,)), "__dict__"), lambda: Weak((1,)).__weakref__,
           lambda: repr(t), lambda: str(t), lambda: repr(T()), lambda: repr(T((1,))), lambda: repr(T(("a", 1.5, None))), lambda: repr((t, t)), lambda: repr([t]), lambda: t.__repr__(), lambda: t.__str__(), lambda: t.__len__(), lambda: t.__iter__().__class__.__name__, lambda: t.__contains__(1), lambda: t.__getitem__(0), lambda: t.__hash__() == hash((1, 2, 3)), lambda: t.__eq__((1, 2, 3)), lambda: t.__lt__((9,)), lambda: t.__add__((4,)), lambda: t.__mul__(2), lambda: t.__rmul__(2), lambda: t.__getnewargs__(), lambda: t.__class__, lambda: T.__name__, lambda: T.__qualname__, lambda: T.__module__, lambda: T.__base__, lambda: T.__bases__, lambda: T.__mro__, lambda: repr(T), lambda: sorted([k for k in dir(T) if not k.startswith("_")]), lambda: sorted(dir(t)) == sorted(dir(T)), lambda: T.count, lambda: T.index is tuple.index, lambda: T.__add__ is tuple.__add__, lambda: T.__new__ is tuple.__new__):
    show(fn)
"""

DEATHS = r"""
class Dies(tuple):
    def __del__(self):
        print("del", tuple.__repr__(self), getattr(self, "name", None))
class Item:
    def __init__(self, n):
        self.n = n
    def __del__(self):
        print("item", self.n)
    def __repr__(self):
        return "Item(" + str(self.n) + ")"
d = Dies((Item(1), Item(2)))
d.name = "first"
del d
print("gone")
class Attr(tuple):
    pass
a = Attr((Item(3), Item(4)))
a.x = Item(5)
a.y = Item(6)
del a
print("gone")
class Slots(tuple):
    __slots__ = ("p", "q")
s = Slots((Item(7),))
s.q = Item(8)
s.p = Item(9)
del s
print("gone")
saved = []
class Back(tuple):
    def __del__(self):
        saved.append(self)
b = Back((Item(10),))
del b
print("saved", saved)
saved.clear()
print("end")
"""


BAD_RESULTS = r"""
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e)
class C:
    def __repr__(self):
        return 1
class S:
    def __str__(self):
        return 1
class B:
    def __bool__(self):
        return 1
class I(int):
    def __repr__(self):
        return 1
class IB(int):
    def __bool__(self):
        return 1
class F(float):
    def __repr__(self):
        return 1
class D(dict):
    def __repr__(self):
        return 1
class T(tuple):
    def __repr__(self):
        return 1
class TB(tuple):
    def __bool__(self):
        return 1
class TS(tuple):
    def __str__(self):
        return 1
class M(type):
    def __repr__(cls):
        return 1
class WithM(metaclass=M):
    pass
class Good:
    def __repr__(self):
        return "good"
for fn in (lambda: repr(T()), lambda: str(T()), lambda: f"{T()}", lambda: bool(TB()), lambda: not TB(), lambda: repr(TS()), lambda: str(TS()), lambda: f"{TS()}", lambda: repr(WithM), lambda: str(WithM), lambda: object.__str__(C()), lambda: object.__str__(Good()), lambda: str(Good()), lambda: object.__repr__(1).startswith("<int object"), lambda: repr(C()), lambda: str(C()), lambda: f"{C()}", lambda: "%s" % C(), lambda: "%r" % C(), lambda: str(S()), lambda: f"{S()}", lambda: bool(B()), lambda: not B(), lambda: repr(I()), lambda: str(I()), lambda: bool(IB()), lambda: not IB(), lambda: repr(F()), lambda: str(F()), lambda: repr(D()), lambda: str(D()), lambda: f"{D()}", lambda: [C()], lambda: repr([C()]), lambda: repr((C(),)), lambda: repr({1: C()}), lambda: ascii(C())):
    show(fn)
"""


def test_messages() -> None:
    same(MESSAGES)


def test_deaths() -> None:
    same(DEATHS)


def test_a_method_that_returns_the_wrong_type_is_named() -> None:
    same(BAD_RESULTS)


if __name__ == "__main__":
    test_messages()
    test_deaths()
    test_a_method_that_returns_the_wrong_type_is_named()
