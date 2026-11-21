"""Review A32 of 2026-11-22 (range ad307d1..f8203de), compiled against CPython: a program for each finding fixed.

Codex's Astra at low effort read five items of review A25 and the fixes of review A31, and of those the other direction:
what CPython keeps, returns or hands on as the object it was given, where a prelude now works on a copy of the data. The
review log has its 24 findings as RL-699 to RL-722. Held here are the 17 fixed. The six that are the identity of an equal
immutable object (RL-699 to RL-701, RL-704, RL-719, RL-720) wait for the author with D-03's wording, so the programs here
print types and never `is` between an exact str or bytes and a result; RL-702 (a bytearray read where the C holds a view)
waits for the buffer step.

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_22_a32
"""
from __future__ import annotations

from typing import Any

from pipeline.tests.test_review_2026_11_19 import same

# a codec of the program's whose incremental decoder is `Dec`, under the name a32txt
CODEC = r'''
import codecs, io
def register(decoder, name="a32txt"):
    info = codecs.CodecInfo(None, None, incrementaldecoder=decoder, name=name)
    codecs.register(lambda n: info if n == name else None)
class Buf(io.BytesIO):
    def writable(self): return False
'''

FINDINGS: list[tuple[str, str, str]] = [
    ('RL-703', 'a struct sequence asks its dict of further fields once for each name', r'''
import os, time
class Key:
    def __init__(self, name, times=None): self.name, self.times, self.asked = name, times, 0
    def __hash__(self): return hash(self.name)
    def __eq__(self, other):
        self.asked += 1
        print("  eq", other)
        return other == self.name and (self.times is None or self.asked <= self.times)
print(time.struct_time(range(9), {Key("tm_zone"): 77}).tm_zone)
print(os.stat_result(range(10), {Key("st_blksize"): 78}).st_blksize)
print(os.statvfs_result(range(10), {Key("f_fsid"): 79}).f_fsid)
print(time.struct_time(range(9), {Key("tm_zone", 1): "a key that answers once"}).tm_zone)
try: time.struct_time(range(9), {"tm_zone": 1, "other": 2})
except TypeError: print("an unknown name: TypeError")
'''),
    ('RL-705', 'a report of an unraisable exception whose first line cannot be made has none', r'''
import sys, weakref
def hook(e): print("  hook:", type(e.exc_value).__name__, e.err_msg, e.object is None)
sys.unraisablehook = hook
class Shown:
    def __repr__(self):
        print("  repr asked")
        raise LookupError("repr")
class D(Shown):
    def __get__(self, obj, typ): return self
    def __call__(self): raise SystemExit(3)
class X: __del__ = D()
x = X()
del x
print("after a finaliser")
class Callback(Shown):
    def __call__(self, ref): raise ValueError("callback")
class W: pass
w = W()
r = weakref.ref(w, Callback())
del w
print("after a weak reference's callback")
class Delegate(Shown):
    def __iter__(self): return self
    def __next__(self): return 1
    def __getattr__(self, name): raise KeyError(name)
def g(): yield from Delegate()
it = g()
next(it)
it.close()
print("after a generator's close")
class Named:
    def __get__(self, obj, typ): return self
    def __call__(self): raise KeyError("named")
    def __repr__(self): return "a finaliser with a name"
class Y: __del__ = Named()
y = Y()
del y
print("and one whose repr works")
'''),
    ('RL-706', 're compiles an unhashable template again with nothing pending', r'''
import re
class S(str): __hash__ = None
class B(bytes): __hash__ = None
def chain(act):
    try: raise ValueError("the caller's")
    except ValueError:
        try: print("   ->", act())
        except BaseException as e:
            out = []
            while e is not None:
                out.append((type(e).__name__, type(e.__cause__).__name__, e.__suppress_context__))
                e = e.__context__
            print("  ", out)
bad_s, bad_b = "\\g<bad>", b"\\g<bad>"
for label, pattern, string, template in (("a str subclass", ".", "x", S(bad_s)), ("a bytes subclass", b".", b"x", B(bad_b)),
                                         ("a bytearray", b".", b"x", bytearray(bad_b))):
    p = re.compile(pattern)
    print(label)
    chain(lambda: p.sub(template, string))
    chain(lambda: p.subn(template, string))
    chain(lambda: p.match(string).expand(template))
p = re.compile("(a)")
print("and one that works:", p.sub(S("<\\1>"), "a"), re.compile(b"(a)").sub(bytearray(b"<\\1>"), b"a"))
'''),
    ('RL-707', 'json makes the note of a failed item with the error pending, not handled', r'''
import json, sys
class Key(str):
    def __repr__(self):
        print("   repr sees:", type(sys.exception()).__name__)
        return "key"
class BadRepr(str):
    def __repr__(self): raise ArithmeticError("repr")
def chain(act):
    try: raise LookupError("the caller's")
    except LookupError:
        try: act()
        except BaseException as e:
            notes = getattr(e, "__notes__", None)
            out = []
            while e is not None:
                out.append((type(e).__name__, type(e.__cause__).__name__, e.__suppress_context__))
                e = e.__context__
            print("  ", out, notes)
chain(lambda: json.dumps({Key("key"): object()}))
chain(lambda: json.dumps({1: object()}))
chain(lambda: json.dumps([1, object()]))
chain(lambda: json.dumps({"a": [{"b": object()}]}))
chain(lambda: json.dumps({BadRepr("k"): object()}))
def default(o): raise KeyError("default")
chain(lambda: json.dumps([object()], default=default))
'''),
    ('RL-708', 'codecs.encode and decode hand a codec plain strings for its options', r'''
import codecs
class S(str): pass
class B(bytes): pass
class Error(str): pass
class Name(str):
    def __radd__(self, other):
        print("   __radd__ was called")
        return "intercepted"
def fn(v, e=""):
    print("   the codec got:", type(v).__name__, type(e).__name__, e)
    return v, 1
def bad(v, e=""): raise LookupError("codec")
info = codecs.CodecInfo(fn, fn, name="a32_code")
failing = codecs.CodecInfo(bad, bad, name="a32_bad")
codecs.register(lambda s: info if s == "a32_code" else failing if s == "a32_bad" else None)
x, y = S("abc"), B(b"abc")
print(type(codecs.encode(x, "a32_code", Error("my errors"))).__name__, type(codecs.decode(y, Name("a32_code"), Error("mine"))).__name__)
for act in (lambda: codecs.encode(x, Name("a32_bad")), lambda: codecs.decode(y, Name("a32_bad")),
            lambda: codecs.encode(x, Name("a32_none")), lambda: codecs.decode(y, Name("a32_none")), lambda: codecs.lookup(Name("a32_none"))):
    try: act()
    except LookupError as e: print("LookupError", getattr(e, "__notes__", None))
'''),
    ('RL-709', 'the groupindex of a pattern without named groups is a new dict', r'''
import re
for pattern in ("x", b"x", "(x)"):
    p = re.compile(pattern)
    v = p.groupindex
    print(type(v).__name__, v is p.groupindex, v == {})
    v["extra"] = 7
    print(v, dict(p.groupindex))
p = re.compile("(?P<name>x)")
v = p.groupindex
print(type(v).__name__, dict(v))
try: v["extra"] = 7
except TypeError: print("a proxy: TypeError")
'''),
    ('RL-710', 'Match.groupdict walks the pattern\'s dict by position and inserts by the hash it stores (RL-711)', r'''
import _sre
CODE = [17, 0, 16, 120, 17, 1, 1]                # a capture around the literal x
def run(label, on_hash):
    state = {"active": False, "hashes": 0}
    class Key(str):
        def __hash__(self):
            if state["active"]:
                state["hashes"] += 1
                on_hash(state, d)
            return str.__hash__(self)
    key = Key("name")
    d = {key: 1}
    m = _sre.compile("x", 0, CODE, 1, d, (None, key)).match("x")
    state["active"] = True
    try: out = m.groupdict()
    except BaseException as e: out = type(e).__name__
    state["active"] = False
    print(label, "->", out, "| hashes:", state["hashes"])
run("plain", lambda state, d: None)
def grow(state, d):
    if state["hashes"] == 1: d["added"] = 1
run("a name added during the walk", grow)
def second_raises(state, d):
    if state["hashes"] == 2: raise LookupError("second hash")
run("a second hash would raise", second_raises)
def first_raises(state, d): raise LookupError("first hash")
run("the first hash raises", first_raises)
import re
m = re.compile("(?P<a>x)(?P<b>y)?").match("x")
print(m.groupdict(), m.groupdict("none"), list(m.groupdict()))
'''),
    ('RL-712', 'binascii reads a decoding alphabet from its own bytes, and keeps the alphabets a program gave in a cache of their own (RL-713)', r'''
import binascii
B64 = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
B32 = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
events = []
def kind(**methods):
    return type("Alphabet", (bytes,), methods)
def attempt(label, act):
    try: print(label, "->", act(), events)
    except BaseException as e: print(label, "->", type(e).__name__, events)
    events.clear()
for name, decode, alphabet, data in (("base64", binascii.a2b_base64, B64, b"YQ=="), ("base32", binascii.a2b_base32, B32, b"ME======")):
    Zero = kind(__len__=lambda self: 0)
    attempt(name + ", a length of 0", lambda: decode(data, alphabet=Zero(alphabet)))
    Other = kind(__getitem__=lambda self, k: bytes.__getitem__(self, bytes.__len__(self) - 1 - k))
    attempt(name + ", an item of its own", lambda: decode(data, alphabet=Other(alphabet[::-1])) == decode(data, alphabet=alphabet[::-1]))
    Raises = kind(__getitem__=lambda self, k: (_ for _ in ()).throw(LookupError()))
    attempt(name + ", an item that raises", lambda: decode(data, alphabet=Raises(alphabet[::-1])) == decode(data, alphabet=alphabet[::-1]))
    def hashed(self):
        events.append("hash")
        return bytes.__hash__(self)
    Hashed = kind(__hash__=hashed)
    a = Hashed(alphabet)
    attempt(name + ", the standard alphabet as an object of the program's: first", lambda: decode(data, alphabet=a))
    attempt(name + ", and again", lambda: decode(data, alphabet=a))
    count = [0]
    def second(self):
        count[0] += 1
        if count[0] == 2: raise ArithmeticError("second hash")
        return bytes.__hash__(self)
    Second = kind(__hash__=second)
    attempt(name + ", a hash that raises the second time", lambda: decode(data, alphabet=Second(alphabet[1:] + alphabet[:1])))
    Gone = kind(__del__=lambda self: events.append("released"))
    g = Gone(bytes(reversed(alphabet)))
    decode(data, alphabet=g)
    del g
    attempt(name + ", the alphabet let go by the program is held by the cache", lambda: "end")
    attempt(name + ", a wrong length", lambda: decode(data, alphabet=alphabet[:-1]))
    attempt(name + ", a str", lambda: decode(data, alphabet="x" * len(alphabet)))
'''),
    ('RL-714', 'IncrementalNewlineDecoder gives back the object it was given where it changes nothing', r'''
import io
class S(str): pass
for translate in (0, 1):
    for final in (0, 1):
        for text in ("xy", "x\ny", "x\ry", "x\r\ny", "", "xy\r", "\r", "\n"):
            d = io.IncrementalNewlineDecoder(None, translate)
            x = S(text)
            y = d.decode(x, final)
            z = d.decode(S("z"), final)
            print(translate, final, repr(text), "|", type(y).__name__, y is x, repr(str(y)), "|", type(z).__name__, repr(str(z)), "|", repr(d.newlines))
d = io.IncrementalNewlineDecoder(None, 1)
d.decode("a\r\nb")
x = S("plain")
y = d.decode(x)
print("after a CRLF was seen, translating:", type(y).__name__, y is x)
d = io.IncrementalNewlineDecoder(None, 0)
d.decode("a\r\nb")
y = d.decode(x)
print("after a CRLF was seen, not translating:", type(y).__name__, y is x)
'''),
    ('RL-715', 'a tm_zone that cannot be encoded is refused', r'''
import time
class S(str): pass
for zone in (S(chr(0xdcff)), chr(0xdcff), S("zone"), "UTC"):
    x = time.struct_time((2024, 1, 3, 0, 0, 0, 2, 3, -1), {"tm_zone": zone})
    for name, act in (("asctime", time.asctime), ("mktime", lambda v: type(time.mktime(v)).__name__), ("strftime", lambda v: time.strftime("%Y", v))):
        try: print(name, ascii(zone), "->", act(x))
        except BaseException as e: print(name, ascii(zone), "->", type(e).__name__)
'''),
    ('RL-716', 'TextIOWrapper hands its decoder the chunk it read, and reads decoded text by its characters (RL-717, RL-718, RL-721)', CODEC + r'''
class B(bytes): pass
class S(str):
    def __getitem__(self, i):
        print("   __getitem__ of the decoded text was called")
        return "override"
    def __radd__(self, other):
        print("   __radd__ of the decoded text was called")
        return "changed"
    def find(self, *a):
        print("   find of the decoded text was called")
        return -1
b = B(b"abc\ndef")
class Chunk(Buf):
    def read1(self, n=-1): return b if super().read1(n) else b""
    def read(self, n=-1): return b if super().read(n) else b""
class Dec(codecs.IncrementalDecoder):
    def decode(self, chunk, final=False):
        print("   the decoder got:", type(chunk).__name__, chunk is b if chunk else "empty")
        return S(bytes(chunk).decode("ascii")) if chunk else ""
register(Dec)
for label, act in (("read(2)", lambda f: f.read(2)), ("read(2) twice", lambda f: f.read(2) + f.read(2)), ("readline", lambda f: f.readline()),
                   ("two lines", lambda f: f.readline() + f.readline()), ("read()", lambda f: f.read()), ("read(1) then read()", lambda f: f.read(1) + f.read()),
                   ("iteration", lambda f: "|".join(f))):
    for newline in ("\n", None, ""):
        f = io.TextIOWrapper(Chunk(b), encoding="a32txt", newline=newline)
        y = act(f)
        print(label, repr(newline), "->", type(y).__name__, repr(str.__str__(y)))
# what read() of the buffer gave goes to the decoder as it is
class Any(codecs.IncrementalDecoder):
    def decode(self, chunk, final=False):
        print("   the decoder got a", type(chunk).__name__)
        return "done"
register(Any, "a32any")
for given in (bytearray(b"hello"), [1, 2], "text", 5):
    class Gives(Buf):
        def read(self, *args): return given
    try: print(io.TextIOWrapper(Gives(), encoding="a32any", newline="\n").read())
    except BaseException as e: print(type(e).__name__)
class GivesArray(Buf):
    def read(self, *args): return bytearray(b"hello")
print(io.TextIOWrapper(GivesArray(), encoding="ascii", newline="\n").read())
class GivesNone(Buf):
    def read(self, *args): return None
try: io.TextIOWrapper(GivesNone(), encoding="ascii").read()
except BaseException as e: print(type(e).__name__)
'''),
    ('RL-722', 'each buffered type has the methods CPython gives it', CODEC + r'''
import io
def answers(label, make):
    out = []
    for name in ("readable", "writable", "seekable"):
        try: out.append(getattr(make(), name)())
        except BaseException as e: out.append(type(e).__name__)
    for name, act in (("next", lambda s: next(s)), ("iter", lambda s: type(iter(s)).__name__), ("read", lambda s: s.read()), ("write", lambda s: s.write(b"x")),
                      ("readline", lambda s: s.readline()), ("peek", lambda s: s.peek()), ("read1", lambda s: s.read1()), ("readinto", lambda s: s.readinto(bytearray(1)))):
        try: out.append((name, act(make())))
        except BaseException as e: out.append((name, type(e).__name__))
    print(label, out)
answers("BufferedReader", lambda: io.BufferedReader(io.BytesIO(b"ab\n")))
answers("BufferedWriter", lambda: io.BufferedWriter(io.BytesIO(b"ab\n")))
answers("BufferedRandom", lambda: io.BufferedRandom(io.BytesIO(b"ab\n")))
answers("BufferedRWPair", lambda: io.BufferedRWPair(io.BytesIO(b"ab\n"), io.BytesIO()))
for kind in (io.BufferedReader, io.BufferedWriter, io.BufferedRandom):
    print(kind.__name__, [n for n in ("readable", "writable", "__next__", "read", "write", "peek", "readline", "truncate", "flush") if n in vars(kind)])
class Dec(codecs.IncrementalDecoder):
    def decode(self, v, final=False): return bytes(v).decode("ascii")
register(Dec)
f = io.TextIOWrapper(io.BufferedReader(io.BytesIO(b"abc")), encoding="a32txt", newline="\n")
print("a text stream over a reader, with a codec that only decodes:", f.read(2), f.readline(), f.writable(), f.readable())
'''),
]


def pytest_generate_tests(metafunc: Any) -> None:
    if "finding" in metafunc.fixturenames:
        metafunc.parametrize("finding", FINDINGS, ids=[f"{rl}-{name}" for rl, name, _ in FINDINGS])


def test_finding(finding: tuple[str, str, str]) -> None:
    same(finding[2])


if __name__ == "__main__":
    for row in FINDINGS:
        same(row[2])
        print("ok", row[0])
