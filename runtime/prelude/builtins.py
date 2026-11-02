"""Built-in functions written in Python (docs/DECISIONS.md, step 3 of the C++ leg).

Bella compiles this module into every program and puts the names in __all__ into the builtins.
CPython runs it in runtime/tests/test_prelude.py against the builtins it stands for, so each
function is checked against CPython directly, before Bella compiles it.
"""
import sys

__all__ = ["print"]


def print(*args: object, sep: object = " ", end: object = "\n", file: object = None, flush: object = False) -> None:
    """print(*args, sep=' ', end='\\n', file=None, flush=False), in builtin_print_impl's order:
    the file first (nothing at all when sys.stdout is None), then sep and end, each str(), then
    flush."""
    if file is None:
        file = sys.stdout
        if file is None:
            return
    if sep is None:
        sep = " "
    elif not isinstance(sep, str):
        raise TypeError("sep must be None or a string, not " + type(sep).__name__)
    if end is None:
        end = "\n"
    elif not isinstance(end, str):
        raise TypeError("end must be None or a string, not " + type(end).__name__)
    first = True
    for arg in args:
        if not first:
            file.write(str(sep))  # type: ignore[attr-defined]  # any object with write()
        first = False
        file.write(str(arg))  # type: ignore[attr-defined]
    file.write(str(end))  # type: ignore[attr-defined]
    if flush:
        file.flush()  # type: ignore[attr-defined]
