# Working in the Bella repository

Bella is a Python → C++26 compiler with exact CPython 3.14.8 semantics. This file is for any
agent or person working here. It is short on purpose; the documents it points to are long.

## Authority

1. `docs/dialect-spec.md` decides what a compiled program must do. On semantics it wins.
2. `docs/design.md` decides how the compiler and runtime are built (sections 13-15 hold the
   review resolutions; where earlier sections disagree, 13-15 win).
3. `docs/DECISIONS.md` lists every decision taken; do not reopen one silently. If a decision
   turns out wrong, say so in the PR and record the change there and in the living document.
4. `docs/feasibility-study.md` is history.

The reference implementation is CPython **3.14.8**. "What does CPython do?" is answered by
running it, not by recollection; the conformance harness exists for that.

## Rules that are not negotiable

* **Never fix a mismatch by editing an expectation.** `conformance/expected/*.json` is recorded
  from CPython. If Bella differs, either Bella is wrong or the difference goes into
  `docs/deviations.toml` with an id, a rationale and a lint rule — never silently.
* **Never approximate.** A construct the pipeline cannot handle raises `Unsupported` naming it
  (see `pipeline/l1/grammar.py`). A runtime facility that does not exist throws
  `bella::NotImplemented` (see `runtime/include/bella/int.hpp`). A slow correct path is fine; a
  fast wrong path is not.
* **A conformance case first.** A new runtime mechanism or pass starts with a case under
  `conformance/cases` (or a reference-model test under `refmodel/tests`) that CPython passes,
  then the implementation. Cases print structured observables, never `str(exc)` of a built-in
  exception, never addresses.
* **Every pass has a `PassSpec`** with its levels, facts, obligations and proof status
  (`pipeline/passes/spec.py`). The manager refuses incomplete records. A pass that removes a
  check emits a certificate the validator can refute (`validation/`).
* **The model before the header.** Changes to attribute lookup, caches, dictionaries or
  lifetimes go into `refmodel/objects.py` first and must keep `python3 -m refmodel.selftest`
  green on several seeds; `runtime/include/bella/object.hpp` is written from the model.
* **Pins are pins.** CPython 3.14.8, the GCC 16 image, `uv.lock`, the grammar at 3.14.
  `--allow-unpinned` runs are for development and are marked non-authoritative in their output.
* **Licences.** Anything linked into a shipped artefact is MIT, BSD or ISC. Tools and test-only
  dependencies may differ (Hypothesis MPL-2.0, Lean 4, GCC). Codon, Boost, Abseil, folly,
  stdexec, Eigen, GMP, Shed Skin are out (study, section 12).
* **Readable output.** Generated C++ keeps Python identifiers and is committed
  (`pipeline/examples/out/`). If a reviewer could not follow it, it is wrong.

## Commands

```
make test               pytest (if installed) + refmodel self-check
make closure            phase-1 closure vs manifest.toml  (pinned interpreter; --allow-unpinned elsewhere)
make record             conformance expectations under the pinned CPython
make check-conformance  RUNNER="python3 {case}" today; the compiled runner later
make slice              CPython == eval1 == C++ on pipeline/examples
make int-test           int.hpp vs CPython with UBSan
make probes             C++26 feature report for the toolchain in use
make check              all of the above (CI)
```

Without pytest, every test module runs directly: `python3 -m refmodel.tests.test_cases`,
`python3 -m pipeline.tests.test_frontend_eval1`, `python3 -m validation.tests.test_certificates`,
`python3 tools/tests/test_closure.py`.

## Conventions

* Python ≥ 3.13 for the compiler's own code, typed, `ruff` clean (`pyproject.toml`); the dialect
  rules (annotations everywhere, no `Any`, no `eval`) apply to `conformance/cases` and
  `pipeline/examples`, which are dialect programs.
* C++26 on GCC only; `__int128` and `__builtin_*_overflow` are allowed (GCC-only project).
* Names: `bella.toml` (project policy), `bella-lint` (the dialect linter, not written yet),
  `bella-plugin-<name>` (intent plugins). The spec calls deviations D-nn, exclusions E-nn,
  conformance clauses C-<section>-<nn>.
* Commit messages name the clause or finding they address (`C-3-05`, `round-3/finding-2`).

## Where to start

`TODO.md` lists Gate 0's first increment in dependency order. Task 1 (the closure on 3.14.8)
needs the Docker image; tasks 2-4 can start on a developer machine with `--allow-unpinned`.
