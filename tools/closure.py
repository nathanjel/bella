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
   whatever really loads at import time, including through import hooks. Every module in
   `[omissions]` is blocked first (`sys.modules[name] = None`), so the importers take the
   fallback paths phase 1 takes. A module seen only here is scanned and followed like any other.
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
     first-use a PEP 810 `lazy import`, or a module-level import of a module listed in
               `__lazy_modules__` at that point (outside `try` and class bodies, checked per
               imported module, as CPython 3.15.2 does): the module is initialised when the bound
               name is first used. Followed like an eager edge (spec section 7: a module an
               import-time observation does not show can still be needed at first use). The lock
               is an inventory; the compiler takes laziness from each import statement itself.
               `__lazy_modules__` in any other form than a literal assigned at module level is an
               error, since the closure could not tell which imports are lazy.
   Every edge records the qualified name of the function it sits in ("" at module level).
3. Transitive closure. Eager, guarded, first-use and dynamic edges are always followed. A lazy edge is
   followed when its target is in the manifest; otherwise the importing function must be
   declared unsupported in `[lazy_unsupported]` -- the "support per API" the second review
   asked for (difflib._test imports doctest; that does not make doctest a phase-1 dependency,
   it makes difflib._test unsupported). An optional edge is followed when its target is in the
   manifest; otherwise it must appear in `[omissions]` (the import resolves to ImportError at
   runtime, as if not installed), and `[omissions]` may hold nothing else; neither table may
   name a module the manifest provides. Modules with status `core` or `shim` are provided by
   the runtime and are not scanned: a shim replaces the real module, so the real module's
   imports do not count. Likewise a function listed in `[replaced]` is replaced by the
   adaptation its module has in `[adaptations]`, so its imports do not count either.
   An import with a computed name (`__import__(name)`) is a lookup in the closed world at
   runtime (spec section 3). Every such site is reviewed in `[dynamic.<module>]` under the key
   "<function>: <name expression>", with the modules the lookup must find in phase 1 (followed
   as dynamic edges, parent packages included) or `[]`; a new site and a stale entry are errors.
   No exemption exists for a module missing on this machine: an optional import of it needs an
   `[omissions]` entry, and an unguarded one in a function a `[lazy_unsupported]` entry, unless
   the guard analysis proves the import dead.
4. Compare with manifest.toml and write closure.lock.json. Exit 1 on any gap. The lock lists,
   per module, the functions that `[lazy_unsupported]` makes unsupported.

Target programs (`targets/targets.toml`, review log D-2 as refined on 2026-11-01): `--target NAME`
computes one program's closure. Its driver is the root, and the program's own code (the driver
and its vendored libraries) has status `program`: it is compiled with the program, not taken
from the manifest. `--all-targets` writes every target's lock under `targets/closure/` and
`targets/closure-summary.json`, which derives the phase-1 increments: 1a is what the easy
programs reach, 1b what the tricky ones add, 1c the rest of the manifest.

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
import tempfile
import tomllib
from collections import Counter, deque
from collections.abc import Collection
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import NamedTuple, cast

EAGER = "eager"              # module level, unconditional (or under a guard true on the target)
GUARDED = "guarded"          # module level, under a guard the closed world cannot evaluate: required
LAZY = "lazy"                # inside a function body: executed when the function runs
OPTIONAL = "optional"        # under try/except ImportError or suppress(ImportError)
DEAD = "dead"                # under a guard false on the target platform: never executed
DYNAMIC = "dynamic"          # importlib.import_module / __import__ with a literal name
DYNAMIC_UNKNOWN = "dynamic-unknown"  # same, with a computed name: reported, not followed
FIRST_USE = "first-use"      # PEP 810 lazy import at module level: initialised at first use of the name
REPLACED = "replaced"        # inside a function an adaptation replaces ([replaced]): never executed
RUNTIME = "runtime"          # observed in sys.modules after importing the roots, not seen statically

FOLLOWED_CLASSES = {EAGER, GUARDED, FIRST_USE, DYNAMIC}   # required whatever the manifest says
PROGRAM = "program"          # status of a target program's own modules: compiled with the program
REPO = Path(__file__).resolve().parents[1]
TARGETS_FILE = REPO / "targets" / "targets.toml"
MANIFEST_STATUSES = ("compiled", "mapped", "core", "shim")
IMPORT_ERROR_NAMES = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}


@dataclass(frozen=True)
class Edge:
    importer: str
    target: str
    cls: str
    line: int
    func: str = ""                  # qualified name of the enclosing function; "" at module level


@dataclass(frozen=True)
class Program:
    """A target program: the driver module is the root; `dirs` hold the program's own code (the
    driver and its vendored libraries), searched first and compiled with the program."""

    name: str
    level: str                # easy | tricky
    root: str                 # module name of the driver
    dirs: tuple[Path, ...]    # searched first: the driver's directory and the vendored libraries
    tables: dict[str, object] = field(default_factory=dict)   # [<target>.closure] in targets.toml
    owned: tuple[Path, ...] = ()   # the driver and its declared packages; () means everything under dirs
    argv: tuple[str, ...] = ()     # how the target is run (targets.toml), for the runtime observation
    cwd: Path | None = None

    @classmethod
    def load(cls, name: str, targets_file: Path = TARGETS_FILE) -> Program:
        spec = tomllib.loads(targets_file.read_text(encoding="utf-8"))[name]
        here = targets_file.parent
        driver = here / spec["driver"]
        vendor = here / "vendor"
        # only the packages targets.toml declares belong to the program (review 2026-11-01, G3 3.2)
        owned = (driver, *(p for pkg in spec["packages"] for p in (vendor / pkg, vendor / f"{pkg}.py")))
        return cls(name, spec["level"], driver.stem, (driver.parent, vendor), dict(spec.get("closure", {})),
                   owned, tuple(spec["argv"]), here)

    @property
    def driver(self) -> Path:
        return self.dirs[0] / f"{self.root}.py"

    def manifest_for(self, manifest: Manifest) -> Manifest:
        """The manifest with this program's own declarations added: its `omissions`,
        `lazy_unsupported` and `dynamic` entries for the program's modules."""
        omissions = cast(dict[str, list[str]], self.tables.get("omissions", {}))
        lazy = cast(dict[str, list[str]], self.tables.get("lazy_unsupported", {}))
        dynamic = cast(dict[str, dict[str, list[str]]], self.tables.get("dynamic", {}))
        return replace(
            manifest,
            omissions=manifest.omissions | {k: manifest.omissions.get(k, set()) | set(v) for k, v in omissions.items()},
            lazy_unsupported=manifest.lazy_unsupported
            | {k: manifest.lazy_unsupported.get(k, set()) | set(v) for k, v in lazy.items()},
            dynamic=manifest.dynamic
            | {k: manifest.dynamic.get(k, {}) | {site: list(ts) for site, ts in v.items()} for k, v in dynamic.items()},
        )

    def owns(self, path: str | None) -> bool:
        if path is None:
            return False
        p = Path(path).resolve()
        if not self.owned:
            return any(p.is_relative_to(d.resolve()) for d in self.dirs)
        return any(p == o.resolve() or p.is_relative_to(o.resolve()) for o in self.owned)


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
    replaced: dict[str, set[str]] = field(default_factory=dict)    # module -> functions an adaptation replaces
    dynamic: dict[str, dict[str, list[str]]] = field(default_factory=dict)   # module -> site key -> modules it reaches

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
            replaced={k: set(v) for k, v in data.get("replaced", {}).items()},
            dynamic={k: {site: list(ts) for site, ts in v.items()} for k, v in data.get("dynamic", {}).items()},
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
                if key == "typing.TYPE_CHECKING":
                    return False          # PEP 484: false whenever the program runs
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
        # PEP 810: the __lazy_modules__ in effect at each module-level import (a frozenset, or
        # UNKNOWN when the module binds it in a form the closure cannot follow)
        self.lazy_policy: dict[ast.AST, object] = {}
        self._lazy: object = frozenset()
        self._in_try = False
        nested = (n for d in ast.walk(tree)
                  if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef))
                  for n in ast.walk(d))
        if any(isinstance(n, ast.Name) and n.id == "__lazy_modules__" for n in nested):
            self._lazy = UNKNOWN          # a function or class body may change it while the module runs
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
        if isinstance(s, (ast.Import, ast.ImportFrom)):
            self.lazy_policy[s] = frozenset() if self._in_try else self._lazy
        if not isinstance(s, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.With, ast.AsyncWith, ast.Try,
                              ast.TryStar, ast.Match, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            literal = _literal_lazy_modules(s)
            if literal is not None:
                self._lazy = literal if certain else UNKNOWN
            elif _mentions(s, "__lazy_modules__"):
                self._lazy = UNKNOWN      # mutated, deleted or rebound to something not literal
        elif isinstance(s, (ast.If, ast.While)) and _mentions(s.test, "__lazy_modules__"):
            self._lazy = UNKNOWN
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
        elif isinstance(s, ast.ImportFrom) and s.module == "typing" and s.level == 0 and \
                any(a.name == "TYPE_CHECKING" for a in s.names):
            for a in s.names:             # `from typing import TYPE_CHECKING`: false whenever the program runs
                self._bind(a.asname or a.name, False if a.name == "TYPE_CHECKING" else UNKNOWN, certain)
        elif isinstance(s, ast.ImportFrom) and any(a.name == "*" for a in s.names):
            exported = _star_exports(s.module) if s.level == 0 and s.module else None
            for k in [k for k in self.env if (k in exported if exported is not None else not k.startswith("_"))]:
                self._bind(k, UNKNOWN, certain)
        elif isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name):
            self._bind(s.targets[0].id, self.ev.value(s.value, self.env), certain)
        elif isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
            if s.value is not None:
                self._bind(s.target.id, self.ev.value(s.value, self.env), certain)
        elif isinstance(s, (ast.For, ast.AsyncFor, ast.With, ast.AsyncWith, ast.Try, ast.TryStar, ast.Match)):
            for name in _names_in(s):
                self._bind(name, UNKNOWN, False)
            outer, self._in_try = self._in_try, self._in_try or isinstance(s, (ast.Try, ast.TryStar))
            for block in _blocks(s):
                self._block(block, False)       # records the truth of nested guards
            self._in_try = outer
        else:
            for name in _names_in(s):
                self._bind(name, UNKNOWN, certain)


def _literal_lazy_modules(s: ast.stmt) -> frozenset[str] | None:
    """`__lazy_modules__ = [...]` of string literals (PEP 810 compatibility form), else None."""
    if (isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name)
            and s.targets[0].id == "__lazy_modules__" and isinstance(s.value, (ast.List, ast.Tuple, ast.Set))
            and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in s.value.elts)):
        return frozenset(e.value for e in s.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str))
    return None


def _mentions(node: ast.AST, name: str) -> bool:
    return any(isinstance(n, ast.Name) and n.id == name for n in ast.walk(node))


def _star_exports(module: str) -> frozenset[str] | None:
    """The names `from module import *` binds when the module is built in (importing it runs no
    Python code, and the tool runs on the target platform); None when the closure cannot know."""
    kind, _ = classify(module)
    if kind != "builtin":
        return None
    mod = importlib.import_module(module)
    names = getattr(mod, "__all__", None)
    return frozenset(names) if names is not None else frozenset(n for n in dir(mod) if not n.startswith("_"))


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
    first_use: bool = False                # a PEP 810 lazy import (module level only, by the grammar)
    in_try: bool = False                   # inside a try statement (__lazy_modules__ does not apply there)
    local: frozenset[str] = frozenset()    # names bound by the enclosing function and class bodies
    qual: str = ""                         # qualified name of the enclosing class or function
    func: str = ""                         # qualified name of the enclosing function ("" outside any)


class _Scanner:
    """Collect import edges from one module's AST with their execution class."""

    def __init__(self, module: str, is_package: bool, platform: Platform | None = None, as_main: bool = False) -> None:
        self.module = module
        self.package = module if is_package else module.rpartition(".")[0]
        # an entry script runs with __name__ == "__main__"; its identity (keys, relative imports) stays `module`
        self.ev = _Evaluator(platform or Platform(), "__main__" if as_main else module)
        self.menv: _ModuleEnv | None = None
        self.edges: list[tuple[str, str, int, str]] = []   # (target, cls, line, enclosing function)
        self.dynamic_unknown: list[tuple[int, str, str]] = []   # (line, enclosing function, name expression)
        self.functions: set[str] = set()                    # qualified names of every function defined
        self.lazy_policy_unknown: list[int] = []            # imports whose laziness the closure cannot tell

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
        env: dict[str, object] = dict(self.menv.final) if self.menv is not None else {"__name__": self.ev.module}
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

    def _lazy_binding(self, node: ast.Import | ast.ImportFrom, module: str, ctx: _Ctx) -> _Ctx:
        """PEP 810, per imported module: `lazy import`, or a module-level import (outside `try`
        and class bodies) of a module in the __lazy_modules__ in effect at that statement."""
        if getattr(node, "is_lazy", 0):
            return ctx._replace(first_use=True)
        if ctx.lazy or ctx.qual or ctx.in_try or self.menv is None:
            return ctx
        policy = self.menv.lazy_policy.get(node, frozenset())
        if policy is UNKNOWN:
            self.lazy_policy_unknown.append(node.lineno)
            return ctx
        assert isinstance(policy, frozenset)
        return ctx._replace(first_use=True) if module in policy else ctx

    @staticmethod
    def _qual(ctx: _Ctx, name: str) -> str:
        if not ctx.qual:
            return name
        return f"{ctx.qual}.<locals>.{name}" if ctx.func == ctx.qual and ctx.func else f"{ctx.qual}.{name}"

    def _visit(self, node: ast.AST, ctx: _Ctx) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                self._add_dotted(alias.name, self._lazy_binding(node, alias.name, ctx), node.lineno)
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
            q = self._qual(ctx, node.name if not isinstance(node, ast.Lambda) else "<lambda>")
            self.functions.add(q)
            # the body runs when called: a handler around the definition does not cover the call
            inner = ctx._replace(lazy=True, optional=False, in_try=False, local=ctx.local | _locals_of(node),
                                 qual=q, func=q)
            for stmt in node.body if isinstance(node.body, list) else [node.body]:
                self._visit(stmt, inner)
            return
        if isinstance(node, ast.ClassDef):
            # the class body runs at definition time, with its own names shadowing the module's
            for part in [*node.decorator_list, *node.bases, *(k.value for k in node.keywords)]:
                self._visit(part, ctx)
            inner = ctx._replace(local=ctx.local | _locals_of(node), qual=self._qual(ctx, node.name))
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
            tctx = ctx._replace(in_try=True)
            for stmt in node.body:
                self._visit(stmt, tctx._replace(optional=True) if optional else tctx)
            for h in node.handlers:                  # a handler runs only when the body failed
                for stmt in h.body:
                    self._visit(stmt, tctx._replace(guarded=True))
            for stmt in node.orelse + node.finalbody:
                self._visit(stmt, tctx)
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
        if ctx.first_use:
            return FIRST_USE
        if ctx.optional:
            return OPTIONAL
        if ctx.lazy:
            return LAZY
        return GUARDED if ctx.guarded else EAGER

    def _add_dotted(self, dotted: str, ctx: _Ctx, line: int) -> None:
        parts = dotted.split(".")
        for i in range(1, len(parts) + 1):
            self.edges.append((".".join(parts[:i]), self._cls(ctx), line, ctx.func))

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
        ctx = self._lazy_binding(node, base, ctx)
        if base:
            self._add_dotted(base, ctx, node.lineno)
        for alias in node.names:
            if alias.name == "*":
                continue
            candidate = f"{base}.{alias.name}" if base else alias.name
            kind, _ = classify(candidate)
            if kind != "missing":
                self.edges.append((candidate, self._cls(ctx), node.lineno, ctx.func))

    def _maybe_dynamic(self, node: ast.Call, ctx: _Ctx) -> None:
        fn = node.func
        name = None
        if isinstance(fn, ast.Name) and fn.id in ("__import__", "import_module"):
            name = fn.id                  # also `from importlib import import_module; import_module(x)`
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
            # inside a function the import runs when it is called, as an import statement there would
            cls = DEAD if ctx.dead else OPTIONAL if ctx.optional else LAZY if ctx.lazy else DYNAMIC
            for parent in _dotted(target):               # importing a.b imports a first
                self.edges.append((parent, cls, node.lineno, ctx.func))
        elif not ctx.dead:
            self.dynamic_unknown.append((node.lineno, ctx.func, ast.unparse(first)))


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


def _dotted(name: str) -> list[str]:
    """`a.b.c` -> a, a.b, a.b.c: importing a submodule imports every parent package first."""
    parts = name.split(".")
    return [".".join(parts[:i]) for i in range(1, len(parts) + 1)]


def site_key(func: str, expr: str) -> str:
    """The [dynamic] key of an import with a computed name: its function and name expression."""
    return f"{func or '<module>'}: {expr}"


@dataclass
class Scan:
    edges: list[Edge] = field(default_factory=list)
    dynamic_unknown: list[tuple[int, str, str]] = field(default_factory=list)   # (line, function, expression)
    functions: set[str] = field(default_factory=set)
    lazy_policy_unknown: list[int] = field(default_factory=list)


def _inside(func: str, replaced: Collection[str]) -> bool:
    return any(func == f or func.startswith(f + ".") for f in replaced)


def scan_module(name: str, path: str, platform: Platform, replaced: Collection[str] = (), as_main: bool = False) -> Scan:
    """Edges of one module. Imports inside a function in `replaced` become REPLACED edges.
    `as_main`: the module is a program's entry script, so `__name__ == "__main__"` (A4-1)."""
    try:
        tree = ast.parse(Path(path).read_text(encoding="utf-8", errors="replace"), filename=path)
    except SyntaxError:
        return Scan()
    scanner = _Scanner(name, _is_package_path(path), platform, as_main)
    scanner.scan(tree)
    edges = [Edge(name, t, REPLACED if _inside(f, replaced) else c, line, f) for (t, c, line, f) in scanner.edges]
    unknown = [(line, f, x) for (line, f, x) in scanner.dynamic_unknown if not _inside(f, replaced)]
    return Scan(edges, unknown, scanner.functions, scanner.lazy_policy_unknown)


# ------------------------------------------------------------------------------------------
# Dynamic observation
# ------------------------------------------------------------------------------------------

def observe_runtime_imports(roots: list[str], blocked: list[str] | tuple[str, ...] = (),
                            search: list[str] | tuple[str, ...] = ()) -> dict[str, list[str]]:
    """Import every root in a fresh isolated interpreter, with the omitted modules blocked so that
    their importers take the fallback paths phase 1 takes; return what each root pulled in.
    `search` goes first on sys.path (a target program's own directories)."""
    code = r"""
import json, sys
roots = json.loads(sys.argv[1])
sys.path[0:0] = json.loads(sys.argv[3])
for name in json.loads(sys.argv[2]):
    sys.modules[name] = None      # an omission resolves to ImportError, as in phase 1
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
        [sys.executable, "-I", "-c", code, json.dumps(roots), json.dumps(list(blocked)), json.dumps(list(search))],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"runtime observation failed:\n{proc.stderr}")
    data = json.loads(proc.stdout)
    per_root: dict[str, list[str]] = data["per_root"]
    return per_root


def observe_program_run(program: Program, blocked: list[str] | tuple[str, ...] = ()) -> list[str]:
    """Run a target program as its harness does (`__main__`, its arguments, its directory), with the
    omitted modules blocked; return every module it loaded. This covers execution, not just import
    (review 2026-11-01, A4-1); the static scan covers the paths this run does not take."""
    # The script runs in a fresh __main__ module with compile() and exec(), not runpy, which would
    # import modules of its own (pkgutil) after the snapshot and blame them on the program.
    code = r"""
import json, sys
driver, argv, search, blocked, out = json.loads(sys.argv[1])
sys.path[0:0] = search
for name in blocked:
    sys.modules[name] = None
with open(driver, encoding="utf-8") as f:
    source = f.read()
main = type(sys)("__main__")
main.__file__ = driver
before = set(sys.modules)
sys.modules["__main__"] = main
sys.argv = [driver, *argv]
failure = None
try:
    exec(compile(source, driver, "exec"), main.__dict__)
except SystemExit:
    pass
except BaseException as exc:  # report, never hide
    failure = "%s: %s" % (type(exc).__name__, exc)
loaded = sorted(set(sys.modules) - before)
with open(out, "w", encoding="utf-8") as f:
    json.dump({"loaded": loaded, "failure": failure}, f)
"""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp, "loaded.json")
        args = [str(program.driver), list(program.argv), [str(d) for d in program.dirs], list(blocked), str(out)]
        subprocess.run([sys.executable, "-I", "-c", code, json.dumps(args)], cwd=program.cwd or program.dirs[0],
                       capture_output=True, text=True, check=False, timeout=600)
        if not out.exists():
            return [f"<run failed: no result from {program.driver.name}>"]
        data = json.loads(out.read_text(encoding="utf-8"))
    loaded: list[str] = data["loaded"]
    return loaded + ([f"<run failed: {data['failure']}>"] if data["failure"] else [])


# ------------------------------------------------------------------------------------------
# Closure
# ------------------------------------------------------------------------------------------

def compute_closure(manifest: Manifest, program: Program | None = None) -> tuple[dict[str, ModuleInfo], list[str]]:
    """The closure of the manifest's roots, or of one target program."""
    if program is None:
        return _compute_closure(manifest, None)
    search = [str(d) for d in program.dirs]
    sys.path[0:0] = search
    importlib.invalidate_caches()
    try:
        return _compute_closure(program.manifest_for(manifest), program)
    finally:
        del sys.path[:len(search)]
        for name in [m for m, mod in sys.modules.items() if program.owns(getattr(mod, "__file__", None))]:
            del sys.modules[name]


def _compute_closure(manifest: Manifest, program: Program | None) -> tuple[dict[str, ModuleInfo], list[str]]:
    infos: dict[str, ModuleInfo] = {}
    problems: list[str] = []
    roots = [program.root] if program else manifest.roots
    queue: deque[tuple[str, str | None]] = deque((r, None) for r in roots)

    def supported(name: str) -> bool:
        return name in manifest.supported or (program is not None and program.owns(classify(name)[1]))
    processed: set[str] = set()
    optional_outside: dict[str, set[str]] = {}
    lazy_outside: dict[str, set[tuple[str, int, str]]] = {}
    functions: dict[str, set[str]] = {}
    unknown_sites: dict[str, list[tuple[int, str, str]]] = {}
    lazy_policy_unknown: dict[str, list[int]] = {}

    def ensure(name: str, reached_by: str | None) -> ModuleInfo:
        info = infos.get(name)
        if info is None:
            kind, path = classify(name)
            status = PROGRAM if program is not None and program.owns(path) else manifest.status_of(name)
            info = ModuleInfo(name=name, kind=kind, path=path, reached_by=reached_by, status=status)
            infos[name] = info
            # core and shim modules are provided by the runtime: their real source is not scanned
            if info.status not in ("core", "shim") and kind in ("source", "frozen") and path:
                scan = scan_module(name, path, manifest.platform, manifest.replaced.get(name, set()),
                                   as_main=program is not None and name == program.root)
                info.edges = scan.edges
                info.dynamic_unknown_lines = [line for line, _, _ in scan.dynamic_unknown]
                functions[name] = scan.functions
                unknown_sites[name] = scan.dynamic_unknown
                if scan.lazy_policy_unknown:
                    lazy_policy_unknown[name] = scan.lazy_policy_unknown
                # the modules a reviewed computed import must reach in phase 1 ([dynamic])
                for key, targets in sorted(manifest.dynamic.get(name, {}).items()):
                    func = key.partition(": ")[0]
                    for t in targets:
                        info.edges += [Edge(name, p, DYNAMIC, 0, "" if func == "<module>" else func)
                                       for p in _dotted(t)]
        return info

    def drain() -> None:
        """Process the queue to a fixed point. Every edge is accounted for, whether or not its
        target was reached before (review 2026-11-01, G2 3.1)."""
        while queue:
            name, reached_by = queue.popleft()
            if name in processed:
                continue
            processed.add(name)
            info = ensure(name, reached_by)
            for e in info.edges:
                follow = e.cls in FOLLOWED_CLASSES
                if e.cls in (LAZY, OPTIONAL):
                    if supported(e.target):
                        follow = True
                    elif e.cls == LAZY:
                        lazy_outside.setdefault(e.importer, set()).add((e.target, e.line, e.func))
                    else:
                        optional_outside.setdefault(e.importer, set()).add(e.target)
                # DEAD: never executed on the target platform; REPLACED: inside a function an
                # adaptation replaces. Both kept in the lock, never followed
                if follow and e.target not in processed:
                    queue.append((e.target, f"{e.importer}:{e.cls}:{e.line}"))

    drain()
    # dynamic observation, the omitted modules blocked: anything that loads at import time and
    # was not seen statically is processed like any other module (review 2026-11-01, A3-1)
    blocked = sorted({t for ts in manifest.omissions.values() for t in ts})
    if program is not None:
        observed = {program.root: observe_program_run(program, blocked)}
    else:
        observed = observe_runtime_imports(roots, blocked)
    for root, loaded in observed.items():
        for mod in loaded:
            if mod.startswith("<import failed"):
                problems.append(f"root {root}: {mod}")
            elif mod not in processed:
                queue.append((mod, f"{root}:{RUNTIME}:0"))
    drain()

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
            if t not in declared:      # also when t is missing here: absence is not a decision (A3-2)
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
        for t, line, _func in sorted(lazy_targets):
            if t in declared:
                continue
            problems.append(f"{importer}:{line}: lazy import of {t} outside the manifest; add {t} to the manifest "
                            f"or declare the importing function unsupported in [lazy_unsupported]")
    # an omitted or lazily unsupported module must really be outside the manifest
    for table, entries in (("[omissions]", manifest.omissions), ("[lazy_unsupported]", manifest.lazy_unsupported)):
        for importer, targets in sorted(entries.items()):
            for t in sorted(targets & manifest.supported):
                problems.append(f"{table} lists {t} for {importer}, but the manifest provides {t} "
                                f"({manifest.status_of(t)}): remove one of the two")
    for importer, declared in sorted(manifest.lazy_unsupported.items()):
        if importer in infos:
            stale = declared - {t for t, _, _ in lazy_outside.get(importer, set())}
            for t in sorted(stale - manifest.supported):
                problems.append(f"[lazy_unsupported] lists {t} for {importer}, which {importer} does not import "
                                f"inside a function")
    # [replaced]: functions an adaptation replaces; they must exist, and the adaptation must be named
    for module, funcs in sorted(manifest.replaced.items()):
        if module not in infos:
            problems.append(f"[replaced] names {module}, which the closure does not reach")
            continue
        if module not in manifest.adaptations:
            problems.append(f"[replaced] names functions of {module}, which has no entry in [adaptations]")
        for f in sorted(funcs - functions.get(module, set())):
            problems.append(f"[replaced] names {module}.{f}, which {module} does not define")
    # [dynamic]: every import with a computed name has been reviewed, site by site (A3-5)
    for module, sites in sorted(unknown_sites.items()):
        reviewed = manifest.dynamic.get(module, {})
        for line, func, expr in sites:
            key = site_key(func, expr)
            if key not in reviewed:
                problems.append(f"{module}:{line}: import with a computed name; review it and add {json.dumps(key)} = "
                                f"[the modules it must reach in phase 1] under [dynamic.{_toml_key(module)}]")
    for module, reviewed in sorted(manifest.dynamic.items()):
        if program is not None and module not in infos:
            continue                      # a program reaches part of the manifest by design
        present = {site_key(f, x) for _, f, x in unknown_sites.get(module, [])}
        for key in sorted(set(reviewed) - present):
            problems.append(f"[dynamic.{_toml_key(module)}] reviews {json.dumps(key)}, which "
                            f"{'is not a site in ' + module if module in infos else 'the closure does not reach'}")
    # a declaration for a module the closure does not reach is stale or misspelt (review 2026-11-01, G3 3.1)
    if program is None:
        for table, entries in (("[omissions]", manifest.omissions), ("[lazy_unsupported]", manifest.lazy_unsupported)):
            for importer in sorted(entries):
                if importer not in infos:
                    problems.append(f"{table} has an entry for {importer}, which the closure does not reach")
    else:
        for table in ("omissions", "lazy_unsupported", "dynamic"):
            for module in sorted(cast(dict[str, object], program.tables.get(table, {}))):
                if module not in infos:
                    problems.append(f"[{program.name}.closure.{table}] has an entry for {module}, which the closure "
                                    f"does not reach")
    for module, lines in sorted(lazy_policy_unknown.items()):
        problems.append(f"{module}: __lazy_modules__ is not a literal list assigned at module level, so the closure "
                        f"cannot tell whether the imports at lines {', '.join(map(str, lines))} are lazy (PEP 810)")
    statuses = {"compiled": manifest.compiled, "mapped": manifest.mapped, "core": manifest.core,
                "shim": set(manifest.shim), "excluded": manifest.excluded}
    for module in sorted(set().union(*statuses.values())):
        listed = [k for k, v in statuses.items() if module in v]
        if len(listed) > 1:
            problems.append(f"{module} is listed under {' and '.join(listed)}: a module has one status")
    unreached = sorted(m for m in manifest.supported - manifest.core if m not in infos)
    if unreached and program is None:     # a program reaches a part of the manifest by design
        problems.append(f"note: {len(unreached)} manifest entries never reached: "
                        f"{', '.join(unreached[:12])}{'...' if len(unreached) > 12 else ''}")
    return infos, problems


def unsupported_functions(infos: dict[str, ModuleInfo], manifest: Manifest) -> dict[str, list[str]]:
    """The functions [lazy_unsupported] refuses: calling one raises the milestone-naming error on
    every path through it (spec section 7). An import inside a nested helper refuses the outermost
    function that contains it, the one a program can name (review 2026-11-01, G2 3.4.3)."""
    out: dict[str, set[str]] = {}
    for name, info in infos.items():
        declared = manifest.lazy_unsupported.get(name, set())
        for e in info.edges:
            if e.cls == LAZY and e.target in declared and e.target not in manifest.supported:
                out.setdefault(name, set()).add(e.func.partition(".<locals>.")[0])
    return {k: sorted(v) for k, v in sorted(out.items())}


def _toml_key(name: str) -> str:
    return json.dumps(name) if "." in name else name


def _stdlib_relative(path: str | None) -> str | None:
    """Paths in the lock are relative to the standard library (or, for a target program's own
    code, to the repository), so the lock is the same on every machine that runs the pinned build."""
    if path is None:
        return None
    for base in (STDLIB_DIR, REPO):
        try:
            return str(Path(path).resolve().relative_to(base.resolve()))
        except ValueError:
            continue
    return path


def _source_lines(info: ModuleInfo) -> int:
    if info.path is None or info.kind not in ("source", "frozen"):
        return 0
    return len(Path(info.path).read_text(encoding="utf-8", errors="replace").splitlines())


def increments(results: dict[str, tuple[Program, dict[str, ModuleInfo]]],
               manifest: Manifest) -> dict[str, dict[str, object]]:
    """The phase-1 increments as closures of the target programs (review log D-2, refined
    2026-11-01): 1a is what the easy programs reach in the manifest, 1b what the tricky ones add,
    1c the rest of the manifest. Each lists its modules with their status and source lines."""
    def reached(level: str) -> dict[str, ModuleInfo]:
        out: dict[str, ModuleInfo] = {}
        for program, infos in results.values():
            if program.level == level:
                out.update({n: i for n, i in infos.items() if i.status in MANIFEST_STATUSES})
        return out
    easy = reached("easy")
    tricky = {n: i for n, i in reached("tricky").items() if n not in easy}
    rest = {n: manifest.status_of(n) for n in sorted(manifest.supported) if n not in easy and n not in tricky}
    def describe(mods: dict[str, ModuleInfo]) -> dict[str, object]:
        by_status: dict[str, int] = {}
        for i in mods.values():
            by_status[i.status] = by_status.get(i.status, 0) + 1
        return {"modules": len(mods), "by_status": dict(sorted(by_status.items())),
                "compiled_source_lines": sum(_source_lines(i) for i in mods.values() if i.status == "compiled"),
                "list": {n: mods[n].status for n in sorted(mods)}}
    return {"1a": describe(easy), "1b": describe(tricky),
            "1c": {"modules": len(rest), "list": rest}}


# ------------------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------------------

def _lock(manifest: Manifest, infos: dict[str, ModuleInfo], errors: list[str], notes: list[str], pinned: bool,
          roots: list[str]) -> dict[str, object]:
    running = ".".join(map(str, sys.version_info[:3]))
    return {
        "python": running,
        "pinned": pinned,
        "authoritative": pinned,
        "build": sys.version,
        "stdlib_dir": "lib/python" + ".".join(map(str, sys.version_info[:2])) + " (paths below are relative to it)",
        "roots": roots,
        "platform": manifest.platform.facts | {
            "builtin_modules_present": sorted(manifest.platform.builtin_present),
            "builtin_modules_absent": sorted(manifest.platform.builtin_absent),
        },
        "module_count": len(infos),
        "errors": errors,
        "notes": notes,
        "unsupported_functions": unsupported_functions(infos, manifest),
        "modules": {
            n: {k: v for k, v in asdict(i).items() if k not in ("edges", "path")} | {
                "path": _stdlib_relative(i.path),
                "edges": [asdict(e) for e in i.edges],
            }
            for n, i in sorted(infos.items())
        },
    }


def _targets_main(args: argparse.Namespace, manifest: Manifest, pinned: bool) -> int:
    names = list(tomllib.loads(TARGETS_FILE.read_text(encoding="utf-8"))) if args.all_targets else [args.target]
    out_dir = REPO / "targets" / "closure"
    out_dir.mkdir(exist_ok=True)
    results: dict[str, tuple[Program, dict[str, ModuleInfo]]] = {}
    summary: dict[str, object] = {}
    errors_of: dict[str, list[str]] = {}
    for name in names:
        program = Program.load(name)
        infos, problems = compute_closure(manifest, program)
        problems += [f"[platform]: {m}" if pinned else f"note: [platform]: {m} (unpinned run)"
                     for m in manifest.platform.mismatches()]
        notes = [p for p in problems if p.startswith("note:")]
        errors = [p for p in problems if not p.startswith("note:")]
        (out_dir / f"{name}.lock.json").write_text(
            json.dumps(_lock(program.manifest_for(manifest), infos, errors, notes, pinned, [program.root]), indent=1) + "\n",
            encoding="utf-8")
        results[name] = (program, infos)
        by_status: dict[str, int] = {}
        for i in infos.values():
            by_status[i.status] = by_status.get(i.status, 0) + 1
        summary[name] = {"level": program.level, "by_status": dict(sorted(by_status.items())), "errors": errors}
        errors_of[name] = errors
        if not args.quiet:
            print(f"{name:24} {program.level:6} {len(infos):4} modules  "
                  + "  ".join(f"{s} {c}" for s, c in sorted(by_status.items()))
                  + (f"\n{'':24} {len(errors)} problem(s): " + "; ".join(errors) if errors else ""))
    if args.all_targets:
        running = ".".join(map(str, sys.version_info[:3]))
        incs = increments(results, manifest)
        data = {"python": running, "authoritative": pinned, "targets": summary, "increments": incs}
        (REPO / "targets" / "closure-summary.json").write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
        if not args.quiet:
            for inc, d in incs.items():
                print(f"increment {inc}: {d['modules']} modules"
                      + (f", {d['compiled_source_lines']} compiled source lines, {d['by_status']}" if "by_status" in d else ""))
            print("wrote targets/closure/*.lock.json and targets/closure-summary.json")
    # 1a must be closed: an easy target's problem fails the run; a tricky one's is reported
    open_easy = [n for n in names if results[n][0].level == "easy" and errors_of[n]]
    if open_easy:
        print(f"open: {', '.join(open_easy)}", file=sys.stderr)
    return 1 if open_easy else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--manifest", type=Path, default=Path("manifest.toml"))
    ap.add_argument("--out", type=Path, default=Path("closure.lock.json"))
    ap.add_argument("--allow-unpinned", action="store_true", help="run on a Python other than the pinned reference build")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--target", help="one target program of targets/targets.toml (its lock goes to targets/closure/)")
    ap.add_argument("--all-targets", action="store_true",
                    help="every target, then targets/closure-summary.json with the phase-1 increments")
    args = ap.parse_args(argv)

    manifest = Manifest.load(args.manifest)
    running = ".".join(map(str, sys.version_info[:3]))
    pinned = running == manifest.python
    if not pinned and not args.allow_unpinned:
        print(f"closure: refusing to run on Python {running}; the manifest is pinned to {manifest.python} "
              f"(use --allow-unpinned for a non-authoritative run)", file=sys.stderr)
        return 2

    if args.target or args.all_targets:
        return _targets_main(args, manifest, pinned)
    infos, problems = compute_closure(manifest)
    # the guards were evaluated with the [platform] facts and the observation ran here: they must agree
    for m in manifest.platform.mismatches():
        problems.append(f"[platform]: {m}" if pinned else f"note: [platform]: {m} (unpinned run)")
    notes = [p for p in problems if p.startswith("note:")]
    errors = [p for p in problems if not p.startswith("note:")]

    lock = _lock(manifest, infos, errors, notes, pinned, manifest.roots)
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
