"""The text of a repr: what a __repr__ or a __str__ of the program's returned, where a prelude makes a text of it.

Review A33 found three places A32's fixes had written `"text" + repr(obj)` (RL-748): a __repr__ may return an instance of a
str subclass, and then the + is that class's __radd__, which CPython's C never calls: PyUnicode_FromFormat's %R and %S and
PyUnicodeWriter_WriteRepr take the characters. The class was every such join in the preludes: 43 of the 66 rows of
`repr_text_sweep.txt` differed when it was written (the repr of a dict, of a partial, of a deque, of a struct sequence,
of a text stream; the message of a KeyError; a note of the JSON encoder). A prelude now takes the text with `_repr_text`
and `_str_text` (design.md, "What a prelude asks of a type"), and calls repr() itself only where the C writes the result
with PyUnicodeWriter_WriteStr, which is str() of it (the repr of an ast node and of a parameterised generic's arguments:
CPython calls the subclass's __str__ there, and so does the runtime).

Each row runs in its own process on both sides, the output compared whole.

Run under pytest or directly: python3 -m pipeline.tests.test_repr_text
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pipeline.build import build

HERE = Path(__file__).resolve().parent
PRELUDE = HERE.parent.parent / "runtime" / "prelude"
# rows that stop by name: the facility they need is not written
STOPS = {2: "a subclass of str as a keyword's name"}
# the files that are CPython's own Python (importlib's), where a repr is joined as CPython's file joins it
ITS_OWN_PYTHON = {"bootstrap_external.py"}
# bootstrap.py: the C's types written in Python begin at the first marker, and importlib's own Python has the part between
STANDS_FOR_C = ("# ---- types.GenericAlias ----", "# ---- structseq (Objects/structseq.c)")
ITS_OWN_AGAIN = "# bella: _bootstrap_external's source loader"
# where the C writes the result of PyObject_Repr with PyUnicodeWriter_WriteStr, the prelude calls repr() and then _str_text
WRITTEN_AS_STR = {"bootstrap.py": 3, "_typing.py": 3, "_ast.py": 2}


def _run(command: list[str], folder: Path) -> tuple[int, str]:
    env = {**os.environ, "PYTHONHASHSEED": "0", "PYTHONWARNINGS": "ignore"}
    done = subprocess.run(command, capture_output=True, text=True, env=env, cwd=folder, timeout=120, stdin=subprocess.DEVNULL)
    return done.returncode, re.sub(r" at 0x[0-9a-f]+", "", done.stdout) + ("" if done.returncode in (0, 70) else done.stderr[-300:])


def test_the_text_of_a_repr_is_its_characters() -> None:
    if shutil.which("g++") is None:
        return
    folder = Path(tempfile.mkdtemp(prefix="bella-reprtext-"))
    try:
        program = folder / "prog.py"
        program.write_text((HERE / "repr_text_sweep.txt").read_text(encoding="utf-8"), encoding="utf-8")
        binary = str(build(program, "prog.py", notes=False))
        count = int(_run([sys.executable, str(program), "count"], folder)[1])
        assert count >= 66, count
        with ThreadPoolExecutor(max_workers=4) as pool:
            reference = list(pool.map(lambda row: _run([sys.executable, str(program), str(row)], folder), range(count)))
            compiled = list(pool.map(lambda row: _run([binary, str(row)], folder), range(count)))
        wrong: list[str] = []
        stopped: set[int] = set()
        for row, (want, got) in enumerate(zip(reference, compiled, strict=True)):
            assert want[0] == 0, (row, want)
            if got[0] == 70:
                stopped.add(row)
            elif got != want:
                wrong.append(f"{row}: compiled {got[1].strip()[:200]!r} (status {got[0]}), CPython {want[1].strip()[:200]!r}")
        assert not wrong, "\n".join(wrong)
        assert stopped == set(STOPS), sorted(stopped ^ set(STOPS))
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_a_prelude_takes_a_repr_as_text() -> None:
    """The rule in the source: repr() is called only where the C hands its result to PyUnicodeWriter_WriteStr, in a
    stand-in for CPython's run of the file, or in importlib's own Python; everywhere else it is _repr_text()."""
    found: dict[str, int] = {}
    for path in sorted(PRELUDE.glob("*.py")):
        if path.name in ITS_OWN_PYTHON:
            continue
        lines = path.read_text(encoding="utf-8").split("\n")
        stands_for_c = path.name != "bootstrap.py"   # that file begins and goes on with importlib's own Python
        for line in lines:
            if path.name == "bootstrap.py" and line.startswith(STANDS_FOR_C):
                stands_for_c = True
            elif path.name == "bootstrap.py" and line.startswith(ITS_OWN_AGAIN):
                stands_for_c = False
            code = line.split("#")[0]
            if not stands_for_c:
                continue
            calls = len(re.findall(r"(?<![\w.])repr\(", code)) + len(re.findall(r"![rs]\}", code))
            if calls and "return str.__str__(repr(value))" not in code:
                found[path.name] = found.get(path.name, 0) + calls
    assert found == WRITTEN_AS_STR, found


if __name__ == "__main__":
    test_a_prelude_takes_a_repr_as_text()
    test_the_text_of_a_repr_is_its_characters()
    print("ok")
