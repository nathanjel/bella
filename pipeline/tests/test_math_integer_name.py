"""`_math_integer`, the name under which CPython 3.15 has the module that `math.integer` is.

The module's own name is `math.integer` and its spec's is `_math_integer`: it is a built-in module of that name, which
`math` imports when it is made and then puts into `sys.modules` under `math.integer` as well, the same object. The
runtime had the module under `math.integer` alone, so `import _math_integer` stopped (the sweep of the manifest's modules,
2026-11-22) and `sys.modules` lacked the name after `import math`. One program a row, since what a row imports first is
what it is about.

Run under pytest or directly: python3 -m pipeline.tests.test_math_integer_name
"""
from __future__ import annotations

from typing import Any

from pipeline.tests.test_review_2026_11_19 import same

HEAD = '''
import sys
def names() -> list[str]:
    return sorted(k for k in sys.modules if "math" in k)
'''

ROWS = {
    "alone": '''
import _math_integer
print(_math_integer.__name__, _math_integer.__spec__.name, _math_integer.__spec__.origin, _math_integer.__spec__.loader.__name__, names())
print(repr(_math_integer.__package__), _math_integer.__loader__.__name__, getattr(_math_integer, "__file__", None), _math_integer.gcd(12, 18))
import math
print(names(), math.integer is _math_integer, sys.modules["math.integer"] is _math_integer)
''',
    "after_math": '''
import math
print(names())
import _math_integer
print(names(), math.integer is _math_integer, sys.modules["math.integer"] is sys.modules["_math_integer"], _math_integer.__name__)
''',
    "dotted": '''
import math.integer
print(names(), math.integer.__name__, math.integer.__spec__.name, sys.modules["_math_integer"] is math.integer)
''',
    "from": '''
from _math_integer import gcd, isqrt
print(gcd(4, 6), isqrt(17), names())
from math.integer import lcm
print(lcm(4, 6), names())
''',
    "public": '''
import _math_integer as m
print(sorted(dir(m)), type(m).__name__, repr(m), "_math_integer" in sys.builtin_module_names, "math.integer" in sys.builtin_module_names)
try:
    m.absent
except AttributeError as error:
    print(type(error).__name__, error.name)
''',
    "deleted": '''
import math
del sys.modules["math.integer"]
import _math_integer
print(names(), _math_integer is math.integer)
''',
}


def pytest_generate_tests(metafunc: Any) -> None:
    if "row" in metafunc.fixturenames:
        metafunc.parametrize("row", sorted(ROWS))


def test_rows(row: str) -> None:
    same(HEAD + ROWS[row])


if __name__ == "__main__":
    for name in sorted(ROWS):
        same(HEAD + ROWS[name])
    print("ok")
