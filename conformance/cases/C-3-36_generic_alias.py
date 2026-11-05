# clause: C-3-36
# spec: section 3
# status: P1
# source: PEP 585, Objects/abstract.c (PyObject_GetItem), Objects/genericaliasobject.c
"""Subscripting a class: type[int], __class_getitem__, a metaclass's __getitem__ first, and the
alias a built-in type gives: what it holds, what it passes on to its origin, what it keeps for
itself, and substitution through __typing_subst__, the protocol TypeVar implements."""
# ruff: noqa: F821, E721  # a str as a type argument, and == of aliases, are what this case is about
from types import GenericAlias


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


# ---- what subscripting a class asks
class WithGetitem:
    def __class_getitem__(cls, item: object) -> tuple[object, object]:
        return (cls, item)


class Child(WithGetitem):
    pass


class Meta(type):
    def __getitem__(cls, item: object) -> str:
        return "meta " + repr(item)


class ViaMeta(metaclass=Meta):
    def __class_getitem__(cls, item: object) -> str:
        return "never"


class NoneHook:
    __class_getitem__ = None


class Plain:
    pass


print("hook:", WithGetitem[1] == (WithGetitem, 1), Child["x"] == (Child, "x"), WithGetitem[1, 2] == (WithGetitem, (1, 2)))  # type: ignore[misc]
print("kind:", type(vars(WithGetitem)["__class_getitem__"]).__name__, WithGetitem.__class_getitem__.__self__ is WithGetitem)  # type: ignore[attr-defined]
print("meta:", ViaMeta[3], ViaMeta["k"])
print("not subscriptable:", failed(lambda: Plain[int]), failed(lambda: NoneHook[int]), failed(lambda: str[int]), failed(lambda: int[int]), failed(lambda: object[int]))  # type: ignore[misc]
print("type:", type[int], type[int].__origin__ is type, type[int].__args__ == (int,), type(type[int]) is GenericAlias)


class TypeMeta(type):
    pass


print("a subclass of type:", failed(lambda: TypeMeta[int]))  # type: ignore[misc]


# ---- the built-in types
for base, item in ((list, int), (dict, (str, int)), (set, str), (frozenset, str), (tuple, (int, ...)), (tuple, ())):
    a = base[item]
    print(repr(a), type(a).__name__, a.__origin__ is base, a.__args__, a.__parameters__, a.__unpacked__)
print("hook of a type:", list.__class_getitem__(int) == list[int], type(vars(list)["__class_getitem__"]).__name__, list.__class_getitem__.__self__ is list)  # type: ignore[attr-defined]
print("arguments:", failed(lambda: list.__class_getitem__()), failed(lambda: list.__class_getitem__(1, 2)))  # type: ignore[call-arg]
print("own class:", type(list[int]).__name__, type(list[int]).__module__, type(list[int]).__qualname__, repr(type(list[int])), list[int].__class__ is GenericAlias)  # type: ignore[comparison-overlap]


# ---- repr
class Outer:
    class Inner:
        pass


def function() -> None:
    pass


print(list[Outer])
print(list[Outer.Inner])
print(list[None], list[type(None)], list[...], list["forward"], list[1], list[function])  # type: ignore[misc,name-defined,valid-type]
print(dict[str, list[int]], list[list[list[int]]], tuple[()], tuple[int, ...])
print(list[[int, str]], list[[]], list[(int, str)], list[((int, str),)])  # type: ignore[misc,valid-type]
print(GenericAlias(Outer.Inner, (int, str)), GenericAlias(function, int))  # type: ignore[arg-type]


class NoQualname:
    def __repr__(self) -> str:
        return "<no qualname>"


class NoModule:
    __qualname__ = "Q"
    __module__ = None  # type: ignore[assignment]
    def __repr__(self) -> str:
        return "<no module>"


class Looks:
    __origin__ = 1
    __args__ = 2
    def __repr__(self) -> str:
        return "<looks generic>"


print(list[NoQualname()], list[NoModule()], list[Looks()])  # type: ignore[misc]


# ---- the constructor
print("constructor:", GenericAlias(list, int) == list[int], GenericAlias(list, (int,)) == list[int], GenericAlias(list, [int]).__args__, GenericAlias(1, 2).__origin__, GenericAlias(1, 2).__args__)  # type: ignore[arg-type]
print("its arguments:", failed(lambda: GenericAlias()), failed(lambda: GenericAlias(list)), failed(lambda: GenericAlias(list, int, str)), failed(lambda: GenericAlias(list, args=int)))  # type: ignore[call-arg]


# ---- comparison and hash
print("equal:", list[int] == list[int], list[int] == list[str], list[int] == dict[int], list[int] != list[str], list[int] != list[int], list[int] == list, list == list[int], list[int] == 1)  # type: ignore[comparison-overlap,misc]
print("hash:", hash(list[int]) == hash(list[int]), hash(list[int]) == hash(list) ^ hash((int,)), {list[int]: 1}[list[int]], failed(lambda: hash(list[[int]])), failed(lambda: hash(list[{}])))  # type: ignore[misc,valid-type]
print("order:", failed(lambda: list[int] < list[int]), failed(lambda: list[int] < 1))  # type: ignore[operator]


# ---- calling: the origin, and __orig_class__ where it can be set
class Made:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args = (args, kwargs)


class Slotted:
    __slots__ = ()


class Refuses:
    def __setattr__(self, name: str, value: object) -> None:
        raise TypeError("no")


class Raises:
    def __setattr__(self, name: str, value: object) -> None:
        raise ValueError("raises")


m = GenericAlias(Made, int)(1, k=2)  # type: ignore[operator]
print("call:", type(m).__name__, m.args, m.__orig_class__ == GenericAlias(Made, int))
print(type(GenericAlias(Slotted, int)()).__name__, type(GenericAlias(Refuses, int)()).__name__, failed(lambda: GenericAlias(Raises, int)()))  # type: ignore[operator]
print(dict[str, int](), dict[str, int]({"a": 1}), list[int]([1, 2]), tuple[int, ...]((1,)), failed(lambda: GenericAlias(1, 2)()))  # type: ignore[arg-type,operator]
print("callable:", callable(list[int]), callable(GenericAlias(1, 2)))  # type: ignore[arg-type]


# ---- attributes: the origin's, but for its own
class Origin:
    """Origin's doc"""
    attribute = "from the class"
    def method(self) -> str:
        return "method"
    @classmethod
    def cm(cls) -> str:
        return cls.__name__
    def __copy__(self) -> None:
        pass
    def __deepcopy__(self, memo: object) -> None:
        pass


alias = GenericAlias(Origin, int)
print("passed on:", alias.__name__, alias.__qualname__, alias.__module__, alias.__doc__, alias.attribute, alias.cm(), alias.method(Origin()), alias.__mro__ == Origin.__mro__)
print("of list:", list[int].__name__, list[int].__qualname__, list[int].__module__, list[int].append is list.append, list[int].__len__ is list.__len__, list[int].__dict__ is not None)
print("missing:", failed(lambda: alias.nothing), hasattr(alias, "nothing"), getattr(alias, "nothing", "default"))
print("not passed on:", hasattr(alias, "__bases__"), hasattr(alias, "__copy__"), hasattr(alias, "__deepcopy__"))
print("own:", alias.__class__ is GenericAlias, alias.__origin__ is Origin, alias.__args__, alias.__parameters__, alias.__unpacked__, alias.__typing_unpacked_tuple_args__)
print("reduce:", alias.__reduce__() == (GenericAlias, (Origin, (int,))), alias.__reduce_ex__(2) == (GenericAlias, (Origin, (int,))))
print("entries:", alias.__mro_entries__(()) == (Origin,), failed(lambda: alias.__mro_entries__()))  # type: ignore[call-arg]
print("read only:", failed(lambda: setattr(alias, "__origin__", 1)), failed(lambda: setattr(alias, "__args__", 1)), failed(lambda: setattr(alias, "__unpacked__", 1)), failed(lambda: setattr(alias, "__parameters__", 1)), failed(lambda: setattr(alias, "x", 1)))
print("deleting:", failed(lambda: delattr(alias, "__origin__")), failed(lambda: delattr(alias, "__name__")), failed(lambda: delattr(alias, "x")))
d = dir(alias)
print("dir:", "attribute" in d, "__origin__" in d, "__args__" in d, "__parameters__" in d, "__mro_entries__" in d, "__reduce_ex__" in d, "__bases__" in dir(Origin), "__unpacked__" in d)
print("own class's dict:", "__origin__" in vars(GenericAlias), type(vars(GenericAlias)["__origin__"]).__name__, type(vars(GenericAlias)["__parameters__"]).__name__)
print("non-str name:", failed(lambda: alias.__getattribute__(1)))  # type: ignore[arg-type]
print("hasattr of an int:", GenericAlias(1, 2).__class__ is GenericAlias, failed(lambda: GenericAlias(1, 2).__name__))  # type: ignore[arg-type]


# ---- the checks
print("checks:", failed(lambda: isinstance([], list[int])), failed(lambda: issubclass(list, list[int])), failed(lambda: isinstance([], (int, list[int]))), isinstance([], (list, list[int])))  # type: ignore[misc]
print("first argument:", isinstance(list[int], GenericAlias), isinstance(list[int], type), failed(lambda: issubclass(list[int], list)))


# ---- a base class
class FromAlias(dict[str, int]):
    pass


print("base:", FromAlias.__bases__, FromAlias.__orig_bases__, FromAlias.__mro__[1].__name__, "__orig_bases__" in vars(FromAlias), FromAlias({"a": 1})["a"])  # type: ignore[attr-defined]


class Sub2(GenericAlias):
    __slots__ = ()
    def __repr__(self) -> str:
        return "Sub2:" + super().__repr__()


s2 = Sub2(list, int)
print("a subclass:", s2, type(s2).__name__, s2 == list[int], list[int] == s2, s2.__origin__ is list, s2.__name__, hash(s2) == hash(list[int]))


class Sub3(GenericAlias):
    def __new__(cls, origin: object, args: object) -> Sub3:
        self = super().__new__(cls, origin, (args, "extra"))  # type: ignore[arg-type]
        return self


print(Sub3(list, int).__args__, Sub3(list, int).__class__.__name__)


class HasHook:
    __class_getitem__ = classmethod(GenericAlias)  # type: ignore[var-annotated]


print("as a hook:", HasHook[int], HasHook[int].__origin__ is HasHook, HasHook[int, str].__args__, type(HasHook[int]) is GenericAlias, HasHook[int]().__orig_class__ == HasHook[int])  # type: ignore[misc]


# ---- substitution, by the protocol TypeVar implements
class Var:
    def __init__(self, name: str) -> None:
        self.name = name
    def __repr__(self) -> str:
        return "~" + self.name
    def __typing_subst__(self, arg: object) -> object:
        SUBSTS.append((self.name, arg))
        return arg


SUBSTS: list[tuple[str, object]] = []
T = Var("T")
S = Var("S")
print("parameters:", list[T].__parameters__ == (T,), dict[T, S].__parameters__ == (T, S), dict[T, T].__parameters__ == (T,), dict[str, list[T]].__parameters__ == (T,), list[[T, S]].__parameters__ == (T, S), list[(T, (S,))].__parameters__ == (T, S), list[int].__parameters__)  # type: ignore[attr-defined,misc,valid-type]
print(repr(list[T]), repr(dict[T, list[S]]), repr(list[[T]]))  # type: ignore[valid-type]
print("cached:", list[T].__parameters__ is not None, (lambda a: a.__parameters__ is a.__parameters__)(list[T]))  # type: ignore[attr-defined,valid-type]
print("one:", list[T][int], list[T][int] == list[int], SUBSTS)  # type: ignore[valid-type]
SUBSTS.clear()
print("two:", dict[T, S][str, int], dict[T, list[S]][str, int], dict[S, T][str, int], SUBSTS)  # type: ignore[valid-type]
SUBSTS.clear()
print("repeat:", dict[T, T][int], list[[T]][str], list[[T, S]][str, int], list[(T, S)][str, int], SUBSTS)  # type: ignore[misc,valid-type]
SUBSTS.clear()
print("partial:", dict[T, S][int, T].__parameters__ == (T,), repr(dict[T, S][int, T]))  # type: ignore[valid-type]
print("not generic:", failed(lambda: list[int][str]), failed(lambda: list[int][()]))
print("wrong number:", failed(lambda: list[T][int, str]), failed(lambda: dict[T, S][int]), failed(lambda: list[T][()]))  # type: ignore[valid-type]
print("keeps its subclass away:", type(Sub2(list, T)[int]).__name__)


class Stale:
    def __repr__(self) -> str:
        return "<stale>"


stale = Stale()
late = list[stale]  # type: ignore[valid-type]
print("late:", late.__parameters__)  # type: ignore[attr-defined]
Stale.__typing_subst__ = lambda self, arg: arg  # type: ignore[attr-defined]
print("not found:", failed(lambda: GenericAlias(list, (T, stale))[int]))


class Params:
    __parameters__ = (T, S)
    def __getitem__(self, item: object) -> tuple[str, object]:
        return ("Params", item)
    def __repr__(self) -> str:
        return "<params>"


class ParamsNotTuple:
    __parameters__ = 5
    def __repr__(self) -> str:
        return "<not a tuple>"


print("an argument's own parameters:", list[Params()].__parameters__ == (T, S), list[Params()][int, str], list[ParamsNotTuple()].__parameters__)  # type: ignore[misc]


class Prepared:
    def __typing_subst__(self, arg: object) -> object:
        return arg
    def __typing_prepare_subst__(self, alias: object, args: object) -> object:
        print("prepare", type(alias).__name__, args)
        return (*args, "added")  # type: ignore[misc]
    def __repr__(self) -> str:
        return "<prepared>"


class Other:
    __typing_prepare_subst__ = None
    def __typing_subst__(self, arg: object) -> object:
        return arg
    def __repr__(self) -> str:
        return "<other>"


P = Prepared()
print("prepared:", dict[P, Other()][int])  # type: ignore[misc,valid-type]


class ClassWithSubst:
    @staticmethod
    def __typing_subst__(arg: object) -> object:
        return arg
    __parameters__ = (T,)


print("a class is never a parameter:", list[ClassWithSubst].__parameters__)  # type: ignore[attr-defined]


# ---- iterating: a starred alias
it = iter(tuple[int, str])  # type: ignore[call-overload]
star = next(it)
print("star:", repr(star), star.__unpacked__, star.__typing_unpacked_tuple_args__ == (int, str), type(it).__name__, failed(lambda: next(it)), iter(it) is it)
print("list star:", repr(next(iter(list[int]))), next(iter(list[int])).__unpacked__, next(iter(list[int])).__typing_unpacked_tuple_args__)  # type: ignore[call-overload]
print("equal stars:", next(iter(list[int])) == next(iter(list[int])), next(iter(list[int])) == list[int], list[int] == next(iter(list[int])))  # type: ignore[call-overload]
print("starred in a tuple:", tuple[*tuple[int, str]], tuple[int, *tuple[str, ...]], [*tuple[int]][0].__unpacked__)  # type: ignore[misc]
print("reduce of a star:", star.__reduce__()[0] is next, type(star.__reduce__()[1][0]).__name__, iter(tuple[int]).__reduce__()[0] is iter)  # type: ignore[call-overload]
print("flattened:", dict[T, S][*tuple[int, str]], failed(lambda: list[T][*tuple[int, ...]]))  # type: ignore[misc,valid-type]
print("substituted star:", next(iter(tuple[T]))[int].__unpacked__, repr(next(iter(tuple[T]))[int]))  # type: ignore[call-overload,valid-type]


class Unpacked:
    __typing_is_unpacked_typevartuple__ = True
    def __typing_subst__(self, arg: object) -> object:
        return (arg, arg)
    def __repr__(self) -> str:
        return "<unpacked>"


class UnpackedBad(Unpacked):
    def __typing_subst__(self, arg: object) -> object:
        return arg


class OwnArgs:
    __typing_unpacked_tuple_args__ = (int, str)
    def __repr__(self) -> str:
        return "<own args>"


class OwnArgsEllipsis:
    __typing_unpacked_tuple_args__ = (int, ...)
    def __repr__(self) -> str:
        return "<ellipsis args>"


print("unpacking:", tuple[Unpacked()][int], failed(lambda: tuple[UnpackedBad()][int]), dict[T, S][OwnArgs()], failed(lambda: list[T][OwnArgs()]), list[T][OwnArgsEllipsis()])  # type: ignore[misc,valid-type]
