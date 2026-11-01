# Staging Revision Review

Date: 2026-11-02  
Reviewer: astra-low  
Sequence: 06  
Reviewed range: `b838bc5..d0bec20`  
Reviewed HEAD: `d0bec205cbb5bbe63d5426ed6ecc4e902eae70bd`

## Assessment

The revision addresses the five findings from review 05 with implementation changes and regression coverage. In particular, operation-specific replay keys, imported-source invalidation, input accounting, and subprocess failure handling are materially better. Replacing annotation answer tables with generated evaluators is a stronger implementation of S-1. The author decisions are now reflected in tests, and the documents distinguish executable-code staging from the still-open layout obligation.

There is one new successful wrong-result replay: two distinct type-alias evaluators can receive the same artifact identity and silently overwrite one another. I also reproduced three gaps where otherwise supported source is rejected or fails during staging. Fix the identity collision before treating an accepted replay as correctness evidence; the other findings concern faithful execution of the dry run and coverage of the newly accepted annotation surface.

I am not reopening S-2 through S-5. Their implementation and scope boundaries are reviewed below against the decisions actually taken.

## Verification

The tree started clean at the requested endpoint. Review covered the changed staging generator, recorder, replay, cache validation, shim changes, closure scanner, new cases, and decision/specification changes. Probes used temporary files and the pinned CPython 3.15.2; no tracked implementation or oracle files were edited.

`uv run make lint test verify staging-check` passed: Ruff, all mypy checks, 98 tests, the 3,000-operation reference-model self-check, 127/127 reference expectations, and all staging evidence checks. Staging reproduced the 60 P1 cases, the selected P2 refusals, and the three phase-1 targets under both mechanisms. The independent standard-library closure recomputation to `/tmp/bella-review6-closure.json` matched the committed lock byte for byte.

No Docker build, CI inspection, C++ validation, or exhaustive audit of the copied annotationlib module was performed. The positive cases establish coverage of those fixtures, not all annotation expressions or compilation contexts.

## Findings

### A6-1 — High: two generated evaluators can share a key and silently overwrite each other

Locations: `pipeline/staging/annotations.py:83`, `pipeline/staging/annotations.py:469`, `pipeline/staging/annotations.py:491`; runtime lookup in `pipeline/staging/boot/sitecustomize.py` (`_entry_point`).

Evaluator identity is `(real source path, co_qualname, co_firstlineno)`. That is not unique for compiler-generated PEP 695 evaluate functions. Two aliases with the same name on the same source line have different code but the same key. Both individually pass the build-time checks, after which the later dictionary assignment replaces the earlier evaluator. Runtime lookup then attaches the wrong evaluator to the still-live earlier alias.

Reproduction:

```python
import annotationlib

type A = int; Old = A; type A = str

if __name__ == "__main__":
    print(annotationlib.call_evaluate_function(
        Old.evaluate_value, annotationlib.Format.STRING))
    print(annotationlib.call_evaluate_function(
        A.evaluate_value, annotationlib.Format.STRING))
```

CPython prints `int` then `str`. Replay prints `str` twice and exits zero. Calling `evaluators_for_source` directly yields one entry keyed as `...::A::3` for the example's alias line, with no declined evaluator. In the minimal two-line generator probe, the corresponding key was `...::A::1`.

Recommendation: assign an identity unique to each source definition/code object and carry it through artifact generation and runtime attachment. At minimum, detect collisions and fail rather than silently replacing an entry. A source span or an appropriate stable code discriminator can distinguish this case; the eventual compiler can attach the evaluator directly. Add an end-to-end regression retaining both aliases, not only an equality check on each generated evaluator in isolation.

### A6-2 — Medium: dry-run exec/eval still inherit the recorder's future flags

Locations: `pipeline/staging/dryrun.py:89`, `pipeline/staging/dryrun.py:98`.

The recorder captures the original caller's future flags, and the artifact is later compiled with them. However, the dry run executes string source by calling `_REAL_EXEC` or `_REAL_EVAL` from inside `dryrun.py`, which itself imports `__future__.annotations`. The builtins inherit that wrapper's compilation context rather than the program caller's. Thus the definition-time run that discovers subsequent generated texts can differ from CPython even though artifact compilation uses the right recorded flags. The new `_compile` wrapper explicitly handles inherited flags; the exec/eval wrappers do not.

Reproduction in a script without a future import:

```python
from collections import namedtuple

ns = {}
exec("def f(x: Missing): pass", ns)
try:
    ns["f"].__annotations__
    fields = "present"
except NameError:
    fields = "absent"
T = namedtuple("T", fields)

if __name__ == "__main__":
    print(T(1))
```

CPython prints `T(absent=1)`. During staging, the wrapper makes the generated function's annotation a string, so it stages the `present` namedtuple text. During replay the correctly compiled generated function raises NameError, selects `absent`, and the program stops with exit 70 at `collections:namedtuple` because that text was never staged.

This is a deterministic module body whose required generated text the dry run should see, not the intentional restriction on definitions reached only at runtime. It is a retained wrapper bug exposed by the strengthened compilation-context claim.

Recommendation: execute build-time string code with the original caller's compilation context explicitly, while preserving the builtin's source handling and namespace semantics. Test both callers with and without future annotations, and make subsequent generation depend on the annotation result so that the test covers discovery as well as final execution.

### A6-3 — Medium: source handling differs from the builtins being staged

Locations: `pipeline/staging/dryrun.py:75`, `pipeline/staging/dryrun.py:114`, `pipeline/staging/dryrun.py:382`; `pipeline/staging/boot/sitecustomize.py:88`, `pipeline/staging/boot/sitecustomize.py:146`.

The implementation treats source as UTF-8-decoded text and compiles eval strings directly. Those are not equivalent to the accepted inputs and preprocessing of CPython's builtins.

Two independent probes:

* `value = eval("  1 + 2")`, followed by printing `value` under the main guard: CPython prints `3`; staging fails with `IndentationError` when constructing the binary artifact. `eval` accepts the leading spaces, while the later direct `compile(..., "eval")` does not apply the same preprocessing.
* `value = eval(b'# coding: latin-1\n"\xe9"')`, followed by printing `value`: CPython prints `é`; replay raises `UnicodeDecodeError` in the unconditional UTF-8 decode. The source bytes contain an explicit encoding declaration. The same decode assumption exists in the new staged-compile path.

These probes exercise the stated support for staged library-generated source; they do not propose widening the dialect to unrestricted runtime compilation. They fail even when the source is available during module initialization.

Recommendation: preserve source kind and apply the matching builtin's decoding/preprocessing rules consistently in recording, artifact construction, and replay lookup. Keep original source identity separate from any normalized compilation input. Add whitespace and encoding-cookie regressions alongside the compilation-mode regression.

### A6-4 — Medium: private attribute names are not mangled in annotation evaluators

Locations: `pipeline/staging/annotations.py:326`, `pipeline/staging/annotations.py:350`.

The rewriter mangles `ast.Name.id`, but does not apply class-private mangling to `ast.Attribute.attr`. The generated standalone function therefore uses `C.__v` where CPython's annotation code uses `C._C__v`. The build-time differential check correctly detects the mismatch and declines the evaluator, but runtime reports a P2 refusal for an ordinary compiler-generated annotation that the new S-1 scope promises to support.

Reproduction:

```python
import annotationlib

class C:
    __v = int
    def f(x: C.__v, y: Missing):
        pass

if __name__ == "__main__":
    ann = annotationlib.get_annotations(C.f, format=annotationlib.Format.FORWARDREF)
    print(ann["x"] is int, ann["y"].__forward_arg__)
```

The missing second name ensures the fallback is exercised rather than returning already-resolved VALUE annotations. CPython returns the integer type for `x` and a ForwardRef for `Missing`; replay exits 70. Direct generator inspection reports `MISMATCH STRING`, comparing `C._C__v` with `C.__v`.

Recommendation: implement private-name mangling for attribute identifiers and other applicable identifier positions, preserving the lexical class context. Add a private-attribute case with an unresolved companion annotation. The existing private bare-name test does not cover attribute syntax. The fail-closed check is working here; the gap is generator coverage and the misleading runtime attribution to a non-generated function.

## Decision and implementation notes

* **S-1 validation:** keeping a generated evaluator only after static and differential checks is useful defense. A6-4 demonstrates that it catches a real translation error. A6-1 demonstrates a distinct obligation: validating each evaluator does not validate the mapping from live functions to evaluators. Test identity/attachment independently of expression translation. The current dynamic validation uses STRING and the second FORWARDREF environment; retain runtime tests with real globals and live closure cells for the first FORWARDREF run as well.
* **S-2:** the selected policy now has a negative conformance case and a runtime interception point. That is an improvement over merely avoiding generated dataclass docstrings in fixtures. The metadata work remains deferred by the author's explicit choice; this review does not recommend silently undoing it.
* **S-3:** the documents correctly retain layout staging as open work and describe runtime text acceptance by artifact availability rather than by where a class definition appears. A6-2 shows why an accurate dry-run context still matters even when a miss safely refuses.
* **S-4 refusal placement:** `[refused]` is currently checked when exec/eval/compile is reached, rather than on entry to the named function. For example, `gettext.c2py("bad_token")` raises a catchable ValueError and the replay continues if it is caught, although the manifest/documentation describes a function-level refusal. Decide whether malformed-input paths are intentionally preserved; otherwise enforce the refusal at the function boundary. The valid Plural-Forms catalogue case does exercise the promised refusal.
* **Closure work:** scanning Python shim source and admitting `_ast_unparse` address a concrete dependency of the new fallback. Keep the module count and source-provenance descriptions synchronized with the generated lock. In particular, the scanner uses the replacement shim for edges but leaves `ModuleInfo.path` pointing at the original CPython module; a consumer interpreting that path as the scanned source would be misled. Distinguish provider/source metadata if the lock is used to drive compilation or source-based invalidation.
* **Documentation:** `docs/staging.md` section 4 still says any code object and any compile stop the program, while the implementation now accepts staged compile outcomes and their code objects. Update that sentence and the replay module header to state the actual boundary. The narrowed D-20 wording and the qualified mechanism comparison are appropriate revisions.

## Disposition

The earlier review findings have substantive fixes; they should not be treated as generally unresolved because these new probes exist. The highest-priority correction is A6-1's silent identity collision. Then align recorder execution and source preprocessing with CPython, and extend the evaluator's private-name handling before making broader coverage claims.

Findings use local A6 identifiers for triage. Only this review document is added; no author decision or review-log verdict is changed here.
