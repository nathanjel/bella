# clause: C-3-52
# spec: section 3
# status: P1
# source: Objects/odictobject.c (collections.OrderedDict, the C type collections imports from _collections)
"""collections.OrderedDict as CPython's C type has it: construction and update (a mapping, keys(), pairs, keywords), the order
(an existing key keeps its place, a deleted one goes to the end when set again, move_to_end, popitem, pop, setdefault, clear,
copy), reversed() of it and of its views, the views' and iterator's types, equality (the order counts only between two
OrderedDicts), repr (empty, nested, recursive, a subclass's name), | and |=, fromkeys, what changing it during iteration
raises, __reduce__ and copy, its __dict__ and weak references, a subclass's __setitem__, __missing__ and __contains__ through
update, setdefault and copy, and how often a key's __hash__ and __eq__ run."""
# ruff: noqa: ANN001, ANN201, ANN202, ANN204, B018, E501, E731
import copy
import weakref
from collections import OrderedDict


def m(f):  # type: ignore[no-untyped-def]
    try:
        return repr(f())
    except BaseException as e:  # noqa: BLE001
        return type(e).__name__


od = OrderedDict([("b", 2), ("a", 1)], c=3)
print(od, list(od), len(od), od["a"], od.get("z", 0))
od["b"] = 20
od["d"] = 4
del od["a"]
od["a"] = 5
print(list(od.items()))
od.move_to_end("b")
od.move_to_end("a", last=False)
print(list(od), m(lambda: od.move_to_end("zz")), m(lambda: OrderedDict().move_to_end("x")))  # type: ignore[arg-type,no-untyped-call]
print(od.popitem(), od.popitem(last=False), list(od), m(lambda: OrderedDict().popitem()))  # type: ignore[no-untyped-call]
print(od.pop("c"), od.pop("zz", "dflt"), m(lambda: od.pop("zz")), od.setdefault("d", 9), od.setdefault("e"), list(od.items()))  # type: ignore[call-arg,no-untyped-call]
c = od.copy()
od.clear()
print(od, c, type(c).__name__, c == OrderedDict([("d", 4), ("e", None)]))

o = OrderedDict.fromkeys("xyz", 0)
print(o, type(o).__name__, list(reversed(o)), list(reversed(o.keys())), list(reversed(o.values())), list(reversed(o.items())))
print(type(o.keys()).__name__, type(o.values()).__name__, type(o.items()).__name__, type(iter(o)).__name__, type(reversed(o)).__name__)
print(o.keys(), o.values(), o.items(), isinstance(o.keys(), type({}.keys())), o.keys() & {"x", "q"}, "y" in o.keys(), ("y", 0) in o.items())
print(issubclass(OrderedDict, dict), OrderedDict.__module__, OrderedDict.__name__, OrderedDict.__mro__)

p, q = OrderedDict(a=1, b=2), OrderedDict(b=2, a=1)
print(p == q, p != q, p == dict(q), dict(q) == p, p == {"b": 2, "a": 1}, p == [("a", 1), ("b", 2)], m(lambda: hash(p)))  # type: ignore[no-untyped-call]
print(p | {"c": 3}, {"c": 3} | p, type({"c": 3} | p).__name__, m(lambda: p | [("x", 1)]))  # type: ignore[no-untyped-call,operator]
p |= [("z", 26)]
print(p)

nested = OrderedDict(inner=OrderedDict(x=1))
nested["self"] = nested  # type: ignore[assignment]
print(nested, OrderedDict(), repr(OrderedDict({1: OrderedDict()})))


class Sub(OrderedDict):  # type: ignore[type-arg]
    def __setitem__(self, key, value):  # type: ignore[no-untyped-def]
        print("  set", key, value)
        super().__setitem__(key, value)

    def __missing__(self, key):  # type: ignore[no-untyped-def]
        return "missing " + str(key)


s = Sub([("k", 1)])
s.update({"l": 2}, m=3)
print(s, s["nope"], s.setdefault("n", 4), s.setdefault("k", 0))
t = s.copy()
print(type(t).__name__, t)


def mutate(f):  # type: ignore[no-untyped-def]
    d = OrderedDict(a=1, b=2, c=3)
    try:
        for k in d:
            f(d, k)
        return "done " + repr(list(d))
    except RuntimeError as e:
        return "RuntimeError " + str(e)


print(mutate(lambda d, k: d.__setitem__(k, 0)), mutate(lambda d, k: d.__setitem__("z", 0)), mutate(lambda d, k: d.move_to_end("a")),  # type: ignore[no-untyped-call]
      mutate(lambda d, k: d.pop("c", None)))  # type: ignore[no-untyped-call]

r = OrderedDict(a=1)
r.attr = "kept"  # type: ignore[attr-defined]
red = r.__reduce__()
print(red[0] is OrderedDict, red[1], red[2], red[3], list(red[4]))
print(copy.copy(r), copy.copy(r).attr, copy.deepcopy(OrderedDict(a=[1])), vars(r))  # type: ignore[attr-defined]
ref = weakref.ref(r)
print(ref() is r, vars(OrderedDict()))
print(m(lambda: OrderedDict(1, 2)), m(lambda: OrderedDict().update(1, 2)), m(lambda: OrderedDict([(1,)])), m(lambda: OrderedDict([(1, 2, 3)])),  # type: ignore[arg-type,call-overload,no-untyped-call]
      m(lambda: OrderedDict([1])), m(lambda: OrderedDict({[]: 1})))  # type: ignore[arg-type,no-untyped-call]


class Key:
    calls: list[str] = []  # noqa: RUF012

    def __init__(self, n: int) -> None:
        self.n = n

    def __hash__(self) -> int:
        Key.calls.append("hash " + str(self.n))
        return self.n % 2

    def __eq__(self, other: object) -> bool:
        Key.calls.append("eq " + str(self.n))
        return isinstance(other, Key) and self.n == other.n


k1, k2, k3 = Key(1), Key(2), Key(3)
h = OrderedDict()
h[k1] = 1
h[k2] = 2
h[k3] = 3
h[k1] = 10
h.move_to_end(k1)
del h[k2]
h.pop(k3)
print([x.n for x in h], Key.calls)
