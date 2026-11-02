#!/usr/bin/env python3
"""The compile scope of a target and the L1 frontier (Gate 0 task 4; review log D-10).

    python tools/scope.py --target cli_easy_slugs [--variant "--help" ...]

Two measurements, on the pinned interpreter:

* Scope. Every function the target's closure defines (each code object compiled from its
  modules' sources: functions, methods, lambdas, generator expressions, class and module
  bodies), against those the program executes, on its recorded run and on each variant's
  arguments (sys.monitoring PY_START). The closure is the inventory of what may run; what runs
  on the recorded inputs is a lower bound of what must compile.
* Frontier. Each executed function and module body is lowered on its own through the L1
  frontend (pipeline/l1/frontend.py), and what stops it is counted by the construct it names.
  This is the work list for the first compiled path, in the order the program needs it.

Writes targets/scope/<target>.json; prints a summary.
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import os
import subprocess
import sys
import tomllib
import types
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
TARGETS = REPO / "targets"
type Code = tuple[str, str, int]            # (real source path, co_qualname, co_firstlineno)


def _walk_codes(code: types.CodeType) -> list[types.CodeType]:
    found = [code]
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            found += _walk_codes(const)
    return found


def _lines(code: types.CodeType) -> set[int]:
    return {line for _, _, line in code.co_lines() if line is not None}


TRACE = r'''
import json, os, sys
executed = set()
def start(code, offset):
    executed.add((os.path.realpath(code.co_filename), code.co_qualname, code.co_firstlineno))
out, driver, *argv = sys.argv[1:]
sys.argv = [driver, *argv]
main = sys.modules["__main__"].__dict__
main.update(__file__=driver, __cached__=None)
code = compile(open(driver, "rb").read(), driver, "exec", dont_inherit=True)
sys.monitoring.use_tool_id(5, "bella-scope")
sys.monitoring.register_callback(5, sys.monitoring.events.PY_START, start)
sys.monitoring.set_events(5, sys.monitoring.events.PY_START)
try:
    exec(code, main)
except SystemExit:
    pass
finally:
    sys.monitoring.set_events(5, 0)
    # a module imported before monitoring began (at interpreter start-up) ran its body too
    for m in list(sys.modules.values()):
        f = getattr(m, "__file__", None)
        if f:
            executed.add((os.path.realpath(f), "<module>", 1))
    with open(out, "w") as f:
        json.dump(sorted(executed), f)
'''


def executed_codes(driver: str, argv: list[str], out: Path) -> set[tuple[str, str, int]]:
    """The code objects a run starts, by (file, qualname, first line)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
    env.update(PYTHONPATH=str(TARGETS / "vendor"), PYTHONHASHSEED="0", PYTHONUTF8="1")
    # frozen start-up modules (os, posixpath, codecs, ...) would hide behind "<frozen ...>" names
    subprocess.run([sys.executable, "-P", "-X", "frozen_modules=off", "-c", TRACE, str(out.resolve()), driver, *argv],
                   cwd=TARGETS, env=env,
                   capture_output=True, text=True, check=True)
    return {(f, q, int(n)) for f, q, n in json.loads(out.read_text(encoding="utf-8"))}


def _first_unsupported(source: str, filename: str) -> str | None:
    """What stops the L1 frontend on `source`, or None if it lowers."""
    from pipeline.l1 import frontend
    from pipeline.l1 import grammar as L
    try:
        frontend.lower(source, filename)
    except (L.Unsupported, L.DialectError) as exc:
        reason = str(exc).split(" (line")[0]
        if reason.startswith("parameter kinds of "):       # one construct, whichever function has it
            reason = "parameter kinds (positional-only, keyword-only, *args, **kwargs)"
        return reason
    except SyntaxError as exc:
        return f"SyntaxError {exc.msg}"
    except Exception as exc:  # noqa: BLE001  # the frontend's own failure is a frontier entry too
        return f"frontend error {type(exc).__name__}"
    return None


# ---- the construct census ---------------------------------------------------------------------
# Each construct: a sample that uses it and little else. "Lowers today" is the frontend's verdict
# on the sample, so the table cannot drift from pipeline/l1/frontend.py.
SAMPLES: dict[str, str] = {
    "def": "def f(): pass",
    "def: default values": "def f(a=1): pass",
    "def: positional-only parameters": "def f(a, /): pass",
    "def: keyword-only parameters": "def f(*, a): pass",
    "def: *args": "def f(*a): pass",
    "def: **kwargs": "def f(**k): pass",
    "def: annotations": "def f(a: int) -> int: pass",
    "def: decorators": "def d(f): return f\n@d\ndef f(): pass",
    "def: nested (closure)": "def f():\n    def g(): pass",
    "nonlocal": "def f():\n    x = 1\n    def g():\n        nonlocal x\n        x = 2",
    "global (in a function)": "def f():\n    global x\n    x = 1",
    "lambda": "f = lambda: 1",
    "yield (generator function)": "def f():\n    yield 1",
    "yield from": "def f():\n    yield from ()",
    "async/await": "async def f(): pass",
    "class": "class C: pass",
    "class: bases": "class C(object): pass",
    "class: keywords (metaclass=...)": "class C(metaclass=type): pass",
    "class: decorators": "def d(c): return c\n@d\nclass C: pass",
    "class: annotations": "class C:\n    x: int",
    "super() / __class__": "class C:\n    def f(self): super()",
    "type parameters (PEP 695)": "def f[T](): pass",
    "type alias (PEP 695)": "type A = int",
    "import": "import os",
    "import a.b": "import os.path",
    "import ... as": "import os as o",
    "from ... import": "from os import path",
    "from . import (relative)": "from . import x",
    "from ... import *": "from os import *",
    "lazy import (PEP 810)": "lazy import os",
    "assignment": "a = 1",
    "assignment: several targets": "a = b = 1",
    "assignment: tuple target": "a, b = 1, 2",
    "assignment: starred target": "a, *b = 1, 2",
    "assignment: attribute/subscript target": "o.a = 1",
    "augmented assignment": "a = 1\na += 1",
    "annotated assignment": "a: int = 1",
    "annotated name, no value": "a: int",
    "del": "a = 1\ndel a",
    "if": "if 1: pass",
    "while": "while 0: pass",
    "for": "for x in (): pass",
    "for/while else": "for x in (): pass\nelse: pass",
    "break/continue": "for x in (): break",
    "return": "def f(): return 1",
    "try/except": "try: pass\nexcept Exception: pass",
    "try/finally": "try: pass\nfinally: pass",
    "except*": "try: pass\nexcept* Exception: pass",
    "raise": "raise ValueError",
    "raise ... from": "raise ValueError from None",
    "assert": "assert 1",
    "with": "with open('x') as f: pass",
    "match": "match 1:\n    case 1: pass",
    "call: keyword arguments": "print(1, sep='')",
    "call: *args": "print(*())",
    "call: **kwargs": "print(**{})",
    "list/tuple display": "[1, (2,)]",
    "dict display": "{1: 2}",
    "set display": "{1}",
    "display: starred": "[*()]",
    "display: dict unpacking": "{**{}}",
    "list comprehension": "[x for x in ()]",
    "set comprehension": "{x for x in ()}",
    "dict comprehension": "{x: x for x in ()}",
    "generator expression": "(x for x in ())",
    "comprehension: several for/if": "[x for y in () for x in y if x]",
    "walrus": "(a := 1)",
    "f-string": "a = 1\nf'{a}'",
    "f-string: conversion/format spec": "a = 1\nf'{a!r:>3}'",
    "t-string": "a = 1\nt'{a}'",
    "subscript": "[1][0]",
    "slice": "[1][0:1]",
    "attribute": "(1).real",
    "comparison": "1 < 2",
    "chained comparison": "1 < 2 < 3",
    "and/or/not": "1 and not 2 or 3",
    "conditional expression": "1 if 2 else 3",
    "constant: int/float/str/bool/None": "1, 1.5, 's', True, None",
    "constant: bytes": "b'x'",
    "constant: Ellipsis": "...",
    "constant: complex": "1j",
}


def _features(unit: ast.AST) -> set[str]:
    """The constructs one unit uses in its own code: nested function and class bodies are units of
    their own, so only their header (decorators, defaults, bases) counts here."""
    out: set[str] = set()

    in_function = isinstance(unit, (ast.FunctionDef, ast.AsyncFunctionDef))

    def own(node: ast.AST, top: bool) -> None:
        if not top and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            header(node, nested=in_function)      # a def in a function is a closure; in a class or module it is not
            return
        if top and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            header(node, nested=False)
            for s in node.body:
                own(s, False)
            return
        classify(node)
        for child in ast.iter_child_nodes(node):
            own(child, False)

    def header(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef, nested: bool) -> None:
        if isinstance(node, ast.ClassDef):
            out.add("class")
            if node.bases:
                out.add("class: bases")
            if node.keywords:
                out.add("class: keywords (metaclass=...)")
            if node.decorator_list:
                out.add("class: decorators")
            if any(isinstance(s, ast.AnnAssign) for s in node.body):
                out.add("class: annotations")
            for e in [*node.bases, *(k.value for k in node.keywords), *node.decorator_list]:
                own(e, False)
        else:
            out.add("def")
            if isinstance(node, ast.AsyncFunctionDef):
                out.add("async/await")
            if nested:
                out.add("def: nested (closure)")
            a = node.args
            if a.defaults or any(d is not None for d in a.kw_defaults):
                out.add("def: default values")
            if a.posonlyargs:
                out.add("def: positional-only parameters")
            if a.kwonlyargs:
                out.add("def: keyword-only parameters")
            if a.vararg:
                out.add("def: *args")
            if a.kwarg:
                out.add("def: **kwargs")
            params = [*a.posonlyargs, *a.args, *a.kwonlyargs, *(x for x in (a.vararg, a.kwarg) if x)]
            if node.returns is not None or any(p.annotation is not None for p in params):
                out.add("def: annotations")
            if node.decorator_list:
                out.add("def: decorators")
            for e in [*a.defaults, *(d for d in a.kw_defaults if d is not None), *node.decorator_list]:
                own(e, False)
        if node.type_params:
            out.add("type parameters (PEP 695)")

    def classify(n: ast.AST) -> None:
        match n:
            case ast.Lambda():
                out.add("lambda")
            case ast.Yield():
                out.add("yield (generator function)")
            case ast.YieldFrom():
                out.add("yield from")
            case ast.Await() | ast.AsyncFor() | ast.AsyncWith():
                out.add("async/await")
            case ast.Nonlocal():
                out.add("nonlocal")
            case ast.Global():
                out.add("global (in a function)")
            case ast.TypeAlias():
                out.add("type alias (PEP 695)")
            case ast.Import(names=names):
                out.add("import")
                if getattr(n, "is_lazy", False):
                    out.add("lazy import (PEP 810)")
                if any("." in a.name for a in names):
                    out.add("import a.b")
                if any(a.asname for a in names):
                    out.add("import ... as")
            case ast.ImportFrom(level=level, names=names):
                out.add("from ... import")
                if getattr(n, "is_lazy", False):
                    out.add("lazy import (PEP 810)")
                if level:
                    out.add("from . import (relative)")
                if any(a.name == "*" for a in names):
                    out.add("from ... import *")
            case ast.Assign(targets=targets):
                out.add("assignment")
                if len(targets) > 1:
                    out.add("assignment: several targets")
                for t in targets:
                    target(t)
            case ast.AugAssign(target=t):
                out.add("augmented assignment")
                target(t)
            case ast.AnnAssign(value=value, target=t):
                out.add("annotated assignment" if value is not None else "annotated name, no value")
                target(t)
            case ast.For(target=t, orelse=orelse) | ast.AsyncFor(target=t, orelse=orelse):
                out.add("for")
                target(t)
                if orelse:
                    out.add("for/while else")
            case ast.While(orelse=orelse):
                out.add("while")
                if orelse:
                    out.add("for/while else")
            case ast.Delete():
                out.add("del")
            case ast.If():
                out.add("if")
            case ast.Break() | ast.Continue():
                out.add("break/continue")
            case ast.Return():
                out.add("return")
            case ast.Try(handlers=handlers, finalbody=finalbody):
                if handlers:
                    out.add("try/except")
                if finalbody:
                    out.add("try/finally")
            case ast.TryStar():
                out.add("except*")
            case ast.Raise(cause=cause):
                out.add("raise ... from" if cause is not None else "raise")
            case ast.Assert():
                out.add("assert")
            case ast.With() | ast.AsyncWith():
                out.add("with")
            case ast.Match():
                out.add("match")
            case ast.Call(args=args, keywords=keywords):
                if any(isinstance(x, ast.Starred) for x in args):
                    out.add("call: *args")
                if any(k.arg is None for k in keywords):
                    out.add("call: **kwargs")
                if any(k.arg is not None for k in keywords):
                    out.add("call: keyword arguments")
                if isinstance(n.func, ast.Name) and n.func.id == "super" or isinstance(n.func, ast.Name) and n.func.id == "__class__":
                    out.add("super() / __class__")
            case ast.Name(id="__class__"):
                out.add("super() / __class__")
            case ast.List(elts=elts) | ast.Tuple(elts=elts) | ast.Set(elts=elts):
                if isinstance(n, ast.Set):
                    out.add("set display")
                elif isinstance(n.ctx, ast.Load):
                    out.add("list/tuple display")
                if isinstance(n.ctx if not isinstance(n, ast.Set) else ast.Load(), ast.Load) and any(isinstance(x, ast.Starred) for x in elts):
                    out.add("display: starred")
            case ast.Dict(keys=keys):
                out.add("dict display")
                if any(k is None for k in keys):
                    out.add("display: dict unpacking")
            case ast.ListComp() | ast.SetComp() | ast.DictComp() | ast.GeneratorExp():
                out.add({ast.ListComp: "list comprehension", ast.SetComp: "set comprehension",
                         ast.DictComp: "dict comprehension", ast.GeneratorExp: "generator expression"}[type(n)])
                gens = n.generators
                if len(gens) > 1 or any(g.ifs for g in gens):
                    out.add("comprehension: several for/if")
            case ast.NamedExpr():
                out.add("walrus")
            case ast.JoinedStr(values=values):
                out.add("f-string")
                if any(isinstance(v, ast.FormattedValue) and (v.conversion != -1 or v.format_spec) for v in values):
                    out.add("f-string: conversion/format spec")
            case ast.TemplateStr():
                out.add("t-string")
            case ast.Subscript(slice=sl):
                out.add("subscript")
                if isinstance(sl, ast.Slice) or isinstance(sl, ast.Tuple) and any(isinstance(x, ast.Slice) for x in sl.elts):
                    out.add("slice")
            case ast.Attribute():
                out.add("attribute")
            case ast.Compare(ops=ops):
                out.add("comparison" if len(ops) == 1 else "chained comparison")
            case ast.BoolOp() | ast.UnaryOp(op=ast.Not()):
                out.add("and/or/not")
            case ast.IfExp():
                out.add("conditional expression")
            case ast.Constant(value=v):
                if isinstance(v, bytes):
                    out.add("constant: bytes")
                elif v is Ellipsis:
                    out.add("constant: Ellipsis")
                elif isinstance(v, complex):
                    out.add("constant: complex")
                else:
                    out.add("constant: int/float/str/bool/None")

    def target(t: ast.expr) -> None:
        if isinstance(t, (ast.Tuple, ast.List)):
            out.add("assignment: tuple target")
            if any(isinstance(x, ast.Starred) for x in t.elts):
                out.add("assignment: starred target")
        elif isinstance(t, (ast.Attribute, ast.Subscript)):
            out.add("assignment: attribute/subscript target")

    own(unit, True)
    unknown = out - SAMPLES.keys()
    assert not unknown, unknown
    return out


def lowers_today() -> dict[str, bool]:
    return {name: _first_unsupported(sample, f"<sample {name}>") is None for name, sample in SAMPLES.items()}


def _unit_nodes(source: str, filename: str) -> dict[tuple[str, int], ast.AST]:
    """Each code object's own node, keyed as CPython names it: (qualname, first line, which is the
    first decorator's for a decorated definition)."""
    tree = ast.parse(source, filename)
    units: dict[tuple[str, int], ast.AST] = {("<module>", 1): tree}

    def visit(body: list[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qual = f"{prefix}{node.name}"
                first = node.decorator_list[0].lineno if node.decorator_list else node.lineno
                units[(qual, first)] = node
                visit(node.body, f"{qual}." if isinstance(node, ast.ClassDef) else f"{qual}.<locals>.")
                continue
            for fld in ("body", "orelse", "finalbody"):
                inner = getattr(node, fld, None)
                if isinstance(inner, list):
                    visit(inner, prefix)
            for h in getattr(node, "handlers", []):
                visit(h.body, prefix)
            for case in getattr(node, "cases", []):
                visit(case.body, prefix)
    visit(tree.body, "")
    return units


def _unit_source(node: ast.AST) -> str:
    """A unit as a module of its own, for the frontend: a definition with its body, or the module
    body without the definitions at its top level (each of those is its own unit)."""
    if isinstance(node, ast.Module):
        return ast.unparse(ast.Module([s for s in node.body if not isinstance(
            s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))], []))
    assert isinstance(node, ast.stmt)
    return ast.unparse(ast.Module([node], []))


def closure_sources(lock: dict[str, Any]) -> dict[str, Path]:
    """The Python sources a stage compiles: its program, the compiled standard-library modules and
    the shims written so far (runtime/shims). Frozen aliases (os.path, collections.abc) have none."""
    stdlib = Path(os.path.dirname(os.__file__))
    paths: dict[str, Path] = {}
    for name, m in lock["modules"].items():
        path = m["path"]
        if not path:
            continue
        if m["status"] == "program" or (m["status"] == "shim" and path.startswith("runtime/")):
            paths[name] = (REPO / path).resolve()
        elif m["status"] == "compiled":
            paths[name] = (stdlib / path).resolve()
    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--target", required=True)
    ap.add_argument("--variant", action="append", default=[],
                    help='arguments of another run, quoted; --variant="--help" for one that starts with a dash')
    args = ap.parse_args(argv)
    spec = tomllib.loads((TARGETS / "targets.toml").read_text(encoding="utf-8"))[args.target]
    lock = json.loads((TARGETS / "closure" / f"{args.target}.lock.json").read_text(encoding="utf-8"))
    paths = closure_sources(lock)
    defined: dict[Code, int] = {}                       # code object -> lines it has
    module_of: dict[str, str] = {}
    nodes: dict[Code, ast.AST] = {}
    for name, path in paths.items():
        module_of[str(path)] = name
        source = path.read_bytes()
        for code in _walk_codes(compile(source, str(path), "exec", dont_inherit=True)):
            defined[(str(path), code.co_qualname, code.co_firstlineno)] = len(_lines(code))
        for (qual, first), node in _unit_nodes(source.decode("utf-8"), str(path)).items():
            nodes[(str(path), qual, first)] = node
    runs = {"recorded": list(spec["argv"])} | {v: v.split() for v in args.variant}
    executed: dict[str, set[Code]] = {}
    scratch = REPO / "build" / "scope"
    scratch.mkdir(parents=True, exist_ok=True)
    for label, run_argv in runs.items():
        executed[label] = {c for c in executed_codes(spec["driver"], run_argv, scratch / "run.json") if c in defined}
    union: set[Code] = set().union(*executed.values())

    # the frontend's verdict on each executed unit (a lambda or a generator expression is part of
    # the unit that contains it); a unit is lowered whole, so only its first blocker is seen
    blockers: collections.Counter[str] = collections.Counter()
    blocked_lines: collections.Counter[str] = collections.Counter()
    lowered = 0
    for key in sorted(union):
        if key not in nodes:
            continue
        reason = _first_unsupported(_unit_source(nodes[key]), key[0])
        if reason is None:
            lowered += 1
        else:
            blockers[reason] += 1
            blocked_lines[reason] += defined[key]

    # the census: every construct the units use, executed and in the whole closure
    verdict = lowers_today()
    used_exec: collections.Counter[str] = collections.Counter()
    used_all: collections.Counter[str] = collections.Counter()
    for key, node in nodes.items():
        for f in _features(node):
            used_all[f] += 1
            if key in union:
                used_exec[f] += 1
    census = [{"construct": k, "executed_units": used_exec[k], "closure_units": used_all[k], "lowers_today": verdict[k]}
              for k in sorted(SAMPLES, key=lambda k: (-used_exec[k], -used_all[k], k)) if used_all[k]]

    def lines(codes: set[Code]) -> int:
        return sum(defined[c] for c in codes)

    report = {
        "target": args.target,
        "python": ".".join(map(str, sys.version_info[:3])),
        "closure": {"modules": len(paths), "code_objects": len(defined), "lines": lines(set(defined))},
        "runs": {label: {"argv": runs[label], "code_objects": len(codes), "lines": lines(codes),
                         "modules": len({module_of[c[0]] for c in codes})} for label, codes in executed.items()},
        "union": {"code_objects": len(union), "lines": lines(union), "modules": sorted({module_of[c[0]] for c in union})},
        "frontend": {"units": lowered + sum(blockers.values()), "lower_to_L1": lowered,
                     "first_blocker": [{"construct": k, "units": n, "lines": blocked_lines[k]}
                                       for k, n in blockers.most_common()]},
        "census": census,
    }
    out = TARGETS / "scope" / f"{args.target}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")

    c = report["closure"]
    print(f"{args.target}: closure {c['modules']} modules, {c['code_objects']} code objects, {c['lines']} lines")
    for r in report["runs"].values():
        print(f"  run {' '.join(r['argv'])!r:48} {r['code_objects']:5} code objects ({r['code_objects'] / c['code_objects']:5.1%}), "
              f"{r['lines']:6} lines ({r['lines'] / c['lines']:5.1%}), {r['modules']} modules")
    u = report["union"]
    print(f"  {'all runs':52} {u['code_objects']:5} code objects ({u['code_objects'] / c['code_objects']:5.1%}), "
          f"{u['lines']:6} lines ({u['lines'] / c['lines']:5.1%}), {len(u['modules'])} modules")
    fr = report["frontend"]
    print(f"  frontend: {fr['lower_to_L1']} of {fr['units']} executed units lower to L1; the first blocker of the rest:")
    for b in fr["first_blocker"]:
        print(f"    {b['units']:5} units {b['lines']:6} lines  {b['construct']}")
    print("  census (units using the construct: executed / whole closure), constructs L1 lacks marked *:")
    for row in census:
        mark = " " if row["lowers_today"] else "*"
        print(f"   {mark} {row['executed_units']:5} {row['closure_units']:6}  {row['construct']}")
    print(f"wrote {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
