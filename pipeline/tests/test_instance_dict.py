"""`del obj.__dict__` compiled, against CPython on the same machine. Case C-3-58 compares which dict the object gets by the order
in which its values go; here are the words of the refusals, which the case does not print, and the one row in which a compiled
program and both evaluators differ from CPython: a method call as the first thing asked of the object, deviation D-23."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from pipeline.build import build
from pipeline.tests import test_frontend_eval1, test_l2
from pipeline.tests.test_review_2026_11_03 import same

MESSAGES = r"""
import functools


def m(g):
    try:
        return repr(g())
    except BaseException as e:
        return type(e).__name__ + ": " + str(e)


class C:
    pass


class E(Exception):
    pass


class NoDict:
    __slots__ = ("a",)


class I(int):
    pass


class T(tuple):
    pass


o = C()
o.a = 1
print(m(lambda: delattr(o, "__dict__")), m(lambda: o.a), m(lambda: delattr(o, "__dict__")), m(lambda: vars(o)))
print(m(lambda: setattr(o, "__dict__", 1)), m(lambda: setattr(o, "__dict__", None)), m(lambda: setattr(o, "__dict__", {"k": 2})), o.k)
del o.__dict__
print(m(lambda: o.k), m(lambda: delattr(o, "k")), m(lambda: o.__dict__))
print(m(lambda: delattr(E(), "__dict__")), m(lambda: delattr(NoDict(), "__dict__")), m(lambda: delattr(C, "__dict__")), m(lambda: delattr(1, "__dict__")),
      m(lambda: delattr(object(), "__dict__")))
print(m(lambda: delattr(I(), "__dict__")), m(lambda: delattr(T(), "__dict__")), m(lambda: delattr(functools.partial(print), "__dict__")), m(lambda: delattr(m, "__dict__")))
i = I(5)
i.a = 1
del i.__dict__
print(m(lambda: i.a), i + 1, m(lambda: vars(i)))
"""

# the keys of C are y, z; z is set first: "y z" is a dict that shares the keys, "z y" an ordinary one
D23 = """
log = []


class V:
    def __init__(self, n):
        self.n = n

    def __del__(self):
        log.append(self.n)


class C:
    def m(self):
        return 1


first = C()
first.y = 1
first.z = 2
o = C()
del o.__dict__
o.m()
o.z = V("z")
o.y = V("y")
del o
print(" ".join(log))
"""


def test_messages() -> None:
    same(MESSAGES)


def test_d23_a_method_call_first_is_a_plain_read() -> None:
    """Deviation D-23 (the author's decision of 2026-11-11, to reconsider): CPython's call form asks nothing of the instance
    (_PyObject_GetMethod), so after it the write still decides and the object gets the dict that shares the class's keys; the
    compiler does not tell a call's load from a plain one, so the call is the plain read that gives it an ordinary dict. When
    this test fails because the two agree, the deviation is over: remove it from the register and the specification."""
    evaluated, cpython = test_frontend_eval1.both(D23)
    assert cpython == "y z\n" and evaluated == "z y\n"
    evaluated2, cpython = test_l2.both(D23)
    assert cpython == "y z\n" and evaluated2 == "z y\n"
    if shutil.which("g++") is None:
        return
    env = dict(os.environ, PYTHONHASHSEED="0")
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp, "prog.py")
        prog.write_text(textwrap.dedent(D23), encoding="utf-8")
        ref = subprocess.run([sys.executable, str(prog)], capture_output=True, text=True, check=False, env=env, cwd=tmp)
        got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, env=env, cwd=tmp)
    assert (ref.stdout, ref.returncode) == ("y z\n", 0)
    assert (got.stdout, got.returncode) == ("z y\n", 0), got.stderr
