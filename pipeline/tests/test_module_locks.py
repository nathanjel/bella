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
* a store to one of the fourteen, which CPython's import system would read, and a delete of one, stop the same way (`set`,
  `del`: RL-1065);
* `_find_and_load` and `_lock_unlock_module` have no local `lock` (`varnames`);
* the fourteen are one list in the runtime's table of entries, the names table, D-33's words and here, and CPython's module
  has no other name the prelude lacks but its dunders and the functions not written yet (no build: RL-1067).

When the threads milestone brings CPython's locks, every row agrees with CPython and D-33 ends; this test then goes.

Run under pytest or directly: python3 -m pipeline.tests.test_module_locks
"""
from __future__ import annotations

import ast
import re
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
elif row == "set":
    setattr(_bootstrap, sys.argv[2], 5)
    print("stored")
elif row == "del":
    delattr(_bootstrap, sys.argv[2])
    print("deleted")
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
    # a store is one CPython's import system would read, and a delete is of an object the runtime lacks (RL-1065)
    COMPILED[("set", _name)] = ("", [f"bella: not implemented: a store to _frozen_importlib.{_name} ({WHY})"], 70)
    COMPILED[("del", _name)] = ("", [f"bella: not implemented: _frozen_importlib.{_name} ({WHY})"], 70)


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


def bound_names(path: Path) -> set[str]:
    """What a prelude's module binds: its definitions, its assignments and imports at module level, and its globals."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                names.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
    for inner in ast.walk(tree):
        if isinstance(inner, ast.Global):
            names.update(inner.names)
    return names


def test_the_fourteen_names_are_one_list() -> None:
    """RL-1067: the names are kept in four places (the runtime's ABSENT_BY_ENTRY, the names table, D-33's words, this test);
    they are one list, each a name of CPython's `_frozen_importlib` the prelude does not bind, and what else CPython's module
    has and the prelude lacks is a module's own dunder or one of the functions not written yet (test_import_text's ABSENT)."""
    import _frozen_importlib  # noqa: PLC0415
    import tomllib  # noqa: PLC0415

    from pipeline.tests.test_import_text import ABSENT, NOT_YET  # noqa: PLC0415
    root = Path(__file__).resolve().parents[2]
    entries = set(re.findall(r'\{"_frozen_importlib:(\w+)", MODULE_LOCKS\}', (root / "runtime" / "src" / "call.cpp").read_text(encoding="utf-8")))
    table = (root / "runtime" / "src" / "cpython_names.inc").read_text(encoding="utf-8")
    words = tomllib.loads((root / "docs" / "deviations.toml").read_text(encoding="utf-8"))["deviations"]["D-33"]["summary"]
    bound = bound_names(root / "runtime" / "prelude" / "bootstrap.py")
    lacks = set(dir(_frozen_importlib)) - bound
    not_yet = {name.split(".", 1)[1] for name, why in ABSENT.items() if why == NOT_YET and name.startswith("_bootstrap.")}
    dunders = {"__builtins__", "__doc__", "__file__", "__loader__", "__name__", "__package__", "__spec__"}   # __file__: set by
    # FrozenImporter's fixing up where the standard library's folder is known (under pytest), absent in a plain run
    wrong = [f"ABSENT_BY_ENTRY has {sorted(entries ^ set(LOCK_NAMES))} beyond or short of the test's list"] if entries != set(LOCK_NAMES) else []
    wrong += [f"{n}: not in the names table" for n in LOCK_NAMES if f'"_frozen_importlib:{n}"' not in table]
    wrong += [f"{n}: D-33's words do not name it" for n in LOCK_NAMES if f"`{n}`" not in words]
    wrong += [f"{n}: the prelude binds it, so its entry is dead" for n in sorted(set(LOCK_NAMES) & bound)]
    wrong += [f"{n}: CPython's module has it and the prelude lacks it, and it is neither a lock's nor not yet"
              for n in sorted(lacks - set(LOCK_NAMES) - dunders - not_yet)]
    assert not wrong, "\n".join(wrong)


def test_module_locks() -> None:
    rows_hold()


if __name__ == "__main__":
    rows_hold()
    print("ok")
