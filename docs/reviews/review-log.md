# Review log

Every finding from an external review, its verdict, and what happened to it. Reviews are input,
not authority: each finding is reproduced against the pinned CPython (or checked in the code)
before it is accepted, and every reviewer's findings are weighed alike. A confirmed defect that
can be fixed without changing the design is fixed with a failing test or conformance case first;
anything that would change the design, the specification or the build plan goes to
[Open for discussion](#open-for-discussion) with a recommendation.

**Status on 2026-11-06:** 346 findings from twenty-five reviews and one round of examples: 299 fixed (most in commit
`0d92b51`, RL-37 with decision D-3, RL-23 with D-1, RL-38 with Gate 0 task 1, RL-52 to RL-70 after
the closure reviews, RL-57 with D-6, RL-71 to RL-86 after the target reviews, RL-72, RL-73, RL-77
and RL-80 with D-7, D-8, D-9 and D-11, RL-50 and RL-58 with Gate 0 task 5, RL-88 to RL-134 after
the staging reviews, RL-136 to RL-168 after the L1 and `eval1` reviews, RL-169 to RL-187 after
the L2 and lifetimes reviews, RL-188 to RL-219 after the compiled-classes reviews, RL-220 to RL-227 but RL-222 and RL-225, RL-228 to RL-253 and RL-255 after the reviews of tracebacks, dicts and operators, 62 of RL-256 to RL-326 after the reviews of compiled imports, RL-327 to RL-333 after A11, RL-334 to RL-346 after G12 and A12, RL-323 with weak references), 21 already done before or
because of the review, 4 planned (D-2 and D-10, accepted by the author), 3 deferred (RL-222 to step 3c), 4 refuted
5 checked with no issue, and 7 accepted, refused or not defects (RL-269, RL-275, RL-284, RL-285, RL-289, RL-319, RL-326). Open: RL-225 (lines inside a statement), RL-254 (a member's type) and RL-277 (a SyntaxError class). The
author decided D-1 to D-11, and S-1 to S-5 of `docs/staging.md`, on 2026-11-01, and D-12 on 2026-11-03.

## Reviews received

| Date | Reviewer | File | Scope | Ran against |
| --- | --- | --- | --- | --- |
| 2026-11-05 | gemini-high (G11) | [2026-11-05-11-gemini-high-abc-hash-fixes.md](2026-11-05-11-gemini-high-abc-hash-fixes.md) | asked for `62d083b..0081164`; no findings | this checkout: its line numbers are those of `365e55e`, not of the range |
| 2026-11-05 | Codex astra-low (A11) | [2026-11-05-astra-low-11-abc-views-builtin-names.md](2026-11-05-astra-low-11-abc-views-builtin-names.md) | `62d083b..0081164`: the fixes of the last review, D-22, `_abc`, class dict views | CPython 3.15.2 and compiled, in a separate checkout |
| 2026-11-06 | gemini-3.8-flash-high (G12) | [2026-11-06-gemini-flash-12-exceptions-os-c-types-re-sys.md](2026-11-06-gemini-flash-12-exceptions-os-c-types-re-sys.md) | `d46c55b..1dab41b`: exceptions, `posix`, C types' methods, reduce, `__flags__`, str subclasses, `re`, `sys` and the earlier commits; four findings, RL-334 to RL-337 | `1dab41b`, in the main checkout |
| 2026-11-06 | Codex astra-low (A12) | [2026-11-06-astra-low-12-c-types-reduce-flags-str-re.md](2026-11-06-astra-low-12-c-types-reduce-flags-str-re.md) | five commits of `d46c55b..1dab41b`, narrowed after the provider's filter stopped a run on the whole range; five findings, RL-338 to RL-342 | `1dab41b`, in a separate checkout |
| 2026-11-04 | gemini-4-argon-high (G10) | [2026-11-04-10-gemini-4-argon-high-compiled-imports-super-metaclasses.md](2026-11-04-10-gemini-4-argon-high-compiled-imports-super-metaclasses.md) | compiled super(), metaclasses, int/dict subclasses, imports and build caches, `e827a47..62d083b` | CPython 3.15.2, GCC 16.2.1 |
| 2026-11-04 | eight Sonnet reviewers, one per focus area (S1), in place of astra-low, whose run failed | [2026-11-04-sonnet-swarm-compiled-imports-super-metaclasses.md](2026-11-04-sonnet-swarm-compiled-imports-super-metaclasses.md) | the same range | CPython 3.15.2, GCC 16.2.1 |
| 2026-11-03 | astra-low (A10) | [2026-11-03-astra-low-10-traceback-dictionary-review.md](2026-11-03-astra-low-10-traceback-dictionary-review.md) | D-12 part 1, step 3a.3's dict, the operators and argument errors, `f12af86..e827a47` | CPython 3.15.2, GCC 16.2.1 |
| 2026-11-03 | gemini-4-argon-high (G9) | [2026-11-03-09-gemini-4-argon-high-tracebacks-dict-operators.md](2026-11-03-09-gemini-4-argon-high-tracebacks-dict-operators.md) | the same range | CPython 3.15.2, GCC 16.2.1 |
| 2026-11-03 | astra-low (A9) | [2026-11-03-astra-low-09-compiled-classes-review.md](2026-11-03-astra-low-09-compiled-classes-review.md) | the C++ emitter, the runtime core and compiled classes, `d28b256..f12af86` | CPython 3.15.2, GCC 16.2.1 |
| 2026-11-02 | gemini-4-argon-high (G8) | [2026-11-02-08-gemini-4-argon-high-cpp-emitter-review.md](2026-11-02-08-gemini-4-argon-high-cpp-emitter-review.md) | the same range | CPython 3.15.2, GCC 16.2.1 |
| 2026-11-02 | astra-low (A8) | [2026-11-02-astra-low-08-l2-lifetime-review.md](2026-11-02-astra-low-08-l2-lifetime-review.md) | the L2 leg, lifetimes in the model and `object.hpp`, `58bb34b..d28b256` | CPython 3.15.2, GCC 16.2.1 |
| 2026-11-02 | gemini-4-argon-high (G7) | [2026-11-02-07-gemini-4-argon-high-l2-lifetimes-review.md](2026-11-02-07-gemini-4-argon-high-l2-lifetimes-review.md) | the same range | CPython 3.15.2, GCC 16.2.1 |
| 2026-11-02 | astra-low (A7) | [2026-11-02-astra-low-07-eval1-semantics-review.md](2026-11-02-astra-low-07-eval1-semantics-review.md) | Gate 0 task 4 steps A1 to B and P-1 to P-3, `3d4e428..58bb34b` | CPython 3.15.2 |
| 2026-11-02 | gemini-4-argon-high (G6) | [2026-11-02-06-gemini-4-argon-high-l1-eval1-review.md](2026-11-02-06-gemini-4-argon-high-l1-eval1-review.md) | the same range | CPython 3.15.2 |
| 2026-11-01 | astra-low (A1) | [2026-11-01-astra-low-01-design-codebase-review.md](2026-11-01-astra-low-01-design-codebase-review.md) | design and Gate-0 code | CPython 3.14.8, GCC 16.2.1 |
| 2026-11-01 | astra-low (A2) | [2026-11-01-astra-low-02-python-version-review.md](2026-11-01-astra-low-02-python-version-review.md) | choice of reference Python | release notes; Bella not run on 3.15.2 |
| 2026-11-01 | gemini-4-argon-high (G) | [2026-11-01-01-gemini-4-argon-high-scaffold-architecture-review.md](2026-11-01-01-gemini-4-argon-high-scaffold-architecture-review.md) | design and Gate-0 code | CPython 3.14.8, GCC 16.2.1 |
| 2026-11-01 | astra-low (A3) | [2026-11-01-astra-low-03-stdlib-closure-review.md](2026-11-01-astra-low-03-stdlib-closure-review.md) | Gate 0 task 1: closure tool, manifest and lock at `b40ef2d` | CPython 3.15.2 (pinned uv build) |
| 2026-11-01 | gemini-4-argon-high (G2) | [2026-11-01-02-gemini-4-argon-high-stdlib-closure-review.md](2026-11-01-02-gemini-4-argon-high-stdlib-closure-review.md) | task 1 and the review-log fixes, `f56d495` to `b40ef2d` | CPython 3.15.2, GCC 16.2.1 |
| 2026-11-02 | gemini-4-argon-high (G5) | [2026-11-02-05-gemini-4-argon-high-staging-revision-review.md](2026-11-02-05-gemini-4-argon-high-staging-revision-review.md) | the staging revision, `b838bc5..d0bec20` | CPython 3.15.2 |
| 2026-11-02 | astra-low (A6) | [2026-11-02-astra-low-06-staging-revision-review.md](2026-11-02-astra-low-06-staging-revision-review.md) | the staging revision, `b838bc5..d0bec20` | CPython 3.15.2 |
| 2026-11-01 | astra-low (A5) | [2026-11-01-astra-low-05-staging-prototype-review.md](2026-11-01-astra-low-05-staging-prototype-review.md) | the staging prototype, `19316ba..b838bc5` | CPython 3.15.2 |
| 2026-11-01 | gemini-4-argon-high (G4) | [2026-11-01-04-gemini-4-argon-high-staging-prototype-review.md](2026-11-01-04-gemini-4-argon-high-staging-prototype-review.md) | the staging prototype and D-7 to D-11, `19316ba..b838bc5` | CPython 3.15.2, GCC 16.2.1 |
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
| RL-03 | A1 #3, G 2.2.5.5 | Locals zero-initialised, `global` ignored, `return Int(0)` on fall-through | Confirmed: `global x` assignment lost; `h(0)` printed 0, not None | Fixed `0d92b51` | `global` honoured; a definite-assignment check refuses reads of possibly unassigned names, calls before the `def`, functions that may fall off their end, and the None value of a procedure (`Unsupported`, never a default). Since step 3a.1 (2026-11-02) the toy emitter is gone and the emitter from L2 runs these programs with CPython's semantics; the tests now require CPython's output |

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

### Staging prototype (A5, G4)

Every finding was reproduced before anything changed: A5 on the working tree, G4 on `b838bc5` in
a separate worktree, then on the working tree, which already fixed some. The review probes run
as `test_the_review_probes_print_what_cpython_prints`, each replayed and compared with CPython.
The author's decisions S-1 to S-5 (`docs/staging.md`) were applied in the same change; S-1
removes the build-time tables that A5-5, G4 3.5a and 3.5b are about.

| ID | From | Finding | Verdict | Status | Evidence and fix |
| --- | --- | --- | --- | --- | --- |
| RL-88 | A5-1 | The replay matched staged code by site and text only: an `eval` ran code staged for an `exec` | Confirmed: prints `None` where CPython prints `2` | Fixed | The key holds the operation; the caller's `__future__` flags and the optimisation level are checked. Test `test_an_eval_never_runs_code_staged_for_an_exec` |
| RL-89 | A5-2, G4 3.4c | Changing an imported module reused a stale artefact | Confirmed: `{'x': 'int'}` after the annotation became `bytes` | Fixed | The artefact lists every source it was made from, by content, and is rebuilt when one changes. Test `test_a_changed_imported_module_rebuilds_the_artefact` |
| RL-90 | A5-3 | The input recorder dropped a module body's own reads, since an importer is always below it on the stack | Confirmed: `"inputs": {}` for a body that reads a file | Fixed | Only the frame that performed the operation decides whether the loader did it. Tests for a body's read, a helper's read and a listing. The stdlib inventory, recomputed, still shows only `subprocess`'s environment read; the recorder's blind spots are listed in `docs/staging.md` section 2 |
| RL-91 | A5-4 | The evidence gate ignored the harness's exit status | Confirmed by reading; the reviewer's simulated crash passed | Fixed | A non-zero exit or a missing summary fails it; a [P2+] refusal must be exit 70 with the `bella: refused: [P2+]` line. Test `test_the_evidence_gate_fails_on_a_crashed_harness` |
| RL-92 | A5-5, G4 3.5b | Recorded exceptions were rebuilt from their display text | Confirmed: `("'missing'",)` for `('missing',)` | Fixed with S-1 | No tables: the entry point raises the real exception. C-3-21 and C-3-22 print the arguments |
| RL-93 | A5 on S-5 | The comparison is coverage and maintenance cost, not a semantic defeat of intrinsics; "nothing per CPython version" is too strong | Agreed | Fixed | `docs/staging.md` sections 1 and 5 |
| RL-94 | A5 on S-1 | Demonstrate the entry point before the scope change | Agreed | Done | The generator, checked against CPython's bytecode and outputs for 250 annotate functions, a corpus of scope shapes, mutation tests, C-3-22 |
| RL-95 | A5 on S-2 | A refusal needs a normative boundary, a negative case and a diagnostic | Agreed | Done | Spec section 3, C-3-24 [P2+], the replay's refusal |
| RL-96 | A5 on S-3 | Keep text and layout contracts apart; a policy refusal needs its own enforcement; fix A5-1 to A5-3 before narrowing the input rule | Agreed | Done | Spec v0.10 section 8; `[refused]` holds when the text was staged (C-7-16); the layout obligation stays open (`TODO.md`) |
| RL-97 | A5 on S-4 | A negative fixture with a real Plural-Forms catalogue, the path registered | Agreed | Done | C-7-16 writes a `.mo` file; manifest `[refused]` |
| RL-98 | A5 on D-20 | Accepting every `_pydatetime` difference is broader than the one observed | Agreed | Fixed | D-20 lists only observed differences (spec section 11, `docs/deviations.toml`) |
| RL-99 | G4 3.1 | The shim refused in `ForwardRef.__forward_code__`, which `typing._make_forward_ref` reads eagerly: every quoted name in a typing form, and every `NamedTuple` or `TypedDict` under PEP 563, was refused | Confirmed on both trees | Fixed | `compile()` is staged like `exec`; the refusal moved to `evaluate` of an expression; a reference built at runtime from an unseen text is refused with `[P2+]` (manifest `[unstaged]`) |
| RL-100 | G4 3.2 A | `_Stringifier` and `ForwardRef` call `ast.unparse`, which `[lazy_unsupported]` refused | Confirmed: in `unsupported_functions`; the shim calls it five times | Fixed | `_ast_unparse` compiled, \[P1\]: a consequence of S-1 (lock 176 modules) |
| RL-101 | G4 3.2 B | `ForwardRef.__resolved_str__` re-parses its string with `ast.parse` | Confirmed: an E-01 at `ast:parse:46` | Fixed | The shim fixes names on a copy of the tree it unparsed; equal to CPython's (probe 3.2B) |
| RL-102 | G4 3.2 C | The closure tool did not scan shim sources | Confirmed: `tools/closure.py:1027` | Fixed | A shim written in Python is scanned instead of CPython's module. Test `test_a_shim_written_in_python_is_scanned_g4_3_2` |
| RL-103 | G4 3.2, recommendation 4 | The replay did not refuse the lock's unsupported functions | Confirmed | Fixed | It does, as phase 1 does. Test `test_unsupported_functions_are_refused` |
| RL-104 | G4 3.3 a-c | The entry was dry-run under its file stem: its own sites missed, a stdlib-named entry collided, `-P` was ignored, and with a lock its texts were dropped | Confirmed: three probes | Fixed | `__bella_entry__`, reported as `__main__`; `--safe-path` under `-P`. Probes 3.3a, 3.3b and `test_the_entry_scripts_texts_survive_a_closure_lock` |
| RL-105 | G4 3.4 a | Sibling modules imported without a lock had no entry points or probes | Confirmed | Fixed | Every module loaded from outside the standard library is the program's (probe 3.4a) |
| RL-106 | G4 3.4 b | A PEP 810 lazy import's module was never defined at build time | Confirmed | Fixed | The dry run resolves program modules' lazy imports to a fixed point (attribute access resolves them, reading the namespace does not) (probe 3.4b) |
| RL-107 | G4 3.4 c | The cache key omitted program module sources | Confirmed on `b838bc5` | Done before (RL-89) | |
| RL-108 | G4 3.5 a | A set inside `Annotated` made a STRING table depend on the hash seed | Confirmed on `b838bc5` | Fixed with S-1 | No build-time STRING: computed at runtime by CPython's own code, as CPython does |
| RL-109 | G4 3.5 c | FORWARDREF refused a hand-written annotate and a PEP 695 evaluate function that CPython answers | Confirmed on both trees | Fixed | Evaluate functions get entry points; a hand-written function that raises `NotImplementedError` falls back to VALUE as in CPython (probes 3.5c) |
| RL-110 | G4 3.5 d | Probes missed `field_names=` and `typename=`; `builtins.exec` was not a site; `exec(text, closure=...)` dropped `closure` | Confirmed | Fixed | (The operation in the key is RL-88.) Probes 3.5d |
| RL-111 | G4 on 3.3 | `run.py` ignored `-P` for the dry run | Confirmed | Fixed | With RL-104 |
| RL-112 | G4 on S-1 to S-5 | Agree with the proposals | Noted | No change | The author decided S-1 to S-5 |

### Staging revision (A6)

Each probe was reproduced on `d0bec20` before the fix, and each now runs in
`test_the_review_probes_print_what_cpython_prints`.

| ID | From | Finding | Verdict | Status | Evidence and fix |
| --- | --- | --- | --- | --- | --- |
| RL-113 | A6-1 | Two evaluators could share an identity (file, qualified name, first line) and overwrite each other: two aliases named alike on one line | Confirmed: `str` twice where CPython prints `int`, `str` | Fixed | The identity adds a hash of every instruction's source position (`annotate_rt.entry_key`, used by the build and the replay alike); a duplicate is declined, never overwritten. Test `test_two_annotate_functions_never_share_an_entry_point` |
| RL-114 | A6-2 | The dry run's `exec` and `eval` compiled in the recorder's context (its `from __future__ import annotations`), so discovery could differ from CPython | Confirmed: exit 70 where CPython prints `T(absent=1)` | Fixed | Each text is compiled explicitly with the caller's flags, and the code the dry run ran is the code staged. Tests with and without PEP 563 in the caller |
| RL-115 | A6-3 | Source handling differed from the builtins: `eval` strips leading spaces and tabs; bytes are decoded by their PEP 263 declaration | Confirmed: an `IndentationError` and a `UnicodeDecodeError` | Fixed | The builtin's preprocessing, applied once, in the dry run; the key is the source as given, `str` or `bytes`. Tests for whitespace and for `eval` and `compile` of declared bytes |
| RL-116 | A6-4 | Private attribute names were not mangled in the evaluators (`C.__v` for `C._C__v`) | Confirmed: the build declined it, and the runtime blamed a function the compiler did not generate | Fixed | Attribute names are mangled as CPython does (keyword-argument names are not); a declined entry point is refused with the build's reason |
| RL-117 | A6 on S-1 | Validating each evaluator does not validate the mapping from live functions to evaluators; keep runtime tests of FORWARDREF's first run, with real globals and live cells | Agreed | Done | RL-113's test; C-3-22 runs the first FORWARDREF run with real globals and live cells (a closure variable before and after binding, class-level names) |
| RL-118 | A6 on S-4 | `[refused]` acted at the `exec`, so `gettext.c2py("bad")` raised a catchable `ValueError` | Confirmed | Fixed | Refused on entry, as the manifest says. Test `test_a_refused_function_is_refused_on_entry` |
| RL-119 | A6 on the closure | A scanned shim's lock entry named CPython's module as its path | Confirmed: `annotationlib.py` | Fixed | `runtime/shims/annotationlib.py` |
| RL-120 | A6 on the documents | `docs/staging.md` section 4 and the replay's header still said any code object and any `compile` stop the program | Confirmed | Fixed | Both state the boundary as implemented |
| RL-121 | A6 on S-2, S-3 | The refusal policies have their cases and interception points; layout staging stays open | Noted | No change | |

### Staging revision (G5)

Reproduced on `d0bec20` in a separate worktree and on `f79ee0a` (after A6), which already fixed
3.2 and 3.7.3. Each probe now runs in `test_the_review_probes_print_what_cpython_prints`.

| ID | From | Finding | Verdict | Status | Evidence and fix |
| --- | --- | --- | --- | --- | --- |
| RL-122 | G5 3.1 | The evaluators returned unresolved PEP 810 lazy imports under FORWARDREF | Confirmed: the replay failed with `AttributeError` on an unresolved lazy import | Fixed | `annotate_rt` does what `_PyLazyImport_Reify` does (CPython 3.15.2 `Python/ceval.c`, `bytecodes.c`, `Objects/lazyimportobject.c`): a lazy import found by a global load, or in a class namespace, is resolved and written back. `LOAD_DEREF` does not resolve one, as the source shows, contrary to the review's description |
| RL-123 | G5 3.2 | Evaluator identities collide for a bound and a default on one line | Confirmed on `d0bec20` | Done before (RL-113) | |
| RL-124 | G5 3.3 | Under PEP 563 the generator skipped the module, and with it the PEP 695 evaluate functions, which PEP 563 leaves | Confirmed: exit 70 | Fixed | Only the annotate owners are skipped |
| RL-125 | G5 3.4 | A starred `TypeVarTuple` default crashed the build | Confirmed: `SyntaxError` | Fixed | Unpacked, as `*args: *Ts` is |
| RL-126 | G5 3.5 | An `IfExp` or f-string annotation matched no owner, since CPython compiles only its parts' positions | Confirmed | Fixed | Every sub-expression's span identifies its owner |
| RL-127 | G5 3.5 | A method's private parameters and locals were not mangled in its scope, so a nested function's annotation loaded them as globals | Confirmed: declined | Fixed | Bindings are mangled as the symbol table mangles them |
| RL-128 | G5 3.5 | Private type-parameter names: mangled with the enclosing class (a function or alias) or the class itself; a class's own bounds and defaults are not mangled | Confirmed | Fixed | |
| RL-129 | G5 3.5 | A class body's `global` reaches past the class namespace | Confirmed | Fixed | A direct global load, in the class's annotations and its methods' |
| RL-130 | G5 3.5 | A walrus inside a lambda inside a comprehension was bound in the scope around it, in the generator and in `tools/closure.py` | Confirmed | Fixed | Both stop at a lambda. Test `test_a_walrus_in_a_lambda_binds_in_the_lambda_g5_3_5` |
| RL-131 | G5 3.6 | Two scripts with the same text in two directories shared an artefact | Confirmed: exit 70 in the second | Fixed | Keyed and checked by the script's real path |
| RL-132 | G5 3.6 | `-O` and `PYTHONOPTIMIZE` were not in the key, nor passed to the dry run | Confirmed: an artefact of level 0 refused under `-O` | Fixed | The level, asked of the interpreter, is in the key and the dry run. Test `test_artefacts_are_per_script_and_per_optimisation_level` |
| RL-133 | G5 3.7 | `eval` of a code object that a staged `compile` returned is allowed at runtime | Confirmed as described | Refuted | By design: that code was compiled at build time and gives CPython's result, so no compiler is needed. A program's own `exec` or `eval` is E-01, which the compiler rejects at build time and the model does not police (`docs/staging.md` section 4) |
| RL-134 | G5 3.7 | `scan.py` took a parenthesised `(x): int` as a `NamedTuple` field | Confirmed: the probe staged the wrong fields | Fixed | Only simple targets |
| RL-135 | G5 3.7 | The lock named CPython's module as a scanned shim's path | Confirmed on `d0bec20` | Done before (RL-119) | |

### L1 and `eval1` (A7)

Reproduced on `58bb34b` under CPython 3.15.2 and `pipeline/l1/run.py`; each probe now runs in
`pipeline/tests/test_review_2026_11_02.py`. The review's "Approach" section adds two concrete
defects (RL-143, RL-144). Its remark that a future global-slot pass must keep the observable
module dictionaries is agreed: the plan keeps a real dict, made when code exposes it (P-3, the
author's direction).

| ID | From | Finding | Verdict | Status | Evidence and fix |
| --- | --- | --- | --- | --- | --- |
| RL-136 | A7-1 | A lone `*x` argument was expanded before the keyword arguments ran | Confirmed: `(1,)` where CPython prints `(1, 2)`, and `__iter__` before the keyword's call | Fixed | `Interpreter.arguments` follows `codegen_call_helper_impl`: a lone `*x` is only evaluated, made a tuple at the call (`_MAKE_CALLARGS_A_TUPLE`, with `_Py_Check_ArgsIterable`'s message) |
| RL-137 | A7-2 | Under `from __future__ import annotations` a module or class got PEP 649's `__annotate__` instead of an `__annotations__` dict | Confirmed: `NameError` for `__annotations__` | Fixed | `desugar-annotations` emits SETUP_ANNOTATIONS (the new `setup_annotations` intrinsic: the namespace's `__annotations__` unless it has one, through `__getitem__` for a custom mapping) before `__doc__`, and stores each simple annotation's text with LOAD_NAME `__annotations__` |
| RL-138 | A7-3 | An annotation without a value dropped its target's evaluation; in a function, `obj().x: int` crashed the frontend | Confirmed: no output where CPython prints `obj`, `key`; an `AssertionError` | Fixed | `codegen_check_ann_expr` and `codegen_check_ann_subscr`: the object, and a subscript's index (each bound of a slice, each element of an extended slice), in every scope |
| RL-139 | A7-4 | A comprehension's helper called `iter()` again on the iterator the enclosing scope made | Confirmed: `iter` twice, and a generator expression's second one after creation | Fixed | L1's `For` gains `iterator`: the comprehension's outermost loop only advances the iterator (FOR_ITER), as CPython's |
| RL-140 | A7-5 | `{**m}` re-hashed the keys CPython copies with their stored hashes | Confirmed: `['hash']` where CPython prints `[]` | Fixed | DICT_UPDATE is the host's own on a copy of the target, so the stored hashes and every comparison are CPython's. DICT_MERGE: exact for string keys; for others the host merge plus a duplicate found by identity, so no `__hash__` runs, and `__eq__` on unequal keys of equal hash may run a different number of times, for a call that then fails ("keywords must be strings"); stated in its docstring. Found: `frozendict` (new in 3.15) takes dict's fast path too |
| RL-141 | A7-6 | `__prepare__ = None` was treated as absent | Confirmed: `created` where CPython raises `TypeError` | Fixed | A sentinel in `runtime/prelude/build_class.py`, for `__mro_entries__` too (G6 2.6.4) |
| RL-142 | A7-7 | Any call named `globals()`, even unused, switched off the program's compile-time NameError | Confirmed with `check(lower(...))` | Fixed | The exemption is gone: spec section 8 says writes through `globals()` reach statically known names, and P-3's `strict=False` covers the library code that needed it. `run.py` now refuses a program `wf1` rejects (exit 70) instead of crashing |
| RL-143 | A7, approach | `eval1_corpus.py --update` would take a partial run as the baseline | Confirmed by reading | Fixed | The update needs a result for every case the harness selects. Test `test_the_corpus_baseline_is_written_only_from_a_complete_run_a7` |
| RL-144 | A7, approach | Library provenance (P-3) came from a directory named `vendor` | Agreed | Fixed | In closure mode it comes from the lock: its roots are the program's own code, its other `program` modules the packages `targets.toml` declares. The directory rule stays only for modules no lock lists (program mode), with RL-167 |

### L1 and `eval1` (G6)

Reproduced on `58bb34b` under CPython 3.15.2 and `pipeline/l1/run.py`; each probe now runs in
`pipeline/tests/test_review_2026_11_02.py`. Five findings (RL-156, RL-161, RL-165, RL-166 a)
are one gap: the frontend checked only what the parser checks. It now compiles the parsed tree
with the pinned host compiler (`check_compile` in `pipeline/l1/frontend.py`), so every
compile-time error of the symbol table and the code generator is CPython's, with its message.
The review's summary says 74 of 80 cases pass under `eval1`; the baseline was 58 of 75 (now 59).

| ID | From | Finding | Verdict | Status | Evidence and fix |
| --- | --- | --- | --- | --- | --- |
| RL-145 | G6 2.1.1 | Under PEP 563 a function's annotation strings were unparsed after other passes had rewritten them (mangled names, `_cmp` walrus, `bella:format`) | Confirmed | Fixed | A new pass, `desugar-function-annotations`, right after `desugar-type-params`: a function's annotations become its `__annotate__` function, an ordinary definition before the function (in its generic scope, if any), which every later pass lowers and `to-l1` attaches to the function. Under PEP 563 the texts are taken there, from the untouched tree |
| RL-146 | G6 2.1.2 | A comprehension in a function's annotation was `Unsupported` | Confirmed | Fixed | RL-145 |
| RL-147 | G6 2.2.1 | `x: T` in a method declared the unmangled name | Confirmed: `global_leak` where CPython raises `UnboundLocalError` | Fixed | Mangled with the class |
| RL-148 | G6 2.2.2 | `self.a: int` in a method crashed the frontend | Confirmed | Done | RL-138 |
| RL-149 | G6 2.2.3 | `(x): int` in a function made `x` local | Confirmed: `UnboundLocalError` where CPython prints the global | Fixed | Only a simple name target is declared |
| RL-150 | G6 2.2.4 | Value-less attribute and subscript targets lost their evaluation | Confirmed | Done | RL-138 |
| RL-151 | G6 2.3.1 | `wf1` rejected a generic class nested in a class whose bases name the outer class's attributes | Confirmed: `WellFormednessError` | Fixed | `wf1` lets a scope marked `classdict` read the nearest class's names, as `eval1` does |
| RL-152 | G6 2.3.2 | A generic class's private type parameter was bound unmangled and read mangled | Confirmed: `WellFormednessError` | Fixed | `desugar-private-names` follows `_Py_MaybeMangle`: the type-parameter scope of a generic class (and the scopes in it, up to the class body) mangles only the type parameters, with the class's own name; a private name in the bases stays as written (CPython 3.15.2 raises `NameError` for `__x` there too) |
| RL-153 | G6 2.3.3 | `type Alias = int` in a class had `__qualname__` `Alias` | Confirmed | Fixed | The value's thunk is named after the alias, so its qualname is CPython's; `_pep695` gives the snippet's value code that qualname (`_Py_make_typealias` takes `co_qualname`) |
| RL-154 | G6 2.4.1 | A walrus in a comprehension in a lambda | Confirmed: `SyntaxError: no binding for nonlocal` | Fixed | `eval1` counts a lambda's prelude among its bindings |
| RL-155 | G6 2.4.2 | A walrus whose target the containing function declares global | Confirmed: `SyntaxError: no binding for nonlocal` | Fixed | The helper declares it global, and so do comprehensions inside the helper |
| RL-156 | G6 2.4.3 | `yield` in a comprehension was accepted | Confirmed | Fixed | The compile check |
| RL-157 | G6 2.5.1 | A `yield` inside an f-string, a slice, a comprehension's iterable or a chained comparison was refused | Confirmed: exit 70 | Fixed | In a generator, an intrinsic's operands are evaluated in order and the intrinsic applied to their values; `__bind__` stores its value. A starred or `**` argument beside a `yield` stays a refusal |
| RL-158 | G6 2.5.2 | `for a[(yield 1)] in xs` crashed `eval1` with `TypeError` | Confirmed | Fixed | A refusal, as a `yield` in an assignment target already is |
| RL-159 | G6 2.5.3 | While a generator ran, `site()` and `caller_flags()` named whoever resumed it | Confirmed by reading; a test shows it | Fixed | The generator's frame is pushed while it runs, taken off at each `yield` and for a `yield from`, and popped when it ends |
| RL-160 | G6 2.6.1 | Mapping patterns with `-1` or `1+2j` keys were rejected | Confirmed: `unsupported` | Fixed | Keys are checked folded, as after CPython's AST optimiser |
| RL-161 | G6 2.6.2 | A repeated class-pattern keyword was accepted | Confirmed | Fixed | The compile check |
| RL-162 | G6 2.6.3 | `**rest` used `dict.update`, which takes pairs from an object without `keys()` | Confirmed: `{'a': 1}` where CPython raises `TypeError` | Fixed | `{**subject}`, which is DICT_UPDATE |
| RL-163 | G6 2.6.4 | `__mro_entries__ = None` and `__prepare__ = None` treated as absent | Confirmed | Done | RL-141 |
| RL-164 | G6 2.7.1 | `f(**{"a": 0}, a=s1(), b=s2())` stopped before `s2()` | Confirmed: `['s1']` where CPython prints `['s1', 's2']` | Fixed | A run of keywords is evaluated whole into a dict before the merge (`codegen_subkwargs`), with RL-136 |
| RL-165 | G6 2.7.2 | `lazy import` in a `try` and `from m import *` in a class were accepted | Confirmed | Fixed | The compile check |
| RL-166 | G6 2.7.3 | (a) `nonlocal` without a binding and a parameter declared `global` accepted; (b) the `globals()` relaxation; (c) `global x` counted as binding `x` though nothing assigns it | Confirmed, all three | Fixed | (a) the compile check; (b) RL-142; (c) `wf1` counts a global declaration as a module binding only where the declaring scope binds the name, a comprehension's walrus included |
| RL-167 | G6 2.7.4 | (a) Closure mode did not lower the lock's program modules (the vendored packages) ahead; (b) D-20's modules were blocked after start-up imported | Confirmed by reading; (b) has no effect today, as start-up reaches no blocked module | Fixed | (a) every `program` module of the lock is lowered before the program starts (P-1); (b) blocked first. With RL-144 |
| RL-168 | Found while fixing RL-137 | Under PEP 563 a class with a method stored `__classdictcell__`, which CPython's does not | Confirmed: measured on 3.15.2 over 28 class bodies | Fixed | Under PEP 563 only a generic definition or a type alias makes the cell; without it any definition or annotation does. Test `test_a_class_namespace_sees_cpythons_stores_with_and_without_pep_563` |

### L2 and lifetimes (A8, G7)

Reproduced on `d28b256` under CPython 3.15.2, `pipeline/l2/run.py` and GCC 16.2.1 (the header
under ASan). The two reviews overlap on eleven findings, so they share one table. The pipeline's
probes now run in `pipeline/tests/test_review_2026_11_02b.py`; the model's in
`refmodel/tests/test_cases.py`, and the header's in `make object-test`
(`runtime/tests/object_reentrancy.*`). Three statements of G7 are wrong and none is a finding:
the range has 8 commits, not 15; SEL is the author's own expression language and its `bn` is MIT
(`docs/DECISIONS.md`, 2026-11-02), not a BSD-3 library of another vendor; and slots are not
released in reverse declaration order (RL-178). Both reviews' common thread is G7's section 3.1:
the frontend's synthetic variables stand for values CPython keeps on its stack, and several
outlived them. Each kind now dies where CPython's stack value does, on the normal path (RL-171,
RL-172, RL-180, RL-185) and during unwinding (RL-186).

| ID | From | Finding | Verdict | Status | Evidence and fix |
| --- | --- | --- | --- | --- | --- |
| RL-169 | A8-1, G7 2.1 | `execute` called the plan's `__getattr__` hook and descriptor as borrowed references; a `__get__` that deletes the hook from the class frees it before it is called | Confirmed: heap-use-after-free under ASan; CPython prints 7 | Fixed | CPython's lookups take strong references (`_PyType_LookupRef`). The model and the header own the hook from the lookup until the operation ends, a descriptor and its `__get__` (`__set__`, `__delete__`) while that runs, and a finaliser while it runs; cache entries stay borrowed (RL-20). Measured on 3.15.2: a descriptor deleted by its own `__get__` dies as `__get__` returns, before the hook runs; a hook deleted while it runs dies after it returns. Test `test_a_descriptor_is_owned_while_its_get_runs_a8_1`; `runtime/tests/object_reentrancy.cpp` prints what `object_reentrancy.py` prints under CPython, without quarantine, under ASan and UBSan, in `make object-test` (the old header fails it with a heap-use-after-free) |
| RL-170 | A8-2, G7 2.7 | The traceback of a failing operation kept `eval2`'s helper frames and their arguments (`x += O()`, `a, b = [O()]`, `f(*O())`, `f(**O())`) alive until the handler ended | Confirmed: "handler" before "del" | Fixed | Every handler `eval2` generates first unlinks the frames of `eval2.py` and `eval1.py` from the exception's traceback, and from those of the exceptions it chains, and clears them (`_Runtime.strip`): CPython's instructions keep no frame. `docs/l2.md` section 5 claimed this before it was true |
| RL-171 | A8-3, G7 2.6 | A failing `__enter__`, or a failing target assignment, left the `with` statement's manager, `__exit__` and value in synthetic variables | Confirmed: "del manager" after the handler; the value after `__exit__` | Fixed | The lookup and `__enter__` run inside a handler that drops the manager, `__enter__` and `__exit__`, and the value is dropped before `__exit__` is called when the target fails. The names are set to None instead of deleted, so every path can drop them whether it bound them or not |
| RL-172 | A8-4, G7 2.2 | A chained comparison's middle operand stayed in a `_cmp` variable until the scope ended, in the module, a function or a class body | Confirmed | Fixed | A `_cmp` name is a stack value: `to-anf` makes it a temporary, and `resolve-names` gives it no slot (`expression_temporary`). Also removes it from `co_varnames` (G7 2.4) |
| RL-173 | A8-5, G7 2.4 | `resolve-names` gave an annotation-only declaration (`z: int`) its slot at the declaration | Confirmed: `('z', 'a')` where CPython has `('a', 'z')`, so the locals died in the wrong order | Fixed | Measured on 3.15.2: a slot is allocated at the first load, store or delete the code generator emits, dead code included; the annotation alone allocates nothing, yet makes the name local, and it can be a cell. `Declare` binds without a slot; declared-only names are classified after the others |
| RL-174 | A8-6, G7 2.5 | A function that declares `x` global did not stop an inner function from capturing an enclosing function's `x` | Confirmed: "2" where CPython prints "1" | Fixed | As `symtable.c`'s `analyze_block`: a scope's global declarations are removed from the bindings it passes to its children; checked two levels deep |
| RL-175 | A8-7, G7 2.12 | `locals()` and `vars()` were recognised by the name they were called through, so an alias (`see = locals`) or `locals(*())` showed `eval2`'s own variables | Confirmed: `True` where CPython prints `False` | Fixed | Every call compares its callee by identity with `locals`, `vars`, `dir`, `eval`, `exec` and `compile` (bound in the factory, so no program binding reaches them; an `is` test, so no `__eq__` runs). `globals()` needs nothing, the generated functions' globals being the module's own. `make targets-eval2` takes 91 s instead of 78 |
| RL-176 | A8-8, G7 2.13 | The handlers `eval2` generates, and the `with` expansion, named `BaseException`, which a program can rebind | Confirmed: `TypeError: catching classes that do not inherit from BaseException` | Fixed | `eval2` catches through a reserved name bound to the builtin; the frontend's `with` uses the `%BaseException` intrinsic |
| RL-177 | A8-9, G7 2.11 | A statement after `return`, `raise`, `break` or `continue` failed `wf2` ("unreachable statement") | Confirmed | Fixed | `to-anf` stops a block at the first statement that does not fall through: CPython compiles the rest and drops it; the names in it were resolved with the others, so slot tables are unchanged |
| RL-178 | A8-10, G7 2.10 | The model and the header released `__slots__` in declaration order | Confirmed. G7's rule ("reverse declaration order") is wrong too: its example is sorted as well as reversed | Fixed | `type_new` sorts a class's slot names (after mangling); measured on 3.15.2 with `('zeta', 'alpha', 'mid')`: `alpha, mid, zeta`. Each class's slots die sorted, the most-derived class's first. C-9-08 gains the case (re-recorded); test `test_slots_die_sorted_by_name_not_declared_order_c_9_08`; the oracle's R0 declares its slots unsorted. `docs/DECISIONS.md` and the docstrings said declaration order; corrected |
| RL-179 | A8-11, G7 2.14 | `wf2` checked `finally` against the live set at the start of the `try`, so a `finally` could use a temporary a `return` had consumed | Confirmed with a hand-built L2 program | Fixed | The `finally` block is checked from the intersection of the entry set and the live sets of every path that leaves the `try` early (return, raise, and break, continue or a loop's end from a loop inside it). `eval2` translates `Return` as a move (`_l2_ret`), so it no longer masks such a program |
| RL-180 | G7 2.3 | A decorator's value stayed in a `_dec` variable until the scope ended | Confirmed, for functions and, found while fixing, classes | Fixed | A `_dec` name is loaded once, where the decorator is applied: the load moves it into a temporary (`moved_on_use`), so it dies after its call |
| RL-181 | G7 2.4 | Synthetic names appear in `co_varnames` | Partly confirmed | Fixed | `_cmp` names no longer have slots (RL-172). The other synthetic variables keep theirs: a representation difference, not an observable one, since `locals()` hides them and none holds a value when its frame ends (RL-185, RL-186). `test_l2_resolve` compares slot tables without them, as before |
| RL-182 | G7 2.8 | `obj[k] += v` released the key, container and result in the wrong order | Confirmed | Fixed | `lifetimes` releases a statement's operands in the reverse of the order CPython's stack holds them: STORE\_SUBSCR drops the key, the container, then the value, STORE\_ATTR the owner, then the value |
| RL-183 | G7 2.9 | `obj.a += v` released the owner after the result | Confirmed | Fixed | RL-182 |
| RL-184 | Found while fixing RL-182 | A discarded call result was released before the call's arguments | Confirmed: CPython prints "del 2, del 1, del result" | Fixed | An operation whose result is discarded gets a temporary, released after its operands (`lifetimes`) |
| RL-185 | Found while fixing RL-171 | A `match` statement's pattern temporaries (`_items`, `_keys`, `_values`, `_cls`, `_attrs`, `_alt`, `_item`, `_cap`) lived until the scope ended, as the pass's docstring admitted | Confirmed | Fixed | They are set to None, newest first, once a pattern has matched and stored its captures (before the guard), and after the case on the paths where it failed |
| RL-186 | Found while fixing RL-185 | When an exception left a `match` pattern, a chained assignment's failing first target, a decorator expression or an inlined comprehension, the synthetic variables outlived the handler | Confirmed: CPython drops these stack values during unwinding | Fixed, but for one order | `eval2`'s generated handlers set the synthetic variables a region stored to None after its temporaries, newest first (a construct is numbered after the ones inside it), and a list, set or dict comprehension's helper its iterator argument as well (CPython inlines them, PEP 709; a generator expression's iterator belongs to a real frame and stays). Open: CPython drops such a comprehension's iterator before its partial result; Bella drops it after, because the caller's operand still holds it while the helper unwinds. The emitter can move the iterator into the helper; `TODO.md` task 4 |
| RL-187 | A8, verification | `make object-test` passed with the use-after-free: the random programs never mutate a class from inside its own callbacks, and the checking mode quarantines dead objects | Confirmed | Fixed | RL-169's test runs without quarantine under ASan and UBSan in `make object-test`. The oracle's R0 now declares unsorted slots, though its programs seldom observe slot deaths; C-9-08 and the model test cover RL-178 |

### Compiled classes (A9, G8)

All 23 of A9's findings reproduce on CPython 3.15.2 and the compiled runner (`PYTHONHASHSEED=0`).
G8's thirteen are a subset; G8 numbered them RL-188 to RL-200 itself, and those labels are its
own: its section numbers are mapped below. Each reviewer's program, the finally matrix and the
programs found while verifying are `pipeline/tests/test_review_2026_11_03.py`; the 31 L2
release-point probes now also run compiled (`pipeline/tests/test_compiled_probes.py`, 60 of 62,
the two generator probes refused until step 3b). Running the earlier rounds' programs compiled
found RL-211 to RL-219.

| ID | From | Finding | Verdict | Status | Evidence and fix |
| --- | --- | --- | --- | --- | --- |
| RL-188 | A9-1, G8 2.5 | List comparison kept positions and lengths read before an element's `__eq__` ran; one that empties the list read past its end | Confirmed: invalid read under ASan at `ops.cpp:294` | Fixed | `list_richcompare` and `tuplerichcompare` as CPython writes them: a list's lengths first for `==`/`!=`, both items held while user code runs, the current lengths read at every step |
| RL-189 | A9-2, G8 2.2 | An unbound method of a C++ type accepted a receiver of another type (`list.append(1, 2)` crashed) | Confirmed: SIGSEGV | Fixed | Every method descriptor knows its type (`Builtin::owner`); a direct call and `__get__` check the receiver with CPython's message (`descriptor 'append' for 'list' objects doesn't apply to a 'int' object`). The prelude's methods of the C++ types check theirs too (RL-218) |
| RL-190 | A9-3, G8 2.3 | `set.discard()` and `set.remove()` read an argument that was not passed | Confirmed: SIGSEGV | Fixed | METH\_O's check on every one-argument set method; a scan of `call.cpp`, `types.cpp` and `set.cpp` found no other method reading an argument before checking the count |
| RL-191 | A9-4 | An exception from `__del__` escaped the death that ran it: from a destructor, `std::terminate` | Confirmed: abort | Fixed | Finalisers run through a hook that reports the exception as CPython reports an unraisable one (`Exception ignored while calling deallocator <function C.__del__ at 0x…>:` and the traceback, on stderr) and drops it, keeping the exception being propagated |
| RL-192 | A9-5, G8 2.1 | A `finally` written inline before a `return` ran inside the `try`'s own catch, so when it raised it ran a second time | Confirmed | Fixed | The emitter notes how a `try` with a `finally` was left (normal, return, break, continue, the loop's end) and jumps past it; the block runs once there and the completion goes on outward. The exception edge runs it in a catch of its own. `docs/emitter.md` section 2 |
| RL-193 | A9-6, G8 2.8 | On the exception edge the `finally` block ran with no exception being handled: a bare `raise` there raised RuntimeError, and a new exception lost its `__context__` | Confirmed | Fixed | The edge makes the exception the one being handled (`Handling`) while the block runs, then `rt::rethrow`, which also restores the exception frame records attach to |
| RL-194 | A9-7 | Unpacking kept its source alive until the scope ended | Confirmed | Fixed | UNPACK\_SEQUENCE pops its source: the emitter releases it after the unpack, before the targets are bound |
| RL-195 | A9-8 | A set insertion whose comparison raised leaked the key | Confirmed: the key never died | Fixed | The table takes its count only when it stores the key |
| RL-196 | A9-9, G8 2.4 | A duplicate base, or bases with no consistent MRO, escaped as an uncaught C++ exception | Confirmed: SIGABRT | Fixed | `type_new` checks duplicates (`duplicate base class A`) and turns a failed C3 merge into CPython's TypeError (`Cannot create a consistent method resolution order (MRO) for bases A, B`) |
| RL-197 | A9-10 | Calling an instance used an instance attribute `__call__` | Confirmed | Fixed | `__call__` is found on the type and bound through its descriptor |
| RL-198 | A9-11 | `list.pop` took any index that was not a small int as 0, after removing nothing yet | Confirmed | Fixed | One conversion for indices (`index_value`: int, bool, `__index__`), before the list changes |
| RL-199 | A9-12, G8 2.9 | Set and dict iterators ignored a change of size | Confirmed | Fixed | Each iterator keeps the size it began with; a change raises CPython's RuntimeError, and keeps raising |
| RL-200 | A9-13, G8 2.6 | Sequence ordering turned an element comparison's result into a bool | Confirmed | Fixed | The deciding comparison's result object is returned as it is (RL-188) |
| RL-201 | A9-14, G8 2.11 | `__len__` returning a bool, or an object with `__index__`, was rejected by truth testing; `len()` and truth disagreed | Confirmed | Fixed | `len()` and truth share CPython's conversion (`length_value`: an index, never negative) |
| RL-202 | A9-15 | Copying an exact set or dict called each key's `__hash__` again | Confirmed | Fixed | The merge paths insert with the stored hashes, as `set_merge`, `set_update_dict_keys` and `dict_merge` do |
| RL-203 | A9-16 | A lookup in an empty dict did not hash the key | Confirmed | Fixed | The key is hashed first |
| RL-204 | A9-17 | The dict repr took a snapshot of the items before calling the keys' and values' `repr` | Confirmed | Fixed | The prelude walks the entries as `PyDict_Next` does, through a runtime primitive (`_dict_next`) |
| RL-205 | A9-18 | `__slots__` rejected a repeated name and accepted a name that is no identifier | Confirmed | Fixed | `type_new_visit_slots`: identifiers only (`__slots__ must be identifiers`), a repeated ordinary name accepted, `__dict__` once and only where no base has a dict. A name beyond ASCII is refused until the Unicode database |
| RL-206 | A9-19, G8 2.12 | `classmethod` of a callable that is not a descriptor raised AttributeError | Confirmed | Fixed | `cm_descr_get` since 3.13: the prelude returns `types.MethodType(func, owner)`; `method.__new__` takes any callable |
| RL-207 | A9-20, G8 2.10 | A Python name could collide with a name the emitter made (`ended1`, `raised1`, `self`): C++ that did not compile, or meant something else | Confirmed | Fixed | Every name the emitter makes matches one pattern, asserted where it is made; a Python name that matches it, or that C++ reserves, is escaped injectively (`py`, `_` as `_1`, a non-ASCII character as `_2` and its code point). The function parameter is `fn`, so `self` stays `self`. G8's `_l2_` prefix was not taken: C++ reserves no such prefix, but readable names stay as written |
| RL-208 | A9-21, G8 2.7 | `NotImplemented` was true in a boolean context | Confirmed | Fixed | TypeError since 3.14 (`NotImplemented should not be used in a boolean context`) |
| RL-209 | A9-22 | `abs()` compared with 0 and negated instead of calling `__abs__` | Confirmed | Fixed | `PyNumber_Absolute`: the int's own, else `__abs__`, else CPython's TypeError |
| RL-210 | A9-23, G8 2.13 | Compiled functions had no docstring, so a property's `__doc__` was None too | Confirmed | Fixed | The code record carries the docstring and `make_function` sets `__doc__` from it |
| RL-211 | Found while verifying (A8's `slot_rule.py` compiled) | A name CPython has and the runtime lacks yet was answered with NameError (`sorted`) or AttributeError (`str.startswith`, `object.__sizeof__`, `BaseException.add_note`), and `__getattr__` ran for it; a program catching those took the wrong branch | Confirmed | Fixed | `tools/cpython_names.py` records from the pinned CPython the builtins, a script's globals, `sys`, and each built-in type's own attributes (`runtime/src/cpython_names.inc`, checked by `make verify`). A lookup that finds nothing refuses such a name (`bella: not implemented: str.startswith (…)`, exit 70) before `__getattr__`, on instances (an `object.hpp` hook), classes and their metatype, C++ objects, `sys`, `builtins` and globals. A name CPython lacks too still raises |
| RL-212 | Found with RL-211 | `sys.maxsize` was 2\*\*62 − 1 | Confirmed: CPython's is 2\*\*63 − 1 | Fixed | It is beyond the immediates, so `sys` no longer has it and RL-211 refuses it until big ints |
| RL-213 | Found while verifying (G7's `syn_raise.py` compiled) | When an exception left a function, the frame record took the frontend's synthetic variables with the real locals: a raising list comprehension's partial result died after the handler | Confirmed: CPython drops it during unwinding (PEP 709 inlines the comprehension) | Fixed | As `eval2`'s `unwind_synthetic` (RL-186): a `StackValues` guard drops them, and a list, set or dict comprehension helper's iterator argument, newest first, after the temporaries and before the frame is recorded |
| RL-214 | Found while verifying (A8's `exec_refs.py` compiled) | A `__getattr__` that is not a function was called with the object and the name; and it ran while the AttributeError it replaces, and so its traceback, was alive | Confirmed: TypeError from `Hook.__call__`; then a descriptor dying after the hook instead of before | Fixed | CPython's `call_attribute`: a function or method descriptor gets the object and the name, another descriptor is bound first, anything else gets the name alone. The AttributeError is dropped first, as `PyErr_Clear` does. Model first (`refmodel/objects.py`, test `test_a_getattr_hook_is_called_as_call_attribute_does`), then `object.hpp` with a runtime hook for its own callables |
| RL-215 | Found while fixing RL-214 | The pointer to the exception being propagated, which frame guards record into, outlived the exception: a refusal unwinding later recorded frames into a dead object | Confirmed by reading: a use-after-free on any refusal after a handled exception died | Fixed | The `PyError` that is thrown or rethrown owns the mark and clears it when it dies; a copy never owns it |
| RL-216 | Found while checking RL-211 | The C++ types had an empty `__qualname__`: `repr(int)` was `<class ''>` | Confirmed | Fixed | `object.hpp`'s `builtin_class` gives a built-in type its name as `__qualname__` |
| RL-217 | Found while checking RL-216 | The prelude's builtins showed they were Python: `print` was a `function` (`<function print at …>`), bound as a method when stored on a class; `property` was a mutable class | Confirmed | Fixed | An exported prelude function's class is `builtin_function_or_method`: its repr, its `__self__` (the builtins module), and no binding; an exported class is immutable as a static type. The decision of 2026-11-02 implied it; `docs/emitter.md` section 1 now says it |
| RL-218 | Found while checking RL-217 | Method objects: a bound method did not read its function's attributes (`C().f.__name__` raised); `object.__new__` was `<built-in function __new__>` with `__self__` None; the prelude's `list.__repr__` and the like took any receiver; a slot wrapper (`list.__len__`) showed itself as a method descriptor | Confirmed | Fixed, one part refused | `method_getattro`'s fallback to `__func__`; `__new__` bound to its type as CPython shows it; the prelude's type methods check their receiver (tested against CPython in `runtime/tests/test_prelude.py`). The runtime holds slot wrappers as method descriptors: their repr and type are refused (the kinds come from RL-211's table) until the runtime has CPython's wrapper types (`TODO.md`) |
| RL-219 | Found while fixing RL-207 | Generated code and string names contained `__` (`code_T____init__`, `S___init__`), which C++ reserves, and a function with a non-ASCII qualified name was named by Python's salted `hash()`, so the generated C++ changed between runs | Confirmed | Fixed | One readable mapping for these names (runs of `_` folded, a non-ASCII character as `_u` and its code point, a dunder string as `S_dunder_…`), told apart by `unique`; test `test_generated_names_are_unreserved_and_reproducible` emits under two hash seeds |

### Found while writing examples (2026-11-03)

Small programs written to show the compiled leg, each compared with CPython 3.15.2
(`pipeline/build.py --run`). Refusals (`max`, `divmod`, `str %`, `2 ** 100`) are correct
behaviour; these three are not.

| ID | From | Finding | Verdict | Status | Evidence and fix |
|----|------|---------|---------|--------|------------------|
| RL-220 | Writing examples | A built-in type the runtime has no constructor for (`int`, `float`, `dict`, `type(len)`) fell into `object.__new__` and raised a TypeError CPython does not: `int("42")` said `int() takes no arguments`, `int()` and `dict()` `object.__new__(int) is not safe`; an explicit `object.__new__(int, 1)` checked its arguments before the type and dropped CPython's `, use int.__new__()` | Confirmed | Fixed | `type_call` refuses (`bella: not implemented: creating an instance of the built-in type 'int'`); `object.__new__(X)` for a built-in `X` checks first, as `tp_new_wrapper` does, and says CPython's words when CPython's `X` has its own `__new__` (the names table), else refuses; test `test_a_builtin_type_without_a_constructor_is_refused` |
| RL-221 | Writing examples | A frame's traceback entry is made when the exception leaves the function, with the line the frame reached by then; CPython makes it when the exception enters the frame (raised there, or arriving from a call). After a `finally` the report named the `finally`'s last line (line 6 for a `raise` on line 4), after a bare `raise` the `raise` (CPython: the original line), and `raise e` lost the original entry (CPython lists the frame twice) | Confirmed | Fixed (D-12, part 1) | Recorded where the exception arrives: `frame.arrived(e)` first in each catch the emitter writes, else the guard; the `PyError` names the frame that recorded the throw, a bare raise records nothing where it re-raises, leaving a frame lets the caller record; case C-3-30, test `test_traceback_entries_and_the_report_are_cpythons`. Measured: `def g():` with `raise ValueError` on line 4 inside `try`, `y = 2` on line 6 in its `finally`: CPython `line 4, in g`, compiled `line 6, in g`; the same for a bare `raise` in a handler, a failed call under `finally`, a raise in a loop's `try`; `raise e`: CPython two entries for the frame, compiled one |
| RL-222 | Found while checking RL-221 | A caught exception keeps its frame alive in CPython (the traceback entry holds the frame object, which takes the locals when the function returns); the compiled guard moves locals into an entry only when the exception leaves, so a function returning a caught exception killed its locals at the return | Confirmed | Deferred to step 3c (D-12, part 2) | An exception stored in its own frame's local makes a cycle CPython frees only in its collector; until 3c the locals die at the return. `def f(): a = N("a"); try: [][0] / except IndexError as e: return e`, then `e = f(); print("returned"); del e`: CPython prints `returned` before `dies a`, compiled after |
| RL-223 | Found while fixing RL-221 | A list, set or dict comprehension's helper appeared in tracebacks (`line 2, in _comp3`); CPython inlines comprehensions (PEP 709), so they have no frame | Confirmed | Fixed | The frontend marks the helper (`inlined`, L1 `FunctionDef`, L2 `Code.meta`); its code record has `shown` false, so its frame records nothing and its locals die in unwinding, as CPython's inlined comprehension restores its variable; a generator expression keeps its frame |
| RL-224 | Found while fixing RL-221 | The prelude's frames appeared in tracebacks (`<bella prelude builtins.py>, line 192, in _list_repr`, and its comprehension); in CPython these are C functions | Confirmed | Fixed | The prelude is emitted with every code record `shown` false (`to_cpp(..., prelude=True)`): its frames record nothing and clear the mark, so the caller records the call |
| RL-225 | Found while fixing RL-223 | A frame's line is its statement's first line: an error on line 9 of a statement that starts on line 8 is reported at 8; CPython reports the failing instruction's line | Confirmed | Open | Needs expression positions through the frontend and L2; `docs/emitter.md` section 5 |
| RL-226 | Found while writing C-3-30 | The uncaught report printed only the last exception: no cause (`raise ... from`), no context, no separator lines | Confirmed | Fixed | `print_traceback` follows `traceback.TracebackException` (compact): the chain first, cause, else context unless suppressed, an exception already shown ends it; `__notes__` is refused. The unraisable report prints the chain too, as CPython 3.15's does (measured) |
| RL-227 | Found while writing C-3-30 | stdout was flushed after the uncaught report; CPython flushes it before, so `2>&1` showed the lines in another order | Confirmed | Fixed | `run_main` flushes stdout before the report; the test compares one merged stream |

### Tracebacks, dicts and operators (A10, G9)

All 13 of A10's findings and all 10 of G9's reproduce on CPython 3.15.2 and the compiled runner
(`PYTHONHASHSEED=0`); three are the same defect (A10-3 and G9 2.4, A10-7 and G9 2.5, A10-10 and
G9 2.6), so 20 are distinct. G9 numbered its findings RL-228 to RL-237 itself; those labels are
its own, and its section numbers are mapped below. Two of G9's suggested fixes are wrong and were
not taken: `list.remove` after `__eq__` shortened the list does not raise ValueError (CPython
deletes the clamped slice `[i, i+1)` and returns None), and dict iteration does not check the
dict's version (CPython counts the entries it still expects, `dictiterobject.len`; a version check
would reject replacing a value, which is allowed). A10-3 is the larger part: an exception's
`args`, `__traceback__`, `__cause__`, `__context__` and `__suppress_context__` were entries of its
`__dict__`. They are now C fields of BaseException, modelled first (`refmodel/objects.py`,
`RefClass(native=...)`: a built-in type's fields, released in its clear function's order, the dict
at its place). Every program is `pipeline/tests/test_review_2026_11_03b.py`; the mechanisms are
cases C-3-31 (exception fields and chaining) and C-6-09 (what a dict operation calls back into).
Fixing them found RL-248 to RL-255.

| ID | From | Finding | Verdict | Status | Evidence and fix |
| --- | --- | --- | --- | --- | --- |
| RL-228 | A10-1 | An error while matching an `except` clause (`except missing:`) was reported at the line of the raise being matched (3), not the clause's (4) | Confirmed | Fixed | L1's `Handler` carries the `except` line; the lowering marks it before the clause's type is evaluated and checked (`CHECK_EXC_MATCH`'s location). Report test `RL-228 a handler header is matched at its line` |
| RL-229 | A10-2 | A raise kept an exception's earlier `__context__` (only an absent or None one was set) and never cut a link back to the new exception, so a reused exception showed a stale context and a cycle could form | Confirmed | Fixed | `raise` follows `_PyErr_SetObject`: the context is always the exception being handled, unless it is the one raised; first the handled exception's context chain is walked (Floyd's) and a link to the new exception cut, a cycle already there left alone. C-3-31 |
| RL-230 | A10-3, G9 2.4 | The linkage fields were ordinary attributes: `raise E from 1` raised E with `__cause__` 1, assigning `__cause__` did not set `__suppress_context__`, any value was accepted for `__cause__`, `__context__`, `__traceback__`, `__suppress_context__`, and `args` stayed a list; they showed in `vars(e)`, and they died with the dict's entries (args before the dict's values; CPython: the dict, then args, the cause, the context) | Confirmed | Fixed | Model first: `RefClass(native=...)`, tests `test_a_builtin_bases_fields_die_after_the_slots_in_its_clear_order` (a mixin first keeps the exception's layout). `object.hpp`: `ClassSpec.native`, the fields indexed after the slots, released by the solid base's order. The runtime: BaseException's getsets and member as `Objects/exceptions.c` has them (CPython's checks and words, none deletable, `args` through `PySequence_Tuple`, a cause setting `__suppress_context__` even when None); AttributeError's `name`, `obj` and NameError's `name` as members. `raise ... from` as `do_raise`: an exception class is called (its result must be an exception), an instance taken, None clears, else TypeError. C-3-31. The member presents as a `getset_descriptor` (RL-254) |
| RL-231 | A10-4 | An exception whose `__str__` raised aborted the program (SIGABRT) while it was reported | Confirmed | Fixed | `print_one`: `_safe_string`, any exception (a SystemExit too, as the bare `except:`) gives `<exception str() failed>`; both reports go through it. Report tests `RL-231 ...` |
| RL-232 | A10-5 | `d[k] = v` whose key comparison raised never released the count taken for `v` | Confirmed | Fixed | Model first: `test_a_store_that_fails_takes_no_count`. `dict_put` takes the value's count only once the lookup succeeded; `dict_store` gives it back when the lookup raises, so `v` dies before the handler runs |
| RL-233 | A10-6 | `setdefault` looked the key up twice; `__eq__` changing its answer between them replaced an existing value | Confirmed | Fixed | `dict_setdefault`: one lookup, the new key inserted where it ended (`dict_setdefault_ref_lock_held`) |
| RL-234 | A10-7, G9 2.5 | `dict.pop` looked up (and hashed) twice: an extra `__hash__` or `__eq__` call could raise or leave the key in the dict | Confirmed | Fixed | `pop_lock_held`: an empty dict hashes nothing (`{}.pop([])` is KeyError, measured), otherwise one hash and one lookup through `dict_pop` |
| RL-235 | A10-8 | `dict.copy()` re-inserted every entry, comparing colliding keys | Confirmed | Fixed | `copy_lock_held`: an empty dict's copy is new; a split dict's shares its keys; a combined one at most a third deleted is cloned, table and all; any other is merged into a new dict (`dict_dict_merge`), which compacts it and compares what collides. C-6-09 |
| RL-236 | A10-9 | `dict.fromkeys` of a dict (or set) hashed every key again | Confirmed | Fixed | `dict_dict_fromkeys` and `dict_set_fromkeys`: one resize, then the stored hashes, from the live table; any other iterable is iterated and hashed |
| RL-237 | A10-10, G9 2.6 | A dict iterator went on after a key was deleted and another added (the size unchanged), yielding an entry it did not expect | Confirmed | Fixed | The iterator counts the entries still to come; meeting one more raises `RuntimeError: dictionary keys changed during iteration` and exhausts the iterator (`dictiter_iternextkey`); the same for the values and items iterators |
| RL-238 | A10-11 | `except (ValueError, 42):` matched ValueError; CPython checks every type of a clause first. A nested tuple was accepted too | Confirmed | Fixed | `exception_matches` as `CHECK_EXC_MATCH`: `_PyEval_CheckExceptTypeValid` (each item an exception class), then the match |
| RL-239 | A10-12 | `x in some_list` leaked a count of the item whose `__eq__` raised | Confirmed | Fixed | The item is held by a `Ref` while it is compared |
| RL-240 | A10-13 | The too-many-positional message dropped `were` when keyword-only arguments were given | Confirmed | Fixed | `too_many_positional`'s wording: the keyword-only clause, then `was` or `were` |
| RL-241 | G9 2.1 | `list.remove` whose `__eq__` emptied the list erased past the end (SIGSEGV) | Confirmed | Fixed | `list_remove_impl`: each item held while compared, against the list as it is then; a match deletes the slice `[i, i+1)` clamped to the list as `__eq__` left it, and returns None (G9's suggested ValueError is not CPython's) |
| RL-242 | G9 2.2 | `a.extend(a)` and `a += a` never ended | Confirmed | Fixed | `_list_extend`: a list extended by itself is repeated (`list_inplace_repeat`) |
| RL-243 | G9 2.3 | `list.count` iterated an uncounted copy of the list: after `__eq__` cleared it, it compared freed objects | Confirmed | Fixed | `list_count_impl`: the live list, each item held while compared |
| RL-244 | G9 2.7 | `MethodType.__new__()` and `slice.__new__()` underflowed the argument count (`got 18446744073709551615`); `BaseException.__new__(int)` and `(1)` printed a literal `X` | Confirmed | Fixed | `tp_new_wrapper`'s checks, shared by the C++ types' `__new__`: `T.__new__(): not enough arguments`, `T.__new__(X): X is not a type object (int)`, `T.__new__(int): int is not a subtype of T` |
| RL-245 | G9 2.8 | `__iter__ = None` called None (`'NoneType' object is not callable`) | Confirmed | Fixed | `slot_tp_iter`: `__iter__` None is not iterable, whatever `__getitem__` says; `slot_sq_contains`: `__contains__` None is `not a container`; and `in` rewords `iter()`'s TypeError as `argument of type 'X' is not a container or iterable` (`_PySequence_IterSearch`), which the runtime did not either |
| RL-246 | G9 2.9 | `object.__init__`'s message named the class by `__qualname__` | Confirmed | Fixed | `tp_name`, the class's `__name__` |
| RL-247 | G9 2.10 | `list.pop(i)` checked for an empty list before converting `i`, so an `__index__` that emptied it gave the wrong message, and `[].pop('x')` was IndexError instead of TypeError | Confirmed | Fixed | The argument is converted first (Argument Clinic), then `pop from empty list` |
| RL-248 | Found while fixing RL-234 | `list`, `dict`, `set` and the keys and items views were hashable (`hash([])` was an int; `{[]: 1}` worked): their types had no `__hash__ = None`, so `object.__hash__` was found | Confirmed | Fixed | Their dicts hold `__hash__` None, as CPython's (`PyObject_HashNotImplemented`) |
| RL-249 | Found while fixing RL-248 | An unhashable key's TypeError said `unhashable type: 'C'`; CPython 3.15 says `cannot use 'C' as a dict key (unhashable type: 'C')`, and `... as a set element (...)` | Confirmed | Fixed | `dict_key_hash` and `set_key_hash` word it as `dict_unhashable_type` and `set_unhashable_type` (the type by `%T`); `hash()` itself keeps the plain message |
| RL-250 | Found while fixing RL-231 | The reports named an exception's class by `__name__`; CPython's use `__qualname__` (`Outer.E: ...`) | Confirmed | Fixed | `fully_qualified_name`, also `%T`'s. Report test `RL-250 ...` |
| RL-251 | Found while checking RL-230 | `type(C.__dict__['x'])` of a `__slots__` member crashed the program: the header's `member_descriptor` class was never made a type | Confirmed | Fixed | The runtime makes `member_descriptor` a type; its methods are still refused (the names table) |
| RL-252 | Found while fixing RL-233 | An insert that resized the table looked the key up again, comparing colliding keys a second time | Confirmed | Fixed | `insert_combined_dict`: after the resize, `find_empty_slot`, which compares nothing. C-6-09 (`the insert that resizes`: 5 comparisons, was 10). `rebuild` now rounds as `calculate_log2_keysize` (at least, not above), which only the bulk resizes reach |
| RL-253 | Found while fixing RL-235 | `{**d}`, `d.update(other)` and `d | other` copied the other dict's items first and inserted them all: no clean-dict clone into an empty dict, and an `__eq__` that changed `other` went unnoticed | Confirmed | Fixed | `dict_merge_dict` as `dict_dict_merge` (override): the clone into an empty dict when `other` is clean, else one resize and each entry from the live table with its stored hash, `RuntimeError: dict mutated during update` when `other`'s size changes |
| RL-254 | Found while fixing RL-230 | `BaseException.__dict__['__suppress_context__']` presents as a `getset_descriptor`; CPython's is a `member_descriptor` | Confirmed | Open | Behaves as CPython's member; only its type differs. The runtime's `member_descriptor` has no methods yet (RL-251); `docs/emitter.md` section 5 |
| RL-255 | Found while documenting RL-230 | A store to a field CPython's exception has and the runtime does not (`StopIteration(5).value = 6`) went into the instance `__dict__`; reading it was already refused | Confirmed | Fixed | `refuse_absent_data_descriptor`: a store or delete of a name no class of the runtime has, where CPython's built-in base has a member or getset (the names table), is refused as the read is. Test `test_stores_to_fields_cpython_has_are_refused` |

### Compiled imports, super, metaclasses (G10, S1)

G10's five findings all reproduce, and three of them were found again by S1. S1, eight Sonnet reviewers with a focus area each, did not see G10's report. Every finding was written as a program and compared with CPython 3.15.2 before anything changed (`pipeline/tests/test_review_2026_11_04.py`, 113 programs at that point, 103 differing); two of those programs were themselves wrong, using computed import names that spec section 8 keeps out of the closed world, and were rewritten. G10's labels RL-256 to RL-260 are kept. The worst of the round was introduced by this round's own range: RL-281, finalisers at exit reading their globals as None. RL-324, `next()` refusing every iterator class of a program's, was found only because a fix went near it.

| ID | Source | Finding | Verdict | Status | Evidence and resolution |
| --- | --- | --- | --- | --- | --- |
| RL-256 | G10 2.1, S1 closure, bootstrap, imports | `from pkg import *` never compiled the submodules `__all__` names, so the import ended in AttributeError (a wrong exit status, not a refusal) | Confirmed | Fixed | `closed_world.star`: the names of a literal `__all__` (`=`, `+=`, `extend`, `append`, `insert`); a computed one takes every submodule the package has. `__import__(..., fromlist=['*'])` too |
| RL-257 | G10 2.2, S1 closure | A dotted frozen name (`importlib.machinery`) went to the program's file; FrozenImporter takes it whatever the parent's path says | Confirmed | Fixed | Such a name never searches the program's directory. One the build does not compile is refused by name (`ModuleKind::Refused`), which also answers `import __hello__` (S1 bootstrap's suspicion) |
| RL-258 | G10 2.3, S1 closure | `from importlib import import_module` and `import importlib as il` were not recognised by the scanner | Confirmed; not visible yet, since `importlib` itself is refused | Fixed | `_called_import`: any `import_module` by name or attribute with a literal name, and a relative name with a literal or `__package__` anchor |
| RL-259 | G10 2.4, S1 closure | `BELLA_KEEP_DEBUG` was not in the link key, so the stripped binary came back | Confirmed | Fixed | The strip flag is in the key. `test_build_cache_keys` |
| RL-260 | G10 2.5, S1 lowering | Two `_falls_through`, which disagreed on loops | Confirmed; only unreachable C++ came of it | Fixed | One definition, `pipeline/l2/grammar.py` `falls_through` |
| RL-261 | S1 closure | `__import__` with `fromlist=`, `level=`, and `builtins.__import__` loaded modules the scanner never saw | Confirmed | Fixed | `_called_import` reads them, by position and by keyword |
| RL-262 | S1 closure | A directory with no `__init__.py` named like a standard-library module (`types/`, `logging/`) made the program refuse; a regular module on a later path entry wins over a namespace package | Confirmed | Fixed | `_regular_in_stdlib` |
| RL-263 | S1 closure | A PEP 263 cookie crashed the build with a Python traceback; a BOM was refused | Confirmed | Fixed | `read_source` uses `decode_source`; undecodable bytes are the build's refusal. `test_source_encodings` |
| RL-264 | S1 closure | A program given by a relative path had that relative path in its frames; 3.15's `co_filename` is absolute | Confirmed | Fixed | `build.py`'s command line passes the absolute path. `test_paths_as_cpython_keeps_them` |
| RL-265 | S1 closure | `_pipeline_bytes` tested the absolute path for a `tests` part: a checkout under a directory of that name had an empty compiler key | Confirmed by the reviewer's copies and by reading | Fixed | Tested relative to the repository |
| RL-266 | S1 closure | The lowered-unit key left out what `header_macros()` depends on, so another `CXXSTD` reused text that no longer compiled | Confirmed | Fixed | The macro names are in the key |
| RL-267 | S1 closure | `_forget_previous` deleted the binary built under another spelling of the same path | Confirmed | Fixed by RL-264 | Both spellings now build one binary. A rebuild under another compiler still replaces the old one, which is that function's purpose |
| RL-268 | S1 closure | A symlinked program's `__file__` was the link's target | Confirmed | Fixed | `run_main` takes `__file__` (the link) and `sys.path[0]` (the target's directory) apart |
| RL-269 | S1 closure | A reachable module with a SyntaxError refuses the whole build, where CPython raises at the import | Confirmed | Accepted | A clean refusal (exit 70) under decision P-1; no wrong answer |
| RL-270 | S1 bootstrap, imports | `m.__dict__ = ...` and `m.__class__ = ...` on a module wrote ordinary entries into its namespace | Confirmed | Fixed | `readonly attribute`, and `object_set_class`'s two messages; a ModuleType subclass stays [P2+] |
| RL-271 | S1 bootstrap | ImportErrors the runtime raises had `.msg` None | Confirmed | Fixed | `raise_new` sets it for ImportError and its subclasses |
| RL-272 | S1 bootstrap, imports | `sys.__doc__`, `builtins.__doc__` and `type(sys).__doc__` read object's docstring or None | Confirmed | Fixed | A generated docstring table (`tools/cpython_names.py`, checked by `make verify`) gives these and every built-in type its own, so `int.__doc__` and `(5).__doc__` are CPython's. `sys` and `builtins` start with the five names CPython's do; the rest of their namespaces follow as they fill |
| RL-273 | S1 bootstrap | `types.SimpleNamespace`: `'SimpleNamespace'` for `'types.SimpleNamespace'` in messages, a writable `__dict__`, several argument errors | Confirmed | Fixed | `ClassObject::name_prefix` (a dotted tp_name, as C types have); a read-only member; the checks a C method's descriptor makes |
| RL-274 | S1 bootstrap | `SourceFileLoader` had no bases, and a `load_module` that 3.15 removed | Confirmed | Fixed | `_LoaderBasics`, `SourceLoader`, `FileLoader`, `SourceFileLoader` as `_bootstrap_external` has them, their functions' `__module__` included (RL-325) |
| RL-275 | S1 bootstrap | `__package__` differing from `__spec__.parent` is refused where CPython warns | Confirmed | Accepted | A clean refusal: the DeprecationWarning shows in `__main__` and the warnings machinery is not there yet |
| RL-276 | S1 lazy | `__lazy_import__` at module level with another globals dict was refused | Confirmed | Fixed | CPython asks only whether the calling frame is at module level |
| RL-277 | S1 lazy | `__lazy_import__` in a function is refused where CPython raises SyntaxError | Confirmed | Open | Known gap (`docs/emitter.md` section 5): the runtime has no SyntaxError class yet |
| RL-278 | S1 lazy | `lazy_import.resolve(1)`: the wrong TypeError text | Confirmed | Fixed | METH_NOARGS's message |
| RL-279 | S1 lazy | `lazy_import` had no docstring, and `lz.resolve.__doc__` was object's | Confirmed | Fixed | The type's from the table. A built-in method's docstring is now refused by name, not answered by object's (RL-310's rule). The order of the type's `__dict__` is not CPython's: no program reaches it but by listing it |
| RL-280 | S1 lazy | `[].append = 1` and `(1).real = 1`: the wrong AttributeError; `del [].append` refused | Confirmed | Fixed | `_PyObject_GenericSetAttrWithDict`'s three messages, from what the names table says the attribute is |
| RL-281 | S1 imports | At exit a `__del__` read its own globals as None, because the runtime cleared namespaces in order; CPython's collector runs every finaliser with them whole | Confirmed; introduced by `3baa30e` | Fixed | Model first (`RefObject.finalize`: a finaliser runs once). `clear_modules` does `finalize_modules`' steps: sys's special names, `sys.modules` emptied, then every finaliser reachable from the namespaces, then the clearing. The walk stands in for the collector until step 3c. An import from a finaliser fails with CPython's message |
| RL-282 | S1 imports | `sys.exit(obj)` whose `__str__` raises aborted the process (exit 134) | Confirmed | Fixed | `exit_status` as `_Py_HandleSystemExitAndKeyboardInterrupt`: the error is dropped, the status is 1 |
| RL-283 | S1 imports | `SystemExit.code` refused, and the status read from `args` | Confirmed | Fixed | A native field as `SystemExit_init` sets it; the status is the `code` attribute, a subclass's too |
| RL-284 | S1 imports | A package's `__path__` extended at run time, or a module `__getattr__` answering for `__path__`, finds nothing new | Confirmed | Not a defect | Spec section 8: nothing outside the closed world can be imported, and the answer is ModuleNotFoundError |
| RL-285 | S1 imports | `__package__ = 'x'` in `__main__`, then a relative import | Confirmed | Not a defect | A computed import, outside the closed world (spec section 8), until the policy's registry exists |
| RL-286 | S1 imports | `import *` with a bad `__all__` read it by subscripting; `range(3)[0]` itself raised TypeError | Confirmed | Fixed | PySequence_GetItem's messages. `range` indexes and slices, with `start`, `stop`, `step`, `index`, `count` |
| RL-287 | S1 imports | `__import__('pkg..sub')` and `('pkg.sub.')` loaded `pkg/__init__.py` under a wrong name | Confirmed | Fixed | `find` takes no name with an empty part |
| RL-288 | S1 imports | `module('a', name='b')` and `module(nme='n')`: the wrong errors | Confirmed | Fixed | `_PyArg_UnpackKeywords`' order |
| RL-289 | S1 imports | The order of finalisers at exit differs after an uncaught exception | Confirmed | Not a defect | D-07: unspecified |
| RL-290 | S1 lowering | A `try` whose body cannot complete, with an `else`, failed well-formedness on a valid program | Confirmed; from before this range | Fixed | The `else` is dropped as CPython drops it; `falls_through` is exact for it |
| RL-291 | S1 lowering | A variable named `match` read in an `except` body broke the C++ | Confirmed | Fixed | The emitter's flag goes through `aux()` |
| RL-292 | S1 lowering | `contract_assert`, a C++26 keyword, was not escaped | Confirmed | Fixed | In `_KEYWORDS` |
| RL-293 | S1 lowering | From the second iteration a `while` test's or `__next__`'s traceback line was the body's last | Confirmed | Fixed | `again_at`: the loop says its line each time round |
| RL-294 | S1 strs | `find`, `startswith` and `count` copied the whole string on each call: a scanning loop was quadratic (67 s where CPython takes 0.03 s) | Confirmed; slow, not wrong | Fixed | `find`, `rfind`, `index`, `rindex`, `count`, `startswith`, `endswith` read the string in place. The search stays naive, O(n*m) |
| RL-295 | S1 strs | `'a'.find(None)`: `not NoneType` where CPython says `not None` | Confirmed | Fixed | `_PyArg_BadArgument` |
| RL-296 | S1 strs | `__index__` returning a non-int: 3.14's wording; a slice ignored `__index__` altogether | Confirmed | Fixed | `%T.__index__() must return an int, not %T`, and `_PyEval_SliceIndex`. A strict subclass of int returned is refused (a DeprecationWarning in CPython) |
| RL-297 | S1 strs | The empty string and one-character Latin-1 strings were not one object; `split` with `maxsplit=0` returned the receiver | Confirmed | Fixed | `str_new` and `str_from_codepoints` share them, as the literals are; a split's tail is a new string |
| RL-298 | S1 remediation | `dict.popitem` looked its key up again, so an `__eq__` could remove the wrong entry | Confirmed | Fixed | `dict_take_last`: by index, nothing compared, as `lookdict_index`. The model never compared |
| RL-299 | S1 remediation | `x in C.__dict__` and `x in iterator` raised TypeError | Confirmed | Fixed | PySequence_Contains for every kind; a mappingproxy hashes its key first |
| RL-300 | S1 remediation | A set used as a key of `in`, `remove`, `discard` raised TypeError | Confirmed | Fixed | `with_set_key`: looked for as a frozenset, as `set_contains` does |
| RL-301 | S1 remediation | A comprehension in a lambda in a loop: NameError | Confirmed | Fixed | `_hoist` visits such a statement twice; the second visit overwrote the lambda's prelude |
| RL-302 | S1 remediation | `del l[:1]` raised a nonsense TypeError | Confirmed | Fixed | `list_ass_subscript`, in its two orders of release; `list indices must be...` for a bad key |
| RL-303 | S1 remediation | Too many positional arguments was reported before a bad keyword | Confirmed | Fixed | `initialize_locals`' order |
| RL-304 | S1 remediation | `T.__new__(X)` skipped tp_new_wrapper's checks for most types; `list.__new__(list)` failed | Confirmed | Fixed | `new_wrapper_class` is tp_new_wrapper whole; each exception type CPython gives a `__new__` has its own; list, tuple, str and bool have theirs |
| RL-305 | S1 remediation | `AttributeError(name=, obj=)`, `NameError(name=)` rejected keywords | Confirmed | Fixed | `AttributeError_init`, `NameError_init`; an unknown keyword gets CPython's message and suggestion (`unexpected_keyword`, Python/suggestions.c) |
| RL-306 | S1 remediation | `__bool__ = None` and `__next__ = None` gave the wrong TypeErrors | Confirmed | Fixed | `slot_nb_bool`; `builtin_next`, see RL-324 |
| RL-307 | S1 remediation | Six wordings: `[*x]`, `''.join(x)`, `[1][obj]`, an `__iter__` returning a non-iterator, `keys()` returning a non-iterable, `dict(x)` with `__getattr__ = None` | Confirmed | Fixed | Each as CPython 3.15's source has it |
| RL-308 | S1 remediation | A class whose `__module__` is not a str: the report said `E`, not `<unknown>.E` | Confirmed | Fixed |  |
| RL-309 | S1 classes | `type.__repr__` called the metaclass's `__repr__`, so `super().__repr__()` in one recursed for ever | Confirmed | Fixed | `type_repr_of` |
| RL-310 | S1 classes | `int` had no special methods of its own: `(5).__repr__()` and `super().__repr__()` were object's | Confirmed | Fixed | `runtime/src/slots.cpp`: int's, bool's, dict's, and those of str, list, tuple, set, frozenset, range, slice, None. `refuse_shadowed`: a name CPython's type has of its own, found on a later class here, is refused where it is read |
| RL-311 | S1 classes | `__iadd__`, `__imul__`, `__ior__` of an int or dict subclass were ignored | Confirmed | Fixed |  |
| RL-312 | S1 classes | `'ab' * K(2)` rejected an int subclass; `range(3)[K(1)]` too | Confirmed | Fixed |  |
| RL-313 | S1 classes | A mixin after the built-in base overrode the built-in's own methods | Confirmed | Fixed | `overrides_builtin` walks the MRO: the built-in's slot wins over what follows it |
| RL-314 | S1 classes | A metaclass's `mro()` was ignored | Confirmed | Fixed | Model first (`RefClass.set_mro`). `mro_invoke` and `mro_check` |
| RL-315 | S1 classes | No instance layout conflict: `class J(E, F)` of int and dict subclasses was made, and failed later | Confirmed | Fixed | `best_base`; `solid_base` as `shape_differs`, so exception types without fields of their own do not conflict |
| RL-316 | S1 classes | `set(d)`, `{*d}`, `dict.fromkeys(d)` bypassed a dict subclass's `__iter__` | Confirmed | Fixed | PyDict_CheckExact, as CPython |
| RL-317 | S1 classes | `type(name, bases, ns)` set no `__module__` | Confirmed | Fixed | `type_new_set_module`, from the calling frame |
| RL-318 | S1 classes | A local or parameter named `__class__` with `super()` crashed the compiler | Confirmed | Fixed | The function has no such cell: RuntimeError at run time, as CPython |
| RL-319 | S1 classes | `del self` then `super()`: UnboundLocalError for RuntimeError | Confirmed | Refused | At build, by name: the load of a deleted local has no way to say so yet |
| RL-320 | S1 classes | Thirteen small differences | Twelve confirmed; `build_class()` in a message not reproduced, `__build_class__` being refused by name | Fixed | `__init_subclass__`'s and `type()`'s messages, `__set_name__`'s note, MRO conflict names (`set_mro_error`), `__get__(None, None)`, a NUL in a type's name, `__index__` on a metaclass, `del int.real`, `repr(slice)` |
| RL-321 | Found while fixing RL-300 | `hash()` of a value beyond the immediates (62 bits and a sign, about half of all str and tuple hashes) returns a truncated number, and the tables used another | Confirmed; from before this range. A proxy key whose `__hash__` returns `hash(s)` missed `s` 2014 times in 4000 | Fixed; the width accepted (D-22, the author, 2026-11-05) | `hash_of` fits every hash at one point, so `hash()`, `__hash__`, tuples, frozensets and the tables agree; values stay 63 bits until `hash()` can return a big int. Tests `RL-321-*`, `test_a_hash_is_deterministic_d_22` |
| RL-322 | Found while fixing RL-300 | `frozenset`, `range` and `slice` hashed by identity, so two equal frozensets missed each other in a dict; `hash(None)` was an address | Confirmed | Fixed | `frozenset_hash_impl`, `range_hash`, `slice_hash`, `none_hash` |
| RL-323 | Split from RL-274 | No class has `__weakref__` in its `__dict__`, so `list(vars(C))` differs from CPython's | Confirmed | Fixed | With weak references (C-9-10): the getset goes in with `__dict__`, before the class's members, in type_ready's order |
| RL-324 | Found while fixing RL-306 | `next(obj)` raised TypeError for every iterator class of a program's | Confirmed | Fixed | `builtin_next`, a StopIteration's value kept |
| RL-325 | Found while fixing RL-274 | A function's `__module__` could not be set or deleted, which `functools.wraps` does | Confirmed | Fixed |  |
| RL-326 | Found while fixing RL-281 | A finaliser at exit that makes a new object with a finaliser: CPython's collector then treats the group as resurrected and never finalises it; here it dies with the namespaces | Confirmed | Not a defect | D-07; to look at again with the collector in 3c |

### What G11's clean report covers

G11 reports no defects in `62d083b..0081164`, so it has nothing to reproduce. It read and ran this checkout, not that range: all its line citations (`types.cpp` 536, 971, 977, 1213, `object.hpp` 644, 670) are those of `365e55e`, which has the fixes for A11's findings, and none are those of `0081164`. So it is no evidence about `0081164`, and it does not contradict A11: its "slots.cpp correctly handle instances of built-in types and their subclasses" is false at `0081164` (RL-332) and true where it ran. It is read as a clean pass over those areas at `365e55e`. Its last probe, a `property` subclass whose `__init__` does not call `super()`, stops with a clean refusal of `property.fget`, which is not a finding. A review run in the working checkout should from now on be given a checkout of its end commit, as A11 made itself.

### Class dict views, built-in names (A11)

A11 is Codex astra-low on `62d083b..0081164`. All four findings reproduce on `dd187f7`. Probing the classes they belong to found three more, RL-332 the worst of them: A11 reports `[].__add__`, and running every special method against subclass instances showed none from `slots.cpp` bound at all. Tests `pipeline/tests/test_review_2026_11_05.py`.

| ID | Source | Finding | Verdict | Status | Evidence and resolution |
| --- | --- | --- | --- | --- | --- |
| RL-327 | A11 #1 | A program's class named after a final built-in cannot be subclassed | Confirmed (`0081164`, mine): `class range: ...; class C(range)` raised TypeError | Fixed | `ClassObject::final_type`, set when a built-in type is made, so a name a program can also use decides nothing |
| RL-328 | A11 #2 | A view of a class's dict kept from `mro()` misses `__doc__`, `__hash__` and `__dict__` | Confirmed (`0081164`, mine). `C.__dict__` itself missed them afterwards too, since it reads the same dict | Fixed | From `mro()` on, every insertion goes through `set_attr` |
| RL-329 | A11 #3 | `[].__add__(R())` tries `R.__radd__`; so do str's and tuple's, and `__mul__`, `__rmul__` | Confirmed (RL-310, `e55e561`). `__mul__` also worded a non-index operand as the operator does | Fixed | `sequence_concat` and `sequence_repeat`: sq_concat and sq_repeat, as `wrap_binaryfunc` and `wrap_indexargfunc` call them. Every method of the built-in types against a reflecting operand now matches |
| RL-330 | A11 #4 | `_abc_init` iterates what `items()` returns twice, and each item twice | Confirmed (`0081164`, mine) | Fixed | One iterator, kept, as `PyMapping_Items` and `PySequence_Fast` do |
| RL-331 | Found on RL-327 | The same name-keyed look-up elsewhere: `class list(dict)`, `+ 1` was refused where CPython raises TypeError; a method's argument message read the table by a program's class name | Confirmed (`refuse_unimplemented_operator` from before this range) | Fixed | The row is the built-in under the class; `cpython_attribute_kind` answers nothing for a program's class |
| RL-332 | Found on RL-329 | No special method from `slots.cpp` binds through a subclass instance: `E(1).__add__(2)`, `D().__eq__(x)` raise TypeError | Confirmed (RL-310, `e55e561`); the operators work, so the corpus never showed it | Fixed | `slot()` made a plain function and set its binding afterwards, and a Builtin's class comes from its binding at construction, so it had no `__get__` |
| RL-333 | Found on RL-328 | What `mro()` sees of the class: CPython has `__dict__` there and not the slots' members; this had the reverse | Confirmed (RL-314, `e55e561`), measured on 3.15.2 | Fixed | `__dict__` goes in first; the members leave for the call and return after it, in order |

### Calls, `sys`, `re`'s buffers, what a subclass overrides (G12, A12)

G12 is gemini-3.8-flash-high on `d46c55b..1dab41b`; A12 is Codex astra-low on five of those commits, because the provider's filter stopped its run on the whole range. All nine findings reproduce on `1dab41b` against 3.15.2. A12 #4 and a suspicion from reading G12 #3 are the same defect. Each fix is in `pipeline/tests/test_review_2026_11_06.py`, where its program and what stands around it run against CPython.

| ID | Source | Finding | Verdict | Status | Evidence and resolution |
| --- | --- | --- | --- | --- | --- |
| RL-334 | G12 #1 | `f.__defaults__` longer than the parameters: `n - ndefaults` wraps, so `f()` says a required argument is missing, and too many arguments reports "from 18446744073709551614" | Confirmed: `def f(x)`, `(10, 20)`, CPython 20. The wording by reading | Fixed | `first_default` signed, as `initialize_locals`'s `m`; `too_many_positional` says what CPython says |
| RL-335 | G12 #2 | `sys.getsizeof(o, default)` ignores the default | Confirmed (`1dab41b`, mine): `__sizeof__ = None` raised TypeError, CPython 42 | Fixed | A TypeError, subclasses too, is the default; other exceptions pass, with or without one |
| RL-336 | G12 #3 | `iter(f, s)` lets `f`'s StopIteration out with what it carries | Confirmed (`a6309a4`, mine): `args (42,)`, CPython `()` | Fixed | `PyErr_Clear`, and a new one |
| RL-337 | G12 #4 | `sys.exit(T((1, 2)))` loses the tuple subclass | Confirmed (`1dab41b`, mine). Wider than reported: a plain tuple lost its identity too, `e.args is t` | Fixed | `args` is the tuple itself, `code` too with more than one item, as `_PyErr_CreateException` and `SystemExit_init` leave them. G12's account, that nothing is unpacked, is not the mechanism: one item still makes `code` that item |
| RL-338 | A12 #1 | A scanner over a bytearray does not hold its buffer, so the bytearray resizes under it | Confirmed (`a6309a4`, mine): `b.append(98)` passed, CPython BufferError | Fixed | `BytesObject::exports`, the check in every path that changes size (`PyByteArray_Resize`'s rule: the same size is no change; `take_bytes` asks outright). A scanner holds it through `_BufferHold`, released when it goes. Nothing else takes an export yet |
| RL-339 | A12 #2 | `"abc"[::Step()]` calls `__index__` twice | Confirmed (`10254b5`, mine) | Fixed | The slice is read once, and those indices decide whether the string comes back unchanged |
| RL-340 | A12 #3 | `__reduce_ex__` asks a tuple subclass for its overridden `__len__` | Confirmed (`cbc3477`, mine): ValueError, CPython accepts | Fixed | `tuple.__len__`, as `PyTuple_GET_SIZE` |
| RL-341 | A12 #4 | `iter(f, s)` misses the identity test, so a NaN or a never-equal sentinel never stops | Confirmed (`a6309a4`, mine) | Fixed | `is` first, as `PyObject_RichCompareBool`; an `__eq__` that raises leaves the iterator as it was |
| RL-342 | A12 #5 | `s.__mul__ == s.__rmul__`: two method wrappers over one function compare equal | Confirmed (`cbc3477`, mine), `(1).__add__ == (1).__radd__` was right already | Fixed | `wrapper_richcompare`: the same descriptor, by owner and name |
| RL-343 | Found on RL-338 | A `re.sub` callback could resize the bytearray being scanned | Confirmed (`a6309a4`, mine): `b'clearedcleared'`, CPython `b'BufferErrorBufferError'` with the clear refused | Fixed | `_subx` holds the export until it ends, also when the callback raises |
| RL-344 | Found on RL-340 | The same overridable look-ups elsewhere: `__getnewargs_ex__`'s dict, `stat_result`'s dict, `_sre.compile`'s `groupindex` and `indexgroup` | Confirmed on `1dab41b`, each against CPython: `__newobj__` for `__newobj_ex__`, `st_atime` 7 for 1.5, IndexError for a group that exists | Fixed | `dict.__len__`, `dict.get`, `tuple.__len__` and so on, as the C does. The same change for `__slotnames__` and the template's list is not reachable yet: subclassing `list` stops by name |
| RL-345 | Found on RL-342 | `p.match == p.prefixmatch` compared unequal: one C function under two names | Confirmed (`a6309a4`, mine): False, CPython True | Fixed | `match = prefixmatch` in `Pattern` and `SRE_Scanner` |
| RL-346 | Found on RL-335 | `__sizeof__` returning `2 ** 70` gave that number; `-(2 ** 70)` raised ValueError. CPython raises OverflowError for both | Confirmed (`1dab41b`, mine) | Fixed | `PyLong_AsSsize_t`'s check before the sign. The pre-header in the value differs from CPython (16 for 32 on a class with a dict) and is not a finding: `sys.getsizeof` values are an implementation detail (dialect spec, section 2's table) |

## Open for discussion

**RL-321 `hash()` beyond the immediates: decided 2026-11-05.** The author accepted 63-bit hashes "as long as it's deterministic and functions as hash in general"; the second half was not true yet and now is (RL-321's row, D-22). Ended the same day: the big-int port lets `hash()` return any int, so a hash is CPython's own and D-22 is gone (`docs/DECISIONS.md`).

**`__spec__.cached` and `sys.implementation.cache_tag`: decided 2026-11-05.** None, as recommended, with D-16 extended: a compiled program has no bytecode cache and says so. `sys.implementation` itself is still refused by name; it comes with `sys.version_info` in the start-up work, with `cache_tag = None`. Test `test_no_bytecode_cache_d_16`.

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

**D-12 When a frame enters a traceback (RL-221, RL-222).** Decided 2026-11-03 by the author, as
recommended: part 1 now (done, with RL-223 to RL-227 found on the way), part 2 with step 3c. The emitter's
decision-5 guard records a frame when an exception leaves the function, and moves the locals
into the entry. CPython records it when the exception is detected in the frame (`PyTraceBack_Here`
at the `error:` label: a `raise X`, or an instruction or call that failed), with that
instruction's line; the frame's own re-raises add nothing (`RERAISE` at the end of a `finally`
or an unmatched `except`, and a bare `raise`, go to `exception_unwind`). So `raise e` lists the
frame twice, and a bare `raise` in `g`, called from `f`'s handler, lists `f` twice (the call,
then the original line) and `g` not at all (measured). The entry holds the frame object, and a
frame that returns or unwinds while its object is referenced moves its locals into it.

Recommendation (revised the same day; the first text recorded at every raise and in the
caller from the guard, which needed a frame stack on every call and made entries for the
exceptions the runtime raises and catches inside itself):
1. RL-221 now, with no lifetime change. The first place in the frame that sees an exception
   arrive (its own `catch` for an `except` or `finally`, or the guard if it has none) records
   `(code, frame.line)`, before any handler code runs; a thread-local mark beside `raising()`
   says the frame has recorded it, the frame's own re-raises keep the mark, leaving a frame
   clears it (so the caller records the call line), and `raise X` records at its own line. The
   guard of a frame the exception leaves moves the locals into that frame's entry, as today.
   Nothing changes on a path without an exception.
2. RL-222 with step 3c. The entry holds a small frame object the guard makes on first need;
   at exit the guard moves the locals into it only if something else still holds it. This
   delays release, it allocates nothing lasting: an exception caught and finished in the frame
   (`except E as e:` unbinds `e`) frees the object while the function runs. But an exception
   stored in a local of its own frame (`err = e`) makes a cycle, frame, `err`, exception,
   traceback, frame, that CPython frees only in its collector (measured with `gc.disable()`:
   the locals die at `gc.collect()`), and the runtime has no collector before 3c: such a frame
   would leak. Until 3c, RL-222 stays a recorded divergence (those locals die at the return,
   earlier than CPython). Model first (`refmodel/objects.py`), with a case under
   `conformance/cases` for each part.

## How to add a review

Put the file in this directory as `YYYY-MM-DD-<reviewer>-<nn>-<topic>.md`, then add a row to
*Reviews received*. Number its findings on from the last ID (`RL-347` next), reproduce each one,
and record the verdict and evidence. Reference the IDs in commit messages.
