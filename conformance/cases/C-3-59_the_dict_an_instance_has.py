# clause: C-3-59
# spec: section 3
# status: P1
# source: Objects/typeobject.c (type_new_descriptors, type_ready_managed_dict), Objects/dictobject.c (ensure_nonmanaged_dict, _PyObjectDict_SetItem, store_instance_attr_lock_held), Objects/object.c (_PyObject_GenericSetAttrWithDict)
"""The dict an instance has depends on its class. A program's class, and a subclass of a built-in type of fixed size,
keep the values in the object and share the class's keys: the values go in the keys' order. A subclass of an int or a
tuple, whose size varies, has a dict of its own that shares the keys: the same order, but a delete of a name it has not
joins no keys, and a cleared dict is an ordinary one. A type written in C with its own dict slot, and whatever derives
from it (exceptions, partial, SimpleNamespace, staticmethod, OrderedDict, the io classes), has an ordinary dict: the
values go in the order they were set. Each row of the first part sets b then a on a second instance, after a first set a
then b, and prints the order in which they went."""
# ruff: noqa: E501, B009, B010
# (getattr and setattr with a name written out: the helpers take any object, and the built-ins are the same read and write)
import collections
import functools
import io
import types
from collections.abc import Callable

log: list[str] = []


class V:
    def __init__(self, n: str) -> None:
        self.n = n

    def __del__(self) -> None:
        log.append(self.n)


def took() -> str:
    """What went since the last call, in order."""
    s = " ".join(log) or "-"
    log.clear()
    return s


def order(make: Callable[[], object]) -> str:
    first = make()
    setattr(first, "a", 1)
    setattr(first, "b", 2)
    o = make()
    setattr(o, "b", V("b"))
    setattr(o, "a", V("a"))
    del o
    return took()


def deletes_missing(o: object) -> None:
    try:
        delattr(o, "nope")
    except AttributeError:
        pass


def f() -> None:
    pass


def g() -> None:
    pass


class Plain:
    pass


class E(Exception):
    pass


class E2(E):
    pass


class MyOSError(OSError):
    pass


class Part(functools.partial[None]):
    pass


class NS(types.SimpleNamespace):
    pass


class SM(staticmethod[[], None]):
    pass


class Prop(property):
    pass


class OD(collections.OrderedDict[str, int]):
    pass


class DD(collections.defaultdict[str, int]):
    pass


class DQ(collections.deque[int]):
    pass


class SIO(io.StringIO):
    pass


class BIO(io.BytesIO):
    pass


class MyInt(int):
    pass


class MyTuple(tuple[int, ...]):
    pass


class MyList(list[int]):
    pass


class MyDict(dict[str, int]):
    pass


class MyStr(str):
    pass


class MyFloat(float):
    pass


print("-- the values in the object: the keys' order")
print("a class:", order(Plain), "| subclasses of list, dict, str, float:", order(MyList), order(MyDict), order(MyStr), order(MyFloat))
print("of property, defaultdict, deque:", order(Prop), order(DD), order(DQ))
print("-- a dict of its own that shares the keys")
print("subclasses of int, tuple:", order(MyInt), order(MyTuple))
print("-- an ordinary dict: the order they were set")
setattr(f, "a", 1)
setattr(f, "b", 2)
setattr(g, "b", V("b"))
setattr(g, "a", V("a"))
vars(g).clear()
print("a function, its dict cleared:", took())
print("exceptions:", order(ValueError), order(KeyError), order(StopIteration), order(lambda: ExceptionGroup("m", [ValueError()])))
print("a program's:", order(E), order(E2), order(MyOSError))
print("partial:", order(lambda: functools.partial(f)), order(lambda: Part(f)), "| an lru_cache wrapper:", order(lambda: functools.lru_cache(lambda: 0)))
print("SimpleNamespace:", order(types.SimpleNamespace), order(NS))
print("staticmethod, classmethod:", order(lambda: staticmethod(f)), order(lambda: classmethod(f)), order(lambda: SM(f)))  # type: ignore[arg-type]
print("OrderedDict:", order(collections.OrderedDict), order(OD))
print("StringIO, BytesIO:", order(io.StringIO), order(SIO), order(io.BytesIO), order(BIO))
print("-- a delete of a name it has not, then another instance's q and nope")
kinds: list[tuple[str, Callable[[], object]]] = [("a class", Plain), ("list", MyList), ("int", MyInt), ("tuple", MyTuple), ("an exception", E), ("partial", lambda: functools.partial(f))]
for title, make in kinds:
    deletes_missing(make())
    b = make()
    setattr(b, "q", V("q"))
    setattr(b, "nope", V("nope"))
    del b
    print(title + ":", took())
print("-- its dict cleared, then z and y set")
for title, make in kinds[:4]:
    first = make()
    setattr(first, "y", 1)
    setattr(first, "z", 2)
    o = make()
    setattr(o, "k", 1)
    vars(o).clear()
    setattr(o, "z", V("z"))
    setattr(o, "y", V("y"))
    del o, first
    print(title + ":", took())
print("-- the delete that fails makes the dict")
e = E()
print(len(e.__reduce__()), end=" ")
deletes_missing(e)
print(len(e.__reduce__()))
p = functools.partial(f)
print(p.__reduce__()[2][3], end=" ")
deletes_missing(p)
print(p.__reduce__()[2][3])
print("end")
