"""Unit tests for the static import scanner in tools/closure.py (no network, no pinning)."""
from __future__ import annotations

import ast
import importlib
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import tools.closure as closure  # noqa: E402
from tools.closure import (  # noqa: E402
    DEAD,
    DYNAMIC,
    EAGER,
    FIRST_USE,
    GUARDED,
    LAZY,
    OPTIONAL,
    REPLACED,
    Platform,
    _Scanner,
    scan_module,
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
    for target, cls, line, _func in s.edges:
        out[(target, cls)] = line
    return out, [line for line, _, _ in s.dynamic_unknown]


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
    assert ("statistics", LAZY) in edges             # import_module("statistics") in a function: runs when called
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


def test_pep810_lazy_imports_are_first_use_edges() -> None:
    src = (
        "import sys\n"
        "lazy import json\n"
        "lazy from collections import OrderedDict\n"
        "__lazy_modules__ = ['csv']\n"
        "import csv\n"
        "import re\n"
        "if sys.platform == 'win32':\n    lazy import winreg\n"
        "def f():\n    import heapq\n"
    )
    edges, _ = _edges(src)
    assert ("json", FIRST_USE) in edges and ("collections", FIRST_USE) in edges
    assert ("collections.OrderedDict", FIRST_USE) not in edges   # a name, not a module
    assert ("csv", FIRST_USE) in edges                # __lazy_modules__ makes a plain import lazy
    assert ("re", EAGER) in edges
    assert ("winreg", DEAD) in edges                  # a false guard still wins
    assert ("heapq", LAZY) in edges


def test_edges_record_their_function() -> None:
    src = (
        "import os\n"
        "class C:\n"
        "    def m(self):\n"
        "        import json\n"
        "        def inner():\n"
        "            import csv\n"
        "def outer():\n"
        "    class K:\n"
        "        def k(self):\n"
        "            import re\n"
        "    return __import__(os.environ['X'])\n"
    )
    s = _Scanner("m", False, LINUX)
    s.scan(ast.parse(src))
    funcs = {t: f for t, _c, _l, f in s.edges}
    assert funcs == {"os": "", "json": "C.m", "csv": "C.m.<locals>.inner", "re": "outer.<locals>.K.k"}
    assert s.dynamic_unknown == [(11, "outer", "os.environ['X']")]
    assert {"C.m", "C.m.<locals>.inner", "outer", "outer.<locals>.K.k"} <= s.functions


def test_imports_inside_replaced_functions_do_not_count() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, "m.py")
        path.write_text("def keep():\n    import json\n\ndef swap():\n    import zipfile\n    __import__(x)\n")
        scan = scan_module("m", str(path), LINUX, {"swap"})
    assert {(e.target, e.cls, e.func) for e in scan.edges} == {("json", LAZY, "keep"), ("zipfile", REPLACED, "swap")}
    assert scan.dynamic_unknown == []


BT_FILES = {
    "bt_app": "import bt_lib\nlazy import bt_later\n",
    "bt_lib": ("def load(name):\n    return __import__(name)\n\n"
               "def fancy():\n    import bt_outside\n\n"
               "def swapped():\n    import bt_heavy\n"),
    "bt_later": "", "bt_target": "", "bt_outside": "", "bt_heavy": "",
}
BT_MANIFEST = """
[reference]
python = "3.15.2"
[phase1]
roots = ["bt_app"]
compiled = ["bt_app", "bt_lib", "bt_later", "bt_target"]
[adaptations]
bt_lib = "swapped() is replaced"
[replaced]
bt_lib = ["swapped"]
[lazy_unsupported]
bt_lib = ["bt_outside"]
[dynamic.bt_lib]
"load: name" = ["bt_target"]
"""


def _closure(manifest_text: str, files: dict[str, str] = BT_FILES, observed: dict[str, list[str]] | None = None,
             ) -> tuple[dict[str, closure.ModuleInfo], list[str], dict[str, list[str]]]:
    """compute_closure on a small module tree, with the runtime observation stubbed."""
    with tempfile.TemporaryDirectory() as tmp:
        for name, src in files.items():
            Path(tmp, f"{name}.py").write_text(src)
        Path(tmp, "manifest.toml").write_text(manifest_text)
        sys.path.insert(0, tmp)
        importlib.invalidate_caches()
        saved = closure.observe_runtime_imports
        def stub(roots: list[str], blocked: object = (), search: object = ()) -> dict[str, list[str]]:
            return dict(observed or {})
        closure.observe_runtime_imports = stub
        try:
            manifest = closure.Manifest.load(Path(tmp, "manifest.toml"))
            infos, problems = closure.compute_closure(manifest)
            return infos, problems, closure.unsupported_functions(infos, manifest)
        finally:
            closure.observe_runtime_imports = saved
            sys.path.remove(tmp)
            for name in files:
                sys.modules.pop(name, None)


def test_replaced_dynamic_and_unsupported_tables() -> None:
    infos, problems, unsupported = _closure(BT_MANIFEST)
    assert problems == [], problems
    assert {"bt_later", "bt_target"} <= set(infos) and "bt_heavy" not in infos
    assert infos["bt_later"].reached_by == "bt_app:first-use:2"
    assert unsupported == {"bt_lib": ["fancy"]}       # the function refused, on every path through it


def test_manifest_tables_are_checked() -> None:
    _, problems, _ = _closure(BT_MANIFEST.replace('[dynamic.bt_lib]\n"load: name" = ["bt_target"]\n', ""))
    assert any('bt_lib:2: import with a computed name; review it and add "load: name"' in p for p in problems), problems
    _, problems, _ = _closure(BT_MANIFEST.replace('bt_lib = ["swapped"]', 'bt_lib = ["gone"]'))
    assert any("[replaced] names bt_lib.gone" in p for p in problems), problems
    _, problems, _ = _closure(BT_MANIFEST + '[omissions]\nbt_app = ["bt_lib"]\n')
    assert any("[omissions] lists bt_lib for bt_app, but the manifest provides bt_lib" in p for p in problems)
    _, problems, _ = _closure(BT_MANIFEST.replace('bt_lib = "swapped() is replaced"', ""))
    assert any("has no entry in [adaptations]" in p for p in problems), problems
    _, problems, _ = _closure(BT_MANIFEST.replace('compiled = ["bt_app"', 'mapped = ["bt_later"]\ncompiled = ["bt_app"'))
    assert any("bt_later is listed under compiled and mapped" in p for p in problems), problems


# ---- review 2026-11-01, astra-low-03 (A3) and gemini-4-argon-high-02 (G2): see the review log ----

def test_runtime_discovered_modules_are_traversed_a3_1() -> None:
    files = {"rv_root": 'loader = __import__\nloader("rv_child")\n',
             "rv_child": "def f():\n    import rv_grandchild\n", "rv_grandchild": ""}
    manifest = '[reference]\npython = "3.15.2"\n[phase1]\nroots = ["rv_root"]\ncompiled = ["rv_root", "rv_child"]\n'
    infos, problems, _ = _closure(manifest, files, {"rv_root": ["rv_child"]})
    assert infos["rv_child"].reached_by == "rv_root:runtime:0"
    assert any("rv_child:2: lazy import of rv_grandchild outside the manifest" in p for p in problems), problems


def test_a_module_missing_here_still_needs_a_decision_a3_2() -> None:
    files = {"rv_root": "def f():\n    import rv_missing_928\ntry:\n    import rv_missing_929\nexcept ImportError:\n    pass\n"}
    manifest = '[reference]\npython = "3.15.2"\n[phase1]\nroots = ["rv_root"]\ncompiled = ["rv_root"]\n'
    _, problems, _ = _closure(manifest, files)
    assert any("lazy import of rv_missing_928" in p for p in problems), problems
    assert any("optional import of rv_missing_929" in p for p in problems), problems


def test_a_handler_around_a_definition_does_not_cover_its_body_a3_3() -> None:
    src = ("try:\n    def f():\n        import rv_required\n        try:\n            import rv_opt\n"
           "        except ImportError:\n            pass\nexcept ImportError:\n    pass\n")
    edges, _ = _edges(src)
    assert ("rv_required", LAZY) in edges and ("rv_opt", OPTIONAL) in edges


def test_lazy_modules_is_read_per_import_and_in_order_a3_4() -> None:
    # each claim measured on CPython 3.15.2 (review log RL-55)
    edges, _ = _edges("__lazy_modules__ = ['fractions']\nimport fractions, json\n")
    assert ("fractions", FIRST_USE) in edges and ("json", EAGER) in edges
    edges, _ = _edges("import fractions\n__lazy_modules__ = ['fractions']\n")
    assert ("fractions", EAGER) in edges
    edges, _ = _edges("__lazy_modules__ = ['fractions']\n__lazy_modules__ = []\nimport fractions\n")
    assert ("fractions", EAGER) in edges
    edges, _ = _edges("__lazy_modules__ = ['xml']\nimport xml.dom\n__lazy_modules__ = ['csv']\nfrom csv import reader\n")
    assert ("xml", EAGER) in edges and ("csv", FIRST_USE) in edges   # the full dotted name is what matches
    edges, _ = _edges("__lazy_modules__ = ['fractions']\ntry:\n    import fractions\nexcept ImportError:\n    pass\n"
                      "class C:\n    import json\nif True:\n    import fractions as f2\n")
    assert ("fractions", OPTIONAL) in edges and ("json", EAGER) in edges and ("fractions", FIRST_USE) in edges
    s = _Scanner("m", False, LINUX)
    s.scan(ast.parse("__lazy_modules__ = ['a']\n__lazy_modules__.append('json')\nimport json\n"))
    assert s.lazy_policy_unknown == [3]          # mutation: the closure says it cannot tell


def test_each_computed_import_site_is_reviewed_a3_5() -> None:
    files = dict(BT_FILES, bt_lib=BT_FILES["bt_lib"] + "\ndef again(other):\n    return __import__(other)\n")
    _, problems, _ = _closure(BT_MANIFEST, files)
    assert any('"again: other"' in p for p in problems), problems
    _, problems, _ = _closure(BT_MANIFEST.replace('"load: name"', '"load: gone"'))
    assert any('reviews "load: gone", which is not a site in bt_lib' in p for p in problems), problems


def test_every_edge_is_accounted_for_whatever_reached_its_target_first_g2_3_1() -> None:
    files = {"rv_a": "import rv_outside\nimport rv_b\n", "rv_b": "def f():\n    import rv_outside\n", "rv_outside": ""}
    manifest = ('[reference]\npython = "3.15.2"\n[phase1]\nroots = ["rv_a"]\ncompiled = ["rv_a", "rv_b"]\n'
                '[lazy_unsupported]\nrv_b = ["rv_outside"]\n')
    _, problems, unsupported = _closure(manifest, files)
    assert not any("does not import inside a function" in p for p in problems), problems
    assert unsupported == {"rv_b": ["f"]}


def test_a_star_import_from_a_builtin_binds_only_its_exports_g2_3_2() -> None:
    src = ("import sys\n_names = sys.builtin_module_names\nif 'posix' in _names:\n    name = 'posix'\n"
           "    from posix import *\nif name == 'nt':\n    def add_dll_directory(path):\n        import nt\n")
    edges, _ = _edges(src)
    assert ("nt", DEAD) in edges                  # os.py: posix does not export `name`


def test_dotted_dynamic_targets_import_their_parents_g2_3_4() -> None:
    edges, _ = _edges("import importlib\nimportlib.import_module('xml.dom.minidom')\n")
    assert {("xml", DYNAMIC), ("xml.dom", DYNAMIC), ("xml.dom.minidom", DYNAMIC)} <= set(edges)


def test_a_nested_helper_refuses_the_function_a_program_names_g2_3_4() -> None:
    files = {"rv_n": "def f():\n    def _inner():\n        import rv_far\n    return _inner\n", "rv_far": ""}
    manifest = ('[reference]\npython = "3.15.2"\n[phase1]\nroots = ["rv_n"]\ncompiled = ["rv_n"]\n'
                '[lazy_unsupported]\nrv_n = ["rv_far"]\n')
    _, problems, unsupported = _closure(manifest, files)
    assert problems == [] and unsupported == {"rv_n": ["f"]}, (problems, unsupported)



def test_type_checking_blocks_are_dead() -> None:
    src = ("import typing as t\nif t.TYPE_CHECKING:\n    import rv_only_for_checkers\n"
           "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    import rv_also_for_checkers\n"
           "if not TYPE_CHECKING:\n    import rv_at_runtime\n")
    edges, _ = _edges(src)
    assert ("rv_only_for_checkers", DEAD) in edges and ("rv_also_for_checkers", DEAD) in edges
    assert ("rv_at_runtime", EAGER) in edges


def test_a_bare_import_module_call_is_a_computed_import() -> None:
    src = "from importlib import import_module\ndef load(name):\n    return import_module(name)\nimport_module('csv')\n"
    s = _Scanner("m", False, LINUX)
    s.scan(ast.parse(src))
    assert s.dynamic_unknown == [(3, "load", "name")]
    assert ("csv", DYNAMIC, 4, "") in s.edges


def test_a_target_programs_closure() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        drivers, vendor = Path(tmp, "drivers"), Path(tmp, "vendor", "rv_lib")
        drivers.mkdir()
        vendor.mkdir(parents=True)
        Path(drivers, "rv_prog.py").write_text("import rv_lib\nimport json\n")
        Path(vendor, "__init__.py").write_text("def f():\n    import rv_lib.sub\n\ndef g():\n    import csv\n")
        Path(vendor, "sub.py").write_text("")
        Path(tmp, "m.toml").write_text('[reference]\npython = "3.15.2"\n[phase1]\nroots = []\ncompiled = ["json"]\n'
                                       'core = ["_json"]\n')
        manifest = closure.Manifest.load(Path(tmp, "m.toml"))
        dirs = (drivers, Path(tmp, "vendor"))
        saved = closure.observe_program_run
        def no_run(program: closure.Program, blocked: list[str] | tuple[str, ...] = ()) -> list[str]:
            return []
        closure.observe_program_run = no_run
        try:
            program = closure.Program("rv", "easy", "rv_prog", dirs)
            infos, problems = closure.compute_closure(manifest, program)
            assert infos["rv_prog"].status == infos["rv_lib"].status == infos["rv_lib.sub"].status == closure.PROGRAM
            assert [p for p in problems if "rv_lib.sub" in p] == []        # the program's own module is supported
            assert any("lazy import of csv outside the manifest" in p for p in problems), problems
            declared = closure.Program("rv", "easy", "rv_prog", dirs, {"lazy_unsupported": {"rv_lib": ["csv"]}})
            infos, problems = closure.compute_closure(manifest, declared)
            assert not any("csv" in p for p in problems), problems
            assert closure.unsupported_functions(infos, declared.manifest_for(manifest)) == {"rv_lib": ["g"]}
        finally:
            closure.observe_program_run = saved


def _program_closure(files: dict[str, str], vendor: dict[str, str], manifest_text: str, **program: object,
                     ) -> tuple[dict[str, closure.ModuleInfo], list[str]]:
    """compute_closure for a small target program, the run observation stubbed."""
    with tempfile.TemporaryDirectory() as tmp:
        drivers, vendor_dir = Path(tmp, "drivers"), Path(tmp, "vendor")
        drivers.mkdir()
        vendor_dir.mkdir()
        for name, src in files.items():
            Path(drivers, f"{name}.py").write_text(src)
        for rel, src in vendor.items():
            Path(vendor_dir, rel).parent.mkdir(parents=True, exist_ok=True)
            Path(vendor_dir, rel).write_text(src)
        Path(tmp, "m.toml").write_text('[reference]\npython = "3.15.2"\n' + manifest_text)
        manifest = closure.Manifest.load(Path(tmp, "m.toml"))
        owned = tuple(Path(tmp, str(o)) for o in program.pop("owned", ()))  # type: ignore[attr-defined]
        tables = program.pop("tables", {})
        saved = closure.observe_program_run
        def no_run(program: closure.Program, blocked: list[str] | tuple[str, ...] = ()) -> list[str]:
            return []
        closure.observe_program_run = no_run
        try:
            prog = closure.Program("rv", "easy", "rv_main", (drivers, vendor_dir), tables, owned)  # type: ignore[arg-type]
            return closure.compute_closure(manifest, prog)
        finally:
            closure.observe_program_run = saved
            for mod in [m for m in sys.modules if m.startswith("rv_")]:
                del sys.modules[mod]


def test_the_entry_script_runs_as_main_a4_1() -> None:
    infos, problems = _program_closure(
        {"rv_main": 'import rv_mod\nif __name__ == "__main__":\n    import rv_needed\n'},
        {"rv_mod.py": 'if __name__ == "__main__":\n    import rv_never\n', "rv_needed.py": "", "rv_never.py": ""},
        '[phase1]\nroots = []\n')
    assert problems == [], problems
    assert infos["rv_needed"].status == closure.PROGRAM            # required: the script is __main__
    assert ("rv_never", DEAD) in {(e.target, e.cls) for e in infos["rv_mod"].edges}   # an imported module is not


def test_per_target_declarations_merge_and_must_name_reached_modules_g3_3_1() -> None:
    base = closure.Manifest.load(Path(__file__).resolve().parents[2] / "manifest.toml")
    prog = closure.Program("rv", "easy", "rv_main", (), {"lazy_unsupported": {"shutil": ["rv_extra"]}})
    merged = prog.manifest_for(base)
    assert merged.lazy_unsupported["shutil"] == base.lazy_unsupported["shutil"] | {"rv_extra"}
    _, problems = _program_closure({"rv_main": "import json\n"}, {}, '[phase1]\nroots = []\ncompiled = ["json"]\n',
                                   tables={"dynamic": {"rv_typo": {"f: x": []}}})
    assert any("[rv.closure.dynamic] has an entry for rv_typo, which the closure does not reach" in p for p in problems)


def test_only_declared_packages_belong_to_the_program_g3_3_2() -> None:
    infos, problems = _program_closure(
        {"rv_main": "import rv_declared\nimport rv_undeclared\n"},
        {"rv_declared/__init__.py": "", "rv_undeclared.py": ""}, '[phase1]\nroots = []\n',
        owned=["drivers/rv_main.py", "vendor/rv_declared"])
    assert infos["rv_declared"].status == closure.PROGRAM
    assert any(p.startswith("rv_undeclared [source]: required but not in manifest") for p in problems), problems


def test_phase1_is_staged_by_target_d10() -> None:
    """Each phase-1 stage counts only what the stages before it do not reach; a target after
    phase 1 (D-7) adds nothing to 1a and is reported apart (review log D-10)."""
    manifest = closure.Manifest.load(Path(__file__).resolve().parents[2] / "manifest.toml")
    def prog(name: str, stage: str) -> closure.Program:
        return closure.Program(name, "easy" if stage != "later" else "tricky", name, (Path("."),), stage=stage)
    def infos(*names: str) -> dict[str, closure.ModuleInfo]:
        return {n: closure.ModuleInfo(n, "source", None, "compiled") for n in names} | {
            "drv": closure.ModuleInfo("drv", "source", None, closure.PROGRAM)}
    results = {"second": (prog("second", "1a.2"), infos("re", "json", "base64")),
               "first": (prog("first", "1a.1"), infos("re", "enum")),
               "after": (prog("after", "later"), infos("re", "html"))}
    incs = closure.increments(results, manifest)
    assert list(incs) == ["1a.1", "1a.2", "1a", "1c", "later"]
    assert list(incs["1a.1"]["list"]) == ["enum", "re"]            # type: ignore[call-overload]
    assert list(incs["1a.2"]["list"]) == ["base64", "json"]        # type: ignore[call-overload]
    assert incs["1a"]["modules"] == 4 and incs["later"]["targets"] == ["after"]
    assert list(incs["later"]["list"]) == ["html"]                  # type: ignore[call-overload]
    assert "html" in incs["1c"]["list"] and "re" not in incs["1c"]["list"]   # type: ignore[operator]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
