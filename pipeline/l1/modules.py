"""The modules eval1 runs (Gate 0 task 4, step A4).

CPython's own import machinery stays in charge: sys.modules, packages, relative imports,
partially initialised modules, __spec__ and the import lock are the interpreter's. A meta-path
finder placed first hands eval1 the modules it should execute. A module's source is found as
CPython's path finder finds it, and lowered through the frontend; `exec_module` then runs its
L1 body with the module's own __dict__ as globals, as CPython's loader execs its code.

Which modules eval1 runs:
* "program" (the default): every module whose source is outside the standard library: the
  program's own modules, a conformance case's fixtures, vendored packages. The standard library
  and the core and mapped modules are the host's.
* "closure": the program's modules, and also every standard-library module the lock lists as
  compiled, plus the shims written in Python (runtime/shims), whose source replaces CPython's.
  Every one of those is lowered before the program starts (decision P-1: a stage compiles its
  whole closure), so the frontend never runs while program code is running. (In "program" mode a program's module is
  lowered when it is first imported; nothing on that path imports, so an __import__ hook the
  program installed sees only the program's own imports.) Host modules of the
  same names are taken out of sys.modules first; the host's own code keeps the module objects
  it already holds.
"""
from __future__ import annotations

import importlib.abc
import importlib.machinery
import importlib.util
import json
import os
import sys
import types
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pipeline.l1 import grammar as L
from pipeline.l1.frontend import lower
from pipeline.l1.grammar import DialectError, Refused, Unsupported
from pipeline.l1.wf import WellFormednessError, check

ROOT = Path(__file__).resolve().parents[2]
STDLIB = Path(os.path.dirname(os.__file__)).resolve()
SHIMS = ROOT / "runtime" / "shims"
TOOLING = ("pipeline", "refmodel", "tools", "validation", "conformance/harness.py")


def module_names(path: Path) -> frozenset[str]:
    """What the import system binds in a module's globals before its body runs, beyond builtins
    (whose dict also holds __name__, __doc__, __package__, __loader__ and __spec__): __file__,
    and __path__ in a package's __init__."""
    return frozenset({"__file__", "__path__"} if path.name == "__init__.py" else {"__file__"})


def lower_file(path: Path, library: bool) -> L.Module:
    """A module lowered and checked; a library module's names are held to CPython's runtime
    resolution, not the program's compile-time rule (proposal P-3, wf.check)."""
    module = lower(path.read_text(encoding="utf-8"), str(path))
    check(module, module_names(path), strict=not library)
    return module


class Eval1Loader(importlib.abc.Loader):
    def __init__(self, system: ModuleSystem, path: Path) -> None:
        self.system, self.path = system, path

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> types.ModuleType | None:
        return None                                   # CPython's default module object

    def exec_module(self, module: types.ModuleType) -> None:
        lowered = self.system.lowered(self.path)
        # exec() of a module's code gives its globals __builtins__ (the builtins dict)
        module.__dict__.setdefault("__builtins__", vars(__import__("builtins")))
        self.system.interp.run_in(lowered, module.__dict__)


class ModuleSystem(importlib.abc.MetaPathFinder):
    def __init__(self, interp: Any, mode: str = "program", lock: Path | None = None) -> None:
        if mode not in ("program", "closure"):
            raise ValueError(mode)
        self.interp, self.mode = interp, mode
        self.cache: dict[Path, L.Module] = {}
        self.failures: dict[Path, str] = {}
        self.closure: dict[str, Path] = {}
        if mode == "closure":
            data = json.loads((lock or ROOT / "closure.lock.json").read_text(encoding="utf-8"))
            for name, m in data["modules"].items():
                path = m.get("path")
                if not path:
                    continue
                if m["status"] == "compiled":
                    self.closure[name] = (STDLIB / path).resolve()
                elif m["status"] == "shim" and path.startswith("runtime/"):
                    self.closure[name] = (ROOT / path).resolve()

    # ---- lowering -------------------------------------------------------------------------
    def lowered(self, path: Path) -> L.Module:
        if path in self.failures:
            raise Refused(f"{path.name}: {self.failures[path]}")
        if path not in self.cache:
            try:
                self.cache[path] = lower_file(path, library=path in self.closure.values() or path.is_relative_to(STDLIB))
            except (Unsupported, DialectError, SyntaxError, WellFormednessError) as exc:
                self.failures[path] = f"{type(exc).__name__}: {exc}"
                raise Refused(f"{path.name}: {self.failures[path]}") from None
        return self.cache[path]

    def prelower(self) -> dict[str, str]:
        """Lower the whole closure now (P-1); returns the modules that do not lower, and why."""
        failed: dict[str, str] = {}
        for name, path in sorted(self.closure.items()):
            try:
                self.lowered(path)
            except Refused:
                failed[name] = self.failures[path]
        return failed

    # ---- finding --------------------------------------------------------------------------
    def find_spec(self, fullname: str, path: Sequence[str] | None = None,
                  target: types.ModuleType | None = None) -> importlib.machinery.ModuleSpec | None:
        if fullname in self.closure:
            source = self.closure[fullname]
            is_package = source.name == "__init__.py"
            spec = importlib.util.spec_from_file_location(
                fullname, source, loader=Eval1Loader(self, source),  # type: ignore[arg-type]  # an importlib Loader
                submodule_search_locations=[str(source.parent)] if is_package else None)
            return spec
        found = importlib.machinery.PathFinder.find_spec(fullname, path)
        if found is None or not found.origin or not found.origin.endswith(".py"):
            return None
        origin = Path(found.origin).resolve()
        if origin.is_relative_to(STDLIB):
            return None                               # the host's (or, in closure mode, not in the lock)
        if any(origin.is_relative_to(ROOT / own) for own in TOOLING):
            return None                               # Bella's own code, which runs eval1, stays the host's
        found.loader = Eval1Loader(self, origin)
        return found

    # ---- activation -----------------------------------------------------------------------
    def activate(self) -> None:
        if self.mode == "closure":
            for name in list(sys.modules):
                if name in self.closure:
                    del sys.modules[name]             # the program gets its own, run by eval1
        sys.meta_path.insert(0, self)
        importlib.invalidate_caches()
