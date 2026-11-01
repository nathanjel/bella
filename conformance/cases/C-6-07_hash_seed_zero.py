# clause: C-6-07
# spec: section 6
# status: P1
# source: deviation D-14 (seeding compatibility is a conformance clause); the harness sets PYTHONHASHSEED=0
"""With PYTHONHASHSEED=0 the hashes of str and bytes are CPython's fixed values, so a program
that fixes the seed sees the same hashes and the same set and dict-hash orders (D-05, D-14).
Numeric hashes do not depend on the seed and must match exactly."""
print([hash(s) for s in ("", "x", "hello", "héllo", "日本")])
print([hash(b) for b in (b"", b"x", b"bytes")])
print(hash(("a", 1)), hash(frozenset({"a"})))
print(list({"apple", "banana", "cherry", "date", "elderberry"}))
print([hash(n) for n in (0, 1, -1, -2, 2**61 - 1, 2**61, 10**30, -(10**30))])
print([hash(f) for f in (1.5, -0.0, 0.1, 1e300, float("inf"), float("-inf"))], hash(1 + 2j) == hash(complex(1, 2)))
