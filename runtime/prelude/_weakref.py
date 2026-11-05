"""_weakref, in Python, from Modules/_weakref.c and Objects/weakrefobject.c; see itertools.py beside it.

The lists are the object model's (object.hpp, `weak_link`): a reference here is an object of one of
these classes with a record there, which the runtime's primitives read. What a program's reference can
tell comes from the C line by line: which references are shared, the order of the list, a dead one's
repr and hash. A proxy forwards attribute access in the runtime (`forwards_attributes`), and everything
else from the methods below, as the C's slots do, each unwrapping the proxies among its operands.
"""

__all__ = ["CallableProxyType", "ProxyType", "ReferenceType", "_remove_dead_weakref", "getweakrefcount", "getweakrefs",
           "proxy", "ref"]

__name__ = "_weakref"

try:
    _number_index                                # noqa: B018  # PyNumber_Index, given by the runtime
    _lookup_special                              # noqa: B018  # _PyObject_LookupSpecial
    _tp_name                                     # noqa: B018  # Py_TYPE(obj)->tp_name
    _weak_supported                              # noqa: B018  # _PyType_SUPPORTS_WEAKREFS
    _weak_basic                                  # noqa: B018  # try_reuse_basic_ref
    _weak_link                                   # noqa: B018  # init_weakref and insert_weakref
    _weak_get                                    # noqa: B018  # _PyWeakref_GET_REF, None when dead
    _weak_list                                   # noqa: B018  # the object's list, in order
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _number_index: Callable[..., int] = _missing
    _lookup_special: Callable[..., tuple[Any, ...]] = _missing
    _tp_name: Callable[..., str] = _missing
    _weak_supported: Callable[..., bool] = _missing
    _weak_basic: Callable[..., Any] = _missing
    _weak_link: Callable[..., None] = _missing
    _weak_get: Callable[..., Any] = _missing
    _weak_list: Callable[..., list[Any]] = _missing

_BASIC_REF = 0
_BASIC_PROXY = 1
_OTHER = 2


def _positional(name: str, nargs: int, lo: int, hi: int) -> None:   # _PyArg_CheckPositional, PyArg_UnpackTuple
    if nargs < lo:
        raise TypeError(name + " expected " + ("" if lo == hi else "at least ") + str(lo) + (" argument" if lo == 1 else " arguments") + ", got " + str(nargs))
    if nargs > hi:
        raise TypeError(name + " expected " + ("" if lo == hi else "at most ") + str(hi) + (" argument" if hi == 1 else " arguments") + ", got " + str(nargs))


def _qualified(t: type) -> str:                  # %T
    module = t.__module__
    return t.__qualname__ if module in ("builtins", "__main__") else module + "." + t.__qualname__


def _get_or_create(cls: type, ob: object, callback: object) -> object:   # get_or_create_weakref
    if not _weak_supported(ob):
        raise TypeError("cannot create weak reference to '" + _tp_name(ob) + "' object")
    kind = _OTHER
    if callback is None:
        if cls is ReferenceType:
            kind = _BASIC_REF
        elif cls is ProxyType or cls is CallableProxyType:
            kind = _BASIC_PROXY
        if kind != _OTHER:
            found = _weak_basic(ob, kind)
            if found is not None:
                return found
    self = object.__new__(cls)
    _weak_link(self, ob, callback, kind)
    return self


def _receiver(self: object, name: str) -> None:   # wrapperdescr_call
    if not issubclass(type(self), ReferenceType):
        raise TypeError("descriptor '" + name + "' requires a 'weakref.ReferenceType' object but received a '" + _tp_name(self) + "'")


class ReferenceType:
    __module__ = "weakref"
    __slots__ = ("_hash",)

    def __new__(cls, *args: object, **kwds: object) -> object:   # weakref___new__: keywords are __init__'s to refuse
        if not issubclass(type(cls), type):      # tp_new_wrapper
            raise TypeError("weakref.ReferenceType.__new__(X): X is not a type object (" + type(cls).__name__ + ")")
        if not issubclass(cls, ReferenceType):
            raise TypeError("weakref.ReferenceType.__new__(" + cls.__name__ + "): " + cls.__name__ + " is not a subtype of weakref.ReferenceType")
        _positional("__new__", len(args), 1, 2)
        return _get_or_create(cls, args[0], args[1] if len(args) > 1 else None)

    def __init__(self, *args: object, **kwds: object) -> None:   # weakref___init__
        _receiver(self, "__init__")
        if kwds:
            raise TypeError("ref() takes no keyword arguments")
        _positional("__init__", len(args), 1, 2)

    def __call__(self, *args: object, **kwds: object) -> object:   # weakref_vectorcall
        _receiver(self, "__call__")
        if kwds:
            raise TypeError("weakref() takes no keyword arguments")
        _positional("weakref", len(args), 0, 0)
        return _weak_get(self)

    def __hash__(self) -> int:                   # weakref_hash: the target's, kept when it dies
        _receiver(self, "__hash__")
        try:
            return self._hash
        except AttributeError:
            pass
        obj = _weak_get(self)
        if obj is None:
            raise TypeError("weak object has gone away")
        self._hash = hash(obj)
        return self._hash

    def __repr__(self) -> str:
        _receiver(self, "__repr__")
        obj = _weak_get(self)
        if obj is None:
            return "<weakref at " + hex(id(self)) + "; dead>"
        found = _lookup_special(obj, "__name__")
        text = "<weakref at " + hex(id(self)) + "; to '" + _qualified(type(obj)) + "' at " + hex(id(obj))
        if found and issubclass(type(found[0]), str):
            return text + " (" + found[0] + ")>"
        return text + ">"

    def __eq__(self, other: object) -> object:   # weakref_richcompare
        _receiver(self, "__eq__")
        if not issubclass(type(other), ReferenceType) and type(other) not in (ProxyType, CallableProxyType):
            return NotImplemented
        obj = _weak_get(self)
        other_obj = _weak_get(other)
        if obj is None or other_obj is None:
            return self is other
        return obj == other_obj

    def __ne__(self, other: object) -> object:
        _receiver(self, "__ne__")
        if not issubclass(type(other), ReferenceType) and type(other) not in (ProxyType, CallableProxyType):
            return NotImplemented
        obj = _weak_get(self)
        other_obj = _weak_get(other)
        if obj is None or other_obj is None:
            return self is not other
        return obj != other_obj

    __hash__ = __hash__                          # defining __eq__ must not make it unhashable


ref = ReferenceType


def _unwrap(v: object) -> object:                # proxy_unwrap
    if type(v) is ProxyType or type(v) is CallableProxyType:
        target = _weak_get(v)
        if target is None:
            raise ReferenceError("weakly-referenced object no longer exists")
        return target
    return v


def _binary(op: object) -> object:               # WRAP_BINARY: for a method and its reflected form alike
    def method(self: object, other: object) -> object:
        return op(_unwrap(self), _unwrap(other))  # type: ignore[operator]
    return method


def _reflected(op: object) -> object:
    def method(self: object, other: object) -> object:
        return op(_unwrap(other), _unwrap(self))  # type: ignore[operator]
    return method


def _unary(op: object) -> object:                # WRAP_UNARY
    def method(self: object) -> object:
        return op(_unwrap(self))                 # type: ignore[operator]
    return method


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


def _proxy_repr(self: object) -> str:
    obj = _weak_get(self)
    if obj is None:
        return "<weakproxy at " + hex(id(self)) + "; dead>"
    return "<weakproxy at " + hex(id(self)) + "; to '" + _qualified(type(obj)) + "' at " + hex(id(obj)) + ">"


def _proxy_new(cls: type, *args: object, **kwds: object) -> object:   # no tp_new
    raise TypeError("cannot create 'weakref." + cls.__name__ + "' instances")


def _proxy_setattr(self: object, name: str, value: object) -> None:
    setattr(_unwrap(self), name, value)


def _proxy_delattr(self: object, name: str) -> None:
    delattr(_unwrap(self), name)


def _proxy_len(self: object) -> int:
    return len(_unwrap(self))                    # type: ignore[arg-type]


def _proxy_contains(self: object, value: object) -> bool:
    return value in _unwrap(self)                # type: ignore[operator]


def _proxy_setitem(self: object, key: object, value: object) -> None:
    _unwrap(self)[key] = value                   # type: ignore[index]


def _proxy_delitem(self: object, key: object) -> None:
    del _unwrap(self)[key]                       # type: ignore[attr-defined]


def _proxy_iter(self: object) -> object:
    return iter(_unwrap(self))                   # type: ignore[call-overload]


def _proxy_next(self: object) -> object:
    obj = _unwrap(self)
    if not _lookup_special(obj, "__next__"):
        raise TypeError("Weakref proxy referenced a non-iterator '" + _tp_name(obj) + "' object")
    return next(obj)                             # type: ignore[call-overload]


def _proxy_pow(self: object, other: object, mod: object = None) -> object:   # WRAP_TERNARY
    return pow(_unwrap(self), _unwrap(other), _unwrap(mod))  # type: ignore[call-overload]


def _proxy_rpow(self: object, other: object, mod: object = None) -> object:
    return pow(_unwrap(other), _unwrap(self), _unwrap(mod))  # type: ignore[call-overload]


def _proxy_bytes(self: object) -> object:        # WRAP_METHOD
    return _unwrap(self).__bytes__()             # type: ignore[attr-defined]


def _proxy_reversed(self: object) -> object:
    return _unwrap(self).__reversed__()          # type: ignore[attr-defined]


def _proxy_call(self: object, *args: object, **kwds: object) -> object:
    return _unwrap(self)(*[_unwrap(a) for a in args], **kwds)  # type: ignore[operator]


_PROXY_NAMESPACE: dict[str, object] = {
    "__module__": "weakref", "__slots__": (), "__new__": _proxy_new, "__repr__": _proxy_repr,
    "__setattr__": _proxy_setattr, "__delattr__": _proxy_delattr,
    "__str__": _unary(str), "__bool__": _unary(bool), "__len__": _proxy_len, "__contains__": _proxy_contains,
    "__getitem__": _binary(lambda a, b: a[b]), "__setitem__": _proxy_setitem, "__delitem__": _proxy_delitem,
    "__iter__": _proxy_iter, "__next__": _proxy_next,
    "__eq__": _binary(lambda a, b: a == b), "__ne__": _binary(lambda a, b: a != b), "__lt__": _binary(lambda a, b: a < b),
    "__le__": _binary(lambda a, b: a <= b), "__gt__": _binary(lambda a, b: a > b), "__ge__": _binary(lambda a, b: a >= b),
    "__neg__": _unary(lambda a: -a), "__pos__": _unary(lambda a: +a), "__abs__": _unary(abs), "__invert__": _unary(lambda a: ~a),
    "__int__": _unary(int), "__float__": _unary(float), "__index__": _unary(_number_index),
    "__add__": _binary(lambda a, b: a + b), "__radd__": _reflected(lambda a, b: a + b), "__iadd__": _binary(_iadd),
    "__sub__": _binary(lambda a, b: a - b), "__rsub__": _reflected(lambda a, b: a - b), "__isub__": _binary(_isub),
    "__mul__": _binary(lambda a, b: a * b), "__rmul__": _reflected(lambda a, b: a * b), "__imul__": _binary(_imul),
    "__matmul__": _binary(lambda a, b: a @ b), "__rmatmul__": _reflected(lambda a, b: a @ b), "__imatmul__": _binary(_imatmul),
    "__floordiv__": _binary(lambda a, b: a // b), "__rfloordiv__": _reflected(lambda a, b: a // b), "__ifloordiv__": _binary(_ifloordiv),
    "__truediv__": _binary(lambda a, b: a / b), "__rtruediv__": _reflected(lambda a, b: a / b), "__itruediv__": _binary(_itruediv),
    "__mod__": _binary(lambda a, b: a % b), "__rmod__": _reflected(lambda a, b: a % b), "__imod__": _binary(_imod),
    "__divmod__": _binary(divmod), "__rdivmod__": _reflected(divmod),
    "__pow__": _proxy_pow, "__rpow__": _proxy_rpow, "__ipow__": _binary(_ipow),
    "__lshift__": _binary(lambda a, b: a << b), "__rlshift__": _reflected(lambda a, b: a << b), "__ilshift__": _binary(_ilshift),
    "__rshift__": _binary(lambda a, b: a >> b), "__rrshift__": _reflected(lambda a, b: a >> b), "__irshift__": _binary(_irshift),
    "__and__": _binary(lambda a, b: a & b), "__rand__": _reflected(lambda a, b: a & b), "__iand__": _binary(_iand),
    "__or__": _binary(lambda a, b: a | b), "__ror__": _reflected(lambda a, b: a | b), "__ior__": _binary(_ior),
    "__xor__": _binary(lambda a, b: a ^ b), "__rxor__": _reflected(lambda a, b: a ^ b), "__ixor__": _binary(_ixor),
}
ProxyType = type("ProxyType", (), {**_PROXY_NAMESPACE, "__bytes__": _proxy_bytes, "__reversed__": _proxy_reversed})
CallableProxyType = type("CallableProxyType", (), {**_PROXY_NAMESPACE, "__call__": _proxy_call})


def proxy(*args: object, **kwds: object) -> object:
    if kwds:
        raise TypeError("_weakref.proxy() takes no keyword arguments")
    _positional("proxy", len(args), 1, 2)
    callback = args[1] if len(args) > 1 else None
    return _get_or_create(CallableProxyType if callable(args[0]) else ProxyType, args[0], callback)


def getweakrefcount(*args: object, **kwds: object) -> int:
    if kwds:
        raise TypeError("_weakref.getweakrefcount() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("_weakref.getweakrefcount() takes exactly one argument (" + str(len(args)) + " given)")
    return len(_weak_list(args[0]))


def getweakrefs(*args: object, **kwds: object) -> list[object]:
    if kwds:
        raise TypeError("_weakref.getweakrefs() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("_weakref.getweakrefs() takes exactly one argument (" + str(len(args)) + " given)")
    return _weak_list(args[0])


def _remove_dead_weakref(*args: object, **kwds: object) -> None:   # _PyDict_DelItemIf(dct, key, is_dead_weakref)
    if kwds:
        raise TypeError("_weakref._remove_dead_weakref() takes no keyword arguments")
    _positional("_remove_dead_weakref", len(args), 2, 2)
    dct, key = args
    if not issubclass(type(dct), dict):
        raise TypeError("_remove_dead_weakref() argument 1 must be dict, not " + ("None" if dct is None else type(dct).__name__))
    hash(key)                                    # its own message, and not a dict's about a key
    absent = object()
    value = dict.get(dct, key, absent)  # type: ignore[call-overload]
    if value is absent:
        return
    if not issubclass(type(value), ReferenceType) and type(value) not in (ProxyType, CallableProxyType):
        raise TypeError("not a weakref")
    if _weak_get(value) is None:
        dict.__delitem__(dct, key)  # type: ignore[arg-type]
