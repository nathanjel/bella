# clause: C-7-88
# spec: section 7 (traceback), E-02
# status: P1
# source: Lib/traceback.py (TracebackException.__init__, _compute_suggestion_error, _check_for_nested_attribute), Python/suggestions.c
"""What traceback adds to the last line of an AttributeError, a NameError and an ImportError: the name that was probably
meant. For a NameError it is looked for among the names the frame that raised could see, its locals, its globals and the
builtins, so the traceback is needed; for an AttributeError the frame says whether the object is the `self` of a method,
which may then be offered its private names. A name of the instance is offered as `self.name`, a standard module that was
not imported as an import that was forgotten. A comprehension's own variables are not the frame's once the exception has
left it. Only the addition is printed, from ". Did you" on: the message before it is the exception's own."""
# ruff: noqa: B018, F401, F821, F841  # the names that are not there are what the rows are about
import math
import traceback
from collections.abc import Callable, Iterator

rate_of_the_module = 7


def added(line: str) -> str:
    at = line.find(". Did you")
    return line[at:].rstrip() if at >= 0 else "(nothing)"


def hint(work: Callable[[], object]) -> str:
    """What the formatted exception adds, with its traceback and without."""
    try:
        work()
    except (AttributeError, NameError, ImportError) as exc:
        full = added(traceback.format_exception(exc)[-1])
        only = added(traceback.format_exception_only(exc)[-1])
        same = added(list(traceback.TracebackException.from_exception(exc).format_exception_only())[-1]) == full
        return f"{type(exc).__name__} {full} | without the traceback: {only} | {same}"
    return "no exception"


class Purchase:
    total = 10
    _secret = 1

    def __init__(self) -> None:
        self.rate = 3
        self.inner = Inner()

    def reads_private(self) -> object:
        return self.secret  # type: ignore[attr-defined]

    def reads_private_of_another(self, other: Purchase) -> object:
        return other.secret  # type: ignore[attr-defined]

    def names_an_attribute(self) -> object:
        return rate  # type: ignore[name-defined]

    def names_nothing_it_has(self) -> object:
        return rte  # type: ignore[name-defined]


class Inner:
    amount = 5


class Guarded:
    def __dir__(self) -> list[str]:
        raise RuntimeError("no listing")


def local_name(amount: int) -> object:
    rate = 3
    return amount * rte  # type: ignore[name-defined]


def global_name() -> object:
    return rate_of_the_modul  # type: ignore[name-defined]


def builtin_name() -> object:
    return lenn("abc")  # type: ignore[name-defined]


def forgotten_import() -> object:
    return fractions.Fraction(1, 2)  # type: ignore[name-defined]


def forgotten_import_or_a_local() -> object:
    fraction = 1
    return fractions.Fraction(1, 2)  # type: ignore[name-defined]


def shared(depth: int) -> Callable[[], object]:
    shared_total = depth

    def inner() -> object:
        seen = shared_total
        return shared_totl  # type: ignore[name-defined]

    return inner


def reads_none_of_them(depth: int) -> Callable[[], object]:
    shared_total = depth

    def inner() -> object:
        return shared_totl  # type: ignore[name-defined]

    return inner


def generator() -> Iterator[int]:
    counted = 1
    yield countd  # type: ignore[name-defined]


def before_it_is_bound() -> int:
    print(later)  # type: ignore[used-before-def, has-type]
    later = 1
    return later


def in_a_comprehension(items: list[Inner]) -> list[str]:
    prefix = "p"
    return [prefix + itm.amount for item in items]  # type: ignore[name-defined]


def attribute_in_a_comprehension(items: list[Inner]) -> set[int]:
    return {item.amuont for item in items}  # type: ignore[attr-defined]


def nested_comprehensions(table: list[list[int]]) -> list[list[int]]:
    return [[cel for cell in row] for row in table]  # type: ignore[name-defined]


def after_a_comprehension(items: list[int]) -> object:
    done = [item for item in items]
    return itme  # type: ignore[name-defined]


def class_body() -> None:
    class Body:
        first_name = 1
        second = first_nam  # type: ignore[name-defined]


purchase = Purchase()
print("an attribute:", hint(lambda: purchase.totl))  # type: ignore[attr-defined]
print("of a module:", hint(lambda: math.sqr))  # type: ignore[attr-defined]
print("a private one, from outside:", hint(lambda: purchase.secret))  # type: ignore[attr-defined]
print("from its own method:", hint(purchase.reads_private))
print("from a method, of another object:", hint(lambda: purchase.reads_private_of_another(Purchase())))
print("asked for as private:", hint(lambda: purchase._secrt))  # type: ignore[attr-defined]
print("one level down:", hint(lambda: purchase.amount))  # type: ignore[attr-defined]
print("of another kind of object:", hint(lambda: (1, 2).append(3)), "|", hint(lambda: frozenset().add(1)))  # type: ignore[attr-defined]
print("an object that will not be listed:", hint(lambda: Guarded().anything))  # type: ignore[attr-defined]
print("nothing near:", hint(lambda: purchase.zzzzzzzz))  # type: ignore[attr-defined]
print("a local name:", hint(lambda: local_name(2)))
print("a global name:", hint(global_name))
print("a builtin:", hint(builtin_name))
print("an attribute of self:", hint(purchase.names_an_attribute))
print("in a method, nothing of self's:", hint(purchase.names_nothing_it_has))
print("a module not imported:", hint(forgotten_import))
print("or a local:", hint(forgotten_import_or_a_local))
print("a name shared with the function around:", hint(shared(1)))
print("which the inner one does not read:", hint(reads_none_of_them(1)))
print("in a generator:", hint(lambda: next(generator())))
print("in a lambda:", hint(lambda: (lambda wanted: wantd)(1)))  # type: ignore[name-defined]
print("before it is bound:", hint(before_it_is_bound))
print("in a comprehension:", hint(lambda: in_a_comprehension([Inner()])))
print("an attribute in a comprehension:", hint(lambda: attribute_in_a_comprehension([Inner()])))
print("in nested comprehensions:", hint(lambda: nested_comprehensions([[1]])))
print("after a comprehension:", hint(lambda: after_a_comprehension([1])))
print("in a class body:", hint(class_body))
try:
    rate_of_the_modle  # type: ignore[name-defined]
except NameError as at_the_top:
    print("in the module's body:", added(traceback.format_exception(at_the_top)[-1]))


def imports_a_name() -> None:
    from math import sqr  # type: ignore[attr-defined]


def imports_a_private_name() -> None:
    from collections import _chain_  # type: ignore[attr-defined]


print("a name a module lacks:", hint(imports_a_name), "|", hint(imports_a_private_name))
