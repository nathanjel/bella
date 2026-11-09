"""The second entry point of a compiler-generated `__annotate__` (decision S-1, docs/staging.md).

CPython's compiler-generated `__annotate__` answers VALUE and VALUE_WITH_FAKE_GLOBALS and raises
NotImplementedError for FORWARDREF and STRING. `annotationlib.call_annotate_function` then re-runs
`annotate.__code__` against substitute globals (a `_StringifierDict`) and cells (`_build_closure`).
A compiled program has no code object to re-run. Instead the compiler generates, next to each
`__annotate__`, an evaluator `__annotate__(format, globals, cells)` that evaluates the same
annotation expressions, in the same order, with every name load done as CPython's opcode does it
against the given mapping and cells (annotate_rt.py). The `annotationlib` shim calls it where
CPython calls the rebuilt function, so FORWARDREF and STRING are CPython's, ForwardRef objects
for names not bound yet included.

This module is that part of the compiler, written from the source as the compiler sees it: the
scopes and their bindings, name mangling, which annotations of a module or class body are
conditional, and the shape of the result (a dict display for a function; entry by entry, with
`__conditional_annotations__` checks, for a class or module). Each evaluator is checked at build
time against the code CPython compiles from the same source, twice, and kept only if both agree:

* statically: the name loads it performs, in order and by kind, are the bytecode's loads;
* by running: under STRING's substitute globals and under FORWARDREF's second run (no
  globals), it returns or raises exactly what re-running CPython's code does.

An annotation the generator cannot handle (a lambda, a comprehension, a t-string) gets no
evaluator; the shim then refuses the fallback with the milestone's marker. Nothing is
approximated.
"""
from __future__ import annotations

import annotationlib
import ast
import copy
import dis
import types
from collections.abc import Callable
from dataclasses import dataclass, field

from pipeline.staging import annotate_rt

_StringifierDict = vars(annotationlib)["_StringifierDict"]
_build_closure = vars(annotationlib)["_build_closure"]
_stringify_single = vars(annotationlib)["_stringify_single"]
_LOADS = ("LOAD_GLOBAL", "LOAD_DEREF", "LOAD_FROM_DICT_OR_GLOBALS", "LOAD_FROM_DICT_OR_DEREF")
_UNSUPPORTED = (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.NamedExpr,
                ast.Await, ast.Yield, ast.YieldFrom, ast.TemplateStr)
RUNTIME = "_rt"        # the evaluator's one global: the helpers of annotate_rt.py


class Unsupported(Exception):
    """A construct the generator does not handle; its annotate function gets no evaluator."""


@dataclass
class Evaluator:
    key: str
    freevars: tuple[str, ...]
    source: str
    code: types.CodeType


@dataclass
class _Scope:
    kind: str                         # module | function | class | typeparams
    name: str
    parent: _Scope | None
    bound: set[str] = field(default_factory=set)
    declared_global: set[str] = field(default_factory=set)   # a class body's `global` too (G5 3.5)


Entry = tuple[str, ast.expr, int | None, bool]     # (key, annotation, conditional index, *-unpack)


@dataclass
class _Owner:
    kind: str                         # function | class | module | evaluate (PEP 695: one value)
    scope: _Scope                     # the scope the annotation scope sits in (a class: its own)
    sees_class: bool                  # the annotation scope reads a class namespace (__classdict__)
    private: str | None               # the class name used for mangling
    type_params: set[str]
    entries: list[Entry]
    strings: bool = False             # PEP 563: the function's __annotate__ returns the annotations' source strings


entry_key = annotate_rt.entry_key       # the identity the build files an evaluator under


def mangle(private: str | None, name: str) -> str:
    """_Py_Mangle: `__x` inside class `C` is `_C__x`; dunders, dotted names and all-underscore
    class names are left alone."""
    if private is None or not name.startswith("__") or name.endswith("__") or "." in name:
        return name
    stripped = private.lstrip("_")
    return f"_{stripped}{name}" if stripped else name


class _Bindings(ast.NodeVisitor):
    """The names one function body binds, not descending into nested scopes."""

    def __init__(self) -> None:
        self.bound: set[str] = set()
        self.declared_global: set[str] = set()
        self.nonlocal_: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.bound.add(node.id)

    def visit_Global(self, node: ast.Global) -> None:
        self.declared_global.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.nonlocal_.update(node.names)

    def visit_Import(self, node: ast.Import) -> None:
        self.bound.update(a.asname or a.name.split(".")[0] for a in node.names)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.bound.update(a.asname or a.name for a in node.names)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.bound.add(node.name)
        for d in (*node.decorator_list, *node.args.defaults, *(d for d in node.args.kw_defaults if d)):
            self.visit(d)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.bound.add(node.name)
        for e in (*node.decorator_list, *node.bases, *(k.value for k in node.keywords)):
            self.visit(e)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for d in (*node.args.defaults, *(d for d in node.args.kw_defaults if d)):
            self.visit(d)

    def _comprehension(self, node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp) -> None:
        # the iteration variables are the comprehension's own; a walrus inside binds here, unless
        # it is inside a lambda (G5 3.5)
        self.bound |= walrus_targets(node)
        self.visit(node.generators[0].iter)

    visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = _comprehension

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self.bound.add(node.name)
        self.generic_visit(node)

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        if node.name:
            self.bound.add(node.name)
        self.generic_visit(node)

    def visit_MatchStar(self, node: ast.MatchStar) -> None:
        if node.name:
            self.bound.add(node.name)

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        if node.rest:
            self.bound.add(node.rest)
        self.generic_visit(node)


def walrus_targets(node: ast.AST) -> set[str]:
    """The names walruses bind in the scope around a comprehension: through nested comprehensions,
    not into a lambda, whose walrus binds in the lambda (the same rule as tools/closure.py's)."""
    found: set[str] = set()
    stack: list[ast.AST] = [node]
    while stack:
        n = stack.pop()
        if isinstance(n, ast.NamedExpr) and isinstance(n.target, ast.Name):
            found.add(n.target.id)
        if not isinstance(n, ast.Lambda):
            stack.extend(ast.iter_child_nodes(n))
    return found


def _function_scope(node: ast.FunctionDef | ast.AsyncFunctionDef, parent: _Scope, private: str | None) -> _Scope:
    """A function's bindings, mangled as CPython's symbol table mangles them inside a class (G5 3.5)."""
    b = _Bindings()
    a = node.args
    params = [*a.posonlyargs, *a.args, *a.kwonlyargs, *([a.vararg] if a.vararg else []), *([a.kwarg] if a.kwarg else [])]
    b.bound.update(p.arg for p in params)
    for stmt in node.body:
        b.visit(stmt)
    bound = {mangle(private, n) for n in (b.bound - b.declared_global) - b.nonlocal_}
    return _Scope("function", node.name, parent, bound, {mangle(private, n) for n in b.declared_global})


TypeParam = ast.TypeVar | ast.ParamSpec | ast.TypeVarTuple    # the concrete ast.type_param classes


def _params(params: list[ast.type_param]) -> list[TypeParam]:
    return [p for p in params if isinstance(p, (ast.TypeVar, ast.ParamSpec, ast.TypeVarTuple))]


def _typeparams_scope(params: list[ast.type_param], parent: _Scope, name: str, private: str | None) -> _Scope | None:
    """A type-parameter scope; its names mangled with `private` (the enclosing class for a function
    or an alias, the class itself for a class: G5 3.5)."""
    return _Scope("typeparams", name, parent, {mangle(private, p.name) for p in _params(params)}) if params else None


def _body_entries(body: list[ast.stmt], conditional: bool, counter: list[int], private: str | None,
                  module: bool) -> list[Entry]:
    """The simple annotations of a class or module body in source order, with the conditional
    index CPython gives them: in a module every one is conditional; in a class, those inside a
    compound statement. A non-simple target (`x.y: int`) is no annotation and takes no index."""
    out: list[Entry] = []
    for stmt in body:
        if isinstance(stmt, ast.AnnAssign):
            if stmt.simple and isinstance(stmt.target, ast.Name):
                index = None
                if module or conditional:
                    index = counter[0]
                    counter[0] += 1
                out.append((stmt.target.id if module else mangle(private, stmt.target.id), stmt.annotation, index, False))
            continue
        blocks: list[list[ast.stmt]] = []
        if isinstance(stmt, (ast.If, ast.For, ast.AsyncFor, ast.While)):
            blocks = [stmt.body, stmt.orelse]
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            blocks = [stmt.body]
        elif isinstance(stmt, (ast.Try, ast.TryStar)):
            blocks = [stmt.body, *(h.body for h in stmt.handlers), stmt.orelse, stmt.finalbody]
        elif isinstance(stmt, ast.Match):
            blocks = [c.body for c in stmt.cases]
        for block in blocks:
            out += _body_entries(block, True, counter, private, module)
    return out


class _Owners(ast.NodeVisitor):
    """Every annotation owner of a module, with the scope its annotations are evaluated in."""

    def __init__(self, pep563: bool = False) -> None:
        self.owners: list[_Owner] = []
        self.scope = _Scope("module", "<module>", None)
        self.private: str | None = None
        # PEP 563 makes annotations strings, with no __annotate__; PEP 695's evaluate functions
        # remain (review 2026-11-02 gemini-4-argon-high-05, 3.3)
        self.pep563 = pep563

    def _type_params(self, params: list[ast.type_param], tp: _Scope | None, private: str | None) -> None:
        """PEP 695: each bound, constraint tuple and default is evaluated lazily by a function of
        its own, inside the type-parameter scope (an evaluate function, like an annotate one). A
        starred default (`*Ts = *tuple[int, str]`) is unpacked, as `*args: *Ts` is (G5 3.4)."""
        for p in _params(params):
            for expr in (p.bound if isinstance(p, ast.TypeVar) else None, p.default_value):
                if expr is not None and tp is not None:
                    starred = isinstance(expr, ast.Starred)
                    inner = expr.value if isinstance(expr, ast.Starred) else expr
                    self.owners.append(_Owner("evaluate", tp, self.scope.kind == "class", private, set(),
                                              [("", inner, None, starred)]))

    def visit_TypeAlias(self, node: ast.TypeAlias) -> None:
        tp = _typeparams_scope(node.type_params, self.scope, node.name.id, self.private)
        self._type_params(node.type_params, tp, self.private)
        self.owners.append(_Owner("evaluate", tp or self.scope, self.scope.kind == "class", self.private, set(),
                                  [("", node.value, None, False)]))

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        outer, private = self.scope, self.private
        for e in (*node.decorator_list, *node.args.defaults, *(d for d in node.args.kw_defaults if d)):
            self.visit(e)
        tp = _typeparams_scope(node.type_params, outer, node.name, private)
        self._type_params(node.type_params, tp, private)
        a = node.args
        entries: list[Entry] = []
        for p in (*a.posonlyargs, *a.args):
            if p.annotation:
                entries.append((mangle(private, p.arg), p.annotation, None, False))
        if a.vararg and a.vararg.annotation:
            ann = a.vararg.annotation
            starred = isinstance(ann, ast.Starred)
            entries.append((mangle(private, a.vararg.arg), ann.value if isinstance(ann, ast.Starred) else ann, None, starred))
        for p in a.kwonlyargs:
            if p.annotation:
                entries.append((mangle(private, p.arg), p.annotation, None, False))
        if a.kwarg and a.kwarg.annotation:
            entries.append((mangle(private, a.kwarg.arg), a.kwarg.annotation, None, False))
        if node.returns:
            entries.append(("return", node.returns, None, False))
        if entries and not self.pep563:
            self.owners.append(_Owner("function", tp or outer, outer.kind == "class", private,
                                      {mangle(private, p.name) for p in _params(node.type_params)}, entries))
        elif entries:                 # under the future import the compiler still makes the function's __annotate__, of strings
            self.owners.append(_Owner("function", tp or outer, False, private, set(), entries, strings=True))
        self.scope = _function_scope(node, tp or outer, private)
        for stmt in node.body:
            self.visit(stmt)
        self.scope = outer

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        outer, private = self.scope, self.private
        for e in (*node.decorator_list, *node.bases, *(k.value for k in node.keywords)):
            self.visit(e)
        # a class's type parameters are mangled with the class itself; their bounds and defaults
        # are evaluated with no class to mangle with (G5 3.5)
        tp = _typeparams_scope(node.type_params, outer, node.name, node.name)
        self._type_params(node.type_params, tp, None)
        declared = _Bindings()
        for stmt in node.body:
            if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                declared.visit(stmt)
        cls = _Scope("class", node.name, tp or outer, set(), {mangle(node.name, n) for n in declared.declared_global})
        entries = _body_entries(node.body, False, [0], node.name, module=False)
        if entries and not self.pep563:
            self.owners.append(_Owner("class", cls, True, node.name,
                                      {mangle(node.name, p.name) for p in _params(node.type_params)}, entries))
        self.scope, self.private = cls, node.name
        for stmt in node.body:
            self.visit(stmt)
        self.scope, self.private = outer, private

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return          # a lambda has no annotations, and nothing inside one owns any


def _resolve(owner: _Owner, name: str) -> str:
    """'free' if a function or type-parameter scope above binds the name, else 'global'."""
    if name in owner.type_params:
        return "free"
    scope: _Scope | None = owner.scope
    if owner.kind == "class" and scope is not None:
        scope = scope.parent              # the class body's own names come through __classdict__
    while scope is not None:
        if scope.kind in ("function", "typeparams"):
            if name in scope.declared_global:
                return "global"
            if name in scope.bound:
                return "free"
        elif scope.kind == "module":
            return "global"
        scope = scope.parent              # a class scope is not visible from nested scopes
    return "global"


def _visible_class(owner: _Owner) -> _Scope | None:
    """The class whose namespace an annotation scope reads, if any."""
    scope: _Scope | None = owner.scope
    while scope is not None and scope.kind == "typeparams":
        scope = scope.parent
    return scope if scope is not None and scope.kind == "class" else None


def _call(fn: str, *args: ast.expr) -> ast.Call:
    return ast.Call(ast.Attribute(ast.Name(RUNTIME, ast.Load()), fn, ast.Load()), list(args), [])


def _name(n: str) -> ast.Name:
    return ast.Name(n, ast.Load())


class _Rewrite(ast.NodeTransformer):
    """An annotation expression with each name load replaced by its opcode's helper. `loads`
    records them in evaluation order, in the bytecode's vocabulary, for the static check."""

    def __init__(self, owner: _Owner) -> None:
        self.owner = owner
        self.loads: list[tuple[str, str]] = []
        self.free: set[str] = set()

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        # CPython mangles a private attribute name in a class too (C.__v is C._C__v; review
        # 2026-11-02 astra-low-06, A6-4), not a keyword argument's name
        node.attr = mangle(self.owner.private, node.attr)
        return self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> ast.expr:
        if not isinstance(node.ctx, ast.Load):
            raise Unsupported(f"a {type(node.ctx).__name__} of {node.id}")
        name = mangle(self.owner.private, node.id)
        kind = _resolve(self.owner, name)
        visible = _visible_class(self.owner)
        if self.owner.sees_class and visible is not None and name in visible.declared_global:
            # a class body's `global` reaches past the class namespace (G5 3.5)
            self.loads.append(("LOAD_GLOBAL", name))
            return ast.copy_location(_call("load_global", _name("_g"), _name("_b"), ast.Constant(name)), node)
        if kind == "free":
            self.free.add(name)
        if self.owner.sees_class:
            classdict = _call("load_deref", _name("_c"), ast.Constant("__classdict__"))
            self.loads.append(("LOAD_DEREF", "__classdict__"))
            if kind == "free":
                self.loads.append(("LOAD_FROM_DICT_OR_DEREF", name))
                new: ast.expr = _call("load_dict_or_deref", classdict, _name("_c"), ast.Constant(name))
            else:
                self.loads.append(("LOAD_FROM_DICT_OR_GLOBALS", name))
                new = _call("load_dict_or_global", classdict, _name("_g"), _name("_b"), ast.Constant(name))
        elif kind == "free":
            self.loads.append(("LOAD_DEREF", name))
            new = _call("load_deref", _name("_c"), ast.Constant(name))
        else:
            self.loads.append(("LOAD_GLOBAL", name))
            new = _call("load_global", _name("_g"), _name("_b"), ast.Constant(name))
        return ast.copy_location(new, node)

    def generic_visit(self, node: ast.AST) -> ast.AST:
        if isinstance(node, _UNSUPPORTED):
            raise Unsupported(type(node).__name__)
        return super().generic_visit(node)


def _generate(owner: _Owner) -> tuple[ast.FunctionDef, list[tuple[str, str]], tuple[str, ...]]:
    rewrite = _Rewrite(owner)
    module = owner.kind == "module"
    conditional = any(index is not None for _, _, index, _ in owner.entries)
    body: list[ast.stmt] = [
        ast.If(ast.Compare(_name("format"), [ast.Gt()], [ast.Constant(2)]), [ast.Raise(_name("NotImplementedError"))], []),
    ]
    if owner.strings:                 # PEP 563: the strings the compiler stored, loading nothing; a starred vararg annotation keeps its star
        body.append(ast.Return(ast.Dict([ast.Constant(k) for k, _, _, _ in owner.entries],
                                        [ast.Constant(("*" if starred else "") + ast.unparse(ann)) for _, ann, _, starred in owner.entries])))
        params = ast.arguments([], [ast.arg("format"), ast.arg("_g"), ast.arg("_c")], None, [], [], None, [])
        fn = ast.FunctionDef("__annotate__", params, body, [], None, None, [])
        ast.copy_location(fn, owner.entries[0][1])
        ast.fix_missing_locations(fn)
        return fn, [], ()
    body.append(ast.Assign([ast.Name("_b", ast.Store())], _call("builtins_of", _name("_g"))))
    values: list[tuple[str, ast.expr, int | None]] = []
    for key, ann, index, starred in owner.entries:
        if index is not None:   # the conditional check's load comes before the value's, as in the bytecode
            rewrite.loads.append(("LOAD_GLOBAL" if module else "LOAD_DEREF", "__conditional_annotations__"))
        value = rewrite.visit(copy.deepcopy(ann))
        values.append((key, ast.copy_location(_call("unpack1", value), ann) if starred else value, index))
    if owner.kind == "evaluate":
        body.append(ast.Return(values[0][1]))
    elif owner.kind == "function":
        body.append(ast.Return(ast.Dict([ast.Constant(k) for k, _, _ in values], [v for _, v, _ in values])))
    else:
        body.append(ast.Assign([ast.Name("_d", ast.Store())], ast.Dict([], [])))
        for key, value, index in values:
            store: ast.stmt = ast.Assign([ast.Subscript(_name("_d"), ast.Constant(key), ast.Store())], value)
            if index is not None:
                held = (_call("load_global", _name("_g"), _name("_b"), ast.Constant("__conditional_annotations__")) if module
                        else _call("load_deref", _name("_c"), ast.Constant("__conditional_annotations__")))
                store = ast.If(ast.Compare(ast.Constant(index), [ast.In()], [held]), [store], [])
            body.append(ast.copy_location(store, value))
        body.append(ast.Return(_name("_d")))
    freevars = set(rewrite.free)
    if owner.sees_class:
        freevars.add("__classdict__")
    if conditional and not module:
        freevars.add("__conditional_annotations__")
    params = ast.arguments([], [ast.arg("format"), ast.arg("_g"), ast.arg("_c")], None, [], [], None, [])
    fn = ast.FunctionDef("__annotate__", params, body, [], None, None, [])
    ast.copy_location(fn, owner.entries[0][1])
    ast.fix_missing_locations(fn)
    return fn, rewrite.loads, tuple(sorted(freevars))


def _cpython_loads(code: types.CodeType) -> list[tuple[str, str]]:
    return [(i.opname, str(i.argval)) for i in dis.get_instructions(code) if i.opname in _LOADS]


def _environment(code: types.CodeType, label: str) -> tuple[object, tuple[object, ...] | None]:
    """STRING's substitute globals and cells, or FORWARDREF's second run's, as
    call_annotate_function builds them (no runtime state: every name is a _Stringifier)."""
    fmt = annotationlib.Format
    is_class = "__classdict__" in code.co_freevars
    names = (_StringifierDict({}, format=fmt.STRING) if label == "STRING"
             else _StringifierDict({}, globals={}, owner=None, is_class=is_class, format=fmt.FORWARDREF))
    stand_in = types.FunctionType(code, {}, closure=tuple(types.CellType() for _ in code.co_freevars) or None)
    closure, _ = _build_closure(stand_in, None, is_class, names, allow_evaluation=False)
    return names, closure


def _outcome(call: Callable[[], object]) -> object:
    try:
        result = call()
    except Exception as exc:  # noqa: BLE001  # what the fallback raises is part of its answer
        return ("raises", type(exc).__name__, exc.args)
    return {k: _stringify_single(v) for k, v in result.items()} if isinstance(result, dict) else _stringify_single(result)


def _agree(code: types.CodeType, evaluator: types.CodeType, freevars: tuple[str, ...]) -> str | None:
    """None if the evaluator answers as re-running `code` does, in both environments."""
    fmt = annotationlib.Format
    fn = types.FunctionType(evaluator, {RUNTIME: annotate_rt})
    for label in ("STRING", "FORWARDREF"):
        names, closure = _environment(code, label)
        expected = _outcome(lambda: types.FunctionType(code, names, closure=closure)(fmt.VALUE_WITH_FAKE_GLOBALS))  # type: ignore[arg-type]  # noqa: B023
        names, closure = _environment(code, label)
        cells = dict(zip(freevars, closure or (), strict=True))
        actual = _outcome(lambda: fn(fmt.VALUE_WITH_FAKE_GLOBALS, names, cells))  # noqa: B023
        if expected != actual:
            return f"{label}: CPython {expected!r}, evaluator {actual!r}"
    return None


def _annotate_codes(code: types.CodeType) -> list[types.CodeType]:
    """The compiler-generated `__annotate__` functions, and the PEP 695 evaluate functions (whose
    one parameter is `.format`), of a module's code."""
    found: list[types.CodeType] = []
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            if const.co_name == "__annotate__" or const.co_varnames[:const.co_argcount] == (".format",):
                found.append(const)
            found += _annotate_codes(const)
    return found


def _span(node: ast.AST) -> tuple[object, ...]:
    return (node.lineno, node.end_lineno, node.col_offset, node.end_col_offset)  # type: ignore[attr-defined]


def evaluators_for_source(path: str) -> tuple[dict[str, Evaluator], list[str]]:
    """(the evaluators of the module at `path`, by entry key; what was declined, as
    "key: reason")."""
    with open(path, "rb") as f:
        source = f.read()
    tree = ast.parse(source, path)
    pep563 = any(isinstance(s, ast.ImportFrom) and s.module == "__future__" and any(a.name == "annotations" for a in s.names)
                 for s in tree.body)
    visitor = _Owners(pep563)
    visitor.visit(tree)
    module_entries = _body_entries(tree.body, False, [0], None, module=True)
    if module_entries and not pep563:
        visitor.owners.append(_Owner("module", visitor.scope, False, None, set(), module_entries))
    # every sub-expression's span: an IfExp or an f-string compiles to its parts' positions only (G5 3.5)
    by_span = {_span(sub): owner for owner in visitor.owners for _, ann, _, _ in owner.entries
               for sub in ast.walk(ann) if isinstance(sub, ast.expr)}
    code = compile(source, path, "exec", dont_inherit=True)   # as the import system compiles it
    evaluators: dict[str, Evaluator] = {}
    declined: list[str] = []
    for annotate in _annotate_codes(code):
        key = entry_key(annotate)
        owners = {id(o): o for pos in annotate.co_positions() if (o := by_span.get(pos)) is not None}
        if len(owners) != 1:
            declined.append(f"{key}: matched to {len(owners)} annotation owners")
            continue
        owner = next(iter(owners.values()))
        try:
            fn, loads, freevars = _generate(owner)
        except Unsupported as exc:
            declined.append(f"{key}: {exc} in an annotation")
            continue
        module_code = compile(ast.Module([fn], []), path, "exec", dont_inherit=True)
        evaluator = next(c for c in module_code.co_consts if isinstance(c, types.CodeType))
        if loads != _cpython_loads(annotate):
            problem: str | None = f"loads {loads} differ from CPython's {_cpython_loads(annotate)}"
        elif freevars != annotate.co_freevars:
            problem = f"free variables {freevars} differ from CPython's {annotate.co_freevars}"
        else:
            problem = _agree(annotate, evaluator, freevars)
        if problem:
            declined.append(f"{key}: MISMATCH {problem}")
            continue
        if key in evaluators:     # never file two under one identity: fail closed (A6-1)
            declined.append(f"{key}: MISMATCH two annotate functions share this identity")
            del evaluators[key]
            continue
        evaluators[key] = Evaluator(key, freevars, ast.unparse(fn), evaluator)
    return evaluators, declined
