# Bella Staging Revision Review (`b838bc5..d0bec20`, S-1 to S-5 & RL-88..RL-112)

- **Date:** 2026-11-02
- **Reviewer:** `gemini-4-argon-high`
- **Sequence:** 05
- **Commit Range Reviewed:** `b838bc5..d0bec20` (`d0bec205cbb5bbe63d5426ed6ecc4e902eae70bd`)

---

## 1. Executive Summary

Commit `d0bec20` applies decisions **S-1 through S-5** and resolves all 24 findings from the first staging review round (`RL-88` through `RL-112`):

1. **Second `__annotate__` Entry Point Generator (Decision S-1):** [`pipeline/staging/annotations.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/annotations.py) and [`pipeline/staging/annotate_rt.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/annotate_rt.py) replace the build-time `STRING` table with a compiler-generated second entry point `__annotate__(format, _g, _c)` per `__annotate__` and PEP 695 `evaluate` function. Every generated evaluator is verified at build time against CPython 3.15.2's own bytecode loads (`_cpython_loads`) and dynamically against CPython's `STRING` and `FORWARDREF` substitute environments (`_agree`).
2. **Staged `compile()` and Line-Number-Free Call-Site Keys (`RL-94`..`RL-100`, `RL-109`, `RL-112`):** [`pipeline/staging/dryrun.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/dryrun.py) and [`pipeline/staging/boot/sitecustomize.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/boot/sitecustomize.py) now stage `builtins.compile()` outcomes (code object or raised exception), key staged operations by `(site, operation, text)` without line numbers, check `__future__` flags and optimization levels at runtime, discover sibling and PEP 810 `lazy import` program modules, and enforce `[refused]` (`gettext:c2py`), `[unstaged]` (`annotationlib:ForwardRef.__forward_code__`), `[lazy_unsupported]`, and `inspect._signature_from_function` refusals.
3. **Closure & Corpus Updates (`RL-98`, S-1..S-4):** `_ast_unparse` is promoted to `compiled` in [`manifest.toml`](file:///home/nathan/workspaces/nth/bella/manifest.toml) (`176` modules total; `113` compiled), [`tools/closure.py`](file:///home/nathan/workspaces/nth/bella/tools/closure.py) scans Python shims in `runtime/shims/`, and five new conformance cases (`C-3-22`..`C-3-24`, `C-7-16`..`C-7-17`) plus [`pipeline/tests/test_staging.py`](file:///home/nathan/workspaces/nth/bella/pipeline/tests/test_staging.py)'s 13 differential `REVIEW_PROBES` lock in the fixes.

**Overall Assessment:** The S-1 architecture (generating a second `__annotate__(format, _g, _c)` entry point verified both statically and dynamically against CPython at build time) is a major improvement over build-time string tables: it handles unbound forward references (`Format.FORWARDREF`), closures, class scopes, and conditional annotations without exposing `__code__` at runtime.

However, differential testing of the new S-1 generator (`annotations.py`), runtime helpers (`annotate_rt.py`), and caching/replay plumbing (`run.py`, `sitecustomize.py`, `scan.py`) against CPython 3.15.2 uncovered **seven concrete bugs** (including silent wrong outputs under `Format.FORWARDREF`, false `[P2+]` refusals on valid `[P1]` annotations, a build-time `SyntaxError` crash on PEP 696 starred `TypeVarTuple` defaults, and an artefact cache collision across working directories). Section 3 details each finding with a minimal reproduction and fix.

---

## 2. Verification of `RL-88`..`RL-112` and S-1..S-5

All 24 items in [`docs/reviews/review-log.md`](file:///home/nathan/workspaces/nth/bella/docs/reviews/review-log.md) (`RL-88`..`RL-112`) were verified:

- **`RL-88`..`RL-92` (`A5-1`..`A5-4`, D-20):** Operation kind (`exec`/`eval`/`compile`), `__future__` flags, and `sys.flags.optimize` are recorded and checked; `sources` hashes all loaded files; `_audit` checks only the immediate caller frame against `_LOADER`; `judge_corpus` fails on non-zero exit or missing summary; D-20 lists only observed differences.
- **`RL-94`..`RL-97` (`3.1`):** Staging `compile()` and keying by `module:qualname` without line numbers resolves quoted forward references in `typing` forms, `NamedTuple` with string annotations, `NamedTuple`/`TypedDict` under `from __future__ import annotations`, and invalid forward-reference `SyntaxError` preservation.
- **`RL-98`..`RL-99` (`3.2`):** `_ast_unparse` is in `manifest.toml` `[phase1].compiled`, `tools/closure.py` scans `runtime/shims/<name>.py`, and `ForwardRef.__resolved_str__` in `runtime/shims/annotationlib.py` deep-copies `self.__ast_node__` instead of calling `ast.parse` at runtime.
- **`RL-100`..`RL-105` (`3.3`–`3.4`):** The entry script is imported under `ENTRY = "__bella_entry__"` and mapped to `"__main__"` in `_module_of` and `_loader_exec`; `--entry` is included in `wanted`; `_program_modules` discovers sibling modules and resolves PEP 810 lazy imports.
- **`RL-106`..`RL-112` (`3.5`):** S-1's second entry point handles `Format.FORWARDREF` and `Format.STRING` for functions, classes, modules, and PEP 695 `type` aliases; hand-written `VALUE`-only annotate functions fall back to `Format.VALUE`; keyword `field_names=` in `namedtuple` and `exec("...", closure=...)` `TypeError` match CPython.

---

## 3. Technical Findings & Bugs in `b838bc5..d0bec20`

### 3.1 [High / Wrong Output] [`annotate_rt.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/annotate_rt.py): PEP 810 `lazy import` bindings (`types.LazyImportType`) are not resolved by `load_global` / `load_deref`, returning raw `<lazy_import>` objects under `Format.FORWARDREF`

- **Location:** [`pipeline/staging/annotate_rt.py:30-84`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/annotate_rt.py#L30-L84) (`_optional_item`, `load_global`, `load_deref`, `load_dict_or_global`, `load_dict_or_deref`)
- **Mechanism:**
  When `annotationlib.get_annotations(obj, format=Format.FORWARDREF)` runs on a function or `@dataclass` whose annotations contain both an unbound forward reference and a PEP 810 `lazy from mod import Name` binding (with the unbound reference evaluated before `Name`):
  1. `get_annotations` first tries `obj.__annotations__` (`Format.VALUE`), which raises `NameError` on the unbound name before reaching `Name`. Thus `Name` in `obj.__globals__` remains an un-reified `types.LazyImportType` (`<lazy_import '...'>`).
  2. `call_annotate_function` ([`runtime/shims/annotationlib.py:851`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py#L851)) builds `namespace = {**annotate.__builtins__, **annotate.__globals__}`, which copies the raw `LazyImportType` into `globals` (`_StringifierDict`).
  3. When CPython 3.15.2 executes `annotate.__code__`, its `LOAD_GLOBAL`, `LOAD_NAME`, `LOAD_FROM_DICT_OR_GLOBALS`, `LOAD_DEREF`, and `LOAD_FROM_DICT_OR_DEREF` opcodes in `Python/bytecodes.c` check `PyLazyImport_CheckExact` and call `_PyLazyImport_Resolve` (`value.resolve()`), returning the resolved object (or, if the lazy import fails, raising `ImportError` so Pass 2 falls back to `ForwardRef.evaluate(format=Format.FORWARDREF)` at [`runtime/shims/annotationlib.py:214-223`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py#L214-L223), which catches the exception and returns `ForwardRef('Name')`).
  4. In [`annotate_rt.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/annotate_rt.py), `load_global`, `load_deref`, `load_dict_or_global`, and `load_dict_or_deref` return `mapping[key]` / `cell.cell_contents` directly without resolving `LazyImportType`.
- **Reproduction:**
  ```python
  import annotationlib
  lazy from decimal import Decimal
  lazy from nonexistent_mod import Missing

  def f(z: Later, x: Decimal, y: list[Decimal]) -> None: ...
  def g(x: Missing, y: Later) -> None: ...

  ann_f = annotationlib.get_annotations(f, format=annotationlib.Format.FORWARDREF)
  print("x:", type(ann_f["x"]), repr(ann_f["x"]))
  print("y:", type(ann_f["y"].__args__[0]), repr(ann_f["y"]))
  ann_g = annotationlib.get_annotations(g, format=annotationlib.Format.FORWARDREF)
  print("g.x:", repr(ann_g["x"]))
  ```
  - **CPython 3.15.2:**
    ```text
    x: <class 'type'> <class 'decimal.Decimal'>
    y: <class 'type'> list[decimal.Decimal]
    g.x: ForwardRef('Missing', owner=<function g at ...>)
    ```
  - **Staging Replay (`d0bec20`):**
    ```text
    x: <class 'lazy_import'> <lazy_import 'decimal.Decimal'>
    y: <class 'lazy_import'> list[<lazy_import 'decimal.Decimal'>]
    g.x: <lazy_import 'nonexistent_mod.Missing'>
    ```
- **Recommendation:** In [`pipeline/staging/annotate_rt.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/annotate_rt.py), obtain `_LazyImportType` (or check `getattr(value, "resolve", None)` on `type(value).__name__ == "lazy_import"` without importing `types`) and call `value = value.resolve()` before returning a found value from `_optional_item`, `load_global`, and `load_deref`.

---

### 3.2 [High / Wrong Output & Collision] [`annotations.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/annotations.py) & [`sitecustomize.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/boot/sitecustomize.py): `entry_key` collides whenever a `TypeVar` has both a bound/constraints and a default (`[T: int = str]`) or two definitions share a line

- **Location:** [`pipeline/staging/annotations.py:83-85, 469, 491`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/annotations.py#L83-L85) and [`pipeline/staging/boot/sitecustomize.py:172, 186`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/boot/sitecustomize.py#L172)
- **Mechanism:**
  In `d0bec20`, `entry_key` is `f"{os.path.realpath(filename)}::{qualname}::{firstlineno}"`.
  In CPython 3.15.2, when a `TypeVar` has both a bound (or constraint tuple) and a default on the same line (e.g., `type Alias[T: int = str] = list[T]`, `def f[T: int = str]():`, or `class C[T: int = str]:`), CPython compiles **two** separate evaluate functions (`T.evaluate_bound` and `T.evaluate_default`), and **both** code objects have `co_qualname == "T"` (or `"Outer.T"`) and the same `co_firstlineno`.
  In `evaluators_for_source`, `T.evaluate_default` overwrites `T.evaluate_bound` in `evaluators[key]`. At runtime under replay, `annotationlib.call_evaluate_function(T.evaluate_bound, Format.STRING)` (or `Format.FORWARDREF`) runs `T.evaluate_default`'s evaluator instead!
  *(Note: Also triggered when a generic function `def f[T](...):` and module-level annotations start on the same line, or two functions/type variables share a name on the same line; in CPython 3.15.2, a generic function's `f.__annotate__.__code__.co_qualname` is `'__annotate__'`, not `'f.__annotate__'`.)*
- **Reproduction:**
  ```python
  import annotationlib
  type Alias[T: int = str] = list[T]
  T = Alias.__type_params__[0]
  F = annotationlib.Format
  print("bound:", annotationlib.call_evaluate_function(T.evaluate_bound, F.STRING))
  print("default:", annotationlib.call_evaluate_function(T.evaluate_default, F.STRING))
  ```
  - **CPython 3.15.2:** `bound: int` / `default: str`
  - **Staging Replay (`d0bec20`):** `bound: str` / `default: str`
- **Recommendation:** Include `tuple(code.co_positions())` (or its deterministic hash, since tuples of `int | None` hash deterministically independent of `PYTHONHASHSEED`) in `entry_key(code)`, and fail closed in `evaluators_for_source` if two code objects ever produce the same key.

---

### 3.3 [High / False `[P2+]` Refusal] [`annotations.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/annotations.py): `evaluators_for_source` skips modules with `from __future__ import annotations`, dropping all PEP 695 `type` alias and `TypeVar` evaluate functions

- **Location:** [`pipeline/staging/annotations.py:456-458`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/annotations.py#L456-L458)
- **Mechanism:**
  Lines 456–458 return early whenever `from __future__ import annotations` appears in `tree.body`:
  ```python
  if any(isinstance(s, ast.ImportFrom) and s.module == "__future__" and any(a.name == "annotations" for a in s.names)
         for s in tree.body):
      return {}, []           # PEP 563: annotations are strings and there is no __annotate__
  ```
  In CPython 3.12–3.15, `from __future__ import annotations` (PEP 563) stringifies module, class, and function `__annotations__` (suppressing `__annotate__` on them), **but PEP 695 `type Alias = ...` (`Alias.evaluate_value`) and type-parameter bounds, constraints, and defaults (`T.evaluate_bound`, `T.evaluate_constraints`, `T.evaluate_default`) are unaffected by `from __future__ import annotations`** — CPython still compiles lazy evaluate functions for them.
  Because `evaluators_for_source` returns `{}, []`, every PEP 695 `type` alias and type parameter in a module using `from __future__ import annotations` gets no second entry point, and `annotationlib.call_evaluate_function(Alias.evaluate_value, Format.STRING)` or `Format.FORWARDREF` (when a name is unbound) is refused at runtime with exit status 70 (`[P2+] annotationlib`).
- **Reproduction:**
  ```python
  from __future__ import annotations
  import annotationlib
  type Alias[T: Bound = Default] = list[T] | Unbound
  print(annotationlib.call_evaluate_function(Alias.evaluate_value, annotationlib.Format.STRING))
  ```
  - **CPython 3.15.2:** `list[T] | Unbound` (exit 0)
  - **Staging Replay (`d0bec20`):** Exit 70 (`bella: refused: [P2+] annotationlib: FORWARDREF and STRING of an annotate function the compiler did not generate...`)
- **Recommendation:** Instead of returning `{}, []` when `from __future__ import annotations` is present, pass `pep563: bool` into `_Owners` so that `module`, `class`, and `function` `__annotate__` owners are skipped under PEP 563 while `evaluate` owners (`visit_TypeAlias` and `_type_params`) are still generated and checked.

---

### 3.4 [High / Build Crash] [`annotations.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/annotations.py): `TypeVarTuple` starred defaults (`[*Ts = *tuple[int, str]]`, PEP 696) crash `evaluators_for_source` with `SyntaxError`

- **Location:** [`pipeline/staging/annotations.py:228-237`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/annotations.py#L228-L237) (`_Owners._type_params`)
- **Mechanism:**
  For `*args: *Ts` in `visit_FunctionDef` (lines 253–255), `annotations.py` checks `starred = isinstance(ann, ast.Starred)` and unwraps `ann.value`, so `_generate` wraps the expression in `_rt.unpack1(...)` (matching CPython's `UNPACK_SEQUENCE 1`).
  However, in `_Owners._type_params` (lines 234–236):
  ```python
  for expr in (p.bound if isinstance(p, ast.TypeVar) else None, p.default_value):
      if expr is not None and tp is not None:
          self.owners.append(_Owner("evaluate", tp, self.scope.kind == "class", self.private, set(),
                                    [("", expr, None, False)]))
  ```
  In Python 3.13+ (PEP 696), a `TypeVarTuple` default must be a starred expression (`[*Ts = *tuple[int, str]]`), so `isinstance(p.default_value, ast.Starred)` is `True`. Passing `starred = False` causes `_generate` to emit `return *_rt.load_global(...)`, which raises `SyntaxError: can't use starred expression here` when `compile(ast.Module([fn], []), ...)` runs at line 480, crashing the dry run.
- **Reproduction:**
  ```python
  type Alias[*Ts = *tuple[int, str]] = tuple[*Ts]
  ```
  Running `evaluators_for_source` or `_replay` on this 1-line module crashes with `SyntaxError: can't use starred expression here`.
- **Recommendation:** In `_Owners._type_params`, unwrap `ast.Starred` just as `visit_FunctionDef` does:
  ```python
  starred = isinstance(expr, ast.Starred)
  inner = expr.value if isinstance(expr, ast.Starred) else expr
  self.owners.append(_Owner("evaluate", tp, self.scope.kind == "class", ..., [("", inner, None, starred)]))
  ```

---

### 3.5 [High / False `[P2+]` Refusal & Build Declines] [`annotations.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/annotations.py): Owner span matching (`by_span`) and CPython 3.15.2 `symtable` edge cases

1. **`ast.IfExp` (`x: Later if cond else int`) and single-interpolation `ast.JoinedStr` (`x: f"{int}"`) fail owner matching (`matched to 0 annotation owners`) (`annotations.py:464, 471`):**
   - `by_span` only indexes the root AST node `_span(ann)` (`{_span(ann): owner for owner in visitor.owners for _, ann, _, _ in owner.entries}`).
   - When the only annotation on a class, function, or type alias is an `ast.IfExp` (`x: Later if cond else int`) or a single-interpolation f-string (`f"{int}"`), CPython 3.15.2's compiler emits instructions with the spans of the child expressions (`test`, `body`, `orelse`, or formatted value) and the enclosing scope, **never** the root `IfExp` or `JoinedStr` span.
   - As a result, `owners` at line 471 is empty (`matched to 0 annotation owners`), the compiler-generated `__annotate__` gets no entry point, and a `@dataclass` using `x: Later if cond else int = 1` is falsely refused at runtime with exit status 70 (`[P2+] annotationlib`):
     ```python
     import dataclasses
     cond = True
     @dataclasses.dataclass
     class Box:
         x: Later if cond else int = 1
     class Later:
         pass
     print(Box(2))  # CPython: Box(x=2); Replay: exit 70 ([P2+] annotationlib)
     ```
   - **Fix:** Because annotation expressions (`ast.expr`) cannot contain statement-level definitions (`def`, `class`, `type`), the AST subtrees of different owners' entries have disjoint source spans. Indexing `{_span(sub): owner for owner in visitor.owners for _, ann, _, _ in owner.entries for sub in ast.walk(ann) if isinstance(sub, ast.expr)}` matches `IfExp` and `JoinedStr` unambiguously.

2. **Private local and parameter names inside methods (`_function_scope`, `annotations.py:167-174`):**
   - `_function_scope(node, tp or outer)` does not mangle `b.bound`, `b.declared_global`, or `b.nonlocal_` with the enclosing class's `private` name.
   - When a method inside `class Outer:` defines a private parameter or local variable and a nested function's annotation references it (`class Outer: def m(self, __p=int): __loc = str; def inner(x: __loc, y: __p): ...`), `inner.__annotate__` mangles the load to `_Outer__loc` / `_Outer__p`, fails to find it in `m`'s unmangled `bound` set `{"__loc", "__p", ...}`, and emits `LOAD_GLOBAL` instead of `LOAD_DEREF`, failing the static check with `MISMATCH`.
   - **Fix:** Pass `private: str | None` to `_function_scope` and mangle `b.bound`, `b.declared_global`, and `b.nonlocal_` with `mangle(private, n)` before constructing `_Scope`.

3. **Private type-parameter names (`[__T]`) and private names in a `ClassDef`'s type-parameter bounds/defaults (`annotations.py:183-184, 231-237, 274-281`):**
   - In CPython 3.15.2 (`Python/symtable.c`):
     - For `type Alias[__T]` and `def m[__T]` inside `class Outer:`, `p.name` (`__T`) is mangled with `Outer` (`_Outer__T`).
     - For `class Inner[__T]:`, `p.name` (`__T`) is mangled with `Inner` (`_Inner__T`), while inside `Inner`'s type-parameter bounds and defaults (`class Inner[T: __Secret = __Default]:`), `st->st_private` is `NULL` (`None`), so `__Secret` and `__Default` are **not** mangled to `_Outer__Secret`.
   - In `annotations.py`, `_typeparams_scope` and `owner.type_params` leave `p.name` unmangled (`"__T"`), and `visit_ClassDef` leaves `self.private = "Outer"` when calling `self._type_params(node.type_params, tp)`. Both cause static `MISMATCH` declines against CPython 3.15.2.

4. **`global` declarations inside a class body (`annotations.py:274-285, 290-306, 330-346`):**
   - When a class body declares `global G` (`def outer(): G = str; class C: global G; x: G; def m(self, a: G): ...`), CPython records `G` as explicitly global in `C`'s symbol table and emits a direct `LOAD_GLOBAL ('G')` (without `LOAD_DEREF ('__classdict__')`) in both `C.__annotate__` and `C.m.__annotate__`.
   - Because `visit_ClassDef` does not collect `declared_global` on the class `_Scope` and `_Rewrite.visit_Name` always uses `LOAD_FROM_DICT_OR_DEREF` / `LOAD_FROM_DICT_OR_GLOBALS` when `self.owner.sees_class` is `True`, both `C.__annotate__` and `C.m.__annotate__` fail the static check with `MISMATCH`.

5. **Walrus operator inside a `lambda` inside a comprehension (`annotations.py:144-149` and [`tools/closure.py:463-467`](file:///home/nathan/workspaces/nth/bella/tools/closure.py#L463-L467)):**
   - Both `_Bindings._comprehension` in `annotations.py` and `_names_in` in `tools/closure.py` use `ast.walk(node)` to find `ast.NamedExpr` targets inside a comprehension. If the comprehension contains a `lambda` (`_ = [lambda: (w := int) for _ in (1,)]`), `ast.walk` descends into the `lambda` body and attributes `w` to the enclosing scope, whereas in Python a walrus inside a `lambda` binds in the `lambda`'s own scope.

---

### 3.6 [Medium / Cache Collision & Stale Artefact] [`pipeline/staging/run.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/run.py): `program_artefact` collides across working directories when given a relative script path, and `stdlib_artefact` / `program_artefact` omit the optimization level (`-O` / `PYTHONOPTIMIZE`)

- **Location:** [`pipeline/staging/run.py:46-110, 121-136`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/run.py#L46-L110)
- **Mechanism:**
  1. **Relative `script` path collision across directories (`run.py:98, 104`):**
     `program_artefact` computes `paths = [script, *INPUTS]` without resolving `script` (`script.resolve()`), and `_key` hashes `str(p)` and `p.read_bytes()`.
     If `run.py main.py` is run from directory `tmp1` and then from directory `tmp2`, where `tmp1/main.py` and `tmp2/main.py` have identical source (e.g., `import annotationlib, helper; ...`) while `tmp1/helper.py` and `tmp2/helper.py` differ:
     - `_key` produces the exact same cache path `build/staging/programs/main-<hash>`.
     - `current(out)` (`run.py:72-85`) checks the file digests in `out.json["sources"]` — which list `/tmp/tmp1/main.py` and `/tmp/tmp1/helper.py`! As long as `tmp1` still exists on disk, `current(out)` returns `True`.
     - `run.py` then runs `tmp2/main.py` with `tmp1`'s `.bin` artefact, whose annotation entry points are keyed by `/tmp/tmp1/helper.py::...`, causing `tmp2` to abort at runtime with exit status 70 (`[P2+] annotationlib`) or run `tmp1`'s staged code.
  2. **Optimization level (`-O` / `PYTHONOPTIMIZE`) omitted from cache key and `dry_run` (`run.py:64, 88, 104`):**
     `sitecustomize.py:277-278` refuses an artefact when `data["optimize"] != sys.flags.optimize`, but neither `stdlib_artefact` nor `program_artefact` includes the target optimization level in `_key(...)`, nor does `run.py` pass `-O`/`-OO` from `python_options` to `dry_run`. Running with `PYTHONOPTIMIZE=1` or `-O` hits the `optimize=0` cached artefact and immediately fails with `bella: refused: E-01: ... was staged at optimisation level 0, not 1`.
- **Reproduction (Directory Collision):**
  ```python
  with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
      main_src = "import annotationlib, helper\nprint(annotationlib.get_annotations(helper.f, format=annotationlib.Format.STRING))\n"
      Path(tmp1, "main.py").write_text(main_src)
      Path(tmp1, "helper.py").write_text("def f(x: int): pass\n")
      Path(tmp2, "main.py").write_text(main_src)
      Path(tmp2, "helper.py").write_text("def f(x: bytes): pass\n")
      subprocess.run([sys.executable, "pipeline/staging/run.py", "main.py"], cwd=tmp1)  # {'x': 'int'}
      subprocess.run([sys.executable, "pipeline/staging/run.py", "main.py"], cwd=tmp2)  # exit 70!
  ```
- **Recommendation:**
  1. In `program_artefact`, resolve `script = script.resolve()` before building `paths` and verify `str(script) in sources` inside `current(out)`.
  2. Compute the effective optimization level from `sys.flags.optimize`, `PYTHONOPTIMIZE`, and `-O`/`-OO` in `python_options`, pass it to `dry_run`, and include it in `_key(...)` for both `stdlib_artefact` and `program_artefact`.

---

### 3.7 [Low / Model Fidelity] [`sitecustomize.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/boot/sitecustomize.py) & [`scan.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/scan.py): Unstaged `exec(code)` / `eval(code)` on staged `compile()` code objects, and minor `scan.py` / `closure.py` edge cases

1. **Unstaged `exec(code_obj)` / `eval(code_obj)` on a code object returned by a staged `compile()` (`sitecustomize.py:84-86`, `dryrun.py:74-78`):**
   - In `sitecustomize.py:84-86`, `if isinstance(source, _CodeType): if id(source) in _staged_code: return source`.
   - Because `_record` in `dryrun.py:74-78` ignores `_CodeType` arguments, the dry run never records whether `exec(code)` or `eval(code)` was actually called at a given site during staging. If a module body calls `C = compile("1 + 1", "<s>", "eval")` at definition time (or `T = typing.Optional["1 + 1"]`, which compiles `"1 + 1"` into `ForwardRef.__forward_code__`), `id(C)` is added to `_staged_code`, and any unstaged runtime `eval(C)` or `exec(C)` under `if __name__ == "__main__":` is allowed instead of being refused with `E-01`.
   - **Fix:** Either record `(site, kind)` for `_CodeType` executions during the dry run (or do not add `ForwardRef.__forward_code__`'s compiled code objects to `_staged_code` unless `exec`/`eval` of that code object was staged at `(site, kind)`).

2. **Non-simple `AnnAssign` (`(x): int`) in `scan.py:88-89`:**
   - In [`pipeline/staging/scan.py:88-89`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/scan.py#L88-L89), `NamedTuple` class field scanning checks `if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)` without `and s.simple` (unlike `annotations.py:194`, which checks `stmt.simple`). A parenthesized target `(x): int` has `s.simple == 0` and is not a `NamedTuple` field in CPython.

3. **`tools/closure.py:1029-1032` shim path in `closure.lock.json`:**
   - When `info.status == "shim" and shim_source.exists()`, `tools/closure.py` sets local `kind, path = "source", str(shim_source)` for scanning, but in `d0bec20` did not update `info.kind, info.path`, leaving `closure.lock.json` pointing at the stdlib `"annotationlib.py"` path instead of `"runtime/shims/annotationlib.py"`.

---

## 4. Summary of Recommended Actions Before Task 6

1. **Resolve `LazyImportType` in `annotate_rt.py` (3.1):** Call `.resolve()` on `LazyImportType` values in `_optional_item`, `load_global`, and `load_deref` so `Format.FORWARDREF` matches CPython 3.15.2 for both valid and failing PEP 810 lazy imports.
2. **Disambiguate `entry_key` and fix `annotations.py` PEP 563 / PEP 696 / `by_span` / `symtable` cases (3.2–3.5):**
   - Include instruction positions in `entry_key(code)`.
   - Keep `evaluate` owners (`TypeAlias` and `_type_params`) when `from __future__ import annotations` is active.
   - Unwrap `ast.Starred` on `p.default_value` in `_Owners._type_params` for PEP 696 `TypeVarTuple` defaults.
   - Index all expression sub-nodes in `by_span` so `ast.IfExp` and `ast.JoinedStr` match their owners.
   - Mangle `_function_scope` bindings and `_typeparams_scope` names with the active `private` class name, use `private = None` for `ClassDef` type-parameter bounds/defaults, and respect `global` declarations inside class bodies.
3. **Fix `run.py` cache keys (3.6):** Resolve `script.resolve()` in `program_artefact` and include the effective optimization level in `_key(...)` and `dry_run(...)`.
