# clause: C-7-06
# spec: section 7
# status: P1
# source: dialect specification section 7, Core data (enum, contextlib, weakref, contextvars, copy, abc, types, reprlib, keyword)
"""Core data modules, part 2."""
import abc
import contextlib
import contextvars
import copy
import enum
import gc
import keyword
import reprlib
import types
import weakref


class Perm(enum.Flag):
    R = enum.auto()
    W = enum.auto()
    X = enum.auto()


class Shade(enum.IntEnum):
    LIGHT = 1
    DARK = 2


print(Perm.R | Perm.W, repr(Perm.R | Perm.X), list(Perm), Perm(3), Perm.W in (Perm.R | Perm.W), Perm(0))
print(Shade.DARK + 1, Shade(1).name, [s.value for s in Shade], Shade["DARK"] is Shade.DARK, repr(Shade.LIGHT))

order: list[str] = []
with contextlib.ExitStack() as stack:
    for name in "abc":
        stack.callback(order.append, name)
print("ExitStack unwinds:", order)
empty: dict[str, int] = {}
with contextlib.suppress(KeyError):
    empty["missing"]  # noqa: B018  # the KeyError suppress swallows
print("suppressed")


@contextlib.contextmanager
def tagged(log: list[str], tag: str):  # type: ignore[no-untyped-def]  # contextmanager's own signature
    log.append(f"enter {tag}")
    try:
        yield tag.upper()
    finally:
        log.append(f"exit {tag}")


log: list[str] = []
with tagged(log, "x") as value:
    log.append(value)
print(log)


class Node:
    pass


cache: weakref.WeakValueDictionary[str, Node] = weakref.WeakValueDictionary()
n = Node()
cache["n"] = n
print("alive:", "n" in cache)
del n
gc.collect()
print("after del:", "n" in cache)

var: contextvars.ContextVar[str] = contextvars.ContextVar("var", default="outer")
token = var.set("inner")
ctx = contextvars.copy_context()
var.reset(token)
print(var.get(), ctx.run(var.get), ctx[var])

nested: dict[str, list[list[int]]] = {"a": [[1], [2, 3]]}
shallow, deep = copy.copy(nested), copy.deepcopy(nested)
nested["a"][1].append(4)  # the inner list is shared by the shallow copy only
print(shallow["a"], deep["a"])


class Shape(abc.ABC):
    @abc.abstractmethod
    def area(self) -> float: ...


try:
    Shape()  # type: ignore[abstract]  # the TypeError is the point
except TypeError as exc:
    print("abstract:", type(exc).__name__)
ns = types.SimpleNamespace(a=1, b=2)
print(ns, ns == types.SimpleNamespace(b=2, a=1))
print(reprlib.repr(list(range(100))), reprlib.repr("x" * 50))
print(keyword.iskeyword("lazy"), keyword.issoftkeyword("lazy"), keyword.iskeyword("match"), keyword.issoftkeyword("match"))
