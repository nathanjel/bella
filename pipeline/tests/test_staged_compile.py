"""A staged compile() compiled, against CPython (docs/staging.md section 4; C-8-11 is the case): the code object it
returns, run by eval and exec in the namespaces given (which the dialect keeps from a program's own source, and a library
may do), its names and counts, ==, the comparison and hash slots, the closure check, and compile()'s own checks of its
arguments with their messages. What it cannot give stops by name."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

PROBE = r"""
from typing import TypeVar
T = TypeVar("T", bound="Item")
c = T.__bound__.__forward_code__
print(c.co_name, c.co_filename, c.co_firstlineno, c.co_varnames, c.co_flags)
try:
    eval(c, {})
except NameError as e:
    print("NameError", e.name)
class Item:
    pass
print(eval(c))
print(eval(c, {"Item": 5}))
print(eval(c, {"Item": 5}, {"Item": 6}))
print(exec(c, {"Item": 1}))
g = {}
exec(c, g, {"Item": 2})
print(sorted(g))
try:
    exec(c, {}, closure=(1,))
except TypeError as e:
    print(e)
U = TypeVar("U", bound="Item")
d = U.__bound__.__forward_code__
V = TypeVar("V", bound="Other")
print(c == d, c != d, c is d, c == V.__bound__.__forward_code__, c == 1, type(c).__eq__(c, d), type(c).__lt__(c, d))
try:
    c < d
except TypeError as e:
    print(e)
def f(): pass
print(f.__code__ == f.__code__, f.__code__ == c, hash(f.__code__) == hash(f.__code__))
for args, kw in [(("x", "<s>", "eval"), {"flags": 0x10000000}), (("x", "<s>", "evil"), {}), (("x", "<s>", 5), {}),
                 ((5, "<s>", "eval"), {}), (("x", "<s>", "eval"), {"optimize": 3}), (("x", "<s>", "eval"), {"module": 5}),
                 (("x", "<s>"), {}), (("x", "<s>", "eval", 0, 0, 0, 0), {}), (("x", "<s>", "eval"), {"bogus": 1}),
                 (("x", 5, "eval"), {}), (("x", "<s>", "eval", "a"), {}), (("x", "<s>", "eval", 2**40), {}),
                 ((), {"source": "x", "filename": "f", "mode": "eval", "flag": 1}),
                 (("x",), {"source": "y", "filename": "f", "mode": "eval"}), (("x", "a\0b", "eval"), {}), (("x", "<s>", "ev\0al"), {})]:
    try:
        compile(*args, **kw)
    except (TypeError, ValueError, OverflowError) as e:
        print(type(e).__name__, e)
"""

# what a staged compile's code object cannot give, and the compiles the build has no outcome for
STOPS = {
    "hash() of a code object a staged compile() made": 'from typing import TypeVar\nT = TypeVar("T", bound="X")\nhash(T.__bound__.__forward_code__)',
    "exec() of a function's code object": "def f():\n    pass\nexec(f.__code__, {})",
    "of a text the dry run did not stage": 'def later():\n    return compile("y", "<s>", "eval")\nif __name__ == "__main__":\n    later()',
    "compile() to an ast tree at ast:parse": 'import ast\nast.parse("x")',
    "in mode 'single'": 'compile("1", "<s>", "single")',
}


def test_the_code_a_staged_compile_returns() -> None:
    same(PROBE)


def test_what_it_cannot_give_stops_by_name() -> None:
    if shutil.which("g++") is None:
        return
    for why, body in STOPS.items():
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text("print('start')\n" + body + "\nprint('not reached')\n", encoding="utf-8")
            got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
        assert (got.returncode, got.stdout) == (70, "start\n") and why in got.stderr, (why, got)


if __name__ == "__main__":
    test_the_code_a_staged_compile_returns()
    test_what_it_cannot_give_stops_by_name()
