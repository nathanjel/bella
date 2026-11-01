"""wf1: well-formedness of an L1 module.

Checks the level's invariants (grammar docstring) and the dialect's static binding rule
(spec, section 8): a bare name bound nowhere in its scope chain and not a builtin is a
compile-time NameError.
"""
from __future__ import annotations

import builtins
from dataclasses import dataclass, field

from pipeline.l1 import grammar as L


class WellFormednessError(Exception):
    pass


@dataclass
class _Scope:
    bound: set[str]
    parent: _Scope | None = None
    unresolved: list[tuple[str, int]] = field(default_factory=list)


def _targets(t: L.Target, out: set[str]) -> None:
    if isinstance(t, L.NameTarget):
        out.add(t.id)
    elif isinstance(t, L.TupleTarget):
        for e in t.elts:
            _targets(e, out)


def _stmt_exprs(s: L.Stmt) -> list[L.Expr]:
    """The expressions a statement evaluates in its own scope (not nested statement bodies)."""
    out: list[L.Expr] = []

    def target(t: L.Target) -> None:
        if isinstance(t, L.AttrTarget):
            out.append(t.obj)
        elif isinstance(t, L.ItemTarget):
            out.extend((t.obj, t.key))
        elif isinstance(t, L.TupleTarget):
            for e in t.elts:
                target(e)

    if isinstance(s, L.FunctionDef):
        return [p.default for p in s.params if p.default is not None]   # defaults: enclosing scope
    for v in vars(s).values():
        if isinstance(v, L.Expr):
            out.append(v)
        elif isinstance(v, L.Target):
            target(v)
        elif isinstance(v, tuple):
            for x in v:
                if isinstance(x, L.Handler) and x.type is not None:
                    out.append(x.type)
                elif isinstance(x, L.Target):
                    target(x)
    return out


def _bound_in(stmts: tuple[L.Stmt, ...], out: set[str]) -> None:
    for s in stmts:
        # names bound by __bind__ (the chained-comparison desugaring) in any statement position:
        # conditions, returns, assignments, assertions (review 2026-11-01, gemini 2.2.1)
        for e in _stmt_exprs(s):
            _walrus(e, out)
        if isinstance(s, (L.Assign, L.AugAssign)):
            _targets(s.target, out)
        elif isinstance(s, L.For):
            _targets(s.target, out)
            _bound_in(s.body, out)
            _bound_in(s.orelse, out)
        elif isinstance(s, (L.If, L.While)):
            _bound_in(s.body, out)
            _bound_in(s.orelse, out)
        elif isinstance(s, L.FunctionDef):
            out.add(s.name)
        elif isinstance(s, L.Delete):
            for t in s.targets:          # `del x` makes x local to its scope, as assignment does
                _targets(t, out)
        elif isinstance(s, L.Try):
            _bound_in(s.body, out)
            for h in s.handlers:
                if h.name:
                    out.add(h.name)
                _bound_in(h.body, out)
            _bound_in(s.orelse, out)
            _bound_in(s.finalbody, out)


def _walrus(e: L.Expr, out: set[str]) -> None:
    """Names bound by the chained-comparison desugaring (__bind__ calls)."""
    if isinstance(e, L.Call) and isinstance(e.func, L.Name) and e.func.id == "__bind__":
        c = e.args[0]
        if isinstance(c, L.Const) and isinstance(c.value, str):
            out.add(c.value)
    for child in _children(e):
        _walrus(child, out)


def _children(e: L.Expr) -> list[L.Expr]:
    out: list[L.Expr] = []
    for v in vars(e).values():
        if isinstance(v, L.Expr):
            out.append(v)
        elif isinstance(v, tuple):
            for x in v:
                if isinstance(x, L.Expr):
                    out.append(x)
                elif isinstance(x, tuple) and len(x) == 2 and isinstance(x[1], L.Expr):
                    out.append(x[1])
    return out


class _Checker:
    def __init__(self, extra_names: frozenset[str] = frozenset()) -> None:
        self.errors: list[str] = []
        self.extra_names = extra_names

    def module(self, m: L.Module) -> None:
        scope = _Scope(bound=set())
        _bound_in(m.body, scope.bound)
        scope.bound |= set(dir(builtins)) | {"__bind__", "__special__", "__name__"} | set(self.extra_names)
        self.block(m.body, scope)

    def block(self, stmts: tuple[L.Stmt, ...], scope: _Scope) -> None:
        for s in stmts:
            self.stmt(s, scope)

    def stmt(self, s: L.Stmt, scope: _Scope) -> None:
        if isinstance(s, L.FunctionDef):
            inner = _Scope(bound={p.name for p in s.params} | set(s.globals) | set(s.nonlocals), parent=scope)
            _bound_in(s.body, inner.bound)
            for p in s.params:
                if p.default is not None:
                    self.expr(p.default, scope)
            self.block(s.body, inner)
            return
        for v in vars(s).values():
            if isinstance(v, L.Expr):
                self.expr(v, scope)
            elif isinstance(v, L.Target):
                self.target(v, scope)
            elif isinstance(v, tuple):
                for x in v:
                    if isinstance(x, L.Stmt):
                        self.stmt(x, scope)
                    elif isinstance(x, L.Handler):
                        if x.type is not None:
                            self.expr(x.type, scope)
                        self.block(x.body, scope)
                    elif isinstance(x, L.Target):
                        self.target(x, scope)

    def target(self, t: L.Target, scope: _Scope) -> None:
        if isinstance(t, L.AttrTarget):
            self.expr(t.obj, scope)
        elif isinstance(t, L.ItemTarget):
            self.expr(t.obj, scope)
            self.expr(t.key, scope)
        elif isinstance(t, L.TupleTarget):
            for e in t.elts:
                self.target(e, scope)

    def expr(self, e: L.Expr, scope: _Scope) -> None:
        if isinstance(e, L.Name):
            s: _Scope | None = scope
            while s is not None:
                if e.id in s.bound:
                    return
                s = s.parent
            self.errors.append(f"line {e.line}: name {e.id!r} is bound nowhere in its scope chain (NameError at compile time)")
            return
        if isinstance(e, L.Compare) and isinstance(e.left, L.Compare):
            pass  # a nested Compare on the left is a value comparison, not a chain: allowed
        for child in _children(e):
            self.expr(child, scope)


def check(m: L.Module, extra_names: frozenset[str] = frozenset()) -> None:
    """Raise WellFormednessError on any violated L1 invariant. `extra_names` are names the host
    binds before the module runs (the conformance harness injects none; tests may)."""
    c = _Checker(extra_names)
    c.module(m)
    if c.errors:
        raise WellFormednessError("\n".join(c.errors))
