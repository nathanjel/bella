# clause: C-3-61
# spec: section 3 (exceptions), section 8 (an uncaught exception's report), D-06
# status: P1
# source: Python/codegen.c (codegen_with_inner: the item's location for BEFORE_WITH and the calls of __exit__), found by a
# same-machine signal test, 2026-11-11 (pipeline/tests/test_signals.py, a KeyboardInterrupt out of a nested with)
"""The line a with statement's own work is charged to. What the statement does itself (looking up __enter__ and
__exit__, calling __enter__, binding its value to the target, calling __exit__ when the body is over, on the way out by
return, break or an exception) is at the line where the item's expression starts: the with's line for one item on one
line, an item's own line when the items take several, and the first line of an expression written over several. What the
body raises keeps the body's line. Each row is the exception's class and its line, counted from the function's first line,
in the function's own entry of the traceback."""
from collections.abc import Callable
from types import TracebackType


class Boom(Exception):
    pass


class M:
    def __init__(self, enter: bool = False, exit: bool = False, swallow: bool = False) -> None:
        self.e, self.x, self.s = enter, exit, swallow

    def __enter__(self) -> M:
        if self.e:
            raise Boom("enter")
        return self

    def __exit__(self, kind: type[BaseException] | None, value: BaseException | None, tb: TracebackType | None) -> bool:
        if self.x:
            raise Boom("exit")
        return self.s


class NoEnter:
    def __exit__(self, *rest: object) -> None:
        pass


class NoExit:
    def __enter__(self) -> None:
        pass


def where(f: Callable[[], object]) -> str:
    """The class of what f raised and the line of f's own entry in its traceback, from f's first line."""
    try:
        f()
    except BaseException as e:
        tb = e.__traceback__
        entry = tb.tb_next if tb is not None else None   # the first entry is this function's, at the call; the next is f's
        if entry is None:
            return type(e).__name__ + " (no entry)"
        return type(e).__name__ + " " + str(entry.tb_lineno - f.__code__.co_firstlineno)
    return "nothing raised"


def enter_raises() -> None:
    with M(enter=True):
        pass


def exit_raises() -> None:
    with M(exit=True):
        pass


def exit_raises_while_handling() -> None:
    with M(exit=True):
        raise ValueError


def no_enter() -> None:
    with NoEnter():  # type: ignore[attr-defined]
        pass


def no_exit() -> None:
    with NoExit():  # type: ignore[attr-defined]
        pass


def the_second_item_on_its_own_line() -> None:
    with M(), \
         M(enter=True):
        pass


def items_in_parentheses() -> None:
    with (
        M() as first,
        M(exit=True) as second,
    ):
        print("in the body:", first is not second)


def an_expression_over_two_lines() -> None:
    with M(
            enter=True):
        pass


def exit_after_a_longer_body() -> None:
    with M(exit=True):
        x = 1
        y = x + 1
        print("in the body:", y)


def exit_on_return() -> int:
    with M(exit=True):
        n = 5
        return n
    return 0                            # M's __exit__ may swallow, as far as a checker knows


def exit_on_break() -> None:
    for _ in range(2):
        with M(exit=True):
            break


def nested() -> None:
    with M():
        with M(enter=True):
            pass


def the_target_cannot_be_unpacked() -> None:
    with M() as (p, q):  # type: ignore[misc]
        pass


def the_target_on_another_line() -> None:
    with (M()  # type: ignore[misc]
          as (p, q)):
        pass


def an_exit_over_two_lines() -> None:
    with M(
            exit=True) as v:
        print("in the body:", type(v).__name__)


def the_body_raises() -> None:
    with M():
        x = 1
        raise ValueError(x)


def the_body_raises_and_exit_swallows_then_another() -> None:
    with M(swallow=True):
        raise ValueError
    raise KeyError


def a_call_in_the_body_fails() -> None:
    with M():
        int("x")


for fn in (enter_raises, exit_raises, exit_raises_while_handling, no_enter, no_exit, the_second_item_on_its_own_line,
           items_in_parentheses, an_expression_over_two_lines, exit_after_a_longer_body, exit_on_return, exit_on_break, nested,
           the_target_cannot_be_unpacked, the_target_on_another_line, an_exit_over_two_lines, the_body_raises,
           the_body_raises_and_exit_swallows_then_another, a_call_in_the_body_fails):
    print(fn.__name__ + ":", where(fn))
