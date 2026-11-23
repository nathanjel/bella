"""What traceback adds to an exception's last line, compiled against CPython (C-7-88; E-02).

traceback's `_compute_suggestion_error` reads the frame that raised (tb_frame.f_locals, f_globals, f_builtins); the
adaptation takes those names from the runtime's traceback entry (runtime/replaced/traceback.py, `__bella_traceback_names__`).
Until 2026-11-15 the read stopped by name, so formatting an AttributeError or a NameError with its traceback ended the
program: `traceback.print_exc()`, `logging.exception`, a unittest failure. Here are the ways a program gets there, and the
frames whose names are asked for: one the exception left, one still running, a module's body, a class's, with chained
exceptions and groups, and the first of two exceptions of one frame. And the stops that stay: the frame of a generator
that waits, whose variables are the generator's while it is suspended, and a frame with a comprehension running. A frame
that is over has its values in its frame object while that is held (RL-222): those rows are `test_kept_frames`.

Run under pytest or directly: python3 -m pipeline.tests.test_traceback_suggestions
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_compiled_imports import same

WAYS = r"""
import io
import logging
import sys
import traceback
import unittest


def added(text):
    return [line[line.find(". Did you"):] for line in text.splitlines() if ". Did you" in line]


class Account:
    balance = 1
    _hidden = 2

    def read(self):
        return self.hidden

    def name(self):
        return balance


def local(amount):
    rate = 3
    return amount * rte


def chained():
    try:
        local(1)
    except NameError as first:
        raise AttributeError("explained") from Account().balanse


def in_context():
    try:
        Account().balanse
    except AttributeError:
        return local(2)


def grouped():
    errors = []
    for work in (lambda: local(1), lambda: Account().balanse, Account().read, Account().name):
        try:
            work()
        except Exception as exc:
            errors.append(exc)
    raise ExceptionGroup("several", errors)


# every way to the formatted text
for label, work in (("local", lambda: local(1)), ("attribute", lambda: Account().balanse), ("private", Account().read), ("self", Account().name),
                    ("chained", chained), ("context", in_context), ("group", grouped)):
    try:
        work()
    except BaseException as exc:
        buffer = io.StringIO()
        traceback.print_exception(exc, file=buffer)
        print(label, "print_exception:", added(buffer.getvalue()))
        print(label, "format_exc:", added(traceback.format_exc()))
        print(label, "format_exception:", added("".join(traceback.format_exception(type(exc), exc, exc.__traceback__))))
        te = traceback.TracebackException.from_exception(exc)
        print(label, "TracebackException:", added("".join(te.format())), added(str(te)), added("".join(te.format_exception_only())))
        print(label, "no traceback given:", added("".join(traceback.format_exception(type(exc), exc, None))))
        buffer = io.StringIO()
        sys.stderr, kept = buffer, sys.stderr
        try:
            traceback.print_exc()
        finally:
            sys.stderr = kept
        print(label, "print_exc:", added(buffer.getvalue()))

# the frame is still running: the handler is in the frame that raised
def same_frame():
    near = 1
    try:
        naer
    except NameError:
        return added(traceback.format_exc())


class Method:
    _private = 1

    def same_frame(self):
        try:
            self.private
        except AttributeError:
            return added(traceback.format_exc())


print("in the frame that raised:", same_frame(), Method().same_frame())
try:
    logging_nam
except NameError:
    print("in the module's body:", added(traceback.format_exc()))


class Body:
    first_one = 1
    try:
        first_on
    except NameError:
        said = added(traceback.format_exc())


print("in a class body still running:", Body.said)

# two exceptions of one frame: the second left it, and its entry has the locals the first one's is asked for
def raises_another():
    held = 1
    try:
        hled
    except NameError:
        raise KeyError("second")


try:
    raises_another()
except KeyError as second:
    print("the first of two exceptions of one frame:", added("".join(traceback.format_exception(second))))

# logging and unittest format with the traceback
stream = io.StringIO()
logging.basicConfig(stream=stream, level=logging.DEBUG, format="%(message)s")
try:
    local(3)
except NameError:
    logging.exception("failed")
try:
    Account().read()
except AttributeError:
    logging.getLogger("x").error("again", exc_info=True)
print("logging:", added(stream.getvalue()))


class Tests(unittest.TestCase):
    def test_name(self):
        local(4)

    def test_attribute(self):
        Account().balanse


result = unittest.TestResult()
unittest.defaultTestLoader.loadTestsFromTestCase(Tests).run(result)
print("unittest:", sorted(hint for _, text in result.errors for hint in added(text)))

# names that are not ASCII are compared in their normal form
class Cafe:
    café = 1


for work in (lambda: Cafe().café, lambda: Cafe().cafè):
    try:
        work()
    except AttributeError:
        print("not ASCII:", [ascii(h) for h in added(traceback.format_exc())])
""".replace("\\u00e9", "é").replace("\\u0301", "́").replace("\\u00e8", "è")

# An entry has the locals of a frame an exception left, for as long as that exception's entry lives; a frame that caught the
# exception and went on kept its own, and they went with it
STOPS = (
    ("import traceback\ndef waits():\n    counted = 1\n    try:\n        countd\n    except NameError as exc:\n        yield exc\n    yield None\n"
     "print('start')\ngen = waits()\ntraceback.format_exception(next(gen))\n", "a generator that waits"),
    ("import traceback\ndef f():\n    near = 1\n    try:\n        naer\n    except NameError:\n        return [traceback.format_exc() for _ in range(1)]\n"
     "print('start')\nf()\n", "comprehension running in it"),
)


def _stops(source: str, words: str) -> None:
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(source, encoding="utf-8")
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
    assert (got.returncode, got.stdout) == (70, "start\n") and words in got.stderr, got


def test_every_way_to_the_formatted_text() -> None:
    same({"main.py": WAYS})


def test_frames_whose_locals_cannot_be_read_stop() -> None:
    for source, words in STOPS:
        _stops(source, words)


if __name__ == "__main__":
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            value()
    print("ok")
