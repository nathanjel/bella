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
first.z = 3
print("shared write visible:", second.z)
second.w = 4
print("shared both ways:", first.w, vars(first) is vars(second))
del first.z
print("shared delete visible:", not hasattr(second, "z"))
