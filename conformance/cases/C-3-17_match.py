# clause: C-3-17
# spec: section 3
# status: P1
# source: TODO task 2 (match); spec section 3 lists match as [P1]
"""Structural pattern matching: class patterns with __match_args__ and keywords, guards,
sequence patterns with a star (str is not a sequence here), mapping patterns with **rest (extra
keys ignored), or-patterns with as, value patterns, capture and wildcard, in order."""
import enum


class Color(enum.Enum):
    RED = "red"
    BLUE = "blue"


class Point:
    __match_args__ = ("x", "y")

    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


def classify(obj: object) -> str:
    match obj:
        case Point(0, 0):
            return "origin"
        case Point(x, 0) if x > 0:
            return f"positive x-axis at {x}"
        case Point(x=x, y=y):
            return f"point {x},{y}"
        case Color.RED:
            return "red"
        case [1, *rest]:
            return f"starts with 1, rest {rest}"
        case [_, _]:
            return "a pair"
        case {"kind": "user", **extra}:
            return f"user with {sorted(map(str, extra))}"
        case {"kind": kind}:
            return f"kind {kind}"
        case int() | float() as n if n < 0:
            return f"negative {n}"
        case str(s):
            return f"string {s!r}"
        case None:
            return "none"
        case _:
            return f"other {type(obj).__name__}"


for value in (Point(0, 0), Point(3, 0), Point(-1, 2), Color.RED, Color.BLUE, [1, 2, 3], (1,), [7, 8], "ab",
              {"kind": "user", "id": 7, "name": "a"}, {"kind": "group", "size": 2}, -2, -1.5, 4, None):
    print(classify(value))
