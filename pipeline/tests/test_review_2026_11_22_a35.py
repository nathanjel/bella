"""Review A35 (Codex Astra, low effort) of 9966dbe..d558f52: the state an allocator leaves, and the fixes of review A34.

25 findings, RL-777 to RL-801, and one more from the reviewer's saved outputs (RL-802); `docs/reviews/review-log.md` has
each with its verdict. The programs here are the reviewer's own probes, kept as it wrote them (`review_a35/<probe>.txt`,
one row a process): the 89 rows that differed between CPython and the compiled program and agree now. The one row left
out is `allocated/struct-new` (RL-776, open with the Struct step).

What the rows hold:

* `lifetime`, `feedback` (RL-782, high, of this session's making): an item is let go of before the next is asked for.
  The class is in `test_item_lifetime.py`.
* `exception` (RL-779, high; RL-780): `yield from` takes the value a StopIteration's struct holds, not an attribute
  `value`; `object.__reduce_ex__` compares what the type's own lookup finds for `__getstate__`.
* `identity` (RL-785, high; RL-786, RL-787; RL-788, high): a type is tested by identity, where `in` asks a metaclass's
  `__eq__` (a stream's finaliser, the weak reference types); `_remove_dead_weakref` hashes its key once and looks it up
  once; a class deriving from the csv reader's or writer's type cannot be instantiated (`allocated` has the same).
* `flags`, `patterns`, `factory` (RL-783, RL-784): matching and class building read `tp_flags` and the MRO as the C
  reads the struct.
* `arg_order` (RL-793, RL-794): a deque iterator's constructor converts its index first; the message for a bad class
  namespace reads the type's name from the type.
* `construction` (RL-798, high; RL-799, RL-800, RL-801, RL-778): OSError's class by a lookup of the errno object; a
  `characters_written` of -1 is none; ast's `__init__` asks for a field's name once and reads `_field_types` as a dict;
  a partial's `__setstate__` replaces the struct's dict.
* `ast_state` (RL-795 to RL-797): ast's `__reduce__` and `__replace__` after the C, an absent attribute told from None.
* `bootstrap`, `members`, `generics` (RL-777, RL-778, RL-781, RL-790): the object's own dict for a wrapper's annotations
  and a partial's state; a generic alias's tuples as the C reads them.
* `bytesinit`, `reinit`, `io_state`, `buffered` (RL-789, RL-791, RL-792, RL-802): `__init__` called again on io objects.
  The `buffered` rows whose stream was never closed had another cause, which `test_exception_release.py` holds.

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_22_a35
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

HERE = Path(__file__).resolve().parent
PRELUDE = HERE.parent.parent / "runtime" / "prelude"

ROWS: dict[str, tuple[str, ...]] = {
    "allocated": ("reader-sub",),
    "arg_order": ("forward", "prepare", "reverse", "zero"),
    "ast_state": ("red-dict", "red-names", "red-nonedict", "red-nonefields", "replace-dict", "replace-names", "replace-nonedict",
                  "replace-nonefields", "replace-order"),
    "bootstrap": ("wrapdel", "wrapread", "wrapwrite"),
    "buffered": ("pair-close-bad", "pair-detach-again", "pair-detach-bad", "pair-open-again", "pair-open-bad", "reader-close-bad",
                 "reader-detach-bad", "reader-open-bad", "writer-close-bad", "writer-detach-bad", "writer-open-bad"),
    "bytesinit": ("array", "none", "sub", "bad", "bytes"),   # the last two agreed before and caught the first fix
    "construction": ("errnoerr", "errnomap", "field", "missing", "restore", "table"),
    "exception": ("next", "state", "throw"),
    "factory": ("derive", "match"),
    "feedback": ("complex", "count", "float", "generic", "list", "sum"),
    "flags": ("eq", "map", "self", "seq"),
    "generics": ("pars", "repr", "sub", "subpars", "unpack"),
    "identity": ("eq", "final", "hashdead", "hashmiss", "ne", "reader", "remove", "writer"),
    "io_state": ("order", "pairbad", "pairgood", "translate"),
    "lifetime": ("buf", "complex", "csv", "deque", "float", "left", "lines", "min", "reduce", "sum"),
    "members": ("cread", "cwrite", "partial", "sread", "swrite"),
    "patterns": ("eq", "map", "self", "seq"),
    "reinit": ("iobc0", "iobc1"),
}


def _run(command: list[str], folder: Path, warnings_shown: bool = False) -> tuple[int, str]:
    env = {**os.environ, "PYTHONHASHSEED": "0", "PYTHONWARNINGS": "ignore"}
    if warnings_shown:
        del env["PYTHONWARNINGS"]
    done = subprocess.run(command, capture_output=True, text=True, env=env, cwd=folder, timeout=120, stdin=subprocess.DEVNULL)
    return done.returncode, done.stdout + ("" if done.returncode == 0 else done.stderr[-300:])


def probe_rows_agree(source: Path, rows: tuple[str, ...], warnings_shown: bool = False) -> None:
    """One of a reviewer's probes, a program that takes its row as its argument: each row under CPython and compiled.
    CPython is told to ignore warnings unless `warnings_shown`: a probe whose rows are about a warning being shown needs
    them, and the compiled program does not read the variable (D-18)."""
    if shutil.which("g++") is None:
        return
    probe = source.stem
    folder = Path(tempfile.mkdtemp(prefix="bella-probe-"))
    try:
        program = folder / "prog.py"
        program.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        binary = str(build(program, "prog.py", notes=False))
        wrong: list[str] = []
        for row in rows:
            want = _run([sys.executable, str(program), row], folder, warnings_shown)
            got = _run([binary, row], folder, warnings_shown)
            assert want[0] == 0, (probe, row, want)
            if got != want:
                wrong.append(f"{probe}/{row}: compiled {got[1].split(chr(10))!r} (status {got[0]}), CPython {want[1].split(chr(10))!r}")
        assert not wrong, "\n".join(wrong)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


WRITE_ON_A_CLOSED_STREAM = r"""
import io
class Bytes(bytes): pass
for value in (1, "s", None, b"x", bytearray(b"y"), Bytes(b"z")):
    for kind in ("write", "init", "open"):
        b = io.BytesIO(b"old")
        if kind != "open": b.close()
        try:
            print(kind, type(value).__name__, b.write(value) if kind != "init" else b.__init__(value), b.closed)
        except Exception as e: print(kind, type(value).__name__, type(e).__name__, b.closed)
"""


def test_a_closed_stream_refuses_after_the_arguments_buffer() -> None:
    """write_bytes takes the argument's buffer and then asks whether the stream is closed: a TypeError for what has no
    buffer, on a closed stream too. `BytesIO.write` and the first fix of RL-789 had the two the other way round, which the
    rerun of the reviewer's agreeing rows showed (`bytesinit/bad`, `reinit/iobc1`)."""
    from pipeline.tests.test_review_2026_11_19 import same
    same(WRITE_ON_A_CLOSED_STREAM)


def rows_agree(probe: str) -> None:
    probe_rows_agree(HERE / "review_a35" / f"{probe}.txt", ROWS[probe])


def pytest_generate_tests(metafunc: Any) -> None:
    if "probe" in metafunc.fixturenames:
        metafunc.parametrize("probe", sorted(ROWS))


def test_rows(probe: str) -> None:
    rows_agree(probe)


def test_no_prelude_tests_a_type_with_in() -> None:
    """The rule in the source (RL-784 to RL-786): a class is compared by identity. `type(x) in (A, B)`, `cls in mro` and
    `T not in mro` compare with `==` where the two are not the same object, which is the `__eq__` of a metaclass; the C
    compares pointers. One place does look a type up in a set, as the C does (`PySet_Contains(state->abstract_types,
    Py_TYPE(self))` in ast's initialiser). A `for` over an MRO is no such test."""
    allowed = {"_ast.py": 2}
    found: dict[str, int] = {}
    for path in sorted(PRELUDE.glob("*.py")):
        if path.name == "bootstrap_external.py":
            continue
        for line in path.read_text(encoding="utf-8").split("\n"):
            code = re.sub(r"\bfor \w+ in ", "", line.split("#")[0])
            hits = (len(re.findall(r"\btype\([\w.\[\]]+\) (?:not )?in [(\w]", code)) + len(re.findall(r"\b(?:not )?in _type_mro\(", code))
                    + len(re.findall(r"\bcls (?:not )?in [(_A-Z]", code)))
            if hits:
                found[path.name] = found.get(path.name, 0) + hits
    assert found == allowed, found


if __name__ == "__main__":
    test_no_prelude_tests_a_type_with_in()
    test_a_closed_stream_refuses_after_the_arguments_buffer()
    for name in sorted(ROWS):
        rows_agree(name)
    print("ok")
