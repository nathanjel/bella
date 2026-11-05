# clause: C-7-21
# spec: section 7
# status: P1
# source: dialect specification section 7 (operator is in the phase-1 closure), Modules/_operator.c
"""operator on its C half: the operators on ints and on a class's special methods, the concatenations
(which are not `+`), the searches, length_hint, _compare_digest, and the three callable classes."""
# ruff: noqa: B018, B912, C408, E721, RUF015
import _operator
import operator as op


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


print(op.add(7, 2), op.sub(7, 2), op.mul(7, 2), op.floordiv(7, 2), op.mod(7, 2), op.pow(7, 2), op.lshift(7, 2), op.rshift(7, 2), op.and_(7, 2), op.or_(7, 2), op.xor(7, 2), op.neg(7), op.pos(7), op.abs(-7), op.inv(7), op.invert(7), op.not_(7), op.truth(7), op.index(7), op.eq(7, 2), op.ne(7, 2), op.lt(7, 2), op.le(7, 2), op.gt(7, 2), op.ge(7, 2), op.is_(7, 7), op.is_not(7, 2), op.is_none(None), op.is_not_none(None))
print(op.iadd(7, 2), op.isub(7, 2), op.imul(7, 2), op.ifloordiv(7, 2), op.imod(7, 2), op.ipow(7, 2), op.ilshift(7, 2), op.irshift(7, 2), op.iand(7, 2), op.ior(7, 2), op.ixor(7, 2), op.add(2**64, 1), op.pow(2, 100), op.index(2**64))  # type: ignore[no-untyped-call]
print(op.getitem([1, 2], 1), op.contains([1], 1), op.countOf([1, 1, 2], 1), op.indexOf([1, 2], 2), op.concat([1], [2]), op.concat("a", "b"), op.concat((1,), (2,)), op.concat(b"a", b"b"), op.length_hint([1, 2]), op.length_hint(5, 9), op.call(max, 1, 2), op.call(sorted, [2, 1], reverse=True))
items = [1]
print(op.iconcat(items, [2]) is items, op.iadd(items, [3]) is items, op.imul(items, 2) is items, items, op.iconcat((1,), (2,)), op.setitem(items, 0, 9), op.delitem(items, 1), items)  # type: ignore[no-untyped-call]
print(op.__add__(1, 2), op.__lt__(1, 2), op.__not__(1), op.__concat__([1], [2]), op.__call__(max, 1, 2), op.add is _operator.add, op.__add__ is _operator.add, op.itemgetter is _operator.itemgetter, op.add, type(op.add).__name__, op.add.__module__, op.itemgetter.__module__, op.itemgetter.__name__)
print(failed(lambda: op.add(1, "a")), failed(lambda: op.add(1)), failed(lambda: op.add(1, 2, 3)), failed(lambda: op.add(a=1, b=2)), failed(lambda: op.neg("a")), failed(lambda: op.index("a")), failed(lambda: op.matmul(1, 2)), failed(lambda: op.floordiv(1, 0)), failed(lambda: op.concat(1, 2)), failed(lambda: op.concat([1], 2)), failed(lambda: op.concat({}, {})), failed(lambda: op.iconcat([1], 2)), failed(lambda: op.countOf(1, 2)), failed(lambda: op.indexOf([1], 2)), failed(lambda: op.length_hint(1, "a")), failed(lambda: op.call()), failed(lambda: _operator._compare_digest(1, 2)), failed(lambda: _operator._compare_digest("é", "é")), failed(lambda: _operator._compare_digest("a", b"a")))  # type: ignore[arg-type,call-arg,call-overload,no-untyped-call]
print(_operator._compare_digest("a", "a"), _operator._compare_digest("a", "b"), _operator._compare_digest("a", "ab"), _operator._compare_digest(b"a", b"a"), _operator._compare_digest(bytearray(b"a"), b"b"))


class Seq:
    def __getitem__(self, i: int) -> int:
        raise IndexError

    def __add__(self, other: object) -> str:
        return "add"

    def __iadd__(self, other: object) -> str:
        return "iadd"


class Hint:
    def __init__(self, v: object) -> None:
        self.v = v

    def __length_hint__(self) -> object:
        return self.v


print(op.concat(Seq(), Seq()), op.concat(Seq(), [1]), op.iconcat(Seq(), [1]), failed(lambda: op.concat(Seq(), 1)), failed(lambda: op.iconcat(Seq(), 1)), op.add(Seq(), 1), op.iadd(Seq(), 1))  # type: ignore[arg-type,no-untyped-call]
print(op.length_hint(Hint(5)), op.length_hint(Hint(NotImplemented), 9), failed(lambda: op.length_hint(Hint("a"))), failed(lambda: op.length_hint(Hint(-1))), failed(lambda: op.length_hint(Hint(2**64))))


class A:
    x = 1

    class B:
        y = 2


print(op.itemgetter(1), op.itemgetter(1, 2), op.itemgetter(1)([1, 2]), op.itemgetter(1, 0)([1, 2]), op.itemgetter("a")({"a": 1}), op.itemgetter(5).__reduce__()[1], op.itemgetter(5, 6).__reduce__()[1])
print(op.attrgetter("x"), op.attrgetter("x", "B.y"), op.attrgetter("x")(A), op.attrgetter("B.y")(A), op.attrgetter("x", "B.y")(A), op.attrgetter("B.y").__reduce__()[1])
print(op.methodcaller("count"), op.methodcaller("count", "a", 1), op.methodcaller("m", x=1), op.methodcaller("count", "a")("aab"), op.methodcaller("split", maxsplit=1)("a b c"), op.methodcaller("count", "a").__reduce__()[1])
print(failed(lambda: op.itemgetter()), failed(lambda: op.itemgetter(x=1)), failed(lambda: op.itemgetter(1)()), failed(lambda: op.itemgetter(1)([])), failed(lambda: op.attrgetter()), failed(lambda: op.attrgetter(1)), failed(lambda: op.attrgetter("a")(1)), failed(lambda: op.methodcaller()), failed(lambda: op.methodcaller(1)), failed(lambda: op.methodcaller("a")(1)), failed(lambda: type("S", (op.itemgetter,), {})), failed(lambda: setattr(op.itemgetter, "x", 1)))  # type: ignore[arg-type,call-arg,call-overload]
print(sorted([(2, "a"), (1, "b")], key=op.itemgetter(0)), sorted(["bb", "a"], key=op.methodcaller("__len__")), list(map(op.add, [1, 2], [3, 4])))
