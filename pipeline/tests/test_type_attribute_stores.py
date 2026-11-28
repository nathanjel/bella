"""Every attribute of `type`, stored and deleted through a class, as CPython answers (RL-1104, found with Question 67).

A class's store or deletion of a name its metaclass has a data descriptor for goes to that descriptor: a member (PyMemberDef:
`__flags__`, `__basicsize__`, `__base__` and the rest) says "readonly attribute", a getset with no setter "attribute '...' of
'type' objects is not writable", and what may be set is set. The names are CPython's `vars(type)`, read when the test runs;
one process a name and a way on each side, since a name the runtime does not have yet stops the compiled program by name,
which this test lets stand.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pipeline.build import build

ATTEMPT = '''
import sys


def attempt(name: str, how: str) -> str:
    class C:
        pass
    try:
        if how == "store":
            setattr(C, name, 3)
        else:
            delattr(C, name)
        return "ok"
    except BaseException as error:  # noqa: BLE001
        return type(error).__name__ + ": " + str(error)


print(sys.argv[1], sys.argv[2], attempt(sys.argv[1], sys.argv[2]))
'''


def _last(cmd: list[str], cwd: Path) -> tuple[str, int]:
    got = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=cwd, timeout=120)
    lines = (got.stdout + got.stderr).strip().splitlines()
    return (lines[-1] if lines else ""), got.returncode


def test_type_attributes_stored_and_deleted_through_a_class() -> None:
    if shutil.which("g++") is None:
        return
    names = sorted(vars(type))
    folder = Path(tempfile.mkdtemp(prefix="bella-type-stores-"))
    try:
        (folder / "attempt.py").write_text(ATTEMPT, encoding="utf-8")
        binary = str(build(folder / "attempt.py", "attempt.py", notes=False))
        wrong = []
        for name in names:
            for how in ("store", "delete"):
                want, _ = _last([sys.executable, "-I", "attempt.py", name, how], folder)
                got, status = _last([binary, name, how], folder)
                if got != want and not (status == 70 and got.startswith("bella: not implemented")):
                    wrong.append(f"{name} {how}: CPython {want!r}, compiled {got!r}")
        assert not wrong, "\n".join(wrong)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    test_type_attributes_stored_and_deleted_through_a_class()
    print("ok")
