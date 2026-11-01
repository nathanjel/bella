# clause: C-3-04
# spec: section 3 (IterStep carries the original exception)
# status: P1
# source: review round 3, finding 4 (next() exposes the StopIteration subclass, args, value and identity)
"""Python-visible next() re-raises the original StopIteration; yield from takes its value."""
from collections.abc import Iterator


class Done(StopIteration):
    pass


original = Done(7, "payload")


class Once:
    def __iter__(self) -> "Once":
        return self

    def __next__(self) -> int:
        raise original


try:
    next(Once())
except StopIteration as exc:
    print(type(exc).__name__, exc.args, exc.value, exc is original)


def delegate() -> Iterator[int]:
    result = yield from Once()
    print("yield from returned", result)


print("for-loop ends normally:", list(Once()) == [])
list(delegate())
