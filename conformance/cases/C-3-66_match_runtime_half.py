# clause: C-3-66
# spec: section 3
# status: P1
# source: Gate 1c, the targets' blockers: C-3-17, C-8-08 and C-8-09 compiled stopped at the intrinsic 'match_class'
"""The runtime half of match (MATCH_CLASS, MATCH_KEYS, MATCH_SEQUENCE, MATCH_MAPPING and the length
checks around them): a class pattern reads its positional attributes by __match_args__, then its
keyword ones, each once and all before any sub-pattern is compared; an AttributeError fails the
case, after __getattr__ has had its turn, and any other exception leaves the match; the built-in
types that match themselves by one positional sub-pattern, and their subclasses; a sequence or a
mapping by its type's flag (str, bytes and bytearray are no sequences; a class registered with
collections.abc is one); a sequence pattern asks the length, then unpacks or indexes; a mapping
pattern asks the length, then get() once per key, and **rest copies through keys() and
__getitem__; and the exception each malformed pattern raises, with the case it stops at."""
import collections
import collections.abc
from collections.abc import Iterator

log: list[str] = []


class Missing(AttributeError):
    pass


class Logged:
    __match_args__ = ("a", "b")

    @property
    def a(self) -> object:
        log.append("a")
        return "A"

    @property
    def b(self) -> object:
        log.append("b")
        return "B"

    @property
    def c(self) -> object:
        log.append("c")
        return "C"

    @property
    def sub(self) -> object:
        log.append("sub")
        raise Missing("sub")

    @property
    def boom(self) -> object:
        log.append("boom")
        raise KeyError("boom")

    def __getattr__(self, name: str) -> object:
        log.append(f"getattr {name}")
        raise AttributeError(name)


class Other:
    pass


def classes(obj: object) -> str:
    log.clear()
    match obj:
        case Other():
            result = "other"
        case Logged(1, b=2):
            result = "never: A is not 1"
        case Logged(x, nothing=y):
            result = f"never: {x} {y}"
        case Logged(x, sub=y):
            result = f"never: {x} {y}"
        case Logged(x, y, c=z) if z == "C":
            result = f"logged {x} {y} {z}"
        case _:
            result = "none"
    return f"{result}; read {log}"


print(classes(Logged()))
print(classes(Other()))


class MyInt(int):
    pass


class Named(int):
    __match_args__ = ("real", "imag")


def selves(obj: object) -> str:
    match obj:
        case bool(v):
            return f"bool {v}"
        case MyInt(v):
            return f"MyInt itself {type(v).__name__} {v is obj}"
        case Named(r, i):
            return f"Named by its args {r} {i}"
        case int(v):
            return f"int {v}"
        case float(v) | str(v) | bytes(v) | bytearray(v) | frozenset(v) | set(v) | dict(v) | list(v) | tuple(v):
            return f"{type(obj).__name__} itself {v is obj}"
        case collections.OrderedDict(v):
            return f"OrderedDict itself {v is obj}"
    return "no"


for selfish in (True, MyInt(3), Named(4), 5, 1.5, "s", b"b", bytearray(b"c"), frozenset({1}), {2}, {"k": 1}, [3], (4,)):
    print(selves(selfish))
print(selves(collections.OrderedDict(a=1)))


class Seq(collections.abc.Sequence[int]):
    def __init__(self, *items: int) -> None:
        self.data = list(items)

    def __len__(self) -> int:
        log.append("len")
        return len(self.data)

    def __getitem__(self, i: int) -> int:  # type: ignore[override]  # an int index is all a pattern uses
        log.append(f"getitem {i}")
        return self.data[i]

    def __iter__(self) -> Iterator[int]:
        log.append("iter")
        return iter(self.data)


class Registered:
    def __len__(self) -> int:
        log.append("len")
        return 2

    def __getitem__(self, i: int) -> int:
        log.append(f"getitem {i}")
        if i in (0, 1, -1, -2):
            return i % 2
        raise IndexError(i)


collections.abc.Sequence.register(Registered)


def sequences(obj: object) -> str:
    log.clear()
    match obj:
        case [a, b, c]:
            result = f"three {a} {b} {c}"
        case [a, *rest] if len(rest) > 2:
            result = f"first {a} rest {rest}"
        case [a, *_, b]:
            result = f"ends {a} {b}"
        case [_]:
            result = "one"
        case _:
            result = "no case"
    return f"{result}; did {log}"


for seq in (Seq(1, 2, 3), Seq(1, 2, 3, 4, 5), Seq(1, 2, 3, 4), Seq(9), Registered(), "abc", b"abc", bytearray(b"abc"),
              collections.deque([1, 2, 3]), range(3)):
    print(type(seq).__name__, sequences(seq))


class Mapped(collections.abc.Mapping[str, int]):
    def __init__(self, **items: int) -> None:
        self.data = items

    def __len__(self) -> int:
        log.append("len")
        return len(self.data)

    def __getitem__(self, key: str) -> int:
        log.append(f"getitem {key}")
        return self.data[key]

    def __iter__(self) -> Iterator[str]:
        log.append("iter")
        return iter(self.data)

    def get(self, key: str, default: object = None) -> object:  # type: ignore[override]  # the default is a sentinel object
        log.append(f"get {key}")
        return self.data.get(key, default)

    def keys(self) -> collections.abc.KeysView[str]:
        log.append("keys")
        return collections.abc.KeysView(self)


def mappings(obj: object) -> str:
    log.clear()
    match obj:
        case {"a": 1, "b": 2, "c": 3, "d": 4}:
            result = "four"
        case {"a": 9, "b": x}:
            result = f"never {x}"
        case {"a": a, "z": z}:
            result = f"never {a} {z}"
        case {"a": a, **rest}:
            result = f"a {a} rest {sorted(rest.items())} {type(rest).__name__} {rest is obj}"
        case _:
            result = "no case"
    return f"{result}; did {log}"


for mapping in (Mapped(a=1, b=2, c=3), {"a": 1, "q": 2}, collections.OrderedDict(a=5), [("a", 1)], Mapped(b=1)):
    print(type(mapping).__name__, mappings(mapping))


class Keys:
    K = "k"
    J = "k"


NotAClass = 3


class ListArgs:
    __match_args__ = ["x"]  # noqa: RUF012  # a list, which a class pattern refuses
    x = 1


class IntArgs:
    __match_args__ = (1,)


class Point:
    __match_args__ = ("x", "y")

    def __init__(self) -> None:
        self.x = 1
        self.y = 2


def malformed(n: int, obj: object) -> str:
    log.clear()
    try:
        match n, obj:
            case 0, Point(1, x=1):  # type: ignore[misc]  # x twice, which the pattern refuses when it runs
                return "never"  # type: ignore[unreachable]  # as mypy reads the pattern
            case 1, NotAClass():  # type: ignore[misc]  # a pattern's class is a name that is not one
                return "never"  # type: ignore[unreachable]  # as mypy reads the pattern
            case 2, ListArgs(1):
                return "never"
            case 3, IntArgs(1):
                return "never"
            case 4, object(1):  # type: ignore[misc]  # object matches no positional sub-pattern
                return "never"  # type: ignore[unreachable]  # as mypy reads the pattern
            case 5, Point(1, 2, 3):  # type: ignore[misc]  # three positional sub-patterns of two
                return "never"  # type: ignore[unreachable]  # as mypy reads the pattern
            case 6, {Keys.K: 1, Keys.J: 2}:
                return "never"
            case 7, Logged(boom=1):
                return "never"
            case 8, Logged(p, a=q):  # type: ignore[misc]  # a twice
                return f"never {p} {q}"  # type: ignore[unreachable]  # as mypy reads the pattern
            case 9, ListArgs():
                return "no positional sub-pattern: the list is never looked at"
            case 10, NotAClass() | Point():  # type: ignore[misc]  # as in case 1
                return "never"
            case _:
                return "fell through"
    except Exception as exc:  # noqa: BLE001  # which exception, by class
        return f"{type(exc).__name__}; read {log}"


for n, obj in enumerate((Point(), 0, ListArgs(), IntArgs(), object(), Point(), {"k": 1, "j": 2}, Logged(), Logged(), ListArgs(), Point())):
    print(n, malformed(n, obj))
print(malformed(11, Point()))
