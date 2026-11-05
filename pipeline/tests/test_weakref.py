"""Weak references and resurrection, compiled, against CPython.

Case C-9-10 shows the behaviour by exception class, as a case must; these compare messages too, the
order of a list and of its callbacks, a proxy's every operator, the classes the standard library builds
on them, and what a finaliser that keeps its object does. Addresses are masked before they are compared.
"""
from __future__ import annotations

from typing import Any

from pipeline.tests.test_review_2026_11_03 import same

SHOW = """def show(f):
    try:
        r = f()
        s = repr(r)
        print(s if " at 0x" not in s else "<" + type(r).__name__ + ">")
    except Exception as e:
        print(type(e).__name__, e)
"""

MASK = """def mask(s):
    out = ""
    i = 0
    while i < len(s):
        if s[i:i + 2] == "0x":
            out += "ADDR"
            i += 2
            while i < len(s) and s[i] in "0123456789abcdef":
                i += 1
        else:
            out += s[i]
            i += 1
    return out
"""


PROGRAMS: list[tuple[str, str]] = [
    ('references', SHOW + MASK + """import weakref, _weakref
class C:
    def m(self):
        return "method"
    def __repr__(self):
        return "C!"
c = C()
r = weakref.ref(c)
print(r() is c, weakref.ref(c) is r, weakref.ReferenceType is weakref.ref, _weakref.ref is weakref.ref, type(r), type(r).__name__, type(r).__qualname__, type(r).__module__, r.__callback__, r.__class__, isinstance(r, weakref.ref), callable(r), weakref.getweakrefcount(c), weakref.getweakrefs(c) == [r], c.__weakref__ is r, hash(r) == hash(c), r == r, r == weakref.ref(c), r != r, r != 1, r == 1)
print(mask(repr(r)), mask(str(r)), weakref.ref.__mro__, weakref.ref.__name__, weakref.ref.__doc__ is not None, _weakref.__doc__ is not None, sorted([n for n in vars(_weakref) if not n.startswith("__")]), [n for n in dir(_weakref) if n.startswith("_") and not n.startswith("__")])
def f():
    pass
class WithName:
    __name__ = "attr"
print(mask(repr(weakref.ref(f))), mask(repr(weakref.ref(C))), mask(repr(weakref.ref(WithName()))), mask(repr(weakref.ref(print))), mask(repr(weakref.ref(c.m))), mask(repr(weakref.ref({1}))))
cb = lambda ref: print("callback", ref() is None)
r2 = weakref.ref(c, cb)
r3 = weakref.ref(c, cb)
r4 = weakref.ref(c, None)
print(r2 is r, r3 is r2, r4 is r, r2.__callback__ is cb, r2() is c, r2 == r, hash(r2) == hash(r), weakref.getweakrefcount(c), weakref.getweakrefs(c) == [r, r3, r2], c.__weakref__ is r)
del r, r4
print(weakref.getweakrefcount(c), weakref.getweakrefs(c) == [r3, r2], c.__weakref__ is r3)
del c
print(r2(), r2.__callback__, r3(), r2 == r3, r2 == r2, r2 != r3, hash(r2) == hash(r2), mask(repr(r2)))
fresh = weakref.ref(C())
print(fresh(), mask(repr(fresh)))
show(lambda: hash(fresh))
for f2 in (lambda: weakref.ref(), lambda: weakref.ref(1), lambda: weakref.ref(1, 2, 3), lambda: weakref.ref("a"), lambda: weakref.ref(None), lambda: weakref.ref([]), lambda: weakref.ref({}), lambda: weakref.ref(()), lambda: weakref.ref(b""), lambda: weakref.ref(True), lambda: weakref.ref(2**64), lambda: weakref.ref(range(1)), lambda: weakref.ref(iter([])), lambda: weakref.ref(object()), lambda: weakref.ref(frozendict()),
           lambda: weakref.ref(C(), x=1), lambda: weakref.ref(C())(1), lambda: weakref.ref(C())(x=1), lambda: weakref.ref.__call__(1), lambda: weakref.ref.__init__(weakref.ref(C)), lambda: weakref.ref.__init__(weakref.ref(C), C, x=1), lambda: weakref.ref.__init__(weakref.ref(C), C, None, 1), lambda: weakref.ref.__new__(weakref.ref), lambda: weakref.ref.__new__(weakref.ref, C, None, 1), lambda: weakref.ref.__new__(int, C), lambda: weakref.ref(C) < weakref.ref(C), lambda: weakref.ref(C).x, lambda: setattr(weakref.ref(C), "x", 1), lambda: setattr(weakref.ref, "x", 1), lambda: weakref.ref(C).__callback__, lambda: setattr(weakref.ref(C), "__callback__", 1), lambda: weakref.ref[int], lambda: weakref.ref[int].__origin__,
           lambda: weakref.getweakrefcount(), lambda: weakref.getweakrefcount(1, 2), lambda: weakref.getweakrefcount(x=1), lambda: weakref.getweakrefcount(1), lambda: weakref.getweakrefcount([]), lambda: weakref.getweakrefcount(C()), lambda: weakref.getweakrefs(), lambda: weakref.getweakrefs(1, 2), lambda: weakref.getweakrefs(1), lambda: weakref.getweakrefs([]), lambda: weakref.getweakrefs(C()),
           lambda: _weakref._remove_dead_weakref(), lambda: _weakref._remove_dead_weakref(1, 2), lambda: _weakref._remove_dead_weakref({}, 1, 2), lambda: _weakref._remove_dead_weakref({}, "k"), lambda: _weakref._remove_dead_weakref({"k": 1}, "k"), lambda: _weakref._remove_dead_weakref({}, []), lambda: _weakref._remove_dead_weakref(None, 1), lambda: _weakref._remove_dead_weakref(x=1)):
    show(f2)
d = {"live": weakref.ref(C), "dead": weakref.ref(C())}
print(_weakref._remove_dead_weakref(d, "live"), sorted(d), _weakref._remove_dead_weakref(d, "dead"), sorted(d), _weakref._remove_dead_weakref(d, "absent"), sorted(d))
"""),
    ('what_can_be_referred_to', SHOW + """import weakref, sys
class Plain:
    pass
class Slots:
    __slots__ = ("x",)
class SlotsWeak:
    __slots__ = ("x", "__weakref__")
class SlotsDict:
    __slots__ = ("__dict__",)
class SubSlots(Slots):
    pass
class SubSlotsEmpty(Slots):
    __slots__ = ()
class SubWeak(SlotsWeak):
    __slots__ = ()
class D(dict):
    pass
class DS(dict):
    __slots__ = ()
class FD(frozendict):
    pass
class I(int):
    pass
class E(Exception):
    pass
def f():
    pass
values = [Plain(), Slots(), SlotsWeak(), SlotsDict(), SubSlots(), SubSlotsEmpty(), SubWeak(), D(), DS(), FD(), I(1), E(), Exception(), f, print, len, [].append, Plain().__str__ if False else f, Plain, int, type, sys, weakref, {1}, frozenset(), object(), 1, 1.5 if False else 2, "a", b"a", bytearray(b"a"), (1,), [1], {}, frozendict(), None, True, Ellipsis, NotImplemented, range(1), slice(1), iter([]), iter(()), iter({}), {}.keys(), enumerate([]), zip(), map(f, []), filter(f, []), reversed([]), property(), staticmethod(f), classmethod(f), super(Plain, Plain()), type(sys), sys.stdout, list[int]]
for v in values:
    def attempt(v=v):
        r = weakref.ref(v)
        return r() is v
    show(attempt)
class HasDel:
    __slots__ = ("__weakref__", "x")
    def __del__(self):
        print("del", weakref.getweakrefcount(self))
h = HasDel()
r = weakref.ref(h)
del h
print(r())
for f3 in (lambda: type("A", (), {"__slots__": ("__weakref__", "__weakref__")}), lambda: type("A", (Plain,), {"__slots__": ("__weakref__",)}), lambda: type("A", (SlotsWeak,), {"__slots__": ("__weakref__",)}), lambda: type("A", (Slots,), {"__slots__": ("__weakref__",)}), lambda: type("A", (I,), {"__slots__": ("__weakref__",)}), lambda: type("A", (int,), {"__slots__": ("__weakref__",)}), lambda: type("A", (D,), {"__slots__": ("__weakref__",)}), lambda: type("A", (dict,), {"__slots__": ("__weakref__",)}), lambda: type("A", (Exception,), {"__slots__": ("__weakref__",)}), lambda: type("A", (Slots, SlotsWeak), {}), lambda: type("A", (), {"__slots__": ("__weakref__", "__dict__", "x")})):
    show(f3)
print(sorted(Plain.__dict__), sorted(Slots.__dict__), sorted(SlotsWeak.__dict__), sorted(SlotsDict.__dict__), sorted(SubSlots.__dict__), sorted(D.__dict__), sorted(DS.__dict__), sorted(FD.__dict__), sorted(I.__dict__), sorted(E.__dict__), list(Plain.__dict__), list(SlotsWeak.__dict__))
print(Plain.__weakref__, SlotsWeak.__weakref__, SubSlots.__weakref__, type(Plain.__weakref__).__name__, Plain().__weakref__, D.__weakref__, E.__weakref__, "__weakref__" in dir(Plain), "__weakref__" in dir(Plain()), "__weakref__" in dir(Slots), "__weakref__" in dir(SlotsWeak()), "__weakref__" in dir(I), "__weakref__" in dir(int))
show(lambda: Slots().__weakref__)
show(lambda: Slots.__weakref__)
show(lambda: setattr(Plain(), "__weakref__", 1))
show(lambda: delattr(Plain(), "__weakref__"))
show(lambda: I().__weakref__)
show(lambda: dir(Plain) == dir(Plain))
print(Plain.__dict__["__weakref__"].__get__(Plain()), Plain.__dict__["__weakref__"], Plain.__dict__["__dict__"], SlotsWeak.__dict__["__weakref__"])
show(lambda: Plain.__dict__["__weakref__"].__get__(1))
show(lambda: Plain.__dict__["__weakref__"].__set__(Plain(), 1))
show(lambda: SlotsWeak.__dict__["__weakref__"].__get__(Plain()))
def order(*slots, bases=(), meta=type):
    return [k for k in meta("A", bases, {"__slots__": slots}).__dict__ if k not in ("__module__", "__slots__", "__doc__")]
class M(type):
    pass
class Q(metaclass=M):
    pass
print(order("__dict__", "x"), order("__weakref__", "x"), order("__dict__", "__weakref__", "x"), order("x", "__weakref__", "__dict__"), order("__weakref__"), order("a", "z"), order("__weakref__", "x", meta=M), list(Q.__dict__))
IW = type("IW", (int,), {"__slots__": ("__weakref__",)})
class K2(I):
    __slots__ = ("__weakref__",)
class K3(K2):
    pass
print(weakref.ref(IW(1))() == 1 if False else 0, sorted(IW.__dict__), sorted(K2.__dict__))
iw = IW(5)
k2 = K2(6)
k3 = K3(7)
print(weakref.ref(iw)() == 5, weakref.ref(k2)() == 6, weakref.ref(k3)() == 7, iw.__weakref__ is not None, I(1) + 1)
show(lambda: weakref.ref(I(1)))
show(lambda: weakref.ref(type("I2", (int,), {})(1)))
show(lambda: setattr(range(1), "start", 1))
show(lambda: delattr(range(1), "start"))
show(lambda: setattr(slice(1), "step", 1))
show(lambda: range.start.__set__(range(1), 1))
show(lambda: range.start.__get__(range(5)))
show(lambda: slice.start.__get__(slice(5)))
show(lambda: range.start.__delete__(range(1)))
"""),
    ('the_order_of_clearing', SHOW + """import weakref
log = []
class Value:
    def __init__(self, n):
        self.n = n
    def __del__(self):
        log.append("value " + str(self.n))
class Target:
    __slots__ = ("a", "__weakref__", "__dict__")
    def __init__(self):
        self.a = Value("slot")
        self.b = Value("dict")
    def __del__(self):
        log.append("del, refs " + str(weakref.getweakrefcount(self)))
def cb(name):
    def callback(ref):
        log.append("cb " + name + " dead=" + str(ref() is None) + " count=" + str(len(log)))
    return callback
t = Target()
basic = weakref.ref(t)
p = weakref.proxy(t)
one = weakref.ref(t, cb("one"))
two = weakref.ref(t, cb("two"))
pcb = weakref.proxy(t, cb("proxy"))
class Sub(weakref.ref):
    pass
sub = Sub(t)
subcb = Sub(t, cb("sub"))
print(weakref.getweakrefs(t)[0] is basic, weakref.getweakrefs(t)[1] is p, [type(r).__name__ for r in weakref.getweakrefs(t)], weakref.getweakrefcount(t), weakref.getweakrefs(t)[2] is subcb, weakref.getweakrefs(t)[3] is sub, weakref.getweakrefs(t)[-1] is one)
del t
print(log, basic(), one(), two(), sub(), subcb())
log.clear()
t2 = Target()
r_kept = weakref.ref(t2, cb("kept"))
r_dropped = weakref.ref(t2, cb("dropped"))
del r_dropped
del t2
print(log)
log.clear()
t3 = Target()
class Mutates:
    def __init__(self):
        self.victim = None
    def __call__(self, ref):
        log.append("mutates: drops the other")
        self.victim = None
m = Mutates()
first = weakref.ref(t3, cb("first"))
second = weakref.ref(t3, m)
m.victim = weakref.ref(t3, cb("victim"))
third = weakref.ref(t3, cb("third"))
del t3
print(log, m.victim)
log.clear()
t4 = Target()
class Raises:
    def __call__(self, ref):
        log.append("raises")
        raise ValueError("in a callback")
kept = [weakref.ref(t4, Raises()), weakref.ref(t4, cb("after raising"))]
del t4
print(log)
log.clear()
class CbDel:
    def __del__(self):
        log.append("callback object dies")
    def __call__(self, ref):
        log.append("called")
t5 = Target()
hold = weakref.ref(t5, CbDel())
del t5
print(log, hold.__callback__)
log.clear()
t6 = Target()
gone = weakref.ref(t6, CbDel())
del gone
print(log)
log.clear()
del t6
print(log)
log.clear()
holder = []
def keep_ref(ref):
    holder.append(ref)
    log.append("kept the reference")
t7 = Target()
weakref.ref(t7, keep_ref)
print(weakref.getweakrefcount(t7))
t8 = Target()
kept8 = weakref.ref(t8, keep_ref)
del t8
print(log, holder == [kept8], holder[0]() is None)
log.clear()
def nested(ref):
    log.append("nested target dies inside a callback")
    inner.clear()
inner = [Target()]
outer = Target()
r9 = weakref.ref(outer, nested)
ri = weakref.ref(inner[0], cb("inner"))
del outer
print(log)
log.clear()
"""),
    ('resurrection', SHOW + """import weakref
keep = []
log = []
class Value:
    def __del__(self):
        log.append("value")
class R:
    def __init__(self, name):
        self.name = name
        self.v = Value()
    def __del__(self):
        log.append("del " + self.name)
        keep.append(self)
    def __repr__(self):
        return "R(" + self.name + ")"
r = R("a")
w = weakref.ref(r)
wcb = weakref.ref(r, lambda ref: log.append("callback"))
del r
print(log, w() is keep[0], wcb() is keep[0], keep, weakref.getweakrefcount(keep[0]), keep[0].name)
log.clear()
keep.clear()
print(log, w(), wcb())
log.clear()
class Once:
    count = 0
    def __del__(self):
        Once.count += 1
        keep.append(self)
o = Once()
del o
print(Once.count, len(keep))
keep.clear()
print(Once.count, len(keep))
class Twice:
    def __del__(self):
        log.append("finaliser")
        global saved
        saved = self
t = Twice()
del t
print(log, saved.__class__.__name__)
log.clear()
del saved
print(log)
class Attr:
    def __del__(self):
        self.after = "set in the finaliser"
        holder.it = self
class Holder:
    pass
holder = Holder()
a = Attr()
del a
print(holder.it.after)
del holder.it
print(hasattr(holder, "it"))
class SelfKeep:
    __slots__ = ("x", "__weakref__")
    def __del__(self):
        self.x = self
s = SelfKeep()
w = weakref.ref(s)
del s
print(w() is not None, w().x is w())
class DK(dict):
    def __del__(self):
        keep.append(self)
d = DK(a=1)
del d
print(keep, type(keep[0]).__name__)
keep.clear()
class FK(frozendict):
    def __del__(self):
        keep.append(self)
f = FK(a=1)
del f
print(keep)
keep.clear()
class IK(int):
    def __del__(self):
        keep.append(self)
i = IK(5)
del i
print(keep, keep[0] + 1)
keep.clear()
print(keep)
class EK(Exception):
    def __del__(self):
        keep.append(self)
e = EK("message")
del e
print(keep[0].args)
keep.clear()
class Container:
    def __init__(self):
        self.v = Value()
c = [R("in a list")]
c.clear()
print(keep)
keep.clear()
log.clear()
class Member:
    def __init__(self, name):
        self.name = name
    def __del__(self):
        log.append("member " + self.name)
class Outer:
    def __init__(self):
        self.m = Member("kept by the outer")
    def __del__(self):
        keep.append(self.m)
o = Outer()
del o
print(log, keep[0].name)
log.clear()
keep.clear()
print(log)
"""),
    ('a_proxy_forwards', SHOW + MASK + """import weakref, _weakref
class T:
    x = 1
    def __init__(self):
        self.y = 2
        self.items = [1, 2, 3]
    def m(self):
        return "m"
    def __str__(self):
        return "T as str"
    def __repr__(self):
        return "T!"
    def __bytes__(self):
        return b"T"
    def __add__(self, o): return ("add", o)
    def __radd__(self, o): return ("radd", o)
    def __iadd__(self, o): return ("iadd", o)
    def __sub__(self, o): return ("sub", o)
    def __rsub__(self, o): return ("rsub", o)
    def __mul__(self, o): return ("mul", o)
    def __rmul__(self, o): return ("rmul", o)
    def __matmul__(self, o): return ("matmul", o)
    def __rmatmul__(self, o): return ("rmatmul", o)
    def __truediv__(self, o): return ("truediv", o)
    def __rtruediv__(self, o): return ("rtruediv", o)
    def __floordiv__(self, o): return ("floordiv", o)
    def __rfloordiv__(self, o): return ("rfloordiv", o)
    def __mod__(self, o): return ("mod", o)
    def __rmod__(self, o): return ("rmod", o)
    def __divmod__(self, o): return ("divmod", o)
    def __rdivmod__(self, o): return ("rdivmod", o)
    def __pow__(self, o, m=None): return ("pow", o, m)
    def __rpow__(self, o, m=None): return ("rpow", o, m)
    def __lshift__(self, o): return ("lshift", o)
    def __rlshift__(self, o): return ("rlshift", o)
    def __rshift__(self, o): return ("rshift", o)
    def __rrshift__(self, o): return ("rrshift", o)
    def __and__(self, o): return ("and", o)
    def __rand__(self, o): return ("rand", o)
    def __or__(self, o): return ("or", o)
    def __ror__(self, o): return ("ror", o)
    def __xor__(self, o): return ("xor", o)
    def __rxor__(self, o): return ("rxor", o)
    def __neg__(self): return "neg"
    def __pos__(self): return "pos"
    def __abs__(self): return "abs"
    def __invert__(self): return "invert"
    def __int__(self): return 42
    def __index__(self): return 43
    def __bool__(self): return False
    def __len__(self): return 3
    def __contains__(self, k): return k == 9
    def __getitem__(self, k): return ("getitem", k)
    def __setitem__(self, k, v): self.items.append(("set", k, v))
    def __delitem__(self, k): self.items.append(("del", k))
    def __iter__(self): return iter("ab")
    def __next__(self): return "next"
    def __reversed__(self): return iter("ba")
    def __eq__(self, o): return ("eq", o)
    def __ne__(self, o): return ("ne", o)
    def __lt__(self, o): return ("lt", o)
    def __le__(self, o): return ("le", o)
    def __gt__(self, o): return ("gt", o)
    def __ge__(self, o): return ("ge", o)
    __hash__ = None
t = T()
p = weakref.proxy(t)
print(type(p), type(p).__name__, type(p).__qualname__, type(p).__module__, type(p) is weakref.ProxyType, _weakref.proxy is weakref.proxy, p.__class__ is T, isinstance(p, T), isinstance(p, weakref.ProxyType), issubclass(type(p), T), weakref.proxy(t) is p, weakref.getweakrefcount(t), weakref.getweakrefs(t) == [p] if False else 0, mask(repr(p)), str(p), bytes(p), p.x, p.y, p.m(), p.__dict__ is t.__dict__, callable(p))
print(p + 1, 1 + p, p - 1, 1 - p, p * 1, 1 * p, p @ 1, 1 @ p, p / 1, 1 / p, p // 1, 1 // p, p % 1, 1 % p, divmod(p, 1), divmod(1, p), p ** 1, 1 ** p, pow(p, 1, 2), p << 1, 1 << p, p >> 1, 1 >> p, p & 1, 1 & p, p | 1, 1 | p, p ^ 1, 1 ^ p, -p, +p, abs(p), ~p, int(p), bool(p), not p, len(p), 9 in p, 8 in p, p[1], p["k"], list(p), list(reversed(p)), next(p), p == 1, p != 1, p < 1, p <= 1, p > 1, p >= 1, 1 == p, 1 < p, [1, 2, 3][1:p] if False else 0, hex(p), [0] * 0, "ab" * 0)
q = weakref.proxy(t)
print(q is p, p + p, p - q, p == p, p < q, p[p], (t + p)[0], (t + p)[1] is p, p + t, 1 + p, (p + p)[1] is t)
pi = p
pi += 1
print(pi)
pi = p
pi -= 1
print(pi)
pi = p
pi *= 1
print(pi)
pi = p
pi /= 1
print(pi)
pi = p
pi //= 1
print(pi)
pi = p
pi %= 1
print(pi)
pi = p
pi **= 1
print(pi)
pi = p
pi <<= 1
print(pi)
pi = p
pi >>= 1
print(pi)
pi = p
pi &= 1
print(pi)
pi = p
pi |= 1
print(pi)
pi = p
pi ^= 1
print(pi)
pi = p
pi @= 1
print(pi)
p[5] = 6
del p[7]
p.z = 8
print(t.items, t.z, p.z)
del p.z
print(hasattr(t, "z"), hasattr(p, "z"), hasattr(p, "x"), getattr(p, "x"), getattr(p, "nope", "dflt"))
for f in (lambda: hash(p), lambda: {p: 1}, lambda: p.nope, lambda: setattr(p, "x"), lambda: p(), lambda: weakref.ProxyType(), lambda: weakref.ProxyType(t), lambda: weakref.CallableProxyType(t), lambda: type("S", (weakref.ProxyType,), {}), lambda: setattr(weakref.ProxyType, "x", 1), lambda: weakref.proxy(), lambda: weakref.proxy(t, None, 1), lambda: weakref.proxy(t, x=1), lambda: weakref.proxy(1), lambda: weakref.proxy([]), lambda: type(weakref.proxy(t, None)).__name__, lambda: weakref.proxy(t, None) is p, lambda: weakref.proxy(t, lambda r: 0) is p):
    show(f)
class F:
    def __call__(self, *a, **k):
        return ("called", len(a), k)
    def m(self):
        return "m"
fn = F()
c = weakref.proxy(fn)
def plain():
    return "plain"
g = weakref.proxy(plain)
print(type(c), type(c).__name__, type(c) is weakref.CallableProxyType, c(), c(1, 2), c(1, k=2), c(c)[1], callable(c), c.m(), mask(repr(c)), weakref.proxy(fn) is c, g(), type(g).__name__, g.__name__, weakref.ProxyType in weakref.ProxyTypes, weakref.CallableProxyType in weakref.ProxyTypes, weakref.ref(fn)() is fn, weakref.getweakrefcount(fn))
class NotIter:
    pass
ni = NotIter()
pn = weakref.proxy(ni)
for f in (lambda: next(pn), lambda: iter(pn), lambda: len(pn), lambda: pn[0], lambda: 1 in pn, lambda: pn + 1, lambda: 1 + pn, lambda: -pn, lambda: bytes(pn), lambda: reversed(pn), lambda: list(reversed(pn)), lambda: pn(), lambda: bool(pn), lambda: str(pn)[:9], lambda: int(pn), lambda: pn < 1, lambda: pn == ni, lambda: ni == pn, lambda: pn != ni, lambda: pn == pn):
    show(f)
del t, fn, plain, ni
dead = [p, c, g, pn]
for x in dead:
    print(mask(repr(x)), type(x).__name__)
    for f in (lambda: x.a, lambda: setattr(x, "a", 1), lambda: delattr(x, "a"), lambda: str(x), lambda: bool(x), lambda: len(x), lambda: 1 in x, lambda: x[0], lambda: x.__setitem__(0, 1), lambda: iter(x), lambda: next(x), lambda: x + 1, lambda: 1 + x, lambda: -x, lambda: x == 1, lambda: 1 == x, lambda: x(), lambda: int(x), lambda: bytes(x), lambda: reversed(x), lambda: x.__class__, lambda: isinstance(x, int), lambda: x.__dict__, lambda: hash(x)):
        show(f)
"""),
    ('what_the_library_builds', SHOW + """import weakref
class K:
    def __init__(self, n):
        self.n = n
    def __repr__(self):
        return "K" + str(self.n)
    def __hash__(self):
        return self.n
    def __eq__(self, o):
        return self.n == o.n
    def m(self):
        return "m" + str(self.n)
a, b, c = K(1), K(2), K(3)
wv = weakref.WeakValueDictionary()
wv["a"] = a
wv["b"] = b
print(type(wv).__name__, len(wv), wv["a"], wv.get("b"), wv.get("z"), "a" in wv, "z" in wv)
del b
print(len(wv), wv.get("b", "gone"), "b" in wv)
show(lambda: wv["b"])
print(wv.pop("a"), len(wv), wv.setdefault("c", c), wv.setdefault("c", K(9)), list(wv.valuerefs())[0]() is c)
wv.clear()
print(len(wv))
b = K(2)
wk = weakref.WeakKeyDictionary()
wk[a] = "A"
wk[b] = "B"
print(type(wk).__name__, len(wk), wk[a], wk.get(b), a in wk, K(1) in wk, K(9) in wk)
del b
print(len(wk), list(wk.keyrefs())[0]() is a, wk.pop(a), len(wk), wk.setdefault(c, "C"), wk.popitem(), len(wk))
b = K(2)
ws = weakref.WeakSet()
ws.add(a)
ws.add(b)
ws.add(a)
print(type(ws).__name__, len(ws), a in ws, K(2) in ws, K(9) in ws)
del b
print(len(ws))
ws.discard(a)
print(len(ws))
wm_target = K(5)
wm = weakref.WeakMethod(wm_target.m)
print(type(wm).__name__, wm()(), wm() == wm_target.m, wm == weakref.WeakMethod(wm_target.m), isinstance(wm, weakref.ref), hash(wm) == hash(wm_target.m))
del wm_target
print(wm(), wm == wm)
log = []
kr_target = K(6)
kr = weakref.KeyedRef(kr_target, lambda r: log.append(r.key), "the key")
print(kr.key, kr() is kr_target, type(kr).__name__)
del kr_target
print(log, kr.key)
log.clear()
class Sub(weakref.ref):
    __slots__ = ("extra",)
    def __new__(cls, ob, cb=None, extra=0):
        self = super().__new__(cls, ob, cb)
        self.extra = extra
        return self
    def __init__(self, ob, cb=None, extra=0):
        super().__init__(ob, cb)
    def __call__(self):
        return ("own", super().__call__())
class Named(weakref.ref):
    pass
t = K(7)
s = Sub(t, None, 5)
n = Named(t)
class M:
    def m(self):
        pass
    @staticmethod
    def st():
        pass
i, j = M(), M()
print(i.m == i.m, i.m != i.m, i.m == j.m, i.m is i.m, hash(i.m) == hash(i.m), hash(i.m) == hash(j.m), [].append == [].append, i.m == M.m, M.m == M.m, M.st == M.st, i.m == 1, {i.m: 1}[i.m], len({i.m, i.m}), print == print, [].append != [].append)
l = []
print(l.append == l.append, hash(l.append) == hash(l.append), l.append == l.extend, l.append != l.append, {l.append: 1}[l.append], len({l.append, l.append}), l.__len__ == l.__len__, "a".join == "a".join, "a".join == "b".join)
print(s.extra, s(), n() is t, n.__dict__, type(n).__name__, s == n, hash(n) == hash(t), Named(t) is n, weakref.ref(t) is n, isinstance(n, weakref.ref), weakref.getweakrefcount(t), Named.__mro__, "__weakref__" in dir(Named), "__dict__" in Named.__dict__, "__weakref__" in Named.__dict__, weakref.ref(n)() is n)
"""),
    ('finalisers_and_collections_at_exit', """import weakref
log = []
class T:
    def __del__(self):
        print("del at exit", weakref.getweakrefcount(self))
t = T()
w = weakref.ref(t, lambda r: print("callback at exit", r() is None))
k = T()
class Holder:
    pass
h = Holder()
h.t = T()
print("end of the program")
"""),
    ('a_member_descriptor', SHOW + r"""
class C:
    __slots__ = ("x", "_C__p", "__q")
    def __setattr__(self, n, v):
        print("setattr", n)
        object.__setattr__(self, n, v)
    def __delattr__(self, n):
        print("delattr", n)
        object.__delattr__(self, n)
class D(C):
    pass
class E:
    pass
d = C.__dict__["x"]
c = C()
show(lambda: d.__set__(c, 1))
show(lambda: c.x)
show(lambda: d.__get__(c))
show(lambda: d.__get__(c, C))
show(lambda: d.__get__(None, C) is d)
show(lambda: d.__get__(c, None))
show(lambda: d.__get__(None, None))
show(lambda: d.__name__)
show(lambda: d.__qualname__)
show(lambda: d.__objclass__)
show(lambda: repr(d))
show(lambda: type(d).__name__)
show(lambda: d.__delete__(c))
show(lambda: d.__get__(c))
show(lambda: c.x)
show(lambda: d.__delete__(c))
show(lambda: d.__set__(1, 1))
show(lambda: d.__get__(1))
show(lambda: d.__delete__(1))
show(lambda: d.__set__(E(), 1))
show(lambda: d.__get__(E()))
show(lambda: setattr(d, "__name__", "a"))
show(lambda: setattr(d, "__objclass__", int))
show(lambda: setattr(d, "__qualname__", "a"))
show(lambda: d.__set__(c))
show(lambda: d.__get__())
show(lambda: d.__delete__())
sub = D()
show(lambda: d.__set__(sub, 2))
show(lambda: d.__get__(sub))
show(lambda: D.x is d)
show(lambda: c.__class__.x.__get__(sub))
show(lambda: C.__dict__["_C__q"].__name__)
show(lambda: C.__dict__["_C__p"].__qualname__)
class Holder:
    __slots__ = ("v",)
class Noisy:
    def __del__(self):
        print("del noisy")
h = Holder()
Holder.v.__set__(h, Noisy())
Holder.v.__set__(h, 1)
print("replaced")
Holder.v.__set__(h, Noisy())
Holder.v.__delete__(h)
print("deleted")
show(lambda: range.start.__name__)
show(lambda: range.start.__objclass__)
show(lambda: slice.step.__qualname__)
"""),
]


def pytest_generate_tests(metafunc: Any) -> None:
    if "program" in metafunc.fixturenames:
        metafunc.parametrize("program", PROGRAMS, ids=[name for name, _ in PROGRAMS])


def test_as_cpython(program: tuple[str, str]) -> None:
    same(program[1])


if __name__ == "__main__":
    for item in PROGRAMS:
        test_as_cpython(item)
