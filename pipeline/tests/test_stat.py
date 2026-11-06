"""_stat, compiled, against CPython: the messages, which case C-7-24 does not compare."""
from __future__ import annotations

from pipeline.tests.test_review_2026_11_03 import same

PROGRAM = r"""
import stat
import _stat
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e)
class Idx:
    def __index__(self):
        return 0o040755
class Bad:
    def __index__(self):
        raise ValueError("inside index")
class Big:
    def __index__(self):
        return 2**64
for name in ("S_IMODE", "S_IFMT", "S_ISDIR", "S_ISCHR", "S_ISBLK", "S_ISREG", "S_ISFIFO", "S_ISLNK", "S_ISSOCK", "S_ISDOOR", "S_ISPORT", "S_ISWHT", "filemode"):
    f = getattr(_stat, name)
    for g in (lambda: f(), lambda: f(1, 2), lambda: f(x=1), lambda: f(1, x=1), lambda: f("a"), lambda: f(1.5), lambda: f(None), lambda: f(-1), lambda: f(-(2**70)), lambda: f(2**32), lambda: f(2**64 - 1), lambda: f(2**64), lambda: f(2**70), lambda: f(True), lambda: f(0o040755), lambda: f(Idx()), lambda: f(Bad()), lambda: f(Big())):
        show(g)
    print(f.__name__, f.__qualname__, f.__module__, type(f).__name__)
print(_stat.__name__, stat.__name__, sorted([k for k in vars(_stat) if k.startswith("__")]))
for mode in range(0, 0o200000, 0o1111):
    print(stat.filemode(mode), end=" ")
print()
"""


def test_as_cpython() -> None:
    same(PROGRAM)


if __name__ == "__main__":
    test_as_cpython()
