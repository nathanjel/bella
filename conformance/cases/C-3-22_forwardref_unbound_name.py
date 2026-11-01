# clause: C-3-22
# spec: section 3
# status: P2+
# expect: FORWARDREF
# source: Gate 0 task 5 (review log D-5): FORWARDREF with a name not bound yet needs CPython's __code__ fallback
"""FORWARDREF where a name is not bound yet, which spec section 3 keeps [P2+] (review log D-5):
a dataclass whose field names its own class, which dataclasses reads in the FORWARDREF format
before the class statement binds the name, and get_annotations on a function annotated with a
name defined later. CPython answers with ForwardRef objects built by re-running the annotate
function's code with substitute globals; phase 1 must refuse with the milestone's name."""
import annotationlib
import dataclasses


@dataclasses.dataclass
class Node:
    value: int
    next: Node | None = None


n = Node(1)
n.next = n
print(n, [f.name for f in dataclasses.fields(Node)])


def link(a: Later) -> None:
    pass


refs = annotationlib.get_annotations(link, format=annotationlib.Format.FORWARDREF)
print({k: v.__forward_arg__ if isinstance(v, annotationlib.ForwardRef) else v for k, v in refs.items()})


class Later:
    pass
