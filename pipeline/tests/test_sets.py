"""set's and frozenset's named methods, compiled, against CPython.

Case C-6-13 shows the behaviour by exception class, as a case must; these compare messages too, walk sets through
generated operations printing them in full, since the order a set iterates in is decided by what went in when and
is part of what a program sees under a seed, and try displays of constants, which CPython folds.
"""
from __future__ import annotations

from typing import Any

from pipeline.tests.test_review_2026_11_03 import same

SHOW = """def show(f):
    try:
        r = f()
        s = repr(r)
        print(s if " at 0x" not in s else "<" + type(r).__name__ + ">")
    except BaseException as e:
        print(type(e).__name__, e)
"""

PROGRAMS: list[tuple[str, str]] = [
    ('messages', SHOW + r"""
s = {1}
fz = frozenset({1})
class It:
    def __iter__(self):
        raise KeyError("iter")
for f in (lambda: set.union(), lambda: set.union(1), lambda: s.union(x=1), lambda: s.union(1), lambda: s.union([[]]), lambda: s.union(It()), lambda: fz.union(1), lambda: fz.union(x=1), lambda: frozenset.union(1), lambda: frozenset.union(),
          lambda: s.intersection(1), lambda: s.intersection([[]]), lambda: s.intersection(x=1), lambda: s.intersection(It()), lambda: set.intersection(1), lambda: fz.intersection(1), lambda: s.intersection_update(1), lambda: s.intersection_update(x=1), lambda: s.intersection_update([[]]), lambda: set.intersection_update(1),
          lambda: s.difference(1), lambda: s.difference([[]]), lambda: s.difference(x=1), lambda: s.difference([1], 1), lambda: fz.difference(1), lambda: s.difference_update(1), lambda: s.difference_update([[]]), lambda: s.difference_update(x=1), lambda: set.difference_update(1),
          lambda: s.symmetric_difference(), lambda: s.symmetric_difference(1), lambda: s.symmetric_difference(1, 2), lambda: s.symmetric_difference(x=1), lambda: s.symmetric_difference([[]]), lambda: fz.symmetric_difference(1), lambda: fz.symmetric_difference(), lambda: s.symmetric_difference_update(), lambda: s.symmetric_difference_update(1), lambda: s.symmetric_difference_update([[]]), lambda: s.symmetric_difference_update(1, 2),
          lambda: s.isdisjoint(), lambda: s.isdisjoint(1, 2), lambda: s.isdisjoint(1), lambda: s.isdisjoint([[]]), lambda: s.isdisjoint([{1}]), lambda: s.isdisjoint(x=1), lambda: fz.isdisjoint(), lambda: s.issubset(), lambda: s.issubset(1), lambda: s.issubset([[]]), lambda: s.issubset(1, 2), lambda: fz.issubset(), lambda: s.issuperset(), lambda: s.issuperset(1), lambda: s.issuperset([[]]), lambda: s.issuperset([{1}]), lambda: s.issuperset(1, 2), lambda: fz.issuperset(),
          lambda: s.pop(1), lambda: s.pop(x=1), lambda: set().pop(), lambda: set.pop(1), lambda: s.copy(1), lambda: s.copy(x=1), lambda: fz.copy(1), lambda: set.copy(1), lambda: frozenset.copy(1), lambda: s.clear(1), lambda: s.clear(x=1), lambda: set.clear(1),
          lambda: s.__ior__(), lambda: s.__ior__(1, 2), lambda: s.__ior__(x=1), lambda: s.__ior__(1), lambda: s.__iand__(1), lambda: s.__isub__(1), lambda: s.__ixor__(1), lambda: set.__ior__(1, 2), lambda: set.__ior__(), lambda: fz.__ior__,
          lambda: s.__init__(1, 2), lambda: s.__init__(x=1), lambda: s.__init__(1), lambda: set.__init__(1), lambda: set.__init__(), lambda: fz.__init__(1, 2), lambda: set(1), lambda: set(1, 2), lambda: set(x=1), lambda: set([[]]), lambda: frozenset(1), lambda: frozenset(1, 2), lambda: frozenset(x=1), lambda: frozenset([[]]), lambda: set.__new__(), lambda: set.__new__(int), lambda: set.__new__(1), lambda: set.__new__(frozenset), lambda: frozenset.__new__(), lambda: frozenset.__new__(int), lambda: frozenset.__new__(1), lambda: frozenset.__new__(set), lambda: frozenset.__new__(frozenset, 1, 2), lambda: frozenset.__new__(frozenset, x=1),
          lambda: s | 1, lambda: 1 | s, lambda: s & 1, lambda: s - 1, lambda: s ^ 1, lambda: s | [1], lambda: s <= [1], lambda: s.add, lambda: s.add(), lambda: s.add([]), lambda: s.remove(), lambda: s.remove(9), lambda: s.remove([]), lambda: s.discard(), lambda: s.discard([]), lambda: {1} in {frozenset({1})}, lambda: {1} in {1}, lambda: [] in {1}, lambda: s.remove({1}), lambda: s.discard({1}), lambda: fz.add, lambda: fz.clear, lambda: fz.pop, lambda: fz.update, lambda: fz.discard, lambda: fz.remove, lambda: fz.intersection_update, lambda: fz.difference_update, lambda: fz.symmetric_difference_update):
    show(f)
print(sorted(set(dir(set)) - set(dir(object))), sorted(set(dir(frozenset)) - set(dir(object))))
"""),
    ('a_walk', r"""
state = 88172645463325252
def word():
    global state
    state ^= (state << 13) & 0xFFFFFFFFFFFFFFFF
    state ^= state >> 7
    state ^= (state << 17) & 0xFFFFFFFFFFFFFFFF
    return state
def pick(w):
    n = w % 40
    start = (w >> 8) % 200
    step = (w >> 16) % 5 + 1
    kind = (w >> 24) % 5
    values = list(range(start, start + n * step, step))
    if kind == 0:
        return values
    if kind == 1:
        return set(values)
    if kind == 2:
        return frozenset(values)
    if kind == 3:
        return {v: 1 for v in values}
    return tuple(["s" + str(v) for v in values])
for round in range(40):
    s = set(pick(word()))
    for step in range(120):
        w = word()
        op = w % 15
        x = pick(w >> 8)
        if op == 0: s = s.union(x)
        elif op == 1: s = s.intersection(x)
        elif op == 2: s = s.difference(x)
        elif op == 3: s = s.symmetric_difference(x)
        elif op == 4: s.update(x)
        elif op == 5: s.intersection_update(x)
        elif op == 6: s.difference_update(x)
        elif op == 7: s.symmetric_difference_update(x)
        elif op == 8 and s: print(s.pop())
        elif op == 9: s.add(w % 300)
        elif op == 10: s.discard(w % 300)
        elif op == 11: print(s.isdisjoint(x), s.issubset(x), s.issuperset(x))
        elif op == 12: s = s.copy()
        elif op == 13 and isinstance(x, (set, frozenset)): s |= x; s &= set(range(250)); s -= x; s ^= set(list(x)[:5])
        elif op == 14 and w & 0x100000: s = set(frozenset(s))
        print(s)
"""),
    ('displays_of_constants', r"""
print({1, 2, 3}, {1, 2}, {1}, {"a", "b", "c", "dd", "eee"}, {"a", "b"}, {1.5, 2.5, 3.5, 4.5, 5.5}, {None, True, 1.5, "a", b"b"}, {(1, 2), (3, 4), (5, 6)}, {-1, -2, -3, -4, -5}, {1 + 1, 2 * 3, 2 ** 3, 7 // 2, 7 % 3}, {not 1, not 0, 5, 6, 7}, {"a" + "b", "c" * 2, "d", "e", "f"})
print({0, 8, 16, 24, 32}, {0, 8, 16, 24, 32, 40, 48, 56, 64, 72}, {64, 56, 48, 40, 32, 24, 16, 8, 0}, {31, 15, 7, 3, 1}, {1, 9, 17, 25, 33}, {5, 13, 21, 29, 37, 45})
x = 8
print({0, x, 16, 24, 32}, {x, 16, 0, 24, 32}, {0, 8, 16, 24, *[32]}, {*[0, 8, 16, 24, 32]}, {0, 8, 16, 24, 32, *[]}, {0, 8, 16, (x, 24), 32}, set([0, 8, 16, 24, 32]), set((0, 8, 16, 24, 32)), frozenset({0, 8, 16, 24, 32}), frozenset([0, 8, 16, 24, 32]))
print([y for y in {0, 8, 16, 24, 32}], [y for z in [1] for y in {0, 8, 16, 24, 32}], {y for y in {0, 8, 16, 24, 32}}, [y for y in {0, 8}], {i for i in (0, 8, 16, 24, 32)}, {0, 8, 16, 24, 32}.pop(), list({0, 8, 16, 24, 32}), sorted({0, 8, 16, 24, 32}), len({0, 0, 0, 8, 8}), {1, 1.0, True}, {0, 0.0, False, -0.0}, {1.0, 1, True}, {True, 1, 1.0})
print({0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34})
print({"s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9", "s10", "s11", "s12", "s13", "s14", "s15", "s16", "s17", "s18", "s19", "s20", "s21", "s22", "s23", "s24", "s25", "s26", "s27", "s28", "s29", "s30", "s31"})
def f():
    return {0, 8, 16, 24, 32}
print(f(), f() is f(), f() == f(), 8 in {0, 8, 16}, x in {0, 8, 16}, x not in {0, 8, 16}, [y for y in {0, 8, 16}], *{0, 8, 16, 24, 32})
for y in {0, 8, 16, 24, 32}:
    print(y, end=" ")
for y in {"a", "b", "c", "dd", "eee", "f"}:
    print(y, end=" ")
for y in {0, 8}:
    print(y, end=" ")
for y in {0, 8, 16, 24, 32, *[]}:
    print(y, end=" ")
for y in {0, x, 16, 24, 32}:
    print(y, end=" ")
for y in {-1, 2**3, 16, 24, 32}:
    print(y, end=" ")
for i, y in enumerate({0, 8, 16, 24, 32}):
    print(y, end=" ")
a, b, c, d, e = {0, 8, 16, 24, 32}
print(a, b, c, d, e, 1 in {0, 8, 16}, 8 in {0, 8, 16}, [] in {1} if False else 0)
try:
    print([] in {0, 8, 16})
except TypeError as exc:
    print(exc)
try:
    print({} not in {0, 8, 16})
except TypeError as exc:
    print(exc)
"""),
    ('chain_map', r"""
from collections import ChainMap
m = ChainMap({"a": 1}, {"a": 2, "b": 3})
print(m["a"], m["b"], len(m), sorted(m), list(m), m, m.maps, m.parents, m.new_child({"c": 4}), m.new_child(c=4)["c"], "a" in m, "z" in m, m.get("z", 9), bool(ChainMap()), bool(m))
m["n"] = 1
del m["n"]
print(m, m.copy(), ChainMap.fromkeys("ab", 1))
for f in (lambda: m["z"], lambda: m.__delitem__("b"), lambda: m.pop("b"), lambda: ChainMap().popitem(), lambda: m.pop("z")):
    try:
        print(f())
    except KeyError as e:
        print(type(e).__name__, e)
print(m.popitem(), m.pop("a", 9), m)
"""),
]


def pytest_generate_tests(metafunc: Any) -> None:
    if "program" in metafunc.fixturenames:
        metafunc.parametrize("program", PROGRAMS, ids=[name for name, _ in PROGRAMS])


def test_as_cpython(program: tuple[str, str]) -> None:
    same(program[1])


if __name__ == "__main__":
    for item in PROGRAMS:
        test_as_cpython(item)
