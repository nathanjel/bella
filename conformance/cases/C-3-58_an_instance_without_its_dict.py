# clause: C-3-58
# spec: section 3
# status: P1
# source: Objects/typeobject.c (subtype_setdict), Objects/dictobject.c (_PyObject_SetManagedDict, set_dict_inline_values, _PyObject_MaterializeManagedDict, ensure_managed_dict), Objects/object.c (_PyObject_GenericGetAttrWithDict, _PyObject_GenericSetAttrWithDict)
"""An instance without its dict: `del obj.__dict__` leaves the object with none, and what is asked of it next decides
what it gets. A plain read that reaches the instance gives it an ordinary dict, whose values go in the order they were
set; a write, a delete or its __dict__ gives it one that shares the class's keys, whose values go in the keys' order;
what the class answers alone (a data descriptor, a slot, a special method) gives it none yet. The instance of an int's
or a tuple's subclass, whose dict is not kept in the object, gets the sharing one whatever comes first. Each row sets z
then y on an object whose class has the keys y, z, and prints the order in which they went. A method call as the first
thing asked is not here: deviation D-23."""
# ruff: noqa: E501, B009, B010
# (getattr and setattr with a name written out: the helpers take any object, and the built-ins are the same read and write)
import copy
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


def failed(f: Callable[[], object]) -> str:
    try:
        f()
    except Exception as e:
        return type(e).__name__
    return "no error"


class Data:
    def __get__(self, obj: object, cls: type | None = None) -> int:
        return 1

    def __set__(self, obj: object, value: int) -> None:
        pass


class NonData:
    def __get__(self, obj: object, cls: type | None = None) -> int:
        return 2


class C:
    y: object
    z: object
    cv = 10
    data = Data()
    nondata = NonData()

    def m(self) -> int:
        return 1

    @property
    def prop(self) -> int:
        return 3

    def __len__(self) -> int:
        return 0


class Slot:
    __slots__ = ("slot", "__dict__")
    slot: int


class Hook:
    cv = 10

    def m(self) -> int:
        return 1

    def __getattr__(self, name: str) -> int:
        raise AttributeError(name)


def keys_of[T](make: Callable[[], T]) -> None:
    first = make()
    setattr(first, "y", 1)
    setattr(first, "z", 2)


def after[T](make: Callable[[], T], touch: Callable[[T], object]) -> str:
    o = make()
    delattr(o, "__dict__")
    touch(o)
    setattr(o, "z", V("z"))
    setattr(o, "y", V("y"))
    del o
    return took()


def read_cv(o: C) -> object:
    return o.cv


def reads_slot(o: Slot) -> str:
    try:
        return str(o.slot)
    except AttributeError:
        return "AttributeError"


def reads_missing(o: object) -> str:
    try:
        return str(getattr(o, "nope"))
    except AttributeError:
        return "AttributeError"


def deletes_missing(o: object) -> str:
    try:
        delattr(o, "nope")
    except AttributeError:
        return "AttributeError"
    return "no error"


keys_of(C)
print("-- what the del lets go of")
o = C()
o.z = V("z")
o.y = V("y")
del o.__dict__
print("its values:", took(), vars(o), hasattr(o, "z"))
o = C()
o.z = V("z")
o.y = V("y")
held = vars(o)
del o.__dict__
print("a dict somebody holds:", took(), list(held), vars(o) is held, vars(o))
del held
print("  let go:", took())
o = C()
o.z = V("z")
o.y = V("y")
print("a dict nobody holds:", list(vars(o)), end=" ")
del o.__dict__
print(took())
o = C()
o.__dict__ = {"z": V("z"), "y": V("y")}
del o.__dict__
print("a dict it was given:", took())
del o.__dict__
del o.__dict__
print("again, with none:", vars(o))
del o.__dict__
o.__dict__ = {"k": 1}
print("one given after:", vars(o))
del o
print("-- what is asked first: nothing, or what only the class answers")
print("nothing:", after(C, lambda o: None))
print("a data descriptor:", after(C, lambda o: o.data))
print("a property:", after(C, lambda o: o.prop))
print("a data descriptor set:", after(C, lambda o: setattr(o, "data", 1)))
print("its class:", after(C, lambda o: o.__class__))
print("a special method:", after(C, lambda o: len(o)))
print("repr, ==, hash, isinstance:", after(C, lambda o: (len(repr(o)) > 0, o == o, hash(o) == hash(o), isinstance(o, C))))
keys_of(Slot)
print("a slot:", after(Slot, reads_slot), after(Slot, lambda o: setattr(o, "slot", 1)))
print("-- a plain read that reaches the instance")
print("a class attribute:", after(C, lambda o: o.cv))
print("a method not called:", after(C, lambda o: o.m))
print("a non-data descriptor:", after(C, lambda o: o.nondata))
print("a name it has not:", after(C, reads_missing))
print("getattr with a default:", after(C, lambda o: getattr(o, "nope", None)))
print("hasattr:", after(C, lambda o: hasattr(o, "nope")))
print("a copy:", after(C, lambda o: type(copy.copy(o)).__name__))
print("the same read at one place:", after(C, read_cv), after(C, read_cv), after(C, read_cv))
print("-- a write, a delete, its __dict__")
print("a write:", after(C, lambda o: setattr(o, "q", 1)))
print("a delete that fails:", after(C, deletes_missing))
print("its __dict__:", after(C, lambda o: o.__dict__))
print("vars:", after(C, lambda o: vars(o)))
print("dir:", after(C, lambda o: len(dir(o)) > 0))
print("another dict given:", after(C, lambda o: setattr(o, "__dict__", {})))
print("-- the order of its names is its own either way")
o = C()
del o.__dict__
o.z = V("z")
o.y = V("y")
print(list(vars(o)), end=" ")
del o
print(took())
o = C()
del o.__dict__
print(o.cv, end=" ")
o.z = V("z")
o.y = V("y")
print(list(vars(o)), end=" ")
del o
print(took())


class Looker(V):
    """A value whose finaliser asks something of the object that held it."""

    def __init__(self, n: str, target: list[C], write: bool) -> None:
        super().__init__(n)
        self.target = target
        self.write = write

    def __del__(self) -> None:
        log.append(self.n)
        t = self.target[0]
        if self.write:
            setattr(t, "w", 5)
        else:
            log.append("sees " + str(getattr(t, "z", None)))


print("-- a finaliser that asks while the del is letting go")
for write in (False, True):
    o = C()
    box = [o]
    o.z = V("z")
    o.y = Looker("y", box, write)
    del o.__dict__
    seen = took()
    o.z = V("z2")
    o.y = V("y2")
    names = list(vars(o))
    box.clear()
    del o
    print("it wrote:" if write else "it read:", seen, names, took())


class Known:
    """Its attributes are the ones the class's own code sets: the keys are theirs, sorted."""

    def __init__(self) -> None:
        self.b = V("b")
        self.a = V("a")


print("-- a class whose attributes its own code sets")
k = Known()
del k.__dict__
print(took(), hasattr(k, "a"), end=" ")
k.b = V("b2")
k.a = V("a2")
print(list(vars(k)), end=" ")
del k
print(took())
k = Known()
del k.__dict__
k.b = V("b3")
k.a = V("a3")
print(took(), k.a.n, list(vars(k)), end=" ")
del k
print(took())
k = Known()
print(k.a.n, k.b.n, end=" ")
del k
print(took())


class MyList(list[int]):
    cv = 10


class MyDict(dict[str, int]):
    cv = 10


class MyStr(str):
    cv = 10


class MyFloat(float):
    cv = 10


class MyComplex(complex):
    cv = 10


class MyInt(int):
    cv = 10


class MyTuple(tuple[int, ...]):
    cv = 10


print("-- subclasses of built-in types: nothing first, a read first, a write first")
kinds: list[Callable[[], object]] = [MyList, MyDict, MyStr, MyFloat, MyComplex, MyInt, MyTuple]
for make in kinds:
    keys_of(make)
    print(type(make()).__name__ + ":", after(make, lambda o: None), "|", after(make, lambda o: getattr(o, "cv")), "|", after(make, lambda o: setattr(o, "q", 1)))
print("-- a class with __getattr__: its method call is a read")
keys_of(Hook)
print("__getattr__:", after(Hook, lambda o: o.cv), "|", after(Hook, lambda o: o.m()), "|", after(Hook, lambda o: setattr(o, "q", 1)), "|", after(Hook, lambda o: None))


class E(Exception):
    pass


class NoDict:
    __slots__ = ("a",)


print("-- what has no dict, and what never loses it")
print(failed(lambda: delattr(E(), "__dict__")), failed(lambda: delattr(NoDict(), "__dict__")), failed(lambda: delattr(C, "__dict__")), failed(lambda: delattr(1, "__dict__")), failed(lambda: delattr(object(), "__dict__")))
print("end")
