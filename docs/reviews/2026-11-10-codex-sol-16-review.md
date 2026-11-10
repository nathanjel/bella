Codex 6.1-sol, 2026-11-10, asked by the author. Verbatim. Tag A16 in the review log. Its range is `2223023..98afa38`: list
subclasses, the exception groups, importlib and the record guard; a focused review, seven findings, run in its own worktree
(`bella-a16`) at `98afa38`. Its probes (`a16-probes/`) stayed in that worktree.

---

Bella review A16 — 2223023..98afa38

Checked detached HEAD `98afa3849d2691766a9fa86931101faca664c4ba` in `/home/nathan/workspaces/nth/bella-a16`; `.venv/bin/python` reports CPython 3.15.2. Dependencies were installed with `uv sync --extra dev`.

Six runtime findings and one harness finding. Every minimal program below was copied to `prog.py` and run with `.venv/bin/python prog.py` and `uv run python pipeline/build.py --run prog.py`. Runtime findings exit 0 on both interpreters, with empty stderr; the wrong results are neither named refusals nor exit 70. Reproduction sources and exact captured results are in `a16-probes/A16-*.py` and `a16-probes/verified.json`.

**A16-01 — P2: Declined list arithmetic overrides fall through to the stored items**

[runtime/src/ops.cpp:257](/home/nathan/workspaces/nth/bella-a16/runtime/src/ops.cpp:257), [runtime/src/ops.cpp:287](/home/nathan/workspaces/nth/bella-a16/runtime/src/ops.cpp:287).

A list subclass whose __add__ or __mul__ returns NotImplemented must leave dispatch to the remaining slots and ultimately raise TypeError here. Bella falls back to the inherited list storage and silently returns a list.

Minimal program:

```python
class L(list):
    def __add__(self, other): return NotImplemented
    def __mul__(self, other): return NotImplemented
x = L([1])
for f in (lambda: x + [1], lambda: x * 2):
    try: print(f())
    except TypeError as e: print(type(e).__name__, str(e))
```

CPython stdout:

```text
TypeError unsupported operand type(s) for +: 'L' and 'list'
TypeError unsupported operand type(s) for *: 'L' and 'int'
```

Bella stdout:

```text
[1, 1]
[1, 1]
```

**A16-02 — P2: Callable list subclasses are misclassified, including exception-group predicates**

[runtime/src/call.cpp:1319](/home/nathan/workspaces/nth/bella-a16/runtime/src/call.cpp:1319), [runtime/src/types.cpp:2159](/home/nathan/workspaces/nth/bella-a16/runtime/src/types.cpp:2159).

is_callable only checks __call__ on Kind::Instance. ListInstance retains Kind::List, so callable() incorrectly returns False. The same check makes BaseExceptionGroup.subgroup/split reject a valid callable predicate; direct invocation of the object works.

Minimal program:

```python
class Predicate(list):
    def __call__(self, e): return isinstance(e, ValueError)
p = Predicate()
print(callable(p))
g = ExceptionGroup('g', [ValueError('v'), TypeError('t')])
try: print(g.subgroup(p).exceptions)
except TypeError as e: print(type(e).__name__, str(e))
```

CPython stdout:

```text
True
(ValueError('v'),)
```

Bella stdout:

```text
False
TypeError expected an exception type, a tuple of exception types, or a callable (other than a class)
```

**A16-03 — P2: Integer conversion ignores a list subclass's __index__**

[runtime/src/ops.cpp:744](/home/nathan/workspaces/nth/bella-a16/runtime/src/ops.cpp:744).

int_index_of restricts special-method lookup to is_heap_obj(), which excludes ListInstance. A valid list-subclass index is rejected with an ordinary TypeError instead of invoking its override.

Minimal program:

```python
class L(list):
    def __index__(self): return 2
try: print(range(L()))
except TypeError as e: print(type(e).__name__, str(e))
```

CPython stdout:

```text
range(0, 2)
```

Bella stdout:

```text
TypeError 'L' object cannot be interpreted as an integer
```

**A16-04 — P2: Sequence concatenation APIs bypass successful subclass overrides**

[runtime/src/ops.cpp:322](/home/nathan/workspaces/nth/bella-a16/runtime/src/ops.cpp:322).

The repeatable(s) branch enters the built-in sequence implementation before trying the subclass's __add__/__iadd__. _operator.concat and _operator.iconcat therefore read the list items instead of returning the overrides' answers. The public operator.concat/iconcat wrappers reproduce the same difference.

Minimal program:

```python
import _operator as operator
class L(list):
    def __add__(self, other): return 'add'
    def __iadd__(self, other): return 'iadd'
for f in (lambda: operator.concat(L([1]), [2]), lambda: operator.iconcat(L([1]), [2])):
    try: print(f())
    except TypeError as e: print(type(e).__name__, str(e))
```

CPython stdout:

```text
add
iadd
```

Bella stdout:

```text
[1, 2]
[1, 2]
```

**A16-05 — P2: find_frozen returns the lookup name instead of the original module name**

[runtime/prelude/_imp.py:121](/home/nathan/workspaces/nth/bella-a16/runtime/prelude/_imp.py:121).

Frozen bootstrap modules have original names distinct from their lookup names. The unconditional third tuple element loses this alias metadata.

Minimal program:

```python
import _imp
print(_imp.find_frozen('_frozen_importlib'))
print(_imp.find_frozen('_frozen_importlib_external'))
```

CPython stdout:

```text
(None, False, 'importlib._bootstrap')
(None, False, 'importlib._bootstrap_external')
```

Bella stdout:

```text
(None, False, '_frozen_importlib')
(None, False, '_frozen_importlib_external')
```

**A16-06 — P3: The external bootstrap exposes _imp as None**

[runtime/prelude/bootstrap_external.py:24](/home/nathan/workspaces/nth/bella-a16/runtime/prelude/bootstrap_external.py:24).

The placeholder is never replaced during startup. CPython exposes the initialized _imp module here; Bella exposes an approximate None value, without stopping by name.

Minimal program:

```python
import _imp
import _frozen_importlib_external as ext
print(ext._imp is _imp)
```

CPython stdout:

```text
True
```

Bella stdout:

```text
False
```

**A16-07 — P2: the record guard rejects ordinary output when the interpreter prefix contains spaces**

[conformance/harness.py:198](/home/nathan/workspaces/nth/bella-a16/conformance/harness.py:198).

`out.stdout.split()` separates paths on all whitespace. With a virtualenv named `build/a16 prefix`, `prefix` becomes a forbidden directory by itself. A case printing only that word is rejected although it leaks no path. Use line boundaries to preserve each complete prefix.

Minimal program (`conformance/cases/C-A16-record-probe.py`):

```python
print('prefix')
```

CPython stdout and Bella compiled stdout are both exactly:

```text
prefix
```

Both program runs exit 0 with empty stderr. The difference is in recording this valid output. Reproduce in this worktree:

```bash
cp a16-probes/record_case.py conformance/cases/C-A16-record-probe.py
.venv/bin/python -m venv --without-pip "build/a16 prefix"
.venv/bin/python conformance/harness.py record \
  --python "$PWD/build/a16 prefix/bin/python" --filter C-A16-record-probe
```

Bella harness: exit 1, empty stdout, stderr:

```text
record: C-A16-record-probe.py prints prefix, which is this machine's and not CI's: print a basename or a name instead
```

Control: the identical case recorded using `$PWD/.venv/bin/python` succeeds with exit 0:

```text
recorded C-A16-record-probe.py                            exit=0
1 cases recorded with CPython 3.15.2
```

Additional probes matched CPython for list override routing through reads/writes, truth, containment, iteration, unpacking, slice assignment, copying and explicit list methods; normal subclass finalization; exception-group construction with list/tuple subclasses and split metadata/notes; exception reduction/state; and function __module__ capture, including loader methods. This is a focused review, not exhaustive coverage.
