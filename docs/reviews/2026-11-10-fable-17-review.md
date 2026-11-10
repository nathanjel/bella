Claude Fable 5.2, in a separate session of its own, 2026-11-10, asked by the author as a cross-check of rounds 14 to 16 by the
newest model. Verbatim. Tag F17 in the review log. Its range is `3ea072a..d9ff83f` (36 commits); it ran in its own worktree
(`bella-f17`) at `d9ff83f`, whose line numbers its citations carry. Eighteen findings; its probes (`f17-probes/`) stayed in
that worktree.

---

# Review F17 (Fable 5.2): `3ea072a..d9ff83f`, a cross-check of rounds 14 to 16

Date: 2026-11-10. Worktree `bella-f17` at `d9ff83f`; nothing else was touched. Oracle: `.venv/bin/python prog.py`
(CPython 3.15.2). Bella: `uv run python pipeline/build.py --run prog.py`. Every finding below was reproduced that way;
the programs are in `f17-probes/findings/` (untracked, in this worktree), named by finding id, with both outputs
beside them; the probe files (`f17-probes/p*.py`, with `drive.py` and `h.py` that run them) are there too.

Method: about 40,000 differential probes (one CPython run and one Bella binary per probe file, restarted after each
stop by name), then the code behind each difference read. The reference C sources (3.15.2) were fetched into
`f17-cpython-src/` and only read. Differences that are a recorded deviation were dropped: D-07 (finalisation order at
exit), D-08 (wording of built-in messages), D-16 (`cached`), D-20 (omitted modules: `_decimal`, `_datetime`,
`_hashlib`, `importlib.abc` and the rest).

## Summary

18 findings: 1 high, 6 medium, 11 low. The areas the earlier rounds probed hardest (list/tuple/str/dict subclasses in
`ops.cpp` and `call.cpp`, OrderedDict's order, the exception groups, struct, binascii, math, the digests, random) agree
with CPython almost everywhere; what I found there is small. The weight is elsewhere:

* **Staged texts** (focus 3). The frontend lowers an `eval`/`exec`/`compile` text as an ordinary module, and three of a
  module's rules are wrong for a text: a leading string is taken for a docstring (F17-01), a comprehension reads
  globals (F17-02), a top-level `global` is dropped (F17-03). Two more are in the runtime's choice of locals (F17-06,
  F17-08). The code is older than the range, but 726399f's code objects run through it
  (`F17-01-02-03_through_compile.py` shows all three through `compile()`), and none of it stops by name.
* **Preludes that use Python operators on a caller's object** where the C reads storage: `StringIO` (F17-04), `_heapq`
  (F17-05), and a group of smaller ones (F17-12). RL-352, RL-360, RL-383 and RL-384 fixed members of this family; it is
  not closed.
* **The build**: the dry run performs the program's writes (F17-07), dies on its own `LookupError` and is ignored
  (F17-15), and the frontend overflows the host's recursion limit on long chains (F17-14).

## Findings

### F17-01 (high): `eval` of a string literal returns None and overwrites `__doc__`

`pipeline/l1/frontend.py:2407` wraps an eval text as `Module([Expr(body)])`; `pipeline/l1/frontend.py:188`
(`_docstring(tree.body)`) then takes that statement for the module's docstring, removes it and stores `__doc__`.

```python
"""module doc"""
print(repr(eval("'abc'")))
print(repr(eval(repr("round trip"))))
print(repr(eval('"x" "y"')), repr(eval("'''triple'''")), repr(eval("('paren')")))
print(repr(eval(compile("'compiled'", "<c>", "eval"))))
ns: dict[str, object] = {}
print(repr(eval("'in ns'", ns)), ns.get("__doc__"))
print(__doc__)
print(repr(eval("'a' + 'b'")), repr(eval("b'bytes'")), repr(eval("f'f{1}'")), repr(eval("1")))
```

CPython:
```
'abc'
'round trip'
'xy' 'triple' 'paren'
'compiled'
'in ns' None
module doc
'ab' b'bytes' 'f1' 1
```
Bella:
```
None
None
None None None
None
None in ns
compiled
'ab' b'bytes' 'f1' 1
```

Cause: mode "eval" reuses the module pipeline, whose docstring rule does not apply to an expression. `eval(repr(s))`
for a str is the plausible program. The module's own `__doc__` is replaced too (line 6 of the output). eval1 and eval2
share the frontend, so the three evaluators agree with each other and the corpus has no case.

### F17-02 (medium): a comprehension in an `exec`/`eval` text with its own locals reads the globals

`pipeline/l1/frontend.py:1686-1742` (a comprehension becomes a helper function), `pipeline/l2/resolve.py:505-508` (a
function's implicit global is `load_global`).

```python
g: dict[str, object] = {"w": "from globals"}
loc: dict[str, object] = {"w": "from locals"}
exec("v = [w for _ in range(2)]", g, loc)
print("shadowed:", loc["v"])
print("eval:", eval("[w for _ in range(2)]", g, loc))

ns: dict[str, object] = {}
try:
    exec("w = 2\nv = [w + i for i in range(2)]\n", {}, ns)
    print("exec:", ns["v"])
except NameError as e:
    print("exec NameError", e.args)
try:
    print("eval:", eval("({k: n for k in 'a'}, {n for _ in 'a'})", {}, {"n": 5}))
except NameError as e:
    print("eval NameError", e.args)
```

CPython:
```
shadowed: ['from locals', 'from locals']
eval: ['from locals', 'from locals']
exec: [2, 3]
eval: ({'a': 5}, {5})
```
Bella:
```
shadowed: ['from globals', 'from globals']
eval: ['from globals', 'from globals']
exec NameError ("name 'w' is not defined",)
eval NameError ("name 'n' is not defined",)
```

Cause: PEP 709. CPython inlines a list, set or dict comprehension into module-level code, where a free name is
`LOAD_NAME` (locals, globals, builtins); the helper function reads globals only. A module run as a module cannot tell
(its locals are its globals); a text given locals can. `eval(expr, {}, variables)` with a comprehension that uses a
second variable is the plausible program: a NameError, or silently the global of the same name. The same root gave
NameError for a function, class or import defined earlier in the same text (`[sq(x) for x in xs]`), a lambda default
inside a comprehension and an f-string holding one, and the builtin `len` where the locals shadow it (some twenty
probes in `p18.py` and `p24.py`). A generator expression is right (CPython does not inline it).

### F17-03 (medium): `global` at the top level of an `exec` text is ignored

`pipeline/l1/frontend.py:2117-2118`: a `Global` statement becomes `Pass`, "recorded on the enclosing FunctionDef"; a
module has none, so its names stay `name` kind and `store_name` writes the locals.

```python
g: dict[str, object] = {"counter": 10}
loc: dict[str, object] = {}
exec("global counter, made\ncounter += 1\nmade = 'here'\nplain = 1\n", g, loc)
print(sorted(k for k in g if k != "__builtins__"), g["counter"], sorted(loc))

g2: dict[str, object] = {"x": 1}
loc2: dict[str, object] = {"x": 10}
exec("global x\ndel x", g2, loc2)
print("x" in g2, "x" in loc2)
```

CPython:
```
['counter', 'made'] 11 ['plain']
False True
```
Bella:
```
['counter'] 10 ['counter', 'made', 'plain']
True False
```

Cause: as above, a rule that is a no-op for a real module. Every binding form is affected (assignment, augmented
assignment, `del`, `import`, `def`, `class`, `for`, `with`, `except ... as`, walrus, annotation, unpacking), and a read
prefers the local. `exec("global x\nx = 1\ndef f():\n    return x\nr = f()", {}, {})` raises NameError in Bella and
gives 1 in CPython.

### F17-04 (medium): `io.StringIO` runs a str subclass's `+`, slicing and `replace` on its buffer

`runtime/prelude/_io.py:3121-3131` (`_sio_write_str`): `text[:pos] + decoded + text[pos + length:]` with `decoded` the
caller's object. Predates the range.

```python
import io


def escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Markup(str):
    """Text that is already safe; anything concatenated to it is escaped (as markupsafe.Markup does)."""

    def __add__(self, other: str) -> "Markup":
        return Markup(str.__add__(self, other if isinstance(other, Markup) else escape(other)))

    def __radd__(self, other: str) -> "Markup":
        return Markup(str.__add__(other if isinstance(other, Markup) else escape(other), self))


out = io.StringIO()
out.write("<p>")
out.write(Markup("<b>bold</b>"))
out.write("</p>")
print(out.getvalue())
```

CPython: `<p><b>bold</b></p>`
Bella: `&lt;p&gt;<b>bo</p>b>`

Cause: the subclass's `__radd__` builds the buffer, so the text already written is escaped, the buffer becomes a
`Markup` whose length is not what the position advanced by, and the next write lands in the middle. The C copies code
points. The same for the initial value and `writelines`; `getvalue()` and `read()` then return the subclass. `print`
to a StringIO is unaffected (it writes `str(obj)`, an exact str). `TextIOWrapper.write` is careful (`str.__len__`,
`str.find`) except for `text.replace` at `_io.py:2729`, reached only with a `newline` that translates.

### F17-05 (medium): `_heapq` reads and writes a list subclass through its `__getitem__`, `__setitem__`, `__delitem__`

`runtime/prelude/_heapq.py:46-58, 72-79, 88-94, 102-118, 186` (`heap[pos]`, `heap[parentpos] = newitem`,
`del heap[n - 1:n]`). Commit a097715.

```python
import heapq


class Recent(list):
    """A list whose indexing counts from the end: [0] is the newest item."""

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
```

CPython:
```
[1, 2, 4, 5, 3] [1, 2, 3, 4, 5]
[]
```
Bella:
```
[5, 1, 4, 2, 3] [2, 2, 1, 1, 1]
[2, 0, 1, 3, 0, 1, ('del', slice(3, 4, None)), 0, 1, 0]
```

Cause: `_heapqmodule.c` uses `PyList_GET_ITEM`, `PyList_SET_ITEM` and `PyList_SetSlice`. The prelude took care of
`len` (`list.__len__`) and `append` but not of item access. Same family as RL-360 and RL-384.

### F17-06 (medium): `eval` inside a module-level comprehension does not see the comprehension's variable

`runtime/src/staged.cpp:104-114` (`from_frame`: a `<module>` caller's locals are its globals); the variable is a local
of the comprehension's helper.

```python
rows = [1, 2, 3]
try:
    print([eval("r * 10") for r in rows])
except NameError as e:
    print("NameError", e.args)
try:
    print({k: eval("k.upper()") for k in "ab"})
except NameError as e:
    print("NameError", e.args)
```

CPython:
```
[10, 20, 30]
{'a': 'A', 'b': 'B'}
```
Bella:
```
NameError ("name 'r' is not defined",)
NameError ("name 'k' is not defined",)
```

Cause: PEP 709 again: the module frame's locals include the inlined comprehension's variables. The same call in a
function stops by name ("eval() in a function or class body, with the frame's locals"); here a catchable NameError
stands where that stop was the honest outcome.

### F17-07 (medium, build; a consequence of the staging design): the dry run performs the program's writes

`pipeline/staging/dryrun.py` imports the entry script as `__bella_entry__` and runs its module body under CPython at
build time whenever `_MAY_STAGE` matches (`pipeline/build.py:186, 318`). Only the output is discarded.

```python
import os
from collections import namedtuple

Run = namedtuple("Run", "n")
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "counter.txt")
n = int(open(path).read()) if os.path.exists(path) else 0
with open(path, "w") as f:
    f.write(str(n + 1))
print(Run(n + 1))
```

From the same starting state (no `counter.txt`): CPython prints `Run(n=1)`; `build.py --run` prints `Run(n=2)` and
leaves `2` in the file.

Cause: a script with no main guard that mentions `namedtuple`, `dataclass`, `TypeVar`, `eval` or a quoted typing
subscript is executed once by the build. `docs/staging.md` lists what module bodies read; it does not say that a
program's writes, deletions or network calls happen at build time, and nothing confines them. I report it as a finding
because the command the project gives for checking a program shows a difference; whether to confine the dry run or to
document it is the author's decision.

### F17-08 (low): `eval`/`exec` called from a staged text that has its own locals uses the globals as locals

`runtime/src/staged.cpp:113`: the caller's code name is `<module>` for a staged text's frame too, so its `m->locals`
is passed over.

```python
g: dict[str, object] = {"__name__": "__main__"}
loc: dict[str, object] = {}
try:
    exec("x = 1\nr = eval('x + 1')\nexec('y = 5')\n", g, loc)
except NameError as e:
    print("NameError", e.args)
print(sorted(loc), "y" in g)
```

CPython: `['r', 'x', 'y'] False`
Bella: `NameError ("name 'x' is not defined",)` then `['x'] False`

### F17-09 (low): OrderedDict's KeyError for a tuple or None key

`runtime/prelude/_collections.py:1018` (pop), `1281` (copy), `1297, 1302` (move_to_end), `1338, 1382` (the iterator):
`raise KeyError(key)` where `Objects/odictobject.c` has `PyErr_SetObject(PyExc_KeyError, key)` (lines 1107, 1265, 1346,
1354, 1768, 1824), which spreads a tuple into the arguments and gives None no argument. Commit 52a3735.

```python
from collections import OrderedDict

cache: OrderedDict = OrderedDict()
cache[("user", 1)] = "a"
for attempt in (lambda: cache.move_to_end(("user", 2)), lambda: cache.pop(("user", 2)), lambda: cache.pop(None), lambda: cache.move_to_end(None, last=False)):
    try:
        attempt()
    except KeyError as e:
        print(repr(e), e.args, "[%s]" % e)
```

CPython:
```
KeyError('user', 2) ('user', 2) [('user', 2)]
KeyError('user', 2) ('user', 2) [('user', 2)]
KeyError() () []
KeyError() () []
```
Bella:
```
KeyError(('user', 2)) (('user', 2),) [('user', 2)]
KeyError(('user', 2)) (('user', 2),) [('user', 2)]
KeyError(None) (None,) [None]
KeyError(None) (None,) [None]
```

Cause: the C's quirk is the observable (D-08 keeps KeyError's key). `del od[k]` and `od[k]` are right: they go through
`_PyErr_SetKeyError`. Found by the random-operation run (`p11.py`: 3900 steps over OrderedDict and two subclasses, 20
differences, all this one).

### F17-10 (low): PEP 563 annotation strings come from `ast.unparse`, CPython's from `Python/ast_unparse.c`

`pipeline/l1/frontend.py:126, 294, 651`. Commits a24ecc0, 37c3487.

```python
from __future__ import annotations


def total(xs: list[int], limit: max(n for n in (1, 2)) = 2) -> sum(x for x in ()): ...
def key(order: lambda *parts: parts, by: lambda **kw: kw, only: lambda *, strict: strict) -> None: ...
def show(label: f"it's a \"{total}\"") -> None: ...


print(total.__annotations__)
print(key.__annotations__)
print(show.__annotations__)
```

CPython:
```
{'xs': 'list[int]', 'limit': 'max(n for n in (1, 2))', 'return': 'sum(x for x in ())'}
{'order': 'lambda*parts: parts', 'by': 'lambda**kw: kw', 'only': 'lambda*, strict: strict', 'return': 'None'}
{'label': 'f\'it\\\'s a "{total}"\'', 'return': 'None'}
```
Bella:
```
{'xs': 'list[int]', 'limit': 'max((n for n in (1, 2)))', 'return': 'sum((x for x in ()))'}
{'order': 'lambda *parts: parts', 'by': 'lambda **kw: kw', 'only': 'lambda *, strict: strict', 'return': 'None'}
{'label': 'f\'\'\'it\'s a "{total}"\'\'\'', 'return': 'None'}
```

Cause: the two unparsers differ in four places, found over 450 expressions (`p20.py`, `p22.py`): a call whose only
argument is a generator expression, a lambda whose first parameter is starred, an f-string holding both quote
characters, and an attribute of a bool constant (`True.real`, which Bella writes `True .real`). Everything else agreed,
numbers and nested f-strings included.

### F17-11 (low): a staged text's SyntaxWarning is issued at build time only; `compile()` replays its first outcome

`pipeline/staging/dryrun.py:74-81, 138-162` (the warning goes to the dry run's stderr; `_compiled.setdefault` at
`:154` and `:161` keeps the first outcome of a key), `runtime/src/staged.cpp` `b_compile` and `find_text` (nothing to
replay).

```python
import warnings

with warnings.catch_warnings(record=True) as seen:
    warnings.simplefilter("always")
    value = eval("1 is 1")
    code = compile("'\\d'", "<w>", "eval")
print(value, [(type(w.message).__name__, w.lineno) for w in seen])

src = "2 is 2"
first = compile(src, "<again>", "eval")
with warnings.catch_warnings():
    warnings.simplefilter("error")
    try:
        compile(src, "<again>", "eval")
        print("compiled")
    except SyntaxError as e:
        print("SyntaxError", e.msg)
```

CPython:
```
True [('SyntaxWarning', 1), ('SyntaxWarning', 1)]
SyntaxError "is" with 'int' literal. Did you mean "=="?
```
Bella:
```
True []
compiled
```

Cause: the outcome of a compile depends on the warning filters as well as on its key. (When the filter is "error" from
the first call on, the dry run records nothing and the binary stops by name, which is fine.)

### F17-12 (low): more places where a caller's str or tuple subclass is asked instead of read (RL-383 incomplete)

* `runtime/prelude/_csv.py:490`: the writer iterates a field with `for c in field` (RL-383 fixed the reader's line at
  `:296`); `:121` and `:492` ask `c in lineterminator`, so a lineterminator whose class defines `__contains__` is
  refused with ValueError "bad delimiter or lineterminator value" where CPython writes the row
  (`F17-12_csv_lineterminator.py`).
* `runtime/prelude/_json.py:528, 569, 650, 696`: the indent is built with `*` and `+` on the caller's object, and the
  separators are written as they are where the C's writer calls `PyObject_Str` on them.
* `runtime/prelude/_operator.py:420`: `attrgetter` calls `item.split(".")` and `"." in item`.
* `runtime/prelude/time.py:349`: `get_clock_info` asks `"\x00" in name` (RL-383 again).
* `runtime/prelude/math.py:997`: `dist` takes `len(p)` of a tuple subclass (`PyTuple_GET_SIZE` in the C).
* `runtime/src/types.cpp:2355`: `exc.args = t` keeps a tuple subclass (`PySequence_Tuple` makes an exact tuple, through
  the subclass's `__iter__`).
* `runtime/src/types.cpp:691-693`: `type(name, bases, {"__qualname__": s})` turns a str subclass into a str; CPython
  keeps the object.

```python
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
print(type(type("N", (), {"__qualname__": Shout("Q")}).__qualname__).__name__)
```

CPython:
```
'"a,b",plain\r\n'
[1!2] {"a"!1}
[
--1
]
5
True
5.0
tuple (1, 2)
Shout
```
Bella:
```
'<a,b>,<plain>\r\n'
[1;2] {"a"=1}
[radd1
]
0
ValueError embedded null character
ValueError both points must have the same number of dimensions
Point Point(x=1, y=2)
str
```

### F17-13 (low): `str.splitlines()` returns a str subclass's own object for a one-line text

`runtime/src/str.cpp:627-630`. Predates the range (80b148c); d9ff83f left it.

```python
class Tag(str):
    def __repr__(self) -> str:
        return "Tag(" + str.__repr__(self) + ")"


t = Tag("one line")
print(t.splitlines())
print(type(t.splitlines()[0]).__name__, t.splitlines()[0] is t)
print(type(t.splitlines(True)[0]).__name__, type(Tag("a\nb").splitlines()[0]).__name__)
```

CPython:
```
['one line']
str False
str str
```
Bella:
```
[Tag('one line')]
Tag True
Tag str
```

Cause: stringlib's `splitlines` appends the object itself only under `STRINGLIB_CHECK_EXACT`. Of 123 str operations
checked for the type they return (`p13.py`), this is the only one that differs; `format()`, `%`, `partition` and the
others that hand back a subclass's own object in CPython do so in Bella too.

### F17-14 (low, build): a long operator, `elif` or call chain ends the build with a RecursionError

`pipeline/l1/frontend.py` (the `ast.NodeVisitor` passes; first frame `desugar_several_targets`), no limit raised in
`pipeline/build.py` (`pipeline/l1/run.py:122` raises it for eval1 only).

```python
x = 1 + 1 + ... + 1        # 330 terms on one line
print(x)
```

CPython: `330`. Bella: a Python traceback from `build.py` ending `RecursionError: maximum recursion depth exceeded`,
exit 1, no `bella: refused`. 250 terms build; so do 250 `elif` branches, where 330 fail; `a.m().m()...` builds with
180 calls and fails with 250; a 500-term `and` and a 500-term string concatenation fail. Nesting that CPython refuses
("too many nested parentheses") is refused by name, correctly. A staged text reaches the same error in
`pipeline/l2/lower.py` (`eval("[" * 200 + "]" * 200)`, which CPython evaluates).

### F17-15 (low, build): the dry run dies on a `LookupError` of its own and the build goes on without it

`pipeline/staging/annotations.py:414` calls `ast.unparse` in the dry run's phase-1 configuration, where the
`unicode_escape` codec is blocked (`_ast_unparse.py:545` needs it for a backslash or control character in an
f-string); `pipeline/build.py:258-259` turns the dry run's failure into "no artefact".

```python
from __future__ import annotations

from dataclasses import dataclass


def render(x: int, fmt: f"\x1b[{x}m" = "") -> str:
    return fmt + str(x)


@dataclass
class Point:
    x: int
    y: int = 0


print(Point(1, 2), render(3), render.__annotations__["fmt"])
```

CPython: `Point(x=1, y=2) 3 f'\x1b[{x}m'`
Bella: the build prints a traceback (`LookupError: unknown encoding: unicode_escape`) and carries on; the binary then
stops with `bella: not implemented: E-01: exec at dataclasses:_FuncBuilder.add_fns_to_class of a text the dry run did
not stage`, exit 70.

Cause: a stop, so not a wrong answer, but the stop names a text the program does have a right to and hides the real
failure. A failed dry run should fail the build.

### F17-16 (low): the bootstrap modules below module level

`runtime/prelude/bootstrap.py:449` (`FrozenImporter`), `bootstrap_external.py` (`PathFinder`, `FileFinder`). Commits
cea5c1e, 5be74e4.

```python
import importlib.machinery as machinery
import sys

frozen = sys.modules["_frozen_importlib"]
print(hasattr(machinery.FrozenImporter, "find_spec"), hasattr(machinery.FrozenImporter, "get_code"), hasattr(machinery.PathFinder, "discover"))
print([n for n in ("SimpleNamespace", "GenericAlias", "Union", "_getstate") if hasattr(frozen, n)])
try:
    print(machinery.FrozenImporter.find_spec("_frozen_importlib").name)
except AttributeError as e:
    print("AttributeError", e.name)
```

CPython:
```
True True True
[]
_frozen_importlib
```
Bella:
```
False False False
['SimpleNamespace', 'GenericAlias', 'Union', '_getstate']
AttributeError find_spec
```

Cause: RL-399 gave the two modules names-table scopes, so a missing module-level name stops by name; a missing class
attribute (`FrozenImporter.find_spec`, `get_code`, `get_source`, `_resolve_filename`, `PathFinder.discover`,
`FileFinder.discover`, `_find_children`) is a plain AttributeError, and the prelude's other contents show in
`dir(_frozen_importlib)` (88 names CPython's module does not have; 25 of CPython's are absent, the module locks
among them).

### F17-17 (low): `time.gmtime` past year 2**31

`runtime/prelude/time.py:392`. Commit 9d2a4b1.

```python
import time

print(tuple(time.gmtime(67768036191676799)))
print(tuple(time.gmtime(67767976233532800)))
```

CPython:
```
(-2147481749, 12, 31, 23, 59, 59, 2, 365, 0)
(-2147483648, 1, 1, 0, 0, 0, 2, 1, 0)
```
Bella:
```
(2147485547, 12, 31, 23, 59, 59, 2, 365, 0)
(2147483648, 1, 1, 0, 0, 0, 2, 1, 0)
```

Cause: the C adds 1900 to `tm_year` in an `int`, and the pin wraps. `asctime` and `strftime` of the result then differ
too. Exotic; listed because the port follows the C elsewhere to this level (RL-378).

### F17-18 (low): `dict.copy` and `items ^ items` call `keys()` on an empty OrderedDict subclass

`runtime/src/set.cpp` `dictitems_xor` and the runtime's `dict_copy`; `copy_lock_held` in `Objects/dictobject.c`
returns a new dict for an empty one before it looks at `tp_iter`.

```python
from collections import OrderedDict


class D(OrderedDict):
    def keys(self):
        print("keys called")
        return super().keys()


d = D()
print(dict.copy(d), len(d.items() ^ {}.items()))
```

CPython: `{} 0`. Bella: `keys called` twice, then `{} 0`.

## Notes that are not findings

* `exec(source, globals=g, locals=l)` by keyword can never be staged: the dry run's hooks (`dryrun.py` `_exec`,
  `_eval`) take the namespaces positionally only, raise TypeError where 3.15's builtins accept the keywords, and the
  binary then stops by name. A stop, but one the hook's signature causes.
* Under `from __future__ import annotations` nothing else in the runtime's PEP 563 surface differed
  (`__annotations__` of functions, classes, modules, nested and conditional ones, setting and deleting, `__annotate__`,
  `annotationlib.get_annotations`).
* `sys.modules` at start-up lacks `time`, `marshal` and `zipimport`, which CPython has imported by then. Not chased.

## What matched CPython, by focus area

1. **Built-in subclass semantics.** List subclasses overriding `__iter__`, `__len__`, `__getitem__`, `__eq__`,
   `__lt__`, `__bool__`, `__contains__`, `__repr__`, `__str__`, `__hash__`, `__reversed__` through 124 consumers
   (`list`, `tuple`, `sorted`, `min`, `max`, `sum`, unpacking, `*args`, `str.join`, `bytes.join`, `+`, `extend`,
   slice assignment, `zip`, `map`, `dict`, `in`, `%`, `format`, `copy`, `__reduce_ex__`, `operator`, `itertools`);
   the same for dict subclasses (127 probes: `dict()`, `{**d}`, `f(**d)`, `update`, `|`, `json`, `copy`, `%(k)s`,
   `format_map`, `__missing__`, `type(n, b, d)`), tuple subclasses (90: `%`, `isinstance`, `except`, `startswith`,
   namedtuple) and str subclasses (74). The type each of 354 operations returns for a subclass of str, int, float,
   complex, tuple, list, dict and frozendict. 1685 probes of str, tuple, list, dict, int and float subclasses with
   overrides handed to builtins and to every prelude module, and 323 of a Markup-like class, StrEnum, IntEnum and
   IntFlag. Only F17-04, F17-05, F17-12, F17-13 came out of all that.
2. **OrderedDict.** 116 directed probes (order after `move_to_end` through every consumer, views, `|`, `copy`,
   `__reduce__`, mutation during iteration, `dict.*` methods called on one); 3900 random steps over OrderedDict and two
   subclasses that log every overridden method (identical call logs apart from F17-09 and F17-18); when keys and
   values die across 17 scenarios (identical; exit order is D-07).
3. **Staged compile.** `compile()`'s argument checks and their order, SyntaxError payloads of ten bad texts, code
   object equality, `TypeVar(bound="X")`, `Optional["X"]`, `ForwardRef("a | b").__forward_code__`, texts with the same
   dict for globals and locals, function and class bodies inside a text, a walrus in a comprehension. A text the dry
   run did not see always stopped by name; I found no way to make the table answer for another text.
4. **str beyond ASCII.** `lower`, `upper`, `title`, `casefold`, `swapcase`, `capitalize`, the eleven predicates,
   `split`, `strip`, `splitlines`, `repr`, `ascii`, `center`, `%r`, `format`, hashed per plane over every code point
   but the surrogates, and thirteen in-context tests per code point (final sigma before and after each, title after
   each, `islower`/`isupper`/`istitle` beside each): all 42 hashes equal. The derivations of the cased and
   case-ignorable sets in `tools/unicode_tables.py` are exact: I checked both against `handle_capital_sigma` and
   `do_title` by reading.
5. **Exception groups.** 195 probes: 26 argument shapes for both constructors, `repr` after the list is mutated,
   `split` and `subgroup` with 18 matchers and 13 invalid ones, `derive` overridden, absent and wrong, metadata and
   notes on the parts, depth 200, and `__reduce__`, `__setstate__` and `copy` of BaseException, ImportError,
   AttributeError, NameError, OSError, SyntaxError, StopIteration, SystemExit, UnicodeDecodeError. No difference.
6. **importlib.** 377 probes: `sys.modules` entries, `find_spec`, `import_module` (absolute and relative),
   `resolve_name`, `__import__` with levels and fromlists, error payloads (`name`, `path`, `name_from`),
   `spec_from_file_location`, `spec_from_loader`, `module_from_spec`, ModuleSpec, loaders' methods. Differences: D-16,
   D-20, F17-16.
7. **C-module ports.** struct, binascii, base64: 9879 probes (31 formats with some 47 values under six byte orders,
   `unpack` of 30 formats over 14 buffers, `pack_into`, `iter_unpack`, half-float rounding, base64 with and without
   strict mode over some 40 inputs), no difference. math: 18163 probes (44 one-argument functions over some 60
   values, 17 two-argument functions over 30 by 30), no difference beyond D-20's Decimal name. json, csv, bisect,
   heapq, zlib: 2911 probes (some 60 objects under 17 keyword sets, 100 texts to load, 20 rows and 41 lines under 21
   dialects, 33 invalid dialects), one difference (F17-05). time, random, statistics, contextvars, the digests,
   hmac: 850 probes, one difference (F17-17) beyond D-20.
8. **Dict views, iterators, PEP 563.** The views' set algebra in `set.cpp` read against `dictobject.c` and exercised
   in the OrderedDict runs: no defect. PEP 563: see F17-10 and the note above.

## What I did not get to

* `_opcode`, `_tokenize`, `_imp` called directly, `_warnings` beyond the registry and `catch_warnings`.
* The built-in iterators' methods other than `__next__` and `__iter__` (`__length_hint__`, `__reduce__`,
  `__setstate__` stop by name where I met them).
* zlib streams beyond the scenarios in `p10.py`; inputs past 4 GiB (RL-369).
* Surrogate code points in str's methods; `int()`/`float()` of non-ASCII text (a known gap).
* Threads: `_contextvars` and `_thread` under concurrency.
* `ListInstance` in `object.hpp` (deallocation order, the cycle collector's traversal): not examined.
* The conformance harness and the record guard (5c2b004, RL-400): not reviewed.
* The reference model, eval1 and eval2 as such: every probe ran compiled only.
