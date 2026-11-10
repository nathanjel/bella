# clause: C-3-24
# spec: section 3
# status: P1
# source: decision S-2 as revised 2026-11-10 (docs/DECISIONS.md): function signatures at runtime are [P1]; Lib/inspect.py over a function's metadata
"""inspect.signature of what a program defines, read at runtime from the function's metadata (its code object's names,
counts and flags, its defaults and annotations): every kind of parameter, defaults evaluated once, annotations, a lambda, a
method through its class and through an instance, class and static methods, a class through __init__ and through __new__, a
callable instance, functools.partial and a decorator that uses functools.wraps (with and without follow_wrapped), a
__signature__ of the program's own, generator and coroutine functions and what inspect says they are, bind, bind_partial and
apply_defaults, replace, equality and hashing, getfullargspec, the parameter names as pycodestyle reads them, and the
docstring dataclasses generates for a class without one, a default factory included."""
import dataclasses
import functools
import inspect
from collections.abc import Callable, Iterator


@dataclasses.dataclass
class Item:
    name: str
    qty: int = 1
    tags: list[str] = dataclasses.field(default_factory=list)


def scale(x: int, factor: float = 2.0, *, exact: bool = False) -> float:
    return x * factor


def every(a: int, b: str = "b", /, c: float = 1.5, *rest: int, d: bytes, e: None = None, **more: object) -> None:
    pass


def plain(a, b=(1, 2), *args, key=[], **kwargs):  # type: ignore[no-untyped-def]  # noqa: ANN001, ANN002, ANN003, ANN201, B006
    pass


def describe(f: object) -> str:
    sig = inspect.signature(f)  # type: ignore[arg-type]
    rows = [f"{p.name}:{p.kind.name}:{p.default is not p.empty and repr(p.default)}:{p.annotation is not p.empty and p.annotation}"
            for p in sig.parameters.values()]
    return f"{sig} | {rows} | {sig.return_annotation is not sig.empty and sig.return_annotation}"


class Shape:
    def __init__(self, sides: int, name: str = "shape") -> None:
        self.sides = sides

    def area(self, unit: str = "m") -> float:
        return 0.0

    @classmethod
    def make(cls, n: int) -> "Shape":  # noqa: UP037  # a quoted annotation stays a str in the signature
        return cls(n)

    @staticmethod
    def helper(v: int, /) -> int:
        return v

    def __call__(self, times: int) -> int:
        return self.sides * times


class Made:
    def __new__(cls, value: int, *, flag: bool = True) -> Made:
        return super().__new__(cls)


def logged[**P](f: Callable[P, float]) -> Callable[P, float]:
    @functools.wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> float:
        return f(*args, **kwargs)
    return wrapper


def counter(start: int, step: int = 1) -> Iterator[int]:
    yield start


async def fetch(url: str, *, retries: int = 3) -> bytes:
    return b""


def declared(*args: object) -> None:
    pass


declared.__signature__ = inspect.Signature([inspect.Parameter("only", inspect.Parameter.KEYWORD_ONLY, default=7)])  # type: ignore[attr-defined]
wrapped = logged(scale)
print(Item.__doc__)
for name, f in (("scale", scale), ("every", every), ("plain", plain), ("lambda", lambda p, q=3, *r: None), ("Shape", Shape),
                ("Shape.area", Shape.area), ("bound area", Shape(3).area), ("Shape.make", Shape.make), ("Shape.helper", Shape.helper),
                ("instance", Shape(4)), ("Made", Made), ("partial", functools.partial(scale, 2, exact=True)),
                ("partial every", functools.partial(every, 1, d=b"")), ("wrapped", wrapped), ("counter", counter), ("fetch", fetch),
                ("declared", declared), ("Item", Item), ("describe", describe)):
    print(name, "->", describe(f))
print(inspect.signature(wrapped, follow_wrapped=False), wrapped.__wrapped__ is scale, wrapped.__name__)  # type: ignore[attr-defined]

sig = inspect.signature(every)
bound = sig.bind(1, "two", 3.0, 4, 5, d=b"d", extra=6)
print(bound.arguments, bound.args, bound.kwargs)
partial = inspect.signature(scale).bind_partial(5)
print(partial.arguments, partial.signature is not None)
partial.apply_defaults()
print(partial.arguments)
print(sig.bind(1, d=b"", a=2).arguments)         # a positional-only name given by keyword goes to **more
for call in (lambda: sig.bind(), lambda: sig.bind(d=b""), lambda: inspect.signature(scale).bind(1, 2, 3),
             lambda: inspect.signature(scale).bind(1, nope=2), lambda: inspect.signature(5)):  # type: ignore[arg-type]
    try:
        call()
    except TypeError as e:
        print("TypeError", type(e).__name__, len(e.args))

narrow = sig.replace(parameters=list(sig.parameters.values())[:2], return_annotation=int)
print(narrow, narrow == sig, sig == inspect.signature(every), hash(sig) == hash(inspect.signature(every)),
      sig.parameters["c"].replace(default=9, name="z"), list(sig.parameters))
print(inspect.getfullargspec(every))
print(inspect.getfullargspec(Shape(1).area).args, inspect.getfullargspec(plain).defaults, inspect.getfullargspec(plain).kwonlydefaults)
print([inspect.isfunction(x) for x in (scale, Shape.area, Shape(1).area, Shape, len)],
      [inspect.ismethod(x) for x in (scale, Shape.area, Shape(1).area, Shape.make)],
      inspect.isgeneratorfunction(counter), inspect.isgeneratorfunction(scale), inspect.iscoroutinefunction(fetch),
      inspect.iscoroutinefunction(counter), inspect.isclass(Shape), inspect.isroutine(scale), callable(Shape(1)))


def _get_parameters(function: object) -> list[str]:     # pycodestyle's reading of a check's arguments
    return [parameter.name for parameter in inspect.signature(function).parameters.values()  # type: ignore[arg-type]
            if parameter.kind == parameter.POSITIONAL_OR_KEYWORD]


print(_get_parameters(scale), _get_parameters(every), _get_parameters(Shape.area), _get_parameters(plain))
