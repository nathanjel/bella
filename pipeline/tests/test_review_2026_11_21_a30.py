"""Review A30 of 2026-11-21 (range b04274c..6ff3049), compiled against CPython: a program for each finding fixed.

Codex's Astra at low effort read which frames count toward the recursion limit, the special methods of A29's fixes, the
item iterators' own pair (RL-584) and the native stack once more; the review log has its twelve findings as RL-643 to
RL-654. Held here: a copy of a dict's item iterator walks with the iterator's own pair (RL-643); a type's slots are read
from the type, whatever its metaclass shows as `__mro__` or `__dict__` (RL-644: the lookups are the runtime's now, in
every prelude); an exception the runtime caught, worked on and sent on keeps its traceback (RL-645: the rule is held by
`test_a_caught_exception_goes_on_through_rethrow`, which reads the runtime's sources); a slot's presence binds nothing
(RL-646, RL-647); the path conversions take a failed binding and None for no method (RL-648, RL-649); an OrderedDict's
iterator is at its end after a key's hash failed (RL-650); `open` and `io.FileIO` test their name's type and take a
failed integer conversion for a path (RL-651); a `fileno` that is None is called (RL-652); `RawIOBase.readall` goes on
after EINTR (RL-654), and so do the eight other places of `_io` where CPython's C does (RL-656, the class behind it: 22 of
the program's 75 rows differed). RL-653 is the wording of a message (D-08).

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_21_a30
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pipeline.tests.test_review_2026_11_19 import same

ROOT = Path(__file__).resolve().parents[2]

FINDINGS: list[tuple[str, str, str]] = [
    ('RL-643', 'a copy of an item iterator walks with the iterator\'s own pair', r'''
import collections, copy, types
class Value:
    def __init__(self, i): self.i = i
    def __del__(self): print("      del", self.i)
class Own(dict):
    def items(self): return dict.items(self)
def fill(): return {k: Value(k) for k in range(3)}
def plain():
    d = fill()
    return d, d
def own():
    d = Own(fill())
    return d, d
def default():
    d = collections.defaultdict(list, fill())
    return d, d
def ordered():
    d = collections.OrderedDict(fill())
    return d, d
def proxied():
    d = fill()
    return d, types.MappingProxyType(d)
def copied(label, make, walk, taken, keep):
    print("  ", label, "| steps taken first:", taken, "| their pairs kept:", keep)
    base, mapping = make()
    it = walk(mapping.items())
    held = [next(it) for _ in range(taken)]
    if not keep: held.clear()
    obj = copy.copy(it)
    base.clear()
    del base, mapping
    print("    the mapping is empty")
    held.clear()
    print("    the program's pairs are gone")
    del obj
    print("    the copy is gone")
    del it
    print("    the iterator is gone")
def reduced(label, make, walk):
    print("  ", label, "| reduced, and stepped")
    base, mapping = make()
    it = walk(mapping.items())
    items = it.__reduce__()[1][0]
    first = items[0]
    del items
    was = id(first)
    a = next(it)
    print("    another pair while the first is held:", a is not first, a[0] == first[0])
    del first, a
    b = next(it)
    print("    the iterator's own pair again:", id(b) == was)
    del b, it
    base.clear()
    print("    done")
for name, make in (("dict", plain), ("a dict subclass", own), ("defaultdict", default), ("OrderedDict", ordered), ("mappingproxy", proxied)):
    for way, walk in (("forward", iter), ("reversed", reversed)):
        print(name, way)
        for taken in (0, 1):
            for keep in (False, True):
                copied(name, make, walk, taken, keep)
        reduced(name, make, walk)
'''),
    ('RL-644', 'a type\'s slots are the type\'s, whatever its metaclass shows as __mro__ or __dict__', r'''
import bisect, collections, functools, io, itertools, operator, os, struct, time
asked = []
class Fake:
    def __fspath__(self): return "invented"
    def __index__(self): return 7
    def __int__(self): return 7
    def __float__(self): return 7.0
    def __getitem__(self, key): return 7
    def __len__(self): return 7
    def __iter__(self): return iter((7,))
    def __next__(self): return 7
    def fileno(self): return 7
class ByMro(type):
    @property
    def __mro__(cls):
        asked.append("__mro__")
        return (Fake, object)
class ByDict(type):
    @property
    def __dict__(cls):
        asked.append("__dict__")
        return vars(Fake)
class APath:
    def __fspath__(self): return "/dev/null"
class AnIndex:
    def __index__(self): return 1
def attempt(label, act):
    try: print("  ", label, "->", repr(act()), "| asked:", asked or "nothing")
    except Exception as e: print("  ", label, "->", type(e).__name__, "| asked:", asked or "nothing")
    asked.clear()
def opened(value):
    with open(value, "rb") as f: return f.read()
def raw(value):
    with io.FileIO(value) as f: return f.read()
def prepared(namespace):
    class Make(type):
        @classmethod
        def __prepare__(cls, name, bases): return namespace
    class T(metaclass=Make): pass
    return type(T).__name__
for meta in (ByMro, ByDict):
    class HasPath(APath, metaclass=meta): pass   # what it has is its own: the path is /dev/null
    class HasIndex(AnIndex, metaclass=meta): pass   # and the index 1
    class Bare(metaclass=meta): pass             # it has nothing: Fake answers for nothing
    for kind in (HasPath, Bare):
        print(meta.__name__, kind.__name__)
        attempt("os.fspath", lambda: os.fspath(kind()))
        attempt("os.stat", lambda: os.stat(kind()).st_size)
        attempt("os.path.exists", lambda: os.path.exists(kind()))
        attempt("open", lambda: opened(kind()))
        attempt("io.FileIO", lambda: raw(kind()))
        attempt("os.fsync", lambda: os.fsync(kind()))
        attempt("a class statement's namespace", lambda: prepared(kind()))
    for kind in (HasIndex, Bare):
        print(meta.__name__, kind.__name__)
        attempt("os.strerror", lambda: os.strerror(kind()) == os.strerror(1))
        attempt("os.urandom", lambda: len(os.urandom(kind())))
        attempt("struct.pack", lambda: struct.pack("b", kind()))
        attempt("time.gmtime", lambda: time.gmtime(kind()).tm_sec)
        attempt("bisect.bisect", lambda: bisect.bisect([0, 1, 2], 5, kind()))
        attempt("collections.deque", lambda: collections.deque([1, 2, 3], kind()))
        attempt("itertools.islice", lambda: list(itertools.islice(range(5), kind())))
        attempt("itertools.count", lambda: type(next(itertools.count(kind()))).__name__)
        attempt("functools.lru_cache", lambda: functools.lru_cache(kind())(len).cache_info().maxsize)
        attempt("operator.length_hint", lambda: operator.length_hint(kind(), 7))
'''),
    ('RL-645', 'an exception that passes a place where the runtime caught it keeps its traceback', r'''
import sys, traceback
n = 0
class Descriptor:
    def __set_name__(self, owner, name): go()
d = Descriptor()
def go():
    global n
    n += 1
    class Local: x = d
def entries(e):
    t, count = e.__traceback__, 0
    while t is not None:
        count += 1
        t = t.tb_next
    return count
for limit in (60, 150):
    for _ in range(2):
        n = 0
        sys.setrecursionlimit(limit)
        try: go()
        except RecursionError as e:
            sys.setrecursionlimit(1000)
            print("__set_name__ |", n, entries(e), len(traceback.extract_tb(e.__traceback__)), len(e.__notes__))
# the same count of entries from a level of calls below other places that catch, look, and send the exception on
def deep(k, act):
    if k: return deep(k - 1, act)
    return act()
class NoVars:
    __slots__ = ()
class Lost:
    def __getattr__(self, name): raise KeyError(name)
class Keys:
    def keys(self): raise ValueError("keys")
class Iter:
    def __iter__(self): raise ValueError("iter")
class Missing(dict):
    def __missing__(self, key): raise ValueError("missing")
class Hash:
    def __hash__(self): raise ValueError("hash")
class Next:
    def __iter__(self): return self
    def __next__(self): raise ValueError("next")
class Contains:
    def __getitem__(self, i): raise ValueError("getitem")
def gen():
    yield from Next()
def raiser(): raise ValueError("called")
ACTS = {
    "vars": lambda: vars(NoVars()),
    "getattr with a default": lambda: getattr(Lost(), "x", None),
    "hasattr": lambda: hasattr(Lost(), "x"),
    "dict from keys": lambda: dict(Keys()),
    "dict update": lambda: {}.update(Keys()),
    "a starred call": lambda: print(*Iter()),
    "a double-starred call": lambda: dict(**Keys()),
    "list": lambda: list(Iter()),
    "bytes": lambda: bytes(Iter()),
    "bytearray extend": lambda: bytearray().extend(Iter()),
    "bytes join": lambda: b"".join(Iter()),
    "str join": lambda: "".join(Iter()),
    "in": lambda: 1 in Contains(),
    "a set of a key": lambda: {Hash()},
    "a set in a set": lambda: {1} in {Hash()} if False else Hash() in {1},
    "__missing__": lambda: Missing()[1],
    "next with a default": lambda: next(Next(), None),
    "yield from": lambda: list(gen()),
    "percent": lambda: "%d" % (Lost(),),
    "format": lambda: "{0.x}".format(Lost()),
    "translate": lambda: "a".translate(Missing()),
    "unpacking": lambda: (lambda a, b: a)(*Next()),
    "iter with a sentinel": lambda: list(iter(raiser, None)),
    "sum": lambda: sum(Next()),
    "min": lambda: min(Next()),
    "sorted": lambda: sorted(Next()),
    "zip": lambda: list(zip(Next())),
    "map": lambda: list(map(str, Next())),
    "enumerate": lambda: list(enumerate(Next())),
    "an import": lambda: __import__("a_module_that_is_not_there"),
}
for label, act in ACTS.items():
    try:
        deep(40, act)
        print(label, "| no exception")
    except Exception as e:
        print(label, "|", type(e).__name__, entries(e) >= 41, entries(e))
'''),
    ('RL-646', 'operator.length_hint binds __len__ once, and an error of that binding is len\'s (RL-647: next of a weak proxy)', r'''
import operator, weakref
class Bind:
    def __init__(self, result, fails=None):
        self.result, self.fails = result, fails
    def __get__(self, obj, owner):
        print("   bound")
        if self.fails is not None: raise self.fails("binding")
        return lambda: self.result
def attempt(label, act):
    try: print(label, "->", repr(act()))
    except Exception as e: print(label, "->", type(e).__name__, e.args)
class Value:
    __len__ = Bind(2)
    def __length_hint__(self): return 9
class LenFails:
    __len__ = Bind(2, TypeError)
    def __length_hint__(self): return 9
class LenFailsOtherwise:
    __len__ = Bind(2, ValueError)
    def __length_hint__(self): return 9
class HintOnly:
    __length_hint__ = Bind(5)
class HintFails:
    __length_hint__ = Bind(5, TypeError)
class NoneLen:
    __len__ = None
    def __length_hint__(self): return 9
for kind in (Value, LenFails, LenFailsOtherwise, HintOnly, HintFails, NoneLen):
    attempt("length_hint of " + kind.__name__, lambda: operator.length_hint(kind(), 7))
class Stepped:
    __next__ = Bind(7)
class StepFails:
    __next__ = Bind(7, KeyError)
class Static:
    __next__ = staticmethod(lambda: 8)
class NoneNext:
    __next__ = None
class Plain: pass
late = Plain()
late.__next__ = lambda: 9
for label, target in (("a descriptor", Stepped()), ("a descriptor that fails", StepFails()), ("a staticmethod", Static()), ("None", NoneNext()), ("the object's own", late)):
    attempt("next of a proxy, __next__ " + label, lambda: next(weakref.proxy(target)))
'''),
    ('RL-648', 'a path whose __fspath__ cannot be bound, or is None, is no path (RL-649)', r'''
import _locale, io, os
class Bind:
    def __init__(self, fails): self.fails = fails
    def __get__(self, obj, owner): raise self.fails("binding")
class Stop(BaseException): pass
class BindFails: __fspath__ = Bind(KeyError)
class BindStops: __fspath__ = Bind(Stop)
class NoneOf: __fspath__ = None
class CallFails:
    def __fspath__(self): raise KeyError("calling")
class Wrong:
    def __fspath__(self): return 3
class Good:
    def __fspath__(self): return "/dev/null"
def opened(value):
    with open(value, "rb") as f: return f.read()
def raw(value):
    with io.FileIO(value) as f: return f.read()
APIS = {"os.fspath": os.fspath, "os.stat": lambda p: os.stat(p).st_size, "os.lstat": lambda p: os.lstat(p).st_size, "os.chdir": os.chdir,
        "os.listdir": os.listdir, "os.scandir": os.scandir, "os.open": lambda p: os.close(os.open(p, os.O_RDONLY)), "os.access": lambda p: os.access(p, os.F_OK),
        "os.readlink": os.readlink, "os.fsencode": os.fsencode, "os.fsdecode": os.fsdecode, "os.path.exists": os.path.exists,
        "open": opened, "io.FileIO": raw, "bindtextdomain": lambda p: _locale.bindtextdomain("bella-a30-example", p)}
for name, api in APIS.items():
    for kind in (BindFails, BindStops, NoneOf, CallFails, Wrong, Good):
        try: print(name, kind.__name__, "->", repr(api(kind())))
        except BaseException as e:
            print(name, kind.__name__, "->", type(e).__name__, e.args if isinstance(e, (TypeError, KeyError, Stop)) else type(e).__name__, type(e.__context__).__name__)
'''),
    ('RL-650', 'an OrderedDict\'s iterator is at its end after a key\'s hash failed', r'''
from collections import OrderedDict
calls, armed, target = 0, False, 0
class K:
    def __hash__(self):
        global calls
        if armed:
            calls += 1
            if calls == target: raise ValueError("hash")
        return 10
    def __del__(self): print("   the key is gone")
def run(view, way, failing):
    global calls, armed, target
    calls, armed, target = 0, False, failing
    d = OrderedDict()
    d[K()] = 'a'
    d[1] = 'b'
    it = way(getattr(d, view)())
    del d
    if way is reversed: print("  ", next(it) if view != "items" else next(it)[1])
    armed = True
    for _ in range(4):
        try:
            item = next(it)
            print("  ", item if view == "values" else (type(item).__name__ if view == "keys" else item[1]))
            del item
        except Exception as e: print("  ", type(e).__name__, type(e.__context__).__name__)
    armed = False
    print("   drop")
    del it
    print("   dropped")
for view in ("items", "values", "keys"):
    for way in (iter, reversed):
        for failing in (1, 2):
            print(view, way.__name__, "the hash call that fails:", failing)
            run(view, way, failing)
# the error goes on as it is: what it had as its context stays, whatever is handled around the call
class Chained:
    def __hash__(self):
        if armed:
            try: raise KeyError("inner")
            except KeyError: raise ValueError("hash")
        return 11
d = OrderedDict()
d[Chained()] = 'c'
it = iter(d.items())
armed = True
try:
    raise LookupError("around")
except LookupError:
    try: next(it)
    except ValueError as e: print("context:", type(e.__context__).__name__, type(e.__context__.__context__).__name__)
armed = False
del it, d
'''),
    ('RL-651', 'open and io.FileIO test their name\'s type, and a failed conversion to an int makes it a path', r'''
import io, warnings
def of_class(answer):
    class C:
        @property
        def __class__(self):
            print("   __class__ was read")
            if answer is None: raise ValueError("class")
            return answer
        def __fspath__(self): return "/dev/null"
    return C()
class Raises:
    def __index__(self): raise ValueError("index")
class RaisesWithPath(Raises):
    def __fspath__(self): return "/dev/null"
class Big:
    def __index__(self): return 2**40
    def __fspath__(self): return "/dev/null"
class Negative:
    def __index__(self): return -5
    def __fspath__(self): return "/dev/null"
class Stops:
    def __index__(self): raise KeyboardInterrupt
    def __fspath__(self): return "/dev/null"
class Sub(int): pass
class Complex(complex):
    def __fspath__(self): return "/dev/null"
class Floats:
    def __float__(self): return 1.0
    def __fspath__(self): return "/dev/null"
ROWS = (("__class__ says bool", of_class(bool)), ("__class__ says int", of_class(int)), ("__class__ raises", of_class(None)),
        ("2**40", 2**40), ("-1", -1), ("1.5", 1.5), ("__index__ raises", Raises()), ("__index__ raises, with a path", RaisesWithPath()),
        ("__index__ too big, with a path", Big()), ("__index__ negative, with a path", Negative()), ("__index__ interrupts, with a path", Stops()),
        ("an int's subclass", Sub(-3)), ("a complex's subclass with a path", Complex(1)), ("__float__ with a path", Floats()), ("None", None))
for label, value in ROWS:
    for opener in (io.FileIO, open):
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter("always")
            try:
                with opener(value) as f: print(opener.__name__, label, "-> opened", f.read(), [w.category.__name__ for w in seen])
            except BaseException as e:
                print(opener.__name__, label, "->", type(e).__name__, e.args, type(e.__context__).__name__, [w.category.__name__ for w in seen])
'''),
    ('RL-652', 'a fileno that is None is called, one that is not there is said to be missing', r'''
import os
class NoneOf: fileno = None
class Missing: pass
class Late: pass
late = Late()
late.fileno = lambda: -1
class Raises:
    @property
    def fileno(self): raise ValueError("fileno")
class Wrong:
    def fileno(self): return "1"
for name, api in (("os.fsync", os.fsync), ("os.fdatasync", os.fdatasync), ("os.fchdir", os.fchdir)):
    for label, value in (("None", NoneOf()), ("missing", Missing()), ("the object's own", late), ("a property that raises", Raises()), ("a str", Wrong())):
        try: print(name, label, "->", api(value))
        except Exception as e: print(name, label, "->", type(e).__name__, e.args)
'''),
    ('RL-654', 'RawIOBase.readall goes on when read was interrupted', r'''
import errno, io
class Shown(OSError):
    @property
    def errno(self): return errno.EINTR          # what the class shows; the C reads the field
class Index:
    def __index__(self): return errno.EINTR
def stream(make):
    class S(io.RawIOBase):
        calls = 0
        def read(self, size=-1):
            self.calls += 1
            if self.calls == 1: return b'a'
            if self.calls in (2, 3): raise make()
            if self.calls == 4: return b'b'
            return b''
    return S()
ROWS = {"InterruptedError(EINTR)": lambda: InterruptedError(errno.EINTR, "interrupted"), "OSError(EINTR)": lambda: OSError(errno.EINTR, "interrupted"),
        "InterruptedError(EINVAL)": lambda: InterruptedError(errno.EINVAL, "invalid"), "OSError()": lambda: OSError(),
        "OSError('text')": lambda: OSError("text"), "a subclass that shows EINTR": lambda: Shown(errno.EINVAL, "invalid"),
        "a subclass with EINTR": lambda: Shown(errno.EINTR, "interrupted"), "errno with __index__": lambda: OSError(Index(), "interrupted"),
        "errno True": lambda: OSError(True, "true"), "ValueError": lambda: ValueError("no OSError")}
for label, make in ROWS.items():
    s = stream(make)
    try: print(label, "->", s.readall(), s.calls)
    except Exception as e: print(label, "->", type(e).__name__, s.calls)
'''),
    ('RL-656', 'the other places where _io goes on after EINTR: readline, writelines, the buffered raw calls, TextIOWrapper', r'''
import errno
import io

ERRORS = {"EINTR": lambda: InterruptedError(errno.EINTR, "interrupted"), "EINVAL": lambda: OSError(errno.EINVAL, "invalid"),
          "ValueError": lambda: ValueError("no OSError")}


class Fails:
    """Raises on chosen calls of a method, counted over the stream's life."""

    def __init__(self, make, at):
        self.make, self.at, self.calls = make, at, 0

    def step(self):
        self.calls += 1
        if self.calls in self.at:
            raise self.make()


def attempt(label, act, *counters):
    try:
        print(label, "->", repr(act()), [c.calls for c in counters])
    except Exception as e:
        print(label, "->", type(e).__name__, [c.calls for c in counters])


for name, make in ERRORS.items():
    print(name)

    # 1 and 2: IOBase.readline, by peek and by read
    def peeked():
        peeks, reads = Fails(make, (2,)), Fails(make, ())
        class S(io.RawIOBase):
            data = b"ab\ncd\n"
            def peek(self, n=0):
                peeks.step()
                return self.data
            def read(self, n=-1):
                reads.step()
                out, self.data = self.data[:n], self.data[n:]
                return out
        s = S()
        attempt("  readline, peek interrupted", lambda: [s.readline(), s.readline(), s.readline()], peeks, reads)

    def read_interrupted():
        reads = Fails(make, (2, 3))
        class S(io.RawIOBase):
            data = b"ab\ncd\n"
            def read(self, n=-1):
                reads.step()
                out, self.data = self.data[:n], self.data[n:]
                return out
        s = S()
        attempt("  readline, read interrupted", lambda: [s.readline(), s.readline(), s.readline()], reads)
        attempt("  and readlines after it", s.readlines, reads)

    # 3: IOBase.writelines
    def lines_written():
        writes = Fails(make, (2, 3))
        got = []
        class S(io.RawIOBase):
            def write(self, b):
                writes.step()
                got.append(bytes(b))
                return len(b)
        s = S()
        attempt("  writelines", lambda: (s.writelines([b"a", b"b", b"c"]), got)[1], writes)

    # 4: the buffered reader's raw read
    def buffered_read():
        intos = Fails(make, (1, 3))
        class Raw(io.RawIOBase):
            data = b"abcdef"
            def readable(self): return True
            def readinto(self, b):
                intos.step()
                n = min(len(b), 2, len(self.data))
                b[:n] = self.data[:n]
                self.data = self.data[n:]
                return n
        r = io.BufferedReader(Raw(), 4)
        attempt("  BufferedReader.read(1)", lambda: r.read(1), intos)
        attempt("  BufferedReader.read()", r.read, intos)
        r2 = io.BufferedReader(Raw(), 4)
        intos.calls = 0
        attempt("  BufferedReader.read1", lambda: r2.read1(3), intos)
        attempt("  BufferedReader.peek", lambda: r2.peek(1)[:1], intos)
        attempt("  BufferedReader.readinto", lambda: (b := bytearray(8), r2.readinto(b), bytes(b))[1:], intos)
        attempt("  BufferedReader.readline", r2.readline, intos)

    # 5: the buffered writer's raw write
    def buffered_write():
        writes = Fails(make, (1, 3))
        got = []
        class Raw(io.RawIOBase):
            def writable(self): return True
            def write(self, b):
                writes.step()
                got.append(bytes(b[:2]))
                return min(len(b), 2)
        w = io.BufferedWriter(Raw(), 4)
        attempt("  BufferedWriter.write", lambda: w.write(b"abc"), writes)
        attempt("  BufferedWriter.flush", lambda: (w.flush(), list(got))[1], writes)
        attempt("  BufferedWriter.write past the buffer", lambda: (w.write(b"defghij"), list(got))[1], writes)
        attempt("  BufferedWriter.close", lambda: (w.close(), list(got))[1], writes)

    # 6: TextIOWrapper's write and flush
    def text_write():
        writes = Fails(make, (1, 3))
        got = []
        class Buffer(io.BufferedIOBase):
            def writable(self): return True
            def write(self, b):
                writes.step()
                got.append(bytes(b))
                return len(b)
        t = io.TextIOWrapper(Buffer(), encoding="ascii", write_through=True)
        attempt("  TextIOWrapper.write, write through", lambda: (t.write("ab"), list(got)), writes)
        t = io.TextIOWrapper(Buffer(), encoding="ascii", line_buffering=True)
        attempt("  TextIOWrapper.write, a line", lambda: (t.write("cd\n"), list(got)), writes)
        t = io.TextIOWrapper(Buffer(), encoding="ascii")
        t.write("ef")
        attempt("  TextIOWrapper.flush", lambda: (t.flush(), list(got))[1], writes)
        t.detach()

    # 7 and 8: TextIOWrapper's read and readline
    def text_read():
        reads = Fails(make, (1, 3))
        class Buffer(io.BufferedIOBase):
            data = b"ab\ncd\nef"
            def readable(self): return True
            def read1(self, n=-1):
                reads.step()
                out, self.data = self.data[:3], self.data[3:]
                return out
            def read(self, n=-1):
                reads.step()
                out, self.data = self.data, b""
                return out
        t = io.TextIOWrapper(Buffer(), encoding="ascii")
        attempt("  TextIOWrapper.read(2)", lambda: t.read(2), reads)
        attempt("  TextIOWrapper.readline", t.readline, reads)
        attempt("  TextIOWrapper.readline again", t.readline, reads)
        attempt("  TextIOWrapper.read()", t.read, reads)
        t = io.TextIOWrapper(Buffer(), encoding="ascii")
        reads.calls = 0
        attempt("  TextIOWrapper.read() at once", t.read, reads)
        t = io.TextIOWrapper(Buffer(), encoding="ascii")
        reads.calls = 0
        attempt("  a line of TextIOWrapper's iteration", lambda: next(t), reads)
        attempt("  TextIOWrapper.readlines", t.readlines, reads)

    for part in (peeked, read_interrupted, lines_written, buffered_read, buffered_write, text_write, text_read):
        part()
'''),
]

CATCH = re.compile(r"catch \((?:const )?PyError& (\w+)\) \{")
ANY_CATCH = re.compile(r"catch \([^)]*\) \{")


def _block_end(text: str, open_brace: int) -> int:
    depth, i, quote = 0, open_brace, ""
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\":
                i += 1
            elif c == quote:
                quote = ""
        elif c in "\"'":
            quote = c
        elif text.startswith("//", i):
            i = text.index("\n", i)
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("a block that does not end")


def bare_rethrows(text: str) -> list[int]:
    """The lines of a bare `throw;` in a catch block that names its PyError; a nested catch block's `throw;` is its own."""
    found = []
    for m in CATCH.finditer(text):
        start = m.end() - 1
        body = text[start:_block_end(text, start)]
        masked = list(body)
        for n in ANY_CATCH.finditer(body, 1):
            for k in range(n.start(), _block_end(body, n.end() - 1) + 1):
                masked[k] = " "
        for t in re.finditer(r"\bthrow;", "".join(masked)):
            found.append(text.count("\n", 0, start + t.start()) + 1)
    return found


def test_a_caught_exception_goes_on_through_rethrow() -> None:
    """RL-645: an exception caught as `const PyError& e` goes on by `rethrow(e)`, which says again that it is the one in
    flight. Between the catch and a bare `throw;` the runtime may have raised and caught another (an optional lookup), and
    that one takes the mark with it when it goes: the frames the first then leaves record nothing, and its traceback is
    short by all of them."""
    assert bare_rethrows("} catch (const PyError& e) {\n    work();\n    throw;\n}") == [3]
    assert bare_rethrows("} catch (const PyError& e) {\n    try { a(); } catch (...) { b(); throw; }\n    rethrow(e);\n}") == []
    bare = {str(p.relative_to(ROOT)): lines
            for p in sorted([*(ROOT / "runtime" / "src").glob("*.cpp"), *(ROOT / "runtime" / "include" / "bella").glob("*.hpp")])
            if (lines := bare_rethrows(p.read_text(encoding="utf-8")))}
    assert not bare, f"a bare `throw;` where the caught PyError has a name: use rethrow(name) {bare}"


def test_no_prelude_walks_a_types_mro_itself() -> None:
    """RL-644: `type(value).__mro__` and `vars(klass)` are attributes of a class, which its metaclass answers first. The
    walk is the runtime's (`_has_slot`, `_type_lookup`, `_lookup_special`); a prelude that CPython runs too keeps a stand-in
    under `except NameError`, read from `type`'s own descriptors."""
    allowed = {"iterating.py"}                   # its stand-in for CPython's run (runtime/tests/test_prelude.py)
    walks = {p.name: n for p in sorted((ROOT / "runtime" / "prelude").glob("*.py")) if p.name not in allowed
             if (n := len(re.findall(r"\)\.__mro__\b|\bcls\.__mro__\b", p.read_text(encoding="utf-8"))))}
    assert not walks, f"a walk of a type's MRO written in a prelude: {walks}"


def pytest_generate_tests(metafunc: Any) -> None:
    if "finding" in metafunc.fixturenames:
        metafunc.parametrize("finding", FINDINGS, ids=[f"{rl}-{name}" for rl, name, _ in FINDINGS])


def test_finding(finding: tuple[str, str, str]) -> None:
    same(finding[2])


if __name__ == "__main__":
    test_a_caught_exception_goes_on_through_rethrow()
    test_no_prelude_walks_a_types_mro_itself()
    for row in FINDINGS:
        same(row[2])
        print("ok", row[0])
