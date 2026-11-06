"""itertools, in Python, from Modules/itertoolsmodule.c line by line (CPython's is built in).

Compiled into the runtime and run at the first import, in a namespace of its own: what a program
sees is the module `fill_itertools` makes from `__all__` (runtime/src/imports.cpp), so that nothing
here but those names is there to be read. pipeline/tests/test_itertools.py compares it with CPython's.

What the C says about when things die is kept, because a finaliser can tell. A slot's name decides
when it is released (a class's slots are released in name order, and the C's deallocs are followed:
hence `_a_`, `_b_`), a value is let go where the C lets it go (`del item`), and the result tuples are
recycled when nothing else holds them, which is what keeps the last items alive until the next step.
An exception is raised outside the `except` that ended the iteration, since the C clears the one it
caught, so that no __context__ shows.
"""

__all__ = ["_grouper", "_tee", "_tee_dataobject", "accumulate", "batched", "chain", "combinations",
           "combinations_with_replacement", "compress", "count", "cycle", "dropwhile", "filterfalse",
           "groupby", "islice", "pairwise", "permutations", "product", "repeat", "starmap", "takewhile",
           "tee", "zip_longest"]

__name__ = "itertools"

try:
    _number_index                                # noqa: B018  # PyNumber_Index, given by the runtime
    _held_once                                   # noqa: B018  # _PyObject_IsUniquelyReferenced of an attribute's value
    _tuple_set                                   # noqa: B018  # PyTuple_SET_ITEM, on a tuple nothing else holds
    _keyword_suggestion                          # noqa: B018  # _Py_CalculateSuggestions
    _bella_new_instance                          # noqa: B018  # tp_alloc: a type's __new__ makes its instance
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_new_instance: Callable[..., Any] = _missing
    _number_index: Callable[..., int] = _missing
    _held_once: Callable[..., bool] = _missing
    _tuple_set: Callable[..., None] = _missing
    _keyword_suggestion: Callable[..., str | None] = _missing

_SSIZE_MAX = 2**63 - 1
_SSIZE_MIN = -(2**63)
_LINKCELLS = 57
_ABSENT = object()


# ---- the argument parsers' messages ----
def _no_keywords(name: str, kwds: dict[str, object]) -> None:    # _PyArg_NoKeywords
    if kwds:
        raise TypeError(name + "() takes no keyword arguments")


def _new_no_keywords(cls: type, own: type, name: str, kwds: dict[str, object]) -> None:
    """The check of a __new__ with positional arguments: a subclass with an __init__ of its own may be
    given keywords (they reach that __init__, and this ignores them)."""
    if (cls is own or cls.__init__ is own.__init__):             # type: ignore[misc]
        _no_keywords(name, kwds)


def _positional(name: str, args: tuple[object, ...], lo: int, hi: int) -> None:  # _PyArg_CheckPositional
    n = len(args)
    if n < lo:
        raise TypeError(name + " expected " + ("" if lo == hi else "at least ") + str(lo) + (" argument" if lo == 1 else " arguments") + ", got " + str(n))
    if n > hi:
        raise TypeError(name + " expected " + ("" if lo == hi else "at most ") + str(hi) + (" argument" if hi == 1 else " arguments") + ", got " + str(n))


def _unpack(name: str, args: tuple[object, ...], kwds: dict[str, object], names: tuple[str, ...], minpos: int, maxpos: int) -> list[object]:
    """_PyArg_UnpackKeywords with no positional-only parameters: the values, or _ABSENT for one not given."""
    nargs = len(args)
    nkw = len(kwds)
    maxargs = len(names)
    if nargs + nkw > maxargs:
        raise TypeError(name + "() takes at most " + str(maxargs) + (" keyword" if nargs == 0 else "") + " argument" + ("" if maxargs == 1 else "s") + " (" + str(nargs + nkw) + " given)")
    if nargs > maxpos:
        if maxpos == 0:
            raise TypeError(name + "() takes no positional arguments")
        raise TypeError(name + "() takes " + ("at most" if minpos < maxpos else "exactly") + " " + str(maxpos) + " positional argument" + ("" if maxpos == 1 else "s") + " (" + str(nargs) + " given)")
    out: list[object] = [*args, *[_ABSENT] * (maxargs - nargs)]
    if nkw:
        i = 0
        while i < nargs:
            if names[i] in kwds:
                raise TypeError("argument for " + name + "() given by name ('" + names[i] + "') and position (" + str(i + 1) + ")")
            i += 1
    left = nkw
    i = nargs
    while i < maxargs:
        if not left and i >= minpos:
            break
        if left and names[i] in kwds:
            out[i] = kwds[names[i]]
            left -= 1
        elif i < minpos:
            raise TypeError(name + "() missing required argument '" + names[i] + "' (pos " + str(i + 1) + ")")
        i += 1
    if left > 0:                                 # error_unexpected_keyword
        for keyword in kwds:
            if keyword not in names:
                suggestion = _keyword_suggestion(names, keyword)
                if suggestion is not None:
                    raise TypeError(name + "() got an unexpected keyword argument '" + keyword + "'. Did you mean '" + suggestion + "'?")  # type: ignore[operator]
                raise TypeError(name + "() got an unexpected keyword argument '" + keyword + "'")
    return out


def _bad_argument(function: str, which: str, expected: str, arg: object) -> TypeError:  # _PyArg_BadArgument
    return TypeError(function + "() " + which + " must be " + expected + ", not " + ("None" if arg is None else type(arg).__name__))


def _room_for(n: int) -> None:
    """PyMem_New or PyTuple_New of n words, which at this size cannot succeed: the list made here would
    be filled before it failed."""
    if n > 2**40:
        raise MemoryError


def _ssize(v: object) -> int:                    # a clinic's Py_ssize_t: _PyNumber_Index, PyLong_AsSsize_t
    i = _number_index(v)
    if not _SSIZE_MIN <= i <= _SSIZE_MAX:
        raise OverflowError("Python int too large to convert to C ssize_t")
    return i


def _as_ssize(v: object) -> int:                 # PyNumber_AsSsize_t(v, PyExc_OverflowError)
    i = _number_index(v)
    if not _SSIZE_MIN <= i <= _SSIZE_MAX:
        raise OverflowError("cannot fit '" + type(v).__name__ + "' into an index-sized integer")
    return i


def _nonnegative(v: object, name: str) -> int:   # a clinic's Py_ssize_t(allow_negative=False)
    i = _ssize(v)
    if i < 0:
        raise ValueError(name + " cannot be negative")
    return i


# ---- batched ----
class batched:
    __slots__ = ("_batch_size", "_it", "_strict")

    def __new__(cls, *args: object, **kwds: object) -> object:
        iterable, n_arg, strict_arg = _unpack("batched", args, kwds, ("iterable", "n", "strict"), 2, 2)
        n = _ssize(n_arg)
        strict = False if strict_arg is _ABSENT else bool(strict_arg)
        if n < 1:
            raise ValueError("n must be at least one")
        it = iter(iterable)  # type: ignore[call-overload]
        self = _bella_new_instance(cls)
        self._batch_size = n
        self._it = it
        self._strict = strict
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        n = self._batch_size
        if n < 0:
            raise StopIteration
        items: list[object] = []
        it = self._it
        i = 0
        ended = False
        try:
            while i < n:
                items.append(next(it))
                i += 1
        except StopIteration:
            ended = True
        except BaseException:
            self._batch_size = -1
            self._it = None
            raise
        if not ended:
            return tuple(items)
        if i == 0:
            self._batch_size = -1
            self._it = None
            raise StopIteration
        if self._strict:
            self._batch_size = -1
            self._it = None
            raise ValueError("batched(): incomplete batch")
        return tuple(items)


# ---- pairwise ----
class pairwise:
    __slots__ = ("_it", "_old", "_result")

    def __new__(cls, *args: object, **kwds: object) -> object:
        _new_no_keywords(cls, pairwise, "pairwise", kwds)
        _positional("pairwise", args, 1, 1)
        it = iter(args[0])  # type: ignore[call-overload]
        self = _bella_new_instance(cls)
        self._it = it
        self._old = _ABSENT
        self._result = tuple([None, None])       # its own, to be recycled: a constant could not be
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        it = self._it
        if it is None:
            raise StopIteration
        old = self._old
        if old is _ABSENT:
            try:
                old = next(it)
            except BaseException:
                self._old = _ABSENT
                self._it = None
                del it
                raise
            self._old = old
            it = self._it
            if it is None:                       # the iterator re-entered this one, and it ended
                self._old = _ABSENT
                raise StopIteration
        try:
            new = next(it)
        except BaseException:
            self._it = None
            self._old = _ABSENT
            del it, old
            raise
        if _held_once(self, "_result"):
            result = self._result
            _tuple_set(result, 0, old)
            _tuple_set(result, 1, new)
        else:
            result = (old, new)
        self._old = new
        return result


# ---- groupby ----
class groupby:
    __slots__ = ("_a_it", "_b_keyfunc", "_c_tgtkey", "_d_currkey", "_e_currvalue", "_f_currgrouper")

    def __new__(cls, *args: object, **kwds: object) -> object:
        iterable, key = _unpack("groupby", args, kwds, ("iterable", "key"), 1, 2)
        self = _bella_new_instance(cls)
        self._c_tgtkey = _ABSENT
        self._d_currkey = _ABSENT
        self._e_currvalue = _ABSENT
        self._b_keyfunc = None if key is _ABSENT else key
        self._f_currgrouper = None
        self._a_it = iter(iterable)  # type: ignore[call-overload]
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        self._f_currgrouper = None
        while True:                              # skip to next iteration group
            if self._d_currkey is _ABSENT:
                pass
            elif self._c_tgtkey is _ABSENT:
                break
            else:
                tgtkey = self._c_tgtkey
                currkey = self._d_currkey
                same = tgtkey is currkey or bool(tgtkey == currkey)
                del tgtkey, currkey
                if not same:
                    break
            if not _groupby_step(self):
                raise StopIteration
        self._c_tgtkey = self._d_currkey
        grouper = _grouper_create(self, self._c_tgtkey)
        return (self._d_currkey, grouper)


def _groupby_step(gbo: object) -> bool:          # groupby_step: False at the end of the input
    try:
        newvalue = next(gbo._a_it)  # type: ignore[attr-defined]
    except StopIteration:
        return False
    keyfunc = gbo._b_keyfunc  # type: ignore[attr-defined]
    newkey = newvalue if keyfunc is None else keyfunc(newvalue)
    oldvalue = gbo._e_currvalue  # type: ignore[attr-defined]
    gbo._e_currvalue = newvalue  # type: ignore[attr-defined]
    gbo._d_currkey = newkey  # type: ignore[attr-defined]
    del oldvalue
    return True


def _grouper_create(parent: object, tgtkey: object) -> object:
    self = _bella_new_instance(_grouper)
    self._parent = parent
    self._tgtkey = tgtkey
    parent._f_currgrouper = id(self)  # type: ignore[attr-defined]  # a borrowed pointer in the C: compared, never followed
    return self


class _grouper:
    __slots__ = ("_parent", "_tgtkey")

    def __new__(cls, *args: object, **kwds: object) -> object:
        _new_no_keywords(cls, _grouper, "_grouper", kwds)
        _positional("_grouper", args, 2, 2)
        if not issubclass(type(args[0]), groupby):
            raise _bad_argument("_grouper", "argument 1", "itertools.groupby", args[0])
        return _grouper_create(args[0], args[1])

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        gbo = self._parent
        if gbo._f_currgrouper != id(self):
            raise StopIteration
        if gbo._e_currvalue is _ABSENT and not _groupby_step(gbo):
            raise StopIteration
        tgtkey = self._tgtkey
        currkey = gbo._d_currkey
        same = tgtkey is currkey or bool(tgtkey == currkey)
        del tgtkey, currkey
        if not same:                             # the current group has ended
            raise StopIteration
        r = gbo._e_currvalue
        gbo._e_currvalue = _ABSENT
        gbo._d_currkey = _ABSENT
        return r


# ---- tee ----
class _tee_dataobject:
    __slots__ = ("_a_it", "_b_values", "_c_nextlink", "_numread", "_running")

    def __new__(cls, *args: object, **kwds: object) -> object:
        _new_no_keywords(cls, _tee_dataobject, "teedataobject", kwds)
        _positional("teedataobject", args, 3, 3)
        it, values, nextlink = args
        if not issubclass(type(values), list):
            raise _bad_argument("teedataobject", "argument 2", "list", values)
        self = _new_data(it)
        n = len(values)  # type: ignore[arg-type]
        if n > _LINKCELLS:
            raise ValueError("Invalid arguments")
        self._b_values = list(values)  # type: ignore[call-overload]
        self._numread = n
        if n == _LINKCELLS:
            if nextlink is not None:
                if type(nextlink) is not _tee_dataobject:
                    raise ValueError("Invalid arguments")
                self._c_nextlink = nextlink
        elif nextlink is not None:               # shouldn't have a next if we are not full
            raise ValueError("Invalid arguments")
        return self

    def __del__(self) -> None:
        # teedataobject_clear: the iterator, the values in order, and the links, a long chain walked and
        # not recursed (teedataobject_safe_decref)
        self._a_it = None
        values = self._b_values
        i = 0
        while i < len(values):
            values[i] = None
            i += 1
        current = self
        while current._c_nextlink is not None and _held_once(current, "_c_nextlink"):
            link = current._c_nextlink
            current._c_nextlink = None
            current = link


def _data_getitem(data: object, i: int) -> object:    # teedataobject_getitem_lock_held
    if i < data._numread:  # type: ignore[attr-defined]
        return data._b_values[i]  # type: ignore[attr-defined]
    if data._running:  # type: ignore[attr-defined]   # this is the lead iterator, so fetch more data
        raise RuntimeError("cannot re-enter the tee iterator")
    data._running = True  # type: ignore[attr-defined]
    ended = False
    try:
        value = next(data._a_it)  # type: ignore[attr-defined]
    except StopIteration:
        ended = True
    finally:
        data._running = False  # type: ignore[attr-defined]
    if ended:
        raise StopIteration
    data._numread += 1  # type: ignore[attr-defined]
    data._b_values.append(value)  # type: ignore[attr-defined]
    return value


def _new_data(it: object) -> object:             # teedataobject_newinternal
    self = _bella_new_instance(_tee_dataobject)
    self._running = False
    self._numread = 0
    self._c_nextlink = None
    self._a_it = it
    self._b_values = []
    return self


class _tee:
    __slots__ = ("_dataobj", "_index")

    def __new__(cls, *args: object, **kwds: object) -> object:
        _new_no_keywords(cls, _tee, "_tee", kwds)
        _positional("_tee", args, 1, 1)
        return _tee_from_iterable(args[0])

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        if self._index >= _LINKCELLS:
            data = self._dataobj
            if data._c_nextlink is None:
                data._c_nextlink = _new_data(data._a_it)
            link = data._c_nextlink
            del data
            self._dataobj = link
            self._index = 0
        value = _data_getitem(self._dataobj, self._index)
        self._index += 1
        return value

    def __copy__(self, *args: object, **kwds: object) -> object:
        if kwds:
            raise TypeError("_tee.__copy__() takes no keyword arguments")
        if args:
            raise TypeError("_tee.__copy__() takes no arguments (" + str(len(args)) + " given)")
        new = _bella_new_instance(type(self))
        new._dataobj = self._dataobj
        new._index = self._index
        return new


def _tee_from_iterable(iterable: object) -> object:   # tee_fromiterable
    it = iter(iterable)  # type: ignore[call-overload]
    if issubclass(type(it), _tee):
        return _tee.__copy__(it)
    new = _bella_new_instance(_tee)
    new._dataobj = _new_data(it)
    new._index = 0
    return new


def tee(*args: object, **kwds: object) -> tuple[object, ...]:
    """Returns a tuple of n independent iterators."""
    if kwds:
        raise TypeError("itertools.tee() takes no keyword arguments")
    _positional("tee", args, 1, 2)
    n = _nonnegative(args[1], "n") if len(args) > 1 else 2
    _room_for(n)
    if n == 0:
        return ()
    it = iter(args[0])  # type: ignore[call-overload]
    to = _tee_from_iterable(it)
    del it
    result = [to]
    i = 1
    while i < n:
        to = _tee.__copy__(to)
        result.append(to)
        i += 1
    return tuple(result)


# ---- cycle ----
class cycle:
    __slots__ = ("_index", "_it", "_saved")

    def __new__(cls, *args: object, **kwds: object) -> object:
        _new_no_keywords(cls, cycle, "cycle", kwds)
        _positional("cycle", args, 1, 1)
        it = iter(args[0])  # type: ignore[call-overload]
        self = _bella_new_instance(cls)
        self._it = it
        self._saved = []
        self._index = -1
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        index = self._index
        if index < 0:
            try:
                item = next(self._it)
            except StopIteration:
                index = -2
            if index != -2:
                self._saved.append(item)
                return item
            index = 0
            self._index = 0
            self._it = None
        saved = self._saved
        if not saved:
            raise StopIteration
        item = saved[index]
        index += 1
        self._index = 0 if index >= len(saved) else index
        return item


# ---- dropwhile, takewhile, starmap, filterfalse, compress ----
class dropwhile:
    __slots__ = ("_func", "_it", "_start")

    def __new__(cls, *args: object, **kwds: object) -> object:
        _new_no_keywords(cls, dropwhile, "dropwhile", kwds)
        _positional("dropwhile", args, 2, 2)
        it = iter(args[1])  # type: ignore[call-overload]
        self = _bella_new_instance(cls)
        self._func = args[0]
        self._it = it
        self._start = False
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        it = self._it
        while True:
            item = next(it)
            if self._start:
                return item
            if not self._func(item):
                self._start = True
                return item
            del item


class takewhile:
    __slots__ = ("_func", "_it", "_stop")

    def __new__(cls, *args: object, **kwds: object) -> object:
        _new_no_keywords(cls, takewhile, "takewhile", kwds)
        _positional("takewhile", args, 2, 2)
        it = iter(args[1])  # type: ignore[call-overload]
        self = _bella_new_instance(cls)
        self._func = args[0]
        self._it = it
        self._stop = False
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        if self._stop:
            raise StopIteration
        item = next(self._it)
        if self._func(item):
            return item
        del item
        self._stop = True
        raise StopIteration


class starmap:
    __slots__ = ("_func", "_it")

    def __new__(cls, *args: object, **kwds: object) -> object:
        _new_no_keywords(cls, starmap, "starmap", kwds)
        _positional("starmap", args, 2, 2)
        it = iter(args[1])  # type: ignore[call-overload]
        self = _bella_new_instance(cls)
        self._func = args[0]
        self._it = it
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        args = next(self._it)
        if type(args) is not tuple:
            args = tuple(args)                   # PySequence_Tuple
        return self._func(*args)


class filterfalse:
    __slots__ = ("_func", "_it")

    def __new__(cls, *args: object, **kwds: object) -> object:
        _new_no_keywords(cls, filterfalse, "filterfalse", kwds)
        _positional("filterfalse", args, 2, 2)
        it = iter(args[1])  # type: ignore[call-overload]
        self = _bella_new_instance(cls)
        self._func = args[0]
        self._it = it
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        it = self._it
        func = self._func
        plain = func is None or func is bool
        while True:
            item = next(it)
            if not (item if plain else func(item)):
                return item
            del item


class compress:
    __slots__ = ("_data", "_selectors")

    def __new__(cls, *args: object, **kwds: object) -> object:
        data, selectors = _unpack("compress", args, kwds, ("data", "selectors"), 2, 2)
        data_it = iter(data)  # type: ignore[call-overload]
        selectors_it = iter(selectors)  # type: ignore[call-overload]
        self = _bella_new_instance(cls)
        self._data = data_it
        self._selectors = selectors_it
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        data = self._data
        selectors = self._selectors
        while True:                              # the datum, the selector, and then its truth
            datum = next(data)
            if next(selectors):
                return datum
            del datum


# ---- islice ----
class islice:
    __slots__ = ("_cnt", "_it", "_next", "_step", "_stop")

    def __new__(cls, *args: object, **kwds: object) -> object:
        _new_no_keywords(cls, islice, "islice", kwds)
        _positional("islice", args, 2, 4)
        seq = args[0]
        start = 0
        stop = -1
        step = 1
        bad_stop = "Stop argument for islice() must be None or an integer: 0 <= x <= sys.maxsize."
        if len(args) == 2:
            if args[1] is not None:
                try:
                    stop = _as_ssize(args[1])
                except BaseException:
                    stop = -1
                if stop == -1:
                    raise ValueError(bad_stop)
        else:
            if args[1] is not None:
                try:
                    start = _as_ssize(args[1])
                except BaseException:
                    start = -1
            if args[2] is not None:
                try:
                    stop = _as_ssize(args[2])
                except BaseException:
                    stop = -1
                if stop == -1:
                    raise ValueError(bad_stop)
        if start < 0 or stop < -1:
            raise ValueError("Indices for islice() must be None or an integer: 0 <= x <= sys.maxsize.")
        if len(args) == 4 and args[3] is not None:
            try:
                step = _as_ssize(args[3])
            except BaseException:
                step = -1
        if step < 1:
            raise ValueError("Step for islice() must be a positive integer or None.")
        it = iter(seq)  # type: ignore[call-overload]
        self = _bella_new_instance(cls)
        self._it = it
        self._next = start
        self._stop = stop
        self._step = step
        self._cnt = 0
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        if self._it is None:
            raise StopIteration
        stop = self._stop
        try:
            while self._cnt < self._next:
                next(self._it)
                self._cnt += 1
            if stop != -1 and self._cnt >= stop:
                raise StopIteration
            item = next(self._it)
        except BaseException:
            self._it = None                      # empty: the iterator goes, whatever ended it
            raise
        self._cnt += 1
        following = self._next + self._step      # on overflow the C's next is smaller than the old one
        self._next = stop if following > _SSIZE_MAX or (stop != -1 and following > stop) else following
        return item


# ---- chain ----
class chain:
    __slots__ = ("_active", "_source")

    def __new__(cls, *args: object, **kwds: object) -> object:
        _new_no_keywords(cls, chain, "chain", kwds)
        return _chain_new(cls, iter(args))

    @classmethod
    def from_iterable(cls, *args: object, **kwds: object) -> object:
        if kwds:
            raise TypeError("chain.from_iterable() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("chain.from_iterable() takes exactly one argument (" + str(len(args)) + " given)")
        return _chain_new(cls, iter(args[0]))  # type: ignore[call-overload]

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        while self._source is not None:
            if self._active is None:
                try:
                    iterable = next(self._source)
                except StopIteration:
                    iterable = _ABSENT
                except BaseException:
                    self._source = None
                    raise
                if iterable is _ABSENT:
                    self._source = None          # no more input sources
                    break
                try:
                    self._active = iter(iterable)  # type: ignore[call-overload]
                except BaseException:
                    self._source = None          # input not iterable
                    raise
                del iterable
            try:
                return next(self._active)
            except StopIteration:
                pass
            self._active = None                  # consumed: try with the next iterable
        raise StopIteration


def _chain_new(cls: type, source: object) -> object:   # chain_new_internal
    self = _bella_new_instance(cls)
    self._source = source
    self._active = None
    return self


# ---- product, combinations, combinations_with_replacement, permutations ----
class product:
    __slots__ = ("_indices", "_pools", "_result", "_stopped")

    def __new__(cls, *args: object, **kwds: object) -> object:
        repeat = 1
        if kwds:
            given = _unpack("product", (), kwds, ("repeat",), 0, 1)[0]
            if given is not _ABSENT:
                repeat = _ssize(given)
            if repeat < 0:
                raise ValueError("repeat argument cannot be negative")
        nargs = 0 if repeat == 0 else len(args)
        if nargs > _SSIZE_MAX // 8 // (repeat or 1):
            raise OverflowError("repeat argument too large")
        _room_for(nargs * repeat)
        pools = [tuple(a) for a in args[:nargs]]  # type: ignore[call-overload]
        self = _bella_new_instance(cls)
        self._pools = tuple(pools) * repeat if nargs else ()
        self._indices = [0] * len(self._pools)
        self._result = None
        self._stopped = False
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        if self._stopped:
            raise StopIteration
        pools = self._pools
        npools = len(pools)
        if self._result is None:
            for pool in pools:
                if not pool:
                    self._stopped = True
                    raise StopIteration
            self._result = tuple([pool[0] for pool in pools])
            return self._result
        if not _held_once(self, "_result"):
            self._result = tuple([*self._result])     # a copy: the other is someone else's
        result = self._result
        indices = self._indices
        i = npools - 1
        while i >= 0:                            # right to left; on to the next pool when one rolls over
            pool = pools[i]
            indices[i] += 1
            if indices[i] == len(pool):
                indices[i] = 0
                _tuple_set(result, i, pool[0])
            else:
                _tuple_set(result, i, pool[indices[i]])
                break
            i -= 1
        if i < 0:
            self._stopped = True
            raise StopIteration
        return result


class combinations:
    __slots__ = ("_indices", "_pool", "_r", "_result", "_stopped")

    def __new__(cls, *args: object, **kwds: object) -> object:
        iterable, r_arg = _unpack("combinations", args, kwds, ("iterable", "r"), 2, 2)
        r = _nonnegative(r_arg, "r")
        pool = tuple(iterable)  # type: ignore[call-overload]
        _room_for(r)
        self = _bella_new_instance(cls)
        self._pool = pool
        self._indices = list(range(r))
        self._result = None
        self._r = r
        self._stopped = r > len(pool)
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        if self._stopped:
            raise StopIteration
        pool = self._pool
        indices = self._indices
        n = len(pool)
        r = self._r
        if self._result is None:
            self._result = tuple([pool[i] for i in indices])
            return self._result
        if not _held_once(self, "_result"):
            self._result = tuple([*self._result])
        result = self._result
        i = r - 1
        while i >= 0 and indices[i] == i + n - r:     # the rightmost index not at its maximum
            i -= 1
        if i < 0:
            self._stopped = True
            raise StopIteration
        indices[i] += 1
        j = i + 1
        while j < r:
            indices[j] = indices[j - 1] + 1
            j += 1
        while i < r:
            _tuple_set(result, i, pool[indices[i]])
            i += 1
        return result


class combinations_with_replacement:
    __slots__ = ("_indices", "_pool", "_r", "_result", "_stopped")

    def __new__(cls, *args: object, **kwds: object) -> object:
        iterable, r_arg = _unpack("combinations_with_replacement", args, kwds, ("iterable", "r"), 2, 2)
        r = _nonnegative(r_arg, "r")
        pool = tuple(iterable)  # type: ignore[call-overload]
        _room_for(r)
        self = _bella_new_instance(cls)
        self._pool = pool
        self._indices = [0] * r
        self._result = None
        self._r = r
        self._stopped = not pool and r != 0
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        if self._stopped:
            raise StopIteration
        pool = self._pool
        indices = self._indices
        n = len(pool)
        r = self._r
        if self._result is None:
            self._result = (pool[0],) * r if n > 0 else ()
            return self._result
        if not _held_once(self, "_result"):
            self._result = tuple([*self._result])
        result = self._result
        i = r - 1
        while i >= 0 and indices[i] == n - 1:
            i -= 1
        if i < 0:
            self._stopped = True
            raise StopIteration
        index = indices[i] + 1
        elem = pool[index]
        while i < r:
            indices[i] = index
            _tuple_set(result, i, elem)
            i += 1
        return result


class permutations:
    __slots__ = ("_cycles", "_indices", "_pool", "_r", "_result", "_stopped")

    def __new__(cls, *args: object, **kwds: object) -> object:
        iterable, r_arg = _unpack("permutations", args, kwds, ("iterable", "r"), 1, 2)
        pool = tuple(iterable)  # type: ignore[call-overload]
        n = len(pool)
        r = n
        if r_arg is not _ABSENT and r_arg is not None:
            if not issubclass(type(r_arg), int):
                raise TypeError("Expected int as r")
            r = int.__index__(r_arg)  # type: ignore[arg-type]
            if not _SSIZE_MIN <= r <= _SSIZE_MAX:
                raise OverflowError("Python int too large to convert to C ssize_t")
        if r < 0:
            raise ValueError("r must be non-negative")
        _room_for(r)
        self = _bella_new_instance(cls)
        self._pool = pool
        self._indices = list(range(n))
        self._cycles = [n - i for i in range(r)]
        self._result = None
        self._r = r
        self._stopped = r > n
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        if self._stopped:
            raise StopIteration
        pool = self._pool
        indices = self._indices
        cycles = self._cycles
        n = len(pool)
        r = self._r
        if self._result is None:
            self._result = tuple([pool[indices[i]] for i in range(r)])
            return self._result
        if n == 0:
            self._stopped = True
            raise StopIteration
        if not _held_once(self, "_result"):
            self._result = tuple([*self._result])
        result = self._result
        i = r - 1
        while i >= 0:                            # the rightmost cycle down, leftward on a rollover
            cycles[i] -= 1
            if cycles[i] == 0:
                index = indices[i]               # indices[i:] = indices[i+1:] + indices[i:i+1]
                j = i
                while j < n - 1:
                    indices[j] = indices[j + 1]
                    j += 1
                indices[n - 1] = index
                cycles[i] = n - i
            else:
                j = cycles[i]
                index = indices[i]
                indices[i] = indices[n - j]
                indices[n - j] = index
                k = i
                while k < r:
                    _tuple_set(result, k, pool[indices[k]])
                    k += 1
                break
            i -= 1
        if i < 0:
            self._stopped = True
            raise StopIteration
        return result


# ---- accumulate ----
class accumulate:
    __slots__ = ("_a_binop", "_b_total", "_c_it", "_d_initial")

    def __new__(cls, *args: object, **kwds: object) -> object:
        iterable, binop, initial = _unpack("accumulate", args, kwds, ("iterable", "func", "initial"), 1, 2)
        it = iter(iterable)  # type: ignore[call-overload]
        self = _bella_new_instance(cls)
        self._a_binop = None if binop is _ABSENT else binop
        self._b_total = _ABSENT
        self._c_it = it
        self._d_initial = None if initial is _ABSENT else initial
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        if self._d_initial is not None:
            self._b_total = self._d_initial
            self._d_initial = None
            return self._b_total
        val = next(self._c_it)
        if self._b_total is _ABSENT:
            self._b_total = val
            return val
        newtotal = self._b_total + val if self._a_binop is None else self._a_binop(self._b_total, val)
        del val
        self._b_total = newtotal
        return newtotal


# ---- count, repeat ----
class count:
    __slots__ = ("_cnt", "_long_cnt", "_long_step")

    def __new__(cls, *args: object, **kwds: object) -> object:
        long_cnt, long_step = _unpack("count", args, kwds, ("start", "step"), 0, 2)
        if (long_cnt is not _ABSENT and not _is_number(long_cnt)) or (long_step is not _ABSENT and not _is_number(long_step)):
            raise TypeError("a number is required")
        fast_mode = (long_cnt is _ABSENT or issubclass(type(long_cnt), int)) and (long_step is _ABSENT or issubclass(type(long_step), int))
        cnt = 0
        if long_cnt is _ABSENT:
            long_cnt = 0
        elif fast_mode:
            cnt = int.__index__(long_cnt)  # type: ignore[arg-type]
            if not _SSIZE_MIN <= cnt <= _SSIZE_MAX:
                fast_mode = False
        if long_step is _ABSENT:
            long_step = 1
        if fast_mode and int.__index__(long_step) != 1:  # type: ignore[arg-type]  # only with a step of 1
            fast_mode = False
        if fast_mode:
            long_cnt = None
        else:
            cnt = _SSIZE_MAX
        self = _bella_new_instance(cls)
        self._cnt = cnt
        self._long_cnt = long_cnt
        self._long_step = long_step
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        if self._cnt != _SSIZE_MAX:
            value = self._cnt
            self._cnt = value + 1
            return value
        if self._long_cnt is None:               # on to the slow mode
            self._long_cnt = _SSIZE_MAX
        result = self._long_cnt
        self._long_cnt = result + self._long_step
        return result

    def __repr__(self) -> str:
        name = type(self).__name__
        if self._long_cnt is None:
            return name + "(" + str(self._cnt) + ")"
        step = self._long_step
        if issubclass(type(step), int) and int.__index__(step) == 1:
            return name + "(" + repr(self._long_cnt) + ")"
        return name + "(" + repr(self._long_cnt) + ", " + repr(step) + ")"


def _is_number(v: object) -> bool:               # PyNumber_Check; the runtime has no complex object yet
    for special in ("__index__", "__int__", "__float__"):
        for c in type(v).__mro__:
            if special in vars(c):
                return True
    return False


class repeat:
    __slots__ = ("_cnt", "_element")

    def __new__(cls, *args: object, **kwds: object) -> object:
        element, times = _unpack("repeat", args, kwds, ("object", "times"), 1, 2)
        cnt = -1
        if times is not _ABSENT:
            cnt = _ssize(times)
            if cnt < 0:                          # the times argument given: never endless
                cnt = 0
        self = _bella_new_instance(cls)
        self._element = element
        self._cnt = cnt
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        cnt = self._cnt
        if cnt == 0:
            raise StopIteration
        if cnt > 0:
            self._cnt = cnt - 1
        return self._element

    def __repr__(self) -> str:
        name = type(self).__name__
        if self._cnt == -1:
            return name + "(" + repr(self._element) + ")"
        return name + "(" + repr(self._element) + ", " + str(self._cnt) + ")"

    def __length_hint__(self, *args: object, **kwds: object) -> int:
        if kwds:
            raise TypeError("repeat.__length_hint__() takes no keyword arguments")
        if args:
            raise TypeError("repeat.__length_hint__() takes no arguments (" + str(len(args)) + " given)")
        if self._cnt == -1:
            raise TypeError("len() of unsized object")
        return self._cnt


# ---- zip_longest ----
class zip_longest:
    __slots__ = ("_a_ittuple", "_b_result", "_c_fillvalue", "_numactive", "_tuplesize")

    def __new__(cls, *args: object, **kwds: object) -> object:
        fillvalue = None
        if kwds:
            if len(kwds) != 1 or "fillvalue" not in kwds:
                raise TypeError("zip_longest() got an unexpected keyword argument")
            fillvalue = kwds["fillvalue"]
        its = [iter(a) for a in args]  # type: ignore[call-overload]
        self = _bella_new_instance(cls)
        self._a_ittuple = its                    # a tuple in the C, whose slots it empties
        self._tuplesize = len(args)
        self._numactive = len(args)
        self._b_result = tuple([None] * len(args))    # its own, to be recycled: a constant could not be
        self._c_fillvalue = fillvalue
        return self

    def __iter__(self) -> object:
        return self

    def __next__(self) -> object:
        tuplesize = self._tuplesize
        if tuplesize == 0 or self._numactive == 0:
            raise StopIteration
        recycled = _held_once(self, "_b_result")
        result = self._b_result if recycled else tuple([None] * tuplesize)
        its = self._a_ittuple
        i = 0
        while i < tuplesize:
            it = its[i]
            if it is None:
                item = self._c_fillvalue
            else:
                ended = False
                try:
                    item = next(it)
                except StopIteration:
                    ended = True
                except BaseException:
                    self._numactive = 0
                    raise
                if ended:
                    self._numactive -= 1
                    if self._numactive == 0:
                        raise StopIteration
                    item = self._c_fillvalue
                    its[i] = None
            del it
            _tuple_set(result, i, item)
            del item
            i += 1
        return result
