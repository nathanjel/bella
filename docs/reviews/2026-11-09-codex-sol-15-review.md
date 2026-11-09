Codex 6.1-sol (high effort), 2026-11-09, asked by the author. Verbatim. Tag A15 in the review log. Its range is `46a5742..c8109ba`:
the C++ runtime and the build; a partial review, five findings, run in its own worktree (`bella-a15`) at `c8109ba`. A15 #5 is
G15 #16.

---

A15 partial review — c8109ba, CPython 3.15.2.

Fresh worktree: /home/nathan/workspaces/nth/bella-a15.
Runtime findings use uv run python pipeline/build.py --run prog.py after copying the reproducer to prog.py. A15-05 uses uv run python pipeline/staging/run.py a15-probes/A15-05.py.

A15-01 — P1: zlib silently truncates 4 GiB inputs

runtime/src/zlib.cpp:74; runtime/src/zlib.cpp:152

```python
import zlib
x = b'x' * 2**32
print(zlib.adler32(x), zlib.crc32(x))
print(len(zlib.compress(x)))
```

CPython stdout:
```text
2441832825 2363233923
4174513
```

Bella stdout:
```text
1 0
8
```

A15-02 — P2: reflected methods override a left dict view

runtime/src/ops.cpp:357

```python
class Other:
    def __iter__(self): return iter([2])
    def __ror__(self, other): return 99
print({1: 0}.keys() | Other())
```

CPython stdout:
```text
{1, 2}
```

Bella stdout:
```text
99
```

A15-03 — P2: items-view XOR hashes equal unhashable values before cancellation

runtime/src/set.cpp:441

```python
try:
    print({'a': []}.items() ^ {'a': []}.items())
except TypeError as e:
    print(type(e).__name__, str(e))
```

CPython stdout:
```text
set()
```

Bella stdout:
```text
TypeError cannot use 'tuple' as a set element (unhashable type: 'list')
```

A15-04 — P2: sys.excepthook ignores its explicit traceback

runtime/src/call.cpp:1167

```python
import io, sys
try:
    1 / 0
except ZeroDivisionError as e:
    tb = e.__traceback__
sys.stderr = io.StringIO()
sys.excepthook(ValueError, ValueError('new'), tb)
print('Traceback' in sys.stderr.getvalue())
```

CPython stdout:
```text
True
```

Bella stdout:
```text
False
```

A15-05 — P2: staging drops the star from future vararg annotations

pipeline/staging/annotations.py:413

```python
from __future__ import annotations
import annotationlib
def f(x: int, *args: *tuple[int, str]): pass
print(annotationlib.get_annotations(f, format=annotationlib.Format.STRING))
```

CPython stdout:
```text
{'x': 'int', 'args': '*tuple[int, str]'}
```

Bella stdout:
```text
```

Bella exit 70, stderr:
```text
bella: refused: [P2+] annotationlib: the build declined the entry point of f.__annotate__: MISMATCH STRING: CPython {'x': 'int', 'args': '*tuple[int, str]'}, evaluator {'x': 'int', 'args': 'tuple[int, str]'}
```
