"""_locale, in Python over the C library's locale calls in posix.cpp (Modules/_localemodule.c); see posix.py beside it.

The process locale is what the runtime set at the start as CPython's start does: LC_CTYPE from the environment, coerced to C.UTF-8
when that is the C locale (PEP 538), the other categories C. Phase 1 is the C and UTF-8 locales (manifest: the rest of locale is
[P2+]); a program may still set another, and what the C library answers for it is what it gets.
"""

__all__ = ["ABDAY_1", "ABDAY_2", "ABDAY_3", "ABDAY_4", "ABDAY_5", "ABDAY_6", "ABDAY_7", "ABMON_1", "ABMON_10", "ABMON_11", "ABMON_12", "ABMON_2", "ABMON_3", "ABMON_4", "ABMON_5", "ABMON_6", "ABMON_7", "ABMON_8", "ABMON_9", "ALT_DIGITS", "AM_STR", "CHAR_MAX", "CODESET", "CRNCYSTR", "DAY_1", "DAY_2", "DAY_3", "DAY_4", "DAY_5", "DAY_6", "DAY_7", "D_FMT", "D_T_FMT", "ERA", "ERA_D_FMT", "ERA_D_T_FMT", "ERA_T_FMT", "Error", "LC_ALL", "LC_COLLATE", "LC_CTYPE", "LC_MESSAGES", "LC_MONETARY", "LC_NUMERIC", "LC_TIME", "MON_1", "MON_10", "MON_11", "MON_12", "MON_2", "MON_3", "MON_4", "MON_5", "MON_6", "MON_7", "MON_8", "MON_9", "NOEXPR", "PM_STR", "RADIXCHAR", "THOUSEP", "T_FMT", "T_FMT_AMPM", "YESEXPR", "bind_textdomain_codeset", "bindtextdomain", "dcgettext", "dgettext", "getencoding", "gettext", "localeconv", "nl_langinfo", "setlocale", "strcoll", "strxfrm", "textdomain"]

__name__ = "_locale"

try:
    _number_index                                # noqa: B018  # PyNumber_Index
    _tp_name                                     # noqa: B018  # Py_TYPE(obj)->tp_name
    _sys                                         # noqa: B018  # the system calls, by name
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _number_index: Callable[..., int] = _missing
    _tp_name: Callable[..., str] = _missing
    _sys: Callable[..., Any] = _missing

ABDAY_1 = 131072
ABDAY_2 = 131073
ABDAY_3 = 131074
ABDAY_4 = 131075
ABDAY_5 = 131076
ABDAY_6 = 131077
ABDAY_7 = 131078
ABMON_1 = 131086
ABMON_10 = 131095
ABMON_11 = 131096
ABMON_12 = 131097
ABMON_2 = 131087
ABMON_3 = 131088
ABMON_4 = 131089
ABMON_5 = 131090
ABMON_6 = 131091
ABMON_7 = 131092
ABMON_8 = 131093
ABMON_9 = 131094
ALT_DIGITS = 131119
AM_STR = 131110
CHAR_MAX = 127
CODESET = 14
CRNCYSTR = 262159
DAY_1 = 131079
DAY_2 = 131080
DAY_3 = 131081
DAY_4 = 131082
DAY_5 = 131083
DAY_6 = 131084
DAY_7 = 131085
D_FMT = 131113
D_T_FMT = 131112
ERA = 131116
ERA_D_FMT = 131118
ERA_D_T_FMT = 131120
ERA_T_FMT = 131121
LC_ALL = 6
LC_COLLATE = 3
LC_CTYPE = 0
LC_MESSAGES = 5
LC_MONETARY = 4
LC_NUMERIC = 1
LC_TIME = 2
MON_1 = 131098
MON_10 = 131107
MON_11 = 131108
MON_12 = 131109
MON_2 = 131099
MON_3 = 131100
MON_4 = 131101
MON_5 = 131102
MON_6 = 131103
MON_7 = 131104
MON_8 = 131105
MON_9 = 131106
NOEXPR = 327681
PM_STR = 131111
RADIXCHAR = 65536
THOUSEP = 65537
T_FMT = 131114
T_FMT_AMPM = 131115
YESEXPR = 327680
_DATE_FMT = 131180

_LANGINFO = frozenset((ABDAY_1, ABDAY_2, ABDAY_3, ABDAY_4, ABDAY_5, ABDAY_6, ABDAY_7, ABMON_1, ABMON_10, ABMON_11, ABMON_12, ABMON_2, ABMON_3, ABMON_4, ABMON_5, ABMON_6, ABMON_7, ABMON_8, ABMON_9, ALT_DIGITS, AM_STR, CODESET, CRNCYSTR, DAY_1, DAY_2, DAY_3, DAY_4, DAY_5, DAY_6, DAY_7, D_FMT, D_T_FMT, ERA, ERA_D_FMT, ERA_D_T_FMT, ERA_T_FMT, MON_1, MON_10, MON_11, MON_12, MON_2, MON_3, MON_4, MON_5, MON_6, MON_7, MON_8, MON_9, NOEXPR, PM_STR, RADIXCHAR, THOUSEP, T_FMT, T_FMT_AMPM, YESEXPR, _DATE_FMT))


class Error(Exception):
    pass


Error.__module__ = "locale"


def _positional(name: str, args: tuple[object, ...], kwds: dict[str, object], low: int, high: int) -> int:   # METH_FASTCALL, _PyArg_CheckPositional
    if kwds:
        raise TypeError("_locale." + name + "() takes no keyword arguments")
    n = len(args)
    if n < low:
        raise TypeError(name + " expected " + ("" if low == high else "at least ") + str(low) + " argument" + ("" if low == 1 else "s") + ", got " + str(n))
    if n > high:
        raise TypeError(name + " expected " + ("" if low == high else "at most ") + str(high) + " argument" + ("" if high == 1 else "s") + ", got " + str(n))
    return n


def _one(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> object:   # METH_O
    if kwds:
        raise TypeError("_locale." + name + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("_locale." + name + "() takes exactly one argument (" + str(len(args)) + " given)")
    return args[0]


def _noargs(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:   # METH_NOARGS
    if kwds:
        raise TypeError("_locale." + name + "() takes no keyword arguments")
    if args:
        raise TypeError("_locale." + name + "() takes no arguments (" + str(len(args)) + " given)")


def _c_string(value: object, what: str) -> bytes:   # str: the C string, UTF-8 with surrogateescape (PyUnicode_EncodeLocale in a UTF-8 locale), no null inside
    if not isinstance(value, str):
        raise TypeError(what + " must be str, not " + _tp_name(value))
    encoded = str.encode(value, "utf-8", "surrogateescape")
    if 0 in encoded:
        raise ValueError("embedded null character")
    return encoded


def _c_string_or_none(value: object, what: str) -> bytes | None:   # str(accept={str, NoneType})
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(what + " must be str or None, not " + _tp_name(value))
    return _c_string(value, what)


def _decode(value: bytes) -> str:                # locale_decode: PyUnicode_DecodeLocale
    return bytes.decode(value, "utf-8", "surrogateescape")


def _int(value: object) -> int:                  # PyLong_AsInt, as the clinic's int converter
    if isinstance(value, float):
        raise TypeError("'float' object cannot be interpreted as an integer")
    out = _number_index(value)
    if out > 2**31 - 1 or out < -(2**31):
        raise OverflowError("Python int too large to convert to C int")
    return out


def setlocale(*args: object, **kwds: object) -> str:
    n = _positional("setlocale", args, kwds, 1, 2)
    category = _int(args[0])
    locale = _c_string_or_none(args[1], "setlocale() argument 2") if n > 1 else None
    result = _sys("setlocale", category, locale)
    if result is None:
        raise Error("unsupported locale setting" if locale is not None else "locale query failed")
    return _decode(result)


def localeconv(*args: object, **kwds: object) -> dict[str, object]:
    _noargs("localeconv", args, kwds)
    fields = _sys("localeconv")
    out: dict[str, object] = {}
    for name, value in fields:
        out[name] = _decode(value) if isinstance(value, bytes) else value
    return out


def strcoll(*args: object, **kwds: object) -> int:
    _positional("strcoll", args, kwds, 2, 2)
    if not isinstance(args[0], str):
        raise TypeError("strcoll() argument 1 must be str, not " + _tp_name(args[0]))
    if not isinstance(args[1], str):
        raise TypeError("strcoll() argument 2 must be str, not " + _tp_name(args[1]))
    for s in args:                               # PyUnicode_AsWideCharString: no NUL in a C wide string
        if "\0" in str.__str__(s):  # type: ignore[arg-type]
            raise ValueError("embedded null character")
    return _sys("strcoll", str.__str__(args[0]), str.__str__(args[1]))  # type: ignore[no-any-return]


def strxfrm(*args: object, **kwds: object) -> str:
    string = _one("strxfrm", args, kwds)
    if not isinstance(string, str):
        raise TypeError("strxfrm() argument must be str, not " + _tp_name(string))
    if str.__contains__(string, "\0"):
        raise ValueError("embedded null character")
    return _sys("strxfrm", str.__str__(string))  # type: ignore[no-any-return]


def nl_langinfo(*args: object, **kwds: object) -> str:
    key = _int(_one("nl_langinfo", args, kwds))
    if key not in _LANGINFO:
        raise ValueError("unsupported langinfo constant")
    return _decode(_sys("nl_langinfo", key))


def getencoding(*args: object, **kwds: object) -> str:
    _noargs("getencoding", args, kwds)
    return _decode(_sys("nl_langinfo", CODESET))


def gettext(*args: object, **kwds: object) -> str:
    msg = _one("gettext", args, kwds)
    return _decode(_sys("gettext", None, _c_string(msg, "gettext() argument"), None))


def dgettext(*args: object, **kwds: object) -> str:
    _positional("dgettext", args, kwds, 2, 2)
    domain = _c_string_or_none(args[0], "dgettext() argument 1")
    return _decode(_sys("gettext", domain, _c_string(args[1], "dgettext() argument 2"), None))


def dcgettext(*args: object, **kwds: object) -> str:
    _positional("dcgettext", args, kwds, 3, 3)
    domain = _c_string_or_none(args[0], "dcgettext() argument 1")
    msg = _c_string(args[1], "dcgettext() argument 2")
    return _decode(_sys("gettext", domain, msg, _int(args[2])))


def textdomain(*args: object, **kwds: object) -> str:
    domain = _one("textdomain", args, kwds)
    return _decode(_sys("textdomain", _c_string_or_none(domain, "textdomain() argument")))


def bindtextdomain(*args: object, **kwds: object) -> object:
    _positional("bindtextdomain", args, kwds, 2, 2)
    domain = _c_string(args[0], "bindtextdomain() argument 1")
    dirname = args[1]
    if dirname is not None:                      # PyUnicode_FSConverter: a path, as the file system encodes it
        if not issubclass(type(dirname), (str, bytes)):
            fspath = getattr(type(dirname), "__fspath__", None)
            if fspath is None:
                raise TypeError("expected str, bytes or os.PathLike object, not " + _tp_name(dirname))
            dirname = fspath(dirname)
            if not issubclass(type(dirname), (str, bytes)):
                raise TypeError("expected " + type(args[1]).__name__ + ".__fspath__() to return str or bytes, not " + type(dirname).__name__)
        dirname = str.encode(dirname, "utf-8", "surrogateescape") if isinstance(dirname, str) else bytes(dirname)
        if 0 in dirname:
            raise ValueError("embedded null byte")
    result = _sys("bindtextdomain", domain, dirname)
    return None if result is None else _decode(result)


def bind_textdomain_codeset(*args: object, **kwds: object) -> object:
    _positional("bind_textdomain_codeset", args, kwds, 2, 2)
    domain = _c_string(args[0], "bind_textdomain_codeset() argument 1")
    codeset = _c_string_or_none(args[1], "bind_textdomain_codeset() argument 2")
    result = _sys("bind_textdomain_codeset", domain, codeset)
    return None if result is None else _decode(result)
