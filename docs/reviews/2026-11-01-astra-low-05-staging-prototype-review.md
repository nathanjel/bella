# Staging Prototype Review

Date: 2026-11-01  
Reviewer: astra-low  
Sequence: 05  
Reviewed range: `19316ba..b838bc5`  
Reviewed HEAD: `b838bc517f88b603b04691e657d78897490dca98`  
Entry point: `docs/staging.md`

## Assessment

The prototype makes useful progress on the hardest part of staging: preserving runtime definition-time effects while replacing dynamic compilation. Running unchanged library code against staged generated functions is a credible direction, and the explicit distinction between the replay model and the future compiler is welcome. The new definition-time cases, runtime annotation investigation, and discovery of the datetime deviation are valuable evidence.

I support continuing with staged texts and probes, but would not yet treat the prototype's soundness or input-accounting claims as established. Two probes produce a successful replay with output different from CPython; a third shows that the recorded input inventory is incomplete even for the operations it claims to observe. Two further defects affect the evidence gate and annotation exceptions. These are implementation defects, separate from the openly documented limitations and author decisions.

## Verification

The working tree started clean at the requested endpoint. I reviewed the staging implementation, annotation shim replacements, new cases, harness changes, and changed design/decision text. Vendored CPython annotationlib machinery was examined around the modified paths rather than audited line by line.

`uv run make staging-check` passed: deterministic JSON dry runs for the stdlib and three staging cases under seeds 0 and 1; 58/58 P1 cases; C-3-22's FORWARDREF refusal; and the three phase-1 targets under both mechanisms. The reported 23 namedtuple texts, 15 dataclass texts, and 102 annotation entries reproduced. This verifies the current positive fixtures, not the stronger universal claims below.

`uv run make lint test verify` also passed: Ruff and all mypy checks, 89 tests, the reference-model self-check over 3,000 operations, and 121/121 reference expectations including phase-1 configuration checks.

The negative probes used temporary modules and fixtures, without modifying tracked implementation or expected-output files. I did not run Docker or inspect CI, and did not rerun the C++ checks: this range adds a CPython replay model rather than a C++ implementation.

## Findings

### A5-1 — High: replay keys omit the compilation mode and can execute the wrong code

Locations: `pipeline/staging/dryrun.py:288`; `pipeline/staging/boot/sitecustomize.py:71`.

The recorder distinguishes `(site, kind, text)`, but the compiled artifact and runtime lookup reduce this to `(site, text)`. The `kind` argument to `_code_for` is used only for diagnostics. An `eval` therefore accepts code compiled in `exec` mode, and vice versa, if source text and reported site match. A source line is not necessarily a unique operation; choosing between the two builtins at one call expression suffices.

Reproduction: include this helper in a temporary program lock as a program module:

```python
def generated(evaluate):
    return (eval if evaluate else exec)("1 + 1")

generated(False)
```

The entry script imports the helper and, under its main guard, prints `helper.generated(True)`. CPython prints `2`. The staged runner exits successfully but prints `None`, because it executes the staged `exec` code object through `eval`. This is a library-generation-path probe of the advertised staging contract, not a request to admit unrestricted user `eval` to the dialect.

Recommendation: retain the operation/mode in the artifact and lookup key, validate the compilation context, and reject a mode that was not staged. A regression should exercise the same text and site with both operations. Full-text equality alone does not establish semantic equality of compiled code.

### A5-2 — High: imported program source changes do not invalidate annotation artifacts

Location: `pipeline/staging/run.py:80`.

`program_artefact` hashes the entry script, staging implementation inputs, the lock file, and the PYTHONPATH string. It imports the lock's program modules but does not hash their source contents. Changing an imported module without changing its dependency inventory consequently reuses stale annotations and staged texts. Unlike an unstaged-text miss, stale annotation answers can silently be wrong.

Reproduction: a helper defines `def f(x: int): pass`; the unchanged entry prints `annotationlib.get_annotations(helper.f, format=Format.STRING)`. A minimal program lock includes the helper. The first replay correctly prints `{'x': 'int'}`. Change only the helper's annotation to `bytes`, leaving its location, qualname, and first line unchanged. CPython prints `{'x': 'bytes'}`, while the next replay still succeeds with `{'x': 'int'}`. The runtime probe evaluates the new annotation, but the shim returns the old table.

Recommendation: make every source contributing generated code or annotation tables an artifact dependency, and hash its contents. Include transitively imported program sources, not just the module names or closure lock. Add an incremental rebuild test that changes an imported annotation without changing the import graph. The compiler's eventual build system needs this dependency contract too.

### A5-3 — High: input filtering suppresses reads performed by imported module bodies

Locations: `pipeline/staging/dryrun.py:121`, `pipeline/staging/dryrun.py:130`; `docs/staging.md` sections 2 and 4.

`_by_import_system` searches the entire ancestor stack for an importlib frame. A module body being executed by the importer naturally has such a frame beneath it. Its own file reads are therefore discarded as though they were the loader's reads of Python source. The same filtering affects the audited directory/process/socket events. Environment accesses use another hook and can still appear, which makes the incomplete inventory look plausible.

Reproduction: import a temporary entry module whose body opens an ordinary data file and reads its contents. The dry run's JSON reports `"inputs": {}`. The file is not Python source or a loader operation.

Recommendation: distinguish loader-owned I/O from I/O initiated within the active module body; an arbitrary ancestor importer is insufficient. Add tests for a direct body read, a read through a helper, directory enumeration, and genuine loader reads that should be excluded. Recompute the stdlib input inventory after fixing the recorder. The current evidence does not substantiate the statement that module bodies read only the subprocess environment variable.

The disclosed absence of clock/random tracking is a separate limitation. This finding concerns a category the prototype explicitly claims to record. It also matters to S-3: do not weaken the input rule using this inventory as evidence that definition-time external inputs are negligible.

### A5-4 — Medium: the corpus evidence gate can accept a crashed harness

Location: `pipeline/staging/check.py:49`.

`corpus()` never checks the P1 harness subprocess's return code. It collects stdout lines beginning with `FAIL` and returns those as the failures. If the harness prints a successful case and then crashes, stderr can contain a traceback and the process can exit nonzero without producing a `FAIL` line. The evidence gate then sees no P1 failure.

Reproduction at the subprocess boundary: supply a completed result with exit code 1, stdout `PASS earlier_case\n`, and stderr containing a traceback, followed by a valid P2 refusal result. `corpus()` returns `[]`. This was a simulated harness-failure probe; the actual harness run in this review completed successfully.

Recommendation: any nonzero harness exit must fail the evidence gate, with stderr retained in the report. Handle empty output explicitly too; today it instead causes an indexing error. Add a regression for a partial-output crash, not just a normal `FAIL` case. For comparison-only runs, distinguish an expected semantic refusal from a broken test process.

### A5-5 — Medium: annotation fallback exceptions are reconstructed from their display text

Locations: `pipeline/staging/annotations.py:69`; `pipeline/staging/boot/sitecustomize.py:125`.

The table serializes exceptions as `[class_name, str(exc)]`; replay constructs `cls(recorded_message)`. An exception's display string is not its constructor arguments. This changes observable exception data, even for ordinary builtins.

Reproduction:

```python
import annotationlib

def f(x: {}["missing"]):
    pass

if __name__ == "__main__":
    try:
        annotationlib.get_annotations(f, format=annotationlib.Format.STRING)
    except KeyError as exc:
        print(exc.args)
```

CPython prints `('missing',)`. Replay prints `("'missing'",)`. Both exit successfully. The difference is in `args`, independent of policies that mask exception wording. Structured exceptions with additional fields need more than a single message as well.

Recommendation: preserve a defined, reconstructible exception representation, including arguments and supported structured fields; refuse cases that cannot be represented faithfully. Alternatively, S-1's runtime fallback mechanism can remove the need to reconstruct these annotation exceptions. Add a case that observes exception arguments, beyond the existing ZeroDivisionError type check.

## Mechanism comparison and open questions

**S-5 — staged texts with probes:** I favor this direction provisionally. It reuses the pinned library's generator and preserves the runtime calls that produce effects. However, the comparison is between a functioning staged implementation and an intentionally partial intrinsic implementation: the latter implements namedtuple and no dataclass generator. Its five failing cases do not establish that compiler intrinsics cannot satisfy them. Describe the result as implementation coverage and maintenance cost, rather than a semantic defeat of intrinsics. Likewise, “per CPython version: nothing” is too strong: site identities include source line numbers, the prototype has a hard-coded namedtuple site, and the annotation machinery uses private CPython helpers. The pin and rerun protocol are still necessary.

**S-1 — annotation fallback entry point:** option 2 is the better long-term direction. A compiler-generated evaluator parameterized by globals and cells has a clearer semantic contract than a collection of special-case precomputed answers and reconstructed exceptions. First demonstrate it for unresolved names, closure cells, class scope, side effects, and exceptions, then make the scope change explicit. The prototype's discovery of self-reference refusals is useful evidence for revisiting D-5; it is not itself an implementation of the broader behavior. Keep `ForwardRef.evaluate` of arbitrary source text separate from evaluating compiler-known annotation expressions.

**S-2 — runtime signatures:** I lean toward a minimal signature record now, with an explicitly bounded `inspect.signature` surface. The report shows that an ordinary phase-1 dataclass reaches this requirement, so deferring the entire issue until the tricky targets no longer matches the dependency evidence. If the author chooses refusal instead, the generated-docstring limitation needs a precise normative boundary, a negative case, and a diagnostic; avoiding it in positive fixtures is not enough. Broad introspection support is not required to provide parameter names, kinds, defaults, and the annotation access needed by this path.

**S-3 — runtime-created classes and external inputs:** keep text selection and layout selection as separate contracts. Exact generated text, under the right compilation context, can safely identify executable code; it does not prove a class's bases, descriptors, fields, or MRO are invariant. The model correctly disclaims that latter proof. Do not mark the layout-staging obligation complete when accepting this model in place of `eval1`. Also describe acceptance in terms of whether the required artifact exists: a dataclass inside a function is not inevitably refused if another definition staged identical generated text. If the phase policy rejects such constructs regardless of hits, that needs independent enforcement. Fix A5-1 through A5-3 before using the prototype to justify narrowing the input rule.

**S-4 — gettext plurals:** temporary refusal is reasonable for the selected targets, provided the specific affected API/path is registered and diagnosed. Keep a negative fixture using an actual Plural-Forms catalogue so that the promised refusal remains testable. An interpreter for the already-parsed expression is a plausible later adaptation; it need not become a general dynamic compiler.

**D-20 and the expanded verification:** running undeclared-deviation P1 cases under the phase-1 configuration is a good improvement and caught a real issue. The new wording accepting all differences between pure-Python datetime and its C accelerator is broader than the demonstrated repr difference. Prefer enumerated observed differences, or explicitly identify that broader acceptance as a policy choice with limits. One repr case cannot establish equivalence of the rest of the datetime API.

## Disposition

Continue the prototype, but fix the successful wrong-result cases and evidence accounting before declaring its contract settled. The current fixtures support a narrower conclusion: the selected programs reproduce their expected behavior under this model. The negative probes show that the implementation does not yet guarantee that every accepted replay does so.

Findings use local A5 identifiers for triage. This review neither changes author decisions nor resolves review-log entries on the author's behalf.
