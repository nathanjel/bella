"""The reports of an exception that the runtime prints itself, compiled against CPython (D-28; case C-7-89; the author's
decision of 2026-11-19).

CPython has its `traceback` module print the report of an uncaught exception, of `sys.excepthook` and of an exception it
can only tell of (in a `__del__`, an atexit callback, a generator's close), and the module adds to the last line of an
AttributeError, a NameError, an ImportError and a ModuleNotFoundError the name that was probably meant, or puts its own
words there for a module of the standard library. A compiled program's reports end with the exception's own message,
whether or not the program holds `traceback`. The case has the rows that CPython without `traceback` prints as a compiled
program does. Here is the rest: a program that does hold `traceback` (its own functions add what the runtime's report
lacks), the reports with an address in them, and what CPython's C prints otherwise than a compiled program when it has no
`traceback`: the box of an exception group and the notes, which a compiled program prints as `traceback` does. So the
whole of the difference is the cut after the message: CPython's report with every addition cut is the compiled program's.

Run under pytest or directly: python3 -m pipeline.tests.test_runtime_reports
"""
from __future__ import annotations

import os
import pty
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from conformance.harness import mask_stderr, simulation_env
from pipeline.build import build

HELD = r"""
import atexit
import sys
import traceback


class Plain:
    total = 10


class Finalised:
    total = 10

    def __del__(self):
        self.totl


def local(amount):
    rate = 3
    return amount * rte


def at_exit():
    counted = 1
    return countd


def closes_badly():
    seen = 1
    try:
        yield 1
    finally:
        sen


def grouped():
    errors = []
    for work in (lambda: local(1), lambda: Plain().totl):
        try:
            work()
        except Exception as exc:
            errors.append(exc)
    raise ExceptionGroup("several", errors)


def noted():
    try:
        Plain().totl
    except AttributeError as exc:
        exc.add_note("a note of the program's")
        raise


def added(lines):
    return [line[line.find(". Did you"):].rstrip() for line in lines if ". Did you" in line]


for label, work in (("attribute", lambda: Plain().totl), ("name", lambda: local(1)), ("group", grouped), ("noted", noted)):
    try:
        work()
    except BaseException as exc:
        print("==", label, file=sys.stderr)
        sys.__excepthook__(type(exc), exc, exc.__traceback__)
        print(label, "traceback's own functions:", added(traceback.format_exception(exc)))
print("== in a __del__", file=sys.stderr)
finalised = Finalised()
del finalised
print("== a generator's close", file=sys.stderr)
waiting = closes_badly()
next(waiting)
del waiting
atexit.register(at_exit)
print("== nothing catches it, and then the atexit callback", file=sys.stderr)
sys.stdout.flush()
local(2)
"""

# With the modules phase 1 leaves out blocked, as the harness records D-20: CPython's report of the import that fails has
# `traceback`'s words for a module of the standard library, the compiled program's the import system's
OMITTED = r"""
import sys

print("start", flush=True)
try:
    raise ModuleNotFoundError("the program's own words", name="json")
except ModuleNotFoundError as exc:
    sys.__excepthook__(type(exc), exc, exc.__traceback__)
import bz2
"""


def _both(source: str, extra_env: dict[str, str] | None = None) -> tuple[subprocess.CompletedProcess[str], subprocess.CompletedProcess[str]] | None:
    """The program under CPython (with `extra_env`) and compiled."""
    if shutil.which("g++") is None:
        return None
    env = dict(os.environ, PYTHONHASHSEED="0")
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(source, encoding="utf-8")
        ref = subprocess.run([sys.executable, "prog.py"], capture_output=True, text=True, check=False, env=dict(env, **(extra_env or {})), cwd=tmp)
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, env=env, cwd=tmp)
    return ref, got


def _report(text: str) -> list[str]:
    """A report as it is compared: D-06's mask, and no addresses."""
    return re.sub(r" at 0x[0-9a-f]+", "", mask_stderr(text)).splitlines()


def test_the_difference_is_the_cut_after_the_message() -> None:
    ran = _both(HELD)
    if ran is None:
        return
    ref, got = ran
    assert (got.returncode, got.stdout) == (ref.returncode, ref.stdout) == (1, ref.stdout), (got, ref)
    assert got.stdout.count(". Did you") == 5, got.stdout      # traceback's own functions add them compiled too (C-7-88)
    want = _report(ref.stderr)
    cut = [line[:at] if (at := line.find(". Did you")) >= 0 else line for line in want]
    assert sum(a != b for a, b in zip(want, cut, strict=True)) == 9, ref.stderr
    assert _report(got.stderr) == cut, f"\n--- compiled\n{got.stderr}\n--- CPython\n{ref.stderr}"
    # what CPython's C leaves out when it has no `traceback`, and a compiled program prints: the group's box and the notes
    assert any(line.startswith("  + Exception Group Traceback") for line in cut) and "a note of the program's" in cut, cut


def test_a_module_of_the_standard_library_that_is_not_there() -> None:
    ran = _both(OMITTED, simulation_env("D-20", sys.executable))
    if ran is None:
        return
    ref, got = ran
    assert (got.returncode, got.stdout) == (ref.returncode, ref.stdout) == (1, "start\n"), (got, ref)
    last = [[line for line in _report(run.stderr) if line.startswith("ModuleNotFoundError")] for run in (ref, got)]
    assert last == [["ModuleNotFoundError: Standard library module 'json' was not found", "ModuleNotFoundError: Standard library module 'bz2' was not found"],
                    ["ModuleNotFoundError: the program's own words", "ModuleNotFoundError: No module named 'bz2'"]], last
    assert [line for line in _report(ref.stderr) if not line.startswith("ModuleNotFoundError")] == \
           [line for line in _report(got.stderr) if not line.startswith("ModuleNotFoundError")], (got, ref)


# ---- colour (D-28 as widened on 2026-11-20; review log RL-528) ----
# CPython's report of an uncaught exception is traceback's, and traceback colours it: at a terminal, and anywhere when
# PYTHON_COLORS=1 or FORCE_COLOR is set (Lib/_colorize.py, can_colorize). The runtime's own report never has colour, as the
# report CPython prints without traceback has none. What a program asks traceback's own functions to print has none on
# either side.
COLOURED = r"""
import sys
import traceback


def total(rows: list[int]) -> int:
    return sum(rows) // len(rows)


if "asked" in sys.argv:
    try:
        total([])
    except ZeroDivisionError:
        traceback.print_exc()
    sys.exit(3)
total([])
"""
ESCAPE = "\x1b["


def _run_with_a_terminal(cmd: list[str], env: dict[str, str], cwd: str, terminal: bool) -> tuple[str, int]:
    """Standard error on a pseudo-terminal, or in a pipe; what was written there, and the status."""
    if not terminal:
        done = subprocess.run(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=False)
        return done.stderr, done.returncode
    master, slave = pty.openpty()
    with subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=slave) as proc:
        os.close(slave)
        data = b""
        while True:
            try:
                chunk = os.read(master, 4096)
            except OSError:                      # the other end is closed: the program is over
                break
            if not chunk:
                break
            data += chunk
        os.close(master)
        status = proc.wait()
    return data.decode().replace("\r\n", "\n"), status


def _coloured(text: str) -> list[str]:
    return mask_stderr(re.sub(r'"[^"]*/([^"/]+)"', r'"\1"', text)).splitlines()


def test_the_runtimes_report_has_no_colour() -> None:
    if shutil.which("g++") is None:
        return
    settings: list[tuple[bool, dict[str, str]]] = [
        (True, {}), (True, {"PYTHON_COLORS": "1"}), (True, {"FORCE_COLOR": "1"}), (True, {"NO_COLOR": "1"}), (True, {"PYTHON_COLORS": "0"}),
        (True, {"TERM": "dumb"}), (True, {"NO_COLOR": "1", "FORCE_COLOR": "1"}), (True, {"PYTHON_COLORS": "1", "NO_COLOR": "1"}),
        (False, {}), (False, {"PYTHON_COLORS": "1"}), (False, {"FORCE_COLOR": "1"}), (False, {"FORCE_COLOR": "1", "TERM": "dumb"})]
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(COLOURED, encoding="utf-8")
        exe = str(build(prog, "prog.py"))
        base = {name: value for name, value in os.environ.items() if not name.startswith("PYTHON") and name not in ("NO_COLOR", "FORCE_COLOR")}
        base |= {"PYTHONHASHSEED": "0", "TERM": "xterm-256color"}
        plain, status = _run_with_a_terminal([sys.executable, "prog.py"], base | {"NO_COLOR": "1"}, tmp, True)
        assert status == 1 and ESCAPE not in plain and "ZeroDivisionError" in plain, plain
        coloured = 0
        for terminal, more in settings:
            env = base | more
            ref, _ = _run_with_a_terminal([sys.executable, "prog.py"], env, tmp, terminal)
            got, got_status = _run_with_a_terminal([exe], env, tmp, terminal)
            coloured += ESCAPE in ref
            assert ESCAPE not in got, (terminal, more, got)
            assert (_coloured(got), got_status) == (_coloured(plain), 1), (terminal, more, got)
            # what the program asks traceback for is the same on both sides, and plain: only the report of an exception
            # nothing caught asks whether it may colour (traceback._print_exception_bltin)
            asked = [_run_with_a_terminal([*cmd, "asked"], env, tmp, terminal) for cmd in ([sys.executable, "prog.py"], [exe])]
            assert (_coloured(asked[0][0]), asked[0][1]) == (_coloured(asked[1][0]), asked[1][1]), (terminal, more, asked)
            assert asked[0][1] == 3 and ESCAPE not in asked[0][0] and ESCAPE not in asked[1][0], (terminal, more, asked)
        # CPython colours in seven of them: a terminal; PYTHON_COLORS=1 at a terminal, in a pipe and over NO_COLOR; FORCE_COLOR
        # at a terminal, in a pipe and over TERM=dumb
        assert coloured == 7, coloured


if __name__ == "__main__":
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            value()
    print("ok")
