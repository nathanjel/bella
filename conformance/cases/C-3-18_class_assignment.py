# clause: C-3-18
# spec: section 3
# status: P2+
# source: TODO task 2 (__class__ assignment with CPython's layout rule); spec section 3, "Classes, later"
"""__class__ assignment between layout-compatible classes changes behaviour in place; to an
incompatible layout it raises TypeError (CPython's rule)."""


class A:
    def who(self) -> str:
        return "A"


class B:
    def who(self) -> str:
        return "B"


class Slotted:
    __slots__ = ("x",)


a = A()
a.__class__ = B  # type: ignore[assignment]  # __class__ assignment is the point
print(a.who(), type(a).__name__, isinstance(a, B))
for target in (Slotted, int):
    try:
        a.__class__ = target  # type: ignore[assignment]  # an incompatible layout, on purpose
    except TypeError as exc:
        print(target.__name__, "->", type(exc).__name__)
