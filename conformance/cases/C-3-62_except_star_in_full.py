# clause: C-3-62
# spec: section 3 (try/except*), section 8 (tracebacks)
# status: P1
# source: Python/codegen.c (codegen_try_star_except), Python/ceval.c (_PyEval_ExceptionGroupMatch, CHECK_EG_MATCH),
#         Objects/exceptions.c (_PyExc_PrepReraiseStar, exception_group_projection, is_same_exception_metadata), CPython 3.15.2
"""What an except* statement does beyond C-3-16: inside a clause the exception being handled is the part it matched; a bare
raise there gives back a group of the original's shape, which is a new object; an exception that is not a group is
wrapped in one when a clause matches it, and the wrapper's traceback names the except* line; what the clauses raise is
gathered with what is left into a new group, which names no line of the frame that re-raises it; a refusal of a clause's
type takes as its context the part the previous clause matched; and else, finally, notes, nesting and derive. Each line
names classes, the program's own messages, and traceback lines counted from the function's first line."""
import sys
from collections.abc import Callable
from types import TracebackType


def lines(e: BaseException, first: int) -> list[int]:
    out: list[int] = []
    tb: TracebackType | None = e.__traceback__
    while tb is not None:
        out.append(tb.tb_lineno - first)
        tb = tb.tb_next
    return out


def shape(e: BaseException) -> object:
    if isinstance(e, BaseExceptionGroup):
        return [e.message, [shape(x) for x in e.exceptions]]
    return type(e).__name__ + repr(e.args)


def run(f: Callable[[], None]) -> BaseException | None:
    try:
        f()
    except BaseException as e:
        return e
    return None


def handled_is_the_match() -> None:
    try:
        raise ExceptionGroup("g", [ValueError(1), TypeError(2)])
    except* ValueError as e:
        print("handled in the first clause is its match:", sys.exception() is e, shape(e))
    except* TypeError as e:
        print("handled in the second clause is its match:", sys.exception() is e, shape(e))
    print("handled after the statement:", sys.exception())


def bare_raise_gives_the_shape_back() -> None:
    orig = ExceptionGroup("outer", [ValueError(1), ExceptionGroup("inner", [TypeError(2), ValueError(3)])])
    try:
        try:
            raise orig
        except* ValueError:
            raise
    except ExceptionGroup as r:
        print("bare raise:", r is orig, shape(r), lines(r, bare_raise_gives_the_shape_back.__code__.co_firstlineno),
              r.__context__, r.__cause__)


def nothing_matched() -> None:
    orig = ExceptionGroup("g", [ValueError(1)])
    try:
        try:
            raise orig
        except* KeyError:
            print("not reached")
    except ExceptionGroup as r:
        print("nothing matched:", r is orig, shape(r), lines(r, nothing_matched.__code__.co_firstlineno))


def naked_inner() -> None:
    try:
        raise KeyError("k")
    except* KeyError:
        raise


def naked() -> None:
    r = run(naked_inner)
    assert isinstance(r, BaseExceptionGroup)
    first = naked_inner.__code__.co_firstlineno
    print("a naked exception re-raised:", shape(r), lines(r, first), lines(r.exceptions[0], first), r.__context__,
          r.exceptions[0].__context__)


def handler_raises_inner() -> None:
    try:
        raise ExceptionGroup("g", [ValueError(1), TypeError(2)])
    except* ValueError as e:
        raise OSError("new") from e


def handler_raises() -> None:
    r = run(handler_raises_inner)
    assert isinstance(r, BaseExceptionGroup)
    first = handler_raises_inner.__code__.co_firstlineno
    new = r.exceptions[0]
    print("a clause raises:", shape(r), lines(r, first), [lines(x, first) for x in r.exceptions],
          type(new.__cause__).__name__, new.__cause__ is new.__context__, new.__suppress_context__, r.__context__)


def several_raise() -> None:
    try:
        try:
            raise ExceptionGroup("g", [ValueError(1), TypeError(2), KeyError(3)])
        except* ValueError:
            raise ValueError(9)  # noqa: B904
        except* TypeError as e:
            raise e.exceptions[0]  # noqa: B904
        except* KeyError:
            pass
    except ExceptionGroup as r:
        print("several clauses raise:", shape(r))


def invalid_types() -> None:
    for t in (ExceptionGroup, (ValueError, ExceptionGroup), int, (int,), BaseExceptionGroup):
        try:
            try:
                raise ValueError
            except* t:  # type: ignore[misc]
                print("not reached")
        except TypeError as e:
            print("invalid:", type(e).__name__, type(e.__context__).__name__)


def refusal_after_a_match() -> None:
    try:
        try:
            raise ExceptionGroup("g", [ValueError(1), TypeError(2)])
        except* ValueError:
            print("first clause ran")
        except* int:  # type: ignore[misc]
            print("not reached")
    except TypeError as e:
        ctx = e.__context__
        print("a refusal's context:", shape(ctx) if ctx is not None else None)


def else_and_finally() -> None:
    order: list[str] = []
    try:
        try:
            order.append("body")
        except* ValueError:
            order.append("handler")
        else:
            order.append("else")
        finally:
            order.append("finally")
        try:
            raise ExceptionGroup("g", [ValueError(1), TypeError(2)])
        except* ValueError:
            order.append("handler")
        else:
            order.append("else")  # type: ignore[unreachable]
        finally:
            order.append("finally sees " + shape(sys.exception() or ValueError()).__str__())
    except ExceptionGroup as r:
        order.append("then " + str(shape(r)))
    print("else and finally:", order)


def notes_and_derive() -> None:
    class Mine(ExceptionGroup):
        def derive(self, excs: object) -> "Mine":  # type: ignore[override]  # noqa: UP037
            return Mine("derived " + self.message, excs)  # type: ignore[arg-type]

    eg = Mine("mine", [ValueError(1), TypeError(2)])
    eg.add_note("a note")
    try:
        try:
            raise eg
        except* ValueError as e:
            print("matched part:", type(e).__name__, shape(e), getattr(e, "__notes__", None))
    except ExceptionGroup as r:
        print("rest:", type(r).__name__, shape(r), getattr(r, "__notes__", None), r.__notes__ is eg.__notes__)


def bare_exception_types() -> None:
    try:
        try:
            raise ValueError("bare")
        except* TypeError:
            print("not reached")
    except ValueError as r:
        print("a bare exception nothing matched:", shape(r))
    try:
        raise ValueError("bare")
    except* (TypeError, ValueError) as e:
        print("a tuple matched a bare one:", shape(e), e.message == "")


for f in (handled_is_the_match, bare_raise_gives_the_shape_back, nothing_matched, naked, handler_raises, several_raise,
          invalid_types, refusal_after_a_match, else_and_finally, notes_and_derive, bare_exception_types):
    f()
