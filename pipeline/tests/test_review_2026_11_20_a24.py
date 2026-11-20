"""Review A24 of 2026-11-20 (range 7a8e3f2..729cd7b), compiled against CPython: one program for each finding fixed.

Codex's Astra at low effort read the step that gives each declaration of a slot its own cell (RL-541, C-3-78), the limit of
digits for a main program's literals (C-8-18) and the fixes of A23; the review log has its eleven findings as RL-564 to
RL-574. Each program here is wider than the report's reproduction and holds it; standard output, the exit status and
standard error must agree. RL-570, RL-571 and RL-573 are held by `test_start_up_environment.py` (the line echoed for a
literal over the limit), RL-565 by the sweep of the order in which a built-in type lets go of what it holds
(`test_release_order.py`), RL-574 by its case; RL-572 is the author's.

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_20_a24
"""
from __future__ import annotations

from typing import Any

from pipeline.tests.test_review_2026_11_19 import same

FINDINGS: list[tuple[str, str, str]] = [
    ('RL-564', 'a slot under the name of a field of the built-in base', r'''
class E(Exception):
    __slots__ = ("args",)

e = E(1)
e.args = 2
print(e.args, BaseException.args.__get__(e), repr(e), str(e))
del e.args
try:
    print(e.args)
except AttributeError:
    print("the slot is empty")
print(BaseException.args.__get__(e))

class O(OSError):
    __slots__ = ("errno", "filename", "strerror")

o = O(2, "No such file", "name.txt")
print(OSError.errno.__get__(o), OSError.filename.__get__(o), str(o))
o.errno = "mine"
print(o.errno, OSError.errno.__get__(o), str(o))

class S(StopIteration):
    __slots__ = ("value",)

s = S(5)
print(StopIteration.value.__get__(s))
s.value = 7
print(s.value, StopIteration.value.__get__(s))

class T(Exception):
    __slots__ = ("__traceback__", "__cause__", "__context__")

try:
    try:
        raise KeyError("k")
    except KeyError:
        raise T("t")
except T as t:
    print(type(BaseException.__context__.__get__(t)).__name__, BaseException.__traceback__.__get__(t) is not None)
    try:
        print(t.__context__)
    except AttributeError:
        print("the slot is empty")
    t.__traceback__ = "mine"
    print(t.__traceback__, BaseException.__traceback__.__get__(t) is not None)

class F(E):
    __slots__ = ("args",)

f = F(9)
f.args = "F's"
E.args.__set__(f, "E's")
print(f.args, E.args.__get__(f), BaseException.args.__get__(f))

class Mark:
    def __init__(self, n):
        self.n = n
    def __del__(self):
        print("gone:", self.n)

def run():
    g = F(Mark("the exception's own"))
    g.args = Mark("F's slot")
    E.args.__set__(g, Mark("E's slot"))

run()

class A(AttributeError):
    __slots__ = ("name", "obj")

try:
    raise A("no such", name="n", obj=3)
except A as a:
    print(AttributeError.name.__get__(a), AttributeError.obj.__get__(a))
    try:
        print(a.name)
    except AttributeError:
        print("the slot is empty")
'''),
    ('RL-566', '__dict__ and __weakref__ are added where the best base has none', r'''
class A:
    __slots__ = ('x',)
class M:
    pass
class W:
    __slots__ = ('__weakref__',)
def attempt(label, make):
    try:
        cls = make()
        d = cls()
        try:
            d.a = 3
            got = "a dict"
        except AttributeError:
            got = "no dict"
        import weakref
        try:
            weakref.ref(d)
            got += ", weak"
        except TypeError:
            got += ", not weak"
        print(label, got, [k.__name__ for k in cls.__mro__], sorted(n for n in vars(cls) if n in ("__dict__", "__weakref__", "x")))
    except Exception as e:
        print(label, type(e).__name__, e)
def c1():
    class D(A, M):
        __slots__ = ('x', '__dict__', '__weakref__')
    return D
def c2():
    class D(M, A):
        __slots__ = ('__dict__',)
    return D
def c3():
    class D(M):
        __slots__ = ('__dict__',)
    return D
def c4():
    class D(M):
        __slots__ = ('__weakref__',)
    return D
def c5():
    class D(A, W):
        __slots__ = ('__weakref__',)
    return D
def c6():
    class D(W, A):
        __slots__ = ('__weakref__',)
    return D
def c7():
    class D(A, M):
        __slots__ = ()
    return D
def c8():
    class D(A):
        __slots__ = ('__dict__', '__dict__')
    return D
def c9():
    class D(A, M):
        __slots__ = ('__weakref__', '__weakref__')
    return D
for i, c in enumerate((c1, c2, c3, c4, c5, c6, c7, c8, c9), 1):
    attempt("c" + str(i), c)
import weakref
class X(int, M):
    pass
class Y(M, int):
    pass
class Z(tuple, M):
    __slots__ = ()
class V(A, M):
    pass
class U(M, W):
    __slots__ = ()
for cls in (X, Y, Z, V, U):
    o = cls()
    try:
        weakref.ref(o)
        weak = "weak"
    except TypeError:
        weak = "not weak"
    try:
        o.a = 1
        has = "a dict"
    except AttributeError:
        has = "no dict"
    print(cls.__name__, has, weak, sorted(n for n in vars(cls) if n in ("__dict__", "__weakref__")), cls.__base__.__name__)
'''),
    ('RL-567', 'the default state of an object with more slots than names', r'''
import copy
class A:
    __slots__ = ('x',)
class B(A):
    __slots__ = ('x',)
    __slotnames__ = ['x']
class C(A):
    __slots__ = ('x',)
class N(A):
    __slots__ = ('y',)
    __slotnames__ = None
class L(A):
    __slots__ = ('y',)
    __slotnames__ = ['x', 'y', 'z']
class G(A):
    __slots__ = iter(('y', 'z'))
class P:
    pass
class Q(P):
    __slotnames__ = []
for cls in (B, C, N, L, G, P, Q):
    o = cls()
    try:
        o.x = 2
    except AttributeError:
        pass
    for proto in (2, 4):
        try:
            print(cls.__name__, proto, o.__reduce_ex__(proto)[2])
        except TypeError as e:
            print(cls.__name__, proto, type(e).__name__, e)
    try:
        print(cls.__name__, "getstate", o.__getstate__())
    except TypeError as e:
        print(cls.__name__, "getstate", type(e).__name__, e)
    try:
        c = copy.copy(o)
        print(cls.__name__, "copy", getattr(c, "x", "none"))
    except TypeError as e:
        print(cls.__name__, "copy", type(e).__name__, e)
'''),
    ('RL-568', 'the error of an empty slot has a name and an object where the attribute lookup adds them', r'''
class D:
    __slots__ = ("x",)
class F(D):
    __slots__ = ("x",)
f = F()
s = super(F, f)
for label, act in (("the member's own __get__", lambda: D.x.__get__(f)), ("by the name", lambda: f.x), ("getattr", lambda: getattr(f, "x")),
                   ("object.__getattribute__", lambda: object.__getattribute__(f, "x")), ("through super()", lambda: s.x),
                   ("the member's __delete__", lambda: D.x.__delete__(f)), ("delattr", lambda: delattr(f, "x")),
                   ("the type's __getattribute__", lambda: F.__getattribute__(f, "x"))):
    try:
        act()
    except AttributeError as e:
        print(label, "|", e.name, "|", "f" if e.obj is f else "the super object" if getattr(e, "obj", None) is s else "none", "|", e)
import functools
p = functools.partial.__new__(functools.partial, abs)
print(type(functools.partial.func).__name__)
'''),
    ('RL-569', 'every item of __slots__ is looked at before a conflict with a class variable', r'''
def attempt(label, make):
    try:
        make()
        print(label, "made")
    except Exception as e:
        print(label, type(e).__name__, e)
def b1():
    class Bad:
        __slots__ = ('x', 1)
        x = 1
def b2():
    class Bad:
        __slots__ = ('x', 'not an identifier!')
        x = 1
def b3():
    class Base:
        pass
    class Bad(Base):
        __slots__ = ('x', '__dict__')
        x = 1
def b4():
    class Bad:
        __slots__ = ('x', 'y')
        y = 1
        x = 2
def b5():
    class Bad:
        __slots__ = ('__dict__', '__dict__', 'x')
        x = 1
def b6():
    class Good:
        __slots__ = ('__qualname__', '__classcell__', 'x', 'x')
    print(sorted(n for n in vars(Good) if not n.startswith("__") or n in ("__qualname__", "__classcell__")))
for i, b in enumerate((b1, b2, b3, b4, b5, b6), 1):
    attempt("b" + str(i), b)
'''),
]


def pytest_generate_tests(metafunc: Any) -> None:
    if "finding" in metafunc.fixturenames:
        metafunc.parametrize("finding", FINDINGS, ids=[f"{rl}-{name}" for rl, name, _ in FINDINGS])


def test_finding(finding: tuple[str, str, str]) -> None:
    same(finding[2])


if __name__ == "__main__":
    for row in FINDINGS:
        same(row[2])
        print("ok", row[0])
