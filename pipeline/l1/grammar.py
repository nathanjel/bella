"""L1 (PyCore) grammar as frozen dataclasses.

Invariants of the level (checked by ``pipeline.l1.wf``):

* no chained comparisons: ``Compare`` has exactly two operands; chains are desugared with
  single evaluation of the middle operands (C-2-01);
* no ``with``, comprehensions, f-strings or decorators: desugared by the frontend;
* truthiness is explicit: every ``If``/``While`` test and every ``Not`` operand is a
  ``Truth`` node, so a later pass can resolve it per type;
* every bare name is statically bound somewhere in its scope chain or is a builtin.

This is the toy subset used by the first slice. It is deliberately smaller than Python: nodes
the frontend does not produce yet raise ``Unsupported`` with the construct's name, so the gap
is visible rather than approximated.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class Unsupported(NotImplementedError):
    """A Python construct the L1 frontend does not lower yet (never silently approximated)."""


@dataclass(frozen=True)
class Node:
    line: int


# ---- expressions --------------------------------------------------------------------------

@dataclass(frozen=True)
class Expr(Node):
    pass


@dataclass(frozen=True)
class Const(Expr):
    value: int | float | str | bool | None


@dataclass(frozen=True)
class Name(Expr):
    id: str


@dataclass(frozen=True)
class BinOp(Expr):
    op: str            # + - * / // % ** << >> & | ^ @
    left: Expr
    right: Expr


@dataclass(frozen=True)
class UnaryOp(Expr):
    op: str            # - + ~
    operand: Expr


@dataclass(frozen=True)
class Truth(Expr):
    """Explicit truth test: __bool__, then __len__, else True."""
    operand: Expr


@dataclass(frozen=True)
class Not(Expr):
    operand: Truth


@dataclass(frozen=True)
class Compare(Expr):
    op: str            # < <= == != > >= in not-in is is-not
    left: Expr
    right: Expr


@dataclass(frozen=True)
class BoolOp(Expr):
    """``and``/``or`` with Python's operand-returning semantics; binary (chains are nested)."""
    op: str            # and | or
    left: Expr
    right: Expr


@dataclass(frozen=True)
class IfExp(Expr):
    test: Truth
    body: Expr
    orelse: Expr


@dataclass(frozen=True)
class Call(Expr):
    func: Expr
    args: tuple[Expr, ...]
    kwargs: tuple[tuple[str, Expr], ...] = ()


@dataclass(frozen=True)
class GetAttr(Expr):
    obj: Expr
    name: str


@dataclass(frozen=True)
class GetItem(Expr):
    obj: Expr
    key: Expr


@dataclass(frozen=True)
class ListLit(Expr):
    items: tuple[Expr, ...]


@dataclass(frozen=True)
class TupleLit(Expr):
    items: tuple[Expr, ...]


@dataclass(frozen=True)
class DictLit(Expr):
    keys: tuple[Expr, ...]
    values: tuple[Expr, ...]


# ---- assignment targets ------------------------------------------------------------------

@dataclass(frozen=True)
class Target(Node):
    pass


@dataclass(frozen=True)
class NameTarget(Target):
    id: str


@dataclass(frozen=True)
class AttrTarget(Target):
    obj: Expr
    name: str


@dataclass(frozen=True)
class ItemTarget(Target):
    obj: Expr
    key: Expr


@dataclass(frozen=True)
class TupleTarget(Target):
    elts: tuple[Target, ...]


# ---- statements ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Stmt(Node):
    pass


@dataclass(frozen=True)
class Assign(Stmt):
    target: Target
    value: Expr


@dataclass(frozen=True)
class AugAssign(Stmt):
    """In-place operator: __iadd__ with fallback to __add__ (the protocol decides at L2)."""
    target: Target
    op: str
    value: Expr


@dataclass(frozen=True)
class ExprStmt(Stmt):
    value: Expr


@dataclass(frozen=True)
class Return(Stmt):
    value: Expr | None


@dataclass(frozen=True)
class If(Stmt):
    test: Truth
    body: tuple[Stmt, ...]
    orelse: tuple[Stmt, ...]


@dataclass(frozen=True)
class While(Stmt):
    test: Truth
    body: tuple[Stmt, ...]
    orelse: tuple[Stmt, ...]


@dataclass(frozen=True)
class For(Stmt):
    """Iteration intent: iter() once, next() until StopIteration (never an index loop)."""
    target: Target
    iterable: Expr
    body: tuple[Stmt, ...]
    orelse: tuple[Stmt, ...]


@dataclass(frozen=True)
class Break(Stmt):
    pass


@dataclass(frozen=True)
class Continue(Stmt):
    pass


@dataclass(frozen=True)
class Pass(Stmt):
    pass


@dataclass(frozen=True)
class Param:
    name: str
    default: Expr | None = None


@dataclass(frozen=True)
class FunctionDef(Stmt):
    name: str
    params: tuple[Param, ...]
    body: tuple[Stmt, ...]
    globals: frozenset[str] = frozenset()
    nonlocals: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Raise(Stmt):
    exc: Expr | None
    cause: Expr | None = None


@dataclass(frozen=True)
class Handler:
    type: Expr | None
    name: str | None
    body: tuple[Stmt, ...]


@dataclass(frozen=True)
class Try(Stmt):
    body: tuple[Stmt, ...]
    handlers: tuple[Handler, ...]
    orelse: tuple[Stmt, ...]
    finalbody: tuple[Stmt, ...]


@dataclass(frozen=True)
class Delete(Stmt):
    targets: tuple[Target, ...]


@dataclass(frozen=True)
class Assert(Stmt):
    test: Truth
    msg: Expr | None


@dataclass(frozen=True)
class Module(Node):
    body: tuple[Stmt, ...]
    source: str = field(default="<module>", compare=False)
