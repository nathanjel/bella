# clause: C-3-27
# spec: section 3
# status: P1
# source: Gate 0 task 4, step A3 (the census of docs/measurements.md, 2026-11-02)
"""Class statements as CPython runs them: decorators, bases and keywords evaluated in order,
the most derived metaclass, __prepare__'s mapping receiving every store of the body (the
implicit ones included), __mro_entries__, __init_subclass__ and __set_name__, the __class__
cell and zero-argument super(), class-body scoping, private-name mangling,
__static_attributes__, __qualname__, __firstlineno__ and cleaned docstrings."""
from collections.abc import Callable

trace: list[str] = []


def t[T](name: str, value: T) -> T:
    trace.append(name)
    return value


def deco(name: str) -> Callable[[type], type]:
    trace.append("evaluate " + name)

    def apply(c: type) -> type:
        trace.append("apply " + name + " to " + c.__name__)
        return c
    return apply


class Recorder(dict[str, object]):
    def __setitem__(self, key: str, value: object) -> None:
        trace.append("store " + key)
        super().__setitem__(key, value)


class Meta(type):
    @classmethod
    def __prepare__(mcls, name: str, bases: tuple[type, ...], /, **kw: object) -> Recorder:
        trace.append(f"prepare {name} {sorted(kw)}")
        return Recorder()

    def __new__(mcls, name: str, bases: tuple[type, ...], ns: dict[str, object], **kw: object) -> Meta:
        trace.append(f"new {name} {sorted(kw)}")
        return super().__new__(mcls, name, bases, dict(ns))

    def __init__(cls, name: str, bases: tuple[type, ...], ns: dict[str, object], **kw: object) -> None:
        super().__init__(name, bases, ns)


class Base:
    def __init_subclass__(cls, /, flavour: str | None = None, **kw: object) -> None:
        trace.append(f"init_subclass {cls.__name__} {flavour}")
        super().__init_subclass__(**kw)


class Named:
    def __set_name__(self, owner: type, name: str) -> None:
        trace.append(f"set_name {owner.__name__}.{name}")


@deco("outer")
@deco("inner")
class C(t("base", Base), metaclass=t("meta", Meta), flavour=t("keyword", "sour")):  # type: ignore[misc, call-arg, metaclass]  # computed base and metaclass
    t("body", None)
    x = 1
    attr = Named()

    def method(self) -> int:
        return self.x


print(trace)
trace.clear()


class Sub(C, flavour="sweet"):  # type: ignore[call-arg]  # Base.__init_subclass__ takes it
    pass


print(trace, type(Sub).__name__)
trace.clear()


def error(make: Callable[[], object]) -> str:
    try:
        make()
    except Exception as exc:  # noqa: BLE001  # the type is the observable
        return type(exc).__name__
    return "no error"


class M1(type):
    pass


class M2(type):
    pass


class M3(M1):
    pass


class A(metaclass=M1):
    pass


class B(metaclass=M2):
    pass


class Derived(metaclass=M3):
    pass


def conflict() -> None:
    class X(A, B):  # type: ignore[metaclass]  # the metaclass conflict is the point
        pass


class Y(A, Derived):
    pass


print(error(conflict), type(Y).__name__)


class Entries:
    def __mro_entries__(self, bases: tuple[object, ...]) -> tuple[type, ...]:
        return (int, A)


class E(Entries(), object):  # type: ignore[misc]  # noqa: UP004  # an __mro_entries__ base before a class
    pass


print([k.__name__ for k in E.__mro__], "__orig_bases__" in vars(E))


class DropsCell(type):
    def __new__(mcls, name: str, bases: tuple[type, ...], ns: dict[str, object]) -> DropsCell:
        kept: dict[str, object] = {}
        for k, v in ns.items():
            if k != "__classcell__":
                kept[k] = v
        return super().__new__(mcls, name, bases, kept)


def dropped() -> None:
    class W(metaclass=DropsCell):
        def m(self) -> type:
            return __class__  # type: ignore[name-defined, no-any-return]  # the implicit cell


print(error(dropped))

# scopes
x = "global x"


def enclosing() -> type:
    v = "enclosing v"

    class K:
        seen = v
        w = "class w"

        def method(self) -> tuple[str, str]:
            return v, x
    return K


K = enclosing()
print(K().method(), K.seen, K.w)  # type: ignore[attr-defined]  # computed class


def late() -> None:
    v = "enclosing"

    class L:
        try:
            print(v)
        except NameError as exc:
            print("NameError", exc.name)
        v = "class"


late()
base = "module base"


class Comprehension:
    base = 3
    items = [i for i in range(base)]
    inner = [base for i in range(1)]


print(Comprehension.items, Comprehension.inner)


# names
class Private:
    """  The doc.
        Second line."""
    __hidden = 1

    def __method(self, n: int) -> int:
        self.__stored = n
        return self.__hidden + n

    def call(self) -> tuple[int, int]:
        return self.__method(5), self.__stored

    class __Inner:
        pass

    def nested(self) -> None:
        def helper(self: Private) -> None:
            self.from_nested = 1  # type: ignore[attr-defined]  # recorded in __static_attributes__
        helper(self)

    def augmented(self) -> None:
        self.aug += 1  # type: ignore[attr-defined]  # an augmented target is not recorded

    def annotated(self) -> None:
        self.ann: int = 1


print(sorted([k for k in vars(Private) if not k.startswith("__")]))
print(Private().call(), Private._Private__Inner.__qualname__, Private.__static_attributes__)  # type: ignore[attr-defined]  # mangled names
print(repr(Private.__doc__), Private.__firstlineno__, Private.__qualname__)  # type: ignore[attr-defined]  # 3.13+


def outer() -> type:
    class InFunction:
        class Nested:
            def m(self) -> None:
                pass
    return InFunction


print(outer().__qualname__, outer().Nested.__qualname__, outer().Nested.m.__qualname__)  # type: ignore[attr-defined]  # computed class


# super
class P:
    def who(self) -> str:
        return "P"

    @classmethod
    def make(cls) -> str:
        return "P.make " + cls.__name__


class Q(P):
    def who(self) -> str:
        return "Q>" + super().who()

    @classmethod
    def make(cls) -> str:
        return "Q>" + super().make()

    def via_class(self) -> str:
        return __class__.__name__  # type: ignore[name-defined, no-any-return]  # the implicit cell

    @staticmethod
    def static() -> str:
        return super().who()  # type: ignore[misc, no-any-return]  # no arguments: the RuntimeError is the point


class R(Q):
    def who(self) -> str:
        return "R>" + super().who()


print(R().who(), R.make(), R().via_class(), error(Q.static))
