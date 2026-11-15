# clause: C-8-15
# spec: section 3 (PEP 667), section 6 (builtins)
# status: P1
# source: Python/bltinmodule.c (builtin_locals_impl, builtin_vars, _dir_locals), Python/ceval.c (_PyEval_GetFrameLocals),
#         Objects/frameobject.c (_PyFrame_GetLocals), PEP 667, the author's decision of 2026-11-14 (every function answers)
"""locals(), vars() and dir() without an argument, in every kind of frame. In a function they are made from the frame as it
is at the call: the names in the order of the code's variables (the parameters, the other locals as they first appear in
the text, then the variables inner functions share, then the ones taken from outside), without those that are not bound;
a dict of its own each time, which nothing writes back from. In a module's body and a class's they are the namespace
itself. The frame is the one that called, whatever name the builtin goes by and whoever was handed it: a helper that calls
what it was given gets its own. A variable that only a comprehension reads or assigns is a plain one, and the comprehension's
own are not the frame's once it is done (PEP 709)."""
# ruff: noqa: B007, B009, F841, F842  # variables bound to be seen, and the builtins reached by getattr
import builtins
import functools
import operator
from collections.abc import Callable, Iterator


def parameters(a: int, b: int = 2, /, c: int = 3, *rest: int, key: str = "k", **more: int) -> None:
    print("the parameters, in the code's order:", list(locals().items()))
    total = a + b + c
    print("and what is bound since:", list(locals()), total)
    print("each is the object itself:", locals()["rest"] is rest, locals()["more"] is more, locals()["key"] is key)


def appearance(flag: bool) -> list[str]:
    if flag:
        early = 1
    late = 2
    if not flag:
        early = 3
    return [*locals(), early + late]  # type: ignore[list-item]


def unbound() -> None:
    declared: int
    print("nothing yet:", locals(), vars(), dir())
    first = 1
    second = 2
    print("two:", locals())
    del first
    print("one deleted:", locals(), dir())
    for item in (5, 6):
        pass
    with open(__file__, encoding="utf-8") as handle:
        names = sorted(locals())
    print("a loop's target and a with's:", names, handle.closed)
    try:
        raise ValueError("gone")
    except ValueError as caught:
        inside = sorted(locals())
    print("an except's name inside:", "caught" in inside, "and after:", "caught" in locals())
    if (walrus := item + 1) > 0:
        import math
    print("a walrus and an import:", locals()["walrus"], locals()["math"] is math)
    try:
        return
    finally:
        print("in a finally:", "walrus" in locals(), len(locals()))


def snapshots() -> None:
    value = 1
    one = locals()
    two = vars()
    print("equal and apart:", one == {"value": 1}, two == {"value": 1, "one": one}, one is two, locals() is locals(), vars() is vars(), type(one).__name__)
    one["value"] = 2
    one["other"] = 3
    print("a write stays in the dict:", value, "other" in locals(), one)
    value = 5
    print("and the dict does not follow:", one["value"], locals()["value"], vars()["value"])


def shared(outer_argument: int, plain_argument: int) -> Callable[[], list[str]]:
    plain = 1
    cell = 2
    later: int

    def inner(own: int = 0) -> list[str]:
        nonlocal later
        untouched = own
        later = cell + outer_argument
        return list(locals())

    print("with the shared ones:", list(locals().items())[:2], list(locals())[2:], dir())
    names = inner()
    print("a shared one is there once it is bound:", list(locals())[-2:], locals()["later"], plain_argument + plain)
    return inner


def reads_none(a: int) -> Callable[[], dict[str, object]]:
    hidden = a

    def inner() -> dict[str, object]:
        return locals()

    return inner


class Base:
    def method(self) -> list[str]:
        return list(locals())


class Derived(Base):
    def method(self) -> list[str]:
        return [*super().method(), "|", *locals()]

    def private(self, __mangled: int = 1) -> list[str]:
        __own = __mangled
        return [*locals(), str(__own)]


def generator(count: int) -> Iterator[dict[str, object]]:
    for step in range(count):
        yield locals()
    yield vars()


def nested_frames(depth: int) -> list[int]:
    below = nested_frames(depth - 1) if depth else []
    return [*below, len(locals()), locals()["depth"]]


def helper(asked: Callable[[], object]) -> object:
    mine = "the helper's own"
    return asked()


def under_other_names() -> None:
    here = "the caller's"
    renamed = locals
    print("by another name:", sorted(renamed()))
    print("handed to a helper:", helper(locals), "|", helper(vars), "|", helper(dir))
    print("through builtins:", sorted(builtins.locals()), sorted(getattr(builtins, "vars")()), getattr(builtins, "dir")())
    print("called by a built-in:", sorted(functools.partial(locals)()), sorted(operator.call(vars)), sorted(max([locals], key=id)()), list(map(len, map(operator.call, [dir]))))
    print("in a lambda:", (lambda: locals())(), (lambda a, b: list(locals()))(1, 2), (lambda: dir())())
    print("in a generator expression:", next(list(locals()) for item in (1,)), next(dir() for item in (1,)))


def used_by_comprehensions(factor: int, table: list[list[int]]) -> dict[str, object]:
    scaled = [[cell * factor for cell in row] for row in table]
    totals = [last := sum(row) for row in table]
    return locals()


def attempt(thunk: Callable[[], object]) -> str:
    try:
        thunk()
    except TypeError:
        return "TypeError"
    return "no error"


class Prepared(dict[str, object]):
    """A class namespace of the program's own."""


class Meta(type):
    @classmethod
    def __prepare__(mcs, name: str, bases: tuple[type, ...], **kwds: object) -> Prepared:  # type: ignore[override]
        return Prepared(given="by __prepare__")


parameters(1)
parameters(1, 5, 6, 7, 8, key="given", x=1, y=2)
print("in the order they appear, not the order they are bound:", appearance(True), appearance(False))
unbound()
snapshots()
shared(10, 20)
print("only what the function names:", reads_none(1)(), reads_none.__code__.co_varnames)
print("a method:", Base().method(), Derived().method(), Derived().private())
steps = generator(2)
print("a generator's own, at each stop:", next(steps), next(steps), next(steps))
print("each frame its own:", nested_frames(2))
under_other_names()
print("what comprehensions read and assign:", used_by_comprehensions(2, [[1, 2], [3]]), used_by_comprehensions.__code__.co_varnames,
      used_by_comprehensions.__code__.co_cellvars)
print("too many arguments:", attempt(lambda: locals(1)), attempt(lambda: locals(x=1)), attempt(lambda: vars(1, 2)), attempt(lambda: dir(1, 2)), attempt(lambda: vars(x=1)))  # type: ignore[call-arg, call-overload]
print("a module's are its globals:", locals() is globals(), vars() is globals(), dir() == sorted(globals()), "parameters" in dir(), "steps" in locals())


class Body:
    first = 1
    names = list(locals())
    locals()["written"] = 2
    vars()["through_vars"] = 3
    same = locals() is vars()
    listed = dir()

    def method(self) -> list[str]:
        return list(locals())


print("a class body's are its namespace:", Body.names, Body.written, Body.through_vars, Body.same, Body.listed, Body().method())  # type: ignore[attr-defined]


class WithPrepare(metaclass=Meta):
    kind = type(locals()).__name__
    seen = list(locals())
    listed = dir()
    locals()["added"] = 1


print("the mapping __prepare__ gave:", WithPrepare.kind, WithPrepare.seen, WithPrepare.listed, WithPrepare.added)  # type: ignore[attr-defined]


def around_a_class(free: int) -> type:
    class Inner:
        uses = free
        names = ("uses" in locals(), "free" in locals(), "uses" in dir(), locals() is vars())

    return Inner


print("a class body in a function:", around_a_class(7).names, around_a_class(7).uses)  # type: ignore[attr-defined]
