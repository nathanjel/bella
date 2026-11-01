**The compiler is feasible, but the design is not ready to implement as written.** The strongest part is the staged IR pipeline with conservative fallback and differential testing. The weakest part is the assumption that annotations, closed-world analysis, and C++ facilities make Python’s runtime semantics straightforward.

I reviewed both documents, checked primary documentation, and ran focused probes with CPython 3.14.8 and GCC 16.2.1. No workspace files were changed.

| Proposed scope | Assessment |
|---|---|
| Typed Python subset compiled through IRs into C++ | Feasible |
| Broad dynamic Python compatibility on a new runtime | Feasible in principle; a substantial language-runtime project |
| Exact semantics, concurrent collection without global pauses, broad package support, and verified passes together | Not established by these documents |
| C++26 as the target | Reasonable, but not essential to the core approach |

The following are the main findings, ordered roughly by implementation risk.

1. **High — The concurrency design contains C++ data races.**

   [Design §10](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter design document and build plan.md:530>) says writable method slots can use plain pointer stores because those stores are atomic on the target hardware. That does not make concurrent C++ reads and writes valid: without synchronization, this is undefined behavior. Mutable class pointers, header flags, and shared inline caches need the same scrutiny. [C++ memory-model specification](https://eel.is/c++draft/intro.races).

   Define publication, mutation, cache invalidation, and reclamation protocols before fixing the header layout. Use atomic operations or locks where required. Hardware atomicity is insufficient.

2. **High — The memory-management proposal combines mechanisms without establishing their compatibility.**

   The [feasibility study](</home/nathan/workspaces/nth-share/bella/Python → C++26 by intent-level AST passes feasibility study.md:114>) promises collection without stack scanning, while the design includes deferred references that are deliberately absent from reference counts. Those references still need a way to keep objects alive. PEP 703 explicitly accounts for deferred references by examining stacks during paused collection. Hazard pointers alone do not supply that accounting. [PEP 703](https://peps.python.org/pep-0703/).

   Other unresolved interactions include:

   - A class containing only scalar declared fields can still acquire a self-reference through `setattr`, invalidating cycle-freedom unless dynamic storage is included in the analysis.
   - Deferred destruction conflicts with the promise of exact refcount-triggered finalizer timing.
   - Cross-thread cycles cannot generally be collected independently by per-thread collectors.
   - Epoch reclamation needs a memory-growth policy when a thread stops reaching safepoints.

   Start with ordinary reference counting and a synchronous collector. Treat concurrent collection as a separately validated milestone.

3. **High — Strict annotations are not sufficient evidence for native representations.**

   [Design §2](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter design document and build plan.md:26>) claims checker acceptance establishes a reliable static type for every expression. It does not establish exact runtime classes, immutable layouts, or trustworthy external values.

   Even valid annotations permit distinctions the proposed lowering must preserve: `int` includes `bool` and subclasses; a parameter annotated `float` may receive an `int`. Stubs, casts, ignored errors, and permissively compiled dependencies create additional boundaries. [Python typing specification](https://typing.python.org/en/latest/spec/special-types.html).

   Keep **declared type**, **proven runtime type**, and **chosen representation** separate in the IR. Add guards or conservative fallback where necessary. Mypyc itself uses runtime checks at annotation and stub boundaries. [Mypyc documentation](https://mypyc.readthedocs.io/en/latest/differences_from_python.html).

4. **High — Attribute lookup and mutation are observably incorrect.**

   The [generic lookup order](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter design document and build plan.md:184>) places fields ahead of descriptors and class attributes ahead of side-table instance attributes. Python requires data descriptors first, then instance attributes, then non-data descriptors and class attributes. [Python descriptor specification](https://docs.python.org/3.14/howto/descriptor.html).

   Concrete consequences:

   - Installing a property on a class must override an existing instance field.
   - After `setattr(s, computed_name, "configured")`, reading `s.host` must observe that value when the name is `"host"`; the illustrated direct `__getattr__` call can bypass it.
   - An inline cache containing only `{class, offset, tag}` cannot safely distinguish changing computed names, instance shapes, or class mutations.
   - `vars(obj)` must expose the live instance dictionary; a newly materialized snapshot is not equivalent.
   - Equality of widened field tables is not CPython’s criterion for allowing `__class__` reassignment.

   I confirmed the relevant Python behaviors locally. Define one correct generic object model first, then optimize accesses under explicit guards.

5. **High — Two supplied arithmetic examples fail at their stated boundaries.**

   I reproduced both using minimal extractions of the [integer sketch](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter design document and build plan.md:406>):

   | Case | Required result | Proposed implementation |
   |---|---:|---|
   | `(-(2**62)) // -1` | `4611686018427387904` | Retagging produces `-4611686018427387904` |
   | `norm2_fast(-2**31, -2**31)` | `9223372036854775808` | Signed `int64_t` overflow; UBSan reports it |

   Floor division must promote when the quotient exceeds the tagged range. Range proofs must cover the complete expression, including intermediate results. The generated bigint-capable `norm2()` also cannot unconditionally be `noexcept` if allocation failure must become a Python exception.

6. **High — Several “intent” mappings need stronger semantic preconditions.**

   The [pass pipeline](</home/nathan/workspaces/nth-share/bella/Python → C++26 by intent-level AST passes feasibility study.md:41>) proposes mappings that are not generally equivalent:

   - `sorted(key=...)` cannot directly become `ranges::sort` with a projection. Python sorting is stable and evaluates each key once; projections may run repeatedly. Cache keys and preserve stability. [Python sorting documentation](https://docs.python.org/3.14/howto/sorting.html).
   - A read-only, nonescaping slice cannot automatically become `span`: later mutation of the source would change the view, whereas Python’s slice is a copy.
   - Chained comparisons require single evaluation of intermediate operands.
   - `finally` and `with` need explicit control-flow handling for suppression, replacement exceptions, and overriding returns; an ordinary RAII destructor is insufficient.
   - C++ argument evaluation must preserve Python’s observable evaluation order.

   Add effect, mutation, exception, and sequencing facts to the optimization requirements. Types and ownership alone are insufficient.

7. **High — Staging and module initialization need an explicit semantic contract.**

   [Running bootstrap twice](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter design document and build plan.md:622>) can detect some nondeterminism; it cannot prove that executing at build time preserves runtime behavior. Both runs may read the same environment variable or configuration file and freeze a value that should differ at deployment.

   Likewise, Python imports cannot generally become eager initialization in dependency order. Conditional imports, cycles, partially initialized modules, and import-time exceptions are observable.

   Make staging opt-in or restricted to proven operations, declare and hash its external inputs, and retain runtime initialization for everything else. Specify a module initialization state machine.

8. **High — The proposed Python 3.14t stable-ABI bridge is unavailable.**

   The [feasibility study](</home/nathan/workspaces/nth-share/bella/Python → C++26 by intent-level AST passes feasibility study.md:157>) explicitly relies on the Limited API/stable ABI of free-threaded Python 3.14. Python 3.14 documentation explicitly says that build does not support them. The bridge must be version-specific, or target a separately verified newer ABI. [Python 3.14 extension documentation](https://docs.python.org/3.14/howto/free-threading-extensions.html#limited-c-api-and-stable-abi).

   Package strategy also needs to follow shared object representations. Mapping NumPy while islanding pandas requires a defined array conversion and ownership protocol; choosing strategies independently per package does not resolve that boundary.

9. **Medium — Separate compilation conflicts with application-dependent layouts.**

   The [design](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter design document and build plan.md:531>) allows application code to widen a dependency’s class layout, rebuilding the dependency. That invalidates precompiled code and any consumers using its field offsets. LTO cannot repair incompatible layouts already compiled into machine code.

   Choose either stable exported layouts with dynamic overflow storage, or application-specific specialization from retained IR. The latter is feasible, but its cache keys must include the relevant whole-program facts and invalidate dependent artifacts transitively.

10. **Medium — The verification and delivery claims exceed the evidence.**

    [Design §9](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter design document and build plan.md:517>) calls differential testing “sound-by-construction.” Testing is useful evidence, not a proof. Pass composition also depends on correct semantics, runtime helpers, staging, plugins, and emission—not only the downstream C++ compiler.

    The [build plan](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter design document and build plan.md:644>) needs revision:

    - Three to four full-time engineers over 33 months implies **8.25–11 engineer-years**, before additional specialist effort, rather than 6–8.
    - Phase 1 promises GIL-free whole programs, while the threaded runtime arrives in phase 4; clarify whether phase 1 is single-threaded.
    - Several roadmap diagrams are only embedded-content placeholders in these files.
    - Speedups, bridge-call latency, and near-linear scaling are hypotheses until measured on named workloads.

**I would retain the architecture and narrow the first release.** Python frontend, explicit protocol operations, successive IRs, readable C++, conservative fallback, and differential tests are good foundations.

The implementation order I recommend is:

1. Specify a small supported dialect, including observable exceptions, identity, mutation, and finalization.
2. Build one end-to-end slice: parse → semantic IR → conservative C++ → executable → CPython comparison.
3. Implement exact integers, evaluation order, basic containers, exceptions, and a single-threaded runtime.
4. Add native representations only when analysis proves their preconditions; measure real applications before expanding scope.
5. Add dynamic classes, package bridges, concurrency, and stronger verification as separate milestones.

Use C++23 as the initial baseline and enable C++26 features individually. Compiler language support and standard-library availability remain separate concerns. [GCC support](https://gcc.gnu.org/projects/cxx-status.html), [libc++ feature status](https://libcxx.llvm.org/Status/Cxx26.html).

The key decision is the first product: a useful compiler for a constrained Python dialect is achievable; the current “almost all Python, exact behavior, new concurrent runtime” scope needs substantially more design work before its schedule or performance claims are credible.