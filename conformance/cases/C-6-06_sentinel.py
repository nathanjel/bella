# clause: C-6-06
# spec: section 6
# status: P1
# source: dialect specification v0.4 section 6 (sentinel, PEP 661, new in 3.15)
"""sentinel: a named unique marker. Its repr and str are its name, it is equal only to itself
(another sentinel of the same name is a different object), it is true, and copy and deepcopy
return the same object."""
import copy

MISSING = sentinel("MISSING")
OTHER = sentinel("MISSING")
print(repr(MISSING), str(MISSING), type(MISSING).__name__, bool(MISSING))
print("equal to itself:", MISSING == MISSING, MISSING is MISSING,
      "| to a namesake:", MISSING == OTHER, MISSING is OTHER)  # type: ignore[comparison-overlap]  # distinct, on purpose
print("copies:", copy.copy(MISSING) is MISSING, copy.deepcopy(MISSING) is MISSING)


def lookup(table: dict[str, int], key: str, default: object = MISSING) -> object:
    return table.get(key, default)


print("as a default:", lookup({"a": 1}, "a"), lookup({"a": 1}, "b") is MISSING)
