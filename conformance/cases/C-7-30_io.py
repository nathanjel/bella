# clause: C-7-30
# spec: section 7
# status: P1
# source: dialect specification section 7 (Files and OS), Modules/_io, Lib/io.py
"""The io module over _io: open() in every mode and layer, FileIO over a descriptor, BufferedReader and BufferedWriter over it, the text
layer with its newline modes, encodings, seek and tell cookies, BytesIO and StringIO, the newline decoder, the base classes and their
checks, what closing and detaching leave, and the module's own names."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E402, E501, E731, PLR0133, SIM115, SLF001, UP015
import io
import os
import sys


def failed(f):  # type: ignore[no-untyped-def]
    try:
        f()
    except Exception as exc:
        return type(exc).__name__
    return "no error"


print(io.open is open, open.__module__, open.__qualname__, type(open).__name__, io.DEFAULT_BUFFER_SIZE, io.SEEK_SET, io.SEEK_CUR, io.SEEK_END, io.text_encoding(None), io.text_encoding("x"))
for cls in (io.IOBase, io.RawIOBase, io.BufferedIOBase, io.TextIOBase, io.FileIO, io.BytesIO, io.StringIO, io.BufferedReader, io.BufferedWriter, io.BufferedRandom, io.BufferedRWPair, io.TextIOWrapper, io.IncrementalNewlineDecoder, io.UnsupportedOperation):
    print(cls.__name__, cls.__module__, [c.__name__ for c in cls.__mro__], issubclass(cls, io.IOBase), isinstance(cls, type))
print(issubclass(io.FileIO, io.RawIOBase), issubclass(io.BytesIO, io.BufferedIOBase), issubclass(io.TextIOWrapper, io.TextIOBase), issubclass(io.StringIO, io.TextIOBase), issubclass(io.BufferedRandom, io.BufferedIOBase), issubclass(io.UnsupportedOperation, OSError), issubclass(io.UnsupportedOperation, ValueError))

path = "C-7-30.tmp"
with open(path, "w", encoding="utf-8") as f:
    print(type(f).__name__, type(f.buffer).__name__, type(f.buffer.raw).__name__, f.mode, f.buffer.mode, f.buffer.raw.mode, f.name == path, f.encoding, f.errors, f.newlines, f.line_buffering, f.write_through, f.closed, f.readable(), f.writable(), f.seekable(), f.isatty(), f.fileno() > 2, f.buffer.raw.closefd, vars(f), sorted(vars(f.buffer.raw)))  # type: ignore[attr-defined]
    print(f.write("one\n"), f.write("twö\n"), f.tell(), f.buffer.tell(), f.buffer.raw.tell(), f.flush(), f.buffer.raw.tell(), failed(lambda: f.read()), failed(lambda: f.write(1)), failed(lambda: f.buffer.write("s")))  # type: ignore[arg-type,attr-defined,func-returns-value,no-untyped-call]
print(f.closed, f.buffer.closed, f.buffer.raw.closed, sorted(vars(f.buffer.raw)), failed(lambda: f.write("x")), failed(lambda: f.read()), failed(lambda: f.flush()), failed(lambda: f.seek(0)), f.close(), failed(lambda: f.fileno()), failed(lambda: f.detach()), f.encoding, f.name == path)  # type: ignore[attr-defined,func-returns-value,no-untyped-call]
print(open(path, "rb").read(), open(path, encoding="utf-8").read(), open(path, encoding="utf-8", newline="").read(), open(path, encoding="latin-1").read(), open(path, "rb").readlines(), list(open(path, encoding="utf-8")), open(path, encoding="utf-8").readlines(3), open(path, "rb").readline(2), open(path, encoding="utf-8").readline(2))
with open(path, "r+", encoding="utf-8") as rw:
    print(type(rw.buffer).__name__, rw.read(3), rw.tell(), rw.write("ZZ"), rw.tell(), rw.seek(0), rw.read(), rw.truncate(4), rw.seek(0), rw.read(), rw.buffer.raw.mode, rw.buffer.mode, rw.mode)  # type: ignore[attr-defined]
with open(path, "ab") as ab:
    print(type(ab).__name__, ab.mode, ab.raw.mode, ab.tell(), ab.write(b"\xff\n"), ab.tell(), failed(lambda: ab.read()), ab.seekable())  # type: ignore[attr-defined,no-untyped-call]
with open(path, "rb", buffering=0) as raw:
    print(type(raw).__name__, raw.mode, raw.read(2), raw.tell(), raw.seek(1), raw.read(), raw.read(), raw.read(0), raw.seekable(), raw.readable(), raw.writable(), raw.isatty(), raw.closefd, raw._blksize > 0, failed(lambda: raw.write(b"x")), failed(lambda: raw.truncate()), raw.readall(), raw.seek(0), raw.readall()[:3], raw.readinto(bytearray(2)), failed(lambda: raw.readinto(b"ab")), repr(raw).split("name=")[0])  # type: ignore[attr-defined,no-untyped-call]
print(failed(lambda: raw.read()), raw.closed, repr(raw), failed(lambda: raw.mode), failed(lambda: raw.fileno()), raw.close())  # type: ignore[func-returns-value,no-untyped-call]
fd = os.open(path, os.O_RDONLY)
fio = io.FileIO(fd, closefd=False)
print(repr(fio), fio.name, fio.read(1), fio.close(), repr(fio), os.read(fd, 1), os.close(fd))  # type: ignore[func-returns-value]
with open(path, "wb") as big:
    print(type(big).__name__, big.write(b"x" * 200000), big.tell(), big.raw.tell(), big.write(b"y" * 100), big.raw.tell(), big.flush(), big.raw.tell(), big.seek(5), big.write(b"Q"), big.seek(0, 2), failed(lambda: big.read()), failed(lambda: big.peek()))  # type: ignore[attr-defined,func-returns-value,no-untyped-call]
with open(path, "rb") as br:
    print(br.read(3), br.tell(), br.raw.tell(), br.peek(2)[:2], br.read1(4), br.readline(2), br.seek(-3, 2), br.read(), br.seek(2), br.read(1), failed(lambda: br.seek(0, 3)), failed(lambda: br.seek("a")), failed(lambda: br.read(-2)), br.read(-1)[:3], br.readinto(bytearray(4)), br.readinto1(bytearray(0)), br.readable(), br.writable(), br.closed, br.name == path, br.mode, br.raw.closefd, failed(lambda: br.write(b"")), failed(lambda: br.truncate()))  # type: ignore[arg-type,attr-defined,no-untyped-call]
with open(path, "w", encoding="utf-8", newline="\r\n") as crlf:
    crlf.write("a\nb\n")
print(open(path, "rb").read(), open(path, encoding="utf-8").readlines(), open(path, encoding="utf-8", newline="").readlines(), open(path, encoding="utf-8", newline="\r").readlines(), open(path, encoding="utf-8", newline="\n").readlines(), open(path, encoding="utf-8", newline="\r\n").readlines(), open(path, encoding="utf-8").newlines)
reader = open(path, encoding="utf-8")
print(reader.read(), reader.newlines, reader.tell(), reader.seek(0), reader.read(1), reader.newlines, reader.tell(), reader.close())  # type: ignore[func-returns-value]
with open(path, "w+", encoding="utf-8") as u:
    u.write("héllo wörld\n" * 3)
    u.seek(0)
    c1 = u.tell()
    u.read(5)
    c2 = u.tell()
    u.readline()
    c3 = u.tell()
    u.seek(c2)
    print(repr(u.read(3)), u.seek(c3), repr(u.readline()), u.seek(c1), repr(u.read(2)), c1 < c2 < c3, u.seek(0, 2) == len("héllo wörld\n".encode()) * 3, failed(lambda: u.seek(-1)), failed(lambda: u.seek(1, 1)), failed(lambda: u.seek(1, 2)), failed(lambda: u.seek(0, 3)), failed(lambda: u.seek("a")))  # type: ignore[arg-type,no-untyped-call]
for n in (1, 3000, 9001):
    with open(path, "w", encoding="utf-8") as w:
        w.write("ab\ncd\n" * n)
    with open(path, encoding="utf-8") as it:
        total = sum(len(line) for line in it)
    print(total, failed(lambda: it.read()), os.path.getsize(path))  # type: ignore[no-untyped-call]
lines = ["x" * 5000 + "\n", "é" * 3000 + "\r\n", "end"]
with open(path, "w", encoding="utf-8", newline="") as w:
    w.writelines(lines)
with open(path, encoding="utf-8") as r:
    print([len(line) for line in r], r.newlines, r.tell() == os.path.getsize(path))
with open(path, encoding="utf-8", newline="") as r:
    print([len(line) for line in r], r.newlines)
with open(path, "rb") as r:  # type: ignore[assignment]
    print([len(line) for line in r], r.tell() == os.path.getsize(path), failed(lambda: next(r)))  # type: ignore[no-untyped-call]
print(failed(lambda: open()), failed(lambda: open(path, 1)), failed(lambda: open(path, "q")), failed(lambda: open(path, "rr")), failed(lambda: open(path, "rw")), failed(lambda: open(path, "rb", encoding="x")), failed(lambda: open(path, "rb", errors="x")), failed(lambda: open(path, "rb", newline="x")), failed(lambda: open(path, "r", buffering=0)), failed(lambda: open(path, "tb")), failed(lambda: open(path, "r", closefd=False)), failed(lambda: open(1.5)), failed(lambda: open([])), failed(lambda: open(path, encoding=1)), failed(lambda: open("C-7-30.absent")), failed(lambda: open(".")), failed(lambda: open(path, "x")), failed(lambda: open(path, encoding="nope")), failed(lambda: open(path, newline="x")), failed(lambda: open(path, "r", opener=lambda n, f: "s")), failed(lambda: open(path, "r", opener=lambda n, f: -1)))  # type: ignore[arg-type,call-overload,no-untyped-call,return-value]
print(failed(lambda: io.FileIO(path, "rwb")), failed(lambda: io.FileIO(path, "++")), failed(lambda: io.FileIO(path, "b")), failed(lambda: io.FileIO(path, "r", closefd=False)), failed(lambda: io.FileIO(-1)), failed(lambda: io.FileIO(1.5)), failed(lambda: io.FileIO(path, mode=1)), failed(lambda: io.FileIO()), io.FileIO(path, "wb").mode, io.FileIO(path, "wb+").mode, io.FileIO(path, "rb+").mode, io.FileIO(path, "ab+").mode, io.FileIO(path, "a").mode)  # type: ignore[arg-type,call-arg,no-untyped-call]
print(failed(lambda: io.BufferedReader(io.BytesIO(), 0)), failed(lambda: io.BufferedReader(1)), failed(lambda: io.BufferedWriter(io.FileIO(path, "r"))), failed(lambda: io.BufferedReader(io.FileIO(path, "w"))), failed(lambda: io.TextIOWrapper(io.BytesIO(), newline="x")), failed(lambda: io.TextIOWrapper(io.BytesIO(), newline=1)), failed(lambda: io.TextIOWrapper(io.BytesIO(), encoding="nope")), failed(lambda: io.TextIOWrapper(io.BytesIO(), errors=1)), failed(lambda: io.TextIOWrapper()), failed(lambda: io.TextIOWrapper(1)), io.TextIOWrapper(io.BytesIO(), encoding="locale").encoding, io.TextIOWrapper(io.BytesIO()).encoding, io.TextIOWrapper(io.BytesIO(), encoding="UTF8").encoding, io.TextIOWrapper(io.BytesIO(b"a"), encoding="u8").read(), io.TextIOWrapper(io.BytesIO(b"\xe9"), encoding="latin-1").read())  # type: ignore[arg-type,call-arg,no-untyped-call,type-var]

bio = io.BytesIO(b"ab\ncd")
print(bio.read(2), bio.read1(2), bio.readline(), bio.readlines(), bio.read(), bio.read(0), bio.tell(), bio.seek(100), bio.read(), bio.write(b"zz"), len(bio.getvalue()), bio.truncate(3), bio.getvalue(), bio.tell(), bio.seek(-2, 2), bio.seek(-100, 1), bio.tell(), bio.readable(), bio.writable(), bio.seekable(), bio.isatty(), bio.flush(), bio.closed, bio.readinto(bytearray(3)), bio.__getstate__(), list(io.BytesIO(b"a\nb")), io.BytesIO(bytearray(b"y")).getvalue(), io.BytesIO(initial_bytes=b"x").getvalue(), io.BytesIO(None).getvalue())  # type: ignore[arg-type,func-returns-value]
print(failed(lambda: bio.read("a")), failed(lambda: bio.seek(-1)), failed(lambda: bio.seek(0, 5)), failed(lambda: bio.seek(0, whence=1)), failed(lambda: bio.truncate(-1)), failed(lambda: bio.write("s")), failed(lambda: bio.readinto(b"")), failed(lambda: io.BytesIO(1)), failed(lambda: io.BytesIO("s")), failed(lambda: bio.readlines("a")), failed(lambda: bio.__setstate__(1)), failed(lambda: bio.__setstate__((b"", -1, None))))  # type: ignore[arg-type,attr-defined,call-arg,no-untyped-call]
bio.__setstate__((b"q", 1, {"a": 1}))  # type: ignore[attr-defined]
print(vars(bio), bio.tell(), bio.read(), bio.close(), bio.closed, failed(lambda: bio.read()), failed(lambda: bio.getvalue()), failed(lambda: bio.readable()), failed(lambda: bio.tell()), failed(lambda: bio.seek(0)), failed(lambda: bio.write(b"")), failed(lambda: bio.__getstate__()), failed(lambda: next(bio)), bio.close())  # type: ignore[func-returns-value,no-untyped-call]
sio = io.StringIO("ab\ncd")
print(repr(sio.read(1)), sio.readline(), sio.readlines(), sio.tell(), sio.seek(0), repr(sio.read()), sio.getvalue(), sio.newlines, sio.line_buffering, sio.encoding, sio.errors, sio.__getstate__(), sio.write("é"), sio.getvalue(), sio.truncate(2), sio.getvalue(), sio.seek(5), sio.write("z"), repr(sio.getvalue()), sio.readable(), sio.writable(), sio.seekable(), list(io.StringIO("a\nb")), repr(io.StringIO("x").read(0)))
print(io.StringIO("a\r\nb", None).getvalue(), io.StringIO("a\nb", "\r\n").getvalue(), io.StringIO("a\r\nb", "").readlines(), io.StringIO("a\r\nb\rc", "").readline(2), io.StringIO("a\r\nb", "\r\n").readlines(), io.StringIO("a\rb\n", "\r").readlines(), io.StringIO("a\r\nb", "").newlines, io.StringIO(newline=None).newlines, io.StringIO("a\r\nb\rc\n").read(), io.StringIO("a\r\nb\rc\n").readlines(), io.StringIO("q", "\r\n").newlines, io.StringIO(None, None).getvalue())
print(failed(lambda: sio.read("a")), failed(lambda: sio.seek(-1)), failed(lambda: sio.seek(0, 5)), failed(lambda: sio.seek(1, 1)), failed(lambda: sio.truncate(-1)), failed(lambda: sio.write(1)), failed(lambda: sio.write(b"x")), failed(lambda: io.StringIO(1)), failed(lambda: io.StringIO("", 1)), failed(lambda: io.StringIO("", "x")), failed(lambda: sio.__setstate__(("a", "\n", -1, None))), failed(lambda: sio.__setstate__(3)))  # type: ignore[arg-type,attr-defined,no-untyped-call]
sio.__setstate__(("abc", "\n", 2, {"k": 1}))  # type: ignore[attr-defined]
print(sio.read(), vars(sio), sio.close(), sio.closed, failed(lambda: sio.read()), failed(lambda: sio.getvalue()), failed(lambda: sio.write("x")), failed(lambda: sio.newlines), failed(lambda: sio.line_buffering), failed(lambda: next(sio)), sio.close())  # type: ignore[func-returns-value,no-untyped-call]
d = io.IncrementalNewlineDecoder(None, True)
print(repr(d.decode("a\r")), repr(d.decode("\nb\rc", True)), d.newlines, d.getstate(), d.setstate((b"", 1)), repr(d.decode("x", True)), failed(lambda: d.decode()), failed(lambda: d.setstate(1)), failed(lambda: d.setstate((1,))), failed(lambda: io.IncrementalNewlineDecoder()), io.IncrementalNewlineDecoder(None, False).decode("a\r\nb\rc"), io.IncrementalNewlineDecoder(None, False, errors="x").newlines, d.reset(), d.newlines)  # type: ignore[arg-type,call-arg,func-returns-value,no-untyped-call]
import codecs
d2 = io.IncrementalNewlineDecoder(codecs.getincrementaldecoder("utf-8")(), True)
print(repr(d2.decode(b"a\r")), repr(d2.decode(b"\n\xc3")), repr(d2.decode(b"\xa9\r", True)), d2.newlines, d2.getstate(), d2.reset(), d2.newlines)  # type: ignore[func-returns-value]
base = io.IOBase()
print(vars(base), base.closed, base.close(), vars(base), base.closed, failed(lambda: base.flush()), failed(lambda: base.__enter__()), failed(lambda: base.tell()), failed(lambda: base.fileno()), failed(lambda: base.seek(0)), failed(lambda: base.truncate()), failed(lambda: base.readline()), base.readable(), base.writable(), base.seekable(), failed(lambda: base._checkReadable()), failed(lambda: base._checkWritable()), failed(lambda: base._checkSeekable()), failed(lambda: iter(base)), failed(lambda: base.writelines([])))  # type: ignore[attr-defined,func-returns-value,no-untyped-call]


class Lines(io.IOBase):
    def __init__(self):  # type: ignore[no-untyped-def]
        self.n = 0

    def read(self, k=-1):  # type: ignore[no-untyped-def]
        self.n += 1
        return b"ab\n" if self.n < 3 else b""


class Peeking(Lines):
    def peek(self, k=0):  # type: ignore[no-untyped-def]
        return b"ab\nz"


class Texty(Lines):
    def read(self, k=-1):  # type: ignore[no-untyped-def]
        return "str"


lines = Lines()  # type: ignore[assignment,no-untyped-call]
peeking = Peeking()  # type: ignore[no-untyped-call]
print(lines.readline(), lines.n, list(Lines()), Lines().readlines(), Lines().readlines(2), Lines().readline(1), Lines().readline(0), peeking.readline(), peeking.n, failed(lambda: Texty().readline()), failed(lambda: list(Texty())), lines.isatty(), failed(lambda: io.IOBase.readline(io.IOBase())))  # type: ignore[attr-defined,no-untyped-call]
raw_base = io.RawIOBase()
buffered_base = io.BufferedIOBase()
text_base = io.TextIOBase()
print(failed(lambda: raw_base.read()), failed(lambda: raw_base.readall()), failed(lambda: raw_base.readinto(bytearray(2))), failed(lambda: raw_base.write(b"a")), failed(lambda: raw_base.readline()), failed(lambda: buffered_base.read()), failed(lambda: buffered_base.read1()), failed(lambda: buffered_base.write(b"")), failed(lambda: buffered_base.detach()), failed(lambda: buffered_base.readinto(bytearray(1))), failed(lambda: buffered_base.readinto(b"")), failed(lambda: text_base.read()), failed(lambda: text_base.readline()), failed(lambda: text_base.write("a")), failed(lambda: text_base.detach()), text_base.encoding, text_base.newlines, text_base.errors)  # type: ignore[no-untyped-call]


class Raw(io.RawIOBase):
    def __init__(self, data):  # type: ignore[no-untyped-def]
        self.data = data
        self.at = 0
        self.calls = []

    def readable(self):  # type: ignore[no-untyped-def]
        return True

    def readinto(self, b):  # type: ignore[no-untyped-def]
        self.calls.append(len(b))
        chunk = self.data[self.at:self.at + len(b)]
        b[:len(chunk)] = chunk
        self.at += len(chunk)
        return len(chunk)


raw_obj = Raw(b"hello\nworld\n")  # type: ignore[no-untyped-call]
through = io.BufferedReader(raw_obj, 4)
print(through.read(2), through.readline(), through.peek(1), through.read(), through.read(), raw_obj.calls, raw_obj.read(2), failed(lambda: through.seek(0)), failed(lambda: through.tell()), through.readable(), through.writable(), through.seekable(), repr(through).split(" ")[0], failed(lambda: through.name), through.close(), through.closed, raw_obj.closed)  # type: ignore[func-returns-value,no-untyped-call]
rw = io.BufferedRWPair(Raw(b"in\n"), io.BytesIO(), 8)  # type: ignore[assignment,no-untyped-call]
print(rw.read(2), rw.write(b"out"), rw.readable(), rw.writable(), rw.closed, rw.isatty(), rw.flush(), rw.close(), rw.closed, failed(lambda: rw.read()))  # type: ignore[arg-type,func-returns-value,no-untyped-call]
out, err, inp = sys.stdout, sys.stderr, sys.stdin
print(type(out).__name__, type(out).__module__, repr(out), out.name, out.mode, out.encoding, out.errors, out.newlines, out.write_through, out.closed, out.fileno(), out.readable(), out.writable(), out.seekable(), vars(out), repr(out.buffer), repr(out.buffer.raw), vars(out.buffer.raw), out.buffer.raw.closefd, out.buffer.raw.mode, sys.__stdout__ is out)  # type: ignore[union-attr]
print(repr(err), err.errors, err.line_buffering, err.fileno(), repr(inp), inp.errors, inp.mode, inp.encoding, inp.readable(), inp.buffer.raw.mode, sys.__stdin__ is inp, sys.__stderr__ is err, sorted(n for n in dir(sys) if "std" in n))  # type: ignore[union-attr]
print(out.write("direct\n"), out.buffer.write(b"bytes\n"), out.flush(), out.buffer.raw.write(b"raw\n"))  # type: ignore[union-attr]
sys.stdout = io.StringIO()
print("captured", 1, 2)
captured = sys.stdout.getvalue()
sys.stdout = out
print(repr(captured), "\udcff".encode("utf-8", "surrogateescape"))
os.remove(path)
