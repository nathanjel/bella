Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-21, the cross-check the author asked for after each step. Verbatim. Tag A30 in the
review log. Its range is `b04274c..6ff3049`, run non-interactively (standard input closed) in its own worktree (`bella-r30`) at `6ff3049`: which
frames count toward the recursion limit and the special methods of A29's fixes (RL-628 to RL-638), the item iterators' own pair (RL-584), and
once more the native stack. Its probes (`r30-probes/codex/`) stayed in that worktree. Twelve findings; each program was run on both sides by
the session before any verdict (review log, A30).

---

# A30 · Bella conformance review

Detached 6ff3049, range b04274c..6ff3049, against CPython 3.15.2. Each row runs in a fresh process with `PYTHONHASHSEED=0`, a 120-second timeout and `ulimit -v 8000000`. The stack is 8192 KiB unless specified. From the checkout, run `.venv/bin/python r30-probes/codex/GROUP/prog.py ROW`, then `timeout 600 ./r30-build r30-probes/codex/GROUP/prog.py` and invoke the emitted binary with the same ROW. The corresponding GROUP/ROW directory holds both output streams and status bytes as decimal numbers.

## A30-01 · Medium · Copying a dict items iterator changes when a value dies

`runtime/src/ops.cpp:2087`. Reproduction row `items/dict-copy`. Reduced program:

```python
import copy
class Value:
    def __init__(self, i): self.i = i
    def __del__(self): print("del", self.i)
d = {k: Value(k) for k in range(3)}
it = iter(d.items())
obj = copy.copy(it)
d.clear()
print("clear")
del obj
print("before del it")
del it
print("after del it")
```

Both exit 0 with empty stderr. The copied iterator owns a list of the remaining items. CPython's temporary iterator in `dictiter_reduce` uses the original's reusable pair for the first item. Bella constructs an iterator with a fresh pair and copies its position, size and remaining length. Consequently the original still holds an empty pair when the copy dies.

| CPython stdout | Bella stdout |
|---|---|
| clear | clear |
| del 2 | del 2 |
| del 1 | del 1 |
| before del it | del 0 |
| del 0 | before del it |
| after del it | after del it |

## A30-02 · Medium · A metaclass can substitute a different filesystem path

`runtime/prelude/posix.py:481` and `:482`. Reproduction rows `lookup/mro-path` and `lookup/dict-path`. Both exit 0 with empty stderr. The former reduces to:

```python
import os
class Actual:
    def __fspath__(self): return '/dev/null'
class Fake:
    def __fspath__(self): return 'invented'
class M(type):
    @property
    def __mro__(cls):
        print('read mro')
        return (Fake, object)
class C(Actual, metaclass=M): pass
print(os.fspath(C()))
```

CPython prints `/dev/null`. Bella prints `read mro` and then `invented`. With a metaclass property named `__dict__` returning `vars(Fake)`, Bella prints `read dict` and then `invented`. CPython again prints only `/dev/null`. Bella's lookup reads the Python-visible MRO and calls `vars(klass)` for each entry. Either can invoke a metaclass property. CPython's `Modules/posixmodule.c:17382` searches the actual type using `_PyObject_LookupSpecial`.

The same observable extra property calls occur in the slot-presence tests at `runtime/prelude/_struct.py:53` and `runtime/prelude/time.py:76`. The `lookup/{mro,dict}-{pack,time}` rows give both classes an `__index__`. Both runtimes then use the genuine conversion, printing `b'\x01'` for packing or `1` for the seconds field, but only Bella prints the property's marker first. All four rows exit 0 with empty stderr.

## A30-03 · Medium · Recursive descriptor naming loses nearly the entire traceback

`runtime/src/types.cpp:882`, `runtime/src/types.cpp:3236`, `runtime/src/core.cpp:1092`. Reproduction row `notes/main`. Minimal recursive shape:

```python
import sys, traceback
class Descriptor:
    def __set_name__(self, owner, name): go()
d = Descriptor()
def go():
    global n
    n += 1
    class Local: x = d
for limit in (60, 150):
    for _ in range(2):
        n = 0
        sys.setrecursionlimit(limit)
        try: go()
        except RecursionError as e:
            sys.setrecursionlimit(1000)
            t, count = e.__traceback__, 0
            while t is not None:
                count += 1
                t = t.tb_next
            print(n, count, len(traceback.extract_tb(e.__traceback__)), len(e.__notes__))
```

| Limit | CPython stdout per run | Bella stdout per run |
|---|---|---|
| 60 | `30 60 60 29` | `30 3 3 29` |
| 150 | `75 150 150 74` | `75 3 3 74` |

Both repetitions give the displayed line. Both processes exit 0 with empty stderr. The raw traceback chain confirms that the loss occurs before formatting. While unwinding, Bella catches the exception to add the descriptor note. Its first optional lookup of `__notes__` encounters a missing attribute. The nested exception takes over the single in-flight exception pointer, which its destructor clears (`runtime/include/bella/runtime.hpp:312`). The outer C++ rethrow does not reinstall that pointer, and unwinding frame guards skip recording when it is empty. The original exception and its notes reach the caller.

## A30-04 · Medium · `operator.length_hint` binds the length descriptor twice and can lose the fallback

`runtime/prelude/_operator.py:264`. Reproduction rows `bind/value` and `bind/raise`, both exit 0 with empty stderr.

```python
import operator, sys
class Length:
    def __get__(self, obj, owner):
        print("bound")
        if sys.argv[1] == "raise": raise TypeError("len binding")
        return lambda: 2
class C:
    __len__ = Length()
    def __length_hint__(self): return 9
try: print(operator.length_hint(C()))
except Exception as e: print(type(e).__name__, e)
```

| Row | CPython stdout, in order | Bella stdout, in order |
|---|---|---|
| value | `bound`, `2` | `bound`, `bound`, `2` |
| raise | `bound`, `9` | `bound`, `TypeError len binding` |

CPython's `_PyObject_HasLen` checks for the slot without executing the descriptor. Its call to get the length handles a TypeError by trying the hint. Bella calls `_lookup_special` outside the TypeError handler for the presence check, then binds the same descriptor again inside `len(obj)`.

## A30-05 · Medium · Advancing a weak proxy binds the referent's next method twice

`runtime/prelude/_weakref.py:301`. Reproduction row `weaknext/descriptor`.

```python
import weakref
class Slot:
    def __get__(self, obj, cls):
        print("bound")
        return lambda: 7
class C: __next__ = Slot()
x = C()
print(next(weakref.proxy(x)))
```

CPython prints `bound` then `7`. Bella prints `bound` twice then `7`. Both exit 0 with empty stderr. CPython's proxy checks the iterator slot with `PyIter_Check` before calling it. Bella uses a binding lookup to test for the slot, discards the bound result, then calls `next(obj)`, which binds it again. The instance-only, metaclass-only, staticmethod, classmethod and class-level None controls in `weaknext` agree.

## A30-06 · Medium · Filesystem APIs propagate an exception raised while binding `__fspath__`

`runtime/prelude/posix.py:894` and `:919`, `runtime/prelude/_io.py:231`. Reproduction group `pathbind`, rows `bind-fspath`, `bind-stat`, `bind-chdir`, `bind-open`, `bind-fileio`.

```python
import os
class Slot:
    def __get__(self, obj, owner): raise KeyError("binding")
class C: __fspath__ = Slot()
try: os.fspath(C())
except Exception as e: print(type(e).__name__, str(e), type(e.__context__).__name__)
```

Bella prints `KeyError 'binding' NoneType` in all five rows. CPython prints the following single line for each. All exit 0 with empty stderr.

| API | CPython stdout |
|---|---|
| os.fspath, open, io.FileIO | `TypeError expected str, bytes or os.PathLike object, not C NoneType` |
| os.stat | `TypeError stat: path should be string, bytes, os.PathLike or integer, not C NoneType` |
| os.chdir | `TypeError chdir: path should be string, bytes, os.PathLike or integer, not C NoneType` |

CPython's `PyOS_FSPath` and its inlined path converter replace an error from the binding lookup with their argument TypeError (`Modules/posixmodule.c:17383` and `:1443`). Bella lets the descriptor exception escape from `_special`. The five `call-*` controls raise the KeyError from the already-bound method, where both sides propagate it.

`_locale.bindtextdomain` also uses this conversion. With the same raising descriptor, `localepath/binding` prints `TypeError expected str, bytes or os.PathLike object, not Plain` on CPython and `KeyError 'binding'` on Bella. The class is named Plain in that probe.

## A30-07 · Low · `bindtextdomain` calls an explicitly disabled path method

`runtime/prelude/_locale.py:242`. Reproduction row `localepath/none`, exit 0 and empty stderr on both sides.

```python
import _locale
class Plain: __fspath__ = None
try: _locale.bindtextdomain('bella-r30-test', Plain())
except Exception as e: print(type(e).__name__, e)
```

CPython prints `TypeError expected str, bytes or os.PathLike object, not Plain`. Bella prints `TypeError 'NoneType' object is not callable`. CPython's filesystem converter treats a slot bound to None as a rejected path argument. Bella tests the truth of the lookup-result tuple. The tuple `(None,)` passes, so the next line calls None. The instance-only, metaclass-only, staticmethod and classmethod rows for this API agree.

## A30-08 · Medium · An OrderedDict items iterator resumes after a failing key hash

`runtime/prelude/_collections.py:1433` (finding the current node) and `:1372` (fetching its value). Reproduction rows `odhash/1` and `odhash/2`.

```python
from collections import OrderedDict
import sys
calls, armed = 0, False
class K:
    def __hash__(self):
        global calls
        if armed:
            calls += 1
            if calls == int(sys.argv[1]): raise ValueError("hash")
        return 10
    def __del__(self): print("del key")
d = OrderedDict()
d[K()] = 'a'
d[1] = 'b'
it = iter(d.items())
del d
armed = True
for _ in range(4):
    try: print(next(it)[1])
    except Exception as e: print(type(e).__name__)
print("drop")
del it
```

| Row | CPython stdout, in order | Bella stdout, in order |
|---|---|---|
| 1 | ValueError, del key, StopIteration, StopIteration, StopIteration, drop | ValueError, a, b, del key, StopIteration, drop |
| 2 | ValueError, del key, StopIteration, StopIteration, StopIteration, drop | ValueError, b, del key, StopIteration, StopIteration, drop |

Both exit 0 with empty stderr. The first hash finds the current node. CPython clears its current key on failure, so the following advance releases the mapping and ends iteration. The second hash fetches the value after advancing the cursor. CPython clears both cursor and mapping on that error. Bella only clears those fields when the lookup returns its missing-value sentinel. An exception bypasses the cleanup in both places, leaving a retryable cursor, and the next call can yield items after CPython has finished.

## A30-09 · Medium · A path's `__class__` property can prevent opening it and produce a spurious warning

`runtime/prelude/_io.py:3554`, `:700` and `:703`. Reproduction group `fileclass`. The six rows change the property's answer and choose `open` or `io.FileIO`. The boolean/FileIO row reduces to:

```python
import io, warnings
class C:
    @property
    def __class__(self):
        print("read class")
        return bool
    def __fspath__(self): return "/dev/null"
with warnings.catch_warnings(record=True) as seen:
    warnings.simplefilter("always")
    try:
        with io.FileIO(C()) as f: print(f.read())
    except Exception as e: print(type(e).__name__, e)
    print([w.category.__name__ for w in seen])
```

CPython prints `b''` then `[]` in every row. All processes exit 0 with empty stderr. Bella stdout follows in line order:

| Property | Bella with io.FileIO | Bella with open |
|---|---|---|
| returns bool | `read class` twice, `TypeError 'C' object cannot be interpreted as an integer`, `['RuntimeWarning']` | same, with three `read class` lines |
| returns int | `read class` twice, `TypeError 'C' object cannot be interpreted as an integer`, `[]` | same, with three `read class` lines |
| raises ValueError("class") | `read class`, `ValueError class`, `[]` | identical to Bella with io.FileIO |

Bella's `isinstance` checks for bool and int allow the apparent `__class__` of an instance to participate. CPython checks the real boolean type and number/index slots, so it continues to the genuine path method without executing the property.

## A30-10 · Low · A non-callable `fileno` is reported as missing

`runtime/prelude/posix.py:874`. Reproduction row `ioattrs/fileno-none`.

```python
import os
class C: fileno = None
try: os.fsync(C())
except Exception as e: print(type(e).__name__, e)
```

CPython prints `TypeError 'NoneType' object is not callable`. Bella prints `TypeError argument must be an int, or have a fileno() method.`. Both exit 0 with empty stderr. CPython's `PyObject_AsFileDescriptor` uses ordinary attribute lookup and attempts to call any value it finds (`Objects/fileobject.c:185`). Bella uses None as its missing-attribute sentinel. The four other `fileno` rows agree.

## A30-11 · Low · RawIOBase.readall gives a different diagnostic for a non-callable read method

`runtime/prelude/_io.py:492`. Reproduction row `ioattrs/read-none`.

```python
import io
class S(io.RawIOBase): read = None
try: S().readall()
except Exception as e: print(type(e).__name__, e)
```

CPython prints `TypeError attribute of type 'NoneType' is not callable`. Bella prints `TypeError 'NoneType' object is not callable`. Both exit 0 with empty stderr. CPython uses `_PyObject_CallMethod` (`Modules/_io/iobase.c:980`), whose non-callable attribute diagnostic is in `Objects/call.c:621`. The prelude uses a Python method call. The instance-only, metaclass-only, staticmethod and classmethod controls agree.

## A30-12 · Medium · RawIOBase.readall abandons a partial read on EINTR

`runtime/prelude/_io.py:492`. Reproduction row `interrupted/eintr`.

```python
import errno, io
class S(io.RawIOBase):
    calls = 0
    def read(self, size):
        self.calls += 1
        if self.calls == 1: return b'a'
        if self.calls == 2: raise InterruptedError(errno.EINTR, 'interrupted')
        return b''
s = S()
try: print(s.readall())
except Exception as e: print(type(e).__name__, e.errno)
print(s.calls)
```

CPython prints `b'a'` then `3`. Bella prints `InterruptedError 4` then `2`. Both exit 0 with empty stderr. CPython checks `_PyIO_trap_eintr()` when the Python read callback raises and retries without losing the bytes already obtained (`Modules/_io/iobase.c:985`). The prelude propagates the first exception. The `einval` control raises the same Python exception class with errno 22 and both sides print `InterruptedError 22` then `2`.

## Coverage and matching results

The archive contains 1,085 paired process rows across 26 probe directories (27 build invocations, including the corrected I/O harness). In 995 pairs, stdout, stderr and exit status were all byte-identical. The other pairs include the findings above, controls for known deviations, and harness limitations. Row manifests are in each probe's `rows` file. `run.py` records timeout as 124 and signal exits as 128 plus the signal number. For deep groups, the output directory ends in the stack size in KiB.

* **Recursion.** The 40 `rec` rows all matched, including the four rejected recursion-limit values. The previous limit stayed at 1000 after 1 (RecursionError), −1 (ValueError), a float (TypeError) and an 81-bit integer (OverflowError). The generator send/throw/close rows each gave 30 calls and 60 traceback entries, then 75 calls and 150 entries. The same was true of unpacking a generator and recursive context-manager exit. The generator consumers, nested handlers, class bodies, numeric conversions, stream write method and every `reflected` row matched. The handler that tries to recurse again printed `59 2` twice then `149 2` twice on both sides.
* **Callbacks.** Tested metaclass prepare/new/init/call, special-method callbacks, colliding keys, copies and reductions, sorting, bisect, heapq, group operations, contextmanager and ExitStack, singledispatch, wraps, cached_property, regex substitution, format_map, translate, Template, JSON object_hook, ChainMap, UserDict and finalization. The largest traceback discrepancy was A30-03. The logging handler gave 9 and 22 calls, the signal handler 30 and 75, and the ABC subclass hook 15 and 38 on both sides. An installed atexit callback and the explicit exception-hook calls matched. A dataclass probe stopped during generated-method setup, so its unrelated callback rows were rerun in `hooks`. Async/thread execution, staged exec/eval and recursive execution of the private atexit drain have no conformance verdict here.
* **Imports (information only).** In the 60-module chains, both import spellings reached modules 9, 9, 24, 24 on CPython at limits 60 and 150. Bella reached 59, 59 and then all 60. Its final 0 counts newly executed module bodies on the cached repeat. Importing the module from its own body returned the same module on both sides. Recursing through cached `__import__` reached 59 and 149 calls on both. Through `importlib.import_module` the counts were 56 and 146 on CPython versus 59 and 149 on Bella.
* **Special methods and streams.** The `slots` group matched in all 120 rows. The operator sweep covered forward, reflected and in-place arithmetic, comparisons, truth, indexing, assignment, deletion, containment, sequence search and calls. Ten initial rows selected nonexistent operator spellings. Their corrected `ibit` replacements all matched. Converter controls covered index, iteration, length, hashing, numeric and path arguments across builtins, itertools, functools, collections, io, time, signal, random, struct, zlib, binascii, hashing and other modules in the manifest. The five context-key diagnostics differ only in addresses. All readinto, write, enter and exit rows in the corrected `ioattrs` group matched. These samples are not exhaustive for every entry point of every module.
* **Item lifetimes.** Of 110 ordinary mapping/iterator rows, 105 matched byte for byte. All five differences were A30-01, for dict, defaultdict, Counter, MappingProxyType and a dict subclass delegating `items()`. The tested OrderedDict copy and repeated reduce matched. Other matching rows include clearing or dropping the mapping while iterating, replacing values, break and an exception in the body, zip, tee, two iterators, sorted/list/dict construction, forward and reverse size changes, repeat advances after exhaustion or mutation, and OrderedDict move_to_end and popitem. The failing-key-hash probes that establish A30-08 were separate.
* **Native stack.** All 112 Bella deep-data runs exited 0, with no timeout, abort or segmentation fault at either stack size. Every 500,000-node finalizing chain reported 500,000 deaths. Releasing slotted, tuple, list, dict and mixed chains completed on both sides, and the weakly watched slotted head died with one callback. Tested walks included repr, str, formatting, tuple hashing and key lookup, equality, order, membership, index, JSON, heapq, bisect, sorting and nested iterators. The archive retains machine-dependent depth differences. At both stack sizes the 50,000-level deque repr raised RecursionError on both sides and subsequent release completed.
