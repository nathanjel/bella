"""Reviews A16 and G16 (2026-11-10; docs/reviews/review-log.md, RL-394 to RL-403): each fix's program and what stands around
it, compiled, against CPython; the names the bootstrap modules lack stop by name; the record guard keeps a prefix whole."""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pipeline.build import build
from pipeline.tests.test_review_2026_11_03 import same

# RL-394, RL-397: a built-in sequence's subclass loses sq_concat to its own __add__, sq_repeat to __mul__ or __rmul__, and the
# in-place slots to __iadd__ and __imul__; it has a number slot only when it defines one of the pair, and then that slot calls
# the method by name, the built-in's wrapper included
SEQUENCE_SLOTS = r"""
import _operator
def show(label, f):
    try:
        r = f()
        print(label, type(r).__name__, r)
    except TypeError as e:
        print(label, "TypeError", e)
NI = lambda self, other: NotImplemented
for base, item, other in ((list, [1], [2]), (tuple, (1,), (2,)), (str, "a", "b")):
    n = base.__name__
    Add = type("Add", (base,), {"__add__": NI})
    Mul = type("Mul", (base,), {"__mul__": NI})
    RMul = type("RMul", (base,), {"__rmul__": NI})
    IAdd = type("IAdd", (base,), {"__iadd__": NI})
    IMul = type("IMul", (base,), {"__imul__": NI})
    Both = type("Both", (base,), {"__add__": NI, "__iadd__": NI})
    Plain = type("Plain", (base,), {})
    show(n + " Add+", lambda: Add(item) + other)
    show(n + " other+Add", lambda: other + Add(item))
    show(n + " Mul*2", lambda: Mul(item) * 2)
    show(n + " 2*Mul", lambda: 2 * Mul(item))
    show(n + " RMul*2", lambda: RMul(item) * 2)
    show(n + " 2*RMul", lambda: 2 * RMul(item))
    show(n + " Plain+5", lambda: Plain(item) + 5)
    show(n + " other+Plain", lambda: other + Plain(item))
    show(n + " base.__add__", lambda: base.__add__(Add(item), other))
    show(n + " base.__mul__", lambda: base.__mul__(Mul(item), 2))
    def iadd(c):
        x = c(item); y = x; x += other; return (x, x is y, y)
    def imul(c):
        x = c(item); y = x; x *= 2; return (x, x is y, y)
    for label, c in (("IAdd", IAdd), ("Add", Add), ("Both", Both), ("Plain", Plain)):
        show(n + " " + label + "+=", lambda: iadd(c))
    for label, c in (("IMul", IMul), ("Mul", Mul), ("RMul", RMul), ("Plain", Plain)):
        show(n + " " + label + "*=", lambda: imul(c))
    show(n + " concat Add", lambda: _operator.concat(Add(item), other))
    show(n + " concat Plain", lambda: _operator.concat(Plain(item), other))
    show(n + " iconcat IAdd", lambda: _operator.iconcat(IAdd(item), other))
    show(n + " iconcat Both", lambda: _operator.iconcat(Both(item), other))
class Concat(list):
    def __add__(self, other): return "add"
    def __iadd__(self, other): return "iadd"
show("operator.concat", lambda: _operator.concat(Concat([1]), [2]))
show("operator.iconcat", lambda: _operator.iconcat(Concat([1]), [2]))
class X:
    def __radd__(self, o): return "radd"
    def __rmul__(self, o): return "rmul"
for v in ([1], type("L", (list,), {})([1]), "a", type("S", (str,), {})("a")):
    show(type(v).__name__ + " + X", lambda: v + X())
    show(type(v).__name__ + " * X", lambda: v * X())
class I(int): pass
def imul_int():
    n = I(2); n *= [1]; return n
show("int-subclass *= list", imul_int)
"""

# RL-395: PyCallable_Check of a built-in's subclass with __call__, and the exception group's predicate
CALLABLE = r"""
class Predicate(list):
    def __call__(self, e): return isinstance(e, ValueError)
class Number(int):
    def __call__(self): return int(self) + 1
class Text(str):
    pass
p = Predicate()
print(callable(p), callable(Number(1)), callable(Text("a")), Number(1)())
g = ExceptionGroup("g", [ValueError("v"), TypeError("t")])
print(g.subgroup(p).exceptions, [x.exceptions for x in g.split(p)])
"""

# RL-396: nb_index of a built-in's subclass, wherever an index is taken
INDEX = r"""
class L(list):
    def __index__(self): return 2
class T(tuple):
    def __index__(self): return 3
class S(str):
    def __index__(self): return 1
class F(float):
    def __index__(self): return 2
for f in (lambda: range(L()), lambda: [1] * L(), lambda: L() * [1], lambda: (1,) * T(), lambda: "ab" * S(), lambda: [10, 20, 30][L()],
          lambda: [10, 20, 30][S():], lambda: range(10)[F(0.5)], lambda: list(range(10))[L():T()], lambda: (1, 2, 3)[S()],
          lambda: hex(L()), lambda: [0, 1, 2].pop(S())):
    try:
        r = f()
        print(type(r).__name__, r)
    except TypeError as e:
        print("TypeError", e)
"""

# RL-398, RL-399, RL-403: the frozen modules' original names, the modules _bootstrap_external imports, the two modules' specs
FROZEN = r"""
import _imp, sys
import _frozen_importlib as boot, _frozen_importlib_external as ext
for name in ("_frozen_importlib", "_frozen_importlib_external", "zipimport", "os", "__hello_only__", "__phello_alias__", "nope"):
    print(name, _imp.find_frozen(name))
print(ext._imp is _imp, ext._io is sys.modules["_io"], ext._warnings is sys.modules["_warnings"], ext.sys is sys)
for m in (boot, ext):
    s = m.__spec__
    print(s, s.loader_state.origname, (s.loader_state.filename or "").rsplit("/", 2)[-2:], m.__loader__, repr(m.__package__),
          "__file__" in vars(m), s.submodule_search_locations, s.has_location, s.parent)
import importlib.util
print(importlib.util.find_spec("_frozen_importlib"), importlib.util.find_spec("_frozen_importlib_external"))
import importlib
print(boot.__file__.rsplit("/", 2)[-2:], ext.__file__.rsplit("/", 2)[-2:], sys._stdlib_dir == ext.__file__.rsplit("/", 2)[0])
"""

# RL-401: a staged compile under a __future__ feature that changes the code's flags
FUTURE = r"""
from __future__ import barry_as_FLUFL
c = compile("1 <> 2", "<test>", "eval")
print(eval(c), c.co_flags)
def f(): pass
print(hex(f.__code__.co_flags))
"""

# RL-402: a forward reference written over several lines
MULTILINE = r"""
from typing import Optional, Union
x = Optional[
    "int"
]
y = Union[
    int,
    "str",
]
print(x, y)
"""

# what the two bootstrap modules lack of CPython's names stops when read (RL-399)
STOPS = {
    "_frozen_importlib_external.marshal": "import _frozen_importlib_external as ext\next.marshal",
    "_frozen_importlib._thread": "import _frozen_importlib as boot\nprint(hasattr(boot, '_thread'))",
}


def test_sequence_slots_of_a_subclass() -> None:
    same(SEQUENCE_SLOTS)


def test_a_subclass_with_call_is_callable() -> None:
    same(CALLABLE)


def test_a_subclass_index() -> None:
    same(INDEX)


def test_the_frozen_modules() -> None:
    same(FROZEN)


def test_a_staged_compile_under_barry_as_flufl() -> None:
    same(FUTURE)


def test_a_forward_reference_over_lines() -> None:
    same(MULTILINE)


def test_what_the_bootstrap_modules_lack_stops_by_name() -> None:
    if shutil.which("g++") is None:
        return
    for name, body in STOPS.items():
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text("print('start')\n" + body + "\nprint('not reached')\n", encoding="utf-8")
            got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
        assert (got.returncode, got.stdout) == (70, "start\n") and name in got.stderr, (name, got)


def test_the_record_guard_keeps_a_prefix_with_a_space() -> None:
    """RL-400: an interpreter under a directory whose name holds a space is one forbidden path, not two words."""
    spec = importlib.util.spec_from_file_location("harness", Path(__file__).resolve().parents[2] / "conformance" / "harness.py")
    assert spec is not None and spec.loader is not None   # the conformance harness is a script, not a package
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    with tempfile.TemporaryDirectory() as tmp:
        venv = Path(tmp, "with space")
        subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True)
        paths = harness.machine_paths(str(venv / "bin" / "python"))
    assert str(venv) in paths and "space" not in paths and all(" " not in p or p.endswith("with space") for p in paths), paths


if __name__ == "__main__":
    test_sequence_slots_of_a_subclass()
    test_a_subclass_with_call_is_callable()
    test_a_subclass_index()
    test_the_frozen_modules()
    test_a_staged_compile_under_barry_as_flufl()
    test_a_forward_reference_over_lines()
    test_what_the_bootstrap_modules_lack_stops_by_name()
    test_the_record_guard_keeps_a_prefix_with_a_space()
