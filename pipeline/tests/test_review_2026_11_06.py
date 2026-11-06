"""Reviews G12 and A12 (RL-334 to RL-346): each program as the reviewer gave it and what stands around it, compiled, against CPython."""
from __future__ import annotations

from pipeline.tests.test_review_2026_11_03 import same

MORE_DEFAULTS_THAN_PARAMETERS = r"""
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e)
def one(x):
    return x
def two(x, y):
    return (x, y)
def none():
    return 0
def kw(x, *, k=1):
    return (x, k)
one.__defaults__ = (10, 20)
two.__defaults__ = (1, 2, 3)
none.__defaults__ = (1,)
kw.__defaults__ = (5, 6)
for fn in (lambda: one(), lambda: one(1), lambda: one(1, 2), lambda: one(1, 2, 3), lambda: one(x=3), lambda: two(), lambda: two(7), lambda: two(7, 8), lambda: two(7, 8, 9), lambda: two(y=1), lambda: none(), lambda: none(1), lambda: kw(), lambda: kw(1, 2), lambda: kw(k=2)):
    show(fn)
one.__defaults__ = ()
two.__defaults__ = (9,)
for fn in (lambda: one(), lambda: one(1, 2), lambda: two(), lambda: two(1), lambda: two(1, 2, 3)):
    show(fn)
"""

GETSIZEOF_DEFAULT = r"""
import sys
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e)
class NoneSize:
    __sizeof__ = None
class Raises:
    def __sizeof__(self):
        raise TypeError("t")
class RaisesOther:
    def __sizeof__(self):
        raise KeyError("k")
class Text:
    def __sizeof__(self):
        return "a"
class Negative:
    def __sizeof__(self):
        return -1
class Huge:
    def __sizeof__(self):
        return 2 ** 70
class HugeNegative:
    def __sizeof__(self):
        return -(2 ** 70)
for fn in (lambda: sys.getsizeof(NoneSize(), 42), lambda: sys.getsizeof(NoneSize()), lambda: sys.getsizeof(Raises(), 42), lambda: sys.getsizeof(Raises()), lambda: sys.getsizeof(RaisesOther(), 42), lambda: sys.getsizeof(Text(), 42), lambda: sys.getsizeof(Text()), lambda: sys.getsizeof(Negative(), 42), lambda: sys.getsizeof(Negative()), lambda: sys.getsizeof(NoneSize(), default=7), lambda: sys.getsizeof(object=NoneSize(), default=None), lambda: sys.getsizeof(Huge()), lambda: sys.getsizeof(Huge(), 42), lambda: sys.getsizeof(HugeNegative(), 42)):
    show(fn)
"""

CALLABLE_ITERATOR = r"""
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e.args, getattr(e, "value", "-"), e.__context__)
def carries():
    raise StopIteration(42)
it = iter(carries, 0)
show(lambda: next(it))
show(lambda: next(it))
print(list(iter(carries, 0)), next(iter(carries, 0), "default"))
nan = float("nan")
calls = []
def f():
    calls.append(1)
    if len(calls) > 3:
        raise KeyError("looped")
    return nan
print(list(iter(f, nan)), len(calls))
class Never:
    def __eq__(self, other):
        return False
o = Never()
n = []
def g():
    n.append(1)
    if len(n) > 3:
        raise KeyError("looped")
    return o
print(list(iter(g, o)), len(n))
other = []
def h():
    other.append(1)
    if len(other) > 2:
        return "end"
    return Never()
print(len(list(iter(h, "end"))))
class Falsy:
    def __bool__(self):
        return False
class Truthy:
    def __bool__(self):
        return True
class EqFalsy:
    def __eq__(self, other):
        return Falsy()
class EqTruthy:
    def __eq__(self, other):
        return Truthy()
class EqRaises:
    def __eq__(self, other):
        raise ValueError("eq")
print(next(iter(lambda: 1, EqFalsy())), next(iter(lambda: 1, EqTruthy()), "stopped"))
bad = iter(lambda: 1, EqRaises())
show(lambda: next(bad))
show(lambda: next(bad))
"""

SYS_EXIT_TUPLE = r"""
import sys
class T(tuple):
    pass
for value in (T(), T((1,)), T((1, 2)), (), (1,), (1, 2), None, 3, "s"):
    try:
        sys.exit(value)
    except SystemExit as e:
        print(repr(value), type(e.code).__name__, repr(e.code), type(e.args).__name__, repr(e.args), e.code is value, e.args is value)
try:
    sys.exit()
except SystemExit as e:
    print(repr(e.code), repr(e.args))
"""


BUFFER_EXPORTS = r"""
import re
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e)
b = bytearray(b"abc")
held = re.compile(b"[a-z]").scanner(b)
for fn in (lambda: b.append(1), lambda: b.extend(b"x"), lambda: b.extend([1]), lambda: b.extend(b""), lambda: b.extend([]), lambda: b.insert(0, 1), lambda: b.pop(), lambda: b.remove(97), lambda: b.remove(0), lambda: b.clear(), lambda: b.resize(1), lambda: b.resize(3), lambda: b.take_bytes(1), lambda: b.take_bytes(0), lambda: b.__iadd__(b"x"), lambda: b.__iadd__(b""), lambda: b.__imul__(2), lambda: b.__imul__(1), lambda: b.__delitem__(0), lambda: b.__delitem__(slice(0, 1)), lambda: b.__delitem__(slice(0, 0)), lambda: b.__setitem__(slice(0, 1), b"xy"), lambda: b.__setitem__(slice(0, 1), b"z"), lambda: b.__setitem__(0, 122), lambda: b.__init__(b"new"), lambda: b.reverse(), lambda: bytes(b)):
    show(fn)
print(b, held.search().span(), held.search().span(), held.search().span(), held.search())
del held
b.append(100)
print(b)
it = re.finditer(b"[a-z]", b)
show(lambda: b.append(101))
print([m.span() for m in it])
del it
show(lambda: b.append(101))
c = bytearray(b"aa")
def clears(m):
    try:
        c.clear()
        return b"cleared"
    except BufferError as e:
        return b"held"
print(re.sub(b"a", clears, c), c)
c.clear()
print(c)
def raises(m):
    raise KeyError("k")
d = bytearray(b"a")
show(lambda: re.sub(b"a", raises, d))
d.append(98)
print(d)
s = re.compile("a").scanner("aXa")
print(s.search().span(), s.search().span(), s.search())
e = bytearray(b"aa")
m = re.search(b"a", e)
e.clear()
print(m.span(), m.group(), m.string, m.groups())
alive_at_exit = re.compile(b"a").scanner(bytearray(b"a"))
"""

SLICES_AND_WRAPPERS = r"""
import re
class Step:
    def __index__(self):
        print("index")
        return 1
print("abc"[::Step()], "aba"[::-1] == "aba", ("aba"[::-1] is "aba"), "abc"[Step():], "abc"[:Step()])
s = "abc"
print(s[:] is s, s[::1] is s, s[0:3] is s, s[0:] is s, s[:3] is s, s[::-1] is s, s[1:] is s, s[0:2] is s)
p = re.compile("a")
print(s.__mul__ == s.__rmul__, s.__add__ == s.__add__, s.__mul__ == s.__mul__, s.__len__ == s.__len__, (1).__add__ == (1).__radd__, p.match == p.prefixmatch, p.match == p.match, p.search == p.match, s.upper == s.upper, s.upper == s.lower, s.__mul__ == s.upper, hash(s.__mul__) == hash(s.__mul__), s.__mul__ != s.__rmul__, [].__mul__ == [].__mul__, p.match.__name__, p.prefixmatch.__name__, type(p.match).__name__, p.scanner("a").match == p.scanner("a").match)
"""

LENGTHS_A_SUBCLASS_CHANGES = r"""
import copyreg
import os
import re
import _sre
from re import _compiler, _parser
class T(tuple):
    def __len__(self):
        return 0
class D(dict):
    def __len__(self):
        return 0
    def __contains__(self, key):
        return False
    def __getitem__(self, key):
        return "subclass"
    def get(self, *a):
        return "subclass"
    def __iter__(self):
        return iter(())
class C:
    def __getnewargs_ex__(self):
        return T(((), {}))
class K:
    def __new__(cls, **kw):
        return object.__new__(cls)
    def __getnewargs_ex__(self):
        return ((), D(a=1))
print(C().__reduce_ex__(2)[0].__name__, K().__reduce_ex__(2)[0].__name__, K().__reduce_ex__(2)[1][2])
print(os.stat_result(range(10), D(st_atime=1.5)).st_atime)
compiled = re.compile("(?P<x>a)")
code = _compiler._code(_parser.parse("(?P<x>a)"), compiled.flags)
made = _sre.compile("(?P<x>a)", compiled.flags, code, 1, D(x=1), T((None, "x")))
m = made.match("a")
print(made.groups, dict(made.groupindex), m.group("x"), m.groupdict(), m.lastgroup, m.lastindex)
"""


def test_more_defaults_than_parameters() -> None:
    same(MORE_DEFAULTS_THAN_PARAMETERS)


def test_getsizeof_default() -> None:
    same(GETSIZEOF_DEFAULT)


def test_callable_iterator() -> None:
    same(CALLABLE_ITERATOR)


def test_sys_exit_with_a_tuple_subclass() -> None:
    same(SYS_EXIT_TUPLE)


def test_a_buffer_held_cannot_be_resized() -> None:
    same(BUFFER_EXPORTS)


def test_slices_and_method_wrappers() -> None:
    same(SLICES_AND_WRAPPERS)


def test_what_a_subclass_cannot_change() -> None:
    same(LENGTHS_A_SUBCLASS_CHANGES)


if __name__ == "__main__":
    test_more_defaults_than_parameters()
    test_getsizeof_default()
    test_callable_iterator()
    test_sys_exit_with_a_tuple_subclass()
    test_a_buffer_held_cannot_be_resized()
    test_slices_and_method_wrappers()
    test_what_a_subclass_cannot_change()
