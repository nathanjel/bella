# clause: C-9-10
# spec: section 9
# status: P1
# source: dialect specification section 9, Objects/weakrefobject.c, Modules/_weakref.c
"""Weak references as objects: which are shared, the order of an object's list and of its callbacks, what
a reference that dies first does, what can be referred to at all, __weakref__ on a class, a subclass of
ref, a proxy's forwarding, and a finaliser that keeps its object. C-9-03 and C-9-04 show the order of
disposal; this needs no collector."""
# ruff: noqa: B018, E721, E742, F821, RUF015, PLR0124, UP037
import _weakref
import weakref


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


class C:
    def m(self) -> str:
        return "method"


c = C()
r = weakref.ref(c)
print(r() is c, weakref.ref(c) is r, weakref.ReferenceType is weakref.ref, _weakref.ref is weakref.ref, type(r).__name__, type(r).__module__, r.__callback__, callable(r), weakref.getweakrefcount(c), weakref.getweakrefs(c) == [r], c.__weakref__ is r, hash(r) == hash(c), r == weakref.ref(c), r != r, r == 1)  # type: ignore[attr-defined]
log: list[str] = []


def cb(name: str) -> object:
    def callback(ref: object) -> None:
        log.append(name + " dead=" + str(ref() is None))  # type: ignore[operator]
    return callback


first = weakref.ref(c, cb("first"))  # type: ignore[arg-type]
second = weakref.ref(c, cb("second"))  # type: ignore[arg-type]
none = weakref.ref(c, None)
print(first is r, second is first, none is r, first.__callback__ is not None, weakref.getweakrefs(c) == [r, second, first], first == r)
gone = weakref.ref(c, cb("gone"))  # type: ignore[arg-type]
del gone
del c
print(log, r(), first(), first.__callback__, first == second, first == first, first != second, hash(r) == hash(r), failed(lambda: hash(first)), failed(lambda: hash(weakref.ref(C()))))
log.clear()


# ---- what can be referred to
class Slots:
    __slots__ = ("x",)


class SlotsWeak:
    __slots__ = ("x", "__weakref__")


class SubSlots(Slots):
    pass


class EmptySlots(Slots):
    __slots__ = ()


class D(dict[str, int]):
    pass


class I(int):
    pass


class IW(int):
    __slots__ = ("__weakref__",)


class E(Exception):
    pass


def f() -> None:
    pass


print(failed(lambda: weakref.ref(C())), failed(lambda: weakref.ref(Slots())), failed(lambda: weakref.ref(SlotsWeak())), failed(lambda: weakref.ref(SubSlots())), failed(lambda: weakref.ref(EmptySlots())), failed(lambda: weakref.ref(D())), failed(lambda: weakref.ref(I(1))), failed(lambda: weakref.ref(IW(1))), failed(lambda: weakref.ref(E())), failed(lambda: weakref.ref(Exception())))
print(failed(lambda: weakref.ref(f)), failed(lambda: weakref.ref(print)), failed(lambda: weakref.ref(C)), failed(lambda: weakref.ref(int)), failed(lambda: weakref.ref(weakref)), failed(lambda: weakref.ref({1})), failed(lambda: weakref.ref(frozenset())), failed(lambda: weakref.ref(C().m)), failed(lambda: weakref.ref([].append)))
print(failed(lambda: weakref.ref(object())), failed(lambda: weakref.ref(1)), failed(lambda: weakref.ref(2**64)), failed(lambda: weakref.ref("a")), failed(lambda: weakref.ref(b"a")), failed(lambda: weakref.ref((1,))), failed(lambda: weakref.ref([1])), failed(lambda: weakref.ref({})), failed(lambda: weakref.ref(frozendict())), failed(lambda: weakref.ref(None)), failed(lambda: weakref.ref(True)), failed(lambda: weakref.ref(range(1))), failed(lambda: weakref.ref(iter([]))))
print(failed(lambda: type("A", (), {"__slots__": ("__weakref__", "__weakref__")})), failed(lambda: type("A", (C,), {"__slots__": ("__weakref__",)})), failed(lambda: type("A", (Slots,), {"__slots__": ("__weakref__",)})), failed(lambda: type("A", (int,), {"__slots__": ("__weakref__",)})), failed(lambda: type("A", (Slots, SlotsWeak), {})))
print(sorted(C.__dict__), sorted(Slots.__dict__), sorted(SlotsWeak.__dict__), sorted(SubSlots.__dict__), sorted(EmptySlots.__dict__), sorted(I.__dict__), list(SlotsWeak.__dict__)[-3:], "__weakref__" in dir(C), "__weakref__" in dir(Slots), C().__weakref__, failed(lambda: Slots().__weakref__), failed(lambda: setattr(C(), "__weakref__", 1)))  # type: ignore[attr-defined]


# ---- a list's order, seen from callbacks and from getweakrefs
class Sub(weakref.ref[object]):
    __slots__ = ("extra",)

    def __new__(cls, ob: object, callback: object = None, extra: int = 0) -> "Sub":
        self = super().__new__(cls, ob, callback)  # type: ignore[arg-type]
        self.extra = extra  # type: ignore[attr-defined]
        return self

    def __init__(self, ob: object, callback: object = None, extra: int = 0) -> None:
        super().__init__(ob, callback)  # type: ignore[call-arg]


class Named(weakref.ref[object]):
    pass


t = C()
basic = weakref.ref(t)
proxy = weakref.proxy(t)
one = weakref.ref(t, cb("one"))  # type: ignore[arg-type]
sub = Sub(t, None, 5)
subcb = Sub(t, cb("subcb"))
named = Named(t)
print([type(x).__name__ for x in weakref.getweakrefs(t)], weakref.getweakrefcount(t), weakref.getweakrefs(t)[0] is basic, sub.extra, sub() is t, named() is t, Named(t) is named, sub == basic, isinstance(sub, weakref.ref), named.__dict__, Named.__mro__[1] is weakref.ref, weakref.ref(named)() is named)  # type: ignore[attr-defined]
del t
print(log, basic(), sub(), named(), one())
log.clear()


# ---- a proxy
class T:
    x = 1

    def __init__(self) -> None:
        self.y = 2

    def __add__(self, o: object) -> str:
        return "add"

    def __radd__(self, o: object) -> str:
        return "radd"

    def __iadd__(self, o: object) -> str:
        return "iadd"

    def __neg__(self) -> str:
        return "neg"

    def __bool__(self) -> bool:
        return False

    def __len__(self) -> int:
        return 3

    def __contains__(self, k: object) -> bool:
        return k == 9

    def __getitem__(self, k: object) -> str:
        return "getitem"

    def __iter__(self) -> object:
        return iter("ab")

    def __str__(self) -> str:
        return "as str"

    def __eq__(self, o: object) -> bool:
        return True

    __hash__ = None  # type: ignore[assignment]


class F:
    def __call__(self, *a: object) -> int:
        return len(a)


target = T()
p = weakref.proxy(target)
fn = F()
pc = weakref.proxy(fn)
print(type(p).__name__, type(p).__module__, type(p) is weakref.ProxyType, type(pc) is weakref.CallableProxyType, weakref.proxy(target) is p, p.__class__ is T, isinstance(p, T), p.x, p.y, p + 1, 1 + p, -p, bool(p), len(p), 9 in p, p[1], list(p), str(p), p == 1, pc(1, 2), callable(pc), callable(p))
pi = p
pi += 1
p.z = 8
print(pi, target.z, p.z, hasattr(p, "nope"))  # type: ignore[attr-defined]
del p.z
print(hasattr(target, "z"), failed(lambda: hash(p)), failed(lambda: p()), failed(lambda: weakref.ProxyType(target)), failed(lambda: type("S", (weakref.ProxyType,), {})), failed(lambda: next(p)), failed(lambda: weakref.proxy(1)))  # type: ignore[call-arg]
del target, fn
print(failed(lambda: p.x), failed(lambda: setattr(p, "x", 1)), failed(lambda: str(p)), failed(lambda: bool(p)), failed(lambda: len(p)), failed(lambda: p + 1), failed(lambda: 1 + p), failed(lambda: p == 1), failed(lambda: pc()), failed(lambda: isinstance(p, int)), failed(lambda: hash(p)), type(p).__name__)


# ---- resurrection
keep: list[object] = []


class Value:
    def __del__(self) -> None:
        log.append("value")


class R:
    def __init__(self) -> None:
        self.v = Value()

    def __del__(self) -> None:
        log.append("del")
        keep.append(self)


o = R()
w = weakref.ref(o)
wc = weakref.ref(o, cb("callback"))  # type: ignore[arg-type]
del o
print(log, w() is keep[0], wc() is keep[0], weakref.getweakrefcount(keep[0]))
log.clear()
keep.clear()
print(log, w(), wc())
log.clear()


class Keeps(dict[str, int]):
    def __del__(self) -> None:
        keep.append(self)


class KeepsInt(int):
    def __del__(self) -> None:
        keep.append(self)


k1 = Keeps(a=1)
del k1
k2 = KeepsInt(5)
del k2
print(keep, type(keep[0]).__name__)
keep.clear()
print(keep)

# ---- what the library builds
wv: weakref.WeakValueDictionary[str, C] = weakref.WeakValueDictionary()
a, b = C(), C()
wv["a"] = a
wv["b"] = b
wk: weakref.WeakKeyDictionary[C, str] = weakref.WeakKeyDictionary()
wk[a] = "A"
wk[b] = "B"
ws: weakref.WeakSet[C] = weakref.WeakSet()
ws.add(a)
ws.add(b)
print(len(wv), len(wk), len(ws), wv["a"] is a, wk[a], a in ws, "a" in wv, b in wk)
del b
print(len(wv), len(wk), len(ws), failed(lambda: wv["b"]), wv.get("b", "gone"))


class M:
    def m(self) -> str:
        return "m"


inst = M()
wm = weakref.WeakMethod(inst.m)
print(wm()(), wm() == inst.m, wm == weakref.WeakMethod(inst.m), inst.m == inst.m, hash(inst.m) == hash(inst.m), inst.m == M().m, type(wm).__name__)  # type: ignore[misc]
del inst
print(wm(), wm == wm)
d = {"live": weakref.ref(C), "dead": weakref.ref(C())}
_weakref._remove_dead_weakref(d, "live")  # type: ignore[attr-defined]
_weakref._remove_dead_weakref(d, "dead")  # type: ignore[attr-defined]
_weakref._remove_dead_weakref(d, "absent")  # type: ignore[attr-defined]
print(sorted(d), failed(lambda: _weakref._remove_dead_weakref({"k": 1}, "k")), failed(lambda: _weakref._remove_dead_weakref(None, "k")))  # type: ignore[attr-defined]
