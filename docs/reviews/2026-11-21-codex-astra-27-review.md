Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-21, the cross-check the author asked for after each step. Verbatim. Tag A27 in the
review log. Its range is `369abde..ebf460e`, four commits, run non-interactively (standard input closed) in its own worktree (`bella-r27`) at
`ebf460e`: the bounded `lru_cache`'s links (RL-600) first, then the fixes of A26. Its probes (`r27-probes/codex/`) stayed in that worktree.
Seven findings; each program was run on both sides by the session before any verdict (review log, A27).

---

# A27 · CPython 3.15.2 conformance review

Detached ebf460e, range 369abde..ebf460e. Probe paths are relative to r27-probes/codex. Each pair preserves stdout, stderr and exit status separately.

## A27-01 · Medium · Failed insertion into a full cache reverses observable cleanup

`runtime/prelude/_functools.py:717`. A colliding key raises on the third comparison with the surviving entry, after the oldest entry has been removed. Both wrappers propagate ValueError and have one entry left. A handler can observe a different sequence of finalizers before it catches the exception.

Reproducer (insert/prog.py)

```python
import functools
class K:
    def __init__(self,n): self.n=n
    def __hash__(self): return 0
    def __eq__(self,o):
        if armed and self.n==1 and o.n==2:
            count.append(1)
            if len(count)==3: raise ValueError
        return self.n==o.n
    def __del__(self): print('key',self.n)
class R:
    def __init__(self,n): self.n=n
    def __del__(self): print('result',self.n)
@functools.lru_cache(2)
def f(k): return R(k.n)
armed=False
count=[]
f(K(0))
f(K(1))
armed=True
try: f(K(2))
except ValueError: print('caught',tuple(f.cache_info()))
f.cache_clear()
```

CPython stdout

```text
result 2
key 0
result 0
caught (0, 3, 2, 1)
key 2
key 1
result 1
```

Bella stdout

```text
result 0
key 0
result 2
caught (0, 3, 2, 1)
key 2
key 1
result 1
```

Both exit 0 with empty stderr. CPython’s bounded_lru_cache_update_lock_held explicitly releases the recycled link (including its new result), then oldkey, then oldresult on this error path. Bella reaches its explicit deletions only on success. Exception unwinding releases the saved old result and key while the new result is still held by the caller of _bounded_update.

## A27-02 · Medium · A program can replace the compiler’s warning function between two literals

`runtime/src/call.cpp:3536`. Put these files side by side and start prog.py. The local warnings module is imported while the first warning is displayed.

prog.py

```python
a='\q'
b='\z'
print('body')
```

warnings.py

```python
import _warnings
def replacement(*args): print('replacement',args[3])
_warnings.warn_explicit=replacement
```

CPython (exit 0), stdout then stderr. FILE stands for the absolute path to hook/prog.py.

```text
body
```

```text
FILE:1: SyntaxWarning: "\q" is an invalid escape sequence. Such sequences will not work in the future. Did you mean "\\q"? A raw string is also an option.
  a='\q'
FILE:2: SyntaxWarning: "\z" is an invalid escape sequence. Such sequences will not work in the future. Did you mean "\\z"? A raw string is also an option.
  b='\z'
```

Bella (exit 0), stdout then stderr. FILE stands for the absolute path to hook/prog.py.

```text
replacement 2
body
```

```text
FILE:1: SyntaxWarning: "\q" is an invalid escape sequence. Such sequences will not work in the future. Did you mean "\\q"? A raw string is also an option.
  a='\q'
```

Bella looks up the Python attribute _warnings.warn_explicit afresh for every recorded warning. CPython’s string parser calls PyErr_WarnExplicitObject directly (Parser/string_parser.c:90). Replacing the module attribute affects subsequent Python calls to it, but the parser still emits the second diagnostic.

## A27-03 · Medium · The cache constructor executes metaclass code to decide whether maxsize is an index

`runtime/prelude/_functools.py:537`. The object below has no index slot. The metaclass supplies an ordinary class attribute on demand.

```python
from _functools import _lru_cache_wrapper
class Meta(type):
    def __getattr__(cls,name):
        print('lookup',name)
        return 1
class Size(metaclass=Meta): pass
try: _lru_cache_wrapper(len, Size(), False, tuple)
except Exception as e: print(type(e).__name__,str(e))
```

CPython stdout

```text
TypeError maxsize should be integer or None
```

Bella stdout

```text
lookup __index__
TypeError 'Size' object cannot be interpreted as an integer
```

Both exit 0 with empty stderr. PyIndex_Check in lru_cache_new checks the numeric slot directly. Bella’s hasattr(type(maxsize_o), "__index__") invokes the metaclass, accepts its answer and only then asks _number_index to convert the value. This accounts for both the extra user call and the different TypeError.

Through public functools.lru_cache this can reject a valid size. This second reproducer (publicsize/prog.py) exits 0 with empty stderr on both sides. CPython stdout is `1` and Bella stdout is `ValueError class lookup`.

```python
from functools import lru_cache
class Meta(type):
    @property
    def __index__(cls):
        raise ValueError('class lookup')
class Size(int, metaclass=Meta): pass
try: print(lru_cache(Size(2))(len)('a'))
except Exception as e: print(type(e).__name__,str(e))
```

## A27-04 · Low · A refused literal echoes stale text if a startup warning changes the file

`runtime/src/call.cpp:3516`. In a fresh directory, create prog.py with the following generator. Put warnings.py beside it, build without PYTHONINTMAXSTRDIGITS, then run with PYTHONINTMAXSTRDIGITS=640. Restore the generated source before each side. The program body is never entered. The complete driver is echo/run.py (run it with python3 -I).

```python
from pathlib import Path
Path("prog.py").write_bytes(b"a='\\q'\nold=" + b"9" * 641 + b"\n")
```

warnings.py

```python
with open('prog.py', 'rb') as f:
    source = f.read()
with open('prog.py', 'wb') as f:
    f.write(source.replace(b'old=', b'new='))
```

Both exit 1 with empty stdout. Stderr below uses FILE for the absolute filename and N for exactly 641 nines. CPython prints

```text
FILE:1: SyntaxWarning: "\q" is an invalid escape sequence. Such sequences will not work in the future. Did you mean "\\q"? A raw string is also an option.
  a='\q'
  File "FILE", line 2
    new=N
SyntaxError: Exceeds the limit (640 digits) for integer string conversion: value has 641 digits; use sys.set_int_max_str_digits() to increase the limit - Consider hexadecimal for huge integer literals to avoid decimal conversion limits.
```

Bella prints the same five lines with the fourth replaced by

```text
    old=N
```

The warning leaves the digit limit and the literal untouched. CPython reads the source line from disk when it constructs the SyntaxError (Python/errors.c, err_programtext). Bella supplies literal.text from the build’s table. The differing text is in the SyntaxError diagnostic itself.

## A27-05 · Low · Valid warning categories leave a checkout-specific filename in the recording

`conformance/harness.py:72`. In mask/prog.py, pass the absolute path to the existing C-8-19 case as argv[1].

```python
import warnings,sys
class Notice(UserWarning): pass
for category in (Warning, Notice, UserWarning):
    warnings.warn_explicit('msg', category, sys.argv[1], 1)
```

CPython and Bella both exit 0 with empty stdout and identical stderr. Here DIR denotes the absolute conformance/cases directory and C denotes C-8-19_the_compilers_warnings_at_each_start.py.

```text
DIR/C:1: Warning: msg
  # clause: C-8-19
DIR/C:1: Notice: msg
  # clause: C-8-19
DIR/C:1: UserWarning: msg
  # clause: C-8-19
```

After passing each actual stream to mask_stderr, both first lines for Warning and Notice still begin with DIR/C. Only UserWarning becomes C. The regex requires at least one character before the literal suffix Warning. Warning itself and a warning subclass named Notice both miss. The machine_paths check in cmd_record consequently rejects an otherwise portable case.

## A27-06 · Medium · RL-600’s eviction-error row cannot detect a broken rollback

`pipeline/tests/test_review_2026_11_21.py:309` enables unconditional equality failure before looking up the incoming key. The first resident collides with that key, so the initial lookup raises before the miss counter advances, before the function runs, and before _extract or _pop_hashed. Even deleting the call to _prepend at runtime/prelude/_functools.py:708 would leave this test’s observation unchanged. The other RL-600 rows do not raise inside the pop.

This two-row reproducer (pop/prog.py) distinguishes the lookup failure from the intended eviction failure. Hitting a puts b first in eviction order while a still precedes b in the hash probe sequence. A comparison of a to b during the subsequent miss can therefore fail specifically inside the pop.

```python
from functools import lru_cache
class K:
    def __init__(self,n): self.n=n
    def __hash__(self): return 0
    def __eq__(self,other):
        if armed and self.n=='a' and other.n==target:
            print('raise',self.n,other.n)
            raise ValueError
        return self.n==other.n
@lru_cache(2)
def f(k): return k.n
a,b,c=K('a'),K('b'),K('c')
for target in ('c','b'):
    armed=False
    f(a); f(b); f(a)
    armed=True
    try: f(c)
    except ValueError: print('caught',tuple(f.cache_info()))
    armed=False
    f(c); f(a)
    print('after retry',tuple(f.cache_info()))
    f.cache_clear()
```

CPython and Bella stdout are identical, stderr is empty, and both exit 0.

```text
raise a c
caught (1, 2, 2, 2)
after retry (2, 3, 2, 2)
raise a b
caught (1, 3, 2, 2)
after retry (2, 4, 2, 2)
```

The miss count at the catch is 2 for a lookup failure and 3 for a pop failure. The final hit in the second row checks that rollback put b back as oldest, so retrying evicted b and kept a. The defect is in the regression test’s reach.

## A27-07 · Medium · A warning naming the cases directory compares equal to one with an empty filename

`conformance/harness.py:191`. Run mask/only/prog.py with the absolute cases directory including its trailing slash, then with the empty string as argv[1]. Both arguments were exercised on both engines.

```python
import sys, warnings
warnings.warn_explicit('msg', UserWarning, sys.argv[1], 1)
```

CPython and Bella each produced the following two distinct stderr streams, respectively (DIR denotes the absolute cases directory). All four runs exited 0 with empty stdout.

```text
DIR/:1: UserWarning: msg
```

```text
:1: UserWarning: msg
```

mask_stderr returned the second stream for all four. Thus a runner that loses the entire directory string would pass against the first reference. os.path.basename of the slash-terminated path is empty, and joining CASES to that empty basename reproduces the input, so the equality guard accepts it even though it has no filename. This is a controlled negative comparison of the harness. The two engines agree for each individual argument.

## Checks that agreed

I compared stdout and stderr as bytes and compared the recorded exit statuses. The paths below name the probe directories. The build-only command had a 600-second timeout. A build refusal has no executable to compare.

| Probes | Observations |
| --- | --- |
| `collide`, `pop` | The exact sequence of equality calls for collisions across insertion, hits and eviction agreed. A comparison failure specifically inside the pop restored the oldest entry. Retrying evicted the intended key. |
| `stress`, `mixed` | Every permutation of hits for capacities 1, 2 and 3 agreed through the next eviction and explicit wrapper destruction. For capacity 1,000 and 5,000 mixed calls, both counted 3,849 hits, 1,151 misses, 151 results finalized before destruction and 1,151 after it. The order-sensitive digest including those finalizers was 953028902. A second 5,000-miss sequence also agreed. |
| `reentry` | All 250 rows agreed, including the cache counters observed inside callbacks. The matrix varies capacity, callback, operation and comparison number. It includes recursive lookup of the same and other keys, clearing the cache, raising in the function/hash/comparison, deleting the global wrapper reference during a call, and key/result finalizers inspecting, clearing or repopulating the cache. |
| `surface`, `life` | Typed and untyped calls with 1, 1.0, True, int and str subclasses, unhashable lists and reordered keywords agreed. So did zero, negative, bool, unbounded and oversized maxsize, the public decorator’s rejection of a plain index-only size, cache_parameters, __wrapped__, object identity under both copy operations, dictionary attributes copied from the function, cached static/class methods and a cached property. A weakref callback and result finalizers ran in the same order when a suspended generator released its wrapper on close. Two wrappers returning each other agreed through explicit clearing. |
| `digits` | One build made with the digit-limit variable unset agreed at limits 640, 642, 651 and 660, including every diagnostic byte. The first long literal is in an f-string field. A shorter literal follows it. There are tokenizer warnings on both sides of another literal on one line, nested format fields with backslashes in f- and t-strings, and 20 later invalid escapes. Both reached the body at 660. |
| `path`, `path/run1` through `run6` | Main __file__, co_filename, inspect.getsourcefile, __spec__, loader.path, argv[0], sys.path[0], logging pathname, warnings.warn and both traceback frame paths agreed. Invocations included dot, dot-dot, doubled separators, an absolute path containing dot and dot-dot, a file symlink, a directory symlink, two working directories and a suffix-free Unicode name with a space in its alias. Each program deliberately ended with ValueError and status 1. Raw stderr differed only in the source and caret lines under traceback frames (D-06). |
| `encoding`, `earlybyte` | A mixed-line-ending Latin-1 main file and nine imported modules printed the same text. Inputs include cookies on lines 1, 2 and 3, LF, CRLF, CR and mixed separators, a form feed, blank line, shebang, Vim cookie, UTF-8 BOM and alternative spellings, and apparent cookies inside a string or following code. A separate Latin-1 main file had a non-ASCII first comment before its second-line cookie. |
| `variants` | Exact builds with warnings on and off initially named the same executable. After changing the source and rebuilding exact/on, the old off and lean executables still ran the old program byte-for-byte like its CPython reference. The new executable’s stdout, stderr and status matched the new source’s CPython run. |
| `invalid` | Under the 640-digit limit, CPython reported the later unterminated string or unmatched closing bracket in preference to the literal. With a later unexpected indent it reported the literal. All three emitted warnings from lines 1 and 3 first. The unrestricted build refused all three invalid files with status 70. It also gave named D-10 refusals for return, break and continue out of finally, and refused ordinary invalid syntax and Latin-1 bytes without a cookie. Unrestricted CPython ran the three finally cases with a warning and exit 0. |

The encoding cases sample the requested combinations across main and imported files. The mutually referencing wrappers were explicitly cleared, so that probe establishes no collection timing for an unreachable cycle. The metaclass probe in `ctor` stopped at Bella’s named phase-2 boundary. The two narrower reproducers for A27-03 both completed.
