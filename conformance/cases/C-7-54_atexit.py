# clause: C-7-54
# spec: section 7
# status: P1
# source: dialect specification sections 2 and 7 (atexit handlers run last, in LIFO order), Modules/atexitmodule.c, Python/pylifecycle.c
"""atexit: the module's five functions and their parsing, registration with arguments and keywords (the function is returned),
unregister by equality from the newest registration back (identity first, then `func == registered`, whatever the comparison
does to the list), _ncallbacks, _clear and _run_exitfuncs; at exit the handlers run newest first over a copy of the list, before
standard output is flushed and the module's globals go; a handler that raises (SystemExit and KeyboardInterrupt too) is reported
as ignored and the rest run; a registration made by a handler is dropped; the program's exit status stays its own."""
# ruff: noqa: E501, PLW1641, SLF001
import atexit
import sys
from collections.abc import Callable


def m(f: Callable[[], object]) -> str:
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


class Named:
    """A callable whose repr holds no address, and whose equality says what it is asked."""

    def __init__(self, name: str, equal: bool | str = False) -> None:
        self.name = name
        self.equal = equal

    def __repr__(self) -> str:
        return "<Named " + self.name + ">"

    def __eq__(self, other: object) -> bool:
        print("  eq", self.name, getattr(other, "name", getattr(other, "__name__", "?")))
        if self.equal == "raise":
            raise RuntimeError("eq raises")
        if self.equal == "clear":
            atexit._clear()
            return True
        if self.equal == "register":
            atexit.register(Named("during"))
            return True
        return self.equal is True

    def __call__(self, *args: object, **kwargs: object) -> None:
        print("call", self.name, args, sorted(kwargs.items()), atexit._ncallbacks())
        if self.name == "boom":
            raise ValueError("boom")
        if self.name == "exit":
            sys.exit(7)
        if self.name == "interrupt":
            raise KeyboardInterrupt
        if self.name == "own":
            raise Own("an exception of the program's") from KeyError("its cause")
        if self.name == "registers":
            print("  registered by a handler:", atexit.register(Named("late")) is not None, atexit._ncallbacks())
        if self.name == "unregisters":
            atexit.unregister(first)
            print("  unregistered by a handler:", atexit._ncallbacks())
        if self.name == "clears":
            atexit._clear()
            print("  cleared by a handler:", atexit._ncallbacks())


class Own(Exception):
    pass


class BadRepr:
    def __repr__(self) -> str:
        raise RuntimeError("no repr")

    def __call__(self) -> None:
        raise ValueError("from a handler with no repr")


class Kept:
    def __del__(self) -> None:
        print("a finaliser, after the handlers:", LABEL)


class Holder:
    def method(self, *args: object) -> None:
        print("a bound method", args, LABEL, len(sys.modules) > 3, sys.stdout is not None)


def plain(*args: object, **kwargs: object) -> None:
    print("plain", args, sorted(kwargs.items()))


LABEL: str = "a global of the module"
kept: Kept = Kept()

print("module:", [(n, type(getattr(atexit, n)).__name__) for n in sorted(dir(atexit))], repr(atexit.__doc__), atexit.__name__, atexit.__spec__.origin, atexit.__loader__.__name__, hasattr(atexit, "__file__"))  # type: ignore[union-attr]
print("functions:", [(f.__name__, f.__qualname__, f.__module__, f.__self__ is atexit, repr(f.__doc__)) for f in (atexit.register, atexit.unregister, atexit._clear, atexit._run_exitfuncs, atexit._ncallbacks)])  # type: ignore[union-attr]
print("arguments:", m(lambda: atexit.register()), m(lambda: atexit.register(3)), m(lambda: atexit.register(func=plain)), m(lambda: atexit.register(None, 1)), m(lambda: atexit.unregister()), m(lambda: atexit.unregister(plain, plain)), m(lambda: atexit.unregister(func=plain)), m(lambda: atexit._clear(1)), m(lambda: atexit._clear(x=1)), m(lambda: atexit._ncallbacks(1)), m(lambda: atexit._run_exitfuncs(1)), m(lambda: atexit._run_exitfuncs(x=1)), m(lambda: atexit.unregister(3)), m(lambda: atexit.unregister(None)), atexit._ncallbacks())  # type: ignore[arg-type,call-arg]

# registration: the function comes back, and the newest runs first
a: Named = Named("a", True)
b: Named = Named("b")
c: Named = Named("c", True)
print("register:", atexit.register(a) is a, atexit.register(b, 1, 2) is b, atexit.register(plain, 1) is plain, atexit.register(plain, 2, k=3) is plain, atexit.register(c, k=1) is c, atexit._ncallbacks())
print("run by hand:", atexit._run_exitfuncs(), atexit._ncallbacks())  # type: ignore[func-returns-value]

# unregister: from the oldest registration on, identity before equality, the argument on the left of ==
for f in (a, b, plain, plain, c):
    atexit.register(f)
print("unregister(plain):", atexit.unregister(plain), atexit._ncallbacks())  # type: ignore[func-returns-value]
print("unregister(probe):", atexit.unregister(Named("probe", True)), atexit._ncallbacks())  # type: ignore[func-returns-value]
atexit.register(a)
atexit.register(b)
print("unregister(b):", atexit.unregister(b), atexit._ncallbacks())  # type: ignore[func-returns-value]
print("unregister(raiser):", m(lambda: atexit.unregister(Named("raiser", "raise"))), atexit._ncallbacks())
for f in (plain, b, plain):
    atexit.register(f)
print("unregister(one that registers):", atexit.unregister(Named("registers", "register")), atexit._ncallbacks())  # type: ignore[func-returns-value]
print("unregister(one that clears):", atexit.unregister(Named("clears", "clear")), atexit._ncallbacks())  # type: ignore[func-returns-value]
atexit.register(plain, "to be cleared")
print("clear:", atexit._clear(), atexit._ncallbacks(), atexit._run_exitfuncs(), atexit._ncallbacks())  # type: ignore[func-returns-value]

# what runs at exit: every kind of callable, and what a handler does to the list while it runs
first: Named = Named("first")
atexit.register(first, 1, 2, k=3)
atexit.register(Named("boom"))
atexit.register(Named("exit"))
atexit.register(Named("registers"))
atexit.register(Named("unregisters"))
atexit.register(Named("clears"))
atexit.register(Named("interrupt"))
atexit.register(Named("own"))
atexit.register(BadRepr())
atexit.register(Holder().method, "with", "arguments")
atexit.register(print, "print, a built-in,", "with a keyword", sep=" | ")
atexit.register(sys.stdout.write, "sys.stdout.write, a method of the stream\n")


@atexit.register
def decorated() -> None:
    print("decorated: the newest, so the first")


print("decorated is still the function:", decorated.__name__, atexit._ncallbacks())
print("end of module")
sys.exit(3)
