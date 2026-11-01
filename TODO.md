# TODO — Gate 0, first increment

The next gate is the one the reviewer set in round two and refined in round three: executable
artefacts, not prose. Each task below says what exists today, what is left, and what "done"
means. Order matters: 1 constrains everything after it; 4 is where the next review happens.

## 1. Compute the real phase-1 dependency closure on CPython 3.15.2

* Today: `tools/closure.py` computes the closure (dynamic + static; dead, optional, lazy,
  guarded and eager edges with platform guards evaluated from `[platform]`, review log D-3;
  per-API scoping through `[lazy_unsupported]`, optional imports through `[omissions]`, which
  may hold nothing else); `codeop` is a shim for `traceback` (D-4); `manifest.toml` was last
  closed on CPython **3.13.18** (161 modules), which is not the reference.
* To do: run `uv run make closure` (or in the image), reconcile `manifest.toml` until it is
  closed on 3.15.2, commit `closure.lock.json`, and change the "LAST RECONCILED" line. On
  2026-11-01, after D-3 and D-4, it reports 25 open items over 172 modules, all new in 3.15:
  `annotationlib`, `_py_warnings`, `compression.zstd` (and `_zstd`), `math.integer` (and
  `_math_integer`), `pathlib._os`, `_hmac`, `fcntl`, `_missing_stdlib_info`, `_types`,
  `_ast_unparse`, and lazy imports in `pathlib` (`urllib.request`, `urllib.error`) and
  `traceback` (`importlib.resources`).
  Teach the tool PEP 810 first: a module-level `lazy import` (`ast.Import.is_lazy`) is a
  first-use edge, not an eager one; today it is followed as eager, which is sound but
  over-approximates. Eleven phase-1 modules use it (`collections`, `contextlib`,
  `dataclasses`, `typing`, `traceback`, `pathlib`, `argparse`, `inspect`, `difflib`,
  `tokenize`, `_colorize`), so lazy-import semantics are phase-1 runtime work.
  `[lazy_unsupported]` refuses whole functions, on every path (author's decision 2026-11-01,
  spec section 7): `Logger.__reduce__` stays there, and `copy.copy(logger)` is refused.
  Review the six `dynamic_unknown` import sites the lock lists (`encodings`, `inspect`,
  `traceback`, `unittest.loader/main`, `warnings`) and decide: registry entry, adaptation, or
  per-API scope.
* Done when: `make closure` exits 0 on 3.15.2 with `authoritative: true` in the lock, and every
  adaptation named in the manifest has an owner note in `docs/dialect-spec.md` section 7.

## 2. Grow the conformance corpus on 3.15.2

* Today: 28 cases + 1 excluded-construct case under `conformance/cases`, from review findings
  and from CPython 3.15 changes (C-9-07, C-3-09..12), recorded authoritatively on 3.15.2
  (2026-11-01); `make verify` reproduces them, D-08 masking is opt-in per case (`# mask:`).
* To do: cases for the 3.15 additions the phase-1 library depends on or the dialect must
  decide: PEP 810 lazy imports (reification at first use, import errors at first use,
  `__lazy_modules__`, `sys.set_lazy_imports` rejected by E-04), PEP 798 unpacking in
  comprehensions (\[P2+\]: a rejection case),
  `frozendict` (PEP 814), `sentinel` (PEP 661); add the cases the reviews asked for that are not yet
  here — the seeding-compatibility clause for D-14 (`PYTHONHASHSEED` fixed, compare
  `hash("x")` across runs), `__class__` assignment with CPython's layout rule, `__getattribute__`
  override cost tier, generator `close()`/`throw()`, `except*`, `match`, chained-comparison
  short-circuit with rich comparisons, dict mutation-during-iteration edge (size change only).
  Port the first 100 functions from CPython's `test_descr`, `test_int`, `test_dict`,
  `test_generators` as clauses (PSF-licensed; test-only, never shipped).
* Done when: every [P1] clause in the spec has at least one case, and `make verify` passes on
  the pin.

## 3. Finish the reference object model and write the real header from it

* Today: `refmodel/objects.py` models promoted fields, dict exposure/replacement/sharing with
  insertion order, descriptors by Python's rules incl. descriptor-class mutation, `__getattr__`,
  class versions from one global counter with subclass propagation (review log D-1),
  runtime-created classes that die (the oracle's `recreate_class`), inline caches keyed by
  version with validity predicates, and checks
  every cached read against the generic path; `refmodel.selftest` and the Hypothesis state
  machine agree with CPython on tens of thousands of random operations.
* To do, in the model first (with a conformance case each): `__setattr__`/`__delattr__`/
  `__getattribute__` overrides; `__class__` assignment; dict-mode (runtime-created) classes
  with shapes; setattr caching; `MAY_RECEIVE_COMPUTED_WRITES` as a class fact and the
  `__getattr__` shortcut it licenses; weak references; object lifetimes, so that `found` is
  really borrowed (review log RL-20); oracle operations for the other 2026-11-01 scenarios
  (RL-22: a raising `__get__`, a memoising `__getattr__`). Before the header, make
  lifetimes explicit (review log D-2, RL-20, RL-49): retain and release points in the L2
  grammar, finaliser traces in `eval1`, and lifetimes in the model. Then write `runtime/include/bella/object.hpp`
  from the model (start from `docs/drafts/object.hpp.draft` and the two findings in
  `docs/DECISIONS.md`), single-threaded first: plain counters, no atomics, no collector.
* Done when: the C++ object model passes the same stateful test through a thin Python
  binding, and C-3-01..12 pass under the compiled runner.

## 4. One complete compilation path on the three target programs

* Scope (review log D-2, decided 2026-11-01): phase 1 is delivered as 1a (core language and
  the data-structure modules the target programs need), 1b (`enum`, `dataclasses`,
  `typing`) and 1c (I/O, `re`, `json`, `logging`, `unittest` and the rest), each closed by a
  gate on its slice of the manifest (design section 11). This task is 1a's first path. The toy emitter now refuses, rather than invents, what
  it cannot represent: possibly unassigned reads, None values, calls before the `def`.
* Today: `make slice` runs `pipeline/examples/*.py` through parse → L1 → `eval1` and through
  the toy C++ emitter; 3/3 integer programs agree with CPython and `fact_big.py` is XFAIL on
  the missing BigInt. The pass manager orders the frontend passes by facts and refuses
  incomplete `PassSpec` records.
* To do: pick the three target programs of phase 0 (one of each shape: a CLI tool, a data
  script, a service handler), run `bella-lint` on them for the tier profile (the linter does
  not exist yet: write it as an `ast` walker over `docs/deviations.toml` and the tier table),
  and grow the slice until the smallest of the three runs end to end: BigInt in `int.hpp`
  (Karatsuba above 64 limbs, Knuth D; or libtommath), `str`, `list`, `dict`, exceptions as
  C++ exceptions, functions as objects, the L2 grammar with declared/proven/representation
  kept apart.
* Done when: the smallest target program prints the same trace under CPython 3.15.2, `eval1`
  and the compiled binary, and the generated C++ is committed under `pipeline/examples/out/`;
  the manifest roots are split into the 1a, 1b and 1c slices, with the closure per slice.

## 5. Staging prototype (gates phase 1b)

* Why: review log D-2 and RL-50. `dataclasses`, `namedtuple`, `enum` and `typing` build code
  with `exec` at definition time; spec section 8 stages it, but the contract between the
  staged result and the runtime is unproven.
* To do: prototype one `@dataclass` and one `namedtuple` whose definitions have observable
  effects (a default factory that counts calls, a field order printed at definition, an
  `__init_subclass__` hook), with a conformance case each first. Try both mechanisms the
  review names: stage-time `exec` keyed by call site and source hash, and compiler intrinsics
  for the known users. Record the choice in `docs/DECISIONS.md`.
* Done when: both programs print CPython's trace under the compiled runner (or under `eval1`
  plus the staged artefact, if the runner is not there yet), and 1b has a mechanism.

## 6. Report

* Write `docs/gate0-report.md`: what the closure found, which clauses pass, which the model
  changed in the design, what the toolchain probes say about GCC 16 (`make probes`), and the
  measured compile time of the slice. That document is review round four's input.

## After Gate 0

* Consolidate the documents (review log D-2): rewrite design sections 3-10 around the final
  decisions, keep sections 13-15 as history, and let `docs/reviews/review-log.md` carry review
  history; make each `PassSpec` status name its evidence, so that "tested" points at the tests.

## Housekeeping

* ~~`uv lock` and commit `uv.lock`; pin the `gcc:16.x` image tag after `docker pull`.~~ Done
  2026-11-01: `uv.lock`, uv 0.13.6, `gcc:16.2.0` by digest (`docs/DECISIONS.md`, Pins).
* Rename the author line in the Markdown exports if the docs are published.
* The `.github/workflows/ci.yml` builds the image and runs `make check`; turn it on once the
  closure is reconciled (task 1). The image builds and every other target in `make check`
  passes in it (2026-11-01). Until then the closure step is `continue-on-error`.
