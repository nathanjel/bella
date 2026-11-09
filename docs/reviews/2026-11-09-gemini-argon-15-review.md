gemini-argon-4 (medium effort) through `agy`, 2026-11-09, asked by the author. Verbatim. Tag G15 in the review log. Its range is
`46a5742..c8109ba`: the Python preludes and the semantics layer; it ran in its own worktree (`bella-g15`) at `c8109ba`, whose
line numbers its citations carry. Nineteen findings; two (#9, #15) do not reproduce on 3.15.2 and one (#13) is a stop by design.

---

### Focus 1: [`_warnings.py`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_warnings.py), [`i_warnings_frame`](file:///home/nathan/workspaces/nth/bella-g15/runtime/src/call.cpp#L1866-L1874), [`_tokenize.py`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_tokenize.py)

#### G15-01 — [`_warnings.py:343`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_warnings.py#L341-L346) (`_setup_context`)
[`_setup_context`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_warnings.py#L305-L353) executes `assert isinstance(registry, dict)` after looking up `"__warningregistry__"` in `globals_`. When a module sets `__warningregistry__ = None` or a non-`dict`, CPython's `setup_context` passes the value through to `warn_explicit` (which accepts `None` and raises `TypeError: 'registry' must be a dict or None` for non-dicts), whereas Bella raises `AssertionError`.

```python
import warnings
for val in (None, 123):
    with warnings.catch_warnings(record=True) as r:
        warnings.simplefilter("always")
        globals()["__warningregistry__"] = val
        try:
            warnings.warn("hello")
            print(val, "ok", len(r))
        except Exception as e:
            print(val, type(e).__name__, e)
```
- **CPython 3.15.2**:
  ```text
  None ok 1
  123 TypeError 'registry' must be a dict or None
  ```
- **Bella (`c8109ba`)**:
  ```text
  None AssertionError 
  123 AssertionError 
  ```

---

#### G15-02 — [`call.cpp:1866-1874`](file:///home/nathan/workspaces/nth/bella-g15/runtime/src/call.cpp#L1866-L1874) (`i_warnings_frame`), [`runtime.hpp:574`](file:///home/nathan/workspaces/nth/bella-g15/runtime/include/bella/runtime.hpp#L571-L579) (`FrameGuard`), [`cpp.py:298`](file:///home/nathan/workspaces/nth/bella-g15/pipeline/backend/cpp.py#L298)
Inlined comprehension helpers have `Code::shown = false`, so [`FrameGuard`](file:///home/nathan/workspaces/nth/bella-g15/runtime/include/bella/runtime.hpp#L571-L579) does not push the helper onto `detail::current_frame()`. Inside the comprehension body, `B_LINE` updates the unlinked `FrameGuard::line` while `detail::current_frame()->line` stays at the line before the comprehension, causing [`i_warnings_frame`](file:///home/nathan/workspaces/nth/bella-g15/runtime/src/call.cpp#L1866-L1874) (`_warnings._frame`) to report a stale line number.

```python
import warnings
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    x = [
        1 +
        (warnings.warn("in comp") or 0)
        for _ in range(1)
    ]
    print("lineno:", w[0].lineno)
```
- **CPython 3.15.2**:
  ```text
  lineno: 7
  ```
- **Bella (`c8109ba`)**:
  ```text
  lineno: 5
  ```

---

#### G15-03 — [`_tokenize.py:44-50`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_tokenize.py#L29-L51) (`TokenizerIter.__new__`)
[`TokenizerIter.__new__`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_tokenize.py#L29-L53) checks `isinstance(encoding, str)` (lines 46–47) before calling `bool(extra_tokens)` (line 50), whereas CPython's clinic parser converts `extra_tokens` (`PyObject_IsTrue`, pos 2) before checking `encoding` (`PyUnicode_Check`, pos 3). In addition, line 44 omits [`_keyword_suggestion`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_tokenize.py#L20-L24) when `extra_tokens` is passed alongside an unknown keyword.

```python
import _tokenize
class BadBool:
    def __bool__(self):
        raise RuntimeError("bad bool")
for kw in [
    {"extra_tokens": BadBool(), "encoding": 123},
    {"extra_tokens": 1, "encodin": "utf-8"},
]:
    try:
        _tokenize.TokenizerIter(lambda: "", **kw)
    except Exception as e:
        print(type(e).__name__, e)
```
- **CPython 3.15.2**:
  ```text
  RuntimeError bad bool
  TypeError tokenizeriter() got an unexpected keyword argument 'encodin'. Did you mean 'encoding'?
  ```
- **Bella (`c8109ba`)**:
  ```text
  TypeError tokenizeriter() argument 'encoding' must be str, not int
  TypeError tokenizeriter() got an unexpected keyword argument 'encodin'
  ```

---

### Focus 2: [`zlib.py`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/zlib.py)

#### G15-04 — [`zlib.py:491`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/zlib.py#L469-L491) (`decompressobj`) and [`zlib.py:401`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/zlib.py#L397-L407) (`Decompress.__init__`)
[`decompressobj`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/zlib.py#L469-L491) converts `zdict` to `bytes` eagerly via [`_buffer`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/zlib.py#L41-L47) at construction time. In CPython (`zlib_decompressobj_impl`), `self->zdict` retains a reference to the caller's object and (for `wbits >= 0`) only extracts its buffer when `inflate()` returns `Z_NEED_DICT` during [`Decompress.decompress`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/zlib.py#L409-L433). Mutating a `bytearray` `zdict` between `decompressobj()` and `decompress()` affects CPython but not Bella.

```python
import zlib
zd = bytearray(b"hello world")
co = zlib.compressobj(zdict=zd)
stream = co.compress(b"hello world hello world") + co.flush()
do = zlib.decompressobj(zdict=zd)
zd[:] = b"wrong dict!"
try:
    print(repr(do.decompress(stream)))
except Exception as e:
    print(type(e).__name__, e)
```
- **CPython 3.15.2**:
  ```text
  error Error -3 while setting zdict: invalid input data
  ```
- **Bella (`c8109ba`)**:
  ```text
  b'hello world hello world'
  ```

---

### Focus 3: C-Module Ports (`_csv`, `_contextvars`, `_bisect`, `_random`, `_statistics`, `_opcode`, `binascii`, `_struct`, `time`, `math`, digests)

#### G15-05 — [`time.py:438,470`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/time.py#L438-L473) (`_gettmarg`)
In [`_gettmarg`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/time.py#L422-L475), `wday = (items[6] + 1) % 7` uses Python's flooring `%` instead of C's remainder `%`, which always yields `0..6` even when `items[6] < -1`. As a result, `if wday < 0: raise ValueError("day of week out of range")` at line 470 is unreachable and [`asctime`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/time.py#L549-L561) / [`strftime`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/time.py#L570-L607) accept `tm_wday < -1`.

```python
import time
for fn in [
    lambda: time.asctime((2024, 1, 1, 0, 0, 0, -2, 1, 0)),
    lambda: time.strftime("%a", (2024, 1, 1, 0, 0, 0, -2, 1, 0)),
]:
    try:
        print("OK", repr(fn()))
    except Exception as e:
        print(type(e).__name__, e)
```
- **CPython 3.15.2**:
  ```text
  ValueError day of week out of range
  ValueError day of week out of range
  ```
- **Bella (`c8109ba`)**:
  ```text
  OK 'Sat Jan  1 00:00:00 2024'
  OK 'Sat'
  ```

---

#### G15-06 — [`binascii.py:87-96`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/binascii.py#L87-L96), [`_struct.py:71-80,99,282-287`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_struct.py#L71-L100), [`time.py:62-71,93,110`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/time.py#L62-L112), [`math.py:55-64,76,730`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/math.py#L55-L78), [`_math_integer.py:19-28`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_math_integer.py#L19-L28), [`_sha3.py:80-89`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_sha3.py#L80-L89), [`_blake2.py:68-77`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_blake2.py#L68-L77) (`_index`)
The custom `_index()` helpers in these 7 modules differ from CPython 3.15.2's `PyNumber_Index` (and Bella's `_number_index` in [`ops.cpp:749`](file:///home/nathan/workspaces/nth/bella-g15/runtime/src/ops.cpp#L741-L753)):
1. When `__index__()` returns a non-`int`, they raise `TypeError: __index__ returned non-int (type <T>)` instead of `TypeError: <Cls>.__index__() must return an int, not <T>`.
2. When `__index__ = None` on a class, `getattr(type(value), "__index__", None)` treats it as absent (`cannot be interpreted as an integer`) instead of calling `None` and raising `TypeError: 'NoneType' object is not callable`.

```python
import binascii, struct, time, math, _sha3, _blake2

class BadIdx:
    def __index__(self): return "abc"

class IdxNone:
    __index__ = None

for obj in (BadIdx(), IdxNone()):
    for name, fn in [
        ("binascii", lambda: binascii.crc32(b"a", obj)),
        ("struct", lambda: struct.pack("i", obj)),
        ("time", lambda: time.gmtime(obj)),
        ("math", lambda: math.gcd(obj, 2)),
        ("_sha3", lambda: _sha3.shake_128(b"a").digest(obj)),
        ("_blake2", lambda: _blake2.blake2b(b"a", digest_size=obj)),
    ]:
        try:
            fn()
        except Exception as e:
            print(f"{type(obj).__name__} {name}: {type(e).__name__}: {e}")
```
- **CPython 3.15.2**:
  ```text
  BadIdx binascii: TypeError: BadIdx.__index__() must return an int, not str
  BadIdx struct: TypeError: BadIdx.__index__() must return an int, not str
  BadIdx time: TypeError: BadIdx.__index__() must return an int, not str
  BadIdx math: TypeError: BadIdx.__index__() must return an int, not str
  BadIdx _sha3: TypeError: BadIdx.__index__() must return an int, not str
  BadIdx _blake2: TypeError: BadIdx.__index__() must return an int, not str
  IdxNone binascii: TypeError: 'NoneType' object is not callable
  IdxNone struct: TypeError: 'NoneType' object is not callable
  IdxNone time: TypeError: 'NoneType' object is not callable
  IdxNone math: TypeError: 'NoneType' object is not callable
  IdxNone _sha3: TypeError: 'NoneType' object is not callable
  IdxNone _blake2: TypeError: 'NoneType' object is not callable
  ```
- **Bella (`c8109ba`)**:
  ```text
  BadIdx binascii: TypeError: __index__ returned non-int (type str)
  BadIdx struct: TypeError: __index__ returned non-int (type str)
  BadIdx time: TypeError: __index__ returned non-int (type str)
  BadIdx math: TypeError: __index__ returned non-int (type str)
  BadIdx _sha3: TypeError: __index__ returned non-int (type str)
  BadIdx _blake2: TypeError: __index__ returned non-int (type str)
  IdxNone binascii: TypeError: 'IdxNone' object cannot be interpreted as an integer
  IdxNone struct: TypeError: 'IdxNone' object cannot be interpreted as an integer
  IdxNone time: TypeError: 'IdxNone' object cannot be interpreted as an integer
  IdxNone math: TypeError: 'IdxNone' object cannot be interpreted as an integer
  IdxNone _sha3: TypeError: 'IdxNone' object cannot be interpreted as an integer
  IdxNone _blake2: TypeError: 'IdxNone' object cannot be interpreted as an integer
  ```

---

#### G15-07 — [`math.py:67-79,551-598`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/math.py#L67-L79), [`time.py:78-89`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/time.py#L78-L89), [`_statistics.py:34-46`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_statistics.py#L34-L46) (`_as_double`, `_special`)
1. When `__float__()` returns a non-`float`, [`_as_double`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/math.py#L67-L79) raises `TypeError: <Cls>.__float__ returned non-float (type <T>)` instead of CPython 3.15.2's `TypeError: <Cls>.__float__() must return a float, not <T>`.
2. When `__float__ = None` (or `__trunc__ = None`, `__ceil__ = None`, `__floor__ = None`), `getattr(type(value), ..., None)` treats `None` as absent and falls through (either calling `__index__` or raising `must be real number` / `doesn't define __trunc__ method`) instead of raising `TypeError: 'NoneType' object is not callable`.

```python
import math, time, _statistics

class BadFloat:
    def __float__(self): return "abc"

class FloatNoneWithIndex:
    __float__ = None
    def __index__(self): return 1

class SpecialNone:
    __float__ = None
    __trunc__ = None
    __ceil__ = None
    __floor__ = None

for label, fn in [
    ("math.sin(BadFloat)", lambda: math.sin(BadFloat())),
    ("time.sleep(BadFloat)", lambda: time.sleep(BadFloat())),
    ("_statistics(BadFloat)", lambda: _statistics._normal_dist_inv_cdf(0.5, BadFloat(), 1.0)),
    ("math.sin(FloatNoneWithIndex)", lambda: math.sin(FloatNoneWithIndex())),
    ("_statistics(FloatNoneWithIndex)", lambda: _statistics._normal_dist_inv_cdf(0.5, FloatNoneWithIndex(), 1.0)),
    ("math.trunc(SpecialNone)", lambda: math.trunc(SpecialNone())),
    ("math.ceil(SpecialNone)", lambda: math.ceil(SpecialNone())),
    ("math.floor(SpecialNone)", lambda: math.floor(SpecialNone())),
]:
    try:
        print(label, "-> OK", fn())
    except Exception as e:
        print(label, "->", type(e).__name__, e)
```
- **CPython 3.15.2**:
  ```text
  math.sin(BadFloat) -> TypeError BadFloat.__float__() must return a float, not str
  time.sleep(BadFloat) -> TypeError BadFloat.__float__() must return a float, not str
  _statistics(BadFloat) -> TypeError BadFloat.__float__() must return a float, not str
  math.sin(FloatNoneWithIndex) -> TypeError 'NoneType' object is not callable
  _statistics(FloatNoneWithIndex) -> TypeError 'NoneType' object is not callable
  math.trunc(SpecialNone) -> TypeError 'NoneType' object is not callable
  math.ceil(SpecialNone) -> TypeError 'NoneType' object is not callable
  math.floor(SpecialNone) -> TypeError 'NoneType' object is not callable
  ```
- **Bella (`c8109ba`)**:
  ```text
  math.sin(BadFloat) -> TypeError BadFloat.__float__ returned non-float (type str)
  time.sleep(BadFloat) -> TypeError BadFloat.__float__ returned non-float (type str)
  _statistics(BadFloat) -> TypeError BadFloat.__float__ returned non-float (type str)
  math.sin(FloatNoneWithIndex) -> OK 0.8414709848078965
  _statistics(FloatNoneWithIndex) -> OK 1.0
  math.trunc(SpecialNone) -> TypeError type SpecialNone doesn't define __trunc__ method
  math.ceil(SpecialNone) -> TypeError must be real number, not SpecialNone
  math.floor(SpecialNone) -> TypeError must be real number, not SpecialNone
  ```

---

#### G15-08 — [`_bisect.py:33-34,84-85,91-92`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_bisect.py#L33-L93) (`_C_MAPPINGS`, `_size`, `_check_sq_item`)
1. `_C_MAPPINGS` omits `"_contextvars.Context"`, which in CPython has `mp_length`/`mp_subscript` and no `sq_length`/`sq_item`. Calling `_bisect.bisect_left(_contextvars.Context(), 1)` raises `TypeError: _contextvars.Context is not a sequence` in CPython, but returns `0` in Bella.
2. [`_size`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_bisect.py#L83-L88) and [`_check_sq_item`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_bisect.py#L90-L93) check `_tp_name(a) in _C_MAPPINGS` by string name rather than type identity, rejecting any user-defined sequence class named `dict` or `mappingproxy`.

```python
import _bisect, _contextvars

class dict:
    def __len__(self): return 0
    def __getitem__(self, i): return i

for obj in (_contextvars.Context(), dict()):
    try:
        print("OK", _bisect.bisect_left(obj, 1))
    except Exception as e:
        print(type(e).__name__, e)
```
- **CPython 3.15.2**:
  ```text
  TypeError _contextvars.Context is not a sequence
  OK 0
  ```
- **Bella (`c8109ba`)**:
  ```text
  OK 0
  TypeError dict is not a sequence
  ```

---

#### G15-09 — [`_md5.py:84`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_md5.py#L84-L88), [`_sha1.py:84`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_sha1.py#L84-L88), [`_sha2.py:84,136,188,240`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_sha2.py#L84-L88), [`_hmac.py:111`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_hmac.py#L111-L115)
[`MD5Type`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_md5.py#L84), [`SHA1Type`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_sha1.py#L84), [`SHA224Type`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_sha2.py#L84), [`SHA256Type`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_sha2.py#L136), [`SHA384Type`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_sha2.py#L188), [`SHA512Type`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_sha2.py#L240), and [`_hmac.HMAC`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_hmac.py#L111) lack a `__new__` disallowing direct instantiation (`Py_TPFLAGS_DISALLOW_INSTANTIATION`), returning an uninitialized instance instead of raising `TypeError: cannot create '...' instances`.

```python
import _md5, _sha1, _sha2, _hmac
for cls in (_md5.MD5Type, _sha1.SHA1Type, _sha2.SHA256Type, _hmac.HMAC):
    try:
        obj = cls()
        print(cls.__name__, "created:", type(obj).__name__)
    except Exception as e:
        print(cls.__name__, "->", type(e).__name__, e)
```
- **CPython 3.15.2**:
  ```text
  md5 -> TypeError cannot create '_md5.md5' instances
  sha1 -> TypeError cannot create '_sha1.sha1' instances
  SHA256Type -> TypeError cannot create '_sha2.SHA256Type' instances
  HMAC -> TypeError cannot create '_hmac.HMAC' instances
  ```
- **Bella (`c8109ba`)**:
  ```text
  md5 created: md5
  sha1 created: sha1
  SHA256Type created: SHA256Type
  HMAC created: HMAC
  ```

---

#### G15-10 — [`_csv.py:91,101,109,117,291,475,485,487`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_csv.py#L90-L120), [`_struct.py:66,623`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_struct.py#L64-L68), [`time.py:576`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/time.py#L574-L578)
When passed a `str` subclass overriding `__str__` or `__iter__`, [`_csv.Dialect`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_csv.py#L135), [`_csv.reader`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_csv.py#L291), [`_struct._format_text`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_struct.py#L64-L68), and [`time.strftime`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/time.py#L570-L578) call Python-level `str(v)` or `for c in line` instead of reading the underlying `str` value (`str.__str__(v)`).

```python
import _csv, struct, time

class MyStr(str):
    def __str__(self): return "i"
    def __iter__(self): raise RuntimeError("MyStr.__iter__")

print("csv delim:", repr(_csv.Dialect(delimiter=MyStr(";")).delimiter))
try:
    print("csv reader:", list(_csv.reader([MyStr("a,b")])))
except Exception as e:
    print("csv reader:", type(e).__name__, e)
print("struct calcsize:", struct.calcsize(MyStr("b")))
print("strftime:", repr(time.strftime(MyStr("%Y"), (2024, 1, 2, 3, 4, 5, 1, 2, 0))))
```
- **CPython 3.15.2**:
  ```text
  csv delim: ';'
  csv reader: [['a', 'b']]
  struct calcsize: 1
  strftime: '2024'
  ```
- **Bella (`c8109ba`)**:
  ```text
  csv delim: 'i'
  csv reader: RuntimeError MyStr.__iter__
  struct calcsize: 4
  strftime: 'i'
  ```

---

#### G15-11 — [`_random.py:180,189`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_random.py#L174-L195) (`Random.setstate`)
[`Random.setstate`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_random.py#L168-L195) uses `tuple.__len__(state)` at line 176, but indexes `state[i]` (line 180) and `state[_N]` (line 189) via `[]` instead of `tuple.__getitem__`, invoking a `tuple` subclass's `__getitem__` whereas CPython's `PyTuple_GET_ITEM` reads the underlying tuple array directly.

```python
import _random
class SubTuple(tuple):
    def __getitem__(self, i):
        raise RuntimeError("SubTuple.__getitem__")
st = SubTuple(_random.Random(1).getstate())
try:
    _random.Random().setstate(st)
    print("OK")
except Exception as e:
    print(type(e).__name__, e)
```
- **CPython 3.15.2**:
  ```text
  OK
  ```
- **Bella (`c8109ba`)**:
  ```text
  RuntimeError SubTuple.__getitem__
  ```

---

#### G15-12 — [`_csv.py:136-145,644-645,662-663`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_csv.py#L136-L145), [`_contextvars.py:249-250`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_contextvars.py#L249-L250), [`_bisect.py:48-49`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_bisect.py#L48-L49), [`_opcode.py:46-47`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_opcode.py#L46-L47), [`_md5.py:50-66`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_md5.py#L50-L66), [`_sha1.py:50-66`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_sha1.py#L50-L66), [`_sha2.py:50-66`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_sha2.py#L50-L66), [`_sha3.py:53-69,95-102`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_sha3.py#L53-L102), [`_blake2.py:102-116`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_blake2.py#L102-L116), [`_hmac.py:117-121,175-195,208-224`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_hmac.py#L175-L224), [`math.py:1045-1065,1182-1224`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/math.py#L1182-L1224), [`_thread.py:129,599-612`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_thread.py#L599-L612)
`_PyArg_UnpackKeywords` / Argument Clinic order and message discrepancies:
1. When `nargs == 0` and `len(kwds) > maxargs`, these functions omit `"keyword "` in `takes at most N keyword arguments (M given)` (and [`_csv.Dialect`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_csv.py#L136-L145) does not check total argument count before scanning `kwds`).
2. [`_hmac.new`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_hmac.py#L175-L195), [`_hmac.compute_digest`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_hmac.py#L208-L224), [`math.isclose`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/math.py#L1182-L1204), and [`_thread.start_joinable_thread`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_thread.py#L597-L612) check unknown keywords before missing required positional arguments (`missing required argument '...' (pos 1)`), and check `kwds` in caller iteration order rather than checking known parameter slots for duplicate positional+keyword arguments first.
3. [`_md5._parse_new`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_md5.py#L50-L66), [`_sha1._parse_new`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_sha1.py#L50-L66), [`_sha2._parse_new`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_sha2.py#L50-L66), and [`_sha3._parse_new`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_sha3.py#L53-L69) evaluate `bool(usedforsecurity)` inside the `kwds` loop before validating remaining keywords, and omit `_keyword_suggestion`; [`_blake2.py:111`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_blake2.py#L111) passes `_PARAMETERS[1:]` (omitting `"data"`), and [`_thread.py:129,607`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_thread.py#L129) omits `_keyword_suggestion`.

```python
import _csv, _contextvars, _bisect, _opcode, _md5, _blake2, _hmac, math, _thread

class BadBool:
    def __bool__(self): raise RuntimeError("bad bool")

for label, fn in [
    ("csv.get_dialect", lambda: _csv.get_dialect(a=1, b=2)),
    ("ContextVar", lambda: _contextvars.ContextVar("v", default=1, extra=2)),
    ("bisect_left", lambda: _bisect.bisect_left(a=[], x=1, lo=0, hi=0, key=None, extra=1)),
    ("opcode.is_valid", lambda: _opcode.is_valid(op=1, extra=2)),
    ("hmac.new(bad=1)", lambda: _hmac.new(bad=1)),
    ("math.isclose(bad=1)", lambda: math.isclose(bad=1)),
    ("start_joinable(bad=1)", lambda: _thread.start_joinable_thread(bad=1)),
    ("md5(dup+bad)", lambda: _md5.md5(b"a", bad=1, data=b"b")),
    ("md5(bool+bad)", lambda: _md5.md5(usedforsecurity=BadBool(), bad=1)),
    ("md5(dat=)", lambda: _md5.md5(dat=b"a")),
    ("blake2b(dat=)", lambda: _blake2.blake2b(dat=b"a")),
    ("lock.acquire(blockin=)", lambda: _thread.lock().acquire(blockin=True)),
]:
    try:
        fn()
    except Exception as e:
        print(f"{label}: {type(e).__name__}: {e}")
```
- **CPython 3.15.2**:
  ```text
  csv.get_dialect: TypeError: get_dialect() takes at most 1 keyword argument (2 given)
  ContextVar: TypeError: ContextVar() takes at most 1 keyword argument (2 given)
  bisect_left: TypeError: bisect_left() takes at most 5 keyword arguments (6 given)
  opcode.is_valid: TypeError: is_valid() takes at most 1 keyword argument (2 given)
  hmac.new(bad=1): TypeError: new() missing required argument 'key' (pos 1)
  math.isclose(bad=1): TypeError: isclose() missing required argument 'a' (pos 1)
  start_joinable(bad=1): TypeError: start_joinable_thread() missing required argument 'function' (pos 1)
  md5(dup+bad): TypeError: argument for md5() given by name ('data') and position (1)
  md5(bool+bad): TypeError: md5() got an unexpected keyword argument 'bad'
  md5(dat=): TypeError: md5() got an unexpected keyword argument 'dat'. Did you mean 'data'?
  blake2b(dat=): TypeError: blake2b() got an unexpected keyword argument 'dat'. Did you mean 'data'?
  lock.acquire(blockin=): TypeError: acquire() got an unexpected keyword argument 'blockin'. Did you mean 'blocking'?
  ```
- **Bella (`c8109ba`)**:
  ```text
  csv.get_dialect: TypeError: get_dialect() takes at most 1 argument (2 given)
  ContextVar: TypeError: ContextVar() takes at most 1 argument (2 given)
  bisect_left: TypeError: bisect_left() takes at most 5 arguments (6 given)
  opcode.is_valid: TypeError: is_valid() takes at most 1 argument (2 given)
  hmac.new(bad=1): TypeError: new() got an unexpected keyword argument 'bad'
  math.isclose(bad=1): TypeError: isclose() got an unexpected keyword argument 'bad'
  start_joinable(bad=1): TypeError: start_joinable_thread() got an unexpected keyword argument 'bad'
  md5(dup+bad): TypeError: md5() got an unexpected keyword argument 'bad'
  md5(bool+bad): RuntimeError: bad bool
  md5(dat=): TypeError: md5() got an unexpected keyword argument 'dat'
  blake2b(dat=): TypeError: blake2b() got an unexpected keyword argument 'dat'
  lock.acquire(blockin=): TypeError: acquire() got an unexpected keyword argument 'blockin'
  ```

---

#### G15-13 — [`_opcode.py:146-153`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_opcode.py#L146-L153) (`stack_effect`, `get_executor`)
[`_opcode.stack_effect`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_opcode.py#L146-L148) and [`_opcode.get_executor`](file:///home/nathan/workspaces/nth/bella-g15/runtime/prelude/_opcode.py#L151-L153) unconditionally call `_bella_refuse(...)` before validating arguments or computing opcode stack effects (which only takes integer opcodes and an optional `oparg` / `jump` flag, no code object).

```python
import _opcode
print(_opcode.stack_effect(1))
```
- **CPython 3.15.2**:
  ```text
  -2
  ```
- **Bella (`c8109ba`)**:
  ```text
  bella: not implemented: _opcode.stack_effect (bytecode stack effects, decision E-02)
  ```

---

#### G15-14 — [`slots.cpp:365-368`](file:///home/nathan/workspaces/nth/bella-g15/runtime/src/slots.cpp#L365-L368) (`dictview_slot`)
In [`dictview_slot`](file:///home/nathan/workspaces/nth/bella-g15/runtime/src/slots.cpp#L365-L368) (added in `954f8d6`), `wrapper_args(a, reflected ? "__ror__" : "__or__", 1)` hardcodes `"__or__"` / `"__ror__"` for all 8 dict-view binary operator descriptors (`__and__`, `__rand__`, `__sub__`, `__rsub__`, `__xor__`, `__rxor__`).

```python
for m in ("__and__", "__rand__", "__sub__", "__xor__"):
    try:
        getattr({}.keys(), m)(x=1)
    except TypeError as e:
        print(m, "->", e)
```
- **CPython 3.15.2**:
  ```text
  __and__ -> wrapper __and__() takes no keyword arguments
  __rand__ -> wrapper __rand__() takes no keyword arguments
  __sub__ -> wrapper __sub__() takes no keyword arguments
  __xor__ -> wrapper __xor__() takes no keyword arguments
  ```
- **Bella (`c8109ba`)**:
  ```text
  __and__ -> wrapper __or__() takes no keyword arguments
  __rand__ -> wrapper __ror__() takes no keyword arguments
  __sub__ -> wrapper __or__() takes no keyword arguments
  __xor__ -> wrapper __or__() takes no keyword arguments
  ```

---

### Focus 4: PEP 563 & Annotations in the Runtime and Pipeline (`a24ecc0`, `37c3487`)

#### G15-15 — [`call.cpp:2098`](file:///home/nathan/workspaces/nth/bella-g15/runtime/src/call.cpp#L2096-L2104) (`runtime_call` `setup_annotations`)
In `setup_annotations`, [`runtime_call`](file:///home/nathan/workspaces/nth/bella-g15/runtime/src/call.cpp#L2096-L2104) checks `if (is_kind(ns, Kind::Dict))` and calls `dict_get` directly on the underlying C++ `Dict` table instead of checking for an exact `dict` (`ns.header()->cls == &dict_type`, matching CPython's `PyDict_CheckExact` in `PyMapping_GetOptionalItem` and [`eval1.py:1604`](file:///home/nathan/workspaces/nth/bella-g15/pipeline/l1/eval1.py#L1603-L1616)). When a metaclass's `__prepare__` returns a `dict` subclass, Bella bypasses `CustomDict.__getitem__("__annotations__")` and overwrites `ns["__annotations__"] = {}`.

```python
events = []
class CustomDict(dict):
    def __getitem__(self, k):
        events.append(("get", k))
        if k == "__annotations__":
            d = {"pre": int}
            super().__setitem__(k, d)
            return d
        return super().__getitem__(k)

class Meta(type):
    @classmethod
    def __prepare__(metacls, name, bases):
        return CustomDict()

class M(metaclass=Meta):
    x: str = "a"

print(events)
print(M.__annotations__)
```
- **CPython 3.15.2**:
  ```text
  [('get', '__name__'), ('get', '__annotations__'), ('get', '__annotations__')]
  {'pre': <class 'int'>, 'x': <class 'str'>}
  ```
- **Bella (`c8109ba`)**:
  ```text
  [('get', '__name__'), ('get', '__annotations__')]
  {'x': <class 'str'>}
  ```

---

#### G15-16 — [`annotations.py:274,413,521`](file:///home/nathan/workspaces/nth/bella-g15/pipeline/staging/annotations.py#L271-L276) (`_Owners.visit_FunctionDef`, `_generate`, `evaluators_for_source`)
When `from __future__ import annotations` is active (`owner.strings = True`) and a function has a starred vararg annotation `*args: *Ts`, [`_Owners.visit_FunctionDef`](file:///home/nathan/workspaces/nth/bella-g15/pipeline/staging/annotations.py#L274) strips `ast.Starred` (`ann.value if isinstance(ann, ast.Starred) else ann`). In [`_generate`](file:///home/nathan/workspaces/nth/bella-g15/pipeline/staging/annotations.py#L412-L414), the `if owner.strings:` branch emits `ast.Constant(ast.unparse(ann))` without prefixing `"*"` when `starred` is `True` (producing `'Ts'` instead of `'*Ts'`), and `by_span` at line 521 only indexes `ann.value` rather than the `ast.Starred` node.

```python
import tempfile
from pathlib import Path
from pipeline.staging.annotations import evaluators_for_source

with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
    f.write("from __future__ import annotations\ndef g(x: int, *args: *Ts) -> str:\n    return 'ok'\n")
    path = f.name
evs, declined = evaluators_for_source(path)
Path(path).unlink()
print("evaluators:", len(evs), "declined:", declined)
```
- **Expected**:
  ```text
  evaluators: 1 declined: []
  ```
- **Bella (`c8109ba`)**:
  ```text
  evaluators: 0 declined: ["g.__annotate__:2: MISMATCH STRING: CPython {'x': 'int', 'args': '*Ts', 'return': 'str'}, evaluator {'x': 'int', 'args': 'Ts', 'return': 'str'}"]
  ```

---

#### G15-17 — [`frontend.py:449`](file:///home/nathan/workspaces/nth/bella-g15/pipeline/l1/frontend.py#L436-L452) (`_TypeParams.thunk`)
In [`_TypeParams.thunk`](file:///home/nathan/workspaces/nth/bella-g15/pipeline/l1/frontend.py#L436-L452) (used for PEP 695 `TypeAliasType.evaluate_value`, `TypeVar.evaluate_bound`, and `TypeVar.evaluate_default`), `fn.bella_public = {fmt: "format"}` sets the public parameter name to `"format"`. In CPython 3.15.2 (`codegen_setup_annotations_scope`), only `__annotate__` renames `.format` to `"format"`; PEP 695 evaluate functions keep `".format"`. Consequently, `co_varnames` is `('format',)` instead of `('.format',)` and passing `format=1` by keyword raises the positional-only error instead of `got an unexpected keyword argument 'format'`.

```python
type Alias = int
def f[T: int = str](x: T) -> T:
    return x

for fn in (Alias.evaluate_value, f.__type_params__[0].evaluate_bound, f.__type_params__[0].evaluate_default):
    print(fn.__code__.co_varnames)
    try:
        fn(format=1)
    except TypeError as e:
        print(e)
```
- **CPython 3.15.2**:
  ```text
  ('.format',)
  Alias() got an unexpected keyword argument 'format'
  ('.format',)
  T() got an unexpected keyword argument 'format'
  ('.format',)
  T() got an unexpected keyword argument 'format'
  ```
- **Bella (`c8109ba`)**:
  ```text
  ('format',)
  Alias() got some positional-only arguments passed as keyword arguments: 'format'
  ('format',)
  T() got some positional-only arguments passed as keyword arguments: 'format'
  ('format',)
  T() got some positional-only arguments passed as keyword arguments: 'format'
  ```

---

#### G15-18 — [`eval2.py:481-485,496,530,819-825`](file:///home/nathan/workspaces/nth/bella-g15/pipeline/l2/eval2.py#L481-L496) (`_Translator.function`, `_Translator.params`, `_check_slots`)
In [`eval2.py`](file:///home/nathan/workspaces/nth/bella-g15/pipeline/l2/eval2.py#L481-L496), declaring a parameter by its `p.public` name (`format` in `__annotate__`) in the generated host function collides when `"format"` is also a free variable or cell variable of `__annotate__`:
1. When an enclosing function binds `format` (`def outer(): format = int; def f(x: format): pass`), `"format"` is in `code.freevars`, so [`_Translator.function`](file:///home/nathan/workspaces/nth/bella-g15/pipeline/l2/eval2.py#L478-L496) emits `def _l2_c2(format, /): ... nonlocal format`, raising `SyntaxError: name 'format' is parameter and nonlocal` in [`compile_module`](file:///home/nathan/workspaces/nth/bella-g15/pipeline/l2/eval2.py#L840).
2. When `"format"` is in `code.cellvars` alongside another cell variable such as `"a"` (`def f(x: [(a := y) for y in (1,)], w: [(format := y) for y in (2,)]): pass`), the host compiler treats `format` as a parameter cell and places it first in `co_cellvars` (`('format', 'a')`), whereas L2 sorts non-parameter cells alphabetically (`('a', 'format')`), raising [`SlotMismatch`](file:///home/nathan/workspaces/nth/bella-g15/pipeline/l2/eval2.py#L825).

```python
from pipeline.l1.frontend import lower
from pipeline.l2.lower import to_l2
from pipeline.l2.lifetimes import lifetimes
from pipeline.l2 import eval2

for label, src in [
    ("freevar", "def outer():\n    format = int\n    def f(x: format): pass\n    return f.__annotations__\nprint(outer())"),
    ("cellvar", "def f(x: [(a := y) for y in (1,)], w: [(format := y) for y in (2,)]): pass\nprint(f.__annotations__)"),
]:
    ns = {}
    exec(src, ns)
    try:
        eval2.Interpreter().run_module(lifetimes(to_l2(lower(src, "<test>"))))
    except Exception as e:
        print(label, "eval2 ->", type(e).__name__, e)
```
- **CPython 3.15.2**:
  ```text
  {'x': <class 'int'>}
  {'x': [1], 'w': [2]}
  ```
- **Bella `eval2` (`c8109ba`)**:
  ```text
  freevar eval2 -> SyntaxError name 'format' is parameter and nonlocal (<test>, line 3)
  cellvar eval2 -> SlotMismatch f.__annotate__: the host compiled (('format', '_format0', '_ann1', '_comp3', '_comp6'), ('format', 'a'), ()), L2 says (('format', '_format0', '_ann1', '_comp3', '_comp6'), ('a', 'format'), ())
  ```

---

#### G15-19 — [`frontend.py:1713-1715,1757-1758`](file:///home/nathan/workspaces/nth/bella-g15/pipeline/l1/frontend.py#L1713-L1760) (`_Comprehensions.comprehension`, `_hoist`) and [`resolve.py:107-108`](file:///home/nathan/workspaces/nth/bella-g15/pipeline/l2/resolve.py#L107-L108) (`_Collector.function`)
When a comprehension containing an assignment expression `[(t := y) for y in ...]` appears inside an annotation (`__annotate__`), [`_hoist`](file:///home/nathan/workspaces/nth/bella-g15/pipeline/l1/frontend.py#L1757-L1758) treats `__annotate__` as a `"function"` scope and [`_Collector.function`](file:///home/nathan/workspaces/nth/bella-g15/pipeline/l2/resolve.py#L107-L108) binds `f.enclosing_binds` directly in `parent` (`__annotate__`). In CPython (`symtable_extend_namedexpr_scope`), walrus targets inside comprehensions skip annotation scopes (`AnnoBlock`) and bind in the enclosing function or module scope.

```python
def f(x: [(t := y) for y in (42,)]):
    pass
print("annotations:", f.__annotations__)
print("module t:", globals().get("t", "MISSING"))

def outer():
    def g(x: [(u := y) for y in (99,)]):
        pass
    _ = g.__annotations__
    print("g.__annotate__ varnames/freevars:", g.__annotate__.__code__.co_varnames, g.__annotate__.__code__.co_freevars)
    try:
        return u
    except NameError as e:
        return f"NameError: {e}"
print("outer u:", outer())
```
- **CPython 3.15.2**:
  ```text
  annotations: {'x': [42]}
  module t: 42
  g.__annotate__ varnames/freevars: ('format', 'y') ('u',)
  outer u: 99
  ```
- **Bella (`c8109ba`)**:
  ```text
  annotations: {'x': [42]}
  module t: MISSING
  g.__annotate__ varnames/freevars: ('format', 'y', 'u') ()
  outer u: NameError: name 'u' is not defined
  ```
