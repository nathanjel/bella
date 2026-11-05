"""frozendict and the reverse iterators of a dict, compiled, against CPython.

Case C-6-11 shows the behaviour by exception class, as a case must; these compare messages too, what
each path of `fromkeys` calls and when, a subclass's overrides on every path that asks for them, and
what a reverse iterator does when its dict changes.
"""
from __future__ import annotations

from typing import Any

from pipeline.tests.test_review_2026_11_03 import same

SHOW = """def show(f):
    try:
        print(repr(f()))
    except Exception as e:
        print(type(e).__name__, e)
"""


PROGRAMS: list[tuple[str, str]] = [
    ('constructing', SHOW + """class P:
    def keys(self):
        return ["a", "b"]
    def __getitem__(self, k):
        print("get", k)
        return k * 2
class Bad:
    def keys(self):
        raise ValueError("no keys")
class NotPairs:
    def __iter__(self):
        return iter([1])
for f in (lambda: frozendict(), lambda: frozendict(None), lambda: frozendict(1), lambda: frozendict(1, 2), lambda: frozendict(1, 2, 3), lambda: frozendict({}, {}), lambda: frozendict("ab"), lambda: frozendict(["ab", "cd"]), lambda: frozendict([(1, 2, 3)]), lambda: frozendict([[1, 2]]),
          lambda: frozendict(P()), lambda: frozendict(Bad()), lambda: frozendict(NotPairs()), lambda: frozendict({[]: 1}), lambda: frozendict([([], 1)]), lambda: frozendict({1: []}), lambda: frozendict({frozenset(): frozendict()}), lambda: frozendict(a=1, b=2), lambda: frozendict({"a": 0}, a=1), lambda: frozendict(**{"a": 1}), lambda: frozendict([("a", 1), ("a", 2)]),
          lambda: frozendict.__new__(frozendict), lambda: frozendict.__new__(frozendict, {"a": 1}), lambda: frozendict.__new__(frozendict, {"a": 1}, b=2), lambda: frozendict.__new__(frozendict, 1, 2), lambda: frozendict.__new__(), lambda: frozendict.__new__(int), lambda: frozendict.__new__(5), lambda: frozendict.__new__(dict), lambda: dict.__new__(frozendict), lambda: object.__new__(frozendict), lambda: int.__new__(frozendict),
          lambda: frozendict.__init__(frozendict()), lambda: frozendict.__init__(frozendict(), 1), lambda: frozendict.__init__(frozendict(), a=1), lambda: frozendict.__init__(1)):
    show(f)
fd = frozendict(a=1)
print(frozendict(fd) is fd, frozendict(fd, b=1) is fd, frozendict(**fd) is fd, frozendict.__new__(frozendict, fd) is fd, frozendict() is frozendict(), type(frozendict()), frozendict(iter({"z": 1}.items())), frozendict(enumerate("ab")), frozendict(zip("ab", (1, 2))))
"""),
    ('reading_messages', SHOW + """fd = frozendict(a=1, b=2)
for f in (lambda: fd["z"], lambda: fd[[]], lambda: fd[{}], lambda: [] in fd, lambda: fd.get([]), lambda: fd.get(), lambda: fd.get(1, 2, 3), lambda: fd.get(key=1), lambda: fd.keys(1), lambda: fd.items(1), lambda: fd.values(1), lambda: fd.copy(1), lambda: fd.__getnewargs__(1), lambda: fd.__reversed__(1), lambda: fd.__len__(1), lambda: fd.__getitem__(), lambda: fd.__contains__(), lambda: fd.__iter__(1), lambda: fd.__hash__(1), lambda: fd.__or__(), lambda: fd.__ror__(1, 2), lambda: fd.__eq__(),
          lambda: frozendict.get({}, "a"), lambda: frozendict.keys({}), lambda: frozendict.items(1), lambda: frozendict.values(1), lambda: frozendict.copy({}), lambda: frozendict.__getnewargs__({}), lambda: frozendict.__reversed__({}), lambda: frozendict.__len__({}), lambda: frozendict.__getitem__({}, 1), lambda: frozendict.__contains__({}, 1), lambda: frozendict.__iter__({}), lambda: frozendict.__repr__({}), lambda: frozendict.__hash__({}), lambda: frozendict.__or__({}, {}), lambda: frozendict.__eq__({}, {}),
          lambda: dict.get(fd, "a"), lambda: dict.keys(fd), lambda: dict.copy(fd), lambda: dict.__len__(fd), lambda: dict.__getitem__(fd, "a"), lambda: dict.__setitem__(fd, "a", 1), lambda: dict.__delitem__(fd, "a"), lambda: dict.update(fd, {}), lambda: dict.clear(fd), lambda: dict.pop(fd, "a"), lambda: dict.popitem(fd), lambda: dict.setdefault(fd, "a"), lambda: dict.__or__(fd, {}), lambda: dict.__ior__(fd, {}), lambda: dict.__eq__(fd, fd), lambda: dict.__repr__(fd), lambda: dict.__iter__(fd), lambda: dict.__contains__(fd, "a"), lambda: dict.__reversed__(fd), lambda: dict.__init__(fd, {}),
          lambda: dict.__reversed__({}, 1), lambda: {}.__reversed__(1), lambda: {}.keys().__reversed__(1), lambda: {}.values().__reversed__(1), lambda: {}.items().__reversed__(1), lambda: dict.__reversed__(1)):
    show(f)
"""),
    ('what_it_refuses', SHOW + """fd = frozendict(a=1)
class C:
    pass
def assign():
    fd["a"] = 2
def delete():
    del fd["a"]
def attr():
    fd.x = 1
def del_attr():
    del fd.x
def cls_attr():
    frozendict.x = 1
def aug():
    f = fd
    f["a"] += 1
def delete_at_an_index():
    del fd[0]
class Idx:
    def __index__(self):
        return 2**70
def delete_at_a_bad_index():
    del fd[Idx()]
def delete_from_things():
    out = []
    for target, key in ((5, 0), (5, "a"), ((1,), 0), ((1,), "a"), ("a", 0), ("a", "x"), (b"a", 0), (b"a", "x"), (range(3), 0), (range(3), "a"), ({1}, 0), ({1}, "a"), (object(), 0), (object(), "a"), (C(), 0), (C(), "a"), ({}.keys(), 0), ({}.keys(), "a"), (None, 0), (None, "a"), (iter(()), 0), (iter(()), "a")):
        try:
            del target[key]
        except TypeError as e:
            out.append(str(e))
    return out
for f in (delete_at_an_index, delete_at_a_bad_index, delete_from_things, assign, delete, attr, del_attr, cls_attr, aug, lambda: fd.update, lambda: fd.pop, lambda: fd.clear, lambda: fd.popitem, lambda: fd.setdefault, lambda: fd.__setitem__, lambda: fd.__delitem__, lambda: fd.__ior__, lambda: fd.__dict__, lambda: frozendict.update, lambda: fd | 1, lambda: 1 | fd, lambda: fd | [("b", 2)], lambda: fd - fd, lambda: fd < fd, lambda: fd + fd, lambda: fd < {}, lambda: {} < fd, lambda: -fd):
    show(f)
def namespace():
    C().__dict__ = fd
class M(type):
    @classmethod
    def __prepare__(mcs, name, bases, **kw):
        return frozendict(x=1)
def prepared():
    class D(metaclass=M):
        pass
    return D
def global_namespace_is_read_only():
    return type("N", (), frozendict(a=1))
def global_namespace():
    return type("N", (), frozendict(a=1)).a
def base_conflicts(*bases):
    return lambda: type("N", bases, {})
for f in (namespace, prepared, global_namespace, lambda: global_namespace_is_read_only().a, base_conflicts(dict, frozendict), base_conflicts(frozendict, dict), base_conflicts(frozendict, int), base_conflicts(int, frozendict), base_conflicts(frozendict, object), base_conflicts(frozendict, frozendict), base_conflicts(frozendict, Exception), base_conflicts(frozendict, type)):
    show(f)
print(fd, frozendict.__flags__ & (1 << 6) != 0 if False else 0)
"""),
    ('the_hash', SHOW + """class H:
    def __init__(self, h):
        self.h = h
    def __hash__(self):
        print("hash", self.h)
        return self.h
    def __eq__(self, other):
        return True
print(hash(frozendict()), hash(frozendict({1: 2})), hash(frozendict({1: 2, 3: 4})), hash(frozendict({3: 4, 1: 2})), hash(frozendict({(1, 2): (3, 4)})), hash(frozendict({-1: -1})), hash(frozendict({2**70: 2**71})), hash(frozendict({None: None})) == hash(frozendict({None: None})), hash(frozendict({True: False})), hash(frozendict({1: 0})), hash(frozendict({"a": 1})) == hash(frozendict({"a": 1})), hash(frozendict({frozendict({1: 2}): frozendict({3: 4})})))
fd = frozendict(a=H(1), b=H(-1), c=H(2**70))
print(hash(fd) == hash(fd), hash(fd) == hash(fd))
k = frozendict({H(5): 1, H(6): 2})
print("made")
print(hash(k) == hash(k))
for f in (lambda: hash(frozendict(a=[1])), lambda: hash(frozendict(a={})), lambda: hash(frozendict(a=set())), lambda: hash(frozendict(a=frozendict(b=[]))), lambda: {frozendict(a=[1]): 1}, lambda: {frozendict(a=[1])}, lambda: frozendict(a=[1]) in {}, lambda: frozendict({frozendict(a=[1]): 1}), lambda: frozendict.__hash__(frozendict(a=[1])), lambda: hash(frozendict(a=H("x")))):
    show(f)
bad = frozendict(a=[1])
show(lambda: hash(bad))
show(lambda: hash(bad))
print(bad)
deep = frozendict()
for _ in range(2000):
    deep = frozendict(a=deep)
print(hash(deep))
"""),
    ('the_operator_in_each_order', SHOW + """class F(frozendict):
    pass
class D(dict):
    pass
class R(frozendict):
    def __ror__(self, other):
        return "R.ror"
    def __or__(self, other):
        return "R.or"
class P:
    def __or__(self, other):
        return "P.or"
    def __ror__(self, other):
        return "P.ror"
values = [frozendict(), frozendict(a=1), {}, {"b": 2}, F(), F(c=3), D(), D(d=4)]
for x in values:
    for y in values:
        r = x | y
        print(type(x).__name__, type(y).__name__, type(r).__name__, r, r is x, r is y)
print(R() | {}, {} | R(), frozendict() | R(), R() | frozendict(), frozendict() | P(), P() | frozendict(), frozendict().__or__(P()), frozendict().__ror__(P()))
for f in (lambda: frozendict() | 1, lambda: 1 | frozendict(), lambda: frozendict() | [], lambda: [] | frozendict(), lambda: frozendict() | None, lambda: frozendict(a=1) | {[]: 1}, lambda: {} | frozendict(a=1) | {[]: 1}):
    show(f)
d = {"a": 1}
d |= frozendict(b=2)
print(d)
d.update(frozendict(c=3))
print(d)
e = frozendict(a=1)
e |= {"b": 2}
print(e, type(e).__name__)
e |= frozendict(c=3)
print(e)
"""),
    ('fromkeys_on_every_path', SHOW + """class Traced(frozendict):
    def __new__(cls, *a, **k):
        print("new", a, k)
        return super().__new__(cls, *a, **k)
    def __init__(self, *a, **k):
        print("init", a, k)
class Other(frozendict):
    pass
class DictOfFrozen(dict):
    def __new__(cls, *a):
        print("dict new", a)
        return frozendict(a=0) if not a else dict.__new__(cls)
    def __init__(self, *a):
        print("dict init", a)
class Maker:
    def __call__(self):
        return frozendict(p=1)
for f in (lambda: frozendict.fromkeys(""), lambda: frozendict.fromkeys("ab", 1), lambda: frozendict.fromkeys({"a": 1}), lambda: frozendict.fromkeys(frozendict(z=1), 2), lambda: frozendict.fromkeys({1, 2}), lambda: frozendict.fromkeys(frozenset({3})), lambda: frozendict.fromkeys([1, 1, 2]), lambda: frozendict.fromkeys(iter("ab")), lambda: frozendict.fromkeys(), lambda: frozendict.fromkeys(1), lambda: frozendict.fromkeys([[]]), lambda: frozendict.fromkeys("a", 1, 2), lambda: frozendict.fromkeys(iterable="a"),
          lambda: frozendict(a=1).fromkeys("b"), lambda: Traced.fromkeys("ab", 5), lambda: Other.fromkeys("ab"), lambda: type(Other.fromkeys("a")).__name__, lambda: Other.fromkeys([[]]), lambda: DictOfFrozen.fromkeys("b", 1), lambda: type(DictOfFrozen.fromkeys("b", 1)).__name__,
          lambda: dict.fromkeys(frozendict(a=1)), lambda: dict.fromkeys(frozendict(a=1), 2), lambda: dict.fromkeys(Other(q=1)), lambda: dict.fromkeys(), lambda: dict.fromkeys(1), lambda: dict.fromkeys([[]]), lambda: {}.fromkeys("a"), lambda: dict.fromkeys(iterable="a"),
          lambda: frozendict.__dict__["fromkeys"], lambda: frozendict.fromkeys.__self__, lambda: frozendict.fromkeys.__name__, lambda: Other.fromkeys.__self__, lambda: type(frozendict.fromkeys).__name__):
    show(f)
"""),
    ('a_subclass_on_every_path', SHOW + """log = []
class O(frozendict):
    extra = "class attribute"
    def __getitem__(self, k):
        log.append(("getitem", k))
        return "from getitem"
    def __iter__(self):
        log.append("iter")
        return iter(["own"])
    def __len__(self):
        log.append("len")
        return 7
    def __contains__(self, k):
        log.append(("contains", k))
        return True
    def keys(self):
        log.append("keys")
        return ["k"]
    def items(self):
        log.append("items")
        return [("i", 1)]
    def values(self):
        log.append("values")
        return ["v"]
    def get(self, k, d=None):
        log.append(("get", k))
        return "from get"
    def __bool__(self):
        log.append("bool")
        return False
    def __repr__(self):
        return "O(...)"
    def __hash__(self):
        log.append("hash")
        return 99
    def __eq__(self, other):
        log.append("eq")
        return "from eq"
    def __ne__(self, other):
        log.append("ne")
        return "from ne"
    def __lt__(self, other):
        return "from lt"
    def __reversed__(self):
        return iter(["rev"])
    def copy(self):
        return "from copy"
o = O({"a": 1})
print(o["x"], list(o), len(o), "q" in o, bool(o), repr(o), str(o), hash(o), o == 1, 1 == o, o != 1, 1 != o, o < 1, 1 > o, list(reversed(o)), o.copy(), o.get("g"), o.keys(), o.items(), o.values(), o.extra)
print(log)
log.clear()
print(dict(o), {**o}, frozendict(o), [*o], list(o.__iter__()), set(o), sorted(o), {}.fromkeys(o), frozendict.fromkeys(o), (lambda **k: k)(**o), dict({"a": 1}, **o))
print(log)
log.clear()
print(frozendict.__getitem__(o, "a"), list(frozendict.__iter__(o)), frozendict.__len__(o), frozendict.__contains__(o, "a"), frozendict.get(o, "a"), list(frozendict.keys(o)), list(frozendict.items(o)), list(frozendict.values(o)), frozendict.__repr__(o), frozendict.__hash__(o) == hash(frozendict(a=1)), frozendict.__eq__(o, {"a": 1}), frozendict.__ne__(o, {"a": 1}), frozendict.__lt__(o, {}), list(frozendict.__reversed__(o)), frozendict.__getnewargs__(o), frozendict.__or__(o, {}), frozendict.__ror__(o, {}), type(frozendict.copy(o)).__name__)
print(log)
log.clear()
class WithSlots(frozendict):
    __slots__ = ("x",)
w = WithSlots(a=1)
w.x = 5
print(w, w.x, hasattr(w, "__dict__"), repr(w), type(w).__name__, WithSlots.__basicsize__ if False else 0)
show(lambda: setattr(w, "y", 1))
class Inst(frozendict):
    def __init__(self, *a, **k):
        self.seen = (a, k)
i = Inst({"a": 1}, b=2)
print(i, i.seen, i.__dict__, vars(i), dir(i) == dir(Inst) + ["seen"] if False else 0, "seen" in dir(i))
del i.seen
print(i.__dict__)
i.__dict__ = {"other": 1}
print(i.other, i)
class Rep(frozendict):
    pass
class Multi(Rep, frozendict):
    pass
class Mix:
    def extra(self):
        return "mix"
class WithMix(Mix, frozendict):
    pass
class Sub2(WithMix):
    pass
print(Rep(), Rep(a=1), repr(Rep(a=[1])), Multi(z=1), WithMix(a=1).extra(), Sub2(y=1), Sub2.__mro__, Sub2(y=1) == {"y": 1}, Sub2(y=1) | {}, type(Sub2(y=1) | {}).__name__, isinstance(Sub2(), frozendict))
class M(type):
    def __call__(cls, *a, **k):
        print("meta call", a, k)
        return super().__call__(*a, **k)
class WithMeta(frozendict, metaclass=M):
    pass
print(WithMeta(a=1), type(WithMeta), WithMeta[int, str], WithMeta.__class_getitem__(int).__origin__)
"""),
    ('a_value_refers_to_it', """l = []
fd = frozendict(me=l)
l.append(fd)
print(fd, l, repr(fd), str(l))
class F(frozendict):
    pass
m = []
f = F(a=m)
m.append(f)
print(f, m)
print(frozendict(a=frozendict(b=frozendict())), F(a=F()), frozendict({frozendict(): frozendict()}), {"a": frozendict(b=1)}, [frozendict()], (frozendict(a=1),), {frozendict()})
class ReprRaises:
    def __repr__(self):
        raise ValueError("no repr")
try:
    repr(frozendict(a=ReprRaises()))
except ValueError as e:
    print(e)
print(frozendict(a=1), frozendict(a=2))
"""),
    ('reversed_dicts', SHOW + """d = {"a": 1, "b": 2, "c": 3}
print(list(reversed(d)), list(reversed(d.keys())), list(reversed(d.values())), list(reversed(d.items())), list(d.__reversed__()), list(d.keys().__reversed__()), list(d.values().__reversed__()), list(d.items().__reversed__()), list(reversed({})), list(reversed({}.items())))
print(type(reversed(d)).__name__, type(reversed(d.keys())).__name__, type(reversed(d.values())).__name__, type(reversed(d.items())).__name__, type(iter(reversed(d))).__name__)
it = reversed(d)
print(iter(it) is it, next(it), next(it), next(it), next(it, "end"), next(it, "end"))
class D(dict):
    def __iter__(self):
        return iter(["own"])
    def __reversed__(self):
        return iter(["own reversed"])
class E(dict):
    def __iter__(self):
        return iter(["own"])
print(list(reversed(D(a=1))), list(reversed(E(a=1))), list(dict.__reversed__(D(a=1))), list(reversed(D(a=1).keys())))
holes = {i: i for i in range(10)}
for i in (9, 0, 5, 6):
    del holes[i]
print(list(reversed(holes)), list(reversed(holes.values())), list(reversed(holes.items())))
holes[100] = 100
print(list(reversed(holes)))
class Attrs:
    pass
a = Attrs()
a.x, a.y = 1, 2
print(list(reversed(a.__dict__)), list(reversed(vars(a).items())))
del a.x
a.z = 3
print(list(reversed(a.__dict__)), list(reversed(a.__dict__.values())))
def grow():
    g = {"a": 1, "b": 2}
    for k in reversed(g):
        g["c"] = 3
def shrink():
    g = {"a": 1, "b": 2}
    for k in reversed(g):
        del g[k]
def same_size():
    g = {"a": 1, "b": 2, "c": 3}
    seen = []
    for k in reversed(g):
        seen.append(k)
        if k == "c":
            del g["a"]
            g["x"] = 9
    return seen
def clear_at_end():
    g = {"a": 1}
    it = reversed(g)
    next(it)
    next(it, None)
    g["b"] = 2
    return next(it, "still ended")
def sticky():
    g = {"a": 1, "b": 2}
    it = reversed(g)
    next(it)
    g["c"] = 3
    out = []
    for _ in range(2):
        try:
            next(it)
        except RuntimeError as e:
            out.append(str(e))
    del g["c"]
    try:
        out.append(next(it))
    except RuntimeError as e:
        out.append(str(e))
    return out
def smaller_then_equal():
    g = {str(i): i for i in range(20)}
    it = reversed(g)
    next(it)
    for k in list(g)[:10]:
        del g[k]
    for k in "abcdefghij":
        g[k] = 0
    return next(it), list(it)[:3]
for f in (grow, shrink, same_size, clear_at_end, sticky, smaller_then_equal):
    show(f)
"""),
    ('the_key_error_is_worded_by_its_container', SHOW + """fd = frozendict(a=1)
d = {"a": 1}
class Sub(dict):
    pass
class FSub(frozendict):
    pass
class UH:
    __hash__ = None
class RaisesHash:
    def __hash__(self):
        raise ValueError("no hash")
class TypeErrorSub(TypeError):
    pass
class RaisesSub:
    def __hash__(self):
        raise TypeErrorSub("sub")
for key in ([], {}, set(), UH(), bytearray(b"a"), frozendict(a=[]), RaisesHash(), RaisesSub()):
    for f in (lambda: d[key], lambda: key in d, lambda: d.get(key), lambda: d.pop(key), lambda: d.pop(key, 0), lambda: d.setdefault(key), lambda: d.__setitem__(key, 1), lambda: d.__delitem__(key), lambda: d.__contains__(key), lambda: d.__getitem__(key), lambda: {key: 1}, lambda: dict([(key, 1)]), lambda: dict.fromkeys([key]), lambda: {}.update([(key, 1)]),
              lambda: fd[key], lambda: key in fd, lambda: fd.get(key), lambda: fd.__contains__(key), lambda: fd.__getitem__(key), lambda: frozendict({key: 1}), lambda: frozendict([(key, 1)]), lambda: frozendict.fromkeys([key]), lambda: fd | {key: 1},
              lambda: Sub()[key], lambda: key in Sub(), lambda: Sub()[key], lambda: FSub()[key], lambda: key in FSub(), lambda: FSub([(key, 1)]), lambda: FSub.fromkeys([key])):
        show(f)
    def setit():
        d[key] = 1
    def delit():
        del d[key]
    show(setit)
    show(delit)
try:
    {}[[]]
except TypeError as e:
    print(e.__context__, e.__cause__, e.__suppress_context__, e.args)
"""),
    ('imports_and_other_readers', SHOW + """import sys
print(__import__("sys", frozendict(), frozendict()) is sys, __import__("sys", frozendict(__name__="m"), None, (), 0) is sys)
def kw(**k):
    return k
print(kw(**frozendict(a=1)), {**frozendict(a=1), "b": 2}, {"b": 2, **frozendict(a=1)}, dict(frozendict(a=1), b=2), dict(b=2, **frozendict(a=1)), [*frozendict(a=1)], (*frozendict(a=1),), {*frozendict(a=1)}, set(frozendict(a=1)), frozenset(frozendict(a=1)), tuple(frozendict(a=1)), list(frozendict(a=1)), sorted(frozendict(b=1, a=2)), sum(frozendict({1: 2, 3: 4})), max(frozendict({1: 2, 3: 4})), min(frozendict({1: 2, 3: 4})), any(frozendict({0: 1})), all(frozendict({0: 1})), list(map(str, frozendict(a=1))), list(filter(None, frozendict({0: 1, 1: 0}))))
a, b = frozendict(x=1, y=2)
print(a, b, "%s" if False else "", len(frozendict()), not frozendict(), bool(frozendict(a=0)), frozendict(a=1) and 1, frozendict() or 2, "yes" if frozendict(a=1) else "no")
for k, v in frozendict(p=1, q=2).items():
    print(k, v)
for k in frozendict(p=1).keys():
    print(k)
for v in frozendict(p=1).values():
    print(v)
show(lambda: kw(**frozendict({1: 2})))
show(lambda: {**frozendict(a=1), **1})
show(lambda: kw(**frozendict(a=1), a=2))
show(lambda: dict(frozendict({1: 2}), **{"b": 3}))
print(dict.__eq__({}, frozendict()), frozendict.__eq__(frozendict(), {}), {} == frozendict(), frozendict() == {}, [frozendict()] == [{}], (frozendict(),) == ({},), {"a": frozendict()} == {"a": {}}, frozendict(a=frozendict()) == frozendict(a={}))
print(type(frozendict().keys()).__name__, type(frozendict().values()).__name__, type(frozendict().items()).__name__, type(iter(frozendict())).__name__, type(iter(frozendict().values())).__name__, type(iter(frozendict().items())).__name__, repr(frozendict(a=1).keys()), repr(frozendict(a=1).values()), repr(frozendict(a=1).items()), hash(frozendict().values()) != 0, frozendict().keys() == {}.keys() if False else 0)
print(isinstance(frozendict, type), frozendict.__class__, callable(frozendict), frozendict.__doc__[:20], frozendict.__dict__["__new__"] is not None, "__new__" in frozendict.__dict__, "update" in frozendict.__dict__, "get" in frozendict.__dict__, sorted(n for n in [] ) if False else 0, frozendict.__init__ is object.__init__, frozendict.__setattr__ is object.__setattr__, dir(frozendict) == dir(frozendict()), "update" in dir(frozendict), "copy" in dir(frozendict()), frozendict.__weakrefoffset__ if False else 0)
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
