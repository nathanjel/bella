# clause: C-3-80
# spec: section 3 (statements: match)
# status: P1
# source: Python/codegen.c (codegen_match_inner, codegen_pattern_helper_store_name), Python/flowgraph.c (swaptimize, apply_static_swaps)
"""The order in which the names a `match` case captures are stored, which is the order the values they held are let go
of. CPython keeps what a pattern captured on its stack until the whole pattern has matched and stores the names then; its
optimizer exchanges those stores where the names are plain locals of a function, so the order follows the pattern's shape:
`[a, [b, c]]` stores b, c and then a. A name that is a global or a cell, a pattern written over several lines, module and
class level keep more or all of the order of capture."""
from collections.abc import Generator


class Tag:
    def __init__(self, name: str, log: list[str]) -> None:
        self.name = name
        self.log = log

    def __del__(self) -> None:
        self.log.append(self.name)


class Point:
    __match_args__ = ("x", "y")

    def __init__(self, x: object, y: object) -> None:
        self.x = x
        self.y = y


def flat_two() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    s: object = [Tag("a2", log), Tag("b2", log)]
    match s:
        case [a, b]:
            pass
    seen = list(log)
    del a, b, s
    return seen


def flat_four() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    d: object = Tag("d", log)
    s: object = [1, 2, 3, 4]
    match s:
        case [a, b, c, d]:
            pass
    seen = list(log)
    del a, b, c, d, s
    return seen


def starred() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    s: object = [1, 2, 3, 4]
    match s:
        case [a, *b, c]:
            pass
    seen = list(log)
    del a, b, c, s
    return seen


def nested_last() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    s: object = [1, [2, 3]]
    match s:
        case [a, [b, c]]:
            pass
    seen = list(log)
    del a, b, c, s
    return seen


def nested_in_the_middle() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    d: object = Tag("d", log)
    s: object = [1, [2, 3], 4]
    match s:
        case [a, [b, c], d]:
            pass
    seen = list(log)
    del a, b, c, d, s
    return seen


def nested_of_one() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    s: object = [1, 2, [3]]
    match s:
        case [a, b, [c]]:
            pass
    seen = list(log)
    del a, b, c, s
    return seen


def nested_twice() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    d: object = Tag("d", log)
    s: object = [1, [2, [3, 4]]]
    match s:
        case [a, [b, [c, d]]]:
            pass
    seen = list(log)
    del a, b, c, d, s
    return seen


def nested_first() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    s: object = [[1, 2], 3]
    match s:
        case [[a, b], c]:
            pass
    seen = list(log)
    del a, b, c, s
    return seen


def with_a_wildcard_star() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    s: object = [1, 0, 0, [2, 3]]
    match s:
        case [a, *_, [b, c]]:
            pass
    seen = list(log)
    del a, b, c, s
    return seen


def mapping() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    s: object = {"x": 1, "y": 2}
    match s:
        case {"x": a, "y": b}:
            pass
    seen = list(log)
    del a, b, s
    return seen


def mapping_with_the_rest() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    s: object = {"x": 1, "y": 2}
    match s:
        case {"x": a, **b}:
            pass
    seen = list(log)
    del a, b, s
    return seen


def mapping_of_two_with_the_rest() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    s: object = {"x": 1, "y": 2, "z": 3}
    match s:
        case {"x": a, "y": b, **c}:
            pass
    seen = list(log)
    del a, b, c, s
    return seen


def mapping_in_a_sequence() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    s: object = [1, {"x": 2, "y": 3}]
    match s:
        case [a, {"x": b, "y": c}]:
            pass
    seen = list(log)
    del a, b, c, s
    return seen


def class_by_position() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    s: object = Point(1, 2)
    match s:
        case Point(a, b):
            pass
    seen = list(log)
    del a, b, s
    return seen


def class_by_keyword() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    s: object = Point(1, 2)
    match s:
        case Point(y=a, x=b):
            pass
    seen = list(log)
    del a, b, s
    return seen


def class_with_a_sequence() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    s: object = Point(1, [2, 3])
    match s:
        case Point(a, [b, c]):
            pass
    seen = list(log)
    del a, b, c, s
    return seen


def class_with_a_wildcard() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    s: object = [1, Point(2, 0)]
    match s:
        case [a, Point(b, _)]:
            pass
    seen = list(log)
    del a, b, s
    return seen


def as_the_whole() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    s: object = [1, 2]
    match s:
        case [a, b] as c:
            pass
    seen = list(log)
    del a, b, c, s
    return seen


def as_a_part() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    d: object = Tag("d", log)
    s: object = [[1, 2], 3]
    match s:
        case [[a, b] as c, d]:
            pass
    seen = list(log)
    del a, b, c, d, s
    return seen


def as_a_mapping() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    s: object = [{"x": 1, "y": 2}]
    match s:
        case [{"x": a, "y": b} as c]:
            pass
    seen = list(log)
    del a, b, c, s
    return seen


def alternatives(which: int) -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    s: object = [which, 1, 2]
    match s:
        case [1, a, b] | [2, b, a]:               # the second alternative captures b first; the stores are the first's
            pass
    seen = list(log)
    del a, b, s
    return seen


def alternatives_in_a_sequence() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    s: object = [1, {"k": 2}, 3]
    match s:
        case [a, ([b] | {"k": b}), c]:
            pass
    seen = list(log)
    del a, b, c, s
    return seen


def guarded(ok: bool) -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    s: object = [1, [2, 3]]
    match s:
        case [a, [b, c]] if ok:                    # the names are stored before the guard is asked
            log.append("taken")
        case _:
            log.append("not taken")
    seen = list(log)
    del a, b, c, s
    return seen


def not_the_last_case() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    s: object = [1, [2, 3]]
    match s:
        case [a, [b, c]]:
            pass
        case [a, b]:
            pass
        case 0:
            pass
    seen = list(log)
    del a, b, c, s
    return seen


def the_second_case() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    s: object = [1, [2, 3]]
    match s:
        case [a, b, c]:                           # fails: nothing is stored by a case that does not match
            pass
        case [a, [b, c]]:
            pass
    seen = list(log)
    del a, b, c, s
    return seen


def on_two_lines() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    s: object = [1, [2, 3]]
    match s:
        case [a,
              [b, c]]:
            pass
    seen = list(log)
    del a, b, c, s
    return seen


def on_three_lines() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    d: object = Tag("d", log)
    s: object = [1, [2, 3], 4]
    match s:
        case [a,
              [b, c],
              d]:
            pass
    seen = list(log)
    del a, b, c, d, s
    return seen


def mapping_on_two_lines() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    s: object = {"x": 1, "y": 2, "z": 3}
    match s:
        case {"x": a,
              "y": b, **c}:
            pass
    seen = list(log)
    del a, b, c, s
    return seen


def two_mappings() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    s: object = [{"x": 1}, {"y": 2}]
    match s:
        case [{"x": a}, {"y": b}]:
            pass
    seen = list(log)
    del a, b, s
    return seen


def mapping_on_the_second_line() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    s: object = [1, {"x": 2, "y": 3}]
    match s:
        case [a,
              {"x": b, "y": c}]:                  # mapping_in_a_sequence, whose mapping is on the line of the stores
            pass
    seen = list(log)
    del a, b, c, s
    return seen


def class_then_a_name() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    s: object = [1, Point(2, 0), 3]
    match s:
        case [a, Point(b, _), c]:
            pass
    seen = list(log)
    del a, b, c, s
    return seen


def class_on_the_second_line() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    s: object = [1, Point(2, 0), 3]
    match s:
        case [a,
              Point(b, _), c]:
            pass
    seen = list(log)
    del a, b, c, s
    return seen


held: object = None


def a_global() -> list[str]:
    global held
    log: list[str] = []
    a: object = Tag("a", log)
    c: object = Tag("c", log)
    held = Tag("global", log)
    s: object = [1, [2, 3]]
    match s:
        case [a, [held, c]]:
            pass
    seen = list(log)
    held = None
    del a, c, s
    return seen


def a_global_first() -> list[str]:
    global held
    log: list[str] = []
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    held = Tag("global", log)
    s: object = [1, [2, 3]]
    match s:
        case [held, [b, c]]:
            pass
    seen = list(log)
    held = None
    del b, c, s
    return seen


def a_cell() -> list[object]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)

    def read() -> object:
        return b

    s: object = [1, [2, 3]]
    match s:
        case [a, [b, c]]:
            pass
    return [*log, a, read(), c]


def a_cell_last() -> list[object]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)

    def read() -> object:
        return c

    s: object = [1, [2, 3]]
    match s:
        case [a, [b, c]]:
            pass
    return [*log, a, b, read()]


def in_a_generator() -> Generator[list[str]]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    s: object = [1, [2, 3]]
    match s:
        case [a, [b, c]]:
            pass
    yield list(log)
    del a, b, c, s


def in_a_loop() -> list[str]:
    log: list[str] = []
    a: object = Tag("a", log)
    b: object = Tag("b", log)
    c: object = Tag("c", log)
    subjects: list[object] = [[1, [2, 3]], {"x": 4, "y": 5}]
    for s in subjects:
        match s:
            case [a, [b, c]]:
                log.append("a sequence")
            case {"x": a, **b}:
                log.append("a mapping")
    seen = list(log)
    del a, b, c, s
    return seen


def what_was_captured() -> list[object]:
    s: object = [1, [2, 3], {"x": 4, "y": 5}]
    match s:
        case [a, [b, c], {"x": d, **e}]:
            return [a, b, c, d, e]
    return []


for shape in (flat_two, flat_four, starred, nested_last, nested_in_the_middle, nested_of_one, nested_twice, nested_first,
              with_a_wildcard_star, mapping, mapping_with_the_rest, mapping_of_two_with_the_rest, mapping_in_a_sequence,
              class_by_position, class_by_keyword, class_with_a_sequence, class_with_a_wildcard, as_the_whole, as_a_part,
              as_a_mapping, alternatives_in_a_sequence, not_the_last_case, the_second_case, on_two_lines, on_three_lines,
              mapping_on_two_lines, two_mappings, mapping_on_the_second_line, class_then_a_name, class_on_the_second_line,
              a_global, a_global_first, a_cell, a_cell_last, in_a_loop):
    print(shape.__name__, shape())
print("alternatives", alternatives(1), alternatives(2))
print("guarded", guarded(True), guarded(False))
print("in_a_generator", next(in_a_generator()))
print("what_was_captured", what_was_captured())

module_log: list[str] = []
ma: object = Tag("a", module_log)
mb: object = Tag("b", module_log)
mc: object = Tag("c", module_log)
subject: object = [1, [2, 3]]
match subject:
    case [ma, [mb, mc]]:
        pass
print("module", list(module_log))


class Body:
    log: list[str] = []
    ca: object = Tag("a", log)
    cb: object = Tag("b", log)
    cc: object = Tag("c", log)
    s: object = [1, [2, 3]]
    match s:
        case [ca, [cb, cc]]:
            pass
    seen = list(log)


print("class", Body.seen)
