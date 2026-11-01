# clause: C-9-01
# spec: section 9
# status: P1
# source: review round 3, finding 1 (PEP 442: weak references are cleared before finalisers run on a cycle)
"""Cyclic disposal: the weak-reference callback fires BEFORE __del__ (PEP 442)."""
import gc
import weakref

order: list[str] = []


class Node:
    def __init__(self) -> None:
        self.me: Node | None = None

    def __del__(self) -> None:
        order.append("finalizer")


def callback(_ref: "weakref.ReferenceType[Node]") -> None:
    order.append("weakref")


n = Node()
n.me = n                      # self-cycle: only the collector can free it
ref = weakref.ref(n, callback)
del n
gc.collect()
print("cyclic disposal order:", order)
print("weakref dead:", ref() is None)
