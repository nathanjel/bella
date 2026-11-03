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
from pipeline.closed_world import find_program_modules


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
    same({"m.py": "print('m runs')\nX = 1\n",
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
        found = {m.name: (None if m.path is None else m.path.relative_to(root.resolve()).as_posix(), m.package)
                 for m in find_program_modules(root / "main.py")}
    assert found == {"a": ("a/__init__.py", True), "a.b": ("a/b.py", False), "a.sibling": ("a/sibling.py", False),
                     "c": ("c/__init__.py", True), "c.d": ("c/d.py", False), "e": ("e.py", False), "g": ("g.py", False),
                     "ns": (None, True)}, found


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
