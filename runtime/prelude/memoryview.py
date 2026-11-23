"""memoryview, in Python (Objects/memoryobject.c), as far as phase 1 has it (the author's decision of 2026-11-14): one-dimensional
views of octets over bytes and bytearray, and views of views. What else CPython's type has (`cast`, `hex`, `count`, `index`,
`toreadonly`, the buffer protocol of a program's own classes) stops by name through the names table.

A view does not hold its object: it holds a managed buffer, the one hold on the object's octets that every view made of it
shares, and the hold ends when the last view holding it is released or dies (refmodel/objects.py, "Buffers"). While it lasts
a bytearray cannot change its size, which is what lets the runtime read a contiguous view's octets where they are.

It runs as `builtins`, after builtins.py has made staticmethod (a class with a __new__ of its own needs it)."""

__all__ = ["memoryview"]
__hidden_classes__ = ["memory_iterator"]         # a type of the builtins that is no name of theirs

try:
    _bella_new_instance                          # noqa: B018  # tp_alloc: this type's __new__ makes its instance
    _bella_export                                # noqa: B018  # a bytearray's ob_exports, up or down (bytearray_getbuffer, bytearray_releasebuffer)
    _number_index                                # noqa: B018  # PyNumber_Index
    _has_slot                                    # noqa: B018  # a slot of the type, by its own MRO and dicts: the runtime's (RL-644)
    _tp_name                                     # noqa: B018  # Py_TYPE(obj)->tp_name
    _class_name                                  # noqa: B018  # _PyType_Name of a class itself
    _bella_refuse                                # noqa: B018  # a stop by name
except NameError:                                # CPython runs this file: what stands for them
    _bella_new_instance = object.__new__

    def _bella_export(obj: object, delta: int) -> None:
        pass

    def _number_index(value: object) -> int:
        import operator
        return operator.index(value)

    def _has_slot(value: object, name: str) -> bool:   # read from type's own descriptors: no metaclass answers (RL-644)
        mro = type.__dict__["__mro__"].__get__(type(value))
        return any(name in type.__dict__["__dict__"].__get__(k) for k in mro)

    def _tp_name(obj: object) -> str:
        return type(obj).__name__

    def _class_name(cls: type) -> str:
        return cls.__name__

    def _bella_refuse(what: str) -> None:
        raise NotImplementedError(what)


_RELEASED = "operation forbidden on released memoryview object"
_SSIZE_MAX = (1 << 63) - 1


def _ssize_product(a: int, b: int) -> int:     # init_slice's `strides[dim] * step`: a Py_ssize_t, which wraps (RL-890)
    return ((a * b + (1 << 63)) % (1 << 64)) - (1 << 63)


class _ManagedBuffer:
    """_PyManagedBufferObject: the master buffer of an exporter, which the views share. Only views that are not released
    hold it, so its end is mbuf_release: the exporter's count of exports goes down (bytearray_releasebuffer), then the
    exporter is let go of, as the slot is cleared after this."""

    __bella_dealloc__ = True                     # its __del__ is C dealloc code: the collection's finaliser pass leaves it (RL-908)
    __slots__ = ("_obj",)

    def __del__(self) -> None:
        _bella_export(self._obj, -1)


def _exporter_octets(exporter: object, start: int, step: int, length: int) -> bytes:
    """The view's octets as an exact bytes: read from the exporter itself, so a bytearray changed in place is seen."""
    if length == 0:
        return b""
    if length == 1:
        return bytes((_octet(exporter, start),))
    stop: int | None = start + (length - 1) * step + (1 if step > 0 else -1)
    if stop is not None and stop < 0:
        stop = None
    key = slice(start, stop, step)
    if issubclass(type(exporter), bytes):
        return bytes.__getitem__(exporter, key)  # type: ignore[arg-type]
    return bytes(bytearray.__getitem__(exporter, key))  # type: ignore[arg-type]


def _octet(exporter: object, at: int) -> int:
    if issubclass(type(exporter), bytes):
        return bytes.__getitem__(exporter, at)  # type: ignore[arg-type]
    return bytearray.__getitem__(exporter, at)  # type: ignore[arg-type]


def _slice_index(value: object) -> int:          # _PyEval_SliceIndex: an int, or what __index__ gives, clamped to a Py_ssize_t
    if not _has_slot(value, "__index__"):
        raise TypeError("slice indices must be integers or have an __index__ method")
    n = _number_index(value)
    return max(-_SSIZE_MAX - 1, min(_SSIZE_MAX, n))


def _adjusted(key: slice, length: int) -> tuple[int, int, int]:
    """PySlice_Unpack (the step first, then the start and the stop) and PySlice_AdjustIndices: start, step, how many."""
    step = 1 if key.step is None else _slice_index(key.step)
    if step == 0:
        raise ValueError("slice step cannot be zero")
    if step < -_SSIZE_MAX:
        step = -_SSIZE_MAX
    if key.start is None:
        start = _SSIZE_MAX if step < 0 else 0
    else:
        start = _slice_index(key.start)
    if key.stop is None:
        stop = -_SSIZE_MAX - 1 if step < 0 else _SSIZE_MAX
    else:
        stop = _slice_index(key.stop)
    if start < 0:
        start += length
        if start < 0:
            start = -1 if step < 0 else 0
    elif start >= length:
        start = length - 1 if step < 0 else length
    if stop < 0:
        stop += length
        if stop < 0:
            stop = -1 if step < 0 else 0
    elif stop >= length:
        stop = length - 1 if step < 0 else length
    if step < 0:
        count = (start - stop - 1) // (-step) + 1 if stop < start else 0
    else:
        count = (stop - start - 1) // step + 1 if start < stop else 0
    return start, step, count


def _exporter(view: memoryview) -> object:       # CHECK_RELEASED, and the object the octets are in
    if view._hold is None:
        raise ValueError(_RELEASED)
    return view._hold._obj  # type: ignore[attr-defined]


def _release(view: memoryview) -> None:         # _memory_release: not while something holds a buffer of the view itself
    if view._hold is None:
        return
    if view._exports > 0:
        raise BufferError("memoryview has " + str(view._exports) + " exported buffer" + ("s" if view._exports > 1 else ""))
    view._hold = None                            # the hold ends with the last view that keeps it


def _pack_single(view: memoryview, at: int, value: object) -> None:   # pack_single for format 'B'
    octet = 0
    wrong: type[Exception] | None = None
    try:
        octet = _number_index(value)             # pylong_as_lu: PyNumber_Index
    except (TypeError, OverflowError, ValueError) as error:
        wrong = TypeError if issubclass(type(error), TypeError) else ValueError   # PyErr_ExceptionMatches: the class
    if wrong is not None:                        # fix_error_int: the error replaced, outside the handler (RL-448, RL-902)
        raise wrong("memoryview: invalid " + ("type" if wrong is TypeError else "value") + " for format 'B'")
    exporter = _exporter(view)                   # CHECK_RELEASED_INT_AGAIN: the conversion may have released the view (RL-891)
    if not 0 <= octet <= 255:
        raise ValueError("memoryview: invalid value for format 'B'")
    bytearray.__setitem__(exporter, at, octet)  # type: ignore[arg-type]


def _contiguous(view: memoryview) -> bool:       # MV_CONTIGUOUS_NDIM1: one item, or items next to each other
    return view._length == 1 or view._step == 1


def _item(view: memoryview, at: object) -> int:  # memory_item: an index, from the end where it is negative
    n = _number_index(at)
    if n < -_SSIZE_MAX - 1 or n > _SSIZE_MAX:    # PyNumber_AsSsize_t(key, PyExc_IndexError)
        raise IndexError("cannot fit 'int' into an index-sized integer")
    if n < 0:
        n += view._length
    if n < 0 or n >= view._length:
        raise IndexError("index out of bounds on dimension 1")
    return n


def _octets_of(other: object) -> bytes | None:   # memory_richcompare's other side: a buffer of octets, or None
    if type(other) is memoryview:
        if other._hold is None:  # type: ignore[attr-defined]
            return None
        return _exporter_octets(other._hold._obj, other._start, other._step, other._length)  # type: ignore[attr-defined]
    if issubclass(type(other), bytes):
        return bytes.__getitem__(other, slice(None))  # type: ignore[arg-type]
    if issubclass(type(other), bytearray):
        return bytes(bytearray.__getitem__(other, slice(None)))  # type: ignore[arg-type]
    if _has_slot(other, "__buffer__"):
        _bella_refuse("[P2+] comparing a memoryview with a buffer of a type other than bytes, bytearray and memoryview")
    return None


class memoryview:  # noqa: N801
    """Create a new memoryview object which references the given object."""

    __slots__ = ("_exports", "_hash", "_hold", "_length", "_readonly", "_start", "_step")
    # memory_dealloc: the view is released (with the last view, the exporter let go of) before its weak references are cleared
    __release__ = ("_hold", "_exports", "_hash", "_length", "_readonly", "_start", "_step", "__weakref__")

    def __new__(*args: object, **kwds: object) -> memoryview:  # noqa: N805  # memoryview_impl
        if not args:
            raise TypeError("memoryview.__new__(): not enough arguments")
        cls = args[0]
        if not issubclass(type(cls), type):
            raise TypeError("memoryview.__new__(X): X is not a type object (" + _tp_name(cls) + ")")
        if not issubclass(cls, memoryview):  # type: ignore[arg-type]
            raise TypeError("memoryview.__new__(" + _class_name(cls) + "): " + _class_name(cls) + " is not a subtype of memoryview")  # type: ignore[arg-type]
        given = args[1:]
        total = len(given) + len(kwds)
        if total > 1:
            if given:
                raise TypeError("memoryview() takes at most 1 argument (" + str(total) + " given)")
            raise TypeError("memoryview() takes at most 1 keyword argument (" + str(total) + " given)")
        if given:
            source = given[0]
        elif "object" in kwds:
            source = kwds["object"]
        else:
            raise TypeError("memoryview() missing required argument 'object' (pos 1)")
        self: memoryview = _bella_new_instance(cls)
        self._exports = 0                        # what holds a buffer of this view itself (the regular expression engine, a hash)
        self._hash = -1                          # memory_hash keeps what it computed: -1 for none yet
        if type(source) is memoryview:           # PyMemoryView_Check: mbuf_add_view, one more view of the same hold
            hold = source._hold  # type: ignore[attr-defined]
            if hold is None:
                raise ValueError(_RELEASED)
            self._hold = hold
            self._start = source._start  # type: ignore[attr-defined]
            self._step = source._step  # type: ignore[attr-defined]
            self._length = source._length  # type: ignore[attr-defined]
            self._readonly = source._readonly  # type: ignore[attr-defined]
            return self
        if issubclass(type(source), (bytes, bytearray)):   # PyObject_GetBuffer: a new hold on the exporter
            hold = _bella_new_instance(_ManagedBuffer)
            hold._obj = source
            _bella_export(source, 1)
            self._hold = hold
            self._start = 0
            self._step = 1
            self._length = bytes.__len__(source) if issubclass(type(source), bytes) else bytearray.__len__(source)  # type: ignore[arg-type]
            self._readonly = issubclass(type(source), bytes)
            return self
        if _has_slot(source, "__buffer__"):
            _bella_refuse("[P2+] the buffer protocol of a type other than bytes, bytearray and memoryview (__buffer__)")
        raise TypeError("memoryview: a bytes-like object is required, not '" + _tp_name(source) + "'")

    # ---- what it is --------------------------------------------------------------------------------------------------
    @property
    def obj(self) -> object:
        """The underlying object of the memoryview."""
        return _exporter(self)

    @property
    def nbytes(self) -> int:
        """The amount of space in bytes that the array would use in a contiguous representation."""
        _exporter(self)
        return self._length

    @property
    def readonly(self) -> bool:
        """A bool indicating whether the memory is read only."""
        _exporter(self)
        return self._readonly

    @property
    def itemsize(self) -> int:
        """The size in bytes of each element of the memoryview."""
        _exporter(self)
        return 1

    @property
    def format(self) -> str:
        """A string containing the format (in struct module style) for each element in the view."""
        _exporter(self)
        return "B"

    @property
    def ndim(self) -> int:
        """An integer indicating how many dimensions of a multi-dimensional array the memory represents."""
        _exporter(self)
        return 1

    @property
    def shape(self) -> tuple[int, ...]:
        """A tuple of ndim integers giving the shape of the memory as an N-dimensional array."""
        _exporter(self)
        return (self._length,)

    @property
    def strides(self) -> tuple[int, ...]:
        """A tuple of ndim integers giving the size in bytes to access each element for each dimension of the array."""
        _exporter(self)
        return (self._step,)

    @property
    def suboffsets(self) -> tuple[int, ...]:
        """A tuple of integers used internally for PIL-style arrays."""
        _exporter(self)
        return ()

    @property
    def c_contiguous(self) -> bool:
        """A bool indicating whether the memory is C contiguous."""
        _exporter(self)
        return _contiguous(self)

    @property
    def f_contiguous(self) -> bool:
        """A bool indicating whether the memory is Fortran contiguous."""
        _exporter(self)
        return _contiguous(self)

    @property
    def contiguous(self) -> bool:
        """A bool indicating whether the memory is contiguous."""
        _exporter(self)
        return _contiguous(self)

    # ---- the items -----------------------------------------------------------------------------------------------------
    def __len__(self) -> int:
        _exporter(self)
        return self._length

    def __getitem__(self, key: object) -> object:   # memory_subscript
        _exporter(self)                          # CHECK_RELEASED
        if _has_slot(key, "__index__"):
            at = _item(self, key)                # PyNumber_AsSsize_t, which may run the program's code; memory_item checks again
            return _octet(_exporter(self), self._start + at * self._step)
        if type(key) is slice:
            view: memoryview = _bella_new_instance(memoryview)   # mbuf_add_view: the slice holds the buffer before its bounds
            view._exports = 0                    # are converted, so a bound that releases this view leaves the slice whole
            view._hash = -1
            view._hold = self._hold
            view._readonly = self._readonly
            view._start = self._start
            view._step = self._step
            view._length = self._length
            start, step, count = _adjusted(key, self._length)   # init_slice
            view._start = self._start + start * self._step
            view._step = _ssize_product(self._step, step)
            view._length = count
            return view
        if issubclass(type(key), tuple):         # PyTuple_GET_SIZE and PyTuple_GET_ITEM: the tuple's own cells
            size = tuple.__len__(key)  # type: ignore[arg-type]
            items = [tuple.__getitem__(key, i) for i in range(size)]  # type: ignore[arg-type]
            if all(_has_slot(k, "__index__") for k in items):   # is_multiindex (an empty tuple is one): memory_item_multi
                if size < 1:
                    raise NotImplementedError("sub-views are not implemented")
                if size > 1:
                    raise TypeError("cannot index 1-dimension view with " + str(size) + "-element tuple")
                at = _item(self, items[0])       # ptr_from_tuple; unpack_single checks for a release again
                return _octet(_exporter(self), self._start + at * self._step)
            if size > 0 and all(type(k) is slice for k in items):   # is_multislice
                raise NotImplementedError("multi-dimensional slicing is not implemented")
        raise TypeError("memoryview: invalid slice key")

    def __setitem__(self, key: object, value: object) -> None:   # memory_ass_sub, for format 'B'
        _exporter(self)                          # CHECK_RELEASED_INT
        if self._readonly:
            raise TypeError("cannot modify read-only memory")
        if _has_slot(key, "__index__"):
            _pack_single(self, self._start + _item(self, key) * self._step, value)
            return
        if type(key) is slice:
            _bella_refuse("memoryview slice assignment")
        if issubclass(type(key), tuple):         # PyTuple_GET_SIZE and PyTuple_GET_ITEM: the tuple's own cells
            size = tuple.__len__(key)  # type: ignore[arg-type]
            items = [tuple.__getitem__(key, i) for i in range(size)]  # type: ignore[arg-type]
            if all(_has_slot(k, "__index__") for k in items):   # is_multiindex
                if size < 1:
                    raise NotImplementedError("sub-views are not implemented")
                if size > 1:
                    raise TypeError("cannot index 1-dimension view with " + str(size) + "-element tuple")
                _pack_single(self, self._start + _item(self, items[0]) * self._step, value)
                return
            if size > 0 and all(type(k) is slice for k in items):   # is_multislice
                raise NotImplementedError("memoryview slice assignments are currently restricted to ndim = 1")
        raise TypeError("memoryview: invalid slice key")

    def __delitem__(self, key: object) -> None:
        _exporter(self)
        if self._readonly:
            raise TypeError("cannot modify read-only memory")
        raise TypeError("cannot delete memory")

    def __iter__(self) -> memory_iterator:       # memory_iter
        _exporter(self)
        it: memory_iterator = _bella_new_instance(memory_iterator)
        it._seq = self
        it._index = 0
        return it

    def tobytes(self, *args: object, **kwds: object) -> bytes:
        """Return the data in the buffer as a byte string.

Order can be {'C', 'F', 'A'}. When order is 'C' or 'F', the data of the
original array is converted to C or Fortran order. For contiguous views,
'A' returns an exact copy of the physical memory. In particular, in-memory
Fortran order is preserved. For non-contiguous views, the data is converted
to C first. order=None is the same as order='C'."""
        if len(args) + len(kwds) > 1:
            raise TypeError("tobytes() takes at most 1 argument (" + str(len(args) + len(kwds)) + " given)")
        for name in kwds:
            if name != "order":
                raise TypeError("tobytes() got an unexpected keyword argument '" + name + "'")
        order = args[0] if args else kwds.get("order")
        chars = b"C"
        if order is not None:                    # the clinic: PyUnicode_AsUTF8AndSize, and no NUL inside
            if not issubclass(type(order), str):
                raise TypeError("tobytes() argument 'order' must be str or None, not " + _tp_name(order))
            chars = str.encode(order, "utf-8")  # type: ignore[arg-type]
            if bytes.__contains__(chars, 0):
                raise ValueError("embedded null character")
        exporter = _exporter(self)
        if not (bytes.__eq__(chars, b"C") or bytes.__eq__(chars, b"F") or bytes.__eq__(chars, b"A")):
            raise ValueError("order must be 'C', 'F' or 'A'")
        return _exporter_octets(exporter, self._start, self._step, self._length)

    def tolist(self, *args: object, **kwds: object) -> list[int]:
        """Return the data in the buffer as a list of elements."""
        if kwds:
            raise TypeError("memoryview.tolist() takes no keyword arguments")
        if args:
            raise TypeError("memoryview.tolist() takes no arguments (" + str(len(args)) + " given)")
        exporter = _exporter(self)
        return [_octet(exporter, self._start + i * self._step) for i in range(self._length)]

    def release(self, *args: object, **kwds: object) -> None:
        """Release the underlying buffer exposed by the memoryview object."""
        if kwds:
            raise TypeError("memoryview.release() takes no keyword arguments")
        if args:
            raise TypeError("memoryview.release() takes no arguments (" + str(len(args)) + " given)")
        _release(self)

    def __enter__(self, *args: object, **kwds: object) -> memoryview:
        if kwds:
            raise TypeError("memoryview.__enter__() takes no keyword arguments")
        if args:
            raise TypeError("memoryview.__enter__() takes no arguments (" + str(len(args)) + " given)")
        _exporter(self)
        return self

    def __exit__(self, *args: object) -> None:   # memory_exit: METH_VARARGS, and release()
        _release(self)

    # ---- as a value ------------------------------------------------------------------------------------------------------
    def __repr__(self) -> str:
        if self._hold is None:
            return "<released memory at " + hex(id(self)) + ">"
        return "<memory at " + hex(id(self)) + ">"

    def __hash__(self) -> int:                   # memory_hash: read-only views alone, after the exporter's own hash
        if self._hash == -1:                     # computed once, and then answered, released or not
            exporter = _exporter(self)
            if not self._readonly:
                raise ValueError("cannot hash writable memoryview object")
            self._exports += 1                   # the view cannot be released while the exporter's hash runs (gh-142664)
            try:
                hash(exporter)
            finally:
                self._exports -= 1
            self._hash = hash(_exporter_octets(exporter, self._start, self._step, self._length))
        return self._hash

    def __eq__(self, other: object) -> object:
        if self is other:                        # the same object is equal to itself, released or not
            return True
        if self._hold is None or (type(other) is memoryview and other._hold is None):  # type: ignore[attr-defined]
            return False
        theirs = _octets_of(other)
        if theirs is None:
            return NotImplemented
        return _exporter_octets(self._hold._obj, self._start, self._step, self._length) == theirs  # type: ignore[attr-defined]

    def __ne__(self, other: object) -> object:
        equal = memoryview.__eq__(self, other)
        return equal if equal is NotImplemented else not equal

    def __lt__(self, other: object) -> object:
        return NotImplemented

    def __le__(self, other: object) -> object:
        return NotImplemented

    def __gt__(self, other: object) -> object:
        return NotImplemented

    def __ge__(self, other: object) -> object:
        return NotImplemented

    def __class_getitem__(cls, item: object) -> object:
        return type(list[int])(cls, item)        # Py_GenericAlias: the type is bootstrap.py's, which runs after this file


class memory_iterator:  # noqa: N801             # memory_iterator: Objects/memoryobject.c, memiterobject
    __slots__ = ("_index", "_seq")

    def __iter__(self) -> memory_iterator:
        return self

    def __next__(self) -> int:                   # memoryiter_next
        seq = self._seq
        if seq is None:
            raise StopIteration
        if self._index < seq._length:
            exporter = _exporter(seq)
            value = _octet(exporter, seq._start + self._index * seq._step)
            self._index += 1
            return value
        self._seq = None
        raise StopIteration


memoryview.__module__ = "builtins"
memory_iterator.__module__ = "builtins"
