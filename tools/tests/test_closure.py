"""Unit tests for the static import scanner in tools/closure.py (no network, no pinning)."""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.closure import (  # noqa: E402
    DEAD,
    DYNAMIC,
    EAGER,
    GUARDED,
    LAZY,
    OPTIONAL,
    Platform,
    _Scanner,
)

LINUX = Platform({"sys.platform": "linux", "os.name": "posix"}, frozenset({"posix"}), frozenset({"nt"}))

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


def _edges(src: str, module: str = "pkg.mod", is_package: bool = False,
           platform: Platform = LINUX) -> tuple[dict[tuple[str, str], int], list[int]]:
    s = _Scanner(module, is_package, platform)
    s.scan(ast.parse(src))
    out: dict[tuple[str, str], int] = {}
    for target, cls, line in s.edges:
        out[(target, cls)] = line
    return out, s.dynamic_unknown


def test_eager_lazy_optional_classes() -> None:
    edges, unknown = _edges(SAMPLE)
    assert ("os", EAGER) in edges
    assert ("json", EAGER) in edges and ("json.decoder", EAGER) in edges
    assert ("collections", EAGER) in edges
    assert ("heapq", LAZY) in edges
    assert ("bisect", LAZY) in edges                 # inside a function, under an `if`: lazy (D-3)
    assert ("_decimal", OPTIONAL) in edges           # try/except ImportError
    assert ("_pydecimal", GUARDED) in edges          # a handler runs only on failure: required, not optional
    assert ("lzma", OPTIONAL) in edges               # with suppress(ImportError)
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


PLATFORM_GUARDS = '''
import sys
import os as _os
_names = sys.builtin_module_names
_WINDOWS = _os.name == "nt"
_false = 0

if 'posix' in _names:
    import posix_branch
elif 'nt' in _names:
    import nt_branch
del _names

if sys.platform == "win32":
    import win_only
else:
    import not_win
if _WINDOWS:
    import win_alias
if _false:
    import never
if sys.platform.startswith("linux") and not _WINDOWS:
    import linux_only
if __name__ == "__main__":
    import doctest
if sys.platform == "win32" or unknown_flag:
    import maybe
while _false:
    import loop_body

def f():
    if sys.platform == "win32":
        import win_in_function
    if 'nt' in _names:                  # _names was deleted at module level: not evaluable here
        import after_del
    if unknown_flag:
        import plain_lazy

def g(sys):
    if sys.platform == "win32":         # a parameter shadows the module: not the platform
        import shadowed
'''


def test_guards_the_closed_world_can_evaluate_d3() -> None:
    edges, _ = _edges(PLATFORM_GUARDS)
    assert ("posix_branch", EAGER) in edges          # 'posix' in sys.builtin_module_names, through an alias
    assert ("nt_branch", DEAD) in edges
    assert ("win_only", DEAD) in edges and ("not_win", EAGER) in edges
    assert ("win_alias", DEAD) in edges              # _WINDOWS = os.name == "nt"
    assert ("never", DEAD) in edges                  # a module-level constant
    assert ("linux_only", EAGER) in edges            # str.startswith, `and`, `not`
    assert ("doctest", DEAD) in edges                # a library module is never __main__
    assert ("maybe", GUARDED) in edges               # one operand unknown, the other false: unknown
    assert ("loop_body", DEAD) in edges
    assert ("win_in_function", DEAD) in edges        # dead inside a function too
    assert ("after_del", LAZY) in edges              # module-level `del` ends what functions may assume
    assert ("plain_lazy", LAZY) in edges
    assert ("shadowed", LAZY) in edges


def test_without_platform_facts_nothing_is_dead() -> None:
    edges, _ = _edges(PLATFORM_GUARDS, platform=Platform())
    assert ("win_only", GUARDED) in edges and ("not_win", GUARDED) in edges
    assert ("nt_branch", GUARDED) in edges
    assert ("never", DEAD) in edges and ("doctest", DEAD) in edges   # constants and __name__ need no facts


def test_names_a_module_may_rebind_are_not_assumed() -> None:
    src = (
        "import sys\n"
        "plat = sys.platform\n"
        "_priv = sys.platform\n"
        "from somewhere import *\n"             # may rebind any public name
        "if plat == 'win32':\n    import public_after_star\n"
        "if _priv == 'win32':\n    import private_after_star\n"
        "twice = 'win32'\n"
        "twice = 'linux'\n"
        "glob = 'win32'\n"
        "def set_it():\n    global glob\n    glob = 'linux'\n"
        "def h():\n"
        "    if twice == 'win32':\n        import bound_twice\n"
        "    if glob == 'win32':\n        import declared_global\n"
    )
    edges, _ = _edges(src)
    assert ("public_after_star", GUARDED) in edges
    assert ("private_after_star", DEAD) in edges     # a star import never binds an underscore name
    assert ("bound_twice", LAZY) in edges            # functions cannot know which binding they see
    assert ("declared_global", LAZY) in edges


def test_optional_wins_over_lazy_and_dead_wins_over_all() -> None:
    src = (
        "import sys\n"
        "def f():\n"
        "    try:\n        import opt_in_function\n    except ImportError:\n        pass\n"
        "if sys.platform == 'win32':\n"
        "    try:\n        import dead_optional\n    except ImportError:\n        pass\n"
    )
    edges, _ = _edges(src)
    assert ("opt_in_function", OPTIONAL) in edges
    assert ("dead_optional", DEAD) in edges


def test_platform_facts_are_checked_against_the_running_interpreter() -> None:
    assert Platform({"sys.platform": sys.platform, "os.name": os.name}).mismatches() == []
    wrong = Platform({"sys.platform": "not-" + sys.platform}, frozenset({"no_such_builtin"}), frozenset({"sys"}))
    problems = wrong.mismatches()
    assert len(problems) == 3, problems


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
