"""_collections, in Python, from Modules/_collectionsmodule.c; see itertools.py beside it.

A deque is a list, kept right to left: its leftmost item is at the end of the list, so that a list's death, which
releases its items last to first, releases a deque's left to right as deque_clear does. The cells below `_b_start`
are free, for appends on the right. `_d_state` counts what the C's `state` counts, since an iterator is told apart
from a mutation by it. The C has no number slots here, only sequence ones: `d + x` asks `x.__radd__` before the
deque's `__add__`, which the runtime knows from `ClassObject::sequence_slots`.
"""

__all__ = ["OrderedDict", "_count_elements", "_deque_iterator", "_deque_reverse_iterator", "_tuplegetter", "defaultdict", "deque"]

__name__ = "_collections"

try:
    _number_index                                # noqa: B018  # PyNumber_Index, given by the runtime
    _tp_name                                     # noqa: B018  # Py_TYPE(obj)->tp_name
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _count_element                               # noqa: B018  # _count_elements' fast path: one hash for each key
    _repr_enter                                  # noqa: B018  # Py_ReprEnter: false when it is in there already
    _repr_leave                                  # noqa: B018  # Py_ReprLeave
    _bella_new_instance                          # noqa: B018  # tp_alloc: a type's __new__ makes its instance
except NameError:
    from collections.abc import Callable
    from typing import Any, NoReturn

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_new_instance: Callable[..., Any] = _missing
    _number_index: Callable[..., int] = _missing
    _tp_name: Callable[..., str] = _missing
    _count_element: Callable[..., None] = _missing
    _repr_enter: Callable[..., bool] = _missing
    _repr_leave: Callable[..., None] = _missing

    def _bella_refuse(text: str) -> NoReturn:
        raise ImportError(text)

_SSIZE_MAX = 2**63 - 1
_SSIZE_MIN = -(2**63)
_MUTATED = "deque mutated during iteration"


def _ssize(value: object, error: type = OverflowError) -> int:   # PyNumber_AsSsize_t(value, error)
    index = _number_index(value)
    if not _SSIZE_MIN <= index <= _SSIZE_MAX:
        raise error("cannot fit '" + _tp_name(value) + "' into an index-sized integer")
    return index


def _clinic_ssize(value: object) -> int:         # the clinic's Py_ssize_t: PyNumber_Index, PyLong_AsSsize_t
    index = _number_index(value)
    if not _SSIZE_MIN <= index <= _SSIZE_MAX:
        raise OverflowError("Python int too large to convert to C ssize_t")
    return index


def _slice_index(value: object) -> int:          # _PyEval_SliceIndexNotNone: clipped
    if not hasattr(type(value), "__index__"):
        raise TypeError("slice indices must be integers or have an __index__ method")
    index = _number_index(value)
    return max(min(index, _SSIZE_MAX), _SSIZE_MIN)


def _same(x: object, y: object) -> bool:         # PyObject_RichCompareBool(x, y, Py_EQ)
    return x is y or bool(x == y)


def _new_receiver(args: tuple[object, ...], owner: type, shown: str) -> None:   # tp_new_wrapper's checks
    if not args:
        raise TypeError(shown + ".__new__(): not enough arguments")
    cls = args[0]
    if not issubclass(type(cls), type):
        raise TypeError(shown + ".__new__(X): X is not a type object (" + _tp_name(cls) + ")")
    if not issubclass(cls, owner):  # type: ignore[arg-type]
        raise TypeError(shown + ".__new__(" + cls.__name__ + "): " + cls.__name__ + " is not a subtype of " + shown)  # type: ignore[attr-defined]


def _receiver(args: tuple[object, ...], cls: type, name: str, shown: str) -> None:   # a method descriptor's
    if not args:
        raise TypeError("unbound method " + shown + "." + name + "() needs an argument")
    if not issubclass(type(args[0]), cls):
        raise TypeError("descriptor '" + name + "' for '" + cls.__module__ + "." + cls.__name__ + "' objects doesn't apply to a '" + _tp_name(args[0]) + "' object")


def _noargs(args: tuple[object, ...], kwds: dict[str, object], cls: type, name: str, shown: str) -> None:   # METH_NOARGS
    _receiver(args, cls, name, shown)
    if kwds:
        raise TypeError(shown + "." + name + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError(shown + "." + name + "() takes no arguments (" + str(len(args) - 1) + " given)")


def _one(args: tuple[object, ...], kwds: dict[str, object], cls: type, name: str, shown: str) -> object:   # METH_O
    _receiver(args, cls, name, shown)
    if kwds:
        raise TypeError(shown + "." + name + "() takes no keyword arguments")
    if len(args) != 2:
        raise TypeError(shown + "." + name + "() takes exactly one argument (" + str(len(args) - 1) + " given)")
    return args[1]


def _wrapper(args: tuple[object, ...], kwds: dict[str, object], cls: type, name: str, count: int) -> None:   # wrapper_call, check_num_args
    if not args:
        raise TypeError("descriptor '" + name + "' of '" + cls.__module__ + "." + cls.__name__ + "' object needs an argument")
    if not issubclass(type(args[0]), cls):
        raise TypeError("descriptor '" + name + "' requires a '" + cls.__module__ + "." + cls.__name__ + "' object but received a '" + _tp_name(args[0]) + "'")
    if kwds:
        raise TypeError("wrapper " + name + "() takes no keyword arguments")
    if len(args) != count + 1:
        raise TypeError("expected " + str(count) + " argument" + ("" if count == 1 else "s") + ", got " + str(len(args) - 1))


# ---- the deque's own operations, on its list

def _d_size(self: object) -> int:
    return len(self._a_items) - self._b_start  # type: ignore[attr-defined]


def _d_at(self: object, index: int) -> object:   # from the left
    return self._a_items[len(self._a_items) - 1 - index]  # type: ignore[attr-defined]


def _d_right_cell(self: object) -> None:         # one free cell below the items
    if self._b_start == 0:  # type: ignore[attr-defined]
        room = max(8, len(self._a_items))  # type: ignore[attr-defined]
        self._a_items[0:0] = [None] * room  # type: ignore[attr-defined]
        self._b_start = room  # type: ignore[attr-defined]


def _d_popright(self: object) -> object:         # deque_pop_impl
    items, start = self._a_items, self._b_start  # type: ignore[attr-defined]
    if start == len(items):
        raise IndexError("pop from an empty deque")
    item = items[start]
    items[start] = None
    self._b_start = start + 1  # type: ignore[attr-defined]
    if self._b_start > 8 and self._b_start * 2 > len(items):  # type: ignore[attr-defined]
        del items[:self._b_start]  # type: ignore[attr-defined]
        self._b_start = 0  # type: ignore[attr-defined]
    self._d_state += 1  # type: ignore[attr-defined]
    return item


def _d_popleft(self: object) -> object:          # deque_popleft_impl
    items = self._a_items  # type: ignore[attr-defined]
    if self._b_start == len(items):  # type: ignore[attr-defined]
        raise IndexError("pop from an empty deque")
    item = items.pop()
    self._d_state += 1  # type: ignore[attr-defined]
    return item


def _d_append(self: object, item: object) -> None:   # deque_append_lock_held
    _d_right_cell(self)
    self._b_start -= 1  # type: ignore[attr-defined]
    self._a_items[self._b_start] = item  # type: ignore[attr-defined]
    if self._c_maxlen >= 0 and _d_size(self) > self._c_maxlen:  # type: ignore[attr-defined]
        _d_popleft(self)
    else:
        self._d_state += 1  # type: ignore[attr-defined]


def _d_appendleft(self: object, item: object) -> None:   # deque_appendleft_lock_held
    self._a_items.append(item)  # type: ignore[attr-defined]
    if self._c_maxlen >= 0 and _d_size(self) > self._c_maxlen:  # type: ignore[attr-defined]
        _d_popright(self)
    else:
        self._d_state += 1  # type: ignore[attr-defined]


def _d_extend(self: object, iterable: object) -> None:   # deque_extend_impl
    if iterable is self:
        iterable = list(iterable)  # type: ignore[call-overload]
    it = iter(iterable)  # type: ignore[call-overload]
    if self._c_maxlen == 0:  # type: ignore[attr-defined]
        for item in it:                          # consume_iterator
            del item
        return
    for item in it:
        _d_append(self, item)
        del item


def _d_extendleft(self: object, iterable: object) -> None:   # deque_extendleft_impl
    if iterable is self:
        iterable = list(iterable)  # type: ignore[call-overload]
    it = iter(iterable)  # type: ignore[call-overload]
    if self._c_maxlen == 0:  # type: ignore[attr-defined]
        for item in it:
            del item
        return
    for item in it:
        _d_appendleft(self, item)
        del item


def _d_clear(self: object) -> None:              # deque_clear: left to right, on a deque already empty
    old = self._a_items  # type: ignore[attr-defined]
    start = self._b_start  # type: ignore[attr-defined]
    self._a_items = []  # type: ignore[attr-defined]
    self._b_start = 0  # type: ignore[attr-defined]
    self._d_state += 1  # type: ignore[attr-defined]
    while len(old) > start:
        del old[-1]


def _d_rotate(self: object, n: int) -> None:     # _deque_rotate
    size = _d_size(self)
    halflen = size >> 1
    if size <= 1:
        return
    if n > halflen or n < -halflen:
        n = n % size if n >= 0 else -(-n % size)  # C's %: the dividend's sign
        if n > halflen:
            n -= size
        elif n < -halflen:
            n += size
    self._d_state += 1  # type: ignore[attr-defined]
    if n == 0:
        return
    start = self._b_start  # type: ignore[attr-defined]
    items = self._a_items  # type: ignore[attr-defined]
    live = items[start:]
    k = n % size                                 # n to the right is k toward the list's front, which is the right
    items[start:] = live[k:] + live[:k]


def _d_copy(self: object) -> object:             # deque_copy_impl
    if type(self) is deque:
        new = deque()
        new._c_maxlen = self._c_maxlen  # type: ignore[attr-defined]
        for index in range(_d_size(self)):
            _d_append(new, _d_at(self, index))
        return new
    if self._c_maxlen < 0:  # type: ignore[attr-defined]
        result = type(self)(self)  # type: ignore[call-arg]
    else:
        result = type(self)(self, self._c_maxlen)  # type: ignore[call-arg, attr-defined]
    if not issubclass(type(result), deque):
        raise TypeError(_tp_name(self) + "() must return a deque, not " + _tp_name(result))
    return result


def _d_delete(self: object, index: int) -> None:   # deque_del_item
    _d_rotate(self, -index)
    item = _d_popleft(self)
    _d_rotate(self, index)
    del item


def _d_compare(v: object, w: object, op: int) -> object:   # deque_richcompare: 0 < 1 <= 2 == 3 != 4 > 5 >=
    if not issubclass(type(v), deque) or not issubclass(type(w), deque):
        return NotImplemented
    vs, ws = _d_size(v), _d_size(w)
    if op == 2:
        if v is w:
            return True
        if vs != ws:
            return False
    if op == 3:
        if v is w:
            return False
        if vs != ws:
            return True
    it1 = iter(v)  # type: ignore[call-overload]
    it2 = iter(w)  # type: ignore[call-overload]
    absent = _d_compare
    while True:
        x = next(it1, absent)
        y = next(it2, absent)
        if x is absent or y is absent:
            break
        if not _same(x, y):
            if op == 0:
                return bool(x < y)
            if op == 1:
                return bool(x <= y)
            if op == 2:
                return False
            if op == 3:
                return True
            if op == 4:
                return bool(x > y)
            return bool(x >= y)
    if op == 0:
        return y is not absent
    if op == 1:
        return x is absent
    if op == 2:
        return x is absent and y is absent
    if op == 3:
        return not (x is absent and y is absent)
    if op == 4:
        return x is not absent
    return y is absent


class deque:
    __module__ = "collections"
    __slots__ = ("_a_items", "_b_start", "_c_maxlen", "_d_state", "__weakref__")

    def __new__(*args: object, **kwds: object) -> deque:   # deque_new: the arguments are __init__'s
        _new_receiver(args, deque, "collections.deque")
        cls, args = args[0], args[1:]
        self = _bella_new_instance(cls)
        self._a_items = []
        self._b_start = 0
        self._c_maxlen = -1
        self._d_state = 0
        return self

    def __init__(*args: object, **kwds: object) -> None:   # deque_init_impl([iterable[, maxlen]])
        _wrapper(args[:1], {}, deque, "__init__", 0)
        self = args[0]
        rest = args[1:]
        total = len(rest) + len(kwds)
        if total > 2:
            raise TypeError("deque() takes at most 2 " + ("" if rest else "keyword ") + "arguments (" + str(total) + " given)")
        iterable, maxlen = None, None
        given_iterable = False
        if rest:
            iterable = rest[0]
            given_iterable = True
        if len(rest) > 1:
            maxlen = rest[1]
        for key, value in kwds.items():
            if key == "iterable":
                if rest:
                    raise TypeError("argument for deque() given by name ('iterable') and position (1)")
                iterable = value
                given_iterable = True
            elif key == "maxlen":
                if len(rest) > 1:
                    raise TypeError("argument for deque() given by name ('maxlen') and position (2)")
                maxlen = value
            else:
                raise TypeError("deque() got an unexpected keyword argument '" + key + "'")
        bound = -1
        if maxlen is not None:
            if not issubclass(type(maxlen), int):    # PyLong_AsSsize_t, which takes no __index__
                raise TypeError("an integer is required")
            bound = int.__index__(maxlen)
            if not _SSIZE_MIN <= bound <= _SSIZE_MAX:
                raise OverflowError("Python int too large to convert to C ssize_t")
            if bound < 0:
                raise ValueError("maxlen must be non-negative")
        self._c_maxlen = bound  # type: ignore[attr-defined]
        if _d_size(self) > 0:
            _d_clear(self)
        if given_iterable:
            _d_extend(self, iterable)

    def append(*args: object, **kwds: object) -> None:
        item = _one(args, kwds, deque, "append", "deque")
        _d_append(args[0], item)

    def appendleft(*args: object, **kwds: object) -> None:
        item = _one(args, kwds, deque, "appendleft", "deque")
        _d_appendleft(args[0], item)

    def extend(*args: object, **kwds: object) -> None:
        iterable = _one(args, kwds, deque, "extend", "deque")
        _d_extend(args[0], iterable)

    def extendleft(*args: object, **kwds: object) -> None:
        iterable = _one(args, kwds, deque, "extendleft", "deque")
        _d_extendleft(args[0], iterable)

    def pop(*args: object, **kwds: object) -> object:
        _noargs(args, kwds, deque, "pop", "deque")
        return _d_popright(args[0])

    def popleft(*args: object, **kwds: object) -> object:
        _noargs(args, kwds, deque, "popleft", "deque")
        return _d_popleft(args[0])

    def clear(*args: object, **kwds: object) -> None:
        _noargs(args, kwds, deque, "clear", "deque")
        _d_clear(args[0])

    def copy(*args: object, **kwds: object) -> object:
        _noargs(args, kwds, deque, "copy", "deque")
        return _d_copy(args[0])

    def __copy__(*args: object, **kwds: object) -> object:
        _noargs(args, kwds, deque, "__copy__", "deque")
        return _d_copy(args[0])

    def reverse(*args: object, **kwds: object) -> None:   # no state++: an iterator goes on, in what it now finds
        _noargs(args, kwds, deque, "reverse", "deque")
        self = args[0]
        self._a_items[self._b_start:] = self._a_items[self._b_start:][::-1]  # type: ignore[attr-defined]

    def rotate(*args: object, **kwds: object) -> None:
        _receiver(args, deque, "rotate", "deque")
        if kwds:
            raise TypeError("deque.rotate() takes no keyword arguments")
        if len(args) > 2:
            raise TypeError("rotate expected at most 1 argument, got " + str(len(args) - 1))
        _d_rotate(args[0], _clinic_ssize(args[1]) if len(args) == 2 else 1)

    def count(*args: object, **kwds: object) -> int:
        v = _one(args, kwds, deque, "count", "deque")
        self = args[0]
        state = self._d_state  # type: ignore[attr-defined]
        total = 0
        for index in range(_d_size(self)):
            if _same(_d_at(self, index), v):
                total += 1
            if state != self._d_state:  # type: ignore[attr-defined]
                raise RuntimeError(_MUTATED)
        return total

    def index(*args: object, **kwds: object) -> int:   # deque_index_impl(value, [start, [stop]])
        _receiver(args, deque, "index", "deque")
        if kwds:
            raise TypeError("deque.index() takes no keyword arguments")
        count = len(args) - 1
        if count < 1:
            raise TypeError("index expected at least 1 argument, got " + str(count))
        if count > 3:
            raise TypeError("index expected at most 3 arguments, got " + str(count))
        self, v = args[0], args[1]
        size = _d_size(self)
        start = _slice_index(args[2]) if count > 1 else 0
        stop = _slice_index(args[3]) if count > 2 else _SSIZE_MAX
        state = self._d_state  # type: ignore[attr-defined]
        if start < 0:
            start = max(start + size, 0)
        if stop < 0:
            stop = max(stop + size, 0)
        stop = min(stop, size)
        start = min(start, stop)
        for position in range(start, stop):
            if _same(_d_at(self, position), v):
                return position
            if state != self._d_state:  # type: ignore[attr-defined]
                raise RuntimeError(_MUTATED)
        raise ValueError("deque.index(x): x not in deque")

    def insert(*args: object, **kwds: object) -> None:   # deque_insert_impl
        _receiver(args, deque, "insert", "deque")
        if kwds:
            raise TypeError("deque.insert() takes no keyword arguments")
        if len(args) != 3:
            raise TypeError("insert expected 2 arguments, got " + str(len(args) - 1))
        self, value = args[0], args[2]
        index = _clinic_ssize(args[1])
        size = _d_size(self)
        if self._c_maxlen == size:  # type: ignore[attr-defined]
            raise IndexError("deque already at its maximum size")
        if index >= size:
            _d_append(self, value)
            return
        if index <= -size or index == 0:
            _d_appendleft(self, value)
            return
        _d_rotate(self, -index)
        if index < 0:
            _d_append(self, value)
        else:
            _d_appendleft(self, value)
        _d_rotate(self, index)

    def remove(*args: object, **kwds: object) -> None:   # deque_remove_impl
        value = _one(args, kwds, deque, "remove", "deque")
        self = args[0]
        state = self._d_state  # type: ignore[attr-defined]
        size = _d_size(self)
        for index in range(size):
            found = _same(_d_at(self, index), value)
            if state != self._d_state:  # type: ignore[attr-defined]
                raise IndexError(_MUTATED)
            if found:
                _d_delete(self, index)
                return
        raise ValueError("deque.remove(x): x not in deque")

    def __len__(*args: object, **kwds: object) -> int:
        _wrapper(args, kwds, deque, "__len__", 0)
        return _d_size(args[0])

    def __iter__(*args: object, **kwds: object) -> object:
        _wrapper(args, kwds, deque, "__iter__", 0)
        return _make_iterator(_deque_iterator, args[0])

    def __reversed__(*args: object, **kwds: object) -> object:
        _noargs(args, kwds, deque, "__reversed__", "deque")
        return _make_iterator(_deque_reverse_iterator, args[0])

    def __contains__(*args: object, **kwds: object) -> bool:   # deque_contains_lock_held
        _wrapper(args, kwds, deque, "__contains__", 1)
        self, v = args
        state = self._d_state  # type: ignore[attr-defined]
        for index in range(_d_size(self)):
            found = _same(_d_at(self, index), v)
            if found:
                return True
            if state != self._d_state:  # type: ignore[attr-defined]
                raise RuntimeError(_MUTATED)
        return False

    def __getitem__(*args: object, **kwds: object) -> object:   # wrap_sq_item, deque_item
        _wrapper(args, kwds, deque, "__getitem__", 1)
        self = args[0]
        index = _ssize(args[1])
        if index < 0:
            index += len(self)  # type: ignore[arg-type]
        if not 0 <= index < _d_size(self):
            raise IndexError("deque index out of range")
        return _d_at(self, index)

    def __setitem__(*args: object, **kwds: object) -> None:   # wrap_sq_setitem, deque_ass_item
        _wrapper(args[:1], {}, deque, "__setitem__", 0)
        if kwds:
            raise TypeError("wrapper __setitem__() takes no keyword arguments")
        if len(args) != 3:                       # wrap_sq_setitem: PyArg_UnpackTuple
            raise TypeError("__setitem__ expected 2 arguments, got " + str(len(args) - 1))
        self = args[0]
        index = _ssize(args[1])
        if index < 0:
            index += len(self)  # type: ignore[arg-type]
        if not 0 <= index < _d_size(self):
            raise IndexError("deque index out of range")
        self._a_items[len(self._a_items) - 1 - index] = args[2]  # type: ignore[attr-defined]

    def __delitem__(*args: object, **kwds: object) -> None:   # wrap_sq_delitem
        _wrapper(args, kwds, deque, "__delitem__", 1)
        self = args[0]
        index = _ssize(args[1])
        if index < 0:
            index += len(self)  # type: ignore[arg-type]
        if not 0 <= index < _d_size(self):
            raise IndexError("deque index out of range")
        _d_delete(self, index)

    def __add__(*args: object, **kwds: object) -> object:   # deque_concat_lock_held
        _wrapper(args, kwds, deque, "__add__", 1)
        self, other = args
        if not isinstance(other, deque):
            raise TypeError("can only concatenate deque (not \"" + _tp_name(other) + "\") to deque")
        new = _d_copy(self)
        _d_extend(new, other)
        return new

    def __iadd__(*args: object, **kwds: object) -> object:   # deque_inplace_concat
        _wrapper(args, kwds, deque, "__iadd__", 1)
        _d_extend(args[0], args[1])
        return args[0]

    def __mul__(*args: object, **kwds: object) -> object:   # wrap_indexargfunc, deque_repeat
        _wrapper(args, kwds, deque, "__mul__", 1)
        return _d_repeat(args[0], _ssize(args[1]))

    def __rmul__(*args: object, **kwds: object) -> object:
        _wrapper(args, kwds, deque, "__rmul__", 1)
        return _d_repeat(args[0], _ssize(args[1]))

    def __imul__(*args: object, **kwds: object) -> object:
        _wrapper(args, kwds, deque, "__imul__", 1)
        return _d_inplace_repeat(args[0], _ssize(args[1]))

    def __repr__(*args: object, **kwds: object) -> str:   # deque_repr
        _wrapper(args, kwds, deque, "__repr__", 0)
        self = args[0]
        if not _repr_enter(self):
            return "[...]"
        try:
            aslist = list(self)  # type: ignore[call-overload]
            maxlen = self._c_maxlen  # type: ignore[attr-defined]
            if maxlen >= 0:
                return type(self).__name__ + "(" + repr(aslist) + ", maxlen=" + str(maxlen) + ")"
            return type(self).__name__ + "(" + repr(aslist) + ")"
        finally:
            _repr_leave(self)

    def __lt__(*args: object, **kwds: object) -> object:
        _wrapper(args, kwds, deque, "__lt__", 1)
        return _d_compare(args[0], args[1], 0)

    def __le__(*args: object, **kwds: object) -> object:
        _wrapper(args, kwds, deque, "__le__", 1)
        return _d_compare(args[0], args[1], 1)

    def __eq__(*args: object, **kwds: object) -> object:
        _wrapper(args, kwds, deque, "__eq__", 1)
        return _d_compare(args[0], args[1], 2)

    def __ne__(*args: object, **kwds: object) -> object:
        _wrapper(args, kwds, deque, "__ne__", 1)
        return _d_compare(args[0], args[1], 3)

    def __gt__(*args: object, **kwds: object) -> object:
        _wrapper(args, kwds, deque, "__gt__", 1)
        return _d_compare(args[0], args[1], 4)

    def __ge__(*args: object, **kwds: object) -> object:
        _wrapper(args, kwds, deque, "__ge__", 1)
        return _d_compare(args[0], args[1], 5)

    __hash__ = None  # type: ignore[assignment]

    def __reduce__(*args: object, **kwds: object) -> object:   # deque___reduce___impl
        _noargs(args, kwds, deque, "__reduce__", "deque")
        self = args[0]
        state = self.__getstate__()  # type: ignore[attr-defined]
        it = iter(self)  # type: ignore[call-overload]
        if self._c_maxlen < 0:  # type: ignore[attr-defined]
            return (type(self), (), state, it)
        return (type(self), ((), self._c_maxlen), state, it)  # type: ignore[attr-defined]

    def __sizeof__(*args: object, **kwds: object) -> int:
        _noargs(args, kwds, deque, "__sizeof__", "deque")
        _bella_refuse("deque.__sizeof__: the size of the C's blocks")


def _d_inplace_repeat(self: object, n: int) -> object:   # deque_inplace_repeat_lock_held
    size = _d_size(self)
    if size == 0 or n == 1:
        return self
    if n <= 0:
        _d_clear(self)
        return self
    if size == 1:
        item = _d_at(self, 0)
        maxlen = self._c_maxlen  # type: ignore[attr-defined]
        if maxlen >= 0 and n > maxlen:
            n = maxlen
        if n * size > 2**28:
            _bella_refuse("a deque of more than 2**28 items")
        self._d_state += 1  # type: ignore[attr-defined]
        for _ in range(n - 1):
            _d_right_cell(self)
            self._b_start -= 1  # type: ignore[attr-defined]
            self._a_items[self._b_start] = item  # type: ignore[attr-defined]
        return self
    if size > _SSIZE_MAX // n:
        raise MemoryError
    seq = list(self)  # type: ignore[call-overload]
    maxlen = self._c_maxlen  # type: ignore[attr-defined]
    if maxlen >= 0 and n * size > maxlen:
        n = (maxlen + size - 1) // size
    if n * size > 2**28:
        _bella_refuse("a deque of more than 2**28 items")
    for _ in range(n - 1):
        _d_extend(self, seq)
    return self


def _d_repeat(self: object, n: int) -> object:   # deque_repeat
    return _d_inplace_repeat(_d_copy(self), n)


def _make_iterator(cls: type, target: object) -> object:   # deque_iter, deque___reversed___impl
    it = _bella_new_instance(cls)
    it._a_deque = target  # type: ignore[attr-defined]
    it._b_position = 0  # type: ignore[attr-defined]
    it._c_counter = _d_size(target)  # type: ignore[attr-defined]
    it._d_state = target._d_state  # type: ignore[attr-defined]
    return it


def _iterator_new(cls: type, args: tuple[object, ...]) -> object:   # "O!|n"
    if len(args) < 1:                            # the keywords it is given are no one's business
        raise TypeError("function takes at least 1 argument (0 given)")
    if len(args) > 2:
        raise TypeError("function takes at most 2 arguments (" + str(len(args)) + " given)")
    if not issubclass(type(args[0]), deque):
        raise TypeError("argument 1 must be collections.deque, not " + ("None" if args[0] is None else _tp_name(args[0])))
    it = _make_iterator(cls, args[0])
    index = _ssize(args[1]) if len(args) == 2 else 0
    for _ in range(index):                       # consume items from the queue
        if it._c_counter == 0 and it._d_state == args[0]._d_state:  # type: ignore[attr-defined]
            break
        it.__next__()  # type: ignore[attr-defined]
    return it


class _deque_iterator:
    __module__ = "collections"
    __slots__ = ("_a_deque", "_b_position", "_c_counter", "_d_state")

    def __new__(*args: object, **kwds: object) -> object:
        _new_receiver(args, _deque_iterator, "collections._deque_iterator")
        cls, args = args[0], args[1:]
        return _iterator_new(cls, args)

    def __iter__(*args: object, **kwds: object) -> object:
        _wrapper(args, kwds, _deque_iterator, "__iter__", 0)
        return args[0]

    def __next__(*args: object, **kwds: object) -> object:   # dequeiter_next
        _wrapper(args, kwds, _deque_iterator, "__next__", 0)
        self = args[0]
        target = self._a_deque  # type: ignore[attr-defined]
        if target._d_state != self._d_state:  # type: ignore[attr-defined]
            self._c_counter = 0  # type: ignore[attr-defined]
            raise RuntimeError(_MUTATED)
        if self._c_counter == 0:  # type: ignore[attr-defined]
            raise StopIteration
        item = _d_at(target, self._b_position)  # type: ignore[attr-defined]
        self._b_position += 1  # type: ignore[attr-defined]
        self._c_counter -= 1  # type: ignore[attr-defined]
        return item

    def __length_hint__(*args: object, **kwds: object) -> int:
        _noargs(args, kwds, _deque_iterator, "__length_hint__", "_deque_iterator")
        return args[0]._c_counter  # type: ignore[attr-defined]

    def __reduce__(*args: object, **kwds: object) -> object:   # dequeiter_reduce
        _noargs(args, kwds, _deque_iterator, "__reduce__", "_deque_iterator")
        self = args[0]
        return (type(self), (self._a_deque, _d_size(self._a_deque) - self._c_counter))  # type: ignore[attr-defined]


class _deque_reverse_iterator:
    __module__ = "collections"
    __slots__ = ("_a_deque", "_b_position", "_c_counter", "_d_state")

    def __new__(*args: object, **kwds: object) -> object:
        _new_receiver(args, _deque_reverse_iterator, "collections._deque_reverse_iterator")
        cls, args = args[0], args[1:]
        return _iterator_new(cls, args)

    def __iter__(*args: object, **kwds: object) -> object:
        _wrapper(args, kwds, _deque_reverse_iterator, "__iter__", 0)
        return args[0]

    def __next__(*args: object, **kwds: object) -> object:   # dequereviter_next
        _wrapper(args, kwds, _deque_reverse_iterator, "__next__", 0)
        self = args[0]
        target = self._a_deque  # type: ignore[attr-defined]
        if self._c_counter == 0:  # type: ignore[attr-defined]
            raise StopIteration
        if target._d_state != self._d_state:  # type: ignore[attr-defined]
            self._c_counter = 0  # type: ignore[attr-defined]
            raise RuntimeError(_MUTATED)
        item = _d_at(target, _d_size(target) - 1 - self._b_position)  # type: ignore[attr-defined]
        self._b_position += 1  # type: ignore[attr-defined]
        self._c_counter -= 1  # type: ignore[attr-defined]
        return item

    def __length_hint__(*args: object, **kwds: object) -> int:
        _noargs(args, kwds, _deque_reverse_iterator, "__length_hint__", "_deque_reverse_iterator")
        return args[0]._c_counter  # type: ignore[attr-defined]

    def __reduce__(*args: object, **kwds: object) -> object:
        _noargs(args, kwds, _deque_reverse_iterator, "__reduce__", "_deque_reverse_iterator")
        self = args[0]
        return (type(self), (self._a_deque, _d_size(self._a_deque) - self._c_counter))  # type: ignore[attr-defined]


# ---- defaultdict

def _factory(self: object) -> object:            # dd->default_factory: the field itself, and None before __init__
    return getattr(self, "_a_factory", None)


class defaultdict(dict):  # type: ignore[type-arg]
    __module__ = "collections"
    __slots__ = ("_a_factory",)

    def __init__(*args: object, **kwds: object) -> None:   # defdict_init
        _wrapper(args[:1], {}, defaultdict, "__init__", 0)
        self = args[0]
        new_default = None
        rest = args[1:]
        if rest:
            new_default = rest[0]
            if not callable(new_default) and new_default is not None:
                raise TypeError("first argument must be callable or None")
            rest = rest[1:]
        old = _factory(self)
        self._a_factory = new_default  # type: ignore[attr-defined]
        dict.__init__(self, *rest, **kwds)  # type: ignore[arg-type]
        del old

    def __missing__(*args: object, **kwds: object) -> object:   # defdict_missing
        key = _one(args, kwds, defaultdict, "__missing__", "defaultdict")
        self = args[0]
        factory = _factory(self)
        if factory is None:
            raise KeyError((key,)[0])
        value = factory()
        return dict.setdefault(self, key, value)  # type: ignore[arg-type]

    def __repr__(*args: object, **kwds: object) -> str:   # defdict_repr
        _wrapper(args, kwds, defaultdict, "__repr__", 0)
        self = args[0]
        base = dict.__repr__(self)  # type: ignore[arg-type]
        factory = _factory(self)
        if factory is None:
            shown = "None"
        elif not _repr_enter(factory):
            shown = "..."
        else:
            try:
                shown = repr(factory)
            finally:
                _repr_leave(factory)
        return type(self).__name__ + "(" + shown + ", " + base + ")"

    def copy(*args: object, **kwds: object) -> object:   # defdict_copy, new_defdict
        _noargs(args, kwds, defaultdict, "copy", "defaultdict")
        return type(args[0])(_factory(args[0]), args[0])  # type: ignore[call-arg]

    def __copy__(*args: object, **kwds: object) -> object:
        _noargs(args, kwds, defaultdict, "__copy__", "defaultdict")
        return type(args[0])(_factory(args[0]), args[0])  # type: ignore[call-arg]

    def __reduce__(*args: object, **kwds: object) -> object:   # defdict_reduce
        _noargs(args, kwds, defaultdict, "__reduce__", "defaultdict")
        self = args[0]
        factory = _factory(self)
        return (type(self), () if factory is None else (factory,), None, None, iter(self.items()))  # type: ignore[attr-defined]

    def __or__(*args: object, **kwds: object) -> object:   # defdict_or
        _wrapper(args, kwds, defaultdict, "__or__", 1)
        return _dd_or(args[0], args[1])

    def __ror__(*args: object, **kwds: object) -> object:
        _wrapper(args, kwds, defaultdict, "__ror__", 1)
        return _dd_or(args[1], args[0])


def _dd_or(left: object, right: object) -> object:
    if issubclass(type(left), defaultdict):
        self, other = left, right
    else:
        self, other = right, left
    if not issubclass(type(other), dict):
        return NotImplemented
    new = type(self)(_factory(self), left)  # type: ignore[call-arg]
    dict.update(new, right)  # type: ignore[arg-type, call-overload]
    return new


class OrderedDict(dict):  # type: ignore[type-arg]   # Objects/odictobject.c
    __module__ = "collections"

    def __new__(cls, *args: object, **kwds: object) -> OrderedDict:
        _bella_refuse("collections.OrderedDict (step 3b: Objects/odictobject.c)")


# ---- _tuplegetter

class _tuplegetter:
    __module__ = "collections"
    __slots__ = ("_a_index", "_b_doc")

    def __new__(*args: object, **kwds: object) -> _tuplegetter:   # tuplegetter_new_impl(index, doc, /)
        _new_receiver(args, _tuplegetter, "collections._tuplegetter")
        cls, args = args[0], args[1:]
        if kwds:
            raise TypeError("_tuplegetter() takes no keyword arguments")
        if len(args) != 2:
            raise TypeError("_tuplegetter expected 2 arguments, got " + str(len(args)))
        self = _bella_new_instance(cls)
        self._a_index = _clinic_ssize(args[0])
        self._b_doc = args[1]
        return self

    def __get__(*args: object, **kwds: object) -> object:   # tuplegetter_descr_get
        if kwds:
            raise TypeError("wrapper __get__() takes no keyword arguments")
        if len(args) < 2:
            raise TypeError("__get__ expected at least 1 argument, got " + str(max(len(args) - 1, 0)))
        if len(args) > 3:
            raise TypeError("__get__ expected at most 2 arguments, got " + str(len(args) - 1))
        self, obj = args[0], args[1]
        owner = args[2] if len(args) == 3 else None
        if obj is None:
            if owner is None:
                raise TypeError("__get__(None, None) is invalid")
            return self
        index = self._a_index  # type: ignore[attr-defined]
        if not issubclass(type(obj), tuple):
            raise TypeError("descriptor for index '" + str(index) + "' for tuple subclasses doesn't apply to '" + _tp_name(obj) + "' object")
        if not 0 <= index < tuple.__len__(obj):  # type: ignore[arg-type]
            raise IndexError("tuple index out of range")
        return tuple.__getitem__(obj, index)  # type: ignore[arg-type]

    def __set__(*args: object, **kwds: object) -> None:   # tuplegetter_descr_set
        _wrapper(args[:1], {}, _tuplegetter, "__set__", 0)
        if len(args) != 3:
            raise TypeError("__set__ expected 2 arguments, got " + str(len(args) - 1))
        raise AttributeError("can't set attribute")

    def __delete__(*args: object, **kwds: object) -> None:
        _wrapper(args, kwds, _tuplegetter, "__delete__", 1)
        raise AttributeError("can't delete attribute")

    def __reduce__(*args: object, **kwds: object) -> object:   # tuplegetter_reduce
        _noargs(args, kwds, _tuplegetter, "__reduce__", "_tuplegetter")
        self = args[0]
        return (type(self), (self._a_index, self._b_doc))  # type: ignore[attr-defined]

    def __repr__(*args: object, **kwds: object) -> str:   # tuplegetter_repr
        _wrapper(args, kwds, _tuplegetter, "__repr__", 0)
        self = args[0]
        return type(self).__name__ + "(" + str(self._a_index) + ", " + repr(self._b_doc) + ")"  # type: ignore[attr-defined]


def _count_elements(*args: object, **kwds: object) -> None:   # _collections__count_elements_impl(mapping, iterable, /)
    if kwds:
        raise TypeError("_collections._count_elements() takes no keyword arguments")
    if len(args) != 2:
        raise TypeError("_count_elements expected 2 arguments, got " + str(len(args)))
    mapping, iterable = args
    it = iter(iterable)  # type: ignore[call-overload]
    cls = type(mapping)
    if issubclass(cls, dict) and getattr(cls, "get", None) is dict.get and getattr(cls, "__setitem__", None) is dict.__setitem__:
        for key in it:
            _count_element(mapping, key)
            del key
        return
    bound_get = mapping.get  # type: ignore[attr-defined]
    for key in it:
        mapping[key] = bound_get(key, 0) + 1  # type: ignore[index]
