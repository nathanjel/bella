# TODO — Gate 0, first increment

The next gate is the one the reviewer set in round two and refined in round three: executable
artefacts, not prose. Each task below says what exists today, what is left, and what "done"
means. Order matters: 1 constrains everything after it; 4 is where the next review happens.

## 1. Compute the real phase-1 dependency closure on CPython 3.15.2

* Today: `tools/closure.py` computes the closure (dynamic + static, lazy and conditional edges,
  per-API scoping through `[lazy_unsupported]`, optional imports through `[omissions]`);
  `manifest.toml` is closed on CPython **3.13.18** (161 modules), which is not the reference.
* To do: run `uv run make closure` (or in the image), reconcile `manifest.toml` until it is
  closed on 3.15.2, commit `closure.lock.json`, and change the "LAST RECONCILED" line. On
  2026-11-01 it reported 28 open items over 172 modules: `annotationlib`, `_py_warnings`,
  `compression.zstd`, `math.integer`, `pathlib._os`, `_hmac`, `fcntl`, `_missing_stdlib_info`,
  `codeop` reached through `traceback` (excluded), and lazy imports in `pathlib`/`traceback`.
  Teach the tool PEP 810 first: a module-level `lazy import` (`ast.Import.is_lazy`) is a
  first-use edge, not an eager one; today it is followed as eager, which is sound but
  over-approximates. Eleven phase-1 modules use it (`collections`, `contextlib`,
  `dataclasses`, `typing`, `traceback`, `pathlib`, `argparse`, `inspect`, `difflib`,
  `tokenize`, `_colorize`), so lazy-import semantics are phase-1 runtime work.
  Review the six `dynamic_unknown` import sites the lock lists (`encodings`, `inspect`,
  `traceback`, `unittest.loader/main`, `warnings`) and decide: registry entry, adaptation, or
  per-API scope.
* Done when: `make closure` exits 0 on 3.15.2 with `authoritative: true` in the lock, and every
  adaptation named in the manifest has an owner note in `docs/dialect-spec.md` section 7.

## 2. Grow the conformance corpus on 3.15.2

* Today: 24 cases + 1 excluded-construct case under `conformance/cases`, from review findings
  and from CPython 3.15 changes (C-9-07), recorded authoritatively on 3.15.2 (2026-11-01) with
  the harness masks for D-06/D-08.
* To do: cases for the 3.15 additions the phase-1 library depends on or the dialect must
  decide: PEP 810 lazy imports (reification at first use, import errors at first use,
  `__lazy_modules__`, `sys.set_lazy_imports`), PEP 798 unpacking in comprehensions,
  `frozendict` (PEP 814), `sentinel` (PEP 661); add the cases the reviews asked for that are not yet
  here — the seeding-compatibility clause for D-14 (`PYTHONHASHSEED` fixed, compare
  `hash("x")` across runs), `__class__` assignment with CPython's layout rule, `__getattribute__`
  override cost tier, generator `close()`/`throw()`, `except*`, `match`, chained-comparison
  short-circuit with rich comparisons, dict mutation-during-iteration edge (size change only).
  Port the first 100 functions from CPython's `test_descr`, `test_int`, `test_dict`,
  `test_generators` as clauses (PSF-licensed; test-only, never shipped).
* Done when: every [P1] clause in the spec has at least one case, and `make record` is
  authoritative.

## 3. Finish the reference object model and write the real header from it

* Today: `refmodel/objects.py` models promoted fields, dict exposure/replacement/sharing with
  insertion order, descriptors by Python's rules incl. descriptor-class mutation, `__getattr__`,
  class versions with subclass propagation, inline caches with validity predicates, and checks
  every cached read against the generic path; `refmodel.selftest` and the Hypothesis state
  machine agree with CPython on tens of thousands of random operations.
* To do, in the model first (with a conformance case each): `__setattr__`/`__delattr__`/
  `__getattribute__` overrides; `__class__` assignment; dict-mode (runtime-created) classes
  with shapes; setattr caching; `MAY_RECEIVE_COMPUTED_WRITES` as a class fact and the
  `__getattr__` shortcut it licenses; weak references. Then write `runtime/include/bella/object.hpp`
  from the model (start from `docs/drafts/object.hpp.draft` and the two findings in
  `docs/DECISIONS.md`), single-threaded first: plain counters, no atomics, no collector.
* Done when: the C++ object model passes the same stateful test through a thin Python
  binding, and C-3-01..08 pass under the compiled runner.

## 4. One complete compilation path on the three target programs

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
  and the compiled binary, and the generated C++ is committed under `pipeline/examples/out/`.

## 5. Report

* Write `docs/gate0-report.md`: what the closure found, which clauses pass, which the model
  changed in the design, what the toolchain probes say about GCC 16 (`make probes`), and the
  measured compile time of the slice. That document is review round four's input.

## Housekeeping

* ~~`uv lock` and commit `uv.lock`; pin the `gcc:16.x` image tag after `docker pull`.~~ Done
  2026-11-01: `uv.lock`, uv 0.13.6, `gcc:16.2.0` by digest (`docs/DECISIONS.md`, Pins).
* Rename the author line in the Markdown exports if the docs are published.
* The `.github/workflows/ci.yml` builds the image and runs `make check`; turn it on once the
  closure is reconciled (task 1). The image builds and every other target in `make check`
  passes in it (2026-11-01). Until then the closure step is `continue-on-error`.
