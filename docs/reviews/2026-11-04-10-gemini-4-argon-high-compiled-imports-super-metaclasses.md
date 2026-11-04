# Bella Review (`e827a47..62d083b`, Compiled super(), Metaclasses, Subclasses, Imports & Build Caches)

- **Date:** 2026-11-04
- **Reviewer:** `gemini-4-argon-high`
- **Sequence:** 10
- **Commit Range Reviewed:** `e827a47..62d083b` (`e827a479b08607756ac2c6b96ae6f2195563f79b..62d083b5bf4c4cabac208c23f7f2aa95878d6801`)
- **Reviewed HEAD:** `62d083b5bf4c4cabac208c23f7f2aa95878d6801`
- **Reference Interpreter:** CPython 3.15.2 (pinned at `.venv/bin/python`)

---

## 1. Executive Summary

This review covers the 8 commits in range `e827a47..62d083b` on `main`, spanning:
1. **Remediation of RL-228 to RL-255** ([`d614f7c`](file:///home/nathan/workspaces/nth/bella/docs/reviews/review-log.md)): Exception C fields, `args` tuple, context cycle cutting via Floyd's algorithm, `_safe_string` reporting, single-lookup dict operations (`setdefault`, `pop`), list safety against mutating `__eq__`, unhashable type formatting, and descriptor protections.
2. **Step 3b Compiled `super()`** ([`cdbc5e0`](file:///home/nathan/workspaces/nth/bella/runtime/src/super.cpp), case C-3-32): Super object type, zero-argument intrinsic, `supercheck` validation, and MRO walking.
3. **Step 3b Metaclasses** ([`bd49090`](file:///home/nathan/workspaces/nth/bella/runtime/src/types.cpp), case C-3-33): Metaclasses derived from `type`, `_PyType_CalculateMetaclass` conflict resolution, `__abstractmethods__`, and special method dispatch.
4. **Subclasses of `dict` and `int`** ([`2e0b1d3`](file:///home/nathan/workspaces/nth/bella/runtime/src/types.cpp), [`5b56b5e`](file:///home/nathan/workspaces/nth/bella/runtime/src/types.cpp)): Unified representation of `dict` and `int` subclasses, `long_new_impl`, and `__slots__` validation.
5. **Compiled Imports** ([`3baa30e`](file:///home/nathan/workspaces/nth/bella/runtime/src/imports.cpp), cases C-8-01, C-8-04, C-8-10): Module resolution, relative import calculations, partial-initialization errors, `import *`, module `__getattr__`, `sys.exit`, and exit global clearance.
6. **Lazy Imports (PEP 810)** ([`23fb0ba`](file:///home/nathan/workspaces/nth/bella/runtime/src/imports.cpp), cases C-8-06, C-8-07): First-use resolution, pending submodules, `ImportCycleError`, and declaration tracking on resolution failures.
7. **Closed-World Compilation & Standard Library Path** ([`62d083b`](file:///home/nathan/workspaces/nth/bella/pipeline/closed_world.py), case C-8-05): Port of `importlib._bootstrap`, `types.SimpleNamespace`, compilation of reachable closures, and build caching.

### 1.1 Verification Status

The baseline test suite passes completely across all suites:
- `uv run pytest -q` passed 100% (532 passed).
- `pipeline/tests/test_compiled_imports.py` passed all 27 tests in 156.6s.
- `pipeline/tests/test_review_2026_11_03b.py` passed all 38 tests in 67.0s.
- `runtime/tests/test_prelude.py` passed all tests.

---

### 1.2 Summary of Findings

All findings were tested and reproduced against pinned CPython 3.15.2 (`.venv/bin/python`). Per the review constraints, clean refusals (`bella: not implemented`, exit 70) and known gaps (native modules not yet implemented, frozen path checked only under CPython, `'os' in sys.modules` False before import) are excluded from defects.

| Finding ID | Severity | Subsystem | Summary |
|---|---|---|---|
| **RL-256** | High | Compiler / Closed World | `pipeline/closed_world.py`: `_imports()` discards `"*"` and misses submodules declared in `__all__` for `from pkg import *`, causing runtime `AttributeError` (exit 1) |
| **RL-257** | Medium | Compiler / Closed World | `pipeline/closed_world.py`: Dotted frozen standard modules (`importlib.machinery`) resolve to local directory files instead of frozen modules |
| **RL-258** | Medium | Compiler / Closed World | `pipeline/closed_world.py`: Dynamic import scanner ignores `from importlib import import_module; import_module("...")` |
| **RL-259** | Medium | Pipeline / Build | `pipeline/build.py`: `build()` link cache key ignores `BELLA_KEEP_DEBUG`, returning stripped binaries when debug symbols are requested |
| **RL-260** | Low | Compiler / Backend | `pipeline/backend/cpp.py`: `_falls_through` diverged from `pipeline/l2/lower.py` by treating all `G.Loop` statements as falling through |

---

## 2. Technical Findings & Reproductions Against CPython 3.15.2

### 2.1 RL-256 [High / Spec Defect] `from pkg import *` Misses Submodules Declared in `__all__`

- **Location:** [`pipeline/closed_world.py:103`](file:///home/nathan/workspaces/nth/bella/pipeline/closed_world.py#L103)
- **Problem:** When scanning imports, `_imports` explicitly discards `"*"`:
  ```python
  elif isinstance(node, ast.ImportFrom):
      base = _resolve(node.module or "", package, node.level)
      if base is not None:
          out.append((base, tuple(a.name for a in node.names if a.name != "*")))
  ```
  Because `fromlist` is empty for `from pkg import *`, `scan()` never inspects `pkg/__init__.py`'s `__all__` to discover submodules. Consequently, submodules listed in `__all__` are never discovered, lowered, or compiled into the executable. At runtime, `import_star` in [`runtime/src/imports.cpp:491`](file:///home/nathan/workspaces/nth/bella/runtime/src/imports.cpp#L491) iterates over `__all__` and looks up attributes on the package object, which raises an uncaught `AttributeError` (exit 1), rather than a clean refusal (exit 70).
- **Reproduction:**
  ```python
  import tempfile, subprocess, sys
  from pathlib import Path
  from pipeline.build import build

  with tempfile.TemporaryDirectory() as tmp:
      tmppath = Path(tmp)
      pkg = tmppath / "mypkg"
      pkg.mkdir()
      (pkg / "__init__.py").write_text('__all__ = ["sub"]\n')
      (pkg / "sub.py").write_text("SUB_VAL = 42\n")
      main = tmppath / "main.py"
      main.write_text('from mypkg import *\nprint("sub:", sub.SUB_VAL)\n')

      ref = subprocess.run([sys.executable, "main.py"], cwd=tmp, capture_output=True, text=True)
      exe = build(main, str(main))
      got = subprocess.run([str(exe)], cwd=tmp, capture_output=True, text=True)
      print(f"CPython (exit {ref.returncode}): {ref.stdout.strip()}")
      print(f"Bella   (exit {got.returncode}): {got.stderr.strip()}")
  ```
- **CPython 3.15.2 vs Bella Output:**
  ```
  CPython (exit 0): sub: 42
  Bella   (exit 1): Traceback (most recent call last):
    File ".../main.py", line 1, in <module>
  AttributeError: module 'mypkg' has no attribute 'sub'
  ```
- **Suggested Fix:**
  In `pipeline/closed_world.py`, when a package has `from pkg import *`, evaluate or parse `__all__` from `pkg/__init__.py` (if it is a literal list/tuple of strings) and enqueue those names as reachable submodules for `find(f"{pkg}.{sub}")`.

---

### 2.2 RL-257 [Medium / Resolution Discrepancy] Dotted Frozen Submodules Resolve to Local User Files

- **Location:** [`pipeline/closed_world.py:132-136`](file:///home/nathan/workspaces/nth/bella/pipeline/closed_world.py#L132-L136)
- **Problem:** In `find_program_modules`:
  ```python
  parent, _, tail = name.rpartition(".")
  where: Path | None
  library_parent = False
  if parent:
      p = find(parent)
      library_parent = p is not None and p.path is not None and (p.origin is not None or p.path.is_relative_to(STDLIB))
      where = p.path.parent if p is not None and p.path is not None and p.package and not library_parent else None
  else:
      where = None if name in FIRST else root
  ```
  The condition `where = None if name in FIRST else root` only runs if `not parent`. When a module name contains dots (such as `importlib.machinery`, which is a member of `FIRST` and `FROZEN`), `parent` is `"importlib"`. If a user project happens to have a local `importlib/machinery.py`, `find("importlib.machinery")` checks `where / "machinery.py"` in the user's project rather than letting `FROZEN` take precedence.
- **Reproduction:**
  ```python
  import tempfile, subprocess, sys
  from pathlib import Path
  from pipeline.closed_world import find_program_modules

  with tempfile.TemporaryDirectory() as tmp:
      tmppath = Path(tmp)
      imp = tmppath / "importlib"
      imp.mkdir()
      (imp / "__init__.py").write_text("# empty\n")
      (imp / "machinery.py").write_text("USER_MACHINERY = True\n")
      main = tmppath / "main.py"
      main.write_text('import importlib.machinery\n')

      mods = find_program_modules(main)
      print([(m.name, m.frozen, str(m.path)) for m in mods])
  ```
- **Execution & Output:**
  ```python
  # CPython 3.15.2 prioritizes FrozenImporter for standard frozen modules:
  # attempts to import <frozen importlib.machinery>

  # Bella closed_world discovery:
  [('importlib', False, '.../importlib/__init__.py'), ('importlib.machinery', False, '.../importlib/machinery.py')]
  ```
  Bella treats `importlib.machinery` as a user source module (`frozen=False`), diverging from CPython where frozen standard library submodules take precedence.
- **Suggested Fix:**
  In `find()`, check if `name in FIRST` before checking `parent`, so that all frozen and native names in `FIRST` bypass user-directory lookups.

---

### 2.3 RL-258 [Medium / Scanner Gap] Dynamic Import Scanner Ignores `from importlib import import_module`

- **Location:** [`pipeline/closed_world.py:107-111`](file:///home/nathan/workspaces/nth/bella/pipeline/closed_world.py#L107-L111)
- **Problem:** In `_imports()`:
  ```python
  elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant) \
          and isinstance(node.args[0].value, str):
      f = node.func
      if (isinstance(f, ast.Name) and f.id == "__import__") or \
              (isinstance(f, ast.Attribute) and f.attr == "import_module" and isinstance(f.value, ast.Name)
               and f.value.id == "importlib"):
          out.append((node.args[0].value, ()))
  ```
  This only matches `__import__("...")` and `importlib.import_module("...")`. If a program imports the function directly via `from importlib import import_module` and calls `import_module("target")`, `f` is `ast.Name(id="import_module")`, which is ignored, leaving `"target"` uncompiled.
- **Reproduction:**
  ```python
  import tempfile
  from pathlib import Path
  from pipeline.closed_world import find_program_modules

  with tempfile.TemporaryDirectory() as tmp:
      tmppath = Path(tmp)
      (tmppath / "dyn.py").write_text("ANSWER = 42\n")
      main = tmppath / "main.py"
      main.write_text('from importlib import import_module\nm = import_module("dyn")\n')
      print("Found modules:", [m.name for m in find_program_modules(main)])
  ```
- **Output:**
  `Found modules: []` (misses `dyn`).
- **Suggested Fix:**
  Expand the check to also match `isinstance(f, ast.Name) and f.id == "import_module"`.

---

### 2.4 RL-259 [Medium / Cache Invalidation] `build()` Cache Key Omits `BELLA_KEEP_DEBUG`

- **Location:** [`pipeline/build.py:195-200`](file:///home/nathan/workspaces/nth/bella/pipeline/build.py#L195-L200)
- **Problem:** In `build()`:
  ```python
  key = _key(*(o.name.encode() for o in objs), lib.parent.name.encode())
  out = BUILD / f"{program.stem}-{key}"
  exe = out / program.stem
  if exe.exists():
      return exe
  out.mkdir(parents=True, exist_ok=True)
  tmp = str(exe) + f".{os.getpid()}.tmp"
  strip = [] if os.environ.get("BELLA_KEEP_DEBUG") else ["-Wl,--strip-debug"]
  proc = subprocess.run([cxx, f"-std={std}", *PROGRAM_FLAGS, *strip, *map(str, objs), str(lib), "-o", tmp], ...)
  ```
  The linker argument `strip` is determined by `BELLA_KEEP_DEBUG`, but `key` only hashes `objs` and `lib.parent.name`. Building without `BELLA_KEEP_DEBUG` populates the cache with a stripped binary; subsequently building with `BELLA_KEEP_DEBUG=1` hits the cache and returns the stripped binary without debug symbols.
- **Reproduction:**
  ```python
  import os, tempfile
  from pathlib import Path
  from pipeline.build import build

  with tempfile.TemporaryDirectory() as tmp:
      main = Path(tmp, "main.py")
      main.write_text("print('hello')\n")

      os.environ.pop("BELLA_KEEP_DEBUG", None)
      exe1 = build(main, str(main))
      sz1 = exe1.stat().st_size

      os.environ["BELLA_KEEP_DEBUG"] = "1"
      exe2 = build(main, str(main))
      sz2 = exe2.stat().st_size

      print(f"Stripped size: {sz1}, with BELLA_KEEP_DEBUG=1: {sz2}")
  ```
- **Output:**
  `Stripped size: 2152768, with BELLA_KEEP_DEBUG=1: 2152768` (identical cached stripped file).
- **Suggested Fix:**
  Include `os.environ.get("BELLA_KEEP_DEBUG", "").encode()` in the `_key(...)` calculation for the link step in `pipeline/build.py`.

---

### 2.5 RL-260 [Low / Emitter Divergence] `_falls_through` Diverged Between `l2/lower.py` and `backend/cpp.py`

- **Location:** [`pipeline/backend/cpp.py:780-781`](file:///home/nathan/workspaces/nth/bella/pipeline/backend/cpp.py#L780-L781) vs [`pipeline/l2/lower.py:38-40`](file:///home/nathan/workspaces/nth/bella/pipeline/l2/lower.py#L38-L40)
- **Problem:** Commit `62d083b` updated `_falls_through` in `pipeline/l2/lower.py` to inspect `G.Loop` via `_leaves_by(..., G.Break)` and `_leaves_by(..., G.EndLoop)` so that loops where every path returns or raises (such as `for ... else: raise`) are correctly recognized as not falling through. However, `pipeline/backend/cpp.py` was not updated:
  ```python
  if isinstance(last, G.Loop):
      return True  # a loop ends by break or end-loop, then falls through
  ```
  In [`backend/cpp.py:312`](file:///home/nathan/workspaces/nth/bella/pipeline/backend/cpp.py#L312), `if _falls_through(c.body): self.out.append(" return rt::none_ref();")` continues to treat all loops as falling through, emitting an unreachable `return rt::none_ref();` for functions whose bodies end in non-falling loops.
- **Suggested Fix:**
  Port the `_leaves_by` logic from `pipeline/l2/lower.py` into `pipeline/backend/cpp.py`'s `_falls_through` so loop control flow is handled consistently across both stages.

---

## 3. Systematic Verification of the 8 Focus Areas

### 3.1 Focus 1: Imports ([`3baa30e`](file:///home/nathan/workspaces/nth/bella/runtime/src/imports.cpp)) vs CPython `import.c` and `ceval.c`

1. **Resolution & Relative Imports:**
   - [`imports.cpp:125-165`](file:///home/nathan/workspaces/nth/bella/runtime/src/imports.cpp#L125-L165) (`resolve_name` / `absolute_name`) faithfully reproduces CPython's `_calc___package__` and `_resolve_name`.
   - Error messages match CPython 3.15.2:
     - Relative import without a known parent: `ImportError: attempted relative import with no known parent package`.
     - Relative import climbing past top level: `ImportError: attempted relative import beyond top-level package`.
2. **Partial-Initialization Errors:**
   - Circular imports during `from mod import attr` generate:
     `cannot import name 'attr' from partially initialized module 'mod' (most likely due to a circular import) (/path/to/mod.py)`
   - Module attribute lookup on a partially initialized module via [`imports.cpp:1086-1095`](file:///home/nathan/workspaces/nth/bella/runtime/src/imports.cpp#L1086-L1095) generates:
     `AttributeError: partially initialized module 'mod' from '/path/to/mod.py' has no attribute 'attr' (most likely due to a circular import)`
   - Both mirror CPython's `_PyImport_GetAbsName` and `module_getattro`.
3. **`import *`:**
   - Implemented via `import_star(v, locals)` ([`imports.cpp:491`](file:///home/nathan/workspaces/nth/bella/runtime/src/imports.cpp#L491)).
   - When `__all__` is defined, it reads via sequence indexing; if absent, it extracts keys from `__dict__` and filters out names with leading underscores.
4. **Module `__getattr__` and `__dir__`:**
   - Matches PEP 562: failed attribute lookups fall back to module-level `__getattr__`, and `dir(mod)` invokes module `__dir__`.
5. **`sys.exit` and Global Clearing Order ([`runtime/src/call.cpp:1518-1570`](file:///home/nathan/workspaces/nth/bella/runtime/src/call.cpp#L1518-L1570)):
   - `exit_status(exc)` handles `None` (0), boolean, integers, and non-integer payloads (which print to stderr and return 1).
   - Module shutdown in `clear_modules()` walks `sys.modules` in insertion order, setting attributes to `None` in insertion order while preserving `__builtins__`, matching CPython's `finalize_remove_modules`.

---

### 3.2 Focus 2: Prelude Bootstrap ([`runtime/prelude/bootstrap.py`](file:///home/nathan/workspaces/nth/bella/runtime/prelude/bootstrap.py))

1. **`bella:` Modifications:**
   - Multiprocessing locks are stubbed out for single-threaded compilation.
   - `_find_spec` redirects to `_bella_find` (the closed-world compiled registry).
   - `FrozenImporter.exec_module` delegates directly to compiled C++ function pointers via `_bella_exec`.
2. **`__spec__`, `__file__`, and Namespace Order:**
   - `new_module(name)` creates modules initialized with `['__name__', '__doc__', '__package__', '__loader__', '__spec__']`.
   - `_init_module_attrs` attaches `__file__` and `__path__` in the exact order observed in CPython 3.15.2.
   - `make_main` puts `__main__` into `sys.modules` with `__builtins__` and `__file__`, matching CPython's `globals()` dictionary layout.

---

### 3.3 Focus 3: Lazy Imports, PEP 810 ([`23fb0ba`](file:///home/nathan/workspaces/nth/bella/runtime/src/imports.cpp))

1. **First-Use Resolution:**
   - Placeholders are resolved on first global, class-dict, or module attribute access ([`imports.cpp:570-650`](file:///home/nathan/workspaces/nth/bella/runtime/src/imports.cpp#L570-L650), `lazy_resolve_impl`).
   - The resolved value replaces the placeholder in the target namespace, ensuring subsequent accesses avoid re-resolution.
2. **Pending Submodules:**
   - Dotted lazy imports (`lazy import pkg.sub.leaf`) bind the root package and register pending children in `pending_submodules()`. Accessing `pkg.sub` resolves the pending child on demand.
3. **`ImportCycleError`:**
   - Recursive lazy resolution is detected via `is_resolving`, raising:
     `ImportCycleError: cannot import name '...' (most likely due to a circular import)`
   - `ImportCycleError` derives from `ImportError`, matching CPython 3.15.2.
4. **Declaration Location on Errors:**
   - `lazy_add_exception_cause` records the declaration site:
     - If the exception already has a cause or context, it appends a note to `__notes__`:
       `lazy import of 'X' declared in <func> at <file>:<line>`
     - Otherwise, it sets an `ImportError` cause with a synthetic traceback pointing to the declaration line.

---

### 3.4 Focus 4: Closed-World Compilation ([`62d083b`](file:///home/nathan/workspaces/nth/bella/pipeline/closed_world.py))

- Module discovery correctly lowers and compiles all modules reachable from `__main__`.
- Namespace packages are explicitly detected as directories without `__init__.py` and returned with `path=None`, resulting in a clean exit 70 refusal (`bella: not implemented: importing '...', a namespace package`), which is by design.
- The 3 discrepancies identified are documented above as **RL-256**, **RL-257**, and **RL-258**.

---

### 3.5 Focus 5: Build Caches ([`pipeline/build.py`](file:///home/nathan/workspaces/nth/bella/pipeline/build.py))

- Lowering cache (`lowered_unit`): correctly hashed against module source, filename, namespace, and all compiler pipeline sources (`_pipeline_bytes()`).
- Compilation cache (`_object`): correctly hashed against unit C++ text, header files in `runtime/include`, compiler flags, compiler path, and C++ standard.
- Runtime library cache (`runtime_library`): correctly hashed against runtime sources, headers, preludes, and flags.
- Executable linking cache (`build`): omits `BELLA_KEEP_DEBUG` (**RL-259**).

---

### 3.6 Focus 6: Smaller Changes

1. **`_falls_through` in `pipeline/l2/lower.py`:**
   - Correctly uses `_leaves_by` to analyze whether loops terminate via `Break` or `EndLoop`.
   - Divergence with `backend/cpp.py` documented in **RL-260**.
2. **`header_macros()` in `pipeline/backend/cpp.py`:**
   - Invokes `g++ -dM -E` on `bella/runtime.hpp` and caches header macros (`ENOENT`, `errno`, `S_IFMT`).
   - Identifiers matching macros are escaped as `py...`, preventing C preprocessor macro expansion collisions.
3. **`runtime/src/str.cpp`:**
   - Complete implementation of 14 core string methods (`find`, `rfind`, `index`, `rindex`, `count`, `startswith`, `endswith`, `partition`, `rpartition`, `split`, `rsplit`, `strip`, `lstrip`, `rstrip`, `replace`).
   - Conforms strictly to CPython 3.15.2 slice index adjustments (`ADJUST_INDICES`), Unicode whitespace classification (`is_space`), short-circuiting on tuples in `startswith`/`endswith`, and Argument Clinic error messages.

---

### 3.7 Focus 7: `super()`, Metaclasses, dict & int Subclasses

1. **`super()` ([`runtime/src/super.cpp`](file:///home/nathan/workspaces/nth/bella/runtime/src/super.cpp)):**
   - Zero-argument `super()` intrinsic retrieves the `__class__` cell and first argument.
   - `supercheck` validates instance and subtype relationships, including proxy `__class__` attributes.
   - `super_getattr` walks the target class MRO and binds descriptors appropriately.
2. **Metaclasses ([`runtime/src/types.cpp:561-600`](file:///home/nathan/workspaces/nth/bella/runtime/src/types.cpp#L561-L600)):**
   - `_PyType_CalculateMetaclass` resolves base metaclasses; conflicts raise `TypeError: metaclass conflict...`.
   - Metaclasses with custom `__new__` take precedence.
   - `__abstractmethods__` prevents instantiation via `object.__new__` with sorted method names.
3. **`int` and `dict` Subclasses ([`runtime/src/types.cpp:480-515`](file:///home/nathan/workspaces/nth/bella/runtime/src/types.cpp#L480-L515)):**
   - Subtypes of `int` prohibit arbitrary `__slots__` with `TypeError: arbitrary __slots__ not supported for subtype of 'int'`, exactly matching CPython 3.15.2.
   - Subtypes of `dict` support `__slots__` and maintain instance dicts alongside dictionary entries.

---

### 3.8 Focus 8: Review Log Remediation (RL-228 to RL-255 in [`d614f7c`](file:///home/nathan/workspaces/nth/bella/docs/reviews/review-log.md))

All 27 remediations in commit `d614f7c` were verified against CPython 3.15.2 and confirmed passing in the test suite:
- `RL-228`: Exception handler line reporting verified.
- `RL-229`: Context cycle cutting using Floyd's algorithm verified in `C-3-31`.
- `RL-230`: `BaseException` native C fields (`args`, `__cause__`, `__context__`, `__traceback__`, `__suppress_context__`) verified.
- `RL-231`: `<exception str() failed>` safe reporting verified.
- `RL-232` to `RL-237`: Single-lookup dict operations (`setdefault`, `pop`), mutating callback protections, and iterators verified in `C-6-09`.
- `RL-239`, `RL-241` to `RL-243`: List operations (`remove`, `extend`, `count`) safe against mutating `__eq__` verified.
- `RL-248` to `RL-253`: Unhashable key formatting and dict update size-change detection verified.
- `RL-254`: Documented as an acknowledged open difference (`__suppress_context__` as `getset_descriptor`).
- `RL-255`: Refusal of unimplemented built-in base fields verified.
- All 38 tests in `pipeline/tests/test_review_2026_11_03b.py` passed in 67.0s.
