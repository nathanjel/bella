# clause: C-3-29
# spec: section 3
# status: P1
# source: Gate 0 task 4, step A5 (the census of docs/measurements.md, 2026-11-02)
"""Generators and comprehensions: send, the return value, yield from, close running finally,
throw, PEP 479 at the generator's boundary only, generator expressions named <genexpr>, set and
dict comprehensions, walrus targets binding in the containing scope (PEP 572), and an exception
raised in a generator taking the caller's exception as its context."""
from collections.abc import Generator, Iterator


def counter(n: int) -> Generator[int, int | None, int]:
    total = 0
    for i in range(n):
        got = yield i
        if got is not None:
            total += got
    return total


g = counter(3)
print(type(g).__name__, g.__name__, g.__qualname__, next(g), g.send(10), g.send(5))  # type: ignore[attr-defined]  # generators have them
try:
    g.send(1)
except StopIteration as stop:
    print("returned", stop.value)


def delegate() -> Generator[int | str, int | None]:
    result = yield from counter(2)
    yield f"result {result}"


print(list(delegate()))


def guarded() -> Generator[int]:
    try:
        yield 1
        yield 2
    finally:
        print("finally runs")


closing = guarded()
print(next(closing))
closing.close()


def catcher() -> Generator[None]:
    while True:
        try:
            yield
        except ValueError as exc:
            print("caught", exc.args)


c = catcher()
next(c)
c.throw(ValueError("thrown"))
c.close()
empty: Iterator[int] = iter([])


def leaks() -> Iterator[int]:
    yield next(empty)


def catches_inside() -> Iterator[int | str]:
    try:
        x = (yield 1) + next(empty)  # type: ignore[operator]  # the StopIteration is the point
        yield x
    except StopIteration:
        yield "caught StopIteration inside"


try:
    list(leaks())
except RuntimeError as exc:
    print("RuntimeError from", type(exc.__cause__).__name__)
print(list(catches_inside()))
squares = (x * x for x in range(4) if x)
print(type(squares).__name__, squares.__name__, squares.__qualname__, list(squares))  # type: ignore[attr-defined]  # generators have it


def make_genexp() -> Iterator[int]:
    return (y for y in [1])


print(make_genexp().__qualname__)  # type: ignore[attr-defined]  # generators have it
print(sorted({x % 3 for x in range(10)}), {k: n for k, n in [("a", 1), ("b", 2)]})


def walrus(xs: list[int]) -> tuple[list[int], int]:
    ys = [last := x * 2 for x in xs]
    return ys, last


print(walrus([1, 2]))
running_total = 0
running = [running_total := running_total + x for x in [1, 2, 3]]
print(running, running_total)


def context() -> None:
    try:
        raise KeyError("outer")
    except KeyError:
        def inner() -> Iterator[None]:
            yield
            raise ValueError("in the generator")
        it = inner()
        next(it)
        try:
            next(it)
        except ValueError as exc:
            print("context", type(exc.__context__).__name__)


context()
