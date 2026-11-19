# clause: C-3-75
# spec: section 3 (generators), section 7 (warnings)
# status: P1
# source: Objects/genobject.c (gen_throw, _gen_throw, gen_set_exception), Python/errors.c (_PyErr_NormalizeException,
#         _PyErr_CreateException), review of the runtime's stops 2026-11-13
"""A generator's throw() given more than the exception: a class with the value to make it of, and a traceback to raise
it with. CPython takes the old form with a DeprecationWarning. The value is the class's argument, or its arguments when
it is a tuple, or the exception itself when it is an instance of the class; a class that cannot be made of it throws what
its making raised. An instance takes no value. The traceback becomes the exception's before the generator's own entry is
added. What is not an exception, or not a traceback, fails in the caller and leaves the generator where it was. A
generator that delegates passes on what it was given, to a generator or to any object with a throw method."""
import traceback
import types
import warnings
from collections.abc import Callable, Generator, Iterator

Catcher = Generator[str, None, str]


def describe(exc: BaseException) -> str:
    entries = [entry.name for entry in traceback.extract_tb(exc.__traceback__)]
    made_of = "(the runtime's own words)" if isinstance(exc, TypeError) else repr(exc.args)
    return f"{type(exc).__name__}{made_of} raised through {entries}"


def catcher() -> Catcher:
    seen = "nothing"
    while True:
        try:
            yield seen
        except GeneratorExit:
            raise
        except BaseException as exc:
            seen = describe(exc)


def started(make: Callable[[], Catcher] = catcher) -> Catcher:
    made = make()
    next(made)
    return made


def old_traceback() -> types.TracebackType | None:
    def raised_here() -> None:
        raise KeyError("earlier")

    try:
        raised_here()
    except KeyError as exc:
        return exc.__traceback__
    return None


class Refuses(Exception):
    def __init__(self, *args: object) -> None:
        raise LookupError("cannot be made of", *args)


class NotAnException(Exception):
    def __new__(cls, *args: object) -> NotAnException:
        return 5  # type: ignore[return-value]


class Narrow(ValueError):
    pass


class HasThrow:
    """An iterator with a throw method of its own, to delegate to."""

    def __iter__(self) -> Iterator[str]:
        return self

    def __next__(self) -> str:
        return "from the iterator"

    def throw(self, *args: object) -> str:
        return f"the iterator's throw got {len(args)}: {[type(a).__name__ for a in args]}"


def delegates_to_a_generator() -> Catcher:
    result = yield from catcher()
    return result


def delegates_to_an_object() -> Generator[str]:
    yield from HasThrow()


def fails_and_goes_on() -> str:
    made = started()
    for wrong in ((5,), (5, 6), (ValueError("the instance"), "text"), (ValueError, "text", "not one")):
        try:
            made.throw(*wrong)
        except TypeError:
            pass
    return "after four that failed, the next one arrives: " + made.throw(KeyError("next"))


TB = old_traceback()
ROWS: list[tuple[str, Callable[[], object]]] = [
    ("a class and a text", lambda: started().throw(ValueError, "text")),
    ("a class and a tuple", lambda: started().throw(ValueError, ("one", 2))),
    ("a class and None", lambda: started().throw(ValueError, None)),
    ("a class and its instance", lambda: started().throw(ValueError, ValueError("made before"))),
    ("a class and a subclass's instance", lambda: started().throw(Exception, Narrow("narrower"))),
    ("a class and another class's instance", lambda: started().throw(ValueError, KeyError("k"))),
    ("a class, a value and None", lambda: started().throw(ValueError, "text", None)),
    ("a class, a value and a traceback", lambda: started().throw(ValueError, "text", TB)),
    ("a class, None and a traceback", lambda: started().throw(ValueError, None, TB)),
    ("an instance and None", lambda: started().throw(ValueError("the instance"), None)),
    ("an instance, None and a traceback", lambda: started().throw(ValueError("the instance"), None, TB)),
    ("an instance and a value", lambda: started().throw(ValueError("the instance"), "text")),  # type: ignore[call-overload]
    ("a class that refuses the value", lambda: started().throw(Refuses, "text")),
    ("a class whose making gives no exception", lambda: started().throw(NotAnException, "text")),
    ("no exception at all", lambda: started().throw(5, 6)),  # type: ignore[call-overload]
    ("no exception at all, one argument", lambda: started().throw(5)),  # type: ignore[call-overload]
    ("a throw that fails leaves the generator where it was", fails_and_goes_on),
    ("no traceback", lambda: started().throw(ValueError, "text", "not one")),  # type: ignore[call-overload]
    ("an instance and no traceback", lambda: started().throw(ValueError("the instance"), None, 5)),  # type: ignore[call-overload]
    ("through a generator it delegates to", lambda: started(delegates_to_a_generator).throw(ValueError, "text", TB)),
    ("to an object's throw, one", lambda: started(delegates_to_an_object).throw(ValueError)),  # type: ignore[arg-type]
    ("to an object's throw, two", lambda: started(delegates_to_an_object).throw(ValueError, "text")),  # type: ignore[arg-type]
    ("to an object's throw, three", lambda: started(delegates_to_an_object).throw(ValueError, "text", TB)),  # type: ignore[arg-type]
    ("one argument, as before", lambda: started().throw(ValueError("alone"))),
    ("too many", lambda: started().throw(ValueError, "text", None, None)),  # type: ignore[call-overload]
    ("none", lambda: started().throw()),  # type: ignore[call-overload]
]

for label, work in ROWS:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            print(f"{label}: {work()}")
        except Exception as exc:
            print(f"{label}: the caller gets {type(exc).__name__}")
    for w in caught:
        print(f"    {w.category.__name__} at line {w.lineno}, this file {w.filename == __file__}: {w.message}")

# the warning as an error: nothing was thrown, and the generator is where it was
kept = started()
with warnings.catch_warnings():
    warnings.simplefilter("error")
    try:
        kept.throw(ValueError, "text")
    except DeprecationWarning:
        print("as an error: DeprecationWarning in the caller")
print("    the generator goes on:", kept.send(None), "|", kept.throw(KeyError("after")))

# a generator that has not started, and one that is over
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    for name, made in (("not started", catcher()), ("over", started())):
        if name == "over":
            made.close()
        try:
            made.throw(ValueError, ("a", "b"), TB)
        except ValueError as exc:
            print(f"{name}: {describe(exc)}")

# the traceback given is the exception's own afterwards, with the entries added to it
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    passed = ValueError("passed")
    print("given a traceback:", started().throw(ValueError, passed, TB), "| it is the instance's now:", passed.__traceback__ is not None)
