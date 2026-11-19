# Bella review S22 (`3234866..bc3f700`): a swarm of Sonnet reviewers

- **Date:** 2026-11-19
- **Reviewer:** nine `claude-sonnet-5-5` agents, one per focus area, each independent of the others and of the codex review of the same range (A22)
- **Commit range reviewed:** `3234866..bc3f700`, in a worktree of its own at `bc3f700` (`bella-r22`)
- **Reference interpreter:** CPython 3.15.2 (the worktree's `.venv/bin/python`), its C source read from the 3.15.2 tarball

Asked for by the author on 2026-11-19 together with A22. The reports below are as the agents wrote them (`R22-sonnet-<focus>.md` in the worktree),
one section per focus; a report's own `##` headings are one level down here. Tag S22 in the review log, where every finding has its
reproduction and verdict. Probe paths (`r22-probes/...`) are the worktree's and do not outlive it.

## Focus `numbers`

Read: commit f656b1c (all of the diff in runtime/src, runtime/prelude/_struct.py, case C-6-23, test_deprecated_number_answers.py, DECISIONS entry), the current float.cpp, complex.cpp, ops.cpp (int_index_of, length_hint, check_sequence_key), types.cpp (number_long), format.cpp (format_long/format_float), imports.cpp, and prelude _struct.py, math.py, cmath.py, _collections.py, against CPython 3.15.2 abstract.c, floatobject.c, complexobject.c, _struct.c, mathmodule.c.
Ran: 13 probe programs (p1..p12, p3b) and 8 small reductions (m1..m8), about 5,900 rows (each row twice: filter "always" and filter "error"), about 24 builds. Five findings (all low), everything else compared clean.

#### struct.pack of a float or complex: an exception that is not an Exception escapes instead of struct.error
Severity: low (needs a `__float__`/`__complex__`/`__index__`-of-float conversion that raises SystemExit, KeyboardInterrupt or GeneratorExit; ordinary programs raise Exception subclasses, which are handled).
Where: runtime/prelude/_struct.py:294 and :301 (`except Exception:` in `_pack_item`, the 'float' and 'complex' kinds; the code RL-450 moved onto the runtime's `_as_double` and `_as_c_complex`).
Repro:
```python
import struct

class Boom:
    def __float__(self):
        raise SystemExit("from __float__")

try:
    struct.pack("<d", Boom())
except BaseException as e:
    print(type(e).__name__, e.args)
```
CPython: `error ('required argument is not a float',)` / Bella: `SystemExit ('from __float__',)`
(also KeyboardInterrupt for `<d`, `<f`, `<e`, `<D`, `<F` in the three byte orders: 36 rows of p5 differ only in this; for the complex formats the message is "required argument is not a complex".)
Why: `np_double`/`np_float`/`np_half`/`np_float_complex` replace any pending error (`PyErr_Occurred`) with `struct.error`; the prelude catches only `Exception`. Use `except BaseException` there (the `failed` flag after the handler already keeps the context right).

#### struct.pack("@P", x) with x an object whose __index__ gives an out-of-range int: struct.error instead of OverflowError
Severity: low (`P` with a non-int and a value beyond 64 bits).
Where: runtime/prelude/_struct.py:279-282 (`kind == "pointer"`), with `_pack_into` at :357-365.
Repro:
```python
import struct

class Huge:
    def __index__(self):
        return 10 ** 30

for v in (Huge(), 10 ** 30):
    try:
        struct.pack("@P", v)
    except BaseException as e:
        print(type(e).__name__, e.args)
```
CPython: `OverflowError ('Python int too large to convert to C unsigned long',)` then `error ('int too large to convert',)` / Bella: `error ('int too large to convert',)` twice.
Same with a value below -2**63 (CPython: `... to C long`); p7 rows "Big(1e30)", "Big(-1e30)", "Big(-2**63-1)", "Big(2**64)" `@P`.
Why: `np_void_p` calls `PyLong_AsVoidPtr`, which raises OverflowError; `s_pack_internal` turns it into struct.error only `if (PyLong_Check(v) && ...)`, i.e. when the argument itself is an int. The prelude raises struct.error itself in `_pack_item` for every `v`, so the `issubclass(type(v), int)` test in `_pack_into` is never reached for 'P'. It should raise OverflowError there ("... C unsigned long" for n >= 0, "... C long" for n < 0) and let `_pack_into` convert it for ints.

#### float(x) and float subclasses of a str subclass that defines __index__ parse the string and skip __index__ (no call, no warning)
Severity: low (a str subclass with `__index__` is unusual).
Where: runtime/src/float.cpp:218 (`float_new_impl`).
Repro:
```python
class StrIdx(str):
    def __index__(self):
        return 4

class Long(float):
    pass

print(float(StrIdx("12")), Long(StrIdx("12")))
```
CPython: `4.0 4.0` (and the DeprecationWarning for a strict-subclass `__index__` answer when it gives one) / Bella: `12.0 12.0`
Why: float_new_impl tests `PyUnicode_CheckExact(x)`; for a str subclass it goes to `PyNumber_Float`, which tries nb_float, then nb_index, and only then `PyFloat_FromString`. Bella's `is_kind(x, Kind::Str)` is true for the subclass instance too and only `__float__` is looked up. (`int(StrIdx("12"))` and `complex(StrIdx("12"))` are right: they matched in p3.)

#### collections.deque item get, set and delete convert the index twice (two __index__ calls, two warnings)
Severity: low (only observable with an `__index__` that has an effect, or a DeprecationWarning for its answer; ordinary ints are fine).
Where: runtime/src/ops.cpp:1496 `check_sequence_key`, called from `getitem` (:1544), `setitem` (:1667), `delitem` (:1683); the deque prelude (`_collections.py:527` `__getitem__`, `_ssize(args[1])`) then converts the original key again.
Repro:
```python
import collections, warnings

class Wide(int):
    pass

class Idx:
    calls = 0
    def __index__(self):
        Idx.calls += 1
        return Wide(1)

def get(d, i):
    return d[i]

def put(d, i):
    d[i] = 0

def rem(d, i):
    del d[i]

for name, op in [("get", get), ("set", put), ("del", rem)]:
    Idx.calls = 0
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        op(collections.deque([5, 6, 7]), Idx())
    print(name, Idx.calls, len(w))
```
(m7.py is this program.)
CPython: get/set/del each call `__index__` once, 1 warning / Bella: each calls it twice, 2 warnings (`deque get index calls 2 warnings 2`; the same for a deque subclass, and for a subclass with its own `__getitem__` only set and del).
Why: PyObject_GetItem converts the key with `PyNumber_AsSsize_t` and calls `sq_item` with the Py_ssize_t; the runtime converts for the IndexError rule and then calls the prelude's `__getitem__` wrapper with the original object, which converts again. (list, tuple, str, bytes, bytearray, range, structseq, re.Match, UserList all give 1 call in p12.)

#### Storing into a tuple, str, bytes, range, structseq or Match with an index-like key never calls the key's __index__
Severity: low (the exception is a TypeError in both; only an `__index__` with an effect, or the DeprecationWarning turned into an error, shows it).
Where: runtime/src/ops.cpp:1666-1679 (`setitem`; the TypeError at :1679).
Repro:
```python
import warnings

class Wide(int):
    pass

class Idx:
    def __index__(self):
        print("__index__ called")
        return Wide(1)

with warnings.catch_warnings():
    warnings.simplefilter("error")
    try:
        (5, 6, 7)[Idx()] = 0
    except BaseException as e:
        print(type(e).__name__, e.args[0][:40])
```
CPython: `__index__ called` then `DeprecationWarning Idx.__index__() must return an int, not Wi` (without the error filter: `__index__ called` once, then `TypeError 'tuple' object does not support item assignment`) / Bella: `TypeError 'tuple' object does not support item assignment`, `__index__` never called (m8: tuple, str, bytes, range; p12: also struct_time, stat_result, version_info, namedtuple, Match).
Why: PyObject_SetItem: for a type with tp_as_sequence and an index-like key it runs `PyNumber_AsSsize_t(key, PyExc_IndexError)` before `PySequence_SetItem` raises the TypeError. `delitem` does this right (1 call in both).

#### list(range(n)) for n beyond 63 bits runs without end instead of raising OverflowError
Severity: low to medium (an accidental `list(range(10**20))` is the kind of mistake a program meets; CPython answers at once, the compiled program computes until killed).
Where: runtime/src/ops.cpp:2222 `length_hint` (comment: "only an object of a Python class can tell it was asked"), used by `list_extend` (:2290) and so by list(), tuple(), `[*x]`, extend, sorted.
Repro:
```python
print("start", flush=True)
try:
    list(range(2 ** 63))
except OverflowError as e:
    print("OverflowError", e.args)
```
CPython: `start` then `OverflowError ('Python int too large to convert to C ssize_t',)` at once / Bella: `start`, then nothing: no exit in 60 s under `ulimit -v 4000000` (m5.py), and `list(range(10**400))` ran for more than ten minutes before I killed it (p3 row "RaisesOverflow range" had it by accident). `len(range(2**63))` is right (OverflowError).
Why: PyObject_LengthHint calls `__len__` of the object (range has one) and a non-TypeError (here OverflowError) propagates. The runtime asks only objects of Python classes. Only list() was run; `[*r]`, extend, sorted, tuple (CPython: MemoryError for tuple) are the same code path by reading and I did not run them under Bella.

#### datetime built from __index__/__float__ objects: the warning is attributed to the stdlib module (so the default filters hide it) and `date.fromordinal(x)` fails
Severity: low (a number object with `__index__` given to datetime; deviations.toml D-20 text says an unlisted _pydatetime/C difference is a defect).
Where: manifest.toml:125 (pure-Python `_pydatetime`: `_index = operator.index` in `_check_date_fields`, `_ord2ymd`, `fromtimestamp`).
Repro:
```python
import datetime

class Wide(int):
    pass

class Idx:
    def __index__(self):
        return Wide(5)

datetime.date(Idx(), 1, 1)         # at the program's line, default filters
print(datetime.date.fromordinal(Idx()))
```
CPython: the program's stderr shows `m7.py:N: DeprecationWarning: Idx.__index__() must return an int, not Wide. ...` for the call and for `fromordinal`, and fromordinal prints `0001-01-05` / Bella: no warning shown for `datetime.date(...)` or `datetime.time(...)` (it is attributed to `_pydatetime`'s line, e.g. L579, where the default filter ignores it; with the "always" filter the recorded `lineno` is 579, 580, 581, 592, 593, 1871 instead of the program's line), and `fromordinal` raises `TypeError unsupported operand type(s) for -=: 'Idx' and 'int'` (m7, p9 rows "datetime date/time/datetime/fromordinal/fromtimestamp"; also `timedelta(seconds=GF(), days=GI())` names the "days" component where CPython says "seconds", and the operand error says `'timedelta'` where CPython says `'datetime.timedelta'`).
Why: the C accelerator converts with `PyNumber_AsSsize_t`/`PyFloat_AsDouble` at the call (warning at the caller's line, `__index__` accepted for `fromordinal`); `_pydatetime` does the arithmetic in Python code.

### Checked and found clean
The commit's own claims held everywhere I pushed them. Values, types, warnings (category, text, line, count), the order of calls, and the result under an error filter matched CPython in:
- p1 (100 rows): int/float/complex subclasses that override `__index__`/`__int__`/`__float__`/`__complex__` (IntOv, FloatOv, PairOv) at 85 sites (subscripts, slices, range, chr, bytes, hex, `%c %d %x %f %s`, int(), float(), complex(), math, cmath, struct, round, ldexp, isqrt, fsum, operators); `Wide(GInt())`, `Long(GF())`, `Pair(GC())`, `Pair(1j, 2j)`, `complex.from_number`, `float.from_number`.
- p2 (172 rows): `__index__` in 120 sequence and module methods (bytearray, list, deque, itertools, random, math, bytes/str methods, os, time, cmath); state left behind after a DeprecationWarning error (struct.pack_into, bytearray.extend/slice/setitem/insert, list insert/imul/setslice/del, deque rotate); order of `__iter__` against the number's conversion (enumerate, islice, combinations, permutations, product, batched, tee).
- p3 + p3b (about 570 rows): 19 kinds of conversion objects (mixins in the MRO, `None` for the special methods, staticmethod, callable instances, functools.partial, wrong-typed and NotImplemented answers, answers that raise KeyError, KeyboardInterrupt, TypeError or OverflowError) at 31 sites each, in particular `__float__` raising OverflowError into math.log's `__index__` retry. Only the struct and str-subclass differences above.
- p4 (74 rows): traceback frames (names, lines) of the warning raised as an error at 18 sites including generators, class bodies, lambdas, comprehensions, random.py frames; default filters, once-per-line, `__warningregistry__` keys, `showwarning` arguments, message and module filters, warning attribute values, source line shown.
- p5 (2,400 rows): struct.pack for 20 codes x 5 byte orders x 24 values (GI, GInt, GF, GC, bool-answering, raising, huge, subclass instances, nan, inf, complex): only the BaseException and `@P` differences above.
- p6 (23 rows): result types of 190 operations on int/float/complex subclasses; 1,296 special-value combinations (0, -0, inf, -inf, nan) of complex(real, imag) with complex parts, in five forms, by checksum.
- p7 (808 rows): int and float subclass mixins in the other base order (`class A(int, Mix)`), Fraction, Decimal, str, None, list at 22 sites; out-of-range `__index__` answers (10**30, -10**30, 2**63, 2**64, -2**63-1) at 56 sites each for int and for an object. Only `@P` and Decimal's name in a TypeError message ('Decimal' vs 'decimal.Decimal': _pydecimal, not the commit). Note: CPython itself words `"x" * (2**63)` two ways ("cannot fit 'int' ..." and "Python int too large ...") depending on how often the same code object has run (adaptive specialisation); I did not count those rows.
- p8 (1,088 rows): struct e/f/d/F/D at range edges, ints and floats beyond float's range, nan payloads, bool, subclasses, in four byte orders; partial state of pack_into with a failing item (zeroing, earlier items written).
- p9 (122 rows): file, BytesIO, StringIO, os fd and metadata functions, re (match positions, group, sub count), json, heapq, Counter, bisect, textwrap, signal, time, itertools, operator, `L[i] += v` counts of `__index__`. Only the deque and datetime differences above (the two sys._getframe rows stop by name and were removed).
- p10 (375 rows): complex(a, b) for 13 x 13 argument kinds (GI, GInt, GF, GC, GCE, GCF, GCBad, 1j, Pair, str, None, 2, 2.5), keyword forms, complex subclasses with `__new__` and `__init__`, argument-count errors; C callers (map, sorted key, max/min key, filter, reduce, partial, accumulate, starmap, itemgetter, methodcaller) with the warning's file and line.
- p11 (27 rows): `warnings.showwarning` raising, nested warnings from the hook, stderr that raises or is None, regex and lineno filters, `__context__` of a warning error and of struct.error raised inside an except block (RL-448), once/module registries; stderr text matched too.
- p12 (35 rows): `__index__` call counts of 13 operations on 22 container kinds (list, tuple, deque, subclasses, bytes, str, UserList, range, structseq, Match, namedtuple); the deque and immutable-store differences above are all it found.

### Not checked
- `array`, `memoryview`, `resource`, `sys._getframe` (stop by name or later phase; the probes that used them were cut).
- Numerical results of libm functions, float formatting digits, `round()` rounding itself, `int()` of strings (outside the commit).
- The `%` format code path for `%b`/`__bytes__`; `str.format` with `__format__` of numeric subclasses beyond f-string and `format()` rows in p6.
- Decimal and Fraction beyond the conversion rows of p7 (they are pure-Python modules).
- Reference counting and use-after-free on the new `warn_ex` paths by running (read only: `Ref` holders are released by RAII on the throwing paths of `int_index_of`, `number_long`, `check_float_result`, `try_special`, and `new_impl`; none of those is noexcept).
- The other six reviewed commits of the range; the warnings machinery itself beyond what the number paths reach.

## Focus `replaced`

Read: commit f656b1c (diff of the 11 prelude files, RL-448 to RL-450, test_replaced_exceptions.py), every non-stub `except`/`raise` in runtime/prelude/*.py and runtime/replaced/*.py (AST scan: 62 raises inside handlers, 1 `from None` left), and the C of _struct.c, timemodule.c, pytime.c, _csv.c, _json.c, _functoolsmodule.c, itertoolsmodule.c, enumobject.c, structseq.c, bltinmodule.c (zip/map), Modules/_io/{bufferedio,iobase,fileio,textio,_iomodule}.c, Python/errors.c.
Ran: 8 probe programs (r22-probes/replaced/p1..p7 and p3b; p3 built twice), 10 builds, about 4,600 output lines, each site both alone and inside the program's own `except KeyError:` (p3 also under `warnings.simplefilter("error")`).

The 16 places RL-448 names are all fixed as claimed (every one of them matches CPython in my rows). The defects are in the same class one step to the side: close paths that chain with `raise e from exc`, a StopIteration handler in zip/map strict, `PyErr_Format` over a failed conversion in the buffered writer, and `except Exception` where the C swallows everything.

#### Buffered/TextIOWrapper/BufferedRWPair close and open()'s cleanup give `__cause__` and `__suppress_context__`, and no `__context__`
Severity: medium. Any program whose flush and close both fail (a full disk or broken pipe under a failing close) meets it; the uncaught traceback prints "The above exception was the direct cause" where CPython prints "During handling of the above exception, another exception occurred", and the "Exception ignored while finalizing file" report does the same.
Where: runtime/prelude/_io.py:1763 (Buffered close), :2008 (BufferedRWPair.close), :2919 (TextIOWrapper.close), :3546 (io.open's cleanup after a failed TextIOWrapper)
Repro (r22-probes/replaced/p6.py, p2.py, p4.py):
```python
import io
class Raw(io.RawIOBase):
    def writable(self): return True
    def write(self, b): raise OSError("write failed")
    def close(self): raise ValueError("close failed")
w = io.BufferedWriter(Raw())
w.write(b"x")
try:
    w.close()
except ValueError as e:
    print(type(e.__context__).__name__, type(e.__cause__).__name__, e.__suppress_context__)
```
CPython: `OSError NoneType False` / Bella: `NoneType OSError True`
The same difference for BufferedRWPair (writer.close raises OSError, reader.close raises ValueError), TextIOWrapper (buffer.flush and buffer.close both raise), and `open(fd, "r", encoding="x", opener=...)` whose cleanup close() fails (EBADF): CPython context LookupError, cause None; Bella context LookupError (implicit) and cause LookupError, suppress True. BufferedRandom/BufferedReader/BufferedWriter and KeyboardInterrupt/SystemExit variants alike (p2.py 20 rows, p4.py 12 rows).
Why: bufferedio.c:599, 2434, textio.c:3055, _iomodule.c:447 call `_PyErr_ChainExceptions1(exc)`, which does `PyException_SetContext(new, exc)` only. `raise e from exc` inside `except BaseException as e:` sets the cause and the flag, and because the handled exception at that point is `e` itself, no context is set (inside a caller's handler the context is that handler's exception, not `exc`). The test file has no row for any of these.

#### zip(strict=True) and map(strict=True) raise their ValueError inside `except StopIteration`, and pass the input's StopIteration value on
Severity: medium. zip(strict=True) mismatches are ordinary; an uncaught one prints a bogus "StopIteration ... During handling of the above exception" block on stderr.
Where: runtime/prelude/iterating.py:286-296 (zip.__next__), :336-342 (map.__next__), :244-255 (`_check_strict`)
Repro (p7.py, p6.py, p1.py rows `zip strict *`, `map strict`, `stopval:zip-strict`):
```python
names = ["a", "b", "c"]; values = [1, 2]
for n, v in zip(names, values, strict=True):
    print(n, v)
```
CPython stderr ends `ValueError: zip() argument 2 is shorter than argument 1` with no chained block / Bella stderr:
```
StopIteration

During handling of the above exception, another exception occurred:
Traceback ...
ValueError: zip() argument 2 is shorter than argument 1
```
Caught: CPython `e.__context__` None (inside `except KeyError:` it is the KeyError); Bella `StopIteration` (inside the handler the chain is [StopIteration, KeyError]).
Second defect, same code: when all inputs end together, `def g(): yield 1; return "val"`; `it = zip(g(), strict=True)`; `next(it); next(it)` raises `StopIteration()` in CPython (`args == ()`), `StopIteration('val')` in Bella; the same for `zip(g(), g(), strict=True)` and `map(f, g(), strict=True)`. (zip/map without strict pass the value on in both, as the C does.)
Why: bltinmodule.c zip_next/map_next `check:` does `PyErr_Clear()` and then `PyErr_Format(ValueError)`, or returns NULL with nothing set at the end. The prelude raises from inside the handler, and the bare `raise` after `_check_strict` re-raises the input's own exception object. It needs the `ended = True` pattern RL-448 used elsewhere, and `raise StopIteration` after the check.

#### BufferedWriter turns a bad `raw.write()` answer into the raw's own TypeError/ValueError; CPython replaces it with OSError "invalid length -1"
Severity: low to medium (a raw whose write() returns a non-int or an out-of-range int; an `__index__` that raises is swallowed in CPython).
Where: runtime/prelude/_io.py:1219 (`_bf_raw_write`, `n = _off_t(res)`)
Repro (p6.py, p4.py 24 rows):
```python
import io
class W(io.RawIOBase):
    def writable(self): return True
    def write(self, b): return "x"      # also 1.0, 2**70, an object whose __index__ raises ZeroDivisionError
w = io.BufferedWriter(W()); w.write(b"abc"); w.flush()
```
CPython: `OSError: raw write() returned invalid length -1 (should have been between 0 and 3)`, context None / Bella: `TypeError: 'str' object cannot be interpreted as an integer` (2**70: `ValueError: cannot fit 'int' into an offset-sized integer`; the raising `__index__`: its own ZeroDivisionError). Same through `write(b"x"*20)` and BufferedRandom.
Why: _bufferedwriter_raw_write does `n = PyNumber_AsSsize_t(res, PyExc_ValueError); Py_DECREF(res); if (n < 0 || n > len) { PyErr_Format(OSError, ...) }` with no PyErr_Occurred check, so any conversion failure (n is -1) is overwritten. The reader side (`_bufferedreader_raw_read`) does check and chains with FromCause, and matches in Bella.

#### BufferedRandom accepts a raw that is not seekable
Severity: low to medium (construction succeeds where CPython refuses; later seeks fail differently).
Where: runtime/prelude/_io.py:1555-1565 (`_bf_make_methods`' `__init__`: only readable/writable are checked)
Repro (p4.py, p6.py):
```python
import io
class NS(io.RawIOBase):
    def readable(self): return True
    def writable(self): return True
    def seekable(self): return False
io.BufferedRandom(NS())
```
CPython: `io.UnsupportedOperation: File or stream is not seekable.` / Bella: no exception.
Why: _io_BufferedRandom___init___impl calls `_PyIOBase_check_seekable(raw, Py_True)` first, then readable and writable.

#### RawIOBase.read()/readall() and BufferedReader raw answers: wrong exception class and wording for an int that does not fit
Severity: low.
Where: runtime/prelude/_io.py:465-468 (`_RawIOBase.read`, `got = _ssize(got)`), :1191 (`_bf_raw_read` uses `_off_t`)
Repro (p6.py, p4.py):
```python
import io
class RI(io.RawIOBase):
    def readinto(self, b): return 2**70
RI().read(3)
```
CPython: `ValueError: cannot fit 'int' into an index-sized integer` / Bella: `OverflowError: Python int too large to convert to C ssize_t` (so also `RI().readall()`). For BufferedReader over such a raw the OSError "raw readinto() failed" chain matches, but its cause says "offset-sized" where CPython says "index-sized", and for an `__index__` object CPython names the object's type (`cannot fit 'Idx' into an index-sized integer`), Bella says 'int'.
Why: _io__RawIOBase_read_impl and _bufferedreader_raw_read use `PyNumber_AsSsize_t(res, PyExc_ValueError)`; the prelude uses the Py_ssize_t clinic converter and the off_t one.

#### struct float/complex and time.clock_* converters let KeyboardInterrupt, SystemExit, GeneratorExit and BaseExceptionGroup through
Severity: low (a `__float__`/`__index__` that raises a BaseException that is not an Exception).
Where: runtime/prelude/_struct.py:294 and :301 (`except Exception`), runtime/prelude/time.py:143 (`_clockid`, `except Exception`)
Repro (p5.py 36 rows, p6.py):
```python
import struct
class KI:
    def __float__(self): raise KeyboardInterrupt("k")
struct.pack("<d", KI())
```
CPython: `struct.error: required argument is not a float` (and `<D`: "...not a complex"; `time.clock_gettime(KI())`: `TypeError: clk_id should be integer, not KI`) / Bella: `KeyboardInterrupt: k`. Same for SystemExit, GeneratorExit, BaseExceptionGroup, for `<f`, `<e`, `pack_into`, `time.clock_getres`.
Why: pack_halffloat/np_float etc. test `x == -1.0 && PyErr_Occurred()` and time_clockid_converter `clk_id == -1 && PyErr_Occurred()`: every pending error is replaced. (posix `_id` and itertools.islice already use BaseException and match.)

#### struct integer codes: an OverflowError raised by `__index__` itself, and 'P' with an out-of-range `__index__` object
Severity: low.
Where: runtime/prelude/_struct.py:260-265 (`_get_pylong`, `_index(value)` not wrapped), :279-283 (pointer branch)
Repro (p5.py 4 rows, p3.py rows `pack P Idx`, p6.py):
```python
import struct
class O:
    def __index__(self): raise OverflowError("o")
struct.pack("<i", O())
```
CPython: `struct.error: 'i' format requires -2147483648 <= number <= 2147483647` (also `<q`, `<b`, ...) / Bella: `OverflowError: o`.
And `struct.pack("P", Idx(2**70))` (an object, not an int, whose `__index__` returns 2**70): CPython `OverflowError: Python int too large to convert to C unsigned long` (for -2**70: "...to C long"), because pack_item converts the OverflowError only when `PyLong_Check(v)`; Bella: `struct.error: int too large to convert`.
Why: every np_*/bp_*/lp_* does `if (PyErr_ExceptionMatches(PyExc_OverflowError)) RANGE_ERROR`, whatever raised it.

#### Clinic-style argument errors name `NoneType`; time.clock_getres(huge int) has another message
Severity: low (wording).
Where: runtime/prelude/time.py:306 (`clock_getres` through `_c_int`), :318 (`pthread_getcpuclockid`), :348 (`get_clock_info`); runtime/prelude/_json.py:472-474 (`make_encoder`)
Repro (p3.py, p3b.py):
```python
import time, json.encoder
for f in (lambda: time.get_clock_info(None), lambda: time.pthread_getcpuclockid(None),
          lambda: json.encoder.c_make_encoder(None, 5, None, None, None, None, None, None, None),
          lambda: time.clock_getres(2**63)):
    try: f()
    except Exception as e: print(type(e).__name__, e)
```
CPython: `... must be str, not None` / `must be int, not None` / `make_encoder() argument 5 must be str, not None` / `OverflowError Python int too large to convert to C long` / Bella: `... not NoneType` (three rows) and `OverflowError signed integer is greater than maximum` (also for 2**64, 2**70, -2**63-1 and -2**70; clock_gettime agrees). `time.pthread_getcpuclockid(obj)` with an `__index__` that raises: CPython propagates its ZeroDivisionError; Bella raises TypeError "must be int, not <type>" (the prelude comment says "no __index__").
Why: `_PyArg_BadArgument` prints "None" for None; clock_getres uses the clinic int converter, whose overflow message is not the byte-array one.

#### BlockingIOError from a raw whose write() returns None has errno 11 always; CPython's is the errno left by the call
Severity: low (only a Python-level raw; a real non-blocking FileIO gives EAGAIN in both).
Where: runtime/prelude/_io.py:1237-1238, 1440-1443 (`_EAGAIN`)
Repro (p4.py 6 rows): `io.BufferedWriter(Raw(), buffer_size=8).write(b"abc"); w.flush()` where `Raw.write` returns None. CPython `BlockingIOError (0, 'write could not complete without blocking', 0)` / Bella `(11, ...)`.
Why: `_set_BlockingIOError` passes the C `errno` (`errno = errnum` captured after the call), which for a Python raw is whatever the interpreter left, usually 0.

### Checked and found clean
- RL-448's sixteen places and the other 11 sites of test_replaced_exceptions.py: context chain, cause, flag, args, alone and inside `except KeyError:` (p1/p3/p3b, about 330 rows).
- StopIteration end values: 31 iterators built over a generator that returns "val" (accumulate, batched, chain, chain.from_iterable, compress both inputs, cycle, dropwhile, takewhile, filterfalse, groupby, islice x2, pairwise, starmap, tee, zip_longest x2, zip, map, filter, enumerate, iter(callable), iter(seq), reversed, csv.reader, ...): only the strict zip/map rows differ (p1, 62 lines).
- csv (31 rows incl. writer(None), non-callable write, reader end, strict, field limit, dialect errors), functools (reduce, cmp_to_key K, lru_cache, partial: 18 rows), iterating/enumerate/reversed/iter (25 rows), itertools argument errors (70 rows): identical.
- struct: 47 format codes x 45 values (ints at every boundary, floats, strings, `__index__`/`__float__`/`__complex__` objects with wrong, subclass and raising answers), pack_into/unpack_from/iter_unpack/calcsize/Struct errors, plus the DeprecationWarning count and the error-filter run: identical except the two struct findings above (about 2,100 rows x 3 modes).
- time: gmtime, localtime, ctime, sleep, clock_gettime(_ns), clock_getres, pthread_getcpuclockid, mktime, asctime, strftime, struct_time, get_clock_info, clock_settime(_ns) over 40 values each; structseq constructors (time.struct_time, os.stat_result, os.terminal_size, sys.version_info, os.uname_result, raising and StopIteration iterables): identical except the wording rows above.
- posix: os.chown uid/gid converter (34 values x 2), posix_spawn env/file_actions/argv/setsigmask/scheduler (20 rows), execve, putenv, setgroups, sched_setaffinity, fspath, sysconf, confstr, pathconf, waitstatus_to_exitcode, utime, urandom and others (about 40 rows): identical.
- json scanner/decoder/encoder (50 rows incl. StopIteration(idx), hooks that raise, deep nesting, notes "when serializing ... item"): identical apart from the RecursionError message (C: "Stack overflow (used 8156 kB) while decoding ...", not portable) and the make_encoder wording above.
- _io: IOBase.close (flush fails / setattr fails: 6 rows) and FileIO.close with a bad fd (6 rows) chain as CPython does; BufferedReader/Writer/Random raw.seek and raw.tell answers (str, float, big, `__index__`, raising: 36 rows); raw.readinto answers for read/read1/peek/readall/readline (about 50 rows, except the two findings); BufferedRWPair with a raw whose close raises (6 rows, except the chain finding).
- Swallow width: nine exception classes (KeyboardInterrupt, SystemExit, GeneratorExit, MemoryError, ZeroDivisionError, StopIteration, BaseExceptionGroup, OverflowError, RecursionError) through 53 sites each (p5, 954 lines): identical except the struct/time rows above. itertools.islice/count arguments, reversed, iter(callable), csv writerow/reader, reduce, chain, operator.indexOf/countOf/contains/length_hint, posix_spawn, structseq, batched, pairwise, tee, accumulate, groupby, cycle, zip_longest, json dumps with a raising default: identical.

### Not checked
- TextIOWrapper.tell's decoder setstate chain (textio.c:3275), FileIO's open-error close (fileio.c:536), `_io` `__del__` unraisable paths and ResourceWarning-as-error finalizers.
- `_rw_forward`'s AttributeError branch (prelude line 1919): I found no way for a program to reach it (BufferedRWPair always holds Buffered objects); `time.strptime` (stops by name: `_strptime` not imported); memoryview rows (stop by name).
- `_warnings.py`, importlib's source in bootstrap.py/bootstrap_external.py, runtime/replaced/*.py, `_collections`, `_sre`, `math` handlers: read for the `from None`/chain class only, not probed.
- Real-file/non-blocking descriptor behaviour of BufferedWriter (only Python-level raws were used).

## Focus `generators`

R22-sonnet-generators.md (S22, focus generators)
Read: commit 560041e (diff and files), generator.cpp, runtime.hpp PyError, core.cpp arrive/record_frame, DECISIONS C-3-75, RL-451/452, test_generators.py last two programs, CPython genobject.c, errors.c, intrinsics.c. Ran 10 probe programs (r22-probes/generators/p1..p10, about 17 builds), about 480 rows, each against CPython 3.15.2.

#### throw(cls, value) ignores the metaclass's __subclasscheck__
Severity: low (needs an exception class whose metaclass defines __subclasscheck__; rare, but the result is a wrong exception type and a missing exception).
Where: runtime/src/generator.cpp:128 (`is_subclass(type_of(val), ...)` in `exception_of`), at bc3f700
Repro:
```python
class Meta(type):
    def __subclasscheck__(cls, sub):
        return True
class M(Exception, metaclass=Meta): pass
def catcher():
    while True:
        try:
            yield
        except BaseException as e:
            yield e
g = catcher(); next(g)
r = g.throw(M, ValueError("v"))
print(type(r).__name__, r.args)

class Meta2(type):
    def __subclasscheck__(cls, sub):
        print("subclasscheck called"); return False
class M2(Exception, metaclass=Meta2): pass
g = catcher(); next(g)
r = g.throw(M2, M2("v"))
print(type(r).__name__, r.args)
```
CPython: `ValueError ('v',)`, then `subclasscheck called` and `M2 (M2('v'),)` / Bella: `M (ValueError('v'),)`, then no call and `M2 ('v',)`.
Also, if the metaclass's __subclasscheck__ raises (`lambda c, s: 1/0`), CPython throws the ZeroDivisionError into the generator (traceback `catcher`, `<lambda>`); Bella throws the class instance as if the check were fine.
Why: PyErr_NormalizeException decides with `PyObject_IsSubclass(inclass, type)`, which honours `__subclasscheck__`; Bella calls the internal `is_subclass`. When the check says yes, CPython uses the value itself as the exception (and its class); when it says no it calls the class with the value.

#### The generator is not "executing" while throw() makes the exception from a class, so __init__/__new__ can re-enter it
Severity: low to medium (needs an exception class whose constructor touches the generator being thrown into, or inspects gi_running; but the outcome is a corrupted state, not just a wrong value).
Where: runtime/src/generator.cpp:105-141 and 160-165 (`exception_of` / `set_exception_pending` run while `g->state` is still Created/Suspended); in the delegating branch the state is put back to Suspended before `set_exception_pending` (line ~179).
Repro:
```python
class Advance(ValueError):
    def __init__(self, *a):
        try:
            next(gg)
        except BaseException as e:
            print("next in init ->", type(e).__name__, e)
def g4():
    try:
        yield 1
    except ValueError:
        print("g4 handler")
        yield "handled"
    yield "after handler"
gg = g4(); next(gg)
try:
    print("throw ->", gg.throw(Advance))
except BaseException as e:
    print("raised", type(e).__name__)
print("next ->", next(gg, "exhausted"))
```
CPython: `next in init -> ValueError generator already executing`, `g4 handler`, `throw -> handled`, `next -> after handler`.
Bella: no "next in init" line (next(gg) succeeded and advanced the generator past the try), then `raised Advance`, `next -> exhausted` (the pending Advance was then thrown into a generator that had moved on, and it died with it).
A simpler row: `class Peek(Exception): def __init__(self): print(gg.gi_running, gg.gi_suspended)` prints `True False` in CPython (also for a not-started generator), `False True` in Bella. A `close()` called from `__init__` also succeeds in Bella (CPython: ValueError generator already executing) and the thrown exception then goes into a closed generator and escapes to the caller instead of being caught by the generator's `except`.
Why: `_gen_throw` sets FRAME_EXECUTING by CAS before `throw_here`/`gen_set_exception` and restores the old state if that fails; Bella creates the exception with the state unchanged. Should set `g->state = Executing` around `exception_of` (restoring on failure), as in the delegating branch of `_gen_throw` (the Finished state is the one case where CPython does not set it).

#### throw(cls, value) when the class returns an instance of another class: CPython constructs twice, Bella once
Severity: low (a class whose __new__ returns an instance of a subclass or of another exception class; side effects of __new__/__call__ run twice in CPython).
Where: runtime/src/generator.cpp:97-115, 118-141 (`create_exception`, `exception_of`).
Repro:
```python
class Base(Exception):
    def __new__(cls, *a):
        print("Base.__new__", cls.__name__, [type(x).__name__ for x in a])
        if cls is Base:
            return Sub(*a)
        return super().__new__(cls, *a)
class Sub(Base): pass
def catcher():
    while True:
        try:
            yield
        except BaseException as e:
            yield e
g = catcher(); next(g)
r = g.throw(Base, "x")
print(type(r).__name__, r.args)
```
CPython: `Base.__new__ Base ['Sub']`, `Base.__new__ Sub ['Sub']`, `Sub (Sub('x'),)` / Bella: no print lines before the result, `Sub ('x',)`. (The same with `throw(Base)` -> `Sub(Sub(),)` vs `Sub()`; with a metaclass `__call__` returning `ValueError("from meta", a)`: CPython `ValueError('from meta', (ValueError('from meta', ()),))`, Bella `ValueError('from meta', ())`. With the class thrown into a finished generator too.)
Why: PyErr_NormalizeException leaves `type` as the class passed when the value was not an instance (the `inclass != type` branch runs only when it was); then PyErr_Restore sees `type != Py_TYPE(value)` and calls `_PyErr_CreateException(type, value)` a second time with the first result as the argument. `exception_of` should repeat the creation when `type_of(exc) != typ` (and only then). The generator does not need to be consulted: this is `gen_set_exception`'s PyErr_Restore step.

#### A `close` attribute of a `yield from` target that raises (not AttributeError) is raised by close()/throw(GeneratorExit); CPython reports it as unraisable and goes on
Severity: low (an object with a property `close` that raises, as a yield from target).
Where: runtime/src/generator.cpp:155-161 (`close_iter`, `optional_getattr`).
Repro:
```python
class BadClose:
    def __iter__(self): return self
    def __next__(self): return 1
    @property
    def close(self): raise RuntimeError("close attr")
def deleg(x):
    yield from x
g = deleg(BadClose()); next(g)
print("close ->", g.close())
g = deleg(BadClose()); next(g)
try:
    g.throw(GeneratorExit)
except BaseException as e:
    print(type(e).__name__)
```
CPython: stderr `Exception ignored while closing generator <__main__.BadClose object at 0x...>:` with the RuntimeError traceback, stdout `close -> None`, then `GeneratorExit`. / Bella: `RuntimeError: close attr` raised by close() (uncaught here, exit 1); throw(GeneratorExit) raises the RuntimeError too.
Why: gen_close_iter calls `PyObject_GetOptionalAttr(yf, close, &meth)`; a failure (not AttributeError) is `PyErr_FormatUnraisable("Exception ignored while closing generator %R", yf)` and the code continues with meth == NULL, returning 0. Bella lets the exception out.

#### An error from getting the `throw` attribute of a `yield from` target is thrown into the delegating generator; CPython raises it in the caller and leaves the generator alone
Severity: low (an object with a property `throw` that raises, as a yield from target).
Where: runtime/src/generator.cpp:185-198 (`gen_throw_impl`, the `try` around `optional_getattr(yf, "throw")` sets `g->pending` and goes to `throw_current`).
Repro:
```python
import traceback
class BadThrow:
    def __iter__(self): return self
    def __next__(self): return 1
    @property
    def throw(self): raise RuntimeError("throw attr")
def deleg(x):
    yield from x
g = deleg(BadThrow()); next(g)
try:
    g.throw(ValueError("x"))
except RuntimeError as e:
    print([x.name for x in traceback.extract_tb(e.__traceback__)])
print(next(g, "exhausted"))
```
CPython: `['<module>', 'throw']` and `1` (the generator is still suspended, frame state restored) / Bella: `['<module>', 'deleg', 'throw']` and `exhausted` (the error was thrown into `deleg`, which died of it). Only the getattr failure behaves this way in CPython (`PyObject_GetOptionalAttr < 0` -> restore frame state, return NULL); an error from *calling* throw() does go into the generator, and Bella is right there.

#### The second DeprecationWarning of a delegated throw is attributed to the wrong line
Severity: low (only seen with `warnings.catch_warnings(record=True)` / `-W error` plus a wrapper whose `throw` is a generator's bound throw called with 2 or 3 arguments through `yield from`).
Where: runtime/src/generator.cpp:185-198, `warn_ex` called from the inner `throw` while the outer generator's frame is not on Bella's frame stack.
Repro:
```python
import warnings
class Wrap:
    def __init__(self, g): self.g = g
    def __iter__(self): return self
    def __next__(self): return next(self.g)
    @property
    def throw(self): return self.g.throw
def outer(x):
    yield from x          # line 10
def inner():
    try:
        yield 1
    except ValueError:
        yield 2
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    o = outer(Wrap(inner())); next(o)
    o.throw(ValueError, "w")   # line 19
print([w.lineno for w in caught])
```
CPython: `[19, 10]` (the caller's line, then the `yield from` line) / Bella: `[19, 19]` (reproduced with exactly this program).
Why: `_gen_throw` links the delegating generator's frame as `tstate->current_frame` before calling the iterator's throw, so a warning raised there (stacklevel 1) names the `yield from` line of the delegator. Bella warns with the caller's frame as the current one.

#### (not generator-specific, seen through throw rows) A wrong-argument-count TypeError has the callee's frame in its traceback
Severity: low to medium (every program that prints or inspects tracebacks of a call with a bad argument list, also in the uncaught report with D-06's file/line/function).
Where: not located; frame arrival for the callee before argument binding (core.cpp `detail::arrive` / the function prologue). Not in the generators files; reported because `g.throw(NeedsArgs)` shows it.
Repro:
```python
import traceback
def f(a, b): pass
class C:
    def __init__(self, a): pass
for fn in (lambda: f(), lambda: C()):
    try:
        fn()
    except TypeError as e:
        print([x.name for x in traceback.extract_tb(e.__traceback__)])
```
CPython: `['<module>', '<lambda>']` twice / Bella: `['<module>', '<lambda>', 'f']`, `['<module>', '<lambda>', '__init__']`. Same for methods, `__new__`, keyword errors and generator functions (`g()` with a missing argument). In CPython the binding error is raised before the callee's frame exists. Through throw: `g.throw(NeedsArgs)` (class with `__init__(self, a, b)`) gives traceback `['catcher']` in CPython, `['catcher', '__init__']` in Bella.

### Checked and found clean
All against CPython, same rows both sides, unless a finding above says so.
- p1 (about 100 rows): metaclass with __subclasscheck__ (findings above); __new__/__init__ raising, returning another exception, needing arguments, with no value / str / tuple / tuple subclass / dict / list / exception instances (own class, parent class, unrelated, BaseException); KeyboardInterrupt, SystemExit, GeneratorExit, StopIteration, StopAsyncIteration, BaseExceptionGroup, subclasses of GeneratorExit and KeyboardInterrupt; instance with an old __traceback__ with and without a tb argument, tb None; a real traceback, one with tb_next assigned; the exception's `__traceback__` afterwards.
- p2 (about 45 rows): thrown exception while the generator handles another (`__context__`, sys.exception() inside), the handled instance thrown back, a context of the handled thrown; caller inside a handler; two-level yield from with handlers; iterators whose throw raises StopIteration with a value, returns a value, whose `close` raises, is not callable, is `None`; `throw` property raising AttributeError; contextlib.contextmanager (six kinds of thrown exception, swallow, StopIteration on exit) and ExitStack; generator expressions (plain, unstarted, three arguments, nested, StopIteration).
- p4 (37 rows, including line numbers): PEP 479 tracebacks and chains through next, send, throw, close, finally, StopIteration subclass, one and two levels of yield from, throw into plain, unstarted and delegating generators, for/list/sum/tuple, generator expressions, contextmanager (body StopIteration, leak, swallow, convert), a StopIteration raised from a helper or inside an except block, `raise ... from`.
- p5 (76 rows): release order of objects with `__del__` on throw paths: handled and unhandled, bad tb argument, instance with a value, not an exception, finished generator, __init__ that raises (the value, `self`, the new exception's argument), delegation chain; close with finally. One difference, RL-222 (a traceback does not keep the locals of the frame that caught and returned): excluded.
- p6 (53 rows): throw/close/send/next into a running generator (also from the inner into an executing outer, and from a finally clause during close); GeneratorExit thrown into generators that yield or return, class/instance/subclass/with value, unstarted, finished; close return value; delegation with a generator, a plain iterator with throw/close, list, list iterator, range, generator expression; GeneratorExit through yield from; arguments passed on as given to an object's throw (1, 2 and 3 arguments).
- p7 (about 45 rows): the exception being made inside a handler of the caller or of the generator (sys.exception() inside __init__, context of a raising __init__, finished generator too); the same instance thrown repeatedly (traceback growth); preset cause and context; ExceptionGroup and BaseExceptionGroup (class with a tuple value); live traceback; with_traceback; the warning's line for direct throws, through an object whose throw is a generator's, and under an error filter (the one difference is the nested warning line above).
- p9: generator finalisation messages on stderr (error in finally, ignored GeneratorExit, StopIteration on close, close of a yield from target raising), apart from source lines (D-06).
- p10 (61 rows): metaclass `__call__` returning other, None, raising, an exception instance; class with `__setattr__` raising thrown with a tb argument; StopIteration, KeyboardInterrupt raised from `__init__` in plain, catching, unstarted and finished generators; GeneratorExit subclass with an `__init__`, with a value of another class, through yield from; an iterator whose throw raises StopIteration(7) given 1, 2, 3 arguments, GeneratorExit class and instance. Differences only as above (the double construction).

### Not checked
- Frame-object-based tracebacks built by the program (`types.TracebackType(...)`, `sys._getframe`): stop by name (E-02).
- Exception classes with a `__traceback__` property or `__slots__`; ABC `register`ed virtual subclasses of an exception class in the subclass check (same cause as the first finding; one row would add nothing).
- Memory safety under ASan: not run; no use after free or leak was seen in the rows, and none was searched for beyond reading `exception_of`, `gen_throw_impl` and the references on their error paths (Ref values throughout; the `catch (const PyError&)` in `exception_of` returns `e.exc` by copy).
- Async generators and coroutines (later phase), threads.
- The uncaught-report format (D-06) beyond the function and line list.

## Focus `warnings-fallback`

Read: commits 3c1ae85 and 5e30722 (diffs and current files: runtime/prelude/_warnings.py, tokenizer.cpp second half, imports.cpp), D-27, case C-7-86 with both expectations, test_warnings_without_the_module.py, and CPython's _warnings.c, traceback.c (display_source_line, _Py_FindSourceFile), file_tokenizer.c, helpers.c, import.c (PyImport_Import).
Ran: 16 probe programs (r22-probes/warnings-fallback/p1..p16.py; p1, p5, p6, p14, p16 driven by argv, 22 runs in all), about 38,000 compared rows (p16 alone: 12,000 random source files x 3 lines); every probe ran on CPython 3.15.2 and compiled, stdout and stderr diffed.

Nearly everything matched row for row. The findings below are all low: each needs an unusual program or environment.

#### PYTHONWARNINGS is ignored (and sys.warnoptions is always empty)
Severity: medium. A test run or CI job that sets PYTHONWARNINGS=error (or ignore, or default::DeprecationWarning) changes what CPython does with every warning; a compiled program never sees it. Not listed in D-xx or in the spec's Environment paragraph (which names PYTHONHASHSEED, PYTHONPATH, PYTHONIOENCODING, PYTHON_LAZY_IMPORTS as honoured or ignored, and nothing about warnings).
Where: runtime/src/call.cpp:1743 (`put(d, "warnoptions", empty.get())`), runtime/prelude/_warnings.py:76 (the initial `filters` are the C defaults only; nothing reads the environment)
Repro:
```python
try:
    ~True                      # DeprecationWarning
except DeprecationWarning:
    print("raised")
print("done")
```
run as `PYTHONWARNINGS=error <program>`.
CPython: prints `raised` then `done` (no warning on stderr) / Bella: prints the DeprecationWarning on stderr and only `done`. With PYTHONWARNINGS=ignore CPython prints no warning, Bella prints it (measured with r22-probes/warnings-fallback/p9.py: under `error` the rows CPython raises are only printed by Bella; under `ignore` the rows CPython silences are printed).
Why: CPython puts -W/PYTHONWARNINGS into config->warnoptions and imports `warnings`, whose _processoptions fills the filters (Python/pylifecycle.c, Lib/warnings.py `_processoptions`). The runtime has no such step. Either honour the variable (apply it when the first warning is shown, or at start-up when it is set) or list it among the ignored environment (like D-18).

#### A registry whose "version" is an int that does not fit a C long: CPython raises OverflowError, Bella warns
Severity: low (a program has to put a huge int in `__warningregistry__["version"]` by hand).
Where: runtime/prelude/_warnings.py:243 (`_already_warned`)
Repro:
```python
import sys, _warnings
sys.modules["warnings"] = None
reg = {"version": 2**100}
_warnings.warn_explicit("m", UserWarning, "<string>", 1, registry=reg)
```
CPython: `OverflowError: Python int too large to convert to C long`, nothing printed, `reg` is `{'version': 0}` / Bella: prints `<string>:1: UserWarning: m`, returns, `reg` has the version and the key. Same for 2**63 and -2**63-1; 2**63-1 and -2**63 agree.
Why: already_warned (Python/_warnings.c) calls `PyLong_AsLong(version_obj) != st->filters_version`; the OverflowError it leaves set makes the next call that checks for errors fail the whole warn_explicit. The prelude compares the Python ints with `!=`.

#### stacklevel -2**63 charges the warning to the caller; CPython walks off the stack to "<sys>"
Severity: low (nobody passes it).
Where: runtime/prelude/_warnings.py:537-550 (`_setup_context`)
Repro:
```python
import sys, _warnings
sys.modules["warnings"] = None
_warnings.warn("m", UserWarning, -2**63)
```
CPython: `<sys>:0: UserWarning: m` / Bella: `prog.py:3: UserWarning: m` plus the source line.
Why: setup_context does `while (--stack_level > 0 && f != NULL)`; for the Py_ssize_t minimum the decrement wraps to +2**63-1 (measured), so the loop runs to the bottom of the stack. The prelude's `stack_level -= 1` is an unbounded int.

#### Wrong text for a None argument: "not NoneType" where CPython says "not None"
Severity: low (the exception's class is right; only args[0] differs, and only for a None argument).
Where: runtime/prelude/_warnings.py:619 and :597
Repro:
```python
import sys, _warnings
sys.modules["warnings"] = None
for call in (lambda: _warnings.warn_explicit("m", UserWarning, None, 1),
             lambda: _warnings.warn("m", UserWarning, skip_file_prefixes=None)):
    try:
        call()
    except TypeError as e:
        print(e.args)
```
CPython: `("warn_explicit() argument 'filename' must be str, not None",)` and `("warn() argument 'skip_file_prefixes' must be tuple, not None",)` / Bella: `... not NoneType` for both.
Why: Argument Clinic's _PyArg_BadArgument names None as "None" and every other object by tp_name; the prelude uses `_tp_name` for all (the message is a ported one, so D-08 does not excuse it). Other types (int, list, ...) match.

#### The source line is read through the str's methods, where CPython reads the raw characters
Severity: low (needs a str subclass that overrides __getitem__/__len__ as a file name, or a program that replaced io.TextIOWrapper to return such lines).
Where: runtime/prelude/_warnings.py:309 (`filename[0]`, `filename[-1]`) and :362-367 (`line[start]`, `line[start:]`)
Repro:
```python
import sys, _io, _warnings
sys.modules["warnings"] = None
with _io.open("src.txt", "w") as f:
    f.write("one\ntwo\n")
class Name(str):
    def __getitem__(self, i):
        return "<" if i == 0 else ">"
_warnings.warn_explicit("m", UserWarning, Name("src.txt"), 2)
```
CPython: `src.txt:2: UserWarning: m` then `  two` / Bella: only the first line (the name looks like "<...>", so the source line is skipped).
The same cause with the line: a replaced `io.TextIOWrapper` whose readline returns `Line("x\n")` (a str subclass with `__str__` returning "STRINGIFIED") and an indented line: CPython strips the raw whitespace and writes an exact str (the subclass's __str__ is not called once anything was stripped); Bella strips through `line[start]`/`line[start:]`, which the subclass can override (measured: CPython `  indented subclass`, Bella `  stringified` for `SL` with __getitem__/__str__ overridden).
Why: display_source_line and the filename test use PyUnicode_READ_CHAR/PyUnicode_Substring; the prelude should use `str.__getitem__(filename, 0)` and the like (it already does so for `str.__len__` and for the sys.path code).

#### The runtime's own import of "warnings" and "io" is called as `__import__(name)`, not the way PyImport_Import calls it
Severity: low (a program that replaces builtins.__import__ to trace imports).
Where: runtime/prelude/_warnings.py:89 and :312 (`_bella_import_if_held(__import__, name)`; runtime/src/imports.cpp i_bella_import_if_held, `invoke(a.pos(0), {a.pos(1)})`)
Repro:
```python
import sys, _warnings, builtins
sys.modules["warnings"] = None
real, calls = builtins.__import__, []
def hook(*args, **kw):
    calls.append((args[0], len(args), type(args[1]).__name__ if len(args) > 1 else None))
    return real(*args, **kw)
builtins.__import__ = hook
_warnings.warn_explicit("m", UserWarning, "src.txt", 1)
builtins.__import__ = real
print(calls)
```
CPython: `[('warnings', 5, 'dict'), ('io', 5, 'dict'), ...]` (PyImport_Import passes globals, locals, a fromlist `[]` and level 0; it then takes the module from sys.modules) / Bella: `[('warnings', 1, None), ('io', 1, None)]`.
Why: PyImport_Import (Python/import.c) calls `__import__(name, globals, globals, [], 0)`; the prelude calls `importer(name)` with one argument. The "warnings" call predates the range; the "io" call is new in 3c1ae85. A hook with the usual signature `(name, globals=None, locals=None, fromlist=(), level=0)` runs, but sees None and (), and gets no chance to look at the importer.

### Checked and found clean

Row counts are probe rows (one printed result each), each run on both sides and diffed; "same" means identical stdout and stderr.

- Encodings of the cookie (p1, 3 runs, about 60 spellings x 4 lines, plus p7's 11 heads): utf-8 spellings, utf-8-sig, latin-1 spellings and aliases, ascii and its aliases, utf-16/32 (with and without -le/-be), a file in UTF-16/32 with BOM, unknown names: same. cp1252, windows-1252, iso-8859-15, latin-9 print no line on Bella where CPython prints one: that is D-20 (a codec outside the phase-1 set; CPython with encodings.cp1252 blocked prints no line either, measured).
- Lexer states on the first two lines (p7, 1,243 rows: 11 heads x about 113 bodies): t-strings, f-strings (nested, open, `=`, lambda), 250-deep brackets, every malformed number, Unicode identifiers (valid, no-break space, euro, ZWJ, combining, emoji, unassigned), indentation errors (tab/space, form feed, 120 levels), unterminated and long strings with invalid UTF-8 or a NUL on a later line, backslash continuations with CR, CRLF and at EOF, NUL, a BOM inside the file, bytes 0xFF in comments: same.
- Random source files (p16, 3 seeds x 4,000 files x lines 1 to 3 = 36,000 rows) built from 70 tokens (coding words, BOM pieces, quotes, brackets, NUL, high bytes, line ends of every kind, no final newline): same except where the cookie names cp1252 (D-20).
- Reader chunk boundaries (p4): a CR, CRLF or LF at byte 8189 to 8193, a two-byte character split at 8189 to 8192, other separators (VT, FF, FS, GS, RS, NEL, U+2028/9), a NUL in the body, a 1 MB line, a 20,000-line file, a truncated UTF-8 tail, an encoded surrogate, an overlong form: same.
- Where the file is looked for (p4, 12 rows): a symlink, a symlink loop, an unreadable file, /dev/null, /proc/self/cmdline, a pipe through /proc/self/fd, a list subclass as sys.path, a str subclass entry: same. Descriptors before and after 3,300 warnings over shapes that fail in different ways: same count (no leak); resident memory after 24,000 more: no growth.
- Writes and the stream (p3 83 rows, p15 50 rows): write that returns None, -1, a str, raises, is a property that raises, is a slot never set, a __getattr__ that records the name, a callable attribute; StringIO, TextIOWrapper over BytesIO with 11 encodings x 5 error handlers x 3 buffering modes (text containing non-Latin letters, a lone surrogate, an emoji: the pieces written before the one that fails, the bytes that come out), closed and detached wrappers, BytesIO, BufferedWriter, a real file opened ascii/strict and utf-8 line-buffered; category with a raising or non-str `__name__`, a text whose `__str__` returns an int or a str subclass, a str-subclass file name, non-ASCII and surrogate file names: same.
- The filters and registries (p2 273 rows, p13 about 70 rows, p8 96 rows): all seven actions, an unknown and an empty action, with and without a registry, once registry and its version key, registry "version" of True/str/float/0/1, preset keys, a dict subclass registry whose methods raise, a non-dict registry, filters of every malformed shape (not a tuple, wrong length, int/bytes/str-subclass action, str or bytes message, str module given and absent, bool/float/huge lineno, a category that is no class or a tuple), regex-like objects that raise, return [] or 1, or mutate or clear the filters or warn while matching, rebinding or deleting `_warnings.filters`, `_defaultaction`, the context variable with a list, a tuple, no attribute, a bad item; unhashable message with and without a registry for default/once/module/always/error, an unhashable metaclass, a hash that raises, a lineno that is an int subclass, an __index__ returning bool or an int subclass; messages and categories of every kind (Warning instances with another category, ints, None, bytes, tuples, a category whose constructor raises); lock functions; argument errors (missing, extra, 6 positionals, wrong skip_file_prefixes, lineno float/str/bool/2**31/-2**31-1, module of every type, module_globals int/None, source): same except the three argument/registry findings above.
- A fake `warnings` in sys.modules (p8, 96 rows): an object that logs every attribute read, with `_showwarnmsg` and `WarningMessage` (arguments passed: 7 without a module, 8 with one, lineno an int, source, sourceline), a non-callable `_showwarnmsg`, no WarningMessage, raising constructors and callbacks, a stale `filters` kept when the attribute is missing, defaultaction (int, error, ignore, once, str subclass), onceregistry (list, dict, dict subclass), attributes that raise RuntimeError, ImportError or KeyboardInterrupt, a class, an int and a dict as the module, a module whose `__spec__._initializing` is set: order of attribute reads and every result: same.
- Frames (p3, p9, p12): stacklevel 0 to 4 and 100 through map, sorted, property, __str__, __getattr__, __enter__/__exit__, __iter__, operators, __call__, __len__, __eq__, class body, comprehensions, generators, lambdas, __del__; a call over several lines; the runtime's own warnings (~bool, int/float/complex/__index__ returning a subclass, generator throw with three arguments) in __main__ and in an imported module, under error/always/ignore/module/once filters, and their registries; a module that warns at import with stacklevel 0 to 5 through import, from-import, __import__, importlib.import_module, fromlist, nested; `__warningregistry__` of every type, `__name__` of every type, deleted, None: same.
- The "<sys>" fallback (p15): registry kept in sys.__dict__, module name "sys", filters on "sys" and "<sys>": same.
- Showing at the end of the program (p5): a global's `__del__` warning at exit (module None ignored, others printed with no source line), an atexit callback, an uncaught exception after a warning, sys.exit after a warning: stdout, stderr and status same (the traceback's source line is D-06).
- The path that does not block `warnings` (p11): a program with no `os` and no blocking, three warnings, explicit ones, a runtime one: the text equals CPython's blocked run; `sys.modules` afterwards lacks `warnings` and `io` (D-27 names `warnings` and what it imports).
- A program that imports `warnings` (p10, 101 rows): simplefilter and filterwarnings with every action and category, regex message/module/lineno filters (module absent: the filename), catch_warnings (record, action, error), showwarning and formatwarning overrides and calls, file=None, an OSError and a ValueError from write, lines with tab, form feed and trailing spaces, the sys.path lookup by name, "<string>", missing files, lineno 0 and past the end, version bump re-showing: same.
- The stops: `del sys.stderr`, a bool used as the descriptor (open returning True, fileno returning True), `module_globals` given as a dict, `importlib.reload`: each ends with `bella: not implemented: ...` and exit 70 as the documentation says (p6; not counted as findings).
- An error filter turning a warning in the middle of the showing path into an exception: the exception class, args and traceback line number (p6 `filtererr`): same.

### Not checked

- Threads, signals during a warning (D-25), the evaluators.
- `-W` and `-X` options: a compiled program has none; only the environment variable was tried (finding 1).
- `warnings.warn_explicit(..., module_globals=...)`: stops by name.
- Source lines for files that change while being shown; /dev/zero or other endless files (CPython would not return either); files over 2 GB.
- A `sys.meta_path` finder asked for "warnings" or "io": a compiled program without them does not consult the finders (`Finder.log` empty after three warnings, where CPython's finder sees the imports); this is D-27's "the import fails as for a module that is not installed", so it was not listed.
- Outside the focus, seen on the way and not pursued: with stderr closed (`2>&-`) or full (`2>/dev/full`) a compiled program's exit status after teardown output differs from CPython's (`sys.exit(3)` with stderr closed: CPython 3, Bella 120; a `__del__` that writes to sys.stderr at exit with stderr on /dev/full: CPython 0, Bella 120). It happens without any warning, so it belongs to the standard-stream/exit area; p5 `stderr` and `quit` show it.
- Re-recording, running `make` or pytest: not allowed here.

## Focus `locals`

R22-sonnet-locals: read commit 16943f1 and the locals/co_* parts of cfc413d (call.cpp function_locals/frame_locals/b_locals/b_vars, b_dir, FrameGuard, cpp.py code_record, resolve.py co_varnames/co_cellvars, frontend.py _Comprehensions/_hoist/_walrus_targets), DECISIONS 2026-11-15, case C-8-15, test_frame_locals.py, and CPython's bltinmodule/ceval/frameobject/symtable/compile.
Ran 10 probe programs (r22-probes/locals/p1..p10.py, 14 builds), about 340 rows, each compared CPython vs compiled.

#### co_varnames and locals() order wrong for a walrus target bound by a comprehension that sits in a nested block
Severity: medium (any function that has an `if`/`for`/`while`/`try`/`with`/`match` body with a comprehension using `:=` after other bindings in that body, then calls locals(); co_varnames is wrong for every comprehension in a nested block, even without `:=`)
Where: pipeline/l1/frontend.py:1899-1923 (`_hoist`) with `_Comprehensions` (frontend.py:1750-1900; no visit_If/For/While/Try/With/Match, so generic_visit descends into the nested bodies); order used at pipeline/l2/resolve.py:96 (`inlined_at` = len(parent.order)) and resolve.py:371 (`co_varnames`)
Repro:
```python
def r1(a):
    if a:
        s = 1
        r = [(w := i) for i in range(a)]
    return locals()
print(list(r1(2)), r1.__code__.co_varnames)

def r4(a):
    for q in a:
        s = [(w := i) for i in range(q)]
        t = 1
    return list(locals())
print(r4([1, 2]), r4.__code__.co_varnames)
```
CPython: ['a', 's', 'w', 'r'] ('a', 's', 'i', 'w', 'r') / ['a', 'q', 'w', 's', 't'] ('a', 'q', 'i', 'w', 's', 't')
Bella:   ['a', 'w', 's', 'r'] ('a', 'i', 'w', 's', 'r') / ['a', 'w', 'q', 's', 't'] ('a', 'i', 'w', 'q', 's', 't')
Why: the transformer hoists the comprehension's helper before the OUTERMOST statement that contains it (the visit of the `if`/`for`/`while`/`try`/`with`/`match` statement already walks its bodies, so `_hoist`'s recursion into the bodies finds nothing left). The helper's position in the scope order, which is where the comprehension's variables and its walrus targets (`enclosing_binds`) are inserted, is therefore before every name bound earlier inside that block. CPython's symtable visits the comprehension where it stands. Same effect in try/except-as (`i` before `e`), with-as, match captures, else/finally blocks. Fix: visit_If/For/While/Try/With/Match (or stop generic_visit at statement lists) so the helper lands in the innermost block, before its statement. Probes p5 (40 functions, 22 differ), p6, p10; top-level comprehensions are right.

#### locals() / vars() of a generator expression has the iterator in `.0`, CPython has the iterable
Severity: low (needs locals()/vars() inside a genexp whose outermost iterable is not already an iterator)
Where: pipeline/l1/frontend.py:1840-1866 (genexp helper is called with iter(<outermost iterable>), `bella_iterator`), runtime/src/call.cpp:713 reads it as is
Repro:
```python
def r6(seq):
    return next(locals() for _ in seq)
seq = [1, 2]
d = r6(seq)
print(type(d['.0']).__name__, d['.0'] is seq)
```
CPython: list True / Bella: list_iterator False
Why: in 3.15 the genexp code does `LOAD_FAST .0; GET_ITER` itself (the argument is the iterable; the TypeError for a non-iterable is still raised eagerly at creation, which Bella keeps). `.0` is range(0, 1), a list, a str, a dict in CPython; Bella gives range_iterator, list_iterator, str_ascii_iterator, dict_keyiterator. `vars()` of the frame shows the same.

#### The class-dict cell holds a mappingproxy, CPython's holds the namespace dict
Severity: low (visible only through `__classdictcell__` in a class body's namespace, or `locals()`/`vars()` inside an annotation of a class body)
Where: runtime/src/types.cpp:844-848 (`Ref proxy = own(new Proxy(c))` stored in the `__classdictcell__` cell)
Repro:
```python
class AC:
    w: locals()
print(type(AC.__annotations__['w']['__classdict__']).__name__)
class H:
    x: int = 1
    loc = locals()
print(type(H.loc['__classdictcell__'].cell_contents).__name__)
```
CPython: dict / dict. Bella: mappingproxy / mappingproxy.
Why: type_new_set_classdictcell stores the class's dict itself in the cell, not a proxy; the annotate scope's locals() then shows `'__classdict__': {...}` (a dict) in CPython.

#### co_varnames / co_nlocals lack the global name a comprehension walrus assigns under `global`
Severity: low (a CPython quirk, visible only in co_varnames/co_nlocals)
Where: pipeline/l2/resolve.py co_varnames / frontend.py `declared_global` handling
Repro:
```python
def r5(a):
    global GG
    r = [(GG := i) for i in range(a)]
print(r5.__code__.co_varnames, r5.__code__.co_nlocals)
```
CPython: ('a', 'i', 'GG', 'r') 4 / Bella: ('a', 'i', 'r') 3
Why: CPython's inlined comprehension (push_inlined_comprehension_state) gives the walrus target of the comprehension a fast-local slot in the enclosing function even though the name is declared global there (locals() does not list it; only the code object does). Also with the assignment `GG = 1` before. Only the tables differ; locals() is the same.

#### dir() with a mapping whose keys() returns a non-iterable: message differs from CPython; dir() argument-count message differs
Severity: low (wording; D-08 allows unported messages, but both are in the range's `dir()`)
Where: runtime/src/imports.cpp:2246-2255 (`b_dir`), runtime/src/imports.cpp:2243 (`positional_only(a, "dir", 0, 1)`)
Repro:
```python
class D(dict):
    def keys(self): return 5
class M(type):
    @classmethod
    def __prepare__(mcls, name, bases): return D()
try:
    class C(metaclass=M):
        d = dir()
except TypeError as e: print(e)
try: dir(1, 2)
except TypeError as e: print(e)
```
CPython: `<qualname of D>.keys() must return an iterable, not int` (probe p2 row a26: 'a26.<locals>.D.keys() must return an iterable, not int'); `dir expected at most 1 argument, got 2`
Bella: `'int' object is not iterable`; `dir() takes from 0 to 1 positional argument but 2 were given`
Why: PyMapping_Keys (method_output_as_list) has its own TypeError; builtin_dir is METH_FASTCALL with PyArg_UnpackTuple wording.

### Checked and found clean
- co_varnames / co_cellvars / co_freevars / co_nlocals / co_argcount and locals() keys, order and values for about 150 function shapes (p1, p2, p4, p7): all parameter kinds (positional-only, defaults, *args, keyword-only, **kw), closures over parameters, nonlocal, global, cells never bound or deleted, del of cells, lambdas (nested, defaults), nested functions three deep, methods with `__class__`/super, generic functions (PEP 695), private-name mangling of locals and parameters, NFKC-normalised identifiers, names bound by import, with, except-as, for, match (captures, partial matches, star/mapping patterns), except*, annotated-only names, comprehension variables shadowing outer names, nested comprehensions with walrus in element and in conditions, dict/set comprehensions, comprehensions in lambdas and in genexps, 300 locals, recursion depth 500. Only the differences above.
- locals(), vars(), dir() in module, class bodies (plain, nested, in functions, with a `__prepare__` OrderedDict / dict subclass / non-dict mapping, keys() overridden, keys() returning an iterator or mixed types), and class-body annotation scopes: 25 rows.
- Reached as another name or from another hand (p3, p8): alias, partial, nested partial, operator.call, methodcaller, getattr(builtins), `__call__`, iter(callable, sentinel), starmap, lru_cache/cache wrapping, defaultdict(locals), dataclass default_factory, helper called with the builtin, class with `__call__`, shadowed names, monkeypatched builtins.locals: 40 rows.
- Generators (p3): locals() between yields, after send/throw/close, yield from, try/finally, genexp frames (`.0`, loop variable, walrus in genexp), with the iterable evaluated outside: 20 rows (only `.0`'s value differs, above).
- Iterable of a comprehension calling locals()/dir() (`[k for k in locals()]`, dict/set/gen forms) answers like CPython: 6 rows.
- Error behaviour (p3, p9): arguments to locals/vars/dir, vars() of ints/None/slots/`__getattr__`/raising `__dict__`/odd `__dict__`, `__context__`/`__cause__`/traceback length, keys() raising inside a class body, `warnings.simplefilter("error")` in effect: 25 rows, only message wording above.
- Annotation scopes (def, class, generic def): `locals()`, `dir()`, `vars()` in annotations of functions inside functions: 6 rows.
- Safety read of the C++ (function_locals, FrameGuard::slots/ns, record_frame's `Ref::share(ns)`, the comprehension counter in ~FrameGuard): no use-after-free or double release found; cells of the compiled frame that are plain locals in CPython read correctly (RL-446) in every shape probed.

### Not checked
- `eval`/`exec` given locals() (stops by name), locals() inside list/set/dict comprehensions (stop by design; note it also stops at module level and in a class body, where CPython simply answers with the namespace, since the `comprehensions > 0` test precedes the CO_OPTIMIZED test in `frame_locals`).
- Class generics (`class G[T]`) and `type X = ...` rows (stop on importing typing), gi_code, `__text_signature__` of builtins, a class overriding `__getattribute__` (stops by name).
- frame objects (`sys._getframe().f_locals`, tb_frame.f_locals), unboxed locals (phase 2), memory use under repeated calls.

## Focus `traceback`

R22 traceback review (S22, Sonnet). Read: commits aa98477 and cfc413d, runtime/replaced/traceback.py, runtime/prelude/_suggestions.py, call.cpp traceback intrinsics, core.cpp add_entry/record_frame/Traceback destroyer, DECISIONS entries, both test modules, CPython traceback.py.
Ran: 10 probe programs (about 17 builds, about 2,900 printed rows, most of them the p3 suggestion sweep) under r22-probes/traceback/, each diffed against .venv CPython 3.15.2.

#### NameError "Did you mean" picks a different builtin on a tie, because vars(builtins) is in another order
Severity: medium (ordinary typo-ed builtins such as dic, mix, pint, folat, lex give another hint; a program that prints traceback.format_exc() or logs the report differs on stderr or in its log)
Where: runtime/replaced/traceback.py `_compute_suggestion_error` (NameError branch: `list(f_locals) + list(names[1]) + list(names[2])`) reading the builtins dict that `__bella_traceback_names__` returns (runtime/src/call.cpp i_traceback_names, `builtins_module()->dict`). The cause is the order of the builtins module's dict, which is the runtime's registration order, not CPython's (_PyBuiltin_Init order).
Repro:
```python
import traceback
def tail(fn):
    try:
        fn()
    except Exception as e:
        return "".join(traceback.format_exception(e)).splitlines()[-1]
def a(): return dic
def b(): return mix
def c(): return pint
print(tail(a)); print(tail(b)); print(tail(c))
```
CPython: `... name 'dic' is not defined. Did you mean: 'dir'?` / `'mix' ... 'max'` / `'pint' ... 'print'`
Bella: `... 'dic' ... Did you mean: 'dict'?` / `'mix' ... 'min'?` / `'pint' ... 'int'?`
Why: _suggestions chooses the first of the equally close names, so the candidate order decides. CPython's builtins dict starts `__build_class__, __import__, __lazy_import__, abs, all, any, ...`; Bella's starts `str, type, bool, range, tuple, list, int, object, dict, ...` (list(vars(builtins))). Probe p3 (every public builtin with 6 typo forms, about 1,100 rows, run on both sides): 31 rows differ, all of them ties (AssertionError, OFError, KyeError, comple, dct, dic, ict, ir, folat, fromat, lex, ist, ma, mix, pint, rint ...). Everything else in the 1,100 NameError rows is the same. Related and visible in the same sweep: `'aiter' in vars(builtins)` and `'anext' in vars(builtins)` are False in Bella though they are in dir(builtins) and in CPython's dict (so `NameError: aiter` hints differ too; async is a later phase, so the order is the point). The fix is to build the builtins dict in CPython's insertion order (the names table knows it).

#### ModuleNotFoundError for a top-level module gets no "Did you mean" even when the program imports the module it is closest to
Severity: low to medium (`import jsn`, `import colections`: the report a program prints with traceback lacks the hint, though json and collections are compiled into the program)
Where: runtime/src/imports.cpp `_bella_discover` (PathFinder.discover() with no parent) feeding `_compute_suggestion_error` in runtime/replaced/traceback.py (ModuleNotFoundError branch, `discover(None)`).
Repro:
```python
import json, re, collections, traceback
def d(): import jsn
try: d()
except ModuleNotFoundError as e: print(traceback.format_exception_only(e)[-1].rstrip())
import importlib.machinery as m
print("json" in {s.name for s in m.PathFinder.discover()})
```
CPython: `ModuleNotFoundError: No module named 'jsn'. Did you mean: 'json'?` / True
Bella: `ModuleNotFoundError: No module named 'jsn'` / False
Why: top-level discover() lists only the program's own directory (sys.path has 1 entry; CPython's 5), so no library module is ever a candidate: also `import ree` -> 're', `import tracebak` -> 'traceback', `import Json` -> 'json'. Under a package parent the library is listed (`import json.decodr` gives `Did you mean: 'json.decoder'?`, same as CPython). DECISIONS (2026-11-12) says the case asks "only what both agree on", so the top-level gap is known in kind, but it is not in docs/deviations.toml and the spec's section 8 says nothing about library names; a program that imports json can reasonably expect the hint. Probes p4, p5, p10.

#### Line of a traceback entry in a multi-line statement: method call or attribute chain, decorator, assert, raise (...)
Severity: medium (the line in every traceback line, `tb_lineno`, `StackSummary.lineno`, and the uncaught-exception report; multi-line call chains, decorators and assert are ordinary code; D-06 keeps the line, so a difference is a defect)
Where: the compiler's line information for the entry of the raising frame (pipeline lowering; the entry's `line` from add_entry/record_frame), not in the replaced traceback code.
Repro:
```python
def boom(*a): raise ValueError("b")
class O:
    def chain(self): return self
    @property
    def prop(self): raise ValueError("p")
def lineno(fn):
    try: fn()
    except Exception as e: return e.__traceback__.tb_next.tb_lineno
def call_chain():
    O().chain(
    ).chain(
    ).prop
def decorated():
    @boom
    def inner(): pass
def assert_multi():
    assert (
        False
    ), "msg"
def raise_multi():
    raise (
        ValueError
    )
for f in (call_chain, decorated, assert_multi, raise_multi):
    print(f.__name__, lineno(f))
```
(Line numbers relative to the def line, one-based within the function body.) Measured in probes p6, p7, p8 (about 140 constructs, 17 differ). Observed pairs (CPython line / Bella line, absolute lines in p8.py): call chain `O().chain(\n).meth(\n)` 16 / 15; `O() \ .chain() \ .prop` 22 / 20; decorator `@boom \n def inner()` 25 / 26 (also two decorators on a class: first called is the inner, CPython the decorator's own line, Bella the class line; `@(\n boom\n)` 240 / 242 in p7); `assert (\n False\n ), "msg"` AssertionError line 30 / 29; `raise (\n ValueError\n)` 116 / 117 in p6; `x.attr.\ \n missing` 165 / 164; `(O()\n .prop)` 62 / 61; `O()[0\n][1\n].attr.missing` 52 / 48; `("a"\n .foo)` 327 / 326.
CPython: the attribute or call is attributed to the line of the attribute name token (`.meth(`, `.prop`, `missing`), a decorator call to the decorator's line, an assert to the line of the failing expression (the test), `raise (X)` to the raise keyword's line.
Bella: the first line of the statement or expression for chains and attributes, the def/class line for decorators, the assert line, and the operand's line for a parenthesised raise operand.
Why: a statement-level (or expression-start) line is recorded where CPython's co_positions give the line of the specific instruction (LOAD_ATTR/CALL for the attribute token; the decorator expression; the assert's raise site; RAISE_VARARGS at the raise line). Single-line cases, calls whose arguments are on later lines, comprehensions, with/for/if/while headers, f-strings, binary operators, subscripts, finally and except clauses all matched (about 125 rows).

#### ModuleNotFoundError built with a non-str name: CPython raises AttributeError when formatting, Bella formats
Severity: low (nothing ordinary builds the exception that way)
Where: runtime/replaced/traceback.py `_find_incompatible_extension_module` (always None) vs CPython's, which calls `.rpartition` etc. on the name.
Repro:
```python
import traceback
print(traceback.format_exception_only(ModuleNotFoundError("x", name=5)))
```
CPython: AttributeError raised from traceback (`'int' object has no attribute ...`) / Bella: `['ModuleNotFoundError: x\n']`
Why: the replacement skips CPython's work entirely, so what CPython's body does with a non-str name is lost. Same path: `format_exception_only(ModuleNotFoundError("x", name="q"))` agrees.

### Checked and found clean
- p1 (about 60 rows): format_exception for cause, context, suppressed context, raise e, bare raise, __notes__ of ten types (list, str, int, tuple, mixed, multiline, empty, None, bytes, dict) and add_note, nested groups, groups with notes, group inside a context, group as a cause, BaseExceptionGroup; an exception whose __str__ raises or returns an int; format_exception_only with None value, args, KeyError, module/qualname/__module__ variants (None, int, builtins, __main__); SyntaxError by hand with and without every field (twelve forms, tab, non-ASCII, offset 0 and 100, non-str text and offset, IndentationError), raised and chained. All the same (file base name, line, function name, message lines).
- p2 (about 55 rows): extract_tb with limits, format_tb, format_list, StackSummary.from_list, FrameSummary fields and repr, clear_frames, tb_next assignment (None, wrong type, loops, swap), with_traceback and raise e with an existing tb, __traceback__ assignment errors, exceptions from generators, class bodies, list/set/dict comprehensions, genexpr, lambdas, methods, properties, __getitem__, __call__, operators, with; an exception raised in __del__ (report and sys.unraisablehook arguments); lifetime rows 1 to 7: an object with __del__ held in the raising frame dies at the same print position as CPython's when the exception, its traceback, a TracebackException, format_exc, sys.exc_info or clear_frames is dropped.
- p3 (about 2,300 rows): AttributeError "Did you mean" and nested-attribute sweeps over dir() of 24 builtin types and 10 library modules (math, os, json, re, collections, itertools, string, random, traceback, builtins) with 3 to 4 typo forms per public name; NameError sweep over every public builtin (the ties are the first finding); dir counts of modules and builtin types.
- p4 (about 145 rows): self-private rule (self, other object, rebound self, alias, static method, `this`), mangled names, property and raising property in nested checks (not executed), the 20-attribute limit, class with __getattr__ (with and without name), __dir__ returning odd items, raising, non-iterable, a generator, a tuple, over 750 candidates and 740 candidates, __dir__ called once, a metaclass __dir__, wrong names of 41, 40, 59 and 60 characters, eight non-ASCII names with normalisation, 36 cross-language hints, 24 from-import and import forms, manual ImportError and ModuleNotFoundError with every combination of name and name_from, stdlib-missing messages, lazy imports (not loaded by a suggestion).
- p5 (about 60 rows): about 45 real NameErrors in function, nested, closure (free variables), method, class body, comprehension, genexpr, lambda, match, walrus, nonlocal, global, args/kwargs, with-target and except-target frames; tie order among locals and globals; module-level NameError and the "forgot to import" hint for eight library names; self.name hint with __getattr__ raising, returning, printing.
- p9 (about 45 rows): clear_frames then format, repeated formatting, bare reraise and raise e across frames, cause chains, through a catching frame, generator frames still running, with_traceback of another exception's traceback, constructed errors without a traceback, AttributeError with and without obj, bad __str__ in a NameError subclass, deleted/unbound locals, unittest errors and assertRaises, logging.exception, print_exception forms (limit, chain, old signature), TracebackException attributes, compact, lookup_lines, limit, bad tb arguments, fake tb and frame objects.
- p6/p7 line numbers: single-line and multi-line calls with arguments on later lines, nested calls, with/for/if/elif/while headers, finally, except expressions, comprehensions, f-strings, binary and comparison operators, subscripts, lambdas, class bodies, imports, `raise ... from`, generator close and throw (also the three-argument form), StopIteration in a generator, recursion folding, RecursionError, sys.tracebacklimit, the limit argument, group depth 20 and width 20, cause cycles, self-context (about 125 rows the same).

### Not checked
- The C++ for memory misuse was read (add_entry, record_frame moving locals into the entry, the destroyer clearing `link->holder`, i_traceback_clear moving the vector out first, i_traceback_names reading `link->holder`), but no crash or leak was found and none was sought with a sanitizer build (no heavy tools).
- tb_frame, tb_lasti, types.TracebackType(...), walk_tb, capture_locals=True, f_locals of a frame: stop by name (E-02), not probed further.
- Namespace packages (stop by name), discovery under a user package beyond what C-8-13 covers, exceptions in a comprehension running in the frame (a listed stop), RL-222 lifetimes.
- Noted but outside the focus and not pursued: a program-level `SyntaxWarning` for `None(` was printed twice by the compiled program (once by CPython).

## Focus `frames-signals`

Read: commits 425fd18, 2c73111, 29010fb and their diffs, the DECISIONS entries and D-25, runtime/src/{call,signals,ops,sre,bigint}.cpp, bn.inc, runtime/prelude/_sre.py, runtime/replaced/traceback.py, the CPython sources for PyObject_Str/Repr, sre, longobject and pythonrun.
Ran: 13 probe programs (r22-probes/frames-signals/p1..p13, p11 in 10 modes), about 1,130 CPython rows compared with the compiled run of each; about 20 builds.

#### A signal handler that resizes a bytearray during a match corrupts memory (segfault)
Severity: medium. Needs a handler that touches a bytearray being matched, which is rare. But C-7-85 created the case by letting handlers run inside the engine, and the result is a use after free rather than an exception.
Where: runtime/prelude/_sre.py:240 (`_matched`, used by match, search, fullmatch and prefixmatch), :374 (`findall`), :404 (`split`); runtime/src/sre.cpp:954 (`i_run` reads `data.data` borrowed from the bytearray's std::string; `get_string` at :900).
Repro:
```python
import re, signal
ba = bytearray(b"a" * (1 << 26) + b"b")
def on_alarm(signum, frame):
    signal.setitimer(signal.ITIMER_REAL, 0)
    ba.extend(b"b" * (1 << 28))          # reallocates the buffer the match is reading
signal.signal(signal.SIGALRM, on_alarm)
signal.setitimer(signal.ITIMER_REAL, 0.05)
try:
    print(re.match(rb"(a+)+$", ba))
except BufferError as e:
    print("BufferError", e)
print(len(ba))
```
CPython: `BufferError Existing exports of data: object cannot be re-sized` then `67108865` / Bella: Segmentation fault (exit 139).
Smaller sizes give no crash but a wrong answer. For `append`, `extend`, `clear` and `pop` in the handler, CPython raises BufferError (the handler's own exception) from match, search, fullmatch, findall, split and re.match, where Bella resizes, goes on matching the old pointer and returns, e.g. `match/append -> returned None len 34`, `match/clear -> raised Interrupted len 0` (p7: 5 mutators x 8 entry points; sub and finditer agree).
Why: `state_init` exports the buffer (PyObject_GetBuffer) for every entry point and releases it in `state_fini`; that is what makes a handler's `ba.extend()` fail. The prelude does `_sre_call("export", string, 1)` only in `_subx` (:307) and the scanner (:649). Before C-7-85 nothing could run Python while the engine held the pointer; now the 4096-step check runs handlers there. `findall` and `split` also re-read `get_string` for each `_run` but pass the old `endpos`, so a shrunk bytearray is read past its end between iterations.

#### The frame a handler is given is a new object at every arrival
Severity: low. Identity of `frame` is rarely used.
Where: runtime/src/signals.cpp:`frame_argument` (a `new FrameObject` for each pass of `check_signals`).
Repro:
```python
import signal
frames = []
signal.signal(signal.SIGUSR1, lambda s, f: frames.append(f))
signal.raise_signal(signal.SIGUSR1)
signal.raise_signal(signal.SIGUSR1)
print(frames[0] is frames[1], frames[0] == frames[1], hash(frames[0]) == hash(frames[1]))
```
CPython: `True True True` (one frame object per running frame; a `set` of the two has 1 member) / Bella: `False False False`.
Why: CPython's PyFrameObject is made once for an interpreter frame and cached; here each pass makes its own, and C-7-87 only guarantees one object for the handlers of one arrival.

#### `del` of an unbound global, class-body or exec'd name raises NameError with `.name` None
Severity: low.
Where: runtime/src/call.cpp:422, :429 and :433 (`delete_name`, `delete_global`) use `raise_new("NameError", ...)`; `raise_name_error` (:388) is what sets `name`.
Repro:
```python
try:
    exec("del nope", {})
except NameError as e:
    print("name:", e.name)
```
CPython: `name: nope` / Bella: `name: None`. The same for `class C: del zz`, and `global gg; del gg` in a function.
Why: the DELETE_NAME / DELETE_GLOBAL path (format_exc_check_arg in ceval) sets `NameError.name`; the load path here does and the delete path does not.

#### A deleted local read in a comprehension, and a doubly deleted nonlocal, raise the other NameError class
Severity: low.
Where: the unbound-local and unbound-free-variable raising around runtime/src/call.cpp:380 and the comprehension lowering.
Repro:
```python
def h():
    x = 1
    del x
    return [x for _ in range(1)]
def k():
    x = 1
    def inner():
        nonlocal x
        del x
    inner()
    inner()
for fn in (h, k):
    try:
        fn()
    except NameError as e:
        print(type(e).__name__, e)
```
CPython: `UnboundLocalError cannot access local variable 'x' where it is not associated with a value` then `NameError cannot access free variable 'x' where it is not associated with a value in enclosing scope` / Bella: the two swapped (`NameError ... free variable` for h, `UnboundLocalError ... local variable` for k).
Why: since PEP 709 a list, set or dict comprehension is inlined, so `x` is the function's own local and the error is UnboundLocalError (also `{x for ...}`, a condition, a nested `[[x] ...]`; p9 b3 to b8; `(x for ...)` stays a free variable and agrees). The comprehension is lowered as a closure here. A second `del x` through a nonlocal is a free-variable error in CPython (DELETE_DEREF) and is treated as a local one here.

#### `print()` after `del sys.stdout` raises AttributeError, not RuntimeError('lost sys.stdout')
Severity: low. This is the C-8-14 area (a name the program deleted).
Where: runtime/prelude/builtins.py:19 (`file = sys.stdout`).
Repro:
```python
import sys
out = sys.stdout
del sys.stdout
try:
    print("hidden")
except Exception as e:
    sys.stdout = out
    print(type(e).__name__, e)
```
CPython: `RuntimeError lost sys.stdout` (also `print("x", file=None)`) / Bella: `AttributeError module 'sys' has no attribute 'stdout'`. `input()` agrees (RuntimeError); `sys.stdout` itself and `warnings` after `del sys.stderr` agree.
Why: builtin_print_impl uses `_PySys_GetAttr` and raises RuntimeError("lost sys.stdout") when it is NULL; the prelude reads the attribute.

#### After the main program has ended, `__file__` is still in the program's globals (atexit callbacks, `__del__` at exit)
Severity: low.
Where: the run_main exit path in runtime/src/call.cpp (the main module's dict is left as it was).
Repro:
```python
import atexit, sys
def bye():
    try:
        print(__file__[-6:])
    except NameError as e:
        print("NameError", e.args)
    print(hasattr(sys.modules["__main__"], "__file__"))
atexit.register(bye)
```
Run as a script. CPython: `NameError ("name '__file__' is not defined",)` then `False` / Bella: `p12.py` then `True` (p12.py is the file name there).
Why: `pyrun_file` (Python/pythonrun.c:493-543) sets `__file__` for a script and pops it again when the script is done; atexit callbacks, finalizers at exit and handlers owed at exit run after that. Side effect in p11 (inatexit rows): a handler owed inside an atexit callback prints differently because its own `__file__` read fails in CPython.

#### `import` of a native module after its `sys.modules` entry was deleted gives back the old, mutated module
Severity: low.
Where: runtime/src/imports.cpp (the native modules are singletons).
Repro:
```python
import sys, math
math.pi = 3
del sys.modules["math"]
import math as again
print(again is not math, again.pi)
```
CPython: `True 3.141592653589793` / Bella: `False 3`. The same for `itertools` and `time` (p9 d1 to d3); Python-level library modules (`string`) agree.
Why: CPython creates a new module object and re-runs its init; here the registry stands for the finder and hands out the one object.

#### A call that applies a decorator is at the def line, not the decorator's line, in tracebacks and in the running stack
Severity: low (not a regression of this range, but it shows up in `extract_stack()` and in a handler's listing taken while a decorator runs).
Where: the call the emitter makes for each decorator (pipeline emitter and the line set before it); `co_firstlineno` already is the first decorator's line (DECISIONS 2026-11-07).
Repro:
```python
import traceback
def deco(f):
    print("decorator applied from line", traceback.extract_stack()[-2].lineno)
    return f
def g():
    @deco
    def f():
        pass
g()
```
CPython: `decorator applied from line 8` (the `@deco` line) / Bella: `line 9` (the `def` line). The same for stacked decorators (CPython gives each decorator its own line, innermost first) and for a decorated class (`@deco2` lines 181 and 180 against 182 and 182 in p3). An exception raised in the decorator has the same wrong line in its traceback (p3: `deco tb lines [142, 135]` against `[143, 135]`).
Why: CPython attributes the decorator call (CALL) to the decorator expression's own line.

### Checked and found clean
- Stack listing of the running stack and of a handler's frame (p2, 335 rows, plus p3, p7, p9, p10): nested and multi-line calls, generators (for, list, yield from, send, genexpr), class bodies (nested, metaclass `__new__` and `__init__`, `__init_subclass__`, `__set_name__`), lambdas, map, filter, sorted/min key, reduce, cmp_to_key, partial, comprehensions, 20 special methods (`__del__`, property, `__getattr__`, `__enter__`/`__exit__`, `__iter__`, `__eq__`, `__hash__`, `__lt__`, `__repr__`, `__call__`, `__getitem__`, `__len__`, `__bool__`, `__add__`, `__format__`, `__contains__`), contextmanager, weakref callback, staged exec and eval code. Each of these was compared for `extract_stack()` and for `extract_stack(frame)` inside a handler, with the handler's repr, `limit` 2 and -1, and `format_stack`. All equal but the decorator line above.
- Limits, `sys.tracebacklimit` 0 and 1, bad arguments (None, int, str, object, a traceback passed as a frame: same TypeError/AttributeError), `print_stack(file=...)`, `StackSummary.extract` handed a handler frame.
- Handler frame lines at the loop turn for 14 loop shapes (while, for, nested, for/else, generator, class body, try in loop, multi-line condition, iter(), itertools.count, with); the frame in atexit and `__del__` at exit; the same signal raised inside its own handler 3 deep; two handlers of one arrival; frame type, copy, weakref, subclassing, str/format/%s/%r of the frame, eq/hash/dict key inside a pass.
- Regex: a handler running a regex of its own, itself interrupted by a nested arrival (a regex and a big-int product and str() inside a handler); raising `Inner` out of a nested match; a raising handler leaving the pattern usable; scanner re-entry from a handler (ValueError "already executing"); a signal raised from a handler; sub with a callable, split, findall, fullmatch, finditer, bytes; KeyboardInterrupt from the default handler; SystemExit(7) from a handler inside a match (finally, atexit, exit status 7). The handler stack seen during `re.match/search/fullmatch/sub/findall/split/finditer` shows the same `re/__init__.py` frames as CPython (10 rows).
- Big ints: a product, square, quotient, divmod, str, int(), format, pow, f-string left by a handler; operands intact afterwards and the squaring memo not poisoned (`big * big` and `big ** 2` after interrupts); nested products and str() from a handler (the scratch buffer is taken from the cache, so it is safe).
- About 230 "owed signal" rows (p5, 4 handler behaviours x 57 operations): the slot `__repr__` of list, dict, set, tuple, deque, OrderedDict, defaultdict, Counter, namedtuple, range, slice, dict_items, SimpleNamespace, exceptions, ints, floats, partial; the repr guard of a self-referential list or dict is left clean after a raise; str/repr/ascii/%/format/f-string/print into StringIO and into a counting writer; `list.sort(key=str)` leaving a permutation; raising in `__del__`, `__exit__`, generator finally, `__next__`; tracebacks (names and lines) and `__context__` of what comes out; the "Exception ignored" text on stderr. All equal except where D-25 (a) puts the handler (a weakref callback, `itertools.count().__repr__`).
- Exit paths with an owed signal (p11): end of main, uncaught exception, `sys.exit(3)`, `__del__` at exit; with and without a raising handler: same output order, same status.
- List methods (p4, 151 rows): sort/sorted with keys and comparisons that append, clear, pop, extend, reverse, sort, set, delete, insert, remove, `+=`, `*=` the list (all "list modified during sort" cases and what the list holds afterwards), a key or `__lt__` that raises, errors and messages of sort/extend/insert/remove/pop/index/count with `__index__` objects, big and float indexes, lying `__length_hint__`, list subclasses overriding `__len__`, `__iter__`, `__getitem__`, `__setitem__`, `append`, `__eq__`, `__iadd__`/`__imul__` returning NotImplemented, the slot wrappers `list.__iadd__` and `list.__imul__` (name, qualname, objclass, bound, unbound with a wrong self, keyword arguments), `__del__` of elements during clear, pop, `*= 0`, slice assignment, deletion and dealloc.
- Deleted names (p6, p9, 113+49 rows): global, shadowed builtin, `global` statement, local, closure cell, `del (a, b)`, `del [a, b]`, except variable, loop variable, parameter, `*args`, with variable, `locals()`/`dir()`/`vars()` after del, class body (twice, missing, enclosing local, global), attributes, dict keys, list items, 15 module attributes (`math.pi`, `math.sqrt`, itertools, time, errno, string, `os.sep`, `sys.maxsize`, `sys.platform`, dunder names): AttributeError/ImportError texts, `.name` and `.obj`, `dir`/`vars`, restoring; `__doc__`, `__name__` (class and function `__module__`), `__file__`, `__spec__`, `__loader__` deleted from the program; `sys.argv`, `sys.stderr`, `sys.path` deleted. Equal apart from the entries above.

### Not checked
- Whether a handler's frame line is right for a signal found at a function's first look (needs a nondeterministic arrival; D-25 covers where it runs).
- Memory misuse of `bn` on the exception path under a sanitizer (no ASan build available to me); read by hand: the scratch cache, the squaring memo and the 5^k cache are safe against a handler that does big-int work of its own.
- The BN_LOOK on `int()` of more than 6000 digits against `_pylong`; ints between 2**30 and 2**64 (D-25 (e)).
- Handler-raise in the middle of sort's own comparisons beyond `str` keys; `sys.unraisablehook` forms; threads and coroutines.
- Recursion depth inside `extract_stack` near the limit.

## Focus `names`

Read: the diffs and files of b661311, 611395b, ff4249a, bb9de1a, d9f6e0d, 306d1a5, 9c64ba9, 20b9c5e; DECISIONS entries and cases C-3-69..74, C-6-22; test_missing_names.py, tools/missing_names.py; CPython's cellobject/iterobject/exceptions(Unicode*Error)/bltinmodule(input)/fileobject(PyFile_GetLine)/_collectionsmodule(defdict_or)/namespaceobject.
Ran: 15 probe programs (p1-p10, m1-m5, r22-probes/names/), about 15,000 rows, each against CPython 3.15.2 (`-S` for the site-related ones) and compiled.

#### defaultdict | frozendict answers a plain dict
Severity: low (frozendict is new in 3.15; the operator is the same one C-3-73 fixed for OrderedDict, so a program mixing the two meets it)
Where: runtime/prelude/_collections.py:855 (`_dd_or`)
Repro:
```python
import collections
dd = collections.defaultdict(list, {1: 2})
r = dd | frozendict({1: 5})
print(type(r).__name__, r)
import types
r = types.MappingProxyType(dd) | frozendict({1: 5})
print(type(r).__name__, r)
```
CPython: `defaultdict defaultdict(<class 'list'>, {1: 5})` twice / Bella: `dict {1: 5}` twice (the default factory is lost; `r[99]` raises KeyError instead of giving `[]`).
Why: `_dd_or` tests `issubclass(type(other), dict)`; frozendict is not a dict subclass, so it returns NotImplemented and dict's own `|` gives a plain dict. defdict_or uses `PyAnyDict_Check(other)`. (`frozendict | defaultdict` and `OrderedDict | frozendict` are right.)

#### UnicodeEncode/Decode/TranslateError with start or end of 2**62 or more: str() prints "0--1"
Severity: low (needs offsets that large; a silent wrong message)
Where: runtime/src/bytes.cpp:1569-1594 (`encode_error_str`, `decode_error_str`, `translate_error_str`), runtime/src/ops.cpp:14 (`as_int`)
Repro:
```python
e = UnicodeEncodeError("ascii", "a€b", 1, 2, "why")
e.start = 2**62; e.end = 2**62 + 1
print(e.start, str(e))
print(str(UnicodeDecodeError("ascii", b"abc", 0, 2**62, "why")))
```
CPython: `4611686018427387904 'ascii' codec can't encode characters in position 4611686018427387904-4611686018427387904: why` and `... bytes in position 0-4611686018427387903: why`
Bella: `4611686018427387904 'ascii' codec can't encode characters in position 0--1: why` and `... position 0--1: why`
Why: the three __str__ read the members with `as_int`, which answers false for anything beyond an immediate and leaves `start = end = 0`. `e.start` itself is right (int_from_i64 in `unicode_set`). They should read the value with `int_fits_i64` as `unicode_set` does (Py_ssize_t members).

#### Unicode*Error constructor keeps start/end as given instead of converting to Py_ssize_t
Severity: low
Where: runtime/src/bytes.cpp:1504-1545 (`unicode_error_init`, `translate_error_init`)
Repro:
```python
class Idx:
    def __index__(self): return 1
e = UnicodeEncodeError("ascii", "a€b", Idx(), True, "why")
print(type(e.start).__name__, type(e.end).__name__, str(e))
e = UnicodeEncodeError.__new__(UnicodeEncodeError)
print(e.start, e.end)
try: UnicodeDecodeError("a", b"b", 2**70, 2, "c")
except OverflowError as x: print(x)
```
CPython: `int int 'ascii' codec can't encode characters in position 1-1: why` / `0 0` / `Python int too large to convert to C ssize_t`
Bella: `Idx bool 'ascii' codec can't encode character '\x61' in position 0: why` / `None None` / `cannot fit 'int' into an index-sized integer`
Why: `__init__` stores `a.pos(2)`/`a.pos(3)` raw (only checks `index_value`), so `e.start` returns the Idx object or True and `str()` treats a non-immediate as 0. UnicodeEncodeError_init/UnicodeDecodeError_init parse "n" into Py_ssize_t fields. The members are Py_ssize_t zero-initialised, so a never-initialised error reads 0, not None (C-3-73 made the setter convert, but not the init). UnicodeDecodeError with a str object also reports the object's TypeError before the later arguments' ("UOnnU" checks args in order: `UnicodeDecodeError('a','b',1,2,3)` is "argument 5 must be str, not int" in CPython); same class, different message, so D-08 may cover that part.

#### object's __lt__, __le__, __gt__, __ge__ do not check their arguments
Severity: low (only called by name with a wrong count; it also shows through any class that inherits them, e.g. typing.List[int].__lt__())
Where: runtime/src/types.cpp:1262 and 3295 (`object_notimplemented`)
Repro:
```python
class K: pass
k = K()
for f in (lambda: k.__lt__(), lambda: k.__lt__(1, 2), lambda: k.__lt__(other=1), lambda: object.__ge__(k)):
    try: print(f())
    except TypeError as e: print("TypeError", e)
```
CPython: `TypeError expected 1 argument, got 0` / `expected 1 argument, got 2` / `wrapper __lt__() takes no keyword arguments` / `expected 1 argument, got 0`
Bella: `NotImplemented` four times.
Why: `object_notimplemented(Obj, Args)` ignores `Args`; the slot wrapper of object's tp_richcompare (wrap_richcmpfunc) takes exactly one argument. mappingproxy's own copies (`proxy_unordered`) do check (`dunder_args`). Seen also as weakref.proxy(k).__lt__() and typing.List[int].__lt__(). (Not determined whether this predates the range; b661311 made these slot wrappers.)

#### Private slots of the prelude's classes are readable, assignable and clobbered by a subclass
Severity: low (DECISIONS 2026-11-06 says private slots "still show in vars()"; the effect on a subclass is the part not noted)
Where: runtime/prelude/iterating.py:101, 181, 270, 316, 360 (`__slots__ = ("_its", "_strict")`, `("_func", "_its", "_strict")`, `("_count", "_it")`, ...); the same for itertools, collections, _io, typing, operator, functools classes (vars() diff, p8)
Repro:
```python
class Tagged(map):
    def __init__(self, f, *its): self._func = "tag"
class Z(zip):
    def __init__(self, *a): self._its = ()
for f in (lambda: list(Tagged(abs, [-1, -2])), lambda: list(Z("ab", "cd")), lambda: enumerate("ab")._it, lambda: hasattr(zip("ab"), "_strict")):
    try: print(f())
    except Exception as e: print("EXC", type(e).__name__)
```
CPython: `[1, 2]` / `[('a', 'c'), ('b', 'd')]` / `EXC AttributeError` / `False`
Bella: `EXC TypeError` / `[]` / `<str_ascii_iterator object ...>` / `True`
Why: the iterators are Python classes with member-descriptor slots under ordinary names, so a user subclass using the same attribute name overwrites the iterator's state, and `vars(enumerate)` has `_count`, `_it` (also zip `_its`/`_strict`, map `_func`/`_its`/`_strict`, filter, reversed `_index`/`_seq`, ~110 more across itertools, collections, _io, typing, operator, functools). Also extra in vars(): types.GenericAlias `__slots__`, `__setattr__`, `__delattr__`, `__reduce_ex__` (functions, not object's slot wrappers: `types.GenericAlias.__setattr__ is object.__setattr__` is True in CPython, False here), the same two on typing.Union; `vars(str)['maketrans']` is a builtin_function_or_method, CPython's is a staticmethod (also bytes, bytearray).

#### weakref.ref / weakref.proxy of a types.SimpleNamespace succeed
Severity: low
Where: runtime/prelude (SimpleNamespace has a `__weakref__` getset_descriptor in vars)
Repro:
```python
import types, weakref
try: weakref.ref(types.SimpleNamespace()); print("ok")
except TypeError as e: print("TypeError", e)
```
CPython: `TypeError cannot create weak reference to 'types.SimpleNamespace' object` / Bella: `ok`
Why: C-3-74's case builds weakrefs to a plain class only; SimpleNamespace's tp_weaklistoffset is 0 in CPython, so `vars(types.SimpleNamespace)` has no `__weakref__` either (Bella: `getset_descriptor`).

#### Small differences around breakpoint() and sys.flags
Severity: low
Where: runtime/prelude/builtins.py:151 (`breakpoint`), sys.flags
Repro:
```python
import sys
sys.breakpointhook = 1
del sys.breakpointhook
try: breakpoint()
except RuntimeError as e: print(e)
print(sys.flags.no_site)
```
CPython (-S): `lost sys.breakpointhook` / `1`. Bella: breakpoint() takes the default path (a RuntimeWarning, returns None) / `0`.
Why: `sys.__dict__.get("breakpointhook", _NO_HOOK)` cannot tell "never set" from "deleted" (builtin_breakpoint raises RuntimeError "lost sys.breakpointhook"); and the compiled program answers as `python -S` (exit, quit, help are NameError) while sys.flags.no_site says 0.

### Checked and found clean
- Iterators (p1, p7; ~1,170 rows): __length_hint__, __reduce__, __reduce_ex__(0,2), __setstate__, copy/deepcopy at fresh, mid, exhausted, for list, tuple, str (ASCII, astral, surrogate, empty), bytes, bytearray, subclasses of list/tuple/set/frozenset/bytes/bytearray/dict, range (negative step, empty, bounds near 2**63, 2**64, huge), reversed variants, dict keys/values/items forward and reversed, OrderedDict (keys/values/items, forward and reversed, mutated), deque (forward, reversed, mutated), defaultdict, Counter, set, enumerate (start at sys.maxsize-1, 2**64, negative), zip (strict), map, filter, iter(callable, sentinel), old-protocol iterators and reversed(seq) with __setstate__ at -5, 0, big, 2**63, 2**70, float, str, None, bool, object; operator.length_hint with odd hints and during mutation of list, set, dict, bytearray, str. No difference.
- __reduce__ of range, slice, Ellipsis, NotImplemented, None, bound/unbound methods, private-name methods, classmethods, builtin functions (module, type, method), method/slot/member/getset/classmethod descriptors and method-wrappers, arity and wrong receiver (p1, ~120 rows). No difference.
- Closure cells (p2; 615 rows): all 6 operators over 9 kinds of content pairs (empty, int, str, NaN, list, complex, __eq__-overriding, NotImplemented-returning), hash, repr (with a 100-character type name modulo address width), cell_contents, deletion, CellType(), recursive contents, raising __eq__, identical contents, set/dict membership. No difference.
- mappingproxy (p3; ~1,600 rows): |, reflected |, |=, and 6 comparisons against 16 operand kinds from 9 proxy kinds (dict, OrderedDict, user Mapping, defaultdict, nested proxy, dict subclass with __or__, Counter, ChainMap, UserMapping with __or__); reversed, hash (including big, negative, non-int __hash__), copy, direct calls with wrong arity and wrong receiver. Only the defaultdict|frozendict row differed.
- Unicode errors (p4; 576 rows): 5 members x 18 values on all three classes, deleting, double-deleting, repr/reduce/copy after deleting, mutating members from inside __str__ of reason/encoding, start/end sweep (13 pairs), constructors with 20 argument shapes, __new__ without __init__, real codec errors modified. Differences listed above only.
- Comparison types (p5; ~6,700 rows): SimpleNamespace (also subclass), weakref.ref (live, dead, callback, subclass, proxy), contextvars.Context, ParamSpec args/kwargs, GenericAlias (including starred, typing.List, Callable), 6 operators among 24 values and against 7 other operands, both directions, by-name calls with 0/1/2 args and keywords, wrong receivers. Only the arity row (object's orderings) differed.
- ~ on bool (p5, p10; ~40 rows): result, DeprecationWarning text, line numbers in multi-line expressions, comprehension, lambda, class body, f-string, filters error/ignore/default/module/once/always, message/category filters, showwarning hook, formatted stderr line, traceback line under an error filter, __context__/__cause__ None, bool.__invert__ vs int.__invert__ wrong arity. No difference.
- input() (p6; ~75 rows over stand-in streams, plus 8 rows over a real pipe): prompt kinds (None, str subclass, raising __str__, int, bytes, NUL, surrogate), 0-3 arguments and keywords, EOF, lone \r, \r\n, bytes line, int/list line, str-subclass line, lost/deleted/None streams, failing write and flush, missing methods, fileno variants (0, 5, str, float, __index__, 2**70, -1, raising), order of the calls the streams see, __context__ on EOFError, StringIO/BytesIO/TextIOWrapper stdin, invalid UTF-8 from a real stdin (surrogateescape), __name__/__doc__/repr. The terminal branch cannot be reached without a tty (not run). No difference.
- Names site adds (p6): exit, quit, copyright, credits, license, help: NameError, AttributeError on builtins, absent from dir(builtins); assigning and deleting builtins.exit; dir(builtins) lists. No difference against `python -S` apart from sys.flags.no_site.
- Names tables (p8, p9; ~2,700 own-name rows over ~120 types and 20 modules, ~1,400 docstring rows): every name CPython has and the runtime lacks is on conformance/names-baseline.txt (spot-checked 13); kinds (wrapper_descriptor/method_descriptor/...), `__doc__` presence and docstring text match for all names both have, except the rows above. Docstrings of module functions and methods match CPython's text.

### Not checked
- input() on a terminal (PyOS_Readline branch, signals while reading, prompt encoding): no tty in the harness. breakpoint() with PYTHONBREAKPOINT naming a hook (a stop by name).
- Exception types' own dicts (vars of UnicodeError etc.): asking the kind of their slot functions stops by name (`type of UnicodeEncodeError.__str__`), so names only were compared through the case, not through vars().
- array iterators, memoryview, itertools' pickling (not in the range).
- `import site` / `_sitebuiltins` (a stop by name), sys.breakpointhook read, `__text_signature__`, frame attributes (stops).
- The C++ for memory misuse was read for the iterator `__reduce__`/`__setstate__` paths only through behaviour; no crash, hang or sanitizer-visible failure appeared in any run.

## Focus `today-misc`

Read: bc3f700 and 98272cf in full (prelude zlib/binascii/posix/_signal/_ast, harness, simulate/sitecustomize, staging/run.py, C-7-89/90/91, test_unsigned_arguments.py, test_runtime_reports.py, call.cpp print_traceback/write_unraisable/uncaught path), against CPython 3.15.2's getargs.c, Python-ast.c, longobject.c (PyLong_AsNativeBytes), pythonrun.c, errors.c, traceback.py.
Ran: 14 probe programs (p1-p12, m1; about 22 builds), about 12,600 rows/modes (p3 5954, p4 4721, p9 1052, p5 390, p1 126 reports, p2 96 uncaught/hook/exit modes, p6/p7/p10/p11/p12/m1 about 90 modes); compiled binaries re-run per mode from build/compiled/<prog>-*/ (no rebuild).

Summary: the integer converters (os, zlib, binascii, signal, struct, time, hash/blake2 parameters), the `_unsigned` warnings of C-7-90, and the AST prelude of C-7-91 are clean against CPython on everything I tried. The defects are in the runtime's own report of an exception (D-28's subject), which is a port of traceback.py that stops short of it in several ways, plus two crashes in it.

#### A wrong-argument-count call carries an extra traceback entry for the callee (report and `__traceback__`)
Severity: medium (any uncaught call with the wrong number of arguments; also what `traceback.extract_tb` or `tb_next` sees)
Where: the binding of a compiled function's parameters (not located precisely; the entry is added when the callee's frame record is already pushed); seen through runtime/src/call.cpp:2699 (emit_stack) and the traceback entries
Repro:
```python
import traceback
def f():
    pass
try:
    f(1)
except TypeError as e:
    print([(x.name, x.lineno) for x in traceback.extract_tb(e.__traceback__)])
    print(e.__traceback__.tb_next is None)
f(1)
```
CPython: `[('<module>', 9)]` / `True`; the uncaught report has one `File ..., line 11, in <module>` line, then `TypeError: f() takes 0 positional arguments but 1 was given`.
Bella: `[('<module>', 9), ('f', 6)]` / `False`; the report has a second entry `File ..., line 6, in f` (the def line). Same for missing keyword-only arguments, bound methods and `K()` with a failing `__init__` signature (p6 argcount, kwmissing, argcount_method, typeerror_in_class_call; a builtin's arity error, `len()`, is right).
Why: CPython raises the binding error in the caller (initialize_locals, before the frame runs), so no entry for the callee exists. The same entry shows in "Error in sys.excepthook:" when the hook takes the wrong number of arguments (p2 hook_wrongargs).

#### The report never folds repeated frames: an uncaught RecursionError prints about 1000 lines
Severity: medium (an uncaught RecursionError, or any frame repeated more than three times in a row, is an ordinary program)
Where: runtime/src/call.cpp:2699 (emit_stack)
Repro:
```python
def rec(n):
    return rec(n + 1)
rec(0)
```
CPython (stderr, 12 lines): `File ..., line 2, in rec` three times, then `  [Previous line repeated 996 more times]`, then `RecursionError: maximum recursion depth exceeded`.
Bella: 1002 lines, `File ..., line 2, in rec` printed for every frame. With 6 nested calls of one frame CPython prints three entries and `[Previous line repeated 3 more times]`; Bella prints six (m1 repeat5, p2 deep).
Why: Lib/traceback.py StackSummary.format collapses a run of identical (file, line, name) after _RECURSIVE_CUTOFF = 3 entries; the port copies TracebackException.format but its emit_stack prints each entry. D-06 covers the source lines and carets only, and the harness's mask keeps the `[Previous line repeated` line, so a case with a deep recursion would fail; none exists. DECISIONS 2026-11-12 says the folding is "CPython's text" for `traceback`'s own functions; the runtime's own printer has none.

#### `sys.tracebacklimit` is ignored by the runtime's report
Severity: low
Where: runtime/src/call.cpp:2699
Repro:
```python
import sys
sys.tracebacklimit = 0
raise ValueError("x")
```
CPython: `ValueError: x` only (limit 0: no header, no frames); with `sys.tracebacklimit = 1` and two frames deep, only the innermost `File ..., in g` line. Negative values act as 0; a non-int is ignored.
Bella: the whole traceback (`Traceback (most recent call last):` and every frame) in all four cases (p2 limit0, limit2, limitneg, limitbad, m1 limit0, limit1).
Why: traceback.py `print_exception(limit=BUILTIN_EXCEPTION_LIMIT)` reads `getattr(sys, 'tracebacklimit', None)` (lines 513-515); the port does not.

#### A group whose `exceptions` is not a tuple crashes the runtime (SIGSEGV)
Severity: low (needs a property that overrides `ExceptionGroup.exceptions`), but it is a memory-misuse crash
Where: runtime/src/call.cpp:2657 and :2664 (`static_cast<Tuple*>(parts.get().object())->items`)
Repro:
```python
class G(ExceptionGroup):
    @property
    def exceptions(self):
        return None
raise G("g", [ValueError(1)])
```
CPython: exit 1, `Traceback (most recent call last): ... GN: g (1 sub-exception)` (traceback.py raises TypeError, `_PyErr_Display` falls back to the C printer, which prints it as an ordinary exception).
Bella: exit status 139 (segmentation fault), nothing printed (p7 group_none, m1 group_none). A property returning a `list` is read as a tuple by accident of layout and prints correctly (p7 group_list); an iterator, a tuple of non-exceptions, or a raising property stop by name or print differently (p7 group_iter, group_nonexc, group_raises).
Why: the cast is done without checking the type. CPython's traceback code iterates whatever `exc_value.exceptions` gives.

#### An exception that escapes the report ends the process with std::terminate (SIGABRT)
Severity: low (needs a `__notes__` that is a Sequence whose iteration raises, or a property raising a BaseException; plausible only in odd code)
Where: runtime/src/call.cpp:2630 (rethrows a non-Exception from `__notes__`), :2718 (`list(notes)` unguarded), :3125-3128 (second print_traceback inside the `catch` of report_uncaught)
Repro:
```python
import collections.abc
class Seq(collections.abc.Sequence):
    def __len__(self): return 1
    def __getitem__(self, i): raise RuntimeError("no notes today")
e = ValueError("m")
e.__notes__ = Seq()
raise e
```
CPython: exit 1; the traceback is printed (twice, since the traceback module fails after writing it and the C printer repeats it), no notes.
Bella: prints the traceback, then `Error in sys.excepthook:` with the RuntimeError, `Original exception was:` and the traceback header, then `terminate called after throwing an instance of 'bella::PyError'`, exit 134 (core dump). Same with a `__notes__` property raising KeyboardInterrupt (m1 notes_ki, p7 notes_ki_uncaught), and with a list subclass whose `__iter__` raises (p10).
Why: print_traceback throws a PyError; report_uncaught handles it once (hook failure), but the "Original exception was" print is made inside the handler and throws again, out of run_main's catch handler, whose enclosing try only catches NotImplemented. CPython's `_PyErr_Display` clears the error and prints with the C code instead. Called directly (`sys.__excepthook__`) the error reaches the caller instead of being absorbed (p1 NP2, p10 notes_seq_raises_hook). In a `__del__` the same exception gives `Exception ignored in sys.unraisablehook: <built-in function unraisablehook>` plus the KeyError/RuntimeError, where CPython prints the report of the original exception (p7 notes_ki_del, p10 notes_seq_raises_del).

#### Module-level objects with `__del__` are finalised at exit in Bella, but never in CPython once a hook defined in `__main__` is installed
Severity: medium (a script that sets `sys.excepthook` (or `sys.unraisablehook`, `sys.displayhook`, `threading.excepthook`) to its own function and has an object with `__del__` or a context that prints at exit)
Where: runtime/src/call.cpp:2853 (finalizable_from) and :2978 (clear_modules): the walk finalises everything reachable from the module namespaces whether or not something else still references the namespace
Repro:
```python
import sys
class D:
    def __del__(self):
        print("D.__del__ ran")
keep = D()
def hook(t, v, tb):
    print("hook ran")
sys.excepthook = hook
raise KeyError("k")
```
CPython: `hook ran` only (exit 1). `D.__del__` never runs: the module dict is referenced by `hook.__globals__` from sys, so the cycle dict -> D -> `__del__` -> dict is not garbage when the collector runs at shutdown.
Bella: `hook ran`, then `D.__del__ ran`. Same without any exception (`sys.excepthook = hook` and end of the script), with `sys.unraisablehook`, `sys.displayhook`, `threading.excepthook`, and with a lambda; CPython runs `__del__` normally when the hook is restored to `sys.__excepthook__`, when `sys.stdout` is replaced by an object of a class from `__main__`, for signal handlers and for atexit callbacks (p11, p12; Bella agrees on all of these).
Why: finalisation order at exit is in D-07 and D-19, but "never finalised" is CPython's observable here and the spec (section 9) says module globals are finalised. A deviation entry, or reachability from sys, is missing.

#### SyntaxError reports have none of the SyntaxError layout
Severity: low (SyntaxError objects are made by hand only: no parser, E-01)
Where: runtime/src/call.cpp:2705 (emit_exception_only prints `type: str(exc)` for every class)
Repro:
```python
raise SyntaxError("invalid syntax", ("file.py", 3, 5, "x y z\n", 3, 6))
```
CPython (after the frame lines):
```
  File "file.py", line 3
    x y z
        ^
SyntaxError: invalid syntax
```
Bella: `SyntaxError: invalid syntax (file.py, line 3)`. Also `raise SyntaxError()`: CPython `SyntaxError: <no detail available>`, Bella `SyntaxError: None`. 25 of the 29 SyntaxError/IndentationError/TabError rows of p1 differ (offsets, end spans, tabs, wide characters, notes). D-28's note names only the keyword hint.
Why: traceback.py `TracebackException._format_syntax_error` is not ported.

#### Writes to a replaced `sys.stderr` are split differently and the report ends with a `flush()`
Severity: low (a wrapper around `sys.stderr` that counts or timestamps writes)
Where: runtime/src/call.cpp:2698 (emit) and :2798 (`err.flush()`)
Repro:
```python
import sys
class Cap:
    def __init__(self): self.w = []; self.f = 0
    def write(self, s): self.w.append(s); return len(s)
    def flush(self): self.f += 1
c = Cap(); old = sys.stderr; sys.stderr = c
e = ValueError("v"); e.__cause__ = KeyError("k")
sys.__excepthook__(type(e), e, None)
sys.stderr = old
print(c.w, c.f)
```
CPython: `["KeyError: 'k'\n", '', '\nThe above exception was the direct cause of the following exception:\n\n', '', 'ValueError: v\n', ''] 0`
Bella: `["KeyError: 'k'\n", '\n', 'The above exception was the direct cause of the following exception:\n', '\n', 'ValueError: v\n'] 1`
The text is the same; the number and boundaries of `write` calls (CPython writes each line then an empty string, from `print(line, end='')`) and the single `flush` differ (p6, 12 rows). With a `write` that fails after N calls CPython repeats the report through the C printer; Bella stops at the failure.

#### Reports when `sys.stderr` is None, deleted or unusable
Severity: low
Where: runtime/src/call.cpp:2508 (write_unraisable) and the stderr helpers used by print_traceback / exit_status
Repro: `import sys; sys.stderr = None; raise SystemExit("bye")` prints `bye` on the C stderr in CPython (handle_system_exit falls back to `PyObject_Print(exc, stderr)`); Bella prints nothing (exit status 1 in both). `import sys; del sys.stderr; raise ValueError("x")`: CPython writes `object address ... lost sys.stderr` (PyErr_Display, no stderr attribute), Bella prints the ordinary traceback. A closed `io.StringIO` as stderr: CPython prints the object dump and `lost sys.stderr`, Bella prints nothing. (m1 systemexit_stderr_none, stderr_deleted; p2 stderr_closed.) The exit statuses agree in all of these.

#### `sys.__unraisablehook__` with a value that is no exception and whose `str()` raises propagates the error
Severity: low
Where: runtime/src/call.cpp:2540 (`Ref text = str_of(value);` unguarded)
Repro:
```python
import sys
got = []; sys.unraisablehook = got.append
class D:
    def __del__(self): raise ValueError("v")
d = D(); del d
class Bad:
    def __str__(self): raise RuntimeError("badstr")
sys.__unraisablehook__(type(got[0])((ValueError, Bad(), None, "m", None)))
```
CPython: `m:` then `ValueError: <exception str() failed>`, exit 0. Bella: `m:` then a RuntimeError traceback from `Bad.__str__`, exit 1 (m1 unraisable_str_raises).
Why: write_unraisable_exc_file wraps `PyFile_WriteObject(exc_value)` in a clear-and-substitute; the port does not.

#### The report reads `__module__` from the class dict, not through the metaclass
Severity: low
Where: runtime/src/call.cpp:2622 (`type->attrs.find("__module__")`)
Repro: a metaclass defining a `__module__` property returning `"meta.mod"`; `sys.__excepthook__(E, E("m"), None)`.
CPython: `meta.mod.E: m` (traceback.py reads `exc_type.__module__`, which finds the metaclass data descriptor first). Bella: `E: m` (m1 metaclass_module; p1 "module via metaclass property").

#### A conformance case with two `# deviation:` lines is simulated differently by the harness and by the staging replay
Severity: low (no case has two; D-27 and D-28 can well meet in a later case)
Where: conformance/harness.py:96-111 (`fields[m.group(1)] = ...`: the last line wins) against pipeline/staging/run.py:46-52 (`declares`: any line counts)
Repro: a case file with `# deviation: D-27` and `# deviation: D-28` in its header: `read_header(path).deviation` is `'D-28'` while `declares(path, "D-27")` and `declares(path, "D-28")` are both True (run on a temp case).
Why: the harness records and checks the case against the D-28 expectation alone (only `warnings` stays importable, which D-27 needs absent), the staging replay blocks both modules.

#### Smaller differences from the integer sweep
Each is a single row; none is in C-7-90/91.
- `time.asctime`/`time.strftime` with a tuple whose weekday is 2**31-1: CPython `ValueError: day of week out of range` (the C `(wday + 1) % 7` overflows), Bella accepts and prints `Tue` (p3 rows 3997, 4270; p6). Low.
- `zlib.crc32_combine(5, 5, None)` and `zlib.adler32_combine(5, 5, None)`: CPython `TypeError: crc32_combine() argument 3 must be int, not None`, Bella `... not NoneType` (runtime/prelude/zlib.py:656 uses `_tp_name`; the clinic's `_PyArg_BadArgument` says `None` for None). Low (message of a ported text).
- `[1, 2, 3].index(2, v)` and `.index(2, 0, v)` with a float subclass that defines `__index__`: CPython uses the index (`ValueError`/`1`), Bella `TypeError: slice indices must be integers or have an __index__ method` (p4). Low.
- `os.getrandom(1, 6)` and `os.getrandom(1, 7)` (GRND_RANDOM|GRND_INSECURE): CPython `OSError: [Errno 22]`, Bella returns one byte. Under gdb the Bella binary makes no getrandom syscall for these calls: the libc's vDSO getrandom answers without checking the flag combination, where the pinned CPython's libc goes to the kernel. Environmental (libc), noted for completeness; runtime/src/posix.cpp:883 would need `syscall(SYS_getrandom, ...)`. Low.

### Checked and found clean
- C-7-90 `_unsigned`, `_unsigned_int_mask`, `_unsigned_bits`, pthread_kill: 18 sites (zlib.crc32/adler32 and both combines, binascii.crc32, os.memfd_create) against 47 values (all widths around 2**15/2**31/2**32/2**63/2**64/2**100, negatives, bool, int subclass, `__index__` objects including a bad one, float, float subclass with `__index__`, str, bytes, None, list, complex): result or exception class and message, the DeprecationWarning (text, category, file, line), and the same under an error filter: no difference (p4, p3). Also the "k" format of posix_spawn's open action and `i`, fd and id converters (p9, 1052 rows).
- Fixed-width converters of the preludes, about 11,000 rows: os (chmod, open, mkdir, umask, chown, makedev/major/minor, mknod, lseek, ftruncate, pread/pwrite, read, dup/dup2, fstat, set_inheritable, strerror, urandom, getpgid, getpriority, sysconf, confstr, fpathconf, W* macros, sendfile, fallocate, fadvise, lockf, eventfd, ttyname, getrandom, pidfd_open, kill/killpg, waitpid, utime, listdir/scandir fd, copy_file_range, splice, timerfd_create, sched_*, setuid family, spawn file actions), time (sleep, gmtime, localtime, ctime, asctime/mktime/strftime for each tuple field, clock_*), signal (signal, getsignal, strsignal, raise_signal, alarm, siginterrupt, setitimer, set_wakeup_fd, pthread_sigmask, pthread_kill), struct (every integer code, pack_into, unpack_from), zlib (every level/method/wbits/memLevel/strategy/bufsize/max_length/length parameter), binascii (hexlify, b2a_base64, a2b_base64), blake2 parameters, shake digest length, itertools, bisect, str/bytes/list index arguments, math. Class, message (except those listed above), and warnings agree; the other differences are D-08 wording ("signed integer is greater than maximum" for "Python int too large to convert to C long" in time's tuple fields) and the `P` format with an `__index__` object that overflows (`struct.error` in Bella, `OverflowError` in CPython; one pair of rows).
- C-7-91 and the AST prelude, 390 rows (p5): every node class constructed with none/some/too many/unknown/duplicate arguments, defaults of list, optional and context fields, `_field_types`, `_fields`/`__match_args__`/`_attributes`/`__doc__`/`__mro__` of 18 classes, subclasses with their own `_fields` (tuple, list, string, missing `_field_types`), `__init__` calling super, the 13 abstract classes and their derived classes, repr (depth, lists, cycles, an `__eq__`-always-true node, odd constants), copy/deepcopy/`__reduce__`/`copy.replace`/`__replace__` (missing fields, unknown keywords, deleted attributes), dump/unparse/walk/NodeVisitor/NodeTransformer/literal_eval on built trees, and the default-filter warning output (once per line, line numbers, `-W error`): identical. (pickle stops by name.)
- The runtime's own report of an exception (p1, 126 reports through `sys.__excepthook__`; p2, p7, p10: about 130 modes through the uncaught path): causes and contexts to depth 5 and 20,000, cycles, self-reference, suppress_context, shared exceptions, groups (nested, 15/16/20 members, depth 13, 3,000 deep, 100,000 wide, same exception twice, with causes, notes, subclasses, a raising `__str__`), notes of every odd type (str, bytes, int, range, dict, set, custom Sequence, iterable, raising `__str__`, deleted, str subclass), `__str__` raising/non-str/empty/multi-line/NUL/surrogate/recursing, `__module__` and `__qualname__` odd values, KeyboardInterrupt, `StopIteration`, Unicode errors, ImportError/NameError fields; SystemExit with None, 0, 3, True, False, str, float, tuple, object, bad `__str__`, 2**31, 2**32+7, 2**63, 2**64, -1, -2, -2**63, -2**63-1, int subclass, bytes, list, empty str, deleted/changed `code`, two arguments, subclass; sys.excepthook replaced, raising, raising SystemExit/KeyboardInterrupt, set to None/int/deleted, calling the default, chained failures; sys.stderr replaced, StringIO, raising write, no write; exceptions in `__del__`, atexit callbacks, generator close (ignored and failing), weakref callbacks, a custom unraisablehook (raising, None, deleted, exiting), default hook rows with 15 argument combinations; stdout closed or failing flush at exit (status 120). Stdout, stderr (after D-06 and the "Did you" cut) and exit status agree, except for what is listed above.
- The D-28 harness side: `SIMULATIONS`/`simulation_env` block `traceback` before the case runs and `record` requires the two traces to differ; I found no way for a case to pass by accident: a runner that prints CPython's additions would differ from `C-7-89...D-28.json`, and CPython's C printer also folds repeated frames and honours `sys.tracebacklimit` and the SyntaxError layout, so a case that declared D-28 with those would fail rather than hide them (the first two and SyntaxError are the findings above, so such a case cannot be added until they are fixed). The guard "the traces differ" does not check that the difference is the cut after the message. `pipeline/tests/test_runtime_reports.py` returns without running (so passes) when no `g++` is present (`_both` returns None).

### Not checked
- pickle of AST nodes (stop by name), `os.statx` (absent), `binascii.crc_hqx`/`b2a_qp`/`a2b_qp`/uu (stop by name), `hashlib.pbkdf2_hmac` (absent), `sys.setprofile`, `sys._getframe`, `traceback`'s `tb_frame` (stops by name).
- Integer thread ids for `signal.pthread_kill` and `time.pthread_getcpuclockid` beyond the author's test (CPython itself segfaults for an invalid id, e.g. `time.pthread_getcpuclockid(2**64)` wraps to 0); only non-int arguments compared.
- Warnings attributed to an imported module's line (single-file programs only); sub-interpreters; threads; coloured tracebacks when stderr is a terminal (`_safe_can_colorize`); real signals during the report; a report written to a full disk.
- `sys.stderr` partially failing in the middle of a chained report (only the p6 write-count rows); the `Exception ignored in` lines for objects whose `repr` has side effects.
