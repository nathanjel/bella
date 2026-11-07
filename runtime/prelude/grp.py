"""grp, in Python over posix.cpp's getgrgid, getgrnam and getgrent (Modules/grpmodule.c); see posix.py beside it."""

__all__ = ["getgrall", "getgrgid", "getgrnam", "struct_group"]

__name__ = "grp"

try:
    _number_index                                # noqa: B018  # PyNumber_Index
    _tp_name                                     # noqa: B018  # Py_TYPE(obj)->tp_name
    _structseq                                   # noqa: B018  # bootstrap.py's: a type of named tuples
    _sys                                         # noqa: B018  # the system calls, by name
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _number_index: Callable[..., int] = _missing
    _tp_name: Callable[..., str] = _missing
    _structseq: Callable[..., Any] = _missing
    _sys: Callable[..., Any] = _missing

struct_group = _structseq("struct_group", "grp", ["gr_name", "gr_passwd", "gr_gid", "gr_mem"], 4)


def _entry(fields: tuple[object, ...]) -> object:   # mkgrent
    name, passwd, gid, members = fields
    return struct_group((bytes.decode(name, "utf-8", "surrogateescape"), bytes.decode(passwd, "utf-8", "surrogateescape"), gid,  # type: ignore[arg-type]
                         [bytes.decode(member, "utf-8", "surrogateescape") for member in members]))  # type: ignore[attr-defined]


def _argument(name: str, parameter: str, args: tuple[object, ...], kwds: dict[str, object]) -> object:   # one argument, by position or by name
    if len(args) + len(kwds) > 1:
        raise TypeError(name + "() takes at most 1 argument (" + str(len(args) + len(kwds)) + " given)")
    if args:
        return args[0]
    if parameter in kwds:
        return kwds[parameter]
    raise TypeError(name + "() missing required argument '" + parameter + "' (pos 1)")   # before any keyword it does not know


def _gid(value: object) -> int:                  # _Py_Gid_Converter: -1 as gid_t has it; what an unsigned long cannot hold is greater than the maximum, what a gid_t cannot is less than the minimum
    if isinstance(value, float):
        raise TypeError("gid should be integer, not " + _tp_name(value))
    if not isinstance(value, int) and not hasattr(type(value), "__index__"):
        raise TypeError("gid should be integer, not " + _tp_name(value))
    gid = _number_index(value)
    if gid == -1:
        return 2**32 - 1
    if gid >= 2**64:
        raise OverflowError("gid is greater than maximum")
    if gid < -1 or gid >= 2**32:
        raise OverflowError("gid is less than minimum")
    return gid


def _shown(gid: int) -> str:                     # the C formats the gid_t as an int: 2**32 - 1 is -1
    return str(gid if gid < 2**31 else gid - 2**32)


def getgrgid(*args: object, **kwds: object) -> object:
    idobj = _argument("getgrgid", "id", args, kwds)
    gid = _gid(idobj)
    found = _sys("getgrgid", gid)
    if found is None:
        raise KeyError("getgrgid(): gid not found: " + _shown(gid))
    return _entry(found)


def getgrnam(*args: object, **kwds: object) -> object:
    name = _argument("getgrnam", "name", args, kwds)
    if not isinstance(name, str):
        raise TypeError("getgrnam() argument 'name' must be str, not " + _tp_name(name))
    encoded = str.encode(name, "utf-8", "surrogateescape")
    if 0 in encoded:
        raise ValueError("embedded null byte")
    found = _sys("getgrnam", encoded)
    if found is None:
        raise KeyError("getgrnam(): name not found: " + repr(name))
    return _entry(found)


def getgrall(*args: object, **kwds: object) -> list[object]:
    if kwds:
        raise TypeError("grp.getgrall() takes no keyword arguments")
    if args:
        raise TypeError("grp.getgrall() takes no arguments (" + str(len(args)) + " given)")
    return [_entry(fields) for fields in _sys("getgrall")]
