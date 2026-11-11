"""_functools, sentinel and MappingProxyType, compiled, against CPython: the messages, which case C-7-25 does not compare."""
from __future__ import annotations

from pipeline.tests.test_review_2026_11_03 import same

MESSAGES = r"""
import functools, types, copy
import _functools
def show(f):
    try:
        r = f()
        s = repr(r)
        print(s if " at 0x" not in s else "<" + type(r).__name__ + ">")
    except BaseException as e:
        print(type(e).__name__, e)
P = functools.partial
X = functools.Placeholder
def add(*a, **k):
    return a, k
K = functools.cmp_to_key(lambda a, b: a - b)
L = functools.lru_cache(maxsize=1)(add)
p = P(add, 1)
for fn in (lambda: P(), lambda: P(1), lambda: P(None), lambda: P(add, X), lambda: P(add, 1, X), lambda: P(add, a=X), lambda: P(add, X, 1)(), lambda: P(add, X, X, 1)(0), lambda: setattr(p, "func", 1), lambda: setattr(p, "args", 1), lambda: setattr(p, "keywords", 1), lambda: delattr(p, "func"), lambda: delattr(p, "__dict__"), lambda: delattr(P(add), "__dict__"), lambda: setattr(p, "__dict__", 1), lambda: p.__setstate__((add, (), None, 1)), lambda: delattr(p, "nothing"), lambda: p.nothing, lambda: P.__new__(), lambda: P.__new__(1), lambda: P.__new__(int), lambda: P.__call__(), lambda: P.__call__(1), lambda: P.__repr__(1), lambda: P.__reduce__(1), lambda: P.__reduce__(), lambda: P.__setstate__(p), lambda: P.__setstate__(p, 1, 2), lambda: p.__setstate__(1), lambda: p.__setstate__((1, 2)), lambda: p.__setstate__((1, (), None, None)), lambda: p.__setstate__((add, 1, None, None)), lambda: p.__setstate__((add, (), 1, None)), lambda: p.__setstate__((add, (), None, 1)), lambda: p.__setstate__((add, (X,), None, None)), lambda: p.__get__(), lambda: p.__get__(None, None), lambda: p.__get__(1, 2, 3), lambda: p.__get__(x=1), lambda: p.__reduce__(1), lambda: type(X)(1), lambda: type(X)(a=1), lambda: type(X).__new__(1), lambda: type("Z", (type(X),), {}), lambda: X.__reduce__(1), lambda: type(X).__repr__(1),
           lambda: functools.reduce(), lambda: functools.reduce(max), lambda: functools.reduce(max, 1), lambda: functools.reduce(max, []), lambda: functools.reduce(1, [1, 2]), lambda: functools.reduce(max, [1], 2, 3), lambda: functools.reduce(max, [1], 2, initial=3), lambda: functools.reduce(function=max, iterable=[1]),
           lambda: K(1) < 1, lambda: 1 < K(1), lambda: K(1) == 1, lambda: K < K(1), lambda: K(1) < K, lambda: hash(K(1)), lambda: {K(1)}, lambda: K(), lambda: K(1, 2), lambda: K(1, obj=2), lambda: functools.cmp_to_key(), lambda: functools.cmp_to_key(1, 2), lambda: functools.cmp_to_key(1, mycmp=2), lambda: type(K)(), lambda: type(K).__new__(type(K)), lambda: type(K).__call__(), lambda: type(K).__call__(1), lambda: type(K).__lt__(1, 2), lambda: type(K).__lt__(K(1)), lambda: functools.cmp_to_key(1)(1) < functools.cmp_to_key(1)(2), lambda: functools.cmp_to_key(lambda a, b: "x")(1) < functools.cmp_to_key(lambda a, b: "x")(2), lambda: type("Z", (type(K),), {}), lambda: K(1).nothing, lambda: setattr(K(1), "x", 1),
           lambda: L([]), lambda: L({}), lambda: functools.lru_cache(maxsize="a"), lambda: functools.lru_cache(maxsize=1.5), lambda: functools.lru_cache(1)(1), lambda: functools._lru_cache_wrapper(), lambda: functools._lru_cache_wrapper(add), lambda: functools._lru_cache_wrapper(1, 1, 1, 1), lambda: functools._lru_cache_wrapper(add, "a", 1, 1), lambda: functools._lru_cache_wrapper(add, 2**70, 1, 1), lambda: functools._lru_cache_wrapper(add, 1, 1, 1, 1), lambda: functools._lru_cache_wrapper(add, 1, 1, 1).cache_info(), lambda: functools._lru_cache_wrapper(add, 1, 1, cache_info_type=tuple, x=1), lambda: L.cache_info(1), lambda: L.cache_clear(1), lambda: L.__reduce__(1), lambda: L.__copy__(1) is L, lambda: L.__deepcopy__() is L, lambda: L.__copy__(x=1), lambda: L.nothing, lambda: L.__get__(), lambda: L.__get__(None, None), lambda: type("Z", (type(L),), {}), lambda: type(L).__call__(), lambda: type(L).__call__(1), lambda: type(L).cache_info(1), lambda: type(L).cache_info(),
           lambda: sentinel(), lambda: sentinel(1), lambda: sentinel("a", "b"), lambda: sentinel("a", repr=1), lambda: sentinel("a", x=1), lambda: sentinel.__new__(), lambda: sentinel.__new__(1), lambda: sentinel.__new__(int), lambda: type("Z", (sentinel,), {}), lambda: setattr(sentinel("a"), "__name__", "b"), lambda: delattr(sentinel("a"), "__name__"), lambda: setattr(sentinel("a"), "x", 1), lambda: sentinel("a").x, lambda: sentinel("a") < sentinel("b"), lambda: sentinel("a") | 1, lambda: 1 | sentinel("a"), lambda: sentinel("a") + 1,
           lambda: types.MappingProxyType(), lambda: types.MappingProxyType(1), lambda: types.MappingProxyType([]), lambda: types.MappingProxyType(()), lambda: types.MappingProxyType(None), lambda: types.MappingProxyType({}, {}), lambda: types.MappingProxyType(x=1), lambda: types.MappingProxyType(mapping={"a": 1}), lambda: types.MappingProxyType({"a": 1})["b"], lambda: types.MappingProxyType({})[[]], lambda: setattr(types.MappingProxyType({}), "x", 1), lambda: types.MappingProxyType({}).__setitem__, lambda: hash(types.MappingProxyType({})), lambda: hash(types.MappingProxyType(types.MappingProxyType({}))),
           lambda: repr(types.MappingProxyType({"a": 1})), lambda: str(types.MappingProxyType({"a": 1})), lambda: types.MappingProxyType({"a": 1})["a"], lambda: "a" in types.MappingProxyType({"a": 1}), lambda: 1 in types.MappingProxyType({"a": 1}), lambda: len(types.MappingProxyType({"a": 1})), lambda: list(types.MappingProxyType({"a": 1})), lambda: list(types.MappingProxyType({"a": 1}).keys()), lambda: list(types.MappingProxyType({"a": 1}).values()), lambda: list(types.MappingProxyType({"a": 1}).items()), lambda: types.MappingProxyType({"a": 1}).copy(), lambda: types.MappingProxyType({"a": 1}).get("a"), lambda: types.MappingProxyType({"a": 1}).get("b", 2), lambda: types.MappingProxyType({"a": 1}) == {"a": 1}, lambda: types.MappingProxyType({"a": 1}) != {"a": 1}, lambda: bool(types.MappingProxyType({})), lambda: types.MappingProxyType(types.MappingProxyType({"a": 1}))["a"]):
    show(fn)
a = sentinel("a")
b = sentinel("b", repr="<b>")
print(a, repr(a), str(a), b, repr(b), a.__name__, b.__name__, a.__module__, type(a).__name__, type(a).__module__, sentinel.__name__, sentinel.__module__, sentinel.__qualname__, a == a, a != a, a == sentinel("a"), a is copy.copy(a), a is copy.deepcopy(a), a.__copy__() is a, a.__deepcopy__({}) is a, a.__reduce__(), bool(a), hash(a) == hash(a), {a: 1}[a], a | int, int | a, a | None, None | a, a | b, a | a, (a | int).__args__, isinstance(a, sentinel), sentinel.__doc__.splitlines()[0], repr(sentinel), type(sentinel.__dict__["__name__"]).__name__)
a.__module__ = "elsewhere"
print(a.__module__)
del a.__module__
show(lambda: a.__module__)
show(lambda: delattr(a, "__module__"))
def in_function():
    return sentinel("x")
print(in_function().__module__, sentinel("y").__module__)
d = {"k": 1}
m = types.MappingProxyType(d)
d["j"] = 2
print(m, len(m), list(m), m["j"], type(m).__name__, types.MappingProxyType is type(m), type(int.__dict__) is type(m), int.__dict__["real"].__name__, "real" in int.__dict__)
class Mapping:
    def __getitem__(self, k):
        return "got " + k
    def get(self, k, d=None):
        return "get " + k + " " + repr(d)
    def __len__(self):
        return 9
    def __iter__(self):
        return iter(["i"])
    def __contains__(self, k):
        return k == "yes"
    def keys(self):
        return ["k"]
    def values(self):
        return ["v"]
    def items(self):
        return ["it"]
    def copy(self):
        return "copied"
    def __repr__(self):
        return "Mapping()"
mm = types.MappingProxyType(Mapping())
print(mm["a"], mm.get("b"), mm.get("b", 1), len(mm), list(mm), "yes" in mm, "no" in mm, mm.keys(), mm.values(), mm.items(), mm.copy(), repr(mm), str(mm))
"""


def test_messages() -> None:
    same(MESSAGES)


if __name__ == "__main__":
    test_messages()
