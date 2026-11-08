"""math.integer, in Python (Modules/mathintegermodule.c): gcd, lcm, factorial, comb, perm and isqrt over Python's ints, each exact by
construction, with the C's argument handling and messages. math takes the six functions from here (math_exec imports _math_integer
and re-exports them), and sys.modules has the module as math.integer."""

__all__ = ["comb", "factorial", "gcd", "isqrt", "lcm", "perm"]

__name__ = "math.integer"

try:
    _tp_name                                     # noqa: B018  # Py_TYPE(o)->tp_name
except NameError:
    def _tp_name(o: object) -> str:
        return type(o).__name__


_LONG_MAX = 2**63 - 1


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


def _positional(name: str, args: tuple[object, ...], kwds: dict[str, object], low: int, high: int) -> None:   # _PyArg_CheckPositional
    if kwds:
        raise TypeError("math.integer." + name + "() takes no keyword arguments")
    if len(args) < low:
        raise TypeError(name + " expected " + ("at least " if low < high else "") + str(low) + " argument" + ("" if low == 1 else "s") + ", got " + str(len(args)))
    if len(args) > high:
        raise TypeError(name + " expected " + ("at most " if low < high else "") + str(high) + " argument" + ("" if high == 1 else "s") + ", got " + str(len(args)))


def _one(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> object:   # METH_O
    if kwds:
        raise TypeError("math.integer." + name + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("math.integer." + name + "() takes exactly one argument (" + str(len(args)) + " given)")
    return args[0]


def _gcd2(a: int, b: int) -> int:                # _PyLong_GCD: Euclid's result, the sign dropped
    a = -a if a < 0 else a
    b = -b if b < 0 else b
    while b:
        a, b = b, a % b
    return a


def gcd(*args: object, **kwds: object) -> int:
    """Greatest Common Divisor."""
    if kwds:
        raise TypeError("math.integer.gcd() takes no keyword arguments")
    if len(args) == 0:
        return 0
    res = _index(args[0])
    if len(args) == 1:
        return -res if res < 0 else res
    for i in range(1, len(args)):
        x = _index(args[i])
        if res == 1:                             # the GCD is 1 already: the rest are only converted
            continue
        res = _gcd2(res, x)
    return res


def lcm(*args: object, **kwds: object) -> int:
    """Least Common Multiple."""
    if kwds:
        raise TypeError("math.integer.lcm() takes no keyword arguments")
    if len(args) == 0:
        return 1
    res = _index(args[0])
    if len(args) == 1:
        return -res if res < 0 else res
    for i in range(1, len(args)):
        x = _index(args[i])
        if res == 0:                             # zero stays zero: the rest are only converted
            continue
        if x == 0:
            res = 0
            continue
        g = _gcd2(res, x)
        res = res // g * x
        res = -res if res < 0 else res
    return res


def isqrt(*args: object, **kwds: object) -> int:
    """Return the integer part of the square root of the input."""
    n = _index(_one("isqrt", args, kwds))
    if n < 0:
        raise ValueError("isqrt() argument must be nonnegative")
    if n == 0:
        return 0
    c = (n.bit_length() - 1) // 2                # the answer has c + 1 bits
    a = 1
    d = 0
    for s in reversed(range(c.bit_length())):    # Newton's iteration on the leading bits, as the C's loop
        e = d
        d = c >> s
        a = (a << (d - e - 1)) + (n >> (2 * c - e - d + 1)) // a
    return a - (1 if a * a > n else 0)


def factorial(*args: object, **kwds: object) -> int:
    """Find n!."""
    arg = _one("factorial", args, kwds)
    if not issubclass(type(arg), int):           # PyLong_AsLongAndOverflow: an int, or __index__
        arg = _index(arg)
    x = int.__index__(arg)  # type: ignore[arg-type]
    if x > _LONG_MAX:
        raise OverflowError("factorial() argument should not exceed " + str(_LONG_MAX))
    if x < 0:
        raise ValueError("factorial() not defined for negative values")
    result = 1
    for i in range(2, x + 1):
        result *= i
    return result


def _perm_comb(n: int, k: int, is_comb: bool) -> int:   # perm_comb: n * (n-1) * ... * (n-k+1), over k! for comb
    result = 1
    for i in range(k):
        result *= n - i
    if is_comb:
        for i in range(2, k + 1):
            result //= i
    return result


def perm(*args: object, **kwds: object) -> int:
    """Number of ways to choose k items from n items without repetition and with order.

Evaluates to n! / (n - k)! when k <= n and evaluates
to zero when k > n.

If k is not specified or is None, then k defaults to n
and the function returns n!.

Raises TypeError if either of the arguments are not integers.
Raises ValueError if either of the arguments are negative."""
    _positional("perm", args, kwds, 1, 2)
    n = args[0]
    k = args[1] if len(args) > 1 else None
    if k is None:
        return factorial(n)
    ni = _index(n)
    ki = _index(k)
    if ni < 0:
        raise ValueError("n must be a non-negative integer")
    if ki < 0:
        raise ValueError("k must be a non-negative integer")
    if ni < ki:
        return 0
    if ki > _LONG_MAX:
        raise OverflowError("k must not exceed " + str(_LONG_MAX))
    return _perm_comb(ni, ki, False)


def comb(*args: object, **kwds: object) -> int:
    """Number of ways to choose k items from n items without repetition and without order.

Evaluates to n! / (k! * (n - k)!) when k <= n and evaluates
to zero when k > n.

Also called the binomial coefficient because it is equivalent
to the coefficient of k-th term in polynomial expansion of the
expression (1 + x)**n.

Raises TypeError if either of the arguments are not integers.
Raises ValueError if either of the arguments are negative."""
    _positional("comb", args, kwds, 2, 2)
    ni = _index(args[0])
    ki = _index(args[1])
    if ni < 0:
        raise ValueError("n must be a non-negative integer")
    if ki < 0:
        raise ValueError("k must be a non-negative integer")
    if ni <= _LONG_MAX:
        if ki > ni:
            return 0
        ki = min(ki, ni - ki)
    else:
        temp = ni - ki
        if temp < 0:
            return 0
        if temp < ki:
            ki = temp
        if ki > _LONG_MAX:
            raise OverflowError("min(n - k, k) must not exceed " + str(_LONG_MAX))
    return _perm_comb(ni, ki, True)
