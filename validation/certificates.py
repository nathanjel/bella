"""Range certificates for integer expressions and the checkers that decide them.

A ``RangeCertificate`` claims: for every assignment of the variables within ``bounds``, every
subexpression of ``expr`` (intermediates included, review round one, finding 5) fits in the
signed ``bits``-bit range. Both checkers fail closed (review 2026-11-01, astra-low-01 #6,
gemini 2.3.1): a verdict is PROVED, REFUTED with a witness, or UNKNOWN, and only PROVED licenses
removing a check. ``check_intervals`` uses interval arithmetic, a sound over-approximation (not
exact: a variable that occurs twice, as in ``x - x``, widens the interval), so it proves or, with a
corner witness, refutes; anything else is UNKNOWN. ``check_z3`` decides the claim with Z3 when the
package is installed: ``unsat`` proves, ``sat`` refutes with the model, ``unknown`` stays UNKNOWN.
"""
from __future__ import annotations

import enum
import itertools
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Var:
    name: str


@dataclass(frozen=True)
class Lit:
    value: int


@dataclass(frozen=True)
class Add:
    left: Expr
    right: Expr


@dataclass(frozen=True)
class Sub:
    left: Expr
    right: Expr


@dataclass(frozen=True)
class Mul:
    left: Expr
    right: Expr


@dataclass(frozen=True)
class Neg:
    operand: Expr


Expr = Var | Lit | Add | Sub | Mul | Neg
Bounds = dict[str, tuple[int, int]]   # inclusive lower and upper bound per variable


@dataclass(frozen=True)
class RangeCertificate:
    expr: Expr
    bounds: Bounds
    bits: int = 64

    @property
    def lo(self) -> int:
        return -(1 << (self.bits - 1))

    @property
    def hi(self) -> int:
        return (1 << (self.bits - 1)) - 1


class Outcome(enum.Enum):
    PROVED = "proved"
    REFUTED = "refuted"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Verdict:
    outcome: Outcome
    witness: dict[str, int] | None = None   # an assignment under which some subexpression overflows
    offending: str | None = None            # the subexpression and its value at the witness
    reason: str | None = None               # why the checker could not decide (UNKNOWN only)

    @property
    def proved(self) -> bool:
        """The only verdict that licenses removing a check."""
        return self.outcome is Outcome.PROVED

    @property
    def refuted(self) -> bool:
        return self.outcome is Outcome.REFUTED


def evaluate(e: Expr, env: dict[str, int]) -> int:
    if isinstance(e, Var):
        return env[e.name]
    if isinstance(e, Lit):
        return e.value
    if isinstance(e, Add):
        return evaluate(e.left, env) + evaluate(e.right, env)
    if isinstance(e, Sub):
        return evaluate(e.left, env) - evaluate(e.right, env)
    if isinstance(e, Mul):
        return evaluate(e.left, env) * evaluate(e.right, env)
    return -evaluate(e.operand, env)


def subexpressions(e: Expr) -> list[Expr]:
    out = [e]
    for child in (getattr(e, "left", None), getattr(e, "right", None), getattr(e, "operand", None)):
        if child is not None:
            out.extend(subexpressions(child))
    return out


def interval(e: Expr, bounds: Bounds) -> tuple[int, int]:
    """Sound bounds of e over the box (an over-approximation when a variable occurs more than once)."""
    if isinstance(e, Var):
        return bounds[e.name]
    if isinstance(e, Lit):
        return e.value, e.value
    if isinstance(e, Neg):
        lo, hi = interval(e.operand, bounds)
        return -hi, -lo
    a_lo, a_hi = interval(e.left, bounds)
    b_lo, b_hi = interval(e.right, bounds)
    if isinstance(e, Add):
        return a_lo + b_lo, a_hi + b_hi
    if isinstance(e, Sub):
        return a_lo - b_hi, a_hi - b_lo
    corners = [a_lo * b_lo, a_lo * b_hi, a_hi * b_lo, a_hi * b_hi]
    return min(corners), max(corners)


def render(e: Expr) -> str:
    if isinstance(e, Var):
        return e.name
    if isinstance(e, Lit):
        return str(e.value)
    if isinstance(e, Neg):
        return f"-({render(e.operand)})"
    op = {"Add": "+", "Sub": "-", "Mul": "*"}[type(e).__name__]
    return f"({render(e.left)} {op} {render(e.right)})"


def check_intervals(cert: RangeCertificate) -> Verdict:
    """Prove the certificate with interval arithmetic, refute it with a corner witness, or say UNKNOWN."""
    undecided: list[str] = []
    names = sorted(cert.bounds)
    for sub in subexpressions(cert.expr):
        lo, hi = interval(sub, cert.bounds)
        if lo < cert.lo or hi > cert.hi:
            for corner in itertools.product(*(cert.bounds[n] for n in names)):
                env = dict(zip(names, corner, strict=True))
                v = evaluate(sub, env)
                if v < cert.lo or v > cert.hi:
                    return Verdict(Outcome.REFUTED, env, f"{render(sub)} = {v}")
            # the interval is an over-approximation: no corner overflows, but an interior point
            # might (130 - x*x at x = 0), or none does (x - x); this checker cannot tell
            undecided.append(f"{render(sub)} in [{lo}, {hi}]")
    if undecided:
        return Verdict(Outcome.UNKNOWN, reason="interval exceeds the range without a corner witness: " + "; ".join(undecided))
    return Verdict(Outcome.PROVED)


def check_z3(cert: RangeCertificate) -> Verdict:
    """Decide the certificate with Z3 (MIT); requires the `z3-solver` package."""
    import z3  # noqa: PLC0415 -- optional dependency

    names = sorted(cert.bounds)
    zvars = {n: z3.Int(n) for n in names}

    def tr(e: Expr) -> Any:
        if isinstance(e, Var):
            return zvars[e.name]
        if isinstance(e, Lit):
            return z3.IntVal(e.value)
        if isinstance(e, Add):
            return tr(e.left) + tr(e.right)
        if isinstance(e, Sub):
            return tr(e.left) - tr(e.right)
        if isinstance(e, Mul):
            return tr(e.left) * tr(e.right)
        return -tr(e.operand)

    solver = z3.Solver()
    for n in names:
        lo, hi = cert.bounds[n]
        solver.add(zvars[n] >= lo, zvars[n] <= hi)
    overflow = [z3.Or(tr(s) < cert.lo, tr(s) > cert.hi) for s in subexpressions(cert.expr)]
    solver.add(z3.Or(*overflow))
    result = solver.check()
    if result == z3.unsat:
        return Verdict(Outcome.PROVED)
    if result == z3.sat:
        m = solver.model()
        env = {n: m.eval(zvars[n], model_completion=True).as_long() for n in names}
        for s in subexpressions(cert.expr):
            v = evaluate(s, env)
            if v < cert.lo or v > cert.hi:
                return Verdict(Outcome.REFUTED, env, f"{render(s)} = {v}")
        return Verdict(Outcome.UNKNOWN, reason="Z3 model does not reproduce an overflow under evaluate()")
    return Verdict(Outcome.UNKNOWN, reason=f"Z3 returned {result}")


# ---- the standing example (design document, section 13; clause C-9-1) ---------------------

NORM2 = Add(Mul(Var("x"), Var("x")), Mul(Var("y"), Var("y")))


def norm2_certificate(bits_of_operands: int) -> RangeCertificate:
    """The claim 'x, y in [-2^b, 2^b) make x*x + y*y safe in int64'."""
    b = 1 << bits_of_operands
    return RangeCertificate(NORM2, {"x": (-b, b - 1), "y": (-b, b - 1)}, 64)
