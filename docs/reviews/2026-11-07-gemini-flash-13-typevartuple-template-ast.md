gemini-3.8-flash-high through `agy`, 2026-11-07, asked by the author. Verbatim, its progress lines included. Tag G13 in the
review log. Its range is `1dab41b..3ea072a`, the same as A13's; it ran in a detached checkout at `3ea072a` with a shared,
pre-built `build/`.

---

An in-depth review of Bella across the eleven commits in the range [`1dab41b..3ea072a`](file:///home/nathan/workspaces/nth/bella) was performed, focusing on the newly added prelude modules, runtime subsystems, frontend AST lowering, and staged execution.

All findings below are confirmed behavioral defects against CPython 3.15.2 verified on both the pinned CPython interpreter (`.venv/bin/python`) and Bella compiled binaries.

---

### Ranked List of Findings

#### 1. `TypeVarTuple` starred default value loses `typing.Unpack`
- **Location:** [`pipeline/l1/frontend.py:476-477`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L476-L477) and [`runtime/prelude/_typing.py:1053-1055`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/_typing.py#L1053-L1055)
- **Problem:**
  When lowering type parameter defaults in `pipeline/l1/frontend.py`:
  ```python
  text += " = " + ("*" if isinstance(tp, ast.TypeVarTuple) else "") + call(
      tp.default_value.value if isinstance(tp, ast.TypeVarTuple) and isinstance(tp.default_value, ast.Starred)
      else tp.default_value, tp.name)
  ```
  For a `TypeVarTuple` with a starred default expression such as `*tuple[int, str]`, `frontend.py` unwraps the `ast.Starred` AST node and passes only the inner `ast.Subscript` (`tuple[int, str]`) to `call()`. The generated thunk evaluates only `tuple[int, str]` without `typing.Unpack`. In `runtime/prelude/_typing.py`:
  ```python
  if default_text.startswith("*"):
      default_text = default_text[1:]
  default = thunks[_thunk_index(default_text)]
  ```
  `_typing.py` strips the leading `*` and assigns the unstarred thunk directly to `param._evaluate_default`. As a result, accessing `param.__default__` produces the raw `tuple[int, str]` rather than `*tuple[int, str]` (`typing.Unpack[tuple[int, str]]`).
- **Minimal Program:**
  ```python
  import typing

  class D[*Ts = *tuple[int, str]]:
      pass

  p = D.__type_params__[0]
  print(p.__default__)
  ```
- **CPython 3.15.2 output:**
  ```
  *tuple[int, str]
  ```
- **Bella compiled output:**
  ```
  tuple[int, str]
  ```

---

#### 2. `Template` missing `sequence_slots` suppresses reflected `__radd__`
- **Location:** [`runtime/prelude/templatelib.py:173-176`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/templatelib.py#L173-L176) and [`runtime/src/call.cpp:2357-2368`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp#L2357-L2368)
- **Problem:**
  In CPython, `string.templatelib.Template` is a sequence type whose concatenation operator `+` is implemented via sequence concatenation `sq_concat` (`_PyTemplate_Concat`), not numeric addition `nb_add`. Under `PyNumber_Add`, if the left operand does not define numeric addition (`nb_add`), the right operand's numeric addition (`__radd__`) is attempted first before falling back to sequence concatenation.
  In Bella, `Template` is defined in Python in `runtime/prelude/templatelib.py` with `def __add__(self, other): ...`. However, `Template` is not registered with `sequence_slots = true` in `runtime/src/call.cpp` (unlike `deque` in `runtime/src/imports.cpp:549`). Because `sequence_slot_of` returns `false`, `binary_op1` in `runtime/src/ops.cpp` treats `Template.__add__` as an `nb_add` number slot. When evaluating `t + Custom()`, Bella invokes `Template.__add__` directly, raising `TypeError: can only concatenate string.templatelib.Template ...` before `Custom.__radd__` is ever given a chance to run.
- **Minimal Program:**
  ```python
  import string.templatelib as st

  class Custom:
      def __radd__(self, other):
          return "custom"

  t = st.Template()
  print(t + Custom())
  ```
- **CPython 3.15.2 output:**
  ```
  custom
  ```
- **Bella compiled output:**
  ```
  Traceback (most recent call last):
    File "/tmp/test_template_radd.py", line 8, in <module>
  TypeError: can only concatenate string.templatelib.Template (not "Custom") to string.templatelib.Template
  ```

---

#### 3. `AST` depth-limited `__repr__` checks cycle detection by equality instead of identity
- **Location:** [`runtime/prelude/_ast.py:80-82`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/_ast.py#L80-L82)
- **Problem:**
  In `runtime/prelude/_ast.py`, `_repr_depth` tracks visited nodes using `_in_repr: list[object] = []` (described in the source comment as `Py_ReprEnter's stack, by identity`). However, it performs recursion detection using:
  ```python
  if self in _in_repr:
      return name + "(...)"
  ```
  In Python, `in` on a list tests object equality (`==`), not object identity (`is`). If an AST node subclass implements `__eq__`, distinct node instances in an AST tree that compare equal trigger false recursion detection, causing child nodes to be prematurely truncated as `Node(...)`. CPython's `Py_ReprEnter` tests object identity by pointer address.
- **Minimal Program:**
  ```python
  import _ast

  class Node(_ast.AST):
      _fields = ("child",)
      def __eq__(self, other):
          return isinstance(other, Node)

  a = Node.__new__(Node)
  b = Node.__new__(Node)
  b.child = None
  a.child = b
  print(repr(a))
  ```
- **CPython 3.15.2 output:**
  ```
  Node(child=Node(child=None))
  ```
- **Bella compiled output:**
  ```
  Node(child=Node(...))
  ```

---

### Components Exercised & Verified

Across the 11 commits in range `1dab41b..3ea072a`, the following behaviors were analyzed, exercised, and verified against CPython 3.15.2:

1. **`faf26bc` (Codec Registry):**
   - Registry lookups, normalization, cache, and error handler callbacks in [`runtime/prelude/_codecs.py`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/_codecs.py).
   - Fast paths for UTF-8, ASCII, and Latin-1 in [`runtime/src/bytes.cpp`](file:///home/nathan/workspaces/nth/bella/runtime/src/bytes.cpp).
   - Stateful UTF-8 decoding (`decode_utf8`, `utf8_step`) with truncated surrogate sequences and incomplete byte boundaries.
   - Zero-length input bypass in `b"".decode()`.

2. **`54638e9` & `d52b26e` (`_io` and Standard Streams):**
   - `FileIO`, `BufferedReader`, `BufferedWriter`, and `BufferedRandom` state transitions.
   - `StringIO` and `BytesIO` edge cases: seeking beyond end, negative seek offsets, non-zero whence errors, and truncate operations.
   - `TextIOWrapper` cookie pack/unpack, tell/seek correctness across pending read buffers and multi-byte decodes.
   - `IncrementalNewlineDecoder` state serialization with 64-bit flag bitmasks.
   - `create_stdio` start-up behavior in [`runtime/src/call.cpp`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp), `PYTHONIOENCODING` override parsing, and flush failures exiting with status 120.

3. **`27c3687` (`pwd`, `grp`, `_locale`, `zlib`, `_ast`, `templatelib`):**
   - `pwd` and `grp` argument converters (`_Py_Uid_Converter`, `_Py_Gid_Converter` handling `-1` and 64-bit bounds).
   - `_locale` wide-character conversions (`strcoll`, `strxfrm` with `nullptr` length queries), `localeconv` structures, and PEP 538 start-up locale coercion.
   - `zlib` constants, `error` hierarchy, and named refusal behaviors.
   - `_ast` node generation, `AST.__init__`, `__reduce__`, `__replace__`, and field dictionary initializations.
   - `Template` and `Interpolation` construction, string splitting, and iterator mechanics.

4. **`68e8bf2` (`_typing` and PEP 695 Intrinsics):**
   - Intrinsics `type_params`, `generic_class`, `typealias`, and `set_type_params`.
   - Lazy bounds, constraints, and default evaluations for `TypeVar`, `ParamSpec`, and `TypeVarTuple`.
   - Variance validation and `NoDefault` singleton behaviors.

5. **`02159e6` (Staging, Offsets, Sentinels):**
   - Staged `exec` text execution with distinct `globals` and `locals` dicts.
   - `type.__dictoffset__` and `__weakrefoffset__` computations across empty slots, dict slots, managed dicts, and base class inheritances.
   - `sentinel` hash and rich comparison slot implementations.

6. **`26ea234` & `980d8a8` (Refmodel and Previous Fixes):**
   - Detached dict attribute deletion order in [`refmodel/objects.py`](file:///home/nathan/workspaces/nth/bella/refmodel/objects.py) and [`runtime/include/bella/object.hpp`](file:///home/nathan/workspaces/nth/bella/runtime/include/bella/object.hpp).
   - Verified regressions against prior review fixes (RL-334 through RL-346).
