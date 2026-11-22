# clause: C-3-79
# spec: section 3 (statements: assignment)
# status: P1
# source: Python/flowgraph.c (optimize_basic_block: BUILD_TUPLE n, UNPACK_SEQUENCE n; apply_static_swaps), Python/codegen.c
"""The order in which the targets of `a, b = x, y` are stored, which is the order the values they held are let go of.
CPython stores two or three local names last to first where one target takes a tuple display of as many items, the
names are plain locals of a function, all different and on one line; everything else is stored in the order written."""
from collections.abc import Generator


class Tag:
    def __init__(self, name: str, log: list[str]) -> None:
        self.name = name
        self.log = log

    def __del__(self) -> None:
        self.log.append(self.name)


class Holder:
    x: Tag | None = None


def two() -> list[str]:
    log: list[str] = []
    a, b = Tag("a", log), Tag("b", log)
    a, b = Tag("a2", log), Tag("b2", log)
    seen = list(log)
    del a, b
    return seen


def three() -> list[str]:
    log: list[str] = []
    a, b, c = Tag("a", log), Tag("b", log), Tag("c", log)
    a, b, c = Tag("a2", log), Tag("b2", log), Tag("c2", log)
    seen = list(log)
    del a, b, c
    return seen


def four() -> list[str]:
    log: list[str] = []
    a, b, c, d = Tag("a", log), Tag("b", log), Tag("c", log), Tag("d", log)
    a, b, c, d = Tag("a2", log), Tag("b2", log), Tag("c2", log), Tag("d2", log)
    seen = list(log)
    del a, b, c, d
    return seen


def list_of_targets() -> list[str]:
    log: list[str] = []
    a, b = Tag("a", log), Tag("b", log)
    [a, b] = Tag("a2", log), Tag("b2", log)
    seen = list(log)
    del a, b
    return seen


def list_display() -> list[str]:
    log: list[str] = []
    a, b = Tag("a", log), Tag("b", log)
    a, b = [Tag("a2", log), Tag("b2", log)]
    seen = list(log)
    del a, b
    return seen


def parameters(a: Tag, b: Tag, log: list[str]) -> list[str]:
    a, b = Tag("a2", log), Tag("b2", log)        # what was passed is still the caller's: nothing goes here
    a, b = Tag("a3", log), Tag("b3", log)
    seen = list(log)
    del a, b
    return seen


def constants() -> list[str]:
    log: list[str] = []
    a: object
    b: object
    a, b = Tag("a", log), Tag("b", log)
    a, b = 1, 2
    return [*log, repr(a), repr(b)]


def exchanged() -> list[str]:
    log: list[str] = []
    a, b = Tag("a", log), Tag("b", log)
    a, b = b, a
    first = [a.name, b.name] + list(log)
    del a, b
    return first


def one_name_twice() -> list[str]:
    log: list[str] = []
    a = Tag("a", log)
    a, a = Tag("a2", log), Tag("a3", log)
    seen = [a.name] + list(log)
    del a
    return seen


def three_with_one_twice() -> list[str]:
    log: list[str] = []
    a, b = Tag("a", log), Tag("b", log)
    a, b, a = Tag("a2", log), Tag("b2", log), Tag("a3", log)
    seen = [a.name] + list(log)
    del a, b
    return seen


def on_two_lines() -> list[str]:
    log: list[str] = []
    a, b = Tag("a", log), Tag("b", log)
    (a,
     b) = Tag("a2", log), Tag("b2", log)
    seen = list(log)
    del a, b
    return seen


def display_on_two_lines() -> list[str]:
    log: list[str] = []
    a, b = Tag("a", log), Tag("b", log)
    a, b = (Tag("a2", log),
            Tag("b2", log))
    seen = list(log)
    del a, b
    return seen


kept: Tag | None = None


def a_global() -> list[str]:
    global kept
    log: list[str] = []
    a = Tag("a", log)
    kept = Tag("global", log)
    a, kept = Tag("a2", log), Tag("global2", log)
    seen = list(log)
    del a
    kept = None
    return seen


def a_cell() -> list[str]:
    log: list[str] = []
    a, b = Tag("a", log), Tag("b", log)

    def read() -> str:
        return a.name

    a, b = Tag("a2", log), Tag("b2", log)
    return [read(), b.name, *log]


def nonlocals() -> list[str]:
    log: list[str] = []
    a, b = Tag("a", log), Tag("b", log)

    def assign() -> None:
        nonlocal a, b
        a, b = Tag("a2", log), Tag("b2", log)

    assign()
    seen = list(log)
    del a, b
    return seen


def an_attribute() -> list[str]:
    log: list[str] = []
    holder = Holder()
    a = Tag("a", log)
    holder.x = Tag("attribute", log)
    a, holder.x = Tag("a2", log), Tag("attribute2", log)
    seen = list(log)
    del a, holder
    return seen


def chained() -> list[str]:
    log: list[str] = []
    a, b = Tag("a", log), Tag("b", log)
    both = a, b = Tag("a2", log), Tag("b2", log)
    seen = list(log)
    del a, b, both
    return seen


def starred() -> list[str]:
    log: list[str] = []
    a: object
    b: object
    a, b = Tag("a", log), Tag("b", log)
    a, *b = Tag("a2", log), Tag("b2", log)
    seen = list(log)
    del a, b
    return seen


def nested() -> list[str]:
    log: list[str] = []
    a, b, c = Tag("a", log), Tag("b", log), Tag("c", log)
    a, (b, c) = Tag("a2", log), (Tag("b2", log), Tag("c2", log))
    seen = list(log)
    del a, b, c
    return seen


def in_a_generator() -> list[str]:
    log: list[str] = []

    def steps() -> Generator[list[str]]:
        a, b = Tag("a", log), Tag("b", log)
        yield []
        a, b = Tag("a2", log), Tag("b2", log)
        yield list(log)
        del a, b

    walk = steps()
    next(walk)
    seen: list[str] = next(walk)
    walk.close()
    return seen


def in_a_loop() -> list[str]:
    log: list[str] = []
    a, b = Tag("a", log), Tag("b", log)
    for a, b in [(Tag("a2", log), Tag("b2", log))]:
        log.append("in the loop: " + a.name + " " + b.name)
    seen = list(log)
    del a, b
    return seen


for shape in (two, three, four, list_of_targets, list_display, constants, exchanged, one_name_twice, three_with_one_twice, on_two_lines,
              display_on_two_lines, a_global, a_cell, nonlocals, an_attribute, chained, starred, nested, in_a_generator, in_a_loop):
    print(shape.__name__, shape())
shared: list[str] = []
first, second = Tag("a", shared), Tag("b", shared)
print("parameters", parameters(first, second, shared))

module_log: list[str] = []
ma, mb = Tag("a", module_log), Tag("b", module_log)
ma, mb = Tag("a2", module_log), Tag("b2", module_log)
print("module", list(module_log))


class Body:
    log: list[str] = []
    ca, cb = Tag("a", log), Tag("b", log)
    ca, cb = Tag("a2", log), Tag("b2", log)
    seen = list(log)


print("class", Body.seen)
