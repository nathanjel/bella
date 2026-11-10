"""collections.OrderedDict compiled, against CPython (Objects/odictobject.c; C-3-52 is the case): the messages, which the
case does not compare; what a key's __hash__ and __eq__ see once the dict's table is rebuilt (od_fast_nodes resized); when keys
and values die; the dict's own methods called on one (a key set past the order); and what the standard library asks of it."""
from __future__ import annotations

from pipeline.tests.test_review_2026_11_03 import same

MESSAGES = r"""
from collections import OrderedDict
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e)
od = OrderedDict(a=1)
for f in (lambda: OrderedDict(1, 2), lambda: OrderedDict([(1,)]), lambda: OrderedDict([(1, 2, 3)]), lambda: OrderedDict([1]),
          lambda: OrderedDict([[]]), lambda: od.update(1, 2), lambda: od.update(5), lambda: od.pop(), lambda: od.pop("zz"),
          lambda: od.pop(1, 2, 3), lambda: od.pop(key="a"), lambda: od.setdefault(), lambda: od.setdefault(key="q", default=7),
          lambda: od.popitem(1, 2), lambda: od.popitem(last=0), lambda: OrderedDict().popitem(), lambda: od.move_to_end(),
          lambda: od.move_to_end("zz", last=False), lambda: od.move_to_end(key="q", last=[]), lambda: od.keys(1), lambda: od.copy(1),
          lambda: od.clear(1), lambda: od.__reduce__(1), lambda: OrderedDict.fromkeys(), lambda: OrderedDict.fromkeys(iterable="ab", value=1),
          lambda: OrderedDict.keys(1), lambda: OrderedDict.__setitem__(1, 2, 3), lambda: OrderedDict.__iter__(), lambda: od[[]],
          lambda: od.__setitem__([], 1), lambda: od.__delitem__("zz"), lambda: od < od, lambda: hash(od), lambda: od | 1,
          lambda: type(iter(od))(), lambda: type(od.keys()).__iter__(1), lambda: type(od.keys())(), lambda: od.__lt__(od),
          lambda: OrderedDict.__init__(1), lambda: od.__init__({}, {}), lambda: type(iter(od)).__next__(1)):
    show(f)
print(OrderedDict.__dict__["fromkeys"], type(OrderedDict.__dict__["keys"]).__name__, type(OrderedDict.__dict__["__iter__"]).__name__,
      OrderedDict.__hash__, OrderedDict.__doc__, type(od.keys()).__module__, type(od.keys()).__mro__, type(iter(od)).__mro__)
"""

COLLISIONS = r"""
from collections import OrderedDict
calls = []
class Key:
    def __init__(self, n):
        self.n = n
    def __hash__(self):
        calls.append(("hash", self.n))
        return self.n % 3
    def __eq__(self, other):
        calls.append(("eq", self.n, getattr(other, "n", None)))
        return isinstance(other, Key) and self.n == other.n
    def __repr__(self):
        return "K" + str(self.n)
keys = [Key(i) for i in range(12)]
od = OrderedDict()
for k in keys:
    od[k] = k.n
print(len(calls), calls[-12:])
calls.clear()
od.move_to_end(keys[0])
od.move_to_end(keys[5], last=False)
del od[keys[3]]
od.pop(keys[7])
print(list(od), calls)
calls.clear()
for k in keys[:4]:
    od[k] = -1
print(list(od.items()), calls)
calls.clear()
print([k.n for k in reversed(od)], len(calls))
calls.clear()
print(od == od.copy(), od.copy() == OrderedDict(reversed(od.items())), len(calls))
calls.clear()
od.clear()
od[keys[1]] = 1
print(od, calls)
"""

DEATHS = r"""
from collections import OrderedDict
class Item:
    def __init__(self, name):
        self.name = name
    def __del__(self):
        print("dies", self.name)
    def __hash__(self):
        return hash(self.name)
    def __eq__(self, other):
        return self is other
    def __repr__(self):
        return self.name
od = OrderedDict()
for n in "abc":
    od[Item("key " + n)] = Item("value " + n)
od.move_to_end(next(iter(od)))
print("moved", list(od))
k = next(iter(od))
del od[k]
del k
print("deleted")
print(od.popitem(last=False))
print("popped")
od.clear()
print("cleared")
for n in "xyz":
    od[Item("key " + n)] = Item("value " + n)
od.move_to_end(next(iter(od)))
del od
print("end")
"""

BYPASS = r"""
from collections import OrderedDict
od = OrderedDict(a=1, b=2)
od.move_to_end("a")
dict.__setitem__(od, "x", 9)
print(list(od), len(od), od, dict(od), {**od}, list(dict.keys(od)), od.get("x"))
dict.__delitem__(od, "b")
try:
    print(list(od.items()))
except KeyError as e:
    print("KeyError", e)
try:
    print(list(od))
except KeyError as e:
    print("KeyError", e)
it = iter(OrderedDict(a=1, b=2))
next(it)
print(it.__reduce__())
v = OrderedDict(a=1, b=2).values()
print(v, reversed(v).__reduce__(), sorted(OrderedDict(b=1, a=2).keys() | {"c"}), OrderedDict(a=1).items() == {("a", 1)})
o = OrderedDict(a=1)
it = iter(o)
o["b"] = 2
try:
    next(it)
except RuntimeError as e:
    print("RuntimeError", e)
try:
    next(it)
except RuntimeError as e:
    print("RuntimeError", e)
"""

LIBRARY = r"""
import copy, json, typing
from collections import OrderedDict
od = OrderedDict([("z", 1), ("a", OrderedDict(q=[1]))])
print(json.dumps(od), json.loads('{"b": 1, "a": 2}', object_pairs_hook=OrderedDict))
print(typing.OrderedDict[str, int], OrderedDict[str, int], isinstance(od, typing.MutableMapping))
deep = copy.deepcopy(od)
print(deep, deep["a"] is od["a"], copy.copy(od)["a"] is od["a"])
class Sub(OrderedDict):
    __slots__ = ("extra",)
s = Sub(a=1)
s.extra = 5
s.more = 6
print(s.__reduce__()[2], copy.copy(s).extra, copy.copy(s).more, vars(s))
"""


def test_messages() -> None:
    same(MESSAGES)


def test_hash_and_eq_through_rebuilt_tables() -> None:
    same(COLLISIONS)


def test_deaths() -> None:
    same(DEATHS)


def test_the_dict_methods_past_the_order() -> None:
    same(BYPASS)


def test_the_standard_library_takes_one() -> None:
    same(LIBRARY)


if __name__ == "__main__":
    test_messages()
    test_hash_and_eq_through_rebuilt_tables()
    test_deaths()
    test_the_dict_methods_past_the_order()
    test_the_standard_library_takes_one()
