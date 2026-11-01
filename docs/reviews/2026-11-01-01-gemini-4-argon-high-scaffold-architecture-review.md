# Bella Architecture & Gate-0 Scaffold Review

- **Date**: 2026-11-01
- **Reviewer**: `gemini-4-argon-high`
- **Target**: `docs/` (v0.3 specification & design) and Gate-0 code scaffold (`refmodel/`, `pipeline/`, `runtime/`, `validation/`, `tools/`, `conformance/`)
- **Toolchain Verified**: CPython 3.14.8, GCC 16.2.1 (`-std=c++26`)

---

## 1. Evaluation of Approach & Potential

### 1.1 Architectural Strengths

1. **Boxed-first, coverage-before-speed phasing ([`docs/design.md` §3](../../docs/design.md))**:
   Proving the object model, dynamic tier (`ClassObject` / `InstanceObject`), and dialect semantics in a single-threaded boxed runtime in Phase 1 before introducing unboxed fast paths (Phase 2) and free-threaded concurrency (Phase 4) is the right way to de-risk a Python compiler.
2. **Executable specification & verification spine ([`docs/DECISIONS.md`](../../docs/DECISIONS.md))**:
   Pairing a clear dialect contract ([`docs/dialect-spec.md`](../../docs/dialect-spec.md)) and machine-readable deviation register ([`docs/deviations.toml`](../../docs/deviations.toml)) with:
   - an executable Python object-model oracle ([`refmodel/objects.py`](../../refmodel/objects.py)) and stateful Hypothesis differential testing against CPython ([`refmodel/oracle.py`](../../refmodel/oracle.py)),
   - an explicit nanopass [`PassSpec`](../../pipeline/passes/spec.py) obligation registry,
   - differential C++26 integer testing ([`runtime/tests/int_differential.py`](../../runtime/tests/int_differential.py)), and
   - SMT translation-validation certificates ([`validation/certificates.py`](../../validation/certificates.py))
   gives Bella a high-leverage verification foundation that has already caught real semantic bugs (Findings 1–3 in [`docs/DECISIONS.md`](../../docs/DECISIONS.md)).
3. **Strict separation of declared type, proven runtime class, and representation ([`docs/design.md` §2](../../docs/design.md))**:
   Treating type annotations as checked contracts rather than dispatch keys avoids Codon's silent semantic drift while preserving a clean path to mypyc/Codon-level speed on proven monomorphic loops.

### 1.2 Strategic & Architectural Risks to Address Early

1. **Phase-1 stdlib scope is very wide ([`manifest.toml`](../../manifest.toml))**:
   Compiling 68 root modules (~167 transitive modules in CPython 3.14.8, including `typing`, `dataclasses`, `enum`, `unittest`, `logging`, `argparse`, `decimal`, `datetime`, `re`, `json`, `hashlib`) requires almost the entire Python language (metaclasses, descriptors, `weakref`, generators, `contextvars`, `sys._getframe` callers in `warnings`/`unittest`/`typing`, and Python 3.14's new `annotationlib`) to work before Phase 1 closes.
   - **Recommendation**: Split Phase-1 stdlib closure into sub-milestones (e.g., Phase 1a: core language + data structures `collections`, `itertools`, `functools`, `math`, `heapq`, `bisect`; Phase 1b: metaprogramming-heavy modules `enum`, `dataclasses`, `typing`; Phase 1c: I/O, `re`, `json`, `datetime`, `decimal`, `logging`, `unittest`, `argparse`).
2. **Under-specified bridge between compile-time staging and runtime execution ([`docs/dialect-spec.md` §3.1](../../docs/dialect-spec.md))**:
   In v0.3, staging was narrowed to a *"compile-time dry run that yields code and layouts only; every definition-time expression executes at runtime in source order."*
   - **Gap**: Stdlib modules like `dataclasses`, `collections.namedtuple`, and `enum` synthesize methods or call `exec` *inside helper functions invoked by decorators or metaclasses at runtime*. If the decorator or metaclass body still executes at runtime in source order, what prevents it from hitting `exec` at runtime, and how does it bind the pre-compiled C++ function pointers emitted during staging?
   - **Recommendation**: Define the explicit lowering contract in [`docs/design.md`](../../docs/design.md): either (a) stage-time `exec` compiles a code artifact keyed by `(caller_site, source_hash)` and runtime `exec` in staged helpers looks up that pre-compiled function table (failing closed on cache miss), or (b) `@dataclass`, `namedtuple`, and `Enum` are lowered via compiler-recognized intrinsic hooks.

---

## 2. Concrete Bugs & Issues in the Code Scaffold

### 2.1 Object Model & Inline Cache (`refmodel/` & `docs/drafts/object.hpp.draft`)

#### Bug 2.1.1 — Unsound `CLASS_ATTR` cache when a non-descriptor class attribute's class later gains `__get__` (High, Reproduced `ModelError`)
- **Location**: [`Runtime._lookup_generic` (`refmodel/objects.py:304`)](../../refmodel/objects.py#L304)
- **Cause**: When `found` on `cls` is a `RefObject` without `__get__`, `_lookup_generic` installs `CacheEntry(cls, cls.version, name, CLASS_ATTR, found)` **without** recording `dep[0], dep[1]` (`found_cls`, `found_version`), contradicting [`docs/DECISIONS.md` line 63](../../docs/DECISIONS.md#L63) (*"Bella records `found_cls`/`found_version` on every entry kind"*).
- **Reproducer**:
  ```python
  from refmodel.objects import CallSite, ModelClass, RefObject, Runtime

  rt = Runtime()
  D = ModelClass("D", (), has_dict=True)
  d = RefObject(D)
  C = ModelClass("C", (), has_dict=True)
  C.set_attr("x", d)
  c = RefObject(C)
  site = CallSite()

  assert rt.getattr(c, "x", site) is d
  # Turn D into a non-data descriptor without mutating C:
  D.set_attr("__get__", lambda self_d, inst, owner=None: 99)
  rt.getattr(c, "x", site)  # raises ModelError: unsound cache for x: cached=<RefObject D> generic=99
  ```
- **Fix**: Pass `dep[0], dep[1]` to `CacheEntry(cls, cls.version, name, CLASS_ATTR, found, dep[0], dep[1])`.

#### Bug 2.1.2 — Unsound cache installation when `__get__` or `__getattr__` mutates the class during lookup (High, Reproduced `ModelError`)
- **Location**: [`Runtime._lookup_generic` (`refmodel/objects.py:289-310`)](../../refmodel/objects.py#L289-L310) and [`Runtime.getattr` (`refmodel/objects.py:350-368`)](../../refmodel/objects.py#L350-L368)
- **Cause**: `_lookup_generic` invokes `self._call_get(found, obj)` / `hook[0](obj, name)` *before* reading `cls.version` and `found.cls.version` to construct `CacheEntry`. If a lazy descriptor's `__get__` or a class's `__getattr__` mutates `cls` (e.g., `cls.set_attr(name, memoized_value)`), `cls.version` increments during the call, and `_lookup_generic` stamps the pre-mutation lookup decision (`NONDATA_DESC` or `GETATTR_HOOK`) with the **post-mutation** `cls.version`.
- **Reproducer**:
  ```python
  from refmodel.objects import CallSite, ModelClass, RefObject, Runtime

  rt = Runtime()
  C = ModelClass("C", (), has_dict=True)
  def lazy_getattr(self_obj, name):
      C.set_attr(name, 42)
      return 42
  C.set_attr("__getattr__", lazy_getattr)
  c = RefObject(C)
  site = CallSite()

  rt.getattr(c, "x", site)  # installs GETATTR_HOOK stamped with post-mutation C.version!
  C.set_attr("__getattr__", lambda self_obj, name: 999)
  # Now C.x is 42, so generic lookup returns 42 (CLASS_ATTR), or if C wasn't mutated again:
  ```
  Even simpler without a second mutation: if `__getattr__` returns `1` on the first call after setting `C.set_attr("x", 2)`, the first `rt.getattr(c, "x", site)` already fails inside `rt.getattr` because `rt.getattr` calls `_lookup_generic` (which mutates `C` and installs `GETATTR_HOOK` at the new version) and then immediately calls `_lookup_cached` (which hits `GETATTR_HOOK` instead of `CLASS_ATTR`).
- **Secondary bug in `Runtime.getattr`**: Calling `_lookup_generic` and then `_lookup_cached` on every cache hit executes effectful `__get__` / `__getattr__` hooks **twice** per read.
- **Fix**: Snapshot `cls_ver = cls.version` (and `found_ver = found.cls.version`) *before* invoking user hooks (`_call_get` or `__getattr__`), or only install the `CacheEntry` if `cls.version == cls_ver and found.cls.version == found_ver` after the hook returns.

#### Bug 2.1.3 — Unset `__slots__` and descriptors raising `AttributeError` do not fall through to `__getattr__` (Medium, Mismatch vs. CPython)
- **Location**: [`Runtime._lookup_generic` (`refmodel/objects.py:278-282`)](../../refmodel/objects.py#L278-L282)
- **Cause**: When a `SlotDescriptor` is `UNSET` (or when `self._call_get(found, obj)` raises `AttributeError`), `_lookup_generic` immediately raises `AttributeError(name)` instead of falling through to step 4 (`__getattr__`). In CPython (`slot_tp_getattr_hook`), any `AttributeError` raised by `PyObject_GenericGetAttr` invokes `__getattr__`.
- **Reproducer**:
  ```python
  class Real:
      __slots__ = ("s",)
      def __getattr__(self, name):
          return f"fallback:{name}"

  assert Real().s == "fallback:s"  # CPython returns "fallback:s"; refmodel raises AttributeError("s")
  ```

#### Bug 2.1.4 — ABA / Use-After-Free hazard in `ICacheEntry` with per-class `version` starting at `0` (High)
- **Location**: [`ICacheEntry` (`docs/drafts/object.hpp.draft:131-141`)](../../docs/drafts/object.hpp.draft#L131-L141) and [`ModelClass.__init__` (`refmodel/objects.py:99`)](../../refmodel/objects.py#L99)
- **Cause**: Per D-19 ([`docs/deviations.toml:120`](../../docs/deviations.toml#L120)), `ClassObject` instances are reference-counted and freed when unreachable, whereas `ICacheEntry` records live for the program lifetime and store raw `ClassObject* cls`, `ClassObject* found_cls`, and borrowed `const Object* found` pointers. Because `version` starts at `0` per class, if a dynamically created class is freed and a new `ClassObject` is allocated at the same address with `version == 0`, `(e->cls == cls && e->version == cls->version)` will match (ABA) and dereference a dangling `e->found` pointer.
- **Fix**: Allocate every class version (initial creation and every mutation) from a single global monotonic `uint64_t` counter (`next_class_version++`), never reusing version numbers across distinct `ClassObject` lifetimes.

#### Bug 2.1.5 — Incomplete `InstanceDict` fast-path comment in `object.hpp.draft` and `docs/design.md` (Low)
- **Location**: [`docs/drafts/object.hpp.draft:147`](../../docs/drafts/object.hpp.draft#L147) and [`docs/design.md:208`](../../docs/design.md#L208)
- **Cause**: Both state `InstanceDict : the dict pointer is non-null; probe by the cached hash` without noting that a dict-probe miss must fall back to the slow path (class attribute / `__getattr__` / `AttributeError`), as [`Runtime._lookup_cached` (`refmodel/objects.py:330-333`)](../../refmodel/objects.py#L330-L333) properly does.

---

### 2.2 Compiler Pipeline (`pipeline/l1/` Frontend, `wf1`, `eval1`, and C++ Backend)

#### Bug 2.2.1 — Chained comparisons fail `wf1` everywhere except top-level `ExprStmt` (High, Reproduced `WellFormednessError`)
- **Location**: [`_bound_in` (`pipeline/l1/wf.py:34-57`)](../../pipeline/l1/wf.py#L34-L57) and [`_local_names` (`pipeline/l1/eval1.py:82-86`)](../../pipeline/l1/eval1.py#L82-L86)
- **Cause**: `_ChainedCompare` in [`pipeline/l1/frontend.py:31-48`](../../pipeline/l1/frontend.py#L31-L48) rewrites `a < b < c` using `__bind__("_cmp0", b)`. However, `_bound_in` in `wf.py` only calls `_walrus(s.value, out)` when `s` is an `L.ExprStmt`! Any chained comparison inside `if`, `while`, `return`, `assign`, or `assert` fails `wf.check`:
- **Reproducer**:
  ```python
  from pipeline.l1.frontend import lower_to_l1
  from pipeline.l1.wf import check

  check(lower_to_l1("x = 2\nif 1 < x < 3:\n    y = 1\n"))
  # raises WellFormednessError: name '_cmp0' is bound nowhere in its scope chain
  ```
- **Additional issue**: Binding `_cmp0` as a scope variable in `eval1` pollutes module `globals()` and function `locals()`, and [`pipeline/backend/emit_cpp.py`](../../pipeline/backend/emit_cpp.py) has no handling for `__bind__` at all.

#### Bug 2.2.2 — List comprehensions inside functions hoist `_lcN` to module scope, breaking access to function locals/parameters (High, Reproduced `WellFormednessError`)
- **Location**: [`_hoist` (`pipeline/l1/frontend.py:160-173`)](../../pipeline/l1/frontend.py#L160-L173)
- **Cause**: In `_hoist`, `s = tr.visit(s)` runs `ast.NodeTransformer.generic_visit` over the entire `FunctionDef` (and nested `If`/`While`/`For`/`Try`) *before* recursing into `s.body`. Consequently, any comprehension inside a function is hoisted to **module level** instead of inside the function body, losing lexical access to function parameters and locals. Nested comprehensions `[[x + y for y in r] for x in r]` similarly hoist the inner helper as a sibling of the outer helper rather than inside it, losing `x`.
- **Reproducer**:
  ```python
  from pipeline.l1.frontend import lower_to_l1
  from pipeline.l1.wf import check

  check(lower_to_l1("def f(y):\n    return [x + y for x in range(3)]\n"))
  # raises WellFormednessError: name 'y' is bound nowhere in its scope chain
  ```

#### Bug 2.2.3 — Right-to-left evaluation order in C++ binary operations and comparisons (High, Violates C-2-01, Reproduced)
- **Location**: [`Emitter.expr` (`pipeline/backend/emit_cpp.py:110-123`)](../../pipeline/backend/emit_cpp.py#L110-L123)
- **Cause**: Finding 3 in [`docs/DECISIONS.md:66-67`](../../docs/DECISIONS.md#L66-L67) noted that GCC 16 evaluates function arguments right-to-left and fixed `Emitter._call`. However, `L.BinOp` and `L.Compare` still emit inline expressions (`bella::int_floordiv({l}, {r})`, `({l} + {r})`, `({l} < {r})`). In C++, overloaded operators on `bella::Int` (`operator+`, `operator-`, `operator*`, `operator<`, etc.) and helper calls (`bella::int_floordiv`, `bella::int_mod`, `bella::int_pow`) are **function calls**, whose argument evaluation order remains unspecified in C++26; GCC 16 evaluates them right-to-left.
- **Reproducer**:
  ```python
  # Compiling and running via pipeline.slice:
  def f(x: int) -> int:
      print(x)
      return x
  print(f(10) + f(3))
  # CPython prints: 10, 3, 13
  # Bella C++ binary prints: 3, 10, 13
  ```
- **Fix**: Sequence `L.BinOp` and `L.Compare` operands into `_tN` temporaries whenever either operand is non-trivial (or unconditionally in L1 codegen).

#### Bug 2.2.4 — Post-loop variable value in `Emitter.for_range` is off by one (Medium, Reproduced Mismatch vs. CPython)
- **Location**: [`Emitter.for_range` (`pipeline/backend/emit_cpp.py:252-270`)](../../pipeline/backend/emit_cpp.py#L252-L270)
- **Cause**: `for_range` emits `for (i = start; i < stop; i = i + step)`. After `for i in range(5): pass`, CPython leaves `i == 4`, whereas the emitted C++ increments `i` to `5` before exiting the loop (and on an empty `range(0)`, C++ sets `i = 0` whereas Python leaves `i` unchanged; if the loop body reassigns `i`, C++ corrupts the loop counter).
- **Fix**: Drive the C++ loop with a fresh hidden induction variable `_idxN` and assign `i = _idxN` at the top of the loop body.

#### Bug 2.2.5 — Additional `frontend.py`, `eval1.py`, `emit_cpp.py`, and `int.hpp` Bugs
1. **Nested `global` / `nonlocal` declarations silently dropped ([`pipeline/l1/frontend.py:326-346`](../../pipeline/l1/frontend.py#L326-L346))**:
   `_ToL1.function` only inspects direct children (`for s in f.body:`) for `ast.Global` and `ast.Nonlocal`, while `_ToL1.stmt` turns any `global`/`nonlocal` inside an `if`/`for`/`try`/`with` block into `L.Pass`.
2. **`with` desugaring bypasses the descriptor protocol ([`pipeline/l1/frontend.py:79-80`](../../pipeline/l1/frontend.py#L79-L80))**:
   `_With._expand` emits `type(_mgr).__enter__(_mgr)` instead of binding the special method via the descriptor protocol (`type(_mgr).__enter__.__get__(_mgr, type(_mgr))()`), breaking context managers whose `__enter__`/`__exit__` is a `@staticmethod`, `@classmethod`, or custom descriptor.
3. **Unbound enclosing cell variables fall through to globals in `eval1` ([`pipeline/l1/eval1.py:113-118`](../../pipeline/l1/eval1.py#L113-L118))**:
   In `Interpreter.load`, when an inner function reads a free variable `name` that belongs to an enclosing function (`name in s.locals_`) but is not yet bound in `s.vars`, the loop continues walking up `s.parent` to module globals instead of raising `NameError`.
4. **`del` on unbound local raises `NameError` instead of `UnboundLocalError`, and `del` on `nonlocal` fails ([`pipeline/l1/eval1.py:138-143`](../../pipeline/l1/eval1.py#L138-L143))**:
   `Interpreter.delete` checks `scope.vars` directly without checking `scope.locals_` or walking `scope.parent` for `nonlocal` variables.
5. **`Emitter.function` ignores `f.globals` ([`pipeline/backend/emit_cpp.py:273-291`](../../pipeline/backend/emit_cpp.py#L273-L291))**:
   Functions that assign to a `global` variable declare a local `bella::Int` shadowing the module-level variable.
6. **`int_lshift` / `int_rshift` exception type ([`runtime/include/bella/int.hpp:95-108`](../../runtime/include/bella/int.hpp#L95-L108))**:
   Throws `std::domain_error("negative shift count")`, whereas Python raises `ValueError`.
7. **Missing D-10 compile-time check ([`docs/deviations.toml:66-70`](../../docs/deviations.toml#L66-L70))**:
   `return`, `break`, or `continue` exiting a `finally` block is specified as a compile-time error in D-10, but neither `frontend.py` nor `wf.py` checks for it.

---

### 2.3 Translation Validation (`validation/certificates.py`)

#### Bug 2.3.1 — False assumption that interval arithmetic is exact over boxes causes `AssertionError` crashes (High, Reproduced)
- **Location**: [`check_intervals` (`validation/certificates.py:127-140`)](../../validation/certificates.py#L127-L140)
- **Cause**: `check_intervals` comments `# intervals are exact over boxes for this grammar, so a corner witness must exist` and raises `AssertionError("interval said overflow but no corner witnessed it")` if no corner of the box overflows.
  This is mathematically false whenever a variable appears more than once in `expr` (the classic **interval dependency problem**):
  1. **False-positive overflow + crash**:
     ```python
     from validation.certificates import CertKind, NarrowCert, Sub, Var, check_intervals
     cert = NarrowCert(expr=Sub(Var("x"), Var("x")), env={"x": (-100, 100)}, bits=8, kind=CertKind.INTERVAL)
     check_intervals(cert)  # interval is [-200, 200], corners x=±100 both evaluate to 0 -> AssertionError!
     ```
  2. **Interior extremum + crash**:
     ```python
     from validation.certificates import CertKind, Lit, Mul, NarrowCert, Sub, Var, check_intervals
     # 130 - x*x on x in [-10, 10] with bits=8 ([-128, 127]):
     cert = NarrowCert(expr=Sub(Lit(130), Mul(Var("x"), Var("x"))), env={"x": (-10, 10)}, bits=8, kind=CertKind.INTERVAL)
     check_intervals(cert)  # true overflow at interior point x=0 (val=130), corners x=±10 evaluate to 30 -> AssertionError!
     ```
- **Fix**: Interval arithmetic is a sound **over-approximation**:
  - If `lo_b <= lo and hi <= hi_b`, the certificate is soundly `SAFE`.
  - If a corner witness overflows, it is `UNSAFE` with that witness.
  - Otherwise, `check_intervals` is inconclusive (either delegate to `check_smt(cert)` to find an interior witness or prove safety, or return an inconclusive status rather than asserting).

---

### 2.4 Stdlib Closure, Conformance Corpus, and Tooling/CI

#### Bug 2.4.1 — `tools/closure.py` fails with 23 problems on the pinned Python 3.14.8, including `traceback` → `codeop` (High)
- Running `python3 tools/closure.py` on the workspace's pinned **Python 3.14.8** fails (`exit 1`) with 23 problems:
  1. **Hard spec conflict (`traceback` → `codeop`)**: In CPython 3.14.8, `Lib/traceback.py:9` unconditionally executes `import codeop`. `traceback` is a `[P1]` compiled module while `codeop` is `[X]` excluded under E-08, producing `codeop: excluded module reached as required (via traceback:eager:9)`.
  2. **Unclassified Python 3.14 stdlib modules**: `annotationlib`, `_py_warnings`, `pathlib._os`, `compression.zstd`, `_zstd`, `_hmac`, and `fcntl` are reached from Phase-1 roots and missing from [`manifest.toml`](../../manifest.toml).
  3. **Classifier precedence bug in [`_Scanner._cls` (`tools/closure.py:256-259`)](../../tools/closure.py#L256-L259)**: `if conditional: return CONDITIONAL` takes precedence over `LAZY`, and `If`/`While`/`Match` set `conditional=True`. Consequently, an unguarded `import foo` inside an `if` branch inside a function (e.g. `calendar` → `argparse`, ` inspect` → `ast`, `zipfile` → `zlib`) is misclassified as `CONDITIONAL` (which expects an `[omissions]` entry with an `except ImportError` handler) instead of `LAZY` (`[lazy_unsupported]`).
  4. **Transitive reachability gap in [`_static_reach` (`tools/closure.py:443-445`)](../../tools/closure.py#L443-L445)**: Reachability from `omitted_targets` only follows `{EAGER, DYNAMIC}` edges, missing `CONDITIONAL`/`LAZY` edges inside omitted packages (such as `shutil` → `compression.zstd` → `_zstd`).

#### Bug 2.4.2 — Conformance cases that violate the dialect specification (Medium)
1. **[`conformance/cases/C-8-02_builtins_fallthrough.py:17-20`](../../conformance/cases/C-8-02_builtins_fallthrough.py#L17-L20)**:
   Tests `print(undefined_name)` where `undefined_name` is bound nowhere in the file, expecting a runtime `NameError`. Under [`docs/dialect-spec.md` §3 line 159](../../docs/dialect-spec.md#L159) (*"A bare name bound nowhere in its scope chain and not a builtin is a compile-time `NameError`"*), this file is a **compile-time error** (`wf1` rejects it). To test runtime `NameError` on a module global in the Bella dialect, the test should bind and `del` the global before calling `missing()`.
2. **[`conformance/cases/C-3-05_descriptor_class_mutation.py:7`](../../conformance/cases/C-3-05_descriptor_class_mutation.py#L7) and [`conformance/cases/C-3-08_rich_comparison_returns_object.py:6`](../../conformance/cases/C-3-08_rich_comparison_returns_object.py#L6)**:
   Both import and use `typing.Any`, violating [`docs/design.md` §2 line 30](../../docs/design.md#L30) (*"`Any` is rejected (`disallow_any_explicit = true`); dynamically typed values are spelled `object`"*).

#### Bug 2.4.3 — `mypy`, `ruff`, and `Dockerfile` Configuration Issues (Medium)
1. **`.venv/bin/mypy` currently reports 44 errors across 7 files**, including:
   - [`pipeline/backend/emit_cpp.py:307-308`](../../pipeline/backend/emit_cpp.py#L307-L308): `for fn in prog.functions:` reuses the parameter `fn: str` for `FunctionDef` objects.
   - [`tools/closure.py:479-481`](../../tools/closure.py#L479-L481): `seen: set[str] = set()` is later reassigned `seen = set()` holding `tuple[str, int]` pairs.
   - [`tools/tests/test_closure.py:49-72`](../../tools/tests/test_closure.py#L49-L72): assertions compare `tuple[str, str]` against `dict[str, list[int]]` (only passing because `not in` on disjoint types returns `True`).
2. **`.venv/bin/ruff check .` currently reports 18 errors**, including `B023` loop-variable capture warnings in [`refmodel/oracle.py:230-231`](../../refmodel/oracle.py#L230-L231) and missing per-file ignores for `conformance/cases/`.
3. **[`Dockerfile:9`](../../Dockerfile#L9) vs. [`pyproject.toml:26`](../../pyproject.toml#L26) version conflict**:
   `Dockerfile` sets `ARG UV_VERSION=0.9`, while `pyproject.toml` sets `required-version = "==0.13.6"`. Building the container image with `uv 0.9` will fail `uv`'s required-version check.

---

## 3. Recommended Next Steps (Ordered Action Plan)

1. **Make `ruff`, `mypy`, and `Dockerfile` cleanly pass**:
   - Update [`Makefile`](../../Makefile) to use `.venv/bin/python` (or `uv run`), fix the 44 `mypy` and 18 `ruff` diagnostics, replace `Any` with `object` in `C-3-05` and `C-3-08`, update `C-8-02` to comply with static name resolution, and bump `UV_VERSION=0.13.6` in [`Dockerfile`](../../Dockerfile).
2. **Fix `refmodel/objects.py` cache soundness bugs and complete Gate-0 Task 2 (`runtime/include/bella/object.hpp`)**:
   - Record `found_cls`/`found_version` on `CLASS_ATTR`; snapshot class versions *before* invoking `__get__`/`__getattr__`; fall through to `__getattr__` on unset slots / descriptor `AttributeError`; and switch `ClassObject::version` to a global monotonic `uint64_t` counter.
   - Expand [`refmodel/oracle.py`](../../refmodel/oracle.py) stateful Hypothesis rules to cover mutating non-descriptor classes into descriptors and mutating classes inside `__get__`/`__getattr__`.
   - Promote [`docs/drafts/object.hpp.draft`](../../docs/drafts/object.hpp.draft) to `runtime/include/bella/object.hpp` with the global monotonic version counter and a C++ GoogleTest / differential harness driven by `refmodel/oracle.py` traces.
3. **Fix `pipeline/l1/` and `emit_cpp.py` correctness bugs before expanding Gate-0 Task 4**:
   - Fix `_hoist` in [`pipeline/l1/frontend.py`](../../pipeline/l1/frontend.py) so comprehensions hoist into their enclosing function/comprehension body rather than module level.
   - Fix `_bound_in` in [`pipeline/l1/wf.py`](../../pipeline/l1/wf.py) and `_local_names` in [`pipeline/l1/eval1.py`](../../pipeline/l1/eval1.py) to visit `__bind__` in all statement expressions (or lower chained comparisons via statement-level temporaries).
   - Sequence `L.BinOp` and `L.Compare` operands in [`pipeline/backend/emit_cpp.py`](../../pipeline/backend/emit_cpp.py) to guarantee left-to-right evaluation, and use a hidden loop counter in `Emitter.for_range`.
   - Fix `int_lshift` / `int_rshift` in [`runtime/include/bella/int.hpp`](../../runtime/include/bella/int.hpp) to map negative shift counts to `ValueError`.
4. **Fix `check_intervals` in [`validation/certificates.py`](../../validation/certificates.py) (Gate-0 Task 5)**:
   - Remove the false corner-witness assertion on multi-occurrence variables; treat interval arithmetic as a fast sound safe-filter that delegates inconclusive overflow candidates to `check_smt`.
5. **Close the Python 3.14.8 stdlib manifest & classifier gaps (Gate-0 Task 3)**:
   - Fix `LAZY` vs. `CONDITIONAL` precedence and transitive omitted-target reachability in [`tools/closure.py`](../../tools/closure.py).
   - Classify the 3.14 internal modules (`annotationlib`, `_py_warnings`, `pathlib._os`, `compression.zstd`, `_zstd`, `_hmac`, `fcntl`) in [`manifest.toml`](../../manifest.toml) and resolve `traceback` → `codeop` (via an omission stub or internal `codeop` shim).
6. **Document the staging-to-runtime lowering contract in [`docs/design.md`](../../docs/design.md)**:
   - Specify how code and layouts produced during the compile-time staging dry run are linked into runtime decorator/metaclass execution for `@dataclass`, `namedtuple`, and `Enum`.
