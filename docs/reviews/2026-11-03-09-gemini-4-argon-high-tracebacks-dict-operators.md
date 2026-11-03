# Bella C++ Leg Review (`f12af86..e827a47`, Tracebacks, Compact Dicts, Builtin Operators & Argument Handling)

- **Date:** 2026-11-03
- **Reviewer:** `gemini-4-argon-high`
- **Sequence:** 09
- **Commit Range Reviewed:** `f12af86..e827a47` (`f12af861c6c6c62853811a97c775ac9fb273441b..e827a479b08607756ac2c6b96ae6f2195563f79b`)
- **Reviewed HEAD:** `e827a479b08607756ac2c6b96ae6f2195563f79b`

---

## 1. Executive Summary

This review covers the 8 commits in range `f12af86..e827a47` on `main`, delivering:
1. Resolution of prior reviews `RL-188` to `RL-219` ([`1904b02`](file:///home/nathan/workspaces/nth/bella/docs/reviews/review-log.md));
2. Gate 0 Task 3 Step 3a.3: The compact `DictObject` unified type, split instance dicts, live views (`keys`, `values`, `items`), and deallocation ordering ([`59433a8`](file:///home/nathan/workspaces/nth/bella/runtime/include/bella/object.hpp));
3. Argument validation, CPython error wording across calling conventions, `f(*value)` intrinsic (`call_args_tuple`), and `list.index(x, start, stop)` ([`5a331d6`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp));
4. Operator dispatch on built-in types following CPython's `abstract.c` (number slots, sequence slots, in-place operators, rich comparisons, set operations) and refusal tables ([`fd6ad46`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp));
5. Constructor refusals for unconstructible built-ins ([`64c6ebb`](file:///home/nathan/workspaces/nth/bella/runtime/src/types.cpp), RL-220);
6. Decision D-12 Part 1: Traceback recording where exceptions arrive (`frame.arrived(e)` at catches, `FrameGuard` unwinding, chained uncaught reports) ([`e827a47`](file:///home/nathan/workspaces/nth/bella/runtime/src/core.cpp), case C-3-30).

### 1.1 Verification Status

The baseline test suite passes completely across all layers:
- `uv run make check` passed in full (448 pytest unit tests, 176 closure modules, 141 conformance expectations, `compiled-corpus` 18/76, `object-test` with ASan/UBSan 1020 operations, `float-diff` 800k+ conversions, and 5/5 slice targets green).
- Prior review remediation (`1904b02`) successfully verified all 23 findings from round 08 in [`pipeline/tests/test_review_2026_11_03.py`](file:///home/nathan/workspaces/nth/bella/pipeline/tests/test_review_2026_11_03.py).

---

### 1.2 Summary of Findings

Following the project principle—*settling what CPython does strictly by executing pinned CPython 3.15.2, treating every claim as something to break*—we identified **10 concrete semantic divergences, compiler/runtime crashes, memory errors, and spec violations** across the reviewed commits:

| Finding ID | Severity | Subsystem | Summary |
|---|---|---|---|
| **RL-228** | Critical | Runtime / List | `list.remove()` dereferences freed memory and crashes with SIGSEGV (exit 139) if `__eq__` empties or shrinks the list |
| **RL-229** | Critical | Runtime / Ops | `list.extend(a)` and `a += a` enter an infinite loop and exhaust memory when extending a list by itself |
| **RL-230** | High | Runtime / List | `list.count()` stores uncounted raw `Obj` pointers in a temporary vector, causing heap-use-after-free if `__eq__` clears the list |
| **RL-231** | High | Runtime / Core | `raise ... from <non-exception>` assigns arbitrary objects as `__cause__` instead of raising `TypeError` |
| **RL-232** | High | Runtime / Dict | `dict.pop()` performs two separate hash-table lookups, invoking `__eq__` twice and failing to remove keys mutated in `__eq__` |
| **RL-233** | High | Runtime / Ops | Dict iteration checks `d->used` instead of `d->version`, missing concurrent key mutations that preserve dict size |
| **RL-234** | Medium | Runtime / Types | `MethodType.__new__()` and `slice.__new__()` underflow unsigned `size_t` on 0 arguments, reporting `got 18446744073709551615` |
| **RL-235** | Medium | Runtime / Ops | Setting `__iter__ = None` attempts to invoke `None()` raising `TypeError: 'NoneType' object is not callable` instead of recognizing it as non-iterable |
| **RL-236** | Medium | Runtime / Types | `object.__init__` uses `__qualname__` instead of `__name__`, reporting incorrect class names for nested types |
| **RL-237** | Medium | Runtime / List | `list.pop(i)` reports `pop index out of range` instead of `pop from empty list` if user `__index__` empties the list |

---

## 2. Technical Findings & Reproductions Against CPython 3.15.2

### 2.1 RL-228 [Critical / Crash] `list.remove()` Dereferences Freed Memory and Crashes with SIGSEGV When `__eq__` Shrinks the List

- **Locations:** [`runtime/src/call.cpp:605-610`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp#L605-L610) (`list_remove_m`), [`runtime/src/call.cpp:572-580`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp#L572-L580) (`list_find`).
- **Problem:** [`list_remove_m`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp#L603) finds the target item's index via `list_find(self, a.pos(0))`:
  ```cpp
  Ref list_remove_m(Obj self, Args a) {
      onearg(a, "list.remove");
      std::int64_t i = list_find(self, a.pos(0));
      if (i < 0) raise_new("ValueError", "list.remove(x): x not in list");
      auto& items = list_self(self)->items;
      Obj old = items[static_cast<std::size_t>(i)];
      items.erase(items.begin() + i);
      decref(old);
      return none_ref();
  }
  ```
  During `list_find`, `compare(CmpOp::Eq, x, v)` invokes user Python `__eq__` methods. If an element's `__eq__` method clears or shrinks the list (e.g. `a.clear()`), `list_find` returns index 0. `list_remove_m` then unconditionally indexes `items[0]` and calls `items.erase(items.begin() + 0)` on the now-empty vector `items`, dereferencing invalid memory and crashing with `SIGSEGV` (exit code 139).
- **Minimal Reproduction (`test_list_remove_uaf.py`):**
  ```python
  a = []

  class Key:
      def __init__(self, name):
          self.name = name
      def __eq__(self, other):
          a.clear()
          return True

  k1 = Key("k1")
  k2 = Key("k2")
  a.append(k1)

  a.remove(k2)
  print("Done, len:", len(a))
  ```
- **Execution & Output:**
  ```sh
  uv run python test_list_remove_uaf.py
  # CPython 3.15.2 output:
  # Done, len: 0

  uv run python pipeline/build.py --run test_list_remove_uaf.py
  # Bella compiled output:
  # [process terminated by SIGSEGV, return code 139]
  ```
- **Suggested Fix:**
  In [`runtime/src/call.cpp:607`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp#L607), re-verify vector bounds and element identity before erasing:
  ```cpp
  auto& items = list_self(self)->items;
  if (static_cast<std::size_t>(i) >= items.size())
      raise_new("ValueError", "list.remove(x): x not in list");
  ```

---

### 2.2 RL-229 [Critical / Infinite Loop] `list.extend(a)` and `a += a` Loop Infinitely When Extending a List by Itself

- **Locations:** [`runtime/src/ops.cpp:1138-1142`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L1138-L1142) (`list_extend`), [`runtime/src/ops.cpp:188`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L188) (`sequence_op`).
- **Problem:** [`list_extend`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L1138) iterates over `value` using `iter(value)` while appending items directly to `list`:
  ```cpp
  void list_extend(Obj list, Obj value) {
      Ref it = iter(value);
      for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get()))
          static_cast<List*>(list.object())->items.push_back(v.release());
  }
  ```
  Unlike `set_merge` (which explicitly guards `if (other == so) return;`) or CPython's `list_extend` (which guards `if (self == b)`), `list_extend` does not check if `list == value`. When extending a list by itself (`a.extend(a)` or `a += a`), every iteration appends an element, increasing `items.size()` at the same rate `it->pos` advances. The loop never terminates, consuming CPU and memory until timeout or OOM.
- **Minimal Reproduction (`test_extend_self.py`):**
  ```python
  a = [1, 2]
  a.extend(a)
  print("Done:", a)
  ```
- **Execution & Output:**
  ```sh
  uv run python test_extend_self.py
  # CPython 3.15.2 output:
  # Done: [1, 2, 1, 2]

  uv run python pipeline/build.py --run test_extend_self.py
  # Bella compiled output:
  # [process hangs indefinitely / times out]
  ```
- **Suggested Fix:**
  In [`runtime/src/ops.cpp:1138`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L1138), snapshot the list if `list == value`:
  ```cpp
  void list_extend(Obj list, Obj value) {
      if (list == value) {
          auto items = static_cast<List*>(list.object())->items;
          for (Obj v : items) { incref(v); static_cast<List*>(list.object())->items.push_back(v); }
          return;
      }
      Ref it = iter(value);
      for (Ref v = for_next(it.get()); !is_end(v); v = for_next(it.get()))
          static_cast<List*>(list.object())->items.push_back(v.release());
  }
  ```

---

### 2.3 RL-230 [High / Use-After-Free] `list.count()` Stores Uncounted Raw Pointers in Temporary Vector, Causing Heap-Use-After-Free

- **Locations:** [`runtime/src/call.cpp:613-621`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp#L613-L621) (`list_count_m`).
- **Problem:** [`list_count_m`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp#L613) iterates over a temporary vector:
  ```cpp
  Ref list_count_m(Obj self, Args a) {
      onearg(a, "list.count");
      std::int64_t n = 0;
      for (Obj x : std::vector<Obj>(list_self(self)->items)) {
          Ref hold = Ref::share(x);
          if (x == a.pos(0) || truth(compare(CmpOp::Eq, x, a.pos(0)).get())) ++n;
      }
      return Ref::steal(Obj::small(n));
  }
  ```
  `std::vector<Obj>` copies raw `Obj` tagged words without taking reference counts (`incref`). If an item's `__eq__` method mutates `self` (e.g. `l.clear()`), all remaining elements in the list are deallocated immediately. On subsequent loop iterations, `x` holds a dangling pointer to a freed heap object. `Ref::share(x)` increments the refcount of dead memory and invokes `compare` on a zombie object.
- **Minimal Reproduction (`test_count_uaf.py`):**
  ```python
  l = []

  class Key:
      def __init__(self, name):
          self.name = name
      def __del__(self):
          print("del", self.name)
      def __eq__(self, other):
          print("eq", self.name)
          l.clear()
          return False

  k1 = Key("k1")
  k2 = Key("k2")
  l.extend([k1, k2])
  del k1; del k2

  target = Key("target")
  print("calling count:")
  l.count(target)
  print("done")
  ```
- **Execution & Output:**
  ```sh
  uv run python test_count_uaf.py
  # CPython 3.15.2 output:
  # calling count:
  # eq k1
  # del k2
  # del k1
  # done
  # del target

  uv run python pipeline/build.py --run test_count_uaf.py
  # Bella compiled output:
  # calling count:
  # eq k1
  # del k2
  # del k1
  # eq target          <-- Invoking __eq__ on freed k2 object!
  # done
  # del target
  ```
- **Suggested Fix:**
  Follow CPython's `list_count` (`Objects/listobject.c`): iterate using index `i` over `items` directly, checking `i < items.size()` on each step, rather than storing uncounted raw pointers in a detached vector.

---

### 2.4 RL-231 [High / Spec Violation] `raise ... from <non-exception>` Sets Arbitrary Objects as `__cause__` Instead of Raising `TypeError`

- **Locations:** [`runtime/src/core.cpp:518-528`](file:///home/nathan/workspaces/nth/bella/runtime/src/core.cpp#L518-L528) (`raise_type`).
- **Problem:** In Python, the expression `raise E from C` requires that `C` is either `None` or an instance/subclass of `BaseException`; any other cause must raise `TypeError: exception causes must derive from BaseException`. In [`runtime/src/core.cpp:518`](file:///home/nathan/workspaces/nth/bella/runtime/src/core.cpp#L518):
  ```cpp
  if (has_cause) {
      Obj c = cause;
      Ref made;
      if (is_kind(c, Kind::Class)) {
          made = invoke(c, {});
          c = made.get();
      }
      setattr(static_cast<Instance*>(exc.get().object()), intern("__cause__"), c);
      setattr(static_cast<Instance*>(exc.get().object()), intern("__suppress_context__"), boolean(true));
  }
  ```
  Bella never validates whether `c` is `None` or an exception object. Passing an arbitrary non-exception (e.g. `raise ValueError("bad") from 123`) blindly sets `__cause__ = 123` on the exception and proceeds.
- **Minimal Reproduction (`test_raise_from_int.py`):**
  ```python
  try:
      raise ValueError("bad") from 123
  except TypeError as e:
      print("Caught TypeError:", e)
  except ValueError as e:
      print("Caught ValueError; cause is:", repr(e.__cause__))
  ```
- **Execution & Output:**
  ```sh
  uv run python test_raise_from_int.py
  # CPython 3.15.2 output:
  # Caught TypeError: exception causes must derive from BaseException

  uv run python pipeline/build.py --run test_raise_from_int.py
  # Bella compiled output:
  # Caught ValueError; cause is: 123
  ```
- **Suggested Fix:**
  In [`runtime/src/core.cpp:518`](file:///home/nathan/workspaces/nth/bella/runtime/src/core.cpp#L518), enforce cause validity:
  ```cpp
  if (has_cause) {
      if (cause != None() && !is_exception(cause) &&
          !(is_kind(cause, Kind::Class) && is_subclass(static_cast<ClassObject*>(cause.object()), base)))
          raise_new("TypeError", "exception causes must derive from BaseException");
      ...
  ```

---

### 2.5 RL-232 [High / Data Inconsistency] `dict.pop()` Performs Two Lookups, Calling `__eq__` Twice and Leaving Mutated Keys in Dict

- **Locations:** [`runtime/src/call.cpp:644-655`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp#L644-L655) (`dict_pop_m`).
- **Problem:** [`dict_pop_m`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp#L644) executes two separate dictionary lookups:
  ```cpp
  Ref dict_pop_m(Obj self, Args a) {
      clinic(a, "pop", "dict.pop", 1, 2);
      Obj v = dict_get(dict_self(self), a.pos(0));
      if (v.is_unset()) {
          if (a.npos > 1) return Ref::share(a.pos(1));
          Ref exc = invoke(Obj::of(exception_class("KeyError")), {a.pos(0)});
          raise(exc.get());
      }
      Ref out = Ref::share(v);
      dict_del(dict_self(self), a.pos(0));
      return out;
  }
  ```
  `dict_get` performs a full lookup that invokes `__eq__`. Then line 653 performs a second independent lookup via `dict_del`. In CPython, `dict.pop` evaluates `__eq__` exactly once. If `__eq__` mutates the dictionary during the first lookup, the second lookup fails to match the key; `dict_pop_m` returns the popped value, but leaves the key inside the dictionary (`len(d)` remains 1).
- **Minimal Reproduction (`test_dict_pop_eq.py`):**
  ```python
  d = {}
  mutated = False

  class Key:
      def __init__(self, name):
          self.name = name
      def __hash__(self):
          return 42
      def __eq__(self, other):
          global mutated
          if self.name == "k1" and getattr(other, "name", None) == "k2" and not mutated:
              mutated = True
              d[self] = "mutated_value"
              return True
          return getattr(self, "name", None) == getattr(other, "name", None)

  k1 = Key("k1")
  k2 = Key("k2")
  d[k1] = "orig_val"

  res = d.pop(k2)
  print("pop:", res, "len:", len(d))
  ```
- **Execution & Output:**
  ```sh
  uv run python test_dict_pop_eq.py
  # CPython 3.15.2 output:
  # pop: mutated_value len: 0

  uv run python pipeline/build.py --run test_dict_pop_eq.py
  # Bella compiled output:
  # pop: mutated_value len: 1
  ```
- **Suggested Fix:**
  Use the atomic `dict_pop(d, key, hash)` helper already provided in [`runtime/include/bella/object.hpp:440`](file:///home/nathan/workspaces/nth/bella/runtime/include/bella/object.hpp#L440):
  ```cpp
  Ref dict_pop_m(Obj self, Args a) {
      clinic(a, "pop", "dict.pop", 1, 2);
      Dict* d = dict_self(self);
      Obj v = dict_pop(d, a.pos(0), hash_of(a.pos(0)));
      if (v.is_unset()) {
          if (a.npos > 1) return Ref::share(a.pos(1));
          Ref exc = invoke(Obj::of(exception_class("KeyError")), {a.pos(0)});
          raise(exc.get());
      }
      return Ref::steal(v);
  }
  ```

---

### 2.6 RL-233 [High / Silent Data Corruption] Dict Iteration Checks `d->used` Instead of `d->version`, Missing Concurrent Key Modifications

- **Locations:** [`runtime/src/ops.cpp:1020-1023`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L1020-L1023) (`Iterator::DictKeysIt`).
- **Problem:** In [`runtime/src/ops.cpp:1020`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L1020):
  ```cpp
  auto* d = static_cast<Dict*>(it->seq.object());
  if (it->size == -2 || static_cast<std::int64_t>(d->used) != it->size) {
      it->size = -2;
      raise_new("RuntimeError", "dictionary changed size during iteration");
  }
  ```
  `Iterator` only checks `d->used != it->size`. In CPython 3.15.2, dict iteration verifies `ma_version_tag`. When a key is deleted and another added (or keys are re-inserted), `d->used` remains unchanged. Bella skips the error check, iterates into newly added keys, and continues iteration silently instead of raising `RuntimeError: dictionary keys changed during iteration`.
- **Minimal Reproduction (`test_dict_version.py`):**
  ```python
  d = {1: "a"}
  try:
      for k in d:
          if k == 1:
              del d[1]
              d[2] = "b"
          print("Saw:", k)
  except RuntimeError as e:
      print("Caught RuntimeError:", e)
  ```
- **Execution & Output:**
  ```sh
  uv run python test_dict_version.py
  # CPython 3.15.2 output:
  # Saw: 1
  # Caught RuntimeError: dictionary keys changed during iteration

  uv run python pipeline/build.py --run test_dict_version.py
  # Bella compiled output:
  # Saw: 1
  # Saw: 2
  ```
- **Suggested Fix:**
  Store `it->version = d->version` on `Iterator` during construction, and check `if (d->version != it->version) raise_new("RuntimeError", "dictionary keys changed during iteration");` on each step.

---

### 2.7 RL-234 [Medium / Arithmetic Underflow] `MethodType.__new__()` and `slice.__new__()` Underflow `size_t` on 0 Args, Reporting `got 18446744073709551615`

- **Locations:** [`runtime/src/types.cpp:50`](file:///home/nathan/workspaces/nth/bella/runtime/src/types.cpp#L50) (`rest`), [`runtime/src/types.cpp:631`](file:///home/nathan/workspaces/nth/bella/runtime/src/types.cpp#L631) (`method_new`), [`runtime/src/types.cpp:696`](file:///home/nathan/workspaces/nth/bella/runtime/src/types.cpp#L696) (`slice_new`).
- **Problem:** [`runtime/src/types.cpp:50`](file:///home/nathan/workspaces/nth/bella/runtime/src/types.cpp#L50) defines:
  ```cpp
  Args rest(Args a) { return Args{a.data + 1, a.npos - 1, a.kwnames, a.nkw}; }
  ```
  Both `method_new` and `slice_new` call `Args r = rest(a)` without verifying that `a.npos >= 1`. When called with 0 arguments (`MethodType.__new__()` or `slice.__new__()`), `a.npos - 1` underflows unsigned `size_t` to `SIZE_MAX` (`18446744073709551615`). When passed to `arity(r, ...)`, Bella raises `TypeError: method expected 2 arguments, got 18446744073709551615`.
- **Minimal Reproduction (`test_slice_new_zero.py`):**
  ```python
  MethodType = type((lambda: None).__get__(1))
  try:
      MethodType.__new__()
  except TypeError as e:
      print("MethodType:", e)
  try:
      slice.__new__()
  except TypeError as e:
      print("slice:", e)
  ```
- **Execution & Output:**
  ```sh
  uv run python test_slice_new_zero.py
  # CPython 3.15.2 output:
  # MethodType: method.__new__(): not enough arguments
  # slice: slice.__new__(): not enough arguments

  uv run python pipeline/build.py --run test_slice_new_zero.py
  # Bella compiled output:
  # MethodType: method expected 2 arguments, got 18446744073709551615
  # slice: slice expected from 1 to 3 arguments, got 18446744073709551615
  ```
- **Suggested Fix:**
  Add `if (a.npos < 1) raise_new("TypeError", "<type>.__new__(): not enough arguments");` in `method_new` and `slice_new` before invoking `rest(a)`.

---

### 2.8 RL-235 [Medium / Spec Violation] Setting `__iter__ = None` Attempts to Call `None()` Raising `TypeError: 'NoneType' object is not callable`

- **Locations:** [`runtime/src/ops.cpp:944-953`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L944-L953) (`iter`), [`runtime/src/call.cpp:1128`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp#L1128) (`i_call_args_tuple`).
- **Problem:** In Python's data model, assigning `__iter__ = None` on a class explicitly marks its instances as non-iterable. In Bella's [`iter`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L944):
  ```cpp
  bool has = false;
  Ref r = call_special(obj, "__iter__", {}, &has);
  if (has) return r;
  ```
  `call_special` finds `__iter__`, observes `has = true`, and attempts to invoke `None()`. This raises `TypeError: 'NoneType' object is not callable` instead of falling back or raising `TypeError: 'X' object is not iterable`. The same issue affects `i_call_args_tuple`.
- **Minimal Reproduction (`test_iter_none.py`):**
  ```python
  class NotIterable:
      __iter__ = None

  try:
      iter(NotIterable())
  except TypeError as e:
      print(e)
  ```
- **Execution & Output:**
  ```sh
  uv run python test_iter_none.py
  # CPython 3.15.2 output:
  # 'NotIterable' object is not iterable

  uv run python pipeline/build.py --run test_iter_none.py
  # Bella compiled output:
  # 'NoneType' object is not callable
  ```
- **Suggested Fix:**
  In [`runtime/src/ops.cpp:944`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp#L944), inspect `type_lookup(type_of(obj), intern("__iter__"))`. If it equals `None()`, treat `__iter__` as absent and fall through directly to `__getitem__` or raise `'X' object is not iterable`.

---

### 2.9 RL-236 [Medium / Formatting Error] `object.__init__` Uses `__qualname__` Instead of `__name__` for Nested Types

- **Locations:** [`runtime/src/types.cpp:274`](file:///home/nathan/workspaces/nth/bella/runtime/src/types.cpp#L274) (`object_init`).
- **Problem:** In [`runtime/src/types.cpp:274`](file:///home/nathan/workspaces/nth/bella/runtime/src/types.cpp#L274):
  ```cpp
  if (type_lookup(cls, N("__new__")) == object_new_fn())
      raise_new("TypeError", cls->qualname + ".__init__() takes exactly one argument (the instance to initialize)");
  ```
  CPython formats this error using `tp_name` (`cls->name`), producing `C.__init__()`. Bella uses `cls->qualname`, producing `Outer.C.__init__()` when the class is nested inside another class or function scope.
- **Minimal Reproduction (`test_qualname_init.py`):**
  ```python
  class Outer:
      class C: pass

  c = Outer.C()
  try:
      object.__init__(c, 1, 2)
  except TypeError as e:
      print(e)
  ```
- **Execution & Output:**
  ```sh
  uv run python test_qualname_init.py
  # CPython 3.15.2 output:
  # C.__init__() takes exactly one argument (the instance to initialize)

  uv run python pipeline/build.py --run test_qualname_init.py
  # Bella compiled output:
  # Outer.C.__init__() takes exactly one argument (the instance to initialize)
  ```
- **Suggested Fix:**
  Change `cls->qualname` to `cls->name` in [`runtime/src/types.cpp:274`](file:///home/nathan/workspaces/nth/bella/runtime/src/types.cpp#L274).

---

### 2.10 RL-237 [Medium / Spec Violation] `list.pop(i)` Reports `pop index out of range` Instead of `pop from empty list` if `__index__` Empties List

- **Locations:** [`runtime/src/call.cpp:545-549`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp#L545-L549) (`list_pop_m`).
- **Problem:** In [`runtime/src/call.cpp:546`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp#L546):
  ```cpp
  if (items.empty()) raise_new("IndexError", "pop from empty list");
  std::int64_t i = a.npos ? index_value(a.pos(0)) : -1;
  if (i < 0) i += static_cast<std::int64_t>(items.size());
  if (i < 0 || i >= static_cast<std::int64_t>(items.size())) raise_new("IndexError", "pop index out of range");
  ```
  `list_pop_m` checks `if (items.empty())` *before* evaluating `index_value(a.pos(0))`. In CPython, `__index__` is evaluated first. If user code inside `__index__` clears the list, CPython observes that the list is empty and raises `IndexError: pop from empty list`. Bella instead reaches line 549 and raises `IndexError: pop index out of range`.
- **Minimal Reproduction (`test_pop_empty.py`):**
  ```python
  l = []

  class Idx:
      def __index__(self):
          l.clear()
          return 0

  l.extend([10, 20])
  try:
      l.pop(Idx())
  except IndexError as e:
      print(e)
  ```
- **Execution & Output:**
  ```sh
  uv run python test_pop_empty.py
  # CPython 3.15.2 output:
  # pop from empty list

  uv run python pipeline/build.py --run test_pop_empty.py
  # Bella compiled output:
  # pop index out of range
  ```
- **Suggested Fix:**
  Convert `a.pos(0)` via `index_value` first, and check `if (items.empty()) raise_new("IndexError", "pop from empty list");` afterwards.

---

## 3. Architecture & Code Quality Evaluation

### 3.1 Tracebacks & Decision D-12 ([`runtime/src/core.cpp`](file:///home/nathan/workspaces/nth/bella/runtime/src/core.cpp), [`pipeline/backend/cpp.py`](file:///home/nathan/workspaces/nth/bella/pipeline/backend/cpp.py))
- Part 1 of D-12 is a huge step forward: recording traceback entries at the point of arrival (`frame.arrived(e)`) ensures that line numbers reflect failing calls and inner raise sites rather than cleanup points at the end of functions.
- The chained exception report in `print_traceback` matches CPython's `traceback.TracebackException` formatting and respects `__suppress_context__` and cycle detection.

### 3.2 Unified Dict Architecture ([`runtime/include/bella/object.hpp`](file:///home/nathan/workspaces/nth/bella/runtime/include/bella/object.hpp))
- Eliminating `Kind::PyDict` and standardizing on `DictObject` across both standalone dicts and instance `__dict__` is clean and adheres to CPython's object model.
- Probing restarts with `d->layout` invalidation properly preserve table integrity during reentrant `__eq__` lookups.
- However, dictionary methods (`dict.pop` in RL-232 and dict views in RL-233) must use the atomic hash-table primitives and `d->version` counters already provided in `object.hpp`.

### 3.3 Operator Protocols ([`runtime/src/ops.cpp`](file:///home/nathan/workspaces/nth/bella/runtime/src/ops.cpp))
- The implementation of `abstract.c`'s precedence rules (number slots first, sequence concatenation/repetition fallback, in-place methods) correctly reflects CPython's dispatch order.
- The static name registry in `cpython_names.inc` ensures that unimplemented operators and attributes fail closed with `NotImplemented` refusals rather than incorrect `AttributeError` / `TypeError` exceptions.

---

## 4. Recommended Next Steps

1. **Fix Critical Severity Findings Prior to Step 3b:**
   - Add boundary check in `list.remove` ([`RL-228`](#21-rl-228-critical--crash-listremove-dereferences-freed-memory-and-crashes-with-sigsegv-when-__eq__-shrinks-the-list)).
   - Guard against self-extension in `list.extend` and `list += list` ([`RL-229`](#22-rl-229-critical--infinite-loop-listextenda-and-a--a-loop-infinitely-when-extending-a-list-by-itself)).
   - Avoid uncounted raw pointers in `list.count` ([`RL-230`](#23-rl-230-high--use-after-free-listcount-stores-uncounted-raw-pointers-in-temporary-vector-causing-heap-use-after-free)).
   - Enforce `BaseException` subclass or `None` on exception causes ([`RL-231`](#24-rl-231-high--spec-violation-raise--from-non-exception-sets-arbitrary-objects-as-__cause__-instead-of-raising-typeerror)).

2. **Dict & Collection Hardening:**
   - Replace the two-step `dict_get` + `dict_del` sequence in `dict.pop` with atomic `dict_pop` ([`RL-232`](#25-rl-232-high--data-inconsistency-dictpop-performs-two-lookups-calling-__eq__-twice-and-leaving-mutated-keys-in-dict)).
   - Check `d->version` during dict iteration ([`RL-233`](#26-rl-233-high--silent-data-corruption-dict-iteration-checks-d-used-instead-of-d-version-missing-concurrent-key-modifications)).

3. **Argument & Builtin Protocol Polish:**
   - Guard against 0 arguments in `method_new` and `slice_new` ([`RL-234`](#27-rl-234-medium--arithmetic-underflow-methodtype__new__-and-slice__new__-underflow-size_t-on-0-args-reporting-got-18446744073709551615)).
   - Handle `__iter__ = None` sentinel in `iter` and `call_args_tuple` ([`RL-235`](#28-rl-235-medium--spec-violation-setting-__iter__--none-attempts-to-call-none-raising-typeerror-nonetype-object-is-not-callable)).
