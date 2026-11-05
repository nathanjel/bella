"""float, compiled, against CPython.

Case C-6-12 shows the behaviour by exception class, as a case must; these compare messages too, and sweep
generated values through what is easy to get nearly right: the digits and layout of repr, _Py_HashDouble,
rounding on the exact value, hex in both directions, comparison across the tower, the correctly rounded
conversions from int and between ints. The values come from a small generator in the program itself, so
that both sides see the same ones without a `random` module.
"""
from __future__ import annotations

from typing import Any

from pipeline.tests.test_review_2026_11_03 import same

SHOW = """def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e, e.args)
"""
VALUES = """state = 88172645463325252
def word():
    global state
    state ^= (state << 13) & 0xFFFFFFFFFFFFFFFF
    state ^= state >> 7
    state ^= (state << 17) & 0xFFFFFFFFFFFFFFFF
    return state
def hex13(n):
    h = hex(n)[2:]
    return "0" * (13 - len(h)) + h
def double():
    w = word()
    kind = w & 7
    w >>= 3
    sign = "-" if w & 1 else ""
    w >>= 1
    if kind == 0:                                # any bits at all, but the specials
        e = (w >> 40) % 2046 - 1022
        return float.fromhex(sign + "0x1." + hex13(w & 0xFFFFFFFFFFFFF) + "p" + str(e))
    if kind == 1:                                # subnormal
        return float.fromhex(sign + "0x0." + hex13(w & 0xFFFFFFFFFFFFF) + "p-1022")
    if kind == 2:                                # small integers
        return float(int(sign + "1") * (w % 100000))
    if kind == 3:                                # short decimals
        return int(sign + "1") * (w % 100000) / 1000
    if kind == 4:                                # halves, where rounding ties
        return int(sign + "1") * ((w % 100000) * 2 + 1) / 2
    if kind == 5:                                # near a power of two, where an int stops being exact
        e = (w >> 8) % 1000
        return float.fromhex(sign + "0x1." + hex13(w & 0xFF) + "p" + str(e))
    if kind == 6:                                # near 2**53
        return float(int(sign + "1") * (2**53 + (w % 4096) - 2048))
    return float.fromhex(sign + "0x1." + hex13(w & 0xFFFFFFFFFFFFF) + "p" + str((w >> 40) % 60 - 30))
def integer():
    w = word()
    bits = w % 1200
    n = (word() << 64) | word()
    while n.bit_length() < bits:
        n = (n << 64) | word()
    n >>= max(n.bit_length() - bits, 0)
    return -n if w & 0x10000 else n
"""

PROGRAMS: list[tuple[str, str]] = [
    ('messages', SHOW + r"""
inf, nan = float("inf"), float("nan")
big = 10**400
for f in (lambda: 1.0 / 0.0, lambda: 1.0 // 0.0, lambda: 1.0 % 0.0, lambda: divmod(1.0, 0.0), lambda: 1 / 0.0, lambda: 1 // 0.0, lambda: 1 % 0.0, lambda: 1.0 / 0, lambda: 0 ** -1, lambda: 0.0 ** -1, lambda: 0.0 ** -1.5,
          lambda: 1.0 + "a", lambda: "a" + 1.0, lambda: 1.0 - "a", lambda: 1.0 * "a", lambda: "a" * 1.0, lambda: [1] * 1.0, lambda: 1.0 * [1], lambda: 1.0 / "a", lambda: 1.0 // "a", lambda: 1.0 % "a", lambda: 1.0 ** "a", lambda: "%d" % 1 if False else 0,
          lambda: 1.0 & 1, lambda: 1 & 1.0, lambda: 1.0 | 1, lambda: 1.0 ^ 1, lambda: 1.0 << 1, lambda: 1 << 1.0, lambda: 1.0 >> 1, lambda: ~1.0, lambda: 1.0 @ 1.0, lambda: 1 @ 1.0,
          lambda: big + 1.0, lambda: 1.0 + big, lambda: big * 1.0, lambda: big / 1.0, lambda: 1.0 / big, lambda: big // 1.0, lambda: big % 1.0, lambda: big ** 1.0, lambda: 1.0 ** big, lambda: divmod(big, 1.0),
          lambda: big / 1, lambda: 2**1024 / 1, lambda: 10**400 / 3, lambda: 1 / 0, lambda: big / 0, lambda: True / False,
          lambda: 2.0 ** 1e10, lambda: 10.0 ** 400, lambda: (-10.0) ** 401, lambda: big ** -1, lambda: 2 ** -big,
          lambda: pow(2.0, 3.0, 5), lambda: pow(2, 3.0, 5), lambda: pow(2, 3, 5.0), lambda: pow(2.0, 3, 5), lambda: pow(1.5, "a"), lambda: pow("a", 1.5), lambda: pow(2.0, 3, None), lambda: pow(1.5, 2, "a"),
          lambda: divmod(1.0, "a"), lambda: divmod("a", 1.0), lambda: 1.0 < "a", lambda: "a" < 1.0, lambda: 1.0 >= None, lambda: 1 < "a"):
    show(f)
for f in (lambda: float(big), lambda: float(2**1024), lambda: float(2**1024 - 2**970), lambda: float(-(2**1024)), lambda: float(None), lambda: float([]), lambda: float({}), lambda: float(object()), lambda: float(1, 2), lambda: float(x=1), lambda: float(1, x=2), lambda: float(print), lambda: float(float),
          lambda: float(""), lambda: float(" "), lambda: float("a"), lambda: float("1a"), lambda: float("1__0"), lambda: float("_1"), lambda: float("1_"), lambda: float("1e"), lambda: float("--1"), lambda: float("0x10"), lambda: float("\x001"), lambda: float("1\x00"), lambda: float("a" * 500),
          lambda: float(b""), lambda: float(b"a"), lambda: float(bytearray(b"a")), lambda: float(b"1_"), lambda: float(b"\xff"), lambda: float(b"1\x00"),
          lambda: float.__new__(), lambda: float.__new__(int), lambda: float.__new__(1), lambda: float.__new__(float, 1, 2), lambda: float.__new__(float, x=1), lambda: float.__new__(bool), lambda: float.from_number(), lambda: float.from_number(1, 2), lambda: float.from_number("1.5"), lambda: float.from_number(None),
          lambda: int(inf), lambda: int(-inf), lambda: int(nan), lambda: round(inf), lambda: round(-inf), lambda: round(nan), lambda: inf.__trunc__(), lambda: nan.__trunc__(), lambda: inf.__floor__(), lambda: nan.__ceil__(), lambda: int("1.5"), lambda: int(1.5, 10), lambda: int(1.5, base=10),
          lambda: inf.as_integer_ratio(), lambda: nan.as_integer_ratio(), lambda: round(1.7976931348623157e308, -308), lambda: round(1.5, 1.5), lambda: round(1.5, "a"), lambda: (1.5).__round__(1, 2), lambda: (1.5).__round__(x=1), lambda: round(1.5, 2**70), lambda: round(1.5, -(2**70)),
          lambda: float.fromhex(""), lambda: float.fromhex("x"), lambda: float.fromhex("0x"), lambda: float.fromhex("0x1p"), lambda: float.fromhex("1 2"), lambda: float.fromhex("infx"), lambda: float.fromhex("\xe9"), lambda: float.fromhex("0x1p1024"), lambda: float.fromhex("0x2p1023"), lambda: float.fromhex("0x1.fffffffffffff8p1023"), lambda: float.fromhex("0x1p99999999999999999999"), lambda: float.fromhex(1), lambda: float.fromhex(b"1"), lambda: float.fromhex(), lambda: float.fromhex("1", "2"), lambda: float.fromhex(x="1"),
          lambda: (1.5).hex(1), lambda: (1.5).hex(x=1), lambda: (1.5).is_integer(1), lambda: (1.5).as_integer_ratio(1), lambda: (1.5).conjugate(1), lambda: (1.5).__trunc__(1), lambda: (1.5).__floor__(1), lambda: (1.5).__ceil__(1), lambda: (1.5).__getnewargs__(1), lambda: (1.5).__format__(), lambda: (1.5).__format__(1), lambda: (1.5).__format__("a", "b"), lambda: float.__getformat__("x"), lambda: float.__getformat__(1), lambda: float.__getformat__("a\0"), lambda: float.__getformat__(),
          lambda: float.hex(1), lambda: float.is_integer("a"), lambda: float.__add__(1, 2), lambda: float.__add__(1.5), lambda: float.__add__(1.5, 1, 2), lambda: float.__neg__(1), lambda: float.__neg__(1.5, 2), lambda: float.__pow__(1.5), lambda: float.__pow__(1.5, 2, 3), lambda: float.__pow__(1.5, 2, 3, 4), lambda: float.__rpow__(1.5, 2, 3), lambda: float.__repr__(1), lambda: float.__hash__(1), lambda: float.__eq__(1, 1.0), lambda: float.__divmod__(1.5), lambda: float.__divmod__(1.5, "a"), lambda: float.__rdivmod__(1.5, "a"), lambda: float.real.__get__(1), lambda: float.real.__set__(1.5, 1), lambda: float.real.__delete__(1.5),
          lambda: setattr(1.5, "x", 1), lambda: setattr(1.5, "real", 1), lambda: delattr(1.5, "real"), lambda: delattr(1.5, "x"), lambda: (1.5).x, lambda: float.x, lambda: setattr(float, "x", 1), lambda: (1.5,)[0](), lambda: iter(1.5), lambda: len(1.5), lambda: (1.5,)[0][0], lambda: chr(1.5), lambda: hex(1.5), lambda: oct(1.5), lambda: bin(1.5), lambda: bytes(1.5), lambda: bytearray(1.5), lambda: list(1.5), lambda: tuple(1.5), lambda: set(1.5), lambda: dict(1.5), lambda: str(1.5, "a"), lambda: list((0,))[1.5], lambda: list((0, 1))[0.0:1.0], lambda: "a"[1.5], lambda: b"a"[1.5], lambda: (1,)[1.5], lambda: {}[1.5], lambda: int.from_bytes(1.5), lambda: (1).to_bytes(1.5), lambda: slice(1.5).indices(2), lambda: range(1.5), lambda: range(0, 1.5), lambda: range(0, 1, 1.5), lambda: type("X", (float, int), {}), lambda: type("X", (float,), {"__slots__": ("a",)})(1.5).a, lambda: object.__new__(type("X", (float,), {})), lambda: ord(1.5), lambda: sum(1.5), lambda: min(1.5), lambda: max(1.5), lambda: sorted(1.5), lambda: abs("a"), lambda: round("a"), lambda: hash([1.5]), lambda: (1.0).real.x):
    show(f)
"""),
    ('values', VALUES + r"""
for i in range(4000):
    x = double()
    print(repr(x), hash(x), x.hex(), float.fromhex(x.hex()) == x, float(repr(x)) == x, float(str(x)) == x, x.is_integer(), x.__trunc__() if x == x and abs(x) < 1e30 else 0, x.__floor__() if abs(x) < 1e30 else 0, x.__ceil__() if abs(x) < 1e30 else 0, round(x) if abs(x) < 1e30 else 0, x.as_integer_ratio())
"""),
    ('rounding', VALUES + r"""
for i in range(3000):
    x = double()
    n = word() % 40 - 20
    print(repr(x), n, repr(round(x, n)), repr(round(x, n + 300)), repr(round(x, n - 280)) if abs(x) < 1e300 else 0)
for x in (0.5, 1.5, 2.5, 3.5, -0.5, -1.5, 5.0, 15.0, 25.0, 35.0, 45.0, 55.0, 95.0, 995.0, 5e22, 15e22, 25e22, 1e22, 1e23, 5e23):
    for n in (0, 1, 2, -1, -2, -3, -22, -23, -24):
        print(x, n, repr(round(x, n)), repr(round(-x, n)))
"""),
    ('arithmetic', VALUES + r"""
for i in range(3000):
    x, y = double(), double()
    print(repr(x + y), repr(x - y), repr(x * y), repr(x / y) if y else 0, repr(x // y) if y else 0, repr(x % y) if y else 0, repr(divmod(x, y)) if y else 0, x < y, x == y)
    try:
        print(repr(abs(x) ** (y / 1e300 if abs(y) > 1e3 else y)))
    except (OverflowError, ZeroDivisionError) as e:
        print(type(e).__name__, e, e.args)
    try:
        print(repr(x ** float(int(y % 50))))
    except (OverflowError, ZeroDivisionError) as e:
        print(type(e).__name__, e, e.args)
"""),
    ('the_tower', VALUES + r"""
def attempt(f):
    try:
        return repr(f())
    except (OverflowError, ZeroDivisionError) as e:
        return type(e).__name__
for i in range(4000):
    n, m = integer(), integer()
    x = double()
    print(attempt(lambda: float(n)), attempt(lambda: n / m), n == x, n < x, n > x, n <= x, x == n, x < n, x > n, attempt(lambda: x + n), attempt(lambda: n * x))
for shift in range(50, 80):
    for delta in (-3, -2, -1, 0, 1, 2, 3):
        n = 2**shift + delta * 2**(shift - 54)
        x = float(n)
        print(repr(x), x == n, x < n, x > n, hash(x) == hash(n), int(x) == n, repr(n / 1), repr(n / 3), repr(3 / n), repr(-n / 7))
for n in (2**1023, 2**1024 - 2**971, 2**1024 - 2**970 - 1, 2**1024 - 2**970, 2**1024 - 1, 2**1024):
    print(attempt(lambda: float(n)), attempt(lambda: n / 1), attempt(lambda: 2 * n / 2), attempt(lambda: -n / 1))
for e in range(1060, 1080):
    for k in (1, 2, 3, 5, 7):
        print(e, k, repr(k / 2**e), repr(-k / 2**e), repr((k * 2**e + 1) / 2**(2 * e)))
"""),
    ('parsing', SHOW + r"""
for s in ("1e400", "-1e400", "1e-400", "-1e-400", "1e308", "1.8e308", "1.7976931348623157e308", "1.7976931348623158e308", "1.7976931348623159e308", "2.2250738585072014e-308", "2.2250738585072011e-308", "4.9406564584124654e-324", "2.4703282292062327e-324", "2.4703282292062328e-324", "1e-323", "3e-324", "2e-324",
          "1" + "0" * 308, "1" + "0" * 309, "0." + "0" * 400 + "1", "0." + "0" * 300 + "1", "1" + "0" * 400 + "e-400", "0." + "0" * 400 + "1e400", "." + "0" * 400 + "1e401", "000000000000000000000000000000001", "0.000000000000000000000000000000000", "0e400", "0e-400", "-0e400",
          "1e+0", "1e-0", "1e00000000000000000000000001", "1e-00000000000000000000000001", "1E1", "1.E1", ".1E1", "1_0_0", "1_0_0.0_0_1", "1_0e0_1", "1.5_5e1_0",
          "\t 1\n", "\v1\f", "\r1\r", " 1 ", "  -1.5  ", "+ 1", "- 1", "1 .5", "1. 5", "1e 5", "infinity ", " infinity", " nan ", "+Infinity", "-iNfInItY", "iNf", "nAn", "-NaN", "+NAN", "1e5.5", "1.5e", "1.5e+", "1.5e-", "e", "E5", ".e5", "+.", "-.", "+.e5", "0_0", "0_", "_0", "0__0", "0_.0", "0._0", "0e_0", "0e0_", "0_e0"):
    show(lambda: float(s))
class I(int):
    def __float__(self):
        return 6.5
    def __index__(self):
        return 7
class J(int):
    pass
class Both:
    __float__ = None
    def __index__(self):
        return 3
class IndexOnly:
    def __index__(self):
        return 2**2000
class BadIndex:
    def __index__(self):
        return 1.5
class FF(float):
    pass
class ReturnsSub:
    def __float__(self):
        return True
show(lambda: float(I(3)))
show(lambda: float(J(3)))
show(lambda: float(Both()))
show(lambda: float(IndexOnly()))
show(lambda: float(BadIndex()))
show(lambda: float(FF(1.5)))
show(lambda: float(ReturnsSub()))
show(lambda: float.from_number(I(3)))
show(lambda: float.from_number(J(3)))
show(lambda: float.from_number(Both()))
show(lambda: float.from_number(IndexOnly()))
show(lambda: FF.from_number(1))
show(lambda: FF.fromhex("1"))
show(lambda: float.__new__(FF, "1.5"))
show(lambda: type(float.__new__(FF, "1.5")).__name__)
"""),
    ('a_subclass', SHOW + r"""
class F(float):
    def __new__(cls, *a):
        print("new", a)
        return float.__new__(cls, *a)
    def __init__(self, *a):
        print("init", a)
    def __del__(self):
        print("del", float.__repr__(self))
    def __str__(self):
        return "as str"
    def __format__(self, spec):
        return "formatted " + spec
    def __getattr__(self, n):
        return "got " + n
    def __truediv__(self, o):
        return "div"
    def __rtruediv__(self, o):
        return "rdiv"
    def __floordiv__(self, o):
        return NotImplemented
    def __rfloordiv__(self, o):
        return NotImplemented
    def __mod__(self, o):
        return "mod"
    def __sub__(self, o):
        return float.__sub__(self, o) + 100
    def __rsub__(self, o):
        return super().__rsub__(o) + 200
    def __mul__(self, o):
        return super().__mul__(o)
    def __ne__(self, o):
        return "ne"
    def __ge__(self, o):
        return "ge"
    def __le__(self, o):
        return "le"
    def __trunc__(self):
        return "trunc"
    def __floor__(self):
        return "floor"
    def __ceil__(self):
        return "ceil"
    def hex(self):
        return "hex"
    def __pos__(self):
        return "pos"
    def __hash__(self):
        return super().__hash__() + 1
    def __eq__(self, o):
        return super().__eq__(o)
    def __lt__(self, o):
        return super().__lt__(o)
f = F(1.5)
print(str(f), f"{f}", f"{f:x}", format(f, "y"), repr(f), f.nothing, f / 1, 1 / f, 1.0 / f, f % 1, f - 1, 1 - f, 1.0 - f, f * 2, 2 * f, 2.0 * f, f != 1, 1 != f, f >= 1, 1 <= f, f <= 1, 1 >= f, f.hex(), float.hex(f), +f, -f, abs(f), hash(f), f == 1.5, 1.5 == f, f < 2, 2 > f, 2.0 > f)
show(lambda: f // 1)
show(lambda: 1 // f)
show(lambda: 1.0 // f)
print(float(f), int(f), bool(f), round(f), round(f, 1), f.real, f.imag, f.conjugate(), f.__float__(), f.is_integer(), f.as_integer_ratio())
g = F()
del g
f.x = 1
print(f.__dict__, f.x, vars(f), "x" in dir(f), f.__class__.__name__, type(f).__mro__[1].__name__)
del f
class Slotted(float):
    __slots__ = ("a", "b")
s = Slotted(1.5)
s.a = 1
print(s.a, s.b if hasattr(s, "b") else "none", s + 1, repr(s))
show(lambda: s.__dict__)
show(lambda: setattr(s, "c", 1))
class Sl2(float):
    __slots__ = ("__weakref__",)
class Sl3(float):
    __slots__ = ("__dict__",)
import weakref
w = Sl2(1.5)
show(lambda: weakref.ref(w)() == 1.5)
show(lambda: weakref.ref(1.5))
show(lambda: weakref.ref(F(1.5)) is None)
print(sorted(Sl2.__dict__), sorted(Sl3.__dict__), sorted(Slotted.__dict__))
class Meta(type):
    pass
class M(float, metaclass=Meta):
    pass
print(M(1.5), type(M(1.5)).__name__, M(1.5) + 1)
class Both1(F, float):
    pass
show(lambda: type(Both1(1.5)).__name__)
print("end")
"""),
    ('sum', SHOW + r"""
class G(float):
    pass
class I(int):
    pass
class Add:
    def __radd__(self, o):
        return ("radd", o)
    def __add__(self, o):
        return ("add", o)
big = 2**70
huge = 10**400
print(sum([0.1] * 10), sum([0.1] * 1000), sum([1e100, 1.0, -1e100, 1e-100]), sum([1e308, 1e308, -1e308]), sum([1.0, 1e100, 1.0, -1e100]), sum([1e16, 1.0, 1.0]), sum([1.0, 1.0, 1e16]))
print(sum([0.1, 0.2, 0.3], 0), sum([0.1, 0.2, 0.3], 0.0), sum([0.1, 0.2, 0.3], 1), sum([1, 2, 0.1, 0.2, 0.3]), sum([True, 0.1, 0.2, 0.3]), sum([0.1, 0.2, 0.3, True]), sum([I(1), 0.1, 0.2, 0.3]), sum([0.1, I(1), 0.2, 0.3]), sum([0.1, 0.2, G(0.3)]), sum([0.1, G(0.2), 0.3]), sum([G(0.1), 0.2, 0.3]), sum([0.1, 0.2, 0.3], G(0.0)), type(sum([0.1], G(0.0))).__name__, type(sum([], G(0.0))).__name__)
print(sum([big, 0.1, 0.2, 0.3]), sum([0.1, big, 0.2, 0.3]), sum([2**62, 2**62, 2**62, 0.1, 0.2, 0.3]), sum([2**63 - 1, 1, 0.1, 0.2, 0.3]), sum([0.1, 2**63, 0.2, 0.3]), sum([0.1, 2**63 - 1, 0.2, 0.3]), sum([0.1, -(2**63), 0.2, 0.3]), sum([0.1, -(2**63) - 1, 0.2, 0.3]), sum([1, 2**63 - 1]), sum([-1, -(2**63)]), sum([2**63]), sum([2**63, 1]), sum([], 2**63), sum([1], 2**63), sum([1], -(2**63) - 1))
print(sum([0.1, Add()]), sum([Add()], 1.5), sum([1, Add()]), sum([], Add()) is not None)
show(lambda: sum([Add(), 0.1]))
print(sum([float("inf"), float("-inf")]), sum([float("inf"), 1.0]), sum([float("nan"), 1.0]), sum([1e308, 1e308]), sum([-1e308, -1e308]), sum([1e308, 1e308, float("-inf")]), sum([-0.0]), sum([-0.0], -0.0), sum([-0.0, -0.0], -0.0), sum([0.0, -0.0], -0.0), sum([], -0.0), sum((x for x in [1.5]) if False else [1.5]))
show(lambda: sum([1.5, "a"]))
show(lambda: sum(["a"], 1.5))
show(lambda: sum([huge], 1.5))
show(lambda: sum([1.5, huge]))
show(lambda: sum([1.5], "a"))
show(lambda: sum(1.5))
show(lambda: sum([1.5], b"a"))
"""),
    ('constants_and_identity', SHOW + r"""
def f():
    return 1.5
def g():
    return 1.5
x = 1.5
y = 1.5
print(x is y, f() is f(), x == f(), f() == g(), (1.5, 1.5)[0] is (1.5, 1.5)[1], 0.0 is 0.0, 0.0 == -0.0, repr(-0.0), repr(0.0), (0.0, -0.0), 1e999, -1e999, 1e-999, -1e-999, 1_000.5, .5, 5., 1e3, 1E3, 0e0, 00.5, 0.1e1, 1.e1, 1_0.0_1e1_0, (1.5, (2.5, "a")), ((0.0,), (0.0,)), [1.5, 2.5][0], {1.5: 2.5}, {1.5, 2.5} == {2.5, 1.5})
a = 1.5
b = a
a += 1
print(a, b, a is b)
def d(p=1.5, *, q=-2.5):
    return p, q
print(d(), d.__defaults__, d.__kwdefaults__)
class C:
    z = 2.5
    def m(self, p=3.5):
        return p
print(C.z, C().z, C().m(), C.m.__defaults__)
print(f"{1.5}", f"{1.5!r}", f"{1.5!s}", f"{-0.0}", f"{1e100}", "a" + str(1.5), str(1.5) + "a", [str(1e16)], str(1e22), repr(1e21), repr(1e-4), repr(1e-5))
print(int(1.9), int(-1.9), int(1e20), int(2.0**70), bool(0.5), str(0.5), float(int(1.5)), round(1.5) + 1, round(1.5, 0) + 1, 3 * 1.5, 1.5 * 3, 7 / 2, -7 / 2, 7 // 2, 7.0 // 2, -7.0 // 2, 7 % 2.5, -7 % 2.5, 2**-1, 2.0**-1, (-2)**-1, 10**-2, 1 / 3)
print(type(1 / 1).__name__, type(2**-1).__name__, type(1.0 + 1).__name__, type(1 + 1.0).__name__, type(True + 1.0).__name__, type(True / True).__name__, type(round(1.5)).__name__, type(round(1.5, 1)).__name__, type(abs(-1.5)).__name__, type(divmod(1.5, 1)[0]).__name__, type(float(1)).__name__, type(sum([1.5])).__name__, type(max(1, 1.5)).__name__, type(pow(2, -1)).__name__, type(pow(2.0, 1)).__name__)
print(isinstance(1.5, (int, float)), isinstance(1.5, object), float in float.__mro__, type(1.5) is float, 1.5.__class__ is float, 1.5.__class__.__name__, float.__doc__ is not None, callable(1.5), hasattr(1.5, "real"), hasattr(1.5, "x"), getattr(1.5, "real"), getattr(1.5, "x", 2.5))
print(list(map(float, ["1", "2.5"])), sorted([3.5, 1, 2.5, 2]), sorted([3.5, 1, 2.5], reverse=True), sorted([0.0, -0.0, 0]), sorted([-0.0, 0.0, 0]), sorted(["b", "a"], key=lambda s: 1.5), max([1.5, 2.5], key=lambda v: -v), min(1.5, 2.5), list(reversed([1.5, 2.5])), [1.5] * 2, (1.5,) * 2, [1.5] + [2.5], tuple([1.5]), set([1.5]), frozenset([1.5]), dict(a=1.5), {"a": 1.5}["a"], list({1.5: 1}), enumerate([1.5]).__next__(), list(zip([1.5], [2.5])), any([0.0, 1.5]), all([0.0, 1.5]), any([0.0]), all([1.5]))
n = float("nan")
print(sorted([n, 1.0]) == sorted([n, 1.0]), n in [n], n in (n,), n in {n}, {n: 1}[n], [n].count(n), [n].index(n), (n,).count(n), (n,).index(n), n is n, [n] == [n], (n,) == (n,), {n: 1} == {n: 1}, {n} == {n}, float("nan") in [n], max(n, 1.0) is n, min(1.0, n) == 1.0, hash(n) == hash(n), hash(n) == hash(float("nan")))
print((1, 2).index(2), (1, 2).index(2.0), (1, 2, 1).count(1), (1, 2, 1).index(1, 1), (1, 2, 1).index(1, -1), (1, 2, 1).index(1, 0, 1), (1, 2).index(2, -100, 100), (1, 2).index(1, True), () .count(1)) if False else print(0)
show(lambda: (1, 2).index(3))
show(lambda: (1, 2).index(1, 1))
show(lambda: (1, 2).index())
show(lambda: (1, 2).count())
show(lambda: (1, 2).count(1, 2))
show(lambda: (1, 2).index(1, 1.5))
show(lambda: (1, 2).index(1, 0, "a"))
show(lambda: (1, 2).index(1, None))
show(lambda: (1, 2, 1).index(1, 1))
show(lambda: (1, 2, 1).index(1, -1))
show(lambda: (1, 2, 1).index(1, 0, 1))
show(lambda: (1, 2).index(2, -100, 100))
show(lambda: (1, 2).index(2, 2**70))
show(lambda: (1, 2).index(2, -(2**70), 2**70))
show(lambda: (1, 2, 1).count(1))
show(lambda: (1, 2, 1).count(1.0))
show(lambda: tuple.count((1,), 1))
show(lambda: tuple.index([1], 1))
"""),
    ('what_has_a_name', SHOW + r"""
class P:
    pass
class S:
    __slots__ = ("a",)
for d in (float.__dict__["real"], float.__dict__["imag"], int.__dict__["real"], P.__dict__["__dict__"], P.__dict__["__weakref__"], range.__dict__["start"], slice.__dict__["start"], type(iter({}.keys())) if False else float.__dict__["real"]):
    print(repr(d), d.__name__, d.__qualname__, d.__objclass__.__name__)
show(lambda: setattr(float.__dict__["real"], "__name__", "x"))
show(lambda: delattr(float.__dict__["real"], "__objclass__"))
show(lambda: setattr(float.__dict__["real"], "__qualname__", "x"))
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
