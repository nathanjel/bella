# clause: C-8-08
# spec: section 8
# status: P1
# source: Gate 0 task 5, the staging prototype (docs/staging.md): staging adds nothing observable
"""@dataclass at runtime with its definition-time effects intact, in order and once each: a
base's __init_subclass__ hook (twice for slots=True, which builds the class again), __set_name__
on a class attribute, class-body statements, a decorator applied after @dataclass, and a default
factory counted per instance. The methods dataclasses generates with exec (spec section 8)
behave as CPython's: __init__ with defaults, keyword-only fields, InitVar and __post_init__,
__repr__, __eq__, ordering, frozen assignment, __slots__, __match_args__, replace, asdict,
astuple, inheritance of fields, and make_dataclass."""
import dataclasses
from dataclasses import KW_ONLY, InitVar, dataclass, field

calls: list[str] = []


def counter() -> list[int]:
    calls.append("factory")
    return [len(calls)]


class Hooked:
    def __init_subclass__(cls, flavour: str = "", **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        print("init_subclass", cls.__name__, repr(flavour), "__dataclass_fields__" in cls.__dict__)


class Tag:
    def __set_name__(self, owner: type, name: str) -> None:
        print("set_name", owner.__name__, name)


def announce[T](cls: type[T]) -> type[T]:
    print("decorated", cls.__name__, sorted(cls.__dict__.get("__dataclass_fields__", {})))
    return cls


@announce
@dataclass(order=True)
class Item(Hooked, flavour="plain"):
    print("class body of Item")
    label = Tag()
    name: str
    qty: int = 1
    tags: list[int] = field(default_factory=counter)
    _: KW_ONLY
    note: str = ""


print("Item fields:", [f.name for f in dataclasses.fields(Item)], "factory calls:", len(calls))


@dataclass(frozen=True, slots=True)
class Point(Hooked):
    x: int
    y: int = 0

    def norm1(self) -> int:
        return abs(self.x) + abs(self.y)


print("Point fields:", [f.name for f in dataclasses.fields(Point)], vars(Point)["__slots__"])


@dataclass
class Account:
    owner: str
    opening: InitVar[int]
    balance: int = field(init=False)
    history: list[str] = field(default_factory=list, repr=False)

    def __post_init__(self, opening: int) -> None:
        self.balance = opening
        self.history.append(f"open {opening}")


@dataclass
class Base:
    a: int
    b: int = 2


@dataclass
class Child(Base):
    c: int = 3
    a: int = 10


Pair = dataclasses.make_dataclass("Pair", [("left", int), ("right", int, field(default=0))], frozen=True)
print("Child fields:", [f.name for f in dataclasses.fields(Child)], "Pair fields:", [f.name for f in dataclasses.fields(Pair)])

first = Item("bolt")
second = Item("nut", 3, note="m4")
print(first, second, "factory calls:", len(calls))
print(first == Item("bolt", tags=[1]), first < second, sorted([second, first])[0].name)
print(dataclasses.replace(second, qty=5), dataclasses.asdict(second), dataclasses.astuple(first))
print(Item.__match_args__, Item.__hash__ is None, "factory calls:", len(calls))
match second:
    case Item(name, qty):
        print("matched", name, qty)

p = Point(3, -4)
try:
    p.x = 1  # type: ignore[misc]  # frozen: the generated __setattr__ raises
except dataclasses.FrozenInstanceError as exc:
    print("frozen:", type(exc).__name__, exc.args)
print(p, p.norm1(), hash(p) == hash(Point(3, -4)), hasattr(p, "__dict__"))

acct = Account("ann", 10)
print(acct, acct.history, [f.name for f in dataclasses.fields(acct)])
print(Child(), Child(1, 2, 3), Pair(1), Pair(1) == Pair(1, 0))
try:
    Item()  # type: ignore[call-arg]  # name is required
except TypeError as exc:
    print("missing argument:", type(exc).__name__)
