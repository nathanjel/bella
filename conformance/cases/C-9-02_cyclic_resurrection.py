# clause: C-9-02
# spec: section 9
# status: P1
# source: review round 3, finding 1 (a resurrected cyclic group lives on with its weak references already dead)
"""Cyclic resurrection: __del__ keeps the object alive, but the weak reference was cleared first."""
import gc
import weakref

keep: list["Node"] = []


class Node:
    def __init__(self) -> None:
        self.me: Node | None = None

    def __del__(self) -> None:
        keep.append(self)


n = Node()
n.me = n
ref = weakref.ref(n)
del n
gc.collect()
print("cyclic resurrection: old weakref dead =", ref() is None, "object alive =", len(keep) == 1)
print("second collection runs no finalizer again:", gc.collect() >= 0 and len(keep) == 1)
