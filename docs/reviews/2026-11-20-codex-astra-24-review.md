Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-20, asked by the author as the cross-check of each step from here on. Verbatim. Tag
A24 in the review log. Its range is `7a8e3f2..729cd7b`, run non-interactively (standard input closed) in its own worktree (`bella-r24`) at
`729cd7b`: the step that gives each declaration of a slot its own cell (RL-541, C-3-78) first, then the limit of digits for a main program's
literals (C-8-18) and the fixes of the review before. Its probes (`r24-probes/codex/`) stayed in that worktree. Eleven findings; each was
run on both sides by the session before any verdict (review log, A24).

---

# A24 · Bella conformance review

Range: `7a8e3f2..729cd7b`. Outputs below use CPython 3.15.2 and the detached checkout at 729cd7b.

## A24-01 · High · A slot that covers BaseException.args aborts class creation

`runtime/include/bella/object.hpp:950`. The class layout rejects a user slot whose name is in the native base-field table. CPython allocates a separate cell and keeps the exception arguments accessible through the base descriptor.

```python
class E(Exception):
    __slots__ = ("args",)
e = E(1)
e.args = 2
print(e.args, BaseException.args.__get__(e))
```

CPython prints `2 (1,)` and exits 0 with empty stderr. Bella prints nothing to stdout and exits 134 (SIGABRT). Its stderr is

```text
terminate called after throwing an instance of 'bella::ModelError'
  what():  'args' is a field of a built-in base
```

## A24-02 · Medium · Weakref callbacks precede user-slot finalizers on deque, partial and BytesIO subclasses

`runtime/include/bella/object.hpp:1996,2017`. The callback runs before either user value is released. CPython's subtype_dealloc clears weakrefs early only when its layout adds the weakref list. For these bases the base deallocator handles the list after the user slots are cleared. Bella delays weakrefs for set storage, but enters release_attributes with the default early-clear behavior for the three affected bases. The observable values in this probe occupy only slots declared by the program.

```python
from collections import deque
from weakref import ref
class Mark:
    def __init__(self, n):
        self.n = n
    def __del__(self):
        print(self.n)
class A(deque):
    __slots__ = ('x',)
class B(A):
    __slots__ = ('x',)
a = B()
B.x.__set__(a, Mark('sub'))
A.x.__set__(a, Mark('base'))
w = ref(a, lambda w: print('weak'))
del a
print(w() is None)
```

CPython stdout is `sub\nbase\nweak\nTrue\n`. Bella stdout is `weak\nsub\nbase\nTrue\n`. Both exit 0 with empty stderr. The same order difference occurred over functools.partial and io.BytesIO. The set, frozenset and random.Random controls matched.

## A24-03 · Medium · A secondary base's instance dictionary prevents a valid slot declaration

`runtime/src/types.cpp:756,762`. Bella checks all direct bases for an existing dictionary or weakref before allowing the explicit slot. CPython uses the selected layout base for this check, then accounts for secondary bases. Here A supplies the layout and M supplies a dictionary on a separate branch.

```python
class A:
    __slots__ = ('x',)
class M:
    pass
try:
    class D(A, M):
        __slots__ = ('x', '__dict__', '__weakref__')
    d = D()
    d.a = 3
    print('dict', d.a)
except Exception as e:
    print('dict', type(e).__name__, e)
```

CPython prints `dict 3`. Bella prints `dict TypeError __dict__ slot disallowed: we already got one`. Both exit 0 with empty stderr.

## A24-04 · Medium · Reduction accepts a slot-name list that accounts for only one of two cells

`runtime/prelude/bootstrap.py:2137`, `runtime/src/types.cpp:2997`. CPython's default reduction checks that the instance layout can be accounted for by the dictionary, weakref and reported slot names (Objects/typeobject.c:8009–8022). Both declarations of x contribute to that layout. Bella decides from the category of the first built-in base and skips the size check on a user class over object.

```python
import copyreg
class A:
    __slots__ = ('x',)
class B(A):
    __slots__ = ('x',)
    __slotnames__ = ['x']
b = B()
b.x = 2
try:
    print(b.__reduce_ex__(4)[2])
except TypeError as e:
    print(type(e).__name__, e)
```

CPython prints `TypeError cannot pickle 'B' object`. Bella prints `(None, {'x': 2})`. Both exit 0 with empty stderr.

## A24-05 · Medium · A direct member read attaches spurious AttributeError context

`runtime/src/types.cpp:234`. The direct member getter calls `raise_attribute_error` with the receiver and member name. CPython's `member_get` leaves the two structured fields unset. Ordinary attribute lookup supplies them separately.

```python
class D:
    __slots__ = ("x",)
class F(D):
    __slots__ = ("x",)
f = F()
try:
    D.x.__get__(f)
except AttributeError as e:
    print(e.name, e.obj is f)
```

CPython prints `None False`. Bella prints `x True`. Both exit 0 with empty stderr. A normal read of `f.x` on the same object gives `x True` on both.

## A24-06 · Low · A slot conflict masks an invalid slot item with the wrong exception class

`runtime/src/types.cpp:758,776`. Bella checks for a class-variable conflict as it visits each name. CPython validates all slot items in type_new_visit_slots before type_new_copy_slots checks any class variables.

```python
try:
    class Bad:
        __slots__ = ('x', 1)
        x = 1
except Exception as e:
    print('invalid', type(e).__name__)
```

CPython prints `invalid TypeError`. Bella prints `invalid ValueError`. Both exit 0 with empty stderr.

## A24-07 · Medium · A CR-delimited main file reports the wrong literal line

`pipeline/build.py:596`. The scanner passes raw bytes to `BytesIO.readline`, which only splits on LF. CPython accepts CR as a physical line ending. Under `PYTHONINTMAXSTRDIGITS=640` the compiled startup uses the scanner’s line 1 and echoes the preceding statement too.

Generate the exact program with `Path("cr.py").write_bytes(b'print("ran")\rx = ' + b'9' * 641 + b'\r')`. Both runs exit 1 with empty stdout. In stderr, writing N for 641 nines and FILE for the same absolute filename, CPython emits `  File "FILE", line 2\n    x = N\n`. Bella emits `  File "FILE", line 1\n    print("ran")\rx = N\r\n`. Both end with the same line:

```text
SyntaxError: Exceeds the limit (640 digits) for integer string conversion: value has 641 digits; use sys.set_int_max_str_digits() to increase the limit - Consider hexadecimal for huge integer literals to avoid decimal conversion limits.
```

## A24-08 · Medium · The oversized-literal diagnostic echoes more source than CPython

`pipeline/build.py:601`, `runtime/src/call.cpp:3491`. Bella keeps the whole physical line. CPython's err_programtext (Python/errors.c:2008) has a 1000-byte buffer and returns at most the first 999 bytes of the offending line. This affects ordinary long literals and shorter literals written with underscores.

Generate a source line with `line = "x = " + "_".join("4" * 701)` and write it followed by LF. Run at limit 700. In the measured probe this was line 15 of `places.py`. Both runs had empty stdout, exit 1 and the same stderr file header and final line. CPython’s middle line is exactly four spaces followed by `line[:999]` (1003 characters). Bella’s is four spaces followed by `line` (1409 characters). A separate 5001-digit literal reproduced the same echo discrepancy under the default 4300-digit limit and an explicit limit of 5000. The common final line for the 701-digit probe is

```text
SyntaxError: Exceeds the limit (700 digits) for integer string conversion: value has 701 digits; use sys.set_int_max_str_digits() to increase the limit - Consider hexadecimal for huge integer literals to avoid decimal conversion limits.
```

## A24-09 · Medium · A parser warning before the oversized literal disappears from the executable

`pipeline/build.py:629`, `runtime/src/call.cpp:3486`. The startup table records decimal literals and their locations. It carries no parser warnings from earlier source, so launching the built executable cannot replay the warning CPython issues before the SyntaxError.

Generate the exact main file with `Path("warnlit.py").write_text('x = "\\q"\nprint("ran")\nx = ' + '8'*641 + '\n')`. At limit 640 both runs exit 1, with empty stdout and identical SyntaxError reports naming line 3. CPython prefixes the following two stderr lines (FILE is the absolute path). Bella's executable omits them.

```text
FILE:1: SyntaxWarning: "\q" is an invalid escape sequence. Such sequences will not work in the future. Did you mean "\\q"? A raw string is also an option.
  x = "\q"
```

At limit 700 both print `ran` and exit 0. CPython still emits those two lines and the executable's stderr is empty. This compares the produced executable's process streams. The build itself also emits parser warnings.

## A24-10 · Medium (test) · The literal-limit regression test cannot fail on a wrong source echo

`pipeline/tests/test_start_up_environment.py:179,485`, `conformance/harness.py:181`. The differential assertion compares stderr after mask_stderr, which strips an indented source line following a File header. The later raw-stderr assertions inspect only CPython and check the line number and digit count. The same mask thus discards the very part of the syntax diagnostic that differs in A24-08.

Use the A24-08 program at limit 700. Both exit 1 with empty stdout. The measured CPython echo is 1003 characters and Bella’s is 1409. Applying the test's mask to those two captured stderr streams produced `raw False masked True` for the corresponding equality checks. This blind spot concerns a parser diagnostic about the main file.

## A24-11 · Medium · Hashing an iterator's result twice calls user code an extra time

`runtime/src/core.cpp:625`. CPython caches a successful tuple hash and resets the cache when enumerate or zip recycles the tuple. Bella recomputes the hash on each call, re-entering the element's Python method even while the same result is held.

```python
class V:
    def __hash__(self):
        print("hash")
        return 1
for v in (next(enumerate([V()])), next(zip([V()]))):
    print(hash(v) == hash(v))
```

CPython stdout is `hash\nTrue\nhash\nTrue\n`. Bella stdout is `hash\nhash\nTrue\nhash\nhash\nTrue\n`. Both exit 0 with empty stderr. The discrepancy is in observable calls, independent of the numeric hash.

## Checks that agreed

- C-3-78 matched byte for byte, including the private-name case, removing and restoring a member at a single read site, direct descriptor operations on unrelated objects, explicit object accessors, replacement of a live slot value and the order of release across two user classes.
- The three-declaration matrix with an intervening empty class printed `1 2 3` for object, list, dict, set, frozenset, float, str, complex, bytearray, Exception, OSError, AttributeError, deque, partial, BytesIO, StringIO, BufferedReader, TextIOWrapper and random.Random. The separate tuple hierarchy kept its tuple payload and both slot values.
- One read site over seven classes agreed before and after rebinding the most-derived member to the base member. Deleting it exposed an empty intermediate cell on both sides. Property, method and plain class-attribute collisions, including a replacement and restoration, produced identical stdout.
- Ordinary shallow and deep copy, getstate and protocol-4 reduction agreed with the default slot-name list. Both returned the visible slot and instance dict in state. Dataclass slot deduplication, subclass initialization under a metaclass, and user slots named __qualname__ and __classcell__ agreed.
- On LF input the limit checks selected the same first oversized number in a decorator, unevaluated type alias, annotation, continued statement, match pattern and f-string format spec. Long digit sequences in a comment, string, float, imaginary literal and all-zero integer produced no false rejection. A runtime call to disable the limit was too late to affect parsing on both sides. Runs covered unset, 0, 640, 700, 5000, an invalid setting and intermediate thresholds. Launches reused executables produced by r24-bella so the parser of the build host could not decide the result for the child process.
- C-3-77 and the batch of 26 program bodies from the previous review's regression table matched on stdout, stderr and exit status. The separate cross-type descriptor probe agreed on get, set and delete for partial.func, TextIOWrapper._finalizing and Struct.size. A slotted csv dialect subclass and the static types' module names agreed. Hashes after recycling an enumerate or zip result agreed with hashes of fresh equivalent tuples.
