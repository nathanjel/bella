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
2. Static: for every reached source module, parse it with `ast` and collect every import
   *anywhere* in the file, plus `importlib.import_module("x")` and `__import__("x")` with
   literal names (dynamic). Relative imports are resolved against the module's package. Each
   import gets one class (review log D-3, 2026-11-01):
     dead      under a guard that is false on the target platform: `sys.platform`, `os.name`
               and `sys.builtin_module_names` come from [platform]; `__name__` is the module's
               own name; module-level names bound once to such values count too. Never executed,
               never compiled, needs no manifest entry; recorded in the lock with its line.
     optional  inside `try: ... except ImportError` or `with suppress(ImportError)`.
     lazy      inside a function body, guarded or not (a guard the closed world cannot
               evaluate is just program logic there).
     guarded   at module level under a guard the closed world cannot evaluate, or in an
               exception handler: executed at import time on some runs, so required.
     eager     at module level, unconditional, or under a guard that is true on the target.
3. Transitive closure. Eager, guarded and dynamic edges are always followed. A lazy edge is
   followed when its target is in the manifest; otherwise the importing function must be
   declared unsupported in `[lazy_unsupported]` -- the "support per API" the second review
   asked for (difflib._test imports doctest; that does not make doctest a phase-1 dependency,
   it makes difflib._test unsupported). An optional edge is followed when its target is in the
   manifest; otherwise it must appear in `[omissions]` (the import resolves to ImportError at
   runtime, as if not installed), and `[omissions]` may hold nothing else. Modules with status
   `core` or `shim` are provided by the runtime and are not scanned: a shim replaces the real
   module, so the real module's imports do not count.
4. Compare with manifest.toml and write closure.lock.json. Exit 1 on any gap.

Run it with the pinned interpreter (bella.toml: reference.python) on the target platform.
`--allow-unpinned` lets it run elsewhere for development, with a loud warning in the lock file.
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
import subprocess
import sys
import sysconfig
import tomllib
from collections import Counter, deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import NamedTuple

EAGER = "eager"              # module level, unconditional (or under a guard true on the target)
GUARDED = "guarded"          # module level, under a guard the closed world cannot evaluate: required
LAZY = "lazy"                # inside a function body: executed when the function runs
OPTIONAL = "optional"        # under try/except ImportError or suppress(ImportError)
DEAD = "dead"                # under a guard false on the target platform: never executed
DYNAMIC = "dynamic"          # importlib.import_module / __import__ with a literal name
DYNAMIC_UNKNOWN = "dynamic-unknown"  # same, with a computed name: reported, not followed
RUNTIME = "runtime"          # observed in sys.modules after importing the roots, not seen statically

FOLLOWED_CLASSES = {EAGER, GUARDED, DYNAMIC}   # required whatever the manifest says
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
class Platform:
    """Facts about the target platform (manifest.toml [platform]) that import guards may test."""

    facts: dict[str, object] = field(default_factory=dict)   # "sys.platform" -> "linux", "os.name" -> "posix"
    builtin_present: frozenset[str] = frozenset()            # names known to be in sys.builtin_module_names
    builtin_absent: frozenset[str] = frozenset()             # names known not to be

    @classmethod
    def from_table(cls, table: dict[str, object]) -> Platform:
        facts = {k: v for k, v in table.items() if k not in ("builtin_modules_present", "builtin_modules_absent")}
        present = table.get("builtin_modules_present", [])
        absent = table.get("builtin_modules_absent", [])
        assert isinstance(present, list) and isinstance(absent, list)
        return cls(facts, frozenset(map(str, present)), frozenset(map(str, absent)))

    def mismatches(self) -> list[str]:
        """Facts the running interpreter contradicts: the dynamic observation would not match them."""
        actual: dict[str, object] = {"sys.platform": sys.platform, "os.name": os.name}
        out = [f"{k} is {actual[k]!r} here, [platform] says {v!r}"
               for k, v in self.facts.items() if k in actual and actual[k] != v]
        out += [f"{k} is not in sys.builtin_module_names here" for k in sorted(self.builtin_present)
                if k not in sys.builtin_module_names]
        out += [f"{k} is in sys.builtin_module_names here" for k in sorted(self.builtin_absent)
                if k in sys.builtin_module_names]
        return out


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
    platform: Platform = field(default_factory=Platform)

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
            platform=Platform.from_table(data.get("platform", {})),
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
# Guards the closed world can evaluate (review log D-3)
# ------------------------------------------------------------------------------------------

class _Unknown:
    """A value the closed world does not know at build time."""

    def __repr__(self) -> str:
        return "UNKNOWN"


UNKNOWN = _Unknown()


@dataclass(frozen=True)
class _ModuleRef:
    """The value of a name bound by `import sys` or `import os as _os`."""

    name: str


class _BuiltinNames:
    """`sys.builtin_module_names`: membership is known only for the names [platform] lists."""


BUILTIN_NAMES = _BuiltinNames()
_CONSTANT_TYPES = (str, int, float, bool, type(None), tuple, frozenset)


class _Evaluator:
    """Evaluates a guard over constants, the [platform] facts, `__name__` and known module names.

    Anything else (a call other than str.startswith/endswith, a subscript, a name bound by a loop
    or inside a `try`) is UNKNOWN, and an UNKNOWN guard is one that may go either way.
    """

    def __init__(self, platform: Platform, module: str) -> None:
        self.platform = platform
        self.module = module

    def value(self, node: ast.expr, env: dict[str, object]) -> object:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return env.get(node.id, UNKNOWN)
        if isinstance(node, ast.Attribute):
            base = self.value(node.value, env)
            if isinstance(base, _ModuleRef):
                key = f"{base.name}.{node.attr}"
                if key == "sys.builtin_module_names":
                    return BUILTIN_NAMES
                return self.platform.facts.get(key, UNKNOWN)
            return UNKNOWN
        if isinstance(node, (ast.BoolOp, ast.Compare)) or (isinstance(node, ast.UnaryOp)
                                                            and isinstance(node.op, ast.Not)):
            return self.truth(node, env)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("startswith", "endswith") and len(node.args) == 1 and not node.keywords):
            base, arg = self.value(node.func.value, env), self.value(node.args[0], env)
            if isinstance(base, str) and isinstance(arg, (str, tuple)):
                return base.startswith(arg) if node.func.attr == "startswith" else base.endswith(arg)
        return UNKNOWN

    def truth(self, node: ast.expr, env: dict[str, object]) -> object:
        """True, False or UNKNOWN: the truth value of the guard on the target platform."""
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            t = self.truth(node.operand, env)
            return UNKNOWN if t is UNKNOWN else not t
        if isinstance(node, ast.BoolOp):
            ts = [self.truth(v, env) for v in node.values]
            decisive = isinstance(node.op, ast.Or)    # `or` is decided by a true operand, `and` by a false one
            if any(t is decisive for t in ts):
                return decisive
            return (not decisive) if all(t is (not decisive) for t in ts) else UNKNOWN
        if isinstance(node, ast.Compare):
            left = self.value(node.left, env)
            result: object = True
            for op, right_node in zip(node.ops, node.comparators, strict=True):
                right = self.value(right_node, env)
                r = self._compare(op, left, right)
                if r is False:
                    return False
                if r is UNKNOWN:
                    result = UNKNOWN
                left = right
            return result
        v = self.value(node, env)
        if v is UNKNOWN or isinstance(v, (_ModuleRef, _BuiltinNames)):
            return UNKNOWN
        return bool(v)

    def _compare(self, op: ast.cmpop, left: object, right: object) -> object:
        if right is BUILTIN_NAMES and isinstance(left, str) and isinstance(op, (ast.In, ast.NotIn)):
            if left in self.platform.builtin_present:
                found = True
            elif left in self.platform.builtin_absent:
                found = False
            else:
                return UNKNOWN
            return found if isinstance(op, ast.In) else not found
        if not (isinstance(left, _CONSTANT_TYPES) and isinstance(right, _CONSTANT_TYPES)):
            return UNKNOWN
        try:
            if isinstance(op, ast.Eq):
                return left == right
            if isinstance(op, ast.NotEq):
                return left != right
            if isinstance(op, (ast.In, ast.NotIn)):
                if isinstance(right, str):
                    if not isinstance(left, str):
                        return UNKNOWN
                    found = left in right
                elif isinstance(right, (tuple, frozenset)):
                    found = left in right
                else:
                    return UNKNOWN
                return found if isinstance(op, ast.In) else not found
            if isinstance(op, ast.Is):
                return left is right
            if isinstance(op, ast.IsNot):
                return left is not right
        except TypeError:
            return UNKNOWN
        return UNKNOWN


def _names_in(node: ast.AST) -> set[str]:
    """Names a statement binds in its own scope (the bodies of nested scopes excluded)."""
    out: set[str] = set()

    def walk(n: ast.AST) -> None:
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
            return
        elif isinstance(n, ast.Lambda):
            return
        elif isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            # the iteration variables belong to the comprehension; a walrus inside binds outside
            out.update(s.target.id for s in ast.walk(n)
                       if isinstance(s, ast.NamedExpr) and isinstance(s.target, ast.Name))
            return
        elif isinstance(n, ast.alias):
            out.add(n.asname or n.name.partition(".")[0])
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        elif isinstance(n, (ast.MatchAs, ast.MatchStar)) and n.name:
            out.add(n.name)
        elif isinstance(n, ast.MatchMapping) and n.rest:
            out.add(n.rest)
        for c in ast.iter_child_nodes(n):
            walk(c)

    walk(node)
    return out


def _locals_of(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda | ast.ClassDef) -> frozenset[str]:
    """Names bound in a function or class body: inside it they shadow the module's names."""
    names: set[str] = set()
    if not isinstance(node, ast.ClassDef):
        a = node.args
        names.update(arg.arg for arg in [*a.posonlyargs, *a.args, *a.kwonlyargs, a.vararg, a.kwarg] if arg)
    for stmt in node.body if isinstance(node.body, list) else [node.body]:
        names |= _names_in(stmt)
    return frozenset(names)


class _ModuleEnv:
    """First pass over a module's top level: the names whose values the closed world knows.

    Module-level statements run in order, so the guard of a module-level `if` or `while` is
    evaluated with the names bound before it (`truth`). Function and class bodies run at a time
    the scan cannot know, so their guards see `final`: a name keeps its value there only if the
    module binds it exactly once and no function declares it `global`. Anything bound inside a
    loop, a `try`, a `with`, a `match` or a branch whose guard is UNKNOWN is UNKNOWN, and a star
    import may rebind any public name.
    """

    def __init__(self, ev: _Evaluator, tree: ast.Module) -> None:
        self.ev = ev
        self.truth: dict[ast.AST, object] = {}
        self.env: dict[str, object] = {"__name__": ev.module}
        self.bindings: Counter[str] = Counter()
        self._block(tree.body, certain=True)
        declared_global = {n for node in ast.walk(tree) if isinstance(node, ast.Global) for n in node.names}
        self.final = {k: (UNKNOWN if self.bindings[k] > 1 or k in declared_global else v)
                      for k, v in self.env.items()}

    def _bind(self, name: str, value: object, certain: bool) -> None:
        self.bindings[name] += 1
        self.env[name] = value if certain else UNKNOWN

    def _block(self, stmts: list[ast.stmt], certain: bool) -> None:
        for s in stmts:
            self._stmt(s, certain)

    def _stmt(self, s: ast.stmt, certain: bool) -> None:
        if isinstance(s, ast.If):
            t = self.truth[s] = self.ev.truth(s.test, self.env)
            if t is not False:
                self._block(s.body, certain and t is True)
            if t is not True:
                self._block(s.orelse, certain and t is False)
        elif isinstance(s, ast.While):
            t = self.truth[s] = self.ev.truth(s.test, self.env)
            if t is not False:
                self._block(s.body, False)
            self._block(s.orelse, certain and t is False)
        elif isinstance(s, ast.Import):
            for a in s.names:
                bound = a.asname or a.name.partition(".")[0]
                self._bind(bound, _ModuleRef(a.name if a.asname else bound), certain)
        elif isinstance(s, ast.ImportFrom) and any(a.name == "*" for a in s.names):
            for k in [k for k in self.env if not k.startswith("_")]:
                self._bind(k, UNKNOWN, certain)
        elif isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name):
            self._bind(s.targets[0].id, self.ev.value(s.value, self.env), certain)
        elif isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
            if s.value is not None:
                self._bind(s.target.id, self.ev.value(s.value, self.env), certain)
        elif isinstance(s, (ast.For, ast.AsyncFor, ast.With, ast.AsyncWith, ast.Try, ast.TryStar, ast.Match)):
            for name in _names_in(s):
                self._bind(name, UNKNOWN, False)
            for block in _blocks(s):
                self._block(block, False)       # records the truth of nested guards
        else:
            for name in _names_in(s):
                self._bind(name, UNKNOWN, certain)


def _blocks(s: ast.stmt) -> list[list[ast.stmt]]:
    if isinstance(s, (ast.Try, ast.TryStar)):
        return [s.body, *(h.body for h in s.handlers), s.orelse, s.finalbody]
    if isinstance(s, ast.Match):
        return [c.body for c in s.cases]
    if isinstance(s, (ast.For, ast.AsyncFor)):
        return [s.body, s.orelse]
    if isinstance(s, (ast.With, ast.AsyncWith)):
        return [s.body]
    return []


# ------------------------------------------------------------------------------------------
# Static scan
# ------------------------------------------------------------------------------------------

class _Ctx(NamedTuple):
    lazy: bool = False                     # inside a function body
    guarded: bool = False                  # under a guard the closed world cannot evaluate, or in a handler
    optional: bool = False                 # under try/except ImportError or suppress(ImportError)
    dead: bool = False                     # under a guard that is false on the target platform
    local: frozenset[str] = frozenset()    # names bound by the enclosing function and class bodies


class _Scanner:
    """Collect import edges from one module's AST with their execution class."""

    def __init__(self, module: str, is_package: bool, platform: Platform | None = None) -> None:
        self.module = module
        self.package = module if is_package else module.rpartition(".")[0]
        self.ev = _Evaluator(platform or Platform(), module)
        self.menv: _ModuleEnv | None = None
        self.edges: list[tuple[str, str, int]] = []   # (target, cls, line)
        self.dynamic_unknown: list[int] = []

    def scan(self, tree: ast.AST) -> None:
        if isinstance(tree, ast.Module):
            self.menv = _ModuleEnv(self.ev, tree)
        self._children(tree, _Ctx())

    # -- context tracking -----------------------------------------------------------------
    def _children(self, node: ast.AST, ctx: _Ctx) -> None:
        for child in ast.iter_child_nodes(node):
            self._visit(child, ctx)

    def _guard(self, node: ast.If | ast.IfExp | ast.While, ctx: _Ctx) -> object:
        if self.menv is not None and node in self.menv.truth:
            return self.menv.truth[node]          # module level: the names bound so far
        env: dict[str, object] = dict(self.menv.final) if self.menv is not None else {"__name__": self.module}
        for name in ctx.local:
            env.pop(name, None)
        return self.ev.truth(node.test, env)

    @staticmethod
    def _branches(t: object, ctx: _Ctx) -> tuple[_Ctx, _Ctx]:
        """Contexts of the body and the else branch under a guard whose truth is t."""
        if t is True:
            return ctx, ctx._replace(dead=True)
        if t is False:
            return ctx._replace(dead=True), ctx
        return ctx._replace(guarded=True), ctx._replace(guarded=True)

    def _visit(self, node: ast.AST, ctx: _Ctx) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                self._add_dotted(alias.name, ctx, node.lineno)
            return
        if isinstance(node, ast.ImportFrom):
            self._add_from(node, ctx)
            return
        if isinstance(node, ast.Call):
            self._maybe_dynamic(node, ctx)
            self._children(node, ctx)
            return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            # decorators and defaults run at definition time; the body runs later
            for part in getattr(node, "decorator_list", []):
                self._visit(part, ctx)
            args = node.args
            for d in list(args.defaults) + [d for d in args.kw_defaults if d is not None]:
                self._visit(d, ctx)
            inner = ctx._replace(lazy=True, local=ctx.local | _locals_of(node))
            for stmt in node.body if isinstance(node.body, list) else [node.body]:
                self._visit(stmt, inner)
            return
        if isinstance(node, ast.ClassDef):
            # the class body runs at definition time, with its own names shadowing the module's
            for part in [*node.decorator_list, *node.bases, *(k.value for k in node.keywords)]:
                self._visit(part, ctx)
            inner = ctx._replace(local=ctx.local | _locals_of(node))
            for stmt in node.body:
                self._visit(stmt, inner)
            return
        if isinstance(node, (ast.If, ast.IfExp)):
            self._visit(node.test, ctx)
            body_ctx, else_ctx = self._branches(self._guard(node, ctx), ctx)
            for part in node.body if isinstance(node.body, list) else [node.body]:
                self._visit(part, body_ctx)
            for part in node.orelse if isinstance(node.orelse, list) else [node.orelse]:
                self._visit(part, else_ctx)
            return
        if isinstance(node, ast.While):
            self._visit(node.test, ctx)
            t = self._guard(node, ctx)
            body_ctx, else_ctx = self._branches(t, ctx)
            if t is True:
                else_ctx = ctx._replace(guarded=True)  # runs only if the loop ends normally
            for stmt in node.body:
                self._visit(stmt, body_ctx)
            for stmt in node.orelse:
                self._visit(stmt, else_ctx)
            return
        if isinstance(node, ast.Match):
            self._visit(node.subject, ctx)
            for case in node.cases:
                for stmt in case.body:
                    self._visit(stmt, ctx._replace(guarded=True))
            return
        if isinstance(node, (ast.Try, ast.TryStar)):
            optional = any(_handler_catches_import_error(h) for h in node.handlers)
            for stmt in node.body:
                self._visit(stmt, ctx._replace(optional=True) if optional else ctx)
            for h in node.handlers:                  # a handler runs only when the body failed
                for stmt in h.body:
                    self._visit(stmt, ctx._replace(guarded=True))
            for stmt in node.orelse + node.finalbody:
                self._visit(stmt, ctx)
            return
        if isinstance(node, (ast.With, ast.AsyncWith)):
            suppressing = any(_is_suppress_import_error(item.context_expr) for item in node.items)
            for item in node.items:
                self._visit(item.context_expr, ctx)
            for stmt in node.body:
                self._visit(stmt, ctx._replace(optional=True) if suppressing else ctx)
            return
        self._children(node, ctx)

    # -- edge construction ----------------------------------------------------------------
    @staticmethod
    def _cls(ctx: _Ctx) -> str:
        if ctx.dead:
            return DEAD
        if ctx.optional:
            return OPTIONAL
        if ctx.lazy:
            return LAZY
        return GUARDED if ctx.guarded else EAGER

    def _add_dotted(self, dotted: str, ctx: _Ctx, line: int) -> None:
        parts = dotted.split(".")
        for i in range(1, len(parts) + 1):
            self.edges.append((".".join(parts[:i]), self._cls(ctx), line))

    def _add_from(self, node: ast.ImportFrom, ctx: _Ctx) -> None:
        if node.level == 0:
            base = node.module or ""
        else:
            try:
                base = importlib.util.resolve_name("." * node.level + (node.module or ""), self.package)
            except (ImportError, ValueError):
                return
        if base == "__future__":
            return
        if base:
            self._add_dotted(base, ctx, node.lineno)
        for alias in node.names:
            if alias.name == "*":
                continue
            candidate = f"{base}.{alias.name}" if base else alias.name
            kind, _ = classify(candidate)
            if kind != "missing":
                self.edges.append((candidate, self._cls(ctx), node.lineno))

    def _maybe_dynamic(self, node: ast.Call, ctx: _Ctx) -> None:
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
            cls = DEAD if ctx.dead else OPTIONAL if ctx.optional else DYNAMIC
            self.edges.append((target, cls, node.lineno))
        elif not ctx.dead:
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


def scan_module(name: str, path: str, platform: Platform) -> tuple[list[Edge], list[int]]:
    try:
        tree = ast.parse(Path(path).read_text(encoding="utf-8", errors="replace"), filename=path)
    except SyntaxError:
        return [], []
    scanner = _Scanner(name, _is_package_path(path), platform)
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

def _static_reach(starts: set[str], classes: set[str], platform: Platform) -> set[str]:
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
            edges, _ = scan_module(name, path, platform)
            for e in edges:
                if e.cls in classes and e.target not in seen:
                    queue.append(e.target)
    return seen


def compute_closure(manifest: Manifest) -> tuple[dict[str, ModuleInfo], list[str]]:
    infos: dict[str, ModuleInfo] = {}
    problems: list[str] = []
    queue: deque[tuple[str, str | None]] = deque((r, None) for r in manifest.roots)
    optional_outside: dict[str, set[str]] = {}
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
                info.edges, info.dynamic_unknown_lines = scan_module(name, path, manifest.platform)
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
            if e.cls in FOLLOWED_CLASSES:
                queue.append((e.target, via))
            elif e.cls == LAZY:
                if e.target in manifest.supported:
                    queue.append((e.target, via))
                else:
                    lazy_outside.setdefault(e.importer, set()).add((e.target, e.line))
            elif e.cls == OPTIONAL:
                if e.target in manifest.supported:
                    queue.append((e.target, via))
                else:
                    optional_outside.setdefault(e.importer, set()).add(e.target)
            # DEAD: never executed on the target platform; kept in the lock, never followed

    # modules that load only because an omitted optional import succeeded on this machine
    omitted_targets = {t for ts in manifest.omissions.values() for t in ts}
    omitted_closure = _static_reach(omitted_targets, FOLLOWED_CLASSES, manifest.platform) - manifest.supported

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
    for importer, targets in sorted(optional_outside.items()):
        declared = manifest.omissions.get(importer, set())
        for t in sorted(targets):
            if t in declared:
                continue
            kind, _ = classify(t)
            if kind == "missing":
                continue  # unavailable on this platform anyway (e.g. msvcrt on Linux)
            problems.append(f"{importer}: optional import of {t} outside the manifest and not declared in [omissions]")
    # [omissions] holds imports under an ImportError guard and nothing else (review log D-3)
    optional_edges = {(e.importer, e.target) for i in infos.values() for e in i.edges if e.cls == OPTIONAL}
    for importer, omitted in sorted(manifest.omissions.items()):
        if importer not in infos:
            continue
        for t in sorted(omitted):
            if (importer, t) not in optional_edges:
                problems.append(f"{importer}: [omissions] lists {t}, which {importer} does not import under an "
                                f"ImportError guard (an import dead on the target needs no entry; a lazy one "
                                f"belongs in [lazy_unsupported])")
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
    # the guards were evaluated with the [platform] facts and the observation ran here: they must agree
    for m in manifest.platform.mismatches():
        problems.append(f"[platform]: {m}" if pinned else f"note: [platform]: {m} (unpinned run)")
    notes = [p for p in problems if p.startswith("note:")]
    errors = [p for p in problems if not p.startswith("note:")]

    lock = {
        "python": running,
        "pinned": pinned,
        "authoritative": pinned,
        "stdlib_dir": str(STDLIB_DIR),
        "roots": manifest.roots,
        "platform": manifest.platform.facts | {
            "builtin_modules_present": sorted(manifest.platform.builtin_present),
            "builtin_modules_absent": sorted(manifest.platform.builtin_absent),
        },
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
