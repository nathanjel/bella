"""_struct, in Python (Modules/_struct.c): the format string (byte order, repeat counts, every code of 3.15, whitespace), the
native table with x86-64's sizes and alignments and the standard tables, pack and unpack for each code with the C's range messages,
`Struct` with `format`, `size`, `pack`, `pack_into`, `unpack`, `unpack_from`, `iter_unpack` and its iterator, the module's functions
over a cache of a hundred compiled formats, and `error`. Floats go through the runtime's PyFloat_Pack and PyFloat_Unpack."""

__all__ = ["Struct", "_clearcache", "calcsize", "error", "iter_unpack", "pack", "pack_into", "unpack", "unpack_from"]
__hidden_classes__ = ["unpack_iterator"]         # _struct.unpack_iterator: a type of the module that is no name of it

__name__ = "_struct"

try:
    _bella_new_instance                          # noqa: B018  # tp_alloc: this type's __new__ makes its instance
    _bella_state_set                             # noqa: B018  # a C function's store into its struct's field (RL-507)
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _tp_name                                     # noqa: B018  # Py_TYPE(o)->tp_name
    _keyword_suggestion                          # noqa: B018  # _Py_CalculateSuggestions
    _float_pack                                  # noqa: B018  # PyFloat_Pack2/4/8: (x, size, little_endian[, cast]) -> bytes
    _float_unpack                                # noqa: B018  # PyFloat_Unpack2/4/8: (data, little_endian[, cast]) -> float
    _number_index                                # noqa: B018  # PyNumber_Index
    _as_double                                   # noqa: B018  # PyFloat_AsDouble: the runtime's, with its warning for a float's subclass
    _as_c_complex                                # noqa: B018  # PyComplex_AsCComplex: (real, imag)
    _has_slot                                    # noqa: B018  # a slot of the type, by its own MRO and dicts: the runtime's (RL-644)
    _buffer_bytes                                # noqa: B018  # a bytes's or bytearray's octets as an exact bytes: the runtime's (RL-698)
    _own_data                                    # noqa: B018  # an argument's own data as the exact base object: the runtime's (RL-698)
    _repr_text                                   # noqa: B018  # %R: the characters of an object's repr, an exact str (RL-748's class)
    _type_name                                   # noqa: B018  # _PyType_Name(Py_TYPE(x)): tp_name after its last dot, no attribute of the class (RL-767)
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_new_instance = object.__new__
    _bella_state_set = object.__setattr__
    _bella_refuse: Callable[..., Any] = _missing
    _keyword_suggestion: Callable[..., str | None] = _missing
    _float_pack: Callable[..., bytes] = _missing
    _float_unpack: Callable[..., float] = _missing

    def _tp_name(o: object) -> str:
        return type(o).__name__

    def _number_index(o: object) -> int:
        import operator
        return operator.index(o)

    def _as_double(value: object) -> float:      # for probing this file under CPython
        return float(value)  # type: ignore[arg-type]

    def _as_c_complex(value: object) -> tuple[float, float]:
        z = complex(value)  # type: ignore[call-overload]
        return z.real, z.imag
    _has_slot: Callable[..., bool] = _missing
    _buffer_bytes: Callable[..., bytes] = _missing
    _own_data: Callable[..., Any] = _missing

    def _repr_text(value: object) -> str:        # a stand-in for CPython's run of this file
        return str.__str__(repr(value))

    def _type_name(value: object) -> str:        # a stand-in for CPython's run of this file
        return type(value).__name__

class error(Exception):  # noqa: N801           # PyErr_NewException("struct.error", NULL, NULL)
    pass


error.__module__ = "struct"

_SSIZE_MAX = 2**63 - 1


# ---- the clinic's converters ----------------------------------------------------------------------------------------------

_ABSENT: object = object()


def _is_bytes_like(value: object) -> bool:
    if issubclass(type(value), (bytes, bytearray)):
        return True
    if _has_slot(value, "__buffer__"):
        _bella_refuse("[P2+] the buffer protocol (__buffer__)")
    return False


def _buffer(value: object) -> bytes:             # Py_buffer, read-only: the bytes
    if not _is_bytes_like(value):
        raise TypeError("a bytes-like object is required, not '" + _tp_name(value) + "'")
    return _buffer_bytes(value)


def _rw_buffer(value: object, function: str, position: int) -> bytearray:   # Py_buffer(accept={rwbuffer}): a bytearray, the one writable buffer
    if issubclass(type(value), bytearray):
        return value  # type: ignore[return-value]
    if not issubclass(type(value), bytes) and _has_slot(value, "__buffer__"):
        _bella_refuse("[P2+] the buffer protocol (__buffer__)")
    raise TypeError(function + "() argument " + str(position) + " must be read-write bytes-like object, not " + _tp_name(value))


_index = _number_index                           # PyNumber_Index: the runtime's, with its messages (review G15 #6)


def _ssize(value: object) -> int:                # the clinic's Py_ssize_t converter
    n = _index(value)
    if n < -(2**63) or n > _SSIZE_MAX:
        raise OverflowError("Python int too large to convert to C ssize_t")
    return n


def _unpack_args(name: str, args: tuple[object, ...], kwds: dict[str, object], names: tuple[str, ...], minpos: int,
                 maxpos: int) -> list[object]:
    """_PyArg_UnpackKeywords: the values, _ABSENT for a keyword not given; `names` are the parameters that may come by keyword, the
    positional-only ones ("") before them."""
    nargs = len(args)
    nkw = len(kwds)
    maxargs = len(names)
    minposonly = 0
    while minposonly < maxargs and not names[minposonly]:
        minposonly += 1
    if nargs + nkw > maxargs:
        raise TypeError(name + "() takes at most " + str(maxargs) + (" keyword" if nargs == 0 else "") + " argument" + ("" if maxargs == 1 else "s") + " (" + str(nargs + nkw) + " given)")
    if nargs > maxpos:
        raise TypeError(name + "() takes " + ("at most" if minpos < maxpos else "exactly") + " " + str(maxpos) + " positional argument" + ("" if maxpos == 1 else "s") + " (" + str(nargs) + " given)")
    if nargs < minposonly:
        raise TypeError(name + "() takes " + ("at least" if minposonly < maxpos else "exactly") + " " + str(minposonly) + " positional argument" + ("" if minposonly == 1 else "s") + " (" + str(nargs) + " given)")
    out: list[object] = [*args, *[_ABSENT] * (maxargs - nargs)]
    if nkw:
        for i in range(nargs):
            if names[i] and names[i] in kwds:
                raise TypeError("argument for " + name + "() given by name ('" + names[i] + "') and position (" + str(i + 1) + ")")
    left = nkw
    i = nargs
    while i < maxargs:
        if not left and i >= minpos:
            break
        if left and names[i] and names[i] in kwds:
            out[i] = kwds[names[i]]
            left -= 1
        elif i < minpos:
            raise TypeError(name + "() missing required argument '" + names[i] + "' (pos " + str(i + 1) + ")")
        i += 1
    if left > 0:                                 # error_unexpected_keyword
        for keyword in kwds:
            if keyword not in names:
                suggestion = _keyword_suggestion(tuple(n for n in names if n), keyword)
                if suggestion is not None:
                    raise TypeError(name + "() got an unexpected keyword argument '" + keyword + "'. Did you mean '" + suggestion + "'?")
                raise TypeError(name + "() got an unexpected keyword argument '" + keyword + "'")
    return out


def _positional(name: str, args: tuple[object, ...], kwds: dict[str, object], low: int, high: int) -> None:   # _PyArg_CheckPositional
    if kwds:
        raise TypeError("_struct." + name + "() takes no keyword arguments")
    if len(args) < low:
        raise TypeError(name + " expected " + ("at least " if low < high else "") + str(low) + " argument" + ("" if low == 1 else "s") + ", got " + str(len(args)))
    if len(args) > high:
        raise TypeError(name + " expected " + ("at most " if low < high else "") + str(high) + " argument" + ("" if high == 1 else "s") + ", got " + str(len(args)))


# ---- the format tables (native_table, bigendian_table, lilendian_table) -------------------------------------------------

# code -> (size, alignment, kind). The kinds: pad, bytes (s), pascal (p), char, int, uint, bool, float, complex, pointer.
_NATIVE: dict[str, tuple[int, int, str]] = {
    "x": (1, 0, "pad"), "b": (1, 0, "int"), "B": (1, 0, "uint"), "c": (1, 0, "char"), "s": (1, 0, "bytes"), "p": (1, 0, "pascal"),
    "h": (2, 2, "int"), "H": (2, 2, "uint"), "i": (4, 4, "int"), "I": (4, 4, "uint"), "l": (8, 8, "int"), "L": (8, 8, "uint"),
    "n": (8, 8, "int"), "N": (8, 8, "uint"), "q": (8, 8, "int"), "Q": (8, 8, "uint"), "?": (1, 1, "bool"),
    "e": (2, 2, "float"), "f": (4, 4, "float"), "d": (8, 8, "float"), "F": (8, 4, "complex"), "D": (16, 8, "complex"),
    "Zf": (8, 4, "complex"), "Zd": (16, 8, "complex"), "P": (8, 8, "pointer"),
}
_STANDARD: dict[str, tuple[int, int, str]] = {
    "x": (1, 0, "pad"), "b": (1, 0, "int"), "B": (1, 0, "uint"), "c": (1, 0, "char"), "s": (1, 0, "bytes"), "p": (1, 0, "pascal"),
    "h": (2, 0, "int"), "H": (2, 0, "uint"), "i": (4, 0, "int"), "I": (4, 0, "uint"), "l": (4, 0, "int"), "L": (4, 0, "uint"),
    "q": (8, 0, "int"), "Q": (8, 0, "uint"), "?": (1, 0, "bool"), "e": (2, 0, "float"), "f": (4, 0, "float"), "d": (8, 0, "float"),
    "F": (8, 0, "complex"), "D": (16, 0, "complex"), "Zf": (8, 0, "complex"), "Zd": (16, 0, "complex"),
}
_WHITESPACE = " \t\n\r\x0b\x0c"                # Py_ISSPACE


class _Code:
    """A formatcode: where an item (or a run of them) sits, how big each is, how many, and its table entry."""

    __slots__ = ("code", "kind", "offset", "repeat", "size")

    def __init__(self, code: str, kind: str, offset: int, size: int, repeat: int) -> None:
        self.code = code
        self.kind = kind
        self.offset = offset
        self.size = size
        self.repeat = repeat


def _prepare(fmt: str) -> tuple[list[_Code], int, int, bool]:   # prepare_s: the codes, the size, the item count, little-endian
    if not str.isascii(fmt):
        raise ValueError("non-ASCII character in struct format")
    if "\x00" in fmt:
        raise error("embedded null character")
    table = _NATIVE
    little = True
    start = 0
    if fmt[:1] == "<":
        table, start = _STANDARD, 1
    elif fmt[:1] in (">", "!"):
        table, little, start = _STANDARD, False, 1
    elif fmt[:1] == "=":
        table, start = _STANDARD, 1
    elif fmt[:1] == "@":
        start = 1
    codes: list[_Code] = []
    size = 0
    length = 0
    i = start
    n = len(fmt)
    while i < n:
        c = fmt[i]
        i += 1
        if c in _WHITESPACE:
            continue
        if "0" <= c <= "9":
            num = ord(c) - 48
            while i < n and "0" <= fmt[i] <= "9":
                if num >= _SSIZE_MAX // 10 and (num > _SSIZE_MAX // 10 or ord(fmt[i]) - 48 > _SSIZE_MAX % 10):
                    raise error("total struct size too long")
                num = num * 10 + ord(fmt[i]) - 48
                i += 1
            if i >= n:
                raise error("repeat count given without format specifier")
            c = fmt[i]
            i += 1
        else:
            num = 1
        code = c
        if c == "Z" and i < n and fmt[i] in "fd":         # the two-character codes
            code = c + fmt[i]
            i += 1
        entry = table.get(code)
        if entry is None:
            raise error("bad char in struct format")
        itemsize, alignment, kind = entry
        if kind in ("bytes", "pascal"):
            if length == _SSIZE_MAX:
                raise error("total struct size too long")
            length += 1
        elif kind != "pad":
            if num > _SSIZE_MAX - length:
                raise error("total struct size too long")
            length += num
        if alignment and size > 0:                       # align
            extra = (alignment - 1) - (size - 1) % alignment
            if extra > _SSIZE_MAX - size:
                raise error("total struct size too long")
            size += extra
        if num > (_SSIZE_MAX - size) // itemsize:
            raise error("total struct size too long")
        if kind in ("bytes", "pascal"):
            codes.append(_Code(code, kind, size, num, 1))
            size += num
        elif kind == "pad":
            size += num
        elif num:
            codes.append(_Code(code, kind, size, itemsize, num))
            size += itemsize * num
    return codes, size, length, little


# ---- one item each way ----------------------------------------------------------------------------------------------------

def _range_error(code: str, size: int, unsigned: bool) -> error:   # _range_error
    largest = (1 << (8 * size)) - 1
    if unsigned:
        return error("'" + code + "' format requires 0 <= number <= " + str(largest))
    half = largest >> 1
    return error("'" + code + "' format requires " + str(~half) + " <= number <= " + str(half))


def _get_pylong(value: object) -> int:           # get_pylong
    if issubclass(type(value), int):
        return int.__index__(value)  # type: ignore[arg-type]
    if _has_slot(value, "__index__"):
        return _index(value)
    raise error("required argument is not an integer")


def _pack_item(code: str, kind: str, size: int, value: object, little: bool) -> bytes:
    if kind == "int":
        n = _get_pylong(value)
        if n < -(1 << (8 * size - 1)) or n >= (1 << (8 * size - 1)):
            raise _range_error(code, size, False)
        return int.to_bytes(n, size, "little" if little else "big", signed=True)
    if kind == "uint":
        n = _get_pylong(value)
        if n < 0 or n >= (1 << (8 * size)):
            raise _range_error(code, size, True)
        return int.to_bytes(n, size, "little" if little else "big")
    if kind == "pointer":                        # np_void_p: PyLong_AsVoidPtr, negative through a long
        n = _get_pylong(value)
        if n < -(1 << 63) or n >= (1 << 64):
            raise error("int too large to convert")
        return int.to_bytes(n & ((1 << 64) - 1), 8, "little")
    if kind == "bool":
        return b"\x01" if value else b"\x00"
    if kind == "char":
        if not issubclass(type(value), bytes) or bytes.__len__(value) != 1:  # type: ignore[arg-type]
            raise error("char format requires a bytes object of length 1")
        return _buffer_bytes(value)
    failed = False                               # the C sets its error over the pending one: raised outside the handler, so that no __context__ of that one shows
    if kind == "float":
        try:
            x = _as_double(value)
        except BaseException:  # noqa: BLE001  # PyFloat_AsDouble failed, whatever with (RL-457)
            failed = True
        if failed:
            raise error("required argument is not a float")
        return _float_pack(x, size, little)
    try:                                         # complex
        real, imag = _as_c_complex(value)
    except BaseException:  # noqa: BLE001
        failed = True
    if failed:
        raise error("required argument is not a complex")
    # np_float_complex casts, an infinity past float's range and no NaN fix; init_endian_tables puts it in the little-endian
    # (and so the '=') table too, where the sizes agree, so only '>' and '!' pack through PyFloat_Pack4
    half = size // 2
    return _float_pack(real, half, little, little) + _float_pack(imag, half, little, little)


def _unpack_item(kind: str, data: bytes, little: bool) -> object:
    if kind == "int":
        return int.from_bytes(data, "little" if little else "big", signed=True)
    if kind in ("uint", "pointer"):
        return int.from_bytes(data, "little" if little else "big")
    if kind == "bool":
        return data[0] != 0
    if kind == "char":
        return data
    if kind == "float":
        return _float_unpack(data, little)
    half = len(data) // 2                        # complex: nu_float_complex's (double)float for '<' and '=', PyFloat_Unpack4 for '>'
    return complex(_float_unpack(data[:half], little, little), _float_unpack(data[half:], little, little))


def _pack_into(codes: list[_Code], size: int, length: int, little: bool, values: tuple[object, ...], out: bytearray, start: int) -> None:
    """s_pack_internal: the values into out at start, the struct's size of it zeroed first."""
    # the writes are the buffer's own (memset, memcpy): nothing of a bytearray subclass's is called (RL-698)
    bytearray.__setitem__(out, slice(start, start + size), bytes(size))
    i = 0
    for code in codes:
        at = start + code.offset
        for _ in range(code.repeat):
            v = values[i]
            i += 1
            if code.kind == "bytes":
                if not issubclass(type(v), (bytes, bytearray)):
                    raise error("argument for 's' must be a bytes object")
                data = _buffer_bytes(v)          # PyBytes_AS_STRING or PyByteArray_AS_STRING, and its size
                n = min(bytes.__len__(data), code.size)
                if n > 0:
                    bytearray.__setitem__(out, slice(at, at + n), data[:n])
            elif code.kind == "pascal":
                if not issubclass(type(v), (bytes, bytearray)):
                    raise error("argument for 'p' must be a bytes object")
                data = _buffer_bytes(v)
                n = bytes.__len__(data)
                if code.size == 0:
                    n = 0
                elif n > code.size - 1:
                    n = code.size - 1
                if n > 0:
                    bytearray.__setitem__(out, slice(at + 1, at + 1 + n), data[:n])
                if n > 255:
                    n = 255
                if n > 0:
                    bytearray.__setitem__(out, at, n)
            else:
                too_large = False
                try:
                    bytearray.__setitem__(out, slice(at, at + code.size), _pack_item(code.code, code.kind, code.size, v, little))
                except OverflowError:
                    if not issubclass(type(v), int):
                        raise
                    too_large = True             # PyErr_SetString over the pending error: raised outside the handler
                if too_large:
                    raise error("int too large to convert")
            at += code.size


def _unpack_from(codes: list[_Code], length: int, little: bool, data: bytes, start: int) -> tuple[object, ...]:   # s_unpack_internal
    out: list[object] = []
    for code in codes:
        at = start + code.offset
        for _ in range(code.repeat):
            if code.kind == "bytes":
                out.append(data[at:at + code.size])
            elif code.kind == "pascal":
                if code.size == 0:
                    n = 0
                else:
                    n = data[at]
                    if n >= code.size:
                        n = code.size - 1
                out.append(data[at + 1:at + 1 + n])
            else:
                out.append(_unpack_item(code.kind, data[at:at + code.size], little))
            at += code.size
    return tuple(out)


# ---- Struct ------------------------------------------------------------------------------------------------------------------

def _format_text(format: object) -> str:         # set_format: a str, or bytes decoded as ASCII with surrogateescape
    if issubclass(type(format), str):
        return str.__str__(format)  # type: ignore[arg-type]  # the text itself, whatever a subclass's __str__ says
    if issubclass(type(format), bytes):
        return bytes.decode(format, "ascii", "surrogateescape")  # type: ignore[arg-type]
    raise TypeError("Struct() argument 1 must be a str or bytes object, not " + _tp_name(format))


class Struct:
    """Struct(format) --> compiled struct object"""

    __slots__ = ("__weakref__", "_codes", "_length", "_little", "format", "size")
    __readonly__ = ("format", "size")            # s_members' Py_READONLY

    def __new__(cls, *args: object, **kwds: object) -> Struct:
        if cls is not Struct:
            _bella_refuse("subclassing _struct.Struct (its __new__ and __init__ warn about each other)")
        if len(args) == 1 and not kwds:
            format = args[0]
        elif not args and len(kwds) == 1 and "format" in kwds:
            format = kwds["format"]
        else:
            format = _unpack_args("Struct", args, kwds, ("format",), 1, 1)[0]
        self: Struct = _bella_new_instance(cls)
        text = _format_text(format)
        codes, size, length, little = _prepare(text)
        _bella_state_set(self, "format", text)
        _bella_state_set(self, "_codes", codes)
        _bella_state_set(self, "size", size)
        _bella_state_set(self, "_length", length)
        _bella_state_set(self, "_little", little)
        return self

    def __init__(self, *args: object, **kwds: object) -> None:   # s_init: __new__ did the work; a second format would warn
        if args or kwds:
            format = args[0] if len(args) == 1 and not kwds else _unpack_args("Struct", args, kwds, ("format",), 1, 1)[0]
            format = _own_data(format)           # the format's characters: its class's __eq__ is not asked (RL-679)
            same = (issubclass(type(format), str) and str.isascii(format) and format == self.format) or (
                issubclass(type(format), bytes) and bytes.decode(format, "ascii", "surrogateescape") == self.format)
            if not same:
                _bella_refuse("Struct.__init__() with another format than __new__()'s (a FutureWarning in 3.15)")

    def __setattr__(self, name: str, value: object) -> None:     # tp_setattro is PyObject_GenericSetAttr: the two members
        object.__setattr__(self, name, value)                     # say themselves that they are read-only

    def __delattr__(self, name: str) -> None:
        object.__delattr__(self, name)

    def __repr__(self) -> str:
        return _type_name(self) + "(" + _repr_text(self.format) + ")"

    def __sizeof__(self) -> int:
        return 64 + 32 * (len(self._codes) + 1)

    def pack(self, *values: object, **kwds: object) -> bytes:
        """Pack values and return the packed bytes.

Return a bytes object containing the provided values packed
according to the struct format string.  See help(struct) for more on
format strings."""
        if kwds:
            raise TypeError("Struct.pack() takes no keyword arguments")
        return _pack_values(self, "pack", values)

    def pack_into(self, *args: object, **kwds: object) -> None:
        """Pack values and write the packed bytes into the buffer.

Pack the provided values according to the struct format string
and write the packed bytes into the writable buffer starting at
offset.  Note that the offset is a required argument.  A negative
offset counts from the end of the buffer.  See help(struct) for
more on format strings."""
        if kwds:
            raise TypeError("Struct.pack_into() takes no keyword arguments")
        if len(args) < 2:
            raise TypeError("pack_into expected at least 2 arguments, got " + str(len(args)))
        _pack_into_buffer(self, "pack_into", 1, args[0], args[1], args[2:])

    def unpack(self, *args: object, **kwds: object) -> tuple[object, ...]:
        """Return a tuple containing unpacked values.

Unpack according to the struct format string.  The buffer's
size in bytes must be the struct size.  See help(struct) for more on
format strings."""
        if kwds:
            raise TypeError("Struct.unpack() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("Struct.unpack() takes exactly one argument (" + str(len(args)) + " given)")
        return _unpack_buffer(self, args[0])

    def unpack_from(self, *args: object, **kwds: object) -> tuple[object, ...]:
        """Return a tuple containing unpacked values.

Values are unpacked according to the struct format string.  The
buffer's size in bytes, starting at position offset, must be at
least the struct size.  A negative offset counts from the end of
the buffer.  See help(struct) for more on format strings."""
        buffer, offset = _unpack_args("unpack_from", args, kwds, ("buffer", "offset"), 1, 2)
        return _unpack_from_buffer(self, buffer, 0 if offset is _ABSENT else offset)

    def iter_unpack(self, *args: object, **kwds: object) -> unpack_iterator:
        """Return an iterator yielding tuples.

Tuples are unpacked from the given bytes source, like a repeated
invocation of unpack_from().  Requires that the bytes length be
a multiple of the struct size."""
        if kwds:
            raise TypeError("Struct.iter_unpack() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("Struct.iter_unpack() takes exactly one argument (" + str(len(args)) + " given)")
        return _iter_unpack(self, args[0])


Struct.__module__ = "_struct"


class unpack_iterator:  # noqa: N801           # _struct.unpack_iterator (Py_TPFLAGS_DISALLOW_INSTANTIATION: made by iter_unpack alone)
    # the C holds the Struct and a Py_buffer, which keeps the object the bytes came from alive until the iterator is
    # exhausted or goes; it lets go of the Struct first (review A36's saved outputs, RL-840)
    __slots__ = ("_data", "_index", "_struct", "_source")

    def __iter__(self) -> unpack_iterator:
        return self

    def __next__(self) -> tuple[object, ...]:
        s = self._struct
        if s is None:
            raise StopIteration
        if self._index >= len(self._data):
            self._struct = None
            self._data = b""
            self._source = None                  # PyBuffer_Release
            raise StopIteration
        result = _unpack_from(s._codes, s._length, s._little, self._data, self._index)
        self._index += s.size
        return result

    def __length_hint__(self) -> int:
        if self._struct is None:
            return 0
        return (len(self._data) - self._index) // self._struct.size


unpack_iterator.__module__ = "_struct"


def _pack_values(s: Struct, name: str, values: tuple[object, ...]) -> bytes:   # Struct_pack_impl
    if len(values) != s._length:
        raise error(name + " expected " + str(s._length) + " items for packing (got " + str(len(values)) + ")")
    out = bytearray(s.size)
    _pack_into(s._codes, s.size, s._length, s._little, values, out, 0)
    return bytes(out)


def _pack_into_buffer(s: Struct, name: str, position: int, buffer: object, offset_arg: object, values: tuple[object, ...]) -> None:
    """Struct_pack_into_impl; position is the buffer's place among the arguments (1 for the method, 2 for the function)."""
    target = _rw_buffer(buffer, name, position)
    offset = _ssize(offset_arg)
    if len(values) != s._length:
        raise error(name + " expected " + str(s._length) + " items for packing (got " + str(len(values)) + ")")
    buflen = bytearray.__len__(target)           # the buffer's length, whatever a subclass's __len__ says
    if offset < 0:
        if offset + s.size > 0:
            raise error("no space to pack " + str(s.size) + " bytes at offset " + str(offset))
        if offset + buflen < 0:
            raise error("offset " + str(offset) + " out of range for " + str(buflen) + "-byte buffer")
        offset += buflen
    if buflen - offset < s.size:
        raise error(name + " requires a buffer of at least " + str(s.size + offset) + " bytes for packing " + str(s.size)
                    + " bytes at offset " + str(offset) + " (actual buffer size is " + str(buflen) + ")")
    _pack_into(s._codes, s.size, s._length, s._little, values, target, offset)


def _unpack_buffer(s: Struct, buffer: object) -> tuple[object, ...]:   # Struct_unpack_impl
    data = _buffer(buffer)
    if len(data) != s.size:
        raise error("unpack requires a buffer of " + str(s.size) + " bytes")
    return _unpack_from(s._codes, s._length, s._little, data, 0)


def _unpack_from_buffer(s: Struct, buffer: object, offset_arg: object) -> tuple[object, ...]:   # Struct_unpack_from_impl
    data = _buffer(buffer)
    offset = _ssize(offset_arg)
    if offset < 0:
        if offset + s.size > 0:
            raise error("not enough data to unpack " + str(s.size) + " bytes at offset " + str(offset))
        if offset + len(data) < 0:
            raise error("offset " + str(offset) + " out of range for " + str(len(data)) + "-byte buffer")
        offset += len(data)
    if len(data) - offset < s.size:
        raise error("unpack_from requires a buffer of at least " + str(s.size + offset) + " bytes for unpacking " + str(s.size)
                    + " bytes at offset " + str(offset) + " (actual buffer size is " + str(len(data)) + ")")
    return _unpack_from(s._codes, s._length, s._little, data, offset)


def _iter_unpack(s: Struct, buffer: object) -> unpack_iterator:   # Struct_iter_unpack_impl
    if s.size == 0:
        raise error("cannot iteratively unpack with a struct of length 0")
    data = _buffer(buffer)
    if len(data) % s.size != 0:
        raise error("iterative unpacking requires a buffer of a multiple of " + str(s.size) + " bytes")
    it: unpack_iterator = _bella_new_instance(unpack_iterator)
    it._struct = s
    it._data = data
    it._source = buffer
    it._index = 0
    return it


# ---- the module's functions, over the cache (cache_struct_converter) --------------------------------------------------------

_MAXCACHE = 100
_cache: dict[object, Struct] = {}


def _cached(format: object) -> Struct:
    """cache_struct_converter: the cache is a dict whose key is the format object itself, so a format's own __hash__ and
    __eq__ are asked (and an unhashable one is a TypeError), and the object is held until the cache is cleared; for a bytes
    format the key is its text, decoded from the bytes themselves (RL-664)."""
    key = bytes.decode(format, "ascii", "surrogateescape") if issubclass(type(format), bytes) else format  # type: ignore[arg-type]
    s = _cache.get(key)
    if s is None:
        s = Struct(key)
        if len(_cache) >= _MAXCACHE:
            _cache.clear()
        try:
            _cache[key] = s
        except BaseException:                    # "if (PyDict_SetItem(state->cache, key, s_object) == -1) PyErr_Clear();"
            pass
    return s


def _clearcache(*args: object, **kwds: object) -> None:
    """Clear the internal cache."""
    if kwds:
        raise TypeError("_struct._clearcache() takes no keyword arguments")
    if args:
        raise TypeError("_struct._clearcache() takes no arguments (" + str(len(args)) + " given)")
    _cache.clear()


def calcsize(*args: object, **kwds: object) -> int:
    """Return size in bytes of the struct described by the format string."""
    if kwds:
        raise TypeError("_struct.calcsize() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("_struct.calcsize() takes exactly one argument (" + str(len(args)) + " given)")
    return _cached(args[0]).size


def pack(*args: object, **kwds: object) -> bytes:
    """pack(format, v1, v2, ...) -> bytes

Return a bytes object containing the values v1, v2, ... packed according
to the format string.  See help(struct) for more on format strings."""
    if kwds:
        raise TypeError("pack() takes no keyword arguments")
    if len(args) < 1:
        raise TypeError("pack expected at least 1 argument, got 0")
    return _pack_values(_cached(args[0]), "pack", args[1:])


def pack_into(*args: object, **kwds: object) -> None:
    """pack_into(format, buffer, offset, v1, v2, ...)

Pack the values v1, v2, ... according to the format string and write
the packed bytes into the writable buffer buf starting at offset.  Note
that the offset is a required argument.  See help(struct) for more
on format strings."""
    if kwds:
        raise TypeError("pack_into() takes no keyword arguments")
    if len(args) < 3:
        raise TypeError("pack_into expected at least 3 arguments, got " + str(len(args)))
    _pack_into_buffer(_cached(args[0]), "pack_into", 2, args[1], args[2], args[3:])


def unpack(*args: object, **kwds: object) -> tuple[object, ...]:
    """Return a tuple containing values unpacked according to the format string.

The buffer's size in bytes must be calcsize(format).

See help(struct) for more on format strings."""
    _positional("unpack", args, kwds, 2, 2)
    return _unpack_buffer(_cached(args[0]), args[1])


def unpack_from(*args: object, **kwds: object) -> tuple[object, ...]:
    """Return a tuple containing values unpacked according to the format string.

The buffer's size, minus offset, must be at least calcsize(format).

See help(struct) for more on format strings."""
    format, buffer, offset = _unpack_args("unpack_from", args, kwds, ("", "buffer", "offset"), 2, 3)
    return _unpack_from_buffer(_cached(format), buffer, 0 if offset is _ABSENT else offset)


def iter_unpack(*args: object, **kwds: object) -> unpack_iterator:
    """Return an iterator yielding tuples unpacked from the given bytes.

The bytes are unpacked according to the format string, like
a repeated invocation of unpack_from().

Requires that the bytes length be a multiple of the format struct size."""
    _positional("iter_unpack", args, kwds, 2, 2)
    return _iter_unpack(_cached(args[0]), args[1])
