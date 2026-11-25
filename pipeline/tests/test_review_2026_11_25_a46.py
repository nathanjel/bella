"""Review A46 (Codex Astra, low effort) of 25e2f67..0c25f5e: the import system's frames as CPython's (Question 43, C-8-22), with
A45's fixes, Questions 44 to 46 and E-06's refusal.

Five findings, RL-948 to RL-952; `docs/reviews/review-log.md` has each with its verdict. Three are fixed and held here, each the
reviewer's program with controls beside it (`review_a46/<probe>/*.txt`, read as modules beside `prog.py`), one row a process,
compared on standard output, standard error and the exit status:

* The import system's decorators are CPython's text, so a loader's check of the name raises in `_check_name_wrapper` and the
  decorated methods' names and code are the wrapper's (`decorators/wrongname`; the controls `rightname`, `extra`, `names`,
  `builtin`, `frozen`: RL-949).
* A property's getter and setter each have CPython's lines (`getters/lines`, `raised`: RL-952).
* A native module's namespace is in CPython's order: all 47 native modules' `__dir__()` (`nativeorder/dir`, the sweep of the
  class), and the program's own changes after it (`changed`, `vars`: RL-951).

The class of RL-948, the names and counts of the code objects of the import system's functions, is swept by `codeobjects`:
every function `runtime/prelude/bootstrap_frames.json` names, reached by name on both sides. The functions in `OPEN` differ
(the module locks, RL-950 and Question 47; the closed world's rewrites of the finders, the bytecode cache and the installer,
Question 48); every other one must agree, and one of `OPEN` that comes to agree is to leave it. Two the prelude had rewritten
where CPython's text runs as it is are CPython's now, and `rewrites` holds what else they show (`relax`, `loaders`).

Run under pytest or directly: python3 -m pipeline.tests.test_review_2026_11_25_a46
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from pipeline.build import build
from pipeline.tests.test_review_2026_11_23_a43 import _run

HERE = Path(__file__).resolve().parent / "review_a46"
TABLE = Path(__file__).resolve().parents[2] / "runtime" / "prelude" / "bootstrap_frames.json"

ROWS: dict[str, tuple[str, ...]] = {
    "decorators": ("wrongname", "rightname", "extra", "names", "builtin", "frozen"),
    "getters": ("lines", "raised"),
    "nativeorder": ("dir", "changed", "vars"),
    "rewrites": ("relax", "loaders"),
    "codeobjects": ("all",),
}

OPEN = frozenset({
    "_bootstrap.FrozenImporter.exec_module", "_bootstrap._exec", "_bootstrap._find_and_load", "_bootstrap._find_spec",
    "_bootstrap._lock_unlock_module", "_bootstrap._setup", "_bootstrap_external.AppleFrameworkLoader.create_module",
    "_bootstrap_external.ExtensionFileLoader.create_module", "_bootstrap_external.FileFinder._fill_cache",
    "_bootstrap_external.FileFinder._find_children", "_bootstrap_external.FileFinder.find_spec",
    "_bootstrap_external.NamespaceLoader.get_resource_reader", "_bootstrap_external.PathFinder._get_spec",
    "_bootstrap_external.PathFinder._path_hooks", "_bootstrap_external.PathFinder._path_importer_cache",
    "_bootstrap_external.PathFinder.discover", "_bootstrap_external.PathFinder.find_distributions",
    "_bootstrap_external.PathFinder.find_spec", "_bootstrap_external.PathFinder.invalidate_caches",
    "_bootstrap_external.SourcelessFileLoader.get_code", "_bootstrap_external.WindowsRegistryFinder._search_registry",
    "_bootstrap_external.WindowsRegistryFinder.find_spec", "_bootstrap_external._code_to_hash_pyc",
    "_bootstrap_external._code_to_timestamp_pyc", "_bootstrap_external._compile_bytecode", "_bootstrap_external._install",
    "_bootstrap_external._write_atomic", "_bootstrap_external.cache_from_source", "_bootstrap_external.source_from_cache",
})


def table_names() -> list[tuple[str, str]]:
    """The functions the table gives CPython's frames, by the module a program reaches them in."""
    modules = {"bootstrap.py": "_bootstrap", "bootstrap_external.py": "_bootstrap_external"}
    preludes = json.loads(TABLE.read_text(encoding="utf-8"))["preludes"]
    return sorted({(modules[p], q) for p, rows in preludes.items() for q in rows if "<locals>" not in q})


def by_function(stdout: str) -> dict[str, str]:
    return {line.split(" ", 1)[0]: line for line in stdout.splitlines()}


def rows_agree(probe: str) -> None:
    """A probe's files copied as modules beside its prog.py, built once; each row under CPython and compiled."""
    if shutil.which("g++") is None:
        return
    folder = Path(tempfile.mkdtemp(prefix="bella-a46-"))
    try:
        for source in sorted((HERE / probe).glob("*.txt")):
            text = source.read_text(encoding="utf-8")
            if probe == "codeobjects" and source.name == "prog.txt":
                lines = [f"NAMES: list[tuple[str, str]] = {table_names()!r}" if line.startswith("NAMES: ") else line
                         for line in text.splitlines()]
                text = "\n".join(lines) + "\n"
            (folder / source.with_suffix(".py").name).write_text(text, encoding="utf-8")
        binary = str(build(folder / "prog.py", "prog.py", notes=False))
        wrong: list[str] = []
        for row in ROWS[probe]:
            want = _run([sys.executable, "prog.py", row], folder)
            got = _run([binary, row], folder)
            if probe == "codeobjects" and got[1:] == want[1:]:
                cpython, compiled = by_function(want[0]), by_function(got[0])
                differ = {name for name in cpython if compiled.get(name) != cpython[name]} | (set(compiled) - set(cpython))
                wrong += [f"{name}: compiled {compiled.get(name)!r}, CPython {cpython[name]!r}" for name in sorted(differ - OPEN)]
                wrong += [f"{name} agrees now: take it out of OPEN" for name in sorted(OPEN & set(cpython) - differ)]
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
