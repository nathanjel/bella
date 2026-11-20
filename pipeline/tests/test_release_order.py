"""The order in which a built-in type lets go of what it holds (RL-550's rule swept over the types; RL-565 of review A24).

An object that is on no cycle dies when its last reference goes, and what it holds dies with it, in the order of the type's
dealloc function. A program sees that order: a callable, an iterable or a value with a `__del__` says when it goes, and so
does the callback of a weak reference. The runtime writes about 120 of CPython's C types in Python; each lets go of its
fields in the order its class declares them, clears its weak references and its dict where its dealloc does
(`__release__` where that is not the common place), and an object of a class that derives from it lets go of that class's
slots and of a dict the class added first (`RefClass.release` in the model, `set_release` in the header).

The sweep makes an object of each type whose fields hold values that record their deaths, fresh or after a first step,
with a weak reference where the type takes one, and for 34 types an object of three classes that derive from it (with a
dict, with slots, with slots, a dict and room for weak references). It drops the object and compares the order of the
deaths with CPython's, a process for each row.

Run under pytest or directly: python3 -m pipeline.tests.test_release_order
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pipeline.build import build

SWEEP = r'''
import _json
import collections
import contextvars
import csv
import functools
import io
import itertools
import operator
import sys
import types
import typing
import weakref

DEATHS = []


class Val:
    def __init__(self, label):
        self.label = label

    def __del__(self):
        DEATHS.append(self.label)


class Fn(Val):
    def __call__(self, *args, **kwds):
        return args[0] if args else None


class It(Val):
    def __init__(self, label, items=()):
        Val.__init__(self, label)
        self.items = list(items)

    def __iter__(self):
        return self

    def __next__(self):
        if self.items:
            return self.items.pop(0)
        raise StopIteration


class Num(Val):
    def __int__(self):
        return 1

    def __index__(self):
        return 1

    def __add__(self, other):
        return Num(self.label + "+")

    def __radd__(self, other):
        return Num("+" + self.label)


class Seq(Val):
    def __len__(self):
        return 2

    def __getitem__(self, i):
        return i


class Raw(Val, io.RawIOBase):
    def __init__(self, label):
        io.RawIOBase.__init__(self)
        Val.__init__(self, label)

    def readable(self):
        return True

    def writable(self):
        return True

    def seekable(self):
        return True

    def readinto(self, b):
        return 0

    def write(self, b):
        return len(b)

    def seek(self, pos, whence=0):
        return 0

    def tell(self):
        return 0

    def __del__(self):
        DEATHS.append(self.label)


class Sink(Val):
    def write(self, text):
        return len(text)


class Context(Val):
    strict = True
    memo = None

    def __init__(self, label):
        Val.__init__(self, label)
        self.object_hook = Fn("object_hook")
        self.object_pairs_hook = Fn("object_pairs_hook")
        self.array_hook = Fn("array_hook")
        self.parse_float = Fn("parse_float")
        self.parse_int = Fn("parse_int")
        self.parse_constant = Fn("parse_constant")


class Target:
    pass


TARGET = Target()


def vals(prefix, n):
    return [Val(prefix + str(i)) for i in range(n)]


def with_attrs(obj, *names):
    for name in names:
        setattr(obj, name, Val("." + name))
    return obj


def started(obj, n=1):
    for _ in range(n):
        next(obj)
    return obj


def called(fn, *args):
    fn(*args)
    return fn


def scanner():
    context = Context("context")
    return _json.make_scanner(context)


def tee_branch():
    a, b = itertools.tee(It("it", vals("v", 3)))
    next(a)
    next(a)
    del a
    return b


def grouper():
    g = itertools.groupby(It("it", [Val("v0"), Val("v1")]), Fn("key"))
    key, group = next(g)
    del key
    return (g, group)


class Deque(collections.deque):
    pass


class Partial(functools.partial):
    pass


class Slotted(collections.deque):
    __slots__ = ("b", "a")


class Enum2(enumerate):
    __slots__ = ("z", "y")


def derived(base, args, kwds=None, slots=None):
    """An object of a class that derives from `base`, with values in its own slots (or its dict) and the base's."""
    def make():
        if slots is None:
            class Sub(base):
                pass
            names = ("m", "k")
        else:
            class Sub(base):
                __slots__ = slots
            names = tuple(n for n in slots if not n.startswith("__")) + (("extra",) if "__dict__" in slots else ())
        obj = Sub(*args(), **(kwds() if kwds is not None else {}))
        for name in names:
            setattr(obj, name, Val("." + name))
        return obj
    return make


BASES = [
    ("enumerate", enumerate, lambda: (It("it"),), None),
    ("zip", zip, lambda: (It("a"), It("b")), None),
    ("map", map, lambda: (Fn("func"), It("a")), None),
    ("filter", filter, lambda: (Fn("func"), It("it")), None),
    ("reversed", reversed, lambda: (Seq("seq"),), None),
    ("property", property, lambda: (Fn("get"), Fn("set")), None),
    ("staticmethod", staticmethod, lambda: (Fn("callable"),), None),
    ("classmethod", classmethod, lambda: (Fn("callable"),), None),
    ("deque", collections.deque, lambda: (vals("d", 2),), None),
    ("defaultdict", collections.defaultdict, lambda: (Fn("factory"), {"k": Val("value")}), None),
    ("OrderedDict", collections.OrderedDict, lambda: (), lambda: {"a": Val("a"), "b": Val("b")}),
    ("partial", functools.partial, lambda: (Fn("func"), Val("arg0")), lambda: {"kw": Val("kw")}),
    ("itertools.chain", itertools.chain, lambda: (It("a"), It("b")), None),
    ("itertools.islice", itertools.islice, lambda: (It("it"), 3), None),
    ("itertools.groupby", itertools.groupby, lambda: (It("it"), Fn("key")), None),
    ("itertools.accumulate", itertools.accumulate, lambda: (It("it"), Fn("func")), None),
    ("itertools.count", itertools.count, lambda: (Num("start"), Num("step")), None),
    ("itertools.repeat", itertools.repeat, lambda: (Val("element"),), None),
    ("itertools.product", itertools.product, lambda: (vals("a", 2),), None),
    ("itertools.zip_longest", itertools.zip_longest, lambda: (It("a"), It("b")), lambda: {"fillvalue": Val("fill")}),
    ("itertools.starmap", itertools.starmap, lambda: (Fn("func"), It("it")), None),
    ("itertools.cycle", itertools.cycle, lambda: (It("it"),), None),
    ("itertools.compress", itertools.compress, lambda: (It("data"), It("selectors")), None),
    ("itertools.pairwise", itertools.pairwise, lambda: (It("it"),), None),
    ("itertools.batched", itertools.batched, lambda: (It("it"), 2), None),
    ("BytesIO", io.BytesIO, lambda: (b"ab",), None),
    ("StringIO", io.StringIO, lambda: ("ab",), None),
    ("BufferedReader", io.BufferedReader, lambda: (Raw("raw"),), None),
    ("BufferedRWPair", io.BufferedRWPair, lambda: (Raw("reader"), Raw("writer")), None),
    ("SimpleNamespace", types.SimpleNamespace, lambda: (), lambda: {"n": Val("n")}),
    ("weakref.ref", weakref.ref, lambda: (TARGET, Fn("callback")), None),
    ("ContextVar", contextvars.ContextVar, lambda: ("name",), lambda: {"default": Val("default")}),
    ("slice", slice, lambda: (Val("start"), Val("stop")), None),
    ("itemgetter", operator.itemgetter, lambda: (Val("i0"),), None),
]


ROWS = [
    ("enumerate", lambda: enumerate(It("it"))),
    ("enumerate, started", lambda: started(enumerate(It("it", vals("v", 2))))),
    ("enumerate subclass with slots", lambda: with_attrs(Enum2(It("it")), "y", "z")),
    ("zip", lambda: zip(It("a"), It("b"), It("c"))),
    ("zip, started", lambda: started(zip(It("a", vals("a", 2)), It("b", vals("b", 2))))),
    ("map", lambda: map(Fn("func"), It("a"), It("b"))),
    ("filter", lambda: filter(Fn("func"), It("it"))),
    ("reversed", lambda: reversed(Seq("seq"))),
    ("callable_iterator", lambda: iter(Fn("callable"), Val("sentinel"))),
    ("property", lambda: property(Fn("get"), Fn("set"), Fn("del"), Val("doc"))),
    ("staticmethod", lambda: with_attrs(staticmethod(Fn("callable")), "extra")),
    ("classmethod", lambda: with_attrs(classmethod(Fn("callable")), "extra")),
    ("slice", lambda: slice(Val("start"), Val("stop"), Val("step"))),
    ("bound method", lambda: types.MethodType(Fn("func"), Val("self"))),
    ("itertools.batched", lambda: itertools.batched(It("it"), 2)),
    ("itertools.pairwise", lambda: itertools.pairwise(It("it"))),
    ("itertools.pairwise, started", lambda: started(itertools.pairwise(It("it", vals("v", 3))))),
    ("itertools.groupby", lambda: itertools.groupby(It("it"), Fn("key"))),
    ("itertools.groupby, started", lambda: started(itertools.groupby(It("it", vals("v", 2)), Fn("key")))),
    ("itertools._grouper", grouper),
    ("itertools.tee", lambda: itertools.tee(It("it"))),
    ("itertools.tee, one branch ahead", tee_branch),
    ("itertools.cycle", lambda: itertools.cycle(It("it"))),
    ("itertools.cycle, started", lambda: started(itertools.cycle(It("it", vals("v", 3))), 2)),
    ("itertools.dropwhile", lambda: itertools.dropwhile(Fn("func"), It("it"))),
    ("itertools.takewhile", lambda: itertools.takewhile(Fn("func"), It("it"))),
    ("itertools.starmap", lambda: itertools.starmap(Fn("func"), It("it"))),
    ("itertools.filterfalse", lambda: itertools.filterfalse(Fn("func"), It("it"))),
    ("itertools.compress", lambda: itertools.compress(It("data"), It("selectors"))),
    ("itertools.islice", lambda: itertools.islice(It("it"), 3)),
    ("itertools.chain", lambda: itertools.chain(It("a"), It("b"))),
    ("itertools.chain, started", lambda: started(itertools.chain(It("a", vals("a", 2)), It("b")))),
    ("itertools.chain.from_iterable", lambda: itertools.chain.from_iterable(It("source"))),
    ("itertools.product", lambda: itertools.product(vals("a", 2), vals("b", 2))),
    ("itertools.product, started", lambda: started(itertools.product(vals("a", 2), vals("b", 2)))),
    ("itertools.combinations", lambda: itertools.combinations(vals("p", 3), 2)),
    ("itertools.combinations, started", lambda: started(itertools.combinations(vals("p", 3), 2))),
    ("itertools.combinations_with_replacement, started", lambda: started(itertools.combinations_with_replacement(vals("p", 2), 2))),
    ("itertools.permutations, started", lambda: started(itertools.permutations(vals("p", 3), 2))),
    ("itertools.accumulate", lambda: itertools.accumulate(It("it"), Fn("func"), initial=Val("initial"))),
    ("itertools.accumulate, started", lambda: started(itertools.accumulate(It("it", vals("v", 2)), Fn("func"), initial=Val("initial")), 2)),
    ("itertools.count", lambda: itertools.count(Num("start"), Num("step"))),
    ("itertools.repeat", lambda: itertools.repeat(Val("element"))),
    ("itertools.zip_longest", lambda: itertools.zip_longest(It("a"), It("b"), fillvalue=Val("fill"))),
    ("itertools.zip_longest, started", lambda: started(itertools.zip_longest(It("a", vals("a", 2)), It("b", vals("b", 1)), fillvalue=Val("fill")))),
    ("deque", lambda: collections.deque(vals("d", 3))),
    ("deque subclass with a dict", lambda: with_attrs(Deque(vals("d", 2)), "x", "y")),
    ("deque subclass with slots", lambda: with_attrs(Slotted(vals("d", 2)), "a", "b")),
    ("deque iterator", lambda: iter(collections.deque(vals("d", 2)))),
    ("defaultdict", lambda: collections.defaultdict(Fn("factory"), {"k": Val("value")})),
    ("OrderedDict", lambda: collections.OrderedDict(a=Val("a"), b=Val("b"))),
    ("partial", lambda: functools.partial(Fn("func"), Val("arg0"), Val("arg1"), kw=Val("kw"))),
    ("partial with attributes", lambda: with_attrs(functools.partial(Fn("func"), Val("arg0"), kw=Val("kw")), "x")),
    ("partial subclass with attributes", lambda: with_attrs(Partial(Fn("func"), Val("arg0"), kw=Val("kw")), "x")),
    ("cmp_to_key's key", lambda: functools.cmp_to_key(Fn("cmp"))(Val("obj"))),
    ("lru_cache's wrapper", lambda: functools.lru_cache(maxsize=2)(Fn("func"))),
    ("lru_cache's wrapper, called", lambda: called(called(functools.lru_cache(maxsize=4)(Fn("func")), "k1"), "k2")),
    ("lru_cache's wrapper, unbounded, called", lambda: called(functools.lru_cache(maxsize=None)(Fn("func")), "k1")),
    ("itemgetter", lambda: operator.itemgetter(Val("i0"), Val("i1"))),
    ("methodcaller", lambda: operator.methodcaller("name", Val("arg"), kw=Val("kw"))),
    ("weakref.ref with a callback", lambda: weakref.ref(TARGET, Fn("callback"))),
    ("ContextVar", lambda: contextvars.ContextVar("name", default=Val("default"))),
    ("csv.reader", lambda: csv.reader(It("lines"))),
    ("csv.writer", lambda: csv.writer(Sink("file"))),
    ("json's scanner", scanner),
    ("json's encoder", lambda: _json.make_encoder({"m": Val("marker")}, Fn("default"), Fn("encoder"), None, ": ", ", ", False, False, True)),
    ("BufferedReader", lambda: io.BufferedReader(Raw("raw"))),
    ("BufferedReader with an attribute", lambda: with_attrs(io.BufferedReader(Raw("raw")), "x")),
    ("BufferedRWPair", lambda: io.BufferedRWPair(Raw("reader"), Raw("writer"))),
    ("BufferedRandom", lambda: io.BufferedRandom(Raw("raw"))),
    ("TextIOWrapper", lambda: io.TextIOWrapper(io.BufferedReader(Raw("raw")))),
    ("BytesIO with an attribute", lambda: with_attrs(io.BytesIO(b"ab"), "x", "y")),
    ("StringIO with an attribute", lambda: with_attrs(io.StringIO("ab"), "x", "y")),
    ("GenericAlias", lambda: types.GenericAlias(Fn("origin"), (Val("arg0"), Val("arg1")))),
    ("SimpleNamespace", lambda: types.SimpleNamespace(b=Val("b"), a=Val("a"))),
    ("TypeAliasType", lambda: typing.TypeAliasType("Alias", Val("value"))),
]


def weak_callback(reference):
    DEATHS.append("weak")


def run(label, make):
    del DEATHS[:]
    try:
        obj = make()
    except Exception as e:
        print(label, "| not made:", type(e).__name__)
        return
    watcher = None
    if type(obj) is not tuple and not isinstance(obj, weakref.ref):
        try:
            watcher = weakref.ref(obj, weak_callback)
        except TypeError:
            pass
    before = list(DEATHS)
    del DEATHS[:]
    del obj
    print(label, "|", before, "|", DEATHS, "|", "watched" if watcher is not None else "takes no weak reference")


for name, base, args, kwds in BASES:
    ROWS.append((name + ": a class with a dict", derived(base, args, kwds)))
    ROWS.append((name + ": a class with slots", derived(base, args, kwds, ("b", "a"))))
    ROWS.append((name + ": a class with slots, a dict and room for weak references", derived(base, args, kwds, ("b", "__dict__", "__weakref__"))))

wanted = sys.argv[1:]
for label, make in ROWS:
    if not wanted or label in wanted:
        run(label, make)
if wanted == ["--labels"]:
    for label, _ in ROWS:
        print(label)
'''


def test_what_a_built_in_type_holds_goes_in_cpythons_order() -> None:
    if shutil.which("g++") is None:
        return
    folder = Path(tempfile.mkdtemp(prefix="bella-release-"))
    try:
        program = folder / "prog.py"
        program.write_text(SWEEP, encoding="utf-8")
        env = {**os.environ, "PYTHONHASHSEED": "0"}
        reference = subprocess.run([sys.executable, str(program)], capture_output=True, text=True, env=env, cwd=folder, timeout=300)
        assert reference.returncode == 0, reference.stderr
        theirs = dict(line.split(" | ", 1) for line in reference.stdout.splitlines())
        assert len(theirs) >= 175, len(theirs)
        binary = str(build(program, "prog.py"))
        wrong: list[str] = []
        for label, expected in theirs.items():            # a process for each row: one that stops takes no other with it
            compiled = subprocess.run([binary, label], capture_output=True, text=True, env=env, cwd=folder, timeout=120)
            got = compiled.stdout.strip().partition(" | ")[2]
            if compiled.returncode != 0 or got != expected:
                wrong.append(f"{label}: compiled {got!r} (status {compiled.returncode}, {compiled.stderr.strip()[-200:]!r}), CPython {expected!r}")
        assert not wrong, "\n".join(wrong)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    test_what_a_built_in_type_holds_goes_in_cpythons_order()
    print("ok")
