# TODO — Gate 0, first increment

The next gate is the one the reviewer set in round two and refined in round three: executable
artefacts, not prose. Each task below says what exists today, what is left, and what "done"
means. Order matters: 1 constrains everything after it; 4 is where the next review happens.

## 1. ~~Compute the real phase-1 dependency closure on CPython 3.15.2~~ Done 2026-11-01

* `make closure` exits 0 on 3.15.2 with `authoritative: true`: 175 modules (112 compiled, 37
  mapped, 19 core, 7 shims; after the closure reviews, review log RL-52 to RL-70). `closure.lock.json` is committed, and CI requires it to be what the
  pinned image computes. Every adaptation in the manifest has its note in spec section 7 (v0.6).
  Decisions: `docs/DECISIONS.md`; mechanism: design section 10.4.
* Runtime work this leaves for the phase-1 runtime: the 16 `first-use` bindings (PEP 810), the
  functions listed under `unsupported_functions` in the lock (each exists as an ordinary object,
  since `shutil` sets `supports_root_dir` on two of them at import, and raises the
  milestone-naming error when called), the `annotationlib` shim (review log D-5: it serves the
  annotation formats through the compiler-generated `__annotate__`), and the codec search over
  the ten phase-1 codecs.

## 2. Grow the conformance corpus on 3.15.2

* Today (2026-11-01): 57 cases (53 \[P1\], 4 \[P2+\]) and 2 excluded-construct cases, recorded
  on 3.15.2; `make verify` reproduces 58 expectations. Every \[P1\] row of spec sections 3 and
  7 has at least one case. The harness checks \[P2+\] cases (the runner must refuse them with
  `[P2+]`) and deviation cases (D-20, simulated on CPython), and `make lint` type-checks the
  corpus as dialect programs. Added in this increment: PEP 810 lazy imports (C-8-05..07,
  X-4-02), PEP 798 (C-3-14, \[P2+\]), `frozendict` and `sentinel` (C-6-05, C-6-06), D-14 seeding
  (C-6-07), generators, `except*`, `match` (C-3-15..17), chained rich comparisons (C-2-02), dict
  mutation (C-6-08: only a size change raises; otherwise iteration follows CPython's entry
  table), `__class__` and `__getattribute__` (C-3-18, C-3-19, \[P2+\]), D-20 (C-7-03), the
  archive formats (C-7-04, \[P2+\]), and one or two cases per stdlib row (C-7-05..14).
* To do: a row is not a sentence. Cases for the normative sentences each row still leaves open,
  starting with section 6 (`str`, `bytes`, `float` formatting and parsing, `complex`, `range`,
  `list`/`tuple` operations, `set` order beyond C-6-03), the data model (numeric protocol with
  `NotImplemented` and reflected operands, `__format__`, `__index__`), exception chaining
  (`__cause__`, `__context__`, `__suppress_context__`), `with`, closures and `nonlocal`,
  `__init_subclass__`, `__set_name__`, `super()`, t-strings (PEP 750). Then port the first 100
  functions from CPython's `test_descr`, `test_int`, `test_dict`, `test_generators` as clauses
  (PSF-licensed; test-only, never shipped).
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

## 4. One complete compilation path on the target programs

* Scope (review log D-2, decided 2026-11-01): phase 1 is delivered as 1a (core language and
  the data-structure modules the target programs need), 1b (`enum`, `dataclasses`,
  `typing`) and 1c (I/O, `re`, `json`, `logging`, `unittest` and the rest), each closed by a
  gate on its slice of the manifest (design section 11). This task is 1a's first path. The toy
  emitter refuses, rather than invents, what it cannot represent.
* Today: `make slice` runs `pipeline/examples/*.py` through parse → L1 → `eval1` and through
  the toy C++ emitter; 4 integer programs (Mandelbrot among them, `docs/measurements.md`) agree
  with CPython and `fact_big.py` is XFAIL on the missing BigInt. The target programs are chosen
  (author, 2026-11-01) and recorded: six under `targets/`, an easy and a tricky one per shape
  (`docs/targets.md` has the comparison and the recommendation), their libraries vendored at
  pinned commits, recorded on 3.15.2 and identical under two hash seeds and under the phase-1
  omissions (`make targets-check`, in CI). On 3.15.2 they stay inside the manifest except for
  pycodestyle (`optparse`, `configparser`).
* To do: take the easy three in the order `docs/targets.md` gives — `cli_easy_slugs`,
  `service_easy_tokens`, `data_easy_sales` — and grow the slice until the first runs end to
  end: BigInt in `int.hpp` (Karatsuba above 64 limbs, Knuth D; or libtommath), `str`, `list`,
  `dict`, exceptions as C++ exceptions, functions as objects, classes with promoted fields
  (argparse's `Namespace` is the first computed-write object), the `re` parser/compiler
  compiled and `_sre` ported, `float` with CPython's `repr`, the L2
  grammar with declared/proven/representation kept apart. Write `bella-lint` as an `ast`
  walker over `docs/deviations.toml` and the tier table (`tools/score_candidate.py` is its
  seed).
* Decided 2026-11-01: each increment is the closure of its target programs (1a: the easy
  three). The easy three already reach `enum` (`re`'s flags) and `typing` (itsdangerous), so
  task 5's staging prototype comes before the first path is done. `make targets-closure`
  computes them (`targets/closure-summary.json`, checked in CI): 1a is 149 manifest modules and
  71,219 compiled source lines, the tricky three add 6 modules, and 25 are reached by none.
  Five targets are closed; `cli_tricky_check` waits on the parked pycodestyle items.
* Decided 2026-11-01: `cli_easy_slugs` no longer uses `unicodedata`, which stays \[P2+\];
  licence questions are registered in `docs/licences.md` and settled when worth it, so zlib's
  licence and the source of the hash primitives (items 4 and 5 of `docs/targets.md` section 5)
  do not block the work.
* Decisions this needs from the author, before the tricky targets: items 1 to 3 of
  `docs/targets.md` section 5 (function metadata at runtime, dead excluded calls, manifest
  growth for pycodestyle). Item 6 is done (`[dynamic]`, review log RL-56).
* Open after the target reviews (review log D-7 to D-11): tomlkit's stateful multiple
  inheritance against 1b, `unicodedata` reached on non-ASCII paths of `re`, `traceback` and
  `urllib.parse`, the regex engine (PCRE2 in the spec, a `_sre` port in this plan), what is
  compiled for a target (the whole closure or what is reachable, and 1a staged by target), and
  the copy protocol against pickling.
* The target oracle (`make targets-check`): bytes, an authoritative recording on the pin, two
  hash seeds and the phase-1 configuration per target; `service_easy_tokens` records whole
  tokens and verifies one CPython signed (review log RL-71 to RL-86).
* Done when: `cli_easy_slugs` prints the recorded output under CPython 3.15.2, `eval1` and the
  compiled binary (`make targets-check TARGET_RUNNER=...` passes for it), and the generated C++
  is committed under `pipeline/examples/out/`.

## 5. Staging prototype (gates the first target path: `re` reaches `enum`, itsdangerous `typing`)

* Why: review log D-2 and RL-50. `dataclasses`, `namedtuple`, `enum` and `typing` build code
  with `exec` at definition time; spec section 8 stages it, but the contract between the
  staged result and the runtime is unproven.
* Implement review log D-5 here (decided 2026-11-01): a compiler-generated `__annotate__` that
  answers VALUE, FORWARDREF when every name resolves, and STRING, and the `annotationlib` shim over
  it, so that `@dataclass`, `NamedTuple`, `TypedDict` and `singledispatch` read annotations while
  the module runs (spec section 8). Case C-3-13 is the target.
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

## Later

* Settle the entries of the licence register, `docs/licences.md`, one by one when each becomes
  worth it (for example, when the component is about to be linked into an artefact).
* `hashlib.pbkdf2_hmac` (over the mapped HMAC) and `hashlib.scrypt` (libsodium) as an adaptation
  of `hashlib`, closing that part of deviation D-20 (review log D-6, option 2). When a target
  program needs either; then add a case, narrow D-20, and record it in `docs/DECISIONS.md`.

## Housekeeping

* ~~`uv lock` and commit `uv.lock`; pin the `gcc:16.x` image tag after `docker pull`.~~ Done
  2026-11-01: `uv.lock`, uv 0.13.6, `gcc:16.2.0` by digest (`docs/DECISIONS.md`, Pins).
* Rename the author line in the Markdown exports if the docs are published.
* ~~Turn the closure step on in `.github/workflows/ci.yml` once task 1 is done.~~ Done
  2026-11-01: both jobs run it without `continue-on-error`, and the pinned job also requires the
  committed `closure.lock.json` to match.
