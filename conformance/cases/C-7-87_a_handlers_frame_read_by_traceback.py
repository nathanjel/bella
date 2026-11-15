# clause: C-7-87
# spec: section 7 (traceback, signal), D-06, E-02
# status: P1
# source: Lib/traceback.py (extract_stack, format_stack, print_stack, walk_stack), Modules/signalmodule.c (_PyErr_CheckSignalsTstate:
#         the frame a handler is called with), Objects/frameobject.c (frame_repr), the author's decision of 2026-11-14
"""The frame a signal handler is given, read by traceback while the handler runs. extract_stack, format_stack and print_stack
given it list the stack the signal found: the file, the line each frame is at and its function, oldest first, the frame
the signal interrupted last, without the handler's own; with the limits of extract_stack. It is what the same functions
give without a frame, less the handler's entry. Two handlers of one arrival are given the same frame; a handler that is
itself interrupted is the frame the second one is given. The frame is of the type types.FrameType and repr() says where it
is. Only the first line of a formatted entry is printed: the source line under it is D-06's."""
import os
import re
import signal
import sys
import traceback
import types
from collections.abc import Callable, Iterator

HERE = __file__
U1, U2 = signal.SIGUSR1, signal.SIGUSR2
Rows = list[tuple[bool, int, str]]
seen: list[str] = []
kept: list[types.FrameType | None] = []


def rows(stack: traceback.StackSummary) -> Rows:
    return [(fs.filename == HERE, fs.lineno or 0, fs.name) for fs in stack]


def heads(entries: list[str]) -> list[str]:
    """The first line of each formatted entry, the directory of this file left out."""
    return [entry.splitlines()[0].strip().replace(HERE.rpartition("/")[0] + "/", "") for entry in entries]


def said(frame: types.FrameType | None) -> str:
    """repr() of a frame without its address and its directory."""
    return re.sub(r"0x[0-9a-fA-F]+", "0x...", repr(frame)).replace(HERE.rpartition("/")[0] + "/", "")


def lists(signum: int, frame: types.FrameType | None) -> None:
    given = rows(traceback.extract_stack(frame))
    own = rows(traceback.extract_stack())
    seen.append(f"the stack the signal found: {given}")
    seen.append(f"the same without the frame, and this handler last: {own[:-1] == given} {own[-1][2]}")
    seen.append(f"the newest two: {rows(traceback.extract_stack(frame, limit=2))}, the oldest one: {rows(traceback.extract_stack(frame, limit=-1))}, "
                f"none: {rows(traceback.extract_stack(frame, limit=0))}")
    seen.append(f"formatted: {heads(traceback.format_stack(frame))} {heads(traceback.format_stack(frame, limit=1))}")
    seen.append(f"what it is: {type(frame).__name__} {isinstance(frame, types.FrameType)} {said(frame)}")


def names_only(signum: int, frame: types.FrameType | None) -> None:
    seen.append(f"found in: {[name for _, _, name in rows(traceback.extract_stack(frame))]}")


def keeps(signum: int, frame: types.FrameType | None) -> None:
    kept.append(frame)
    seen.append(f"handler of {signal.Signals(signum).name}: {[name for _, _, name in rows(traceback.extract_stack(frame))]}")


def interrupted_itself(signum: int, frame: types.FrameType | None) -> None:
    seen.append(f"the first handler was given: {[name for _, _, name in rows(traceback.extract_stack(frame))]}")
    signal.raise_signal(U2)
    seen.append("the first handler goes on")


def prints(signum: int, frame: types.FrameType | None) -> None:
    traceback.print_stack(frame)
    traceback.print_stack(frame, limit=1)


def shown(label: str) -> None:
    for line in seen:
        print(f"{label}: {line}")
    seen.clear()


def innermost() -> None:
    os.kill(os.getpid(), U1)


def middle() -> None:
    innermost()


def outer() -> None:
    middle()


class K:
    def method(self) -> None:
        signal.raise_signal(U1)

    @property
    def read(self) -> int:
        signal.raise_signal(U1)
        return 0

    def __len__(self) -> int:
        signal.raise_signal(U1)
        return 0


def generator() -> Iterator[int]:
    signal.raise_signal(U1)
    yield 1
    signal.raise_signal(U1)
    yield 2


def drive(it: Iterator[int]) -> list[int]:
    return list(it)


def by_a_builtin(work: Callable[[], None]) -> None:
    for _ in map(lambda call: call(), [work]):
        pass


def both_at_once() -> None:
    signal.pthread_sigmask(signal.SIG_BLOCK, {U1, U2})
    os.kill(os.getpid(), U1)
    os.kill(os.getpid(), U2)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, {U1, U2})


signal.signal(U1, lists)
outer()
shown("three calls deep")
signal.raise_signal(U1)
shown("in the module's body")

signal.signal(U1, names_only)
K().method()
K().read  # noqa: B018  # reading the property is the call
len(K())
drive(generator())
by_a_builtin(innermost)
(lambda: signal.raise_signal(U1))()
shown("other frames")


class Body:
    signal.raise_signal(U1)
    after = "the body goes on"


shown("a class body")

signal.signal(U1, keeps)
signal.signal(U2, keeps)
both_at_once()
shown("two signals of one arrival")
print("the same frame for both:", len(kept), kept[0] is kept[1], kept[0] is not None)
kept.clear()

signal.signal(U1, interrupted_itself)
signal.signal(U2, names_only)
middle()
shown("a handler interrupted")

signal.signal(U1, prints)
sys.stderr.flush()
outer()
sys.stderr.flush()
signal.signal(U1, signal.SIG_DFL)
signal.signal(U2, signal.SIG_DFL)
print("done", Body.after)
