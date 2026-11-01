#!/usr/bin/env python3
"""bella closure -- compute the phase-1 import closure against the pinned standard library.

Why this exists
---------------
Dialect specification v0.3, section 7, promises a *dependency-closed* phase-1 manifest:
every module Bella claims to support must have every module it imports at runtime
supported too, or an adaptation named. Review rounds two and three showed that an
inventory made by reading source is not closed (logging -> threading, argparse -> gettext,
statistics -> bisect, collections -> keyword/reprlib, shutil -> optional bz2/lzma). This
tool computes the closure mechanically and fails the build when the manifest is open. A closed
manifest is an inventory -- every import accounted for -- not proof that those modules compile or
that their APIs are reproduced (review 2026-11-01, astra-low-01).

How it works
------------
1. Dynamic: import every root in a fresh `python -I` and diff sys.modules. This catches
   whatever really loads at import time, including through import hooks.
2. Static: for every reached source module, parse it with `ast` and collect every
   import *anywhere* in the file -- module level, inside functions (lazy), inside `if`,
   `try: ... except ImportError` or `with suppress(ImportError)` (conditional) -- plus
   `importlib.import_module("x")` and `__import__("x")` with literal names (dynamic).
   Relative imports are resolved against the module's package.
3. Transitive closure. Eager and dynamic edges are always followed. A lazy edge (an import
   inside a function) is followed when its target is in the manifest; otherwise the
   importing function must be declared unsupported in `[lazy_unsupported]` -- this is the
   "support per API" the second review asked for (difflib._test imports doctest; that does
   not make doctest a phase-1 dependency, it makes difflib._test unsupported). A conditional
   edge is followed when its target is in the manifest; otherwise it must appear in
   `[omissions]` (the import resolves to ImportError at runtime, as if not installed).
   Modules with status `core` or `shim` are provided by the runtime and are not scanned:
   a shim replaces the real module, so the real module's imports do not count.
4. Compare with manifest.toml and write closure.lock.json. Exit 1 on any gap.

Run it with the pinned interpreter (bella.toml: reference.python). `--allow-unpinned`
lets it run elsewhere for development, with a loud warning in the lock file.
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import subprocess
import sys
import sysconfig
import tomllib
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path

EAGER = "eager"              # module level, unconditional: executed at import time
LAZY = "lazy"                # inside a function body: executed when the function runs
CONDITIONAL = "conditional"  # under `if`, `try/except ImportError`, `with suppress(ImportError)`
DYNAMIC = "dynamic"          # importlib.import_module / __import__ with a literal name
DYNAMIC_UNKNOWN = "dynamic-unknown"  # same, with a computed name: reported, not followed
RUNTIME = "runtime"          # observed in sys.modules after importing the roots, not seen statically

REQUIRED_CLASSES = {EAGER, LAZY, DYNAMIC, RUNTIME}
IMPORT_ERROR_NAMES = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}


@dataclass(frozen=True)
class Edge:
    importer: str
    target: str
    cls: str
    line: int


@dataclass
class ModuleInfo:
    name: str
    kind: str                       # source | extension | builtin | frozen | namespace | missing
    path: str | None
    status: str = "unknown"         # compiled | mapped | core | shim | excluded | missing-from-manifest
    reached_by: str | None = None   # first edge that reached it: "importer:cls:line"
    edges: list[Edge] = field(default_factory=list)
    dynamic_unknown_lines: list[int] = field(default_factory=list)


# ------------------------------------------------------------------------------------------
# Manifest
# ------------------------------------------------------------------------------------------

@dataclass
class Manifest:
    python: str
    roots: list[str]
    compiled: set[str]
    mapped: set[str]
    core: set[str]
    shim: dict[str, str]
    excluded: set[str]
    omissions: dict[str, set[str]]
    lazy_unsupported: dict[str, set[str]]
    adaptations: dict[str, str]

    @property
    def supported(self) -> set[str]:
        return self.compiled | self.mapped | self.core | set(self.shim)

    def status_of(self, name: str) -> str:
        if name in self.excluded:
            return "excluded"
        if name in self.compiled:
            return "compiled"
        if name in self.mapped:
            return "mapped"
        if name in self.core:
            return "core"
        if name in self.shim:
            return "shim"
        return "missing-from-manifest"

    @classmethod
    def load(cls, path: Path) -> Manifest:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        p1 = data.get("phase1", {})
        return cls(
            python=data["reference"]["python"],
            roots=list(p1.get("roots", [])),
            compiled=set(p1.get("compiled", [])),
            mapped=set(p1.get("mapped", [])),
            core=set(p1.get("core", [])),
            shim=dict(p1.get("shim", {})),
            excluded=set(data.get("excluded", {}).get("modules", [])),
            omissions={k: set(v) for k, v in data.get("omissions", {}).items()},
            lazy_unsupported={k: set(v) for k, v in data.get("lazy_unsupported", {}).items()},
            adaptations=dict(data.get("adaptations", {})),
        )


# ------------------------------------------------------------------------------------------
# Module classification
# ------------------------------------------------------------------------------------------

STDLIB_DIR = Path(sysconfig.get_paths()["stdlib"])


def classify(name: str) -> tuple[str, str | None]:
    """Return (kind, source path) for a module name without importing user code."""
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, ValueError, AttributeError):
        spec = None
    if spec is None:
        return "missing", None
    origin = spec.origin
    if origin == "built-in":
        return "builtin", None
    if origin == "frozen":
        src = _frozen_source(name)
        return "frozen", (str(src) if src else None)
    if origin is None:
        if spec.submodule_search_locations is not None:
            return "namespace", None
        return "missing", None
    if origin.endswith((".so", ".pyd", ".dylib")):
        return "extension", origin
    if origin.endswith(".py"):
        return "source", origin
    return "other", origin


def _frozen_source(name: str) -> Path | None:
    rel = name.replace(".", "/")
    for candidate in (STDLIB_DIR / f"{rel}.py", STDLIB_DIR / rel / "__init__.py"):
        if candidate.exists():
            return candidate
    return None


def _is_package_path(path: str | None) -> bool:
    return path is not None and Path(path).name == "__init__.py"


# ------------------------------------------------------------------------------------------
# Static scan
# ------------------------------------------------------------------------------------------

class _Scanner:
    """Collect import edges from one module's AST with their execution class."""

    def __init__(self, module: str, is_package: bool) -> None:
        self.module = module
        self.package = module if is_package else module.rpartition(".")[0]
        self.edges: list[tuple[str, str, int]] = []   # (target, cls, line)
        self.dynamic_unknown: list[int] = []

    # -- context tracking -----------------------------------------------------------------
    def scan(self, node: ast.AST, lazy: bool = False, conditional: bool = False) -> None:
        for child in ast.iter_child_nodes(node):
            self._visit(child, lazy, conditional)

    def _visit(self, node: ast.AST, lazy: bool, conditional: bool) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                self._add_dotted(alias.name, lazy, conditional, node.lineno)
            return
        if isinstance(node, ast.ImportFrom):
            self._add_from(node, lazy, conditional)
            return
        if isinstance(node, ast.Call):
            self._maybe_dynamic(node, lazy, conditional)
            self.scan(node, lazy, conditional)
            return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            # decorators and defaults run at definition time; the body runs later
            for part in getattr(node, "decorator_list", []):
                self._visit(part, lazy, conditional)
            args = node.args
            for d in list(args.defaults) + [d for d in args.kw_defaults if d is not None]:
                self._visit(d, lazy, conditional)
            body = node.body if isinstance(node.body, list) else [node.body]
            for stmt in body:
                self._visit(stmt, True, conditional)
            return
        if isinstance(node, ast.IfExp):
            self._visit(node.test, lazy, conditional)
            self._visit(node.body, lazy, True)
            self._visit(node.orelse, lazy, True)
            return
        if isinstance(node, (ast.If, ast.While)):
            # the test is unconditional; branches are conditional
            self._visit(node.test, lazy, conditional)
            for stmt in node.body + node.orelse:
                self._visit(stmt, lazy, True)
            return
        if isinstance(node, ast.Match):
            self._visit(node.subject, lazy, conditional)
            for case in node.cases:
                for stmt in case.body:
                    self._visit(stmt, lazy, True)
            return
        if isinstance(node, (ast.Try, ast.TryStar)):
            optional = any(_handler_catches_import_error(h) for h in node.handlers)
            for stmt in node.body:
                self._visit(stmt, lazy, conditional or optional)
            for h in node.handlers:
                for stmt in h.body:
                    self._visit(stmt, lazy, True)
            for stmt in node.orelse:
                self._visit(stmt, lazy, conditional)
            for stmt in node.finalbody:
                self._visit(stmt, lazy, conditional)
            return
        if isinstance(node, (ast.With, ast.AsyncWith)):
            suppressing = any(_is_suppress_import_error(item.context_expr) for item in node.items)
            for item in node.items:
                self._visit(item.context_expr, lazy, conditional)
            for stmt in node.body:
                self._visit(stmt, lazy, conditional or suppressing)
            return
        self.scan(node, lazy, conditional)

    # -- edge construction ----------------------------------------------------------------
    def _cls(self, lazy: bool, conditional: bool) -> str:
        if conditional:
            return CONDITIONAL
        return LAZY if lazy else EAGER

    def _add_dotted(self, dotted: str, lazy: bool, conditional: bool, line: int) -> None:
        parts = dotted.split(".")
        for i in range(1, len(parts) + 1):
            self.edges.append((".".join(parts[:i]), self._cls(lazy, conditional), line))

    def _add_from(self, node: ast.ImportFrom, lazy: bool, conditional: bool) -> None:
        if node.level == 0:
            base = node.module or ""
        else:
            try:
                base = importlib.util.resolve_name("." * node.level + (node.module or ""), self.package)
            except (ImportError, ValueError):
                return
        if base == "__future__":
            return
        cls = self._cls(lazy, conditional)
        if base:
            self._add_dotted(base, lazy, conditional, node.lineno)
        for alias in node.names:
            if alias.name == "*":
                continue
            candidate = f"{base}.{alias.name}" if base else alias.name
            kind, _ = classify(candidate)
            if kind != "missing":
                self.edges.append((candidate, cls, node.lineno))

    def _maybe_dynamic(self, node: ast.Call, lazy: bool, conditional: bool) -> None:
        fn = node.func
        name = None
        if isinstance(fn, ast.Name) and fn.id == "__import__":
            name = "__import__"
        elif isinstance(fn, ast.Attribute) and fn.attr == "import_module":
            name = "import_module"
        if name is None or not node.args:
            return
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            target = first.value
            if target.startswith("."):
                try:
                    target = importlib.util.resolve_name(target, self.package)
                except (ImportError, ValueError):
                    return
            self.edges.append((target, DYNAMIC if not conditional else CONDITIONAL, node.lineno))
        else:
            self.dynamic_unknown.append(node.lineno)


def _handler_catches_import_error(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    names: list[str] = []
    for n in ast.walk(handler.type):
        if isinstance(n, ast.Name):
            names.append(n.id)
        elif isinstance(n, ast.Attribute):
            names.append(n.attr)
    return any(n in IMPORT_ERROR_NAMES for n in names)


def _is_suppress_import_error(expr: ast.AST) -> bool:
    if not isinstance(expr, ast.Call):
        return False
    fn = expr.func
    fname = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
    if fname != "suppress":
        return False
    for arg in expr.args:
        for n in ast.walk(arg):
            if isinstance(n, ast.Name) and n.id in IMPORT_ERROR_NAMES:
                return True
            if isinstance(n, ast.Attribute) and n.attr in IMPORT_ERROR_NAMES:
                return True
    return False


def scan_module(name: str, path: str) -> tuple[list[Edge], list[int]]:
    try:
        tree = ast.parse(Path(path).read_text(encoding="utf-8", errors="replace"), filename=path)
    except SyntaxError:
        return [], []
    scanner = _Scanner(name, _is_package_path(path))
    scanner.scan(tree)
    edges = [Edge(name, t, c, line) for (t, c, line) in scanner.edges]
    return edges, scanner.dynamic_unknown


# ------------------------------------------------------------------------------------------
# Dynamic observation
# ------------------------------------------------------------------------------------------

def observe_runtime_imports(roots: list[str]) -> dict[str, list[str]]:
    """Import every root in a fresh isolated interpreter; return what each pulled in."""
    code = r"""
import json, sys
roots = json.loads(sys.argv[1])
before = set(sys.modules)
result = {}
for r in roots:
    prior = set(sys.modules)
    try:
        __import__(r)
    except Exception as exc:  # report, never hide
        result[r] = ["<import failed: %s: %s>" % (type(exc).__name__, exc)]
        continue
    result[r] = sorted(set(sys.modules) - prior)
print(json.dumps({"baseline": sorted(before), "per_root": result}))
"""
    proc = subprocess.run(
        [sys.executable, "-I", "-c", code, json.dumps(roots)],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"runtime observation failed:\n{proc.stderr}")
    data = json.loads(proc.stdout)
    per_root: dict[str, list[str]] = data["per_root"]
    return per_root


# ------------------------------------------------------------------------------------------
# Closure
# ------------------------------------------------------------------------------------------

def _static_reach(starts: set[str], classes: set[str]) -> set[str]:
    """Modules reachable from `starts` over edges of the given classes (manifest-blind)."""
    seen: set[str] = set()
    queue: deque[str] = deque(starts)
    while queue:
        name = queue.popleft()
        if name in seen:
            continue
        seen.add(name)
        kind, path = classify(name)
        if kind in ("source", "frozen") and path:
            edges, _ = scan_module(name, path)
            for e in edges:
                if e.cls in classes and e.target not in seen:
                    queue.append(e.target)
    return seen


def compute_closure(manifest: Manifest) -> tuple[dict[str, ModuleInfo], list[str]]:
    infos: dict[str, ModuleInfo] = {}
    problems: list[str] = []
    queue: deque[tuple[str, str | None]] = deque((r, None) for r in manifest.roots)
    conditional_outside: dict[str, set[str]] = {}
    lazy_outside: dict[str, set[tuple[str, int]]] = {}

    def ensure(name: str, reached_by: str | None) -> ModuleInfo:
        info = infos.get(name)
        if info is None:
            kind, path = classify(name)
            info = ModuleInfo(name=name, kind=kind, path=path, reached_by=reached_by,
                              status=manifest.status_of(name))
            infos[name] = info
            # core and shim modules are provided by the runtime: their real source is not scanned
            if info.status not in ("core", "shim") and kind in ("source", "frozen") and path:
                info.edges, info.dynamic_unknown_lines = scan_module(name, path)
        return info

    while queue:
        name, reached_by = queue.popleft()
        if name in infos:
            continue
        info = ensure(name, reached_by)
        for e in info.edges:
            if e.target in infos:
                continue
            via = f"{e.importer}:{e.cls}:{e.line}"
            if e.cls in (EAGER, DYNAMIC):
                queue.append((e.target, via))
            elif e.cls == LAZY:
                if e.target in manifest.supported:
                    queue.append((e.target, via))
                else:
                    lazy_outside.setdefault(e.importer, set()).add((e.target, e.line))
            elif e.cls == CONDITIONAL:
                if e.target in manifest.supported:
                    queue.append((e.target, via))
                else:
                    conditional_outside.setdefault(e.importer, set()).add(e.target)

    # modules that load only because an omitted optional import succeeded on this machine
    omitted_targets = {t for ts in manifest.omissions.values() for t in ts}
    omitted_closure = _static_reach(omitted_targets, {EAGER, DYNAMIC}) - manifest.supported

    # dynamic observation: anything that loaded at import time and was not seen statically
    observed = observe_runtime_imports(manifest.roots)
    for root, loaded in observed.items():
        for mod in loaded:
            if mod.startswith("<import failed"):
                problems.append(f"root {root}: {mod}")
                continue
            if mod in infos or mod in omitted_closure:
                continue
            ensure(mod, f"{root}:{RUNTIME}:0")

    # problems
    for name, info in sorted(infos.items()):
        if info.status == "excluded":
            problems.append(f"{name}: excluded module reached as required (via {info.reached_by})")
        elif info.status == "missing-from-manifest" and info.kind != "missing":
            problems.append(f"{name} [{info.kind}]: required but not in manifest (via {info.reached_by})")
        elif info.kind == "missing" and info.status == "missing-from-manifest":
            problems.append(f"{name}: not importable on this platform and not declared (via {info.reached_by})")
        # consistency: a source module listed as mapped, or an extension listed as compiled
        if info.status == "compiled" and info.kind not in ("source", "frozen", "namespace"):
            problems.append(f"{name}: listed as compiled but is {info.kind}")
        if info.status == "mapped" and info.kind in ("source", "frozen"):
            problems.append(f"{name}: listed as mapped but has Python source ({info.path})")
    for importer, targets in sorted(conditional_outside.items()):
        declared = manifest.omissions.get(importer, set())
        for t in sorted(targets):
            if t in declared:
                continue
            kind, _ = classify(t)
            if kind == "missing":
                continue  # unavailable on this platform anyway (e.g. msvcrt on Linux)
            problems.append(f"{importer}: conditional import of {t} outside the manifest and not declared in [omissions]")
    for importer, lazy_targets in sorted(lazy_outside.items()):
        declared = manifest.lazy_unsupported.get(importer, set())
        for t, line in sorted(lazy_targets):
            if t in declared:
                continue
            kind, _ = classify(t)
            if kind == "missing":
                continue
            problems.append(f"{importer}:{line}: lazy import of {t} outside the manifest; add {t} to the manifest "
                            f"or declare the importing function unsupported in [lazy_unsupported]")
    unreached = sorted(m for m in manifest.supported - manifest.core if m not in infos)
    if unreached:
        problems.append(f"note: {len(unreached)} manifest entries never reached: "
                        f"{', '.join(unreached[:12])}{'...' if len(unreached) > 12 else ''}")
    return infos, problems


# ------------------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--manifest", type=Path, default=Path("manifest.toml"))
    ap.add_argument("--out", type=Path, default=Path("closure.lock.json"))
    ap.add_argument("--allow-unpinned", action="store_true", help="run on a Python other than the pinned reference build")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    manifest = Manifest.load(args.manifest)
    running = ".".join(map(str, sys.version_info[:3]))
    pinned = running == manifest.python
    if not pinned and not args.allow_unpinned:
        print(f"closure: refusing to run on Python {running}; the manifest is pinned to {manifest.python} "
              f"(use --allow-unpinned for a non-authoritative run)", file=sys.stderr)
        return 2

    infos, problems = compute_closure(manifest)
    notes = [p for p in problems if p.startswith("note:")]
    errors = [p for p in problems if not p.startswith("note:")]

    lock = {
        "python": running,
        "pinned": pinned,
        "authoritative": pinned,
        "stdlib_dir": str(STDLIB_DIR),
        "roots": manifest.roots,
        "module_count": len(infos),
        "errors": errors,
        "notes": notes,
        "modules": {
            n: {k: v for k, v in asdict(i).items() if k != "edges"} | {
                "edges": [asdict(e) for e in i.edges]
            }
            for n, i in sorted(infos.items())
        },
    }
    args.out.write_text(json.dumps(lock, indent=1, sort_keys=False) + "\n", encoding="utf-8")

    if not args.quiet:
        by_status: dict[str, int] = {}
        for i in infos.values():
            by_status[i.status] = by_status.get(i.status, 0) + 1
        print(f"closure of {len(manifest.roots)} roots: {len(infos)} modules on Python {running}"
              f"{'' if pinned else '  [UNPINNED, non-authoritative]'}")
        for s, c in sorted(by_status.items()):
            print(f"  {s:24} {c}")
        for n in notes:
            print(f"  {n}")
        if errors:
            print(f"\n{len(errors)} problem(s):")
            for e in errors:
                print(f"  - {e}")
        print(f"\nwrote {args.out}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
