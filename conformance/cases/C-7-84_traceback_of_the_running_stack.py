# clause: C-7-84
# spec: section 7 (traceback, formatting from source maps), D-06, E-02
# status: P1
# source: Lib/traceback.py (extract_stack, format_stack, print_stack, StackSummary.extract)
"""traceback gives the running stack, oldest frame first: the file, the line each frame is at and its function, from the
frame that asks outwards, with the limits of extract_tb (the newest frames for a positive limit, the oldest for a negative
one) and sys.tracebacklimit. A call a built-in makes has no frame of its own; a generator's frame is under whoever resumes
it. Only the first line of each formatted entry is printed: the source line under it is D-06's. What is no frame is
refused as CPython refuses it."""
import functools
import io
import sys
import traceback
from collections.abc import Callable, Iterator

HERE = __file__
Rows = list[tuple[bool, int, str]]


def rows(stack: traceback.StackSummary) -> Rows:
    return [(fs.filename == HERE, fs.lineno or 0, fs.name) for fs in stack]


def inner(limit: int | None = None) -> traceback.StackSummary:
    return traceback.extract_stack(limit=limit)


def middle(limit: int | None = None) -> traceback.StackSummary:
    return inner(limit)


def outer(limit: int | None = None) -> traceback.StackSummary:
    return middle(limit)


class K:
    seen: traceback.StackSummary

    def method(self) -> traceback.StackSummary:
        return traceback.extract_stack()

    @classmethod
    def of_the_class(cls) -> traceback.StackSummary:
        return traceback.extract_stack()

    @property
    def read(self) -> traceback.StackSummary:
        return traceback.extract_stack()

    def __len__(self) -> int:
        self.seen = traceback.extract_stack()
        return 0


def gen() -> Iterator[traceback.StackSummary]:
    yield traceback.extract_stack()
    yield traceback.extract_stack()


def drive(it: Iterator[traceback.StackSummary]) -> traceback.StackSummary:
    return next(it)


def comprehended() -> traceback.StackSummary:
    return [traceback.extract_stack() for _ in range(1)][0]


def spread() -> Rows:
    return rows(traceback.extract_stack(
        limit=None,
    ))


def deep(n: int) -> traceback.StackSummary:
    return traceback.extract_stack() if n == 0 else deep(n - 1)


def heads(chunks: list[str]) -> list[str]:  # the first line of each formatted piece, the case's file named <case>
    return [chunk.split("\n", 1)[0].replace(HERE, "<case>") for chunk in chunks]


def formatted(limit: int | None = None) -> list[str]:
    return traceback.format_stack(limit=limit)


def attempt(thunk: Callable[[], object]) -> str:
    try:
        thunk()
    except Exception as exc:  # noqa: BLE001  # which exception, by class
        return type(exc).__name__
    return "no exception"


print("module:", rows(traceback.extract_stack()))
print("nested:", rows(outer()))
print("limits:", rows(outer(2)), rows(outer(-2)), rows(outer(0)), [fs.name for fs in outer(10)], [fs.name for fs in outer(-10)])
sys.tracebacklimit = 1
print("tracebacklimit:", rows(outer()), [fs.name for fs in outer(3)], heads(formatted()))
sys.tracebacklimit = -1
print("negative tracebacklimit:", rows(outer()), heads(formatted()))
del sys.tracebacklimit
k = K()
print("method:", rows(k.method()), rows(K.of_the_class()), rows(k.read))
len(k)
print("special method:", rows(k.seen))
g = gen()
print("generator:", rows(next(g)))
print("generator resumed elsewhere:", rows(drive(g)))
print("a built-in's call:", [rows(s) for s in map(lambda v: traceback.extract_stack(), [1])],
      rows(functools.partial(inner)()), rows(functools.reduce(lambda a, b: traceback.extract_stack(), [1, 2])))  # type: ignore[arg-type, return-value]
print("comprehension:", [rows(traceback.extract_stack()) for _ in range(1)], rows(comprehended()))
print("a call over several lines:", spread(
), rows(outer(
    None)))
print("recursion:", [fs.name for fs in deep(4)], heads(traceback.format_list(deep(6))))
stack = outer()
last = stack[-1]
print("summary:", type(stack).__name__, len(stack), type(last).__name__, len(last), last[1], last[2], last.name, last.lineno, last.locals,
      last == (HERE, last.lineno, "inner", last.line), isinstance(stack, list))
print("format_stack:", heads(formatted()), heads(formatted(1)), heads(formatted(-1)), formatted(0))
out = io.StringIO()


def show(limit: int | None = None) -> None:
    traceback.print_stack(limit=limit, file=out)


show()
show(1)
print("print_stack:", heads([line for line in out.getvalue().splitlines() if not line.startswith("    ")]))   # no source line
try:
    print(1 // 0)
except ZeroDivisionError as exc:
    print("in a handler:", rows(outer()))
    tb = exc.__traceback__
    print("no frame:", [attempt(lambda f=f, bad=bad: f(bad)) for bad in (5, "frame", tb) for f in (traceback.extract_stack, traceback.format_stack, traceback.print_stack)],  # type: ignore[misc]
          attempt(lambda: traceback.StackSummary.extract(iter([(tb, 1)]))))  # type: ignore[arg-type]
