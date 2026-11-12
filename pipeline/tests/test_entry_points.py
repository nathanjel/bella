"""The S-1 entry points in a compiled program (docs/staging.md section 6, C-3-65): what has none stops by name.

An annotate function the program wrote itself has no entry point, so its STRING and FORWARDREF, which CPython answers by
re-running its code, stop; so does a compiler-generated one whose evaluator the build declined (an annotation with a
lambda, or two evaluate functions of one type parameter, which share the key a compiled function is found by), naming
the reason. The words are the runtime's, so they are compared here, on the machine that builds; and the PEP 695 evaluate
functions that have entry points answer as CPython's, and so does FORWARDREF of a function the program wrote that supports
VALUE only, frames included."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.build import build  # noqa: E402
from pipeline.tests.test_review_2026_11_03 import same  # noqa: E402

STOPS = (
    ("hand_written", "import annotationlib\ndef annotate(format):\n    if format > 2:\n        raise NotImplementedError\n"
     "    return {'x': int}\nclass C:\n    pass\nC.__annotate__ = annotate\nprint('start')\n"
     "print(annotationlib.get_annotations(C, format=annotationlib.Format.STRING))\n",
     "[P2+] annotationlib: FORWARDREF and STRING of an annotate function the compiler did not generate"),
    ("declined", "import annotationlib\ndef f(a: (lambda: Missing)()) -> None:\n    pass\nprint('start')\n"
     "print(annotationlib.get_annotations(f, format=annotationlib.Format.FORWARDREF))\n",
     "[P2+] annotationlib: the build declined the entry point of f.__annotate__: Lambda in an annotation"),
    # a type parameter's bound or constraints and its default: two evaluate functions with one qualified name and first line,
    # which the compiled key cannot tell apart (CPython's positions can)
    ("one_key", "import annotationlib\nclass G[U: (int, Later) = Other]:\n    pass\nprint('start')\n"
     "print(annotationlib.call_evaluate_function(G.__type_params__[0].evaluate_default, annotationlib.Format.STRING))\n",
     "[P2+] annotationlib: the build declined the entry point of U: another function of the module has its qualified name and first line"),
)

# the PEP 695 evaluate functions through their entry points: a bound, constraints, a default and an alias's value, each read
# with STRING and FORWARDREF, and the code names and first lines they are found by
EVALUATE = r"""
import annotationlib
F = annotationlib.Format
def show(v):
    if isinstance(v, annotationlib.ForwardRef):
        return f"ForwardRef({v.__forward_arg__!r})"
    if isinstance(v, tuple):
        return tuple(show(x) for x in v)
    return v
def f[T: Later, *Ts, **P]():
    pass
class G[U: (int, Later2), W = Later3]:
    pass
type Alias[V] = list[V] | Later4
T = f.__type_params__[0]
U, W = G.__type_params__
for fn in (T.evaluate_bound, U.evaluate_constraints, W.evaluate_default, Alias.evaluate_value):
    code = fn.__code__
    print(code.co_qualname, code.co_firstlineno, code.co_freevars)
    for fmt in (F.STRING, F.FORWARDREF):
        print(" ", fmt.name, show(annotationlib.call_evaluate_function(fn, fmt)))
"""

# FORWARDREF of an annotate function a program wrote itself that supports VALUE only: CPython's re-run raises
# NotImplementedError and CPython answers VALUE (annotationlib's line 839). The runtime's stand-in for the re-run is a
# built-in, so the NotImplementedError that is the context of an error VALUE raises has CPython's frames: the line that
# called the re-run and the function's own. (The replay's stand-in is a frame of its own, so C-3-67 prints only the
# context's class.) A function that supports VALUE_WITH_FAKE_GLOBALS needs the re-run itself and stops.
CONTEXT = r"""
import annotationlib
def lines(tb):
    out = []
    while tb is not None:
        out.append(tb.tb_lineno)
        tb = tb.tb_next
    return out
def failing(format):
    if format != 1:
        raise NotImplementedError
    raise LookupError("value")
class C:
    pass
C.__annotate__ = failing
try:
    annotationlib.get_annotations(C, format=annotationlib.Format.FORWARDREF)
except LookupError as exc:
    print(lines(exc.__traceback__), type(exc.__context__).__name__, lines(exc.__context__.__traceback__))
"""
# VALUE raises NameError, so get_annotations goes past __annotations__ to the re-run, which CPython does against fake globals
FAKE_GLOBALS = ("import annotationlib\ndef annotate(format):\n    if format > 2:\n        raise NotImplementedError\n"
                "    return {'x': Undefined}\nclass C:\n    pass\nC.__annotate__ = annotate\nprint('start')\n"
                "print(annotationlib.get_annotations(C, format=annotationlib.Format.FORWARDREF))\n")


def _stops(source: str, words: str) -> None:
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(source, encoding="utf-8")
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
    assert (got.returncode, got.stdout) == (70, "start\n") and words in got.stderr, got


def test_hand_written_annotate_stops() -> None:
    _stops(STOPS[0][1], STOPS[0][2])


def test_declined_entry_point_stops() -> None:
    _stops(STOPS[1][1], STOPS[1][2])


def test_evaluate_functions_with_one_key_stop() -> None:
    _stops(STOPS[2][1], STOPS[2][2])


def test_evaluate_functions_are_cpythons() -> None:
    same(EVALUATE)


def test_value_only_forwardref_has_cpythons_frames() -> None:
    same(CONTEXT)


def test_forwardref_of_a_function_that_takes_fake_globals_stops() -> None:
    _stops(FAKE_GLOBALS, "[P2+] annotationlib: FORWARDREF of an annotate function the compiler did not generate, which supports "
                         "VALUE_WITH_FAKE_GLOBALS, re-runs its __code__ (decision S-1)")


if __name__ == "__main__":
    test_hand_written_annotate_stops()
    test_declined_entry_point_stops()
    test_evaluate_functions_with_one_key_stop()
    test_evaluate_functions_are_cpythons()
    test_value_only_forwardref_has_cpythons_frames()
    test_forwardref_of_a_function_that_takes_fake_globals_stops()
    print("ok")
