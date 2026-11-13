# clause: C-6-22
# spec: section 6 (Builtins: input), D-11 (breakpoint), section 7 (the sys surface: stdin, stdout, stderr)
# status: P1
# source: Python/bltinmodule.c (builtin_input_impl, builtin_breakpoint), Objects/fileobject.c (PyFile_GetLine, PyFile_WriteObject),
#         Python/sysmodule.c (sys_breakpointhook)
"""input() away from a terminal. It wants the three standard streams (one that is None or gone is lost), flushes
sys.stderr, asks sys.stdin for its descriptor (a stream without one is no terminal), writes str(prompt) to sys.stdout and
flushes it, and gives sys.stdin.readline() without its one trailing newline: a str or a bytes as the stream gave it, EOFError
for an empty one, TypeError for anything else. A flush that fails is passed over; a write that fails is not. breakpoint()
with PYTHONBREAKPOINT=0 does nothing."""
import io
import os
import sys
from collections.abc import Callable

LOG: list[str] = []


class Stream:
    """A stand-in for a standard stream that notes what input() asks of it."""

    def __init__(self, name: str, lines: list[object] | None = None, fd: object = None, broken: tuple[str, ...] = ()) -> None:
        self.name = name
        self.lines = lines if lines is not None else []
        self.fd = fd
        self.broken = broken

    def flush(self) -> None:
        LOG.append(self.name + ".flush")
        if "flush" in self.broken:
            raise OSError("the flush failed")

    def fileno(self) -> object:
        LOG.append(self.name + ".fileno")
        if self.fd is None:
            raise io.UnsupportedOperation("fileno")
        return self.fd

    def write(self, text: str) -> int:
        LOG.append(self.name + ".write " + ascii(text))
        if "write" in self.broken:
            raise OSError("the write failed")
        return len(text)

    def readline(self, *args: object) -> object:
        LOG.append(self.name + ".readline" + ascii(args))
        return self.lines.pop(0) if self.lines else ""


class Bare:
    """A stream with nothing input() asks for but a flush."""

    def flush(self) -> None:
        LOG.append("bare.flush")


class Unprintable:
    def __str__(self) -> str:
        raise ZeroDivisionError


def attempt(thunk: Callable[[], object]) -> str:
    try:
        result = thunk()
    except Exception as exc:  # noqa: BLE001  # which exception, by class
        return type(exc).__name__
    return ascii(result)


def ask(prompt: tuple[object, ...], fin: object, fout: object = None, ferr: object = None) -> tuple[str, list[str]]:
    """input(*prompt) with the three streams replaced; the result or the exception's class, and what was asked of them."""
    LOG.clear()
    kept = sys.stdin, sys.stdout, sys.stderr
    sys.stdin, sys.stdout, sys.stderr = fin, fout if fout is not None else Stream("out"), ferr if ferr is not None else Stream("err")
    try:
        result = attempt(lambda: input(*prompt))
    finally:
        sys.stdin, sys.stdout, sys.stderr = kept
    return result, list(LOG)


print("a line:", ask((), Stream("in", ["a line\n"])))
print("a prompt:", ask(("prompt> ",), Stream("in", ["a line\n", "the next\n"])))
print("a prompt that is no str:", ask((5,), Stream("in", ["no newline"])), ask((None,), Stream("in", ["\n"]))[0], ask((b"b",), Stream("in", ["x\n"]))[1][2])
print("one newline only:", ask((), Stream("in", ["two\n\n"]))[0], ask((), Stream("in", ["cr\r\n"]))[0], ask((), Stream("in", ["\n\n"]))[0], ask((), Stream("in", ["\r"]))[0])
print("the end:", ask((), Stream("in", []))[0], ask((), Stream("in", [""]))[0], ask((), Stream("in", [b""]))[0])
print("bytes:", ask((), Stream("in", [b"bytes\n"]))[0], ask((), Stream("in", [b"x"]))[0], ask((), Stream("in", [b"\n\n"]))[0])
print("neither:", ask((), Stream("in", [5]))[0], ask((), Stream("in", [None]))[0], ask((), Stream("in", [bytearray(b"x\n")]))[0], ask((), Stream("in", [["x"]]))[0])
print("a descriptor that is no terminal:", ask(("p",), Stream("in", ["x\n"], fd=7)), ask(("p",), Stream("in", ["x\n"], fd=-1))[0])
print("a descriptor that is no int:", ask(("p",), Stream("in", ["x\n"], fd="zero")), ask(("p",), Stream("in", ["x\n"], fd=2 ** 70))[0], ask(("p",), Stream("in", ["x\n"], fd=1.5))[0])
print("nothing to read with:", ask(("p",), Bare()))
print("nothing to write with:", ask(("p",), Stream("in", ["x\n"]), Bare()), ask((), Stream("in", ["x\n"]), Bare()))
print("a write that fails:", ask(("p",), Stream("in", ["x\n"]), Stream("out", broken=("write",))))
print("a prompt that cannot be shown:", ask((Unprintable(),), Stream("in", ["x\n"])))
print("a flush that fails:", ask((), Stream("in", ["x\n"]), Stream("out", broken=("flush",)), Stream("err", broken=("flush",))))
for lost in ("stdin", "stdout", "stderr"):
    stream = getattr(sys, lost)
    setattr(sys, lost, None)
    try:
        as_none = attempt(input)
    finally:
        setattr(sys, lost, stream)
    delattr(sys, lost)
    try:
        gone = attempt(input)
    finally:
        setattr(sys, lost, stream)
    print("lost:", lost, as_none, gone)
print("arguments:", attempt(lambda: input(prompt="x")), attempt(lambda: input("a", "b")), type(input).__name__, input.__name__, input.__module__)  # type: ignore[call-arg]
real = sys.stdin
sys.stdin = io.StringIO("first\nsecond\n\nlast")
print("from a StringIO:", ascii(input()), ascii(input("? ")), ascii(input()), ascii(input()), attempt(input))
sys.stdin = io.BytesIO(b"bytes one\nbytes two")
print("from a BytesIO:", ascii(input()), ascii(input()), attempt(input))
sys.stdin = io.TextIOWrapper(io.BytesIO("zażółć\r\nx\ry\n".encode()), encoding="utf-8", newline="")
print("from a text file:", ascii(input()), ascii(input()), attempt(input))
sys.stdin = real
os.environ["PYTHONBREAKPOINT"] = "0"
print("breakpoint, switched off:", breakpoint(), breakpoint(1, 2, key=3), type(breakpoint).__name__)  # type: ignore[func-returns-value]
