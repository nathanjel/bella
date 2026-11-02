# clause: C-3-25
# spec: section 3
# status: P1
# source: Gate 0 task 4, step A1 (the census of docs/measurements.md, 2026-11-02)
"""Parameter kinds and call unpacking: CPython's binding order, defaults read when the call
happens, *args and **kwargs evaluated where CPython evaluates them, and the binding errors by
type (D-08: never their wording)."""
from collections.abc import Callable, Iterator, Mapping

trace: list[str] = []


def v[T](name: str, value: T) -> T:
    trace.append(name)
    return value


def shape(a: int, /, b: int = 2, *rest: int, c: int, d: int = 4, **extra: int) -> tuple[object, ...]:
    return (a, b, rest, c, d, sorted(extra.items()))


print(shape(1, c=3))
print(shape(1, 5, 6, 7, c=3, d=8, e=9))
print(shape(1, *[5, 6], c=3, **{"z": 1, "y": 2}))
print(shape(*(1,), **{"c": 3, "b": 7}))


def keyword_named_like_positional_only(a: int, /, **kw: int) -> tuple[int, list[tuple[str, int]]]:
    return a, sorted(kw.items())


print(keyword_named_like_positional_only(1, a=2))

# arguments: positional and starred first, in order, then the keyword items in order
def collect(*args: int, **kwargs: int) -> tuple[tuple[int, ...], list[str]]:
    return args, list(kwargs)


print(collect(v("p1", 1), *v("s1", [2]), v("p2", 3), k=v("k1", 4), **v("m1", {"j": 5})), trace)
trace.clear()
print(collect(x=v("kw x", 1), *v("star", [1]), **v("dstar", {"z": 1})), trace)  # noqa: B026  # CPython's order is the point
trace.clear()


class Logged(Mapping[str, int]):
    """A mapping that is not a dict: ** lists keys() first, then reads each value."""

    def __init__(self, names: list[str]) -> None:
        self.names = names

    def keys(self) -> list[str]:      # type: ignore[override]  # the protocol ** uses
        trace.append("keys")
        return list(self.names)

    def __getitem__(self, key: str) -> int:
        trace.append("get " + key)
        return len(key)

    def __iter__(self) -> Iterator[str]:
        return iter(self.names)

    def __len__(self) -> int:
        return len(self.names)


class QuietDict(dict[str, int]):
    """A dict subclass that keeps dict's iteration: ** reads its storage, not its methods."""

    def keys(self) -> list[str]:      # type: ignore[override]  # never called by **
        trace.append("never")
        return []

    def __getitem__(self, key: str) -> int:
        trace.append("never")
        return 0


print(collect(**Logged(["ab", "c"])), trace)
trace.clear()
print(collect(**QuietDict(q=1)), trace)
trace.clear()


def error(call: Callable[[], object]) -> str:
    try:
        call()
    except TypeError as exc:
        return type(exc).__name__
    return "no error"


def two(a: int, b: int) -> None:
    pass


def only_keywords(*, k: int) -> None:
    pass


def posonly(a: int, b: int = 1, /) -> None:
    pass


print(error(lambda: two(1)),                  # type: ignore[call-arg]  # a missing argument
      error(lambda: two(1, 2, 3)),              # type: ignore[call-arg]  # too many
      error(lambda: two(1, a=1)),               # type: ignore[misc, call-arg]  # multiple values
      error(lambda: two(1, 2, c=3)),            # type: ignore[call-arg]  # unexpected keyword
      error(lambda: only_keywords(1)),          # type: ignore[call-arg]  # positional for keyword-only
      error(lambda: only_keywords()),           # type: ignore[call-arg]  # missing keyword-only
      error(lambda: posonly(a=1)),              # type: ignore[call-arg]  # positional-only by keyword
      error(lambda: posonly(1, 2, 3)))          # type: ignore[call-arg]  # too many
print(error(lambda: collect(*v("not iterable", 1))),       # type: ignore[misc]  # not iterable
      error(lambda: collect(**v("not a mapping", 1))),     # type: ignore[arg-type]  # not a mapping
      trace)
trace.clear()
print(error(lambda: collect(**{"a": 1}, a=2)), error(lambda: collect(**Logged(["a"]), **{"a": 1})), trace)
trace.clear()
print(error(lambda: collect(**{1: 2})))   # type: ignore[arg-type]  # keywords must be strings


# defaults are evaluated once, positional ones before keyword-only ones, and read at call time
def counted(a: int = v("default a", 1), *, k: int = v("default k", 2), b: int = v("default b", 3)) -> tuple[int, int, int]:
    return a, k, b


print(trace, counted.__defaults__, counted.__kwdefaults__)
trace.clear()
counted.__defaults__ = (10,)
counted.__kwdefaults__ = {"k": 20, "b": 30}
print(counted(), counted(1, k=2))
counted.__kwdefaults__ = {"k": 20}
print(error(lambda: counted()))
