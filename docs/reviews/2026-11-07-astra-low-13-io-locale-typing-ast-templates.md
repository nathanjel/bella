Codex astra-low (`gpt-6-astra`, effort low), 2026-11-07, asked by the author. Verbatim. Tag A13 in the review log. Its range is
`1dab41b..3ea072a` (eleven commits: the codec registry, `_io` and the standard streams, pwd, grp, `_locale`, zlib, `_ast`, the
t-string types, `_typing` and PEP 695's intrinsics, a staged `exec` with its own locals, the type offsets, the model's
failed-delete rule). It ran in a detached checkout at `3ea072a` with a shared, pre-built `build/`.

---

Found eight reproducible defects, ranked below. All reproductions used the pinned CPython and compiled checkout. No tracked files changed.

1. **`TextIOWrapper.tell()` produces a position that skips unread data** — `runtime/prelude/_io.py:2934`

   `skip_bytes` is not capped to the saved input’s length. After restoring a newline cookie, the position calculation can advance beyond the bytes actually decoded.

   ```python
   import _io
   t = _io.TextIOWrapper(_io.BytesIO(b'\rc\n'), encoding='utf-8')
   print(repr(t.read(1)))
   t.seek(t.tell())
   print(repr(t.read(1)))
   p = t.tell()
   print(repr(t.read()))
   t.seek(p)
   print(repr(t.read()))
   ```

   CPython:
   ```text
   '\n'
   'c'
   '\n'
   '\n'
   ```

   Bella:
   ```text
   '\n'
   'c'
   '\n'
   ''
   ```

2. **Replacement stdout without `closed` causes exit status 120 and never gets flushed** — `runtime/src/call.cpp:480`

   The unconditional `getattr("closed")` treats a missing optional attribute as a flush failure.

   ```python
   import sys

   class Output:
       def write(self, text: str) -> int:
           return sys.__stdout__.write(text)

       def flush(self) -> None:
           sys.__stdout__.write("flushed\n")

   sys.stdout = Output()
   print("hello")
   ```

   CPython stdout, exit **0**:
   ```text
   hello
   flushed
   flushed
   ```

   Bella stdout, exit **120**:
   ```text
   hello
   ```

   Bella stderr:
   ```text
   Exception ignored while flushing sys.stdout:
   AttributeError: 'Output' object has no attribute 'closed'
   ```

3. **Reinitializing `TextIOWrapper` retains the previous stream’s decoded data** — `runtime/prelude/_io.py:2667`

   Replacing the buffer does not clear decoded characters, snapshots, or pending writes. This can return data from the old stream or write old pending bytes into the new one.

   ```python
   import _io
   a = _io.BytesIO(b"abc")
   t = _io.TextIOWrapper(a, encoding="utf-8")
   print(t.read(1))
   b = _io.BytesIO(b"XYZ")
   t.__init__(b, encoding="utf-8")
   print(t.read(2))
   ```

   CPython:
   ```text
   a
   XY
   ```

   Bella:
   ```text
   a
   bc
   ```

   Separately reproduced the pending-write variant: CPython leaves the new buffer as `b'new'`; Bella writes `b'oldnew'`.

4. **Startup coerces the locale despite explicit `LC_ALL=C`** — `runtime/src/posix.cpp:354`

   The coercion path lacks the `LC_ALL` guard. This changes the actual C locale, independently of UTF-8 mode.

   Run both programs with `LC_ALL=C` and `PYTHONCOERCECLOCALE` unset:

   ```python
   import _locale
   print(_locale.setlocale(_locale.LC_CTYPE))
   ```

   CPython:
   ```text
   C
   ```

   Bella:
   ```text
   C.UTF-8
   ```

5. **A lazy `TypeVar` bound returning `None` is evaluated repeatedly** — `runtime/prelude/_typing.py:319`

   `None` represents both an unevaluated bound and a successfully cached result.

   ```python
   counter = 0

   def bound() -> object:
       global counter
       counter += 1
       return None

   def f[T: bound()]() -> None:
       pass

   t = f.__type_params__[0]
   print(t.__bound__, t.__bound__, counter)
   ```

   CPython:
   ```text
   None None 1
   ```

   Bella:
   ```text
   None None 2
   ```

6. **Template iteration drops nonempty string subclasses whose `__len__` returns zero** — `runtime/prelude/templatelib.py:196`

   The emptiness check invokes the subclass override instead of inspecting the underlying string length.

   ```python
   class S(str):
       def __len__(self) -> int:
           return 0

   Template = type(t"")
   print(list(Template(S("hello"))))
   ```

   CPython:
   ```text
   ['hello']
   ```

   Bella:
   ```text
   []
   ```

7. **AST repr detects recursion using equality instead of identity** — `runtime/prelude/_ast.py:79`

   Distinct nodes that compare equal are incorrectly abbreviated. This also invokes user comparison methods during recursion detection.

   ```python
   import _ast

   class Node(_ast.AST):
       _fields = ("child",)

       def __eq__(self, other: object) -> bool:
           return True

   print(Node(Node(None)))
   ```

   CPython:
   ```text
   Node(child=Node(child=None))
   ```

   Bella:
   ```text
   Node(child=Node(...))
   ```

8. **Text cookies use the wrong integer field layout** — `runtime/prelude/_io.py:2553`

   The implementation allocates 64 bits to every cookie field; the pinned implementation uses narrower integer fields after the position. This is separate from finding 1.

   ```python
   import _io
   t = _io.TextIOWrapper(_io.BytesIO(b'\rc'), encoding='utf-8')
   t.read(1)
   print(t.tell())
   ```

   CPython:
   ```text
   340282367000166625996085689099021713409
   ```

   Bella:
   ```text
   6277101735386680764176071790128604879584176795969512275969
   ```