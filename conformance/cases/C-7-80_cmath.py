# clause: C-7-80
# spec: section 7
# status: P1
# source: dialect specification section 7, Numbers: cmath (C-7-08 stopped there)
"""cmath: every function on the 49 pairs of the seven classes of a double (C99 Annex G's special values: the
infinities, a negative and a positive finite number, the two zeros, NaN), with the signs of the zeros and NaNs it
gives and the class of the error it raises; finite arguments through each function's paths (large, subnormal, near
one, the overflow of cosh and exp), rounded since the C library's last bit is the host's; log with a base; phase,
polar, rect; isfinite, isinf, isnan and isclose with its tolerances; what the functions convert their arguments with
(__complex__, __float__, __index__, a complex subclass read as stored); the wrong calls; the constants and names."""
import cmath
import math

INF = float("inf")
NAN = float("nan")
CLASSES = (-INF, -2.5, -0.0, 0.0, 2.5, INF, NAN)


def part(x: float) -> str:
    if x != x:
        return "nan" if math.copysign(1.0, x) > 0 else "-nan"
    if x in (INF, -INF) or x == 0.0:
        return repr(x)
    return format(x, ".12g")


def shown(result: object) -> str:
    if isinstance(result, complex):
        return part(result.real) + "," + part(result.imag)
    if isinstance(result, bool):
        return repr(result)
    if isinstance(result, float):
        return part(result)
    if isinstance(result, tuple):
        return "(" + " ".join(shown(item) for item in result) + ")"
    return repr(result)


def outcome(function: object, *args: object, **kwds: object) -> str:
    try:
        result = function(*args, **kwds)  # type: ignore[operator]
    except Exception as exc:  # noqa: BLE001  # which exception, by class
        return type(exc).__name__
    return shown(result)


ONE = (cmath.acos, cmath.acosh, cmath.asin, cmath.asinh, cmath.atan, cmath.atanh, cmath.cos, cmath.cosh, cmath.exp, cmath.log,
       cmath.log10, cmath.sin, cmath.sinh, cmath.sqrt, cmath.tan, cmath.tanh, cmath.phase, cmath.polar, cmath.isfinite,
       cmath.isinf, cmath.isnan)
for function in ONE:
    for x in CLASSES:
        print(function.__name__, part(x), *(outcome(function, complex(x, y)) for y in CLASSES))
for r in CLASSES:
    print("rect", part(r), *(outcome(cmath.rect, r, phi) for phi in CLASSES))

VALUES = (complex(0.5, 0.25), complex(-3, 4), complex(3, -4), complex(1e-310, 1e-310), complex(-1e-310, 0.0), complex(0.0, 4e-320),
          complex(1e308, 1e308), complex(-1.5e308, 1.5e308), complex(1, 1e-300), complex(1, 0), complex(-1, -0.0), complex(1, 1e-20),
          complex(0.71, 0.0), complex(0.6, 0.8), complex(1.2, -0.9), complex(700, 1), complex(-709.5, 2), complex(709.5, -0.0),
          complex(800, 0.5), complex(-800, 0.5), complex(2.5, 1e300), complex(1e-20, 30), complex(20, 1e308))
for function in ONE:
    print(function.__name__, *(outcome(function, z) for z in VALUES))
print("rect", *(outcome(cmath.rect, r, phi) for r, phi in ((2.0, 0.5), (-3.0, -0.0), (1e308, 3.0), (2.0, 1e300), (-0.0, 2.0))))

BASES = ((8, 2), (0, 2), (1, 1), (2, 0), (0, 0), (1j, 1j), (complex(3, 4), complex(-1, 2)), (100, 10.0), (-8, -2), (INF, 2),
         (2, INF), (complex(NAN, 1), 2), (1e-310, 1e300), (2, 1 + 1e-16))
print("log base", *(outcome(cmath.log, z, base) for z, base in BASES))


class Complexish:
    def __init__(self, value: object) -> None:
        self.value = value

    def __complex__(self) -> complex:
        return self.value  # type: ignore[return-value]  # a wrong result on purpose for some rows


class Floatish:
    def __float__(self) -> float:
        return 4.0


class Indexish:
    def __index__(self) -> int:
        return 9


class Stored(complex):
    @property
    def real(self) -> float:
        return 100.0


class FloatSub(float):
    pass


class Raising:
    def __complex__(self) -> complex:
        raise KeyError("raised")


class NoneComplex:
    __complex__ = None


ARGS = (Complexish(complex(-4, 0)), Complexish(1.5), Complexish(None), Floatish(), Indexish(), Stored(-4, 0), FloatSub(-4.0), True,
        -9, 10**400, "4", None, Raising(), NoneComplex(), [1])
for function in (cmath.sqrt, cmath.phase, cmath.polar, cmath.isnan, cmath.log):
    print("argument", function.__name__, *(outcome(function, arg) for arg in ARGS))
print("base argument", *(outcome(cmath.log, 4, arg) for arg in ARGS))
print("rect argument", *(outcome(cmath.rect, arg, 0.5) for arg in ARGS), *(outcome(cmath.rect, 2.0, arg) for arg in ARGS))
print("isclose argument", *(outcome(cmath.isclose, arg, -4) for arg in ARGS))

CLOSE = ((1, 1 + 1e-10), (1, 1.1), (INF, INF), (INF, -INF), (complex(INF, 1), complex(INF, 2)), (NAN, NAN), (1j, 1j + 1e-10j),
         (complex(1e308, 1e308), complex(-1e308, -1e308)), (0, 1e-300), (complex(1, NAN), complex(1, NAN)))
print("isclose", *(outcome(cmath.isclose, a, b) for a, b in CLOSE))
print("isclose rel", *(outcome(cmath.isclose, a, b, rel_tol=0.2) for a, b in CLOSE))
print("isclose abs", *(outcome(cmath.isclose, a, b, abs_tol=1e-200) for a, b in CLOSE))
print("isclose tolerances", outcome(cmath.isclose, 1, 1, rel_tol=-1), outcome(cmath.isclose, 1, 1, abs_tol=-0.0),
      outcome(cmath.isclose, 1, 2, abs_tol=-1e-300), outcome(cmath.isclose, 1, 2, rel_tol=Floatish()), outcome(cmath.isclose, 1, 2, abs_tol=Indexish()),
      outcome(cmath.isclose, a=1, b=1 + 1e-12), outcome(cmath.isclose, 1, rel_tol=NAN, b=1.5), outcome(cmath.isclose, 1, 2, rel_tol=INF))

print("calls", outcome(cmath.sqrt), outcome(cmath.sqrt, 1, 2), outcome(cmath.sqrt, z=1), outcome(cmath.log), outcome(cmath.log, 1, 2, 3),
      outcome(cmath.log, 1, base=2), outcome(cmath.rect, 1), outcome(cmath.rect, 1, phi=2), outcome(cmath.isclose, 1),
      outcome(cmath.isclose, 1, 2, 3), outcome(cmath.isclose, a=1, b=1, c=2), outcome(cmath.isclose, 1, a=1), outcome(cmath.phase, 1, 2))

print("constants", cmath.pi, cmath.e, cmath.tau, cmath.inf, cmath.nan, cmath.infj, cmath.nanj, part(cmath.nan), part(cmath.nanj.imag),
      part(cmath.nanj.real), part(cmath.infj.real), cmath.pi == math.pi, cmath.e == math.e, cmath.tau == math.tau)
print("names", sorted(n for n in dir(cmath) if not n.startswith("_")), cmath.__name__, cmath.__doc__)
for name in sorted(n for n in dir(cmath) if not n.startswith("_")):
    value = getattr(cmath, name)
    if callable(value):
        print(name, type(value).__name__, value.__name__, value.__qualname__, value.__module__, repr(value), repr(value.__doc__))
    else:
        print(name, type(value).__name__)
