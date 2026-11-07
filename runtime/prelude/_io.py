"""_io, in Python from Modules/_io (iobase.c, fileio.c, bufferedio.c, bytesio.c, stringio.c, textio.c, _iomodule.c); see itertools.py beside it.

Each class is the C's: its name, its bases, what it keeps and the order it does things in, with the C's messages. What the C keeps in its struct
is in private slots here, and the instance has a __dict__ as the C's does (`name` and `mode` are set in it). The system calls are posix.cpp's
(`_sys`), with the convention of posix.py: a negative result is -errno.

CPython hands a raw stream's readinto() a memoryview of the buffer; the buffered classes here read a FileIO through the runtime, and a raw
object of the program's stops by name. Not written: BytesIO.getbuffer (a memoryview), readinto1 on a program's buffer, and reconfigure.
"""

__all__ = ["BufferedRWPair", "BufferedRandom", "BufferedReader", "BufferedWriter", "BytesIO", "DEFAULT_BUFFER_SIZE", "FileIO",
           "IncrementalNewlineDecoder", "StringIO", "TextIOWrapper", "UnsupportedOperation", "_BufferedIOBase", "_BytesIOBuffer", "_IOBase", "_RawIOBase",
           "_TextIOBase", "open", "open_code", "text_encoding"]

__name__ = "_io"

try:
    _number_index                                # noqa: B018  # PyNumber_Index
    _tp_name                                     # noqa: B018  # Py_TYPE(obj)->tp_name
    _keyword_suggestion                          # noqa: B018  # _Py_CalculateSuggestions
    _bella_new_instance                          # noqa: B018  # tp_alloc
    _sys                                         # noqa: B018  # the system calls, by name (posix.cpp)
    _io_call                                     # noqa: B018  # the runtime's part, by name
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _number_index: Callable[..., int] = _missing
    _tp_name: Callable[..., str] = _missing
    _keyword_suggestion: Callable[..., str | None] = _missing
    _bella_new_instance: Callable[..., Any] = _missing
    _sys: Callable[..., Any] = _missing
    _io_call: Callable[..., Any] = _missing

DEFAULT_BUFFER_SIZE = 128 * 1024
_ABSENT = object()
_SSIZE_MAX = 2**63 - 1
_READ_MAX = 2**31 - 1                            # _PY_READ_MAX
_SMALLCHUNK = 8 * 1024
_LARGE_BUFFER_CUTOFF_SIZE = 65536

_EINTR = 4
_EAGAIN = 11
_EISDIR = 21
_ESPIPE = 29
_O_RDONLY, _O_WRONLY, _O_RDWR = 0, 1, 2
_O_CREAT, _O_EXCL, _O_TRUNC, _O_APPEND = 0o100, 0o200, 0o1000, 0o2000
_S_IFMT, _S_IFDIR, _S_IFCHR = 0o170000, 0o040000, 0o020000


class UnsupportedOperation(OSError, ValueError):
    pass


UnsupportedOperation.__module__ = "io"


def _refuse(what: str) -> None:
    _io_call("refuse", what)


def _unpack(name: str, args: tuple[object, ...], kwds: dict[str, object], names: tuple[str, ...], minpos: int, maxpos: int, posonly: int = 0) -> list[object]:
    """_PyArg_UnpackKeywords: the values, or _ABSENT for one not given; the first `posonly` names cannot be given by keyword."""
    nargs = len(args)
    nkw = len(kwds)
    maxargs = len(names)
    if nargs + nkw > maxargs:
        raise TypeError(name + "() takes at most " + str(maxargs) + (" keyword" if nargs == 0 else "") + " argument" + ("" if maxargs == 1 else "s") + " (" + str(nargs + nkw) + " given)")
    if nargs > maxpos:
        if maxpos == 0:
            raise TypeError(name + "() takes no positional arguments")
        raise TypeError(name + "() takes " + ("at most" if minpos < maxpos else "exactly") + " " + str(maxpos) + " positional argument" + ("" if maxpos == 1 else "s") + " (" + str(nargs) + " given)")
    minposonly = min(minpos, posonly)
    if nargs < minposonly:
        raise TypeError(name + "() takes " + ("at least" if minposonly < maxpos else "exactly") + " " + str(minposonly) + " positional argument" + ("" if minposonly == 1 else "s") + " (" + str(nargs) + " given)")
    out: list[object] = [*args, *[_ABSENT] * (maxargs - nargs)]
    if nkw:
        i = posonly
        while i < nargs:
            if names[i] in kwds:
                raise TypeError("argument for " + name + "() given by name ('" + names[i] + "') and position (" + str(i + 1) + ")")
            i += 1
    left = nkw
    i = nargs
    while i < maxargs:
        if not left and i >= minpos:
            break
        if left and i >= posonly and names[i] in kwds:
            out[i] = kwds[names[i]]
            left -= 1
        elif i < minpos:
            raise TypeError(name + "() missing required argument '" + names[i] + "' (pos " + str(i + 1) + ")")
        i += 1
    if left > 0:                                 # error_unexpected_keyword
        keyword_names = names[posonly:]
        for keyword in kwds:
            if keyword not in keyword_names:
                suggestion = _keyword_suggestion(keyword_names, keyword)
                if suggestion is not None:
                    raise TypeError(name + "() got an unexpected keyword argument '" + keyword + "'. Did you mean '" + suggestion + "'?")
                raise TypeError(name + "() got an unexpected keyword argument '" + keyword + "'")
    return out


def _noargs(shown: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:   # METH_NOARGS, bound: args[0] is self
    if kwds:
        raise TypeError(shown + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError(shown + "() takes no arguments (" + str(len(args) - 1) + " given)")


def _one(shown: str, args: tuple[object, ...], kwds: dict[str, object]) -> object:   # METH_O, bound
    if kwds:
        raise TypeError(shown + "() takes no keyword arguments")
    if len(args) != 2:
        raise TypeError(shown + "() takes exactly one argument (" + str(len(args) - 1) + " given)")
    return args[1]


def _positional(name: str, shown: str, args: tuple[object, ...], kwds: dict[str, object], low: int, high: int) -> int:   # METH_FASTCALL, bound
    if kwds:
        raise TypeError(shown + "() takes no keyword arguments")
    n = len(args) - 1
    if n < low:
        raise TypeError(name + " expected " + ("" if low == high else "at least ") + str(low) + " argument" + ("" if low == 1 else "s") + ", got " + str(n))
    if n > high:
        raise TypeError(name + " expected " + ("" if low == high else "at most ") + str(high) + " argument" + ("" if high == 1 else "s") + ", got " + str(n))
    return n


def _ssize_or_none(value: object, absent: int = -1) -> int:   # Py_ssize_t(accept={int, NoneType}) = -1
    if value is _ABSENT or value is None:
        return absent
    if not isinstance(value, int) and not hasattr(type(value), "__index__"):
        raise TypeError("argument should be integer or None, not '" + _tp_name(value) + "'")
    return _ssize(value)


def _ssize(value: object) -> int:                # Py_ssize_t's converter: __index__, within the C type
    out = _number_index(value)
    if out > _SSIZE_MAX or out < -_SSIZE_MAX - 1:
        raise OverflowError("Python int too large to convert to C ssize_t")
    return out


def _int(value: object) -> int:                  # PyLong_AsInt
    out = _number_index(value)
    if out > 2**31 - 1 or out < -(2**31):
        raise OverflowError("Python int too large to convert to C int")
    return out


def _off(value: object) -> int:                  # Py_off_t: PyLong_AsLongLong
    if not isinstance(value, int):
        if hasattr(type(value), "__index__"):
            value = _number_index(value)
        else:
            raise TypeError("'" + _tp_name(value) + "' object cannot be interpreted as an integer")
    out = int.__index__(value)  # type: ignore[arg-type]
    if out > _SSIZE_MAX or out < -_SSIZE_MAX - 1:
        raise OverflowError("Python int too large to convert to C long")
    return out


def _c_string(value: object, what: str) -> str:  # str(accept={str, NoneType}): a C string, or None
    if not isinstance(value, str):
        raise TypeError(what + " must be str or None, not " + _tp_name(value))
    str.encode(value, "utf-8")
    if str.__contains__(value, "\0"):
        raise ValueError("embedded null character")
    return value


def _full_name(value: object) -> str:            # %T
    cls = type(value)
    return cls.__qualname__ if cls.__module__ in ("builtins", "__main__") else cls.__module__ + "." + cls.__qualname__


def _special(value: object, name: str) -> object:   # _PyObject_LookupSpecial: None when it has none
    for klass in type(value).__mro__:
        found = vars(klass)
        if name in found:
            descriptor = found[name]
            get = _lookup_get(descriptor)
            return descriptor if get is None else get(descriptor, value, type(value))
    return None


def _lookup_get(descriptor: object) -> object:
    for klass in type(descriptor).__mro__:
        found = vars(klass)
        if "__get__" in found:
            return found["__get__"]
    return None


def _optional_attr(value: object, name: str) -> object:   # PyObject_GetOptionalAttr: _ABSENT when it has none
    try:
        return getattr(value, name)
    except AttributeError:
        return _ABSENT


def _fail(code: int, filename: object = _ABSENT) -> None:   # PyErr_SetFromErrnoWithFilenameObject
    if filename is _ABSENT:
        raise OSError(code, _sys("strerror", code))
    raise OSError(code, _sys("strerror", code), filename)


def _fspath(path: object) -> object:             # PyOS_FSPath
    if issubclass(type(path), (str, bytes)):
        return path
    func = _special(path, "__fspath__")
    if func is None:
        raise TypeError("expected str, bytes or os.PathLike object, not " + _tp_name(path))
    result = func()  # type: ignore[operator]
    if not issubclass(type(result), (str, bytes)):
        raise TypeError("expected " + type(path).__name__ + ".__fspath__() to return str or bytes, not " + type(result).__name__)
    return result


def _is_bytes_like(value: object) -> bool:
    if issubclass(type(value), (bytes, bytearray)):
        return True
    if hasattr(type(value), "__buffer__"):
        _refuse("[P2+] the buffer protocol (__buffer__)")
    return False


def _rw_buffer(value: object, method: str, argument: str = "argument") -> bytearray:   # Py_buffer(accept={rwbuffer}): a bytearray, the one writable buffer there is
    if issubclass(type(value), bytearray):
        return value  # type: ignore[return-value]
    if not issubclass(type(value), bytes) and hasattr(type(value), "__buffer__"):
        _refuse("[P2+] the buffer protocol (__buffer__)")
    raise TypeError(method + "() " + argument + " must be read-write bytes-like object, not " + _tp_name(value))


def _buffer(value: object) -> bytes:             # PyObject_GetBuffer, read-only: the bytes
    if not _is_bytes_like(value):
        raise TypeError("a bytes-like object is required, not '" + _tp_name(value) + "'")
    return bytes(value)  # type: ignore[arg-type]


# ---- _IOBase (iobase.c) ----

def _is_closed(self: object) -> bool:            # iobase_is_closed: the instance has __IOBase_closed
    return hasattr(self, "__IOBase_closed")


def _check_closed(self: object) -> None:         # iobase_check_closed: the `closed` attribute as the object answers it
    closed = _optional_attr(self, "closed")
    if closed is not _ABSENT and closed:
        raise ValueError("I/O operation on closed file.")


def _check_ability(self: object, method: str, message: str) -> None:   # _PyIOBase_check_seekable and the others
    result = getattr(self, method)()
    if result is not True:
        if not result:
            raise UnsupportedOperation(message)


def _unsupported(message: str) -> None:
    raise UnsupportedOperation(message)


def _peek_or_read(self: object, limit: int, chunks: list[bytes]) -> bool:
    """_io__IOBase_readline_impl's loop body: one chunk, by peek() when there is one; True when a line is complete."""
    nreadahead = 1
    peek = _optional_attr(self, "peek")
    if peek is not _ABSENT:
        readahead = peek(1)  # type: ignore[operator]
        if not issubclass(type(readahead), bytes):
            raise OSError("peek() should have returned a bytes object, not '" + _tp_name(readahead) + "'")
        n = bytes.__len__(readahead)
        if n > 0:
            found = 0
            while found < n and (limit < 0 or found < limit):
                c = bytes.__getitem__(readahead, found)  # type: ignore[arg-type]
                found += 1
                if c == 10:
                    break
            nreadahead = found
    b = self.read(nreadahead)  # type: ignore[attr-defined]
    if not issubclass(type(b), bytes):
        raise OSError("read() should have returned a bytes object, not '" + _tp_name(b) + "'")
    if bytes.__len__(b) == 0:
        return True
    chunks.append(b)
    return bytes.__getitem__(b, bytes.__len__(b) - 1) == 10  # type: ignore[arg-type]


class _IOBase:
    __slots__ = ("__dict__", "__weakref__")

    def seek(*args: object, **kwds: object) -> object:  # noqa: N805
        offset, whence = _unpack("seek", args[1:], kwds, ("offset", "whence"), 1, 2, 2)
        _int(offset)
        if whence is not _ABSENT:
            _int(whence)
        _unsupported("seek")
        return None

    def tell(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("_IOBase.tell", args, kwds)
        return args[0].seek(0, 1)  # type: ignore[attr-defined]

    def truncate(*args: object, **kwds: object) -> object:  # noqa: N805
        _unpack("truncate", args[1:], kwds, ("size",), 0, 1, 1)
        _unsupported("truncate")
        return None

    def flush(*args: object, **kwds: object) -> None:  # noqa: N805
        _noargs("_IOBase.flush", args, kwds)
        if _is_closed(args[0]):
            raise ValueError("I/O operation on closed file.")

    @property
    def closed(self) -> bool:
        return _is_closed(self)

    def _checkClosed(*args: object, **kwds: object) -> None:  # noqa: N802, N805
        _noargs("_IOBase._checkClosed", args, kwds)
        _check_closed(args[0])

    def _checkSeekable(*args: object, **kwds: object) -> None:  # noqa: N802, N805
        _noargs("_IOBase._checkSeekable", args, kwds)
        _check_ability(args[0], "seekable", "File or stream is not seekable.")

    def _checkReadable(*args: object, **kwds: object) -> None:  # noqa: N802, N805
        _noargs("_IOBase._checkReadable", args, kwds)
        _check_ability(args[0], "readable", "File or stream is not readable.")

    def _checkWritable(*args: object, **kwds: object) -> None:  # noqa: N802, N805
        _noargs("_IOBase._checkWritable", args, kwds)
        _check_ability(args[0], "writable", "File or stream is not writable.")

    def close(*args: object, **kwds: object) -> None:  # noqa: N805
        _noargs("_IOBase.close", args, kwds)
        self = args[0]
        if _is_closed(self):
            return
        try:
            self.flush()  # type: ignore[attr-defined]
        finally:
            setattr(self, "__IOBase_closed", True)  # noqa: B010

    def __del__(self) -> None:                   # iobase_finalize
        try:
            closed = _optional_attr(self, "closed")
            closed = -1 if closed is _ABSENT else (1 if closed else 0)
        except BaseException:  # noqa: BLE001
            closed = -1
        if closed == 0:
            try:
                self._finalizing = True
            except BaseException:  # noqa: BLE001, S110
                pass
            try:
                self.close()  # type: ignore[attr-defined]
            except BaseException:  # noqa: BLE001
                _io_call("unraisable", "Exception ignored while finalizing file " + repr(self))

    def seekable(*args: object, **kwds: object) -> bool:  # noqa: N805
        _noargs("_IOBase.seekable", args, kwds)
        return False

    def readable(*args: object, **kwds: object) -> bool:  # noqa: N805
        _noargs("_IOBase.readable", args, kwds)
        return False

    def writable(*args: object, **kwds: object) -> bool:  # noqa: N805
        _noargs("_IOBase.writable", args, kwds)
        return False

    def __enter__(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("_IOBase.__enter__", args, kwds)
        _check_closed(args[0])
        return args[0]

    def __exit__(*args: object, **kwds: object) -> object:  # noqa: N805
        if kwds:
            raise TypeError("_IOBase.__exit__() takes no keyword arguments")
        return args[0].close()  # type: ignore[attr-defined]

    def fileno(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("_IOBase.fileno", args, kwds)
        _unsupported("fileno")
        return None

    def isatty(*args: object, **kwds: object) -> bool:  # noqa: N805
        _noargs("_IOBase.isatty", args, kwds)
        _check_closed(args[0])
        return False

    def readline(*args: object, **kwds: object) -> bytes:  # noqa: N805
        n = _positional("readline", "_IOBase.readline", args, kwds, 0, 1)
        self = args[0]
        limit = _ssize_or_none(args[1]) if n else -1
        chunks: list[bytes] = []
        total = 0
        while limit < 0 or total < limit:
            if _peek_or_read(self, limit - total if limit >= 0 else -1, chunks):
                break
            total += bytes.__len__(chunks[-1])
        return b"".join(chunks)

    def __iter__(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("_IOBase.__iter__", args, kwds)
        _check_closed(args[0])
        return args[0]

    def __next__(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("_IOBase.__next__", args, kwds)
        line = args[0].readline()  # type: ignore[attr-defined]
        if len(line) == 0:
            raise StopIteration
        return line

    def readlines(*args: object, **kwds: object) -> list[object]:  # noqa: N805
        n = _positional("readlines", "_IOBase.readlines", args, kwds, 0, 1)
        self = args[0]
        hint = _ssize_or_none(args[1]) if n else -1
        result: list[object] = []
        if hint <= 0:
            result.extend(self)  # type: ignore[arg-type]
            return result
        length = 0
        for line in self:  # type: ignore[attr-defined]
            result.append(line)
            length += len(line)
            if length > hint:
                break
        return result

    def writelines(*args: object, **kwds: object) -> None:  # noqa: N805
        lines = _one("_IOBase.writelines", args, kwds)
        self = args[0]
        _check_closed(self)
        for line in iter(lines):  # type: ignore[call-overload]
            self.write(line)  # type: ignore[attr-defined]


# ---- _RawIOBase ----

class _RawIOBase(_IOBase):
    __slots__ = ()

    def read(*args: object, **kwds: object) -> object:  # noqa: N805
        n = _positional("read", "_RawIOBase.read", args, kwds, 0, 1)
        self = args[0]
        size = _ssize(args[1]) if n else -1
        if size < 0:
            return self.readall()  # type: ignore[attr-defined]
        b = bytearray(size)
        got = self.readinto(b)  # type: ignore[attr-defined]
        if got is None:
            return None
        got = _ssize(got)
        if got < 0 or got > size:
            raise ValueError("readinto returned " + str(got) + " outside buffer size " + str(size))
        del b[got:]
        return bytes(b)

    def readall(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("_RawIOBase.readall", args, kwds)
        self = args[0]
        chunks: list[bytes] = []
        while True:
            data = self.read(DEFAULT_BUFFER_SIZE)  # type: ignore[attr-defined]
            if data is None:
                if not chunks:
                    return None
                break
            if not issubclass(type(data), bytes):
                raise TypeError("read() should return bytes")
            if bytes.__len__(data) == 0:
                break
            chunks.append(data)
        return b"".join(chunks)

    def readinto(*args: object, **kwds: object) -> object:  # noqa: N805
        if kwds:
            raise TypeError("_RawIOBase.readinto() takes no keyword arguments")
        raise NotImplementedError

    def write(*args: object, **kwds: object) -> object:  # noqa: N805
        if kwds:
            raise TypeError("_RawIOBase.write() takes no keyword arguments")
        raise NotImplementedError


# ---- _BufferedIOBase ----

def _readinto_generic(self: object, b: object, method: str, read: str) -> object:   # _bufferediobase_readinto_generic
    target = _rw_buffer(b, method)
    data = getattr(self, read)(bytearray.__len__(target))
    if not issubclass(type(data), bytes):
        raise TypeError("read() should return bytes")
    n = bytes.__len__(data)
    if n > bytearray.__len__(target):
        raise ValueError("read() returned too much data: " + str(bytearray.__len__(target)) + " bytes requested, " + str(n) + " returned")
    target[0:n] = data
    return n


class _BufferedIOBase(_IOBase):
    __slots__ = ()

    def detach(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("_BufferedIOBase.detach", args, kwds)
        _unsupported("detach")
        return None

    def read(*args: object, **kwds: object) -> object:  # noqa: N805
        _positional("read", "_BufferedIOBase.read", args, kwds, 0, 1)
        _unsupported("read")
        return None

    def read1(*args: object, **kwds: object) -> object:  # noqa: N805
        _positional("read1", "_BufferedIOBase.read1", args, kwds, 0, 1)
        _unsupported("read1")
        return None

    def write(*args: object, **kwds: object) -> object:  # noqa: N805
        _positional("write", "_BufferedIOBase.write", args, kwds, 1, 1)
        _unsupported("write")
        return None

    def readinto(*args: object, **kwds: object) -> object:  # noqa: N805
        b = _one("_BufferedIOBase.readinto", args, kwds)
        return _readinto_generic(args[0], b, "readinto", "read")

    def readinto1(*args: object, **kwds: object) -> object:  # noqa: N805
        b = _one("_BufferedIOBase.readinto1", args, kwds)
        return _readinto_generic(args[0], b, "readinto1", "read1")


# ---- _TextIOBase ----

class _TextIOBase(_IOBase):
    __slots__ = ()

    def detach(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("_TextIOBase.detach", args, kwds)
        _unsupported("detach")
        return None

    def read(*args: object, **kwds: object) -> object:  # noqa: N805
        _positional("read", "_TextIOBase.read", args, kwds, 0, 1)
        _unsupported("read")
        return None

    def readline(*args: object, **kwds: object) -> object:  # noqa: N805
        _positional("readline", "_TextIOBase.readline", args, kwds, 0, 1)
        _unsupported("readline")
        return None

    def write(*args: object, **kwds: object) -> object:  # noqa: N805
        _positional("write", "_TextIOBase.write", args, kwds, 1, 1)
        _unsupported("write")
        return None

    @property
    def encoding(self) -> object:
        return None

    @property
    def newlines(self) -> object:
        return None

    @property
    def errors(self) -> object:
        return None


# ---- FileIO (fileio.c) ----

def _fileio_closed(self: object) -> None:
    raise ValueError("I/O operation on closed file")


def _fileio_mode_string(self: FileIO) -> str:     # mode_string
    if self._b_created:
        return "xb+" if self._c_readable else "xb"
    if self._e_appending:
        return "ab+" if self._c_readable else "ab"
    if self._c_readable:
        if self._d_writable:
            return "wb+" if self._f_truncate else "rb+"
        return "rb"
    return "wb"


def _fileio_lseek(self: FileIO, posobj: object, whence: int, suppress_pipe_error: bool) -> int:   # portable_lseek
    pos = 0 if posobj is None else _off(posobj)
    res = _sys("lseek", self._a_fd, pos, whence)
    if self._g_seekable < 0:
        self._g_seekable = 1 if res >= 0 else 0
    if res < 0:
        if suppress_pipe_error and -res == _ESPIPE:
            return 0
        _fail(-res)
    return res  # type: ignore[no-any-return]


def _fileio_new_buffersize(currentsize: int) -> int:   # new_buffersize
    addend = currentsize >> 3 if currentsize > _LARGE_BUFFER_CUTOFF_SIZE else 256 + currentsize
    if addend < _SMALLCHUNK:
        addend = _SMALLCHUNK
    return addend + currentsize


def _fileio_internal_close(self: FileIO) -> None:
    fd = self._a_fd
    if fd >= 0:
        self._a_fd = -1
        res = _sys("close", fd)
        if res < 0:
            _fail(-res)


class FileIO(_RawIOBase):
    __slots__ = ("_a_fd", "_b_created", "_c_readable", "_d_writable", "_e_appending", "_f_truncate", "_g_seekable", "_h_closefd", "_i_finalizing", "_j_blksize", "_k_stat_atopen", "_l_in_repr")

    def __new__(cls, *args: object, **kwds: object) -> FileIO:   # fileio_new
        self: FileIO = _bella_new_instance(cls)
        self._a_fd = -1
        self._b_created = False
        self._c_readable = False
        self._d_writable = False
        self._e_appending = False
        self._f_truncate = False
        self._g_seekable = -1
        self._h_closefd = True
        self._i_finalizing = False
        self._j_blksize = 0
        self._k_stat_atopen = None
        self._l_in_repr = False
        return self

    def __init__(*args: object, **kwds: object) -> None:  # noqa: N805
        self: FileIO = args[0]  # type: ignore[assignment]
        nameobj, mode, closefd, opener = _unpack("FileIO", args[1:], kwds, ("file", "mode", "closefd", "opener"), 1, 4)
        if mode is _ABSENT:
            mode = "r"
        elif not isinstance(mode, str):
            raise TypeError("FileIO() argument 'mode' must be str, not " + _tp_name(mode))
        else:
            str.encode(mode, "utf-8")
            if str.__contains__(mode, "\0"):
                raise ValueError("embedded null character")
        closefd = True if closefd is _ABSENT else (True if closefd else False)
        if opener is _ABSENT:
            opener = None
        if self._a_fd >= 0:
            if self._h_closefd:
                _fileio_internal_close(self)
            else:
                self._a_fd = -1
        if isinstance(nameobj, bool):
            _refuse("the RuntimeWarning 'bool is used as a file descriptor' (warnings: step 3b)")
        fd = -1
        if isinstance(nameobj, int) or hasattr(type(nameobj), "__index__"):
            fd = _int(nameobj)
            if fd < 0:
                raise ValueError("negative file descriptor")
        name: bytes = b""
        if fd < 0:
            path = _fspath(nameobj)
            name = str.encode(path, "utf-8", "surrogateescape") if issubclass(type(path), str) else path  # type: ignore[arg-type,assignment]
            if 0 in name:
                raise ValueError("embedded null byte")
        rwa = False
        plus = False
        flags = 0
        self._b_created = self._c_readable = self._d_writable = self._e_appending = self._f_truncate = False
        for c in str.__str__(mode):
            if c == "x":
                if rwa:
                    raise ValueError("Must have exactly one of create/read/write/append mode and at most one plus")
                rwa = True
                self._b_created = True
                self._d_writable = True
                flags |= _O_EXCL | _O_CREAT
            elif c == "r":
                if rwa:
                    raise ValueError("Must have exactly one of create/read/write/append mode and at most one plus")
                rwa = True
                self._c_readable = True
            elif c == "w":
                if rwa:
                    raise ValueError("Must have exactly one of create/read/write/append mode and at most one plus")
                rwa = True
                self._d_writable = True
                self._f_truncate = True
                flags |= _O_CREAT | _O_TRUNC
            elif c == "a":
                if rwa:
                    raise ValueError("Must have exactly one of create/read/write/append mode and at most one plus")
                rwa = True
                self._d_writable = True
                self._e_appending = True
                flags |= _O_APPEND | _O_CREAT
            elif c == "b":
                pass
            elif c == "+":
                if plus:
                    raise ValueError("Must have exactly one of create/read/write/append mode and at most one plus")
                self._c_readable = self._d_writable = True
                plus = True
            else:
                raise ValueError("invalid mode: " + mode[:200])
        if not rwa:
            raise ValueError("Must have exactly one of create/read/write/append mode and at most one plus")
        if self._c_readable and self._d_writable:
            flags |= _O_RDWR
        elif self._c_readable:
            flags |= _O_RDONLY
        else:
            flags |= _O_WRONLY
        fd_is_own = False
        try:
            if fd >= 0:
                self._a_fd = fd
                self._h_closefd = closefd
            else:
                self._h_closefd = True
                if not closefd:
                    raise ValueError("Cannot use closefd=False with file name")
                if opener is None:
                    opened = _sys("open", name, flags, 0o666)
                    if opened < 0:
                        _fail(-opened, nameobj)
                    self._a_fd = opened
                else:
                    fdobj = opener(nameobj, flags)  # type: ignore[operator]
                    if not isinstance(fdobj, int):
                        raise TypeError("expected integer from opener")
                    self._a_fd = _int(fdobj)
                    if self._a_fd < 0:
                        raise ValueError("opener returned " + str(self._a_fd))
                fd_is_own = True
            st = _sys("stat", self._a_fd, True)
            self._j_blksize = DEFAULT_BUFFER_SIZE
            if isinstance(st, int):
                if -st == 9:                     # EBADF
                    _fail(-st)
                self._k_stat_atopen = None
            else:
                if st[0] & _S_IFMT == _S_IFDIR:
                    _fail(_EISDIR, nameobj)
                self._k_stat_atopen = (st[0], st[6])
                if st[13] > 1:
                    self._j_blksize = st[13]
            self.name = nameobj
            if self._e_appending:
                _fileio_lseek(self, None, 2, True)
        except BaseException:
            if not fd_is_own:
                self._a_fd = -1
            if self._a_fd >= 0:
                try:
                    _fileio_internal_close(self)
                except BaseException as e:  # noqa: BLE001
                    raise e from None  # the close's error, with the first chained: _PyErr_ChainExceptions1
            self._k_stat_atopen = None
            raise

    def __getstate__(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("FileIO.__getstate__", args, kwds)
        raise TypeError("cannot pickle '" + type(args[0]).__name__ + "' instances")

    def _dealloc_warn(*args: object, **kwds: object) -> None:  # noqa: N805
        _one("FileIO._dealloc_warn", args, kwds)   # the ResourceWarning for an unclosed file: CPython's default filters hide it; not emitted

    def fileno(*args: object, **kwds: object) -> int:  # noqa: N805
        _noargs("FileIO.fileno", args, kwds)
        self: FileIO = args[0]  # type: ignore[assignment]
        if self._a_fd < 0:
            _fileio_closed(self)
        return self._a_fd

    def readable(*args: object, **kwds: object) -> bool:  # noqa: N805
        _noargs("FileIO.readable", args, kwds)
        self: FileIO = args[0]  # type: ignore[assignment]
        if self._a_fd < 0:
            _fileio_closed(self)
        return self._c_readable

    def writable(*args: object, **kwds: object) -> bool:  # noqa: N805
        _noargs("FileIO.writable", args, kwds)
        self: FileIO = args[0]  # type: ignore[assignment]
        if self._a_fd < 0:
            _fileio_closed(self)
        return self._d_writable

    def seekable(*args: object, **kwds: object) -> bool:  # noqa: N805
        _noargs("FileIO.seekable", args, kwds)
        self: FileIO = args[0]  # type: ignore[assignment]
        if self._a_fd < 0:
            _fileio_closed(self)
        if self._g_seekable < 0:
            try:
                _fileio_lseek(self, None, 1, False)
            except OSError:
                pass
        return self._g_seekable == 1

    def readinto(*args: object, **kwds: object) -> object:  # noqa: N805
        b = _one("FileIO.readinto", args, kwds)
        self: FileIO = args[0]  # type: ignore[assignment]
        target = _rw_buffer(b, "readinto", "argument 1")   # the clinic's defining_class counts it
        if self._a_fd < 0:
            _fileio_closed(self)
        if not self._c_readable:
            raise UnsupportedOperation("File not open for reading")
        data = _sys("read", self._a_fd, bytearray.__len__(target))
        if isinstance(data, int):
            if -data == _EAGAIN:
                return None
            _fail(-data)
        n = bytes.__len__(data)
        target[0:n] = data
        return n

    def readall(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("FileIO.readall", args, kwds)
        self: FileIO = args[0]  # type: ignore[assignment]
        if self._a_fd < 0:
            _fileio_closed(self)
        if not self._c_readable:
            raise UnsupportedOperation("File not open for reading")
        end = -1
        if self._k_stat_atopen is not None and self._k_stat_atopen[1] < _READ_MAX:
            end = self._k_stat_atopen[1]
        if end <= 0:
            bufsize = _SMALLCHUNK
        else:
            bufsize = _READ_MAX if end > _READ_MAX - 1 else end + 1
            if bufsize > _LARGE_BUFFER_CUTOFF_SIZE:
                pos = _sys("lseek", self._a_fd, 0, 1)
                if end >= pos >= 0 and (end - pos) < (_READ_MAX - 1):
                    bufsize = end - pos + 1
        chunks: list[bytes] = []
        bytes_read = 0
        while True:
            if bytes_read >= bufsize:
                bufsize = _fileio_new_buffersize(bytes_read)
                if bufsize > _SSIZE_MAX or bufsize <= 0:
                    raise OverflowError("unbounded read returned more bytes than a Python bytes object can hold")
            data = _sys("read", self._a_fd, bufsize - bytes_read)
            if isinstance(data, int):
                if -data == _EAGAIN:
                    if bytes_read > 0:
                        break
                    return None
                _fail(-data)
            if bytes.__len__(data) == 0:
                break
            chunks.append(data)
            bytes_read += bytes.__len__(data)
        return b"".join(chunks)

    def read(*args: object, **kwds: object) -> object:  # noqa: N805
        n = _positional("read", "FileIO.read", args, kwds, 0, 1)
        self: FileIO = args[0]  # type: ignore[assignment]
        size = _ssize_or_none(args[1]) if n else -1
        if self._a_fd < 0:
            _fileio_closed(self)
        if not self._c_readable:
            raise UnsupportedOperation("File not open for reading")
        if size < 0:
            return self.readall()
        if size > _READ_MAX:
            size = _READ_MAX
        data = _sys("read", self._a_fd, size)
        if isinstance(data, int):
            if -data == _EAGAIN:
                return None
            _fail(-data)
        return data

    def write(*args: object, **kwds: object) -> object:  # noqa: N805
        b = _one("FileIO.write", args, kwds)
        self: FileIO = args[0]  # type: ignore[assignment]
        data = _buffer(b)
        if self._a_fd < 0:
            _fileio_closed(self)
        if not self._d_writable:
            raise UnsupportedOperation("File not open for writing")
        n = _sys("write", self._a_fd, data)
        if n < 0:
            if -n == _EAGAIN:
                return None
            _fail(-n)
        return n

    def seek(*args: object, **kwds: object) -> int:  # noqa: N805
        n = _positional("seek", "FileIO.seek", args, kwds, 1, 2)
        self: FileIO = args[0]  # type: ignore[assignment]
        whence = _int(args[2]) if n > 1 else 0
        if self._a_fd < 0:
            _fileio_closed(self)
        return _fileio_lseek(self, args[1], whence, False)

    def tell(*args: object, **kwds: object) -> int:  # noqa: N805
        _noargs("FileIO.tell", args, kwds)
        self: FileIO = args[0]  # type: ignore[assignment]
        if self._a_fd < 0:
            _fileio_closed(self)
        return _fileio_lseek(self, None, 1, False)

    def truncate(*args: object, **kwds: object) -> object:  # noqa: N805
        n = _positional("truncate", "FileIO.truncate", args, kwds, 0, 1)
        self: FileIO = args[0]  # type: ignore[assignment]
        posobj = args[1] if n else None
        if self._a_fd < 0:
            _fileio_closed(self)
        if not self._d_writable:
            raise UnsupportedOperation("File not open for writing")
        if posobj is None:
            posobj = _fileio_lseek(self, None, 1, False)
        pos = _off(posobj)
        res = _sys("ftruncate", self._a_fd, pos)
        if res < 0:
            _fail(-res)
        self._k_stat_atopen = None
        return posobj

    def close(*args: object, **kwds: object) -> None:  # noqa: N805
        _noargs("FileIO.close", args, kwds)
        self: FileIO = args[0]  # type: ignore[assignment]
        try:
            _RawIOBase.close(self)
        except BaseException:
            if not self._h_closefd:
                self._a_fd = -1
                raise
            try:
                _fileio_internal_close(self)
            except BaseException as e:  # noqa: BLE001
                raise e from None
            raise
        if not self._h_closefd:
            self._a_fd = -1
            return
        _fileio_internal_close(self)

    def isatty(*args: object, **kwds: object) -> bool:  # noqa: N805
        _noargs("FileIO.isatty", args, kwds)
        self: FileIO = args[0]  # type: ignore[assignment]
        if self._a_fd < 0:
            _fileio_closed(self)
        return _sys("isatty", self._a_fd) != 0

    def _isatty_open_only(*args: object, **kwds: object) -> bool:  # noqa: N805
        _noargs("FileIO._isatty_open_only", args, kwds)
        self: FileIO = args[0]  # type: ignore[assignment]
        if self._k_stat_atopen is not None and self._k_stat_atopen[0] & _S_IFMT != _S_IFCHR:
            return False
        return self.isatty()

    def __repr__(self) -> str:
        type_name = _tp_name(self)[:100]
        if self._a_fd < 0:
            return "<" + type_name + " [closed]>"
        nameobj = _optional_attr(self, "name")
        if nameobj is _ABSENT:
            return "<" + type_name + " fd=" + str(self._a_fd) + " mode='" + _fileio_mode_string(self) + "' closefd=" + ("True" if self._h_closefd else "False") + ">"
        if self._l_in_repr:
            raise RuntimeError("reentrant call inside " + type_name + ".__repr__")
        self._l_in_repr = True
        try:
            shown = repr(nameobj)
        finally:
            self._l_in_repr = False
        return "<" + type_name + " name=" + shown + " mode='" + _fileio_mode_string(self) + "' closefd=" + ("True" if self._h_closefd else "False") + ">"

    @property
    def closed(self) -> bool:
        return self._a_fd < 0

    @property
    def closefd(self) -> bool:
        return self._h_closefd

    @property
    def mode(self) -> str:
        return _fileio_mode_string(self)

    @property
    def _blksize(self) -> int:
        return self._j_blksize

    @property
    def _finalizing(self) -> bool:
        return self._i_finalizing

    @_finalizing.setter
    def _finalizing(self, value: object) -> None:
        self._i_finalizing = True if value else False


# ---- BufferedReader, BufferedWriter, BufferedRandom (bufferedio.c): one state, as the C's `buffered` struct ----

_BUFFERED_SLOTS = ("_a_raw", "_b_ok", "_c_detached", "_d_readable", "_e_writable", "_f_buffer", "_g_buffer_size", "_h_pos", "_i_raw_pos", "_j_read_end",
                   "_k_write_pos", "_l_write_end", "_m_abs_pos", "_n_buffer_mask", "_o_in_repr", "_finalizing")


class _Buffered:                                 # the shape of the three classes' state, for the functions below; never a base
    _a_raw: object
    _b_ok: bool
    _c_detached: bool
    _d_readable: bool
    _e_writable: bool
    _f_buffer: bytearray
    _g_buffer_size: int
    _h_pos: int
    _i_raw_pos: int
    _j_read_end: int
    _k_write_pos: int
    _l_write_end: int
    _m_abs_pos: int
    _n_buffer_mask: int
    _o_in_repr: bool
    _finalizing: bool


def _bf_new(cls: type) -> _Buffered:             # the struct's zero state: `ok` false until __init__ has run
    self: _Buffered = _bella_new_instance(cls)
    self._a_raw = None
    self._b_ok = False
    self._c_detached = False
    self._d_readable = self._e_writable = False
    self._f_buffer = bytearray()
    self._g_buffer_size = 0
    self._h_pos = self._i_raw_pos = 0
    self._j_read_end = self._l_write_end = -1
    self._k_write_pos = 0
    self._m_abs_pos = -1
    self._n_buffer_mask = 0
    self._o_in_repr = False
    self._finalizing = False
    return self


def _bf_check_initialized(self: _Buffered) -> None:   # CHECK_INITIALIZED
    if not self._b_ok:
        if self._c_detached:
            raise ValueError("raw stream has been detached")
        raise ValueError("I/O operation on uninitialized object")


def _bf_valid_read(self: _Buffered) -> bool:
    return self._d_readable and self._j_read_end != -1


def _bf_valid_write(self: _Buffered) -> bool:
    return self._e_writable and self._l_write_end != -1


def _bf_readahead(self: _Buffered) -> int:       # READAHEAD
    return self._j_read_end - self._h_pos if self._d_readable and _bf_valid_read(self) else 0


def _bf_raw_offset(self: _Buffered) -> int:      # RAW_OFFSET
    return self._i_raw_pos - self._h_pos if (_bf_valid_read(self) or _bf_valid_write(self)) and self._i_raw_pos >= 0 else 0


def _bf_adjust_position(self: _Buffered, new_pos: int) -> None:   # ADJUST_POSITION
    self._h_pos = new_pos
    if _bf_valid_read(self) and self._j_read_end < self._h_pos:
        self._j_read_end = self._h_pos


def _bf_minus_last_block(self: _Buffered, size: int) -> int:   # MINUS_LAST_BLOCK
    if self._n_buffer_mask:
        return size & ~self._n_buffer_mask
    return self._g_buffer_size * (size // self._g_buffer_size)


def _bf_closed(self: _Buffered) -> bool:         # IS_CLOSED, buffered_closed
    _bf_check_initialized(self)
    return True if getattr(self._a_raw, "closed") else False  # noqa: B009


def _bf_check_closed(self: _Buffered, message: str) -> None:   # CHECK_CLOSED
    if _bf_closed(self) and _bf_readahead(self) == 0:
        raise ValueError(message)


def _bf_raw_tell(self: _Buffered) -> int:        # _buffered_raw_tell
    res = self._a_raw.tell()  # type: ignore[attr-defined]
    n = _off_t(res)
    if n < 0:
        raise OSError("Raw stream returned invalid position " + str(n))
    self._m_abs_pos = n
    return n


def _off_t(res: object) -> int:                  # PyNumber_AsOff_t(res, ValueError)
    if not isinstance(res, int) and not hasattr(type(res), "__index__"):
        raise TypeError("'" + _tp_name(res) + "' object cannot be interpreted as an integer")
    n = _number_index(res)
    if n > _SSIZE_MAX or n < -_SSIZE_MAX - 1:
        raise ValueError("cannot fit 'int' into an offset-sized integer")
    return n


def _bf_raw_seek(self: _Buffered, target: int, whence: int) -> int:   # _buffered_raw_seek
    res = self._a_raw.seek(target, whence)  # type: ignore[attr-defined]
    n = _off_t(res)
    if n < 0:
        raise OSError("Raw stream returned invalid position " + str(n))
    self._m_abs_pos = n
    return n


def _bf_raw_tell_or_cached(self: _Buffered) -> int:   # RAW_TELL
    return self._m_abs_pos if self._m_abs_pos != -1 else _bf_raw_tell(self)


def _bf_init(self: _Buffered) -> None:           # _buffered_init
    if self._g_buffer_size <= 0:
        raise ValueError("buffer size must be strictly positive")
    self._f_buffer = bytearray(self._g_buffer_size)
    n = self._g_buffer_size - 1
    while n & 1:
        n >>= 1
    self._n_buffer_mask = self._g_buffer_size - 1 if n == 0 else 0
    try:
        _bf_raw_tell(self)
    except BaseException:  # noqa: BLE001, S110
        pass


def _bf_reset_read(self: _Buffered) -> None:
    self._j_read_end = -1


def _bf_reset_write(self: _Buffered) -> None:
    self._k_write_pos = 0
    self._l_write_end = -1


def _bf_raw_read(self: _Buffered, at: int, length: int, into: bytearray | None = None) -> int:
    """_bufferedreader_raw_read: raw.readinto() over `length` bytes at `at` of the buffer (or of `into`); -2 when it had nothing (None).
    CPython gives readinto() a memoryview of the buffer; this gives it a bytearray of the length, and takes what it wrote."""
    target = bytearray(length)
    res = self._a_raw.readinto(target)  # type: ignore[attr-defined]
    if res is None:
        return -2
    try:
        n = _off_t(res)
    except BaseException as e:
        raise OSError("raw readinto() failed") from e
    if n < 0 or n > length:
        raise OSError("raw readinto() returned invalid length " + str(n) + " (should have been between 0 and " + str(length) + ")")
    if bytearray.__len__(target) != length:
        _refuse("a raw stream that resized the buffer readinto() was given (a memoryview would have refused: the buffer protocol, [P2+])")
    dest = self._f_buffer if into is None else into
    dest[at:at + n] = target[:n]
    if n > 0 and self._m_abs_pos != -1:
        self._m_abs_pos += n
    return n


def _bf_fill_buffer(self: _Buffered) -> int:     # _bufferedreader_fill_buffer
    start = self._j_read_end if _bf_valid_read(self) else 0
    n = _bf_raw_read(self, start, self._g_buffer_size - start)
    if n <= 0:
        return n
    self._j_read_end = start + n
    self._i_raw_pos = start + n
    return n


def _bf_raw_write(self: _Buffered, data: bytes) -> int:   # _bufferedwriter_raw_write; -2 when the raw would block (None)
    res = self._a_raw.write(data)  # type: ignore[attr-defined]
    if res is None:
        return -2
    n = _off_t(res)
    if n < 0 or n > bytes.__len__(data):
        raise OSError("raw write() returned invalid length " + str(n) + " (should have been between 0 and " + str(bytes.__len__(data)) + ")")
    if n > 0 and self._m_abs_pos != -1:
        self._m_abs_pos += n
    return n


def _bf_flush_unlocked(self: _Buffered) -> None:   # _bufferedwriter_flush_unlocked
    if not _bf_valid_write(self) or self._k_write_pos == self._l_write_end:
        _bf_reset_write(self)
        return
    rewind = _bf_raw_offset(self) + (self._h_pos - self._k_write_pos)
    if rewind != 0:
        _bf_raw_seek(self, -rewind, 1)
        self._i_raw_pos -= rewind
    while self._k_write_pos < self._l_write_end:
        n = _bf_raw_write(self, bytes(self._f_buffer[self._k_write_pos:self._l_write_end]))
        if n == -2:
            raise BlockingIOError(_EAGAIN, "write could not complete without blocking", 0)
        self._k_write_pos += n
        self._i_raw_pos = self._k_write_pos
    _bf_reset_write(self)


def _bf_flush_and_rewind(self: _Buffered) -> None:   # buffered_flush_and_rewind_unlocked
    _bf_flush_unlocked(self)
    if self._d_readable:
        n = _bf_raw_offset(self)
        try:
            _bf_raw_seek(self, -n, 1)
        finally:
            _bf_reset_read(self)


def _bf_read_all(self: _Buffered) -> object:     # _bufferedreader_read_all
    current_size = _bf_readahead(self)
    data = b""
    if current_size:
        data = bytes(self._f_buffer[self._h_pos:self._h_pos + current_size])
        self._h_pos += current_size
    if self._e_writable:
        _bf_flush_and_rewind(self)
    _bf_reset_read(self)
    readall = _optional_attr(self._a_raw, "readall")
    if readall is not _ABSENT:
        tmp = readall()  # type: ignore[operator]
        if tmp is not None and not issubclass(type(tmp), bytes):
            raise TypeError("readall() should return bytes")
        if current_size == 0:
            return tmp
        return data if tmp is None else data + tmp  # type: ignore[operator]
    chunks: list[bytes] = []
    while True:
        if data:
            chunks.append(data)
        got = self._a_raw.read()  # type: ignore[attr-defined]
        if got is not None and not issubclass(type(got), bytes):
            raise TypeError("read() should return bytes")
        if got is None or bytes.__len__(got) == 0:
            return got if current_size == 0 else b"".join(chunks)
        current_size += bytes.__len__(got)
        if self._m_abs_pos != -1:
            self._m_abs_pos += bytes.__len__(got)
        data = got


def _bf_read_fast(self: _Buffered, n: int) -> object:   # _bufferedreader_read_fast: None when the buffer has less
    current_size = _bf_readahead(self)
    if n <= current_size:
        res = bytes(self._f_buffer[self._h_pos:self._h_pos + n])
        self._h_pos += n
        return res
    return None


def _bf_read_generic(self: _Buffered, n: int) -> object:   # _bufferedreader_read_generic
    current_size = _bf_readahead(self)
    if n <= current_size:
        return _bf_read_fast(self, n)
    out = bytearray(n)
    remaining = n
    written = 0
    if current_size > 0:
        out[0:current_size] = self._f_buffer[self._h_pos:self._h_pos + current_size]
        remaining -= current_size
        written += current_size
        self._h_pos += current_size
    if self._e_writable:
        _bf_flush_and_rewind(self)
    _bf_reset_read(self)
    while remaining > 0:
        r = _bf_minus_last_block(self, remaining)
        if r == 0:
            break
        r = _bf_raw_read(self, written, r, out)
        if r == 0 or r == -2:
            if r == 0 or written > 0:
                return bytes(out[:written])
            return None
        remaining -= r
        written += r
    self._h_pos = 0
    self._i_raw_pos = 0
    self._j_read_end = 0
    while remaining > 0 and self._j_read_end < self._g_buffer_size:
        r = _bf_fill_buffer(self)
        if r == 0 or r == -2:
            if r == 0 or written > 0:
                return bytes(out[:written])
            return None
        if remaining > r:
            out[written:written + r] = self._f_buffer[self._h_pos:self._h_pos + r]
            written += r
            self._h_pos += r
            remaining -= r
        elif remaining > 0:
            out[written:written + remaining] = self._f_buffer[self._h_pos:self._h_pos + remaining]
            written += remaining
            self._h_pos += remaining
            remaining = 0
        if remaining == 0:
            break
    return bytes(out)


def _bf_peek_unlocked(self: _Buffered) -> bytes:   # _bufferedreader_peek_unlocked
    have = _bf_readahead(self)
    if have > 0:
        return bytes(self._f_buffer[self._h_pos:self._h_pos + have])
    _bf_reset_read(self)
    r = _bf_fill_buffer(self)
    if r == -2:
        r = 0
    self._h_pos = 0
    return bytes(self._f_buffer[0:r])


def _bf_readline(self: _Buffered, limit: int) -> bytes:   # _buffered_readline
    _bf_check_closed(self, "readline of closed file")
    n = _bf_readahead(self)
    if limit >= 0 and n > limit:
        n = limit
    start = self._h_pos
    found = self._f_buffer.find(b"\n", start, start + n)
    if found >= 0:
        self._h_pos = found + 1
        return bytes(self._f_buffer[start:found + 1])
    if n == limit:
        self._h_pos += n
        return bytes(self._f_buffer[start:start + n])
    chunks: list[bytes] = []
    if n > 0:
        chunks.append(bytes(self._f_buffer[start:start + n]))
        self._h_pos += n
        if limit >= 0:
            limit -= n
    if self._e_writable:
        _bf_flush_and_rewind(self)
    while True:
        _bf_reset_read(self)
        n = _bf_fill_buffer(self)
        if n <= 0:
            break
        if limit >= 0 and n > limit:
            n = limit
        found = self._f_buffer.find(b"\n", 0, n)
        if found >= 0:
            chunks.append(bytes(self._f_buffer[0:found + 1]))
            self._h_pos = found + 1
            break
        chunks.append(bytes(self._f_buffer[0:n]))
        if n == limit:
            self._h_pos = n
            break
        if limit >= 0:
            limit -= n
    return b"".join(chunks)


def _bf_write(self: _Buffered, data: bytes) -> int:   # _io_BufferedWriter_write_impl
    if _bf_closed(self):
        raise ValueError("write to closed file")
    if not _bf_valid_read(self) and not _bf_valid_write(self):
        self._h_pos = 0
        self._i_raw_pos = 0
    length = bytes.__len__(data)
    avail = self._g_buffer_size - self._h_pos
    if length <= avail and length < self._g_buffer_size:
        self._f_buffer[self._h_pos:self._h_pos + length] = data
        if not _bf_valid_write(self) or self._k_write_pos > self._h_pos:
            self._k_write_pos = self._h_pos
        _bf_adjust_position(self, self._h_pos + length)
        if self._h_pos > self._l_write_end:
            self._l_write_end = self._h_pos
        return length
    try:
        _bf_flush_unlocked(self)
    except BlockingIOError:
        if self._d_readable:
            _bf_reset_read(self)
        kept = self._l_write_end - self._k_write_pos
        self._f_buffer[0:kept] = self._f_buffer[self._k_write_pos:self._l_write_end]
        self._l_write_end -= self._k_write_pos
        self._i_raw_pos -= self._k_write_pos
        self._h_pos -= self._k_write_pos
        self._k_write_pos = 0
        avail = self._g_buffer_size - self._l_write_end
        if length <= avail:
            self._f_buffer[self._l_write_end:self._l_write_end + length] = data
            self._l_write_end += length
            self._h_pos += length
            return length
        self._f_buffer[self._l_write_end:self._l_write_end + avail] = data[:avail]
        self._l_write_end += avail
        self._h_pos += avail
        raise BlockingIOError(_EAGAIN, "write could not complete without blocking", avail) from None
    offset = _bf_raw_offset(self)
    if offset != 0:
        _bf_raw_seek(self, -offset, 1)
        self._i_raw_pos -= offset
    remaining = length
    written = 0
    while remaining >= self._g_buffer_size:
        n = _bf_raw_write(self, data[written:])
        if n == -2:
            if remaining > self._g_buffer_size:
                self._f_buffer[0:self._g_buffer_size] = data[written:written + self._g_buffer_size]
                self._i_raw_pos = 0
                _bf_adjust_position(self, self._g_buffer_size)
                self._l_write_end = self._g_buffer_size
                written += self._g_buffer_size
                raise BlockingIOError(_EAGAIN, "write could not complete without blocking", written)
            break
        written += n
        remaining -= n
    if self._d_readable:
        _bf_reset_read(self)
    if remaining > 0:
        self._f_buffer[0:remaining] = data[written:written + remaining]
        written += remaining
    self._k_write_pos = 0
    self._l_write_end = remaining
    _bf_adjust_position(self, remaining)
    self._i_raw_pos = 0
    return written


def _bf_readinto_generic(self: _Buffered, b: object, readinto1: bool, shown: str) -> object:   # _buffered_readinto_generic
    _bf_check_initialized(self)
    target = _rw_buffer(b, shown)
    _bf_check_closed(self, "readinto of closed file")
    length = bytearray.__len__(target)
    written = 0
    n = _bf_readahead(self)
    if n > 0:
        if n >= length:
            target[0:length] = self._f_buffer[self._h_pos:self._h_pos + length]
            self._h_pos += length
            return length
        target[0:n] = self._f_buffer[self._h_pos:self._h_pos + n]
        self._h_pos += n
        written = n
    if self._e_writable:
        _bf_flush_and_rewind(self)
    _bf_reset_read(self)
    self._h_pos = 0
    remaining = length - written
    while remaining > 0:
        if remaining > self._g_buffer_size:
            n = _bf_raw_read(self, written, remaining, target)
        elif not (readinto1 and written):
            n = _bf_fill_buffer(self)
            if n > 0:
                if n > remaining:
                    n = remaining
                target[written:written + n] = self._f_buffer[self._h_pos:self._h_pos + n]
                self._h_pos += n
                written += n
                remaining -= n
                continue
        else:
            n = 0
        if n == 0 or (n == -2 and written > 0):
            break
        if n < 0:
            return None
        if readinto1:
            written += n
            break
        written += n
        remaining -= n
    return written


def _bf_repr(self: _Buffered) -> str:            # buffered_repr
    type_name = _tp_name(self)
    try:
        nameobj = getattr(self, "name")  # noqa: B009
    except ValueError:
        nameobj = _ABSENT
    except AttributeError:
        nameobj = _ABSENT
    if nameobj is _ABSENT:
        return "<" + type_name + ">"
    if self._o_in_repr:
        raise RuntimeError("reentrant call inside " + type_name + ".__repr__")
    self._o_in_repr = True
    try:
        shown = repr(nameobj)
    finally:
        self._o_in_repr = False
    return "<" + type_name + " name=" + shown + ">"


def _bf_init_args(shown: str, args: tuple[object, ...], kwds: dict[str, object]) -> tuple[object, int]:
    raw, buffer_size = _unpack(shown, args[1:], kwds, ("raw", "buffer_size"), 1, 2)
    return raw, DEFAULT_BUFFER_SIZE if buffer_size is _ABSENT else _ssize(buffer_size)


def _bf_make_methods(cls: type, shown: str, can_read: bool, can_write: bool) -> None:
    """The methods of one of the three classes, from the shared functions: what the C registers in each type's method table."""
    def init(*args: object, **kwds: object) -> None:
        self: _Buffered = args[0]  # type: ignore[assignment]
        raw, buffer_size = _bf_init_args(shown, args, kwds)
        self._b_ok = False
        self._c_detached = False
        if can_read:
            _check_ability(raw, "readable", "File or stream is not readable.")
        if can_write:
            _check_ability(raw, "writable", "File or stream is not writable.")
        self._a_raw = raw
        self._g_buffer_size = buffer_size
        self._d_readable = can_read
        self._e_writable = can_write
        _bf_init(self)
        if can_read:
            _bf_reset_read(self)
        if can_write:
            _bf_reset_write(self)
            self._h_pos = 0
        self._b_ok = True

    def read(*args: object, **kwds: object) -> object:
        n = _positional("read", shown + ".read", args, kwds, 0, 1)
        self: _Buffered = args[0]  # type: ignore[assignment]
        size = _ssize_or_none(args[1]) if n else -1
        _bf_check_initialized(self)
        if size < -1:
            raise ValueError("read length must be non-negative or -1")
        _bf_check_closed(self, "read of closed file")
        if size == -1:
            return _bf_read_all(self)
        res = _bf_read_fast(self, size)
        if res is not None:
            return res
        return _bf_read_generic(self, size)

    def read1(*args: object, **kwds: object) -> object:
        n = _positional("read1", shown + ".read1", args, kwds, 0, 1)
        self: _Buffered = args[0]  # type: ignore[assignment]
        size = _ssize(args[1]) if n else -1
        _bf_check_initialized(self)
        if size < 0:
            size = self._g_buffer_size
        _bf_check_closed(self, "read of closed file")
        if size == 0:
            return b""
        have = _bf_readahead(self)
        if have > 0:
            return _bf_read_fast(self, min(have, size))
        if self._e_writable:
            _bf_flush_and_rewind(self)
        _bf_reset_read(self)
        out = bytearray(size)
        r = _bf_raw_read(self, 0, size, out)
        if r == -2:
            r = 0
        return bytes(out[:r])

    def peek(*args: object, **kwds: object) -> bytes:
        n = _positional("peek", shown + ".peek", args, kwds, 0, 1)
        self: _Buffered = args[0]  # type: ignore[assignment]
        if n:
            _ssize(args[1])
        _bf_check_initialized(self)
        _bf_check_closed(self, "peek of closed file")
        if self._e_writable:
            _bf_flush_and_rewind(self)
        return _bf_peek_unlocked(self)

    def readinto(*args: object, **kwds: object) -> object:
        b = _one(shown + ".readinto", args, kwds)
        return _bf_readinto_generic(args[0], b, False, "readinto")  # type: ignore[arg-type]

    def readinto1(*args: object, **kwds: object) -> object:
        b = _one(shown + ".readinto1", args, kwds)
        return _bf_readinto_generic(args[0], b, True, "readinto1")  # type: ignore[arg-type]

    def readline(*args: object, **kwds: object) -> bytes:
        n = _positional("readline", shown + ".readline", args, kwds, 0, 1)
        self: _Buffered = args[0]  # type: ignore[assignment]
        size = _ssize_or_none(args[1]) if n else -1
        _bf_check_initialized(self)
        return _bf_readline(self, size)

    def write(*args: object, **kwds: object) -> int:
        b = _one(shown + ".write", args, kwds)
        self: _Buffered = args[0]  # type: ignore[assignment]
        data = _buffer(b)
        _bf_check_initialized(self)
        return _bf_write(self, data)

    def flush(*args: object, **kwds: object) -> object:
        _noargs(shown + ".flush", args, kwds)
        self: _Buffered = args[0]  # type: ignore[assignment]
        _bf_check_initialized(self)
        if not can_write:                        # _io__Buffered_simple_flush: the reader's flush is the raw's
            return self._a_raw.flush()  # type: ignore[attr-defined]
        _bf_check_closed(self, "flush of closed file")
        _bf_flush_and_rewind(self)
        return None

    def tell(*args: object, **kwds: object) -> int:
        _noargs(shown + ".tell", args, kwds)
        self: _Buffered = args[0]  # type: ignore[assignment]
        _bf_check_initialized(self)
        pos = _bf_raw_tell(self) - _bf_raw_offset(self)
        return 0 if pos < 0 else pos

    def seek(*args: object, **kwds: object) -> int:
        n = _positional("seek", shown + ".seek", args, kwds, 1, 2)
        self: _Buffered = args[0]  # type: ignore[assignment]
        targetobj = args[1]
        whence = _int(args[2]) if n > 1 else 0
        _bf_check_initialized(self)
        if (whence < 0 or whence > 2) and whence != 3 and whence != 4:   # SEEK_DATA and SEEK_HOLE pass
            raise ValueError("whence value " + str(whence) + " unsupported")
        _bf_check_closed(self, "seek of closed file")
        _check_ability(self._a_raw, "seekable", "File or stream is not seekable.")
        target = _off_t(targetobj)
        if (whence == 0 or whence == 1) and self._d_readable:
            current = _bf_raw_tell_or_cached(self)
            avail = _bf_readahead(self)
            if avail > 0:
                offset = target - (current - _bf_raw_offset(self)) if whence == 0 else target
                if -self._h_pos <= offset <= avail:
                    self._h_pos += offset
                    if current - avail + offset < 0:
                        return 0
                    return current - avail + offset
        if self._e_writable:
            _bf_flush_unlocked(self)
        if whence == 1:
            target -= _bf_raw_offset(self)
        res = _bf_raw_seek(self, target, whence)
        self._i_raw_pos = -1
        if self._d_readable:
            _bf_reset_read(self)
        return res

    def truncate(*args: object, **kwds: object) -> object:
        n = _positional("truncate", shown + ".truncate", args, kwds, 0, 1)
        self: _Buffered = args[0]  # type: ignore[assignment]
        pos = args[1] if n else None
        _bf_check_initialized(self)
        _bf_check_closed(self, "truncate of closed file")
        if not self._e_writable:
            _unsupported("truncate")
        _bf_flush_and_rewind(self)
        res = self._a_raw.truncate(pos)  # type: ignore[attr-defined]
        try:
            _bf_raw_tell(self)
        except BaseException:  # noqa: BLE001, S110
            pass
        return res

    def close(*args: object, **kwds: object) -> object:
        _noargs(shown + ".close", args, kwds)
        self: _Buffered = args[0]  # type: ignore[assignment]
        _bf_check_initialized(self)
        if _bf_closed(self):
            return None
        if self._finalizing:
            try:
                self._dealloc_warn(self)  # type: ignore[attr-defined]
            except BaseException:  # noqa: BLE001, S110
                pass
        exc: BaseException | None = None
        try:
            self.flush()  # type: ignore[attr-defined]
        except BaseException as e:  # noqa: BLE001
            exc = e
        try:
            res = self._a_raw.close()  # type: ignore[attr-defined]
        except BaseException as e:
            if exc is not None:
                raise e from exc
            raise
        finally:
            self._f_buffer = bytearray()
            self._j_read_end = 0
            self._h_pos = 0
        if exc is not None:
            raise exc
        return res

    def detach(*args: object, **kwds: object) -> object:
        _noargs(shown + ".detach", args, kwds)
        self: _Buffered = args[0]  # type: ignore[assignment]
        _bf_check_initialized(self)
        self.flush()  # type: ignore[attr-defined]
        raw = self._a_raw
        self._a_raw = None
        self._c_detached = True
        self._b_ok = False
        return raw

    def seekable(*args: object, **kwds: object) -> object:
        _noargs(shown + ".seekable", args, kwds)
        _bf_check_initialized(args[0])  # type: ignore[arg-type]
        return args[0]._a_raw.seekable()  # type: ignore[attr-defined]

    def readable(*args: object, **kwds: object) -> object:
        _noargs(shown + ".readable", args, kwds)
        _bf_check_initialized(args[0])  # type: ignore[arg-type]
        return args[0]._a_raw.readable()  # type: ignore[attr-defined]

    def writable(*args: object, **kwds: object) -> object:
        _noargs(shown + ".writable", args, kwds)
        _bf_check_initialized(args[0])  # type: ignore[arg-type]
        return args[0]._a_raw.writable()  # type: ignore[attr-defined]

    def fileno(*args: object, **kwds: object) -> object:
        _noargs(shown + ".fileno", args, kwds)
        _bf_check_initialized(args[0])  # type: ignore[arg-type]
        return args[0]._a_raw.fileno()  # type: ignore[attr-defined]

    def isatty(*args: object, **kwds: object) -> object:
        _noargs(shown + ".isatty", args, kwds)
        _bf_check_initialized(args[0])  # type: ignore[arg-type]
        return args[0]._a_raw.isatty()  # type: ignore[attr-defined]

    def _dealloc_warn(*args: object, **kwds: object) -> None:
        source = _one(shown + "._dealloc_warn", args, kwds)
        self: _Buffered = args[0]  # type: ignore[assignment]
        if self._b_ok and self._a_raw is not None:
            try:
                self._a_raw._dealloc_warn(source)  # type: ignore[attr-defined]
            except BaseException:  # noqa: BLE001, S110
                pass

    def __getstate__(*args: object, **kwds: object) -> object:
        _noargs(shown + ".__getstate__", args, kwds)
        raise TypeError("cannot pickle '" + type(args[0]).__name__ + "' instances")

    def __sizeof__(*args: object, **kwds: object) -> int:
        _noargs(shown + ".__sizeof__", args, kwds)
        self: _Buffered = args[0]  # type: ignore[assignment]
        return 152 + (self._g_buffer_size if bytearray.__len__(self._f_buffer) else 0)

    def __next__(*args: object, **kwds: object) -> object:   # buffered_iternext
        _noargs(shown + ".__next__", args, kwds)
        self: _Buffered = args[0]  # type: ignore[assignment]
        _bf_check_initialized(self)
        if type(self) is cls and can_read:
            line = _bf_readline(self, -1)
        else:
            line = self.readline()  # type: ignore[attr-defined]
            if not issubclass(type(line), bytes):
                raise OSError("readline() should have returned a bytes object, not '" + _tp_name(line) + "'")
        if bytes.__len__(line) == 0:
            raise StopIteration
        return line

    def __repr__(self: _Buffered) -> str:
        return _bf_repr(self)

    def __new__(klass: type, *args: object, **kwds: object) -> _Buffered:
        return _bf_new(klass)

    members: dict[str, object] = {"__init__": init, "flush": flush, "tell": tell, "seek": seek, "truncate": truncate, "close": close, "detach": detach,
                                  "seekable": seekable, "readable": readable, "writable": writable, "fileno": fileno, "isatty": isatty,
                                  "_dealloc_warn": _dealloc_warn, "__getstate__": __getstate__, "__sizeof__": __sizeof__, "__next__": __next__,
                                  "__repr__": __repr__, "__new__": __new__}
    if can_read:
        members.update({"read": read, "read1": read1, "peek": peek, "readinto": readinto, "readinto1": readinto1, "readline": readline})
    if can_write:
        members["write"] = write
    for name, member in members.items():
        member.__name__ = name  # type: ignore[attr-defined]
        member.__qualname__ = shown + "." + name  # type: ignore[attr-defined]
        setattr(cls, name, member)


def _bf_raw_property(self: _Buffered) -> object:
    _bf_check_initialized(self)
    return self._a_raw


def _bf_closed_property(self: _Buffered) -> object:
    _bf_check_initialized(self)
    return getattr(self._a_raw, "closed")  # noqa: B009


def _bf_name_property(self: _Buffered) -> object:
    _bf_check_initialized(self)
    return getattr(self._a_raw, "name")  # noqa: B009


def _bf_mode_property(self: _Buffered) -> object:
    _bf_check_initialized(self)
    return getattr(self._a_raw, "mode")  # noqa: B009


class BufferedReader(_BufferedIOBase):
    __slots__ = _BUFFERED_SLOTS
    raw = property(_bf_raw_property)
    closed = property(_bf_closed_property)
    name = property(_bf_name_property)
    mode = property(_bf_mode_property)


class BufferedWriter(_BufferedIOBase):
    __slots__ = _BUFFERED_SLOTS
    raw = property(_bf_raw_property)
    closed = property(_bf_closed_property)
    name = property(_bf_name_property)
    mode = property(_bf_mode_property)


class BufferedRandom(_BufferedIOBase):
    __slots__ = _BUFFERED_SLOTS
    raw = property(_bf_raw_property)
    closed = property(_bf_closed_property)
    name = property(_bf_name_property)
    mode = property(_bf_mode_property)


_bf_make_methods(BufferedReader, "BufferedReader", True, False)
_bf_make_methods(BufferedWriter, "BufferedWriter", False, True)
_bf_make_methods(BufferedRandom, "BufferedRandom", True, True)


# ---- BufferedRWPair ----

def _rw_forward(target: object, name: str, args: tuple[object, ...]) -> object:   # _forward_call
    if target is None:
        raise ValueError("I/O operation on uninitialized object")
    try:
        func = getattr(target, name)
    except AttributeError:
        raise AttributeError(name) from None
    return func(*args)


class BufferedRWPair(_BufferedIOBase):
    __slots__ = ("_a_reader", "_b_writer")

    def __new__(cls, *args: object, **kwds: object) -> BufferedRWPair:
        self: BufferedRWPair = _bella_new_instance(cls)
        self._a_reader = None
        self._b_writer = None
        return self

    def __init__(*args: object, **kwds: object) -> None:  # noqa: N805
        self: BufferedRWPair = args[0]  # type: ignore[assignment]
        if kwds:
            raise TypeError("BufferedRWPair() takes no keyword arguments")
        n = len(args) - 1
        if n < 2:
            raise TypeError("BufferedRWPair expected at least 2 arguments, got " + str(n))
        if n > 3:
            raise TypeError("BufferedRWPair expected at most 3 arguments, got " + str(n))
        reader, writer = args[1], args[2]
        buffer_size = _ssize(args[3]) if n > 2 else DEFAULT_BUFFER_SIZE
        _check_ability(reader, "readable", "File or stream is not readable.")
        _check_ability(writer, "writable", "File or stream is not writable.")
        self._a_reader = BufferedReader(reader, buffer_size)
        self._b_writer = BufferedWriter(writer, buffer_size)

    def read(*args: object, **kwds: object) -> object:  # noqa: N805
        if kwds:
            raise TypeError("BufferedRWPair.read() takes no keyword arguments")
        return _rw_forward(args[0]._a_reader, "read", args[1:])  # type: ignore[attr-defined]

    def peek(*args: object, **kwds: object) -> object:  # noqa: N805
        if kwds:
            raise TypeError("BufferedRWPair.peek() takes no keyword arguments")
        return _rw_forward(args[0]._a_reader, "peek", args[1:])  # type: ignore[attr-defined]

    def read1(*args: object, **kwds: object) -> object:  # noqa: N805
        if kwds:
            raise TypeError("BufferedRWPair.read1() takes no keyword arguments")
        return _rw_forward(args[0]._a_reader, "read1", args[1:])  # type: ignore[attr-defined]

    def readinto(*args: object, **kwds: object) -> object:  # noqa: N805
        if kwds:
            raise TypeError("BufferedRWPair.readinto() takes no keyword arguments")
        return _rw_forward(args[0]._a_reader, "readinto", args[1:])  # type: ignore[attr-defined]

    def readinto1(*args: object, **kwds: object) -> object:  # noqa: N805
        if kwds:
            raise TypeError("BufferedRWPair.readinto1() takes no keyword arguments")
        return _rw_forward(args[0]._a_reader, "readinto1", args[1:])  # type: ignore[attr-defined]

    def write(*args: object, **kwds: object) -> object:  # noqa: N805
        if kwds:
            raise TypeError("BufferedRWPair.write() takes no keyword arguments")
        return _rw_forward(args[0]._b_writer, "write", args[1:])  # type: ignore[attr-defined]

    def flush(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("BufferedRWPair.flush", args, kwds)
        return _rw_forward(args[0]._b_writer, "flush", ())  # type: ignore[attr-defined]

    def readable(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("BufferedRWPair.readable", args, kwds)
        return _rw_forward(args[0]._a_reader, "readable", ())  # type: ignore[attr-defined]

    def writable(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("BufferedRWPair.writable", args, kwds)
        return _rw_forward(args[0]._b_writer, "writable", ())  # type: ignore[attr-defined]

    def close(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("BufferedRWPair.close", args, kwds)
        self: BufferedRWPair = args[0]  # type: ignore[assignment]
        exc: BaseException | None = None
        try:
            _rw_forward(self._b_writer, "close", ())
        except BaseException as e:  # noqa: BLE001
            exc = e
        try:
            ret = _rw_forward(self._a_reader, "close", ())
        except BaseException as e:
            if exc is not None:
                raise e from exc
            raise
        if exc is not None:
            raise exc
        return ret

    def isatty(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("BufferedRWPair.isatty", args, kwds)
        self: BufferedRWPair = args[0]  # type: ignore[assignment]
        ret = _rw_forward(self._b_writer, "isatty", ())
        if ret is not False:
            return ret
        return _rw_forward(self._a_reader, "isatty", ())

    def __getstate__(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("BufferedRWPair.__getstate__", args, kwds)
        raise TypeError("cannot pickle '" + type(args[0]).__name__ + "' instances")

    @property
    def closed(self) -> object:
        if self._b_writer is None:
            raise RuntimeError("the BufferedRWPair object is being garbage-collected")
        return getattr(self._b_writer, "closed")  # noqa: B009


# ---- BytesIO (bytesio.c) ----

def _bio_check_closed(self: BytesIO) -> None:
    if self._a_buf is None:
        raise ValueError("I/O operation on closed file.")


def _bio_scan_eol(self: BytesIO, length: int) -> int:   # scan_eol: the bytes up to and including the next newline, at most `length` (-1: all)
    buf: bytearray = self._a_buf  # type: ignore[assignment]
    if self._b_pos >= self._c_string_size:
        return 0
    maxlen = self._c_string_size - self._b_pos
    if 0 <= length < maxlen:
        maxlen = length
    found = buf.find(b"\n", self._b_pos, self._b_pos + maxlen)
    return maxlen if found < 0 else found - self._b_pos + 1


def _bio_write_bytes(self: BytesIO, data: bytes) -> int:   # write_bytes
    _bio_check_closed(self)
    if self._d_exports > 0:
        raise BufferError("Existing exports of data: object cannot be re-sized")
    length = bytes.__len__(data)
    if length == 0:
        return 0
    buf: bytearray = self._a_buf  # type: ignore[assignment]
    endpos = self._b_pos + length
    if self._b_pos > self._c_string_size:
        buf[self._c_string_size:self._b_pos] = bytes(self._b_pos - self._c_string_size)
    buf[self._b_pos:endpos] = data
    if endpos > self._c_string_size:
        self._c_string_size = endpos
    self._b_pos = endpos
    return length


class BytesIO(_BufferedIOBase):
    __slots__ = ("_a_buf", "_b_pos", "_c_string_size", "_d_exports")

    def __new__(cls, *args: object, **kwds: object) -> BytesIO:
        self: BytesIO = _bella_new_instance(cls)
        self._a_buf = bytearray()
        self._b_pos = 0
        self._c_string_size = 0
        self._d_exports = 0
        return self

    def __init__(*args: object, **kwds: object) -> None:  # noqa: N805
        self: BytesIO = args[0]  # type: ignore[assignment]
        (initial_bytes,) = _unpack("BytesIO", args[1:], kwds, ("initial_bytes",), 0, 1)
        if self._d_exports > 0:
            raise BufferError("Existing exports of data: object cannot be re-sized")
        self._b_pos = 0
        self._c_string_size = 0
        if initial_bytes is not _ABSENT and initial_bytes is not None:
            data = _buffer(initial_bytes)
            self._a_buf = bytearray(data)
            self._c_string_size = bytes.__len__(data)
        else:
            self._a_buf = bytearray()

    def getvalue(*args: object, **kwds: object) -> bytes:  # noqa: N805
        _noargs("BytesIO.getvalue", args, kwds)
        self: BytesIO = args[0]  # type: ignore[assignment]
        _bio_check_closed(self)
        return bytes(self._a_buf[:self._c_string_size])  # type: ignore[index]

    def getbuffer(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("BytesIO.getbuffer", args, kwds)
        _bio_check_closed(args[0])  # type: ignore[arg-type]
        _refuse("BytesIO.getbuffer (a memoryview: the buffer protocol, [P2+])")
        return None

    def read(*args: object, **kwds: object) -> bytes:  # noqa: N805
        n = _positional("read", "BytesIO.read", args, kwds, 0, 1)
        self: BytesIO = args[0]  # type: ignore[assignment]
        size = _ssize_or_none(args[1]) if n else -1
        _bio_check_closed(self)
        avail = self._c_string_size - self._b_pos
        if avail < 0:
            avail = 0
        if size < 0 or size > avail:
            size = avail
        out = bytes(self._a_buf[self._b_pos:self._b_pos + size])  # type: ignore[index]
        self._b_pos += size
        return out

    def read1(*args: object, **kwds: object) -> bytes:  # noqa: N805
        n = _positional("read1", "BytesIO.read1", args, kwds, 0, 1)
        self: BytesIO = args[0]  # type: ignore[assignment]
        size = _ssize_or_none(args[1]) if n else -1
        return BytesIO.read(self, size)

    def readline(*args: object, **kwds: object) -> bytes:  # noqa: N805
        n = _positional("readline", "BytesIO.readline", args, kwds, 0, 1)
        self: BytesIO = args[0]  # type: ignore[assignment]
        size = _ssize_or_none(args[1]) if n else -1
        _bio_check_closed(self)
        count = _bio_scan_eol(self, size)
        out = bytes(self._a_buf[self._b_pos:self._b_pos + count])  # type: ignore[index]
        self._b_pos += count
        return out

    def readlines(*args: object, **kwds: object) -> list[bytes]:  # noqa: N805
        n = _positional("readlines", "BytesIO.readlines", args, kwds, 0, 1)
        self: BytesIO = args[0]  # type: ignore[assignment]
        arg = args[1] if n else None
        _bio_check_closed(self)
        if isinstance(arg, int):
            maxsize = _ssize(arg)
        elif arg is None:
            maxsize = -1
        else:
            raise TypeError("integer argument expected, got '" + _tp_name(arg) + "'")
        result: list[bytes] = []
        size = 0
        while True:
            count = _bio_scan_eol(self, -1)
            if count == 0:
                break
            result.append(bytes(self._a_buf[self._b_pos:self._b_pos + count]))  # type: ignore[index]
            self._b_pos += count
            size += count
            if maxsize > 0 and size >= maxsize:
                break
        return result

    def readinto(*args: object, **kwds: object) -> int:  # noqa: N805
        b = _one("BytesIO.readinto", args, kwds)
        self: BytesIO = args[0]  # type: ignore[assignment]
        target = _rw_buffer(b, "readinto")
        _bio_check_closed(self)
        length = bytearray.__len__(target)
        avail = self._c_string_size - self._b_pos
        if length > avail:
            length = avail
        if length < 0:
            length = 0
        target[0:length] = self._a_buf[self._b_pos:self._b_pos + length]  # type: ignore[index]
        self._b_pos += length
        return length

    def truncate(*args: object, **kwds: object) -> int:  # noqa: N805
        n = _positional("truncate", "BytesIO.truncate", args, kwds, 0, 1)
        self: BytesIO = args[0]  # type: ignore[assignment]
        arg = args[1] if n else None
        _bio_check_closed(self)
        if self._d_exports > 0:
            raise BufferError("Existing exports of data: object cannot be re-sized")
        if arg is None:
            size = self._b_pos
        else:
            size = _off(arg)
            if size < 0:
                raise ValueError("negative size value " + str(size))
        if size < self._c_string_size:
            self._c_string_size = size
            del self._a_buf[size:]  # type: ignore[union-attr]
        return size

    def seek(*args: object, **kwds: object) -> int:  # noqa: N805
        n = _positional("seek", "BytesIO.seek", args, kwds, 1, 2)
        self: BytesIO = args[0]  # type: ignore[assignment]
        pos = _off(args[1])
        whence = _int(args[2]) if n > 1 else 0
        _bio_check_closed(self)
        if pos < 0 and whence == 0:
            raise ValueError("negative seek value " + str(pos))
        if whence == 1:
            if pos > _SSIZE_MAX - self._b_pos:
                raise OverflowError("new position too large")
            pos += self._b_pos
        elif whence == 2:
            if pos > _SSIZE_MAX - self._c_string_size:
                raise OverflowError("new position too large")
            pos += self._c_string_size
        elif whence != 0:
            raise ValueError("invalid whence (" + str(whence) + ", should be 0, 1 or 2)")
        if pos < 0:
            pos = 0
        self._b_pos = pos
        return pos

    def tell(*args: object, **kwds: object) -> int:  # noqa: N805
        _noargs("BytesIO.tell", args, kwds)
        self: BytesIO = args[0]  # type: ignore[assignment]
        _bio_check_closed(self)
        return self._b_pos

    def write(*args: object, **kwds: object) -> int:  # noqa: N805
        b = _one("BytesIO.write", args, kwds)
        self: BytesIO = args[0]  # type: ignore[assignment]
        _bio_check_closed(self)
        if self._d_exports > 0:
            raise BufferError("Existing exports of data: object cannot be re-sized")
        return _bio_write_bytes(self, _buffer(b))

    def writelines(*args: object, **kwds: object) -> None:  # noqa: N805
        lines = _one("BytesIO.writelines", args, kwds)
        self: BytesIO = args[0]  # type: ignore[assignment]
        _bio_check_closed(self)
        for item in iter(lines):  # type: ignore[call-overload]
            _bio_write_bytes(self, _buffer(item))

    def close(*args: object, **kwds: object) -> None:  # noqa: N805
        _noargs("BytesIO.close", args, kwds)
        self: BytesIO = args[0]  # type: ignore[assignment]
        if self._d_exports > 0:
            raise BufferError("Existing exports of data: object cannot be re-sized")
        self._a_buf = None

    def flush(*args: object, **kwds: object) -> None:  # noqa: N805
        _noargs("BytesIO.flush", args, kwds)
        _bio_check_closed(args[0])  # type: ignore[arg-type]

    def isatty(*args: object, **kwds: object) -> bool:  # noqa: N805
        _noargs("BytesIO.isatty", args, kwds)
        _bio_check_closed(args[0])  # type: ignore[arg-type]
        return False

    def readable(*args: object, **kwds: object) -> bool:  # noqa: N805
        _noargs("BytesIO.readable", args, kwds)
        _bio_check_closed(args[0])  # type: ignore[arg-type]
        return True

    def writable(*args: object, **kwds: object) -> bool:  # noqa: N805
        _noargs("BytesIO.writable", args, kwds)
        _bio_check_closed(args[0])  # type: ignore[arg-type]
        return True

    def seekable(*args: object, **kwds: object) -> bool:  # noqa: N805
        _noargs("BytesIO.seekable", args, kwds)
        _bio_check_closed(args[0])  # type: ignore[arg-type]
        return True

    def __getstate__(*args: object, **kwds: object) -> tuple[object, ...]:  # noqa: N805
        _noargs("BytesIO.__getstate__", args, kwds)
        self: BytesIO = args[0]  # type: ignore[assignment]
        value = BytesIO.getvalue(self)
        d = _optional_attr(self, "__dict__")
        return value, self._b_pos, (None if d is _ABSENT or dict.__len__(d) == 0 else dict(d))  # type: ignore[arg-type,call-overload]

    def __setstate__(*args: object, **kwds: object) -> None:  # noqa: N805
        state = _one("BytesIO.__setstate__", args, kwds)
        self: BytesIO = args[0]  # type: ignore[assignment]
        if not issubclass(type(state), tuple) or tuple.__len__(state) < 3:  # type: ignore[arg-type]
            raise TypeError(_tp_name(self) + ".__setstate__ argument should be 3-tuple, got " + _tp_name(state))
        BytesIO.__init__(self, tuple.__getitem__(state, 0))  # type: ignore[arg-type]
        position = tuple.__getitem__(state, 1)  # type: ignore[arg-type]
        if not isinstance(position, int):
            raise TypeError("second item of state must be an integer, not " + _tp_name(position))
        pos = _ssize(position)
        if pos < 0:
            raise ValueError("position value cannot be negative")
        self._b_pos = pos
        d = tuple.__getitem__(state, 2)  # type: ignore[arg-type]
        if d is not None:
            if not isinstance(d, dict):
                raise TypeError("third item of state should be a dict, got a " + _tp_name(d))
            self.__dict__ = d  # type: ignore[attr-defined]

    def __sizeof__(*args: object, **kwds: object) -> int:  # noqa: N805
        _noargs("BytesIO.__sizeof__", args, kwds)
        self: BytesIO = args[0]  # type: ignore[assignment]
        return 64 + (bytearray.__len__(self._a_buf) + 1 if self._a_buf is not None else 0)

    def __iter__(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("BytesIO.__iter__", args, kwds)
        return args[0]

    def __next__(*args: object, **kwds: object) -> bytes:  # noqa: N805
        _noargs("BytesIO.__next__", args, kwds)
        self: BytesIO = args[0]  # type: ignore[assignment]
        _bio_check_closed(self)
        count = _bio_scan_eol(self, -1)
        if count == 0:
            raise StopIteration
        out = bytes(self._a_buf[self._b_pos:self._b_pos + count])  # type: ignore[index]
        self._b_pos += count
        return out

    @property
    def closed(self) -> bool:
        return self._a_buf is None


class _BytesIOBuffer:                            # the exporter behind BytesIO.getbuffer: no instances from Python, and getbuffer stops by name
    __slots__ = ()


# ---- IncrementalNewlineDecoder (textio.c) ----

_NEWLINES_BY_SEEN = (None, "\n", "\r", ("\r", "\n"), "\r\n", ("\n", "\r\n"), ("\r", "\r\n"), ("\r", "\n", "\r\n"))


def _nl_decode(self: IncrementalNewlineDecoder, input: object, final: bool) -> str:   # _PyIncrementalNewlineDecoder_decode
    if not self._a_ok:
        raise ValueError("IncrementalNewlineDecoder.__init__() not called")
    if self._b_decoder is not None:
        output = self._b_decoder.decode(input, True if final else False)  # type: ignore[attr-defined]
    else:
        output = input
    if not isinstance(output, str):
        raise TypeError("decoder should return a string result, not '" + _tp_name(output) + "'")
    text: str = str.__str__(output) if type(output) is not str else output
    if self._c_pendingcr and (final or str.__len__(text) > 0):
        text = "\r" + text
        self._c_pendingcr = False
    if not final and str.__len__(text) > 0 and text[-1] == "\r":
        text = text[:-1]
        self._c_pendingcr = True
    crlf = text.count("\r\n")
    cr = text.count("\r") - crlf
    lf = text.count("\n") - crlf
    seen = 0
    if lf:
        seen |= 1
    if cr:
        seen |= 2
    if crlf:
        seen |= 4
    self._d_seennl |= seen
    if self._e_translate:
        if crlf:
            text = text.replace("\r\n", "\n")
        if cr:
            text = text.replace("\r", "\n")
    return text


class IncrementalNewlineDecoder:
    __slots__ = ("_a_ok", "_b_decoder", "_c_pendingcr", "_d_seennl", "_e_translate", "_f_errors")

    def __new__(cls, *args: object, **kwds: object) -> IncrementalNewlineDecoder:
        self: IncrementalNewlineDecoder = _bella_new_instance(cls)
        self._a_ok = False
        self._b_decoder = None
        self._c_pendingcr = False
        self._d_seennl = 0
        self._e_translate = False
        self._f_errors = "strict"
        return self

    def __init__(*args: object, **kwds: object) -> None:  # noqa: N805
        self: IncrementalNewlineDecoder = args[0]  # type: ignore[assignment]
        decoder, translate, errors = _unpack("IncrementalNewlineDecoder", args[1:], kwds, ("decoder", "translate", "errors"), 2, 3)
        self._a_ok = False
        self._b_decoder = decoder
        self._e_translate = True if translate else False
        self._f_errors = "strict" if errors is _ABSENT else errors
        self._d_seennl = 0
        self._c_pendingcr = False
        self._a_ok = True

    def decode(*args: object, **kwds: object) -> str:  # noqa: N805
        input, final = _unpack("decode", args[1:], kwds, ("input", "final"), 1, 2)  # noqa: A001
        return _nl_decode(args[0], input, final is not _ABSENT and (True if final else False))  # type: ignore[arg-type]

    def getstate(*args: object, **kwds: object) -> tuple[object, int]:  # noqa: N805
        _noargs("IncrementalNewlineDecoder.getstate", args, kwds)
        self: IncrementalNewlineDecoder = args[0]  # type: ignore[assignment]
        if not self._a_ok:
            raise ValueError("IncrementalNewlineDecoder.__init__() not called")
        if self._b_decoder is not None:
            state = self._b_decoder.getstate()  # type: ignore[attr-defined]
            if not isinstance(state, tuple) or tuple.__len__(state) != 2:
                raise TypeError("illegal decoder state")
            buffer, flag = tuple.__getitem__(state, 0), tuple.__getitem__(state, 1)
            if not isinstance(flag, int):
                raise TypeError("illegal decoder state")
            flag = int.__index__(flag) & ((1 << 64) - 1)
        else:
            buffer = b""
            flag = 0
        flag <<= 1
        if self._c_pendingcr:
            flag |= 1
        return buffer, flag

    def setstate(*args: object, **kwds: object) -> None:  # noqa: N805
        state = _one("IncrementalNewlineDecoder.setstate", args, kwds)
        self: IncrementalNewlineDecoder = args[0]  # type: ignore[assignment]
        if not self._a_ok:
            raise ValueError("IncrementalNewlineDecoder.__init__() not called")
        if not isinstance(state, tuple):
            raise TypeError("state argument must be a tuple")
        if tuple.__len__(state) != 2:
            raise TypeError("setstate(): illegal state argument")
        buffer, flag = tuple.__getitem__(state, 0), tuple.__getitem__(state, 1)
        if not isinstance(flag, int):
            raise TypeError("setstate(): illegal state argument")
        flag = int.__index__(flag) & ((1 << 64) - 1)
        self._c_pendingcr = (flag & 1) != 0
        flag >>= 1
        if self._b_decoder is not None:
            self._b_decoder.setstate((buffer, flag))  # type: ignore[attr-defined]

    def reset(*args: object, **kwds: object) -> None:  # noqa: N805
        _noargs("IncrementalNewlineDecoder.reset", args, kwds)
        self: IncrementalNewlineDecoder = args[0]  # type: ignore[assignment]
        if not self._a_ok:
            raise ValueError("IncrementalNewlineDecoder.__init__() not called")
        self._d_seennl = 0
        self._c_pendingcr = False
        if self._b_decoder is not None:
            self._b_decoder.reset()  # type: ignore[attr-defined]

    @property
    def newlines(self) -> object:
        if not self._a_ok:
            raise ValueError("IncrementalNewlineDecoder.__init__() not called")
        return _NEWLINES_BY_SEEN[self._d_seennl]


# ---- TextIOWrapper ----

def _find_line_ending(translated: bool, universal: bool, readnl: object, text: str, start: int, end: int, after: object) -> tuple[int, int]:
    """_PyIO_find_line_ending over text[start:end]: the length of the first line with its ending, or -1 and how much holds no ending;
    `after` is what the C reads past `end` (the NUL that ends its strings), which decides a '\\r' at the end in universal mode."""
    length = end - start
    if translated:
        pos = str.find(text, "\n", start, end)
        return (pos - start + 1, 0) if pos >= 0 else (-1, length)
    if universal:
        s = start
        while True:
            while s < end and text[s] > "\r":
                s += 1
            if s >= end:
                return -1, length
            ch = text[s]
            s += 1
            if ch == "\n":
                return s - start, 0
            if ch == "\r":
                following = text[s] if s < end else after
                if following == "\n":
                    return s - start + 1, 0
                return s - start, 0
    nl: str = readnl  # type: ignore[assignment]
    nl_len = str.__len__(nl)
    if nl_len == 1:
        pos = str.find(text, nl, start, end)
        return (pos - start + 1, 0) if pos >= 0 else (-1, length)
    pos = str.find(text, nl, start, end)
    if pos >= 0:
        return pos - start + nl_len, 0
    pos = str.find(text, nl[0], start, end)
    return -1, (pos - start if pos >= 0 else length)


def _tw_check_attached(self: TextIOWrapper) -> None:   # CHECK_ATTACHED
    if not self._a_ok:
        raise ValueError("I/O operation on uninitialized object")
    if self._b_detached:
        raise ValueError("underlying buffer has been detached")


def _tw_check_closed(self: TextIOWrapper) -> None:   # CHECK_CLOSED
    if type(self) is TextIOWrapper:
        if getattr(self._c_buffer, "closed"):  # noqa: B009
            raise ValueError("I/O operation on closed file.")
    else:
        _check_closed(self)


def _tw_validate_newline(newline: object) -> None:
    if newline is not None and newline != "" and newline != "\n" and newline != "\r" and newline != "\r\n":
        raise ValueError("illegal newline value: " + str(newline))


def _tw_set_decoded_chars(self: TextIOWrapper, chars: str | None) -> None:
    self._j_decoded_chars = chars
    self._k_decoded_chars_used = 0


def _tw_get_decoded_chars(self: TextIOWrapper, n: int) -> str:   # textiowrapper_get_decoded_chars
    if self._j_decoded_chars is None:
        return ""
    avail = str.__len__(self._j_decoded_chars) - self._k_decoded_chars_used
    if n < 0 or n > avail:
        n = avail
    chars = self._j_decoded_chars[self._k_decoded_chars_used:self._k_decoded_chars_used + n]
    self._k_decoded_chars_used += n
    return chars


def _tw_decode(decoder: object, data: bytes, eof: bool) -> str:   # _textiowrapper_decode
    if type(decoder) is IncrementalNewlineDecoder:
        decoded = _nl_decode(decoder, data, eof)
    else:
        decoded = decoder.decode(data, True if eof else False)  # type: ignore[attr-defined]
    if not isinstance(decoded, str):
        raise TypeError("decoder should return a string result, not '" + _tp_name(decoded) + "'")
    return decoded


def _tw_decoder_state(self: TextIOWrapper) -> tuple[bytes, object]:
    state = self._h_decoder.getstate()  # type: ignore[attr-defined]
    if not isinstance(state, tuple):
        raise TypeError("illegal decoder state")
    if tuple.__len__(state) != 2:
        raise TypeError("illegal decoder state")
    dec_buffer, dec_flags = tuple.__getitem__(state, 0), tuple.__getitem__(state, 1)
    if not isinstance(dec_buffer, bytes):
        raise TypeError("illegal decoder state: the first item should be a bytes object, not '" + _tp_name(dec_buffer) + "'")
    return dec_buffer, dec_flags


def _tw_read_chunk(self: TextIOWrapper, size_hint: int) -> bool:   # textiowrapper_read_chunk: True unless at the end
    if self._h_decoder is None:
        _unsupported("not readable")
    dec_buffer: bytes = b""
    dec_flags: object = 0
    if self._f_telling:
        dec_buffer, dec_flags = _tw_decoder_state(self)
    if size_hint > 0:
        size_hint = int(max(self._l_b2cratio, 1.0) * size_hint)
    chunk_size = max(self._e_chunk_size, size_hint)
    input_chunk = self._c_buffer.read1(chunk_size) if self._g_has_read1 else self._c_buffer.read(chunk_size)  # type: ignore[attr-defined]
    if not _is_bytes_like(input_chunk):
        raise TypeError("underlying " + ("read1" if self._g_has_read1 else "read") + "() should have returned a bytes-like object, not '" + _tp_name(input_chunk) + "'")
    data = bytes(input_chunk)  # type: ignore[arg-type]
    nbytes = bytes.__len__(data)
    eof = nbytes == 0
    decoded_chars = _tw_decode(self._h_decoder, data, eof)
    _tw_set_decoded_chars(self, decoded_chars)
    nchars = str.__len__(decoded_chars)
    self._l_b2cratio = nbytes / nchars if nchars > 0 else 0.0
    if nchars > 0:
        eof = False
    if self._f_telling:
        self._m_snapshot = (dec_flags, dec_buffer + data)
    return not eof


def _tw_writeflush(self: TextIOWrapper) -> None:   # _textiowrapper_writeflush
    if self._n_pending is None:
        return
    pending = self._n_pending
    self._n_pending = None
    self._o_pending_count = 0
    data = b"".join(pending)
    self._c_buffer.write(data)  # type: ignore[attr-defined]


def _tw_readline(self: TextIOWrapper, limit: int) -> str:   # _textiowrapper_readline
    _tw_check_closed(self)
    _tw_writeflush(self)
    chunked = 0
    chunks: list[str] = []
    remaining: str | None = None
    line: str | None = None
    start = endpos = offset_to_buffer = 0
    while True:
        res = True
        while self._j_decoded_chars is None or str.__len__(self._j_decoded_chars) == 0:
            res = _tw_read_chunk(self, 0)
            if not res:
                break
        if not res:
            _tw_set_decoded_chars(self, None)
            self._m_snapshot = None
            start = endpos = offset_to_buffer = 0
            line = None
            break
        if remaining is None:
            line = self._j_decoded_chars
            start = self._k_decoded_chars_used
            offset_to_buffer = 0
        else:
            line = remaining + self._j_decoded_chars  # type: ignore[operator]
            start = 0
            offset_to_buffer = str.__len__(remaining)
            remaining = None
        line_len = str.__len__(line)  # type: ignore[arg-type]
        found, consumed = _find_line_ending(self._p_readtranslate, self._q_readuniversal, self._r_readnl, line, start, line_len, "")  # type: ignore[arg-type]
        if found >= 0:
            endpos = found + start
            if limit >= 0 and (endpos - start) + chunked >= limit:
                endpos = start + limit - chunked
            break
        endpos = consumed + start
        if limit >= 0 and (endpos - start) + chunked >= limit:
            endpos = start + limit - chunked
            break
        if endpos > start:
            chunks.append(line[start:endpos])  # type: ignore[index]
            chunked += endpos - start
        if endpos < line_len:
            remaining = line[endpos:line_len]  # type: ignore[index]
        line = None
        _tw_set_decoded_chars(self, None)
    if line is not None:
        self._k_decoded_chars_used = endpos - offset_to_buffer
        if start > 0 or endpos < str.__len__(line):
            line = line[start:endpos]
    if remaining is not None:
        chunks.append(remaining)
    if chunks:
        if line is not None:
            chunks.append(line)
        return "".join(chunks)
    return "" if line is None else line


def _tw_pack_cookie(position: int, dec_flags: int = 0, bytes_to_feed: int = 0, need_eof: bool = False, chars_to_skip: int = 0) -> int:
    """textiowrapper_build_cookie: the fields' C sizes, little-endian: start_pos (Py_off_t, 8 bytes), dec_flags, bytes_to_feed and
    chars_to_skip (int, 4 bytes each), need_eof (char)."""
    return position | (dec_flags << 64) | (bytes_to_feed << 96) | (chars_to_skip << 128) | ((1 if need_eof else 0) << 160)


def _tw_unpack_cookie(bigint: int) -> tuple[int, int, int, bool, int]:   # textiowrapper_parse_cookie
    rest, position = divmod(bigint, 1 << 64)
    rest, dec_flags = divmod(rest, 1 << 32)
    rest, bytes_to_feed = divmod(rest, 1 << 32)
    need_eof, chars_to_skip = divmod(rest, 1 << 32)
    return position, dec_flags, bytes_to_feed, need_eof != 0, chars_to_skip


def _tw_set_newline(self: TextIOWrapper, newline: str | None) -> None:   # what __init__ keeps of newline: readnl, readuniversal, readtranslate, writetranslate, writenl
    self._r_readnl = newline
    self._q_readuniversal = newline is None or newline == ""
    self._p_readtranslate = newline is None
    self._x_writetranslate = newline is None or newline != ""
    self._y_writenl = None
    if not self._q_readuniversal and newline is not None and newline != "\n":
        self._y_writenl = newline


def _tw_decoder_setstate(self: TextIOWrapper, start_pos: int, dec_flags: object) -> None:
    """_textiowrapper_decoder_setstate: at the start of the stream the decoder is reset, not given (b"", 0), for the codecs whose
    state at the start is not that (UTF-16's BOM); IncrementalNewlineDecoder's reset also forgets the newlines seen."""
    if start_pos == 0 and dec_flags == 0:
        self._h_decoder.reset()  # type: ignore[attr-defined]
    else:
        self._h_decoder.setstate((b"", dec_flags))  # type: ignore[attr-defined]


def _tw_encoder_reset(self: TextIOWrapper, start_of_stream: bool) -> None:   # _textiowrapper_encoder_reset
    if start_of_stream:
        self._i_encoder.reset()  # type: ignore[attr-defined]
        self._s_encoding_start_of_stream = True
    else:
        self._i_encoder.setstate(0)  # type: ignore[attr-defined]
        self._s_encoding_start_of_stream = False


class TextIOWrapper(_TextIOBase):
    __slots__ = ("_a_ok", "_b_detached", "_c_buffer", "_d_encoding", "_e_chunk_size", "_f_telling", "_g_has_read1", "_h_decoder", "_i_encoder",
                 "_j_decoded_chars", "_k_decoded_chars_used", "_l_b2cratio", "_m_snapshot", "_n_pending", "_o_pending_count", "_p_readtranslate",
                 "_q_readuniversal", "_r_readnl", "_s_encoding_start_of_stream", "_t_errors", "_u_seekable", "_v_line_buffering", "_w_write_through",
                 "_x_writetranslate", "_y_writenl", "_z_in_repr", "_finalizing")

    def __new__(cls, *args: object, **kwds: object) -> TextIOWrapper:
        self: TextIOWrapper = _bella_new_instance(cls)
        self._a_ok = False
        self._b_detached = False
        self._c_buffer = None
        self._d_encoding = None
        self._e_chunk_size = 8192
        self._f_telling = False
        self._g_has_read1 = False
        self._h_decoder = None
        self._i_encoder = None
        self._j_decoded_chars = None
        self._k_decoded_chars_used = 0
        self._l_b2cratio = 0.0
        self._m_snapshot = None
        self._n_pending = None
        self._o_pending_count = 0
        self._p_readtranslate = False
        self._q_readuniversal = False
        self._r_readnl = None
        self._s_encoding_start_of_stream = False
        self._t_errors = None
        self._u_seekable = False
        self._v_line_buffering = False
        self._w_write_through = False
        self._x_writetranslate = False
        self._y_writenl = None
        self._z_in_repr = False
        self._finalizing = False
        return self

    def __init__(*args: object, **kwds: object) -> None:  # noqa: N805
        self: TextIOWrapper = args[0]  # type: ignore[assignment]
        buffer, encoding, errors, newline, line_buffering, write_through = _unpack(
            "TextIOWrapper", args[1:], kwds, ("buffer", "encoding", "errors", "newline", "line_buffering", "write_through"), 1, 6)
        if encoding is _ABSENT or encoding is None:
            encoding = None
        elif not isinstance(encoding, str):
            raise TypeError("TextIOWrapper() argument 'encoding' must be str or None, not " + _tp_name(encoding))
        else:
            _c_string(encoding, "TextIOWrapper() argument 'encoding'")
        if errors is _ABSENT or errors is None:
            errors = "strict"
        elif not isinstance(errors, str):
            raise TypeError("TextIOWrapper() argument 'errors' must be str or None, not " + _tp_name(errors)[:50])
        else:
            _c_string(errors, "TextIOWrapper() argument 'errors'")
        if newline is _ABSENT or newline is None:
            newline = None
        elif not isinstance(newline, str):
            raise TypeError("TextIOWrapper() argument 'newline' must be str or None, not " + _tp_name(newline))
        else:
            _c_string(newline, "TextIOWrapper() argument 'newline'")
        line_buffering = line_buffering is not _ABSENT and (True if line_buffering else False)
        write_through = write_through is not _ABSENT and (True if write_through else False)
        self._a_ok = False
        self._b_detached = False
        _tw_validate_newline(newline)
        # the C clears what an earlier __init__ left: buffer, encoding, encoder, decoder, readnl, decoded chars, pending bytes, snapshot,
        # errors, the counts and the ratio (A13 #3)
        self._c_buffer = None
        self._d_encoding = None
        self._h_decoder = None
        self._i_encoder = None
        self._r_readnl = None
        self._j_decoded_chars = None
        self._k_decoded_chars_used = 0
        self._n_pending = None
        self._o_pending_count = 0
        self._m_snapshot = None
        self._t_errors = None
        self._l_b2cratio = 0.0
        if encoding is None:
            encoding = "utf-8"                   # _Py_GetLocaleEncoding in UTF-8 mode (D-15)
        elif encoding == "locale":
            encoding = "UTF-8"
        codec_info = _io_call("lookup_text", encoding)
        self._d_encoding = encoding
        self._t_errors = errors
        self._e_chunk_size = 8192
        self._v_line_buffering = line_buffering
        self._w_write_through = write_through
        _tw_set_newline(self, newline)
        self._c_buffer = buffer
        if buffer.readable():  # type: ignore[attr-defined]
            self._h_decoder = codec_info.incrementaldecoder(errors)
            if self._q_readuniversal:
                self._h_decoder = IncrementalNewlineDecoder(self._h_decoder, self._p_readtranslate)
        if buffer.writable():  # type: ignore[attr-defined]
            self._i_encoder = codec_info.incrementalencoder(errors)
        self._u_seekable = self._f_telling = True if buffer.seekable() else False  # type: ignore[attr-defined]
        self._g_has_read1 = hasattr(buffer, "read1")
        self._s_encoding_start_of_stream = False
        if self._u_seekable and self._i_encoder is not None:
            cookie = buffer.tell()  # type: ignore[attr-defined]
            if cookie == 0:
                self._s_encoding_start_of_stream = True
            else:
                self._i_encoder.setstate(0)
        self._a_ok = True

    def detach(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("TextIOWrapper.detach", args, kwds)
        self: TextIOWrapper = args[0]  # type: ignore[assignment]
        self.flush()  # type: ignore[attr-defined]
        _tw_check_attached(self)
        buffer = self._c_buffer
        self._c_buffer = None
        self._b_detached = True
        return buffer

    def reconfigure(*args: object, **kwds: object) -> None:  # noqa: N805
        _refuse("TextIOWrapper.reconfigure (_io: step 3b)")

    def write(*args: object, **kwds: object) -> int:  # noqa: N805
        text = _one("TextIOWrapper.write", args, kwds)
        self: TextIOWrapper = args[0]  # type: ignore[assignment]
        if not isinstance(text, str):
            raise TypeError("write() argument must be str, not " + _tp_name(text))
        _tw_check_attached(self)
        _tw_check_closed(self)
        if self._i_encoder is None:
            _unsupported("not writable")
        textlen = str.__len__(text)
        haslf = False
        if (self._x_writetranslate and self._y_writenl is not None) or self._v_line_buffering:
            if str.find(text, "\n") != -1:
                haslf = True
        if haslf and self._x_writetranslate and self._y_writenl is not None:
            text = text.replace("\n", self._y_writenl)
        text_needflush = self._w_write_through
        needflush = self._v_line_buffering and (haslf or str.find(text, "\r") != -1)
        b = self._i_encoder.encode(text)  # type: ignore[attr-defined]
        self._s_encoding_start_of_stream = False
        if not isinstance(b, bytes):
            raise TypeError("encoder should return a bytes object, not '" + _tp_name(b) + "'")
        bytes_len = bytes.__len__(b)
        if bytes_len >= self._e_chunk_size:
            while self._n_pending is not None:
                _tw_writeflush(self)
        if bytes_len > 0:
            if self._n_pending is None:
                self._n_pending = [b]
            else:
                self._n_pending.append(b)
            self._o_pending_count += bytes_len
        if self._o_pending_count >= self._e_chunk_size or needflush or text_needflush:
            _tw_writeflush(self)
        if needflush:
            self._c_buffer.flush()  # type: ignore[attr-defined]
        if self._m_snapshot is not None:
            _tw_set_decoded_chars(self, None)
            self._m_snapshot = None
        if self._h_decoder is not None:
            self._h_decoder.reset()  # type: ignore[attr-defined]
        return textlen

    def read(*args: object, **kwds: object) -> str:  # noqa: N805
        n = _positional("read", "TextIOWrapper.read", args, kwds, 0, 1)
        self: TextIOWrapper = args[0]  # type: ignore[assignment]
        size = _ssize_or_none(args[1]) if n else -1
        _tw_check_attached(self)
        _tw_check_closed(self)
        if self._h_decoder is None:
            _unsupported("not readable")
        _tw_writeflush(self)
        if size < 0:
            data = self._c_buffer.read()  # type: ignore[attr-defined]
            if data is None:
                raise BlockingIOError("Read returned None.")
            if not isinstance(data, bytes):
                raise TypeError("underlying read() should have returned a bytes object, not '" + _tp_name(data) + "'")
            decoded = _tw_decode(self._h_decoder, data, True)
            result = _tw_get_decoded_chars(self, -1) + decoded
            if self._m_snapshot is not None:
                _tw_set_decoded_chars(self, None)
                self._m_snapshot = None
            return result
        remaining = size
        chunks: list[str] = []
        result = _tw_get_decoded_chars(self, size)
        remaining -= str.__len__(result)
        res = True
        while remaining > 0 and res:
            res = _tw_read_chunk(self, remaining)
            if str.__len__(result) > 0:
                chunks.append(result)
            result = _tw_get_decoded_chars(self, remaining)
            remaining -= str.__len__(result)
        if chunks:
            chunks.append(result)
            return "".join(chunks)
        return result

    def readline(*args: object, **kwds: object) -> str:  # noqa: N805
        n = _positional("readline", "TextIOWrapper.readline", args, kwds, 0, 1)
        self: TextIOWrapper = args[0]  # type: ignore[assignment]
        size = _ssize(args[1]) if n else -1
        _tw_check_attached(self)
        return _tw_readline(self, size)

    def flush(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("TextIOWrapper.flush", args, kwds)
        self: TextIOWrapper = args[0]  # type: ignore[assignment]
        _tw_check_attached(self)
        _tw_check_closed(self)
        self._f_telling = self._u_seekable
        _tw_writeflush(self)
        return self._c_buffer.flush()  # type: ignore[attr-defined]

    def close(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("TextIOWrapper.close", args, kwds)
        self: TextIOWrapper = args[0]  # type: ignore[assignment]
        _tw_check_attached(self)
        if getattr(self._c_buffer, "closed"):  # noqa: B009
            return None
        if self._b_detached:
            return None
        if self._finalizing:
            try:
                self._c_buffer._dealloc_warn(self)  # type: ignore[attr-defined]
            except BaseException:  # noqa: BLE001, S110
                pass
        exc: BaseException | None = None
        try:
            self.flush()  # type: ignore[attr-defined]
        except BaseException as e:  # noqa: BLE001
            exc = e
        try:
            res = self._c_buffer.close()  # type: ignore[attr-defined]
        except BaseException as e:
            if exc is not None:
                raise e from exc
            raise
        if exc is not None:
            raise exc
        return res

    def fileno(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("TextIOWrapper.fileno", args, kwds)
        _tw_check_attached(args[0])  # type: ignore[arg-type]
        return args[0]._c_buffer.fileno()  # type: ignore[attr-defined]

    def seekable(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("TextIOWrapper.seekable", args, kwds)
        _tw_check_attached(args[0])  # type: ignore[arg-type]
        return args[0]._c_buffer.seekable()  # type: ignore[attr-defined]

    def readable(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("TextIOWrapper.readable", args, kwds)
        _tw_check_attached(args[0])  # type: ignore[arg-type]
        return args[0]._c_buffer.readable()  # type: ignore[attr-defined]

    def writable(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("TextIOWrapper.writable", args, kwds)
        _tw_check_attached(args[0])  # type: ignore[arg-type]
        return args[0]._c_buffer.writable()  # type: ignore[attr-defined]

    def isatty(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("TextIOWrapper.isatty", args, kwds)
        _tw_check_attached(args[0])  # type: ignore[arg-type]
        return args[0]._c_buffer.isatty()  # type: ignore[attr-defined]

    def truncate(*args: object, **kwds: object) -> object:  # noqa: N805
        n = _positional("truncate", "TextIOWrapper.truncate", args, kwds, 0, 1)
        self: TextIOWrapper = args[0]  # type: ignore[assignment]
        pos = args[1] if n else None
        _tw_check_attached(self)
        self.flush()  # type: ignore[attr-defined]
        return self._c_buffer.truncate(pos)  # type: ignore[attr-defined]

    def seek(*args: object, **kwds: object) -> object:  # noqa: N805
        n = _positional("seek", "TextIOWrapper.seek", args, kwds, 1, 2)
        self: TextIOWrapper = args[0]  # type: ignore[assignment]
        cookie_obj = args[1]
        whence = _int(args[2]) if n > 1 else 0
        _tw_check_attached(self)
        _tw_check_closed(self)
        if not self._u_seekable:
            _unsupported("underlying stream is not seekable")
        if whence == 1:
            if cookie_obj != 0:
                _unsupported("can't do nonzero cur-relative seeks")
            cookie_obj = self.tell()  # type: ignore[attr-defined]
            whence = 0
        elif whence == 2:
            if cookie_obj != 0:
                _unsupported("can't do nonzero end-relative seeks")
            self.flush()  # type: ignore[attr-defined]
            _tw_set_decoded_chars(self, None)
            self._m_snapshot = None
            if self._h_decoder is not None:
                self._h_decoder.reset()  # type: ignore[attr-defined]
            res = self._c_buffer.seek(0, 2)  # type: ignore[attr-defined]
            if self._i_encoder is not None:
                _tw_encoder_reset(self, res == 0)
            return res
        elif whence != 0:
            raise ValueError("invalid whence (" + str(whence) + ", should be 0, 1 or 2)")
        if cookie_obj < 0:  # type: ignore[operator]
            raise ValueError("negative seek position " + repr(cookie_obj))
        self.flush()  # type: ignore[attr-defined]
        cookie = _number_index(cookie_obj)
        start_pos, dec_flags, bytes_to_feed, need_eof, chars_to_skip = _tw_unpack_cookie(cookie)
        self._c_buffer.seek(start_pos)  # type: ignore[attr-defined]
        _tw_set_decoded_chars(self, None)
        self._m_snapshot = None
        if self._h_decoder is not None:
            _tw_decoder_setstate(self, start_pos, dec_flags)
        if chars_to_skip:
            input_chunk = self._c_buffer.read(bytes_to_feed)  # type: ignore[attr-defined]
            if not isinstance(input_chunk, bytes):
                raise TypeError("underlying read() should have returned a bytes object, not '" + _tp_name(input_chunk) + "'")
            self._m_snapshot = (dec_flags, input_chunk)
            decoded = self._h_decoder.decode(input_chunk, True if need_eof else False)  # type: ignore[attr-defined]
            if not isinstance(decoded, str):
                raise TypeError("decoder should return a string result, not '" + _tp_name(decoded) + "'")
            _tw_set_decoded_chars(self, decoded)
            if str.__len__(decoded) < chars_to_skip:
                raise OSError("can't restore logical file position")
            self._k_decoded_chars_used = chars_to_skip
        else:
            self._m_snapshot = (dec_flags, b"")
        if self._i_encoder is not None:
            _tw_encoder_reset(self, start_pos == 0 and dec_flags == 0)
        return cookie_obj

    def tell(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("TextIOWrapper.tell", args, kwds)
        self: TextIOWrapper = args[0]  # type: ignore[assignment]
        _tw_check_attached(self)
        _tw_check_closed(self)
        if not self._u_seekable:
            _unsupported("underlying stream is not seekable")
        if not self._f_telling:
            raise OSError("telling position disabled by next() call")
        _tw_writeflush(self)
        self.flush()  # type: ignore[attr-defined]
        posobj = self._c_buffer.tell()  # type: ignore[attr-defined]
        if self._h_decoder is None or self._m_snapshot is None:
            return posobj
        position = _number_index(posobj)
        dec_flags, next_input = self._m_snapshot
        position -= bytes.__len__(next_input)
        chars_to_skip = self._k_decoded_chars_used
        if chars_to_skip == 0:
            return _tw_pack_cookie(position, dec_flags)
        decoder = self._h_decoder
        saved_state = decoder.getstate()  # type: ignore[attr-defined]
        try:
            # the C asserts skip_bytes <= len(next_input) and, built without the assert, decodes past the snapshot's bytes when the
            # ratio is stale after a seek (its result then comes from the terminating NUL); the cap keeps the asserted invariant
            skip_bytes = min(int(self._l_b2cratio * chars_to_skip), bytes.__len__(next_input))
            skip_back = 1
            while skip_bytes > 0:
                _tw_decoder_setstate(self, position, dec_flags)
                n = str.__len__(_tw_decode(decoder, next_input[:skip_bytes], False))
                if n <= chars_to_skip:
                    b, d = _tw_decoder_state(self)
                    if bytes.__len__(b) == 0:
                        dec_flags = d
                        chars_to_skip -= n
                        break
                    skip_bytes -= bytes.__len__(b)
                    skip_back = 1
                else:
                    skip_bytes -= skip_back
                    skip_back = skip_back * 2
            else:
                skip_bytes = 0
                _tw_decoder_setstate(self, position, dec_flags)
            start_pos = position + skip_bytes
            start_flags = dec_flags
            if chars_to_skip == 0:
                return _tw_pack_cookie(start_pos, start_flags)
            bytes_fed = 0
            need_eof = False
            chars_decoded = 0
            i = skip_bytes
            total = bytes.__len__(next_input)
            while i < total:
                bytes_fed += 1
                chars_decoded += str.__len__(_tw_decode(decoder, next_input[i:i + 1], False))
                dec_buffer, dec_flags = _tw_decoder_state(self)
                if bytes.__len__(dec_buffer) == 0 and chars_decoded <= chars_to_skip:
                    start_pos += bytes_fed
                    chars_to_skip -= chars_decoded
                    start_flags, bytes_fed, chars_decoded = dec_flags, 0, 0
                if chars_decoded >= chars_to_skip:
                    break
                i += 1
            else:
                chars_decoded += str.__len__(_tw_decode(decoder, b"", True))
                need_eof = True
                if chars_decoded < chars_to_skip:
                    raise OSError("can't reconstruct logical file position")
            return _tw_pack_cookie(start_pos, start_flags, bytes_fed, need_eof, chars_to_skip)  # type: ignore[arg-type]
        finally:
            decoder.setstate(saved_state)  # type: ignore[attr-defined]

    def __next__(*args: object, **kwds: object) -> str:  # noqa: N805
        _noargs("TextIOWrapper.__next__", args, kwds)
        self: TextIOWrapper = args[0]  # type: ignore[assignment]
        _tw_check_attached(self)
        self._f_telling = False
        if type(self) is TextIOWrapper:
            line = _tw_readline(self, -1)
        else:
            line = self.readline()  # type: ignore[attr-defined]
            if not isinstance(line, str):
                raise OSError("readline() should have returned a str object, not '" + _tp_name(line) + "'")
        if str.__len__(line) == 0:
            self._m_snapshot = None
            self._f_telling = self._u_seekable
            raise StopIteration
        return line

    def _dealloc_warn(*args: object, **kwds: object) -> None:  # noqa: N805
        source = _one("TextIOWrapper._dealloc_warn", args, kwds)
        self: TextIOWrapper = args[0]  # type: ignore[assignment]
        if self._a_ok and not self._b_detached:
            try:
                self._c_buffer._dealloc_warn(source)  # type: ignore[attr-defined]
            except BaseException:  # noqa: BLE001, S110
                pass

    def __getstate__(*args: object, **kwds: object) -> object:  # noqa: N805
        _noargs("TextIOWrapper.__getstate__", args, kwds)
        raise TypeError("cannot pickle '" + type(args[0]).__name__ + "' instances")

    def __repr__(self) -> str:
        type_name = _tp_name(self)[:100]
        if not self._a_ok:
            raise ValueError("I/O operation on uninitialized object")
        if self._z_in_repr:
            raise RuntimeError("reentrant call inside " + type_name + ".__repr__")
        self._z_in_repr = True
        try:
            parts = ["<" + type_name]
            try:
                nameobj = getattr(self, "name")  # noqa: B009
            except (AttributeError, ValueError):
                nameobj = _ABSENT
            if nameobj is not _ABSENT:
                parts.append(" name=" + repr(nameobj))
            modeobj = _optional_attr(self, "mode")
            if modeobj is not _ABSENT:
                parts.append(" mode=" + repr(modeobj))
            parts.append(" encoding=" + repr(self._d_encoding) + ">")
            return "".join(parts)
        finally:
            self._z_in_repr = False

    @property
    def encoding(self) -> object:
        _tw_check_attached(self)
        return self._d_encoding

    @property
    def errors(self) -> object:
        _tw_check_attached(self)
        return self._t_errors

    @property
    def line_buffering(self) -> bool:
        _tw_check_attached(self)
        return self._v_line_buffering

    @property
    def write_through(self) -> bool:
        _tw_check_attached(self)
        return self._w_write_through

    @property
    def buffer(self) -> object:
        _tw_check_attached(self)
        return self._c_buffer

    @property
    def closed(self) -> object:
        _tw_check_attached(self)
        return getattr(self._c_buffer, "closed")  # noqa: B009

    @property
    def name(self) -> object:
        _tw_check_attached(self)
        return getattr(self._c_buffer, "name")  # noqa: B009

    @property
    def newlines(self) -> object:
        _tw_check_attached(self)
        if self._h_decoder is None or type(self._h_decoder) is not IncrementalNewlineDecoder:
            return None
        return self._h_decoder.newlines

    @property
    def _CHUNK_SIZE(self) -> int:  # noqa: N802
        _tw_check_attached(self)
        return self._e_chunk_size

    @_CHUNK_SIZE.setter
    def _CHUNK_SIZE(self, value: object) -> None:  # noqa: N802
        _tw_check_attached(self)
        if value is _ABSENT:
            raise AttributeError("cannot delete attribute")
        n = _off_t(value)
        if n <= 0:
            raise ValueError("a strictly positive integer is required")
        self._e_chunk_size = n


# ---- StringIO (stringio.c) ----

def _sio_check(self: StringIO) -> None:
    if not self._a_ok:
        raise ValueError("I/O operation on uninitialized object")
    if self._b_closed:
        raise ValueError("I/O operation on closed file")


def _sio_write_str(self: StringIO, obj: str) -> None:   # write_str
    decoded: str = _nl_decode(self._c_decoder, obj, True) if self._c_decoder is not None else obj
    if self._h_writenl is not None:
        decoded = decoded.replace("\n", self._h_writenl)
    length = str.__len__(decoded)
    if self._e_pos > _SSIZE_MAX - length:
        raise OverflowError("new position too large")
    text = self._d_text
    size = str.__len__(text)
    if self._e_pos > size:
        text = text + "\0" * (self._e_pos - size)
    self._d_text = text[:self._e_pos] + decoded + text[self._e_pos + length:]
    self._e_pos += length


def _sio_readline(self: StringIO, limit: int) -> str:   # _stringio_readline
    size = str.__len__(self._d_text)
    if self._e_pos >= size:
        return ""
    if limit < 0 or limit > size - self._e_pos:
        limit = size - self._e_pos
    end = self._e_pos + limit                    # the C puts a NUL at `end` for the search: a '\r' there ends the line
    found, _consumed = _find_line_ending(self._g_readtranslate, self._f_readuniversal, self._i_readnl, self._d_text, self._e_pos, end, "")
    if found < 0:
        found = limit
    out = self._d_text[self._e_pos:self._e_pos + found]
    self._e_pos += found
    return out


class StringIO(_TextIOBase):
    __slots__ = ("_a_ok", "_b_closed", "_c_decoder", "_d_text", "_e_pos", "_f_readuniversal", "_g_readtranslate", "_h_writenl", "_i_readnl")

    def __new__(cls, *args: object, **kwds: object) -> StringIO:
        self: StringIO = _bella_new_instance(cls)
        self._a_ok = False
        self._b_closed = False
        self._c_decoder = None
        self._d_text = ""
        self._e_pos = 0
        self._f_readuniversal = False
        self._g_readtranslate = False
        self._h_writenl = None
        self._i_readnl = None
        return self

    def __init__(*args: object, **kwds: object) -> None:  # noqa: N805
        self: StringIO = args[0]  # type: ignore[assignment]
        value, newline_obj = _unpack("StringIO", args[1:], kwds, ("initial_value", "newline"), 0, 2)
        newline: str | None = "\n"
        if newline_obj is None:
            newline = None
        elif newline_obj is not _ABSENT:
            if not isinstance(newline_obj, str):
                raise TypeError("newline must be str or None, not " + _tp_name(newline_obj))
            str.encode(newline_obj, "utf-8")
            newline = newline_obj
            cut = str.find(newline, "\0")
            if cut >= 0:
                newline = newline[:cut]
        if newline is not None and newline != "" and newline != "\n" and newline != "\r" and newline != "\r\n":
            raise ValueError("illegal newline value: " + repr(newline_obj))
        if value is not _ABSENT and value is not None and not isinstance(value, str):
            raise TypeError("initial_value must be str or None, not " + _tp_name(value))
        self._a_ok = False
        self._i_readnl = newline
        self._f_readuniversal = newline is None or newline == ""
        self._g_readtranslate = newline is None
        self._h_writenl = newline if newline is not None and newline[:1] == "\r" else None
        self._c_decoder = IncrementalNewlineDecoder(None, self._g_readtranslate) if self._f_readuniversal else None
        self._d_text = ""
        self._e_pos = 0
        if value is not _ABSENT and value is not None and str.__len__(value) > 0:
            _sio_write_str(self, value)
        self._e_pos = 0
        self._b_closed = False
        self._a_ok = True

    def getvalue(*args: object, **kwds: object) -> str:  # noqa: N805
        _noargs("StringIO.getvalue", args, kwds)
        self: StringIO = args[0]  # type: ignore[assignment]
        _sio_check(self)
        return self._d_text

    def tell(*args: object, **kwds: object) -> int:  # noqa: N805
        _noargs("StringIO.tell", args, kwds)
        self: StringIO = args[0]  # type: ignore[assignment]
        _sio_check(self)
        return self._e_pos

    def read(*args: object, **kwds: object) -> str:  # noqa: N805
        n = _positional("read", "StringIO.read", args, kwds, 0, 1)
        self: StringIO = args[0]  # type: ignore[assignment]
        size = _ssize_or_none(args[1]) if n else -1
        _sio_check(self)
        avail = str.__len__(self._d_text) - self._e_pos
        if size < 0 or size > avail:
            size = avail if avail > 0 else 0
        out = self._d_text[self._e_pos:self._e_pos + size]
        self._e_pos += size
        return out

    def readline(*args: object, **kwds: object) -> str:  # noqa: N805
        n = _positional("readline", "StringIO.readline", args, kwds, 0, 1)
        self: StringIO = args[0]  # type: ignore[assignment]
        size = _ssize_or_none(args[1]) if n else -1
        _sio_check(self)
        return _sio_readline(self, size)

    def __next__(*args: object, **kwds: object) -> str:  # noqa: N805
        _noargs("StringIO.__next__", args, kwds)
        self: StringIO = args[0]  # type: ignore[assignment]
        _sio_check(self)
        if type(self) is StringIO:
            line = _sio_readline(self, -1)
        else:
            line = self.readline()  # type: ignore[attr-defined]
            if not isinstance(line, str):
                raise OSError("readline() should have returned a str object, not '" + _tp_name(line) + "'")
        if str.__len__(line) == 0:
            raise StopIteration
        return line

    def truncate(*args: object, **kwds: object) -> int:  # noqa: N805
        n = _positional("truncate", "StringIO.truncate", args, kwds, 0, 1)
        self: StringIO = args[0]  # type: ignore[assignment]
        pos = args[1] if n else None
        _sio_check(self)
        if pos is None:
            size = self._e_pos
        else:
            size = _off(pos)
            if size < 0:
                raise ValueError("negative pos value " + str(size))
        if size < str.__len__(self._d_text):
            self._d_text = self._d_text[:size]
        return size

    def seek(*args: object, **kwds: object) -> int:  # noqa: N805
        n = _positional("seek", "StringIO.seek", args, kwds, 1, 2)
        self: StringIO = args[0]  # type: ignore[assignment]
        pos = _ssize(args[1])
        whence = _int(args[2]) if n > 1 else 0
        _sio_check(self)
        if whence != 0 and whence != 1 and whence != 2:
            raise ValueError("Invalid whence (" + str(whence) + ", should be 0, 1 or 2)")
        if pos < 0 and whence == 0:
            raise ValueError("Negative seek position " + str(pos))
        if whence != 0 and pos != 0:
            raise OSError("Can't do nonzero cur-relative seeks")
        if whence == 1:
            pos = self._e_pos
        elif whence == 2:
            pos = str.__len__(self._d_text)
        self._e_pos = pos
        return pos

    def write(*args: object, **kwds: object) -> int:  # noqa: N805
        obj = _one("StringIO.write", args, kwds)
        self: StringIO = args[0]  # type: ignore[assignment]
        if not self._a_ok:
            raise ValueError("I/O operation on uninitialized object")
        if not isinstance(obj, str):
            raise TypeError("string argument expected, got '" + _tp_name(obj) + "'")
        _sio_check(self)
        size = str.__len__(obj)
        if size > 0:
            _sio_write_str(self, obj)
        return size

    def close(*args: object, **kwds: object) -> None:  # noqa: N805
        _noargs("StringIO.close", args, kwds)
        self: StringIO = args[0]  # type: ignore[assignment]
        self._b_closed = True
        self._d_text = ""

    def readable(*args: object, **kwds: object) -> bool:  # noqa: N805
        _noargs("StringIO.readable", args, kwds)
        _sio_check(args[0])  # type: ignore[arg-type]
        return True

    def writable(*args: object, **kwds: object) -> bool:  # noqa: N805
        _noargs("StringIO.writable", args, kwds)
        _sio_check(args[0])  # type: ignore[arg-type]
        return True

    def seekable(*args: object, **kwds: object) -> bool:  # noqa: N805
        _noargs("StringIO.seekable", args, kwds)
        _sio_check(args[0])  # type: ignore[arg-type]
        return True

    def __getstate__(*args: object, **kwds: object) -> tuple[object, ...]:  # noqa: N805
        _noargs("StringIO.__getstate__", args, kwds)
        self: StringIO = args[0]  # type: ignore[assignment]
        value = StringIO.getvalue(self)
        d = _optional_attr(self, "__dict__")
        return value, self._i_readnl, self._e_pos, (None if d is _ABSENT or dict.__len__(d) == 0 else dict(d))  # type: ignore[arg-type,call-overload]

    def __setstate__(*args: object, **kwds: object) -> None:  # noqa: N805
        state = _one("StringIO.__setstate__", args, kwds)
        self: StringIO = args[0]  # type: ignore[assignment]
        if not isinstance(state, tuple) or tuple.__len__(state) < 4:
            raise TypeError(_tp_name(self) + ".__setstate__ argument should be 4-tuple, got " + _tp_name(state))
        StringIO.__init__(self, tuple.__getitem__(state, 0), tuple.__getitem__(state, 1))
        initial = tuple.__getitem__(state, 0)
        self._d_text = str.__str__(initial) if isinstance(initial, str) else ""  # type: ignore[arg-type]
        position_obj = tuple.__getitem__(state, 2)
        if not isinstance(position_obj, int):
            raise TypeError("third item of state must be an integer, got " + _tp_name(position_obj))
        pos = _ssize(position_obj)
        if pos < 0:
            raise ValueError("position value cannot be negative")
        self._e_pos = pos
        d = tuple.__getitem__(state, 3)
        if d is not None:
            if not isinstance(d, dict):
                raise TypeError("fourth item of state should be a dict, got a " + _tp_name(d))
            self.__dict__ = d  # type: ignore[attr-defined]

    @property
    def closed(self) -> bool:
        if not self._a_ok:
            raise ValueError("I/O operation on uninitialized object")
        return self._b_closed

    @property
    def line_buffering(self) -> bool:
        _sio_check(self)
        return False

    @property
    def newlines(self) -> object:
        _sio_check(self)
        if self._c_decoder is None:
            return None
        return self._c_decoder.newlines


# ---- open, open_code, text_encoding (_iomodule.c) ----

def open(*args: object, **kwds: object) -> object:  # noqa: A001
    file, mode, buffering, encoding, errors, newline, closefd, opener = _unpack(
        "open", args, kwds, ("file", "mode", "buffering", "encoding", "errors", "newline", "closefd", "opener"), 1, 8)
    if mode is _ABSENT:
        mode = "r"
    elif not isinstance(mode, str):
        raise TypeError("open() argument 'mode' must be str, not " + _tp_name(mode))
    else:
        _c_string(mode, "open() argument 'mode'")
    buffering = -1 if buffering is _ABSENT else _int(buffering)
    if encoding is _ABSENT or encoding is None:
        encoding = None
    else:
        _c_string(encoding, "open() argument 'encoding'")
    if errors is _ABSENT or errors is None:
        errors = None
    else:
        _c_string(errors, "open() argument 'errors'")
    if newline is _ABSENT or newline is None:
        newline = None
    else:
        _c_string(newline, "open() argument 'newline'")
    closefd = True if closefd is _ABSENT else (True if closefd else False)
    if opener is _ABSENT:
        opener = None
    is_number = isinstance(file, int) or hasattr(type(file), "__index__") or hasattr(type(file), "__int__") or hasattr(type(file), "__float__")
    path_or_fd = file if is_number else _fspath(file)
    if not is_number and not issubclass(type(path_or_fd), (str, bytes)):
        raise TypeError("invalid file: " + repr(file))
    creating = reading = writing = appending = updating = text = binary = False
    shown: str = mode
    i = 0
    length = str.__len__(shown)
    while i < length:
        c = shown[i]
        if c == "x":
            creating = True
        elif c == "r":
            reading = True
        elif c == "w":
            writing = True
        elif c == "a":
            appending = True
        elif c == "+":
            updating = True
        elif c == "t":
            text = True
        elif c == "b":
            binary = True
        else:
            raise ValueError("invalid mode: '" + shown + "'")
        if str.find(shown, c, i + 1) >= 0:
            raise ValueError("invalid mode: '" + shown + "'")
        i += 1
    rawmode = ("x" if creating else "") + ("r" if reading else "") + ("w" if writing else "") + ("a" if appending else "") + ("+" if updating else "")
    if text and binary:
        raise ValueError("can't have text and binary mode at once")
    if (1 if creating else 0) + (1 if reading else 0) + (1 if writing else 0) + (1 if appending else 0) > 1:
        raise ValueError("must have exactly one of create/read/write/append mode")
    if binary and encoding is not None:
        raise ValueError("binary mode doesn't take an encoding argument")
    if binary and errors is not None:
        raise ValueError("binary mode doesn't take an errors argument")
    if binary and newline is not None:
        raise ValueError("binary mode doesn't take a newline argument")
    if binary and buffering == 1:
        _refuse("the RuntimeWarning 'line buffering (buffering=1) isn't supported in binary mode' (warnings: step 3b)")
    raw = FileIO(path_or_fd, rawmode, closefd, opener)
    result: object = raw
    try:
        isatty = False
        if buffering < 0:
            isatty = True if raw._isatty_open_only() else False
        if buffering == 1 or isatty:
            buffering = -1
            line_buffering = True
        else:
            line_buffering = False
        if buffering < 0:
            buffering = _int(raw._blksize)
            buffering = max(min(buffering, 8192 * 1024), DEFAULT_BUFFER_SIZE)
        if buffering < 0:
            raise ValueError("invalid buffering size")
        if buffering == 0:
            if not binary:
                raise ValueError("can't have unbuffered text I/O")
            return result
        if updating:
            buffer: object = BufferedRandom(raw, buffering)
        elif creating or writing or appending:
            buffer = BufferedWriter(raw, buffering)
        elif reading:
            buffer = BufferedReader(raw, buffering)
        else:
            raise ValueError("unknown mode: '" + shown + "'")
        result = buffer
        if binary:
            return result
        wrapper = TextIOWrapper(buffer, encoding, errors, newline, line_buffering)
        result = wrapper
        wrapper.mode = shown  # type: ignore[attr-defined]
        return result
    except BaseException as exc:
        try:
            result.close()  # type: ignore[attr-defined]
        except BaseException as e:  # noqa: BLE001
            raise e from exc
        raise


def open_code(*args: object, **kwds: object) -> object:
    (path,) = _unpack("open_code", args, kwds, ("path",), 1, 1)
    if not isinstance(path, str):
        raise TypeError("open_code() argument 'path' must be str, not " + _tp_name(path))
    return open(path, "rb")


def text_encoding(*args: object, **kwds: object) -> object:
    if kwds:
        raise TypeError("_io.text_encoding() takes no keyword arguments")
    n = len(args)
    if n < 1:
        raise TypeError("text_encoding expected at least 1 argument, got 0")
    if n > 2:
        raise TypeError("text_encoding expected at most 2 arguments, got " + str(n))
    if n > 1:
        _int(args[1])
    if args[0] is None:
        return "utf-8"
    return args[0]


def _std_stream(fd: int, name: str, mode: str, encoding: str, errors: str) -> object:
    """create_stdio (Python/pylifecycle.c): open(fd, mode, -1, closefd=False), the raw named, line buffering on a tty and for stderr,
    then a TextIOWrapper with the encoding and errors the configuration chose (PYTHONIOENCODING, else UTF-8 by D-15) and newline "\n",
    with its mode set."""
    buf = open(fd, mode, -1, None, None, None, False)
    raw = buf.raw  # type: ignore[attr-defined]
    raw.name = name
    isatty = True if raw.isatty() else False
    line_buffering = isatty or fd == 2
    stream = TextIOWrapper(buf, encoding, errors, "\n", line_buffering, False)
    stream.mode = mode[:1]  # type: ignore[attr-defined]
    return stream


_io_call("hooks", open, _std_stream)
