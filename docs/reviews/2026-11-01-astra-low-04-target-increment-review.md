# Target Increment Review

Date: 2026-11-01  
Reviewer: astra-low  
Sequence: 04  
Baseline: `b40ef2da9716ec5056421919acb5ae0f008fca79` (review 03)  
Reviewed HEAD: `8b8eb0d627ffc888ab0b500d23df62eb02f19471`

## Assessment

The target programs substantially improve the development plan: they expose real dependency costs, provide repeatable input/output fixtures, and make the first compilation path concrete. Keeping vendored snapshots intact and distinguishing easy from tricky targets are sensible choices. The closure corrections following review 03 are present, with regression tests; I am not carrying those findings forward as unresolved.

The new computed increments are reproducible, but they are not yet a sufficient specification of deliverable scope. There are two conflicts with the phase boundaries and three correctness gaps in the target tooling/oracle below. Resolve those before using a green target check or a clean target closure as evidence that the corresponding milestone is satisfied. None requires abandoning the target-driven approach.

## Verification and limits

| Check | Result |
| --- | --- |
| Starting tree | Clean at the reviewed HEAD |
| `uv run make lint test verify targets-check` | Passed: Ruff, mypy, 74 tests, reference-model self-check, 58/58 reference expectations, six targets under seeds 0 and 1 |
| Target closure recomputation | All six locks reproduced byte for byte using the pinned CPython 3.15.2 |
| Computed increments | Recomputed increment data matches the committed summary: 149 / 6 / 25 manifest modules |
| Known tricky-target errors | Reproduced pycodestyle's three diagnostics: missing `configparser`, missing `optparse`, and the computed import in `optparse.Values.read_module` |
| Negative probes | Reproduced the entry-point omission, acceptance of a non-authoritative recording, and constant-MAC false pass described below |

Review focused on changed first-party tools, harnesses, drivers, policy and decision documents, and the vendored paths relevant to their claims. This is not an exhaustive audit of the approximately 73,000 added lines or a legal review of the vendored libraries. I did not rerun Docker, C++ probes, the integer driver, the performance benchmark, or inspect current CI status. Passing CPython fixtures establishes reproducibility of the oracle; it does not establish compiled support for these libraries.

## Findings

### A4-1 — High: target closure evaluates the entry script as an imported module

Locations: `tools/closure.py:132`, `tools/closure.py:935`, `tools/closure.py:959`, `tools/closure.py:1001`.

`Program.load` uses the driver's stem as its root. Static scanning consequently evaluates `__name__` as that stem, and runtime observation imports the root. The actual target harness executes the driver as a script, where `__name__ == "__main__"`. Required imports inside that guard are therefore classified as dead by both routes of discovery.

Reproduction: create a temporary `review_entry.py` containing:

```python
if __name__ == "__main__":
    import review_required
```

Put an ordinary `review_required.py` beside it, then call `compute_closure` with `Program("review", "easy", "review_entry", (temporary_directory,))`. Using the repository manifest with unrelated replacement declarations cleared, the result contains only `review_entry`, reports no errors, and records the dependency as `cls='dead'`.

The six current drivers keep imports outside their main guards, so this probe does not prove their present locks lack that specific dependency. It proves that a normal subsequent driver edit can silently invalidate the closure gate.

Recommendation: represent entry-script execution explicitly, evaluating its guards with `__name__ == "__main__"` while retaining a stable module identity for paths and policy keys. Keep imported dependencies under their normal names. Add a regression covering a required import inside the entry guard and an ordinary imported module with the same guard. If runtime observation is intended to cover execution as well as import, give it the configured arguments, working directory, and environment; document its coverage separately from the static closure.

### A4-2 — High: the new phase-1b promise requires a feature the dialect must reject

Locations: `docs/DECISIONS.md:212`, `docs/design.md:790`, `docs/dialect-spec.md:56`, `docs/dialect-spec.md:104`, `targets/targets.toml` (`data_tricky_toml`), `targets/vendor/tomlkit/items.py:500`, `targets/vendor/tomlkit/items.py:632`.

The new decision makes the tricky targets part of phase 1b and describes this as a change of order, not scope. Yet tomlkit's selected target explicitly exercises stateful multiple inheritance, which remains P2+ in the normative dialect and must be refused during phase 1.

This is concrete library structure, not merely a pessimistic scorer count: `Integer(Item, _CustomInt)` combines an integer base with `Item`, whose initializer stores `_trivia`; `Integer` adds further state. The target manifest itself calls these subclasses “tier 3 MI.” The pending decisions in `docs/targets.md` section 5 cover metadata, dead excluded calls, and manifest growth, but do not settle this milestone conflict.

Recommendation: explicitly choose whether tomlkit moves to a later phase, the stateful-MI subset moves into phase 1 with a defined implementation/test obligation, or an approved adaptation removes that requirement. Record that choice before presenting 1b as only six additional modules plus the two pending stdlib additions. Module counts do not measure the extra object-model capability.

### A4-3 — Medium: the computed phase-1a inventory contradicts the Unicode decision

Locations: `docs/DECISIONS.md:217`, `docs/dialect-spec.md:139`, `docs/targets.md:266`, `manifest.toml:89`, `targets/closure-summary.json` (`increments.1a.list.unicodedata`).

The author explicitly kept `unicodedata` P2+ and lowered the slug target's requirements to avoid pulling it forward. Nevertheless, the computed 1a inventory includes it as a mapped module. For example, the token target's lock reaches it through `urllib.parse:lazy:514`. The target analysis simultaneously says no target uses it and describes the Unicode tables as a shared phase-1 cost.

The mapped manifest entry predates this increment; the new defect is treating the generated closure as the definitive phase schedule without reconciling that entry with the newly reaffirmed decision. Dropping direct use from the slug driver does not remove a transitive dependency from a conservative module closure.

Recommendation: choose and encode one interpretation. If its relevant APIs remain unsupported, declare the applicable adaptations/refusals and make the closure reflect them. If an internal subset is required while public access remains P2+, specify the subset and enforce that boundary. If the full module is actually needed in 1a, obtain an explicit scope revision. Regenerate the inventory and cost discussion after that choice.

### A4-4 — Medium: target checking ignores the recording's authority and Python version

Location: `targets/run_targets.py:96`.

`record` carefully writes `authoritative` and `python` metadata, including a false authority marker for `--allow-unpinned`. `check` reads the metadata but consults only `exit`. Consequently a development recording, or a stale recording after changing the reference pin, can become the successful comparison oracle.

Reproduction: copy the slug target's three expected files to a temporary directory, change its metadata to `{"exit": 0, "python": "0.0.0", "authoritative": false}`, and point the harness at that directory and target. `check` passes both seeds and returns zero. No tracked fixture was modified in this probe.

Recommendation: require `authoritative is True` and a recorded Python version equal to the configured reference pin before comparison. An explicit development override can permit exploratory comparisons, but should not satisfy the release/CI gate. Add negative tests for both metadata failures.

### A4-5 — Medium: the token target accepts a completely incorrect signing algorithm

Location: `targets/drivers/service_easy_tokens.py:81`.

The driver substitutes a token-length placeholder for each deterministic signed token. Later requests verify tokens produced by the same implementation. This tests self-consistency and expiry behavior, but hides incorrect token serialization or signatures of the same length from the CPython comparison.

Reproduction on the pinned interpreter: before executing the driver, replace `itsdangerous.signer.HMACAlgorithm.get_signature` with a function returning `b"X" * 20` for every key and message. Running the configured request fixture still produces output exactly equal to `expected/service_easy_tokens.out`, including its tamper and expiry results. The signing routine no longer computes a MAC at all.

Recommendation: record the full token bytes/string; the secret and clock are already fixed test fixtures. Also verify at least one fixed CPython-produced token, and include a payload/signature mutation that retains the original token shape. This establishes compatibility across implementations instead of relying entirely on sign-and-verify round trips. The primitive digest conformance tests remain useful, but do not replace this integration check.

## Additional review notes

* **Oracle fidelity:** `run_one` captures text with universal-newline conversion and `errors="replace"`. It cannot enforce byte-identical stdout/stderr: CRLF becomes LF and malformed UTF-8 is replaced. If exact stream bytes are the contract, capture and compare bytes. A subprocess timeout would also keep a hung future compiled runner from blocking the gate indefinitely.
* **Regex implementation decision:** `docs/targets.md:254` describes a C++ port of `_sre` and explicitly rules out a regex-library swap; `docs/dialect-spec.md:139` still says `re` maps onto PCRE2. Reconcile this before estimating or implementing the matcher. These imply materially different work.
* **D-5 and D-20:** runtime annotation formats now have an explicit decision, and recording both ordinary and deviation-simulated CPython traces is a useful improvement. Keep the annotation implementation/staging obligations visible; the broader corpus is a smoke-test foundation rather than proof of every normative sentence. The target harness's ordinary check does not itself rerun the documented phase-1 omission simulation, so automating that target configuration would preserve the reported manual evidence against future changes.
* **Planning:** 71,219 compiled stdlib lines in the easy closure is valuable evidence that “easy” describes the workload, not a small compiler implementation. Retain the narrow first executable path and the staging/lifetime prerequisites. Separate the conservative module inventory from reachable APIs, required language features, and actual runtime implementation cost.
* **Candidate analysis and measurements:** the scorer appropriately calls itself a reading aid, and the Mandelbrot report identifies the toy pipeline, fixed-point arithmetic, and benchmark limits. Keep those qualifications. Neither AST counts nor the toy arithmetic speedup validates support or performance for the newly selected libraries.

Suggested order: correct entry-point closure semantics and settle the two phase-boundary conflicts, then strengthen the recording and token oracles before relying on compiled target results. Findings use local A4 identifiers for subsequent triage in the review log; this review does not change implementation policy or close issues on the author's behalf.
