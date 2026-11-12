"""gc, in Python (Modules/gcmodule.c and Modules/clinic/gcmodule.c.h): what a program asks of the collector, each function
parsing its arguments in the C's order and words, over one primitive, `_gc(name, ...)`, the runtime's collector state
(runtime/src/gc.cpp, the interpreter's GCState): whether automatic collection is on, the three thresholds, the debugging
flags, and the interpreter's two lists, `garbage` and `callbacks`, which the module only adds, as CPython's does, so they are
the same objects for the program's life. What needs the cycle collector stops by name, after its arguments are checked,
until the runtime has one (step 3c): collect, get_count, get_stats, is_tracked, is_finalized. get_objects, get_referrers,
get_referents, freeze, unfreeze and get_freeze_count read CPython's object graph, which a compiled program does not have
(E-05), and stop by name the same way. The functions' docstrings are the names table's rows, as every built-in function's."""

__all__ = ["enable", "disable", "isenabled", "set_debug", "get_debug", "get_count", "set_threshold", "get_threshold", "collect",
           "get_objects", "get_stats", "is_tracked", "is_finalized", "get_referrers", "get_referents", "freeze", "unfreeze",
           "get_freeze_count", "garbage", "callbacks", "DEBUG_STATS", "DEBUG_COLLECTABLE", "DEBUG_UNCOLLECTABLE", "DEBUG_SAVEALL",
           "DEBUG_LEAK"]                       # vars(gc)'s order on the pin

__name__ = "gc"

try:
    _gc                                          # noqa: B018  # the runtime's collector state, by name (runtime/src/gc.cpp)
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _number_index                                # noqa: B018  # PyNumber_Index, with its messages
    _unpack_keywords                             # noqa: B018  # _PyArg_UnpackKeywords
    _tp_name                                     # noqa: B018  # Py_TYPE(obj)->tp_name
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _gc: Callable[..., Any] = _missing
    _bella_refuse: Callable[..., Any] = _missing
    _number_index: Callable[..., int] = _missing
    _unpack_keywords: Callable[..., Any] = _missing
    _tp_name: Callable[..., str] = _missing

_ABSENT: object = object()
_NUM_GENERATIONS = 3
_INT_MIN, _INT_MAX = -2**31, 2**31 - 1
_LONG_MIN, _LONG_MAX = -2**63, 2**63 - 1
_SSIZE_MIN, _SSIZE_MAX = -2**63, 2**63 - 1

DEBUG_STATS = 1                                  # _PyGC_DEBUG_STATS ... (Include/internal/pycore_gc.h)
DEBUG_COLLECTABLE = 2
DEBUG_UNCOLLECTABLE = 4
DEBUG_SAVEALL = 32
DEBUG_LEAK = DEBUG_COLLECTABLE | DEBUG_UNCOLLECTABLE | DEBUG_SAVEALL

garbage = _gc("garbage")                         # gcstate->garbage, made with the interpreter
callbacks = _gc("callbacks")                     # gcstate->callbacks


def _noargs(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:   # METH_NOARGS
    if kwds:
        raise TypeError("gc." + name + "() takes no keyword arguments")
    if args:
        raise TypeError("gc." + name + "() takes no arguments (" + str(len(args)) + " given)")


def _one(name: str, args: tuple[object, ...], kwds: dict[str, object]) -> object:   # METH_O
    if kwds:
        raise TypeError("gc." + name + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("gc." + name + "() takes exactly one argument (" + str(len(args)) + " given)")
    return args[0]


def _as_int(value: object) -> int:               # PyLong_AsInt, as the clinic's int converter
    n = _number_index(value)
    if n < _INT_MIN or n > _INT_MAX:
        raise OverflowError("Python int too large to convert to C int")
    return n


def _parse_int(value: object) -> int:            # PyArg_ParseTuple's "i": PyLong_AsLong, then the int's range
    n = _number_index(value)
    if n < _LONG_MIN or n > _LONG_MAX:
        raise OverflowError("Python int too large to convert to C long")
    if n > _INT_MAX:
        raise OverflowError("signed integer is greater than maximum")
    if n < _INT_MIN:
        raise OverflowError("signed integer is less than minimum")
    return n


def _collector(what: str) -> None:               # what the cycle collector answers, which the runtime does not have yet
    _bella_refuse(what + " (the cycle collector: step 3c)")


def _object_graph(what: str) -> None:            # CPython's object graph, which a compiled program does not have
    _bella_refuse(what + " (CPython's object graph, E-05)")


def enable(*args: object, **kwds: object) -> None:   # gc_enable_impl: PyGC_Enable
    _noargs("enable", args, kwds)
    _gc("enable")


def disable(*args: object, **kwds: object) -> None:   # gc_disable_impl: PyGC_Disable
    _noargs("disable", args, kwds)
    _gc("disable")


def isenabled(*args: object, **kwds: object) -> bool:   # gc_isenabled_impl: PyGC_IsEnabled
    _noargs("isenabled", args, kwds)
    return _gc("isenabled")  # type: ignore[no-any-return]


def set_debug(*args: object, **kwds: object) -> None:   # gc_set_debug_impl
    _gc("set_debug", _as_int(_one("set_debug", args, kwds)))


def get_debug(*args: object, **kwds: object) -> int:   # gc_get_debug_impl
    _noargs("get_debug", args, kwds)
    return _gc("get_debug")  # type: ignore[no-any-return]


def get_count(*args: object, **kwds: object) -> tuple[int, int, int]:   # gc_get_count_impl: the generations' counts
    _noargs("get_count", args, kwds)
    _collector("gc.get_count")
    raise AssertionError("unreachable")


def set_threshold(*args: object, **kwds: object) -> None:   # gc_set_threshold: METH_VARARGS, one to three, all parsed first
    if kwds:
        raise TypeError("set_threshold() takes no keyword arguments")
    if not 1 <= len(args) <= 3:
        raise TypeError("gc.set_threshold requires 1 to 3 arguments")
    values = [_parse_int(a) for a in args]
    for generation, value in enumerate(values):
        _gc("set_threshold", generation, value)


def get_threshold(*args: object, **kwds: object) -> tuple[int, int, int]:   # gc_get_threshold_impl
    _noargs("get_threshold", args, kwds)
    return _gc("get_threshold")  # type: ignore[no-any-return]


def collect(*args: object, **kwds: object) -> int:   # gc_collect_impl: collect(generation=2)
    (given,) = _unpack_keywords("collect", ("generation",), 0, 0, 1, 0, args, kwds, _ABSENT)
    generation = _NUM_GENERATIONS - 1 if given is _ABSENT else _as_int(given)
    if generation < 0 or generation >= _NUM_GENERATIONS:
        raise ValueError("invalid generation")
    _collector("gc.collect")
    raise AssertionError("unreachable")


def get_objects(*args: object, **kwds: object) -> list[object]:   # gc_get_objects_impl: get_objects(generation=None)
    (given,) = _unpack_keywords("get_objects", ("generation",), 0, 0, 1, 0, args, kwds, _ABSENT)
    generation = -1
    if given is not _ABSENT and given is not None:   # _Py_convert_optional_to_ssize_t
        if not hasattr(type(given), "__index__"):
            raise TypeError("argument should be integer or None, not '" + _tp_name(given) + "'")
        generation = _number_index(given)
        if generation < _SSIZE_MIN or generation > _SSIZE_MAX:
            raise OverflowError("cannot fit '" + _tp_name(given) + "' into an index-sized integer")
    if generation >= _NUM_GENERATIONS:
        raise ValueError("generation parameter must be less than the number of available generations (" + str(_NUM_GENERATIONS) + ")")
    if generation < -1:
        raise ValueError("generation parameter cannot be negative")
    _object_graph("gc.get_objects")
    raise AssertionError("unreachable")


def get_stats(*args: object, **kwds: object) -> list[dict[str, int]]:   # gc_get_stats_impl: each generation's counters
    _noargs("get_stats", args, kwds)
    _collector("gc.get_stats")
    raise AssertionError("unreachable")


def is_tracked(*args: object, **kwds: object) -> bool:   # gc_is_tracked_impl: PyObject_GC_IsTracked
    _one("is_tracked", args, kwds)
    _collector("gc.is_tracked")
    raise AssertionError("unreachable")


def is_finalized(*args: object, **kwds: object) -> bool:   # gc_is_finalized_impl: PyObject_GC_IsFinalized
    _one("is_finalized", args, kwds)
    _collector("gc.is_finalized")
    raise AssertionError("unreachable")


def get_referrers(*args: object, **kwds: object) -> list[object]:   # gc_get_referrers_impl: *objs, METH_FASTCALL
    if kwds:
        raise TypeError("gc.get_referrers() takes no keyword arguments")
    _object_graph("gc.get_referrers")
    raise AssertionError("unreachable")


def get_referents(*args: object, **kwds: object) -> list[object]:   # gc_get_referents_impl: *objs, METH_FASTCALL
    if kwds:
        raise TypeError("gc.get_referents() takes no keyword arguments")
    _object_graph("gc.get_referents")
    raise AssertionError("unreachable")


def freeze(*args: object, **kwds: object) -> None:   # gc_freeze_impl: _PyGC_Freeze
    _noargs("freeze", args, kwds)
    _object_graph("gc.freeze")


def unfreeze(*args: object, **kwds: object) -> None:   # gc_unfreeze_impl: _PyGC_Unfreeze
    _noargs("unfreeze", args, kwds)
    _object_graph("gc.unfreeze")


def get_freeze_count(*args: object, **kwds: object) -> int:   # gc_get_freeze_count_impl: _PyGC_GetFreezeCount
    _noargs("get_freeze_count", args, kwds)
    _object_graph("gc.get_freeze_count")
    raise AssertionError("unreachable")
