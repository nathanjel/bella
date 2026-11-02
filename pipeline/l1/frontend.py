"""Frontend: CPython ast (L0) -> L1 through registered desugaring passes.

Each desugaring is a pass on the L0 tree with a PassSpec (obligations stated, status tested
by pipeline/tests). The final pass lowers to L1 and raises ``Unsupported`` for every construct
it does not cover, naming it, so the gap is visible rather than approximated.
"""
from __future__ import annotations

import __future__
import ast
import dataclasses
import itertools
import sys
import tomllib
import warnings
from pathlib import Path
from typing import Any

import _ast_unparse  # type: ignore[import-not-found]  # noqa: F401  # ast.unparse imports it on first use; here, never while a program runs

from pipeline.l1 import grammar as L
from pipeline.passes import manager
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

def _annotate_function(entries: list[tuple[str, ast.expr, int | None]], condition: ast.expr | None,
                        future: bool, line: ast.AST) -> ast.FunctionDef:
    """PEP 649 as 3.15.2 compiles a module's or a class's annotations: __annotate__(format, /)
    raising NotImplementedError above VALUE_WITH_FAKE_GLOBALS, else a dict filled in order, a
    conditional annotation only if its index is in the conditional set (its statement ran);
    under PEP 563 the values are the annotations' source text."""
    fmt, d = _tmp("format"), _tmp("ann")
    body: list[ast.stmt] = [
        ast.If(test=ast.Compare(left=ast.Name(id=fmt, ctx=ast.Load()), ops=[ast.Gt()], comparators=[ast.Constant(2)]),
               body=[ast.Raise(exc=_intrinsic("NotImplementedError"), cause=None)], orelse=[]),
        ast.Assign(targets=[ast.Name(id=d, ctx=ast.Store())], value=ast.Dict(keys=[], values=[]))]
    for key, annotation, index in entries:
        value = ast.Constant(ast.unparse(annotation)) if future else annotation
        store: ast.stmt = ast.Assign(targets=[ast.Subscript(value=ast.Name(id=d, ctx=ast.Load()), slice=ast.Constant(key),
                                                            ctx=ast.Store())], value=value)
        if index is not None:
            assert condition is not None
            store = ast.If(test=ast.Compare(left=ast.Constant(index), ops=[ast.In()], comparators=[condition]),
                           body=[store], orelse=[])
        body.append(store)
    body.append(ast.Return(ast.Name(id=d, ctx=ast.Load())))
    fn = ast.FunctionDef(name="__annotate__", args=ast.arguments(posonlyargs=[ast.arg(arg=fmt)], args=[], kwonlyargs=[],
                                                                 kw_defaults=[], defaults=[]),
                         body=body, decorator_list=[], returns=None, type_params=[])
    fn.bella_public = {fmt: "format"}  # type: ignore[attr-defined]
    fn.bella_annotation = True  # type: ignore[attr-defined]
    return ast.fix_missing_locations(_copy_loc(fn, line))


class _Annotations:
    """Module and class annotations as 3.15.2 compiles them (PEP 649):

    * module: __annotate__ is made at the start of the body, then the set
      __conditional_annotations__ (both before the docstring's __doc__); every annotation
      statement, once it ran, adds its index to the set;
    * class: only annotations inside blocks are conditional, their set a hidden variable of the
      class; the function is stored as __annotate_func__ at the end of the body and reads names
      from the class's namespace first;
    * a non-simple target's annotation is never evaluated; `x: T` without a value makes x
      local (Declare), its name mangled as the symbol table mangles it; an attribute or
      subscript target without a value still has its object (and its index, each part of a
      slice) evaluated, in every scope. The module's docstring becomes an explicit __doc__ store.

    Under PEP 563 (`from __future__ import annotations`) a module or class whose own statements
    hold an annotation sets up a real __annotations__ mapping first (SETUP_ANNOTATIONS: before
    the docstring's __doc__, after the module's set of conditional annotations), and each simple
    annotation stores its source text in it as it runs; no __annotate__ is made."""

    def __init__(self, future: bool) -> None:
        self.future = future
        self.classes: list[str] = []

    @property
    def private(self) -> str | None:
        return self.classes[-1] if self.classes else None

    def run(self, tree: ast.Module) -> ast.Module:
        doc = _docstring(tree.body)
        body = tree.body[1:] if doc is not None else tree.body
        annotated = self.has_annotations(tree.body)     # before block() rewrites nested statements in place
        entries: list[tuple[str, ast.expr, int | None]] = []
        body = self.block(body, entries, module=True, depth=0, condition=ast.Name(id="__conditional_annotations__", ctx=ast.Load()))
        prologue: list[ast.stmt] = []
        if entries:
            prologue.append(_annotate_function(entries, ast.Name(id="__conditional_annotations__", ctx=ast.Load()),
                                               self.future, tree))
        if annotated:
            prologue.append(ast.Assign(targets=[ast.Name(id="__conditional_annotations__", ctx=ast.Store())],
                                       value=ast.Call(func=_intrinsic("set"), args=[], keywords=[])))
        if annotated and self.future:
            prologue.append(_setup_annotations())
        if doc is not None:
            prologue.append(ast.Assign(targets=[ast.Name(id="__doc__", ctx=ast.Store())], value=ast.Constant(doc)))
        for st in prologue:
            ast.copy_location(st, tree.body[0] if tree.body else tree)
            ast.fix_missing_locations(st)
        tree.body = [*prologue, *body]
        return tree

    @staticmethod
    def has_annotations(stmts: list[ast.stmt]) -> bool:
        def walk(body: list[ast.stmt]) -> bool:
            for s in body:
                if isinstance(s, ast.AnnAssign):
                    return True
                if isinstance(s, _DEFS):
                    continue
                for fld in ("body", "orelse", "finalbody"):
                    inner = getattr(s, fld, None)
                    if isinstance(inner, list) and inner and isinstance(inner[0], ast.stmt) and walk(inner):
                        return True
                if any(walk(h.body) for h in getattr(s, "handlers", [])) or any(walk(c.body) for c in getattr(s, "cases", [])):
                    return True
            return False
        return walk(stmts)

    def block(self, stmts: list[ast.stmt], entries: list[tuple[str, ast.expr, int | None]], module: bool, depth: int,
              condition: ast.expr | None) -> list[ast.stmt]:
        out: list[ast.stmt] = []
        for s in stmts:
            if isinstance(s, ast.AnnAssign):
                out += self.annassign(s, entries, module, depth, condition)
            elif isinstance(s, ast.ClassDef):
                out.append(self.class_(s))
            elif isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
                s.body = self.function_body(s.body)
                out.append(s)
            else:
                for fld in ("body", "orelse", "finalbody"):
                    inner = getattr(s, fld, None)
                    if isinstance(inner, list) and inner and isinstance(inner[0], ast.stmt):
                        setattr(s, fld, self.block(inner, entries, module, depth + 1, condition))
                for h in getattr(s, "handlers", []):
                    h.body = self.block(h.body, entries, module, depth + 1, condition)
                for case in getattr(s, "cases", []):
                    case.body = self.block(case.body, entries, module, depth + 1, condition)
                out.append(s)
        return out

    def function_body(self, stmts: list[ast.stmt]) -> list[ast.stmt]:
        """In a function an annotation is never evaluated: `x: T = v` assigns, `x: T` declares."""
        out: list[ast.stmt] = []
        for s in stmts:
            if isinstance(s, ast.AnnAssign):
                if s.value is not None:
                    out.append(_copy_loc(ast.Assign(targets=[s.target], value=s.value), s))
                elif s.simple and isinstance(s.target, ast.Name):
                    out.append(_declare(s, self.private))
                else:
                    out += _annotated_target_parts(s)
                continue
            if isinstance(s, ast.ClassDef):
                out.append(self.class_(s))
                continue
            if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
                s.body = self.function_body(s.body)
            else:
                for fld in ("body", "orelse", "finalbody"):
                    inner = getattr(s, fld, None)
                    if isinstance(inner, list) and inner and isinstance(inner[0], ast.stmt):
                        setattr(s, fld, self.function_body(inner))
                for h in getattr(s, "handlers", []):
                    h.body = self.function_body(h.body)
                for case in getattr(s, "cases", []):
                    case.body = self.function_body(case.body)
            out.append(s)
        return out

    def annassign(self, s: ast.AnnAssign, entries: list[tuple[str, ast.expr, int | None]], module: bool, depth: int,
                  condition: ast.expr | None) -> list[ast.stmt]:
        out: list[ast.stmt] = []
        if s.value is not None:
            out.append(_copy_loc(ast.Assign(targets=[s.target], value=s.value), s))
        elif s.simple and isinstance(s.target, ast.Name):
            out.append(_declare(s, self.private))
        else:
            out += _annotated_target_parts(s)
        if s.simple and isinstance(s.target, ast.Name) and self.future:
            # PEP 563: the text, then LOAD_NAME __annotations__, the mangled name, STORE_SUBSCR
            key = mangle(self.private, s.target.id)
            out.append(_copy_loc(ast.Assign(
                targets=[ast.Subscript(value=ast.Name(id="__annotations__", ctx=ast.Load()), slice=ast.Constant(key),
                                       ctx=ast.Store())],
                value=ast.Constant(ast.unparse(s.annotation))), s))
        elif s.simple and isinstance(s.target, ast.Name):
            key = mangle(self.private, s.target.id)
            index: int | None = None
            if module or depth > 0:
                index = len([e for e in entries if e[2] is not None])
                assert condition is not None
                out.append(_copy_loc(ast.Expr(ast.Call(func=_intrinsic("set_add"), args=[condition, ast.Constant(index)],
                                                       keywords=[])), s))
            entries.append((key, s.annotation, index))
        # a non-simple target's annotation is never evaluated
        return [ast.fix_missing_locations(o) for o in out]

    def class_(self, c: ast.ClassDef) -> ast.ClassDef:
        self.classes.append(c.name)
        condition_name = _tmp("cond")
        entries: list[tuple[str, ast.expr, int | None]] = []
        doc = _docstring(c.body)
        rest = c.body[1:] if doc is not None else c.body
        annotated = self.has_annotations(rest)          # before block() rewrites nested statements in place
        body = self.block(rest, entries, module=False, depth=0, condition=ast.Name(id=condition_name, ctx=ast.Load()))
        self.classes.pop()
        head = c.body[:1] if doc is not None else []
        if any(index is not None for _, _, index in entries):
            head.append(ast.fix_missing_locations(_copy_loc(ast.Assign(
                targets=[ast.Name(id=condition_name, ctx=ast.Store())],
                value=ast.Call(func=_intrinsic("set"), args=[], keywords=[])), c)))
        tail: list[ast.stmt] = []
        if entries:
            fn = _annotate_function(entries, ast.Name(id=condition_name, ctx=ast.Load()), self.future, c)
            fn.bella_store = "__annotate_func__"  # type: ignore[attr-defined]
            fn.bella_classdict = True  # type: ignore[attr-defined]
            tail.append(fn)
        c.body = [*head, *body, *tail] or [ast.Pass()]
        if annotated:
            c.bella_has_annotations = True  # type: ignore[attr-defined]
            if self.future:
                c.bella_setup_annotations = True  # type: ignore[attr-defined]  # desugar-class-body places it before __doc__
        return c


def _declare(s: ast.AnnAssign, private: str | None) -> ast.stmt:
    """`x: T` with no value: x is a local of a function (the symbol table binds it), mangled in a class."""
    assert isinstance(s.target, ast.Name)
    node = ast.Expr(ast.Call(func=_intrinsic("declare"), args=[ast.Constant(mangle(private, s.target.id))], keywords=[]))
    return ast.fix_missing_locations(_copy_loc(node, s))


def _annotated_target_parts(s: ast.AnnAssign) -> list[ast.stmt]:
    """codegen_check_ann_expr and codegen_check_ann_subscr (Python/codegen.c, 3.15.2): an
    annotated attribute or subscript with no value still evaluates the object and, for a
    subscript, the index (each bound of a slice, each element of an extended slice), and reads
    or stores nothing; a name target evaluates nothing."""
    parts: list[ast.expr] = []

    def index(e: ast.expr) -> None:
        if isinstance(e, ast.Slice):
            parts.extend(x for x in (e.lower, e.upper, e.step) if x is not None)
        elif isinstance(e, ast.Tuple):
            for x in e.elts:
                index(x)
        else:
            parts.append(e)
    if isinstance(s.target, ast.Attribute):
        parts.append(s.target.value)
    elif isinstance(s.target, ast.Subscript):
        parts.append(s.target.value)
        index(s.target.slice)
    return [ast.fix_missing_locations(_copy_loc(ast.Expr(p), p)) for p in parts]


def _setup_annotations() -> ast.stmt:
    """SETUP_ANNOTATIONS: the setup_annotations intrinsic makes __annotations__ in the running
    module's or class's namespace unless it holds one (PEP 563)."""
    return ast.Expr(ast.Call(func=_intrinsic("setup_annotations"), args=[], keywords=[]))


@register(PassSpec(
    name="desugar-annotations", source=Level.L0, target=Level.L0,
    produces=frozenset({Fact.ANNOTATIONS_EXPLICIT}),
    obligations=(
        Obligation("wf", "no AnnAssign remains; a module or class with simple annotations has its __annotate__ function"),
        Obligation("semantics", "PEP 649 as 3.15.2 compiles it: the module function first and every module annotation conditional on its statement having run, the class function stored last as __annotate__func__ reading the class namespace first, non-simple targets' annotations never evaluated, annotated names local, the module docstring stored as __doc__ after them"),
        Obligation("terminates", "one rewrite per annotated statement and per scope"),
    ),
    discharge=Discharge.TESTED, status="tested",
))
def desugar_annotations(tree: ast.Module) -> ast.Module:
    return _Annotations("annotations" in getattr(tree, "bella_future", ())).run(tree)


class _TypeParams:
    """PEP 695 as 3.15.2 compiles it: a generic function, class or alias runs in a hidden scope
    "<generic parameters of NAME>" that binds its type parameters, transparent to qualnames,
    able to see a class's namespace; the decorators are evaluated before it runs and applied
    to what it returns, stored once. The parameters' bounds, constraints and defaults, and an
    alias's value, are lazy thunks (annotation scopes). The objects themselves (TypeVar,
    TypeVarTuple, ParamSpec, Generic[...], TypeAliasType) are made by the type_params,
    generic_class and typealias intrinsics from a text that names the thunks; a generic
    class gets Generic[...] after its bases and __type_params__ in its namespace."""

    def __init__(self) -> None:
        self.scopes: list[str] = ["module"]

    def run(self, tree: ast.Module) -> ast.Module:
        tree.body = self.block(tree.body)
        return tree

    def block(self, stmts: list[ast.stmt]) -> list[ast.stmt]:
        out: list[ast.stmt] = []
        for s in stmts:
            out.extend(self.stmt(s))
        return out

    def stmt(self, s: ast.stmt) -> list[ast.stmt]:
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            self.scopes.append("class" if isinstance(s, ast.ClassDef) else "function")
            s.body = self.block(s.body)
            self.scopes.pop()
            if s.type_params:
                return self.generic(s)
            return [s]
        if isinstance(s, ast.TypeAlias):
            return self.alias(s)
        for fld in ("body", "orelse", "finalbody"):
            inner = getattr(s, fld, None)
            if isinstance(inner, list) and inner and isinstance(inner[0], ast.stmt):
                setattr(s, fld, self.block(inner))
        for h in getattr(s, "handlers", []):
            h.body = self.block(h.body)
        for case in getattr(s, "cases", []):
            case.body = self.block(case.body)
        return [s]

    def thunk(self, expr: ast.expr, in_class: bool) -> tuple[str, ast.FunctionDef]:
        name = _tmp("lazy")
        fn = ast.FunctionDef(name=name, args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
                             body=[ast.Return(expr)], decorator_list=[], returns=None, type_params=[])
        fn.bella_annotation = True  # type: ignore[attr-defined]
        fn.bella_classdict = in_class  # type: ignore[attr-defined]
        return name, ast.fix_missing_locations(_copy_loc(fn, expr))

    def params_text(self, params: list[ast.type_param], in_class: bool) -> tuple[str, list[ast.stmt], list[str]]:
        """The parameter list as text, each lazy expression a call of a thunk, the thunks'
        definitions, and their names in the order the text uses them."""
        parts: list[str] = []
        defs: list[ast.stmt] = []
        names: list[str] = []

        def call(e: ast.expr) -> str:
            name, fn = self.thunk(e, in_class)
            defs.append(fn)
            names.append(name)
            return f"__bella_{len(names) - 1}__()"
        for tp in params:
            if isinstance(tp, ast.TypeVar):
                text = tp.name
                if isinstance(tp.bound, ast.Tuple):
                    text += ": (" + "".join(call(c) + ", " for c in tp.bound.elts) + ")"
                elif tp.bound is not None:
                    text += ": " + call(tp.bound)
            elif isinstance(tp, ast.TypeVarTuple):
                text = "*" + tp.name
            else:
                assert isinstance(tp, ast.ParamSpec)
                text = "**" + tp.name
            if tp.default_value is not None:
                text += " = " + ("*" if isinstance(tp, ast.TypeVarTuple) else "") + call(
                    tp.default_value.value if isinstance(tp, ast.TypeVarTuple) and isinstance(tp.default_value, ast.Starred)
                    else tp.default_value)
            parts.append(text)
        return ", ".join(parts), defs, names

    def generic(self, s: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> list[ast.stmt]:
        in_class = self.scopes[-1] == "class"
        text, defs, thunks = self.params_text(s.type_params, in_class)
        names = [tp.name for tp in s.type_params]  # type: ignore[attr-defined]  # every type_param kind has one
        decorators, s.decorator_list = s.decorator_list, []
        params = _tmp("params")
        body: list[ast.stmt] = [*defs]
        thunk_loads = [ast.Name(id=t, ctx=ast.Load()) for t in thunks]
        if isinstance(s, ast.ClassDef):
            base = _tmp("generic_base")
            body.append(_assign_tuple([params, base], ast.Call(func=_intrinsic("generic_class"),
                                                                args=[ast.Constant(f"class __bella_tp__[{text}]: pass"),
                                                                      *thunk_loads], keywords=[])))
            body.append(_assign_tuple(names, ast.Name(id=params, ctx=ast.Load())))
            s.bases = [*s.bases, ast.Name(id=base, ctx=ast.Load())]
            s.bella_type_params = params  # type: ignore[attr-defined]
            s.type_params = []
            body += [s, ast.Return(ast.Name(id=s.name, ctx=ast.Load()))]
            return self.scope(s.name, body, decorators, s, in_class, mangle_only=(s.name, frozenset(names)))
        else:
            body.append(ast.Assign(targets=[ast.Name(id=params, ctx=ast.Store())],
                                   value=ast.Call(func=_intrinsic("type_params"),
                                                  args=[ast.Constant(f"def __bella_tp__[{text}](): pass"), *thunk_loads],
                                                  keywords=[])))
            body.append(_assign_tuple(names, ast.Name(id=params, ctx=ast.Load())))
            s.type_params = []
            body += [s, ast.Return(ast.Call(func=_intrinsic("set_type_params"),
                                            args=[ast.Name(id=s.name, ctx=ast.Load()), ast.Name(id=params, ctx=ast.Load())],
                                            keywords=[]))]
        return self.scope(s.name, body, decorators, s, in_class)

    def alias(self, s: ast.TypeAlias) -> list[ast.stmt]:
        in_class = self.scopes[-1] == "class"
        assert isinstance(s.name, ast.Name)
        name = s.name.id
        value_name, value_fn = self.thunk(s.value, in_class)
        # the value's function is named after the alias, as CPython's is: the alias takes its
        # __qualname__ from it (_Py_make_typealias; review 2026-11-02, G6 2.3.3)
        value_fn.name, value_fn.bella_store = name, value_name  # type: ignore[attr-defined]
        text, defs, thunks = self.params_text(s.type_params, in_class)
        made = ast.Call(func=_intrinsic("typealias"),
                        args=[ast.Constant(f"type {name}[{text}] = __bella_v__()" if s.type_params else f"type {name} = __bella_v__()"),
                              ast.Name(id=value_name, ctx=ast.Load()), *(ast.Name(id=t, ctx=ast.Load()) for t in thunks)],
                        keywords=[])
        if not s.type_params:
            out = [value_fn, ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=made)]
            return [ast.fix_missing_locations(_copy_loc(o, s)) for o in out]
        alias = _tmp("alias")
        body: list[ast.stmt] = [*defs, value_fn, ast.Assign(targets=[ast.Name(id=alias, ctx=ast.Store())], value=made),
                                _assign_tuple([tp.name for tp in s.type_params],  # type: ignore[attr-defined]
                                              ast.Attribute(value=ast.Name(id=alias, ctx=ast.Load()), attr="__type_params__",
                                                            ctx=ast.Load())),
                                ast.Return(ast.Name(id=alias, ctx=ast.Load()))]
        return self.scope(name, body, [], s, in_class)

    def scope(self, name: str, body: list[ast.stmt], decorators: list[ast.expr], node: ast.AST, in_class: bool,
              mangle_only: tuple[str, frozenset[str]] | None = None) -> list[ast.stmt]:
        helper = ast.FunctionDef(name=f"<generic parameters of {name}>",
                                 args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
                                 body=body, decorator_list=[], returns=None, type_params=[])
        if mangle_only is not None:
            helper.bella_mangle_only = mangle_only  # type: ignore[attr-defined]  # a generic class (desugar-private-names)
        store = _tmp("generic")
        helper.bella_store = store  # type: ignore[attr-defined]
        helper.bella_transparent = True  # type: ignore[attr-defined]
        helper.bella_classdict = in_class  # type: ignore[attr-defined]
        value: ast.expr = ast.Call(func=ast.Name(id=store, ctx=ast.Load()), args=[], keywords=[])
        for d in reversed(decorators):
            value = ast.Call(func=d, args=[value], keywords=[])
        out: list[ast.stmt] = [helper, ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=value),
                               ast.Delete(targets=[ast.Name(id=store, ctx=ast.Del())])]
        return [ast.fix_missing_locations(_copy_loc(o, node)) for o in out]


def _assign_tuple(names: list[str], value: ast.expr) -> ast.stmt:
    return ast.Assign(targets=[ast.Tuple(elts=[ast.Name(id=n, ctx=ast.Store()) for n in names], ctx=ast.Store())], value=value)


@register(PassSpec(
    name="desugar-type-params", source=Level.L0, target=Level.L0,
    requires=frozenset({Fact.ANNOTATIONS_EXPLICIT}),
    produces=frozenset({Fact.NO_TYPE_PARAMS}),
    obligations=(
        Obligation("wf", "no type parameter list or type alias statement remains"),
        Obligation("semantics", "the generic scope as 3.15.2 compiles it: decorators first, type parameters with lazy bounds, constraints and defaults, Generic[...] after a class's bases, __type_params__ set, an alias's value lazy"),
        Obligation("terminates", "one rewrite per generic definition or alias"),
    ),
    discharge=Discharge.TESTED, status="tested",
))
def desugar_type_params(tree: ast.Module) -> ast.Module:
    return ast.fix_missing_locations(_TypeParams().run(tree))


class _FunctionAnnotations:
    """A function's annotations as 3.15.2 compiles them (PEP 649): its __annotate__(format, /),
    defined where the function is defined (inside a generic function's type-parameter scope, so
    it sees the type parameters; reading the class namespace first in a class), raising
    NotImplementedError above VALUE_WITH_FAKE_GLOBALS (2), else returning the dict in CPython's
    order: positional-only, positional, *args, keyword-only, **kwargs, return, each name mangled
    in a class. A starred annotation (`*args: *Ts`) is unpacked to its one item (UNPACK_SEQUENCE 1).
    Under PEP 563 the values are the annotations' source text, taken here, before any other
    pass rewrites an expression (review 2026-11-02, G6 2.1).

    The function is an ordinary definition placed just before the one it annotates, so every
    later pass lowers it as what it is (comprehensions, f-strings, private names); to-l1 attaches
    it to that function (L1 FunctionDef.annotate) instead of binding it."""

    def __init__(self, future: bool) -> None:
        self.future = future
        self.scopes: list[tuple[str, str | None]] = [("module", None)]   # (kind, the class that mangles)

    def run(self, tree: ast.Module) -> ast.Module:
        tree.body = self.block(tree.body)
        return tree

    def block(self, stmts: list[ast.stmt]) -> list[ast.stmt]:
        out: list[ast.stmt] = []
        for s in stmts:
            if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
                annotate = self.annotate(s)
                if getattr(s, "bella_transparent", False):
                    kind = "generic in class" if getattr(s, "bella_classdict", False) else "generic"
                else:
                    kind = "function"
                self.scopes.append((kind, self.scopes[-1][1]))
                s.body = self.block(s.body)
                self.scopes.pop()
                out += [annotate, s] if annotate is not None else [s]
                continue
            if isinstance(s, ast.ClassDef):
                self.scopes.append(("class", s.name))
                s.body = self.block(s.body)
                self.scopes.pop()
                out.append(s)
                continue
            for fld in ("body", "orelse", "finalbody"):
                inner = getattr(s, fld, None)
                if isinstance(inner, list) and inner and isinstance(inner[0], ast.stmt):
                    setattr(s, fld, self.block(inner))
            for h in getattr(s, "handlers", []):
                h.body = self.block(h.body)
            for case in getattr(s, "cases", []):
                case.body = self.block(case.body)
            out.append(s)
        return out

    def annotate(self, f: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.FunctionDef | None:
        a = f.args
        params = [*a.posonlyargs, *a.args, *([a.vararg] if a.vararg else []), *a.kwonlyargs, *([a.kwarg] if a.kwarg else [])]
        items: list[tuple[str, ast.expr]] = [(p.arg, p.annotation) for p in params if p.annotation is not None]
        if f.returns is not None:
            items.append(("return", f.returns))
        if not items:
            return None
        kind, private = self.scopes[-1]
        fmt, d = _tmp("format"), _tmp("ann")
        body: list[ast.stmt] = [
            ast.If(test=ast.Compare(left=ast.Name(id=fmt, ctx=ast.Load()), ops=[ast.Gt()], comparators=[ast.Constant(2)]),
                   body=[ast.Raise(exc=_intrinsic("NotImplementedError"), cause=None)], orelse=[]),
            ast.Assign(targets=[ast.Name(id=d, ctx=ast.Store())], value=ast.Dict(keys=[], values=[]))]
        for key, e in items:
            value: ast.expr
            if self.future:
                value = ast.Constant(ast.unparse(e))
            elif isinstance(e, ast.Starred):
                one = _tmp("unpacked")
                body.append(_copy_loc(ast.Assign(targets=[ast.Tuple(elts=[ast.Name(id=one, ctx=ast.Store())], ctx=ast.Store())],
                                                 value=e.value), e))
                value = ast.Name(id=one, ctx=ast.Load())
            else:
                value = e
            body.append(_copy_loc(ast.Assign(targets=[ast.Subscript(value=ast.Name(id=d, ctx=ast.Load()),
                                                                    slice=ast.Constant(mangle(private, key)), ctx=ast.Store())],
                                             value=value), e))
        body.append(ast.Return(ast.Name(id=d, ctx=ast.Load())))
        for p in params:
            p.annotation = None
        f.returns = None
        fn = ast.FunctionDef(name=_tmp("annotate"), args=ast.arguments(posonlyargs=[ast.arg(arg=fmt)], args=[], kwonlyargs=[],
                                                                       kw_defaults=[], defaults=[]),
                             body=body, decorator_list=[], returns=None, type_params=[])
        fn.bella_public = {fmt: "format"}  # type: ignore[attr-defined]
        fn.bella_annotation = True  # type: ignore[attr-defined]
        # under PEP 563 the values are strings and CPython makes no annotation scope, so nothing
        # reads the class namespace (no __classdict__ cell; measured against co_freevars)
        fn.bella_classdict = not self.future and kind in ("class", "generic in class")  # type: ignore[attr-defined]
        fn.bella_annotate_for = f.name  # type: ignore[attr-defined]
        f.bella_annotate = fn.name  # type: ignore[union-attr]
        return ast.fix_missing_locations(_copy_loc(fn, f))


@register(PassSpec(
    name="desugar-function-annotations", source=Level.L0, target=Level.L0,
    requires=frozenset({Fact.NO_TYPE_PARAMS}),
    produces=frozenset({Fact.FUNCTION_ANNOTATIONS_EXPLICIT}),
    obligations=(
        Obligation("wf", "no function parameter or return annotation remains; each annotated function is preceded by its __annotate__ definition, marked for it"),
        Obligation("semantics", "PEP 649 as 3.15.2 compiles a function's annotations: evaluated only when __annotate__ is called, in the scope that defines the function, in CPython's order with mangled names; under PEP 563 their source text as written"),
        Obligation("terminates", "one rewrite per annotated function"),
    ),
    discharge=Discharge.TESTED, status="tested",
))
def desugar_function_annotations(tree: ast.Module) -> ast.Module:
    return ast.fix_missing_locations(_FunctionAnnotations("annotations" in getattr(tree, "bella_future", ())).run(tree))


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


def _needs_classdict(cls: ast.ClassDef, future: bool) -> bool:
    """symtable 3.14+: a class whose own body defines a function (anywhere in its statements,
    not inside a nested function or class) or has an annotation gets the __classdict__ cell,
    which holds the namespace while the body runs and is stored as __classdictcell__ (measured
    on 3.15.2). Under PEP 563 no annotation scope reads the class, so only a generic definition
    or a type alias makes the cell: its type-parameter scope or its value's (measured on 3.15.2,
    review 2026-11-02)."""
    if not future and getattr(cls, "bella_has_annotations", False):
        return True

    def makes_cell(f: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        if not future:
            return True
        # a generic definition's scope, or a type alias's value (desugar-type-params)
        return bool(getattr(f, "bella_transparent", False)) or \
            (bool(getattr(f, "bella_annotation", False)) and not getattr(f, "bella_annotate_for", None))

    def walk(stmts: list[ast.stmt]) -> bool:
        for s in stmts:
            if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)) and makes_cell(s):
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

    def __init__(self, future: bool = False) -> None:
        self.future = future                 # PEP 563
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
        if isinstance(n, ast.GeneratorExp):
            n.generators[0].iter = self.node(n.generators[0].iter)  # type: ignore[assignment]  # evaluated in the enclosing scope
            n.bella_qualname = self.qualname("<genexpr>")  # type: ignore[attr-defined]
            in_class = self.stack[-1][4] or self.stack[-1][0] == "class"
            self.stack.append(("function", n.bella_qualname, frozenset(), None, in_class))  # type: ignore[attr-defined]
            n.elt = self.node(n.elt)  # type: ignore[assignment]
            for i, g in enumerate(n.generators):
                g.target = self.node(g.target)  # type: ignore[assignment]
                if i:
                    g.iter = self.node(g.iter)  # type: ignore[assignment]
                g.ifs = [self.node(c) for c in g.ifs]  # type: ignore[misc]
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
        if getattr(f, "bella_transparent", False):
            # a generic scope: its own qualname, and none in what it defines (an annotation scope)
            f.bella_qualname = self.qualname(f.name)  # type: ignore[union-attr]
            f.body = self.block(f.body)
            return f
        annotated = getattr(f, "bella_annotate_for", None)
        f.bella_qualname = (f"{self.qualname(annotated)}.__annotate__" if annotated  # type: ignore[union-attr]
                            else self.qualname(f.name))
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
        if getattr(c, "bella_type_params", None):
            prologue.append(store("__type_params__", ast.Name(id=c.bella_type_params, ctx=ast.Load())))  # type: ignore[attr-defined]
        if getattr(c, "bella_setup_annotations", False):
            prologue.append(_setup_annotations())      # PEP 563: codegen_body, before the docstring
        doc = _docstring(c.body)
        if doc is not None:
            body = [store("__doc__", ast.Constant(doc)), *body[1:]]
        epilogue = [store("__static_attributes__", ast.Tuple(elts=[ast.Constant(a) for a in attributes], ctx=ast.Load()))]
        classdict = _needs_classdict(c, self.future)
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
    requires=frozenset({Fact.FUNCTION_ANNOTATIONS_EXPLICIT}),
    produces=frozenset({Fact.CLASS_BODIES_EXPLICIT}),
    obligations=(
        Obligation("wf", "every class body starts with the __module__, __qualname__ and __firstlineno__ stores and ends with __static_attributes__ (and __classcell__ when needed); no zero-argument super() call remains in a function"),
        Obligation("semantics", "the namespace a class body leaves is CPython's (names, values, order of stores); super() reads the __class__ cell and the first argument as CPython's does"),
        Obligation("terminates", "one rewrite per class and per super() call"),
    ),
    discharge=Discharge.TESTED, status="tested",
))
def desugar_class_body(tree: ast.Module) -> ast.Module:
    return ast.fix_missing_locations(_ClassBodies("annotations" in getattr(tree, "bella_future", ())).run(tree))


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
    arguments in calls are not mangled (measured on 3.15.2).

    The type-parameter scope of a generic class (and the scopes inside it, up to the class body)
    mangles only the type parameters' names, with the class's own name: _Py_MaybeMangle and
    ste_mangled_names (Python/symtable.c, 3.15.2), so `class Box[__T]: v = __T` binds and reads
    _Box__T while any other private name there stays as written (review 2026-11-02, G6 2.3.2)."""

    def __init__(self) -> None:
        self.private: str | None = None
        self.only: frozenset[str] | None = None      # ste_mangled_names, when set

    def mangle(self, name: str) -> str:
        if self.only is not None and name not in self.only:
            return name
        return mangle(self.private, name)

    def visit(self, n: ast.AST) -> None:
        p, only = self.private, self.only
        if isinstance(n, ast.ClassDef):
            for e in [*n.decorator_list, *n.bases, *(k.value for k in n.keywords)]:
                self.visit(e)
            n.bella_store = self.mangle(n.name)  # type: ignore[attr-defined]
            self.private, self.only = n.name, None
            for s in n.body:
                self.visit(s)
            self.private, self.only = p, only
            return
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            n.bella_store = self.mangle(getattr(n, "bella_store", n.name))  # type: ignore[union-attr]
            scoped = getattr(n, "bella_mangle_only", None)
            if scoped is not None:
                self.private, self.only = scoped
                for child in ast.iter_child_nodes(n):
                    self.visit(child)
                self.private, self.only = p, only
                return
        if isinstance(n, ast.arg):
            n.arg = self.mangle(n.arg)
        elif isinstance(n, ast.Name):
            n.id = self.mangle(n.id)
        elif isinstance(n, ast.Attribute):
            n.attr = self.mangle(n.attr)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            n.names = [self.mangle(x) for x in n.names]
        elif isinstance(n, ast.ExceptHandler) and n.name:
            n.name = self.mangle(n.name)
        elif isinstance(n, (ast.MatchAs, ast.MatchStar)) and n.name:
            n.name = self.mangle(n.name)
        elif isinstance(n, ast.MatchMapping) and n.rest:
            n.rest = self.mangle(n.rest)
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                a.bella_raw = a.name  # type: ignore[attr-defined]  # the fromlist keeps it unmangled (codegen)
                if a.name != "*":
                    a.name = self.mangle(a.name)
                if a.asname:
                    a.asname = self.mangle(a.asname)
        elif isinstance(n, ast.Import):
            for a in n.names:
                a.bella_store = self.mangle(a.asname or a.name.partition(".")[0])  # type: ignore[attr-defined]
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


class _Imports:
    """Import statements as CPython 3.15.2's codegen compiles them (Python/codegen.c), in
    intrinsic calls and ordinary stores:

        import a.b.c          a = import_name("a.b.c", None, 0, mode)
        import a.b.c as d     d = import_from(import_from(import_name("a.b.c", None, 0, mode), "b"), "c")
        from m import x as y  t = import_name("m", ("x",), level, mode); y = import_from(t, "x")
        from m import *       import_star(import_name("m", ("*",), level, "eager"))

    The mode is decided where codegen decides it, on the original structure: "lazy" for
    `lazy import` (module scope only), "eager" in a function or class, in a try body, an except
    handler, a finally block or anything a finally guards, and for `import *`; otherwise
    "default", which __lazy_modules__ can make lazy at runtime."""

    def __init__(self) -> None:
        self.scope = "module"
        self.guarded = 0

    def run(self, tree: ast.Module) -> ast.Module:
        tree.body = self.block(tree.body)
        return tree

    def block(self, body: list[ast.stmt]) -> list[ast.stmt]:
        out: list[ast.stmt] = []
        for s in body:
            out.extend(self.stmt(s))
        return out

    def mode(self, lazy: bool, line: int) -> str:
        if lazy:
            if self.scope != "module":
                raise SyntaxError(f"lazy imports only allowed in module scope (line {line})")
            return "lazy"
        return "eager" if self.scope != "module" or self.guarded else "default"

    def stmt(self, s: ast.stmt) -> list[ast.stmt]:
        if isinstance(s, ast.Import):
            return self.import_(s)
        if isinstance(s, ast.ImportFrom):
            return self.import_from(s)
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            saved, saved_guard = self.scope, self.guarded
            self.scope, self.guarded = ("class" if isinstance(s, ast.ClassDef) else "function"), 0
            s.body = self.block(s.body)
            self.scope, self.guarded = saved, saved_guard
            return [s]
        if isinstance(s, (ast.Try, ast.TryStar)):
            finally_ = bool(s.finalbody)
            self.guarded += 1
            s.body = self.block(s.body)
            for h in s.handlers:
                h.body = self.block(h.body)
            self.guarded -= 1
            # a try's else is outside its handlers; a finally guards everything in the statement
            self.guarded += finally_
            s.orelse = self.block(s.orelse)
            s.finalbody = self.block(s.finalbody)
            self.guarded -= finally_
            return [s]
        for fld in ("body", "orelse"):
            inner = getattr(s, fld, None)
            if isinstance(inner, list) and inner and isinstance(inner[0], ast.stmt):
                setattr(s, fld, self.block(inner))
        for case in getattr(s, "cases", []):
            case.body = self.block(case.body)
        return [s]

    def import_(self, s: ast.Import) -> list[ast.stmt]:
        mode = self.mode(bool(getattr(s, "is_lazy", False)), s.lineno)
        out: list[ast.stmt] = []
        for a in s.names:
            value: ast.expr = _call("import_name", ast.Constant(a.name), ast.Constant(None), ast.Constant(0), ast.Constant(mode))
            if a.asname:
                for part in a.name.split(".")[1:]:
                    value = _call("import_from", value, ast.Constant(part))
            store = getattr(a, "bella_store", a.asname or a.name.partition(".")[0])
            out.append(ast.Assign(targets=[ast.Name(id=store, ctx=ast.Store())], value=value))
        return [ast.fix_missing_locations(_copy_loc(o, s)) for o in out]

    def import_from(self, s: ast.ImportFrom) -> list[ast.stmt]:
        lazy = bool(getattr(s, "is_lazy", False))
        star = s.names[0].name == "*"
        if star and lazy:
            raise SyntaxError(f"cannot lazy import * (line {s.lineno})")
        if star and self.scope == "function":
            raise SyntaxError(f"import * only allowed at module level (line {s.lineno})")
        mode = "eager" if star and not lazy else self.mode(lazy, s.lineno)
        fromlist = ast.Constant(tuple(getattr(a, "bella_raw", a.name) for a in s.names))  # type: ignore[arg-type]  # codegen's tuple constant
        imported = _call("import_name", ast.Constant(s.module or ""), fromlist, ast.Constant(s.level), ast.Constant(mode))
        if star:
            return [ast.fix_missing_locations(_copy_loc(ast.Expr(_call("import_star", imported)), s))]
        module = _tmp("mod")
        out: list[ast.stmt] = [ast.Assign(targets=[ast.Name(id=module, ctx=ast.Store())], value=imported)]
        for a in s.names:
            value = _call("import_from", ast.Name(id=module, ctx=ast.Load()), ast.Constant(a.name))
            out.append(ast.Assign(targets=[ast.Name(id=a.asname or a.name, ctx=ast.Store())], value=value))
        out.append(ast.Delete(targets=[ast.Name(id=module, ctx=ast.Del())]))
        return [ast.fix_missing_locations(_copy_loc(o, s)) for o in out]


def _call(intrinsic: str, *args: ast.expr) -> ast.Call:
    return ast.Call(func=_intrinsic(intrinsic), args=list(args), keywords=[])


@register(PassSpec(
    name="desugar-imports", source=Level.L0, target=Level.L0,
    requires=frozenset({Fact.PRIVATE_NAMES_MANGLED}),
    produces=frozenset({Fact.NO_IMPORTS}),
    obligations=(
        Obligation("wf", "no Import or ImportFrom node remains; lazy imports only at module scope, import * not in a function"),
        Obligation("semantics", "each import runs IMPORT_NAME, IMPORT_FROM and the stores in codegen's order, with the mode codegen gives it (lazy, eager in functions, classes and try/except/finally, default elsewhere), the fromlist unmangled"),
        Obligation("terminates", "one rewrite per import statement"),
    ),
    discharge=Discharge.TESTED, status="tested",
))
def desugar_imports(tree: ast.Module) -> ast.Module:
    return ast.fix_missing_locations(_Imports().run(tree))


class _SeveralTargets(ast.NodeTransformer):
    """`a = b[i] = v`: v once, then stored to each target left to right, as CPython's COPY and
    stores do; the temporary is deleted afterwards so that it holds the value no longer."""

    def visit_Assign(self, node: ast.Assign) -> Any:
        self.generic_visit(node)
        if len(node.targets) == 1:
            return node
        t = _tmp("val")
        out: list[ast.stmt] = [ast.Assign(targets=[ast.Name(id=t, ctx=ast.Store())], value=node.value)]
        out += [ast.Assign(targets=[target], value=ast.Name(id=t, ctx=ast.Load())) for target in node.targets]
        out.append(ast.Delete(targets=[ast.Name(id=t, ctx=ast.Del())]))
        return [ast.fix_missing_locations(_copy_loc(s, node)) for s in out]


@register(PassSpec(
    name="desugar-several-targets", source=Level.L0, target=Level.L0,
    produces=frozenset({Fact.SINGLE_TARGETS}),
    obligations=(
        Obligation("wf", "every Assign has one target"),
        Obligation("semantics", "the value is evaluated once, then stored to the targets left to right, each target's own expressions evaluated when it is stored to"),
        Obligation("terminates", "one rewrite per assignment"),
    ),
    discharge=Discharge.TESTED, status="tested",
))
def desugar_several_targets(tree: ast.Module) -> ast.Module:
    return _as_module(ast.fix_missing_locations(_SeveralTargets().visit(tree)))


def _is_wildcard(p: ast.pattern) -> bool:
    return isinstance(p, ast.MatchAs) and p.pattern is None and p.name is None


def _irrefutable(p: ast.pattern) -> bool:
    if isinstance(p, ast.MatchAs):
        return p.pattern is None or _irrefutable(p.pattern)
    if isinstance(p, ast.MatchOr):
        return any(_irrefutable(alt) for alt in p.patterns)
    return False


def _pattern_names(p: ast.pattern) -> list[str]:
    """The names a pattern binds, in the order CPython stores them (codegen's pc->stores):
    depth first, left to right, an `as` name after its pattern, an or-pattern's in its first
    alternative's order; with its compile-time errors."""
    out: list[str] = []

    def add(name: str | None, line: int) -> None:
        if name is None:
            return
        if name in out:
            raise SyntaxError(f"multiple assignments to name {name!r} in pattern (line {line})")
        out.append(name)

    def walk(q: ast.pattern) -> None:
        if isinstance(q, ast.MatchAs):
            if q.pattern is not None:
                walk(q.pattern)
            add(q.name, q.lineno)
        elif isinstance(q, ast.MatchStar):
            add(q.name, q.lineno)
        elif isinstance(q, ast.MatchSequence):
            if sum(isinstance(x, ast.MatchStar) for x in q.patterns) > 1:
                raise SyntaxError(f"multiple starred names in sequence pattern (line {q.lineno})")
            for x in q.patterns:
                walk(x)
        elif isinstance(q, ast.MatchMapping):
            seen: list[object] = []
            for k in q.keys:
                if isinstance(k, (ast.Constant, ast.UnaryOp, ast.BinOp)):
                    # CPython checks the key after its AST optimiser folded a signed or complex
                    # literal (-1, 1+2j) into a constant (review 2026-11-02, G6 2.6.1)
                    value = ast.literal_eval(k)
                    if value in seen:
                        raise SyntaxError(f"mapping pattern checks duplicate key ({value!r}) (line {q.lineno})")
                    seen.append(value)
                elif not isinstance(k, ast.Attribute):
                    raise SyntaxError(f"mapping pattern keys may only match literals and attribute lookups (line {q.lineno})")
            for x in q.patterns:
                walk(x)
            add(q.rest, q.lineno)
        elif isinstance(q, ast.MatchClass):
            for x in [*q.patterns, *q.kwd_patterns]:
                walk(x)
        elif isinstance(q, ast.MatchOr):
            first = _pattern_names(q.patterns[0])
            for i, alt in enumerate(q.patterns):
                if i < len(q.patterns) - 1 and _irrefutable(alt):
                    raise SyntaxError(f"wildcard makes remaining patterns unreachable (line {alt.lineno})"
                                      if not isinstance(alt, ast.MatchAs) or alt.name is None else
                                      f"name capture {alt.name!r} makes remaining patterns unreachable (line {alt.lineno})")
                if set(_pattern_names(alt)) != set(first):
                    raise SyntaxError(f"alternative patterns bind different names (line {q.lineno})")
            for name in first:
                add(name, q.lineno)
    walk(p)
    return out


class _Match(ast.NodeTransformer):
    """`match`, as CPython 3.15.2's codegen compiles it (Python/codegen.c), in ordinary checks and
    the helpers of runtime/prelude/match.py (MATCH_SEQUENCE, MATCH_MAPPING, MATCH_KEYS,
    MATCH_CLASS): the subject once; the cases in order; a pattern's captures stored, in
    codegen's order, once the whole pattern has matched and before the guard; an or-pattern
    committed to the first alternative that matches; sequence items unpacked (UNPACK_SEQUENCE
    or UNPACK_EX), or taken by subscript, len() at each access, when the star is a wildcard;
    mapping values by the subject's get(); class attributes by __match_args__ and getattr.
    A case's pattern temporaries stand for CPython's stack slots and are released where those
    are popped, newest first: once a pattern has matched and stored its captures (before the
    guard), and right after the case on the paths where it failed (review 2026-11-02)."""

    _CLEAR = "__bella_clear_pattern_temporaries__"

    def tmp(self, prefix: str) -> str:
        name = _tmp(prefix)
        self.case_temps.append(name)
        return name

    def visit_Match(self, node: ast.Match) -> Any:
        self.generic_visit(node)
        subj, done = _tmp("subj"), _tmp("done")
        out: list[ast.stmt] = [_assign(subj, node.subject), _assign(done, ast.Constant(False))]
        for i, case in enumerate(node.cases):
            if i < len(node.cases) - 1 and case.guard is None and _irrefutable(case.pattern):
                p = case.pattern
                name = p.name if isinstance(p, ast.MatchAs) and p.pattern is None else None
                raise SyntaxError(f"name capture {name!r} makes remaining patterns unreachable (line {p.lineno})"
                                  if name else f"wildcard makes remaining patterns unreachable (line {p.lineno})")
            names = _pattern_names(case.pattern)
            self.case_temps: list[str] = []
            self.captures = {n: self.tmp("cap") for n in names}
            success: list[ast.stmt] = [_assign(done, ast.Constant(True)),
                                       ast.Delete(targets=[ast.Name(id=subj, ctx=ast.Del())]), *case.body]
            then: list[ast.stmt] = [_assign(n, ast.Name(id=self.captures[n], ctx=ast.Load())) for n in names]
            then.append(ast.Expr(ast.Constant(self._CLEAR)))
            then += [ast.If(test=case.guard, body=success, orelse=[])] if case.guard is not None else success
            tested = self.pattern(case.pattern, ast.Name(id=subj, ctx=ast.Load()), then)
            clear = [_assign(t, ast.Constant(None)) for t in reversed(self.case_temps)]
            out.append(ast.If(test=ast.UnaryOp(op=ast.Not(), operand=ast.Name(id=done, ctx=ast.Load())),
                              body=self._place(tested, clear), orelse=[]))
            out += [_assign(t, ast.Constant(None)) for t in reversed(self.case_temps)]   # the failed paths
        out.append(ast.If(test=ast.UnaryOp(op=ast.Not(), operand=ast.Name(id=done, ctx=ast.Load())),
                          body=[ast.Delete(targets=[ast.Name(id=subj, ctx=ast.Del())])], orelse=[]))
        out.append(ast.Delete(targets=[ast.Name(id=done, ctx=ast.Del())]))
        return [ast.fix_missing_locations(_copy_loc(o, node)) for o in out]

    def _place(self, stmts: list[ast.stmt], clear: list[ast.stmt]) -> list[ast.stmt]:
        """The marker in the success path becomes the clearing statements."""
        out: list[ast.stmt] = []
        for st in stmts:
            if isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and st.value.value == self._CLEAR:
                out += [_assign(t.targets[0].id, ast.Constant(None)) for t in clear if isinstance(t, ast.Assign)
                        and isinstance(t.targets[0], ast.Name)]
                continue
            for fld in ("body", "orelse"):
                if isinstance(getattr(st, fld, None), list):
                    setattr(st, fld, self._place(getattr(st, fld), clear))
            out.append(st)
        return out

    def capture(self, name: str | None, value: ast.expr) -> list[ast.stmt]:
        return [] if name is None else [_assign(self.captures[name], value)]

    def pattern(self, p: ast.pattern, subj: ast.expr, then: list[ast.stmt]) -> list[ast.stmt]:
        if isinstance(p, ast.MatchValue):
            return [ast.If(test=ast.Compare(left=subj, ops=[ast.Eq()], comparators=[p.value]), body=then, orelse=[])]
        if isinstance(p, ast.MatchSingleton):
            return [ast.If(test=ast.Compare(left=subj, ops=[ast.Is()], comparators=[ast.Constant(p.value)]),
                           body=then, orelse=[])]
        if isinstance(p, ast.MatchAs):
            if p.pattern is None:
                return [*self.capture(p.name, subj), *then]
            return self.pattern(p.pattern, subj, [*self.capture(p.name, subj), *then])
        if isinstance(p, ast.MatchOr):
            ok = self.tmp("alt")
            out: list[ast.stmt] = [_assign(ok, ast.Constant(False))]
            for i, alt in enumerate(p.patterns):
                code = self.pattern(alt, subj, [_assign(ok, ast.Constant(True))])
                out += code if i == 0 else [ast.If(test=ast.UnaryOp(op=ast.Not(), operand=ast.Name(id=ok, ctx=ast.Load())),
                                                   body=code, orelse=[])]
            return [*out, ast.If(test=ast.Name(id=ok, ctx=ast.Load()), body=then, orelse=[])]
        if isinstance(p, ast.MatchSequence):
            return self.sequence(p, subj, then)
        if isinstance(p, ast.MatchMapping):
            return self.mapping(p, subj, then)
        if isinstance(p, ast.MatchClass):
            cls, attrs = self.tmp("cls"), self.tmp("attrs")
            subs = [*p.patterns, *p.kwd_patterns]
            inner = self.chain([(sub, _item(attrs, i)) for i, sub in enumerate(subs) if not _is_wildcard(sub)], then)
            return [_assign(cls, p.cls),
                    _assign(attrs, _call("match_class", ast.Name(id=cls, ctx=ast.Load()), subj, ast.Constant(len(p.patterns)),
                                         ast.Constant(tuple(p.kwd_attrs)))),  # type: ignore[arg-type]  # a tuple constant
                    ast.If(test=_is_not_none(attrs), body=inner, orelse=[])]
        raise L.Unsupported(f"pattern {type(p).__name__} (line {p.lineno})")

    def chain(self, steps: list[tuple[ast.pattern, ast.expr]], then: list[ast.stmt]) -> list[ast.stmt]:
        """Each sub-pattern on its value, in order, the next only if the previous matched."""
        code = then
        for sub, value in reversed(steps):
            code = self.pattern(sub, value, code)
        return code

    def sequence(self, p: ast.MatchSequence, subj: ast.expr, then: list[ast.stmt]) -> list[ast.stmt]:
        size = len(p.patterns)
        star = next((i for i, x in enumerate(p.patterns) if isinstance(x, ast.MatchStar)), -1)
        star_wildcard = star >= 0 and p.patterns[star].name is None  # type: ignore[attr-defined]
        only_wildcard = all(_is_wildcard(x) or (isinstance(x, ast.MatchStar) and x.name is None) for x in p.patterns)
        length = ast.Call(func=_intrinsic("len"), args=[subj], keywords=[])
        if only_wildcard:
            body = then
        elif star_wildcard:
            body = then
            for i in reversed(range(size)):
                sub = p.patterns[i]
                if i == star or _is_wildcard(sub):
                    continue
                index: ast.expr = ast.Constant(i) if i < star else ast.BinOp(
                    left=ast.Call(func=_intrinsic("len"), args=[subj], keywords=[]), op=ast.Sub(), right=ast.Constant(size - i))
                item = self.tmp("item")
                body = [_assign(item, ast.Subscript(value=subj, slice=index, ctx=ast.Load())),
                        *self.pattern(sub, ast.Name(id=item, ctx=ast.Load()), body)]
        else:
            items = self.tmp("items")
            before, after = (size, -1) if star < 0 else (star, size - star - 1)
            steps = [(sub, _item(items, i)) for i, sub in enumerate(p.patterns)]
            body = [_assign(items, _call("unpack", subj, ast.Constant(before), ast.Constant(after))),
                    *self.chain([(sub if not isinstance(sub, ast.MatchStar) else
                                  ast.MatchAs(pattern=None, name=sub.name), value) for sub, value in steps], then)]
        if star < 0:
            body = [ast.If(test=ast.Compare(left=length, ops=[ast.Eq()], comparators=[ast.Constant(size)]), body=body, orelse=[])]
        elif size > 1:
            body = [ast.If(test=ast.Compare(left=length, ops=[ast.GtE()], comparators=[ast.Constant(size - 1)]),
                           body=body, orelse=[])]
        return [ast.If(test=_call("match_is_sequence", subj), body=body, orelse=[])]

    def mapping(self, p: ast.MatchMapping, subj: ast.expr, then: list[ast.stmt]) -> list[ast.stmt]:
        size = len(p.keys)
        if not size and p.rest is None:
            body = then
        else:
            keys, values = self.tmp("keys"), self.tmp("values")
            rest = self.capture(p.rest, _call("mapping_rest", subj, ast.Name(id=keys, ctx=ast.Load()))) if p.rest else []
            inner = self.chain([(sub, _item(values, i)) for i, sub in enumerate(p.patterns)], [*rest, *then])
            body = [_assign(keys, ast.Tuple(elts=list(p.keys), ctx=ast.Load())),
                    _assign(values, _call("match_keys", subj, ast.Name(id=keys, ctx=ast.Load()))),
                    ast.If(test=_is_not_none(values), body=inner, orelse=[])]
            if size:
                body = [ast.If(test=ast.Compare(left=ast.Call(func=_intrinsic("len"), args=[subj], keywords=[]),
                                                ops=[ast.GtE()], comparators=[ast.Constant(size)]), body=body, orelse=[])]
        return [ast.If(test=_call("match_is_mapping", subj), body=body, orelse=[])]


def _assign(name: str, value: ast.expr) -> ast.stmt:
    return ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=value)


def _item(name: str, i: int) -> ast.expr:
    return ast.Subscript(value=ast.Name(id=name, ctx=ast.Load()), slice=ast.Constant(i), ctx=ast.Load())


def _is_not_none(name: str) -> ast.expr:
    return ast.Compare(left=ast.Name(id=name, ctx=ast.Load()), ops=[ast.IsNot()], comparators=[ast.Constant(None)])


@register(PassSpec(
    name="desugar-match", source=Level.L0, target=Level.L0,
    requires=frozenset({Fact.PRIVATE_NAMES_MANGLED}),
    produces=frozenset({Fact.NO_MATCH}),
    obligations=(
        Obligation("wf", "no Match node remains; codegen's compile-time pattern errors are raised"),
        Obligation("semantics", "the subject once, cases in order, captures stored in codegen's order after a whole pattern matches and before the guard, or-patterns committed to their first matching alternative, and the MATCH_* instructions' order of effects (runtime/prelude/match.py)"),
        Obligation("terminates", "one rewrite per match statement and per pattern node"),
    ),
    discharge=Discharge.TESTED, status="tested",
))
def desugar_match(tree: ast.Module) -> ast.Module:
    return _as_module(ast.fix_missing_locations(_Match().visit(tree)))


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
        # %special is CPython's special-method lookup (_PyObject_LookupSpecial): the type's MRO,
        # bound through the descriptor protocol, TypeError when missing. CPython 3.15 looks up
        # __exit__ before __enter__ (review 2026-11-01, gemini 2.2.5.2; measured on 3.15.2).
        mgr, exit_, enter, value, exc, err = (_tmp("mgr"), _tmp("exit"), _tmp("enter"), _tmp("val"), _tmp("exc"), _tmp("err"))
        # The references die where CPython's stack drops them (measured on 3.15.2 with __del__
        # probes): the manager is held only through the bound __exit__ once both methods are looked
        # up, the bound __enter__ dies after its call, the value once the target holds it (at once
        # with no target, and before __exit__ when assigning the target fails), and __exit__ when
        # the statement ends, on every path. A failed lookup or __enter__ releases them all before
        # the exception goes on (review 2026-11-02, A8-3). The names are set to None rather than
        # deleted, so that each path can release them whether or not it had bound them. The
        # handler's BaseException is the builtin, whatever the program binds to the name (A8-8).
        src = f"""
{mgr} = None
{exit_} = None
{enter} = None
try:
    {exit_} = __special__({mgr}, "__exit__")
    {enter} = __special__({mgr}, "__enter__")
    {mgr} = None
    {value} = {enter}()
    {enter} = None
except BaseException:
    {mgr} = None
    {enter} = None
    {exit_} = None
    raise
{exc} = True
try:
    try:
        pass
    except BaseException as {err}:
        {value} = None
        {exc} = False
        if not {exit_}(type({err}), {err}, {err}.__traceback__):
            raise
finally:
    try:
        if {exc}:
            {exit_}(None, None, None)
    finally:
        {exit_} = None
"""
        stmts = ast.parse(src).body
        for n in ast.walk(ast.Module(stmts, [])):
            if isinstance(n, ast.Name) and n.id in ("type", "BaseException"):
                n.id = _INTRINSIC + n.id
            elif isinstance(n, ast.Name) and n.id == "__special__":
                n.id = _INTRINSIC + "special"     # an intrinsic too: no program binding reaches it
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
        inner_body.append(_assign(value, ast.Constant(None)))
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


def _walrus_targets(nodes: list[ast.AST]) -> list[str]:
    """PEP 572: the names a comprehension's walrus expressions bind (nested comprehensions
    included, lambdas not: they are scopes of their own), in source order."""
    out: list[str] = []

    def walk(n: ast.AST) -> None:
        if isinstance(n, ast.Lambda):
            return
        if isinstance(n, ast.NamedExpr) and isinstance(n.target, ast.Name) and n.target.id not in out:
            out.append(n.target.id)
        for child in ast.iter_child_nodes(n):
            walk(child)
    for n in nodes:
        walk(n)
    return out


class _Comprehensions(ast.NodeTransformer):
    """Each comprehension becomes a helper taking iter(<outermost iterable>), defined just before
    the statement in the scope that contains the comprehension, so that it closes over that
    scope as a comprehension does; the outermost iterable is evaluated in that scope, the rest
    inside the helper, and the loop variables do not leak (PEP 709's observable behaviour;
    review 2026-11-01, astra-low-01 #5, gemini 2.2.2).

    * list, set, dict: the helper builds the container (dict items with the key evaluated
      before the value, as MAP_ADD) and returns it;
    * generator expression: the helper is a generator function named <genexpr>, with CPython's
      qualname, called with the iterator, as CPython calls its genexpr code;
    * a walrus target binds in the containing scope (PEP 572): the helper declares it nonlocal
      (global at module level) and the containing function binds it; in a class body it is a
      SyntaxError, as in CPython.

    Comprehensions in a lambda's body are hoisted into the lambda itself (its prelude). The
    transformer does not enter nested function bodies: ``_hoist`` lowers each body in its own
    scope."""

    def __init__(self, scope: str, globals_: frozenset[str] = frozenset()) -> None:
        self.hoisted: list[ast.stmt] = []
        self.scope = scope                       # "module", "function" or "class"
        self.globals_ = globals_                 # the names the containing function declares global

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        # decorators and defaults run in the enclosing scope; the body is lowered by _hoist
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        node.args.defaults = [self.visit(d) for d in node.args.defaults]
        node.args.kw_defaults = [self.visit(d) if d is not None else None for d in node.args.kw_defaults]
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        return self.visit_FunctionDef(node)  # type: ignore[arg-type]

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        # the header runs in this scope; the body is lowered by _hoist
        node.decorator_list = [self.visit(d) for d in node.decorator_list]
        node.bases = [self.visit(b) for b in node.bases]
        for k in node.keywords:
            k.value = self.visit(k.value)
        return node

    def visit_Lambda(self, node: ast.Lambda) -> ast.AST:
        node.args.defaults = [self.visit(d) for d in node.args.defaults]
        node.args.kw_defaults = [self.visit(d) if d is not None else None for d in node.args.kw_defaults]
        inner = _Comprehensions("function")
        node.body = inner.visit(node.body)
        node.bella_prelude = inner.hoisted  # type: ignore[attr-defined]  # helpers, made at each call
        return node

    def visit_ListComp(self, node: ast.ListComp) -> ast.AST:
        return self.comprehension(node, "list")

    def visit_SetComp(self, node: ast.SetComp) -> ast.AST:
        return self.comprehension(node, "set")

    def visit_DictComp(self, node: ast.DictComp) -> ast.AST:
        return self.comprehension(node, "dict")

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> ast.AST:
        return self.comprehension(node, "genexp")

    def comprehension(self, node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp, kind: str) -> ast.AST:
        if not isinstance(node, ast.DictComp) and isinstance(node.elt, ast.Starred):
            raise L.Unsupported("unpacking in a comprehension (PEP 798, new in 3.15) is [P2+]")
        if any(g.is_async for g in node.generators):
            raise L.Unsupported("async comprehension")
        fname, res, arg = _tmp("gen" if kind == "genexp" else "comp"), _tmp("res"), _tmp("it")
        outer_iter = self.visit(node.generators[0].iter)      # evaluated in this scope
        res_load = ast.Name(id=res, ctx=ast.Load())
        action: ast.stmt
        if isinstance(node, ast.DictComp):
            assert node.key is not None      # a dict comprehension's key (None only marks ** in a display)
            action = ast.Expr(ast.Call(func=_intrinsic("map_add"), args=[res_load, node.key, node.value],  # type: ignore[list-item]
                                       keywords=[]))
        elif kind == "genexp":
            action = ast.Expr(ast.Yield(value=node.elt))
        else:
            action = ast.Expr(ast.Call(func=ast.Attribute(value=res_load, attr="append" if kind == "list" else "add",
                                                          ctx=ast.Load()), args=[node.elt], keywords=[]))
        inner: list[ast.stmt] = [action]
        for i, gen in enumerate(reversed(node.generators)):
            for cond in reversed(gen.ifs):
                inner = [ast.If(test=cond, body=inner, orelse=[])]
            is_outer = i == len(node.generators) - 1
            iterable = ast.Name(id=arg, ctx=ast.Load()) if is_outer else gen.iter
            inner = [ast.For(target=gen.target, iter=iterable, body=inner, orelse=[])]
            if is_outer:
                inner[0].bella_iterator = True  # type: ignore[attr-defined]  # the iterator GET_ITER made outside (A7-4)
        parts: list[ast.AST] = [node.key, node.value] if isinstance(node, ast.DictComp) and node.key else [node.elt]  # type: ignore[union-attr, list-item]
        parts += [c for g in node.generators for c in g.ifs] + [g.iter for g in node.generators[1:]]
        bound_outside = _walrus_targets(parts)
        body: list[ast.stmt] = []
        # PEP 572: a walrus target binds in the containing scope, honouring its global declaration
        # (review 2026-11-02, G6 2.4.2); the helper's own comprehensions see the same names global
        declared_global = [n for n in bound_outside if self.scope != "function" or n in self.globals_]
        declared_nonlocal = [n for n in bound_outside if n not in declared_global]
        if bound_outside:
            if self.scope == "class":
                raise SyntaxError("assignment expression within a comprehension cannot be used in a class body "
                                  f"(line {node.lineno})")
            if declared_global:
                body.append(ast.Global(names=declared_global))
            if declared_nonlocal:
                body.append(ast.Nonlocal(names=declared_nonlocal))
        if kind != "genexp":
            init: ast.expr = (ast.List(elts=[], ctx=ast.Load()) if kind == "list" else ast.Dict(keys=[], values=[])
                              if kind == "dict" else ast.Call(func=_intrinsic("set"), args=[], keywords=[]))
            body.append(ast.Assign(targets=[ast.Name(id=res, ctx=ast.Store())], value=init))
        body += inner
        if kind != "genexp":
            body.append(ast.Return(ast.Name(id=res, ctx=ast.Load())))
        for st in body:
            ast.copy_location(st, node)
            ast.fix_missing_locations(st)
        fn = ast.FunctionDef(
            name="<genexpr>" if kind == "genexp" else fname,
            args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=arg)], kwonlyargs=[], kw_defaults=[], defaults=[]),
            body=_hoist(body, "function", frozenset(declared_global)),   # comprehensions in the element, conditions or inner loops
            decorator_list=[], returns=None, type_params=[])
        fn.bella_store = fname  # type: ignore[attr-defined]
        fn.bella_qualname = getattr(node, "bella_qualname", None)  # type: ignore[attr-defined]
        if declared_nonlocal:
            fn.bella_enclosing_binds = declared_nonlocal  # type: ignore[attr-defined]
        self.hoisted.append(ast.fix_missing_locations(_copy_loc(fn, node)))
        return ast.fix_missing_locations(_copy_loc(ast.Call(
            func=ast.Name(id=fname, ctx=ast.Load()),
            args=[ast.Call(func=_intrinsic("iter"), args=[outer_iter], keywords=[])],
            keywords=[]), node))


def _hoist(stmts: list[ast.stmt], scope: str = "module", globals_: frozenset[str] = frozenset()) -> list[ast.stmt]:
    """`globals_`: the names the function whose statements these are declares global."""
    out: list[ast.stmt] = []
    for s in stmts:
        tr = _Comprehensions(scope, globals_)
        s = tr.visit(s)
        inner, inner_globals = scope, globals_
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
            inner, inner_globals = "function", frozenset(declarations(s.body)[0])
        elif isinstance(s, ast.ClassDef):
            inner, inner_globals = "class", frozenset()
        for fld in ("body", "orelse", "finalbody"):
            if hasattr(s, fld) and isinstance(getattr(s, fld), list):
                setattr(s, fld, _hoist(getattr(s, fld), inner, inner_globals))
        if isinstance(s, (ast.Try, ast.TryStar)):
            for h in s.handlers:
                h.body = _hoist(h.body, scope, globals_)
        for case in getattr(s, "cases", []):
            case.body = _hoist(case.body, scope, globals_)
        out.extend(tr.hoisted)
        out.append(s)
    return out


@register(PassSpec(
    name="desugar-listcomp", source=Level.L0, target=Level.L0,
    produces=frozenset({Fact.NO_COMPREHENSIONS}),
    obligations=(
        Obligation("wf", "output contains no ListComp, SetComp, DictComp or GeneratorExp node"),
        Obligation("semantics", "the outermost iterable is evaluated (and iter() called) in the enclosing scope before the loop; the helper is defined in the comprehension's own scope so it sees that scope's names; loop variables do not leak (PEP 709 observable behaviour); elements added in order, a dict's key before its value; a generator expression is a generator named <genexpr>; walrus targets bind in the containing scope (PEP 572)"),
        Obligation("terminates", "one helper per comprehension"),
    ),
    discharge=Discharge.TESTED, status="tested",
))
def desugar_listcomp(tree: ast.Module) -> ast.Module:
    tree.body = _hoist(tree.body, "module")
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


class _TemplateStr(_FString):
    """PEP 750 t-strings: Template(*parts), each replacement field an Interpolation(value, its
    source text, its conversion, its format spec), evaluated in order as BUILD_INTERPOLATION and
    BUILD_TEMPLATE evaluate them; a format spec is an f-string, desugared as one."""

    def visit_TemplateStr(self, node: ast.TemplateStr) -> ast.AST:
        self.generic_visit(node)
        parts: list[ast.expr] = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                parts.append(v)
            elif isinstance(v, ast.Interpolation):
                conversion = {-1: None, 115: "s", 114: "r", 97: "a"}[v.conversion]
                spec: ast.expr = v.format_spec if v.format_spec is not None else ast.Constant("")
                parts.append(ast.Call(func=_intrinsic("interpolation"),
                                      args=[v.value, ast.Constant(v.str), ast.Constant(conversion), spec], keywords=[]))
            else:
                raise L.Unsupported(f"t-string part {type(v).__name__}")
        return ast.fix_missing_locations(_copy_loc(ast.Call(func=_intrinsic("template"), args=parts, keywords=[]), node))


@register(PassSpec(
    name="desugar-fstring", source=Level.L0, target=Level.L0,
    produces=frozenset({Fact.NO_FSTRINGS}),
    obligations=(
        Obligation("wf", "output contains no JoinedStr or TemplateStr node"),
        Obligation("semantics", "each replacement field is format(conversion(value), spec) evaluated left to right, joined in order"),
        Obligation("terminates", "one rewrite per JoinedStr"),
    ),
    discharge=Discharge.TESTED, status="tested",
))
def desugar_fstring(tree: ast.Module) -> ast.Module:
    return _as_module(ast.fix_missing_locations(_TemplateStr().visit(tree)))


class _Decorators(ast.NodeTransformer):
    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        return self.visit_FunctionDef(node)  # type: ignore[arg-type]  # the same rewrite: temps before, applied once

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        return self.visit_FunctionDef(node)  # type: ignore[arg-type]

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


def _yields(body: list[ast.stmt]) -> bool:
    """The code yields (a generator): a yield in it, not in a nested function, lambda or class."""
    def walk(n: ast.AST) -> bool:
        if isinstance(n, (ast.Yield, ast.YieldFrom)):
            return True
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            return False
        return any(walk(c) for c in ast.iter_child_nodes(n))
    return any(walk(s) for s in body)


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
        self.annotates: dict[str, L.FunctionDef] = {}   # desugar-function-annotations' functions, by marker

    def module(self, tree: ast.Module, source: str) -> L.Module:
        self.units = [_Unit("module", "")]
        return L.Module(line=1, body=self.block(tree.body), source=source)

    def qualname(self, name: str) -> str:
        """compiler_set_qualname: <parent>.<locals>.name in a function, <parent>.name in a class,
        and the bare name at module level or when the parent declares the name global."""
        parent = self.units[-1]
        if parent.kind == "module" or name in parent.globals:
            return name
        return f"{parent.qualname}.<locals>.{name}" if parent.kind == "function" else f"{parent.qualname}.{name}"

    # ---- statements -------------------------------------------------------------------------
    def block(self, stmts: list[ast.stmt]) -> tuple[L.Stmt, ...]:
        out: list[L.Stmt] = []
        for s in stmts:
            if isinstance(s, ast.FunctionDef) and getattr(s, "bella_annotate_for", None):
                # a function's __annotate__ (desugar-function-annotations): made with it, never bound
                self.annotates[s.name] = dataclasses.replace(self.function(s), name="__annotate__")
                continue
            out.append(self.stmt(s))
        return tuple(out)

    def stmt(self, s: ast.stmt) -> L.Stmt:
        ln = s.lineno
        if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call) and isinstance(s.value.func, ast.Name) \
                and s.value.func.id == _INTRINSIC + "declare":
            arg = s.value.args[0]
            assert isinstance(arg, ast.Constant) and isinstance(arg.value, str)
            return L.Declare(ln, (arg.value,))
        if isinstance(s, ast.Expr):
            return L.ExprStmt(ln, self.expr(s.value))
        if isinstance(s, ast.Assign):
            if len(s.targets) != 1:
                raise L.Unsupported("several assignment targets must be desugared first")
            return L.Assign(ln, self.target(s.targets[0]), self.expr(s.value))
        if isinstance(s, ast.AnnAssign):
            raise L.Unsupported(f"annotations must be desugared first (line {ln})")

        if isinstance(s, ast.AugAssign):
            return L.AugAssign(ln, self.target(s.target), _BINOPS[type(s.op)], self.expr(s.value))
        if isinstance(s, ast.Return):
            return L.Return(ln, self.expr(s.value) if s.value is not None else None)
        if isinstance(s, ast.If):
            return L.If(ln, self.truth(s.test), self.block(s.body), self.block(s.orelse))
        if isinstance(s, ast.While):
            return L.While(ln, self.truth(s.test), self.block(s.body), self.block(s.orelse))
        if isinstance(s, ast.For):
            return L.For(ln, self.target(s.target), self.expr(s.iter), self.block(s.body), self.block(s.orelse),
                         iterator=bool(getattr(s, "bella_iterator", False)))
        if isinstance(s, ast.Break):
            return L.Break(ln)
        if isinstance(s, ast.Continue):
            return L.Continue(ln)
        if isinstance(s, ast.Pass):
            return L.Pass(ln)
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
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
        if isinstance(s, (ast.Import, ast.ImportFrom)):
            raise L.Unsupported(f"imports must be desugared first (line {ln})")
        if isinstance(s, ast.TypeAlias):
            raise L.Unsupported(f"type aliases must be desugared first (line {ln})")
        raise L.Unsupported(f"statement {type(s).__name__} (line {ln})")

    def params(self, a: ast.arguments, owner: str, public: dict[str, str] | None = None) -> tuple[L.Param, ...]:
        positional = [*a.posonlyargs, *a.args]
        defaults: list[ast.expr | None] = [None] * (len(positional) - len(a.defaults)) + list(a.defaults)
        out = [L.Param(arg.arg, self.expr(d) if d is not None else None,
                       "positional-only" if i < len(a.posonlyargs) else "positional-or-keyword",
                       (public or {}).get(arg.arg))
               for i, (arg, d) in enumerate(zip(positional, defaults, strict=True))]
        if a.vararg:
            out.append(L.Param(a.vararg.arg, None, "*args"))
        out += [L.Param(arg.arg, self.expr(d) if d is not None else None, "keyword-only")
                for arg, d in zip(a.kwonlyargs, a.kw_defaults, strict=True)]
        if a.kwarg:
            out.append(L.Param(a.kwarg.arg, None, "**kwargs"))
        return tuple(out)

    def function(self, f: ast.FunctionDef | ast.AsyncFunctionDef) -> L.FunctionDef:
        if f.decorator_list:
            raise L.Unsupported("decorators must be desugared first")
        yields = _yields(f.body)
        if isinstance(f, ast.AsyncFunctionDef):
            kind = "async generator" if yields else "coroutine"
        else:
            kind = "generator" if yields else "function"
        if f.type_params:
            raise L.Unsupported(f"type parameters must be desugared first ({f.name}, line {f.lineno})")
        params = self.params(f.args, f.name, getattr(f, "bella_public", None))
        qualname = getattr(f, "bella_qualname", None) or self.qualname(f.name)
        globals_, nonlocals = declarations(f.body)
        annotate = self.annotates.pop(getattr(f, "bella_annotate", ""), None)
        in_class = bool(self.units) and (self.units[-1].kind == "class" or self.units[-1].kind == "generic in class")
        kind_of_unit = ("generic in class" if in_class else "generic") if getattr(f, "bella_transparent", False) else "function"
        self.units.append(_Unit(kind_of_unit, qualname, frozenset(globals_)))
        try:
            # an async def's body runs only when its coroutine runs, which is [P2+]: not lowered
            body = self.block(f.body) if kind in ("function", "generator") else ()
        finally:
            self.units.pop()
        decorators = tuple(L.Name(f.lineno, t) for t in getattr(f, "bella_decorators", []))
        return L.FunctionDef(f.lineno, f.name, params, body, frozenset(globals_), frozenset(nonlocals),
                             qualname=qualname, decorators=decorators, annotate=annotate, docstring=_docstring(f.body),
                             store=getattr(f, "bella_store", "") if getattr(f, "bella_store", f.name) != f.name else "",
                             kind=kind, enclosing_binds=frozenset(getattr(f, "bella_enclosing_binds", ())),
                             annotation=bool(getattr(f, "bella_annotation", False)),
                             classdict=bool(getattr(f, "bella_classdict", False)))

    def class_(self, c: ast.ClassDef) -> L.Assign:
        """``C = d1(d2(build_class(<body>, "C", *bases, **keywords)))``: the decorators (already
        evaluated into names) applied once to what build_class returns, then one store."""
        ln = c.lineno
        if c.type_params:
            raise L.Unsupported(f"type parameters must be desugared first (class {c.name}, line {ln})")
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
            prelude = self.block(getattr(e, "bella_prelude", []))
            body = self.expr(e.body)
        finally:
            self.units.pop()
        return L.Lambda(e.lineno, params, body, qualname, "generator" if _yields([ast.Expr(e.body)]) else "function",
                        prelude)

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
            return L.TupleTarget(ln, tuple(L.StarTarget(e.lineno, self.target(e.value)) if isinstance(e, ast.Starred)
                                           else self.target(e) for e in t.elts))
        raise L.Unsupported(f"assignment target {type(t).__name__} (line {ln})")

    # ---- expressions ------------------------------------------------------------------------
    def truth(self, e: ast.expr) -> L.Truth:
        return L.Truth(e.lineno, self.expr(e))

    def expr(self, e: ast.expr) -> L.Expr:
        ln = e.lineno
        if isinstance(e, ast.Constant):
            value: object = e.value
            if isinstance(value, tuple) and all(isinstance(x, str) for x in value):
                return L.TupleLit(ln, tuple(L.Const(ln, x) for x in value))       # an import's fromlist
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
        if isinstance(e, ast.Yield):
            return L.Yield(ln, self.expr(e.value) if e.value is not None else None)
        if isinstance(e, ast.YieldFrom):
            return L.YieldFrom(ln, self.expr(e.value))
        if isinstance(e, ast.Attribute):
            return L.GetAttr(ln, self.expr(e.value), e.attr)
        if isinstance(e, ast.Subscript):
            return L.GetItem(ln, self.expr(e.value), self.expr(e.slice))
        if isinstance(e, ast.Slice):
            parts = [self.expr(p) if p is not None else L.Const(ln, None) for p in (e.lower, e.upper, e.step)]
            return L.Call(ln, L.Intrinsic(ln, "slice"), tuple(parts))      # BUILD_SLICE, whatever `slice` names
        if isinstance(e, (ast.List, ast.Tuple, ast.Set)):
            items = tuple(L.Starred(x.lineno, self.expr(x.value)) if isinstance(x, ast.Starred) else self.expr(x)
                          for x in e.elts)
            return (L.ListLit if isinstance(e, ast.List) else L.TupleLit if isinstance(e, ast.Tuple) else L.SetLit)(ln, items)
        if isinstance(e, ast.Dict):
            return L.DictLit(ln, tuple(self.expr(k) if k is not None else None for k in e.keys),
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
                        Fact.CLASS_BODIES_EXPLICIT, Fact.PRIVATE_NAMES_MANGLED, Fact.NO_IMPORTS, Fact.SINGLE_TARGETS, Fact.NO_MATCH,
                        Fact.ANNOTATIONS_EXPLICIT, Fact.NO_TYPE_PARAMS, Fact.FUNCTION_ANNOTATIONS_EXPLICIT}),
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


FRONTEND_PASSES = ["desugar-annotations", "desugar-type-params", "desugar-function-annotations", "desugar-class-body", "desugar-private-names", "desugar-imports", "desugar-several-targets", "desugar-match",
                   "desugar-chained-compare", "desugar-with",
                   "desugar-listcomp", "desugar-fstring", "desugar-decorators", "to-l1"]


def check_compile(tree: ast.Module | ast.Expression, filename: str, mode: str, inherit_future: frozenset[str]) -> None:
    """Every compile-time error of CPython 3.15.2, from its own compiler: the symbol table's and
    the code generator's (a nonlocal without a binding, a parameter declared global, `import *`
    outside a module, a lazy import in a try, `yield` in a comprehension, a repeated attribute in
    a class pattern, ...), raised as the SyntaxError CPython raises (review 2026-11-02, G6 2.4.3,
    2.6.2, 2.7.2, 2.7.3). The host is the pinned interpreter (check_host_grammar), so "what does
    CPython reject?" is answered by asking it. The parsed tree is compiled, before any pass
    rewrites it, and the code is dropped; the parser's warnings were already given by
    ast.parse, and the compiler's are not repeated here."""
    flags = 0
    for name in inherit_future:
        flags |= getattr(__future__, name).compiler_flag
    with warnings.catch_warnings(module=warnings):          # the host's module, whatever sys.modules holds
        warnings.simplefilter("ignore")
        compile(tree, filename, mode, flags=flags, dont_inherit=True)


def check_host_grammar() -> None:
    """L0 is the host interpreter's own ast, so the host's minor version *is* the accepted grammar.
    The three settings stay distinct -- host interpreter (pyproject), semantic reference
    (bella.toml [reference].python), accepted grammar ([reference].grammar) -- and this is the one
    place their coupling is enforced (review 2026-11-01, astra-low-02, gate step 1)."""
    pinned = tomllib.loads((Path(__file__).resolve().parents[2] / "bella.toml").read_text(encoding="utf-8"))
    grammar = str(pinned["reference"]["grammar"])
    host = f"{sys.version_info.major}.{sys.version_info.minor}"
    if host != grammar:
        raise RuntimeError(f"the frontend parses with the host ast: host Python {host} != bella.toml grammar {grammar}")


_FUTURE_FEATURES = frozenset({"nested_scopes", "generators", "division", "absolute_import", "with_statement",
                              "print_function", "unicode_literals", "barry_as_FLUFL", "generator_stop", "annotations"})


def future_features(tree: ast.Module) -> frozenset[str]:
    """The __future__ features a module enables (Python/future.c): `from __future__ import` at its
    beginning (after a docstring); one anywhere else, or an unknown feature, is a SyntaxError."""
    features: set[str] = set()
    leading = True
    for i, s in enumerate(tree.body):
        if i == 0 and isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str):
            continue
        if isinstance(s, ast.ImportFrom) and s.module == "__future__" and s.level == 0:
            if not leading:
                raise SyntaxError(f"from __future__ imports must occur at the beginning of the file (line {s.lineno})")
            for a in s.names:
                if a.name == "braces":
                    raise SyntaxError(f"not a chance (line {s.lineno})")
                if a.name not in _FUTURE_FEATURES:
                    raise SyntaxError(f"future feature {a.name} is not defined (line {s.lineno})")
                features.add(a.name)
            continue
        leading = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "__future__" and node.level == 0 \
                and not any(node is s for s in tree.body):
            raise SyntaxError(f"from __future__ imports must occur at the beginning of the file (line {node.lineno})")
    return frozenset(features)


def lower(source: str, filename: str = "<module>", mode: str = "exec",
          inherit_future: frozenset[str] = frozenset()) -> L.Module:
    """Parse and lower a program to L1 through the registered passes in fact order. Mode "eval"
    lowers an expression (a staged eval text): the module's last statement is its value.
    `inherit_future` are the caller's __future__ features (a staged exec text compiled in the
    context of the function that runs it)."""
    check_host_grammar()
    if mode == "eval":
        expression = ast.parse(source, filename=filename, mode="eval")
        check_compile(expression, filename, mode, inherit_future)
        tree = ast.Module([ast.fix_missing_locations(ast.copy_location(ast.Expr(expression.body), expression.body))], [])
    else:
        tree = ast.parse(source, filename=filename)
        check_compile(tree, filename, mode, inherit_future)
    check_finally(tree)
    tree.bella_source = filename  # type: ignore[attr-defined]
    tree.bella_future = future_features(tree) | inherit_future  # type: ignore[attr-defined]
    _TAKEN.clear()
    _TAKEN.update(_identifiers(tree))
    _SYNTHETIC.clear()
    module = manager.run(tree, manager.pipeline(FRONTEND_PASSES))
    assert isinstance(module, L.Module)
    return dataclasses.replace(module, synthetic=frozenset(_SYNTHETIC), future=tree.bella_future, mode=mode)  # type: ignore[attr-defined]
