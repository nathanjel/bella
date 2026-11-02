# clause: C-3-26
# spec: section 3
# status: P1
# source: Gate 0 task 4, step A2 (the census of docs/measurements.md, 2026-11-02)
"""Function objects: names and qualified names, docstrings as CPython 3.13+ cleans them,
lambdas, decorators evaluated before the defaults and applied bottom-up, PEP 649 annotations
evaluated lazily in the defining scope, and desugared statements that a program's own
binding of `type`, `iter`, `format`, `str`, `repr` or `slice` cannot change."""
from collections.abc import Callable
from typing import Protocol

trace: list[str] = []


class Unary(Protocol):
    __name__: str
    __qualname__: str

    def __call__(self, x: int = ...) -> int: ...


def note(name: str) -> Callable[[Unary], Unary]:
    trace.append("evaluate " + name)

    def apply(fn: Unary) -> Unary:
        trace.append("apply " + name + " to " + fn.__name__)
        return fn
    return apply


def default(value: int) -> int:
    trace.append("default")
    return value


@note("outer")
@note("inner")
def decorated(x: int = default(1)) -> int:
    """First line.
        Indented more.
    Back at the margin.

	A tab."""
    return x


print(trace)
trace.clear()
print(decorated.__name__, decorated.__qualname__, decorated.__module__, repr(decorated.__doc__))


def outer() -> Callable[[int], Callable[[], int]]:
    def middle(n: int) -> Callable[[], int]:
        return lambda: n * 2
    return middle


inner = outer()(21)
print(inner(), inner.__name__, inner.__qualname__, inner.__doc__, inner.__defaults__)
class Power(Protocol):
    __qualname__: str

    def __call__(self, n: int, power: int = ...) -> int: ...


square: Power = lambda n, power=2: n ** power   # noqa: E731  # a lambda bound to a name is the point
print(square(3), square(2, power=3), square.__qualname__)


def no_doc() -> None:
    f"not a docstring {1}"   # noqa: B021  # an f-string is not a docstring


print(no_doc.__doc__, no_doc.__annotate__ is not None, no_doc.__annotations__)


# annotations: lazy, in the defining scope, CPython's key order; the format parameter is hidden
def annotated(p: int, /, a: Later, *args: str, k: format, **kw: bytes) -> list[int]:  # type: ignore[valid-type]  # format is the builtin
    return []


class Later:
    pass


ann = annotated.__annotations__
print(list(ann), ann["a"], ann["k"] is format, ann["return"])
annotate = annotated.__annotate__
assert annotate is not None
print(annotate(1) == ann, annotate.__qualname__)   # type: ignore[arg-type]  # the generated function takes an int
try:
    annotate(3)                                     # type: ignore[arg-type]  # above VALUE_WITH_FAKE_GLOBALS
except NotImplementedError as exc:
    print("NotImplementedError", exc.args)


def forward(x: "Missing") -> None:   # type: ignore[name-defined]  # noqa: UP037, F821  # a string stays a string
    pass


def unbound(x: Missing) -> None:     # type: ignore[name-defined]  # noqa: F821  # evaluated only when read
    pass


print(forward.__annotations__)
try:
    _ = unbound.__annotations__
except NameError as exc:
    print("NameError", exc.name)


# hygiene: the desugarings call the builtins, whatever the program binds to their names
class Manager:
    def __enter__(self) -> str:
        return "entered"

    def __exit__(self, *exc: object) -> None:
        trace.append("exit")


def shadowing(type: str, iter: str, format: str, str: int, repr: int) -> list[object]:
    with Manager() as m:
        pass
    squares = [n * n for n in range(3)]
    return [m, squares, f"{type!r:>8}|{iter!s}|{format}", trace]


print(shadowing("t", "i", "f", 1, 2))
trace.clear()
slice = None   # noqa: A001  # shadows the builtin; a[1:2] must not call it
print([1, 2, 3][1:])
