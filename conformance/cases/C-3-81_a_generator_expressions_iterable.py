# clause: C-3-81
# spec: section 3 (expressions: generator expressions)
# status: P1
# source: Python/codegen.c (codegen_comprehension: a generator expression's code takes the iterable and calls GET_ITER itself), Python/ceval.c (_PyFrame_ClearLocals)
"""What a generator expression holds, and when it lets go of it. Its code is given the iterable of its first `for`,
which stays its variable `.0` for as long as the generator has its frame; `iter()` is called on it when the expression is
evaluated, and the iterator is the frame's alone: it goes when the loop ends, before the variables, and first of all when
a generator that did not finish is given up. (A list, set or dict comprehension is given the iterator, and the iterable
goes at once.)"""
import traceback
import weakref
from collections.abc import Iterator


class Item:
    def __init__(self, number: int, log: list[str]) -> None:
        self.number = number
        self.log = log

    def __del__(self) -> None:
        self.log.append("drop " + str(self.number))


class Steps:
    def __init__(self, count: int, log: list[str]) -> None:
        self.count = count
        self.at = 0
        self.log = log

    def __iter__(self) -> Steps:
        return self

    def __next__(self) -> Item:
        self.at += 1
        if self.at > self.count:
            self.log.append("stop")
            raise StopIteration
        self.log.append("next " + str(self.at))
        return Item(self.at, self.log)

    def __del__(self) -> None:
        self.log.append("drop iterator")


class Source:
    def __init__(self, count: int, log: list[str]) -> None:
        self.count = count
        self.log = log

    def __iter__(self) -> Steps:
        self.log.append("iter")
        return Steps(self.count, self.log)

    def __del__(self) -> None:
        self.log.append("drop iterable")


def taken(log: list[str]) -> list[str]:
    seen = list(log)
    del log[:]
    return seen


def made_and_run() -> list[list[str]]:
    log: list[str] = []
    out: list[list[str]] = []
    g = (v for v in Source(3, log))
    out.append(taken(log))                      # iter() was called; nothing went
    first = next(g)
    out.append(taken(log))
    del first
    out.append(taken(log))                      # the generator's variable still has the item
    for _ in g:
        pass
    out.append(taken(log))                      # the loop's end: the iterator, then the variables (the iterable last)
    del g, _
    out.append(taken(log))
    return out


def made_and_dropped() -> list[str]:
    log: list[str] = []
    g = (v for v in Source(3, log))
    del g
    return taken(log)


def closed_after_one() -> list[list[str]]:
    log: list[str] = []
    g = (v for v in Source(3, log))
    first = next(g)
    del first
    g.close()
    closed = taken(log)
    del g
    return [closed, taken(log)]


def dropped_after_one() -> list[str]:
    log: list[str] = []
    g = (v for v in Source(3, log))
    first = next(g)
    del first
    del g
    return taken(log)


def summed() -> list[str]:
    log: list[str] = []
    total = sum(1 for v in Source(3, log))
    log.append("total " + str(total))
    return taken(log)


def listed() -> list[str]:
    log: list[str] = []
    numbers = list(v.number for v in Source(2, log))
    log.append("numbers " + str(numbers))
    return taken(log)


def two_loops() -> list[list[str]]:
    log: list[str] = []
    g = ((a.number, b.number) for a in Source(2, log) for b in Source(1, log))
    made = taken(log)                           # only the first iterable is asked when the expression is evaluated
    pairs = list(g)
    log.append("pairs " + str(pairs))
    return [made, taken(log)]


def with_a_condition() -> list[str]:
    log: list[str] = []
    numbers = list(v.number for v in Source(4, log) if v.number % 2 == 0)
    log.append("numbers " + str(numbers))
    return taken(log)


def the_other_comprehensions() -> list[list[str]]:
    log: list[str] = []
    out: list[list[str]] = []
    as_list = [v for v in Source(2, log)]
    out.append(taken(log))                      # given the iterator: the iterable goes once iter() has returned
    as_set = {v for v in Source(2, log)}
    out.append(taken(log))
    as_dict = {v.number: v for v in Source(2, log)}
    out.append(taken(log))
    out.append([str(len(as_list)), str(len(as_set)), str(sorted(as_dict))])
    return out


def an_iterator_given() -> list[list[str]]:
    log: list[str] = []
    steps = Steps(2, log)
    g = (v.number for v in steps)               # iter() of an iterator is the iterator: `.0` and the loop have one object
    del steps
    made = taken(log)
    numbers = list(g)
    log.append("numbers " + str(numbers))
    return [made, taken(log)]


def kept_alive() -> list[bool]:
    log: list[str] = []
    source = Source(2, log)
    watch = weakref.ref(source)
    g = (v.number for v in source)
    del source
    while_it_lives = watch() is not None        # the generator's `.0` is the only reference
    numbers = list(g)
    after_the_end = watch() is None             # a generator that has finished has no frame
    return [while_it_lives, after_the_end, numbers == [1, 2]]


def what_locals_shows() -> list[str]:
    shown: list[str] = []
    one: Iterator[int] = iter([7])
    iterables: list[object] = [[1], (1,), range(1), "a", {1: 2}, {1}, frozenset([1]), b"a", one]
    for iterable in iterables:
        names = next(locals() for v in iterable)  # type: ignore[attr-defined]
        shown.append(" ".join(name + "=" + type(value).__name__ for name, value in sorted(names.items())))
    return shown


class Refuses:
    def __iter__(self) -> Iterator[int]:
        raise ValueError


def a_failing_iter() -> list[str]:
    try:
        (v for v in Refuses())
    except ValueError as error:
        return [frame.name for frame in traceback.extract_tb(error.__traceback__)]
    return []


def not_iterable() -> str:
    try:
        (v for v in 5)  # type: ignore[attr-defined]
    except TypeError:
        return "TypeError when the expression is evaluated"
    return "no error"


def in_a_lambda() -> list[str]:
    log: list[str] = []
    numbers = list((lambda: (v.number for v in Source(2, log)))())
    log.append("numbers " + str(numbers))
    return taken(log)


class Body:
    log: list[str] = []
    numbers = list(v.number for v in Source(2, log))
    seen = list(log)


for shape in (made_and_run, made_and_dropped, closed_after_one, dropped_after_one, summed, listed, two_loops, with_a_condition,
              the_other_comprehensions, an_iterator_given, kept_alive, what_locals_shows, a_failing_iter, not_iterable, in_a_lambda):
    print(shape.__name__, shape())
print("class", Body.numbers, Body.seen)

module_log: list[str] = []
module_numbers = list(v.number for v in Source(2, module_log))
print("module", module_numbers, module_log)
