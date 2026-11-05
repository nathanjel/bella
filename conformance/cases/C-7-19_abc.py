# clause: C-7-19
# spec: section 7
# status: P1
# source: PEP 3119, Lib/abc.py and Modules/_abc.c (the first native module a frozen module needs)
"""Abstract classes: which class cannot be made and why, the abstract names a class inherits and
drops, virtual subclasses, the hook, and when the caches answer without asking the hook again.
The token's value depends on what else has registered, so only its changes are shown."""
# ruff: noqa: B024  # ABCs with no abstract method are what this case is about
import _abc  # type: ignore[import-not-found]
import abc
from abc import ABC, ABCMeta, abstractmethod


def failed(f: object) -> str:
    try:
        f()  # type: ignore[operator]
    except Exception as exc:
        return type(exc).__name__
    return "no error"


# ---- abstract names, inherited and dropped
class Shape(ABC):
    @abstractmethod
    def area(self) -> int: ...
    @abstractmethod
    def name(self) -> str: ...
    def twice(self) -> int:
        return self.area() * 2


class Square(Shape):
    def area(self) -> int:
        return 4


class Named(Square):
    def name(self) -> str:
        return "named"


print("abstract:", Shape.__abstractmethods__ == {"area", "name"}, Square.__abstractmethods__ == {"name"}, Named.__abstractmethods__ == set())
print("type:", type(Shape.__abstractmethods__).__name__, type(Named.__abstractmethods__).__name__)
print("make:", failed(Shape), failed(Square), failed(Named), Named().twice(), Named().name())
print("object's:", failed(lambda: object.__new__(Shape)))  # type: ignore[type-abstract]


class Reopened(Named):
    @abstractmethod
    def name(self) -> str: ...


print("reopened:", Reopened.__abstractmethods__ == {"name"}, failed(Reopened))


# ---- the descriptors: an abstract callable makes them abstract
class Described(ABC):
    @classmethod
    @abstractmethod
    def c(cls) -> int: ...
    @staticmethod
    @abstractmethod
    def s() -> int: ...
    @property
    @abstractmethod
    def p(self) -> int: ...
    @classmethod
    def plain_c(cls) -> int:
        return 1
    @staticmethod
    def plain_s() -> int:
        return 2
    @property
    def plain_p(self) -> int:
        return 3


print("descriptors:", Described.__abstractmethods__ == {"c", "s", "p"})
for n in ("c", "s", "p", "plain_c", "plain_s", "plain_p"):
    print(n, vars(Described)[n].__isabstractmethod__)


class Setter(ABC):
    @property
    def only_set(self) -> int:
        return 1
    @only_set.setter
    @abstractmethod
    def only_set(self, v: int) -> None: ...
    @property
    def only_del(self) -> int:
        return 1
    @only_del.deleter
    @abstractmethod
    def only_del(self) -> None: ...


print("accessors:", Setter.__abstractmethods__ == {"only_set", "only_del"}, property().__isabstractmethod__)


class OldStyle(ABC):
    @abc.abstractclassmethod  # type: ignore[arg-type]
    def c(cls) -> int: ...  # type: ignore[empty-body]
    @abc.abstractstaticmethod
    def s() -> int: ...  # type: ignore[empty-body]
    @abc.abstractproperty
    def p(self) -> int: ...


print("old style:", OldStyle.__abstractmethods__ == {"c", "s", "p"})
print("kinds:", abc.abstractclassmethod.__mro__[1].__name__, abc.abstractstaticmethod.__mro__[1].__name__, abc.abstractproperty.__mro__[1].__name__)
print(abc.abstractclassmethod.__isabstractmethod__, abc.abstractstaticmethod.__isabstractmethod__, abc.abstractproperty.__isabstractmethod__)


def plain() -> None:
    pass


print("decorator:", abstractmethod(plain) is plain, plain.__isabstractmethod__)  # type: ignore[attr-defined]


# ---- an attribute set later counts only after update_abstractmethods
class Later(ABC):
    @abstractmethod
    def f(self) -> None: ...


Later.f = lambda self: None  # type: ignore[method-assign]
print("later:", Later.__abstractmethods__ == {"f"}, failed(Later))
print("updated:", abc.update_abstractmethods(Later) is Later, Later.__abstractmethods__ == set(), failed(Later))  # type: ignore[type-abstract]


class Plain:
    pass


print("not an ABC:", abc.update_abstractmethods(Plain) is Plain, hasattr(Plain, "__abstractmethods__"))


class Hand:
    @abstractmethod
    def f(self) -> None: ...


print("without the metaclass:", hasattr(Hand, "__abstractmethods__"), failed(Hand))
Hand.__abstractmethods__ = frozenset({"f"})  # type: ignore[attr-defined]
print("set by hand:", failed(Hand))
del Hand.__abstractmethods__  # type: ignore[attr-defined]
print("deleted:", failed(Hand), hasattr(Hand, "__abstractmethods__"))


# ---- the classes themselves
print("names:", ABC.__name__, ABC.__module__, ABCMeta.__name__, ABCMeta.__module__, type(ABC).__name__, ABC.__slots__, ABC.__mro__[1].__name__)
print("impl:", "_abc_impl" in vars(Shape), type(Shape._abc_impl).__name__, type(Shape._abc_impl).__module__, type(Shape._abc_impl).__qualname__)  # type: ignore[attr-defined]
print("impl type:", repr(type(Shape._abc_impl)), type(Shape._abc_impl).__mro__[1].__name__, type(type(Shape._abc_impl)).__name__)  # type: ignore[attr-defined]
print("own impl:", Shape._abc_impl is not Square._abc_impl, type(Shape._abc_impl)(1, k=2) is not None)  # type: ignore[attr-defined]
print("impl doc:", type(Shape._abc_impl).__doc__)  # type: ignore[attr-defined]
Made = ABCMeta("Made", (Shape,), {"area": lambda self: 1, "name": lambda self: "m", "extra": 5})
print("functional:", Made.__name__, Made.__abstractmethods__ == set(), Made().area(), Made.extra)  # type: ignore[attr-defined]


class Kw(ABC):
    seen: object = None
    def __init_subclass__(cls, flag: int = 0) -> None:
        Kw.seen = flag


class KwChild(Kw, flag=3):
    pass


print("keywords:", Kw.seen)


class Meta2(ABCMeta):
    def __new__(mcls, name: str, bases: tuple[type, ...], ns: dict[str, object]) -> Meta2:
        cls = super().__new__(mcls, name, bases, ns)
        print("made", name, hasattr(cls, "_abc_impl"))
        return cls


class ViaMeta2(metaclass=Meta2):
    @abstractmethod
    def f(self) -> None: ...


print("meta:", type(ViaMeta2).__name__, ViaMeta2.__abstractmethods__ == {"f"})


# ---- virtual subclasses
class Base(ABC):
    def shared(self) -> str:
        return "from Base"


class Virtual:
    pass


class ViaVirtual(Virtual):
    pass


token = abc.get_cache_token()
print("before:", issubclass(Virtual, Base), isinstance(Virtual(), Base), issubclass(ViaVirtual, Base))
print("register:", Base.register(Virtual) is Virtual, abc.get_cache_token() == token + 1)  # type: ignore[operator]
print("after:", issubclass(Virtual, Base), isinstance(Virtual(), Base), issubclass(ViaVirtual, Base), isinstance(ViaVirtual(), Base))
print("no method:", hasattr(Virtual, "shared"), Base in Virtual.__mro__, Base in ViaVirtual.__mro__, len(Virtual.__bases__))


@Base.register
class Decorated:
    pass


print("decorated:", issubclass(Decorated, Base), Decorated.__name__)
print("builtin:", issubclass(int, Base), Base.register(int) is int, issubclass(int, Base), isinstance(1, Base), isinstance(True, Base), issubclass(bool, Base))
token = abc.get_cache_token()
print("already:", Base.register(Virtual) is Virtual, abc.get_cache_token() == token, Base.register(Base) is Base, abc.get_cache_token() == token)
print("not a class:", failed(lambda: Base.register(1)), failed(lambda: Base.register("x")))  # type: ignore[arg-type]


class Chain1(ABC):
    pass


class Chain2(ABC):
    pass


class Chain3(ABC):
    pass


Chain1.register(Chain2)
Chain2.register(Chain3)
print("chain:", issubclass(Chain3, Chain1), issubclass(Chain1, Chain3), issubclass(Chain2, Chain1), issubclass(Chain2, Chain3))
print("cycle:", failed(lambda: Chain3.register(Chain1)), failed(lambda: Chain2.register(Chain1)))


class Sub1(Base):
    pass


class Sub2(Sub1):
    pass


class Below:
    pass


Sub2.register(Below)
print("registered below:", issubclass(Below, Sub2), issubclass(Below, Sub1), issubclass(Below, Base), isinstance(Below(), Base))
print("subclasses:", [c.__name__ for c in Base.__subclasses__()], [c.__name__ for c in Sub1.__subclasses__()], Sub2.__subclasses__())
print("arg 1:", failed(lambda: issubclass(1, Base)), failed(lambda: isinstance(1, 1)), isinstance("s", Sub2))  # type: ignore[arg-type]


# ---- the hook, and when it is asked
ASKED: list[str] = []


class Hooked(ABC):
    @classmethod
    def __subclasshook__(cls, C: type) -> object:  # type: ignore[override]
        ASKED.append(C.__name__)
        if C.__name__ == "Yes":
            return True
        if C.__name__ == "No":
            return False
        if C.__name__ == "Bad":
            return 1
        return NotImplemented


class Yes:
    pass


class No:
    pass


class Bad:
    pass


class Neither:
    pass


class HookedChild(Hooked):
    pass


class No2(Hooked):
    pass


print("yes:", issubclass(Yes, Hooked), issubclass(Yes, Hooked), isinstance(Yes(), Hooked), ASKED)
ASKED.clear()
print("no:", issubclass(No, Hooked), issubclass(No, Hooked), isinstance(No(), Hooked), ASKED)
ASKED.clear()
print("neither:", issubclass(Neither, Hooked), issubclass(Neither, Hooked), ASKED)
ASKED.clear()
print("child:", issubclass(HookedChild, Hooked), issubclass(HookedChild, Hooked), ASKED)
ASKED.clear()
print("bad:", failed(lambda: issubclass(Bad, Hooked)), failed(lambda: issubclass(Bad, Hooked)), ASKED)
ASKED.clear()
Base.register(Bad)
print("any register forgets the negative answers:", issubclass(No, Hooked), issubclass(Neither, Hooked), issubclass(Yes, Hooked), ASKED)
ASKED.clear()
Hooked._abc_caches_clear()  # type: ignore[attr-defined]
print("cleared:", issubclass(Yes, Hooked), issubclass(No, Hooked), ASKED)
ASKED.clear()


class Reg(ABC):
    pass


class InReg:
    pass


Reg.register(InReg)
print("registry cleared:", issubclass(InReg, Reg))
Reg._abc_caches_clear()  # type: ignore[attr-defined]
Reg._abc_registry_clear()  # type: ignore[attr-defined]
print(issubclass(InReg, Reg))


# ---- __class__ can lie: isinstance asks about it and about the real type
class Liar:
    @property  # type: ignore[misc]
    def __class__(self) -> type:
        return Virtual


class HonestMeta(ABC):
    pass


HonestMeta.register(Virtual)
print("lie:", isinstance(Liar(), HonestMeta), issubclass(Liar, HonestMeta), type(Liar()).__name__)


class Liar2:
    @property  # type: ignore[misc]
    def __class__(self) -> type:
        raise AttributeError("no class")


print("no __class__:", isinstance(Liar2(), HonestMeta), type(Liar2()).__name__)
HonestMeta.register(Liar2)
print("real type:", isinstance(Liar2(), HonestMeta))


class Liar3:
    @property  # type: ignore[misc]
    def __class__(self) -> object:  # type: ignore[override]
        return 5


class Liar4:
    @property  # type: ignore[misc]
    def __class__(self) -> object:  # type: ignore[override]
        return []


print("not a class:", failed(lambda: isinstance(Liar3(), HonestMeta)), failed(lambda: isinstance(Liar4(), HonestMeta)))


# ---- what a metaclass of an ABC overrides, and the order of the checks
CHECKS: list[str] = []


class Logging(ABCMeta):
    def __subclasscheck__(cls, C: type) -> bool:
        CHECKS.append(cls.__name__ + "<-" + C.__name__)
        return super().__subclasscheck__(C)
    def __instancecheck__(cls, inst: object) -> bool:
        CHECKS.append(cls.__name__ + "?" + type(inst).__name__)
        return super().__instancecheck__(inst)


class L1(metaclass=Logging):
    pass


class L2(L1):
    pass


class L3(L2):
    pass


class Out:
    pass


print("instance:", isinstance(Out(), L1), CHECKS)
CHECKS.clear()
print("again:", isinstance(Out(), L1), CHECKS)
CHECKS.clear()
print("exact skips the check:", isinstance(L1(), L1), CHECKS)
CHECKS.clear()
print("subclass:", isinstance(L3(), L1), CHECKS)
CHECKS.clear()
print("descends:", issubclass(int, L1), CHECKS)
CHECKS.clear()
L2.register(Out)
print("registered:", issubclass(Out, L1), CHECKS)
CHECKS.clear()
print("registering asks both ways:", L3.register(Yes) is Yes, CHECKS)
CHECKS.clear()


# ---- a wrong _abc_impl
class Wrong(ABC):
    pass


Wrong._abc_impl = 1  # type: ignore[attr-defined]
print("wrong impl:", failed(lambda: isinstance(1, Wrong)), failed(lambda: issubclass(int, Wrong)), failed(lambda: Wrong.register(int)))
del Wrong._abc_impl  # type: ignore[attr-defined]
print("inherited impl:", hasattr(Wrong, "_abc_impl"), issubclass(Wrong, Wrong), issubclass(int, Wrong))


# ---- the flags collections.abc sets: popped from the class, and the error
class Flagged(ABC):
    __abc_tpflags__ = 1 << 5


print("popped:", "__abc_tpflags__" in vars(Flagged))


def both() -> object:
    class Both(ABC):
        __abc_tpflags__ = (1 << 5) | (1 << 6)
    return Both


print("both:", failed(both))


class NotAnInt(ABC):
    __abc_tpflags__ = "x"


print("popped, not an int:", "__abc_tpflags__" in vars(NotAnInt))


# ---- the native module
print("module:", _abc.__name__, _abc.__package__, _abc.__spec__.origin, _abc.__doc__)
for f in (_abc.get_cache_token, _abc._abc_init, _abc._abc_register, _abc._abc_instancecheck, _abc._abc_subclasscheck, _abc._get_dump, _abc._reset_registry, _abc._reset_caches):
    print(repr(f).partition(" at ")[0], type(f).__name__, f.__module__, f.__name__)
print("int token:", type(_abc.get_cache_token()).__name__, _abc.get_cache_token() == abc.get_cache_token(), abc.get_cache_token is _abc.get_cache_token)
print("arguments:", failed(lambda: _abc._abc_init()), failed(lambda: _abc._abc_register(Base)), failed(lambda: _abc.get_cache_token(1)))
print("not an ABC:", failed(lambda: _abc._abc_instancecheck(int, 1)), failed(lambda: _abc._abc_subclasscheck(int, int)), failed(lambda: _abc._reset_caches(int)))


class Fresh(ABC):
    pass


print("empty dump:", _abc._get_dump(Fresh)[:3] == (set(), set(), set()), len(_abc._get_dump(Fresh)), type(_abc._get_dump(Fresh)[2]).__name__, type(_abc._get_dump(Fresh)[3]).__name__)
_abc._abc_init(Plain)
print("init by hand:", "_abc_impl" in vars(Plain), Plain.__abstractmethods__ == set())  # type: ignore[attr-defined]
