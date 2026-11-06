"""Generators, compiled, against CPython: the messages case C-3-41 does not compare, what happens at exit, and generator
expressions."""
from __future__ import annotations

import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

SHOW = """def show(f):
    try:
        r = f()
        s = repr(r)
        print(s if " at 0x" not in s else "<" + type(r).__name__ + ">")
    except BaseException as e:
        print(type(e).__name__, e)
"""

PROGRAMS: list[tuple[str, str]] = [
    ("messages", SHOW + r"""
import types
class E(Exception):
    pass
def plain():
    yield 1
def running():
    yield next(me)
me = running()
def closes():
    yield me2.close()
me2 = closes()
def throws():
    yield me3.throw(E)
me3 = throws()
def sends():
    yield me4.send(None)
me4 = sends()
def nested():
    yield from me5
me5 = nested()
class NoIter:
    pass
class BadClass(Exception):
    def __init__(self):
        raise ValueError("cannot be made")
def yf(x):
    r = yield from x
    yield r
class Sends:
    def __iter__(self):
        return self
    def __next__(self):
        return 1
class BadClose:
    def __iter__(self):
        return self
    def __next__(self):
        return 1
    def close(self):
        raise E("close failed")
class BadThrow:
    def __iter__(self):
        return self
    def __next__(self):
        return 1
    def throw(self, e):
        raise E("throw failed")
def started(g):
    next(g)
    return g
g = plain()
for fn in (lambda: next(me), lambda: next(me2), lambda: next(me3), lambda: next(me4), lambda: next(me5),
           lambda: plain().send(1), lambda: plain().send("a"), lambda: plain().send(None), lambda: plain().send(), lambda: plain().send(1, 2), lambda: plain().send(x=1),
           lambda: plain().close(1), lambda: plain().close(x=1), lambda: plain().__next__(1), lambda: plain().__iter__(1), lambda: plain().__del__(1), lambda: plain().__next__(x=1),
           lambda: plain().throw(), lambda: plain().throw(1), lambda: plain().throw("a"), lambda: plain().throw(None), lambda: plain().throw(int), lambda: plain().throw(object()), lambda: plain().throw(E, E(), None, 1), lambda: plain().throw(x=E), lambda: plain().throw(BadClass),
           lambda: plain().throw(E), lambda: plain().throw(E("x")), lambda: started(plain()).throw(E("y")), lambda: started(plain()).throw(BadClass), lambda: started(plain()).throw(1),
           lambda: next(yf(NoIter())), lambda: next(yf(1)), lambda: next(yf(None)), lambda: started(yf([1])).send(1), lambda: started(yf(Sends())).send(1), lambda: started(yf("ab")).send("x"),
           lambda: started(yf(BadClose())).close(), lambda: started(yf(BadClose())).throw(GeneratorExit), lambda: started(yf(BadThrow())).throw(E("z")), lambda: started(yf(BadThrow())).throw(GeneratorExit),
           lambda: g.gi_running, lambda: g.gi_suspended, lambda: g.gi_yieldfrom, lambda: g.gi_state, lambda: g.__name__, lambda: g.__qualname__, lambda: g.nothing,
           lambda: setattr(g, "__name__", 1), lambda: setattr(g, "__qualname__", 1), lambda: setattr(g, "gi_running", 1), lambda: setattr(g, "gi_state", 1), lambda: setattr(g, "x", 1), lambda: delattr(g, "__name__"), lambda: delattr(g, "x"),
           lambda: type(g)(), lambda: type(g).__new__(type(g)), lambda: type("X", (type(g),), {}), lambda: types.GeneratorType is type(g), lambda: isinstance(g, types.GeneratorType), lambda: type(g).__name__, lambda: type(g).__module__, lambda: type(g).__qualname__,
           lambda: type(g).send(1, 2), lambda: type(g).close(1), lambda: type(g).throw(1, E), lambda: type(g).__next__(1), lambda: type(g).__iter__(1), lambda: type(g).__del__(1), lambda: type(g).__repr__(1), lambda: type(g).__dict__["gi_running"].__get__(1), lambda: type(g).__dict__["__name__"].__get__(1),
           lambda: g[0], lambda: len(g), lambda: g + 1, lambda: 1 in plain(), lambda: bool(g), lambda: hash(g) == hash(g), lambda: g == g, lambda: g != g, lambda: g < g, lambda: iter(g) is g, lambda: g.__iter__() is g, lambda: list(plain()), lambda: tuple(plain()), lambda: set(plain()), lambda: dict([(1, 2)]), lambda: sorted(plain()), lambda: [*plain()], lambda: (*plain(),), lambda: {*plain()}, lambda: print(*plain()), lambda: max(plain()), lambda: any(plain()), lambda: sum(plain()), lambda: "".join(str(i) for i in plain()), lambda: dict((i, i) for i in plain()), lambda: enumerate(plain()).__next__(), lambda: next(zip(plain(), plain())), lambda: next(map(str, plain())), lambda: next(filter(None, plain()))):
    show(fn)
g.__name__ = "renamed"
g.__qualname__ = "Re.named"
print(g.__name__, g.__qualname__, repr(g).startswith("<generator object Re.named at 0x"), plain.__name__)
class K:
    def m(self):
        yield self
print(K().m().__qualname__, K().m().__name__, K.m.__name__, repr(K().m()).startswith("<generator object K.m at"))
def outer():
    def inner():
        yield
    return inner()
print(outer().__qualname__, (x for x in []).__qualname__, (x for x in []).__name__)
def renamed():
    yield
renamed.__name__ = "other"
renamed.__qualname__ = "other.q"
print(renamed().__name__, renamed().__qualname__)
"""),
    ("arguments", SHOW + r"""
def f(a, b=2, *c, d=4, **e):
    yield a, b, c, d, e
for fn in (lambda: f(), lambda: f(1, 2, 3, x=1).__next__(), lambda: f(1, a=1), lambda: f(1, d=9).__next__()):
    show(fn)
def uses_cell(a):
    def read():
        return a
    yield read
    a = 2
    yield read
g = uses_cell(1)
r = next(g)
print(r())
next(g)
print(r())
def calls(n):
    if n:
        yield from calls(n - 1)
    yield n
print(list(calls(5)))
def deep(n):
    yield from deep(n + 1)
show(lambda: next(deep(0)))
def fib():
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b
f2 = fib()
print([next(f2) for _ in range(20)])
class It:
    def __iter__(self):
        yield 1
        yield 2
print(list(It()), [*It()], tuple(It()), sum(It()), dict.fromkeys(It()))
a, b = It()
print(a, b)
def many():
    for i in range(100000):
        yield i
print(sum(many()), max(many()))
keep = [many() for _ in range(1000)]
print(sum([next(k) for k in keep]))
del keep
"""),
    ("genexprs", SHOW + r"""
log = []
class Src:
    def __init__(self, name):
        log.append("made " + name)
        self.name = name
    def __iter__(self):
        log.append("iter " + self.name)
        return iter([1, 2])
g = (x for x in Src("outer"))
print(log)
log.clear()
print(next(g), log)
h = (x + y for x in Src("a") for y in Src("b"))
print(log)
log.clear()
print(list(h), log)
log.clear()
show(lambda: (x for x in 1))
show(lambda: (x for x in None))
show(lambda: list(x for x in [1, 2] if x > 1))
show(lambda: list((x, y) for x in [1, 2] for y in [3, 4] if x != y))
show(lambda: sum(x * x for x in range(5)))
show(lambda: list(x for x in (y for y in [1, 2])))
show(lambda: list(1 / x for x in [1, 0]))
n = 10
add = (x + n for x in [1])
n = 20
print(list(add))
def in_function(n):
    return (x + n for x in [1, 2])
print(list(in_function(1)))
class C:
    v = [1, 2]
    g = (x for x in v)
    try:
        h = [y for y in (x * w for x in v)]
    except NameError as e:
        print("NameError")
print(list(C.g))
g2 = (x for x in [1, 2])
print(g2.gi_state, g2.gi_suspended, next(g2), g2.gi_state, g2.gi_suspended, list(g2), g2.gi_state)
g3 = (x for x in [1])
g3.close()
print(list(g3), g3.gi_state)
g4 = (x for x in [1])
show(lambda: g4.throw(ValueError("v")))
print(list(g4))
g5 = (x for x in [1])
show(lambda: g5.send(1))
print(next(g5))
show(lambda: g5.send(1))
print(", ".join(str(i) for i in range(3)), sorted(i for i in [3, 1]), set(i for i in [1, 1]), tuple(i for i in "ab"), dict((i, 1) for i in "a"), max(i for i in [1, 2]), any(i for i in [0, 1]), all(i for i in [0, 1]), "x".join(c for c in "ab"), frozenset(i for i in [1]) == {1}, len(list(i for i in [])))
"""),
    ("at_exit", r"""
class D:
    def __init__(self, n):
        self.n = n
    def __del__(self):
        print("del", self.n)
def holds(n):
    d = D(n)
    try:
        yield d
    finally:
        print("finally", n)
def uncaught_in_close():
    try:
        yield 1
    finally:
        raise ValueError("in finally")
def ignores():
    try:
        yield 1
    except GeneratorExit:
        yield 2
def in_with():
    class M:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            print("exit", a[0].__name__)
    with M():
        yield 1
kept = holds("kept at module level")
next(kept)
kept2 = holds("unstarted")
kept3 = in_with()
next(kept3)
a = uncaught_in_close()
next(a)
del a
print("after a")
b = ignores()
next(b)
del b
print("after b")
def resurrect():
    global saved
    try:
        yield 1
    finally:
        saved = "was closing"
c = resurrect()
next(c)
del c
print(saved)
print("end")
"""),
]

REFUSED = (
    ("def f():\n    yield\nf().gi_code", "gi_code"),
    ("def f():\n    yield\nf().gi_frame", "gi_frame"),
    ("def f():\n    yield\nf().throw(ValueError, ValueError(), None)", "DeprecationWarning"),
)


def pytest_generate_tests(metafunc: Any) -> None:
    if "program" in metafunc.fixturenames:
        metafunc.parametrize("program", PROGRAMS, ids=[name for name, _ in PROGRAMS])
    if "refused" in metafunc.fixturenames:
        metafunc.parametrize("refused", REFUSED, ids=[text[-24:] for text, _ in REFUSED])


def test_as_cpython(program: tuple[str, str]) -> None:
    same(program[1])


def test_what_is_not_there_yet_stops_by_name(refused: tuple[str, str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(textwrap.dedent(refused[0]) + "\n", encoding="utf-8")
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, timeout=60)
    assert got.returncode == 70 and "not implemented" in got.stderr and refused[1] in got.stderr, got


if __name__ == "__main__":
    for item in PROGRAMS:
        test_as_cpython(item)
