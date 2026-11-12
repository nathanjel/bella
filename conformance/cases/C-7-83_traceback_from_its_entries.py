# clause: C-7-83
# spec: section 7 (traceback, formatting from source maps), D-06
# status: P1
# source: Lib/traceback.py (extract_tb, format_tb, StackSummary, FrameSummary, TracebackException, print_exc)
"""traceback formats a traceback entry by entry: the file, the line and the function of each, innermost last, with the
limits of extract_tb and sys.tracebacklimit, a recursion's repeated entries folded, a chain's causes and contexts, and the
summaries' own surface. Only the first line of each formatted entry is printed (the file, the line and the function): the
source line and its carets under it are D-06's."""
import io
import sys
import traceback

HERE = __file__


def deeper(n: int) -> None:
    if n == 0:
        raise ValueError("deep")
    deeper(n - 1)


def outer() -> None:
    try:
        deeper(6)
    except ValueError as exc:
        raise KeyError("k") from exc


def heads(chunks: list[str]) -> list[str]:  # the first line of each formatted piece, the case's file named <case>
    return [chunk.split("\n", 1)[0].replace(HERE, "<case>") for chunk in chunks]


try:
    outer()
except KeyError as exc:
    caught = exc
tb = caught.__traceback__
cause = caught.__cause__
assert cause is not None
print("entries:", [(fs.filename == HERE, fs.lineno, fs.name) for fs in traceback.extract_tb(tb)])
print("cause's entries:", [(fs.lineno, fs.name) for fs in traceback.extract_tb(cause.__traceback__)])
print("limits:", [fs.name for fs in traceback.extract_tb(cause.__traceback__, limit=2)],
      [fs.name for fs in traceback.extract_tb(cause.__traceback__, limit=-2)], traceback.extract_tb(cause.__traceback__, limit=0))
sys.tracebacklimit = 1
print("tracebacklimit:", [fs.name for fs in traceback.extract_tb(cause.__traceback__)], len(traceback.format_exception(cause)))
sys.tracebacklimit = -5
print("negative tracebacklimit:", traceback.extract_tb(cause.__traceback__))
del sys.tracebacklimit
print("format_tb:", heads(traceback.format_tb(cause.__traceback__)))
summary = traceback.extract_tb(tb)
first = summary[0]
print("summary:", type(summary).__name__, len(summary), type(first).__name__, len(first), first[1], first[2], first.lineno, first.name,
      repr(first).replace(HERE, "<case>"), first == (HERE, first.lineno, first.name, first.line), first.locals)
print("format:", heads(summary.format()))
print("folded:", heads(traceback.extract_tb(cause.__traceback__).format()))
te = traceback.TracebackException.from_exception(caught)
print("TracebackException:", te.exc_type_str, len(te.stack), te.__cause__ is not None, te.__context__ is not None,
      te.__suppress_context__, [fs.name for fs in te.__cause__.stack] if te.__cause__ is not None else None)
print("chain:", heads(list(te.format())))
print("format_exception:", heads(traceback.format_exception(caught, chain=False)))
out = io.StringIO()
try:
    outer()
except KeyError:
    traceback.print_exc(limit=1, file=out, chain=False)
print("print_exc:", heads([line for line in out.getvalue().splitlines() if not line.startswith("    ")]))   # no source line, no carets
try:
    [1][2]
except IndexError as exc:
    print("one entry:", [(fs.lineno, fs.name) for fs in traceback.extract_tb(exc.__traceback__)], heads(traceback.format_exception_only(exc))[0].split(":")[0])
print("no traceback:", traceback.extract_tb(None), traceback.format_tb(None), heads(traceback.format_exception(ValueError("v"))))
