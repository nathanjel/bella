# clause: C-3-22
# spec: section 3
# status: P1
# source: decision S-1 (2026-11-01, docs/staging.md): FORWARDREF and STRING with names not bound yet
"""FORWARDREF and STRING where annotationlib re-runs an annotate function against substitute
globals and cells, which Bella answers with the compiler-generated second entry point (decision
S-1). A dataclass whose field names its own class, read before the class statement binds it; a
function annotated with a name defined later; a class body naming a class attribute and an
unbound global; a closure variable read before and after it is bound; private names; module
annotations, some under a condition not taken; an annotation with an effect, which FORWARDREF
evaluates; and annotations whose evaluation raises, with the exception's arguments."""
import annotationlib
import dataclasses
import sys
import typing
from annotationlib import Format, ForwardRef, type_repr

effects: list[str] = []


def note(label: str) -> type:
    effects.append(label)
    return int


def show(value: object) -> str:
    """Like type_repr, through generic aliases and unions, with ForwardRef shown without its owner
    (whose repr is an address)."""
    if isinstance(value, ForwardRef):
        return f"ForwardRef({value.__forward_arg__!r}, is_class={value.__forward_is_class__})"
    origin, args = typing.get_origin(value), typing.get_args(value)
    if origin is typing.Union:
        return " | ".join(show(a) for a in args)
    if origin is not None and args:
        return f"{type_repr(origin)}[{', '.join(show(a) for a in args)}]"
    return value if isinstance(value, str) else type_repr(value)


def report(label: str, obj: object, fmt: Format) -> None:
    try:
        ann = annotationlib.get_annotations(obj, format=fmt)
    except Exception as exc:  # noqa: BLE001  # the exception and its arguments are the observable
        print(label, fmt.name, "raises", type(exc).__name__, exc.args)
    else:
        print(label, fmt.name, {k: show(v) for k, v in ann.items()})


@dataclasses.dataclass
class Node:
    value: int
    next: Node | None = None


n = Node(1)
n.next = n
print(n, [(f.name, show(f.type)) for f in dataclasses.fields(Node)])


def link(a: Later, b: list[Later] | None, c: Later.attr, d: note("link") | Missing) -> Later:  # type: ignore[name-defined, valid-type, empty-body]  # noqa: F821  # unbound on purpose
    pass


class Shelf:
    size = int
    __secret: list[Unbound]  # type: ignore[name-defined]  # noqa: F821  # a private name, unbound
    width: size  # type: ignore[valid-type]  # a class attribute
    depth: Later


def outer() -> object:
    def inner(a: T, b: list[T]) -> T:  # type: ignore[valid-type]  # read before T is bound
        return a

    for fmt in (Format.FORWARDREF, Format.STRING):
        report("inner before T", inner, fmt)
    T = int
    report("inner after T", inner, Format.FORWARDREF)
    return inner


outer()
for fmt in (Format.FORWARDREF, Format.STRING):
    report("link", link, fmt)
    report("Shelf", Shelf, fmt)
print("effects", effects)


def raising(a: {}["missing"], b: Later) -> None:  # type: ignore[valid-type]  # noqa: UP037, F821  # a dict lookup that raises KeyError
    pass


for fmt in (Format.VALUE, Format.FORWARDREF, Format.STRING):
    report("raising", raising, fmt)

flag = False
module_first: Later
if flag:
    module_skipped: int
module_last: list[Unbound]  # type: ignore[name-defined]  # noqa: F821  # unbound on purpose


class Later:
    attr = int


for fmt in (Format.FORWARDREF, Format.STRING):
    report("module", sys.modules[__name__], fmt)
report("link once Later exists", link, Format.FORWARDREF)
