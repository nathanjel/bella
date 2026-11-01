# Bella — Target Programs, Increments & Conformance Review (03)

- **Date:** 2026-11-01
- **Reviewer:** `gemini-4-argon-high`
- **Sequence:** 03
- **Scope:** Commits `6730ed8` through `8b8eb0d` — closure review fixes (`RL-52`..`RL-70`), decisions `D-5` and `D-6` (`spec v0.7`), conformance corpus growth (57 cases + `D-20` simulation + `[P2+]` refusal checks), Mandelbrot slice measurement, import and recording of the six target programs, licence register (`L-01`..`L-07`), and per-target closure / Phase-1 increment computation (`1a`, `1b`, `1c`).

---

## 1. Executive Summary & Verification of Recent Changes

All findings from the previous closure review (`gemini-4-argon-high-02`, `RL-52`..`RL-70`) were cleanly reproduced, tested, and resolved in `6730ed8` and `b2e9501`:
- **Runtime annotations (`D-5` / `RL-58`)**: `docs/dialect-spec.md` (v0.7, §§3 and 7) now admits annotations at runtime in the `VALUE` format, `FORWARDREF` when every name resolves, and `STRING` via a compiler-generated `__annotate__`, with `C-3-13_annotations_at_runtime.py` pinning `@dataclass`, `NamedTuple`, `TypedDict`, and `@singledispatch` registration.
- **Observable Phase-1 omissions (`D-6` / `RL-57`)**: Registered as deviation `D-20` in `docs/deviations.toml` and `docs/dialect-spec.md` §11, and verified both by `C-7-01_hash_and_hmac_surface.py` (kept surface) and `C-7-03_phase1_omissions_observable.py` (simulated `D-20` trace via `conformance/simulate/sitecustomize.py`).
- **`_hmac` mapped (`RL-61`)**: `_hmac` is now in `[phase1].mapped`, preserving `hmac.digest(memoryview(...), ...)` (`C-7-01`).
- **`tools/closure.py` & `Makefile` fixes (`RL-52`..`RL-56`, `RL-63`..`RL-70`)**: All static/dynamic closure edge cases now have unit tests in `tools/tests/test_closure.py`.

Running `make check` on the pinned CPython `3.15.2+20261026` and host `g++ (GCC) 16.2.1` passes in full:
- `make closure`: 175 modules (`112 compiled, 19 core, 37 mapped, 7 shim`), matching `closure.lock.json`.
- `make targets-closure`: 6 target locks generated in `targets/closure/*.lock.json` and `targets/closure-summary.json`.
- `make lint`: `ruff` and three `mypy` passes (`packages` = 39 files; `conformance/cases` + `pipeline/examples` with `--disallow-any-explicit` = 70 files; `targets/drivers` with `--disallow-any-explicit` = 6 files) all pass with 0 issues.
- `make test`: 74 pytest tests pass + `refmodel.selftest` (3,000 operations over 50 worlds, 65,395 cache hits, 0 mismatches).
- `make verify`: 58/58 conformance expectations reproduced on CPython 3.15.2 (55 `[P1]` + `C-7-03 [D-20]` + 4 `[P2+]`).
- `make slice` & `make int-test`: 5/5 slice examples (`collatz`, `fib`, `loops`, `mandelbrot` pass; `fact_big` expected XFAIL) and 2,000 differential `bella::Int` cases pass.
- `make targets-check`: All 6 target programs match their 3.15.2 recordings under `PYTHONHASHSEED=0` and `1` (and we independently verified they also match when run with `D-20` omissions and `importlib.resources` blocked).

At the same time, computing the target closures on CPython 3.15.2 (`8b8eb0d`) and cross-checking the six targets against `docs/dialect-spec.md` v0.7 surfaces **three architectural/spec issues** and **four tooling bugs** that should be addressed before starting the first end-to-end target compilation path.

---

## 2. Architectural & Specification Findings

### 2.1 `unicodedata` was decided `[P2+]` (`2c456fc`), but remains in `manifest.toml` `[phase1].mapped` and Increment `1a` — and removing it exposes a whole-function `[lazy_unsupported]` trap
- **Where:** `manifest.toml:89`, `targets/closure-summary.json:231`, `docs/DECISIONS.md:217-219`, `docs/dialect-spec.md:118,139`, `docs/targets.md:28-29,266-268`.
- **Finding:**
  1. In commit `2c456fc` (*"Keep `unicodedata` `[P2+]`: lower `cli_easy_slugs`' requirements"*), the author decided Option (c): `unicodedata` stays `[P2+]` in Phase 1 (matching `docs/dialect-spec.md` §§6 and 7), and modified `targets/drivers/cli_easy_slugs.py` to drop non-ASCII bytes (`text.encode("ascii", "ignore").decode()`) rather than calling `unicodedata.normalize` and `unicodedata.combining`.
  2. However, `"unicodedata"` was never removed from `manifest.toml`'s `[phase1].mapped` list (line 89). Because `tools/closure.py` follows every `lazy` (in-function) edge whose target is in `manifest.supported`, `unicodedata` is still reached by `cli_easy_slugs` (via `re -> re._parser:lazy:343`) and by every other target program. Consequently, `"unicodedata": "mapped"` is still in `closure.lock.json`, in Increment `1a` (`targets/closure-summary.json:231`), and in all six `targets/closure/*.lock.json` files.
  3. **Why simply removing `unicodedata` from `mapped` and adding `[lazy_unsupported]` fails:**
     In CPython 3.15.2, three Phase-1 stdlib modules import `unicodedata` inside core functions that execute on ordinary ASCII inputs:
     - `re._parser`: `_class_escape` (line 343) and `_escape` (line 403) execute `import unicodedata` only inside `elif c == "N" and source.istext:` (for `\N{CHARNAME}` named escapes), but `_escape` and `_class_escape` are called for **every** backslash escape in any regex (`\d`, `\w`, `\s`, `\b`, `\.`, etc., including `C-7-07_text_modules.py`).
     - `traceback`: `_compute_suggestion_error` (line 1887, called when formatting `AttributeError`, `NameError`, or `ImportError`, including `C-7-02_traceback_formats_module_not_found.py`), `_str_width` (line 1026), and `_zip_display_width` (line 1013) only import `unicodedata` inside `if not wrong_name.isascii():` / `if ord(c) >= 128:` / `if not line.isascii():`.
     - `urllib.parse`: `_checknetloc` (line 514, called by `urlsplit` on every URL with a netloc, including `C-7-07_text_modules.py`) returns immediately on `if not netloc or netloc.isascii(): return` and only imports `unicodedata` for non-ASCII netlocs.
     Because Bella's `[lazy_unsupported]` rule (`D-1` / `spec §7`) refuses the **entire outermost enclosing function on every path through it**, declaring `unicodedata` in `[lazy_unsupported]` would refuse `re._parser._escape`, `re._parser._class_escape`, `traceback._compute_suggestion_error`, and `urllib.parse._checknetloc` on all ASCII inputs!
- **Recommendation:**
  Move `unicodedata` from `[phase1].mapped` to `[phase1.shim]` (a shim module whose `lookup`, `normalize`, `combining`, `category`, `east_asian_width`, and `iter_graphemes` functions raise the `[P2+]` milestone-naming error when called, and whose `import unicodedata` statement succeeds). That honours the `2c456fc` decision (`unicodedata` is `[P2+]`, no UCD table mapping in Phase 1a beyond `str` methods) while allowing `re._parser`, `traceback`, and `urllib.parse` to run all ASCII paths unadapted and fail with `[P2+]` only when `\N{...}` or non-ASCII netloc/suggestion normalization is actually called.

### 2.2 Increment `1a` contains 85% of the Phase-1 manifest (149/175 modules, 71,219 lines) due to uncalled stdlib functions and `first-use` edges
- **Where:** `targets/closure-summary.json:78-255`, `tools/closure.py:983-996,1133-1155`, `docs/DECISIONS.md:212-216,227-233`, `TODO.md:67-94`, `docs/targets.md:19-23,260-264`.
- **Finding:**
  1. Decision `D-2` (`RL-48`) split Phase 1 into `1a`, `1b`, and `1c` so the first end-to-end compilation milestone would not have to compile the entire stdlib closure at once.
  2. However, defining `1a` as the union of the static module-level closures of the three easy targets puts **149 out of 175 manifest modules (85% of Phase 1, 71,219 compiled source lines)** into `1a`, leaving only **6 modules (2,739 lines)** in `1b` (`html`, `html.entities`, `signal`, `_signal`, `importlib._bootstrap`, `importlib._bootstrap_external`) and **25 modules** in `1c`.
  3. Tracing the `reached_by` chains in `targets/closure/*.lock.json` shows why `cli_easy_slugs` (a 62-line script importing only `argparse`, `re`, `sys`, `pathlib`) reaches **112 modules** (`72 compiled, 15 core, 20 mapped, 4 shim, 1 program`), including `ast`, `dis`, `opcode`, `tokenize`, `token`, `_tokenize`, `_ast`, `inspect`, `dataclasses`, `typing`, `urllib.parse`, `ipaddress`, `difflib`, and `traceback`:
     - `re` eagerly imports `enum`; `enum.EnumType.__signature__` (`enum.py:1119`, a `@property` only invoked if a user calls `inspect.signature(EnumCls)`) has `from inspect import Parameter, Signature`, which pulls `inspect -> ast, dis, opcode, _opcode_metadata, tokenize, token, _tokenize, _ast, linecache` (~8.7k lines + 2 core modules) into `cli_easy_slugs` and `1a`. (Note that `docs/targets.md:260-264` still assumes only `tomlkit`, `mistune`, and `pycodestyle` reach `dataclasses -> inspect -> ast/dis/tokenize`.)
     - `argparse` (`argparse.py:95`) has `lazy import _colorize` (`first-use`), and `_colorize` (`_colorize.py:6-7`) has `from dataclasses import dataclass, field, Field` (`eager`) and `lazy from typing import ...` (`first-use`).
     - `inspect._main()` (`inspect.py:3461`, the `python -m inspect` CLI entry point) and `random._parse_args()` (`random.py:1021`, the `python -m random` CLI entry point) lazily import `argparse`, causing `service_easy_tokens` and `data_easy_sales` to pull in `argparse`, `gettext`, `shutil`, and `difflib`.
     - `pathlib.PurePath.as_uri` (`pathlib/__init__.py:544`) lazily imports `urllib.parse`, which eagerly imports `ipaddress` (2,300 lines).
  4. Measuring what the three easy targets actually load in `sys.modules` when executing their recorded workloads (with omitted modules blocked) shows a large gap between module-level static closure and runtime execution:
     - `cli_easy_slugs`: lock has **112** modules; **62** are present in `sys.modules` at exit (**14** loaded after interpreter startup); **50** modules in its lock are never loaded (`_ast`, `_colorize`, `_opcode`, `_tokenize`, `annotationlib`, `ast`, `dataclasses`, `difflib`, `dis`, `inspect`, `ipaddress`, `opcode`, `token`, `tokenize`, `traceback`, `typing`, `unicodedata`, `urllib`, `urllib.parse`, etc.).
     - `service_easy_tokens`: lock has **144** modules; **91** in `sys.modules` at exit (**37** post-startup); **53** never loaded (`argparse`, `ast`, `dataclasses`, `difflib`, `dis`, `gettext`, `inspect`, `ipaddress`, `opcode`, `shutil`, `token`, `tokenize`, `traceback`, etc.).
     - `data_easy_sales`: lock has **146** modules; **83** in `sys.modules` at exit (**35** post-startup); **63** never loaded (`argparse`, `ast`, `dataclasses`, `difflib`, `dis`, `hashlib`, `inspect`, `ipaddress`, `opcode`, `shutil`, `token`, `tokenize`, `traceback`, `typing`, `zlib`, etc.).
- **Recommendation:**
  Keep `targets/closure-summary.json` as the honest module-level inventory, but for the compiler pipeline (`TODO.md` task 4):
  1. Compile target programs with **function/class-level reachability (dead-function pruning)** or on-demand compilation of `lazy` (in-function) and `first-use` imports, so uncalled stdlib functions (`EnumType.__signature__`, `inspect._main`, `random._parse_args`, `PurePath.as_uri`) do not force `cli_easy_slugs` to compile `inspect`, `ast`, `dis`, `tokenize`, `dataclasses`, `urllib.parse`, and `ipaddress`.
  2. Sub-stage `1a` explicitly by target (`1a.1: cli_easy_slugs`, `1a.2: service_easy_tokens`, `1a.3: data_easy_sales`), matching `TODO.md` task 4's "done when".

### 2.3 Unlisted Spec vs. Target Contradictions in `data_tricky_toml` (`tomlkit`) and `copy` (`[P1]` vs `[P2+]`)
- **Where:** `docs/dialect-spec.md:57,60,104`, `targets/targets.toml:49-53`, `docs/targets.md:155-165,271-302`, `targets/vendor/tomlkit/items.py:564-572,632,1060,2254`.
- **Finding:**
  `docs/targets.md` §5 lists the spec/manifest questions surfaced by the tricky targets (`inspect.signature` at runtime, dead `compile()` in `pycodestyle`, `optparse` + `configparser`), but omits two `[P2+]` restrictions in `docs/dialect-spec.md` that `data_tricky_toml` (and `copy` in Phase 1a) hit directly:
  1. **Builtin/slotted-base + stateful class multiple inheritance (`[P2+]` in spec §3 line 57 and §5 line 104):**
     `tomlkit` defines `class String(str, Item)`, `class Integer(Item, _CustomInt)`, `class Float(Item, _CustomFloat)`, `class Array(Item, _CustomList)`, `class AbstractTable(Item, _CustomDict)`, and `class DateTime(Item, datetime)` (where `_pydatetime.datetime` defines 10 `__slots__`, and `Item` has no `__slots__` and assigns `self._trivia = trivia`). Both `targets/targets.toml:50` and `targets/drivers/data_tricky_toml.py:9` explicitly call this *"stateful multiple inheritance, tier 3"*, which `docs/dialect-spec.md` §5 (line 104) marks **`[P2+]`** (*"A `[P2+]` tier compiles to an error naming the milestone, not to a slower path"*).
  2. **`__reduce__` / `__reduce_ex__` / `__getstate__` / `__setstate__` (`[P2+]` in spec §3 line 60 vs `[P1]` `copy`):**
     `docs/dialect-spec.md` §3 (line 60) marks `Pickling (__reduce__, __getstate__, __setstate__)` as `[P2+]`. Yet `copy` and `copyreg` are `[P1]` (`compiled`), and CPython's `copy.copy(x)` and `copy.deepcopy(x)` on **any** user class without a custom `__copy__`/`__deepcopy__` call `x.__reduce_ex__(4)` (which on `object` calls `x.__getstate__()`) and reconstruct via `copyreg._reconstructor` / `__setstate__`. Furthermore, `tomlkit.items.Item` (`items.py:564-571`) implements `copy.copy()` by overriding `__reduce__`, `__reduce_ex__`, and `_getstate`. (Currently `C-7-06` only tests `copy.copy`/`copy.deepcopy` on `dict` and `list`, which take `_copy_builtin_containers` and bypass `__reduce_ex__`.)
- **Recommendation:**
  1. In `docs/dialect-spec.md` §3, move `object.__reduce_ex__`, `__reduce__`, `__getstate__`, `__setstate__`, and `copyreg.__newobj__`/`_reconstructor` (as used by `copy.copy` and `copy.deepcopy`) to `[P1]`, keeping only the `pickle` module itself `[P2+]`, and add a conformance case for `copy.copy` / `copy.deepcopy` on user classes (slotted, unslotted, and custom `__getstate__`/`__reduce_ex__`).
  2. Add `tomlkit`'s builtin/slotted-base + `Item` multiple inheritance to `docs/targets.md` §5 so the author can decide before Phase 1b whether single-payload-base + attribute-mixin inheritance is `[P1]` (updating spec §§3 and 5 and `refmodel/objects.py`) or part of a tier-3 milestone.

---

## 3. Tooling & Harness Bugs

### 3.1 `tools/closure.py` — `Program.manifest_for` overwrites per-module entries instead of merging, and stale/misspelled per-target declarations on unreached modules are silently ignored
- **Where:** `tools/closure.py:138-149,1030-1037,1051-1056,1074-1080`.
- **Finding:**
  1. **Shallow dict union overwrites stdlib entries:**
     In `Program.manifest_for` (lines 144–149):
     ```python
     return replace(
         manifest,
         omissions=manifest.omissions | {k: set(v) for k, v in omissions.items()},
         lazy_unsupported=manifest.lazy_unsupported | {k: set(v) for k, v in lazy.items()},
         dynamic=manifest.dynamic | {k: {site: list(ts) for site, ts in v.items()} for k, v in dynamic.items()},
     )
     ```
     If a target's `[<target>.closure]` table declares an entry for a module `k` that already has an entry in `manifest.toml`, `|` replaces `manifest`'s set/dict for `k` instead of unioning `manifest.omissions.get(k, set()) | set(v)`.
  2. **Unreached modules in `[<target>.closure]` (and in `manifest.toml` `[omissions]` / `[lazy_unsupported]`) pass silently:**
     Because `_compute_closure` cannot distinguish `program.tables` entries from `manifest.toml` entries, line 1075 (`if program is not None and module not in infos: continue`), line 1031 (`if importer not in infos: continue`), and line 1052 (`if importer in infos:`) skip any module not in `infos`.
     - If `targets/targets.toml` has a typo in a module name under `[<target>.closure.dynamic]`, `[<target>.closure.lazy_unsupported]`, or `[<target>.closure.omissions]` (e.g. `[service_tricky_markdown.closure.dynamic."mistune.plugns"]`), `tools/closure.py --target` silently ignores it and exits 0.
     - Even when `program is None` (`make closure`), a stale module key in `manifest.toml`'s `[omissions]` or `[lazy_unsupported]` that is not in `infos` is silently ignored (whereas `[replaced]` at line 1059 and `[dynamic]` at line 1080 report `"which the closure does not reach"`).
- **Reproducer:**
  ```python
  from pathlib import Path
  from tools import closure

  m = closure.Manifest.load(Path("manifest.toml"))
  p = closure.Program.load("cli_easy_slugs")
  p.tables = {
      "dynamic": {"mistune.typo": {"f: x": []}},
      "lazy_unsupported": {"humanize.typo": ["importlib.resources"]},
      "omissions": {"no_such_mod": ["foo"]},
  }
  _, problems = closure.compute_closure(m, p)
  assert problems == []  # all three invalid entries are silently ignored
  ```
- **Recommendation:**
  Merge per-module sets/dicts in `Program.manifest_for`, check that every module key in `manifest.omissions` and `manifest.lazy_unsupported` is in `infos` when `program is None`, and check that every module key in `program.tables` (`omissions`, `lazy_unsupported`, `dynamic`) is in `infos` when `program is not None`.

### 3.2 `tools/closure.py` — `Program.load` and `Program.owns` ignore `targets.toml`'s `packages` list and grant `status = "program"` to all of `targets/drivers/` and `targets/vendor/`
- **Where:** `tools/closure.py:131-153,1251-1256`.
- **Finding:**
  1. `Program.load` sets `dirs = (driver.parent, here / "vendor")` for every target, ignoring `spec["packages"]` in `targets/targets.toml`, and `Program.owns(path)` returns `True` for any file under `targets/drivers/` or `targets/vendor/`. If `cli_easy_slugs` (`packages = []`) or any other target accidentally imports an undeclared package from `targets/vendor/` or another driver from `targets/drivers/`, `Program.owns` marks it `status = "program"` (`supported = True`) instead of reporting an error.
  2. Restricting `Program.owns` to the target's driver path (`here / spec["driver"]`) plus the declared packages in `spec["packages"]` (`here / "vendor" / pkg` and `here / "vendor" / f"{pkg}.py"`) enforces that `targets.toml`'s `packages` list is exact.
  3. Also in `tools/closure.py`: `main()` returns early at line 1252 (`if args.target or args.all_targets: return _targets_main(...)`) before checking `manifest.platform.mismatches()` at line 1255.

### 3.3 `targets/run_targets.py` — `check` does not verify `"authoritative": true` and does not run under the Phase-1 (`D-20`) simulation
- **Where:** `targets/run_targets.py:96-123`, `TODO.md:77-78`, `docs/DECISIONS.md:205-208`.
- **Finding:**
  1. `run_targets.py:record` writes `"authoritative": authoritative` into `targets/expected/<name>.json`, and the module docstring states that `--allow-unpinned` records a non-authoritative marker *"as the conformance harness does"*. However, unlike `conformance/harness.py`, `run_targets.py:check` never checks `meta.get("authoritative")`, so non-authoritative recordings pass `make targets-check` silently.
  2. `TODO.md:77-78` states that the targets are checked *"under two hash seeds and under the phase-1 omissions (`make targets-check`, in CI)"*. Currently `run_targets.py:check` only runs `seeds = [0, 1]` on unblocked CPython (where C `_decimal`, C `_datetime`, OpenSSL `_hashlib`, and `importlib.resources` are present). Adding a `D-20` simulation run (when `args.runner is None`) to `run_targets.py:check` will verify the pure-Python `_pydecimal`, `_pydatetime`, and OpenSSL-less `hashlib` paths in CI on every push.
  3. Minor: `run_targets.py:116-118` only prints `_diff(want_out, r["stdout"])` under `--verbose`, omitting `_diff(want_err, r["stderr"])` when `stderr` mismatches.

### 3.4 `tools/score_candidate.py` — Submodule manifest check false positive (`importlib.resources`) and non-`.py` file parsing on `targets/vendor/*`
- **Where:** `tools/score_candidate.py:192-207`, `docs/targets.md:309`.
- **Finding:**
  1. Line 204 computes `outside = sorted(m for m in scan.stdlib if m.split(".")[0] not in supported and m not in supported)`. Because top-level `"importlib"` and `"urllib"` are in `supported`, any submodule outside the manifest (`importlib.resources`, `urllib.request`, `importlib.metadata`) satisfies `m.split(".")[0] in supported` and is misreported under `stdlib in manifest` instead of `stdlib OUTSIDE`. (For `targets/vendor/humanize`, `score_candidate.py` prints `importlib.resources` under `stdlib in manifest` and `stdlib OUTSIDE: -`.)
  2. Running the command in `docs/targets.md:309` (`python3 -I tools/score_candidate.py --manifest manifest.toml targets/drivers/*.py targets/vendor/*`) passes `targets/vendor/LICENSE.*` as file arguments; `score()` tries to `ast.parse` non-`.py` files and reports `dynamism: {'syntax error: invalid syntax': 1}` for all five license files.
  3. `score_candidate.py` walks into `if TYPE_CHECKING:` blocks, reporting `typing_extensions` (in `itsdangerous`) and `_typeshed` (in `tomlkit`) as third-party imports.

### 3.5 Minor Notes in `conformance/harness.py` and `docs/deviations.toml`
- **`conformance/harness.py:252`**: `cmd_check` builds `cmd` with `args.runner.split()` rather than `shlex.split(args.runner)` (unlike `targets/run_targets.py:75`), which will split quoted arguments containing spaces.
- **`docs/deviations.toml:126` & `docs/dialect-spec.md:233` (`D-20`)**: Both state that *"`shutil` offers only the `gztar`, `tar` and `zip` archive formats"*. Since calling `shutil.make_archive` / `unpack_archive` on those built-in formats is `[P2+]` (`C-7-04`), consider phrasing this as *"`shutil.get_archive_formats()` and `get_unpack_formats()` list only `gztar`, `tar` and `zip` (calling built-in archive formats is `[P2+]`, C-7-04)"*.

---

## 4. Recommended Next Steps

1. **Resolve `unicodedata` in `manifest.toml` (Finding 2.1):** Move `unicodedata` from `[phase1].mapped` to `[phase1.shim]` (raising the `[P2+]` error when called) and regenerate `closure.lock.json` and `targets/closure*` so `unicodedata` is genuinely `[P2+]` while `re._parser`, `traceback`, and `urllib.parse` continue to work on ASCII inputs.
2. **Tighten `tools/closure.py` and `targets/run_targets.py` (Findings 3.1–3.3):**
   - Merge per-module sets/dicts in `Program.manifest_for` and fail on unreached module keys in `[omissions]`, `[lazy_unsupported]`, and `[<target>.closure]`.
   - Restrict `Program.owns` to the target's driver and its declared `packages` in `targets.toml`.
   - Check `"authoritative": true` and run a `D-20`-simulated pass in `targets/run_targets.py:check`.
3. **Clarify `copy` (`__reduce_ex__`/`__getstate__`) and `tomlkit` MI in `docs/dialect-spec.md` & `docs/targets.md` (Finding 2.3):** Move the `copy` object-reduction protocol to `[P1]` in spec §3 (with a conformance case on user classes) and record `tomlkit`'s builtin/slotted-base + `Item` multiple inheritance in `docs/targets.md` §5.
4. **Proceed to Task 5 (Staging Prototype) and Task 4 (`cli_easy_slugs` compilation path) with dead-function / lazy-import pruning (Finding 2.2):** Prototype `__annotate__` + `annotationlib` shim and staging (`C-3-13`), and ensure the compiler does not have to compile uncalled stdlib functions (`EnumType.__signature__ -> inspect -> ast/dis/tokenize`, `PurePath.as_uri -> urllib.parse -> ipaddress`) when compiling `cli_easy_slugs`.
