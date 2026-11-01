# Bella Gate-0 Task 1 (Stdlib Closure on CPython 3.15.2) & Review-Log Fixes Review

- **Date**: 2026-11-01
- **Reviewer**: `gemini-4-argon-high`
- **Target**: Commit `b40ef2d` (Gate 0 Task 1: Phase-1 manifest closure on CPython 3.15.2, spec v0.6) and commits `f56d495`–`bcd7fe7` (3.15.2 pin, review-log fixes RL-01..RL-51, decisions D-1..D-4)
- **Toolchain Verified**: CPython 3.15.2 (pinned `python-build-standalone` via `.venv`), GCC 16.2.1 (`-std=c++26`)

---

## 1. Overall Evaluation

### 1.1 Verification of Task 1 and Review-Log Fixes

All claims in the delivery note were verified directly against `b40ef2d`:
- **`make closure`**: Exits `0` on CPython 3.15.2 (`authoritative: true`) with **174 modules** (`112 compiled`, `36 mapped`, `19 core`, `7 shim`), `0` errors, `0` notes, and byte-for-byte identical [`closure.lock.json`](../../closure.lock.json) output with stdlib-relative paths (`no machine paths`).
- **Full check suite (`make check` with `.venv/bin` on `PATH`)**:
  - `ruff check .` and `mypy`: clean across all 37 source files (`0` errors).
  - `pytest`: 59/59 passed, plus `refmodel.selftest` (3,000 operations across 50 worlds, 65,395 cache hits, 0 mismatches).
  - `conformance/harness.py verify`: 28/28 authoritative expectations reproduced on CPython 3.15.2.
  - `tools/probe_toolchain.py`: 17/20 C++26 probes pass on GCC 16.2.
  - `pipeline.slice`: 4/4 as expected (3 PASS, 1 XFAIL on `fact_big.py`).
  - `runtime/tests/int_differential.py`: 2,000/2,000 cases match CPython 3.15.2.
- **Quality of the `0d92b51`–`bcd7fe7` fixes**:
  - Splitting [`Runtime.getattr`](../../refmodel/objects.py#L343-L465) into pure plan selection (`_plan_generic` / `_plan_cached`) followed by single execution (`_execute`), and keying inline caches by a single process-wide 64-bit monotonic [`VersionCounter`](../../refmodel/objects.py#L75-L98) (D-1, C-3-12) with `recreate_class` in [`refmodel/oracle.py`](../../refmodel/oracle.py#L254-L275), is an unusually clean resolution of RL-16 through RL-23.
  - Adding definite-assignment checking and left-to-right operand sequencing in [`pipeline/backend/emit_cpp.py`](../../pipeline/backend/emit_cpp.py#L102-L195), hygienic synthetic temporaries in [`pipeline/l1/frontend.py`](../../pipeline/l1/frontend.py#L20-L30) and [`pipeline/l1/eval1.py`](../../pipeline/l1/eval1.py#L64), and three-valued (`PROVED` / `REFUTED` / `UNKNOWN`) fail-closed verdicts in [`validation/certificates.py`](../../validation/certificates.py#L72-L93) thoroughly resolve the compiler and validator bugs from the first review round.
  - The new `[dynamic]` table in [`manifest.toml`](../../manifest.toml#L140-L155) proved its value immediately by catching the 10 Phase-1 codec modules (`encodings.utf_8`, etc.) that neither static import scanning nor startup-subtracted runtime observation could see.

---

## 2. Review of the Four Highlighted Decisions in Task 1

### 2.1 `annotationlib` as a Shim vs. Runtime Execution of `dataclasses`, `typing`, `functools`, and `inspect` (High — Needs Narrowing Before Phase 1b)

[`manifest.toml:108`](../../manifest.toml#L108) and [`docs/dialect-spec.md` §7](../../docs/dialect-spec.md#L166) specify the `annotationlib` shim as:
> `Format, ForwardRef (without evaluate) and type_repr; get_annotations, call_annotate_function and the FORWARDREF and STRING formats raise with the milestone name, since annotations are [P2+] (spec section 3) and the real formats rebuild functions from __code__ (E-02, E-07)`

Scanning the 112 compiled Phase-1 stdlib modules in CPython 3.15.2 shows four places where compiled Phase-1 code calls those refused APIs **at runtime** (because per [`docs/dialect-spec.md` §8 line 175](../../docs/dialect-spec.md#L175), every definition-time decorator and metaclass still executes at runtime in source order):

1. **`inspect.py:147` (`from annotationlib import get_annotations`)**:
   `inspect` is in `[phase1].compiled` and executes `from annotationlib import get_annotations` unconditionally at module top level. The `annotationlib` shim must therefore export `get_annotations` (as well as `annotations_to_string` and `get_annotate_from_class_namespace`) as importable symbols.
2. **`dataclasses.py:1057, 1413` (`annotationlib.get_annotations(cls, format=annotationlib.Format.FORWARDREF)`)**:
   When `@dataclass` executes at runtime, `_process_class` calls `annotationlib.get_annotations(cls, format=Format.FORWARDREF)`. If `get_annotations` or `Format.FORWARDREF` unconditionally raises the `[P2+]` milestone refusal, `@dataclass` will fail at runtime unless `_process_class` is replaced at runtime by the staging mechanism.
3. **`typing.py:3054-3056, 3208-3210` (`NamedTuple` and `TypedDict` metaclasses)**:
   When `class P(NamedTuple):` or `class T(TypedDict):` executes at runtime, `_NamedTupleMeta.__new__` and `_TypedDictMeta.__new__` call `annotationlib.get_annotate_from_class_namespace(ns)` and `annotationlib.call_annotate_function(annotate, Format.FORWARDREF)`.
4. **`functools.py:970-971` (`@singledispatch` registration by type annotation)**:
   `singledispatch.register` calls `get_type_hints(func, format=Format.FORWARDREF)` → `annotationlib.get_annotations(func, format=Format.FORWARDREF)`.

**Why `__code__` is not actually needed for resolved annotations in 3.15.2**:
In CPython 3.15.2's `Lib/annotationlib.py`:
- `get_annotations(obj, format=Format.FORWARDREF)` (lines 1007–1015) *first* reads `obj.__annotations__` (which calls `obj.__annotate__(Format.VALUE)`), and **only** falls back to `call_annotate_function(annotate, Format.FORWARDREF)` if evaluating `__annotations__` raised an exception (such as `NameError` on an unresolved forward reference)!
- Furthermore, `call_annotate_function(annotate, format)` (lines 755–758) *first* calls `annotate(format)` directly, and **only** touches `annotate.__code__` if `annotate(format)` raises `NotImplementedError`.

**Recommendation**:
Have the `annotationlib` shim provide `Format`, `ForwardRef` (without `evaluate`), `type_repr`, `annotations_to_string`, `get_annotate_from_class_namespace`, `call_annotate_function`, and `get_annotations`, where:
- For `Format.VALUE` and `Format.FORWARDREF` (when annotations resolve without `NameError`) and `Format.STRING` (via `annotations_to_string`), the shim calls `annotate(Format.VALUE)` / reads `__annotations__` directly (no `__code__` needed).
- Alternatively, compiler-generated `__annotate__(format)` functions can handle `Format.VALUE`, `Format.FORWARDREF`, and `Format.STRING` directly from the AST at compile time.
- Only `eval_str=True`, `ForwardRef.evaluate()`, or an annotation whose runtime evaluation raises `NameError` and would require `__code__` re-execution with `_StringifierDict` needs to raise the `[P2+]` refusal.

---

### 2.2 `hashlib` and `hmac` Without OpenSSL (`_hashlib` and `_hmac` Omitted)

- **Omitting `_hashlib` (OpenSSL, Apache-2.0)** is the right call for the Phase-1 license rule, and recording `hashlib.pbkdf2_hmac` and `hashlib.scrypt` as absent in Phase 1 matches a CPython built `--without-openssl`.
- **Distinguishing `_hmac` from `_hashlib`**:
  Unlike `_hashlib` (which links OpenSSL), `_hmac` in CPython 3.14/3.15 (`Modules/_hmacmodule.c`) is CPython's built-in **HACL\*** implementation (MIT-licensed verified C code — the exact same source as `_md5`, `_sha1`, `_sha2`, and `_sha3`, which [`manifest.toml`](../../manifest.toml#L89-L91) already lists under `mapped`).
- **Two observable differences vs. the pinned CPython 3.15.2 oracle when `_hashlib` and `_hmac` are both omitted**:
  1. **`hmac.digest` with `memoryview` keys**: In the pinned CPython 3.15.2 oracle (where `_hashlib` and `_hmac` are present), `hmac.digest(memoryview(b"k"), b"a", "sha256")` succeeds because the C implementations accept any buffer-protocol object. When both `_hashlib` and `_hmac` are omitted, `hmac.digest` falls back to `hmac._compute_digest_fallback` (`Lib/hmac.py:242`), which explicitly checks `if not isinstance(key, (bytes, bytearray)): raise TypeError(...)`.
  2. **`hashlib.algorithms_available`**: In the pinned CPython 3.15.2 build, `hashlib.algorithms_available` includes OpenSSL-provided names (`ripemd160`, `sm3`, `sha512_224`, `sha512_256`), whereas without `_hashlib` it equals `hashlib.algorithms_guaranteed`.
- **Recommendation**: Either map `_hmac` alongside `_md5`/`_sha1`/`_sha2`/`_sha3` (which restores `hmac.digest` buffer compatibility and speed at no licensing cost), or record both points in [`docs/deviations.toml`](../../docs/deviations.toml) / [`docs/dialect-spec.md` §7](../../docs/dialect-spec.md#L166).

---

### 2.3 `Path.as_uri`, `Path.from_uri`, and `ast.unparse` in `[lazy_unsupported]`

- Refusing whole functions listed in `unsupported_functions` (`ast.unparse`, `base64.main`, `logging.Logger.__reduce__`, `pathlib.Path.as_uri`, `pathlib.Path.from_uri`, `shutil._make_tarball`, `shutil._make_zipfile`, `shutil._unpack_tarfile`, `shutil._unpack_zipfile`) on every path through the function keeps Phase-1 API support a static build-time property.
- **Note on `PurePath.as_uri` vs. `Path.as_uri` in CPython 3.15.2**:
  In `Lib/pathlib/__init__.py`, `Path.as_uri` (line 1465) imports `from urllib.request import pathname2url` (`[P2+]`) and is refused, whereas `PurePath.as_uri` (line 522, deprecated in 3.14 for removal in 3.19) imports `from urllib.parse import quote_from_bytes` (`[P1]`) and is **not** in `unsupported_functions`. If `Path.as_uri` is `[P2+]`, consider whether `PurePath.as_uri` should stay allowed (since `urllib.parse` is in Phase 1) or also be marked `[P2+]` for consistency.
- **Note on `shutil._make_tarball` / `_make_zipfile` function attributes**:
  `Lib/shutil.py:1132-1133` executes `_make_tarball.supports_root_dir = True` and `_make_zipfile.supports_root_dir = True` at module import time. When the compiler emits stubs for `unsupported_functions`, it should replace only the function body (raising the milestone-naming error when called) so the function object itself still exists at module init and accepts attribute assignments.

---

### 2.4 `traceback._find_incompatible_extension_module` in `[replaced]` and the `codeop` Shim

- **Sound**: `TracebackException.__init__` calls `_find_incompatible_extension_module` whenever it formats a `ModuleNotFoundError`. Putting it in `[lazy_unsupported]` would have broken formatting *any* `ModuleNotFoundError` via `traceback`. Replacing it to return `None` in `[replaced]` (and shimming `codeop.compile_command` with an uncatchable `E-08` refusal so `suppress(Exception)` in `_find_keyword_typos` cannot silently swallow it) is well-reasoned and backed by measurement on 3.15.2.

---

## 3. Concrete Bugs & Issues Found in the Updated Code

### 3.1 BFS Visit-Order Bug in `compute_closure` Skips `LAZY` and `OPTIONAL` Checks When Target Was Already Reached (`Medium`, Reproduced)

- **Location**: [`compute_closure` (`tools/closure.py:845-860`)](../../tools/closure.py#L845-L860)
- **Cause**:
  ```python
  for e in info.edges:
      if e.target in infos:
          continue
  ```
  `if e.target in infos: continue` runs *before* the `elif e.cls == LAZY:` and `elif e.cls == OPTIONAL:` branches that populate `lazy_outside` and `optional_outside`.
  If a module `X` outside `manifest.supported` (e.g., an `excluded` or `missing-from-manifest` module) is reached first by module `A` (so `X` is added to `infos`), and a later module `B` has a `LAZY` or `OPTIONAL` import of `X`:
  1. `B`'s edge to `X` is skipped at `if e.target in infos: continue` and never added to `lazy_outside["B"]` or `optional_outside["B"]`.
  2. If `B` properly declared `X` in `[lazy_unsupported]`, lines 928–932 report a **bogus error**:
     `[lazy_unsupported] lists X for B, which B does not import inside a function`!
  3. If `B` forgot to declare `X` in `[lazy_unsupported]` or `[omissions]`, the missing declaration in `B` goes unreported.
- **Reproducer**:
  ```python
  # Module 'a' eagerly imports 'outside' and 'b'; module 'b' lazily imports 'outside' inside f():
  # compute_closure reports:
  #   1. outside [source]: required but not in manifest (via a:eager:1)
  #   2. [lazy_unsupported] lists outside for b, which b does not import inside a function  <-- FALSE
  ```
- **Fix**: Record `lazy_outside` and `optional_outside` whenever `e.target not in manifest.supported` *before* checking `if e.target in infos: continue` for queue insertion.

---

### 3.2 `from posix import *` in `os.py` Clobbers `name = 'posix'` in `_ModuleEnv`, Turning `if name == 'nt':` into `LAZY` Instead of `DEAD` (`Medium`, Reproduced)

- **Location**: [`_ModuleEnv._stmt` (`tools/closure.py:455-457`)](../../tools/closure.py#L455-L457) and [`compute_closure` (`tools/closure.py:916-918`)](../../tools/closure.py#L916-L918)
- **Cause**:
  1. In CPython 3.15.2's `Lib/os.py:52-55`:
     ```python
     if 'posix' in _names:
         name = 'posix'
         linesep = '\n'
         from posix import *
     ```
     Because `from posix import *` immediately follows `name = 'posix'`, `_ModuleEnv._stmt` resets every public name in `self.env` (including `name`) to `UNKNOWN`.
  2. Consequently, at `Lib/os.py:1169` (`if name == 'nt': ... def add_dll_directory(path): import nt`), `_Scanner` evaluates `name == 'nt'` as `UNKNOWN` instead of `False`!
  3. In [`closure.lock.json`](../../closure.lock.json), `('os', 'nt', 1197, 'add_dll_directory')` is therefore recorded with `"cls": "lazy"` instead of `"cls": "dead"`.
  4. The only reason `make closure` did not fail on `os:1197` is [`tools/closure.py:916-918`](../../tools/closure.py#L916-L918):
     ```python
     kind, _ = classify(t)
     if kind == "missing":
         continue
     ```
     Because `nt` has `kind == "missing"` on Linux, `compute_closure` silently ignores the `LAZY` import of `nt`, so `os.add_dll_directory` is neither dead nor listed in `unsupported_functions`!
- **Why `if kind == "missing": continue` in `lazy_outside` is a problem**:
  For `optional_outside` (`try: import msvcrt except ImportError:`), skipping `kind == "missing"` is benign because the `except ImportError` handler catches it at runtime. For `lazy_outside` (an *unguarded* `import` inside a function), if the function is not under a false platform guard (`DEAD`), calling that function at runtime would fail with `ModuleNotFoundError` instead of being refused by `[lazy_unsupported]`.
- **Fix**:
  - In `os.py` (or `_ModuleEnv`), preserve `name` when `"os.name"` is in `platform.facts` (or do not let `from posix import *` clobber `name` when `posix` is a known builtin module that does not export `name`), so `if name == 'nt':` in `os.py:1169` is properly classified as `DEAD`.
  - Remove `if kind == "missing": continue` from the `lazy_outside` loop (`tools/closure.py:916-918`) so unguarded function-level imports of missing modules cannot slip past `[lazy_unsupported]`.

---

### 3.3 `omitted_closure` Includes Transitive Imports of Function-Local Omissions (`pickle`), Masking Runtime Observations (`Low/Medium`)

- **Location**: [`compute_closure` (`tools/closure.py:865-876`)](../../tools/closure.py#L865-L876)
- **Cause**:
  `omitted_targets = {t for ts in manifest.omissions.values() for t in ts}` includes `tracemalloc` (which `_py_warnings` only imports *inside a function* `_formatwarnmsg_impl` at line 174, never at module import time).
  `_static_reach(omitted_targets, FOLLOWED_CLASSES, manifest.platform) - manifest.supported` then follows `tracemalloc`'s top-level `import pickle` and puts `'pickle'` and `'_compat_pickle'` into `omitted_closure`.
  As a result, line 875 (`if mod in infos or mod in omitted_closure: continue`) would ignore `pickle` if any Phase-1 root ever loaded `pickle` at import time.
- **Better mechanism**:
  In [`observe_runtime_imports`](../../tools/closure.py#L764-L790), set `sys.modules[om] = None` for every omitted target before importing the roots in the subprocess. Verified on CPython 3.15.2: all 68 roots import cleanly with `sys.modules[om] = None`, which forces `decimal`, `datetime`, `hashlib`, `hmac`, `uuid`, `shutil`, and `pathlib._os` to execute their actual Phase-1 pure-Python fallback branches during dynamic observation, eliminating the need for `omitted_closure` heuristics altogether.

---

### 3.4 Minor Scanner & Lockfile Edge Cases in `tools/closure.py` (`Low`)

1. **Dotted module names in `_maybe_dynamic` (`tools/closure.py:684-692`) and `[dynamic]` (`tools/closure.py:837`)**:
   Unlike `_add_dotted` (which adds edges for every parent package `a`, `a.b`, `a.b.c`), `_maybe_dynamic` and `[dynamic]` only emit an edge to the leaf target `t`. If a dotted dynamic target's parent package is not separately imported, the parent package will not be added to `infos`.
2. **Literal `import_module("...")` inside a function ignores `ctx.lazy` (`tools/closure.py:691`)**:
   `cls = DEAD if ctx.dead else OPTIONAL if ctx.optional else DYNAMIC` classifies a literal `importlib.import_module("x")` inside a function as `DYNAMIC` (unconditionally followed at module level) rather than `LAZY` (eligible for `[lazy_unsupported]`).
3. **`unsupported_functions` when a lazy import sits in a nested helper function (`tools/closure.py:964-973`)**:
   If a public function `f()` contains a nested helper `def _ inner(): import outside`, `e.func` is `"f.<locals>._inner"`, so `unsupported_functions` records `"f.<locals>._inner"` rather than `"f"`. (None of the 9 unsupported functions in Phase 1 are nested helpers, so current lock output is unaffected, but normalizing `e.func.partition(".<locals>.")[0]` or refusing the outer callable will be needed when the runtime consumes `unsupported_functions`.)

---

### 3.5 `Makefile` `lint` Target Does Not Use `$(PY)` (`Low`, Reproduced)

- **Location**: [`Makefile:54`](../../Makefile#L54)
- **Cause**: `Makefile` defines `PY ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)` (RL-30) and uses `$(PY)` in every target *except* `lint`:
  ```makefile
  lint:
  	ruff check . && mypy
  ```
  On a developer host where `.venv/bin` is not prepended to `PATH`, `make closure`, `make test`, `make verify`, `make probes`, `make slice`, and `make int-test` all succeed via `$(PY)`, while `make lint` and `make check` fail with `ruff: command not found`.
- **Fix**: Change line 54 to `$(PY) -m ruff check . && $(PY) -m mypy`.

---

## 4. Recommended Next Steps

1. **Apply the small fixes in `tools/closure.py` and `Makefile`**:
   - Move `if e.target in infos: continue` below `lazy_outside` / `optional_outside` recording in [`compute_closure`](../../tools/closure.py#L845-L860).
   - Preserve `os.name` across `from posix import *` in [`_ModuleEnv`](../../tools/closure.py#L455-L457) so `os.add_dll_directory` (`os.py:1197`) is classified as `DEAD` in `closure.lock.json`, and remove `if kind == "missing": continue` from `lazy_outside` (`tools/closure.py:916-918`).
   - Block omitted modules (`sys.modules[om] = None`) in [`observe_runtime_imports`](../../tools/closure.py#L764-L790) so import-time observation exercises the actual Phase-1 fallback paths.
   - Use `$(PY) -m ruff check . && $(PY) -m mypy` in [`Makefile:54`](../../Makefile#L54).
2. **Refine the `annotationlib` shim specification before Phase 1b (Gate 0 Task 5)**:
   - Include `get_annotations`, `call_annotate_function`, `get_annotate_from_class_namespace`, and `annotations_to_string` in the `annotationlib` shim (backed by `__annotations__` / `Format.VALUE` evaluation without `__code__`) so `import inspect` and runtime execution of `@dataclass`, `NamedTuple`, `TypedDict`, and `@singledispatch.register` work without hitting the `[P2+]` refusal when annotations are already in scope.
3. **Decide whether to map `_hmac` (HACL\*, MIT) alongside `_sha2`/`_sha3`**:
   - Either add `_hmac` to `[phase1].mapped` (preserving `hmac.digest` on `memoryview` keys) or document the pure-Python `hmac.digest` `bytes`/`bytearray` restriction and `hashlib.algorithms_available` in [`docs/deviations.toml`](../../docs/deviations.toml).
4. **Proceed to Gate 0 Tasks 2–5 as ordered in [`TODO.md`](../../TODO.md)**:
   - Grow the 3.15.2 conformance corpus (PEP 810 `lazy import`, `frozendict`, `sentinel`, `__class__` assignment, generator `close()`/`throw()`).
   - Add explicit retain/release lifetime points in L2 and finaliser traces in `eval1` / `refmodel`, then promote `runtime/include/bella/object.hpp`.
   - Prototype the staging-to-runtime contract on `@dataclass` and `namedtuple` (Gate 0 Task 5).
