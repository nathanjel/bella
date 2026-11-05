# clause: C-3-37
# spec: section 3
# status: P1
# source: dialect specification section 3 (bytes, bytearray), Objects/bytesobject.c, Objects/bytearrayobject.c
"""bytes and bytearray: literals, construction, the sequence protocol, comparison, hash, repr, the
bridge to str, and their methods. `%` comes with str's, and a class derived from them is refused
until str's and list's are written (pipeline/tests/test_bytes.py)."""
# ruff: noqa: E721, B015, PLW0129, UP018, UP003, UP012  # comparing, evaluating and spelling them out is what this case is about


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


# ---- literals and repr
print(b"", b"abc", b"\x00\xff", b"a'b", b'a"b', b"a'\"b", b"\n\t\r\\", b"\x7f\x80", rb"\n", bytes(b"copy"))
print(type(b"").__name__, type(b"").__module__, type(b"").__qualname__, bytes, bytearray, type(bytearray()).__name__)
print(repr(bytearray()), repr(bytearray(b"ab'c")), str(b"x"), str(bytearray(b"x")), f"{b'y'}", f"{bytearray(b'y')!r}")  # type: ignore[str-bytes-safe]
empty, single = b"", b"a"
print(empty is bytes(), single is bytes([97]), single is b"a"[:], len(b""), len(b"abc"), len(bytearray(b"ab")))
print(bool(b""), bool(b"\x00"), bool(bytearray()), bool(bytearray(b"\x00")))


# ---- construction
class Idx:
    def __index__(self) -> int:
        return 2


class WithBytes:
    def __bytes__(self) -> bytes:
        return b"from __bytes__"


class BadBytes:
    def __bytes__(self) -> object:
        return 1


class ByteIter:
    def __iter__(self) -> object:
        return iter([65, 66])


class Seq:
    def __getitem__(self, i: int) -> int:
        if i > 1:
            raise IndexError
        return 97 + i


print(bytes(), bytes(3), bytes(0), bytes(Idx()), bytes([1, 2]), bytes((65,)), bytes(range(3)), bytes(b"x"), bytes(bytearray(b"y")))
print(bytes(WithBytes()), bytes(ByteIter()), bytes(Seq()), bytes("é", "utf-8"), bytes("é", "latin-1"), bytes("a", encoding="ascii"), bytes("é", "ascii", "ignore"), bytes("é", errors="replace", encoding="ascii"))  # type: ignore[call-overload]
print(bytes(iter([1])), bytes({1: "a"}), bytes({5}), bytes(True))
print(bytearray(), bytearray(2), bytearray([1]), bytearray(b"x"), bytearray(bytearray(b"y")), bytearray("é", "utf-8"), bytearray(Idx()), bytearray(ByteIter()), bytearray(Seq()))  # type: ignore[call-overload]
print("refused:", failed(lambda: bytes("x")), failed(lambda: bytes(-1)), failed(lambda: bytes([256])), failed(lambda: bytes([-1])), failed(lambda: bytes(["a"])), failed(lambda: bytes(None)), failed(lambda: bytes(b"x", "utf-8")), failed(lambda: bytes("x", 1)), failed(lambda: bytes(1, "utf-8")), failed(lambda: bytes(BadBytes())), failed(lambda: bytes(object())), failed(lambda: bytes(1, 2, 3, 4)))  # type: ignore[arg-type,call-overload,list-item]
print("bytearray refused:", failed(lambda: bytearray("x")), failed(lambda: bytearray(-1)), failed(lambda: bytearray([256])), failed(lambda: bytearray(None)), failed(lambda: bytearray(b"x", "utf-8")))  # type: ignore[arg-type,call-overload]


# ---- the sequence protocol
b = b"hello"
print(b[0], b[-1], b[1:3], b[::-1], b[::2], b[10:], b[:0], b[slice(1, 2)], type(b[1:3]).__name__, b[:] is b, b[Idx()])
print("index:", failed(lambda: b[5]), failed(lambda: b[-6]), failed(lambda: b["a"]), failed(lambda: b[None]))  # type: ignore[call-overload]
ba = bytearray(b"hello")
print(ba[0], ba[-1], ba[1:3], ba[::-1], type(ba[1:3]).__name__, ba[:] is ba, ba[:] == ba, ba[Idx()])
print(list(b"ab"), list(bytearray(b"ab")), [x for x in b"\x00\xff"], tuple(b"a"), set(b"aa"), type(iter(b"")).__name__, type(iter(bytearray())).__name__)
it = iter(b"ab")
print(next(it), next(it), failed(lambda: next(it)), iter(it) is it)
print(104 in b, 0 in b, b"ell" in b, b"" in b, b"x" in b, bytearray(b"ell") in b, b"ell" in ba, 104 in ba, Idx() in b"\x02", True in b"\x01")  # type: ignore[comparison-overlap]
print("in refused:", failed(lambda: "a" in b), failed(lambda: 256 in b), failed(lambda: -1 in b), failed(lambda: None in b), failed(lambda: "a" in ba))  # type: ignore[operator]
print(b + b"x", b + bytearray(b"y"), type(b + bytearray(b"y")).__name__, bytearray(b"a") + b"b", type(bytearray(b"a") + b"b").__name__, b"" + b is b, b + b"" is b)
print(b * 2, 2 * b, b * 0, b * -1, bytearray(b"a") * 2, 2 * bytearray(b"a"), b * Idx(), b * 1 is b, type(bytearray(b"a") * 1).__name__)
print("add refused:", failed(lambda: b + "x"), failed(lambda: "x" + b), failed(lambda: b + 1), failed(lambda: b * "x"), failed(lambda: b * None))  # type: ignore[operator]


# ---- in place: a new bytes, the same bytearray
x = b"a"
y = x
x += b"b"
print(x, y, x is y)
ba2 = bytearray(b"a")
ba3 = ba2
ba2 += b"b"
ba2 += bytearray(b"c")
print(ba2, ba3, ba2 is ba3)
ba2 *= 2
print(ba2, ba2 is ba3)
print("iadd refused:", failed(lambda: ba2.__iadd__("x")))  # type: ignore[arg-type]


# ---- a bytearray changes
m = bytearray(b"abcdef")
m[0] = 65
m[-1] = 70
print(m)
m[1:3] = b"XYZ"
print(m)
m[1:4] = b""
print(m)
m[::2] = b"12"
print(m)
del m[0]
print(m)
del m[0:1]
print(m)
del m[::2]
print(m)
print("store refused:", failed(lambda: m.__setitem__(0, 256)), failed(lambda: m.__setitem__(0, "a")), failed(lambda: m.__setitem__(99, 1)), failed(lambda: m.__setitem__(slice(0, 1), 5)), failed(lambda: m.__setitem__(slice(None, None, 2), b"xxxxxx")), failed(lambda: m.__delitem__(99)))  # type: ignore[call-overload]
print("bytes is immutable:", failed(lambda: b.__setitem__(0, 1)), failed(lambda: b.__delitem__(0)), hasattr(b, "__setitem__"), hasattr(ba, "__setitem__"))  # type: ignore[attr-defined,index]
print(failed(lambda: hash(bytearray())), hash(b"") == 0, hash(b"abc") == hash(bytes(b"abc")), hash(b"a") == hash("a"), {b"k": 1}[b"k"], b"k" in {b"k"}, frozenset({b"k"}) == frozenset({b"k"}))
n = bytearray()
n.append(65)
n.append(True)
n.extend(b"xy")
n.extend([66])
n.extend(bytearray(b"z"))
n.insert(0, 67)
print(n, n.pop(), n.pop(0), n)
n.clear()
print(n, n.copy() is not n, failed(lambda: n.pop()), failed(lambda: n.append(256)), failed(lambda: n.append("a")), failed(lambda: n.extend("a")), failed(lambda: n.extend([256])))  # type: ignore[arg-type]
v = bytearray(b"abca")
v.remove(97)
print(v)
v.reverse()
print(v, failed(lambda: v.remove(0)))


# ---- comparison
print(b"a" == b"a", b"a" != b"b", b"a" < b"b", b"a" <= b"a", b"b" > b"a", b"a" >= b"b", b"ab" > b"a", b"" < b"a")  # type: ignore[comparison-overlap]
print(b"a" == bytearray(b"a"), bytearray(b"a") == b"a", bytearray(b"a") == bytearray(b"a"), bytearray(b"a") < b"b", b"a" < bytearray(b"b"), bytearray(b"a") != b"a")
print(b"a" == "a", "a" == b"a", b"a" == 97, b"a" != "a", bytearray(b"a") == "a", b"a" == [97], b"\xff" > b"\x00")  # type: ignore[comparison-overlap]
print("order refused:", failed(lambda: b"a" < "a"), failed(lambda: "a" < b"a"), failed(lambda: b"a" < 1), failed(lambda: bytearray(b"a") < "a"), failed(lambda: bytearray(b"a") < 1))  # type: ignore[operator]


# ---- the bridge to str
print("é€😀".encode(), "é".encode("utf-8"), "é".encode("latin-1"), "abc".encode("ascii"), "é".encode("ascii", "ignore"), "é".encode("ascii", "replace"), "é".encode(errors="strict", encoding="utf-8"), "".encode())
print("é".encode("ascii", "backslashreplace"), "é".encode("ascii", "xmlcharrefreplace"), "\udc80".encode("utf-8", "surrogateescape"), "\udc80".encode("utf-8", "surrogatepass"), "\udc80".encode("utf-8", "ignore"), "\udc80".encode("utf-8", "replace"))
print(b"\xc3\xa9".decode(), b"\xc3\xa9".decode("utf-8"), b"\xe9".decode("latin-1"), b"abc".decode("ascii"), bytearray(b"\xc3\xa9").decode(), b"\xff".decode("utf-8", "ignore"), b"\xff".decode("utf-8", "replace"), repr(b"\xff".decode("utf-8", "surrogateescape")), b"\xff".decode("ascii", "backslashreplace"), b"".decode())
print(b"a".decode(encoding="utf-8", errors="strict"), b"a".decode("UTF-8"), b"a".decode("utf8"), b"a".decode("UTF_8"), b"a".decode("ascii"), b"a".decode("us-ascii"), b"a".decode("latin1"), b"a".decode("iso-8859-1"), "a".encode("U8"))
print("codec errors:", failed(lambda: "é".encode("ascii")), failed(lambda: "é".encode("nosuch")), failed(lambda: "é".encode("ascii", "nosuch")), failed(lambda: b"\xff".decode()), failed(lambda: b"\xff".decode("ascii")), failed(lambda: b"a".decode("nosuch")), failed(lambda: "\udc80".encode()))
try:
    b"a\xffb".decode()
except UnicodeDecodeError as e:
    print(e.encoding, e.object, e.start, e.end, e.reason, e.args[0], isinstance(e, ValueError))
try:
    "aéb".encode("ascii")
except UnicodeEncodeError as e:
    print(e.encoding, e.object, e.start, e.end, e.reason, isinstance(e, ValueError))


# ---- methods
print(b"a,b".split(b","), b" a  b ".split(), b"a,b,c".split(b",", 1), b"a b".rsplit(), b"a,b,c".rsplit(b",", 1), b"a\nb\r\nc".splitlines(), b"a\nb".splitlines(True), bytearray(b"a,b").split(b","), type(bytearray(b"a,b").split(b",")[0]).__name__)
print(b"-".join([b"a", b"b"]), b"".join([]), b"-".join([bytearray(b"a")]), bytearray(b"-").join([b"a", b"b"]), type(bytearray(b"-").join([b"a"])).__name__, b"".join((b"x",)), b"x".join(iter([b"a", b"b"])), failed(lambda: b"".join(["a"])), failed(lambda: b"".join([1])), failed(lambda: b"".join(1)))  # type: ignore[arg-type,list-item]
print(b"abcabc".find(b"c"), b"abcabc".rfind(b"c"), b"abc".find(b"z"), b"abc".find(98), b"abcabc".find(b"a", 1), b"abcabc".find(b"a", 1, 2), b"abc".index(b"b"), b"abcb".rindex(b"b"), b"aaa".count(b"a"), b"aaa".count(b""), b"aba".count(97), failed(lambda: b"abc".index(b"z")), failed(lambda: b"a".find("a")), failed(lambda: b"a".find(256)))  # type: ignore[arg-type]
print(b"abc".startswith(b"a"), b"abc".endswith(b"c"), b"abc".startswith((b"x", b"a")), b"abc".endswith((b"x",)), b"abc".startswith(b"b", 1), b"abc".endswith(b"b", 0, 2), bytearray(b"a").startswith(b"a"), failed(lambda: b"a".startswith("a")), failed(lambda: b"a".endswith(97)))  # type: ignore[arg-type]
print(b" a ".strip(), b" a ".lstrip(), b" a ".rstrip(), b"xax".strip(b"x"), b"xax".lstrip(b"x"), b"xax".rstrip(b"x"), bytearray(b" a ").strip(), b"\t\n\r\x0b\x0c a".lstrip(), failed(lambda: b"a".strip("a")))  # type: ignore[arg-type]
print(b"aXb".lower(), b"aXb".upper(), b"aXb".swapcase(), b"ab cd".title(), b"aB".capitalize(), bytearray(b"a").upper(), b"\xc9".lower())
print(b"a1".isalnum(), b"a".isalpha(), b"1".isdigit(), b"a".islower(), b"A".isupper(), b" ".isspace(), b"A".istitle(), b"\x7f".isascii(), b"\x80".isascii(), b"".isalpha(), b"".isascii())
print(b"aba".replace(b"a", b"x"), b"aba".replace(b"a", b"x", 1), b"ab".replace(b"", b"-"), b"aba".removeprefix(b"a"), b"aba".removesuffix(b"a"), b"a".center(3), b"a".ljust(3, b"-"), b"a".rjust(3), b"5".zfill(3), b"-5".zfill(3), b"a\tb".expandtabs(4))
print(b"a,b".partition(b","), b"a,b,c".rpartition(b","), b"ab".partition(b","), bytearray(b"a,b").partition(b","), b"a".hex(), b"\xab\xcd".hex(), b"\xab\xcd".hex("-"), b"\xab\xcd\xef".hex(":", 2), bytes.fromhex("ab cd"), bytearray.fromhex("ab"), failed(lambda: bytes.fromhex("a")), failed(lambda: bytes.fromhex("zz")))
print(b"abc".translate(bytes(range(256))), b"abc".translate(None, b"b"), bytes.maketrans(b"a", b"b")[97], b"abc".translate(bytes.maketrans(b"a", b"x")))


# ---- their special methods, read and called
class Dunder:
    def __bytes__(self) -> bytes:
        return b"d"


print(bytes(Dunder()), bytes.__name__, bytes.__mro__[1].__name__, bytearray.__mro__[1].__name__, isinstance(b"", object), issubclass(bytes, object), bytes.__doc__[:5], bytearray.__doc__[:9])  # type: ignore[index]
print(b"a".__class__ is bytes, bytes.__add__(b"a", b"b"), bytes.__len__(b"a"), b"a".__len__(), b"a".__add__(b"b"), b"a".__eq__(b"a"), b"a".__eq__(1), b"a".__ne__(b"a"), b"a".__lt__(1), b"a".__contains__(97), b"a".__getitem__(0), b"a".__mul__(2), b"a".__rmul__(2), b"a".__hash__() == hash(b"a"), b"a".__repr__(), b"a".__str__(), b"a".__bytes__(), type(b"a".__iter__()).__name__, b"a".__getnewargs__())  # type: ignore[operator]
print(failed(lambda: bytes.__add__("a", b"b")), failed(lambda: b"a".__add__(1)), failed(lambda: b"a".__mul__("x")), failed(lambda: setattr(b"", "x", 1)), failed(lambda: setattr(bytes, "x", 1)), failed(lambda: b"".nothing))  # type: ignore[attr-defined,operator]
print(ord(b"a"), ord(bytearray(b"a")), failed(lambda: ord(b"ab")), chr(97).encode(), int(b"12"), int(bytearray(b"12")), int(b"ff", 16), failed(lambda: int(b"x")))
