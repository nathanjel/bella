# clause: C-3-73
# spec: section 3 (the data model: what a type has of its own), section 6 (builtins: reversed)
# status: P1
# source: Objects/descrobject.c (mappingproxy_or, mappingproxy_ior, mappingproxy_reversed, mappingproxy_richcompare, mappingproxy_hash)
"""A mappingproxy stands for its mapping in `|`, on either side: the two are or-ed as any two objects are, so the answer is
the mapping's own (a dict for a dict, an OrderedDict for an OrderedDict), the other operand's reflected method is given the
mapping itself, and the TypeError names the mapping's type. `|=` is refused in words of its own. reversed() is the
mapping's. Only == and != compare, by the mapping; an object that is no dict of a kind is given a copy of an exact dict
to compare with, so it cannot change the dict behind the proxy (a class's least of all)."""
import collections
import types
from collections.abc import Callable, Iterator

SEEN: list[object] = []


class K:
    marker = 1


class Sees:
    """An operand that says what it was given."""

    def __ror__(self, other: object) -> tuple[object, ...]:
        return ("ror", type(other).__name__, other is BACKING)

    def __or__(self, other: object) -> tuple[object, ...]:
        return ("or", type(other).__name__, other is BACKING)


class Declines:
    def __or__(self, other: object) -> object:
        SEEN.append(type(other).__name__)
        return NotImplemented

    def __ror__(self, other: object) -> object:
        SEEN.append(("reflected", type(other).__name__))
        return NotImplemented


class Peek:
    """Equal to anything, and says what it was compared with."""

    def __eq__(self, other: object) -> bool:
        SEEN.append((type(other).__name__, other is BACKING, other == BACKING if isinstance(other, dict) else None))
        return True

    def __hash__(self) -> int:
        return 0


class Grabs:
    """Changes the dict it is compared with."""

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            other["marker"] = "changed"
            other["grabbed"] = True
        return False

    def __hash__(self) -> int:
        return 0


class Table:
    """A mapping that is no dict, with an `|` of its own and no __reversed__."""

    def __getitem__(self, key: object) -> object:
        return key

    def __len__(self) -> int:
        return 1

    def __iter__(self) -> Iterator[object]:
        return iter([1])

    def __or__(self, other: object) -> tuple[object, ...]:
        return ("Table.__or__", type(other).__name__)

    def __eq__(self, other: object) -> bool:
        SEEN.append(("Table.__eq__", type(other).__name__))
        return True

    def __hash__(self) -> int:
        return 5


def attempt(thunk: Callable[[], object]) -> str:
    try:
        result = thunk()
    except Exception as exc:  # noqa: BLE001  # which exception, by class
        return type(exc).__name__
    return ascii(result)


def in_place(target: object, other: object) -> object:
    target |= other  # type: ignore[operator]
    return target


def public(mapping: object) -> list[str]:
    assert isinstance(mapping, dict)
    return sorted(name for name in mapping if not name.startswith("__"))


BACKING = {1: 2}
proxy = types.MappingProxyType(BACKING)
other_proxy = types.MappingProxyType({5: 6})
ordered = types.MappingProxyType(collections.OrderedDict(a=1))
frozen = types.MappingProxyType(frozendict(a=1))
of_table = types.MappingProxyType(Table())  # type: ignore[arg-type, var-annotated]
print("or:", proxy | {3: 4}, {3: 4} | proxy, proxy | proxy, proxy | other_proxy, other_proxy | proxy, type(proxy | {}).__name__, (proxy | {}) is BACKING, (proxy | {}) == BACKING,
      ordered | {"b": 2}, type(ordered | {"b": 2}).__name__, {"b": 2} | ordered, type({"b": 2} | ordered).__name__, frozen | {"b": 2}, type(frozen | {}).__name__,
      of_table | 5, attempt(lambda: proxy | of_table), of_table | proxy, BACKING)  # type: ignore[operator]
print("or, of a class's:", public(vars(K) | {"extra": 1}), public({"extra": 1} | vars(K)), type(vars(K) | {}).__name__, public(vars(K) | vars(K)), (vars(K) | {"marker": 2})["marker"],
      K.marker, "extra" in vars(K))
print("what the other operand is given:", proxy | Sees(), Sees() | proxy, attempt(lambda: Declines() | proxy), attempt(lambda: proxy | Declines()), SEEN)
SEEN.clear()
print("or, refused:", attempt(lambda: proxy | 5), attempt(lambda: 5 | proxy), attempt(lambda: proxy | [(1, 2)]), attempt(lambda: proxy | None), attempt(lambda: None | proxy),  # type: ignore[operator]
      attempt(lambda: int | proxy), attempt(lambda: proxy | int), attempt(lambda: "a" | proxy), attempt(lambda: proxy | {1}), sorted({1: 2}.keys() | proxy), sorted(proxy | {7: 8}.keys()),  # type: ignore[operator]
      attempt(lambda: object() | proxy))  # type: ignore[operator]
print("or, by name:", proxy.__or__({3: 4}), proxy.__ror__({3: 4}), attempt(lambda: proxy.__or__(5)), attempt(lambda: proxy.__ror__(5)), proxy.__or__(other_proxy),  # type: ignore[operator]
      types.MappingProxyType.__or__(proxy, {9: 9}), attempt(lambda: types.MappingProxyType.__or__({}, {})), attempt(lambda: proxy.__or__()), attempt(lambda: proxy.__or__({}, {})),  # type: ignore[call-arg, operator]
      [type(vars(types.MappingProxyType)[name]).__name__ for name in ("__or__", "__ror__", "__ior__", "__reversed__", "__lt__", "__eq__")])
print("in place:", attempt(lambda: in_place(proxy, {})), attempt(lambda: in_place(proxy, 5)), attempt(lambda: proxy.__ior__({})), in_place({7: 8}, proxy), attempt(lambda: in_place(5, proxy)),  # type: ignore[attr-defined]
      attempt(lambda: in_place(vars(K), {})), attempt(lambda: in_place({1}, proxy)), BACKING, attempt(lambda: proxy.__ior__()))  # type: ignore[attr-defined]
print("reversed:", list(reversed(proxy)), type(reversed(proxy)).__name__, list(reversed(types.MappingProxyType({1: 2, 3: 4, 5: 6}))), list(reversed(ordered)),
      type(reversed(ordered)).__name__, list(reversed(vars(K))) == list(vars(K))[::-1], [name for name in reversed(vars(K)) if not name.startswith("__")],
      attempt(lambda: reversed(of_table)), attempt(lambda: of_table.__reversed__()), type(proxy.__reversed__()).__name__, attempt(lambda: proxy.__reversed__(1)),  # type: ignore[call-arg]
      list(reversed(frozen)))
print("compared:", proxy == {1: 2}, proxy == BACKING, proxy == proxy, proxy == types.MappingProxyType({1: 2}), proxy != {1: 2}, proxy != {}, {1: 2} == proxy, proxy == [(1, 2)],
      ordered == {"a": 1}, frozen == {"a": 1}, frozen == frozendict(a=1), vars(K) == dict(vars(K)), vars(K) == vars(K), vars(K) != {}, proxy == 5, proxy != 5)
print("not ordered:", [attempt(lambda op=op: op(proxy, proxy)) for op in (lambda a, b: a < b, lambda a, b: a <= b, lambda a, b: a > b, lambda a, b: a >= b)],  # type: ignore[misc]
      attempt(lambda: proxy < {1: 2}), attempt(lambda: {1: 2} >= proxy), proxy.__lt__(proxy), proxy.__le__({}), proxy.__gt__(5), proxy.__ge__(proxy),  # type: ignore[operator]
      attempt(lambda: proxy.__lt__()), attempt(lambda: types.MappingProxyType.__ge__({}, {})), proxy.__eq__({1: 2}), proxy.__ne__({1: 2}), proxy.__eq__(5), proxy.__ne__(5))  # type: ignore[operator]
print("what another object is compared with:", proxy == Peek(), Peek() == proxy, proxy != Peek(), SEEN)
SEEN.clear()
print("a dict of a kind is given the mapping:", ordered == Peek(), of_table == Peek(), frozen == Peek(), SEEN)
SEEN.clear()
print("and cannot change it:", vars(K) == Grabs(), K.marker, "grabbed" in vars(K), proxy == Grabs(), BACKING, vars(K) != Grabs(), K.marker)
print("hashed:", attempt(lambda: hash(proxy)), hash(frozen) == hash(frozendict(a=1)), attempt(lambda: hash(vars(K))), hash(of_table), attempt(lambda: {proxy: 1}), {frozen: 1}[frozen])
