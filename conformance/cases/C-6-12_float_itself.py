# clause: C-6-12
# spec: section 6
# status: P1
# source: dialect specification section 6, Objects/floatobject.c, Objects/longobject.c (long_true_divide, PyLong_AsDouble), Python/bltinmodule.c (sum)
"""float as a type: arithmetic with its signs and specials, division and power with ints, comparison and hash
across the tower, repr, parsing with its spellings, rounding, hex, a subclass, and sum's compensation."""
# ruff: noqa: B002, B015, B018, B023, B033, E721, PLR0124, RUF015, RUF069, FURB157, UP003, UP018, UP037
inf = float("inf")
nan = float("nan")
BIG = 2**70
HUGE = 10**400


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


# ---- repr: where it changes to an exponent, and the shortest digits
for x in (0.0, -0.0, 1.0, -1.0, 0.1, 0.2, 0.1 + 0.2, 1.5, 100.0, 1e15, 1e16, 1.5e16, 1e22, 1e23, 1e100, 1.7976931348623157e308, 5e-324, 2.2250738585072014e-308, 0.001, 0.0001, 0.00001, 0.000123, 1.0e-5, 123456789012345678.0, 9007199254740993.0, 1234567.125, 1 / 3, 2 / 3, 1e300 * 1e10, -1e300 * 1e10):
    print(repr(x), str(x), f"{x}", x.hex())
print(nan, -nan, inf, -inf, repr(nan), [1.5, -0.0], (1.5,), {1.5: 2.5}, {1.5})

# ---- arithmetic
for a, b in ((7.5, 2.0), (-7.5, 2.0), (7.5, -2.0), (-7.5, -2.0), (1.0, 3.0), (5.5, 1.5), (-5.5, 1.5), (5.5, -1.5), (0.0, 5.0), (-0.0, 5.0), (0.0, -5.0), (1e308, 1e-308), (1e308, 10.0), (inf, 2.0), (2.0, inf), (-2.0, inf), (inf, inf), (3.0, nan), (nan, 3.0), (5, 2.5), (2.5, 5), (True, 0.5), (0.5, False if False else True), (BIG, 2.0), (2.0, BIG)):
    print(a, b, a + b, a - b, a * b, a / b, a // b, a % b, divmod(a, b))
print(-(0.0), +(-0.0), abs(-0.0), abs(-1.5), -inf, abs(-inf), -(-1.5), bool(0.0), bool(-0.0), bool(0.1), bool(nan), bool(inf), not 0.0, not 1.5)
print(failed(lambda: 1.0 / 0.0), failed(lambda: 1.0 // 0.0), failed(lambda: 1.0 % 0.0), failed(lambda: divmod(1.0, 0.0)), failed(lambda: 1 / 0.0), failed(lambda: 1.0 / 0), failed(lambda: 0.0 / 0.0), failed(lambda: inf / 0.0), failed(lambda: 1.0 + "a"), failed(lambda: "a" + 1.0), failed(lambda: 1.0 & 1), failed(lambda: 1 << 1.0), failed(lambda: ~1.0), failed(lambda: 1.0 @ 1.0), failed(lambda: [1] * 1.5), failed(lambda: "a" * 1.5), failed(lambda: list((1,))[0.0]), failed(lambda: range(1.0)), failed(lambda: HUGE + 1.0), failed(lambda: 1.0 * HUGE), failed(lambda: HUGE / 1.0), failed(lambda: 1.0 < HUGE))  # type: ignore[call-overload,operator]
y = 1.5
y += 1
y *= 2
y /= 4
y -= 0.25
y //= 0.25
y %= 2.5
y **= 2
print(y, type(y).__name__)

# ---- power
for a, b in ((2.0, 3.0), (2.0, -1.0), (2.0, 0.5), (4.0, 0.5), (0.0, 0.0), (nan, 0.0), (1.0, nan), (nan, 1.0), (1.0, inf), (-1.0, inf), (2.0, inf), (0.5, inf), (2.0, -inf), (0.5, -inf), (inf, 2.0), (inf, -2.0), (-inf, 3.0), (-inf, 2.0), (-inf, -3.0), (-inf, -2.0), (0.0, 2.0), (-0.0, 3.0), (-0.0, 2.0), (-2.0, 3.0), (-2.0, 2.0), (-1.0, 1e300), (-1.0, 1e300 + 1), (2, 3.0), (2.0, 3), (2, -2), (-2, -3), (1, -5), (True, -1), (10, -400)):
    print(a, b, a**b, pow(a, b))
print(failed(lambda: 0.0 ** -1.0), failed(lambda: 0 ** -1), failed(lambda: 0.0 ** -2), failed(lambda: -0.0 ** -3.0), failed(lambda: 2.0 ** 1e10), failed(lambda: 10.0 ** 400), failed(lambda: (-10.0) ** 401), failed(lambda: pow(2.0, 3.0, 5)), failed(lambda: pow(2, 3.0, 5)), failed(lambda: pow(2, 3, 5.0)), failed(lambda: pow(2.0, 3, 5)), failed(lambda: HUGE ** -1), failed(lambda: 2 ** -HUGE), failed(lambda: pow(1.5, "a")))  # type: ignore[misc]
print(10.0**-400, 2.0**-1080, 2**-1074, 1e308**1)

# ---- int / int, correctly rounded and with its limits
for a, b in ((1, 2), (1, 3), (-1, 3), (7, -2), (0, 5), (0, -5), (2**53 + 1, 1), (2**54 + 3, 2), (3 * 2**70, 2**70), (2**1000, 2**999), (10**308, 1), (10**400, 10**399), (10**400, 10**100 + 1), (1, 10**300), (1, 10**400), (-1, 10**400), (10**3000, 10**3000 + 1), (2**1024 - 2**970 - 1, 1), (1, 2**1074), (1, 2**1075), (3, 2**1075), (1, 3 * 2**1074), (2**64, 3), (10**30, 7)):
    print(a / b)
print(failed(lambda: 1 / 0), failed(lambda: BIG / 0), failed(lambda: HUGE / 1), failed(lambda: 2**1024 / 1), failed(lambda: 10**400 / 3), failed(lambda: True / False))

# ---- float(int), int(float)
for i in (0, 1, -1, 2**53, 2**53 + 1, 2**53 + 2, 2**53 + 3, 2**63, 2**64 + 1, -(2**64) - 1, 2**70 + 2**17, 2**70 + 2**17 + 1, 2**70 + 3 * 2**17, 10**22, 10**23, 10**300, 2**1024 - 2**970 - 1, True, False):
    print(float(i))
print(failed(lambda: float(HUGE)), failed(lambda: float(2**1024)), failed(lambda: float(2**1024 - 2**970)), failed(lambda: float(-(2**1024))))
for f in (0.0, -0.0, 0.5, -0.5, 0.999, 1.5, -1.5, 1e15, 1e16, 1e22, 1e23, 2.0**62, -(2.0**62), 2.0**63, 2.0**64, 1e100, 1.7976931348623157e308):
    print(int(f), f.__trunc__(), f.__floor__(), f.__ceil__(), f.__int__(), round(f))
print(failed(lambda: int(inf)), failed(lambda: int(-inf)), failed(lambda: int(nan)), failed(lambda: round(inf)), failed(lambda: round(nan)), failed(lambda: inf.__trunc__()), failed(lambda: nan.__floor__()), failed(lambda: inf.__ceil__()), failed(lambda: int("1.5")))

# ---- comparisons across the tower are exact
for a, b in ((1.0, 1), (1.5, 1), (1.5, 2), (-1.5, -1), (-1.5, -2), (0.0, 0), (-0.0, 0), (2.0**53, 2**53), (2.0**53, 2**53 + 1), (2.0**53 + 2, 2**53 + 1), (2.0**70, 2**70), (2.0**70, 2**70 + 1), (2.0**70, 2**70 - 1), (-(2.0**70), -(2**70) - 1), (1e308, 10**308), (1e308, 10**400), (-1e308, -(10**400)), (inf, 10**400), (-inf, -(10**400)), (nan, 1), (nan, 10**400), (nan, nan), (inf, inf), (0.5, True), (1.0, True), (0.0, False), (1.5, 1.5), (0.1, 0.2)):
    print(a, b, a == b, a != b, a < b, a <= b, a > b, a >= b, b == a, b != a, b < a, b <= a, b > a, b >= a)
print(1.0 == "1", 1.0 != "1", 1.0 == None, 1.0 == [1.0], [1.0] == [1], (1, 2.0) == (1.0, 2), {1: 2} == {1.0: 2.0}, {1.0} == {1}, failed(lambda: 1.0 < "a"), failed(lambda: "a" < 1.0), failed(lambda: 1.0 < None), max(1, 2.5), min(1, 0.5), max(1.0, 1), min(1, 1.0), sorted([2.5, 1, 2**70, -0.5, True]), [nan] == [nan], nan in [nan], nan == nan, nan is nan, 1.0 in [1], 1 in [1.0], 1.0 in (1,), 1.0 in {1}, 2.0 in range(5), 2.5 in range(5), range(5).index(2.0), range(5).count(2.0), [1, 2].index(2.0), (1, 2).count(1.0), "a" in {1.0: "a"}, {1: "a"}[1.0], {1.0: "a"}[1], {0.0: "a"}[-0.0], len({1, 1.0, True}), len({0.0, -0.0, 0}), type(next(iter({1.0, 1}))).__name__)  # type: ignore[arg-type,comparison-overlap,index,operator]

# ---- hash
for f in (0.0, -0.0, 1.0, -1.0, 2.0, 0.5, 1.5, -1.5, 0.1, 1e100, 1e-100, 2.0**61, 2.0**61 - 2**9, 2.0**62, -(2.0**61), 1e308, 5e-324, 2.5, 1234.5678, inf, -inf):
    print(hash(f), f.__hash__())
print(hash(2.0) == hash(2), hash(2.0**70) == hash(2**70), hash(0.5) == hash(True), hash(-1.0) == hash(-1), hash((1.0, 2.5)), hash(frozenset({1.5})), type(hash(nan)).__name__, hash(nan) == hash(nan))

# ---- parsing, and its spellings
for s in ("0", "1", "-1", "+1", "1.5", ".5", "5.", "-.5", "+5.", "1e5", "1E5", "1e+5", "1e-5", "1.5e3", ".5e1", "5.e1", " 1.5", "1.5 ", "\t\n1.5\r\f\v ", "1_000", "1_0.0_1", "1_0e1_0", "inf", "INF", "Inf", "+inf", "-inf", "infinity", "INFINITY", "-Infinity", "nan", "NaN", "+nan", "-nan", "1e400", "-1e400", "1e-400", "-1e-400", "1e99999999999999999999", "-1e99999999999999999999", "1e-99999999999999999999", "0e99999999999999999999", "0.000000000000000000000000000000000000001e39", "100000000000000000000000000000e-29", "2.2250738585072012e-308", "1.7976931348623157e308", "1.7976931348623159e308", "4.9406564584124654e-324", "2.4703282292062327e-324", "2.4703282292062328e-324", "0.1000000000000000055511151231257827", "9007199254740993", "00001", "-0", "-0.0", "0e0"):
    print(float(s), float(s.encode()), float(bytearray(s.encode())))
for s in ("", " ", "a", "1a", "a1", "1e", "1e+", "e5", ".", "-", "+", "+-1", "--1", "1 2", "1__0", "_1", "1_", "1_.0", "1._0", "1e_5", "1e5_", "1_e5", "0x10", "in", "infin", "infinit", "infinityy", "na", "nanx", "1.5.5", "1,5", "\x001", "1\x00", "1\x1c", "\x1c1"):
    print(failed(lambda: float(s)), failed(lambda: float(s.encode("latin-1"))))
print(float(), float(1.5), float(True), float("1.5"), float(0), failed(lambda: float(None)), failed(lambda: float([])), failed(lambda: float(1, 2)), failed(lambda: float(x=1)), failed(lambda: float({})), failed(lambda: float(object())), failed(lambda: int(1.5, 10)), failed(lambda: float.__new__(int)), failed(lambda: float.__new__(1)), float.__new__(float), float.__new__(float, "2.5"))  # type: ignore[arg-type,call-arg,call-overload]


class HasFloat:
    def __float__(self) -> float:
        return 2.5


class HasIndex:
    def __index__(self) -> int:
        return 7


class HasBoth:
    def __float__(self) -> float:
        return 2.5

    def __index__(self) -> int:
        return 7


class BadFloat:
    def __float__(self) -> object:
        return 1


class RaisesFloat:
    def __float__(self) -> float:
        raise KeyError("no")


class IntHolder:
    def __int__(self) -> int:
        return 3


print(float(HasFloat()), float(HasIndex()), float(HasBoth()), failed(lambda: float(BadFloat())), failed(lambda: float(RaisesFloat())), failed(lambda: float(IntHolder())), float.from_number(1.5), float.from_number(HasFloat()), float.from_number(HasIndex()), float.from_number(3), failed(lambda: float.from_number("1.5")), failed(lambda: float.from_number(None)))  # type: ignore[arg-type]

# ---- rounding
for f, n in ((0.5, None), (1.5, None), (2.5, None), (-0.5, None), (-1.5, None), (-2.5, None), (2.675, 2), (2.665, 2), (1.005, 2), (0.125, 2), (0.375, 2), (1.15, 1), (1.25, 1), (1.35, 1), (1234.5678, 2), (1234.5678, 0), (1234.5678, -2), (1250.0, -2), (1350.0, -2), (1251.0, -2), (5.0, -1), (15.0, -1), (25.0, -1), (35.0, -1), (4.9, -1), (5.1, -1), (50.0, -2), (51.0, -2), (500.0, -3), (-5.0, -1), (-15.0, -1), (0.0, 2), (-0.0, 2), (-0.001, 2), (1e300, 2), (1e300, -299), (1e300, -300), (1e300, -301), (1.4e308, -308), (5e-324, 323), (5e-324, 324), (5e-324, 322), (1e-320, 320), (1.0, 400), (1.0, -400), (-1.0, -400), (1.5, 2**70), (1.5, -(2**70)), (0.1, 16), (0.1, 17), (0.1, 18), (0.1, 30), (inf, 2), (-inf, 2), (inf, -2), (1.5, True)):
    print(f, n, round(f, n), type(round(f, n)).__name__)
print(round(nan, 2), failed(lambda: round(1.7976931348623157e308, -308)), failed(lambda: round(1.5, 1.5)), failed(lambda: round(1.5, "a")), failed(lambda: (1.5).__round__(1, 2)), (1.5).__round__(), (1.5).__round__(None), (1.55).__round__(1))  # type: ignore[call-overload]

# ---- hex
for f in (1.0, -1.0, 0.5, 1.5, 0.1, 255.0, 1e300, 5e-324, 2.2250738585072014e-308, 1.7976931348623157e308, 0.0, -0.0, inf, -inf, nan):
    print(f.hex(), float.fromhex(f.hex()))
for s in ("1", "0x1", "0X1", "-0x1", "+0x1", "0x1p0", "0x1P0", "1p0", "0x1p+1", "0x1p-1", "0x.8", "0x1.", "0x1.8", "1.8p1", "0x10", "ff", "FF", "0xfF.fFp4", "  0x1  ", "\t0x1\n", "inf", "-inf", "INFINITY", "nan", "-nan", "0x0p9999", "0x0.0p-9999", "0x1p-1074", "0x1p-1075", "0x1.8p-1075", "0x3p-1075", "0x1p-1076", "0x1p1023", "0x1.fffffffffffffp1023", "0x1.fffffffffffff7p1023", "0x1.00000000000008", "0x1.00000000000018", "0x1.000000000000081", "0x1.0000000000000800000000000000000001", "0x0000000000000000000000000000000000000000001", "0x1p-99999999999999999999", "0x0p99999999999999999999"):
    print(float.fromhex(s))
for s in ("", " ", "x", "0x", "0xg", "1 2", "0x1p", "0x1p+", "0xp1", "0x.", "1e5e5", "infx", "0x1p1.5", "\xe9"):
    print(failed(lambda: float.fromhex(s)))
print(failed(lambda: float.fromhex("0x1p1024")), failed(lambda: float.fromhex("0x2p1023")), failed(lambda: float.fromhex("0x1.fffffffffffff8p1023")), failed(lambda: float.fromhex("0x1p99999999999999999999")), failed(lambda: float.fromhex(1)), failed(lambda: float.fromhex()), failed(lambda: (1.5).hex(1)))  # type: ignore[arg-type,call-arg]

# ---- the rest of its methods and attributes
print((1.5).is_integer(), (2.0).is_integer(), inf.is_integer(), nan.is_integer(), (0.0).as_integer_ratio(), (0.5).as_integer_ratio(), (-0.25).as_integer_ratio(), (10.0).as_integer_ratio(), (0.1).as_integer_ratio(), (1e300).as_integer_ratio()[1], (5e-324).as_integer_ratio()[0], failed(lambda: inf.as_integer_ratio()), failed(lambda: nan.as_integer_ratio()))
print((1.5).real, (1.5).imag, (1.5).conjugate(), (1.5).__float__(), (1.5).__getnewargs__(), (1.5).__pos__(), (1.5).__neg__(), (-1.5).__abs__(), (1.5).__bool__(), (1.5).__repr__(), (1.5).__str__(), (1.5).__format__(""), format(1.5), format(1.5, ""), float.__getformat__("double"), float.__getformat__("float"), failed(lambda: float.__getformat__("x")), failed(lambda: float.__getformat__(1)), (1.5).__eq__(1.5), (1.5).__eq__(1), (1.0).__eq__(1), (1.5).__eq__("a"), (1.5).__lt__(2), (1.5).__add__(1), (1.5).__radd__(1), (1.5).__add__("a"), (1.5).__rsub__(1), (1.5).__pow__(2), (1.5).__rpow__(2), (1.5).__pow__(2, None), (1.5).__divmod__(1), (1.5).__rdivmod__(2), (1.5).__floordiv__(1), (1.5).__rfloordiv__(2), (1.5).__mod__(1), (1.5).__rmod__(2), (1.5).__truediv__(2), (1.5).__rtruediv__(3), (1.5).__mul__(2), (1.5).__rmul__(2), (1.5).__sub__(1))  # type: ignore[attr-defined,operator]
print((1).__float__(), True.__float__(), (2**70).__float__(), (1).__truediv__(2), (1).__rtruediv__(2), (1).__add__(1.5), (1).__radd__(1.5), (1).__eq__(1.0), (1).__lt__(1.5), (1).__pow__(-1), (1).__pow__(1.5), (1).__divmod__(1.5), sorted(set(dir(1.5)) - set(dir(object))) == sorted([k for k in vars(float) if k not in dir(object)]), type(1.5), type(1.5).__name__, float.__name__, float.__qualname__, float.__module__, float.__mro__, float.__bases__, isinstance(1.5, float), isinstance(1, float), isinstance(True, float), issubclass(float, object), issubclass(bool, float), callable(float), float.__dict__["real"].__name__, type(float.__dict__["real"]).__name__)  # type: ignore[operator]
print(failed(lambda: setattr(1.5, "x", 1)), failed(lambda: setattr(1.5, "real", 1)), failed(lambda: delattr(1.5, "real")), failed(lambda: (1.5).x), failed(lambda: (1.5, )[0]()), failed(lambda: iter(1.5)), failed(lambda: len(1.5)), failed(lambda: (1.5, )[0][0]), failed(lambda: chr(1.5)), failed(lambda: hex(1.5)), failed(lambda: bin(1.5)), failed(lambda: bytes(1.5)), failed(lambda: list(1.5)), failed(lambda: str(1.5, "a")), failed(lambda: list((0,))[1.5]), failed(lambda: list((0, 1))[0.0:1.0]), failed(lambda: int.from_bytes(1.5)), failed(lambda: (1).to_bytes(1.5)), failed(lambda: slice(1.5).indices(2)), failed(lambda: range(0, 1.5)), failed(lambda: float.hex(1)), failed(lambda: float.__add__(1, 2)), float.__add__(1.5, 2), float.real.__get__(1.5))  # type: ignore[arg-type,attr-defined,call-overload,index,operator]
x = 2.5
print(x is x, float(x) is x, +x is x, x.real is x, x.conjugate() is x, x.__float__() is x, -(-x) is x, abs(x) is x, x * 1.0 is x, x.__pos__() is x, type(x.__getnewargs__()[0]).__name__)


# ---- a subclass
class F(float):
    tag = "f"

    def __add__(self, o: object) -> str:  # type: ignore[override]
        return "add"

    def __radd__(self, o: object) -> str:  # type: ignore[override]
        return "radd"

    def __eq__(self, o: object) -> bool:
        return True

    def __lt__(self, o: object) -> bool:
        return True

    def __gt__(self, o: object) -> bool:
        return False

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "F!"

    def __hash__(self) -> int:
        return 5

    def __float__(self) -> float:
        return 9.5

    def __int__(self) -> int:
        return 9

    def __neg__(self) -> str:  # type: ignore[override]
        return "neg"

    def __abs__(self) -> str:  # type: ignore[override]
        return "abs"

    def __round__(self, n: object = None) -> str:  # type: ignore[override]
        return "round"

    def __pow__(self, o: object, m: object = None) -> str:  # type: ignore[override]
        return "pow"

    def __rpow__(self, o: object, m: object = None) -> str:  # type: ignore[override]
        return "rpow"

    def __divmod__(self, o: object) -> str:  # type: ignore[override]
        return "divmod"

    def __rdivmod__(self, o: object) -> str:  # type: ignore[override]
        return "rdivmod"


class G(float):
    __slots__ = ("a",)

    def __new__(cls, v: object, a: int = 0) -> "G":
        self = super().__new__(cls, v)  # type: ignore[arg-type]
        self.a = a  # type: ignore[attr-defined]
        return self


class H(float):
    def __init__(self, v: object) -> None:
        self.k = 4


class Sub(G):
    pass


f = F(1.5)
g = G("2.5", 3)
h = H(3.5)
s = Sub(0.5)  # type: ignore[assignment]
p = float.__new__(F, 1.25)
print(f + 1, 1 + f, f + f, 1.5 + f, f - 1, 1 - f, f == 0, 1 == f, 1.0 == f, f != 0, f < 0, 0 < f, 0.0 < f, f > 0, bool(f), repr(f), str(f), f"{f}", [f], hash(f), float(f), int(f), -f, +f, abs(f), round(f), f**2, 2**f, 2.0**f, divmod(f, 1), divmod(1, f), divmod(1.0, f), f.real, f.imag, f.hex(), f.is_integer(), f.tag, type(f).__name__, type(f.real).__name__, type(+f).__name__, f.conjugate(), type(f.conjugate()).__name__, float.__float__(f), float.__repr__(f), float.__hash__(f) == hash(1.5), float.__eq__(f, 1.5), float.__add__(f, 1), float.__neg__(f), float.__abs__(f), float.__int__(f), float.__round__(f), type(float.__float__(f)).__name__, p, float.__repr__(p), isinstance(f, float), issubclass(F, float), F.__mro__[1].__name__)
print(g, g.a, g + 1, -g, g == 2.5, hash(g) == hash(2.5), repr(g), type(g).__name__, int(g), float(g), type(float(g)).__name__, bool(g), round(g), g.as_integer_ratio(), g.__getnewargs__(), sorted(g.__slots__), failed(lambda: setattr(g, "b", 1)), h, h.k, h.__dict__, h + 1, s, s.a, s.__dict__, F.fromhex("0x1p0"), type(F.fromhex("0x1p0")).__name__, type(G.fromhex("0x1p0")).__name__, type(F.from_number(1.5)).__name__, G.from_number(1.5).a, float.from_number(f), type(float.from_number(f)).__name__, type(float(g)).__name__, failed(lambda: F(1, 2)), failed(lambda: F("a")), F(), type(F()).__name__, H(1.5).k, failed(lambda: H(1.5, 2)), failed(lambda: H(x=1)), failed(lambda: object.__new__(F)), failed(lambda: int.__new__(F)), failed(lambda: float.__new__(int, 1)), failed(lambda: type("X", (int, float), {})))  # type: ignore[attr-defined,call-arg,type-var]
g2 = G(1.5)
g2.a = 7  # type: ignore[attr-defined]
del g2.a  # type: ignore[attr-defined]
print(failed(lambda: g2.a), failed(lambda: setattr(p, "z", 1)) if False else 0, sum([g, 1.5]), sum([1.5, g]), max(g, 1.0) is g, sorted([g, 1.0])[1] is g, {2.5: "a"}[g], {g: "b"}[2.5], g in [2.5], 2.5 in [g])  # type: ignore[attr-defined,index]

# ---- sum: compensated while the items are floats and small ints, plain after anything else
print(sum([0.1] * 10), sum([0.1] * 10, 0.0), sum([1e100, 1.0, -1e100, 1e-100]), sum([1e308, 1e308, -1e308]), sum([1e308, 1e308]), sum([inf, 1.0]), sum([inf, -inf]), sum([1.0, 2, True]), sum([1, 2.5]), sum([2.5, 1]), sum([], 1.5), sum([], 0.0), sum((1.5, 2.5)), sum([0.1, 0.2, 0.3]), sum([0.1, 0.2, 0.3], 0), sum([1e16, 1.0, 1.0]), sum([1.0, 1e16, 1.0, -1e16]), sum([-0.0]), sum([-0.0], -0.0), sum([], -0.0), sum([0.0, -0.0]), sum([1.5, 2**70]), sum([2**70, 1.5]), sum([1.5, BIG, 0.1, 0.2, 0.3]), sum([0.1, 0.2, F(0.3)]) if False else 0, sum([0.1, G(0.2), 0.3, 0.4]), sum([1, 0.1, 0.2, 0.3]), sum([2**62, 2**62, 2**62, 0.1, 0.2, 0.3]), sum([1, BIG, 0.1, 0.2, 0.3]), sum([True, 0.5]), sum([0.5, True]), failed(lambda: sum([1.5, "a"])), failed(lambda: sum(["a"], 1.5)), failed(lambda: sum([HUGE], 1.5)), sum([0.1, 0.2], G(1.5)), type(sum([1.5], G(1.5))).__name__, sum([1], F(1.5)) if False else 0)  # type: ignore[list-item]
