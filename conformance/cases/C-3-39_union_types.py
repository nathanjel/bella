# clause: C-3-39
# spec: section 3
# status: P1
# source: dialect specification section 3, Objects/unionobject.c, Objects/typeobject.c (type_or)
"""typing.Union, made by |: which operands may be in one, how they flatten and collapse, equality and hash whatever
the order, what isinstance makes of one, and its substitution of parameters."""
# ruff: noqa: B004, B015, B018, B023, E721, RUF036, UP007, UP045
import types


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


class C:
    pass


class D(C):
    pass


class Meta(type):
    def __or__(cls, other: object) -> str:  # type: ignore[override]
        return "Meta.__or__"

    def __ror__(cls, other: object) -> str:  # type: ignore[override]
        return "Meta.__ror__"


class WithMeta(metaclass=Meta):
    pass


class Unhashable:
    __hash__ = None  # type: ignore[assignment]

    def __eq__(self, other: object) -> bool:
        return True


u = int | str
print(u, repr(u), str(u), type(u).__name__, type(u).__module__, type(u).__qualname__, type(u) is types.UnionType, isinstance(u, types.UnionType), isinstance(u, type), u.__args__, u.__name__, u.__qualname__, u.__module__, u.__origin__ is types.UnionType, u.__parameters__, u.__doc__.splitlines()[0])  # type: ignore[attr-defined,union-attr]
print(int | None, None | int, int | int, int | str | int, (int | str) | float, int | (str | float), (int | str) | (str | float), C | D, D | C, C | C, type(None) | int, int | type(None), None | None if False else 0, list[int] | str, str | list[int], list[int] | list[int], list[int] | list[str], dict[str, int] | None, None | dict[str, int], (int | None) | None, None | (int | None), (int | str) | None, type(int | int).__name__, int | int is int)
print((int | str).__args__, (int | None).__args__, (None | int).__args__, (int | str | float).__args__, (str | int).__args__, (int | (str | float)).__args__, ((int | str) | (float | bool)).__args__, (bool | int).__args__, (object | int).__args__, (list[int] | int).__args__)  # type: ignore[union-attr]

# ---- equality and hash
print(int | str == str | int, int | str != str | int, int | str == int | float, int | str == int, int == int | str, int | str == "a", (int | str) == (int | str | int), hash(int | str) == hash(str | int), hash(int | str) == hash(frozenset((int, str))), len({int | str, str | int, int | float}), {int | str: 1}[str | int], int | str in [str | int], (int | None) == (None | int), (int | str | float) == (float | int | str), (int | str) != (int | str | float), list[int] | str == str | list[int], list[int] | str == list[str] | str, (int | str).__eq__(1), (int | str).__ne__(1), (int | str).__eq__(str | int), (int | str).__ne__(str | int), (int | str).__lt__(str | int), (int | str).__le__(1), (int | str).__gt__(1), (int | str).__ge__(1), failed(lambda: (int | str) < (str | int)), failed(lambda: (int | str) >= 1))  # type: ignore[call-arg,index,operator]

# ---- what isinstance makes of one
print(isinstance(1, int | str), isinstance("a", int | str), isinstance(1.5, int | str), isinstance(None, int | None), isinstance(1, int | None), isinstance(1.5, int | None), issubclass(int, int | str), issubclass(bool, int | str), issubclass(float, int | str), issubclass(type(None), int | None), issubclass(D, C | int), isinstance(D(), C | int), isinstance(1, (int | str, float)), isinstance(1.5, (int | str, float)), issubclass(float, (int | str, float)), failed(lambda: isinstance(1, list[int] | str)), failed(lambda: issubclass(int, list[int] | str)), failed(lambda: isinstance(1, int | list[str])), isinstance(1, int | list[str]) if False else 0)

# ---- what | refuses, and who gets asked
print(failed(lambda: int | 1), failed(lambda: 1 | int), failed(lambda: int | "a"), failed(lambda: "a" | int), failed(lambda: int | 1.5), failed(lambda: int | []), failed(lambda: [] | int), failed(lambda: int | (int,)), failed(lambda: int | {}), failed(lambda: {} | int), failed(lambda: int | {1}), failed(lambda: {1} | int), failed(lambda: None | None), failed(lambda: list[int] | 1), failed(lambda: 1 | list[int]), failed(lambda: list[int] | "a"), failed(lambda: "a" | list[int]), failed(lambda: int & str), failed(lambda: int ^ str), failed(lambda: int + str), failed(lambda: ~int), failed(lambda: -int))  # type: ignore[operator]
print(WithMeta | int, int | WithMeta, WithMeta | None, None | WithMeta, WithMeta | WithMeta, list[int] | WithMeta, WithMeta | list[int], (int | str) | WithMeta, WithMeta | (int | str))
print(type.__or__(int, str), type.__ror__(int, str), type.__or__(int, None), type.__ror__(int, None), type.__or__(int, 1), type.__ror__(int, 1), type.__or__(int, "a"), int.__or__ is not None, failed(lambda: type.__or__(1, int)), failed(lambda: type.__or__(int)), failed(lambda: type.__or__(int, str, float)), failed(lambda: type.__ror__(1, int)), (int).__ror__(1) if False else 0, C.__or__(int) if False else 0, type.__or__(C, int), type.__ror__(C, int), type.__or__(int, list[str]), list[int].__or__(str), list[int].__ror__(str), list[int].__or__(1), list[int].__ror__(1), list[int].__or__(None), list[int].__ror__(None))  # type: ignore[call-arg]
print((int | str).__or__(float), (int | str).__ror__(float), (int | str).__or__(None), (int | str).__ror__(None), (int | str).__or__(int), failed(lambda: (int | str).__or__()), failed(lambda: (int | str).__or__(1, 2)), failed(lambda: (int | str).__ror__()))  # type: ignore[call-arg,operator]

# ---- what a Union does not do
print(failed(lambda: types.UnionType()), failed(lambda: types.UnionType(int, str)), failed(lambda: type(int | str)(int)), failed(lambda: object.__new__(types.UnionType)), failed(lambda: type("X", (types.UnionType,), {})), failed(lambda: (int | str)()), failed(lambda: (int | str)(1)), failed(lambda: setattr(int | str, "__args__", ())), failed(lambda: delattr(int | str, "__args__")), failed(lambda: setattr(int | str, "x", 1)), failed(lambda: delattr(int | str, "x")), failed(lambda: (int | str).nothing), failed(lambda: setattr(int | str, "__name__", "x")), failed(lambda: setattr(int | str, "__origin__", "x")), failed(lambda: setattr(int | str, "__parameters__", ())), failed(lambda: setattr(int | str, "__qualname__", "x")), failed(lambda: setattr(int | str, "__module__", "x")), failed(lambda: list(int | str)), failed(lambda: iter(int | str)), failed(lambda: len(int | str)), failed(lambda: (int | str)[int]), failed(lambda: (int | str)[()]), failed(lambda: (int | str)[0]), failed(lambda: 1 in (int | str)), bool(int | str), not (int | str), hasattr(int | str, "__dict__"), hasattr(int | str, "__weakref__"), hasattr(int | str, "__getitem__"), hasattr(int | str, "__call__"), hasattr(int | str, "__iter__"), hasattr(int | str, "__len__"), hasattr(int | str, "__mro_entries__"), hasattr(types.UnionType, "__class_getitem__"))  # type: ignore[arg-type,call-arg,call-overload,index,misc,operator,union-attr]
try:
    class Sub(int | str):  # type: ignore[misc]
        pass
except TypeError:
    print("cannot subclass")
print(failed(lambda: (int | str).__mro_entries__((int | str,))), failed(lambda: (int | str).__mro_entries__()), failed(lambda: (int | str).__mro_entries__(1, 2)))  # type: ignore[union-attr]
print(types.UnionType[int, str], types.UnionType[int], types.UnionType[int, int], types.UnionType[None], types.UnionType[int, None], types.UnionType[int | str, float], types.UnionType[list[int], str], types.UnionType.__class_getitem__((int, str)), types.UnionType.__class_getitem__(int), failed(lambda: types.UnionType[()]), failed(lambda: types.UnionType.__class_getitem__()), failed(lambda: types.UnionType.__class_getitem__(1, 2)), failed(lambda: types.UnionType.__class_getitem__(())))  # type: ignore[attr-defined,misc]
print(types.UnionType.__name__, types.UnionType.__qualname__, types.UnionType.__module__, repr(types.UnionType), types.UnionType.__base__.__name__, types.UnionType.__mro__[1].__name__, types.UnionType.__doc__.splitlines()[0], type(types.UnionType.__dict__["__args__"]).__name__, repr(types.UnionType.__dict__["__args__"]), type(types.UnionType.__dict__["__name__"]).__name__, repr(types.UnionType.__dict__["__name__"]), types.UnionType.__or__(int | str, float), types.UnionType.__ror__(int | str, float), types.UnionType.__eq__(int | str, str | int), types.UnionType.__hash__(int | str) == hash(int | str), types.UnionType.__repr__(int | str), types.UnionType.__getitem__ is not None, failed(lambda: types.UnionType.__or__(1, 2)) if False else 0, failed(lambda: types.UnionType.__repr__(1)), failed(lambda: types.UnionType.__hash__(1)), failed(lambda: types.UnionType.__eq__(1, 2)), types.UnionType.__dict__["__args__"].__get__(int | str), failed(lambda: types.UnionType.__dict__["__args__"].__get__(1)))  # type: ignore[arg-type,operator,union-attr]
print(sorted([k for k in dir(int | str)]))

# ---- an unhashable member


class Eq:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Eq) and self.n == other.n

    def __repr__(self) -> str:
        return "Eq(" + str(self.n) + ")"


g1 = list[Eq(1)]  # type: ignore[misc,valid-type]
g2 = list[Eq(1)]  # type: ignore[misc,valid-type]
g3 = list[Eq(2)]  # type: ignore[misc,valid-type]
print(failed(lambda: hash(g1)), g1 == g2, g1 == g3)
v = g1 | int
print(v, v.__args__, failed(lambda: hash(v)), v == (int | g2), v == (g2 | int), v == (int | g3), v != (int | g3), v == (int | str), (int | str) == v, g1 | g2, g1 | g3, (g1 | g3).__args__, (g1 | g2 | g3).__args__, ((g1 | int) | g2), failed(lambda: {v}), failed(lambda: {v: 1}), v == v, (g1 | g3 | int) == (g3 | g1 | int), (g1 | g3 | int) == (g1 | int), (g1 | int) == (g1 | g3 | int), (g1 | g3 | int) != (g3 | g1 | int), isinstance(v, types.UnionType))
