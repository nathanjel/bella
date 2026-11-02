"""Regression tests for the findings of the 2026-11-01 reviews (docs/reviews/review-log.md).

Each test reproduces a confirmed finding against CPython (the oracle): the frontend and eval1
must agree with CPython, and the toy C++ emitter must either agree too or refuse the program
with ``Unsupported`` -- never print something else. Run under pytest or directly:
python3 -m pipeline.tests.test_review_2026_11_01
"""
from __future__ import annotations

import ast
import contextlib
import io
import shutil
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from pipeline.l1 import frontend as fe
from pipeline.l1.eval1 import special_lookup
from pipeline.l1.grammar import DialectError, Unsupported
from pipeline.slice import run_cpp, run_cpython, run_eval1
from pipeline.tests.test_frontend_eval1 import both

_TMP = Path(tempfile.mkdtemp(prefix="bella-review-"))
_HAVE_CXX = shutil.which("g++") is not None


def _write(src: str) -> Path:
    path = _TMP / f"case{len(list(_TMP.glob('case*.py')))}.py"
    path.write_text(textwrap.dedent(src), encoding="utf-8")
    return path


def three_way(src: str) -> tuple[str, str, str]:
    """(CPython, eval1, C++) outputs; C++ is '<unsupported>' when the emitter refuses."""
    path = _write(src)
    ref = run_cpython(path)
    e1 = run_eval1(path)
    if not _HAVE_CXX:
        return ref, e1, ref
    try:
        cpp = run_cpp(path, _TMP / "out", "g++", "c++26")
    except Unsupported:
        cpp = "<unsupported>"
    return ref, e1, cpp


def agree(src: str) -> None:
    ref, e1, cpp = three_way(src)
    assert e1 == ref, f"eval1 {e1!r} != CPython {ref!r}"
    assert cpp == ref, f"C++ {cpp!r} != CPython {ref!r}"


def eval1_agrees_cpp_refuses(src: str) -> None:
    ref, e1, cpp = three_way(src)
    assert e1 == ref, f"eval1 {e1!r} != CPython {ref!r}"
    assert cpp == "<unsupported>", f"the toy emitter must refuse, not print {cpp!r} (CPython: {ref!r})"


# ---- emitter: evaluation order (astra-low-01 #1, gemini 2.2.3) ---------------------------------

def test_binary_and_comparison_operands_evaluate_left_to_right() -> None:
    agree("""
        def f(x: int) -> int:
            print(x)
            return x
        print(f(1) + f(2))
        print(f(3) < f(4))
        print(f(5) * (f(6) - f(7)) // f(8))
        y = 10
        y += f(9)
        print(y)
    """)


def test_range_arguments_evaluate_left_to_right() -> None:
    agree("""
        def f(x: int) -> int:
            print("arg", x)
            return x
        for i in range(f(1), f(3)):
            print(i)
    """)


# ---- emitter: for-range target semantics (astra-low-01 #2, gemini 2.2.4) ---------------------

def test_range_loop_target_keeps_python_meaning() -> None:
    agree("""
        i = 9
        for i in range(3):
            pass
        print(i)
        j = 9
        for j in range(0):
            pass
        print(j)
        n = 0
        for k in range(3):
            k = k + 10
            n = n + 1
        print(n, k)
    """)


# ---- emitter: invented values (astra-low-01 #3, gemini 2.2.5.5) ------------------------------

def test_global_assignment_in_function() -> None:
    agree("""
        x = 1
        def g() -> None:
            global x
            x = 5
        g()
        print(x)
    """)


def test_value_function_that_can_fall_off_the_end_is_refused() -> None:
    eval1_agrees_cpp_refuses("""
        def h(a: int) -> int:
            if a > 0:
                return 1
        print(h(0))
    """)


def test_none_valued_call_used_as_a_value_is_refused() -> None:
    eval1_agrees_cpp_refuses("""
        def g() -> None:
            print("g")
        print(g())
    """)


def test_read_of_a_possibly_unassigned_local_is_refused() -> None:
    eval1_agrees_cpp_refuses("""
        def f(c: int) -> int:
            if c > 0:
                v = 1
            return v
        print(f(1))
    """)


def test_call_before_definition_is_refused() -> None:
    src = """
        try:
            print(later(1))
        except NameError:
            print("NameError")
        def later(x: int) -> int:
            return x
    """
    ref, e1, _ = three_way(src)
    assert e1 == ref
    try:
        run_cpp(_write("print(later(1))\ndef later(x: int) -> int:\n    return x\n"), _TMP / "out", "g++", "c++26")
    except Unsupported:
        pass
    else:
        raise AssertionError("calling a function before its def must be refused, not compiled")


# ---- frontend: comprehension scope (astra-low-01 #5, gemini 2.2.2) ---------------------------

def test_comprehension_sees_enclosing_function_scope() -> None:
    out, ref = both("""
def f(x):
    return [x + i for i in range(2)]
print(f(10))
r = range(3)
print([[a + b for b in r] for a in r])
print([v for v in [w * 2 for w in r] if v])
def g(n):
    total = []
    for k in range(n):
        total.append([k * j for j in range(k)])
    return total
print(g(4))
""")
    assert out == ref


# ---- frontend/wf: chained comparisons everywhere (gemini 2.2.1) ------------------------------

def test_chained_comparison_in_every_statement_position() -> None:
    out, ref = both("""
x = 2
if 1 < x < 3:
    print("if")
while 0 < x < 3:
    x = x + 1
ok = 1 < 2 < 3
assert 1 < 2 < 3
def f(a):
    return 0 < a < 10
print(ok, f(5), f(11))
""")
    assert out == ref


def test_synthetic_names_are_not_visible_in_globals() -> None:
    out, ref = both("""
x = 2
y = 1 < x < 3
z = [i for i in range(2)]
print(sorted([k for k in globals() if k[:2] != "__"]))
""")
    assert out == ref


def test_synthetic_names_do_not_collide_with_user_names() -> None:
    out, ref = both("""
_cmp0 = "user"
_lc0 = "user"
ok = 1 < 2 < 3
v = [n for n in range(2)]
print(_cmp0, _lc0, ok, v)
""")
    assert out == ref


# ---- frontend: nested global/nonlocal (gemini 2.2.5.1) ---------------------------------------

def test_global_declared_in_a_nested_block() -> None:
    out, ref = both("""
x = 1
def g(c):
    if c:
        global x
    x = 7
g(True)
print(x)
""")
    assert out == ref


# ---- eval1: free variables and del (gemini 2.2.5.3, 2.2.5.4) ---------------------------------

def test_unbound_free_variable_raises_name_error() -> None:
    out, ref = both("""
x = "global"
def outer():
    def inner():
        return x
    try:
        print(inner())
    except NameError as e:
        print("NameError", e.name)
    x = "local"
outer()
""")
    assert out == ref


def test_del_of_unbound_local_and_of_nonlocal() -> None:
    out, ref = both("""
def f():
    try:
        del y
    except UnboundLocalError as e:
        print("UnboundLocalError", e.name)
    y = 1
f()
def outer():
    z = 1
    def inner():
        nonlocal z
        del z
    inner()
    try:
        print(z)
    except NameError as e:
        print("unbound", type(e).__name__)
outer()
g = 1
def drop():
    global g
    del g
drop()
try:
    print(g)
except NameError as e:
    print("deleted global", e.name)
""")
    assert out == ref


# ---- eval1: host-state builtins (found while reproducing gemini 2.2.1) -----------------------

def test_eval1_does_not_leak_the_host_interpreter_state() -> None:
    out, ref = both("""
a = 1
print("a" in globals(), globals()["a"], "a" in locals(), "Interpreter" in globals())
""")
    assert out == ref
    for src in ("def f():\n    return locals()\nf()\n", "eval('1')\n", "exec('x = 1')\n"):
        try:
            both(src)
        except Unsupported:
            continue
        raise AssertionError(f"eval1 must refuse {src!r}, not run it against the host")


# ---- frontend: with uses the special-method lookup (gemini 2.2.5.2) --------------------------

WITH_SOURCE = '''
log = []
class Probe:
    def __init__(self, tag):
        self.tag = tag
    def __get__(self, obj, owner=None):
        log.append("lookup " + self.tag)
        tag = self.tag
        def method(*args):
            log.append("call " + tag)
            return "probed" if tag == "enter" else False
        return method
class M:
    @staticmethod
    def __enter__():
        return "static"
    @classmethod
    def __exit__(cls, *a):
        log.append("exit " + cls.__name__)
        return False
class P:
    __enter__ = Probe("enter")
    __exit__ = Probe("exit")
with M() as v:
    log.append(v)
with P() as w:
    log.append(w)
try:
    with M():
        raise KeyError("inside")
except KeyError as exc:
    log.append("propagated " + type(exc).__name__)
try:
    with 1:
        pass
except TypeError as exc:
    log.append("TypeError")
print(log)
'''


def test_with_desugaring_binds_through_the_descriptor_protocol() -> None:
    tree = fe.desugar_with(ast.parse(WITH_SOURCE))
    ast.fix_missing_locations(tree)
    desugared, original = io.StringIO(), io.StringIO()
    # the desugaring calls intrinsics, names no source can spell; bind them to the builtins
    env: dict[str, Any] = {"__special__": special_lookup, "bella:type": type}
    with contextlib.redirect_stdout(desugared):
        exec(compile(tree, "<desugared>", "exec", dont_inherit=True), env)  # noqa: S102 -- the desugaring under test
    with contextlib.redirect_stdout(original):
        exec(WITH_SOURCE, {})  # noqa: S102 -- the oracle
    assert desugared.getvalue() == original.getvalue(), (desugared.getvalue(), original.getvalue())


# ---- dialect rules and named gaps (gemini 2.2.5.7, astra-low-02) -----------------------------

def test_d10_control_flow_leaving_finally_is_a_compile_time_error() -> None:
    programs = {
        "return 1": "def f():\n    try:\n        pass\n    finally:\n        return 1\n",
        "break": "def f():\n    while True:\n        try:\n            pass\n        finally:\n            break\n",
        "continue": "def f():\n    for i in range(2):\n        try:\n            pass\n        finally:\n            continue\n",
    }
    for body, src in programs.items():
        try:
            fe.lower(src)
        except DialectError as exc:
            assert "D-10" in str(exc)
        else:
            raise AssertionError(f"D-10 not enforced for {body!r}")
    fe.lower("def f():\n    try:\n        pass\n    finally:\n        for i in range(2):\n            break\n")


def test_new_3_15_syntax_is_refused_by_name() -> None:
    # PEP 810 lazy imports are lowered since task 4 step A4 (pipeline/tests/test_l1_imports.py)
    for src, needle in (("rows = [[1]]\nprint([*r for r in rows])\n", "PEP 798"),):
        try:
            fe.lower(src)
        except Unsupported as exc:
            assert needle in str(exc), str(exc)
        else:
            raise AssertionError(f"{needle} construct must be refused")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
