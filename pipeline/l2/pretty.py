"""The L2 printer: one line per statement, as docs/l2.md section 6 shows L2.

    python -m pipeline.l2.pretty program.py      # lowers through L1 to L2 and prints it
"""
from __future__ import annotations

import sys
from collections.abc import Iterator

from pipeline.l2 import grammar as G


def atom(a: G.Atom | None) -> str:
    if a is None:
        return "-"
    if isinstance(a, G.Temp):
        return f"t{a.n}"
    return repr(a.value)


def ref(r: G.NameRef) -> str:
    if r.kind == "classdict":
        return f"classdict[{r.mapping}->{r.then}] {r.id}"
    return f"{r.kind} {r.id}"


def _kw(kw: tuple[tuple[str, G.Atom], ...]) -> list[str]:
    return [f"{k}={atom(v)}" for k, v in kw]


def op(o: G.Op) -> str:
    match o:
        case G.Load(r):
            return ref(r)
        case G.Copy(a):
            return f"copy({atom(a)})"
        case G.Locals():
            return "locals"
        case G.CellOf(r):
            return f"cell_of({ref(r)})"
        case G.Builtin(name):
            return f"builtin {name}"
        case G.Binary(o_, a, b):
            return f"binary({o_}, {atom(a)}, {atom(b)})"
        case G.InPlace(o_, a, b):
            return f"inplace({o_}, {atom(a)}, {atom(b)})"
        case G.Unary(o_, a):
            return f"unary({o_}, {atom(a)})"
        case G.Not(a):
            return f"not({atom(a)})"
        case G.Truth(a):
            return f"truth({atom(a)})"
        case G.Compare(o_, a, b):
            return f"compare({o_}, {atom(a)}, {atom(b)})"
        case G.GetAttr(obj, name, cache):
            return f"getattr({atom(obj)}, {name!r})" + (f"@{cache}" if cache else "")
        case G.SetAttr(obj, name, value):
            return f"setattr({atom(obj)}, {name!r}, {atom(value)})"
        case G.DelAttr(obj, name):
            return f"delattr({atom(obj)}, {name!r})"
        case G.GetItem(obj, key):
            return f"getitem({atom(obj)}, {atom(key)})"
        case G.SetItem(obj, key, value):
            return f"setitem({atom(obj)}, {atom(key)}, {atom(value)})"
        case G.DelItem(obj, key):
            return f"delitem({atom(obj)}, {atom(key)})"
        case G.Iter(a):
            return f"iter({atom(a)})"
        case G.ForNext(a):
            return f"for_next({atom(a)})"
        case G.Call(f, args, kw):
            return f"call({', '.join([atom(f), *map(atom, args), *_kw(kw)])})"
        case G.CallEx(f, args, kwargs):
            return f"call_ex({atom(f)}, {atom(args)}, {atom(kwargs)})"
        case G.Runtime(name, args, kw):
            return f"runtime {name}({', '.join([*map(atom, args), *_kw(kw)])})"
        case G.BuildList(items):
            return f"build_list({', '.join(map(atom, items))})"
        case G.BuildTuple(items):
            return f"build_tuple({', '.join(map(atom, items))})"
        case G.BuildSet(items):
            return f"build_set({', '.join(map(atom, items))})"
        case G.BuildMap(keys, values):
            return f"build_map({', '.join(f'{atom(k)}: {atom(v)}' for k, v in zip(keys, values, strict=True))})"
        case G.ListToTuple(a):
            return f"list_to_tuple({atom(a)})"
        case G.MakeFunction(code, defaults, kwdefaults, closure, annotate):
            parts = [f"<code {code.qualname}>"]
            if defaults is not None:
                parts.append(f"defaults={atom(defaults)}")
            if kwdefaults is not None:
                parts.append(f"kwdefaults={atom(kwdefaults)}")
            if closure:
                parts.append(f"closure=({', '.join(map(atom, closure))})")
            if annotate is not None:
                parts.append(f"annotate={atom(annotate)}")
            return f"make_function({', '.join(parts)})"
        case G.Yield(a):
            return f"yield({atom(a)})"
        case G.YieldFrom(a):
            return f"yield_from({atom(a)})"
    # the two-operand container operations share one spelling
    name = type(o).__name__
    fields = [atom(getattr(o, f)) for f in o.__dataclass_fields__]
    return f"{''.join('_' + c.lower() if c.isupper() else c for c in name).lstrip('_')}({', '.join(fields)})"


def stmts(body: tuple[G.Stmt, ...], indent: int, codes: list[G.Code]) -> Iterator[str]:
    pad = "    " * indent
    for s in body:
        match s:
            case G.Let(t, o):
                if isinstance(o, G.MakeFunction):
                    codes.append(o.code)
                yield f"{pad}{atom(t)} = {op(o)}"
            case G.Do(o):
                yield f"{pad}{op(o)}"
            case G.Unpack(targets, value, star):
                names = [("*" if i == star else "") + atom(t) for i, t in enumerate(targets)]
                yield f"{pad}{', '.join(names)} = unpack({atom(value)})"
            case G.Store(r, v):
                yield f"{pad}store {ref(r)}, {atom(v)}"
            case G.Delete(r):
                yield f"{pad}delete {ref(r)}"
            case G.Release(t):
                yield f"{pad}release {atom(t)}"
            case G.If(t, body_, orelse):
                yield f"{pad}if {atom(t)}:"
                yield from stmts(body_, indent + 1, codes) if body_ else iter([f"{pad}    pass"])
                if orelse:
                    yield f"{pad}else:"
                    yield from stmts(orelse, indent + 1, codes)
            case G.IfEnd(t, body_, orelse):
                yield f"{pad}if is_end({atom(t)}):"
                yield from stmts(body_, indent + 1, codes) if body_ else iter([f"{pad}    pass"])
                if orelse:
                    yield f"{pad}else:"
                    yield from stmts(orelse, indent + 1, codes)
            case G.Loop(body_, holds, orelse):
                yield f"{pad}loop" + (f" holding {', '.join(map(atom, holds))}" if holds else "") + ":"
                yield from stmts(body_, indent + 1, codes)
                if orelse:
                    yield f"{pad}loop else:"
                    yield from stmts(orelse, indent + 1, codes)
            case G.EndLoop():
                yield f"{pad}end loop"
            case G.Break():
                yield f"{pad}break"
            case G.Continue():
                yield f"{pad}continue"
            case G.Return(v):
                yield f"{pad}return {atom(v)}"
            case G.Raise(exc, cause, has_cause):
                yield f"{pad}raise" + (f" {atom(exc)}" if exc is not None else "") + (f" from {atom(cause)}" if has_cause else "")
            case G.Try(body_, handlers, orelse, finalbody):
                yield f"{pad}try:"
                yield from stmts(body_, indent + 1, codes)
                for h in handlers:
                    yield from stmts(h.match, indent + 1, codes)
                    head = "except" + (f" {atom(h.type)}" if h.type is not None else "")
                    yield f"{pad}{head}" + (f" as {ref(h.name)}" if h.name is not None else "") + ":"
                    yield from stmts(h.body, indent + 1, codes) if h.body else iter([f"{pad}    pass"])
                if orelse:
                    yield f"{pad}else:"
                    yield from stmts(orelse, indent + 1, codes)
                if finalbody:
                    yield f"{pad}finally:"
                    yield from stmts(finalbody, indent + 1, codes)
            case G.Line(n):
                yield f"{pad}line {n}"
            case _:
                raise TypeError(f"unknown L2 statement {s!r}")


def code(c: G.Code) -> str:
    params = ", ".join(("*" if p.kind == "*args" else "**" if p.kind == "**kwargs" else "") + p.name for p in c.params)
    head = f"code {c.qualname}({params}) kind {c.kind}"
    slots = f"  varnames [{', '.join(c.varnames)}]  cellvars [{', '.join(c.cellvars)}]  freevars [{', '.join(c.freevars)}]"
    nested: list[G.Code] = []
    body = list(stmts(c.body, 1, nested))
    out = [head + slots, *body]
    for n in nested:
        out += ["", code(n)]
    return "\n".join(out)


def module(m: G.Module) -> str:
    return code(m.code)


def main(argv: list[str]) -> int:
    from pipeline.l1.frontend import lower
    from pipeline.l2.lower import to_l2
    path = argv[1]
    src = open(path, encoding="utf-8").read()
    print(module(to_l2(lower(src, path))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
