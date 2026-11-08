# clause: C-6-19
# spec: section 6
# status: P1
# source: dialect specification section 6, Objects/dictobject.c (dictviews_sub, _PyDictView_Intersect, dictviews_or, dictviews_xor,
#         dictview_richcompare, dictviews_isdisjoint, dictitems_contains)
"""The set operations of dict keys and items views: `-`, `&`, `|` and `^` with a set, another view, a list, a tuple, a string, a
generator or a dict on either side (the result is a set; the other side is any iterable, and the reflected forms copy that side into
the set first), the in-place forms, the comparisons `==`, `!=`, `<`, `<=`, `>`, `>=` against sets, frozensets and views (another
type is NotImplemented, so `==` is False and `<` fails), isdisjoint, an items view's membership and hashing of its pairs, the values
view's absence from all of it, the keys and items looked up and the errors (unhashable values, an operand that is no iterable)."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, E741, E742, F601, PLR0133, SLF001


def m(f):  # type: ignore[no-untyped-def]
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


def s(f):  # type: ignore[no-untyped-def]  # a set, sorted for printing
    try:
        v = f()
    except Exception as e:
        return type(e).__name__ + ": " + str(e)
    return (type(v).__name__, sorted(v, key=repr)) if isinstance(v, (set, frozenset)) else repr(v)


d = {"a": 1, "b": 2, "c": 3}
e = {"b": 20, "c": 3, "d": 4}
k, i, v = d.keys(), d.items(), d.values()
print("types:", type(k).__name__, type(i).__name__, type(v).__name__, len(k), len(i), len(v), "a" in k, ("a", 1) in i, ("a", 2) in i, ("a",) in i, "a" in i, 1 in v, k.mapping is d, i.mapping["a"], type(k.mapping).__name__, m(lambda: hash(k)), m(lambda: hash(i)), list(reversed(k)), list(reversed(i)), list(reversed(v)))  # type: ignore[no-untyped-call,operator]
print("sub:", s(lambda: k - e.keys()), s(lambda: k - {"a"}), s(lambda: k - ["a", "x"]), s(lambda: k - ("b",)), s(lambda: k - "ab"), s(lambda: k - (c for c in "c")), s(lambda: k - e), s(lambda: k - k), s(lambda: e.keys() - k), s(lambda: {"a", "z"} - k), s(lambda: frozenset({"a", "z"}) - k), s(lambda: ["a", "z", "z"] - k), s(lambda: ("a", "z") - k), s(lambda: "az" - k), s(lambda: {"z": 1} - k), s(lambda: i - e.items()), s(lambda: i - {("a", 1)}), s(lambda: i - [("a", 1), ("b", 3)]), s(lambda: {("a", 1), ("z", 9)} - i), s(lambda: e.items() - i), s(lambda: k - 5), s(lambda: 5 - k), s(lambda: k - None), s(lambda: k - v), s(lambda: v - k), s(lambda: k - e.values()), s(lambda: i - k), s(lambda: k - i))  # type: ignore[no-untyped-call,operator]
print("and:", s(lambda: k & e.keys()), s(lambda: k & {"a", "c", "z"}), s(lambda: k & ["a", "c", "c", "z"]), s(lambda: k & ("b",)), s(lambda: k & "cz"), s(lambda: k & (c for c in "ab")), s(lambda: k & e), s(lambda: k & k), s(lambda: {"a", "z"} & k), s(lambda: frozenset({"c"}) & k), s(lambda: ["a", "a", "z"] & k), s(lambda: "ca" & k), s(lambda: {"a": 0} & k), s(lambda: i & e.items()), s(lambda: i & {("a", 1), ("b", 3)}), s(lambda: i & [("c", 3)]), s(lambda: {("a", 1)} & i), s(lambda: [("a", 1), ("a", 1)] & i), s(lambda: k & 5), s(lambda: 5 & k), s(lambda: k & v), s(lambda: v & k), s(lambda: i & k), s(lambda: k & i), s(lambda: k & [["x"]]), s(lambda: k & set()), s(lambda: set() & k))  # type: ignore[no-untyped-call,operator]
print("or:", s(lambda: k | e.keys()), s(lambda: k | {"z"}), s(lambda: k | ["z", "z"]), s(lambda: k | ("a",)), s(lambda: k | "zy"), s(lambda: k | (c for c in "q")), s(lambda: k | e), s(lambda: k | k), s(lambda: {"z"} | k), s(lambda: frozenset() | k), s(lambda: ["z"] | k), s(lambda: "zy" | k), s(lambda: {"z": 1} | k), s(lambda: i | e.items()), s(lambda: i | {("z", 26)}), s(lambda: i | [("a", 1)]), s(lambda: {("z", 26)} | i), s(lambda: k | 5), s(lambda: 5 | k), s(lambda: k | v), s(lambda: v | k), s(lambda: k | [["x"]]), s(lambda: i | k), s(lambda: k | i))  # type: ignore[no-untyped-call,operator]
print("xor:", s(lambda: k ^ e.keys()), s(lambda: k ^ {"a", "z"}), s(lambda: k ^ ["a", "z", "z"]), s(lambda: k ^ ("a",)), s(lambda: k ^ "az"), s(lambda: k ^ (c for c in "a")), s(lambda: k ^ e), s(lambda: k ^ k), s(lambda: {"a", "z"} ^ k), s(lambda: frozenset({"a"}) ^ k), s(lambda: ["a", "z"] ^ k), s(lambda: "az" ^ k), s(lambda: {"a": 0, "z": 0} ^ k), s(lambda: i ^ e.items()), s(lambda: i ^ {("a", 1), ("z", 26)}), s(lambda: {("a", 1)} ^ i), s(lambda: k ^ 5), s(lambda: 5 ^ k), s(lambda: k ^ v), s(lambda: v ^ k), s(lambda: k ^ [["x"]]), s(lambda: i ^ k), s(lambda: k ^ i))  # type: ignore[no-untyped-call,operator]


def inplace(op):  # type: ignore[no-untyped-def]
    x = d.keys()
    y = x
    if op == "-":
        x -= {"a"}  # type: ignore[assignment]
    elif op == "&":
        x &= ["a", "b"]  # type: ignore[assignment]
    elif op == "|":
        x |= ("z",)  # type: ignore[assignment]
    else:
        x ^= "az"  # type: ignore[assignment]
    return (type(x).__name__, sorted(x), x is y, type(y).__name__, sorted(d))


print("inplace:", inplace("-"), inplace("&"), inplace("|"), inplace("^"), m(lambda: d.values().__ior__({1})), m(lambda: type(d.keys().__or__).__name__), m(lambda: d.keys().__ior__), m(lambda: d.keys().__rsub__({1})), m(lambda: d.keys().__sub__({"a"}) == {"b", "c"}), m(lambda: d.keys().__and__([1, 2])), m(lambda: d.keys().__sub__(5)), m(lambda: d.keys().__rand__("abc") == {"a", "b", "c"}), m(lambda: d.values().__sub__), m(lambda: d.items().__xor__({("a", 1)}) == {("b", 2), ("c", 3)}))  # type: ignore[attr-defined,no-untyped-call,operator]
print("compare sets:", k == {"a", "b", "c"}, k == {"a", "b"}, k != {"a", "b"}, k == frozenset("abc"), k <= {"a", "b", "c"}, k < {"a", "b", "c"}, k < {"a", "b", "c", "d"}, k <= {"a", "b"}, k >= {"a"}, k > {"a"}, k > {"a", "b", "c"}, k >= {"a", "b", "c", "d"}, {"a"} < k, {"a", "b", "c"} <= k, {"a", "b", "c", "d"} > k, {"a", "b", "c", "d"} >= k, frozenset({"a"}) < k, set() < k, k > set(), k >= set(), k == set(), set() == k, k != set())
print("compare views:", k == e.keys(), k == d.keys(), k != e.keys(), k <= d.keys(), k < d.keys(), k >= d.keys(), k > d.keys(), {"b": 1, "c": 2}.keys() < k, {"b": 1, "c": 2}.keys() <= k, k > {"b": 1, "c": 2}.keys(), k < {"b": 1}.keys(), i == {("a", 1), ("b", 2), ("c", 3)}, i == d.items(), i == e.items(), i < {("a", 1), ("b", 2), ("c", 3), ("d", 4)}, i <= {("a", 1), ("b", 2), ("c", 3)}, i > {("a", 1)}, i >= e.items(), {("a", 1)} < i, {("a", 1)} <= i, i == k, k == i, i != k, i == {"a", "b", "c"}, k == {("a", 1)}, k == v, v == k, v == v, v == d.values(), v == [1, 2, 3], k == ["a", "b", "c"], k == ("a", "b", "c"), k != ["a", "b", "c"], i == [("a", 1)], k == "abc", k == {"a": 1, "b": 2, "c": 3}, k == 5)  # type: ignore[comparison-overlap]
print("compare errors:", m(lambda: k < ["a"]), m(lambda: k <= ("a",)), m(lambda: k > "ab"), m(lambda: k >= d), m(lambda: ["a"] < k), m(lambda: k < v), m(lambda: v < k), m(lambda: v <= v), m(lambda: i < k), m(lambda: k < i), m(lambda: k < 5), m(lambda: k <= None), m(lambda: i > {1}), m(lambda: i >= {("a", 1), 2}))  # type: ignore[no-untyped-call,operator]
print("isdisjoint:", k.isdisjoint({"z"}), k.isdisjoint({"a"}), k.isdisjoint(["z", "a"]), k.isdisjoint(e.keys()), k.isdisjoint({"d": 1}.keys()), k.isdisjoint("xyz"), k.isdisjoint("xa"), k.isdisjoint(c for c in "q"), k.isdisjoint(k), k.isdisjoint(set()), {}.keys().isdisjoint(k), k.isdisjoint(e), i.isdisjoint({("a", 1)}), i.isdisjoint({("a", 2)}), i.isdisjoint([("b", 2), ("z", 0)]), i.isdisjoint(e.items()), i.isdisjoint(k), k.isdisjoint(i), i.isdisjoint(["a"]), i.isdisjoint([("a",)]), m(lambda: k.isdisjoint(5)), m(lambda: k.isdisjoint()), m(lambda: k.isdisjoint({"a"}, {"b"})), m(lambda: v.isdisjoint({1})), m(lambda: k.isdisjoint([["x"]])), m(lambda: k.isdisjoint(other={"a"})), k.isdisjoint(v), k.isdisjoint({1: 2}.values()))  # type: ignore[arg-type,attr-defined,call-arg,list-item,no-untyped-call]
u = {"a": [1], "b": [2]}
ui = u.items()
print("unhashable values:", m(lambda: ("a", [1]) in ui), m(lambda: ("a", [2]) in ui), m(lambda: ("z", [1]) in ui), m(lambda: ui - {("a", 1)}), m(lambda: ui | set()), m(lambda: ui & {("a", 1)}), m(lambda: ui & [("a", [1])]), m(lambda: ui ^ set()), m(lambda: ui == {("a", 1)}), m(lambda: ui == u.items()), m(lambda: {("a", 1)} == ui), m(lambda: ui <= {("a", 1)}), m(lambda: ui.isdisjoint({("a", 1)})), m(lambda: ui.isdisjoint([("a", [1])])), m(lambda: ui.isdisjoint([("z", [1])])), s(lambda: ui & [("a", [1]), ("b", [3])]), s(lambda: ui & [("c", [1])]), m(lambda: k & [["x"]]), m(lambda: k - [["x"]]), m(lambda: k.isdisjoint([["x"]])), m(lambda: k | [["x"]]), m(lambda: k ^ [["x"]]), m(lambda: {"a": 1}.keys() & [["x"], "a"]), m(lambda: set([["x"]]) - k))  # type: ignore[arg-type,list-item,no-untyped-call]


class Eq:
    def __init__(self, tag, eq=True):  # type: ignore[no-untyped-def]
        self.tag = tag
        self.eq = eq

    def __eq__(self, o):  # type: ignore[no-untyped-def]
        print("  eq", self.tag, getattr(o, "tag", o))
        return self.eq

    def __hash__(self):  # type: ignore[no-untyped-def]
        return 7

    def __repr__(self):  # type: ignore[no-untyped-def]
        return "Eq(" + str(self.tag) + ")"


print("lookups:")
dd = {"x": Eq("vx"), "y": Eq("vy", False)}  # type: ignore[no-untyped-call]
print(" ", ("x", Eq("probe")) in dd.items(), ("y", Eq("probe2")) in dd.items(), ("z", Eq("probe3")) in dd.items())  # type: ignore[no-untyped-call]
print(" ", dd.items().isdisjoint([("x", Eq("p4"))]), dd.items().isdisjoint([("y", Eq("p5"))]))  # type: ignore[no-untyped-call]
kd = {Eq("k1"): 1, Eq("k2"): 2}  # type: ignore[no-untyped-call]
print(" ", s(lambda: kd.keys() & [Eq("q1")]), s(lambda: kd.keys() - [Eq("q2")]), kd.keys() == {Eq("q3")}, kd.keys() <= {Eq("q4"), Eq("q5", False)})  # type: ignore[no-untyped-call]


class Keys(dict):  # type: ignore[type-arg]
    def keys(self):  # type: ignore[no-untyped-def]
        return "shadowed"


print("subclass:", m(lambda: Keys(a=1).keys()), m(lambda: dict.keys(Keys(a=1)) - {"a"}), m(lambda: type(dict.keys(Keys(a=1))).__name__), m(lambda: dict.keys(Keys(a=1)) == {"a"}))  # type: ignore[no-untyped-call]
grow = {1: 1, 2: 2}


class Grows:
    def __hash__(self):  # type: ignore[no-untyped-def]
        return 1

    def __eq__(self, o):  # type: ignore[no-untyped-def]
        grow[len(grow) + 10] = 0
        return False


print("mutation:", m(lambda: grow.keys() & [Grows(), Grows()]), sorted(grow), m(lambda: grow.keys() - [Grows()]), sorted(grow), m(lambda: sorted(grow.keys() | [9])), m(lambda: {}.keys() | []), m(lambda: {}.items() ^ {}.items()), m(lambda: {}.keys() == set()), m(lambda: {}.keys() < set()), m(lambda: {}.keys() <= {}.keys()))  # type: ignore[no-untyped-call]
