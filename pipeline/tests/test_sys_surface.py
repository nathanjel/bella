"""sys's named tuples and limits, compiled, against CPython: the messages case C-7-28 does not compare."""
from __future__ import annotations

from pipeline.tests.test_review_2026_11_03 import same

MESSAGES = r"""
import sys
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e)
v = sys.version_info
for fn in (lambda: type(v)(), lambda: type(v)((1,)), lambda: type(sys.flags)(), lambda: type(sys.float_info)(), lambda: type(sys.float_info)(()), lambda: type(sys.float_info)(range(11)).max, lambda: type(sys.int_info)(range(5)), lambda: type(sys.hash_info)(1), lambda: type(sys.thread_info)(range(3)), lambda: type("X", (type(v),), {}), lambda: type("X", (type(sys.float_info),), {}), lambda: setattr(v, "major", 1), lambda: delattr(v, "major"), lambda: setattr(v, "x", 1), lambda: v.x, lambda: vars(v), lambda: v.__replace__(major=1), lambda: v.__replace__(nothing=1), lambda: v.__replace__(1), lambda: v.__reduce__(1), lambda: type(v).major, lambda: repr(type(v).major)[:30], lambda: repr(type(v)), lambda: type(v).__module__, lambda: type(sys.flags).__module__, lambda: type(v).__name__, lambda: type(v).__qualname__, lambda: type(v).__repr__(1), lambda: type(v).__reduce__(), lambda: sys.flags.nothing, lambda: sys.flags.__reduce__()[1][1],
           lambda: sys.getrecursionlimit(1), lambda: sys.getrecursionlimit(x=1), lambda: sys.setrecursionlimit(), lambda: sys.setrecursionlimit("a"), lambda: sys.setrecursionlimit(1.5), lambda: sys.setrecursionlimit(0), lambda: sys.setrecursionlimit(-1), lambda: sys.setrecursionlimit(2**70), lambda: sys.setrecursionlimit(1), lambda: sys.setrecursionlimit(x=1), lambda: sys.setrecursionlimit(1, 2),
           lambda: sys.get_int_max_str_digits(1), lambda: sys.set_int_max_str_digits(), lambda: sys.set_int_max_str_digits("a"), lambda: sys.set_int_max_str_digits(1), lambda: sys.set_int_max_str_digits(639), lambda: sys.set_int_max_str_digits(-1), lambda: sys.getsizeof(), lambda: sys.getsizeof(1, 2, 3), lambda: sys.getsizeof(x=1), lambda: sys.getswitchinterval(1), lambda: sys.setswitchinterval(), lambda: sys.setswitchinterval(0), lambda: sys.setswitchinterval(-1), lambda: sys.setswitchinterval("a"), lambda: sys.is_finalizing(1), lambda: sys.getdefaultencoding(1), lambda: sys.nothing, lambda: sys.getrecursionlimit.__name__, lambda: sys.getrecursionlimit.__module__, lambda: repr(sys.getrecursionlimit), lambda: sys.getrecursionlimit.__self__ is sys):
    show(fn)
def down(n):
    return down(n + 1)
class Sized:
    def __sizeof__(self):
        return -1
class Named:
    def __sizeof__(self):
        return "a"
for fn in (lambda: down(0), lambda: sys.getsizeof(Sized()), lambda: sys.getsizeof(Named())):
    show(fn)
"""


def test_messages() -> None:
    same(MESSAGES)


if __name__ == "__main__":
    test_messages()
