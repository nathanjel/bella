"""eval1: the executable semantics of L1.

A reference interpreter for PyCore that delegates every primitive operation to CPython itself
(the semantics of ``+`` on ints, of ``iter``/``next``, of ``isinstance`` are Python's, so the
reference may use them) while implementing the parts L1 makes explicit: scoping and binding,
control flow, the iteration protocol, exception handling, truthiness, function objects.

It is the oracle each later level is tested against: eval2(P(x)) must equal eval1(x).
"""
from __future__ import annotations

import builtins
import operator
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pipeline.l1 import grammar as L

_BIN: dict[str, Callable[[Any, Any], Any]] = {
    "+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.truediv,
    "//": operator.floordiv, "%": operator.mod, "**": operator.pow, "<<": operator.lshift,
    ">>": operator.rshift, "&": operator.and_, "|": operator.or_, "^": operator.xor, "@": operator.matmul,
}
_IBIN: dict[str, Callable[[Any, Any], Any]] = {
    "+": operator.iadd, "-": operator.isub, "*": operator.imul, "/": operator.itruediv,
    "//": operator.ifloordiv, "%": operator.imod, "**": operator.ipow, "<<": operator.ilshift,
    ">>": operator.irshift, "&": operator.iand, "|": operator.ior, "^": operator.ixor, "@": operator.imatmul,
}
_UN: dict[str, Callable[[Any], Any]] = {"-": operator.neg, "+": operator.pos, "~": operator.invert}
_CMP: dict[str, Callable[[Any, Any], Any]] = {
    "<": operator.lt, "<=": operator.le, "==": operator.eq, "!=": operator.ne, ">": operator.gt,
    ">=": operator.ge, "in": lambda a, b: operator.contains(b, a),
    "not-in": lambda a, b: not operator.contains(b, a), "is": operator.is_, "is-not": operator.is_not,
}


class _Break(BaseException):
    pass


class _Continue(BaseException):
    pass


class _Return(BaseException):
    def __init__(self, value: Any) -> None:
        self.value = value


_SIGNALS = (_Break, _Continue, _Return)


@dataclass
class Scope:
    vars: dict[str, Any]
    parent: Scope | None = None            # enclosing function scope (closures), None for the module
    locals_: frozenset[str] = frozenset()  # names that are local throughout (Python's rule)
    globals_: frozenset[str] = frozenset()
    nonlocals_: frozenset[str] = frozenset()
    module: Scope | None = None

    def is_module(self) -> bool:
        return self.module is None


@dataclass
class Function:
    node: L.FunctionDef
    defaults: dict[str, Any]
    closure: Scope
    interp: Interpreter = field(repr=False)

    @property
    def __name__(self) -> str:
        return self.node.name

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.interp.call(self, args, kwargs)


def _local_names(f: L.FunctionDef) -> frozenset[str]:
    from pipeline.l1.wf import _bound_in
    out: set[str] = {p.name for p in f.params}
    _bound_in(f.body, out)
    return frozenset(out - set(f.globals) - set(f.nonlocals))


class Interpreter:
    def __init__(self, builtins_: dict[str, Any] | None = None) -> None:
        self.builtins = dict(vars(builtins)) if builtins_ is None else builtins_

    # ---- entry ---------------------------------------------------------------------------
    def run_module(self, m: L.Module, name: str = "__main__") -> Scope:
        module = Scope(vars={"__name__": name})
        self.block(m.body, module)
        return module

    # ---- names -----------------------------------------------------------------------------
    def load(self, name: str, scope: Scope, line: int) -> Any:
        if scope.is_module():
            if name in scope.vars:
                return scope.vars[name]
            if name in self.builtins:
                return self.builtins[name]            # fall-through to builtins (C-8-02)
            raise NameError(f"name '{name}' is not defined", name=name)
        if name in scope.globals_:
            return self.load(name, scope.module or scope, line)
        if name in scope.locals_:
            if name in scope.vars:
                return scope.vars[name]
            raise UnboundLocalError(f"cannot access local variable '{name}' where it is not associated with a value", name=name)
        s: Scope | None = scope.parent
        while s is not None and not s.is_module():
            if name in s.vars:
                return s.vars[name]
            s = s.parent
        return self.load(name, scope.module or scope, line)

    def store(self, name: str, value: Any, scope: Scope) -> None:
        if scope.is_module() or name in scope.locals_:
            scope.vars[name] = value
            return
        if name in scope.globals_:
            assert scope.module is not None
            scope.module.vars[name] = value
            return
        if name in scope.nonlocals_:
            s: Scope | None = scope.parent
            while s is not None and not s.is_module():
                if name in s.locals_ or name in s.vars:
                    s.vars[name] = value
                    return
                s = s.parent
            raise SyntaxError(f"no binding for nonlocal '{name}' found")
        scope.vars[name] = value

    def delete(self, name: str, scope: Scope) -> None:
        target = scope.module if (name in scope.globals_ and scope.module is not None) else scope
        if name not in target.vars:
            raise NameError(f"name '{name}' is not defined", name=name)
        del target.vars[name]

    # ---- statements ------------------------------------------------------------------------
    def block(self, stmts: tuple[L.Stmt, ...], scope: Scope) -> None:
        for s in stmts:
            self.stmt(s, scope)

    def assign(self, t: L.Target, value: Any, scope: Scope) -> None:
        if isinstance(t, L.NameTarget):
            self.store(t.id, value, scope)
        elif isinstance(t, L.AttrTarget):
            setattr(self.expr(t.obj, scope), t.name, value)
        elif isinstance(t, L.ItemTarget):
            self.expr(t.obj, scope)[self.expr(t.key, scope)] = value
        elif isinstance(t, L.TupleTarget):
            items = list(value)
            if len(items) != len(t.elts):
                raise ValueError(f"expected {len(t.elts)} values, got {len(items)}")
            for sub, v in zip(t.elts, items, strict=True):
                self.assign(sub, v, scope)
        else:
            raise TypeError(f"unknown target {t}")

    def stmt(self, s: L.Stmt, scope: Scope) -> None:
        if isinstance(s, L.ExprStmt):
            self.expr(s.value, scope)
        elif isinstance(s, L.Assign):
            self.assign(s.target, self.expr(s.value, scope), scope)
        elif isinstance(s, L.AugAssign):
            if isinstance(s.target, L.NameTarget):
                cur = self.load(s.target.id, scope, s.line)
                self.store(s.target.id, _IBIN[s.op](cur, self.expr(s.value, scope)), scope)
            elif isinstance(s.target, L.AttrTarget):
                obj = self.expr(s.target.obj, scope)
                setattr(obj, s.target.name, _IBIN[s.op](getattr(obj, s.target.name), self.expr(s.value, scope)))
            elif isinstance(s.target, L.ItemTarget):
                obj, key = self.expr(s.target.obj, scope), self.expr(s.target.key, scope)
                obj[key] = _IBIN[s.op](obj[key], self.expr(s.value, scope))
            else:
                raise TypeError("illegal augmented assignment target")
        elif isinstance(s, L.Return):
            raise _Return(self.expr(s.value, scope) if s.value is not None else None)
        elif isinstance(s, L.If):
            self.block(s.body if self.expr(s.test, scope) else s.orelse, scope)
        elif isinstance(s, L.While):
            broke = False
            while self.expr(s.test, scope):
                try:
                    self.block(s.body, scope)
                except _Break:
                    broke = True
                    break
                except _Continue:
                    continue
            if not broke:
                self.block(s.orelse, scope)
        elif isinstance(s, L.For):
            it = iter(self.expr(s.iterable, scope))
            broke = False
            while True:
                try:
                    v = next(it)
                except StopIteration:
                    break
                self.assign(s.target, v, scope)
                try:
                    self.block(s.body, scope)
                except _Break:
                    broke = True
                    break
                except _Continue:
                    continue
            if not broke:
                self.block(s.orelse, scope)
        elif isinstance(s, L.Break):
            raise _Break()
        elif isinstance(s, L.Continue):
            raise _Continue()
        elif isinstance(s, L.Pass):
            pass
        elif isinstance(s, L.FunctionDef):
            defaults = {p.name: self.expr(p.default, scope) for p in s.params if p.default is not None}
            self.store(s.name, Function(s, defaults, scope, self), scope)
        elif isinstance(s, L.Raise):
            if s.exc is None:
                raise  # re-raise the exception being handled (Python's own machinery)
            exc = self.expr(s.exc, scope)
            if isinstance(exc, type) and issubclass(exc, BaseException):
                exc = exc()
            if s.cause is not None:
                cause = self.expr(s.cause, scope)
                if isinstance(cause, type) and issubclass(cause, BaseException):
                    cause = cause()
                raise exc from cause
            raise exc
        elif isinstance(s, L.Try):
            self.try_stmt(s, scope)
        elif isinstance(s, L.Delete):
            for t in s.targets:
                if isinstance(t, L.NameTarget):
                    self.delete(t.id, scope)
                elif isinstance(t, L.AttrTarget):
                    delattr(self.expr(t.obj, scope), t.name)
                elif isinstance(t, L.ItemTarget):
                    del self.expr(t.obj, scope)[self.expr(t.key, scope)]
                else:
                    raise TypeError("illegal delete target")
        elif isinstance(s, L.Assert):
            if not self.expr(s.test, scope):
                raise AssertionError(self.expr(s.msg, scope)) if s.msg is not None else AssertionError()
        else:
            raise TypeError(f"unknown statement {type(s).__name__}")

    def try_stmt(self, s: L.Try, scope: Scope) -> None:
        try:
            try:
                self.block(s.body, scope)
            except _SIGNALS:
                raise
            except BaseException as exc:
                for h in s.handlers:
                    if h.type is None:
                        matched = True
                    else:
                        t = self.expr(h.type, scope)
                        matched = isinstance(exc, t)
                    if matched:
                        if h.name:
                            self.store(h.name, exc, scope)
                        try:
                            self.block(h.body, scope)
                        finally:
                            if h.name:
                                scope.vars.pop(h.name, None)   # except-clause names are unbound afterwards
                        break
                else:
                    raise
            else:
                self.block(s.orelse, scope)
        finally:
            self.block(s.finalbody, scope)

    # ---- calls -----------------------------------------------------------------------------
    def call(self, fn: Function, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        node = fn.node
        module = fn.closure if fn.closure.is_module() else fn.closure.module
        scope = Scope(vars={}, parent=fn.closure, locals_=_local_names(node),
                      globals_=node.globals, nonlocals_=node.nonlocals, module=module)
        names = [p.name for p in node.params]
        if len(args) > len(names):
            raise TypeError(f"{node.name}() takes {len(names)} positional arguments but {len(args)} were given")
        for name, value in zip(names, args, strict=False):
            scope.vars[name] = value
        for k, v in kwargs.items():
            if k not in names:
                raise TypeError(f"{node.name}() got an unexpected keyword argument '{k}'")
            if k in scope.vars:
                raise TypeError(f"{node.name}() got multiple values for argument '{k}'")
            scope.vars[k] = v
        for name in names:
            if name not in scope.vars:
                if name in fn.defaults:
                    scope.vars[name] = fn.defaults[name]
                else:
                    raise TypeError(f"{node.name}() missing 1 required positional argument: '{name}'")
        try:
            self.block(node.body, scope)
        except _Return as r:
            return r.value
        return None

    # ---- expressions -----------------------------------------------------------------------
    def expr(self, e: L.Expr, scope: Scope) -> Any:
        if isinstance(e, L.Const):
            return e.value
        if isinstance(e, L.Name):
            return self.load(e.id, scope, e.line)
        if isinstance(e, L.BinOp):
            return _BIN[e.op](self.expr(e.left, scope), self.expr(e.right, scope))
        if isinstance(e, L.UnaryOp):
            return _UN[e.op](self.expr(e.operand, scope))
        if isinstance(e, L.Truth):
            return bool(self.expr(e.operand, scope))
        if isinstance(e, L.Not):
            return not self.expr(e.operand, scope)
        if isinstance(e, L.Compare):
            return _CMP[e.op](self.expr(e.left, scope), self.expr(e.right, scope))
        if isinstance(e, L.BoolOp):
            left = self.expr(e.left, scope)
            if e.op == "and":
                return self.expr(e.right, scope) if left else left
            return left if left else self.expr(e.right, scope)
        if isinstance(e, L.IfExp):
            return self.expr(e.body, scope) if self.expr(e.test, scope) else self.expr(e.orelse, scope)
        if isinstance(e, L.Call):
            if isinstance(e.func, L.Name) and e.func.id == "__bind__":
                name = e.args[0]
                assert isinstance(name, L.Const) and isinstance(name.value, str)
                value = self.expr(e.args[1], scope)
                self.store(name.value, value, scope)
                return value
            fn = self.expr(e.func, scope)
            args = [self.expr(a, scope) for a in e.args]
            kwargs = {k: self.expr(v, scope) for k, v in e.kwargs}
            return fn(*args, **kwargs)
        if isinstance(e, L.GetAttr):
            return getattr(self.expr(e.obj, scope), e.name)
        if isinstance(e, L.GetItem):
            return self.expr(e.obj, scope)[self.expr(e.key, scope)]
        if isinstance(e, L.ListLit):
            return [self.expr(x, scope) for x in e.items]
        if isinstance(e, L.TupleLit):
            return tuple(self.expr(x, scope) for x in e.items)
        if isinstance(e, L.DictLit):
            return {self.expr(k, scope): self.expr(v, scope) for k, v in zip(e.keys, e.values, strict=True)}
        raise TypeError(f"unknown expression {type(e).__name__}")


def run_source(source: str, filename: str = "<module>") -> Scope:
    from pipeline.l1.frontend import lower
    from pipeline.l1.wf import check
    module = lower(source, filename)
    check(module)
    return Interpreter().run_module(module)
