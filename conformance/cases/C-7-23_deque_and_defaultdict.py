# clause: C-7-23
# spec: section 7
# status: P1
# source: dialect specification section 7, Modules/_collectionsmodule.c
"""collections.deque and defaultdict: what each method does at both ends and under a maxlen, the state an iterator
watches, comparisons, the sequence slots' order against a reflected method, the order in which items die, and
_tuplegetter and _count_elements as collections uses them."""
# ruff: noqa: B007, B015, B018, B023, RUF015, SLF001, C408
import _collections  # type: ignore[import-not-found]
import collections
from collections import defaultdict, deque


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


# ---- the two ends
d = deque([1, 2, 3])
print(d, len(d), list(d), bool(d), bool(deque()), d[0], d[-1], d[1], 2 in d, 9 in d, list(reversed(d)), d.maxlen, type(d).__name__, type(d).__module__, repr(d), str(d), deque.__name__, deque.__qualname__, deque.__module__)
print(d.append(4), d, d.appendleft(0), d, d.pop(), d, d.popleft(), d, d.extend([4, 5]), d, d.extendleft([0, -1]), d, d.clear(), d, len(d))  # type: ignore[func-returns-value]
print(failed(lambda: d.pop()), failed(lambda: d.popleft()), failed(lambda: d[0]), failed(lambda: d[-1]), failed(lambda: d.__getitem__(0)))
d = deque(range(5))
print(d.rotate(), d, d.rotate(2), d, d.rotate(-1), d, d.rotate(0), d, d.rotate(5), d, d.rotate(7), d, d.rotate(-7), d, d.rotate(100), d, d.rotate(-101), d, deque().rotate(3), deque([1]).rotate(3), d.reverse(), d)  # type: ignore[func-returns-value]
print(d.count(1), d.count(9), d.index(1), failed(lambda: d.index(9)), d.index(1, 0), failed(lambda: d.index(1, 3)), d.index(1, -5), d.index(1, -100, 100), failed(lambda: d.index(1, 0, 0)), d.index(1, True), failed(lambda: d.index(1, 1.5)), failed(lambda: d.index(1, None)), failed(lambda: d.index()), failed(lambda: d.count()), failed(lambda: d.index(1, 2, 3, 4)))  # type: ignore[arg-type,call-arg]
print(d.insert(0, "a"), d, d.insert(100, "b"), d, d.insert(-100, "c"), d, d.insert(2, "d"), d, d.insert(-2, "e"), d, d.remove("a"), d, failed(lambda: d.remove("zz")), d.remove("e"), d)  # type: ignore[arg-type,func-returns-value]
d[0] = "first"  # type: ignore[assignment]
d[-1] = "last"  # type: ignore[assignment]
del d[1]
del d[-2]
print(d, failed(lambda: d.__setitem__(100, 1)), failed(lambda: d.__delitem__(100)), failed(lambda: d.__getitem__(100)), failed(lambda: d.__getitem__(-100)), failed(lambda: d["a"]), failed(lambda: d[1:2]), failed(lambda: d[1.5]), failed(lambda: d.__getitem__("a")), failed(lambda: d.__setitem__("a", 1)), failed(lambda: d.__delitem__("a")), failed(lambda: d[2**70]), failed(lambda: d.__getitem__(2**70)), d[True], failed(lambda: hash(d)))  # type: ignore[arg-type,index]
for i in range(40):
    d.append(i)
    d.appendleft(-i)
print(d, len(d), d[0], d[-1], d[40], d[-40])
for i in range(30):
    d.pop()
    d.popleft()
print(d, len(d))

# ---- maxlen
m = deque([1, 2, 3], 2)
print(m, m.maxlen, m.append(4), m, m.appendleft(0), m, m.extend([7, 8, 9]), m, m.extendleft([1, 2, 3]), m, len(m), failed(lambda: m.insert(0, 1)), m.pop(), m.insert(0, "x"), m, failed(lambda: setattr(m, "maxlen", 1)), failed(lambda: delattr(m, "maxlen")), repr(m), m == deque(m), m == deque(m, 5), m.copy(), m.copy().maxlen, m.__copy__().maxlen, (m + m).maxlen, (m * 2).maxlen, m + m, m * 3, 3 * m)  # type: ignore[arg-type,func-returns-value]
print(deque([1, 2], 0), deque(maxlen=0).append(1), len(deque([1, 2], 0)), deque(maxlen=None).maxlen, deque([], None).maxlen, deque(iterable=[1]), deque(maxlen=1, iterable=[1, 2]), failed(lambda: deque(maxlen=-1)), failed(lambda: deque([], "a")), failed(lambda: deque([], 1.5)), failed(lambda: deque(maxlen=2**70)), failed(lambda: deque(1)), failed(lambda: deque([], 1, 2)), failed(lambda: deque(x=1)), failed(lambda: deque([1], iterable=[2])), failed(lambda: deque([1], 1, maxlen=2)), deque([1], True).maxlen, deque("abc"), deque((1, 2)), deque({1: 2}), deque(), deque([]))  # type: ignore[arg-type,call-overload,func-returns-value]
r = deque([1, 2, 3])
r.__init__([9], 3)  # type: ignore[misc]
print(r, r.maxlen, r.__init__(), r, r.maxlen)  # type: ignore[misc]

# ---- what an iterator watches
d = deque([1, 2, 3, 4])
it = iter(d)
print(next(it), type(it).__name__, type(it).__module__, it.__length_hint__(), iter(it) is it)  # type: ignore[attr-defined]
d[0] = "same state"  # type: ignore[assignment]
d.reverse()
print(next(it), it.__length_hint__())  # type: ignore[attr-defined]
d.rotate(0)
print(failed(lambda: next(it)), it.__length_hint__(), failed(lambda: next(it)))  # type: ignore[attr-defined]
rv = reversed(d)
print(next(rv), type(rv).__name__, rv.__length_hint__())  # type: ignore[attr-defined]
d.append(1)
print(failed(lambda: next(rv)), failed(lambda: next(rv)))
for change in (lambda q: q.append(1), lambda q: q.appendleft(1), lambda q: q.pop(), lambda q: q.popleft(), lambda q: q.clear(), lambda q: q.extend([1]), lambda q: q.extend([]), lambda q: q.extendleft([]), lambda q: q.rotate(), lambda q: q.rotate(0), lambda q: q.reverse(), lambda q: q.insert(1, 1), lambda q: q.remove(2), lambda q: q.__delitem__(0), lambda q: q.__setitem__(0, 1), lambda q: q.__iadd__([1]), lambda q: q.__imul__(1), lambda q: q.__imul__(2), lambda q: q.__init__(), lambda q: q.__init__([1, 2, 3]), lambda q: q.copy(), lambda q: q.count(1), lambda q: q.index(1), lambda q: 1 in q):
    q = deque([1, 2, 3])
    i = iter(q)  # type: ignore[assignment]
    next(i)  # type: ignore[call-overload]
    change(q)
    print(failed(lambda: next(i)), end=" ")  # type: ignore[call-overload]
print()
one = deque([1])
print(one.__imul__(1), one.__imul__(3), one, one.__imul__(0), deque(maxlen=2).__imul__(3), failed(lambda: list(iter(deque([1]))).x), collections._deque_iterator(deque([1, 2, 3])).__next__(), collections._deque_iterator(deque([1, 2, 3]), 2).__next__(), list(collections._deque_iterator(deque([1, 2, 3]), 5)), list(_collections._deque_reverse_iterator(deque([1, 2, 3]), 1)), failed(lambda: collections._deque_iterator(1)), failed(lambda: collections._deque_iterator()), failed(lambda: collections._deque_iterator(deque(), 1, 2)), failed(lambda: collections._deque_iterator(deque(), "a")), failed(lambda: type("X", (collections._deque_iterator,), {})))  # type: ignore[attr-defined]


# ---- what runs while a method looks
class Mutates:
    def __init__(self, q: deque[object]) -> None:
        self.q = q

    def __eq__(self, o: object) -> bool:
        self.q.append(1)
        return False

    __hash__ = None  # type: ignore[assignment]


class Raises:
    def __eq__(self, o: object) -> bool:
        raise KeyError("eq")

    __hash__ = None  # type: ignore[assignment]


for name in ("count", "index", "remove", "__contains__"):
    q: deque[object] = deque()  # type: ignore[no-redef]
    q.extend([Mutates(q), 1, 2])  # type: ignore[arg-type,list-item]
    print(name, failed(lambda: getattr(q, name)(5)), failed(lambda: getattr(deque([Raises()]), name)(5)), len(q))
print(deque([1, 2]) == deque([1, 2]), deque([1, 2]) != deque([1, 2]), deque([1]) == [1], deque([1]) != [1], deque([1, 2]) < deque([1, 3]), deque([1, 2]) <= deque([1, 2]), deque([1, 2]) > deque([1]), deque([1, 2]) >= deque([2]), deque() == deque(), deque() < deque([1]), deque([1, 2]) < deque([1, 2, 3]), deque([1, 2, 3]) < deque([1, 2]), failed(lambda: deque([1]) < [1]), failed(lambda: [1] < deque([1])), failed(lambda: deque(["a"]) < deque([1])), deque([1]).__eq__([1]), deque([1]).__lt__(1), failed(lambda: deque([Raises()]) == deque([1])), deque([float("nan")]) == deque([float("nan")]), deque([1.0]) == deque([1]), sorted([deque([2]), deque([1])]))  # type: ignore[list-item,operator]
nan = float("nan")
print(deque([nan]) == deque([nan]), nan in deque([nan]), deque([nan]).count(nan), deque([nan]).index(nan))


# ---- the sequence slots' order
class Reflects:
    def __radd__(self, o: object) -> str:
        return "radd"

    def __rmul__(self, o: object) -> str:
        return "rmul"

    def __mul__(self, o: object) -> str:
        return "mul"

    def __add__(self, o: object) -> str:
        return "add"


class Index:
    def __index__(self) -> int:
        return 2


d = deque([1, 2])
print(d + Reflects(), Reflects() + d, d * Reflects(), Reflects() * d, d + deque([3]), d * 2, 2 * d, d * 0, d * -1, d * True, d * Index(), Index() * d, failed(lambda: d + [3]), failed(lambda: [3] + d), failed(lambda: d + 1), failed(lambda: 1 + d), failed(lambda: d * 1.5), failed(lambda: 1.5 * d), failed(lambda: d * "a"), failed(lambda: "a" * d), failed(lambda: d * 2**70), failed(lambda: 2**70 * d), d.__add__(deque([3])), failed(lambda: d.__add__([3])), failed(lambda: d.__add__(Reflects())), d.__mul__(2), d.__rmul__(2), failed(lambda: d.__mul__("a")), failed(lambda: d.__mul__(1.5)), failed(lambda: d.__mul__(2**70)), failed(lambda: d - d), failed(lambda: d / 2), failed(lambda: -d))  # type: ignore[operator]
x = deque([1])
x += [2]
x += (3,)
x += "ab"  # type: ignore[arg-type]
x *= 2
y = x
y += deque([9])
print(x, x is y, failed(lambda: x.__iadd__(1)), failed(lambda: x.__imul__("a")))  # type: ignore[arg-type]
z: object = deque([1])
z += Reflects()
print(z)
s = deque([1, 2])
s.extend(s)
s.extendleft(s)
s += s
print(s, s.copy() == s, s.__copy__() == s, s.__copy__() is s, type(s.__copy__()).__name__)
rec: deque[object] = deque([1])
rec.append(rec)
print(rec, repr(rec), [rec], str(rec))


# ---- a subclass
class Sub(deque):  # type: ignore[type-arg]
    def __init__(self, *a: object, **k: object) -> None:
        self.tag = "t"
        super().__init__(*a, **k)  # type: ignore[call-overload]

    def append(self, x: object) -> None:
        super().append(("wrapped", x))

    def __iter__(self) -> object:  # type: ignore[override]
        return iter(["from iter"])

    def __len__(self) -> int:
        return 100


class Plain(deque):  # type: ignore[type-arg]
    def __repr__(self) -> str:
        return "Plain:" + super().__repr__()


class Added(deque):  # type: ignore[type-arg]
    def __add__(self, o: object) -> str:  # type: ignore[override]
        return "own add"

    def __mul__(self, o: object) -> str:  # type: ignore[override]
        return "own mul"

    def __getitem__(self, i: object) -> str:  # type: ignore[override]
        return "own getitem " + repr(i)


class Slotted(deque):  # type: ignore[type-arg]
    __slots__ = ("a",)


class BadCopy(deque):  # type: ignore[type-arg]
    def __new__(cls, *a: object) -> object:  # type: ignore[misc]
        return 1


s2 = Sub([1], 5)
s2.append(2)
p = Plain([1])
a = Added([1])
sl = Slotted([1])
print(s2.tag, s2.__dict__, s2.maxlen, list(s2), deque.__iter__(s2).__next__(), deque.__len__(s2), repr(s2), len(s2), s2[0], failed(lambda: s2[-1]), s2 == deque(["from iter"]), p, p.copy(), type(p.copy()).__name__, p + p, type(p + p).__name__, p * 2, type(p * 2).__name__, a + 1, 1 * a if False else 0, a * 1, a[1:2], a["x"], type(sl).__name__, failed(lambda: setattr(sl, "b", 1)), failed(lambda: sl.__dict__), Plain.__mro__[1] is deque, issubclass(Plain, deque), isinstance(p, deque), failed(lambda: BadCopy().copy()))  # type: ignore[attr-defined]
print(sorted(set(dir(deque)) - set(dir(object))), sorted(set(dir(defaultdict)) - set(dir(dict))), sorted(set(dir(collections._deque_iterator)) - set(dir(object))), sorted(set(dir(collections._tuplegetter)) - set(dir(object))), deque[int], defaultdict[str, int], deque.__hash__, callable(deque), failed(lambda: deque.__new__(int)), failed(lambda: deque.__new__(1)), failed(lambda: deque.append(1, 2)), failed(lambda: deque.append()), failed(lambda: deque.__len__(1)), failed(lambda: deque.__len__()), failed(lambda: type("X", (deque, dict), {})), failed(lambda: type("X", (deque, int), {})))  # type: ignore[arg-type,attr-defined,call-arg]


# ---- the order in which items die
class Noisy:
    def __init__(self, n: object) -> None:
        self.n = n

    def __del__(self) -> None:
        print("del", self.n, end="; ")


def noisy(*names: object) -> deque[Noisy]:
    return deque([Noisy(n) for n in names])


q1 = noisy("a", "b", "c")
del q1
print("death")
q2 = noisy("a", "b", "c")
q2.clear()
print("clear")
q3 = noisy("a", "b", "c")
q3.rotate()
q3.append(Noisy("d"))
del q3
print("rotated")
q4 = noisy("a", "b")
q4.maxlen  # noqa: B018
q5: deque[Noisy] = deque(maxlen=1)
q5.append(Noisy("x"))
q5.append(Noisy("y"))
print("trim")
q5.appendleft(Noisy("z"))
print("trim left")
q4.pop()
print("pop")
q4.popleft()
print("popleft")
q6 = noisy("a", "b", "c", "d")
del q6[1]
print("delitem")
q6[0] = 1  # type: ignore[assignment]
print("setitem")
q6.remove(1)  # type: ignore[arg-type]
print("remove")
q6 *= 0
print("imul 0")
q7: deque[Noisy] = deque([Noisy("g"), Noisy("h")], 0)
print("maxlen 0", len(q7))
q8 = noisy("a", "b")
q8.__init__([Noisy("new")])  # type: ignore[misc]
print("init")
del q5, q8

# ---- defaultdict
dd: defaultdict[str, object] = defaultdict(list)
dd["a"].append(1)  # type: ignore[attr-defined]
print(dd, dd["a"], "b" in dd, dd.default_factory, len(dd), dict(dd), type(dd).__name__, type(dd).__module__, repr(dd), str(dd), isinstance(dd, dict), issubclass(defaultdict, dict), defaultdict.__mro__[1], dd.get("zz"), "zz" in dd, dd.__missing__("m"), "m" in dd, dd.pop("m"), dd.setdefault("s", 1), dd == {"a": [1], "s": 1}, dd.copy(), type(dd.copy()).__name__, dd.copy().default_factory, dd.__copy__(), dd.__copy__() is dd)
print(defaultdict(), defaultdict().default_factory, defaultdict(None), defaultdict(int, a=1), defaultdict(int, {"a": 1}, b=2), defaultdict(int, [("a", 1)]), defaultdict(None, a=1), failed(lambda: defaultdict(1)), failed(lambda: defaultdict("a")), failed(lambda: defaultdict(int, 1)), failed(lambda: defaultdict()["x"]), failed(lambda: defaultdict(None)["x"]), failed(lambda: defaultdict(lambda: 1 / 0)["x"]), failed(lambda: defaultdict(default_factory=int)["x"]), defaultdict(default_factory=int), failed(lambda: defaultdict(int).__missing__()), failed(lambda: defaultdict(int).__missing__(1, 2)), failed(lambda: defaultdict.__missing__(1, 2)), failed(lambda: defaultdict(int).copy(1)), failed(lambda: hash(defaultdict())), defaultdict.__hash__)  # type: ignore[arg-type,call-arg,call-overload,index]
e: defaultdict[str, int] = defaultdict(int)
print(e["x"], e["y"], e, e.__reduce__()[0].__name__, e.__reduce__()[1:3 + 1 - 1], list(e.__reduce__()[4]), defaultdict().__reduce__()[1], failed(lambda: setattr(e, "x", 1)), e.__or__({"z": 1}), e | {"z": 1}, {"z": 1} | e, type({"z": 1} | e).__name__, (e | {"z": 1}).default_factory, ({"z": 1} | e).default_factory, e.__or__(1), e.__ror__(1), failed(lambda: e | 1), failed(lambda: 1 | e), defaultdict(int) | defaultdict(str), (defaultdict(int) | defaultdict(str)).default_factory, (defaultdict(str) | defaultdict(int)).default_factory)  # type: ignore[operator,union-attr]
e |= {"w": 1}
e.default_factory = str  # type: ignore[assignment]
print(e, e["q"] == "", e.default_factory)  # type: ignore[comparison-overlap]
e.default_factory = 1  # type: ignore[assignment]
print(failed(lambda: e["r"]), e.default_factory)
del e.default_factory
print(e.default_factory, failed(lambda: e["r"]))
e.default_factory = None
print(failed(lambda: e["r"]), type(defaultdict.__dict__["default_factory"]).__name__, defaultdict.__dict__["default_factory"])


class Inserts(defaultdict):  # type: ignore[type-arg]
    def __setitem__(self, k: object, v: object) -> None:
        print("setitem", k, v)
        super().__setitem__(k, v)

    def __missing__(self, k: object) -> object:
        return "own " + repr(k)


class Counts(defaultdict):  # type: ignore[type-arg]
    def __setitem__(self, k: object, v: object) -> None:
        print("setitem", k, v)
        super().__setitem__(k, v)


class Factory(defaultdict):  # type: ignore[type-arg]
    def __repr__(self) -> str:
        return "F" + super().__repr__()


ins = Inserts(int)
cnt = Counts(int)
print(ins["a"], ins, cnt["a"], cnt, Factory(int), Factory(int).copy(), type(Factory(int).copy()).__name__, type(Factory(int) | {}).__name__, type({} | Factory(int)).__name__)
self_ref: defaultdict[str, object] = defaultdict()
self_ref.default_factory = self_ref  # type: ignore[assignment]
self_ref["a"] = 1
inner_repr = repr(self_ref)
print(inner_repr)
loop: defaultdict[str, object] = defaultdict(int)
loop["me"] = loop
print(loop)


def racing() -> int:
    race["k"] = 5
    return 1


race: defaultdict[str, int] = defaultdict(racing)
print(race["k"], dict(race))

# ---- _tuplegetter and _count_elements
g = collections._tuplegetter(1, "the doc")  # type: ignore[attr-defined]
print(g, repr(g), g.__doc__, g.__get__((1, 2)), g.__get__((1, 2), tuple), g.__get__(None, tuple) is g, failed(lambda: g.__get__(None, None)), failed(lambda: g.__get__([1, 2])), failed(lambda: g.__get__((1,))), failed(lambda: g.__get__(1)), failed(lambda: g.__get__()), failed(lambda: g.__set__((1, 2), 1)), failed(lambda: g.__delete__((1, 2))), g.__reduce__()[0].__name__, g.__reduce__()[1], failed(lambda: collections._tuplegetter(1)), failed(lambda: collections._tuplegetter("a", "b")), failed(lambda: collections._tuplegetter(1, "a", 2)), failed(lambda: collections._tuplegetter(index=1, doc="a")), failed(lambda: collections._tuplegetter(2**70, "a")), failed(lambda: type("X", (collections._tuplegetter,), {})), collections._tuplegetter(-1, None).__get__((1, 2)) if False else 0, failed(lambda: collections._tuplegetter(-1, None).__get__((1, 2))), collections._tuplegetter(0, None).__doc__, type(collections._tuplegetter.__dict__["__doc__"]).__name__)  # type: ignore[attr-defined]
g.__doc__ = "changed"
print(g.__doc__, g)
del g.__doc__
print(g.__doc__)
counts: dict[object, int] = {}
collections._count_elements(counts, "abca")  # type: ignore[attr-defined]
print(counts)
collections._count_elements(counts, [1, 1.0, True])  # type: ignore[attr-defined]
print(counts)


class Hashes:
    def __init__(self) -> None:
        self.calls = 0

    def __hash__(self) -> int:
        self.calls += 1
        return 1


class Maps(dict):  # type: ignore[type-arg]
    def get(self, k: object, default: object = None) -> object:
        print("get", k, default)
        return super().get(k, default)

    def __setitem__(self, k: object, v: object) -> None:
        print("set", k, v)
        super().__setitem__(k, v)


class Subclassed(dict):  # type: ignore[type-arg]
    pass


class Keys:
    def __init__(self) -> None:
        self.store: dict[object, object] = {}

    def get(self, k: object, default: object) -> object:
        return self.store.get(k, default)

    def __setitem__(self, k: object, v: object) -> None:
        self.store[k] = v


h = Hashes()
collections._count_elements({}, [h, h])  # type: ignore[attr-defined]
one_key = Subclassed()
collections._count_elements(one_key, "aa")  # type: ignore[attr-defined]
mp = Maps()
collections._count_elements(mp, "aa")  # type: ignore[attr-defined]
ks = Keys()
collections._count_elements(ks, "aab")  # type: ignore[attr-defined]
print(h.calls, one_key, mp, ks.store, failed(lambda: collections._count_elements({}, 1)), failed(lambda: collections._count_elements(1, [1])), failed(lambda: collections._count_elements({})), failed(lambda: collections._count_elements({}, [[]])), failed(lambda: collections._count_elements({"a": "x"}, "a")), failed(lambda: collections._count_elements(mapping={}, iterable=[])))  # type: ignore[attr-defined]
