# Conformance corpus

The dialect specification is the test plan: every normative sentence maps to a clause, and a
clause is a program that runs unchanged under CPython 3.14.8 and under Bella. `harness.py`
records the observable trace under CPython and compares a Bella run against it.

```
python3 conformance/harness.py list
python3 conformance/harness.py record                         # on the pinned CPython (Docker)
python3 conformance/harness.py record --allow-unpinned        # elsewhere: non-authoritative
python3 conformance/harness.py check --runner "python3 {case}"      # tautological today
python3 conformance/harness.py check --runner "bella run {case}"    # once the compiler exists
```

## Writing a case

* File name `C-<spec section>-<nn>_<slug>.py`; the header lines `clause`, `spec`, `status`,
  `source` (and `expect` for `X` cases) are read by the harness.
* The case is a dialect program: annotated, ruff-clean under the dialect rules, no `eval`.
* Print structured observables: `type(exc).__name__`, `exc.args`, `exc.name`, `.value`, list
  items, `is` results. Never print `str(exc)` of a built-in exception the runtime raised
  (D-08 exempts that wording), and never print `id()` values or addresses (D-01, D-02).
* Keep it deterministic: the harness sets `PYTHONHASHSEED=0` and UTF-8 mode; use `gc.collect()`
  explicitly when a cycle must be collected at a known point.
* An `X` case (status `X`, `expect: E-xx`) is one the compiler must reject; CPython runs it,
  so no expectation is recorded.

## What the harness compares

stdout byte for byte; stderr after the D-06 mask (frames reduced to `File "name.py", line N`)
and the D-08 mask (the message of a built-in exception on a `Type: message` line); exit code.
The masks only touch what the register declares exempt, so a case that prints `exc.args`
itself is compared exactly.

## Status of the recorded expectations

`expected/*.json` carries `recorded_with` and `authoritative`. Expectations recorded on any
Python other than the pinned 3.14.8 are kept only as examples of the format; `check` skips them
unless `--allow-unpinned` is given. Gate 0 re-records the corpus in the Docker image.

## Provenance

Every case names its source: a review-round finding, or a spec section. The cases in this
first batch come from review rounds one to three (docs/reviews/) and were verified under
CPython before being added.
