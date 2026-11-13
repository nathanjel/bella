"""traceback formatted from a traceback's entries and from the running stack, the path finder's discovery and _suggestions,
compiled, against CPython: the words of the errors the cases compare by class (C-7-82, C-7-83, C-7-84, C-8-13), discovery of a
program's own modules beside it, and what stops by name."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

WORDS = r"""
import _suggestions, importlib.machinery, importlib.util, string, traceback
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
g = _suggestions._generate_suggestions
print(m(lambda: g()), m(lambda: g([])), m(lambda: g([], "a", 1)), m(lambda: g([], item="a")), m(lambda: g((), "a")), m(lambda: g([1], "a")),
      m(lambda: g([], 1)), m(lambda: g(["a"], "\ud800")), m(lambda: g(["𐏿", "b"], "a")), m(lambda: g(["a"], b"a")), m(lambda: g({}, 1)))
print(g.__doc__, g.__name__, g.__qualname__, g.__module__, type(g).__name__, _suggestions.__doc__, sorted(n for n in vars(_suggestions) if not n.startswith("__")))
def raises():
    raise KeyError(1)
try:
    1 / 0
except ZeroDivisionError as exc:
    tb = exc.__traceback__
try:
    raises()
except KeyError as exc:
    tb2 = exc.__traceback__
print(m(lambda: setattr(tb, "tb_next", 1)), m(lambda: delattr(tb, "tb_next")), m(lambda: setattr(tb, "tb_next", tb)),
      m(lambda: setattr(tb2.tb_next, "tb_next", tb2)), m(lambda: setattr(tb2, "tb_next", "x")))
inner = tb2.tb_next
tb2.tb_next = None
print(tb2.tb_next, [fs.name for fs in traceback.extract_tb(tb2)])
tb2.tb_next = tb
print(tb2.tb_next is tb, [fs.name for fs in traceback.extract_tb(tb2)], inner.tb_next)
try:
    list(importlib.machinery.PathFinder.discover(importlib.util.find_spec("string")))
except ValueError as exc:
    print(type(exc).__name__, str(exc).startswith("ModuleSpec(name='string'"), str(exc).endswith("is not a package module"))
"""

UNITTEST = r"""
import re, traceback, unittest
class T(unittest.TestCase):
    def test_fails(self):
        self.assertEqual(1, 2)
    def test_errors(self):
        raise ValueError("boom")
    def test_chained(self):
        try:
            {}["k"]
        except KeyError as exc:
            raise RuntimeError("r") from exc
    def helper(self):
        self.assertTrue(False)
    def test_helper(self):
        self.helper()
    def test_in_context(self):
        with self.assertRaises(KeyError):
            self.fail("not that one")
    def test_raises(self):
        with self.assertRaises(KeyError) as caught:
            {}["k"]
        print("caught:", type(caught.exception).__name__, caught.exception.args, caught.exception.__traceback__)
        self.assertRaises(ZeroDivisionError, lambda: 1 // 0)
        with self.assertRaisesRegex(ValueError, "b.d"):
            raise ValueError("bad")
    def test_not_raised(self):
        with self.assertRaises(KeyError):
            pass
result = unittest.TestResult()
unittest.defaultTestLoader.loadTestsFromTestCase(T).run(result)
print(result.testsRun, len(result.failures), len(result.errors))
for test, text in sorted(result.failures + result.errors, key=lambda pair: pair[0].id()):
    print(test.id(), [re.sub(r'File ".*?"', 'File "<prog>"', line) for line in text.splitlines() if not line.startswith("    ")])
"""

# _Py_CalculateSuggestions against the pin's own, over generated names: few letters in both cases, so that prefixes and suffixes are
# shared, case flips and near misses are common, and lengths cross the 40 bytes; some names beyond ASCII (the distance is over UTF-8)
SWEEP = r"""
import _suggestions
state = 12345
def rand(n):
    global state
    state = (state * 1103515245 + 12345) % 2**31
    return (state >> 8) % n
ALPHABET = "abAB_é"
def word():
    kind = rand(10)
    length = rand(4) if kind == 0 else 38 + rand(8) if kind == 1 else 1 + rand(12)
    return "".join(ALPHABET[rand(len(ALPHABET)) if rand(7) == 0 else rand(2)] for _ in range(length))
def near(w):
    out = list(w)
    for _ in range(rand(4)):
        if not out:
            break
        i = rand(len(out))
        choice = rand(4)
        if choice == 0:
            out[i] = out[i].swapcase()
        elif choice == 1:
            del out[i]
        elif choice == 2:
            out.insert(i, ALPHABET[rand(len(ALPHABET))])
        else:
            out[i] = ALPHABET[rand(len(ALPHABET))]
    return "".join(out)
total = 0
chosen = 0
for trial in range(6000):
    name = word()
    candidates = [near(name) if rand(3) else word() for _ in range(rand(9))]
    got = _suggestions._generate_suggestions(candidates, name)
    if got is not None:
        chosen += 1
        total = (total * 31 + candidates.index(got) + 7 * len(got)) % 1000000007
    else:
        total = (total * 31 + 1) % 1000000007
print(chosen, total)
"""

# traceback.clear_frames: a frame the exception left gives up its locals when cleared, not when the traceback dies
CLEARED = r"""
import traceback, weakref
class K:
    pass
seen = []
def leaves():
    k = K()
    seen.append(weakref.ref(k))
    raise ValueError("x")
def catches():
    mine = K()
    seen.append(weakref.ref(mine))
    try:
        leaves()
    except ValueError as exc:
        tb = exc.__traceback__
        print([r() is not None for r in seen])
        print(traceback.clear_frames(tb), [r() is not None for r in seen], [fs.name for fs in traceback.extract_tb(tb)])
        traceback.clear_frames(tb)
        return tb
tb = catches()
print(seen[1]() is not None, traceback.clear_frames(None))   # not seen[0]: a frame that caught and returned keeps its locals (RL-222)
class Fake:
    tb_next = None
    class tb_frame:
        @staticmethod
        def clear():
            print("a frame of the program's own making is cleared")
            raise RuntimeError("still running")
print(traceback.clear_frames(Fake()))
"""

# a text's frames: each entry's globals are the namespace the text ran in, held by the entry after the namespace is dropped
STAGED = r"""
import traceback, unittest
result = unittest.TestResult()
def entries(namespace):
    try:
        exec("def boom():\n    raise ValueError('x')\nboom()\n", namespace)
    except ValueError as exc:
        tb = exc.__traceback__
    out = []
    while tb is not None:
        out.append(tb)
        tb = tb.tb_next
    return out
plain = entries({})
marked = entries({"__unittest": True})
junk = [bytearray(64) for _ in range(2000)]
print([result._is_relevant_tb_level(tb) for tb in plain], [result._is_relevant_tb_level(tb) for tb in marked])
print([(fs.filename.rpartition("/")[2], fs.lineno, fs.name) for fs in traceback.extract_tb(marked[0])])
"""

BESIDE = r"""
import importlib, importlib.machinery, traceback, helper
names = {spec.name for spec in importlib.machinery.PathFinder.discover()}
print("helper" in names)
try:
    importlib.import_module("helpr")
except ModuleNotFoundError as exc:
    print(traceback.format_exception_only(exc)[-1].rstrip().endswith(". Did you mean: 'helper'?"))
"""

# the running stack (C-7-84): a staged text's frames, the words for what is no frame, a traceback where a frame is wanted (its entry
# stands for its frame only inside traceback), and the frame the walk of a traceback gives, handed back to StackSummary
RUNNING = r"""
import io, re, traceback
def named(line):
    return re.sub(r'File ".*?"', 'File "<prog>"', line)
def rows(stack):
    return [(fs.filename.rpartition("/")[2], fs.lineno, fs.name) for fs in stack]
def m(f):
    try:
        return repr(f())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)
ns = {"traceback": traceback}
exec("stack = traceback.extract_stack()\ndef f():\n    return traceback.extract_stack()\nstack2 = f()\n", ns)
print(rows(ns["stack"]), rows(ns["stack2"]), rows(eval("traceback.extract_stack()")), rows(eval("traceback.extract_stack(limit=1)")))
def raises():
    raise KeyError(1)
try:
    raises()
except KeyError as exc:
    tb = exc.__traceback__
for bad in (5, "frame", tb, int, [(tb, 1)]):
    print(m(lambda: traceback.extract_stack(bad)), m(lambda: traceback.format_stack(bad)), m(lambda: traceback.print_stack(bad)))
print(m(lambda: traceback.StackSummary.extract(iter([(tb, 1)]))), m(lambda: traceback.StackSummary.extract([(5, 1)])), m(lambda: traceback.StackSummary.extract([5])),
      m(lambda: traceback.StackSummary.extract([(tb.tb_next, 1)], capture_locals=True)), m(lambda: traceback.StackSummary.extract([])))
walked = list(traceback._walk_tb_with_full_positions(tb))
print(len(walked), [type(frame).__name__ for frame, _ in walked], [positions[0] for _, positions in walked])
print(rows(traceback.StackSummary.extract([(frame, 7) for frame, _ in walked])), rows(traceback.StackSummary.extract([(walked[1][0], 3)] * 2, limit=1)))
def inner(**kwds):
    return traceback.extract_stack(**kwds)
print(rows(inner(f=None)), rows(inner(f=None, limit=1)), rows(inner(limit=-1)), m(lambda: inner(g=1)), m(lambda: traceback.extract_stack(None, None, None)))
out = io.StringIO()
print(traceback.print_stack(file=out), [named(line) for line in out.getvalue().splitlines() if not line.startswith("    ")])
print(m(lambda: traceback.print_stack(file=5)), [named(chunk.split("\n")[0]) for chunk in traceback.format_stack(None, 1)])
"""


def test_the_words() -> None:
    same(WORDS)


def test_unittest_reports_only_the_tests_own_entries() -> None:
    """unittest drops its own entries from a failure's traceback by each frame's globals, and cuts an assertion's at the first
    of its own by assigning tb_next: the reports name the test's frames and nothing of unittest's."""
    same(UNITTEST)


def test_the_choice_of_a_suggestion() -> None:
    same(SWEEP)


def test_clear_frames() -> None:
    same(CLEARED)


def test_a_texts_entries_keep_its_namespace() -> None:
    same(STAGED)


def test_a_programs_own_modules_beside_it() -> None:
    """The program's directory holds a module it imports; the build found it there, so the path finder lists it, and the report of
    a misspelt import suggests it. Compiled only: CPython lists every module of every sys.path entry, so whether it suggests
    anything depends on what is installed (from 750 candidates on, nothing)."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "helper.py").write_text("X = 1\n", encoding="utf-8")
        prog = Path(tmp, "prog.py")
        prog.write_text(BESIDE, encoding="utf-8")
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
    assert (got.returncode, got.stdout) == (0, "True\nTrue\n"), got


def test_the_running_stack() -> None:
    same(RUNNING)


def test_a_frame_is_not_the_programs_to_read() -> None:
    """E-02: the frames of the running stack are not given (walk_stack asks sys._getframe), and the frame the walk of a traceback
    gives is one of the type `frame` with nothing of CPython's to read."""
    if shutil.which("g++") is None:
        return
    cases = (("import traceback\nlist(traceback.walk_stack(None))", "sys._getframe (a frame object"),
             ("import traceback\ntry:\n    1 / 0\nexcept ZeroDivisionError as exc:\n    frame, _ = next(traceback._walk_tb_with_full_positions(exc.__traceback__))\n"
              "    frame.f_code", "frame.f_code"),
             ("import traceback\ntry:\n    1 / 0\nexcept ZeroDivisionError as exc:\n    list(traceback.walk_tb(exc.__traceback__))", "tb_frame"),
             ("import traceback\ntry:\n    1 / 0\nexcept ZeroDivisionError as exc:\n    frame, _ = next(traceback._walk_tb_with_full_positions(exc.__traceback__))\n"
              "    repr(frame)", "the repr of a frame"),
             ("import os, signal\nsignal.signal(signal.SIGUSR1, lambda signum, frame: print(repr(frame)))\nos.kill(os.getpid(), signal.SIGUSR1)", "the repr of a frame"))
    for body, name in cases:
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text(f"print('start')\n{body}\n", encoding="utf-8")
            got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
        assert (got.returncode, got.stdout) == (70, "start\n") and "not implemented" in got.stderr and name in got.stderr, (body, got)


def test_capture_locals_stops() -> None:
    if shutil.which("g++") is None:
        return
    source = ("import traceback\nprint('start')\ntry:\n    1 / 0\nexcept ZeroDivisionError as exc:\n"
              "    traceback.TracebackException.from_exception(exc, capture_locals=True)\n")
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(source, encoding="utf-8")
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
    assert (got.returncode, got.stdout) == (70, "start\n") and "traceback's capture_locals (the locals of a frame, E-02)" in got.stderr, got


if __name__ == "__main__":
    test_the_words()
    test_unittest_reports_only_the_tests_own_entries()
    test_the_choice_of_a_suggestion()
    test_clear_frames()
    test_a_texts_entries_keep_its_namespace()
    test_a_programs_own_modules_beside_it()
    test_the_running_stack()
    test_a_frame_is_not_the_programs_to_read()
    test_capture_locals_stops()
