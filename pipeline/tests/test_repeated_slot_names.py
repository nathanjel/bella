"""A slot named more than once in one `__slots__` (review A25, RL-591).

CPython makes a cell for each entry of `__slots__`: a name written twice is two cells, of which the first can no longer be
reached (the second member takes its place in the class's dict). Nothing shows the lost cell but the object's size, and one
thing reads the size: the default state `object.__reduce_ex__` makes at protocol 2 and above refuses an object that is
larger than its `__slotnames__` account for. `copyreg` gives a name for each entry, so the refusal needs a class that sets
`__slotnames__` itself. The runtime counted one cell a name.

Run under pytest or directly: python3 -m pipeline.tests.test_repeated_slot_names
"""
from __future__ import annotations

from pipeline.tests.test_review_2026_11_19 import same

NAMES_SET = r'''
import copy
def outcome(f):
    try: return repr(f())
    except Exception as e: return type(e).__name__
def make(slots, names, base=object):
    class C(base):
        __slots__ = slots
    if names is not None:
        C.__slotnames__ = names
    return C
class Base1:
    __slots__ = ("p", "p")
ROWS = [
    ("twice, one name", ("x", "x"), ["x"], object),
    ("twice, two names", ("x", "x"), ["x", "x"], object),
    ("twice, no names set", ("x", "x"), None, object),
    ("twice, three names", ("x", "x"), ["x", "x", "x"], object),
    ("once, one name", ("x",), ["x"], object),
    ("once, no name", ("x",), [], object),
    ("three of two, two names", ("a", "b", "a"), ["a", "b"], object),
    ("three of two, three names", ("a", "b", "a"), ["a", "b", "a"], object),
    ("list twice, one name", ["x", "x"], ["x"], object),
    ("over a base that has one twice, one name", ("y",), ["y", "p"], Base1),
    ("over a base that has one twice, three names", ("y",), ["y", "p", "p"], Base1),
    ("the same name as the base's, one name", ("p",), ["p"], Base1),
]
for label, slots, names, base in ROWS:
    cls = make(slots, names, base)
    o = cls()
    for name in ("x", "a", "p"):
        try: setattr(o, name, 1)
        except AttributeError: pass
    print(label, "|", outcome(lambda: o.__reduce_ex__(2)[2]), "|", outcome(lambda: o.__getstate__()), "|", outcome(lambda: type(copy.copy(o)).__name__), "|", cls.__slotnames__)
'''

NAMES_LEFT_TO_COPYREG = r'''
import copy
def outcome(f):
    try: return repr(f())
    except Exception as e: return type(e).__name__
class Dup:
    __slots__ = ("x", "x")
class Once:
    __slots__ = ("x",)
class Three:
    __slots__ = ("a", "b", "a", "b", "a")
class Sub(Dup):
    __slots__ = ("y",)
class SubSame(Once):
    __slots__ = ("x",)
class WithDict(Dup):
    pass
class Listed:
    __slots__ = ["x", "y", "x"]
for cls in (Dup, Once, Three, Sub, SubSame, WithDict, Listed):
    o = cls()
    for name in ("x", "a"):
        try: setattr(o, name, 1)
        except AttributeError: pass
    print(cls.__name__, outcome(lambda: o.__reduce_ex__(2)[2]), outcome(lambda: o.__getstate__()), outcome(lambda: type(copy.copy(o)).__name__),
          getattr(cls, "__slotnames__", "unset"), cls.__slots__, sorted(n for n in vars(cls) if not n.startswith("__")))
'''


def test_a_repeated_name_is_a_cell_the_size_test_counts() -> None:
    same(NAMES_SET)


def test_copyregs_names_account_for_every_entry() -> None:
    same(NAMES_LEFT_TO_COPYREG)


if __name__ == "__main__":
    test_a_repeated_name_is_a_cell_the_size_test_counts()
    test_copyregs_names_account_for_every_entry()
    print("ok")
