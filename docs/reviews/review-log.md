# Review log

Every finding from an external review, its verdict, and what happened to it. Reviews are input,
not authority: each finding is reproduced against the pinned CPython (or checked in the code)
before it is accepted, and every reviewer's findings are weighed alike. A confirmed defect that
can be fixed without changing the design is fixed with a failing test or conformance case first;
anything that would change the design, the specification or the build plan goes to
[Open for discussion](#open-for-discussion) with a recommendation.

**Status on 2026-11-01:** 87 findings from seven reviews: 65 fixed (most in commit `0d92b51`,
RL-37 with decision D-3, RL-23 with D-1, RL-38 with Gate 0 task 1, RL-52 to RL-70 after the
closure reviews, RL-57 with D-6, RL-71 to RL-86 after the target reviews, RL-72, RL-73, RL-77
and RL-80 with D-7, D-8, D-9 and D-11, RL-50 and RL-58 with Gate 0 task 5), 10 already done
before or because of the review, 4 planned (D-2 and D-10, accepted by the author), 2 deferred,
3 refuted and 3 checked with no issue. Nothing is open for discussion: the author decided D-1
to D-11 on 2026-11-01. The staging prototype raises its own questions, S-1 to S-5 in
`docs/staging.md`.

## Reviews received

| Date | Reviewer | File | Scope | Ran against |
| --- | --- | --- | --- | --- |
| 2026-11-01 | astra-low (A1) | [2026-11-01-astra-low-01-design-codebase-review.md](2026-11-01-astra-low-01-design-codebase-review.md) | design and Gate-0 code | CPython 3.14.8, GCC 16.2.1 |
| 2026-11-01 | astra-low (A2) | [2026-11-01-astra-low-02-python-version-review.md](2026-11-01-astra-low-02-python-version-review.md) | choice of reference Python | release notes; Bella not run on 3.15.2 |
| 2026-11-01 | gemini-4-argon-high (G) | [2026-11-01-01-gemini-4-argon-high-scaffold-architecture-review.md](2026-11-01-01-gemini-4-argon-high-scaffold-architecture-review.md) | design and Gate-0 code | CPython 3.14.8, GCC 16.2.1 |
| 2026-11-01 | astra-low (A3) | [2026-11-01-astra-low-03-stdlib-closure-review.md](2026-11-01-astra-low-03-stdlib-closure-review.md) | Gate 0 task 1: closure tool, manifest and lock at `b40ef2d` | CPython 3.15.2 (pinned uv build) |
| 2026-11-01 | gemini-4-argon-high (G2) | [2026-11-01-02-gemini-4-argon-high-stdlib-closure-review.md](2026-11-01-02-gemini-4-argon-high-stdlib-closure-review.md) | task 1 and the review-log fixes, `f56d495` to `b40ef2d` | CPython 3.15.2, GCC 16.2.1 |
| 2026-11-01 | astra-low (A4) | [2026-11-01-astra-low-04-target-increment-review.md](2026-11-01-astra-low-04-target-increment-review.md) | the target programs and the computed increments, `b40ef2d` to `8b8eb0d` | CPython 3.15.2 (pinned uv build) |
| 2026-11-01 | gemini-4-argon-high (G3) | [2026-11-01-03-gemini-4-argon-high-targets-increments-review.md](2026-11-01-03-gemini-4-argon-high-targets-increments-review.md) | `6730ed8` to `8b8eb0d`: corpus, targets, licence register, increments | CPython 3.15.2, GCC 16.2.1 |
| 2026-10-30 | external, rounds 1-3 | [round-1.md](round-1.md), [round-2.md](round-2.md), [round-3.md](round-3.md) | design documents | resolved in design sections 13-15 |

All findings below were re-checked on CPython 3.15.2 (the pin since `f56d495`). Several of G's
reproducers name APIs that do not exist (`CallSite`, `ModelClass`, `NarrowCert`, `CertKind`);
they were rewritten against the real ones (`Site`, `RefClass`, `RangeCertificate`) before judging.

**Verdicts:** Confirmed, Partly confirmed, Refuted, No issue (checked, nothing wrong).
**Status:** Fixed (commit), Done (already applied before the review), Discuss (see below),
Deferred (tracked in `TODO.md`), Known (already a Gate-0 task), Planned (a design change the
author accepted, scheduled in `TODO.md`).

## Findings

### Toy C++ emitter

| ID | From | Finding | Verdict | Status | Evidence and fix |
| --- | --- | --- | --- | --- | --- |
| RL-01 | A1 #1, G 2.2.3 | Binary operands and comparisons evaluated right to left | Confirmed: `f(1) + f(2)` printed 2, 1 | Fixed `0d92b51` | Operands bound in order whenever the order is observable (a call in an operand, or two operands that can raise). Also found: `range(a, b)` evaluated `b` first; fixed. Test `test_binary_and_comparison_operands_evaluate_left_to_right`, `test_range_arguments_evaluate_left_to_right` |
| RL-02 | A1 #2, G 2.2.4 | `for i in range(...)` used `i` as the C++ counter | Confirmed: 3 instead of 2 after the loop, 0 instead of 9 on an empty range, body assignment changed the iteration | Fixed `0d92b51` | Hidden counter, target assigned at the top of each iteration. Test `test_range_loop_target_keeps_python_meaning` |
| RL-03 | A1 #3, G 2.2.5.5 | Locals zero-initialised, `global` ignored, `return Int(0)` on fall-through | Confirmed: `global x` assignment lost; `h(0)` printed 0, not None | Fixed `0d92b51` | `global` honoured; a definite-assignment check refuses reads of possibly unassigned names, calls before the `def`, functions that may fall off their end, and the None value of a procedure (`Unsupported`, never a default) |

### Frontend, wf1 and eval1

| ID | From | Finding | Verdict | Status | Evidence and fix |
| --- | --- | --- | --- | --- | --- |
| RL-04 | A1 #5, G 2.2.2 | Comprehension helpers hoisted to module scope | Confirmed: `def f(x): return [x + i ...]` rejected; nested comprehensions too | Fixed `0d92b51` | Helper defined in the comprehension's own scope; inner helpers inside outer ones; the outermost iterable stays in the enclosing scope. Test `test_comprehension_sees_enclosing_function_scope` |
| RL-05 | G 2.2.1 | Chained-comparison temporaries recognised only in expression statements | Confirmed: `if 1 < x < 3` failed wf1 | Fixed `0d92b51` | wf1 collects bindings from every statement's expressions. Test `test_chained_comparison_in_every_statement_position` |
| RL-06 | G 2.2.1 | Temporaries visible in `globals()`/`locals()`; emitter cannot compile `__bind__` | Confirmed (observable only after RL-07) | Fixed `0d92b51` | Synthetic names are hygienic (never collide with program identifiers), recorded on `Module.synthetic` and stored apart from program bindings; the emitter compiles `__bind__`. Tests `test_synthetic_names_are_not_visible_in_globals`, `..._do_not_collide_with_user_names` |
| RL-07 | found 2026-11-01 while reproducing RL-06 | eval1 handed `globals()`, `locals()`, `vars()`, `dir()`, `eval`, `exec`, `compile` to the host interpreter | Confirmed: `globals()` returned eval1's own module dict | Fixed `0d92b51` | Intrinsics: exact at module level, `Unsupported` inside functions until modelled; `eval`/`exec`/`compile` refused (E-01). Test `test_eval1_does_not_leak_the_host_interpreter_state` |
| RL-08 | G 2.2.5.1 | `global`/`nonlocal` inside a nested block dropped | Confirmed | Fixed `0d92b51` | Declarations collected from the whole body, not nested defs. Test `test_global_declared_in_a_nested_block` |
| RL-09 | G 2.2.5.2 | `with` called `type(m).__enter__(m)`, bypassing descriptor binding | Confirmed: desugared code raised TypeError for a staticmethod `__enter__` | Fixed `0d92b51` | `__special__` = CPython's special-method lookup; `__exit__` looked up before `__enter__` (measured on 3.15.2); TypeError when missing. Test `test_with_desugaring_binds_through_the_descriptor_protocol` |
| RL-10 | G 2.2.5.3 | Unbound free variable fell through to the global | Confirmed: printed "global" instead of NameError | Fixed `0d92b51` | NameError with `name`. Test `test_unbound_free_variable_raises_name_error` |
| RL-11 | G 2.2.5.4 | `del` of an unbound local raised NameError; `del` of a nonlocal failed | Confirmed | Fixed `0d92b51` | Python's rules for locals, nonlocals and globals; `del` makes a name local. Also found: CPython 3.15 leaves `UnboundLocalError.name` as None (measured), which eval1 set on reads too; fixed. Test `test_del_of_unbound_local_and_of_nonlocal` |
| RL-12 | G 2.2.5.7 | D-10 not enforced | Confirmed | Fixed `0d92b51` | `DialectError("D-10: ...")` for return/break/continue leaving `finally`; loops inside `finally` allowed. Test `test_d10_control_flow_leaving_finally_is_a_compile_time_error` |
| RL-13 | A2 | 3.15 rejects AST constructors with missing fields: audit synthesized nodes | No issue | Checked | All five desugarings compile under `-W error` on 3.15.2 and match the original program |
| RL-14 | A2 | Host Python, semantic reference and grammar should not be implicitly interchangeable | Partly confirmed | Fixed `0d92b51` | They are separate settings (pyproject, `bella.toml` `python`, `grammar`); the one real coupling (L0 is the host `ast`) is now enforced: `frontend.check_host_grammar` |
| RL-15 | A2 | New 3.15 syntax must be classified | Confirmed | Fixed `0d92b51` | `lazy import` (PEP 810) and comprehension unpacking (PEP 798) refused by name until implemented. Test `test_new_3_15_syntax_is_refused_by_name` |

### Reference object model

| ID | From | Finding | Verdict | Status | Evidence and fix |
| --- | --- | --- | --- | --- | --- |
| RL-16 | A1 #4, G 2.1.2 | The cache check executed `__get__`/`__getattr__` a second time | Confirmed: counter read 1, 2, 3 raised ModelError | Fixed `0d92b51` | Lookup is a plan; the cached plan is compared with the generic plan before any user code runs; the chosen plan executes once. Case C-3-10, test `test_attribute_hooks_run_once_per_read_c_3_10` |
| RL-17 | G 2.1.2 | Entries stamped with the class version seen after the hook ran | Confirmed: a memoising `__getattr__` gave 1, 1 instead of 1, 2 | Fixed `0d92b51` | Versions taken when the plan is made. Case C-3-10 |
| RL-18 | G 2.1.1 | ClassAttr entry ignored the found object's own class | Confirmed: a class attribute whose class gained `__get__` stayed cached | Fixed `0d92b51` | ClassAttr entries record `found_cls`/`found_version`. Case C-3-11 |
| RL-19 | G 2.1.3 | AttributeError from an unset slot or a descriptor skipped `__getattr__` | Confirmed | Fixed `0d92b51` | `__getattr__` looked up first and called on any AttributeError, as `slot_tp_getattr_hook` does. Case C-3-09; spec section 3 now says so |
| RL-20 | A1 #4 | `CacheEntry.found` described as borrowed but held strongly | Confirmed (the model has no lifetimes) | Deferred: TODO task 3 | Stated in the model's docstring; lifetimes enter the model with RL-49 |
| RL-21 | G 2.1.5 | `InstanceDict` fast path does not say a miss falls back | Confirmed (the model already falls back) | Fixed `0d92b51` | Design section 3 and `docs/drafts/object.hpp.draft` |
| RL-22 | G 3.2 | Oracle should generate the new scenarios randomly | Accepted | Deferred: TODO task 3 | Deterministic tests cover them now (RL-16 to RL-19) |
| RL-23 | G 2.1.4 | ABA: per-class versions start at 0, so a freed class's entry can match a new class at the same address | Confirmed for the C++ draft; reproduced in the model once its entries stopped holding their class | Fixed with D-1 | One process-wide 64-bit counter; entries keyed by version alone, with no class pointer; 0 is never cached. With versions tied to the class address, the model's self-check serves a dead class's entry to the class born at its address on seed 1. Case C-3-12 (CPython 3.15.2 puts 10 of its 12 classes at one address), oracle operation `recreate_class`, test `test_dead_class_entries_never_match_a_new_class_c_3_12` and two more; design section 3, `docs/drafts/object.hpp.draft` |

### Runtime, validation, harness and CI

| ID | From | Finding | Verdict | Status | Evidence and fix |
| --- | --- | --- | --- | --- | --- |
| RL-24 | G 2.2.5.6 | Negative shift threw `std::domain_error`, not ValueError | Confirmed | Fixed `0d92b51` | `bella::ValueError`; the differential test now asks CPython rather than re-implementing its rule |
| RL-25 | A1 #6 | SMT `unknown` treated as proof | Confirmed (`check_z3` returned proved unless `sat`) | Fixed `0d92b51` | Verdicts PROVED / REFUTED / UNKNOWN; only PROVED removes a check. Test `test_z3_unknown_is_not_a_proof` |
| RL-26 | A1 #6, G 2.3.1 | Interval checker asserted exactness and crashed on `x - x` | Confirmed (both examples) | Fixed `0d92b51` | Inconclusive is UNKNOWN; Z3 proves `x - x`. Test `test_interval_checker_fails_closed_on_dependent_variables` |
| RL-27 | A1 #7 | `check` passed with nothing checked (`0/0`, exit 0) | Confirmed | Fixed `0d92b51` | No selected case is an error; a case without an authoritative expectation fails. `conformance/tests/test_harness.py` |
| RL-28 | A1 #7 | D-08 mask made user messages indistinguishable | Confirmed | Fixed `0d92b51` | Masking is opt-in per case (`# mask: TypeError, ...`); no current expectation used it |
| RL-29 | A1 #7 | CI records expectations instead of checking anything | Confirmed | Fixed `0d92b51` | New `verify`: the pinned CPython must reproduce every recorded expectation; `make check` runs `verify` and `lint`. `check --runner` waits for a compiled runner |
| RL-30 | G 3.1 | Makefile should use the project environment | Confirmed | Fixed `0d92b51` | `PY` defaults to `.venv/bin/python` when present |
| RL-31 | G 2.4.3.3 | Dockerfile `UV_VERSION=0.9` conflicts with `required-version` | Done | Fixed in `e3c20a6` | The review saw a mid-change snapshot |

### Corpus, closure and lint

| ID | From | Finding | Verdict | Status | Evidence and fix |
| --- | --- | --- | --- | --- | --- |
| RL-32 | G 2.4.2.1 | C-8-02 read a name bound nowhere (a compile-time error in the dialect) | Confirmed | Fixed `0d92b51` | The case binds and deletes the name; recorded observables unchanged |
| RL-33 | G 2.4.2.2 | C-3-05 and C-3-08 used `typing.Any` | Confirmed | Fixed `0d92b51` | `object`; observables unchanged |
| RL-34 | G 2.4.3.1-2 | mypy 44 errors, ruff 18 (23 on py315) | Confirmed | Fixed `0d92b51` | Both clean; `lint` added to `make check` and CI. Deliberate patterns in dialect programs carry a targeted `noqa` code with a reason, never a per-file ignore |
| RL-35 | G 2.4.3.1 | `test_closure.py` assertions pass vacuously | Refuted | Annotation fixed | `_edges` returns a dict keyed by `(target, class)`, so `("os", EAGER) in edges` is a real check; only its declared return type was wrong |
| RL-36 | G 2.4.1.4 | Omitted-module reach should follow CONDITIONAL and LAZY edges | Refuted | No change | The set is used to *ignore* runtime observations: following conditional edges from `bz2` grows it from 14 to 318 modules (`unittest`, `asyncio`, `__main__` included), hiding real requirements. Lazy edges never run at import time. The cited case is covered: `compression/zstd/__init__.py:29` imports `_zstd` eagerly |
| RL-37 | G 2.4.1.3 | An unguarded import under `if` inside a function is CONDITIONAL, not LAZY | Confirmed as described, but deliberate (the test and the manifest's `[omissions]` comment say so) | Fixed with D-3 | It conflicted with spec section 7, which calls only `try/except ImportError` imports optional. Classes are now dead, optional, lazy, guarded and eager; guards over the `[platform]` facts are evaluated; `[omissions]` may hold only optional imports, which the tool checks. Tests `test_guards_the_closed_world_can_evaluate_d3` and four more in `tools/tests/test_closure.py` |
| RL-38 | G 2.4.1.1-2 | Closure fails on the pin; `traceback` imports excluded `codeop`; unclassified 3.14/3.15 modules | Confirmed | Fixed (Gate 0 task 1); `codeop` with D-4 | 28 open items on 3.15.2, 25 after D-3 and D-4, all of them modules new in 3.15; closed on 2026-11-01 with 174 modules, and CI requires the committed lock to match the pinned image's. Decisions in `docs/DECISIONS.md` and design section 10.4 |
| RL-39 | A1 | The closure is an inventory, not proof that the modules compile | Accepted | Fixed (with this log) | README and `tools/closure.py` docstring |

### Python version (A2)

| ID | From | Finding | Verdict | Status | Evidence and fix |
| --- | --- | --- | --- | --- | --- |
| RL-40 | A2 | Use CPython 3.15.2 as the reference now (3.14.10 if migration cost mattered) | Agreed | Done `f56d495` | Corpus, closure and dependencies re-checked: [migration report](../migrations/2026-11-01-cpython-3.14.8-to-3.15.2.md) |
| RL-41 | A2 | Initially reject lazy imports | Refuted | Spec v0.4: PEP 810 \[P1\] | Eleven phase-1 modules use module-level `lazy import` (`collections`, `dataclasses`, `typing`, `traceback`, ...), so rejecting it rejects them; the reviewer did not run Bella on 3.15. The frontend refuses `lazy import` by name until it is implemented (RL-15) |
| RL-42 | A2 | Classify `frozendict` and `sentinel` explicitly | Agreed | Done `622c56f` | Spec v0.4 sections 3 and 6 |
| RL-43 | A2 | Defer comprehension unpacking | Agreed (no phase-1 module uses it) | Done `622c56f` | \[P2+\]; refused by name (RL-15) |
| RL-44 | A2 | "UTF-8 by default" differs from "always UTF-8" | Agreed | Done `622c56f` | D-15 narrowed to `PYTHONUTF8=0`, `PYTHONIOENCODING`, `encoding="locale"` (all measured) |
| RL-45 | A2 | `abi3t` is an option, not a guarantee; keep the version-specific bridge | Agreed | Done `622c56f` | Design sections 10 and 13 |
| RL-46 | A2 | Keep GIL-enabled CPython as the oracle | Agreed | Done | The pinned python-build-standalone build is the default (GIL) build |
| RL-47 | A2 | Run the corpus on both versions, keep both outputs, classify; write a migration report; no floating "latest" | Agreed | Fixed (with this log) | [migration report](../migrations/2026-11-01-cpython-3.14.8-to-3.15.2.md): two observables changed, both new in 3.15; the process for future moves is in the report |

### Design and plan (A1, G)

| ID | From | Finding | Verdict | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| RL-48 | A1, G 1.2.1 | Phase 1 is too wide: split it | Agreed in substance by both | Planned: D-2 | |
| RL-49 | A1 | Make lifetimes (retain/release timing) explicit in the IR | Agreed | Planned: D-2 | Prerequisite for RL-20 |
| RL-50 | A1, G 1.2.2 | The staging-to-runtime contract for `exec`-built code is unresolved | Agreed by both | Fixed: Gate 0 task 5 | `docs/staging.md`: staged by call site and text, with build-time probes for literal `namedtuple` calls, an unstaged text refused with E-01 (spec v0.9 section 8); the mechanism awaits the author's confirmation (S-5) |
| RL-51 | A1 | Consolidate the authoritative documents; present PassSpec as obligation tracking | Agreed | Planned: D-2 | |

### Closure on 3.15.2 (A3, G2)

Both reviews reproduced the 174-module lock byte for byte. Every tool finding below was
reproduced on `b40ef2d` with the reviewers' method (temporary modules, runtime observation
stubbed) before it was fixed; each fix has a test in `tools/tests/test_closure.py`. The fixed
tool closes the manifest at 175 modules (`_hmac` added), and the lock changed only where the
fixes say: `os.add_dll_directory`'s import of `nt` is now dead, and the `[dynamic]` edges name
their function and parent package.

| ID | From | Finding | Verdict | Status | Evidence and fix |
| --- | --- | --- | --- | --- | --- |
| RL-52 | A3-1 | A module seen only by the runtime observation was scanned but its edges never processed | Confirmed: `rv_child`'s lazy import of a module outside the manifest went unreported | Fixed | The queue is drained to a fixed point after the observation. Test `test_runtime_discovered_modules_are_traversed_a3_1`. Today's lock does not change (its runtime-only modules have no edges), as the reviewer said |
| RL-53 | A3-2, G2 3.2 | A target missing on this machine needed no decision | Confirmed: `def f(): import missing` and an optional import of a missing module both passed | Fixed | No host-absence exemption; Windows-only `_winapi` and `nt` are now `[omissions]` of `ntpath` and `pathlib._os`; `os.add_dll_directory` is proved dead instead (RL-65). Test `test_a_module_missing_here_still_needs_a_decision_a3_2` |
| RL-54 | A3-3 | An ImportError handler around a `def` made the imports in its body optional | Confirmed: `('rv_required', 'optional', 3, 'f')` | Fixed | A function or lambda body starts with no exception context. Test `test_a_handler_around_a_definition_does_not_cover_its_body_a3_3` |
| RL-55 | A3-4 | `__lazy_modules__` was read for the whole statement and the whole module | Confirmed. Measured on 3.15.2: checked per imported module, with the value at that point; reassignment and in-place mutation take effect; the full dotted name matches; `from` imports count; module-level `if`, `with` and `for` blocks count; `try` and class bodies do not | Fixed | Classified per module in execution order; any other form than a literal assigned at module level is an error, since the closure could not tell. The lock is described as an inventory; the compiler takes laziness from each statement (design section 10.4 corrected). Test `test_lazy_modules_is_read_per_import_and_in_order_a3_4` |
| RL-56 | A3-5 | `[dynamic]` recorded a review per module, so a new site in a reviewed module passed | Confirmed | Fixed | One key per site, `"<function>: <name expression>"`; a new site and a stale key are errors. Test `test_each_computed_import_site_is_reviewed_a3_5` |
| RL-57 | A3, G2 2.2 | hashlib without OpenSSL: add cases for the kept surface; the absent APIs and `algorithms_available` differ from the pinned CPython | Confirmed (measured: `pbkdf2_hmac`, `scrypt` absent; five names fewer in `algorithms_available`) | Fixed with D-6: deviation D-20 | Case C-7-01 prints the kept surface (digests, HMAC, buffer keys); it is identical on the pinned build and with `_hashlib` blocked. The differences are not in the deviation register |
| RL-58 | G2 2.1, A3 | The `annotationlib` shim refuses what `@dataclass`, `NamedTuple`, `TypedDict` and `singledispatch.register` call at runtime | Confirmed: spec section 8 runs decorators and class bodies at runtime; calls at `dataclasses.py` 1057 and 1413, `typing.py` 3054 and 3208, `functools.py` 970; `inspect` imports `get_annotations` at module level | Fixed with D-5: Gate 0 task 5 | Annotations \[P1\] at runtime; case C-3-13 pins CPython's behaviour. The shim (`runtime/shims/annotationlib.py`) and the build-time tables pass C-3-13 and C-3-21 under the staging replay (`docs/staging.md`); the compiler side is TODO task 4 |
| RL-59 | A3 | Refusals name private `shutil` helpers; decide which public calls stay valid | Agreed | Done | Decided in spec section 7: the built-in archive formats are \[P2+\], so `make_archive` and `unpack_archive` refuse for them; `get_archive_formats` and registered formats work. Case C-7-04 (\[P2+\]), now that the harness checks \[P2+\] refusals (TODO task 2) |
| RL-60 | A3 | The `traceback` replacement needs a runtime test | Agreed | Done | Case C-7-02: `TracebackException` and `format_exception_only` on a `ModuleNotFoundError`, which goes through the replaced function |
| RL-61 | G2 2.2 | Omitting `_hmac` loses CPython behaviour for no licence reason | Confirmed: `hmac.digest(memoryview(b"k"), ...)` raises `TypeError` with `_hashlib` and `_hmac` blocked and works with only `_hashlib` blocked | Fixed | `_hmac` mapped, like the digests it builds on; C-7-01 covers it |
| RL-62 | G2 2.3 | `PurePath.as_uri` is allowed while `Path.as_uri` is refused | No issue | No change | `PurePath.as_uri` imports only `urllib.parse` (\[P1\]), so the per-function rule supports it, as CPython would run it |
| RL-63 | G2 2.3 | A refused function must still exist as an object: `shutil` sets `supports_root_dir` on two of them at import | Agreed | Done | Spec section 7 and `TODO.md` (runtime work): only a call raises |
| RL-64 | G2 3.1 | An edge whose target was already reached skipped the lazy and optional accounting | Confirmed: a correct `[lazy_unsupported]` entry was reported stale | Fixed | Every edge is accounted for before the queue check. Test `test_every_edge_is_accounted_for_whatever_reached_its_target_first_g2_3_1` |
| RL-65 | G2 3.2 | `from posix import *` made `os.name` unknown, so `os.add_dll_directory` was not dead | Confirmed | Fixed | A star import from a built-in module binds exactly the names that module exports. Test `test_a_star_import_from_a_builtin_binds_only_its_exports_g2_3_2` |
| RL-66 | G2 3.3 | The static reach of omitted modules could mask runtime observations (`tracemalloc` reaches `pickle`) | Confirmed | Fixed | The observation blocks every omitted module (`sys.modules[name] = None`), so importers take their phase-1 fallbacks; the masking set is gone. All 68 roots import cleanly that way |
| RL-67 | G2 3.4.1 | A dotted dynamic target did not reach its parent packages | Confirmed | Fixed | Literal dynamic imports and `[dynamic]` targets add every parent. Test `test_dotted_dynamic_targets_import_their_parents_g2_3_4` |
| RL-68 | G2 3.4.2 | A literal `import_module("x")` inside a function was followed as required | Confirmed | Fixed | It is a lazy edge, like an import statement there |
| RL-69 | G2 3.4.3 | A nested helper, not the function a program names, was recorded as refused | Confirmed | Fixed | The outermost enclosing function is refused (spec section 7 says so). Test `test_a_nested_helper_refuses_the_function_a_program_names_g2_3_4` |
| RL-70 | G2 3.5 | `make lint` ran `ruff`/`mypy` from `PATH`, not `$(PY)` | Confirmed | Fixed | `$(PY) -m ruff check . && $(PY) -m mypy` |

### Target programs and increments (A4, G3)

Both reviews reproduced the six target locks and the increments (149 / 6 / 25) byte for byte.
Every tool and oracle finding was reproduced on `8b8eb0d` before it was fixed. After the fixes
the locks and increments are unchanged: no driver had an import under its main guard, and
nothing relied on the other gaps.

| ID | From | Finding | Verdict | Status | Evidence and fix |
| --- | --- | --- | --- | --- | --- |
| RL-71 | A4-1 | The closure evaluated a target's entry script as an imported module, so imports under `if __name__ == "__main__":` were dead | Confirmed: the reviewer's probe recorded the import as dead, with no problem reported | Fixed | The root is scanned with `__name__ == "__main__"` (its identity unchanged), and the runtime observation runs the program as the harness does (`__main__`, its arguments and directory, by `compile` and `exec`, not `runpy`, which imports `pkgutil` itself) instead of importing it. Test `test_the_entry_script_runs_as_main_a4_1` |
| RL-72 | A4-2, G3 2.3.1 | `data_tricky_toml` needs stateful multiple inheritance with built-in bases, which is \[P2+\], yet the refined D-2 puts it in 1b | Confirmed: `Integer(Item, _CustomInt)`, `String(str, Item)`, `DateTime(Item, datetime)` and four more; `Item.__init__` stores `_trivia` | Fixed with D-7: the tricky three follow phase 1 | Module closures do not measure language features; design section 11, `targets.toml` stage |
| RL-73 | A4-3, G3 2.1 | `unicodedata` is in the 1a inventory although the author kept it \[P2+\] | Confirmed, and wider than reported: six functions in `re._parser`, `traceback` and `urllib.parse` import it on non-ASCII paths of functions every ASCII input goes through, so refusing those functions whole would break ASCII regexes, URLs and tracebacks | Fixed with D-8: `unicodedata` \[P1\] | Spec v0.8 sections 6 and 7, case C-7-15, a manifest root |
| RL-74 | A4-4, G3 3.3.1 | `run_targets.py check` accepted a non-authoritative or stale recording | Confirmed (the reviewer's probe passed) | Fixed | `check` requires `authoritative` and the pinned Python version; `--allow-unpinned` permits a development comparison. `tools/tests/test_run_targets.py` |
| RL-75 | A4-5 | The token target printed token lengths, so a wrong MAC of the same length passed | Confirmed: with every signature replaced by `b"X" * 20` the output still matched | Fixed | Full tokens are recorded, a token CPython signed is verified, and a same-length mutation is rejected; the constant-MAC probe now fails |
| RL-76 | A4 note | The target oracle compared decoded text and had no time limit | Confirmed | Fixed | Bytes, 600 s per run |
| RL-77 | A4 note | Spec section 7 maps `re` onto PCRE2; `docs/targets.md` and `TODO.md` plan a port of `_sre` | Confirmed (inconsistent) | Fixed with D-9: the `_sre` port | Spec v0.8 section 7; licence register L-08 |
| RL-78 | A4 note, G3 3.3.2 | `targets-check` did not run the phase-1 configuration | Confirmed | Fixed | A third run under the D-20 simulation; all six pass |
| RL-79 | A4 note, G3 2.2 | 1a is 85 % of the manifest because the closure counts uncalled functions; G3 measured 62, 91 and 83 modules loaded by the easy targets against 112, 144 and 146 in their locks | Agreed | Planned: D-10 (TODO task 4) | 1a staged by target, 1a.1 to 1a.3 (`targets/closure-summary.json`); the compile scope is measured in task 4 |
| RL-80 | G3 2.3.2 | `copy` is \[P1\], but copying a user class goes through `__reduce_ex__`, `__getstate__` and `copyreg`, which spec section 3 files under pickling, \[P2+\] | Confirmed | Fixed with D-11: the copy protocol \[P1\] | Spec v0.8 section 3, case C-3-20 |
| RL-81 | G3 3.1 | A per-target declaration replaced the manifest's entry for the same module, and a misspelt or stale key passed silently | Confirmed (the reviewer's probe) | Fixed | Entries are merged; a declaration for a module the closure does not reach is an error. Test `test_per_target_declarations_merge_and_must_name_reached_modules_g3_3_1` |
| RL-82 | G3 3.2 | Every file under `targets/drivers` and `targets/vendor` counted as the program's own; the platform check was skipped in target mode | Confirmed | Fixed | Only the driver and the packages `targets.toml` declares; the platform facts are checked. Test `test_only_declared_packages_belong_to_the_program_g3_3_2` |
| RL-83 | G3 3.3.3 | `check --verbose` showed no stderr diff | Confirmed | Fixed | |
| RL-84 | G3 3.4 | `score_candidate.py` counted submodules by their package, parsed licence files, and walked `TYPE_CHECKING` blocks | Confirmed (humanize's `importlib.resources` was misreported) | Fixed | |
| RL-85 | G3 3.5 | The conformance harness split `--runner` on spaces; D-20's wording said `shutil` offers three formats, though calling them is \[P2+\] | Confirmed | Fixed | `shlex.split`; D-20 now speaks of what `get_archive_formats` and `get_unpack_formats` list (spec section 11, `docs/deviations.toml`) |
| RL-86 | G3 2.2 | `docs/targets.md` said only the tricky targets reach `dataclasses` → `inspect` → `ast` | Confirmed: the easy ones do too (`enum.EnumType.__signature__`, `_colorize`) | Fixed | |
| RL-87 | A4 note | Keep the qualifications of the candidate scorer and the Mandelbrot measurement | Agreed | No change | |

## Open for discussion

**D-1 Class versions from one global counter (RL-23).** Decided 2026-11-01: accepted as
recommended (design section 3, `docs/drafts/object.hpp.draft`, `refmodel/objects.py`, case
C-3-12). Writing it into the model first showed two simplifications: an entry needs no class
pointer at all, since the version names the class (a `cls_hint` integer only decides which
older entry an install replaces), and the found object's class is read through `found` after
the class version matched, which also notices a `__class__` assignment to `found`. The
recommendation, explained in detail at the author's request, was to accept: CPython does the same for type version
tags, and the reviewer's case is real once runtime-created classes can die. It changes design
section 3 (the `version` field and its allocation) and the draft header; the model adopts it in
the same change, so the header is still written from the model.

Measured on 3.15.2 by reading `tp_version_tag` (offset 384 in the pinned headers) through
`ctypes`: tags come from one process-wide counter (two new classes got 131185 and 131186); a
modification sets a class's tag to 0, and the next lookup assigns the next number (131187), to
each subclass as well; a class created after another died took the dead class's address
(`0x37774080`) with a new tag (131191, then 131192); after 1000 modifications a class gets no
new tag and is never cached again. In Bella's draft, versions are per class and start at 0, so a
new class at a freed address would match a stale entry that also says 0: a field offset from
another layout, or a dangling `found`.

**D-2 Scope and order of the next increment (RL-48 to RL-51).** Decided 2026-11-01: accepted
as recommended (design section 11, `TODO.md`, `docs/DECISIONS.md`). Refined the same day, once
the target programs were picked: each increment is the closure of its target programs, which
moves `re`, `enum` and `typing` into 1a and staging ahead of the first path (an order change). Both code reviewers ask for
a smaller first deliverable, and A1 adds three prerequisites. Recommendation:
1. Split phase 1 into 1a (core language and the data-structure modules the three target
   programs need), 1b (`enum`, `dataclasses`, `typing`), 1c (I/O, `re`, `json`, `logging`,
   `unittest`, ...). Gate 0 task 4 already targets the smallest program first; this makes it
   the plan.
2. Before relying on staging, prototype one `@dataclass` and one `namedtuple` with observable
   definition-time effects. G's two options are stage-time `exec` keyed by call site and
   source hash, or compiler intrinsics for the three known users. Choose after the prototype.
3. Add retain/release points to the L2 grammar and finaliser traces to `eval1` before the
   header; the model gains lifetimes with them (RL-20).
4. Consolidate the documents after Gate 0: rewrite design sections 3-10 around the final
   decisions, keep sections 13-15 as history, and let this log carry review history from now
   on. PassSpec status should name its evidence, so that "tested" points at the tests.

**D-3 Imports under `if` (RL-37).** Decided 2026-11-01: accepted as recommended (spec v0.5
section 7, design section 10.4, `tools/closure.py`, `manifest.toml` `[platform]`). Until then an
`if`-guarded import outside the manifest became an omission (ImportError at runtime), while
spec section 7 defines optional imports as `try/except ImportError` only. Recommendation: inside functions, `if`-guarded imports become
LAZY (the function is unsupported, not silently failing). At module level, add a `[platform]`
manifest table for guards the closed world can evaluate (`sys.platform`, `os.name`), and keep
`[omissions]` for ImportError guards only. Follow-up decided the same day: `[lazy_unsupported]`
keeps refusing whole functions, on every path (spec section 7, design section 10.4), so
`copy.copy(logger)` stays refused although CPython reaches `Logger.__reduce__` without importing
`pickle`.

**D-4 `traceback` needs `codeop` (RL-38).** Decided 2026-11-01: the shim, as recommended, with
one refinement found while writing it up: the refusal names E-08 rather than a milestone and
cannot be caught, since `traceback` calls `compile_command` inside `suppress(Exception)` and a
catchable error would drop CPython's keyword suggestion silently (measured; spec v0.5 sections 4
and 7, design section 10.4). `traceback` imports `codeop` (excluded by E-08) at
module level, but only calls `codeop.compile_command` in two functions that format syntax errors
(3.15.2 `traceback.py` lines 1458 and 1507). A compiled program cannot raise a syntax error at
runtime, because `compile` is excluded (E-01). Recommendation: a `codeop` shim under
`[phase1.shim]` that provides the `PyCF_*` constants and a `compile_command` that raises with the
milestone name, recorded in `[adaptations]`. Keeping E-08 intact is better than un-excluding
`codeop`.

**D-5 Annotations at runtime and the `annotationlib` shim (RL-58).** Decided 2026-11-01: option
1, as recommended (spec v0.7 sections 3 and 7; case C-3-13; implemented in TODO task 5). Spec v0.6 section 7
specifies a shim whose `get_annotations` and `call_annotate_function` raise with the milestone
name, because annotations are \[P2+\] (section 3). But section 8 runs every decorator and class
body at runtime, and `@dataclass`, `NamedTuple`, `TypedDict` and `singledispatch.register` call
those functions with the FORWARDREF format, so the shim as specified fails every dataclass at
runtime. CPython's own path needs no `__code__` when the annotations evaluate: FORWARDREF reads
`__annotations__` first, and `call_annotate_function` calls `annotate(format)` before any
fallback (3.15.2 source). Options:
1. Annotations in the VALUE format become \[P1\] for classes and functions (a compiler-generated
   `__annotate__`), and the shim serves VALUE, FORWARDREF when evaluation succeeds, and STRING
   from compile-time text; only the `__code__` fallbacks (a `NameError` under FORWARDREF,
   `ForwardRef.evaluate`) stay \[P2+\]. This is G2's proposal.
2. Annotations stay \[P2+\]; the staging contract replaces the annotation reads in
   `dataclasses`, `typing` and `functools` with staged metadata (adaptations of three modules).

Recommendation: 1. It follows CPython's own fast path, leaves the three modules unadapted, and is
what section 8 already implies. Settle the details in the staging prototype (TODO task 5), which
gates phase 1b, where these modules belong.

**D-6 Phase-1 omissions are observable (RL-57).** Decided 2026-11-01: option 1, deviation D-20
registered (spec v0.7 section 11, `docs/deviations.toml`); option 2 is a later task in `TODO.md`.
An omission makes a module behave as not
installed (spec section 7), and the pinned CPython has those modules, so some effects are visible:
`hashlib.pbkdf2_hmac` and `hashlib.scrypt` are absent, `algorithms_available` lacks `md5-sha1`,
`ripemd160`, `sha512_224`, `sha512_256` and `sm3`, `shutil` lists 3 archive formats instead of 6
(no `bztar`, `xztar`, `zstdtar`), and a codec outside the phase-1 set raises `LookupError` (all
measured on 3.15.2 with the omitted modules blocked). The deviation register has no entry for this,
and a difference not in the register is a defect. Options:
1. Register D-20, "phase-1 omissions behave as modules not installed", accepted for phase 1, with
   these effects listed and a lint rule for `pbkdf2_hmac`, `scrypt`, `algorithms_available`,
   archive format names and codec names outside the set.
2. Close the `hashlib` part instead: `pbkdf2_hmac` over the mapped HMAC and `scrypt` from
   libsodium, as an adaptation of `hashlib`.

Recommendation: 1 now, 2 when a target program needs either. The harness then needs a way to
check a case that differs by a registered deviation (TODO task 2).

**D-7 tomlkit's stateful multiple inheritance (RL-72).** Decided 2026-11-01: option 1, widened by
the author to all three tricky targets, which follow phase 1 (design section 11, `targets.toml`
stage "later"); items 1 to 3 of `docs/targets.md` section 5 move with them. Seven tomlkit classes combine
`Item`, which keeps instance state, with a built-in base (`int`, `float`, `str`, `list`, `dict`,
`datetime`, `date`, `time`): stateful multiple inheritance, \[P2+\] in spec sections 3 and 5.
Decision D-2 as refined makes 1b the closure of the tricky targets; describing that as a change
of order was wrong for this target, since a module closure does not measure language features.
Options:
1. `data_tricky_toml` moves after phase 1, to the milestone where stateful multiple inheritance
   lands; its recording stays, and 1b is what mistune and pycodestyle need.
2. Bring the subset tomlkit uses into phase 1: one Python base with instance state plus one
   built-in base, with CPython's layout rules, model first and with conformance cases.
3. Adapt tomlkit: rejected, since vendored libraries are never edited.

Recommendation: 1 now, and revisit 2 once the object header exists (TODO task 3), because the
layout of built-in bases belongs to it. Each tricky target's language features should be checked
against the tier table as well as its module closure (`bella-lint`'s job, TODO task 4).

**D-8 `unicodedata` in phase 1 (RL-73).** Decided 2026-11-01: option 2, for later revision, because
of how much of the phase-1 library depends on it (spec v0.8 sections 6 and 7, case C-7-15); this
reverses option (c), and `cli_easy_slugs` keeps its lowered requirements. The author kept `unicodedata` \[P2+\] (option (c)
of 2026-11-01), but the phase-1 library calls it on non-ASCII paths: `re._parser._escape` and
`_class_escape` for `\N{...}` (`lookup`), `traceback._str_width` and `_zip_display_width`
(`combining`, `category`, `east_asian_width`, `iter_graphemes`), `traceback._compute_suggestion_error`
and `urllib.parse._checknetloc` (`normalize`, NFKC). Each of these functions also runs on every
ASCII input. Options:
1. A shim (G3's proposal): `import unicodedata` succeeds and each function raises the
   milestone-naming error when called. ASCII paths run unchanged; a regex with `\N{...}`, a
   non-ASCII host, a non-ASCII name in a suggestion, and the caret width of a non-ASCII source
   line in a debug-build traceback raise \[P2+\]. Option (c) stands.
2. `unicodedata` becomes \[P1\]: the names table, normalisation and grapheme segmentation, a scope
   change.

Recommendation: 1. It is the existing shim mechanism and keeps the author's decision; release
builds print file and line only (D-06), so tracebacks there never reach the width functions.

**D-9 The regex engine (RL-77).** Decided 2026-11-01, as recommended (spec v0.8 section 7), with
the licence as its own register entry, L-08: `re` and `sre.c` carry Secret Labs AB's notice,
redistributable under CNRI's Python 1.6 licence. Spec section 7 maps `re` onto PCRE2; `docs/targets.md`
and `TODO.md` plan to compile `re`'s pure-Python parser and compiler and port the `_sre` engine.
Recommendation: the `_sre` port. PCRE2 differs from CPython's `re` in syntax, Unicode classes,
error messages and the order of backtracking, and "never approximate" rules out an engine that
gives different matches; the port is PSF-licensed (licence register L-01). If accepted, spec
section 7 changes in the next revision.

**D-10 What is compiled for a target (RL-79).** Decided 2026-11-01, as recommended: 1a.1 to 1a.3
now (`targets.toml` stage), and the function-level scope measured in TODO task 4. The closure counts every function of every
reached module (an inventory of what may run), which makes 1a 149 modules and 71,219 lines.
Options:
1. Compile the whole closure.
2. Compile what the closed world can reach, function by function: a pass with a `PassSpec`,
   whose obligation is that no function reachable at runtime, by name or by a computed name the
   tier rules admit, is left out. The closure stays the inventory.
3. In any case, stage 1a by target: 1a.1 `cli_easy_slugs`, 1a.2 `service_easy_tokens`,
   1a.3 `data_easy_sales`, each with its own gate.

Recommendation: 3 now, and 2 as compiler work in TODO task 4, measured against what the
targets load (G3's numbers).

**D-11 The copy protocol (RL-80).** Decided 2026-11-01, as recommended (spec v0.8 section 3, case
C-3-20). `copy.copy` and `copy.deepcopy` on a user class without
`__copy__` call `__reduce_ex__(4)`, which uses `__getstate__` and `copyreg`, while spec section 3
files `__reduce__`, `__getstate__` and `__setstate__` under pickling, \[P2+\]. Recommendation (G3's):
the reduction protocol as `copy` uses it becomes \[P1\] (`__reduce_ex__`, `__reduce__`,
`__getstate__`, `__setstate__`, `copyreg.__newobj__` and `_reconstructor`), and only the `pickle`
module stays \[P2+\]; E-05 keeps excluding programs that rely on `copyreg` internals. A
conformance case comes first: copying unslotted, slotted and customised user classes.

## How to add a review

Put the file in this directory as `YYYY-MM-DD-<reviewer>-<nn>-<topic>.md`, then add a row to
*Reviews received*. Number its findings on from the last ID (`RL-88` next), reproduce each one,
and record the verdict and evidence. Reference the IDs in commit messages.
