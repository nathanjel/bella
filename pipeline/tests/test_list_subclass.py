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


def test_messages() -> None:
    same(MESSAGES)


def test_deaths() -> None:
    same(DEATHS)


def test_the_standard_library_takes_one() -> None:
    same(LIBRARY)


if __name__ == "__main__":
    test_messages()
    test_deaths()
    test_the_standard_library_takes_one()
