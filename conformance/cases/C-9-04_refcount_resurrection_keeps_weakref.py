# clause: C-9-04
# spec: section 9
# status: P1
# source: review round 2, finding 6 (resurrection on the refcount path aborts disposal before weakrefs are cleared)
"""Refcount resurrection: the object lives on AND its weak reference is still alive."""
import weakref

keep: list[Plain] = []


class Plain:
    def __del__(self) -> None:
        keep.append(self)


p = Plain()
ref = weakref.ref(p)
del p
print("refcount resurrection: weakref alive =", ref() is not None, "object alive =", len(keep) == 1)
print("finalizer ran once (PEP 442):", end=" ")
keep.clear()           # drop the last reference again: __del__ must NOT run a second time
print(len(keep) == 0)
