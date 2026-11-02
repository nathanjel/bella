"""lifetimes: the `Release` statements of L2 (docs/l2.md section 5).

A backward liveness analysis over the structured tree places each release where CPython drops
the reference:

* after the statement that uses a temporary for the last time on its path, the temporaries that
  die there newest first (an operation drops its operands last-evaluated first: `a * b` drops
  `b`, then `a`; a call drops its arguments last to first, then the callable; measured on
  3.15.2);
* at the start of a branch that does not need a temporary the other branch needs (`a and b`
  drops `a` before evaluating `b`, CPython's POP_TOP);
* never for what a statement consumes (`Store`, `Return`, `Raise`, an `If` test, an `Unpack`
  source, a `Yield`'s value, which goes to the caller at the suspension) or what a `Loop` holds
  (the loop releases its iterator itself);
* a temporary nothing uses is released right after the statement that makes it.

The output satisfies wf2 with `lifetimes=True`.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from pipeline.l2 import grammar as G
from pipeline.l2.wf import _operands
from pipeline.passes.spec import Discharge, Fact, Level, Obligation, PassSpec, register


@dataclass
class _Ctx:
    holds: frozenset[int] = frozenset()
    break_live: frozenset[int] = frozenset()       # live after the innermost loop, holds included
    end_live: frozenset[int] = frozenset()         # live entering its orelse, holds included
    head_live: frozenset[int] = frozenset()        # live at the head of its body


def _temps(atoms: list[G.Atom | None]) -> set[int]:
    return {a.n for a in atoms if isinstance(a, G.Temp)}


def _uses(s: G.Stmt) -> tuple[set[int], set[int], set[int]]:
    """(used, consumed, defined) temporaries of a simple statement."""
    match s:
        case G.Let(t, op):
            used = _temps(list(_operands(op)))
            consumed = _temps([op.value]) if isinstance(op, G.Yield) else set()
            return used, consumed, {t.n}
        case G.Do(op):
            used = _temps(list(_operands(op)))
            return used, (_temps([op.value]) if isinstance(op, G.Yield) else set()), set()
        case G.Unpack(targets, value, _):
            v = _temps([value])
            return v, v, {t.n for t in targets}
        case G.Store(_, v):
            used = _temps([v])
            return used, used, set()
        case G.Return(v):
            used = _temps([v])
            return used, used, set()
        case G.Raise(exc, cause, _):
            used = _temps([exc, cause])
            return used, used, set()
    return set(), set(), set()


def _releases(temps: set[int]) -> list[G.Stmt]:
    return [G.Release(G.Temp(n)) for n in sorted(temps, reverse=True)]


class _Pass:
    def __init__(self) -> None:
        self.holds_all: set[int] = set()

    def block(self, body: tuple[G.Stmt, ...], live_out: frozenset[int], ctx: _Ctx) -> tuple[tuple[G.Stmt, ...], frozenset[int]]:
        out: list[G.Stmt] = []
        live = live_out
        for s in reversed(body):
            new, live = self.stmt(s, live, ctx)
            out[:0] = new
        return tuple(out), live

    def branch(self, body: tuple[G.Stmt, ...], needed: frozenset[int], live_in: frozenset[int],
               skip: frozenset[int] = frozenset()) -> tuple[G.Stmt, ...]:
        """A branch begins by releasing what only the other path needs."""
        drop = set(needed - live_in - skip) - self.holds_all
        return (*_releases(drop), *body)

    def stmt(self, s: G.Stmt, live_after: frozenset[int], ctx: _Ctx) -> tuple[list[G.Stmt], frozenset[int]]:
        match s:
            case G.Line() | G.Delete():
                return [s], live_after
            case G.Release():
                return [], live_after             # the pass places every release itself
            case G.Break():
                return [s], ctx.break_live
            case G.EndLoop():
                return [s], ctx.end_live
            case G.Continue():
                return [s], ctx.head_live
            case G.Return() | G.Raise():
                used, _, _ = _uses(s)
                return [s], frozenset(used) | ctx.holds
            case G.If(t, body, orelse):
                b, in_b = self.block(body, live_after, ctx)
                o, in_o = self.block(orelse, live_after, ctx)
                needed = in_b | in_o
                new = G.If(t, self.branch(b, needed, in_b), self.branch(o, needed, in_o))
                return [new], needed | {t.n}
            case G.IfEnd(t, body, orelse):
                b, in_b = self.block(body, live_after, ctx)
                o, in_o = self.block(orelse, live_after, ctx)
                needed = in_b | in_o
                end = frozenset({t.n})
                # at the end marker the temporary holds nothing; on the other path it holds the
                # next value, released at once when nothing uses it
                stepped = G.IfEnd(t, self.branch(b, needed - end, in_b), self.branch(o, needed | end, in_o))
                return [stepped], needed | end
            case G.Loop(body, holds, orelse):
                hold = frozenset(h.n for h in holds)
                self.holds_all |= hold
                o, in_else = self.block(orelse, live_after, ctx)
                head = hold
                for _ in range(8):                       # to a fixpoint (two rounds suffice for structured code)
                    inner = _Ctx(ctx.holds | hold, live_after | hold, in_else | hold, head)
                    b, in_body = self.block(body, head, inner)
                    new_head = in_body | hold
                    if new_head == head:
                        break
                    head = new_head
                return [G.Loop(b, holds, o)], head
            case G.Try(body, handlers, orelse, finalbody):
                fin, in_fin = self.block(finalbody, live_after, ctx) if finalbody else ((), live_after)
                after = in_fin
                o, in_or = self.block(orelse, after, ctx)
                new_handlers = []
                exc_live: frozenset[int] = in_fin if finalbody else frozenset()
                for h in handlers:
                    hb, in_hb = self.block(h.body, after, ctx)
                    typed = in_hb | ({h.type.n} if h.type is not None else frozenset())
                    m, in_m = self.block(h.match, typed, ctx)
                    new_handlers.append(G.Handler(m, h.type, h.name, hb))
                    exc_live |= in_m
                b, in_body = self.block(body, in_or | exc_live, ctx)
                return [G.Try(b, tuple(new_handlers), o, fin)], in_body | exc_live
        used, consumed, defined = _uses(s)
        live_before = (live_after - defined) | used
        dying = (used | defined) - live_after - consumed - self.holds_all
        if isinstance(s, G.Let) and isinstance(s.op, G.MakeFunction):
            s = replace(s, op=replace(s.op, code=lifetimes_code(s.op.code)))
        return [s, *_releases(dying)], frozenset(live_before)


def lifetimes_code(code: G.Code) -> G.Code:
    body, _ = _Pass().block(code.body, frozenset(), _Ctx())
    return replace(code, body=body)


@register(PassSpec(
    name="lifetimes", source=Level.L2, target=Level.L2,
    requires=frozenset({Fact.ANF}),
    produces=frozenset({Fact.LIFETIMES_EXPLICIT}),
    obligations=(
        Obligation("wf", "output satisfies wf2 with lifetimes=True"),
        Obligation("semantics", "eval2(lifetimes(m)) == CPython on the lifetime cases (C-9, C-3-01, C-3-12) and the "
                                "release-point probes of pipeline/tests/test_l2.py, and == eval2(m) elsewhere"),
        Obligation("terminates", "structural recursion; the loop fixpoint grows a finite set of temporaries"),
    ),
    discharge=Discharge.TESTED, status="tested",
))
def lifetimes(m: G.Module) -> G.Module:
    return replace(m, code=lifetimes_code(m.code))
