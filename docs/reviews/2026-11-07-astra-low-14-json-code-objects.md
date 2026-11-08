Codex astra-low (`gpt-6-astra`, effort low), 2026-11-07, asked by the author. Verbatim. Tag A14 in the review log. Its range is
`3ea072a..46a5742` (two commits: the code objects behind `function.__code__` and `__closure__` with the A13/G13 fixes, and
`_json` with the build's search of `PYTHONPATH`). It ran in a detached checkout at `46a5742` with a shared, pre-built `build/`.

---

Found **8 reproducible defects**, ranked below. Each minimal program was compiled and compared with the pinned CPython 3.15.2 using `PYTHONHASHSEED=0`. No tracked files were changed.

The compiled scanner/hook/indent probes and the combined prior-review regression cases passed. Separately, 69,905 short scanner inputs matched when running the shim under CPython.

1. **Float subclass comparisons can corrupt JSON output** — `runtime/prelude/_json.py:530`

   `_encode_float` invokes overridden comparisons to classify the underlying float. A finite value can consequently serialize as infinity.

   ```python
   import json
   class F(float):
       def __ne__(self, other):
           return True
   print(json.dumps(F(1.5)))
   ```

   CPython prints `1.5`; Bella prints `Infinity`.

2. **Dictionary mutation during encoding raises an extra exception** — `runtime/prelude/_json.py:650`

   The Python dictionary iterator detects size changes; CPython’s encoder traverses the dictionary with `PyDict_Next` and includes the newly inserted entry.

   ```python
   import json
   d = {'a': object()}
   def default(obj):
       d['b'] = 2
       return 1
   try:
       print(json.dumps(d, default=default))
   except Exception as e:
       print(type(e).__name__)
   ```

   CPython prints `{"a": 1, "b": 2}`; Bella prints `RuntimeError`.

3. **Tuple subclass iteration is ignored** — `runtime/prelude/_json.py:661`

   The encoder reads tuple storage directly for subclasses. CPython’s sequence conversion honors their iterator.

   ```python
   import json
   class T(tuple):
       def __iter__(self):
           return iter((9,))
   print(json.dumps(T((1, 2))))
   ```

   CPython prints `[9]`; Bella prints `[1, 2]`.

4. **Adding serialization notes invokes user overrides** — `runtime/prelude/_json.py:524`

   `_note` calls the exception’s `add_note` method. CPython’s internal note operation bypasses that override. This introduces user-visible calls and can lose notes or replace the original exception.

   ```python
   import json
   class Error(Exception):
       def add_note(self, note):
           print('override called')
   def bad(obj):
       raise Error('bad')
   try:
       json.dumps([object()], default=bad)
   except Error as e:
       print(getattr(e, '__notes__', []))
   ```

   CPython:
   ```text
   ['when serializing list item 0']
   ```

   Bella:
   ```text
   override called
   []
   ```

5. **Captured comprehension variables disappear from code metadata** — `pipeline/l2/resolve.py:376`, `pipeline/backend/cpp.py:277`

   The metadata merge excludes a comprehension’s cell variables from `co_varnames` and does not propagate them into the enclosing code’s `co_cellvars`.

   ```python
   def f():
       return [(lambda: i) for i in range(2)]
   print(f.__code__.co_varnames, f.__code__.co_cellvars)
   ```

   CPython prints `('i',) ('i',)`; Bella prints `() ()`.

6. **`co_flags` omits future flags and generic-function nesting** — `pipeline/backend/cpp.py:280`

   Flags are reconstructed without future-annotation state. Inferring `CO_NESTED` from `<locals>` in the qualified name also misses a generic function’s enclosing type-parameter scope.

   ```python
   from __future__ import annotations
   def f[T]():
       pass
   print(bool(f.__code__.co_flags & 0x1000000))
   print(bool(f.__code__.co_flags & 0x10))
   ```

   CPython:
   ```text
   True
   True
   ```

   Bella:
   ```text
   False
   False
   ```

7. **`function.__closure__` has unstable identity** — `runtime/src/types.cpp:1545`

   Every read constructs a new tuple, whereas CPython returns the function’s stored closure tuple.

   ```python
   def outer():
       x = 1
       def inner():
           return x
       return inner
   f = outer()
   print(f.__closure__ is f.__closure__)
   ```

   CPython prints `True`; Bella prints `False`.

8. **`scanstring` does not enforce the index’s C-sized range** — `runtime/prelude/_json.py:147`

   `_number_index` accepts arbitrarily large integers, which subsequently reach the string bounds check. CPython rejects overflow during argument conversion.

   ```python
   import _json
   try:
       _json.scanstring('"x"', 10**100)
   except Exception as e:
       print(type(e).__name__)
   ```

   CPython prints `OverflowError`; Bella prints `ValueError`.