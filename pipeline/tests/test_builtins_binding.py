"""E-06 (the author's decision of 2026-11-25, Question 46; review log RL-946): rebinding a module's `__builtins__` is excluded,
and its direct forms are refused at compile time with the exclusion's id.

CPython's function takes its builtins from its globals' `__builtins__` when it is made (`_PyDict_LoadBuiltinsFromGlobals`),
so after `__builtins__ = {"len": f}` the functions, lambdas and class bodies made later look `len` up there; the runtime's
never do. The rows: each way a module binds the name is refused (`check_builtins_binding`), and the command says so with
status 70; what does not bind it (a read, a deletion, an annotation alone, a function's local or parameter, a class body's
attribute, a comprehension's own variable) is compiled and agrees with CPython.

Run under pytest or directly: python3 -m pipeline.tests.test_builtins_binding
"""
from __future__ import annotations

import ast
import shutil
import sys
import tempfile
from pathlib import Path

from pipeline.l1 import grammar as L
from pipeline.l1.frontend import check_builtins_binding
from pipeline.tests.test_review_2026_11_03 import same
from pipeline.tests.test_review_2026_11_21_a26 import BUILDER, _command

REFUSED = {
    "assign": "__builtins__ = {}\n",
    "annotated": "__builtins__: dict = {}\n",
    "augmented": "__builtins__ += 1\n",
    "tuple": "a, __builtins__ = 1, 2\n",
    "for": "for __builtins__ in [1]:\n    pass\n",
    "with": "import contextlib\nwith contextlib.nullcontext() as __builtins__:\n    pass\n",
    "except": "try:\n    pass\nexcept ValueError as __builtins__:\n    pass\n",
    "import": "import builtins as __builtins__\n",
    "fromimport": "from os import __builtins__\n",
    "def": "def __builtins__():\n    pass\n",
    "class": "class __builtins__:\n    pass\n",
    "global": "def f():\n    global __builtins__\n    __builtins__ = {}\n",
    "walrus": "if (__builtins__ := {}):\n    pass\n",
    "walrus in a comprehension": "[(__builtins__ := i) for i in range(1)]\n",
    "match": "match 1:\n    case __builtins__:\n        pass\n",
    "type": "type __builtins__ = int\n",
}

ALLOWED = """\
import builtins
import types


def local() -> int:
    __builtins__ = 1
    return __builtins__


def parameter(__builtins__: int) -> int:
    return __builtins__


class Body:
    __builtins__ = 2


lam = lambda: (__builtins__ := 3)  # noqa: E731
seen = [__builtins__ for __builtins__ in range(4, 5)]
__builtins__: dict
print("read", type(__builtins__).__name__, __builtins__ is builtins)
print("local", local(), "parameter", parameter(5), "class body", Body.__builtins__, "lambda", lam(), "comprehension", seen)
m = types.ModuleType("m")
m.x = 6
print("module attribute", m.x, len([1, 2]))
del __builtins__


def after() -> int:
    return len([1, 2, 3])


print("deleted", after(), after.__builtins__ is vars(builtins))
"""


def test_each_binding_is_refused() -> None:
    wrong = []
    for name, source in REFUSED.items():
        try:
            check_builtins_binding(ast.parse(source))
            wrong.append(f"{name}: not refused")
        except L.DialectError as exc:
            if not str(exc).startswith("E-06: "):
                wrong.append(f"{name}: {exc}")
    assert not wrong, wrong


def test_what_does_not_bind_it_is_compiled() -> None:
    check_builtins_binding(ast.parse(ALLOWED))
    same(ALLOWED)


def test_the_command_refuses_it() -> None:
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        tmp = str(Path(tmp).resolve())
        Path(tmp, "prog.py").write_text('__builtins__ = {"len": lambda x: 42}\n\n\ndef f() -> int:\n    return len([])\n\n\nprint(f())\n',
                                        encoding="utf-8")
        reference = _command([sys.executable, "prog.py"], tmp)
        assert (reference.returncode, reference.stdout) == (0, b"42\n"), reference
        ran = _command([*BUILDER, "--run", "prog.py"], tmp)
        refusal = "bella: refused: E-06: assigning to `__builtins__` (rebinding a module's builtins is excluded) (line 1)"
        assert (ran.returncode, ran.stdout, ran.stderr.decode().splitlines()) == (70, b"", [refusal]), ran


if __name__ == "__main__":
    test_each_binding_is_refused()
    test_what_does_not_bind_it_is_compiled()
    test_the_command_refuses_it()
    print("ok")
