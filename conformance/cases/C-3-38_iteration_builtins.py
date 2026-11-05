# clause: C-3-38
# spec: section 3
# status: P1
# source: Python/bltinmodule.c, Objects/enumobject.c, Objects/listobject.c (list.sort, powersort)
"""sorted and list.sort, reversed, enumerate, zip, map, filter, min, max, sum, any and all: what each
asks of its arguments and when, and for sort which pairs it compares and in what order, which a
__lt__ can see. Comparison logs are compared byte for byte, so the merge strategy itself is held."""
# ruff: noqa: B007, B023, C400, C414, RUF015, E721, UP037, B905, B912  # what these asks of a program is what this case is about


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


# ---- sort: results and stability
print(sorted([3, 1, 2]), sorted("bca"), sorted((2, 1)), sorted({1: "a"}), sorted([]), sorted([1]), sorted(iter([2, 1])), sorted(range(3), reverse=True))
print(sorted(["b", "A", "c"], key=lambda s: ord(s) | 32), sorted([(1, "b"), (1, "a"), (0, "c")]), sorted([[2], [1, 5], [1]]), sorted([True, False, 2, 0]))
pairs = [(1, "a"), (0, "b"), (1, "c"), (0, "d"), (1, "e")]
print(sorted(pairs, key=lambda p: p[0]), sorted(pairs, key=lambda p: p[0], reverse=True))
items = [5, 2, 9]
print(items.sort(), items, items.sort(reverse=True), items, items.sort(key=lambda v: -v), items, items.sort(key=None, reverse=False), items)
print("arguments:", failed(lambda: sorted()), failed(lambda: sorted([], [])), failed(lambda: [].sort(1)), failed(lambda: [].sort(x=1)), failed(lambda: sorted([], x=1)), failed(lambda: sorted(1)), failed(lambda: sorted([1, "a"])), failed(lambda: [1, "a"].sort()), failed(lambda: sorted([1, 2], key=1)))  # type: ignore[call-overload,type-var]
big = [(i * 7919) % 1009 for i in range(1000)]
print("big:", sorted(big)[:5], sorted(big)[-5:], sorted(big, reverse=True)[:3], sorted(big) == sorted(sorted(big)), len(sorted(big)))


# ---- the order of comparisons: what a __lt__ sees
class Logged:
    log: list[tuple[int, int]] = []
    def __init__(self, v: int) -> None:
        self.v = v
    def __lt__(self, other: "Logged") -> bool:
        Logged.log.append((self.v, other.v))
        return self.v < other.v
    def __repr__(self) -> str:
        return str(self.v)


def compared(values: list[int], **kwds: bool) -> list[tuple[int, int]]:
    Logged.log = []
    out = sorted([Logged(v) for v in values], **kwds)  # type: ignore[call-overload]
    assert [o.v for o in out] == sorted(values, **kwds)  # type: ignore[call-overload]
    return Logged.log


print(compared([]), compared([1]), compared([1, 2]), compared([2, 1]), compared([1, 1]))
print(compared([3, 1, 2]), compared([1, 2, 3]), compared([3, 2, 1]), compared([2, 2, 1, 1]), compared([1, 3, 2, 4]))
print(compared([5, 3, 8, 1, 9, 2], reverse=True))
for n, step in ((10, 3), (70, 7), (130, 11), (300, 13), (600, 17)):
    data = [(i * step) % n for i in range(n)]
    log = compared(data)
    total = 0
    for x, y in log:
        total = (total * 31 + x * 3 + y) % 1000000007
    print(n, len(log), total, log[:4], log[-4:])
runs = list(range(100)) + list(range(100, 0, -1)) + [5] * 40 + list(range(50))
log = compared(runs)
print("natural runs:", len(log), log[:3], log[-3:])
gallop = list(range(0, 400, 2)) + list(range(1, 400, 2))
log = compared(gallop)
print("merge:", len(log), log[:6], log[-6:])
gallop_hi = list(range(200, 400)) + list(range(0, 200))
log = compared(gallop_hi)
print("gallop:", len(log), log[:6], log[-6:])
log = compared([1] * 100)
print("equal:", len(log), log[:2])


class Counted:
    calls = 0
    def __init__(self, v: int) -> None:
        self.v = v
    def __lt__(self, other: object) -> object:
        Counted.calls += 1
        return NotImplemented
    def __gt__(self, other: "Counted") -> bool:
        Counted.calls += 100
        return self.v > other.v


print("NotImplemented asks again:", [c.v for c in sorted([Counted(2), Counted(1)])], Counted.calls)


class Eq:
    log: list[str] = []
    def __init__(self, v: int) -> None:
        self.v = v
    def __eq__(self, other: object) -> bool:
        Eq.log.append("eq")
        return self.v == other.v  # type: ignore[attr-defined,no-any-return]
    def __lt__(self, other: "Eq") -> bool:
        Eq.log.append("lt")
        return self.v < other.v
    __hash__ = None  # type: ignore[assignment]


same = Eq(1)
sorted([(Eq(2), 1), (Eq(1), 2), (same, 3), (same, 0)])
print("in tuples:", Eq.log)


class Other:
    pass


print("mixed:", failed(lambda: sorted([Logged(1), Other()])), failed(lambda: sorted([(Logged(1),), (Other(),)])), failed(lambda: sorted([(1,), ()])), sorted([(), (1,)]))  # type: ignore[type-var]


# ---- what the list looks like during a sort
class Watches:
    seen: list[int] = []
    target: list[object] = []
    def __lt__(self, other: object) -> bool:
        Watches.seen.append(len(Watches.target))
        return False


Watches.target = [Watches(), Watches()]
Watches.target.sort()
print("empty while sorting:", Watches.seen, len(Watches.target))


class Changes:
    target: list[object] = []
    def __lt__(self, other: object) -> bool:
        Changes.target.append(1)
        return False


Changes.target = [Changes(), Changes()]
print("changed:", failed(lambda: Changes.target.sort()), len(Changes.target))


class Raises:
    def __init__(self, v: int) -> None:
        self.v = v
    def __lt__(self, other: "Raises") -> bool:
        if self.v == 0:
            raise KeyError("in the compare")
        return self.v < other.v


whole = [Raises(v) for v in (3, 1, 0, 2)]
print("raises:", failed(lambda: whole.sort()), len(whole), {r.v for r in whole} == {0, 1, 2, 3})


def key_raises(v: int) -> int:
    if v == 2:
        raise ValueError("in the key")
    return v


keyed = [3, 2, 1]
print("key raises:", failed(lambda: keyed.sort(key=key_raises)), keyed)
key_order: list[int] = []


def recording(v: int) -> int:
    key_order.append(v)
    return v


sorted([3, 1, 2], key=recording)
print("keys once, in order:", key_order)
kept = [3, 1, 2]
print("reverse is stable and restores:", failed(lambda: kept.sort(reverse=True, key=lambda v: v)), kept)


# ---- reversed
print(list(reversed([1, 2])), list(reversed((1, 2))), list(reversed("ab")), list(reversed(b"ab")), list(reversed(range(3))), list(reversed(range(1, 10, 3))), list(reversed([])))


class HasReversed:
    def __reversed__(self) -> object:
        return iter(["from __reversed__"])


class NoneReversed:
    __reversed__ = None
    def __getitem__(self, i: int) -> int:
        return i
    def __len__(self) -> int:
        return 1


class Seq:
    def __len__(self) -> int:
        return 2
    def __getitem__(self, i: int) -> str:
        return "item " + str(i)


class ShortSeq:
    def __len__(self) -> int:
        return 3
    def __getitem__(self, i: int) -> int:
        if i == 2:
            raise IndexError
        return i


print(list(reversed(HasReversed())), list(reversed(Seq())), list(reversed(ShortSeq())), type(reversed(Seq())).__name__, type(reversed([])).__name__, type(reversed(range(1))).__name__, type(reversed(())).__name__, type(reversed("")).__name__)  # type: ignore[call-overload]
print("refused:", failed(lambda: reversed()), failed(lambda: reversed([], [])), failed(lambda: reversed(1)), failed(lambda: reversed(iter([]))), failed(lambda: reversed(NoneReversed())), failed(lambda: reversed(set())), failed(lambda: reversed(x=1)))  # type: ignore[call-overload]
r = reversed([1, 2])
print(iter(r) is r, next(r), next(r), failed(lambda: next(r)), failed(lambda: next(r)))
grow = [1, 2, 3]
g = reversed(grow)
print(next(g))
grow.clear()
print(failed(lambda: next(g)))
grow2 = [1, 2]
g2 = reversed(grow2)
grow2.append(3)
print(list(g2))
print(reversed.__name__, reversed.__mro__[1].__name__, type(reversed).__name__, callable(reversed))
print("hint:", reversed(Seq()).__length_hint__(), reversed((1, 2)).__length_hint__())  # type: ignore[attr-defined]


# ---- enumerate
print(list(enumerate("ab")), list(enumerate("ab", 5)), list(enumerate("ab", start=-1)), list(enumerate(iterable="a")), list(enumerate([])), list(enumerate(iterable="a", start=2)))
e = enumerate(["x"])
print(iter(e) is e, next(e), failed(lambda: next(e)), type(e).__name__, enumerate.__name__, type(enumerate).__name__)
print("refused:", failed(lambda: enumerate()), failed(lambda: enumerate(1)), failed(lambda: enumerate([], "a")), failed(lambda: enumerate([], 1, 2)), failed(lambda: enumerate([], x=1)), failed(lambda: enumerate(start=1)))  # type: ignore[arg-type,call-arg]


class Index:
    def __index__(self) -> int:
        return 7


print(list(enumerate("a", Index())), list(enumerate("a", True)))  # type: ignore[arg-type]
for i, v in enumerate("ab"):
    print(i, v)


class E2(enumerate):  # type: ignore[type-arg]
    def __next__(self) -> object:  # type: ignore[override]
        return ("mine", super().__next__())


print(next(E2("a")), list(E2("ab")), isinstance(E2(""), enumerate))


# ---- zip
print(list(zip()), list(zip("ab")), list(zip("ab", [1, 2, 3])), list(zip("abc", [1], (2, 3))), list(zip("ab", "cd", strict=True)), list(zip(strict=True)), list(zip("a", strict=False)))
z = zip("a")
print(iter(z) is z, next(z), failed(lambda: next(z)), type(z).__name__, zip.__name__)
print("refused:", failed(lambda: zip(1)), failed(lambda: zip("a", 1)), failed(lambda: zip(x=1)), failed(lambda: list(zip("a", "ab", strict=True))), failed(lambda: list(zip("ab", "a", strict=True))), failed(lambda: list(zip("a", "b", "cd", strict=True))))  # type: ignore[call-overload]
consumed = iter([1, 2, 3])
print(list(zip("a", consumed)), list(consumed))
consumed2 = iter([1, 2, 3])
print(list(zip(consumed2, "a")), list(consumed2))
for a, b in zip("ab", "cd"):
    print(a, b)
print(dict(zip("ab", [1, 2])), list(zip(*[(1, 2), (3, 4)])))


# ---- map and filter
print(list(map(str, [1, 2])), list(map(lambda a, b: a + b, [1, 2], [3, 4, 5])), list(map(str, [])), list(map(lambda a, b: a, "a", "b", strict=True)), type(map(str, [])).__name__)
print(list(filter(None, [0, 1, "", "a"])), list(filter(lambda v: v > 1, [1, 2, 3])), list(filter(bool, [0, 1])), type(filter(None, [])).__name__)
m = map(str, [1])
print(iter(m) is m, next(m), failed(lambda: next(m)), map.__name__, filter.__name__)
print("refused:", failed(lambda: map()), failed(lambda: map(str)), failed(lambda: map(str, 1)), failed(lambda: list(map(1, [1]))), failed(lambda: map(str, [], x=1)), failed(lambda: list(map(str, "a", "ab", strict=True))), failed(lambda: filter()), failed(lambda: filter(None)), failed(lambda: filter(None, 1)), failed(lambda: list(filter(1, [1]))), failed(lambda: filter(None, [], [])), failed(lambda: filter(None, [], x=1)))  # type: ignore[arg-type,call-overload]


# ---- min and max
print(min([3, 1, 2]), max([3, 1, 2]), min(3, 1), max(3, 1), min("ba"), max("ba"), min([1], default=0), min([], default=0), max([], default=None), min(1, 2, key=lambda v: -v), max([1, 2], key=lambda v: -v), min([1, 2], key=None), max(1, 2, 3))
print("first of equals:", min([(1, "a"), (1, "b")], key=lambda p: p[0]), max([(1, "a"), (1, "b")], key=lambda p: p[0]))
print("refused:", failed(lambda: min()), failed(lambda: max()), failed(lambda: min(1)), failed(lambda: min([])), failed(lambda: max([])), failed(lambda: min(1, 2, default=0)), failed(lambda: min([1, "a"])), failed(lambda: max(1, "a")), failed(lambda: min([1], x=1)), failed(lambda: min([1], key=1)), failed(lambda: min([1, 2], key=1)))  # type: ignore[call-overload,type-var]


class Logs:
    log: list[str] = []
    def __init__(self, n: str) -> None:
        self.n = n
    def __lt__(self, other: "Logs") -> bool:
        Logs.log.append(self.n + "<" + other.n)
        return False
    def __gt__(self, other: "Logs") -> bool:
        Logs.log.append(self.n + ">" + other.n)
        return False


a1, a2, a3 = Logs("a"), Logs("b"), Logs("c")
print(min(a1, a2, a3).n, max(a1, a2, a3).n, Logs.log)


# ---- sum, any and all
print(sum([1, 2]), sum([]), sum([1], 5), sum([1], start=5), sum(range(4)), sum((True, True)), sum([[1], [2]], []), sum([(1,)], ()), sum(iter([1])))
print("refused:", failed(lambda: sum()), failed(lambda: sum(1)), failed(lambda: sum(["a"])), failed(lambda: sum([], "")), failed(lambda: sum([], b"")), failed(lambda: sum([], bytearray())), failed(lambda: sum([1], 2, 3)), failed(lambda: sum([1], x=1)))  # type: ignore[call-overload,list-item]


class Adds:
    def __radd__(self, other: object) -> str:
        return "radd " + repr(other)
    def __add__(self, other: object) -> str:
        return "add " + repr(other)


print(sum([Adds()]), sum([1, Adds()]), sum([], Adds()) is not None, sum([1], Adds()))  # type: ignore[list-item]
print(any([]), all([]), any([0, 1]), all([0, 1]), any("a"), all(""), any([0]), all([1]), any(iter([1])), all(iter([0])))
print("refused:", failed(lambda: any()), failed(lambda: all()), failed(lambda: any(1)), failed(lambda: all(1)), failed(lambda: any([], [])), failed(lambda: all(x=1)))  # type: ignore[arg-type,call-arg]
stopped: list[int] = []


def seen(v: int) -> int:
    stopped.append(v)
    return v


print(any(map(seen, [0, 1, 2])), stopped, all(map(seen, [1, 0, 2])), stopped)
print(len.__class__.__name__, sorted.__class__.__name__, min.__class__.__name__, sum.__class__.__name__, any.__class__.__name__, sorted.__name__, min.__module__, repr(max).startswith("<built-in function max"))
