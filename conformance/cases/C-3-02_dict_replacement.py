# clause: C-3-02
# spec: section 3
# status: P1
# source: review round 2, finding 4 and round 3, finding 2 (obj.__dict__ = d; the old dict stays usable)
"""__dict__ replacement: writes go through the new dict, the old dict is independently usable."""


class Example:
    def __init__(self) -> None:
        self.x = 1


obj = Example()
old = obj.__dict__
replacement: dict[str, int] = {"y": 2}
obj.__dict__ = replacement
print("new attr visible:", obj.y)
print("old attr gone:", not hasattr(obj, "x"))
print("vars is replacement:", vars(obj) is replacement)
replacement["z"] = 3
print("write through replacement:", obj.z)
print("old dict still usable:", list(old.items()))
try:
    obj.__dict__ = 5  # type: ignore[assignment]
except TypeError as exc:
    print("non-dict rejected:", type(exc).__name__)
print("class __dict__ is read-only:", type(Example.__dict__).__name__)
try:
    Example.__dict__["x"] = 1  # type: ignore[index]
except TypeError as exc:
    print("write through class __dict__ rejected:", type(exc).__name__)
