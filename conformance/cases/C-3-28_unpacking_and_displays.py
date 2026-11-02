# clause: C-3-28
# spec: section 3
# status: P1
# source: Gate 0 task 4, step A5 (the census of docs/measurements.md, 2026-11-02)
"""Assignment and displays as CPython runs them: several targets stored left to right, starred
targets, unpacking that reads an iterator only as far as it needs (an infinite one included),
the order in which display items are evaluated and hashed (all items first, unless one is
starred or there are more than 30 of them), dict unpacking, and the error types."""
import itertools
from collections.abc import Callable

trace: list[str] = []


class Hashed:
    def __init__(self, n: int) -> None:
        self.n = n

    def __hash__(self) -> int:
        trace.append(f"hash {self.n}")
        return self.n

    def __eq__(self, other: object) -> bool:
        return self is other


def v[T](name: str, value: T) -> T:
    trace.append(name)
    return value


def error(make: Callable[[], object]) -> str:
    try:
        make()
    except (TypeError, ValueError) as exc:
        return type(exc).__name__
    return "no error"


a = b = c = [1]
print(a is b, b is c)
first, *middle, last = range(5)
print(first, middle, last)
*everything, = "ab"  # type: ignore[str-unpack]  # unpacking a string is the point
outer, (inner, *rest) = 1, [2, 3, 4]
print(everything, outer, inner, rest)


def too_many() -> None:
    _p, _q = [1, 2, 3]  # type: ignore[misc]  # the ValueError is the point


def too_few() -> None:
    _p, *_q, _r = [1]  # type: ignore[misc]  # the ValueError is the point


def not_iterable() -> None:
    _p, _q = 5  # type: ignore[misc]  # the TypeError is the point


def infinite() -> None:
    _p, _q = itertools.count()     # reads three items, then stops


print(error(too_many), error(too_few), error(not_iterable), error(infinite))
print([*range(3), 4, *"ab"], (*[1], 2), sorted({*[3, 1], 2}))
plain = {v("a", Hashed(1)), v("b", Hashed(2))}
print(trace)
trace.clear()
starred = {v("a", Hashed(1)), *v("b", [Hashed(2)]), v("c", Hashed(3))}
print(trace)
trace.clear()
merged = {v("k1", Hashed(1)): v("v1", 1), **v("m", {Hashed(0): 0}), v("k2", Hashed(2)): v("v2", 2)}
print(trace, len(merged))
trace.clear()
big = {Hashed(0): v("v0", 0), Hashed(1): v("v1", 1), Hashed(2): 2, Hashed(3): 3, Hashed(4): 4, Hashed(5): 5,
       Hashed(6): 6, Hashed(7): 7, Hashed(8): 8, Hashed(9): 9, Hashed(10): 10, Hashed(11): 11, Hashed(12): 12,
       Hashed(13): 13, Hashed(14): 14, Hashed(15): 15, Hashed(16): 16}
print(trace)
trace.clear()
print(error(lambda: {**1}), error(lambda: [*1]), error(lambda: {*1}))  # type: ignore[dict-item, misc]  # the TypeErrors are the point
