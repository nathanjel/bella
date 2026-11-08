# clause: C-7-36
# spec: section 7
# status: P1
# source: dialect specification section 7, Modules/_struct.c, Objects/floatobject.c (PyFloat_Pack2/4/8)
"""struct over _struct: the format string (byte order, counts, whitespace, every code of 3.15 and its native size and alignment), pack
and unpack of each kind with the C's range and type messages, the half, single and double floats with their rounding, NaNs and
overflow, Struct's attributes and methods, unpack_from and pack_into with offsets, the unpack iterator, the module's functions and
their calling conventions, the cache."""
# ruff: noqa: ANN001, ANN002, ANN003, ANN201, ANN202, ANN204, B018, B023, E501, E731, E741, E742, F601, PLR0133, SLF001
import struct


def m(f):  # type: ignore[no-untyped-def]
    try:
        return repr(f())
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


s = struct.Struct(">Q")
print(s.format, s.size, s.pack(1), s.unpack(b"\x00" * 7 + b"\x05"), repr(s), s.__sizeof__(), type(s).__name__, type(s).__module__, struct.error.__module__, struct.error.__name__)
for fmt in ("", "x", "b", "B", "h", "H", "i", "I", "l", "L", "q", "Q", "n", "N", "e", "f", "d", "?", "c", "s", "p", "P", "F", "D", "Zf", "Zd", "<l", ">l", "=l", "!l", "@l", "2b3h", "b0i", "0s", "bi", "<bi", "hqb", "ci", "3s2x i", "  b  ", "10p"):
    print(repr(fmt), m(lambda: struct.calcsize(fmt)))  # type: ignore[no-untyped-call]
print(m(lambda: struct.calcsize("<n")), m(lambda: struct.calcsize("z")), m(lambda: struct.calcsize("3")), m(lambda: struct.calcsize("é")), m(lambda: struct.calcsize("b\x00")), m(lambda: struct.calcsize(1)), m(lambda: struct.calcsize(b"<l")), m(lambda: struct.calcsize(b"\xff")), m(lambda: struct.calcsize("9999999999999999999999b")), m(lambda: struct.calcsize("99999999999999999s")))  # type: ignore[arg-type,no-untyped-call]
print(struct.pack("<hHiIlLqQ", -2, 2, -3, 3, -4, 4, -5, 5), struct.pack(">hHiIlLqQ", -2, 2, -3, 3, -4, 4, -5, 5), struct.pack("hHiIlLqQnN", -2, 2, -3, 3, -4, 4, -5, 5, -6, 6), struct.pack("bB?c3s5p2x", -1, 255, 3, b"x", b"abcdef", b"hello world", ), struct.pack("P", 2**64 - 1), struct.pack("P", -1))
print(struct.unpack("<hHiIlLqQ", struct.pack("<hHiIlLqQ", -2, 2, -3, 3, -4, 4, -5, 5)), struct.unpack("bB?c3s5p2x", struct.pack("bB?c3s5p2x", -1, 255, 3, b"x", b"ab", b"hello world")), struct.unpack("P", struct.pack("P", -1)), struct.unpack("0s0p", b""), struct.unpack("1p", b"\x05"), struct.unpack("3p", b"\x09ab"))
for fmt, v in (("b", 128), ("b", -129), ("B", 256), ("B", -1), ("h", 2**15), ("H", -1), ("i", 2**31), ("I", 2**32), ("l", 2**63), ("L", 2**64), ("q", -(2**63) - 1), ("Q", -1), ("n", 2**63), ("N", -1), ("<l", 2**31), ("<L", 2**32), (">q", 2**63), (">Q", 2**64), ("<h", 2**70), ("P", 2**64), ("P", -(2**63) - 1), ("b", 1.5), ("b", "1"), ("c", b"ab"), ("c", "a"), ("c", bytearray(b"a")), ("s", "a"), ("p", 1), ("?", object()), ("f", "1"), ("f", 1), ("f", 1e40), ("e", 65520.0), ("e", 65519.0), ("d", 1e308), ("e", 1e-30), ("f", 2**130), ("F", 1), ("F", "x"), ("D", 1 + 2j), ("F", 1e40 + 0j), ("x", 1), ("", 1)):
    print(fmt, repr(v)[:10], m(lambda: struct.pack(fmt, v)))  # type: ignore[no-untyped-call]
class I:
    def __index__(self): return 7  # type: ignore[no-untyped-def]
class Fl:
    def __float__(self): return 2.5  # type: ignore[no-untyped-def]
class Idx2:
    def __index__(self): return 3  # type: ignore[no-untyped-def]
print(struct.pack("b", I()), struct.pack("f", Fl()), struct.pack("d", Idx2()), struct.pack("e", I()), struct.pack("?", []), struct.pack("?", [0]), struct.pack("Q", True), m(lambda: struct.pack("b", Fl())), m(lambda: struct.pack("f", I())))  # type: ignore[no-untyped-call]
for fmt, data in (("<e", b"\x00\x3c"), ("<e", b"\x00\x7c"), ("<e", b"\x00\xfc"), ("<e", b"\x01\x7c"), ("<e", b"\x01\x00"), ("<e", b"\xff\x7b"), ("<f", b"\x00\x00\x80\x3f"), ("<f", b"\x01\x00\x80\x7f"), ("<f", b"\x00\x00\xc0\x7f"), ("<f", b"\x01\x00\x00\x00"), (">d", b"\x3f\xf0\x00\x00\x00\x00\x00\x00"), ("<d", b"\x01\x00\x00\x00\x00\x00\xf0\x7f"), ("<F", b"\x00\x00\x80\x3f\x00\x00\x00\xc0"), (">D", b"\x3f\xf0" + b"\x00" * 6 + b"\xc0\x00" + b"\x00" * 6)):
    print(fmt, m(lambda: struct.unpack(fmt, data)))  # type: ignore[no-untyped-call]
print(struct.pack("<e", 1.0), struct.pack(">e", -2.5), struct.pack("<e", 6.1e-5), struct.pack("<e", 5.9e-8), struct.pack("<e", 1e-8), struct.pack("<e", float("nan")), struct.pack("<e", float("-inf")), struct.pack("<f", 1.1), struct.pack(">f", float("nan")), struct.pack("<f", -0.0), struct.pack("<d", 0.1), struct.pack(">d", float("inf")), struct.pack("<e", 2049.0), struct.pack("<e", 2051.0), struct.pack("<e", 65504.0))
print(m(lambda: struct.pack("bb", 1)), m(lambda: struct.pack("bb", 1, 2, 3)), m(lambda: struct.unpack("bb", b"a")), m(lambda: struct.unpack("bb", "ab")), m(lambda: struct.pack(">Q", 2**64)), m(lambda: struct.pack(">h", 2**70)), m(lambda: struct.pack("<I", -1)))  # type: ignore[arg-type,no-untyped-call]
print(struct.unpack_from("<h", b"\x01\x00\x02\x00", 2), struct.unpack_from("<h", b"\x01\x00\x02\x00", offset=-2), struct.unpack_from("<h", buffer=b"\x01\x00\x02\x00"), m(lambda: struct.unpack_from("<h", b"\x01", 0)), m(lambda: struct.unpack_from("<h", b"\x01\x00\x02", -3)), m(lambda: struct.unpack_from("<h", b"\x01\x00", -1)), m(lambda: struct.unpack_from("<h", b"\x01\x00\x02", 2)), m(lambda: struct.unpack_from("<h", b"\x01\x00", 1.5)), m(lambda: struct.unpack_from("<h", b"\x01\x00", 2**70)))  # type: ignore[arg-type,no-untyped-call]
ba = bytearray(6)
struct.pack_into("<h", ba, 1, 258)
print(ba)
struct.pack_into("<h", ba, -2, 513)
print(ba)
print(m(lambda: struct.pack_into("<h", ba, 5, 1)), m(lambda: struct.pack_into("<h", ba, -1, 1)), m(lambda: struct.pack_into("<h", ba, -7, 1)), m(lambda: struct.pack_into("<h", b"ab", 0, 1)), m(lambda: struct.pack_into("<h", ba, 0)), m(lambda: struct.pack_into("<h", ba, 0, 1, 2)), m(lambda: struct.pack_into("<h", ba, "0", 1)), m(lambda: struct.pack_into("<h", ba, 0, 2**40)))  # type: ignore[arg-type,no-untyped-call]
it = struct.iter_unpack("<h", b"\x01\x00\x02\x00\x03\x00")
print(type(it).__name__, type(it).__module__, it.__length_hint__(), next(it), it.__length_hint__(), list(it), it.__length_hint__(), m(lambda: next(it)), m(lambda: struct.iter_unpack("<h", b"\x01")), m(lambda: struct.iter_unpack("", b"")), m(lambda: struct.iter_unpack("<h", "ab")), m(lambda: type(it)()))  # type: ignore[arg-type,attr-defined,no-untyped-call]
print(m(lambda: s.pack(1, 2)), m(lambda: s.pack()), m(lambda: s.pack(1, x=2)), m(lambda: s.unpack()), m(lambda: s.unpack(b"", b"")), m(lambda: s.unpack(buffer=b"")), m(lambda: s.unpack_from()), m(lambda: s.unpack_from(b"", 0, 1)), m(lambda: s.unpack_from(b"", offsett=1)), m(lambda: s.pack_into(ba)), m(lambda: s.pack_into(ba, 0)), m(lambda: s.iter_unpack()), m(lambda: s.iter_unpack(b"", 1)))  # type: ignore[call-arg,no-untyped-call]
print(m(lambda: struct.Struct()), m(lambda: struct.Struct("b", "b")), m(lambda: struct.Struct(format="b")), m(lambda: struct.Struct(fmt="b")), m(lambda: struct.Struct(1)), m(lambda: struct.Struct(None)), m(lambda: struct.Struct(b"\xff")), m(lambda: struct.Struct("b", format="b")), m(lambda: struct.Struct(b"<l").format))  # type: ignore[arg-type,call-arg,misc,no-untyped-call]
def setsize(): s.size = 1  # type: ignore[misc,no-untyped-def]
def delfmt(): del s.format  # type: ignore[no-untyped-def]
def setx(): s.x = 1  # type: ignore[attr-defined,no-untyped-def]
print(m(setsize), m(delfmt), m(setx), m(lambda: struct.pack()), m(lambda: struct.unpack("b")), m(lambda: struct.unpack("b", b"a", 1)), m(lambda: struct.unpack(fmt="b", buffer=b"a")), m(lambda: struct.calcsize()), m(lambda: struct.calcsize("b", "b")), m(lambda: struct.calcsize(format="b")), m(lambda: struct.unpack_from(format="b", buffer=b"a")), m(lambda: struct.unpack_from("b")), m(lambda: struct.pack_into("b", ba)), m(lambda: struct.iter_unpack("b")), m(lambda: struct._clearcache(1)), m(lambda: struct._clearcache()))  # type: ignore[attr-defined,call-arg,no-untyped-call]
for i in range(205):
    struct.calcsize(str(i) + "x")
print(struct.calcsize("3x"), struct.pack("3s", bytearray(b"abcd")), struct.pack("3p", bytearray(b"abcd")), struct.pack("300p", b"x" * 299)[:3], struct.pack("300p", b"x" * 299)[-1:], struct.unpack("300p", b"\xff" + b"y" * 299)[0][:3], len(struct.unpack("300p", b"\xff" + b"y" * 299)[0]))
