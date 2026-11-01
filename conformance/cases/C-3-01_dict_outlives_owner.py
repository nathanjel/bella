# clause: C-3-01
# spec: section 3
# status: P1
# source: review round 3, finding 2 (an exposed instance dictionary outlives its owner)
"""vars(obj) keeps working after obj is finalised; the owner is finalised on schedule."""


class Example:
    def __init__(self) -> None:
        self.y = 2
        self.x = 1

    def __del__(self) -> None:
        print("owner finalized")


obj = Example()
retained = vars(obj)
print("stable identity:", vars(obj) is retained, "type is dict:", type(retained) is dict)
del obj
print("retained after del:", list(retained.items()))
