"""Unit tests for the static import scanner in tools/closure.py (no network, no pinning)."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.closure import CONDITIONAL, DYNAMIC, EAGER, LAZY, _Scanner  # noqa: E402

SAMPLE = '''
import os, json.decoder
from collections import abc as cabc
from . import sibling
from .sub import leaf

def f():
    import heapq
    if x:
        import bisect

try:
    import _decimal
except ImportError:
    from _pydecimal import *

import contextlib
with contextlib.suppress(ImportError):
    import lzma

def g(name):
    importlib.import_module("statistics")
    __import__(name)
'''


def _edges(src: str, module: str = "pkg.mod", is_package: bool = False) -> tuple[dict[tuple[str, str], int], list[int]]:
    s = _Scanner(module, is_package)
    s.scan(ast.parse(src))
    out: dict[tuple[str, str], int] = {}
    for target, cls, line in s.edges:
        out[(target, cls)] = line
    return out, s.dynamic_unknown


def test_eager_lazy_conditional_classes() -> None:
    edges, unknown = _edges(SAMPLE)
    assert ("os", EAGER) in edges
    assert ("json", EAGER) in edges and ("json.decoder", EAGER) in edges
    assert ("collections", EAGER) in edges
    assert ("heapq", LAZY) in edges
    assert ("bisect", CONDITIONAL) in edges          # inside a function AND under if: conditional wins
    assert ("_decimal", CONDITIONAL) in edges        # try/except ImportError
    assert ("_pydecimal", CONDITIONAL) in edges      # the handler body is conditional too
    assert ("lzma", CONDITIONAL) in edges            # with suppress(ImportError)
    assert ("statistics", DYNAMIC) in edges          # importlib.import_module("statistics") in a function
    assert unknown == [SAMPLE.splitlines().index("    __import__(name)") + 1]  # computed name: reported by line


def test_relative_imports_resolve_against_package() -> None:
    edges, _ = _edges(SAMPLE, module="pkg.mod", is_package=False)
    assert ("pkg", EAGER) in edges                   # from . import sibling
    assert ("pkg.sub", EAGER) in edges               # from .sub import leaf
    edges_pkg, _ = _edges("from . import x\n", module="pkg", is_package=True)
    assert ("pkg", EAGER) in edges_pkg


def test_definition_time_expressions_are_eager() -> None:
    src = "def f(x=__import__('json')):\n    pass\n"
    edges, _ = _edges(src)
    assert ("json", DYNAMIC) in edges                # a default is evaluated at definition time


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
