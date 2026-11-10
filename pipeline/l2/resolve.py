"""resolve-names: CPython's symbol-table rules over L1 (Python/symtable.c, Python/compile.c).

For every scope of an L1 module (the module body, each function, lambda and class body) this
computes what CPython's compiler computes: each name's scope (LOCAL, CELL, FREE,
GLOBAL_EXPLICIT, GLOBAL_IMPLICIT), the implicit `__class__` and `__classdict__` cells of a class
body, and the slot tables of the code object in CPython's order: `co_varnames` (parameters, then
the other locals in the order the code generator first emits a load, store or delete of them;
an annotation alone makes a name local without a slot), `co_cellvars` (sorted, then the implicit
class cells), `co_freevars` (sorted). `NameRef`s are then read off with `Scopes.ref`.

The frontend's synthetic names (decorator values, a match statement's subject, comprehension
helpers, ...) are hidden locals of the scope that binds them, in a module or class body too, so
that they never reach a namespace the program can see (eval1 keeps them apart the same way). A
chained comparison's `_cmp` names are not variables at all: `to-anf` makes them temporaries.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from pipeline.l1 import grammar as L
from pipeline.l2 import grammar as G

LOCAL, CELL, FREE, GLOBAL_EXPLICIT, GLOBAL_IMPLICIT = "LOCAL", "CELL", "FREE", "GLOBAL_EXPLICIT", "GLOBAL_IMPLICIT"
_CLASS_IMPLICIT = ("__class__", "__classdict__", "__conditional_annotations__")


@dataclass(eq=False)
class Scope:
    kind: str                         # module | function | lambda | class
    node: object
    qualname: str
    params: list[str] = field(default_factory=list)
    bound: set[str] = field(default_factory=set)
    globals: set[str] = field(default_factory=set)
    nonlocals: set[str] = field(default_factory=set)
    order: list[str] = field(default_factory=list)       # every name, in order of first appearance
    children: list[Scope] = field(default_factory=list)
    parent: Scope | None = None
    can_see_class: bool = False       # an annotation or type-parameter scope in a class
    module_frame: bool = False        # a comprehension inlined into the module's own code: its free names are LOAD_NAME there
    synthetic: frozenset[str] = frozenset()
    # results
    scopes: dict[str, str] = field(default_factory=dict)
    needs_class_cell: bool = False
    needs_classdict: bool = False
    varnames: tuple[str, ...] = ()
    cellvars: tuple[str, ...] = ()
    freevars: tuple[str, ...] = ()
    # the inlined comprehensions (PEP 709) this scope holds, each with the length of `order` when it was met: CPython's
    # co_varnames has their variables where the comprehension stands
    inlined_at: list[tuple[int, Scope]] = field(default_factory=list)

    @property
    def function_like(self) -> bool:
        return self.kind in ("function", "lambda")

    def see(self, name: str) -> None:
        if name not in self.scopes and name not in self.order:
            self.order.append(name)

    def bind(self, name: str) -> None:
        self.see(name)
        self.bound.add(name)


class _Collector:
    """Builds the scope tree: who binds, declares and uses which name."""

    def __init__(self, synthetic: frozenset[str]) -> None:
        self.synthetic = synthetic
        self.by_node: dict[int, Scope] = {}

    def new(self, kind: str, node: object, qualname: str, parent: Scope | None) -> Scope:
        s = Scope(kind, node, qualname, synthetic=self.synthetic, parent=parent)
        self.by_node[id(node)] = s
        if parent is not None:
            parent.children.append(s)
        return s

    def module(self, m: L.Module) -> Scope:
        s = self.new("module", m, "<module>", None)
        s.globals |= m.globals
        self.block(m.body, s)
        return s

    def function(self, f: L.FunctionDef, parent: Scope, bind: bool = True) -> None:
        for d in f.decorators:
            self.expr(d, parent)
        for p in f.params:
            if p.default is not None:
                self.expr(p.default, parent)
        if f.annotate is not None:
            self.function(f.annotate, parent, bind=False)     # attached to f, bound to no name
        s = self.new("function", f, f.qualname or f.name, parent)
        if f.inlined and parent is not None:
            parent.inlined_at.append((len(parent.order), s))
        s.can_see_class = f.classdict
        s.module_frame = f.module_frame
        s.params += _param_order(f.params)
        for p in f.params:
            s.bind(p.name)
        s.globals |= f.globals
        s.nonlocals |= f.nonlocals
        for n in [*sorted(f.globals), *sorted(f.nonlocals)]:
            s.see(n)
        if f.classdict:
            s.see("__classdict__")
        self.block(f.body, s)
        if bind:
            parent.bind(f.store or f.name)
        for n in f.enclosing_binds:                           # in the comprehension's order: CPython's co_varnames
            if f.binds_through and parent.parent is not None:   # an annotation scope between: the function around it binds, it sees
                parent.parent.bind(n)
                parent.see(n)
            else:
                parent.bind(n)

    def lambda_(self, e: L.Lambda, parent: Scope) -> None:
        for p in e.params:
            if p.default is not None:
                self.expr(p.default, parent)
        s = self.new("lambda", e, e.qualname, parent)
        s.params += _param_order(e.params)
        for p in e.params:
            s.bind(p.name)
        self.block(e.prelude, s)
        self.expr(e.body, s)

    def class_body(self, e: L.ClassBody, parent: Scope) -> None:
        s = self.new("class", e, e.qualname, parent)
        s.globals |= e.globals
        s.nonlocals |= e.nonlocals
        s.needs_class_cell = e.classcell
        s.needs_classdict = e.classdict
        self.block(e.body, s)

    # ---- statements ----------------------------------------------------------------------------

    def block(self, body: tuple[L.Stmt, ...], s: Scope) -> None:
        for st in body:
            self.stmt(st, s)

    def stmt(self, st: L.Stmt, s: Scope) -> None:
        match st:
            case L.FunctionDef():
                self.function(st, s)
            case L.Assign(target=target, value=value):
                self.expr(value, s)
                self.target(target, s)
            case L.AugAssign(target=target, value=value):
                if isinstance(target, L.NameTarget):
                    s.see(target.id)          # loaded before the value is evaluated
                else:
                    self.target_parts(target, s)
                self.expr(value, s)
                self.target(target, s)
            case L.ExprStmt(value=value):
                if (isinstance(value, L.Call) and isinstance(value.func, L.Intrinsic)
                        and value.func.name == "setup_annotations"):
                    s.bind("__annotations__")
                self.expr(value, s)
            case L.Return(value=value):
                if value is not None:
                    self.expr(value, s)
            case L.If(test=test, body=body, orelse=orelse) | L.While(test=test, body=body, orelse=orelse):
                self.expr(test, s)
                self.block(body, s)
                self.block(orelse, s)
            case L.For(target=target, iterable=iterable, body=body, orelse=orelse):
                self.expr(iterable, s)
                self.target(target, s)
                self.block(body, s)
                self.block(orelse, s)
            case L.Declare(names=names):
                # `x: T` makes x local, but the code generator emits nothing for it: the slot is
                # taken at the first load, store or delete (an annotated-only local has none)
                s.bound.update(names)
            case L.Raise(exc=exc, cause=cause):
                if exc is not None:
                    self.expr(exc, s)
                if cause is not None:
                    self.expr(cause, s)
            case L.Try(body=body, handlers=handlers, orelse=orelse, finalbody=finalbody):
                # codegen's order, which decides first appearance: the body, the else block, the
                # handlers, the finally block (compiler_try_except, compiler_try_finally)
                self.block(body, s)
                self.block(orelse, s)
                for h in handlers:
                    if h.type is not None:
                        self.expr(h.type, s)
                    if h.name is not None:
                        s.bind(h.name)
                    self.block(h.body, s)
                self.block(finalbody, s)
            case L.Delete(targets=targets):
                for t in targets:
                    self.target(t, s)
            case L.Assert(test=test, msg=msg):
                self.expr(test, s)
                if msg is not None:
                    self.expr(msg, s)
            case L.Break() | L.Continue() | L.Pass():
                pass
            case _:
                raise TypeError(f"resolve-names: unknown L1 statement {type(st).__name__}")

    def target_parts(self, t: L.Target, s: Scope) -> None:
        if isinstance(t, L.AttrTarget):
            self.expr(t.obj, s)
        elif isinstance(t, L.ItemTarget):
            self.expr(t.obj, s)
            self.expr(t.key, s)

    def target(self, t: L.Target, s: Scope) -> None:
        match t:
            case L.NameTarget(id=name):
                s.bind(name)
            case L.AttrTarget() | L.ItemTarget():
                self.target_parts(t, s)
            case L.StarTarget(target=inner):
                self.target(inner, s)
            case L.TupleTarget(elts=elts):
                for e in elts:
                    self.target(e, s)

    # ---- expressions -------------------------------------------------------------------------

    def expr(self, e: L.Expr, s: Scope) -> None:
        match e:
            case L.Name(id=name):
                if name != "__bind__" and not expression_temporary(name, s.synthetic):
                    s.see(name)
                if name == "super" and s.function_like:
                    s.see("__class__")         # symtable: a function loading `super` uses __class__
                return
            case L.Lambda():
                self.lambda_(e, s)
                return
            case L.ClassBody():
                self.class_body(e, s)
                return
            case L.Intrinsic(name="classcell") if s.kind != "class":
                s.see("__class__")            # a method's __class__ cell
                return
            case L.Call(func=L.Name(id="__bind__"), args=(L.Const(value=str() as name), value)):
                self.expr(value, s)
                if not expression_temporary(name, s.synthetic):
                    s.bind(name)               # a walrus the program wrote is a real binding
                return
        for child in _children(e):
            self.expr(child, s)


def expression_temporary(name: str, synthetic: frozenset[str]) -> bool:
    """A chained comparison's middle operand (`_cmp*`): a stack value in CPython, a temporary
    in L2, never a variable (review 2026-11-02, A8-4)."""
    return name in synthetic and name.startswith("_cmp")


def moved_on_use(name: str, synthetic: frozenset[str]) -> bool:
    """A decorator's value (`_dec*`), evaluated before the definition and loaded exactly once,
    where it is applied: the load moves it into a temporary, so it dies after its call as the
    stack value does in CPython (review 2026-11-02, G7 2.3)."""
    return name in synthetic and name.startswith("_dec")


def _param_order(params: tuple[L.Param, ...]) -> list[str]:
    """co_varnames' order: positional parameters, keyword-only ones, then *args and **kwargs."""
    rank = {"positional-only": 0, "positional-or-keyword": 0, "keyword-only": 1, "*args": 2, "**kwargs": 3}
    return [p.name for p in sorted(params, key=lambda p: rank[p.kind])]


def _children(e: L.Expr) -> list[L.Expr]:
    out: list[L.Expr] = []
    for name in e.__dataclass_fields__:
        v = getattr(e, name)
        if isinstance(v, L.Expr):
            out.append(v)
        elif isinstance(v, tuple):
            for x in v:
                if isinstance(x, L.Expr):
                    out.append(x)
                elif isinstance(x, tuple) and len(x) == 2 and isinstance(x[1], L.Expr):
                    out.append(x[1])
    return out


# ---- analysis (symtable.c analyze_block, analyze_name, update_symbols) ------------------------

def _analyze(s: Scope, bound: set[str] | None, class_entry: Scope | None) -> set[str]:
    """Decides every name of `s` and its children; returns the names free in `s`."""
    local: set[str] = set()
    free: set[str] = set()
    # every name the scope uses, then the ones it only declares (`x: T` alone): those are
    # classified too, since a nested function may capture them, but get no slot
    names = list(s.order) + sorted(n for n in s.bound if n not in s.order)
    for name in names:
        if name in s.synthetic and name in s.bound:
            s.scopes[name] = LOCAL         # a hidden local, in any kind of scope
            local.add(name)
        elif name in s.globals:
            s.scopes[name] = GLOBAL_EXPLICIT
        elif name in s.nonlocals:
            if bound is None or name not in bound:
                raise SyntaxError(f"no binding for nonlocal '{name}' found")
            s.scopes[name] = FREE
            free.add(name)
        elif name in s.bound:
            s.scopes[name] = LOCAL
            local.add(name)
        elif class_entry is not None and name in class_entry.globals:
            s.scopes[name] = GLOBAL_EXPLICIT
        elif (class_entry is not None and name in class_entry.bound and name not in class_entry.nonlocals
              and name != "__classdict__"):
            s.scopes[name] = GLOBAL_IMPLICIT     # the class namespace or the globals, never the enclosing function
        elif bound is not None and name in bound:
            s.scopes[name] = FREE
            free.add(name)
        else:
            s.scopes[name] = GLOBAL_IMPLICIT
    # what the children see
    newbound: set[str] = set()
    if s.kind == "class":
        if bound is not None:
            newbound |= bound
        newbound |= set(_CLASS_IMPLICIT)
    else:
        if s.function_like:
            newbound |= local
        elif s.kind == "module":
            newbound |= {n for n in local if n in s.synthetic}
        if bound is not None:
            newbound |= bound
    # analyze_name discards a name declared global from the bound set: an enclosing function's
    # binding of it is invisible below this scope (review 2026-11-02, A8-6)
    newbound -= {n for n, sc in s.scopes.items() if sc == GLOBAL_EXPLICIT}
    allfree: set[str] = set()
    for child in s.children:
        entry = s if (child.can_see_class and s.kind == "class") else None
        allfree |= _analyze(child, set(newbound), entry)
    if s.kind == "class":
        for implicit, flag in (("__class__", "needs_class_cell"), ("__classdict__", "needs_classdict")):
            if implicit in allfree:
                setattr(s, flag, True)
                allfree.discard(implicit)
        allfree.discard("__conditional_annotations__")
    # update_symbols: a local some child captures is a cell; a name free in a child and bound
    # further out is free here too; in a class, a name it also uses itself is a free variable of
    # the class code as well (DEF_FREE_CLASS)
    class_free: set[str] = set()
    for name in sorted(allfree):
        sc = s.scopes.get(name)
        if sc == LOCAL and (s.function_like or name in s.synthetic):
            s.scopes[name] = CELL
            allfree.discard(name)
        elif sc is not None:
            if s.kind == "class" and sc != FREE:
                class_free.add(name)
        elif bound is not None and name in bound:
            s.scopes[name] = FREE
            s.order.append(name)
        else:
            allfree.discard(name)          # global for the child: nothing to pass up
    _slots(s, class_free)
    return free | allfree


def co_varnames(s: Scope) -> tuple[str, ...]:
    """CPython's co_varnames: the parameters, then the other locals in order of first appearance, an inlined
    comprehension's variables (PEP 709) where the comprehension stands; the compiler's own names left out. A name an
    inlined comprehension assigns outward (`:=`) is a fast local of this code unless a nested function captures it
    (`comprehension_fast`)."""
    out: list[str] = [n for n in s.params if n not in s.synthetic]
    seen = set(out)
    fast = comprehension_fast(s)
    inlined = sorted(s.inlined_at, key=lambda pair: pair[0])
    at = 0

    def add(names: tuple[str, ...]) -> None:
        for n in names:
            if n not in seen:
                seen.add(n)
                out.append(n)

    for i, n in enumerate(s.order):
        while at < len(inlined) and inlined[at][0] <= i:
            add(_inlined_varnames(inlined[at][1]))
            at += 1
        if n in s.synthetic:
            continue
        if (s.scopes.get(n) == LOCAL and (s.function_like or n in s.params)) or (n in fast and s.function_like):
            add((n,))
    while at < len(inlined):
        add(_inlined_varnames(inlined[at][1]))
        at += 1
    return tuple(out)


def comprehension_fast(s: Scope) -> set[str]:
    """The names this scope holds as cells only because an inlined comprehension assigns them (`nonlocal` in the hoisted
    function): CPython stores them as fast locals, as no closure sees them. A nested function capturing one, through the
    comprehension or beside it, makes it a cell for both."""
    def free_below(scope: Scope, name: str) -> bool:
        for child in scope.children:
            if _is_inlined(scope, child):
                if free_below(child, name):
                    return True
            elif child.scopes.get(name) == FREE:
                return True
        return False

    return {n for n, kind in s.scopes.items()
            if kind == CELL and n not in s.params and n not in s.synthetic and not free_below(s, n)}


def _is_inlined(parent: Scope, child: Scope) -> bool:
    return any(c is child for _, c in parent.inlined_at)


def _inlined_varnames(s: Scope) -> tuple[str, ...]:
    """An inlined comprehension's variables as the enclosing code lists them: the names it isolates on entry, which are
    its locals and its cells (a cell of an inlined comprehension is a fast local of the enclosing code too), in order of
    first appearance, then those of its own inlined comprehensions, as the symbol table merged them after its own. A
    name it assigns outward is the enclosing code's, listed where that code binds it."""
    out: list[str] = []
    seen: set[str] = set()
    for n in s.order:
        if s.scopes.get(n) in (LOCAL, CELL) and n not in s.synthetic and n not in seen:
            seen.add(n)
            out.append(n)
    for _, child in sorted(s.inlined_at, key=lambda pair: pair[0]):
        for m in _inlined_varnames(child):
            if m not in seen:
                seen.add(m)
                out.append(m)
    return tuple(out)


def _inlined_cells(s: Scope) -> set[str]:
    cells = {n for n in s.cellvars if n not in s.synthetic}
    for _, child in s.inlined_at:
        cells |= _inlined_cells(child)
    return cells


def co_cellvars(s: Scope) -> tuple[str, ...]:
    """CPython's co_cellvars: the cells that are fast locals too (parameters, an inlined comprehension's variables that a
    closure captures) in co_varnames' order, then the other cells sorted; a name an inlined comprehension only assigns
    outward is no cell (`comprehension_fast`); the compiler's own names left out."""
    varnames = co_varnames(s)
    cells = {n for n in s.cellvars if n not in s.synthetic} - comprehension_fast(s)
    for _, child in s.inlined_at:
        cells |= _inlined_cells(child)
    return tuple(n for n in varnames if n in cells) + tuple(sorted(cells - set(varnames)))


def _slots(s: Scope, class_free: set[str]) -> None:
    params = list(s.params)
    locals_ = [n for n in s.order if s.scopes.get(n) == LOCAL and n not in params]
    if s.function_like or s.kind in ("module", "class"):
        if not s.function_like:
            locals_ = [n for n in locals_ if n in s.synthetic]
        s.varnames = tuple(params + locals_)
    # parameters that are cells first, in parameter order, then the other cells sorted
    # (co_cellvars lists the localsplus entries marked CO_FAST_CELL)
    cells = [n for n in params if s.scopes.get(n) == CELL]
    cells += sorted(n for n, sc in s.scopes.items() if sc == CELL and n not in params)
    if s.kind == "class":
        if s.needs_class_cell:
            cells.append("__class__")
        if s.needs_classdict:
            cells.append("__classdict__")
    s.cellvars = tuple(cells)
    s.freevars = tuple(sorted({n for n in s.order if s.scopes.get(n) == FREE} | class_free))


@dataclass
class Scopes:
    """The resolution of one module: the scope of each L1 scope node."""
    root: Scope
    by_node: dict[int, Scope]

    def of(self, node: object) -> Scope:
        return self.by_node[id(node)]

    def ref(self, s: Scope, name: str, ctx: str = "load") -> G.NameRef:
        """The NameRef CPython's compiler_nameop would emit for `name` in scope `s`."""
        sc = s.scopes.get(name)
        if sc is None:
            raise KeyError(f"resolve-names: {name!r} was never seen in {s.qualname}")
        if sc == LOCAL:
            if s.function_like or name in s.synthetic:
                return G.NameRef("local", name)
            return G.NameRef("name", name)
        if sc == CELL:
            return G.NameRef("cell", name)
        if sc == FREE:
            if ctx == "load" and s.kind == "class":
                return G.NameRef("classdict", name, then="free", mapping="locals")
            if ctx == "load" and s.can_see_class:
                return G.NameRef("classdict", name, then="free", mapping="__classdict__")
            return G.NameRef("free", name)
        if sc == GLOBAL_EXPLICIT:
            if ctx == "load" and s.can_see_class:
                return G.NameRef("classdict", name, then="global", mapping="__classdict__")
            return G.NameRef("global", name)
        # GLOBAL_IMPLICIT
        if s.function_like:
            if ctx == "load" and s.can_see_class:
                return G.NameRef("classdict", name, then="global", mapping="__classdict__")
            if ctx == "load" and s.module_frame:      # inlined into module code, where an implicit global is OP_NAME (review F17 #2)
                return G.NameRef("name", name, mapping="module")
            return G.NameRef("global", name)
        return G.NameRef("name", name)


def resolve(m: L.Module) -> Scopes:
    c = _Collector(m.synthetic)
    root = c.module(m)
    _analyze(root, None, None)
    return Scopes(root, c.by_node)
