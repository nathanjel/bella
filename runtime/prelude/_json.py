"""_json, in Python (Modules/_json.c): the scanner and the encoder the json package takes from it, with the C's rules and messages.
scanstring, encode_basestring and encode_basestring_ascii are the module's functions; make_scanner is the Scanner type, called by the
decoder as scan_once(string, idx); make_encoder is the Encoder type, called by JSONEncoder.encode as _iterencode(obj, level) and
answering a one-element tuple. A key read twice in one document is one object (the memo); a failing item adds the C's notes."""

__all__ = ["encode_basestring", "encode_basestring_ascii", "make_encoder", "make_scanner", "scanstring"]

__name__ = "_json"

try:
    _bella_new_instance                          # noqa: B018  # tp_alloc: this type's __new__ makes its instance
    _number_index                                # noqa: B018  # PyNumber_Index
    _tp_name                                     # noqa: B018  # Py_TYPE(obj)->tp_name, and %T
    _dict_next                                   # noqa: B018  # PyDict_Next: the entries as they are at each step
    _raise_as_is                                 # noqa: B018  # a pending error goes on as it is: no context taken (RL-650)
    _own_data                                    # noqa: B018  # an argument's own data as the exact base object: the runtime's (RL-698)
    _repr_text                                   # noqa: B018  # %R: the characters of an object's repr, an exact str (RL-748's class)
except NameError:
    import operator

    _bella_new_instance = object.__new__
    _number_index = operator.index

    def _dict_next(d: dict[object, object], i: int) -> tuple[int, object, object] | None:
        items = list(d.items())
        return (i + 1, *items[i]) if i < len(items) else None

    def _tp_name(obj: object) -> str:
        t = type(obj)
        return t.__name__ if t.__module__ in ("builtins", "__main__") else t.__module__ + "." + t.__name__

    def _raise_as_is(exc: BaseException) -> None:   # a stand-in for CPython's run: the runtime's takes no context
        raise exc

    def _own_data(value: str) -> str:            # a stand-in: the characters
        return str.__str__(value)

    def _repr_text(value: object) -> str:        # a stand-in for CPython's run of this file
        return str.__str__(repr(value))


class _Absent:
    pass


_ABSENT = _Absent()


def _ssize(value: object) -> int:                # the clinic's Py_ssize_t converter: an index that a C ssize_t holds (A14 #8)
    n = _number_index(value)
    if n < -(2**63) or n >= 2**63:
        raise OverflowError("Python int too large to convert to C ssize_t")
    return n
_WHITESPACE = " \t\n\r"
_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}
_HEX = "0123456789abcdefABCDEF"


def _parse_args(name: str, args: tuple[object, ...], kwds: dict[str, object], names: tuple[str, ...], required: int) -> list[object]:
    """PyArg_ParseTupleAndKeywords with a keyword list: the values in order, _ABSENT for an optional one not given."""
    if len(args) + len(kwds) > len(names):
        raise TypeError(name + "() takes at most " + str(len(names)) + " argument" + ("" if len(names) == 1 else "s") + " (" + str(len(args) + len(kwds)) + " given)")
    values: list[object] = list(args)
    for i in range(len(args), len(names)):
        key = names[i]
        if key in kwds:
            values.append(kwds[key])
        elif i < required:
            raise TypeError(name + "() missing required argument '" + key + "' (pos " + str(i + 1) + ")")
        else:
            values.append(_ABSENT)
    for i in range(len(args)):
        if names[i] in kwds:
            raise TypeError("argument for " + name + "() given by name ('" + names[i] + "') and position (" + str(i + 1) + ")")
    for key in kwds:
        if key not in names:
            raise TypeError("'" + key + "' is an invalid keyword argument for " + name + "()")
    return values


def _raise_errmsg(msg: str, s: str, end: int) -> None:   # raise_errmsg: json.decoder.JSONDecodeError
    import json.decoder

    raise json.decoder.JSONDecodeError(msg, s, end)


def _scanstring(pystr: str, end: int, strict: bool) -> tuple[str, int]:   # scanstring_unicode
    length = str.__len__(pystr)
    begin = end - 1
    if end < 0 or length < end:
        raise ValueError("end is out of bounds")
    parts: list[str] = []
    while True:
        nxt = end
        c = ""
        while nxt < length:
            c = pystr[nxt]
            if c == '"' or c == "\\":
                break
            if c <= "\x1f" and strict:
                _raise_errmsg("Invalid control character at", pystr, nxt)
            nxt += 1
        if c == '"' and not parts and nxt < length:   # the fast path: no escape so far
            return pystr[end:nxt], nxt + 1
        if nxt >= length or c != "\\" and c != '"':
            _raise_errmsg("Unterminated string starting at", pystr, begin)
        if nxt != end:
            parts.append(pystr[end:nxt])
        nxt += 1
        if c == '"':
            end = nxt
            break
        if nxt == length:
            _raise_errmsg("Unterminated string starting at", pystr, begin)
        c = pystr[nxt]
        if c != "u":
            end = nxt + 1
            unescaped = _ESCAPES.get(c)
            if unescaped is None:
                _raise_errmsg("Invalid \\escape", pystr, end - 2)
            parts.append(unescaped)  # type: ignore[arg-type]
            continue
        nxt += 1
        end = nxt + 4
        if end > length:
            _raise_errmsg("Invalid \\uXXXX escape", pystr, nxt - 1)
        code = 0
        while nxt < end:
            digit = pystr[nxt]
            if digit not in _HEX:
                _raise_errmsg("Invalid \\uXXXX escape", pystr, end - 5)
            code = (code << 4) | int(digit, 16)
            nxt += 1
        if 0xD800 <= code <= 0xDBFF and end + 6 < length and pystr[nxt] == "\\" and pystr[nxt + 1] == "u":
            nxt += 2
            end += 6
            code2 = 0
            while nxt < end:
                digit = pystr[nxt]
                if digit not in _HEX:
                    _raise_errmsg("Invalid \\uXXXX escape", pystr, end - 5)
                code2 = (code2 << 4) | int(digit, 16)
                nxt += 1
            if 0xDC00 <= code2 <= 0xDFFF:
                code = 0x10000 + (((code - 0xD800) << 10) | (code2 - 0xDC00))
            else:
                end -= 6
        parts.append(chr(code))
    return "".join(parts), end


def scanstring(*args: object, **kwds: object) -> tuple[str, int]:
    """Scan the string s for a JSON string.

End is the index of the character in s after the quote that started the
JSON string. Unescapes all valid JSON string escape sequences and raises
ValueError on attempt to decode an invalid string. If strict is False
then literal control characters are allowed in the string.

Returns a tuple of the decoded string and the index of the character in
s after the end quote."""
    if kwds:
        raise TypeError("_json.scanstring() takes no keyword arguments")
    if len(args) < 2:
        raise TypeError("scanstring expected at least 2 arguments, got " + str(len(args)))
    if len(args) > 3:
        raise TypeError("scanstring expected at most 3 arguments, got " + str(len(args)))
    pystr = args[0]
    if not issubclass(type(pystr), str):
        raise TypeError("scanstring() argument 1 must be str, not " + _tp_name(pystr))
    end = _ssize(args[1])
    strict = True if len(args) < 3 else bool(args[2])
    return _scanstring(str.__str__(pystr), end, strict)


def _ascii_escape(s: str) -> str:               # ascii_escape_unicode
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\b":
            out.append("\\b")
        elif ch == "\f":
            out.append("\\f")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif o >= 0x7F:
            if o >= 0x10000:
                v = o - 0x10000
                out.append("\\u" + format(0xD800 | ((v >> 10) & 0x3FF), "04x") + "\\u" + format(0xDC00 | (v & 0x3FF), "04x"))
            else:
                out.append("\\u" + format(o, "04x"))
        elif o < 0x20:
            out.append("\\u" + format(o, "04x"))
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _escape(s: str) -> str:                     # escape_unicode
    out = ['"']
    for ch in s:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\b":
            out.append("\\b")
        elif ch == "\f":
            out.append("\\f")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ch < "\x20":
            out.append("\\u" + format(ord(ch), "04x"))
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def encode_basestring_ascii(*args: object, **kwds: object) -> str:
    """Return an ASCII-only JSON representation of a Python string"""
    if kwds:
        raise TypeError("_json.encode_basestring_ascii() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("_json.encode_basestring_ascii() takes exactly one argument (" + str(len(args)) + " given)")
    pystr = args[0]
    if not issubclass(type(pystr), str):
        raise TypeError("encode_basestring_ascii() argument must be str, not " + _tp_name(pystr))
    return _ascii_escape(str.__str__(pystr))


def encode_basestring(*args: object, **kwds: object) -> str:
    """Return a JSON representation of a Python string"""
    if kwds:
        raise TypeError("_json.encode_basestring() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("_json.encode_basestring() takes exactly one argument (" + str(len(args)) + " given)")
    pystr = args[0]
    if not issubclass(type(pystr), str):
        raise TypeError("encode_basestring() argument must be str, not " + _tp_name(pystr))
    return _escape(str.__str__(pystr))


class _StopScan(Exception):                      # raise_stop_iteration, carried inside until scan_once raises StopIteration(idx)
    pass


class Scanner:
    """JSON scanner object"""

    __slots__ = ("_strict", "_object_hook", "_object_pairs_hook", "_array_hook", "_parse_float", "_parse_int", "_parse_constant")

    def __new__(cls, *args: object, **kwds: object) -> Scanner:   # scanner_new
        (ctx,) = _parse_args("make_scanner", args, kwds, ("context",), 1)
        self: Scanner = _bella_new_instance(cls)
        self._strict = bool(getattr(ctx, "strict"))  # noqa: B009
        self._object_hook = getattr(ctx, "object_hook")  # noqa: B009
        self._object_pairs_hook = getattr(ctx, "object_pairs_hook")  # noqa: B009
        self._array_hook = getattr(ctx, "array_hook")  # noqa: B009
        self._parse_float = getattr(ctx, "parse_float")  # noqa: B009
        self._parse_int = getattr(ctx, "parse_int")  # noqa: B009
        self._parse_constant = getattr(ctx, "parse_constant")  # noqa: B009
        return self

    @property
    def strict(self) -> bool:
        return self._strict

    @property
    def object_hook(self) -> object:
        return self._object_hook

    @property
    def object_pairs_hook(self) -> object:
        return self._object_pairs_hook

    @property
    def array_hook(self) -> object:
        return self._array_hook

    @property
    def parse_float(self) -> object:
        return self._parse_float

    @property
    def parse_int(self) -> object:
        return self._parse_int

    @property
    def parse_constant(self) -> object:
        return self._parse_constant

    def __call__(self, *args: object, **kwds: object) -> tuple[object, int]:   # scanner_call
        pystr, idx = _parse_args("scan_once", args, kwds, ("string", "idx"), 2)
        if not issubclass(type(pystr), str):
            raise TypeError("first argument must be a string, not " + _tp_name(pystr))
        index = _ssize(idx)
        memo: dict[str, str] = {}
        try:
            return _scan_once(self, memo, str.__str__(pystr), index)
        except _StopScan as stop:
            at = stop.args[0]
        raise StopIteration(at)                  # raise_stop_iteration: an exception of its own, raised outside the handler


def _skip_whitespace(pystr: str, idx: int, end_idx: int) -> int:
    while idx <= end_idx and pystr[idx] in _WHITESPACE:
        idx += 1
    return idx


def _parse_object(s: Scanner, memo: dict[str, str], pystr: str, idx: int) -> tuple[object, int]:   # _parse_object_unicode
    end_idx = str.__len__(pystr) - 1
    has_pairs_hook = s._object_pairs_hook is not None
    pairs: list[tuple[str, object]] = []
    rval: dict[str, object] = {}
    idx = _skip_whitespace(pystr, idx, end_idx)
    if idx > end_idx or pystr[idx] != "}":
        while True:
            if idx > end_idx or pystr[idx] != '"':
                _raise_errmsg("Expecting property name enclosed in double quotes", pystr, idx)
            key, idx = _scanstring(pystr, idx + 1, s._strict)
            key = memo.setdefault(key, key)
            idx = _skip_whitespace(pystr, idx, end_idx)
            if idx > end_idx or pystr[idx] != ":":
                _raise_errmsg("Expecting ':' delimiter", pystr, idx)
            idx = _skip_whitespace(pystr, idx + 1, end_idx)
            val, idx = _scan_once(s, memo, pystr, idx)
            if has_pairs_hook:
                pairs.append((key, val))
            else:
                rval[key] = val
            idx = _skip_whitespace(pystr, idx, end_idx)
            if idx <= end_idx and pystr[idx] == "}":
                break
            if idx > end_idx or pystr[idx] != ",":
                _raise_errmsg("Expecting ',' delimiter", pystr, idx)
            comma_idx = idx
            idx = _skip_whitespace(pystr, idx + 1, end_idx)
            if idx <= end_idx and pystr[idx] == "}":
                _raise_errmsg("Illegal trailing comma before end of object", pystr, comma_idx)
    if has_pairs_hook:
        return s._object_pairs_hook(pairs), idx + 1  # type: ignore[operator]
    if s._object_hook is not None:
        return s._object_hook(rval), idx + 1  # type: ignore[operator]
    return rval, idx + 1


def _parse_array(s: Scanner, memo: dict[str, str], pystr: str, idx: int) -> tuple[object, int]:   # _parse_array_unicode
    end_idx = str.__len__(pystr) - 1
    rval: list[object] = []
    idx = _skip_whitespace(pystr, idx, end_idx)
    if idx > end_idx or pystr[idx] != "]":
        while True:
            val, idx = _scan_once(s, memo, pystr, idx)
            rval.append(val)
            idx = _skip_whitespace(pystr, idx, end_idx)
            if idx <= end_idx and pystr[idx] == "]":
                break
            if idx > end_idx or pystr[idx] != ",":
                _raise_errmsg("Expecting ',' delimiter", pystr, idx)
            comma_idx = idx
            idx = _skip_whitespace(pystr, idx + 1, end_idx)
            if idx <= end_idx and pystr[idx] == "]":
                _raise_errmsg("Illegal trailing comma before end of array", pystr, comma_idx)
    if idx > end_idx or pystr[idx] != "]":
        _raise_errmsg("Expecting value", pystr, end_idx)
    if s._array_hook is not None:
        return s._array_hook(rval), idx + 1  # type: ignore[operator]
    return rval, idx + 1


def _parse_constant(s: Scanner, constant: str, idx: int) -> tuple[object, int]:
    return s._parse_constant(constant), idx + str.__len__(constant)  # type: ignore[operator]


def _is_digit(ch: str) -> bool:
    return "0" <= ch <= "9"


def _match_number(s: Scanner, pystr: str, start: int) -> tuple[object, int]:   # _match_number_unicode
    end_idx = str.__len__(pystr) - 1
    idx = start
    is_float = False
    if pystr[idx] == "-":
        idx += 1
        if idx > end_idx:
            raise _StopScan(start)
    if "1" <= pystr[idx] <= "9":
        idx += 1
        while idx <= end_idx and _is_digit(pystr[idx]):
            idx += 1
    elif pystr[idx] == "0":
        idx += 1
    else:
        raise _StopScan(start)
    if idx < end_idx and pystr[idx] == "." and _is_digit(pystr[idx + 1]):
        is_float = True
        idx += 2
        while idx <= end_idx and _is_digit(pystr[idx]):
            idx += 1
    if idx < end_idx and pystr[idx] in "eE":
        e_start = idx
        idx += 1
        if idx < end_idx and pystr[idx] in "-+":
            idx += 1
        while idx <= end_idx and _is_digit(pystr[idx]):
            idx += 1
        if _is_digit(pystr[idx - 1]):
            is_float = True
        else:
            idx = e_start
    numstr = pystr[start:idx]
    if is_float and s._parse_float is not float:
        return s._parse_float(numstr), idx  # type: ignore[operator]
    if not is_float and s._parse_int is not int:
        return s._parse_int(numstr), idx  # type: ignore[operator]
    if is_float:
        return float(numstr), idx
    return int(numstr), idx


def _scan_once(s: Scanner, memo: dict[str, str], pystr: str, idx: int) -> tuple[object, int]:   # scan_once_unicode
    length = str.__len__(pystr)
    if idx < 0:
        raise ValueError("idx cannot be negative")
    if idx >= length:
        raise _StopScan(idx)
    c = pystr[idx]
    if c == '"':
        return _scanstring(pystr, idx + 1, s._strict)
    if c == "{":
        return _parse_object(s, memo, pystr, idx + 1)
    if c == "[":
        return _parse_array(s, memo, pystr, idx + 1)
    if c == "n":
        if idx + 3 < length and pystr[idx + 1:idx + 4] == "ull":
            return None, idx + 4
    elif c == "t":
        if idx + 3 < length and pystr[idx + 1:idx + 4] == "rue":
            return True, idx + 4
    elif c == "f":
        if idx + 4 < length and pystr[idx + 1:idx + 5] == "alse":
            return False, idx + 5
    elif c == "N":
        if idx + 2 < length and pystr[idx + 1:idx + 3] == "aN":
            return _parse_constant(s, "NaN", idx)
    elif c == "I":
        if idx + 7 < length and pystr[idx + 1:idx + 8] == "nfinity":
            return _parse_constant(s, "Infinity", idx)
    elif c == "-":
        if idx + 8 < length and pystr[idx + 1:idx + 9] == "Infinity":
            return _parse_constant(s, "-Infinity", idx)
    return _match_number(s, pystr, idx)


make_scanner = Scanner


class Encoder:
    """Encoder(markers, default, encoder, indent, key_separator, item_separator, sort_keys, skipkeys, allow_nan)"""

    __slots__ = ("_markers", "_defaultfn", "_encoder", "_indent", "_key_separator", "_item_separator", "_sort_keys", "_skipkeys", "_allow_nan",
                 "_fast_encode")

    def __new__(cls, *args: object, **kwds: object) -> Encoder:   # encoder_new: "OOOOUUppp:make_encoder"
        markers, defaultfn, encoder, indent, key_separator, item_separator, sort_keys, skipkeys, allow_nan = _parse_args(
            "make_encoder", args, kwds,
            ("markers", "default", "encoder", "indent", "key_separator", "item_separator", "sort_keys", "skipkeys", "allow_nan"), 9)
        if not issubclass(type(key_separator), str):
            raise TypeError("make_encoder() argument 5 must be str, not " + _tp_name(key_separator))
        if not issubclass(type(item_separator), str):
            raise TypeError("make_encoder() argument 6 must be str, not " + _tp_name(item_separator))
        if markers is not None and not issubclass(type(markers), dict):
            raise TypeError("make_encoder() argument 1 must be dict or None, not " + _tp_name(markers))
        self: Encoder = _bella_new_instance(cls)
        self._markers = markers
        self._defaultfn = defaultfn
        self._encoder = encoder
        self._indent = indent
        self._key_separator = key_separator
        self._item_separator = item_separator
        self._sort_keys = bool(sort_keys)
        self._skipkeys = bool(skipkeys)
        self._allow_nan = bool(allow_nan)
        self._fast_encode = _ascii_escape if encoder is encode_basestring_ascii else _escape if encoder is encode_basestring else None
        return self

    @property
    def markers(self) -> object:
        return self._markers

    @property
    def default(self) -> object:
        return self._defaultfn

    @property
    def encoder(self) -> object:
        return self._encoder

    @property
    def indent(self) -> object:
        return self._indent

    @property
    def key_separator(self) -> object:
        return self._key_separator

    @property
    def item_separator(self) -> object:
        return self._item_separator

    @property
    def sort_keys(self) -> bool:
        return self._sort_keys

    @property
    def skipkeys(self) -> bool:
        return self._skipkeys

    def __call__(self, *args: object, **kwds: object) -> tuple[str]:   # encoder_call: "On:_iterencode"
        obj, level = _parse_args("_iterencode", args, kwds, ("obj", "_current_indent_level"), 2)
        indent_level = _ssize(level)
        cache: list[str] | None = None
        if self._indent is not None:             # create_indent_cache: the newline at the level given, then levels from 0
            newline_indent = "\n"
            if indent_level:
                newline_indent = _concat(newline_indent, self._indent * indent_level)  # type: ignore[operator]   # PyUnicode_AppendAndDel of PySequence_Repeat
            cache = [newline_indent]
        parts: list[str] = []
        _encode_obj(self, parts, obj, 0, cache)
        return ("".join(parts),)


def _note(exc: BaseException, text: str) -> None:   # _PyErr_FormatNote: BaseException_add_note itself, not an override (A14 #4)
    BaseException.add_note(exc, text)


def _raise_noted(exc: BaseException, prefix: str, shown: object = _ABSENT) -> None:
    """_PyErr_FormatNote and the return of the error: the C makes the note's text while the error is pending, so a repr of the
    program's that runs for it sees whatever was being handled around the call, not this error; a note that cannot be made
    is an error of its own with the first as its context (_PyErr_ChainExceptions1). The caller has left its handler (RL-707)."""
    second: BaseException | None = None
    try:                                         # the text (%R: the repr's characters, RL-748) and the add: what either raises has
        text = prefix if shown is _ABSENT else prefix + _repr_text(shown)   # the first error as its context (RL-725)
        BaseException.add_note(exc, text)
    except BaseException as e:
        second = e
    if second is not None:
        second.__context__ = exc
        _raise_as_is(second)
    _raise_as_is(exc)


def _encode_float(s: Encoder, obj: float) -> str:   # encoder_encode_float: PyFloat_AS_DOUBLE, no comparison of the subclass's (A14 #1)
    value = float.__float__(obj)
    if value != value or value == _INF or value == -_INF:
        if not s._allow_nan:
            raise ValueError("Out of range float values are not JSON compliant: " + _repr_text(obj))
        if value > 0:
            return "Infinity"
        if value < 0:
            return "-Infinity"
        return "NaN"
    return float.__repr__(obj)


_INF = float("inf")


def _write_string(s: Encoder, parts: list[str], obj: str) -> None:   # encoder_write_string
    if s._fast_encode is not None:
        parts.append(s._fast_encode(str.__str__(obj)))
        return
    encoded = s._encoder(obj)  # type: ignore[operator]
    if not issubclass(type(encoded), str):
        raise TypeError("encoder() must return a string, not " + _tp_name(encoded))
    parts.append(_written(encoded))


def _concat(left: str, right: object) -> str:   # PyUnicode_Concat: the two texts, never a subclass's __add__ or __radd__ (review F17 #12)
    if not issubclass(type(right), str):
        raise TypeError('can only concatenate str (not "' + _tp_name(right) + '") to str')
    return str.__add__(str.__str__(left), str.__str__(right))


def _written(text: str) -> str:   # PyUnicodeWriter_WriteStr: an exact str as it is, a subclass's instance through str()
    return text if type(text) is str else str(text)


def _item_separator(s: Encoder, level: int, cache: list[str]) -> str:   # get_item_separator, filling the cache a level at a time
    while level * 2 > len(cache):              # update_indent_cache
        have = (len(cache) + 1) // 2
        newline_indent = _concat(cache[(have - 1) * 2], s._indent)
        cache.append(_concat(s._item_separator, newline_indent))
        cache.append(newline_indent)
    return cache[level * 2 - 1]


def _encode_obj(s: Encoder, parts: list[str], obj: object, level: int, cache: list[str] | None) -> None:   # encoder_listencode_obj
    if obj is None:
        parts.append("null")
    elif obj is True:
        parts.append("true")
    elif obj is False:
        parts.append("false")
    elif issubclass(type(obj), str):
        _write_string(s, parts, obj)
    elif issubclass(type(obj), int):
        parts.append(int.__repr__(obj))
    elif issubclass(type(obj), float):
        parts.append(_encode_float(s, obj))
    elif issubclass(type(obj), (list, tuple)):
        _encode_list(s, parts, obj, level, cache)
    elif issubclass(type(obj), (dict, frozendict)):
        _encode_dict(s, parts, obj, level, cache)
    else:
        ident = None
        markers = s._markers
        if markers is not None:
            ident = id(obj)
            if dict.__contains__(markers, ident):    # PyDict_Contains, PyDict_SetItem: the dict's own, whatever its class has (RL-684)
                raise ValueError("Circular reference detected")
            dict.__setitem__(markers, ident, obj)
        newobj = s._defaultfn(obj)  # type: ignore[operator]
        failed: BaseException | None = None
        try:
            _encode_obj(s, parts, newobj, level, cache)
        except BaseException as exc:
            failed = exc
        if failed is not None:
            _raise_noted(failed, "when serializing " + _tp_name(obj) + " object")
        if ident is not None:
            dict.__delitem__(markers, ident)  # type: ignore[arg-type]


def _encode_key_value(s: Encoder, parts: list[str], first: list[bool], dct: object, key: object, value: object, level: int,
                      cache: list[str] | None, separator: str) -> None:   # encoder_encode_key_value
    if issubclass(type(key), str):
        keystr: object = key
    elif issubclass(type(key), float):
        keystr = _encode_float(s, key)
    elif key is True or key is False or key is None:
        keystr = "true" if key is True else "false" if key is False else "null"
    elif issubclass(type(key), int):
        keystr = int.__repr__(key)
    elif s._skipkeys:
        return
    else:
        raise TypeError("keys must be str, int, float, bool or None, not " + _tp_name(key))
    if first[0]:
        first[0] = False
        if s._indent is not None:
            parts.append(cache[level * 2])  # type: ignore[index]
    else:
        parts.append(_written(separator))
    _write_string(s, parts, keystr)  # type: ignore[arg-type]
    parts.append(_written(s._key_separator))
    failed: BaseException | None = None
    try:
        _encode_obj(s, parts, value, level, cache)
    except BaseException as exc:
        failed = exc
    if failed is not None:
        _raise_noted(failed, "when serializing " + _tp_name(dct) + " item ", key)


def _encode_dict(s: Encoder, parts: list[str], dct: object, level: int, cache: list[str] | None) -> None:   # encoder_listencode_dict
    if (dict.__len__(dct) if issubclass(type(dct), dict) else len(dct)) == 0:  # type: ignore[arg-type]   # PyDict_GET_SIZE
        parts.append("{}")
        return
    ident = None
    markers = s._markers
    if markers is not None:
        ident = id(dct)
        if dict.__contains__(markers, ident):    # PyDict_Contains, PyDict_SetItem: the dict's own, whatever its class has (RL-684)
            raise ValueError("Circular reference detected")
        dict.__setitem__(markers, ident, dct)
    parts.append("{")
    separator = s._item_separator
    if s._indent is not None:
        level += 1
        separator = _item_separator(s, level, cache)  # type: ignore[arg-type]
    first = [True]
    if s._sort_keys or type(dct) is not dict and type(dct) is not frozendict:
        items = dct.items()  # type: ignore[attr-defined]
        if type(items) is not list:              # PyMapping_Items: what items() gave if it is an exact list, else its iterator listed
            items = list(iter(items))
        if s._sort_keys:
            list.sort(items)
        at = 0
        while at < list.__len__(items):          # PyList_GET_SIZE and PyList_GET_ITEM; a pair's two slots (PyTuple_GET_ITEM), RL-682
            item = list.__getitem__(items, at)
            if not issubclass(type(item), tuple) or tuple.__len__(item) != 2:
                raise ValueError("items must return 2-tuples")
            _encode_key_value(s, parts, first, dct, tuple.__getitem__(item, 0), tuple.__getitem__(item, 1), level, cache, separator)
            at += 1
    else:                                        # PyDict_Next: the entries as they are at each step, an inserted one included (A14 #2)
        pos = 0
        while True:
            step = _dict_next(dct, pos)  # type: ignore[arg-type]
            if step is None:
                break
            pos, key, value = step
            _encode_key_value(s, parts, first, dct, key, value, level, cache, separator)
    if ident is not None:
        dict.__delitem__(markers, ident)  # type: ignore[arg-type]
    if s._indent is not None and not first[0]:
        level -= 1
        parts.append(cache[level * 2])  # type: ignore[index]
    parts.append("}")


def _encode_list(s: Encoder, parts: list[str], seq: object, level: int, cache: list[str] | None) -> None:   # encoder_listencode_list
    # PySequence_Fast: an exact list or tuple is the object itself, its size read again at every step and an item what it holds
    # then; a subclass is iterated into a list first (A14 #3)
    fast: object = seq if type(seq) is list or type(seq) is tuple else list(iter(seq))  # type: ignore[call-overload]   # of its iterator: no length is asked (RL-661)
    size = list.__len__ if issubclass(type(fast), list) else tuple.__len__
    item = list.__getitem__ if issubclass(type(fast), list) else tuple.__getitem__
    if size(fast) == 0:  # type: ignore[arg-type]
        parts.append("[]")
        return
    ident = None
    markers = s._markers
    if markers is not None:
        ident = id(seq)
        if dict.__contains__(markers, ident):    # PyDict_Contains, PyDict_SetItem: the dict's own, whatever its class has (RL-684)
            raise ValueError("Circular reference detected")
        dict.__setitem__(markers, ident, seq)
    parts.append("[")
    separator = s._item_separator
    if s._indent is not None:
        level += 1
        separator = _item_separator(s, level, cache)  # type: ignore[arg-type]
        parts.append(cache[level * 2])  # type: ignore[index]
    i = 0
    while i < size(fast):  # type: ignore[arg-type]
        obj = item(fast, i)  # type: ignore[arg-type]
        if i:
            parts.append(_written(separator))
        failed: BaseException | None = None
        try:
            _encode_obj(s, parts, obj, level, cache)
        except BaseException as exc:
            failed = exc
        if failed is not None:
            _raise_noted(failed, "when serializing " + _tp_name(seq) + " item " + str(i))
        i += 1
    if ident is not None:
        dict.__delitem__(markers, ident)  # type: ignore[arg-type]
    if s._indent is not None:
        level -= 1
        parts.append(cache[level * 2])  # type: ignore[index]
    parts.append("]")


make_encoder = Encoder
