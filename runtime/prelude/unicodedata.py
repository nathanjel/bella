"""unicodedata, in Python (Modules/unicodedata.c), over the C's algorithms and the pin's databases in C++ (runtime/src/unicodedata.cpp,
`_ucd_call`); see itertools.py beside it. What the C does with objects is here: the clinic's conversions and their messages (a
character is a str of length one, read as stored; a name is a str's UTF-8 or a bytes object's bytes), the module's functions and the
UCD type's methods, one C function each, given the module or the 3.2.0 database as self (UCD_Check is `old`), the UCD type and its one
instance, the grapheme cluster iterator and its segments (no names of the module, as in C), and the capsule.
"""
__all__ = ["UCD", "_ucnhash_CAPI", "bidirectional", "block", "category", "combining", "decimal", "decomposition", "digit", "east_asian_width",
           "extended_pictographic", "grapheme_cluster_break", "indic_conjunct_break", "is_normalized", "isxidcontinue", "isxidstart",
           "iter_graphemes", "lookup", "mirrored", "name", "normalize", "numeric", "ucd_3_2_0", "unidata_version"]
__name__ = "unicodedata"
__hidden_classes__ = ["Segment", "GraphemeBreakIterator"]   # types of the module that are no names of it

try:
    _ucd_call                                    # noqa: B018  # the C's algorithms over the databases, by name
    _number_index                                # noqa: B018  # PyNumber_Index
    _tp_name                                     # noqa: B018  # Py_TYPE(obj)->tp_name
    _bella_new_instance                          # noqa: B018  # tp_alloc
    _bella_refuse                                # noqa: B018  # a stop by name
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _ucd_call: Callable[..., Any] = _missing
    _number_index: Callable[..., int] = _missing
    _tp_name: Callable[..., str] = _missing
    _bella_new_instance: Callable[..., Any] = _missing
    _bella_refuse: Callable[..., Any] = _missing

unidata_version = _ucd_call("unidata_version")   # UNIDATA_VERSION, as the copied database says it
_NAME_MAXLEN = _ucd_call("name_maxlen")          # NAME_MAXLEN, as the copied names say it
_SSIZE_MAX = 2**63 - 1                           # PY_SSIZE_T_MAX


# ---- the calling conventions and the clinic's converters ----
def _type_name(value: object) -> str:            # _PyArg_BadArgument's "not %.50s"
    return "None" if value is None else _tp_name(value)[:50]


def _one(qualname: str, args: tuple[object, ...], kwds: dict[str, object]) -> object:   # METH_O
    if kwds:
        raise TypeError(qualname + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError(qualname + "() takes exactly one argument (" + str(len(args)) + " given)")
    return args[0]


def _fastcall(qualname: str, name: str, args: tuple[object, ...], kwds: dict[str, object], low: int, high: int) -> None:   # METH_FASTCALL
    if kwds:                                                                                                                 # with
        raise TypeError(qualname + "() takes no keyword arguments")                                                       # _PyArg_CheckPositional
    if len(args) < low:
        raise TypeError(name + " expected " + ("at least " if low < high else "") + str(low) + " argument" + ("" if low == 1 else "s") + ", got " + str(len(args)))
    if len(args) > high:
        raise TypeError(name + " expected " + ("at most " if low < high else "") + str(high) + " argument" + ("" if high == 1 else "s") + ", got " + str(len(args)))


def _character(name: str, which: str, value: object) -> int:   # int(accept={str}): PyUnicode_READ_CHAR of a str of length one
    if not issubclass(type(value), str):
        raise TypeError(name + "() " + which + " must be a unicode character, not " + _type_name(value))
    length = _ucd_call("length", value)
    if length != 1:
        raise TypeError(name + "(): " + which + " must be a unicode character, not a string of length " + str(length))
    return ord(value)  # type: ignore[arg-type]


def _unicode(name: str, which: str, value: object) -> object:   # unicode: PyUnicode_Check
    if not issubclass(type(value), str):
        raise TypeError(name + "() " + which + " must be str, not " + _type_name(value))
    return value


def _ssize(value: object) -> int:                # Py_ssize_t's converter
    out = _number_index(value)
    if not -(2**63) <= out < 2**63:
        raise OverflowError("Python int too large to convert to C ssize_t")
    return out


def _name_bytes(value: object) -> object:        # PyArg_Parse's "s#": a str's UTF-8, or a buffer that need not be released (bytes)
    if issubclass(type(value), str):
        return str.encode(value, "utf-8")  # type: ignore[arg-type]
    if issubclass(type(value), bytes):
        return value
    if issubclass(type(value), (bytearray, memoryview)):
        raise TypeError("lookup() argument must be read-only bytes-like object, not " + _type_name(value))
    if hasattr(type(value), "__buffer__"):
        _bella_refuse("[P2+] the buffer protocol (__buffer__)")
    raise TypeError("a bytes-like object is required, not '" + _tp_name(value) + "'")


# ---- the C's functions: each one serves the module (old is False) and the UCD type (old is True) ----
def _decimal(qualname: str, old: bool, args: tuple[object, ...], kwds: dict[str, object]) -> object:
    _fastcall(qualname, "decimal", args, kwds, 1, 2)
    rc = _ucd_call("decimal", _character("decimal", "argument 1", args[0]), old)
    if rc < 0:
        if len(args) < 2:
            raise ValueError("not a decimal")
        return args[1]
    return rc


def _digit(qualname: str, old: bool, args: tuple[object, ...], kwds: dict[str, object]) -> object:
    _fastcall(qualname, "digit", args, kwds, 1, 2)
    rc = _ucd_call("digit", _character("digit", "argument 1", args[0]))
    if rc < 0:
        if len(args) < 2:
            raise ValueError("not a digit")
        return args[1]
    return rc


def _numeric(qualname: str, old: bool, args: tuple[object, ...], kwds: dict[str, object]) -> object:
    _fastcall(qualname, "numeric", args, kwds, 1, 2)
    rc = _ucd_call("numeric", _character("numeric", "argument 1", args[0]), old)
    if rc == -1.0:
        if len(args) < 2:
            raise ValueError("not a numeric character")
        return args[1]
    return rc


def _property(prop: str, qualname: str, old: bool, args: tuple[object, ...], kwds: dict[str, object]) -> object:   # METH_O on a character
    return _ucd_call(prop, _character(prop, "argument", _one(qualname, args, kwds)), old)


def _is_normalized(qualname: str, old: bool, args: tuple[object, ...], kwds: dict[str, object]) -> object:
    _fastcall(qualname, "is_normalized", args, kwds, 2, 2)
    form = _unicode("is_normalized", "argument 1", args[0])
    return _ucd_call("is_normalized", old, form, _unicode("is_normalized", "argument 2", args[1]))


def _normalize(qualname: str, old: bool, args: tuple[object, ...], kwds: dict[str, object]) -> object:
    _fastcall(qualname, "normalize", args, kwds, 2, 2)
    form = _unicode("normalize", "argument 1", args[0])
    return _ucd_call("normalize", old, form, _unicode("normalize", "argument 2", args[1]))


def _name(qualname: str, old: bool, args: tuple[object, ...], kwds: dict[str, object]) -> object:
    _fastcall(qualname, "name", args, kwds, 1, 2)
    result = _ucd_call("name", _character("name", "argument 1", args[0]), old)
    if result is None:
        if len(args) < 2:
            raise ValueError("no such name")
        return args[1]
    return result


def _lookup(qualname: str, old: bool, args: tuple[object, ...], kwds: dict[str, object]) -> object:
    name = _name_bytes(_one(qualname, args, kwds))
    if bytes.__len__(name) > _NAME_MAXLEN:  # type: ignore[arg-type]
        raise KeyError("name too long")
    result = _ucd_call("lookup", name, old)
    if result is None:                           # "%s": the name up to its first NUL, decoded as UTF-8 with replacements
        shown = bytes.decode(bytes.partition(name, b"\x00")[0], "utf-8", "replace")  # type: ignore[arg-type]
        raise KeyError("undefined character name '" + shown + "'")
    return result


# ---- the module's functions ----
def decimal(*args: object, **kwds: object) -> object:
    """Converts a Unicode character into its equivalent decimal value.

Returns the decimal value assigned to the character chr as integer.
If no such value is defined, default is returned, or, if not given,
ValueError is raised."""
    return _decimal("unicodedata.decimal", False, args, kwds)


def digit(*args: object, **kwds: object) -> object:
    """Converts a Unicode character into its equivalent digit value.

Returns the digit value assigned to the character chr as integer.
If no such value is defined, default is returned, or, if not given,
ValueError is raised."""
    return _digit("unicodedata.digit", False, args, kwds)


def numeric(*args: object, **kwds: object) -> object:
    """Converts a Unicode character into its equivalent numeric value.

Returns the numeric value assigned to the character chr as float.
If no such value is defined, default is returned, or, if not given,
ValueError is raised."""
    return _numeric("unicodedata.numeric", False, args, kwds)


def category(*args: object, **kwds: object) -> object:
    """Returns the general category assigned to the character chr as string."""
    return _property("category", "unicodedata.category", False, args, kwds)


def bidirectional(*args: object, **kwds: object) -> object:
    """Returns the bidirectional class assigned to the character chr as string.

If no such value is defined, an empty string is returned."""
    return _property("bidirectional", "unicodedata.bidirectional", False, args, kwds)


def combining(*args: object, **kwds: object) -> object:
    """Returns the canonical combining class assigned to the character chr as integer.

Returns 0 if no combining class is defined."""
    return _property("combining", "unicodedata.combining", False, args, kwds)


def mirrored(*args: object, **kwds: object) -> object:
    """Returns the mirrored property assigned to the character chr as integer.

Returns 1 if the character has been identified as a "mirrored"
character in bidirectional text, 0 otherwise."""
    return _property("mirrored", "unicodedata.mirrored", False, args, kwds)


def east_asian_width(*args: object, **kwds: object) -> object:
    """Returns the east asian width assigned to the character chr as string."""
    return _property("east_asian_width", "unicodedata.east_asian_width", False, args, kwds)


def decomposition(*args: object, **kwds: object) -> object:
    """Returns the character decomposition mapping assigned to the character chr as string.

An empty string is returned in case no such mapping is defined."""
    return _property("decomposition", "unicodedata.decomposition", False, args, kwds)


def name(*args: object, **kwds: object) -> object:
    """Returns the name assigned to the character chr as a string.

If no name is defined, default is returned, or, if not given,
ValueError is raised."""
    return _name("unicodedata.name", False, args, kwds)


def lookup(*args: object, **kwds: object) -> object:
    """Look up character by name.

If a character with the given name is found, return the
corresponding character.  If not found, KeyError is raised."""
    return _lookup("unicodedata.lookup", False, args, kwds)


def is_normalized(*args: object, **kwds: object) -> object:
    """Return whether the Unicode string unistr is in the normal form 'form'.

Valid values for form are 'NFC', 'NFKC', 'NFD', and 'NFKD'."""
    return _is_normalized("unicodedata.is_normalized", False, args, kwds)


def normalize(*args: object, **kwds: object) -> object:
    """Return the normal form 'form' for the Unicode string unistr.

Valid values for form are 'NFC', 'NFKC', 'NFD', and 'NFKD'."""
    return _normalize("unicodedata.normalize", False, args, kwds)


# the module's own: no UCD method has them
def block(*args: object, **kwds: object) -> object:
    """Return block assigned to the character chr."""
    return _ucd_call("block", _character("block", "argument", _one("unicodedata.block", args, kwds)))


def grapheme_cluster_break(*args: object, **kwds: object) -> object:
    """Returns the Grapheme_Cluster_Break property assigned to the character."""
    return _ucd_call("grapheme_cluster_break", _character("grapheme_cluster_break", "argument", _one("unicodedata.grapheme_cluster_break", args, kwds)))


def indic_conjunct_break(*args: object, **kwds: object) -> object:
    """Returns the Indic_Conjunct_Break property assigned to the character."""
    return _ucd_call("indic_conjunct_break", _character("indic_conjunct_break", "argument", _one("unicodedata.indic_conjunct_break", args, kwds)))


def extended_pictographic(*args: object, **kwds: object) -> object:
    """Returns the Extended_Pictographic property assigned to the character, as boolean."""
    return _ucd_call("extended_pictographic", _character("extended_pictographic", "argument", _one("unicodedata.extended_pictographic", args, kwds)))


def isxidstart(*args: object, **kwds: object) -> object:
    """Return True if the character has the XID_Start property, else False."""
    return _ucd_call("isxidstart", _character("isxidstart", "argument", _one("unicodedata.isxidstart", args, kwds)))


def isxidcontinue(*args: object, **kwds: object) -> object:
    """Return True if the character has the XID_Continue property, else False."""
    return _ucd_call("isxidcontinue", _character("isxidcontinue", "argument", _one("unicodedata.isxidcontinue", args, kwds)))


def iter_graphemes(*args: object, **kwds: object) -> object:
    """Returns an iterator to iterate over grapheme clusters.

It uses extended grapheme cluster rules from TR29."""
    _fastcall("unicodedata.iter_graphemes", "iter_graphemes", args, kwds, 1, 3)
    unistr = _unicode("iter_graphemes", "argument 1", args[0])
    start = _ssize(args[1]) if len(args) > 1 else 0
    end = _ssize(args[2]) if len(args) > 2 else _SSIZE_MAX
    length = _ucd_call("length", unistr)
    if end > length:                             # ADJUST_INDICES
        end = length
    elif end < 0:
        end += length
        end = max(end, 0)
    if start < 0:
        start += length
        start = max(start, 0)
    it = _bella_new_instance(GraphemeBreakIterator)
    it._a_string = unistr                        # _Py_InitGraphemeBreak
    it._b_state = (start, start, end, 0, 0, 0, 0)   # start, pos, end, gcb, ep_state, incb_state, ri_flag
    return it


# ---- the types ----
class UCD:
    __slots__ = ("_a_name",)

    @property
    def unidata_version(self) -> str:            # a read-only member
        return self._a_name

    def decimal(*args: object, **kwds: object) -> object:  # noqa: N805
        """Converts a Unicode character into its equivalent decimal value.

Returns the decimal value assigned to the character chr as integer.
If no such value is defined, default is returned, or, if not given,
ValueError is raised."""
        return _decimal("UCD.decimal", True, args[1:], kwds)

    def digit(*args: object, **kwds: object) -> object:  # noqa: N805
        """Converts a Unicode character into its equivalent digit value.

Returns the digit value assigned to the character chr as integer.
If no such value is defined, default is returned, or, if not given,
ValueError is raised."""
        return _digit("UCD.digit", True, args[1:], kwds)

    def numeric(*args: object, **kwds: object) -> object:  # noqa: N805
        """Converts a Unicode character into its equivalent numeric value.

Returns the numeric value assigned to the character chr as float.
If no such value is defined, default is returned, or, if not given,
ValueError is raised."""
        return _numeric("UCD.numeric", True, args[1:], kwds)

    def category(*args: object, **kwds: object) -> object:  # noqa: N805
        """Returns the general category assigned to the character chr as string."""
        return _property("category", "UCD.category", True, args[1:], kwds)

    def bidirectional(*args: object, **kwds: object) -> object:  # noqa: N805
        """Returns the bidirectional class assigned to the character chr as string.

If no such value is defined, an empty string is returned."""
        return _property("bidirectional", "UCD.bidirectional", True, args[1:], kwds)

    def combining(*args: object, **kwds: object) -> object:  # noqa: N805
        """Returns the canonical combining class assigned to the character chr as integer.

Returns 0 if no combining class is defined."""
        return _property("combining", "UCD.combining", True, args[1:], kwds)

    def mirrored(*args: object, **kwds: object) -> object:  # noqa: N805
        """Returns the mirrored property assigned to the character chr as integer.

Returns 1 if the character has been identified as a "mirrored"
character in bidirectional text, 0 otherwise."""
        return _property("mirrored", "UCD.mirrored", True, args[1:], kwds)

    def east_asian_width(*args: object, **kwds: object) -> object:  # noqa: N805
        """Returns the east asian width assigned to the character chr as string."""
        return _property("east_asian_width", "UCD.east_asian_width", True, args[1:], kwds)

    def decomposition(*args: object, **kwds: object) -> object:  # noqa: N805
        """Returns the character decomposition mapping assigned to the character chr as string.

An empty string is returned in case no such mapping is defined."""
        return _property("decomposition", "UCD.decomposition", True, args[1:], kwds)

    def name(*args: object, **kwds: object) -> object:  # noqa: N805
        """Returns the name assigned to the character chr as a string.

If no name is defined, default is returned, or, if not given,
ValueError is raised."""
        return _name("UCD.name", True, args[1:], kwds)

    def lookup(*args: object, **kwds: object) -> object:  # noqa: N805
        """Look up character by name.

If a character with the given name is found, return the
corresponding character.  If not found, KeyError is raised."""
        return _lookup("UCD.lookup", True, args[1:], kwds)

    def is_normalized(*args: object, **kwds: object) -> object:  # noqa: N805
        """Return whether the Unicode string unistr is in the normal form 'form'.

Valid values for form are 'NFC', 'NFKC', 'NFD', and 'NFKD'."""
        return _is_normalized("UCD.is_normalized", True, args[1:], kwds)

    def normalize(*args: object, **kwds: object) -> object:  # noqa: N805
        """Return the normal form 'form' for the Unicode string unistr.

Valid values for form are 'NFC', 'NFKC', 'NFD', and 'NFKD'."""
        return _normalize("UCD.normalize", True, args[1:], kwds)


class Segment:
    __slots__ = ("_a_string", "_b_start", "_c_end")

    @property
    def start(self) -> int:                      # a read-only member
        return self._b_start

    @property
    def end(self) -> int:
        return self._c_end

    def __str__(self) -> str:                    # Segment_str: PyUnicode_Substring
        return _ucd_call("substring", self._a_string, self._b_start, self._c_end)  # type: ignore[no-any-return]

    def __repr__(self) -> str:
        return "<Segment " + str(self._b_start) + ":" + str(self._c_end) + ">"


class GraphemeBreakIterator:
    __slots__ = ("_a_string", "_b_state")

    def __iter__(self) -> GraphemeBreakIterator:   # PyObject_SelfIter
        return self

    def __next__(self) -> Segment:               # GBI_iternext
        start = self._b_state[0]
        pos, self._b_state = _ucd_call("next_break", self._a_string, self._b_state)
        if pos < 0:
            raise StopIteration
        s = _bella_new_instance(Segment)
        s._a_string = self._a_string
        s._b_start = start
        s._c_end = pos
        return s  # type: ignore[no-any-return]


ucd_3_2_0 = _bella_new_instance(UCD)             # new_previous_version: Unicode database version 3.2.0 used by the IDNA encoding
ucd_3_2_0._a_name = "3.2.0"
_ucnhash_CAPI = _ucd_call("capsule")
