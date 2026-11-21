"""Review A33 of 2026-11-22 (range f8203de..6bd852a), compiled against CPython: a program for each finding fixed.

Codex's Astra at low effort read the fixes of review A32, the names of __slots__ sorted as objects and the list of names a
type has beyond CPython's. The review log has its 27 findings as RL-723 to RL-749. Most are of three kinds: what the C does
with an error that is pending, not handled (a report or a note made after the handler has ended: RL-725, RL-728, RL-742,
RL-747); a C integer where a prelude kept the object or a Python int (RL-723, RL-736, RL-737, RL-741); and what a type has
or lacks beside CPython's (RL-726, RL-731, RL-732, RL-734, RL-735, RL-743 to RL-745). itertools._tee_dataobject keeps its
__del__ (the other half of RL-731): it waits for a deallocator a prelude can name without one. RL-750 to RL-752 are what the
reviewer's saved outputs showed and its report did not name (the rows compared pairwise); RL-753, the class behind RL-748,
has its own module (test_repr_text.py).

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_22_a33
"""
from __future__ import annotations

from typing import Any

from pipeline.tests.test_review_2026_11_19 import same

# a codec of the program's whose incremental decoder is `Dec`, and a text stream over b"abc" with it
CODEC = r'''
import codecs, io, sys
def stream(decoder, name):
    info = codecs.CodecInfo(None, None, incrementaldecoder=decoder, name=name)
    codecs.register(lambda n: info if n == name else None)
    class Buf(io.BytesIO):
        def writable(self): return False
    return io.TextIOWrapper(Buf(b"abc"), encoding=name, newline="\n")
'''

FINDINGS: list[tuple[str, str, str]] = [
    ('RL-723', "the newline decoder's flag is shifted within 64 bits", r'''
import io
class Decoder:
    def __init__(self, flag): self.flag = flag
    def getstate(self): return b"x", self.flag
    def decode(self, data, final=False): return data
for flag in (-1, 2**63, 2**64 - 1, 5, 0):
    for translate in (True, False):
        d = io.IncrementalNewlineDecoder(Decoder(flag), translate)
        print(flag, d.getstate())
d = io.IncrementalNewlineDecoder(Decoder(-1), True)
d.decode("a\r")
print("a pending carriage return:", d.getstate())
'''),
    ('RL-724', "the newline decoder's reset and setstate return what the decoder's returned", r'''
import io
class Decoder:
    def reset(self): return "reset"
    def setstate(self, state):
        print("  given", state)
        return ["set"]
d = io.IncrementalNewlineDecoder(Decoder(), True)
print(d.reset())
print(d.setstate((b"x", 5)))
print(io.IncrementalNewlineDecoder(None, True).reset(), io.IncrementalNewlineDecoder(None, True).setstate((b"", 1)))
'''),
    ('RL-725', "a note that cannot be added has the first error as its context", r'''
import json, sys
class E(Exception): pass
def default(o):
    print("  default, handled:", type(sys.exception()).__name__)
    e = E()
    e.__notes__ = 42
    raise e
for arguments in ({}, {"indent": 2}, {"skipkeys": True}):
    try: raise LookupError
    except LookupError:
        try: json.dumps([{"q": [object()]}], default=default, **arguments)
        except BaseException as e:
            print(type(e).__name__, getattr(e, "__notes__", None), type(e.__context__).__name__, type(e.__cause__).__name__,
                  type(e.__context__.__context__).__name__)
'''),
    ('RL-726', "the io types whose allocator is object's check their arguments as it does", r'''
import io
def arguments(kind):
    if kind is io.BufferedRWPair: return (io.BytesIO(), io.BytesIO())
    if kind is io.IncrementalNewlineDecoder: return (None, True)
    return (io.BytesIO(),)
for kind in (io.BufferedReader, io.BufferedWriter, io.BufferedRandom, io.BufferedRWPair, io.IncrementalNewlineDecoder, io.TextIOWrapper):
    class New(kind):
        def __new__(cls, *args):
            return super().__new__(cls, *args)
    class Bare(kind):
        def __new__(cls, *args):
            return super().__new__(cls)
    class Init(kind):
        def __init__(self, *args):
            super().__init__(*args)
    for sub in (New, Bare, Init):
        try: print(kind.__name__, sub.__name__, type(sub(*arguments(kind))).__name__)
        except TypeError: print(kind.__name__, sub.__name__, "TypeError")
    x = kind(*arguments(kind))
    print(kind.__name__, "through an instance:", type(x.__new__(type(x))).__name__)
    class NoInit(kind):
        __init__ = object.__init__
    for given in (arguments(kind), ()):
        try: print(kind.__name__, "with object's __init__:", type(NoInit(*given)).__name__)
        except TypeError: print(kind.__name__, "with object's __init__: TypeError")
'''),
    ('RL-727', "a buffered stream wants True itself from readable() and writable()", r'''
import io
class I(int): pass
answer = None
class Raw(io.BytesIO):
    def readable(self): return answer
    def writable(self): return answer
    def seekable(self): return True
for answer in (I(1), 1.0, -1, 2**70, "yes", True, False, None, 0):
    for kind, streams in ((io.BufferedReader, 1), (io.BufferedWriter, 1), (io.BufferedRandom, 1), (io.BufferedRWPair, 2)):
        try:
            kind(*[Raw(b"abcd") for _ in range(streams)])
            print(type(answer).__name__, kind.__name__, "made")
        except io.UnsupportedOperation:
            print(type(answer).__name__, kind.__name__, "UnsupportedOperation")
    answer = True                                # for the finalisers of the streams made
'''),
    ('RL-728', "a finaliser's and an atexit callback's report is made after the handler has ended", r'''
import atexit, io, os, sys, warnings
def log(tag): print("  ", tag, "sees", type(sys.exception()).__name__)
def hook(e):
    log("hook")
    print("  ", e.exc_type.__name__, e.err_msg, e.object is None)
sys.unraisablehook = hook
class F(io.BytesIO):
    def close(self):
        log("close")
        raise ValueError("file close")
    def __repr__(self):
        log("repr")
        return "file"
f = F()
del f
try: raise LookupError
except LookupError:
    f = F()
    del f
class Released:
    def __del__(self): log("released")
class Bad(io.BytesIO):
    def close(self): raise ValueError("file close")
    def __repr__(self):
        holder.clear()
        raise KeyError("no repr")
holder = [Released()]
b = Bad()
del b
print("a file that is finalised open, the warning an error:")
warnings.simplefilter("error", ResourceWarning)
class G(io.FileIO):
    def __repr__(self):
        log("repr")
        return "G"
g = G(os.devnull)
del g
warnings.simplefilter("ignore", ResourceWarning)
class C:
    def __call__(self):
        log("call")
        raise ValueError("callback")
    def __repr__(self):
        log("repr")
        return "C"
atexit.register(C())
print("end")
'''),
    ('RL-729', 'two slot names with the same text are compared', r'''
events = []
class S(str):
    def __lt__(self, other):
        events.append("lt")
        return False
names = [S("a"), S("a")]
class C: __slots__ = names
print(C.__slots__ is names, [k for k in vars(C) if k == "a"], events)
class R(str):
    def __lt__(self, other): raise LookupError
try:
    class D: __slots__ = [R("a"), R("a")]
    print("made")
except LookupError: print("LookupError")
events.clear()
class T: __slots__ = (S("b"), S("a"), S("b"), "c")
print(events, [k for k in vars(T) if k in "abc"])
t = T()
t.a, t.b, t.c = 1, 2, 3
print(t.a, t.b, t.c)
'''),
    ('RL-730', "a sys.stderr that cannot be written ends the report at the first write that fails", r'''
import sys
class Err:
    def __init__(self, good): self.good = good
    def write(self, s):
        print("  write", repr(s) if "File " not in s else "a frame's line")
        if self.good <= 0: raise KeyError("err")
        self.good -= 1
    def flush(self): print("  flush")
class D:
    def __repr__(self): return "del"
    def __call__(self): raise ValueError("broken")
class X: __del__ = D()
old = sys.stderr
for good in (0, 1, 2):
    sys.stderr = Err(good)
    x = X()
    del x
    sys.stderr = old
    print("ok", good)
class Shown:
    def __repr__(self): return "shown"
print("an object in the report:")
kinds = []
sys.unraisablehook = lambda e: kinds.append(type(e))
x = X()
del x
sys.unraisablehook = sys.__unraisablehook__
for message in ("said", None):
    for good in (0, 1, 2, 3, 4, 5, 6, 7):
        sys.stderr = Err(good)
        try:
            sys.__unraisablehook__(kinds[0]((ValueError, ValueError("v"), None, message, Shown())))
            sys.stderr = old
            print("  returned")
        except BaseException as e:
            sys.stderr = old
            print("  raised", type(e).__name__)
'''),
    ('RL-731', "zlib's objects have no __del__", r'''
import zlib
for made in (zlib._ZlibDecompressor(), zlib.compressobj(), zlib.decompressobj(), zlib.compressobj().copy(), zlib.decompressobj().copy()):
    print(type(made).__name__, hasattr(made, "__del__"), "__del__" in vars(type(made)))
c = zlib.compressobj()
data = c.compress(b"abc" * 100) + c.flush()
d = zlib.decompressobj()
print(d.decompress(data) == b"abc" * 100, zlib._ZlibDecompressor().decompress(data) == b"abc" * 100)
'''),
    ('RL-732', 'no class derives from the type of typing.NoDefault, and it shows nothing of a class statement', r'''
import typing
try:
    class T(type(typing.NoDefault)): pass
    print("made")
except TypeError: print("TypeError")
kind = type(typing.NoDefault)
for name in ("__firstlineno__", "__static_attributes__", "__slots__", "__module__", "__dict__", "__weakref__"):
    print(name, getattr(typing.NoDefault, name, "absent"), name in vars(kind))
print(kind.__module__, kind.__name__, kind.__qualname__, repr(typing.NoDefault), kind() is typing.NoDefault, typing.NoDefault.__reduce__())
try: kind(1)
except TypeError: print("TypeError")
'''),
    ('RL-733', "a slot name's own __hash__ is asked when the class's variables are checked", r'''
class S(str):
    def __hash__(self):
        print("  hash")
        raise ArithmeticError
try:
    class X: __slots__ = [S("a")]
    print("made")
except ArithmeticError: print("ArithmeticError")
class H(str):
    def __hash__(self):
        print("  hash asked")
        return str.__hash__(self)
    def __eq__(self, other):
        print("  eq asked")
        return str.__eq__(self, other)
class Y: __slots__ = [H("a"), "b"]
print(sorted(k for k in vars(Y) if k in "ab"))
try:
    class Z:
        a = 1
        __slots__ = [H("a")]
    print("made")
except ValueError: print("ValueError")
class Q: __slots__ = [H("__qualname__")]
print("made", "__qualname__" in vars(Q))
'''),
    ('RL-734', 'ast.AST has no __annotate_func__', r'''
import ast
print(hasattr(ast.AST, "__annotate_func__"), "__annotate_func__" in vars(ast.AST), "__annotations__" in vars(ast.AST), ast.AST._fields,
      ast.AST._attributes, ast.AST.__match_args__)
print(ast.Name("x")._fields, ast.Assign._attributes, repr(ast.Name("x")), repr(ast.Constant([1, "a"])))
'''),
    ('RL-736', "a text stream's position with a decoder flag that is negative", CODEC + r'''
class Dec(codecs.IncrementalDecoder):
    def getstate(self): return b"", -1
    def setstate(self, state): print("  set", type(state[1]).__name__, state[1])
    def decode(self, data, final=False): return bytes(data).decode()
f = stream(Dec, "a33neg")
print(f.read(1))
p = f.tell()
print("tell", p)
print("seek", f.seek(p), f.read())
for cookie in (((1 << 32) - 1) << 64, 1 << 95, (1 << 64) - 1, 1 << 63, 3 | (5 << 64), 1 << 167, 1 << 168, 1 << 200):
    try: print("seek", f.seek(cookie))
    except Exception as e: print("seek", type(e).__name__)
'''),
    ('RL-737', "a text stream's tell makes a C int of the decoder's flag", CODEC + r'''
class I(int):
    def __eq__(self, other):
        print("  eq")
        return False
    def __lshift__(self, other):
        print("  shift")
        return 4
    def __index__(self):
        print("  index of an int")
        return 9
    __hash__ = int.__hash__
class Index:
    def __index__(self):
        print("  index")
        return 3
flag = 0
class Dec(codecs.IncrementalDecoder):
    def getstate(self): return b"", flag
    def setstate(self, state): print("  set", type(state[1]).__name__, state[1] if type(state[1]) in (int, I, bool) else "")
    def decode(self, data, final=False): return bytes(data).decode()
number = 0
for flag in (I(2), Index(), 2**32, -(2**31) - 1, 2**31 - 1, 1.5, None, "1", True):
    number += 1
    f = stream(Dec, "a33flag" + str(number))
    try:
        f.read(1)
        p = f.tell()
        print("tell", p)
        print("seek", f.seek(p), f.read())
    except Exception as e: print(type(e).__name__)
'''),
    ('RL-738', "the capability checks return the checked result", r'''
import io
v = io.BytesIO()
print(v._checkReadable(), v._checkWritable(), v._checkSeekable(), v._checkClosed())
class No(io.BytesIO):
    def readable(self): return 1
for check in (No()._checkReadable, io.IOBase()._checkSeekable):
    try: print(check())
    except io.UnsupportedOperation: print("UnsupportedOperation")
'''),
    ('RL-739', "__reduce_ex__(2) of a C type whose struct holds state is refused", r'''
import collections, csv, functools, hashlib, io, itertools, json, operator, re, struct, zlib
made = [struct.Struct("b"), itertools.chain([1]), itertools.count(), itertools.repeat(1), itertools.accumulate([1]), itertools.batched([1], 1),
        itertools.combinations([1], 1), itertools.cycle([1]), itertools.islice([1], 1), itertools.pairwise([1]), itertools.product([1]),
        itertools.groupby([1]), itertools.tee([1])[0], itertools.zip_longest([1]), itertools.starmap(len, []), itertools.takewhile(len, []),
        hashlib.blake2b(), hashlib.blake2s(),
        json.JSONEncoder().iterencode, io.IncrementalNewlineDecoder(None, True), io.BufferedRWPair(io.BytesIO(), io.BytesIO()),
        struct.iter_unpack("b", b"a"), csv.reader([]), csv.writer(io.StringIO()), zlib.compressobj(), zlib.decompressobj(),
        functools.cmp_to_key(lambda a, b: 0)(1), re.compile("a").scanner("a"), object(), collections.OrderedDict(), operator.itemgetter(1),
        functools.partial(len), collections.deque([1]), io.BytesIO(b"a"), io.StringIO("a")]
for value in made:
    for protocol in (2, 0):
        try:
            got = value.__reduce_ex__(protocol)
            print(type(value).__name__, protocol, type(got).__name__, len(got))
        except Exception as e:
            print(type(value).__name__, protocol, type(e).__name__)
class Sub(itertools.chain): pass
class Slotted(itertools.chain): __slots__ = ("a",)
for value in (Sub([1]), Slotted([1])):
    try: print(type(value).__name__, value.__reduce_ex__(2)[2:])
    except Exception as e: print(type(value).__name__, type(e).__name__)
'''),
    ('RL-740', "TextIOBase's read, readline and write convert their argument before they refuse", r'''
import io
t = io.TextIOBase()
for name in ("read", "readline", "write"):
    for argument in (1.5, None, 2**70, b"x", "x", 3, "a\0b", "\udc80", True):
        try: print(name, type(argument).__name__, getattr(t, name)(argument))
        except Exception as e: print(name, type(argument).__name__, type(e).__name__)
for name in ("read", "readline", "write"):
    try: print(getattr(t, name)())
    except Exception as e: print(name, "no argument", type(e).__name__)
try: t.writelines(["a", b"b"])
except Exception as e: print("writelines", type(e).__name__)
'''),
    ('RL-741', "the newline decoder's flag is any index, and one past 64 bits warns", r'''
import io, warnings
class I:
    def __index__(self):
        print("  index")
        return 3
class D:
    def __init__(self, flag): self.flag = flag
    def getstate(self): return b"", self.flag
    def setstate(self, state): print("  state", state)
for flag in (I(), 2**65, -(2**65), 2**64, 2**64 - 1, -(2**63), -(2**63) - 1, 1.5, None, True):
    d = io.IncrementalNewlineDecoder(D(flag), True)
    for name in ("get", "set"):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try: print(name, d.getstate() if name == "get" else d.setstate((b"", flag)))
            except Exception as e: print(name, type(e).__name__)
            print("  warned:", [w.category.__name__ for w in caught])
'''),
    ('RL-742', "a decoder given its state back after a failed tell sees no error as handled", CODEC + r'''
restore = None
class Dec(codecs.IncrementalDecoder):
    def decode(self, data, final=False):
        if bytes(data) == b"a": raise KeyError("decode")
        return bytes(data).decode()
    def getstate(self): return b"", 0
    def setstate(self, state):
        print("  restore sees", type(sys.exception()).__name__)
        if restore is not None: raise restore
number = 0
for restore in (None, ValueError("restore")):
    number += 1
    class First(Dec):
        seen = 0
        def decode(self, data, final=False):
            First.seen += 1
            return bytes(data).decode() if First.seen == 1 else Dec.decode(self, data, final)
    f = stream(First, "a33restore" + str(number))
    f.read(1)
    try: raise OSError
    except OSError:
        try: f.tell()
        except BaseException as e:
            print(type(e).__name__, type(e.__context__).__name__, type(e.__context__.__context__).__name__ if e.__context__ is not None else None)
'''),
    ('RL-743', "types.GenericAlias has object's __reduce_ex__", r'''
import copy
class Index:
    def __init__(self, fail): self.fail = fail
    def __index__(self):
        print("  index")
        if self.fail: raise LookupError
        return 2
for protocol in (1.5, 2**60, Index(False), Index(True), 2, 0, None, "2"):
    try: print(list[int].__reduce_ex__(protocol))
    except Exception as e: print(type(e).__name__)
print("__reduce_ex__" in vars(type(list[int])), copy.copy(list[int]), copy.deepcopy(dict[str, int]), copy.copy(list[int]) == list[int])
try: list[int].__reduce_ex__()
except TypeError: print("TypeError")
'''),
    ('RL-744', "types.LazyImportType has object's __new__", r'''
import types
class Ordinary: pass
for cls in (object, Ordinary, types.LazyImportType, int):
    try: print(type(types.LazyImportType.__new__(cls)).__name__)
    except TypeError: print("TypeError")
try: types.LazyImportType()
except TypeError: print("TypeError")
print("__new__" in vars(types.LazyImportType), types.LazyImportType.__new__ is object.__new__)
'''),
    ('RL-745', "BufferedRWPair has object's __getstate__", r'''
import copy, io
class Sub(io.BufferedRWPair): pass
for kind in (io.BufferedRWPair, Sub):
    x = kind(io.BytesIO(), io.BytesIO())
    print(kind.__name__, x.__getstate__())
    x.label = "a33"
    print(kind.__name__, x.__getstate__(), "__getstate__" in vars(io.BufferedRWPair))
    function, arguments = x.__reduce__()[:2]
    print(function.__name__, [getattr(a, "__name__", a) for a in arguments])
    for protocol in (2, 3):
        try: x.__reduce_ex__(protocol)
        except TypeError: print("TypeError")
    try: copy.copy(x)
    except TypeError: print("TypeError")
'''),
    ('RL-746', "__reduce_ex__(2) of a type that cannot be instantiated is refused", r'''
import csv, functools, io, re, struct, zlib
class Kept:
    def __getstate__(self):
        print("  state asked")
        return None
made = [csv.reader([]), csv.writer(io.StringIO()), zlib.compressobj(), zlib.decompressobj(), functools.cmp_to_key(lambda a, b: 0)(1),
        re.compile("a").scanner("a"), struct.iter_unpack("b", b"a"), iter([]), iter(()), {}.keys(), reversed([]), (x for x in ()), len]
for value in made:
    for protocol in (2, 3, 4):
        try: print(type(value).__name__, protocol, type(value.__reduce_ex__(protocol)).__name__)
        except Exception as e: print(type(value).__name__, protocol, type(e).__name__)
'''),
    ('RL-747', "a codec's failure gets its note with the error pending, not handled", r'''
import codecs, sys
notes = []
class S(str): pass
class E(Exception):
    @property
    def __notes__(self):
        print("  notes read, handled:", type(sys.exception()).__name__)
        return notes
class Refuses(Exception):
    @property
    def __notes__(self): return 42
def fn(value, errors="strict"):
    print("  codec, handled:", type(sys.exception()).__name__)
    raise kind()
codecs.register(lambda n: codecs.CodecInfo(fn, fn, name=n) if n == "notes33" else None)
for kind in (E, Refuses, KeyError):
    for call in (codecs.encode, codecs.decode):
        try: raise LookupError
        except LookupError:
            try: call(S("x") if call is codecs.encode else b"x", S("notes33"), S("abc"))
            except Exception as e:
                print(type(e).__name__, type(e.__context__).__name__, type(e.__context__.__context__).__name__ if e.__context__ else None,
                      notes if kind is E else getattr(e, "__notes__", None))
    notes.clear()
kind = E
try: "x".encode("notes33")
except E as e: print(type(e).__name__, e.__context__, notes)
'''),
    ('RL-748', "a report's or a note's text has the characters of what __repr__ returned", r'''
import atexit, io, json, os, sys, warnings
class Repr(str):
    def __radd__(self, left):
        print("  radd")
        return "wrong report"
    def __add__(self, right):
        print("  add")
        return "wrong report"
class Key(str):
    def __repr__(self): return Repr("key")
try: json.dumps({Key("k"): object()})
except Exception as e: print(type(e).__name__, e.__notes__, [type(n).__name__ for n in e.__notes__])
def hook(e): print("  hook:", e.exc_type.__name__, e.err_msg, type(e.err_msg).__name__, e.object is None)
sys.unraisablehook = hook
class F(io.BytesIO):
    def close(self): raise ValueError("close")
    def __repr__(self): return Repr("shown")
f = F()
del f
warnings.simplefilter("error", ResourceWarning)
class G(io.FileIO):
    def __repr__(self): return Repr("G")
g = G(os.devnull)
del g
warnings.simplefilter("ignore", ResourceWarning)
class C:
    def __call__(self): raise ValueError("callback")
    def __repr__(self): return Repr("shown")
atexit.register(C())
print("end")
'''),
    ('RL-749', "a bound method over a callable without a name is shown with a question mark", r'''
import sys, types
class Call:
    def __call__(self, *a): raise ValueError("field")
class Named:
    def __init__(self, **names): self.__dict__.update(names)
    def __call__(self, *a): return None
class X: __del__ = classmethod(Call())
def hook(e): print("  hook:", e.exc_type.__name__, e.exc_value, e.exc_traceback is None, e.err_msg, e.object is None)
sys.unraisablehook = hook
x = X()
del x
class S(str):
    def __str__(self): return "a str of its own"
for callable_ in (Call(), Named(__name__="named"), Named(__name__="named", __qualname__="Q.named"), Named(__qualname__=7, __name__="n"),
                  Named(__name__=8), Named(__qualname__=S("subclass")), len, print):
    print(repr(types.MethodType(callable_, 1)))
class Raises:
    def __getattr__(self, name): raise LookupError(name)
    def __call__(self): return None
try: repr(types.MethodType(Raises(), 1))
except LookupError: print("LookupError")
'''),
    ('RL-750', "BufferedRandom asks its raw stream whether it seeks, first", r'''
import io
class I(int): pass
answer = True
class R(io.BytesIO):
    def readable(self):
        print("  readable")
        return True
    def writable(self):
        print("  writable")
        return True
    def seekable(self):
        print("  seekable")
        return answer
for answer in (True, False, None, 1, I(1), 2**80):
    try:
        io.BufferedRandom(R())
        print("made")
    except io.UnsupportedOperation: print("UnsupportedOperation")
    answer = True
'''),
    ('RL-751', "a BlockingIOError of a buffered write has the errno the raw stream's write left", r'''
import errno, io, os
class R(io.BytesIO):
    def write(self, data): return None
for kind in (io.BufferedWriter, io.BufferedRandom):
    raw = R()
    x = kind(raw, 2)
    for op in ("write", "flush", "write", "big write"):
        try:
            if op == "flush": x.flush()
            else: x.write(b"abc" if op == "write" else b"abcdefgh")
        except BlockingIOError as e: print(kind.__name__, op, e.errno, e.characters_written)
    del R.write
    x.close()
    R.write = lambda self, data: None
r, w = os.pipe()
os.set_blocking(w, False)
f = io.BufferedWriter(io.FileIO(w, "w"), 8)
try:
    for _ in range(64): f.write(b"x" * 65536)
    print("never blocked")
except BlockingIOError as e: print("a full pipe:", e.errno == errno.EAGAIN, e.characters_written > 0)   # reaches: a full pipe
while True:
    try: f.flush()
    except BlockingIOError: os.read(r, 1 << 20)
    else: break
f.close()
os.close(r)
'''),
    ('RL-752', "the wrappers of object and of the exceptions count their arguments", r'''
import functools
import types
import typing


class C:
    pass


class M(type):
    pass


class D(metaclass=M):
    pass


def name_of(target: object) -> str:
    return getattr(target, "__name__", "?")


for name in ("__lt__", "__le__", "__gt__", "__ge__", "__eq__", "__ne__", "__hash__", "__init__", "__dir__", "__reduce__", "__repr__", "__str__", "__format__", "__setattr__", "__delattr__", "__init_subclass__", "__subclasshook__", "__reduce_ex__", "__getstate__"):
    for target in (object, C, D, typing.Any, int, str, list, type, M, ValueError, UnicodeDecodeError, OSError, types.MappingProxyType, super, dict, tuple, float, bytes, set, range, slice, property, functools.partial, type(None), bool, complex, frozenset, bytearray, KeyError, StopIteration, BaseExceptionGroup, SyntaxError, ImportError, AttributeError, SystemExit):
        for arguments in ((), (0,), (0, 1), (0, 1, 2)):
            try:
                result = getattr(target, name)(*arguments)
                shown = "NotImplemented" if result is NotImplemented else type(result).__name__
            except AttributeError:
                shown = "AttributeError"
            except TypeError:
                shown = "TypeError"
            print(name, name_of(target), len(arguments), shown)
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
