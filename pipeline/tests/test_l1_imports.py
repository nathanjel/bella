"""Gate 0 task 4, step A4: import statements lowered to import_name, import_from and
import_star (desugar-imports), eval1 against CPython. The modules imported here are the host's;
the C-8 cases run eval1's module system on their fixtures (make eval1-corpus).

Run under pytest or directly: python3 -m pipeline.tests.test_l1_imports
"""
from __future__ import annotations

from pipeline.l1.frontend import lower
from pipeline.tests.test_frontend_eval1 import both

FORMS = '''
import os.path
import os.path as p
import collections.abc
from collections import abc as a, OrderedDict
print(os.path is p, os.__name__, a.Mapping.__name__, OrderedDict.__name__, collections.abc is a)
def error(make):
    try:
        make()
    except ImportError as exc:
        return [type(exc).__name__, exc.name, exc.name_from]
    return "no error"
def missing_name():
    from os import nonexistent
def missing_module():
    import nonexistent_module_for_bella
print(error(missing_name), error(missing_module))
from string import *
print(ascii_letters[:3], "Template" in globals(), "_re" in globals())
class C:
    import math
    from math import pi as __pi, tau
print(C.math.__name__, C._C__pi, C.tau, "math" in vars(C))
def f():
    import sys as s
    from os import sep
    return s.maxsize > 0, sep
print(f())
'''

LAZY = '''
import sys, types
lazy import json
lazy from textwrap import dedent
# whether `lazy from` binds a proxy depends on whether the module is loaded already, which the
# two runs of one process share; the C-8 cases check it in processes of their own
print(type(globals()["json"]) is types.LazyImportType)
print(json.dumps([1]), type(globals()["json"]).__name__, dedent("  x"), type(globals()["dedent"]).__name__)
try:
    import colorsys
except ImportError:
    pass
print(type(globals()["colorsys"]).__name__)
__lazy_modules__ = ["fractions"]
import fractions
print(type(globals()["fractions"]).__name__, fractions.Fraction(1, 2), type(globals()["fractions"]).__name__)
'''

HOOKED = '''
import builtins
seen = []
real = builtins.__import__
def hook(name, globals=None, locals=None, fromlist=(), level=0):
    seen.append((name, fromlist, level, locals is None))
    return real(name, globals, locals, fromlist, level)
builtins.__import__ = hook
try:
    import os.path
    from os import sep
    def inner():
        import os
    inner()
    class K:
        import os
finally:
    builtins.__import__ = real
print(seen)
'''


def check(src: str) -> None:
    got, ref = both(src)
    assert got == ref, f"\n--- eval1\n{got}\n--- cpython\n{ref}"


def test_import_forms_and_errors() -> None:
    check(FORMS)


def test_lazy_imports_and_lazy_modules() -> None:
    check(LAZY)


def test_a_replaced_import_hook_sees_what_cpython_passes() -> None:
    check(HOOKED)


def test_lazy_import_outside_the_module_scope_is_a_syntax_error() -> None:
    for src in ("def f():\n    lazy import os\n", "class C:\n    lazy import os\n", "lazy from os import *\n",
                "def f():\n    from os import *\n"):
        try:
            lower(src, "<test>")
        except SyntaxError:
            continue
        raise AssertionError(f"{src!r} was accepted")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
