# clause: C-9-12
# spec: section 9 (lifetimes), section 7 (traceback)
# status: P1
# source: Python/frame.c (_PyFrame_ClearExceptCode: a frame object something else holds takes the frame over; take_ownership:
#         and the frame object of the caller, made if need be, as f_back), Objects/genobject.c (gen_clear_frame, gen_close:
#         a generator's one frame, cleared at its end, at a close and at its dealloc), Objects/frameobject.c (frame_dealloc),
#         review log RL-222
"""A frame has one frame object at most, which its traceback entries share. When the frame is over while something else
holds that object, the object keeps what the frame had, and the frame object of the frame that called it: so a caller
that returned keeps its variables too, for as long as the frame it called is kept. A generator's frame is one over all
its resumes: an exception it kept in its first resume keeps its variables after it has ended, or after it was closed
while suspended, when its frame object keeps what the loop it was suspended in held as well. A bare raise after a yield
adds no second entry of the generator's frame."""
# ruff: noqa: F841  # the locals are there to be held
from collections.abc import Iterator


class Tracked:
    def __init__(self, name: str) -> None:
        self.name = name

    def __del__(self) -> None:
        print("  released:", self.name)


def catches_and_returns() -> BaseException:
    own = Tracked("a local of the frame that caught")
    try:
        raise ValueError("kept")
    except ValueError as exc:
        return exc


def calls() -> BaseException:
    mine = Tracked("a local of its caller")
    return catches_and_returns()


def raises() -> None:
    deepest = Tracked("a local of the frame that raised")
    raise KeyError("from below")


def passes() -> None:
    middle = Tracked("a local of the frame it passed")
    raises()


def catches_from_two_below() -> BaseException:
    top = Tracked("a local of the frame that caught it")
    try:
        passes()
    except KeyError as exc:
        return exc
    return KeyError("not reached")


def keeps_from_its_first_resume(into: list[BaseException]) -> Iterator[int]:
    local = Tracked("a local of the generator")
    try:
        raise ValueError("first resume")
    except ValueError as exc:
        into.append(exc)
    yield 1
    print("  the second resume sees it:", local.name)
    yield 2


def suspended_in_a_loop(into: list[BaseException]) -> Iterator[Tracked]:
    try:
        raise ValueError("before the loop")
    except ValueError as exc:
        into.append(exc)
    for item in iter([Tracked("the item it yielded"), Tracked("an item only the loop's iterator holds")]):  # noqa: UP028 - the loop's iterator on the frame's stack is the row
        yield item


def reraises_past_a_yield() -> Iterator[int]:
    try:
        raise ValueError("caught")
    except ValueError:
        yield 1
        raise


print("a caller of a frame that kept its exception:")
kept = calls()
print("  the calls are over")
del kept
print("  the exception is gone")

print("an exception that passed a frame and was caught two frames up:")
kept = catches_from_two_below()
print("  the call is over")
del kept
print("  the exception is gone")

print("a generator that kept an exception in its first resume:")
held: list[BaseException] = []
gen = keeps_from_its_first_resume(held)
print(" ", next(gen), next(gen), next(gen, "ended"))
del gen
print("  the generator is gone")
held.clear()
print("  the exception is gone")

print("a generator closed while suspended in a loop:")
walker = suspended_in_a_loop(held)
yielded = next(walker)
del yielded
del walker
print("  the generator is gone")
held.clear()
print("  the exception is gone")

print("a bare raise after a yield:")
again = reraises_past_a_yield()
next(again)
try:
    next(again)
except ValueError as error:
    entries = 0
    tb = error.__traceback__
    while tb is not None:
        entries += 1
        tb = tb.tb_next
    print("  entries:", entries)
