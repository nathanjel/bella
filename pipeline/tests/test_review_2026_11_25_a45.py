"""Review A45 (Codex Astra, low effort) of 756222f..25e2f67: the program's module objects counted (Question 36, C-9-14), with
C-3-82, A44's fixes and the C-9-13 split.

Five findings, RL-943 to RL-947; `docs/reviews/review-log.md` has each with its verdict. Three are fixed and held here, each
the reviewer's program with controls beside it (`review_a45/<probe>/prog.txt`, read as `prog.py`), one row a process, compared
on standard output, standard error and the exit status:

* A module made with a str subclass's object as its name holds it only in its namespace, as `module_init_dict` keeps
  `md_name` for an exact str alone (`modname/replaced`, `reinit`; the control `modname/kept`: RL-943).
* A function a staged text made holds the text's globals and builtins, not the locals it ran with, so `dataclass`'s
  `__create_fn__` goes with `_create_fn`'s locals (`textlocals/saveall`; the controls `methods`, `frozen`: RL-945).
* `dir()` of a module is its namespace's keys, with no hashing (`moddir/subclass`; the controls `native`, a native module's
  names of CPython's and one the program deleted, and `plain`: RL-947).

RL-944 (a class's dict written through the proxy's reflected `|`) and RL-946 (a rebound `__builtins__`) are the author's.

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_25_a45
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from pipeline.build import build
from pipeline.tests.test_review_2026_11_23_a43 import _run, silent

HERE = Path(__file__).resolve().parent / "review_a45"

ROWS: dict[str, tuple[str, ...]] = {
    "moddir": ("subclass", "native", "plain"),
    "modname": ("replaced", "kept", "reinit"),
    "textlocals": ("saveall", "methods", "frozen"),
}


def rows_agree(probe: str) -> None:
    """A probe's program built once; each row under CPython and compiled."""
    if shutil.which("g++") is None:
        return
    folder = Path(tempfile.mkdtemp(prefix="bella-a45-"))
    try:
        (folder / "prog.py").write_text((HERE / probe / "prog.txt").read_text(encoding="utf-8"), encoding="utf-8")
        binary = str(build(folder / "prog.py", "prog.py", notes=False))
        wrong: list[str] = []
        for row in ROWS[probe]:
            want = _run([sys.executable, "prog.py", row], folder)
            got = _run([binary, row], folder)
            if silent(want):
                wrong.append(f"{probe}/{row}: prints nothing under CPython (RL-1077)")
            elif got != want:
                wrong.append(f"{probe}/{row}: compiled {got!r}, CPython {want!r}")
        assert not wrong, "\n".join(wrong)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def pytest_generate_tests(metafunc: Any) -> None:
    if "probe" in metafunc.fixturenames:
        metafunc.parametrize("probe", sorted(ROWS))


def test_rows(probe: str) -> None:
    rows_agree(probe)


if __name__ == "__main__":
    for name in sorted(ROWS):
        rows_agree(name)
    print("ok")
