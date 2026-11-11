"""What a compiled program starts with, against CPython on the same machine: the signals CPython ignores when it starts
(SIGPIPE and SIGXFSZ, Python/pylifecycle.c's signal_install_handlers), seen from outside the program, where case C-7-73 sees
them from inside: a reader that has gone is a BrokenPipeError and exit status 120, a write past the file size limit an OSError."""
from __future__ import annotations

import os
import resource
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pipeline.build import build

STDOUT_GONE = r"""
import sys
print("a line nobody reads")
try:
    sys.stdout.flush()
except BrokenPipeError as e:
    print("caught:", e.errno, e.strerror, file=sys.stderr)
print("another")
"""

TOO_LARGE = r"""
import os
import sys
f = open(sys.argv[1], "wb", buffering=0)
try:
    for _ in range(64):
        f.write(b"x" * 65536)
    print("written")
except OSError as e:
    print(type(e).__name__, e.errno, e.strerror, e.filename)
f.close()
print(os.path.getsize(sys.argv[1]) <= 1024 * 1024)
os.unlink(sys.argv[1])
"""


def _limit_file_size() -> None:
    resource.setrlimit(resource.RLIMIT_FSIZE, (262144, resource.getrlimit(resource.RLIMIT_FSIZE)[1]))


def test_a_reader_that_has_gone() -> None:
    if shutil.which("g++") is None:
        return
    outcomes = []
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(STDOUT_GONE, encoding="utf-8")
        for command in ([sys.executable, str(prog)], [str(build(prog, "prog.py"))]):
            r, w = os.pipe()
            os.close(r)
            try:
                done = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=w, stderr=subprocess.PIPE, text=True, check=False)
            finally:
                os.close(w)
            outcomes.append((done.stderr, done.returncode))
    assert outcomes[0] == outcomes[1], outcomes
    assert outcomes[0] == ("caught: 32 Broken pipe\nException ignored while flushing sys.stdout:\nBrokenPipeError: [Errno 32] Broken pipe\n", 120), outcomes[0]


def test_a_write_past_the_file_size_limit() -> None:
    if shutil.which("g++") is None:
        return
    outcomes = []
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(TOO_LARGE, encoding="utf-8")
        for command in ([sys.executable, str(prog)], [str(build(prog, "prog.py"))]):
            done = subprocess.run([*command, str(Path(tmp, "big.bin"))], stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False, preexec_fn=_limit_file_size)  # noqa: PLW1509
            outcomes.append((done.stdout, done.stderr, done.returncode))
    assert outcomes[0] == outcomes[1], outcomes
    assert outcomes[0] == ("OSError 27 File too large None\nTrue\n", "", 0), outcomes[0]


if __name__ == "__main__":
    test_a_reader_that_has_gone()
    test_a_write_past_the_file_size_limit()
