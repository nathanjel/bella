"""collections.deque, defaultdict and the helpers of `_collections`, compiled, against CPython.

Case C-7-23 shows the behaviour by exception class, as a case must; these compare messages too, walk a deque
through generated operations next to a model everything can check, and use the classes `collections` builds on
top: Counter, UserDict, UserList. `list` slice assignment arrived with the deque, and is tested here.
"""
from __future__ import annotations

import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from pipeline.build import build
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
    ('deque_messages', SHOW + r"""
import _collections
from collections import deque
d = deque([1, 2, 3])
class Bad:
    def __index__(self):
        return "a"
for f in (lambda: deque(1), lambda: deque([], "a"), lambda: deque([], 1.5), lambda: deque([], -1), lambda: deque([], 2**70), lambda: deque([], Bad()), lambda: deque([], 1, 2), lambda: deque(x=1), lambda: deque([1], iterable=[2]), lambda: deque([1], 1, maxlen=2), lambda: deque(iterable=[1], maxlen=1, x=2), lambda: deque.__new__(), lambda: deque.__new__(int), lambda: deque.__new__(1), lambda: deque.__init__(), lambda: deque.__init__(1),
          lambda: d.append(), lambda: d.append(1, 2), lambda: d.append(x=1), lambda: d.appendleft(), lambda: d.extend(), lambda: d.extend(1), lambda: d.extendleft(1), lambda: d.extendleft(), lambda: d.pop(1), lambda: d.pop(x=1), lambda: d.popleft(1), lambda: d.clear(1), lambda: d.copy(1), lambda: d.__copy__(1), lambda: d.reverse(1),
          lambda: d.rotate("a"), lambda: d.rotate(1.5), lambda: d.rotate(1, 2), lambda: d.rotate(x=1), lambda: d.rotate(2**70), lambda: d.count(), lambda: d.count(1, 2), lambda: d.index(), lambda: d.index(1, 2, 3, 4), lambda: d.index(1, "a"), lambda: d.index(1, 0, "a"), lambda: d.index(1, None), lambda: d.index(x=1), lambda: d.index(9), lambda: d.index(1, 2**70), lambda: d.index(3, -(2**70), 2**70), lambda: d.insert(), lambda: d.insert(1), lambda: d.insert(1, 2, 3), lambda: d.insert("a", 1), lambda: d.insert(1.5, 1), lambda: d.insert(2**70, 1), lambda: d.insert(x=1), lambda: d.remove(), lambda: d.remove(9), lambda: d.remove(1, 2),
          lambda: d[10], lambda: d[-10], lambda: d["a"], lambda: d[1:2], lambda: d[1.5], lambda: d[None], lambda: d[2**70], lambda: d[-(2**70)], lambda: d.__getitem__(10), lambda: d.__getitem__("a"), lambda: d.__getitem__(1.5), lambda: d.__getitem__(2**70), lambda: d.__getitem__(), lambda: d.__getitem__(1, 2), lambda: d.__getitem__(x=1),
          lambda: d.__setitem__(10, 1), lambda: d.__setitem__("a", 1), lambda: d.__setitem__(2**70, 1), lambda: d.__setitem__(1), lambda: d.__delitem__(10), lambda: d.__delitem__("a"), lambda: d.__delitem__(2**70), lambda: d.__delitem__(), lambda: d.__len__(1), lambda: d.__iter__(1), lambda: d.__reversed__(1), lambda: d.__contains__(), lambda: d.__contains__(1, 2),
          lambda: d + 1, lambda: 1 + d, lambda: d + [1], lambda: [1] + d, lambda: d.__add__(1), lambda: d.__add__(), lambda: d * "a", lambda: "a" * d, lambda: d * 1.5, lambda: 1.5 * d, lambda: d * [1], lambda: [1] * d, lambda: d * d, lambda: d * 2**70, lambda: 2**70 * d, lambda: d.__mul__("a"), lambda: d.__mul__(1.5), lambda: d.__mul__(2**70), lambda: d.__mul__(), lambda: d.__rmul__("a"), lambda: d.__imul__("a"), lambda: d.__iadd__(1), lambda: d.__iadd__(), lambda: d - 1, lambda: d / 1, lambda: d // 1, lambda: d % 1, lambda: d ** 1, lambda: -d, lambda: +d, lambda: abs(d), lambda: ~d, lambda: d @ d, lambda: d < 1, lambda: 1 < d, lambda: d < [1], lambda: deque(["a"]) < deque([1]), lambda: d.__lt__(), lambda: d.__eq__(1, 2), lambda: hash(d), lambda: {d}, lambda: {d: 1}, lambda: d.x, lambda: setattr(d, "x", 1), lambda: setattr(d, "maxlen", 1), lambda: delattr(d, "maxlen"), lambda: d.__dict__, lambda: d.__weakref__,
          lambda: deque.append(), lambda: deque.append(1, 2), lambda: deque.pop(), lambda: deque.pop(1), lambda: deque.__len__(), lambda: deque.__len__(1), lambda: deque.__getitem__(1, 2), lambda: deque.__add__(1, 2), lambda: deque.__repr__(1), lambda: deque.__iter__(1), lambda: deque.__eq__(1, 2), lambda: deque.maxlen.__get__(1),
          lambda: _collections._deque_iterator(), lambda: _collections._deque_iterator(1), lambda: _collections._deque_iterator(d, "a"), lambda: _collections._deque_iterator(d, 1, 2), lambda: _collections._deque_iterator(deque=d), lambda: type("X", (_collections._deque_iterator,), {}), lambda: type("X", (_collections._deque_reverse_iterator,), {}), lambda: _collections._deque_reverse_iterator(1), lambda: iter(d).__next__(1), lambda: iter(d).__iter__(1), lambda: iter(d).__length_hint__(1), lambda: iter(d).x, lambda: setattr(iter(d), "x", 1)):
    show(f)
print(repr(deque), repr(type(iter(d))), repr(type(reversed(d))), deque.__doc__ is not None, deque.__hash__, deque.maxlen, type(deque.maxlen).__name__, deque.maxlen.__name__, deque.maxlen.__qualname__, deque.maxlen.__objclass__)
print(deque.__mro__, deque.__bases__, sorted(deque.__dict__) == sorted(set(deque.__dict__)))
"""),
    ('a_deque_walked', r"""
from collections import deque
state = 88172645463325252
def word():
    global state
    state ^= (state << 13) & 0xFFFFFFFFFFFFFFFF
    state ^= state >> 7
    state ^= (state << 17) & 0xFFFFFFFFFFFFFFFF
    return state
for maxlen in (None, 0, 1, 2, 5, 40):
    d = deque(maxlen=maxlen)
    for step in range(3000):
        w = word()
        op = w % 24
        v = (w >> 8) % 1000
        try:
            if op < 4: d.append(v)
            elif op < 8: d.appendleft(v)
            elif op < 10: d.pop()
            elif op < 12: d.popleft()
            elif op == 12: d.rotate(v % 50 - 25)
            elif op == 13: d.reverse()
            elif op == 14: d.extend([v, v + 1, v + 2])
            elif op == 15: d.extendleft([v, v + 1, v + 2])
            elif op == 16: d.insert(v % 40 - 20, v)
            elif op == 17: d.remove(d[v % len(d)])
            elif op == 18: del d[v % (2 * len(d)) - len(d)]
            elif op == 19: d[v % (2 * len(d)) - len(d)] = v
            elif op == 20: print(d.index(d[v % len(d)]), d.count(d[0]), d[-1] in d)
            elif op == 21: d = d.copy()
            elif op == 22 and len(d) < 40: d *= 2
            elif op == 23 and step % 97 == 0: d.clear()
        except (IndexError, ZeroDivisionError) as e:
            print(type(e).__name__, e)
        if step % 7 == 0:
            print(d, len(d), list(reversed(d)) == list(d)[::-1])
"""),
    ('defaultdict_messages', SHOW + r"""
from collections import defaultdict
d = defaultdict(int)
class Raises:
    def __call__(self):
        raise KeyError("from factory")
for f in (lambda: defaultdict(1), lambda: defaultdict("a"), lambda: defaultdict([]), lambda: defaultdict(int, 1), lambda: defaultdict(int, 1, 2), lambda: defaultdict(int, [1]), lambda: defaultdict(int, [(1,)]), lambda: defaultdict(x=1), lambda: defaultdict(None)["x"], lambda: defaultdict()["x"], lambda: defaultdict(None).__missing__("x"), lambda: defaultdict(None).__missing__((1, 2)), lambda: defaultdict(Raises())["x"], lambda: defaultdict(lambda a: 1)["x"], lambda: d.__missing__(), lambda: d.__missing__(1, 2), lambda: d.__missing__(x=1), lambda: d.__missing__([]), lambda: d[[]], lambda: d.copy(1), lambda: d.__copy__(1), lambda: d.__reduce__(1), lambda: d.__or__(), lambda: d.__or__(1, 2), lambda: d.__ror__(), lambda: d | 1, lambda: 1 | d, lambda: d.__or__(1), lambda: d.__ror__(1), lambda: d.__repr__(1), lambda: hash(d), lambda: setattr(d, "x", 1), lambda: d.x, lambda: d.__dict__, lambda: d.__weakref__, lambda: defaultdict.__missing__(1, 2), lambda: defaultdict.__missing__(), lambda: defaultdict.__repr__(1), lambda: defaultdict.copy(1), lambda: defaultdict.__or__(1, 2), lambda: defaultdict.__init__(1), lambda: defaultdict.__init__(), lambda: defaultdict.default_factory.__get__(1), lambda: defaultdict.default_factory.__set__(1, 2), lambda: defaultdict.default_factory.__name__, lambda: defaultdict.default_factory.__objclass__, lambda: defaultdict.default_factory.__qualname__):
    show(f)
class S(defaultdict):
    __slots__ = ("a",)
class T(defaultdict):
    def __init__(self):
        super().__init__(list)
class U(defaultdict):
    default_factory = 5
s = S(int)
s.a = 1
print(s, s.a, s["k"], sorted(S.__dict__), T()["k"], T(), type(T()).__name__, U(int).default_factory, U.default_factory, s.__reduce__()[1], list(s.__reduce__()[4]))
show(lambda: T().copy())
show(lambda: T() | {})
show(lambda: {} | T())
show(lambda: setattr(s, "b", 1))
show(lambda: S.__mro__)
show(lambda: defaultdict.__mro__)
print(defaultdict.__name__, defaultdict.__qualname__, defaultdict.__module__, repr(defaultdict), defaultdict.__doc__ is not None, defaultdict[int], defaultdict[int, str])
print(sorted(defaultdict(int, a=1).items()), list(defaultdict(int, a=1)), list(defaultdict(int, a=1).keys()), list(defaultdict(int, a=1).values()), defaultdict(int, a=1).get("a"), defaultdict(int, a=1) == {"a": 1}, {"a": 1} == defaultdict(int, a=1), len(defaultdict(int, a=1)), defaultdict(int, a=1).pop("a"), defaultdict(int, a=1).popitem(), dict(defaultdict(int, a=1)), defaultdict(int, a=1).setdefault("b", 2), bool(defaultdict()), repr(defaultdict(lambda: 1, a=1)).split(" at ")[0], str(defaultdict(int, a=[1, {2: 3}])))
"""),
    ('tuplegetter_and_counting', SHOW + r"""
import _collections
g = _collections._tuplegetter(1, "doc")
class T:
    x = _collections._tuplegetter(0, "first")
for f in (lambda: _collections._tuplegetter(), lambda: _collections._tuplegetter(1), lambda: _collections._tuplegetter(1, 2, 3), lambda: _collections._tuplegetter("a", 1), lambda: _collections._tuplegetter(1.5, 1), lambda: _collections._tuplegetter(2**70, 1), lambda: _collections._tuplegetter(index=1, doc=2), lambda: _collections._tuplegetter.__new__(int, 1, 2), lambda: _collections._tuplegetter.__new__(1, 1, 2), lambda: g.__get__(), lambda: g.__get__(1, 2, 3), lambda: g.__get__(1), lambda: g.__get__("a"), lambda: g.__get__([1, 2]), lambda: g.__get__((1,)), lambda: g.__get__(()), lambda: g.__get__(None), lambda: g.__get__(None, None), lambda: g.__get__(None, int) is g, lambda: g.__get__(x=1), lambda: g.__set__(1), lambda: g.__set__((1, 2), 3), lambda: g.__set__(1, 3), lambda: g.__delete__((1, 2)), lambda: g.__delete__(), lambda: g.__reduce__(1), lambda: g.__repr__(1), lambda: g.x, lambda: setattr(g, "x", 1), lambda: type("X", (_collections._tuplegetter,), {}), lambda: T.x, lambda: T().x, lambda: _collections._tuplegetter.__doc__, lambda: _collections._tuplegetter.__dict__["__doc__"], lambda: g.__doc__, lambda: _collections._tuplegetter(1, None).__doc__, lambda: _collections._tuplegetter(1, [1]).__doc__, lambda: _collections._tuplegetter(1, [1]), lambda: _collections._tuplegetter(-1, "n"), lambda: _collections._tuplegetter(-1, "n").__get__((1, 2)), lambda: _collections._tuplegetter(5, "n").__get__((1, 2))):
    show(f)
for f in (lambda: _collections._count_elements(), lambda: _collections._count_elements({}), lambda: _collections._count_elements({}, [], 1), lambda: _collections._count_elements({}, 1), lambda: _collections._count_elements(1, [1]), lambda: _collections._count_elements(None, []), lambda: _collections._count_elements({}, [[]]), lambda: _collections._count_elements({"a": "x"}, "a"), lambda: _collections._count_elements({"a": None}, "a"), lambda: _collections._count_elements(mapping={}), lambda: _collections._count_elements([], [1])):
    show(f)
print(_collections._count_elements, _collections.__name__, _collections.__doc__ is not None, sorted([k for k in dir(_collections) if not k.startswith("__")]))
"""),
    ('what_collections_builds', SHOW + r"""
import collections
from collections import Counter, UserDict, UserList, defaultdict, deque
c = Counter("abracadabra")
print(c, c["a"], c["z"], sorted(c.elements()), c.total(), sum(c.values()), len(c), list(c))
c.update("aaa")
c.subtract("b")
print(c, +c, -c, c + c, c - c, c | c, c & c, Counter({"a": 2}), Counter(a=3), type(c.copy()).__name__)
show(lambda: Counter.fromkeys("a"))
show(lambda: Counter(1))
show(lambda: c + 1)
u = UserDict(a=1)
u["b"] = 2
print(u, u.data, len(u), "a" in u, u["a"], list(u), u.copy(), type(u.copy()).__name__, u | {"c": 3}, {"c": 3} | u, u.get("z"))
del u["a"]
show(lambda: u["a"])
l = UserList([1, 2, 3])
l.append(4)
print(l, l.data, len(l), l[0], l[1:2], type(l[1:2]).__name__, l + [5], [5] + l, l * 2, 2 * l, 3 in l, l == [1, 2, 3, 4], l < [9], l.index(2), l.count(2), l.copy())
l.extend([5])
l.insert(0, 0)
l.remove(5)
l.pop()
l.reverse()
l[0] = 9
del l[1]
print(l)
print(collections.__name__, collections.deque is deque, collections.defaultdict is defaultdict, sorted(collections.__all__))
show(lambda: collections.OrderedDict)
"""),
    ('subclasses_store_their_own', SHOW + r"""
from collections import defaultdict, deque
import _thread
class D(deque):
    def __setattr__(self, n, v):
        print("setattr", n)
        object.__setattr__(self, n, v)
class DD(defaultdict):
    def __setattr__(self, n, v):
        print("setattr", n)
        object.__setattr__(self, n, v)
class R(_thread.RLock):
    def __setattr__(self, n, v):
        print("setattr", n)
        object.__setattr__(self, n, v)
class L(_thread._local):
    def __setattr__(self, n, v):
        print("setattr", n)
        super().__setattr__(n, v)
d = D([1, 2])
d.append(3)
d.popleft()
d.tag = 1
print(d, d.tag)
dd = DD(int)
dd["a"]
dd.tag = 1
dd.default_factory = str
print(dd, dd.tag)
r = R()
r.acquire()
r.release()
r.tag = 1
print(r.tag)
l = L()
l.tag = 1
print(l.tag, l.__dict__)
"""),
    ('list_slices', SHOW + r"""
class N:
    def __init__(self, n):
        self.n = n
    def __del__(self):
        print("del", self.n, end="; ")
    def __repr__(self):
        return "N" + str(self.n)
def assign(l, s, v):
    l[s] = v
    return l
for s in (slice(0, 0), slice(1, 2), slice(None), slice(2, 1), slice(-1, None), slice(100, 200), slice(None, None, 2), slice(None, None, -1), slice(1, None, 2), slice(3, 0, -1), slice(0, 0, 2), slice(0, 0, -1), slice(5, 2, 2), slice(2, 5, -1), slice(None, None, 1), slice(True, None), slice(0, 2, 1), slice(0, 2, None), slice(-100, 100), slice(100, -100), slice(2**70, -(2**70)), slice(-(2**70), 2**70, 2**70), slice(None, None, -(2**70))):
    for v in ([], [9], [8, 9], (7,), "ab", iter([1]), {1: 2}, range(2), {3}):
        show(lambda: assign([0, 1, 2, 3, 4], s, v))
for s, v in ((slice(0, 1), 1), (slice(None, None, 2), 1), (slice(0, 1, 0), []), (slice("a", 1), []), (slice(1.5), []), (slice(0, 1), None), (slice(0, "a", 1), [1]), (slice(0, 1, "a"), [1])):
    show(lambda: assign([1], s, v))
class Iter:
    def __iter__(self):
        raise KeyError("iter")
class NotIter:
    def __iter__(self):
        return 1
class TE:
    def __iter__(self):
        raise TypeError("from iter")
class Gen:
    def __iter__(self):
        return iter([1, 2])
for v in (Iter(), NotIter(), TE(), Gen()):
    show(lambda: assign([1, 2, 3], slice(0, 1), v))
    show(lambda: assign([1, 2, 3], slice(None, None, 2), v))
a = [1, 2, 3]
a[:] = a
print(a)
a[::-1] = a
print(a)
a[1:1] = a
print(a)
show(lambda: assign(a, slice(None, None, 2), a[1:3]))
show(lambda: assign(a, slice(None, None, 2), a[:len(a[::2])]))
print(a)
l = [N(1), N(2), N(3), N(4)]
l[1:3] = []
print("sliced")
l = [N(1), N(2), N(3), N(4)]
l[::2] = [5, 6]
print("extended")
l = [N(1), N(2)]
l[:] = []
print("emptied")
l = [N(1), N(2), N(3)]
l[::-1] = [7, 8, 9]
print("reversed")
l = [N(1), N(2), N(3)]
l[0:2] = [N(4)]
print("swapped")
l = []
print("end of the last list")
class Grows:
    def __iter__(self):
        victim.clear()
        return iter([1, 2])
victim = [1, 2, 3, 4]
victim[1:3] = Grows()
print(victim)
victim = [1, 2, 3, 4]
show(lambda: assign(victim, slice(None, None, 2), Grows()))
print(victim)
class Reenter:
    def __init__(self, l):
        self.l = l
    def __del__(self):
        print("during", len(self.l), end="; ")
        self.l.append("from del")
r = []
r.extend([Reenter(r), 1])
r[0:1] = [7, 8]
print(r)
r = []
r.extend([Reenter(r), 1, 2])
r[::2] = [7, 8]
print(r)
class Idx:
    def __index__(self):
        print("index", end=" ")
        return 1
b = [1, 2, 3]
b[Idx():Idx()] = [9]
print(b)
"""),
]

REFUSED = (
    ("import collections\ncollections.OrderedDict().__sizeof__()\n", "OrderedDict.__sizeof__"),   # OrderedDict itself: C-3-52
    ("from collections import deque\ndeque().__sizeof__()\n", "__sizeof__"),
)


def pytest_generate_tests(metafunc: Any) -> None:
    if "program" in metafunc.fixturenames:
        metafunc.parametrize("program", PROGRAMS, ids=[name for name, _ in PROGRAMS])
    if "refused" in metafunc.fixturenames:
        metafunc.parametrize("refused", REFUSED, ids=[text for _, text in REFUSED])


def test_as_cpython(program: tuple[str, str]) -> None:
    same(program[1])


def test_what_is_not_there_yet_stops_by_name(refused: tuple[str, str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(textwrap.dedent(refused[0]), encoding="utf-8")
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, timeout=60)
    assert got.returncode == 70 and "not implemented" in got.stderr and refused[1] in got.stderr, got


if __name__ == "__main__":
    for item in PROGRAMS:
        test_as_cpython(item)
