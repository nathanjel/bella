# clause: C-7-24
# spec: section 7
# status: P1
# source: dialect specification section 7, Modules/_stat.c, Lib/stat.py
"""_stat and the module stat, which is the standard library's over it: the constants, the tests of a mode, what a mode
may be, and filemode's letters."""
# ruff: noqa: B018, B023, RUF015
import stat

import _stat


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


names = [k for k in sorted(vars(_stat)) if not k.startswith("__")]
print(names)
print([getattr(_stat, k) for k in names if isinstance(getattr(_stat, k), int)])
print(all([getattr(stat, k) == getattr(_stat, k) or callable(getattr(_stat, k)) for k in names]), stat.S_ISDIR is _stat.S_ISDIR, stat.filemode is _stat.filemode, stat.S_IMODE is _stat.S_IMODE)
modes = (0, 1, 0o777, 0o7777, 0o170000, 0o170777, 0o040000, 0o040755, 0o020000, 0o060000, 0o100000, 0o100644, 0o010000, 0o120000, 0o140000, 0o104755, 0o102755, 0o041777, 0o104644, 0o102644, 0o041776, 0o100000 + 2**31, 2**32 - 1, True)
for m in modes:
    print(m, stat.S_IMODE(m), stat.S_IFMT(m), stat.S_ISDIR(m), stat.S_ISCHR(m), stat.S_ISBLK(m), stat.S_ISREG(m), stat.S_ISFIFO(m), stat.S_ISLNK(m), stat.S_ISSOCK(m), stat.S_ISDOOR(m), stat.S_ISPORT(m), stat.S_ISWHT(m), stat.filemode(m))


class Idx:
    def __index__(self) -> int:
        return 0o040755


print(stat.S_ISDIR(Idx()), stat.filemode(Idx()), stat.S_IMODE(Idx()), stat.S_IFMT(Idx()))  # type: ignore[arg-type]
for name in ("S_IMODE", "S_IFMT", "S_ISDIR", "S_ISCHR", "S_ISBLK", "S_ISREG", "S_ISFIFO", "S_ISLNK", "S_ISSOCK", "S_ISDOOR", "S_ISPORT", "S_ISWHT", "filemode"):
    f = getattr(stat, name)
    print(name, failed(lambda: f()), failed(lambda: f(1, 2)), failed(lambda: f(x=1)), failed(lambda: f("a")), failed(lambda: f(1.5)), failed(lambda: f(None)), failed(lambda: f(-1)), failed(lambda: f(2**32)), failed(lambda: f(2**64)), failed(lambda: f(2**70)), f.__name__, f.__module__)
print(stat.UF_NODUMP, stat.SF_ARCHIVED, stat.FILE_ATTRIBUTE_ARCHIVE, stat.ST_MODE, stat.ST_CTIME, stat.S_IEXEC, stat.S_IREAD, stat.S_IWRITE, stat.S_ENFMT, stat.S_IFDOOR, stat.S_IFPORT, stat.S_IFWHT)
