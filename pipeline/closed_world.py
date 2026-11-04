"""The modules a program can import, found at build time (spec section 8: a closed world).

The build compiles the entry module and every module an import in it can reach, found as CPython
3.15.2's import system finds them for `python program.py`:
* sys.path[0] is the program's directory;
* a built-in or frozen module of the pinned interpreter comes first (BuiltinImporter and
  FrozenImporter precede the path finder), so a file of the program's with such a name is never
  imported;
* in a directory, a package (`name/__init__.py`) comes before a module (`name.py`), and a
  directory without `__init__.py` is a namespace package;
* a submodule is searched in its parent package's directory;
* after the program's directory comes the standard library, as `closure.lock.json` knows it: a
  module of status `compiled`, or a shim whose source is ours (decision P-1: a stage compiles its
  target's whole closure). What the runtime provides (`core`, `mapped`) is not compiled here, and a
  shim not written yet is refused by name when imported.

What an import can reach is read from each module's source: every import statement in it,
function-local and conditional ones included (an import that never runs costs only its
compilation), each `from` name that may be a submodule, and `__import__` or
`importlib.import_module` with a literal name. A name found nowhere is the runtime's to refuse (a
standard-library module it does not have) or ModuleNotFoundError (one that is not installed), when
the import runs. The manifest's omissions behave as not installed (spec section 7).
"""
from __future__ import annotations

import _imp
import ast
import json
import os
import sys
import tomllib
from dataclasses import dataclass
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STDLIB = Path(os.path.dirname(os.__file__)).resolve()
FROZEN = frozenset(_imp._frozen_module_names())  # type: ignore[attr-defined]  # CPython's; no stub
FIRST = frozenset(sys.builtin_module_names) | FROZEN   # found before sys.path


@dataclass(frozen=True)
class ProgramModule:
    name: str
    path: Path | None              # None: a namespace package (refused when imported, step 3b)
    package: bool                  # an __init__.py: its directory is __path__
    frozen: bool = False           # CPython finds it frozen: FrozenImporter's spec, `<frozen name>` frames
    origin: Path | None = None     # a shim's `__file__`: the standard library's file it stands for


@cache
def library_modules() -> dict[str, tuple[Path, Path]]:
    """The standard-library modules the build compiles: name -> (source, the file CPython has)."""
    data = json.loads((ROOT / "closure.lock.json").read_text(encoding="utf-8"))
    out: dict[str, tuple[Path, Path]] = {}
    for name, m in data["modules"].items():
        path = m.get("path")
        if not path:
            continue                   # an alias a module makes itself (os.path, collections.abc), or the runtime's
        if m["status"] == "compiled":
            out[name] = (STDLIB / path, STDLIB / path)
        elif m["status"] == "shim" and path.startswith("runtime/"):
            cpython = name.replace(".", "/") + ".py"
            out[name] = (ROOT / path, STDLIB / cpython)
    return out


@cache
def omitted_modules() -> frozenset[str]:
    """The manifest's omissions: not installed, as far as a program can tell (spec section 7)."""
    manifest = tomllib.loads((ROOT / "manifest.toml").read_text(encoding="utf-8"))
    return frozenset(t for targets in manifest.get("omissions", {}).values() for t in targets)


def _package_of(name: str, package: bool) -> str | None:
    """What __package__ is for a module the import system loaded (spec.parent)."""
    if name == "__main__":
        return None
    return name if package else name.rpartition(".")[0]


def _resolve(name: str, package: str | None, level: int) -> str | None:
    """importlib._bootstrap._resolve_name: None where the import raises ImportError."""
    if level == 0:
        return name or None
    if not package:
        return None
    bits = package.rsplit(".", level - 1)
    if len(bits) < level:
        return None
    return f"{bits[0]}.{name}" if name else bits[0]


def _imports(tree: ast.Module, package: str | None) -> list[tuple[str, tuple[str, ...]]]:
    """Each absolute name an import may load, with the names a `from` import asks of it."""
    out: list[tuple[str, tuple[str, ...]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(alias.name, ()) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = _resolve(node.module or "", package, node.level)
            if base is not None:
                out.append((base, tuple(a.name for a in node.names if a.name != "*")))
        elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[0].value, str):
            f = node.func
            if (isinstance(f, ast.Name) and f.id == "__import__") or \
                    (isinstance(f, ast.Attribute) and f.attr == "import_module" and isinstance(f.value, ast.Name)
                     and f.value.id == "importlib"):
                out.append((node.args[0].value, ()))
    return out


def find_program_modules(program: Path) -> list[ProgramModule]:
    """Every module of the program's own an import can reach, in the order they were found."""
    root = program.resolve().parent
    found: dict[str, ProgramModule] = {}
    absent: set[str] = set()
    queue: list[ProgramModule] = []

    def find(name: str) -> ProgramModule | None:
        if name in found:
            return found[name]
        if name in absent:
            return None
        parent, _, tail = name.rpartition(".")
        where: Path | None
        library_parent = False
        if parent:
            p = find(parent)
            library_parent = p is not None and p.path is not None and (p.origin is not None or p.path.is_relative_to(STDLIB))
            where = p.path.parent if p is not None and p.path is not None and p.package and not library_parent else None
        else:
            where = None if name in FIRST else root
        result: ProgramModule | None = None
        if where is not None:
            if (where / tail / "__init__.py").is_file():
                result = ProgramModule(name, (where / tail / "__init__.py").resolve(), True)
            elif (where / f"{tail}.py").is_file():
                result = ProgramModule(name, (where / f"{tail}.py").resolve(), False)
            elif (where / tail).is_dir() and tail.isidentifier():
                result = ProgramModule(name, None, True)
        if result is None and (not parent or library_parent):
            library = library_modules().get(name)
            if library is not None:
                source, origin = library
                result = ProgramModule(name, source.resolve(), source.name == "__init__.py" or origin.name == "__init__.py",
                                       name in FROZEN, origin if source != origin else None)
        if result is None:
            absent.add(name)
            return None
        found[name] = result
        queue.append(result)
        return result

    def scan(source: Path, name: str, package: bool) -> None:
        tree = ast.parse(source.read_text(encoding="utf-8"), str(source))
        for target, fromlist in _imports(tree, _package_of(name, package)):
            parts = target.split(".")
            for i in range(1, len(parts) + 1):
                find(".".join(parts[:i]))
            m = found.get(target)
            if m is not None and m.package:
                for x in fromlist:
                    find(f"{target}.{x}")

    scan(program, "__main__", False)
    done = 0
    while done < len(queue):
        m = queue[done]
        done += 1
        if m.path is not None:
            scan(m.path, m.name, m.package)
    return queue


def namespace_of(name: str) -> str:
    """The C++ namespace a module is emitted into: injective (`.` is `_0`, `_` is `_1`)."""
    if name == "__main__":
        return "bella::m_main"
    out = []
    for c in name:
        if c == ".":
            out.append("_0")
        elif c == "_":
            out.append("_1")
        elif c.isascii() and c.isalnum():
            out.append(c)
        else:
            out.append(f"_2{ord(c):06x}")
    return "bella::mod_" + "".join(out)
