# clause: C-3-65
# spec: section 3
# status: P1
# source: decision S-1 (docs/staging.md section 6); Lib/typing.py 3.15.2 (NamedTupleMeta, _TypedDictMeta: call_annotate_function(..., FORWARDREF))
"""typing's class syntax reads a class body's annotations with FORWARDREF through annotationlib, which re-runs the
compiler-generated __annotate__ against substitute globals: in Bella the second entry point (decision S-1). A NamedTuple
and a TypedDict whose fields name classes bound and not bound yet, a class attribute and a private name; a nested
function's annotations over a cell bound, a cell not yet bound and a global not bound; STRING of the same; and an
annotation that raises, seen in its traceback (the frames to the entry point's, whose line is the annotation's); the code
names and first lines a compiled program finds an entry point by, of a decorated class, a module-level generic function,
a generic method and the module, each read with FORWARDREF."""
import annotationlib
import sys
from collections.abc import Callable
from typing import NamedTuple, NotRequired, TypedDict

Format = annotationlib.Format


class Point(NamedTuple):
    x: int
    y: "float" = 0.0  # noqa: UP037  # a string annotation stays one
    label: str = ""


class Node(NamedTuple):
    value: int
    next: Later | None = None   # noqa: F821  # bound after the class statement
    parent: "Node | None" = None  # noqa: UP037


def shown(annotations: dict[str, object]) -> dict[str, object]:
    return {k: (f"ForwardRef({v.__forward_arg__!r})" if isinstance(v, annotationlib.ForwardRef) else v) for k, v in annotations.items()}


print(Point._fields, Point._field_defaults, Point(1), Point.__annotations__)
print(Node._fields, Node(3), shown(annotationlib.get_annotations(Node, format=Format.FORWARDREF)))
print(annotationlib.get_annotations(Node, format=Format.STRING))


class Movie(TypedDict):
    title: str
    year: NotRequired[int]
    sequel: "Movie | None"  # noqa: UP037
    director: Person            # noqa: F821  # bound after
    __secret: Later             # noqa: F821  # a private name, mangled


print(sorted(Movie.__required_keys__), sorted(Movie.__optional_keys__))
print(shown(annotationlib.get_annotations(Movie, format=Format.FORWARDREF)))
print(annotationlib.get_annotations(Movie, format=Format.STRING))


class Later:
    pass


class Person:
    pass


print(shown(Node.__annotations__), shown(Movie.__annotations__))


def outer() -> tuple[Callable[[object, object, object], object], dict[str, object]]:
    bound = int

    def f(a: bound, b: unbound, c: Missing) -> bound:  # type: ignore[valid-type, name-defined]  # noqa: F821
        return a

    snapshot = annotationlib.get_annotations(f, format=Format.FORWARDREF)
    unbound = str
    return f, snapshot


f, before = outer()
assert callable(f)
print("before:", shown(before))
after = annotationlib.get_annotations(f, format=Format.FORWARDREF)
print("after:", shown(after))
print("string:", annotationlib.get_annotations(f, format=Format.STRING))
print("closure:", f.__annotate__.__code__.co_freevars, len(f.__annotate__.__closure__ or ()))  # type: ignore[union-attr]


class Raising:
    fine: int
    broken: 1 / 0 + x  # type: ignore[valid-type]  # noqa: F821


for fmt in (Format.STRING, Format.FORWARDREF):
    try:
        annotationlib.get_annotations(Raising, format=fmt)
    except ZeroDivisionError as e:
        tb, frames = e.__traceback__, 1
        assert tb is not None
        while tb.tb_next is not None:
            tb, frames = tb.tb_next, frames + 1
        print(fmt.name, type(e).__name__, frames, tb.tb_lineno)


def deco[C](cls: C) -> C:
    return cls


@deco
class Decorated:
    a: Undefined1  # type: ignore[name-defined]  # noqa: F821


def generic[T](a: T, b: Undefined2) -> T:  # type: ignore[name-defined]  # noqa: F821
    return a


class Box[T]:
    def get[U](self, u: U, v: Undefined3) -> T | U:  # type: ignore[name-defined]  # noqa: F821
        raise NotImplementedError


level: Undefined4 = 0  # type: ignore[name-defined]  # noqa: F821
# what a compiled program finds an entry point by: the code's qualified name and first line (a decorated class's is its
# first decorator's, a module-level generic function's annotate is __annotate__ alone)
module = sys.modules[__name__]
for owner in (Decorated, generic, Box.get, module):
    code = owner.__annotate__.__code__  # type: ignore[union-attr]
    print(code.co_qualname, code.co_firstlineno, code.co_freevars, shown(annotationlib.get_annotations(owner, format=Format.FORWARDREF)))
