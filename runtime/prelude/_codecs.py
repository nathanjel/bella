"""_codecs, in Python over the codecs in runtime/src/bytes.cpp, from Modules/_codecsmodule.c and Python/codecs.c; see itertools.py beside it.

The registry is here as the interpreter's state has it: the search functions, their cache, the error handlers by name. The runtime's
str.encode and bytes.decode know the names PyUnicode_AsEncodedString and PyUnicode_Decode shortcut; for any other name they come here
(`_codecs_call("hooks", ...)`), as those go to _PyCodec_EncodeText and _PyCodec_DecodeText. `_start` is the end of _PyCodec_InitRegistry:
the runtime calls it before the program's first line, and it imports `encodings`, whose search function finds the phase-1 codecs.

Not written: UTF-7, the escape codecs and charmap (they stop by name), the namereplace handler (it needs the Unicode
database), and a handler a program registers when a built-in codec would call it.
"""

__all__ = ["_normalize_encoding", "_unregister_error", "ascii_decode", "ascii_encode", "charmap_build", "charmap_decode", "charmap_encode", "decode", "encode",
           "escape_decode", "escape_encode", "latin_1_decode", "latin_1_encode", "lookup", "lookup_error", "raw_unicode_escape_decode", "raw_unicode_escape_encode",
           "readbuffer_encode", "register", "register_error", "unicode_escape_decode", "unicode_escape_encode", "unregister", "utf_16_be_decode",
           "utf_16_be_encode", "utf_16_decode", "utf_16_encode", "utf_16_ex_decode", "utf_16_le_decode", "utf_16_le_encode", "utf_32_be_decode",
           "utf_32_be_encode", "utf_32_decode", "utf_32_encode", "utf_32_ex_decode", "utf_32_le_decode", "utf_32_le_encode", "utf_7_decode", "utf_7_encode",
           "utf_8_decode", "utf_8_encode"]

__name__ = "_codecs"

try:
    _tp_name                                     # noqa: B018  # Py_TYPE(obj)->tp_name
    _keyword_suggestion                          # noqa: B018  # _Py_CalculateSuggestions
    _codecs_call                                 # noqa: B018  # the runtime's codecs and what it keeps of an exception, by name
    _number_index                                # noqa: B018  # PyNumber_Index, with its messages
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _tp_name: Callable[..., str] = _missing
    _keyword_suggestion: Callable[..., str | None] = _missing
    _codecs_call: Callable[..., Any] = _missing
    _number_index: Callable[..., int] = _missing

_ABSENT = object()
_search_path: list[object] = []                  # interp->codecs.search_path
_search_cache: dict[str, object] = {}            # interp->codecs.search_cache
_error_registry: dict[str, object] = {}          # interp->codecs.error_registry
_library: list[object] = []                      # the search function `encodings` registered at the start, then what it found
_BUILTIN_HANDLERS = ("strict", "ignore", "replace", "xmlcharrefreplace", "backslashreplace", "namereplace", "surrogatepass", "surrogateescape")


def _refuse(what: str) -> None:
    _codecs_call("refuse", what)


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
                    raise TypeError(name + "() got an unexpected keyword argument '" + keyword + "'. Did you mean '" + suggestion + "'?")
                raise TypeError(name + "() got an unexpected keyword argument '" + keyword + "'")
    return out


def _one(name: str, args: tuple[object, ...], kwds: dict[str, object], module: str = "_codecs.") -> object:   # METH_O
    if kwds:
        raise TypeError(module + name + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError(module + name + "() takes exactly one argument (" + str(len(args)) + " given)")
    return args[0]


def _positional(name: str, args: tuple[object, ...], kwds: dict[str, object], low: int, high: int) -> int:   # METH_FASTCALL, _PyArg_CheckPositional
    if kwds:
        raise TypeError("_codecs." + name + "() takes no keyword arguments")
    n = len(args)
    if n < low:
        raise TypeError(name + " expected " + ("" if low == high else "at least ") + str(low) + " argument" + ("" if low == 1 else "s") + ", got " + str(n))
    if n > high:
        raise TypeError(name + " expected " + ("" if low == high else "at most ") + str(high) + " argument" + ("" if high == 1 else "s") + ", got " + str(n))
    return n


def _c_string(value: str) -> str:                # PyUnicode_AsUTF8AndSize, and a C string has no null inside
    str.encode(value, "utf-8")
    if str.__contains__(value, "\0"):
        raise ValueError("embedded null character")
    return value


def _errors(function: str, position: int, args: tuple[object, ...]) -> str | None:   # str(accept={str, NoneType}) = None
    if len(args) < position:
        return None
    value = args[position - 1]
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(function + "() argument " + str(position) + " must be str or None, not " + _tp_name(value))
    return _c_string(value)


def _text(function: str, value: object) -> str:  # unicode
    if not isinstance(value, str):
        raise TypeError(function + "() argument 1 must be str, not " + _tp_name(value))
    return value


def _cut(text: str) -> str:                      # %.400s
    if str.__len__(text) <= 100:
        return text
    return bytes.decode(str.encode(text, "utf-8", "surrogatepass")[:400], "utf-8", "replace")


def _full_name(value: object) -> str:            # %T
    cls = type(value)
    return cls.__qualname__ if cls.__module__ in ("builtins", "__main__") else cls.__module__ + "." + cls.__qualname__


# ---- the registry (Python/codecs.c) ----

def _normalized(encoding: str) -> str:           # normalizestring: ASCII letters in lower case, a space a hyphen
    out: list[str] = []
    for ch in str.__str__(encoding):
        if ch == " ":
            ch = "-"
        elif "A" <= ch <= "Z":
            ch = chr(ord(ch) + 32)
        out.append(ch)
    return "".join(out)


def _lookup(encoding: str) -> object:            # _PyCodec_Lookup
    name = _normalized(encoding)
    result = dict.get(_search_cache, name)
    if result is not None:
        return result
    count = list.__len__(_search_path)
    if count == 0:
        raise LookupError("no codec search functions registered: can't find encoding")
    i = 0
    while i < count:
        func = _search_path[i]
        result = func(name)  # type: ignore[operator]
        if result is None:
            i += 1
            continue
        if not isinstance(result, tuple) or tuple.__len__(result) != 4:
            raise TypeError("codec search functions must return 4-tuples")
        if list.__len__(_library) > 0 and func is _library[0]:
            _library.append(result)
        break
    if result is None:
        raise LookupError("unknown encoding: " + encoding)
    _search_cache[name] = result
    return result


def _lookup_text(encoding: str, alternate_command: str | None) -> object:   # _PyCodec_LookupTextEncoding
    codec = _lookup(encoding)
    if type(codec) is not tuple:
        try:
            attr = codec._is_text_encoding  # type: ignore[attr-defined]
        except AttributeError:
            return codec
        if not attr:
            if alternate_command is None:
                raise LookupError("'" + _cut(encoding) + "' is not a text encoding")
            raise LookupError("'" + _cut(encoding) + "' is not a text encoding; use " + alternate_command + " to handle arbitrary codecs")
    return codec


def _call_codec(function: object, value: object, encoding: str, errors: str | None, doing: str, bad_result: str) -> object:
    """_PyCodec_EncodeInternal and _PyCodec_DecodeInternal: the codec's function, a note on what it raises, and its first result."""
    try:
        result = function(value) if errors is None else function(value, errors)  # type: ignore[operator]
    except BaseException as exc:                 # _PyErr_FormatNote: BaseException's own add_note, whatever the class overrides
        BaseException.add_note(exc, doing + " with '" + encoding + "' codec failed")
        raise
    if not isinstance(result, tuple) or tuple.__len__(result) != 2:
        raise TypeError(bad_result)
    return tuple.__getitem__(result, 0)


def _encode(obj: object, encoding: str, errors: str | None) -> object:   # PyCodec_Encode
    return _call_codec(tuple.__getitem__(_lookup(encoding), 0), obj, encoding, errors, "encoding", "encoder must return a tuple (object, integer)")  # type: ignore[arg-type]


def _decode(obj: object, encoding: str, errors: str | None) -> object:   # PyCodec_Decode
    return _call_codec(tuple.__getitem__(_lookup(encoding), 1), obj, encoding, errors, "decoding", "decoder must return a tuple (object,integer)")  # type: ignore[arg-type]


def _text_encode(text: str, encoding: str, errors: str | None) -> object:
    """PyUnicode_AsEncodedString past its shortcuts: _PyCodec_EncodeText, and what it takes for bytes."""
    codec = _lookup_text(encoding, "codecs.encode()")
    v = _call_codec(tuple.__getitem__(codec, 0), text, encoding, errors, "encoding", "encoder must return a tuple (object, integer)")  # type: ignore[arg-type]
    if isinstance(v, bytes):
        return v
    if isinstance(v, bytearray):
        _refuse("the RuntimeWarning for an encoder that returns a bytearray (warnings: step 3b)")
    raise TypeError("'" + _cut(encoding) + "' encoder returned '" + _cut(_tp_name(v)) + "' instead of 'bytes'; use codecs.encode() to encode to arbitrary types")


def _text_decode(data: bytes, encoding: str, errors: str | None) -> object:
    """PyUnicode_Decode past its shortcuts: _PyCodec_DecodeText. CPython hands the decoder a memoryview of the bytes; the library's
    decoders pass it on to the functions below, which take the bytes as well, and a decoder of the program's would see the difference."""
    codec = _lookup_text(encoding, "codecs.decode()")
    library = False
    for entry in _library:
        if entry is codec:
            library = True
    if not library:
        _refuse("decoding with a codec the program registered: it is given a memoryview (the buffer protocol: step 3b)")
    v = _call_codec(tuple.__getitem__(codec, 1), data, encoding, errors, "decoding", "decoder must return a tuple (object,integer)")  # type: ignore[arg-type]
    if not isinstance(v, str):
        raise TypeError("'" + _cut(encoding) + "' decoder returned '" + _cut(_tp_name(v)) + "' instead of 'str'; use codecs.decode() to decode to arbitrary types")
    return v


def _unknown_handler(name: str) -> None:
    """PyCodec_LookupError, where a built-in codec meets an error under a name it has no code for."""
    if name in _error_registry:
        _refuse("the error handler '" + name + "' a program registered, called by a built-in codec (step 3b)")
    raise LookupError("unknown error handler name '" + _cut(name) + "'")


def _start() -> None:
    """_PyCodec_InitRegistry's last step, and the start-up's look for the filesystem encoding (config_get_codec_name)."""
    __import__("encodings")
    if list.__len__(_search_path) > 0:
        _library.append(_search_path[0])
    _lookup("utf-8")


def register(*args: object, **kwds: object) -> None:
    search_function = _one("register", args, kwds)
    if not callable(search_function):
        raise TypeError("argument must be callable")
    _search_path.append(search_function)


def unregister(*args: object, **kwds: object) -> None:
    search_function = _one("unregister", args, kwds)
    i = 0
    while i < list.__len__(_search_path):
        if _search_path[i] is search_function:
            del _search_path[i]
            _search_cache.clear()
            return
        i += 1


def lookup(*args: object, **kwds: object) -> object:
    encoding = _one("lookup", args, kwds)
    if not isinstance(encoding, str):
        raise TypeError("lookup() argument must be str, not " + _tp_name(encoding))
    return _lookup(_c_string(encoding))


def _coding_args(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> tuple[object, str, str | None]:
    obj, encoding, errors = _unpack(name, args, kwds, ("obj", "encoding", "errors"), 1, 3)
    if encoding is not _ABSENT:
        if not isinstance(encoding, str):
            raise TypeError(name + "() argument 'encoding' must be str, not " + _tp_name(encoding))
        _c_string(encoding)
    if errors is not _ABSENT:
        if not isinstance(errors, str):
            raise TypeError(name + "() argument 'errors' must be str, not " + _tp_name(errors))
        _c_string(errors)
    return obj, ("utf-8" if encoding is _ABSENT else encoding), (None if errors is _ABSENT else errors)  # type: ignore[return-value]


def encode(*args: object, **kwds: object) -> object:
    obj, encoding, errors = _coding_args("encode", args, kwds)
    return _encode(obj, encoding, errors)


def decode(*args: object, **kwds: object) -> object:
    obj, encoding, errors = _coding_args("decode", args, kwds)
    return _decode(obj, encoding, errors)


def _normalize_encoding(*args: object, **kwds: object) -> str:
    """_Py_normalize_encoding without the lower case: runs of what is neither ASCII alphanumeric nor a dot become one underscore,
    none at either end, and a null ends the name as it ends a C string."""
    (encoding,) = _unpack("_normalize_encoding", args, kwds, ("encoding",), 1, 1)
    if not isinstance(encoding, str):
        raise TypeError("_normalize_encoding() argument 'encoding' must be str, not " + _tp_name(encoding))
    str.encode(encoding, "utf-8")
    out: list[str] = []
    punct = False
    for ch in str.__str__(encoding):
        if ch == "\0":
            break
        if "a" <= ch <= "z" or "A" <= ch <= "Z" or "0" <= ch <= "9" or ch == ".":
            if punct and out:
                out.append("_")
            punct = False
            out.append(ch)
        else:
            punct = True
    return "".join(out)


# ---- the error handlers, by name ----

def register_error(*args: object, **kwds: object) -> None:
    _positional("register_error", args, kwds, 2, 2)
    errors = args[0]
    if not isinstance(errors, str):
        raise TypeError("register_error() argument 1 must be str, not " + _tp_name(errors))
    name = _c_string(errors)
    handler = args[1]
    if not callable(handler):
        raise TypeError("handler must be callable")
    if name in _BUILTIN_HANDLERS:
        _refuse("replacing the built-in error handler '" + name + "' (the runtime's codecs do not ask the registry for it: step 3b)")
    _error_registry[str.__str__(name)] = handler


def _unregister_error(*args: object, **kwds: object) -> bool:
    errors = _one("_unregister_error", args, kwds)
    if not isinstance(errors, str):
        raise TypeError("_unregister_error() argument must be str, not " + _tp_name(errors))
    name = str.__str__(_c_string(errors))
    if name in _BUILTIN_HANDLERS:
        raise ValueError("cannot un-register built-in error handler '" + name + "'")
    if name in _error_registry:
        del _error_registry[name]
        return True
    return False


def lookup_error(*args: object, **kwds: object) -> object:
    name = _one("lookup_error", args, kwds)
    if not isinstance(name, str):
        raise TypeError("lookup_error() argument must be str, not " + _tp_name(name))
    handler = dict.get(_error_registry, str.__str__(_c_string(name)))
    if handler is None:
        raise LookupError("unknown error handler name '" + _cut(name) + "'")
    return handler


def _is(exc: object, cls: type) -> bool:         # PyObject_TypeCheck
    return issubclass(type(exc), cls)


def _wrong_exception_type(exc: object) -> None:
    raise TypeError("don't know how to handle " + _full_name(exc) + " in error callback")


def _params(exc: object, as_bytes: bool) -> tuple[object, int, int, int, int]:
    """_PyUnicodeError_GetParams: the object, its length, and start, end and their distance brought inside it."""
    obj = _codecs_call("field", exc, "object", _ABSENT)
    if obj is _ABSENT:
        raise TypeError("UnicodeError 'object' attribute is not set")
    if as_bytes:
        if not isinstance(obj, bytes):
            raise TypeError("UnicodeError 'object' attribute must be a bytes")
        n = bytes.__len__(obj)
    else:
        if not isinstance(obj, str):
            raise TypeError("UnicodeError 'object' attribute must be a string")
        n = str.__len__(obj)
    start: int = _codecs_call("field", exc, "start", 0)
    end: int = _codecs_call("field", exc, "end", 0)
    if start < 0:
        start = 0
    if start >= n:
        start = 0 if n == 0 else n - 1
    if end < 1:
        end = 1
    if end > n:
        end = n
    return obj, n, start, end, (end - start if end > start else 0)


def _hex(ch: int) -> str:                        # codec_handler_write_unicode_hex
    digits = "0123456789abcdef"
    width = 8 if ch >= 0x10000 else 4 if ch >= 0x100 else 2
    out = ["\\", "U" if width == 8 else "u" if width == 4 else "x"]
    shift = 4 * (width - 1)
    while shift >= 0:
        out.append(digits[(ch >> shift) & 15])
        shift -= 4
    return "".join(out)


def _standard_encoding(exc: object) -> tuple[int, int]:
    """get_standard_encoding on the exception's encoding: 0 UTF-8, 1 and 2 UTF-16 big and little endian, 3 and 4 UTF-32, -1 another."""
    encoding = _codecs_call("field", exc, "encoding", _ABSENT)
    if encoding is _ABSENT:
        raise TypeError("UnicodeError 'encoding' attribute is not set")
    if not isinstance(encoding, str):
        raise TypeError("UnicodeError 'encoding' attribute must be a string")
    str.encode(encoding, "utf-8")
    e = str.__str__(encoding)
    cut = str.find(e, "\0")
    if cut >= 0:
        e = e[:cut]
    if str.__len__(e) >= 3 and e[0] in "uU" and e[1] in "tT" and e[2] in "fF":
        e = e[3:]
        if e[:1] in ("-", "_"):
            e = e[1:]
        if e == "8":
            return 0, 3
        for digits, big, little, width in (("16", 1, 2, 2), ("32", 3, 4, 4)):
            if e[:2] == digits:
                e = e[2:]
                if e == "":
                    return little, width
                if e[:1] in ("-", "_"):
                    e = e[1:]
                if str.__len__(e) == 2 and e[1] in "eE":
                    if e[0] in "bB":
                        return big, width
                    if e[0] in "lL":
                        return little, width
                return -1, 0
    elif e == "cp65001":
        return 0, 3
    return -1, 0


def _handler_arg(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> object:
    return _one(name, args, kwds, "")


def strict_errors(*args: object, **kwds: object) -> object:
    exc = _handler_arg("strict_errors", args, kwds)
    if isinstance(exc, BaseException):
        raise exc
    raise TypeError("codec must pass exception instance")


def ignore_errors(*args: object, **kwds: object) -> object:
    exc = _handler_arg("ignore_errors", args, kwds)
    if _is(exc, UnicodeEncodeError) or _is(exc, UnicodeTranslateError):
        return "", _params(exc, False)[3]
    if _is(exc, UnicodeDecodeError):
        return "", _params(exc, True)[3]
    _wrong_exception_type(exc)
    return None


def replace_errors(*args: object, **kwds: object) -> object:
    exc = _handler_arg("replace_errors", args, kwds)
    if _is(exc, UnicodeEncodeError):
        _obj, _n, _start, end, distance = _params(exc, False)
        return "?" * distance, end
    if _is(exc, UnicodeDecodeError):
        return "�", _params(exc, True)[3]
    if _is(exc, UnicodeTranslateError):
        _obj, _n, _start, end, distance = _params(exc, False)
        return "�" * distance, end
    _wrong_exception_type(exc)
    return None


def xmlcharrefreplace_errors(*args: object, **kwds: object) -> object:
    exc = _handler_arg("xmlcharrefreplace_errors", args, kwds)
    if not _is(exc, UnicodeEncodeError):
        _wrong_exception_type(exc)
    obj, _n, start, end, _distance = _params(exc, False)
    out: list[str] = []
    i = start
    while i < end:
        out.append("&#" + str(ord(str.__getitem__(obj, i))) + ";")  # type: ignore[arg-type]
        i += 1
    return "".join(out), end


def backslashreplace_errors(*args: object, **kwds: object) -> object:
    exc = _handler_arg("backslashreplace_errors", args, kwds)
    out: list[str] = []
    if _is(exc, UnicodeEncodeError) or _is(exc, UnicodeTranslateError):
        obj, _n, start, end, _distance = _params(exc, False)
        i = start
        while i < end:
            out.append(_hex(ord(str.__getitem__(obj, i))))  # type: ignore[arg-type]
            i += 1
        return "".join(out), end
    if _is(exc, UnicodeDecodeError):
        obj, _n, start, end, _distance = _params(exc, True)
        i = start
        while i < end:
            byte: int = bytes.__getitem__(obj, i)  # type: ignore[arg-type,assignment]
            out.append("\\x" + "0123456789abcdef"[byte >> 4] + "0123456789abcdef"[byte & 15])
            i += 1
        return "".join(out), end
    _wrong_exception_type(exc)
    return None


def namereplace_errors(*args: object, **kwds: object) -> object:
    exc = _handler_arg("namereplace_errors", args, kwds)
    if not _is(exc, UnicodeEncodeError):
        _wrong_exception_type(exc)
    _refuse("the error handler namereplace (it needs the Unicode database)")
    return None


def surrogatepass(*args: object, **kwds: object) -> object:
    exc = _handler_arg("surrogatepass", args, kwds)
    if _is(exc, UnicodeEncodeError):
        code, width = _standard_encoding(exc)
        if code < 0:
            raise exc  # type: ignore[misc]
        obj, _n, start, end, _distance = _params(exc, False)
        made = bytearray()
        i = start
        while i < end:
            ch = ord(str.__getitem__(obj, i))  # type: ignore[arg-type]
            if ch < 0xD800 or ch > 0xDFFF:
                raise exc  # type: ignore[misc]
            if code == 0:
                made += bytes((0xE0 | (ch >> 12), 0x80 | ((ch >> 6) & 0x3F), 0x80 | (ch & 0x3F)))
            elif code == 2:
                made += bytes((ch & 0xFF, ch >> 8))
            elif code == 1:
                made += bytes((ch >> 8, ch & 0xFF))
            elif code == 4:
                made += bytes((ch & 0xFF, ch >> 8, 0, 0))
            else:
                made += bytes((0, 0, ch >> 8, ch & 0xFF))
            i += 1
        return bytes(made), end
    if _is(exc, UnicodeDecodeError):
        code, width = _standard_encoding(exc)
        if code < 0:
            raise exc  # type: ignore[misc]
        obj, n, start, _end, _distance = _params(exc, True)
        ch = 0
        if n - start >= width:
            p: bytes = bytes.__getitem__(obj, slice(start, start + width))  # type: ignore[arg-type,assignment]
            if code == 0:
                if (p[0] & 0xF0) == 0xE0 and (p[1] & 0xC0) == 0x80 and (p[2] & 0xC0) == 0x80:
                    ch = ((p[0] & 0x0F) << 12) + ((p[1] & 0x3F) << 6) + (p[2] & 0x3F)
            elif code == 2:
                ch = p[1] << 8 | p[0]
            elif code == 1:
                ch = p[0] << 8 | p[1]
            elif code == 4:
                ch = (p[3] << 24) | (p[2] << 16) | (p[1] << 8) | p[0]
            else:
                ch = (p[0] << 24) | (p[1] << 16) | (p[2] << 8) | p[3]
        if ch < 0xD800 or ch > 0xDFFF:
            raise exc  # type: ignore[misc]
        return chr(ch), start + width
    _wrong_exception_type(exc)
    return None


def surrogateescape(*args: object, **kwds: object) -> object:
    exc = _handler_arg("surrogateescape", args, kwds)
    if _is(exc, UnicodeEncodeError):
        obj, _n, start, end, _distance = _params(exc, False)
        made = bytearray()
        i = start
        while i < end:
            ch = ord(str.__getitem__(obj, i))  # type: ignore[arg-type]
            if ch < 0xDC80 or ch > 0xDCFF:
                raise exc  # type: ignore[misc]
            made.append(ch - 0xDC00)
            i += 1
        return bytes(made), end
    if _is(exc, UnicodeDecodeError):
        obj, _n, start, _end, distance = _params(exc, True)
        out: list[str] = []
        consumed = 0
        while consumed < 4 and consumed < distance:
            byte: int = bytes.__getitem__(obj, start + consumed)  # type: ignore[arg-type,assignment]
            if byte < 128:
                break
            out.append(chr(0xDC00 + byte))
            consumed += 1
        if consumed == 0:
            raise exc  # type: ignore[misc]
        return "".join(out), start + consumed
    _wrong_exception_type(exc)
    return None


for _name, _handler in (("strict", strict_errors), ("ignore", ignore_errors), ("replace", replace_errors), ("xmlcharrefreplace", xmlcharrefreplace_errors),
                        ("backslashreplace", backslashreplace_errors), ("namereplace", namereplace_errors), ("surrogatepass", surrogatepass),
                        ("surrogateescape", surrogateescape)):
    _codecs_call("builtin", _handler)            # PyCFunction_NewEx(def, NULL, NULL): a built-in function of no module
    _error_registry[_name] = _handler


# ---- the codecs (Modules/_codecsmodule.c over Objects/unicodeobject.c) ----

def _decoder(name: str, codec: str, stateful: bool) -> object:
    def decode_function(*args: object, **kwds: object) -> tuple[str, int]:
        _positional(name, args, kwds, 1, 3 if stateful else 2)
        data: bytes = _codecs_call("buffer", args[0])
        errors = _errors(name, 2, args)
        final = stateful and len(args) > 2 and (True if args[2] else False)
        return _codecs_call("decode", codec, data, errors, final or not stateful)  # type: ignore[no-any-return]
    decode_function.__name__ = decode_function.__qualname__ = name
    return decode_function


def _encoder(name: str, codec: str) -> object:
    def encode_function(*args: object, **kwds: object) -> tuple[bytes, int]:
        _positional(name, args, kwds, 1, 2)
        text = _text(name, args[0])
        errors = _errors(name, 2, args)
        return _codecs_call("encode", codec, text, errors), str.__len__(text)
    encode_function.__name__ = encode_function.__qualname__ = name
    return encode_function


def _unwritten(name: str, what: str) -> object:
    def unwritten(*args: object, **kwds: object) -> None:
        _refuse(what)
    unwritten.__name__ = unwritten.__qualname__ = name
    return unwritten


utf_8_decode = _decoder("utf_8_decode", "utf-8", True)
utf_8_encode = _encoder("utf_8_encode", "utf-8")
latin_1_decode = _decoder("latin_1_decode", "latin-1", False)
latin_1_encode = _encoder("latin_1_encode", "latin-1")
ascii_decode = _decoder("ascii_decode", "ascii", False)
ascii_encode = _encoder("ascii_encode", "ascii")


def readbuffer_encode(*args: object, **kwds: object) -> tuple[bytes, int]:
    _positional("readbuffer_encode", args, kwds, 1, 2)
    data: bytes = str.encode(args[0], "utf-8") if isinstance(args[0], str) else _codecs_call("buffer", args[0])
    _errors("readbuffer_encode", 2, args)
    return data, bytes.__len__(data)




def _c_int(value: object) -> int:                # the clinic's int: PyLong_AsInt
    n = _number_index(value)
    if n < -2**31 or n >= 2**31:
        raise OverflowError("Python int too large to convert to C int")
    return n


def _wide_decoder(name: str, codec: str, byteorder: int | None) -> object:
    """utf_16_decode and the others: (data, errors=None, final=False, /), and the ex decoder (byteorder None here) with byteorder=0
    before final, whose result says the order it ended with."""
    def decode_function(*args: object, **kwds: object) -> tuple[object, ...]:
        n = _positional(name, args, kwds, 1, 4 if byteorder is None else 3)
        data: bytes = _codecs_call("buffer", args[0])
        errors = _errors(name, 2, args)
        if byteorder is None:
            order = _c_int(args[2]) if n > 2 else 0
            final = n > 3 and (True if args[3] else False)
        else:
            order = byteorder
            final = n > 2 and (True if args[2] else False)
        text, consumed, order = _codecs_call("decode_wide", codec, data, errors, order, final)
        return (text, consumed, order) if byteorder is None else (text, consumed)
    decode_function.__name__ = decode_function.__qualname__ = name
    return decode_function


def _wide_encoder(name: str, codec: str, byteorder: int | None) -> object:
    """utf_16_encode(str, errors=None, byteorder=0, /), and the -le and -be ones without a byteorder."""
    def encode_function(*args: object, **kwds: object) -> tuple[bytes, int]:
        _positional(name, args, kwds, 1, 3 if byteorder is None else 2)
        text = _text(name, args[0])
        errors = _errors(name, 2, args)
        order = (_c_int(args[2]) if len(args) > 2 else 0) if byteorder is None else byteorder
        return _codecs_call("encode_wide", codec, text, errors, order), str.__len__(text)
    encode_function.__name__ = encode_function.__qualname__ = name
    return encode_function


utf_16_decode = _wide_decoder("utf_16_decode", "utf-16", 0)
utf_16_le_decode = _wide_decoder("utf_16_le_decode", "utf-16", -1)
utf_16_be_decode = _wide_decoder("utf_16_be_decode", "utf-16", 1)
utf_16_ex_decode = _wide_decoder("utf_16_ex_decode", "utf-16", None)
utf_16_encode = _wide_encoder("utf_16_encode", "utf-16", None)
utf_16_le_encode = _wide_encoder("utf_16_le_encode", "utf-16", -1)
utf_16_be_encode = _wide_encoder("utf_16_be_encode", "utf-16", 1)
utf_32_decode = _wide_decoder("utf_32_decode", "utf-32", 0)
utf_32_le_decode = _wide_decoder("utf_32_le_decode", "utf-32", -1)
utf_32_be_decode = _wide_decoder("utf_32_be_decode", "utf-32", 1)
utf_32_ex_decode = _wide_decoder("utf_32_ex_decode", "utf-32", None)
utf_32_encode = _wide_encoder("utf_32_encode", "utf-32", None)
utf_32_le_encode = _wide_encoder("utf_32_le_encode", "utf-32", -1)
utf_32_be_encode = _wide_encoder("utf_32_be_encode", "utf-32", 1)
utf_7_decode = _unwritten("utf_7_decode", "_codecs.utf_7_decode (not a phase-1 codec: specification section 7)")
utf_7_encode = _unwritten("utf_7_encode", "_codecs.utf_7_encode (not a phase-1 codec: specification section 7)")
unicode_escape_decode = _unwritten("unicode_escape_decode", "_codecs.unicode_escape_decode (not a phase-1 codec: specification section 7)")
unicode_escape_encode = _unwritten("unicode_escape_encode", "_codecs.unicode_escape_encode (not a phase-1 codec: specification section 7)")
raw_unicode_escape_decode = _unwritten("raw_unicode_escape_decode", "_codecs.raw_unicode_escape_decode (not a phase-1 codec: specification section 7)")
raw_unicode_escape_encode = _unwritten("raw_unicode_escape_encode", "_codecs.raw_unicode_escape_encode (not a phase-1 codec: specification section 7)")
escape_decode = _unwritten("escape_decode", "_codecs.escape_decode (not a phase-1 codec: specification section 7)")
escape_encode = _unwritten("escape_encode", "_codecs.escape_encode (not a phase-1 codec: specification section 7)")
charmap_decode = _unwritten("charmap_decode", "_codecs.charmap_decode (not a phase-1 codec: specification section 7)")
charmap_encode = _unwritten("charmap_encode", "_codecs.charmap_encode (not a phase-1 codec: specification section 7)")
charmap_build = _unwritten("charmap_build", "_codecs.charmap_build (not a phase-1 codec: specification section 7)")

_codecs_call("hooks", _text_encode, _text_decode, _unknown_handler, _start, _lookup_text)
