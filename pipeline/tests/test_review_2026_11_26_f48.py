"""Review F48 (Claude workflows, 2026-11-26) of Questions 33 to 48 and of the code of 2026-11-24 and 25.

144 subjects, RL-958 to RL-1101; `docs/reviews/review-log.md` has each with its verdict. The fixed ones are held here, each
the reviewer's sweep of the defect's class (`review_f48/<probe>/*.txt`, read as modules beside `prog.py`; `rows.txt` has one
argument list a line), one row a process, compared on standard output, standard error and the exit status:

* A module name that is not a str does not end the program: 22 entry points of the import system, each handed nine kinds of
  name (`entrynames`: RL-1033). The rows in `STOPS` stop by name, where a compiled program has no source or frozen code to
  run; the row in `OPEN` waits for Question 48 (what `FrozenImporter.exec_module` does for a module that is not frozen).
* What a handler given to `os.register_at_fork` reaches is finalised at the exit, and the three lists of handlers are let go
  of in CPython's order (`atfork`: RL-1070; logging, threading and random register theirs when imported, so a filter, a
  handler or a formatter of the program's own kept the main module's globals from being finalised, a file left open with
  them).
* A class with a long chain of bases is made in time in proportion to it (`basechain`: RL-1039; a chain of 300, a ladder of
  40 diamonds, 60 class statements, and what `__base__` is with slots and built-in bases).

And one registered difference is held as D-17 words it (the author's decision of 2026-11-26, Question 49: A; RL-980):

* The frames CPython enters without checking the recursion limit (`unchecked`): 1,200 generators chained by `yield from` or
  by `for`, and a recursion 1,200 deep through `*args`, `**kwargs` or a bound method object called with a keyword, end
  under CPython and raise RecursionError compiled (`REGISTERED`); at 900 both end, and a recursive generator, the lazy
  sieve and a decorated recursion raise on both sides at 1,200.

And one decision's step (the author's, 2026-11-26, Question 50: B; RL-983):

* `decimal` and `datetime` are CPython's Python versions here, and the frames of their functions are none a program sees, as
  CPython's C modules have none (`cmodules`, 60 rows): 33 operations that raise, each with the entries of its traceback; an
  uncaught one; 13 ways the two modules call the program back (a tzinfo's methods, a Rational's numerator), with the stack
  there and a warning charged two levels up; a recursion that ends in an operation, counted; the two deprecation warnings
  of `datetime`, charged to the caller's line. What stays the Python version's is registered (D-20): what a signal of
  `decimal` carries, and a rounding mode's name that is not checked.

A row of `STOPS` must stop with its words, a row of `OPEN` must differ, and a row of `REGISTERED` must give what its entry
says: one that comes to agree with CPython is to leave its table.

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_26_f48
"""
from __future__ import annotations

import shlex
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from pipeline.build import build
from pipeline.tests.test_review_2026_11_23_a43 import _run

HERE = Path(__file__).resolve().parent / "review_f48"

NOT_COMPILED = "bella: not implemented: executing a module the program does not have compiled"
KINDS = ("int", "none", "bytes", "float", "list", "tuple", "strsub", "strsub2", "str")

# rows where the compiled program stops by name, CPython doing what a compiled program cannot
STOPS: dict[tuple[str, tuple[str, ...]], str] = {
    **{("entrynames", ("source.exec_module", kind)): NOT_COMPILED for kind in KINDS},
    **{("entrynames", ("frozen.exec_module", kind)): NOT_COMPILED for kind in KINDS if kind != "strsub2"},
}
# rows that differ as a registered deviation says: what the compiled program prints there
REGISTERED: dict[tuple[str, tuple[str, ...]], tuple[str, str]] = {
    **{("unchecked", (shape, "1200")): ("D-17", "RecursionError\n") for shape in ("yield from", "for", "*args", "**kwargs", "bound method")},
    # decimal is CPython's _pydecimal: its signals carry a text where the C module's carry the conditions, and it takes a
    # rounding mode's name unchecked
    ("cmodules", ("frames", "16")): ("D-20", "Decimal(1).to_integral_value(rounding='up') -> no error: Decimal\n"),
    ("cmodules", ("args", "0")): ("D-20", "Decimal('x') -> InvalidOperation (\"Invalid literal for Decimal: 'x'\",)\n"),
    ("cmodules", ("args", "1")): ("D-20", "Decimal(1) / Decimal(0) -> DivisionByZero ('x / 0',)\n"),
    ("cmodules", ("args", "2")): ("D-20", "Decimal(0) / Decimal(0) -> InvalidOperation ('0 / 0',)\n"),
    ("cmodules", ("args", "3")): ("D-20", "Decimal(-1).sqrt() -> InvalidOperation ('sqrt(-x), x > 0',)\n"),
    ("cmodules", ("args", "6")): ("D-20", "Decimal('1e999999999') * 10 -> Overflow ('above Emax',)\n"),
    ("cmodules", ("args", "7")): ("D-20", "Decimal('NaN') < 1 -> InvalidOperation ('comparison involving NaN',)\n"),
    ("cmodules", ("args", "12")): ("D-20", "Decimal(1).quantize(Decimal('1e-400'), context) -> InvalidOperation "
                                           "('quantize result has too many digits for current context',)\n"),
}
# rows that differ until the author has decided (Question 48)
OPEN: frozenset[tuple[str, tuple[str, ...]]] = frozenset({
    ("entrynames", ("frozen.exec_module", "strsub2")),
})


def rows_of(probe: str) -> list[tuple[str, ...]]:
    return [tuple(shlex.split(line)) for line in (HERE / probe / "rows.txt").read_text(encoding="utf-8").splitlines()]


def rows_agree(probe: str) -> None:
    """A probe's files copied as modules beside its prog.py, built once; each row under CPython and compiled."""
    if shutil.which("g++") is None:
        return
    folder = Path(tempfile.mkdtemp(prefix="bella-f48-"))
    try:
        for source in sorted((HERE / probe).glob("*.txt")):
            if source.name != "rows.txt":
                (folder / source.with_suffix(".py").name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        binary = str(build(folder / "prog.py", "prog.py", notes=False))
        rows = rows_of(probe)
        assert rows, f"{probe}: no rows"
        wrong: list[str] = []
        for row in rows:
            want = _run([sys.executable, "prog.py", *row], folder)
            got = _run([binary, *row], folder)
            stop = STOPS.get((probe, row))
            if stop is not None:
                if got[2] != 70 or stop not in "\n".join(got[1]):
                    wrong.append(f"{probe}/{row}: compiled {got!r}, where it is to stop with {stop!r}")
            elif (probe, row) in REGISTERED:
                entry, printed = REGISTERED[(probe, row)]
                if got == want:
                    wrong.append(f"{probe}/{row} agrees now: take it out of REGISTERED and narrow {entry}")
                elif got != (printed, [], 0) or want[1:] != ([], 0):
                    wrong.append(f"{probe}/{row}: compiled {got!r}, CPython {want!r}, where {entry} says {printed!r} against a run that ends")
            elif (probe, row) in OPEN:
                if got == want:
                    wrong.append(f"{probe}/{row} agrees now: take it out of OPEN")
            elif got != want:
                wrong.append(f"{probe}/{row}: compiled {got!r}, CPython {want!r}")
        assert not wrong, "\n".join(wrong)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def pytest_generate_tests(metafunc: Any) -> None:
    if "probe" in metafunc.fixturenames:
        metafunc.parametrize("probe", sorted(p.name for p in HERE.iterdir() if p.is_dir()))


def test_rows(probe: str) -> None:
    rows_agree(probe)


if __name__ == "__main__":
    for folder in sorted(p for p in HERE.iterdir() if p.is_dir()):
        rows_agree(folder.name)
    print("ok")
