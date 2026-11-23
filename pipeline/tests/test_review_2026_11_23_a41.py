"""Review A41 (Codex Astra, low effort) of 7355673..256985b: the cycle collector (the model by trial deletion, the header's
collector, the runtime's kinds and the gc module).

Eight findings, RL-904 to RL-911; `docs/reviews/review-log.md` has each with its verdict. The programs are the reviewer's own
probes (`review_a41/<probe>.txt`, one row a process): the rows that differed and agree now.

* The guard of a collection is held from before the start callbacks to after the stop ones (`callbacks/*`: RL-904).
* A suspended generator in a group is finalised by the collection's pass, its close run before the reckoning again
  (`sequence/gen`, `sequence/genlive`: RL-905).
* The release path sets the finalised flag after its finaliser returns, the collection's pass before (`lifetime/refcount`,
  `extra/refcount`: RL-906).
* The collection's pass runs a finaliser where CPython has a tp_finalize: an exact BytesIO's or StringIO's inherited
  iobase_finalize, which their own deallocators skip (`extra/ioflag`, `streams/string`: RL-907), and not a prelude helper's
  `__del__` that stands for C dealloc code (`export/revive`, `resources/context`: RL-908; the source rule below holds the
  class).
* A prelude class traverses what its C type's tp_traverse visits (`resources/scanner`: RL-909, the scanner's subject), and
  a C type without Py_TPFLAGS_HAVE_GC is not tracked (`directory/*`: RL-911, os.scandir's iterator; the names table's
  flags decide for every type).
* The debugging flags are read where gc.c reads them: DEBUG_SAVEALL in delete_garbage (`phase/saveall`, `flags/fromdel`),
  and DEBUG_STATS and DEBUG_COLLECTABLE, whose lines are CPython's counts and addresses, stop by name there (RL-910).

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_23_a41
"""
from __future__ import annotations

import ast
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pipeline.build import build
from pipeline.tests.test_review_2026_11_22_a35 import probe_rows_agree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

ROWS: dict[str, tuple[str, ...]] = {
    "callbacks": ("start", "stop"),
    "directory": ("owned", "path-drop", "path-hold", "path-revive"),
    "export": ("revive",),
    "extra": ("ioflag", "refcount"),
    "flags": ("fromdel",),
    "lifetime": ("refcount",),
    "phase": ("saveall",),
    "resources": ("context", "scanner"),
    "sequence": ("gen", "genlive"),
    "streams": ("string",),
}
STOPS = {"stats": "gc.DEBUG_STATS", "collectable": "gc.DEBUG_COLLECTABLE"}


def rows_agree(probe: str) -> None:
    probe_rows_agree(HERE / "review_a41" / f"{probe}.txt", ROWS[probe])


def stops_by_name(row: str) -> None:
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text((HERE / "review_a41" / "flags.txt").read_text(encoding="utf-8"), encoding="utf-8")
        got = subprocess.run([str(build(prog, "prog.py")), row], capture_output=True, text=True, check=False, cwd=tmp)
    assert got.returncode == 70 and "bella: not implemented" in got.stderr and STOPS[row] in got.stderr, (row, got)


def pytest_generate_tests(metafunc: Any) -> None:
    if "probe" in metafunc.fixturenames:
        metafunc.parametrize("probe", sorted(ROWS))
    if "stop" in metafunc.fixturenames:
        metafunc.parametrize("stop", sorted(STOPS))


def test_rows(probe: str) -> None:
    rows_agree(probe)


def test_stops(stop: str) -> None:
    stops_by_name(stop)


def test_every_prelude_finaliser_is_one_of_cpythons_two_kinds() -> None:
    """RL-908's class: a prelude class's `__del__` is either CPython's tp_finalize of the type it stands for (the names table
    has `__del__` for that type, so the collection's pass runs it) or C dealloc code, marked `__bella_dealloc__` (run at the
    object's end alone). The names table says which C types have a tp_finalize."""
    table = (ROOT / "runtime" / "src" / "cpython_names.inc").read_text(encoding="utf-8")
    finalizing = {m.split(".")[-1] for m in re.findall(r'\{"([^"]+):__del__", "wrapper_descriptor"\}', table)}
    unmarked = []
    for path in sorted((ROOT / "runtime" / "prelude").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ClassDef):
                continue
            names = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
            marked = any(isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__bella_dealloc__" for t in n.targets) for n in node.body)
            if "__del__" in names and not marked and node.name not in finalizing:
                unmarked.append(f"{path.name}:{node.name}")
    assert not unmarked, unmarked


if __name__ == "__main__":
    for probe in sorted(ROWS):
        rows_agree(probe)
    for row in sorted(STOPS):
        stops_by_name(row)
    test_every_prelude_finaliser_is_one_of_cpythons_two_kinds()
    print("ok")
