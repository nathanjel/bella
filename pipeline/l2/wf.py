"""wf2: well-formedness of L2 (docs/l2.md section 4).

Two modes. Before the `lifetimes` pass (`lifetimes=False`), L2 has no releases yet, and the check
is that every temporary is assigned on every path before it is used. After it, the check is the
release discipline: a temporary is live from its `Let` until exactly one `Release` or consumer
(`Store`, `Return`, `Raise`, an `If` test, an `Unpack` source) on every path; it is never used
or assigned while dead or live respectively; the paths that meet (after an `If`, at a loop's
`Continue` and the end of its body, at a `Try`'s end) agree on what is live; a `Loop` releases
what it `holds` when it is left; and what is live when a `Return` or `Raise` leaves the code is
only what the enclosing loops hold. Exceptions need nothing written: the live temporaries die
newest first, by the semantics.

Both modes check the names: a `local`, `cell` or `free` reference is in its code object's slot
table, `name` is used only in a module or class body, `CellOf` takes a cell or free variable, a
closure matches the nested code's free variables, `Break` and `Continue` are inside a loop, and
every type is "object" (phase 1).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from pipeline.l2 import grammar as G


class WellFormednessError(Exception):
    pass


def _operands(o: G.Op) -> list[G.Atom]:
    out: list[G.Atom] = []
    for name in o.__dataclass_fields__:
        v = getattr(o, name)
        if isinstance(v, (G.Temp, G.Const)):
            out.append(v)
        elif isinstance(v, tuple):
            for x in v:
                if isinstance(x, (G.Temp, G.Const)):
                    out.append(x)
                elif isinstance(x, tuple) and len(x) == 2 and isinstance(x[1], (G.Temp, G.Const)):
                    out.append(x[1])
    return out


@dataclass
class _Loop:
    holds: frozenset[int]
    entry: frozenset[int]
    breaks: list[set[int] | None] = field(default_factory=list)
    continues: list[set[int]] = field(default_factory=list)
    ends: list[set[int]] = field(default_factory=list)


class _Checker:
    def __init__(self, lifetimes: bool) -> None:
        self.lifetimes = lifetimes
        self.errors: list[str] = []

    def fail(self, code: G.Code, msg: str) -> None:
        self.errors.append(f"{code.qualname}: {msg}")

    # ---- names -------------------------------------------------------------------------------

    def ref(self, code: G.Code, r: G.NameRef) -> None:
        if r.kind not in G.NAME_KINDS:
            self.fail(code, f"unknown name kind {r.kind!r} for {r.id!r}")
        elif r.kind == "local" and r.id not in code.varnames:
            self.fail(code, f"local {r.id!r} is not in varnames")
        elif r.kind == "cell" and r.id not in code.cellvars:
            self.fail(code, f"cell {r.id!r} is not in cellvars")
        elif r.kind == "free" and r.id not in code.freevars:
            self.fail(code, f"free {r.id!r} is not in freevars")
        elif r.kind == "name" and code.kind not in ("module", "classbody"):
            self.fail(code, f"name {r.id!r} (LOAD_NAME) outside a module or class body")
        elif r.kind == "classdict" and (r.then not in ("global", "free") or r.mapping not in ("locals", "__classdict__")):
            self.fail(code, f"classdict {r.id!r} needs then= global|free and mapping= locals|__classdict__")
        if r.type != G.OBJECT:
            self.fail(code, f"{r.id!r} has type {r.type!r}: phase 1 has only object")

    # ---- temporaries -------------------------------------------------------------------------

    def use(self, code: G.Code, live: set[int], a: G.Atom | None) -> None:
        if isinstance(a, G.Temp):
            if a.type != G.OBJECT:
                self.fail(code, f"t{a.n} has type {a.type!r}: phase 1 has only object")
            if a.n not in live:
                self.fail(code, f"t{a.n} used where it is not live")

    def consume(self, code: G.Code, live: set[int], a: G.Atom | None) -> None:
        self.use(code, live, a)
        if self.lifetimes and isinstance(a, G.Temp):
            live.discard(a.n)

    def define(self, code: G.Code, live: set[int], t: G.Temp) -> None:
        if self.lifetimes and t.n in live:
            self.fail(code, f"t{t.n} assigned while it is still live")
        live.add(t.n)

    def op(self, code: G.Code, live: set[int], o: G.Op) -> None:
        if isinstance(o, (G.Load, G.CellOf)):
            self.ref(code, o.ref)
            if isinstance(o, G.CellOf) and o.ref.kind not in ("cell", "free"):
                self.fail(code, f"cell_of {o.ref.id!r}: a {o.ref.kind} variable has no cell")
        for a in _operands(o):
            self.use(code, live, a)
        if isinstance(o, G.Yield) and self.lifetimes and isinstance(o.value, G.Temp):
            live.discard(o.value.n)        # YIELD_VALUE hands the value to the caller at the suspension
        if isinstance(o, G.MakeFunction):
            if len(o.closure) != len(o.code.freevars):
                self.fail(code, f"make_function {o.code.qualname}: {len(o.closure)} cells for freevars {list(o.code.freevars)}")
            self.code(o.code)

    # ---- statements --------------------------------------------------------------------------

    def block(self, code: G.Code, body: tuple[G.Stmt, ...], live: set[int], loops: list[_Loop]) -> set[int] | None:
        """The live set after the block, or None when the block does not fall through."""
        state: set[int] | None = set(live)
        for s in body:
            if state is None:
                self.fail(code, f"unreachable statement {type(s).__name__}")
                return None
            state = self.stmt(code, s, state, loops)
        return state

    def merge(self, code: G.Code, what: str, states: list[set[int] | None]) -> set[int] | None:
        reached = [s for s in states if s is not None]
        if not reached:
            return None
        if not self.lifetimes:
            out = set(reached[0])
            for s in reached[1:]:
                out &= s
            return out
        first = reached[0]
        for s in reached[1:]:
            if s != first:
                self.fail(code, f"{what}: paths meet with different live temporaries "
                                f"({sorted(first)} against {sorted(s)})")
        return set(first)

    def leaving(self, code: G.Code, live: set[int], loops: list[_Loop], what: str) -> None:
        if not self.lifetimes:
            return
        held: set[int] = set()
        for lp in loops:
            held |= lp.holds
        if live - held:
            self.fail(code, f"{what} leaves t{', t'.join(map(str, sorted(live - held)))} unreleased")

    def stmt(self, code: G.Code, s: G.Stmt, live: set[int], loops: list[_Loop]) -> set[int] | None:
        match s:
            case G.Let(t, o):
                self.op(code, live, o)
                self.define(code, live, t)
                return live
            case G.Do(o):
                self.op(code, live, o)
                return live
            case G.Unpack(targets, value, star):
                self.consume(code, live, value)
                if star >= len(targets):
                    self.fail(code, f"unpack: star index {star} out of {len(targets)} targets")
                for t in targets:
                    self.define(code, live, t)
                return live
            case G.Store(r, v):
                self.ref(code, r)
                self.consume(code, live, v)
                return live
            case G.Delete(r):
                self.ref(code, r)
                return live
            case G.Release(t):
                self.use(code, live, t)
                live.discard(t.n)
                if not self.lifetimes:
                    live.add(t.n)          # before the lifetimes pass a release is only a use
                return live
            case G.If(t, body, orelse):
                self.consume(code, live, t)
                return self.merge(code, "if", [self.block(code, body, live, loops), self.block(code, orelse, live, loops)])
            case G.IfEnd(t, body, orelse):
                self.use(code, live, t)
                ended = set(live)
                if self.lifetimes:
                    ended.discard(t.n)     # the end marker: nothing to release
                return self.merge(code, "if is_end", [self.block(code, body, ended, loops), self.block(code, orelse, live, loops)])
            case G.Loop(body, holds, orelse):
                for held in holds:
                    self.use(code, live, held)
                lp = _Loop(frozenset(x.n for x in holds), frozenset(live))
                end = self.block(code, body, set(live), [*loops, lp])
                if self.lifetimes:
                    for st in [*lp.continues, *([end] if end is not None else [])]:
                        if st != set(lp.entry):
                            self.fail(code, f"loop: an iteration ends with {sorted(st)} live, it began with {sorted(lp.entry)}")
                exits: list[set[int] | None] = []
                loop_end = self.merge(code, "loop end", list(lp.ends))
                if loop_end is not None:
                    if self.lifetimes:
                        loop_end -= lp.holds
                    else:
                        loop_end |= lp.entry
                    exits.append(self.block(code, orelse, loop_end, loops))
                for b in lp.breaks:
                    if b is not None:
                        exits.append((b - lp.holds) if self.lifetimes else (b | lp.entry))
                return self.merge(code, "after loop", exits)
            case G.Break():
                if not loops:
                    self.fail(code, "break outside a loop")
                    return None
                loops[-1].breaks.append(set(live))
                return None
            case G.EndLoop():
                if not loops:
                    self.fail(code, "end of loop outside a loop")
                    return None
                loops[-1].ends.append(set(live))
                return None
            case G.Continue():
                if not loops:
                    self.fail(code, "continue outside a loop")
                    return None
                loops[-1].continues.append(set(live))
                return None
            case G.Return(v):
                self.consume(code, live, v)
                self.leaving(code, live, loops, "return")
                return None
            case G.Raise(exc, cause, _):
                self.consume(code, live, exc)
                self.consume(code, live, cause)
                self.leaving(code, live, loops, "raise")
                return None
            case G.Try(body, handlers, orelse, finalbody):
                entry = set(live)
                ends = [self.block(code, (*body, *orelse), entry, loops)]
                for handler in handlers:
                    matched = self.block(code, handler.match, entry, loops)
                    if matched is None:
                        continue
                    if handler.type is not None:
                        self.consume(code, matched, handler.type)
                    if handler.name is not None:
                        self.ref(code, handler.name)
                    ends.append(self.block(code, handler.body, matched, loops))
                if self.lifetimes:
                    for path_end in ends:
                        if path_end is not None and path_end != entry:
                            self.fail(code, f"try: a path ends with {sorted(path_end)} live, it began with {sorted(entry)}")
                after = self.merge(code, "after try", ends)
                if finalbody:
                    fin = self.block(code, finalbody, entry, loops)
                    if self.lifetimes and fin is not None and fin != entry:
                        self.fail(code, f"finally: ends with {sorted(fin)} live, began with {sorted(entry)}")
                    if fin is None:
                        return None
                return after
            case G.Line():
                return live
        self.fail(code, f"unknown statement {s!r}")
        return live

    def code(self, code: G.Code) -> None:
        if code.kind not in G.CODE_KINDS:
            self.fail(code, f"unknown code kind {code.kind!r}")
        for group in (code.varnames, code.cellvars, code.freevars):
            if len(set(group)) != len(group):
                self.fail(code, f"a slot table repeats a name: {list(group)}")
        params = [p.name for p in code.params]
        if list(code.varnames[: len(params)]) != params and not set(params) <= set(code.cellvars):
            # a parameter captured by an inner scope is both a varname and a cell (CPython's
            # co_varnames keeps it); otherwise varnames starts with the parameters
            missing = [p for p in params if p not in code.varnames]
            if missing:
                self.fail(code, f"parameters {missing} are not in varnames")
        end = self.block(code, code.body, set(), [])
        if end is not None and self.lifetimes and end:
            self.fail(code, f"the code ends with t{', t'.join(map(str, sorted(end)))} unreleased")


def check(m: G.Module, lifetimes: bool = True) -> None:
    """Raise WellFormednessError on any violated L2 invariant."""
    c = _Checker(lifetimes)
    if m.code.kind != "module":
        c.fail(m.code, f"a module's code has kind {m.code.kind!r}")
    c.code(m.code)
    if c.errors:
        raise WellFormednessError("\n".join(c.errors))
