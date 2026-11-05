"""itertools, compiled, against CPython.

Case C-7-20 shows the behaviour by exception class, as a case must; these compare messages too, when
an item dies through each iterator (a finaliser can tell, and the recycled result tuples are what
keeps the last items alive), what happens after an exception, and the edges of 64 bits.
"""
from __future__ import annotations

from typing import Any

from pipeline.tests.test_review_2026_11_03 import same

SHOW = """def show(f):
    try:
        r = f()
        s = repr(r)
        print(s if " at 0x" not in s else "<" + type(r).__name__ + ">")
    except Exception as e:
        print(type(e).__name__, e)
"""

LIFE = """import itertools as it
log = []
class D:
    def __init__(self, n):
        self.n = n
    def __del__(self):
        log.append("del " + str(self.n))
    def __repr__(self):
        return "D" + str(self.n)
    def __bool__(self):
        return self.n % 2 == 0
    def __add__(self, other):
        return D(self.n + other.n + 100)
    def __hash__(self):
        return self.n
    def __index__(self):
        return self.n
    def __eq__(self, other):
        return self.n // 2 == other.n // 2
    def __lt__(self, other):
        return self.n < other.n
def source(n=6):
    return map(D, range(n))
def clean(v):
    if type(v) is tuple:
        return tuple([clean(x) for x in v])
    return v if " at 0x" not in repr(v) else "<" + type(v).__name__ + ">"
def watch(name, make, steps=4):
    print("==", name)
    i = make()
    print("made", log)
    log.clear()
    for _ in range(steps):
        r = next(i, "end")
        print("got", clean(r), log)
        log.clear()
        del r
        print("dropped", log)
        log.clear()
    del i
    print("gone", log)
    log.clear()
"""

SOURCES = """class Raises:
    def __init__(self, items, exc):
        self.items = list(items)
        self.exc = exc
        self.left = True
    def __iter__(self):
        return self
    def __next__(self):
        if self.items:
            return self.items.pop(0)
        if self.left:
            self.left = False
            raise self.exc
        raise StopIteration
class Ends:
    def __init__(self, value):
        self.value = value
    def __iter__(self):
        return self
    def __next__(self):
        raise StopIteration(self.value)
class NoIter:
    pass
class BadIter:
    def __iter__(self):
        return 5
class IterRaises:
    def __iter__(self):
        raise KeyError("no iter")
class Index:
    def __init__(self, v):
        self.v = v
    def __index__(self):
        return self.v
class IndexRaises:
    def __index__(self):
        raise KeyError("no index")
def clean(v):
    if type(v) is tuple:
        return tuple([clean(x) for x in v])
    return v if " at 0x" not in repr(v) else "<" + type(v).__name__ + ">"
def after(i, n=4):
    out = []
    for _ in range(n):
        try:
            out.append(clean(next(i)))
        except StopIteration as e:
            out.append(("stop", e.args, e.__context__))
        except Exception as e:
            out.append((type(e).__name__, str(e), e.__context__))
    return out
"""


PROGRAMS: list[tuple[str, str]] = [
    ('every_type_in_plain_use', """import itertools as it
print(list(it.chain()), list(it.chain("ab", (), [1])), list(it.chain.from_iterable([])), list(it.chain.from_iterable(["ab", (1,)])), list(it.chain("a").__iter__()))
print(list(it.islice("abcde", 2)), list(it.islice("abcde", 1, 3)), list(it.islice("abcde", 1, None)), list(it.islice("abcde", None)), list(it.islice("abcde", None, 2)), list(it.islice("abcde", 0, None, 2)), list(it.islice("abcde", None, None, None)), list(it.islice("abcde", 10)), list(it.islice("abcde", 3, 3)), list(it.islice("abcde", 4, 2)), list(it.islice("abcde", 1, 100, 3)), list(it.islice("", 3)))
print(list(it.product()), list(it.product("ab")), list(it.product("ab", "xy")), list(it.product("ab", repeat=2)), list(it.product("ab", "x", repeat=2)), list(it.product("ab", repeat=0)), list(it.product("", "a")), list(it.product("a", "")), list(it.product(repeat=2)), list(it.product(repeat=0)), list(it.product("", repeat=0)))
print(list(it.combinations("abcd", 2)), list(it.combinations("ab", 0)), list(it.combinations("ab", 3)), list(it.combinations("", 0)), list(it.combinations("abc", 3)), list(it.combinations(range(4), 3)), list(it.combinations(iterable="ab", r=1)))
print(list(it.combinations_with_replacement("abc", 2)), list(it.combinations_with_replacement("", 0)), list(it.combinations_with_replacement("", 1)), list(it.combinations_with_replacement("a", 3)), list(it.combinations_with_replacement("ab", 0)))
print(list(it.permutations("abc")), list(it.permutations("abc", 2)), list(it.permutations("ab", 0)), list(it.permutations("ab", 3)), list(it.permutations("")), list(it.permutations("", 0)), list(it.permutations("abc", None)), list(it.permutations(iterable="ab", r=1)), len(list(it.permutations(range(5)))), list(it.permutations(range(4), 3))[-3:])
print(list(it.accumulate([])), list(it.accumulate([1, 2, 3])), list(it.accumulate([1, 2, 3], max)), list(it.accumulate([1, 2], initial=5)), list(it.accumulate([], initial=5)), list(it.accumulate([1, 2], None, initial=None)), list(it.accumulate(iterable=[1], func=None)), list(it.accumulate(["a", "b"])), list(it.accumulate([1, 2], lambda a, b: a - b, initial=0)))
print(list(it.batched("abcde", 2)), list(it.batched("", 2)), list(it.batched("ab", 2, strict=True)), list(it.batched("ab", 5)), list(it.batched(iterable="abc", n=1)), list(it.batched("abcd", True)))
print(list(it.pairwise("")), list(it.pairwise("a")), list(it.pairwise("abcd")), list(it.compress("abc", [1, 0, 1])), list(it.compress("abc", [1])), list(it.compress("a", [1, 1])), list(it.compress(data="ab", selectors=[0, 1])))
print(list(it.takewhile(lambda x: x < 2, [1, 3, 1])), list(it.dropwhile(lambda x: x < 2, [1, 3, 1])), list(it.filterfalse(lambda x: x < 2, [1, 3, 1])), list(it.filterfalse(None, [0, 1])), list(it.filterfalse(bool, [0, 1])), list(it.starmap(pow, [(2, 3), [2, 4], "ab" and (1, 1)])), list(it.starmap(lambda *a: a, [(), (1,)])))
print(list(it.zip_longest()), list(it.zip_longest("ab")), list(it.zip_longest("ab", "c")), list(it.zip_longest("", "")), list(it.zip_longest("a", "bc", "def", fillvalue="-")), list(it.zip_longest("a", fillvalue=None)))
print([(k, list(g)) for k, g in it.groupby("")], [(k, list(g)) for k, g in it.groupby("aabbca")], [(k, list(g)) for k, g in it.groupby([1, 2, 3, 4], lambda x: x // 2)], [(k, list(g)) for k, g in it.groupby([1, 2], key=None)], [(k, list(g)) for k, g in it.groupby(iterable="aa", key=str.islower if False else None)])
print(list(it.islice(it.cycle("ab"), 5)), list(it.cycle("")), list(it.islice(it.count(), 3)), list(it.islice(it.count(5), 2)), list(it.islice(it.count(5, 2), 2)), list(it.islice(it.count(step=3), 2)), list(it.islice(it.count(start=1, step=-1), 3)), list(it.repeat("a", 0)), list(it.repeat("a", 2)), list(it.repeat("a", -1)), list(it.repeat(object="a", times=1)), list(it.islice(it.repeat("a"), 2)))
a, b = it.tee("abc")
print(next(a), next(a), next(b), list(a), list(b), it.tee("a", 0), len(it.tee("a", 3)), [list(t) for t in it.tee("ab", 1)], [list(t) for t in it.tee("ab", 3)])
"""),
    ('what_the_classes_say', SHOW + """import itertools as it
import _collections_abc as abc
print(it, it.__name__, it.__package__, it.__spec__.name, it.__spec__.origin, it.__file__ if hasattr(it, "__file__") else "no file", it.__doc__ is not None)
print(sorted([n for n in vars(it) if not n.startswith("__")]), it.__dict__ is vars(it), [n for n in dir(it) if n.startswith("_") and not n.startswith("__")])
names = ["accumulate", "batched", "chain", "combinations", "combinations_with_replacement", "compress", "count", "cycle", "dropwhile", "filterfalse", "groupby", "islice", "pairwise", "permutations", "product", "repeat", "starmap", "takewhile", "zip_longest", "_grouper", "_tee", "_tee_dataobject"]
for n in names:
    c = getattr(it, n)
    print(n, c, c.__name__, c.__qualname__, c.__module__, c.__mro__, c.__base__, type(c), c.__doc__ is None, isinstance(c, type), callable(c), hasattr(c, "__next__"), hasattr(c, "__iter__"), hasattr(c, "__dict__"), hasattr(c, "__slots__"), issubclass(c, abc.Iterator) if n != "_tee_dataobject" else None)
    show(lambda: setattr(c, "x", 1))
    show(lambda: delattr(c, "__doc__"))
    show(lambda: type("S", (c,), {}).__name__)
print(it.tee, type(it.tee).__name__, it.tee.__name__, it.tee.__qualname__, it.tee.__module__, callable(it.tee))
values = [it.chain(), it.count(), it.repeat(1), it.islice("", 0), it.cycle(""), it.product(), it.groupby(""), it.tee("a")[0], it.zip_longest(), it.pairwise(""), it.batched("", 1)]
for v in values:
    print(type(v).__name__, iter(v) is v, v.__iter__() is v, isinstance(v, abc.Iterator), isinstance(v, abc.Iterable), hasattr(v, "__dict__"), hasattr(v, "__length_hint__"), hasattr(v, "x"), "__next__" in dir(v), "__iter__" in dir(v))
    show(lambda: setattr(v, "x", 1))
    show(lambda: len(v))
    show(lambda: v[0])
print(repr(it.chain())[:17], repr(it.islice("", 0))[:18], repr(it.tee("a")[0])[:17], repr(it.groupby(""))[:19], str(it.count()), repr(it.count(3)), repr(it.count(3, 1)), repr(it.count(3, True)), repr(it.count(True)), repr(it.count(False, False)), repr(it.count(3, 2)), repr(it.count(2**64)), repr(it.count(2**64, 2**64)), repr(it.count(step=-1)), repr(it.count(start=0, step=1)), repr(it.repeat("a")), repr(it.repeat("a", 2)), repr(it.repeat("a", -5)), repr(it.repeat("a", 0)), repr(it.repeat(it)), str(it.repeat(None, 1)))
c = it.count(5)
next(c)
print(c, next(c), c)
d = it.count(2, 3)
next(d)
print(d)
r = it.repeat("a", 3)
next(r)
print(r, r.__length_hint__(), list(r), r.__length_hint__(), r)
show(lambda: it.repeat("a").__length_hint__())
show(lambda: it.repeat("a", 2).__length_hint__(1))
show(lambda: it.repeat("a", 2).__length_hint__(x=1))
print(it.chain[int], type(it.chain[int]).__name__, it.chain[int].__origin__, it.chain[int].__args__, it.chain[int]("a").__class__)
show(lambda: it.islice[int])
show(lambda: it.chain.__class_getitem__())
print(it.chain.from_iterable.__name__, it.chain.from_iterable.__self__ is it.chain, type(it.tee("a")[0].__copy__()).__name__)
show(lambda: it.tee("a")[0].__copy__(1))
class S(it.chain):
    pass
print(S.from_iterable.__self__ is S, type(S.from_iterable([])).__name__, it.chain.from_iterable.__self__)
"""),
    ('constructor_messages', SHOW + SOURCES + """import itertools as it
for f in (lambda: it.chain(1), lambda: list(it.chain(1)), lambda: list(it.chain("a", 1, "b")), lambda: it.chain(x=1), lambda: it.chain.from_iterable(), lambda: it.chain.from_iterable(1), lambda: it.chain.from_iterable(1, 2), lambda: it.chain.from_iterable(iterable=1), lambda: list(it.chain.from_iterable([1])),
          lambda: it.islice(), lambda: it.islice("a"), lambda: it.islice("a", 1, 2, 3, 4), lambda: it.islice("a", 1, x=1), lambda: it.islice(1, 1), lambda: it.islice("a", "b"), lambda: it.islice("a", -1), lambda: it.islice("a", 1.5 if False else "x"), lambda: it.islice("a", 2**64), lambda: it.islice("a", -(2**64)), lambda: it.islice("a", -1, 2), lambda: it.islice("a", "b", 2), lambda: it.islice("a", 2**64, 2), lambda: it.islice("a", 1, -1), lambda: it.islice("a", 1, -2), lambda: it.islice("a", 1, "x"), lambda: it.islice("a", 1, 2**64), lambda: it.islice("a", 0, 1, 0), lambda: it.islice("a", 0, 1, -1), lambda: it.islice("a", 0, 1, "x"), lambda: it.islice("a", 0, 1, 2**64), lambda: it.islice("a", IndexRaises()), lambda: it.islice("a", IndexRaises(), 1), lambda: it.islice("a", 0, IndexRaises()), lambda: it.islice("a", 0, 1, IndexRaises()), lambda: it.islice("a", Index(1)), lambda: list(it.islice("ab", Index(1), Index(2), Index(1))), lambda: it.islice(NoIter(), 1), lambda: it.islice(BadIter(), 1), lambda: it.islice(IterRaises(), 1), lambda: it.islice("a", 2**63 - 1), lambda: it.islice("a", 2**63),
          lambda: it.product(1), lambda: it.product("a", 1), lambda: it.product(repeat=-1), lambda: it.product(repeat="a"), lambda: it.product(repeat=2**64), lambda: it.product(x=1), lambda: it.product(repeat=1, x=1), lambda: it.product(rpeat=1), lambda: it.product("a", repeat=2**62), lambda: it.product(1, repeat=0), lambda: it.product(repeat=None), lambda: it.product(repeat=Index(1)),
          lambda: it.combinations(), lambda: it.combinations("a"), lambda: it.combinations("a", 1, 2), lambda: it.combinations("a", r=1, x=1), lambda: it.combinations("a", x=1), lambda: it.combinations("a", 1, r=1), lambda: it.combinations(r=1), lambda: it.combinations(1, 1), lambda: it.combinations("a", -1), lambda: it.combinations("a", "b"), lambda: it.combinations("a", 2**64), lambda: it.combinations(1, -1), lambda: it.combinations("a", None), lambda: it.combinations("a", Index(1)), lambda: it.combinations(iterable="a", rr=1), lambda: it.combinations(iterables="a", r=1),
          lambda: it.combinations_with_replacement(), lambda: it.combinations_with_replacement("a"), lambda: it.combinations_with_replacement("a", -1), lambda: it.combinations_with_replacement("a", "b"), lambda: it.combinations_with_replacement(1, 1), lambda: it.combinations_with_replacement("a", 1, 2),
          lambda: it.permutations(), lambda: it.permutations(1), lambda: it.permutations("a", -1), lambda: it.permutations("a", "b"), lambda: it.permutations("a", 2**64), lambda: it.permutations("a", -(2**64)), lambda: it.permutations("a", 1, 2), lambda: it.permutations("a", x=1), lambda: it.permutations("a", Index(1)), lambda: it.permutations(1, "b"), lambda: it.permutations("a", True), lambda: it.permutations("a", 1.5 if False else "c"),
          lambda: it.accumulate(), lambda: it.accumulate(1), lambda: it.accumulate("a", None, None), lambda: it.accumulate("a", None, 1), lambda: it.accumulate("a", x=1), lambda: it.accumulate("a", intial=1), lambda: list(it.accumulate(["a", 1])), lambda: list(it.accumulate([1, 2], 5)), lambda: list(it.accumulate([1, 2], initial="a")),
          lambda: it.batched(), lambda: it.batched("a"), lambda: it.batched("a", 0), lambda: it.batched("a", -1), lambda: it.batched("a", "b"), lambda: it.batched("a", 2**64), lambda: it.batched(1, 1), lambda: it.batched("a", 1, True), lambda: it.batched("a", 1, 2, strict=True), lambda: it.batched("a", 1, x=1), lambda: it.batched("a", 1, strct=True), lambda: list(it.batched("abc", 2, strict=True)), lambda: it.batched(1, 0),
          lambda: it.pairwise(), lambda: it.pairwise(1), lambda: it.pairwise("a", "b"), lambda: it.pairwise(x="a"), lambda: it.pairwise(iterable="a"),
          lambda: it.compress(), lambda: it.compress("a"), lambda: it.compress(1, "a"), lambda: it.compress("a", 1), lambda: it.compress("a", "b", "c"), lambda: it.compress("a", x=1), lambda: it.compress("a", selector=1),
          lambda: it.takewhile(), lambda: it.takewhile(None), lambda: it.takewhile(None, 1), lambda: it.takewhile(None, "a", "b"), lambda: it.takewhile(None, "a", x=1), lambda: list(it.takewhile(None, "a")), lambda: list(it.takewhile(1, "a")),
          lambda: it.dropwhile(), lambda: it.dropwhile(None), lambda: it.dropwhile(None, 1), lambda: it.dropwhile(None, "a", x=1), lambda: list(it.dropwhile(None, "a")),
          lambda: it.filterfalse(), lambda: it.filterfalse(None), lambda: it.filterfalse(None, 1), lambda: it.filterfalse(None, "a", x=1), lambda: list(it.filterfalse(1, "a")),
          lambda: it.starmap(), lambda: it.starmap(None), lambda: it.starmap(None, 1), lambda: it.starmap(None, "a", x=1), lambda: list(it.starmap(None, [()])), lambda: list(it.starmap(max, [1])), lambda: list(it.starmap(max, [None])),
          lambda: it.zip_longest(1), lambda: it.zip_longest("a", 1), lambda: it.zip_longest(x=1), lambda: it.zip_longest(fillvalue=1, x=2), lambda: it.zip_longest(fill=1),
          lambda: it.groupby(), lambda: it.groupby(1), lambda: it.groupby("a", None, 1), lambda: it.groupby("a", x=1), lambda: it.groupby("a", ky=None), lambda: it.groupby(key=None), lambda: list(it.groupby("a", 1)), lambda: it.groupby(iterables="a"),
          lambda: it.cycle(), lambda: it.cycle(1), lambda: it.cycle("a", "b"), lambda: it.cycle(x="a"), lambda: it.cycle(iterable="a"),
          lambda: it.count("a"), lambda: it.count(1, "a"), lambda: it.count(None), lambda: it.count(1, None), lambda: it.count(1, 2, 3), lambda: it.count(x=1), lambda: it.count(stat=1), lambda: it.count(1, start=2), lambda: it.count(Index(1)), lambda: next(it.count(Index(1), 1)),
          lambda: it.repeat(), lambda: it.repeat(1, "a"), lambda: it.repeat(1, 2, 3), lambda: it.repeat(1, x=1), lambda: it.repeat(1, tmes=1), lambda: it.repeat(1, 2**64), lambda: it.repeat(1, -(2**64)), lambda: it.repeat(times=1), lambda: it.repeat(1, None), lambda: list(it.repeat(1, Index(2))), lambda: list(it.repeat(1, True)),
          lambda: it.tee(), lambda: it.tee(1), lambda: it.tee("a", 1, 2), lambda: it.tee("a", n=1), lambda: it.tee("a", -1), lambda: it.tee("a", "b"), lambda: it.tee("a", 2**64), lambda: it.tee(1, 0), lambda: it.tee(1, -1), lambda: it.tee("a", None), lambda: it.tee("a", Index(1)) and 0, lambda: it.tee(iterable="a"),
          lambda: it._tee(), lambda: it._tee(1), lambda: it._tee("a", "b"), lambda: it._tee(x=1), lambda: type(it._tee("a")).__name__, lambda: list(it._tee("ab")), lambda: it._tee(it._tee("ab")).__class__.__name__,
          lambda: it._grouper(), lambda: it._grouper(1, 2), lambda: it._grouper(None, 2), lambda: it._grouper(it.groupby("a"), 2, 3), lambda: it._grouper(x=1), lambda: list(it._grouper(it.groupby("a"), "a")),
          lambda: it._tee_dataobject(), lambda: it._tee_dataobject(1, 2, 3), lambda: it._tee_dataobject(iter("a"), [], None).__class__.__name__, lambda: it._tee_dataobject(iter("a"), [1], 2), lambda: it._tee_dataobject(iter("a"), [1] * 58, None), lambda: it._tee_dataobject(iter("a"), [1] * 57, 2), lambda: it._tee_dataobject(iter("a"), [1] * 57, None).__class__.__name__, lambda: it._tee_dataobject(iter("a"), [1] * 57, it._tee_dataobject(iter("b"), [], None)).__class__.__name__, lambda: it._tee_dataobject(iter("a"), [], None, x=1)):
    show(f)
"""),
    ('after_an_exception_and_at_the_end', SOURCES + """import itertools as it
def bad(items=(1, 2)):
    return Raises(items, ValueError("source"))
def key_raises(x):
    raise KeyError("key")
print(after(it.chain(bad(), "z")), after(it.chain.from_iterable(bad(["a"]))), after(it.chain(Ends("v"), "z")), after(it.chain.from_iterable(Ends("v"))), after(it.chain.from_iterable(["a", 1, "b"])), after(it.chain("a", NoIter(), "b")))
print(after(it.islice(bad(), 5)), after(it.islice(bad(), 2, 5)), after(it.islice(Ends("v"), 2)), after(it.islice(bad(), 1)), after(it.islice("abc", 1)))
print(after(it.accumulate(bad())), after(it.accumulate(Ends("v"))), after(it.accumulate([1, "a", 2])), after(it.accumulate([1, 2], key_raises)))
print(after(it.batched(bad(), 5)), after(it.batched(Ends("v"), 2)), after(it.batched(bad(), 1)), after(it.batched("abc", 2, strict=True)), after(it.batched("ab", 2, strict=True)))
print(after(it.pairwise(bad())), after(it.pairwise(bad([]))), after(it.pairwise(Ends("v"))), after(it.pairwise(bad([1]))), after(it.pairwise("ab")))
print(after(it.compress(bad(), [1, 1, 1])), after(it.compress("abc", bad([1]))), after(it.compress(Ends("v"), [1])), after(it.compress("a", Ends("v"))))
print(after(it.takewhile(bool, bad())), after(it.takewhile(bool, Ends("v"))), after(it.takewhile(key_raises, "a")), after(it.takewhile(bool, [1, 0, 1])))
print(after(it.dropwhile(bool, bad())), after(it.dropwhile(bool, Ends("v"))), after(it.dropwhile(key_raises, "ab")), after(it.dropwhile(bool, [1, 0, 1])))
print(after(it.filterfalse(bool, bad([0]))), after(it.filterfalse(bool, Ends("v"))), after(it.filterfalse(key_raises, "ab")), after(it.starmap(max, bad([(1, 2)]))), after(it.starmap(max, Ends("v"))), after(it.starmap(key_raises, [(1,)])), after(it.starmap(max, [(1, 2), 5, (3, 4)])))
print(after(it.zip_longest(bad(), "z")), after(it.zip_longest("z", bad([]))), after(it.zip_longest(Ends("v"), "z")), after(it.zip_longest("ab", Ends("v"))), after(it.zip_longest(Ends("v"))), after(it.zip_longest("ab", bad([1]), "xyz")))
print(after(it.cycle(bad())), after(it.cycle(Ends("v"))), after(it.cycle(bad([]))), after(it.cycle("ab"), 5))
gb = it.groupby(bad())
print(after(gb))
gb = it.groupby("ab", key_raises)
print(after(gb))
gb = it.groupby(Ends("v"))
print(after(gb))
t1, t2 = it.tee(bad())
print(after(t1), after(t2))
t1, t2 = it.tee(Ends("v"))
print(after(t1), after(t2))
print(after(it.product("a", "b")), after(it.combinations("ab", 1)), after(it.combinations_with_replacement("a", 1)), after(it.permutations("a")), after(it.repeat("a", 1)), after(it.islice(it.count(), 2)))
class Key:
    def __init__(self, n):
        self.n = n
    def __eq__(self, other):
        if self.n == 3 or other.n == 3:
            raise ValueError("eq")
        return self.n == other.n
gb = it.groupby([Key(1), Key(1), Key(3), Key(4)])
k, g = next(gb)
print(k.n, after(g, 3), after(gb, 3))
gb = it.groupby([Key(1), Key(3), Key(1)])
print(type(next(gb)[1]).__name__, after(gb, 2), after(gb, 1))
class NotTrue:
    def __bool__(self):
        raise ValueError("no truth")
print(after(it.compress("ab", [NotTrue(), 1])), after(it.takewhile(lambda x: NotTrue(), "ab")), after(it.dropwhile(lambda x: NotTrue(), "ab")), after(it.filterfalse(lambda x: NotTrue(), "ab")), after(it.filterfalse(None, [NotTrue(), 0])))
"""),
    ('groupby_and_its_groups', """import itertools as it
gb = it.groupby("aabbc")
k1, g1 = next(gb)
print(k1, next(g1))
k2, g2 = next(gb)
print(type(g2).__name__)
print(k2, list(g1), next(g2), list(g2), next(g2, "end"), list(g1))
print(next(gb)[0], next(gb, "end"), next(gb, "end"), list(g2))
gb = it.groupby("aab")
groups = list(gb)
print([k for k, g in groups], [list(g) for k, g in groups])
gb = it.groupby("aab")
k, g = next(gb)
g2 = it._grouper(gb, "a")
print(list(g), list(g2), next(gb, ("end",))[0])
gb = it.groupby("aab")
k, g = next(gb)
copy = iter(g)
print(copy is g, type(g).__name__, next(g), next(copy), next(copy, "end"), next(gb)[0], next(gb, "end"))
class Reenter:
    def __init__(self, n, gb=None):
        self.n = n
        self.gb = gb
    def __eq__(self, other):
        if holder and holder[0] is not None and self.n == 2:
            g = holder.pop()
            print("re-entered", type(next(g, "end")).__name__)
        return self.n == other.n
    def __repr__(self):
        return "R" + str(self.n)
holder = []
gb = it.groupby([Reenter(1), Reenter(2), Reenter(2), Reenter(3)])
print(next(gb)[0])
holder.append(gb)
print(next(gb)[0], next(gb, ("end",))[0])
holder.clear()
calls = []
def key(x):
    calls.append(x)
    return x // 2
gb = it.groupby([1, 2, 3, 4, 5], key)
print(calls)
print(next(gb)[0], calls)
print(next(gb)[0], calls)
class Eq:
    def __init__(self, n):
        self.n = n
    def __eq__(self, other):
        print("eq", self.n, other.n)
        return "yes" if self.n == other.n else ""
print([(k.n, len(list(g))) for k, g in it.groupby([Eq(1), Eq(1), Eq(2)])])
same = object()
print([len(list(g)) for k, g in it.groupby([same, same])])
class Never:
    def __eq__(self, other):
        return False
n = Never()
print([len(list(g)) for k, g in it.groupby([n, n, n])])
"""),
    ('tee_and_its_chain', SHOW + """import itertools as it
a, b = it.tee(range(200))
print(next(a), sum(a), next(b), list(b)[-1], next(a, "end"))
a, b, c = it.tee(range(130), 3)
print(list(it.islice(a, 60))[-1], list(it.islice(b, 57))[-1], next(c))
d = a.__copy__()
print(next(a), next(d), next(b), list(c)[-1])
print(type(a).__name__, type(d).__name__, it.tee(a)[0].__class__.__name__, len(it.tee(a, 2)))
x, y = it.tee(iter("abc"))
z, w = it.tee(x)
print(next(z), next(w), next(x), next(y), list(z), list(w), list(x), list(y))
i = it._tee("ab")
print(next(i), next(iter(i)), next(i, "end"))
class Back:
    def __init__(self):
        self.t = None
    def __iter__(self):
        return self
    def __next__(self):
        return next(self.t)
b = Back()
t1, t2 = it.tee(b)
b.t = t1
show(lambda: next(t1))
show(lambda: next(t2))
class Count:
    def __init__(self):
        self.n = 0
    def __iter__(self):
        print("iter asked", self.n)
        return self
    def __next__(self):
        self.n += 1
        return self.n
c = Count()
pair = it.tee(c)
print(next(pair[0]), next(pair[1]), next(pair[0]))
long_chain, tail = it.tee(range(300000))
print(sum(tail))
del tail
print(next(long_chain))
del long_chain
print("freed")
l1, l2 = it.tee(range(300000))
for _ in l2:
    pass
del l2
del l1
print("freed again")
"""),
    ('when_an_item_dies', LIFE + """watch("chain", lambda: it.chain(source(2), source(2)))
watch("from_iterable", lambda: it.chain.from_iterable([source(1), source(1)]))
watch("islice", lambda: it.islice(source(), 1, 5, 2))
watch("islice stop", lambda: it.islice(source(), 2))
watch("accumulate", lambda: it.accumulate(source(3)))
watch("accumulate initial", lambda: it.accumulate(source(2), initial=D(50)))
watch("accumulate func", lambda: it.accumulate(source(3), lambda a, b: b))
watch("batched", lambda: it.batched(source(5), 2))
watch("batched strict", lambda: it.batched(source(3), 2))
watch("pairwise", lambda: it.pairwise(source(4)), 5)
watch("compress", lambda: it.compress(source(4), source(4)))
watch("takewhile", lambda: it.takewhile(lambda x: x.n < 2, source()))
watch("takewhile bool", lambda: it.takewhile(bool, source()))
watch("dropwhile", lambda: it.dropwhile(lambda x: x.n < 2, source()))
watch("filterfalse", lambda: it.filterfalse(lambda x: x.n % 2 == 0, source()))
watch("filterfalse none", lambda: it.filterfalse(None, source()))
watch("starmap", lambda: it.starmap(lambda a, b: D(a.n + b.n + 10), it.batched(source(), 2)))
watch("zip_longest", lambda: it.zip_longest(source(1), source(3)), 5)
watch("zip_longest fill", lambda: it.zip_longest(source(2), source(1), fillvalue=D(90)), 4)
watch("cycle", lambda: it.cycle(source(2)), 5)
watch("repeat", lambda: it.repeat(D(70), 2))
watch("count", lambda: it.count(D(1), D(2)), 2)
watch("product", lambda: it.product(source(2), source(2)), 5)
watch("combinations", lambda: it.combinations(source(3), 2), 4)
watch("cwr", lambda: it.combinations_with_replacement(source(2), 2), 4)
watch("permutations", lambda: it.permutations(source(2), 2), 3)
watch("groupby", lambda: it.groupby(source()), 4)
watch("groupby key", lambda: it.groupby(source(), lambda x: x.n // 2), 4)
watch("tee", lambda: it.tee(source(3))[0], 4)
print("== tee pair")
a, b = it.tee(source(3))
print(next(a), log)
log.clear()
print(next(a), log)
log.clear()
print(next(b), log)
log.clear()
del a
print(log)
log.clear()
del b
print(log)
log.clear()
print("== keeping a result")
p = it.pairwise(source(5))
first = next(p)
second = next(p)
print(first, second, first is second, log)
log.clear()
del second
print(log)
third = next(p)
print(third, log)
log.clear()
del first
print(log)
fourth = next(p)
print(fourth, third is fourth, log)
log.clear()
del third, fourth
print(log)
log.clear()
del p
print(log)
log.clear()
print("== groups")
gb = it.groupby(source())
k, g = next(gb)
print(k, next(g), log)
log.clear()
del k
print(log)
print(next(g, "end"), log)
log.clear()
del g
print(log)
print(clean(next(gb)), log)
log.clear()
del gb
print(log)
log.clear()
print("== a tuple is recycled when nothing else holds it")
for make in (lambda: it.pairwise(range(5)), lambda: it.product("ab", "cd"), lambda: it.combinations("abcd", 2), lambda: it.combinations_with_replacement("abc", 2), lambda: it.permutations("abc", 2), lambda: it.zip_longest("abcde", "de")):
    i = make()
    a = id(next(i))
    b = id(next(i))
    k = next(i)
    c = next(i)
    print(a == b, k is c, id(k) == a, k, c)
"""),
    ('sixty_four_bits', SHOW + """import itertools as it
c = it.count(2**63 - 3)
print([next(c) for _ in range(5)], c)
c = it.count(2**63 - 1)
print(c, next(c), c, next(c), c)
c = it.count(2**64)
print(c, next(c), c)
c = it.count(-(2**63))
print(c, next(c), next(c), c)
c = it.count(-(2**63) - 1)
print(c, next(c), next(c), c)
c = it.count(2**62 - 1)
print(next(c), next(c), next(c), c)
c = it.count(0, 2**64)
print(next(c), next(c), c)
c = it.count(1, 2**62)
print(next(c), next(c), next(c), c)
c = it.count(step=0)
print(next(c), next(c), c)
class I(int):
    pass
c = it.count(I(5))
print(c, next(c), type(next(c)).__name__, c)
c = it.count(I(5), I(1))
print(c, next(c), c)
c = it.count(I(5), I(2))
print(c, next(c), type(next(c)).__name__, c)
c = it.count(I(2**70))
print(c, type(next(c)).__name__, type(next(c)).__name__, c)
print(list(it.islice("abc", 2**63 - 1)), list(it.islice("abc", 1, 2**63 - 1, 2**63 - 1)), list(it.islice("abcd", 0, None, 2**63 - 1)), list(it.islice("abcd", 1, None, 2**62)), list(it.islice("abcd", 2**63 - 1, None)))
print(it.repeat("a", 2**63 - 1).__iter__().__class__.__name__, it.repeat("a", 2**63 - 1), it.repeat("a", 2**63 - 1).__length_hint__(), it.repeat("a", 2**62).__length_hint__())
show(lambda: it.combinations("ab", 2**63 - 1))
show(lambda: it.combinations_with_replacement("", 2**62))
show(lambda: it.permutations("ab", 2**63 - 1))
show(lambda: it.product("", repeat=2**60))
show(lambda: it.tee("a", 2**62))
show(lambda: it.combinations_with_replacement("a", 2**60))
"""),
    ('subclasses', SHOW + """import itertools as it
class C(it.chain):
    """ + '"""C doc"""' + """
    def __init__(self, *a, **k):
        self.seen = (a, k)
    def __next__(self):
        return "own " + str(super().__next__())
    def __repr__(self):
        return "C!"
c = C("ab", x=1)
print(c, c.seen, next(c), list(c), C.__doc__, type(c).__name__, isinstance(c, it.chain), C.__mro__, list(it.chain.__iter__(c)), c.__dict__)
class P(it.chain):
    pass
show(lambda: P("a", x=1))
class Cnt(it.count):
    pass
print(Cnt(), Cnt(3), Cnt(3, 2), next(Cnt(3)), repr(Cnt(2**64)))
class Rep(it.repeat):
    pass
print(Rep(1), Rep(1, 2), Rep(1, 2).__length_hint__())
class WithInit(it.islice):
    def __init__(self, *a, **k):
        print("init", a, k)
print(list(WithInit("ab", 1, flag=True)))
show(lambda: type("NoInit", (it.islice,), {})("ab", 1, flag=True))
show(lambda: type("N", (it.pairwise,), {"__init__": lambda self, *a, **k: None})("ab", x=1).__class__.__name__)
show(lambda: type("N", (it.starmap,), {"__init__": lambda self, *a, **k: None})(max, "ab", x=1).__class__.__name__)
show(lambda: type("N", (it.takewhile,), {})(None, "a", x=1))
show(lambda: type("N", (it.cycle,), {"__init__": lambda self, *a, **k: None})("a", x=1).__class__.__name__)
show(lambda: type("N", (it.product,), {})("a", x=1))
show(lambda: type("N", (it.count,), {})(x=1))
class Mix(it.chain):
    tag = "t"
    def more(self):
        return self.tag
m = Mix()
m.y = 1
print(m.more(), m.y, m.__dict__, list(m), vars(m), dir(m) == dir(Mix) + [] if False else 0, "more" in dir(m))
show(lambda: type("Both", (it.chain, it.count), {}))
show(lambda: type("Both", (it.chain, int), {}))
show(lambda: type("Both", (it.chain, dict), {}))
"""),
    ('users_of_it', """import itertools as it
def flatten(xs):
    return list(it.chain.from_iterable(xs))
def chunks(xs, n):
    i = iter(xs)
    out = []
    while True:
        c = list(it.islice(i, n))
        if not c:
            return out
        out.append(c)
print(flatten([[1], [2, 3], []]), chunks(range(7), 3), dict(zip("ab", it.count(1))), list(zip(it.repeat("a"), "xy")), list(map(pow, range(3), it.repeat(2))), sum(it.islice(it.count(1), 100)), [k for k, _ in it.groupby(sorted("mississippi"))], max(it.starmap(lambda a, b: a * b, it.product(range(4), range(4)))))
print(sorted(it.combinations(range(4), 2), key=lambda t: -t[1])[:2], {t for t in it.permutations("ab")} == {("a", "b"), ("b", "a")}, tuple(it.pairwise(range(3))), set(it.chain("a", "b")) == {"a", "b"}, list(reversed(list(it.accumulate(range(4))))), "".join(it.chain("ab", "cd")), "".join(it.repeat("x", 3)), [*it.islice("abc", 2)], (*it.compress("ab", [1, 0]),), {**dict(it.pairwise("abc"))}, dict(it.batched("abcd", 2)))
a, *rest = it.chain("abc")
print(a, rest, list(enumerate(it.repeat("z", 2))), list(it.chain(it.chain("a"), it.islice("b", 1))), any(it.repeat(True, 1)), all(it.repeat(False, 1)), min(it.islice(it.count(5), 3)), list(filter(None, it.chain([0], [1]))), len(list(it.tee("abc", 4))), sorted(it.chain([2], [1])))
for i, (x, y) in zip(it.count(), it.product("ab", repeat=2)):
    print(i, x, y)
print(list(it.takewhile(lambda n: n < 20, map(lambda n: n * n, it.count()))))
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
