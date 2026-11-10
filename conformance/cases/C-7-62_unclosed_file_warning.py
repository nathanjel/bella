# clause: C-7-62
# spec: section 7
# status: P1
# source: dialect specification section 7 (io, warnings), Modules/_io/fileio.c (fileio_dealloc_warn, _io_FileIO_close_impl), Modules/_io/bufferedio.c (_io__Buffered__dealloc_warn_impl, _io__Buffered_close_impl), Modules/_io/textio.c (_io_TextIOWrapper_close_impl), Modules/_io/iobase.c (iobase_finalize), Python/_warnings.c (PyErr_ResourceWarning)
"""The ResourceWarning of a file that is dropped open. Which objects give it (a file that owns its descriptor, under whatever
buffer or text layer the program dropped) and which do not (a closed one, one that does not own its descriptor, one in memory,
an open that failed and closed what it had opened); what it says and about what (the object dropped is its source, the line
that dropped it is charged); what a subclass can change (_dealloc_warn is asked of the raw file by the layers above it, never of
the object itself); the warning made an error (reported as unraisable, about the raw file); the filters and the registry; and
the two closes of a raw file failing one after the other."""
# ruff: noqa: E501, PTH, SIM115
# A descriptor's number is the process's own and is masked. What the default hook prints, and a file still open when the
# program ends, are on standard error and are compared on one machine (pipeline/tests/test_system_modules.py).
import io
import os
import sys
import tempfile
import warnings
from collections.abc import Callable


def digits(text: str) -> str:
    return "".join("N" if c.isdigit() else c for c in text)


def drop(label: str, make: Callable[[], object]) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            make()
        except Exception as e:
            print("  raised", type(e).__name__)
    print(label, [(w.category.__name__, digits(str(w.message)), type(w.source).__name__, os.path.basename(w.filename), w.lineno, w.source.closed)  # type: ignore[union-attr]
                  for w in caught])


class Mine(io.FileIO):
    pass


class Closing(io.FileIO):
    def close(self) -> None:
        print("  close called, finalizing:", self._finalizing)  # type: ignore[attr-defined]
        super().close()


class NoWarn(io.FileIO):
    def _dealloc_warn(self, source: object) -> None:
        print("  NoWarn._dealloc_warn called with", type(source).__name__, source is self)


class Quiet(io.BufferedReader):
    def _dealloc_warn(self, source: object) -> None:
        print("  Quiet._dealloc_warn called")


class Loud(io.FileIO):
    def _dealloc_warn(self, source: object) -> None:
        print("  Loud._dealloc_warn", type(source).__name__)
        raise ValueError("from _dealloc_warn")


class Text(io.TextIOWrapper):
    def _dealloc_warn(self, source: object) -> None:
        print("  Text._dealloc_warn called")


class Odd:
    """A buffer that is no buffer: a text layer asks it for _dealloc_warn all the same."""
    closed = False

    def readable(self) -> bool:
        return True

    def writable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return False

    def flush(self) -> None:
        pass

    def close(self) -> None:
        print("  Odd.close")

    def _dealloc_warn(self, source: object) -> None:
        print("  Odd._dealloc_warn", type(source).__name__)


class Bare:
    closed = False

    def readable(self) -> bool:
        return True

    def writable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return False

    def flush(self) -> None:
        pass

    def close(self) -> None:
        print("  Bare.close")


class BadRepr(io.FileIO):
    def __repr__(self) -> str:
        raise KeyError("no repr")


class WarnRepr(io.FileIO):
    def __repr__(self) -> str:
        raise UserWarning("repr warns")


class Failing(io.FileIO):
    def flush(self) -> None:
        raise ValueError("flush failed")


def with_block() -> None:
    with open("f", "rb") as f:
        f.read()


def named() -> None:
    f = open("f", "rb")
    f.read(1)
    del f


def rebound() -> object:
    f: object = open("f", "rb")
    f = None
    return f


def at_return() -> bytes:
    f = open("f", "rb")
    return f.read(2)


def again() -> None:
    f = io.FileIO("f")
    f.__init__("f")  # type: ignore[misc]
    f.close()


def main() -> None:
    d = tempfile.mkdtemp()
    os.chdir(d)
    with open("f", "w", encoding="utf-8") as f:
        f.write("text\n")

    # which objects warn
    drop("text", lambda: open("f", encoding="utf-8"))
    drop("binary", lambda: open("f", "rb"))
    drop("raw", lambda: open("f", "rb", buffering=0))
    drop("write", lambda: open("g", "wb"))
    drop("random", lambda: open("g", "r+b"))
    drop("text write", lambda: open("g", "w", encoding="ascii"))
    drop("closed", lambda: open("f", "rb").close())
    drop("fd", lambda: open(os.open("f", os.O_RDONLY), "rb"))
    fd = os.open("f", os.O_RDONLY)
    drop("fd kept", lambda: open(fd, "rb", closefd=False))
    drop("fd kept raw", lambda: io.FileIO(fd, closefd=False))
    os.close(fd)
    drop("FileIO", lambda: io.FileIO("f"))
    drop("BufferedReader over FileIO", lambda: io.BufferedReader(io.FileIO("f")))
    drop("TextIOWrapper over BufferedReader", lambda: io.TextIOWrapper(io.BufferedReader(io.FileIO("f")), encoding="utf-8"))
    drop("BytesIO", lambda: io.BytesIO(b"x"))
    drop("StringIO", lambda: io.StringIO("x"))
    drop("TextIOWrapper over BytesIO", lambda: io.TextIOWrapper(io.BytesIO(b"x"), encoding="utf-8"))
    drop("BufferedReader over BytesIO", lambda: io.BufferedReader(io.BytesIO(b"x")))
    drop("detached", lambda: open("f", encoding="utf-8").detach())
    drop("detached raw", lambda: open("f", "rb").detach())
    drop("TemporaryFile", lambda: tempfile.TemporaryFile())
    drop("TemporaryFile text", lambda: tempfile.TemporaryFile("w+", encoding="utf-8"))

    # where it is charged
    drop("with", with_block)
    drop("del", named)
    drop("rebound", rebound)
    drop("at return", at_return)

    # what a subclass changes
    drop("subclass", lambda: Mine("f"))
    drop("close overridden", lambda: Closing("f"))
    drop("warn overridden", lambda: NoWarn("f"))
    drop("warn overridden under a buffer", lambda: io.BufferedReader(NoWarn("f")))
    drop("buffer subclass overriding", lambda: Quiet(io.FileIO("f")))
    drop("raw override raising, under a buffer", lambda: io.BufferedReader(Loud("f")))
    drop("raw override raising, under text", lambda: io.TextIOWrapper(io.BufferedReader(Loud("f")), encoding="utf-8"))
    drop("text subclass with the name", lambda: Text(io.BufferedReader(io.FileIO("f")), encoding="utf-8"))
    drop("text over an odd buffer", lambda: io.TextIOWrapper(Odd(), encoding="utf-8"))  # type: ignore[type-var]
    drop("text over a buffer without it", lambda: io.TextIOWrapper(Bare(), encoding="utf-8"))  # type: ignore[type-var]
    drop("repr raises", lambda: BadRepr("f"))

    # an open that fails after the file was opened closes it itself; one that never opened has nothing to close
    drop("open fails late", lambda: open("f", encoding="no-such-encoding"))
    drop("a directory", lambda: open(".", "rb"))
    drop("missing", lambda: open("missing", "rb"))
    drop("init again", again)

    # the warning made an error: reported as unraisable, about the raw file, and the file is closed all the same
    seen: list[tuple[str, str, str | None, object]] = []
    old = sys.unraisablehook
    sys.unraisablehook = lambda u: seen.append((u.exc_type.__name__, digits(str(u.exc_value)), u.err_msg, u.object))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        open("f", "rb", buffering=0)
        open("f", "rb")
        open("f", encoding="utf-8")
        BadRepr("f")
    drop("repr raises a warning", lambda: WarnRepr("f"))
    sys.unraisablehook = old
    for row in seen:
        print("unraisable:", row)

    # the filters: the default ones ignore it, yet the frame's registry is made; "default" shows a line once
    with warnings.catch_warnings(record=True) as caught:
        open("f", "rb")
    print("default filters:", len(caught), type(globals().get("__warningregistry__")).__name__)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("default")
        for _ in range(3):
            open("f", "rb")
        open("f", "rb")
    print("once a line:", len(caught), [w.lineno - caught[0].lineno for w in caught])
    with warnings.catch_warnings(record=True) as caught:
        warnings.filterwarnings("always", category=ResourceWarning, message="unclosed file <_io.Buffered")
        open("f", "rb")
        open("f", "rb", buffering=0)
        open("f", encoding="utf-8")
    print("by message:", [type(w.source).__name__ for w in caught])

    # the two methods and the flag
    print("has:", hasattr(io.FileIO, "_dealloc_warn"), hasattr(io.BufferedReader, "_dealloc_warn"), hasattr(io.BufferedWriter, "_dealloc_warn"), hasattr(io.BufferedRandom, "_dealloc_warn"),
          hasattr(io.TextIOWrapper, "_dealloc_warn"), hasattr(io.BufferedRWPair, "_dealloc_warn"), hasattr(io.BytesIO, "_dealloc_warn"), hasattr(io.StringIO, "_dealloc_warn"),
          hasattr(io.TextIOWrapper, "_finalizing"), hasattr(io.FileIO, "_finalizing"), hasattr(io.BufferedReader, "_finalizing"),
          type(io.FileIO.__dict__["_finalizing"]).__name__, type(io.FileIO.__dict__["_dealloc_warn"]).__name__, type(io.BufferedReader.__dict__["_dealloc_warn"]).__name__)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        raw = io.FileIO("f")
        print("called:", raw._dealloc_warn("anything"), raw._dealloc_warn(raw), raw._finalizing)  # type: ignore[attr-defined]
        raw.close()
        print("closed:", raw._dealloc_warn(raw))  # type: ignore[attr-defined]
        b = open("f", "rb")
        b._dealloc_warn(b)  # type: ignore[attr-defined]
        b.close()
        b._dealloc_warn(b)  # type: ignore[attr-defined]
        t = open("f", encoding="utf-8")
        t.buffer._dealloc_warn(t)  # type: ignore[attr-defined]
        t.close()
        flagged = io.FileIO("f")
        flagged._finalizing = True  # type: ignore[attr-defined]
        flagged.close()             # a close that believes it is the finalizer's
    print("asked:", [(str(w.message), type(w.source).__name__, w.lineno - caught[0].lineno) for w in caught])
    wrong: list[Callable[[], object]] = [lambda: io.FileIO("f")._dealloc_warn(), lambda: io.FileIO._dealloc_warn(1, 2), lambda: open("f", "rb")._dealloc_warn(1, 2)]  # type: ignore[attr-defined]
    for call in wrong:
        try:
            call()
        except Exception as e:
            print("  wrong call:", type(e).__name__)

    # the raw file's two closes, one failing after the other: the second error carries the first as its context
    failing = Failing("f")
    os.close(failing.fileno())
    try:
        failing.close()
    except Exception as e:
        print("both fail:", type(e).__name__, type(e.__context__).__name__, e.__suppress_context__, e.__cause__, failing.closed)
    failing = Failing("f")
    try:
        failing.close()
    except Exception as e:
        print("flush fails:", type(e).__name__, type(e.__context__).__name__, e.__suppress_context__, failing.closed)
    try:
        io.FileIO("f", opener=lambda path, flags: 9999)
    except Exception as e:
        print("init fails and its close fails:", type(e).__name__, type(e.__context__).__name__, e.__suppress_context__, e.__cause__)
    os.chdir("/")
    for name in os.listdir(d):
        os.unlink(os.path.join(d, name))
    os.rmdir(d)


if __name__ == "__main__":
    main()
