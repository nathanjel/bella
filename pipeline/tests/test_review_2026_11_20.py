"""Review A23 of 2026-11-20 (range bc3f700..7a8e3f2), compiled against CPython: one program for each finding fixed.

Codex's Astra at medium effort read the range, with the day's change first (the state of a built-in type that the prelude
writes has no name, RL-507); the review log has its 28 findings as RL-535 to RL-562. Each program here is the report's own
reproduction, run under CPython and compiled: standard output, the exit status and standard error must agree. The findings
left open (RL-549, RL-552, RL-553) and the author's (RL-555) have no program here; RL-562 is the repair of a test of
the review before (`test_review_2026_11_19.py`), and RL-557 has a test of its own below, since it needs a directory as
standard input. RL-541 was done as a step of its own (C-3-78), with RL-563, which the session found beside it.

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_20
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from pipeline.build import build
from pipeline.tests.test_review_2026_11_19 import same

FINDINGS: list[tuple[str, str, str]] = [
    ('RL-535', 'Reading a partial member under a second name aborts the process', r'''
from functools import partial
class P(partial):
    _p_phcount = partial.args
p = P(abs, -2)
print(p._p_phcount)
'''),
    ('RL-536', 'Python code can still read the supposedly unnamed state', r'''
import functools

p = functools.partial(abs, -2)
ns = getattr(type(int | str).__setattr__, "__globals__", {})
print(hasattr(p, "_p_phcount"), "_bella_state_get" in ns)
if "_bella_state_get" in ns:
    print(ns["_bella_state_get"](p, "_p_phcount"))
'''),
    ('RL-537', 'A dialect subclass silently changes CSV parsing and output', r'''
import _csv, io

class D(_csv.Dialect):
    delimiter = ";"
d = D(delimiter=",")
print(d.delimiter, next(_csv.reader(["a,b"], d)))
f = io.StringIO()
_csv.writer(f, d).writerow(["a","b"])
print(repr(f.getvalue()))
'''),
    ('RL-538', 'Read-only members can be written through the generic setter or their descriptor', r'''
from functools import partial
p = partial(abs, -4)
try:
    print("readonly", object.__setattr__(p, "args", (-77,)))
except AttributeError as e:
    print("readonly", type(e).__name__, str(e))
print("readonly call", p())
'''),
    ('RL-539', 'A partial subclass can lose its underlying arguments during construction', r'''
import functools

try:
    class P(functools.partial):
        args = (11,)
    p = P(abs,-6)
    print(functools.partial.args.__get__(p))
except Exception as e:
    print(type(e).__name__)
'''),
    ('RL-540', 'Shadowing GenericAlias.__origin__ with a property prevents construction', r'''
import types

try:
    class G(types.GenericAlias):
        @property
        def __origin__(self):
            return tuple
    g = G(list, int)
    print(g.__origin__, repr(g), type(g()))
except Exception as e:
    print(type(e).__name__)
'''),
    ('RL-542', 'Constructing a text stream calls a subclass setter for _finalizing', r'''
import io

log = []
class T(io.TextIOWrapper):
    def __setattr__(self, name, value):
        log.append(name)
        super().__setattr__(name, value)
f = T(io.BytesIO())
print(log)
f.close()
'''),
    ('RL-543', 'Stream _finalizing accepts non-booleans and can be deleted', r'''
import io, os

for f in (io.TextIOWrapper(io.BytesIO()), io.BufferedWriter(io.BytesIO()), io.FileIO(os.devnull)):
    try:
        f._finalizing = 1
        print(repr(f._finalizing))
    except Exception as e:
        print(type(e).__name__)
    f.close()
'''),
    ('RL-544', 'GenericAlias and its iterator publish hidden field names through __slots__', r'''
import types
cls = type(iter(list[int]))
print(getattr(cls, "__slots__", None), "__static_attributes__" in vars(cls))
print(getattr(types.GenericAlias, "__slots__", None))
'''),
    ('RL-545', 'A user can construct an uninitialized generic-alias iterator', r'''
try:
    t = type(iter(list[int]))
    x = t()
    print(type(x).__name__)
except Exception as e:
    print(type(e).__name__)
'''),
    ('RL-546', 'A partial subclass cannot assign its own shadowing attribute', r'''
import functools

try:
    class P(functools.partial):
        args = (22,)
    p = P(abs,-5)
    p.args = "value"
    print(p.args, p())
except Exception as e:
    print(type(e).__name__)
'''),
    ('RL-547', 'Restoring BytesIO state replaces and aliases the instance dictionary', r'''
import io

b = io.BytesIO()
b.first = 1
state = {'second':2}
b.__setstate__((b"x",0,state))
print(vars(b), vars(b) is state)
'''),
    ('RL-548', 'BytesIO.__getstate__ loses the distinction between an absent and an allocated empty dictionary', r'''
import io

b = io.BytesIO(b'a')
print(b.__getstate__())
vars(b)
print(b.__getstate__())
'''),
    ('RL-550', 'Deleting a partial releases its argument before its callable', r'''
import functools

class Item:
    def __init__(self, name):
        self.name = name
    def __del__(self):
        print(self.name)
    def __call__(self):
        pass
p = functools.partial(Item('func'), Item('arg'), option=Item('kw'))
del p
print('done')
'''),
    ('RL-551', 'enumerate and zip release the current item too early', r'''
class Item:
    def __init__(self, name):
        self.name = name
    def __del__(self):
        print(self.name)
it = enumerate(map(Item, ['item']))
next(it)
print('advanced')
del it
print('done')
'''),
    ('RL-554', 'The newly presented formatter iterators have an extra class-dictionary entry', r'''
import _string

for it in (_string.formatter_parser(''),_string.formatter_field_name_split('a')[1]):
    print(type(it).__name__,vars(type(it)).get("__module__"), type(it).__module__)
'''),
    ('RL-556', 'Finalization calls flush on a replacement sys.__stdout__', r'''
import os
import sys
class F:
    closed = False
    def flush(self, emit=os.write):
        emit(1, b"flush\n")
sys.__stdout__ = F()
'''),
    ('RL-558', 'Newline translation bypasses a string subclass’s replace method', r'''
import io

class S(str):
    def replace(self, a, b):
        return "changed"
b = io.BytesIO()
w = io.TextIOWrapper(b, newline="\r\n", write_through=True)
print(w.write(S("a\n")), b.getvalue())
'''),
    ('RL-559', 'A buffered UTF-8 write releases its input before flush', r'''
import io

class S(str):
    def __del__(self):
        print("released")
w = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
w.write(S("abc"))
print("flushing")
w.flush()
'''),
    ('RL-560', 'A custom incremental encoder returning its input is rejected', r'''
import io, codecs

try:
    class E:
        def __init__(self, errors): pass
        def encode(self, text):
            return text
    def find(name):
        if name == "own":
            return codecs.CodecInfo(name="own", encode=None, decode=None, incrementalencoder=E, incrementaldecoder=codecs.lookup("utf-8").incrementaldecoder)
    codecs.register(find)
    b = io.BytesIO()
    w = io.TextIOWrapper(b, encoding="own", write_through=True)
    print(w.write("abc"), b.getvalue())
except Exception as e:
    print(type(e).__name__)
'''),
    ('RL-561', 'A non-string codec name can incorrectly enter fast-encoder selection', r'''
import codecs, io

try:
    class Label:
        @property
        def __class__(self): return str
    u = codecs.lookup('utf-8')
    def find(n):
        if n == "custom":
            return codecs.CodecInfo(name=Label(), encode=u.encode, decode=u.decode, incrementalencoder=u.incrementalencoder, incrementaldecoder=u.incrementaldecoder)
    codecs.register(find)
    b = io.BytesIO()
    w = io.TextIOWrapper(b, encoding="custom", write_through=True)
    print(w.write("hello"), b.getvalue())
except Exception as e:
    print(type(e).__name__)
'''),
    ('RL-538', 'the same for a generic alias, a union and a Struct', r'''
import struct
g = list[int]
u = int | str
s = struct.Struct("I")
for label, obj, name, value in (("alias", g, "__origin__", tuple), ("union", u, "__args__", (float, bool)), ("struct", s, "size", 1)):
    for way in ("object.__setattr__", "the member"):
        try:
            if way == "the member":
                getattr(type(obj), name).__set__(obj, value)
            else:
                object.__setattr__(obj, name, value)
            print(label, way, "stored")
        except AttributeError as e:
            print(label, way, "AttributeError", e, e.name)
print(g, u, s.size, len(s.pack(1)))
'''),
    ('RL-551', 'zip keeps its result as enumerate does, and gives a tuple of its own while the last one is held', r'''
class Item:
    def __init__(self, name):
        self.name = name
    def __del__(self):
        print("gone:", self.name)
it = zip(map(Item, ["a", "b"]), map(Item, ["c", "d"]))
next(it)
print("advanced once")
kept = next(it)
print("advanced twice; the pair is held:", [i.name for i in kept])
again = enumerate(map(Item, ["e", "f"]), 5)
first = next(again)
second = next(again)
print(first[0], second[0], first is second, first[1].name, second[1].name)
del it
print("the zip is gone")
del kept, first, second, again
print("done")
'''),
    ('RL-547', 'the state of a stream with no dict yet takes the given dict itself', r'''
import io
for kind, state in ((io.BytesIO, (b"x", 0)), (io.StringIO, ("x", None, 0))):
    b = kind()
    given = {"second": 2}
    b.__setstate__(state + (given,))
    print(kind.__name__, vars(b), vars(b) is given, b.__getstate__()[-1] is given, b.__getstate__()[-1])
    c = kind()
    print(kind.__name__, c.__getstate__()[-1], vars(c), c.__getstate__()[-1])
'''),
    ('RL-548', "a stream's state reads and replaces the dict it has, whatever a deriving class has under __dict__", r'''
import io

class B(io.BytesIO):
    __dict__ = property(lambda self: {"lie": True})

b = B(b"ab")
print(b.__getstate__())
b.x = 1
print(b.__getstate__(), b.__dict__)
b.__setstate__((b"cd", 0, {"given": 1}))
print(b.__getstate__(), b.x, b.given)
c = B()
c.__setstate__((b"cd", 0, {"g": 2}))
print(c.__getstate__(), c.g, c.__dict__)

class S(io.StringIO):
    __dict__ = property(lambda self: {"lie": True})

s = S("ab")
print(s.__getstate__())
s.y = 2
print(s.__getstate__(), s.__dict__)
s.__setstate__(("cd", None, 0, {"given": 1}))
print(s.__getstate__(), s.y, s.given)
t = S()
t.__setstate__(("cd", None, 0, {"g": 1}))
print(t.__getstate__(), t.g)
'''),
    ('RL-541', "A second subclass's same-named slot overwrites the first subclass's slot", r'''
import collections

class D(collections.deque):
    __slots__ = ("_a_items",)

class F(D):
    __slots__ = ("_a_items",)
o = F([2])
D._a_items.__set__(o, "D")
F._a_items.__set__(o, "F")
print(D._a_items.__get__(o), F._a_items.__get__(o), list(o))
'''),
    ('RL-563', 'a member of a class that is no base, which a class has under a name, is read as a slot of the name', r'''
class A:
    __slots__ = ("x",)

class B:
    __slots__ = ("x",)

class H(A):
    __slots__ = ()
    x = B.x

h = H()
A.x.__set__(h, "A's")
for label, act in (("read", lambda: h.x), ("store", lambda: setattr(h, "x", 1)), ("delete", lambda: delattr(h, "x")),
                   ("object.__setattr__", lambda: object.__setattr__(h, "x", 1)), ("object.__delattr__", lambda: object.__delattr__(h, "x")),
                   ("object.__getattribute__", lambda: object.__getattribute__(h, "x")), ("getattr with a default", lambda: getattr(h, "x", "default"))):
    try:
        print(label, repr(act()))
    except (TypeError, AttributeError) as e:
        print(label, type(e).__name__, e)
print(A.x.__get__(h))
'''),
]


def pytest_generate_tests(metafunc: Any) -> None:
    if "finding" in metafunc.fixturenames:
        metafunc.parametrize("finding", FINDINGS, ids=[f"{rl}-{name}" for rl, name, _ in FINDINGS])


def test_finding(finding: tuple[str, str, str]) -> None:
    same(finding[2])


def test_a_directory_as_standard_input() -> None:
    """RL-557: init_sys_streams' first check. The start ends with its own message, before any stream is made: nothing of
    the program runs, the status is 1, and standard error is CPython's but for the thread's number and name."""
    if shutil.which("g++") is None:
        return
    env = dict(os.environ, PYTHONHASHSEED="0")
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text('print("never printed")\n', encoding="utf-8")
        exe = str(build(prog, "prog.py"))
        runs = []
        for command in ([sys.executable, "prog.py"], [exe]):
            folder = os.open(tmp, os.O_RDONLY)
            try:
                done = subprocess.run(command, capture_output=True, text=True, check=False, env=env, cwd=tmp, stdin=folder)
            finally:
                os.close(folder)
            lines = done.stderr.splitlines()
            runs.append((done.returncode, done.stdout, lines[:3], [line.split(" 0x")[0] + line[line.index(" (most"):] for line in lines[3:]]))
    assert runs[0] == runs[1], runs
    assert runs[0][0] == 1 and runs[0][2][0] == "Fatal Python error: init_sys_streams: <stdin> is a directory, cannot continue", runs[0]


if __name__ == "__main__":
    for item in FINDINGS:
        test_finding(item)
    test_a_directory_as_standard_input()
