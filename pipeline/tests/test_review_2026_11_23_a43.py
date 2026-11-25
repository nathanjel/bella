"""Review A43 (Codex Astra, low effort) of 4cbedcc..2c342bc: the exit as CPython's `finalize_modules` sequence (RL-514,
C-9-13), and A42's fixes again.

Fourteen findings, RL-923 to RL-936; `docs/reviews/review-log.md` has each with its verdict. The programs are the reviewer's
own probes, a directory each with the modules a probe imports (`review_a43/<probe>/*.txt`, read as `.py`), one row a process,
compared on standard output, standard error and the exit status: the rows that differed and agree now, with the reviewer's
controls beside them. RL-933 (`exit/failed`), decided by the author on 2026-11-24 (Question 36: a module of the program's is
counted), joined them with that step (C-9-14).

* The exit's steps where CPython has them: the shutdown warning of a `gc.garbage` with something in it (`gcwarning`:
  RL-923); `sys.is_finalizing()` true from the end of atexit's handlers (`flag`: RL-927); the second `flush_std_files` on the
  stream a late finaliser put in sys, with its status 120 (`lateflush`: RL-925).
* What the runtime's own namespaces held of the program's goes when CPython lets go of it: a value stored on the import
  system's two modules (`bootstrap`: RL-926), the objects of gc's two lists (`reduce/garbage`, `reduce/callback`,
  `exit/garbage`: RL-928).
* Module objects die by their count: each sys.modules entry is one (`alias`: RL-936), a namespace goes when its last holder
  does, in whatever step (`phase/ns`, `imports/namespace`: RL-930), and a module a finaliser adds while sys.modules is
  emptied is wiped with the others (`newmodule`: RL-935; the probe puts entries in first, so that the insert does not
  compact the table behind the removal's position, which depends on how full sys.modules is: D-30).
* The wiping hashes a key that is not an exact str (`key`: RL-931), and an exception while sys.modules is emptied is
  reported as ignored (`modkey`: RL-934).
* `bytes.hex` and `bytearray.hex` refuse an unknown keyword before they convert `bytes_per_sep` (`hex`: RL-924).
* With classes as counted objects (C-3-12, 2026-11-24): a class that a finaliser's new object refers to lives through the
  exit's collection, whose reckoning of what is reachable again is by counts (`fresh`, `reduce/cycle`, `reduce/kept`,
  `roots/newcycle`: RL-929), and a stream that only a dead class holds is finalised when the class goes (`buffer`, `drain`,
  `streamheld`, `pipe`, `imports/buffer`: RL-932).

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_23_a43
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from pipeline.build import build
from pipeline.tests.test_review_2026_11_19 import _report

HERE = Path(__file__).resolve().parent / "review_a43"

ROWS: dict[str, tuple[str, ...]] = {
    "alias": ("keep",),
    "bootstrap": ("internal", "external"),
    "buffer": ("noctx", "ctx"),
    "drain": ("observe",),
    "exit": ("garbage", "alias", "dynamic", "cache", "generator", "errorhandler", "warning", "after", "weakfinal", "context",
             "deep", "trace", "failed"),
    "flag": ("path", "cycle", "callback", "flush", "disabled"),
    "fresh": ("default", "bare"),
    "gcwarning": ("warn", "save"),
    "hex": ("bytes", "array", "hexlify"),
    "imports": ("namespace", "closure", "default", "instance", "dict", "sys_exit", "uncaught", "buffer"),
    "key": ("visible", "_private"),
    "lateflush": ("ok", "fail"),
    "modkey": ("alias",),
    "newmodule": ("insert",),
    "phase": ("ns", "cycle", "plain"),
    "pipe": ("open",),
    "reduce": ("garbage", "callback", "immediate", "cycle", "kept"),
    "roots": ("garbage", "callback", "context", "codec", "warning", "resurrect", "unraisable", "newcycle"),
    "streamheld": ("ctx", "sys", "handler"),
}


def _run(command: list[str], folder: Path) -> tuple[str, list[str], int]:
    env = {**os.environ, "PYTHONHASHSEED": "0"}
    env.pop("PYTHONWARNINGS", None)
    done = subprocess.run(command, capture_output=True, text=True, env=env, cwd=folder, timeout=120, stdin=subprocess.DEVNULL)
    return done.stdout, _report(done.stderr), done.returncode


def rows_agree(probe: str) -> None:
    """A probe's files copied as modules beside its prog.py, built once; each row under CPython and compiled."""
    if shutil.which("g++") is None:
        return
    folder = Path(tempfile.mkdtemp(prefix="bella-a43-"))
    try:
        for source in sorted((HERE / probe).rglob("*.txt")):
            target = folder / source.relative_to(HERE / probe).with_suffix(".py")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
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
