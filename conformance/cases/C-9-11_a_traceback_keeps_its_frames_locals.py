# clause: C-9-11
# spec: section 9 (lifetimes), section 7 (traceback)
# status: P1
# source: Python/traceback.c (tb_dealloc: an entry holds its frame), Python/frame.c (take_ownership: a frame object that is
#         still referenced keeps the frame's locals when the frame is over), Objects/frameobject.c (frame_tp_clear), review log
#         RL-222 and D-12 part 2 (decided 2026-11-03: with the collector, step 3c; until then a compiled frame that caught an
#         exception and returned releases its locals at the return)
"""A traceback's entries hold the frames they stand for, and a frame keeps its locals for as long as it is held, also when
it is over. So what a function's variables refer to lives as long as an exception that passed through the function or was
caught in it: until the exception is released, loses its traceback, or its frames are cleared. That holds for the frame
that raised, for a frame the exception left, and for a frame that caught it and returned normally; a frame that has
dropped the exception before it ended keeps nothing."""
# ruff: noqa: F841  # the locals are there to be held
import traceback


class Tracked:
    def __init__(self, name: str) -> None:
        self.name = name

    def __del__(self) -> None:
        print("  released:", self.name)


def catches_and_returns() -> BaseException:
    first = Tracked("the first local of the frame that caught")
    second = Tracked("its second local")
    try:
        raise ValueError("kept")
    except ValueError as exc:
        return exc


def raises() -> None:
    inner = Tracked("a local of the frame that raised")
    raise ValueError("from below")


def catches_from_below() -> BaseException:
    outer = Tracked("a local of the frame that caught from below")
    try:
        raises()
    except ValueError as exc:
        return exc
    return ValueError("not reached")


def catches_and_drops() -> str:
    held = Tracked("a local of a frame that dropped the exception")
    try:
        raise ValueError("dropped")
    except ValueError:
        pass
    return "the frame is over"


def stores(into: list[BaseException]) -> None:
    held = Tracked("a local of a frame that stored the exception")
    try:
        raise ValueError("stored")
    except ValueError as exc:
        into.append(exc)


def raises_another() -> None:
    held = Tracked("a local of a frame two exceptions passed")
    try:
        raise ValueError("first")
    except ValueError:
        raise KeyError("second")  # noqa: B904  # the context is the point


def passes_through() -> None:
    held = Tracked("a local of a frame the exception passed through")
    raises()


print("caught and returned:")
kept = catches_and_returns()
print("  the call is over")
del kept
print("  the exception is gone")

print("caught from below:")
kept = catches_from_below()
print("  the call is over")
del kept
print("  the exception is gone")

print("dropped before the frame ended:")
print(" ", catches_and_drops())

print("stored by the frame that caught:")
stored: list[BaseException] = []
stores(stored)
print("  the call is over")
stored.clear()
print("  the list is empty")

print("without its traceback:")
kept = catches_from_below()
kept.__traceback__ = None
print("  the traceback is gone")
del kept

print("with_traceback(None):")
kept = catches_and_returns()
same = kept.with_traceback(None)
print("  the traceback is gone", same is kept)
del kept, same

print("two exceptions of one frame:")
try:
    raises_another()
except KeyError as second:
    first = second.__context__
    print("  caught:", type(second).__name__, type(first).__name__)
print("  the second is gone")
del first
print("  the first is gone")

print("a frame the exception passed through:")
try:
    passes_through()
except ValueError as passed:
    kept = passed
print("  caught")
del kept
print("  the exception is gone")

print("clear_frames:")
kept = catches_from_below()
traceback.clear_frames(kept.__traceback__)
print("  cleared")
del kept
print("  the exception is gone")

print("a copy of the traceback's entry keeps it too:")
kept = catches_and_returns()
entry = kept.__traceback__
del kept
print("  the exception is gone")
del entry
print("  the entry is gone")
