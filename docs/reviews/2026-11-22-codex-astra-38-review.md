Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-22, the cross-check the author asked for after each step. Verbatim. Tag A38 in the
review log. Its range is `b414387..7f7c267`, run non-interactively (standard input closed) in its own worktree (`bella-r38`) at `7f7c267`: the
frontend's name counter reset for each unit and the fixes of review A37 (RL-841 to RL-858). Its probes (`r38-probes/codex/`) stayed in that
worktree. 16 findings; each was run on both sides by the session before any verdict (review log, A38).

---

# Bella conformance review A38

Detached checkout `7f7c267`, range `b414387..7f7c267`. The probes are under `r38-probes/codex/`. For each row I ran `PYTHONHASHSEED=0 .venv/bin/python <probe>/prog.py <row>` and the binary printed by `./r38-build <probe>/prog.py` with the same row and seed. Runs had a 120-second timeout and an 8,000,000 KiB virtual-memory limit. The saved status files use shell exit status.

## A38-01 · High · A bound built-in stored as an initialiser receives an extra argument

`runtime/src/types.cpp:713`, in `type_call`. Reduced program for `slots/object-bound-p`:

```python
sink = []
class C: pass
C.__init__ = sink.append
try:
    print(type(C(1)).__name__)
except TypeError:
    print("TypeError")
```

CPython prints `C`. Bella prints `TypeError`. In `slots/object-bound-n`, change the call to `C()`. CPython prints `TypeError` and Bella prints `C`. The positional case also reproduces with a float subclass (`slots/float-bound-p`). Each output is a single newline-terminated line. All six runs have empty stderr and exit zero.

CPython calls the already-bound method with the constructor's arguments. Bella's built-in fast path supplies the new instance as well. With no constructor arguments the append succeeds in Bella, making this a silent side effect as well as a difference in which calls raise.

## A38-02 · High · A foreign initialiser runs on an incompatible receiver

`runtime/src/types.cpp:714` and `runtime/src/call.cpp:788`. In the A38-01 program change the assignment to `C.__init__ = list.__init__` and call `C()` (`slots/object-otherin-n`). CPython prints `TypeError`. Bella prints `C`. Both exit zero with empty stderr. CPython's wrapper checks that the receiver is a list. Bella dispatches directly to the built-in initialiser, bypassing that check. The same matrix includes abnormal exits on incompatible receivers. For example, `slots/int-otherin-p` has CPython stdout `TypeError\n` and status 0, versus empty stdout and status 139 for Bella. Both stderr files are empty.

## A38-03 · Medium · List and OSError argument checks read a displaced allocator wrapper

`runtime/src/call.cpp:791`. Row `slots/list-other-k`:

```python
class C(list): pass
C.__new__ = tuple.__new__
try:
    print(type(C(k=1)).__name__)
except TypeError:
    print("TypeError")
```

CPython prints `TypeError`. Bella prints `C`. Both have empty stderr and status 0. Installing the wrapper preserves the list allocator. Bella's class call accounts for this, but the keyword guard in `list_init_m` still compares the visible `__new__` attribute with list's wrapper.

The same stale comparison occurs in `runtime/src/types.cpp:2298`, in `oserror_use_init`. Minimal example:

```python
class C(OSError):
    def __init__(self, *a, **k): print(self.args, self.errno)
C.__new__ = tuple.__new__
try: C(2, 'old', tag=1)
except TypeError: print('TypeError')
```

CPython prints `() None`; Bella prints `TypeError`. CPython defers population of the exception fields to the custom initialiser. Bella takes the eager path. With positional arguments alone the custom initialiser runs on both sides but sees different initial state. In `state/os-pass` the five CPython lines are `init () None` three times with `() None` after the second and third call. Bella prints `TypeError LookupError NoneType 2`, then `init (1, 'initial') 1`, `(1, 'initial') 1`, and repeats those last two lines. `state/os-again` also shows that a call to the base initialiser changes the fields only on CPython. `state/block-pass` and `state/block-again` reproduce this over BlockingIOError. All exit zero with empty stderr. Further list cases are `slots/list-mixin-k` and `history/b-list-other-create`.

## A38-04 · High · FileIO omits close-on-exec handling for a custom opener

`runtime/prelude/_io.py:920` and `runtime/prelude/_io.py:927`. Reduced from `file/r-r+`:

```python
import io, os
def opener(path, flags):
    print(bool(flags & os.O_CLOEXEC))
    fd = os.open(path, os.O_RDWR)
    os.set_inheritable(fd, True)
    return fd
with io.FileIO('/dev/null') as f:
    f.__init__('/dev/null', 'r', opener=opener)
    print(os.get_inheritable(f.fileno()))
```

CPython prints `True` then `False`. Bella prints `False` then `True`. Each is on its own line. The full row repeats the observation for a third initialisation in mode `r+`. Rows `a-x`, `bb-+r`, `q-a`, `w-r`, `r-path` and `fd-w` also exercise the opener. All runs exit zero with empty stderr. The saved output includes the intervening FileIO field and method observations.

On this Linux build, CPython's `_io_FileIO___init___impl` adds `O_CLOEXEC` to the flags before calling the opener and clears inheritability on the returned descriptor even when the opener set it. Bella computes only access and creation flags and goes from validating the returned descriptor straight to stat. The descriptor remains inheritable across exec.

## A38-05 · Medium · _random.Random rejects a subclass keyword even with a distinct allocator

`runtime/prelude/_random.py:142`. Row `clinic/random-new`:

```python
import _random
class C(_random.Random):
    def __new__(cls, *args, **kw):
        return _random.Random.__new__(cls)
try:
    print(type(C(tag=1)).__name__)
except TypeError:
    print("TypeError")
```

CPython prints `C`. Bella prints `TypeError`. Deleting `C.__new__` just before the call gives the same difference (`clinic/random-del`). All four processes exit zero with empty stderr. CPython's keyword restriction depends on the allocator slot. The subclass installs the generic slot and retains it after deletion. Bella refuses every nonempty keyword dictionary in `_random.Random.__init__`.

## A38-06 · Medium · Sequence operations refuse the numeric methods of a frozendict subclass

`runtime/src/ops.cpp:343` (shared by `i_sequence_concat` and `i_sequence_repeat`). Reduced from `sequence/fd-add-concat`:

```python
import operator
class C(frozendict):
    def __add__(self, other): return 'z'
x = C()
try: print(operator.concat(x, x))
except TypeError: print('TypeError')
```

CPython prints `z`. Bella prints `TypeError`. With `__mul__` returning `'x'`, the encoder made by `_json.make_encoder(None,None,_json.encode_basestring,x,':',',',False,False,False)`, called with `(1,2)`, returns `('1',)` under CPython and raises TypeError under Bella. Rows `fd-add-concat`, `fd-mul-indent`, `fd-all-concat`, `fd-all-indent` have empty stderr and exit zero. CPython's `PySequence_Check` excludes dict subclasses but permits a frozendict subclass with a sequence item slot. Bella's sequence test excludes the dict storage kind before reaching the numeric fallback.

A third caller is TypeVar substitution (`substitution/fd-typevar-all`). With an empty frozendict subclass that defines `__add__` to return `('custom',)`, substituting for a TypeVar with a default prints `('custom',)` under CPython and `TypeError` under Bella. Both exit zero with empty stderr.

## A38-07 · Medium · Re-entering descriptor initialisation leaves metadata from the displaced callable

`runtime/prelude/builtins.py:552` and `runtime/prelude/builtins.py:614` (`_sm_set`, `_cm_set`). Reduced from `reinit/staticmethod-reenter`:

```python
def second(): pass
def last(): pass
class First:
    def __del__(self): s.__init__(last)
s = staticmethod(First())
s.__init__(second)
print(s.__func__.__name__, s.__name__)
```

CPython prints `last last`. Bella prints `last second`. Replacing staticmethod with classmethod produces the same difference. Both full rows then call the initialiser without arguments (both print `TypeError`), reinitialise it with `last`, and print the name again (CPython `last`, Bella `second`). All runs exit zero with empty stderr.

Installing the second callable releases the first, whose finaliser installs the third. CPython reads the descriptor's current callable after the release when copying metadata. Bella passes the outer call's saved argument to `_wraps`. Initialising with the current callable again takes the identity shortcut, preserving the stale name.

## A38-08 · Medium · The warning source file is closed with a wrapper construction error handled

`runtime/prelude/_warnings.py:362`. Row `handlers/warning-new`, reduced to its distinguishing callback:

```python
import _warnings, io, sys, warnings
raw = io.FileIO(__file__)
class Bin:
    def fileno(self): return raw.fileno()
    def close(self):
        print('binary close', type(sys.exception()).__name__)
        raise KeyError()
def fail(*args): raise ValueError()
del warnings._showwarnmsg
io.open = lambda *args: Bin()
io.TextIOWrapper = fail
try: raise LookupError()
except LookupError:
    _warnings.warn_explicit('a38', UserWarning, 'x.py', 1)
print('end')
```

CPython stdout is `binary close LookupError\nend\n`. Bella stdout is `binary close ValueError\nend\n`. Both write `x.py:1: UserWarning: a38\n` to stderr and exit zero. Both suppress the close's KeyError. CPython closes the binary after the failed wrapper call with the caller's handled exception visible. Bella calls the user-defined close inside the handler for the wrapper failure. The companion row `warning-read` fails later, in `readline`, and agrees.

A second handler in the same source-line lookup has the same effect. In `reenter/warning-path` (`runtime/prelude/_warnings.py:344`), replace `sys.path` with `['/one','/two']` and use an `io.open` that prints its filename and handled exception and always raises ValueError. Both runs initially print `open x.py LookupError`. CPython prints `open /one/x.py LookupError` and `open /two/x.py LookupError`; Bella prints `open /one/x.py ValueError` and `open /two/x.py ValueError`. Both then print `end`, give the same warning on stderr, and exit zero. Bella calls the fallback search inside the first open's handler.

## A38-09 · Medium · UnicodeDecodeError validates its source before converting the indices

`runtime/src/bytes.cpp:1510`. Row `exceptions/decode-both`, reduced:

```python
class Index:
    def __index__(self):
        print('index')
        raise LookupError()
e = UnicodeDecodeError('e', b'a', 1, 2, 'reason')
try: e.__init__('e', None, Index(), 2, 'reason')
except BaseException as exc: print(type(exc).__name__)
```

CPython prints `index` then `LookupError`. Bella prints just `TypeError`. The full row prints `1 2 reason b'a'` on both sides after the failure and after a third, valid call. Both have empty stderr and status zero. CPython's argument parser takes argument two as an arbitrary object in `UOnnU`. It calls the index conversions before checking whether that object supplies bytes. Bella checks the source type first, skipping the program's callback.

## A38-10 · Medium · FileIO calls subclass overrides while reading a path or formatting an invalid mode

`runtime/prelude/_io.py:854` (path's null-byte check) and `runtime/prelude/_io.py:896` (invalid mode). Both are reads of concrete bytes or characters in CPython. Reduced path row:

```python
import io
class Path(bytes):
    def __contains__(self, x):
        print('contains')
        raise ArithmeticError()
f = io.FileIO('/dev/null')
try:
    f.__init__(Path(b'/dev/null'))
    print('ok')
except BaseException as e: print(type(e).__name__)
print('closed', f.closed)
f.close()
```

For `fileargs/bytes`, CPython prints `ok\nclosed False\n`. Bella prints `contains\nArithmeticError\nclosed True\n`. Returning the same bytes subclass from a path-like object's `__fspath__` gives the same difference after an initial `path` line (`fileargs/path`). CPython checks the encoded path's storage for a null byte. Bella evaluates `0 in name`, dispatching to the override after the previous descriptor has been closed.

For `fileargs/invalid`, define `class Mode(str)` whose `__getitem__` prints `getitem` and raises LookupError. Call `f.__init__('/dev/null', Mode('z'))` in the same program. CPython prints `ValueError\nclosed True\n`. Bella prints `getitem\nLookupError\nclosed True\n`. The slice `mode[:200]` invokes user code while forming the diagnostic. All six runs exit zero with empty stderr.

## A38-11 · Medium · FileIO keeps the opener's returned int subclass through the name store

`runtime/prelude/_io.py:923`. Reduced from `opener/ok`:

```python
import io, os
f = io.FileIO('/dev/null')
class FD(int):
    def __del__(self): print(f.name)
def opener(path, flags): return FD(os.open('/dev/null', os.O_RDONLY))
f.__init__('/dev/zero', 'r', opener=opener)
f.close()
```

The finaliser sees `/dev/null` in CPython and `/dev/zero` in Bella. The full row also instruments the name setter and runs inside an outer LookupError handler:

```text
CPython                           Bella
drop False /dev/null LookupError  store /dev/null
store /dev/null                   drop False /dev/zero LookupError
done False /dev/zero              done False /dev/zero
```

If the name setter raises (`opener/failed-store`), CPython prints `drop False /dev/null LookupError` before `store /dev/null`. Bella prints `store /dev/null` then `drop True /dev/null LookupError`. Both end with `error ValueError` and `done True /dev/null`. All runs exit zero with empty stderr. CPython decrements the reference to the opener's result immediately after extracting its integer. Bella retains the result in the local `fdobj` through the remainder of initialisation, including closing the descriptor on failure.

## A38-12 · Medium · A failed regex substitution releases the input export before disposing of earlier replacements

`runtime/prelude/_sre.py:357`. Row `state/sre-fail`, reduced:

```python
import re
data = bytearray(b'ab')
class Part(bytes):
    def __del__(self):
        try: data.extend(b'z')
        except BufferError: pass
def replace(m):
    if m.start(): raise ArithmeticError()
    return Part(b'x')
try: re.sub(b'.', replace, data)
except ArithmeticError: pass
print(data)
```

CPython leaves the data at `bytearray(b'ab')`. Bella leaves it at `bytearray(b'abz')`. The full row prints `part LookupError` on both sides, then `held` on CPython and `released` on Bella. Both print `ArithmeticError LookupError NoneType 4`. After appending a further byte explicitly, they print `after bytearray(b'ab!')` and `after bytearray(b'abz!')` respectively. Both exit zero with empty stderr.

In CPython's `pattern_subx` error path, the partial output list is decremented before `state_fini` releases the input buffer. Bella unexports the input in `finally` while the partial output is still live. The control `state/sre-type`, which reaches the join before failing on an invalid replacement, agrees on both sides.

## A38-13 · Medium · I/O retry checks expose the caught OSError to errno conversion

`runtime/prelude/_io.py:296`, called from the OSError handlers. Row `reduced/13`:

```python
import io, sys
class E:
    def __index__(self):
        print(type(sys.exception()).__name__)
        return 4
class R(io.RawIOBase):
    once = True
    def read(self, n=-1):
        if self.once:
            self.once = False
            raise OSError(E(), 'io')
        return b''
try: raise LookupError()
except LookupError: R().readline()
```

CPython prints `LookupError`. Bella prints `OSError`. Both retry successfully, exit zero, and write nothing to stderr. All 18 `eintr` rows reproduce the callback difference across readline's peek and read, writelines, raw readall, buffered read and write, and text read, readline and write. In the `bad` rows the callback itself raises KeyError and both propagate the original OSError with LookupError as its context. CPython's `_PyIO_trap_eintr` saves the raised exception before converting the errno field with `PyLong_AsLongAndOverflow`. The prelude calls `_number_index` while handling that exception.

## A38-14 · Medium · Descriptor metadata survives into the next attribute lookup

`runtime/prelude/builtins.py:484`. Minimal form of `copyattr/static-new`:

```python
class V:
    def __del__(self): print('drop')
class Wrapped:
    @property
    def __module__(self): return V()
    @property
    def __name__(self): print('name'); return 'x'
class W(staticmethod):
    def __setattr__(self, n, v):
        if n != '__module__': super().__setattr__(n, v)
W(Wrapped())
```

CPython prints `drop` before `name`. Bella prints `name` before `drop`. The full probes print the first getter as well. CPython stdout is `module\ndrop LookupError\nname\n`, Bella's is `module\nname\ndrop LookupError\n`. Rows `{class,static}-{new,again,fail}` cover construction, reinitialisation, and failure of the next getter. The failing rows add `ValueError LookupError` on both sides. Every run has empty stderr and status zero. CPython's `functools_copy_attr` releases each fetched value immediately after the setter returns. Bella holds it in `value` while evaluating the next getter, even if the setter discarded it.

## A38-15 · Medium · A close result's finaliser can re-enter a buffered stream too early

`runtime/prelude/_io.py:1964`. Row `closevalue/writer`, reduced:

```python
import io
class Result:
    def __del__(self):
        try: print(s.close())
        except RuntimeError: print('RuntimeError')
class Raw(io.BytesIO):
    def close(self):
        super().close()
        return Result()
class W(io.BufferedWriter):
    def flush(self): raise KeyboardInterrupt()
s = W(Raw())
try: s.close()
except KeyboardInterrupt: pass
```

CPython's nested call raises RuntimeError. Bella's returns None. The full rows `writer`, `reader` and `random` print `drop LookupError`, then `nested RuntimeError` on CPython and `nested None` on Bella, then `KeyboardInterrupt LookupError` and `end` on both. All have empty stderr and exit zero. CPython clears the raw close's return value while still holding the buffered-stream lock when flush has failed. Bella clears the lock's owner in the finally block while `res` is live. Its finaliser can call close on the now-closed stream. The TextIOWrapper control agrees.

## A38-16 · Medium · A newline decoder appears uninitialised to finalisers during reinitialisation

`runtime/prelude/_io.py:2634`. Reduced from `newline/errors-newlines`:

```python
import io
class Errors:
    def __del__(self):
        try: print(repr(d.newlines))
        except ValueError: print('ValueError')
d = io.IncrementalNewlineDecoder(None, True, Errors())
d.decode('a\r\n', True)
d.__init__(None, False)
print(repr(d.newlines))
```

CPython prints `'\r\n'` then `None`. Bella prints `ValueError` then `None`. An old decoder's finaliser and an old errors object's finaliser both reproduce the difference. In the `{decoder,errors}-{decode,getstate,reset,setstate}` rows, CPython's first line is respectively `'x\n'`, `(b'', 0)`, `None`, and `None`. Bella's first line is always `ValueError`. All ten rows end with `None`, empty stderr, and status zero.

In CPython, the test for initialisation is that the struct's errors pointer is non-null. The new errors object is already installed when the displaced references are released. The old newline history is reset afterwards. Bella clears an additional readiness flag before replacing either field, so a finaliser sees an artificial uninitialised state.

## Evidence index

Each row below has six saved files under `r38-probes/codex/<probe>/<row>/`. Each probe has its own `prog.py`. The `reduced` probe runs the report examples for A38-01 through A38-13 independently. The other probes include the surrounding observations.

<details><summary>A38-01 · 73 differing rows</summary>

- **reduced** — `01`
- **slots** — `BufferedIOBase-bound-n`, `BufferedIOBase-bound-p`, `BufferedRWPair-bound-n`, `BufferedRWPair-bound-p`, `BufferedRandom-bound-n`, `BufferedRandom-bound-p`, `BufferedReader-bound-n`, `BufferedReader-bound-p`, `BufferedWriter-bound-n`, `BufferedWriter-bound-p`, `BytesIO-bound-n`, `BytesIO-bound-p`, `Exception-bound-n`, `Exception-bound-p`, `FileIO-bound-n`, `FileNotFoundError-bound-n`, `IOBase-bound-n`, `IOBase-bound-p`, `OSError-bound-n`, `OSError-bound-p`, `OrderedDict-bound-n`, `OrderedDict-bound-p`, `Random-bound-n`, `Random-bound-p`, `RawIOBase-bound-n`, `RawIOBase-bound-p`, `SimpleNamespace-bound-n`, `SimpleNamespace-bound-p`, `StringIO-bound-n`, `StringIO-bound-p`, `TextIOBase-bound-n`, `TextIOBase-bound-p`, `TextIOWrapper-bound-n`, `TextIOWrapper-bound-p`, `bytearray-bound-n`, `bytearray-bound-p`, `bytes-bound-n`, `bytes-bound-p`, `chain-bound-n`, `chain-bound-p`, `classmethod-bound-p`, `complex-bound-n`, `complex-bound-p`, `count-bound-n`, `count-bound-p`, `defaultdict-bound-n`, `defaultdict-bound-p`, `deque-bound-n`, `deque-bound-p`, `dict-bound-n`, `dict-bound-p`, `float-bound-n`, `float-bound-p`, `frozenset-bound-n`, `int-bound-n`, `int-bound-p`, `list-bound-n`, `list-bound-p`, `object-bound-n`, `object-bound-p`, `product-bound-n`, `property-bound-n`, `property-bound-p`, `repeat-bound-p`, `set-bound-n`, `set-bound-p`, `staticmethod-bound-p`, `str-bound-n`, `str-bound-p`, `tuple-bound-n`, `zip-bound-n`, `zip_longest-bound-n`

</details>

<details><summary>A38-02 · 105 differing rows</summary>

- **reduced** — `02`
- **slots** — `BufferedIOBase-otherin-k`, `BufferedIOBase-otherin-n`, `BufferedRWPair-otherin-k`, `BufferedRWPair-otherin-n`, `BufferedRWPair-otherin-p`, `BufferedRWPair-otherin-pk`, `BufferedRandom-otherin-k`, `BufferedRandom-otherin-n`, `BufferedRandom-otherin-p`, `BufferedRandom-otherin-pk`, `BufferedReader-otherin-k`, `BufferedReader-otherin-n`, `BufferedReader-otherin-p`, `BufferedReader-otherin-pk`, `BufferedWriter-otherin-k`, `BufferedWriter-otherin-n`, `BufferedWriter-otherin-p`, `BufferedWriter-otherin-pk`, `BytesIO-otherin-k`, `BytesIO-otherin-n`, `BytesIO-otherin-p`, `BytesIO-otherin-pk`, `Exception-otherin-k`, `Exception-otherin-n`, `Exception-otherin-p`, `Exception-otherin-pk`, `FileIO-otherin-k`, `FileIO-otherin-n`, `FileNotFoundError-otherin-k`, `FileNotFoundError-otherin-n`, `IOBase-otherin-k`, `IOBase-otherin-n`, `OSError-otherin-k`, `OSError-otherin-n`, `OSError-otherin-p`, `OSError-otherin-pk`, `OrderedDict-otherin-k`, `OrderedDict-otherin-n`, `Random-otherin-k`, `Random-otherin-n`, `Random-otherin-p`, `Random-otherin-pk`, `RawIOBase-otherin-k`, `RawIOBase-otherin-n`, `SimpleNamespace-otherin-k`, `SimpleNamespace-otherin-n`, `StringIO-otherin-k`, `StringIO-otherin-n`, `StringIO-otherin-p`, `StringIO-otherin-pk`, `TextIOBase-otherin-k`, `TextIOBase-otherin-n`, `TextIOWrapper-otherin-k`, `TextIOWrapper-otherin-n`, `TextIOWrapper-otherin-p`, `TextIOWrapper-otherin-pk`, `bytearray-otherin-k`, `bytearray-otherin-n`, `bytearray-otherin-p`, `bytearray-otherin-pk`, `bytes-otherin-n`, `bytes-otherin-p`, `chain-otherin-k`, `chain-otherin-n`, `chain-otherin-p`, `chain-otherin-pk`, `classmethod-otherin-p`, `complex-otherin-n`, `complex-otherin-p`, `count-otherin-n`, `count-otherin-p`, `defaultdict-otherin-k`, `defaultdict-otherin-n`, `deque-otherin-k`, `deque-otherin-n`, `deque-otherin-p`, `deque-otherin-pk`, `dict-otherin-k`, `dict-otherin-n`, `float-otherin-k`, `float-otherin-n`, `float-otherin-p`, `float-otherin-pk`, `frozenset-otherin-k`, `frozenset-otherin-n`, `int-otherin-n`, `int-otherin-p`, `object-otherin-k`, `object-otherin-n`, `product-otherin-n`, `property-otherin-k`, `property-otherin-n`, `property-otherin-p`, `property-otherin-pk`, `repeat-otherin-p`, `set-otherin-k`, `set-otherin-n`, `staticmethod-otherin-p`, `str-otherin-n`, `str-otherin-p`, `tuple-otherin-k`, `tuple-otherin-n`, `zip-otherin-n`, `zip_longest-otherin-n`

</details>

<details><summary>A38-03 · 9 differing rows</summary>

- **history** — `b-list-other-create`
- **reduced** — `03`, `03-os`
- **slots** — `list-mixin-k`, `list-other-k`
- **state** — `block-again`, `block-pass`, `os-again`, `os-pass`

</details>

<details><summary>A38-04 · 225 differing rows</summary>

- **file** — `a+-`, `a+-+`, `a+-++`, `a+-+ab`, `a+-+xb`, `a+-R`, `a+-a`, `a+-aa`, `a+-bb`, `a+-br`, `a+-bw+`, `a+-r`, `a+-rb`, `a+-rbbr`, `a+-rr`, `a+-rt`, `a+-rw`, `a+-rx`, `a+-u`, `a+-w`, `a+-wb+`, `a+-ww`, `a+-x`, `a+-xx`, `a+-☀`, `a-`, `a-+`, `a-++`, `a-+ab`, `a-+xb`, `a-R`, `a-a`, `a-aa`, `a-bb`, `a-br`, `a-bw+`, `a-r`, `a-rb`, `a-rbbr`, `a-rr`, `a-rt`, `a-rw`, `a-rx`, `a-u`, `a-w`, `a-wb+`, `a-ww`, `a-x`, `a-xx`, `a-☀`, `bb-+r`, `fd-+ab`, `fd-+xb`, `fd-a`, `fd-br`, `fd-bw+`, `fd-r`, `fd-rb`, `fd-w`, `fd-wb+`, `fd-x`, `path-+ab`, `path-+xb`, `path-a`, `path-br`, `path-bw+`, `path-r`, `path-rb`, `path-w`, `path-wb+`, `path-x`, `q-a`, `r+-`, `r+-+`, `r+-++`, `r+-+ab`, `r+-+xb`, `r+-R`, `r+-a`, `r+-aa`, `r+-bb`, `r+-br`, `r+-bw+`, `r+-r`, `r+-rb`, `r+-rbbr`, `r+-rr`, `r+-rt`, `r+-rw`, `r+-rx`, `r+-u`, `r+-w`, `r+-wb+`, `r+-ww`, `r+-x`, `r+-xx`, `r+-☀`, `r-`, `r-+`, `r-++`, `r-+ab`, `r-+xb`, `r-R`, `r-a`, `r-aa`, `r-bb`, `r-br`, `r-bw+`, `r-path`, `r-r`, `r-r+`, `r-rb`, `r-rbbr`, `r-rr`, `r-rt`, `r-rw`, `r-rx`, `r-u`, `r-w`, `r-wb+`, `r-ww`, `r-x`, `r-xx`, `r-☀`, `w+-`, `w+-+`, `w+-++`, `w+-+ab`, `w+-+xb`, `w+-R`, `w+-a`, `w+-aa`, `w+-bb`, `w+-br`, `w+-bw+`, `w+-r`, `w+-rb`, `w+-rbbr`, `w+-rr`, `w+-rt`, `w+-rw`, `w+-rx`, `w+-u`, `w+-w`, `w+-wb+`, `w+-ww`, `w+-x`, `w+-xx`, `w+-☀`, `w-`, `w-+`, `w-++`, `w-+ab`, `w-+xb`, `w-R`, `w-a`, `w-aa`, `w-bb`, `w-br`, `w-bw+`, `w-r`, `w-rb`, `w-rbbr`, `w-rr`, `w-rt`, `w-rw`, `w-rx`, `w-u`, `w-w`, `w-wb+`, `w-ww`, `w-x`, `w-xx`, `w-☀`, `x+-`, `x+-+`, `x+-++`, `x+-+ab`, `x+-+xb`, `x+-R`, `x+-a`, `x+-aa`, `x+-bb`, `x+-br`, `x+-bw+`, `x+-r`, `x+-rb`, `x+-rbbr`, `x+-rr`, `x+-rt`, `x+-rw`, `x+-rx`, `x+-u`, `x+-w`, `x+-wb+`, `x+-ww`, `x+-x`, `x+-xx`, `x+-☀`, `x-`, `x-+`, `x-++`, `x-+ab`, `x-+xb`, `x-R`, `x-a`, `x-aa`, `x-bb`, `x-br`, `x-bw+`, `x-r`, `x-rb`, `x-rbbr`, `x-rr`, `x-rt`, `x-rw`, `x-rx`, `x-u`, `x-w`, `x-wb+`, `x-ww`, `x-x`, `x-xx`, `x-☀`
- **reduced** — `04`

</details>

<details><summary>A38-05 · 17 differing rows</summary>

- **clinic** — `random-del`, `random-new`
- **history** — `r-Random-both-del`, `r-Random-both-restore`, `r-Random-both-same`, `r-Random-init-restore`, `r-Random-new-del`, `r-Random-new-restore`, `r-Random-new-same`, `r-Random-none-restore`, `r-Random-other-restore`, `r-Random-wrapper-restore`
- **reduced** — `05`
- **valid** — `rawrandom-cnw-kw`, `rawrandom-delnew-kw`, `rawrandom-new-kw`, `rawrandom-snw-kw`

</details>

<details><summary>A38-06 · 6 differing rows</summary>

- **reduced** — `06`
- **sequence** — `fd-add-concat`, `fd-all-concat`, `fd-all-indent`, `fd-mul-indent`
- **substitution** — `fd-typevar-all`

</details>

<details><summary>A38-07 · 3 differing rows</summary>

- **reduced** — `07`
- **reinit** — `classmethod-reenter`, `staticmethod-reenter`

</details>

<details><summary>A38-08 · 3 differing rows</summary>

- **handlers** — `warning-new`
- **reduced** — `08`
- **reenter** — `warning-path`

</details>

<details><summary>A38-09 · 2 differing rows</summary>

- **exceptions** — `decode-both`
- **reduced** — `09`

</details>

<details><summary>A38-10 · 4 differing rows</summary>

- **fileargs** — `bytes`, `invalid`, `path`
- **reduced** — `10`

</details>

<details><summary>A38-11 · 3 differing rows</summary>

- **opener** — `failed-store`, `ok`
- **reduced** — `11`

</details>

<details><summary>A38-12 · 2 differing rows</summary>

- **reduced** — `12`
- **state** — `sre-fail`

</details>

<details><summary>A38-13 · 19 differing rows</summary>

- **eintr** — `all-bad`, `all-ok`, `bread-bad`, `bread-ok`, `bwrite-bad`, `bwrite-ok`, `line-bad`, `line-ok`, `lines-bad`, `lines-ok`, `peek-bad`, `peek-ok`, `tline-bad`, `tline-ok`, `tread-bad`, `tread-ok`, `twrite-bad`, `twrite-ok`
- **reduced** — `13`

</details>

<details><summary>A38-14 · 6 differing rows</summary>

- **copyattr** — `class-again`, `class-fail`, `class-new`, `static-again`, `static-fail`, `static-new`

</details>

<details><summary>A38-15 · 3 differing rows</summary>

- **closevalue** — `random`, `reader`, `writer`

</details>

<details><summary>A38-16 · 10 differing rows</summary>

- **newline** — `decoder-decode`, `decoder-getstate`, `decoder-newlines`, `decoder-reset`, `decoder-setstate`, `errors-decode`, `errors-getstate`, `errors-newlines`, `errors-reset`, `errors-setstate`

</details>

## Coverage and matching observations

9,403 distinct process pairs across 29 probe programs. 8,788 matched stdout, stderr and status byte for byte. 490 reproduced the findings above, including reduced examples. 125 ended at an explicitly named Bella limitation. A match counts the observations printed by that row. The history probe prints several calls on one class in each process.

| Probe | Matched | Differed | Named stop |
|---|---:|---:|---:|
| alias | 1 | 0 | 0 |
| cachedclose | 6 | 0 | 0 |
| classnames | 2 | 0 | 1 |
| cleanup | 29 | 0 | 0 |
| clinic | 3 | 2 | 2 |
| closevalue | 1 | 3 | 0 |
| consumer | 24 | 0 | 0 |
| copyattr | 0 | 6 | 0 |
| eintr | 0 | 18 | 0 |
| exceptions | 18 | 1 | 0 |
| file | 30 | 224 | 0 |
| fileargs | 3 | 3 | 0 |
| guards | 20 | 0 | 0 |
| handlers | 10 | 1 | 0 |
| history | 3273 | 11 | 28 |
| names | 8 | 0 | 2 |
| newline | 0 | 10 | 0 |
| opener | 0 | 2 | 0 |
| reduced | 0 | 14 | 0 |
| reenter | 2 | 1 | 0 |
| reinit | 14 | 2 | 0 |
| sequence | 464 | 4 | 0 |
| slots | 3970 | 178 | 68 |
| staged | 2 | 0 | 3 |
| staged-text | 1 | 0 | 1 |
| state | 2 | 5 | 0 |
| streams | 30 | 0 | 0 |
| substitution | 59 | 1 | 0 |
| valid | 816 | 4 | 20 |

**Scope limits.** The slot suites distinguish construction-time definitions from later assignments, deletion, and restoring a wrapper. The shape tests include classmethod, staticmethod, Python functions, unrelated built-ins, inheritance, and exception subclasses. They use different argument corpora: `slots` uses a scalar, `valid` supplies type-appropriate arguments, and `history` also calls the object methods directly. This is broad empirical coverage, short of every Cartesian combination for every subclassable type. The handler and reinitialisation probes reach the named mechanisms above. They do not establish exhaustive coverage of every handler exit, every parse failure, or every method of every partially initialised object. Named-stop rows carry no conformance verdict.

**What matched.**

- **Cleanup and exception chains.** All 29 `cleanup` rows and all 24 `consumer` rows agreed. These include OrderedDict iterator lookup, Context.run, tee, groupby, zip_longest, accumulate, starmap, enumerate, zip, both sorts, dict.fromkeys, set.update, text and bytes join, print, json.dump, the CSV writer, struct.pack, and numeric conversion. The buffered, paired and text streams' close methods agreed on the ordinary two-error cases, including the second callback's handled exception and the propagated error's context, cause and traceback length. The close-result finaliser in A38-15 distinguishes the buffered streams.
- **Re-entry.** Both lru cache rows agreed when the evicted result's finaliser cleared and repopulated the same cache and then raised. Reversed, islice, batched and IOBase.close agreed on the KeyboardInterrupt and GeneratorExit rows. The import failure removed the replacement from sys.modules with `_initializing` still true, and reset state on exit. The zlib dictionary release, the tee re-entry check, the OrderedDict iterators' failed reductions, and the repr guard retries agreed.
- **Repeated initialisation.** All 30 `streams` rows agreed, including raw ability checks, tell and size failures, and the third initialisation. The probes also agreed for deque, defaultdict, OrderedDict, BytesIO, StringIO, SimpleNamespace, ordinary property reinitialisation, and the ordinary descriptor metadata copies in `reinit`. For FileIO, after removing the two observations of the custom opener in A38-04, every `file` row agreed on mode, readable, writable, seekable, closefd, name, tell, repr, and exceptions. The descriptor, path-like and invalid-mode cases have their own saved outputs.
- **Sequences.** The mapping classes agreed on bisect, AST observations, joins, struct arguments, JSON separators, operator index/count/length hint, and the OS argument checks in the exercised rows. The frozendict subclass accounted for all five differences in the sequence and substitution probes.
- **Generated names.** The two package modules agreed on computed values, local names, module directory entries, class dictionary keys, annotation evaluation, qualnames, and `co_varnames`, `co_cellvars`, and `co_freevars`. The generator's reduction refusal, custom class namespace stores, and traceback function names agreed where observed. A staged exec with an explicit namespace and a staged eval with explicit globals agreed. Importing one physical source file under two module names gave each module its own counter, functions, classes and type alias. Reusing the original import resumed its own counter. No discrepancy attributable to the per-unit name reset was observed.
