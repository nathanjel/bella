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
  lifetimes explicit (review log D-2, RL-20, RL-49): release points in the L2 grammar
  (`docs/l2.md` v1), checked by `eval2` against CPython's finaliser traces, and lifetimes in
  the model. `eval1` keeps no finaliser traces (author, 2026-11-02: L1 says nothing about when
  an object dies, so `eval2` is the first level exact about lifetimes).
  * Done 2026-11-02: lifetimes in the model (`refmodel/objects.py`): counted objects and dicts,
    CPython's release orders (slots most-derived first, then instance attributes in the class's
    shared-keys order, a failed `del` included; split and ordinary dicts), class mutations that
    version before they release, `CacheEntry.found` borrowed and checked (RL-20). Case C-9-08;
    the oracle compares death logs after every operation (`drop`, tagged values, dying
    descriptors), in the self-test and the Hypothesis machine.
  * Done 2026-11-02: `runtime/include/bella/object.hpp`, written from the model, single-threaded
    (16-byte header, plain counts, classes disposed but not freed, standard containers for
    storage). `make object-test` (in `make check` and CI, also under ASan and UBSan) runs the
    model's random programs on the model, on CPython and on the header through a `ctypes`
    binding (`runtime/tests/object_binding.cpp`), comparing every outcome, death and attribute
    after every operation; the header's checking mode compares every cached read with the
    generic lookup. The first half of the done-when below holds; the second waits for the
    emitter (C-3-01..12 under the compiled runner).
  Then write `runtime/include/bella/object.hpp`
  from the model (start from `docs/drafts/object.hpp.draft` and the two findings in
  `docs/DECISIONS.md`), single-threaded first: plain counters, no atomics, no collector.
* Done when: the C++ object model passes the same stateful test through a thin Python
  binding, and C-3-01..12 pass under the compiled runner.

## 4. One complete compilation path on the target programs

* Scope (review log D-2, decided 2026-11-01; revised the same day by D-7 and D-10, below): phase
  1 was first cut as 1a (core language and the data-structure modules the target programs
  need), 1b (`enum`, `dataclasses`, `typing`) and 1c (I/O, `re`, `json`, `logging`, `unittest`
  and the rest), each closed by a gate on its slice of the manifest (design section 11). D-7
  removed 1b: phase 1 is the easy three, staged 1a.1 to 1a.3, and 1c is the rest of the manifest
  (`targets/closure-summary.json` lists it). This task is 1a's first path. The toy emitter
  refuses, rather than invents, what it cannot represent.
* Today: `make slice` runs `pipeline/examples/*.py` through parse → L1 → `eval1` and through
  the toy C++ emitter; 5 integer programs (Mandelbrot among them, `docs/measurements.md`) agree
  with CPython, `fact_big.py` since the big ints. The target programs are chosen
  (author, 2026-11-01) and recorded: six under `targets/`, an easy and a tricky one per shape
  (`docs/targets.md` has the comparison and the recommendation), their libraries vendored at
  pinned commits, recorded on 3.15.2 and identical under two hash seeds and under the phase-1
  omissions (`make targets-check`, in CI). On 3.15.2 they stay inside the manifest except for
  pycodestyle (`optparse`, `configparser`).
* To do: take the easy three in the order `docs/targets.md` gives — `cli_easy_slugs`,
  `service_easy_tokens`, `data_easy_sales` — and grow the slice until the first runs end to
  end: BigInt in `int.hpp` on a copy of SEL's `bn` (decided 2026-11-02), `str`, `list`,
  `dict`, exceptions as C++ exceptions, functions as objects, classes with promoted fields
  (argparse's `Namespace` is the first computed-write object), the `re` parser/compiler
  compiled and `_sre` ported, `unicodedata` with tables generated from the UCD (case C-7-15),
  the copy protocol (case C-3-20), `float` with CPython's `repr` (digits from libstdc++'s
  `<charconv>`, `make float-diff`; decided 2026-11-02), the L2 grammar (`docs/l2.md` v1). Write `bella-lint` as an `ast`
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
      through `enum.global_enum`). The spec's compile-time NameError would refuse `re`. Decided
      as P-3 (spec v0.12 section 8): library modules look such names up at runtime
      (`strict=False`), and the program's own modules keep the compile-time error.
  * A5b `match`, done 2026-11-02 (C-3-17, `pipeline/tests/test_l1_match.py`):
    * `desugar-match` lowers `match` as 3.15.2's codegen does, onto ordinary checks and
      `runtime/prelude/match.py` (`MATCH_SEQUENCE`, `MATCH_MAPPING`, `MATCH_KEYS`,
      `MATCH_CLASS` in Python). Captures are stored in codegen's order before the guard; an
      or-pattern commits to its first alternative; sequence items are unpacked, or taken by
      subscript with `len()` at each access when the star is a wildcard. The order of
      effects is tested against CPython, and so are codegen's compile-time pattern errors.
    * t-strings (PEP 750) lower to `Template` and `Interpolation`; `annotationlib` builds one
      at import.
    * Found: `eval1` passed an empty keyword dict to every call. A C type that refuses
      keywords (`Template`) tells the two apart; now a call with no keyword items passes none,
      as `CALL` does.
    * The closure: 70 of 72 modules lower; PEP 695 is left (`typing`, `_colorize`).
  * A6, done 2026-11-02 (`pipeline/tests/test_l1_annotations.py`; C-3-25, C-3-27 and C-3-28 now
    pass under `eval1`):
    * `desugar-annotations` lowers module and class annotations as 3.15.2 compiles them (PEP
      649).
      * A module's `__annotate__` is made first, and every module annotation is conditional on
        its statement having run (`__conditional_annotations__`).
      * A class's function is stored last, as `__annotate_func__`, and reads the class
        namespace first. So do methods' annotate functions (`LOAD_FROM_DICT_OR_GLOBALS`).
      * Non-simple targets' annotations are never evaluated, and `x: T` makes `x` local.
    * Found: the frontend never stored a module's docstring as `__doc__`; it does now.
    * `desugar-type-params` lowers PEP 695 into hidden generic scopes, as the bytecode does:
      decorators first, lazy bounds, constraints and defaults, `Generic[...]` after a class's
      bases, `__type_params__`, and lazy alias values. `eval1` lets CPython make the objects,
      from a text whose expressions call `eval1` thunks; the compiled runtime will have its
      own.
    * Found: `eval1` cached `_has_yield` by `id()` of nodes that could be freed, so a reused id
      gave a stale answer under pytest. The cache now keeps the node.
    * `make eval1-corpus`: 58 of 75. All 72 of `cli_easy_slugs`'s closure modules lower.
    * The S-1 second entry point (FORWARDREF and STRING through the `annotationlib` shim) is
      still to do.
  * B, done 2026-11-02: the easy three print their recorded output under `eval1`, each with its
    whole closure lowered to L1. `make targets-eval1` runs it, in `make check` and CI. That is
    the second leg of gates 1a.1, 1a.2 and 1a.3; the C++ leg remains.
    * Staged texts (`pipeline/l1/staged.py`): the staging dry runs' artefacts, as the replay
      takes them. Every text is lowered before the program starts, in the caller's
      `__future__` context and with the builtins' preprocessing. At runtime it is found by the
      replay's key, from a frame stack `eval1` now keeps. A miss, a `[refused]` function and an
      `[unsupported]` one refuse.
    * Closure mode runs CPython's start-up modules under `eval1` first, applies the phase-1
      omissions (D-20) as the replay does, and gives the host its modules back before printing
      a traceback.
    * Found:
      * A module whose annotations all stood in blocks had no conditional set.
      * Vendored packages were held to the program's strict name rule; they are library code
        under P-3.
    * Not needed by the targets, so still open: P-1's statement refusals (every closure module
      lowers whole), the frames that `sys._getframemodulename` and `logging`'s `findCaller`
      read (namedtuple's default module worked through the staged text), tracebacks with
      frames, and the S-1 second entry point.
    * Each run takes about 11 to 15 seconds: `eval1` interprets `argparse`, `re`'s parser,
      `enum` and `dataclasses` from L1.
  * Reviewed 2026-11-02 (astra-low-07, gemini-4-argon-high-06; review log RL-136 to RL-168,
    `pipeline/tests/test_review_2026_11_02.py`): 30 fixes, among them CPython's compile-time
    errors from the host compiler, the pass `desugar-function-annotations`, PEP 563's
    `__annotations__` dict, call construction (`CALL_FUNCTION_EX`'s lone `*x`, keyword runs),
    dict merges with stored hashes, generator frames and the strict name check without the
    `globals()` exemption. `make eval1-corpus`: 59 of 75. Left as refusals: a `yield` in a `for`
    target, and beside a starred or `**` argument.
  * C the C++ leg (go-ahead 2026-11-02, `docs/DECISIONS.md`), in this order:
    1. The L2 leg, all Python and testable at once: the grammar file, `wf2`, the printer and
       `eval2` with its hygiene (a `gc.get_referrers` checking mode, explicit unwinding, a
       generated `__del__` probe per kind of release point); then `resolve-names`, `to-anf`,
       `protocol-ops` and `lifetimes`, each checked as `eval1 == eval2` on the corpus and the
       easy three, and the lifetime cases as `eval2 == CPython`.
       * Done 2026-11-02 (`pipeline/l2/`, `docs/l2.md` section 7): the grammar, `wf2`, the printer,
         resolve-names (checked against CPython's code objects), `to-anf` with protocol-ops,
         `lifetimes`, and `eval2` as a translation to host functions with the explicit unwinding.
         `make eval2-corpus`: 63 of 76, every `eval1` case and the lifetime cases.
       * Done 2026-11-02: the easy three under eval2 with their whole closures (`make
         targets-eval2`, in `make check` and CI): every closure module lowered to L2 and compiled
         before the program starts, the staged texts replayed by the calling code's site.
       * Done 2026-11-02, closing the step: the checking mode (`audit=True`) and the generated
         probes (`pipeline/tests/test_l2_probes.py`: 31 kinds of release point, at module level
         and in a function, all equal to CPython and clean under the audit). They found the `with`
         desugaring keeping its manager alive until the frame ended (fixed in the frontend).
       * Reviewed 2026-11-02 (astra-low-08, gemini-4-argon-high-07; review log RL-169 to
         RL-187, `pipeline/tests/test_review_2026_11_02b.py`): 19 fixes, among them the header's
         borrowed hook (a use-after-free), slots at the first emitted use, the frontend's
         synthetic variables dying where CPython's stack values do, on every path, and helper
         frames out of tracebacks. **Open:** when a list, set or dict comprehension raises,
         CPython drops its iterator and then its partial result; `eval2` drops the result first,
         because the caller's operand holds the iterator while the helper unwinds. The emitter
         moves the iterator into the helper; `eval2` needs a fused call to do the same (RL-186).
    2. Lifetimes in the model and `object.hpp` from it (task 3); independent of 1.
    3. The runtime types and the emitter: task 3's done-when (C-3-01..12 under the compiled
       runner) first, then gate 1a.1. Decided 2026-11-02 (`docs/DECISIONS.md`): a C++ core and
       a Python prelude, in this order:
       * 3a the emitter from L2 and the runtime core: C-3-01..03, 05..11 and the slice examples
         compiled; a compiled-corpus baseline; the toy L1 emitter retires.
         * 3a.1 done 2026-11-02 (`docs/emitter.md`): `pipeline/backend/cpp.py`, the runtime core
           (`runtime.hpp`, `runtime/src/`), `print` in the prelude, `pipeline/build.py`; the
           slice examples and `pipeline/tests/test_compiled.py` match CPython compiled, `make
           compiled-corpus` 1 of 76 (classes next); the toy emitter is gone.
         * 3a.2 done 2026-11-02 (`docs/emitter.md` section 3): classes compiled. The prelude's
           `__build_class__`, `type.__new__` in CPython's order, descriptors everywhere,
           special-method dispatch with CPython's protocols, `property`, `staticmethod`,
           `classmethod` and the containers' `repr` in the prelude, `set` as CPython's table.
           C-3-05..11 pass compiled; `make compiled-corpus` 15 of 76 (43 of the rest import
           modules). Left for 3a.2: the exception classes into the prelude, `super()`,
           metaclasses.
         * Reviewed 2026-11-03 (astra-low-09, gemini-4-argon-high-08; review log RL-188 to
           RL-219, `pipeline/tests/test_review_2026_11_03.py`): 23 fixes, among them `finally`
           running twice, finalisers' exceptions escaping a destructor, crashes on wrong
           receivers and arities, and injective names; 9 more found by running the earlier
           rounds' programs compiled, among them names CPython has now refused by a recorded
           table instead of answered with NameError or AttributeError. The L2 release-point
           probes run compiled (`test_compiled_probes.py`). Later: the slot wrappers' own types
           (their repr and type are refused, RL-218).
         * 3a.3 done 2026-11-03 (`docs/emitter.md` section 3a): one dict type, `object.hpp`'s
           compact dict with the runtime's hash and `==`, so an instance's `__dict__` is a dict
           like any other; the split rules measured on 3.15.2 and modelled first; the dict's
           missing methods (`clear`, `copy`, `popitem`, `setdefault`, `update`, `fromkeys`) and
           live views. C-3-01..03 pass compiled, and C-9-08 with them: `make compiled-corpus`
           18 of 76. Found on the way and fixed: `keys()`, `values()`, `items()` returned lists,
           `str(KeyError(k))` was not `repr(k)`, a lookup whose `__eq__` changed the dict raised
           RuntimeError instead of starting again. Then every C++ builtin and method words a
           wrong argument count as CPython does for its calling convention, `f(*value)` compiles
           (`call_args_tuple`), and `list.index` takes start and stop. Then the operators on the
           built-in types: dict, set, range and slice equality were identity, `[0] * 3` and
           `{1} | {2}` raised TypeError; they are CPython's now, and an operator CPython handles
           that the runtime lacks is refused by the recorded table. Left (refused): the views'
           set operations, `str %` formatting, `type | type`;
           the constructors of `int`, `float` and `dict` (they fell into `object.__new__`,
           RL-220). Then D-12: a frame
           enters a traceback where the exception arrives, the prelude and inlined comprehensions
           have no frames, and the report prints the chain (RL-221, RL-223 to RL-227, C-3-30);
           lines inside a multi-line statement are the statement's (RL-225, open).
         * Reviewed 2026-11-03 (astra-low-10, gemini-4-argon-high-09; review log RL-228 to
           RL-255, `pipeline/tests/test_review_2026_11_03b.py`): 27 fixes, among them an
           exception's fields as BaseException's (not its `__dict__`, released in
           `BaseException_clear`'s order; modelled first as a built-in base's native fields,
           C-3-31), context and cause as `_PyErr_SetObject` and `do_raise` set them, every dict
           operation calling back into keys as CPython's (C-6-09), crashes and a hang in `list`
           methods whose `__eq__` changes the list, and `list`, `dict` and `set` hashable until
           now. Open: RL-254 (a member's type).
       * 3b generators (state machines) and compiled imports: C-3-04. First `super()` and
         metaclasses, which the standard library needs as soon as it imports (`abc`, `enum`).
         * `super()` done 2026-11-03 (`runtime/src/super.cpp`, case C-3-32,
           `pipeline/tests/test_compiled_super.py`): super objects as `Objects/typeobject.c` makes
           them, the zero-argument form through the frontend's intrinsic, eval1's scenarios
           compiled. Found on the way: `object.__setattr__` and `__delattr__` took the object
           among their arguments, so neither `super().__setattr__(k, v)` nor
           `object.__setattr__(o, k, v)` worked; a free variable's NameError had no `name`;
           deleting a C++ type's member was refused.
         * Metaclasses done 2026-11-03 (case C-3-33, `pipeline/tests/test_compiled_metaclasses.py`):
           `type` subclasses as bases, the winning metaclass computed in `type.__new__`, a
           metaclass's `__call__`, stores, `__getattr__` and special methods serving its classes,
           `isinstance`/`issubclass` as `Objects/abstract.c`, `__abstractmethods__`. Found on
           the way: assigning a class's `__module__` recursed without end, and its `__doc__` could
           not be set. Next: subclasses of `dict` and `int` (enum's `_EnumDict`, `IntFlag`), then
           compiled imports with `_abc` in C++ (the lock's core module; `_py_abc` needs weak
           references, 3c).
         * Subclasses of the built-in types (decided 2026-11-03, `docs/DECISIONS.md`: the object
           is the built-in's, with the subclass's attribute storage beside it). In order, each
           with its case: the model (a built-in base's data released after the instance dict);
           `object.hpp`'s attribute storage for objects that are not instances; `dict`
           subclasses (the `dict` constructor with them, RL-220's refusal; done 2026-11-03,
           case C-3-34, `pipeline/tests/test_compiled_builtin_subclasses.py`; found on the way:
           the prelude's dict repr asked a subclass's `__len__`, `list(x)` never asked a Python
           object for its length hint, `object.__setattr__` and friends knew instances only);
           `int` subclasses (the `int` constructor; done 2026-11-03, case C-3-35; found on the
           way: a str constant with a NUL was cut at it, `range()` and `chr()` refused objects
           with `__index__`, a subclass's reflected method did not come first for subclasses of
           built-ins); `str`, `tuple`, `list` as the targets reach them. Then `types.GenericAlias`
           (`dict[str, int]` as a base or a value: `__class_getitem__`, `__mro_entries__`).
         * Compiled imports (decided 2026-11-03, `docs/DECISIONS.md`; `docs/emitter.md` section 4a):
           * The program's own modules, done 2026-11-03 (case C-8-10, C-8-01 and C-8-04 compiled,
             `pipeline/tests/test_compiled_imports.py`): the build finds them
             (`pipeline/closed_world.py`) and compiles each as a unit; the import system is
             `runtime/src/imports.cpp` and `runtime/prelude/bootstrap.py` (`importlib._bootstrap`'s
             text). With them `globals()`, `dir()`, `sys.modules`, `sys.path`, `sys.exit`,
             `ImportError`'s fields, the module type, and the first `str` methods
             (`runtime/src/str.cpp`). Found on the way: a class's slot descriptors stood in its dict
             in the order declared, not sorted, in the model and the header (Hypothesis found it);
             an AttributeError leaving `getattr` had no `name` and `obj` unless the runtime raised
             it; `sys.exit` and an uncaught exception left the modules' globals unreleased.
           * Lazy imports (PEP 810), done 2026-11-04 (C-8-05 to C-8-07; tests in
             `test_compiled_imports.py`): `lazyimportobject.c` and `import.c`'s lazy half in
             `imports.cpp`, with pending submodules, `__lazy_import__`, `ImportCycleError` and
             the declaration on a resolution error. Found on the way: the first version of C-8-10
             was outside the dialect (E-04, E-06: replacing `__import__`, writing `sys.modules`);
             those paths moved to the runtime's tests, which the standard library needs.
           * The standard library's path, done 2026-11-04 (C-8-05; `types` runs compiled): the build
             compiles a program's whole reachable closure from the lock (P-1), every one of
             `cli_easy_slugs`'s 70-odd modules compiles, `BuiltinImporter` and `FrozenImporter` are
             ported, `_types` is native, and the names table covers the native modules. Found on
             the way: a `for ... else: raise` got an unreachable `return` that wf2 refused
             (`operator`, `ast`), a Python name spelled like a macro of the headers broke the C++
             (`ENOENT`), the harness lost a whole run to one case's timeout, and parallel builds
             could read each other's half-written source.
           * Reviewed 2026-11-04 (G10 and eight Sonnet reviewers; `docs/reviews/review-log.md`,
             RL-256 to RL-326; `pipeline/tests/test_review_2026_11_04.py`). Fixed among them:
             finalisers at exit reading their globals as None, `next()` of a program's iterator,
             `int`'s special methods, instance layout conflicts, a metaclass's `mro()`, `from pkg
             import *`, frozenset hashed by identity. Decided by the author 2026-11-05: hashes
             keep 63 bits (D-22, the `bn` port stays where it is planned) and `__spec__.cached`
             is None (D-16); `sys.implementation` comes with `sys.version_info`, `cache_tag` None.
           * `_abc` done (C-7-19, `runtime/src/abc.cpp`): the frozen `abc` runs compiled on it, with
             strong references until 3c (confirmed by the author 2026-11-04). With it, views of a
             class's `__dict__`, `type.__subclasses__`, `object.__subclasshook__`,
             `__isabstractmethod__`, a built-in function's `__module__` and `__qualname__`, and the
             types a class cannot derive from (`final:` in the names table). When `match` is
             compiled, read the bits `__abc_tpflags__` carries: inherited, and passed on by
             `register` (`_PyType_SetFlagsRecursive`).
           * Subscripting a class and `types.GenericAlias` done (C-3-36), and `dir()` of a class or
             an object. `types.UnionType` (`X | Y`) is refused until it is written.
           * Reviewed 2026-11-05 (A11, RL-327 to RL-333; `pipeline/tests/test_review_2026_11_05.py`).
             Fixed among them: no special method from `slots.cpp` bound through a subclass instance
             (`E(1).__add__(2)`), and a program's class named after a built-in read that built-in's rows.
           * `bytes` and `bytearray` done (C-3-37, `runtime/src/bytes.cpp`): every method but `%`,
             and the UTF-8, ASCII, Latin-1 and utf-8-sig codecs with CPython's error ranges and
             handlers. Left, each stopping by name: `%` (with `str %`), a class derived from them
             (with `str`'s and `list`'s), the codecs UTF-16 and UTF-32, `namereplace`.
           * `list.sort` and `sorted` done (C-3-38, `runtime/src/sort.cpp`, powersort line for line,
             since a `__lt__` can see which pairs are compared), and `reversed`, `enumerate`, `zip`,
             `map`, `filter`, `min`, `max`, `sum`, `any`, `all` (`runtime/prelude/iterating.py`).
             `iter(callable, sentinel)` and `ascii` stop by name.
           * Big ints done (C-6-10, `runtime/src/bigint.cpp` on a copy of SEL's `bn`): every operator
             at every size, floor semantics, two's complement, CPython's hashes (D-22 ended), text in
             every base with the limit of digits, the three readings of an index, `range` past 64
             bits with `longrange_iterator`, a subclass holding a big value, `bin`, `oct`, `hex`,
             `divmod`, `pow`, `round`, `to_bytes`, `from_bytes`, `slice.indices`, `sys.maxsize`.
             Measured against CPython on numbers each program draws, past each of `bn`'s changes
             of algorithm, and under ASan and UBSan. Inline limbs wait for a measurement that asks.
           * `frozendict` done (C-6-11; C-6-05 reaches it through `copy`, which needs `_weakref`), and
             with it `dict.__reversed__` and the views' (`reversed` of a dict stopped by name until
             now). Set operations on dict views still stop by name.
           * `itertools` done (C-7-20, `runtime/prelude/itertools.py`): the first built-in module written
             in Python, compiled with the prelude and run at the first import.
           * `_operator` done (C-7-21, `runtime/prelude/_operator.py`), so `operator` is the standard library's.
           * `float` done (C-6-12, `runtime/src/float.cpp`), with `int / int`, `int ** negative`, `sum`'s
             compensation and `tuple.index` and `count`.
           * `_thread` done (C-7-22, `runtime/prelude/_thread.py`): one thread, and what would need another stops
             by name. `threading` itself is the standard library's, still to import.
           * `_collections` done but for `OrderedDict`, which stops by name (C-7-23, `runtime/prelude/_collections.py`),
             with `list` slice assignment and `str.maketrans`.
           * `set`'s and `frozenset`'s named methods done (C-6-13).
           * `str`'s methods done on ASCII text (C-6-14); beyond ASCII, what needs the Unicode database stops by name.
           * The format mini-language, `str.format`, `format_map` and `_string` done (C-6-15, `runtime/src/format.cpp`).
           * `str %` done (C-6-16, `runtime/src/format.cpp`).
           * `complex` done (C-6-17, `runtime/src/complex.cpp`).
           * `typing.Union` done (C-3-39, `runtime/prelude/bootstrap.py`): `int | str`, and `isinstance` of one. `|` with what is not unionable asks `typing`; a program that has not imported it stops by name, as it is not in its closure. `vars()` of a C type written in Python still lists its private slots and its own `__new__`, and lacks `__getattribute__`.
           * Subclasses of `tuple` done (C-3-40): the object is a `TupleInstance` whose kind stays `Tuple`, as `PyTuple_Check` says yes of it; `is_exact_tuple` says what only an exact one does. `match` on one waits for `match` itself. `__class__` assignment stays [P2+].
           * Staged texts reach compiled programs (`runtime/src/staged.cpp`, `staged_tables` in `pipeline/build.py`): the dry runs' texts are compiled into the binary, and `eval` and `exec` run the one the site asks for, in the namespaces given, or stop with E-01. Still to do: a separate locals mapping (the second entry point, S-1, which `dataclasses` needs), `compile()`'s staged code objects, the manifest's refused and unsupported functions at their call, and a text's `__future__` flags against the caller's. `namedtuple` now stops at its generator expression.
           * Generators done (C-3-41, `runtime/src/generator.cpp`, the emitter's `generator`): the state machine of design section 10.3. Still to do: coroutines and async generators on the same machinery, `gi_code` and `gi_frame` (no code or frame objects yet), `throw(type, value, tb)` (a DeprecationWarning), and a generator in a reference cycle, which waits for 3c's collector.
           * `_functools` done (C-7-25, `runtime/prelude/_functools.py`), with `sentinel` (bootstrap.py) and `types.MappingProxyType` over any mapping. `namedtuple` works compiled. `functools.update_wrapper` on a built-in function stops at `builtin_function_or_method.__doc__`.
           * The rest of the exception hierarchy (C-6-18): `OSError` with its errno map and the two-argument `args`, `SyntaxError`, the `Warning`s; `errno`; `NoneType()`. `ExceptionGroup` stays absent, with `except*`.
           * `posix` and `os` (C-7-26): every name of the pin's module exists, the calls a program most needs are real system calls (`runtime/src/posix.cpp`) with what CPython's errors carry, and the rest are functions that stop by name when called, as are `dir_fd=` and the like. `sys.builtin_module_names`, `platform`, `audit`, `getfilesystemencoding`, `getfilesystemencodeerrors`; `builtin_function_or_method.__doc__` from the names table. Named tuples (`_bella_structseq` in bootstrap.py): `sys.version_info` and `time.struct_time` will use them. Not yet: `scandir` and `DirEntry`, so `os.walk`; `fork` and the process functions.
           * A type written in C is one kind of thing whichever language the runtime writes it in (C-3-42): `present_methods` makes the prelude's methods built-ins that run the prelude's function, so `type()`, `repr()`, binding and the receiver's check are the C++ types' own; `wrapper_descriptor` and `method-wrapper` are real types, where they stopped by name; `object.__new__(itertools.count)` is CPython's TypeError, so the prelude allocates with `_bella_new_instance`, C's `tp_alloc`.
           * `object.__reduce_ex__`, `__reduce__`, `__getstate__` (C-3-43), in bootstrap.py from Objects/typeobject.c, over `copyreg`; a program that reaches them without importing `copyreg` stops by name. What a C type's layout refuses comes from the names table (`itemsize:`, `state:`). `type.__flags__` is exact (C-3-44): a C type's from the names table, a class's from what a class that says nothing has on its first C base, with its `__slots__`, abstract, collection and vectorcall bits; `abc` now keeps the collection flags, which `match` will read.
           * Subclasses of `str` (C-3-45): a `StrInstance` whose kind stays `Str`, as `tuple`'s, with `str`'s own slots reading the text whatever the subclass says. `str` operations return the very object where CPython's writer does (`s + ""`, `s[:]`, `"%s" % s`, `"{}".format(s)`, a partition that finds nothing), and `"%s" % (x,)` is compiled as the f-string it says (`optimize_format`). A str subclass as an attribute's stored name, a keyword's name, a class's name or a key in its namespace stops by name, since CPython keeps the object there. `enum` imports. Next: `_sre`, where both easy targets stop.
           * `re` over `_sre` (C-7-27), as review log D-9 decided: `runtime/src/sre.cpp` and `sre_lib.inc` are the C port of the engine and the code validator, in the C's shape with Secret Labs' notice (L-08); `runtime/prelude/_sre.py` is what `sre.c` does with objects. `tools/unicode_tables.py` generates `runtime/src/unicode_tables.inc` from the pin (L-03), held to it by `make verify`, and `runtime/src/unicode.cpp` answers from it: the engine's categories and case mappings, `repr()` beyond Latin-1, `str.isidentifier`. `iter(callable, sentinel)`; `builtin_method`; a prelude's property where the C has a member or a getset is that descriptor. `\\N{...}` waits for `unicodedata`; the other `str` methods beyond ASCII can now use the tables.
           * The `sys` surface of section 7 and what the library reads when it imports (C-7-28): `version_info`, `flags`, `float_info`, `int_info`, `hash_info`, `thread_info` as named tuples, `implementation` as D-16 has it, `set`/`getrecursionlimit`, `getsizeof`, and the rest. `sys.executable`, `prefix` and the others say the compiled program, deviation D-21, accepted by the author 2026-11-06 with a lint rule for `sys.executable`. 
           * The codec registry (C-7-29): `runtime/prelude/_codecs.py` from Python/codecs.c and Modules/_codecsmodule.c, over the UTF-8, ASCII and Latin-1 codecs of `runtime/src/bytes.cpp`, which now decode statefully (`final`). `str.encode` and `bytes.decode` take CPython's shortcuts for the names PyUnicode_AsEncodedString and PyUnicode_Decode shortcut, and the registry for every other name, so `encodings`' search function finds the phase-1 codecs by a computed name and a program's registered codec works; a failing codec gets CPython's note (`BaseException.add_note`, new). The eight error handlers are built-in functions of no module; a handler the program registers, or a built-in name re-registered, stops by name when a built-in codec would call it. Start-up imports `encodings` before the program's first line, as _PyCodec_InitRegistry does, so `_codecs`, `codecs`, `encodings`, `encodings.aliases` and `encodings.utf_8` are in `sys.modules` from the start; `find_program_modules` seeds every program with them and the manifest's `[dynamic.encodings]` list. Not written: UTF-16 and UTF-32 (phase 1), UTF-7, the escape codecs and charmap, namereplace.
           * `_io` (C-7-30): `runtime/prelude/_io.py` from Modules/_io, class by class with the C's bases, state and messages: the four base classes, `FileIO` over posix.cpp's calls, `BufferedReader`, `BufferedWriter` and `BufferedRandom` as one state machine (the C's `buffered` struct), `BufferedRWPair`, `BytesIO`, `StringIO`, `IncrementalNewlineDecoder`, `TextIOWrapper` with the C's pending bytes, read chunks, snapshot and seek/tell cookies, and `open`, `open_code`, `text_encoding`. `builtins.open` is `_io.open` from the start (`_io` is imported at start-up). A prelude property may have a setter now (a pool beside the getters), `__del__` is a slot wrapper of no arguments, and a heap type of CPython's keeps its inherited `tp_new` for `__reduce_ex__`. Where CPython hands a raw stream's `readinto()` a memoryview, the buffered classes hand a bytearray of the length and stop by name if it was resized. Not written, stopping by name: `BytesIO.getbuffer`, `TextIOWrapper.reconfigure`, (the RuntimeWarnings of `open` and `FileIO` are issued since 2026-11-10: C-7-63). The `ResourceWarning` for an unclosed file is emitted since 2026-11-10 (C-7-62; DECISIONS), as the dialect specification's lifetimes section asks. `sys.stdin`, `stdout` and `stderr` are `_io` objects made at start-up as create_stdio makes them (`PYTHONIOENCODING` honoured), in place of the runtime's own class; the runtime's reports (a traceback, a SystemExit's message, an exception ignored) go through `sys.stderr` as CPython's do, and the flush at the end that fails is exit status 120.
           * `pwd`, `grp`, `_locale`, `zlib`'s shape and `_ast` (C-7-31, C-7-32), what `cli_easy_slugs` imports next: `pwd` and `grp` over the C library's database calls with the C's converters and messages (`_Py_Uid_Converter`'s -1 and ranges); `_locale` over `setlocale`, `localeconv`, `strcoll`/`strxfrm` (wide strings), `nl_langinfo` and the `gettext` family, the pin's constants, and `_Py_SetLocaleFromEnv` with PEP 538's coercion at start-up; `zlib` with its constants and `error`, every function stopping by name (its library is licence entry L-02, still open); `_ast` as Python-ast.c makes it, generated from the pin: the 126 node classes with `_fields`, `_attributes`, `__match_args__`, docstrings, `_field_types` (the same dict as `__annotations__`) and the optional fields' class-attribute defaults, `AST.__init__`, `__reduce__`, `__replace__` and the depth-limited repr; `ast.parse` (compile()) and an abstract class's instantiation (a DeprecationWarning) stop by name. With them: `type.__annotations__` and `type.__annotate__` as typeobject.c has them (`__annotate_func__`, `__annotations_cache__`); a type of CPython's whose flags lack IMMUTABLETYPE (ast's nodes) takes a class attribute; a type C made with `type()` keeps its bare `tp_name` (the names table records which: `ast.Constant` says `'Constant' object`, `_io.FileIO` says `'_io.FileIO' object`); the names table is keyed by `tp_name`, since `ast.Match` and `re.Match` are not one type; `dir()` of an instance shows its dict where CPython's type has a `__dict__`; the t-string types `Template`, `Interpolation` and `TemplateIter` (`runtime/prelude/templatelib.py`, from templateobject.c and interpolationobject.c) behind the `template` and `interpolation` intrinsics and `string.templatelib`, which `annotationlib` imports. The prelude's units compile at -O1 (the `_io` unit took GCC 16 nine minutes at -O2).
           * `_typing` (C-7-33): `runtime/prelude/_typing.py` from Objects/typevarobject.c: `TypeVar`, `ParamSpec`, `ParamSpecArgs`, `ParamSpecKwargs`, `TypeVarTuple`, `TypeAliasType`, `Generic`, `NoDefault`, `_ConstEvaluator` and `_idfunc`, with the lazy bounds, constraints, defaults and values, substitution through `typing`, and the unions `make_union` and `_Py_union_type_or` make (a `TypeAliasType` is unionable now). PEP 695's intrinsics (`type_params`, `generic_class`, `typealias`, `set_type_params`) are the module's, imported at first use, reading the parameter text the frontend writes; a module prelude's `__intrinsics__` and `__hidden_classes__` work as a start-up prelude's. The frontend's lazy functions are CPython's shape now: one positional `format` parameter, 1 by default, refused above 2, named after their parameter or alias (one function for a constraints tuple), and eval1 gives the oracle's the same qualnames (C-3-25, C-3-27 and C-3-28 pass compiled with it). With them: `type()` refuses a base with `__mro_entries__` as CPython does; a presented class keeps its own `__class_getitem__`; a prelude class's `__module__` is its tp_name's; a C type without a `__dict__` row shows none. Not here: the STRING and FORWARDREF formats of a lazy function (`annotationlib`'s fake globals need the second entry point: `function.__closure__` stops), a string bound's `ForwardRef` (typing compiles it eagerly: stops at `compile()`).
           * A staged text under `exec(text, globals, locals)` with a locals mapping of its own (dataclasses' `_FuncBuilder.add_fns_to_class`): the text's `Module` carries the locals dict, its top level reads and writes it (LOAD_NAME, STORE_NAME) and its functions see the globals, as PyEval_EvalCode runs it; a mapping that is not a dict stops by name. `type.__dictoffset__` and `__weakrefoffset__` (dataclasses' `slots=True` reads them): a C type's from the names table (`offsets:`), a class's by type_new_alloc's rule (a managed dict is -1 where the base has none, a managed weak reference -32 where the base has none and is not variable-sized). `sentinel`'s hash and comparisons are object's as its own slots (tp_hash, tp_richcompare).
           * Code objects, their names and counts (C-3-46; E-02 narrowed in v0.14 by the author, 2026-11-07): `function.__code__` is one `code` object per compiled function with `co_name`, `co_qualname`, `co_filename`, `co_firstlineno` (a decorator's line), the argument counts, `co_nlocals`, `co_varnames` in CPython's order (an inlined comprehension's variables where it stands, its cells among them, `resolve.co_varnames`), `co_cellvars` (parameter cells first, the rest sorted, an inlined comprehension's among them, `resolve.co_cellvars`), `co_freevars` and `co_flags` (`CO_NESTED` from the enclosing codes, `CO_FUTURE_ANNOTATIONS` from the module's future set; review A14); `function.__closure__` is the cells; `del cell.cell_contents` empties a cell. The bytecode side (`co_code`, `co_consts`, `replace`, `code(...)`, `__code__` assignment) stops by name. `dataclasses(slots=True)` repoints `__class__` cells with them; a slots dataclass without a `__class__` reference then imports `inspect` for `__wrapped__` members, which imports `dis` and `_opcode`: the next module (its tables from the pin; `stack_effect` and the rest stop by name). Under eval1 a function's `__code__` is the interpreter's own: a code object synthesised by the oracle (`compile` of a stub with the same parameters, locals, cells and kind, then `replace`) would make C-3-46 pass there too.
           * `_json` (C-7-34): `runtime/prelude/_json.py` from Modules/_json.c: `scanstring`, `encode_basestring`, `encode_basestring_ascii`, the `Scanner` (`make_scanner`, with the memo that makes a repeated key one object, the hooks, the StopIteration carrying the index) and the `Encoder` (`make_encoder`, answering one chunk in a tuple, the indent cache, `sort_keys` over the items, the notes a failing item adds, circular references by identity), each message the C's. The build searches `PYTHONPATH`'s entries after the program's directory, as CPython's import does, which is how the target runner's vendored packages (`targets/vendor`) reach a compiled target. `service_easy_tokens` stopped next at `binascii`, then `_struct`; behind them `hashlib`'s family (`_md5`, `_sha1`, `_sha2`, `_sha3`, `_blake2`, imported at `hashlib`'s import) and `_hmac`, then `time`.
           * `binascii` (C-7-35): `runtime/prelude/binascii.py` from Modules/binascii.c: `a2b_base64` and `b2a_base64` with 3.15's parameters (`padded`, `wrapcol`, `newline`, `alphabet`; `strict_mode`, `ignorechars`, `canonical`) and every message of the strict decoder, `a2b_hex`/`unhexlify` with `ignorechars`, `b2a_hex`/`hexlify` with a separator (Python/pystrhex.c, where a Latin-1 str separator is allowed when bytes come back), `crc32`, `Error` and `Incomplete`, the alphabets; the clinic's converters (an ASCII str or a bytes-like object; `size_t`'s three messages; `PyBytesObject`) and its calling conventions. uu, quoted-printable, `crc_hqx`, base32, ascii85 and base85 stop by name, as does a `crc32` seed outside 32 bits (3.15 masks it with a DeprecationWarning, which stderr would have to carry).
           * `_struct` (C-7-36): `runtime/prelude/_struct.py` from Modules/_struct.c: the format string (byte order, counts, whitespace, every code of 3.15 including `Zf`/`Zd` and the native-only `n`, `N`, `P`), the native table with x86-64's sizes and alignments and the standard tables, pack and unpack of each kind with the C's range, type and count messages, `Struct` (`format` and `size` members, the methods, `__repr__`, `__sizeof__`), `unpack_iterator`, the module's functions over the hundred-entry cache, `error`. Floats go through two runtime primitives written from Objects/floatobject.c (`_float_pack`, `_float_unpack`: PyFloat_Pack2's software path, Pack4's cast with the overflow test and the NaN payload fix, and the plain casts of the complex codes that `init_endian_tables` puts in the little-endian table). A Struct subclass and a second `__init__` format stop by name (3.15 warns there).
           * `time` (C-7-37): `runtime/prelude/time.py` from Modules/timemodule.c and Python/pytime.c over ten calls in posix.cpp (`clock_gettime`, `clock_getres`, `clock_settime`, `localtime_r`, `gmtime_r`, `mktime` with the C's `tm_wday` sentinel, `strftime` with the doubling buffer, `tzset`, `clock_nanosleep` on the monotonic clock to a deadline, `pthread_getcpuclockid`): the clocks and their float and nanosecond forms, `sleep`, `gmtime`, `localtime`, `mktime`, `strftime` (an ASCII run through the C library, the rest copied up to the next `%`), `asctime`, `ctime`, `strptime` through `_strptime`, `struct_time`, `get_clock_info`, `tzset` and the module's `timezone`, `altzone`, `daylight`, `tzname` by this build's January-and-July rule (no HAVE_DECL_TZNAME), set on the module itself through a new prelude primitive (`_bella_module_set`, PyModule_Add from inside). A timestamp converts as pytime does (an index, else a real number; floor; the two overflow messages).
           * `math` and `math.integer` (C-7-38): `runtime/prelude/math.py` from Modules/mathmodule.c over one primitive (`_libm`, libm.cpp: the C library's function by name with errno, so math_1, math_1a, math_2 and is_error are the prelude's), and `runtime/prelude/_math_integer.py` from Modules/mathintegermodule.c (gcd, lcm, factorial, comb, perm, isqrt over Python's ints, the C's messages), registered as `math.integer` in sys.modules with math's six taken from it. CPython's own gamma, lgamma, sinpi, remainder, log/log2/log10 with the large-int path (`n / 2**bits` for `_PyLong_Frexp`), fsum, the double-length vector norm of hypot and dist, sumprod's triple length, pow's special cases, nextafter with steps over the float's bits (`_float_pack`), ulp, isclose, prod, floor/ceil/trunc through the special methods, frexp/ldexp/modf: each ported line for line. fmax/fmin keep GCC's expansion of the C (the first argument where equal, so `fmax(-0.0, 0.0)` is `-0.0`), which CPython's build has and the library call does not. `service_easy_tokens` stopped next at `_md5`.
           * The digests (C-7-39): `_md5`, `_sha1`, `_sha2`, `_sha3`, `_blake2` and `_hmac` as preludes from their C modules over `runtime/src/hashes.cpp`, where MD5, SHA-1, SHA-2, Keccak (SHA-3 and SHAKE) and BLAKE2b/s with the full parameter block are written from RFC 1321, RFC 3174, FIPS 180-4, FIPS 202 and RFC 7693 (no library: licence entry L-04 needs none). A hash's state travels as bytes (`_hash_new`, `_hash_update`, `_hash_digest`, `_hash_xof`), so a copy is a copy of bytes. The types' shapes are the C's: `_md5.md5` and `_sha1.sha1` made by their functions alone (the names table's DISALLOW_INSTANTIATION flag now marks a presented class), `_sha2.SHA256Type` and the rest, `_sha3`'s six types with their own constructors (whose errors say `sha3_224()`, as the clinic does), `_blake2`'s two with every parameter checked in the C's order, `_hmac.HMAC` with RFC 2104 in Python over the digests, the one-shots. The deprecated `string` keyword stops by name (3.15 warns). hashlib and hmac run as in a CPython without OpenSSL (deviation D-20): `hashlib.new('ripemd160')` and `hmac.new(key, msg, 'blake2s')` differ from the pin by design. `service_easy_tokens` stopped next at the `setup_annotations` intrinsic.
           * PEP 563 in the runtime (C-3-47): the `setup_annotations` intrinsic (SETUP_ANNOTATIONS's rules on the namespace: an exact dict asked without running code, another mapping through `__getitem__`, a new dict unless one stands), `function.__annotations__` with funcobject.c's rules (made once from `__annotate__` and cached, the setter and deleter clearing `__annotate__`, `__annotate__`'s setter clearing the dict), and under `from __future__ import annotations` the function's `__annotate__` returns the strings (as CPython 3.15.2's does; a first version made the dict at definition and dropped `__annotate__`, which the staging check caught in CI). `service_easy_tokens` stopped next at `zlib.compress` (licence entry L-02, settled 2026-11-08: zlib linked). `data_easy_sales` stops at `_csv`. `_contextvars` (which `traceback` imports) and `_opcode` (`inspect`) stay in the queue.
           * `_csv` (C-7-40): `runtime/prelude/_csv.py` from Modules/_csv.c, no primitive beyond `_tp_name`: the Dialect type with the C's conversions (`_set_char`, `_set_char_or_none`, `_set_str`, `_set_int` with its C-int range, `_set_bool`) and checks in its order, an instance reused when nothing else is given, attributes read off any object or a registered name; the reader's state machine (`parse_process_char` with its nine states and the end-of-line pseudo-character, so quoted fields span lines and `\r`/`\n` inside and outside quotes behave as the C's), QUOTE_NONNUMERIC/QUOTE_STRINGS floats and QUOTE_NOTNULL/QUOTE_STRINGS None, the field size limit, `line_num`, the strict errors; the writer's `join_append` with escaping, doublequote and the space-delimiter rule, the single-empty-record rule, `writerows`; the registry and `field_size_limit`. `_csv.reader`/`_csv.writer` are made by their functions alone (the table's flag), their members and getsets come from the prelude's properties. The `csv` package runs compiled over it (reader, DictReader, writer, Sniffer, dialect classes); `csv.DictWriter` stopped at the runtime's set operations on dict views (`rowdict.keys() - fieldnames`) until C-6-19, and `method_descriptor.__doc__` answers since the digests step. `data_easy_sales` moves from `_csv` to `_contextvars`, which `_pydecimal` imports for its context variable.
           * `_contextvars` (C-7-41): `runtime/prelude/_contextvars.py` from Python/context.c, no primitive beyond `_tp_name`: ContextVar (the constructor's `O|$O` parsing in the C's order, `get` with its three fallbacks, `set` returning a Token, `reset` with the used, other-variable and other-context errors, the hash from the address and the name), Token (`MISSING` as an instance of its own `Token.MISSING` type, the context manager of 3.14), Context (a mapping of variables replaced on every set and shared by copies, as the C's HAMT is; `run` enters the context so sets land in it and stay, re-entering refused; `__eq__` over values; the `keys`/`values`/`items` iterator types of builtins as hidden classes) and `copy_context`. The thread's current context is the module's. Iteration order is insertion order where the C's is its hash tree's (address-dependent, so no observable). `decimal` on `_pydecimal` runs compiled with it (`localcontext`, `getcontext`). `data_easy_sales` moves from `_contextvars` to `_bisect`.
           * `_bisect` (C-7-42): `runtime/prelude/_bisect.py` from Modules/_bisectmodule.c: the clinic's parsing (`lo` through PyNumber_Index and PyLong_AsSsize_t, non-negative; `hi` an index or None, -1 meaning the length as the C's default does, so `hi=-1` is the length and `hi=-2` is not; the messages in `_PyArg_UnpackKeywords`'s order), PySequence_Size and get_sq_item's errors (a C mapping type is "not a sequence", a class without `__getitem__` "does not support indexing", a class of the program with one is indexed, a subclass of dict included), the comparisons `x < key(a[mid])` and `key(a[mid]) < x`, insort's one key call and its insert through the object. The C mapping types are named (dict, mappingproxy, OrderedDict, defaultdict, re.Match, GenericAlias, Union, the weak proxies): the runtime has no slot to ask. `data_easy_sales` moves from `_bisect` to `_random`, which `random` imports for `statistics`.
           * `_random` (C-7-43): `runtime/prelude/_random.py` from Modules/_randommodule.c: MT19937 on 624 Python ints (init_genrand, init_by_array, genrand_uint32 as the C has them), `random` from two words, `seed` (an int's `int.__abs__`, an object's hash as a size_t, split into 32-bit words from the right; None takes 2496 bytes of `urandom` through posix.cpp), `getstate`/`setstate` with PyLong_AsUnsignedLong's and PyLong_AsLong's messages and the uint32 truncation, `getrandbits` with the uint64 converter's messages and MemoryError where malloc fails. Agrees with the pin bit for bit over seeds of every width and 2000 draws; `random.Random` subclasses it. `_statistics` (C-7-44): `_normal_dist_inv_cdf`, Wichura's AS241 with the C's expression association, sqrt and log through `_libm`. `_heapq` (C-7-45): the ten functions with the C's siftdown/siftup (the comparisons made and their order, the size-change RuntimeError), heapify's cache-friendly order past 2500 items, the clinic's messages; `heapq.merge` stops at the runtime's `list_iterator.__next__` (an iterator's `__next__` as an attribute), queued. `method_descriptor.__doc__` now answers for a method the prelude writes (its docstring is the C's ml_doc); `sys.excepthook` and `sys.__excepthook__` print the traceback as the top level does. `threading` moves from a shim to write to CPython's own module compiled over `_thread` (manifest, closure lock, `_threading_local` compiled as its never-taken fallback): locals, locks, RLock, Event, Condition, Semaphore and the main thread work with one thread, `Thread.start` stops with the milestone name. Known gaps left on the way: `vars()` of a presented C type shows the prelude's private slot members and `__module__`; `wrapper_descriptor.__text_signature__`; subclasses of `list`.
           * The set operations of dict views (C-6-19): `-`, `&`, `|`, `^` with a keys or items view on either side (dictviews_sub, _PyDictView_Intersect with its choice of which side to iterate, dictviews_or, dictviews_xor: a set, the other side any iterable), the comparisons against sets and views (dictview_richcompare, NotImplemented for the rest), `isdisjoint`, `mapping`, and the views' slot wrappers (`dict_keys.__or__` and its kin, the six comparisons) in set.cpp, ops.cpp and slots.cpp. `csv.DictWriter` runs compiled with it. Still queued: subclasses of `list`.
           * The built-in iterators' `__next__` and `__iter__` as attributes (C-3-48): slot wrappers on the sixteen iterator types (slots.cpp), so `it.__next__` binds as a method-wrapper that raises StopIteration at the end; `heapq.merge` runs compiled. The names table gained the bytes, bytearray and reversed-dict iterator types. Still queued on iterators: `__length_hint__`, `__reduce__`, `__setstate__`.
           * `zlib` (C-7-46): zlib 1.3.2, the pin's version, vendored under `runtime/vendor/zlib-1.3.2` (licence entry L-02, admitted by the author 2026-11-08; the release tarball's digest recorded there) and built into the runtime library as C; `runtime/src/zlib.cpp` runs the library's calls on stream handles behind one primitive, with the C module's output block schedule (32 KB, 64 KB, 256 KB, ... from pycore_blocks_output_buffer.h), which deflate's stored blocks take their boundaries from; `runtime/prelude/zlib.py` is Modules/zlibmodule.c in Python: compress, decompress, compressobj and Compress (compress, flush, copy), decompressobj and Decompress (max_length, unconsumed_tail, unused_data, eof, flush), _ZlibDecompressor's buffering, adler32, crc32 and the combines, the messages zlib_error builds. A start value outside an unsigned 32-bit int stops by name (3.15 warns of it, as binascii's does). _ZlibDecompressor with a zdict on a zlib-format stream raises the SystemError CPython 3.15.2 raises (decompress_buf's Z_NEED_DICT path sets no exception); a prelude method whose docstring is all indented lines gets it assigned after the class, since the compiler's docstring cleaning would strip the indent. With it `service_easy_tokens` agrees with its recording: gate 1a.2. `make targets-compiled` checks the easy three.
           * Next, what the survey and a walk of the built-ins' names found: `bytes %`; subclasses of `list` and `str`; `_typing` (`typing`, and the `type_params` intrinsic);
             `_heapq`; `object.__getstate__` and `copyreg`; `_ast` 6, `posix` 6 (`_stat` done, C-7-24; `os` is what stops them), `gc` 4.
             Generators are refused where they run (`weakref`'s iteration, a generator expression), and
             stop more once these are past. Then the rest of the start-up modules run at start-up (`encodings` and its codecs do, with C-7-29).
       * 3c, its first half done: weak references and resurrection (C-9-03, C-9-04, C-9-10), in the model
         first (`RefWeak`, the oracle's `weak_new`, `revive`), then the header and `_weakref`.
       * the `gc` module done 2026-11-12 (C-7-77; DECISIONS): its state, words and refusals, so `weakref.finalize` runs at
         exit; `collect`, `get_count`, `get_stats`, `is_tracked` and `is_finalized` stop by name until the collector is in
         the header, and the object-graph functions stay stops (E-05).
       * 3c, the collector in the model done 2026-11-12 (`refmodel/collector.py`, CPython's gc.c; DECISIONS): the
         author chose how the header finds its objects on 2026-11-14 (DECISIONS): trial deletion over candidate
         roots, so the model's collector is rewritten that way first (it is gc.c's lists today), then the header;
         decided the same day: gc's numbers are the runtime's own and every collection is a full one (D-04 gets
         the observable and a lint rule), the candidate buffer's size triggers a collection (growing with the heap:
         taken, for the author to overrule), and a lean build collects only when asked, at the runtime's looks and
         at exit (D-24 gets it); then `make object-test` with `World(cycles=True)`.
       * 3c, what is left: the cycle collector in the header, `gc`: C-3-12, C-9-01, C-9-02, C-9-07; it
         replaces the exit walk, which today finalises a list's items first to last and in breadth-first
         order, where CPython's teardown releases what it can by reference count. `_abc` takes real weak references then, which only the collector can tell
         from today's strong ones (a class is in a cycle with its own mro). With it, a caught exception
         keeps its frame's locals (RL-222, decided with D-12).
  * **Gap, marked (2026-11-02):** L2 v1 has a type slot on every place, always `object`; the
    design's level table says every L2 expression carries the oracle's type. Closes in phase 2,
    when a pass produces `Fact.TYPES` (none does today, so none can require it). Until then no
    pass may let a declared type change what a program does.
  * Module globals in phase 1: a dict per module and a per-site cache (key version and index, as
    `LOAD_GLOBAL_MODULE`); the author's glue pass is phase 2, with the module dict as a view over
    the fields, modelled first (see "After Gate 0").
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
  is committed under `pipeline/examples/out/`. **Reached 2026-11-07**: `make targets-compiled` (the third leg, in
  `make check` and CI) builds the driver with `pipeline/build.py --run` and compares the bytes; the compiled
  `cli_easy_slugs` agrees with the recording. **Gate 1a.3 reached 2026-11-08**: the compiled `data_easy_sales` agrees with its
  recording (`make targets-compiled` checks both), after `_csv`, `_contextvars`, `_bisect`, `_random`, `_statistics`, `_heapq`,
  `sys.excepthook` and CPython's own `threading` compiled over the `_thread` prelude. **Gate 1a.2 reached 2026-11-08** with zlib (L-02 settled: zlib linked): the compiled `service_easy_tokens` agrees with its recording. The easy three are done compiled. The tricky three were run compiled the same day (DECISIONS 2026-11-08): each stops before its first line, at `configparser`/`optparse` (admitted the same day, C-7-48 and C-7-49), `_warnings`, `_opcode` (done, C-7-47), `importlib` (core, not provided yet), a staged `compile()`'s code object and `list` subclasses, in that order of dependence; C-7-49 compiled also wants the exception-group classes, which `contextlib.suppress` reads. `_warnings` done the same day (C-7-50 on all legs, C-7-51 compiled after `importlib`), with `_tokenize` (construction only) and `sys.path_importer_cache`. `importlib` done 2026-11-09 (C-7-52; DECISIONS): the markdown target now stops at `str.isspace` beyond ASCII (the Unicode database), the CLI target at `collections.OrderedDict`. The exception-group classes done the same day (C-3-49; DECISIONS), and `list` subclasses (C-3-51; `import traceback` and C-3-50 compiled). The staged `compile()` code object done the same day (C-8-11; DECISIONS): **`data_tricky_toml` agrees with its recording compiled**, the first of the tricky three, and `make targets-compiled` checks it. `collections.OrderedDict` done 2026-11-10 (C-3-52; DECISIONS): cli_tricky_check now stops at `_tokenize.TokenizerIter` (the C tokenizer), and compiled `inspect.signature` answers as CPython does (S-2 is the author's to revisit). str's predicates and case conversions beyond ASCII done the same day (C-3-53; DECISIONS): **`service_tricky_markdown` agrees with its recording compiled**, the second of the tricky three. S-2 revised the same day: function signatures at runtime are \[P1\] (C-3-24 compares output). The tokenizer done the same day (C-7-53; DECISIONS): CPython's lexer as its own C text under `runtime/src/tokenizer.cpp`; **`cli_tricky_check` agrees with its recording compiled, and with it all six targets** (`make targets-compiled`). `atexit` done the same day (C-7-54, C-7-55; DECISIONS): the end of a program is `Py_FinalizeEx`'s order, `threading._shutdown` then the handlers, and C-7-49 compiled now stops at `os.scandir`. The hooks of the way out done the same day (C-7-56, C-7-57; DECISIONS): `sys.excepthook` with `sys.last_exc`, `sys.unraisablehook` with its `UnraisableHookArgs`, `traceback.tb_next`. `os.scandir` and `dir_fd` for `stat`, `lstat`, `open`, `unlink`, `rmdir` done the same day (C-7-58; DECISIONS): **C-7-49 passes compiled**. Next, with every target agreeing: (the copying functions of `os` are done: `copy_file_range`, `sendfile`, `chmod`, `fchmod`, C-7-59; `utime` and the extended attributes, C-7-60; `shutil`'s copy and move functions run) (the ResourceWarning of an unclosed file is done: C-7-62, in flight and on the way out; the default hook's "Enable tracemalloc" line, which E-03 leaves out, is accepted and listed under D-20: the author's decision of 2026-11-14; done after it the same day: the two RuntimeWarnings of `io` and `os`, a bool as a file descriptor and line buffering asked of a binary file, C-7-63; queued from it: the source line `_warnings` prints itself when `warnings._showwarnmsg` is gone, a stop by name) (`dir_fd` for `os.mkdir`, `access`, `readlink`, `symlink`, `link`, `rename` and `replace` is done: C-7-64, and C-7-61 has their rows) (the descriptor functions of `os` are done: `dup`, `dup2`, `pipe`, `pipe2`, the inheritable and blocking flags, `closerange`, `fchdir`, `fdatasync`, `sync`, `truncate`, `ftruncate`, `pread`, `pwrite`, `lockf`, `posix_fallocate`, `posix_fadvise`, C-7-65; the wait statuses, `waitstatus_to_exitcode`, `major`, `minor` and `makedev`, C-7-66; ownership, the ids and groups, the priority, `getloadavg`, `sched_yield` and `getrandom`, C-7-67; of `os` still stopping by name: the process functions (`fork`, the `exec` and `wait` families, `kill`, `system`), `fork` and `forkpty` are [P2+] by the spec (sections 3 and 7) and stay stops, and `wait3` and `wait4` give a `resource.struct_rusage`, a module the manifest does not have; `_signal` done 2026-11-11 (C-7-75, C-7-76 on the compiled leg; D-24, D-25, D-26; DECISIONS), with `os.kill`, `os.killpg`, `_thread.interrupt_main`, SIGINT as KeyboardInterrupt and an untimed lock wait that is a real one: generated code looks at a frame's start and a loop's turn, as CPython's evaluation loop does, and the build has `--fidelity lean`, which leaves those looks out; case C-7-11 compiled still waits for `gc`. Left from it: the looks CPython's C takes that the runtime does not (D-25 (e): `_sre` every 4096 steps, big-int multiplication, division and conversion to decimal, the start of `str()`, `repr()` and print; each a `check_signals()` where the C has it): **to be closed, the author's decision of 2026-11-14** (a case first: an alarm's handler that raises inside a long match, as measured, 1 s under CPython and 7 s compiled); the other places of D-25, (b), (c), (d) and (f), are accepted (the same decision), with the lint rule for (c) owed to `bella-lint`, and stay reopenable if a program needs them (the generator-expression calls could be lowered as CPython's loop, and the layout looks marked as the breaks are); the frontend gives a list, set or dict comprehension in a scope that can see a class (an annotation scope, a type alias, a type parameter's bound in a class) its own frame and CPython's name and qualname (`<listcomp>`, symtable.c's `ste_can_see_class_scope`), where it inlines them today, a conformance case first; the signal tests found, and C-3-61 fixed, the lines of a with statement's own work; the switch is read from the build command and `BELLA_FIDELITY` only: `bella.toml`'s `[runtime]` is to carry `fidelity` when it is read at all, with D-09's `assertions` beside it (nothing reads that table yet); `statvfs`, `fstatvfs`, `sysconf`, `confstr`, `pathconf` and `fpathconf` are done, C-7-68; `readv`, `preadv`, `writev`, `pwritev`, `readinto`, `eventfd` with its read and write, `memfd_create`, `mkfifo`, `mknod` and `splice`, C-7-69; the five `timerfd` functions, the nine `sched_*` functions and `sched_param`, `pidfd_open`, `ctermid`, `device_encoding`, `getlogin` and `getgrouplist`, C-7-70; the setters of ids (`setuid` to `setresgid`), `setgroups`, `initgroups`, `setpgid`, `setpgrp`, `setsid` and `setpriority`, C-7-71; the pseudo-terminal functions (`openpty`, `posix_openpt`, `grantpt`, `unlockpt`, `ptsname`, `ttyname`, `tcgetpgrp`, `tcsetpgrp`, `login_tty`), `chroot`, `unshare`, `setns` and posix's two input-hook functions, C-7-72; `posix_spawn`, `posix_spawnp`, `wait`, `waitpid`, `waitid`, `system`, `execv`, `execve` and `abort`, C-7-74: the four names of `posix` left without a body (`fork`, `forkpty`, `wait3`, `wait4`) say what they wait for when they stop; members and getsets say CPython's `__doc__` and are the kind CPython's are (C-3-56); a partial given no dict has none (C-3-57); what a sweep of ninety types still shows: `type` lacks `__basicsize__`, `__itemsize__`, `__type_params__`, a generator `gi_code` and `gi_frame`, a module `__annotations__` and `__annotate__`, a code object most of its members, `__text_signature__` and `__vectorcalloffset__` are nowhere, `SimpleNamespace` shows a `__weakref__`, `vars(UnicodeEncodeError)` stops at its `__init__`, and the preludes' own slots (`GenericAlias._ga_parameters`, a union's) are visible in `vars()` of their types) (`gc` done 2026-11-12, C-7-77; `except*` done the same day, C-3-16 and C-3-62, DECISIONS) (the report of an exception group and of notes done the same day, C-8-12) the built-ins' `__text_signature__` (so that `inspect.signature` answers for a built-in and for a class with neither `__init__` nor `__new__`), source lines in an uncaught traceback. Review F17 done the same day (RL-404 to RL-421; DECISIONS): thirteen fixed, two stops by name; left from it: replaying a staged text's compile-time warning through the program's filters (RL-414, a stop until then), a frame's locals inside an inlined comprehension (RL-409, a stop), the quadratic C++ of a long `elif` or `and` chain (seen under RL-417), RL-410 and RL-419 were decided by the author and done on 2026-11-10 (DECISIONS: the dry run confined with a note; the bootstrap classes' members back and guarded, the two namespaces' own names hidden and their listing stopped by name). **On the roadmap from RL-419:** split `bootstrap.py` into the import system and a start-up module of its own (`SimpleNamespace`, `GenericAlias`, `Union`, the pickling helpers) and re-home the runtime's primitives, so that `dir()` and `vars()` of `_frozen_importlib` and `_frozen_importlib_external` are CPython's and need no stop; to do when a program needs the listing. Seen with RL-419, measured again and done on 2026-11-11 (C-3-54; DECISIONS): what an AttributeError carries when an attribute cannot be set or deleted, the members' wording, and a function's `__dict__`, `__doc__` and own attributes set and deleted. `property`, `staticmethod` and `classmethod` done the same day as CPython's types are (C-3-55 on every leg; DECISIONS): their fields in slots no program can name, the members and getsets by the names table, the constructors, copies, names and docstrings as `descrobject.c` and `funcobject.c` have them; with it a slotted class's own names ("is read-only") and `__reduce_ex__` of a subclass of a C type. Left from it: the words of a wrong arity to `__get__`, `__set__` and `__delete__` called by hand (`del` of a partial's `__dict__` is refused since C-3-57, and `partial.__setstate__` given no dict leaves the partial with none: `drop_dict` in the model and the header). **Three divergences measured with C-3-57 and C-3-58 on 2026-11-11, all older than them, all in the order an object's attribute values are released; all three closed the same day:** `del obj.__dict__` of a class's instance (C-3-58; a method call as the first thing asked afterwards stays different, deviation D-23, which the author wants reconsidered: exact needs a call's load told from a plain one through L1, L2, the backend and both evaluators); and the kind of dict an instance has, which is its class's (C-3-59; DECISIONS): the values in the object for a program's class and a subclass of a built-in type of fixed size, a dict of its own that shares the class's keys for an `int`'s or a `tuple`'s subclass, an ordinary dict for a type written in C with its own dict slot and whatever derives from it (exceptions, `functools.partial`, an `lru_cache` wrapper, `types.SimpleNamespace`, `staticmethod`, `classmethod`, `collections.OrderedDict`, the `io` classes, `threading.local`), decided by CPython's own type flags and dict offsets in the names table. A fourth, found by the model's Hypothesis machine right after C-3-59 and closed the same day (C-3-60; DECISIONS): a class's shared keys have thirty places, and each instance made takes one as a key does, so a class that has made some thirty instances takes one more name and then none. Left from C-3-59: a type the table has no row for keeps its values in the object, as before, and nothing lists such types yet (the test compares some seventy types with CPython, not all the runtime presents); seen while sweeping: subclasses of `set`, `frozenset`, `bytes` and `bytearray` done 2026-11-12 (C-3-63, C-3-64); `bytes % ...` (PEP 461) done the same day (C-6-20); the S-1 entry points in compiled programs done the same day (C-3-65 and, compiled, C-3-13, C-3-21, C-3-22; typing's `NamedTuple` and `TypedDict` class syntax, `__bases__` assigned the bases a class has, `types.CellType`, a module's `__annotations__` and `__annotate__`; DECISIONS), noted from it: a compiled traceback through annotationlib showed the shim's line numbers (done the same day, C-3-67: the three shims keep every line of CPython's at its own number, `tools/tests/test_shims.py`; FORWARDREF of a hand-written VALUE-only annotate function goes through a native stand-in on CPython's own lines); `C.__bases__` and `C.__mro__` were a new tuple at each read (done the same day, C-3-68: one object each until replaced, model first); a staged text's annotate functions get no entry point (a stop by name); a type parameter's bound or constraints and its default share the compiled key (qualified name and first line), so both are declined and stop under STRING and FORWARDREF: an anchor in the compiled `Code` (the first expression's position) would tell them apart; match's runtime half in compiled programs done the same day (C-3-66; C-3-17, C-8-08 and C-8-09 pass compiled; `runtime/prelude/match.py` among the runtime's Python modules, a type's tp_name from the runtime, and eval1's from CPython's own message; the length hint through the old protocol's iterator; `str.join` through `PySequence_Fast`; `pipeline/tests/test_compiled_match.py`); no message in the runtime truncates a name to CPython's `%.80s` or `%.200s`, so a type name longer than that is printed whole; binascii's base32 both ways and the UTF-16 and UTF-32 codecs done the same day (C-7-79; C-7-07 passes compiled; `test_base32`, `test_wide_codecs`); `cmath` done the same day (C-7-80; C-7-08 passes compiled; `test_cmath`; DECISIONS), and from it a question for the author: of two NaN operands CPython's float `+` and `*` give the left one's NaN and the runtime's compiled ones the right one's (GCC commutes them), complex `+` the other way round; decided by the author on 2026-11-14: unspecified, like libm's last bits (spec v0.18; DECISIONS); `unicodedata` done the same day (C-7-81; C-7-15 passes compiled; `test_unicodedata`; DECISIONS): the pin's generated databases copied whole (`tools/unicodedata_source.py`) and unicodedata.c ported to `runtime/src/unicodedata.cpp`, under a prelude for its objects; found with it and fixed: `bytes` and `bytearray`'s own `__len__`, `__iter__`, `__contains__` and `__getitem__` ran a subclass's overrides (C-3-64); the runtime's stops that waited for the Unicode database are done the same day (C-6-21; DECISIONS: `int()`, `float()` and `complex()` of a str beyond ASCII, a format's digits, a % format's errors, `namereplace`, `__slots__` names); the path finder's discovery, `_suggestions` and traceback from its entries done the same day (C-8-13, C-7-82, C-7-83; C-7-02 and C-7-14 pass compiled; DECISIONS: `PathFinder.discover` lists the registry's modules in each entry, `_suggestions` a prelude over suggestions.c's choice with its two limits, `_walk_tb_with_full_positions`, `StackSummary._extract_from_extended_frame_gen`, `clear_frames` and unittest's `TestResult._is_relevant_tb_level` replaced, `tb_next` assignable, so unittest's reports and `assertRaises` work compiled); left from it: traceback's suggestion for a raised AttributeError or NameError reads the innermost frame's locals and stops at `tb_frame`, as do `walk_tb`, `walk_stack` and `capture_locals` (`extract_stack`, `format_stack` and `print_stack` of the running stack done 2026-11-13, C-7-84: the runtime's frame chain through `StackSummary.extract`, and a frame object of the runtime's own where a traceback's entry stood for its frame; DECISIONS); review F21 of the day's last three commits done the same day (RL-430 to RL-444, review log; DECISIONS), and from it, open: the two copies of str's character properties, `unicode_tables.inc`'s ranges behind `unicode.cpp`'s predicates and CPython's type records in `unicodetype_db.inc`, to become one (RL-438: the records answer every predicate; a step of its own with C-7-81's sweep); the METH_O and `_PyArg_CheckPositional` helpers about twenty preludes each type again, to become primitives every prelude has, as `_unpack_keywords` did for the clinic parsers (RL-439); the direct-run blocks of nine test modules that miss tests and two modules without one (`test_bytes`, `test_collections`, `test_complex`, `test_generators`, `test_posix`, `test_review_2026_11_04`, `test_staged_compiled`, `test_thread`, `test_union`; `test_instance_dict`, `test_review_2026_11_09`), to become one runner that calls every test of a module, with a check (RL-443); `list.__iadd__` and `list.__imul__` as attributes (done 2026-11-13, C-3-51); a name of the names table read after the program deleted it, a native module's, a builtin or a module's own first name (done 2026-11-13, C-8-14: each module's names recorded once it is filled; DECISIONS); from the sweep of the manifest's modules made with them (118 modules, 101 with CPython's public surface name for name), the names the runtime does not have yet and stops at: builtins' `locals` (the author decided on 2026-11-14: `locals()`, `vars()` and `dir()` answer for every function, from the frame's record of its locals; DECISIONS; to do, C-8-03 is its case), `aiter`, `anext`, `__build_class__` and `__debug__` (`input` and `breakpoint` done 2026-11-13, C-6-22, and the six names site adds taken out of the names table, as the spec's Builtins row has them: a compiled program answers as `python -S`; DECISIONS), fifty of sys, which the spec's sys surface leaves \[P2+\] or \[X\] (`displayhook`, `breakpointhook` and their originals, `abi_info`, `gettrace`, `getprofile`, `getrefcount`, `path_hooks`, `call_tracing`, `getdlopenflags`, the lazy-import switches, the rest CPython's internals), `zlib.__getattr__`, `_locale._DATE_FMT` and `_ast._is_abstract`; a warning of the runtime's own needs `warnings` in the program's closure (`breakpoint()`'s D-11 warning in a program that imports it nowhere stops at the import; the author decided on 2026-11-14: such a program prints the warning as CPython's C does when it cannot import the module, `show_warning`, with a deviation for what still differs, and `copyreg` stays a stop by name; DECISIONS; to do, a case first); `input()` at a terminal reads the C stdin as CPython's does, so a program that also reads `sys.stdin` there mixes two buffers, as in CPython; the names of the names table the runtime lacks are a list under version control since 2026-11-13 (`tools/missing_names.py`, `conformance/names-baseline.txt`, held by `test_missing_names.py`: 271 names, of which 185 are the dialect's own; C-3-69 and DECISIONS for the first fifty-two off it: the callables' and the singletons' own slots, the docstrings of slot wrappers and of the built-in types' methods, `builtins.__debug__`, `_locale._DATE_FMT`, `zlib.__getattr__`, `_ast._is_abstract`), and what is on it and could come off next: `__getattribute__` of the nine types whose lookup is their own (module, super, type, method, the weak proxies, `types.GenericAlias`, `typing.Union`, the lazy import; the generic thirty-three done the same day), (the iterators' `__length_hint__`, `__reduce__` and `__setstate__` done the same day, C-3-71, with `reversed`, `enumerate`, `zip`, `map`, `filter` and `iter(callable, sentinel)`: `operator.length_hint` and `copy.copy` of a built-in iterator answer; DECISIONS) (`__reduce__` of a range, a slice, `Ellipsis`, `NotImplemented`, a built-in function, a bound method, the descriptors and the method-wrapper done the same day, C-3-72: `copy.copy` of a bound method answers; seen with it and left: an inherited built-in method called with the wrong number of arguments names the receiver's type when the receiver's type has its own `tp_getattro` or the call goes through the bound object (`k.meth.__reduce_ex__()` says `method.__reduce_ex__()` in CPython, `b = range(3).__reduce_ex__; b()` says `range.__reduce_ex__()`), and `object` in the runtime either way) (`~` on a bool with its DeprecationWarning, and the comparisons that `types.SimpleNamespace`, `types.GenericAlias`, `weakref.ref`, `_contextvars.Context` and a ParamSpec's `args` and `kwargs` name and decline, done the same day, C-3-74; left from it: the runtime's other stops at a DeprecationWarning, which can now warn the same way (`__index__`, `__float__` and `__complex__` returning a subclass's instance, `complex()` given a complex as a part, `generator.throw` with three arguments)) (`cell`'s comparisons, hash and repr done the same day, C-3-70, compiled only: the evaluators' own closure cells do not compare as CPython's), (`mappingproxy`'s `|`, `|=`, `reversed()` and comparisons done the same day, C-3-73: `proxy | dict` raised TypeError where CPython merges; with it `UnicodeTranslateError.encoding`, the Unicode errors' members as `PyMember_SetOne` has them and their `__str__` checks, `OrderedDict | frozendict`, and a proxy's hash in all 64 bits; DECISIONS) `ast.AST`'s attribute slots; the operator table (`binop:`, `iop:`, `cmp:` rows of the names table) measured over every type the missing-names program reaches and not a fixed set, so that an operator the runtime lacks stops by name (a mappingproxy's `|` raised TypeError until C-3-73); seen with it: a static method of a built-in type is the builtin itself in the type's dict where CPython's holds a `staticmethod` (`vars(str)["maketrans"]`), and an abstract AST node class instantiated still stops where CPython warns; a slot wrapper's `__doc__` and `__text_signature__` stop by name (`list.__add__.__doc__`); the frame a signal handler is given is to carry its record as traceback's frames do, so that `traceback.print_stack(frame)`, `format_stack(frame)` and `extract_stack(frame)` list the interrupted stack in a handler and `repr(frame)` is CPython's (the author's decision of 2026-11-14: traceback reads it, the program still cannot, E-02 unchanged; a frame walked after its handlers have run stops by name; a case first, compiled leg); a C module's class that allows it (ast's node classes) with a name deleted is not recorded and stops as before; left from it: the prelude's cost per call (a sweep of the whole database is 27 times CPython's time); `pathlib.Path.write_bytes` makes a memoryview (\[P2+\]), which stops C-7-10, and C-7-01 makes one itself (the author decided on 2026-11-14: a minimal memoryview is \[P1\], one-dimensional views of octets over bytes and bytearray, the export count in the model first; DECISIONS; to do, a case first); a program's closure does not reach what a prelude function imports: `object.__getstate__` (and so `__reduce_ex__`, `set.__reduce__`, `bytearray.__reduce__`) imports copyreg as CPython's `_PyType_GetSlotNames` does, which stops by name unless the program imports copy, pickle or copyreg itself, `import queue` stops ("the standard library: step 3b"), and a program that imports `logging` stopped at `sys._getframe` (done 2026-11-12, C-7-78: `findCaller` replaced through `[replaced]`, the call sites from the runtime's frame chain; DECISIONS). Seen with `atexit`: a built-in module imported again after its entry left `sys.modules` is the same module object (CPython's multi-phase modules are made anew); to settle as a second creation or a stop. Seen 2026-11-08: the committed `fact_big.cpp` changes in its synthetic names
  (`_format3` to `_format4215`) when the slice's process has lowered the prelude units first, as the frontend's
  `_counter` is one per process; numbering per module (reset where `_TAKEN` is filled) would make the committed
  output a function of the program alone. Not done yet.

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
  mapping (decision S-1; prototype `pipeline/staging/annotations.py`; done 2026-11-12 by lowering
  the generator's evaluators, whose loads are calls of `annotate_rt.py`, C-3-65); give compiled functions the
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
* Phase 2, decided 2026-11-03 (`docs/DECISIONS.md`): typed code. Static types from the checked
  annotations, exactness guarded where values enter a typed function, Bella's flow analysis
  inside; unboxed `int`/`bool`/`float`, direct calls where the binding provably never changes.
  Until then the compiled program is an exact C++ rendering of CPython's evaluation.
* Phase 2, decided 2026-11-02: the author's glue pass for module globals, an L2-to-L2 pass after
  `resolve-names` giving every global the closed world sees a field in one application object.
  The module dict becomes a view over the fields (insertion order, mutation counter), written in
  `refmodel/objects.py` first as a kind of object for modules; 15 closure modules and every module
  with a dataclass expose their dicts, so migrating on exposure would not pay. Also phase 2: the
  oracle's types in L2 (`Fact.TYPES`, closing the marked gap of task 4) and a pass for the common
  try-and-catch idioms (C++ throws cost about ten times a CPython raise).

## Later

* The author's direction (P-3, 2026-11-02): a whole-program pass that glues the modules' globals
  into one application-wide object with fixed slots, once the closed world and the staging
  snapshot are known. It belongs with the C++ leg's L2; the model comes first, as promoted
  globals with a dict made only when exposed (`refmodel/objects.py`). It is to be detailed with
  the author.

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
