# clause: C-7-56
# spec: section 2
# status: P1
# source: dialect specification section 2 (entry and exit: an uncaught exception), Python/pythonrun.c (_PyErr_PrintEx), Python/sysmodule.c (sys.excepthook)
"""An uncaught exception goes to sys.excepthook. The program's own hook is called once, with the class, the exception and its
traceback, after sys.last_exc and the three older names were set; nothing else is written, and the exit status is 1. The
built-in hook, which the program's calls by hand here, writes CPython's report of whatever it is given. atexit's handlers run
after the hook and still read sys.last_exc."""
# ruff: noqa: E501
import atexit
import sys
from types import TracebackType


class Refused(Exception):
    pass


def entries(tb: TracebackType | None) -> list[int]:
    """The lines of a traceback's entries, outermost first."""
    lines = []
    while tb is not None:
        lines.append(tb.tb_lineno)
        tb = tb.tb_next
    return lines


def hook(kind: type[BaseException], value: BaseException, tb: TracebackType | None) -> None:
    print("hook:", kind.__name__, repr(value), entries(tb), repr(value.__cause__), value.__traceback__ is tb)
    print("last:", sys.last_exc is value, sys.last_type is kind, sys.last_value is value, sys.last_traceback is tb)
    print("the built-in hook, by hand:", file=sys.stderr)
    sys.__excepthook__(kind, value, tb)
    print("and of an exception that was never raised:", file=sys.stderr)
    sys.__excepthook__(KeyError, KeyError("never raised"), None)


def at_exit() -> None:
    print("at exit:", repr(sys.last_exc), entries(sys.last_traceback), sys.excepthook is hook)


def inner(n: int) -> None:
    try:
        raise ValueError("the cause")
    except ValueError as e:
        raise Refused("uncaught", n) from e


def outer() -> None:
    inner(3)


print("before:", sys.excepthook is sys.__excepthook__, type(sys.excepthook).__name__, sys.excepthook.__name__, sys.excepthook.__module__,
      [hasattr(sys, n) for n in ("last_exc", "last_type", "last_value", "last_traceback")])
sys.excepthook = hook
atexit.register(at_exit)
outer()
print("not reached")
