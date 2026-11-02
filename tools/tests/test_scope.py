"""tools/scope.py: the census classifier agrees with its own samples, and units are keyed as
CPython keys code objects.

Run under pytest or directly: python3 tools/tests/test_scope.py
"""
from __future__ import annotations

import ast
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools import scope  # noqa: E402


def test_every_sample_shows_its_own_construct() -> None:
    for name, sample in scope.SAMPLES.items():
        units = scope._unit_nodes(sample, "<sample>")
        found = set().union(*(scope._features(node) for node in units.values()))
        assert name in found, (name, sorted(found))


def test_a_def_is_a_closure_only_inside_a_function() -> None:
    source = "def f():\n    def g(): pass\nclass C:\n    def m(self): pass\n"
    assert "def: nested (closure)" not in scope._features(ast.parse(source))
    units = scope._unit_nodes(source, "<m>")
    assert "def: nested (closure)" in scope._features(units[("f", 1)])
    assert "def: nested (closure)" not in scope._features(units[("C", 3)])


def test_units_are_keyed_as_cpython_keys_code_objects() -> None:
    source = ("import functools\n"
              "@functools.cache\n"
              "\n"
              "def f():\n"
              "    def g(): pass\n"
              "class C:\n"
              "    @staticmethod\n"
              "    def m(): pass\n"
              "if True:\n"
              "    def h(): pass\n"
              "try:\n"
              "    pass\n"
              "except Exception:\n"
              "    def k(): pass\n")
    def codes(c: types.CodeType) -> set[tuple[str, int]]:
        out = {(c.co_qualname, c.co_firstlineno)}
        for k in c.co_consts:
            if isinstance(k, types.CodeType):
                out |= codes(k)
        return out
    assert set(scope._unit_nodes(source, "<m>")) == codes(compile(source, "<m>", "exec", dont_inherit=True))


def test_the_verdict_comes_from_the_frontend() -> None:
    verdict = scope.lowers_today()
    assert verdict["if"] and verdict["return"]
    assert verdict["match"] and verdict["type alias (PEP 695)"] and not verdict["except*"]   # except* not yet


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
