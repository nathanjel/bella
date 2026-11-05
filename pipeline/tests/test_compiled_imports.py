"""Compiled imports against CPython (step 3b; case C-8-10, and C-8-01 and C-8-04 compiled).

Programs of several modules are written to a directory, run by CPython as `python main.py` and
compiled by pipeline/build.py with the modules the build finds (pipeline/closed_world.py); their
stdout and exit status must agree, and their stderr too where a test says so (masked as the
harness masks it: D-06 keeps a traceback's file names and lines). Covered: what the import system
puts in a module's namespace and in sys.modules, the messages of a partially initialised module,
of a missing name and of a shadowing one, the module type's own methods, __import__'s arguments,
ImportError's fields, globals() in a frame of each module, a module run again after its body
failed, the order modules' globals are released at exit, and a traceback through a module body.
Also the str methods the import system brought in (runtime/src/str.cpp), over many inputs, and a
class's slot descriptors in sorted order (found on the way).

Run under pytest or directly: python3 -m pipeline.tests.test_compiled_imports
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from conformance.harness import mask_stderr
from pipeline.build import build
from pipeline.closed_world import STDLIB, find_program_modules


def same(files: dict[str, str], stderr: bool = False, sort_stdout: bool = False, status: int | None = None) -> None:
    """main.py and its modules under CPython and compiled: stdout and status (and stderr) agree."""
    if shutil.which("g++") is None:
        return
    env = dict(os.environ, PYTHONHASHSEED="0")
    with tempfile.TemporaryDirectory() as tmp:
        for name, text in files.items():
            path = Path(tmp, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(text), encoding="utf-8")
        main = Path(tmp, "main.py")
        ref = subprocess.run([sys.executable, "main.py"], capture_output=True, text=True, check=False, env=env, cwd=tmp)
        got = subprocess.run([str(build(main, str(main)))], capture_output=True, text=True, check=False, env=env, cwd=tmp)
    if status is not None:
        assert ref.returncode == status, ref
    arrange = (lambda text: sorted(text.splitlines())) if sort_stdout else (lambda text: text)
    want = (arrange(ref.stdout), ref.returncode, mask_stderr(ref.stderr) if stderr else "")
    have = (arrange(got.stdout), got.returncode, mask_stderr(got.stderr) if stderr else "")
    assert have == want, (f"\n--- compiled (exit {got.returncode})\n{got.stdout}{got.stderr}\n"
                          f"--- CPython (exit {ref.returncode})\n{ref.stdout}{ref.stderr}")


PROBE = """
class Probe:
    def __init__(self, name):
        self.name = name
    def __del__(self):
        print("dies", self.name)
"""


def test_globals_are_released_at_exit_in_sys_modules_order() -> None:
    """Measured on 3.15.2: __main__'s namespace first, then each module's, in the order the modules
    finished loading, each in insertion order (finalize_remove_modules; D-07)."""
    same({"probe.py": PROBE,
          "ma.py": "from probe import Probe\n_a_private = Probe('ma._a_private')\na_public = Probe('ma.a_public')\n",
          "mb.py": "from probe import Probe\nimport ma\nb_public = Probe('mb.b_public')\n_b_private = Probe('mb._b_private')\n",
          "main.py": "import mb\nfrom probe import Probe\nm1 = Probe('main.m1')\n_m2 = Probe('main._m2')\nprint('end')\n"})


def test_every_way_out_of_the_program_releases_the_modules_globals() -> None:
    """sys.exit and an uncaught exception release what a normal end does (spec section 9); the order
    between modules on those paths is D-07's, so the deaths are compared sorted."""
    for how, status in (("sys.exit(3)", 3), ("raise ValueError('boom')", 1), ("sys.exit('words')", 1), ("sys.exit()", 0),
                        ("sys.exit(None)", 0), ("sys.exit((1, 2))", 1), ("sys.exit(True)", 1), ("sys.exit(2**40)", 0), ("sys.exit(2**40 + 7)", 7),
                        ("raise SystemExit(4)", 4), ("raise SystemExit", 0)):
        same({"probe.py": PROBE, "m.py": "from probe import Probe\nmod_obj = Probe('m.mod_obj')\n",
              "main.py": f"""\
                  import sys
                  import m
                  from probe import Probe
                  g = Probe('main.g')
                  def f():
                      local = Probe('f.local')
                      {how}
                  f()
                  """}, sort_stdout=True, status=status)


def test_a_traceback_through_a_module_body() -> None:
    same({"bad.py": "x = 1\ndef f():\n    raise ValueError('in f')\nf()\n",
          "main.py": "print('start')\nimport bad\n"}, stderr=True)


def test_circular_imports_and_their_messages() -> None:
    """The wording of each partial-initialisation message, with origins shown by name only."""
    same({"pkg/__init__.py": "",
          "pkg/a.py": "import pkg.b\nX = 1\n",
          "pkg/b.py": """\
              import sys
              import pkg.a as a
              def show(e):
                  print(type(e).__name__, str(e).replace(sys.path[0], '<dir>'), e.name)
              try:
                  a.X
              except AttributeError as e:
                  show(e)
              try:
                  from pkg.a import X
              except ImportError as e:
                  show(e)
                  print(e.name_from, e.path.replace(sys.path[0], '<dir>'))
              import pkg
              try:
                  pkg.a
              except AttributeError as e:
                  show(e)
              """,
          "top.py": """\
              import sys
              import main_helper
              """,
          "main_helper.py": """\
              import sys
              import top
              try:
                  top.anything
              except AttributeError as e:
                  print(str(e).replace(sys.path[0], '<dir>'))
              try:
                  from top import anything
              except ImportError as e:
                  print(str(e).replace(sys.path[0], '<dir>'))
              """,
          "main.py": "import pkg.a\nprint(pkg.a.X)\nimport top\n"})


def test_the_module_type() -> None:
    same({"m.py": "VALUE = 1\ndef __getattr__(name):\n    if name == 'lazy':\n        return 'served'\n    raise AttributeError(name)\n",
          "main.py": """\
              import sys
              import m
              M = type(sys)
              made = M('made')
              print(repr(made), list(vars(made)), made.__doc__, M('x', 'doc').__doc__)
              made.attr = 1
              print(made.attr, made.__dict__ is vars(made), dir(made))
              del made.attr
              for f in (lambda: made.attr, lambda: delattr(made, 'attr')):
                  try:
                      f()
                  except AttributeError as e:
                      print(type(e).__name__, e, e.name)
              del made.__name__
              print(repr(made))
              try:
                  made.zz
              except AttributeError as e:
                  print(e)
              made.__file__ = '/somewhere/made.py'
              print(repr(made))
              from m import lazy
              print(lazy, m.lazy, getattr(m, 'nothing', 'default'))
              try:
                  m.nothing
              except AttributeError as e:
                  print('hook:', e.args, e.name, e.obj is m)
              print(isinstance(m, M), type(m).__name__, M.__name__)
              """})


def test_import_arguments_and_errors() -> None:
    same({"pkg/__init__.py": "", "pkg/sub.py": "S = 1\n",
          "main.py": """\
              for f in (lambda: __import__(), lambda: __import__(1), lambda: __import__('pkg', level=-1),
                        lambda: __import__(''), lambda: __import__('x', None, None, [], 1),
                        lambda: __import__('pkg', fromlist=[1]), lambda: __import__('pkg', bad=1),
                        lambda: __import__('pkg', {}, None, ['sub'], 1), lambda: __import__('pkg', level='x'),
                        lambda: __import__('pkg', {'__package__': 3}, None, [], 1),
                        lambda: __import__('pkg', {'__package__': ''}, None, [], 1)):
                  try:
                      print(f())
                  except (TypeError, ValueError, ImportError, KeyError) as e:
                      print(type(e).__name__, e)
              print(__import__('pkg', fromlist=['sub']).sub.S, __import__('pkg.sub').__name__,
                    __import__('sub', {'__package__': 'pkg', '__name__': 'pkg'}, None, ['S'], 1).S,
                    __import__('pkg', fromlist=['absent', 'sub']).__name__)
              """})


def test_relative_import_statements_and_their_errors() -> None:
    same({"pkg/__init__.py": "", "pkg/sub/__init__.py": "", "pkg/plain.py": "X = 1\n",
          "pkg/sub/deep.py": """\
              from ..plain import X
              from .. import plain
              from . import __name__ as here
              print(X, plain.X, here)
              try:
                  from ... import nothing
              except ImportError as e:
                  print(type(e).__name__, e, e.name)
              try:
                  from ...beyond import nothing
              except ImportError as e:
                  print(type(e).__name__, e, e.name)
              """,
          "main.py": """\
              import pkg.sub.deep
              try:
                  from . import x
              except ImportError as e:
                  print(type(e).__name__, e, e.name)
              try:
                  from .y import x
              except ImportError as e:
                  print(type(e).__name__, e, e.name)
              """})


def test_import_error_fields() -> None:
    same({"main.py": """\
              e = ImportError('m', 'n', name='x')
              print(repr(e), str(e), e.msg, e.name, e.path, e.name_from)
              e = ImportError('m', name='x', path='p')
              print(repr(e), str(e), e.msg)
              del e.msg
              print(e.msg, repr(ImportError()), repr(ImportError(name='q')), repr(ModuleNotFoundError('a', name='b')))
              e.name_from = 'f'
              print(e.name_from, isinstance(ModuleNotFoundError(), ImportError))
              """})


def test_globals_and_a_module_run_again() -> None:
    """globals() is the calling frame's module's; a module whose body failed runs again in a new
    module object, and a function its first run made keeps that run's namespace."""
    same({"helper.py": "def g():\n    return globals()\nNAME = 'helper'\n",
          "flaky.py": """\
              import sys
              def keep():
                  return VALUE
              VALUE = 'first'
              if 'flaky_kept' not in sys.modules['builtins'].__dict__:
                  sys.modules['builtins'].__dict__['flaky_kept'] = keep
                  raise RuntimeError('first run fails')
              VALUE = 'second'
              """,
          "main.py": """\
              import helper
              print(helper.g()['NAME'], globals()['__name__'], helper.g() is vars(helper))
              def local():
                  return globals() is vars(__import__('__main__'))
              print(local())
              try:
                  import flaky
              except RuntimeError as e:
                  print(e)
              import flaky
              print(flaky.VALUE, flaky_kept(), flaky.keep())
              """})


def test_sys_modules_edits() -> None:
    """E-04 excludes these in a program's own code; the standard library does them (os.path,
    collections.abc), so the runtime behaves as CPython."""
    same({"m.py": "print('m runs')\nX = 1\n",
          "replaced.py": "import sys\nclass StandIn:\n    def __repr__(self):\n        return '<the stand-in>'\nsys.modules[__name__] = StandIn()\n",
          "main.py": """\
              import sys
              import m
              del sys.modules['m']
              import m as again
              print(again is not m, sys.modules['m'] is again)
              sys.modules['m'] = 'not a module'
              import m as other
              print(other)
              def f():
                  import m
                  return m
              print(f())
              sys.modules['blocked'] = None
              try:
                  import blocked
              except ImportError as e:
                  print(type(e).__name__, e, e.name)
              import replaced
              print(replaced, sys.modules['replaced'])
              """})


def test_a_hook_replacing_import() -> None:
    """E-04 and E-06 exclude this in a program's own code. The call's arguments are CPython's; what
    a hook would also see of CPython's C code importing `_io` to read a module's file (how often
    depends on __pycache__) has no counterpart in a program that reads no module files, so the
    test leaves those calls out."""
    same({"pkg/__init__.py": "", "pkg/plain.py": "X = 1\n", "pkg/stars.py": "a = 1\n",
          "main.py": """\
              import builtins
              calls = []
              original = builtins.__import__
              def hook(name, globals=None, locals=None, fromlist=(), level=0):
                  if name != '_io':
                      calls.append((name, fromlist, level, globals is MODULE_GLOBALS, locals is None))
                  return original(name, globals, locals, fromlist, level)
              MODULE_GLOBALS = globals()
              builtins.__import__ = hook
              import pkg.plain
              from pkg import stars as s
              def local():
                  import pkg.plain as p
                  from pkg.plain import X
              local()
              builtins.__import__ = original
              print(calls)
              del builtins.__import__
              try:
                  import pkg
              except ImportError as e:
                  print(type(e).__name__, e)
              builtins.__import__ = original
              """})


def test_the_build_finds_the_programs_modules() -> None:
    """Packages before modules, a namespace package, function-local and literal __import__ names,
    and a built-in or frozen module's name never taken from the program's directory."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name, text in {"main.py": "import a.b\nfrom c import d\ndef f():\n    import e\n__import__('g')\nimport os\n",
                           "a/__init__.py": "", "a/b.py": "from . import sibling\n", "a/sibling.py": "",
                           "a.py": "", "c/__init__.py": "", "c/d.py": "", "e.py": "", "g.py": "", "os.py": "",
                           "ns/x.py": ""}.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text, encoding="utf-8")
        (root / "main.py").write_text((root / "main.py").read_text() + "import ns.x\n", encoding="utf-8")
        modules = find_program_modules(root / "main.py")
        found = {m.name: (m.path.relative_to(root.resolve()).as_posix() if m.path is not None else None, m.package)
                 for m in modules if m.path is None or m.path.is_relative_to(root.resolve())}
        library = {m.name: m for m in modules if m.path is not None and not m.path.is_relative_to(root.resolve())}
    assert found == {"a": ("a/__init__.py", True), "a.b": ("a/b.py", False), "a.sibling": ("a/sibling.py", False),
                     "c": ("c/__init__.py", True), "c.d": ("c/d.py", False), "e": ("e.py", False), "g": ("g.py", False),
                     "ns": (None, True)}, found
    # `os` is frozen, so the program's os.py is never imported; its closure comes with it
    assert library["os"].frozen and library["os"].path == STDLIB / "os.py" and "stat" in library
    assert not library["types"].frozen if "types" in library else True
    assert library["_collections_abc"].frozen and library["_collections_abc"].origin == STDLIB / "_collections_abc.py"
    assert "os.path" not in library and "collections.abc" not in library      # aliases their parents make


# ---- lazy imports (PEP 810; C-8-05 to C-8-07) ----
LAZY_FILES = {
    "noisy.py": "print('  [noisy runs]')\nVALUE = 42\ndef f():\n    return 'f'\nOTHER = 'other'\n",
    "broken.py": "print('  [broken runs]')\nraise LookupError('broken refuses')\n",
    "chained.py": "print('  [chained runs]')\ntry:\n    raise KeyError('inner')\nexcept KeyError:\n    raise ValueError('outer')\n",
    "pkg/__init__.py": "print('  [pkg runs]')\n",
    "pkg/sub/__init__.py": "print('  [pkg.sub runs]')\n",
    "pkg/sub/leaf.py": "print('  [pkg.sub.leaf runs]')\nLEAF = 'leaf'\n",
    "pkg/other.py": "print('  [pkg.other runs]')\nOTHER = 'other'\n",
}


def lazy(main: str, **more: str) -> None:
    same({**LAZY_FILES, **{k.replace("__", "/") + ".py": v for k, v in more.items()}, "main.py": main}, stderr=True)


def test_lazy_first_use_once_and_rebinding() -> None:
    lazy("""\
        import sys
        lazy import noisy
        lazy from noisy import VALUE, f as renamed
        g = globals()
        print('statement done', 'noisy' in sys.modules, type(g['noisy']).__name__, type(g['VALUE']).__name__, repr(g['noisy']), repr(g['VALUE']), repr(g['renamed']))
        print('use', VALUE)
        print('then', type(g['VALUE']).__name__, type(g['noisy']).__name__, type(g['renamed']).__name__)
        print(renamed(), noisy.OTHER, type(g['noisy']).__name__, type(g['renamed']).__name__)
        print(g['VALUE'], noisy.VALUE)
        lazy from noisy import OTHER
        print('loaded at once:', type(g['OTHER']).__name__, OTHER)
        """)


def test_lazy_use_from_functions_classes_and_other_modules() -> None:
    lazy("""\
        lazy import noisy
        lazy import pkg.other as aliased
        def reader():
            return noisy.VALUE
        print('defined')
        print(reader())
        class C:
            value = aliased.OTHER
        print(C.value)
        import holder
        print(type(vars(holder)['later']).__name__)
        print(holder.later.VALUE, type(vars(holder)['later']).__name__)
        print(hasattr(holder, 'never'), type(vars(holder)['never']).__name__, repr(vars(holder)['never']))
        """, holder="lazy import noisy as later\nlazy import absent_module as never\nprint('holder done')\n")


def test_lazy_errors_arrive_at_first_use_with_their_declaration() -> None:
    lazy("""\
        import sys
        lazy import broken
        lazy import chained
        lazy import absent_module
        lazy from noisy import nothing
        print('statements done')
        for attempt in (1, 2):
            try:
                broken.x
            except LookupError as e:
                c = e.__cause__
                print(attempt, type(e).__name__, e.args, 'broken' in sys.modules, type(c).__name__, c.args, e.__suppress_context__, c.__traceback__ is not None)
        try:
            chained.x
        except ValueError as e:
            print(type(e).__name__, type(e.__context__).__name__, e.__cause__, [n.rpartition(' at ')[0] for n in e.__notes__])
        try:
            absent_module.x
        except ModuleNotFoundError as e:
            print(type(e).__name__, e.name, e.__cause__.args)
        try:
            nothing
        except ImportError as e:
            print(type(e).__name__, e.name, e.name_from, e.__cause__.args)
        print('still a placeholder:', type(globals()['broken']).__name__)
        """)


def test_an_uncaught_lazy_error_reports_its_declaration() -> None:
    lazy("lazy import broken\nprint('declared')\nprint(broken.x)\n")


def test_lazy_dotted_imports_and_pending_submodules() -> None:
    lazy("""\
        import sys
        lazy import pkg.sub.leaf
        print('root', repr(globals()['pkg']), 'pkg' in sys.modules)
        print(pkg.__name__, 'pkg.sub' in sys.modules, 'sub' in vars(pkg))
        print(pkg.sub.__name__, 'pkg.sub.leaf' in sys.modules)
        print(pkg.sub.leaf.LEAF, 'leaf' in vars(pkg.sub))
        lazy import pkg.sub.leaf as leaf
        print(repr(globals()['leaf']))
        print(leaf.LEAF, leaf is sys.modules['pkg.sub.leaf'])
        """)
    lazy("""\
        import sys
        lazy from pkg.sub import leaf
        lazy from pkg import other, sub
        print(repr(globals()['leaf']), repr(globals()['other']), 'pkg' in sys.modules)
        print(leaf.LEAF, 'pkg.other' in sys.modules)
        print(type(globals()['other']).__name__, other.OTHER, sub.__name__)
        import pkg
        print(hasattr(pkg, 'absent'), getattr(pkg, 'absent', 'default'))
        """)
    lazy("""\
        import sys
        lazy import pkg.sub.leaf
        import pkg
        print('pkg' in sys.modules, 'pkg.sub' in sys.modules, 'sub' in vars(pkg))
        print(hasattr(pkg, 'sub'), 'pkg.sub' in sys.modules, 'sub' in vars(pkg))
        print(pkg.sub.leaf.LEAF)
        """)
    lazy("""\
        lazy import pkg.absent.child
        print(pkg.__name__)
        try:
            pkg.absent
        except ImportError as e:
            print(type(e).__name__, e.name)
        lazy import noisy.child
        try:
            noisy.VALUE
        except ImportError as e:
            print(type(e).__name__, e.name)
        """)


def test_lazy_modules_list_and_the_lazy_import_builtin() -> None:
    lazy("""\
        import sys
        __lazy_modules__ = ['noisy', 'pkg.other']
        import noisy
        from pkg import other
        import pkg.other as o2
        print('noisy' in sys.modules, 'pkg' in sys.modules, repr(globals()['noisy']), repr(globals()['other']), repr(globals()['o2']))
        print(noisy.VALUE, other.OTHER)
        __lazy_modules__ = ('noisy',)
        p = __lazy_import__('pkg.sub')
        print(repr(p), type(p).__name__, repr(__lazy_import__('pkg.sub', fromlist=('leaf',))), repr(__lazy_import__('pkg.sub', fromlist='leaf')))
        print(p.resolve().__name__)
        for f in (lambda: __lazy_import__(), lambda: __lazy_import__(1), lambda: __lazy_import__('x', level=-1),
                  lambda: __lazy_import__('x', 5), lambda: __lazy_import__('x', {}), lambda: __lazy_import__('x', None, None, None, 1),
                  lambda: __lazy_import__('x', globals(), None, 5)):
            try:
                f()
            except (TypeError, ValueError) as e:
                print(type(e).__name__, e)
        """)


def test_lazy_placeholders_are_objects_of_their_own_type() -> None:
    lazy("""\
        lazy import noisy
        lazy from noisy import nothing
        g = globals()
        p = g['noisy']
        L = type(p)
        print(L.__name__, L.__module__, repr(L), isinstance(p, L), hash(p) == hash(p), p == p, bool(p))
        for f in (lambda: p.VALUE, lambda: p.x, lambda: L(), lambda: g['nothing'].x, lambda: p.resolve(1)):
            try:
                print(f())
            except (AttributeError, TypeError) as e:
                print(type(e).__name__, e)
        print(p.resolve().VALUE, type(g['noisy']).__name__)
        q = g['noisy']
        del noisy
        print('noisy' in g)
        lazy import noisy
        noisy = 5
        print(noisy)
        def h():
            return noisy
        print(h())
        """)


def test_lazy_cycles_and_hooks() -> None:
    lazy("""\
        lazy import cyc_a
        try:
            cyc_a.V
        except ImportError as e:
            print(type(e).__name__, e.name, str(e), isinstance(e, ImportError))
        """, cyc_a="lazy from cyc_b import B\nprint('a runs')\nV = B\n", cyc_b="lazy from cyc_a import V as B\nprint('b runs')\nW = B\n")
    lazy("""\
        import builtins
        calls = []
        real = builtins.__import__
        def hook(name, globals=None, locals=None, fromlist=(), level=0):
            calls.append((name, globals is GLOBALS, locals is GLOBALS, fromlist, level))
            return real(name, globals, locals, fromlist, level)
        GLOBALS = globals()
        builtins.__import__ = hook
        lazy import noisy
        lazy from pkg.other import OTHER
        lazy import pkg.sub.leaf
        print('declared', calls)
        print(noisy.VALUE, OTHER, pkg.sub.leaf.LEAF)
        print([c for c in calls if c[0] != '_io'])
        builtins.__import__ = real
        real_lazy = builtins.__lazy_import__
        def lazy_hook(name, globals=None, locals=None, fromlist=None, level=0):
            print('lazy hook', name, globals is GLOBALS, locals is GLOBALS, fromlist, level)
            return real(name, globals, locals, fromlist or (), level)
        builtins.__lazy_import__ = lazy_hook
        lazy import pkg.other
        lazy from noisy import f
        print(f(), type(globals()['f']).__name__)
        del builtins.__lazy_import__
        try:
            import needs_lazy
        except ImportError as e:
            print(type(e).__name__, e)
        builtins.__lazy_import__ = real_lazy
        """, needs_lazy="lazy import noisy\n")


def test_lazy_import_called_outside_module_level_is_refused() -> None:
    """CPython raises SyntaxError, a class the runtime does not have yet: refused by name."""
    if shutil.which("g++") is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        main = Path(tmp, "main.py")
        main.write_text("def f():\n    return __lazy_import__('x')\nprint('start')\nf()\nprint('not reached')\n", encoding="utf-8")
        got = subprocess.run([str(build(main, str(main)))], capture_output=True, text=True, check=False, cwd=tmp)
    assert (got.returncode, got.stdout) == (70, "start\n") and "bella: not implemented" in got.stderr, got


def test_a_module_namespace_with_a_placeholder() -> None:
    lazy("""\
        import holder
        print(type(vars(holder)['VALUE']).__name__)
        from holder import VALUE
        print(VALUE, type(vars(holder)['VALUE']).__name__)
        import star_source
        print(type(vars(star_source)['OTHER']).__name__, star_source.__all__)
        from star_source import *
        print(OTHER, type(vars(star_source)['OTHER']).__name__)
        import hooks
        print(hooks.anything, dir(hooks))
        """,
         holder="lazy from noisy import VALUE\nprint('holder done')\n",
         star_source="lazy from noisy import OTHER\n__all__ = ['OTHER']\n",
         hooks="lazy from hook_src import __getattr__, __dir__\n",
         hook_src="def __getattr__(name):\n    return 'from the lazy hook ' + name\ndef __dir__():\n    return ['b', 'a']\n")


# ---- the standard library and the modules the runtime provides ----
def test_a_library_and_a_builtin_module_present_as_cpythons() -> None:
    """`types` is the standard library's own source, run compiled; `_types` is the runtime's. Paths
    are shown from the standard library's directory (D-12: the path recorded at build)."""
    same({"main.py": """\
              import sys
              import types
              import _types
              def path(p):
                  return p.rpartition('/python3.15/')[2]
              print(repr(_types), repr(_types.__spec__), _types.__package__, _types.__loader__, _types.__doc__)
              print(path(repr(types)), path(types.__file__), types.__package__, type(types.__loader__).__name__)
              s = types.__spec__
              print(s.name, s.parent, s.has_location, path(s.origin), s.submodule_search_locations, s.loader_state)
              print(list(vars(_types))[:5], list(vars(types))[:7], 'FunctionType' in vars(types))
              print([k for k in sys.modules if k in ('_types', 'types')])
              for n in ('AsyncGeneratorType', 'BuiltinFunctionType', 'BuiltinMethodType', 'CapsuleType', 'CellType',
                        'ClassMethodDescriptorType', 'CodeType', 'CoroutineType', 'EllipsisType', 'FrameLocalsProxyType',
                        'FrameType', 'FunctionType', 'GeneratorType', 'GenericAlias', 'GetSetDescriptorType', 'LambdaType',
                        'LazyImportType', 'MappingProxyType', 'MemberDescriptorType', 'MethodDescriptorType', 'MethodType',
                        'MethodWrapperType', 'ModuleType', 'NoneType', 'NotImplementedType', 'SimpleNamespace',
                        'TracebackType', 'UnionType', 'WrapperDescriptorType'):
                  print(n, repr(getattr(types, n)), getattr(types, n) is getattr(_types, n))
              def f():
                  pass
              class C:
                  def m(self):
                      pass
              print(isinstance(f, types.FunctionType), isinstance(len, types.BuiltinFunctionType), isinstance(C().m, types.MethodType),
                    isinstance(sys, types.ModuleType), types.ModuleType('x'), isinstance(type.__dict__, types.MappingProxyType),
                    type(None) is types.NoneType, type(NotImplemented) is types.NotImplementedType, type(...) is types.EllipsisType)
              print(types.get_original_bases(C))
              """})


def test_simple_namespace() -> None:
    same({"main.py": """\
              from types import SimpleNamespace as NS
              n = NS(a=1, b='two')
              print(n, repr(n), n.a, n.b, n == NS(a=1, b='two'), n != NS(a=1), n == 5, vars(n), type(n).__name__, type(n).__module__)
              print(NS({'x': 1}), NS([('y', 2)], z=3), NS({'x': 1}, x=2), NS())
              n.c = n
              print(n)
              del n.c, n.a
              print(n)
              class Sub(NS):
                  pass
              print(Sub(q=1), Sub(q=1) == NS(q=1), NS.__name__, NS.__qualname__, repr(NS))
              for f in (lambda: NS(1, 2), lambda: NS({1: 2}), lambda: NS(5), lambda: hash(NS()), lambda: n.nothing):
                  try:
                      print(f())
                  except (TypeError, AttributeError, ValueError) as e:
                      print(type(e).__name__)
              print(NS(a=1).__replace__(a=2, b=3), NS(a=1).__reduce__()[1:])
              """})


def test_a_missing_native_module_or_name_is_refused_and_an_omitted_one_is_not_installed() -> None:
    if shutil.which("g++") is None:
        return
    for body, refused in (("import _thread", "_thread"), ("import _types\n_types.nothing_here\nprint('absent')", None),
                          ("try:\n    import _decimal\nexcept ImportError as e:\n    print(type(e).__name__, e.name)", None),
                          ("try:\n    import not_a_module_anywhere\nexcept ImportError as e:\n    print(type(e).__name__, e.name)", None)):
        with tempfile.TemporaryDirectory() as tmp:
            main = Path(tmp, "main.py")
            main.write_text(body + "\n", encoding="utf-8")
            got = subprocess.run([str(build(main, str(main)))], capture_output=True, text=True, check=False, cwd=tmp)
            ref = subprocess.run([sys.executable, "-c", "import sys\nsys.modules['_decimal'] = None\n" + body], capture_output=True, text=True, check=False, cwd=tmp)
        if refused is not None:
            assert got.returncode == 70 and f"importing '{refused}'" in got.stderr, got
        else:
            assert (got.stdout, got.returncode) == (ref.stdout, ref.returncode), (body, got, ref)


def test_slot_descriptors_stand_in_the_class_dict_sorted() -> None:
    """Found on the way (the model's stateful test): type_new_slots sorts __slots__, and the class
    dict takes the member descriptors in that order, so a class's attributes are released in it."""
    same({"main.py": """\
              class R:
                  __slots__ = ("x", "k", "a")
              print([n for n in vars(R) if n in ("x", "k", "a")])
              class P:
                  def __init__(self, n): self.n = n
                  def __del__(self): print("dies", self.n)
              class Q:
                  __slots__ = ("x", "k")
              Q.x = P("first")
              Q.k = P("second")
              for n in [n for n in vars(Q) if n in ("x", "k")]:
                  delattr(Q, n)
              """})


# ---- str methods (runtime/src/str.cpp) ----
STR_METHODS = r'''
def show(x):
    """x with each character beyond Latin-1 as <code point> (repr of those needs unicodedata, D-8)"""
    if isinstance(x, str):
        return "".join([c if ord(c) < 256 else "<" + str(ord(c)) + ">" for c in x])
    if isinstance(x, (list, tuple)):
        return [show(y) for y in x]
    return x
samples = ["", "a", "abcabc", "  spaced  out  ", "\t\n x \x1c\x85　y ", "é·ü", "aaa", "a,b,,c,", "😀x😀"]
subs = ["", "a", "b", "bc", "x", "é", ",", "😀", "aa"]
bounds = [(None, None), (1, None), (-2, None), (0, -1), (2, 1), (10, 20), (-10, 2), (None, 3)]
for s in samples:
    for sub in subs:
        row = [s.find(sub), s.rfind(sub), s.count(sub), s.startswith(sub), s.endswith(sub)]
        for b in bounds:
            row += [s.find(sub, *b), s.rfind(sub, *b), s.count(sub, *b), s.startswith(sub, *b), s.endswith(sub, *b)]
        if sub:
            row += [s.partition(sub), s.rpartition(sub), s.split(sub), s.rsplit(sub), s.split(sub, 1), s.rsplit(sub, 1),
                    s.split(sub, 0), s.replace(sub, "<>"), s.replace(sub, "", 1), s.strip(sub), s.lstrip(sub), s.rstrip(sub)]
        row += [s.replace("", "-"), s.replace("", "-", 2)]
        print(show(s), show(sub), show(row))
    print(show([s.split(), s.rsplit(), s.split(None, 1), s.rsplit(None, 1), s.split(maxsplit=0), s.rsplit(sep=None, maxsplit=2),
                s.strip(), s.lstrip(), s.rstrip(), s.startswith(("q", "a")), s.endswith(("c", "x", ""))]))
print("a.b.c".rpartition("."), "abc".rpartition("."), "abc".partition("."), "x".partition("x"))
t, sep = "abc", "b"
print(t.partition(sep)[1] is sep, t.strip() is t, t.replace("q", "r") is t, t.partition("q")[0] is t, t.split()[0] is t,
      t.rpartition("q")[2] is t, t.replace("", "") is t)
def err(f):
    try:
        print(repr(f()))
    except (TypeError, ValueError) as e:
        print(type(e).__name__, e)
for f in (lambda: "a".find(), lambda: "a".find(1), lambda: "a".find("a", 1, 2, 3), lambda: "a".find("a", "x"),
          lambda: "a".index("b"), lambda: "a".rindex("b"), lambda: "a".index("a", 1), lambda: "a".find(sub="a"),
          lambda: "a".partition(""), lambda: "a".partition(1), lambda: "a".partition(), lambda: "a".rpartition(""),
          lambda: "a".split(""), lambda: "a".split(1), lambda: "a".split(",", "x"), lambda: "a".split(",", 1, 2),
          lambda: "a".split(",", sep=","), lambda: "a".strip(1), lambda: "a".strip("a", "b"), lambda: "a".lstrip(x="a"),
          lambda: "a".startswith(1), lambda: "a".startswith(("a", 1)), lambda: "a".endswith(("b", 1)),
          lambda: "a".replace("a"), lambda: "a".replace(1, "b"), lambda: "a".replace("a", 1), lambda: "aaa".replace("a", "b", count=2),
          lambda: "aaa".replace("a", "b", 1, count=2), lambda: "aaa".replace("a", "b", -1), lambda: "a b".split(maxsplit=-5),
          lambda: "abc".find("c", True), lambda: "x".count("", 0, 10), lambda: "abc".count("", 2), lambda: "".startswith("", 1)):
    err(f)
class Ix:
    def __index__(self):
        return 1
print("abc".find("b", Ix()), "a b c".split(" ", Ix()), "abc".startswith("b", Ix()))
'''


def test_str_methods_are_cpythons() -> None:
    same({"main.py": STR_METHODS})


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
