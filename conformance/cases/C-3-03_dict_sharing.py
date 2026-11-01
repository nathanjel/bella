# clause: C-3-03
# spec: section 3
# status: P1
# source: review round 3, finding 2 (two objects can share one instance dictionary)
"""second.__dict__ = first.__dict__: attribute writes on one are visible on the other."""


class Example:
    pass


first = Example()
second = Example()
second.__dict__ = first.__dict__
first.z = 3  # type: ignore[attr-defined]  # attributes through a shared __dict__ are the point
print("shared write visible:", second.z)  # type: ignore[attr-defined]  # as above
second.w = 4  # type: ignore[attr-defined]  # as above
print("shared both ways:", first.w, vars(first) is vars(second))  # type: ignore[attr-defined]  # as above
del first.z  # type: ignore[attr-defined]  # as above
print("shared delete visible:", not hasattr(second, "z"))
