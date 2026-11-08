"""zlib, in Python (Modules/zlibmodule.c) over zlib 1.3.2 itself (runtime/src/zlib.cpp, runtime/vendor/zlib-1.3.2; licence entry
L-02): compress and decompress, compressobj and the Compress type (compress, flush, copy), decompressobj and the Decompress type
(decompress with max_length, flush, copy, unused_data, unconsumed_tail, eof), _ZlibDecompressor (3.12's buffered one: needs_input,
eof, unused_data), adler32, crc32 and their combines, the constants, error and the two versions. The library's calls run in C++
on stream handles; which calls, when a stream ends, what is saved and every message are the C module's, here."""

__all__ = ["DEFLATED", "DEF_BUF_SIZE", "DEF_MEM_LEVEL", "MAX_WBITS", "ZLIB_RUNTIME_VERSION", "ZLIB_VERSION", "Z_BEST_COMPRESSION",
           "Z_BEST_SPEED", "Z_BLOCK", "Z_DEFAULT_COMPRESSION", "Z_DEFAULT_STRATEGY", "Z_FILTERED", "Z_FINISH", "Z_FIXED", "Z_FULL_FLUSH",
           "Z_HUFFMAN_ONLY", "Z_NO_COMPRESSION", "Z_NO_FLUSH", "Z_PARTIAL_FLUSH", "Z_RLE", "Z_SYNC_FLUSH", "Z_TREES", "_ZlibDecompressor",
           "adler32", "adler32_combine", "compress", "compressobj", "crc32", "crc32_combine", "decompress", "decompressobj", "error"]

__name__ = "zlib"

__hidden_classes__ = ["Compress", "Decompress"]   # zlib.Compress and zlib.Decompress: types of the module that are no names of it

try:
    _bella_new_instance                          # noqa: B018  # tp_alloc: this type's __new__ makes its instance
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _tp_name                                     # noqa: B018  # Py_TYPE(o)->tp_name
    _number_index                                # noqa: B018  # PyNumber_Index
    _zlib                                        # noqa: B018  # zlib.cpp: the library's calls by name
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_new_instance = object.__new__
    _bella_refuse: Callable[..., Any] = _missing
    _zlib: Callable[..., Any] = _missing

    def _tp_name(o: object) -> str:
        return type(o).__name__

    def _number_index(o: object) -> int:
        import operator
        return operator.index(o)


DEFLATED = 8
DEF_BUF_SIZE = 16384
DEF_MEM_LEVEL = 8
MAX_WBITS = 15
Z_BEST_COMPRESSION = 9
Z_BEST_SPEED = 1
Z_BLOCK = 5
Z_DEFAULT_COMPRESSION = -1
Z_DEFAULT_STRATEGY = 0
Z_FILTERED = 1
Z_FINISH = 4
Z_FIXED = 4
Z_FULL_FLUSH = 3
Z_HUFFMAN_ONLY = 2
Z_NO_COMPRESSION = 0
Z_NO_FLUSH = 0
Z_PARTIAL_FLUSH = 1
Z_RLE = 3
Z_SYNC_FLUSH = 2
Z_TREES = 6
ZLIB_VERSION, ZLIB_RUNTIME_VERSION = _zlib("version")

_Z_OK = 0
_Z_STREAM_END = 1
_Z_NEED_DICT = 2
_Z_STREAM_ERROR = -2
_Z_DATA_ERROR = -3
_Z_MEM_ERROR = -4
_Z_BUF_ERROR = -5
_Z_VERSION_ERROR = -6
_ABSENT: object = object()
_MAXSIZE = 2**63 - 1
_UINT_MAX = 2**32 - 1
_DEF_MAX_INITIAL_BUF_SIZE = 16 * 1024 * 1024


class error(Exception):  # noqa: N801
    pass


error.__module__ = "zlib"


def _zlib_error(err: int, zmsg: object, msg: str) -> error:   # zlib_error
    text: object = "library version mismatch" if err == _Z_VERSION_ERROR else zmsg
    if text is None:
        text = {_Z_BUF_ERROR: "incomplete or truncated stream", _Z_STREAM_ERROR: "inconsistent stream state", _Z_DATA_ERROR: "invalid input data"}.get(err)
    if text is None:
        return error("Error " + str(err) + " " + msg)
    return error("Error " + str(err) + " " + msg + ": " + str(text))


def _buffer(value: object) -> bytes:             # Py_buffer: bytes, bytearray; the rest stops by name or is no buffer
    if issubclass(type(value), (bytes, bytearray)):
        return bytes(value)  # type: ignore[arg-type]
    if hasattr(type(value), "__buffer__"):
        _bella_refuse("[P2+] the buffer protocol (__buffer__)")
    raise TypeError("a bytes-like object is required, not '" + _tp_name(value) + "'")


def _int(value: object) -> int:                  # the clinic's int: PyLong_AsInt after __index__
    n = _number_index(value)
    if n > 2**31 - 1 or n < -(2**31):
        raise OverflowError("Python int too large to convert to C int")
    return n


def _ssize(value: object, name: str, allow_negative: bool) -> int:   # Py_ssize_t, allow_negative=False
    n = _number_index(value)
    if n > _MAXSIZE or n < -_MAXSIZE - 1:
        raise OverflowError("Python int too large to convert to C ssize_t")
    if n < 0 and not allow_negative:
        raise ValueError(name + " cannot be negative")
    return n


def _unsigned(value: object, name: str) -> int:   # unsigned_int(bitwise=True): a value out of range warns in 3.15, then wraps
    if not issubclass(type(value), int):
        if not hasattr(type(value), "__index__"):
            raise TypeError("'" + _tp_name(value) + "' object cannot be interpreted as an integer")
    n = _number_index(value)
    if n < 0 or n > _UINT_MAX:
        _bella_refuse("zlib." + name + " with a start value outside an unsigned 32-bit int (3.15 warns of its removal)")
    return n


def _arguments(fname: str, names: tuple[str, ...], maxpos: int, minpos: int, args: tuple[object, ...], kwds: dict[str, object]) -> list[object]:
    """_PyArg_UnpackKeywords: `names` in order, the first `maxpos` positional, the first `minpos` required."""
    nargs = len(args)
    if nargs + len(kwds) > len(names):
        raise TypeError(fname + "() takes at most " + str(len(names)) + " argument" + ("" if len(names) == 1 else "s") + " (" + str(nargs + len(kwds)) + " given)")
    if nargs > maxpos:
        raise TypeError(fname + "() takes at most " + str(maxpos) + " positional argument" + ("" if maxpos == 1 else "s") + " (" + str(nargs) + " given)")
    values: list[object] = [*args, *[_ABSENT] * (len(names) - nargs)]
    for keyword, value in kwds.items():
        if keyword in names:
            at = names.index(keyword)
            if at < nargs:
                raise TypeError("argument for " + fname + "() given by name ('" + keyword + "') and position (" + str(at + 1) + ")")
            values[at] = value
    for at in range(minpos):
        if values[at] is _ABSENT:
            if not names[at]:                    # positional-only: counted, "exactly" when nothing more may follow
                raise TypeError(fname + "() takes " + ("exactly " if minpos == maxpos else "at least ") + str(minpos) + " positional argument" + ("" if minpos == 1 else "s") + " (" + str(nargs) + " given)")
            raise TypeError(fname + "() missing required argument '" + names[at] + "' (pos " + str(at + 1) + ")")
    for keyword in kwds:
        if keyword not in names or not keyword:
            raise TypeError(fname + "() got an unexpected keyword argument '" + keyword + "'")
    return values


# ---- the one-shot functions ----------------------------------------------------------------------------------------------------

def compress(*args: object, **kwds: object) -> bytes:
    """Returns a bytes object containing compressed data.

  data
    Binary data to be compressed.
  level
    Compression level, in 0-9 or -1.
  wbits
    The window buffer size and container format."""
    given = _arguments("compress", ("", "level", "wbits"), 3, 1, args, kwds)
    data = _buffer(given[0])
    level = Z_DEFAULT_COMPRESSION if given[1] is _ABSENT else _int(given[1])
    wbits = MAX_WBITS if given[2] is _ABSENT else _int(given[2])
    err, handle, zmsg = _zlib("deflate_init", level, DEFLATED, wbits, DEF_MEM_LEVEL, Z_DEFAULT_STRATEGY)
    if err == _Z_MEM_ERROR:
        raise MemoryError("Out of memory while compressing data")
    if err == _Z_STREAM_ERROR:
        raise error("Bad compression level")
    if err != _Z_OK:
        raise _zlib_error(err, zmsg, "while compressing data")
    try:
        err, out, zmsg = _zlib("deflate", handle, data, Z_FINISH)
        if err == _Z_STREAM_ERROR:
            raise _zlib_error(err, zmsg, "while compressing data")
        err = _zlib("end", handle)
        if err != _Z_OK:
            raise _zlib_error(err, None, "while finishing compression")
        return out  # type: ignore[no-any-return]
    finally:
        _zlib("free", handle)


def decompress(*args: object, **kwds: object) -> bytes:
    """Returns a bytes object containing the uncompressed data.

  data
    Compressed data.
  wbits
    The window buffer size and container format.
  bufsize
    The initial output buffer size."""
    given = _arguments("decompress", ("", "wbits", "bufsize"), 3, 1, args, kwds)
    data = _buffer(given[0])
    wbits = MAX_WBITS if given[1] is _ABSENT else _int(given[1])
    bufsize = DEF_BUF_SIZE if given[2] is _ABSENT else _ssize(given[2], "bufsize", False)
    if bufsize == 0:
        bufsize = 1
    err, handle, zmsg = _zlib("inflate_init", wbits)
    if err == _Z_MEM_ERROR:
        raise MemoryError("Out of memory while decompressing data")
    if err != _Z_OK:
        raise _zlib_error(err, zmsg, "while preparing to decompress data")
    try:
        err, out, _consumed, zmsg, _context = _zlib("inflate", handle, data, -1, bufsize, Z_FINISH, None)
        if err == _Z_MEM_ERROR:
            raise MemoryError("Out of memory while decompressing data")
        if err != _Z_STREAM_END:
            raise _zlib_error(err, zmsg, "while decompressing data")
        err = _zlib("end", handle)
        if err != _Z_OK:
            raise _zlib_error(err, None, "while finishing decompression")
        return out  # type: ignore[no-any-return]
    finally:
        _zlib("free", handle)


# ---- Compress and Decompress -----------------------------------------------------------------------------------------------------

def _no_args(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:   # the clinic's METH_METHOD with no parameters
    if args or kwds:
        raise TypeError(name + "() takes no arguments")


class Compress:
    __slots__ = ("_handle", "_initialised")

    def __del__(self) -> None:
        if self._handle:
            _zlib("free", self._handle)
            self._handle = 0

    def compress(self, *args: object, **kwds: object) -> bytes:
        """Returns a bytes object containing compressed data.

  data
    Binary data to be compressed.

After calling this function, some of the input data may still
be stored in internal buffers for later processing.
Call the flush() method to clear these buffers."""
        data = _buffer(_arguments("compress", ("",), 1, 1, args, kwds)[0])
        err, out, zmsg = _zlib("deflate", self._handle, data, Z_NO_FLUSH)
        if err == _Z_STREAM_ERROR:
            raise _zlib_error(err, zmsg, "while compressing data")
        return out  # type: ignore[no-any-return]

    def flush(self, *args: object, **kwds: object) -> bytes:
        given = _arguments("flush", ("",), 1, 0, args, kwds)
        mode = Z_FINISH if given[0] is _ABSENT else _int(given[0])
        if mode == Z_NO_FLUSH:
            return b""
        err, out, zmsg = _zlib("deflate", self._handle, b"", mode)
        if err == _Z_STREAM_ERROR:
            raise _zlib_error(err, zmsg, "while flushing")
        if err == _Z_STREAM_END and mode == Z_FINISH:
            err = _zlib("end", self._handle)
            if err != _Z_OK:
                raise _zlib_error(err, None, "while finishing compression")
            self._initialised = False
        elif err != _Z_OK and err != _Z_BUF_ERROR:
            raise _zlib_error(err, zmsg, "while flushing")
        return out  # type: ignore[no-any-return]

    def copy(self, *args: object, **kwds: object) -> Compress:
        """Return a copy of the compression object."""
        _no_args("copy", args, kwds)
        return _copy_compress(self)

    def __copy__(self, *args: object, **kwds: object) -> Compress:
        _no_args("__copy__", args, kwds)
        return _copy_compress(self)

    def __deepcopy__(self, *args: object, **kwds: object) -> Compress:
        _arguments("__deepcopy__", ("",), 1, 1, args, kwds)
        return _copy_compress(self)


Compress.__module__ = "zlib"
# a docstring whose lines are all indented would lose that indentation to the compiler's cleaning (3.13+); the C's keeps it
Compress.flush.__doc__ = ("Return a bytes object containing any remaining compressed data.\n\n  mode\n    One of the constants Z_SYNC_FLUSH, "
                          "Z_FULL_FLUSH, Z_FINISH.\n    If mode == Z_FINISH, the compressor object can no longer be\n    used after calling the "
                          "flush() method.  Otherwise, more data\n    can still be compressed.")


def _copy_compress(self: Compress) -> Compress:  # zlib_Compress_copy_impl
    if not self._initialised:
        raise ValueError("Inconsistent stream state")
    err, handle = _zlib("copy", self._handle)
    if err == _Z_STREAM_ERROR:
        raise ValueError("Inconsistent stream state")
    if err == _Z_MEM_ERROR:
        raise MemoryError("Can't allocate memory for compression object")
    if err != _Z_OK:
        raise _zlib_error(err, None, "while copying compression object")
    other: Compress = _bella_new_instance(Compress)
    other._handle = handle
    other._initialised = True
    return other


def compressobj(*args: object, **kwds: object) -> Compress:
    """Return a compressor object.

  level
    The compression level (an integer in the range 0-9 or -1; default is
    currently equivalent to 6).  Higher compression levels are slower,
    but produce smaller results.
  method
    The compression algorithm.  If given, this must be DEFLATED.
  wbits
    +9 to +15: The base-two logarithm of the window size.  Include a zlib
        container.
    -9 to -15: Generate a raw stream.
    +25 to +31: Include a gzip container.
  memLevel
    Controls the amount of memory used for internal compression state.
    Valid values range from 1 to 9.  Higher values result in higher memory
    usage, faster compression, and smaller output.
  strategy
    Used to tune the compression algorithm.  Possible values are
    Z_DEFAULT_STRATEGY, Z_FILTERED, and Z_HUFFMAN_ONLY.
  zdict
    The predefined compression dictionary - a sequence of bytes
    containing subsequences that are likely to occur in the input data."""
    given = _arguments("compressobj", ("level", "method", "wbits", "memLevel", "strategy", "zdict"), 6, 0, args, kwds)
    level = Z_DEFAULT_COMPRESSION if given[0] is _ABSENT else _int(given[0])
    method = DEFLATED if given[1] is _ABSENT else _int(given[1])
    wbits = MAX_WBITS if given[2] is _ABSENT else _int(given[2])
    mem_level = DEF_MEM_LEVEL if given[3] is _ABSENT else _int(given[3])
    strategy = Z_DEFAULT_STRATEGY if given[4] is _ABSENT else _int(given[4])
    zdict = None if given[5] is _ABSENT else _buffer(given[5])
    if zdict is not None and len(zdict) > _UINT_MAX:
        raise OverflowError("zdict length does not fit in an unsigned int")
    err, handle, zmsg = _zlib("deflate_init", level, method, wbits, mem_level, strategy)
    if err == _Z_MEM_ERROR:
        raise MemoryError("Can't allocate memory for compression object")
    if err == _Z_STREAM_ERROR:
        raise ValueError("Invalid initialization option")
    if err != _Z_OK:
        raise _zlib_error(err, zmsg, "while creating compression object")
    self: Compress = _bella_new_instance(Compress)
    self._handle = handle
    self._initialised = True
    if zdict is not None:
        err = _zlib("deflate_setdict", handle, zdict)
        if err == _Z_STREAM_ERROR:
            raise ValueError("Invalid dictionary")
        if err != _Z_OK:
            raise ValueError("deflateSetDictionary()")
    return self


class Decompress:
    __slots__ = ("_eof", "_handle", "_initialised", "_unconsumed_tail", "_unused_data", "_zdict")

    def __del__(self) -> None:
        if self._handle:
            _zlib("free", self._handle)
            self._handle = 0

    @property
    def unused_data(self) -> bytes:
        return self._unused_data

    @property
    def unconsumed_tail(self) -> bytes:
        return self._unconsumed_tail

    @property
    def eof(self) -> bool:
        return self._eof

    def _save_unconsumed_input(self, data: bytes, consumed: int, err: int) -> None:   # save_unconsumed_input
        if err == _Z_STREAM_END and consumed < len(data):
            self._unused_data += data[consumed:]
            consumed = len(data)
        if consumed < len(data) or self._unconsumed_tail:
            self._unconsumed_tail = data[consumed:]

    def decompress(self, *args: object, **kwds: object) -> bytes:
        """Return a bytes object containing the decompressed version of the data.

  data
    The binary data to decompress.
  max_length
    The maximum allowable length of the decompressed data.
    Unconsumed input data will be stored in
    the unconsumed_tail attribute.

After calling this function, some of the input data may still be stored in
internal buffers for later processing.
Call the flush() method to clear these buffers."""
        given = _arguments("decompress", ("", "max_length"), 2, 1, args, kwds)
        data = _buffer(given[0])
        max_length = 0 if given[1] is _ABSENT else _ssize(given[1], "max_length", False)
        if max_length == 0:
            max_length = -1
        err, out, consumed, zmsg, context = _zlib("inflate", self._handle, data, max_length, -1, Z_SYNC_FLUSH, self._zdict)
        if context == "setdict":
            raise _zlib_error(err, zmsg, "while setting zdict")
        self._save_unconsumed_input(data, consumed, err)
        if err == _Z_STREAM_END:
            self._eof = True                     # inflateEnd waits for flush(), as the C keeps it
        elif err != _Z_OK and err != _Z_BUF_ERROR:
            raise _zlib_error(err, zmsg, "while decompressing data")
        return out  # type: ignore[no-any-return]

    def flush(self, *args: object, **kwds: object) -> bytes:
        given = _arguments("flush", ("",), 1, 0, args, kwds)
        length = DEF_BUF_SIZE if given[0] is _ABSENT else _ssize(given[0], "length", True)
        if length <= 0:
            raise ValueError("length must be greater than zero")
        if not self._initialised:
            return b""
        data = self._unconsumed_tail
        err, out, consumed, zmsg, _context = _zlib("inflate", self._handle, data, -1, length, Z_FINISH, None)
        self._save_unconsumed_input(data, consumed, err)
        if err == _Z_STREAM_END:
            self._eof = True
            self._initialised = False
            err = _zlib("end", self._handle)
            if err != _Z_OK:
                raise _zlib_error(err, None, "while finishing decompression")
        elif err != _Z_OK and err != _Z_BUF_ERROR:
            raise _zlib_error(err, zmsg, "while decompressing data")
        return out  # type: ignore[no-any-return]

    def copy(self, *args: object, **kwds: object) -> Decompress:
        """Return a copy of the decompression object."""
        _no_args("copy", args, kwds)
        return _copy_decompress(self)

    def __copy__(self, *args: object, **kwds: object) -> Decompress:
        _no_args("__copy__", args, kwds)
        return _copy_decompress(self)

    def __deepcopy__(self, *args: object, **kwds: object) -> Decompress:
        _arguments("__deepcopy__", ("",), 1, 1, args, kwds)
        return _copy_decompress(self)


Decompress.__module__ = "zlib"
Decompress.flush.__doc__ = "Return a bytes object containing any remaining decompressed data.\n\n  length\n    the initial size of the output buffer."


def _copy_decompress(self: Decompress) -> Decompress:   # zlib_Decompress_copy_impl
    if not self._initialised:
        raise ValueError("Inconsistent stream state")
    err, handle = _zlib("copy", self._handle)
    if err == _Z_STREAM_ERROR:
        raise ValueError("Inconsistent stream state")
    if err == _Z_MEM_ERROR:
        raise MemoryError("Can't allocate memory for decompression object")
    if err != _Z_OK:
        raise _zlib_error(err, None, "while copying decompression object")
    other: Decompress = _bella_new_instance(Decompress)
    other._handle = handle
    other._initialised = True
    other._unused_data = self._unused_data
    other._unconsumed_tail = self._unconsumed_tail
    other._zdict = self._zdict
    other._eof = self._eof
    return other


def _inflate_zdict(handle: int, zdict: bytes) -> None:   # set_inflate_zdict
    if len(zdict) > _UINT_MAX:
        raise OverflowError("zdict length does not fit in an unsigned int")
    err = _zlib("inflate_setdict", handle, zdict)
    if err != _Z_OK:
        raise _zlib_error(err, None, "while setting zdict")


def decompressobj(*args: object, **kwds: object) -> Decompress:
    """Return a decompressor object.

  wbits
    The window buffer size and container format.
  zdict
    The predefined compression dictionary.  This must be the same
    dictionary as used by the compressor that produced the input data."""
    given = _arguments("decompressobj", ("wbits", "zdict"), 2, 0, args, kwds)
    wbits = MAX_WBITS if given[0] is _ABSENT else _int(given[0])
    zdict: bytes | None = None
    if given[1] is not _ABSENT:
        if not issubclass(type(given[1]), (bytes, bytearray)) and not hasattr(type(given[1]), "__buffer__"):
            raise TypeError("zdict argument must support the buffer protocol")
        zdict = _buffer(given[1])
    err, handle, zmsg = _zlib("inflate_init", wbits)
    if err == _Z_STREAM_ERROR:
        raise ValueError("Invalid initialization option")
    if err == _Z_MEM_ERROR:
        raise MemoryError("Can't allocate memory for decompression object")
    if err != _Z_OK:
        raise _zlib_error(err, zmsg, "while creating decompression object")
    self: Decompress = _bella_new_instance(Decompress)
    self._handle = handle
    self._initialised = True
    self._unused_data = b""
    self._unconsumed_tail = b""
    self._eof = False
    self._zdict = zdict
    if zdict is not None and wbits < 0:
        _inflate_zdict(handle, zdict)
    return self


# ---- _ZlibDecompressor -----------------------------------------------------------------------------------------------------------

class _ZlibDecompressor:
    """Create a decompressor object for decompressing data incrementally.

  zdict
    The predefined compression dictionary. This is a sequence of bytes
    (such as a bytes object) containing subsequences that are expected
    to occur frequently in the data that is to be compressed. Those
    subsequences that are expected to be most common should come at the
    end of the dictionary. This must be the same dictionary as used by the
    compressor that produced the input data."""

    __slots__ = ("_eof", "_handle", "_initialised", "_input", "_needs_input", "_unused_data", "_zdict")

    def __new__(cls, *args: object, **kwds: object) -> _ZlibDecompressor:
        given = _arguments("_ZlibDecompressor", ("wbits", "zdict"), 2, 0, args, kwds)
        wbits = MAX_WBITS if given[0] is _ABSENT else _int(given[0])
        zdict: object = None if given[1] is _ABSENT else given[1]   # any object: read as a buffer only where the C reads it
        err, handle, zmsg = _zlib("inflate_init", wbits)
        if err == _Z_STREAM_ERROR:
            raise ValueError("Invalid initialization option")
        if err == _Z_MEM_ERROR:
            raise MemoryError("Can't allocate memory for decompression object")
        if err != _Z_OK:
            raise _zlib_error(err, zmsg, "while creating decompression object")
        self: _ZlibDecompressor = _bella_new_instance(cls)
        self._handle = handle
        self._initialised = True
        self._eof = False
        self._needs_input = True
        self._input = b""
        self._unused_data = b""
        self._zdict = zdict
        if zdict is not None and wbits < 0:
            _inflate_zdict(handle, _buffer(zdict))
        return self

    def __del__(self) -> None:
        if self._handle:
            _zlib("free", self._handle)
            self._handle = 0

    @property
    def eof(self) -> bool:
        return self._eof

    @property
    def needs_input(self) -> bool:
        return self._needs_input

    @property
    def unused_data(self) -> bytes:
        return self._unused_data

    def decompress(self, *args: object, **kwds: object) -> bytes:
        """Decompress *data*, returning uncompressed data as bytes.

If *max_length* is nonnegative, returns at most *max_length* bytes
of decompressed data.  If this limit is reached and further output
can be produced, *self.needs_input* will be set to ``False``.  In
this case, the next call to *decompress()* may provide *data* as b''
to obtain more of the output.

If all of the input data was decompressed and returned (either
because this was less than *max_length* bytes, or because
*max_length* was negative), *self.needs_input* will be set to True.

Attempting to decompress data after the end of stream is reached
raises an EOFError.  Any data found after the end of the stream
is ignored and saved in the unused_data attribute."""
        given = _arguments("decompress", ("data", "max_length"), 2, 1, args, kwds)
        data = _buffer(given[0])
        max_length = -1 if given[1] is _ABSENT else _ssize(given[1], "max_length", True)
        if self._eof:
            raise EOFError("End of stream already reached")
        pending = self._input + data                 # decompress(): the buffered input, then the new
        first = DEF_BUF_SIZE if max_length < 0 else min(max_length, _DEF_MAX_INITIAL_BUF_SIZE)   # decompress_buf's first buffer
        err, out, consumed, zmsg, context = _zlib("inflate", self._handle, pending, max_length, first, Z_SYNC_FLUSH, None)
        rest = pending[consumed:]
        if err == _Z_NEED_DICT:                      # decompress_buf's `goto error` sets no exception: CPython 3.15.2 raises this SystemError
            self._input = b""
            raise SystemError("<method 'decompress' of 'zlib._ZlibDecompressor' objects> returned NULL without setting an exception")
        if err == _Z_STREAM_END:
            self._eof = True
            self._initialised = False
            err = _zlib("end", self._handle)
            if err != _Z_OK:
                self._input = b""
                raise _zlib_error(err, None, "while finishing decompression")
        elif err != _Z_OK and err != _Z_BUF_ERROR:
            self._input = b""
            raise _zlib_error(err, zmsg, "while decompressing data")
        if self._eof:
            self._needs_input = False
            if rest:
                self._unused_data = rest
            self._input = b""
        elif not rest:
            self._input = b""
            self._needs_input = True
        else:
            self._needs_input = False
            self._input = rest
        return out  # type: ignore[no-any-return]


_ZlibDecompressor.__module__ = "zlib"


# ---- the checksums ---------------------------------------------------------------------------------------------------------------

def adler32(*args: object, **kwds: object) -> int:
    """Compute an Adler-32 checksum of data.

  value
    Starting value of the checksum.

The returned checksum is an integer."""
    if kwds:
        raise TypeError("zlib.adler32() takes no keyword arguments")
    if len(args) < 1:
        raise TypeError("adler32 expected at least 1 argument, got 0")
    if len(args) > 2:
        raise TypeError("adler32 expected at most 2 arguments, got " + str(len(args)))
    data = _buffer(args[0])
    value = 1 if len(args) == 1 else _unsigned(args[1], "adler32")
    return _zlib("adler32", data, value)  # type: ignore[no-any-return]


def crc32(*args: object, **kwds: object) -> int:
    """Compute a CRC-32 checksum of data.

  value
    Starting value of the checksum.

The returned checksum is an integer."""
    if kwds:
        raise TypeError("zlib.crc32() takes no keyword arguments")
    if len(args) < 1:
        raise TypeError("crc32 expected at least 1 argument, got 0")
    if len(args) > 2:
        raise TypeError("crc32 expected at most 2 arguments, got " + str(len(args)))
    data = _buffer(args[0])
    value = 0 if len(args) == 1 else _unsigned(args[1], "crc32")
    return _zlib("crc32", data, value)  # type: ignore[no-any-return]


def _combine(fname: str, args: tuple[object, ...], kwds: dict[str, object]) -> int:
    if kwds:
        raise TypeError("zlib." + fname + "() takes no keyword arguments")
    if len(args) != 3:
        raise TypeError(fname + " expected 3 arguments, got " + str(len(args)))
    c1 = _unsigned(args[0], fname)
    c2 = _unsigned(args[1], fname)
    if not issubclass(type(args[2]), int):
        raise TypeError(fname + "() argument 3 must be int, not " + _tp_name(args[2]))
    length = int.__index__(args[2])  # type: ignore[arg-type]
    if length > _MAXSIZE or length < -_MAXSIZE - 1:
        raise OverflowError("Python int too large to convert to C ssize_t")
    if length < 0:
        raise ValueError("len2 must be non-negative")
    return _zlib(fname, c1, c2, length)  # type: ignore[no-any-return]


def adler32_combine(*args: object, **kwds: object) -> int:
    """Combine two Adler-32 checksums into one.

  adler1
    Adler-32 checksum for sequence A
  adler2
    Adler-32 checksum for sequence B
  len2
    Length of sequence B

Given the Adler-32 checksum 'adler1' of a sequence A and the
Adler-32 checksum 'adler2' of a sequence B of length 'len2',
return the Adler-32 checksum of A and B concatenated."""
    return _combine("adler32_combine", args, kwds)


def crc32_combine(*args: object, **kwds: object) -> int:
    """Combine two CRC-32 checksums into one.

  crc1
    CRC-32 checksum for sequence A
  crc2
    CRC-32 checksum for sequence B
  len2
    Length of sequence B

Given the CRC-32 checksum 'crc1' of a sequence A and the
CRC-32 checksum 'crc2' of a sequence B of length 'len2',
return the CRC-32 checksum of A and B concatenated."""
    return _combine("crc32_combine", args, kwds)
