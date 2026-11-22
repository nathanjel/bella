"""itertools.tee's data links go as CPython's do, and have no finaliser a program can see.

`itertools._tee_dataobject.__del__` was the last name of `conformance/names-surplus.txt` (RL-731): CPython's type has a
deallocator, `teedataobject_clear`, which lets go of the iterator, then of the values from the first, then of the next link,
walking a long chain in a loop (`teedataobject_safe_decref`). The prelude had a `__del__` to do the same. It needs none: the
order is the order of the object's fields once the values are kept by index in a dict, which lets go of its values from the
first (a list starts at its end), and the runtime lets go of a chain of any length without the native stack (RL-624).

The program: one link, three links with the iterator held by the last, a reader ahead of the other, a copy, a chain of
three million items, and `hasattr`.

Run under pytest or directly: python3 -m pipeline.tests.test_tee_dealloc
"""
from __future__ import annotations

from pathlib import Path

from pipeline.tests.test_review_2026_11_19 import same

PROGRAM = r'''
import copy
import itertools


class V:
    def __init__(self, n: int) -> None:
        self.n = n

    def __del__(self) -> None:
        print("drop", self.n)


class It:
    def __init__(self, n: int) -> None:
        self.i, self.n = 0, n

    def __iter__(self) -> "It":
        return self

    def __next__(self) -> V:
        self.i += 1
        if self.i > self.n:
            raise StopIteration
        return V(self.i)

    def __del__(self) -> None:
        print("drop iterator")


print("1. one link: the iterator, then its values in order")
a, b = itertools.tee(It(5))
for _ in range(3):
    next(a)
del a
print("the second goes")
del b
print("2. three links, the iterator held by the last")
a, b = itertools.tee(It(200))
for _ in range(120):
    next(a)
del a
print("the second goes")
del b
print("3. the reader ahead goes last: nothing is held behind it")
a, b = itertools.tee(It(130))
for _ in range(60):
    next(a)
    next(b)
print("both read 60")
del b
for _ in range(60):
    next(a)
print("the first read 120")
del a
print("4. a copy shares the links")
a, b = itertools.tee(It(4))
next(a)
c = copy.copy(b)
del a, b
print("the copy is left")
print(next(c).n)
del c
print("5. a long chain goes without the native stack")
a, b = itertools.tee(iter(range(3_000_000)))
total = 0
for value in a:
    total += value
del a
print(total)
del b
print("6. no finaliser a program can see")
print(hasattr(itertools._tee_dataobject, "__del__"), hasattr(itertools._tee, "__del__"))
print("end")
'''


def test_a_tees_links_go_in_cpythons_order() -> None:
    same(PROGRAM)


def test_no_name_beyond_cpythons_is_listed() -> None:
    surplus = Path(__file__).resolve().parent.parent.parent / "conformance" / "names-surplus.txt"
    assert surplus.read_text(encoding="utf-8").split() == []


if __name__ == "__main__":
    test_no_name_beyond_cpythons_is_listed()
    test_a_tees_links_go_in_cpythons_order()
    print("ok")
