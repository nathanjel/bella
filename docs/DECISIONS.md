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

**2026-11-01 — review-log decisions D-2, D-3 and D-4** (author's decisions on the discussion
items of [the review log](reviews/review-log.md); dialect specification v0.5 and the design
document edited and re-exported the same day). D-1 followed the same day (below).

* D-2, the next increment: phase 1 is delivered as 1a (core language and the data-structure
  modules the three target programs need), 1b (`enum`, `dataclasses`, `typing`) and 1c (I/O,
  `re`, `json`, `logging`, `unittest` and the rest). Staging is prototyped on one `@dataclass`
  and one `namedtuple` before 1b relies on it; lifetimes become explicit (retain/release in
  L2, finaliser traces in `eval1`, lifetimes in the model) before the object header; the
  documents are consolidated after Gate 0, with review history in the review log from
  2026-11-01 on and each `PassSpec` status naming its evidence. Design section 11; `TODO.md`.
* D-3, import guards: only `try`/`except ImportError` and `suppress(ImportError)` make an
  import optional, and `[omissions]` holds nothing else. Guards over constants, `__name__` and
  the `[platform]` facts are evaluated at build time (false: dead, true: unguarded); any other
  guard makes an import lazy inside a function and required at module level. Spec section 7,
  design section 10.4, `tools/closure.py`, `manifest.toml` `[platform]`.
* D-4, `traceback` and `codeop`: a shim with CPython's `PyCF_*` values whose compiling
  functions stop the program with the E-08 refusal, which no `except` clause catches (a
  catchable error would be swallowed by `traceback`'s `suppress(Exception)` and drop the
  keyword suggestion silently). E-08 is unchanged for programs. Spec sections 4 and 7, design
  section 10.4, `manifest.toml` `[phase1.shim]`.

**2026-11-01 — review-log decision D-1, and the unit of `[lazy_unsupported]`** (author's
decisions; design document sections 3 and 10.4, dialect specification v0.5 section 7, edited
and re-exported the same day).

* D-1, class versions: one process-wide 64-bit counter, as CPython's type version tags, instead
  of a counter per class. A new class and every mutation of a class or a base take a number
  never issued before, so a cache entry is keyed by the version alone and keeps no class
  pointer (`cls_hint`, the address as an integer, only picks which older entry an install
  replaces); `found_version` is checked through `found`, after the class version matched; 0 is
  never a version, and a class that gets it after 2^64 − 1 numbers is never cached again. No
  per-class limit (CPython's 1000 rations a 32-bit space). Model first (`VersionCounter`, the
  oracle's `recreate_class`), then case C-3-12, design section 3 and
  `docs/drafts/object.hpp.draft`. Review log RL-23.
* `[lazy_unsupported]` refuses the whole function, as before (the alternative was refusing at
  the import statement when it runs): calling an unsupported function raises the
  milestone-naming error on every path through it, so `copy.copy(logger)` is refused in phase 1
  because `Logger.__reduce__` imports `pickle` for an unregistered logger. Support stays a
  build-time property of an API, not of a run.

**2026-11-01 — the phase-1 closure on CPython 3.15.2** (Gate 0, task 1, with the author's go-ahead;
dialect specification v0.6 section 7 and design document section 10.4, edited and re-exported
the same day). `make closure` passes on the pin with 174 modules, and CI requires the committed
`closure.lock.json` to be what the pinned image computes (it is, byte for byte).

* The tool: `first-use` edges for PEP 810 lazy imports, followed as required (spec section 7);
  `[replaced]` for functions an adaptation replaces; `[dynamic]` for the review of every import
  with a computed name; a module has one status, and a provided module is never omitted; the
  lock lists the functions `[lazy_unsupported]` refuses and holds no machine paths.
* `annotationlib` is a shim (`Format`, `ForwardRef` without `evaluate`, `type_repr`): its
  other formats rebuild functions from `__code__` (E-02, E-07), and `dataclasses`, `typing` and
  `functools` need it at staging.
* `_hashlib` (OpenSSL, Apache-2.0) and `_hmac` are omitted, so `hashlib` and `hmac` behave as in
  a CPython built without OpenSSL: `pbkdf2_hmac` and `scrypt` are absent in phase 1. The digests
  stay mapped (BearSSL or libsodium, spec section 7). Revisit if a target program needs either.
  (`_hmac` was mapped after review the same day; see the next entry.)
* Contradictions resolved by spec section 7: `_decimal`, `_datetime` and `_uuid` omitted (the
  pure-Python paths); `_locale`, `_sha2`, `pwd` and `grp` mapped; `_thread` a shim only.
* The codec search must find the ten phase-1 codecs (`encodings.utf_8` and relatives), which are
  compiled and listed in `[dynamic]`; any other encoding raises `LookupError`.
* Unsupported in phase 1: `ast.unparse`, `Path.as_uri`, `Path.from_uri` (they import
  `_ast_unparse` and `urllib.request`). Omitted: `compression.zstd` (for `shutil`) and `fcntl`
  (for `pathlib._os`). `traceback._find_incompatible_extension_module` is replaced (returns None).
* Listed: `_py_warnings`, `pathlib._os`, `_missing_stdlib_info` (compiled), `math.integer` and
  `_math_integer` (mapped), `_types` (core). Removed as unreached on 3.15.2: `pathlib._abc`,
  `pathlib._local`, `_socket`, and `difflib`'s `[lazy_unsupported]` entry (3.15 removed
  `difflib._test`).

**2026-11-01 — the closure reviews** (astra-low-03, gemini-4-argon-high-02; review log RL-52 to
RL-70). Both reproduced the lock byte for byte. Nineteen findings: thirteen fixed, two done, one
deferred, one checked with no issue, two for the author (D-5, D-6).

* The closure tool, each with a test: modules seen only at runtime are traversed; a module
  missing on this machine needs a decision like any other; a handler around a `def` does not
  cover its body; `__lazy_modules__` is read per import in execution order (measured); every
  computed-import site is reviewed by key; every edge is accounted for whatever reached its
  target first; a star import from a built-in binds only its exports (`os.add_dll_directory` is
  dead); the observation blocks omitted modules; dotted dynamic targets reach their parents; a
  nested helper refuses the outermost function; `make lint` uses `$(PY)`.
* `_hmac` is mapped: omitting it made `hmac.digest` reject buffer keys, with no licence reason.
  The Windows-only `_winapi` and `nt` are declared omissions of `ntpath` and `pathlib._os`. The
  closure has 175 modules.
* Spec v0.6 section 7, amended the same day: an unsupported function is the outermost one that
  contains the import, and it exists as an ordinary object; only a call raises.
* Cases C-7-01 (the hashing surface phase 1 keeps; identical with `_hashlib` blocked) and C-7-02
  (`traceback` formats a `ModuleNotFoundError` through the replaced function).
* Open: D-5, annotations at runtime (spec section 8 runs `@dataclass` at runtime, and it calls
  `get_annotations`, which the shim refuses); D-6, registering the observable effects of
  omissions as deviation D-20.

**2026-11-01 — review-log decisions D-5 and D-6** (author's decisions; dialect specification v0.7
and the design document edited and re-exported the same day).

* D-5, annotations at runtime: option 1. Annotations are \[P1\] in the VALUE format, in
  FORWARDREF when every name resolves, and in STRING, through a compiler-generated
  `__annotate__`; only what needs CPython's `__code__` fallback (FORWARDREF with an undefined
  name, `ForwardRef.evaluate`) stays \[P2+\]. The `annotationlib` shim has every public name and
  serves those formats, so `@dataclass`, `NamedTuple`, `TypedDict` and `singledispatch` work while
  the module runs (spec section 8). Case C-3-13 records CPython's behaviour; the implementation
  belongs to the staging prototype (TODO task 5). Spec sections 3 and 7.
* D-6, observable omissions: option 1. Deviation D-20, accepted for phase 1: `hashlib` without
  OpenSSL (`pbkdf2_hmac`, `scrypt` absent, `algorithms_available` equal to the guaranteed set),
  `shutil` with three archive formats, and `LookupError` for a codec outside the phase-1 set.
  Option 2, providing `pbkdf2_hmac` and `scrypt` in the runtime, is a later task (`TODO.md`).
  Spec section 11, `docs/deviations.toml`.

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
   records `found_cls`/`found_version` on every entry kind (since D-1, `found_version` alone,
   checked through `found`). Found by `refmodel.selftest` on its first run with cache-heavy
   workloads; fixed in `refmodel/objects.py`.
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
7. Class versions must never be reissued (2026-11-01, D-1). Once cache entries stopped holding
   their class, the model reproduced RL-23: with versions tied to the class address, a dead
   class's entry was served to the class created at its address on the first seed (a Slot entry
   for a field the new layout does not have), which the model reported as an unsound hit. Per-class counters starting at 0 fail sooner, since two
   live classes share version 0. CPython 3.15.2 placed ten of C-3-12's twelve classes at one
   address.
