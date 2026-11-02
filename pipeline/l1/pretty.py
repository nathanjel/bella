"""L1 as text, for people: `python -m pipeline.l1.pretty program.py` (or `-c "source"`).

Python-like on purpose, with what L1 makes explicit shown as such:

* `%name(...)` is an intrinsic: a builtin the desugarings call whatever the program binds to
  the name, or one of the core's operations (build_class, import_name, classcell, ...);
* `truth(x)` is the explicit truth test of a condition;
* `(name := value)` is a binding expression (__bind__);
* `classbody NAME:` is the function of the namespace a class statement runs;
* a definition's header carries what CPython attaches to it: its kind, qualname, decorators,
  docstring and annotate function;
* names the frontend generated (`_comp3`, `_dec0`) are hidden from the program: eval1 keeps
  them out of globals() and locals().
"""
from __future__ import annotations

import sys

from pipeline.l1 import grammar as L

_PREC = {"or": 1, "and": 2, "not": 3, "cmp": 4, "|": 5, "^": 6, "&": 7, "<<": 8, ">>": 8, "+": 9, "-": 9,
         "*": 10, "/": 10, "//": 10, "%": 10, "@": 10, "unary": 11, "**": 12}


def expr(e: L.Expr, prec: int = 0) -> str:
    text, mine = _expr(e)
    return f"({text})" if mine < prec else text


def _expr(e: L.Expr) -> tuple[str, int]:
    if isinstance(e, L.Const):
        return repr(e.value), 99
    if isinstance(e, L.Name):
        return e.id, 99
    if isinstance(e, L.Intrinsic):
        return f"%{e.name}", 99
    if isinstance(e, L.BinOp):
        p = _PREC[e.op]
        right = p + 1 if e.op != "**" else p
        return f"{expr(e.left, p if e.op != '**' else p + 1)} {e.op} {expr(e.right, right)}", p
    if isinstance(e, L.UnaryOp):
        return f"{e.op}{expr(e.operand, _PREC['unary'])}", _PREC["unary"]
    if isinstance(e, L.Truth):
        return f"truth({expr(e.operand)})", 99
    if isinstance(e, L.Not):
        return f"not {expr(e.operand, _PREC['not'])}", _PREC["not"]
    if isinstance(e, L.Compare):
        op = {"not-in": "not in", "is-not": "is not"}.get(e.op, e.op)
        return f"{expr(e.left, _PREC['cmp'] + 1)} {op} {expr(e.right, _PREC['cmp'] + 1)}", _PREC["cmp"]
    if isinstance(e, L.BoolOp):
        p = _PREC[e.op]
        return f"{expr(e.left, p + 1)} {e.op} {expr(e.right, p)}", p
    if isinstance(e, L.IfExp):
        return f"{expr(e.body, 1)} if {expr(e.test, 1)} else {expr(e.orelse)}", 0
    if isinstance(e, L.Starred):
        return f"*{expr(e.value, 99)}", 99
    if isinstance(e, L.Call):
        if isinstance(e.func, L.Name) and e.func.id == "__bind__":
            name = e.args[0]
            assert isinstance(name, L.Const) and isinstance(name.value, str)
            return f"({name.value} := {expr(e.args[1])})", 99
        parts = [expr(a) for a in e.args]
        parts += [f"**{expr(v)}" if k is None else f"{k}={expr(v)}" for k, v in e.kwargs]
        return f"{expr(e.func, 99)}({', '.join(parts)})", 99
    if isinstance(e, L.GetAttr):
        return f"{expr(e.obj, 99)}.{e.name}", 99
    if isinstance(e, L.GetItem):
        return f"{expr(e.obj, 99)}[{expr(e.key)}]", 99
    if isinstance(e, L.ListLit):
        return f"[{', '.join(expr(x) for x in e.items)}]", 99
    if isinstance(e, L.TupleLit):
        inner = ", ".join(expr(x) for x in e.items)
        return f"({inner}{',' if len(e.items) == 1 else ''})", 99
    if isinstance(e, L.SetLit):
        return "{" + ", ".join(expr(x) for x in e.items) + "}", 99
    if isinstance(e, L.DictLit):
        items = [f"**{expr(v)}" if k is None else f"{expr(k)}: {expr(v)}" for k, v in zip(e.keys, e.values, strict=True)]
        return "{" + ", ".join(items) + "}", 99
    if isinstance(e, L.Yield):
        return ("yield" if e.value is None else f"yield {expr(e.value)}"), 0
    if isinstance(e, L.YieldFrom):
        return f"yield from {expr(e.value)}", 0
    if isinstance(e, L.Lambda):
        head = f"lambda {params(e.params)}".rstrip()
        kind = "  # generator" if e.kind == "generator" else ""
        if e.prelude:
            return f"{head}: [prelude {len(e.prelude)} stmt] {expr(e.body)}{kind}", 0
        return f"{head}: {expr(e.body)}{kind}", 0
    if isinstance(e, L.ClassBody):
        return f"<classbody {e.qualname}>", 99
    raise TypeError(f"unknown expression {type(e).__name__}")


def target(t: L.Target) -> str:
    if isinstance(t, L.NameTarget):
        return t.id
    if isinstance(t, L.AttrTarget):
        return f"{expr(t.obj, 99)}.{t.name}"
    if isinstance(t, L.ItemTarget):
        return f"{expr(t.obj, 99)}[{expr(t.key)}]"
    if isinstance(t, L.StarTarget):
        return f"*{target(t.target)}"
    if isinstance(t, L.TupleTarget):
        inner = ", ".join(target(x) for x in t.elts)
        return f"({inner}{',' if len(t.elts) == 1 else ''})"
    raise TypeError(f"unknown target {type(t).__name__}")


def params(ps: tuple[L.Param, ...]) -> str:
    out: list[str] = []
    for i, p in enumerate(ps):
        name = p.name if p.public is None else f"{p.name}<{p.public}>"
        if p.kind == "*args":
            name = "*" + name
        elif p.kind == "**kwargs":
            name = "**" + name
        elif p.kind == "keyword-only" and not any(q.kind in ("*args", "keyword-only") for q in ps[:i]):
            out.append("*")
        out.append(name if p.default is None else f"{name}={expr(p.default)}")
        if p.kind == "positional-only" and (i + 1 == len(ps) or ps[i + 1].kind != "positional-only"):
            out.append("/")
    return ", ".join(out)


class _Printer:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def emit(self, depth: int, text: str) -> None:
        self.lines.append("    " * depth + text)

    def block(self, stmts: tuple[L.Stmt, ...], depth: int) -> None:
        if not stmts:
            self.emit(depth, "pass")
        for s in stmts:
            self.stmt(s, depth)

    def classbody_in(self, e: L.Expr, depth: int) -> None:
        """A class statement's body, printed under the statement that builds it."""
        for sub in _subexprs(e):
            if isinstance(sub, L.ClassBody):
                flags = [f for f, on in (("classcell", sub.classcell), ("classdict", sub.classdict)) if on]
                self.emit(depth + 1, f"classbody {sub.qualname}:" + (f"  # {', '.join(flags)}" if flags else ""))
                self.block(sub.body, depth + 2)

    def stmt(self, s: L.Stmt, depth: int) -> None:
        if isinstance(s, L.Assign):
            self.emit(depth, f"{target(s.target)} = {expr(s.value)}")
            self.classbody_in(s.value, depth)
        elif isinstance(s, L.AugAssign):
            self.emit(depth, f"{target(s.target)} {s.op}= {expr(s.value)}")
        elif isinstance(s, L.ExprStmt):
            self.emit(depth, expr(s.value))
        elif isinstance(s, L.Return):
            self.emit(depth, "return" if s.value is None else f"return {expr(s.value)}")
            if s.value is not None:
                self.classbody_in(s.value, depth)
        elif isinstance(s, (L.If, L.While)):
            self.emit(depth, f"{'if' if isinstance(s, L.If) else 'while'} {expr(s.test)}:")
            self.block(s.body, depth + 1)
            if s.orelse:
                self.emit(depth, "else:")
                self.block(s.orelse, depth + 1)
        elif isinstance(s, L.For):
            self.emit(depth, f"for {target(s.target)} in {'iterator ' if s.iterator else ''}{expr(s.iterable)}:")
            self.block(s.body, depth + 1)
            if s.orelse:
                self.emit(depth, "else:")
                self.block(s.orelse, depth + 1)
        elif isinstance(s, (L.Break, L.Continue, L.Pass)):
            self.emit(depth, type(s).__name__.lower())
        elif isinstance(s, L.Declare):
            self.emit(depth, f"declare {', '.join(s.names)}  # an annotated name: local, unbound")
        elif isinstance(s, L.FunctionDef):
            self.function(s, depth)
        elif isinstance(s, L.Raise):
            text = "raise" if s.exc is None else f"raise {expr(s.exc)}"
            self.emit(depth, text if s.cause is None else f"{text} from {expr(s.cause)}")
        elif isinstance(s, L.Try):
            self.emit(depth, "try:")
            self.block(s.body, depth + 1)
            for h in s.handlers:
                head = "except" + (f" {expr(h.type)}" if h.type is not None else "") + (f" as {h.name}" if h.name else "")
                self.emit(depth, head + ":")
                self.block(h.body, depth + 1)
            if s.orelse:
                self.emit(depth, "else:")
                self.block(s.orelse, depth + 1)
            if s.finalbody:
                self.emit(depth, "finally:")
                self.block(s.finalbody, depth + 1)
        elif isinstance(s, L.Delete):
            self.emit(depth, f"del {', '.join(target(t) for t in s.targets)}")
        elif isinstance(s, L.Assert):
            self.emit(depth, f"assert {expr(s.test)}" + (f", {expr(s.msg)}" if s.msg is not None else ""))
        else:
            raise TypeError(f"unknown statement {type(s).__name__}")

    def function(self, f: L.FunctionDef, depth: int) -> None:
        notes: list[str] = []
        if f.kind != "function":
            notes.append(f.kind)
        if f.qualname and f.qualname != f.name:
            notes.append(f"qualname {f.qualname!r}")
        if f.store:
            notes.append(f"stored as {f.store}")
        if f.decorators:
            notes.append(f"decorators {', '.join(expr(d) for d in f.decorators)} (applied bottom-up)")
        if f.globals:
            notes.append(f"global {', '.join(sorted(f.globals))}")
        if f.nonlocals:
            notes.append(f"nonlocal {', '.join(sorted(f.nonlocals))}")
        if f.enclosing_binds:
            notes.append(f"binds {', '.join(sorted(f.enclosing_binds))} in the enclosing scope")
        if f.annotation:
            notes.append("annotate function: names resolved when called")
        if f.classdict:
            notes.append("reads the class namespace first")
        if f.docstring is not None:
            notes.append(f"doc {f.docstring!r}")
        for note in notes:
            self.emit(depth, f"# {note}")
        self.emit(depth, f"def {f.name}({params(f.params)}):")
        if f.annotate is not None:
            self.emit(depth + 1, "# __annotate__ (made with the function):")
            for line in _render(f.annotate.body, 0):
                self.emit(depth + 1, "#     " + line)
        if f.kind in ("coroutine", "async generator"):
            self.emit(depth + 1, "...  # the body runs only when the coroutine runs: [P2+], not lowered")
        else:
            self.block(f.body, depth + 1)


def _subexprs(e: L.Expr) -> list[L.Expr]:
    out: list[L.Expr] = [e]
    for v in vars(e).values():
        items = v if isinstance(v, tuple) else (v,)
        for x in items:
            if isinstance(x, L.Expr):
                out += _subexprs(x)
            elif isinstance(x, tuple) and len(x) == 2 and isinstance(x[1], L.Expr):
                out += _subexprs(x[1])
    return out


def _render(stmts: tuple[L.Stmt, ...], depth: int) -> list[str]:
    p = _Printer()
    p.block(stmts, depth)
    return p.lines


def render(m: L.Module) -> str:
    return "\n".join(_render(m.body, 0)) + "\n"


def main(argv: list[str]) -> int:
    from pipeline.l1.frontend import lower
    if argv[:1] == ["-c"]:
        source, name = argv[1], "<string>"
    else:
        name = argv[0]
        with open(name, encoding="utf-8") as f:
            source = f.read()
    sys.stdout.write(render(lower(source, name)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
