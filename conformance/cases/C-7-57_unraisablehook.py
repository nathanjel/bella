# clause: C-7-57
# spec: section 9
# status: P1
# source: dialect specification section 9 (finalisers), Python/errors.c (PyErr_FormatUnraisable, the default hook), Python/sysmodule.c (sys.unraisablehook)
"""An exception nothing can propagate goes to sys.unraisablehook as an UnraisableHookArgs (the class, the exception, its
traceback, the message and an object): raised by a finaliser, a weak reference's callback, a generator closed with its last
reference, a file's finaliser, or a handler of atexit. The program's hook is called with it; the built-in hook writes the
message and CPython's report to sys.stderr, and takes nothing but that type. A hook that raises, exits or cannot be called is
itself reported, with the hook as the object and its own exception; with None for a hook, or none at all, the built-in one runs."""
# ruff: noqa: E501
import atexit
import io
import sys
import weakref
from collections.abc import Callable, Iterator
from types import TracebackType


class Named:
    """A callable whose repr holds no address; it raises what its name says."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        if self.name == "bad repr":
            raise RuntimeError("no repr")
        return "<Named " + self.name + ">"

    def __call__(self, *args: object) -> None:
        if self.name == "exits":
            sys.exit(9)
        raise ValueError("from " + self.name)


class Finalised:
    def __del__(self) -> None:
        raise KeyError("from a finaliser")


class Referent:
    pass


class File(io.RawIOBase):
    def __repr__(self) -> str:
        return "<File>"

    def close(self) -> None:
        raise OSError("close fails")


def m(f: Callable[[], object]) -> str:
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


def entries(tb: TracebackType | None) -> list[int]:
    """The lines of a traceback's entries, outermost first."""
    lines = []
    while tb is not None:
        lines.append(tb.tb_lineno)
        tb = tb.tb_next
    return lines


def hook(u: sys.UnraisableHookArgs) -> None:
    message = u.err_msg.split(" at 0x")[0] if u.err_msg is not None else None
    print("hook:", type(u).__name__, u.exc_type.__name__, repr(u.exc_value), entries(u.exc_traceback), message, u.object, len(u), u[1] is u.exc_value,  # type: ignore[arg-type,index]
          u.exc_value is not None and u.exc_value.__traceback__ is u.exc_traceback)


def closing() -> Iterator[int]:
    try:
        yield 1
    finally:
        raise RuntimeError("from a generator's close")


def trigger(name: str) -> None:
    """One ignored exception whose report holds no address: a weak reference's callback."""
    referent = Referent()
    reference = weakref.ref(referent, Named(name))
    del referent
    del reference


print("the hook:", sys.unraisablehook is sys.__unraisablehook__, type(sys.unraisablehook).__name__, sys.unraisablehook.__name__, sys.unraisablehook.__module__, repr(sys.unraisablehook.__doc__)[:40])
default = sys.__unraisablehook__
sys.unraisablehook = hook

# what is reported, and with what
finalised = Finalised()
del finalised
trigger("a weak reference's callback")
generator = closing()
next(generator)
del generator
file = File()
del file
referent = Referent()
reference = weakref.ref(referent, int)  # type: ignore[arg-type]  # a callback that raises with no frame of its own
del referent
atexit.register(Named("a handler of atexit"))

# the argument's type
kept: list[sys.UnraisableHookArgs] = []
sys.unraisablehook = kept.append
trigger("kept")
sys.unraisablehook = hook
args = kept[0]
Args = type(args)
print("type:", Args.__name__, Args.__qualname__, Args.__module__, repr(Args.__doc__), Args.__mro__ == (Args, tuple, object), Args.n_fields, Args.n_sequence_fields, Args.n_unnamed_fields,  # type: ignore[attr-defined]
      [n for n in ("exc_type", "exc_value", "exc_traceback", "err_msg", "object") if type(Args.__dict__[n]).__name__ == "member_descriptor"])
print("made:", m(lambda: Args((1, 2, 3, 4, 5))), m(lambda: Args((1, 2))), m(lambda: Args()), m(lambda: Args((1, 2, 3, 4, 5, 6))), m(lambda: type("S", (Args,), {})),  # type: ignore[call-arg]
      args.err_msg, args.object, args.exc_type is ValueError, args[3] is args.err_msg, args == tuple(args), m(lambda: args._replace), args.__reduce__()[0] is Args)  # type: ignore[arg-type,attr-defined,index]

# the built-in hook, by hand: the message and the object make the first line, then the report of the exception
print("-- by hand", file=sys.stderr)
for made in (Args((ValueError, ValueError("a message alone"), None, "A message", None)),  # type: ignore[call-arg]
             Args((ValueError, ValueError("an object alone"), None, None, Named("object"))),  # type: ignore[call-arg]
             Args((ValueError, ValueError("a message and an object"), None, "A message", Named("object"))),  # type: ignore[call-arg]
             Args((ValueError, ValueError("neither"), None, None, None)),  # type: ignore[call-arg]
             Args((ValueError, ValueError("an object whose repr raises"), None, None, Named("bad repr"))),  # type: ignore[call-arg]
             Args((ValueError, None, None, "No exception", None)),  # type: ignore[call-arg]
             Args((None, None, None, None, None)),  # type: ignore[call-arg]
             Args((ValueError, "a value that is no exception", None, "Its text", None)),  # type: ignore[call-arg]
             args):
    print(m(lambda: default(made)), file=sys.stderr)  # noqa: B023
print("arguments:", m(lambda: default(1)), m(lambda: default()), m(lambda: default(args, args)), m(lambda: default(unraisable=args)), m(lambda: default((ValueError, ValueError(), None, None, None))))  # type: ignore[arg-type,call-arg]

# a hook that fails is reported itself; no hook, or None, is the built-in one
for label, installed in (("raises", Named("the hook")), ("exits", Named("exits")), ("cannot be called", 3), ("is None", None), ("is the built-in one again", default)):
    print("-- a hook that", label, file=sys.stderr)
    sys.unraisablehook = installed  # type: ignore[assignment]
    trigger("the callback, under a hook that " + label)
print("-- no hook", file=sys.stderr)
del sys.unraisablehook
trigger("the callback, with no hook")
print("-- no sys.stderr", file=sys.stderr)
sys.unraisablehook = default
stderr, sys.stderr = sys.stderr, None
trigger("the callback, with no stream")
sys.stderr = stderr
sys.unraisablehook = hook
print("end of module")
