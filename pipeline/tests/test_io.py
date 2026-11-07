"""_io, compiled, against CPython: the messages case C-7-30 does not compare, the base classes' and in-memory streams' edge cases, files
through every layer, a raw object of the program's under a BufferedReader, and what stops by name."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

BASES_AND_MEMORY = r"""
import io, _io, os, sys
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
b = _io._IOBase()
for f in (lambda: b.readline(1, 2), lambda: b.readline(size=1), lambda: b.readline("a"), lambda: b.seek(), lambda: b.seek("a"), lambda: b.seek(1, "a"), lambda: b.seek(1, 2, 3), lambda: b.seek(1, whence=2), lambda: b.truncate(1, 2), lambda: b.truncate(), lambda: b.fileno(), lambda: b.isatty(),
          lambda: b.readlines("a"), lambda: b.readlines(1, 2), lambda: b.writelines(), lambda: b.writelines(1), lambda: b.writelines([1]), lambda: b._checkClosed(1), lambda: b._checkReadable(), lambda: b._checkWritable(), lambda: b._checkSeekable(), lambda: next(b), lambda: b.__exit__(), lambda: b.__enter__(1), lambda: b.readline(None), lambda: b.readlines(None)):
    print(m(f))
print(vars(b), b.closed, m(lambda: b.close()), vars(b), b.closed, m(lambda: b.flush()), m(lambda: b.__enter__()), m(lambda: b.readline()), m(lambda: b.tell()), m(lambda: b.read()), m(lambda: b.close()), m(lambda: iter(b)), m(lambda: b.writelines([])), m(lambda: b._checkClosed()))
r = _io._RawIOBase()
print(m(lambda: r.read()), m(lambda: r.read(2)), m(lambda: r.readall()), m(lambda: r.readinto(bytearray(2))), m(lambda: r.write(b"a")), m(lambda: r.readline()), m(lambda: r.read("a")), m(lambda: r.read(None)))
t = _io._TextIOBase(); bb = _io._BufferedIOBase()
print(m(lambda: t.read()), m(lambda: t.readline()), m(lambda: t.write("a")), m(lambda: t.detach()), t.encoding, t.newlines, t.errors, m(lambda: bb.read()), m(lambda: bb.read1()), m(lambda: bb.write(b"")), m(lambda: bb.detach()), m(lambda: bb.readinto(bytearray(1))), m(lambda: bb.readinto1(bytearray(1))), m(lambda: bb.readinto(b"")), m(lambda: bb.readinto(1)))
print(io.UnsupportedOperation.__module__, io.UnsupportedOperation.__qualname__, io.UnsupportedOperation("x").args, [c.__name__ for c in io.UnsupportedOperation.__mro__], type(_io._IOBase.__dict__["closed"]).__name__, type(_io._IOBase.__dict__["readline"]).__name__, type(_io._IOBase.__dict__["__del__"]).__name__, type(_io.FileIO.__dict__["mode"]).__name__, type(_io.FileIO.__dict__["_blksize"]).__name__, type(_io.TextIOWrapper.__dict__["_CHUNK_SIZE"]).__name__)
print(m(lambda: _io.FileIO.__getstate__(_io.FileIO(0, closefd=False))), m(lambda: _io.FileIO(0, closefd=False).__reduce_ex__(2)), m(lambda: _io.BytesIO().__reduce_ex__(2)[1:]), m(lambda: _io.StringIO().__reduce_ex__(2)[1:]), m(lambda: _io.TextIOWrapper(_io.BytesIO()).__reduce_ex__(2)))
class L(_io._IOBase):
    def __init__(self): self.n = 0
    def read(self, k=-1): self.n += 1; return b"ab\n" if self.n < 3 else b""
l = L()
print(m(lambda: l.readline()), l.n, m(lambda: _io._IOBase.readline(_io._IOBase())), m(lambda: list(L())), m(lambda: L().readlines()), m(lambda: L().readlines(2)), m(lambda: L().readlines(None)), m(lambda: L().readlines(0)), m(lambda: L().readline(1)), m(lambda: L().readline(0)))
class P(L):
    def peek(self, k=0): self.p = getattr(self, "p", 0) + 1; return b"ab\nz"
p = P(); print(m(lambda: p.readline()), p.n, p.p)
class S(L):
    def read(self, k=-1): return "str"
print(m(lambda: S().readline()), m(lambda: list(S())))
class N(L):
    def read(self, k=-1): return None
print(m(lambda: N().readline()))
print(_io.DEFAULT_BUFFER_SIZE, _io.open_code, m(lambda: _io.text_encoding(None, 1)), m(lambda: _io.text_encoding()), m(lambda: _io.text_encoding("x", "y")), m(lambda: _io.text_encoding(5)), m(lambda: open_code), io.text_encoding("x"))
b = io.BytesIO(b"ab\ncd")
print(m(lambda: b.read(None)), m(lambda: b.read("a")), m(lambda: b.read(1, 2)), m(lambda: b.seek(-1)), m(lambda: b.seek(0, 5)), m(lambda: b.seek(0, whence=1)), m(lambda: b.seek("a")), m(lambda: b.truncate(-1)), m(lambda: b.truncate("a")), m(lambda: b.write("s")), m(lambda: b.write(1)), m(lambda: b.readline(None)), m(lambda: b.readlines(None)), m(lambda: b.readlines(2)), m(lambda: b.readlines("a")))
print(m(lambda: io.BytesIO(1)), m(lambda: io.BytesIO("s")), m(lambda: io.BytesIO(b"", 1)), m(lambda: io.BytesIO(initial_bytes=b"x").getvalue()), m(lambda: io.BytesIO(bytearray(b"y")).getvalue()), b.__getstate__(), m(lambda: b.__setstate__((b"q", 1, {"a": 1}))), vars(b), b.tell(), m(lambda: b.__setstate__(1)), m(lambda: b.__setstate__((1, 1, None))), m(lambda: b.__setstate__((b"", -1, None))), m(lambda: b.__setstate__((b"", "x", None))), m(lambda: b.__setstate__((b"", 1, 1))))
b.seek(0); print(b.read(2), b.read1(2), b.readline(), b.readlines(), b.read(), b.read(0), b.tell(), b.seek(100), b.read(), b.write(b"zz"), len(b.getvalue()), b.truncate(3), b.getvalue(), b.tell(), b.seek(-2, 2), b.seek(-100, 1), b.tell())
b.close(); print(b.closed, m(lambda: b.read()), m(lambda: b.getvalue()), m(lambda: b.readable()), m(lambda: b.tell()), m(lambda: b.seek(0)), m(lambda: b.write(b"")), m(lambda: b.truncate()), m(lambda: b.flush()), m(lambda: b.isatty()), m(lambda: b.__getstate__()), m(lambda: b.close()), m(lambda: next(b)), m(lambda: b.writelines([])))
c = io.BytesIO(); print(c.readable(), c.writable(), c.seekable(), c.isatty(), c.flush(), c.closed, list(io.BytesIO(b"a\nb")), m(lambda: next(io.BytesIO())), io.BytesIO(b"x").readinto(bytearray(3)), m(lambda: io.BytesIO(b"x").readinto(b"")), io.BytesIO(b"abc").readline(2), io.BytesIO(b"abc").read(-5), io.BytesIO(b"abc").read1(-5), io.BytesIO(b"abc").readlines(-5))
s = io.StringIO("ab\ncd")
print(m(lambda: s.read(None)), m(lambda: s.read("a")), m(lambda: s.seek(-1)), m(lambda: s.seek(0, 5)), m(lambda: s.seek(1, 1)), m(lambda: s.seek(0, 1)), m(lambda: s.seek(0, 2)), m(lambda: s.truncate(-1)), m(lambda: s.write(1)), m(lambda: s.write(b"x")), s.readline(), s.readlines(), s.newlines, s.line_buffering, m(lambda: s.encoding), m(lambda: s.errors), s.__getstate__(), m(lambda: io.StringIO(1)), m(lambda: io.StringIO("", 1)), m(lambda: io.StringIO("", "x")), m(lambda: io.StringIO(None, None).getvalue()), m(lambda: io.StringIO("a\r\nb", None).getvalue()), m(lambda: io.StringIO("a\nb", "\r\n").getvalue()), m(lambda: io.StringIO("a\r\nb", "").readlines()), m(lambda: io.StringIO("a\r\nb\rc", "").readline(2)), m(lambda: io.StringIO("a\r\nb", "\r\n").readlines()), m(lambda: io.StringIO("a\rb\n", "\r").readlines()))
s.close(); print(s.closed, m(lambda: s.read()), m(lambda: s.getvalue()), m(lambda: s.write("x")), m(lambda: s.seek(0)), m(lambda: s.readable()), m(lambda: s.newlines), m(lambda: s.line_buffering), m(lambda: s.close()), m(lambda: next(s)), m(lambda: s.__getstate__()), m(lambda: iter(s)))
x = io.StringIO(); x.__setstate__(("abc", "\n", 2, {"k": 1})); print(x.read(), vars(x), m(lambda: x.__setstate__(("a", "\n", -1, None))), m(lambda: x.__setstate__(("a", "\n", "q", None))), m(lambda: x.__setstate__(("a", "\n", 1, 2))), m(lambda: x.__setstate__((1, "\n", 1, None))), m(lambda: x.__setstate__(("a",))), m(lambda: x.__setstate__(3)))
y = io.StringIO(); y.seek(3); y.write("z"); print(repr(y.getvalue()), y.tell(), io.StringIO("abc").truncate(1), m(lambda: io.StringIO("abc").truncate("a")), io.StringIO("abc").seek(10), list(io.StringIO("a\nb")), repr(io.StringIO("x").read(0)))
d = io.IncrementalNewlineDecoder(None, True); print(d.decode("a\r"), repr(d.decode("\nb\rc", True)), d.newlines, d.getstate(), d.setstate((b"", 1)), d.decode("x", True), m(lambda: d.decode()), m(lambda: d.decode("a", final=True)), m(lambda: d.setstate(1)), m(lambda: d.setstate((1,))), m(lambda: io.IncrementalNewlineDecoder()), m(lambda: io.IncrementalNewlineDecoder(None, False, "strict", 1)), m(lambda: io.IncrementalNewlineDecoder.__new__(io.IncrementalNewlineDecoder).decode("a")), io.IncrementalNewlineDecoder(None, False).decode("a\r\nb\rc"), io.IncrementalNewlineDecoder(None, False, errors="x").newlines)
import codecs
d2 = io.IncrementalNewlineDecoder(codecs.getincrementaldecoder("utf-8")(), True); print(repr(d2.decode(b"a\r")), repr(d2.decode(b"\n\xc3")), repr(d2.decode(b"\xa9\r", True)), d2.newlines, d2.getstate(), d2.reset(), d2.newlines, d2.getstate())
"""

FILES = r"""
import io, _io, os, sys
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
p = "t3.txt"
for f in (lambda: open(), lambda: open(p, 1), lambda: open(p, "q"), lambda: open(p, "rr"), lambda: open(p, "rw"), lambda: open(p, "rb", encoding="x"), lambda: open(p, "rb", errors="x"), lambda: open(p, "rb", newline="x"), lambda: open(p, "r", buffering=0), lambda: open(p, "tb"), lambda: open(p, "r", closefd=False), lambda: open(1.5), lambda: open([]), lambda: open(p, mode=3), lambda: open(p, "r", "a"), lambda: open(p, encoding=1), lambda: open("/nonexistent/x"), lambda: open("."), lambda: open(p, "r", 1, "utf-8", None, None, True, None, 1), lambda: open(p, "x"), lambda: open(p, "r", opener=lambda n, f: "s"), lambda: open(p, "r", opener=lambda n, f: -1), lambda: open(p, "r", opener=lambda n, f: 1.5)):
    print(m(f))
w = open(p, "w", encoding="utf-8", newline="\r\n"); print(repr(w), w.write("one\ntwo\n"), w.tell(), w.buffer.tell(), m(lambda: w.read()), w.closed, w.close(), w.closed, m(lambda: w.write("x")))
print(open(p, "rb").read(), open(p, encoding="utf-8").read(), open(p, encoding="utf-8", newline="").read(), open(p, encoding="utf-8", newline="\r\n").readlines(), open(p, encoding="utf-8", newline="\r").readlines(), open(p, encoding="utf-8", newline="\n").readlines())
with open(p, "r+", encoding="utf-8") as rw:
    print(repr(rw), rw.read(3), rw.tell(), rw.write("ZZ"), rw.tell(), rw.seek(0), rw.read(), rw.truncate(4), rw.seek(0), rw.read(), rw.buffer.raw.mode, rw.buffer.mode, rw.mode)
raw = io.FileIO(p, "r"); print(repr(raw), raw.mode, raw.read(2), raw.tell(), raw.seek(1), raw.read(), raw.read(), raw.read(0), raw.seekable(), raw.readable(), raw.writable(), raw.isatty(), raw.fileno() > 2, raw.closefd, raw._blksize, m(lambda: raw.write(b"x")), m(lambda: raw.truncate()), raw.readall(), raw.seek(0), raw.readall(), raw.readinto(bytearray(2)), m(lambda: raw.readinto(b"ab")), raw.close(), raw.closed, repr(raw), m(lambda: raw.read()), m(lambda: raw.fileno()), m(lambda: raw.mode), m(lambda: raw.closefd), raw.close())
raw2 = io.FileIO(p, "ab+"); print(raw2.mode, raw2.tell(), raw2.write(b"\xff"), raw2.seek(0), raw2.read(), io.FileIO(p, "wb").mode, io.FileIO(p, "wb+").mode, io.FileIO(p, "rb+").mode, m(lambda: io.FileIO(p, "rwb")), m(lambda: io.FileIO(p, "++")), m(lambda: io.FileIO(p, "b")), m(lambda: io.FileIO(p, "z")), m(lambda: io.FileIO(p, "r", closefd=False)), m(lambda: io.FileIO(-1)), m(lambda: io.FileIO(1.5)), m(lambda: io.FileIO(p, mode=1)), m(lambda: io.FileIO()), m(lambda: io.FileIO(p, "r", True, None, 1)))
fd = os.open(p, os.O_RDONLY); fio = io.FileIO(fd, closefd=False); print(repr(fio), fio.name, fio.read(1), fio.close(), repr(fio), os.read(fd, 1), os.close(fd))
big = open(p, "wb"); print(repr(big), big.write(b"x" * 200000), big.tell(), big.raw.tell(), big.write(b"y" * 100), big.raw.tell(), big.flush(), big.raw.tell(), big.seek(5), big.write(b"Q"), big.seek(0, 2), big.close())
with open(p, "rb") as br:
    print(br.read(3), br.tell(), br.raw.tell(), br.peek(2)[:2], br.read1(4), br.readline(2), br.seek(-3, 2), br.read(), br.seek(2), br.read(1), m(lambda: br.seek(0, 3)), m(lambda: br.seek("a")), m(lambda: br.read(-2)), br.read(-1)[:3], br.readinto(bytearray(4)), br.readinto1(bytearray(0)), br.readable(), br.writable(), br.closed, br.name, br.mode, br.fileno() > 2, br.isatty(), br.raw.closefd, m(lambda: br.write(b"")), m(lambda: br.truncate()), m(lambda: br.read()), m(lambda: br.closed), m(lambda: repr(br)))
t = open(p, encoding="latin-1"); print(t.read(5), t.tell(), t.read(2), t.tell(), t.seek(0), t.readline(3), t.tell(), t.seek(t.tell()), t.read(1), m(lambda: t.seek(-1)), m(lambda: t.seek(1, 1)), m(lambda: t.seek(1, 2)), t.seek(0, 2), t.tell(), t.seek(0), t.encoding, t.errors, t.line_buffering, t.write_through, t.newlines, t.buffer.raw.name, t.name, t.close())
for i in range(3):
    open(p, "w", encoding="utf-8").write("ab\ncd\n" * (i * 3000 + 1))
    with open(p, encoding="utf-8") as it:
        print(sum(len(line) for line in it), it.tell() == os.path.getsize(p), m(lambda: it.tell()) if i == 0 else "")
u = open(p, "w+", encoding="utf-8"); u.write("héllo wörld\n" * 3); u.seek(0); c1 = u.tell(); u.read(5); c2 = u.tell(); u.readline(); c3 = u.tell(); u.seek(c2); print(repr(u.read(3)), u.seek(c3), repr(u.readline()), u.seek(c1), repr(u.read(2)), c1 < c2 < c3, u.seek(0, 2) == len("héllo wörld\n".encode()) * 3, m(lambda: u.seek(c2 + 1 << 64)), u.close())

class Tracker(io.StringIO):
    def close(self): print("closing", self.getvalue()); super().close()
def make():
    t = Tracker("alive"); t.write("!")
make(); print("after make")
os.remove(p); print(type(sys.stdout).__name__)
"""

RAW_OF_THE_PROGRAM = r"""
import io
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
class Raw(io.RawIOBase):
    def __init__(self, data):
        self.data = data
        self.at = 0
        self.calls = []
    def readable(self):
        return True
    def readinto(self, b):
        self.calls.append(len(b))
        chunk = self.data[self.at:self.at + len(b)]
        b[:len(chunk)] = chunk
        self.at += len(chunk)
        return len(chunk)
raw_obj = Raw(b"hello\nworld\n")
through = io.BufferedReader(raw_obj, 4)
print(m(lambda: through.read(2)), m(lambda: through.readline()), m(lambda: through.peek(1)), m(lambda: through.read()), m(lambda: through.read()), raw_obj.calls, m(lambda: raw_obj.read(2)))
print(m(lambda: through.seek(0)), m(lambda: through.tell()), through.readable(), through.writable(), through.seekable(), repr(through).split(" ")[0], m(lambda: through.name), through.close(), through.closed, raw_obj.closed)
"""


def test_bases_and_memory_streams() -> None:
    same(BASES_AND_MEMORY)


def test_files_through_every_layer() -> None:
    same(FILES)


def test_a_raw_object_of_the_program() -> None:
    same(RAW_OF_THE_PROGRAM)


def test_what_is_absent_stops_by_name() -> None:
    cases = (("import io\nio.FileIO(True)", "bool is used as a file descriptor"), ("import io\nio.BytesIO(b'a').getbuffer()", "getbuffer"),
             ("open('prog.py', 'rb', buffering=1)", "line buffering"), ("open('prog.py').reconfigure(encoding='utf-8')", "reconfigure"),
             ("import io\nio.BytesIO().readinto(memoryview(bytearray(1)))", "memoryview"))
    for body, name in cases:
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text(f"print('start')\n{body}\n", encoding="utf-8")
            got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
        assert (got.returncode, got.stdout) == (70, "start\n") and "not implemented" in got.stderr and name in got.stderr, (body, got)


if __name__ == "__main__":
    test_bases_and_memory_streams()
    test_files_through_every_layer()
    test_a_raw_object_of_the_program()
    test_what_is_absent_stops_by_name()
