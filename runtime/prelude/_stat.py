"""_stat, in Python, from Modules/_stat.c; see itertools.py beside it.

The constants are Linux's, as the pin's are. S_IFDOOR, S_IFPORT and S_IFWHT are 0 there, and their S_IS... say False.
"""

__all__ = ["SF_APPEND", "SF_ARCHIVED", "SF_DATALESS", "SF_FIRMLINK", "SF_IMMUTABLE", "SF_NOUNLINK", "SF_SETTABLE", "SF_SNAPSHOT", "ST_ATIME", "ST_CTIME", "ST_DEV", "ST_GID", "ST_INO", "ST_MODE", "ST_MTIME", "ST_NLINK", "ST_SIZE", "ST_UID", "S_ENFMT", "S_IEXEC", "S_IFBLK", "S_IFCHR", "S_IFDIR", "S_IFDOOR", "S_IFIFO", "S_IFLNK", "S_IFMT", "S_IFPORT", "S_IFREG", "S_IFSOCK", "S_IFWHT", "S_IMODE", "S_IREAD", "S_IRGRP", "S_IROTH", "S_IRUSR", "S_IRWXG", "S_IRWXO", "S_IRWXU", "S_ISBLK", "S_ISCHR", "S_ISDIR", "S_ISDOOR", "S_ISFIFO", "S_ISGID", "S_ISLNK", "S_ISPORT", "S_ISREG", "S_ISSOCK", "S_ISUID", "S_ISVTX", "S_ISWHT", "S_IWGRP", "S_IWOTH", "S_IWRITE", "S_IWUSR", "S_IXGRP", "S_IXOTH", "S_IXUSR", "UF_APPEND", "UF_COMPRESSED", "UF_DATAVAULT", "UF_HIDDEN", "UF_IMMUTABLE", "UF_NODUMP", "UF_NOUNLINK", "UF_OPAQUE", "UF_SETTABLE", "UF_TRACKED", "filemode"]

__name__ = "_stat"

try:
    _number_index                                # noqa: B018  # PyNumber_Index, given by the runtime
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _number_index: Callable[..., int] = _missing

SF_APPEND = 262144
SF_ARCHIVED = 65536
SF_DATALESS = 1073741824
SF_FIRMLINK = 8388608
SF_IMMUTABLE = 131072
SF_NOUNLINK = 1048576
SF_SETTABLE = 4294901760
SF_SNAPSHOT = 2097152
ST_ATIME = 7
ST_CTIME = 9
ST_DEV = 2
ST_GID = 5
ST_INO = 1
ST_MODE = 0
ST_MTIME = 8
ST_NLINK = 3
ST_SIZE = 6
ST_UID = 4
S_ENFMT = 1024
S_IEXEC = 64
S_IFBLK = 24576
S_IFCHR = 8192
S_IFDIR = 16384
S_IFDOOR = 0
S_IFIFO = 4096
S_IFLNK = 40960
S_IFPORT = 0
S_IFREG = 32768
S_IFSOCK = 49152
S_IFWHT = 0
S_IREAD = 256
S_IRGRP = 32
S_IROTH = 4
S_IRUSR = 256
S_IRWXG = 56
S_IRWXO = 7
S_IRWXU = 448
S_ISGID = 1024
S_ISUID = 2048
S_ISVTX = 512
S_IWGRP = 16
S_IWOTH = 2
S_IWRITE = 128
S_IWUSR = 128
S_IXGRP = 8
S_IXOTH = 1
S_IXUSR = 64
UF_APPEND = 4
UF_COMPRESSED = 32
UF_DATAVAULT = 128
UF_HIDDEN = 32768
UF_IMMUTABLE = 2
UF_NODUMP = 1
UF_NOUNLINK = 16
UF_OPAQUE = 8
UF_SETTABLE = 65535
UF_TRACKED = 64


def _mode(args: tuple[object, ...], kwds: dict[str, object], name: str) -> int:   # METH_O, _PyLong_AsMode_t
    if kwds:
        raise TypeError("_stat." + name + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("_stat." + name + "() takes exactly one argument (" + str(len(args)) + " given)")
    value = _number_index(args[0])
    if value < 0:
        raise OverflowError("can't convert negative value to unsigned int")
    if value >= 2**64:
        raise OverflowError("Python int too large to convert to C unsigned long")
    if value >= 2**32:
        raise OverflowError("mode out of range")
    return value


def S_IMODE(*args: object, **kwds: object) -> int:
    return _mode(args, kwds, "S_IMODE") & 0o7777


def S_IFMT(*args: object, **kwds: object) -> int:
    return _mode(args, kwds, "S_IFMT") & 0o170000


def S_ISDIR(*args: object, **kwds: object) -> bool:
    return _mode(args, kwds, "S_ISDIR") & 0o170000 == S_IFDIR


def S_ISCHR(*args: object, **kwds: object) -> bool:
    return _mode(args, kwds, "S_ISCHR") & 0o170000 == S_IFCHR


def S_ISBLK(*args: object, **kwds: object) -> bool:
    return _mode(args, kwds, "S_ISBLK") & 0o170000 == S_IFBLK


def S_ISREG(*args: object, **kwds: object) -> bool:
    return _mode(args, kwds, "S_ISREG") & 0o170000 == S_IFREG


def S_ISFIFO(*args: object, **kwds: object) -> bool:
    return _mode(args, kwds, "S_ISFIFO") & 0o170000 == S_IFIFO


def S_ISLNK(*args: object, **kwds: object) -> bool:
    return _mode(args, kwds, "S_ISLNK") & 0o170000 == S_IFLNK


def S_ISSOCK(*args: object, **kwds: object) -> bool:
    return _mode(args, kwds, "S_ISSOCK") & 0o170000 == S_IFSOCK


def S_ISDOOR(*args: object, **kwds: object) -> bool:
    _mode(args, kwds, "S_ISDOOR")
    return False


def S_ISPORT(*args: object, **kwds: object) -> bool:
    _mode(args, kwds, "S_ISPORT")
    return False


def S_ISWHT(*args: object, **kwds: object) -> bool:
    _mode(args, kwds, "S_ISWHT")
    return False


def filemode(*args: object, **kwds: object) -> str:   # stat_filemode: filetype, then fileperm
    mode = _mode(args, kwds, "filemode")
    kind = mode & 0o170000
    out = {S_IFREG: "-", S_IFDIR: "d", S_IFLNK: "l", S_IFBLK: "b", S_IFCHR: "c", S_IFIFO: "p", S_IFSOCK: "s"}.get(kind, "?")
    out += "r" if mode & S_IRUSR else "-"
    out += "w" if mode & S_IWUSR else "-"
    out += ("s" if mode & S_IXUSR else "S") if mode & S_ISUID else ("x" if mode & S_IXUSR else "-")
    out += "r" if mode & S_IRGRP else "-"
    out += "w" if mode & S_IWGRP else "-"
    out += ("s" if mode & S_IXGRP else "S") if mode & S_ISGID else ("x" if mode & S_IXGRP else "-")
    out += "r" if mode & S_IROTH else "-"
    out += "w" if mode & S_IWOTH else "-"
    out += ("t" if mode & S_IXOTH else "T") if mode & S_ISVTX else ("x" if mode & S_IXOTH else "-")
    return out
