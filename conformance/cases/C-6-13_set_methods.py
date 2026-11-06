# clause: C-6-13
# spec: section 6
# status: P1
# source: dialect specification section 6, Objects/setobject.c
"""set's and frozenset's named methods, with any iterable where the C takes one: the order a result iterates in,
which the operations decide by what they insert when; what set.pop's finger does; and what the same names do on
a dict, whose stored hashes the C reads."""
# ruff: noqa: B015, B018, B023, C405, C408, FURB171, RUF015, SIM118

def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


big = set(range(100))
few = {1, 2, 3}
other = {3, 4, 5}
print(few.union(other), few.union(), few.union([9], (8,), "a", {7: 1}, iter([6])), few.union(few), few.union(few, few), frozenset(few).union(other), type(frozenset(few).union(other)).__name__, type(few.union(frozenset(other))).__name__)
print(few.intersection(other), few.intersection(), few.intersection([1], (1, 2)), few.intersection(few), few.intersection({3: 1}), few.intersection(iter([3, 3, 1, 2, 9])), frozenset(few).intersection(other), type(frozenset(few).intersection([1])).__name__, big.intersection(few), few.intersection(big), big.intersection(range(5, 2, -1)))
print(few.difference(other), few.difference(), few.difference([1], [2]), few.difference(few), few.difference({1: 1}), big.difference(range(95)), big.difference({i: 1 for i in range(95)}), big.difference(set(range(95))), big.difference({1: 1}), big.difference({1}), frozenset(few).difference(other), type(frozenset(few).difference(other)).__name__)
print(few.symmetric_difference(other), few.symmetric_difference([1, 1, 9, 9]), few.symmetric_difference(few), few.symmetric_difference({1: 1, 9: 9}), few.symmetric_difference(frozenset(other)), frozenset(few).symmetric_difference(other), type(frozenset(few).symmetric_difference(other)).__name__, big.symmetric_difference(range(50, 150)))
print(few.isdisjoint(other), few.isdisjoint({9}), few.isdisjoint([9, 8]), few.isdisjoint([9, 1]), few.isdisjoint(few), set().isdisjoint(set()), few.isdisjoint(frozenset({9})), few.isdisjoint({9: 1}), few.isdisjoint("ab"), few.isdisjoint(big), big.isdisjoint(few))
print(few.issubset(big), big.issubset(few), few.issubset(few), few.issubset([1, 2, 3, 4]), few.issubset([1, 2]), few.issubset(iter([1, 2, 3])), few.issubset({1: 1, 2: 2, 3: 3}), set().issubset([]), few.issuperset({1}), few.issuperset(big), few.issuperset(few), few.issuperset([1, 1]), few.issuperset([9]), few.issuperset(iter([])), few.issuperset({1: 1}), frozenset(few).issubset(big), frozenset(few).issuperset([1]))

# ---- in place
s = {1, 2, 3}
print(s.intersection_update([1, 2], {2, 3}), s, s.intersection_update(), s, s.intersection_update(s), s)  # type: ignore[func-returns-value]
s = {1, 2, 3}
print(s.difference_update([1], {2}), s, s.difference_update(), s, s.difference_update(s), s)  # type: ignore[func-returns-value]
s = {1, 2, 3}
print(s.symmetric_difference_update([3, 4, 4]), s, s.symmetric_difference_update(s), s, s.symmetric_difference_update({5: 1}), s, s.symmetric_difference_update(frozenset({5})), s)  # type: ignore[func-returns-value]
s = {1, 2, 3}
t = s
s |= {4}
s &= {1, 4, 5}
s -= {1}
s ^= {7}
print(s, t is s, s.__ior__({8}), s.__iand__({8, 7}), s.__isub__({8}), s.__ixor__({9}), s, s.__ior__([1]), s.__iand__([1]), s.__isub__([1]), s.__ixor__([1]), failed(lambda: s.__ior__()), failed(lambda: s.__ior__(1, 2)))  # type: ignore[arg-type,call-arg]
f = frozenset({1})
g = f
f |= {2}
print(f, g, f is g, type(f).__name__)
print(failed(lambda: s.__dict__), hasattr(frozenset, "__ior__"), hasattr(frozenset, "clear"), hasattr(frozenset, "pop"), hasattr(frozenset, "add"), hasattr(frozenset, "update"), hasattr(frozenset, "__init__"))

# ---- copy, clear, pop, and the finger
c = {1, 2, 3}
d = c.copy()
d.add(4)
print(c, d, c.copy() == c, c.copy() is c, type(c.copy()).__name__, frozenset(c).copy(), type(frozenset(c).copy()).__name__, c.clear(), c, len(c), failed(lambda: c.pop()))  # type: ignore[func-returns-value]
fz = frozenset({1})
print(fz.copy() is fz, frozenset(fz) is fz, frozenset() == frozenset(), frozenset([1]) == {1}, frozenset(set(fz)) is fz)
p = set(range(20))
order = []
while p:
    order.append(p.pop())
print(order)
p = {5, 13, 21, 29}
print(p.pop(), p.pop(), p.add(5), p.pop(), p, p.pop(), p.pop() if p else "empty", p)  # type: ignore[func-returns-value]
p = set(range(10))
print(p.pop(), p.pop(), p.discard(5), p.pop(), p.add(100), p.pop(), list(p), p.clear(), p.add(3), p.add(11), p.pop(), p)  # type: ignore[func-returns-value]
p = set(range(10))
p.pop()
p.pop()
q = p.copy()
print(q.pop(), p.pop(), q == p)
p.intersection_update(range(100))
print(p.pop(), p)

# ---- what deleting does to a table: dummies are resized away by difference_update, and not by discard
w = set(range(64))
w.difference_update(range(0, 60))
print(w, list(w))
w = set(range(64))
for i in range(60):
    w.discard(i)
print(w, list(w))
w = set(range(1000))
w -= set(range(5, 1000))
print(w, w.pop())
for i in (100, 1000):
    x = set(range(i))
    x.difference_update(set(range(i * 20)))
    print(x)
    y = set(range(i))
    y.difference_update(range(5, i))
    y.add(i * 8 + 1)
    print(list(y))
strs = {"a", "b", "c", "dd", "eee"}
print(strs, strs.union("xyz"), strs.intersection("abc"), strs.difference(["a"]), strs.symmetric_difference(["a", "z"]), sorted(strs))

# ---- construction
print(set(), set([1, 1]), set("aab"), set({1: 2}), set(frozenset({1})), frozenset(), frozenset("aa"), frozenset({1}), set.__new__(set), set.__new__(set, [1, 2]), frozenset.__new__(frozenset, [1, 2]), frozenset.__new__(frozenset), failed(lambda: set(1)), failed(lambda: set(1, 2)), failed(lambda: set(x=1)), failed(lambda: frozenset(1)), failed(lambda: frozenset(1, 2)), failed(lambda: frozenset(x=1)), failed(lambda: set.__new__(int)), failed(lambda: set.__new__(1)), failed(lambda: frozenset.__new__(set)), failed(lambda: set.__new__()), failed(lambda: frozenset.__new__()))  # type: ignore[arg-type,call-arg,call-overload,type-var]
r = {1, 2}
print(r.__init__(), r, r.__init__([3]), r, r.__init__(r), r, failed(lambda: r.__init__(1, 2)), failed(lambda: r.__init__(x=1)), failed(lambda: r.__init__(1)), r)  # type: ignore[misc]
r = {1, 2}
print(failed(lambda: set.__init__(1)), failed(lambda: set.__init__()), r.__init__({3, 4}), r)  # type: ignore[call-overload,misc]


# ---- what the keys do
class Key:
    def __init__(self, n: int, log: list[str]) -> None:
        self.n = n
        self.log = log

    def __hash__(self) -> int:
        self.log.append("hash " + str(self.n))
        return 1

    def __eq__(self, o: object) -> bool:
        self.log.append("eq " + str(self.n))
        return isinstance(o, Key) and self.n == o.n

    def __repr__(self) -> str:
        return "K" + str(self.n)


log: list[str] = []
k1, k2, k3 = Key(1, log), Key(2, log), Key(3, log)
keys: set[object] = {k1, k2}
log.clear()


def step(name: str, f: object) -> None:
    result = failed(f)
    print(name, result, log)
    log.clear()


# a set's stored hashes and a dict's are read; an iterable's items are hashed
step("union set", lambda: keys.union({k3}))
step("union list", lambda: keys.union([k3]))
step("union dict", lambda: keys.union({k3: 1}))
step("intersection set", lambda: keys.intersection({k1}))
step("intersection list", lambda: keys.intersection([k1]))
step("difference set", lambda: keys.difference({k1}))
step("difference list", lambda: keys.difference([k1]))
step("difference dict", lambda: keys.difference({k1: 1}))
step("symmetric set", lambda: keys.symmetric_difference({k1}))
step("symmetric list", lambda: keys.symmetric_difference([k1]))
step("symmetric dict", lambda: keys.symmetric_difference({k1: 1}))
step("isdisjoint set", lambda: keys.isdisjoint({k3}))
step("isdisjoint list", lambda: keys.isdisjoint([k3]))
step("issubset set", lambda: keys.issubset({k1, k2, k3}))
step("issubset list", lambda: keys.issubset([k1, k2, k3]))
step("issuperset set", lambda: keys.issuperset({k1}))
step("issuperset list", lambda: keys.issuperset([k1]))
step("copy", lambda: keys.copy())
step("in", lambda: k1 in keys)


class Dies:
    def __init__(self, n: int) -> None:
        self.n = n

    def __del__(self) -> None:
        print("del", self.n, end="; ")

    def __hash__(self) -> int:
        return self.n


kept = [Dies(i) for i in range(4)]
held = set(kept)
del kept
item = held.pop()
print(item.n, len(held))
del item
print("popped")
held.clear()
print("cleared")
live = [Dies(i) for i in range(10, 13)]
h2 = set(live)
h3 = {live[0]}
del live
h2.difference_update(h3)
print("no death", len(h2))
del h3
print("deleted the other")
h2.intersection_update([])
print("intersected")
