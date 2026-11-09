"""_bisect, in Python (Modules/_bisectmodule.c): bisect_left, bisect_right, insort_left and insort_right with the clinic's parsing
(lo a non-negative index, hi an index or None where -1 means the length, as the C's default does), PySequence_Size and the sequence
slot's own errors for what is no sequence, the comparison `x < key(a[mid])` and insort's one key call. bisect imports * from here."""

__all__ = ["bisect_left", "bisect_right", "insort_left", "insort_right"]

__name__ = "_bisect"

try:
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _tp_name                                     # noqa: B018  # Py_TYPE(o)->tp_name
    _number_index                                # noqa: B018  # PyNumber_Index
    _is_c_type                                   # noqa: B018  # the object's type is CPython's, not a class of the program's
    _unpack_keywords                             # noqa: B018  # _PyArg_UnpackKeywords
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

    def _is_c_type(o: object) -> bool:
        return type(o).__module__ != "__main__"   # for probing this file under CPython
    _unpack_keywords: Callable[..., Any] = _missing

_ABSENT: object = object()
_MAXSIZE = 2**63 - 1
# the C mapping types a phase-1 program can hold: mp_subscript and no sq_item, so no sequence for the slot's purposes
_C_MAPPINGS = ("dict", "mappingproxy", "collections.OrderedDict", "collections.defaultdict", "re.Match", "types.GenericAlias", "typing.Union",
               "weakref.ProxyType", "weakref.CallableProxyType", "_contextvars.Context")


def _c_mapping(a: object) -> bool:               # one of CPython's mapping types (mp_subscript, no sq_item), never a class of the program's named like one
    return _is_c_type(a) and _tp_name(a) in _C_MAPPINGS


def _ssize(value: object, overflow: str) -> int:   # PyLong_AsSsize_t after PyNumber_Index
    n = _number_index(value)
    if n > _MAXSIZE or n < -_MAXSIZE - 1:
        raise OverflowError(overflow)
    return n


def _arguments(fname: str, args: tuple[object, ...], kwds: dict[str, object]) -> tuple[object, object, int, int, object]:
    """The clinic's (a, x, lo=0, hi=None, *, key=None) through _PyArg_UnpackKeywords, with its messages in its order."""
    values = _unpack_keywords(fname, ("a", "x", "lo", "hi", "key"), 0, 2, 4, 0, args, kwds, _ABSENT)
    a, x, lo_given, hi_given, key = values
    lo = 0
    if lo_given is not _ABSENT:
        lo = _ssize(lo_given, "Python int too large to convert to C ssize_t")
        if lo < 0:
            raise ValueError("lo cannot be negative")
    hi = -1
    if hi_given is not _ABSENT and hi_given is not None:   # _Py_convert_optional_to_ssize_t
        if not hasattr(type(hi_given), "__index__"):
            raise TypeError("argument should be integer or None, not '" + _tp_name(hi_given) + "'")
        hi = _ssize(hi_given, "cannot fit '" + _tp_name(hi_given) + "' into an index-sized integer")
    if key is _ABSENT:
        key = None
    return a, x, lo, hi, key


def _size(a: object) -> int:                     # PySequence_Size
    if not hasattr(type(a), "__len__"):
        raise TypeError("object of type '" + _tp_name(a) + "' has no len()")
    if _c_mapping(a):
        raise TypeError(_tp_name(a) + " is not a sequence")
    return len(a)  # type: ignore[arg-type]


def _check_sq_item(a: object) -> None:           # get_sq_item: the sequence slot, or the C's two messages
    if hasattr(type(a), "__getitem__"):
        if _c_mapping(a):                        # mp_subscript alone
            raise TypeError(_tp_name(a) + " is not a sequence")
        return                                   # a sequence type, or a class of the program (a subclass of dict too): the heap type has the slot
    raise TypeError("'" + _tp_name(a) + "' object does not support indexing")


def _bisect(a: object, x: object, lo: int, hi: int, key: object, right: bool) -> int:   # internal_bisect_right / _left
    if hi == -1:
        hi = _size(a)
    _check_sq_item(a)
    while lo < hi:
        mid = (lo + hi) // 2
        item = a[mid]  # type: ignore[index]
        if key is not None:
            item = key(item)  # type: ignore[operator]
        if (x < item) if right else (item < x):
            if right:
                hi = mid
            else:
                lo = mid + 1
        elif right:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _insort(fname: str, args: tuple[object, ...], kwds: dict[str, object], right: bool) -> None:
    a, x, lo, hi, key = _arguments(fname, args, kwds)
    index = _bisect(a, x if key is None else key(x), lo, hi, key, right)  # type: ignore[operator]
    a.insert(index, x)  # type: ignore[attr-defined]


def bisect_right(*args: object, **kwds: object) -> int:
    """Return the index where to insert item x in list a, assuming a is sorted.

The return value i is such that all e in a[:i] have e <= x, and all e in
a[i:] have e > x.  So if x already appears in the list, a.insert(i, x)
will insert just after the rightmost x already there.

Optional args lo (default 0) and hi (default len(a)) bound the
slice of a to be searched.

A custom key function can be supplied to customize the sort order."""
    a, x, lo, hi, key = _arguments("bisect_right", args, kwds)
    return _bisect(a, x, lo, hi, key, True)


def bisect_left(*args: object, **kwds: object) -> int:
    """Return the index where to insert item x in list a, assuming a is sorted.

The return value i is such that all e in a[:i] have e < x, and all e in
a[i:] have e >= x.  So if x already appears in the list, a.insert(i, x)
will insert just before the leftmost x already there.

Optional args lo (default 0) and hi (default len(a)) bound the
slice of a to be searched.

A custom key function can be supplied to customize the sort order."""
    a, x, lo, hi, key = _arguments("bisect_left", args, kwds)
    return _bisect(a, x, lo, hi, key, False)


def insort_right(*args: object, **kwds: object) -> None:
    """Insert item x in list a, and keep it sorted assuming a is sorted.

If x is already in a, insert it to the right of the rightmost x.

Optional args lo (default 0) and hi (default len(a)) bound the
slice of a to be searched.

A custom key function can be supplied to customize the sort order."""
    _insort("insort_right", args, kwds, True)


def insort_left(*args: object, **kwds: object) -> None:
    """Insert item x in list a, and keep it sorted assuming a is sorted.

If x is already in a, insert it to the left of the leftmost x.

Optional args lo (default 0) and hi (default len(a)) bound the
slice of a to be searched.

A custom key function can be supplied to customize the sort order."""
    _insort("insort_left", args, kwds, False)
