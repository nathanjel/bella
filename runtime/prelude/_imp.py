"""_imp, in Python (Python/import.c's module): the low-level half of the import system that importlib's package and util import.
In a closed world most of it has nothing to do: the lock is one thread's, the built-in and frozen module names are the pin's
(the names table), the source hash is the runtime's siphash13 keyed as _Py_KeyedHash keys it, and what would load a frozen code
object or an extension module stops by name."""

__all__ = ["_fix_co_filename", "_frozen_module_names", "_override_frozen_modules_for_tests", "_override_multi_interp_extensions_check",
           "_set_lazy_attributes", "acquire_lock", "check_hash_based_pycs", "create_builtin", "create_dynamic", "exec_builtin", "exec_dynamic",
           "extension_suffixes", "find_frozen", "get_frozen_object", "init_frozen", "is_builtin", "is_frozen", "is_frozen_package", "lock_held",
           "pyc_magic_number_token", "release_lock", "source_hash"]

__name__ = "_imp"

try:
    _bella_refuse                                # noqa: B018  # a facility phase 1 lacks, where it would run
    _tp_name                                     # noqa: B018  # Py_TYPE(o)->tp_name
    _number_index                                # noqa: B018  # PyNumber_Index
    _unpack_keywords                             # noqa: B018  # _PyArg_UnpackKeywords
    _cpython_table                               # noqa: B018  # a row of the names table (tools/cpython_names.py): the pin's build constants
    _source_hash                                 # noqa: B018  # _Py_KeyedHash: siphash13 with the key and 0
    _bella_create_builtin                        # noqa: B018  # the runtime's built-in module for a spec
    _bella_set_lazy_attributes                   # noqa: B018  # _imp._set_lazy_attributes
except NameError:
    from collections.abc import Callable
    from typing import Any

    def _missing(*args: object) -> Any:
        raise ImportError("this file needs the runtime's primitives")

    _bella_refuse: Callable[..., Any] = _missing
    _unpack_keywords: Callable[..., Any] = _missing
    _cpython_table: Callable[..., Any] = _missing
    _source_hash: Callable[..., Any] = _missing
    _bella_create_builtin: Callable[..., Any] = _missing
    _bella_set_lazy_attributes: Callable[..., Any] = _missing

    def _tp_name(o: object) -> str:
        return type(o).__name__

    def _number_index(o: object) -> int:
        import operator
        return operator.index(o)

import sys

_ABSENT = object()
_FROZEN: tuple[str, ...] = tuple(_cpython_table("imp:frozen_module_names").split("\n"))
_FROZEN_PACKAGES: frozenset[str] = frozenset(_cpython_table("imp:frozen_packages").split("\n"))
_EXTENSION_SUFFIXES: tuple[str, ...] = tuple(_cpython_table("imp:extension_suffixes").split("\n"))
check_hash_based_pycs: str = _cpython_table("imp:check_hash_based_pycs")
pyc_magic_number_token: int = int(_cpython_table("imp:pyc_magic_number_token"))
_lock_depth = 0                                  # the interpreter's import lock, held by the one thread


def _noargs(fname: str, args: tuple[object, ...], kwds: dict[str, object]) -> None:   # METH_NOARGS
    if kwds:
        raise TypeError("_imp." + fname + "() takes no keyword arguments")
    if args:
        raise TypeError("_imp." + fname + "() takes no arguments (" + str(len(args)) + " given)")


def _one(fname: str, args: tuple[object, ...], kwds: dict[str, object]) -> object:   # METH_O
    if kwds:
        raise TypeError("_imp." + fname + "() takes no keyword arguments")
    if len(args) != 1:
        raise TypeError("_imp." + fname + "() takes exactly one argument (" + str(len(args)) + " given)")
    return args[0]


def _str_arg(fname: str, value: object) -> str:   # the clinic's `unicode` converter for a METH_O function
    if not isinstance(value, str):
        raise TypeError(fname + "() argument must be str, not " + _tp_name(value))
    return value


def acquire_lock(*args: object, **kwds: object) -> None:
    global _lock_depth
    _noargs("acquire_lock", args, kwds)
    _lock_depth += 1


def release_lock(*args: object, **kwds: object) -> None:
    global _lock_depth
    _noargs("release_lock", args, kwds)
    if _lock_depth == 0:
        raise RuntimeError("not holding the import lock")
    _lock_depth -= 1


def lock_held(*args: object, **kwds: object) -> bool:
    _noargs("lock_held", args, kwds)
    return _lock_depth > 0


def is_builtin(*args: object, **kwds: object) -> int:   # is_builtin: -1 for a module of the interpreter's own (sys, builtins), 1 for a built-in, 0 otherwise
    name = _str_arg("is_builtin", _one("is_builtin", args, kwds))
    if name in ("sys", "builtins"):
        return -1
    return 1 if name in sys.builtin_module_names else 0


def is_frozen(*args: object, **kwds: object) -> bool:
    name = _str_arg("is_frozen", _one("is_frozen", args, kwds))
    return name in _FROZEN


def is_frozen_package(*args: object, **kwds: object) -> bool:
    name = _str_arg("is_frozen_package", _one("is_frozen_package", args, kwds))
    if name not in _FROZEN:
        raise ImportError("No such frozen object named " + repr(name), name=name)
    return name in _FROZEN_PACKAGES


def find_frozen(*args: object, **kwds: object) -> tuple[object, bool, str] | None:   # (data, is_package, origname) or None
    name, withdata = _unpack_keywords("find_frozen", ("name", "withdata"), 1, 1, 1, 0, args, kwds, _ABSENT)
    if not isinstance(name, str):
        raise TypeError("find_frozen() argument 1 must be str, not " + _tp_name(name))
    if withdata is not _ABSENT and bool(withdata):
        _bella_refuse("_imp.find_frozen with withdata (the frozen module's marshalled code: a compiled program has none)")
    if name not in _FROZEN:
        return None
    return (None, name in _FROZEN_PACKAGES, name)


def get_frozen_object(*args: object, **kwds: object) -> object:
    if kwds:
        raise TypeError("_imp.get_frozen_object() takes no keyword arguments")
    if not 1 <= len(args) <= 2:
        raise TypeError("get_frozen_object expected " + ("at least 1 argument" if not args else "at most 2 arguments") + ", got " + str(len(args)))
    name = args[0]
    if not isinstance(name, str):
        raise TypeError("get_frozen_object() argument 1 must be str, not " + _tp_name(name))
    if name not in _FROZEN:
        raise ImportError("No such frozen object named " + repr(name), name=name)
    _bella_refuse("_imp.get_frozen_object (a frozen module's code object: a compiled program has none)")


def init_frozen(*args: object, **kwds: object) -> object:
    name = _str_arg("init_frozen", _one("init_frozen", args, kwds))
    if name not in _FROZEN:
        return None
    _bella_refuse("_imp.init_frozen (initialising a frozen module outside the import system)")


def extension_suffixes(*args: object, **kwds: object) -> list[str]:
    _noargs("extension_suffixes", args, kwds)
    return list(_EXTENSION_SUFFIXES)


def source_hash(*args: object, **kwds: object) -> bytes:
    key, source = _unpack_keywords("source_hash", ("key", "source"), 0, 2, 2, 0, args, kwds, _ABSENT)
    k = _number_index(key)                       # the clinic's `long`
    if k > 2**63 - 1 or k < -(2**63):
        raise OverflowError("Python int too large to convert to C long")
    if not isinstance(source, (bytes, bytearray)):
        if hasattr(type(source), "__buffer__"):
            _bella_refuse("[P2+] the buffer protocol (__buffer__)")
        raise TypeError("a bytes-like object is required, not '" + _tp_name(source) + "'")
    return _source_hash(k, bytes(source))  # type: ignore[no-any-return]   # the C long's bits are the key's (a negative one wraps)


def create_builtin(*args: object, **kwds: object) -> object:
    spec = _one("create_builtin", args, kwds)
    spec.name                                    # noqa: B018  # create_builtin reads the spec's name first: its AttributeError for anything else
    return _bella_create_builtin(spec)


def exec_builtin(*args: object, **kwds: object) -> int:
    _one("exec_builtin", args, kwds)
    return 0


def create_dynamic(*args: object, **kwds: object) -> object:
    _bella_refuse("_imp.create_dynamic (an extension module: a compiled program has none)")


def exec_dynamic(*args: object, **kwds: object) -> int:
    _bella_refuse("_imp.exec_dynamic (an extension module: a compiled program has none)")


def _fix_co_filename(*args: object, **kwds: object) -> None:
    _bella_refuse("_imp._fix_co_filename (a code object's filename, E-02)")


def _frozen_module_names(*args: object, **kwds: object) -> list[str]:
    _noargs("_frozen_module_names", args, kwds)
    return list(_FROZEN)


def _override_frozen_modules_for_tests(*args: object, **kwds: object) -> int:
    _bella_refuse("_imp._override_frozen_modules_for_tests (the test suite's switch)")


def _override_multi_interp_extensions_check(*args: object, **kwds: object) -> int:
    _one("_override_multi_interp_extensions_check", args, kwds)
    raise RuntimeError("_imp._override_multi_interp_extensions_check() cannot be used in the main interpreter")


def _set_lazy_attributes(*args: object, **kwds: object) -> None:
    if kwds:
        raise TypeError("_imp._set_lazy_attributes() takes no keyword arguments")
    if len(args) != 2:
        raise TypeError("_set_lazy_attributes expected 2 arguments, got " + str(len(args)))
    if not isinstance(args[1], str):
        raise TypeError("_set_lazy_attributes() argument 2 must be str, not " + _tp_name(args[1]))
    _bella_set_lazy_attributes(args[0], args[1])
