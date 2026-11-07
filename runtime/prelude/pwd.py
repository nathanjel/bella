"""pwd, in Python over posix.cpp's getpwuid, getpwnam and getpwent (Modules/pwdmodule.c); see posix.py beside it."""

__all__ = ["getpwall", "getpwnam", "getpwuid", "struct_passwd"]

__name__ = "pwd"

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

struct_passwd = _structseq("struct_passwd", "pwd", ["pw_name", "pw_passwd", "pw_uid", "pw_gid", "pw_gecos", "pw_dir", "pw_shell"], 7)


def _entry(fields: tuple[object, ...]) -> object:   # mkpwent: the strings decoded as the filesystem's (PyUnicode_DecodeFSDefault)
    name, passwd, uid, gid, gecos, home, shell = fields
    return struct_passwd((bytes.decode(name, "utf-8", "surrogateescape"), bytes.decode(passwd, "utf-8", "surrogateescape"), uid, gid,  # type: ignore[arg-type]
                          bytes.decode(gecos, "utf-8", "surrogateescape"), bytes.decode(home, "utf-8", "surrogateescape"), bytes.decode(shell, "utf-8", "surrogateescape")))  # type: ignore[arg-type]


def _one(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> object:   # METH_O
    if kwds:
        raise TypeError("pwd." + name + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("pwd." + name + "() takes exactly one argument (" + str(len(args)) + " given)")
    return args[0]


def _uid(value: object) -> int | None:           # _Py_Uid_Converter: an int, -1 as uid_t has it, out of range is None (an OverflowError the caller turns into KeyError)
    if isinstance(value, float):
        raise TypeError("uid should be integer, not " + _tp_name(value))
    if not isinstance(value, int) and not hasattr(type(value), "__index__"):
        raise TypeError("uid should be integer, not " + _tp_name(value))
    uid = _number_index(value)
    if uid == -1:
        return 2**32 - 1
    if uid < -1 or uid >= 2**32:
        return None
    return uid


def _shown(uid: int) -> str:                     # the C formats the uid_t as an int: 2**32 - 1 is -1
    return str(uid if uid < 2**31 else uid - 2**32)


def getpwuid(*args: object, **kwds: object) -> object:
    uidobj = _one("getpwuid", args, kwds)
    uid = _uid(uidobj)
    if uid is None:
        raise KeyError("getpwuid(): uid not found")
    found = _sys("getpwuid", uid)
    if found is None:
        raise KeyError("getpwuid(): uid not found: " + _shown(uid))
    return _entry(found)


def getpwnam(*args: object, **kwds: object) -> object:
    name = _one("getpwnam", args, kwds)
    if not isinstance(name, str):
        raise TypeError("getpwnam() argument must be str, not " + _tp_name(name))
    encoded = str.encode(name, "utf-8", "surrogateescape")
    if 0 in encoded:
        raise ValueError("embedded null byte")
    found = _sys("getpwnam", encoded)
    if found is None:
        raise KeyError("getpwnam(): name not found: " + repr(name))
    return _entry(found)


def getpwall(*args: object, **kwds: object) -> list[object]:
    if kwds:
        raise TypeError("pwd.getpwall() takes no keyword arguments")
    if args:
        raise TypeError("pwd.getpwall() takes no arguments (" + str(len(args)) + " given)")
    return [_entry(fields) for fields in _sys("getpwall")]
