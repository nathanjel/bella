# clause: C-7-63
# spec: section 7
# status: P1
# source: dialect specification section 7 (io, os, warnings), Modules/_io/_iomodule.c (_io_open_impl), Modules/_io/fileio.c (_io_FileIO___init___impl), Modules/posixmodule.c (_fd_converter), Objects/fileobject.c (PyObject_AsFileDescriptor)
"""The two RuntimeWarnings of io and os. Line buffering asked of a binary file: open warns and gives the file with the default
buffer, after its checks of the mode and before it opens anything. A bool given as a file descriptor: FileIO and open warn, and
of os the functions that take a descriptor where a path may stand (stat, listdir, chdir, scandir), as dir_fd, or as an object
with fileno (fsync); the functions that take a plain int do not (fstat, isatty, lseek, read, write). The warning is charged to
the calling line; made an error it is raised there and nothing is opened or asked."""
# ruff: noqa: E501, PTH, SIM115
# The descriptors a bool names are the program's own standard input and output: only what does not depend on what they are, and
# changes nothing about them, is done with them here.
import io
import os
import tempfile
import warnings
from collections.abc import Callable


def show(label: str, call: Callable[[], object], outcome: bool = True) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            result = type(call()).__name__
        except Exception as e:
            result = "raised " + type(e).__name__
    print(label, result if outcome else "-", [(w.category.__name__, str(w.message), os.path.basename(w.filename), w.lineno - LINE, w.source) for w in caught])


def failing(label: str, call: Callable[[], object]) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        try:
            result = type(call()).__name__
        except Exception as e:
            result = "raised " + type(e).__name__
    print(label, result)


class Flag(int):
    pass


class Index:
    def __index__(self) -> int:
        return 1


class Fileno:
    def __init__(self, value: object) -> None:
        self.value = value

    def fileno(self) -> object:
        return self.value


def binary_line() -> tuple[str, str, bytes, bool]:
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        with open("f", "rb", buffering=1) as f:
            return type(f).__name__, type(f.raw).__name__, f.read(), f.line_buffering if hasattr(f, "line_buffering") else False


LINE = 0


def main() -> None:
    global LINE
    d = tempfile.mkdtemp()
    os.chdir(d)
    with open("f", "w", encoding="utf-8") as f:
        f.write("text\n")
    with warnings.catch_warnings(record=True) as here:
        warnings.simplefilter("always")
        warnings.warn("the line the others are counted from", stacklevel=1)
    LINE = here[0].lineno

    # line buffering asked of a binary file
    show("binary, buffering=1", lambda: open("f", "rb", buffering=1).close())
    show("binary write, buffering=1", lambda: open("g", "wb", buffering=1).close())
    show("binary r+, buffering=1", lambda: open("g", "r+b", 1).close())
    show("io.open", lambda: io.open("f", "rb", 1).close())  # noqa: UP020
    show("text, buffering=1", lambda: open("f", buffering=1, encoding="utf-8").close())
    show("binary, buffering=2", lambda: open("f", "rb", buffering=2).close())
    show("after the mode's checks", lambda: open("f", "rbt", buffering=1))
    show("after the encoding's check", lambda: open("f", "rb", buffering=1, encoding="utf-8"))
    show("before the file is opened", lambda: open("missing", "rb", buffering=1))
    print("what it gives:", binary_line())
    failing("an error", lambda: open("f", "rb", buffering=1))
    failing("an error, and nothing made", lambda: open("made", "wb", buffering=1))
    print("  made:", os.path.exists("made"))
    failing("an error, the mode's first", lambda: open("f", "rbt", buffering=1))
    failing("an error, before the missing file's", lambda: open("missing", "rb", buffering=1))

    # a bool as a file descriptor: io
    show("FileIO(True)", lambda: io.FileIO(True, "w", closefd=False))
    show("FileIO(False)", lambda: io.FileIO(False, closefd=False))
    show("open(True)", lambda: open(True, "w", closefd=False, encoding="utf-8"))
    show("open(True, 'wb')", lambda: open(True, "wb", closefd=False))
    show("open(True, 'wb', 1): both", lambda: open(True, "wb", 1, closefd=False))
    show("FileIO(Flag(1))", lambda: io.FileIO(Flag(1), "w", closefd=False))
    show("FileIO(1)", lambda: io.FileIO(1, "w", closefd=False))
    failing("FileIO(True), an error", lambda: io.FileIO(True, "w", closefd=False))
    failing("open(True), an error", lambda: open(True, "w", closefd=False, encoding="utf-8"))

    # a bool as a file descriptor: os, where a path may stand, as dir_fd, and through fileno
    show("os.stat(True)", lambda: os.stat(True))
    show("os.stat(False)", lambda: os.stat(False))
    show("os.listdir(True)", lambda: os.listdir(True), outcome=False)
    show("os.scandir(True)", lambda: os.scandir(True), outcome=False)
    show("os.chdir(True)", lambda: os.chdir(True), outcome=False)
    show("os.stat('f', dir_fd=True)", lambda: os.stat("f", dir_fd=True), outcome=False)
    show("os.open('f', 0, dir_fd=True)", lambda: os.open("f", os.O_RDONLY, dir_fd=True), outcome=False)
    show("os.unlink('nothing', dir_fd=True)", lambda: os.unlink("nothing", dir_fd=True), outcome=False)
    show("os.fsync(True)", lambda: os.fsync(True), outcome=False)
    show("os.fsync(fileno giving True)", lambda: os.fsync(Fileno(True)), outcome=False)  # type: ignore[arg-type]
    show("os.stat(Flag(1))", lambda: os.stat(Flag(1)))
    show("os.stat(Index())", lambda: os.stat(Index()))  # type: ignore[arg-type]
    failing("os.stat(True), an error", lambda: os.stat(True))
    failing("os.stat('f', dir_fd=True), an error", lambda: os.stat("f", dir_fd=True))
    failing("os.fsync(True), an error", lambda: os.fsync(True))
    failing("os.listdir(False), an error", lambda: os.listdir(False))

    # and where a plain int is taken: no warning
    show("os.fstat(True)", lambda: os.fstat(True))
    show("os.isatty(False)", lambda: os.isatty(False))
    show("os.lseek(True, 0, 1)", lambda: os.lseek(True, 0, os.SEEK_CUR), outcome=False)
    show("os.write(True, b'')", lambda: os.write(True, b""))
    show("os.read(False, 0)", lambda: os.read(False, 0), outcome=False)
    show("os.get_terminal_size(True)", lambda: os.get_terminal_size(True), outcome=False)
    os.chdir("/")
    for name in os.listdir(d):
        os.unlink(os.path.join(d, name))
    os.rmdir(d)


if __name__ == "__main__":
    main()
