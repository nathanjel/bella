# clause: C-3-63
# spec: section 3 (classes: a subclass of a built-in type), section 6 (set, frozenset)
# status: P1
# source: Objects/setobject.c (CPython 3.15.2: set_new, set_init, frozenset_new, set_repr, the number and sequence slots of
#         a heap type over them, set_reduce, make_new_set_basetype), Objects/typeobject.c (the slots a subclass overrides)
"""A subclass of set or frozenset is a set: it has attributes, a __dict__ unless __slots__ say otherwise, a weak reference,
and the set's own data. What a set's own methods and operators make is a set or a frozenset, never the subclass; what
the program overrides (__iter__, __len__, __contains__, __or__, __eq__, __hash__, __init__) is what iteration, len(), in,
the operators and hashing ask; another set's own methods read its elements whatever it overrides. Its repr names the
subclass; copy and pickle's reduction keep it."""
import copy
import weakref
from collections.abc import Iterable, Iterator


class Tags(set[str]):
    def __init__(self, items: Iterable[str] = (), owner: str = "nobody") -> None:
        super().__init__(items)
        self.owner = owner


class Frozen(frozenset[int]):
    pass


class Slotted(set[int]):
    __slots__ = ("note",)
    note: str


class Noisy(set[int]):
    def __iter__(self) -> Iterator[int]:
        yield from sorted(super().__iter__(), reverse=True)

    def __len__(self) -> int:
        return 100

    def __contains__(self, item: object) -> bool:
        return item == "anything"

    def __or__(self, other: object) -> str:  # type: ignore[override]
        return "Noisy.__or__"


class Equal(frozenset[int]):
    def __eq__(self, other: object) -> bool:
        return True

    def __hash__(self) -> int:
        return 7


t = Tags(["b", "a"], owner="me")
print("tags:", sorted(t), t.owner, vars(t), type(t).__name__, isinstance(t, set), len(t), "a" in t)
t.add("c")
t |= {"d"}
print("after add and |=:", sorted(t), type(t).__name__, t.owner)
print("operators make sets:", type(t | {"z"}).__name__, type(t & {"a"}).__name__, type(t - {"a"}).__name__, type(t ^ {"q"}).__name__,
      type(t.copy()).__name__, type(t.union()).__name__, type(t.difference(set())).__name__)
print("repr:", repr(Tags()), repr(Tags(["x"])), repr(Frozen()), repr(Frozen([3])), repr(Slotted([1])))
f = Frozen([3, 1, 2])
keyed: dict[frozenset[int], str] = {f: "key"}
print("frozen:", sorted(f), type(f).__name__, hash(f) == hash(frozenset([1, 2, 3])), keyed[frozenset([1, 2, 3])],
      type(f | {9}).__name__, f == frozenset([1, 2, 3]), Frozen([1]) is not Frozen([1]), type(Frozen(f)).__name__)
print("frozenset of a Frozen is a new frozenset:", type(frozenset(f)).__name__, frozenset(f) == f)
s = Slotted([5])
s.note = "slot"
print("slotted:", s.note, hasattr(s, "__dict__"), sorted(s))
try:
    s.other = 1  # type: ignore[attr-defined]
except AttributeError as e:
    print("slotted refuses:", type(e).__name__)
n = Noisy([1, 2, 3])
anything: object = "anything"
print("noisy:", list(n), len(n), anything in n, 1 in n, n | {4}, sorted(set(n)), sorted(set().union(n)), bool(n),
      sorted({0}.union(n)), n == {1, 2, 3}, sorted(frozenset(n)))
eq = Equal([1])
print("equal:", eq == frozenset([2]), hash(eq), {eq: 1}.get(Equal([5])), frozenset([1]) == eq, eq in {Equal([9])})


class Rehashed(frozenset[int]):
    def __hash__(self) -> int:
        return super().__hash__()


rehashed = Rehashed([1, 2])
by_set: dict[frozenset[int], str] = {rehashed: "found"}
print("the base's own hash:", hash(rehashed) == hash(frozenset([1, 2])), frozenset.__hash__(Equal([2])) == hash(frozenset([2])), hash(Equal([2])),
      by_set[frozenset([1, 2])], rehashed in {frozenset([1, 2])}, frozenset([1, 2]) in {rehashed})
r = weakref.ref(t)
print("weak:", r() is t)
c = copy.copy(t)
print("copy:", type(c).__name__, sorted(c), c.owner, c is not t)
reduced = t.__reduce_ex__(2)
assert isinstance(reduced, tuple)
print("reduce:", reduced[0] is Tags, type(reduced[1]).__name__)
print("reduce of a set subclass:", Tags.__reduce__(t)[0] is Tags, sorted(Tags.__reduce__(t)[1][0]), Tags.__reduce__(t)[2])
print("methods with a subclass argument:", sorted({1}.union(Noisy([2]))), sorted({1, 2}.intersection(Noisy([2]))),
      {1}.issubset(Noisy([1])), sorted(set(Frozen([4]))))
d = Tags()
d.update(["k"])
d.discard("k")
print("empty again:", d, bool(d), d.owner)
print("mro:", [k.__name__ for k in Tags.__mro__], (Frozen.__base__ or object).__name__, Slotted.__flags__ & (1 << 10) == Tags.__flags__ & (1 << 10))
