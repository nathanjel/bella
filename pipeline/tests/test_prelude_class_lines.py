"""The `__firstlineno__` of every class a prelude defines, asked by the module that presents it (review F48, RL-1092's class).

CPython's compiler stores a class's first line as `__firstlineno__`; a type written in C has none. A prelude class stands for
one or the other: the import system's classes are CPython's Python classes, whose lines are CPython's text's (the F48 probe
`classlines`, through `tools/bootstrap_frames.py`); every other prelude's stands for a C type, or for a name its module does
not present, and an AttributeError is the answer on both sides. The rows are generated from the preludes' text, one process
a row on each side, since a name the runtime lacks stops the compiled program by name.
"""
from __future__ import annotations

import ast
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pipeline.build import build

ROOT = Path(__file__).resolve().parents[2]
PRELUDE = ROOT / "runtime" / "prelude"
SKIPPED = {"bootstrap.py", "bootstrap_external.py"}   # the import system's: probe `classlines`

ASK = '''
import importlib
import sys


def ask(module_name: str, name: str) -> str:
    try:
        module = importlib.import_module(module_name)
    except BaseException as error:
        return "no module " + type(error).__name__
    try:
        cls = getattr(module, name)
    except BaseException as error:
        return "no name " + type(error).__name__
    try:
        return repr(type(cls).__name__) + " " + repr(cls.__firstlineno__)
    except BaseException as error:
        return type(error).__name__


print(sys.argv[1], sys.argv[2], ask(sys.argv[1], sys.argv[2]))
'''


def rows() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for path in sorted(PRELUDE.glob("*.py")):
        if path.name in SKIPPED:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        out += [(path.stem, n.name) for n in tree.body if isinstance(n, ast.ClassDef) and not n.name.startswith("_bella")]
    return out


def _last(cmd: list[str], cwd: Path) -> str:
    got = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=cwd, timeout=120)
    lines = (got.stdout + got.stderr).strip().splitlines()
    return lines[-1] if lines else f"nothing, status {got.returncode}"


def test_every_prelude_class_answers_as_cpython() -> None:
    if shutil.which("g++") is None:
        return
    found = rows()
    assert len(found) > 200, found                 # 273 on 2026-11-28
    folder = Path(tempfile.mkdtemp(prefix="bella-classlines-"))
    try:
        (folder / "ask.py").write_text(ASK, encoding="utf-8")
        binary = str(build(folder / "ask.py", "ask.py", notes=False))
        wrong = []
        for module, name in found:
            want = _last([sys.executable, "-I", "ask.py", module, name], folder)
            got = _last([binary, module, name], folder)
            if want != got:
                wrong.append(f"{module}.{name}: CPython {want!r}, compiled {got!r}")
        assert not wrong, "\n".join(wrong)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    test_every_prelude_class_answers_as_cpython()
    print("ok")
