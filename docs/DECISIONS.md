# Decisions

Taken by the author on 2026-10-30 unless noted. The living documents remain the authority on
rationale; this file is the quick reference agents and reviewers can grep. D-numbers refer to
`docs/deviations.toml`.

## Design decisions (design document, section 12)

| # | Decision |
| --- | --- |
| 1 | The compiler is written in Python; the runtime in C++26. Self-hosting the compiler is a phase-3 stretch goal. |
| 2 | Undeclared attributes live in a per-instance dictionary slot (no shared side table); inline promoted fields migrate into the dictionary when it is exposed. |
| 3 | `__getattribute__` overrides are admitted (tier 2, [P2+]). |
| 4 | Toolchain: the newest GCC at `-std=c++26`, no C++23 fallback profile, Clang not targeted until its reflection and libc++ catch up. libgccjit is not the backend (GPLv3 without the runtime exception; no C++ front end); a C-level IR may be added later for a JIT tier. |
| 5 | Lean 4 is the proof assistant for rung-4 proofs; tools and test-only dependencies may carry licences other than MIT/BSD. |
| 6 | Exceptions cross module boundaries; `std::expected` is used only for locally handled exceptions inside one function. |
| 7 | CPython's defaults are kept wherever a change would risk compatibility (`int` digit limit 4300, recursion limit 1000). |
| 8 | Hypothesis (MPL-2.0) is accepted as a test-only dependency. |
| 9 | Generated C++ is committed as a reviewed build artefact; CI can build from it without running the converter. |

## Dialect decisions (dialect specification, section 12)

| # | Decision | Register |
| --- | --- | --- |
| 1 | Accept the address and identity deviations; identity relationships are preserved up to renaming. | D-01, D-02, D-03 |
| 2 | Recursion limit by a per-call depth counter raising `RecursionError`; cost measured in phase 2. | D-17 |
| 3 | `str` uses the PEP 393 representation (Latin-1/UCS-2/UCS-4 per string, O(1) indexing) with a cached UTF-8 copy for C libraries. | D-13 |
| 4 | Implement CPython's set table algorithm so iteration order matches for value-hashed elements. | D-05 |
| 5 | Hash randomisation on, with the `PYTHONHASHSEED` protocol. | D-14 |
| 6 | Tracebacks: file and line only in release builds; CPython's format in debug builds. | D-06 |
| 7 | Assertions active by default; a build-profile switch that strips them and makes `__debug__` false is planned [P2+]. | D-09 |
| 8 | Control flow leaving `finally` is a compile-time error. | D-10 |
| 9 | `breakpoint()` warns and continues. | D-11 |
| 10 | UTF-8 mode always on. | D-15 |
| 11 | Built-in exception message wording is free for now; structured payloads stay observable; revisit at phase 2. | D-08 |
| 12 | `sys.implementation.name == "bella"`, `platform.python_implementation() == "Bella"`. | D-16 |
| 13 | Shared-container memory model (threads, [P2+]): per-operation atomicity for `list`, `dict`, `set`, nothing stronger. | — |
| 14 | First release targets Linux x86-64 and aarch64 only. | — |
| 15 | Grammar frozen at CPython 3.15 for phases 0-2 (PEP 649 annotations, t-strings, PEP 810 lazy imports and PEP 798 comprehension unpacking included). Revised from 3.14 on 2026-11-01. | — |
| 16 | Stack sizes: 8 MiB main thread, 2 MiB other threads, overridable in `bella.toml`. | — |
| 17 | Project name Bella, MIT licence; tool and file names `bella.toml`, `bella-lint`, `bella-plugin-<name>`. | — |

## Changes after 2026-10-30

**2026-11-01 — the reference moves from CPython 3.14.8 to 3.15.2** (author's decision: the
newest stable release, since Bella has no installed base to keep compatible). 3.16 is at
alpha 1 and cannot be a reference for exact semantics. The move cost nothing in artefacts:
the closure had never been reconciled and the corpus had been recorded on 3.13, and every
test, the model self-check (four seeds), the slice and the int differential pass unchanged
on 3.15.2. Consequences, all applied (repository 2026-11-01; dialect specification v0.4 and the
design document edited and re-exported the same day):

* Applied: `bella.toml`, `manifest.toml`, `.python-version`, `Dockerfile`, `pyproject.toml`
  (the compiler now requires 3.15: its L0 is the host `ast`), decision 15 (grammar at 3.15),
  the corpus re-recorded authoritatively, C-9-02's premise corrected, C-9-07 added.
* Dialect specification v0.4: the pin and grammar (sections 1-3, decision 15); PEP 810 lazy
  imports \[P1\], because eleven phase-1 modules use them, with initialisation at first use
  (sections 3, 7, 8); PEP 798 unpacking in comprehensions \[P2+\], since no phase-1 module
  uses it; `frozendict` and `sentinel` commitments (sections 3, 6); `profiling` in E-03,
  `sys.set_lazy_imports*` in E-04; the cyclic finalisation sequence of finding 5 (section 9);
  D-15 narrowed to the opt-out, `PYTHONIOENCODING` and `encoding="locale"`, all of which
  CPython 3.15 honours (verified); D-18 adds `.start` files and the lazy-imports mode.
* Design document: the island is 3.15t; PEP 803 (`abi3t`, a stable ABI for free-threaded
  builds) makes a stable-ABI bridge possible again, but the version-specific bridge of round
  one's finding 8 stays the baseline until the bridge's API needs are known (sections 10, 10.1,
  13); L0 is 3.15 syntax (section 8). The design never relied on 3.14's incremental collector
  (reverted in 3.14.5 and 3.15), so nothing changed there.
* Still open: the closure tool's first-use edge class for module-level `lazy import` (TODO,
  task 1).

## Pins

| What | Value | Where |
| --- | --- | --- |
| Reference CPython | 3.15.2 (moving it is a spec revision; moved from 3.14.8 on 2026-11-01) | `bella.toml`, `manifest.toml`, the harness |
| Grammar | 3.15 | `bella.toml` |
| C++ | GCC 16.2.0 (`gcc:16.2.0@sha256:07280eb2…`, multi-arch index), `-std=c++26` | `Dockerfile`, `bella.toml` |
| uv | 0.13.6 exactly; it selects the CPython build (python-build-standalone `3.15.2+20261026`), uv-managed interpreters only | `Dockerfile`, `pyproject.toml` `[tool.uv]`, `.python-version` |
| Python dependencies | `uv.lock` (pytest 9.2.0, hypothesis 6.170.14, ruff 0.17.3, mypy 2.4.1, z3-solver 5.3.3.0 on 2026-11-01) | `pyproject.toml` |

## Findings recorded by the executable model (2026-10-31)

1. Exposure must reproduce first-assignment order after promotion: `vars(obj)` lists attributes
   in the order they were first assigned, so the runtime needs a per-object order record for
   promoted fields, as CPython keeps in `_PyDictValues.insertion_order` (one byte per slot).
   The reference model keeps `RefObject.order`; the design document's section 3 should say so.
2. An inline-cache entry that resolves to *instance storage* (a promoted field or a dictionary
   entry) must also depend on the class and version of whatever object the class lookup found
   for that name: a non-data descriptor can become a data descriptor through a change to its
   own class alone, and then it must win over the instance value. CPython's specializer
   avoids the case by never specialising when the class has an attribute of that name; Bella
   records `found_cls`/`found_version` on every entry kind. Found by `refmodel.selftest` on
   its first run with cache-heavy workloads; fixed in `refmodel/objects.py`.
3. C++ argument evaluation order (GCC: right to left) is observable through `print(f(), g())`
   when the calls have effects; the emitter binds every effectful argument to a temporary in
   order (C-2-01). Found by the toy slice on `pipeline/examples/loops.py`.
4. GCC 16.2 ships more of C++26 than design section 10.3 says (2026-11-01, `make probes`, 17/20 on
   both GCC 16.2.0 in the image and Fedora's 16.2.1): reflection (`-freflection`), expansion
   statements, contracts (`-fcontracts`) and `std::simd` in libstdc++ itself (namespace
   `std::simd`, `std::simd::vec<T>`, per P3287/P3441), so no reference `simd` headers are needed.
   Four probes had been failing on their own bugs (a non-transient `constexpr std::vector`, a
   constexpr loop variable over a runtime tuple, a non-const parameter in `post`, the pre-P3287
   `std::simd<T>` spelling). Still missing: `std::execution`, `std::hazard_pointer`, `std::rcu`.
   Section 10.3 of the design document was corrected on 2026-11-01.
5. CPython 3.15 changed two behaviours the corpus records (found by re-recording on 3.15.2;
   both differ on 3.15.0 and 3.15.2 and on no 3.14 release up to 3.14.10):
   * Cyclic finalisation (C-9-02, C-9-07): weak references *with* callbacks are cleared and
     their callbacks run before any finaliser, as before; weak references *without* callbacks
     are no longer cleared first: they still resolve inside `__del__`, are cleared only when
     the object is really freed, and survive a resurrection. 3.14 cleared both kinds first.
   * `del obj.attr` on a missing attribute raises `AttributeError` with `name` set to the
     attribute (C-3-06); 3.14 left it `None`. `name` is a structured payload (D-08 keeps it).
   Also: `ast.Import`/`ast.ImportFrom` gained `is_lazy` (not listed in What's New), and eleven
   phase-1 modules use module-level `lazy import` (TODO, task 1).
6. The 2026-11-01 reviews (astra-low-01/02, gemini-4-argon-high-01): 51 findings, every one
   reproduced or refuted on 3.15.2; verdicts, evidence and the four items that need the author's
   decision (D-1 to D-4) are in `docs/reviews/review-log.md`. Two facts measured along the way
   that the implementation must follow: CPython 3.15 leaves `UnboundLocalError.name` as None
   (NameError carries the name), and a `with` statement looks up `__exit__` before `__enter__`.
