# clause: C-6-01
# spec: section 6
# status: P1
# source: review round 1, finding 5 (kMin // -1 must promote; range proofs must cover intermediates)
"""int is exact at the tagged-representation boundaries; bool is an int; floor semantics."""
KMIN = -(2**62)
KMAX = 2**62 - 1

print("kMin // -1:", KMIN // -1)
print("kMin % -1:", KMIN % -1)
print("divmod(kMin, -1):", divmod(KMIN, -1))
print("kMax + 1:", KMAX + 1)
print("kMin - 1:", KMIN - 1)
print("-(2**63) // -1:", (-(2**63)) // -1)
x = -(2**31)
print("norm2 at -2**31:", x * x + x * x)
print("2**62 * 2:", 2**62 * 2)
print("floor division signs:", 7 // 2, -7 // 2, 7 // -2, -7 // -2)
print("modulo signs:", 7 % 2, -7 % 2, 7 % -2, -7 % -2)
print("bool is int:", True + True, isinstance(True, int), type(True).__name__)  # noqa: UP003  -- the runtime type of True is the observable
print("hash formulas:", hash(2**61 - 1), hash(2**61), hash(-1), hash(-2))
print("bitwise on negatives:", ~5, -5 >> 1, -5 & 0xFF, (-1) << 70)
print("pow:", pow(3, 100, 7), 2**-1, 2**100)
try:
    print(1 // 0)
except ZeroDivisionError as exc:
    print("division by zero:", type(exc).__name__)
print("str/int round trip:", int(str(10**60)) == 10**60, int("1_000"), int("ff", 16))
