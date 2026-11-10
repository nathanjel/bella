"""Reviews A16 and G16 (2026-11-10; docs/reviews/review-log.md, RL-394 to RL-403): each fix's program and what stands around
it, compiled, against CPython; the names the bootstrap modules lack stop by name; the record guard keeps a prefix whole.
Review F17 (RL-404 to RL-421) below them: staged texts as texts, the preludes over a caller's subclass, the build and its dry run."""
from __future__ import annotations

import ast
import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from pipeline import staging
from pipeline.build import build, to_cpp
from pipeline.l1.frontend import annotation_text
from pipeline.l1.grammar import Unsupported
from pipeline.staging import run as staging_run
from pipeline.tests.test_review_2026_11_03 import same

# RL-394, RL-397: a built-in sequence's subclass loses sq_concat to its own __add__, sq_repeat to __mul__ or __rmul__, and the
# in-place slots to __iadd__ and __imul__; it has a number slot only when it defines one of the pair, and then that slot calls
# the method by name, the built-in's wrapper included
SEQUENCE_SLOTS = r"""
import _operator
def show(label, f):
    try:
        r = f()
        print(label, type(r).__name__, r)
    except TypeError as e:
        print(label, "TypeError", e)
NI = lambda self, other: NotImplemented
for base, item, other in ((list, [1], [2]), (tuple, (1,), (2,)), (str, "a", "b")):
    n = base.__name__
    Add = type("Add", (base,), {"__add__": NI})
    Mul = type("Mul", (base,), {"__mul__": NI})
    RMul = type("RMul", (base,), {"__rmul__": NI})
    IAdd = type("IAdd", (base,), {"__iadd__": NI})
    IMul = type("IMul", (base,), {"__imul__": NI})
    Both = type("Both", (base,), {"__add__": NI, "__iadd__": NI})
    Plain = type("Plain", (base,), {})
    show(n + " Add+", lambda: Add(item) + other)
    show(n + " other+Add", lambda: other + Add(item))
    show(n + " Mul*2", lambda: Mul(item) * 2)
    show(n + " 2*Mul", lambda: 2 * Mul(item))
    show(n + " RMul*2", lambda: RMul(item) * 2)
    show(n + " 2*RMul", lambda: 2 * RMul(item))
    show(n + " Plain+5", lambda: Plain(item) + 5)
    show(n + " other+Plain", lambda: other + Plain(item))
    show(n + " base.__add__", lambda: base.__add__(Add(item), other))
    show(n + " base.__mul__", lambda: base.__mul__(Mul(item), 2))
    def iadd(c):
        x = c(item); y = x; x += other; return (x, x is y, y)
    def imul(c):
        x = c(item); y = x; x *= 2; return (x, x is y, y)
    for label, c in (("IAdd", IAdd), ("Add", Add), ("Both", Both), ("Plain", Plain)):
        show(n + " " + label + "+=", lambda: iadd(c))
    for label, c in (("IMul", IMul), ("Mul", Mul), ("RMul", RMul), ("Plain", Plain)):
        show(n + " " + label + "*=", lambda: imul(c))
    show(n + " concat Add", lambda: _operator.concat(Add(item), other))
    show(n + " concat Plain", lambda: _operator.concat(Plain(item), other))
    show(n + " iconcat IAdd", lambda: _operator.iconcat(IAdd(item), other))
    show(n + " iconcat Both", lambda: _operator.iconcat(Both(item), other))
class Concat(list):
    def __add__(self, other): return "add"
    def __iadd__(self, other): return "iadd"
show("operator.concat", lambda: _operator.concat(Concat([1]), [2]))
show("operator.iconcat", lambda: _operator.iconcat(Concat([1]), [2]))
class X:
    def __radd__(self, o): return "radd"
    def __rmul__(self, o): return "rmul"
for v in ([1], type("L", (list,), {})([1]), "a", type("S", (str,), {})("a")):
    show(type(v).__name__ + " + X", lambda: v + X())
    show(type(v).__name__ + " * X", lambda: v * X())
class I(int): pass
def imul_int():
    n = I(2); n *= [1]; return n
show("int-subclass *= list", imul_int)
"""

# RL-395: PyCallable_Check of a built-in's subclass with __call__, and the exception group's predicate
CALLABLE = r"""
class Predicate(list):
    def __call__(self, e): return isinstance(e, ValueError)
class Number(int):
    def __call__(self): return int(self) + 1
class Text(str):
    pass
p = Predicate()
print(callable(p), callable(Number(1)), callable(Text("a")), Number(1)())
g = ExceptionGroup("g", [ValueError("v"), TypeError("t")])
print(g.subgroup(p).exceptions, [x.exceptions for x in g.split(p)])
"""

# RL-396: nb_index of a built-in's subclass, wherever an index is taken
INDEX = r"""
class L(list):
    def __index__(self): return 2
class T(tuple):
    def __index__(self): return 3
class S(str):
    def __index__(self): return 1
class F(float):
    def __index__(self): return 2
for f in (lambda: range(L()), lambda: [1] * L(), lambda: L() * [1], lambda: (1,) * T(), lambda: "ab" * S(), lambda: [10, 20, 30][L()],
          lambda: [10, 20, 30][S():], lambda: range(10)[F(0.5)], lambda: list(range(10))[L():T()], lambda: (1, 2, 3)[S()],
          lambda: hex(L()), lambda: [0, 1, 2].pop(S())):
    try:
        r = f()
        print(type(r).__name__, r)
    except TypeError as e:
        print("TypeError", e)
"""

# RL-398, RL-399, RL-403: the frozen modules' original names, the modules _bootstrap_external imports, the two modules' specs
FROZEN = r"""
import _imp, sys
import _frozen_importlib as boot, _frozen_importlib_external as ext
for name in ("_frozen_importlib", "_frozen_importlib_external", "zipimport", "os", "__hello_only__", "__phello_alias__", "nope"):
    print(name, _imp.find_frozen(name))
print(ext._imp is _imp, ext._io is sys.modules["_io"], ext._warnings is sys.modules["_warnings"], ext.sys is sys)
for m in (boot, ext):
    s = m.__spec__
    print(s, s.loader_state.origname, (s.loader_state.filename or "").rsplit("/", 2)[-2:], m.__loader__, repr(m.__package__),
          "__file__" in vars(m), s.submodule_search_locations, s.has_location, s.parent)
import importlib.util
print(importlib.util.find_spec("_frozen_importlib"), importlib.util.find_spec("_frozen_importlib_external"))
import importlib
print(boot.__file__.rsplit("/", 2)[-2:], ext.__file__.rsplit("/", 2)[-2:], sys._stdlib_dir == ext.__file__.rsplit("/", 2)[0])
"""

# RL-401: a staged compile under a __future__ feature that changes the code's flags
FUTURE = r"""
from __future__ import barry_as_FLUFL
c = compile("1 <> 2", "<test>", "eval")
print(eval(c), c.co_flags)
def f(): pass
print(hex(f.__code__.co_flags))
"""

# RL-402: a forward reference written over several lines
MULTILINE = r"""
from typing import Optional, Union
x = Optional[
    "int"
]
y = Union[
    int,
    "str",
]
print(x, y)
"""

# what the two bootstrap modules lack of CPython's names stops when read (RL-399)
STOPS = {
    "_frozen_importlib_external.marshal": "import _frozen_importlib_external as ext\next.marshal",
    "_frozen_importlib._thread": "import _frozen_importlib as boot\nprint(hasattr(boot, '_thread'))",
}


def test_sequence_slots_of_a_subclass() -> None:
    same(SEQUENCE_SLOTS)


def test_a_subclass_with_call_is_callable() -> None:
    same(CALLABLE)


def test_a_subclass_index() -> None:
    same(INDEX)


def test_the_frozen_modules() -> None:
    same(FROZEN)


def test_a_staged_compile_under_barry_as_flufl() -> None:
    same(FUTURE)


def test_a_forward_reference_over_lines() -> None:
    same(MULTILINE)


def test_what_the_bootstrap_modules_lack_stops_by_name() -> None:
    if shutil.which("g++") is None:
        return
    for name, body in STOPS.items():
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text("print('start')\n" + body + "\nprint('not reached')\n", encoding="utf-8")
            got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
        assert (got.returncode, got.stdout) == (70, "start\n") and name in got.stderr, (name, got)


def test_the_record_guard_keeps_a_prefix_with_a_space() -> None:
    """RL-400: an interpreter under a directory whose name holds a space is one forbidden path, not two words."""
    spec = importlib.util.spec_from_file_location("harness", Path(__file__).resolve().parents[2] / "conformance" / "harness.py")
    assert spec is not None and spec.loader is not None   # the conformance harness is a script, not a package
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)
    with tempfile.TemporaryDirectory() as tmp:
        venv = Path(tmp, "with space")
        subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True)
        paths = harness.machine_paths(str(venv / "bin" / "python"))
    assert str(venv) in paths and "space" not in paths and all(" " not in p or p.endswith("with space") for p in paths), paths



# ---- review F17 (docs/reviews/2026-11-10-fable-17-review.md; RL-404 to RL-421) -------------------------------------------------

# RL-404, RL-405, RL-406, RL-411: a staged text is a module's code run with the namespaces it is given. Its comprehensions are
# inlined (PEP 709) and read the frame's locals first, generator expressions, lambdas, functions and class bodies the globals;
# a walrus in a comprehension and a top-level `global` bind in the globals; an expression's text has no docstring; a text run
# from a text uses that text's locals
STAGED_TEXTS = r"""
import contextlib
import math

def run(label, src, g=None, loc=None, kind="exec", show=("v", "r", "s", "z", "after", "y", "q", "x", "plain", "made", "counter")):
    g = {} if g is None else g
    loc = {} if loc is None else loc
    try:
        r = (eval if kind == "eval" else exec)(src, g, loc)
    except Exception as e:
        r = type(e).__name__ + ": " + str(e.args)
    print(label, repr(r), {k: g[k] for k in show if k in g}, {k: loc[k] for k in show if k in loc}, sorted(k for k in g if k != "__builtins__"), sorted(loc))
G = {"w": "g"}
run("walrus", "[y := 5 for _ in 'a']")
run("walrus then read", "[y := 5 for _ in 'a']\nz = y")
run("walrus shadowed", "[y := 5 for _ in 'a']\nz = y", {}, {"y": "local y"})
run("own name", "w = 2\nv = [w + i for i in range(2)]")
run("list", "v = [w for _ in 'a']", dict(G), {"w": "l"})
run("nested", "v = [[w for _ in 'a'] for _ in 'b']", dict(G), {"w": "l"})
run("genexp", "v = list(w for _ in 'a')", dict(G), {"w": "l"})
run("genexp outer iterable", "v = list(u for u in w)", dict(G), {"w": "l"})
run("lambda in", "v = [(lambda: w)() for _ in 'a']", dict(G), {"w": "l"})
run("comp in lambda", "v = (lambda: [w for _ in 'a'])()", dict(G), {"w": "l"})
run("class body", "class C:\n    v = [w for _ in 'a']\nr = C.v", dict(G), {"w": "l"})
run("class body own", "class C:\n    w = 'class'\n    v = [w for _ in 'a']\n    u = [k for k in w]\nr = (C.v, C.u)", dict(G), {"w": "l"})
run("function", "def f():\n    return [w for _ in 'a']\nr = f()", dict(G), {"w": "l"})
run("builtin shadowed", "v = [len for _ in 'a'][0]('abc')", {}, {"len": lambda s: "local len"})
run("dict and set", "v = {k: w for k in 'a'}; s = {w for _ in 'a'}", dict(G), {"w": "l"})
run("iteration variable", "x = 1\nv = [x for x in range(3)]\nafter = x")
run("global then comp", "global q\nq = 1\nv = [q for _ in 'a']", {}, {"q": "l"})
run("eval", "[w for _ in 'a']", dict(G), {"w": "l"}, "eval")
run("condition", "v = [1 for _ in 'a' if w]", dict(G), {"w": ""})
run("iterable", "v = [u for u in w]", dict(G), {"w": "l"})
run("inner iterable", "v = [u for _ in 'a' for u in w]", dict(G), {"w": "l"})
run("deleted local", "del w\nv = [w for _ in 'a']", dict(G), {"w": "l"})
run("missing", "v = [nope for _ in 'a']")
run("fstring", "v = [f'{w}!' for _ in 'a']", dict(G), {"w": "l"})
run("comp in default", "def f(a=[w for _ in 'a']):\n    return a\nr = f()", dict(G), {"w": "l"})
run("comp in decorator", "def deco(v):\n    return lambda f: v\n@deco([w for _ in 'a'])\ndef r(): pass", dict(G), {"w": "l"})
run("def then comp", "def sq(n):\n    return n * n\nv = [sq(i) for i in range(3)]")
run("import then comp", "import math\nv = [math.floor(i / 2) for i in range(3)]")
run("class then comp", "class K:\n    n = 3\nv = [K.n for _ in 'a']")
run("global decl", "global counter, made\ncounter += 1\nmade = 'here'\nplain = 1\n", {"counter": 10})
run("global del", "global x\ndel x", {"x": 1}, {"x": 10})
run("global in block", "if True:\n    global x\n    x = 5\nz = x", {}, {"x": "local"})
run("global def", "global f\ndef f():\n    return 1\nz = f()")
run("global class", "global K\nclass K:\n    pass\nz = K.__name__")
run("global import", "global math\nimport math\nz = math.pi > 3")
run("global for", "global i\nfor i in range(3):\n    pass\nz = i", {}, {"i": "local"})
run("global with", "import contextlib\nglobal cm\nwith contextlib.nullcontext(7) as cm:\n    pass\nz = cm")
run("global except", "global e\ntry:\n    1 / 0\nexcept ZeroDivisionError as e:\n    z = type(e).__name__\nafter = 'e' in globals()")
run("global walrus", "global n\nz = (n := 4) + 1", {}, {"n": "local"})
run("global annotated", "global a\na: int = 3\nz = a", {}, {"a": "local"})
run("global unpack", "global p, q\np, q = 1, 2\nz = p + q", {}, {"p": "lp"})
run("global read prefers", "global x\nz = x", {"x": "g"}, {"x": "l"})
run("global then function reads", "global x\nx = 1\ndef f():\n    return x\nr = f()")
run("global aug", "global t\nt = [1]\nt += [2]\nz = t", {}, {"t": "local"})
run("docstring exec", "'''text doc'''\nz = 1")
run("literal eval", "'abc'", kind="eval")
run("literal eval concat", "'x' 'y'", kind="eval")
run("bytes eval", "b'x'", kind="eval")
run("nested exec", "x = 1\nr = eval('x + 1')\nexec('y = 5')\n", {"__name__": "m"})
run("nested exec globals given", "x = 1\nexec('y = x', globals())\n", {"__name__": "m", "x": "g"})
print(__doc__)
"""

# RL-404: the value of a str literal, every spelling, and the module's own docstring untouched
EVAL_LITERALS = r"""
'''module doc'''
print(repr(eval("'abc'")))
print(repr(eval(repr("round trip"))))
print(repr(eval('"x" "y"')), repr(eval("'''triple'''")), repr(eval("('paren')")))
print(repr(eval(compile("'compiled'", "<c>", "eval"))))
ns: dict[str, object] = {}
print(repr(eval("'in ns'", ns)), ns.get("__doc__"))
print(__doc__)
print(repr(eval("'a' + 'b'")), repr(eval("b'bytes'")), repr(eval("f'f{1}'")), repr(eval("1")))
"""

# RL-404 to RL-406 through compile(): the code object carries the same rules
THROUGH_COMPILE = r"""
code = compile("[w * 2 for _ in range(2)]", "<expr>", "eval")
try:
    print(eval(code, {}, {"w": 21}))
except NameError as e:
    print("NameError", e.args)
g: dict[str, object] = {}
loc: dict[str, object] = {}
exec(compile("global made\nmade = 1\n", "<stmt>", "exec"), g, loc)
print("made" in g, "made" in loc)
print(repr(eval(compile("'text'", "<lit>", "eval"))))
"""

# RL-407, RL-408, RL-415, RL-416: where the C reads a str's code points, a list's or a tuple's items, the preludes do, whatever
# a caller's subclass defines; RL-412: PyErr_SetObject(PyExc_KeyError, key); RL-420: tm_year + 1900 in a C int; RL-421: an empty
# dict is copied before its class is asked anything
STRINGIO = r"""
import io


def escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Markup(str):
    '''Text that is already safe; anything concatenated to it is escaped (as markupsafe.Markup does).'''

    def __add__(self, other: str) -> "Markup":
        return Markup(str.__add__(self, other if isinstance(other, Markup) else escape(other)))

    def __radd__(self, other: str) -> "Markup":
        return Markup(str.__add__(other if isinstance(other, Markup) else escape(other), self))


out = io.StringIO()
out.write("<p>")
out.write(Markup("<b>bold</b>"))
out.write("</p>")
print(out.getvalue())


class Tag(str):
    pass


buf = io.StringIO(Tag("init"))
print(type(buf.getvalue()).__name__, type(io.StringIO(Markup("m")).read()).__name__)
"""

HEAPQ = r"""
import heapq


class Recent(list):
    '''A list whose indexing counts from the end: [0] is the newest item.'''

    def __getitem__(self, i):
        return list.__getitem__(self, -1 - i) if isinstance(i, int) else list.__getitem__(self, i)


h = Recent()
for v in [5, 1, 4, 2, 3]:
    heapq.heappush(h, v)
print(list(list.__iter__(h)), [heapq.heappop(h) for _ in range(5)])


class Logged(list):
    log: list[object] = []

    def __setitem__(self, i, v):
        Logged.log.append(i)
        list.__setitem__(self, i, v)

    def __delitem__(self, i):
        Logged.log.append(("del", i))
        list.__delitem__(self, i)


s = Logged([3, 2, 1])
heapq.heapify(s)
heapq.heappush(s, 0)
heapq.heappop(s)
print(Logged.log)
"""

KEYERROR = r"""
from collections import OrderedDict

cache: OrderedDict = OrderedDict()
cache[("user", 1)] = "a"
for attempt in (lambda: cache.move_to_end(("user", 2)), lambda: cache.pop(("user", 2)), lambda: cache.pop(None), lambda: cache.move_to_end(None, last=False)):
    try:
        attempt()
    except KeyError as e:
        print(repr(e), e.args, "[%s]" % e)
"""

CSV_DIALECT = r"""
import csv
import io


class In(str):
    def __contains__(self, x: object) -> bool:
        return True


class Eq(str):
    def __eq__(self, o: object) -> bool:
        return True

    def __hash__(self) -> int:
        return 1


class Zero(str):
    def __len__(self) -> int:
        return 0


for label, kw in (("lineterminator contains", {"lineterminator": In("\n")}), ("delimiter eq", {"delimiter": Eq(";")}), ("delimiter len", {"delimiter": Zero(";")}), ("quotechar eq", {"quotechar": Eq("'")}), ("escapechar contains", {"escapechar": In("\\")})):
    b = io.StringIO()
    try:
        csv.writer(b, **kw).writerow(["a;b", "c'd", "e\\f", 1])
        print(label, repr(b.getvalue()))
    except (ValueError, TypeError, csv.Error) as e:
        print(label, type(e).__name__, e.args)
"""

SPLITLINES = r"""
class Tag(str):
    def __repr__(self) -> str:
        return "Tag(" + str.__repr__(self) + ")"


t = Tag("one line")
print(t.splitlines())
print(type(t.splitlines()[0]).__name__, t.splitlines()[0] is t)
print(type(t.splitlines(True)[0]).__name__, type(Tag("a\nb").splitlines()[0]).__name__)
"""

GMTIME = r"""
import time

print(tuple(time.gmtime(67768036191676799)))
print(tuple(time.gmtime(67767976233532800)))
"""

EMPTY_COPY = r"""
from collections import OrderedDict


class D(OrderedDict):
    def keys(self):
        print("keys called")
        return super().keys()


d = D()
print(dict.copy(d), len(d.items() ^ {}.items()))
"""

PEP563 = r"""
from __future__ import annotations


def total(xs: list[int], limit: max(n for n in (1, 2)) = 2) -> sum(x for x in ()): ...
def key(order: lambda *parts: parts, by: lambda **kw: kw, only: lambda *, strict: strict) -> None: ...
def show(label: f"it's a \"{total}\"") -> None: ...


print(total.__annotations__)
print(key.__annotations__)
print(show.__annotations__)
"""

DRY_RUN_UNPARSE = r"""
from __future__ import annotations

from dataclasses import dataclass


def render(x: int, fmt: f"\x1b[{x}m" = "") -> str:
    return fmt + str(x)


@dataclass
class Point:
    x: int
    y: int = 0


print(Point(1, 2), render(3), render.__annotations__["fmt"])
"""

SUBCLASS_READS = r"""
import csv
import io
import json
import math
import operator
import time
from collections import namedtuple


class Chars(str):
    def __iter__(self):
        return iter(["<", str(self), ">"])


buf = io.StringIO()
csv.writer(buf).writerow([Chars("a,b"), Chars("plain")])
print(repr(buf.getvalue()))


class Shout(str):
    def __str__(self) -> str:
        return "!"

    def __radd__(self, other: str) -> str:
        return "radd"

    def split(self, *a: object) -> list[str]:
        return ["imag"]

    def __contains__(self, x: object) -> bool:
        return True


print(json.dumps([1, 2], separators=(Shout(";"), Shout("="))), json.dumps({"a": 1}, separators=(Shout(";"), Shout("="))))
print(json.dumps([1], indent=Shout("--")))
print(operator.attrgetter(Shout("real"))(5))
try:
    print(time.get_clock_info(Shout("monotonic")).monotonic)
except ValueError as e:
    print("ValueError", e)


class Empty(tuple):
    def __len__(self) -> int:
        return 0


try:
    print(math.dist(Empty((1, 2)), (4, 6)))
except ValueError as e:
    print("ValueError", e)
Point = namedtuple("Point", "x y")
err = ValueError()
err.args = Point(1, 2)
print(type(err.args).__name__, err.args)
"""

# RL-409: a text that asks for the frame's locals from inside a comprehension would have to see the comprehension's variables
# (PEP 709); RL-414: a text CPython's compiler warns of, whose warning the program's filters would see each time it is compiled;
# RL-415: a class's __qualname__ that is a str subclass's instance is kept as that object by CPython
F17_STOPS = {
    "in a comprehension": "rows = [1, 2, 3]\nprint([eval('r * 10') for r in rows])",
    "in a comprehension, with": "print({k: eval('k.upper()') for k in 'ab'})",
    "eval at __main__:<module>: the staged text makes CPython's compiler warn (SyntaxWarning": "print(eval('1 is 1'))",
    "compile() at __main__:<module>: the staged text makes CPython's compiler warn (SyntaxWarning": "compile(chr(39) + chr(92) + 'd' + chr(39), '<w>', 'eval')",
    "__qualname__": "class S(str): pass\ntype('N', (), {'__qualname__': S('Q')})",
}

# RL-409: what stands around the stop: the first iterable is evaluated outside the comprehension, a function called from one has
# a frame of its own, and a text given its namespaces asks for no frame's
AROUND_THE_COMPREHENSION_STOP = r"""
rows = [1, 2, 3]
def scaled(r: int) -> int:
    return eval("r * 10", {"r": r})
print([r for r in eval("rows")], [scaled(r) for r in rows], [eval("r + 1", {}, {"r": r}) for r in rows])
print([n for n in (eval("len(rows)"),)], sorted({k: eval("k.upper()", {"k": k}) for k in "ab"}.items()))
"""

# RL-413: the expressions on which ast.unparse and Python/ast_unparse.c differ, and some on which they agree
ANNOTATIONS = ["list[int]", "max(n for n in (1, 2))", "sum(x for x in ())", "f(a, (b for b in c))", "lambda *parts: parts", "lambda **kw: kw",
               "lambda *, strict: strict", "lambda a, *b, c=1, **d: a", "f'it\\'s a \"{total}\"'", "True.real", "None.__class__", "1 .real",
               "'quoted'", "__private", "a if b else c", "x[1:2, ...]", "{**a, 'k': [*b]}", "not a or -b ** 2", "f'{x!r:>{w}}'",
               "b'\\x00' + b\"'\"", "1e100j", "(a, *b)", "x @ y", "await_", "*Ts"]


def test_staged_texts_as_texts() -> None:
    same(STAGED_TEXTS)


def test_eval_of_a_literal() -> None:
    same(EVAL_LITERALS)


def test_texts_through_compile() -> None:
    same(THROUGH_COMPILE)


def test_stringio_copies_code_points() -> None:
    same(STRINGIO)


def test_heapq_reads_the_list() -> None:
    same(HEAPQ)


def test_preludes_read_a_subclass_as_the_c_does() -> None:
    same(SUBCLASS_READS)
    same(CSV_DIALECT)
    same(SPLITLINES)


def test_keyerror_gmtime_and_an_empty_copy() -> None:
    same(KEYERROR)
    same(GMTIME)
    same(EMPTY_COPY)


def test_pep563_strings_are_the_compilers() -> None:
    same(PEP563)
    same(DRY_RUN_UNPARSE)


def test_annotation_text_is_the_compilers() -> None:
    """RL-413 without a build: each text is what the pinned compiler stores for the annotation."""
    for source in ANNOTATIONS:
        starred = source.startswith("*")
        program = "from __future__ import annotations\ndef f(" + ("*a: " if starred else "a: ") + source + "): ...\n"
        namespace: dict[str, Any] = {}
        exec(compile(program, "<annotations>", "exec", dont_inherit=True), namespace)  # noqa: S102
        tree = ast.parse(program).body[1]
        assert isinstance(tree, ast.FunctionDef)
        arg = tree.args.vararg if starred else tree.args.args[0]
        assert arg is not None and arg.annotation is not None
        assert annotation_text(arg.annotation) == namespace["f"].__annotations__["a"], source


def test_what_f17_found_stops_by_name() -> None:
    if shutil.which("g++") is None:
        return
    same(AROUND_THE_COMPREHENSION_STOP)
    for name, body in F17_STOPS.items():
        with tempfile.TemporaryDirectory() as tmp:
            prog = Path(tmp, "prog.py")
            prog.write_text("print('start')\n" + body + "\nprint('not reached')\n", encoding="utf-8")
            got = subprocess.run([str(build(prog, "prog.py"))], capture_output=True, text=True, check=False, cwd=tmp)
        assert (got.returncode, got.stdout) == (70, "start\n") and name in got.stderr, (name, got)


def test_a_long_chain_builds_or_is_refused_by_name() -> None:
    """RL-417: a chain as deep as it is long goes through the passes; past their reach the build refuses, with no traceback."""
    chain = "x = " + " + ".join(["1"] * 330) + "\nprint(x)\n"
    same(chain)
    for source in ("x = " + " + ".join(["1"] * 3000) + "\n", "x = 0\nif x == 1:\n    pass\n" + "".join(f"elif x == {i}:\n    pass\n" for i in range(2, 400)),
                   "class A:\n    def m(self): return self\nx = A()" + ".m()" * 400 + "\n", "x = " + " and ".join(["1"] * 600) + "\n",
                   "x = " + "[" * 150 + "]" * 150 + "\n"):
        assert "x" in to_cpp(source, "chain.py", "bella::m_main")
    limit = sys.getrecursionlimit()
    try:
        to_cpp("x = " + " + ".join(["1"] * 30000) + "\n", "chain.py", "bella::m_main")
    except (Unsupported, RecursionError, MemoryError) as exc:      # the pinned compiler itself gives up between 10000 and 30000 terms
        assert isinstance(exc, Unsupported) and "chain" in str(exc), exc
    else:
        raise AssertionError("a 30000-term chain was lowered")
    assert sys.getrecursionlimit() == limit


def test_a_failure_of_the_dry_run_itself_fails_the_build() -> None:
    """RL-418: the tool's own error has its own exit status, which the build does not take for "nothing staged"."""
    assert staging.TOOL_FAILED == staging_run.TOOL_FAILED
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp, "artefact")
        try:
            staging_run.dry_run(out, [], ["--modules-from", str(Path(tmp, "no-such-lock.json"))])
        except staging_run.DryRunFailed as exc:
            assert exc.tool, exc
        else:
            raise AssertionError("the dry run went through")
        prog = Path(tmp, "ends.py")                      # a program that ends the process is not the tool failing
        prog.write_text("import os\nos._exit(3)\n", encoding="utf-8")
        try:
            staging_run.dry_run(out, [], ["--entry", str(prog)])
        except staging_run.DryRunFailed as exc:
            assert not exc.tool, exc
        else:
            raise AssertionError("the dry run went through")


if __name__ == "__main__":
    test_sequence_slots_of_a_subclass()
    test_a_subclass_with_call_is_callable()
    test_a_subclass_index()
    test_the_frozen_modules()
    test_a_staged_compile_under_barry_as_flufl()
    test_a_forward_reference_over_lines()
    test_what_the_bootstrap_modules_lack_stops_by_name()
    test_the_record_guard_keeps_a_prefix_with_a_space()
    test_staged_texts_as_texts()
    test_eval_of_a_literal()
    test_texts_through_compile()
    test_stringio_copies_code_points()
    test_heapq_reads_the_list()
    test_preludes_read_a_subclass_as_the_c_does()
    test_keyerror_gmtime_and_an_empty_copy()
    test_pep563_strings_are_the_compilers()
    test_annotation_text_is_the_compilers()
    test_what_f17_found_stops_by_name()
    test_a_long_chain_builds_or_is_refused_by_name()
    test_a_failure_of_the_dry_run_itself_fails_the_build()
