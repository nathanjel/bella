"""The exit's reporter (C-9-13): a finaliser that says where in the exit it runs, through what it holds alone (`os.write`,
the namespace it was given, `sys` and the builtins' namespace), since by the end the program's names, the builtins and `sys`
are cleared. Its line has no builtin in it: `str.format` and `!=` are no builtins."""
import builtins
import os
import sys
import types
from collections.abc import Callable

Namespace = dict[str, object] | None


def report(tag: str, g: Namespace, w: Callable[[int, bytes], int] = os.write, s: types.ModuleType = sys,
           b: dict[str, object] = builtins.__dict__) -> None:
    modules: object = s.__dict__.get("modules")
    line = "  {}: LABEL={!r} modules={!r} open={!r} print={!r} stdout={!r}\n".format(
        tag, None if g is None else g.get("LABEL"), modules is not None and modules != {}, b.get("open") is not None,
        b.get("print") is not None, s.__dict__.get("stdout") is not None)
    w(1, line.encode())


class C:
    def __init__(self, tag: str, g: Namespace) -> None:
        self.tag = tag
        self.g = g

    def __del__(self, r: Callable[[str, Namespace], None] = report) -> None:
        r(self.tag, self.g)


class Callback:
    """A weak reference's callback that reaches no namespace of the program's."""

    def __init__(self, tag: str) -> None:
        self.tag = tag

    def __call__(self, ref: object, w: Callable[[int, bytes], int] = os.write) -> None:
        w(1, f"  {self.tag}: called\n".encode())
