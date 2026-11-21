Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-21, the cross-check the author asked for after each step. Verbatim. Tag A31 in the
review log. Its range is `30cd727..ad307d1`, run non-interactively (standard input closed) in its own worktree (`bella-r31`) at `ad307d1`: the
fixes of review A30 (RL-643 to RL-654), the retries after EINTR (RL-656) and the type tests of the preludes (RL-655), and beside the last the
question the session put to it: an argument that is an instance of a subclass of str, int, bytes, tuple, list or dict whose class overrides
methods, where CPython's C reads the object's own data. Its probes (`r31-probes/codex/`, the links below) stayed in that worktree. 41
findings; each was run on both sides by the session before any verdict (review log, A31).

---

# Bella conformance review A31

**41 confirmed findings at ad307d1.** Bella's `hmac.compare_digest` returned True for unequal stored bytes (A31-32). SHA-256 and HMAC consumed different bytes from CPython (A31-11 and A31-33). JSON serialized a dictionary entry as `{"other": "other"}` where CPython wrote `{"key": 1}` (A31-26). I use High for these comparison, digest and serialization results. Each numbered finding below has a reproducer.

Detached `ad307d1`, range `30cd727..ad307d1`, CPython 3.15.2 on Linux. Each finding links the exact runnable program and captured results. Each row ran in a fresh process with `PYTHONHASHSEED=0`, `ulimit -v 8000000` and a 120-second timeout. The following commands reproduce A31-32 from the checkout root. Substitute the probe directory and two arguments given in each finding for the other cases.

```sh
P=r31-probes/codex/digests
set -- 3 log
export PYTHONHASHSEED=0
ulimit -v 8000000
binary=$(timeout 600 ./r31-build "$P/prog.py")
timeout 120 .venv/bin/python "$P/prog.py" "$@"
timeout 120 "$binary" "$@"
```

For subclass findings the displayed expression is the minimal call. In the exact probe, S, I, F, B, A, T, L and D subclass str, int, float, bytes, bytearray, tuple, list and dict respectively. Each instrumented method records its name, then delegates to the base implementation in `log` mode or raises ArithmeticError in `raise` mode. The program snapshots the log before formatting the result. Tables show stdout without its final newline. Unless specified, stderr is empty and both exit statuses are zero.

## A31-01 · Medium · Opening a file indexes the original mode object

`runtime/prelude/_io.py:3627`. The mode parser reads the base string length, then evaluates shown[i] on the original object for each character. A subclass can interrupt validation before the file opens.

| Minimal call | Arguments and evidence | CPython stdout | Bella stdout |
|---|---|---|---|
| `open("/dev/null",S("r")).close()` | [0 log](r31-probes/codex/subclasses/0-log) · [program](r31-probes/codex/subclasses/prog.py) | `None []` | `None ['__getitem__']` |
| `open("/dev/null",S("r")).close()` | [0 raise](r31-probes/codex/subclasses/0-raise) · [program](r31-probes/codex/subclasses/prog.py) | `None []` | `ArithmeticError ['__getitem__']` |

Reduced program (driver arguments `0 log`):

```python
class Mode(str):

    def __getitem__(self, i):
        raise LookupError()
try: print(repr(open('/dev/null', Mode('r')).close()))
except Exception as e: print(type(e).__name__)
```

CPython prints `None`. Bella prints `LookupError`. [Driver](r31-probes/codex/reduced/prog.py) · [Captures](r31-probes/codex/reduced/0-log)

## A31-02 · Medium · TextIOWrapper compares the original encoding and newline objects

`runtime/prelude/_io.py:2893`. The locale encoding check uses ==. Newline validation and translation setup also use ordinary comparisons at lines 2581 and 2758. CPython reads the character data for both options.

| Minimal call | Arguments and evidence | CPython stdout | Bella stdout |
|---|---|---|---|
| `open("/dev/null",encoding=S("utf8")).close()` | [1 log](r31-probes/codex/subclasses/1-log) · [program](r31-probes/codex/subclasses/prog.py) | `None []` | `None ['__eq__']` |
| `open("/dev/null",encoding=S("utf8")).close()` | [1 raise](r31-probes/codex/subclasses/1-raise) · [program](r31-probes/codex/subclasses/prog.py) | `None []` | `ArithmeticError ['__eq__']` |
| `open("/dev/null",newline=S("")).close()` | [3 log](r31-probes/codex/subclasses/3-log) · [program](r31-probes/codex/subclasses/prog.py) | `None []` | `None ['__ne__', '__eq__', '__ne__']` |
| `open("/dev/null",newline=S("")).close()` | [3 raise](r31-probes/codex/subclasses/3-raise) · [program](r31-probes/codex/subclasses/prog.py) | `None []` | `ArithmeticError ['__ne__']` |

Reduced program (driver arguments `1 log`):

```python
class Encoding(str):

    def __eq__(self, other):
        raise LookupError()
try: print(repr(open('/dev/null', encoding=Encoding('utf8')).close()))
except Exception as e: print(type(e).__name__)
```

CPython prints `None`. Bella prints `LookupError`. [Driver](r31-probes/codex/reduced/prog.py) · [Captures](r31-probes/codex/reduced/1-log)

## A31-03 · Medium · BytesIO.write calls the input’s __bytes__

`runtime/prelude/_io.py:260`. The same helper is reached by FileIO.write, BufferedWriter.write, the BytesIO constructor and BytesIO.writelines. [FileIO](r31-probes/codex/details/23-log) · [BufferedWriter](r31-probes/codex/details/24-log) · [Constructor](r31-probes/codex/details/26-log) · [Writelines](r31-probes/codex/details/27-log)

A bytearray subclass with its own __bytes__ produces the same error in data selection. BytesIO initialized with the stored bytes `buf` returns `buf` under CPython and `override` under Bella. [Bytearray case](r31-probes/codex/lifetimes/5-log)

The buffer helper calls bytes(value). A bytes subclass can intercept that conversion. CPython consumes its buffer directly.

| Minimal call | Arguments and evidence | CPython stdout | Bella stdout |
|---|---|---|---|
| `io.BytesIO().write(B(b"ab"))` | [7 log](r31-probes/codex/subclasses/7-log) · [program](r31-probes/codex/subclasses/prog.py) | `2 []` | `2 ['__bytes__']` |
| `io.BytesIO().write(B(b"ab"))` | [7 raise](r31-probes/codex/subclasses/7-raise) · [program](r31-probes/codex/subclasses/prog.py) | `2 []` | `ArithmeticError ['__bytes__']` |

Reduced program (driver arguments `3 log`):

```python
import io
class Data(bytes):

    def __bytes__(self):
        return b'other'
def write():
    f = io.BytesIO()
    f.write(Data(b'x'))
    return f.getvalue()
try: print(repr(write()))
except Exception as e: print(type(e).__name__)
```

CPython prints `b'x'`. Bella prints `b'other'`. [Driver](r31-probes/codex/reduced/prog.py) · [Captures](r31-probes/codex/reduced/3-log)

## A31-04 · Medium · A bytes path intercepts the embedded-NUL check

`runtime/prelude/posix.py:935`. The path converter uses membership on the original bytes object. CPython checks the underlying path buffer.

| Minimal call | Arguments and evidence | CPython stdout | Bella stdout |
|---|---|---|---|
| `os.stat(B(b"/dev/null")).st_size` | [13 log](r31-probes/codex/subclasses/13-log) · [program](r31-probes/codex/subclasses/prog.py) | `0 []` | `0 ['__contains__']` |
| `os.stat(B(b"/dev/null")).st_size` | [13 raise](r31-probes/codex/subclasses/13-raise) · [program](r31-probes/codex/subclasses/prog.py) | `0 []` | `ArithmeticError ['__contains__']` |

Reduced program (driver arguments `4 log`):

```python
import os
class Path(bytes):

    def __contains__(self, item):
        raise LookupError()
try: print(repr(os.stat(Path(b'/dev/null')).st_size))
except Exception as e: print(type(e).__name__)
```

CPython prints `0`. Bella prints `LookupError`. [Driver](r31-probes/codex/reduced/prog.py) · [Captures](r31-probes/codex/reduced/4-log)

## A31-05 · Medium · JSON asks the source sequence for a length hint

`runtime/prelude/_json.py:693`. The subclass branch materializes list(seq), which asks the original source for its length. CPython materializes the iterator and only invokes the source’s __iter__.

| Minimal call | Arguments and evidence | CPython stdout | Bella stdout |
|---|---|---|---|
| `json.dumps(L([1]))` | [23 log](r31-probes/codex/subclasses/23-log) · [program](r31-probes/codex/subclasses/prog.py) | `'[1]' ['__iter__']` | `'[1]' ['__iter__', '__len__']` |
| `json.dumps(T((2,)))` | [24 log](r31-probes/codex/subclasses/24-log) · [program](r31-probes/codex/subclasses/prog.py) | `'[2]' ['__iter__']` | `'[2]' ['__iter__', '__len__']` |

Reduced program (driver arguments `5 log`):

```python
import json
class Array(list):

    def __len__(self):
        raise LookupError()
try: print(repr(json.dumps(Array([1]))))
except Exception as e: print(type(e).__name__)
```

CPython prints `'[1]'`. Bella prints `LookupError`. [Driver](r31-probes/codex/reduced/prog.py) · [Captures](r31-probes/codex/reduced/5-log)

## A31-06 · Medium · Registering a codec error handler calls name comparisons

`runtime/prelude/_codecs.py:338`. The check against the built-in handler names precedes normalization to an exact string, so the user’s equality method runs once per candidate.

| Minimal call | Arguments and evidence | CPython stdout | Bella stdout |
|---|---|---|---|
| `codecs.register_error(S("probe"),codecs.strict_errors)` | [34 log](r31-probes/codex/subclasses/34-log) · [program](r31-probes/codex/subclasses/prog.py) | `None []` | `None ['__eq__', '__eq__', '__eq__', '__eq__', '__eq__', '__eq__', '__eq__', '__eq__']` |
| `codecs.register_error(S("probe"),codecs.strict_errors)` | [34 raise](r31-probes/codex/subclasses/34-raise) · [program](r31-probes/codex/subclasses/prog.py) | `None []` | `ArithmeticError ['__eq__']` |

Reduced program (driver arguments `6 log`):

```python
import codecs
class Encoding(str):

    def __eq__(self, other):
        raise LookupError()
try: print(repr(codecs.register_error(Encoding('probe'), codecs.strict_errors)))
except Exception as e: print(type(e).__name__)
```

CPython prints `None`. Bella prints `LookupError`. [Driver](r31-probes/codex/reduced/prog.py) · [Captures](r31-probes/codex/reduced/6-log)

## A31-07 · Medium · Warning filter validation calls tuple subclass methods

`runtime/prelude/_warnings.py:211`. The filter loop takes len(item) and unpacks item. CPython reads the five tuple slots directly. The row first installs an ignore filter and prepends its tuple-subclass equivalent.

| Minimal call | Arguments and evidence | CPython stdout | Bella stdout |
|---|---|---|---|
| `warning("filter")` | [35 log](r31-probes/codex/subclasses/35-log) · [program](r31-probes/codex/subclasses/prog.py) | `None []` | `None ['__len__', '__iter__']` |
| `warning("filter")` | [35 raise](r31-probes/codex/subclasses/35-raise) · [program](r31-probes/codex/subclasses/prog.py) | `None []` | `ArithmeticError ['__len__']` |

Reduced program (driver arguments `7 log`):

```python
import warnings
class Filter(tuple):

    def __len__(self):
        raise LookupError()
def filtering():
    warnings.filters.insert(0, Filter(('ignore', None, Warning, None, 0)))
    warnings.warn('text')
try: print(repr(filtering()))
except Exception as e: print(type(e).__name__)
```

CPython prints `None`. Bella prints `LookupError`. [Driver](r31-probes/codex/reduced/prog.py) · [Captures](r31-probes/codex/reduced/7-log)

## A31-08 · Medium · The struct format cache bypasses the format’s hash

`runtime/prelude/_struct.py:606`. The cache also changes finalisation order. After struct.calcsize(s) and del s, CPython retains the format until struct._clearcache(). Bella has already finalised it. [CPython](r31-probes/codex/ownership/0-log/c.out) · [Bella](r31-probes/codex/ownership/0-log/b.out)

The cache constructs its key from a normalized format. CPython also normalizes bytes formats, but preserves str subclasses as cache keys. CPython uses the supplied object for both lookup and insertion on a cache miss.

| Minimal call | Arguments and evidence | CPython stdout | Bella stdout |
|---|---|---|---|
| `struct.pack(S("i"),I(1))` | [59 log](r31-probes/codex/subclasses/59-log) · [program](r31-probes/codex/subclasses/prog.py) | `b'\x01\x00\x00\x00' ['__hash__', '__hash__']` | `b'\x01\x00\x00\x00' []` |
| `struct.pack(S("i"),I(1))` | [59 raise](r31-probes/codex/subclasses/59-raise) · [program](r31-probes/codex/subclasses/prog.py) | `ArithmeticError ['__hash__']` | `b'\x01\x00\x00\x00' []` |

Reduced program (driver arguments `8 log`):

```python
import struct
class Format(str):

    def __hash__(self):
        raise LookupError()
try: print(repr(struct.calcsize(Format('2s'))))
except Exception as e: print(type(e).__name__)
```

CPython prints `LookupError`. Bella prints `2`. [Driver](r31-probes/codex/reduced/prog.py) · [Captures](r31-probes/codex/reduced/8-log)

## A31-09 · Medium · Packing a string field indexes the bytes subclass

`runtime/prelude/_struct.py:345`. The p-field branch on lines 349–355 does the same for Pascal strings, including bytearray subclasses. Overriding length to return zero changes the packed three bytes from `02 78 79` to `00 00 00`. [Pascal field](r31-probes/codex/format/5-log)

The s-field packer computes the length of the original object and copies a Python slice. The C packer reads its buffer.

| Minimal call | Arguments and evidence | CPython stdout | Bella stdout |
|---|---|---|---|
| `struct.pack("2s",B(b"xx"))` | [61 log](r31-probes/codex/subclasses/61-log) · [program](r31-probes/codex/subclasses/prog.py) | `b'xx' []` | `b'xx' ['__len__', '__getitem__']` |
| `struct.pack("2s",B(b"xx"))` | [61 raise](r31-probes/codex/subclasses/61-raise) · [program](r31-probes/codex/subclasses/prog.py) | `b'xx' []` | `ArithmeticError ['__len__']` |

Reduced program (driver arguments `9 log`):

```python
import struct
class Field(bytes):

    def __getitem__(self, i):
        return b'z'
try: print(repr(struct.pack('1s', Field(b'x'))))
except Exception as e: print(type(e).__name__)
```

CPython prints `b'x'`. Bella prints `b'z'`. [Driver](r31-probes/codex/reduced/prog.py) · [Captures](r31-probes/codex/reduced/9-log)

## A31-10 · Medium · Unpacking calls the input’s __bytes__

`runtime/prelude/_struct.py:77`. The read-buffer helper converts with bytes(value), so an override can prevent unpacking.

| Minimal call | Arguments and evidence | CPython stdout | Bella stdout |
|---|---|---|---|
| `struct.unpack("2s",B(b"ab"))` | [62 log](r31-probes/codex/subclasses/62-log) · [program](r31-probes/codex/subclasses/prog.py) | `(b'ab',) []` | `(b'ab',) ['__bytes__']` |
| `struct.unpack("2s",B(b"ab"))` | [62 raise](r31-probes/codex/subclasses/62-raise) · [program](r31-probes/codex/subclasses/prog.py) | `(b'ab',) []` | `ArithmeticError ['__bytes__']` |

Reduced program (driver arguments `10 log`):

```python
import struct
class Data(bytes):

    def __bytes__(self):
        return b'other'
try: print(repr(struct.unpack('1s', Data(b'x'))))
except Exception as e: print(type(e).__name__)
```

CPython prints `(b'x',)`. Bella prints `error`. [Driver](r31-probes/codex/reduced/prog.py) · [Captures](r31-probes/codex/reduced/10-log)

## A31-11 · High · Compression, hex conversion and SHA-256 call __bytes__

`runtime/prelude/zlib.py:101`. The three input-buffer helpers call bytes(value), also at binascii.py:76 and _sha2.py:44. The same behavior was measured for all 14 guaranteed hashlib constructors, for zlib compression dictionaries and CRCs, and for binascii hex, base64 and CRC functions. See _blake2.py:64, _md5.py:44, _sha1.py:44, _sha3.py:53 and binascii.py:86. [Hash and binascii calls, rows 90–112](r31-probes/codex/more/rows) · [BLAKE2 key, salt, person and data](r31-probes/codex/details/82-log) · [Hash update](r31-probes/codex/details/83-log)

All three C APIs accept the underlying bytes without calling the override.

| Minimal call | Arguments and evidence | CPython stdout | Bella stdout |
|---|---|---|---|
| `zlib.compress(B(b"ab"),I(1))` | [77 log](r31-probes/codex/subclasses/77-log) · [program](r31-probes/codex/subclasses/prog.py) | `b'x\x01KL\x02\x00\x01&\x00\xc4' []` | `b'x\x01KL\x02\x00\x01&\x00\xc4' ['__bytes__']` |
| `zlib.compress(B(b"ab"),I(1))` | [77 raise](r31-probes/codex/subclasses/77-raise) · [program](r31-probes/codex/subclasses/prog.py) | `b'x\x01KL\x02\x00\x01&\x00\xc4' []` | `ArithmeticError ['__bytes__']` |
| `binascii.hexlify(B(b"a"))` | [78 log](r31-probes/codex/subclasses/78-log) · [program](r31-probes/codex/subclasses/prog.py) | `b'61' []` | `b'61' ['__bytes__']` |
| `binascii.hexlify(B(b"a"))` | [78 raise](r31-probes/codex/subclasses/78-raise) · [program](r31-probes/codex/subclasses/prog.py) | `b'61' []` | `ArithmeticError ['__bytes__']` |
| `hashlib.sha256(B(b"x")).hexdigest()` | [79 log](r31-probes/codex/subclasses/79-log) · [program](r31-probes/codex/subclasses/prog.py) | `'2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881' []` | `'2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881' ['__bytes__']` |
| `hashlib.sha256(B(b"x")).hexdigest()` | [79 raise](r31-probes/codex/subclasses/79-raise) · [program](r31-probes/codex/subclasses/prog.py) | `'2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881' []` | `ArithmeticError ['__bytes__']` |

Reduced program (driver arguments `13 log`):

```python
import hashlib
class Data(bytes):

    def __bytes__(self):
        return b'other'
try: print(repr(hashlib.sha256(Data(b'x')).hexdigest()))
except Exception as e: print(type(e).__name__)
```

CPython prints `'2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881'`. Bella prints `'d9298a10d1b0735837dc4bd85dac641b0f3cef27a47e5d53a54f2f3f5b2fcffa'`. [Driver](r31-probes/codex/reduced/prog.py) · [Captures](r31-probes/codex/reduced/13-log)

## A31-12 · Medium · importlib.import_module drops six traceback entries

`pipeline/backend/cpp.py:325` marks every prelude frame invisible. The import bootstrap is also a prelude, although these functions are Python frames in CPython. A module that raises 30 recursive calls deep exposes this through ordinary traceback inspection at the default recursion limit, on both the initial import and a second attempt.

Minimal operation: `importlib.import_module("badmodule")`, with [badmodule.py](r31-probes/codex/traces/badmodule.py) beside the [driver](r31-probes/codex/traces/prog.py). Run the driver with `35 log`. Both runs exit 0 with empty stderr. CPython prints `ArithmeticError 41` twice, with `_gcd_import, _find_and_load, _find_and_load_unlocked, _load_unlocked, exec_module, _call_with_frames_removed` between `import_module` and the imported module body. Bella prints `ArithmeticError 35` twice and jumps straight from `import_module` to that body. The 31 recursive function entries and chain flags agree. [CPython stdout](r31-probes/codex/traces/35-log/c.out) · [Bella stdout](r31-probes/codex/traces/35-log/b.out)


With the linked four-line badmodule.py beside it, the following driver retains the frame names on both import attempts.

```python
import importlib, traceback
def go():
    importlib.import_module("badmodule")
for attempt in range(2):
    try: go()
    except ArithmeticError as e:
        frames = traceback.extract_tb(e.__traceback__)
        print(len(frames), [f.name for f in frames])
```

## A31-13 · Medium · TextIOWrapper.seek reads a different position from an int subclass

`runtime/prelude/_io.py:3135` calls `_number_index(cookie_obj)`. CPython's `textiowrapper_parse_cookie` in Modules/_io/textio.c:2509 calls `PyNumber_Long`, which invokes the integer subclass's `__int__`. An absolute seek can therefore succeed on both sides and leave the stream at different positions. With a delegating subclass of int, arguments `11 log` print `0 ['__lt__', '__int__']` on CPython and `0 ['__lt__']` on Bella. [Exact program](r31-probes/codex/more/prog.py) · [Outputs](r31-probes/codex/more/11-log)

Reduced program (driver arguments `14 log`):

```python
import io
class Position(int):

    def __int__(self):
        return 1
def seek():
    f = io.TextIOWrapper(io.BytesIO(b'ab'), encoding='ascii')
    f.seek(Position(0))
    return f.read()
try: print(repr(seek()))
except Exception as e: print(type(e).__name__)
```

CPython prints `'b'`. Bella prints `'ab'`. [Driver](r31-probes/codex/reduced/prog.py) · [Captures](r31-probes/codex/reduced/14-log)

## A31-14 · Medium · TypeAliasType dispatches to the type-parameter tuple

`runtime/prelude/_typing.py:854` tests the tuple's truth value and line 857 iterates the original tuple. CPython checks its stored length and elements. For `typing.TypeAliasType(S("Name"), int, type_params=T(())).__name__`, arguments `60 log` print `'Name' []` under CPython and `'Name' ['__len__']` under Bella. [Exact program](r31-probes/codex/more/prog.py) · [Outputs](r31-probes/codex/more/60-log)

```python
import typing
class Empty(tuple):
    def __len__(self): raise LookupError()
try: print(repr(typing.TypeAliasType('N', int, type_params=Empty()).__name__))
except Exception as e: print(type(e).__name__)
```

Driver arguments `0 log`. CPython stdout is `'N'`. Bella stdout is `LookupError`. [Program](r31-probes/codex/decisions/prog.py) · [Captures](r31-probes/codex/decisions/0-log)

## A31-15 · Medium · A filter action can turn an ignored warning into a raised exception

At `runtime/prelude/_warnings.py:498`, ordinary equality dispatches to the action string. CPython uses _PyUnicode_EqualToASCIIString. The same ignore action follows different branches.

```python
import warnings
class Action(str):
    def __eq__(self,other): return other=="error"
class Filters(list):
    def __iter__(self): raise LookupError()
def emit(action="ignore",line=0,wrap=False):
    with warnings.catch_warnings(record=True) as records:
        items=[(action,None,Warning,None,line),("always",None,Warning,None,0)]
        warnings.filters=Filters(items) if wrap else items
        warnings.warn_explicit("x",UserWarning,"f",1)
        return len(records)
try: print(repr(emit(Action('ignore'))))
except Exception as e: print(type(e).__name__)
```

Driver arguments `1 log`. CPython stdout is `0`. Bella stdout is `UserWarning`. [Program](r31-probes/codex/decisions/prog.py) · [Captures](r31-probes/codex/decisions/1-log)

## A31-16 · Medium · A line-number override changes which warning filter wins

At `runtime/prelude/_warnings.py:203` the range check compares the original int and line 205 calls int(value). CPython's PyLong_AsSsize_t reads the stored integer. The first filter should match line one.

```python
import warnings
class Line(int):
    def __int__(self): return 2
class Filters(list):
    def __iter__(self): raise LookupError()
def emit(action="ignore",line=0,wrap=False):
    with warnings.catch_warnings(record=True) as records:
        items=[(action,None,Warning,None,line),("always",None,Warning,None,0)]
        warnings.filters=Filters(items) if wrap else items
        warnings.warn_explicit("x",UserWarning,"f",1)
        return len(records)
try: print(repr(emit(line=Line(1))))
except Exception as e: print(type(e).__name__)
```

Driver arguments `2 log`. CPython stdout is `0`. Bella stdout is `1`. [Program](r31-probes/codex/decisions/prog.py) · [Captures](r31-probes/codex/decisions/2-log)

## A31-17 · Medium · A warnings.filters list subclass controls filter iteration

At `runtime/prelude/_warnings.py:210`, enumerate(items) asks for the list's iterator. CPython's filter_search uses PyList_GET_SIZE and PyList_GET_ITEM. This is distinct from the per-filter tuple access in A31-07.

```python
import warnings
class Filters(list):
    def __iter__(self): raise LookupError()
def emit(action="ignore",line=0,wrap=False):
    with warnings.catch_warnings(record=True) as records:
        items=[(action,None,Warning,None,line),("always",None,Warning,None,0)]
        warnings.filters=Filters(items) if wrap else items
        warnings.warn_explicit("x",UserWarning,"f",1)
        return len(records)
try: print(repr(emit(wrap=True)))
except Exception as e: print(type(e).__name__)
```

Driver arguments `3 log`. CPython stdout is `0`. Bella stdout is `LookupError`. [Program](r31-probes/codex/decisions/prog.py) · [Captures](r31-probes/codex/decisions/3-log)

## A31-18 · Medium · The POSIX path helpers slice a str or bytes subclass

At `runtime/prelude/posix.py:1350`, _splitroot slices the supplied path. Both splitroot and normpath use the helper. On a relative path the original object also reaches rest.split(sep) at line 1370. The C implementation scans the stored characters.

```python
import os
class Path(str):
    def __getitem__(self,i): raise LookupError()
try: print(repr(os.path.normpath(Path('a//b'))))
except Exception as e: print(type(e).__name__)
```

Driver arguments `4 log`. CPython stdout is `'a/b'`. Bella stdout is `LookupError`. [Program](r31-probes/codex/decisions/prog.py) · [Captures](r31-probes/codex/decisions/4-log)

## A31-19 · Medium · execv tests the truth value of argv[0] after conversion

At `runtime/prelude/posix.py:700`, _arglist tests if not out[0]. The filesystem converter can preserve a bytes subclass. The empty-string check therefore calls its length method, after the legitimate sequence operations used to retrieve the argument. CPython checks the converted C string.

```python
import os
class Arg(bytes):
    def __len__(self): return 0
try: print(repr(os.execv('/a31-never-here', [Arg(b'prog')])))
except Exception as e: print(type(e).__name__)
```

Driver arguments `5 log`. CPython stdout is `FileNotFoundError`. Bella stdout is `ValueError`. [Program](r31-probes/codex/decisions/prog.py) · [Captures](r31-probes/codex/decisions/5-log)

## A31-20 · Medium · Environment variable validation dispatches membership to the input bytes

At `runtime/prelude/posix.py:905`, _fsconverter tests 0 in data. The putenv name check also uses 61 in name at line 1290. CPython reads raw bytes. unsetenv reaches the same NUL check.

```python
import os
class Name(bytes):
    def __contains__(self,i): return True
try: print(repr(os.putenv(Name(b'A31'), b'x')))
except Exception as e: print(type(e).__name__)
```

Driver arguments `6 log`. CPython stdout is `None`. Bella stdout is `ValueError`. [Program](r31-probes/codex/decisions/prog.py) · [Captures](r31-probes/codex/decisions/6-log)

## A31-21 · Medium · The struct c field can pack a different character

At `runtime/prelude/_struct.py:293` the packer has already validated the stored length, but calls bytes(value) to get the character. CPython copies the original byte.

```python
import struct
class Char(bytes):
    def __bytes__(self): return b"Z"
try: print(repr(struct.pack('c', Char(b'x'))))
except Exception as e: print(type(e).__name__)
```

Driver arguments `7 log`. CPython stdout is `b'x'`. Bella stdout is `b'Z'`. [Program](r31-probes/codex/decisions/prog.py) · [Captures](r31-probes/codex/decisions/7-log)

## A31-22 · Medium · Closing a generator loses the active exception from GeneratorExit.__context__

At `runtime/src/generator.cpp:371`, gen_close constructs a GeneratorExit and installs it as a pending exception. At line 396 gen_raise_pending establishes a context only when the generator itself has a handler active. CPython's close path sets GeneratorExit while the caller's exception is still being handled. A generator can observe this directly.

```python
def gen():
    try: yield 1
    except GeneratorExit as e: print(type(e).__name__, type(e.__context__).__name__)

g = gen()
next(g)
try: raise KeyError()
except KeyError: g.close()
```

Run the [driver](r31-probes/codex/genclose/prog.py) with `0 log`. CPython prints `GeneratorExit KeyError`. Bella prints `GeneratorExit NoneType`. Both exit 0 with empty stderr. A caught throw(GeneratorExit()) through yield from also exposes the missing context in the delegate, with identical outer traceback lengths. [Caught throw](r31-probes/codex/delegation/7-log)

The same difference occurs with finalisation, with a delegating generator's close, and with its finalisation. [Explicit close](r31-probes/codex/genclose/0-log) · [Finalisation](r31-probes/codex/genclose/1-log) · [Delegation](r31-probes/codex/genclose/4-log)

In the 30-deep probe, both sides preserve the 35 frames of the error raised during close, followed by GeneratorExit's single frame. Only CPython retains the preceding ValueError and its 32 frames. The unraisable hook sees the same missing link on finalisation. [CPython chain](r31-probes/codex/chaining/6-log/c.out) · [Bella chain](r31-probes/codex/chaining/6-log/b.out) · [Finaliser captures](r31-probes/codex/chaining/7-log)

## A31-23 · Medium · Struct construction calls the format subclass’s equality method

At `runtime/prelude/_struct.py:432`, Struct.__init__ compares its incoming format against self.format, even on the first construction. CPython accepts the contents of the string without that comparison. This occurs with direct Struct construction, independently of the module-level cache in A31-08.

```python
import struct
class Format(str):
    def __eq__(self,other): raise LookupError()
    __hash__=str.__hash__
try: print(repr(struct.Struct(Format('2s')).size))
except Exception as e: print(type(e).__name__)
```

Driver arguments `0 log`. CPython stdout is `2`. Bella stdout is `LookupError`. [Program](r31-probes/codex/format/prog.py) · [Captures](r31-probes/codex/format/0-log)

## A31-24 · Medium · A bytes separator changes the characters emitted by binascii.hexlify

At `runtime/prelude/binascii.py:568`, the separator byte comes from sep[0]. CPython does call the separator’s length method, but obtains its byte from the underlying buffer. The reduced program leaves the length check untouched.

```python
import binascii
class Sep(bytes):
    def __getitem__(self,index): return 33
try: print(repr(binascii.hexlify(b'xy', Sep(b':'))))
except Exception as e: print(type(e).__name__)
```

Driver arguments `1 log`. CPython stdout is `b'78:79'`. Bella stdout is `b'78!79'`. [Program](r31-probes/codex/format/prog.py) · [Captures](r31-probes/codex/format/1-log)

## A31-25 · Medium · os.path.splitroot returns the original subclass for a relative path

At `runtime/prelude/posix.py:1352`, _splitroot returns path as the tail when it has no leading slash. CPython constructs a base string. This is observable even when the subclass overrides no methods.

```python
import os
class Simple(str): pass
def meta():
    a=Simple("x")
    return type(os.path.splitroot(a)[2]).__name__,type(os.path.normpath(a)).__name__
try: print(repr(meta()))
except Exception as e: print(type(e).__name__)
```

Driver arguments `3 log`. CPython stdout is `('str', 'str')`. Bella stdout is `('Simple', 'str')`. [Program](r31-probes/codex/format/prog.py) · [Captures](r31-probes/codex/format/3-log)

## A31-26 · High · JSON changes the key and value supplied by dict.items()

At `runtime/prelude/_json.py:671` the encoder calls len(item), then indexes item at line 673. CPython calls the dict subclass’s items method, validates each returned pair by its stored tuple size, and reads both stored entries using PyTuple_GET_ITEM. The distinction changes the serialized document.

```python
import json
class Pair(tuple):
    def __getitem__(self,key): return "other"
class Items(dict):
    def items(self): return [Pair(("key",1))]
try: print(repr(json.dumps(Items(x=1))))
except Exception as e: print(type(e).__name__)
```

Driver arguments `0 log`. CPython stdout is `'{"key": 1}'`. Bella stdout is `'{"other": "other"}'`. [Program](r31-probes/codex/state/prog.py) · [Captures](r31-probes/codex/state/0-log)

## A31-27 · Medium · JSON asks the collection returned by dict.items() for its length

At `runtime/prelude/_json.py:667`, list(dct.items()) asks the original non-exact list for a length hint. PyMapping_Items materializes that result through its iterator. This reproduces with exact tuple pairs, independently of A31-26.

```python
import json
class Length(list):
    def __len__(self): raise LookupError()
class SizedItems(dict):
    def items(self): return Length([("x",1)])
try: print(repr(json.dumps(SizedItems(x=1))))
except Exception as e: print(type(e).__name__)
```

Driver arguments `1 log`. CPython stdout is `'{"x": 1}'`. Bella stdout is `LookupError`. [Program](r31-probes/codex/state/prog.py) · [Captures](r31-probes/codex/state/1-log)

## A31-28 · Medium · A markers dict subclass can make JSON diagnose a nonexistent cycle

At `runtime/prelude/_json.py:703` the encoder tests ident in markers. CPython calls PyDict_Contains and updates the underlying dict. Bella dispatches membership, assignment and deletion through ordinary Python operations. An empty markers dict can therefore stop a one-element list from being encoded.

```python
import json
class Markers(dict):
    def __contains__(self,key): return True
def marker():
    enc=json.encoder.c_make_encoder(Markers(),str,json.encoder.encode_basestring,None,":",",",False,False,True)
    return enc([1],0)
try: print(repr(marker()))
except Exception as e: print(type(e).__name__)
```

Driver arguments `2 log`. CPython stdout is `('[1]',)`. Bella stdout is `ValueError`. [Program](r31-probes/codex/state/prog.py) · [Captures](r31-probes/codex/state/2-log)

## A31-29 · Medium · partial.__setstate__ invokes tuple hooks while validating the state

At `runtime/prelude/_functools.py:292`, the method calls len(state), then unpacks the outer tuple. CPython reads all four fields via PyArg_ParseTuple. The nested argument tuple also reaches len(fnargs) on line 297 where CPython reads PyTuple_GET_SIZE. Its later conversion to a tuple legitimately calls __iter__ on both sides. [Nested tuple example](r31-probes/codex/state/4-log)

```python
import functools
class State(tuple):
    def __iter__(self): raise LookupError()
def restored(state):
    f=functools.partial(sum)
    f.__setstate__(state)
    return f()
try: print(repr(restored(State((int, (), {}, None)))))
except Exception as e: print(type(e).__name__)
```

Driver arguments `3 log`. CPython stdout is `0`. Bella stdout is `LookupError`. [Program](r31-probes/codex/state/prog.py) · [Captures](r31-probes/codex/state/3-log)

## A31-30 · Medium · bindtextdomain calls __bytes__ on its directory argument

At `runtime/prelude/_locale.py:250`, the bytes directory is processed through bytes(dirname). CPython reads the directory's path bytes without calling its conversion hook.

```python
import _locale
class Bytes(bytes):
    def __bytes__(self): raise LookupError()
def bind(): return _locale.bindtextdomain("a31",Bytes(b"/tmp"))
try: print(repr(bind()))
except Exception as e: print(type(e).__name__)
```

Driver arguments `6 log`. CPython stdout is `'/tmp'`. Bella stdout is `LookupError`. [Program](r31-probes/codex/neighbors/prog.py) · [Captures](r31-probes/codex/neighbors/6-log)

## A31-31 · Medium · struct.pack_into uses the destination bytearray’s Python methods

At `runtime/prelude/_struct.py:552`, len(target) calls the subclass to establish writable capacity. At line 333 the packer zeroes the buffer through item assignment, also dispatching to the subclass. CPython obtains a writable buffer and writes into it. A two-byte destination whose overridden length returns zero raises struct.error only on Bella. [Length variant](r31-probes/codex/state/9-log)

```python
import struct
class Output(bytearray):
    def __setitem__(self,k,v): raise LookupError()
def write(cls):
    b=cls(b"xy")
    struct.pack_into("B",b,0,65)
    return bytes(b)
try: print(repr(write(Output)))
except Exception as e: print(type(e).__name__)
```

Driver arguments `10 log`. CPython stdout is `b'Ay'`. Bella stdout is `LookupError`. [Program](r31-probes/codex/state/prog.py) · [Captures](r31-probes/codex/state/10-log)

## A31-32 · High · compare_digest can report equality for unequal bytes or text

At `runtime/prelude/_operator.py:315` the buffer branch uses bytes(a) and bytes(b). The string branch at lines 304–307 calls isascii and encode on the inputs. CPython compares stored bytes or ASCII data directly. Both _operator._compare_digest and the public hmac.compare_digest return a different Boolean. [Direct bytes case](r31-probes/codex/digests/0-log) · [Text case](r31-probes/codex/digests/4-log)

```python
import hmac
class Data(bytes):
    def __bytes__(self): return b"same"
try: print(repr(hmac.compare_digest(Data(b'a'), Data(b'b'))))
except Exception as e: print(type(e).__name__)
```

Driver arguments `3 log`. CPython stdout is `False`. Bella stdout is `True`. [Program](r31-probes/codex/digests/prog.py) · [Captures](r31-probes/codex/digests/3-log)

## A31-33 · High · HMAC computes the digest of bytes supplied by an override

At `runtime/prelude/_hmac.py:61` the buffer converter calls bytes(value) on the key and the message. CPython reads their buffers. Both the one-shot function and the HMAC object compute a different digest for this key. [Object API](r31-probes/codex/digests/6-log)

```python
import hmac
class Data(bytes):
    def __bytes__(self): return b"same"
try: print(repr(hmac.digest(Data(b'k'), b'x', 'sha256').hex()))
except Exception as e: print(type(e).__name__)
```

Driver arguments `5 log`. CPython stdout is `'c38edc8815c8489f64738978f44008f8596345545f0baa68ef6fcf5c53e57189'`. Bella stdout is `'b276a3f1986d5135f8301b382537ba0f32f13670d9d4d74fd6a69aeee29a40fa'`. [Program](r31-probes/codex/digests/prog.py) · [Captures](r31-probes/codex/digests/5-log)

## A31-34 · Medium · warnings.warn consults methods on skip_file_prefixes

At `runtime/prelude/_warnings.py:612` the stack-level adjustment tests len(prefixes). _setup_context also tests and iterates the tuple on lines 540–541. CPython uses the tuple’s stored entries. This occurs even when warning output is ignored and even with an empty tuple. [Nonempty iteration variant](r31-probes/codex/neighbors/1-log)

```python
import warnings
class Len(tuple):
    def __len__(self): raise LookupError()
def prefix(x):
    warnings.simplefilter("ignore")
    warnings.warn("message",skip_file_prefixes=x)
try: print(repr(prefix(Len(()))))
except Exception as e: print(type(e).__name__)
```

Driver arguments `0 log`. CPython stdout is `None`. Bella stdout is `LookupError`. [Program](r31-probes/codex/neighbors/prog.py) · [Captures](r31-probes/codex/neighbors/0-log)

## A31-35 · Medium · itertools._tee_dataobject reads its initial values through list hooks

At `runtime/prelude/itertools.py:347`, the tee data constructor takes len(values), then copies by iterating list(values). CPython copies entries from the supplied list's storage.

```python
import itertools
class List(list):
    def __iter__(self): raise LookupError()
    def __len__(self): raise LookupError()
def tee(): return type(itertools._tee_dataobject(iter(()),List([1]),None)).__name__
try: print(repr(tee()))
except Exception as e: print(type(e).__name__)
```

Driver arguments `2 log`. CPython stdout is `'_tee_dataobject'`. Bella stdout is `LookupError`. [Program](r31-probes/codex/neighbors/prog.py) · [Captures](r31-probes/codex/neighbors/2-log)

## A31-36 · Medium · A stored group index intercepts a match lookup

At `runtime/prelude/_sre.py:521`, _getindex preserves the dictionary value as an int subclass. The subsequent range check uses its rich comparison. CPython converts the numeric value to a C index. The probe uses bytecode produced by re's own compiler for the same named group.

```python
import re, _sre
class Index(int):
    def __lt__(self,n): raise LookupError()
def sr():
    tree=re._parser.parse("(?P<x>a)",0)
    words=re._compiler._code(tree,0)
    p=_sre.compile("(?P<x>a)",32,words,1,{"x":Index(1)},(None,"x"))
    return p.match("a").group("x")
try: print(repr(sr()))
except Exception as e: print(type(e).__name__)
```

Driver arguments `3 log`. CPython stdout is `'a'`. Bella stdout is `LookupError`. [Program](r31-probes/codex/neighbors/prog.py) · [Captures](r31-probes/codex/neighbors/3-log)

## A31-37 · Medium · A bytes replacement template can fail while retrying template compilation

At `runtime/prelude/_sre.py:266`, the retry for an unhashable bytes subclass uses bytes(repl). This invokes __bytes__. CPython's retry takes the object's byte contents. The backreference should expand to the matched character.

```python
import re
class Unhashable(bytes):
    __hash__=None
    def __bytes__(self): raise LookupError()
def regex(x): return re.compile(b"(a)").sub(x,b"a")
try: print(repr(regex(Unhashable(bytes((92, 49))))))
except Exception as e: print(type(e).__name__)
```

Driver arguments `4 log`. CPython stdout is `b'a'`. Bella stdout is `LookupError`. [Program](r31-probes/codex/neighbors/prog.py) · [Captures](r31-probes/codex/neighbors/4-log)


## A31-38 · Medium · Text streams expose the option object under mode, encoding and errors

At `runtime/prelude/_io.py:3693`, open assigns the original mode to the wrapper. Lines 3691 and 2896–2897 pass and store the original encoding and errors objects. CPython constructs a fresh base string for mode and passes C strings to the wrapper. Direct TextIOWrapper construction preserves an errors subclass on both sides, but its encoding is a plain str under CPython. [Direct wrapper](r31-probes/codex/lifetimes/4-log)

```python
class S(str): pass
def options():
    mode,encoding,errors=S("r"),S("utf8"),S("strict")
    with open("/dev/null",mode,encoding=encoding,errors=errors) as stream:
        return tuple(type(v).__name__ for v in (stream.mode,stream.encoding,stream.errors))
try: print(repr(options()))
except Exception as e: print(type(e).__name__)
```

Driver arguments `3 log`. CPython stdout is `('str', 'str', 'str')`. Bella stdout is `('S', 'S', 'S')`. [Program](r31-probes/codex/lifetimes/prog.py) · [Captures](r31-probes/codex/lifetimes/3-log)

## A31-39 · Medium · A temporary argument survives deletion inside its callee

The positional call emitted by `pipeline/backend/cpp.py:1118` passes objects held by caller temporaries to invoke. Argument binding at runtime/src/call.cpp:260 acquires another reference. The caller’s reference survives until invoke returns. CPython can release the sole temporary argument in the callee, so its finaliser runs before the next statement. The probe contains no cycle, traceback or shutdown finalisation. With an explicit caller reference, both implementations postpone finalisation until that reference is deleted. [Retained control](r31-probes/codex/lifetimes/1-log)

```python
class X:
    def __del__(self): print("finalised")
def discard(x):
    del x
    print("inside")
def release():
    discard(X())
    print("outside")
try: print(repr(release()))
except Exception as e: print(type(e).__name__)
```

Driver arguments `0 log`. Each column is stdout, one line per row. Both runs exit 0 with empty stderr.

| CPython | Bella |
|---|---|
| finalised | inside |
| inside | finalised |
| outside | outside |
| None | None |

 [Program](r31-probes/codex/lifetimes/prog.py) · [Captures](r31-probes/codex/lifetimes/0-log)

## A31-40 · Medium · repr skips bytes and bytearray subclass overrides

At `runtime/src/ops.cpp:969`, repr_unchecked returns bytes_repr directly for either storage type. The str, int and float branches check for overrides. The difference also appears when displaying a result returned by a program-registered encoder: both sides return the exact object supplied by the encoder, yet repr of that object differs.

```python
class B(bytes):
    def __repr__(self): return "overridden"
print(repr(repr(B(b"ab"))))
```

Driver arguments `0 log`. CPython prints `'overridden'`. Bella prints `"b'ab'"`. The corresponding bytearray case prints `'overridden'` and `"A(b'ab')"`. [Program](r31-probes/codex/conversions/prog.py) · [Bytes](r31-probes/codex/conversions/0-log) · [Bytearray](r31-probes/codex/conversions/2-log) · [Encoder result type and identity](r31-probes/codex/conversions/4-log)

## A31-41 · Medium · execv, execve and posix_spawn expose a different exception when argv length fails

At `runtime/prelude/posix.py:1562`, a failing len(argv) propagates before the empty-argument check. The same applies at lines 1574 and 825. CPython also calls the length override, but PySequence_Size returns -1 on failure. The subsequent argc < 1 check replaces the error with ValueError. This happens before an executable is opened.

```python
import os
class L(list):
    def __len__(self): raise LookupError()
try: os.execv("/a31-not-present", L(["x"]))
except BaseException as e: print(type(e).__name__, type(e.__context__).__name__)
```

Driver arguments `5 log`. CPython prints `ValueError NoneType`. Bella prints `LookupError NoneType`. Both exit 0 with empty stderr. [Program](r31-probes/codex/conversions/prog.py) · [execv](r31-probes/codex/conversions/5-log) · [execve](r31-probes/codex/conversions/6-log) · [posix_spawn](r31-probes/codex/conversions/7-log)

## Coverage and matching behavior

I compared **5,409 process pairs** across 27 probe programs. 4,764 pairs matched byte for byte across stdout, stderr and exit status. These counts include controls, reduced reproducers and reruns with a wider set of overrides. The row index records all three comparisons independently and identifies each capture directory. The 37 examples in the examples driver also rerun the corresponding report snippets, one selection per process. [Comparison index](r31-probes/codex/comparisons.tsv) · [Example driver](r31-probes/codex/examples/prog.py) · [Example selections](r31-probes/codex/examples/rows)

The slot matrices covered the APIs drawn from the A30 tests against 26 input shapes, followed by 11 inherited or disabled-slot shapes. The path matrix used 10 representations, including both booleans, an int subclass overriding __index__, and path-like objects returning str, bytes, bytearray or a second path-like object. Its private descriptors allowed successful reads, chmod, truncate and timestamp changes. The byte-for-byte comparison includes warnings on stderr for boolean descriptors. [Slot matrix](r31-probes/codex/slots/prog.py) · [Inherited slots](r31-probes/codex/inherited/prog.py) · [Additional slot consumers](r31-probes/codex/slotextras/prog.py) · [Path matrix](r31-probes/codex/paths/prog.py)

The fcntl pipe-capacity setter was unavailable in the compiled closure. The signal tests used real pipes and the operating system's existing capacity. Source-format differences in uncaught tracebacks, declared module omissions, named stops and previously open issues were excluded from the numbered findings. The comparison index gives the precise calls and input shapes covered.

- **Signals and I/O.** All 28 pipe comparisons matched. The calls included os.read, raw and buffered reads, TextIOWrapper.readline, input and sys.stdin.read with fd 0 attached to a pipe, os.write, BufferedWriter.flush and print. The handler ran once between the same output lines. With a slow reader and a 243,000-byte payload, a raising handler left the same 65,536-byte prefix for os.write. Buffered flush and print delivered all 243,000 bytes after close. The child’s complete received bytes were compared with the source prefix. [Read and write cases](r31-probes/codex/signals/prog.py) · [Actual fd 0](r31-probes/codex/stdin/prog.py) · [Partial writes](r31-probes/codex/partialwrites/prog.py)
- **Tracebacks and chaining.** The original 61-row trace driver had one differing row, A31-12. The later active-exception tests exposed A31-22. Matching cases included a 30-deep call crossing with and nested finally blocks, descriptor and operator fallbacks, hash and equality failures, generator.throw, weakref and finaliser callbacks, atexit, JSON and regex callbacks, contextmanager, ExitStack, exception groups, stored raises, with_traceback(None) and notes added during unwinding. Ordinary import, from-import and __import__ matched on both failed attempts. A logging handler reached through logger.warning produced the same exception and 38 frame names. [Trace driver](r31-probes/codex/traces/prog.py) · [Chaining driver](r31-probes/codex/chaining/prog.py) · [Logging captures](r31-probes/codex/ownership/1-log)
- **Built-in slots and paths.** All completed, non-stop comparisons in the three slot matrices matched. In the dedicated 480-pair path matrix the four differing rows were the two subclass types returned by splitroot, passed directly or returned by __fspath__ (A31-25). [Direct bytes](r31-probes/codex/paths/45-5) · [Path-like returning bytes](r31-probes/codex/paths/45-7) · [Matching boolean fd warning](r31-probes/codex/paths/3-1)
- **Math.** Every one of the 62 public callable math names in the pinned interpreter was exercised with int and float subclasses. The resulting values or exception classes and the observed method calls agreed. For example, cos skipped a float subclass’s __float__ and called an int subclass’s __float__ once. ceil called __ceil__ on both. The two-operand fmin and fmax cases used both argument orders. [Float cos](r31-probes/codex/subclasses/119-log) · [Integer cos](r31-probes/codex/subclasses/120-log) · [Ceil](r31-probes/codex/subclasses/113-log) · [Additional math calls](r31-probes/codex/details/rows)
- **Legitimate subclass dispatch.** json.dumps called a dict subclass’s items once. bisect_left called a list subclass’s length and item methods. insort_right also called insert. Heap push, pop and heapify used the list’s storage. CSV converted numeric fields through their string methods, and lru_cache hashed a single subclass key. With newline translation active, TextIOWrapper.write called the text subclass’s replace on both sides. These controls distinguish the observed extra calls from methods CPython actually dispatches. [JSON](r31-probes/codex/subclasses/25-log) · [Bisect](r31-probes/codex/subclasses/91-log) · [Insort](r31-probes/codex/subclasses/92-log) · [Heap](r31-probes/codex/subclasses/93-log) · [CSV](r31-probes/codex/subclasses/65-log) · [Cache](r31-probes/codex/protocols/19-log) · [Text translation](r31-probes/codex/details/28-log)
