#!/usr/bin/env python3
"""Score a candidate target program or package against the phase-1 dialect.

    python3 tools/score_candidate.py --manifest manifest.toml PATH [PATH ...]

For each path (a package directory or a single file) it reports:
  * size: files and non-blank source lines;
  * imports: stdlib modules used, split into in-manifest and outside (names only; the full
    closure is tools/closure.py), plus third-party imports;
  * dynamism: counts of constructs by dialect tier (spec section 5) and exclusions (section 4),
    from the ast -- __getattr__/__getattribute__/__setattr__ definitions, computed-name
    getattr/setattr, class mutation after definition, metaclasses, runtime type() creation,
    __class__ assignment, eval/exec/compile, frame introspection, threads, async;
  * unsupported-by-the-slice constructs that matter for the first compilation path: classes,
    lambdas, generators, with, try/finally, *args/**kwargs, decorators, comprehensions.

It is a reading aid for choosing targets, not a conformance tool; a high tier-2 count is a
cost, not a defect.
"""
from __future__ import annotations

import argparse
import ast
import sys
import tomllib
from collections import Counter
from pathlib import Path
from typing import TypedDict

STDLIB = set(sys.stdlib_module_names)
EXCLUDED_CALLS = {"eval", "exec", "compile"}
FRAME_ATTRS = {"_getframe", "currentframe", "stack", "settrace", "setprofile", "f_locals", "f_back"}


def load_manifest(path: Path) -> set[str]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    p1 = data["phase1"]
    return set(p1["compiled"]) | set(p1["mapped"]) | set(p1["core"]) | set(p1.get("shim", {})) | set(p1["roots"])


class Scan(ast.NodeVisitor):
    def __init__(self, pkg_names: set[str]) -> None:
        self.pkg_names = pkg_names
        self.stdlib: set[str] = set()
        self.third: set[str] = set()
        self.tiers: Counter[str] = Counter()
        self.slice_gaps: Counter[str] = Counter()
        self.class_names: set[str] = set()

    def _mod(self, name: str) -> None:
        top = name.split(".")[0]
        if top in self.pkg_names:
            return
        if top in STDLIB:
            self.stdlib.add(name if name.count(".") <= 1 else ".".join(name.split(".")[:2]))
        else:
            self.third.add(top)

    def visit_If(self, n: ast.If) -> None:
        # `if TYPE_CHECKING:` never runs (PEP 484): only its else branch counts (review 2026-11-01, G3 3.4)
        t = n.test
        if (isinstance(t, ast.Name) and t.id == "TYPE_CHECKING") or (isinstance(t, ast.Attribute) and t.attr == "TYPE_CHECKING"):
            for stmt in n.orelse:
                self.visit(stmt)
            return
        self.generic_visit(n)

    def visit_Import(self, n: ast.Import) -> None:
        for a in n.names:
            self._mod(a.name)

    def visit_ImportFrom(self, n: ast.ImportFrom) -> None:
        if n.level == 0 and n.module:
            self._mod(n.module)
        if any(a.name == "*" for a in n.names):
            self.tiers["star-import (lint F403)"] += 1

    def visit_ClassDef(self, n: ast.ClassDef) -> None:
        self.class_names.add(n.name)
        self.slice_gaps["class"] += 1
        for kw in n.keywords:
            if kw.arg == "metaclass":
                self.tiers["metaclass (staged if pure, else tier 3)"] += 1
        if len(n.bases) > 1:
            self.tiers["multiple inheritance (tier 3 if stateful)"] += 1
        self.slice_gaps["decorator"] += len(n.decorator_list)
        for item in n.body:
            if isinstance(item, ast.FunctionDef):
                if item.name == "__getattr__":
                    self.tiers["__getattr__ (tier 1)"] += 1
                elif item.name == "__getattribute__":
                    self.tiers["__getattribute__ (tier 2, P2+)"] += 1
                elif item.name in ("__setattr__", "__delattr__"):
                    self.tiers["__setattr__/__delattr__ (tier 2)"] += 1
                elif item.name == "__slots__":
                    pass
            if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__slots__" for t in item.targets):
                self.tiers["__slots__ (helps)"] += 1
        self.generic_visit(n)

    def visit_FunctionDef(self, n: ast.FunctionDef) -> None:
        if n.decorator_list:
            self.slice_gaps["decorator"] += len(n.decorator_list)
        if n.args.vararg or n.args.kwarg:
            self.slice_gaps["*args/**kwargs"] += 1
        if n.args.kwonlyargs:
            self.slice_gaps["keyword-only"] += 1
        self.generic_visit(n)

    def visit_AsyncFunctionDef(self, n: ast.AsyncFunctionDef) -> None:
        self.tiers["async def (P2+)"] += 1
        self.generic_visit(n)

    def visit_Await(self, n: ast.Await) -> None:
        self.tiers["await (P2+)"] += 1
        self.generic_visit(n)

    def visit_Lambda(self, n: ast.Lambda) -> None:
        self.slice_gaps["lambda"] += 1
        self.generic_visit(n)

    def visit_Yield(self, n: ast.Yield) -> None:
        self.slice_gaps["generator"] += 1
        self.generic_visit(n)

    def visit_YieldFrom(self, n: ast.YieldFrom) -> None:
        self.slice_gaps["generator"] += 1
        self.generic_visit(n)

    def visit_With(self, n: ast.With) -> None:
        self.slice_gaps["with"] += 1
        self.generic_visit(n)

    def visit_Try(self, n: ast.Try) -> None:
        self.slice_gaps["try"] += 1
        self.generic_visit(n)

    def visit_ListComp(self, n: ast.ListComp) -> None:
        self.slice_gaps["comprehension"] += 1
        self.generic_visit(n)

    visit_DictComp = visit_SetComp = visit_GeneratorExp = visit_ListComp  # type: ignore[assignment]

    def visit_JoinedStr(self, n: ast.JoinedStr) -> None:
        self.slice_gaps["f-string"] += 1
        self.generic_visit(n)

    def visit_Call(self, n: ast.Call) -> None:
        f = n.func
        name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
        if name in EXCLUDED_CALLS and isinstance(f, ast.Name):
            self.tiers[f"{name}() (EXCLUDED E-01)"] += 1
        elif name in ("getattr", "setattr", "delattr", "hasattr") and isinstance(f, ast.Name):
            if len(n.args) >= 2 and not (isinstance(n.args[1], ast.Constant) and isinstance(n.args[1].value, str)):
                self.tiers[f"{name}(computed name) (tier 2)"] += 1
            else:
                self.tiers[f"{name}(literal) (lint B009/B010)"] += 1
        elif name == "type" and isinstance(f, ast.Name) and len(n.args) == 3:
            self.tiers["type(name, bases, ns) (tier 3, P2+)"] += 1
        elif name in FRAME_ATTRS:
            self.tiers[f"{name} (EXCLUDED E-02)"] += 1
        elif name in ("import_module", "__import__"):
            self.tiers["dynamic import (tier 2)"] += 1
        elif name in ("vars", "locals", "globals") and isinstance(f, ast.Name):
            self.tiers[f"{name}() (tier 2)"] += 1
        elif (name in ("__getattribute__", "__setattr__", "__delattr__") and isinstance(f, ast.Attribute)
              and isinstance(f.value, ast.Name) and f.value.id == "object" and len(n.args) >= 2
              and not isinstance(n.args[1], ast.Constant)):
            self.tiers[f"object.{name}(computed name) (tier 2)"] += 1
        elif name == "Thread" or (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "threading"):
            self.tiers["threading (P2+)"] += 1
        self.generic_visit(n)

    def visit_Attribute(self, n: ast.Attribute) -> None:
        if n.attr in FRAME_ATTRS:
            self.tiers[f"{n.attr} (EXCLUDED E-02)"] += 1
        if n.attr == "__dict__":
            self.tiers["__dict__ access (tier 2)"] += 1
        if n.attr == "__class__" and isinstance(n.ctx, ast.Store):
            self.tiers["__class__ assignment (tier 1, P2+)"] += 1
        self.generic_visit(n)

    def visit_Assign(self, n: ast.Assign) -> None:
        for t in n.targets:
            if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id in self.class_names:
                self.tiers["class attribute write after definition (tier 1)"] += 1
        self.generic_visit(n)


class Score(TypedDict):
    path: str
    files: int
    lines: int
    stdlib_in: list[str]
    stdlib_out: list[str]
    third_party: list[str]
    tiers: dict[str, int]
    slice_gaps: dict[str, int]


def score(path: Path, supported: set[str]) -> Score:
    files = [path] if path.is_file() else sorted(p for p in path.rglob("*.py") if "test" not in p.parts and "tests" not in p.parts)
    pkg_names = {path.stem} | ({p.stem for p in path.iterdir() if p.suffix == ".py"} if path.is_dir() else set())
    scan = Scan(pkg_names)
    lines = 0
    for f in files:
        src = f.read_text(encoding="utf-8", errors="replace")
        lines += sum(1 for ln in src.splitlines() if ln.strip() and not ln.strip().startswith("#"))
        try:
            scan.visit(ast.parse(src, filename=str(f)))
        except SyntaxError as exc:
            scan.tiers[f"syntax error: {exc.msg}"] += 1
    # a submodule is in the manifest only by its own name: importlib.resources is not because importlib is
    outside = sorted(m for m in scan.stdlib if m not in supported)
    inside = sorted(m for m in scan.stdlib if m not in outside)
    return {"path": str(path), "files": len(files), "lines": lines, "stdlib_in": inside, "stdlib_out": outside,
            "third_party": sorted(scan.third), "tiers": dict(scan.tiers.most_common()), "slice_gaps": dict(scan.slice_gaps.most_common())}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--manifest", type=Path, default=Path("manifest.toml"))
    args = ap.parse_args(argv)
    supported = load_manifest(args.manifest)
    for p in args.paths:
        if (p.is_file() and p.suffix != ".py") or p.name == "__pycache__":
            continue                      # a licence file, data, a cache: nothing to parse
        r = score(p, supported)
        print(f"== {r['path']}: {r['files']} files, {r['lines']} lines")
        print(f"   stdlib in manifest : {', '.join(r['stdlib_in']) or '-'}")
        print(f"   stdlib OUTSIDE     : {', '.join(r['stdlib_out']) or '-'}")
        print(f"   third party        : {', '.join(r['third_party']) or '-'}")
        print(f"   dynamism           : {r['tiers'] or '-'}")
        print(f"   slice gaps         : {r['slice_gaps'] or '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
