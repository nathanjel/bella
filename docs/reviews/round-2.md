**The revisions materially improve the proposal, but the three documents still do not form a consistent implementation contract.** I would proceed with a bounded phase-0 prototype and conformance corpus. I would not yet freeze the dialect or approve the phase-1 delivery scope.

The boxed-first approach is reasonable, and I accept the documented GCC/C++26 decision. The main remaining risks concern Python semantics, dependency coverage, and object lifetimes—not the backend language.

I reviewed all three files, inspected relevant CPython 3.14.8 library sources, and ran focused semantic probes. The arithmetic checks used GCC with UBSan. No workspace files were changed.

**Several earlier findings can now be closed at the design level:**

| Earlier finding | Current assessment |
|---|---|
| Tagged floor-division overflow and unsafe `norm2` bounds | Corrected. Extracted floor/mod paths matched CPython on **1,156 cases**, including promotion selection; corrected `norm2` boundary was UBSan-clean. |
| Sorting keys, slice aliasing, exception suppression, argument sequencing | The new effect requirements give the right direction. |
| Free-threaded Python 3.14 stable ABI | Corrected to a version-specific bridge in the authoritative resolution. |
| Dependency layout widening | Stable exported layouts plus optional whole-program specialization is a sound direction. |
| Testing described as proof; staffing arithmetic | Corrected. |
| First release described as threaded | Corrected to single-threaded in the build plan. |

These are corrections to a proposal. The supplied workspace contains the documents, not the compiler or conformance suite needed to validate implementation claims.

The remaining findings are below.

1. **High — Phase 1 is not closed over its own library dependencies.**

   The [dialect’s library table](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter dialect specification v0.md:134>) promises modules whose dependencies are explicitly deferred or excluded. Inspecting the installed CPython sources confirmed:

   | Promised in phase 1 | Dependencies outside phase 1 |
   |---|---|
   | `logging` | `threading`, `traceback`; caller discovery also uses `sys._getframe` |
   | `argparse` | `gettext` |
   | `_pydecimal` | `contextvars` |
   | `unittest` | `traceback` |
   | `copy` | `copyreg` |

   Staging does not remove dependencies that are used during ordinary runtime calls.

   There is also a milestone contradiction: the dialect requires working `gc.collect()` and cycle finalization in phase 1, while the [review resolutions](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter design document and build plan.md:698>) place the synchronous collector in phase 2.

   **Required change:** define support per API where necessary, compute the dependency closure, and name every required mapping or adaptation. Either move synchronous cycle collection into phase 1 or explicitly defer the corresponding guarantees. “Pure Python compiles” cannot substitute for this inventory.

2. **High — Snapshot immortality contradicts the lifetime contract.**

   The [staging contract](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter dialect specification v0.md:167>) makes **every snapshotted object immortal**. Section 9 simultaneously requires synchronous destruction when an acyclic object loses its last reference.

   For example, suppose a staged module creates:

   ```python
   class Resource:
       def __del__(self) -> None:
           print("closed")

   resource = Resource()
   ```

   Later, `del module.resource` must print `"closed"` when that is the last reference. An immortal snapshot instance cannot do so. I confirmed the corresponding CPython behavior.

   Recording build inputs improves reproducibility, but does not resolve object lifetime, import-time effects, or when staged module contents become visible through `sys.modules`.

   **Required change:** distinguish serialized snapshot data from runtime objects. Materialize ordinary objects with ordinary ownership at the appropriate initialization point. Immortalize only objects for which collectability, weak references, finalizers, and retained referents cannot expose a difference. Specify which staging effects are forbidden, replayed, or intentionally removed.

3. **High — The attribute-cache finding remains open.**

   The revised [cache entry](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter design document and build plan.md:170>) adds a class version, but still lacks the requested attribute name and instance shape.

   Consider one call site:

   ```python
   [getattr(obj, name) for name in ("x", "y")]
   ```

   Both accesses have the same class and class version. A cached field offset for `"x"` must not serve `"y"`.

   Further invalidation cases remain unspecified:

   - A base-class mutation changes lookup on subclasses.
   - An instance gains an attribute that shadows a previously cached class attribute.
   - A field is absent or deleted, requiring fallback to a class attribute or `__getattr__`.
   - Runtime-created instances of the same class have different shapes.

   The [computed-write example](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter design document and build plan.md:288>) also still sends every computed name directly to overflow storage. `setattr(n, name, value)` must first honor descriptors and existing fields.

   **Required change:** specify a cache key and validity predicate for each lookup kind. Include name identity, relevant MRO/version dependencies, shape or storage checks, and field-presence handling. Make computed writes go through the same semantic lookup rules.

4. **High — A live dictionary proxy still falls short of the promised dictionary semantics.**

   The [design](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter design document and build plan.md:442>) promises a new proxy allocation per access. CPython preserves stronger behavior:

   ```python
   vars(obj) is vars(obj)       # True
   type(vars(obj)) is dict      # True

   replacement = {}
   obj.__dict__ = replacement
   vars(obj) is replacement    # True
   ```

   Writes through `replacement` must then affect attribute access. I verified these cases locally.

   Related rules also need correction:

   - `Cls.__dict__` is a read-only mapping proxy; assigning through it raises `TypeError`.
   - A class declaring `__slots__ = ()` can still inherit an instance dictionary from its base. The design’s blanket “class with `__slots__` has no pointer” rule is incorrect. [Python’s slot rules](https://docs.python.org/3.14/reference/datamodel.html#slots).

   **Required change:** support stable dictionary identity, replacement and aliasing, and correct inherited layout capabilities. If exposing `__dict__` forces an object into dictionary-backed storage, that is a defensible implementation choice.

5. **High — Some generic protocol slots cannot express the admitted behavior.**

   The [runtime draft](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter design document and build plan.md:109>) gives equality a `bool` result. Python rich comparison may return another object or `NotImplemented`; conversion to truth happens only when required by the surrounding operation. [Python comparison protocol](https://docs.python.org/3.14/reference/datamodel.html#object.__eq__).

   My probe confirmed that a custom `__eq__` can make `a == b` return `"comparison-result"`.

   The iterator slot also needs explicit semantics for termination payloads. A false return alone must not discard `StopIteration.value`, which phase-1 `yield from` and direct `next()` handling can observe.

   **Required change:** separate general comparison from truth-tested comparison. Define iterator outcomes—including yielded value, termination value, and exceptional termination—before implementing generator lowering.

6. **High — Several normative rules describe behavior different from CPython.**

   These are specification defects rather than unresolved implementation details:

   | Current rule | Required correction |
   |---|---|
   | Missing names in a partially initialized module raise `ImportError` | Attribute access such as `a.x` raises `AttributeError`; `from a import x` can raise `ImportError`. My circular-import probes confirmed the distinction. |
   | A statically bound but unassigned name raises `NameError` | Global lookup can fall through to builtins. After assigning and deleting a global `len`, a function can again call builtin `len`. Local lookup behaves differently. |
   | Function `locals()` is a read-only snapshot | It is a **mutable detached dictionary**; writes do not update the local variables. [Python documentation](https://docs.python.org/3.14/library/functions.html#locals). |
   | Finalization universally runs `__del__` before weakref callbacks | Cyclic disposal has a different sequence, and resurrection can abort disposal. [PEP 442](https://peps.python.org/pep-0442/). |
   | Every float hash must match CPython | NaN hashing depends on object identity. Fixed `PYTHONHASHSEED` does not make it match across processes or runtimes. [Numeric hashing specification](https://docs.python.org/3.14/library/stdtypes.html#hashing-of-numeric-types). |

   Relevant locations are [program initialization](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter dialect specification v0.md:159>), [finalization](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter dialect specification v0.md:175>), and [observable hashes](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter dialect specification v0.md:28>).

   The observability rule also needs refinement: declaring address values unobservable should still preserve useful identity relationships. Excluding every program that makes a decision using an address-derived value is too broad.

   **Required change:** turn these cases into conformance clauses and define comparison under permitted identity renaming. Exempt identity-dependent hash values explicitly, while preserving their required equality and stability properties.

7. **High for the later threaded runtime — The atomic-publication recipe is still incomplete.**

   The [concurrency resolution](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter design document and build plan.md:523>) prescribes relaxed loads and release stores. A relaxed load of a newly published cache-entry pointer does not establish visibility of the entry’s initialized fields. Publication needs an acquire operation or another documented synchronization mechanism. [C++ memory-order specification](https://eel.is/c++draft/atomics.order).

   Additionally:

   - Concurrent collection needs a safe way to inspect the owner’s non-atomic `local` count.
   - Separate atomic fields do not automatically provide a consistent class/version/descriptor snapshot.
   - Replacing cache entries requires a reclamation protocol.
   - Synchronous finalization and queuing finalizers to another thread need a reconciled contract.

   **Required change:** write explicit publication, invalidation, reference-count merging, thread-exit, and collector-snapshot protocols. This can remain outside phase 1, but should not be recorded as resolved merely because fields became atomic.

8. **Medium — The documents still contain competing instructions.**

   The precedence statement helps, but substantial contradictions remain inside the current design:

   - [Section 2](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter design document and build plan.md:26>) still says checker acceptance eliminates speculative boxed paths; its later paragraph correctly requires guards and fallback.
   - The checker configuration forbids global rebinding, while the dialect admits `global` assignment.
   - The island topology table still requires the nonexistent 3.14t stable ABI.
   - Examples retain removed side-table machinery and obsolete cache types.
   - Some scope entries promise every builtin while other entries defer specific builtins.
   - The design says the test suite now contains the rejected arithmetic certificate, but that suite is not among the supplied artifacts.

   **Required change:** apply resolutions directly to the authoritative rules and examples. Keep the review history as history. Pin the exact checker configuration and Python reference build; “whichever 3.14.x is current at build time” is too fluid for exact exception text and reproducible cached artifacts.

**My recommendation is to preserve the architecture and tighten the release contract before expanding it further.** Boxed-first compilation is a sensible way to establish semantics. The current phase-1 list, however, remains a large Python runtime and standard-library project despite the “constrained” label.

The next gate should require:

1. **A dependency-closed phase-1 manifest**, listing supported APIs and required adaptations.
2. **Executable conformance cases for the findings above**, with intentional deviations separated from defects.
3. **A corrected generic object model**, covering dictionaries, descriptors, protocol results, lifetimes, and cache validity.
4. **One complete compilation path exercised on named programs**, using a pinned GCC/libstdc++ toolchain with feature probes.

For the pending decisions, I favor the recursion counter, PEP 393-style strings, Linux-first scope, and truthful implementation identity. Exact set iteration order needs qualification for identity-dependent hashes; it is not solved merely by copying CPython’s set-table algorithm. The 33-month estimate should remain provisional until the dependency manifest and first complete compilation path establish what the team actually has to build.