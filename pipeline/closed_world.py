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
compilation), each `from` name that may be a submodule, what `from pkg import *` imports (the names
of the package's `__all__`, or every submodule when its `__all__` is computed), and `__import__` or
`import_module` with literal arguments. A name found nowhere is the runtime's to refuse (a
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
from importlib.machinery import PathFinder
from importlib.util import decode_source
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STDLIB = Path(os.path.dirname(os.__file__)).resolve()
FROZEN = frozenset(_imp._frozen_module_names())  # type: ignore[attr-defined]  # CPython's; no stub
FIRST = frozenset(sys.builtin_module_names) | FROZEN   # found before sys.path


def read_source(path: Path) -> str:
    """A module's text as CPython reads it: its PEP 263 cookie or BOM, universal newlines."""
    try:
        return decode_source(path.read_bytes())
    except (UnicodeDecodeError, LookupError) as exc:
        raise SyntaxError(f"{path}: {exc}") from exc


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


def _argument(call: ast.Call, position: int, keyword: str) -> ast.expr | None:
    if len(call.args) > position:
        return call.args[position]
    return next((k.value for k in call.keywords if k.arg == keyword), None)


def _literal_str(node: ast.expr | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _literal_strs(node: ast.expr | None) -> tuple[str, ...] | None:
    """A list or tuple of string literals; None for anything else."""
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    out = [_literal_str(e) for e in node.elts]
    return None if None in out else tuple(e for e in out if e is not None)


def _called_import(call: ast.Call, package: str | None) -> tuple[str, tuple[str, ...]] | None:
    """What a call of `__import__` or `import_module` with literal arguments imports, by whatever
    name it is reached (`builtins.__import__`, `il.import_module`, `from importlib import
    import_module`). A call of something else of that name only costs a compilation."""
    f = call.func
    called = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
    name = _literal_str(_argument(call, 0, "name"))
    if name is None:
        return None
    if called == "__import__":
        level = _argument(call, 4, "level")
        base = _resolve(name, package, level.value if isinstance(level, ast.Constant) and isinstance(level.value, int) else 0)
        return None if base is None else (base, _literal_strs(_argument(call, 3, "fromlist")) or ())
    if called == "import_module":
        dots = len(name) - len(name.lstrip("."))
        if not dots:
            return name, ()
        anchor = _argument(call, 1, "package")
        known = package if isinstance(anchor, ast.Name) and anchor.id == "__package__" else _literal_str(anchor)
        base = _resolve(name[dots:], known, dots)
        return None if base is None else (base, ())
    return None


def _imports(tree: ast.Module, package: str | None) -> list[tuple[str, tuple[str, ...]]]:
    """Each absolute name an import may load, with the names a `from` import asks of it (`*` too)."""
    out: list[tuple[str, tuple[str, ...]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(alias.name, ()) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = _resolve(node.module or "", package, node.level)
            if base is not None:
                out.append((base, tuple(a.name for a in node.names)))
        elif isinstance(node, ast.Call):
            called = _called_import(node, package)
            if called is not None:
                out.append(called)
    return out


def _all_names(tree: ast.Module) -> tuple[str, ...] | None:
    """The names a package's `__all__` holds, as far as its source says: None when one of them is
    computed. A module without `__all__` has none: `import *` then loads no submodule."""
    names: list[str] = []
    for node in ast.walk(tree):
        values: list[ast.expr | None] = []
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            values.append(node.value)
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)) and isinstance(node.target, ast.Name) and node.target.id == "__all__":
            values.append(node.value)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) \
                and node.func.value.id == "__all__":
            if node.func.attr == "extend":
                values.append(_argument(node, 0, ""))
            elif node.func.attr in ("append", "insert"):
                item = node.args[-1] if node.args else None
                values.append(ast.List(elts=[item]) if item is not None else None)
        for value in values:
            literal = _literal_strs(value)
            if literal is None:
                return None
            names += literal
    return tuple(names)


def _submodules(m: ProgramModule) -> list[str]:
    """Every module a package has, by file or by the lock: what a computed `__all__` may name."""
    assert m.path is not None
    if m.origin is not None or m.path.is_relative_to(STDLIB):
        return [n for n in library_modules() if n.startswith(m.name + ".") and "." not in n[len(m.name) + 1:]]
    tails = [p.stem for p in m.path.parent.glob("*.py") if p.name != "__init__.py"]
    tails += [p.name for p in m.path.parent.iterdir() if p.is_dir() and p.name != "__pycache__"]
    return [f"{m.name}.{t}" for t in sorted(tails) if t.isidentifier()]


def _regular_in_stdlib(name: str) -> bool:
    """A top-level name the standard library has as a module or package: on a later sys.path entry,
    it wins over a directory without __init__.py (a namespace package needs no regular module of
    that name anywhere on the path)."""
    spec = PathFinder.find_spec(name, [str(STDLIB), str(STDLIB / "lib-dynload")])
    return spec is not None and spec.origin is not None


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
        if not name or name.startswith(".") or name.endswith(".") or ".." in name:
            absent.add(name)                   # no file has an empty name: ModuleNotFoundError when imported
            return None
        parent, _, tail = name.rpartition(".")
        where: Path | None
        library_parent = False
        if parent:
            p = find(parent)
            library_parent = p is not None and p.path is not None and (p.origin is not None or p.path.is_relative_to(STDLIB))
            where = p.path.parent if p is not None and p.path is not None and p.package and not library_parent else None
            if name in FIRST:
                where = None                   # FrozenImporter takes a dotted name whatever its parent's path says
        else:
            where = None if name in FIRST else root
        result: ProgramModule | None = None
        if where is not None:
            if (where / tail / "__init__.py").is_file():
                result = ProgramModule(name, (where / tail / "__init__.py").resolve(), True)
            elif (where / f"{tail}.py").is_file():
                result = ProgramModule(name, (where / f"{tail}.py").resolve(), False)
            elif (where / tail).is_dir() and tail.isidentifier() and (parent or not _regular_in_stdlib(tail)):
                result = ProgramModule(name, None, True)
        if result is None and (not parent or library_parent or name in FROZEN):
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

    def star(m: ProgramModule) -> None:
        """`from m import *` imports what m's __all__ names (_handle_fromlist)."""
        assert m.path is not None
        names = _all_names(ast.parse(read_source(m.path), str(m.path)))
        for full in (_submodules(m) if names is None else [f"{m.name}.{x}" for x in names]):
            parts = full.split(".")
            for i in range(1, len(parts) + 1):
                find(".".join(parts[:i]))

    def scan(source: Path, name: str, package: bool) -> None:
        tree = ast.parse(read_source(source), str(source))
        for target, fromlist in _imports(tree, _package_of(name, package)):
            parts = target.split(".")
            for i in range(1, len(parts) + 1):
                find(".".join(parts[:i]))
            m = found.get(target)
            if m is not None and m.package and m.path is not None:
                for x in fromlist:
                    if x == "*":
                        star(m)
                    else:
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
