# Eval1 Semantics Review

Date: 2026-11-02  
Reviewer: astra-low  
Sequence: 07  
Reviewed range: `3d4e428f60ea57122298ed7ffb6fff6e1db637fb..58bb34b7b6b2fdce87e2972b87f38c80cbc0aa7a`  
Reviewed HEAD: `58bb34b7b6b2fdce87e2972b87f38c80cbc0aa7a`

## Assessment

This is a substantial and useful advance: the frontend now expresses much more of the language in L1, the module system can execute compiled library closures, and the printer makes those translations inspectable. Measuring the library's syntax before choosing whole-closure compilation was sensible. Keeping host-provided objects distinct from the eventual compiled runtime is also the right way to describe the evidence.

The positive corpus does not yet establish the claimed opcode-level exactness. I reproduced six runtime/frontend mismatches and one policy mismatch. Most are observable without frames, finalizers, unsupported introspection, or an unimplemented annotation fallback. One changes a function's actual arguments; another accepts a class CPython rejects. The dictionary and iterator findings show why translating C operations into superficially equivalent Python operations needs adversarial protocol tests.

This review does not rediscover the declared open work: statement-level refusals, S-1's second annotation entry point under eval1, frames and traceback fidelity, the listed super edges, temporary finalization timing, or the C++ backend. Those remain acknowledged limits rather than new findings.

## Verification and scope

The tree started clean at the requested endpoint. I read the changed frontend/evaluator paths, runtime class and match helpers, module and staged-text integration, wf1 policy, measurement/decision material, and representative tests. This is not a claim to have exhaustively audited every added line or every copied shim.

The requested command was run locally:

```sh
uv run make lint test verify eval1-corpus targets-eval1 staging-check slice
```

The full command exited zero. Results: lint and mypy passed; 135 tests passed; the reference-model self-check passed over 3,000 operations; 139/139 reference expectations reproduced; eval1 preserved its 58-case baseline out of 75 cases; all three easy targets matched under whole-closure eval1; and `staging-check` passed. The integer slice reported 5/5 as expected: four full passes and the existing `fact_big.py` C++ XFAIL for missing BigInt promotion; eval1 agreed with CPython on all five. The slice validates the existing integer backend, not a C++ implementation of the new language features.

Differential probes ran each temporary source in separate processes under pinned CPython 3.15.2 and `pipeline/l1/run.py` in its default program mode. The affected frontend/evaluator operations are also used in closure mode; I did not establish that any of the three current easy-target outputs changes because of these probes. Only this review file is added. CI's reported status was not independently inspected, and Docker was not rebuilt.

## Findings

### A7-1 — High: a sole starred call argument is expanded too early

Location: `pipeline/l1/eval1.py:1196` (`Interpreter.arguments`).

Every starred positional operand is immediately extended into the argument list. CPython's single-star call path can retain that operand until after keyword expressions have run, and only then convert it for the call. This affects actual values, not just tracing or exception wording.

Reproduction:

```python
data = [1]
def kw():
    data.append(2)
    return 0
def f(*args, **kwargs):
    print(args)
f(*data, x=kw())
```

CPython prints `(1, 2)`; eval1 prints `(1,)`. Both exit zero. A custom iterable also shows `kw` before `__iter__` on CPython and the reverse under eval1.

Recommendation: model the distinct call-building paths, including the single-star operand retained until CALL_FUNCTION_EX, rather than using one eager expansion rule for every call. Test keyword mutation of the iterable and failures during iteration, alongside multiple-star and ordinary-prefix cases. Argument binding after construction cannot recover the correct values once expansion happened too early.

### A7-2 — High: future-annotation module semantics are replaced by PEP 649 semantics

Locations: `pipeline/l1/frontend.py:110`, `pipeline/l1/frontend.py:154` (`_annotate_function`, `_Annotations.run`).

The `future` flag changes annotation values into strings, but the pass still creates a deferred `__annotate__` function and conditional-annotation set. Under `from __future__ import annotations`, CPython sets up and updates the module's annotation dictionary instead. These namespace effects are observable without using FORWARDREF/STRING fallback machinery.

Reproduction:

```python
from __future__ import annotations
print("__annotations__" in globals())
x: int
print("__annotate__" in globals())
print(__annotations__)
```

CPython prints `True`, `False`, and `{'x': 'int'}`. Eval1 prints `False`, `True`, then exits with NameError for `__annotations__`.

Recommendation: give PEP 563 module/class annotations their own setup and statement-update semantics, rather than expressing them as string-valued PEP 649 annotations. Cover observation before the annotated statement, conditional statements, and mutation/replacement of `__annotations__`. This finding is independent of the acknowledged missing S-1 entry point under eval1.

### A7-3 — High: annotation-only targets lose effects, and function targets can crash lowering

Locations: `pipeline/l1/frontend.py:213`, `pipeline/l1/frontend.py:240`, `pipeline/l1/frontend.py:287` (`function_body`, `annassign`, `_declare`).

Not evaluating an annotation is different from not evaluating its target expressions. For an annotation-only attribute/subscript target, CPython still evaluates the object and, for subscripts, the key. At module/class scope the pass drops that work. Inside a function, the same form is passed to `_declare`, which asserts that the target is an `ast.Name`.

Reproduction:

```python
def obj():
    print("obj")
    return []
def key():
    print("key")
    return 0
obj()[key()]: int
```

CPython prints `obj` and `key`; eval1 exits successfully with no output. A separate function containing `obj().x: int`, followed by calling that function, prints `obj` on CPython but crashes the frontend with AssertionError under eval1.

Recommendation: distinguish name declarations from annotation-only attribute/subscript forms. Preserve the target component evaluations in their original order without performing an attribute/subscript read or assignment. Test both side effects and exceptions, at module, class, and function scope. Valid input must not reach an internal assertion.

### A7-4 — Medium: comprehensions obtain the outer iterator twice

Locations: `pipeline/l1/frontend.py:1346` (`_Comprehensions.comprehension`); `pipeline/l1/eval1.py` (`Interpreter.stmt`, `L.For` branch).

The comprehension call explicitly passes `iter(outer_expression)` to its helper. The helper then runs an ordinary L1 `For`, which calls `iter` on that already-created iterator again. For a generator expression, the extra call occurs when iteration starts, after creation. CPython's comprehension loop consumes the iterator it already holds.

Reproduction: use a one-element iterator whose `__iter__` prints `iter` and returns itself. `[x for x in I()]` prints `iter` once on CPython and twice under eval1. With `g = (x for x in I()); print("created"); print(next(g))`, CPython prints one `iter` before `created`; eval1 prints another afterward.

Recommendation: distinguish an existing iterator from a general iterable in the lowered loop operation, or otherwise preserve the single GET_ITER boundary. Test an iterator whose second `__iter__` has an effect or raises. This is not the known lifetime difference for comprehension temporaries.

### A7-5 — Medium: dict unpacking rehashes keys that CPython copies with cached hashes

Location: `pipeline/l1/eval1.py:1475` (`_dict_update`); the related fast path in `_dict_merge` deserves the same audit.

For an ordinary dict, `_dict_update` loops over `dict.items` and assigns each pair with `target[k] = v`. CPython's dict merge path can reuse stored key hashes. The Python-level loop invokes user `__hash__` again, introducing extra effects and potentially exceptions on an otherwise successful dictionary copy.

Reproduction:

```python
trace = []
class K:
    def __hash__(self):
        trace.append("hash")
        return 1
k = K()
m = {k: 3}
trace.clear()
n = {**m}
print(trace, len(n))
```

CPython prints `[] 1`; eval1 prints `['hash'] 1`.

Recommendation: use a host operation that preserves the exact-dict merge behavior in this oracle, and specify the cached-hash behavior for the eventual runtime. Keep the generic mapping path separate, with its keys/getitem ordering. Add keys whose hash raises after initial insertion; a pure dict copy should not acquire a new failure path. Audit duplicate detection for `**` calls as well, without assuming its Python membership tests are equivalent to cached-hash C lookups.

### A7-6 — Medium: explicit `__prepare__ = None` is treated as an absent method

Location: `runtime/prelude/build_class.py:92`.

`getattr(meta, "__prepare__", None)` uses None for both absence and an explicitly present value. If a metaclass defines `__prepare__ = None`, CPython attempts to call that value and raises TypeError. Bella instead creates an empty namespace and successfully constructs the class.

Reproduction:

```python
class M(type):
    __prepare__ = None
try:
    class C(metaclass=M):
        pass
    print("created")
except TypeError:
    print("TypeError")
```

CPython prints `TypeError`; eval1 prints `created`.

Recommendation: use an absence sentinel distinct from any user-provided attribute value. Audit the equivalent optional-attribute handling in `_update_bases`, which also uses None for `__mro_entries__`. Test missing, explicitly None, and callable attributes separately. This does not involve the listed super edge cases.

### A7-7 — Medium: any globals() call disables the program's strict name-binding rule

Locations: `pipeline/l1/wf.py:105`, `pipeline/l1/wf.py:199`.

There is a third effective relaxation beyond star imports and P-3 library modules. `_writes_globals` returns true for any syntactic call named `globals`, including read-only calls inside uncalled functions. `_Checker.module` then sets the same `star` flag used to accept unresolved names. This happens even with `check(..., strict=True)` on the program's own entry module.

Reproduction using `check(lower(source))`:

```python
print(missing)                         # rejected with WellFormednessError
```

Both of these instead pass the strict checker with no diagnostics:

```python
globals()
print(missing)
```

```python
def unused():
    return globals()
print(missing)
```

Neither example writes a module global, imports a star, or invokes P-3's library exemption. The decision and spec v0.12 explicitly retain compile-time NameError for the program's own modules.

Recommendation: remove the blanket globals-call exemption from strict program checking. P-3 already has an explicit `strict=False` path for library modules. If additional permitted program writes need analysis, represent those writes and their known bindings directly; do not infer them from the presence of a read-only builtin call. Keep library classification explicit at the module boundary.

## Approach and remaining evidence

* **P-1/D-10:** whole-closure compilation is now an explicit decision supported by measurements, not an accidental consequence of the sample targets. Keep the measurement's reachable-work estimate separate from proof that every declared library API lowers. The known statement-refusal gap remains an implementation milestone, not evidence against the decision itself.
* **P-3:** permitting CPython global lookup in designated library modules addresses a real dependency such as enum's writes into re. Preserve that provenance through compilation rather than relying solely on a path containing a directory named `vendor`. A7-7 is a separate, unapproved weakening for program code, not a criticism of the accepted library policy. Future global-slot optimization must preserve the existing observable module dictionaries and mutation behavior.
* **Host borrowing:** real host function/generator/PEP 695 objects are reasonable model scaffolding. They do not automatically validate the L1 code that computes arguments, performs name loads, creates iterators, or chooses imports. Differential tests should observe those boundaries explicitly. The declared absence of frames and the C++ leg remains visible and should stay so.
* **Imports and match:** I inspected the one-shot import adapter, lazy-import mode handling, and match helper paths. The basic additional MATCH_KEYS/hash probe I ran agreed with CPython; this is not an exhaustive validation of those subsystems. Module boundaries and callable protocol hooks remain useful adversarial test points.
* **Regression gate:** `eval1-corpus` is correctly presented as a baseline gate, not a full conformance claim. Its result is 58 of 75 cases, not 75 passing cases. The tool should also require a complete harness run/summary before writing `--update`; currently any partial nonempty result can become the new baseline after a harness crash. A normal check usually notices missing baseline cases, but the update path deserves a stronger completion check.
* **Readable L1:** the new printer is useful for reviewing these transformations. Where an operation has different construction paths in CPython, showing the selected path explicitly would make order-of-effects review easier than hiding it in a generic helper.

## Disposition

Keep the architecture and the accepted scope decisions. Prioritize call construction and annotation semantics, then the extra protocol invocations and strict-checker exemption. The needed next evidence is focused differential tests at these boundaries, not merely more successful ordinary examples.

Findings use local A7 identifiers for triage. This review does not alter decisions or resolve review-log entries on the author's behalf.
