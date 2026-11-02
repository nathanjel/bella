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
    is_class: bool = False     # a class body: its names are invisible to the scopes nested in it
    # holds `from m import *`, or (for the module) the module writes its globals through
    # globals(): what binds which name is known only at runtime
    star: bool = False


def _targets(t: L.Target, out: set[str]) -> None:
    if isinstance(t, L.NameTarget):
        out.add(t.id)
    elif isinstance(t, L.StarTarget):
        _targets(t.target, out)
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
        elif isinstance(t, L.StarTarget):
            target(t.target)
        elif isinstance(t, L.TupleTarget):
            for e in t.elts:
                target(e)

    if isinstance(s, L.FunctionDef):
        # decorators and defaults run in the enclosing scope; the annotate function is lazy
        return [*s.decorators, *(p.default for p in s.params if p.default is not None)]
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
            out.add(s.store or s.name)
            out.update(s.enclosing_binds)        # a comprehension's walrus targets (PEP 572)
        elif isinstance(s, L.Declare):
            out.update(s.names)                  # `x: T` makes x local
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


def _writes_globals(m: L.Module) -> bool:
    """The module calls globals() (re binds RegexFlag's members with globals().update, inspect
    its CO_ flags with globals()[...] =): its globals are written by computed name, so a name
    this checker cannot resolve may still be bound when the code runs."""
    def walk(x: object) -> bool:
        if isinstance(x, L.Call) and isinstance(x.func, L.Name) and x.func.id == "globals":
            return True
        if isinstance(x, L.Node) or isinstance(x, L.Handler) or isinstance(x, L.Param):
            return any(walk(v) for v in vars(x).values())
        if isinstance(x, tuple):
            return any(walk(v) for v in x)
        return False
    return walk(m.body)


def _imports_star(stmts: tuple[L.Stmt, ...]) -> bool:
    """A scope's own statements hold `from m import *` (the import_star intrinsic)."""
    for s in stmts:
        if isinstance(s, L.ExprStmt) and isinstance(s.value, L.Call) and isinstance(s.value.func, L.Intrinsic) \
                and s.value.func.name == "import_star":
            return True
        for v in vars(s).values():
            if isinstance(v, tuple):
                inner = tuple(x for x in v if isinstance(x, L.Stmt))
                if inner and not isinstance(s, L.FunctionDef) and _imports_star(inner):
                    return True
                if any(isinstance(x, L.Handler) and _imports_star(x.body) for x in v):
                    return True
    return False


def _declared_global(stmts: tuple[L.Stmt, ...], out: set[str]) -> None:
    """Names a nested function or class body declares global: the module binds them too."""
    def expr(e: L.Expr) -> None:
        if isinstance(e, L.ClassBody):
            out.update(e.globals)
            _declared_global(e.body, out)
            return
        if isinstance(e, L.Lambda):
            expr(e.body)
        for child in _children(e):
            expr(child)

    for s in stmts:
        if isinstance(s, L.FunctionDef):
            out.update(s.globals)
            _declared_global(s.body, out)
        for e in _stmt_exprs(s):
            expr(e)
        for v in vars(s).values():
            if isinstance(v, tuple):
                for x in v:
                    if isinstance(x, L.Stmt):
                        _declared_global((x,), out)
                    elif isinstance(x, L.Handler):
                        _declared_global(x.body, out)


def _walrus(e: L.Expr, out: set[str]) -> None:
    """Names bound by the chained-comparison desugaring (__bind__ calls)."""
    if isinstance(e, L.Call) and isinstance(e.func, L.Name) and e.func.id == "__bind__":
        c = e.args[0]
        if isinstance(c, L.Const) and isinstance(c.value, str):
            out.add(c.value)
    for child in _children(e):
        _walrus(child, out)


def _children(e: L.Expr) -> list[L.Expr]:
    """The sub-expressions evaluated in e's own scope: a lambda contributes its defaults, its
    body is a scope of its own."""
    if isinstance(e, L.Lambda):
        return [p.default for p in e.params if p.default is not None]
    if isinstance(e, L.ClassBody):
        return []              # its body is a scope of its own; bases and keywords are the call's
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
        scope = _Scope(bound=set(), star=_imports_star(m.body) or _writes_globals(m))
        _bound_in(m.body, scope.bound)
        _declared_global(m.body, scope.bound)
        scope.bound |= set(dir(builtins)) | {"__bind__", "__name__"} | set(self.extra_names)
        self.block(m.body, scope)

    def block(self, stmts: tuple[L.Stmt, ...], scope: _Scope) -> None:
        for s in stmts:
            self.stmt(s, scope)

    def stmt(self, s: L.Stmt, scope: _Scope) -> None:
        if isinstance(s, L.FunctionDef):
            inner = _Scope(bound={p.name for p in s.params} | set(s.globals) | set(s.nonlocals), parent=scope)
            _bound_in(s.body, inner.bound)
            for d in s.decorators:
                self.expr(d, scope)
            for p in s.params:
                if p.default is not None:
                    self.expr(p.default, scope)
            if s.annotation:
                return            # an annotate function's names are resolved when it is called (PEP 649)
            self.block(s.body, inner)
            return                # s.annotate is evaluated lazily, its names when it is called
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
        elif isinstance(t, L.StarTarget):
            self.target(t.target, scope)
        elif isinstance(t, L.TupleTarget):
            for e in t.elts:
                self.target(e, scope)

    def expr(self, e: L.Expr, scope: _Scope) -> None:
        if isinstance(e, L.Lambda):
            inner = _Scope(bound={p.name for p in e.params}, parent=scope)
            _walrus(e.body, inner.bound)
            _bound_in(e.prelude, inner.bound)
            self.block(e.prelude, inner)
            for p in e.params:
                if p.default is not None:
                    self.expr(p.default, scope)
            self.expr(e.body, inner)
            return
        if isinstance(e, L.ClassBody):
            inner = _Scope(bound=set(e.globals) | set(e.nonlocals), parent=scope, is_class=True, star=_imports_star(e.body))
            _bound_in(e.body, inner.bound)
            self.block(e.body, inner)
            return
        if isinstance(e, L.Name):
            # the scope itself, then the enclosing ones, skipping class bodies (Python's rule);
            # __class__ is the cell of the nearest class a function is in
            if e.id in scope.bound:
                return
            s: _Scope | None = scope.parent
            while s is not None:
                if s.is_class:
                    if e.id == "__class__" and not scope.is_class:
                        return
                elif e.id in s.bound:
                    return
                s = s.parent
            # a name a star import may bind (the module scope, or the class body using it) is
            # accepted: what `import *` binds is the imported module's business, known at runtime
            module = scope
            while module.parent is not None:
                module = module.parent
            if module.star or (scope.is_class and scope.star):
                return
            self.errors.append(f"line {e.line}: name {e.id!r} is bound nowhere in its scope chain (NameError at compile time)")
            return
        if isinstance(e, L.Compare) and isinstance(e.left, L.Compare):
            pass  # a nested Compare on the left is a value comparison, not a chain: allowed
        for child in _children(e):
            self.expr(child, scope)


def check(m: L.Module, extra_names: frozenset[str] = frozenset(), strict: bool = True) -> list[str]:
    """Raise WellFormednessError on any violated L1 invariant. `extra_names` are names the host
    binds before the module runs (the conformance harness injects none; tests may).

    `strict=False` is for library modules of the closure (proposal P-3, for the author): a name
    bound nowhere that the checker can see is not a compile-time NameError there but a runtime
    global lookup, as in CPython, since library code binds module globals by computed name from
    other modules (enum.global_enum writes re's flags). The unresolved names are returned."""
    c = _Checker(extra_names)
    c.module(m)
    unresolved = [e for e in c.errors if "is bound nowhere in its scope chain" in e]
    errors = c.errors if strict else [e for e in c.errors if e not in unresolved]
    if errors:
        raise WellFormednessError("\n".join(errors))
    return [] if strict else unresolved
