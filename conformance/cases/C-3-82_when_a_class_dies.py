# clause: C-3-82
# spec: section 3 (classes; section 9: a class is reference-counted like any other object)
# status: P1
# source: Objects/typeobject.c (type_traverse, type_clear, type_dealloc, type_new_set_classdictcell), Objects/descrobject.c
#         (mappingproxy_getitem, mappingproxy_get, mappingproxy_contains, mappingproxy_len, mappingproxy_traverse)
"""When a class dies, and what dies with it. A class's MRO holds the class, so it dies in a collection once nothing else
holds it, its dict cleared in its order and what only the dict held dying with it; its objects, its subclasses and a
method's `__class__` cell keep it. A mappingproxy of the class's dict (`C.__dict__`, and the cell an annotation scope
reads the class's names from) holds the dict and not the class: it outlives the class, and shows the dict as the class's
death left it, empty. Each collection's deaths and callbacks are printed sorted, since their order is not defined (D-04)."""
import gc
import weakref
from annotationlib import Format

deaths: list[str] = []


class Marker:
    def __init__(self, name: str) -> None:
        self.name = name

    def __del__(self) -> None:
        deaths.append(self.name)


def collect(label: str) -> None:
    gc.collect()
    print(label, sorted(deaths))
    deaths.clear()


class A:
    pass


def plain(name: str) -> type:
    """A class whose dict names nothing of it: no method, no slot, no dict or weakref descriptor of its own."""
    class B(A):
        x = Marker(name)
    return B


def named(name: str) -> type:
    """A class a method's `__class__` cell names (its `super()`): its dict holds it."""
    class D(A):
        x = Marker(name)

        def me(self) -> str:
            return super().__repr__()
    return D


def dropped() -> None:
    plain("dropped.x")
    collect("dropped")


def instance() -> None:
    obj = plain("instance.x")()
    collect("instance kept")
    del obj
    collect("instance gone")


def subclass() -> None:
    base = plain("subclass.base.x")

    class Sub(base):  # type: ignore[valid-type, misc]
        y = Marker("subclass.y")
    del base
    collect("subclass kept")
    print("subclass base", [k.__name__ for k in Sub.__mro__])
    del Sub
    collect("subclass gone")


def callback() -> None:
    def said(ref: object) -> None:
        deaths.append("callback")
    ref = weakref.ref(plain("callback.x"), said)
    collect("callback")
    print("callback ref", ref() is None)


def proxy_plain() -> None:
    p = plain("proxy.x").__dict__
    print("proxy before", sorted(p), "x" in p)
    collect("proxy plain")
    print("proxy len", len(p), "keys", sorted(p), "in", "x" in p, "__module__" in p)
    print("proxy get", p.get("x"), p.get("x", "default"))
    try:
        p["x"]
    except KeyError as e:
        print("proxy getitem", type(e).__name__, e.args)
    print("proxy repr", repr(p), "eq", p == {}, "copy", p.copy())
    print("proxy views", list(p.keys()), list(p.values()), list(p.items()))
    print("proxy or", p | {"k": 1}, {"k": 1} | p)
    del p
    collect("proxy plain gone")


def proxy_named() -> None:
    p = named("named.x").__dict__
    collect("proxy named")
    print("proxy named", sorted(p), len(p))
    del p
    collect("proxy named gone")


def proxy_iterator() -> None:
    p = plain("iterator.x").__dict__
    it = iter(p)
    first = next(it)
    values = p.values()
    items = p.items()
    del p
    collect("iterator")
    print("iterator first", first, "values", len(values), list(values), "items", len(items))
    try:
        print("iterator next", next(it))
    except RuntimeError as e:
        print("iterator next", type(e).__name__)
    except StopIteration:
        print("iterator next", "StopIteration")


def annotated() -> None:
    class C(A):
        T = int
        x = Marker("annotated.x")
        y: T  # type: ignore[valid-type]
    annotate = C.__annotate__
    assert annotate is not None
    print("annotated before", annotate(Format.VALUE))
    del C
    collect("annotated")
    try:
        print("annotated after", annotate(Format.VALUE))
    except NameError as e:
        print("annotated after", type(e).__name__, e.name)
    del annotate
    collect("annotated gone")


gc.disable()
dropped()
instance()
subclass()
callback()
proxy_plain()
proxy_named()
proxy_iterator()
annotated()
collect("end")
