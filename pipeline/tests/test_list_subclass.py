"""Subclasses of list, compiled, against CPython: the messages, which case C-3-51 does not compare, a finaliser's order, a
weak reference's callback, and what the standard library asks of one (traceback.StackSummary is one; json, heapq and
random.shuffle take one)."""
from __future__ import annotations

from pipeline.tests.test_review_2026_11_03 import same

MESSAGES = r"""
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e)
class L(list):
    pass
class New(list):
    def __new__(cls, *args, **kwds):
        return super().__new__(cls)
class BadLen(list):
    def __len__(self):
        return "a"
class BadBool(list):
    def __bool__(self):
        return 1
class NoneIter(list):
    __iter__ = None
class Slots(list):
    __slots__ = ("x",)
for f in (lambda: L(1), lambda: L(None), lambda: L(1, 2), lambda: L(x=1), lambda: L([1], x=1), lambda: New([1], x=1),
          lambda: New(1, 2), lambda: list.__new__(int), lambda: list.__new__(), lambda: list.__init__(1),
          lambda: list.__init__(L(), 1, 2), lambda: list.__init__(L(), x=1), lambda: L()[0], lambda: L([1])["a"],
          lambda: L().pop(), lambda: L().remove(1), lambda: L().index(1), lambda: hash(L()), lambda: L() + (1,),
          lambda: L() < 1, lambda: len(BadLen()), lambda: bool(BadBool()), lambda: list(NoneIter()),
          lambda: setattr(Slots(), "y", 1), lambda: L.__getitem__(1, 0), lambda: list.__delitem__(L([1]), 5),
          lambda: L([1]).__setitem__(5, 0), lambda: type("X", (list, dict), {}), lambda: type("X", (list, tuple), {})):
    show(f)
"""

DEATHS = r"""
import weakref
class L(list):
    def __del__(self):
        print("del", len(self), [x.n for x in self])
class Item:
    def __init__(self, n):
        self.n = n
    def __del__(self):
        print("item", self.n)
a = L([Item(1), Item(2)])
a.attr = Item(3)
del a
b = L([Item(4)])
r = weakref.ref(b, lambda ref: print("callback"))
del b
print("after", r())
c = L([Item(5)])
c.clear()
d = L([Item(6), Item(7)])
d.__init__([Item(8)])
print("end")
"""

LIBRARY = r"""
import heapq, json, random, traceback
class M(list):
    pass
print(json.dumps(M([1, M([2])])), json.dumps({"k": M([1])}))
h = M([5, 1, 3])
heapq.heapify(h)
print(heapq.heappop(h), h, type(h).__name__)
random.seed(1)
s = M(range(5))
random.shuffle(s)
print(s)
st = traceback.StackSummary.from_list([("f.py", 1, "fn", "x = 1")])
print(type(st).__name__, len(st), st.format())
print("".join(traceback.format_exception(ExceptionGroup("g", [ValueError(1)]))), end="")
"""


# list.__iadd__ and list.__imul__ as attributes (sq_inplace_concat and sq_inplace_repeat's wrappers): what they are, what they take,
# and a subclass's own that asks the base for it
IN_PLACE = r"""
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e)
class L(list):
    pass
class Counted(list):
    calls = 0
    def __iadd__(self, other):
        Counted.calls += 1
        return super().__iadd__(other)
    def __imul__(self, n):
        Counted.calls += 1
        return super().__imul__(n)
class Other(list):
    def __iadd__(self, other):
        return "mine"
class Index:
    def __index__(self):
        return 2
print(type(list.__iadd__).__name__, type([].__iadd__).__name__, list.__iadd__.__name__, list.__iadd__.__qualname__, list.__imul__.__qualname__,
      list.__iadd__.__objclass__ is list, "__iadd__" in list.__dict__, "__imul__" in vars(list),
      "__iadd__" in vars(L), L.__iadd__ is list.__iadd__, [].__iadd__.__self__, repr(list.__iadd__), repr(list.__imul__))   # not __doc__, __text_signature__: a slot wrapper's stop by name (TODO)
x = [1]
for f in (lambda: list.__iadd__(x, [2]), lambda: list.__iadd__(x, (3,)), lambda: list.__iadd__(x, "ab"), lambda: list.__iadd__(x, {5: 6}),
          lambda: list.__iadd__(x, iter([7])) is x, lambda: x.__iadd__(x), lambda: list.__iadd__(x, 5), lambda: list.__iadd__(x, None), lambda: list.__iadd__(x),
          lambda: list.__iadd__(x, [], []), lambda: list.__iadd__(), lambda: list.__iadd__(5, []), lambda: list.__iadd__((1,), []), lambda: list.__iadd__(x, other=[]),
          lambda: x.__iadd__(), lambda: x.__iadd__(1, 2), lambda: x.__iadd__(other=[])):
    show(f)
y = [1, 2]
for f in (lambda: list.__imul__(y, 2), lambda: list.__imul__(y, True), lambda: list.__imul__(y, Index()) is y, lambda: len(y), lambda: list.__imul__(y, 0),
          lambda: list.__imul__(y, -3), lambda: list.__imul__([1], "a"), lambda: list.__imul__([1], 2.0), lambda: list.__imul__([1], None),
          lambda: list.__imul__([1], 2 ** 70), lambda: list.__imul__([], 2 ** 70), lambda: list.__imul__([1]), lambda: list.__imul__([1], 1, 2), lambda: list.__imul__(),
          lambda: list.__imul__("a", 2), lambda: [1].__imul__(), lambda: [1].__imul__(n=2), lambda: [1].__imul__(3), lambda: [1].__imul__(-1)):
    show(f)
c = Counted([1])
kept = c
c += [2]
c *= 2
c.__iadd__([3])
show(lambda: (c, type(c).__name__, c is kept, Counted.calls, list.__iadd__(c, [4]) is c, list.__imul__(c, 1) is c, Counted.calls, c))
o = Other([1])
show(lambda: (list.__iadd__(o, [2]), o, o.__iadd__([3]), o))
o += [9]
show(lambda: o)
l = L([1])
show(lambda: (l.__iadd__([2]) is l, l.__imul__(2) is l, l, type(l).__name__, L.__imul__(l, 0), list.__iadd__(l, L([5])), list.__imul__(L([1, 2]), 2)))
import operator
z = [1]
show(lambda: (operator.iadd(z, [2]) is z, operator.imul(z, 2) is z, z, operator.__iadd__(z, (0,)), operator.iconcat(z, [8]), operator.iconcat(c, [1]) is c, Counted.calls))
show(lambda: sorted(n for n in vars(list) if n.startswith("__i")))
"""


def test_messages() -> None:
    same(MESSAGES)


def test_the_in_place_operators_as_attributes() -> None:
    same(IN_PLACE)


def test_deaths() -> None:
    same(DEATHS)


def test_the_standard_library_takes_one() -> None:
    same(LIBRARY)


if __name__ == "__main__":
    test_messages()
    test_the_in_place_operators_as_attributes()
    test_deaths()
    test_the_standard_library_takes_one()
