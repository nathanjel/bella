**Bella is closer to an implementable design, but I still recommend changes before freezing the dialect or object model.** Several previous findings are resolved; the remaining problems are concentrated in lifetime semantics, cache validity, and specification consistency.

I reviewed all three updated files and ran new probes against the pinned **CPython 3.14.8**. The workspace still contains only the three documents, so this evaluates the proposed mechanisms—not a compiler implementation. No files were changed.

The following changes are sound improvements:

- Cache entries now include attribute names, shapes, and subclass invalidation.
- Rich comparison returns an object rather than forcing a Boolean.
- Iterator termination now carries a value.
- Instance dictionaries have stable identity and support replacement.
- Global rebinding, builtin fallback, mutable `locals()`, and import-error distinctions are clearer.
- Synchronous cycle collection is now in phase 1.
- Published pointers use acquire/release ordering, and unresolved threading protocols are explicitly deferred.
- The reference Python version and accepted product decisions are recorded.

I would keep these changes. The findings below need further work.

1. **High — The cyclic-finalization sequence is still reversed.**

   [Dialect §9](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter dialect specification v0.md:179>) says cyclic disposal runs `__del__` first, checks resurrection, and only then clears weak references.

   PEP 442 requires:

   1. Clear weak references and invoke eligible callbacks.
   2. Run finalizers.
   3. Check whether the isolated group was resurrected.
   4. Clear references and dispose of the remaining garbage.

   This is distinct from ordinary refcount-triggered disposal. [PEP 442](https://peps.python.org/pep-0442/#disposal-of-cyclic-isolates).

   My CPython probes produced:

   ```text
   cyclic disposal order: ['weakref', 'finalizer']
   cyclic resurrection: old weakref dead=True, object alive=True
   ```

   **Fix:** correct the normative sequence and add both cases to the conformance corpus. The weak-reference behavior after resurrection makes this more than an ordering preference.

2. **High — Field-backed dictionaries need an independent lifetime model.**

   The [new dictionary mechanism](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter design document and build plan.md:219>) stores entries backed by an owner’s inline fields, while the following paragraph says the dictionary is freed with its object.

   An exposed instance dictionary can outlive its owner:

   ```python
   obj = Example()
   retained = vars(obj)
   del obj
   print(retained)
   ```

   CPython can finalize `obj` immediately while `retained` remains usable. Keeping the owner alive to preserve inline storage would change finalizer timing; retaining raw pointers into freed inline storage would be unsafe.

   There are two related cases:

   - After `obj.__dict__ = replacement`, a retained reference to the **old** dictionary remains independently usable.
   - Two objects can share the same dictionary through `second.__dict__ = first.__dict__`.

   All three behaviors were confirmed locally.

   **Fix:** specify ownership and detachment explicitly. A straightforward first implementation is to move optimized dictionary-backed fields into ordinary dictionary storage when the dictionary is exposed, then route those attributes through that dictionary. Actual `__slots__` fields must remain separate.

   Also replace the literal “some MRO class lacks `__slots__`” test with an inherited layout capability: builtin `object` lacks a `__slots__` attribute, yet a properly slotted subclass still has no instance dictionary.

3. **High — Cache validity remains incomplete, and permanent entries introduce observable retention.**

   The [cache predicates](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter design document and build plan.md:193>) are substantially better, but three cases remain.

   **Inline-field shadowing:** `ClassAttr` checks the instance dictionary, but an attribute may have been assigned into an inline field while the dictionary remains null:

   ```python
   class C:
       x = 1

   c = C()
   read(c)       # caches class attribute
   c.x = 2       # stored inline under the proposed layout
   read(c)       # must now return 2
   ```

   The validity predicate must check all applicable instance storage.

   **Descriptor-type mutation:** adding `__set__` to a descriptor’s class can turn it into a data descriptor, changing lookup precedence without modifying the class containing that descriptor. Bumping the descriptor class and its subclasses does not invalidate caches on the containing class. My probe changed the same attribute lookup from `1` to `99`.

   **Retention:** entries contain an owning `Obj descriptor`, and the [concurrency policy](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter design document and build plan.md:551>) says entries are never freed. An obsolete entry can therefore retain a descriptor after the program replaces it. In CPython, my descriptor finalized immediately on replacement when its last legitimate reference disappeared.

   **Fix:** distinguish permanent cache metadata from references that affect Python object lifetimes. Define invalidation dependencies for descriptor types, include inline storage in shadowing checks, and release obsolete payload ownership appropriately. A bounded allocation count does not make retained objects semantically harmless.

4. **High — `IterStep` preserves the termination value but can still lose the exception.**

   The [new iterator result](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter design document and build plan.md:113>) represents completion with one value. That is sufficient for some loop and generator-delegation paths, but not for unrestricted Python-visible `next()`.

   For example:

   ```python
   class Done(StopIteration):
       pass

   original = Done(7, "payload")

   class Iterator:
       def __next__(self):
           raise original
   ```

   Catching the result of `next(Iterator())` exposes the original subclass, both arguments, `.value`, and the exception’s identity. My probe returned:

   ```text
   Done (7, 'payload') 7 True
   ```

   Reducing this to `Finished(7)` loses information required by the dialect.

   **Fix:** preserve the original exception where it can be observed, or separate the internal loop-advance operation from Python-visible `next()`. Document exactly when converting an exception into a termination result is valid.

5. **High — Staging still needs effect analysis inside definitions, and D-19 has transitive consequences.**

   The [revised staging contract](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter dialect specification v0.md:167>) separates definition statements from runtime effect statements. That distinction cannot be made solely from statement kind.

   Function definitions evaluate defaults and decorators. Class definitions execute class bodies, metaclasses, and hooks. These expressions can allocate resources, mutate state, perform I/O, or raise. [Python function-definition semantics](https://docs.python.org/3.14/reference/compound_stmts.html#function-definitions).

   There is also a lifetime consequence:

   ```python
   def f(resource=Resource()):
       pass

   del f
   ```

   CPython can finalize the default resource when `f` disappears. An immortal function retaining its defaults keeps that ordinary resource alive too. I verified this behavior locally.

   D-19 accepts the collectability difference for frozen definitions, but the text says other objects retain ordinary lifetime semantics. Those promises conflict when frozen definitions retain ordinary objects.

   **Fix:** analyze effects inside definitions and specify ownership of defaults, closures, decorator results, and class attributes. Either explicitly broaden D-19’s lifetime exception or separate immortal compiled metadata from ordinary, reference-counted Python function and class objects.

6. **Medium — The accepted exception-text deviation needs a narrower contract and harness rule.**

   I accept the decision to leave builtin diagnostic wording flexible. However, [D-08 and the observation table](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter dialect specification v0.md:24>) risk treating builtin exception payloads as optional.

   The exemption should not cover:

   - User-provided arguments to builtin exceptions.
   - `KeyError`’s missing key.
   - `OSError`’s errno and filenames.
   - `StopIteration.value`.
   - Structured Unicode-error information.

   Nor does normalizing uncaught-exception reports handle a program that catches an exception and prints or branches on `str(exc)`.

   **Fix:** exempt runtime-generated human-readable wording specifically, preserve structured and user-supplied payloads, and state whether programs depending on exempt wording fall outside the equivalence guarantee. Update the harness definition accordingly; it currently still describes essentially byte-for-byte output comparison.

7. **Medium — The dependency manifest and document reconciliation are still incomplete.**

   Adding the threading shim and library adaptations addresses the examples from the previous review. It does not yet establish the [claimed dependency closure](</home/nathan/workspaces/nth-share/bella/Python → C++26 converter dialect specification v0.md:151>).

   Further inspection of CPython 3.14.8 found:

   - `statistics` imports `bisect`.
   - `collections` imports `keyword` and `reprlib`.
   - `shutil` attempts optional imports of `bz2` and `lzma`.

   The first three are unlisted and therefore deferred under the current rule. The optional imports need an explicit policy: omission with runtime `ImportError`, adaptation, or compile-time rejection.

   There are also direct textual conflicts:

   - The dialect both rejects `import threading` and provides a phase-1 threading shim.
   - `contextvars` and `copyreg` appear in both phase-1 and deferred groups.
   - The design still calls `locals()` read-only in its tier table.
   - Some examples use the removed `overflow` member.
   - The feasibility study still describes dependency-order initialization, projection sorting, deferred counting, and a C++23 fallback.

   **Fix:** generate or record the actual closure against the pinned standard library, including optional imports and adaptations. Treat the feasibility study as historical where appropriate, and remove competing operational instructions from the current design.

**My readiness assessment is now more focused:** the overall architecture and major product choices are suitable for a prototype. The unresolved items above should become executable acceptance cases before their corresponding runtime mechanisms are implemented.

The next deliverable should be small and concrete:

- Correct the cyclic-finalization contract.
- Implement a reference model for dictionary exposure/replacement and cache invalidation.
- Add the demonstrated lifetime, descriptor, and iterator-exception cases to the conformance corpus.
- Produce the actual phase-1 dependency closure.
- Run one complete compilation path against those cases.

The explicit phase-4 deferrals are appropriate. They need not block this single-threaded work, but the claim that stale class/version combinations are always a legitimate interleaving should remain unproven until the snapshot protocol is specified.