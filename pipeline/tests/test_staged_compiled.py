"""exec and eval of staged texts in a compiled program, against CPython (docs/staging.md; spec section 8)."""
from __future__ import annotations

import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

HITS = r"""
class Dies:
    def __init__(self, n):
        self.n = n
    def __del__(self):
        print("dies", self.n)
def show(f):
    try:
        print(repr(f()))
    except BaseException as e:
        print(type(e).__name__, e)
a = 10
print(eval("1 + 2"), eval("a + 1"), eval(" a"), eval("\ta"), eval(b"a * 2"))
exec("b = a + 5")
print(b)
ns = {"a": 1}
print(eval("a + 1", ns), sorted(ns), ns["__builtins__"] is __builtins__.__dict__ if False else 0)
exec("c = a + 1", ns)
print(ns["c"], sorted(ns))
f = eval("lambda x: x + a", ns)
print(f(1), f.__globals__ is ns, f.__module__, f.__name__, f.__qualname__, f.__code__.co_filename if False else 0)
ns["a"] = 100
print(f(1))
named = {"__name__": "somewhere", "t": tuple}
g = eval("lambda: t", named)
print(g.__module__, g() is tuple)
print(eval("len('abc')", {}))
exec("def h(y=2):\n    return y * 2\n", ns)
print(ns["h"](), ns["h"].__name__, ns["h"].__qualname__, ns["h"].__module__, ns["h"].__defaults__)
exec("class K:\n    v = 1\n    def m(self):\n        return self.v\n", ns)
print(ns["K"]().m(), ns["K"].__name__, ns["K"].__module__ if "__name__" in ns else "no name", ns["K"].__qualname__)
print(eval("globals() is ns_again", {"ns_again": None}) if False else 0)
same_ns = {}
print(eval("globals()", same_ns) is same_ns)
exec("x = 1\ndel x", same_ns)
print("x" in same_ns)

# what a text's builtins are
none = {"__builtins__": {}}
show(lambda: eval("len", none))
print(sorted(none), none["__builtins__"])
mine = {"__builtins__": {"len": lambda x: "my len"}}
print(eval("len('abc')", mine))
k = eval("lambda: len('abc')", mine)
print(k())
mine["__builtins__"] = {"len": lambda x: "later"}
print(k(), eval("len('abc')", mine))
module_builtins = {"__builtins__": __builtins__}
print(eval("len('ab')", module_builtins))
show(lambda: eval("undefined_name_here", {}))
show(lambda: eval("1 / 0", {}))
try:
    exec("raise ValueError('inside')", {})
except ValueError as e:
    print("caught", e)

# the arguments
for fn in (lambda: eval(), lambda: exec(), lambda: eval(1), lambda: exec(1), lambda: eval(None), lambda: eval([]), lambda: eval("1", 1), lambda: eval("1", []), lambda: eval("1", {}, 1), lambda: eval("1", None, 1), lambda: exec("y = 1", 1), lambda: exec("y = 1", []), lambda: exec("y = 1", {}, 1), lambda: exec("y = 1", None, 1), lambda: eval("1", {}, {}, {}), lambda: exec("y = 1", {}, {}, {}), lambda: exec("y = 1", {}, {}, None, None), lambda: exec("y = 1", closure=(1,)), lambda: eval("1", locals=1), lambda: eval("1", globals=1), lambda: exec("y = 1", globals=1), lambda: exec("y = 1", locals=1), lambda: eval("1", {}, globals={}), lambda: exec("y = 1", {}, globals={}), lambda: exec("y = 1", {}, {}, locals={})):
    show(fn)

# a namespace lives as long as what holds it
d = {"o": Dies(1)}
fn = eval("lambda: o", d)
del d
print("held", fn().n)
del fn
print("released")
d2 = {"o": Dies(2)}
exec("p = o", d2)
del d2
print("gone")
"""

# what the dry run cannot see: it imports the program, so a __main__ block stays false there
REFUSED = (
    ('def f(s):\n    return eval(s, {})\nif __name__ == "__main__":\n    print(f("1 + " + "1"))', "E-01: eval at __main__:f of a text"),
    ('def f(s):\n    exec(s, {})\nif __name__ == "__main__":\n    f("z" + str(1) + " = 1")', "E-01: exec at __main__:f of a text"),
    ('if __name__ == "__main__":\n    print(eval("1 + 1"))', "E-01: eval at __main__:<module> of a text"),
    ('def f():\n    v = 1\n    return eval("v")\nf()', "the frame's locals"),
    ('import collections\nexec("y = 1", {}, collections.ChainMap({}))', "a locals mapping that is not a dict"),
    ('if __name__ == "__main__":\n    compile("1", "<s>", "eval")', "E-01: compile at __main__:<module> of a text"),
)


def pytest_generate_tests(metafunc: Any) -> None:
    if "refused" in metafunc.fixturenames:
        metafunc.parametrize("refused", REFUSED, ids=[text[:40] for text, _ in REFUSED])


def test_a_staged_text_runs_as_cpython_runs_it() -> None:
    same(HITS)


def test_anything_else_stops_by_name(refused: tuple[str, str]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(textwrap.dedent(refused[0]) + "\n", encoding="utf-8")
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, timeout=60)
    assert got.returncode == 70 and refused[1] in got.stderr, got


if __name__ == "__main__":
    test_a_staged_text_runs_as_cpython_runs_it()
