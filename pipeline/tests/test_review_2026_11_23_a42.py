"""Review A42 (Codex Astra, low effort) of d5927f0..4cbedcc: a buffer argument held through the call (RL-702, RL-583) and a
frame's values kept by its frame object (RL-222).

Ten findings, RL-912 to RL-921; `docs/reviews/review-log.md` has each with its verdict. The programs are the reviewer's own
probes (`review_a42/<probe>.txt`, one row a process): the rows that differed and agree now; `collected.txt` and
`separators.txt` are the session's, for the classes of RL-916 and RL-921.

* A generator's frame object has no `f_back`: `clear_gen_frame` sets the frame's previous to NULL before it clears it, so a
  kept exception of the generator keeps none of its resumer's variables (`frames/*`, `ownership/close`, `delete`,
  `ignoreclose`: RL-912). Not here: `ownership/cyclegen`, which agrees now on the caller's variables, the row's point, and
  runs the same two finalisers in one collection in another order (D-04: a group's deaths compare as a multiset).
* A frame object's clear (`traceback.clear_frames`, the collection's) releases its slots in place, last first, so a
  finaliser one of them runs still finds the slots below (a suggestion from them) and a clear it starts releases them
  (`edges/clearing`, `ownership/reenter`: RL-917).
* blake2's constructor lets go of every buffer it took when a later one fails (`buffers/key`, `buffers/salt`: RL-913).
* `a2b_base64` and `a2b_base32` take their arguments in the clinic's order, hold `ignorechars` as a buffer, build the
  alphabet's table after the conversions (its length checked there) and read the octets after the table's lookup
  (`buffers/32*`, `64resize`, `alphabet`, `ignore`, `conversion/hash*`, `edges/b32*`: RL-914, RL-915, RL-919, RL-920).
* The collection neither finalises nor clears a prelude helper that stands for C dealloc code: it dies when what holds it
  is cleared, and lets go of its buffer then (`buffers/iterator`, `collected/*`: RL-916, a view of a view too).
* An exhausted `iter_unpack` iterator lets go of its Struct before its buffer (`edges/struct`: RL-918).
* `hexlify`'s separator is read as stored, whatever its `__len__` says (`separator/ab`, `separators.txt`: RL-921).

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_23_a42
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.tests.test_review_2026_11_19 import same
from pipeline.tests.test_review_2026_11_22_a35 import probe_rows_agree

HERE = Path(__file__).resolve().parent

ROWS: dict[str, tuple[str, ...]] = {
    "buffers": ("32resize", "32write", "64resize", "alphabet", "ignore", "iterator", "key", "salt"),
    "collected": ("view_in_cycle", "view_of_view_in_cycle", "iter_in_cycle", "iter_fresh_in_cycle", "scanner_in_cycle",
                  "finditer_in_cycle", "decompressor_in_cycle"),
    "conversion": ("hashdata", "hashignore", "hashresize"),
    "edges": ("b32invalid", "b32len", "clearing", "struct"),
    "frames": ("escape", "finish", "suspended", "throw"),
    "ownership": ("close", "delete", "ignoreclose", "reenter"),
    "separator": ("a", "ab"),
}


def rows_agree(probe: str) -> None:
    probe_rows_agree(HERE / "review_a42" / f"{probe}.txt", ROWS[probe])


def pytest_generate_tests(metafunc: Any) -> None:
    if "probe" in metafunc.fixturenames:
        metafunc.parametrize("probe", sorted(ROWS))


def test_rows(probe: str) -> None:
    rows_agree(probe)


def test_separators() -> None:
    same((HERE / "review_a42" / "separators.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    for probe in sorted(ROWS):
        rows_agree(probe)
    test_separators()
    print("ok")
