# Stdlib Closure Review

Date: 2026-11-01  
Reviewer: astra-low  
Sequence: 03  
Reviewed commit: `b40ef2da9716ec5056421919acb5ae0f008fca79`

## Assessment

The delivery materially improves the project. I reproduced the reported 174-module inventory and the committed lock byte for byte, and the claimed checks are supported by local results and a successful CI run. The new codec entries, explicit adaptations, status consistency checks, and mandatory lock comparison are useful improvements.

However, the tool can still report a closed inventory while missing required dependency decisions. I would accept the current lock as a reproducible snapshot, but would fix findings A3-1 and A3-2 before treating the closure gate as complete. A3-3 through A3-5 concern incorrect or insufficient policy metadata. These are focused tool corrections, not reasons to abandon the manifest approach.

The reproductions below distinguish defects in the checker from defects demonstrated in the current standard-library inventory. In particular, I did **not** establish that the current 174-module set needs additional modules because of A3-1. Some findings are retained weaknesses from earlier revisions, not regressions introduced by this commit.

## Verification

| Check | Result |
| --- | --- |
| Reviewed tree | HEAD was `b40ef2d`; working tree initially clean |
| Interpreter | `uv run python --version`: CPython 3.15.2 |
| Closure tests | 13 passed |
| Closure recomputation | 174 modules: 112 compiled, 36 mapped, 19 core, 7 shims; no errors |
| Lock comparison | `/tmp/bella-review-task1-closure.json` matched committed `closure.lock.json` byte for byte |
| Lock paths | No absolute module paths in the current lock |
| `uv run make lint test verify` | Ruff and mypy clean; 59 tests passed; reference-model self-check passed; 28/28 expectations reproduced |
| Targeted negative probes | Reproduced all five findings below |
| CI for the reviewed commit | Both the Docker job and developer-machine smoke job succeeded |

The coder's “CI still running” status is now superseded by [successful run 41324836067](https://github.com/nathanjel/bella/actions/runs/41324836067). I inspected its job results; I did not independently rebuild Docker or rerun the C++ probes/slice/integer driver locally during this focused review. The local closure comparison used the pinned uv-managed interpreter. `verify` establishes oracle reproducibility, not compiled stdlib support.

## Findings

### A3-1 — High: runtime-discovered modules never enter the dependency worklist

Location: [tools/closure.py](../../tools/closure.py), `compute_closure`, lines 840–877 at the reviewed commit. Retained behavior, still relevant to task 1's completeness claim.

The static queue is exhausted before runtime observation. A newly observed module is passed to `ensure()`, which scans and stores its edges, but those edges are never processed. Its eager, function-local, optional, and manifest-declared dynamic dependencies therefore do not receive the normal closure treatment.

Reproduction using temporary source modules and a controlled observation result:

```python
# rv_root.py
loader = __import__
loader("rv_child")

# rv_child.py
def f():
    import rv_grandchild
```

List `rv_root` and `rv_child` as compiled, root the graph at `rv_root`, and supply the observation `{"rv_root": ["rv_child"]}`. Provide an empty `rv_grandchild.py`, but leave it outside the manifest.

**Observed:** the result contains `rv_root` and `rv_child`, and `rv_child` has a recorded lazy edge to `rv_grandchild`, but `problems == []`. The tool does not demand support or an unsupported-function decision for `f`.

The observer is stubbed here to isolate graph processing; it supplies exactly the kind of result that the observer is intended to contribute. This is not a test claiming the isolated subprocess can import arbitrary temporary fixtures without path setup.

**Fix:** feed observed modules into the same worklist and run to a fixed point. Distinguish discovered nodes from nodes whose edges have been processed; otherwise the existing `if name in infos: continue` will skip nodes created by `ensure()`. Add a regression with a runtime-discovered source module whose function imports an undeclared module.

**Current-snapshot limit:** the lock's runtime-discovered entries currently have no scanned edges (`__future__`, mapped math entries, and importlib core entries). This explains why the snapshot passes without demonstrating the missing traversal.

### A3-2 — High: absence on the host silently substitutes for a manifest decision

Location: [tools/closure.py](../../tools/closure.py), lines 892–920. Retained behavior.

For both optional and function-local imports outside the manifest, the tool calls `classify()` and silently continues when the target is missing. In particular, a required import in a supported function can disappear from policy enforcement merely because that dependency is not installed on the review machine.

```python
# rv_root.py; only rv_root is declared compiled
def f():
    import rv_does_not_exist_928
```

**Observed:** the scanner records a lazy edge, but `compute_closure()` returns no problems and `unsupported_functions()` contains no entry for `f`.

That violates the documented rule that a function-local dependency outside the manifest needs an explicit refusal decision. For optional imports it also violates the stated requirement that omissions be recorded. A missing module is not evidence that its import statement is unreachable.

**Fix:** require a support, omission, or refusal decision for live edges regardless of host availability. If platform absence is an accepted separate category, record and validate it explicitly rather than treating every unresolved name as safe. Platform-dead code should be excluded by the guard analysis.

**Current-snapshot evidence:** the lock already contains undeclared missing targets accepted this way: optional `_winapi`/`nt` edges in `ntpath`, an optional `_winapi` edge in `pathlib._os`, and the lazy `nt` edge in `os.add_dll_directory`. The latter function is absent on Linux because CPython places its definition under `if name == 'nt'`; the scanner has not proved that branch dead. These are not a request to implement Windows APIs on Linux. They show where an implicit host-absence exemption currently fills gaps in the declared policy.

### A3-3 — Medium: optional exception context leaks into deferred function bodies

Location: [tools/closure.py](../../tools/closure.py), `_Scanner._visit`, line 580.

Entering a function body sets `lazy=True` but retains `optional=True` from the enclosing definition context. Consequently:

```python
try:
    def f():
        import rv_required
except ImportError:
    pass

f()
```

**Observed scanner edge:** `('rv_required', 'optional', 3, 'f')`.

The surrounding handler only covers creation of `f`, not a later call. With a real but unsupported target, the tool asks for an omission instead of the function-level refusal required by decision D-3. Exceptions during a call after the `try` are not suppressed by that handler.

**Fix:** clear inherited exception-suppression context when entering a deferred function or lambda body; preserve it for decorators/defaults evaluated at definition time. New handlers inside the function can then establish their own optional context. Add both outer-handler and inner-handler tests. Other inherited facts should be considered separately: a function definition in proven dead code remains dead.

### A3-4 — Medium: `__lazy_modules__` metadata does not follow execution order or individual imports

Locations: [tools/closure.py](../../tools/closure.py), `_first_use` at lines 541–550 and `_literal_lazy_modules` at lines 725–733. This concerns the new task-1 metadata.

Two independently reproduced cases:

```python
__lazy_modules__ = ["fractions"]
import fractions, math
```

The scanner marks both edges eager because it requires every module in the statement to appear in the list. Under the pinned CPython, `fractions` is still absent from `sys.modules` immediately after this statement: its import is lazy.

```python
import fractions
__lazy_modules__ = ["fractions"]
```

The scanner marks the earlier import first-use because it gathers lazy-module declarations from the entire module. CPython has already loaded `fractions` at that point. Reassignment is also not modeled: the scanner unions all literal declarations.

These examples agree with [PEP 810](https://peps.python.org/pep-0810/): `__lazy_modules__` is checked at each import, and can change between imports.

**Impact:** eager and first-use edges are both traversed, so these cases need not change the module count. They do invalidate the claim that this metadata can tell the runtime when bindings are lazy. Import timing changes observable effects and exceptions.

**Fix:** classify each imported module independently, using the declaration visible at that program point. Represent unknown/mutable policy explicitly or require a documented restricted form; do not silently supply inaccurate timing metadata. Treat the lock as an inventory, not a substitute for the compiler's binding-level import IR.

### A3-5 — Medium: a module-level dynamic entry does not record review of every site

Location: [tools/closure.py](../../tools/closure.py), lines 942–950; [manifest.toml](../../manifest.toml), `[dynamic]`.

Once `rv_root = []` exists under `[dynamic]`, any number of new computed imports in `rv_root` are accepted without a new review decision:

```python
def reviewed(name):
    return __import__(name)

def new_unreviewed(name):
    return __import__(name)
```

**Observed:** the scanner finds both sites, but the module entry satisfies the check and `problems == []`.

The current claim that all eight sites were manually reviewed may be true. The checker enforces only that their containing modules have entries. CI's stale-lock comparison will detect a source-induced lock change until the lock is regenerated, but regeneration can then bless the new site without any recorded policy review.

**Fix:** key review decisions by module and qualified function plus a stable site identifier or expression fingerprint; check both new and stale sites. Alternatively, narrow the documented guarantee to module-wide policy approval, explicitly acknowledging that it does not enforce the promised per-site review. This does not demand solving arbitrary computed imports statically.

## Assessment of the decisions called out by the coder

**hashlib / hmac:** acceptable as an explicitly scoped phase-1 policy, given the project's licensing constraint. The API gap is now visible in the spec. However, “like CPython without OpenSSL” is a different library configuration from the pinned reference executable. Add focused compatibility cases for the permitted digest/HMAC surface and explicit absence tests for `pbkdf2_hmac` and `scrypt`; do not replace the main oracle with a different build or hide failures in broad masks. Removing an accelerator dependency does not itself prove the mapped digests preserve behavior.

**annotationlib shim:** acceptable as an inventory placeholder, conditional on the already accepted staging work (D-2 / RL-50). It is not evidence that dataclasses work at runtime. In the pinned source, `dataclasses._process_class` calls `annotationlib.get_annotations(..., format=FORWARDREF)` at lines 1057–1058. The spec also requires runtime definition effects to be replayed, while the proposed shim refuses that call. The staging prototype must demonstrate how that call is replaced or served from correct metadata while effects are preserved. This is the existing unresolved staging obligation, not a new claim that the closure tool must implement dataclasses.

**Path URI methods and ast.unparse:** reasonable explicit deferrals. The lock correctly names `Path.as_uri`, `Path.from_uri`, and `ast.unparse` as refused functions. Preserve the distinction between a public API refusal and merely letting a deeper import fail. The analogous archive entries name private `shutil` helpers; decide and test which public calls remain valid before shipping that runtime policy.

**Traceback helper replacement:** reasonable under the closed-world premise. `[replaced]` is better than excluding a dependency without explanation, and the tool checks that the function exists and its module has an adaptation. A runtime test should eventually demonstrate that an ordinary `ModuleNotFoundError` still formats successfully with this replacement. The inventory does not yet validate replacement semantics.

**Lazy imports:** I accept the project's revision of my earlier recommendation to defer them. The inspected phase-1 library depends on them, so supporting that library requires the lazy-import runtime work. A3-4 concerns the correctness of its metadata, not reopening that scope decision.

## Reproducing the graph findings

Run this from the repository root with `uv run python`. It creates only temporary modules and stubs runtime observation, following the existing closure unit tests' isolation approach. At the reviewed commit, each `problems` list printed below is empty; the first two should instead require additional dependency decisions, and the third demonstrates the review-granularity limitation.

```python
import importlib
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
import tools.closure as c

def probe(files, extra_manifest, observed):
    with tempfile.TemporaryDirectory() as directory:
        for name, source in files.items():
            Path(directory, name + ".py").write_text(source)
        path = Path(directory, "manifest.toml")
        path.write_text('[reference]\npython="3.15.2"\n' + extra_manifest)
        sys.path.insert(0, directory)
        importlib.invalidate_caches()
        try:
            manifest = c.Manifest.load(path)
            with patch.object(c, "observe_runtime_imports", return_value=observed):
                infos, problems = c.compute_closure(manifest)
            print("modules:", sorted(infos), "problems:", problems)
            print("refused:", c.unsupported_functions(infos, manifest))
        finally:
            sys.path.remove(directory)

probe(
    {"rv_root": 'loader=__import__\nloader("rv_child")\n',
     "rv_child": 'def f():\n    import rv_grandchild\n',
     "rv_grandchild": ''},
    '[phase1]\nroots=["rv_root"]\ncompiled=["rv_root","rv_child"]\n',
    {"rv_root": ["rv_child"]},
)
probe(
    {"rv_root": 'def f():\n    import rv_does_not_exist_928\n'},
    '[phase1]\nroots=["rv_root"]\ncompiled=["rv_root"]\n',
    {},
)
probe(
    {"rv_root": 'def reviewed(name):\n    return __import__(name)\n'
                'def new_unreviewed(name):\n    return __import__(name)\n'},
    '[phase1]\nroots=["rv_root"]\ncompiled=["rv_root"]\n'
    '[dynamic]\nrv_root=[]\n',
    {},
)
```

## Recommended follow-up

Keep the new manifest and the successful pinned CI gate. Add negative tests for A3-1 through A3-5, repair graph traversal and missing-target handling, then regenerate and compare the lock. Review any newly surfaced platform entries explicitly. Carry shim and replacement conformance into their implementation milestones rather than treating a closed import graph as proof of working APIs.

This review changes no compiler code, manifest, expectations, or prior review verdicts. Finding labels A3-1 through A3-5 are local to this review, for reproduction and disposition through the existing review-log process.
