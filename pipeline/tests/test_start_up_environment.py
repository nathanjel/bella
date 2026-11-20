"""The variables of CPython's start-up and a compiled program (the specification's Environment paragraph, D-18; C-8-16).

Read (the author's decision of 2026-11-20, review log RL-527): `PYTHONUNBUFFERED`, `PYTHONINTMAXSTRDIGITS`, `PYTHON_CPU_COUNT`,
and `PYTHONHASHSEED` as before. One probe is run under CPython and compiled with each value, and the two must agree on standard
output, the exit status and standard error, to the letter where CPython refuses the value and ends before the program's first line.

Not read: `PYTHONWARNINGS` (the author's decision of the same day, RL-483) and the others that only an interpreter has a use
for or that the decision left out. Whatever such a variable says, a compiled program runs as CPython does without it, so there
the compiled program with the variable is compared with CPython without it, and CPython with it must differ, or the row shows
nothing.

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


# what the variables that are read change, and what those that are not read would change under CPython
PROBE = '''
import os
import sys

flag = True
print("debug:", __debug__)
try:
    assert flag is False
    print("assert skipped")
except AssertionError:
    print("assert raised")
print("flags:", sys.flags)
print("warnoptions:", sys.warnoptions, "| dont_write_bytecode:", sys.dont_write_bytecode, "| pycache_prefix:", sys.pycache_prefix)
print("digits:", sys.get_int_max_str_digits())
for size in (640, 641, 4300, 4301):
    try:
        print(size, len(str(10 ** (size - 1))), end=" ")
    except ValueError:
        print(size, "refused", end=" ")
    try:
        print(len(str(int("7" * size))))
    except ValueError:
        print("refused")
sys.set_int_max_str_digits(5000)
print("digits set:", sys.get_int_max_str_digits(), sys.flags.int_max_str_digits)
print("cpus:", os.cpu_count(), os.process_cpu_count(), sys._get_cpu_count_config())
for stream in (sys.stdin, sys.stdout, sys.stderr):
    print(stream.name, stream.encoding, stream.errors, stream.line_buffering, stream.write_through, type(stream.buffer).__name__)
sys.stdout.flush()
sys.stdout.write("through, ")
os.write(1, b"past, ")
sys.stdout.write("through again\\n")
sys.stdout.flush()
sys.stderr.write("through, ")
os.write(2, b"past, ")
sys.stderr.write("through again\\n")
with open(sys.argv[0]) as source:
    print("opened:", source.encoding.lower())
if "BELLA_TEST_HASHES" in os.environ:
    print("hashes:", hash("the same text"), hash(b"the same bytes"), hash(("a", 1.5)), sorted({"b", "a", "c"}) == ["a", "b", "c"])
'''

READ: dict[str, list[str]] = {
    "PYTHONUNBUFFERED": ["1", "0", "yes", "-3", "2", " 1", "00", "1x", "0.5", "-0", "99999999999999999999", " "],
    "PYTHONINTMAXSTRDIGITS": ["0", "640", "641", "1000", " 700", "+800", "2147483647", "639", "1", "-1", "-0", "2147483648",
                              "99999999999999999999", "700 ", "0x400", "many", "6_40", "640.0", " "],
    "PYTHON_CPU_COUNT": ["1000003", "1", " 7777", "+12", "2147483647", "default", "0", "-2", "2147483648", "5x", "Default", "many",
                         "default ", " "],
    "PYTHONHASHSEED": ["0", "7", " 7", "+7", "007", "4294967295", "4294967296", "-1", "-0", "7x", "Random", "seven",
                       "18446744073709551616", " "],
}
# two that cannot be taken: the seed is told of first, then the digits
TOGETHER = [{"PYTHONINTMAXSTRDIGITS": "5", "PYTHON_CPU_COUNT": "0", "PYTHONHASHSEED": "seven"}, {"PYTHONINTMAXSTRDIGITS": "5", "PYTHON_CPU_COUNT": "0"},
            {"PYTHON_CPU_COUNT": "0", "PYTHONHASHSEED": "seven"}, {"PYTHONINTMAXSTRDIGITS": "640", "PYTHON_CPU_COUNT": "3", "PYTHONUNBUFFERED": "1"}]
NOT_READ = [("PYTHONOPTIMIZE", "1"), ("PYTHONOPTIMIZE", "2"), ("PYTHONDEVMODE", "1"), ("PYTHONWARNINGS", "error"),
            ("PYTHONWARNDEFAULTENCODING", "1"), ("PYTHONDONTWRITEBYTECODE", "1"), ("PYTHONPYCACHEPREFIX", "/nowhere"),
            ("PYTHONSAFEPATH", "1"), ("PYTHONNOUSERSITE", "1"), ("PYTHONDEBUG", "1"), ("PYTHONVERBOSE", "1"), ("PYTHONINSPECT", "1"),
            ("PYTHONMALLOCSTATS", "1"), ("PYTHONPROFILEIMPORTTIME", "1"), ("PYTHONUTF8", "0")]
# no difference under CPython for this probe either: the row only holds that the compiled program is not disturbed
NOT_SEEN = [("PYTHONFAULTHANDLER", "1"), ("PYTHONTRACEMALLOC", "1"), ("PYTHONMALLOC", "debug"), ("PYTHONNODEBUGRANGES", "1"),
            ("PYTHONPATH", "/nowhere"), ("PYTHON_LAZY_IMPORTS", "all"), ("PYTHONSTARTUP", "/nowhere"), ("PYTHONHOME", "/nowhere"),
            ("PYTHONPLATLIBDIR", "lib64"), ("PYTHON_GIL", "1"), ("PYTHON_CONTEXT_AWARE_WARNINGS", "0"), ("PYTHON_THREAD_INHERIT_CONTEXT", "1"),
            ("PYTHON_FROZEN_MODULES", "off"), ("PYTHONPERFSUPPORT", "1"), ("PYTHON_JIT", "1"), ("PYTHON_DISABLE_REMOTE_DEBUG", "1")]
Outcome = tuple[str, int, list[str]]


def _probe(tmp: str) -> tuple[dict[str, str], list[str], list[str]]:
    """The environment without any of CPython's variables, and the two commands."""
    prog = Path(tmp, "prog.py")
    prog.write_text(PROBE, encoding="utf-8")
    env = {name: value for name, value in os.environ.items() if not name.startswith("PYTHON")}
    return env, [sys.executable, "prog.py"], [str(build(prog, "prog.py"))]


def _run(cmd: list[str], env: dict[str, str], tmp: str) -> Outcome:
    done = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env, cwd=tmp, stdin=subprocess.DEVNULL)
    return done.stdout, done.returncode, _report(done.stderr)


def test_the_variables_that_are_read() -> None:
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        base, cpython, compiled = _probe(tmp)
        fixed = base | {"PYTHONHASHSEED": "0", "BELLA_TEST_HASHES": "1"}
        want = _run(cpython, fixed, tmp)
        assert want[1] == 0 and "through, past, through again" not in want[0], want
        assert _run(compiled, fixed, tmp) == want
        refused = 0
        for name, values in READ.items():
            for value in values:
                env = fixed | {name: value}
                ref = _run(cpython, env, tmp)
                assert _run(compiled, env, tmp) == ref, f"{name}={value!r}"
                refused += ref[1] == 1
                if ref[1] == 1:
                    assert ref[0] == "" and ref[2][0].startswith("Fatal Python error: config_init_"), ref
        assert refused == 26, refused
        for more in TOGETHER:
            env = fixed | more
            assert _run(compiled, env, tmp) == _run(cpython, env, tmp), more
        for seed in ("random", ""):                  # another key in every run: only what does not depend on it
            env = base | {"PYTHONHASHSEED": seed}
            assert _run(compiled, env, tmp) == _run(cpython, env, tmp), seed
        # the record is of the start: what the program does to its environment afterwards changes nothing
        late = base | {"PYTHONHASHSEED": "0"}
        Path(tmp, "late.py").write_text("import os\nimport sys\nos.environ['PYTHON_CPU_COUNT'] = '1000003'\n"
                                        "os.environ['PYTHONINTMAXSTRDIGITS'] = '640'\nos.putenv('PYTHON_CPU_COUNT', '1000003')\n"
                                        "print(os.cpu_count() == 1000003, os.process_cpu_count() == 1000003, sys.get_int_max_str_digits())\n",
                                        encoding="utf-8")
        ref = _run([sys.executable, "late.py"], late, tmp)
        assert ref[0] == "False False 4300\n", ref
        assert _run([str(build(Path(tmp, "late.py"), "late.py"))], late, tmp) == ref


def test_the_variables_that_are_not_read() -> None:
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        base, cpython, compiled = _probe(tmp)
        base |= {"PYTHONHASHSEED": "0"}
        want = _run(cpython, base, tmp)
        assert want[1] == 0, want
        assert _run(compiled, base, tmp) == want
        for name, value in NOT_READ:
            assert _run(cpython, base | {name: value}, tmp) != want, f"CPython no longer reads {name}: the row shows nothing"
            assert _run(compiled, base | {name: value}, tmp) == want, f"{name}={value!r}"
        for name, value in NOT_SEEN:
            assert _run(compiled, base | {name: value}, tmp) == want, f"{name}={value!r}"


# programs that use the streams, each with both outputs in one pipe, so that the order of the writes is seen
IN_USE: dict[str, str] = {
    "an uncaught exception after output": '''
import sys

print("a line")
sys.stdout.write("half a line, ")
sys.stderr.write("half a line of errors, ")
print("more", file=sys.stderr)


def total(rows: list[int]) -> int:
    return sum(rows) // len(rows)


total([])
''',
    "leaving without a flush": '''
import os
import sys

sys.stdout.write("written, and then the process is gone")
sys.stderr.write("so is this")
os._exit(3)
''',
    "input and its prompt": '''
import sys

sys.stdout.write("before the prompt; ")
answer = input("a question? ")
print("answered", repr(answer))
print(repr(sys.stdin.readline()), repr(sys.stdin.read()))
try:
    input("another? ")
except EOFError:
    print("no more")
''',
    "bytes under the text, a warning, and an exit with words": '''
import sys

flag = True
sys.stdout.write("text, ")
sys.stdout.buffer.write(b"bytes under it, ")
sys.stdout.write("text again\\n")
print(~flag)
print("x" * 200000 == sys.stdout.write("x" * 200000) * "x", file=sys.stderr)
sys.stdout.write("\\nthe last of standard output, ")
raise SystemExit("the words of the exit")
''',
}


def test_streams_in_use_with_and_without_their_buffers() -> None:
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        base = {name: value for name, value in os.environ.items() if not name.startswith("PYTHON")} | {"PYTHONHASHSEED": "0"}
        for title, source in IN_USE.items():
            prog = Path(tmp, "prog.py")
            prog.write_text(source, encoding="utf-8")
            exe = str(build(prog, "prog.py"))
            seen = []
            for more in ({}, {"PYTHONUNBUFFERED": "1"}, {"PYTHONUNBUFFERED": "0"}):
                both = []
                for cmd in ([sys.executable, "prog.py"], [exe]):
                    done = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, env=base | more, cwd=tmp,
                                          input=b"an answer\nthe second line\nthe rest")
                    both.append((_report(done.stdout.decode()), done.returncode))
                assert both[0] == both[1], f"{title} {more}:\n--- CPython\n{both[0]}\n--- compiled\n{both[1]}"
                seen.append(both[0])
            assert seen[0] == seen[2], title
            assert seen[0] != seen[1] or title.startswith("input"), f"{title}: nothing is seen of the buffers"


def test_sys_flags_when_the_limit_of_digits_is_set() -> None:
    """_PySys_SetFlagObj: sys.flags is a new object each time; the one the program kept says what it said (RL-530)."""
    if shutil.which("g++") is None:
        return
    source = '''
import sys

held = sys.flags
sys.set_int_max_str_digits(700)
print(held.int_max_str_digits, sys.flags.int_max_str_digits, held is sys.flags, type(held) is type(sys.flags), held == sys.flags)
print(sys.flags[:17] == held[:17], sys.flags.gil == held.gil, sys.flags.lazy_imports == held.lazy_imports, len(sys.flags))
try:
    sys.set_int_max_str_digits(5)
except ValueError:
    print("ValueError", sys.get_int_max_str_digits(), sys.flags.int_max_str_digits)
del sys.flags
try:
    sys.set_int_max_str_digits(800)
except RuntimeError as e:
    print("RuntimeError", e.args, sys.get_int_max_str_digits())
sys.flags = held
sys.set_int_max_str_digits(900)
print(held.int_max_str_digits, sys.flags.int_max_str_digits, sys.get_int_max_str_digits())
'''
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(source, encoding="utf-8")
        env = dict(os.environ, PYTHONHASHSEED="0")
        assert _run([str(build(prog, "prog.py"))], env, tmp) == _run([sys.executable, "prog.py"], env, tmp)


def test_pythonwarnings_is_ignored_without_the_module() -> None:
    _ignored(PROGRAMS["without warnings"])


def test_pythonwarnings_is_ignored_with_the_module() -> None:
    _ignored(PROGRAMS["holding warnings"])


if __name__ == "__main__":
    test_the_variables_that_are_read()
    test_the_variables_that_are_not_read()
    test_streams_in_use_with_and_without_their_buffers()
    test_sys_flags_when_the_limit_of_digits_is_set()
    test_pythonwarnings_is_ignored_without_the_module()
    test_pythonwarnings_is_ignored_with_the_module()
