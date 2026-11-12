# clause: C-8-12
# spec: section 8 (an uncaught exception's report), D-06
# status: P1
# source: Lib/traceback.py (TracebackException: the queue that builds the chains and the groups, format with
#         _ExceptionPrintContext, format_exception_only with __notes__), Python/pythonrun.c (_PyErr_Display), CPython 3.15.2
"""The report of an exception group and of notes (PEP 654, PEP 678), as the built-in hook writes it on standard error: the
boxes and margins of a group, each part's own traceback and chain, the fifteen parts and ten levels shown, a group that was
never raised, the same part twice, and notes that are strings, lines, other objects, a __notes__ that is no sequence and a
note whose str() fails. The program then ends with an uncaught group whose part has a cause."""
import sys


def raised[E: BaseException](e: E) -> E:
    try:
        raise e
    except BaseException:
        return e


def caused() -> Exception:
    try:
        try:
            raise KeyError("inner")
        except KeyError as k:
            raise ValueError("outer") from k
    except ValueError as v:
        return v


def in_context() -> Exception:
    try:
        try:
            raise OSError("first")
        except OSError:
            raise TypeError("second")  # noqa: B904
    except TypeError as t:
        return t


def report(e: BaseException) -> None:
    sys.__excepthook__(type(e), e, e.__traceback__)
    print("reported", type(e).__name__)


report(raised(ExceptionGroup("flat", [raised(ValueError(1)), raised(TypeError(2))])))
report(raised(ExceptionGroup("nested", [raised(ExceptionGroup("inner", [caused(), in_context()])), raised(OSError(3))])))
report(ExceptionGroup("never raised", [ValueError(1), KeyError(2)]))
wide = raised(ExceptionGroup("wide", [ValueError(i) for i in range(17)]))
report(wide)
deep: Exception = ValueError("bottom")
for level in range(12):
    deep = ExceptionGroup(f"level {level}", [deep])
report(raised(deep))
twice = raised(ValueError("twice"))
report(raised(ExceptionGroup("the same part twice", [twice, twice])))


class Unprintable:
    def __str__(self) -> str:
        raise RuntimeError("no")


noted = raised(ValueError("noted"))
noted.add_note("a note")
noted.add_note("a note\nof two lines")
noted.__notes__.append(42)  # type: ignore[arg-type]
noted.__notes__.append(Unprintable())  # type: ignore[arg-type]
report(noted)
odd = raised(KeyError("odd notes"))
odd.__notes__ = 5  # type: ignore[assignment]
report(odd)
group_noted = raised(ExceptionGroup("noted group", [noted, raised(OSError(4))]))
group_noted.add_note("the group's note")
report(group_noted)
base = raised(BaseExceptionGroup("base", [raised(KeyboardInterrupt()), raised(ValueError(5))]))
report(base)
raise ExceptionGroup("uncaught", [caused(), raised(KeyError("k"))])
