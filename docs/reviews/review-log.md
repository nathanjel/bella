# Review log

Every finding from an external review, its verdict, and what happened to it. Reviews are input,
not authority: each finding is reproduced against the pinned CPython (or checked in the code)
before it is accepted, and every reviewer's findings are weighed alike. A confirmed defect that
can be fixed without changing the design is fixed with a failing test or conformance case first;
anything that would change the design, the specification or the build plan goes to
[Open for discussion](#open-for-discussion) with a recommendation.

**Status on 2026-11-01:** 51 findings from three reviews: 34 fixed (most in commit `0d92b51`,
RL-37 with decision D-3, RL-23 with D-1, RL-38 with Gate 0 task 1), 7 already done before or
because of the review, 4 planned (D-2, accepted by the author), 2 deferred, 3 refuted and 1
checked with no issue. Nothing is open for discussion: the author decided D-1 to D-4 on
2026-11-01.

## Reviews received

| Date | Reviewer | File | Scope | Ran against |
| --- | --- | --- | --- | --- |
| 2026-11-01 | astra-low (A1) | [2026-11-01-astra-low-01-design-codebase-review.md](2026-11-01-astra-low-01-design-codebase-review.md) | design and Gate-0 code | CPython 3.14.8, GCC 16.2.1 |
| 2026-11-01 | astra-low (A2) | [2026-11-01-astra-low-02-python-version-review.md](2026-11-01-astra-low-02-python-version-review.md) | choice of reference Python | release notes; Bella not run on 3.15.2 |
| 2026-11-01 | gemini-4-argon-high (G) | [2026-11-01-01-gemini-4-argon-high-scaffold-architecture-review.md](2026-11-01-01-gemini-4-argon-high-scaffold-architecture-review.md) | design and Gate-0 code | CPython 3.14.8, GCC 16.2.1 |
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
| RL-50 | A1, G 1.2.2 | The staging-to-runtime contract for `exec`-built code is unresolved | Agreed by both | Planned: D-2 | |
| RL-51 | A1 | Consolidate the authoritative documents; present PassSpec as obligation tracking | Agreed | Planned: D-2 | |

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
as recommended (design section 11, `TODO.md`, `docs/DECISIONS.md`). Both code reviewers ask for
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

## How to add a review

Put the file in this directory as `YYYY-MM-DD-<reviewer>-<nn>-<topic>.md`, then add a row to
*Reviews received*. Number its findings on from the last ID (`RL-52` next), reproduce each one,
and record the verdict and evidence. Reference the IDs in commit messages.
