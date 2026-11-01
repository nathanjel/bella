# clause: C-3-12
# spec: section 3
# status: P1
# source: review 2026-11-01 gemini-4-argon-high, bug 2.1.4 (review log RL-23, decision D-1)
#         a class that dies must not lend its cache entries to a class created later at its address
"""One attribute read, at one call site, sees a sequence of classes that each die before the next
one is created. CPython 3.15.2 gives the next class the dead class's memory (measured with id(),
which a case must not print). Each read must still follow the new class's own layout and lookup
kind: second slot, first slot, class attribute, property, __getattr__, instance dictionary."""
import gc
import weakref


def make(kind: int) -> type:
    """A new class object on every call; a class statement whose body uses no runtime values."""
    if kind == 0:
        class TwoSlots:
            __slots__ = ("a", "x")

            def __init__(self) -> None:
                self.a = "a"
                self.x = "second slot"
        return TwoSlots
    if kind == 1:
        class OneSlot:
            __slots__ = ("x",)

            def __init__(self) -> None:
                self.x = "first slot"
        return OneSlot
    if kind == 2:
        class ClassAttribute:
            x = "class attribute"
        return ClassAttribute
    if kind == 3:
        class Property:
            @property
            def x(self) -> str:
                return "property"
        return Property
    if kind == 4:
        class Hook:
            def __getattr__(self, name: str) -> str:
                return "__getattr__ " + name
        return Hook

    class Plain:
        def __init__(self) -> None:
            self.x = "instance dictionary"
    return Plain


def read(obj: object) -> object:
    return obj.x  # type: ignore[attr-defined]  # the one call site every class below goes through


for round_ in range(2):
    for kind in range(6):
        cls = make(kind)
        obj = cls()
        print(round_, cls.__name__, read(obj), read(obj))
        ref = weakref.ref(cls)
        del obj, cls
        gc.collect()
        print("  collected:", ref() is None)
