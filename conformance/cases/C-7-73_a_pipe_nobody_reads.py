# clause: C-7-73
# spec: section 7
# status: P1
# source: dialect specification sections 3 and 7 (process and signals), Python/pylifecycle.c (signal_install_handlers: SIGPIPE and SIGXFSZ are ignored when the interpreter starts), Modules/posixmodule.c (os_write_impl), Modules/_io/fileio.c, Modules/_io/bufferedio.c
"""A pipe nobody reads. CPython ignores SIGPIPE when it starts, so writing to such a pipe is an error the program can catch,
BrokenPipeError, and not the end of the process: through os.write, through a raw file, through a buffered one (where the
error comes when the buffer is written out, and again when the file is closed), and through a text file."""
# ruff: noqa: E501, PTH, SIM115
import os
from collections.abc import Callable


def m(f: Callable[[], object]) -> str:
    try:
        return repr(f())
    except OSError as e:
        return type(e).__name__ + ": " + repr((e.errno, e.strerror, e.filename))
    except Exception as e:
        return type(e).__name__


def broken() -> int:
    """The writing end of a pipe whose reading end is closed."""
    r, w = os.pipe()
    os.close(r)
    return w


def main() -> None:
    w = broken()
    print("os.write:", m(lambda: os.write(w, b"x")), m(lambda: os.write(w, b"")), m(lambda: os.writev(w, [b"a", b"b"])), issubclass(BrokenPipeError, ConnectionError), BrokenPipeError.__mro__[1:4] == (ConnectionError, OSError, Exception))
    os.close(w)

    raw = open(broken(), "wb", buffering=0)
    print("a raw file:", m(lambda: raw.write(b"x")), m(lambda: raw.write(b"")), raw.closed, m(raw.close), raw.closed)

    buffered = open(broken(), "wb")
    print("a buffered file:", buffered.write(b"kept in the buffer"), m(buffered.flush), m(buffered.flush), buffered.closed, m(buffered.close), buffered.closed, m(buffered.close))

    text = open(broken(), "w", encoding="utf-8")
    print("a text file:", text.write("kept"), m(text.flush), text.closed, m(text.close), text.closed)

    lines = open(broken(), "w", encoding="utf-8", buffering=1)
    print("a line-buffered text file:", m(lambda: lines.write("no newline")), m(lambda: lines.write(" and one\n")), m(lines.close), lines.closed)

    # the pipe was whole when the write began: what was written is counted, and the error comes with the next write
    r, w2 = os.pipe()
    print("a reader that leaves:", os.write(w2, b"taken"), os.read(r, 100), os.close(r), m(lambda: os.write(w2, b"lost")))  # type: ignore[func-returns-value]
    os.close(w2)
    print("still here")


if __name__ == "__main__":
    main()
