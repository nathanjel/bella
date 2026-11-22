"""The iterating builtins, in Python (Python/bltinmodule.c, Objects/enumobject.c).

A module of its own because a class with a __new__ needs staticmethod in the builtins, which
builtins.py puts there only when it has finished. It runs as `builtins` too, and CPython runs it in
runtime/tests/test_prelude.py against the builtins it stands for.
"""

__all__ = ["reversed", "enumerate", "zip", "map", "filter", "min", "max", "sum", "any", "all"]
__intrinsics__ = ["_callable_iterator"]
__hidden_classes__ = ["callable_iterator"]       # a type of the builtins that is no name of theirs


try:
    _lookup_special                              # noqa: B018  # _PyObject_LookupSpecial, given by the compiled runtime
    _number_index                                # noqa: B018  # PyNumber_Index
    _sequence_check                              # noqa: B018  # PySequence_Check
    _tp_name                                     # noqa: B018  # Py_TYPE(obj)->tp_name
    _bella_new_instance                          # noqa: B018  # tp_alloc: this type's __new__ makes its instance
    _held_once                                   # noqa: B018  # _PyObject_IsUniquelyReferenced of a field's value
    _tuple_set                                   # noqa: B018  # PyTuple_SET_ITEM, on a tuple nothing else holds
    _is_c_type                                   # noqa: B018  # the object's type is CPython's, not a class of the program's
    _type_name                                   # noqa: B018  # _PyType_Name(Py_TYPE(x)): tp_name after its last dot, no attribute of the class (RL-767)
except NameError:
    import operator

    _bella_new_instance = object.__new__

    def _held_once(obj: object, name: str) -> bool:
        return False                             # under CPython a tuple is never used again

    def _tuple_set(target: object, i: int, value: object) -> None:
        raise ImportError("this file needs the runtime's primitives")

    _number_index = operator.index

    def _sequence_check(obj: object) -> bool:
        return not isinstance(obj, dict) and hasattr(type(obj), "__getitem__")

    def _tp_name(obj: object) -> str:
        t = type(obj)
        return t.__name__ if t.__module__ in ("builtins", "__main__") else t.__module__ + "." + t.__name__

    def _lookup_special(obj: object, name: str) -> tuple[object, ...]:
        """Run by CPython (runtime/tests/test_prelude.py): the bound special method in a tuple, or ()."""
        for c in type(obj).__mro__:
            if name in vars(c):
                found = vars(c)[name]
                get = getattr(type(found), "__get__", None)
                return (found if get is None else get(found, obj, type(obj)),)
        return ()

    def _is_c_type(value: object) -> bool:       # a stand-in for CPython's run of this file
        return type(value).__module__ != "__main__"

    def _type_name(value: object) -> str:        # a stand-in for CPython's run of this file
        return type(value).__name__

_END = object()


def _next_only(it: object) -> object:
    """An iterator the C holds, for a `for` of this file: its __next__ alone is called from here on. A `for` asks its
    operand for an iterator again, which is a second __iter__ call on an iterator of a class of the program's; the C took
    the iterator once (PyObject_GetIter) and calls tp_iternext (RL-765). The item is handed on and not kept: the C has
    let go of it before it asks for the next one, and a loop of this file does the same with `del` (RL-782)."""
    held: list[object] = []
    while True:
        held.append(next(it, _END))  # type: ignore[call-overload]
        if held[0] is _END:
            return
        yield held.pop()


def _tp_iter(iterable: object) -> object:        # PyObject_GetIter, once
    it = iter(iterable)  # type: ignore[call-overload]
    return it if _is_c_type(it) else _next_only(it)


class callable_iterator:                         # iter(callable, sentinel): Objects/iterobject.c, calliterobject
    __slots__ = ("_callable", "_sentinel")

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:                # calliter_iternext
        if self._callable is None:
            raise StopIteration
        stopped = False
        try:
            result = self._callable()
        except StopIteration:                    # PyErr_Clear: what it carried goes, and next() raises a new one
            stopped = True
        if not stopped and self._sentinel is not result and not self._sentinel == result:   # PyObject_RichCompareBool: the same object is equal
            return result
        self._callable = None
        self._sentinel = None
        raise StopIteration

    def __reduce__(self, *args: object, **kwds: object) -> object:   # calliter_reduce
        _no_arguments("callable_iterator.__reduce__", args, kwds)
        if self._callable is not None:         # exhausted: both are gone (None stands for C's NULL here, and a sentinel may be None)
            return (iter, (self._callable, self._sentinel))
        return (iter, ((),))


_SSIZE_MAX = 9223372036854775807                 # PY_SSIZE_T_MAX


def _no_arguments(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:
    """A METH_NOARGS method's check."""
    if kwds:
        raise TypeError(name + "() takes no keyword arguments")
    if args:
        raise TypeError(name + "() takes no arguments (" + str(len(args)) + " given)")


def _one_argument(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> object:
    """A METH_O method's check, and its argument."""
    if kwds:
        raise TypeError(name + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError(name + "() takes exactly one argument (" + str(len(args)) + " given)")
    return args[0]


def _callable_iterator(function: object, sentinel: object) -> object:
    if not callable(function):
        raise TypeError("iter(v, w): v must be callable")
    made = _bella_new_instance(callable_iterator)
    made._callable = function
    made._sentinel = sentinel
    return made


class reversed:
    """Return a reverse iterator over the values of the given sequence."""

    __slots__ = ("_index", "_seq")

    def __new__(cls, *args: object, **kwds: object) -> object:   # reversed_new_impl
        if cls is reversed and kwds:
            raise TypeError("reversed() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("reversed expected 1 argument, got " + str(len(args)))
        seq = args[0]
        found = _lookup_special(seq, "__reversed__")
        if found:
            if found[0] is None:
                raise TypeError("'" + _type_name(seq) + "' object is not reversible")
            return found[0]()  # type: ignore[operator]
        if not _sequence_check(seq):
            raise TypeError("'" + _tp_name(seq) + "' object is not reversible")
        self = _bella_new_instance(cls)
        self._index = len(seq) - 1  # type: ignore[arg-type]
        self._seq = seq
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:                # reversed_next
        index = self._index
        if index >= 0:
            ended = False
            try:
                item = self._seq[index]  # type: ignore[index]
            except BaseException as e:
                self._index = -1
                self._seq = None
                if not issubclass(type(e), (IndexError, StopIteration)):   # PyErr_ExceptionMatches asks the type (RL-464)
                    raise
                ended = True                     # PyErr_Clear: the iterator ends, and what next() raises then has no context of it
            if ended:
                raise StopIteration
            self._index = index - 1
            return item
        self._index = -1
        self._seq = None
        raise StopIteration

    def __length_hint__(self, *args: object, **kwds: object) -> int:   # reversed_len: the sequence's length is asked while an index stands
        _no_arguments("reversed.__length_hint__", args, kwds)
        if self._index == -1:
            return 0
        size = len(self._seq)  # type: ignore[arg-type]
        position = self._index + 1
        return 0 if size < position else position

    def __reduce__(self, *args: object, **kwds: object) -> object:   # reversed_reduce
        _no_arguments("reversed.__reduce__", args, kwds)
        if self._index != -1:
            return (type(self), (self._seq,), self._index)
        return (type(self), ((),))

    def __setstate__(self, *args: object, **kwds: object) -> None:   # reversed_setstate: PyLong_AsSsize_t, clipped to the sequence as it is now
        given = _one_argument("reversed.__setstate__", args, kwds)
        if not issubclass(type(given), int):
            raise TypeError("an integer is required")
        state = int.__index__(given)             # the int's own value, whatever a subclass's __int__ or comparisons say (RL-462)
        if not -_SSIZE_MAX - 1 <= state <= _SSIZE_MAX:
            raise OverflowError("Python int too large to convert to C ssize_t")
        if self._index != -1:                    # an exhausted one stays so
            size = len(self._seq)  # type: ignore[arg-type]
            self._index = -1 if state < -1 else size - 1 if state > size - 1 else state


class enumerate:
    """Return an enumerate object.

  iterable
    an object supporting iteration

The enumerate object yields pairs containing a count (from start, which
defaults to zero) and a value yielded by the iterable argument.

enumerate is useful for obtaining an indexed list:
    (0, seq[0]), (1, seq[1]), (2, seq[2]), ..."""

    __slots__ = ("_it", "_result", "_count")     # as enum_dealloc lets go of them: en_sit, en_result, the index

    def __new__(cls, *args: object, **kwds: object) -> object:   # enumerate_vectorcall
        nargs, names = len(args), list(kwds)
        total = nargs + len(names)

        def invalid(name: str) -> TypeError:
            return TypeError("'" + name + "' is an invalid keyword argument for enumerate()")

        start: object = 0
        if total == 2:
            if len(names) == 1:
                if names[0] != "start":
                    raise invalid(names[0])
            elif len(names) == 2:
                if names[0] == "start":
                    if names[1] != "iterable":
                        raise invalid(names[1])
                else:
                    if names[0] != "iterable":
                        raise invalid(names[0])
                    if names[1] != "start":
                        raise invalid(names[1])
            start = args[1] if nargs == 2 else kwds["start"]
        elif total == 1:
            if names and names[0] != "iterable":
                raise invalid(names[0])
        elif nargs == 0:
            raise TypeError("enumerate() missing required argument 'iterable'")
        else:
            raise TypeError("enumerate() takes at most 2 arguments (" + str(total) + " given)")
        iterable = args[0] if nargs else kwds["iterable"]
        self = _bella_new_instance(cls)
        self._count = _number_index(start)
        self._it = iter(iterable)  # type: ignore[call-overload]
        self._result = tuple([None, None])       # en_result: its own, to be used again; a constant could not be
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        item = next(self._it)
        count = self._count
        self._count = count + 1
        if _held_once(self, "_result"):          # enum_next: the pair it gave last, when nothing else holds it. The item it
            result = self._result                # gave stays alive in it until the next one, or the iterator, goes (RL-551)
            _tuple_set(result, 0, count)
            _tuple_set(result, 1, item)
            return result
        return (count, item)

    def __reduce__(self, *args: object, **kwds: object) -> object:   # enum_reduce: the iterator it holds, and the count it stands at
        _no_arguments("enumerate.__reduce__", args, kwds)
        return (type(self), (self._it, self._count))


def _strict_argument(kwds: dict[str, object], name: str) -> bool:
    if len(kwds) > 1:
        raise TypeError(name + "() takes at most 1 keyword argument (" + str(len(kwds)) + " given)")
    for key in kwds:
        if key != "strict":
            raise TypeError(name + "() got an unexpected keyword argument '" + key + "'")
    return bool(kwds["strict"]) if kwds else False


def _shorter_or_longer(name: str, what: str, i: int) -> ValueError:
    plural = " " if i == 1 else "s 1-"
    return ValueError(name + "() argument " + str(i + 1) + " is " + what + " than argument" + plural + str(i))


def _check_strict(name: str, its: tuple[object, ...], i: int) -> None:
    """zip_next's and map_next's `check`, for the iterator at i having stopped."""
    if i:
        raise _shorter_or_longer(name, "shorter", i)
    for k in range(1, len(its)):
        try:
            next(its[k])  # type: ignore[call-overload]
        except StopIteration:
            continue
        raise _shorter_or_longer(name, "longer", k)


class zip:
    """The zip object yields n-length tuples, where n is the number of iterables
passed as positional arguments to zip().  The i-th element in every tuple
comes from the i-th iterable argument to zip().  This continues until the
shortest argument is exhausted.

If strict is true and one of the arguments is exhausted before the others,
raise a ValueError.

   >>> list(zip('abcdefg', range(3), range(4)))
   [('a', 0, 'b'), ('b', 1, 'c'), ('c', 2, 'd')]"""

    __slots__ = ("_its", "_result", "_strict")   # as zip_dealloc lets go of them: ittuple, result

    def __new__(cls, *args: object, **kwds: object) -> object:   # zip_new
        strict = _strict_argument(kwds, "zip")
        its = [iter(a) for a in args]  # type: ignore[call-overload]
        self = _bella_new_instance(cls)
        self._its = tuple(its)
        self._result = tuple([None for _ in its])    # its own tuple, to be used again
        self._strict = strict
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:                # zip_next
        its = self._its
        if not its:
            raise StopIteration
        # zip_next: the tuple it gave last when nothing else holds it, each place given its new item as the item comes
        # (the old one is let go of then, before the next iterator is asked); a tuple of its own otherwise
        again = _held_once(self, "_result")
        recycled: object = self._result if again else None
        fresh: list[object] = []
        i = 0
        for it in its:
            ended = False
            try:
                item = next(it)
            except StopIteration:
                if not self._strict:
                    raise                        # the iterator's own StopIteration, as its tp_iternext left it
                ended = True                     # check: it is cleared, and what follows is not raised while handling it (RL-473)
            if ended:
                _check_strict("zip", its, i)
                raise StopIteration              # all are exhausted: next()'s own
            if again:
                _tuple_set(recycled, i, item)
            else:
                fresh.append(item)
            del item
            i += 1
        return recycled if again else tuple(fresh)

    def __reduce__(self, *args: object, **kwds: object) -> object:   # zip_reduce: the iterators it holds
        _no_arguments("zip.__reduce__", args, kwds)
        if self._strict:
            return (type(self), self._its, True)
        return (type(self), self._its)

    def __setstate__(self, *args: object, **kwds: object) -> None:   # zip_setstate
        self._strict = bool(_one_argument("zip.__setstate__", args, kwds))


class map:
    """Make an iterator that computes the function using arguments from
each of the iterables.  Stops when the shortest iterable is exhausted.

If strict is true and one of the arguments is exhausted before the others,
raise a ValueError."""

    __slots__ = ("_its", "_func", "_strict")       # map_dealloc's order: the iterators, then the function

    def __new__(cls, *args: object, **kwds: object) -> object:   # map_new
        strict = _strict_argument(kwds, "map")
        if len(args) < 2:
            raise TypeError("map() must have at least two arguments.")
        its = [iter(a) for a in args[1:]]  # type: ignore[call-overload]
        self = _bella_new_instance(cls)
        self._func = args[0]
        self._its = tuple(its)
        self._strict = strict
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:                # map_next
        its = self._its
        items = []
        i = 0
        for it in its:
            ended = False
            try:
                items.append(next(it))
            except StopIteration:
                if not self._strict:
                    raise                        # the iterator's own StopIteration, as its tp_iternext left it
                ended = True                     # check: cleared, as in zip (RL-473)
            if ended:
                _check_strict("map", its, i)
                raise StopIteration
            i += 1
        return self._func(*items)

    def __reduce__(self, *args: object, **kwds: object) -> object:   # map_reduce: the function and the iterators it holds
        _no_arguments("map.__reduce__", args, kwds)
        if self._strict:
            return (type(self), (self._func, *self._its), True)
        return (type(self), (self._func, *self._its))

    def __setstate__(self, *args: object, **kwds: object) -> None:   # map_setstate
        self._strict = bool(_one_argument("map.__setstate__", args, kwds))


class filter:
    """Return an iterator yielding those items of iterable for which function(item)
is true. If function is None, return the items that are true."""

    __slots__ = ("_func", "_it")

    def __new__(cls, *args: object, **kwds: object) -> object:   # filter_new
        if cls is filter and kwds:
            raise TypeError("filter() takes no keyword arguments")
        if len(args) != 2:
            raise TypeError("filter expected 2 arguments, got " + str(len(args)))
        it = iter(args[1])  # type: ignore[call-overload]
        self = _bella_new_instance(cls)
        self._func = args[0]
        self._it = it
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:                # filter_next
        func = self._func
        check_true = func is None or func is bool
        while True:
            item = next(self._it)
            if (item if check_true else func(item)):
                return item
            del item                             # Py_DECREF(item) before the next tp_iternext (RL-782)

    def __reduce__(self, *args: object, **kwds: object) -> object:   # filter_reduce
        _no_arguments("filter.__reduce__", args, kwds)
        return (type(self), (self._func, self._it))


def _min_max(name: str, args: tuple[object, ...], kwds: dict[str, object], smaller: bool) -> object:
    """min_max in Python/bltinmodule.c."""
    if not args:
        raise TypeError(name + " expected at least 1 argument, got 0")
    for key in kwds:
        if key != "key" and key != "default":
            raise TypeError(name + "() got an unexpected keyword argument '" + key + "'")
    positional = len(args) > 1
    if positional and "default" in kwds:
        raise TypeError("Cannot specify a default for " + name + "() with multiple positional arguments")
    keyfunc = kwds.get("key")
    it = iter(args if positional else args[0])   # held here and asked with next(): it goes where the C lets go of it
    best_item: object = None
    best_value: object = None
    have = False
    while True:
        item = next(it, _END)
        if item is _END:
            break
        value = item if keyfunc is None else keyfunc(item)  # type: ignore[operator]
        if not have:
            best_item, best_value, have = item, value, True
        elif (value < best_value) if smaller else (value > best_value):  # type: ignore[operator]
            best_value, best_item = value, item  # Py_DECREF(maxval); Py_DECREF(maxitem)
        del item, value                          # the C holds neither across the next tp_iternext (RL-782)
    if not have:
        if "default" in kwds:
            return kwds["default"]
        raise ValueError(name + "() iterable argument is empty")
    del best_value, it                           # Py_DECREF(maxval); Py_DECREF(it); return maxitem
    return best_item


def min(*args: object, **kwds: object) -> object:
    """min(iterable, *[, default=obj, key=func]) -> value
min(arg1, arg2, *args, *[, key=func]) -> value

With a single iterable argument, return its smallest item. The
default keyword-only argument specifies an object to return if
the provided iterable is empty.
With two or more positional arguments, return the smallest argument."""
    return _min_max("min", args, kwds, True)


def max(*args: object, **kwds: object) -> object:
    """max(iterable, *[, default=obj, key=func]) -> value
max(arg1, arg2, *args, *[, key=func]) -> value

With a single iterable argument, return its biggest item. The
default keyword-only argument specifies an object to return if
the provided iterable is empty.
With two or more positional arguments, return the largest argument."""
    return _min_max("max", args, kwds, False)


_LONG_MAX = 9223372036854775807
_LONG_MIN = -9223372036854775808


def _cs_add(hi: float, lo: float, x: float) -> tuple[float, float]:   # cs_add, Neumaier's improved Kahan-Babuska
    t = hi + x
    if abs(hi) >= abs(x):
        lo += (hi - t) + x
    else:
        lo += (x - t) + hi
    return t, lo


def _cs_to_double(hi: float, lo: float) -> float:   # cs_to_double
    return hi + lo if lo and lo - lo == 0.0 else hi  # finite: the sign of a negative zero and an infinity survive


def sum(*args: object, **kwds: object) -> object:   # builtin_sum_impl
    """Return the sum of a 'start' value (default: 0) plus an iterable of numbers

When the iterable is empty, return the start value.
This function is intended specifically for use with numeric values and
may reject non-numeric types."""
    if len(args) + len(kwds) > 2:
        raise TypeError("sum() takes at most 2 arguments (" + str(len(args) + len(kwds)) + " given)")
    if not args:
        raise TypeError("sum() takes at least 1 positional argument (0 given)")
    for key in kwds:
        if key != "start":
            raise TypeError("sum() got an unexpected keyword argument '" + key + "'")
    if len(args) > 1 and kwds:
        raise TypeError("argument for sum() given by name ('start') and position (2)")
    result = args[1] if len(args) > 1 else kwds.get("start", 0)
    it = _tp_iter(args[0])
    if issubclass(type(result), str):
        raise TypeError("sum() can't sum strings [use ''.join(seq) instead]")
    if issubclass(type(result), bytes):
        raise TypeError("sum() can't sum bytes [use b''.join(seq) instead]")
    if issubclass(type(result), bytearray):
        raise TypeError("sum() can't sum bytearray [use b''.join(seq) instead]")
    # builtin_sum_impl's stages: exact ints in a C long; then floats, compensated, with ints in a C long
    # among them; then complex numbers, compensated in each part, with ints and floats among them; then
    # anything, with plain +. What ends a stage ends it for good.
    if type(result) is int and _LONG_MIN <= result <= _LONG_MAX:
        for item in it:
            if (type(item) is int or type(item) is bool) and _LONG_MIN <= item and item <= _LONG_MAX and (
                    item <= _LONG_MAX - result if result >= 0 else item >= _LONG_MIN - result):
                result = result + int(item)
                del item                         # Py_DECREF(item) before the next tp_iternext, in every stage (RL-782)
                continue
            result = result + item  # type: ignore[operator]
            del item
            break
        else:
            return result
    if type(result) is float:
        hi, lo = result, 0.0
        for item in it:
            if type(item) is float:
                x = item
            elif issubclass(type(item), int) and _LONG_MIN <= int.__index__(item) <= _LONG_MAX:  # type: ignore[arg-type]
                x = float(int.__index__(item))  # type: ignore[arg-type]
            else:
                if lo and lo - lo == 0.0:        # finite: the sign of a negative zero and an infinity survive
                    hi = hi + lo
                result = hi + item  # type: ignore[operator]
                del item
                break
            del item
            t = hi + x                           # cs_add, Neumaier's improved Kahan-Babuska
            if abs(hi) >= abs(x):
                lo += (hi - t) + x
            else:
                lo += (x - t) + hi
            hi = t
        else:
            return hi + lo if lo and lo - lo == 0.0 else hi
    if type(result) is complex:
        re_hi, re_lo = result.real, 0.0
        im_hi, im_lo = result.imag, 0.0
        for item in it:
            if type(item) is complex:
                re_hi, re_lo = _cs_add(re_hi, re_lo, item.real)
                im_hi, im_lo = _cs_add(im_hi, im_lo, item.imag)
            elif issubclass(type(item), int):
                re_hi, re_lo = _cs_add(re_hi, re_lo, float(int.__index__(item)))  # type: ignore[arg-type]
            elif issubclass(type(item), float):
                re_hi, re_lo = _cs_add(re_hi, re_lo, float.__float__(item))  # type: ignore[arg-type]
            else:
                result = complex(_cs_to_double(re_hi, re_lo), _cs_to_double(im_hi, im_lo)) + item  # type: ignore[operator]
                del item
                break
            del item
        else:
            return complex(_cs_to_double(re_hi, re_lo), _cs_to_double(im_hi, im_lo))
    for item in it:
        result = result + item  # type: ignore[operator]
        del item
    return result


def _one_argument(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> object:   # METH_O
    if kwds:
        raise TypeError(name + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError(name + "() takes exactly one argument (" + str(len(args)) + " given)")
    return args[0]


def any(*args: object, **kwds: object) -> bool:
    """Return True if bool(x) is True for any x in the iterable.

If the iterable is empty, return False."""
    it = _tp_iter(_one_argument("any", args, kwds))
    for item in it:
        found = bool(item)                       # PyObject_IsTrue(item); Py_DECREF(item)
        del item
        if found:
            del it                               # Py_DECREF(it); Py_RETURN_TRUE
            return True
    return False


def all(*args: object, **kwds: object) -> bool:
    """Return True if bool(x) is True for all values x in the iterable.

If the iterable is empty, return True."""
    it = _tp_iter(_one_argument("all", args, kwds))
    for item in it:
        found = bool(item)
        del item
        if not found:
            del it
            return False
    return True
