# clause: C-3-11
# spec: section 3
# status: P1
# source: review 2026-11-01 gemini-4-argon-high, bug 2.1.1 (a plain class attribute whose own class gains __get__)
"""A plain object stored as a class attribute becomes a descriptor when its own class gains
__get__, without any change to the class that holds it; later reads go through __get__."""


class D:
    pass


def late_get(self: D, obj: object, owner: object = None) -> int:
    return 99


d = D()


class Holder:
    x = d


h = Holder()
print(h.x is d)
D.__get__ = late_get  # type: ignore[attr-defined]
print(h.x)
del D.__get__  # type: ignore[attr-defined]
print(h.x is d)
