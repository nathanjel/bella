"""The variables of CPython's start-up that a compiled program does not read (the specification's Environment paragraph, D-18).

`PYTHONWARNINGS` is ignored by the author's decision of 2026-11-20 (review log RL-483): whatever the variable says, a compiled
program starts with the warning filters CPython has without it, and `sys.warnoptions` is empty. So each program here is run
under CPython with the variable unset and compiled with it set to each value, and the two must agree on standard output, the
exit status and standard error (after the harness's mask, with file names cut to their last part).

Run under pytest or directly: python3 -m pipeline.tests.test_start_up_environment
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from conformance.harness import mask_stderr
from pipeline.build import build

# a program that holds no `warnings` (the C's own printing, D-27; so it does not ask whether the module is there) and one that does
PROGRAMS: dict[str, str] = {
    "without warnings": '''
import sys

flag = True
print("warnoptions:", sys.warnoptions)
try:
    print(~flag)
except DeprecationWarning:
    print("raised as an error")
print("done")
''',
    "holding warnings": '''
import sys
import warnings

flag = True
print("warnoptions:", sys.warnoptions)
print("filters:", [(action, category.__name__, module is not None) for action, _, category, module, _ in warnings.filters])
try:
    print(~flag)
except DeprecationWarning:
    print("raised as an error")
try:
    warnings.warn("the program's own", UserWarning)
    print("warned")
except UserWarning:
    print("the program's own, raised as an error")
try:
    warnings.warn("for later", PendingDeprecationWarning)
    print("not shown by default")
except PendingDeprecationWarning:
    print("pending, raised as an error")
''',
}

# what `-W` takes: an action, an action for a category, for a module, several, one that is no action, nothing
VALUES = ["error", "ignore", "always", "default", "once", "error::DeprecationWarning", "ignore::DeprecationWarning:__main__",
          "error::UserWarning,always::PendingDeprecationWarning", "bogus", "error:::0:too:many", ""]


def _report(text: str) -> list[str]:
    text = re.sub(r'File "[^"]*/([^"/]+)"', r'File "\1"', text)
    text = re.sub(r'(^|\s)/[^\s:"]*/([^/\s:"]+\.py)', r"\1\2", text, flags=re.MULTILINE)
    return mask_stderr(text).splitlines()


def _ignored(source: str) -> None:
    if shutil.which("g++") is None:
        return
    env = {name: value for name, value in os.environ.items() if name != "PYTHONWARNINGS"} | {"PYTHONHASHSEED": "0"}
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(source, encoding="utf-8")
        exe = str(build(prog, "prog.py"))

        def run(cmd: list[str], **more: str) -> tuple[str, int, list[str]]:
            done = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env | more, cwd=tmp, stdin=subprocess.DEVNULL)
            return done.stdout, done.returncode, _report(done.stderr)

        want = run([sys.executable, "prog.py"])
        assert "warnoptions: []" in want[0] and want[1] == 0, want
        heeded = run([sys.executable, "prog.py"], PYTHONWARNINGS="error")
        assert heeded != want, "CPython no longer reads PYTHONWARNINGS: the test shows nothing"
        assert run([exe]) == want
        for value in VALUES:
            assert run([exe], PYTHONWARNINGS=value) == want, f"PYTHONWARNINGS={value!r}"


def test_pythonwarnings_is_ignored_without_the_module() -> None:
    _ignored(PROGRAMS["without warnings"])


def test_pythonwarnings_is_ignored_with_the_module() -> None:
    _ignored(PROGRAMS["holding warnings"])


if __name__ == "__main__":
    test_pythonwarnings_is_ignored_without_the_module()
    test_pythonwarnings_is_ignored_with_the_module()
