"""int beyond the immediates, compiled, against CPython.

Case C-6-10 shows the behaviour by exception class, as a case must; these compare messages too, and
drive the arithmetic with numbers the program draws itself: every operator on every size where bn
changes algorithm (schoolbook, Karatsuba, Knuth, Barrett, the decimal divide and conquer), every
range whose bounds sit at the edges of the immediates and of 64 bits, and text in every base.
"""
from __future__ import annotations

from typing import Any

from pipeline.tests.test_review_2026_11_03 import same

DRAW = """MASK = 2**64 - 1
state = 88172645463325252
def word():
    global state
    state ^= (state << 13) & MASK
    state ^= state >> 7
    state ^= (state << 17) & MASK
    return state
def number(limbs):
    n = 0
    for _ in range(limbs):
        n = (n << 64) | word()
    kind = word() % 8
    if kind == 0:
        n >>= word() % 64
    elif kind == 1:
        n = (1 << (64 * limbs)) - 1 - word() % 2
    elif kind == 2:
        n = 1 << (word() % (64 * limbs))
    elif kind == 3:
        n = (1 << (64 * limbs - 1)) + word() % 3
    elif kind == 4:
        n = (n >> 64) << 64
    return -n if word() & 1 else n
P = 2**127 - 1
def d(x):
    return x if -(2**400) < x < 2**400 else (x % P, x.bit_length())
"""

SHOW = """def show(f):
    try:
        print(repr(f()))
    except Exception as e:
        print(type(e).__name__, e)
"""

EDGES = """EDGES = [0, 1, -1, 3, -7, 2**62 - 1, 2**62, 2**62 + 1, -(2**62), -(2**62) - 1, 2**63 - 1, 2**63, 2**63 + 1, -(2**63), -(2**63) - 1, 2**64 - 1, 2**64, 2**64 + 1, -(2**64), 2**65, 2**125, -(2**126)]
"""


def _arith(pairs: str, rounds: int) -> str:
    return DRAW + f"""for la, lb in {pairs}:
    for _ in range({rounds}):
        a, b = number(la), number(lb)
        print(d(a + b), d(a - b), d(b - a), d(a * b), d(a * a))
        if b:
            q, r = divmod(a, b)
            print(d(a // b), d(a % b), d(q), d(r), q * b + r == a)
        if a:
            print(d(b // a), d(b % a))
        print(d(a & b), d(a | b), d(a ^ b), d(~a), d(-a), d(abs(a)))
        print(a == b, a != b, a < b, a <= b, a > b, a >= b, a == a, hash(a), hash(b), a.bit_length(), a.bit_count())
"""


PROGRAMS: list[tuple[str, str]] = [
    ('immediates_meeting_big_ints', EDGES + """for a in EDGES:
    for b in EDGES:
        print(a + b, a - b, a * b, a & b, a | b, a ^ b, a < b, a == b)
        if b:
            print(a // b, a % b, divmod(a, b))
        if 0 <= b < 200:
            print(a << b, a >> b)
    print(-a, abs(a), ~a, +a, hash(a), bool(a), a.bit_length(), a.bit_count(), str(a), hex(a), oct(a), bin(a), int(str(a)), int(hex(a), 16))
"""),
    ('arithmetic_on_small_sizes', _arith("[(1, 1), (1, 2), (2, 1), (2, 2), (3, 1), (3, 2), (5, 3), (8, 8), (20, 7)]", 60)),
    ('arithmetic_past_karatsuba', _arith("[(33, 33), (40, 70), (70, 40), (100, 100), (64, 32), (170, 165), (330, 165)]", 12)),
    ('arithmetic_past_barrett', _arith("[(3000, 1500), (5200, 2600), (5300, 2570)]", 3)),
    ('powers', DRAW + """for limbs in (1, 2, 3, 5, 9):
    for _ in range(12):
        a = number(limbs)
        print(d(a ** 2), d(a ** 3), d(a ** 7), d(a ** 16), d(a ** 0), d(a ** 1))
        m = number(limbs)
        e = abs(number(limbs))
        if m:
            print(pow(a, e, m), pow(a, 5, m), pow(a, 0, m), pow(2, e, m), pow(a, e, -m))
print(0 ** 0, 0 ** 5, 1 ** 2**70, (-1) ** 2**70, (-1) ** (2**70 + 1), 0 ** 2**70, (-2) ** 63, (-2) ** 64, 2 ** 62, 2 ** 63, 3 ** 39, 3 ** 40, (-3) ** 39, (-3) ** 40)
"""),
    ('modular_inverses', SHOW + DRAW + """for limbs in (1, 2, 4):
    for _ in range(40):
        a, m = number(limbs), number(limbs)
        if m:
            show(lambda: pow(a, -1, m))
            show(lambda: pow(a, -3, m))
for args in ((2, -1, 4), (0, -1, 5), (2, -1, 1), (2, -1, -1), (0, -1, 1), (3, -1, 7), (3, -1, -7), (-3, -1, 7), (2, 3, 0), (2**70, -1, 2**70 + 1), (2, -5, 2**70 + 1)):
    show(lambda: pow(*args))
"""),
    ('shifts_and_their_ends', SHOW + DRAW + """for limbs in (1, 2, 3, 7):
    for _ in range(30):
        a, n = number(limbs), word() % 400
        print(d(a << n), d(a >> n), d(a >> (n + 64 * limbs)), (a << n) >> n == a)
for f in (lambda: 1 << -1, lambda: 1 >> -1, lambda: 2**64 << -1, lambda: 2**64 >> -(2**64), lambda: 0 << 2**70, lambda: 0 >> 2**70, lambda: 1 >> 2**70, lambda: -1 >> 2**70, lambda: 2**64 >> 2**70, lambda: -(2**64) >> 2**70, lambda: 1 << 2**70, lambda: 1 << 2**64, lambda: -1 << 2**63, lambda: 1 << 2**80, lambda: 2**64 << 2**64):
    show(f)
"""),
    ('text_in_every_base', SHOW + DRAW + """DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"
for base in range(2, 37):
    for size in (1, 5, 12, 13, 20, 60, 300):
        text = "".join([DIGITS[word() % base] for _ in range(size)])
        for t in (text, "-" + text, " +" + text + " ", "0" * 30 + text):
            print(d(int(t, base)))
for t, base in (("0x" + "f" * 40, 16), ("0X" + "F" * 40, 0), ("0o" + "7" * 40, 8), ("0O" + "7" * 40, 0), ("0b" + "1" * 90, 2), ("0B" + "1" * 90, 0), ("1_000" * 10, 10), ("0x_ff_" + "f" * 30, 16), ("0" * 40, 0), ("0_0" * 20, 0), ("-0" * 1, 10)):
    show(lambda: int(t, base))
for t, base in (("1" * 40 + "x", 10), ("0x" + "f" * 40, 10), ("9" * 40, 8), ("1_" * 30, 10), ("__1" + "1" * 30, 10), ("0" * 39 + "1", 0), ("1" * 40, 1), ("1" * 40, 37), ("1" * 40, 2**64), ("1" * 40, -(2**64)), (b"1" * 40, 10), (b"x" * 40, 16), (bytearray(b"1" * 40), 16)):
    show(lambda: int(t, base))
for limbs in (1, 2, 3, 9, 40):
    for _ in range(12):
        a = number(limbs)
        for f in (hex, oct, bin):
            print(f(a), int(f(a), 0) == a)
        print(int(str(a)) == a)
print(hex(True), bin(False), oct(True), hex(-1), bin(-1), oct(-1), hex(2**62), hex(-(2**62)), bin(2**64), oct(2**64))
"""),
    ('the_limit_of_digits', SHOW + DRAW + """import sys
print(sys.get_int_max_str_digits(), sys.maxsize)
show(lambda: str(10**4299)[:5])
show(lambda: str(10**4300))
show(lambda: repr(-(10**4300)))
show(lambda: f"{10**4300}")
show(lambda: int("1" * 4300) % 97)
show(lambda: int("1" * 4301))
show(lambda: int("1" * 4300 + "_1"))
show(lambda: int("-" + "1" * 4301))
show(lambda: int("0" * 4301))
show(lambda: int(b"1" * 4301))
show(lambda: int("1" * 4301, 3))
show(lambda: int("1" * 4301, 36))
show(lambda: int("1" * 4301, 16) % 97)
show(lambda: int("1" * 4301, 32) % 97)
show(lambda: int("1" * 640) % 97)
for bad in (639, 1, -1, -(2**70), 2**31, 2**70, "a", None):
    show(lambda: sys.set_int_max_str_digits(bad))
show(lambda: sys.set_int_max_str_digits())
show(lambda: sys.set_int_max_str_digits(640, 640))
show(lambda: sys.set_int_max_str_digits(maxdigits=640))
print(sys.get_int_max_str_digits())
show(lambda: len(str(10**639)))
show(lambda: str(10**640))
show(lambda: int("1" * 640) % 97)
show(lambda: int("1" * 641))
sys.set_int_max_str_digits(0)
print(sys.get_int_max_str_digits())
for limbs in (300, 1000, 4000, 9000):
    a = number(limbs)
    t = str(a)
    print(len(t), t[:40], t[-40:], int(t) == a)
print(len(str(10**100000)), str(10**100000)[:5], len(str(10**100000 - 1)), str(10**100000 - 1)[-5:], int("1" + "0" * 100000) == 10**100000)
sys.set_int_max_str_digits(4300)
show(lambda: str(10**4300))
"""),
    ('messages', SHOW + """big = 2**64
class I:
    def __index__(self):
        return 2**64
class Neg:
    def __index__(self):
        return -(2**64)
class L:
    def __init__(self, v):
        self.v = v
    def __len__(self):
        return self.v
class H:
    def __init__(self, v):
        self.v = v
    def __hash__(self):
        return self.v
    def __eq__(self, other):
        return True
class Hint:
    def __init__(self, v):
        self.v = v
    def __iter__(self):
        return iter(())
    def __length_hint__(self):
        return self.v
items = [1, 2, 3]
for f in (lambda: big // 0, lambda: big % 0, lambda: divmod(big, 0), lambda: 1 // (big - big), lambda: 0 ** -1, lambda: 0 ** -big, lambda: big + "a", lambda: "a" + big, lambda: big < "a", lambda: big @ 1, lambda: 1 @ big, lambda: -"a",
          lambda: items[big], lambda: items[-big], lambda: "abc"[big], lambda: (1,)[big], lambda: b"a"[big], lambda: bytearray(b"a")[big], lambda: range(3)[big], lambda: range(3)[-big], lambda: range(3)["a"], lambda: range(3)[I()], lambda: items[I()], lambda: items[Neg()],
          lambda: items * big, lambda: "a" * big, lambda: (1,) * big, lambda: b"a" * big, lambda: bytearray(b"a") * big, lambda: big * "a", lambda: big * [1], lambda: items * I(), lambda: items.__mul__(big), lambda: "a".__mul__(big), lambda: (1,).__rmul__(big),
          lambda: chr(big), lambda: chr(-big), lambda: chr(I()), lambda: bytes(big), lambda: bytes(-big), lambda: bytes(I()), lambda: bytearray(big), lambda: bytes([big]), lambda: bytes([-big]), lambda: bytearray([big]),
          lambda: items.pop(big), lambda: items.insert(big, 1), lambda: "a b".split(None, big), lambda: "aaa".replace("a", "b", big), lambda: b"a".center(big), lambda: b"a".ljust(big), lambda: bytearray(b"a").pop(big), lambda: bytearray(b"a").insert(big, 1), lambda: b"a".expandtabs(big), lambda: b"a".hex("-", big), lambda: b"a b".split(None, big), lambda: b"a".replace(b"a", b"b", big),
          lambda: len(L(big)), lambda: len(L(-big)), lambda: len(L(2**63)), lambda: len(L(2**63 - 1)), lambda: bool(L(big)), lambda: bool(L(-big)), lambda: bool(L(2**63 - 1)),
          lambda: list(Hint(big)), lambda: list(Hint(-big)), lambda: list(Hint(2**63 - 1)) if False else 0,
          lambda: hash(H(big)) == hash(big), lambda: hash(H(2**63 - 1)), lambda: hash(H(-(2**63))), lambda: hash(H(-(2**63) - 1)) == hash(-(2**63) - 1), lambda: hash(H(2**63)) == hash(2**63), lambda: hash(H(-1)), lambda: hash(H(True)), lambda: hash(H(2**61 - 1)),
          lambda: hex("a"), lambda: bin(None), lambda: oct(1, 2), lambda: hex(), lambda: hex(I()), lambda: bin(Neg()),
          lambda: divmod(), lambda: divmod(1), lambda: divmod(1, 2, 3), lambda: divmod(1, "a"), lambda: divmod("a", 1), lambda: divmod(big, "a"), lambda: divmod("a", big), lambda: divmod(x=1, y=2),
          lambda: pow(), lambda: pow(1), lambda: pow(1, 2, 3, 4), lambda: pow(1, "a"), lambda: pow("a", 1), lambda: pow(1, 2, "a"), lambda: pow(1, "a", 3), lambda: pow("a", 2, 3), lambda: pow(1, 2, base=3), lambda: pow(exp=2), lambda: pow(base=2),
          lambda: round(), lambda: round("a"), lambda: round(None), lambda: round(1, 2, 3), lambda: round(5, "a"), lambda: round(5, None), lambda: round(number=5), lambda: round(ndigits=2), lambda: round(5, 2, number=3), lambda: (5).__round__("a"), lambda: (5).__round__(1, 2), lambda: (5).__round__(x=2),
          lambda: (5).to_bytes(-1), lambda: (5).to_bytes(1, "x"), lambda: (5).to_bytes(1, 5), lambda: (-5).to_bytes(1), lambda: (300).to_bytes(1), lambda: (128).to_bytes(1, signed=True), lambda: (-129).to_bytes(1, signed=True), lambda: (5).to_bytes(big), lambda: (5).to_bytes(1, "big", True), lambda: (5).to_bytes(1, "big", signed=None), lambda: (0).to_bytes(0), lambda: (-1).to_bytes(0, signed=True), lambda: (1).to_bytes(0), lambda: (5).to_bytes(length=2, byteorder="little"), lambda: (-128).to_bytes(1, signed=True), lambda: (127).to_bytes(1, signed=True), lambda: (255).to_bytes(),
          lambda: int.from_bytes(), lambda: int.from_bytes(5), lambda: int.from_bytes(b"a", "x"), lambda: int.from_bytes(b"a", 5), lambda: int.from_bytes(b"\\xff"), lambda: int.from_bytes(b"\\xff", signed=True), lambda: int.from_bytes(b""), lambda: int.from_bytes(b"", signed=True), lambda: int.from_bytes([1, 2]), lambda: int.from_bytes(bytearray(b"ab"), "little"), lambda: bool.from_bytes(b"\\x01"), lambda: int.from_bytes(b"a", "big", True), lambda: int.from_bytes(bytes=b"a", byteorder="little", signed=True), lambda: int.from_bytes(b"\\x80" + b"\\x00" * 8, signed=True), lambda: int.from_bytes(b"\\x00" * 8 + b"\\x80", "little", signed=True), lambda: int.from_bytes(b"\\xff" * 16, signed=True),
          lambda: (5).bit_length(1), lambda: (5).bit_count(1), lambda: (5).conjugate(1), lambda: (5).is_integer(1), lambda: (5).as_integer_ratio(), lambda: (2**64).as_integer_ratio(), lambda: (5).__getnewargs__(), lambda: (2**64).__getnewargs__(), lambda: (5).real, lambda: True.real, lambda: True.imag, lambda: True.numerator, lambda: True.denominator, lambda: True.conjugate(), lambda: True.bit_length(), lambda: True.to_bytes(), lambda: type(True.real).__name__, lambda: int.real, lambda: type(int.__dict__["real"]).__name__,
          lambda: range(big, big + 1, 0), lambda: range(1, 2, 3, 4), lambda: range(), lambda: range("a"), lambda: range(1, "a"), lambda: range(1, 2, "a"), lambda: range(2**70, 2**70 + 3).index(5), lambda: range(2**70, 2**70 + 3).index(2**70 + 9), lambda: len(range(big)), lambda: len(range(2**63)), lambda: len(range(0, 2**64, 2)), lambda: range(3)[1:"a"], lambda: range(3)[::0], lambda: slice(1).indices(-1), lambda: slice(1).indices("a"), lambda: slice("a").indices(1), lambda: slice(0, 1, 0).indices(1), lambda: slice(0, 1, 2).indices(), lambda: slice(1, None, 2**70).indices(2**70),
          lambda: [1].index(1, big), lambda: [1].index(1, -big), lambda: [1].index(1, 0, big), lambda: "a".find("a", big), lambda: "a".find("a", -big), lambda: "a".index("a", 0, big), lambda: b"a".find(b"a", big), lambda: b"a".find(big), lambda: b"a".count(-big), lambda: big in b"a", lambda: -big in b"a", lambda: big in bytearray(b"a"), lambda: big in "a"):
    show(f)
"""),
    ('builtins_are_what_they_are', SHOW + """import builtins, sys
for n in ("bin", "oct", "hex", "divmod", "pow", "round"):
    f = getattr(builtins, n)
    print(n, type(f).__name__, f.__name__, f.__qualname__, f.__module__, callable(f))
for n in ("set_int_max_str_digits", "get_int_max_str_digits"):
    f = getattr(sys, n)
    print(n, type(f).__name__, f.__name__, f.__module__)
print(type((5).bit_length).__name__, (5).bit_length.__name__, (5).bit_length.__self__, int.bit_length(5), type(int.from_bytes).__name__, int.from_bytes.__name__, int.from_bytes.__self__ is int, type((1).__round__).__name__, int.__round__(15, -1), slice(1).indices.__self__, type(slice(1).indices).__name__)
print(dir(5) == dir(2**64), dir(int) == dir(2**64), "bit_length" in dir(5), "real" in dir(True), type(iter(range(2**64))).__name__, dir(iter(range(2**64))) == dir(type(iter(range(2**64)))), iter(range(2**64)).__class__.__mro__ == (type(iter(range(2**64))), object))
print(iter(iter(range(2**64))) is not None, int.real, int.imag, range.start, slice.step, type(int.real).__name__, type(range.stop).__name__, type(slice.start).__name__)
it = iter(range(2**64, 2**64 + 2))
print(iter(it) is it, next(it), next(it), next(it, "end"), next(it, "end"))
"""),
    ('ranges_at_the_edges', SHOW + """VALUES = [0, 1, -1, 7, -7, 2**62 - 1, 2**62, -(2**62), -(2**62) - 1, 2**63 - 1, 2**63, -(2**63), -(2**63) - 1, 2**64, -(2**64), 2**64 + 5]
STEPS = [1, -1, 2, -2, 3, -3, 2**61, -(2**61), 2**62, -(2**62), 2**63 - 1, -(2**63), -(2**63) + 1, 2**63, 2**64, -(2**64)]
def first(it, n=3):
    out = []
    for v in it:
        out.append(v)
        if len(out) == n:
            break
    return out
for a in VALUES:
    for b in VALUES:
        for c in STEPS:
            r = range(a, b, c)
            n = 0
            for v in (r.start, r.stop, r.step):
                n += hash(v) & 1
            try:
                size = len(r)
            except OverflowError:
                size = "long"
            print(a, b, c, r, size, bool(r), hash(r), type(iter(r)).__name__, first(r), type(reversed(r)).__name__, first(reversed(r)))
            if r:
                print(r[0], r[-1], a in r, b in r, a + c in r, r.count(a), r.index(a), r[1:3], r[::-1], r[::2], r[:2**70], r[-(2**70):], r == r[::1], r == range(a, b, c), r != r[1:], hash(r[::1]) == hash(r))
"""),
    ('ranges_compare_by_their_values', """print(range(0) == range(5, 1), range(2**70, 0) == range(0), range(0, 2**64, 2**64) == range(0, 5, 100), range(0, 2**64, 2**65) == range(1), hash(range(2**70, 0)) == hash(range(0)), hash(range(0, 2**64, 2**64)) == hash(range(0, 5, 100)), range(1, 2**70, 2) == range(1, 2**70 + 1, 2), range(1, 2**70, 2) != range(1, 2**70 - 1, 2), {range(2**70): 1}[range(2**70)], range(2**70) in {range(2**70)})
for r in (range(2**70), range(-(2**70), 2**70, 2**69), range(2**70, -(2**70), -(2**69)), range(5, 2**70), range(2**70, 5)):
    print(r, r.start, r.stop, r.step, bool(r), r[:3], r[-3:], r[::2**68], r[1:], r[:-1], 5 in r, 2**69 in r, r.count(5), hash(r), type(iter(r)).__name__, type(reversed(r)).__name__)
    it = iter(r)
    print(next(it, None), next(it, None), next(it, None))
    rv = reversed(r)
    print(next(rv, None), next(rv, None))
total = 0
for i in range(2**64, 2**64 + 100, 7):
    total += i
print(total, sum(range(2**70, 2**70 + 5)), list(range(2**70, 2**70 + 3)), [i for i in range(-(2**70), -(2**70) + 3)], tuple(range(2**70, 2**70 - 3, -1)), set(range(2**70, 2**70 + 2)) == {2**70, 2**70 + 1}, dict.fromkeys(range(2**70, 2**70 + 1)) if False else 0, list(zip(range(2**70, 2**70 + 2), "ab")), list(enumerate(range(2**70, 2**70 + 2))), min(range(2**70, 2**70 + 3)), max(range(2**70, 2**70 + 3)), sorted(range(2**70, 2**70 + 3), reverse=True))
"""),
    ('a_subclass_holds_a_big_value', SHOW + """class B(int):
    def __repr__(self):
        return "B(" + int.__repr__(self) + ")"
class Plain(int):
    pass
class R(int):
    def __radd__(self, other):
        return ("radd", other)
    def __rmul__(self, other):
        return ("rmul", other)
    def __lt__(self, other):
        return "lt"
    def __gt__(self, other):
        return "gt"
class Own(int):
    def __neg__(self):
        return "neg"
    def __pos__(self):
        return "pos"
    def __invert__(self):
        return "invert"
    def __abs__(self):
        return "abs"
    def __bool__(self):
        return False
    def __index__(self):
        return 1
    def __int__(self):
        return 2
    def __hash__(self):
        return 3
    def __str__(self):
        return "str"
    def __add__(self, other):
        return "add"
big = 2**64
for c in (B, Plain):
    x = c(big)
    print(x, repr(x), str(x), f"{x}", x + 1, 1 + x, x - 1, x * 2, x // 3, x % 3, x ** 2, x << 1, x >> 1, x & 3, x | 3, x ^ 3, -x, +x, ~x, abs(x), hash(x) == hash(big), int(x), bool(x), x == big, big == x, x != big, x < big, x <= big, x > 1, 1 < x, len(str(x)))
    print(type(x + 1).__name__, type(-x).__name__, type(+x).__name__, type(abs(x)).__name__, type(~x).__name__, type(int(x)).__name__, type(x).__name__, isinstance(x, int), type(x).__mro__[1].__name__, x.real, x.imag, x.numerator, x.denominator, x.conjugate(), x.bit_length(), x.bit_count(), x.is_integer(), x.to_bytes(9), x.__index__(), x.__int__(), x.__round__(), x.__round__(-1), x.__floor__(), x.__ceil__(), x.__trunc__(), x.__neg__(), x.__pos__(), x.__abs__(), x.__invert__(), x.__bool__(), x.as_integer_ratio(), x.__getnewargs__())
    print(c(big + 1) == big + 1, {x: 1}[big], big in {x}, {big: 2}[x], [1, 2, 3][x:], [1, 2, 3][:x], "abc"[x:], hex(x), bin(x), oct(x), divmod(x, 3), pow(x, 2, 7), pow(2, x, 7), round(x), round(x, -2), str(x)[:3], list(range(x, x + 2)), range(x).stop, type(range(x).stop).__name__, sorted([x, 1, 2**70]), max(x, 1), min(x, 1), sum([x, x]))
    x.tag = "t"
    print(x.tag, x.__dict__, c("123456789012345678901234567890"), c(b"ffffffffffffffffffffffff", 16), c(), c(0), c(big - big), c(-big), c(big) + c(big), c(big) * c(big), -c(-big))
    show(lambda: [1][x])
    show(lambda: [1] * x)
    show(lambda: "a" * x)
    show(lambda: chr(x))
    show(lambda: bytes(x))
print(big + R(1), R(1) + big, 2 * R(big), R(big) * 2, big < R(1), R(1) < big, big > R(1), R(big) < 1, big + R(big), R(big) + big, 1 + R(big), R(big) + 1)
o = Own(big)
show(lambda: [1, 2, 3][o])
show(lambda: "ab" * o)
print(-o, +o, ~o, abs(o), bool(o), not o, o and 1, o or 1, hash(o), str(o), repr(o), f"{o}", int(o), o + 1, 1 + o, o - 1, hex(o), range(o), o.__index__(), int.__index__(o), int.__int__(o), int.__neg__(o), int.__add__(o, 1), int.__bool__(o), int.__hash__(o) == hash(big), int.__repr__(o), int.__abs__(o), int.__invert__(o), {o: 1}[3] if False else 0)
class Bad(int):
    def __new__(cls, v):
        return int.__new__(cls, v * 2)
print(Bad(2**64), type(Bad(2**64)).__name__, Bad(2), int.__new__(Plain, 2**70), type(int.__new__(Plain, 2**70)).__name__, int.__new__(int, 2**70), type(int.__new__(int, 2**70)).__name__)
"""),
    ('dunders_returning_big_ints', SHOW + """big = 2**64
class C:
    def __int__(self):
        return big
class I:
    def __index__(self):
        return big
class T:
    def __trunc__(self):
        return big
class S:
    def __int__(self):
        return True
class N:
    def __int__(self):
        return "a"
    def __index__(self):
        return "a"
for f in (lambda: int(C()), lambda: int(I()), lambda: int(-big), lambda: int(True), lambda: int(False), lambda: int(N()), lambda: [1][N()], lambda: hex(I()), lambda: range(I()), lambda: list(range(0, I(), big)), lambda: range(I())[I()], lambda: range(I() , 0), lambda: [1, 2][I():], lambda: [1, 2][:I()], lambda: [1, 2][::I()], lambda: "ab"[::I()], lambda: b"ab"[I():], lambda: round(5, I()), lambda: (5).__round__(I()), lambda: pow(2, I(), 5) if False else 0, lambda: [1].index(1, I()), lambda: "a".find("a", I()), lambda: sum([big, big], big), lambda: slice(I()).indices(5), lambda: slice(None, None, I()).indices(5), lambda: slice(1).indices(I())):
    show(f)
"""),
    ('constants_of_a_module_are_one_object', """a = 123456789012345678901234567890
b = 123456789012345678901234567890
def f():
    return 123456789012345678901234567890
class K:
    v = 123456789012345678901234567890
print(a is b, a is f(), a is K.v, f() is f(), -123456789012345678901234567890 == -a, (a, 123456789012345678901234567890)[0] is (123456789012345678901234567890, a)[0], 18446744073709551616, 4611686018427387904, 4611686018427387903, -4611686018427387904, -4611686018427387905, 9223372036854775807, -9223372036854775808)
def g(x=123456789012345678901234567890, *, y=(18446744073709551616, 1)):
    return x, y
print(g(), g.__defaults__, g.__kwdefaults__, g.__code__.co_consts if False else 0)
h = 0x""" + "f" * 4000 + """
print(h % 97, h.bit_length(), hex(h)[:10], h == 2**16000 - 1)
print(0b1""" + "0" * 70 + """, 0o1""" + "0" * 30 + """, 1_000_000_000_000_000_000_000_000)
match_value = 2**64
print({18446744073709551616: "k"}[match_value], match_value == 18446744073709551616, (18446744073709551616,) == (match_value,), [18446744073709551616] == [match_value])
"""),
    ('exit_with_a_big_int', "import sys\nsys.exit(2**64)\n"),
    ('exit_with_a_negative_big_int', "import sys\nsys.exit(-(2**64))\n"),
    ('exit_with_a_value_beyond_the_int_of_c', "import sys\nsys.exit(2**32 + 3)\n"),
    ('exit_with_the_largest_64_bits', "import sys\nsys.exit(2**63 - 1)\n"),
    ('exit_with_a_subclass_holding_a_big_int', "import sys\nclass B(int):\n    pass\nsys.exit(B(2**64))\n"),
    ('raising_system_exit_with_a_big_int', "raise SystemExit(2**70)\n"),
    ('an_uncaught_error_of_the_digit_limit', "print(1)\nprint(10**4300)\n"),
    ('the_sum_a_program_does', """def fact(n):
    return 1 if n < 2 else n * fact(n - 1)
def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
def gcd(a, b):
    while b:
        a, b = b, a % b
    return a
def isqrt(n):
    x = n
    y = (x + 1) // 2
    while y < x:
        x = y
        y = (x + n // x) // 2
    return x
print(fact(25), fact(100), fib(100), fib(1000), gcd(fact(50), fib(300)), isqrt(10**100), sum(i * i for i in []) if False else 0, 2**100 % 97, pow(3, 1000, 10**9 + 7))
h = 14695981039346656037
for c in b"the quick brown fox":
    h = ((h ^ c) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
print(h, hex(h), h >> 60, h & 0xFF, h % 1000)
"""),
]


def pytest_generate_tests(metafunc: Any) -> None:
    if "program" in metafunc.fixturenames:
        metafunc.parametrize("program", PROGRAMS, ids=[name for name, _ in PROGRAMS])


def test_as_cpython(program: tuple[str, str]) -> None:
    same(program[1])


if __name__ == "__main__":
    for item in PROGRAMS:
        test_as_cpython(item)
