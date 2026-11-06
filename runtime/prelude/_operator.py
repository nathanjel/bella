"""_operator, in Python, from Modules/_operator.c (CPython's is built in); see itertools.py beside it.

Lib/operator.py imports everything from here. What the C calls from Python/abstract.c is the operator
the Python statement compiles to, except PySequence_Concat and its in-place form, which the runtime
gives (`_sequence_concat`), and the searches, ported here.
"""

__all__ = ["_compare_digest", "abs", "add", "and_", "attrgetter", "call", "concat", "contains", "countOf", "delitem",
           "eq", "floordiv", "ge", "getitem", "gt", "iadd", "iand", "iconcat", "ifloordiv", "ilshift", "imatmul", "imod",
           "imul", "index", "indexOf", "inv", "invert", "ior", "ipow", "irshift", "is_", "is_none", "is_not", "is_not_none",
           "isub", "itemgetter", "itruediv", "ixor", "le", "length_hint", "lshift", "lt", "matmul", "methodcaller", "mod",
           "mul", "ne", "neg", "not_", "or_", "pos", "pow", "rshift", "setitem", "sub", "truediv", "truth", "xor"]

__name__ = "_operator"

try:
    _number_index                                # noqa: B018  # PyNumber_Index, given by the runtime
    _lookup_special                              # noqa: B018  # _PyObject_LookupSpecial
    _sequence_concat                             # noqa: B018  # PySequence_Concat, PySequence_InPlaceConcat
    _bella_new_instance                          # noqa: B018  # tp_alloc: a type's __new__ makes its instance
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_new_instance: Callable[..., Any] = _missing
    _number_index: Callable[..., int] = _missing
    _lookup_special: Callable[..., tuple[Any, ...]] = _missing
    _sequence_concat: Callable[..., object] = _missing

_builtin_abs = abs
_builtin_pow = pow
_SSIZE_MAX = 2**63 - 1
_SSIZE_MIN = -(2**63)


def _positional(name: str, nargs: int, lo: int, hi: int) -> None:   # _PyArg_CheckPositional
    if nargs < lo:
        raise TypeError(name + " expected " + ("" if lo == hi else "at least ") + str(lo) + (" argument" if lo == 1 else " arguments") + ", got " + str(nargs))
    if nargs > hi:
        raise TypeError(name + " expected " + ("" if lo == hi else "at most ") + str(hi) + (" argument" if hi == 1 else " arguments") + ", got " + str(nargs))


def _noargs(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:   # METH_NOARGS
    if kwds:
        raise TypeError(name + "() takes no keyword arguments")
    if args:
        raise TypeError(name + "() takes no arguments (" + str(len(args)) + " given)")


def _named(f: object, name: str) -> object:
    f.__name__ = name                            # type: ignore[attr-defined]
    f.__qualname__ = name                        # type: ignore[attr-defined]
    return f


def _fastcall(name: str, nargs: int, op: object) -> object:   # METH_FASTCALL, with the clinic's check
    def f(*args: object, **kwds: object) -> object:
        if kwds:
            raise TypeError("_operator." + name + "() takes no keyword arguments")
        _positional(name, len(args), nargs, nargs)
        return op(*args)                         # type: ignore[operator]
    return _named(f, name)


def _meth_o(name: str, op: object) -> object:    # METH_O
    def f(*args: object, **kwds: object) -> object:
        if kwds:
            raise TypeError("_operator." + name + "() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("_operator." + name + "() takes exactly one argument (" + str(len(args)) + " given)")
        return op(args[0])                       # type: ignore[operator]
    return _named(f, name)


# ---- the operators ----
truth = _meth_o("truth", lambda a: not not a)    # noqa: SIM208
add = _fastcall("add", 2, lambda a, b: a + b)
sub = _fastcall("sub", 2, lambda a, b: a - b)
mul = _fastcall("mul", 2, lambda a, b: a * b)
matmul = _fastcall("matmul", 2, lambda a, b: a @ b)
floordiv = _fastcall("floordiv", 2, lambda a, b: a // b)
truediv = _fastcall("truediv", 2, lambda a, b: a / b)
mod = _fastcall("mod", 2, lambda a, b: a % b)
neg = _meth_o("neg", lambda a: -a)
pos = _meth_o("pos", lambda a: +a)
abs = _meth_o("abs", lambda a: _builtin_abs(a))
inv = _meth_o("inv", lambda a: ~a)
invert = _meth_o("invert", lambda a: ~a)
lshift = _fastcall("lshift", 2, lambda a, b: a << b)
rshift = _fastcall("rshift", 2, lambda a, b: a >> b)
not_ = _meth_o("not_", lambda a: not a)
and_ = _fastcall("and_", 2, lambda a, b: a & b)
xor = _fastcall("xor", 2, lambda a, b: a ^ b)
or_ = _fastcall("or_", 2, lambda a, b: a | b)
eq = _fastcall("eq", 2, lambda a, b: a == b)
ne = _fastcall("ne", 2, lambda a, b: a != b)
lt = _fastcall("lt", 2, lambda a, b: a < b)
le = _fastcall("le", 2, lambda a, b: a <= b)
gt = _fastcall("gt", 2, lambda a, b: a > b)
ge = _fastcall("ge", 2, lambda a, b: a >= b)
pow = _fastcall("pow", 2, lambda a, b: a ** b)
is_ = _fastcall("is_", 2, lambda a, b: a is b)
is_not = _fastcall("is_not", 2, lambda a, b: a is not b)
is_none = _meth_o("is_none", lambda a: a is None)
is_not_none = _meth_o("is_not_none", lambda a: a is not None)
index = _meth_o("index", lambda a: _number_index(a))


def _iadd(a: object, b: object) -> object:
    a += b  # type: ignore[operator]
    return a


def _isub(a: object, b: object) -> object:
    a -= b  # type: ignore[operator]
    return a


def _imul(a: object, b: object) -> object:
    a *= b  # type: ignore[operator]
    return a


def _imatmul(a: object, b: object) -> object:
    a @= b  # type: ignore[operator]
    return a


def _ifloordiv(a: object, b: object) -> object:
    a //= b  # type: ignore[operator]
    return a


def _itruediv(a: object, b: object) -> object:
    a /= b  # type: ignore[operator]
    return a


def _imod(a: object, b: object) -> object:
    a %= b  # type: ignore[operator]
    return a


def _ilshift(a: object, b: object) -> object:
    a <<= b  # type: ignore[operator]
    return a


def _irshift(a: object, b: object) -> object:
    a >>= b  # type: ignore[operator]
    return a


def _iand(a: object, b: object) -> object:
    a &= b  # type: ignore[operator]
    return a


def _ixor(a: object, b: object) -> object:
    a ^= b  # type: ignore[operator]
    return a


def _ior(a: object, b: object) -> object:
    a |= b  # type: ignore[operator]
    return a


def _ipow(a: object, b: object) -> object:
    a **= b  # type: ignore[operator]
    return a


iadd = _fastcall("iadd", 2, _iadd)
isub = _fastcall("isub", 2, _isub)
imul = _fastcall("imul", 2, _imul)
imatmul = _fastcall("imatmul", 2, _imatmul)
ifloordiv = _fastcall("ifloordiv", 2, _ifloordiv)
itruediv = _fastcall("itruediv", 2, _itruediv)
imod = _fastcall("imod", 2, _imod)
ilshift = _fastcall("ilshift", 2, _ilshift)
irshift = _fastcall("irshift", 2, _irshift)
iand = _fastcall("iand", 2, _iand)
ixor = _fastcall("ixor", 2, _ixor)
ior = _fastcall("ior", 2, _ior)
ipow = _fastcall("ipow", 2, _ipow)
concat = _fastcall("concat", 2, lambda a, b: _sequence_concat(a, b, False))
iconcat = _fastcall("iconcat", 2, lambda a, b: _sequence_concat(a, b, True))
contains = _fastcall("contains", 2, lambda a, b: b in a)


def _getitem(a: object, b: object) -> object:
    return a[b]  # type: ignore[index]


def _setitem(a: object, b: object, c: object) -> None:
    a[b] = c  # type: ignore[index]


def _delitem(a: object, b: object) -> None:
    del a[b]  # type: ignore[attr-defined]


getitem = _fastcall("getitem", 2, _getitem)
setitem = _fastcall("setitem", 3, _setitem)
delitem = _fastcall("delitem", 2, _delitem)


# ---- _PySequence_IterSearch ----
def _search_iter(seq: object) -> object:
    try:
        return iter(seq)  # type: ignore[call-overload]
    except TypeError:
        pass
    raise TypeError("argument of type '" + type(seq).__name__ + "' is not iterable")


def _index_of(a: object, b: object) -> int:      # PySequence_Index
    it = _search_iter(a)
    n = 0
    while True:
        try:
            item = next(it)  # type: ignore[call-overload]
        except StopIteration:
            break
        found = item is b or item == b
        del item
        if found:
            return n
        n += 1
    raise ValueError("sequence.index(x): x not in sequence")


def _count_of(a: object, b: object) -> int:      # PySequence_Count
    it = _search_iter(a)
    n = 0
    while True:
        try:
            item = next(it)  # type: ignore[call-overload]
        except StopIteration:
            return n
        if item is b or item == b:
            n += 1
        del item


indexOf = _fastcall("indexOf", 2, _index_of)
countOf = _fastcall("countOf", 2, _count_of)


def length_hint(*args: object, **kwds: object) -> int:     # PyObject_LengthHint
    if kwds:
        raise TypeError("_operator.length_hint() takes no keyword arguments")
    _positional("length_hint", len(args), 1, 2)
    obj = args[0]
    default = 0
    if len(args) > 1:
        default = _number_index(args[1])
        if not _SSIZE_MIN <= default <= _SSIZE_MAX:
            raise OverflowError("Python int too large to convert to C ssize_t")
    if _lookup_special(obj, "__len__"):          # _PyObject_HasLen
        failed = False
        try:
            return len(obj)  # type: ignore[arg-type]
        except TypeError:
            failed = True
        del failed
    found = _lookup_special(obj, "__length_hint__")
    if not found:
        getattr(type(obj), "__length_hint__", None)   # refused here if CPython's type has it and this one does not yet
        return default
    try:
        result = found[0]()
    except TypeError:
        return default
    del found
    if result is NotImplemented:
        return default
    if not issubclass(type(result), int):
        raise TypeError(_qualified(type(obj)) + ".__length_hint__() must return an int, not " + _qualified(type(result)))
    res = int.__index__(result)
    if not _SSIZE_MIN <= res <= _SSIZE_MAX:
        raise OverflowError("Python int too large to convert to C ssize_t")
    if res < 0:
        raise ValueError(_qualified(type(obj)) + ".__length_hint__() must return a non-negative int")
    return res


def _qualified(t: type) -> str:                  # %T
    module = t.__module__
    return t.__qualname__ if module in ("builtins", "__main__") else module + "." + t.__qualname__


def _compare_digest(*args: object, **kwds: object) -> bool:
    if kwds:
        raise TypeError("_operator._compare_digest() takes no keyword arguments")
    _positional("_compare_digest", len(args), 2, 2)
    a, b = args
    if issubclass(type(a), str) and issubclass(type(b), str):
        if not a.isascii() or not b.isascii():   # type: ignore[attr-defined]
            raise TypeError("comparing strings with non-ASCII characters is not supported")
        left = a.encode("ascii")                 # type: ignore[attr-defined]
        right = b.encode("ascii")                # type: ignore[attr-defined]
    else:
        if not _has_buffer(a) and not _has_buffer(b):
            raise TypeError("unsupported operand types(s) or combination of types: '" + type(a).__name__ + "' and '" + type(b).__name__ + "'")
        if not _has_buffer(a):
            raise TypeError("a bytes-like object is required, not '" + type(a).__name__ + "'")
        if not _has_buffer(b):
            raise TypeError("a bytes-like object is required, not '" + type(b).__name__ + "'")
        left = bytes(a)  # type: ignore[call-overload]
        right = bytes(b)  # type: ignore[call-overload]
    # _tscmp: the loop's length is b's, and every byte of it is looked at
    length = len(right)
    if len(left) == length:
        result = 0
    else:
        left = right
        result = 1
    i = 0
    while i < length:
        result |= left[i] ^ right[i]
        i += 1
    return result == 0


def _has_buffer(v: object) -> bool:              # PyObject_CheckBuffer
    return issubclass(type(v), (bytes, bytearray, memoryview))


def call(*args: object, **kwds: object) -> object:
    _positional("call", len(args), 1, _SSIZE_MAX)
    return args[0](*args[1:], **kwds)            # type: ignore[operator]


# ---- Py_ReprEnter ----
_repr_running: list[object] = []


def _repr_enter(obj: object) -> bool:
    for held in _repr_running:
        if held is obj:
            return False
    _repr_running.append(obj)
    return True


def _repr_leave(obj: object) -> None:
    i = len(_repr_running) - 1
    while i >= 0:
        if _repr_running[i] is obj:
            del _repr_running[i]
            return
        i -= 1


# ---- itemgetter ----
class itemgetter:
    __module__ = "operator"
    __slots__ = ("_item", "_nitems")

    def __new__(cls, *args: object, **kwds: object) -> object:
        if kwds:
            raise TypeError("itemgetter() takes no keyword arguments")
        nitems = len(args)
        if nitems <= 1:
            _positional("itemgetter", nitems, 1, 1)
            item = args[0]
        else:
            item = args
        self = _bella_new_instance(cls)
        self._item = item
        self._nitems = nitems
        return self

    def __call__(self, *args: object, **kwds: object) -> object:
        if kwds:
            raise TypeError("itemgetter() takes no keyword arguments")
        _positional("itemgetter", len(args), 1, 1)
        obj = args[0]
        if self._nitems == 1:
            return obj[self._item]  # type: ignore[index]
        return tuple([obj[item] for item in self._item])  # type: ignore[index]

    def __repr__(self) -> str:
        if not _repr_enter(self):
            return "operator.itemgetter(...)"
        try:
            if self._nitems == 1:
                return "operator.itemgetter(" + repr(self._item) + ")"
            return "operator.itemgetter" + repr(self._item)
        finally:
            _repr_leave(self)

    def __reduce__(self, *args: object, **kwds: object) -> object:
        _noargs("itemgetter.__reduce__", args, kwds)
        if self._nitems == 1:
            return (type(self), (self._item,))
        return (type(self), self._item)


# ---- attrgetter ----
class attrgetter:
    __module__ = "operator"
    __slots__ = ("_attr", "_nattrs")

    def __new__(cls, *args: object, **kwds: object) -> object:
        if kwds:
            raise TypeError("attrgetter() takes no keyword arguments")
        nattrs = len(args)
        if nattrs <= 1:
            _positional("attrgetter", nattrs, 1, 1)
        names: list[object] = []
        for item in args:
            if not issubclass(type(item), str):
                raise TypeError("attribute name must be a string")
            names.append(tuple(item.split(".")) if "." in item else item)  # type: ignore[attr-defined, operator]
        self = _bella_new_instance(cls)
        self._attr = tuple(names)
        self._nattrs = nattrs
        return self

    def __call__(self, *args: object, **kwds: object) -> object:
        if kwds:
            raise TypeError("attrgetter() takes no keyword arguments")
        _positional("attrgetter", len(args), 1, 1)
        obj = args[0]
        if self._nattrs == 1:
            return _dotted_getattr(obj, self._attr[0])
        return tuple([_dotted_getattr(obj, attr) for attr in self._attr])

    def __repr__(self) -> str:
        if not _repr_enter(self):
            return "operator.attrgetter(...)"
        try:
            if self._nattrs == 1:
                return "operator.attrgetter(" + repr(_dot_joined(self._attr[0])) + ")"
            return "operator.attrgetter" + repr(tuple([_dot_joined(a) for a in self._attr]))
        finally:
            _repr_leave(self)

    def __reduce__(self, *args: object, **kwds: object) -> object:
        _noargs("attrgetter.__reduce__", args, kwds)
        return (type(self), tuple([_dot_joined(a) for a in self._attr]))


def _dotted_getattr(obj: object, attr: object) -> object:
    if type(attr) is tuple:                      # chained getattr
        for name in attr:
            obj = getattr(obj, name)
        return obj
    return getattr(obj, attr)  # type: ignore[call-overload]


def _dot_joined(attr: object) -> object:
    return ".".join(attr) if type(attr) is tuple else attr


# ---- methodcaller ----
class methodcaller:
    __module__ = "operator"
    __slots__ = ("_a_name", "_b_args", "_c_kwds")

    def __new__(cls, *args: object, **kwds: object) -> object:
        if len(args) < 1:
            raise TypeError("methodcaller needs at least one argument, the method name")
        name = args[0]
        if not issubclass(type(name), str):
            raise TypeError("method name must be a string")
        self = _bella_new_instance(cls)
        self._c_kwds = kwds
        self._a_name = name
        self._b_args = args[1:]
        return self

    def __call__(self, *args: object, **kwds: object) -> object:
        # the vectorcall path checks in the other order; past _METHODCALLER_MAX_ARGS there is only tp_call
        if 1 + len(self._b_args) + len(self._c_kwds) < 8:
            _positional("methodcaller", len(args), 1, 1)
        if kwds:
            raise TypeError("methodcaller() takes no keyword arguments")
        _positional("methodcaller", len(args), 1, 1)
        method = getattr(args[0], self._a_name)
        return method(*self._b_args, **self._c_kwds)

    def __repr__(self) -> str:
        if not _repr_enter(self):
            return "operator.methodcaller(...)"
        try:
            parts = [repr(a) for a in self._b_args]
            for key in self._c_kwds:
                parts.append(key + "=" + repr(self._c_kwds[key]))
            if not parts:
                return "operator.methodcaller(" + repr(self._a_name) + ")"
            return "operator.methodcaller(" + repr(self._a_name) + ", " + ", ".join(parts) + ")"
        finally:
            _repr_leave(self)

    def __reduce__(self, *args: object, **kwds: object) -> object:
        _noargs("methodcaller.__reduce__", args, kwds)
        if not self._c_kwds:
            return (type(self), (self._a_name, *self._b_args))
        from functools import partial
        return (partial(type(self), self._a_name, **self._c_kwds), self._b_args)
