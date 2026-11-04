"""L2 grammar (docs/l2.md v1) as frozen dataclasses.

L2 is L1 made explicit in three ways:

* names: every access says which of CPython's instructions makes it (`NameRef.kind`), decided
  statically as CPython's symbol table decides it, and every code object lists its slots in
  CPython's order (`co_varnames`, `co_cellvars`, `co_freevars`);
* evaluation order: A-normal form. An operand is a constant or a temporary, never a nested
  expression and never a name: a name is loaded into a temporary where CPython loads it
  (`g += f()` loads `g` before calling `f`);
* lifetimes: `Release` statements where CPython drops a reference. A temporary is consumed by
  `Store`, `Return`, `Raise`, `Yield`'s value, `If`'s test and `Unpack`'s source, and released
  by a `Release` everywhere else. On an exception the live temporaries die newest first, before
  any handler runs: a rule of the semantics, not statements (docs/l2.md section 8, decision 1).

Every temporary and every name has a `type`; in phase 1 it is always "object" (a marked gap until
phase 2, docs/l2.md section 1).

Operations (`Op`) take their operands in evaluation order. `Let` binds an operation's result to a
fresh temporary; `Do` evaluates an operation for its effect and drops the result at once (CPython's
POP_TOP). The emitter later fuses `Let` + `Release`s into calls that take their operands by move.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from types import EllipsisType

OBJECT = "object"

NAME_KINDS = ("local", "cell", "free", "global", "name", "classdict")


@dataclass(frozen=True)
class Temp:
    n: int
    type: str = OBJECT


@dataclass(frozen=True)
class Const:
    value: int | float | complex | str | bytes | bool | None | EllipsisType | tuple[object, ...] | frozenset[object]


Atom = Const | Temp


@dataclass(frozen=True)
class NameRef:
    """How a name is reached, as CPython's compiler decides it.

    * local: LOAD_FAST / STORE_FAST, a slot of the frame (`co_varnames`).
    * cell: LOAD_DEREF on the frame's own cell (`co_cellvars`): a local some inner scope captures.
    * free: LOAD_DEREF on a cell of the closure (`co_freevars`).
    * global: LOAD_GLOBAL / STORE_GLOBAL: the module's namespace, then builtins.
    * name: LOAD_NAME / STORE_NAME: the frame's namespace mapping (a class body's, or the module's
      globals at module level), then globals, then builtins.
    * classdict: LOAD_FROM_DICT_OR_GLOBALS / LOAD_FROM_DICT_OR_DEREF: a mapping first, then
      `then` ("global" or "free"). `mapping` says which: "locals" (a class body reading a free
      variable of its function) or "__classdict__" (an annotation or type-parameter scope in a
      class, through the `__classdict__` cell).
    """
    kind: str
    id: str
    then: str = ""
    mapping: str = ""
    type: str = OBJECT


# ---- operations ----------------------------------------------------------------------------

@dataclass(frozen=True)
class Op:
    pass


@dataclass(frozen=True)
class Load(Op):
    """A new reference to what the name holds (UnboundLocalError, NameError as CPython raises)."""
    ref: NameRef


@dataclass(frozen=True)
class Copy(Op):
    """COPY: another reference to the operand (the value of `a and b` when `a` decides it, the
    value a walrus leaves after storing)."""
    a: Atom


@dataclass(frozen=True)
class Locals(Op):
    """LOAD_LOCALS: the namespace mapping of a module or class body."""


@dataclass(frozen=True)
class CellOf(Op):
    """The cell object of a cell or free variable (LOAD_CLOSURE), for a closure being built."""
    ref: NameRef


@dataclass(frozen=True)
class Builtin(Op):
    """The interpreter's own builtin or runtime helper `name`, whatever the program binds to the
    name (L1's Intrinsic used as a value)."""
    name: str


@dataclass(frozen=True)
class Binary(Op):
    op: str            # + - * / // % ** << >> & | ^ @
    a: Atom
    b: Atom


@dataclass(frozen=True)
class InPlace(Op):
    op: str            # += -= ... : __iadd__, falling back to __add__ (BINARY_OP with NB_INPLACE_*)
    a: Atom
    b: Atom


@dataclass(frozen=True)
class Unary(Op):
    op: str            # - + ~
    a: Atom


@dataclass(frozen=True)
class Not(Op):
    """`not`: the operand is already a bool from `Truth`."""
    a: Atom


@dataclass(frozen=True)
class Truth(Op):
    """TO_BOOL: __bool__, then __len__, else True."""
    a: Atom


@dataclass(frozen=True)
class Compare(Op):
    op: str            # < <= == != > >= in not-in is is-not
    a: Atom
    b: Atom


@dataclass(frozen=True)
class GetAttr(Op):
    obj: Atom
    name: str
    cache: int = 0     # the inline cache slot of this site (0: none yet)


@dataclass(frozen=True)
class SetAttr(Op):
    obj: Atom
    name: str
    value: Atom


@dataclass(frozen=True)
class DelAttr(Op):
    obj: Atom
    name: str


@dataclass(frozen=True)
class GetItem(Op):
    obj: Atom
    key: Atom


@dataclass(frozen=True)
class SetItem(Op):
    obj: Atom
    key: Atom
    value: Atom


@dataclass(frozen=True)
class DelItem(Op):
    obj: Atom
    key: Atom


@dataclass(frozen=True)
class Iter(Op):
    """GET_ITER."""
    obj: Atom


@dataclass(frozen=True)
class ForNext(Op):
    """FOR_ITER: the next value, or the end marker when the iterator is exhausted (StopIteration
    from `__next__` is consumed here, as CPython consumes it)."""
    it: Atom


@dataclass(frozen=True)
class Call(Op):
    """A call with its arguments spelled out: positional, then keyword (CALL, CALL_KW)."""
    func: Atom
    args: tuple[Atom, ...]
    kw: tuple[tuple[str, Atom], ...] = ()


@dataclass(frozen=True)
class CallEx(Op):
    """CALL_FUNCTION_EX: the positional arguments as one tuple, the keywords as one dict or None."""
    func: Atom
    args: Atom
    kwargs: Atom | None = None


@dataclass(frozen=True)
class Runtime(Op):
    """One of L1's intrinsics called by name (`import_name`, `build_class`, `unpack_iterable`,
    `format`...): the interpreter's own helper, never a name the program can rebind."""
    name: str
    args: tuple[Atom, ...]
    kw: tuple[tuple[str, Atom], ...] = ()


@dataclass(frozen=True)
class BuildList(Op):
    items: tuple[Atom, ...]


@dataclass(frozen=True)
class BuildTuple(Op):
    items: tuple[Atom, ...]


@dataclass(frozen=True)
class BuildSet(Op):
    items: tuple[Atom, ...]


@dataclass(frozen=True)
class BuildMap(Op):
    """BUILD_MAP: keys and values evaluated pairwise, inserted in order."""
    keys: tuple[Atom, ...]
    values: tuple[Atom, ...]


@dataclass(frozen=True)
class ListExtend(Op):
    """LIST_EXTEND (a starred item of a display); returns None."""
    target: Atom
    value: Atom


@dataclass(frozen=True)
class ListAppend(Op):
    target: Atom
    value: Atom


@dataclass(frozen=True)
class SetUpdate(Op):
    target: Atom
    value: Atom


@dataclass(frozen=True)
class SetAdd(Op):
    target: Atom
    value: Atom


@dataclass(frozen=True)
class DictUpdate(Op):
    """DICT_UPDATE (`{**m}`): TypeError naming the type when m is not a mapping."""
    target: Atom
    value: Atom


@dataclass(frozen=True)
class DictMerge(Op):
    """DICT_MERGE (`f(**m)`): a duplicate keyword is a TypeError naming `func`."""
    target: Atom
    value: Atom
    func: Atom


@dataclass(frozen=True)
class MapAdd(Op):
    target: Atom
    key: Atom
    value: Atom


@dataclass(frozen=True)
class ListToTuple(Op):
    """CALL_INTRINSIC_1 INTRINSIC_LIST_TO_TUPLE."""
    value: Atom


@dataclass(frozen=True)
class MakeFunction(Op):
    """MAKE_FUNCTION and SET_FUNCTION_ATTRIBUTE: `defaults` a tuple, `kwdefaults` a dict,
    `closure` the cells (from `CellOf`), in the order of `code.freevars`."""
    code: Code
    defaults: Atom | None = None
    kwdefaults: Atom | None = None
    closure: tuple[Atom, ...] = ()
    annotate: Atom | None = None


@dataclass(frozen=True)
class Yield(Op):
    """YIELD_VALUE: suspends; the result is what send() passes back."""
    value: Atom


@dataclass(frozen=True)
class YieldFrom(Op):
    """`yield from`: PEP 380 delegation; the result is the subiterator's return value."""
    it: Atom


OPS_WITHOUT_RESULT = (SetAttr, DelAttr, SetItem, DelItem, ListExtend, ListAppend, SetUpdate, SetAdd,
                      DictUpdate, DictMerge, MapAdd)


# ---- statements ----------------------------------------------------------------------------

@dataclass(frozen=True)
class Stmt:
    pass


@dataclass(frozen=True)
class Let(Stmt):
    """`t = op`: one operation, its result in a fresh temporary."""
    t: Temp
    op: Op


@dataclass(frozen=True)
class Do(Stmt):
    """An operation for its effect; its result is dropped at once (POP_TOP)."""
    op: Op


@dataclass(frozen=True)
class Unpack(Stmt):
    """UNPACK_SEQUENCE / UNPACK_EX: `targets` receive the items in order; with `star` >= 0, the
    target at that index receives the list of the middle items. Consumes `value`."""
    targets: tuple[Temp, ...]
    value: Atom
    star: int = -1


@dataclass(frozen=True)
class Store(Stmt):
    """Binds the name; consumes `value`. The old value is released after the new one is stored."""
    ref: NameRef
    value: Atom


@dataclass(frozen=True)
class Delete(Stmt):
    ref: NameRef


@dataclass(frozen=True)
class Release(Stmt):
    """This temporary's reference ends here."""
    t: Temp


@dataclass(frozen=True)
class If(Stmt):
    """POP_JUMP_IF_TRUE / _FALSE on a bool temporary, which the test consumes."""
    test: Temp
    body: tuple[Stmt, ...]
    orelse: tuple[Stmt, ...] = ()


@dataclass(frozen=True)
class IfEnd(Stmt):
    """Whether `ForNext` found the iterator exhausted. In `body` the temporary is the end marker
    and needs no release; in `orelse` it holds the next value."""
    t: Temp
    body: tuple[Stmt, ...]
    orelse: tuple[Stmt, ...] = ()


@dataclass(frozen=True)
class Loop(Stmt):
    """Repeats `body`. Left by `Break` (skipping `orelse`), by `EndLoop` (then `orelse` runs,
    outside the loop: a `Break` or `Continue` there is the enclosing loop's), by Return or by an
    exception. `holds` are temporaries the loop owns (a `for` loop's iterator): released when
    control leaves the loop by Break, EndLoop or Return, before `orelse` and after the `finally`
    blocks nested in the loop have run, as CPython pops the iterator (POP_ITER) when the
    unwinding reaches the loop's own block. On an exception they die by the unwinding rule,
    like any temporary."""
    body: tuple[Stmt, ...]
    holds: tuple[Temp, ...] = ()
    orelse: tuple[Stmt, ...] = ()


@dataclass(frozen=True)
class EndLoop(Stmt):
    """Leaves the innermost loop the way a `while` whose test fails or a `for` whose iterator is
    exhausted leaves it: its `orelse` runs."""


@dataclass(frozen=True)
class Break(Stmt):
    pass


@dataclass(frozen=True)
class Continue(Stmt):
    pass


@dataclass(frozen=True)
class Return(Stmt):
    value: Atom


@dataclass(frozen=True)
class Raise(Stmt):
    """`raise` (exc None: re-raise the exception being handled), `raise exc`, `raise exc from c`."""
    exc: Atom | None = None
    cause: Atom | None = None
    has_cause: bool = False


@dataclass(frozen=True)
class Handler:
    """`except` clause. `match` computes the type into `type` (evaluated only when an exception
    reaches this clause, in clause order); `name` is bound to the exception and deleted when the
    body ends, as CPython does (`e = None; del e`)."""
    match: tuple[Stmt, ...]
    type: Temp | None
    name: NameRef | None
    body: tuple[Stmt, ...]


@dataclass(frozen=True)
class Try(Stmt):
    body: tuple[Stmt, ...]
    handlers: tuple[Handler, ...] = ()
    orelse: tuple[Stmt, ...] = ()
    finalbody: tuple[Stmt, ...] = ()


@dataclass(frozen=True)
class Line(Stmt):
    """The source line from here on: tracebacks and the frame record."""
    n: int


# ---- code objects ----------------------------------------------------------------------------

CODE_KINDS = ("module", "function", "generator", "coroutine", "async generator", "classbody", "lambda")


@dataclass(frozen=True)
class Param:
    name: str
    kind: str = "positional-or-keyword"     # as L1's PARAM_KINDS
    public: str | None = None


@dataclass(frozen=True)
class Code:
    """One code object: a module body, a function, a lambda or a class body.

    The slot tables are in CPython's order: `varnames` (parameters first, then the other locals
    in order of first appearance), `cellvars`, `freevars`. A frame releases its slots in reverse
    order when it exits (`_PyFrame_ClearLocals`)."""
    name: str
    qualname: str
    kind: str
    params: tuple[Param, ...]
    varnames: tuple[str, ...]
    cellvars: tuple[str, ...]
    freevars: tuple[str, ...]
    body: tuple[Stmt, ...]
    first_line: int = 0
    docstring: str | None = None
    # L1's facts the runtime needs: a class body returning its __class__ cell, an annotate
    # function (PEP 649), a scope whose loads see the class namespace first
    classcell: bool = False
    annotation: bool = False
    classdict: bool = False
    meta: tuple[tuple[str, object], ...] = field(default=(), compare=False)


@dataclass(frozen=True)
class Module:
    code: Code
    source: str = field(default="<module>", compare=False)
    future: frozenset[str] = field(default=frozenset(), compare=False)


def leaves_by(stmts: Sequence[Stmt], kind: type[Stmt]) -> bool:
    """A statement of `kind` (Break or EndLoop) that belongs to the loop these statements are the
    body of; a nested loop's body has its own, its `else` block is this loop's."""
    for s in stmts:
        if isinstance(s, kind):
            return True
        if isinstance(s, (If, IfEnd)) and (leaves_by(s.body, kind) or leaves_by(s.orelse, kind)):
            return True
        if isinstance(s, Loop) and leaves_by(s.orelse, kind):
            return True
        if isinstance(s, Try) and any(leaves_by(b, kind) for b in (s.body, s.orelse, s.finalbody, *(h.body for h in s.handlers))):
            return True
    return False


def falls_through(stmts: Sequence[Stmt]) -> bool:
    """Control can reach the end of these statements. Both the lowering and the emitter ask."""
    if not stmts:
        return True
    last = stmts[-1]
    if isinstance(last, (Return, Raise, Break, Continue, EndLoop)):
        return False
    if isinstance(last, (If, IfEnd)):
        return falls_through(last.body) or falls_through(last.orelse)
    if isinstance(last, Loop):
        # a `break`, or the iterator's end and then an `else` block that falls through; a `for ...
        # else: raise` with no `break` does not (operator.indexOf), and wf2 refuses what follows it
        return leaves_by(last.body, Break) or (leaves_by(last.body, EndLoop) and falls_through(last.orelse))
    if isinstance(last, Try):
        if last.finalbody and not falls_through(last.finalbody):
            return False
        return (falls_through(last.body) and falls_through(last.orelse)) or any(falls_through(h.body) for h in last.handlers)
    return True
