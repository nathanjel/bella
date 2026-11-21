"""Review A25 of 2026-11-21 (range 729cd7b..30ad3a9), compiled against CPython: one program for each finding fixed.

Codex's Astra at low effort read the step that gives a built-in type's dealloc its own order (RL-565, RL-577), the fixes of
A24 and the streams' state methods; the review log has its 22 findings as RL-578 to RL-599. Each program here is the
report's own reproduction, run under CPython and compiled: standard output, the exit status and standard error must
agree. The findings left open (RL-583, RL-591, RL-592, RL-599) have no program here; RL-584 was done later the
same day and has one, and RL-585, RL-588, RL-593, RL-594, RL-597 and RL-598 that night.
The last program is RL-600's, found in the reviewer's probes after the round: the keys and results of a bounded
`lru_cache`, which the prelude's ring of links held for good. Its row with a comparison that fails stops at the lookup of
the third key (review A27, RL-619); the pop of the oldest link is reached by RL-619's program in
pipeline/tests/test_review_2026_11_21_a27.py.

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
    ('RL-585', "a BufferedRWPair, an exact BytesIO and an exact StringIO have no finaliser of IOBase's (RL-598)", r'''
import io, weakref
events = []
class V:
    def __init__(self, n): self.n = n
    def __del__(self): events.append(self.n)
class Raw(io.BytesIO):
    def __init__(self, n):
        super().__init__()
        self.n = n
    def close(self):
        events.append("close " + self.n)
        super().close()
    def __del__(self): events.append("del " + self.n)
def pair():
    p = io.BufferedRWPair(Raw("r"), Raw("w"))
    p.x = V("dict")
    w = weakref.ref(p, lambda r: events.append("weak"))
    del p
pair()
print("a pair:", events)
class Pair(io.BufferedRWPair): pass
def sub():
    p = Pair(Raw("r"), Raw("w"))
    w = weakref.ref(p, lambda r: events.append("weak"))
    del p
events.clear()
sub()
print("a subclass of the pair:", events)
for kind in (io.BytesIO, io.StringIO):
    events.clear()
    o = kind()
    o.close = lambda: events.append("close")
    o.x = V("dict")
    w = weakref.ref(o, lambda r: events.append("weak"))
    del o
    print("an exact", kind.__name__ + ":", events)
    class Sub(kind): pass
    events.clear()
    o = Sub()
    o.close = lambda: events.append("close")
    o.x = V("dict")
    w = weakref.ref(o, lambda r: events.append("weak"))
    del o
    print("   a subclass:", events)
'''),
    ('RL-593', 'a struct sequence lets go of its fields first one first, those past the visible ones after them', r'''
import os, time
events = []
class V:
    def __init__(self, n): self.n = n
    def __del__(self): events.append(self.n)
def gone(label, make):
    events.clear()
    made = make()
    del made
    print(label, events)
gone("terminal_size:", lambda: os.terminal_size((V("columns"), V("lines"))))
gone("struct_time:", lambda: time.struct_time([V(str(i)) for i in range(9)]))
gone("struct_time with its two more:", lambda: time.struct_time([V(str(i)) for i in range(11)]))
gone("stat_result:", lambda: os.stat_result([V(str(i)) for i in range(10)]))
gone("stat_result with more:", lambda: os.stat_result([V(str(i)) for i in range(15)]))
gone("times_result:", lambda: os.times_result([V(str(i)) for i in range(5)]))
gone("a tuple, last one first:", lambda: tuple([V(str(i)) for i in range(3)]))
kept = time.struct_time([V(str(i)) for i in range(11)])
events.clear()
state = kept.__reduce__()
del kept
print("a struct_time whose reduced state is held:", events)
del state
print("   and the state let go:", events)
'''),
    ('RL-594', 'an iterator of a Context holds the mapping until it dies, exhausted or not', r'''
import contextvars
events = []
class V:
    def __del__(self): events.append("v")
for kind in ("keys", "values", "items", "__iter__"):
    events.clear()
    cx = contextvars.Context()
    cx.run(contextvars.ContextVar("k").set, V())
    it = getattr(cx, kind)()
    del cx
    list(it)
    events.append("exhausted")
    del it
    print(kind, events)
'''),
    ('RL-597', 'a __del__ is bound as a special method is: a staticmethod, a classmethod, a descriptor, a builtin, None', r'''
import sys
def hook(e): print("   unraisable", e.exc_type.__name__, e.err_msg.split(" at 0x")[0])
sys.unraisablehook = hook
class S(list):
    @staticmethod
    def __del__(): print("static")
class C(list):
    @classmethod
    def __del__(cls): print("class", cls.__name__)
class Bound:
    def __get__(self, obj, owner):
        print("bound for", type(obj).__name__, owner.__name__)
        return lambda: print("called")
class D: __del__ = Bound()
class N: __del__ = None
class P: __del__ = print                         # a builtin function binds nothing: called with no argument
class L: __del__ = lambda *a: print("a function, with", len(a))
class M: __del__ = list.clear                    # a method of another type: called with the object, which it refuses
class Raises:
    def __get__(self, obj, owner): raise ValueError("binding")
class F: __del__ = Raises()                      # no finaliser is called, and nothing is reported
class Callable:
    def __call__(self, *a): print("an instance called with", len(a))
class I: __del__ = Callable()
class StaticRaises(list):
    @staticmethod
    def __del__(): raise KeyError("static")
class Sub(S): pass
for k in (S, C, D, N, P, L, M, F, I, StaticRaises, Sub):
    print(k.__name__)
    o = k()
    del o
print("done")
'''),
    ('RL-588', 'the names of __slots__ are sorted as objects: a str subclass decides the order of the members and of their release', r'''
events = []
class T(str):
    def __lt__(self, other):
        events.append("compare " + str(self) + " " + str(other))
        return super().__gt__(other)
class V:
    def __init__(self, n): self.n = n
    def __del__(self): events.append("gone " + self.n)
class D:
    __slots__ = (T("a"), T("b"), T("c"))
print(events, [n for n in vars(D) if n in ("a", "b", "c")])
events.clear()
d = D()
d.a, d.b, d.c = V("a"), V("b"), V("c")
del d
print("released:", events)
events.clear()
class M:
    __slots__ = (T("z"), "m", T("__p"), "__dict__", "__weakref__", "a")
print(len(events) > 0, [n for n in vars(M) if n in ("z", "m", "a", "_M__p")])
events.clear()
m = M()
m.z, m.m, m.a, m._M__p, m.other = V("z"), V("m"), V("a"), V("p"), V("in the dict")
del m
print("released:", events)
events.clear()
class Bad(str):
    def __lt__(self, other): raise LookupError("lt")
try:
    class E: __slots__ = (Bad("a"), Bad("b"))
    print("made")
except LookupError: print("a comparison that raises: no class")
class One: __slots__ = (Bad("a"),)
print("one name:", [n for n in vars(One) if n == "a"])
class P: __slots__ = ("c", "a", "b")
print("plain names:", [n for n in vars(P) if n in ("a", "b", "c")])
p = P()
p.a, p.b, p.c = V("a"), V("b"), V("c")
del p
print("released:", events)
class Sub(D): __slots__ = (T("y"), T("x"))
events.clear()
s = Sub()
s.a, s.b, s.c, s.x, s.y = V("a"), V("b"), V("c"), V("x"), V("y")
del s
print("a subclass, its own first:", [e for e in events if e.startswith("gone")])
'''),
    ('RL-584', 'the item iterators of dict and OrderedDict keep their own pair and give it again', r'''
from collections import OrderedDict

events: list[str] = []


class V:
    def __init__(self, n: str) -> None:
        self.n = n

    def __repr__(self) -> str:
        return self.n

    def __del__(self) -> None:
        events.append(self.n)


def said() -> list[str]:
    out = list(events)
    events.clear()
    return out


for kind in (dict, OrderedDict):
    for backwards in (False, True):
        label = kind.__name__ + (", reversed" if backwards else "")
        d = kind()
        for n in "abc":
            d["k" + n] = V("v" + n)
        it = reversed(d.items()) if backwards else iter(d.items())
        k, v = next(it)                          # unpacked at once: the pair is the iterator's alone
        first = repr(v)
        del v
        d[k] = None                              # the mapping lets go of the value; the iterator's pair has it still
        events.append("replaced")
        k2, v2 = next(it)                        # the same pair is given again, with the next key and value
        del v2
        events.append("advanced")
        print(label, "| the first value goes at the next step:", first, said())
        held = next(it)                          # the same pair once more, and the program keeps it: the second value is the mapping's alone again
        try:
            next(it)
        except StopIteration:
            events.append("exhausted")
        d.clear()
        events.append("cleared")
        print(label, "| the second value goes with the mapping, the third is in the pair the program holds:", said())
        del it
        events.append("the iterator went")
        print(label, "| the iterator's end takes nothing with it:", said(), held)
        del held
        print(label, "| the program's own:", said())
    d = kind((n, V("w" + n)) for n in "xyz")
    stepped = iter(d.items())
    pairs = [hash(next(stepped)) == hash((n, d[n])) for n in "xyz"]
    print(kind.__name__, "| a pair used again has the hash of what it holds now:", pairs)
    items = list(d.items())
    print(kind.__name__, "| pairs that are held are all different objects:", len({id(p) for p in items}) == 3, items)
    del d, items, pairs, stepped
    print(kind.__name__, "| let go:", sorted(said()))
od = OrderedDict((n, V("o" + n)) for n in "pqr")
it = iter(od.items())
k, v = next(it)
del v
state = it.__reduce__()
print("an OrderedDict's item iterator, reduced:", state[1], said())
k, v = next(it)
del v, state
od.clear()
print("and stepped once more:", said())
del it
print("and gone:", said())
'''),
    ('RL-600', 'a bounded lru_cache lets go of its links, oldest first, at its end and when it is cleared', r'''
import functools
import weakref


class Noted:
    """A value that says when it goes; equal and hashed by its label."""

    def __init__(self, label: str) -> None:
        self.label = label

    def __repr__(self) -> str:
        return self.label

    def __hash__(self) -> int:
        return hash(self.label)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Noted) and other.label == self.label

    def __del__(self) -> None:
        print("  gone:", self.label)


def make(maxsize: int | None, typed: bool = False) -> "functools._lru_cache_wrapper[Noted]":
    def compute(key: Noted, tag: str = "") -> Noted:
        return Noted("result of " + key.label + tag)
    return functools.lru_cache(maxsize, typed)(compute)


def fill(cached: "functools._lru_cache_wrapper[Noted]", labels: str) -> None:
    for label in labels:
        cached(Noted("key " + label))


print("---- a bounded cache at its end: the keys and results, oldest first")
f = make(3)
fill(f, "abc")
print(f.cache_info())
del f
print("---- after a hit the order is the order of use")
f = make(3)
fill(f, "abc")
f(Noted("key a"))
print("  (the probe key went; the cached one stays)")
del f
print("---- a miss in a full cache lets the oldest go, the key before the result")
f = make(2)
fill(f, "abc")
print("  then:", f.cache_info())
fill(f, "b")
fill(f, "d")
print("  then:", f.cache_info())
del f
print("---- cache_clear")
f = make(3)
fill(f, "abc")
f.cache_clear()
print("  cleared:", f.cache_info())
fill(f, "xy")
f.cache_clear()
del f
print("---- an unbounded cache at its end, and cleared")
f = make(None)
fill(f, "abc")
del f
f = make(None)
fill(f, "ab")
f.cache_clear()
print("  cleared:", f.cache_info())
del f
print("---- no cache")
f = make(0)
fill(f, "ab")
print(f.cache_info())
del f
print("---- the wrapper's own things: weak references, the function, its dict, then the links")


class Function:
    def __call__(self, key: Noted) -> Noted:
        return Noted("result of " + key.label)

    def __del__(self) -> None:
        print("  gone: the function")


g = functools.lru_cache(2)(Function())
g.note = Noted("a value in the wrapper's dict")      # type: ignore[attr-defined]
fill(g, "ab")
watch = weakref.ref(g, lambda r: print("  the weak reference's callback"))
del g
print("---- and for an unbounded one")
g = functools.lru_cache(None)(Function())
g.note = Noted("a value in the wrapper's dict")      # type: ignore[attr-defined]
fill(g, "ab")
watch = weakref.ref(g, lambda r: print("  the weak reference's callback"))
del g
print("---- typed, and keywords")
h = make(2, True)
h(Noted("key a"), tag="!")
h(Noted("key a"))
h(key=Noted("key k"))
print("  then:", h.cache_info())
del h
print("---- a result that is asked for while it is being computed")
calls: list[str] = []


@functools.lru_cache(2)
def again(n: int) -> Noted:
    calls.append("in " + str(n))
    if n > 0:
        again(n - 1)
        again(n - 1)
    return Noted("again " + str(n))


again(3)
print("  calls:", len(calls), again.cache_info())
again.cache_clear()
print("---- a key whose comparison fails when a third key is looked up")


class Touchy:
    def __init__(self, label: str, fail: list[bool]) -> None:
        self.label = label
        self.fail = fail

    def __hash__(self) -> int:
        return 7

    def __eq__(self, other: object) -> bool:
        if self.fail[0]:
            raise RuntimeError("no comparison now")
        return isinstance(other, Touchy) and other.label == self.label

    def __del__(self) -> None:
        print("  gone: touchy", self.label)


switch = [False]


@functools.lru_cache(2)
def touchy(key: Touchy) -> str:
    return "value of " + key.label


touchy(Touchy("a", switch))
touchy(Touchy("b", switch))
switch[0] = True
try:
    touchy(Touchy("c", switch))
except RuntimeError as e:
    print("  RuntimeError:", e.args, touchy.cache_info())
switch[0] = False
print("  still there:", touchy(Touchy("a", switch)), touchy(Touchy("b", switch)), touchy.cache_info())
touchy(Touchy("d", switch))
print("  then:", touchy.cache_info())
touchy.cache_clear()
print("---- a method's cache dies with the class's function, not the object")


class Holder:
    @functools.lru_cache(2)
    def get(self, n: int) -> Noted:
        return Noted("held " + str(n))


holder = Holder()
holder.get(1)
holder.get(2)
holder.get(3)
del holder
print("  the object is still a key")
Holder.get.cache_clear()
print("---- the end")
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
