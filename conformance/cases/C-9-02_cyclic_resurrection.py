# clause: C-9-02
# spec: section 9
# status: P1
# source: review round 3, finding 1; premise revised for CPython 3.15 on 2026-11-01 (DECISIONS, finding 5): a weak
#         reference without a callback is cleared only when the object is really freed, so it survives resurrection
"""Cyclic resurrection: __del__ keeps the object alive, and its callback-less weak reference stays alive with it."""
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
