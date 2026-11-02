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


def test_every_release_point_kind() -> None:
    failures = []
    for kind, template in TEMPLATES.items():
        for in_function in (False, True):
            got, ref = both(PRELUDE + program(template, in_function))
            if got != ref:
                where = "in a function" if in_function else "at module level"
                failures.append(f"{kind} ({where}):\n--- eval2\n{got}--- cpython\n{ref}")
    assert not failures, "\n".join(failures)


def test_the_translation_holds_nothing_it_released() -> None:
    """The checking mode (docs/l2.md section 5): every release of every probe audited."""
    for template in TEMPLATES.values():
        for in_function in (False, True):
            m = l2(PRELUDE + program(template, in_function))
            with contextlib.redirect_stdout(io.StringIO()):
                ns = eval2.Interpreter(dict(vars(builtins)), audit=True).run_module(m)
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
    test_every_release_point_kind()
    print(f"ok test_every_release_point_kind ({len(TEMPLATES)} kinds, two contexts each)")
    test_the_translation_holds_nothing_it_released()
    print("ok test_the_translation_holds_nothing_it_released")
    test_the_audit_catches_a_holder_of_the_translations()
    print("ok test_the_audit_catches_a_holder_of_the_translations")
