# clause: C-7-61
# spec: section 7
# status: P1
# source: dialect specification section 7 (os), Modules/posixmodule.c and Modules/clinic/posixmodule.c.h (Argument Clinic converts in the order of the parameters; path_converter, dir_fd_converter, _fd_converter), review R20 (RL-429)
"""The order in which the functions of os convert their arguments. An argument that is asked for its path (__fspath__), its
number (__index__, __float__) or its truth (__bool__) says so, and a program can see the order: the parameters' own, whatever
order the call names them in; what a function converts itself (the times of utime, the offsets of copy_file_range and
sendfile) comes after all of them; a conversion that fails ends it there; and an object that is a number and a path at once
is a descriptor to the functions that take one."""
# ruff: noqa: E501, PTH
# The extended attributes, where review R20 found the order wrong (RL-429), need a file system that has them and are compared
# on one machine (pipeline/tests/test_review_2026_11_10.py).
import os
import tempfile
from collections.abc import Callable

trace: list[str] = []


class Path:
    def __init__(self, name: str, value: str) -> None:
        self.name = name
        self.value = value

    def __fspath__(self) -> str:
        trace.append("fspath " + self.name)
        return self.value


class Index:
    def __init__(self, name: str, value: int) -> None:
        self.name = name
        self.value = value

    def __index__(self) -> int:
        trace.append("index " + self.name)
        return self.value


class Truth:
    def __init__(self, name: str, value: bool) -> None:
        self.name = name
        self.value = value

    def __bool__(self) -> bool:
        trace.append("bool " + self.name)
        return self.value


class Real:
    def __init__(self, name: str, value: float) -> None:
        self.name = name
        self.value = value

    def __float__(self) -> float:
        trace.append("float " + self.name)
        return self.value


class Both:
    """An index and a path at once."""
    def __init__(self, name: str, number: int, value: str) -> None:
        self.name = name
        self.number = number
        self.value = value

    def __index__(self) -> int:
        trace.append("index " + self.name)
        return self.number

    def __fspath__(self) -> str:
        trace.append("fspath " + self.name)
        return self.value


def show(label: str, call: Callable[[], object]) -> None:
    del trace[:]
    try:
        call()
        outcome = "ok"
    except Exception as e:
        outcome = type(e).__name__
    print(label, outcome, trace)


def P(name: str, value: str = "file") -> Path:
    return Path(name, value)


def N(name: str, value: int) -> Index:
    return Index(name, value)


def T(name: str, value: bool = True) -> Truth:
    return Truth(name, value)


def main() -> None:
    with tempfile.TemporaryDirectory() as d:
        os.chdir(d)
        with open("file", "wb") as f:
            f.write(b"0123456789abcdef")
        os.mkdir("dir")
        top = os.open(d, os.O_RDONLY)
        fd = os.open("file", os.O_RDWR)
        out = os.open("out", os.O_RDWR | os.O_CREAT)

        show("stat", lambda: os.stat(P("path"), dir_fd=N("dir_fd", top), follow_symlinks=T("follow")))  # type: ignore[arg-type]
        show("stat by name", lambda: os.stat(follow_symlinks=T("follow"), dir_fd=N("dir_fd", top), path=P("path")))  # type: ignore[arg-type]
        show("stat fd follow", lambda: os.stat(N("path", fd), follow_symlinks=T("follow", False)))  # type: ignore[arg-type]
        show("stat fd dir_fd", lambda: os.stat(N("path", fd), dir_fd=N("dir_fd", top), follow_symlinks=T("follow", False)))  # type: ignore[arg-type]
        show("stat both", lambda: os.stat(Both("path", fd, "missing")))
        show("stat bad dir_fd", lambda: os.stat(P("path"), dir_fd="x", follow_symlinks=T("follow")))  # type: ignore[arg-type]
        show("lstat", lambda: os.lstat(P("path"), dir_fd=N("dir_fd", top)))  # type: ignore[arg-type]
        show("lstat both", lambda: os.lstat(Both("path", fd, "file")))
        show("mkdir", lambda: os.mkdir(P("path", "made"), N("mode", 0o700), dir_fd=N("dir_fd", top)))  # type: ignore[arg-type]
        show("mkdir by name", lambda: os.mkdir(dir_fd=N("dir_fd", top), mode=N("mode", 0o700), path=P("path", "made by name")))  # type: ignore[arg-type]
        show("mkdir bad mode", lambda: os.mkdir(P("path", "made2"), "x", dir_fd=N("dir_fd", top)))  # type: ignore[arg-type]
        show("access", lambda: os.access(P("path"), N("mode", os.R_OK), dir_fd=N("dir_fd", top), effective_ids=T("effective", False), follow_symlinks=T("follow")))  # type: ignore[arg-type]
        show("access by name", lambda: os.access(follow_symlinks=T("follow"), effective_ids=T("effective", False), dir_fd=N("dir_fd", top), mode=N("mode", os.R_OK), path=P("path")))  # type: ignore[arg-type]
        show("access bad mode", lambda: os.access(P("path"), "x", dir_fd=N("dir_fd", top), effective_ids=T("effective", False), follow_symlinks=T("follow")))  # type: ignore[arg-type]
        show("access bad dir_fd", lambda: os.access(P("path"), N("mode", os.R_OK), dir_fd="x", effective_ids=T("effective", False), follow_symlinks=T("follow")))  # type: ignore[arg-type]
        show("readlink", lambda: os.readlink(P("path", "nolink"), dir_fd=N("dir_fd", top)))  # type: ignore[arg-type]
        show("symlink", lambda: os.symlink(P("src"), P("dst", "link"), T("is_dir", False), dir_fd=N("dir_fd", top)))  # type: ignore[arg-type]
        show("symlink bad dst", lambda: os.symlink(P("src"), 1.5, T("is_dir", False), dir_fd=N("dir_fd", top)))  # type: ignore[arg-type]
        show("link", lambda: os.link(P("src"), P("dst", "hard"), src_dir_fd=N("src_dir_fd", top), dst_dir_fd=N("dst_dir_fd", top), follow_symlinks=T("follow")))  # type: ignore[arg-type]
        show("link by name", lambda: os.link(follow_symlinks=T("follow"), dst_dir_fd=N("dst_dir_fd", top), src_dir_fd=N("src_dir_fd", top), dst=P("dst", "hard by name"), src=P("src")))  # type: ignore[arg-type]
        show("link bad dst", lambda: os.link(P("src"), 1.5, src_dir_fd=N("src_dir_fd", top), dst_dir_fd=N("dst_dir_fd", top), follow_symlinks=T("follow")))  # type: ignore[arg-type]
        show("link bad dst_dir_fd", lambda: os.link(P("src"), P("dst", "hard2"), src_dir_fd=N("src_dir_fd", top), dst_dir_fd="x", follow_symlinks=T("follow")))  # type: ignore[arg-type]
        show("rename", lambda: os.rename(P("src", "hard"), P("dst", "harder"), src_dir_fd=N("src_dir_fd", top), dst_dir_fd=N("dst_dir_fd", top)))  # type: ignore[arg-type]
        show("rename by name", lambda: os.rename(dst_dir_fd=N("dst_dir_fd", top), src_dir_fd=N("src_dir_fd", top), dst=P("dst", "hard by another name"), src=P("src", "hard by name")))  # type: ignore[arg-type]
        show("rename bad src_dir_fd", lambda: os.rename(P("src", "harder"), P("dst", "hardest"), src_dir_fd="x", dst_dir_fd=N("dst_dir_fd", top)))  # type: ignore[arg-type]
        show("replace", lambda: os.replace(P("src", "harder"), P("dst", "hard"), src_dir_fd=N("src_dir_fd", top), dst_dir_fd=N("dst_dir_fd", top)))  # type: ignore[arg-type]
        show("open", lambda: os.close(os.open(P("path"), N("flags", os.O_RDONLY), N("mode", 0o600), dir_fd=N("dir_fd", top))))  # type: ignore[arg-type]
        show("open by name", lambda: os.close(os.open(dir_fd=N("dir_fd", top), mode=N("mode", 0o600), flags=N("flags", os.O_RDONLY), path=P("path"))))  # type: ignore[arg-type]
        show("open bad flags", lambda: os.open(P("path"), "x", N("mode", 0o600), dir_fd=N("dir_fd", top)))  # type: ignore[arg-type]
        show("chmod", lambda: os.chmod(P("path"), N("mode", 0o600), dir_fd=N("dir_fd", top), follow_symlinks=T("follow")))  # type: ignore[arg-type]
        show("chmod fd", lambda: os.chmod(N("path", fd), N("mode", 0o600), follow_symlinks=T("follow", False)))  # type: ignore[arg-type]
        show("chmod both", lambda: os.chmod(Both("path", fd, "missing"), N("mode", 0o600)))  # type: ignore[arg-type]
        show("chmod bad mode", lambda: os.chmod(P("path"), "x", dir_fd=N("dir_fd", top), follow_symlinks=T("follow")))  # type: ignore[arg-type]
        show("fchmod", lambda: os.fchmod(N("fd", fd), N("mode", 0o600)))  # type: ignore[arg-type]
        show("copy_file_range", lambda: os.copy_file_range(N("src", fd), N("dst", out), N("count", 4), N("offset_src", 0), N("offset_dst", 0)))  # type: ignore[arg-type]
        show("copy_file_range by name", lambda: os.copy_file_range(offset_dst=N("offset_dst", 0), offset_src=N("offset_src", 0), count=N("count", 4), dst=N("dst", out), src=N("src", fd)))  # type: ignore[arg-type]
        show("copy_file_range bad count", lambda: os.copy_file_range(N("src", fd), N("dst", out), "x", N("offset_src", 0), N("offset_dst", 0)))  # type: ignore[arg-type]
        show("copy_file_range bad offset", lambda: os.copy_file_range(N("src", fd), N("dst", out), N("count", 4), "x", N("offset_dst", 0)))  # type: ignore[arg-type]
        show("sendfile", lambda: os.sendfile(N("out_fd", out), N("in_fd", fd), N("offset", 0), N("count", 4)))  # type: ignore[arg-type]
        show("sendfile bad count", lambda: os.sendfile(N("out_fd", out), N("in_fd", fd), N("offset", 0), "x"))  # type: ignore[arg-type]
        show("sendfile bad offset", lambda: os.sendfile(N("out_fd", out), N("in_fd", fd), "x", N("count", 4)))  # type: ignore[arg-type]
        show("utime times", lambda: os.utime(P("path"), (N("atime", 1), Real("mtime", 2.5)), dir_fd=N("dir_fd", top), follow_symlinks=T("follow")))  # type: ignore[arg-type]
        show("utime ns", lambda: os.utime(P("path"), ns=(N("atime", 1), N("mtime", 2)), dir_fd=N("dir_fd", top), follow_symlinks=T("follow")))  # type: ignore[arg-type]
        show("utime both given", lambda: os.utime(P("path"), (N("atime", 1), N("mtime", 2)), ns=(N("atime_ns", 1), N("mtime_ns", 2)), dir_fd=N("dir_fd", top), follow_symlinks=T("follow")))  # type: ignore[arg-type]
        show("utime bad times", lambda: os.utime(P("path"), 5, dir_fd=N("dir_fd", top), follow_symlinks=T("follow")))  # type: ignore[arg-type]
        show("utime bad atime", lambda: os.utime(P("path"), ("x", N("mtime", 2)), dir_fd=N("dir_fd", top), follow_symlinks=T("follow")))  # type: ignore[arg-type]
        show("utime fd follow", lambda: os.utime(N("path", fd), (N("atime", 1), N("mtime", 2)), follow_symlinks=T("follow", False)))  # type: ignore[arg-type]
        show("utime fd dir_fd", lambda: os.utime(N("path", fd), (N("atime", 1), N("mtime", 2)), dir_fd=N("dir_fd", top)))  # type: ignore[arg-type]
        show("listdir both", lambda: os.listdir(Both("path", top, "missing")))
        show("scandir both", lambda: os.scandir(Both("path", top, "missing")).close())
        show("chdir both", lambda: os.chdir(Both("path", top, "missing")))
        show("unlink", lambda: os.unlink(P("path", "hard"), dir_fd=N("dir_fd", top)))  # type: ignore[arg-type]
        show("remove", lambda: os.remove(P("path", "link"), dir_fd=N("dir_fd", top)))  # type: ignore[arg-type]
        show("rmdir", lambda: os.rmdir(P("path", "made"), dir_fd=N("dir_fd", top)))  # type: ignore[arg-type]
        show("rmdir bad dir_fd", lambda: os.rmdir(P("path", "dir"), dir_fd=1.5))  # type: ignore[arg-type]
        os.close(out)
        os.close(fd)
        os.close(top)
        os.chdir("/")


if __name__ == "__main__":
    main()
