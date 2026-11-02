# Bella L2 Lifetimes Review (`58bb34b..d28b256`, L2 ANF, Name Resolution, Reference Model & C++ Object Header)

- **Date:** 2026-11-02
- **Reviewer:** `gemini-4-argon-high`
- **Sequence:** 07
- **Commit Range Reviewed:** `58bb34b..d28b256` (`58bb34b7b6b2fdce87e2972b87f38c80cbc0aa7a..d28b25606840edeed5ccdcae4d1207b3c2773634`)
- **Reviewed HEAD:** `d28b25606840edeed5ccdcae4d1207b3c2773634`

---

## 1. Executive Summary

This review covers the 15 commits in range `58bb34b..d28b256`, advancing Gate 0 Task 3 (the reference object model and C++ object header) and Task 4 (the L2 intermediate representation, name resolution, ANF lowering, lifetimes pass, well-formedness checker `wf2`, and `eval2` execution runner).

### 1.1 Scope & Verification Status

1. **Resolution of Prior Reviews (`a2939cb`):**
   - Commit `a2939cb` systematically resolved all 33 findings (`RL-136` through `RL-168` in [`docs/reviews/review-log.md`](file:///home/nathan/workspaces/nth/bella/docs/reviews/review-log.md)) from our previous review (`docs/reviews/2026-11-02-06-gemini-4-argon-high-l1-eval1-review.md`).
   - Regression tests in [`pipeline/tests/test_review_2026_11_02.py`](file:///home/nathan/workspaces/nth/bella/pipeline/tests/test_review_2026_11_02.py) pass cleanly in full.

2. **Decisions Preceding C++ Implementation (`99b47f0`):**
   - Recorded in [`docs/DECISIONS.md`](file:///home/nathan/workspaces/nth/bella/docs/DECISIONS.md), Dialect Spec v0.13, and [`docs/licences.md`](file:///home/nathan/workspaces/nth/bella/docs/licences.md):
     - `int`: Pinned copy of Software Equalizer Limited's `bn` library (BSD-3-Clause).
     - `float`: Formatting and parsing via `std::to_chars` / `std::from_chars` (libstdc++), verified by [`runtime/tests/float_differential.py`](file:///home/nathan/workspaces/nth/bella/runtime/tests/float_differential.py).
     - `math`: Dynamic linkage against host glibc `libm`, reproducing CPython's machine-dependent IEEE-754 semantics.
     - L2 intermediate representation specification in [`docs/l2.md`](file:///home/nathan/workspaces/nth/bella/docs/l2.md) v1.

3. **L2 Lowering Pipeline (`cbdde8b`, `34162be`, `728ab70`):**
   - [`pipeline/l2/grammar.py`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/grammar.py): AST representation for A-Normal Form (ANF) statements, atomic operands (`Const`, `Temp`), and explicit memory/scope operations (`Let`, `Do`, `Release`, `Store`, `Delete`).
   - [`pipeline/l2/resolve.py`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/resolve.py): Computes CPython scope classification (`LOCAL`, `CELL`, `FREE`, `GLOBAL_EXPLICIT`, `GLOBAL_IMPLICIT`) and slot tables (`co_varnames`, `co_cellvars`, `co_freevars`).
   - [`pipeline/l2/lower.py`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/lower.py): Flattens L1 expressions into temporaries following Python's left-to-right evaluation order.
   - [`pipeline/l2/lifetimes.py`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/lifetimes.py): Inserts precise `Release` statements where temporaries expire.
   - [`pipeline/l2/wf.py`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/wf.py): Verifies L2 invariants before and after lifetime annotation.
   - [`pipeline/l2/eval2.py`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/eval2.py): Executes L2 by synthesizing and running host Python code objects with slot-checking and release-audit modes.

4. **Reference Model & C++ Object Header (`60f1fe1`, `9eba3e1`, `d28b256`):**
   - Reference model [`refmodel/objects.py`](file:///home/nathan/workspaces/nth/bella/refmodel/objects.py) models reference counting, split instance dicts with shared keys (up to 30 keys), C3 MRO linearisation, inline cache invalidation via monotonically increasing class versions, and conformance case `C-9-08`.
   - Real C++26 header [`runtime/include/bella/object.hpp`](file:///home/nathan/workspaces/nth/bella/runtime/include/bella/object.hpp) implements the single-threaded object model with a 16-byte object header (`Obj` tagged words, `ClassObject`, `Instance`, `DictObject`, `SlotDescriptor`).

5. **Test Suite Verification:**
   - Ran `uv run make test eval2-corpus targets-eval2 object-test float-diff` on pinned CPython 3.15.2 with GCC 16.2.1:
     - Unit tests: 180 passed in 110s.
     - `refmodel.selftest`: 3000 operations over 50 worlds passed (66,700 cache hits, 24,793 misses, 162 deallocations matching CPython).
     - `eval2-corpus`: 63 of 76 cases passed (preserving baseline).
     - `targets-eval2`: All 3 targets (`cli_easy_slugs`, `service_easy_tokens`, `data_easy_sales`) matched recorded runs byte-for-byte in `--modules closure` mode.
     - `object-test`: 3000 operations passed (199 deaths in CPython order, 63,897 hits); 1020 operations passed with `--sanitize` (AddressSanitizer and UndefinedBehaviorSanitizer).
     - `float-diff`: 375,024 shortest, 150,000 scientific, 150,000 fixed, and 225,007 parse cases with 0 unexpected differences against CPython 3.15.2.

---

### 1.2 Summary of Findings

Despite the comprehensive test coverage on ordinary paths, treating "what CPython does" as a strict standard of truth settled by running CPython 3.15.2 reveals **14 concrete divergences and bugs** across the new code:

- **1 Critical Memory Safety Bug:** A borrowed fallback hook in [`runtime/include/bella/object.hpp`](file:///home/nathan/workspaces/nth/bella/runtime/include/bella/object.hpp) causes heap use-after-free under reentrant descriptor deletion (§2.1).
- **5 High Severity Lifetime Leaks / Scope Bugs:** Chained comparison temporaries leaking into frame/module locals (§2.2); decorator callables retained until scope exit (§2.3); frontend synthetic variables polluting `co_varnames` (§2.4); intermediate `global` declarations failing to isolate inner closures (§2.5); and failed `with` entry leaking context managers (§2.6).
- **1 High Severity Traceback Retention Bug:** Implementation helper frames retaining exception operands (§2.7).
- **4 Medium Severity Evaluation / Deallocation Order Bugs:** Augmented assignment to subscripts dropping key after result (§2.8); augmented assignment to attributes dropping owner after result (§2.9); `__slots__` deallocation inverting CPython's release order (§2.10); and valid unreachable code causing `wf2` rejection (§2.11).
- **3 Hygiene & Verifier Bugs:** `locals()` / `vars()` frame isolation bypass (§2.12); module-level `BaseException` shadowing (§2.13); and `wf2` accepting consumed returns before `finally` (§2.14).

All findings below exclude the known open items explicitly listed in [`TODO.md`](file:///home/nathan/workspaces/nth/bella/TODO.md) (comprehension/PEP 695 scopes, async def, >30 shared keys, non-string keys, resurrecting `__del__`, `__class__` assignment, dict-mode classes, weakrefs, threads).

---

## 2. Technical Findings & Reproductions Against CPython 3.15.2

### 2.1 [Critical / Memory Safety] Borrowed Fallback Hook in `object.hpp` Causes Heap Use-After-Free under Reentrant Descriptor Mutation

- **Locations:** [`runtime/include/bella/object.hpp:590-612`](file:///home/nathan/workspaces/nth/bella/runtime/include/bella/object.hpp#L590-L612) (`execute`), [`runtime/include/bella/object.hpp:435`](file:///home/nathan/workspaces/nth/bella/runtime/include/bella/object.hpp#L435) (`call`), [`runtime/include/bella/object.hpp:527-545`](file:///home/nathan/workspaces/nth/bella/runtime/include/bella/object.hpp#L527-L545) (`plan_generic`), and [`runtime/include/bella/object.hpp:558`](file:///home/nathan/workspaces/nth/bella/runtime/include/bella/object.hpp#L558) (`plan_cached`).
- **Problem:** When an attribute lookup plan resolves to a descriptor or slot whose execution raises `AttributeError`, `execute` catches `AttributeError` and falls back to calling `plan.hook` (`__getattr__`). However, `plan.hook` is stored as an uncounted borrowed reference (`Obj hook = detail::hook_of(cls)`). If the descriptor's `__get__` method reentrantly mutates the class by deleting or overwriting `__getattr__` (e.g. `del cls.__getattr__`), `hook`'s refcount drops to 0 and the underlying `Function` object is deleted immediately. When `execute` subsequently catches `AttributeError` and invokes `call(plan.hook, ...)`, it executes through a freed pointer, triggering an immediate AddressSanitizer `heap-use-after-free` crash.
- **Minimal Reproduction:**
  Save as `test_uaf.cpp`:
  ```cpp
  #include "bella/object.hpp"
  #include <iostream>

  using namespace bella;

  int main() {
      auto* c = make_class({.name = "C"});
      auto* hook = new Function([](std::span<const Obj>) { return Obj::small(42); });
      c->set_attr(intern("__getattr__"), Obj::of(hook));

      auto* get = new Function([c](std::span<const Obj>) -> Obj {
          c->del_attr(intern("__getattr__")); // Destroys hook
          throw AttributeError("fallback");
      });
      auto* d = make_class({.name = "D", .attrs = {{"__get__", Obj::of(get)}}});
      c->set_attr(intern("x"), Obj::of(new_instance(d)));

      Ref inst = Ref::share(Obj::of(new_instance(c)));
      Ref res = getattr(static_cast<Instance*>(inst.get().object()), intern("x"));
      std::cout << res.get().small_value() << "\n";
  }
  ```
- **Execution & Output:**
  ```sh
  g++ -std=c++26 -O1 -g -fsanitize=address,undefined -Iruntime/include test_uaf.cpp -o test_uaf
  ASAN_OPTIONS=detect_leaks=0 ./test_uaf
  ```
  **CPython Equivalent Behavior:**
  In CPython 3.15.2, `C().x` successfully prints `42`: CPython holds an internal reference to the looked-up `tp_getattr_hook` during descriptor evaluation, preventing premature deallocation.
  **Bella Output:**
  Aborts with AddressSanitizer:
  ```text
  ==12345==ERROR: AddressSanitizer: heap-use-after-free on address 0x... at pc 0x... bp 0x... sp 0x...
  READ of size 8 at 0x... thread T0
      #0 0x... in bella::call(bella::Obj, std::initializer_list<bella::Obj>) runtime/include/bella/object.hpp:435
      #1 0x... in bella::execute(bella::LookupPlan const&, bella::Instance*, bella::Str const*) runtime/include/bella/object.hpp:610
      #2 0x... in bella::getattr(bella::Instance*, bella::Str const*, bella::Site*) runtime/include/bella/object.hpp:631
  freed by thread T0 here:
      #0 0x... in operator delete(void*, unsigned long)
      #1 0x... in bella::detail::bury(bella::Object*) runtime/include/bella/object.hpp:794
      #2 0x... in bella::dealloc(bella::Object*) runtime/include/bella/object.hpp:864
      #3 0x... in bella::decref(bella::Object*) runtime/include/bella/object.hpp:117
      #4 0x... in bella::ClassObject::del_attr(bella::Str const*) runtime/include/bella/object.hpp:299
  ```
- **Suggested Fix:** In `LookupPlan`, convert `hook` and `found` from raw borrowed `Obj` words to owning `Ref` handles during active execution in `execute()`, or incref `plan.hook` before entering user-defined descriptor code and decref it upon exit.

---

### 2.2 [High / Lifetime Leak] Chained Comparison Temporaries (`_cmp0`) Leak Intermediate Operands into Frame / Module Locals

- **Locations:** [`pipeline/l1/frontend.py:1390-1408`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L1390-L1408) (`desugar_chained_compare`), [`pipeline/l2/lower.py:383-389`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/lower.py#L383-L389) (`__bind__`), and [`pipeline/l2/resolve.py:229-232, 266-268`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/resolve.py#L229-L232).
- **Problem:** `desugar_chained_compare` transforms `a < b < c` into `(a < (_bind__('_cmp0', b))) and (_cmp0 < c)`. In `lower.py:388`, `__bind__` stores `b` into synthetic local `_cmp0` (`self.emit(G.Store(self.ref(name.value, "store"), stored))`). In `resolve.py`, `_cmp0` is classified as a hidden `LOCAL` variable. Unlike ANF temporaries which are managed by `lifetimes.py` and released at their last use, named local variables are never released or deleted. As a result, `b` remains alive in the frame until function return, and at module scope remains bound in module globals for the entire process lifetime!
- **Minimal Reproduction:**
  Save as `test_chained.py`:
  ```python
  class Dead:
      def __init__(self, name, val): self.name = name; self.val = val
      def __gt__(self, other): return self.val > (other.val if isinstance(other, Dead) else other)
      def __lt__(self, other): return self.val < (other.val if isinstance(other, Dead) else other)
      def __del__(self): print("del", self.name)

  def run():
      print("start")
      _ = 1 < Dead("mid", 2) < 3
      print("after comp")

  run()
  print("after run")
  ```
- **Execution & Output:**
  ```sh
  uv run python test_chained.py
  uv run python pipeline/l2/run.py test_chained.py
  ```
  **CPython 3.15.2 Output:**
  ```text
  start
  del mid
  after comp
  after run
  ```
  **Bella eval2 Output:**
  ```text
  start
  after comp
  del mid
  after run
  ```
- **Suggested Fix:** Either lower chained comparison intermediate values as true ANF temporaries in L2 (using ANF `Let` bindings and short-circuit `If` branches rather than walrus expressions), or emit an explicit `Delete` statement for the synthetic `_cmp*` name at the exit of the comparison expression.

---

### 2.3 [High / Lifetime Leak] Decorator Callables (`_dec0`) Leak in Synthetic Locals Until Scope Exit

- **Locations:** [`pipeline/l1/frontend.py:1763`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L1763) (`desugar_decorators`), [`pipeline/l2/lower.py:219-223`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/lower.py#L219-L223), and [`pipeline/l2/resolve.py:338`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/resolve.py#L338).
- **Problem:** `desugar_decorators` desugars `@dec\ndef f(): pass` by creating synthetic local assignment `_dec0 = dec; f = _dec0(f)`. No `del _dec0` is ever emitted. In CPython, decorator expressions live on the evaluation stack and are popped immediately when the decorated function/class definition completes. In Bella, `_dec0` remains stored in the function's local frame slots or the module dict, keeping callable objects and their closure references alive until function return or process termination.
- **Minimal Reproduction:**
  Save as `test_dec.py`:
  ```python
  class Probe:
      def __init__(self, name): self.name = name
      def __call__(self, fn): return fn
      def __del__(self): print("del", self.name)

  def outer():
      print("outer start")
      @Probe("my_dec")
      def g(): pass
      print("outer middle")

  outer()
  print("outer end")
  ```
- **Execution & Output:**
  ```sh
  uv run python test_dec.py
  uv run python pipeline/l2/run.py test_dec.py
  ```
  **CPython 3.15.2 Output:**
  ```text
  outer start
  del my_dec
  outer middle
  outer end
  ```
  **Bella eval2 Output:**
  ```text
  outer start
  outer middle
  del my_dec
  outer end
  ```
- **Suggested Fix:** In `pipeline/l1/frontend.py:1763` (`desugar_decorators`), emit `del _dec0` immediately following the decorated assignment `f = _dec0(f)`, or lower decorators directly in L2 as evaluation temporaries (`Let(d, expr); Let(fn, make_function); Let(wrapped, Call(d, (fn,))); Release(d)`).

---

### 2.4 [High / Frame Slot Tables] Synthetic Names and Annotation-Only Declarations Corrupt `co_varnames`

- **Locations:** [`pipeline/l2/resolve.py:159`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/resolve.py#L159), [`pipeline/l2/resolve.py:333-351`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/resolve.py#L333-L351) (`_slots`), and [`pipeline/l2/eval2.py:715-730`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/eval2.py#L715-L730) (`_check_slots`).
- **Problem:**
  1. `_slots` in `resolve.py` populates `s.varnames` from `s.order`, which includes all frontend synthetic names (`_cmp0`, `_dec0`, `_mgr0`, etc.). In CPython 3.15.2, `co_varnames` contains *only* parameters and user-defined local variables. For `def foo(a, b, c): return a < b < c`, CPython produces `co_varnames == ('a', 'b', 'c')`, while Bella produces `('a', 'b', 'c', '_cmp0')`! For `def outer(): @dec\n def g(): pass`, CPython produces `('g',)`, while Bella produces `('_dec0', 'g')`!
  2. Furthermore, for annotation-only statements (`z: int; a = 1; z = 2`), CPython allocates fast-local slots in *first-assignment/first-use* order (`co_varnames == ('a', 'z')`). `resolve.py:159` binds `z` at the declaration, causing Bella to output `co_varnames == ('z', 'a')`.
  3. Because frame cleanup releases locals in reverse slot order, modifying `co_varnames` alters the deallocation sequence of function locals on frame exit.
- **Minimal Reproduction:**
  Save as `test_varnames.py`:
  ```python
  import ast
  from pipeline.l1 import frontend
  from pipeline.l2 import resolve

  def foo(a, b, c): return a < b < c
  def outer():
      @dec
      def g(): pass

  print("CPython foo:", foo.__code__.co_varnames)
  print("CPython outer:", outer.__code__.co_varnames)

  src = """
  def foo(a, b, c): return a < b < c
  def outer():
      @dec
      def g(): pass
  """
  m = frontend.lower(ast.parse(src), "test.py")
  scopes = resolve.resolve(m)
  for node, s in scopes.by_node.items():
      if s.qualname in ("foo", "outer"):
          print(f"Bella {s.qualname}:", s.varnames)
  ```
- **Execution & Output:**
  ```sh
  uv run python test_varnames.py
  ```
  **Output:**
  ```text
  CPython foo: ('a', 'b', 'c')
  CPython outer: ('g',)
  Bella foo: ('a', 'b', 'c', '_cmp0')
  Bella outer: ('_dec0', 'g')
  ```
- **Suggested Fix:** Filter `s.synthetic` out of `s.varnames` in `_slots()`, and track separate passes for symbol classification vs. fast-local slot index assignment (following `Python/compile.c:compiler_enter_scope` and `allocate_fast_slot`).

---

### 2.5 [High / Closure Analysis] Intermediate `global` Declaration Fails to Block Closure Capture in `resolve.py`

- **Locations:** [`pipeline/l2/resolve.py:289-305`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/resolve.py#L289-L305) (`_analyze`).
- **Problem:** When an intermediate function declares `global x`, any inner function referencing `x` must resolve `x` globally (`GLOBAL_IMPLICIT`), ignoring enclosing function scopes. However, `_analyze` passes `bound` down through child scopes without masking out names declared `global` in intermediate scopes. When `inner` is analyzed, `x` is found in `bound` (from `outer`), causing `inner` to classify `x` as `FREE`. When `lower.py` then attempts to retrieve `middle`'s closure cell for `x`, it fails with `KeyError` because `middle` has no cell for `x`.
- **Minimal Reproduction:**
  Save as `test_global.py`:
  ```python
  x = 1
  def outer():
      x = 2
      def middle():
          global x
          def inner(): return x
          return inner
      return middle()

  print(outer()())
  ```
- **Execution & Output:**
  ```sh
  uv run python test_global.py
  uv run python pipeline/l2/run.py test_global.py
  ```
  **CPython 3.15.2 Output:**
  ```text
  1
  ```
  **Bella eval2 Output:**
  Crash during L2 lowering:
  ```text
  KeyError: "to-anf: outer.<locals>.middle has no cell for 'x' to pass on"
  ```
- **Suggested Fix:** In `pipeline/l2/resolve.py:290-302`, subtract `s.globals` from `newbound` when building the bound environment for child scopes:
  ```python
  newbound = (set(bound) if bound is not None else set()) - s.globals
  ```

---

### 2.6 [High / Lifetime Leak] Exception During `with` Entry (`__enter__`) Leaks Synthetic Context Managers

- **Location:** [`pipeline/l1/frontend.py:1443-1464`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py#L1443-L1464) (`_With._expand`).
- **Problem:** In `_With._expand`, the method lookups and calls for `__exit__` and `__enter__` (`_exit = __special__(mgr, '__exit__'); _enter = __special__(mgr, '__enter__'); _val = _enter()`) occur *before* the outer `try...finally` block. If `_enter()` raises an exception, control immediately exits the `with` statement without executing `finally: del _exit`. The synthetic local `_exit` (which holds a bound method referencing the manager object) remains permanently bound in frame locals, deferring deallocation of the manager object.
- **Minimal Reproduction:**
  Save as `test_with_fail.py`:
  ```python
  class C:
      def __enter__(self): raise ValueError("boom")
      def __exit__(self, *args): pass
      def __del__(self): print("del manager")

  try:
      with C():
          pass
  except ValueError:
      print("caught")
  print("after with")
  ```
- **Execution & Output:**
  ```sh
  uv run python test_with_fail.py
  uv run python pipeline/l2/run.py test_with_fail.py
  ```
  **CPython 3.15.2 Output:**
  ```text
  caught
  del manager
  after with
  ```
  **Bella eval2 Output:**
  ```text
  caught
  after with
  del manager
  ```
- **Suggested Fix:** Wrap the evaluation of `__enter__()` in an internal try-block whose exception handler explicitly deletes `_exit` and `_enter` before re-raising.

---

### 2.7 [High / Exception Unwinding] Implementation Helper Tracebacks in `eval2.py` Retain Operands Beyond Exception Handlers

- **Locations:** [`pipeline/l2/eval2.py:157, 161, 173, 494`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/eval2.py#L157).
- **Problem:** When an in-place arithmetic operation, unpack, or star-expansion fails in `_Runtime` helper functions (such as `_Runtime.inplace` or `_Runtime.unpack`), Python attaches a stack frame for `_Runtime` to the exception's `__traceback__`. The parameters `a` and `b` in that frame remain referenced as long as the exception traceback is alive. In CPython, `1 += O()` operates purely on the evaluation stack without helper frames; when `TypeError` is raised, `O()` is popped and decreffed *before* entering the `except` block. In Bella, `O()` survives until the exception object itself is cleared.
- **Minimal Reproduction:**
  Save as `test_inplace_leak.py`:
  ```python
  class O:
      def __del__(self): print("del operand")

  try:
      x = 1
      x += O()
  except TypeError:
      print("handler")
  print("after")
  ```
- **Execution & Output:**
  ```sh
  uv run python test_inplace_leak.py
  uv run python pipeline/l2/run.py test_inplace_leak.py
  ```
  **CPython 3.15.2 Output:**
  ```text
  del operand
  handler
  after
  ```
  **Bella eval2 Output:**
  ```text
  handler
  del operand
  after
  ```
- **Suggested Fix:** In `pipeline/l2/eval2.py`, catch exceptions inside `_Runtime` helper methods, clear local references (`a = None; b = None`), and re-raise with stripped tracebacks (`raise exc.with_traceback(None)`), or strip implementation frames during exception boundary translation.

---

### 2.8 [Medium / Drop Order] Augmented Assignment to Subscript Drops Index Before Result Instead of Vice-Versa

- **Locations:** [`pipeline/l2/lower.py:286-290`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/lower.py#L286-L290) and [`pipeline/l2/lifetimes.py:65-67`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/lifetimes.py#L65-L67).
- **Problem:** In CPython's `STORE_SUBSCR` opcode implementation (`Python/bytecodes.c:1684`), the stack operands are popped and decreffed in order:
  ```c
  sub = POP(); container = TOP(); v = SECOND();
  Py_DECREF(sub); Py_DECREF(container); Py_DECREF(v);
  ```
  Here `sub` is the subscript key, and `v` is the assigned result. Thus CPython decrefs `key` *before* `result`.
  In Bella `lower.py:286-290`:
  ```python
  o, k = self.expr(obj), self.expr(key)
  cur = self.let(G.GetItem(o, k))
  result = self.expr(L.BinOp(cur, op, val))
  self.emit(G.SetItem(o, k, result))
  ```
  `lifetimes.py:65` releases all dead temporaries after `SetItem` in descending numerical order (`sorted(releases, reverse=True)`). Because `result` was allocated after `k`, `result.n > k.n`, so Bella emits `Release(result)` *before* `Release(k)`!
- **Minimal Reproduction:**
  Save as `test_subscr.py`:
  ```python
  class Dead:
      def __init__(self, name): self.name = name
      def __add__(self, other): return Dead("res")
      def __del__(self): print("del", self.name)

  class Sink:
      def __getitem__(self, k): return Dead("cur")
      def __setitem__(self, k, v): pass

  print("--- begin ---")
  Sink()[Dead("key")] += Dead("val")
  print("--- end ---")
  ```
- **Execution & Output:**
  ```sh
  uv run python test_subscr.py
  uv run python pipeline/l2/run.py test_subscr.py
  ```
  **CPython 3.15.2 Output:**
  ```text
  --- begin ---
  del val
  del cur
  del key
  del res
  --- end ---
  ```
  **Bella eval2 Output:**
  ```text
  --- begin ---
  del val
  del cur
  del res
  del key
  --- end ---
  ```
- **Suggested Fix:** When multiple temporaries die at a `SetItem` operation in `lifetimes.py`, sort the releases to match CPython's operand stack pop order: release `key`, then `obj`, then `value`.

---

### 2.9 [Medium / Drop Order] Augmented Assignment to Attribute Drops Owner After Result Instead of Before Result

- **Locations:** [`pipeline/l2/lower.py:280-284`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/lower.py#L280-L284) and [`pipeline/l2/lifetimes.py:65-67`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/lifetimes.py#L65-L67).
- **Problem:** For `Sink().attr += Dead("val")`, CPython's compiler emits:
  `LOAD_ATTR`, `BINARY_OP`, `SWAP 2`, `STORE_ATTR`.
  In `STORE_ATTR`, `owner` is at the top of the stack and `value` is second. `owner` is popped and decreffed first. In Bella's ANF, `SetAttr(o, attr, result)` has `result` allocated with a higher temporary index than `o`. `lifetimes.py` releases `result` before `o`.
- **Minimal Reproduction:**
  Save as `test_attr.py`:
  ```python
  class Dead:
      def __init__(self, name): self.name = name
      def __add__(self, other): return Dead("res")
      def __del__(self): print("del", self.name)

  class Sink:
      def __init__(self): self.__dict__["attr"] = Dead("cur")
      def __setattr__(self, name, value): pass

  print("--- begin ---")
  Sink().attr += Dead("val")
  print("--- end ---")
  ```
- **Execution & Output:**
  ```sh
  uv run python test_attr.py
  uv run python pipeline/l2/run.py test_attr.py
  ```
  **CPython 3.15.2 Output:**
  ```text
  --- begin ---
  del val
  del cur
  del res
  --- end ---
  ```
  **Bella eval2 Output:**
  ```text
  --- begin ---
  del val
  del res
  del cur
  --- end ---
  ```
- **Suggested Fix:** Order dead temporary releases after `SetAttr` such that `owner` is released before `value`.

---

### 2.10 [Medium / Slot Deallocation] `__slots__` Deallocation Order in Reference Model and `object.hpp` Inverts CPython's Slot Release Order

- **Locations:** [`refmodel/objects.py:368-372`](file:///home/nathan/workspaces/nth/bella/refmodel/objects.py#L368-L372), [`runtime/include/bella/object.hpp:828-829`](file:///home/nathan/workspaces/nth/bella/runtime/include/bella/object.hpp#L828-L829), and [`docs/DECISIONS.md:541`](file:///home/nathan/workspaces/nth/bella/docs/DECISIONS.md#L541).
- **Problem:** `docs/DECISIONS.md:541`, `refmodel/objects.py`, and `runtime/include/bella/object.hpp` state that slots are released in declaration order. However, measuring CPython 3.15.2 (`typeobject.c:subtype_dealloc`) demonstrates that CPython iterates slots in reverse declaration order (or slot offset order). For `__slots__ = ('z', 'a')`, CPython releases `a` then `z`. Bella's model and C++ header release `z` then `a`.
- **Minimal Reproduction:**
  Save as `test_slots_death.py`:
  ```python
  class O:
      def __init__(self, n): self.n = n
      def __del__(self): print("del", self.n)

  class C:
      __slots__ = ('z', 'a')

  c = C()
  c.a = O('a')
  c.z = O('z')
  print("--- del c ---")
  del c
  print("--- done ---")
  ```
- **Execution & Output:**
  ```sh
  uv run python test_slots_death.py
  ```
  **CPython 3.15.2 Output:**
  ```text
  --- del c ---
  del a
  del z
  --- done ---
  ```
  **Bella Reference Model & `object.hpp` Output:**
  ```text
  --- del c ---
  del z
  del a
  --- done ---
  ```
- **Suggested Fix:** In `runtime/include/bella/object.hpp:828-829` and `refmodel/objects.py:368-372`, reverse the per-class slot iteration during deallocation:
  ```cpp
  for (ClassObject* c : obj->cls->mro) {
      auto slots = c->own_slot_names();
      for (auto it = slots.rbegin(); it != slots.rend(); ++it)
          decref(std::exchange(obj->field(*it), Obj{}));
  }
  ```

---

### 2.11 [Medium / Static Rejection] Valid Unreachable Source Code Triggers `wf2` Rejection (`unreachable statement Line`)

- **Locations:** [`pipeline/l2/lower.py:173`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/lower.py#L173) and [`pipeline/l2/wf.py:118-120`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/wf.py#L118-L120).
- **Problem:** In valid Python code, statements frequently appear after unconditional `return` or `raise` (dead code). `lower.py` emits `G.Line` and instructions for this dead code. In `wf2`, `self.block` checks statements sequentially. After a terminating statement (`Return`), `state` becomes `None`. When the next statement (such as `G.Line`) is encountered, line 119 fails with `self.fail(code, f"unreachable statement {type(s).__name__}")`, rejecting the program with exit code 70.
- **Minimal Reproduction:**
  Save as `test_dead_code.py`:
  ```python
  def f():
      return 1
      x = 2

  print(f())
  ```
- **Execution & Output:**
  ```sh
  uv run python test_dead_code.py
  uv run python pipeline/l2/run.py test_dead_code.py
  ```
  **CPython 3.15.2 Output:**
  ```text
  1
  ```
  **Bella eval2 Output:**
  Exits 70:
  ```text
  bella-eval2: unsupported: f: unreachable statement Line
  ```
- **Suggested Fix:** In `lower.py`, prune unreachable statements after unconditional control-flow terminators (`Return`, `Raise`, `Break`, `Continue`), or update `wf.py:118-120` to tolerate or drop unreachable statements instead of failing well-formedness.

---

### 2.12 [Medium / Namespace Hygiene] `locals()` / `vars()` Isolation in `eval2.py` Bypassed by Aliasing or Call Expansions

- **Location:** [`pipeline/l2/eval2.py:379-388`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/eval2.py#L379-L388).
- **Problem:** `eval2.py` intercepts calls to `locals()` by matching AST call expressions where the function is a direct `G.Builtin("locals")`. If a user program calls `locals` through an alias (`see = locals; see()`) or via argument unpacking (`locals(*())`), the call invokes host Python's `locals()`, exposing generated runtime internals (`_l2_R`, `_l2_codes`, `_l2_box`, and synthetic temporaries).
- **Minimal Reproduction:**
  Save as `test_locals_alias.py`:
  ```python
  def f():
      see = locals
      print("_l2_R" in see())
      print("_l2_R" in locals(*()))

  f()
  ```
- **Execution & Output:**
  ```sh
  uv run python test_locals_alias.py
  uv run python pipeline/l2/run.py test_locals_alias.py
  ```
  **CPython 3.15.2 Output:**
  ```text
  False
  False
  ```
  **Bella eval2 Output:**
  ```text
  True
  True
  ```
- **Suggested Fix:** Wrap built-in `locals` in the interpreter's builtins table with a sanitizing wrapper that filters out all identifiers starting with `_l2_` and any names present in `_hidden(code)`.

---

### 2.13 [Medium / Namespace Hygiene] Module-Level Shadowing of `BaseException` Breaks Generated `eval2` Exception Handlers

- **Locations:** [`pipeline/l2/eval2.py:468, 618, 625`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/eval2.py#L468).
- **Problem:** When generating exception handlers and unwinding code for host Python execution, `eval2` generates Python source containing bare `except BaseException:`. Because the generated module function executes with the program's module dict as globals, shadowing `BaseException` in program code (e.g. `BaseException = int`) causes host Python to attempt `except <int>:`, crashing with a `TypeError`.
- **Minimal Reproduction:**
  Save as `test_shadow_baseexc.py`:
  ```python
  BaseException = int

  try:
      1 / 0
  except ZeroDivisionError:
      print("caught")
  ```
- **Execution & Output:**
  ```sh
  uv run python test_shadow_baseexc.py
  uv run python pipeline/l2/run.py test_shadow_baseexc.py
  ```
  **CPython 3.15.2 Output:**
  ```text
  caught
  ```
  **Bella eval2 Output:**
  ```text
  TypeError: catching classes that do not inherit from BaseException is not allowed
  ```
- **Suggested Fix:** Reference the true `BaseException` through the runtime helper object (e.g. `except _l2_R.BaseException:`), which cannot be shadowed by program globals.

---

### 2.14 [Low / Verifier Soundness] `wf2` Verifies `finally` Against Pre-Try Live Set Even After Consuming `Return`

- **Location:** [`pipeline/l2/wf.py:235-258`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/wf.py#L235-L258) (`stmt(G.Try)`).
- **Problem:** In L2's contract, `Return(v)` consumes `v` so `v` is no longer live. However, for a `Try` statement whose `body` contains `Return(v)`, `wf2` checks `finalbody` using `entry` (the live set upon entering `try`), which still considers `v` live! If `finalbody` subsequently uses `v`, `wf2` erroneously accepts the code as well-formed even though `v` was already consumed on that path.
- **Minimal Reproduction:**
  Save as `test_wf_unsound.py`:
  ```python
  from pipeline.l2 import grammar as G
  from pipeline.l2.wf import check
  from pipeline.l2.eval2 import Interpreter

  v, f = G.Temp(1), G.Temp(2)
  fn = G.Code('f', 'f', 'function', (), (), (), (), (
      G.Let(v, G.Copy(G.Const('value'))),
      G.Try((G.Return(v),), finalbody=(
          G.Let(f, G.Load(G.NameRef('global', 'print'))),
          G.Do(G.Call(f, (v,))),
          G.Release(f),
      )),
  ))
  module = G.Module(G.Code('<module>', '<module>', 'module', (), (), (), (), (
      G.Let(f, G.MakeFunction(fn)),
      G.Do(G.Call(f, ())),
      G.Release(f),
  )))
  check(module)
  print("wf2 accepted invalid reuse of consumed temporary")
  ```
- **Execution & Output:**
  ```sh
  PYTHONPATH=. uv run python test_wf_unsound.py
  ```
  **Output:**
  ```text
  wf2 accepted invalid reuse of consumed temporary
  ```
- **Suggested Fix:** In `wf.py:252-258`, propagate the live sets across normal and abrupt termination exits into `finalbody`, verifying that temporaries consumed by a prior `Return` or `Raise` are not usable in `finalbody`.

---

## 3. Architecture & Specification Evaluation

### 3.1 ANF Lowering & Lifetimes Discipline
The introduction of A-Normal Form (ANF) with explicit `Let`, `Do`, and `Release` statements in `pipeline/l2/` is a solid compiler engineering milestone. It bridges the gap between high-level Python ASTs and C++ RAII destructors. The lifetime annotation pass (`lifetimes.py`) computes exact live ranges for temporaries, and the release-checking mode (`audit=True`) provides valuable verification.

However, the architecture currently suffers from a leak boundary: **frontend synthetic variables are treated as Python local variables rather than evaluation temporaries**. Because chained comparisons (`_cmp*`), decorators (`_dec*`), `with` statements (`_mgr*`, `_exit*`), and match statements create synthetic names via `_tmp()` that lower to named stores (`G.Store`), they escape the ANF lifetime analysis completely. In CPython, all of these are stack temporaries that die at expression or statement completion. Bella must extend ANF lowering to handle these expressions natively without synthetic local variables.

### 3.2 Reference Model & `object.hpp` Header
The single-threaded object model in `runtime/include/bella/object.hpp` accurately reflects the reference model in `refmodel/objects.py`. The tagged-word design (`Obj`), 16-byte object headers, split instance dicts with shared keys, and version-stamped inline caches closely match CPython's fast-path behavior.

The primary defect in `object.hpp` is **relying on borrowed pointers (`Obj`) for execution plans across arbitrary user-code invocation boundaries** (§2.1). In CPython, any object pointer that might be accessed during or after calling arbitrary Python code is explicitly increffed (e.g. `Py_INCREF(hook)`). Adopting this discipline in `execute()` will ensure memory safety under reentrant descriptor callbacks.

---

## 4. Prioritized Recommendations for Next Steps

1. **Fix Memory Safety in `object.hpp` (Critical):**
   - In [`runtime/include/bella/object.hpp:590-612`](file:///home/nathan/workspaces/nth/bella/runtime/include/bella/object.hpp#L590-L612), turn `plan.hook` and `plan.found` into counted references during `execute()` to eliminate the heap use-after-free vulnerability under reentrant descriptor deletion.
2. **Eliminate Synthetic Variable Lifetime Leaks (High):**
   - Modify [`pipeline/l1/frontend.py`](file:///home/nathan/workspaces/nth/bella/pipeline/l1/frontend.py) and [`pipeline/l2/lower.py`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/lower.py) to lower chained comparisons and decorators as genuine ANF evaluation temporaries rather than named locals.
   - For `with` expansions, guarantee cleanup of `_exit` and `_enter` when `__enter__()` raises.
3. **Align `co_varnames` with CPython 3.15.2 (High):**
   - In [`pipeline/l2/resolve.py:333-351`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/resolve.py#L333-L351), exclude synthetic names from `co_varnames`, and allocate fast-local slots in first-use/assignment order rather than declaration order.
   - In `pipeline/l2/resolve.py:289-305`, block closure capture across intermediate `global` declarations.
4. **Correct Operand Drop Orders to Match CPython (Medium):**
   - Adjust `lifetimes.py` release sorting for augmented assignments to subscripts (`STORE_SUBSCR`) and attributes (`STORE_ATTR`) to mirror CPython's opcode stack pop order.
   - In `object.hpp` and `refmodel/objects.py`, reverse slot deallocation order to match `subtype_dealloc`.
5. **Clean Up Helper Frames & Unreachable Code (Medium):**
   - Strip `_Runtime` helper frames on exceptions in `eval2.py` so operands are freed immediately.
   - Prune unreachable code in `lower.py` or relax `wf2` to allow dead code following unconditional terminators.
