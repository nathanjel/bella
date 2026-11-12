"""The runtime half of match in a compiled program (runtime/prelude/match.py, C-3-66): the words of the errors a malformed
pattern raises, with a type's tp_name in them, and the length hints the starred rest of an unpacking and the other lists
built from an iterator ask (iter_len, Objects/iterobject.c).

The words are the runtime's and CPython's, so they are compared here, on the machine that builds, compiled and under eval1.
A C type made from a spec keeps the spec's whole name (re.Pattern, itertools.count, _struct.Struct), a class statement's
is its __name__, and no attribute of the class tells which: match.py takes it from the runtime (`_bella_tp_name_of`), and
eval1 from CPython's own message (pipeline/l1/eval1.py, _tp_name)."""
from __future__ import annotations

import collections
import itertools
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.l1.eval1 import _tp_name  # noqa: E402
from pipeline.tests.test_frontend_eval1 import both  # noqa: E402
from pipeline.tests.test_review_2026_11_03 import same  # noqa: E402

WORDS = r"""
import collections, itertools, re, struct
class Local:
    class Inner:
        __match_args__ = ()
class Before:
    __match_args__ = ()
Before.__name__ = "After"
class ListArgs:
    __match_args__ = ["x"]
class IntArgs:
    __match_args__ = (1,)
class TupleSub(tuple):
    pass
class SubArgs:
    __match_args__ = TupleSub(("x",))
class Point:
    __match_args__ = ("x", "y")
    def __init__(self):
        self.x, self.y = 1, 2
class Keys:
    K = "k"
    J = "k"
    N = 1.0
    M = 1
NotAClass = 3
def words(n, subject):
    try:
        match n, subject:
            case 0, Point(1, 2, 3): pass
            case 1, Point(1, x=1): pass
            case 2, Point(1, y=2, x=3): pass
            case 3, ListArgs(1): pass
            case 4, IntArgs(1): pass
            case 5, SubArgs(1): pass
            case 6, NotAClass(): pass
            case 7, {Keys.K: 1, Keys.J: 2}: pass
            case 8, object(1): pass
            case 9, int(1, 2): pass
            case 10, Local.Inner(1): pass
            case 11, Before(1): pass
            case 12, re.Pattern(1): pass
            case 13, itertools.count(1): pass
            case 14, collections.deque(1): pass
            case 15, struct.Struct(1): pass
            case 16, collections.OrderedDict(1, 2): pass
            case 17, {Keys.N: 1, Keys.M: 2}: pass
            case 18, Point(1, 2, 3, x=1): pass
    except (TypeError, ValueError) as exc:
        return f"{type(exc).__name__}: {exc}"
    return "no error"
subjects = [Point(), Point(), Point(), ListArgs(), IntArgs(), SubArgs(), 0, {"k": 1, "j": 2}, object(), 5, Local.Inner(), Before(),
            re.compile("a"), itertools.count(), collections.deque(), struct.Struct("i"), collections.OrderedDict(), {1: 1, 2: 2}, Point()]
for n, s in enumerate(subjects):
    print(n, words(n, s))
"""

# who asks a sequence's length on the way, and when: a list built from the old protocol's iterator asks it through the
# iterator's hint (a starred target's rest after the names before it, list(), sorted(), a star display, str.join and a
# slice assignment through PySequence_Fast, bytes()), a tuple and a bytearray do not, an exhausted iterator has nothing
# to ask, a __len__ that is no int is no hint and a negative one is an error; and str.join takes every item before it
# looks at the first
HINTS = r"""
log = []
class R:
    def __init__(self, n=2):
        self.n = n
    def __len__(self):
        log.append("len")
        return self.n
    def __getitem__(self, i):
        if 0 <= i < self.n:
            return i
        raise IndexError(i)
class BadLen(R):
    def __len__(self):
        log.append("len")
        return "two"
class NegLen(R):
    def __len__(self):
        log.append("len")
        return -1
class NoLen:
    def __getitem__(self, i):
        if 0 <= i < 2:
            return i
        raise IndexError(i)
def show(label, f):
    log.clear()
    try:
        r = f()
    except Exception as e:
        r = type(e).__name__
    print(label, r, log)
def unpack():
    a, *rest = R(3)
    return a, rest
def unpack_neg():
    a, *rest = NegLen(3)
    return a, rest
def half():
    it = iter(R(3))
    next(it)
    return list(it)
def exhausted():
    it = iter(R(1))
    list(it)
    log.clear()
    return list(it)
def gen():
    for x in ("a", 1, "b"):
        log.append(f"yield {x!r}")
        yield x
def slice_set():
    l = [7, 8, 9]
    l[0:1] = iter(R())
    return l
def ext_slice_set():
    l = [7, 8, 9, 10]
    l[::2] = iter(R())
    return l
def iadd():
    l = [7]
    l += iter(R())
    return l
show("list", lambda: list(R()))
show("list iter", lambda: list(iter(R())))
show("unpack star", unpack)
show("unpack star neg", unpack_neg)
show("tuple", lambda: tuple(R()))
show("tuple iter", lambda: tuple(iter(R())))
show("star display", lambda: [*iter(R())])
show("star tuple", lambda: (*iter(R()),))
show("reversed", lambda: list(reversed(R())))
show("bad len", lambda: list(iter(BadLen())))
show("neg len", lambda: list(iter(NegLen())))
show("neg len direct", lambda: list(NegLen()))
show("no len", lambda: list(iter(NoLen())))
show("half", half)
show("exhausted", exhausted)
show("sorted", lambda: sorted(iter(R())))
show("bytes", lambda: bytes(iter(R())))
show("bytearray", lambda: bytearray(iter(R())))
show("join", lambda: ",".join(iter(R())))
show("extend", lambda: [9].extend(iter(R())))
show("join order", lambda: ",".join(gen()))
show("join one", lambda: ",".join(iter(["x"])))
show("bytes join", lambda: b",".join(iter([b"a", b"b"])))
show("slice set", slice_set)
show("extended slice set", ext_slice_set)
show("iadd", iadd)
"""


def _eval1(src: str) -> None:
    got, ref = both(src)
    assert got == ref, f"\n--- eval1\n{got}\n--- cpython\n{ref}"


def test_match_error_words_are_cpythons() -> None:
    same(WORDS)


def test_match_error_words_under_eval1() -> None:
    _eval1(WORDS)


def test_length_hints_are_cpythons() -> None:
    same(HINTS)


def test_length_hints_under_eval1() -> None:
    _eval1(HINTS)


def test_eval1_tp_name_is_cpythons() -> None:
    class Local:
        class Inner:
            pass

    renamed = type("Before", (), {})
    renamed.__name__ = "Aft): er"
    names = [_tp_name(t) for t in (re.Pattern, itertools.count, struct.Struct, collections.deque, collections.OrderedDict,
                                    Local.Inner, renamed, int, type, type(None), BaseException)]
    assert names == ["re.Pattern", "itertools.count", "_struct.Struct", "collections.deque", "collections.OrderedDict",
                     "Inner", "Aft): er", "int", "type", "NoneType", "BaseException"], names


if __name__ == "__main__":
    test_match_error_words_are_cpythons()
    test_match_error_words_under_eval1()
    test_length_hints_are_cpythons()
    test_length_hints_under_eval1()
    test_eval1_tp_name_is_cpythons()
    print("ok")
