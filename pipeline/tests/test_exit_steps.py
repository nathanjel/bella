"""The exit's order and steps, as the runtime chooses them (D-07; the author's decision of 2026-11-24, Question 39: B).

Section 9 promises which of the objects still alive at exit are finalised, and C-9-13 holds that promise: each row prints
the tags of what its finalisers wrote, sorted. The order among them and the step of the exit each runs in (what it still
finds of its module's globals, `sys` and the builtins) are unspecified but for the single-underscore order CPython's
reference guarantees, kept free for a faster exit. The exit's steps are CPython's (H4, RL-514: `finalize_modules`' steps,
`_PyModule_ClearDict`'s two passes); within a step the runtime finalises in its own order, which differs from CPython's in
some placements (RL-988). This test holds C-9-13's rows: the same case with BELLA_CASE_STEPS set prints all its finalisers
wrote, in order, under CPython and compiled, and adds the rows whose outcome follows the order, a weak reference's callback
at exit among them (`ORDER_ROWS`; Question 66: B).
A change that relaxes the order changes this test openly, with an entry in docs/DECISIONS.md.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pipeline.build import build

CASES = Path(__file__).resolve().parents[2] / "conformance" / "cases"
CASE = CASES / "C-9-13_the_steps_of_the_exit.py"


def _run(command: list[str], folder: Path) -> tuple[str, str, int]:
    env = {**os.environ, "PYTHONHASHSEED": "0", "BELLA_CASE_STEPS": "1"}
    env.pop("PYTHONWARNINGS", None)
    env.pop("BELLA_CASE_SHOW", None)
    done = subprocess.run(command, capture_output=True, text=True, env=env, cwd=folder, timeout=300, stdin=subprocess.DEVNULL)
    return done.stdout, done.stderr, done.returncode


def test_the_exit_keeps_cpython_order() -> None:
    if shutil.which("g++") is None:
        return
    folder = Path(tempfile.mkdtemp(prefix="bella-exit-steps-"))
    try:
        shutil.copy(CASE, folder / "prog.py")
        shutil.copytree(CASES / "exitpkg", folder / "exitpkg", ignore=shutil.ignore_patterns("__pycache__"))
        binary = str(build(folder / "prog.py", "prog.py", notes=False))
        want = _run([sys.executable, "prog.py"], folder)
        got = _run([binary], folder)
        assert "asker: finalised" in want[0] and "kept._under: LABEL='kept'" in want[0], want
        assert got == want, f"compiled {got!r}\nCPython {want!r}"
    finally:
        shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    test_the_exit_keeps_cpython_order()
    print("ok")
