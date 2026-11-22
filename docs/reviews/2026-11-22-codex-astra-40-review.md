Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-22. Verbatim. Tag A40 in the review log. Several steps in one review (the author's
rule of 2026-11-22): its range is `c1a3dbd..98d8f3f`, run non-interactively (standard input closed) in its own worktree (`bella-r40`) at
`98d8f3f`: the fixes of review A39, a slot named twice, how a Struct gets its format, and the minimal memoryview. Its probes
(`r40-probes/codex/`) stayed in that worktree. 17 findings; each was run on both sides by the session before any verdict (review log, A40).

---

# Bella conformance review A40

Detached at `98d8f3f`, reviewing `c1a3dbd..98d8f3f` against CPython 3.15.2. There are **17 verified findings (8 high, 9 medium)**. The tables give stdout in line order, with ` / ` separating lines. Both stderr files are empty and both exit statuses are zero unless indicated. The probes catch exceptions to show what a caller can branch on.

For each row below, from the checkout, set `p=r40-probes/codex/view/prog.py`, build with `timeout 600 ./r40-build "$p"`, then run `PYTHONHASHSEED=0 timeout 120 .venv/bin/python "$p" ROW` and `PYTHONHASHSEED=0 timeout 120 BINARY ROW` under `ulimit -v 8000000`. The source and six output files per row are beside each other under the suite directory. The examples use `v = memoryview(bytearray(b"abc"))` unless specified.

| Finding and row | Minimal operation | CPython | Bella | Cause |
|---|---|---|---|---|
| A40-01 medium, `cache` | Give a bytes subclass a hash that prints `hash` and returns 1, and a finalizer that prints `exporter gone`. Make `m=memoryview(B(b"a"))`. Print `hash(m)==hash(b"a")` twice, release it and print the comparison again. | `hash / True / True / exporter gone / True` | `hash / True / hash / True / exporter gone / ValueError` | runtime/prelude/memoryview.py:400 computes the exporter and content hashes on every call. CPython caches the first successful result on the view and can return it even after release. |
| A40-02 high, `weak` | Make `m=memoryview(B(b"a"))` with a printing exporter finalizer. Keep `r=weakref.ref(m, lambda r: print("view gone"))`, delete m, print r(). | `exporter gone / view gone / None` | `view gone / exporter gone / None` | CPython's memory_dealloc returns the export before clearing weakrefs. Bella selects the common weakrefs-first order at runtime/src/call.cpp:1912. This happens inside the function. |
| A40-03 medium, `tuple` | Give a tuple subclass T a printing __bool__ returning False. Print `v[T((0,))]`. | `97` | `bool / NotImplementedError` | runtime/prelude/memoryview.py:307 tests Python truth and then iterates the key. CPython reads the concrete tuple cells and length. |
| A40-04 medium, `order` | Give a str subclass S an __eq__ that prints its argument and returns False. Print `v.tobytes(S("C"))`. | `b'abc'` | `eq C / eq F / eq A / ValueError` | runtime/prelude/memoryview.py:362 uses Python membership to parse an order whose Unicode data CPython reads directly. Additional rows surface/surrogate-{plain,reverse,slice,empty,gone}: v.tobytes(chr(0xd800)) prints UnicodeEncodeError under CPython and ValueError under Bella in all five. CPython converts order to UTF-8 before entering the method, even on a released view. |
| A40-05 medium, `stride` | Print `v[::1<<62][::4].strides`. | `(0,)` | `(18446744073709551616,)` | runtime/prelude/memoryview.py:302 multiplies as arbitrary-precision integers. The pinned interpreter stores the product in a signed machine-sized stride. The view has one accessible item throughout. |
| A40-06 high, `sub`, `set` | In I.__index__, call v.release(), print "released", return 0. Read `v[I()]`, or assign `v[0]=I()` and print the exporter. | Both `released / ValueError` | Read `released / 97`. Write `released / bytearray(b'\x00bc')` | runtime/prelude/memoryview.py:295 and :325 retain the exporter across user conversion and access it without rechecking release. The assignment changes a byte after release succeeded. |
| A40-07 high, `slice` | Using the same I, print `v[I():].tolist()`. | `released / [97, 98, 99]` | `released / ValueError` | runtime/prelude/memoryview.py:300 copies the hold after converting bounds. CPython's memory_subscript registers the child before init_slice invokes the callback. |

### Bytes-like consumers

Use the same commands with `p=r40-probes/codex/consumers/prog.py`. Here `v=memoryview(bytearray(b"6162"))`; the stride variant uses `v[::2]`, and the released variant calls `v.release()` first. Each error below was caught and printed, with full text in the row's output files.

| Finding and rows | Minimal operation | CPython stdout | Bella stdout | Cause |
|---|---|---|---|---|
| A40-08 medium, `text-stride`, `text-released` | Override io.BytesIO.read1 to return v, then call io.TextIOWrapper(Raw()).read(1). | Both `TypeError underlying read1() should have returned a bytes-like object, not 'memoryview'` | `BufferError memoryview: underlying buffer is not C-contiguous`, or `ValueError operation forbidden on released memoryview object` | runtime/prelude/_io.py:2964 passes the type check and propagates the conversion error where CPython replaces a failed buffer acquisition. |
| A40-09 high, `extend-stride`, `extend-released` | Extend an empty bytearray with v and print it. | Both `TypeError can't set bytearray slice from memoryview` | `bytearray(b'66')`, or the released-view ValueError above | runtime/src/bytes.cpp:1394 copies a full view. CPython's extend requires a simple buffer and converts acquisition failures to TypeError. |
| A40-10 high, `fromhex-*`, `afromhex-*` (six rows) | Print bytes.fromhex(v) or bytearray.fromhex(v). | Contiguous `b'ab'` or `bytearray(b'ab')`; stride BufferError; released ValueError (full texts as above). | All six `TypeError fromhex() argument must be str or bytes-like, not memoryview` | runtime/src/bytes.cpp:651 excludes views from the bytes-like input path. The pinned CPython accepts an ASCII buffer for both constructors. |
| A40-11 medium, `hexlify-stride`, `hexlify-released` | Print binascii.unhexlify(v). | Both `TypeError argument should be bytes, buffer or ASCII string, not 'memoryview'` | Stride BufferError or released ValueError as above | runtime/prelude/binascii.py:95 lets a conversion failure escape the ASCII buffer converter. |
| A40-12 high, `sub-contiguous` | Print re.sub(b"b", v, b"abc"). | `b'a6162c'` | `ValueError cannot hash writable memoryview object` | runtime/src/sre.cpp:960 scans bytes_data(repl) even though get_string has already supplied the view’s buffer. bytes_data expects a BytesObject (runtime/src/bytes.cpp:24). runtime/prelude/_sre.py:325 consequently passes the writable view into the hash-keyed template compiler. |

### Exporter callbacks

Use the commands above with `p=r40-probes/codex/export/prog.py` (or `surface/prog.py` for the indicated row).

| Finding and rows | Minimal operation | CPython stdout | Bella stdout | Cause |
|---|---|---|---|---|
| A40-13 high, `block`, `surface/forhash-plain` | Make v a view of a bytes subclass whose __hash__ releases v. In block, catch and print the exception class inside __hash__, return 1, then print the content-hash comparison and v.tobytes(). In forhash-plain, print "hash callback" and let the failure propagate. | block: `BufferError / True / b'xy'`; forhash: `hash callback / BufferError` | block: `True / ValueError`; forhash: `hash callback / True` | runtime/prelude/memoryview.py:404 calls hash(exporter) without increasing the view's own export count across that callback. CPython's memory_hash temporarily increments it. This affects the first call, independently of the cache in A40-01. |
| A40-14 high, `hook`, `refuse`, `compare` | Override __buffer__ on B(bytes) to print flags and return memoryview(b"changed"), and __release_buffer__ to print "release". Print memoryview(B(b"x")).tobytes() then release it. Alternatively print memoryview(b"changed")==B(b"x"). On A(bytearray), have __buffer__ raise LookupError and print memoryview(A(b"x")).tolist(). | hook: `buffer 284 / b'changed' / release`; refuse: `LookupError`; compare: `buffer 284 / release / True` | hook: `b'x'`; refuse: `[120]`; compare: `False` | runtime/prelude/memoryview.py:201 and :155 check bytes/bytearray ancestry before considering the buffer hook in both __new__ and _octets_of. These rows silently use the base storage. Even the raising override becomes a successful construction. |

The additional `export/weak` row reproduces A40-02 with the last view descended from a reversed slice. CPython prints `drop / weak / None`, Bella `weak / drop / None`.

### A40-15 medium — the memory iterator is presented as a subclassable type with unchecked methods

Use the `construct` suite, with `v=memoryview(b"ab")` and `T=type(iter(v))`. Row `itersub` prints `type("S",(T,),{}).__name__`: CPython catches TypeError and Bella prints `S`. In row `next`, calling `T.__next__(v)` gives TypeError under CPython and AttributeError under Bella. The Python method body attempts to read iterator state from the wrong receiver.

Both decisions depend on the CPython type metadata for the hidden class. runtime/src/call.cpp:4041 presents its methods and looks up its final flag, but the type metadata lacks the memory_iterator entries. CPython's slot wrapper enforces its receiver and its type disallows subclassing.

The `conversion/metadata` row prints the types of T.__next__ and T.__iter__: CPython gives `('wrapper_descriptor', 'wrapper_descriptor')`, Bella `('function', 'function')`. In `conversion/iterwrong`, `T.__iter__(v) is v` prints `True` on Bella. CPython prints `TypeError descriptor '__iter__' requires a 'memory_iterator' object but received a 'memoryview'`.

### A40-16 medium — bytearray partitioning rejects a strided separator

At runtime/src/bytes.cpp:399 the shared partition/rpartition implementation requests a simple buffer. CPython's bytearray methods first copy the entire separator with _PyByteArray_FromBufferObject. With `v=memoryview(b"axe")[::2]`, both `bytearray(b"baec").partition(v)` and `bytearray(b"baec").rpartition(v)` print `(bytearray(b'b'), bytearray(b'ae'), bytearray(b'c'))` under CPython and raise BufferError under Bella. Start the `extra` suite with `partition-partition` or `partition-rpartition`. The `methods/rpartition-stride` row also checks a separator with no match: CPython prints `(bytearray(b''), bytearray(b''), bytearray(b'4142'))`; Bella prints `BufferError memoryview: underlying buffer is not C-contiguous`.

### A40-17 medium — assigning an octet propagates the wrong exception class

At runtime/prelude/memoryview.py:325, _number_index(value) propagates its exception directly. CPython's pack_single passes the failure through fix_error_int. An OverflowError or a subclass of ValueError becomes a plain ValueError, and a subclass of TypeError becomes a plain TypeError. A caller can distinguish all four cases below by exception class alone.

Run the `conversion` suite. Give the assigned value an __index__ that raises the indicated exception with the argument "from callback", then execute `v[0] = I()` on a writable view.

| Row | CPython stdout | Bella stdout |
|---|---|---|
| overflow | `ValueError memoryview: invalid value for format 'B'` | `OverflowError from callback` |
| myoverflow | `ValueError memoryview: invalid value for format 'B'` | `MyOverflow from callback` |
| myvalue | `ValueError memoryview: invalid value for format 'B'` | `MyValue from callback` |
| mytype | `TypeError memoryview: invalid type for format 'B'` | `MyType from callback` |

### Minimal executable programs

[The minimal suite](r40-probes/codex/minimal/prog.py) contains one independent function per finding, numbered in report order. Each has also been built and run on both interpreters. From this checkout:

```sh
ulimit -v 8000000
export PYTHONHASHSEED=0
p=r40-probes/codex/minimal/prog.py
bin=$(timeout 600 ./r40-build "$p")
for row in $(seq -w 1 17); do
    timeout 120 .venv/bin/python "$p" "$row"
    timeout 120 "$bin" "$row"
done
```

The programs share the imports and exception handler in the linked file. Each row below uses only its numbered function and prints the class of any exception it catches.

<details><summary>A40-01 — CPython <code>hash / True / True</code> · Bella <code>hash / True / ValueError</code></summary>

```python
def f01():
    class B(bytes):
        def __hash__(self):
            print("hash")
            return 1
    v = memoryview(B(b"a"))
    print(hash(v) == hash(b"a"))
    v.release()
    print(hash(v) == hash(b"a"))
```

</details>

<details><summary>A40-02 — CPython <code>exporter / view / None</code> · Bella <code>view / exporter / None</code></summary>

```python
def f02():
    class B(bytes):
        def __del__(self): print("exporter")
    v = memoryview(B(b"a"))
    r = weakref.ref(v, lambda r: print("view"))
    del v
    print(r())
```

</details>

<details><summary>A40-03 — CPython <code>97</code> · Bella <code>NotImplementedError</code></summary>

```python
def f03():
    class T(tuple):
        def __bool__(self): return False
    print(memoryview(b"a")[T((0,))])
```

</details>

<details><summary>A40-04 — CPython <code>b'a'</code> · Bella <code>ValueError</code></summary>

```python
def f04():
    class S(str):
        def __eq__(self, other): return False
    print(memoryview(b"a").tobytes(S("C")))
```

</details>

<details><summary>A40-05 — CPython <code>(0,)</code> · Bella <code>(18446744073709551616,)</code></summary>

```python
def f05():
    print(memoryview(b"a")[::1 << 62][::4].strides)
```

</details>

<details><summary>A40-06 — CPython <code>ValueError</code> · Bella <code>97</code></summary>

```python
def f06():
    v = memoryview(bytearray(b"a"))
    class I:
        def __index__(self):
            v.release()
            return 0
    print(v[I()])
```

</details>

<details><summary>A40-07 — CPython <code>b'a'</code> · Bella <code>ValueError</code></summary>

```python
def f07():
    v = memoryview(b"a")
    class I:
        def __index__(self):
            v.release()
            return 0
    print(v[I():].tobytes())
```

</details>

<details><summary>A40-08 — CPython <code>TypeError</code> · Bella <code>BufferError</code></summary>

```python
def f08():
    class Raw(io.BytesIO):
        def read1(self, n): return memoryview(b"abc")[::2]
    print(io.TextIOWrapper(Raw()).read(1))
```

</details>

<details><summary>A40-09 — CPython <code>TypeError</code> · Bella <code>bytearray(b'ac')</code></summary>

```python
def f09():
    a = bytearray()
    a.extend(memoryview(b"abc")[::2])
    print(a)
```

</details>

<details><summary>A40-10 — CPython <code>b'a'</code> · Bella <code>TypeError</code></summary>

```python
def f10():
    print(bytes.fromhex(memoryview(b"61")))
```

</details>

<details><summary>A40-11 — CPython <code>TypeError</code> · Bella <code>BufferError</code></summary>

```python
def f11():
    print(binascii.unhexlify(memoryview(b"abc")[::2]))
```

</details>

<details><summary>A40-12 — CPython <code>b'y'</code> · Bella <code>ValueError</code></summary>

```python
def f12():
    print(re.sub(b"x", memoryview(bytearray(b"y")), b"x"))
```

</details>

<details><summary>A40-13 — CPython <code>BufferError</code> · Bella <code>True</code></summary>

```python
def f13():
    class B(bytes):
        def __hash__(self):
            v.release()
            return 1
    v = memoryview(B(b"a"))
    print(hash(v) == hash(b"a"))
```

</details>

<details><summary>A40-14 — CPython <code>LookupError</code> · Bella <code>[97]</code></summary>

```python
def f14():
    class B(bytes):
        def __buffer__(self, flags): raise LookupError
    print(memoryview(B(b"a")).tolist())
```

</details>

<details><summary>A40-15 — CPython <code>TypeError</code> · Bella <code>S</code></summary>

```python
def f15():
    T = type(iter(memoryview(b"a")))
    print(type("S", (T,), {}).__name__)
```

</details>

<details><summary>A40-16 — CPython <code>(bytearray(b'b'), bytearray(b'ae'), bytearray(b'c'))</code> · Bella <code>BufferError</code></summary>

```python
def f16():
    print(bytearray(b"baec").partition(memoryview(b"axe")[::2]))
```

</details>

<details><summary>A40-17 — CPython <code>ValueError</code> · Bella <code>OverflowError</code></summary>

```python
def f17():
    class I:
        def __index__(self): raise OverflowError("index")
    memoryview(bytearray(b"a"))[0] = I()
```

</details>

### Checks that agreed

* All 13 resize/lifetime rows agreed. A view of a reversed slice of a bytearray subclass saw in-place writes during iteration, ignored overridden length and indexing, and kept the exporter alive until explicit release. The suite compared append, extend, pop, clear, in-place addition and multiplication, deletion of a stepped slice, length-changing slice assignment, resize(), reinitialization, and no-op operations. Each row also checked the bytes left after the operation.
* All 972 rows in `slots`, 1,656 in `numeric`, and 108 in `descriptor` agreed. Another 558 in `slotmore` agreed. These recorded calls and result or exception classes for special methods stored on classes and metaclasses, including functions and lambdas, staticmethods, classmethods, built-ins, bound methods, slot wrappers, callable instances, partials, properties and classmethod(None). The descriptor rows exercised inherited hooks after deletion of a shadowing hook. The numeric rows covered reflected and in-place operations. The requested exclusion for overriding __getattribute__ applies to the remaining slotmore rows.
* In `frames` all 24 branch, loop, handler, with, match, lambda and nested-scope rows agreed, including zero, one and several iterations, break, continue, walrus targets and loop else. The checked genexpr traceback names and line numbers agreed for a failing filter, zero-argument super() in a classmethod and in a nested function, and the later iterable of a comprehension. Generator-helper lifetime is already recorded in TODO.md.
* All 27 rows in `formats` and `structmore` agreed. They included both construction hooks, properties and slots shadowing format and size, cache lookups with subclass keys, invalid formats, shallow and deep copy, and ignored, recorded and error-promoted warnings. A separate row agreed on the warning's source line and filename. Repeated private slot names colliding after mangling agreed with default, short and full __slotnames__.
* The view attribute tuples, item lists and byte copies agreed on fresh, reversed, sliced, empty and released views. The tested raising keys and slice bounds, comparisons with subclasses, and iteration/membership during in-place mutation agreed. Rebinding builtins.memoryview left the tested slicing, copying and equality results in agreement.
* Consumer checks included OS scalar and vectored writes, raw and buffered file writes, Path.write_bytes, shutil.copyfileobj, BytesIO.writelines, codecs, int.from_bytes, hashlib and HMAC construction and update, zlib compression, struct unpacking, re captures and callback mutation, and bytes/bytearray search, translation, formatting and concatenation. The `methods` suite agreed on 110 of 111 rows. The observed exceptions caused by a consumer omitting a temporary buffer export are already covered by the project's open buffer items.

Across the saved suites, 3,793 row pairs have all six evidence files. 3,676 matched byte for byte on stdout, stderr and exit status. The total includes minimized reproductions, excluded rows and named stops. No run timed out or terminated by signal. Coverage is empirical for the combinations present in the [probe sources and outputs](r40-probes/codex/).
