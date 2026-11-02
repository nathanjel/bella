"""The name loads of an `__annotate__` evaluated against a given mapping and cells (decision S-1,
docs/staging.md; CPython 3.15.2 `Python/bytecodes.c` and `Objects/abstract.c`).

CPython's annotationlib re-runs `annotate.__code__` with substitute globals and cells. Bella's
compiler instead generates, next to each `__annotate__`, a second entry point that evaluates the
same expressions with every name load done by one of these functions (pipeline/staging/
annotations.py generates it). Each function does what its opcode does, including which
`__getitem__` and `__missing__` run:

    load_global          LOAD_GLOBAL
    load_deref           LOAD_DEREF (a free variable, or __classdict__)
    load_dict_or_global  LOAD_FROM_DICT_OR_GLOBALS (class scope: the class namespace, then globals)
    load_dict_or_deref   LOAD_FROM_DICT_OR_DEREF (class scope: the class namespace, then the cell)
    builtins_of          the builtins a function made over these globals gets
    _reify               _PyLazyImport_Reify: a PEP 810 lazy import found by a global load or in a
                         class namespace is resolved and written back (Objects/lazyimportobject.c;
                         review 2026-11-02 gemini-4-argon-high-05, 3.1); LOAD_DEREF does not resolve
    unpack1              UNPACK_SEQUENCE 1 (`*args: *Ts`)

and `entry_key`, the identity under which the build files an entry point and the model finds it
for a live function (in Bella the compiler attaches the entry point to the function instead).

It imports only what start-up has loaded: the replay model loads this file before the program.
"""
import builtins
import os
import sys

TYPE_CHECKING = False
if TYPE_CHECKING:
    from typing import Any

_MISSING = object()
_BUILTINS = vars(builtins)
_ModuleType = type(sys)


def _optional_item(mapping: object, key: str) -> object:
    """PyMapping_GetOptionalItem: a dict is read directly; any other mapping by its __getitem__,
    a KeyError meaning "not there"."""
    if type(mapping) is dict:
        return dict.get(mapping, key, _MISSING)
    try:
        return mapping[key]  # type: ignore[index]
    except KeyError:
        return _MISSING


def _lazy_type() -> Any:
    """types.LazyImportType. `types` is not loaded at start-up, but an entry point runs inside
    annotationlib, which has imported it."""
    types = sys.modules.get("types")
    return getattr(types, "LazyImportType", None)


def _reify(value: Any, name: str, namespace: Any) -> Any:
    """What the interpreter does with a lazy import it loads from `namespace`: resolve it and, if
    the namespace still holds it, store the result there; an exact dict directly, another mapping
    by its __setitem__, a read-only one not at all. (The interpreter may also replace a parent
    module's attribute: an optimisation its source says can be skipped.)"""
    lazy = _lazy_type()
    if lazy is None or type(value) is not lazy:      # PyLazyImport_CheckExact
        return value
    resolved = value.resolve()
    if type(namespace) is dict:
        if dict.get(namespace, name, _MISSING) is value:
            dict.__setitem__(namespace, name, resolved)
    elif hasattr(type(namespace), "__setitem__"):
        if _optional_item(namespace, name) is value:
            namespace[name] = resolved
    return resolved


def builtins_of(g: dict[str, object]) -> object:
    """_PyEval_BuiltinsFromGlobals: globals['__builtins__'] read as a plain dict entry (no
    __missing__), a module standing for its dict, else the running interpreter's builtins."""
    b = dict.get(g, "__builtins__", _MISSING)
    if b is _MISSING:
        return _BUILTINS
    return vars(b) if isinstance(b, _ModuleType) else b


def load_global(g: dict[str, object], b: object, name: str) -> object:
    namespace: Any = g
    if type(g) is dict and type(b) is dict:       # the exact-dict path: no __missing__ anywhere
        value = dict.get(g, name, _MISSING)
        if value is _MISSING:
            namespace, value = b, dict.get(b, name, _MISSING)
    else:
        value = _optional_item(g, name)
        if value is _MISSING:
            namespace, value = b, _optional_item(b, name)
    if value is _MISSING:
        raise NameError(f"name '{name}' is not defined", name=name)
    return _reify(value, name, namespace)


def load_deref(cells: dict[str, object], name: str) -> object:
    try:
        value = cells[name].cell_contents  # type: ignore[attr-defined]
    except ValueError:
        value = _MISSING
    if value is _MISSING:
        raise NameError(f"cannot access free variable '{name}' where it is not associated with a value in "
                        "enclosing scope", name=name)
    return value


def load_dict_or_global(classdict: object, g: dict[str, object], b: object, name: str) -> object:
    value = _optional_item(classdict, name)
    return load_global(g, b, name) if value is _MISSING else _reify(value, name, classdict)


def load_dict_or_deref(classdict: object, cells: dict[str, object], name: str) -> object:
    value = _optional_item(classdict, name)
    return load_deref(cells, name) if value is _MISSING else _reify(value, name, classdict)


def entry_key(code: Any) -> str:
    """The file, qualified name and first line, and the source positions of every instruction:
    two definitions can share the first three (two aliases on one line, review 2026-11-02
    astra-low-06, A6-1), not the positions. A tuple of ints and None hashes the same in every
    process, whatever PYTHONHASHSEED is."""
    positions = hash(tuple(code.co_positions())) & 0xFFFF_FFFF_FFFF_FFFF
    return f"{os.path.realpath(code.co_filename)}::{code.co_qualname}::{code.co_firstlineno}::{positions:016x}"


def unpack1(value: Any) -> Any:
    (only,) = value
    return only
