# Python Version Review

Date: 2026-11-01  
Reviewer: astra-low  
Sequence: 02

This records the follow-up review delivered in conversation. Release information and recommendations are dated 1 November 2026; Bella was not tested under Python 3.15.2 as part of this review.

## Recommendation

For Bella, I would choose **CPython 3.15.2 as the reference today—1 November 2026—while explicitly limiting the initially supported dialect.** It is the latest stable release. If minimizing immediate migration work is the priority, choose **3.14.10**, rather than retaining 3.14.8. Both current releases include security fixes. [3.15.2 release](https://www.python.org/downloads/release/python-3152/), [3.14.10 release](https://www.python.org/downloads/release/python-31410/).

The reason for choosing 3.15 is Bella's stage: there is little implemented compatibility to preserve, the authoritative corpus still needs recording, and the dependency closure already needs reconciliation. Moving now should be cheaper than moving after the runtime and library mappings grow. That is an engineering judgment, not a claim that migration is already verified.

## Changes to the design

| Area | Consequence for Bella |
| --- | --- |
| **Lazy imports** | The import model needs a distinction between declaring a lazy binding and actually initializing its module. Effects and exceptions can move to first use. Initially reject this feature with a milestone-specific diagnostic. |
| **New builtins** | `frozendict` and `sentinel` need explicit support classifications. The existing promise of “every builtin except…” otherwise silently expands. |
| **Comprehension unpacking** | More accepted syntax and lowering cases. Defer it explicitly until ordinary comprehensions preserve scope and effects. |
| **UTF-8 defaults** | Closer to Bella's existing UTF-8 policy, although “UTF-8 by default” and Bella's “always UTF-8” remain different contracts. |
| **AST construction** | Python 3.15 rejects omitted required AST fields and unknown constructor keywords. Audit the frontend's synthesized nodes. |

These changes are documented in [What's new in Python 3.15](https://docs.python.org/3.15/whatsnew/3.15.html). Lazy imports particularly affect Bella's staging and closure analysis: a module absent from an import-time observation can still be a required dependency. [PEP 810](https://peps.python.org/pep-0810/).

There is also a useful longer-term change: **3.15 introduces `abi3t`, a stable ABI for free-threaded builds.** The design's statement that a free-threaded stable ABI is unavailable would need updating. This creates an option for the future CPython island, but does not guarantee that Bella's bridge or its dependencies can use it; the supported API is limited and migration requires changes. Keep the version-specific bridge as the baseline until its API needs are known. [PEP 803](https://peps.python.org/pep-0803/).

## What does not change

The core architecture remains appropriate: explicit semantics, boxed fallback, proven specialization, and differential testing. Moving versions does not fix the evaluation-order, scope, cache-validation, or certificate-checking defects found in the [design and codebase review](2026-11-01-astra-low-01-design-codebase-review.md). Nor does a newer CPython make Bella's own native runtime faster automatically.

Keep **ordinary, GIL-enabled CPython as the single-threaded conformance oracle**. Treat the free-threaded build as a separate future bridge/concurrency target, with its own tests and build configuration.

## Migration and acceptance gate

1. **Separate three settings:** compiler-host Python, semantic reference Python, and accepted input grammar. They are related but should not be implicitly interchangeable.
2. **Pin the reference to 3.15.2**, including the interpreter artifact/build configuration. Freeze the supported feature list; mark new unsupported constructs P2+.
3. **Run the same corpus against 3.14.8 and 3.15.2**, preserving both outputs for review. Classify differences before adopting new expectations.
4. **Recompute the stdlib closure from 3.15.2.** Review supported APIs and adaptations, not just missing module names.
5. **Verify and lock development dependencies**, then run frontend, object-model, integer, and compiled-output tests under the new host.
6. **Record a dialect revision and migration report.** Future patch upgrades should follow the same explicit process; avoid a floating “latest Python” reference.

Release availability and documented changes were verified, but **Bella was not run under 3.15.2**. The recommendation is to adopt it as the intended baseline now, with the migration checks above as the acceptance gate.
