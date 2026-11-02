"""to-anf: L1 to L2 (docs/l2.md sections 4 and 7), with resolve-names' decisions.

Every L1 expression becomes a sequence of `Let`s in Python's evaluation order, each one named
operation; every name access becomes the instruction CPython's compiler would emit for it. The
construction orders that CPython's code generator fixes, and that eval1 already follows, are kept
step for step: a call's arguments (codegen_call_helper_impl: a lone `*x` made a tuple only at the
call, runs of keywords built into a dict and merged), displays (starunpack_helper: built at the
first starred item, or empty above 30 items) and dict displays (runs of pairs as sub-dicts, a run
above 15 pairs built pair by pair).

The output has no `Release`s yet (that is the `lifetimes` pass): it satisfies `wf2` with
`lifetimes=False`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from pipeline.l1 import grammar as L
from pipeline.l2 import grammar as G
from pipeline.l2.resolve import Scope, Scopes, resolve
from pipeline.passes.spec import Discharge, Fact, Level, Obligation, PassSpec, register

STACK_USE_GUIDELINE = 30        # _PY_STACK_USE_GUIDELINE (Include/internal/pycore_compile.h)

# intrinsics that eval1 serves with the running frame's context; the rest are plain values
FRAME_INTRINSICS = ("type_params", "generic_class", "typealias", "setup_annotations", "import_name", "import_star")


@dataclass
class _Block:
    stmts: list[G.Stmt] = field(default_factory=list)


class _Code:
    """Lowers one scope (module, function, lambda or class body) to one code object."""

    def __init__(self, scopes: Scopes, scope: Scope) -> None:
        self.scopes = scopes
        self.scope = scope
        self.n = 0
        self.blocks: list[_Block] = [_Block()]
        self.line = 0

    # ---- emission ------------------------------------------------------------------------------

    @property
    def out(self) -> list[G.Stmt]:
        return self.blocks[-1].stmts

    def emit(self, s: G.Stmt) -> None:
        self.out.append(s)

    def temp(self) -> G.Temp:
        self.n += 1
        return G.Temp(self.n)

    def let(self, op: G.Op) -> G.Temp:
        t = self.temp()
        self.emit(G.Let(t, op))
        return t

    def sub(self, stmts: tuple[L.Stmt, ...]) -> tuple[G.Stmt, ...]:
        self.blocks.append(_Block())
        self.block(stmts)
        return tuple(self.blocks.pop().stmts)

    def capture(self) -> None:
        self.blocks.append(_Block())

    def captured(self) -> tuple[G.Stmt, ...]:
        return tuple(self.blocks.pop().stmts)

    def at(self, line: int) -> None:
        if line and line != self.line:
            self.line = line
            self.emit(G.Line(line))

    def ref(self, name: str, ctx: str = "load") -> G.NameRef:
        return self.scopes.ref(self.scope, name, ctx)

    def into(self, a: G.Atom, t: G.Temp) -> None:
        """Make `t` hold `a`: rename the Let that just produced it, or copy."""
        last = self.out[-1] if self.out else None
        if isinstance(a, G.Temp) and isinstance(last, G.Let) and last.t == a:
            self.out[-1] = G.Let(t, last.op)
        else:
            self.emit(G.Let(t, G.Copy(a)))

    # ---- code objects --------------------------------------------------------------------------

    def build(self, node: L.Module | L.FunctionDef | L.Lambda | L.ClassBody) -> G.Code:
        s = self.scope
        params: tuple[G.Param, ...] = ()
        doc: str | None = None
        kind = "module"
        if isinstance(node, L.Module):
            self.block(node.body)
            name = "<module>"
        elif isinstance(node, L.ClassBody):
            kind = "classbody"
            if s.needs_classdict:
                # LOAD_LOCALS; STORE_DEREF __classdict__, before anything else the body does
                self.emit(G.Store(G.NameRef("cell", "__classdict__"), self.let(G.Locals())))
            self.block(node.body)
            name = node.qualname.rsplit(".", 1)[-1]
        elif isinstance(node, L.Lambda):
            kind = "generator" if node.kind == "generator" else "lambda"
            params = tuple(G.Param(p.name, p.kind, p.public) for p in node.params)
            self.block(node.prelude)
            self.at(node.line)
            value = self.expr(node.body)
            self.emit(G.Return(value))
            name = "<lambda>"
        else:
            kind = node.kind
            params = tuple(G.Param(p.name, p.kind, p.public) for p in node.params)
            doc = node.docstring
            self.block(node.body)
            if _falls_through(self.out):
                self.emit(G.Return(G.Const(None)))
            name = node.name
        return G.Code(
            name=name, qualname=s.qualname, kind=kind, params=params,
            varnames=s.varnames, cellvars=s.cellvars, freevars=s.freevars,
            body=tuple(self.out), first_line=getattr(node, "line", 0), docstring=doc,
            classcell=isinstance(node, L.ClassBody) and s.needs_class_cell,
            annotation=isinstance(node, L.FunctionDef) and node.annotation,
            classdict=isinstance(node, L.FunctionDef) and node.classdict,
            meta=(("hidden", frozenset(n for n in s.varnames if n in s.synthetic)),
                  ("needs_classdict", s.needs_classdict)))

    def child(self, node: L.FunctionDef | L.Lambda | L.ClassBody) -> G.Code:
        return _Code(self.scopes, self.scopes.of(node)).build(node)

    def make_function(self, node: L.FunctionDef | L.Lambda | L.ClassBody) -> G.Temp:
        """MAKE_FUNCTION: defaults in parameter order (positional, then keyword-only), then the
        annotate function, then the function with its closure."""
        defaults: G.Atom | None = None
        kwdefaults: G.Atom | None = None
        annotate: G.Atom | None = None
        if not isinstance(node, L.ClassBody):
            pos = [p for p in node.params if p.default is not None and p.kind in ("positional-only", "positional-or-keyword")]
            kwo = [p for p in node.params if p.default is not None and p.kind == "keyword-only"]
            if pos:
                defaults = self.let(G.BuildTuple(tuple(self.expr(p.default) for p in pos if p.default is not None)))
            if kwo:
                values = [self.expr(p.default) for p in kwo if p.default is not None]
                kwdefaults = self.let(G.BuildMap(tuple(G.Const(p.name) for p in kwo), tuple(values)))
            if isinstance(node, L.FunctionDef) and node.annotate is not None:
                annotate = self.make_function(node.annotate)
        code = self.child(node)
        closure = tuple(self.let(G.CellOf(self.cell_ref(n))) for n in code.freevars)
        return self.let(G.MakeFunction(code, defaults, kwdefaults, closure, annotate))

    def cell_ref(self, name: str) -> G.NameRef:
        """The cell this scope holds for `name`, to pass to a closure (LOAD_CLOSURE)."""
        if name in self.scope.cellvars:
            return G.NameRef("cell", name)
        if name in self.scope.freevars:
            return G.NameRef("free", name)
        raise KeyError(f"to-anf: {self.scope.qualname} has no cell for {name!r} to pass on")

    # ---- statements ----------------------------------------------------------------------------

    def block(self, stmts: tuple[L.Stmt, ...]) -> None:
        for st in stmts:
            self.stmt(st)

    def stmt(self, st: L.Stmt) -> None:
        self.at(st.line)
        match st:
            case L.ExprStmt(value=value):
                a = self.expr(value)
                last = self.out[-1] if self.out else None
                if isinstance(a, G.Temp) and isinstance(last, G.Let) and last.t == a:
                    self.out[-1] = G.Do(last.op)              # POP_TOP at once
            case L.Assign(target=target, value=value):
                self.assign(target, self.expr(value))
            case L.AugAssign(target=target, op=op, value=value):
                self.aug_assign(target, op, value)
            case L.Return(value=value):
                self.emit(G.Return(self.expr(value) if value is not None else G.Const(None)))
            case L.If(test=test, body=body, orelse=orelse):
                t = self.test(test)
                self.emit(G.If(t, self.sub(body), self.sub(orelse)))
            case L.While(test=test, body=body, orelse=orelse):
                self.capture()
                t = self.test(test)
                self.emit(G.If(t, self.sub(body), (G.EndLoop(),)))
                loop_body = self.captured()
                self.emit(G.Loop(loop_body, (), self.sub(orelse)))
            case L.For(target=target, iterable=iterable, body=body, orelse=orelse, iterator=iterator):
                source = self.expr(iterable)
                it = source if iterator and isinstance(source, G.Temp) else self.let(G.Iter(source))
                self.capture()
                v = self.let(G.ForNext(it))
                self.capture()
                self.assign(target, v)
                self.block(body)
                step = self.captured()
                self.emit(G.IfEnd(v, (G.EndLoop(),), step))
                loop_body = self.captured()
                self.emit(G.Loop(loop_body, (it,), self.sub(orelse)))
            case L.Break():
                self.emit(G.Break())
            case L.Continue():
                self.emit(G.Continue())
            case L.Pass() | L.Declare():
                pass
            case L.FunctionDef():
                decorators = [self.expr(d) for d in st.decorators]   # top first, applied bottom-up
                fn: G.Atom = self.make_function(st)
                for d in reversed(decorators):
                    fn = self.let(G.Call(d, (fn,)))
                self.emit(G.Store(self.ref(st.store or st.name, "store"), fn))
            case L.Raise(exc=exc, cause=cause):
                e = self.expr(exc) if exc is not None else None
                c = self.expr(cause) if cause is not None else None
                self.emit(G.Raise(e, c, cause is not None))
            case L.Try(body=body, handlers=handlers, orelse=orelse, finalbody=finalbody):
                lowered = []
                for h in handlers:
                    self.capture()
                    ty = self.expr(h.type) if h.type is not None else None
                    if ty is not None and not isinstance(ty, G.Temp):
                        ty = self.let(G.Copy(ty))
                    match_ = self.captured()
                    name = self.ref(h.name, "store") if h.name is not None else None
                    lowered.append(G.Handler(match_, ty if isinstance(ty, G.Temp) else None, name, self.sub(h.body)))
                self.emit(G.Try(self.sub(body), tuple(lowered), self.sub(orelse), self.sub(finalbody)))
            case L.Delete(targets=targets):
                for tgt in targets:
                    self.delete(tgt)
            case L.Assert(test=test, msg=msg):
                t = self.test(test)
                self.capture()
                cls = self.let(G.Builtin("AssertionError"))       # LOAD_ASSERTION_ERROR
                err = self.let(G.Call(cls, (self.expr(msg),))) if msg is not None else cls
                self.emit(G.Raise(err))
                self.emit(G.If(t, (), self.captured()))
            case _:
                raise TypeError(f"to-anf: unknown L1 statement {type(st).__name__}")

    def test(self, e: L.Expr) -> G.Temp:
        a = self.expr(e)
        return a if isinstance(a, G.Temp) else self.let(G.Truth(a))

    def assign(self, t: L.Target, v: G.Atom) -> None:
        match t:
            case L.NameTarget(id=name):
                self.emit(G.Store(self.ref(name, "store"), v))
            case L.AttrTarget(obj=obj, name=name):
                self.emit(G.Do(G.SetAttr(self.expr(obj), name, v)))
            case L.ItemTarget(obj=obj, key=key):
                o = self.expr(obj)
                self.emit(G.Do(G.SetItem(o, self.expr(key), v)))
            case L.TupleTarget(elts=elts):
                star = next((i for i, x in enumerate(elts) if isinstance(x, L.StarTarget)), -1)
                temps = tuple(self.temp() for _ in elts)
                self.emit(G.Unpack(temps, v, star))
                for sub_t, value in zip(elts, temps, strict=True):
                    self.assign(sub_t.target if isinstance(sub_t, L.StarTarget) else sub_t, value)
            case _:
                raise TypeError(f"to-anf: illegal target {t}")

    def aug_assign(self, t: L.Target, op: str, value: L.Expr) -> None:
        match t:
            case L.NameTarget(id=name):
                cur = self.let(G.Load(self.ref(name)))                 # loaded before the value
                result = self.let(G.InPlace(op, cur, self.expr(value)))
                self.emit(G.Store(self.ref(name, "store"), result))
            case L.AttrTarget(obj=obj, name=name):
                o = self.expr(obj)
                cur = self.let(G.GetAttr(o, name))
                result = self.let(G.InPlace(op, cur, self.expr(value)))
                self.emit(G.Do(G.SetAttr(o, name, result)))
            case L.ItemTarget(obj=obj, key=key):
                o = self.expr(obj)
                k = self.expr(key)
                cur = self.let(G.GetItem(o, k))
                result = self.let(G.InPlace(op, cur, self.expr(value)))
                self.emit(G.Do(G.SetItem(o, k, result)))
            case _:
                raise TypeError("to-anf: illegal augmented assignment target")

    def delete(self, t: L.Target) -> None:
        match t:
            case L.NameTarget(id=name):
                self.emit(G.Delete(self.ref(name, "del")))
            case L.AttrTarget(obj=obj, name=name):
                self.emit(G.Do(G.DelAttr(self.expr(obj), name)))
            case L.ItemTarget(obj=obj, key=key):
                o = self.expr(obj)
                self.emit(G.Do(G.DelItem(o, self.expr(key))))
            case L.TupleTarget(elts=elts):
                for e in elts:
                    self.delete(e)
            case _:
                raise TypeError("to-anf: illegal delete target")

    # ---- expressions ---------------------------------------------------------------------------

    def expr(self, e: L.Expr) -> G.Atom:
        match e:
            case L.Const(value=value):
                return G.Const(value)
            case L.Name(id=name):
                return self.let(G.Load(self.ref(name)))
            case L.Intrinsic(name=name):
                return self.intrinsic(name)
            case L.BinOp(op=op, left=left, right=right):
                a = self.expr(left)
                return self.let(G.Binary(op, a, self.expr(right)))
            case L.UnaryOp(op=op, operand=operand):
                return self.let(G.Unary(op, self.expr(operand)))
            case L.Truth(operand=operand):
                return self.let(G.Truth(self.expr(operand)))
            case L.Not(operand=operand):
                return self.let(G.Not(self.expr(operand)))
            case L.Compare(op=op, left=left, right=right):
                a = self.expr(left)
                return self.let(G.Compare(op, a, self.expr(right)))
            case L.BoolOp(op=op, left=left, right=right):
                # COPY; TO_BOOL; POP_JUMP: the left operand decides, and is the value when it does
                result = self.temp()
                a = self.expr(left)
                t = self.let(G.Truth(a))
                self.capture()
                self.into(self.expr(right), result)
                evaluate_right = self.captured()
                keep_left = (G.Let(result, G.Copy(a)),)
                self.emit(G.If(t, evaluate_right, keep_left) if op == "and" else G.If(t, keep_left, evaluate_right))
                return result
            case L.IfExp(test=test, body=body, orelse=orelse):
                result = self.temp()
                t = self.test(test)
                self.capture()
                self.into(self.expr(body), result)
                then = self.captured()
                self.capture()
                self.into(self.expr(orelse), result)
                self.emit(G.If(t, then, self.captured()))
                return result
            case L.Call():
                return self.call(e)
            case L.Lambda():
                return self.make_function(e)
            case L.ClassBody():
                return self.make_function(e)
            case L.Yield(value=value):
                return self.let(G.Yield(self.expr(value) if value is not None else G.Const(None)))
            case L.YieldFrom(value=value):
                return self.let(G.YieldFrom(self.expr(value)))
            case L.GetAttr(obj=obj, name=name):
                return self.let(G.GetAttr(self.expr(obj), name))
            case L.GetItem(obj=obj, key=key):
                o = self.expr(obj)
                return self.let(G.GetItem(o, self.expr(key)))
            case L.ListLit() | L.TupleLit() | L.SetLit():
                return self.display(e)
            case L.DictLit():
                return self.dict_display(e)
            case L.Starred():
                raise TypeError("to-anf: a starred expression outside a call or display")
        raise TypeError(f"to-anf: unknown L1 expression {type(e).__name__}")

    def intrinsic(self, name: str) -> G.Temp:
        if name == "classcell":
            return self.let(G.CellOf(G.NameRef("cell" if self.scope.kind == "class" else "free", "__class__")))
        if name == "classdictcell":
            return self.let(G.CellOf(G.NameRef("cell", "__classdict__")))
        return self.let(G.Builtin(name))

    def call(self, e: L.Call) -> G.Atom:
        if isinstance(e.func, L.Name) and e.func.id == "__bind__":
            name = e.args[0]
            assert isinstance(name, L.Const) and isinstance(name.value, str)
            v = self.expr(e.args[1])
            stored = self.let(G.Copy(v))                    # COPY; STORE: the value stays the result
            self.emit(G.Store(self.ref(name.value, "store"), stored))
            return v
        simple = not any(isinstance(a, L.Starred) for a in e.args) and all(k is not None for k, _ in e.kwargs)
        if isinstance(e.func, L.Intrinsic) and simple and e.func.name not in ("classcell", "classdictcell"):
            args = tuple(self.expr(a) for a in e.args)
            kw = tuple((k, self.expr(v)) for k, v in e.kwargs if k is not None)
            return self.let(G.Runtime(e.func.name, args, kw))
        fn = self.expr(e.func)
        if simple:
            args = tuple(self.expr(a) for a in e.args)
            kw = tuple((k, self.expr(v)) for k, v in e.kwargs if k is not None)
            return self.let(G.Call(fn, args, kw))
        # CALL_FUNCTION_EX (codegen_call_helper_impl)
        lone = len(e.args) == 1 and isinstance(e.args[0], L.Starred)
        positional: G.Atom
        star: G.Atom | None = None
        if lone:
            starred = e.args[0]
            assert isinstance(starred, L.Starred)
            star = self.expr(starred.value)          # made a tuple only at the call
            positional = star
        else:
            positional = self.display_items(e.args, "tuple")
        kwargs: G.Temp | None = None
        run: list[tuple[str, L.Expr]] = []

        def flush() -> None:
            nonlocal kwargs
            if not run:
                return
            values = tuple(self.expr(v) for _, v in run)          # BUILD_MAP: every value first
            sub = self.let(G.BuildMap(tuple(G.Const(k) for k, _ in run), values))
            run.clear()
            if kwargs is None:
                kwargs = sub
            else:
                self.emit(G.Do(G.DictMerge(kwargs, sub, fn)))
        for kw_name, kw_value in e.kwargs:
            if kw_name is not None:
                run.append((kw_name, kw_value))
                continue
            flush()
            if kwargs is None:
                kwargs = self.let(G.BuildMap((), ()))
            self.emit(G.Do(G.DictMerge(kwargs, self.expr(kw_value), fn)))
        flush()
        if star is not None:
            positional = self.let(G.Runtime("call_args_tuple", (star,)))   # _MAKE_CALLARGS_A_TUPLE
        return self.let(G.CallEx(fn, positional, kwargs))

    def display(self, e: L.ListLit | L.TupleLit | L.SetLit) -> G.Temp:
        kind = "set" if isinstance(e, L.SetLit) else "tuple" if isinstance(e, L.TupleLit) else "list"
        return self.display_items(e.items, kind)

    def display_items(self, items: tuple[L.Expr, ...], kind: str) -> G.Temp:
        """starunpack_helper: with no starred item and at most 30 items, every item is evaluated
        before the container is built; otherwise it is built at the first starred item (or empty,
        when big) and each later item is added as it is evaluated; a tuple is made from the list."""
        big = len(items) > STACK_USE_GUIDELINE
        if not big and not any(isinstance(x, L.Starred) for x in items):
            values = tuple(self.expr(x) for x in items)
            op = G.BuildSet(values) if kind == "set" else G.BuildTuple(values) if kind == "tuple" else G.BuildList(values)
            return self.let(op)
        pending: list[G.Atom] = []
        built: G.Temp | None = (self.let(G.BuildSet(()) if kind == "set" else G.BuildList(()))) if big else None
        for x in items:
            if isinstance(x, L.Starred):
                if built is None:
                    built = self.let(G.BuildSet(tuple(pending)) if kind == "set" else G.BuildList(tuple(pending)))
                value = self.expr(x.value)
                self.emit(G.Do(G.SetUpdate(built, value) if kind == "set" else G.ListExtend(built, value)))
            else:
                value = self.expr(x)
                if built is None:
                    pending.append(value)
                else:
                    self.emit(G.Do(G.SetAdd(built, value) if kind == "set" else G.ListAppend(built, value)))
        assert built is not None
        return self.let(G.ListToTuple(built)) if kind == "tuple" else built

    def dict_display(self, e: L.DictLit) -> G.Temp:
        """codegen_dict: runs of pairs become sub-dicts (evaluated, then built), a run longer than
        15 pairs is built pair by pair (MAP_ADD); `**m` is merged with DICT_UPDATE."""
        result: G.Temp | None = None
        run: list[tuple[L.Expr, L.Expr]] = []

        def flush() -> None:
            nonlocal result
            if not run:
                return
            if len(run) * 2 > STACK_USE_GUIDELINE:
                sub = self.let(G.BuildMap((), ()))
                for k, v in run:
                    key = self.expr(k)
                    self.emit(G.Do(G.MapAdd(sub, key, self.expr(v))))
            else:
                keys: list[G.Atom] = []
                values: list[G.Atom] = []
                for k, v in run:
                    keys.append(self.expr(k))
                    values.append(self.expr(v))
                sub = self.let(G.BuildMap(tuple(keys), tuple(values)))
            run.clear()
            if result is None:
                result = sub
            else:
                self.emit(G.Do(G.DictUpdate(result, sub)))

        for k, v in zip(e.keys, e.values, strict=True):
            if k is None:
                flush()
                if result is None:
                    result = self.let(G.BuildMap((), ()))
                self.emit(G.Do(G.DictUpdate(result, self.expr(v))))
            else:
                run.append((k, v))
                if len(run) * 2 > STACK_USE_GUIDELINE + 2:
                    flush()
        flush()
        return result if result is not None else self.let(G.BuildMap((), ()))


def _falls_through(stmts: list[G.Stmt]) -> bool:
    if not stmts:
        return True
    last = stmts[-1]
    if isinstance(last, (G.Return, G.Raise, G.Break, G.Continue, G.EndLoop)):
        return False
    if isinstance(last, (G.If, G.IfEnd)):
        return _falls_through(list(last.body)) or _falls_through(list(last.orelse))
    if isinstance(last, G.Loop):
        return True       # Break leaves it; an infinite loop without one never falls through, which is harmless
    if isinstance(last, G.Try):
        if last.finalbody and not _falls_through(list(last.finalbody)):
            return False
        return (_falls_through([*last.body, *last.orelse]) or any(_falls_through(list(h.body)) for h in last.handlers))
    return True


@register(PassSpec(
    name="to-anf", source=Level.L1, target=Level.L2,
    requires=frozenset({Fact.EXPLICIT_TRUTH}),
    produces=frozenset({Fact.NAMES_RESOLVED, Fact.ANF}),
    obligations=(
        Obligation("wf", "output satisfies wf2 with lifetimes=False (pipeline.l2.wf)"),
        Obligation("semantics", "eval2(to_anf(m)) == eval1(m) == CPython on the conformance corpus "
                                "(make eval2-corpus) and the differential tests of pipeline/tests/test_l2.py"),
        Obligation("fact_sound", "resolve-names (an analysis of this pass) gives every code object CPython's slot "
                                 "tables: CPython's own code objects (test_l2_resolve) and the host's for the "
                                 "translated code (eval2's SlotMismatch)"),
        Obligation("terminates", "structural recursion over L1"),
    ),
    discharge=Discharge.TESTED, status="tested",
))
def to_l2(m: L.Module) -> G.Module:
    scopes = resolve(m)
    code = _Code(scopes, scopes.root).build(m)
    return G.Module(code, source=m.source, future=m.future)
