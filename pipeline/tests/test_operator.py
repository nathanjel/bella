"""operator and _operator, compiled, against CPython.

Case C-7-21 shows the behaviour by exception class, as a case must; these compare messages too, each
name's argument checks, the concatenations (which are not `+`), the searches, and the three callable
classes.
"""
from __future__ import annotations

from typing import Any

from pipeline.tests.test_review_2026_11_03 import same

SHOW = """def show(f):
    try:
        r = f()
        s = repr(r)
        print(s if " at 0x" not in s else "<" + type(r).__name__ + ">")
    except Exception as e:
        print(type(e).__name__, e)
"""

CLASSES = """class Num:
    def __init__(self, n):
        self.n = n
    def __repr__(self):
        return "Num(" + str(self.n) + ")"
class Ops(Num):
    def __add__(self, o): return "add"
    def __radd__(self, o): return "radd"
    def __iadd__(self, o): return "iadd"
    def __sub__(self, o): return "sub"
    def __isub__(self, o): return "isub"
    def __mul__(self, o): return "mul"
    def __imul__(self, o): return "imul"
    def __matmul__(self, o): return "matmul"
    def __imatmul__(self, o): return "imatmul"
    def __truediv__(self, o): return "truediv"
    def __itruediv__(self, o): return "itruediv"
    def __floordiv__(self, o): return "floordiv"
    def __ifloordiv__(self, o): return "ifloordiv"
    def __mod__(self, o): return "mod"
    def __imod__(self, o): return "imod"
    def __pow__(self, o, m=None): return ("pow", m)
    def __ipow__(self, o): return "ipow"
    def __lshift__(self, o): return "lshift"
    def __ilshift__(self, o): return "ilshift"
    def __rshift__(self, o): return "rshift"
    def __irshift__(self, o): return "irshift"
    def __and__(self, o): return "and"
    def __iand__(self, o): return "iand"
    def __or__(self, o): return "or"
    def __ior__(self, o): return "ior"
    def __xor__(self, o): return "xor"
    def __ixor__(self, o): return "ixor"
    def __neg__(self): return "neg"
    def __pos__(self): return "pos"
    def __abs__(self): return "abs"
    def __invert__(self): return "invert"
    def __eq__(self, o): return "eq"
    def __ne__(self, o): return "ne"
    def __lt__(self, o): return "lt"
    def __le__(self, o): return "le"
    def __gt__(self, o): return "gt"
    def __ge__(self, o): return "ge"
    def __bool__(self): return False
    def __index__(self): return 7
    __hash__ = None
class Seq:
    def __init__(self, items):
        self.items = items
    def __getitem__(self, i):
        return self.items[i]
    def __len__(self):
        return len(self.items)
    def __add__(self, o):
        return "Seq.add"
    def __repr__(self):
        return "Seq"
class SeqNoAdd:
    def __getitem__(self, i):
        raise IndexError
class SeqIadd(Seq):
    def __iadd__(self, o):
        return "Seq.iadd"
class AddOnly:
    def __add__(self, o):
        return "AddOnly.add"
    def __iadd__(self, o):
        return "AddOnly.iadd"
class Radd:
    def __radd__(self, o):
        return "Radd.radd"
"""


PROGRAMS: list[tuple[str, str]] = [
    ('every_name_on_numbers', """import operator as op
a, b = 7, 2
print(op.add(a, b), op.sub(a, b), op.mul(a, b), op.floordiv(a, b), op.mod(a, b), op.pow(a, b), op.lshift(a, b), op.rshift(a, b), op.and_(a, b), op.or_(a, b), op.xor(a, b), op.neg(a), op.pos(a), op.abs(-a), op.inv(a), op.invert(a), op.not_(a), op.truth(a), op.not_(0), op.truth(0), op.index(a), op.eq(a, b), op.ne(a, b), op.lt(a, b), op.le(a, b), op.gt(a, b), op.ge(a, b), op.is_(a, a), op.is_not(a, a), op.is_none(None), op.is_not_none(None), op.is_none(a), op.is_not_none(a))
print(op.iadd(a, b), op.isub(a, b), op.imul(a, b), op.ifloordiv(a, b), op.imod(a, b), op.ipow(a, b), op.ilshift(a, b), op.irshift(a, b), op.iand(a, b), op.ior(a, b), op.ixor(a, b), op.add(2**64, 1), op.mul(2**64, 2**64), op.pow(2, 100), op.neg(2**64), op.index(2**64), op.abs(-(2**64)), op.ipow(2, 70))
print(op.getitem([1, 2], 1), op.getitem({"a": 1}, "a"), op.getitem("ab", slice(1, None)), op.contains([1], 1), op.contains({1: 2}, 2), op.contains("ab", "a"), op.countOf([1, 1, 2], 1), op.countOf("aab", "a"), op.indexOf([1, 2], 2), op.indexOf("ab", "b"), op.concat([1], [2]), op.concat("a", "b"), op.concat((1,), (2,)), op.concat(b"a", b"b"), op.concat(bytearray(b"a"), b"b"), op.length_hint([1, 2]), op.length_hint(5), op.length_hint(5, 9), op.length_hint("abc", 9), op.call(max, 1, 2), op.call(sorted, [2, 1], reverse=True), op.call(lambda: 1))
l = [1]
print(op.iconcat(l, [2]) is l, l, op.iadd(l, [3]) is l, l, op.imul(l, 2) is l, l, op.iconcat(l, "a") is l, l, op.iconcat((1,), (2,)), op.iconcat("a", "b"), op.iconcat(bytearray(b"a"), b"b"), op.iadd((1,), (2,)))
d = {"a": 1}
print(op.setitem(d, "b", 2), d, op.delitem(d, "a"), d, op.ior(d, {"c": 3}) is d, d, op.or_({"x": 1}, {"y": 2}), op.and_({1, 2}, {2}), op.iand({1, 2}, {2}), op.sub({1}, {1}), op.is_(None, None), op.is_not(1, 2))
"""),
    ('dunders_are_asked', CLASSES + """import operator as op
x, y = Ops(1), Ops(2)
print(op.add(x, y), op.sub(x, y), op.mul(x, y), op.matmul(x, y), op.truediv(x, y), op.floordiv(x, y), op.mod(x, y), op.pow(x, y), op.lshift(x, y), op.rshift(x, y), op.and_(x, y), op.or_(x, y), op.xor(x, y), op.neg(x), op.pos(x), op.abs(x), op.inv(x), op.invert(x), op.not_(x), op.truth(x), op.eq(x, y), op.ne(x, y), op.lt(x, y), op.le(x, y), op.gt(x, y), op.ge(x, y), op.index(x), op.is_(x, x), op.is_not(x, y))
print(op.iadd(x, y), op.isub(x, y), op.imul(x, y), op.imatmul(x, y), op.itruediv(x, y), op.ifloordiv(x, y), op.imod(x, y), op.ipow(x, y), op.ilshift(x, y), op.irshift(x, y), op.iand(x, y), op.ior(x, y), op.ixor(x, y), op.__add__(x, y), op.__iadd__(x, y), op.__lt__(x, y), op.__not__(x), op.__neg__(x), op.__abs__(x), op.__inv__(x), op.__invert__(x), op.__index__(x), op.__pow__(x, y), op.__ipow__(x, y), op.__and__(x, y), op.__or__(x, y), op.__concat__([1], [2]), op.__contains__([1], 1), op.__getitem__([1], 0), op.__call__(max, 1, 2), op.__pos__(x), op.__mod__(x, y), op.__matmul__(x, y), op.__imatmul__(x, y))
print(op.add(1, Ops(1)), op.iadd(1, Ops(1)), op.add([1], Radd()), op.add("a", Radd()), op.iadd([1], Seq([])) if False else 0, op.index(True), op.index(False), op.truth([]), op.truth([0]), op.not_([]), op.not_(None))
"""),
    ('messages', SHOW + CLASSES + """import operator as op, _operator
binary = ["add", "sub", "mul", "matmul", "floordiv", "truediv", "mod", "pow", "lshift", "rshift", "and_", "or_", "xor", "eq", "ne", "lt", "le", "gt", "ge", "is_", "is_not", "iadd", "isub", "imul", "imatmul", "ifloordiv", "itruediv", "imod", "ipow", "ilshift", "irshift", "iand", "ior", "ixor", "concat", "iconcat", "contains", "getitem", "delitem", "countOf", "indexOf", "_compare_digest"]
unary = ["truth", "neg", "pos", "abs", "inv", "invert", "not_", "index", "is_none", "is_not_none"]
for n in binary:
    f = getattr(_operator, n)
    show(lambda: f())
    show(lambda: f(1))
    show(lambda: f(1, 2, 3))
    show(lambda: f(1, 2, x=3))
    show(lambda: f(a=1, b=2))
for n in unary:
    f = getattr(_operator, n)
    show(lambda: f())
    show(lambda: f(1, 2))
    show(lambda: f(1, x=3))
    show(lambda: f(a=1))
for f in (lambda: op.setitem(), lambda: op.setitem(1, 2), lambda: op.setitem(1, 2, 3, 4), lambda: op.setitem(1, 2, 3), lambda: op.setitem([], 0, 1), lambda: op.setitem([1], "a", 1), lambda: op.setitem((1,), 0, 1), lambda: op.getitem(1, 2), lambda: op.getitem([], 0), lambda: op.getitem({}, "k"), lambda: op.getitem([], "a"), lambda: op.delitem(1, 2), lambda: op.delitem([], 0), lambda: op.delitem({}, "k"), lambda: op.delitem((1,), 0),
          lambda: op.add(1, "a"), lambda: op.add("a", 1), lambda: op.sub("a", 1), lambda: op.mul("a", "b"), lambda: op.floordiv(1, 0), lambda: op.mod(1, 0), lambda: op.lshift(1, -1), lambda: op.neg("a"), lambda: op.pos("a"), lambda: op.abs("a"), lambda: op.inv("a"), lambda: op.invert("a"), lambda: op.index("a"), lambda: op.index(None), lambda: op.lt(1, "a"), lambda: op.matmul(1, 2), lambda: op.imatmul(1, 2), lambda: op.iadd(1, "a"), lambda: op.ipow("a", 1),
          lambda: op.concat(1, 2), lambda: op.concat(1, [2]), lambda: op.concat([1], 2), lambda: op.concat("a", 1), lambda: op.concat((1,), [2]), lambda: op.concat(b"a", 1), lambda: op.concat({}, {}), lambda: op.concat({1}, {2}), lambda: op.concat(None, 1), lambda: op.concat(range(1), range(1)), lambda: op.concat(AddOnly(), 1), lambda: op.concat(Seq([]), 1), lambda: op.concat(SeqNoAdd(), 1), lambda: op.concat(1, Radd()), lambda: op.concat([1], Radd()), lambda: op.concat(iter(()), 1),
          lambda: op.iconcat(1, 2), lambda: op.iconcat([1], 2), lambda: op.iconcat("a", 1), lambda: op.iconcat((1,), [2]), lambda: op.iconcat({}, {}), lambda: op.iconcat(AddOnly(), 1), lambda: op.iconcat(Seq([]), 1), lambda: op.iconcat(SeqIadd([]), 1), lambda: op.iconcat(SeqNoAdd(), 1), lambda: op.iconcat(1, Radd()), lambda: op.iconcat([1], Radd()), lambda: op.iconcat(bytearray(b"a"), 1),
          lambda: op.contains(1, 2), lambda: op.contains(None, 2), lambda: op.contains("a", 1), lambda: op.contains({}, []), lambda: op.contains({1}, []),
          lambda: op.countOf(1, 2), lambda: op.countOf(None, 2), lambda: op.indexOf(1, 2), lambda: op.indexOf(None, 2), lambda: op.indexOf([1], 2), lambda: op.indexOf([], 2), lambda: op.countOf([], 2), lambda: op.indexOf(iter("ab"), "b"), lambda: op.countOf(iter("abb"), "b"), lambda: op.indexOf({"a": 1}, "a"), lambda: op.countOf({"a": 1}, "a"), lambda: op.indexOf(Seq([1, 2]), 2), lambda: op.countOf(Seq([1, 1]), 1), lambda: op.indexOf(SeqNoAdd(), 1),
          lambda: op.length_hint(), lambda: op.length_hint(1, 2, 3), lambda: op.length_hint(1, "a"), lambda: op.length_hint(1, 2**64), lambda: op.length_hint(1, -1), lambda: op.length_hint(1, default=2), lambda: op.length_hint(obj=1), lambda: op.length_hint([1], "a"), lambda: op.length_hint(1, True), lambda: op.length_hint(1, Ops(1)),
          lambda: op.call(), lambda: op.call(1), lambda: op.call(max), lambda: op.call(obj=max),
          lambda: _operator._compare_digest("a", "a"), lambda: _operator._compare_digest("a", "b"), lambda: _operator._compare_digest("a", "ab"), lambda: _operator._compare_digest("", ""), lambda: _operator._compare_digest("é", "é"), lambda: _operator._compare_digest("a", "é"), lambda: _operator._compare_digest(b"a", b"a"), lambda: _operator._compare_digest(b"a", b"b"), lambda: _operator._compare_digest(b"a", b"ab"), lambda: _operator._compare_digest(bytearray(b"a"), b"a"), lambda: _operator._compare_digest("a", b"a"), lambda: _operator._compare_digest(b"a", "a"), lambda: _operator._compare_digest(1, 2), lambda: _operator._compare_digest(1, b"a"), lambda: _operator._compare_digest(b"a", 1), lambda: _operator._compare_digest("a", 1), lambda: _operator._compare_digest(None, "a")):
    show(f)
class Hint:
    def __init__(self, v):
        self.v = v
    def __length_hint__(self):
        if isinstance(self.v, Exception):
            raise self.v
        return self.v
class HintAttr:
    __length_hint__ = None
class BadLen:
    def __len__(self):
        raise TypeError("len says no")
    def __length_hint__(self):
        return 3
class WorseLen:
    def __len__(self):
        raise ValueError("len says no")
class I(int):
    pass
for v in (5, 0, -1, True, I(3), "a", None, 2**64, -(2**64), NotImplemented, TypeError("no"), ValueError("no")):
    show(lambda: op.length_hint(Hint(v)))
    show(lambda: op.length_hint(Hint(v), 9))
show(lambda: op.length_hint(HintAttr()))
show(lambda: op.length_hint(BadLen()))
show(lambda: op.length_hint(WorseLen()))
show(lambda: op.length_hint(object(), 4))
show(lambda: op.length_hint(int, 4))
"""),
    ('the_three_classes', SHOW + CLASSES + """import operator as op
for c in (op.itemgetter, op.attrgetter, op.methodcaller):
    print(c, c.__name__, c.__qualname__, c.__module__, c.__mro__, c.__doc__ is not None, type(c), callable(c), hasattr(c, "__call__"), hasattr(c, "__repr__"), hasattr(c, "__reduce__"), hasattr(c, "__slots__"), hasattr(c, "__dict__"))
    show(lambda: setattr(c, "x", 1))
    show(lambda: type("S", (c,), {}))
print(op.itemgetter(1), op.itemgetter(1, 2), op.itemgetter("a"), op.itemgetter((1, 2)), op.itemgetter(None), op.itemgetter(slice(1)), op.itemgetter(1)([1, 2]), op.itemgetter(1, 0)([1, 2]), op.itemgetter("a")({"a": 1}), op.itemgetter("a", "b")({"a": 1, "b": 2}), op.itemgetter(0)("xy"), op.itemgetter(slice(1, None))([1, 2, 3]), op.itemgetter(-1)((1, 2)), op.itemgetter(0)((1, 2)), op.itemgetter(5).__reduce__()[1], op.itemgetter(5, 6).__reduce__()[1], op.itemgetter(5).__reduce__()[0] is op.itemgetter, op.itemgetter(2**64), op.itemgetter(True)((1, 2)))
class A:
    x = 1
    class B:
        y = 2
        class C:
            z = 3
print(op.attrgetter("x"), op.attrgetter("x", "B.y"), op.attrgetter("B.C.z"), op.attrgetter("x")(A), op.attrgetter("x", "B")(A)[0], op.attrgetter("B.y")(A), op.attrgetter("B.C.z")(A), op.attrgetter("x", "B.C.z")(A), op.attrgetter("x").__reduce__()[1], op.attrgetter("x", "B.y").__reduce__()[1], op.attrgetter("B.C.z").__reduce__()[1], op.attrgetter("").__reduce__()[1], op.attrgetter("a..b").__reduce__()[1], op.attrgetter(".").__reduce__()[1], op.attrgetter("a..b"), op.attrgetter("."), op.attrgetter(""))
print(op.methodcaller("upper" if False else "count"), op.methodcaller("count", "a"), op.methodcaller("count", "a", 1, 2), op.methodcaller("m", x=1), op.methodcaller("m", 1, x=1, y="b"), op.methodcaller("count", "a")("aab"), op.methodcaller("get", "k", "d")({}), op.methodcaller("get", "k", default=1) if False else 0, op.methodcaller("append", 1)([]), op.methodcaller("split", maxsplit=1)("a b c"), op.methodcaller("count", "a").__reduce__()[1], op.methodcaller("count").__reduce__()[0] is op.methodcaller)
for f in (lambda: op.itemgetter(), lambda: op.itemgetter(x=1), lambda: op.itemgetter(1, x=1), lambda: op.itemgetter(1)(), lambda: op.itemgetter(1)(1, 2), lambda: op.itemgetter(1)(x=1), lambda: op.itemgetter(1)([], x=1), lambda: op.itemgetter(1)([]), lambda: op.itemgetter(1)(1), lambda: op.itemgetter("a")({}), lambda: op.itemgetter(1, 2)([1]), lambda: op.itemgetter(1, 2)(1), lambda: op.itemgetter(5)((1, 2)), lambda: op.itemgetter(2**64)((1, 2)), lambda: op.itemgetter(-5)((1, 2)), lambda: op.itemgetter("a")((1, 2)), lambda: op.itemgetter(1).__reduce__(1) and 0,
          lambda: op.attrgetter(), lambda: op.attrgetter(1), lambda: op.attrgetter("a", 1), lambda: op.attrgetter(None), lambda: op.attrgetter(x="a"), lambda: op.attrgetter("a", x=1), lambda: op.attrgetter("a")(), lambda: op.attrgetter("a")(1, 2), lambda: op.attrgetter("a")(x=1), lambda: op.attrgetter("a")(1), lambda: op.attrgetter("a.b")(1), lambda: op.attrgetter("x.y")(A), lambda: op.attrgetter("a", "b")(1), lambda: op.attrgetter("")(1), lambda: op.attrgetter("a..b")(1), lambda: op.attrgetter(".")(A), lambda: op.attrgetter("x")(None),
          lambda: op.methodcaller(), lambda: op.methodcaller(1), lambda: op.methodcaller(None), lambda: op.methodcaller(x=1), lambda: op.methodcaller("a")(), lambda: op.methodcaller("a")(1, 2), lambda: op.methodcaller("a")(x=1), lambda: op.methodcaller("a")(1), lambda: op.methodcaller("count")("a"), lambda: op.methodcaller("append")(1), lambda: op.methodcaller("append", 1, 2)([]), lambda: op.methodcaller("__len__", x=1)([])):
    show(f)
got = op.itemgetter(1)
print(got.__class__.__name__, callable(got), hasattr(got, "x"), hasattr(got, "__dict__"), got.__call__([1, 2]), got.__repr__(), str(got), "__call__" in dir(got), "__reduce__" in dir(got))
show(lambda: setattr(got, "x", 1))
class ReprHolder:
    def __init__(self):
        self.g = None
    def __repr__(self):
        return "H<" + repr(self.g) + ">"
h = ReprHolder()
h.g = op.itemgetter(h)
print(h.g, h)
ha = []
ga = op.methodcaller("m", ha)
ha.append(ga)
print(ga, ha)
gk = op.methodcaller("m", key=ha)
print(repr(gk)[:30])
class Reentrant:
    def __getitem__(self, i):
        return op.itemgetter(0)((i,))
print(op.itemgetter(1, 2)(Reentrant()), sorted([(2, "a"), (1, "b")], key=op.itemgetter(0)), sorted([{"k": 2}, {"k": 1}], key=op.itemgetter("k")), max([(1, 2), (3, 0)], key=op.itemgetter(1)), sorted(["bb", "a"], key=op.methodcaller("__len__")), sorted([A, A.B], key=op.attrgetter("__name__"))[0].__name__, list(map(op.add, [1, 2], [3, 4])), list(map(op.itemgetter(0), [(1,), (2,)])))
"""),
    ('the_modules_themselves', SHOW + """import operator, _operator
print(operator, operator.__name__, operator.__file__ is not None if False else 0, _operator, _operator.__name__, _operator.__package__, _operator.__spec__.origin, _operator.__doc__ is not None, operator.__doc__ == _operator.__doc__, operator.__all__ == sorted(operator.__all__), len(operator.__all__), [n for n in operator.__all__ if not hasattr(_operator, n)])
print(sorted([n for n in vars(_operator) if not n.startswith("__")]), [n for n in dir(_operator) if n.startswith("_") and not n.startswith("__")], operator.add is _operator.add, operator.itemgetter is _operator.itemgetter, operator.__add__ is _operator.add, operator.__lt__ is _operator.lt, operator.__call__ is _operator.call, operator._compare_digest is _operator._compare_digest if hasattr(operator, "_compare_digest") else None)
for n in ("add", "truth", "concat", "countOf", "length_hint", "call", "abs", "pow", "_compare_digest", "is_none", "index"):
    f = getattr(_operator, n)
    print(n, f, type(f).__name__, f.__name__, f.__qualname__, f.__module__, callable(f))
print(operator.attrgetter.__module__, _operator.attrgetter.__qualname__, type(_operator.add) is type(len), repr(_operator.add) == "<built-in function add>", isinstance(_operator.add, type(len)))
show(lambda: setattr(_operator.add, "x", 1))
show(lambda: _operator.nothing)
show(lambda: operator.nothing)
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
