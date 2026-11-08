# clause: C-3-47
# spec: section 3
# source: PEP 563 in 3.15 (codegen_body's SETUP_ANNOTATIONS; Python/bytecodes.c), annotationlib
"""Annotations under `from __future__ import annotations`: a module's and a class body's `__annotations__` are dicts of strings made
when the body runs (SETUP_ANNOTATIONS, which keeps one a body already has), no `__annotate__` exists, functions carry their strings,
and annotationlib answers every format from the strings."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, E741, E742, F601, PLR0133, SLF001
from __future__ import annotations

import annotationlib
import typing as t

x: int = 1
y: str
z: list[int] = []
if x:
    w: dict[str, int] = {}


class C:
    a: int = 1
    b: t.Any = None  # type: ignore[explicit-any]
    c: str
    d = 5

    def f(self, v: int = 2) -> int:
        return self.a + v


class D(C):
    e: float = 2.5

    class Inner:
        g: Undefined  # type: ignore[name-defined]  # noqa: F821  # a string, never looked up


class E:
    __annotations__ = {"preset": "yes"}
    f: int = 1


class F:
    pass


def g(p: int, *args: str, q: C = None, **kw: float) -> list[C]:  # type: ignore[assignment]
    r: int = p
    return [r]  # type: ignore[list-item]


print(__annotations__, C.__annotations__, D.__annotations__, D.Inner.__annotations__, E.__annotations__, "__annotations__" in vars(F), F.__annotations__)
print(C().f(), C.d, D.e, sorted(k for k in vars(D) if not k.startswith("__")), type(C.__annotations__), "__annotate__" in globals(), getattr(C, "__annotate__", "none"), g.__annotations__, C.f.__annotations__, g(1))
print(annotationlib.get_annotations(C), annotationlib.get_annotations(C, format=annotationlib.Format.STRING), annotationlib.get_annotations(D, format=annotationlib.Format.FORWARDREF), annotationlib.get_annotations(g), annotationlib.get_annotations(D.Inner, format=annotationlib.Format.VALUE))
print(C.__dict__["__annotations__"] is C.__annotations__, __annotations__ is globals()["__annotations__"], sorted(__annotations__), sorted(D.__annotations__))
