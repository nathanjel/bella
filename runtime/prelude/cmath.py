"""cmath, in Python (Modules/cmathmodule.c) over the C library's functions (libm.cpp's `_libm`, answering the result and errno):
C99 Annex G's special values as the C's seven-by-seven tables, every function's own algorithm line for line (the scalings that
keep sqrt, log and the inverse functions from overflowing or losing the bits of a subnormal, the reductions of asin, atan, cos,
sin and tan to the hyperbolic functions), the errno each sets and the clinic's protected wrappers that turn it into ValueError
or OverflowError, log with a base through complexobject.c's _Py_c_quot, phase, polar over _Py_c_abs, rect with its own table,
isclose, the constants. An argument becomes a complex as PyComplex_AsCComplex has it (the runtime's, `_as_c_complex`)."""

__all__ = ["acos", "acosh", "asin", "asinh", "atan", "atanh", "cos", "cosh", "e", "exp", "inf", "infj", "isclose", "isfinite", "isinf",
           "isnan", "log", "log10", "nan", "nanj", "phase", "pi", "polar", "rect", "sin", "sinh", "sqrt", "tan", "tanh", "tau"]

__name__ = "cmath"

try:
    _libm                                        # noqa: B018  # the C library's function by name: (result, errno)
    _as_c_complex                                # noqa: B018  # PyComplex_AsCComplex: (real, imag)
    _as_double                                   # noqa: B018  # PyFloat_AsDouble
    _unpack_keywords                             # noqa: B018  # _PyArg_UnpackKeywords
    _bella_refuse                                # noqa: B018  # a stop by name
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _libm: Callable[..., Any] = _missing
    _unpack_keywords: Callable[..., Any] = _missing
    _bella_refuse: Callable[..., Any] = _missing

    def _as_c_complex(value: object) -> tuple[float, float]:   # for probing this file under CPython
        z = complex(value)  # type: ignore[arg-type]
        return z.real, z.imag

    def _as_double(value: object) -> float:
        return float(value)  # type: ignore[arg-type]

_EDOM = 33
_ERANGE = 34

_INF = float("inf")
_NAN = float("nan")
_DBL_MAX = 1.7976931348623157e308
_DBL_MIN = 2.2250738585072014e-308
_DBL_MANT_DIG = 53
_M_LN2 = 0.6931471805599453094                   # natural log of 2
_M_LN10 = 2.302585092994045684                   # natural log of 10
_PI = 3.141592653589793                          # Py_MATH_PI
_E = 2.718281828459045                           # Py_MATH_E

pi = _PI
e = _E
tau = 6.283185307179586                          # Py_MATH_TAU
inf = _INF
nan = abs(_NAN)                                  # fabs(Py_NAN)
infj = complex(0.0, _INF)
nanj = complex(0.0, abs(_NAN))


# ---- the C's floating-point functions -------------------------------------------------------------------------------------------

def _isnan(x: float) -> bool:
    return x != x


def _isinf(x: float) -> bool:
    return x == _INF or x == -_INF


def _isfinite(x: float) -> bool:
    return x == x and x != _INF and x != -_INF


def _copysign(x: float, y: float) -> float:
    return _libm("copysign", x, y)[0]  # type: ignore[no-any-return]


def _ldexp(x: float, exponent: int) -> float:
    return _libm("ldexp", x, exponent)[0]  # type: ignore[no-any-return]


def _c(name: str, *values: float) -> float:      # a libm function whose errno the C does not read
    return _libm(name, *values)[0]  # type: ignore[no-any-return]


def _log1p(x: float) -> float:                   # _Py_log1p (Modules/_math.h): the sign of a zero kept on every platform
    if x == 0.0:
        return x
    return _c("log1p", x)


_CM_LARGE_DOUBLE = _DBL_MAX / 4.0
_CM_SQRT_LARGE_DOUBLE = _c("sqrt", _CM_LARGE_DOUBLE)
_CM_LOG_LARGE_DOUBLE = _c("log", _CM_LARGE_DOUBLE)
_CM_SQRT_DBL_MIN = _c("sqrt", _DBL_MIN)
_CM_SCALE_UP = 2 * (_DBL_MANT_DIG // 2) + 1      # FLT_RADIX == 2
_CM_SCALE_DOWN = -(_CM_SCALE_UP + 1) // 2


# ---- special values -------------------------------------------------------------------------------------------------------------

_ST_NINF = 0                                     # negative infinity
_ST_NEG = 1                                      # negative finite number (nonzero)
_ST_NZERO = 2                                    # -0.
_ST_PZERO = 3                                    # +0.
_ST_POS = 4                                      # positive finite number (nonzero)
_ST_PINF = 5                                     # positive infinity
_ST_NAN = 6                                      # Not a Number


def _special_type(d: float) -> int:
    if _isfinite(d):
        if d != 0:
            if _copysign(1.0, d) == 1.0:
                return _ST_POS
            return _ST_NEG
        if _copysign(1.0, d) == 1.0:
            return _ST_PZERO
        return _ST_NZERO
    if _isnan(d):
        return _ST_NAN
    if _copysign(1.0, d) == 1.0:
        return _ST_PINF
    return _ST_NINF


_P = _PI
_P14 = 0.25 * _PI
_P12 = 0.5 * _PI
_P34 = 0.75 * _PI
_N = _NAN
_U = -9.5426319407711027e33                      # unlikely value, used as placeholder
_I = _INF

_ACOS = (
    ((_P34, _I), (_P, _I), (_P, _I), (_P, -_I), (_P, -_I), (_P34, -_I), (_N, _I)),
    ((_P12, _I), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (_P12, -_I), (_N, _N)),
    ((_P12, _I), (_U, _U), (_P12, 0.), (_P12, -0.), (_U, _U), (_P12, -_I), (_P12, _N)),
    ((_P12, _I), (_U, _U), (_P12, 0.), (_P12, -0.), (_U, _U), (_P12, -_I), (_P12, _N)),
    ((_P12, _I), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (_P12, -_I), (_N, _N)),
    ((_P14, _I), (0., _I), (0., _I), (0., -_I), (0., -_I), (_P14, -_I), (_N, _I)),
    ((_N, _I), (_N, _N), (_N, _N), (_N, _N), (_N, _N), (_N, -_I), (_N, _N)))

_ACOSH = (
    ((_I, -_P34), (_I, -_P), (_I, -_P), (_I, _P), (_I, _P), (_I, _P34), (_I, _N)),
    ((_I, -_P12), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (_I, _P12), (_N, _N)),
    ((_I, -_P12), (_U, _U), (0., -_P12), (0., _P12), (_U, _U), (_I, _P12), (_N, _P12)),
    ((_I, -_P12), (_U, _U), (0., -_P12), (0., _P12), (_U, _U), (_I, _P12), (_N, _P12)),
    ((_I, -_P12), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (_I, _P12), (_N, _N)),
    ((_I, -_P14), (_I, -0.), (_I, -0.), (_I, 0.), (_I, 0.), (_I, _P14), (_I, _N)),
    ((_I, _N), (_N, _N), (_N, _N), (_N, _N), (_N, _N), (_I, _N), (_N, _N)))

_ASINH = (
    ((-_I, -_P14), (-_I, -0.), (-_I, -0.), (-_I, 0.), (-_I, 0.), (-_I, _P14), (-_I, _N)),
    ((-_I, -_P12), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (-_I, _P12), (_N, _N)),
    ((-_I, -_P12), (_U, _U), (-0., -0.), (-0., 0.), (_U, _U), (-_I, _P12), (_N, _N)),
    ((_I, -_P12), (_U, _U), (0., -0.), (0., 0.), (_U, _U), (_I, _P12), (_N, _N)),
    ((_I, -_P12), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (_I, _P12), (_N, _N)),
    ((_I, -_P14), (_I, -0.), (_I, -0.), (_I, 0.), (_I, 0.), (_I, _P14), (_I, _N)),
    ((_I, _N), (_N, _N), (_N, -0.), (_N, 0.), (_N, _N), (_I, _N), (_N, _N)))

_ATANH = (
    ((-0., -_P12), (-0., -_P12), (-0., -_P12), (-0., _P12), (-0., _P12), (-0., _P12), (-0., _N)),
    ((-0., -_P12), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (-0., _P12), (_N, _N)),
    ((-0., -_P12), (_U, _U), (-0., -0.), (-0., 0.), (_U, _U), (-0., _P12), (-0., _N)),
    ((0., -_P12), (_U, _U), (0., -0.), (0., 0.), (_U, _U), (0., _P12), (0., _N)),
    ((0., -_P12), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (0., _P12), (_N, _N)),
    ((0., -_P12), (0., -_P12), (0., -_P12), (0., _P12), (0., _P12), (0., _P12), (0., _N)),
    ((0., -_P12), (_N, _N), (_N, _N), (_N, _N), (_N, _N), (0., _P12), (_N, _N)))

_COSH = (
    ((_I, _N), (_U, _U), (_I, 0.), (_I, -0.), (_U, _U), (_I, _N), (_I, _N)),
    ((_N, _N), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (_N, _N), (_N, _N)),
    ((_N, 0.), (_U, _U), (1., 0.), (1., -0.), (_U, _U), (_N, 0.), (_N, 0.)),
    ((_N, 0.), (_U, _U), (1., -0.), (1., 0.), (_U, _U), (_N, 0.), (_N, 0.)),
    ((_N, _N), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (_N, _N), (_N, _N)),
    ((_I, _N), (_U, _U), (_I, -0.), (_I, 0.), (_U, _U), (_I, _N), (_I, _N)),
    ((_N, _N), (_N, _N), (_N, 0.), (_N, 0.), (_N, _N), (_N, _N), (_N, _N)))

_EXP = (
    ((0., 0.), (_U, _U), (0., -0.), (0., 0.), (_U, _U), (0., 0.), (0., 0.)),
    ((_N, _N), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (_N, _N), (_N, _N)),
    ((_N, _N), (_U, _U), (1., -0.), (1., 0.), (_U, _U), (_N, _N), (_N, _N)),
    ((_N, _N), (_U, _U), (1., -0.), (1., 0.), (_U, _U), (_N, _N), (_N, _N)),
    ((_N, _N), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (_N, _N), (_N, _N)),
    ((_I, _N), (_U, _U), (_I, -0.), (_I, 0.), (_U, _U), (_I, _N), (_I, _N)),
    ((_N, _N), (_N, _N), (_N, -0.), (_N, 0.), (_N, _N), (_N, _N), (_N, _N)))

_LOG = (
    ((_I, -_P34), (_I, -_P), (_I, -_P), (_I, _P), (_I, _P), (_I, _P34), (_I, _N)),
    ((_I, -_P12), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (_I, _P12), (_N, _N)),
    ((_I, -_P12), (_U, _U), (-_I, -_P), (-_I, _P), (_U, _U), (_I, _P12), (_N, _N)),
    ((_I, -_P12), (_U, _U), (-_I, -0.), (-_I, 0.), (_U, _U), (_I, _P12), (_N, _N)),
    ((_I, -_P12), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (_I, _P12), (_N, _N)),
    ((_I, -_P14), (_I, -0.), (_I, -0.), (_I, 0.), (_I, 0.), (_I, _P14), (_I, _N)),
    ((_I, _N), (_N, _N), (_N, _N), (_N, _N), (_N, _N), (_I, _N), (_N, _N)))

_SINH = (
    ((_I, _N), (_U, _U), (-_I, -0.), (-_I, 0.), (_U, _U), (_I, _N), (_I, _N)),
    ((_N, _N), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (_N, _N), (_N, _N)),
    ((0., _N), (_U, _U), (-0., -0.), (-0., 0.), (_U, _U), (0., _N), (0., _N)),
    ((0., _N), (_U, _U), (0., -0.), (0., 0.), (_U, _U), (0., _N), (0., _N)),
    ((_N, _N), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (_N, _N), (_N, _N)),
    ((_I, _N), (_U, _U), (_I, -0.), (_I, 0.), (_U, _U), (_I, _N), (_I, _N)),
    ((_N, _N), (_N, _N), (_N, -0.), (_N, 0.), (_N, _N), (_N, _N), (_N, _N)))

_SQRT = (
    ((_I, -_I), (0., -_I), (0., -_I), (0., _I), (0., _I), (_I, _I), (_N, _I)),
    ((_I, -_I), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (_I, _I), (_N, _N)),
    ((_I, -_I), (_U, _U), (0., -0.), (0., 0.), (_U, _U), (_I, _I), (_N, _N)),
    ((_I, -_I), (_U, _U), (0., -0.), (0., 0.), (_U, _U), (_I, _I), (_N, _N)),
    ((_I, -_I), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (_I, _I), (_N, _N)),
    ((_I, -_I), (_I, -0.), (_I, -0.), (_I, 0.), (_I, 0.), (_I, _I), (_I, _N)),
    ((_I, -_I), (_N, _N), (_N, _N), (_N, _N), (_N, _N), (_I, _I), (_N, _N)))

_TANH = (
    ((-1., 0.), (_U, _U), (-1., -0.), (-1., 0.), (_U, _U), (-1., 0.), (-1., 0.)),
    ((_N, _N), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (_N, _N), (_N, _N)),
    ((-0.0, _N), (_U, _U), (-0., -0.), (-0., 0.), (_U, _U), (-0.0, _N), (-0., _N)),
    ((0.0, _N), (_U, _U), (0., -0.), (0., 0.), (_U, _U), (0.0, _N), (0., _N)),
    ((_N, _N), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (_N, _N), (_N, _N)),
    ((1., 0.), (_U, _U), (1., -0.), (1., 0.), (_U, _U), (1., 0.), (1., 0.)),
    ((_N, _N), (_N, _N), (_N, -0.), (_N, 0.), (_N, _N), (_N, _N), (_N, _N)))

_RECT = (
    ((_I, _N), (_U, _U), (-_I, 0.), (-_I, -0.), (_U, _U), (_I, _N), (_I, _N)),
    ((_N, _N), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (_N, _N), (_N, _N)),
    ((0., 0.), (_U, _U), (-0., 0.), (-0., -0.), (_U, _U), (0., 0.), (0., 0.)),
    ((0., 0.), (_U, _U), (0., -0.), (0., 0.), (_U, _U), (0., 0.), (0., 0.)),
    ((_N, _N), (_U, _U), (_U, _U), (_U, _U), (_U, _U), (_N, _N), (_N, _N)),
    ((_I, _N), (_U, _U), (_I, -0.), (_I, 0.), (_U, _U), (_I, _N), (_I, _N)),
    ((_N, _N), (_N, _N), (_N, 0.), (_N, 0.), (_N, _N), (_N, _N), (_N, _N)))

# each function answers a Py_complex and the errno it leaves: (real, imag, errno)

def _table(table: tuple[tuple[tuple[float, float], ...], ...], x: float, y: float) -> tuple[float, float]:
    return table[_special_type(x)][_special_type(y)]


def _special(table: tuple[tuple[tuple[float, float], ...], ...], x: float, y: float) -> tuple[float, float, int]:   # SPECIAL_VALUE: the table's entry, errno = 0
    re, im = _table(table, x, y)
    return re, im, 0


def _special_case(x: float, y: float) -> bool:   # SPECIAL_VALUE's test
    return not _isfinite(x) or not _isfinite(y)


# ---- complexobject.c ------------------------------------------------------------------------------------------------------------

def _c_abs(x: float, y: float) -> tuple[float, int]:   # _Py_c_abs: ERANGE on overflow, else 0 (a NaN leaves errno as it was: 0 here)
    if not _isfinite(x) or not _isfinite(y):
        if _isinf(x):
            return abs(x), 0
        if _isinf(y):
            return abs(y), 0
        return _NAN, 0
    result = _c("hypot", x, y)
    if not _isfinite(result):
        return result, _ERANGE
    return result, 0


def _add(x: float, y: float) -> float:          # x + y as the machine adds them: of two NaNs, the first's (x86's rule), not
    if x != x:                                   # whichever operand the C++ compiler put first
        return x * 1.0                           # the NaN quieted
    return x + y


def _mul(x: float, y: float) -> float:          # x * y likewise
    if x != x:
        return x * 1.0
    return x * y


def _c_quot(ar: float, ai: float, br: float, bi: float) -> tuple[float, float, bool]:   # _Py_c_quot: True where it sets EDOM
    # Each numerator in the order the pinned build's machine code computes it (clang pairs the two in one vector and turns
    # `a.imag*ratio - a.real` into `-a.real + ratio*a.imag`): the same number, and where both operands are NaN the result is the
    # first one's, so the sign of a NaN quotient is the pin's too (IEEE 754 does not interpret it). A denominator has one NaN at most.
    edom = False
    abs_breal = -br if br < 0 else br
    abs_bimag = -bi if bi < 0 else bi
    if abs_breal >= abs_bimag:
        if abs_breal == 0.0:
            edom = True
            rr = ri = 0.0
        else:
            ratio = bi / br
            denom = bi * ratio + br                       # b.real + b.imag * ratio
            rr = _add(ar, _mul(ratio, ai)) / denom        # (a.real + a.imag * ratio) / denom
            ri = _add(ai, _mul(ratio, -ar)) / denom       # (a.imag - a.real * ratio) / denom
    elif abs_bimag >= abs_breal:
        ratio = br / bi
        denom = br * ratio + bi
        rr = _add(ai, _mul(ratio, ar)) / denom            # (a.real * ratio + a.imag) / denom
        ri = _add(-ar, _mul(ratio, ai)) / denom           # (a.imag * ratio - a.real) / denom
    else:                                        # at least one of b.real or b.imag is a NaN
        rr = ri = _NAN
    if _isnan(rr) and _isnan(ri):               # recover infinities and zeros that computed as nan+nanj (C11 G.5.2, _Cdivd)
        if (_isinf(ar) or _isinf(ai)) and _isfinite(br) and _isfinite(bi):
            x = _copysign(1.0 if _isinf(ar) else 0.0, ar)
            y = _copysign(1.0 if _isinf(ai) else 0.0, ai)
            rr = _INF * (x * br + y * bi)
            ri = _INF * (y * br - x * bi)
        elif (_isinf(abs_breal) or _isinf(abs_bimag)) and _isfinite(ar) and _isfinite(ai):
            x = _copysign(1.0 if _isinf(br) else 0.0, br)
            y = _copysign(1.0 if _isinf(bi) else 0.0, bi)
            rr = 0.0 * (ar * x + ai * y)
            ri = 0.0 * (ai * x - ar * y)
    return rr, ri, edom


# ---- the functions --------------------------------------------------------------------------------------------------------------

def _acos(x: float, y: float) -> tuple[float, float, int]:
    if _special_case(x, y):
        return _special(_ACOS, x, y)
    if abs(x) > _CM_LARGE_DOUBLE or abs(y) > _CM_LARGE_DOUBLE:   # avoid unnecessary overflow for large arguments
        rr = _c("atan2", abs(y), x)
        ri = -_copysign(_c("log", _c("hypot", x / 2., y / 2.)) + _M_LN2 * 2., y)
    else:
        s1r, s1i, _ = _sqrt(1. - x, -y)
        s2r, s2i, _ = _sqrt(1. + x, y)
        rr = 2. * _c("atan2", s1r, s2r)
        ri = _c("asinh", s2r * s1i - s2i * s1r)
    return rr, ri, 0


def _acosh(x: float, y: float) -> tuple[float, float, int]:
    if _special_case(x, y):
        return _special(_ACOSH, x, y)
    if abs(x) > _CM_LARGE_DOUBLE or abs(y) > _CM_LARGE_DOUBLE:
        rr = _c("log", _c("hypot", x / 2., y / 2.)) + _M_LN2 * 2.
        ri = _c("atan2", y, x)
    else:
        s1r, s1i, _ = _sqrt(x - 1., y)
        s2r, s2i, _ = _sqrt(x + 1., y)
        rr = _c("asinh", s1r * s2r + s1i * s2i)
        ri = 2. * _c("atan2", s1i, s2r)
    return rr, ri, 0


def _asin(x: float, y: float) -> tuple[float, float, int]:       # asin(z) = -i asinh(iz)
    sr, si, err = _asinh(-y, x)
    return si, -sr, err


def _asinh(x: float, y: float) -> tuple[float, float, int]:
    if _special_case(x, y):
        return _special(_ASINH, x, y)
    if abs(x) > _CM_LARGE_DOUBLE or abs(y) > _CM_LARGE_DOUBLE:
        if y >= 0.:
            rr = _copysign(_c("log", _c("hypot", x / 2., y / 2.)) + _M_LN2 * 2., x)
        else:
            rr = -_copysign(_c("log", _c("hypot", x / 2., y / 2.)) + _M_LN2 * 2., -x)
        ri = _c("atan2", y, abs(x))
    else:
        s1r, s1i, _ = _sqrt(1. + y, -x)
        s2r, s2i, _ = _sqrt(1. - y, x)
        rr = _c("asinh", s1r * s2i - s2r * s1i)
        ri = _c("atan2", y, s1r * s2r - s1i * s2i)
    return rr, ri, 0


def _atan(x: float, y: float) -> tuple[float, float, int]:       # atan(z) = -i atanh(iz)
    sr, si, err = _atanh(-y, x)
    return si, -sr, err


def _atanh(x: float, y: float) -> tuple[float, float, int]:
    if _special_case(x, y):
        return _special(_ATANH, x, y)
    if x < 0.:                                   # reduce to the case where z.real >= 0., using atanh(z) = -atanh(-z)
        rr, ri, err = _atanh(-x, -y)
        return -rr, -ri, err
    ay = abs(y)
    if x > _CM_SQRT_LARGE_DOUBLE or ay > _CM_SQRT_LARGE_DOUBLE:   # atanh(z) ~ 1/z +/- i*pi/2 where abs(z) is large
        h = _c("hypot", x / 2., y / 2.)          # safe from overflow
        return x / 4. / h / h, _copysign(_PI / 2., y), 0
    if x == 1. and ay < _CM_SQRT_DBL_MIN:       # C99: atanh(1+/-0.) is inf +/- 0i
        if ay == 0.:
            return _INF, y, _EDOM
        return -_c("log", _c("sqrt", ay) / _c("sqrt", _c("hypot", ay, 2.))), _copysign(_c("atan2", 2., -ay) / 2, y), 0
    rr = _log1p(4. * x / ((1 - x) * (1 - x) + ay * ay)) / 4.
    ri = -_c("atan2", -2. * y, (1 - x) * (1 + x) - ay * ay) / 2.
    return rr, ri, 0


def _cos(x: float, y: float) -> tuple[float, float, int]:        # cos(z) = cosh(iz)
    return _cosh(-y, x)


def _cosh(x: float, y: float) -> tuple[float, float, int]:
    if not _isfinite(x) or not _isfinite(y):   # cosh(+/-inf + iy) where y is not a NaN is computed
        if _isinf(x) and _isfinite(y) and y != 0.:
            if x > 0:
                rr = _copysign(_INF, _c("cos", y))
                ri = _copysign(_INF, _c("sin", y))
            else:
                rr = _copysign(_INF, _c("cos", y))
                ri = -_copysign(_INF, _c("sin", y))
        else:
            rr, ri = _table(_COSH, x, y)
        return rr, ri, _EDOM if _isinf(y) and not _isnan(x) else 0
    if abs(x) > _CM_LOG_LARGE_DOUBLE:            # where cosh(z.real) overflows but cosh(z) does not
        x_minus_one = x - _copysign(1., x)
        rr = _c("cos", y) * _c("cosh", x_minus_one) * _E
        ri = _c("sin", y) * _c("sinh", x_minus_one) * _E
    else:
        rr = _c("cos", y) * _c("cosh", x)
        ri = _c("sin", y) * _c("sinh", x)
    return rr, ri, _ERANGE if _isinf(rr) or _isinf(ri) else 0


def _exp(x: float, y: float) -> tuple[float, float, int]:
    if not _isfinite(x) or not _isfinite(y):
        if _isinf(x) and _isfinite(y) and y != 0.:
            if x > 0:
                rr = _copysign(_INF, _c("cos", y))
                ri = _copysign(_INF, _c("sin", y))
            else:
                rr = _copysign(0., _c("cos", y))
                ri = _copysign(0., _c("sin", y))
        else:
            rr, ri = _table(_EXP, x, y)
        return rr, ri, _EDOM if _isinf(y) and (_isfinite(x) or (_isinf(x) and x > 0)) else 0
    if x > _CM_LOG_LARGE_DOUBLE:
        lv = _c("exp", x - 1.)
        rr = lv * _c("cos", y) * _E
        ri = lv * _c("sin", y) * _E
    else:
        lv = _c("exp", x)
        rr = lv * _c("cos", y)
        ri = lv * _c("sin", y)
    return rr, ri, _ERANGE if _isinf(rr) or _isinf(ri) else 0


def _log(x: float, y: float) -> tuple[float, float, int]:        # c_log
    if _special_case(x, y):
        return _special(_LOG, x, y)
    ax = abs(x)
    ay = abs(y)
    if ax > _CM_LARGE_DOUBLE or ay > _CM_LARGE_DOUBLE:
        rr = _c("log", _c("hypot", ax / 2., ay / 2.)) + _M_LN2
    elif ax < _DBL_MIN and ay < _DBL_MIN:
        if ax > 0. or ay > 0.:                   # where hypot(ax, ay) is subnormal
            rr = _c("log", _c("hypot", _ldexp(ax, _DBL_MANT_DIG), _ldexp(ay, _DBL_MANT_DIG))) - _DBL_MANT_DIG * _M_LN2
        else:                                    # log(+/-0. +/- 0i)
            return -_INF, _c("atan2", y, x), _EDOM
    else:
        h = _c("hypot", ax, ay)
        if 0.71 <= h and h <= 1.73:
            am = ax if ax > ay else ay           # max(ax, ay)
            an = ay if ax > ay else ax           # min(ax, ay)
            rr = _log1p((am - 1) * (am + 1) + an * an) / 2.
        else:
            rr = _c("log", h)
    return rr, _c("atan2", y, x), 0


def _log10(x: float, y: float) -> tuple[float, float, int]:
    rr, ri, err = _log(x, y)
    return rr / _M_LN10, ri / _M_LN10, err


def _sin(x: float, y: float) -> tuple[float, float, int]:        # sin(z) = -i sinh(iz)
    sr, si, err = _sinh(-y, x)
    return si, -sr, err


def _sinh(x: float, y: float) -> tuple[float, float, int]:
    if not _isfinite(x) or not _isfinite(y):   # sinh(+/-inf + iy) where y is finite and nonzero is computed
        if _isinf(x) and _isfinite(y) and y != 0.:
            if x > 0:
                rr = _copysign(_INF, _c("cos", y))
                ri = _copysign(_INF, _c("sin", y))
            else:
                rr = -_copysign(_INF, _c("cos", y))
                ri = _copysign(_INF, _c("sin", y))
        else:
            rr, ri = _table(_SINH, x, y)
        return rr, ri, _EDOM if _isinf(y) and not _isnan(x) else 0
    if abs(x) > _CM_LOG_LARGE_DOUBLE:
        x_minus_one = x - _copysign(1., x)
        rr = _c("cos", y) * _c("sinh", x_minus_one) * _E
        ri = _c("sin", y) * _c("cosh", x_minus_one) * _E
    else:
        rr = _c("cos", y) * _c("sinh", x)
        ri = _c("sin", y) * _c("cosh", x)
    return rr, ri, _ERANGE if _isinf(rr) or _isinf(ri) else 0


def _sqrt(x: float, y: float) -> tuple[float, float, int]:
    # s = sqrt((x + hypot(x, y))/2) and d = (y/2)/s for nonnegative x and y, the formula for s rewritten as
    # 2*sqrt(x/8 + hypot(x/8, y/8)) to avoid overflow, and both scaled by a power of 2 where hypot would be subnormal
    if _special_case(x, y):
        return _special(_SQRT, x, y)
    if x == 0. and y == 0.:
        return 0., y, 0                          # errno as the wrapper left it
    ax = abs(x)
    ay = abs(y)
    if ax < _DBL_MIN and ay < _DBL_MIN:         # where hypot(ax, ay) is subnormal
        ax = _ldexp(ax, _CM_SCALE_UP)
        s = _ldexp(_c("sqrt", ax + _c("hypot", ax, _ldexp(ay, _CM_SCALE_UP))), _CM_SCALE_DOWN)
    else:
        ax /= 8.
        s = 2. * _c("sqrt", ax + _c("hypot", ax, ay / 8.))
    d = ay / (2. * s)
    if x >= 0.:
        return s, _copysign(d, y), 0
    return d, _copysign(s, y), 0


def _tan(x: float, y: float) -> tuple[float, float, int]:        # tan(z) = -i tanh(iz)
    sr, si, err = _tanh(-y, x)
    return si, -sr, err


def _tanh(x: float, y: float) -> tuple[float, float, int]:
    # tanh(x+iy) = (tanh(x)(1+tan(y)^2) + i tan(y)(1-tanh(x))^2) / (1+tan(y)^2 tanh(x)^2), 1-tanh(x)^2 as 1/cosh(x)^2, or
    # as 4 exp(-2*x) where abs(x) is large
    if not _isfinite(x) or not _isfinite(y):   # tanh(+/-inf + iy) where y is finite and nonzero is computed
        if _isinf(x) and _isfinite(y) and y != 0.:
            if x > 0:
                rr = 1.0
                ri = _copysign(0., 2. * _c("sin", y) * _c("cos", y))
            else:
                rr = -1.0
                ri = _copysign(0., 2. * _c("sin", y) * _c("cos", y))
        else:
            rr, ri = _table(_TANH, x, y)
        return rr, ri, _EDOM if _isinf(y) and _isfinite(x) else 0
    if abs(x) > _CM_LOG_LARGE_DOUBLE:            # danger of overflow in 2.*z.imag
        rr = _copysign(1., x)
        ri = 4. * _c("sin", y) * _c("cos", y) * _c("exp", -2. * abs(x))
    else:
        tx = _c("tanh", x)
        ty = _c("tan", y)
        cx = 1. / _c("cosh", x)
        txty = tx * ty
        denom = 1. + txty * txty
        rr = tx * (1. + ty * ty) / denom
        ri = ((ty / denom) * cx) * cx
    return rr, ri, 0


# ---- the clinic's wrappers ------------------------------------------------------------------------------------------------------

def _one(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> object:   # METH_O
    if kwds:
        raise TypeError("cmath." + name + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("cmath." + name + "() takes exactly one argument (" + str(len(args)) + " given)")
    return args[0]


def _positional(name: str, args: tuple[object, ...], kwds: dict[str, object], low: int, high: int) -> None:   # METH_FASTCALL
    if kwds:                                                                                                       # with _PyArg_CheckPositional
        raise TypeError("cmath." + name + "() takes no keyword arguments")
    if len(args) < low:
        raise TypeError(name + " expected " + ("at least " if low < high else "") + str(low) + " argument" + ("" if low == 1 else "s") + ", got " + str(len(args)))
    if len(args) > high:
        raise TypeError(name + " expected " + ("at most " if low < high else "") + str(high) + " argument" + ("" if high == 1 else "s") + ", got " + str(len(args)))


def _double(value: object) -> float:            # the clinic's `double`: a float itself read directly, else PyFloat_AsDouble
    if type(value) is float:
        return value  # type: ignore[return-value]
    return _as_double(value)


def _protected(name: str, args: tuple[object, ...], kwds: dict[str, object], impl: object) -> complex:   # Py_complex_protected
    x, y = _as_c_complex(_one(name, args, kwds))
    rr, ri, err = impl(x, y)  # type: ignore[operator]
    if err == _EDOM:
        raise ValueError("math domain error")
    if err == _ERANGE:
        raise OverflowError("math range error")
    return complex(rr, ri)


def _math_error(err: int) -> None:
    if err == _EDOM:
        raise ValueError("math domain error")
    if err == _ERANGE:
        raise OverflowError("math range error")
    _bella_refuse("cmath: errno " + str(err) + " from the C library (PyErr_SetFromErrno, an unexpected math error)")


def acos(*args: object, **kwds: object) -> complex:
    """Return the arc cosine of z."""
    return _protected("acos", args, kwds, _acos)


def acosh(*args: object, **kwds: object) -> complex:
    """Return the inverse hyperbolic cosine of z."""
    return _protected("acosh", args, kwds, _acosh)


def asin(*args: object, **kwds: object) -> complex:
    """Return the arc sine of z."""
    return _protected("asin", args, kwds, _asin)


def asinh(*args: object, **kwds: object) -> complex:
    """Return the inverse hyperbolic sine of z."""
    return _protected("asinh", args, kwds, _asinh)


def atan(*args: object, **kwds: object) -> complex:
    """Return the arc tangent of z."""
    return _protected("atan", args, kwds, _atan)


def atanh(*args: object, **kwds: object) -> complex:
    """Return the inverse hyperbolic tangent of z."""
    return _protected("atanh", args, kwds, _atanh)


def cos(*args: object, **kwds: object) -> complex:
    """Return the cosine of z."""
    return _protected("cos", args, kwds, _cos)


def cosh(*args: object, **kwds: object) -> complex:
    """Return the hyperbolic cosine of z."""
    return _protected("cosh", args, kwds, _cosh)


def exp(*args: object, **kwds: object) -> complex:
    """Return the exponential value e**z."""
    return _protected("exp", args, kwds, _exp)


def log10(*args: object, **kwds: object) -> complex:
    """Return the base-10 logarithm of z."""
    return _protected("log10", args, kwds, _log10)


def sin(*args: object, **kwds: object) -> complex:
    """Return the sine of z."""
    return _protected("sin", args, kwds, _sin)


def sinh(*args: object, **kwds: object) -> complex:
    """Return the hyperbolic sine of z."""
    return _protected("sinh", args, kwds, _sinh)


def sqrt(*args: object, **kwds: object) -> complex:
    """Return the square root of z."""
    return _protected("sqrt", args, kwds, _sqrt)


def tan(*args: object, **kwds: object) -> complex:
    """Return the tangent of z."""
    return _protected("tan", args, kwds, _tan)


def tanh(*args: object, **kwds: object) -> complex:
    """Return the hyperbolic tangent of z."""
    return _protected("tanh", args, kwds, _tanh)


def log(*args: object, **kwds: object) -> complex:
    """log(z[, base]) -> the logarithm of z to the given base.

If the base is not specified, returns the natural logarithm (base e)
of z."""
    _positional("log", args, kwds, 1, 2)
    x, y = _as_c_complex(args[0])
    rr, ri, err = _log(x, y)                     # errno = 0; x = c_log(x)
    if len(args) == 2:
        bx, by = _as_c_complex(args[1])
        br, bi, err = _log(bx, by)               # c_log(y) leaves its own errno
        rr, ri, edom = _c_quot(rr, ri, br, bi)
        if edom:
            err = _EDOM
    if err != 0:
        _math_error(err)
    return complex(rr, ri)


def phase(*args: object, **kwds: object) -> float:
    """Return argument, also known as the phase angle, of a complex."""
    x, y = _as_c_complex(_one("phase", args, kwds))
    phi, err = _libm("atan2", y, x)              # should not cause any exception; the C library may say ERANGE where it underflows
    if err != 0:
        _math_error(err)
    return phi  # type: ignore[no-any-return]


def polar(*args: object, **kwds: object) -> tuple[float, float]:
    """Convert a complex from rectangular coordinates to polar coordinates.

r is the distance from 0 and phi the phase angle."""
    x, y = _as_c_complex(_one("polar", args, kwds))
    phi = _c("atan2", y, x)
    r, err = _c_abs(x, y)
    if err != 0:
        _math_error(err)
    return r, phi


def rect(*args: object, **kwds: object) -> complex:
    """Convert from polar coordinates to rectangular coordinates."""
    _positional("rect", args, kwds, 2, 2)
    r = _double(args[0])
    phi = _double(args[1])
    if not _isfinite(r) or not _isfinite(phi):
        # where r is +/-infinity and phi finite but nonzero the result is (+-INF +-INF i), with the signs of cos(phi) and sin(phi)
        if _isinf(r) and _isfinite(phi) and phi != 0.:
            if r > 0:
                zr = _copysign(_INF, _c("cos", phi))
                zi = _copysign(_INF, _c("sin", phi))
            else:
                zr = -_copysign(_INF, _c("cos", phi))
                zi = -_copysign(_INF, _c("sin", phi))
        else:
            zr, zi = _table(_RECT, r, phi)
        if r != 0. and not _isnan(r) and _isinf(phi):   # EDOM where r is a nonzero number and phi is infinite
            _math_error(_EDOM)
    elif phi == 0.0:                             # bugs.python.org/issue18513: the sign of a zero phi
        zr = r
        zi = r * phi
    else:
        zr = r * _c("cos", phi)
        zi = r * _c("sin", phi)
    return complex(zr, zi)


def isfinite(*args: object, **kwds: object) -> bool:
    """Return True if both the real and imaginary parts of z are finite, else False."""
    x, y = _as_c_complex(_one("isfinite", args, kwds))
    return _isfinite(x) and _isfinite(y)


def isnan(*args: object, **kwds: object) -> bool:
    """Checks if the real or imaginary part of z not a number (NaN)."""
    x, y = _as_c_complex(_one("isnan", args, kwds))
    return _isnan(x) or _isnan(y)


def isinf(*args: object, **kwds: object) -> bool:
    """Checks if the real or imaginary part of z is infinite."""
    x, y = _as_c_complex(_one("isinf", args, kwds))
    return _isinf(x) or _isinf(y)


_ABSENT = object()


def isclose(*args: object, **kwds: object) -> bool:
    """Determine whether two complex numbers are close in value.

  rel_tol
    maximum difference for being considered "close", relative to the
    magnitude of the input values
  abs_tol
    maximum difference for being considered "close", regardless of the
    magnitude of the input values

Return True if a is close in value to b, and False otherwise.

For the values to be considered close, the difference between them must
be smaller than at least one of the tolerances.

-inf, inf and NaN behave similarly to the IEEE 754 Standard.  That is,
NaN is not close to anything, even itself. inf and -inf are only close
to themselves."""
    a_obj, b_obj, rel_obj, abs_obj = _unpack_keywords("isclose", ("a", "b", "rel_tol", "abs_tol"), 0, 2, 2, 0, args, kwds, _ABSENT)
    ar, ai = _as_c_complex(a_obj)
    br, bi = _as_c_complex(b_obj)
    rel_tol = 1e-09 if rel_obj is _ABSENT else _double(rel_obj)
    abs_tol = 0.0 if abs_obj is _ABSENT else _double(abs_obj)
    if rel_tol < 0.0 or abs_tol < 0.0:           # sanity check on the inputs
        raise ValueError("tolerances must be non-negative")
    if ar == br and ai == bi:                    # exact equality, which catches two infinities of the same sign
        return True
    if _isinf(ar) or _isinf(ai) or _isinf(br) or _isinf(bi):   # two infinities of opposite sign, or one infinity and a finite number
        return False
    diff, _ = _c_abs(ar - br, ai - bi)           # the "weak" test of the Boost library
    return (diff <= rel_tol * _c_abs(br, bi)[0] or diff <= rel_tol * _c_abs(ar, ai)[0]) or diff <= abs_tol
