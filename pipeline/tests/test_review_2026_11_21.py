"""Review A25 of 2026-11-21 (range 729cd7b..30ad3a9), compiled against CPython: one program for each finding fixed.

Codex's Astra at low effort read the step that gives a built-in type's dealloc its own order (RL-565, RL-577), the fixes of
A24 and the streams' state methods; the review log has its 22 findings as RL-578 to RL-599. Each program here is the
report's own reproduction, run under CPython and compiled: standard output, the exit status and standard error must
agree. The findings left open (RL-583 to RL-585, RL-588, RL-591 to RL-594, RL-597 to RL-599) have no program here.

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_21
"""
from __future__ import annotations

from typing import Any

from pipeline.tests.test_review_2026_11_19 import same

FINDINGS: list[tuple[str, str, str]] = [
    ('RL-578', 'a regex scanner lets go of its subject, then its pattern', r'''
import re, weakref
events = []
class S(str):
    def __del__(self): events.append(str(self))
p = re.compile(S("a"))
re.purge()
w = weakref.ref(p, lambda r: events.append("pattern"))
s = p.scanner(S("abc"))
del p, s
print(events)
'''),
    ('RL-579', 'a function lets go of its __module__ before its defaults', r'''
events = []
class V:
    def __init__(self, n): self.n = n
    def __del__(self): events.append(self.n)
def make():
    v = V("closure")
    def f(a=V("default"), *, k=V("kw")): return v
    f.__doc__ = V("doc")
    f.__module__ = V("module")
    f.x = V("dict")
    return f
import weakref
f = make()
w = weakref.ref(f, lambda r: events.append("weak"))
del f
print(events)
'''),
    ('RL-580', "an exception's state is the dict it has, whatever a deriving class has under __dict__", r'''
for base in (Exception, OSError, ImportError, AttributeError):
    class E(base):
        __dict__ = {'fake': 1}
    e = E('a')
    e.x = 2
    print(base.__name__, e.__reduce__()[2])
'''),
    ('RL-581', 'a ContextVar lets go of its name, then its default', r'''
import contextvars as c
events=[]
class V:
    def __init__(self,n): self.n=n
    def __del__(self): events.append(self.n)
class S(str):
    def __del__(self): events.append(str(self))
def var():
    x=c.ContextVar(S("name"),default=V("default"))
    del x
var()
print(events)
'''),
    ('RL-582', 'a Token lets go of its variable, then its old value', r'''
import contextvars as c
events=[]
class V:
    def __init__(self,n): self.n=n
    def __del__(self): events.append(self.n)
def tok():
    ctx=c.Context()
    def make():
        x=c.ContextVar("x",default=V("default"))
        x.set(V("old"))
        return x.set(None)
    t=ctx.run(make)
    del ctx,t
tok()
print(events)
'''),
    ('RL-586', "a function lets go of its closure's cells last one first", r'''
events=[]
class V:
    def __init__(self,n): self.n=n
    def __del__(self): events.append(self.n)
def closure():
    def create():
        a=V("a"); b=V("b");c=V("c")
        def f():return a,b,c
        return f
    f=create()
    del f
closure()
print(events)
'''),
    ('RL-587', 'an lru_cache wrapper lets go of its cache, then its function', r'''
import _functools
events=[]
class V:
    def __init__(self,n): self.n=n
    def __del__(self): events.append(self.n)
class F(V):
    def __call__(self,*args): return V("result")
def cache():
    f=_functools._lru_cache_wrapper(F("func"),None,False,tuple)
    f(V("key"))
    del f
cache()
print(events)
'''),
    ('RL-589', 'the conflict of a private slot names the mangled member', r'''
try:
    class A:
        __slots__ = ("__x",)
        __x = 1
except ValueError as e:
    print(type(e).__name__, str(e))
'''),
    ('RL-590', 'arbitrary __slots__ are refused for a subtype of the best base', r'''
for base in (int, bytes):
    class Parent(base):
        __slots__ = ()
    try:
        class Child(Parent):
            __slots__ = ("x",)
    except TypeError as e:
        print(type(e).__name__, str(e))
'''),
    ('RL-595', '__setstate__ of a closed in-memory stream is refused', r'''
import io
class B(io.BytesIO):
    __dict__ = "hidden"
class S(io.StringIO):
    __dict__ = "hidden"
for k, state in ((B, (b"ok", 1, {"v": 2})), (S, ("ok", None, 1, {"v": 2}))):
    o = k()
    o.close()
    try: o.__setstate__(state)
    except Exception as e: print(type(e).__name__, str(e))
    print(o.closed, o.__dict__, None if o.closed else o.__getstate__())
'''),
    ('RL-596', 'BytesIO.__setstate__ refuses None for the buffer', r'''
import io
class B(io.BytesIO):
    __dict__ = "hidden"
o = B()
try: o.__setstate__((None, 0, {"v": 2}))
except Exception as e: print(type(e).__name__, str(e))
print(o.closed, o.__dict__, o.__getstate__())
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
