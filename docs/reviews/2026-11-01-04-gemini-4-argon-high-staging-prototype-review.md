# Bella Staging Prototype & D-5 `annotationlib` Shim Review (Commits `19316ba`..`b838bc5`)

**Date:** 2026-11-01  
**Reviewer:** `gemini-4-argon-high`  
**Sequence:** 04  
**Scope:** Commits `19316ba` through `b838bc5` — Decisions D-7 to D-11 (`19316ba`) and Gate 0 Task 5: Staging Prototype & D-5 `annotationlib` Shim (`b838bc5`, [`docs/staging.md`](file:///home/nathan/workspaces/nth/bella/docs/staging.md))

---

## 1. Executive Summary & Verification

### 1.1 Reproduction of Stated Claims
All checks in `make check` pass on the pinned CPython 3.15.2 and GCC 16.2.1 (`16.2.1 20261029`):
- **`make closure`**: 175 modules (`112 compiled`, `37 mapped`, `19 core`, `7 shim`, with `unicodedata` added as a `[P1]` root per D-8).
- **`make targets-closure`**: Increment `1a` is now sub-staged by target per D-10 (`1a.1` `cli_easy_slugs`: 111 modules / 52,106 lines; `1a.2` `service_easy_tokens`: +24 modules / 7,356 lines; `1a.3` `data_easy_sales`: +14 modules / 11,757 lines; `1c`: 31 modules; `later`: 6 modules for the three tricky targets moved past Phase 1 per D-7).
- **`make lint`**: `ruff` and `mypy` pass across 50 tool/model files, 76 dialect/corpus files (`--disallow-any-explicit`), and 6 target drivers.
- **`make test`**: 89/89 `pytest` tests pass (including [`pipeline/tests/test_staging.py`](file:///home/nathan/workspaces/nth/bella/pipeline/tests/test_staging.py)) + `refmodel.selftest` (3,000 ops over 50 worlds).
- **`make verify`**: 121/121 expectations reproduced on CPython 3.15.2 (now running every `[P1]` case under both standard CPython and the `D-20` simulation, catching F-1 on [`C-7-09_date_modules.py`](file:///home/nathan/workspaces/nth/bella/conformance/cases/C-7-09_date_modules.py)).
- **`make staging-check`**:
  - Dry-run artefacts for `stdlib`, `C-8-08`, `C-8-09`, and `C-3-21` are byte-identical across `PYTHONHASHSEED=0` and `1`.
  - All 58 `[P1]` conformance cases pass under the staging replay model (`pipeline/staging/run.py`), and `C-3-22` (`[P2+]`) is refused as expected.
  - All 3 Phase-1 targets (`cli_easy_slugs`, `service_easy_tokens`, `data_easy_sales`) match their authoritative recordings byte-for-byte under the replay.

### 1.2 Summary of Review Findings
The staging prototype in [`pipeline/staging/`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/dryrun.py) and [`docs/staging.md`](file:///home/nathan/workspaces/nth/bella/docs/staging.md) is well-designed and empirically settles the mechanism choice (staged texts keyed by call site and text + build-time `namedtuple` probes). However, our testing uncovered **five concrete bug groups** in the `annotationlib` shim and staging prototype (each reproduced below on `b838bc5`), including two issues that directly affect open question **S-1** in [`docs/staging.md`](file:///home/nathan/workspaces/nth/bella/docs/staging.md#L180-L190):

1. **[High] [`ForwardRef.__forward_code__`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py#L307-L312) refuses at `ForwardRef` creation time when called by `typing._make_forward_ref`**:
   - In CPython 3.15.2, `typing._make_forward_ref` (`Lib/typing.py:194`) accesses `forward_ref.__forward_code__` eagerly at `ForwardRef` construction time on *every* string annotation passed through `typing._type_convert` (ignoring its return value, purely as a syntax check).
   - Because [`runtime/shims/annotationlib.py:310-312`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py#L310-L312) placed `_bella.refuse(...)` inside `ForwardRef.__forward_code__` instead of `ForwardRef.evaluate()` ([`annotationlib.py:230`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py#L230)), the shim refuses **even when the string is a plain identifier (`"int"`, `"Node"`) and `evaluate()` is never called**.
   - Consequently, `@dataclass` fields using `Optional["Node"]`, `Union["Node", None]`, `ClassVar["int"]`, `Final["int"]`, or `Callable[["Node"], None]`, and **every** `typing.NamedTuple` or `typing.TypedDict` with any quoted annotation (`x: "int"`) or under `from __future__ import annotations` fail at class definition time with exit code 70.
2. **[High] Two hidden runtime blockers for S-1 Option 2 in [`runtime/shims/annotationlib.py`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py) and [`manifest.toml`](file:///home/nathan/workspaces/nth/bella/manifest.toml#L134) (and [`tools/closure.py`](file:///home/nathan/workspaces/nth/bella/tools/closure.py#L1027) not scanning `runtime/shims/*.py`)**:
   - **Blocker A (`ast.unparse` is refused in Phase 1)**: S-1 Option 2 proposes running CPython's `FORWARDREF` and `STRING` code over a compiler-generated second `__annotate__` entry point. However, `_Stringifier.__repr__` ([`annotationlib.py:539`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py#L539)) and `ForwardRef.__forward_arg__` ([`annotationlib.py:282`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py#L282)) call `ast.unparse(self.__ast_node__)` on every compound annotation (`Node | None`, `list[Node]`), and `ast.unparse` is in `unsupported_functions` in `closure.lock.json` (`ast = ["_ast_unparse"]` in [`manifest.toml:134`](file:///home/nathan/workspaces/nth/bella/manifest.toml#L134)). The replay model missed this because [`sitecustomize.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/boot/sitecustomize.py) only blocks `[omissions]`, not `unsupported_functions`.
   - **Blocker B (`ForwardRef.__resolved_str__` calls `ast.parse` → `builtins.compile()`, which is E-01)**: When an unbound name is combined with a resolved non-constant object (e.g., `@dataclass class Node: x: Node | int = 1`), `_Stringifier` populates `self.__extra_names__`. Accessing `repr()` on that `ForwardRef` (e.g., `print(dataclasses.fields(Node))`) calls `ForwardRef.__resolved_str__` ([`annotationlib.py:298`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py#L298)), which calls `ast.parse(resolved_str, mode="eval")` → `builtins.compile()`, triggering an `E-01` refusal.
   - **Blocker C (`tools/closure.py` skips `shim` files)**: [`tools/closure.py:1027`](file:///home/nathan/workspaces/nth/bella/tools/closure.py#L1027) does not scan `runtime/shims/*.py`, so `annotationlib.py`'s imports (`ast`, `enum`, `keyword`, `types`, `typing`, `warnings`) are untracked in target closures.
3. **[Medium-High] [`_import_entry`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/dryrun.py#L176-L188) in `pipeline/staging/dryrun.py` loads the entry script under its basename stem instead of `"__main__"`, causing three failures**:
   - **3a**: Any definition-time `exec`/`eval` site located in the entry module itself (e.g., a class decorator or helper defined in the entry script) is recorded under `f"{stem}:{qualname}:{lineno}"`, whereas runtime replay looks up `f"__main__:{qualname}:{lineno}"` and refuses with `E-01`.
   - **3b**: Registering `sys.modules[stem] = module` (combined with `sys.path.insert(0, dirname(entry))` at [`dryrun.py:223`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/dryrun.py#L223) ignoring `-P`) collides with stdlib modules when the entry script shares a name with one (e.g., `calendar.py` importing `calendar`), causing the dry run of the entry module to fail silently (`failed_imports`) and stage nothing.
   - **3c**: Running `dryrun.py` with both `--modules-from` and `--entry` (as documented in [`dryrun.py:3-5`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/dryrun.py#L3-L5)) drops **100%** of the entry script's staged texts because `_import_entry` records `_body()` as `stem` while `wanted` ([`dryrun.py:262`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/dryrun.py#L262)) contains `"__main__"`.
4. **[Medium] Multi-module programs without `--program-lock`, PEP 810 `lazy import` program modules, and `--program-module` cache invalidation in [`dryrun.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/dryrun.py) / [`run.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/run.py)**:
   - **4a**: Sibling modules imported by an entry script without `--program-lock` are omitted from `covered` ([`dryrun.py:234-237`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/dryrun.py#L234-L237)), so their `STRING` annotation tables and `namedtuple` probes are never built and fail at runtime.
   - **4b**: A module imported via PEP 810 `lazy import` is bound as a `types.LazyImportType` proxy without executing its module body during `dryrun.py` (unless separately listed in `--program-module`), so any `@dataclass` or `namedtuple` in that lazy module is unstaged and fails with `E-01` at first use.
   - **4c**: [`program_artefact`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/run.py#L80-L92) in `run.py` hashes `[script, *INPUTS, program_lock]` for the cache key, omitting the source files of the `--program-module` modules themselves.
5. **[Medium] Four defects in [`annotations.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/annotations.py), [`annotationlib.py`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py), [`scan.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/scan.py), and [`sitecustomize.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/boot/sitecustomize.py)**:
   - **5a**: [`_stable(value)`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/annotations.py#L52-L59) returns `True` for every `_Stringifier` without walking `_Stringifier__ast_node__` for `ast.Set`, so `def f(a: Annotated[int, {"p", "q"}])` is marked stable (`unstable: None`) yet produces different `STRING` tables under `PYTHONHASHSEED=0` vs `1`.
   - **5b**: [`_raised`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/annotations.py#L69-L70) and [`_Hooks.exception`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/boot/sitecustomize.py#L124-L130) serialize exceptions as `[type(exc).__name__, str(exc)]` and reconstruct via `cls(recorded[1])`, corrupting `KeyError.args` (`KeyError('missing')` → `KeyError("'missing'")`), losing `AttributeError.name` (`'no_such_attr'` → `None`, violating D-08), and crashing on multi-argument built-in exceptions (`UnicodeError`).
   - **5c**: [`call_annotate_function`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py#L822-L825) under `Format.FORWARDREF` refuses when `compiled is None or _is_evaluate` *before* trying `annotate(Format.VALUE)`, breaking custom `__annotate__` functions and resolved PEP 695 `type Alias = ...` `evaluate_value` functions that CPython supports.
   - **5d**: [`scan.py:100-120`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/scan.py#L100-L120) ignores keyword arguments `typename=` / `field_names=` in `namedtuple` probes (and `builtins.exec`/`eval`/`compile` in `exec_sites`); [`dryrun.py:288`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/dryrun.py#L288) and [`sitecustomize.py:53,85-89`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/boot/sitecustomize.py#L85-L89) drop `kind` (`exec` vs `eval`) from the compiled code key and silently drop `closure=` in `exec()`.

---

## 2. Responses to Open Questions S-1 to S-5 ([`docs/staging.md` §8](file:///home/nathan/workspaces/nth/bella/docs/staging.md#L179-L208))

### S-1: `FORWARDREF` with an unbound name (Self-referential `@dataclass`, `NamedTuple`, `TypedDict`)
- **Recommendation**: **Adopt Option 2** (generate a second entry point next to each `__annotate__` that evaluates the annotation expressions against a passed mapping and closure cells, running CPython's `FORWARDREF` and `STRING` logic without build-time tables), **with the three fixes detailed in Findings 3.1 and 3.2 below**:
  1. Fix `ForwardRef.__forward_code__` ([`runtime/shims/annotationlib.py:307-312`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py#L307-L312)) so `typing._make_forward_ref`'s eager `. __forward_code__` access does not refuse valid string forward references at creation time (which currently breaks even Option 1's quoted annotations like `Optional["Node"]` and `from __future__ import annotations`).
  2. Move `_ast_unparse` from `[lazy_unsupported]` to `[phase1].compiled` in [`manifest.toml`](file:///home/nathan/workspaces/nth/bella/manifest.toml#L134) (it is 608 lines of pure Python in CPython 3.15.2), because CPython's `_Stringifier.__repr__` and `ForwardRef.__forward_arg__` call `ast.unparse`.
  3. Adapt `ForwardRef.__resolved_str__` ([`runtime/shims/annotationlib.py:296-300`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py#L296-L300)) to apply `_ExtraNameFixer(names)` directly to a copy of `self.__ast_node__` before calling `ast.unparse`, eliminating its call to `ast.parse` (`builtins.compile`, excluded by E-01).
  4. In the compiler's second entry point for class/method `__annotate__` functions, preserve CPython 3.15's `LOAD_FROM_DICT_OR_GLOBALS` semantics when `__classdict__` is replaced by `_Stringifier("__classdict__")` (`_Stringifier.__getitem__` raises `KeyError` on `"__classdict__"` so lookup falls through to the passed `globals` mapping).

### S-2: Function signatures at runtime (`dataclass.__doc__` calling `inspect.signature`)
- **Recommendation**: **Agree with Option 1** (refuse reading the auto-generated `_DataclassDocstring` descriptor on a `@dataclass` without an explicit docstring in Phase 1, and add a `bella-lint` check). In CPython 3.15.2 (`Lib/dataclasses.py:1232-1235`), `cls.__doc__ = _auto_docstring` is lazy and never calls `inspect.signature` unless `cls.__doc__` is read, and [`docs/dialect-spec.md` §7](file:///home/nathan/workspaces/nth/bella/docs/dialect-spec.md#L149) already marks `inspect` as `[P2+]`. Revisit with `docs/targets.md` §5 item 1 after Phase 1.

### S-3: Classes made at runtime (`@dataclass` / `make_dataclass` inside functions) & the recorded-input rule
- **Recommendation**: **Agree with both parts**:
  1. Refusing `@dataclass` / `make_dataclass` inside functions in Phase 1 (with a `bella-lint` warning) follows [`docs/dialect-spec.md` §3](file:///home/nathan/workspaces/nth/bella/docs/dialect-spec.md#L56-L57) and [§5](file:///home/nathan/workspaces/nth/bella/docs/dialect-spec.md#L103) (classes depending on runtime values are Tier 3 `[P2+]`, and unstaged runtime `exec` is E-01).
  2. Amending [`docs/dialect-spec.md` §8](file:///home/nathan/workspaces/nth/bella/docs/dialect-spec.md#L175) so that recorded build-time inputs only invalidate *staged layout facts* (field sets, MROs) while *staged code texts* remain sound (since runtime lookup keys on the exact `(site, kind, text)` tuple and can only miss if an input selects an unstaged branch) is clean and accurate.

### S-4: `gettext.c2py` plural expressions from `.mo` files
- **Recommendation**: **Agree with Option 2** (refuse `gettext.c2py` with E-01 in Phase 1 and warn in `bella-lint` until a target program requires `.mo` catalogues with `Plural-Forms`).

### S-5: Confirm the staging mechanism
- **Recommendation**: **Confirm staged texts keyed by `(site, kind, text)` with build-time probes for literal `namedtuple` calls**. The evidence in [`docs/staging.md` §5](file:///home/nathan/workspaces/nth/bella/docs/staging.md#L119-L136) is conclusive: 58/58 `[P1]` cases, 23/23 stdlib `namedtuple` texts, and 15/15 stdlib `dataclasses` texts pass with zero copied stdlib code per CPython release, whereas compiler intrinsics fail 5/58 `[P1]` cases (`C-3-13`, `C-7-02`, `C-7-07`, `C-7-14`, `C-8-08`) and would duplicate 516 lines of `dataclasses.py` plus `namedtuple`'s template.

---

## 3. Detailed Bug Findings & Reproducers

### 3.1 `ForwardRef.__forward_code__` refuses when touched by `typing._make_forward_ref` (Breaks quoted types in `typing` and `from __future__ import annotations`)

- **Location**: [`runtime/shims/annotationlib.py:307-312`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py#L307-L312) and [`runtime/shims/annotationlib.py:203-230`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py#L203-L230)
- **Problem**:
  In [`runtime/shims/annotationlib.py:307-312`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py#L307-L312), the `ForwardRef.__forward_code__` property was replaced with:
  ```python
  @property
  def __forward_code__(self):
      if self.__code__ is not None:
          return self.__code__
      # bella: compiling the text of a forward reference needs a compiler at runtime (E-01)
      _bella.refuse("[P2+] annotationlib: evaluating a ForwardRef that is not a plain name "
                    "needs compile() at runtime (spec section 3, review log D-5)")
  ```
  However, in CPython 3.15.2, `typing._make_forward_ref` (`Lib/typing.py:187-195`) touches `forward_ref.__forward_code__` **eagerly at creation time** on every string converted by `typing._type_convert`:
  ```python
  forward_ref = annotationlib.ForwardRef(code, **kwargs)
  # For compatibility, eagerly compile the forwardref's code.
  forward_ref.__forward_code__
  return forward_ref
  ```
  This happens **even when `code` is a plain identifier (`"int"`, `"Node"`) and `ForwardRef.evaluate()` is never called**. As a result:
  1. Self-referential `@dataclass` definitions using quoted annotations inside `typing` forms (`Optional["Node"]`, `Union["Node", None]`, `ClassVar["int"]`, `Final["int"]`, `Callable[["Node"], None]`) — which S-1 Option 1 explicitly relies on — fail at class definition time with exit code 70.
  2. Every `typing.NamedTuple` or `typing.TypedDict` with a quoted field annotation (even `x: "int"`) or in a module with `from __future__ import annotations` (even `x: int`) fails at class definition time with exit code 70.
- **Reproducer**:
  ```bash
  .venv/bin/python -c '
  import tempfile, subprocess, sys
  from pathlib import Path
  for label, code in [
      ("dataclass Optional[\"Node\"]", "from dataclasses import dataclass\nfrom typing import Optional\n@dataclass\nclass Node:\n    next: Optional[\"Node\"] = None\nprint(Node())"),
      ("NamedTuple plain quoted", "from typing import NamedTuple\nclass N(NamedTuple):\n    x: \"int\"\nprint(N(1))"),
      ("NamedTuple future annotations", "from __future__ import annotations\nfrom typing import NamedTuple\nclass N(NamedTuple):\n    x: int\nprint(N(1))"),
      ("TypedDict future annotations", "from __future__ import annotations\nfrom typing import TypedDict\nclass T(TypedDict):\n    x: int\nprint(T(x=1))"),
  ]:
      with tempfile.TemporaryDirectory() as tmp:
          p = Path(tmp, "t.py"); p.write_text(code)
          r = subprocess.run([sys.executable, "pipeline/staging/run.py", str(p)], capture_output=True, text=True)
          print(f"{label:32}: rc={r.returncode} err={r.stderr.strip()}")
  '
  ```
  Output on `b838bc5`:
  ```text
  dataclass Optional["Node"]      : rc=70 err=bella: refused: [P2+] annotationlib: evaluating a ForwardRef that is not a plain name needs compile() at runtime (spec section 3, review log D-5)
  NamedTuple plain quoted         : rc=70 err=bella: refused: [P2+] annotationlib: evaluating a ForwardRef that is not a plain name needs compile() at runtime (spec section 3, review log D-5)
  NamedTuple future annotations   : rc=70 err=bella: refused: [P2+] annotationlib: evaluating a ForwardRef that is not a plain name needs compile() at runtime (spec section 3, review log D-5)
  TypedDict future annotations    : rc=70 err=bella: refused: [P2+] annotationlib: evaluating a ForwardRef that is not a plain name needs compile() at runtime (spec section 3, review log D-5)
  ```
- **Recommendation**:
  Move the `[P2+]` refusal for evaluating a non-identifier `ForwardRef` into `ForwardRef.evaluate()` at [`runtime/shims/annotationlib.py:230`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py#L230) (in the `else:` branch of `if arg.isidentifier() and not keyword.iskeyword(arg):`), and either replace `typing._make_forward_ref` (or allow `__forward_code__` when called from `typing._make_forward_ref`) so constructing a `ForwardRef` via `typing` does not require `compile()` at runtime.

---

### 3.2 S-1 Option 2 Runtime Blockers: `ast.unparse` (`[lazy_unsupported]`), `ast.parse` (`E-01`) in `ForwardRef.__resolved_str__`, and Unscanned Shims in `tools/closure.py`

- **Location**: [`runtime/shims/annotationlib.py:13,282,298-300,539`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py#L282-L300), [`manifest.toml:134`](file:///home/nathan/workspaces/nth/bella/manifest.toml#L134), [`tools/closure.py:1027`](file:///home/nathan/workspaces/nth/bella/tools/closure.py#L1027)
- **Problem**:
  [`docs/staging.md` §8 S-1 Option 2](file:///home/nathan/workspaces/nth/bella/docs/staging.md#L184-L190) states:
  > *"The shim then runs CPython's own FORWARDREF and STRING code unchanged, the build-time tables become unnecessary, and only `ForwardRef.evaluate` of an expression stays `[P2+]`."*
  
  Running CPython's `FORWARDREF` and `STRING` code at runtime hits three obstacles in Phase 1:
  1. **`ast.unparse` is refused in Phase 1**: `_Stringifier.__repr__` ([`annotationlib.py:539`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py#L539)) and `ForwardRef.__forward_arg__` ([`annotationlib.py:282`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py#L282)) call `ast.unparse(self.__ast_node__)` whenever an annotation is not a bare identifier (e.g., `Node | None`). In [`manifest.toml:134`](file:///home/nathan/workspaces/nth/bella/manifest.toml#L134), `ast = ["_ast_unparse"]` is in `[lazy_unsupported]`, so `ast.unparse` is refused at runtime (`closure.lock.json` `unsupported_functions`). Note that [`pipeline/staging/boot/sitecustomize.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/boot/sitecustomize.py) currently does not stub `unsupported_functions` from `closure.lock.json`, which is why `ast.unparse` was not refused in the replay model.
  2. **`ForwardRef.__resolved_str__` calls `ast.parse` (`builtins.compile`, excluded by E-01)**: When an unbound name in `FORWARDREF` is combined with a resolved non-constant object (e.g., `Node | int`, `int | Node`, `Node[int]`), `_Stringifier` populates `self.__extra_names__ = {'__annotationlib_name_1__': <class 'int'>}` and sets `self.__ast_node__` to `ast.BinOp(...)`. When `repr()` or `__resolved_str__` is accessed on that `ForwardRef` (for example, `print(dataclasses.fields(Node))`), `ForwardRef.__resolved_str__` ([`annotationlib.py:296-300`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py#L296-L300)) first unparses `self.__ast_node__` via `self.__forward_arg__` and then calls `ast.parse(resolved_str, mode="eval")` (which calls `builtins.compile()`, refused by `E-01`) to run `_ExtraNameFixer(names)`.
  3. **`tools/closure.py` does not scan `runtime/shims/*.py`**: [`tools/closure.py:1027`](file:///home/nathan/workspaces/nth/bella/tools/closure.py#L1027) skips scanning modules with `status == "shim"`. Now that [`runtime/shims/annotationlib.py`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py) is a 1,180-line Python module in the tree importing `ast`, `enum`, `keyword`, `types`, `typing`, and `warnings`, its imports are invisible to `tools/closure.py`.
- **Reproducer (for `ForwardRef.__resolved_str__` calling `builtins.compile`)**:
  ```bash
  .venv/bin/python -c '
  import annotationlib, builtins
  d = annotationlib._StringifierDict({"int": int}, globals={}, owner=None, is_class=True, format=annotationlib.Format.FORWARDREF)
  val = d["Node"] | d["int"]
  d.transmogrify(None)
  orig = builtins.compile
  builtins.compile = lambda *a, **k: (print("COMPILE CALLED:", a[:3]), orig(*a, **k))[1]
  print(repr(val))
  '
  ```
  Output:
  ```text
  COMPILE CALLED: ('Node | __annotationlib_name_1__', '<unknown>', 'eval')
  ForwardRef('Node | int', is_class=True)
  ```
- **Recommendation**:
  1. For S-1 Option 2, move `_ast_unparse` into `[phase1].compiled` in [`manifest.toml`](file:///home/nathan/workspaces/nth/bella/manifest.toml) and remove `ast = ["_ast_unparse"]` from `[lazy_unsupported]`.
  2. In [`runtime/shims/annotationlib.py:289-304`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py#L289-L304) (`ForwardRef.__resolved_str__`), when `self.__ast_node__` is an `ast.AST`, run `_ExtraNameFixer(names)` on `copy.deepcopy(self.__ast_node__)` before calling `ast.unparse(node)` instead of unparsing to a string and re-parsing with `ast.parse`.
  3. In [`tools/closure.py:1027`](file:///home/nathan/workspaces/nth/bella/tools/closure.py#L1027), scan `runtime/shims/<name>.py` whenever a shim file exists on disk so shim dependencies are tracked in the closure.
  4. In [`pipeline/staging/boot/sitecustomize.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/boot/sitecustomize.py), consider also stubbing `unsupported_functions` from `closure.lock.json` so the replay model catches calls to `[lazy_unsupported]` stdlib functions.

---

### 3.3 [`_import_entry`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/dryrun.py#L176-L188) in `pipeline/staging/dryrun.py` Uses Filename Stem Instead of `"__main__"`

- **Location**: [`pipeline/staging/dryrun.py:176-188,223,230-231,262-265`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/dryrun.py#L176-L265)
- **Problem**:
  `_import_entry` executes the entry script under `name = os.path.splitext(os.path.basename(path))[0]` (or `"__bella_entry__"` if `name in sys.modules`). This causes three distinct bugs:
  1. **Call-site mismatch for definition-time `exec`/`eval` in the entry script**: During `dryrun.py`, `frame.f_globals["__name__"]` in the entry script is `stem` (e.g., `"prog"`), so `_site(frame)` records `f"{stem}:{qualname}:{lineno}"`. At runtime in [`sitecustomize.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/boot/sitecustomize.py), `frame.f_globals["__name__"]` is `"__main__"`, so `_site(frame)` is `f"__main__:{qualname}:{lineno}"` (which is also what `scan.scan` records in `exec_sites` at [`dryrun.py:231,242`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/dryrun.py#L231-L242)). Any decorator or helper in the entry script that uses `exec`/`eval` at definition time always misses at runtime and fails with `E-01`.
  2. **`sys.modules` collision when the entry script basename matches a stdlib module**: Because `_import_entry` registers `sys.modules[name] = module` under `stem` before executing it (and [`dryrun.py:223`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/dryrun.py#L223) inserts `dirname(args.entry)` at `sys.path[0]` even when `run.py` was passed `-P`), an entry script named e.g. `calendar.py` or `decimal.py` that imports that stdlib module imports its own partially-initialized module during `dryrun.py`, raising `AttributeError` (swallowed into `failed_imports`) and staging nothing.
  3. **`dryrun.py --modules-from LOCK --entry SCRIPT` drops all entry-script texts**: `_import_entry` records `_body()` as `stem` and discards its return value, while line 231 adds `"__main__"` to `program`. When `lock_modules` is non-empty (`--modules-from`), `wanted` ([`dryrun.py:262`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/dryrun.py#L262)) contains `"__main__"` but not `stem`, so line 265 filters out every text staged by the entry script.
- **Reproducer**:
  ```bash
  .venv/bin/python -c '
  import json, subprocess, sys, tempfile
  from pathlib import Path

  with tempfile.TemporaryDirectory() as tmp:
      # 3a: definition-time exec in entry module
      p1 = Path(tmp, "prog.py")
      p1.write_text("def dec(c):\n ns={}; exec(\"def f(s): return 7\", {}, ns); c.f=ns[\"f\"]; return c\n@dec\nclass C: pass\nprint(C().f())\n")
      r1 = subprocess.run([sys.executable, "pipeline/staging/run.py", str(p1)], capture_output=True, text=True)
      print("3a:", r1.returncode, r1.stderr.strip())

      # 3b: entry script named calendar.py run with -P
      p2 = Path(tmp, "calendar.py")
      p2.write_text("import calendar\nfrom dataclasses import dataclass\n@dataclass\nclass D:\n m: int = calendar.JANUARY\nprint(D())\n")
      r2 = subprocess.run([sys.executable, "pipeline/staging/run.py", "-P", str(p2)], capture_output=True, text=True)
      print("3b:", r2.returncode, r2.stderr.strip())

      # 3c: dryrun.py --modules-from + --entry
      j, b = Path(tmp, "a.json"), Path(tmp, "a.bin")
      subprocess.run([sys.executable, "-P", "pipeline/staging/dryrun.py", "--out", str(j), "--binary", str(b),
                      "--modules-from", "closure.lock.json", "--entry", "conformance/cases/C-8-08_staged_dataclass.py"], check=True)
      d = json.loads(j.read_text())
      print("3c: C-8-08 texts kept =", [t for t in d["texts"] if any("C-8-08" in x or "__main__" in x for x in t["by"])])
  '
  ```
  Output on `b838bc5`:
  ```text
  3a: 70 bella: refused: E-01: exec at __main__:dec:2 of a text the dry run did not stage (spec section 8)
  3b: 70 bella: refused: E-01: exec at dataclasses:_FuncBuilder.add_fns_to_class:499 of a text the dry run did not stage (spec section 8)
  3c: C-8-08 texts kept = []
  ```
- **Recommendation**:
  In [`_import_entry`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/dryrun.py#L176-L188), always load the entry script under the reserved module name `"__bella_entry__"` (never `stem`, avoiding any `sys.modules` collision with stdlib modules), and map `"__bella_entry__"` to `"__main__"` in [`_site(frame)`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/dryrun.py#L50-L51) and [`_loader_exec`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/dryrun.py#L105-L113). That keeps `if __name__ == "__main__":` false during the dry run while ensuring `_site`, `_body`, `wanted`, and `scan.scan` all consistently identify the entry module as `"__main__"`. Also pass `--safe-path` (or omit `sys.path.insert(0, dirname(args.entry))`) when `-P` is passed to [`run.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/run.py).

---

### 3.4 Missing Sibling Modules in `covered`, Unresolved PEP 810 `lazy import` Modules in `dryrun.py`, and Incomplete Cache Key in `run.py`

- **Location**: [`pipeline/staging/dryrun.py:224-237`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/dryrun.py#L224-L237) and [`pipeline/staging/run.py:80-92`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/run.py#L80-L92)
- **Problem**:
  1. **Sibling modules omitted from `covered` when running without `--program-lock`**: In [`dryrun.py:224-237`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/dryrun.py#L224-L237), `program` only records `args.program_module` and `args.entry`. When `run.py` runs a multi-file program without `--program-lock`, any sibling module `helper.py` imported by `args.entry` is never added to `program` / `covered`, so `tables_for_source` and `scan.scan` (for `namedtuple` probes) are never run on `helper.py`.
  2. **PEP 810 `lazy import` modules not executed during `dryrun.py`**: When an entry script or module executes `lazy import lazy_mod` (PEP 810), Python binds a `types.LazyImportType` proxy in the module's globals without importing `lazy_mod`. Unless `lazy_mod` was explicitly passed via `--program-module`, `lazy_mod`'s module body never runs during `dryrun.py`, so any `@dataclass` or `namedtuple` in `lazy_mod` is unstaged and fails with `E-01` when first used at runtime.
  3. **`run.py:program_artefact` cache key omits `--program-module` files**: In [`pipeline/staging/run.py:81-88`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/run.py#L81-L88), `paths = [script, *INPUTS]` (plus `program_lock`) never hashes the `.py` files of the `modules` extracted from `program_lock`, so edits to program/vendored modules can serve stale cached `.bin` files.
- **Reproducer**:
  ```bash
  .venv/bin/python -c '
  import subprocess, sys, tempfile
  from pathlib import Path

  with tempfile.TemporaryDirectory() as tmp:
      Path(tmp, "helper.py").write_text("import collections\ndef f(x: int) -> str:\n P = collections.namedtuple(\"P\", \"u v\")\n return str(P(x, x))\n")
      p1 = Path(tmp, "prog1.py")
      p1.write_text("import annotationlib, helper\nprint(annotationlib.get_annotations(helper.f, format=annotationlib.Format.STRING), helper.f(1))\n")
      r1 = subprocess.run([sys.executable, "pipeline/staging/run.py", str(p1)], capture_output=True, text=True)
      print("4a (sibling module):", r1.returncode, r1.stderr.strip())

      Path(tmp, "lazy_mod.py").write_text("from dataclasses import dataclass\n@dataclass\nclass Cfg:\n host: str = \"localhost\"\n")
      p2 = Path(tmp, "prog2.py")
      p2.write_text("lazy import lazy_mod\nif __name__ == \"__main__\":\n print(lazy_mod.Cfg())\n")
      r2 = subprocess.run([sys.executable, "pipeline/staging/run.py", str(p2)], capture_output=True, text=True)
      print("4b (PEP 810 lazy import):", r2.returncode, r2.stderr.strip())
  '
  ```
  Output on `b838bc5`:
  ```text
  4a (sibling module): 70 bella: refused: [P2+] annotationlib: this STRING form is not one the compiler could compute at build time (spec section 3, review log D-5)
  4b (PEP 810 lazy import): 70 bella: refused: E-01: exec at dataclasses:_FuncBuilder.add_fns_to_class:499 of a text the dry run did not stage (spec section 8)
  ```
- **Recommendation**:
  1. In [`dryrun.py`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/dryrun.py), after importing the entry script and program modules, resolve any `types.LazyImportType` values found in `vars(module)` of non-stdlib program modules (to a fixed point), and include in `program` every loaded module in `sys.modules` whose `__file__` is under the program/entry directory (outside `STDLIB_DIR` and `pipeline/staging`).
  2. In [`pipeline/staging/run.py:80-92`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/run.py#L80-L92), include the source paths of all `modules` in `paths` when computing `_key(...)`.

---

### 3.5 Four Additional Defects in `annotations.py`, `annotationlib.py`, `scan.py`, and `sitecustomize.py`

1. **[`pipeline/staging/annotations.py:52-59`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/annotations.py#L52-L59) — `_stable(value)` misses `ast.Set` inside `_Stringifier` ASTs (Hash-seed non-determinism)**:
   - `_stable(value)` returns `True` immediately for `isinstance(value, _Stringifier)`. When a set literal is nested inside an expression involving a `_Stringifier` (e.g., `def f(a: Annotated[int, {"p", "q"}]) -> None:`), `_Stringifier.__convert_to_ast` (`annotationlib.py:433-442`) iterates over the `set` in hash-seed order and builds an `ast.Set` inside the outer `_Stringifier.__ast_node__`.
   - Reproducer:
     ```bash
     .venv/bin/python -c '
     import subprocess, sys
     code = "import tempfile\nfrom pathlib import Path\nfrom pipeline.staging import annotations\nwith tempfile.TemporaryDirectory() as d:\n p=Path(d,\"m.py\"); p.write_text(\"from typing import Annotated\\ndef f(a: Annotated[int, {\\\"p\\\", \\\"q\\\"}]) -> None: pass\\n\")\n print(list(annotations.tables_for_source(str(p)).values())[0])"
     for s in ("0", "1"):
         print("seed", s, subprocess.run([sys.executable, "-c", code], env={"PYTHONHASHSEED": s}, capture_output=True, text=True).stdout.strip())
     '
     ```
     Output:
     ```text
     seed 0 {'is_class': False, 'string': {'a': "Annotated[int, {'p', 'q'}]", 'return': 'None'}, 'string_raises': None, 'unstable': None, 'second_raises': None}
     seed 1 {'is_class': False, 'string': {'a': "Annotated[int, {'q', 'p'}]", 'return': 'None'}, 'string_raises': None, 'unstable': None, 'second_raises': None}
     ```
   - **Fix**: When `isinstance(value, _Stringifier)`, check `node = getattr(value, "_Stringifier__ast_node__", None)` and return `False` if `isinstance(node, ast.AST)` and any node in `ast.walk(node)` is an `ast.Set`.

2. **[`pipeline/staging/annotations.py:69-70`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/annotations.py#L69-L70) & [`pipeline/staging/boot/sitecustomize.py:124-130`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/boot/sitecustomize.py#L124-L130) — `_raised` and `_Hooks.exception` corrupt structured exception payloads**:
   - `_raised(exc)` records `[type(exc).__name__, str(exc)]` and `_Hooks.exception` reconstructs `cls(recorded[1])`.
   - For `KeyError('missing')`, `str(exc)` is `"'missing'"`, so `KeyError(recorded[1])` produces `KeyError("'missing'")` (with literal quotes in `.args`).
   - For `AttributeError` (e.g., `(1).no_such_attr`), reconstructing via `AttributeError(recorded[1])` loses `.name` (`None` instead of `'no_such_attr'`, violating D-08).
   - **Fix**: Record `exc.args` and `getattr(exc, "name", None)` (or reconstruct with `cls(*args)` and restore `name` when present).

3. **[`runtime/shims/annotationlib.py:822-825`](file:///home/nathan/workspaces/nth/bella/runtime/shims/annotationlib.py#L822-L825) — `call_annotate_function` refuses custom `__annotate__` functions and resolved PEP 695 `evaluate` functions under `Format.FORWARDREF`**:
   - Unlike `Format.STRING` (lines 778–784), `Format.FORWARDREF` checks `if compiled is None or _is_evaluate: _bella.refuse(...)` *before* attempting `annotate(Format.VALUE)` (or checking if `annotate(Format.VALUE_WITH_FAKE_GLOBALS)` raises `NotImplementedError`).
   - Thus a custom `def my_annotate(fmt):` that implements `Format.VALUE` and raises `NotImplementedError` for other formats, or `call_evaluate_function(Alias.evaluate_value, Format.FORWARDREF)` on a resolved `type Alias = int | str`, is refused under the replay even though CPython returns `annotate(Format.VALUE)`.
   - **Fix**: Try `annotate(Format.VALUE)` first (or handle `NotImplementedError` from `VALUE_WITH_FAKE_GLOBALS`), and only consult `compiled` if `annotate(Format.VALUE)` raises an `Exception`.

4. **[`pipeline/staging/scan.py:100-120`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/scan.py#L100-L120) & [`pipeline/staging/boot/sitecustomize.py:53,85-89`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/boot/sitecustomize.py#L85-L89) — Keyword arguments in `namedtuple` probes, `(site, kind, text)` key, and `exec(..., closure=...)`**:
   - In [`scan.py:100-101`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/scan.py#L100-L101), `if name in self.namedtuple_names and len(node.args) >= 2:` misses calls that pass `field_names=` (or `typename=`) by keyword, e.g., `collections.namedtuple("Pt", field_names="u v")` inside a function. Also, `scan.py:98` only matches bare `exec`/`eval`/`compile`, missing `builtins.exec`/`builtins.eval`/`builtins.compile`.
   - In [`dryrun.py:288`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/dryrun.py#L288) and [`sitecustomize.py:53,71`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/boot/sitecustomize.py#L53-L71), `compiled` is keyed by `(site, text)` instead of `(site, kind, text)`, so an `exec` and `eval` at the same line would collide or cross-match.
   - In [`sitecustomize.py:85-89`](file:///home/nathan/workspaces/nth/bella/pipeline/staging/boot/sitecustomize.py#L85-L89), `exec` accepts `*, closure: Any = None` and drops `closure` instead of refusing when `closure is not None` (since a string `exec` in Python cannot take a `closure`).
