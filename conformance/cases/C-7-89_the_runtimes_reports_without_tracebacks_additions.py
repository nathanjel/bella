# clause: C-7-89
# spec: section 7 (sys, traceback), D-28
# status: P1
# source: Python/pythonrun.c (_PyErr_Display: traceback._print_exception_bltin when it can be imported, else print_exception),
#         Lib/traceback.py (TracebackException.__init__: what is added to the message), the author's decision of 2026-11-19
# deviation: D-28
"""The report of an exception that the runtime prints itself: for an exception nothing caught, and when the program calls
sys.excepthook or sys.__excepthook__. CPython has its traceback module print it, and that module adds to the last line of an
AttributeError, a NameError, an ImportError and a ModuleNotFoundError the name that was probably meant, and puts its own
words in place of the message of a ModuleNotFoundError that names a module of the standard library. A compiled program's
report ends with the exception's own message (D-28), which is what CPython prints when it cannot import traceback: the
second expectation. The entries above the last line, the lines between chained exceptions and what the program reads from
the exception are the same. Standard output has what the program sees; the reports are on standard error."""
# ruff: noqa: B018, F401, F821, F841  # the names that are not there are what the rows are about
import math
import sys
from collections.abc import Callable

rate_of_the_module = 7


class Purchase:
    total = 10
    _secret = 1

    def __init__(self) -> None:
        self.rate = 3

    def reads_private(self) -> object:
        return self.secret  # type: ignore[attr-defined]

    def names_an_attribute(self) -> object:
        return rate  # type: ignore[name-defined]


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


def imports_a_name() -> None:
    from math import sqr  # type: ignore[attr-defined]


def no_such_module() -> object:
    return __import__("no_such_module_at_all")


def near_a_module() -> object:
    return __import__("fractionz")


def names_a_standard_module() -> None:
    raise ModuleNotFoundError("the program's own words", name="json")


def explained() -> None:
    try:
        local_name(1)
    except NameError as first:
        raise AttributeError("explained") from first


def while_handling() -> object:
    try:
        Purchase().totl  # type: ignore[attr-defined]
    except AttributeError:
        return local_name(2)
    return None


def nothing_near() -> object:
    return Purchase().zzzzzzzz  # type: ignore[attr-defined]


def a_value_error() -> None:
    raise ValueError("total", 10)


ROWS: list[tuple[str, Callable[[], object]]] = [
    ("an attribute", lambda: Purchase().totl),  # type: ignore[attr-defined]
    ("of a module", lambda: math.sqr),  # type: ignore[attr-defined]
    ("a private one, from its own method", Purchase().reads_private),
    ("of another kind of object", lambda: (1, 2).append(3)),  # type: ignore[attr-defined]
    ("another language's name", lambda: [].push(1)),  # type: ignore[attr-defined]
    ("an operator a float lacks", lambda: (1.0).__or__),  # type: ignore[operator]
    ("nothing near", nothing_near),
    ("a local name", lambda: local_name(1)),
    ("a global name", global_name),
    ("a builtin", builtin_name),
    ("an attribute of self", Purchase().names_an_attribute),
    ("a module not imported", forgotten_import),
    ("or a local", forgotten_import_or_a_local),
    ("a name a module lacks", imports_a_name),
    ("no such module", no_such_module),
    ("a module near one that is there", near_a_module),
    ("a module of the standard library, named by the program", names_a_standard_module),
    ("with its cause", explained),
    ("raised while another was handled", while_handling),
    ("an exception that gets no addition", a_value_error),
]


def seen(exc: BaseException) -> str:
    """What the program reads from the exception: the same with the addition and without."""
    name = getattr(exc, "name", "(none)")
    return f"{type(exc).__name__} name={name!r} name_from={getattr(exc, 'name_from', '(none)')!r}"


print("the hook is the runtime's own:", sys.excepthook is sys.__excepthook__)
for label, work in ROWS:
    try:
        work()
    except Exception as exc:
        print(f"{label}: {seen(exc)}")
        print(f"== {label}", file=sys.stderr)
        sys.__excepthook__(type(exc), exc, exc.__traceback__)

try:
    Purchase().totl  # type: ignore[attr-defined]
except AttributeError as through_the_hook:
    print("through sys.excepthook:", seen(through_the_hook))
    print("== through sys.excepthook", file=sys.stderr)
    sys.excepthook(AttributeError, through_the_hook, through_the_hook.__traceback__)
    print("== without its traceback", file=sys.stderr)
    sys.excepthook(AttributeError, through_the_hook, None)

print("== nothing catches the last one", file=sys.stderr)
print("the program ends with it", flush=True)
local_name(3)
