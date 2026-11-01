# clause: C-3-21
# spec: section 3
# status: P1
# source: Gate 0 task 5 (review log D-5): what a compiler-generated __annotate__ answers when called directly
"""A compiler-generated __annotate__ answers VALUE and VALUE_WITH_FAKE_GLOBALS and raises
NotImplementedError for FORWARDREF and STRING, as CPython's does. annotationlib then answers
STRING after evaluating the annotations once with the real globals (the probe in
call_annotate_function, whose effects are visible), and FORWARDREF from __annotations__ when
every name resolves. STRING forms of common shapes, of a closure variable and of a module's
annotations; an annotation whose evaluation raises raises in every format."""
import annotationlib
import sys
import typing
from annotationlib import Format, type_repr

events: list[str] = []


def note(label: str) -> type:
    events.append(label)
    return int


class Box:
    size: int
    label: "str"  # noqa: UP037  # a string annotation stays a string in every format
    pair: tuple[int, str]


def f(a: int | None, b: list["Box"], c: typing.Callable[[int], str], *args: int,  # noqa: UP037  # quoted on purpose
      d: typing.Literal[1, "a"] = 1, **kw: float) -> None:
    pass


def side(x: note("ann")) -> None:  # type: ignore[valid-type]  # an annotation with an effect
    pass


def broken(x: 1 / 0) -> None:  # type: ignore[valid-type]  # evaluating it raises
    pass


def outer() -> object:
    T = int

    def inner(x: T, y: list[T]) -> T:  # type: ignore[valid-type]  # a closure variable
        return x

    return inner


module_level: int = 1


def show(ann: dict[str, object]) -> dict[str, str]:
    return {k: v if isinstance(v, str) else type_repr(v) for k, v in ann.items()}


for owner in (Box, f):
    annotate = owner.__annotate__
    assert annotate is not None
    for fmt in (Format.VALUE, Format.VALUE_WITH_FAKE_GLOBALS, Format.FORWARDREF, Format.STRING):
        try:
            print(owner.__name__, fmt.name, show(annotate(fmt)))
        except NotImplementedError as exc:
            print(owner.__name__, fmt.name, "raises", type(exc).__name__)

for obj in (Box, f, outer(), sys.modules[__name__]):
    print(getattr(obj, "__qualname__", "module"), annotationlib.get_annotations(obj, format=Format.STRING))

print("STRING", annotationlib.get_annotations(side, format=Format.STRING), events)
print("VALUE", show(annotationlib.get_annotations(side)), events)
print("FORWARDREF", show(annotationlib.get_annotations(side, format=Format.FORWARDREF)), events)
print("FORWARDREF", show(annotationlib.get_annotations(f, format=Format.FORWARDREF)))
for fmt in (Format.VALUE, Format.FORWARDREF, Format.STRING):
    try:
        annotationlib.get_annotations(broken, format=fmt)
    except ZeroDivisionError as exc:
        print("broken", fmt.name, "raises", type(exc).__name__)
