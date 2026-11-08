"""math, in Python (Modules/mathmodule.c) over the C library's functions (libm.cpp's `_libm`, answering the result and errno): the
wrappers math_1, math_1a and math_2 with their error rules and messages, CPython's own gamma, lgamma, sinpi, remainder, log, log2 and
log10, fsum (Shewchuk), hypot and dist (the double-length vector norm), sumprod (triple length), pow's special cases, nextafter with
steps, ulp, isclose, prod, floor, ceil and trunc through the special methods, ldexp, frexp, modf, the constants. comb, factorial, gcd,
isqrt, lcm and perm are math.integer's (runtime/prelude/_math_integer.py), set by the runtime when the module is made."""

__all__ = ["acos", "acosh", "asin", "asinh", "atan", "atan2", "atanh", "cbrt", "ceil", "copysign", "cos", "cosh", "degrees", "dist", "e",
           "erf", "erfc", "exp", "exp2", "expm1", "fabs", "floor", "fma", "fmax", "fmin", "fmod", "frexp", "fsum", "gamma", "hypot", "inf",
           "isclose", "isfinite", "isinf", "isnan", "isnormal", "issubnormal", "ldexp", "lgamma", "log", "log10", "log1p", "log2", "modf",
           "nan", "nextafter", "pi", "pow", "prod", "radians", "remainder", "signbit", "sin", "sinh", "sqrt", "sumprod", "tan", "tanh", "tau",
           "trunc", "ulp"]

__name__ = "math"

try:
    _tp_name                                     # noqa: B018  # Py_TYPE(o)->tp_name
    _libm                                        # noqa: B018  # the C library's function by name: (result, errno)
    _float_pack                                  # noqa: B018  # PyFloat_Pack8: a float's eight bytes
    _float_unpack                                # noqa: B018  # PyFloat_Unpack8
    _keyword_suggestion                          # noqa: B018  # _Py_CalculateSuggestions
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _libm: Callable[..., Any] = _missing
    _float_pack: Callable[..., bytes] = _missing
    _float_unpack: Callable[..., float] = _missing
    _keyword_suggestion: Callable[..., str | None] = _missing

    def _tp_name(o: object) -> str:
        return type(o).__name__


pi = 3.141592653589793
e = 2.718281828459045
tau = 6.283185307179586
inf = float("inf")
nan = float("nan")

_EDOM = 33
_ERANGE = 34
_INF = inf
_LONG_MAX = 2**63 - 1
_LONG_MIN = -(2**63)
_INT_MAX = 2**31 - 1
_INT_MIN = -(2**31)
_DBL_MIN = 2.2250738585072014e-308


# ---- the clinic's and the C API's conversions ------------------------------------------------------------------------------

def _index(value: object) -> int:                # PyNumber_Index
    if issubclass(type(value), int):
        return int.__index__(value)  # type: ignore[arg-type]
    index = getattr(type(value), "__index__", None)
    if index is None:
        raise TypeError("'" + _tp_name(value) + "' object cannot be interpreted as an integer")
    result = index(value)
    if not issubclass(type(result), int):
        raise TypeError("__index__ returned non-int (type " + _tp_name(result) + ")")
    return int.__index__(result)


def _as_double(value: object) -> float:          # PyFloat_AsDouble
    if issubclass(type(value), float):
        return float.__float__(value)  # type: ignore[arg-type]
    to_float = getattr(type(value), "__float__", None)
    if to_float is not None:
        result = to_float(value)
        if not issubclass(type(result), float):
            raise TypeError(_tp_name(value) + ".__float__ returned non-float (type " + _tp_name(result) + ")")
        return float.__float__(result)
    if hasattr(type(value), "__index__"):
        return float(_index(value))
    raise TypeError("must be real number, not " + _tp_name(value))


def _clinic_double(value: object) -> float:      # the clinic's `double`: PyFloat_AsDouble, a float itself read directly
    if type(value) is float:
        return value  # type: ignore[return-value]
    return _as_double(value)


def _one(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> object:   # METH_O
    if kwds:
        raise TypeError("math." + name + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("math." + name + "() takes exactly one argument (" + str(len(args)) + " given)")
    return args[0]


def _positional(name: str, args: tuple[object, ...], kwds: dict[str, object], low: int, high: int) -> None:   # _PyArg_CheckPositional
    if kwds:
        raise TypeError("math." + name + "() takes no keyword arguments")
    if len(args) < low:
        raise TypeError(name + " expected " + ("at least " if low < high else "") + str(low) + " argument" + ("" if low == 1 else "s") + ", got " + str(len(args)))
    if len(args) > high:
        raise TypeError(name + " expected " + ("at most " if low < high else "") + str(high) + " argument" + ("" if high == 1 else "s") + ", got " + str(len(args)))


def _isnan(x: float) -> bool:
    return x != x


def _isinf(x: float) -> bool:
    return x == _INF or x == -_INF


def _isfinite(x: float) -> bool:
    return x == x and x != _INF and x != -_INF


def _repr(x: float) -> str:                      # PyOS_double_to_string(x, 'r', 0, Py_DTSF_ADD_DOT_0)
    return float.__repr__(x)


def _is_error(r: float, err: int, raise_edom: bool) -> bool:   # is_error: True when an exception stands
    if err == _EDOM:
        if raise_edom:
            raise ValueError("math domain error")
        return True
    if err == _ERANGE:
        if abs(r) < 1.5:                         # an underflow the library reported; a zero or tiny result is kept
            return False
        raise OverflowError("math range error")
    raise ValueError(err, "Unexpected math error")


def _math_1(name: str, arg: object, can_overflow: bool, err_msg: str | None) -> float:   # math_1
    x = _as_double(arg)
    r, err = _libm(name, x)
    if _isnan(r) and not _isnan(x):
        return _domain_error(x, err_msg)
    if _isinf(r) and _isfinite(x):
        if can_overflow:
            raise OverflowError("math range error")
        return _domain_error(x, err_msg)
    if _isfinite(r) and err and _is_error(r, err, True):
        raise ValueError("math domain error")
    return r


def _domain_error(x: float, err_msg: str | None) -> float:
    if err_msg is not None:
        raise ValueError(err_msg.replace("%s", _repr(x)))
    raise ValueError("math domain error")


def _math_1a(result: tuple[float, int], x: float, err_msg: str | None) -> float:   # math_1a: the function set errno itself
    r, err = result
    if err and _is_error(r, err, err_msg is None):
        if err_msg is not None and err == _EDOM:
            raise ValueError(err_msg.replace("%s", _repr(x)))
        raise ValueError("math domain error")
    return r


def _math_2(name: str, args: tuple[object, ...], kwds: dict[str, object], funcname: str) -> float:   # math_2
    _positional(funcname, args, kwds, 2, 2)
    x = _as_double(args[0])
    y = _as_double(args[1])
    r, err = _libm(name, x, y)
    if _isnan(r):
        err = _EDOM if not _isnan(x) and not _isnan(y) else 0
    elif _isinf(r):
        err = _ERANGE if _isfinite(x) and _isfinite(y) else 0
    if err and _is_error(r, err, True):
        raise ValueError("math domain error")
    return r


# ---- the FUNC1 table ----------------------------------------------------------------------------------------------------------

def acos(*args: object, **kwds: object) -> float:
    """Return the arc cosine (measured in radians) of x.

The result is between 0 and pi."""
    return _math_1("acos", _one("acos", args, kwds), False, "expected a number in range from -1 up to 1, got %s")


def acosh(*args: object, **kwds: object) -> float:
    """Return the inverse hyperbolic cosine of x."""
    return _math_1("acosh", _one("acosh", args, kwds), False, "expected argument value not less than 1, got %s")


def asin(*args: object, **kwds: object) -> float:
    """Return the arc sine (measured in radians) of x.

The result is between -pi/2 and pi/2."""
    return _math_1("asin", _one("asin", args, kwds), False, "expected a number in range from -1 up to 1, got %s")


def asinh(*args: object, **kwds: object) -> float:
    """Return the inverse hyperbolic sine of x."""
    return _math_1("asinh", _one("asinh", args, kwds), False, None)


def atan(*args: object, **kwds: object) -> float:
    """Return the arc tangent (measured in radians) of x.

The result is between -pi/2 and pi/2."""
    return _math_1("atan", _one("atan", args, kwds), False, None)


def atan2(*args: object, **kwds: object) -> float:
    """Return the arc tangent (measured in radians) of y/x.

Unlike atan(y/x), the signs of both x and y are considered."""
    return _math_2("atan2", args, kwds, "atan2")


def atanh(*args: object, **kwds: object) -> float:
    """Return the inverse hyperbolic tangent of x."""
    return _math_1("atanh", _one("atanh", args, kwds), False, "expected a number between -1 and 1, got %s")


def cbrt(*args: object, **kwds: object) -> float:
    """Return the cube root of x."""
    return _math_1("cbrt", _one("cbrt", args, kwds), False, None)


def copysign(*args: object, **kwds: object) -> float:
    """Return a float with the magnitude (absolute value) of x but the sign of y.

On platforms that support signed zeros, copysign(1.0, -0.0)
returns -1.0.
"""
    return _math_2("copysign", args, kwds, "copysign")


def cos(*args: object, **kwds: object) -> float:
    """Return the cosine of x (measured in radians)."""
    return _math_1("cos", _one("cos", args, kwds), False, "expected a finite input, got %s")


def cosh(*args: object, **kwds: object) -> float:
    """Return the hyperbolic cosine of x."""
    return _math_1("cosh", _one("cosh", args, kwds), True, None)


def erf(*args: object, **kwds: object) -> float:
    """Error function at x."""
    x = _as_double(_one("erf", args, kwds))
    return _math_1a(_libm("erf", x), x, None)


def erfc(*args: object, **kwds: object) -> float:
    """Complementary error function at x."""
    x = _as_double(_one("erfc", args, kwds))
    return _math_1a(_libm("erfc", x), x, None)


def exp(*args: object, **kwds: object) -> float:
    """Return e raised to the power of x."""
    return _math_1("exp", _one("exp", args, kwds), True, None)


def exp2(*args: object, **kwds: object) -> float:
    """Return 2 raised to the power of x."""
    return _math_1("exp2", _one("exp2", args, kwds), True, None)


def expm1(*args: object, **kwds: object) -> float:
    """Return exp(x)-1.

This function avoids the loss of precision involved in the direct evaluation of exp(x)-1 for small x."""
    return _math_1("expm1", _one("expm1", args, kwds), True, None)


def fabs(*args: object, **kwds: object) -> float:
    """Return the absolute value of the float x."""
    return _math_1("fabs", _one("fabs", args, kwds), False, None)


def log1p(*args: object, **kwds: object) -> float:
    """Return the natural logarithm of 1+x (base e).

The result is computed in a way which is accurate for x near zero."""
    x = _as_double(_one("log1p", args, kwds))
    if x == 0.0:                                 # _Py_log1p: the sign of a zero kept
        return x
    return _math_1_value("log1p", x, False, "expected argument value > -1, got %s")


def _math_1_value(name: str, x: float, can_overflow: bool, err_msg: str | None) -> float:   # math_1 on a converted double
    r, err = _libm(name, x)
    if _isnan(r) and not _isnan(x):
        return _domain_error(x, err_msg)
    if _isinf(r) and _isfinite(x):
        if can_overflow:
            raise OverflowError("math range error")
        return _domain_error(x, err_msg)
    if _isfinite(r) and err and _is_error(r, err, True):
        raise ValueError("math domain error")
    return r


def sin(*args: object, **kwds: object) -> float:
    """Return the sine of x (measured in radians)."""
    return _math_1("sin", _one("sin", args, kwds), False, "expected a finite input, got %s")


def sinh(*args: object, **kwds: object) -> float:
    """Return the hyperbolic sine of x."""
    return _math_1("sinh", _one("sinh", args, kwds), True, None)


def sqrt(*args: object, **kwds: object) -> float:
    """Return the square root of x."""
    return _math_1("sqrt", _one("sqrt", args, kwds), False, "expected a nonnegative input, got %s")


def tan(*args: object, **kwds: object) -> float:
    """Return the tangent of x (measured in radians)."""
    return _math_1("tan", _one("tan", args, kwds), False, "expected a finite input, got %s")


def tanh(*args: object, **kwds: object) -> float:
    """Return the hyperbolic tangent of x."""
    return _math_1("tanh", _one("tanh", args, kwds), False, None)


# ---- gamma, lgamma (m_tgamma, m_lgamma, m_sinpi, lanczos_sum) -------------------------------------------------------------------

_LANCZOS_N = 13
_LANCZOS_G = 6.024680040776729583740234375
_LANCZOS_G_MINUS_HALF = 5.524680040776729583740234375
_LANCZOS_NUM = (23531376880.410759688572007674451636754734846804940, 42919803642.649098768957899047001988850926355848959,
                35711959237.355668049440185451547166705960488635843, 17921034426.037209699919755754458931112671403265390,
                6039542586.3520280050642916443072979210699388420708, 1439720407.3117216736632230727949123939715485786772,
                248874557.86205415651146038641322942321632125127801, 31426415.585400194380614231628318205362874684987640,
                2876370.6289353724412254090516208496135991145378768, 186056.26539522349504029498971604569928220784236328,
                8071.6720023658162106380029022722506138218516325024, 210.82427775157934587250973392071336271166969580291,
                2.5066282746310002701649081771338373386264310793408)
_LANCZOS_DEN = (0.0, 39916800.0, 120543840.0, 150917976.0, 105258076.0, 45995730.0, 13339535.0, 2637558.0, 357423.0, 32670.0, 1925.0, 66.0, 1.0)
_GAMMA_INTEGRAL = (1.0, 1.0, 2.0, 6.0, 24.0, 120.0, 720.0, 5040.0, 40320.0, 362880.0, 3628800.0, 39916800.0, 479001600.0, 6227020800.0,
                   87178291200.0, 1307674368000.0, 20922789888000.0, 355687428096000.0, 6402373705728000.0, 121645100408832000.0,
                   2432902008176640000.0, 51090942171709440000.0, 1124000727777607680000.0)
_LOGPI = 1.144729885849400174143427351353058711647


def _c(name: str, *values: float) -> float:      # the library's function, errno dropped
    return _libm(name, *values)[0]  # type: ignore[no-any-return]


def _sinpi(x: float) -> float:                   # m_sinpi, for finite x
    y = _c("fmod", abs(x), 2.0)
    n = int(_c("round", 2.0 * y))
    if n == 0:
        r = _c("sin", pi * y)
    elif n == 1:
        r = _c("cos", pi * (y - 0.5))
    elif n == 2:
        r = _c("sin", pi * (1.0 - y))
    elif n == 3:
        r = -_c("cos", pi * (y - 1.5))
    else:
        r = _c("sin", pi * (y - 2.0))
    return _c("copysign", 1.0, x) * r


def _lanczos_sum(x: float) -> float:
    num = 0.0
    den = 0.0
    if x < 5.0:
        for i in range(_LANCZOS_N - 1, -1, -1):
            num = num * x + _LANCZOS_NUM[i]
            den = den * x + _LANCZOS_DEN[i]
    else:
        for i in range(_LANCZOS_N):
            num = num / x + _LANCZOS_NUM[i]
            den = den / x + _LANCZOS_DEN[i]
    return num / den


def _tgamma(x: float) -> tuple[float, int]:      # m_tgamma: the value and errno
    if not _isfinite(x):
        if _isnan(x) or x > 0.0:
            return x, 0
        return nan, _EDOM
    if x == 0.0:
        return _c("copysign", _INF, x), _EDOM
    if x == _c("floor", x):
        if x < 0.0:
            return nan, _EDOM
        if x <= 23:
            return _GAMMA_INTEGRAL[int(x) - 1], 0
    absx = abs(x)
    if absx < 1e-20:
        r = 1.0 / x
        return r, (_ERANGE if _isinf(r) else 0)
    if absx > 200.0:
        if x < 0.0:
            return 0.0 / _sinpi(x), 0
        return _INF, _ERANGE
    y = absx + _LANCZOS_G_MINUS_HALF
    if absx > _LANCZOS_G_MINUS_HALF:
        q = y - absx
        z = q - _LANCZOS_G_MINUS_HALF
    else:
        q = y - _LANCZOS_G_MINUS_HALF
        z = q - absx
    z = z * _LANCZOS_G / y
    if x < 0.0:
        r = -pi / _sinpi(absx) / absx * _c("exp", y) / _lanczos_sum(absx)
        r -= z * r
        if absx < 140.0:
            r /= _c("pow", y, absx - 0.5)
        else:
            sqrtpow = _c("pow", y, absx / 2.0 - 0.25)
            r /= sqrtpow
            r /= sqrtpow
    else:
        r = _lanczos_sum(absx) / _c("exp", y)
        r += z * r
        if absx < 140.0:
            r *= _c("pow", y, absx - 0.5)
        else:
            sqrtpow = _c("pow", y, absx / 2.0 - 0.25)
            r *= sqrtpow
            r *= sqrtpow
    return r, (_ERANGE if _isinf(r) else 0)


def _lgamma(x: float) -> tuple[float, int]:      # m_lgamma
    if not _isfinite(x):
        if _isnan(x):
            return x, 0
        return _INF, 0
    if x == _c("floor", x) and x <= 2.0:
        if x <= 0.0:
            return _INF, _EDOM
        return 0.0, 0
    absx = abs(x)
    if absx < 1e-20:
        return -_c("log", absx), 0
    r = _c("log", _lanczos_sum(absx)) - _LANCZOS_G
    r += (absx - 0.5) * (_c("log", absx + _LANCZOS_G - 0.5) - 1)
    if x < 0.0:
        r = _LOGPI - _c("log", abs(_sinpi(absx))) - _c("log", absx) - r
    return r, (_ERANGE if _isinf(r) else 0)


def gamma(*args: object, **kwds: object) -> float:
    """Gamma function at x."""
    x = _as_double(_one("gamma", args, kwds))
    return _math_1a(_tgamma(x), x, "expected a noninteger or positive integer, got %s")


def lgamma(*args: object, **kwds: object) -> float:
    """Natural logarithm of absolute value of Gamma function at x."""
    x = _as_double(_one("lgamma", args, kwds))
    return _math_1a(_lgamma(x), x, "expected a noninteger or positive integer, got %s")


# ---- remainder (m_remainder) ------------------------------------------------------------------------------------------------

def _remainder(x: float, y: float) -> float:
    if _isfinite(x) and _isfinite(y):
        if y == 0.0:
            return nan
        absx = abs(x)
        absy = abs(y)
        m = _c("fmod", absx, absy)
        c = absy - m
        if m < c:
            r = m
        elif m > c:
            r = -c
        else:
            r = m - 2.0 * _c("fmod", 0.5 * (absx - m), absy)
        return _c("copysign", 1.0, x) * r
    if _isnan(x):
        return x
    if _isnan(y):
        return y
    if _isinf(x):
        return nan
    return x


def remainder(*args: object, **kwds: object) -> float:
    """Difference between x and the closest integer multiple of y.

Return x - n*y where n*y is the closest integer multiple of y.
In the case where x is exactly halfway between two multiples of
y, the nearest even value of n is used. The result is always exact."""
    _positional("remainder", args, kwds, 2, 2)
    x = _as_double(args[0])
    y = _as_double(args[1])
    r = _remainder(x, y)
    err = 0
    if _isnan(r):
        err = _EDOM if not _isnan(x) and not _isnan(y) else 0
    elif _isinf(r):
        err = _ERANGE if _isfinite(x) and _isfinite(y) else 0
    if err and _is_error(r, err, True):
        raise ValueError("math domain error")
    return r


# ---- floor, ceil, trunc -----------------------------------------------------------------------------------------------------

def _special(value: object, name: str) -> object:   # _PyObject_MaybeCallSpecialNoArgs: the type's method, or _ABSENT
    method = getattr(type(value), name, None)
    if method is None:
        return _ABSENT
    return method(value)


_ABSENT: object = object()


def _from_double(x: float) -> int:               # PyLong_FromDouble
    if _isnan(x):
        raise ValueError("cannot convert float NaN to integer")
    if _isinf(x):
        raise OverflowError("cannot convert float infinity to integer")
    return int(x)


def ceil(*args: object, **kwds: object) -> object:
    """Return the ceiling of x as an Integral.

This is the smallest integer >= x."""
    number = _one("ceil", args, kwds)
    if type(number) is float:
        x: float = number  # type: ignore[assignment]
    else:
        result = _special(number, "__ceil__")
        if result is not _ABSENT:
            return result
        x = _as_double(number)
    return _from_double(_c("ceil", x))


def floor(*args: object, **kwds: object) -> object:
    """Return the floor of x as an Integral.

This is the largest integer <= x."""
    number = _one("floor", args, kwds)
    if type(number) is float:
        x: float = number  # type: ignore[assignment]
    else:
        result = _special(number, "__floor__")
        if result is not _ABSENT:
            return result
        x = _as_double(number)
    return _from_double(_c("floor", x))


def trunc(*args: object, **kwds: object) -> object:
    """Truncates the Real x to the nearest Integral toward 0.

Uses the __trunc__ magic method."""
    x = _one("trunc", args, kwds)
    if type(x) is float:
        return float.__int__(x)  # type: ignore[arg-type]
    result = _special(x, "__trunc__")
    if result is _ABSENT:
        raise TypeError("type " + _tp_name(x) + " doesn't define __trunc__ method")
    return result


# ---- fmax, fmin, signbit, isfinite and the rest of the one-liners ---------------------------------------------------------------

def _two_doubles(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> tuple[float, float]:   # the clinic: two positional doubles
    if kwds:
        raise TypeError("math." + name + "() takes no keyword arguments")
    if len(args) != 2:
        raise TypeError(name + " expected 2 arguments, got " + str(len(args)))
    return _clinic_double(args[0]), _clinic_double(args[1])


def fmax(*args: object, **kwds: object) -> float:
    """Return the larger of two floating-point arguments.

Equivalent to the C99 fmax() function: the result is the greater of the
arguments, unless one is a NaN, in which case the other is returned."""
    x, y = _two_doubles("fmax", args, kwds)
    return _c("fmax", x, y)


def fmin(*args: object, **kwds: object) -> float:
    """Return the smaller of two floating-point arguments.

Equivalent to the C99 fmin() function: the result is the lesser of the
arguments, unless one is a NaN, in which case the other is returned."""
    x, y = _two_doubles("fmin", args, kwds)
    return _c("fmin", x, y)


def signbit(*args: object, **kwds: object) -> bool:
    """Return True if the sign of x is negative and False otherwise."""
    x = _clinic_double(_one("signbit", args, kwds))
    return _c("copysign", 1.0, x) < 0.0


def isfinite(*args: object, **kwds: object) -> bool:
    """Return True if x is neither an infinity nor a NaN, and False otherwise."""
    return _isfinite(_clinic_double(_one("isfinite", args, kwds)))


def isinf(*args: object, **kwds: object) -> bool:
    """Return True if x is a positive or negative infinity, and False otherwise."""
    return _isinf(_clinic_double(_one("isinf", args, kwds)))


def isnan(*args: object, **kwds: object) -> bool:
    """Return True if x is a NaN (not a number), and False otherwise."""
    return _isnan(_clinic_double(_one("isnan", args, kwds)))


def isnormal(*args: object, **kwds: object) -> bool:
    """Return True if x is normal, and False otherwise."""
    x = _clinic_double(_one("isnormal", args, kwds))
    return _isfinite(x) and abs(x) >= _DBL_MIN


def issubnormal(*args: object, **kwds: object) -> bool:
    """Return True if x is subnormal, and False otherwise."""
    x = _clinic_double(_one("issubnormal", args, kwds))
    return _isfinite(x) and x != 0.0 and abs(x) < _DBL_MIN


def degrees(*args: object, **kwds: object) -> float:
    """Convert angle x from radians to degrees."""
    return _clinic_double(_one("degrees", args, kwds)) * (180.0 / pi)


def radians(*args: object, **kwds: object) -> float:
    """Convert angle x from degrees to radians."""
    return _clinic_double(_one("radians", args, kwds)) * (pi / 180.0)


# ---- frexp, ldexp, modf -----------------------------------------------------------------------------------------------------

def frexp(*args: object, **kwds: object) -> tuple[float, int]:
    """Return the mantissa and exponent of x, as pair (m, e).

m is a float and e is an int, such that x = m * 2.**e.
If x is 0, m and e are both 0.  Else 0.5 <= abs(m) < 1.0."""
    x = _clinic_double(_one("frexp", args, kwds))
    if _isnan(x) or _isinf(x) or not x:
        return x, 0
    (m, exponent), _ = _libm("frexp", x)
    return m, exponent


def ldexp(*args: object, **kwds: object) -> float:
    """Return x * (2**i).

This is essentially the inverse of frexp()."""
    _positional("ldexp", args, kwds, 2, 2)
    x = _clinic_double(args[0])
    i = args[1]
    if not issubclass(type(i), int):
        raise TypeError("Expected an int as second argument to ldexp.")
    exponent = int.__index__(i)  # type: ignore[arg-type]
    if exponent > _LONG_MAX:                     # PyLong_AsLongAndOverflow's clamp
        exponent = _LONG_MAX
    elif exponent < _LONG_MIN:
        exponent = _LONG_MIN
    if x == 0.0 or not _isfinite(x):
        r = x
        err = 0
    elif exponent > _INT_MAX:
        r = _c("copysign", _INF, x)
        err = _ERANGE
    elif exponent < _INT_MIN:
        r = _c("copysign", 0.0, x)
        err = 0
    else:
        r, err = _libm("ldexp", x, exponent)
        if _isinf(r):
            err = _ERANGE
    if err and _is_error(r, err, True):
        raise ValueError("math domain error")
    return r


def modf(*args: object, **kwds: object) -> tuple[float, float]:
    """Return the fractional and integer parts of x.

Both results carry the sign of x and are floats."""
    x = _clinic_double(_one("modf", args, kwds))
    if _isinf(x):
        return _c("copysign", 0.0, x), x
    if _isnan(x):
        return x, x
    (frac, whole), _ = _libm("modf", x)
    return frac, whole


# ---- log, log2, log10 (m_log, m_log2, m_log10, loghelper) ---------------------------------------------------------------------

def _m_log(name: str, x: float) -> tuple[float, int]:   # m_log, m_log2, m_log10: the special values, the library for the rest
    if _isfinite(x):
        if x > 0.0:
            return _libm(name, x)  # type: ignore[no-any-return]
        return (-_INF if x == 0.0 else nan), _EDOM
    if _isnan(x):
        return x, 0
    if x > 0.0:
        return x, 0
    return nan, _EDOM


def _loghelper_int(arg: int, name: str) -> float:   # loghelper_int: a large int through its frexp
    if arg <= 0:
        raise ValueError("expected a positive input")
    try:
        x = float(arg)
    except OverflowError:
        bits = arg.bit_length()
        x = arg / (1 << bits)                    # _PyLong_Frexp: the correctly rounded mantissa in [0.5, 1)
        return _c("fma", _m_log(name, 2.0)[0], float(bits), _m_log(name, x)[0])
    return _m_log(name, x)[0]


def _loghelper(arg: object, name: str) -> float:
    if issubclass(type(arg), int):
        return _loghelper_int(int.__index__(arg), name)  # type: ignore[arg-type]
    try:
        x = _as_double(arg)
    except OverflowError:
        if hasattr(type(arg), "__index__"):
            return _loghelper_int(_index(arg), name)
        raise
    r, err = _m_log(name, x)
    if _isnan(r) and not _isnan(x):
        return _domain_error(x, "expected a positive input, got %s")
    if _isinf(r) and _isfinite(x):
        return _domain_error(x, "expected a positive input, got %s")
    if _isfinite(r) and err and _is_error(r, err, True):
        raise ValueError("math domain error")
    return r


def log(*args: object, **kwds: object) -> float:
    """log(x, [base=math.e])
Return the logarithm of x to the given base.

If the base is not specified, returns the natural logarithm (base e) of x."""
    _positional("log", args, kwds, 1, 2)
    num = _loghelper(args[0], "log")
    if len(args) == 1:
        return num
    den = _loghelper(args[1], "log")
    return num / den


def log2(*args: object, **kwds: object) -> float:
    """Return the base 2 logarithm of x."""
    return _loghelper(_one("log2", args, kwds), "log2")


def log10(*args: object, **kwds: object) -> float:
    """Return the base 10 logarithm of x."""
    return _loghelper(_one("log10", args, kwds), "log10")


# ---- fma, fmod, pow ---------------------------------------------------------------------------------------------------------

def fma(*args: object, **kwds: object) -> float:
    """Fused multiply-add operation.

Compute (x * y) + z with a single round."""
    if kwds:
        raise TypeError("math.fma() takes no keyword arguments")
    if len(args) != 3:
        raise TypeError("fma expected 3 arguments, got " + str(len(args)))
    x, y, z = _clinic_double(args[0]), _clinic_double(args[1]), _clinic_double(args[2])
    r = _c("fma", x, y, z)
    if _isfinite(r):
        return r
    if _isnan(r):
        if not _isnan(x) and not _isnan(y) and not _isnan(z):
            raise ValueError("invalid operation in fma")
    elif _isfinite(x) and _isfinite(y) and _isfinite(z):
        raise OverflowError("overflow in fma")
    return r


def fmod(*args: object, **kwds: object) -> float:
    """Return fmod(x, y), according to platform C.

x % y may differ."""
    x, y = _two_doubles("fmod", args, kwds)
    if _isinf(y) and _isfinite(x):
        return x
    r, err = _libm("fmod", x, y)
    if _isnan(r):
        err = _EDOM if not _isnan(x) and not _isnan(y) else 0
    if err and _is_error(r, err, True):
        raise ValueError("math domain error")
    return r


def pow(*args: object, **kwds: object) -> float:  # noqa: A001
    """Return x**y (x to the power of y)."""
    x, y = _two_doubles("pow", args, kwds)
    err = 0
    if not _isfinite(x) or not _isfinite(y):
        if _isnan(x):
            r = 1.0 if y == 0.0 else x
        elif _isnan(y):
            r = 1.0 if x == 1.0 else y
        elif _isinf(x):
            odd_y = _isfinite(y) and _c("fmod", abs(y), 2.0) == 1.0
            if y > 0.0:
                r = x if odd_y else abs(x)
            elif y == 0.0:
                r = 1.0
            else:
                r = _c("copysign", 0.0, x) if odd_y else 0.0
        elif abs(x) == 1.0:
            r = 1.0
        elif y > 0.0 and abs(x) > 1.0:
            r = y
        elif y < 0.0 and abs(x) < 1.0:
            r = -y
        else:
            r = 0.0
    else:
        r, err = _libm("pow", x, y)
        if not _isfinite(r):
            if _isnan(r):
                err = _EDOM
            elif _isinf(r):
                err = _EDOM if x == 0.0 else _ERANGE
    if err and _is_error(r, err, True):
        raise ValueError("math domain error")
    return r


# ---- fsum (Shewchuk, as msum) -------------------------------------------------------------------------------------------------

def _assign_double(item: object) -> float:       # ASSIGN_DOUBLE
    if type(item) is float:
        return item  # type: ignore[return-value]
    if type(item) is int:
        return float(item)  # type: ignore[arg-type]
    return _as_double(item)


def fsum(*args: object, **kwds: object) -> float:
    """Return an accurate floating-point sum of values in the iterable seq.

Assumes IEEE-754 floating-point arithmetic."""
    seq = _one("fsum", args, kwds)
    partials: list[float] = []
    special_sum = 0.0
    inf_sum = 0.0
    for item in seq:  # type: ignore[attr-defined]
        x = _assign_double(item)
        xsave = x
        i = 0
        for j in range(len(partials)):
            y = partials[j]
            if abs(x) < abs(y):
                x, y = y, x
            hi = x + y
            yr = hi - x
            lo = y - yr
            if lo != 0.0:
                partials[i] = lo
                i += 1
            x = hi
        del partials[i:]
        if x != 0.0:
            if not _isfinite(x):
                if _isfinite(xsave):
                    raise OverflowError("intermediate overflow in fsum")
                if _isinf(xsave):
                    inf_sum += xsave
                special_sum += xsave
                del partials[:]
            else:
                partials.append(x)
    if special_sum != 0.0:
        if _isnan(inf_sum):
            raise ValueError("-inf + inf in fsum")
        return special_sum
    hi = 0.0
    n = len(partials)
    if n > 0:
        n -= 1
        hi = partials[n]
        lo = 0.0
        while n > 0:
            x = hi
            n -= 1
            y = partials[n]
            hi = x + y
            yr = hi - x
            lo = y - yr
            if lo != 0.0:
                break
        if n > 0 and ((lo < 0.0 and partials[n - 1] < 0.0) or (lo > 0.0 and partials[n - 1] > 0.0)):
            y = lo * 2.0
            x = hi + y
            yr = x - hi
            if y == yr:
                hi = x
    return hi


# ---- hypot, dist (vector_norm) ----------------------------------------------------------------------------------------------

def _dl_mul(x: float, y: float) -> tuple[float, float]:   # dl_mul: the product and its error, through fma
    z = x * y
    zz = _c("fma", x, y, -z)
    return z, zz


def _dl_fast_sum(a: float, b: float) -> tuple[float, float]:
    x = a + b
    y = (a - x) + b
    return x, y


def _dl_sum(a: float, b: float) -> tuple[float, float]:
    x = a + b
    z = x - a
    y = (a - (x - z)) + (b - z)
    return x, y


def _vector_norm(vec: list[float], largest: float, found_nan: bool) -> float:   # vector_norm
    if _isinf(largest):
        return largest
    if found_nan:
        return nan
    n = len(vec)
    if largest == 0.0 or n <= 1:
        return largest
    (_, max_e), _ = _libm("frexp", largest)
    if max_e < -1023:
        return _DBL_MIN * _vector_norm([v / _DBL_MIN for v in vec], largest / _DBL_MIN, found_nan)
    scale = _c("ldexp", 1.0, -max_e)
    csum = 1.0
    frac1 = 0.0
    frac2 = 0.0
    for v in vec:
        x = v * scale
        pr_hi, pr_lo = _dl_mul(x, x)
        sm_hi, sm_lo = _dl_fast_sum(csum, pr_hi)
        csum = sm_hi
        frac1 += pr_lo
        frac2 += sm_lo
    h = _c("sqrt", csum - 1.0 + (frac1 + frac2))
    pr_hi, pr_lo = _dl_mul(-h, h)
    sm_hi, sm_lo = _dl_fast_sum(csum, pr_hi)
    csum = sm_hi
    frac1 += pr_lo
    frac2 += sm_lo
    x = csum - 1.0 + (frac1 + frac2)
    h += x / (2.0 * h)
    return h / scale


def hypot(*args: object, **kwds: object) -> float:
    """hypot(*coordinates) -> value

Multidimensional Euclidean distance from the origin to a point.

Roughly equivalent to:
    sqrt(sum(x**2 for x in coordinates))

For a two dimensional point (x, y), gives the hypotenuse
using the Pythagorean theorem:  sqrt(x*x + y*y).

For example, the hypotenuse of a 3/4/5 right triangle is:

    >>> hypot(3.0, 4.0)
    5.0
"""
    if kwds:
        raise TypeError("math.hypot() takes no keyword arguments")
    largest = 0.0
    found_nan = False
    coordinates: list[float] = []
    for item in args:
        x = abs(_assign_double(item))
        coordinates.append(x)
        found_nan = found_nan or _isnan(x)
        if x > largest:
            largest = x
    return _vector_norm(coordinates, largest, found_nan)


def dist(*args: object, **kwds: object) -> float:
    """Return the Euclidean distance between two points p and q.

The points should be specified as sequences (or iterables) of
coordinates.  Both inputs must have the same dimension.

Roughly equivalent to:
    sqrt(sum((px - qx) ** 2.0 for px, qx in zip(p, q)))"""
    _positional("dist", args, kwds, 2, 2)
    p, q = args
    if not issubclass(type(p), tuple):
        p = tuple(p)  # type: ignore[call-overload]
    if not issubclass(type(q), tuple):
        q = tuple(q)  # type: ignore[call-overload]
    if len(p) != len(q):  # type: ignore[arg-type]
        raise ValueError("both points must have the same number of dimensions")
    largest = 0.0
    found_nan = False
    diffs: list[float] = []
    for i in range(len(p)):  # type: ignore[arg-type]
        px = _assign_double(p[i])  # type: ignore[index]
        qx = _assign_double(q[i])  # type: ignore[index]
        x = abs(px - qx)
        diffs.append(x)
        found_nan = found_nan or _isnan(x)
        if x > largest:
            largest = x
    return _vector_norm(diffs, largest, found_nan)


# ---- sumprod (triple length) -------------------------------------------------------------------------------------------------

def _tl_fma(x: float, y: float, total: tuple[float, float, float]) -> tuple[float, float, float]:
    pr_hi, pr_lo = _dl_mul(x, y)
    sm_hi, sm_lo = _dl_sum(total[0], pr_hi)
    r1_hi, r1_lo = _dl_sum(total[1], pr_lo)
    r2_hi, r2_lo = _dl_sum(r1_hi, sm_lo)
    return sm_hi, r2_hi, total[2] + r1_lo + r2_lo


def _tl_to_d(total: tuple[float, float, float]) -> float:
    last_hi, last_lo = _dl_sum(total[1], total[0])
    return total[2] + last_lo + last_hi


def _long_fits(v: int) -> bool:
    return _LONG_MIN <= v <= _LONG_MAX


def sumprod(*args: object, **kwds: object) -> object:
    """Return the sum of products of values from two iterables p and q.

Roughly equivalent to:

    sum(map(operator.mul, p, q, strict=True))

For float and mixed int/float inputs, the intermediate products
and sums are computed with extended precision."""
    _positional("sumprod", args, kwds, 2, 2)
    p_it = iter(args[0])  # type: ignore[call-overload]
    q_it = iter(args[1])  # type: ignore[call-overload]
    total: object = 0
    int_path = True
    int_total = 0
    int_in_use = False
    flt_path = True
    flt_total = (0.0, 0.0, 0.0)
    flt_in_use = False
    sentinel = object()
    while True:
        p_i = next(p_it, sentinel)
        q_i = next(q_it, sentinel)
        p_stopped = p_i is sentinel
        q_stopped = q_i is sentinel
        if p_stopped != q_stopped:
            raise ValueError("Inputs are not the same length")
        finished = p_stopped and q_stopped
        if int_path:
            if not finished and type(p_i) is int and type(q_i) is int:
                if _long_fits(p_i) and _long_fits(q_i):  # type: ignore[arg-type]
                    prod_i = p_i * q_i  # type: ignore[operator]
                    if _long_fits(prod_i) and _long_fits(int_total + prod_i):
                        int_total += prod_i
                        int_in_use = True
                        continue
            int_path = False
            if int_in_use:
                total = total + int_total  # type: ignore[operator]
                int_total = 0
                int_in_use = False
        if flt_path:
            if not finished:
                flt_p: float | None = None
                flt_q: float | None = None
                if type(p_i) is float and type(q_i) is float:
                    flt_p, flt_q = p_i, q_i  # type: ignore[assignment]
                elif type(p_i) is float and (type(q_i) is int or type(q_i) is bool):
                    flt_p = p_i  # type: ignore[assignment]
                    flt_q = _long_to_double(q_i)
                elif type(q_i) is float and (type(p_i) is int or type(p_i) is bool):
                    flt_q = q_i  # type: ignore[assignment]
                    flt_p = _long_to_double(p_i)
                if flt_p is not None and flt_q is not None:
                    new_total = _tl_fma(flt_p, flt_q, flt_total)
                    if _isfinite(new_total[0]):
                        flt_total = new_total
                        flt_in_use = True
                        continue
            flt_path = False
            if flt_in_use:
                total = total + _tl_to_d(flt_total)  # type: ignore[operator]
                flt_total = (0.0, 0.0, 0.0)
                flt_in_use = False
        if finished:
            return total
        total = total + p_i * q_i  # type: ignore[operator]


def _long_to_double(v: object) -> float | None:  # PyLong_AsDouble, None where it overflows (the float path then ends)
    try:
        return float(v)  # type: ignore[arg-type]
    except OverflowError:
        return None


# ---- isclose, prod, nextafter, ulp ----------------------------------------------------------------------------------------------

def isclose(*args: object, **kwds: object) -> bool:
    """Determine whether two floating-point numbers are close in value.

  rel_tol
    maximum difference for being considered "close", relative to the
    magnitude of the input values
  abs_tol
    maximum difference for being considered "close", regardless of the
    magnitude of the input values

Return True if a is close in value to b, and False otherwise.

For the values to be considered close, the difference between them
must be smaller than at least one of the tolerances.

-inf, inf and NaN behave similarly to the IEEE 754 Standard.  That
is, NaN is not close to anything, even itself.  inf and -inf are
only close to themselves."""
    names = ("a", "b", "rel_tol", "abs_tol")
    nargs = len(args)
    if nargs + len(kwds) > 4:
        raise TypeError("isclose() takes at most 4 arguments (" + str(nargs + len(kwds)) + " given)")
    if nargs > 2:
        raise TypeError("isclose() takes exactly 2 positional arguments (" + str(nargs) + " given)")
    values: list[object] = [*args, *[_ABSENT] * (4 - nargs)]
    for keyword, value in kwds.items():
        if keyword not in names:
            suggestion = _keyword_suggestion(names, keyword)
            if suggestion is not None:
                raise TypeError("isclose() got an unexpected keyword argument '" + keyword + "'. Did you mean '" + suggestion + "'?")
            raise TypeError("isclose() got an unexpected keyword argument '" + keyword + "'")
        at = names.index(keyword)
        if at < nargs:
            raise TypeError("argument for isclose() given by name ('" + keyword + "') and position (" + str(at + 1) + ")")
        values[at] = value
    for at in range(2):
        if values[at] is _ABSENT:
            raise TypeError("isclose() missing required argument '" + names[at] + "' (pos " + str(at + 1) + ")")
    a = _clinic_double(values[0])
    b = _clinic_double(values[1])
    rel_tol = 1e-09 if values[2] is _ABSENT else _clinic_double(values[2])
    abs_tol = 0.0 if values[3] is _ABSENT else _clinic_double(values[3])
    if rel_tol < 0.0 or abs_tol < 0.0:
        raise ValueError("tolerances must be non-negative")
    if a == b:
        return True
    if _isinf(a) or _isinf(b):
        return False
    diff = abs(b - a)
    return diff <= abs(rel_tol * b) or diff <= abs(rel_tol * a) or diff <= abs_tol


def prod(*args: object, **kwds: object) -> object:
    """Calculate the product of all the elements in the input iterable.

The default start value for the product is 1.

When the iterable is empty, return the start value.  This function is
intended specifically for use with numeric values and may reject
non-numeric types."""
    nargs = len(args)
    if nargs + len(kwds) > 2:
        raise TypeError("prod() takes at most 2 arguments (" + str(nargs + len(kwds)) + " given)")
    if nargs != 1:                               # iterable is positional-only
        raise TypeError("prod() takes exactly 1 positional argument (" + str(nargs) + " given)")
    start: object = 1
    for keyword, value in kwds.items():
        if keyword == "start":
            start = value
        else:
            suggestion = _keyword_suggestion(("start",), keyword)
            if suggestion is not None:
                raise TypeError("prod() got an unexpected keyword argument '" + keyword + "'. Did you mean '" + suggestion + "'?")
            raise TypeError("prod() got an unexpected keyword argument '" + keyword + "'")
    result = start
    for item in args[0]:  # type: ignore[attr-defined]
        result = result * item  # type: ignore[operator]
    return result


def nextafter(*args: object, **kwds: object) -> float:
    """Return the floating-point value the given number of steps after x towards y.

If steps is not specified or is None, it defaults to 1.

Raises a TypeError, if x or y is not a double, or if steps is not
an integer.  Raises ValueError if steps is negative."""
    nargs = len(args)
    if nargs + len(kwds) > 3:
        raise TypeError("nextafter() takes at most 3 arguments (" + str(nargs + len(kwds)) + " given)")
    if nargs > 2:
        raise TypeError("nextafter() takes exactly 2 positional arguments (" + str(nargs) + " given)")
    if nargs < 2:
        raise TypeError("nextafter() takes exactly 2 positional arguments (" + str(nargs) + " given)")
    steps: object = None
    for keyword, value in kwds.items():
        if keyword != "steps":
            suggestion = _keyword_suggestion(("steps",), keyword)
            if suggestion is not None:
                raise TypeError("nextafter() got an unexpected keyword argument '" + keyword + "'. Did you mean '" + suggestion + "'?")
            raise TypeError("nextafter() got an unexpected keyword argument '" + keyword + "'")
        steps = value
    x = _clinic_double(args[0])
    y = _clinic_double(args[1])
    if _isnan(x):
        return x
    if _isnan(y):
        return y
    if steps is None:
        return _c("nextafter", x, y)
    usteps = _index(steps)
    if usteps < 0:
        raise ValueError("steps must be a non-negative integer")
    if usteps >= 2**64 - 1:
        usteps = 2**64 - 1
    if usteps == 0:
        return x
    ux = int.from_bytes(_float_pack(x, 8, True), "little")
    uy = int.from_bytes(_float_pack(y, 8, True), "little")
    if ux == uy:
        return x
    sign_bit = 1 << 63
    ax = ux & ~sign_bit
    ay = uy & ~sign_bit
    if (ux ^ uy) & sign_bit:
        if ax + ay <= usteps:
            return y
        if ax < usteps:
            return _bits_float((uy & sign_bit) | (usteps - ax))
        return _bits_float(ux - usteps)
    if ax > ay:
        if ax - ay >= usteps:
            return _bits_float(ux - usteps)
        return y
    if ay - ax >= usteps:
        return _bits_float(ux + usteps)
    return y


def _bits_float(bits: int) -> float:
    return _float_unpack(int.to_bytes(bits & (2**64 - 1), 8, "little"), True)  # type: ignore[no-any-return]


def ulp(*args: object, **kwds: object) -> float:
    """Return the value of the least significant bit of the float x."""
    x = _clinic_double(_one("ulp", args, kwds))
    if _isnan(x):
        return x
    x = abs(x)
    if _isinf(x):
        return x
    x2 = _c("nextafter", x, _INF)
    if _isinf(x2):
        x2 = _c("nextafter", x, -_INF)
        return x - x2
    return x2 - x
