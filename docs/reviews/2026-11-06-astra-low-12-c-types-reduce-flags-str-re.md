Codex astra-low (`gpt-6-astra`, effort low), 2026-11-06, asked by the author. Verbatim. Tag A12 in the review log. Its range is
five commits of `d46c55b..1dab41b`: `38df31f`, `cbc3477`, `e348de1`, `10254b5`, `a6309a4`. A first run on the whole range was
stopped by the provider's filter ("flagged for possible cybersecurity risk") before it reported anything, so the author chose
one narrower retry, which left out `posix`, `os`, exceptions, `sys` and the earlier commits. No Codex review covers those.

---

Found five reproducible defects, ranked below. All reproductions used the pinned CPython and compiled Bella programs; none are registered deviations or stops by name. Tracked files remain unchanged.

1. **[P2] Regex scanners do not retain the input’s buffer export** — `runtime/prelude/_sre.py:635` (`a6309a4`).

   Keeping only the bytearray reference permits resizing while the scanner retains its original bounds. CPython prevents this with `BufferError`.

   ```python
   import re
   b = bytearray(b'a')
   s = re.compile(b'a').scanner(b)
   try:
       b.append(98)
       print('resized')
   except BufferError:
       print('BufferError')
   ```

   CPython prints `BufferError`; Bella prints `resized`.

2. **[P2] Full string slices evaluate the step twice** — `runtime/src/ops.cpp:1360` (`10254b5`).

   After `each_index` converts the step, `slice_is_forward` invokes `__index__` again. This duplicates observable side effects and can raise an exception after an otherwise successful slice.

   ```python
   class Step:
       def __index__(self):
           print('index')
           return 1

   print('abc'[::Step()])
   ```

   CPython:
   ```text
   index
   abc
   ```

   Bella:
   ```text
   index
   index
   abc
   ```

3. **[P2] `__reduce_ex__` uses an overridden tuple length** — `runtime/prelude/bootstrap.py:1825` (`cbc3477`).

   CPython checks the underlying tuple size of `__getnewargs_ex__`’s result. Bella calls its overridable `__len__`, rejecting valid reconstruction arguments.

   ```python
   import copyreg

   class T(tuple):
       def __len__(self):
           return 0

   class C:
       def __getnewargs_ex__(self):
           return T(((), {}))

   try:
       C().__reduce_ex__(2)
       print('ok')
   except Exception as e:
       print(type(e).__name__)
   ```

   CPython prints `ok`; Bella prints `ValueError`.

4. **[P2] Callable iterators miss the sentinel identity check** — `runtime/prelude/iterating.py:57` (`a6309a4`).

   CPython stops when the returned object *is* the sentinel, even when it does not equal itself. Bella tests equality alone, so consuming this iterator until exhaustion would never finish.

   ```python
   x = float('nan')
   it = iter(lambda: x, x)
   print(next(it, 'stopped'))
   ```

   CPython prints `stopped`; Bella prints `nan`.

5. **[P2] Distinct method wrappers compare equal** — `runtime/src/ops.cpp:592` (`cbc3477`, affecting wrappers introduced by `38df31f`).

   Equality compares the implementation function and receiver without distinguishing the wrapped descriptors. `__mul__` and `__rmul__` share Bella’s implementation but are distinct wrappers in CPython.

   ```python
   s = 'abc'
   print(s.__mul__ == s.__rmul__)
   ```

   CPython prints `False`; Bella prints `True`.

Also exercised type flags before and after instance mutation and for a slotted string subclass; those matched. Regex captures, lookbehind, empty matches, and Unicode word categories matched until a permitted stop by name. The exhaustive Unicode-table check passed against CPython 3.15.2.