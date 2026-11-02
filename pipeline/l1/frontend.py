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

_DEFS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def declarations(stmts: list[ast.stmt]) -> tuple[set[str], set[str]]:
    """The names a scope declares global and nonlocal: a declaration applies to the whole scope
    wherever it stands, but not to nested functions or classes (review 2026-11-01, gemini
    2.2.5.1)."""
    globals_: set[str] = set()
    nonlocals: set[str] = set()

    def walk(body: list[ast.stmt]) -> None:
        for s in body:
            if isinstance(s, ast.Global):
                globals_.update(s.names)
            elif isinstance(s, ast.Nonlocal):
                nonlocals.update(s.names)
            elif isinstance(s, _DEFS):
                continue
            for fld in ("body", "orelse", "finalbody"):
                inner = getattr(s, fld, None)
                if isinstance(inner, list):
                    walk(inner)
            for h in getattr(s, "handlers", []):
                walk(h.body)
            for case in getattr(s, "cases", []):
                walk(case.body)
    walk(stmts)
    return globals_, nonlocals


def _own_nodes(node: ast.AST) -> list[ast.AST]:
    """Every node of a scope's own code: nested functions and lambdas included (they belong to
    the class for these purposes), nested class bodies not (only their header)."""
    out: list[ast.AST] = []

    def walk(n: ast.AST) -> None:
        out.append(n)
        if isinstance(n, ast.ClassDef):
            for e in [*n.decorator_list, *n.bases, *(k.value for k in n.keywords)]:
                walk(e)
            return
        for child in ast.iter_child_nodes(n):
            walk(child)
    for child in ast.iter_child_nodes(node):
        if isinstance(node, ast.ClassDef) and child in (*node.decorator_list, *node.bases, *(k.value for k in node.keywords)):
            continue
        walk(child)
    return out


def _static_attributes(cls: ast.ClassDef) -> tuple[str, ...]:
    """CPython 3.13+ __static_attributes__: the names X of every `self.X` stored inside a
    function of the class (the object literally named self; nested classes record their own),
    as an annotated or plain target, a for/with/comprehension target; not an augmented
    assignment's, not a `del`; sorted, unmangled."""
    found: set[str] = set()

    def walk(n: ast.AST, in_function: bool, skip: ast.AST | None) -> None:
        if isinstance(n, ast.ClassDef):
            return
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            in_function = True
        if isinstance(n, ast.AugAssign):
            skip = n.target
        if (in_function and n is not skip and isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store)
                and isinstance(n.value, ast.Name) and n.value.id == "self"):
            found.add(n.attr)
        for child in ast.iter_child_nodes(n):
            walk(child, in_function, skip)
    for s in cls.body:
        walk(s, False, None)
    return tuple(sorted(found))


def _uses_class_cell(cls: ast.ClassDef) -> bool:
    """symtable: a function of the class that loads `super` or `__class__` makes the class
    create the __class__ cell (nested classes make their own)."""
    def walk(n: ast.AST, in_function: bool) -> bool:
        if isinstance(n, ast.ClassDef):
            return False
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            in_function = True
        if in_function and isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in ("super", "__class__"):
            return True
        return any(walk(c, in_function) for c in ast.iter_child_nodes(n))
    return any(walk(s, False) for s in cls.body)


def _needs_classdict(cls: ast.ClassDef) -> bool:
    """symtable 3.14+: a class whose own body defines a function (anywhere in its statements,
    not inside a nested function or class) or has an annotation gets the __classdict__ cell,
    which holds the namespace while the body runs and is stored as __classdictcell__ (measured
    on 3.15.2)."""
    def walk(stmts: list[ast.stmt]) -> bool:
        for s in stmts:
            if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.AnnAssign)):
                return True
            if isinstance(s, ast.ClassDef):
                continue
            for fld in ("body", "orelse", "finalbody"):
                inner = getattr(s, fld, None)
                if isinstance(inner, list) and walk(inner):
                    return True
            if any(walk(h.body) for h in getattr(s, "handlers", [])):
                return True
            if any(walk(case.body) for case in getattr(s, "cases", [])):
                return True
        return False
    return walk(cls.body)


class _ClassBodies:
    """Records CPython's qualname on every definition and lambda (compiler_set_qualname), and
    makes each class body explicit, as CPython's compiler does: it starts by storing
    __module__ (from __name__), __qualname__ and __firstlineno__, its docstring becomes a
    store of the cleaned __doc__, and it ends by storing __static_attributes__ and, when a
    function of the class uses super or __class__, __classcell__, which it returns; before
    them, __classdictcell__ when the body defines a function or has an annotation.
    Zero-argument super() in a function becomes an explicit call of the `super` intrinsic
    with what CPython's super() reads: the function's __class__ cell and its first argument."""

    def __init__(self) -> None:
        # (kind, qualname, names declared global there, first positional parameter, in a class)
        self.stack: list[tuple[str, str, frozenset[str], str | None, bool]] = [("module", "", frozenset(), None, False)]

    def qualname(self, name: str) -> str:
        kind, qual, globals_, _, _ = self.stack[-1]
        if kind == "module" or name in globals_:
            return name
        return f"{qual}.<locals>.{name}" if kind == "function" else f"{qual}.{name}"

    def run(self, tree: ast.Module) -> ast.Module:
        tree.body = self.block(tree.body)
        return tree

    def block(self, body: list[ast.stmt]) -> list[ast.stmt]:
        return [self.node(s) for s in body]  # type: ignore[misc]

    def node(self, n: ast.AST) -> ast.AST:
        if isinstance(n, ast.ClassDef):
            return self.class_(n)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return self.function(n)
        if isinstance(n, ast.Lambda):
            n.args = self.node(n.args)  # type: ignore[assignment]
            n.bella_qualname = self.qualname("<lambda>")  # type: ignore[attr-defined]
            params = [*n.args.posonlyargs, *n.args.args]
            in_class = self.stack[-1][4] or self.stack[-1][0] == "class"
            self.stack.append(("function", n.bella_qualname, frozenset(), params[0].arg if params else None, in_class))  # type: ignore[attr-defined]
            n.body = self.node(n.body)  # type: ignore[assignment]
            self.stack.pop()
            return n
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "super" and not n.args
                and not n.keywords and self.stack[-1][0] == "function"):
            _, _, _, first, in_class = self.stack[-1]
            ln = n
            cell: ast.expr = _intrinsic("classcell") if in_class else _intrinsic("missing")
            arg: ast.expr = ast.Name(id=first, ctx=ast.Load()) if first else _intrinsic("missing")
            return ast.fix_missing_locations(_copy_loc(ast.Call(func=_intrinsic("super"), args=[
                _copy_loc(ast.Name(id="super", ctx=ast.Load()), ln), _copy_loc(cell, ln), _copy_loc(arg, ln)],
                keywords=[]), ln))
        for fld, value in ast.iter_fields(n):
            if isinstance(value, list):
                setattr(n, fld, [self.node(v) if isinstance(v, ast.AST) else v for v in value])
            elif isinstance(value, ast.AST):
                setattr(n, fld, self.node(value))
        return n

    def function(self, f: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.AST:
        f.decorator_list = [self.node(d) for d in f.decorator_list]  # type: ignore[misc]
        f.args = self.node(f.args)  # type: ignore[assignment]
        if f.returns is not None:
            f.returns = self.node(f.returns)  # type: ignore[assignment]
        f.bella_qualname = self.qualname(f.name)  # type: ignore[union-attr]
        globals_, _ = declarations(f.body)
        params = [*f.args.posonlyargs, *f.args.args]
        in_class = self.stack[-1][4] or self.stack[-1][0] == "class"
        self.stack.append(("function", f.bella_qualname, frozenset(globals_), params[0].arg if params else None, in_class))  # type: ignore[union-attr]
        f.body = self.block(f.body)
        self.stack.pop()
        return f

    def class_(self, c: ast.ClassDef) -> ast.AST:
        c.decorator_list = [self.node(d) for d in c.decorator_list]  # type: ignore[misc]
        c.bases = [self.node(b) for b in c.bases]  # type: ignore[misc]
        for k in c.keywords:
            k.value = self.node(k.value)  # type: ignore[assignment]
        qual = self.qualname(c.name)
        c.bella_qualname = qual  # type: ignore[attr-defined]
        attributes = _static_attributes(c)
        classcell = _uses_class_cell(c)
        c.bella_classcell = classcell  # type: ignore[attr-defined]
        globals_, _ = declarations(c.body)
        self.stack.append(("class", qual, frozenset(globals_), None, True))
        body = self.block(c.body)
        self.stack.pop()
        first = c.decorator_list[0].lineno if c.decorator_list else c.lineno

        def store(name: str, value: ast.expr) -> ast.stmt:
            return ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=value)
        prologue = [store("__module__", ast.Name(id="__name__", ctx=ast.Load())),
                    store("__qualname__", ast.Constant(qual)), store("__firstlineno__", ast.Constant(first))]
        doc = _docstring(c.body)
        if doc is not None:
            body = [store("__doc__", ast.Constant(doc)), *body[1:]]
        epilogue = [store("__static_attributes__", ast.Tuple(elts=[ast.Constant(a) for a in attributes], ctx=ast.Load()))]
        classdict = _needs_classdict(c)
        c.bella_classdict = classdict  # type: ignore[attr-defined]
        if classdict:
            epilogue.append(store("__classdictcell__", _intrinsic("classdictcell")))
        if classcell:
            epilogue += [store("__classcell__", _intrinsic("classcell")), ast.Return(_intrinsic("classcell"))]
        for s in [*prologue, *epilogue]:
            _copy_loc(s, c)
            ast.fix_missing_locations(s)
        c.body = [*prologue, *body, *epilogue]
        return c


@register(PassSpec(
    name="desugar-class-body", source=Level.L0, target=Level.L0,
    produces=frozenset({Fact.CLASS_BODIES_EXPLICIT}),
    obligations=(
        Obligation("wf", "every class body starts with the __module__, __qualname__ and __firstlineno__ stores and ends with __static_attributes__ (and __classcell__ when needed); no zero-argument super() call remains in a function"),
        Obligation("semantics", "the namespace a class body leaves is CPython's (names, values, order of stores); super() reads the __class__ cell and the first argument as CPython's does"),
        Obligation("terminates", "one rewrite per class and per super() call"),
    ),
    discharge=Discharge.TESTED, status="tested",
))
def desugar_class_body(tree: ast.Module) -> ast.Module:
    return ast.fix_missing_locations(_ClassBodies().run(tree))


def mangle(private: str | None, name: str) -> str:
    """_Py_Mangle: __name inside class C is _C__name, unless it ends with __ or holds a dot, or
    the class name is only underscores."""
    if private is None or not name.startswith("__") or name.endswith("__") or "." in name:
        return name
    stripped = private.lstrip("_")
    return f"_{stripped}{name}" if stripped else name


class _PrivateNames:
    """Private-name mangling over a class's own code (its functions and lambdas included; a
    nested class mangles with its own name): names, attributes, parameters, global and
    nonlocal declarations, except-clause names, imported names, and the names definitions
    are stored under. A definition keeps its unmangled __name__ and __qualname__, and keyword
    arguments in calls are not mangled (measured on 3.15.2)."""

    def __init__(self) -> None:
        self.private: str | None = None

    def visit(self, n: ast.AST) -> None:
        p = self.private
        if isinstance(n, ast.ClassDef):
            for e in [*n.decorator_list, *n.bases, *(k.value for k in n.keywords)]:
                self.visit(e)
            n.bella_store = mangle(p, n.name)  # type: ignore[attr-defined]
            self.private = n.name
            for s in n.body:
                self.visit(s)
            self.private = p
            return
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            n.bella_store = mangle(p, n.name)  # type: ignore[union-attr]
        if isinstance(n, ast.arg):
            n.arg = mangle(p, n.arg)
        elif isinstance(n, ast.Name):
            n.id = mangle(p, n.id)
        elif isinstance(n, ast.Attribute):
            n.attr = mangle(p, n.attr)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            n.names = [mangle(p, x) for x in n.names]
        elif isinstance(n, ast.ExceptHandler) and n.name:
            n.name = mangle(p, n.name)
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                if a.name != "*":
                    a.name = mangle(p, a.name)
                if a.asname:
                    a.asname = mangle(p, a.asname)
        elif isinstance(n, ast.Import):
            for a in n.names:
                a.bella_store = mangle(p, a.asname or a.name.partition(".")[0])  # type: ignore[attr-defined]
        for child in ast.iter_child_nodes(n):
            self.visit(child)


@register(PassSpec(
    name="desugar-private-names", source=Level.L0, target=Level.L0,
    requires=frozenset({Fact.CLASS_BODIES_EXPLICIT}),
    produces=frozenset({Fact.PRIVATE_NAMES_MANGLED}),
    obligations=(
        Obligation("wf", "no identifier of a class's code is a private name of that class"),
        Obligation("semantics", "every identifier CPython's compiler mangles is mangled as _Py_Mangle does; __name__, __qualname__, __static_attributes__ and call keywords are not"),
        Obligation("terminates", "one visit per node"),
    ),
    discharge=Discharge.TESTED, status="tested",
))
def desugar_private_names(tree: ast.Module) -> ast.Module:
    _PrivateNames().visit(tree)
    return tree


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
    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        return self.visit_FunctionDef(node)  # type: ignore[arg-type]  # the same rewrite: temps before, applied once

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
        Obligation("wf", "no FunctionDef or ClassDef has decorators"),
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
        if isinstance(s, ast.ClassDef):
            return self.class_(s)
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
        qualname = getattr(f, "bella_qualname", None) or self.qualname(f.name)
        globals_, nonlocals = declarations(f.body)
        annotate = self.annotate(f, qualname)
        self.units.append(_Unit("function", qualname, frozenset(globals_)))
        try:
            body = self.block(f.body)
        finally:
            self.units.pop()
        decorators = tuple(L.Name(f.lineno, t) for t in getattr(f, "bella_decorators", []))
        return L.FunctionDef(f.lineno, f.name, params, body, frozenset(globals_), frozenset(nonlocals),
                             qualname=qualname, decorators=decorators, annotate=annotate, docstring=_docstring(f.body),
                             store=getattr(f, "bella_store", "") if getattr(f, "bella_store", f.name) != f.name else "")

    def class_(self, c: ast.ClassDef) -> L.Assign:
        """``C = d1(d2(build_class(<body>, "C", *bases, **keywords)))``: the decorators (already
        evaluated into names) applied once to what build_class returns, then one store."""
        ln = c.lineno
        if c.type_params:
            raise L.Unsupported(f"type parameters (PEP 695) of class {c.name} (line {ln})")
        if c.decorator_list:
            raise L.Unsupported("decorators must be desugared first")
        if not hasattr(c, "bella_qualname"):
            raise L.Unsupported("class bodies must be made explicit first (desugar-class-body)")
        qualname: str = c.bella_qualname
        bases = tuple(L.Starred(b.lineno, self.expr(b.value)) if isinstance(b, ast.Starred) else self.expr(b) for b in c.bases)
        keywords = tuple((k.arg, self.expr(k.value)) for k in c.keywords)
        globals_, nonlocals = declarations(c.body)
        self.units.append(_Unit("class", qualname, frozenset(globals_)))
        try:
            body = self.block(c.body)
        finally:
            self.units.pop()
        made: L.Expr = L.Call(ln, L.Intrinsic(ln, "build_class"),
                              (L.ClassBody(ln, qualname, body, frozenset(globals_), frozenset(nonlocals),
                                           bool(getattr(c, "bella_classcell", False)),
                                           bool(getattr(c, "bella_classdict", False))), L.Const(ln, c.name), *bases),
                              keywords)
        for t in reversed(getattr(c, "bella_decorators", [])):
            made = L.Call(ln, L.Name(ln, t), (made,))
        return L.Assign(ln, L.NameTarget(ln, getattr(c, "bella_store", c.name)), made)

    def lambda_(self, e: ast.Lambda) -> L.Lambda:
        params = self.params(e.args, "<lambda>")
        qualname = getattr(e, "bella_qualname", None) or self.qualname("<lambda>")
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
            if isinstance(e.value, (int, float, complex, str, bytes, bool)) or e.value is None or e.value is Ellipsis:
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
    requires=frozenset({Fact.NO_CHAINED_COMPARE, Fact.NO_WITH, Fact.NO_COMPREHENSIONS, Fact.NO_FSTRINGS, Fact.NO_DECORATORS,
                        Fact.CLASS_BODIES_EXPLICIT, Fact.PRIVATE_NAMES_MANGLED}),
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


FRONTEND_PASSES = ["desugar-class-body", "desugar-private-names", "desugar-chained-compare", "desugar-with",
                   "desugar-listcomp", "desugar-fstring", "desugar-decorators", "to-l1"]


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
