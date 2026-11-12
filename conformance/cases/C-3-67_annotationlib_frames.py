# clause: C-3-67
# spec: section 3
# status: P1
# source: Gate 1c: compiled tracebacks through annotationlib showed the shim's line numbers (C-3-65)
"""A traceback through annotationlib has CPython's line numbers in each of its frames: a function's
and a class's annotation naming an unbound name raise NameError from get_annotations and from
call_annotate_function in the VALUE format, and a ForwardRef to an unbound name raises it from
evaluate. An annotate function a program writes itself that supports VALUE only is answered in
the FORWARDREF format by calling it with VALUE, as CPython does once its re-run raises
NotImplementedError, with a closure or without one (get_annotations reads __annotations__ first,
which calls it with VALUE); an error raised by that call has CPython's frames and the
NotImplementedError as its context."""
import annotationlib
from collections.abc import Callable
from types import TracebackType

F = annotationlib.Format


def lines(tb: TracebackType | None) -> list[int]:
    out: list[int] = []
    while tb is not None:
        out.append(tb.tb_lineno)
        tb = tb.tb_next
    return out


def report(label: str, thunk: Callable[[], object]) -> None:
    try:
        result = thunk()
    except Exception as exc:  # noqa: BLE001  # which exception, and the lines of its frames
        context = exc.__context__
        print(label, type(exc).__name__, lines(exc.__traceback__), type(context).__name__ if context is not None else None)
    else:
        print(label, result)


def unbound(x: Undefined) -> None:  # type: ignore[name-defined]  # noqa: F821  # unbound on purpose
    pass


class Unbound:
    y: Undefined2  # type: ignore[name-defined]  # noqa: F821  # unbound on purpose


report("function VALUE", lambda: annotationlib.get_annotations(unbound))
report("class VALUE", lambda: annotationlib.get_annotations(Unbound))
report("call_annotate_function", lambda: annotationlib.call_annotate_function(unbound.__annotate__, F.VALUE))  # type: ignore[arg-type]  # a function's __annotate__ is set
report("function FORWARDREF", lambda: {k: (type(v).__name__, getattr(v, "__forward_arg__", v))
                                       for k, v in annotationlib.get_annotations(unbound, format=F.FORWARDREF).items()})
report("ForwardRef.evaluate", lambda: annotationlib.ForwardRef("Undefined3").evaluate())


def value_only(fail: bool) -> Callable[[int], dict[str, object]]:
    tag = "closed over"

    def annotate(format: int) -> dict[str, object]:
        if format != 1:
            raise NotImplementedError
        if fail:
            raise LookupError(tag)
        return {"x": int, "tag": tag}
    return annotate


def plain(format: int) -> dict[str, object]:
    if format != 1:
        raise NotImplementedError
    return {"y": str}


class Closed:
    pass


class Plain:
    pass


class Failing:
    pass


closed = value_only(False)
Closed.__annotate__ = closed  # a class's __annotate__ set by hand
Plain.__annotate__ = plain
Failing.__annotate__ = value_only(True)
# get_annotations takes __annotations__ first when VALUE works; call_annotate_function goes to the re-run
report("hand-written with a closure", lambda: annotationlib.call_annotate_function(closed, F.FORWARDREF))
report("hand-written without one", lambda: annotationlib.call_annotate_function(plain, F.FORWARDREF))
report("hand-written by get_annotations", lambda: annotationlib.get_annotations(Plain, format=F.FORWARDREF))
report("hand-written VALUE raising", lambda: annotationlib.get_annotations(Failing, format=F.FORWARDREF))
report("hand-written VALUE", lambda: annotationlib.get_annotations(Plain))
