# Bella C++ Emitter Review (`d28b256..f12af86`, L2 to C++26 Emitter, Runtime Core & Classes Compiled)

- **Date:** 2026-11-02
- **Reviewer:** `gemini-4-argon-high`
- **Sequence:** 08
- **Commit Range Reviewed:** `d28b256..f12af86` (`d28b25606840edeed5ccdcae4d1207b3c2773634..f12af861c6c6c62853811a97c775ac9fb273441b`)
- **Reviewed HEAD:** `f12af861c6c6c62853811a97c775ac9fb273441b`

---

## 1. Executive Summary

This review covers the 5 commits in range `d28b256..f12af86` on `main`, delivering:
1. Resolution of prior reviews `RL-169` to `RL-187` ([`749e1b5`](file:///home/nathan/workspaces/nth/bella/docs/reviews/review-log.md));
2. Test harness parallelisation via `pytest-xdist` ([`e0ac36b`](file:///home/nathan/workspaces/nth/bella/Makefile));
3. Gate 0 Task 3 Step 3a.1: The C++26 emitter from L2 ([`pipeline/backend/cpp.py`](file:///home/nathan/workspaces/nth/bella/pipeline/backend/cpp.py)), compiler driver ([`pipeline/build.py`](file:///home/nathan/workspaces/nth/bella/pipeline/build.py)), and runtime core ([`runtime/include/bella/runtime.hpp`](file:///home/nathan/workspaces/nth/bella/runtime/include/bella/runtime.hpp), [`runtime/src/call.cpp`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp), [`runtime/src/core.cpp`](file:///home/nathan/workspaces/nth/bella/runtime/src/core.cpp), [`runtime/src/ops.cpp`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp), [`runtime/src/set.cpp`](file:///home/nathan/workspaces/nth/bella/runtime/src/set.cpp));
4. Gate 0 Task 3 Step 3a.2: Compiling classes, class bodies, and descriptor binding ([`2c9a06a`](file:///home/nathan/workspaces/nth/bella/runtime/src/types.cpp), cases C-3-05..11);
5. Instance `__dict__` method refusal stub ([`f12af86`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp)).

### 1.1 Verification Status

The baseline test suite passes completely across all layers:
- `uv run make check` passed in 3m10s across 16 workers:
  - pytest: 334 passed (including new review regression suites [`pipeline/tests/test_review_2026_11_02b.py`](file:///home/nathan/workspaces/nth/bella/pipeline/tests/test_review_2026_11_02b.py), [`pipeline/tests/test_compiled.py`](file:///home/nathan/workspaces/nth/bella/pipeline/tests/test_compiled.py), and [`runtime/tests/test_prelude.py`](file:///home/nathan/workspaces/nth/bella/runtime/tests/test_prelude.py)).
  - stdlib closure tool: 176 modules locked and verified byte-for-byte.
  - Conformance harness: 141/141 verified expectations.
  - Evaluation runners: `eval1-corpus` 60/76, `eval2-corpus` 63/76, `compiled-corpus` 15/76 (baseline established for Step 3a.1).
  - Target suites: `targets-eval1` and `targets-eval2` passed all 3 closure targets (`cli_easy_slugs`, `service_easy_tokens`, `data_easy_sales`).
  - Native runtime suites: `object-test` passed 3000 operations (plus 1020 operations under ASan and UBSan); `float-diff` passed 800k+ conversions without deviation; `make slice` passed 5/5 programs.
  - Static typing & linting: `mypy --strict` and `ruff check` passed across all 87 pipeline files.

---

### 1.2 Summary of Findings

Following the project principle—*settling what CPython does strictly by executing pinned CPython 3.15.2, treating every claim as something to break*—we identified **13 concrete semantic divergences, compiler bugs, and runtime crashes** in the new C++ leg:

| Finding ID | Severity | Subsystem | Summary |
|---|---|---|---|
| **RL-188** | Critical | Compiler / Emitter | Inlined `finally` inside `return` causes double execution of `finally` blocks upon exception |
| **RL-189** | Critical | Runtime / Core | Missing receiver type check in `list_self` and `list_append` causes SIGSEGV on unbound methods |
| **RL-190** | Critical | Runtime / Set | `set.discard()` and `set.remove()` read out-of-bounds `a.pos(0)` without arity check causing SIGSEGV |
| **RL-191** | Critical | Runtime / Object | Duplicate base classes throw unhandled `bella::TypeError` instead of `PyError`, aborting with SIGABRT |
| **RL-192** | High | Runtime / Ops | Mutating a list during sequence comparison causes buffer overrun and SIGSEGV |
| **RL-193** | High | Runtime / Ops | Sequence rich comparison coerces element comparison return values to `bool` |
| **RL-194** | High | Runtime / Ops | `bool(NotImplemented)` returns `True` instead of raising `TypeError` |
| **RL-195** | High | Compiler / Runtime | Bare `raise` in `finally` without preceding exception handler raises `RuntimeError` instead of propagating in-flight exception |
| **RL-196** | High | Runtime / Set | Set mutation during iteration is silently accepted instead of raising `RuntimeError` |
| **RL-197** | Medium | Compiler / Emitter | Emitter loop flag names (`ended1`, `raised1`) collide with user Python identifiers, breaking C++ compilation |
| **RL-198** | Medium | Runtime / Ops | Custom `__len__` returning `bool` raises `TypeError` during boolean evaluation |
| **RL-199** | Medium | Runtime / Prelude | `classmethod` bound to custom callable without `__get__` raises `AttributeError` |
| **RL-200** | Medium | Compiler / Runtime | Function docstrings (`__doc__`) are omitted on compiled function objects |

---

## 2. Technical Findings & Reproductions Against CPython 3.15.2

### 2.1 RL-188 [Critical / Compiler Bug] Inlined `finally` Inside `return` Causes Double Execution of `finally` Blocks upon Exception

- **Locations:** [`pipeline/backend/cpp.py:347-354`](file:///home/nathan/workspaces/nth/bella/pipeline/backend/cpp.py#L347-L354) (`case G.Return`), [`pipeline/backend/cpp.py:388-402`](file:///home/nathan/workspaces/nth/bella/pipeline/backend/cpp.py#L388-L402) (`try_`).
- **Problem:** When a `return` statement occurs inside a `try` block protected by a `finally` clause, [`pipeline/backend/cpp.py`](file:///home/nathan/workspaces/nth/bella/pipeline/backend/cpp.py) inlines the `finally` body immediately before returning (`self.finally_inline(ex, indent + 1)`). Crucially, this inlined execution takes place *inside* the generated C++ `try { ... }` block:
  ```cpp
  try {
      {
          Ref ret = Ref::share(Obj::small(1));
          {
              // Inlined s.finalbody inside the C++ try block!
              t1 = rt::load_global(M, S_print);
              rt::invoke(t1.get(), {K_finally});
              rt::raise_type(t4.get(), Obj{}, false);
          }
          return ret;
      }
  } catch (...) {
      {
          // Outer catch catches the exception raised by finalbody and runs finalbody AGAIN!
          t1 = rt::load_global(M, S_print);
          rt::invoke(t1.get(), {K_finally});
          rt::raise_type(t4.get(), Obj{}, false);
      }
      throw;
  }
  ```
  If any statement in the inlined `finally` block raises an exception (or calls a function that raises), control transfers to the enclosing `} catch (...) {` of that *same* `try` block, which unconditionally executes `s.finalbody` a second time!
- **Minimal Reproduction (`test_finally.py`):**
  ```python
  def f():
      try:
          return 1
      finally:
          print("finally")
          raise ValueError("boom")

  try:
      f()
  except ValueError:
      print("caught")
  ```
- **Execution & Output:**
  ```sh
  uv run python test_finally.py
  # CPython 3.15.2 output:
  # finally
  # caught

  uv run python pipeline/build.py --run test_finally.py
  # Bella compiled output:
  # finally
  # finally
  # caught
  ```
- **Suggested Fix:**
  In [`pipeline/backend/cpp.py`](file:///home/nathan/workspaces/nth/bella/pipeline/backend/cpp.py), a return leaving a `try/finally` block must not run the `finally` code inside the C++ `try` scope. Instead, set a flag or transfer control out of the C++ `try` block before executing the `finally` sequence, or pop the active `finally` exit from the enclosing exception-handler stack while inlining its body so that exceptions within the `finally` block propagate directly to outer handlers.

---

### 2.2 RL-189 [Critical / Crash] Missing Receiver Type Check in `list_self` Causes SIGSEGV on Unbound Method Calls

- **Locations:** [`runtime/src/call.cpp:482`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp#L482) (`list_self`), [`runtime/src/ops.cpp:913-915`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L913-L915) (`list_append`).
- **Problem:** [`runtime/src/call.cpp:482`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp#L482) defines:
  ```cpp
  List* list_self(Obj self) { return static_cast<List*>(self.object()); }
  ```
  and [`runtime/src/ops.cpp:915`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L915) executes:
  ```cpp
  void list_append(Obj list, Obj value) {
      incref(value);
      static_cast<List*>(list.object())->items.push_back(value);
  }
  ```
  Neither helper verifies that `self` is a heap object or that `is_kind(self, Kind::List)`. When an unbound method descriptor is invoked with an invalid receiver—e.g. `list.append(1, 2)` where `1` is an immediate small integer `Obj::small(1)` (`bits = 0x3`)—`self.object()` returns an invalid non-pointer address (`0x3`). Dereferencing `->items` causes an immediate segmentation fault (`SIGSEGV`, exit code 139).
- **Minimal Reproduction (`test_list_append.py`):**
  ```python
  try:
      list.append(1, 2)
  except TypeError:
      print("TypeError")
  ```
- **Execution & Output:**
  ```sh
  uv run python test_list_append.py
  # CPython 3.15.2 output:
  # TypeError

  uv run python pipeline/build.py --run test_list_append.py
  # Bella compiled output:
  # [process terminated by SIGSEGV, return code 139]
  ```
- **Suggested Fix:**
  Add receiver validation in `list_self`:
  ```cpp
  List* list_self(Obj self) {
      if (!is_kind(self, Kind::List))
          raise_new("TypeError", "descriptor for 'list' objects doesn't apply to a '" + type_of(self)->name + "' object");
      return static_cast<List*>(self.object());
  }
  ```
  Apply corresponding checks across `dict_self` and `set_self`.

---

### 2.3 RL-190 [Critical / Crash] `set.discard()` and `set.remove()` Read Out-of-Bounds `a.pos(0)` Without Arity Check Causing SIGSEGV

- **Locations:** [`runtime/src/set.cpp:184-195`](file:///home/nathan/workspaces/nth/bella/runtime/src/set.cpp#L184-L195) (`set_discard_m`, `set_remove_m`), [`runtime/include/bella/runtime.hpp:41`](file:///home/nathan/workspaces/nth/bella/runtime/include/bella/runtime.hpp#L41) (`Args::pos`).
- **Problem:** Unlike `set_add_m` which validates `if (a.npos != 1) raise_new("TypeError", ...)`, `set_discard_m` and `set_remove_m` only call `no_kw(a, "discard")` and immediately dereference `a.pos(0)`. In [`runtime/include/bella/runtime.hpp:41`](file:///home/nathan/workspaces/nth/bella/runtime/include/bella/runtime.hpp#L41), `Args::pos(i)` does no bounds checking:
  ```cpp
  Obj pos(std::size_t i) const { return data[i]; }
  ```
  When `s.discard()` or `s.remove()` is called with zero arguments, `a.npos == 0`, and `a.pos(0)` performs an out-of-bounds read into stack memory or dereferences a null pointer, causing SIGSEGV.
- **Minimal Reproduction (`test_set_discard.py`):**
  ```python
  s = set()
  try:
      s.discard()
  except TypeError:
      print("TypeError")
  ```
- **Execution & Output:**
  ```sh
  uv run python test_set_discard.py
  # CPython 3.15.2 output:
  # TypeError

  uv run python pipeline/build.py --run test_set_discard.py
  # Bella compiled output:
  # [process terminated by SIGSEGV, return code 139]
  ```
- **Suggested Fix:**
  Add positional arity enforcement in `set_discard_m` and `set_remove_m`:
  ```cpp
  Ref set_discard_m(Obj self, Args a) {
      positional_only(a, "discard", 1, 1);
      set_discard(set_self(self), a.pos(0));
      return none_ref();
  }
  ```

---

### 2.4 RL-191 [Critical / Crash] Duplicate Base Classes Throw Unhandled `bella::TypeError` Aborting with SIGABRT

- **Locations:** [`runtime/include/bella/object.hpp:47`](file:///home/nathan/workspaces/nth/bella/runtime/include/bella/object.hpp#L47), [`runtime/include/bella/object.hpp:425`](file:///home/nathan/workspaces/nth/bella/runtime/include/bella/object.hpp#L425) (`c3`).
- **Problem:** In [`runtime/include/bella/object.hpp:47`](file:///home/nathan/workspaces/nth/bella/runtime/include/bella/object.hpp#L47), `bella::TypeError` is defined as:
  ```cpp
  struct TypeError : std::runtime_error { using std::runtime_error::runtime_error; };
  ```
  When class creation encounters duplicate base classes or an inconsistent MRO, `c3()` throws `bella::TypeError("inconsistent MRO")`. However, `bella::TypeError` does NOT inherit from `bella::PyError` (the exception type caught by compiled Python code and runtime guards). As a result, the exception escapes uncaught through `main()`, causing `std::terminate()` and aborting the process (`SIGABRT`, exit code 134).
- **Minimal Reproduction (`test_mro.py`):**
  ```python
  class A:
      pass

  try:
      class B(A, A):
          pass
      print("created")
  except TypeError:
      print("TypeError")
  ```
- **Execution & Output:**
  ```sh
  uv run python test_mro.py
  # CPython 3.15.2 output:
  # TypeError

  uv run python pipeline/build.py --run test_mro.py
  # Bella compiled output:
  # terminate called after throwing an instance of 'bella::TypeError'
  #   what():  inconsistent MRO
  # [process terminated by SIGABRT, return code 134]
  ```
- **Suggested Fix:**
  Catch `bella::TypeError` at the runtime boundary in [`runtime/src/types.cpp`](file:///home/nathan/workspaces/nth/bella/runtime/src/types.cpp) where `make_class` is called and re-raise as a Python `PyError` via `raise_new("TypeError", e.what())`. Alternatively, make `make_class` take an error-reporting channel or unify exception hierarchies.

---

### 2.5 RL-192 [High / Memory Corruption] Mutating List During Sequence Comparison Causes Buffer Overrun and SIGSEGV

- **Locations:** [`runtime/src/ops.cpp:286-295`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L286-L295) (`sequence_compare`), [`runtime/src/ops.cpp:309`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L309) (`native_compare`).
- **Problem:** [`runtime/src/ops.cpp:286`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L286) executes:
  ```cpp
  bool sequence_compare(CmpOp op, const std::vector<Obj>& a, const std::vector<Obj>& b) {
      std::size_t n = std::min(a.size(), b.size());
      std::size_t i = 0;
      for (; i < n; ++i)
          if (!(a[i] == b[i] || truth(compare(CmpOp::Eq, a[i], b[i]).get()))) break;
      if (i >= n) return ordered(op, a.size(), b.size());
      ...
      return truth(compare(op, a[i], b[i]).get());
  }
  ```
  `a` and `b` are references directly bound to `list->items`. During element comparison, a custom `__eq__` method can execute arbitrary Python code that modifies `a` or `b` (e.g. `a.clear()`). Because `n` was cached as the pre-loop minimum size, subsequent iterations read beyond `a.data() + a.size()`, and line 294 reads out-of-bounds elements, leading to memory corruption and SIGSEGV.
- **Minimal Reproduction (`test_list_mutate.py`):**
  ```python
  a = []
  b = []

  class C:
      def __eq__(self, o):
          a.clear()
          b.clear()
          return False
      def __lt__(self, o):
          return True

  a.extend([C(), 1])
  b.extend([C(), 2])
  print(a < b)
  ```
- **Execution & Output:**
  ```sh
  uv run python test_list_mutate.py
  # CPython 3.15.2 output:
  # False

  uv run python pipeline/build.py --run test_list_mutate.py
  # Bella compiled output:
  # [process terminated by SIGSEGV, return code 139]
  ```
- **Suggested Fix:**
  Follow CPython's list comparison design (`listobject.c:list_richcompare`): inspect the current sizes of both lists on *every* iteration step and safely terminate or adjust indices if mutation occurs.

---

### 2.6 RL-193 [High / Spec Violation] Sequence Rich Comparison Coerces Element Comparison Return Values to `bool`

- **Locations:** [`runtime/src/ops.cpp:294`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L294) (`sequence_compare`), [`runtime/src/ops.cpp:307-309`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L307-L309) (`native_compare`).
- **Problem:** In Python, comparing two lists or tuples (`a < b`, `a > b`, etc.) evaluates element-wise rich comparisons. When a differing element's comparison method returns a non-boolean value (e.g. integer `42`), CPython returns that exact value directly. In Bella, [`sequence_compare`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L286) returns a C++ `bool` coerced via `truth()`, and [`native_compare`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L299) wraps it with `boolean(...)`. As a result, Bella returns `True` instead of the underlying object.
- **Minimal Reproduction (`test_rich_cmp.py`):**
  ```python
  class C:
      def __eq__(self, o): return False
      def __lt__(self, o): return 42

  print([C()] < [C()])
  print((C(),) < (C(),))
  ```
- **Execution & Output:**
  ```sh
  uv run python test_rich_cmp.py
  # CPython 3.15.2 output:
  # 42
  # 42

  uv run python pipeline/build.py --run test_rich_cmp.py
  # Bella compiled output:
  # True
  # True
  ```
- **Suggested Fix:**
  Change `sequence_compare` to return `Ref` rather than `bool`. For differing elements on inequality operators, return `compare(op, elem_a, elem_b)` directly without coercing via `truth()`.

---

### 2.7 RL-194 [High / Spec Violation] `bool(NotImplemented)` Returns `True` Instead of Raising `TypeError`

- **Locations:** [`runtime/src/ops.cpp:376`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L376) (`truth`).
- **Problem:** [`runtime/src/ops.cpp:376`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L376) handles singletons in boolean evaluation as:
  ```cpp
  case Kind::Singleton: return o != NONE;
  ```
  `NOT_IMPLEMENTED` is a `Singleton` object distinct from `NONE`, so `truth(NOT_IMPLEMENTED)` evaluates to `true`. In Python 3.9+ (and CPython 3.15.2), using `NotImplemented` in a boolean context is forbidden and raises `TypeError: NotImplemented should not be used in a boolean context`.
- **Minimal Reproduction (`test_notimpl.py`):**
  ```python
  try:
      print(bool(NotImplemented))
  except TypeError:
      print("TypeError")
  ```
- **Execution & Output:**
  ```sh
  uv run python test_notimpl.py
  # CPython 3.15.2 output:
  # TypeError

  uv run python pipeline/build.py --run test_notimpl.py
  # Bella compiled output:
  # True
  ```
- **Suggested Fix:**
  In [`runtime/src/ops.cpp:376`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L376):
  ```cpp
  case Kind::Singleton:
      if (o == NOTIMPLEMENTED)
          raise_new("TypeError", "NotImplemented should not be used in a boolean context");
      return o != NONE;
  ```

---

### 2.8 RL-195 [High / Spec Violation] Bare `raise` in `finally` Raises `RuntimeError` Instead of Propagating In-Flight Exception

- **Locations:** [`pipeline/backend/cpp.py:356-357`](file:///home/nathan/workspaces/nth/bella/pipeline/backend/cpp.py#L356-L357), [`runtime/src/core.cpp:554-555`](file:///home/nathan/workspaces/nth/bella/runtime/src/core.cpp#L554-L555) (`reraise`).
- **Problem:** When a `finally` block contains a bare `raise`, Bella emits `rt::reraise()`. In [`runtime/src/core.cpp:554`](file:///home/nathan/workspaces/nth/bella/runtime/src/core.cpp#L554), `reraise()` checks `if (handled().empty()) raise_new("RuntimeError", "No active exception to reraise")`. However, in Bella's emitter, `handled()` is only populated inside `except` blocks (via `rt::Handling handling(e.exc)`). In a `try ... finally` block, the exception caught by `catch (...)` is not pushed to `handled()`. Consequently, executing a bare `raise` in a `finally` block raises `RuntimeError` instead of re-raising the active in-flight exception.
- **Minimal Reproduction (`test_bare_raise.py`):**
  ```python
  try:
      try:
          raise ValueError("original")
      finally:
          raise
  except BaseException as e:
      print(type(e).__name__)
  ```
- **Execution & Output:**
  ```sh
  uv run python test_bare_raise.py
  # CPython 3.15.2 output:
  # ValueError

  uv run python pipeline/build.py --run test_bare_raise.py
  # Bella compiled output:
  # RuntimeError
  ```
- **Suggested Fix:**
  In [`pipeline/backend/cpp.py:392`](file:///home/nathan/workspaces/nth/bella/pipeline/backend/cpp.py#L392), catch `const rt::PyError& e` instead of `...`, and wrap the execution of `s.finalbody` with `rt::Handling handling(e.exc)` so that `reraise()` accesses the active exception.

---

### 2.9 RL-196 [High / Spec Violation] Set Mutation During Iteration Is Silently Accepted

- **Locations:** [`runtime/src/ops.cpp:790-796`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L790-L796) (`Iterator::SetIt`).
- **Problem:** In [`runtime/src/ops.cpp:790`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L790), the comment notes `// table order; a change of size during iteration fails`, and line 792 checks:
  ```cpp
  if (it->pos < 0) raise_new("RuntimeError", "Set changed size during iteration");
  ```
  However, `it->pos` is never set to a negative number anywhere in the runtime, `Iterator` does not record the set's size or version upon creation, and neither `set_add` nor `set_discard` increments a version counter. Mutating a set while iterating over it proceeds silently, iterating over newly added elements or skipping entries.
- **Minimal Reproduction (`test_set_mutate.py`):**
  ```python
  s = {1, 2}
  try:
      for x in s:
          s.add(4)
          print("iterated", x)
  except RuntimeError:
      print("RuntimeError")
  ```
- **Execution & Output:**
  ```sh
  uv run python test_set_mutate.py
  # CPython 3.15.2 output:
  # iterated 1
  # RuntimeError

  uv run python pipeline/build.py --run test_set_mutate.py
  # Bella compiled output:
  # iterated 1
  # iterated 2
  # iterated 4
  ```
- **Suggested Fix:**
  Store the initial set size `initial_size = st->used` in `Iterator` upon instantiation. At each step in `Iterator::SetIt`, verify `if (st->used != it->initial_size) raise_new("RuntimeError", "Set changed size during iteration")`.

---

### 2.10 RL-197 [Medium / Compilation Error] Emitter Identifier Collisions (`ended1`, `raised1`) Cause C++ Compiler Errors

- **Locations:** [`pipeline/backend/cpp.py:36`](file:///home/nathan/workspaces/nth/bella/pipeline/backend/cpp.py#L36) (`_EMITTER_NAME`), [`pipeline/backend/cpp.py:317`](file:///home/nathan/workspaces/nth/bella/pipeline/backend/cpp.py#L317) (`ended`), [`pipeline/backend/cpp.py:412`](file:///home/nathan/workspaces/nth/bella/pipeline/backend/cpp.py#L412) (`raised`).
- **Problem:** The emitter generates local C++ variables like `bool ended1 = false;` (for loop `else:` blocks) and `bool raised1 = false;` (for try `else:` blocks). However, `_EMITTER_NAME` in [`pipeline/backend/cpp.py:36`](file:///home/nathan/workspaces/nth/bella/pipeline/backend/cpp.py#L36) only checks `r"^(t\d+|K_\d+|S_\w*|code_\w*|f_\w*|py_\w*|c_\w*|e\d+)$"`. If a Python function uses a variable named `ended1` or `raised1`, `cpp_name` leaves the identifier unescaped. The emitter emits both `Ref ended1;` (for the Python local) and `bool ended1 = false;` (for the loop flag) in the same C++ scope, causing a hard compilation failure (`conflicting declaration 'bool ended1'`).
- **Minimal Reproduction (`test_ended.py`):**
  ```python
  def f():
      ended1 = 10
      for x in []:
          pass
      else:
          print("else", ended1)

  f()
  ```
- **Execution & Output:**
  ```sh
  uv run python test_ended.py
  # CPython 3.15.2 output:
  # else 10

  uv run python pipeline/build.py --run test_ended.py
  # Bella compiled output:
  # error: conflicting declaration ‘bool ended1’
  #    54 |     bool ended1 = false;
  # note: previous declaration as ‘bella::Ref ended1’
  #    43 |     Ref ended1;
  # error: could not convert ‘ended1’ from ‘bella::Ref’ to ‘bool’
  ```
- **Suggested Fix:**
  Prefix internal emitter control flags with a reserved identifier prefix that cannot collide with user variables, e.g. `_l2_ended` and `_l2_raised`, or expand `_EMITTER_NAME` to include `r"^(ended\d+|raised\d+|handling\d+|match\d+)$"`.

---

### 2.11 RL-198 [Medium / Spec Violation] Custom `__len__` Returning `bool` Raises `TypeError` in Boolean Evaluation

- **Locations:** [`runtime/src/ops.cpp:394`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L394) (`truth`).
- **Problem:** When an object defines `__len__` but not `__bool__`, boolean coercion evaluates `__len__`. In [`runtime/src/ops.cpp:394`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L394):
  ```cpp
  r = call_special(v, "__len__", {}, &has);
  if (has) {
      if (!r.get().is_small())
          raise_new("TypeError", "'" + type_of(r.get())->name + "' object cannot be interpreted as an integer");
      if (r.get().small_value() < 0) raise_new("ValueError", "__len__() should return >= 0");
      return r.get().small_value() != 0;
  }
  ```
  In Python, `bool` is a subclass of `int`, and `bool` values (or any object defining `__index__`) are valid return values for `__len__()`. In Bella, `True` and `False` are heap `BoolObject`s, for which `is_small()` returns `false`. Bella raises `TypeError: 'bool' object cannot be interpreted as an integer`.
- **Minimal Reproduction (`test_len_bool.py`):**
  ```python
  class C:
      def __len__(self):
          return True

  print(bool(C()))
  ```
- **Execution & Output:**
  ```sh
  uv run python test_len_bool.py
  # CPython 3.15.2 output:
  # True

  uv run python pipeline/build.py --run test_len_bool.py
  # Bella compiled output:
  # TypeError: 'bool' object cannot be interpreted as an integer
  ```
- **Suggested Fix:**
  Accept `Kind::Bool` alongside `is_small()` in `truth()`, extracting 1 for `True` and 0 for `False`.

---

### 2.12 RL-199 [Medium / Spec Violation] `classmethod` Bound to Custom Callable Without `__get__` Raises `AttributeError`

- **Locations:** [`runtime/prelude/builtins.py:138-141`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/builtins.py#L138-L141) (`classmethod.__get__`).
- **Problem:** In [`runtime/prelude/builtins.py:138`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/builtins.py#L138):
  ```python
  def __get__(self, obj: object, owner: object = None) -> object:
      if owner is None:
          owner = type(obj)
      return self.__func__.__get__(owner, type(owner))
  ```
  This unconditionally assumes `self.__func__` implements `__get__`. If `self.__func__` is a custom callable class without a descriptor `__get__` method, Python's `classmethod` binds it directly to `owner` as a method (`MethodType(func, owner)`). Bella instead raises `AttributeError: 'Callable' object has no attribute '__get__'`.
- **Minimal Reproduction (`test_classmethod.py`):**
  ```python
  class Callable:
      def __call__(self, cls, *args):
          return (cls, args)

  class A:
      cm = classmethod(Callable())

  print(A.cm(1, 2))
  ```
- **Execution & Output:**
  ```sh
  uv run python test_classmethod.py
  # CPython 3.15.2 output:
  # (<class '__main__.A'>, (1, 2))

  uv run python pipeline/build.py --run test_classmethod.py
  # Bella compiled output:
  # AttributeError: 'Callable' object has no attribute '__get__'
  ```
- **Suggested Fix:**
  In [`runtime/prelude/builtins.py:138`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/builtins.py#L138), check if `hasattr(type(self.__func__), "__get__")`: if present, invoke `__get__`; otherwise, return a bound `MethodType(self.__func__, owner)`.

---

### 2.13 RL-200 [Medium / Metadata Loss] Function Docstrings Are Not Preserved on Compiled Function Objects

- **Locations:** [`pipeline/backend/cpp.py:202-204`](file:///home/nathan/workspaces/nth/bella/pipeline/backend/cpp.py#L202-L204), [`runtime/src/call.cpp:146`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp#L146) (`make_function`).
- **Problem:** In [`runtime/src/call.cpp:146`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp#L146), `make_function` initializes `f->doc = none_ref()`. The emitter in [`pipeline/backend/cpp.py`](file:///home/nathan/workspaces/nth/bella/pipeline/backend/cpp.py) does not pass docstrings to `Code` or `make_function`, so `f.__doc__` is always `None` for compiled functions.
- **Minimal Reproduction (`test_doc.py`):**
  ```python
  def foo():
      """my docstring"""
      pass

  print("Doc:", foo.__doc__)
  ```
- **Execution & Output:**
  ```sh
  uv run python test_doc.py
  # CPython 3.15.2 output:
  # Doc: my docstring

  uv run python pipeline/build.py --run test_doc.py
  # Bella compiled output:
  # Doc: None
  ```
- **Suggested Fix:**
  Emit `c.doc` into `Code` and pass it to `f->doc` during `make_function`.

---

## 3. Architecture & Code Quality Evaluation

### 3.1 C++ Emitter (`pipeline/backend/cpp.py`)
- **Structure:** Clean ANF code generation emitting readable, indented C++26 code. The mapping from L2 `Let`, `Do`, `Release`, and `Store` to C++ `Ref` assignments is direct and understandable.
- **Hygiene & Naming:** Identifier renaming via `_KEYWORDS` and `_EMITTER_NAME` is fragile because new compiler temporaries (`ended1`, `raised1`) were added without registering them in `_EMITTER_NAME` or using a distinct prefix. Standardizing on a dedicated prefix (such as `_l2_`) will eliminate identifier collisions systematically.
- **Control Flow & Cleanup:** Inlining `finally` blocks across `return`, `break`, and `continue` requires care regarding C++ exception scope nesting. Because inlined finally blocks currently execute inside the enclosing C++ `try`, exceptions raised within `finally` are improperly caught by the same `catch (...)` block.

### 3.2 Runtime Separation (`runtime/prelude/` vs `runtime/src/`)
- Writing higher-level builtins (`build_class`, `classmethod`, `staticmethod`, `property`, `super`) in Python prelude files ([`runtime/prelude/`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/)) and compiling them through the same compiler pipeline is a major strength.
- However, prelude methods must anticipate edge cases where operands are not standard Python functions (e.g. `classmethod` wrapping a custom callable object as in RL-199).

### 3.3 Memory Model & Object Layout (`runtime/src/` & `runtime/include/bella/object.hpp`)
- The 16-byte `Obj` word and `Ref` RAII wrapper are robust and performant.
- Care is needed when native methods dereference `Obj` receivers: calling `static_cast<List*>(self.object())` without verifying `is_kind(self, Kind::List)` bypasses type safety and turns Python `TypeError`s into OS segmentation faults.

---

## 4. Recommended Next Steps

1. **Fix Critical Severity Findings Prior to Step 3a.3:**
   - Resolve **RL-188** (finally inlining exception handling) in [`pipeline/backend/cpp.py`](file:///home/nathan/workspaces/nth/bella/pipeline/backend/cpp.py).
   - Add receiver type checks across all native method descriptors (**RL-189**) in [`runtime/src/call.cpp`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp) and [`runtime/src/ops.cpp`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp).
   - Add arity enforcement in `set.discard` and `set.remove` (**RL-190**) in [`runtime/src/set.cpp`](file:///home/nathan/workspaces/nth/bella/runtime/src/set.cpp).
   - Catch `bella::TypeError` during class creation and re-throw as `PyError` (**RL-191**).

2. **Harden Native Sequence and Collection Operations:**
   - Implement list mutation protection during sequence comparisons (**RL-192**).
   - Ensure sequence rich comparison returns the raw element comparison object (**RL-193**).
   - Track iteration mutation versions in `SetObject` and `Dict` (**RL-196**).

3. **Compiler Hygiene:**
   - Namespace all emitter-generated temporaries with `_l2_` (**RL-197**).
   - Wire `__doc__` preservation into `make_function` and `Code` records (**RL-200**).
