"""Static facts the staging prototype reads from source (docs/staging.md).

* exec_sites: every call of `exec`, `eval` or `compile` by its bare name, as the call site the
  runtime sees it: `module:qualname:line`, with CPython's qualified names (`f.<locals>.g`,
  `C.m`, `<module>`). The dry run's ledger counts the texts staged at each.
* namedtuple_calls: calls of `namedtuple`/`collections.namedtuple` whose field names (and
  `rename`) are literals, and `typing.NamedTuple` classes and calls with literal fields. The
  text `collections.namedtuple` evaluates depends on nothing else, so the dry run can stage a
  call it does not reach (one inside a function) by making the same call at build time
  ("probes"), and the intrinsics mechanism can generate its code without running anything.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class NamedTupleCall:
    where: str                      # path:line
    typename: str
    fields: str | tuple[str, ...]   # as written: one string, or a sequence of names
    rename: bool


class _Scopes(ast.NodeVisitor):
    def __init__(self, module: str, path: str) -> None:
        self.module, self.path = module, path
        self.stack: list[tuple[str, bool]] = []      # (name, is_function)
        self.sites: list[tuple[str, str]] = []
        self.calls: list[NamedTupleCall] = []
        # the names namedtuple and NamedTuple are bound to in this module (a compiler resolves
        # bindings; `from collections import namedtuple as _namedtuple` is _pydecimal's)
        self.namedtuple_names = {"namedtuple", "collections.namedtuple"}
        self.namedtuple_class_names = {"NamedTuple", "typing.NamedTuple"}

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.asname and alias.name in ("collections", "typing"):
                self.namedtuple_names.add(f"{alias.asname}.namedtuple")
                self.namedtuple_class_names.add(f"{alias.asname}.NamedTuple")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if node.module == "collections" and alias.name == "namedtuple":
                self.namedtuple_names.add(alias.asname or alias.name)
            elif node.module == "typing" and alias.name == "NamedTuple":
                self.namedtuple_class_names.add(alias.asname or alias.name)

    def qualname(self) -> str:
        parts: list[str] = []
        for i, (name, _) in enumerate(self.stack):
            if i and self.stack[i - 1][1]:
                parts.append("<locals>")
            parts.append(name)
        return ".".join(parts) or "<module>"

    def _scope(self, name: str, is_function: bool, node: ast.AST, whole: bool) -> None:
        self.stack.append((name, is_function))
        if whole:
            self.visit(node)
        else:
            self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        for d in node.decorator_list:
            self.visit(d)
        for default in node.args.defaults + [d for d in node.args.kw_defaults if d]:
            self.visit(default)
        self.stack.append((node.name, True))
        for stmt in node.body:
            self.visit(stmt)
        self.stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._scope("<lambda>", True, node.body, whole=True)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._scope("<genexpr>", True, node, whole=False)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for e in (*node.decorator_list, *node.bases, *(k.value for k in node.keywords)):
            self.visit(e)
        if any(_dotted(b) in self.namedtuple_class_names for b in node.bases):
            fields = tuple(s.target.id for s in node.body
                           if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name))
            self.calls.append(NamedTupleCall(f"{self.path}:{node.lineno}", node.name, fields, False))
        self.stack.append((node.name, False))
        for stmt in node.body:
            self.visit(stmt)
        self.stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        name = _dotted(node.func)
        if name in ("exec", "eval", "compile"):
            self.sites.append((f"{self.module}:{self.qualname()}:{node.lineno}", name))
        if name in self.namedtuple_names and len(node.args) >= 2:
            self._namedtuple(node, node.args[0], node.args[1])
        elif name in self.namedtuple_class_names and len(node.args) == 2 and isinstance(node.args[1], (ast.List, ast.Tuple)):
            names = [e.elts[0] for e in node.args[1].elts if isinstance(e, ast.Tuple) and e.elts]
            if len(names) == len(node.args[1].elts):
                self._namedtuple(node, node.args[0], ast.Tuple(elts=names))
        self.generic_visit(node)

    def _namedtuple(self, node: ast.Call, typename: ast.expr, fields: ast.expr) -> None:
        rename = next((k.value for k in node.keywords if k.arg == "rename"), ast.Constant(False))
        if not (isinstance(typename, ast.Constant) and isinstance(typename.value, str)
                and isinstance(rename, ast.Constant) and isinstance(rename.value, bool)):
            return
        if isinstance(fields, ast.Constant) and isinstance(fields.value, str):
            spelled: str | tuple[str, ...] = fields.value
        elif isinstance(fields, (ast.List, ast.Tuple)) and all(
                isinstance(e, ast.Constant) and isinstance(e.value, str) for e in fields.elts):
            spelled = tuple(str(e.value) for e in fields.elts if isinstance(e, ast.Constant))
        else:
            return
        self.calls.append(NamedTupleCall(f"{self.path}:{node.lineno}", typename.value, spelled, rename.value))


def _dotted(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    return ""


def scan(source: str, module: str, path: str) -> tuple[list[tuple[str, str]], list[NamedTupleCall]]:
    """(exec sites as (site, kind), literal namedtuple calls) of one module's source."""
    visitor = _Scopes(module, path)
    visitor.visit(ast.parse(source, path))
    return visitor.sites, visitor.calls
