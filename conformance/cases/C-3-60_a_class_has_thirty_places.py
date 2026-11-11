# clause: C-3-60
# spec: section 3
# status: P1
# source: Objects/dictobject.c (_PyDict_NewKeysForClass, _PyObject_InitInlineValues, insert_split_key, store_instance_attr_lock_held); found by the reference model's Hypothesis machine, 2026-11-11
"""A class whose instances keep their values in them has thirty places for the keys they share. A key takes one, and so
does each instance made while more than one is left, so a class that has made some thirty instances takes one more name
and then none: an instance that stores a name the keys cannot take has an ordinary dict from there on, and its values go
in the order they were set. Names the keys already hold still go in the keys' order, a subclass has places of its own,
and the instance of an int's or a tuple's subclass, which keeps no values in it, takes no place. Each row stores two
values on a last instance and prints the order in which they went."""
# ruff: noqa: E501, B009, B010
# (getattr and setattr with a name written out: the helpers take any object, and the built-ins are the same read and write)
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


def fresh() -> type[object]:
    class K:
        pass
    return K


def fresh_list() -> type[object]:
    class K(list[int]):
        pass
    return K


def fresh_int() -> type[object]:
    class K(int):
        pass
    return K


def fresh_tuple() -> type[object]:
    class K(tuple[int, ...]):
        pass
    return K


def fresh_exception() -> type[object]:
    class K(Exception):
        pass
    return K


def many(cls: type[object], n: int) -> None:
    for _ in range(n):
        cls()


def names(cls: type[object], *stored: str) -> None:
    """An instance that stores these names, in this order, and goes."""
    o = cls()
    for name in stored:
        setattr(o, name, 1)


def last_two(cls: type[object], first: str, second: str) -> str:
    o = cls()
    setattr(o, first, V(first))
    setattr(o, second, V(second))
    del o
    return took()


print("-- instances made before the names x, y, z were stored: 0, 26, 27, 40")
for title, make in (("a class", fresh), ("list", fresh_list), ("int", fresh_int), ("tuple", fresh_tuple), ("an exception", fresh_exception)):
    row: list[str] = []
    for n in (0, 26, 27, 40):
        K = make()
        many(K, n)
        names(K, "x", "y")
        names(K, "x", "z")
        row.append(last_two(K, "z", "x"))
    print(title + ":", " | ".join(row))
print("-- names the keys already hold, and the one more they take")
K = fresh()
names(K, "x", "y")
many(K, 40)
print(last_two(K, "y", "x"), end=" | ")
o = K()
setattr(o, "x", V("x"))
setattr(o, "w", V("w"))
setattr(o, "y", V("y"))
print(list(vars(o)), end=" ")
del o
print(took(), "|", last_two(K, "w", "x"), "|", last_two(K, "v", "x"))


class Known:
    """Its attributes are the ones the class's own code sets: the keys hold them from the start."""

    def __init__(self) -> None:
        self.b = V("b")
        self.a = V("a")


print("-- the class's own code sets them")
many(Known, 40)
took()
k = Known()
del k
print(took(), end=" | ")
k = Known()
setattr(k, "n", V("n"))
del k
print(took(), end=" | ")
k = Known()
setattr(k, "m", V("m"))
print(list(vars(k)), end=" ")
del k
print(took(), end=" | ")
k = Known()
k.a = V("a2")
del k
print(took())
print("-- the last place")
K = fresh()
names(K, "k0")
many(K, 100)
names(K, "p")
print(last_two(K, "p", "k0"), end=" | ")
names(K, "r")
print(last_two(K, "r", "k0"), "|", last_two(K, "p", "k0"))
print("-- a subclass has places of its own")
Base = fresh()


class Sub(Base):  # type: ignore[misc, valid-type]
    pass


many(Base, 40)
names(Sub, "x", "y")
names(Sub, "x", "z")
print(last_two(Sub, "z", "x"), end=" | ")
many(Sub, 40)
names(Base, "x", "y")
print(last_two(Base, "y", "x"), last_two(Base, "q", "x"))
print("end")
