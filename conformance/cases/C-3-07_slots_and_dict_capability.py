# clause: C-3-07
# spec: section 3
# status: P1
# source: review round 2, finding 4 and round 3, finding 2 (__dict__ presence is an inherited layout capability)
"""__slots__ = () under an unslotted base keeps __dict__; a fully slotted hierarchy has none."""


class Open:
    pass


class SlotsUnderOpen(Open):
    __slots__ = ()


class Closed:
    __slots__ = ("t",)


class EmptyUnderClosed(Closed):
    __slots__ = ()


class WithDictSlot(Closed):
    __slots__ = ("__dict__",)


def has_dict(obj: object) -> bool:
    return hasattr(obj, "__dict__")


print("open:", has_dict(Open()), "slots-under-open:", has_dict(SlotsUnderOpen()))
print("closed:", has_dict(Closed()), "empty-under-closed:", has_dict(EmptyUnderClosed()),
      "with-dict-slot:", has_dict(WithDictSlot()))
c = Closed()
try:
    c.w = 1  # type: ignore[attr-defined]
except AttributeError as exc:
    print("undeclared on slotted:", type(exc).__name__, exc.name)
try:
    print(c.t)  # type: ignore[attr-defined]  # an unset slot, read on purpose
except AttributeError as exc:
    print("unset slot:", type(exc).__name__, exc.name)
c.t = 5  # type: ignore[attr-defined]  # the slot exists at runtime; the checker cannot see it
print("slot set:", c.t)  # type: ignore[attr-defined]  # as above
