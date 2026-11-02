"""Generated release-point probes: every kind of place CPython drops a reference, at module level
and inside a function, under CPython and under eval2 (docs/l2.md section 5, decision 2's probes).

Each template sends objects whose `__del__` prints through one kind of release point between
printed markers, so a release one statement early or late changes the output. Each runs twice:
as module code (names are `name`) and as a function's body (names are `local`).

Run under pytest or directly: python3 -m pipeline.tests.test_l2_probes
"""
from __future__ import annotations

import builtins
import contextlib
import gc
import io
import textwrap
from typing import Any

from pipeline.l2 import eval2
from pipeline.tests.test_l2 import both, l2

PRELUDE = '''
class P:
    def __init__(self, n):
        self.n = n
    def __del__(self):
        print("del", self.n)
    def __add__(self, other):
        return 0
    def __radd__(self, other):
        return 0
    def __bool__(self):
        return self.n != "false"
    def __iter__(self):
        return iter([1, 2])
    def __getitem__(self, key):
        return 0
    def __call__(self, *args, **kwargs):
        return 0
    def __enter__(self):
        print("enter", self.n)
        return self
    def __exit__(self, *exc):
        print("exit", self.n)
        return False
    def __contains__(self, item):
        return False
    def __eq__(self, other):
        return self is other
    __hash__ = object.__hash__
def p(n):
    return P(n)
'''

TEMPLATES: dict[str, str] = {
    "binary operands": 'x = p("a") + p("b")\nprint("after")',
    "call arguments": 'str(p("a")), repr(p("b"))\nprint("after")',
    "method receiver": 'p("v").__add__(1)\nprint("after")',
    "attribute owner": 'p("v").n\nprint("after")',
    "subscript": 'p("v")[p("k")]\nprint("after")',
    "store releases the old value": 'x = p("a")\nprint("mid")\nx = p("b")\nprint("after")\ndel x\nprint("end")',
    "delete": 'x = p("v")\ndel x\nprint("after")',
    "for iterator": 'for i in p("v"):\n    print("body", i)\nprint("after")',
    "for break": 'for i in p("v"):\n    break\nprint("after")',
    "for else": 'for i in []:\n    pass\nelse:\n    q = p("e")\n    print("else")\ndel q\nprint("after")',
    "with manager": 'with p("m") as m:\n    print("body")\ndel m\nprint("after")',
    "except as": 'try:\n    raise ValueError(p("v"))\nexcept ValueError as e:\n    print("handler")\nprint("after")',
    "augmented assignment": 'x = p("a")\nx += 1\nprint("after", x)',
    "unpack": 'a, b = p("a"), p("b")\ndel a\nprint("mid")\ndel b\nprint("after")',
    "starred unpack": 'a, *b = [p("a"), p("b"), p("c")]\ndel b\nprint("mid")\ndel a\nprint("after")',
    "list display": 'x = [p("a"), *[p("b")], p("c")]\nx = None\nprint("after")',
    "dict display": 'x = {"k": p("a"), **{"j": p("b")}}\nx = None\nprint("after")',
    "keyword merge": 'f = lambda **kw: 0\nf(a=p("a"), **{"b": p("b")})\nprint("after")',
    "starred call": 'f = lambda *args: 0\nf(*[p("a")], p("b"))\nprint("after")',
    "conditional expression": 'x = p("a") if p("test") else p("b")\nprint("mid")\ndel x\nprint("after")',
    "and or": 'x = p("false") or p("b")\nprint("mid")\ndel x\ny = p("t") and p("c")\ndel y\nprint("after")',
    "comparison": 'p("a") == p("b")\nprint("after")',
    "contains": '1 in p("v")\nprint("after")',
    "lambda default": 'f = lambda x=p("d"): x\nprint("mid")\ndel f\nprint("after")',
    "return value discarded": 'def r():\n    return p("v")\nr()\nprint("after")',
    "raising function's locals": 'def bad():\n    loc = p("loc")\n    raise KeyError("k")\ntry:\n    bad()\nexcept KeyError:\n    print("handler")\nprint("after")',
    "generator closed on last reference": 'def g():\n    try:\n        yield p("y")\n    finally:\n        print("gen finally")\nit = g()\nnext(it)\nprint("mid")\ndel it\nprint("after")',
    "comprehension": 'x = [i for i in [p("a"), p("b")]]\nprint("mid")\nx = None\nprint("after")',
    "walrus": 'if (w := p("w")):\n    print("body")\ndel w\nprint("after")',
    "assert": 'assert p("v")\nprint("after")',
    "class body": 'class C:\n    x = p("v").n\nprint("after", C.x)',
}


def program(template: str, in_function: bool) -> str:
    if not in_function:
        return template + "\n"
    return "def run():\n" + textwrap.indent(template, "    ") + "\nrun()\nprint(\"returned\")\n"


CASES = [(kind, in_function) for kind in TEMPLATES for in_function in (False, True)]


def pytest_generate_tests(metafunc: Any) -> None:
    """Under pytest each probe is a test of its own, so that they run on several workers."""
    if {"kind", "in_function"} <= set(metafunc.fixturenames):
        metafunc.parametrize(("kind", "in_function"), CASES,
                             ids=[f"{k}-{'function' if f else 'module'}" for k, f in CASES])


def test_release_point(kind: str, in_function: bool) -> None:
    got, ref = both(PRELUDE + program(TEMPLATES[kind], in_function))
    where = "in a function" if in_function else "at module level"
    assert got == ref, f"{kind} ({where}):\n--- eval2\n{got}--- cpython\n{ref}"


def test_the_translation_holds_nothing_it_released(kind: str, in_function: bool) -> None:
    """The checking mode (docs/l2.md section 5): every release of the probe audited."""
    m = l2(PRELUDE + program(TEMPLATES[kind], in_function))
    with contextlib.redirect_stdout(io.StringIO()):
        interp = eval2.Interpreter(dict(vars(builtins)), audit=True)
        interp.load_runtime()       # as the module system does
        ns = interp.run_module(m)
        ns.clear()
        gc.collect()


def test_the_audit_catches_a_holder_of_the_translations() -> None:
    rt = eval2._Runtime(eval2.Interpreter(), {})

    class Held:
        pass

    def generated() -> None:
        _l2_box = Held()          # noqa: N806  # a reserved local, as the translation names them
        _l2_ch = _l2_box          # noqa: N806
        rt.audit(_l2_ch)
    try:
        generated()
    except eval2.AuditError as exc:
        assert "_l2_box" in str(exc)
    else:
        raise AssertionError("the audit missed a reserved local holding a released object")


if __name__ == "__main__":
    for case in CASES:
        test_release_point(*case)
    print(f"ok test_release_point ({len(TEMPLATES)} kinds, two contexts each)")
    for case in CASES:
        test_the_translation_holds_nothing_it_released(*case)
    print("ok test_the_translation_holds_nothing_it_released")
    test_the_audit_catches_a_holder_of_the_translations()
    print("ok test_the_audit_catches_a_holder_of_the_translations")
