"""memoryview, as far as phase 1 has it (the author's decision of 2026-11-14; runtime/prelude/memoryview.py; case C-6-25).

Four programs, each run once under CPython and once compiled:

* SURFACE: what a view is made of and what refuses, with CPython's words; items, slices and keys of every kind; what a
  view says of itself; equality, hash, repr, iteration, `tobytes` and `tolist` with their argument checks; assignment of an
  item where the view is writable, and the refusals where it is not; the context manager; weak references.
* EDGES: contiguity (a strided view of one item is contiguous, one of none is not), iteration after a release, slices with
  `__index__` and None, comparison with views, bytes, bytearrays and bytes subclasses, the exporter's own hash asked first,
  what a released view refuses, `obj` of a slice, the Sequence ABC.
* CONSUMERS: 42 places that take bytes-like data, each with a contiguous view and a strided one: most take a simple buffer
  (BufferError for the strided), some copy (bytes(), bytearray(), slice assignment, %b, equality, hash), and some word the
  failure as a TypeError of their own (join, concatenation, str() with an encoding, re).
* REGULAR_EXPRESSIONS: re over a view of bytes and of a bytearray; the engine holds a buffer of the view itself, so a
  callback that releases it, or a scanner that is alive, is a BufferError.

What stops by name and is not here: `cast`, `hex`, `count`, `index`, `toreadonly`, `__buffer__`, slice assignment, a
memoryview as a buffer to write into, `__sizeof__`, pickling. Left out as well: `vars(memoryview)` lists only the names the
runtime has, as `vars(dict)` does (TODO.md).

Run under pytest or directly: python3 -m pipeline.tests.test_memoryview
"""
from __future__ import annotations

from typing import Any

from pipeline.tests.test_review_2026_11_19 import same

SURFACE = r'''
import sys
def t(label, f):
    try: r = f(); print(label, "->", repr(r)[:120])
    except BaseException as e: print(label, "->", type(e).__name__ + ":", str(e)[:150])
m = memoryview(b"abcdef")
w = memoryview(bytearray(b"abc"))
gone = memoryview(b"x"); gone.release()
t("type", lambda: (type(m).__name__, type(m).__module__, type(m).__qualname__))
t("subclass", lambda: type("S", (memoryview,), {}))
t("memoryview('s')", lambda: memoryview("s"))
t("memoryview(5)", lambda: memoryview(5))
t("memoryview()", lambda: memoryview())
t("memoryview(b'', b'')", lambda: memoryview(b"", b""))
t("memoryview(x=b'')", lambda: memoryview(x=b""))
t("memoryview(object=b'a', x=1)", lambda: memoryview(object=b"a", x=1))
t("m[6]", lambda: m[6])
t("m['a']", lambda: m["a"])
t("m[1.5]", lambda: m[1.5])
t("m[::0]", lambda: m[::0])
t("m[True]", lambda: m[True])
t("m[...]", lambda: m[...])
t("m[()]", lambda: m[()])
t("m[0,]", lambda: m[0,])
t("m[0, 1]", lambda: m[0, 1])
t("m[2**70]", lambda: m[2**70])
class I:
    def __index__(self): return 2
t("m[I()]", lambda: m[I()])
t("m[I():]", lambda: m[I():].tobytes())
t("len gone", lambda: len(gone))
t("gone[0]", lambda: gone[0])
t("gone.format", lambda: gone.format)
t("gone.obj", lambda: gone.obj)
t("repr m", lambda: repr(m)[:13])
t("repr gone", lambda: repr(gone)[:22])
t("str m", lambda: str(m)[:13])
t("hash m", lambda: hash(m) == hash(b"abcdef"))
t("hash m[::2]", lambda: hash(m[::2]) == hash(b"ace"))
t("hash w", lambda: hash(w))
t("hash gone", lambda: hash(gone))
t("m == b'abcdef'", lambda: m == b"abcdef")
t("m == bytearray", lambda: m == bytearray(b"abcdef"))
t("m == m[:]", lambda: m == m[:])
t("m == 'abcdef'", lambda: m == "abcdef")
t("m != b'x'", lambda: m != b"x")
t("m < m", lambda: m < m)
t("gone == gone", lambda: gone == gone)
t("gone == b'x'", lambda: gone == b"x")
t("m == gone", lambda: m == gone)
t("m.__eq__(5)", lambda: m.__eq__(5))
t("list(m[:3])", lambda: list(m[:3]))
t("iter type", lambda: type(iter(m)).__name__)
t("iter gone", lambda: iter(gone))
t("reversed(m)", lambda: list(reversed(m))[:2])
t("b'a' in m", lambda: 97 in m)
t("m.tolist()", lambda: m[:2].tolist())
t("m.tobytes('C')", lambda: m.tobytes("C"))
t("m.tobytes('X')", lambda: m.tobytes("X"))
t("m.tobytes(order=None)", lambda: m.tobytes(order=None))
t("m.release(1)", lambda: m.release(1))
t("w[0] = 120", lambda: w.__setitem__(0, 120))
t("m[0] = 120", lambda: m.__setitem__(0, 120))
t("del w[0]", lambda: w.__delitem__(0))
t("nbytes shape strides", lambda: (m.nbytes, m.shape, m.strides, m.suboffsets, m.c_contiguous, m.f_contiguous, m.contiguous, m[::2].contiguous))
t("obj", lambda: m.obj is m.obj and type(m.obj).__name__)
t("obj of view of view", lambda: memoryview(m).obj is m.obj)
t("m.__enter__() is m", lambda: m.__enter__() is m)
t("gone.__enter__", lambda: gone.__enter__())
t("m.__exit__(1,2,3)", lambda: memoryview(b"a").__exit__(1, 2, 3))
t("m.__exit__()", lambda: memoryview(b"a").__exit__())
t("bytes(gone)", lambda: bytes(gone))
t("bool(m)", lambda: (bool(m), bool(memoryview(b""))))
t("dir extra", lambda: sorted(set(dir(m)) - set(dir(object))))
t("readonly set", lambda: setattr(m, "readonly", False))
t("attr set", lambda: setattr(m, "x", 1))
t("weakref", lambda: __import__("weakref").ref(m)() is m)

'''

EDGES = r'''
import sys
def t(label, f):
    try: r = f(); print(label.ljust(34), "->", repr(r)[:200])
    except BaseException as e: print(label.ljust(34), "->", type(e).__name__ + ":", str(e)[:150])
m = memoryview(b"abcdef")
t("one strided contiguous", lambda: (m[::5].contiguous, m[::5].strides, len(m[::5])))
t("empty strided contiguous", lambda: (m[2:2:3].contiguous, len(m[2:2:3]), m[2:2:3].strides))
t("reversed contiguous", lambda: (m[::-1].contiguous, m[::-1].strides))
t("crc of one strided", lambda: __import__("zlib").crc32(m[::5]))
t("crc of empty strided", lambda: __import__("zlib").crc32(m[2:2:3]))
t("crc of reversed", lambda: __import__("zlib").crc32(m[::-1]))
t("bytes join one strided", lambda: b"".join([m[::5]]))
it = iter(memoryview(b"ab"))
v2 = memoryview(b"xyz"); it2 = iter(v2); next(it2)
t("release with an iterator", lambda: v2.release())
t("next after release", lambda: next(it2))
t("iter of iter", lambda: iter(it) is it)
t("memory_iterator repr", lambda: repr(it)[:24])
t("length_hint", lambda: it.__length_hint__())
t("mv[int]", lambda: memoryview[int])
t("m.__len__()", lambda: m.__len__())
t("m.__getitem__(slice(1,2)).tobytes()", lambda: m.__getitem__(slice(1, 2)).tobytes())
t("slice with None", lambda: m[None:None].tobytes())
t("slice with __index__", lambda: m[slice(True, 3)].tobytes())
t("slice bad", lambda: m["a":2])
t("m[-1]", lambda: m[-1])
t("m[-7]", lambda: m[-7])
t("format of bytearray view", lambda: memoryview(bytearray(b"a")).format)
t("memoryview(memoryview(bytearray)).readonly", lambda: memoryview(memoryview(bytearray(b"a"))).readonly)
t("view of view of released", lambda: memoryview(memoryview(b"a")[0:0]))
t("eq other view", lambda: memoryview(b"ab") == memoryview(bytearray(b"ab")))
t("eq different lengths", lambda: memoryview(b"ab") == b"abc")
t("eq strided vs bytes", lambda: memoryview(b"abcd")[::2] == b"ac")
t("eq bytes subclass", lambda: memoryview(b"ab") == type("B", (bytes,), {})(b"ab"))
t("hash cached", lambda: hash(memoryview(b"ab")) == hash(b"ab"))
t("bool released", lambda: bool((lambda g: (g.release(), g)[1])(memoryview(b"a"))))
t("len released", lambda: len((lambda g: (g.release(), g)[1])(memoryview(b""))))
t("released release again", lambda: (lambda g: (g.release(), g.release())[1])(memoryview(b"a")))
t("with exit returns", lambda: memoryview(b"a").__exit__(None, None, None))
t("exit released", lambda: (lambda g: (g.release(), g.__exit__(None, None, None))[1])(memoryview(b"a")))
t("enter released", lambda: (lambda g: (g.release(), g.__enter__())[1])(memoryview(b"a")))
t("dir released", lambda: len(dir((lambda g: (g.release(), g)[1])(memoryview(b"a")))))
t("obj of slice", lambda: memoryview(b"ab")[1:].obj)
t("isinstance Sequence", lambda: isinstance(m, __import__("collections.abc").abc.Sequence))
t("reversed type", lambda: type(reversed(m)).__name__)
t("m.tolist() strided", lambda: m[::2].tolist())
t("tobytes(order='A')", lambda: m.tobytes(order="A"))
t("tobytes(1)", lambda: m.tobytes(1))
t("tobytes('C', 1)", lambda: m.tobytes("C", 1))
t("tobytes(x=1)", lambda: m.tobytes(x=1))
t("tolist(1)", lambda: m.tolist(1))
t("private names", lambda: [n for n in ("_hold", "_start", "_step", "_length", "_readonly", "_obj") if hasattr(m, n)])
t("dir equal", lambda: sorted(dir(m)))
t("release attr kinds", lambda: (type(memoryview.release).__name__, type(memoryview.obj).__name__, type(memoryview.__getitem__).__name__, type(memoryview.__new__).__name__))
t("isinstance check", lambda: isinstance(m, memoryview) and type(m) is memoryview)

'''

CONSUMERS = r'''
import binascii, hashlib, io, os, struct, zlib, base64, re, codecs, _md5, _sha2, _blake2, hmac
s = memoryview(b"\x01\x02\x03\x04\x05\x06")[::2]
c = memoryview(b"\x01\x02\x03\x04")
def t(label, f):
    try: r = f(); print(label.ljust(28), "ok", repr(r)[:60])
    except BaseException as e: print(label.ljust(28), type(e).__name__ + ":", str(e)[:80])
rows = {
 "bytes(v)": lambda v: bytes(v), "bytearray(v)": lambda v: bytearray(v), "b''.join([v])": lambda v: b"".join([v]),
 "b'a' + v": lambda v: b"a" + v, "bytearray()+=v": lambda v: (lambda b: (b.__iadd__(v), b)[1])(bytearray()),
 "b'a'.startswith(v)": lambda v: b"\x01".startswith(v), "v in b'..'": lambda v: v in b"\x01\x03\x05",
 "b'..'.find(v)": lambda v: b"\x01\x03".find(v), "b'..'.split(v)": lambda v: b"\x01\x03".split(v),
 "bytes.fromhex": lambda v: None, "int.from_bytes": lambda v: int.from_bytes(v, "big"),
 "str(v,'latin-1')": lambda v: str(v, "latin-1"), "codecs.decode": lambda v: codecs.decode(v, "latin-1"),
 "BytesIO(v)": lambda v: io.BytesIO(v).getvalue(), "BytesIO.write(v)": lambda v: io.BytesIO().write(v),
 "struct.unpack": lambda v: struct.unpack("3B", v), "struct.unpack_from": lambda v: struct.unpack_from("B", v),
 "struct.iter_unpack": lambda v: list(struct.iter_unpack("B", v)),
 "binascii.hexlify": lambda v: binascii.hexlify(v), "binascii.crc32": lambda v: binascii.crc32(v),
 "binascii.a2b_hex": lambda v: binascii.a2b_hex(memoryview(b"0a0b")[::1]),
 "zlib.crc32": lambda v: zlib.crc32(v), "zlib.compress": lambda v: len(zlib.compress(v)),
 "hashlib.sha256": lambda v: hashlib.sha256(v).hexdigest()[:8], "hashlib.md5": lambda v: hashlib.md5(v).hexdigest()[:8],
 "blake2b": lambda v: hashlib.blake2b(v).hexdigest()[:8], "hmac.digest key": lambda v: hmac.digest(v, b"m", "sha256")[:2],
 "base64.b64encode": lambda v: base64.b64encode(v), "re.match": lambda v: re.match(b".", v),
 "os.write": lambda v: os.write(os.open(os.devnull, os.O_WRONLY), v), "os.fsencode": lambda v: None,
 "memoryview(v)": lambda v: memoryview(v).tobytes(), "v == b'..'": lambda v: v == b"\x01\x03\x05",
 "hash(v)": lambda v: hash(v) == hash(bytes(v)), "v.tobytes()": lambda v: v.tobytes(),
 "bytearray(b'..')[0:2]=v": lambda v: (lambda b: (b.__setitem__(slice(0, 2), v), b)[1])(bytearray(b"zz")),
 "b'%b' % v": lambda v: b"%b" % v, "bytes.maketrans": lambda v: len(bytes.maketrans(v, v)),
 "float.fromhex": lambda v: None, "complex": lambda v: None,
 "ascii(v)": lambda v: ascii(v)[:8], "print to BytesIO": lambda v: None,
}
for name, f in rows.items():
    t(name + " contiguous", lambda: f(c))
    t(name + " strided", lambda: f(s))

'''

REGULAR_EXPRESSIONS = r'''
import re
v = memoryview(b"abc abd")
def t(label, f):
    try: r = f(); print(label.ljust(26), "->", repr(r)[:150])
    except BaseException as e: print(label.ljust(26), "->", type(e).__name__ + ":", str(e)[:120])
t("match", lambda: re.match(b"ab", v))
t("match string", lambda: re.match(b"ab", v).string is v)
t("group", lambda: (re.match(b"(a)(b)", v).group(0, 1, 2), type(re.match(b"ab", v).group()).__name__))
t("findall", lambda: re.findall(b"ab.", v))
t("sub", lambda: re.sub(b"a", b"z", v))
t("split", lambda: re.split(b" ", v))
t("finditer", lambda: [m.span() for m in re.finditer(b"ab", v)])
t("strided", lambda: re.match(b"a", v[::2]))
t("released", lambda: (lambda g: (g.release(), re.match(b"a", g)))(memoryview(b"a")))
t("release during sub", lambda: re.sub(b".", lambda m: (v.release(), b"")[1], v))
t("released after", lambda: v.tobytes())
w = memoryview(bytearray(b"xyz"))
t("bytearray view search", lambda: re.search(b"y", w).span())
t("scanner hold", lambda: (lambda it: (next(it).span(), w.release()))(re.finditer(b".", w)))
t("pattern from view", lambda: re.compile(memoryview(b"ab")))
t("fullmatch str pattern", lambda: re.fullmatch("a", memoryview(b"a")))

'''


PROGRAMS = {"surface": SURFACE, "edges": EDGES, "consumers": CONSUMERS, "regular_expressions": REGULAR_EXPRESSIONS}


def pytest_generate_tests(metafunc: Any) -> None:
    if "program" in metafunc.fixturenames:
        metafunc.parametrize("program", sorted(PROGRAMS))


def test_programs(program: str) -> None:
    same(PROGRAMS[program])


if __name__ == "__main__":
    for name in sorted(PROGRAMS):
        same(PROGRAMS[name])
    print("ok")
