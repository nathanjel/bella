# clause: C-3-64
# spec: section 3 (classes: a subclass of a built-in type), section 6 (bytes, bytearray)
# status: P1
# source: Objects/bytesobject.c (CPython 3.15.2: bytes_new, bytes_subtype_new, bytes_repr, bytes___getnewargs__),
#         Objects/bytearrayobject.c (bytearray_init, bytearray_repr, bytearray_reduce_ex), Objects/typeobject.c (__slots__ of a
#         variable-size base, the dict and weak reference a subclass gets)
"""A subclass of bytes or of bytearray holds the base's data and attributes beside it. bytes has an item size, so its subclass
gets a __dict__ but no weak reference and no slots of its own; bytearray's gets all three. Their methods, slices and
operators make the base type; a bytes subclass's repr is a bytes literal, a bytearray subclass's names the class; copy and
pickle's reductions keep the subclass; what the program overrides is what iteration, len(), in, hashing and the operators
ask."""
import copy
import weakref
from collections.abc import Iterator


class Name(bytes):
    def __new__(cls, text: str) -> "Name":  # noqa: UP037
        return super().__new__(cls, text.encode("ascii"))

    def shout(self) -> bytes:
        return self.upper()


class Buffer(bytearray):
    __slots__ = ("note", "__dict__", "__weakref__")
    note: str


class Plain(bytes):
    pass


class Odd(bytes):
    def __iter__(self) -> Iterator[int]:
        return iter([0])

    def __len__(self) -> int:
        return 99

    def __contains__(self, item: object) -> bool:
        return True

    def __hash__(self) -> int:
        return 5

    def __add__(self, other: object) -> str:  # type: ignore[override]
        return "Odd.__add__"


n = Name("ab")
n.tag = "t"  # type: ignore[attr-defined]
print("name:", n, type(n).__name__, n.tag, vars(n), isinstance(n, bytes), len(n), n[0], n == b"ab", hash(n) == hash(b"ab"))  # type: ignore[attr-defined]
print("methods make bytes:", type(n.upper()).__name__, type(n + b"c").__name__, type(n[0:1]).__name__, type(n * 2).__name__,
      type(n.replace(b"a", b"z")).__name__, type(n.shout()).__name__, type(bytes(n)).__name__, bytes(n) is n)
print("repr:", repr(n), repr(Plain()), repr(Plain(b"x")), str(Plain(b"q")))
print("no weak reference:", "__weakref__" in vars(Name), "__dict__" in vars(Name))
try:
    weakref.ref(n)
except TypeError as e:
    print("weakref refused:", type(e).__name__)
try:
    type("Slots", (bytes,), {"__slots__": ("x",)})
except TypeError as e:
    print("slots refused:", type(e).__name__)
b = Buffer(b"xy")
b.note = "slot"
b.extra = 1  # type: ignore[attr-defined]
b.append(122)
b += b"!"
print("buffer:", bytes(b), type(b).__name__, b.note, vars(b), len(b), weakref.ref(b)() is b)
print("buffer methods make bytearrays:", type(b.upper()).__name__, type(b + b"x").__name__, type(b[0:1]).__name__, type(b.copy()).__name__,
      type(b * 2).__name__)
print("buffer repr:", repr(b), repr(Buffer()))
o = Odd(b"abc")
print("odd:", list(o), len(o), 7 in o, hash(o), o + b"x", b"x" + o, bytes(o), o == b"abc", o.decode(), o.upper())
p = Plain(b"pq")
p.tag = "kept"  # type: ignore[attr-defined]
c = copy.copy(p)
print("copy of a bytes subclass:", type(c).__name__, c, c is not p, getattr(c, "tag", None))
d = copy.deepcopy(b)
print("copy of a bytearray subclass:", type(d).__name__, bytes(d), d.note if hasattr(d, "note") else "no note", vars(d))
print("newargs:", n.__getnewargs__(), Plain(b"pq").__getnewargs__())
print("join and in:", b"-".join([Plain(b"a"), Buffer(b"b")]), Plain(b"a") in [b"a"], Plain(b"abc").__contains__(b"a"), b"abc".__contains__(Plain(b"b")))
print("mro:", [k.__name__ for k in Name.__mro__], [k.__name__ for k in Buffer.__mro__])
