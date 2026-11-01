# Conformance corpus

The dialect specification is the test plan: every normative sentence maps to a clause, and a
clause is a program that runs unchanged under CPython 3.15.2 and under Bella. `harness.py`
records the observable trace under CPython and compares a Bella run against it.

```
python3 conformance/harness.py list
python3 conformance/harness.py record                         # on the pinned CPython (Docker)
python3 conformance/harness.py record --allow-unpinned        # elsewhere: non-authoritative
python3 conformance/harness.py check --runner "python3 {case}"      # tautological today
python3 conformance/harness.py check --runner "bella run {case}"    # once the compiler exists
```

## Writing a case

* File name `C-<spec section>-<nn>_<slug>.py`; the header lines `clause`, `spec`, `status`
  (`P1`, `P2+` or `X`), `source`, and optionally `expect`, `mask` and `deviation` are read by
  the harness. Fixtures a case imports (`lazy_noisy.py`, `cycpkg/`) start with a lower-case
  letter, so the harness does not take them for cases.
* The case is a dialect program: annotated, ruff-clean under the dialect rules, and clean
  under strict mypy with no explicit `Any` (`make lint` checks all of `conformance/cases`, the
  input contract of design section 2). A deliberate dynamic pattern carries a targeted
  `# type: ignore[code]  # reason`, never a blanket ignore.
* Print structured observables: `type(exc).__name__`, `exc.args`, `exc.name`, `.value`, list
  items, `is` results. Never print `str(exc)` of a built-in exception the runtime raised
  (D-08 exempts that wording), and never print `id()` values or addresses (D-01, D-02).
* Keep it deterministic: the harness sets `PYTHONHASHSEED=0` and UTF-8 mode; use `gc.collect()`
  explicitly when a cycle must be collected at a known point.
* Keep it independent of the environment: no clock, no local time zone, no absolute paths, no
  terminal width (set `COLUMNS` if a module reads it). New cases are run under two different
  `TZ`, `LANG` and `COLUMNS` settings before they are recorded.
* An `X` case (status `X`, `expect: E-xx`) is one the compiler must reject; CPython runs it,
  so no expectation is recorded.
* A `P2+` case is recorded and verified on CPython like a `P1` case (it is what the milestone
  must reach), but `check` passes it only when the runner refuses it: a non-zero exit with the
  marker `[P2+]` in stderr, plus the `# expect:` text if the case gives one (spec section 10:
  a \[P2+\] clause must fail with the milestone-naming error, never pass by accident). So the
  compiler's milestone refusals carry `[P2+]` in their message.
* A case with `# deviation: D-nn` differs from CPython by a registered deviation. It has a
  second expectation, `expected/<case>.D-nn.json`, recorded on CPython made to show the
  deviation, and `check` compares the runner with that one. Only D-20 can be shown that way
  today: `conformance/simulate/sitecustomize.py` blocks the manifest's omissions and the codecs
  outside the phase-1 set at start-up. `record` refuses a deviation case whose two traces are
  equal.

## What the harness compares

stdout byte for byte; stderr after the D-06 mask (frames reduced to `File "name.py", line N`)
and the D-08 mask (the message of a built-in exception on a `Type: message` line); exit code.
The masks only touch what the register declares exempt, so a case that prints `exc.args`
itself is compared exactly.

## Status of the recorded expectations

`expected/*.json` carries `recorded_with` and `authoritative` (and `deviation` for a deviation
trace). Expectations recorded on any Python other than the pinned 3.15.2 are kept only as
examples of the format; `check` skips them unless `--allow-unpinned` is given. The corpus was
recorded on the pinned 3.15.2 on 2026-11-01: 57 cases (53 \[P1\], 4 \[P2+\]) and 2 `X` cases;
`make verify` reproduces 58 expectations (one deviation trace).

## Provenance

Every case names its source: a review-round finding, or a spec section. The cases in this
first batch come from review rounds one to three (docs/reviews/) and were verified under
CPython before being added.
