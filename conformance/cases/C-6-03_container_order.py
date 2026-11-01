# clause: C-6-03
# spec: section 6 (dict insertion order; set order for value-hashed elements, D-05)
# status: P1
# source: dialect specification section 6
"""dict order after delete and re-insert; popitem is LIFO; set order of small ints."""
d: dict[str, int] = {"a": 1, "b": 2, "c": 3}
del d["a"]
d["a"] = 4
print("reinsert goes to the end:", list(d))
print("popitem is LIFO:", d.popitem())
print("set of small ints:", {5, 3, 9, 1, 7})
print("set of strings is value-hashed; order fixed by PYTHONHASHSEED=0:", sorted({"x", "y", "z"}))
s: dict[int, int] = {}
try:
    for _ in s:
        pass
    s[1] = 1
    for _ in s:
        s[2] = 2
except RuntimeError as exc:
    print("size change during iteration:", type(exc).__name__)
