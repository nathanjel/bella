# clause: C-6-24
# spec: section 6 (built-in types: tuple)
# status: P1
# source: Objects/tupleobject.c (tuple_hash, ob_hash, tuple_alloc, tuple_subtype_new), Include/internal/pycore_tuple.h
#         (_PyTuple_Recycle), Objects/enumobject.c (enum_next), Python/bltinmodule.c (zip_next), Modules/itertoolsmodule.c
#         (pairwise_next, product_next, combinations_next, permutations_next, zip_longest_next), Objects/dictobject.c
#         (dictiter_iternextitem)
"""A tuple keeps its hash once it was computed (CPython 3.14 and later): its elements' __hash__ is asked once, however
often the tuple is hashed or looked up as a key, alone or inside another tuple. A hash that could not be computed is not
kept. The iterators that use their result tuple again (enumerate, zip, those of itertools, a dict's items) forget it
with the old elements: the hash is that of what the tuple holds now."""
import itertools
from collections import namedtuple
from collections.abc import Iterator

asked: list[str] = []


class Counted:
    """An element that says when its hash is asked."""

    def __init__(self, label: str, value: int = 0) -> None:
        self.label = label
        self.value = value

    def __hash__(self) -> int:
        asked.append(self.label)
        return hash((self.label, self.value))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Counted) and (other.label, other.value) == (self.label, self.value)


def taken() -> str:
    """What was asked since the last look, and the list emptied."""
    said = " ".join(asked) or "nothing"
    asked.clear()
    return said


print("---- the elements are asked once")
a, b = Counted("a"), Counted("b")
t = (a, b)
first = hash(t)
print("the first hash asks:", taken())
print("the second and third ask:", taken() if hash(t) == first and hash(t) == first else "another value")
print("by the method:", t.__hash__() == first, tuple.__hash__(t) == first, taken())

print("---- as a key")
d = {t: "kept"}
print("stored:", taken())
print("found:", d[t], t in d, d.get(t), taken())
d[t] = "again"
print("stored again:", taken(), "| in a set:", t in {t}, len({t, t}), taken())
equal = (Counted("a"), Counted("b"))
print("an equal tuple of other elements is asked for its own:", d[equal], taken())
print("and once:", d[equal], equal in d, taken())

print("---- inside another tuple, and the same tuple under another name")
outer = (t, 1, ("x", t))
print(hash(outer) == hash(outer), "asks:", taken())
print("t[:] is t:", t[:] is t, "| tuple(t) is t:", tuple(t) is t, "| t + () is t:", t + () is t, "| t * 1 is t:", t * 1 is t)
print("so none of them asks:", hash(t[:]) == hash(tuple(t)) == hash(t + ()) == hash(t * 1) == first, taken())
print("a slice is a new tuple:", hash(t[0:1]) == hash((a,)), taken())

print("---- a class over tuple")


class Pair(tuple[Counted, ...]):
    pass


class Loud(tuple[Counted, ...]):
    def __hash__(self) -> int:
        asked.append("Loud")
        return tuple.__hash__(self)


Point = namedtuple("Point", ["x", "y"])
pair, loud, point = Pair((Counted("c"),)), Loud((Counted("e"),)), Point(Counted("x"), Counted("y"))
print("Pair:", hash(pair) == hash(pair), taken())
print("Loud, whose own method runs each time:", hash(loud) == hash(loud), taken())
print("a named tuple:", hash(point) == hash(point), taken(), "| its plain tuple is another object:", hash(tuple(point)) == hash(point), taken())

print("---- a hash that could not be computed is not kept")


class Fragile(Counted):
    broken = True

    def __hash__(self) -> int:
        asked.append(self.label)
        if Fragile.broken:
            raise ValueError("not now")
        return 5


fragile = (Counted("before"), Fragile("fragile"), Counted("after"))
for attempt in ("first", "second"):
    try:
        print(attempt, "gives", hash(fragile))
    except ValueError:
        print(attempt, "raises ValueError after:", taken())
Fragile.broken = False
print("then it can:", hash(fragile) == hash(fragile), "asks:", taken())
try:
    hash((1, [2], Counted("never")))
except TypeError:
    print("an unhashable element: TypeError, and what stands after it is not asked:", taken())

print("---- what is kept is the first answer")
moving = Counted("m", 1)
holder = (moving,)
kept = hash(holder)
moving.value = 2
print("asked when it was computed:", taken())
print("the tuple's own is unchanged:", hash(holder) == kept, taken(), "| a new tuple of the element differs:", hash((moving,)) != kept, taken())
empty: tuple[object, ...] = ()
print("the empty tuple:", hash(empty) == hash(tuple()) == hash(t[2:]), empty is tuple())

print("---- an iterator's result tuple, used again, has the hash of what it holds")


def hashes(pairs: Iterator[tuple[object, ...]], count: int) -> list[int]:
    return [hash(next(pairs)) for _ in range(count)]             # each result is let go before the next is asked for


labels, numbers = ["p", "q", "r"], [1, 2, 3]
print("zip:", hashes(zip(labels, numbers, strict=True), 3) == [hash(pair) for pair in [("p", 1), ("q", 2), ("r", 3)]])
print("enumerate:", hashes(enumerate(labels, 5), 3) == [hash(pair) for pair in [(5, "p"), (6, "q"), (7, "r")]])
print("pairwise:", hashes(itertools.pairwise(labels), 2) == [hash(("p", "q")), hash(("q", "r"))])
print("product:", hashes(itertools.product(labels, repeat=2), 9) == [hash(pair) for pair in list(itertools.product(labels, repeat=2))])
print("combinations:", hashes(itertools.combinations(numbers, 2), 3) == [hash((1, 2)), hash((1, 3)), hash((2, 3))])
print("combinations_with_replacement:", hashes(itertools.combinations_with_replacement(labels, 2), 6)
      == [hash(pair) for pair in list(itertools.combinations_with_replacement(labels, 2))])
print("permutations:", hashes(itertools.permutations(numbers), 6) == [hash(pair) for pair in list(itertools.permutations(numbers))])
print("zip_longest:", hashes(itertools.zip_longest(labels, [1]), 3) == [hash(("p", 1)), hash(("q", None)), hash(("r", None))])
print("a dict's items:", hashes(iter({"p": 1, "q": 2}.items()), 2) == [hash(("p", 1)), hash(("q", 2))])
counted = [Counted("z1"), Counted("z2"), Counted("z3")]
print("and each element is asked once a tuple:", len(hashes(zip(counted, counted, strict=True), 3)), taken())
held = list(zip(counted, numbers, strict=True))
print("results that are held keep their own:", [hash(pair) for pair in held] == [hash(pair) for pair in held], taken())
