"""Review A44 (Codex Astra, low effort) of 2c342bc..756222f: classes as counted objects (C-3-12, D-19), and A43's fixes with
`_abc`'s weak references again.

Six findings, RL-937 to RL-942; `docs/reviews/review-log.md` has each with its verdict. The programs are the reviewer's own
probes (`review_a44/<probe>/prog.txt`, read as `prog.py`), one row a process, compared on standard output, standard error and
the exit status: the rows that differed, with the reviewer's controls beside them.

* `gc.garbage` under `DEBUG_SAVEALL` has a dead class's dict and its MRO's tuple (`collect/savedict`, `collect/savemro`;
  the controls `collect/callback`, `collect/final`: RL-937).
* `_abc` looks a class up by the hash its basic weak reference kept at the first look-up, whatever its metaclass's
  `__hash__` becomes (`abchash/change`, `abcanswer/change`, where the answer changes; `abchash/empty`, `restore`,
  `unhashable`: RL-938).
* A class holds the names of its `__slots__` the program made (`slotname/clear`: RL-939).
* A metaclass's `mro()` sees the class with no MRO and not yet among its bases' subclasses, may give an order C3 refuses,
  and the class it fails for dies at once (`construction/normal`, `construction/fail`, `mrotuple/building`,
  `customc3/resolve`, `mroread/stale`: RL-940); the tuple it returns is the class's `__mro__` (`mrotuple/identity`: RL-941).
* A name assigned to a class is never finalised at the exit while it reaches the class (`exitname/normal`, `qual`,
  `cycle`, `external/normal`, `external/cycle`; the controls `exitname/attr`, `exitname/drop`: RL-942).

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_24_a44
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from pipeline.build import build
from pipeline.tests.test_review_2026_11_23_a43 import _run

HERE = Path(__file__).resolve().parent / "review_a44"

ROWS: dict[str, tuple[str, ...]] = {
    "abcanswer": ("change",),
    "abchash": ("change", "empty", "restore", "unhashable"),
    "collect": ("callback", "final", "savedict", "savemro"),
    "construction": ("normal", "fail"),
    "customc3": ("resolve",),
    "exitname": ("attr", "cycle", "drop", "normal", "qual"),
    "external": ("normal", "cycle"),
    "mroread": ("stale",),
    "mrotuple": ("building", "identity"),
    "slotname": ("clear",),
}


def rows_agree(probe: str) -> None:
    """A probe's program built once; each row under CPython and compiled."""
    if shutil.which("g++") is None:
        return
    folder = Path(tempfile.mkdtemp(prefix="bella-a44-"))
    try:
        (folder / "prog.py").write_text((HERE / probe / "prog.txt").read_text(encoding="utf-8"), encoding="utf-8")
        binary = str(build(folder / "prog.py", "prog.py", notes=False))
        wrong: list[str] = []
        for row in ROWS[probe]:
            want = _run([sys.executable, "prog.py", row], folder)
            got = _run([binary, row], folder)
            if got != want:
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
