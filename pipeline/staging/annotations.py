"""Compile-time answers for annotationlib's `__code__` fallbacks (review log D-5, docs/staging.md).

CPython's compiler-generated `__annotate__` answers VALUE (and VALUE_WITH_FAKE_GLOBALS) and
raises NotImplementedError for FORWARDREF and STRING. `annotationlib.call_annotate_function`
then re-runs `annotate.__code__` with substitute globals. A compiled program has no code objects
to re-run, so for each `__annotate__` it generates, the compiler computes those re-runs at build
time where their result depends on nothing but the code:

* STRING: the run in which every name, global or free, is a `_Stringifier`. Its result is a
  function of the annotation expressions alone (`_Stringifier` builds strings from AST nodes and
  constants), so this module runs CPython's own code for it, on the pinned interpreter, against
  the same code object the program will contain.
* FORWARDREF's second run, with no globals: whether it raises, and what. The shim re-raises that
  when VALUE raises something other than a NameError (an annotation like `1 / 0`).

An entry whose STRING form would not be the same at runtime (a set of strings, whose order the
hash seed decides; a lambda, whose repr holds an address) is recorded as unstable, and the shim
refuses STRING for it rather than answer with a build-time string.
"""
from __future__ import annotations

import annotationlib
import builtins
import os
import re
import types
from typing import TypedDict

# CPython's own fallback machinery; private names, read on the pinned interpreter only
_StringifierDict = vars(annotationlib)["_StringifierDict"]
_build_closure = vars(annotationlib)["_build_closure"]
_stringify_single = vars(annotationlib)["_stringify_single"]
_Stringifier = vars(annotationlib)["_Stringifier"]

_STABLE_CONSTANTS = (str, bytes, int, float, complex, bool, type(None), type(...))
_ADDRESS = re.compile(r" at 0x[0-9a-fA-F]+")


class AnnotateEntry(TypedDict):
    is_class: bool
    string: dict[str, str] | None         # STRING, when it can be computed at build time
    string_raises: list[str] | None       # [exception class name, message] if the STRING run raises
    unstable: str | None                  # why STRING is not a build-time constant, if it is not
    second_raises: list[str] | None       # FORWARDREF's second run: what it raises, if anything


def entry_key(filename: str, qualname: str, firstlineno: int) -> str:
    """How the shim finds the entry for an `__annotate__` (the compiler attaches it instead)."""
    return f"{os.path.realpath(filename)}::{qualname}::{firstlineno}"


def _stable(value: object) -> bool:
    if isinstance(value, _Stringifier) or type(value) in _STABLE_CONSTANTS:
        return True
    if isinstance(value, (tuple, list)) and type(value) in (tuple, list):
        return all(_stable(v) for v in value)
    if isinstance(value, dict) and type(value) is dict:
        return all(_stable(k) and _stable(v) for k, v in value.items())
    return False


def _stand_in(code: types.CodeType) -> types.FunctionType:
    """A function over `code` with empty cells: what `_build_closure` reads (`__closure__`,
    `__code__.co_freevars`) when it replaces every cell with a `_Stringifier`."""
    cells = tuple(types.CellType() for _ in code.co_freevars) or None
    return types.FunctionType(code, {}, closure=cells)


def _raised(exc: BaseException) -> list[str]:
    return [type(exc).__name__, str(exc)]


def entry_for(code: types.CodeType) -> AnnotateEntry:
    is_class = "__classdict__" in code.co_freevars
    fmt = annotationlib.Format
    entry: AnnotateEntry = {"is_class": is_class, "string": None, "string_raises": None,
                            "unstable": None, "second_raises": None}
    # STRING: call_annotate_function's fallback, as CPython 3.15.2 runs it
    names = _StringifierDict({}, format=fmt.STRING)
    closure, _ = _build_closure(_stand_in(code), None, is_class, names, allow_evaluation=False)
    try:
        annos = types.FunctionType(code, names, closure=closure)(fmt.VALUE_WITH_FAKE_GLOBALS)
    except Exception as exc:  # noqa: BLE001  # the program sees whatever the fallback raises
        entry["string_raises"] = _raised(exc)
    else:
        unstable = [k for k, v in annos.items() if not _stable(v)]
        strings = {k: _stringify_single(v) for k, v in annos.items()}
        unstable += [k for k, s in strings.items() if _ADDRESS.search(s)]
        if unstable:
            entry["unstable"] = f"the STRING form of {', '.join(sorted(set(unstable)))} is not a build-time constant"
        else:
            entry["string"] = strings
    # FORWARDREF's second run: no globals, every cell a _Stringifier
    names = _StringifierDict({}, globals={}, owner=None, is_class=is_class, format=fmt.FORWARDREF)
    closure, _ = _build_closure(_stand_in(code), None, is_class, names, allow_evaluation=False)
    try:
        types.FunctionType(code, names, closure=closure)(fmt.VALUE_WITH_FAKE_GLOBALS)
    except Exception as exc:  # noqa: BLE001
        entry["second_raises"] = _raised(exc)
    return entry


def _annotate_codes(code: types.CodeType) -> list[types.CodeType]:
    found: list[types.CodeType] = []
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            if const.co_name == "__annotate__":
                found.append(const)
            found += _annotate_codes(const)
    return found


def tables_for_source(path: str) -> dict[str, AnnotateEntry]:
    """Every `__annotate__` the compiler generates for the module at `path`, with its entry.
    The module is compiled as the import system compiles it (same file name, flags and
    optimisation level), so the code objects are the ones the program will run."""
    with open(path, "rb") as f:
        source = f.read()
    code = compile(source, path, "exec", dont_inherit=True)
    return {entry_key(c.co_filename, c.co_qualname, c.co_firstlineno): entry_for(c) for c in _annotate_codes(code)}


def builtin_exception(name: str) -> type[BaseException] | None:
    """The exception class a recorded [name, message] pair names, if it is a built-in one."""
    cls = getattr(builtins, name, None)
    return cls if isinstance(cls, type) and issubclass(cls, BaseException) else None
