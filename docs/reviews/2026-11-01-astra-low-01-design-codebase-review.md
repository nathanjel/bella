# Design Codebase Review

Date: 2026-11-01  
Reviewer: astra-low  
Sequence: 01

This records the review delivered in conversation, against the repository state inspected then. Findings have not been revalidated against subsequent changes. File links identify the reviewed implementation; line numbers may move.

The architectural direction is worth pursuing, but the starter code is a research scaffold, not yet a dependable semantic foundation. The main concern is that several components silently accept programs they execute incorrectly, despite the design's explicit “correct or unsupported” rule.

I reviewed the three `early-design` documents—the copies in `docs` were identical—and the compiler slice, object model, validation, conformance harness, and build configuration.

## Code findings

### 1. High: the emitter changes expression evaluation order

[emit_cpp.py](../../pipeline/backend/emit_cpp.py), around line 113, nests binary operands directly into C++ expressions. The temporary-binding fix covers call arguments, but not arithmetic operands.

I reproduced this with `print(f(1) + f(2))`, where `f` prints its argument before returning it:

| Execution | Output |
| --- | --- |
| CPython and `eval1` | `1`, `2`, `3` |
| Generated C++ | `2`, `1`, `3` |

Introduce explicit sequencing before emission for every potentially effectful operand. The planned ANF representation addresses exactly this problem.

### 2. High: range-loop lowering changes the loop variable's meaning

[emit_cpp.py](../../pipeline/backend/emit_cpp.py), around line 252, uses the Python target as the C++ induction variable.

| Program behavior | CPython / `eval1` | C++ |
| --- | --- | --- |
| Execute `for i in range(3): pass`, then print `i` | `2` | `3` |
| Initialize `i = 9`, execute an empty `range(0)` loop, then print `i` | `9` | `0` |

Assigning to `i` inside the body will also alter iteration incorrectly. Use a separate internal iterator and assign the Python target only when an element is yielded. This follows the [Python loop contract](https://docs.python.org/3/reference/compound_stmts.html#the-for-statement).

### 3. High: the emitter invents values and ignores binding semantics

[emit_cpp.py](../../pipeline/backend/emit_cpp.py), around line 273, initializes locals to zero, ignores `FunctionDef.globals`, and inserts `return Int(0)` on fallthrough.

I confirmed:

- A function assigning `global x` leaves the compiled module's `x` unchanged.
- A function falling through returns `0` instead of `None`.

Until the runtime supports these cases, reject them explicitly. A restricted backend is reasonable; silently substituting semantics undermines the testing strategy.

### 4. High: object-model cache validation executes user behavior twice

[objects.py](../../refmodel/objects.py), around line 349, performs generic lookup, then cached lookup on the same live state. Both can invoke descriptors or `__getattr__`.

A getter that increments a counter returns `1` on the first access; the second access invokes it twice and raises `ModelError` because the results are `2` and `3`. The model also stores ordinary strong Python references in fields described as “borrowed.”

Compare generic and cached execution in independent equivalent worlds, or compare lookup decisions before invoking the selected operation once. Extend tests to effectful getters, exceptions, mutation during lookup, and descriptor lifetimes before deriving the C++ header.

### 5. Medium: comprehension lowering loses enclosing scope

[frontend.py](../../pipeline/l1/frontend.py), around line 160, traverses into function bodies and hoists comprehension helpers outside the function.

```python
def f(x: int):
    return [x + i for i in range(2)]
print(f(10))
```

CPython prints `[10, 11]`; Bella rejects it because `x` is unbound in the generated helper. This needs scope-aware lowering and hygienic generated identifiers.

### 6. High before enabling optimizations: certificate checking must fail closed

[certificates.py](../../validation/certificates.py), around line 169, treats every solver result other than `sat` as proof, including `unknown`. Only `unsat` proves the absence of overflow.

Separately, interval arithmetic is described as exact for this grammar, but repeated variables introduce dependencies. I reproduced an assertion failure for `x - x`, with `x ∈ [-100, 100]` and an 8-bit result: every intermediate fits, but the interval approximation cannot establish that.

Use explicit **proved / refuted / unknown** outcomes. An inconclusive interval or solver result should preserve the checked implementation.

### 7. High for release gating: CI does not establish conformance

[Makefile](../../Makefile), around line 50, runs `record`, but omits `check-conformance`. Recording expectations is not checking Bella.

The [harness](../../conformance/harness.py), around line 156, also exits successfully when required expectations are skipped: I ran a filtered check with runner `false` and got `0/0 passed`, exit zero. Its stderr mask makes `ValueError("user-message-A")` and `ValueError("user-message-B")` indistinguishable, contrary to the structured/user-payload commitment.

Separate oracle recording from validation, fail on missing required coverage, and keep user-provided exception payloads observable.

## Feedback on the approach

The strongest choices are the separation of declared types from proven runtime classes and representation, the generic boxed fallback, executable IR semantics, and differential testing. The object model has already produced useful design corrections; that is good evidence for keeping the model-first workflow.

I would change four things in the proposed plan:

- **Make the first deliverable substantially smaller.** Phase 1 includes descriptors, generators, exception groups, finalization, cycle collection, staging, and a broad standard library. That is already a substantial Python runtime. Pick the three real target programs now, then deliver one complete, explicitly bounded path through the smallest. Keep the wider P1 contract as a later milestone.
- **Treat staging as an unresolved implementation problem.** The [staging contract](../dialect-spec.md), section 8, now preserves runtime definition effects, which is the right direction. It still needs an executable account of how captured generated code replaces `exec` while runtime decorators, defaults, hooks, and object identities remain correct. Prototype one dataclass or namedtuple example with observable effects before relying on staging for library coverage.
- **Make lifetime changes explicit in the IR.** Exact refcount-triggered finalization affects assignment, temporaries, argument binding, exception unwinding, and optimization. C++ RAII alone will not establish the required destruction points. Include retain/release timing and observable finalizer traces in the executable semantics early.
- **Consolidate the authoritative documents.** The review appendices override earlier sections, but earlier text still describes field-backed exposed dictionaries, immortal functions/classes, and snapshot-based L1 lowering. Rewrite those sections around the final decisions and preserve review history separately. Likewise, present `PassSpec` as obligation tracking until evidence and executable checks are attached to its status.

The dependency-closure tool is useful, but closure should be treated as an inventory prerequisite, not proof that those modules can be compiled or their APIs reproduced.

## Verification performed

On the available **CPython 3.14.8 and GCC 16.2.1**:

| Check | Result |
| --- | --- |
| `make test` fallback and reference-model self-check | Passed |
| Supplied compilation examples | Three passed; BigInt example expected failure |
| Integer differential test with UBSan | 2,000 cases, zero mismatches; 315 reported promotions |
| Dependency closure | Failed with 23 reported problems |
| Existing expectations against CPython | 23 positive cases matched; exclusion case failed as expected with a CPython runner |
| Additional targeted examples | Confirmed the defects above |

Pytest, Hypothesis, and Z3 were unavailable, so their checks were not exercised. Source and expectations were left unchanged during the review.

The recommended next increment is to fix the semantic and validation defects above, turn each reproduction into a regression case, reconcile the pinned closure, and compile one small real application end to end. That would provide a firmer basis for extending the runtime or committing to the schedule.
