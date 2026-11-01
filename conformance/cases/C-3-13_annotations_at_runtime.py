# clause: C-3-13
# spec: section 3
# status: P1
# source: review log D-5 (2026-11-01): annotations at runtime in the VALUE, FORWARDREF and STRING formats
"""Annotations a compiled program reads at runtime (review log D-5): get_annotations in the VALUE
format, FORWARDREF when every name resolves, and STRING, and the definition-time code that reads
them while the module runs (spec section 8): @dataclass, NamedTuple, TypedDict and
singledispatch registration by annotation. What needs CPython's __code__ fallback (FORWARDREF
with an undefined name, ForwardRef.evaluate) is [P2+] and not exercised here."""
import annotationlib
import dataclasses
import functools
import typing
from annotationlib import Format, type_repr


class Point:
    x: int
    y: "float"  # noqa: UP037  # a string annotation stays a string in every format
    tags: list[str]


def scale(p: Point, factor: float = 2.0) -> dict[str, int]:
    return {"x": p.x}


def show(value: object) -> str:
    return value if isinstance(value, str) else type_repr(value)


for obj in (Point, scale):
    for fmt in (Format.VALUE, Format.FORWARDREF, Format.STRING):
        ann = annotationlib.get_annotations(obj, format=fmt)
        print(obj.__name__, fmt.name, {k: show(v) for k, v in ann.items()})
print("__annotations__ is VALUE:", Point.__annotations__ == annotationlib.get_annotations(Point))
annotate = Point.__annotate__
assert annotate is not None
print("__annotate__(VALUE):", sorted(annotate(Format.VALUE)))


@dataclasses.dataclass
class Item:
    name: str
    qty: int = 1
    tags: list[str] = dataclasses.field(default_factory=list)


print([(f.name, show(f.type), f.default is dataclasses.MISSING) for f in dataclasses.fields(Item)])
print(Item("bolt"), Item("nut", 3, ["m4"]))


class Pair(typing.NamedTuple):
    left: int
    right: str = "r"


print(Pair._fields, Pair._field_defaults, Pair(1), {k: show(v) for k, v in annotationlib.get_annotations(Pair).items()})


class Movie(typing.TypedDict):
    title: str
    year: int


print(sorted(Movie.__required_keys__), {k: show(v) for k, v in annotationlib.get_annotations(Movie).items()})


@functools.singledispatch
def describe(arg: object) -> str:
    return "object"


@describe.register
def _(arg: int) -> str:
    return "int"


@describe.register
def _(arg: list) -> str:  # type: ignore[type-arg]  # dispatch needs a class, not list[int]
    return "list"


print(describe(1), describe([1]), describe("s"), describe(1.5))
