"""_sre, in Python over the engine in runtime/src/sre.cpp, from Modules/_sre/sre.c; see itertools.py beside it.

The engine (`_sre_call("run", ...)`) reads a pattern's code and a string's data and gives the marks; what the C does with objects is here,
in its words. Pattern, Match, SRE_Scanner and SRE_Template are no names of the module, as in C, and cannot be made from Python
(Py_TPFLAGS_DISALLOW_INSTANTIATION): the runtime presents them (`_present`), so a property here is a member or a getset as the names table says.
"""

__all__ = ["CODESIZE", "MAGIC", "MAXGROUPS", "MAXREPEAT", "ascii_iscased", "ascii_tolower", "compile", "copyright", "getcodesize", "template",
           "unicode_iscased", "unicode_tolower"]

__name__ = "_sre"

try:
    _number_index                                # noqa: B018  # PyNumber_Index
    _tp_name                                     # noqa: B018  # Py_TYPE(obj)->tp_name
    _keyword_suggestion                          # noqa: B018  # _Py_CalculateSuggestions
    _bella_new_instance                          # noqa: B018  # tp_alloc
    _sre_call                                    # noqa: B018  # the engine, by name
    _present                                     # noqa: B018  # a class the module has in C, with what it cannot do
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _number_index: Callable[..., int] = _missing
    _tp_name: Callable[..., str] = _missing
    _keyword_suggestion: Callable[..., str | None] = _missing
    _bella_new_instance: Callable[..., Any] = _missing
    _sre_call: Callable[..., Any] = _missing
    _present: Callable[..., None] = _missing

CODESIZE = 4
MAGIC = 20230612
MAXGROUPS = 1073741823
MAXREPEAT = 4294967295
copyright = " SRE 2.2.2 Copyright (c) 1997-2002 by Secret Labs AB "  # noqa: A001

_ABSENT = object()
_SSIZE_MAX = 2**63 - 1
_compile_template_func: list[object] = []


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


def _ssize(value: object) -> int:                # Py_ssize_t's converter
    out = _number_index(value)
    if not -(2**63) <= out < 2**63:
        raise OverflowError("Python int too large to convert to C ssize_t")
    return out


def _int(value: object) -> int:                  # PyLong_AsInt
    out = _number_index(value)
    if not -2147483648 <= out <= 2147483647:
        raise OverflowError("Python int too large to convert to C int")
    return out


def _one_int(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> int:   # METH_O with an int
    if kwds:
        raise TypeError("_sre." + name + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("_sre." + name + "() takes exactly one argument (" + str(len(args)) + " given)")
    return _int(args[0])


def getcodesize(*args: object, **kwds: object) -> int:
    if kwds:
        raise TypeError("_sre.getcodesize() takes no keyword arguments")
    if args:
        raise TypeError("_sre.getcodesize() takes no arguments (" + str(len(args)) + " given)")
    return CODESIZE


def ascii_iscased(*args: object, **kwds: object) -> bool:
    ch = _one_int("ascii_iscased", args, kwds)
    return 0 <= ch < 128 and (65 <= ch <= 90 or 97 <= ch <= 122)


def unicode_iscased(*args: object, **kwds: object) -> bool:
    ch = _one_int("unicode_iscased", args, kwds)
    return ch >= 0 and (ch != _sre_call("lower", ch) or ch != _sre_call("upper", ch))


def ascii_tolower(*args: object, **kwds: object) -> int:
    ch = _one_int("ascii_tolower", args, kwds)
    return ch + 32 if 65 <= ch <= 90 else ch


def unicode_tolower(*args: object, **kwds: object) -> int:
    ch = _one_int("unicode_tolower", args, kwds)
    return ch if ch < 0 else _sre_call("lower", ch)   # past the database, unchanged, and an int again


def compile(*args: object, **kwds: object) -> object:  # noqa: A001  # _sre_compile_impl
    pattern, flags, code, groups, groupindex, indexgroup = _unpack("compile", args, kwds, ("pattern", "flags", "code", "groups", "groupindex", "indexgroup"), 6, 6)
    flag_bits = _int(flags)
    if not issubclass(type(code), list):
        raise TypeError("compile() argument 'code' must be list, not " + type(code).__name__)
    group_count = _ssize(groups)
    if not issubclass(type(groupindex), dict):
        raise TypeError("compile() argument 'groupindex' must be dict, not " + type(groupindex).__name__)
    if not issubclass(type(indexgroup), tuple):
        raise TypeError("compile() argument 'indexgroup' must be tuple, not " + type(indexgroup).__name__)
    words = _sre_call("code", code)
    isbytes = -1
    if pattern is not None:
        isbytes = 1 if _sre_call("getstring", pattern)[1] else 0
    self = _bella_new_instance(Pattern)
    self._a_pattern = pattern
    self._b_flags = flag_bits
    self._c_groups = group_count
    self._d_groupindex = groupindex if dict.__len__(groupindex) > 0 else None  # type: ignore[arg-type]
    self._e_indexgroup = indexgroup if self._d_groupindex is not None and tuple.__len__(indexgroup) > 0 else None  # type: ignore[arg-type]
    self._f_code = words
    self._g_isbytes = isbytes
    _sre_call("validate", words, group_count)
    return self


def template(*args: object, **kwds: object) -> object:  # _sre_template_impl
    if kwds:
        raise TypeError("_sre.template() takes no keyword arguments")
    if len(args) != 2:
        raise TypeError("template expected 2 arguments, got " + str(len(args)))
    chunks = args[1]
    if not issubclass(type(chunks), list):
        raise TypeError("template() argument 2 must be list, not " + type(chunks).__name__)
    n = list.__len__(chunks)  # type: ignore[arg-type]
    if n & 1 == 0 or n < 1:
        raise TypeError("invalid template")
    self = _bella_new_instance(SRE_Template)
    self._a_literal = list.__getitem__(chunks, 0)  # type: ignore[arg-type]
    items = []
    i = 1
    while i < n:
        given = list.__getitem__(chunks, i)  # type: ignore[arg-type]
        if not issubclass(type(given), int):     # PyLong_AsSsize_t
            raise TypeError("an integer is required")
        index = _ssize(given)
        if index < 0:
            raise TypeError("invalid template")
        literal = list.__getitem__(chunks, i + 1)  # type: ignore[arg-type]
        if (issubclass(type(literal), str) and str.__len__(literal) == 0) or (issubclass(type(literal), bytes) and bytes.__len__(literal) == 0):
            literal = _ABSENT                    # Skip empty literals
        items.append((index, literal))
        i += 2
    self._b_items = items
    return self


def _state(self: object, string: object, pos: int, endpos: int) -> tuple[int, int, int]:   # state_init: the length, and the boundaries adjusted
    length, isbytes = _sre_call("getstring", string)
    if isbytes and self._g_isbytes == 0:  # type: ignore[attr-defined]
        raise TypeError("cannot use a string pattern on a bytes-like object")
    if not isbytes and self._g_isbytes > 0:  # type: ignore[attr-defined]
        raise TypeError("cannot use a bytes pattern on a string-like object")
    if pos < 0:
        pos = 0
    elif pos > length:
        pos = length
    if endpos < 0:
        endpos = 0
    elif endpos > length:
        endpos = length
    return length, pos, endpos


def _run(self: object, string: object, pos: int, endpos: int, start: int, must_advance: bool, mode: int) -> object:
    return _sre_call("run", self._f_code, self._c_groups, string, pos, endpos, start, must_advance, mode)  # type: ignore[attr-defined]


def _new_match(pattern: object, string: object, pos: int, endpos: int, marks: tuple[int, ...]) -> object:   # pattern_new_match
    match = _bella_new_instance(Match)
    match._a_string = string
    match._b_regs = None
    match._c_pattern = pattern
    match._d_pos = pos
    match._e_endpos = endpos
    match._f_lastindex = marks[2]
    match._g_groups = pattern._c_groups + 1  # type: ignore[attr-defined]
    match._h_mark = (marks[0], marks[1], *marks[3:])
    return match


def _span_of(string: object, marks: tuple[int, ...], index: int, empty: bool) -> object:   # state_getslice
    i = marks[3 + (index - 1) * 2]
    j = marks[4 + (index - 1) * 2]
    if i < 0 or j < 0:
        if not empty:
            return None
        i = j = 0
    return _sre_call("slice", string, i, j)


def _pos_args(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> tuple[object, int, int]:
    string, pos, endpos = _unpack(name, args, kwds, ("string", "pos", "endpos"), 1, 3)
    return string, 0 if pos is _ABSENT else _ssize(pos), _SSIZE_MAX if endpos is _ABSENT else _ssize(endpos)


def _matched(self: object, name: str, mode: int, args: tuple[object, ...], kwds: dict[str, object]) -> object:
    string, pos, endpos = _pos_args(name, args, kwds)
    _length, pos, endpos = _state(self, string, pos, endpos)
    marks = _run(self, string, pos, endpos, pos, False, mode)
    return None if marks is None else _new_match(self, string, pos, endpos, marks)  # type: ignore[arg-type]


def _compile_template(pattern: object, repl: object) -> object:   # compile_template
    if not _compile_template_func:
        import re  # noqa: PLC0415
        _compile_template_func.append(re._compile_template)  # type: ignore[attr-defined]
    func = _compile_template_func[0]
    try:
        result = func(pattern, repl)  # type: ignore[operator]
    except TypeError:                            # the replacement string is unhashable: the basic type, and again
        if issubclass(type(repl), str) and type(repl) is not str:
            repl = str.__str__(repl)  # type: ignore[arg-type]
        elif issubclass(type(repl), (bytes, bytearray)) and type(repl) is not bytes:
            repl = bytes(repl)  # type: ignore[call-overload]
        else:
            raise
        result = func(pattern, repl)  # type: ignore[operator]
    if type(result) is not SRE_Template:
        raise RuntimeError("the result of compiling a replacement string is " + _tp_name(result))
    return result


def _expand(template_object: object, match: object) -> object:   # expand_template
    items = template_object._b_items  # type: ignore[attr-defined]
    literal = template_object._a_literal  # type: ignore[attr-defined]
    if not items:
        return literal
    out = [literal]
    for index, after in items:
        if index >= match._g_groups:  # type: ignore[attr-defined]
            raise IndexError("no such group")
        item = _getslice_by_index(match, index, None)
        if item is not None:
            out.append(item)
        if after is not _ABSENT:
            out.append(after)
    return str.join("", out) if issubclass(type(literal), str) else bytes.join(b"", out)


def _subx(self: object, name: str, repl: object, string: object, count: int, subn: bool) -> object:   # pattern_subx
    literal = False
    is_callable = callable(repl)
    if not is_callable:
        has = _sre_call("has_backslash", repl)
        literal = has is False
    filter_object = repl
    if is_callable:
        kind = 2
    elif literal:
        kind = 0
    else:
        filter_object = _compile_template(self, repl)
        if not filter_object._b_items:  # type: ignore[attr-defined]
            filter_object = filter_object._a_literal  # type: ignore[attr-defined]
            kind = 0
        else:
            kind = 1
    length, _pos, endpos = _state(self, string, 0, _SSIZE_MAX)
    out: list[object] = []
    n = i = 0
    start = 0
    must_advance = False
    _sre_call("export", string, 1)               # state_init holds the buffer until state_fini: a callback cannot resize what is being scanned
    try:
        while not count or n < count:
            marks = _run(self, string, 0, endpos, start, must_advance, 2)
            if marks is None:
                break
            b = marks[0]  # type: ignore[index]
            e = marks[1]  # type: ignore[index]
            if i < b:
                out.append(_sre_call("slice", string, i, b))
            if kind != 0:
                match = _new_match(self, string, 0, endpos, marks)  # type: ignore[arg-type]
                item = _expand(filter_object, match) if kind == 1 else filter_object(match)  # type: ignore[operator]
            else:
                item = filter_object
            if item is not None:
                out.append(item)
            i = e
            n += 1
            must_advance = e == b
            start = e
        if i < endpos:
            out.append(_sre_call("slice", string, i, endpos))
    finally:
        _sre_call("export", string, -1)
    joiner = _sre_call("slice", string, 0, 0)
    if not out:
        item = joiner
    elif issubclass(type(joiner), bytes):
        item = bytes.join(joiner, out)
    else:
        item = str.join(joiner, out)
    return (item, n) if subn else item


class Pattern:
    __module__ = "re"
    __slots__ = ("_a_pattern", "_b_flags", "_c_groups", "_d_groupindex", "_e_indexgroup", "_f_code", "_g_isbytes", "__weakref__")

    @property
    def pattern(self) -> object:
        return self._a_pattern

    @property
    def flags(self) -> int:
        return self._b_flags

    @property
    def groups(self) -> int:
        return self._c_groups

    @property
    def groupindex(self) -> object:              # pattern_groupindex
        import types  # noqa: PLC0415
        return types.MappingProxyType({} if self._d_groupindex is None else self._d_groupindex)

    def prefixmatch(*args: object, **kwds: object) -> object:  # noqa: N805
        return _matched(args[0], "prefixmatch", 0, args[1:], kwds)

    match = prefixmatch                          # one C function under two names, so bound they compare equal

    def fullmatch(*args: object, **kwds: object) -> object:  # noqa: N805
        return _matched(args[0], "fullmatch", 1, args[1:], kwds)

    def search(*args: object, **kwds: object) -> object:  # noqa: N805
        return _matched(args[0], "search", 2, args[1:], kwds)

    def findall(*args: object, **kwds: object) -> list[object]:  # noqa: N805  # _sre_SRE_Pattern_findall_impl
        self = args[0]
        string, pos, endpos = _pos_args("findall", args[1:], kwds)
        _length, pos, endpos = _state(self, string, pos, endpos)
        out: list[object] = []
        groups = self._c_groups  # type: ignore[attr-defined]
        start = pos
        must_advance = False
        while start <= endpos:
            marks = _run(self, string, pos, endpos, start, must_advance, 2)
            if marks is None:
                break
            if groups == 0:
                out.append(_sre_call("slice", string, marks[0], marks[1]))  # type: ignore[index]
            elif groups == 1:
                out.append(_span_of(string, marks, 1, True))  # type: ignore[arg-type]
            else:
                out.append(tuple([_span_of(string, marks, i + 1, True) for i in range(groups)]))  # type: ignore[arg-type]
            must_advance = marks[1] == marks[0]  # type: ignore[index]
            start = marks[1]  # type: ignore[index]
        return out

    def finditer(*args: object, **kwds: object) -> object:  # noqa: N805
        string, pos, endpos = _pos_args("finditer", args[1:], kwds)
        return iter(_new_scanner(args[0], string, pos, endpos).search, None)

    def scanner(*args: object, **kwds: object) -> object:  # noqa: N805
        string, pos, endpos = _pos_args("scanner", args[1:], kwds)
        return _new_scanner(args[0], string, pos, endpos)

    def split(*args: object, **kwds: object) -> list[object]:  # noqa: N805  # _sre_SRE_Pattern_split_impl
        self = args[0]
        string, maxsplit = _unpack("split", args[1:], kwds, ("string", "maxsplit"), 1, 2)
        limit = 0 if maxsplit is _ABSENT else _ssize(maxsplit)
        _length, _pos, endpos = _state(self, string, 0, _SSIZE_MAX)
        out: list[object] = []
        groups = self._c_groups  # type: ignore[attr-defined]
        n = 0
        last = 0
        start = 0
        must_advance = False
        while not limit or n < limit:
            marks = _run(self, string, 0, endpos, start, must_advance, 2)
            if marks is None:
                break
            out.append(_sre_call("slice", string, last, marks[0]))  # type: ignore[index]
            for i in range(groups):
                out.append(_span_of(string, marks, i + 1, False))  # type: ignore[arg-type]
            n += 1
            must_advance = marks[1] == marks[0]  # type: ignore[index]
            last = start = marks[1]  # type: ignore[index]
        out.append(_sre_call("slice", string, last, endpos))
        return out

    def sub(*args: object, **kwds: object) -> object:  # noqa: N805
        repl, string, count = _unpack("sub", args[1:], kwds, ("repl", "string", "count"), 2, 3)
        return _subx(args[0], "sub", repl, string, 0 if count is _ABSENT else _ssize(count), False)

    def subn(*args: object, **kwds: object) -> object:  # noqa: N805
        repl, string, count = _unpack("subn", args[1:], kwds, ("repl", "string", "count"), 2, 3)
        return _subx(args[0], "subn", repl, string, 0 if count is _ABSENT else _ssize(count), True)

    def __copy__(*args: object, **kwds: object) -> object:  # noqa: N805
        if kwds:
            raise TypeError("Pattern.__copy__() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("Pattern.__copy__() takes no arguments (" + str(len(args) - 1) + " given)")
        return args[0]

    def __deepcopy__(*args: object, **kwds: object) -> object:  # noqa: N805
        if kwds:
            raise TypeError("Pattern.__deepcopy__() takes no keyword arguments")
        if len(args) != 2:
            raise TypeError("Pattern.__deepcopy__() takes exactly one argument (" + str(len(args) - 1) + " given)")
        return args[0]

    def __repr__(self) -> str:                   # pattern_repr
        flags = self._b_flags
        if self._g_isbytes == 0 and flags & (4 | 32 | 256) == 32:
            flags &= ~32                         # Omit re.UNICODE for valid string patterns
        names = []
        for name, value in (("re.IGNORECASE", 2), ("re.LOCALE", 4), ("re.MULTILINE", 8), ("re.DOTALL", 16), ("re.UNICODE", 32), ("re.VERBOSE", 64), ("re.DEBUG", 128), ("re.ASCII", 256)):
            if flags & value:
                names.append(name)
                flags &= ~value
        if flags:
            names.append(hex(flags & 0xFFFFFFFF))
        shown = repr(self._a_pattern)[:200]
        return "re.compile(" + shown + ", " + "|".join(names) + ")" if names else "re.compile(" + shown + ")"

    def __hash__(self) -> int:                   # pattern_hash
        h = hash(self._a_pattern) ^ hash(self._f_code) ^ self._b_flags ^ self._g_isbytes ^ (len(self._f_code) // CODESIZE)
        return -2 if h == -1 else h

    def __eq__(self, other: object) -> object:   # pattern_richcompare
        if type(other) is not Pattern:
            return NotImplemented
        if self is other:
            return True
        return (self._b_flags == other._b_flags and self._g_isbytes == other._g_isbytes and self._f_code == other._f_code
                and bool(self._a_pattern == other._a_pattern))

    def __ne__(self, other: object) -> object:
        if type(other) is not Pattern:
            return NotImplemented
        return not Pattern.__eq__(self, other)

    def __lt__(self, other: object) -> object:
        return NotImplemented

    def __le__(self, other: object) -> object:
        return NotImplemented

    def __gt__(self, other: object) -> object:
        return NotImplemented

    def __ge__(self, other: object) -> object:
        return NotImplemented


def _getindex(self: object, index: object) -> int:   # match_getindex
    if index is _ABSENT:
        return 0
    i = -1
    if hasattr(type(index), "__index__"):
        i = _clamped_index(index)
    else:
        groupindex = self._c_pattern._d_groupindex  # type: ignore[attr-defined]
        if groupindex is not None:
            found = dict.get(groupindex, index, _ABSENT)
            if found is not _ABSENT and issubclass(type(found), int):
                i = found
    if i < 0 or i >= self._g_groups:  # type: ignore[attr-defined]
        raise IndexError("no such group")
    return i


def _clamped_index(value: object) -> int:        # PyNumber_AsSsize_t(index, NULL)
    out = _number_index(value)
    return min(max(out, -(2**63)), 2**63 - 1)


def _getslice_by_index(self: object, index: int, default: object) -> object:   # match_getslice_by_index
    marks = self._h_mark  # type: ignore[attr-defined]
    string = self._a_string  # type: ignore[attr-defined]
    if string is None or marks[index * 2] < 0:
        return default
    length = _sre_call("getstring", string)[0]
    return _sre_call("slice", string, min(marks[index * 2], length), min(marks[index * 2 + 1], length))


class Match:
    __module__ = "re"
    __slots__ = ("_a_string", "_b_regs", "_c_pattern", "_d_pos", "_e_endpos", "_f_lastindex", "_g_groups", "_h_mark")

    @property
    def string(self) -> object:
        return self._a_string

    @property
    def re(self) -> object:
        return self._c_pattern

    @property
    def pos(self) -> int:
        return self._d_pos

    @property
    def endpos(self) -> int:
        return self._e_endpos

    @property
    def lastindex(self) -> object:
        return self._f_lastindex if self._f_lastindex >= 0 else None

    @property
    def lastgroup(self) -> object:
        names = self._c_pattern._e_indexgroup
        if names is not None and 0 <= self._f_lastindex < tuple.__len__(names):
            return tuple.__getitem__(names, self._f_lastindex)
        return None

    @property
    def regs(self) -> object:                    # match_regs, cached
        if self._b_regs is None:
            marks = self._h_mark
            self._b_regs = tuple([(marks[i * 2], marks[i * 2 + 1]) for i in range(self._g_groups)])
        return self._b_regs

    def group(*args: object, **kwds: object) -> object:  # noqa: N805
        self = args[0]
        if kwds:
            raise TypeError("Match.group() takes no keyword arguments")
        wanted = args[1:]
        if len(wanted) == 0:
            return _getslice_by_index(self, 0, None)
        if len(wanted) == 1:
            return _getslice_by_index(self, _getindex(self, wanted[0]), None)
        return tuple([_getslice_by_index(self, _getindex(self, w), None) for w in wanted])

    def __getitem__(self, name: object) -> object:
        return _getslice_by_index(self, _getindex(self, name), None)

    def groups(*args: object, **kwds: object) -> tuple[object, ...]:  # noqa: N805
        self = args[0]
        default = _unpack("groups", args[1:], kwds, ("default",), 0, 1)[0]
        value = None if default is _ABSENT else default
        return tuple([_getslice_by_index(self, i, value) for i in range(1, self._g_groups)])  # type: ignore[attr-defined]

    def groupdict(*args: object, **kwds: object) -> dict[object, object]:  # noqa: N805
        self = args[0]
        default = _unpack("groupdict", args[1:], kwds, ("default",), 0, 1)[0]
        value = None if default is _ABSENT else default
        out: dict[object, object] = {}
        groupindex = self._c_pattern._d_groupindex  # type: ignore[attr-defined]
        if groupindex is None:
            return out
        for key in dict.__iter__(groupindex):
            out[key] = _getslice_by_index(self, _getindex(self, key), value)
        return out

    def start(*args: object, **kwds: object) -> int:  # noqa: N805
        return args[0]._h_mark[_group_arg("start", args[1:], kwds, args[0]) * 2]  # type: ignore[attr-defined]

    def end(*args: object, **kwds: object) -> int:  # noqa: N805
        return args[0]._h_mark[_group_arg("end", args[1:], kwds, args[0]) * 2 + 1]  # type: ignore[attr-defined]

    def span(*args: object, **kwds: object) -> tuple[int, int]:  # noqa: N805
        index = _group_arg("span", args[1:], kwds, args[0])
        marks = args[0]._h_mark  # type: ignore[attr-defined]
        return (marks[index * 2], marks[index * 2 + 1])

    def expand(*args: object, **kwds: object) -> object:  # noqa: N805
        template_text = _unpack("expand", args[1:], kwds, ("template",), 1, 1)[0]
        return _expand(_compile_template(args[0]._c_pattern, template_text), args[0])  # type: ignore[attr-defined]

    def __copy__(*args: object, **kwds: object) -> object:  # noqa: N805
        if kwds:
            raise TypeError("Match.__copy__() takes no keyword arguments")
        if len(args) != 1:
            raise TypeError("Match.__copy__() takes no arguments (" + str(len(args) - 1) + " given)")
        return args[0]

    def __deepcopy__(*args: object, **kwds: object) -> object:  # noqa: N805
        if kwds:
            raise TypeError("Match.__deepcopy__() takes no keyword arguments")
        if len(args) != 2:
            raise TypeError("Match.__deepcopy__() takes exactly one argument (" + str(len(args) - 1) + " given)")
        return args[0]

    def __repr__(self) -> str:                   # match_repr
        group0 = _getslice_by_index(self, 0, None)
        return "<re.Match object; span=(" + str(self._h_mark[0]) + ", " + str(self._h_mark[1]) + "), match=" + repr(group0)[:50] + ">"


def _group_arg(name: str, args: tuple[object, ...], kwds: dict[str, object], self: object) -> int:   # clinic: group=0, positional only
    if kwds:
        raise TypeError("Match." + name + "() takes no keyword arguments")
    if len(args) > 1:
        raise TypeError(name + " expected at most 1 argument, got " + str(len(args)))
    return _getindex(self, args[0] if args else _ABSENT)


def _new_scanner(pattern: object, string: object, pos: int, endpos: int) -> object:   # pattern_scanner
    _length, pos, endpos = _state(pattern, string, pos, endpos)
    self = _bella_new_instance(SRE_Scanner)
    self._a_pattern = pattern
    self._b_string = string
    self._c_pos = pos
    self._d_endpos = endpos
    self._e_start = pos
    self._f_must_advance = False
    self._g_executing = False
    hold = _BufferHold()
    hold._string = string
    _sre_call("export", string, 1)
    self._h_hold = hold
    return self


def _scan(self: object, mode: int) -> object:    # _sre_SRE_Scanner_search_impl
    if self._g_executing:  # type: ignore[attr-defined]
        raise ValueError("regular expression scanner already executing")
    if self._e_start is None or self._e_start > self._d_endpos:  # type: ignore[attr-defined]
        return None
    self._g_executing = True  # type: ignore[attr-defined]
    try:
        marks = _run(self._a_pattern, self._b_string, self._c_pos, self._d_endpos, self._e_start, self._f_must_advance, mode)  # type: ignore[attr-defined]
        if marks is None:
            self._e_start = None  # type: ignore[attr-defined]
            return None
        self._f_must_advance = marks[1] == marks[0]  # type: ignore[attr-defined, index]
        self._e_start = marks[1]  # type: ignore[attr-defined, index]
        return _new_match(self._a_pattern, self._b_string, self._c_pos, self._d_endpos, marks)  # type: ignore[attr-defined, arg-type]
    finally:
        self._g_executing = False  # type: ignore[attr-defined]


class _BufferHold:
    """What a scanner keeps of its bytes-like string, as its SRE_STATE keeps the buffer: released when the scanner goes (state_fini)."""

    __slots__ = ("_string",)

    def __del__(self) -> None:
        _sre_call("export", self._string, -1)


class SRE_Scanner:  # noqa: N801
    __slots__ = ("_a_pattern", "_b_string", "_c_pos", "_d_endpos", "_e_start", "_f_must_advance", "_g_executing", "_h_hold")

    @property
    def pattern(self) -> object:
        return self._a_pattern

    def prefixmatch(*args: object, **kwds: object) -> object:  # noqa: N805
        _scanner_args("prefixmatch", args, kwds)
        return _scan(args[0], 0)

    match = prefixmatch

    def search(*args: object, **kwds: object) -> object:  # noqa: N805
        _scanner_args("search", args, kwds)
        return _scan(args[0], 2)


def _scanner_args(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:   # METH_METHOD with no parameters
    if kwds or len(args) != 1:
        raise TypeError(name + "() takes no arguments")


class SRE_Template:  # noqa: N801
    __slots__ = ("_a_literal", "_b_items")


# which are METH_METHOD in C: bound, each is a builtin_method. A Match's __getitem__ is mp_subscript alone, so it is no sequence
_present(Pattern, "re", False, ("prefixmatch", "match", "fullmatch", "search", "finditer", "scanner", "sub", "subn"))
_present(Match, "re", True, ())
_present(SRE_Scanner, "_sre", False, ("prefixmatch", "match", "search"))
_present(SRE_Template, "_sre", False, ())
