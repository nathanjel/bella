# clause: C-6-17
# spec: section 6
# status: P1
# source: dialect specification section 6, Objects/complexobject.c, Objects/unicode_formatter.c
"""complex: the constructor and its strings, arithmetic with its mixed real forms, the corners of C11's Annex G that
the C recovers, comparison and hash with the other numbers, repr, __format__, its subclasses, and sum()'s stage."""
# ruff: noqa: B015, B018, B023, B033, E712, E731, F601, PLR0133, PLW0129, RUF015, UP003, UP018, UP031, UP032, UP037


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


inf = float("inf")
nan = float("nan")

# ---- literals, repr, str
print(1j, 2.5j, 0j, 1e20j, 1e-20j, 1e400j, 1_000j, 0.1j, repr(1j), str(1j), type(1j).__name__, type(1j) is complex)
print(1 + 2j, 1 - 2j, -1j, -(1 + 2j), +1j, 1.5 + 2.5j, -0j, 0j * -1, 0.0 - 0j, -0.0 + 0j, -0.0 - 0j)
print(complex(0.0, 1.0), complex(-0.0, 1.0), complex(0.0, -0.0), complex(-0.0, -0.0), complex(1, 0), complex(1, -0.0), complex(inf, nan), complex(nan, inf), complex(-inf, -inf), complex(nan, nan), complex(0, nan), complex(1e16, 1e16), complex(1e15, 1e-5), complex(1.5e300, -1.5e-300))
print((1 + 2j).real, (1 + 2j).imag, type((1 + 2j).real).__name__, (1 + 2j).conjugate(), (-0.0 + 0j).conjugate(), (1 + 2j).__getnewargs__(), (1 + 2j).__complex__(), abs(3 + 4j), abs(-3 - 4j), abs(complex(inf, nan)), abs(complex(nan, inf)), abs(complex(nan, 1)), bool(0j), bool(1j), bool(complex(0, 0)), bool(complex(1, 0)), bool(complex(nan, 0)), bool(-0j), not 1j)  # type: ignore[attr-defined]
x = 1 + 2j
print(x is x, +x is x, x.__pos__() is x, x.__complex__() is x, complex(x) is x, complex.from_number(x) is x)

# ---- the constructor
for args in ((), (1,), (1.5,), (True,), (1, 2), (1.5, 2.5), (True, False), (1, 0.5), (2**70,), (2**70, 2**70)):
    print(args, complex(*args))
print(complex(real=1), complex(imag=2), complex(real=1, imag=2), complex(1, imag=2), complex(1.5, imag=-0.0))
for s in ("1", "1.5", "1j", "1J", "j", "J", "+j", "-j", "1+j", "1-j", "1+1j", "1-1j", "1.5+2.5j", "-1.5-2.5j", " 1 ", "\t1+1j\n", "(1+1j)", " ( 1+1j ) ", "(j)", "(1)", "1e5", "1e5j", "1e5+1e5j", "1E5J", "inf", "-inf", "infinity", "INF", "nan", "-nan", "NAN", "infj", "nanj", "inf+infj", "nan+nanj", "-inf-infj", "1+infj", "1+nanj", "1_000", "1_000j", "1_0+2_0j", "1e1_0", ".5", "5.", ".5j", "5.j", "0", "-0", "0j", "-0j", "0+0j", "-0-0j", "0-0j", "1e400", "1e400j", "-1e400", "1e-400j", "00", "007j"):
    print(repr(s), complex(s))
for s in ("", " ", "a", "1+", "1-", "+", "-", "1+1", "1+1i", "1i", "(1", "1)", "()", "( )", "((1))", "(1+1j", "1+1j)", "1 + 1j", "1 +1j", "1+ 1j", "1j+1", "j1", "jj", "1jj", "1+1jj", "1+1j1", "1e", "1e+", "e5", ".", ".j", "_", "_1", "1_", "1__0", "1_.5", "1._5", "1e_5", "1e5_", "1_j", "1+_1j", "1\x00", "\x001", "1\x002", "(1)j", "+-1", "--1", "++j", "+-j", "infinit", "na", "1+in", "nanj+1", "0x10", "1,5", "١"[:0] + "1 1"):
    print(repr(s), failed(lambda: complex(s)))


class HasComplex:
    def __complex__(self) -> complex:
        return 3 + 4j


class HasFloat:
    def __float__(self) -> float:
        return 1.5


class HasIndex:
    def __index__(self) -> int:
        return 7


class HasAll:
    def __complex__(self) -> complex:
        return 5j

    def __float__(self) -> float:
        return 6.5

    def __index__(self) -> int:
        return 8


class BadComplex:
    def __complex__(self) -> int:
        return 1


class BadFloat:
    def __float__(self) -> int:
        return 1


class Raises:
    def __complex__(self) -> complex:
        raise ValueError


class NoneFloat:
    __float__ = None


class Neither:
    pass


class FloatSub(float):
    def __float__(self) -> float:
        return 9.5


class IntSub(int):
    def __index__(self) -> int:
        return 9

    def __float__(self) -> float:
        return 8.5


print(complex(HasComplex()), complex(HasFloat()), complex(HasIndex()), complex(HasAll()), complex(FloatSub(1.5)), complex(IntSub(1)), complex(HasFloat(), 2), complex(1, HasFloat()), complex(HasIndex(), HasIndex()), complex(HasFloat(), HasIndex()), complex(FloatSub(1.5), IntSub(1)), complex(imag=HasFloat()), complex(real=HasFloat()))
print(complex.from_number(1), complex.from_number(1.5), complex.from_number(1j), complex.from_number(True), complex.from_number(HasComplex()), complex.from_number(HasFloat()), complex.from_number(HasIndex()), complex.from_number(HasAll()), complex.from_number(FloatSub(1.5)), complex.from_number(IntSub(1)))
print(failed(lambda: complex(None)), failed(lambda: complex([])), failed(lambda: complex(b"1")), failed(lambda: complex(bytearray(b"1"))), failed(lambda: complex(Neither())), failed(lambda: complex(BadComplex())), failed(lambda: complex(BadFloat())), failed(lambda: complex(Raises())), failed(lambda: complex(NoneFloat())), failed(lambda: complex(2**2000)), failed(lambda: complex("1", 2)), failed(lambda: complex(1, "2")), failed(lambda: complex("1", "2")), failed(lambda: complex(real="1")), failed(lambda: complex(imag="1")), failed(lambda: complex(None, 1)), failed(lambda: complex(1, None)), failed(lambda: complex(1, 2, 3)), failed(lambda: complex(x=1)), failed(lambda: complex(1, 2, x=1)), failed(lambda: complex(1, real=1)), failed(lambda: complex(1, 2, imag=1)), failed(lambda: complex(real=1, imag=2, x=3)), failed(lambda: complex(Neither(), 1)), failed(lambda: complex(1, Neither())), failed(lambda: complex(BadFloat(), 1)), failed(lambda: complex(1, BadFloat())), failed(lambda: complex(2**2000, 1)), failed(lambda: complex(1, 2**2000)))  # type: ignore[call-overload]
print(failed(lambda: complex.from_number("1")), failed(lambda: complex.from_number(None)), failed(lambda: complex.from_number()), failed(lambda: complex.from_number(1, 2)), failed(lambda: complex.from_number(number=1)), failed(lambda: complex.from_number(Neither())), failed(lambda: complex.from_number(BadComplex())), failed(lambda: complex.from_number(BadFloat())), failed(lambda: complex.from_number(2**2000)))  # type: ignore[arg-type,call-arg]

# ---- arithmetic, and the mixed forms: a real operand leaves the other part alone
vals = (0.0, -0.0, 1.0, -1.0, 2.0, 0.5, inf, -inf, nan)
for a in vals:
    z = complex(a, 1.0)
    w = complex(1.0, a)
    print(z + 1.0, 1.0 + z, z - 1.0, 1.0 - z, z * 2.0, 2.0 * z, z + 1, 1 + z, z - 1, 1 - z, z * 2, 2 * z, z + w, z - w, z * w, w * z)
    print(z + True, True + z, z * False, False * z, -z, +z, z.conjugate(), abs(w) if a == a and a not in (inf, -inf) else 0)
print(complex(0.0, -0.0) + 0.0, 0.0 + complex(0.0, -0.0), complex(-0.0, -0.0) + (-0.0), -0.0 + complex(-0.0, -0.0), complex(0.0, -0.0) - 0.0, 0.0 - complex(0.0, 0.0), -0.0 - complex(0.0, 0.0), complex(0.0, -0.0) * 1.0, 1.0 * complex(0.0, -0.0), complex(1, 0) * -1.0, -1.0 * complex(1, 0), complex(inf, 0) * 2, complex(inf, 0) * complex(2, 0), complex(inf, nan) * 2.0, complex(nan, inf) * complex(0, 1), complex(inf, inf) * complex(1, 1), complex(1e308, 1e308) * complex(1e308, 1e308), complex(inf, 1) * complex(nan, nan), complex(nan, nan) * complex(inf, 1), complex(0, inf) * complex(0, nan))
print((1 + 2j) / (3 + 4j), (1 + 2j) / 2, (1 + 2j) / 2.5, 2 / (1 + 1j), 2.5 / (1 + 1j), 1j / 1j, (1 + 1j) / (1 - 1j), (1 + 2j) / (0 + 1j), (1 + 2j) / (1 + 0j), 1 / 1j, 1.0 / -1j, True / 1j, (1 + 2j) / True, complex(1e308, 1e308) / complex(1e308, 1e308), complex(inf, 1) / (1 + 1j), complex(1, inf) / (1 + 1j), (1 + 1j) / complex(inf, 1), (1 + 1j) / complex(1, inf), complex(inf, inf) / complex(inf, inf), complex(nan, 1) / (1 + 1j), (1 + 1j) / complex(nan, 1), 1 / complex(inf, 1), 1.0 / complex(1, inf), 1.0 / complex(inf, inf), 1.0 / complex(nan, 1), inf / complex(1, 1), nan / complex(1, 1), complex(inf, 1) / 2, complex(1, 1) / inf, complex(inf, 1) / inf, complex(1, 1) / nan)
print(failed(lambda: 1j / 0), failed(lambda: 1j / 0.0), failed(lambda: 1j / 0j), failed(lambda: 1 / 0j), failed(lambda: 1.0 / 0j), failed(lambda: 0 / 0j), failed(lambda: 0j / 0j), failed(lambda: 1j / False), failed(lambda: 1j / -0.0), failed(lambda: 1j / complex(0.0, -0.0)), failed(lambda: complex(inf, 0) / 0), failed(lambda: complex(nan, 0) / 0j), failed(lambda: inf / 0j), failed(lambda: nan / 0j))

# ---- powers
print((1 + 1j) ** 2, (1 + 1j) ** 0, (1 + 1j) ** 1, (1 + 1j) ** -1, (1 + 1j) ** -2, 2j ** 3, 2j ** 10, (2 + 0j) ** 100 == 2.0 ** 100, (1 + 1j) ** 2.0, (1 + 1j) ** (2 + 0j), 1j ** 2, 1j ** 4, 2 ** (2 + 0j), 2.0 ** (2 + 0j), (0 + 0j) ** 0, (0 + 0j) ** 0j, (0 + 0j) ** 1, (0 + 0j) ** 2.5, 0 ** 1j if False else 0, 0j ** (1 + 0j), True ** 1j, 1j ** True, 1j ** False, pow(1j, 2), pow(2j, 2, None), pow(2, 2 + 0j), pow(1j, 2.0), 1 ** 1j)
for b, e in ((1 + 2j, 0.5), (1 + 2j, 1.5), (2, 1j), (2.0, 1j), (1j, 1j), (1 + 1j, 1 + 1j), (-8.0, 1 / 3), (-8, 1 / 3), (-1.5, 0.5), (-1, 0.5), (-2.0, -0.5), (1j, 101), (1j, -101), (1j, 100.5), (2j, 0.5)):
    r = b ** e
    print(type(r).__name__, round(r.real, 6), round(r.imag, 6), type(pow(b, e)).__name__)
print(failed(lambda: 0j ** -1), failed(lambda: 0j ** -1.5), failed(lambda: 0j ** 1j), failed(lambda: 0j ** (1 + 1j)), failed(lambda: 0 ** 1j), failed(lambda: 0.0 ** -1j), failed(lambda: (1e200 + 1e200j) ** 2), failed(lambda: (1e200 + 1e200j) ** 2.5), failed(lambda: (1e308 + 0j) ** 100), failed(lambda: 2 ** (1e4 + 0j)), failed(lambda: 2 ** (1e4 + 1j)), failed(lambda: (2 + 0j) ** 1e4), failed(lambda: pow(1j, 2, 3)), failed(lambda: pow(2, 1j, 3)), failed(lambda: pow(2, 3, 1j)), failed(lambda: pow(1.5, 1j, 3)), failed(lambda: pow(1j, 1.5, 3)), failed(lambda: pow(1, 1.5, 1j)), failed(lambda: pow("a", 2, 1j)), failed(lambda: pow("a", 1j, 3)), failed(lambda: pow(1j, "a", 3)), failed(lambda: pow(1j, "a")), failed(lambda: 1j ** "a"), failed(lambda: "a" ** 1j), failed(lambda: pow(1j, 1j, 1j)), failed(lambda: pow(1j, 2, None)))  # type: ignore[call-overload,misc,operator]
print((1e-200 + 1e-200j) ** 2, (1e-200 + 0j) ** 3, (1e-200 + 1e-200j) ** 2.5 == 0, 1j ** 0.0, 1j ** 0j, complex(inf, 0) ** 0, complex(nan, nan) ** 0, complex(nan, nan) ** 0j, complex(1, 0) ** 1000 if False else 0, complex(1, 0) ** 100, complex(1, 0) ** -100, failed(lambda: complex(inf, 0) ** 1), failed(lambda: complex(inf, inf) ** 2), (1 + 0j) ** nan, (1 + 0j) ** complex(nan, 0))

# ---- what a complex does not do
for f in (lambda: 1j % 1, lambda: 1 % 1j, lambda: 1j // 1, lambda: 1 // 1j, lambda: divmod(1j, 1), lambda: divmod(1, 1j), lambda: 1j < 1, lambda: 1 < 1j, lambda: 1j <= 1j, lambda: 1j > 1.5, lambda: 1.5 >= 1j, lambda: 1j & 1, lambda: 1 | 1j, lambda: 1j ^ 1j, lambda: 1j << 1, lambda: 1 >> 1j, lambda: ~1j, lambda: 1j @ 1j, lambda: int(1j), lambda: float(1j), lambda: round(1j), lambda: round(1j, 1), lambda: [1].__getitem__(1j), lambda: [1] * 1j, lambda: 1j * [1], lambda: "a" * 1j, lambda: "a" + 1j, lambda: 1j + "a", lambda: 1j + None, lambda: None + 1j, lambda: 1j - [], lambda: 1j * {}, lambda: 1j / "a", lambda: "a" / 1j, lambda: range(1j), lambda: 1j.__float__(), lambda: 1j.__int__(), lambda: 1j.__mod__(1), lambda: 1j.__floordiv__(1), lambda: 1j.__divmod__(1), lambda: (1j).nothing, lambda: setattr(1j, "real", 1), lambda: setattr(1j, "imag", 1), lambda: setattr(1j, "x", 1), lambda: delattr(1j, "real"), lambda: "%d" % 1j, lambda: "%x" % 1j, lambda: "%f" % 1j, lambda: "%c" % 1j, lambda: hex(1j), lambda: chr(1j)):  # type: ignore[arg-type,attr-defined,call-overload,operator,str-format]
    print(failed(f), end=" ")
print()

# ---- comparison and hash, with the other numbers
print(1j == 1j, 1j != 1j, 1 + 0j == 1, 1 == 1 + 0j, 1.0 == 1 + 0j, 1 + 0j == 1.0, 1 + 1j == 1, 1 == 1 + 1j, 1 + 1j == 1.0, 1 + 0j != 1, 1 != 1 + 0j, 1.0 != 1 + 0j, True == 1 + 0j, 1 + 0j == True, 0j == False, 0j == 0, 0j == -0.0, complex(0.0, -0.0) == 0, 1j == "a", "a" == 1j, 1j != "a", None == 1j, 1j == None, [] == 1j, 1j == (1,), complex(nan, 0) == complex(nan, 0), complex(nan, 0) != complex(nan, 0), complex(nan, 0) == nan, nan == complex(nan, 0), complex(inf, 0) == inf, inf == complex(inf, 0), complex(inf, 0) == 2**2000, 2**2000 == complex(inf, 0), complex(2.0**70, 0) == 2**70, 2**70 == complex(2.0**70, 0), complex(2.0**70, 0) == 2**70 + 1, 2**70 + 1 == complex(2.0**70, 0), complex(2.0**70, 1) == 2**70, complex(1e308, 0) == 2**2000)  # type: ignore[comparison-overlap]
print(hash(0j), hash(1 + 0j), hash(1j), hash(1 + 1j), hash(-1j), hash(1 - 1j), hash(-1 + 0j), hash(2 + 3j), hash(1.5 + 2.5j), hash(complex(inf, 0)), hash(complex(0, inf)), hash(complex(inf, inf)), hash(complex(-inf, -inf)), hash(1e300 + 1e300j), hash(complex(1, 0)) == hash(1), hash(complex(1.5, 0)) == hash(1.5), hash(complex(0.0, 0.0)) == hash(complex(-0.0, -0.0)), (1 + 0j).__hash__(), len({1: 1, 1.0: 2, 1 + 0j: 3}), {1: "int"}[1 + 0j], {1 + 0j: "cx"}[1], {1j: "x"}[0 + 1j], sorted([abs(1j), abs(2j)]), len({1j, 1j, 2j}), 1j in [1j], 1j in (1,), 1 + 0j in [1], 1 in {1 + 0j}, [1j, 2j].index(2j), [1 + 0j].count(1), (1j, 2j) == (1j, 2j), [1j] < [2j] if False else 0, failed(lambda: [1j] < [2j]), failed(lambda: sorted([1j, 2j])), failed(lambda: max(1j, 2j)))  # type: ignore[call-overload,index,type-var]

# ---- the wrappers, through the class
print(complex.__add__(1j, 1), complex.__add__(1j, 1.5), complex.__add__(1j, 1j), complex.__add__(1j, "a"), complex.__radd__(1j, 1), complex.__radd__(1j, "a"), complex.__sub__(1j, 1), complex.__rsub__(1j, 1), complex.__mul__(1j, 2), complex.__rmul__(1j, 2), complex.__truediv__(1j, 2), complex.__rtruediv__(1j, 2), complex.__pow__(1j, 2), complex.__rpow__(1j, 2) == 2 ** 1j, complex.__pow__(1j, "a"), complex.__rpow__(1j, "a"), complex.__neg__(1j), complex.__pos__(1j), complex.__abs__(1j), complex.__bool__(1j), complex.__repr__(1j), complex.__hash__(1j), complex.__eq__(1j, 1j), complex.__eq__(1j, "a"), complex.__ne__(1j, 1j), complex.__ne__(1j, "a"), complex.__lt__(1j, 1j), complex.__le__(1j, 1), complex.__gt__(1j, "a"), complex.__ge__(1j, 1.5), complex.conjugate(1j), complex.__complex__(1j), complex.__getnewargs__(1j), complex.__format__(1j, ""), complex.__str__(1j))  # type: ignore[attr-defined,operator]
print(float.__add__(1.5, 1j), int.__add__(1, 1j), float.__radd__(1.5, 1j), int.__radd__(1, 1j), float.__eq__(1.5, 1j), int.__eq__(1, 1 + 0j), float.__mul__(1.5, 1j), float.__pow__(1.5, 1j), int.__pow__(1, 1j), float.__rpow__(1.5, 1j), float.__truediv__(1.0, 1j), int.__truediv__(1, 1j), (-8.0).__pow__(0.5).imag != 0, float.__pow__(-8.0, 1.5).imag != 0)  # type: ignore[call-overload,operator]
print(failed(lambda: complex.__add__(1, 1)), failed(lambda: complex.__add__()), failed(lambda: complex.__add__(1j)), failed(lambda: complex.__add__(1j, 1, 2)), failed(lambda: complex.__neg__(1)), failed(lambda: complex.__neg__(1j, 1)), failed(lambda: complex.__repr__(1)), failed(lambda: complex.__hash__(1)), failed(lambda: complex.__eq__(1, 1j)), failed(lambda: complex.__pow__(1j, 2, 3)), failed(lambda: complex.__pow__(1j)), failed(lambda: complex.__pow__(1j, 2, 3, 4)), failed(lambda: complex.__rpow__(1j, 2, 3)), failed(lambda: complex.conjugate(1)), failed(lambda: complex.conjugate(1j, 1)), failed(lambda: complex.__complex__(1)), failed(lambda: complex.__getnewargs__(1)), failed(lambda: complex.__format__(1, "")), failed(lambda: complex.__format__(1j)), failed(lambda: complex.__format__(1j, 1)), failed(lambda: complex.real.__get__(1)), failed(lambda: complex.imag.__get__("a")), failed(lambda: complex.real.__set__(1j, 1)), failed(lambda: complex.real.__delete__(1j)))  # type: ignore[arg-type,attr-defined,call-arg,operator]
print(complex.real.__get__(1 + 2j), complex.imag.__get__(1 + 2j), complex.real.__get__(None, complex) is complex.real, type(complex.real).__name__, repr(complex.real), repr(complex.imag), complex.real.__name__, complex.real.__objclass__.__name__, complex.__name__, complex.__qualname__, complex.__module__, complex.__base__.__name__, complex.__mro__[1].__name__, complex.__bases__[0].__name__, isinstance(1j, complex), issubclass(complex, object), isinstance(1, complex), isinstance(1.0, complex), issubclass(int, complex))  # type: ignore[attr-defined,union-attr]

# ---- subclasses


class C(complex):
    pass


class Named(complex):
    def __repr__(self) -> str:
        return "Named(" + complex.__repr__(self) + ")"

    def __add__(self, other: object) -> str:  # type: ignore[override]
        return "Named.__add__"

    def __radd__(self, other: object) -> str:  # type: ignore[override]
        return "Named.__radd__"

    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False

    def __hash__(self) -> int:
        return 42

    def __bool__(self) -> bool:
        return False

    def __abs__(self) -> str:  # type: ignore[override]
        return "Named.__abs__"

    def __neg__(self) -> str:  # type: ignore[override]
        return "Named.__neg__"

    def __pos__(self) -> str:  # type: ignore[override]
        return "Named.__pos__"

    def __pow__(self, other: object, mod: object = None) -> str:  # type: ignore[override]
        return "Named.__pow__"

    def __rpow__(self, other: object, mod: object = None) -> str:  # type: ignore[override]
        return "Named.__rpow__"

    def __format__(self, spec: str) -> str:
        return "Named.__format__"

    def __complex__(self) -> complex:
        return 7j


class Slotted(complex):
    __slots__ = ("x",)


class Newer(complex):
    def __new__(cls, a: float) -> "Newer":
        return complex.__new__(cls, a, a)

    def __init__(self, a: float) -> None:
        self.a = a


c = C(1, 2)
print(c, repr(c), type(c).__name__, type(c + 1).__name__, type(-c).__name__, type(+c).__name__, type(c.conjugate()).__name__, type(c.__complex__()).__name__, type(complex(c)).__name__, type(C(c)).__name__, c.__complex__() is c, +c is c, complex(c) is c, c == 1 + 2j, 1 + 2j == c, hash(c) == hash(1 + 2j), bool(c), abs(C(3, 4)), c * 2, 2 * c, c / 1, c ** 2, 2 ** C(2, 0), c.real, c.imag, C(), C("1+2j"), C(1.5), C(real=1), C(imag=2), C(1j), C(HasComplex()), C(HasFloat()), C.from_number(1), type(C.from_number(1)).__name__, C.from_number(1j), type(C.from_number(1j)).__name__, type(C.from_number(c)).__name__, format(c, ".1f"), format(c), "%s" % c, str(c), f"{c}", f"{c!r}")
c.y = 5  # type: ignore[attr-defined]
print(c.y, vars(c), c.__dict__, hasattr(1j, "__dict__"), "y" in dir(c), failed(lambda: C("a")), failed(lambda: C(None)), failed(lambda: C(1, 2, 3)), failed(lambda: complex.__new__(int)), failed(lambda: complex.__new__(1)), failed(lambda: complex.__new__()), failed(lambda: complex.__new__(object)), type(complex.__new__(C)).__name__, complex.__new__(complex), complex.__new__(complex, 1, 2), complex.__new__(C, 1, 2), failed(lambda: complex.__new__(complex, 1, 2, 3)))  # type: ignore[attr-defined,call-overload,type-var]
n = Named(1, 2)
print(n, repr(n), str(n), n + 1, 1 + n, 1.5 + n, 1j + n, n - 1, 1 - n, n * 2, n == 5, 5 == n, n != 5, 5 != n, 1j == n, 1j != n, hash(n), bool(n), not n, abs(n), -n, +n, n ** 2, 2 ** n, 1j ** n, 1.5 ** n, pow(n, 2), format(n, ""), format(n, "x"), f"{n}", complex(n), n.conjugate(), n.__complex__(), complex.__repr__(n), complex.__add__(n, 1), complex.__eq__(n, 1 + 2j), complex.__hash__(n) == hash(1 + 2j), complex.__bool__(n), complex.__abs__(C(3, 4)), complex.__neg__(n), complex.__pos__(n), type(complex.__pos__(n)).__name__, {n: 1}[n], sum([n], 1j) if False else 0)
s = Slotted(1, 2)  # type: ignore[assignment]
s.x = 3  # type: ignore[attr-defined]
print(s, s.x, hasattr(s, "__dict__"), failed(lambda: setattr(s, "z", 1)), Newer(2.5), Newer(2.5).a, type(Newer(2.5) + 1).__name__, failed(lambda: Newer()), failed(lambda: type("X", (complex, int), {})), failed(lambda: type("X", (complex, float), {})), failed(lambda: type("X", (float, complex), {})), type("X", (complex,), {})(1).real, failed(lambda: type("X", (C, int), {})), isinstance(c, complex), issubclass(C, complex), C.__base__.__name__, C.__mro__[1].__name__)  # type: ignore[attr-defined,call-arg,union-attr]


class Rsub(float):
    def __add__(self, other: object) -> str:  # type: ignore[override]
        return "Rsub.__add__"

    def __radd__(self, other: object) -> str:  # type: ignore[override]
        return "Rsub.__radd__"


class Radd:
    def __add__(self, other: object) -> str:
        return "Radd.__add__"

    def __radd__(self, other: object) -> str:
        return "Radd.__radd__"

    def __rmul__(self, other: object) -> str:
        return "Radd.__rmul__"

    def __rtruediv__(self, other: object) -> str:
        return "Radd.__rtruediv__"

    def __rpow__(self, other: object) -> str:
        return "Radd.__rpow__"

    def __rsub__(self, other: object) -> str:
        return "Radd.__rsub__"

    def __rmod__(self, other: object) -> str:
        return "Radd.__rmod__"

    def __eq__(self, other: object) -> bool:
        return True

    def __hash__(self) -> int:
        return 1


print(1j + Radd(), Radd() + 1j, 1j * Radd(), 1j / Radd(), 1j ** Radd(), 1j - Radd(), 1j % Radd(), 1j == Radd(), Radd() == 1j, 1j != Radd(), Rsub(1.5) + 1j, 1j + Rsub(1.5), 1j - Rsub(1.5), Rsub(1.5) - 1j, IntSub(1) + 1j, 1j + IntSub(1), 1j * FloatSub(2.0), 1j / IntSub(1))
y = 1j
y += 1
y *= 2
y -= 1.5
y /= 2
y **= 2
print(y, type(y).__name__)

# ---- __format__, and what goes through it
for spec in ("", "f", ".1f", ".0f", "e", ".2e", "E", "g", ".2g", "G", "n", ".3n", "F", "10", "<10", ">10", "^10", "*^12", "*<12", "*>12", "+", "-", " ", "+.1f", " .1f", "-.1f", "#", "#.0f", "#g", "#e", "z", "z.1f", "12.3f", "<12.3f", "^12.3e", ",", ",.2f", "_", "_.2f", "20,.2f", ".,", ".3,f", "._f", ".3_f", "_.3_f", ".0", ".1", ".5", "10.2", "*>10.2", "+10.2", "+z.1f"):
    print(repr(spec), [format(v, spec) for v in (1 + 2j, 1j, 0j, -0j, complex(-0.0, 0.0), complex(0.0, -0.0), 1234567.125 + 7654321.5j, complex(-1.5, -2.5), complex(inf, -inf), complex(nan, nan), complex(0, inf), 1e20j, 1e-20 + 1e20j, complex(-0.001, -0.001))])
for spec in ("d", "b", "x", "o", "c", "s", "%", "r", "a", "05", "010.2f", "0", "=10", "*=10", "=+10.2f", "0>10", "0<10", "0^10", "00", ",d", ",s", "_x", "z,d"):
    print(repr(spec), failed(lambda: format(1 + 2j, spec)), end="; ")
print()
print("{}".format(1j), "{:.1f}".format(1 + 2j), "{0.real} {0.imag}".format(1 + 2j), "{!r}".format(1j), "{!s:>5}".format(1j), f"{1j}", f"{1 + 2j:.2f}", f"{1j!r}", f"{1j!s:>6}", f"{1j!a}", "%s %r %a" % (1j, 1j, 1j), "%5s|" % 1j, "%-8s|" % 1j, ascii(1j), str(1 + 2j), repr((1j,)), repr([1j]), repr({1j: 1j}), repr({1j}))  # type: ignore[str-format]

# ---- sum: the stages, compensated in both parts
print(sum([1j, 2j]), sum([1 + 1j, 2.5, 3]), sum([1.5, 1j, 2.5]), sum([1, 1j, 2]), sum([1j, True]), sum([], 1j), sum([1j], 1j), sum([1], 1j), sum([1.5], 1j), sum([True], 1j), sum([FloatSub(1.5)], 1j), sum([IntSub(1)], 1j), sum([C(1)], 1j), type(sum([C(1)], 1j)).__name__, sum([C(1), C(1)]), type(sum([C(1), C(1)])).__name__, sum([1j], C(1)), type(sum([1j], C(1))).__name__, sum([1e100j, 1j, -1e100j]), sum([1e100, 1j, -1e100]), sum([complex(1e100, 1e100), 1 + 1j, complex(-1e100, -1e100)]), sum([1j, 1e100, 1.0, -1e100]), sum([1.0, 1e100, 1j, 1.0, -1e100]), sum([1j, 2**100, -(2**100), 1]), sum([complex(-0.0, -0.0)], complex(-0.0, -0.0)), sum([complex(inf, 0), complex(-inf, 0)]), sum([complex(inf, inf), 1j]), sum([1e308j, 1e308j, -1e308j]), failed(lambda: sum([1j, "a"])), failed(lambda: sum([1j, None])), failed(lambda: sum([1j, 2**2000])), failed(lambda: sum([2**2000, 1j])), failed(lambda: sum(["a"], 1j)), failed(lambda: sum([1j], "a")))  # type: ignore[list-item]
print(sum([Radd()], 1j), sum([1j, Radd()]), sum([1j, Named(1)], 0.5), failed(lambda: sum([Radd(), 1j], 1j)), failed(lambda: sum([1j, Named(1), 1j], 0.5)))  # type: ignore[list-item,type-var]

# ---- the number system around it
print(isinstance(1j, object), type(1j) is not float, 1j.real.__class__.__name__, (1).real, (1).imag, (1.5).real, (1.5).imag, (1).conjugate(), (1.5).conjugate(), hasattr(1, "__complex__"), hasattr(1.5, "__complex__"), hasattr(1j, "__float__"), hasattr(1j, "__int__"), hasattr(1j, "__index__"), hasattr(1j, "__round__"), hasattr(1j, "__trunc__"), hasattr(1j, "__floor__"), hasattr(1j, "__ceil__"), hasattr(1j, "__mod__"), hasattr(1j, "__divmod__"), hasattr(1j, "__floordiv__"), hasattr(1j, "__rmod__"), hasattr(1j, "__radd__"), hasattr(1j, "__rpow__"), hasattr(complex, "from_number"), hasattr(complex, "real"), callable(1j.conjugate), complex.__doc__[:20])  # type: ignore[index]
