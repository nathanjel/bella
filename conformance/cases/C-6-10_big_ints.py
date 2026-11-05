# clause: C-6-10
# spec: section 6
# status: P1
# source: dialect specification section 6 (int is unbounded), Objects/longobject.c; decision of 2026-11-02 (SEL's bn)
"""int beyond the immediates: every operator across the boundary and far past it, floor semantics,
two's complement for the bitwise operators, hashes, text in every base, the 4300-digit limit, and
what a value too large for an index does where an index is asked for."""
# ruff: noqa: PLR0124, E711, E712  # a value compared with itself, with None and with True is what is shown


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


# ---- literals and the boundary
print(4611686018427387903, 4611686018427387904, -4611686018427387904, -4611686018427387905, 9223372036854775807, 9223372036854775808, 18446744073709551616)
print(0xFFFFFFFFFFFFFFFFFFFF, 0o7777777777777777777777777, 0b1111111111111111111111111111111111111111111111111111111111111111111, 1_000_000_000_000_000_000_000_000)
big = 123456789012345678901234567890
neg = -987654321098765432109876543210
print(big, neg, type(big).__name__, type(neg).__name__, repr(big), str(neg), f"{big}", isinstance(big, int), bool(big), bool(-big))
kmax = 2**62 - 1
kmin = -(2**62)
print(kmax + 1, kmin - 1, kmax * 2, kmin * 2, kmin * -1, -kmin, kmin // -1, abs(kmin), kmax - kmin, kmin - kmax)
print(kmax + 1 - 1 == kmax, (kmax + 1) - 1, type((kmax + 1) - 1).__name__, (kmin - 1) + 1, 2**64 - 2**64, 2**64 // 2**64, 2**64 % 2**64)


# ---- the four rules, all sign combinations
for a in (big, neg, 2**64, -(2**64), 2**64 + 1, 2**128 - 1, 7, -7, 1, -1, 0):
    for b in (big, neg, 2**64, -(2**64), 2**63, 3, -3, 1, -1):
        print(a + b, a - b, a * b, a // b, a % b, end=" | ")
    print()
print(big * big * big, (big * big) // big == big, (big * big) % big, -big // 7, -big % 7, big // -7, big % -7, 1 // big, -1 // big, 1 % big, -1 % big)
print("zero:", failed(lambda: big // 0), failed(lambda: big % 0), failed(lambda: 1 // (big - big)), big * 0, 0 * big, big - big, 0 // big, 0 % big)


# ---- large products and quotients: past the schoolbook and Knuth thresholds
digits = 0
x = 3**5000
y = 7**3000
print(x % 1000000007, y % 1000000007, (x * y) % 1000000007, (x * x) % 1000000007, (x // y) % 1000000007, (x % y) % 1000000007, x // y * y + x % y == x)
a100k = 10**20000 + 12345
print(a100k % 97, (a100k * a100k) % 97, (a100k * a100k - 1) // (a100k - 1) == a100k + 1, (a100k**3) % 1009)


# ---- powers
print(2**100, (-2)**101, 3**0, big**2, big**0, 0**0, 1**big, (-1)**big, (-1)**(big + 1), 0**big, 10**30, (10**30)**2)
print(pow(2, 100), pow(2, 100, 7), pow(3, big, 1000), pow(big, 3, 1000), pow(big, big, 10**20), pow(-3, 5, 7), pow(3, 5, -7), pow(2, 0, 1), pow(big, 0, 5), pow(0, 0, 5))
print(pow(3, -1, 7), pow(big, -1, 1000000007), failed(lambda: pow(2, -1, 4)), failed(lambda: pow(2, 3, 0)))


# ---- shifts
print(1 << 62, 1 << 63, 1 << 64, 1 << 1000 == 2**1000, -1 << 64, big << 3, big >> 3, neg >> 3, neg << 3, big >> 1000, neg >> 1000, 0 << 1000, 1 >> 1000, -1 >> 1000, (1 << 64) >> 64, big >> 0, big << 0)
print(failed(lambda: 1 << -1), failed(lambda: 1 >> -1), failed(lambda: big << -1), failed(lambda: big >> -1), 0 << big, 1 >> big, -1 >> big, big >> big, neg >> big, failed(lambda: 1 << big))


# ---- bitwise: infinite two's complement
m = 2**64 + 5
n = -(2**64) - 3
print(m & n, m | n, m ^ n, ~m, ~n, m & -1, m | -1, m ^ -1, n & -1, n | -1, n ^ -1, m & 0, m | 0, m ^ 0, n & 0, n | 0, n ^ 0)
print(m & 255, n & 255, m | 255, n | 255, m ^ 255, n ^ 255, -1 & m, 255 & n, m & m, n & n, m ^ m, n ^ n, ~~m == m, m & ~m, m | ~m)
print(True & m, m & True, False | m, True ^ n, big & False)
for a in (2**70 - 1, -(2**70), 2**64, -(2**64), 2**63, -(2**63), 2**128 + 2**64 + 1, -(2**128) - 2**64 - 1):
    for b in (2**70 - 1, -(2**70), 2**64, -(2**64), 1, -1):
        print(a & b, a | b, a ^ b, end=" | ")
    print()


# ---- comparison
print(big == big, big == big + 1, big != neg, big > neg, neg < big, big >= big, big <= big, big > 1, 1 < big, neg < 1, 1 > neg, big == 1, 1 == big, big == "a", big != None)  # type: ignore[comparison-overlap]
print(2**64 == 2**64, 2**64 > 2**64 - 1, -(2**64) < -(2**64) + 1, 2**64 > -(2**64), (2**64 + 1) > 2**64, big > True, big == True)
print(failed(lambda: big < "a"), failed(lambda: "a" < big), failed(lambda: big < None), [2**64, 1, -(2**64)] == [2**64, 1, -(2**64)], (big,) < (big + 1,), sorted([2**64, 1, -(2**64), 2**63, 0]), min(big, 1), max(big, 1), sum([big, big]))  # type: ignore[operator]


# ---- hash: the value modulo 2**61 - 1, with its sign
print(hash(2**61 - 1), hash(2**61), hash(2**61 + 1), hash(-(2**61)), hash(-(2**61) - 1), hash(2**62), hash(2**63), hash(2**64), hash(-(2**64)), hash(big), hash(neg), hash(2**61 * 5), hash(10**30), hash(-(10**30)))
print(hash(2**61 - 2), hash(-(2**61) + 2), hash(4 * (2**61 - 1) - 1), hash(-(4 * (2**61 - 1)) + 1), hash(-1 - 2**61 + 1), hash(1 - (2**61 - 1)))
print({2**64: 1}[2**64], 2**64 in {2**64}, {big: "b"}.get(big), {2**64, 2**64}, len({2**64, 2**64 + 2**61 - 1}), {2**61: 1, 1: 2}[1], {1: 2, 2**61: 3}[2**61])


class HashBig:
    def __init__(self, v: int) -> None:
        self.v = v
    def __hash__(self) -> int:
        return self.v
    def __eq__(self, other: object) -> bool:
        return True


print(hash(HashBig(2**64)) == hash(2**64), hash(HashBig(2**63)) == hash(2**63), hash(HashBig(2**63 - 1)), hash(HashBig(2**62)), hash(HashBig(-(2**63))), hash(HashBig(-1)), hash(HashBig(-(2**63) - 1)) == hash(-(2**63) - 1))
print({HashBig(2**64): 1}.get(2**64), 2**64 in {HashBig(2**64)})  # type: ignore[call-overload]


# ---- text
print(int("123456789012345678901234567890"), int("-123456789012345678901234567890"), int(" +1_000_000_000_000_000_000_000 "), int("f" * 30, 16), int("0x" + "f" * 30, 16), int("0b" + "1" * 70, 0), int("z" * 20, 36), int("1" * 70, 2), int("7" * 30, 8), int("0o" + "7" * 30, 0), int(b"1" + b"0" * 30))
print(failed(lambda: int("1" * 30 + "x")), failed(lambda: int("0x" + "f" * 30)), failed(lambda: int("f" * 30, 10)), failed(lambda: int("1_" * 20)), int("0" * 40), int("0" * 40, 16), int("00" + "1" * 30))
print(len(str(2**10000)), str(2**1000)[:20], str(2**1000)[-20:], str(10**4299)[:3], len(str(10**4299)), str(-(10**4299))[:3])
print("limit:", failed(lambda: str(10**4300)), failed(lambda: repr(10**4300)), failed(lambda: f"{10**4300}"), failed(lambda: print(10**4300)), failed(lambda: int("1" * 4301)), len(str(int("1" * 4300))), int("1" * 5000, 16) > 0, int("1" * 5000, 2) > 0, failed(lambda: int("1" * 5000, 10)), failed(lambda: int("1" * 5000, 3)), failed(lambda: int("1" * 5000, 36)))


# ---- where an index is asked for
items = [1, 2, 3]
print(failed(lambda: items[2**64]), failed(lambda: items[-(2**64)]), failed(lambda: "abc"[2**64]), failed(lambda: (1,)[2**64]), failed(lambda: b"a"[2**64]), items[2**64:], items[:2**64], items[-(2**64):], items[:-(2**64)], items[::2**64], items[::-(2**64)], "abc"[2**64:], "abc"[:2**64], (1, 2)[:2**64], b"ab"[:2**64], range(3)[:2**64], list(range(3)[2**64:]))
print(failed(lambda: items * 2**64), failed(lambda: "a" * 2**64), failed(lambda: (1,) * 2**64), failed(lambda: b"a" * 2**64), failed(lambda: 2**64 * "a"), failed(lambda: items * -(2**64)), failed(lambda: "a" * -(2**64)), failed(lambda: (1,) * -(2**64)), failed(lambda: b"a" * -(2**64)))
print(failed(lambda: chr(2**64)), failed(lambda: bytes(2**64)), failed(lambda: bytearray(2**64)), failed(lambda: items.pop(2**64)), failed(lambda: items.insert(2**64, 1) or items.pop()), failed(lambda: "a".find("a", 2**64) or 0), failed(lambda: list(range(2**64 + 1, 2**64 + 3))), failed(lambda: [0][2**64:]))  # type: ignore[func-returns-value]


class BigIndex:
    def __index__(self) -> int:
        return 2**64


print(failed(lambda: items[BigIndex()]), items[BigIndex():], failed(lambda: "a" * BigIndex()), failed(lambda: bytes(BigIndex())), failed(lambda: range(BigIndex()) and 1), failed(lambda: len(range(BigIndex()))))


class BigLen:
    def __len__(self) -> int:
        return 2**64


class BigBool:
    def __bool__(self) -> int:
        return 2**64


print(failed(lambda: len(BigLen())), failed(lambda: bool(BigLen())), failed(lambda: bool(BigBool())))


# ---- ranges past the immediates
r = range(2**64, 2**64 + 6, 2)
print(r, list(r), len(r), r[0], r[-1], r.start, r.stop, r.step, 2**64 + 2 in r, 2**64 + 1 in r, r.index(2**64 + 2), r.count(2**64), list(reversed(r)), bool(r), r == range(2**64, 2**64 + 6, 2), hash(r) == hash(range(2**64, 2**64 + 6, 2)), r[1:], type(iter(r)).__name__, r[::-1])
huge = range(2**1000)
print(type(iter(huge)).__name__, huge.stop == 2**1000, huge[5], huge[-1] == 2**1000 - 1, 5 in huge, 2**1000 in huge, failed(lambda: len(huge)), bool(huge), next(iter(huge)), repr(range(2**70)), huge[:3], len(huge[:3]), huge[2**999] == 2**999)
print(list(range(2**62 - 2, 2**62 + 2)), list(range(-(2**62) + 1, -(2**62) - 3, -1)), range(2**62).stop, len(range(2**62)), range(2**62)[2**61] == 2**61, type(iter(range(2**62))).__name__, type(iter(range(2**63))).__name__, type(iter(range(2**64))).__name__)
print(failed(lambda: len(range(2**63))), len(range(2**63 - 1)), failed(lambda: range(2**64)[2**64]), failed(lambda: range(0, 1, 2**64 - 2**64)), list(range(0, 2**64, 2**63)), list(range(2**64, 0, -(2**63))), range(0, 2**64, 2**63)[1])


# ---- bool and subclasses meeting big ints
class Big(int):
    def __repr__(self) -> str:
        return "Big(" + super().__repr__() + ")"


s = Big(2**64)
print(s, s + 1, type(s + 1).__name__, -s, type(-s).__name__, abs(s), s * 2, s // 2, s % 3, s == 2**64, 2**64 == s, hash(s) == hash(2**64), int(s), type(int(s)).__name__, bool(s), s > 1, s << 1, s >> 1, s & 1, ~s, type(s).__name__)
print(Big("123456789012345678901234567890"), Big(), Big(5) + 2**64, int(Big(2**70)), True + 2**64, 2**64 + True, True * 2**64, False * 2**64, 2**64 - True, -True + 2**64)


class Convert:
    def __int__(self) -> int:
        return 2**64


class ConvertIndex:
    def __index__(self) -> int:
        return 2**65


print(int(Convert()), int(ConvertIndex()), int(2**64), int(-(2**64)), type(int(2**64)).__name__, int(True), (2**64).__index__(), (2**64).__int__(), (2**64).__add__(1), (2**64).__radd__(1), (2**64).__sub__(1), (2**64).__mul__(2), (2**64).__neg__(), (2**64).__pos__(), (2**64).__abs__(), (2**64).__invert__(), (2**64).__bool__(), (2**64).__eq__(2**64), (2**64).__lt__(1), (2**64).__hash__(), (2**64).__repr__()[:5], (2**64).__add__("a"), (1).__add__(2**64), (1).__lt__(2**64), (1).__eq__(2**64))  # type: ignore[operator]
print((2**64).real == 2**64, (2**64).imag, (2**64).numerator == 2**64, (2**64).denominator, (2**64).conjugate() == 2**64, (2**64).bit_length(), (-(2**64)).bit_length(), (2**64).bit_count(), (2**64 - 1).bit_count(), (0).bit_length(), (5).bit_length(), (-5).bit_count(), (2**64).is_integer(), (2**64).to_bytes(9, "big"), (2**64).to_bytes(9, "little"), int.from_bytes(b"\x01" + b"\x00" * 8, "big"), int.from_bytes(b"\xff" * 9, "big", signed=True), (-(2**64)).to_bytes(10, "big", signed=True), failed(lambda: (2**64).to_bytes(1, "big")), failed(lambda: (-1).to_bytes(1, "big")))
print(divmod(big, 7), divmod(neg, 7), divmod(7, big), divmod(-7, big), divmod(big, -7), divmod(big, big), divmod(2**64, 2**32), failed(lambda: divmod(big, 0)), failed(lambda: divmod(big, "a")))  # type: ignore[operator]
print(bin(2**70), oct(2**70), hex(2**70), bin(-(2**70)), oct(-(2**70)), hex(-(2**70)), hex(big), bin(5), oct(8), hex(255), hex(-255), bin(0), bin(True), hex(0), oct(0), failed(lambda: hex("a")), failed(lambda: bin(None)))  # type: ignore[arg-type]
print(round(big), round(big, 0), round(big, -5), round(neg, -5), round(5, -1), round(15, -1), round(25, -1), round(5), round(-5), round(True), type(round(True)).__name__, round(2**64 + 5, -1), round(2**64, 2), failed(lambda: round(5, "a")), failed(lambda: round("a")), round(5, 2**64))  # type: ignore[call-overload]
