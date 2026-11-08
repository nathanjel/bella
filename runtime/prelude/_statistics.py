"""_statistics, in Python (Modules/_statisticsmodule.c): _normal_dist_inv_cdf, Wichura's AS241 with the C's coefficients and its
expressions' association, so the doubles are the C's; sqrt and log through the C library (libm.cpp). statistics imports it."""

__all__ = ["_normal_dist_inv_cdf"]

__name__ = "_statistics"

try:
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _tp_name                                     # noqa: B018  # Py_TYPE(o)->tp_name
    _number_index                                # noqa: B018  # PyNumber_Index
    _libm                                        # noqa: B018  # libm.cpp: (name, x) -> (result, errno)
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_refuse: Callable[..., Any] = _missing

    def _tp_name(o: object) -> str:
        return type(o).__name__

    def _number_index(o: object) -> int:
        import operator
        return operator.index(o)

    def _libm(name: str, x: float) -> tuple[float, int]:
        import math
        return getattr(math, name)(x), 0


def _as_double(value: object) -> float:          # PyFloat_AsDouble, the clinic's `double`
    if issubclass(type(value), float):
        return float.__float__(value)  # type: ignore[arg-type]
    to_float = getattr(type(value), "__float__", None)
    if to_float is not None:
        result = to_float(value)
        if not issubclass(type(result), float):
            raise TypeError(_tp_name(value) + ".__float__ returned non-float (type " + _tp_name(result) + ")")
        return float.__float__(result)
    if hasattr(type(value), "__index__"):
        return float(_number_index(value))
    raise TypeError("must be real number, not " + _tp_name(value))


def _normal_dist_inv_cdf(*args: object, **kwds: object) -> float:
    if kwds:
        raise TypeError("_statistics._normal_dist_inv_cdf() takes no keyword arguments")
    if len(args) != 3:
        raise TypeError("_normal_dist_inv_cdf expected 3 arguments, got " + str(len(args)))
    p = _as_double(args[0])
    mu = _as_double(args[1])
    sigma = _as_double(args[2])
    if p <= 0.0 or p >= 1.0:
        raise ValueError("inv_cdf undefined for these parameters")
    q = p - 0.5
    if abs(q) <= 0.425:
        r = 0.180625 - q * q
        num = (((((((2.5090809287301226727e+3 * r +
                     3.3430575583588128105e+4) * r +
                     6.7265770927008700853e+4) * r +
                     4.5921953931549871457e+4) * r +
                     1.3731693765509461125e+4) * r +
                     1.9715909503065514427e+3) * r +
                     1.3314166789178437745e+2) * r +
                     3.3871328727963666080e+0) * q
        den = (((((((5.2264952788528545610e+3 * r +
                     2.8729085735721942674e+4) * r +
                     3.9307895800092710610e+4) * r +
                     2.1213794301586595867e+4) * r +
                     5.3941960214247511077e+3) * r +
                     6.8718700749205790830e+2) * r +
                     4.2313330701600911252e+1) * r +
                     1.0)
        if den == 0.0:
            raise ValueError("inv_cdf undefined for these parameters")
        x = num / den
        return mu + (x * sigma)
    r = p if q <= 0.0 else 1.0 - p
    if r <= 0.0 or r >= 1.0:
        raise ValueError("inv_cdf undefined for these parameters")
    r = _libm("sqrt", -_libm("log", r)[0])[0]
    if r <= 5.0:
        r = r - 1.6
        num = (((((((7.74545014278341407640e-4 * r +
                     2.27238449892691845833e-2) * r +
                     2.41780725177450611770e-1) * r +
                     1.27045825245236838258e+0) * r +
                     3.64784832476320460504e+0) * r +
                     5.76949722146069140550e+0) * r +
                     4.63033784615654529590e+0) * r +
                     1.42343711074968357734e+0)
        den = (((((((1.05075007164441684324e-9 * r +
                     5.47593808499534494600e-4) * r +
                     1.51986665636164571966e-2) * r +
                     1.48103976427480074590e-1) * r +
                     6.89767334985100004550e-1) * r +
                     1.67638483018380384940e+0) * r +
                     2.05319162663775882187e+0) * r +
                     1.0)
    else:
        r -= 5.0
        num = (((((((2.01033439929228813265e-7 * r +
                     2.71155556874348757815e-5) * r +
                     1.24266094738807843860e-3) * r +
                     2.65321895265761230930e-2) * r +
                     2.96560571828504891230e-1) * r +
                     1.78482653991729133580e+0) * r +
                     5.46378491116411436990e+0) * r +
                     6.65790464350110377720e+0)
        den = (((((((2.04426310338993978564e-15 * r +
                     1.42151175831644588870e-7) * r +
                     1.84631831751005468180e-5) * r +
                     7.86869131145613259100e-4) * r +
                     1.48753612908506148525e-2) * r +
                     1.36929880922735805310e-1) * r +
                     5.99832206555887937690e-1) * r +
                     1.0)
    if den == 0.0:
        raise ValueError("inv_cdf undefined for these parameters")
    x = num / den
    if q < 0.0:
        x = -x
    return mu + (x * sigma)
