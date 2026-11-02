"""Frontend: CPython ast (L0) -> L1 through registered desugaring passes.

Each desugaring is a pass on the L0 tree with a PassSpec (obligations stated, status tested
by pipeline/tests). The final pass lowers to L1 and raises ``Unsupported`` for every construct
it does not cover, naming it, so the gap is visible rather than approximated.
"""
from __future__ import annotations

import ast
import dataclasses
import itertools
from typing import Any

from pipeline.l1 import grammar as L
from pipeline.passes.spec import Discharge, Fact, Level, Obligation, PassSpec, register

_counter = itertools.count()
# Hygiene (review 2026-11-01, astra-low-01 #5): generated names never collide with an identifier
# of the program being lowered, and are recorded so that the module can hide them (Module.synthetic).
_TAKEN: set[str] = set()
_SYNTHETIC: set[str] = set()


def _tmp(prefix: str) -> str:
    while True:
        name = f"_{prefix}{next(_counter)}"
        if name not in _TAKEN:
            _SYNTHETIC.add(name)
            return name


def _identifiers(tree: ast.AST) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.arg):
            out.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            out.update(node.names)
        elif isinstance(node, ast.alias):
            out.add((node.asname or node.name).split(".")[0])
        elif isinstance(node, ast.ExceptHandler) and node.name:
            out.add(node.name)
        elif isinstance(node, ast.keyword) and node.arg:
            out.add(node.arg)
    return out


# ---------------------------------------------------------------------------------------------
# Dialect checks on L0 (compile-time errors with a register id)
# ---------------------------------------------------------------------------------------------

def check_finally(tree: ast.AST) -> None:
    """D-10: return, break or continue that would leave a finally block is a compile-time error
    (CPython 3.14+ warns, PEP 765). break/continue of a loop inside the finally block are fine."""
    def scan(stmts: list[ast.stmt], in_loop: bool) -> None:
        for st in stmts:
            if isinstance(st, ast.Return) or (isinstance(st, (ast.Break, ast.Continue)) and not in_loop):
                kind = type(st).__name__.lower()
                raise L.DialectError(f"D-10: '{kind}' leaving a finally block is a compile-time error (line {st.lineno})")
            if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            loops = isinstance(st, (ast.For, ast.AsyncFor, ast.While))
            for fld in ("body", "orelse", "finalbody"):
                inner = getattr(st, fld, None)
                if isinstance(inner, list):
                    scan(inner, in_loop or (loops and fld == "body"))
            for h in getattr(st, "handlers", []):
                scan(h.body, in_loop)
            for case in getattr(st, "cases", []):
                scan(case.body, in_loop)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Try, ast.TryStar)):
            scan(node.finalbody, False)


# Builtins the desugarings call are intrinsics: a name no source can spell (a colon), lowered to
# L.Intrinsic, so a program binding `type`, `iter` or `format` cannot change what a `with`
# statement, a comprehension or an f-string does.
_INTRINSIC = "bella:"


def _intrinsic(name: str) -> ast.Name:
    return ast.Name(id=_INTRINSIC + name, ctx=ast.Load())


def _copy_loc[N: ast.AST](new: N, old: ast.AST) -> N:
    return ast.copy_location(new, old)


def _as_module(tree: object) -> ast.Module:
    assert isinstance(tree, ast.Module)
    return tree


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
    return _as_module(ast.fix_missing_locations(_ChainedCompare().visit(tree)))


class _With(ast.NodeTransformer):
    """PEP 343 expansion with the _exc flag (CPython's documented semantics)."""

    def visit_With(self, node: ast.With) -> Any:
        self.generic_visit(node)
        body: list[ast.stmt] = list(node.body)
        for item in reversed(node.items):
            body = self._expand(item, body, node)
        return body

    def _expand(self, item: ast.withitem, body: list[ast.stmt], loc: ast.AST) -> list[ast.stmt]:
        # __special__ is CPython's special-method lookup (_PyObject_LookupSpecial): the type's MRO,
        # bound through the descriptor protocol, TypeError when missing. CPython 3.15 looks up
        # __exit__ before __enter__ (review 2026-11-01, gemini 2.2.5.2; measured on 3.15.2).
        mgr, exit_, enter, value, exc, err = (_tmp("mgr"), _tmp("exit"), _tmp("enter"), _tmp("val"), _tmp("exc"), _tmp("err"))
        src = f"""
{mgr} = None
{exit_} = __special__({mgr}, "__exit__")
{enter} = __special__({mgr}, "__enter__")
{value} = {enter}()
{exc} = True
try:
    try:
        pass
    except BaseException as {err}:
        {exc} = False
        if not {exit_}(type({err}), {err}, {err}.__traceback__):
            raise
finally:
    if {exc}:
        {exit_}(None, None, None)
"""
        stmts = ast.parse(src).body
        for n in ast.walk(ast.Module(stmts, [])):
            if isinstance(n, ast.Name) and n.id == "type":
                n.id = _INTRINSIC + "type"
        assign = stmts[0]
        assert isinstance(assign, ast.Assign)
        assign.value = item.context_expr
        try_outer = stmts[5]
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
        Obligation("semantics", "PEP 343: __exit__ then __enter__ looked up on the type and bound through the descriptor protocol (TypeError if missing), __exit__ receives the exception triple, a true return suppresses, __exit__ runs exactly once on every exit path"),
        Obligation("terminates", "one expansion per with-item"),
    ),
    discharge=Discharge.TESTED, status="tested",
))
def desugar_with(tree: ast.Module) -> ast.Module:
    return _as_module(ast.fix_missing_locations(_With().visit(tree)))


class _ListComp(ast.NodeTransformer):
    """[E for x in IT if C] -> a helper taking iter(IT): the loop variable does not leak.

    The helper is defined in the scope that contains the comprehension, immediately before the
    statement, so it closes over that scope's names as a comprehension does; the outermost
    iterable is evaluated in that scope, everything else inside the helper (review 2026-11-01,
    astra-low-01 #5, gemini 2.2.2). The transformer does not enter nested function bodies:
    ``_hoist`` lowers each body in its own scope.
    """

    def __init__(self) -> None:
        self.hoisted: list[ast.stmt] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        # decorators and defaults run in the enclosing scope; the body is lowered by _hoist
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        node.args.defaults = [self.visit(d) for d in node.args.defaults]
        node.args.kw_defaults = [self.visit(d) if d is not None else None for d in node.args.kw_defaults]
        return node

    def visit_Lambda(self, node: ast.Lambda) -> ast.AST:
        return node          # its body is another scope; L1 does not lower lambdas yet

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        return node          # class scopes are not lowered by L1 yet

    def visit_ListComp(self, node: ast.ListComp) -> ast.AST:
        if isinstance(node.elt, ast.Starred):
            raise L.Unsupported("unpacking in a comprehension (PEP 798, new in 3.15) is [P2+]")
        fname, res, arg = _tmp("lc"), _tmp("res"), _tmp("it")
        outer_iter = self.visit(node.generators[0].iter)      # evaluated in this scope
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
        body: list[ast.stmt] = ([ast.Assign(targets=[ast.Name(id=res, ctx=ast.Store())], value=ast.List(elts=[], ctx=ast.Load()))]
                                + inner + [ast.Return(ast.Name(id=res, ctx=ast.Load()))])
        for st in body:
            ast.copy_location(st, node)
            ast.fix_missing_locations(st)
        fn = ast.FunctionDef(
            name=fname,
            args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=arg)], kwonlyargs=[], kw_defaults=[], defaults=[]),
            body=_hoist(body),           # comprehensions inside the element, conditions or inner loops
            decorator_list=[], returns=None, type_params=[])
        self.hoisted.append(ast.fix_missing_locations(_copy_loc(fn, node)))
        return ast.fix_missing_locations(_copy_loc(ast.Call(
            func=ast.Name(id=fname, ctx=ast.Load()),
            args=[ast.Call(func=_intrinsic("iter"), args=[outer_iter], keywords=[])],
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
        Obligation("semantics", "the outermost iterable is evaluated in the enclosing scope before the loop; the helper is defined in the comprehension's own scope so it sees that scope's names; loop variables do not leak (PEP 709 observable behaviour); elements appended in order"),
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
                    value = ast.Call(func=_intrinsic("str"), args=[value], keywords=[])
                elif v.conversion == 114:
                    value = ast.Call(func=_intrinsic("repr"), args=[value], keywords=[])
                elif v.conversion == 97:
                    value = ast.Call(func=_intrinsic("ascii"), args=[value], keywords=[])
                spec: ast.expr = v.format_spec if v.format_spec is not None else ast.Constant("")
                parts.append(ast.Call(func=_intrinsic("format"), args=[value, spec], keywords=[]))
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
    return _as_module(ast.fix_missing_locations(_FString().visit(tree)))


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
        # the def applies them bottom-up to the new function and binds the name once, as CPython
        # does (a __prepare__ namespace sees one store)
        node.bella_decorators = temps  # type: ignore[attr-defined]
        out = [*pre, node]
        for s in out:
            ast.copy_location(s, node)
            ast.fix_missing_locations(s)
        return out


@register(PassSpec(
    name="desugar-decorators", source=Level.L0, target=Level.L0,
    produces=frozenset({Fact.NO_DECORATORS}),
    obligations=(
        Obligation("wf", "no FunctionDef has decorators"),
        Obligation("semantics", "decorator expressions are evaluated top-down before the defaults, and applied bottom-up to the new function before its name is bound, once"),
        Obligation("terminates", "one rewrite per decorated def"),
    ),
    discharge=Discharge.TESTED, status="tested",
))
def desugar_decorators(tree: ast.Module) -> ast.Module:
    return _as_module(ast.fix_missing_locations(_Decorators().visit(tree)))


# ---------------------------------------------------------------------------------------------
# L0 -> L1
# ---------------------------------------------------------------------------------------------

_BINOPS = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.FloorDiv: "//", ast.Mod: "%",
           ast.Pow: "**", ast.LShift: "<<", ast.RShift: ">>", ast.BitAnd: "&", ast.BitOr: "|",
           ast.BitXor: "^", ast.MatMult: "@"}
_UNOPS = {ast.USub: "-", ast.UAdd: "+", ast.Invert: "~"}
_CMPOPS = {ast.Lt: "<", ast.LtE: "<=", ast.Eq: "==", ast.NotEq: "!=", ast.Gt: ">", ast.GtE: ">=",
           ast.In: "in", ast.NotIn: "not-in", ast.Is: "is", ast.IsNot: "is-not"}


def clean_doc(doc: str) -> str:
    """A docstring as CPython 3.13+ stores it (``_PyCompile_CleanDoc``, Python/compile.c): tabs
    expanded, the first line's leading spaces removed, and from every later line the smallest
    indentation of the later non-blank lines. Nothing else is stripped."""
    doc = doc.expandtabs()
    lines = doc.split("\n")
    margins = [len(x) - len(x.lstrip(" ")) for x in lines[1:] if x.strip(" ")]
    margin = min(margins) if margins else 0
    out = [lines[0].lstrip(" ")]
    for line in lines[1:]:
        cut = 0
        while cut < margin and cut < len(line) and line[cut] == " ":
            cut += 1
        out.append(line[cut:])
    return "\n".join(out)


def _docstring(body: list[ast.stmt]) -> str | None:
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        return clean_doc(body[0].value.value)
    return None


@dataclasses.dataclass
class _Unit:
    """A scope being lowered: its kind (module, function, class), CPython's qualname for it, and
    the names it declares global (a definition named global gets a bare qualname)."""
    kind: str
    qualname: str
    globals: frozenset[str] = frozenset()


class _ToL1:
    def __init__(self) -> None:
        self.units: list[_Unit] = []
        self.future_annotations = False      # PEP 563: annotations are their source text

    def module(self, tree: ast.Module, source: str) -> L.Module:
        self.future_annotations = any(
            isinstance(s, ast.ImportFrom) and s.module == "__future__" and any(a.name == "annotations" for a in s.names)
            for s in tree.body)
        self.units = [_Unit("module", "")]
        return L.Module(line=1, body=tuple(self.stmt(s) for s in tree.body), source=source)

    def qualname(self, name: str) -> str:
        """compiler_set_qualname: <parent>.<locals>.name in a function, <parent>.name in a class,
        and the bare name at module level or when the parent declares the name global."""
        parent = self.units[-1]
        if parent.kind == "module" or name in parent.globals:
            return name
        return f"{parent.qualname}.<locals>.{name}" if parent.kind == "function" else f"{parent.qualname}.{name}"

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
        if isinstance(s, (ast.Import, ast.ImportFrom)) and getattr(s, "is_lazy", False):
            raise L.Unsupported(f"lazy import (PEP 810, new in 3.15) (line {ln})")
        raise L.Unsupported(f"statement {type(s).__name__} (line {ln})")

    def params(self, a: ast.arguments, owner: str) -> tuple[L.Param, ...]:
        positional = [*a.posonlyargs, *a.args]
        defaults: list[ast.expr | None] = [None] * (len(positional) - len(a.defaults)) + list(a.defaults)
        out = [L.Param(arg.arg, self.expr(d) if d is not None else None,
                       "positional-only" if i < len(a.posonlyargs) else "positional-or-keyword")
               for i, (arg, d) in enumerate(zip(positional, defaults, strict=True))]
        if a.vararg:
            out.append(L.Param(a.vararg.arg, None, "*args"))
        out += [L.Param(arg.arg, self.expr(d) if d is not None else None, "keyword-only")
                for arg, d in zip(a.kwonlyargs, a.kw_defaults, strict=True)]
        if a.kwarg:
            out.append(L.Param(a.kwarg.arg, None, "**kwargs"))
        return tuple(out)

    def annotate(self, f: ast.FunctionDef, qualname: str) -> L.FunctionDef | None:
        """PEP 649: ``__annotate__(format, /)`` raising NotImplementedError above
        VALUE_WITH_FAKE_GLOBALS (2), else the dict in CPython's order (positional-only,
        positional, ``*args``, keyword-only, ``**kwargs``, return). Under PEP 563 the values are
        the annotations' source text. Its parameter is a hidden name, so an annotation that
        names ``format`` means the builtin, as in CPython."""
        a = f.args
        params = [*a.posonlyargs, *a.args, *([a.vararg] if a.vararg else []), *a.kwonlyargs, *([a.kwarg] if a.kwarg else [])]
        items = [(p.arg, p.annotation) for p in params if p.annotation is not None]
        if f.returns is not None:
            items.append(("return", f.returns))
        if not items:
            return None
        ln = f.lineno
        fmt = _tmp("format")
        self.units.append(_Unit("function", f"{qualname}.__annotate__"))
        try:
            values = tuple(L.Const(e.lineno, ast.unparse(e)) if self.future_annotations else self.expr(e) for _, e in items)
        finally:
            self.units.pop()
        body: tuple[L.Stmt, ...] = (
            L.If(ln, L.Truth(ln, L.Compare(ln, ">", L.Name(ln, fmt), L.Const(ln, 2))),
                 (L.Raise(ln, L.Intrinsic(ln, "NotImplementedError")),), ()),
            L.Return(ln, L.DictLit(ln, tuple(L.Const(ln, k) for k, _ in items), values)),
        )
        return L.FunctionDef(ln, "__annotate__", (L.Param(fmt, None, "positional-only", public="format"),), body,
                             qualname=f"{qualname}.__annotate__")

    def function(self, f: ast.FunctionDef) -> L.FunctionDef:
        if f.decorator_list:
            raise L.Unsupported("decorators must be desugared first")
        if f.type_params:
            raise L.Unsupported(f"type parameters (PEP 695) of {f.name} (line {f.lineno})")
        params = self.params(f.args, f.name)
        qualname = self.qualname(f.name)
        globals_: set[str] = set()
        nonlocals: set[str] = set()

        def declarations(stmts: list[ast.stmt]) -> None:
            # a global/nonlocal statement applies to the whole function wherever it stands, but
            # not to nested functions or classes (review 2026-11-01, gemini 2.2.5.1)
            for s in stmts:
                if isinstance(s, ast.Global):
                    globals_.update(s.names)
                elif isinstance(s, ast.Nonlocal):
                    nonlocals.update(s.names)
                elif isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                for fld in ("body", "orelse", "finalbody"):
                    inner = getattr(s, fld, None)
                    if isinstance(inner, list):
                        declarations(inner)
                for h in getattr(s, "handlers", []):
                    declarations(h.body)
                for case in getattr(s, "cases", []):
                    declarations(case.body)

        declarations(f.body)
        annotate = self.annotate(f, qualname)
        self.units.append(_Unit("function", qualname, frozenset(globals_)))
        try:
            body = self.block(f.body)
        finally:
            self.units.pop()
        decorators = tuple(L.Name(f.lineno, t) for t in getattr(f, "bella_decorators", []))
        return L.FunctionDef(f.lineno, f.name, params, body, frozenset(globals_), frozenset(nonlocals),
                             qualname=qualname, decorators=decorators, annotate=annotate, docstring=_docstring(f.body))

    def lambda_(self, e: ast.Lambda) -> L.Lambda:
        params = self.params(e.args, "<lambda>")
        qualname = self.qualname("<lambda>")
        self.units.append(_Unit("function", qualname))
        try:
            body = self.expr(e.body)
        finally:
            self.units.pop()
        return L.Lambda(e.lineno, params, body, qualname)

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
            if e.id.startswith(_INTRINSIC):
                return L.Intrinsic(ln, e.id.removeprefix(_INTRINSIC))
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
            args = tuple(L.Starred(a.lineno, self.expr(a.value)) if isinstance(a, ast.Starred) else self.expr(a)
                         for a in e.args)
            return L.Call(ln, self.expr(e.func), args, tuple((k.arg, self.expr(k.value)) for k in e.keywords))
        if isinstance(e, ast.Lambda):
            return self.lambda_(e)
        if isinstance(e, ast.Attribute):
            return L.GetAttr(ln, self.expr(e.value), e.attr)
        if isinstance(e, ast.Subscript):
            return L.GetItem(ln, self.expr(e.value), self.expr(e.slice))
        if isinstance(e, ast.Slice):
            parts = [self.expr(p) if p is not None else L.Const(ln, None) for p in (e.lower, e.upper, e.step)]
            return L.Call(ln, L.Intrinsic(ln, "slice"), tuple(parts))      # BUILD_SLICE, whatever `slice` names
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


def check_host_grammar() -> None:
    """L0 is the host interpreter's own ast, so the host's minor version *is* the accepted grammar.
    The three settings stay distinct -- host interpreter (pyproject), semantic reference
    (bella.toml [reference].python), accepted grammar ([reference].grammar) -- and this is the one
    place their coupling is enforced (review 2026-11-01, astra-low-02, gate step 1)."""
    import sys
    import tomllib
    from pathlib import Path
    pinned = tomllib.loads((Path(__file__).resolve().parents[2] / "bella.toml").read_text(encoding="utf-8"))
    grammar = str(pinned["reference"]["grammar"])
    host = f"{sys.version_info.major}.{sys.version_info.minor}"
    if host != grammar:
        raise RuntimeError(f"the frontend parses with the host ast: host Python {host} != bella.toml grammar {grammar}")


def lower(source: str, filename: str = "<module>") -> L.Module:
    """Parse and lower a program to L1 through the registered passes in fact order."""
    from pipeline.passes import manager
    check_host_grammar()
    tree = ast.parse(source, filename=filename)
    check_finally(tree)
    tree.bella_source = filename  # type: ignore[attr-defined]
    _TAKEN.clear()
    _TAKEN.update(_identifiers(tree))
    _SYNTHETIC.clear()
    module = manager.run(tree, manager.pipeline(FRONTEND_PASSES))
    assert isinstance(module, L.Module)
    return dataclasses.replace(module, synthetic=frozenset(_SYNTHETIC))
