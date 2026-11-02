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
  compiled and `_sre` ported, `unicodedata` with tables generated from the UCD (case C-7-15),
  the copy protocol (case C-3-20), `float` with CPython's `repr`, the L2
  grammar with declared/proven/representation kept apart. Write `bella-lint` as an `ast`
  walker over `docs/deviations.toml` and the tier table (`tools/score_candidate.py` is its
  seed).
* Decided 2026-11-01: each increment is the closure of its target programs, and phase 1 is the
  easy three, one stage each with its own gate (review log D-7, D-10): 1a.1 `cli_easy_slugs`
  (111 manifest modules, 52,106 compiled source lines), 1a.2 `service_easy_tokens` (+24,
  7,356), 1a.3 `data_easy_sales` (+14, 11,757); 1c is the other 31. `cli_easy_slugs` already
  reaches `enum` (`re`'s flags), and `service_easy_tokens` `typing` (itsdangerous), so task 5's
  staging prototype comes before the first path is done. `make targets-closure` computes the
  stages from `targets.toml` (`targets/closure-summary.json`, checked in CI). The tricky three
  follow phase 1; their recordings stay oracles.
* Measured 2026-11-02 (review log D-10; `docs/measurements.md`, `tools/scope.py`,
  `targets/scope/*.json`): `cli_easy_slugs`'s closure is 73 modules, 3,607 code objects and
  35,360 lines. Its recorded run executes 253 code objects (7 %) and 6,816 lines (19 %); with
  `--help`, a bad argument and other options, 403 and 8,650 (11 %, 24 %). The other two easy
  targets execute 6 % and 5 % of their code objects. Of the 379 executed units, 193 lower to L1
  today. The census of what L1 lacks, by executed units: classes 116, imports 68, parameter
  kinds 33, zero-argument `super()` 15, generator expressions 9, several targets 9, set
  displays 9, bytes 7, lambdas 6. The whole closure adds `match`, starred targets, dict
  unpacking, 94 generator functions and 40 `async def`. Found on the way: `_collections_abc`
  runs `async def` and `sys._getframe()` at import, and the frontend silently drops
  annotations and PEP 695 type parameters.
* Decided 2026-11-02 (P-1, P-2; spec v0.11 section 7):
  * P-1: the whole closure is compiled. A statement the pipeline cannot lower compiles to a
    refusal that names the construct and line (exit 70, `bella: refused:`). The build writes the
    inventory of refused statements, and the gate requires the target to reach none of them.
  * P-2: `_collections_abc` is a shim that takes its four probed types from `_types` (C-7-18).
* Recorded with P-1, for step B: the refusal node keeps the names its statement binds, so
  scoping is unchanged. Desugaring passes leave what they cannot lower in place, so that
  `to-l1` can refuse it, instead of failing the module. An `async def` is defined, not refused;
  running a coroutine is \[P2+\].
* The plan, in the order the census gives. Constructs come in as desugaring passes over the
  AST onto a small L1 core (author, 2026-11-02). Each pass has a `PassSpec` and is tested
  against CPython on observable behaviour, not on bytecode identity. The core grows only where
  a function or runtime object needs it, and `eval1` lends CPython's objects to the oracle only;
  the C++ runtime is Bella's own. Each step starts with conformance cases recorded on the pin.
  * A1 and A2, done 2026-11-02 (C-3-25, C-3-26, `pipeline/tests/test_l1_functions.py`; the
    cases also need A3 and A4 to run under `eval1`):
    * The core gains parameter kinds, the general call (`*` and `**` in place), lambdas, and
      `__annotate__` made with the function (PEP 649, in CPython's key order, lazy, PEP 563
      strings ready). Docstrings are cleaned as `_PyCompile_CleanDoc` cleans them.
    * `eval1` makes real function objects and binds arguments as `initialize_locals` does, with
      CPython's messages. `**` merges as 3.15.2's `_PyDict_MergeUniq`, read from its source.
    * Decorators stay a pass, and the definition applies them before its single store.
    * Desugarings call intrinsics, which a program binding `type`, `iter` or `format` cannot
      change (until now, a parameter named `type` broke `with`).
    * The oracle in `both()` no longer inherits the test module's `from __future__ import
      annotations`.
    * PEP 695 type parameters are refused, not dropped. `pipeline/l1/run.py` runs a program
      under `eval1`, and serves as the harness's runner.
  * A3 classes, done 2026-11-02 (C-3-27, `pipeline/tests/test_l1_classes.py`):
    * A class statement is lowered as CPython's compiler lowers it, to a single store of
      `build_class(<body>, name, *bases, **keywords)` with the decorators applied.
      `runtime/prelude/build_class.py` is CPython 3.15.2's `__build_class__` in Python, read
      from the pinned source. It covers metaclass resolution and conflict, `__prepare__` and its
      mapping check, `__mro_entries__` and `__orig_bases__`, and the `__class__`-cell checks.
      The prelude is compiled like any module; `eval1` runs it.
    * The core gains one node, the class-body function. Its names go through the namespace
      mapping, and its body is invisible to nested scopes except through the `__class__` cell.
    * Two passes do the rest:
      * `desugar-class-body` records qualnames and makes the implicit stores explicit:
        `__module__`, `__qualname__`, `__firstlineno__`, `__doc__`, `__static_attributes__`,
        and `__classdictcell__`, which 3.15 stores for any body with a `def`. It also makes
        zero-argument `super()` an explicit intrinsic call.
      * `desugar-private-names` mangles as `_Py_Mangle` does.
    * `eval1` makes its calls through a function whose globals are the program module's, so
      that `type.__new__`'s `__module__` comes from the program. Frame-walking calls
      (`sys._getframe`, `sys._getframemodulename`) are for step B.
    * `wf1` now binds names that nested scopes declare `global`.
    * Bytes, complex and Ellipsis constants are lowered.
    * Executed units of `cli_easy_slugs` that lower to L1: 300 of 375, up from 193 of 379.
    * Known edges, each a RuntimeError or AttributeError where CPython raises another kind:
      `super()` whose first argument was deleted, and `super` called through another name.
  * A4 imports, done 2026-11-02 (`pipeline/tests/test_l1_imports.py`; C-8-01 and C-8-04 to
    C-8-07 pass under `eval1`):
    * `desugar-imports` lowers every form as 3.15.2's codegen compiles it: `import_name`,
      `import_from` and `import_star` intrinsics with ordinary stores, and a fromlist that stays
      unmangled. Each import gets the mode codegen gives it: lazy, eager (in a function or class,
      in `try`/`except`/`finally`, or for `import *`), or default, which `__lazy_modules__`
      can make lazy at runtime. `lazy` outside module scope and `import *` in a function are
      SyntaxErrors. `__future__` features are read from the original tree, with CPython's
      placement rule.
    * `eval1` calls `__import__` and `__lazy_import__` as `_PyEval_LazyImportName` does; the
      latter from a frame whose globals are its locals, as it requires. `IMPORT_FROM` and
      `import *` run as CPython's own code, on the object handed over, and loads resolve lazy
      objects.
    * `pipeline/l1/modules.py` lets CPython's import machinery decide, with a meta-path finder
      that hands `eval1` the modules to execute: the program's own modules, and in closure
      mode the lock's compiled modules and shims, all lowered first (P-1).
    * `pipeline/l1/run.py` sets up `__main__`, `sys.argv` and `sys.path[0]` as `python
      program.py` does.
    * No code of the frontend or `eval1` imports while a program runs, so a program's
      `__import__` hook sees only the program's imports. One did: the hook recursed into
      `eval1`'s own late import.
    * `make eval1-corpus` (in `make check` and CI) runs the corpus under `eval1`: 43 of 73
      cases pass, and none of `conformance/eval1-baseline.txt` may regress. `wf1` accepts
      what a star import may bind until the compiler knows modules' exports statically.
    * In closure mode, 25 of `cli_easy_slugs`'s 72 closure modules lower whole. The rest wait
      on A5 (generator expressions, several targets, `yield`, sets, comprehensions, starred
      forms) and A6 (a `type` alias). `match`, and an `async def` in `_collections_abc`'s class
      bodies, wait on step B's refusals.
  * A5 the remaining forms, done 2026-11-02 (C-3-28, C-3-29, `pipeline/tests/test_l1_forms.py`):
    * Passes: several targets, stored left to right, with the temporary deleted afterwards.
      Every comprehension kind (list, set, dict with the key before the value, generator
      expressions as generators named `<genexpr>`), walrus targets binding in the containing
      scope (PEP 572; they were rejected before), and comprehensions in lambdas inlined into
      the lambda.
    * Core:
      * Starred targets, with CPython's unpacking, which reads an iterator only one item past
        what it needs (`eval1` used to read all of it).
      * Starred, set and dict-unpacking displays, built as codegen builds them (items first
        unless starred or more than 30; dicts in sub-dicts of 15 pairs).
      * Bytes, complex and Ellipsis constants; `yield` and `yield from`.
      * Function kinds: generator, coroutine, async generator.
    * Generators in `eval1`: the body runs on host generators, so the objects are real
      generators. A `StopIteration` is carried through the inner frames, so that PEP 479 acts
      only at the generator's boundary, as in CPython.
    * `async def` defines its function; the coroutine it makes refuses when run (P-1).
    * Refusals are uncatchable (`L.Refused`): no except clause catches them and no finally
      runs. That covers `eval1`'s own runtime gaps, which raised a catchable
      `NotImplementedError` before, and modules that do not lower.
    * `try` runs `finally` outside any handler for `return`, `break` and `continue`, and clears
      an except clause's name as codegen does. Except clauses match by the MRO.
    * `raise` evaluates the exception and its cause before instantiating either.
    * `make eval1-corpus`: 53 of 75. Of `cli_easy_slugs`'s 72 closure modules, 67 lower. Left:
      `match` (`dataclasses`, `traceback`, the `annotationlib` shim) and PEP 695 (`typing`,
      `_colorize`).
    * Found: the stdlib binds module globals by computed name from other modules (`re`'s flags,
      through `enum.global_enum`). The spec's compile-time NameError would refuse `re`. Proposal
      P-3 is for the author; `wf1` applies it provisionally (`strict=False` for library modules).
  * A5b `match` (C-3-17), as a desugaring pass onto intrinsics for the sequence, mapping and
    class patterns.
  * A6 the rest of the annotations: classes and modules (PEP 649, with `__classdict__`), PEP
    695 aliases and type parameters, and the S-1 second entry point.
  * B `eval1` runs `cli_easy_slugs` end to end: the closure lowered as P-1 decides, the staged
    texts from the staging artefact, and refusals as in staging. This is the gate's second leg
    (`make targets-check TARGET_RUNNER=...`).
  * C the C++ leg: task 3's header, L2, and the runtime list above.
* Decided 2026-11-01: `cli_easy_slugs` no longer uses `unicodedata` (it kept the lowered
  requirements when `unicodedata` became \[P1\] the same day, review log D-8); licence questions are registered in `docs/licences.md` and settled when worth it, so zlib's
  licence and the source of the hash primitives (items 4 and 5 of `docs/targets.md` section 5)
  do not block the work.
* After phase 1, with the tricky targets: items 1 to 3 of `docs/targets.md` section 5 (function
  metadata at runtime, dead excluded calls, manifest growth for pycodestyle) and stateful
  multiple inheritance with built-in bases (tomlkit). Item 6 is done (`[dynamic]`, review log
  RL-56).
* Decided after the target reviews (review log D-7 to D-11): the tricky three follow phase 1;
  `unicodedata` is \[P1\] (spec v0.8, for later revision); `re` runs on a port of `_sre`, its
  licence entry L-08; 1a is staged by target; the copy protocol is \[P1\] and `pickle` stays
  \[P2+\].
* The target oracle (`make targets-check`): bytes, an authoritative recording on the pin, two
  hash seeds and the phase-1 configuration per target; `service_easy_tokens` records whole
  tokens and verifies one CPython signed (review log RL-71 to RL-86).
* Done when (the gate of 1a.1): `cli_easy_slugs` prints the recorded output under CPython 3.15.2, `eval1` and the
  compiled binary (`make targets-check TARGET_RUNNER=...` passes for it), and the generated C++
  is committed under `pipeline/examples/out/`.

## 5. ~~Staging prototype~~ Done 2026-11-01 (`docs/staging.md`; S-1 to S-5 wait on the author)

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
* Done 2026-11-01. Staged texts, keyed by call site and text, with probes for literal
  `namedtuple` calls; intrinsics compared and rejected. C-8-08, C-8-09, C-3-21 and every other
  \[P1\] case, and the three phase-1 targets, print CPython's output under the replay model
  (`make staging-check`). `eval1` cannot run a class, so the replay runs the staged code as
  bytecode compiled at build time in its place. D-5's shim and tables are in
  `runtime/shims/annotationlib.py` and `pipeline/staging/annotations.py`. What remains moves
  to task 4: compile the staged texts through L1 to C++; generate each `__annotate__` and, beside
  it, the second entry point, which needs the L2 grammar to express name loads through a given
  mapping (decision S-1; prototype `pipeline/staging/annotations.py`); give compiled functions the
  attributes the shim reads (`__globals__`, `__builtins__`, `__closure__`, `__defaults__`); provide
  the shim's `_bella` hooks and the refusal in the runtime; write the `bella-lint` warnings for
  `@dataclass` and `make_dataclass` inside functions (S-3). Open: the layout half of staging (field
  sets, MROs taken as facts), which the prototype does not use, under spec section 8's input rule.
  The other phase-1 shims (`threading`, `socket`, `subprocess`, `asyncio`, `_thread`, `codeop`) are
  still to be written.
* Revised 2026-11-01 after the reviews astra-low-05 and gemini-4-argon-high-04 (review log RL-88
  to RL-112) and decisions S-1 to S-5.

## 6. Report

* Write `docs/gate0-report.md`: what the closure found, which clauses pass, which the model
  changed in the design, what the toolchain probes say about GCC 16 (`make probes`), and the
  measured compile time of the slice. That document is review round four's input.

## After Gate 0

* Consolidate the documents (review log D-2): rewrite design sections 3-10 around the final
  decisions, keep sections 13-15 as history, and let `docs/reviews/review-log.md` carry review
  history; make each `PassSpec` status name its evidence, so that "tested" points at the tests.

## Later

* Revisit the staging mechanism (decision S-5, 2026-11-01): the author's idea of using the GCC
  compiler within the program, so that a text the dry run did not see can still be compiled.
  GCC's own licence and libgccjit's (GPL; *to verify*) would need a licence register entry.
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
