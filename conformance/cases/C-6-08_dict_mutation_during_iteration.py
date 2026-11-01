# clause: C-6-08
# spec: section 6
# status: P1
# source: TODO task 2 (dict mutation during iteration: only a size change raises)
"""Iterating a dict while changing its size raises RuntimeError. A mutation that keeps the size
does not raise: iteration continues by position in the entry table, so it sees what CPython's
compact layout puts there (measured on 3.15.2: after clear() and two inserts, the iterator at
position 1 yields the second new key). Assigning to existing keys is allowed. A set raises on
a size change too."""
from collections.abc import Callable


def run(label: str, d: dict[str, int], step: Callable[[dict[str, int], str], object]) -> None:
    seen: list[str] = []
    try:
        for k in d:
            seen.append(k)
            if len(seen) > 20:
                print(label, "-> runaway")
                return
            step(d, k)
        print(label, "-> no error, seen", seen, "| now", d)
    except RuntimeError as exc:
        print(label, "->", type(exc).__name__, "seen", seen, "| now", d)


def refill(d: dict[str, int], k: str) -> None:
    if k == "a":
        d.clear()
        d.update(x=1, y=2)


def swap_last(d: dict[str, int], k: str) -> None:
    if k == "a":
        d.pop("c")
        d["z"] = 1


def double(d: dict[str, int], k: str) -> None:
    d[k] *= 10


def insert(d: dict[str, int], k: str) -> None:
    d["new"] = 0


def pop_and_add(d: dict[str, int], k: str) -> None:
    d.pop(k)
    d[k + "!"] = 1


run("assign existing", {"a": 1, "b": 2}, double)
run("insert", {"a": 1, "b": 2, "c": 3}, insert)
run("pop", {"a": 1, "b": 2, "c": 3}, lambda d, k: d.pop(k))
run("pop self, add another", {"a": 1, "b": 2, "c": 3}, pop_and_add)
run("pop last, add another", {"a": 1, "b": 2, "c": 3}, swap_last)
run("clear and refill", {"a": 1, "b": 2}, refill)
s = {1, 2, 3}
try:
    for x in s:
        s.add(x + 10)
except RuntimeError as exc:
    print("set add ->", type(exc).__name__)
