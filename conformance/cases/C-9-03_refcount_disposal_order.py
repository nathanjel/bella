# clause: C-9-03
# spec: section 9
# status: P1
# source: review round 2, finding 6 (the refcount path differs from the cyclic path: __del__ first)
"""Refcount-triggered disposal: __del__ runs BEFORE the weak-reference callback, synchronously."""
import weakref

order: list[str] = []


class Plain:
    def __del__(self) -> None:
        order.append("finalizer")


def callback(_ref: weakref.ReferenceType[Plain]) -> None:
    order.append("weakref")


p = Plain()
ref = weakref.ref(p, callback)
order.append("before del")
del p
order.append("after del")
print("refcount disposal order:", order)
print("weakref dead:", ref() is None)
