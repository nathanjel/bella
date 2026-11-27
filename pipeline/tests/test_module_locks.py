"""D-33: the import system takes no module locks, until the threads milestone (the author's decision of 2026-11-25, Question 47:
C; review A46, RL-950).

CPython 3.15.2's `_find_and_load` takes a lock for the name of a module it is about to load (`Lib/importlib/_bootstrap.py:1339`,
`_get_module_lock`, which looks the name up in `_module_locks` at 438); the runtime's one thread never waits for one, and its
prelude takes none. The register says what a program sees of that, and this test holds each part, a row a process, the program
built once (`prog.py` beside a one-line `sample.py`):

* each of the fourteen names of the lock machinery stops the program with D-33's words, where CPython has the object (`name`);
  a name of `_frozen_importlib`'s that is absent for want of work still says "not yet" (`other`);
* an import by a name whose class overrides `__hash__`, which CPython calls in `_get_module_lock`, stops by name (`hash`: E-04,
  the author's decision of 2026-11-27, Question 52), and a str subclass that overrides nothing imports as CPython does
  (`plain`);
* `_find_and_load` and `_lock_unlock_module` have no local `lock` (`varnames`).

When the threads milestone brings CPython's locks, every row agrees with CPython and D-33 ends; this test then goes.

Run under pytest or directly: python3 -m pipeline.tests.test_module_locks
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_review_2026_11_23_a43 import _run

LOCK_NAMES = ("_BlockingOnManager", "_DeadlockError", "_DummyModuleLock", "_ImportLockContext", "_List", "_ModuleLock",
              "_ModuleLockManager", "_WeakValueDictionary", "_blocking_on", "_get_module_lock", "_has_deadlocked", "_module_locks",
              "_thread", "_weakref")
WHY = "a module lock: the import system takes none until the threads milestone, D-33"

PROG = '''\
import sys
import traceback
from importlib import _bootstrap


class Name(str):
    def __hash__(self) -> int:
        for entry in traceback.extract_stack():
            if entry.name == "_get_module_lock":
                raise ValueError("hash during lock lookup")
        return super().__hash__()


class Plain(str):
    pass


def include() -> None:
    import sample  # noqa: F401


row = sys.argv[1]
if row == "name":
    print(type(getattr(_bootstrap, sys.argv[2])).__name__)
elif row == "other":
    print(type(_bootstrap._load).__name__)
elif row == "hash":
    try:
        print(__import__(Name("sample")).answer)
    except ValueError as error:
        print(error)
elif row == "plain":
    print(__import__(Plain("sample")).answer)
elif row == "varnames":
    for f in (_bootstrap._find_and_load, _bootstrap._lock_unlock_module):
        print(f.__name__, f.__code__.co_nlocals, f.__code__.co_varnames)
'''

# CPython's side, as 3.15.2 gives it; the compiled side, as D-33 says
CPYTHON: dict[tuple[str, ...], tuple[str, list[str], int]] = {
    ("other",): ("function\n", [], 0),
    ("hash",): ("hash during lock lookup\n", [], 0),
    ("plain",): ("42\n", [], 0),
    ("varnames",): ("_find_and_load 6 ('name', 'import_', 'lazy_submodule', 'module', 'lock', 'message')\n"
                    "_lock_unlock_module 2 ('name', 'lock')\n", [], 0),
}
COMPILED: dict[tuple[str, ...], tuple[str, list[str], int]] = {
    ("other",): ("", ["bella: not implemented: _frozen_importlib._load (CPython has it; the runtime does not yet)"], 70),
    ("hash",): ("", ["bella: not implemented: an import by a name whose class overrides str's __hash__ (CPython's import system calls "
                     "the methods of the name it is handed: E-04)"], 70),
    ("plain",): ("42\n", [], 0),
    ("varnames",): ("_find_and_load 5 ('name', 'import_', 'lazy_submodule', 'module', 'message')\n"
                    "_lock_unlock_module 1 ('name',)\n", [], 0),
}
for _name in LOCK_NAMES:
    COMPILED[("name", _name)] = ("", [f"bella: not implemented: _frozen_importlib.{_name} ({WHY})"], 70)


def rows_hold() -> None:
    if shutil.which("g++") is None:
        return
    folder = Path(tempfile.mkdtemp(prefix="bella-d33-"))
    try:
        (folder / "prog.py").write_text(PROG, encoding="utf-8")
        (folder / "sample.py").write_text("answer = 42\n", encoding="utf-8")
        binary = str(build(folder / "prog.py", "prog.py", notes=False))
        wrong: list[str] = []
        for row, compiled in COMPILED.items():
            want = CPYTHON.get(row)
            got_cpython = _run([sys.executable, "prog.py", *row], folder)
            if want is not None and got_cpython != want:
                wrong.append(f"{row}: CPython gave {got_cpython!r}, the register says {want!r}")
            if want is None and (got_cpython[1:] != ([], 0) or not got_cpython[0].strip()):
                wrong.append(f"{row}: CPython has no object there: {got_cpython!r}")
            got = _run([binary, *row], folder)
            if got != compiled:
                wrong.append(f"{row}: compiled {got!r}, D-33 says {compiled!r}")
        assert not wrong, "\n".join(wrong)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_module_locks() -> None:
    rows_hold()


if __name__ == "__main__":
    rows_hold()
    print("ok")
