# clause: C-8-14
# spec: section 8 (modules), section 3 (attribute lookup)
# status: P1
# source: Objects/moduleobject.c (_Py_module_getattro_impl), Python/ceval.c (the global lookup, import_from)
"""A name the program deletes from a module is absent from then on, a built-in module's as any other's: reading it raises
AttributeError, hasattr is False, the from-import raises ImportError, and the lookup of one of the module's own first names
(__file__) raises NameError. The module's dict is the only record: a deletion through vars() counts the same, and a name set
again is there again, last in the dict. (The names of `builtins` are not a program's to assign or delete: E-06.)"""
import errno
import itertools
import math
import string
import sys
import time
from collections.abc import Callable
from types import ModuleType


def attempt(thunk: Callable[[], object]) -> str:
    try:
        result = thunk()
    except Exception as exc:  # noqa: BLE001  # which exception, by class
        return type(exc).__name__
    return ascii(result)


def imported(module: str, name: str) -> tuple[str, object, object]:
    try:
        if module == "math":
            from math import pi, tau  # noqa: F401, PLC0415
        elif module == "itertools":
            from itertools import chain  # noqa: F401, PLC0415
        elif module == "sys":
            from sys import maxsize  # noqa: F401, PLC0415
        elif module == "string":
            from string import digits  # noqa: F401, PLC0415
        else:
            from errno import ENOENT  # noqa: F401, PLC0415
    except ImportError as exc:
        return type(exc).__name__, exc.name, exc.name_from == name
    return "imported", None, None


def absent(module: ModuleType, name: str) -> tuple[object, ...]:
    try:
        getattr(module, name)
    except AttributeError as exc:
        return (type(exc).__name__, exc.name, exc.obj is module, hasattr(module, name), getattr(module, name, "a default"), name in dir(module),
                name in vars(module))
    return ("there",)


pi = math.pi
tau = math.tau
print("there:", absent(math, "pi"), imported("math", "pi")[0])
del math.pi
print("del:", absent(math, "pi"), imported("math", "pi"), attempt(lambda: math.pi), attempt(lambda: math.tau == tau))
print("again:", attempt(lambda: delattr(math, "pi")), attempt(lambda: vars(math).pop("pi")), attempt(lambda: delattr(math, "never")),
      attempt(lambda: math.never), absent(math, "never"))  # type: ignore[attr-defined]
math.pi = pi  # type: ignore[misc]
print("set again:", math.pi == pi, imported("math", "pi")[0], list(vars(math))[-1])
vars(math).pop("tau")
print("through vars:", absent(math, "tau"), imported("math", "tau"))
math.tau = tau  # type: ignore[misc]
chain = itertools.chain
del vars(itertools)["chain"]
print("a type:", absent(itertools, "chain"), imported("itertools", "chain"), attempt(lambda: list(itertools.chain("a", "b"))), list(chain("a", "b")))
itertools.chain = chain  # type: ignore[misc]
maxsize = sys.maxsize
delattr(sys, "maxsize")
print("sys:", absent(sys, "maxsize"), imported("sys", "maxsize"))
sys.maxsize = maxsize
monotonic, enoent, digits = time.monotonic, errno.ENOENT, string.digits
del time.monotonic, errno.ENOENT, string.digits
print("others:", absent(time, "monotonic")[:4], absent(errno, "ENOENT")[:4], imported("errno", "ENOENT"), absent(string, "digits")[:4], imported("string", "digits"))
time.monotonic, errno.ENOENT, string.digits = monotonic, enoent, digits  # type: ignore[misc]
here = __file__
del __file__
print("the module's own:", attempt(lambda: __file__), "__file__" in globals(), "__file__" in vars(sys.modules[__name__]))
__file__ = here
print("back:", __file__ == here)
