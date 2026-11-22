"""_csv, in Python (Modules/_csv.c): the Dialect type with the C's conversions and checks in its order, the reader (its state
machine over each character and the line terminator, the field size limit, the quoting modes' conversions) and the writer (the join
with escaping and quoting, the empty-record rules), the dialect registry, field_size_limit, the QUOTE_* constants and Error. Each
message is the C's. The csv package imports from here."""

__all__ = ["Dialect", "Error", "QUOTE_ALL", "QUOTE_MINIMAL", "QUOTE_NONE", "QUOTE_NONNUMERIC", "QUOTE_NOTNULL", "QUOTE_STRINGS", "Reader",
           "Writer", "_dialects", "field_size_limit", "get_dialect", "list_dialects", "reader", "register_dialect", "unregister_dialect",
           "writer"]

__name__ = "_csv"

try:
    _bella_new_instance                          # noqa: B018  # tp_alloc: this type's __new__ makes its instance
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _tp_name                                     # noqa: B018  # Py_TYPE(o)->tp_name
    _unpack_keywords                             # noqa: B018  # _PyArg_UnpackKeywords
    _keyword_suggestion                          # noqa: B018  # _Py_CalculateSuggestions
    _has_slot                                    # noqa: B018  # a slot of the type, by its own MRO and dicts: the runtime's (RL-644)
    _is_c_type                                   # noqa: B018  # the object's type is CPython's, not a class of the program's
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_new_instance = object.__new__
    _bella_refuse: Callable[..., Any] = _missing

    def _tp_name(o: object) -> str:
        return type(o).__name__

    _unpack_keywords: Callable[..., Any] = _missing
    _keyword_suggestion: Callable[..., Any] = _missing
    _has_slot: Callable[..., bool] = _missing

    def _is_c_type(value: object) -> bool:       # a stand-in for CPython's run of this file
        return type(value).__module__ != "__main__"

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

QUOTE_MINIMAL = 0
QUOTE_ALL = 1
QUOTE_NONNUMERIC = 2
QUOTE_NONE = 3
QUOTE_STRINGS = 4
QUOTE_NOTNULL = 5

_dialects: dict[object, object] = {}
_field_limit = 128 * 1024
_ABSENT: object = object()
_EOL: object = object()                          # the end of a line, after its characters


class Error(Exception):
    pass


Error.__module__ = "_csv"


# ---- Dialect ----------------------------------------------------------------------------------------------------------------

_DIALECT_KWS = ("dialect", "delimiter", "doublequote", "escapechar", "lineterminator", "quotechar", "quoting", "skipinitialspace", "strict")


def _set_bool(value: object, default: bool) -> bool:
    return default if value is _ABSENT else bool(value)


def _set_int(name: str, value: object, default: int) -> int:
    if value is _ABSENT:
        return default
    if type(value) is not int:
        raise TypeError('"' + name + '" must be an integer, not ' + _tp_name(value))
    n = int.__index__(value)
    if n > 2**31 - 1 or n < -(2**31):
        raise OverflowError("Python int too large to convert to C int")
    return n


def _set_char_or_none(name: str, value: object, default: str | None) -> str | None:
    if value is _ABSENT:
        return default
    if value is None:
        return None
    if not issubclass(type(value), str):
        raise TypeError('"' + name + '" must be a unicode character or None, not ' + _tp_name(value))
    if str.__len__(value) != 1:  # type: ignore[arg-type]
        raise TypeError('"' + name + '" must be a unicode character or None, not a string of length ' + str(str.__len__(value)))  # type: ignore[arg-type]
    return str.__str__(value)  # type: ignore[arg-type]  # the text itself, whatever a subclass's __str__ says


def _set_char(name: str, value: object, default: str) -> str:
    if value is _ABSENT:
        return default
    if not issubclass(type(value), str):
        raise TypeError('"' + name + '" must be a unicode character, not ' + _tp_name(value))
    if str.__len__(value) != 1:  # type: ignore[arg-type]
        raise TypeError('"' + name + '" must be a unicode character, not a string of length ' + str(str.__len__(value)))  # type: ignore[arg-type]
    return str.__str__(value)  # type: ignore[arg-type]  # the text itself, whatever a subclass's __str__ says


def _set_str(name: str, value: object, default: str) -> str:
    if value is _ABSENT:
        return default
    if not issubclass(type(value), str):
        raise TypeError('"' + name + '" must be a string, not ' + _tp_name(value))
    return value  # type: ignore[return-value]


def _check_char(name: str, c: str | None, lineterminator: str, allowspace: bool) -> None:   # dialect_check_char
    if c is None:
        return
    if c == "\r" or c == "\n" or (c == " " and not allowspace):
        raise ValueError("bad " + name + " value")
    if str.find(lineterminator, c) >= 0:         # PyUnicode_FindChar: not a subclass's __contains__ (review F17 #12)
        raise ValueError("bad " + name + " or lineterminator value")


def _check_chars(name1: str, name2: str, c1: str | None, c2: str | None) -> None:   # dialect_check_chars
    if c1 == c2 and c1 is not None:
        raise ValueError("bad " + name1 + " or " + name2 + " value")


class Dialect:
    """CSV dialect

The Dialect type records CSV parsing and generation options.
"""

    __slots__ = ("_delimiter", "_doublequote", "_escapechar", "_lineterminator", "_quotechar", "_quoting", "_skipinitialspace", "_strict")

    def __new__(cls, *args: object, **kwds: object) -> Dialect:
        # PyArg_ParseTupleAndKeywords(args, kwargs, "|OOOOOOOOO", dialect_kws, ...)
        if len(args) > 9:
            raise TypeError("function takes at most 9 arguments (" + str(len(args)) + " given)")
        given: list[object] = [*args, *[_ABSENT] * (9 - len(args))]
        for keyword, value in kwds.items():
            if keyword not in _DIALECT_KWS:
                suggestion = _keyword_suggestion(_DIALECT_KWS, keyword)
                raise TypeError("this function got an unexpected keyword argument '" + keyword + "'" + ("" if suggestion is None else ". Did you mean '" + suggestion + "'?"))
            at = _DIALECT_KWS.index(keyword)
            if given[at] is not _ABSENT:
                raise TypeError("argument for function given by name ('" + keyword + "') and position (" + str(at + 1) + ")")
            given[at] = value
        dialect, delimiter, doublequote, escapechar, lineterminator, quotechar, quoting, skipinitialspace, strict = given
        if dialect is not _ABSENT:
            if issubclass(type(dialect), str):
                dialect = _from_registry(dialect)
            if issubclass(type(dialect), Dialect) and all(v is _ABSENT for v in given[1:]):   # the instance itself is reused
                return dialect
            if delimiter is _ABSENT:
                delimiter = getattr(dialect, "delimiter", _ABSENT)
            if doublequote is _ABSENT:
                doublequote = getattr(dialect, "doublequote", _ABSENT)
            if escapechar is _ABSENT:
                escapechar = getattr(dialect, "escapechar", _ABSENT)
            if lineterminator is _ABSENT:
                lineterminator = getattr(dialect, "lineterminator", _ABSENT)
            if quotechar is _ABSENT:
                quotechar = getattr(dialect, "quotechar", _ABSENT)
            if quoting is _ABSENT:
                quoting = getattr(dialect, "quoting", _ABSENT)
            if skipinitialspace is _ABSENT:
                skipinitialspace = getattr(dialect, "skipinitialspace", _ABSENT)
            if strict is _ABSENT:
                strict = getattr(dialect, "strict", _ABSENT)
        self: Dialect = _bella_new_instance(cls)
        c_delimiter = _set_char("delimiter", delimiter, ",")
        c_doublequote = _set_bool(doublequote, True)
        c_escapechar = _set_char_or_none("escapechar", escapechar, None)
        c_lineterminator = _set_str("lineterminator", lineterminator, "\r\n")
        c_quotechar = _set_char_or_none("quotechar", quotechar, '"')
        c_quoting = _set_int("quoting", quoting, QUOTE_MINIMAL)
        c_skipinitialspace = _set_bool(skipinitialspace, False)
        c_strict = _set_bool(strict, False)
        if c_quoting not in (QUOTE_MINIMAL, QUOTE_ALL, QUOTE_NONNUMERIC, QUOTE_NONE, QUOTE_STRINGS, QUOTE_NOTNULL):
            raise TypeError('bad "quoting" value')
        if quotechar is None and quoting is _ABSENT:
            c_quoting = QUOTE_NONE
        if c_quoting != QUOTE_NONE and c_quotechar is None:
            raise TypeError("quotechar must be set if quoting enabled")
        _check_char("delimiter", c_delimiter, c_lineterminator, True)
        _check_char("escapechar", c_escapechar, c_lineterminator, not c_skipinitialspace)
        _check_char("quotechar", c_quotechar, c_lineterminator, not c_skipinitialspace)
        _check_chars("delimiter", "escapechar", c_delimiter, c_escapechar)
        _check_chars("delimiter", "quotechar", c_delimiter, c_quotechar)
        _check_chars("escapechar", "quotechar", c_escapechar, c_quotechar)
        self._delimiter = c_delimiter
        self._doublequote = c_doublequote
        self._escapechar = c_escapechar
        self._lineterminator = c_lineterminator
        self._quotechar = c_quotechar
        self._quoting = c_quoting
        self._skipinitialspace = c_skipinitialspace
        self._strict = c_strict
        return self

    @property
    def delimiter(self) -> str:
        return self._delimiter

    @property
    def doublequote(self) -> bool:
        return self._doublequote

    @property
    def escapechar(self) -> str | None:
        return self._escapechar

    @property
    def lineterminator(self) -> str:
        return self._lineterminator

    @property
    def quotechar(self) -> str | None:
        return self._quotechar

    @property
    def quoting(self) -> int:
        return self._quoting

    @property
    def skipinitialspace(self) -> bool:
        return self._skipinitialspace

    @property
    def strict(self) -> bool:
        return self._strict

    def __reduce__(self, *args: object) -> object:
        """raises an exception to avoid pickling"""
        raise TypeError("cannot pickle 'Dialect' instances")

    def __reduce_ex__(self, *args: object) -> object:
        """raises an exception to avoid pickling"""
        raise TypeError("cannot pickle 'Dialect' instances")


Dialect.__module__ = "_csv"


def _from_registry(name: object) -> object:      # get_dialect_from_registry
    found = _dialects.get(name, _ABSENT)
    if found is _ABSENT:
        raise Error("unknown dialect")
    return found


def _call_dialect(dialect: object, kwds: dict[str, object]) -> Dialect:   # _call_dialect
    if dialect is _ABSENT:
        return Dialect(**kwds)
    return Dialect(dialect, **kwds)


# ---- the reader -------------------------------------------------------------------------------------------------------------

_START_RECORD, _START_FIELD, _ESCAPED_CHAR, _IN_FIELD, _IN_QUOTED_FIELD, _ESCAPE_IN_QUOTED_FIELD, _QUOTE_IN_QUOTED_FIELD, _EAT_CRNL, _AFTER_ESCAPED_CRNL = range(9)


class reader:  # noqa: N801                     # _csv.reader: made by reader() alone
    """CSV reader

Reader objects are responsible for reading and parsing tabular data
in CSV format.
"""

    __slots__ = ("_dialect", "_field", "_fields", "_input", "_line_num", "_state", "_unquoted")

    def __iter__(self) -> reader:
        return self

    def __next__(self) -> list[object]:          # Reader_iternext
        _parse_reset(self)
        d: Dialect = self._dialect
        while True:
            ended = False
            try:
                line = next(self._input)
            except StopIteration:
                ended = True                     # PyIter_Next: the input's end, its StopIteration cleared
            if ended:
                if len(self._field) != 0 or self._state == _IN_QUOTED_FIELD:
                    if d._strict:
                        raise Error("unexpected end of data")
                    _parse_save_field(self)
                    break
                raise StopIteration              # tp_iternext's NULL: a StopIteration of next()'s own, without the input's value
            if not issubclass(type(line), str):
                raise Error("iterator should return strings, not " + _tp_name(line) + " (the file should be opened in text mode)")
            if self._fields is None:
                raise Error("iterator has already advanced the reader")
            self._line_num += 1
            for c in str.__str__(line):  # type: ignore[arg-type]  # the text itself: a subclass's __iter__ is not consulted
                _parse_process_char(self, c)
            del line                             # Py_DECREF(lineobj) before the next line is asked for (RL-830)
            _parse_process_char(self, _EOL)
            if self._state == _START_RECORD:
                break
        fields = self._fields
        self._fields = None
        return fields  # type: ignore[return-value]

    @property
    def dialect(self) -> Dialect:
        return self._dialect

    @property
    def line_num(self) -> int:
        return self._line_num


reader.__module__ = "_csv"
Reader = reader


# The C's own functions over the struct (parse_reset, parse_save_field, parse_add_char, parse_process_char): no names of
# the type, as there (RL-507)
def _parse_reset(self: Reader) -> None:                    # parse_reset
    self._fields = []
    self._field = []
    self._state = _START_RECORD
    self._unquoted = False


def _parse_save_field(self: Reader) -> None:               # parse_save_field
    d: Dialect = self._dialect
    quoting = d._quoting
    text = "".join(self._field)
    field: object
    if self._unquoted and len(self._field) == 0 and quoting in (QUOTE_NOTNULL, QUOTE_STRINGS):
        field = None
    else:
        field = text
        if self._unquoted and len(self._field) != 0 and quoting in (QUOTE_NONNUMERIC, QUOTE_STRINGS):
            field = float(text)
        self._field = []
    self._fields.append(field)  # type: ignore[union-attr]


def _parse_add_char(self: Reader, c: str) -> None:         # parse_add_char
    if len(self._field) >= _field_limit:
        raise Error("field larger than field limit (" + str(_field_limit) + ")")
    self._field.append(c)


def _parse_process_char(self: Reader, c: object) -> None:       # parse_process_char
    d: Dialect = self._dialect
    state = self._state
    if state == _START_RECORD:
        if c is _EOL:
            return
        if c == "\n" or c == "\r":
            self._state = _EAT_CRNL
            return
        self._state = state = _START_FIELD
    if state == _START_FIELD:
        self._unquoted = True
        if c == "\n" or c == "\r" or c is _EOL:
            _parse_save_field(self)
            self._state = _START_RECORD if c is _EOL else _EAT_CRNL
        elif c == d._quotechar and d._quoting != QUOTE_NONE:
            self._unquoted = False
            self._state = _IN_QUOTED_FIELD
        elif c == d._escapechar:
            self._state = _ESCAPED_CHAR
        elif c == " " and d._skipinitialspace:
            pass
        elif c == d._delimiter:
            _parse_save_field(self)
        else:
            _parse_add_char(self, c)  # type: ignore[arg-type]
            self._state = _IN_FIELD
    elif state == _ESCAPED_CHAR:
        if c == "\n" or c == "\r":
            _parse_add_char(self, c)  # type: ignore[arg-type]
            self._state = _AFTER_ESCAPED_CRNL
            return
        if c is _EOL:
            c = "\n"
        _parse_add_char(self, c)  # type: ignore[arg-type]
        self._state = _IN_FIELD
    elif state == _AFTER_ESCAPED_CRNL or state == _IN_FIELD:
        if state == _AFTER_ESCAPED_CRNL and c is _EOL:
            return
        if c == "\n" or c == "\r" or c is _EOL:
            _parse_save_field(self)
            self._state = _START_RECORD if c is _EOL else _EAT_CRNL
        elif c == d._escapechar:
            self._state = _ESCAPED_CHAR
        elif c == d._delimiter:
            _parse_save_field(self)
            self._state = _START_FIELD
        else:
            _parse_add_char(self, c)  # type: ignore[arg-type]
    elif state == _IN_QUOTED_FIELD:
        if c is _EOL:
            pass
        elif c == d._escapechar:
            self._state = _ESCAPE_IN_QUOTED_FIELD
        elif c == d._quotechar and d._quoting != QUOTE_NONE:
            self._state = _QUOTE_IN_QUOTED_FIELD if d._doublequote else _IN_FIELD
        else:
            _parse_add_char(self, c)  # type: ignore[arg-type]
    elif state == _ESCAPE_IN_QUOTED_FIELD:
        if c is _EOL:
            c = "\n"
        _parse_add_char(self, c)  # type: ignore[arg-type]
        self._state = _IN_QUOTED_FIELD
    elif state == _QUOTE_IN_QUOTED_FIELD:
        if d._quoting != QUOTE_NONE and c == d._quotechar:
            _parse_add_char(self, c)  # type: ignore[arg-type]
            self._state = _IN_QUOTED_FIELD
        elif c == d._delimiter:
            _parse_save_field(self)
            self._state = _START_FIELD
        elif c == "\n" or c == "\r" or c is _EOL:
            _parse_save_field(self)
            self._state = _START_RECORD if c is _EOL else _EAT_CRNL
        elif not d._strict:
            _parse_add_char(self, c)  # type: ignore[arg-type]
            self._state = _IN_FIELD
        else:
            raise Error("'" + d._delimiter + "' expected after '" + str(d._quotechar) + "'")
    elif state == _EAT_CRNL:
        if c == "\n" or c == "\r":
            pass
        elif c is _EOL:
            self._state = _START_RECORD
        else:
            raise Error("new-line character seen in unquoted field - do you need to open the file with newline=''?")


def _unpack(fname: str, args: tuple[object, ...], low: int, high: int) -> None:   # PyArg_UnpackTuple
    if len(args) < low:
        raise TypeError(fname + " expected " + ("at least " if low < high else "") + str(low) + " argument" + ("" if low == 1 else "s") + ", got " + str(len(args)))
    if len(args) > high:
        raise TypeError(fname + " expected " + ("at most " if low < high else "") + str(high) + " argument" + ("" if high == 1 else "s") + ", got " + str(len(args)))


def _reader_new(*args: object, **kwds: object) -> reader:
    """Return a reader object that will process lines from the given iterable.

The "iterable" argument can be any object that returns a line
of input for each iteration, such as a file object or a list.  The
optional "dialect" argument defines a CSV dialect.  The function
also accepts optional keyword arguments which override settings
provided by the dialect.

The returned object is an iterator.  Each iteration returns a row
of the CSV file (which can span multiple input lines).
"""
    self: reader = _bella_new_instance(Reader)
    self._line_num = 0
    _parse_reset(self)
    _unpack("reader", args, 1, 2)
    self._input = iter(args[0])  # type: ignore[call-overload]
    self._dialect = _call_dialect(args[1] if len(args) > 1 else _ABSENT, kwds)
    return self


_reader_new.__name__ = "reader"
_reader_new.__qualname__ = "reader"
reader = _reader_new  # type: ignore[assignment,misc]


# ---- the writer -------------------------------------------------------------------------------------------------------------

def _number_check(o: object) -> bool:            # PyNumber_Check
    return _has_slot(o, "__index__") or _has_slot(o, "__int__") or _has_slot(o, "__float__") or issubclass(type(o), complex)


class writer:  # noqa: N801                     # _csv.writer: made by writer() alone
    """CSV writer

Writer objects are responsible for generating tabular data
in CSV format from sequence input.
"""

    __slots__ = ("_dialect", "_num_fields", "_rec", "_write")

    def writerow(self, *args: object, **kwds: object) -> object:
        """Construct and write a CSV record from an iterable of fields.

Non-string elements will be converted to string."""
        if kwds:
            raise TypeError("writer.writerow() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("writer.writerow() takes exactly one argument (" + str(len(args)) + " given)")
        return _csv_writerow(self, args[0])

    def writerows(self, *args: object, **kwds: object) -> None:
        """Construct and write a series of iterables to a csv file.

Non-string elements will be converted to string."""
        if kwds:
            raise TypeError("writer.writerows() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("writer.writerows() takes exactly one argument (" + str(len(args)) + " given)")
        for row in args[0]:  # type: ignore[attr-defined]
            _csv_writerow(self, row)
            del row                              # Py_DECREF(row_obj) before the next tp_iternext (RL-782)

    @property
    def dialect(self) -> Dialect:
        return self._dialect


writer.__module__ = "_csv"
Writer = writer


# join_append with join_append_data, and csv_writerow: the C's own functions, no names of the type
def _join_append(self: Writer, field: str | None, quoted: bool) -> None:   # join_append and join_append_data
    d: Dialect = self._dialect
    if field is not None and type(field) is not str:
        field = str.__str__(field)           # PyUnicode_DATA and PyUnicode_GET_LENGTH: the text, not a subclass's __len__ or __iter__
    length = 0 if field is None else len(field)
    if length == 0 and d._delimiter == " " and d._skipinitialspace:
        if d._quoting == QUOTE_NONE or (field is None and d._quoting in (QUOTE_STRINGS, QUOTE_NOTNULL)):
            raise Error("empty field must be quoted if delimiter is a space and skipinitialspace is true")
        quoted = True
    out: list[str] = []
    if self._num_fields > 0:
        out.append(d._delimiter)
    body: list[str] = []
    if field is not None:
        for c in field:
            want_escape = False
            if c == d._delimiter or c == d._escapechar or c == d._quotechar or c == "\n" or c == "\r" or str.find(d._lineterminator, c) >= 0:
                if d._quoting == QUOTE_NONE:
                    want_escape = True
                else:
                    if c == d._quotechar:
                        if d._doublequote:
                            body.append(d._quotechar)
                        else:
                            want_escape = True
                    elif c == d._escapechar:
                        want_escape = True
                    if not want_escape:
                        quoted = True
                if want_escape:
                    if d._escapechar is None:
                        raise Error("need to escape, but no escapechar set")
                    body.append(d._escapechar)
            body.append(c)
    if quoted:
        out.append(d._quotechar)  # type: ignore[arg-type]
    out += body
    if quoted:
        out.append(d._quotechar)  # type: ignore[arg-type]
    self._rec += out
    self._num_fields += 1


def _csv_writerow(self: Writer, seq: object) -> object:  # csv_writerow
    d: Dialect = self._dialect
    it = None                                # the C sets its error over the pending one: raised outside the handler, so that no __context__ of that one shows
    try:
        it = _tp_iter(seq)
    except TypeError:
        pass
    if it is None:
        raise Error("iterable expected, not " + _tp_name(seq))
    self._rec = []
    self._num_fields = 0
    null_field = False
    for field in it:
        if d._quoting == QUOTE_NONNUMERIC:
            quoted = not _number_check(field)
        elif d._quoting == QUOTE_ALL:
            quoted = True
        elif d._quoting == QUOTE_STRINGS:
            quoted = issubclass(type(field), str)
        elif d._quoting == QUOTE_NOTNULL:
            quoted = field is not None
        else:
            quoted = False
        null_field = field is None
        if issubclass(type(field), str):
            _join_append(self, field, quoted)
        elif null_field:
            _join_append(self, None, quoted)
        else:
            _join_append(self, str(field), quoted)
        del field                                # Py_DECREF(field) before the next tp_iternext (RL-782)
    del it                                       # Py_DECREF(iter), before the record is written
    if self._num_fields > 0 and len(self._rec) == 0:
        if d._quoting == QUOTE_NONE or (null_field and d._quoting in (QUOTE_STRINGS, QUOTE_NOTNULL)):
            raise Error("single empty field record must be quoted")
        self._num_fields -= 1
        _join_append(self, None, True)
    self._rec.append(d._lineterminator)
    line = "".join(self._rec)
    return self._write(line)


def _writer_new(*args: object, **kwds: object) -> writer:
    """Return a writer object that will write user data on the given file object.

The "fileobj" argument can be any object that supports the file API.
The optional "dialect" argument defines a CSV dialect.  The function
also accepts optional keyword arguments which override settings
provided by the dialect.
"""
    self: writer = _bella_new_instance(Writer)
    self._rec = []
    self._num_fields = 0
    _unpack("writer", args, 1, 2)
    write = getattr(args[0], "write", _ABSENT)
    if write is _ABSENT or not callable(write):
        raise TypeError('argument 1 must have a "write" method')
    self._write = write
    self._dialect = _call_dialect(args[1] if len(args) > 1 else _ABSENT, kwds)
    return self


_writer_new.__name__ = "writer"
_writer_new.__qualname__ = "writer"
writer = _writer_new  # type: ignore[assignment,misc]


# ---- the registry -----------------------------------------------------------------------------------------------------------

def list_dialects(*args: object, **kwds: object) -> list[object]:
    """Return a list of all known dialect names."""
    if kwds:
        raise TypeError("_csv.list_dialects() takes no keyword arguments")
    if args:
        raise TypeError("_csv.list_dialects() takes no arguments (" + str(len(args)) + " given)")
    return list(_dialects)


def register_dialect(*args: object, **kwds: object) -> None:
    """Create a mapping from a string name to a CVS dialect.

The optional "dialect" argument specifies the base dialect instance
or the name of the registered dialect.  The function also accepts
optional keyword arguments which override settings provided by the
dialect.
"""
    _unpack("register_dialect", args, 1, 2)
    name = args[0]
    if not issubclass(type(name), str):
        raise TypeError("dialect name must be a string")
    _dialects[name] = _call_dialect(args[1] if len(args) > 1 else _ABSENT, kwds)


def unregister_dialect(*args: object, **kwds: object) -> None:
    """Delete the name/dialect mapping associated with a string name."""
    name = _one_arg("unregister_dialect", "name", args, kwds)
    if _dialects.pop(name, _ABSENT) is _ABSENT:
        raise Error("unknown dialect")


def get_dialect(*args: object, **kwds: object) -> object:
    """Return the dialect instance associated with name."""
    return _from_registry(_one_arg("get_dialect", "name", args, kwds))


def _one_arg(fname: str, pname: str, args: tuple[object, ...], kwds: dict[str, object]) -> object:   # the clinic: one positional-or-keyword
    return _unpack_keywords(fname, (pname,), 0, 1, 1, 0, args, kwds, _ABSENT)[0]


def field_size_limit(*args: object, **kwds: object) -> int:
    """Sets an upper limit on parsed fields.

Returns old limit. If limit is not given, no new limit is set and
the old limit is returned"""
    global _field_limit
    new_limit = _unpack_keywords("field_size_limit", ("new_limit",), 0, 0, 1, 0, args, kwds, _ABSENT)[0]
    old = _field_limit
    if new_limit is not _ABSENT:
        if type(new_limit) is not int:
            raise TypeError("limit must be an integer")
        n = int.__index__(new_limit)
        if n < -(2**63) or n > 2**63 - 1:
            raise OverflowError("Python int too large to convert to C ssize_t")
        _field_limit = n
    return old
