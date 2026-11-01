"""Frontend: CPython ast (L0) -> L1 through registered desugaring passes.

Each desugaring is a pass on the L0 tree with a PassSpec (obligations stated, status tested
by pipeline/tests). The final pass lowers to L1 and raises ``Unsupported`` for every construct
it does not cover, naming it, so the gap is visible rather than approximated.
"""
from __future__ import annotations

import ast
import itertools
from typing import Any

from pipeline.l1 import grammar as L
from pipeline.passes.spec import Discharge, Fact, Level, Obligation, PassSpec, register

_counter = itertools.count()


def _tmp(prefix: str) -> str:
    return f"_{prefix}{next(_counter)}"


def _copy_loc(new: ast.AST, old: ast.AST) -> ast.AST:
    return ast.copy_location(new, old)


# ---------------------------------------------------------------------------------------------
# L0 -> L0 desugarings
# ---------------------------------------------------------------------------------------------

class _ChainedCompare(ast.NodeTransformer):
    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        self.generic_visit(node)
        if len(node.ops) == 1:
            return node
        # a OP1 b OP2 c  ->  (a OP1 (_t := b)) and (_t OP2 c)   -- b evaluated once, c only if needed
        parts: list[ast.expr] = []
        left: ast.expr = node.left
        for i, (op, right) in enumerate(zip(node.ops, node.comparators, strict=True)):
            last = i == len(node.ops) - 1
            if last:
                parts.append(_copy_loc(ast.Compare(left=left, ops=[op], comparators=[right]), node))
            else:
                name = _tmp("cmp")
                bound = _copy_loc(ast.NamedExpr(target=ast.Name(id=name, ctx=ast.Store()), value=right), node)
                parts.append(_copy_loc(ast.Compare(left=left, ops=[op], comparators=[bound]), node))
                left = ast.Name(id=name, ctx=ast.Load())
        return ast.fix_missing_locations(_copy_loc(ast.BoolOp(op=ast.And(), values=parts), node))


@register(PassSpec(
    name="desugar-chained-compare", source=Level.L0, target=Level.L0,
    produces=frozenset({Fact.NO_CHAINED_COMPARE}),
    obligations=(
        Obligation("wf", "output contains no Compare with more than one operator"),
        Obligation("semantics", "a OP1 b OP2 c == (a OP1 b) and (b OP2 c) with b evaluated exactly once and c only if the first comparison is true (C-2-01)"),
        Obligation("terminates", "one rewrite per Compare node"),
    ),
    discharge=Discharge.TESTED, status="tested",
))
def desugar_chained_compare(tree: ast.Module) -> ast.Module:
    return ast.fix_missing_locations(_ChainedCompare().visit(tree))


class _With(ast.NodeTransformer):
    """PEP 343 expansion with the _exc flag (CPython's documented semantics)."""

    def visit_With(self, node: ast.With) -> Any:
        self.generic_visit(node)
        body: list[ast.stmt] = list(node.body)
        for item in reversed(node.items):
            body = self._expand(item, body, node)
        return body

    def _expand(self, item: ast.withitem, body: list[ast.stmt], loc: ast.AST) -> list[ast.stmt]:
        mgr, exit_, value, exc, err = (_tmp("mgr"), _tmp("exit"), _tmp("val"), _tmp("exc"), _tmp("err"))
        src = f"""
{mgr} = None
{exit_} = type({mgr}).__exit__
{value} = type({mgr}).__enter__({mgr})
{exc} = True
try:
    try:
        pass
    except BaseException as {err}:
        {exc} = False
        if not {exit_}({mgr}, type({err}), {err}, {err}.__traceback__):
            raise
finally:
    if {exc}:
        {exit_}({mgr}, None, None, None)
"""
        stmts = ast.parse(src).body
        assign = stmts[0]
        assert isinstance(assign, ast.Assign)
        assign.value = item.context_expr
        try_outer = stmts[4]
        assert isinstance(try_outer, ast.Try)
        try_inner = try_outer.body[0]
        assert isinstance(try_inner, ast.Try)
        inner_body: list[ast.stmt] = []
        if item.optional_vars is not None:
            inner_body.append(ast.Assign(targets=[item.optional_vars], value=ast.Name(id=value, ctx=ast.Load())))
        inner_body.extend(body)
        try_inner.body = inner_body
        for s in stmts:
            ast.copy_location(s, loc)
            ast.fix_missing_locations(s)
        return stmts


@register(PassSpec(
    name="desugar-with", source=Level.L0, target=Level.L0,
    produces=frozenset({Fact.NO_WITH}),
    obligations=(
        Obligation("wf", "output contains no With node"),
        Obligation("semantics", "PEP 343: __enter__/__exit__ looked up on the type, __exit__ receives the exception triple, a true return suppresses, __exit__ runs exactly once on every exit path"),
        Obligation("terminates", "one expansion per with-item"),
    ),
    discharge=Discharge.TESTED, status="tested",
))
def desugar_with(tree: ast.Module) -> ast.Module:
    return ast.fix_missing_locations(_With().visit(tree))


class _ListComp(ast.NodeTransformer):
    """[E for x in IT if C] -> a hoisted helper taking iter(IT): the loop variable does not leak."""

    def __init__(self) -> None:
        self.hoisted: list[ast.stmt] = []

    def visit_ListComp(self, node: ast.ListComp) -> ast.AST:
        self.generic_visit(node)
        fname, res, arg = _tmp("lc"), _tmp("res"), _tmp("it")
        inner: list[ast.stmt] = [ast.Expr(ast.Call(
            func=ast.Attribute(value=ast.Name(id=res, ctx=ast.Load()), attr="append", ctx=ast.Load()),
            args=[node.elt], keywords=[]))]
        for i, gen in enumerate(reversed(node.generators)):
            if gen.is_async:
                raise L.Unsupported("async comprehension")
            for cond in reversed(gen.ifs):
                inner = [ast.If(test=cond, body=inner, orelse=[])]
            is_outer = i == len(node.generators) - 1
            iterable = ast.Name(id=arg, ctx=ast.Load()) if is_outer else gen.iter
            inner = [ast.For(target=gen.target, iter=iterable, body=inner, orelse=[])]
        fn = ast.FunctionDef(
            name=fname,
            args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=arg)], kwonlyargs=[], kw_defaults=[], defaults=[]),
            body=[ast.Assign(targets=[ast.Name(id=res, ctx=ast.Store())], value=ast.List(elts=[], ctx=ast.Load()))]
                 + inner + [ast.Return(ast.Name(id=res, ctx=ast.Load()))],
            decorator_list=[], returns=None, type_params=[])
        self.hoisted.append(ast.fix_missing_locations(_copy_loc(fn, node)))
        outer_iter = node.generators[0].iter
        return ast.fix_missing_locations(_copy_loc(ast.Call(
            func=ast.Name(id=fname, ctx=ast.Load()),
            args=[ast.Call(func=ast.Name(id="iter", ctx=ast.Load()), args=[outer_iter], keywords=[])],
            keywords=[]), node))


def _hoist(stmts: list[ast.stmt]) -> list[ast.stmt]:
    out: list[ast.stmt] = []
    for s in stmts:
        tr = _ListComp()
        s = tr.visit(s)
        for fld in ("body", "orelse", "finalbody"):
            if hasattr(s, fld) and isinstance(getattr(s, fld), list):
                setattr(s, fld, _hoist(getattr(s, fld)))
        if isinstance(s, ast.Try):
            for h in s.handlers:
                h.body = _hoist(h.body)
        out.extend(tr.hoisted)
        out.append(s)
    return out


@register(PassSpec(
    name="desugar-listcomp", source=Level.L0, target=Level.L0,
    produces=frozenset({Fact.NO_COMPREHENSIONS}),
    obligations=(
        Obligation("wf", "output contains no ListComp node"),
        Obligation("semantics", "the outermost iterable is evaluated in the enclosing scope before the loop; loop variables do not leak (PEP 709 observable behaviour); elements appended in order"),
        Obligation("terminates", "one helper per comprehension"),
    ),
    discharge=Discharge.TESTED, status="tested",
))
def desugar_listcomp(tree: ast.Module) -> ast.Module:
    tree.body = _hoist(tree.body)
    return ast.fix_missing_locations(tree)


class _FString(ast.NodeTransformer):
    def visit_JoinedStr(self, node: ast.JoinedStr) -> ast.AST:
        self.generic_visit(node)
        parts: list[ast.expr] = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                parts.append(v)
            elif isinstance(v, ast.FormattedValue):
                value: ast.expr = v.value
                if v.conversion == 115:
                    value = ast.Call(func=ast.Name(id="str", ctx=ast.Load()), args=[value], keywords=[])
                elif v.conversion == 114:
                    value = ast.Call(func=ast.Name(id="repr", ctx=ast.Load()), args=[value], keywords=[])
                elif v.conversion == 97:
                    value = ast.Call(func=ast.Name(id="ascii", ctx=ast.Load()), args=[value], keywords=[])
                spec: ast.expr = v.format_spec if v.format_spec is not None else ast.Constant("")
                parts.append(ast.Call(func=ast.Name(id="format", ctx=ast.Load()), args=[value, spec], keywords=[]))
            else:
                raise L.Unsupported(f"f-string part {type(v).__name__}")
        joined = ast.Call(
            func=ast.Attribute(value=ast.Constant(""), attr="join", ctx=ast.Load()),
            args=[ast.Tuple(elts=parts, ctx=ast.Load())], keywords=[])
        return ast.fix_missing_locations(_copy_loc(joined, node))


@register(PassSpec(
    name="desugar-fstring", source=Level.L0, target=Level.L0,
    produces=frozenset({Fact.NO_FSTRINGS}),
    obligations=(
        Obligation("wf", "output contains no JoinedStr node"),
        Obligation("semantics", "each replacement field is format(conversion(value), spec) evaluated left to right, joined in order"),
        Obligation("terminates", "one rewrite per JoinedStr"),
    ),
    discharge=Discharge.TESTED, status="tested",
))
def desugar_fstring(tree: ast.Module) -> ast.Module:
    return ast.fix_missing_locations(_FString().visit(tree))


class _Decorators(ast.NodeTransformer):
    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.generic_visit(node)
        if not node.decorator_list:
            return node
        # decorators are evaluated top-down before the def, applied bottom-up after it
        temps = [_tmp("dec") for _ in node.decorator_list]
        pre = [ast.Assign(targets=[ast.Name(id=t, ctx=ast.Store())], value=d)
               for t, d in zip(temps, node.decorator_list, strict=True)]
        node.decorator_list = []
        applied: ast.expr = ast.Name(id=node.name, ctx=ast.Load())
        for t in reversed(temps):
            applied = ast.Call(func=ast.Name(id=t, ctx=ast.Load()), args=[applied], keywords=[])
        post = ast.Assign(targets=[ast.Name(id=node.name, ctx=ast.Store())], value=applied)
        out = [*pre, node, post]
        for s in out:
            ast.copy_location(s, node)
            ast.fix_missing_locations(s)
        return out


@register(PassSpec(
    name="desugar-decorators", source=Level.L0, target=Level.L0,
    produces=frozenset({Fact.NO_DECORATORS}),
    obligations=(
        Obligation("wf", "no FunctionDef has decorators"),
        Obligation("semantics", "decorator expressions are evaluated top-down before the definition and applied bottom-up after it; the name is rebound once"),
        Obligation("terminates", "one rewrite per decorated def"),
    ),
    discharge=Discharge.TESTED, status="tested",
))
def desugar_decorators(tree: ast.Module) -> ast.Module:
    return ast.fix_missing_locations(_Decorators().visit(tree))


# ---------------------------------------------------------------------------------------------
# L0 -> L1
# ---------------------------------------------------------------------------------------------

_BINOPS = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.FloorDiv: "//", ast.Mod: "%",
           ast.Pow: "**", ast.LShift: "<<", ast.RShift: ">>", ast.BitAnd: "&", ast.BitOr: "|",
           ast.BitXor: "^", ast.MatMult: "@"}
_UNOPS = {ast.USub: "-", ast.UAdd: "+", ast.Invert: "~"}
_CMPOPS = {ast.Lt: "<", ast.LtE: "<=", ast.Eq: "==", ast.NotEq: "!=", ast.Gt: ">", ast.GtE: ">=",
           ast.In: "in", ast.NotIn: "not-in", ast.Is: "is", ast.IsNot: "is-not"}


class _ToL1:
    def module(self, tree: ast.Module, source: str) -> L.Module:
        return L.Module(line=1, body=tuple(self.stmt(s) for s in tree.body), source=source)

    # ---- statements -------------------------------------------------------------------------
    def block(self, stmts: list[ast.stmt]) -> tuple[L.Stmt, ...]:
        return tuple(self.stmt(s) for s in stmts)

    def stmt(self, s: ast.stmt) -> L.Stmt:
        ln = s.lineno
        if isinstance(s, ast.Expr):
            return L.ExprStmt(ln, self.expr(s.value))
        if isinstance(s, ast.Assign):
            if len(s.targets) != 1:
                # a = b = v  ->  tmp = v; a = tmp; b = tmp  is a later refinement; keep it visible
                raise L.Unsupported("assignment with several targets")
            return L.Assign(ln, self.target(s.targets[0]), self.expr(s.value))
        if isinstance(s, ast.AnnAssign):
            if s.value is None:
                return L.Pass(ln)
            return L.Assign(ln, self.target(s.target), self.expr(s.value))
        if isinstance(s, ast.AugAssign):
            return L.AugAssign(ln, self.target(s.target), _BINOPS[type(s.op)], self.expr(s.value))
        if isinstance(s, ast.Return):
            return L.Return(ln, self.expr(s.value) if s.value is not None else None)
        if isinstance(s, ast.If):
            return L.If(ln, self.truth(s.test), self.block(s.body), self.block(s.orelse))
        if isinstance(s, ast.While):
            return L.While(ln, self.truth(s.test), self.block(s.body), self.block(s.orelse))
        if isinstance(s, ast.For):
            return L.For(ln, self.target(s.target), self.expr(s.iter), self.block(s.body), self.block(s.orelse))
        if isinstance(s, ast.Break):
            return L.Break(ln)
        if isinstance(s, ast.Continue):
            return L.Continue(ln)
        if isinstance(s, ast.Pass):
            return L.Pass(ln)
        if isinstance(s, ast.FunctionDef):
            return self.function(s)
        if isinstance(s, ast.Raise):
            return L.Raise(ln, self.expr(s.exc) if s.exc else None, self.expr(s.cause) if s.cause else None)
        if isinstance(s, ast.Try):
            handlers = tuple(L.Handler(self.expr(h.type) if h.type else None, h.name, self.block(h.body))
                             for h in s.handlers)
            return L.Try(ln, self.block(s.body), handlers, self.block(s.orelse), self.block(s.finalbody))
        if isinstance(s, ast.Delete):
            return L.Delete(ln, tuple(self.target(t) for t in s.targets))
        if isinstance(s, ast.Assert):
            return L.Assert(ln, self.truth(s.test), self.expr(s.msg) if s.msg else None)
        if isinstance(s, (ast.Global, ast.Nonlocal)):
            return L.Pass(ln)   # recorded on the enclosing FunctionDef
        raise L.Unsupported(f"statement {type(s).__name__} (line {ln})")

    def function(self, f: ast.FunctionDef) -> L.FunctionDef:
        if f.decorator_list:
            raise L.Unsupported("decorators must be desugared first")
        a = f.args
        if a.posonlyargs or a.kwonlyargs or a.vararg or a.kwarg:
            raise L.Unsupported(f"parameter kinds of {f.name} (positional-only, keyword-only, *args, **kwargs)")
        defaults: list[ast.expr | None] = [None] * (len(a.args) - len(a.defaults)) + list(a.defaults)
        params = tuple(L.Param(arg.arg, self.expr(d) if d is not None else None)
                       for arg, d in zip(a.args, defaults, strict=True))
        globals_: set[str] = set()
        nonlocals: set[str] = set()
        for s in f.body:
            if isinstance(s, ast.Global):
                globals_.update(s.names)
            elif isinstance(s, ast.Nonlocal):
                nonlocals.update(s.names)
        return L.FunctionDef(f.lineno, f.name, params, self.block(f.body), frozenset(globals_), frozenset(nonlocals))

    # ---- targets ----------------------------------------------------------------------------
    def target(self, t: ast.expr) -> L.Target:
        ln = t.lineno
        if isinstance(t, ast.Name):
            return L.NameTarget(ln, t.id)
        if isinstance(t, ast.Attribute):
            return L.AttrTarget(ln, self.expr(t.value), t.attr)
        if isinstance(t, ast.Subscript):
            return L.ItemTarget(ln, self.expr(t.value), self.expr(t.slice))
        if isinstance(t, (ast.Tuple, ast.List)):
            return L.TupleTarget(ln, tuple(self.target(e) for e in t.elts))
        raise L.Unsupported(f"assignment target {type(t).__name__} (line {ln})")

    # ---- expressions ------------------------------------------------------------------------
    def truth(self, e: ast.expr) -> L.Truth:
        return L.Truth(e.lineno, self.expr(e))

    def expr(self, e: ast.expr) -> L.Expr:
        ln = e.lineno
        if isinstance(e, ast.Constant):
            if isinstance(e.value, (int, float, str, bool)) or e.value is None:
                return L.Const(ln, e.value)
            raise L.Unsupported(f"constant of type {type(e.value).__name__}")
        if isinstance(e, ast.Name):
            return L.Name(ln, e.id)
        if isinstance(e, ast.BinOp):
            return L.BinOp(ln, _BINOPS[type(e.op)], self.expr(e.left), self.expr(e.right))
        if isinstance(e, ast.UnaryOp):
            if isinstance(e.op, ast.Not):
                return L.Not(ln, self.truth(e.operand))
            return L.UnaryOp(ln, _UNOPS[type(e.op)], self.expr(e.operand))
        if isinstance(e, ast.Compare):
            if len(e.ops) != 1:
                raise L.Unsupported("chained comparison must be desugared first")
            return L.Compare(ln, _CMPOPS[type(e.ops[0])], self.expr(e.left), self.expr(e.comparators[0]))
        if isinstance(e, ast.BoolOp):
            op = "and" if isinstance(e.op, ast.And) else "or"
            node = self.expr(e.values[-1])
            for v in reversed(e.values[:-1]):
                node = L.BoolOp(ln, op, self.expr(v), node)
            return node
        if isinstance(e, ast.IfExp):
            return L.IfExp(ln, self.truth(e.test), self.expr(e.body), self.expr(e.orelse))
        if isinstance(e, ast.Call):
            if any(isinstance(a, ast.Starred) for a in e.args) or any(k.arg is None for k in e.keywords):
                raise L.Unsupported("call with *args or **kwargs unpacking")
            return L.Call(ln, self.expr(e.func), tuple(self.expr(a) for a in e.args),
                          tuple((k.arg or "", self.expr(k.value)) for k in e.keywords))
        if isinstance(e, ast.Attribute):
            return L.GetAttr(ln, self.expr(e.value), e.attr)
        if isinstance(e, ast.Subscript):
            return L.GetItem(ln, self.expr(e.value), self.expr(e.slice))
        if isinstance(e, ast.Slice):
            parts = [self.expr(p) if p is not None else L.Const(ln, None) for p in (e.lower, e.upper, e.step)]
            return L.Call(ln, L.Name(ln, "slice"), tuple(parts))
        if isinstance(e, ast.List):
            return L.ListLit(ln, tuple(self.expr(x) for x in e.elts))
        if isinstance(e, ast.Tuple):
            return L.TupleLit(ln, tuple(self.expr(x) for x in e.elts))
        if isinstance(e, ast.Dict):
            if any(k is None for k in e.keys):
                raise L.Unsupported("dict unpacking in literal")
            return L.DictLit(ln, tuple(self.expr(k) for k in e.keys if k is not None),
                             tuple(self.expr(v) for v in e.values))
        if isinstance(e, ast.NamedExpr):
            raise L.Unsupported("walrus outside a desugared comparison")
        raise L.Unsupported(f"expression {type(e).__name__} (line {ln})")


class _ToL1WithWalrus(_ToL1):
    """The chained-comparison desugaring introduces NamedExpr; lower it as a binding expression."""

    def expr(self, e: ast.expr) -> L.Expr:
        if isinstance(e, ast.NamedExpr):
            assert isinstance(e.target, ast.Name)
            return L.Call(e.lineno, L.Name(e.lineno, "__bind__"), (L.Const(e.lineno, e.target.id), self.expr(e.value)))
        return super().expr(e)


@register(PassSpec(
    name="to-l1", source=Level.L0, target=Level.L1,
    requires=frozenset({Fact.NO_CHAINED_COMPARE, Fact.NO_WITH, Fact.NO_COMPREHENSIONS, Fact.NO_FSTRINGS, Fact.NO_DECORATORS}),
    produces=frozenset({Fact.EXPLICIT_TRUTH}),
    obligations=(
        Obligation("wf", "output satisfies wf1 (pipeline.l1.wf)"),
        Obligation("semantics", "eval1(to_l1(t)) == CPython(t) on the conformance corpus and generated programs"),
        Obligation("terminates", "structural recursion over the ast"),
    ),
    discharge=Discharge.TESTED, status="tested",
))
def to_l1(tree: ast.Module) -> L.Module:
    return _ToL1WithWalrus().module(tree, getattr(tree, "bella_source", "<module>"))


FRONTEND_PASSES = ["desugar-chained-compare", "desugar-with", "desugar-listcomp", "desugar-fstring",
                   "desugar-decorators", "to-l1"]


def lower(source: str, filename: str = "<module>") -> L.Module:
    """Parse and lower a program to L1 through the registered passes in fact order."""
    from pipeline.passes import manager
    tree = ast.parse(source, filename=filename)
    tree.bella_source = filename  # type: ignore[attr-defined]
    return manager.run(tree, manager.pipeline(FRONTEND_PASSES))
