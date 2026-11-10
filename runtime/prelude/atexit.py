"""atexit, in Python (Modules/atexitmodule.c): the list of (function, arguments, keywords) the interpreter state holds, newest
first; register and unregister with the C's own parsing and messages, unregister's walk from the oldest registration on with
PyObject_RichCompareBool (identity, then `func == registered`) and its search for the entry again after a comparison that may
have changed the list; _clear, _ncallbacks and _run_exitfuncs. The runtime calls _atexit_call at the end of the program
(Python/pylifecycle.c, make_pre_finalization_calls), after threading._shutdown and before the standard streams are flushed.
The functions' docstrings are the names table's rows, as every built-in function's."""

__all__ = ["_clear", "_ncallbacks", "_run_exitfuncs", "register", "unregister"]
__intrinsics__ = ["_atexit_call"]               # _PyAtExit_Call, the runtime's at the end of the program

__name__ = "atexit"

try:
    _unraisable                                  # noqa: B018  # PyErr_FormatUnraisable: a message (None if it did not format) and the exception
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _unraisable: Callable[..., Any] = _missing

# struct atexit_state's callbacks: the interpreter's, so it outlives the module's entry in sys.modules
_callbacks: list[tuple[object, tuple[object, ...], dict[str, object] | None]] = []


def _noargs(qualname: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:   # METH_NOARGS
    if kwds:
        raise TypeError(qualname + "() takes no keyword arguments")
    if args:
        raise TypeError(qualname + "() takes no arguments (" + str(len(args)) + " given)")


def _atexit_call() -> None:                      # atexit_callfuncs: over a copy, and whatever was registered meanwhile goes unrun
    copy = list(_callbacks)
    for func, args, kwargs in copy:
        try:
            if kwargs is None:
                func(*args)  # type: ignore[operator]
            else:
                func(*args, **kwargs)  # type: ignore[operator]
        except BaseException as e:  # noqa: BLE001  # PyErr_FormatUnraisable takes whatever is set: SystemExit and KeyboardInterrupt too
            try:
                message: str | None = "Exception ignored in atexit callback " + repr(func)
            except BaseException:  # noqa: BLE001  # PyUnicode_FromFormatV failed on %R: PyErr_Clear, and the report has no first line
                message = None
            _unraisable(message, e)
    _callbacks.clear()


def register(*args: object, **kwargs: object) -> object:
    if len(args) == 0:
        raise TypeError("register() takes at least 1 argument (0 given)")
    func = args[0]
    if not callable(func):
        raise TypeError("the first argument must be callable")
    _callbacks.insert(0, (func, args[1:], kwargs if kwargs else None))   # atexit callbacks go in a LIFO order
    return func


def unregister(*args: object, **kwds: object) -> None:   # METH_O
    if kwds:
        raise TypeError("atexit.unregister() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("atexit.unregister() takes exactly one argument (" + str(len(args)) + " given)")
    func = args[0]
    i = len(_callbacks) - 1
    while i >= 0:                                # atexit_unregister_locked
        entry = _callbacks[i]
        registered = entry[0]
        if func is registered or func == registered:   # PyObject_RichCompareBool(func, to_compare, Py_EQ)
            # found; but its index could have changed if it or other callbacks were unregistered during the comparison
            j = min(len(_callbacks) - 1, i)
            while j >= 0:
                if _callbacks[j] is entry:
                    del _callbacks[j]
                    i = j
                    break
                j -= 1
        if i >= len(_callbacks):                 # as the C: i is clamped to the list after the entry's turn
            i = len(_callbacks)
        i -= 1


def _run_exitfuncs(*args: object, **kwds: object) -> None:
    _noargs("atexit._run_exitfuncs", args, kwds)
    _atexit_call()


def _clear(*args: object, **kwds: object) -> None:
    _noargs("atexit._clear", args, kwds)
    _callbacks.clear()


def _ncallbacks(*args: object, **kwds: object) -> int:
    _noargs("atexit._ncallbacks", args, kwds)
    return len(_callbacks)
