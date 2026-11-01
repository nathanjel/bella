# clause: C-6-02
# spec: section 6
# status: P1
# source: dialect specification section 6 (mixed int/float comparison is exact; round half to even)
"""Numeric tower observables: exact mixed comparison, shortest repr, banker's rounding, NaN."""
print("2**53+1 == 2.0**53:", 2**53 + 1 == 2.0**53)
print("2**53+1 > 2.0**53:", 2**53 + 1 > 2.0**53)
print("repr shortest:", repr(0.1 + 0.2), repr(1e16), repr(1.0), repr(-0.0))
print("round half to even:", round(0.5), round(1.5), round(2.5), round(2.675, 2))
nan = float("nan")
print("nan != nan:", nan != nan, "nan in [nan]:", nan in [nan])
print("int/float promotion:", 1 / 2, 7 // 2.0, 2**0.5 == 2**0.5, type(10**20 * 1.0).__name__)
print("hash(2.0) == hash(2):", hash(2.0) == hash(2), hash(1.5))
try:
    float(10**400)
except OverflowError as exc:
    print("int too large for float:", type(exc).__name__)
