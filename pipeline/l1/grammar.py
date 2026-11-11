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
from types import EllipsisType


class Unsupported(NotImplementedError):
    """A Python construct the L1 frontend does not lower yet (never silently approximated)."""


class Refused(BaseException):  # noqa: N818  # a refusal, not an error a program may handle
    """A runtime refusal: what the program reached is not lowered (decision P-1) or is beyond the
    phase (running a coroutine). It stops the program, stderr `bella: refused: ...` and exit 70;
    no except clause catches it and no finally block runs."""


class DialectError(Exception):
    """A program outside the dialect: a compile-time error naming its register or exclusion id
    (for example D-10, control flow leaving ``finally``). Unlike ``Unsupported`` it is permanent."""


@dataclass(frozen=True)
class Node:
    line: int


# ---- expressions --------------------------------------------------------------------------

@dataclass(frozen=True)
class Expr(Node):
    pass


@dataclass(frozen=True)
class Const(Expr):
    value: int | float | complex | str | bytes | bool | None | EllipsisType


@dataclass(frozen=True)
class Intrinsic(Expr):
    """A builtin the frontend's desugarings call (``iter``, ``format``, ``type``, ...): always
    the interpreter's own, whatever the program binds to the name (hygiene: a parameter called
    ``type`` must not change what a ``with`` statement calls)."""
    name: str


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
class Starred(Expr):
    """``*value`` among a call's positional arguments: iterated into them in place."""
    value: Expr


@dataclass(frozen=True)
class Call(Expr):
    """Positional arguments (a ``Starred`` one is unpacked in place) are evaluated before the
    keyword items, which keep their source order; a keyword item named None is ``**mapping``,
    merged as CPython's DICT_MERGE does (a duplicate name is a TypeError)."""
    func: Expr
    args: tuple[Expr, ...]
    kwargs: tuple[tuple[str | None, Expr], ...] = ()


@dataclass(frozen=True)
class ClassBody(Expr):
    """A class statement's body as a function of the namespace, the way CPython's compiler makes
    it: called by ``build_class`` with the mapping ``__prepare__`` returned, it runs the body with
    that mapping as its locals (names stored and deleted through it; a name the body binds is
    read from it, then from globals and builtins; a free name from it, then from the enclosing
    function), and returns the ``__class__`` cell when ``classcell`` is set (a function in the
    body uses ``super`` or ``__class__``). Functions defined in the body do not see its names."""
    qualname: str
    body: tuple[Stmt, ...]
    globals: frozenset[str] = frozenset()
    nonlocals: frozenset[str] = frozenset()
    classcell: bool = False
    classdict: bool = False    # the __classdict__ cell: the namespace while the body runs, stored as __classdictcell__


@dataclass(frozen=True)
class Lambda(Expr):
    """A function expression: ``params`` as in ``FunctionDef``, the body one expression."""
    params: tuple[Param, ...]
    body: Expr
    qualname: str
    kind: str = "function"     # "generator" when the body yields
    prelude: tuple[Stmt, ...] = ()   # the helpers of comprehensions in the body, made at each call


@dataclass(frozen=True)
class Yield(Expr):
    """``yield value``: suspends the generator; its value is what send() passes back."""
    value: Expr | None


@dataclass(frozen=True)
class YieldFrom(Expr):
    """``yield from value``: PEP 380 delegation; its value is the subiterator's return value."""
    value: Expr


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
    """A display; a ``Starred`` item is iterated into it in place (LIST_EXTEND). Built as codegen
    builds it: the items first, unless one is starred or there are more than 30."""
    items: tuple[Expr, ...]


@dataclass(frozen=True)
class TupleLit(Expr):
    items: tuple[Expr, ...]


@dataclass(frozen=True)
class SetLit(Expr):
    """`folded`: CPython makes this display a frozenset constant and updates an empty set from it, and the
    table that leaves, so the order the set iterates in, is not the one inserting the items would."""
    items: tuple[Expr, ...]
    folded: bool = False


@dataclass(frozen=True)
class DictLit(Expr):
    """A key of None is ``**value`` (DICT_UPDATE). Pairs are built in codegen's sub-dicts."""
    keys: tuple[Expr | None, ...]
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
class StarTarget(Target):
    """``*target`` among a TupleTarget's elements (at most one): gets the list of the rest."""
    target: Target


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
    """Iteration intent: iter() once, next() until StopIteration (never an index loop).
    ``iterator``: the iterable is already the iterator, made by GET_ITER where the loop was
    written (a comprehension's outermost loop), so the loop only advances it (FOR_ITER)."""
    target: Target
    iterable: Expr
    body: tuple[Stmt, ...]
    orelse: tuple[Stmt, ...]
    iterator: bool = False


@dataclass(frozen=True)
class Break(Stmt):
    """`looks`: CPython 3.15.2 compiles this break to JUMP_BACKWARD, so its eval loop looks for signals when the
    break leaves the loop (the frontend asks CPython's compiler: mark_looking_breaks)."""
    looks: bool = False


@dataclass(frozen=True)
class Continue(Stmt):
    pass


@dataclass(frozen=True)
class Pass(Stmt):
    pass


PARAM_KINDS = ("positional-only", "positional-or-keyword", "*args", "keyword-only", "**kwargs")


@dataclass(frozen=True)
class Param:
    """A parameter. A function's parameters are in CPython's order: positional-only,
    positional-or-keyword, ``*args``, keyword-only, ``**kwargs``; defaults are evaluated in that
    order when the definition runs (positional ones become ``__defaults__``, keyword-only ones
    ``__kwdefaults__``)."""
    name: str
    default: Expr | None = None
    kind: str = "positional-or-keyword"
    public: str | None = None   # the name CPython reports, when `name` is a hidden one (annotate's format)


@dataclass(frozen=True)
class FunctionDef(Stmt):
    """A definition, run as CPython runs one: the decorators (already evaluated into names by
    the frontend, top first) are applied bottom-up to the new function, and the name is bound
    once. ``annotate`` is the PEP 649 ``__annotate__`` the frontend generates, defined in the
    same scope as the function; ``qualname`` is ``co_qualname``."""
    name: str
    params: tuple[Param, ...]
    body: tuple[Stmt, ...]
    globals: frozenset[str] = frozenset()
    nonlocals: frozenset[str] = frozenset()
    qualname: str = ""
    decorators: tuple[Expr, ...] = ()
    annotate: FunctionDef | None = None
    docstring: str | None = None
    store: str = ""            # the name it is bound to, when private-name mangling changed it
    # "function"; "generator" (the body yields: a call makes a generator); "coroutine" and
    # "async generator" (async def: a call makes the object, and running it is [P2+], so the
    # body is not lowered)
    kind: str = "function"
    # names this function binds in the scope that contains it: a comprehension's walrus
    # targets (PEP 572), declared nonlocal or global in the comprehension's function, in the
    # order the comprehension binds them
    enclosing_binds: tuple[str, ...] = ()
    # the enclosing binds skip the scope that contains the comprehension, an annotation scope, and bind in the function around
    # it (symtable_extend_namedexpr_scope passes an AnnotationBlock by); that scope has them free
    binds_through: bool = False
    # an annotate function (PEP 649): its names are resolved when it is called, never checked
    # statically; `classdict`: defined in a class, so a name is looked up in the class's
    # namespace first (LOAD_FROM_DICT_OR_GLOBALS, LOAD_FROM_DICT_OR_DEREF)
    annotation: bool = False
    classdict: bool = False
    # a list, set or dict comprehension's helper: CPython inlines it (PEP 709), so it has no
    # frame of its own and never enters a traceback
    inlined: bool = False
    # such a helper whose comprehension stands in the module's own code (not in a function, a lambda, a class body or a
    # generator expression): inlined there, its free names are LOAD_NAME, the frame's locals before the globals
    module_frame: bool = False
    # co_firstlineno: the first decorator's line when there are decorators, else the def's (`line`)
    first_line: int = 0


@dataclass(frozen=True)
class Declare(Stmt):
    """`x: T` with no value: binds nothing at runtime, but makes the name local to its scope
    (symtable's DEF_LOCAL), as an assignment would."""
    names: tuple[str, ...]


@dataclass(frozen=True)
class Raise(Stmt):
    exc: Expr | None
    cause: Expr | None = None


@dataclass(frozen=True)
class Handler:
    type: Expr | None
    name: str | None
    body: tuple[Stmt, ...]
    line: int = 0                       # the `except` line: where matching runs (CHECK_EXC_MATCH's location)


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
    # names the frontend generated (comparison temporaries, comprehension helpers); they are
    # chosen not to collide with any identifier of the source and are invisible to the program
    synthetic: frozenset[str] = field(default=frozenset(), compare=False)
    future: frozenset[str] = field(default=frozenset(), compare=False)   # its __future__ features
    mode: str = field(default="exec", compare=False)   # "eval": the value is the last statement's
    # the names its own statements declare global, and the walrus targets of its comprehensions, which the symbol table
    # declares so (symtable_extend_namedexpr_scope): stored and read in the globals, where a text run with locals of its own
    # would use those (STORE_GLOBAL against STORE_NAME); in a module run as a module the two are one mapping
    globals: frozenset[str] = field(default=frozenset(), compare=False)
