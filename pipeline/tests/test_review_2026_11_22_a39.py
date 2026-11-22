"""Review A39 (Codex Astra, low effort) of 7f7c267..2996062, four steps in one review: the order of a pattern's stores,
the fixes of review A38, a generator expression's iterable and iterator (RL-488), the stack the program runs on.

11 findings, RL-875 to RL-885; `docs/reviews/review-log.md` has each with its verdict. The programs are the reviewer's own
probes (`review_a39/<probe>.txt`, one row a process): the rows that differed between CPython and the compiled program and
agree now. Not here: its rows on the stack (RL-883 and RL-884 are the decision's own consequences, and need a shell's
limits), the rows whose only difference is the text of a report (D-28), and two rows that print an address.

What the rows and the tests hold:

* What a class has under a special name is called as the slot calls it. A prelude's built-in function stored as
  `__call__`, `__enter__` or `__exit__` has no `__get__` and is not given the object (`slots`, `reduced/{call,enter}`:
  RL-877). A descriptor's `__set__` and `__delete__` are looked up as methods of the descriptor, so a staticmethod, a
  classmethod, a bound built-in or an object with `__call__` stored there gets the arguments CPython gives it; `__get__`
  is called as it is, the descriptor first (RL-878; `descriptor_kinds`: this session's sweep, 17 kinds of thing stored
  under each of the three names, reached through an instance, the class and a metaclass). `classmethod` binds what is not
  callable, and the call is what fails (`reduced/hint*`, `lastrows`: RL-879).
* A generator expression. An exception thrown into one that has not started lets go of its iterator as the frame
  unwinds, before the handler (`gen/throw*`, `lifetime`, `reduced/unstarted`: RL-875); after PEP 479's translation the
  frame's variables live while the RuntimeError's cause does (`reduced/stop`, `gen/throwstartedS`: RL-876); its frame is
  at the line of the `for` clause being asked and at the element's line when resumed (`trace`, compared by the frames'
  names and lines: RL-880); a zero-argument `super()` in it takes its `.0` (`contexts`, `more`: RL-881); and the helper of
  a comprehension in a branch is made in that branch (`breakcell`, `gen/break`: RL-882).
* The policy's stack size has a range, and no number wraps to nothing (RL-885).

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_22_a39
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from pipeline.build import build
from pipeline.closed_world import MAIN_STACK_MIB, MAIN_STACK_MIB_MOST, program_main_stack
from pipeline.tests.test_review_2026_11_19 import same
from pipeline.tests.test_review_2026_11_22_a35 import probe_rows_agree

HERE = Path(__file__).resolve().parent

ROWS: dict[str, tuple[str, ...]] = {
    "breakcell": ("observe",),
    "contexts": ("super",),
    "gen": ("break", "throwG", "throwK", "throwS", "throwstartedS", "throwV"),
    "lastrows": ("none-class", "prop-class"),
    "lifetime": ("throw-0",),
    "more": ("super",),
    "reduced": ("call", "enter", "hint", "hintbind", "set", "stop", "unstarted"),
    "slots": ("call", "enter", "exit", "length_hint"),
}
TRACE_ROWS = ("elem", "if", "iter", "later", "next", "resumed", "throw")


def rows_agree(probe: str) -> None:
    probe_rows_agree(HERE / "review_a39" / f"{probe}.txt", ROWS[probe])


def pytest_generate_tests(metafunc: Any) -> None:
    if "probe" in metafunc.fixturenames:
        metafunc.parametrize("probe", sorted(ROWS))


def test_rows(probe: str) -> None:
    rows_agree(probe)


def test_descriptor_kinds() -> None:
    """The class of RL-878 beyond the reviewer's rows: a function, two lambdas, a staticmethod, a classmethod, a bound
    built-in, built-in functions, an object with `__call__`, a class, None, a partial, a property, another type's method
    and slot wrapper, a method-wrapper and `classmethod(None)`, each stored as `__get__`, `__set__` and `__delete__` of a
    descriptor that an instance, its class and a metaclass's class are asked through. 153 rows in one process a side."""
    same((HERE / "review_a39" / "descriptor_kinds.txt").read_text(encoding="utf-8"))


def _frames(command: list[str], folder: Path) -> tuple[int, list[tuple[str, str]], str]:
    env = {**os.environ, "PYTHONHASHSEED": "0"}
    done = subprocess.run(command, capture_output=True, text=True, env=env, cwd=folder, timeout=120, stdin=subprocess.DEVNULL)
    lines = done.stderr.strip().split("\n")
    return done.returncode, re.findall(r'File ".*", line (\d+), in (\S+)', done.stderr), lines[-1] if lines else ""


def test_a_generator_expressions_frame_is_at_its_clauses_line() -> None:
    """RL-880: a generator expression written over five lines, failing in its element, its condition, its first and its
    later iterable, in `__next__`, and thrown into before and after its first item. The frames' lines and names and the
    exception's line are compared; the source lines CPython prints under each frame are the report's (D-28)."""
    if shutil.which("g++") is None:
        return
    folder = Path(tempfile.mkdtemp(prefix="bella-trace-"))
    try:
        program = folder / "prog.py"
        program.write_text((HERE / "review_a39" / "trace.txt").read_text(encoding="utf-8"), encoding="utf-8")
        binary = str(build(program, "prog.py", notes=False))
        for row in TRACE_ROWS:
            want = _frames([sys.executable, str(program), row], folder)
            got = _frames([binary, row], folder)
            assert want[1], (row, want)
            assert got == want, (row, got, want)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_the_policys_stack_size_has_a_range() -> None:
    """RL-885: `[platform] main_stack_mib` is a whole number of MiB from 1 to 2**20, and anything else is refused when
    the program is built (2**44 became no stack at all in the runtime's bytes). No policy is 256."""
    with tempfile.TemporaryDirectory() as tmp:
        def said(text: str, name: str) -> int:
            folder = Path(tmp, name)
            folder.mkdir()
            (folder / "bella.toml").write_text(text, encoding="utf-8")
            return program_main_stack(folder)

        assert said("", "nothing") == MAIN_STACK_MIB == 256
        assert said("[platform]\nmain_stack_mib = 1\n", "one") == 1
        assert said(f"[platform]\nmain_stack_mib = {MAIN_STACK_MIB_MOST}\n", "most") == MAIN_STACK_MIB_MOST == 1 << 20
        for at, wrong in enumerate(("0", "-1", str(MAIN_STACK_MIB_MOST + 1), str(1 << 44), str(1 << 62), "true", "1.5", '"8"', "[8]")):
            try:
                said(f"[platform]\nmain_stack_mib = {wrong}\n", f"wrong{at}")
            except ValueError as error:
                assert "main_stack_mib" in str(error), error
            else:
                raise AssertionError(f"main_stack_mib = {wrong} was taken")


if __name__ == "__main__":
    test_the_policys_stack_size_has_a_range()
    test_descriptor_kinds()
    test_a_generator_expressions_frame_is_at_its_clauses_line()
    for name in sorted(ROWS):
        rows_agree(name)
    print("ok")
