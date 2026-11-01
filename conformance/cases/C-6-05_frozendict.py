# clause: C-6-05
# spec: section 6
# status: P1
# source: dialect specification v0.4 section 6 (frozendict, PEP 814, new in 3.15)
"""frozendict: immutable, not a dict subclass; insertion order kept for iteration and repr but
ignored by ==; hashable when every key and value is, with hash(frozenset(items)); | returns a
frozendict; copy.copy returns the same object and copy.deepcopy a new one."""
import copy

fd = frozendict({"b": 2, "a": 1})
print(repr(fd), list(fd), len(fd), "a" in fd, fd.get("z", 0))
print("== ignores order:", fd == frozendict({"a": 1, "b": 2}), "| == dict:", fd == {"b": 2, "a": 1})
print("dict subclass:", isinstance(fd, dict), [c.__name__ for c in type(fd).__mro__])
print("hash:", hash(fd) == hash(frozenset(fd.items())), hash(frozendict(a=1)) == hash(frozendict({"a": 1})))
try:
    fd["c"] = 3  # type: ignore[index]  # the point: frozendict refuses item assignment
except TypeError as exc:
    print("item assignment ->", type(exc).__name__)
try:
    del fd["a"]  # type: ignore[attr-defined]
except TypeError as exc:
    print("item deletion ->", type(exc).__name__)
for name, action in (("update", lambda: fd.update(c=3)),  # type: ignore[attr-defined]
                     ("hash of a list value", lambda: hash(frozendict(a=[1])))):
    try:
        action()
    except (TypeError, AttributeError) as exc:
        print(name, "->", type(exc).__name__)
merged = fd | {"c": 3}
print("merge:", repr(merged), type(merged).__name__, "| dict():", dict(fd), "| fromkeys:", frozendict.fromkeys("ab", 0))
print("copy is same:", copy.copy(fd) is fd, "| deepcopy is same:", copy.deepcopy(fd) is fd, copy.deepcopy(fd) == fd)
