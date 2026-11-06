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

**2026-11-01 — the conformance corpus, first increment of Gate 0 task 2.** 57 cases and 2
excluded-construct cases, every \[P1\] row of spec sections 3 and 7 covered at least once,
recorded on 3.15.2.

* \[P2+\] cases are recorded on CPython and must be refused by the runner: a non-zero exit with
  `[P2+]` in stderr (and the case's `# expect:` text). The compiler's milestone refusals carry
  that marker; spec section 10 asks for a milestone-naming error and does not fix its form.
* A case may declare one registered deviation it differs by; it then has a second expectation,
  recorded on CPython made to show the deviation. D-20 is the only one that can be shown that
  way (the manifest's omissions and the codecs outside the phase-1 set, blocked at start-up).
* The corpus and `pipeline/examples` are type-checked by `make lint` under strict mypy with no
  explicit `Any`, the input contract of design section 2. Fifteen files needed it: deliberate
  dynamism now carries targeted ignores with reasons, and three new cases had real typing
  mistakes, fixed. No recorded expectation changed.
* Measured on the way: a dict mutation that keeps the size does not raise, and iteration then
  follows CPython's entry table (C-6-08); a failed lazy import runs the module again at the next
  use (C-8-06); `copy.deepcopy` of a `frozendict` is a new object, `copy.copy` the same one
  (C-6-05).

**2026-11-01 — the target programs** (author's decision; `targets/`, `docs/targets.md`). Six
programs, an easy and a tricky one for each shape, built and recorded by the author's earlier
session and imported here: `cli_easy_slugs` (stdlib), `service_easy_tokens` (itsdangerous
2.3.0.dev at `672971d`), `data_easy_sales` (humanize 4.14.0 at `38d9d91`), `service_tricky_markdown`
(mistune 3.4.0 at `f7ec702`), `data_tricky_toml` (tomlkit 0.15.2 at `d7def7d`), `cli_tricky_check`
(pycodestyle 2.15.0 at `3cee4cc`); all MIT or BSD-3. Gate 0 task 4 starts with the easy three,
`cli_easy_slugs` first.

* Re-recorded on the 3.15.2 pin (authoritative): identical output to the 3.13.18 recording,
  under both hash seeds, and under the phase-1 configuration (omissions and the codec subset
  blocked, as D-20 is simulated). `make targets-check` runs in `make check` and in CI; recording
  stays a deliberate step (`make targets-record`), as for the conformance corpus.
* The drivers are dialect programs and pass strict mypy (`make lint`; four needed targeted
  ignores, no behaviour change); the vendored snapshots and the input data are excluded from
  ruff and never edited.
* Decided the same day (author): each phase-1 increment is the closure of its target programs:
  1a what the three easy programs reach, 1b what the tricky three add, 1c the rest of the
  manifest. A change of order, not of scope: the easy programs already reach `enum` (`re`'s flags
  are an `IntFlag`) and `typing` (itsdangerous's `Generic` bases), so staging (TODO task 5)
  comes before the first path. Design section 11; review log D-2.
* Decided the same day (author): `unicodedata` stays \[P2+\], and `cli_easy_slugs` lowers its
  requirements instead: it drops non-ASCII characters rather than decomposing them (NFKD), so
  "Zażółć gęślą jaźń" now slugs to `za-gl-ja` (re-recorded). A scope change was avoided, not made.
* Decided the same day (author): licence questions go to a register, `docs/licences.md`, and are
  settled one by one when worth it; work proceeds meanwhile. It holds seven entries, L-01 to
  L-07, among them the PSF licence of the compiled standard library, zlib, the Unicode tables,
  and the source of the hash primitives (items 4 and 5 of `docs/targets.md` section 5).
* Open for the author, before the tricky targets: items 1 to 3 of `docs/targets.md` section 5
  (item 6 is done by `[dynamic]`; item 2's deviation would be D-21).

**2026-11-01 — the phase-1 increments, computed.** `tools/closure.py` takes a target program as
its root (`--target`, `--all-targets`): the driver and its vendored libraries have status
`program`, and a target may declare its own `omissions`, `lazy_unsupported` and `dynamic` entries
in `targets.toml`. `make targets-closure` writes each target's lock and
`targets/closure-summary.json`, which CI requires to be current. 1a (the easy three) is 149
manifest modules and 71,219 compiled source lines; the tricky three add 6 modules plus `optparse`
and `configparser`; 25 manifest modules are reached by no target. Found and fixed on the way:
`typing.TYPE_CHECKING` is false at runtime, so imports under it are dead (itsdangerous's
`typing_extensions`); a bare `import_module(name)` is a computed import (mistune's plugin loader
was missed). Neither changes the standard library's closure. The parked items 1 to 3 of
`docs/targets.md` section 5 wait for the tricky targets.

**2026-11-01 — the target reviews** (astra-low-04, gemini-4-argon-high-03; review log RL-71 to
RL-87). Both reproduced the target locks and the increments. Eleven fixes, each reproduced
first: target closures treat the entry script as `__main__` and observe the program by running
it; per-target declarations merge with the manifest's and must name reached modules; a
program owns only its driver and declared packages; the target oracle compares bytes, with a
time limit, only against an authoritative recording on the pin, and also runs each target in the
phase-1 configuration; the token target records whole tokens and verifies one CPython signed (a
wrong MAC used to pass); `score_candidate.py`, the harness's runner splitting and D-20's wording
corrected. The locks and increments are unchanged. Five points go to the author, D-7 to D-11:
tomlkit's stateful multiple inheritance, `unicodedata` on non-ASCII paths of the phase-1
library, the regex engine, the compile scope of a target, and the copy protocol.

**2026-11-01 — D-7 to D-11 decided** (author; review log D-7 to D-11, spec v0.8, design section
11 rev 444). This changes two decisions taken earlier the same day, as noted.
* D-7: the three tricky targets follow phase 1, not only tomlkit (the author widened option 1).
  Phase 1 is the easy three. The increments decision above said 1b was "a change of order, not
  of scope"; that was wrong for the tricky targets, whose language features (stateful multiple
  inheritance with built-in bases, function metadata at runtime) a module closure does not
  measure. 1b is gone; their recordings stay oracles, their closures are still computed, and
  items 1 to 3 of `docs/targets.md` section 5 move with them.
* D-8: `unicodedata` becomes \[P1\] (option 2), for later revision, because of how much of the
  phase-1 library depends on it: `re`'s parser, `traceback`'s width functions and
  `urllib.parse`'s netloc check call it on non-ASCII input. This reverses option (c) above;
  `cli_easy_slugs` keeps its lowered requirements. The recommendation was the shim (option 1).
  Case C-7-15; licence register L-03.
* D-9: `re` runs on a C++ port of `_sre` under its compiled pure-Python parser and compiler, not
  on PCRE2 (spec section 7). Its licence is a separate register entry, L-08: the `re` package
  and `sre.c` carry Secret Labs AB's notice, redistributable under CNRI's Python 1.6 licence.
* D-10: as recommended. 1a is staged by target, each stage with its own gate: 1a.1
  `cli_easy_slugs`, 1a.2 `service_easy_tokens`, 1a.3 `data_easy_sales` (`targets.toml` stage;
  111, 24 and 14 manifest modules; 1c the other 31). Compiling the whole closure against
  compiling what the closed world reaches, function by function, is measured in TODO task 4.
* D-11: as recommended. Copying through the reduction protocol (`__reduce_ex__`, `__reduce__`,
  `__getstate__`, `__setstate__`, `__getnewargs__`, `__getnewargs_ex__`, `copyreg`'s
  reconstructors) is \[P1\]; the `pickle` module stays \[P2+\]. Case C-3-20. `Logger.__reduce__`
  still refuses `copy.copy(logger)`, since it imports `pickle` (D-3).

**2026-11-01 — Gate 0 task 5, the staging prototype** (`docs/staging.md`; spec v0.9 section 8
and section 3, design section 11 rev 445).
* Mechanism, chosen by the prototype as design section 11 asked, for the author to confirm
  (S-5): code that module bodies generate with `exec`/`eval` is staged by call site and text,
  compiled at build time and found at runtime by the same key. A literal `namedtuple` call is
  also made at build time wherever it sits. An unstaged text stops the program with the E-01
  refusal. Compiler intrinsics were tried for `namedtuple` and lost: no `dataclasses` text, a
  computed `namedtuple` in `inspect` missed, 53 of 58 \[P1\] cases against 58, and CPython's
  templates copied per version.
* Evidence: every \[P1\] case and the three phase-1 targets print CPython's output under the
  replay model (no `exec` but staged code, the annotationlib shim, the D-20 omissions); the dry
  run is identical under two hash seeds. Cases C-8-08 and C-8-09 pin the definition-time
  effects. `make staging-check` runs in `make check` and CI. The model runs the staged code as
  CPython bytecode compiled at build time; `eval1` cannot run a class yet, so it is not used.
* D-5 implemented as a shim and build-time tables: STRING computed by CPython's own fallback
  code on the program's code objects, FORWARDREF from VALUE when every name resolves. Spec
  v0.7's statement that the generated `__annotate__` answers STRING itself was an observable
  difference from CPython, whose function raises `NotImplementedError` (C-3-21). Corrected in
  v0.9, the design otherwise unchanged.
* Found on the way: the phase-1 configuration changes C-7-09's output (`_pydatetime`'s
  `IsoCalendarDate` repr). It is a D-20 effect that no check saw. The case now declares D-20,
  `verify` runs every \[P1\] case in the phase-1 configuration, and D-20 names the effect.
* For the author, S-1 to S-5 in `docs/staging.md`. The pressing one is S-1: under D-5 as
  decided, a dataclass whose annotation names its own class is refused (C-3-22, \[P2+\]). The
  recommendation is a second, compiler-generated entry point per `__annotate__` that makes
  FORWARDREF and STRING exact.

**2026-11-01 — S-1 to S-5 decided, and the staging reviews** (author; `docs/staging.md` sections
8 and 9; review log RL-88 to RL-112; spec v0.10; design section 11 and the shim paragraph, rev 448).
* S-1, as proposed: the compiler generates a second entry point per `__annotate__` (and per PEP
  695 evaluate function) that evaluates the same expressions against the globals and cells it is
  given; the shim calls it where CPython re-runs `__code__`. FORWARDREF and STRING with names not
  bound yet are \[P1\]; evaluating the text of a reference or annotation stays \[P2+\]. This
  changes D-5's carve-out. The build-time STRING tables are gone. Consequence, found by review
  G4: `ast.unparse` is \[P1\], since CPython's FORWARDREF and STRING code calls it.
* S-2: function signatures at runtime stay out of phase 1 (C-3-24), revisited with item 1 of
  `docs/targets.md` section 5.
* S-3, as proposed: an unstaged runtime text is refused, `bella-lint` warns about dataclasses made
  in functions, and spec section 8 holds code and layouts to separate rules.
* S-4: catalogues with Plural-Forms are refused until a target needs them (C-7-16; manifest
  `[refused]`, enforced whether or not the text was staged).
* S-5: staged texts with probes, confirmed. To revisit later: the author's idea of using the GCC
  compiler within the program (`TODO.md`, Later).
* The two reviews of the prototype (astra-low-05, gemini-4-argon-high-04) found wrong-output
  replays, and gaps in the build's dependencies, its input record and its coverage. All 24
  findings are fixed or done, each with a test; the review probes run as one differential test.
  `compile()` is now staged like `exec` and `eval`, and keys drop line numbers.

**2026-11-02 — the staging revision reviewed** (astra-low-06; review log RL-113 to RL-121). Four
findings, each reproduced and now a replay-against-CPython test: evaluator identities could
collide (two aliases on one line; now keyed by source positions as well, duplicates declined),
the dry run compiled strings in its own `__future__` context, `eval`'s whitespace and the
decoding of bytes were not the builtins', and private attribute names were not mangled. `[refused]`
now acts when the function is called, as the manifest says.

**2026-11-02 — the staging revision reviewed again** (gemini-4-argon-high-05; review log RL-122 to
RL-135). Two of its findings were astra-low-06's; one is refuted (running a staged `compile`'s code
object needs no compiler); the rest are fixed, each with a replay-against-CPython test. Among
them: entry points resolve PEP 810 lazy imports as the interpreter does (read from CPython
3.15.2's source; `LOAD_DEREF` does not); PEP 695 evaluate functions keep entry points under PEP
563; the generator covers starred defaults, `IfExp` and f-string annotations, mangled bindings
and type parameters, a class body's `global`, and a walrus in a lambda; artefacts are keyed by
the script's real path and the optimisation level.

**2026-11-02 — the compile scope measured; P-1 and P-2 for the author** (Gate 0 task 4, review
log D-10; `docs/measurements.md`, `tools/scope.py`).
* The measurement: `cli_easy_slugs` executes 7 % of its closure's code objects on its recorded
  run and 11 % with `--help`, a bad argument and other options (19 % and 24 % of the lines). Of
  its 379 executed units, 193 lower to L1 today. The census of what L1 lacks orders task 4's
  plan, A1 to C in `TODO.md`.
* P-1, for the author, is the compile scope. Recommended: the whole closure, with a statement
  the pipeline cannot lower compiled to a refusal that names it. It gives the staging refusal
  (exit 70 and a `bella: refused:` line), the build lists every refused statement, and the gate
  requires the target to reach none. Compile-time `Unsupported` stays the default for the corpus
  and the examples. The alternatives: the whole closure with every unit lowered (this needs
  `match`, 94 generator functions and 40 `async def` that the targets never run, and `async`
  is outside phase 1), or what the closed world reaches. That needs a reachability pass whose
  obligation is that nothing reachable is left out, and it stays an optimisation for later.
* P-2, for the author, is `_collections_abc`'s import-time probes: `async def`, a coroutine
  made and closed, an async generator, and `type(sys._getframe().f_locals)`. Recommended: a
  shim that takes the four types from `_types`, which is core and exports them, as `types`
  does. The alternative is making and closing coroutines in phase 1, with running one refused.
* Found and to be fixed in step A6: the frontend drops function and module annotations and
  PEP 695 type parameters without saying so, which is an approximation that the rules forbid.
  Function annotations and type parameters are fixed in A1/A2: the first are lowered and the
  second refused.
* The author, on how task 4 grows the frontend: constructs come in as AST-rewriting passes onto
  a small L1 core. The lowering need not be 1-to-1 with CPython's internals, and Bella must not
  become another Nuitka, a compiler that keeps CPython's runtime. Exactness is judged on what a
  program can observe. `eval1` may lend CPython's objects to the oracle; the C++ runtime may
  not. TODO task 4's plan is written that way: classes as a pass onto a `build_class` written in
  Python, imports as intrinsic calls, and the remaining forms as desugarings.

**2026-11-02 — P-1 and P-2 decided** (author; spec v0.11 section 7, design section 11 rev 450).
* P-1, as recommended: a stage compiles its target's whole closure. A statement the pipeline
  does not lower yet compiles to a refusal where it would run (`bella: refused:`, exit 70,
  uncatchable). The build lists them, and the gate requires the target to reach none.
  Exclusions and the program's own dialect errors stay compile-time errors. Consequences found
  while recording it:
  * An `async def` statement must be lowered, since class bodies in the closure define
    coroutine functions at import (`_collections_abc`'s `AsyncIterator.__anext__`). Defining
    one is lowered; running a coroutine stays \[P2+\].
  * A refused statement still binds its names for scoping, so its refusal node records them.
  * Generator functions come before step B, since `_collections_abc` defines them at import.
* P-2, as recommended: `runtime/shims/_collections_abc.py` is CPython's module with one marked
  change, the four types imported from `_types` (case C-7-18). `tools/tests/test_shims.py` checks
  that every shim differs from the pinned module only at `bella:` lines, and that this one has
  CPython's namespace and the same four objects. The locks are regenerated (113 modules; 1a.1
  has 72 compiled modules and 5 shims).

**2026-11-02 — P-3 for the author: names the standard library binds by computed name** (Gate 0
task 4 step A5).
* Found: `re` binds `DEBUG`, `A`, `I` and the other flags through `enum.global_enum`, which writes
  `sys.modules[cls.__module__].__dict__` from `enum`. `re._constants` and `inspect` bind names with
  `globals().update(...)` and `globals()[...] =`. Spec section 8 says a bare name bound nowhere in its
  scope chain is a compile-time NameError, and that writes through `globals()` reach statically
  known names. Read that way, `re` is outside the dialect, yet it is \[P1\].
* Recommended: in the closure's library modules (standard library, shims, vendored packages), a name
  the compiler cannot resolve is a runtime global lookup, exactly as in CPython: bound, else builtin,
  else NameError. The compile-time NameError stays for the program's own modules. A later
  optimisation can take the names that module bodies bind from the staging dry run.
* Applied provisionally, and reversible: `wf.check(strict=False)` for library modules; it lists
  the unresolved names.

**2026-11-02 — the easy three run under `eval1` with their whole closures** (Gate 0 task 4,
steps A1 to A6 and B; TODO task 4).
* L1 covers what the three easy targets' closures contain. All 72, 93 and 94 closure modules
  lower whole, and each program prints its recorded output under `eval1` (`make targets-eval1`,
  in CI). This is the second leg of gates 1a.1 to 1a.3.
* `make eval1-corpus` passes 58 of the 75 conformance cases under `eval1`, and none of
  `conformance/eval1-baseline.txt` may regress.
* The lowering follows the author's guidance of the same day: desugaring passes onto a small
  core. Class statements go to a `build_class` written in Python, and `match` to helpers
  written in Python; imports become intrinsic calls under CPython's own import machinery.
  `eval1` lends CPython's objects to the oracle only: functions, generators, PEP 695 objects.
* Found and fixed on the way: builtins called by name in desugarings, decorators stored twice,
  PEP 695 and annotations dropped silently, the module docstring never stored, `eval1`'s late
  imports reached by a program's import hook, an empty keyword dict passed to every call, a
  stale cache keyed by `id()`, and the oracle inheriting the test module's `__future__`.
* Next: the C++ leg (task 3's header, L2, the runtime), and P-3 waits on the author.

**2026-11-02 — P-3 decided; the author's direction for module globals** (author; spec v0.12 section 8,
design section 11 rev 451).
* P-3, as recommended, after a minimal example. A module that uses `enum.global_enum` gets its
  flags written into its namespace from `enum`, so names like `re`'s `DEBUG` are bound nowhere in
  its own source. In the closure's library modules (standard library, shims, vendored packages),
  such a name is a runtime global lookup with CPython's semantics; the program's own modules keep
  the compile-time NameError. `wf.check(strict=False)` implements it for library modules.
* The author's direction for later, in the author's words: "another pass that would actually
  glue these globals together in one global class object for the application". Our reading, to
  be detailed with the author when L2 is designed: once the closed world is known (every module,
  and the staging snapshot of what module bodies bound), a whole-program pass gives every
  module's globals a fixed slot in one application-wide object, so that most global accesses are
  slot accesses and only what stays dynamic is looked up. The likely mechanism is the reference
  model's promoted fields, with a dict made only when exposed (`globals()`, `vars(module)`,
  `sys.modules[...].__dict__`), written into `refmodel/objects.py` first.

**2026-11-02 — the L1 and `eval1` reviews processed** (astra-low-07, gemini-4-argon-high-06 on
`3d4e428..58bb34b`; review log RL-136 to RL-168). 33 findings: 30 fixed, 3 duplicates, none
refuted. Four changes of structure, all inside the design:
* The frontend compiles each parsed tree with the pinned host compiler and drops the code
  (`check_compile`), so a program CPython's symbol table or code generator rejects is rejected
  with CPython's `SyntaxError`. Five findings were instances of the gap. The host is the pinned
  interpreter already (L0 is its `ast`); a self-hosted frontend will need its own checks.
* A function's annotations are lowered by a pass of their own, `desugar-function-annotations`,
  into an `__annotate__` function placed before the function, so every later pass lowers it;
  `to-l1` attaches it to the function. Under PEP 563 a module or class sets up a real
  `__annotations__` mapping (the new `setup_annotations` intrinsic, SETUP_ANNOTATIONS).
* L1's `For` gains `iterator`: a comprehension's outermost loop advances the iterator made where
  the comprehension stands, without a second `iter()` (FOR_ITER).
* `wf1` drops the exemption a `globals()` call gave the whole program: spec section 8 already
  says writes through `globals()` reach statically known names, and P-3's `strict=False` covers
  the library code that needed it. Library provenance comes from the lock where there is one.

**2026-11-02 — the decisions before the C++ leg** (author, asked one at a time with the
measurement or code that bears on each; spec v0.13 section 6, design sections 6, 8 and 11 rev 457,
`docs/l2.md` v1 section 8, `docs/licences.md`).
1. **Big integers: a copy of SEL's `bn`** (`sel/cpp/sel.cpp`, commit `f6df7ff`; MIT, the author's
   own). Bella keeps its own copy in `runtime/`, changed freely (first: entry points that write
   into the object's inline limbs instead of returning a `std::vector`), with a header naming
   SEL's commit and every change, so fixes can be ported back. L-05 settled as own code. The
   Python layer on top is Bella's.
2. **`float` digits from libstdc++** (`std::to_chars`, `std::from_chars`): identical to CPython
   3.15.2 on the pinned GCC 16.2.0, except out-of-range parses, where the wrapper supplies
   Python's infinity or zero. `make float-diff` keeps the differential (in `make check` and CI at
   300,000 cases; every GCC bump runs it at 3,000,000, which on 2026-11-02 compared 3.75 million
   shortest, 1.5 million `.Ne`, 1.5 million `.Nf` and 2.25 million parses: no difference). Python's
   layer is ported. Not taken:
   CPython's `dtoa.c`. **Kept on record as an alternative that may come back**: Bella's own
   Schubfach and Eisel-Lemire on the `bn` copy, the fallback if the differential ever fails or the
   libstdc++ entry (L-09, new, GPL-3.0 with the GCC Runtime Library Exception) is refused. L-06
   settled.
3. **`math` through glibc's libm, linked dynamically**, so a binary returns what CPython returns
   on the same machine. Measured: the same CPython 3.15.2 build on glibc 2.41 (the image) and 2.43
   (this host) differs in the last bit on 33,319 of 2.16 million calls, all in `asinh`, `acosh`,
   `atanh`, `erf` and `erfc` (`math.erfc(2.338130394649152)`: `...389` against `...386`); the
   other 24 functions agreed. Spec v0.13 says so; conformance cases must not print the last bits
   of those functions. glibc gets licence entry L-10 (LGPL-2.1-or-later, dynamic).
4. **L2 v1** (`docs/l2.md` section 8 has the reasons and the rejected options):
   * Reference drops are `release` statements; the exception edge is a rule (newest first, before
     the handler), which C++ unwinding gives.
   * `eval2` runs on host objects, with a `gc.get_referrers` checking mode, explicit unwinding and
     a generated probe per kind of release point, not on the reference model.
   * Types: the slot only, always `object` in phase 1. **A marked gap**: the design's level table
     says every L2 expression carries the oracle's type; that holds from phase 2, when a pass
     produces `Fact.TYPES` (`TODO.md`, task 4).
   * Exceptions are C++ exceptions (design section 12): a throw costs about 1.7 µs against
     CPython's 0.18 µs per raise, so the runtime uses sentinels for the misses it expects and a
     phase-2 pass rewrites the common try-and-catch idioms.
   * Frames: a record on the C++ stack and a guard that, during unwinding, appends the frame to
     the traceback and takes the locals over, so they die with the traceback, as in CPython.
5. **Module globals: no glue pass in phase 1** (dicts, with a per-site cache in the style of
   CPython's `LOAD_GLOBAL_MODULE`); the author's pass comes in phase 2, with the module dict as a
   view over the fields rather than migrated on exposure, written in the model first. Measured: 15
   closure modules expose their own globals, and `dataclasses` exposes every module that defines
   a dataclass.
6. **`eval1` keeps no finaliser traces** (the author: "drop finaliser traces from eval1"). L1 says
   nothing about when an object dies, so `eval2` is the first level exact about lifetimes: the
   lifetime cases compare it with CPython directly, and every other case keeps `eval1 == eval2`.
   This replaces "finaliser traces in `eval1`" in TODO task 3 and design section 11.
7. **The go-ahead for the C++ leg**, in this order: the L2 leg (grammar, `wf2`, printer, `eval2`,
   then `resolve-names`, `to-anf`, `protocol-ops`, `lifetimes`), lifetimes in the model and
   `object.hpp` (task 3, independent of the L2 leg), then the runtime types and the emitter, with
   task 3's done-when before gate 1a.1.
* Corrected on the way: a frame releases its locals in *reverse* slot order
  (`_PyFrame_ClearLocals` walks down from the stack top; locals `a, b, c` die as `c, b, a`), not in
  slot order as the L2 draft said.

**2026-11-02 — L2 v1 implemented: resolve-names, to-anf, lifetimes, wf2, eval2** (`pipeline/l2/`,
`docs/l2.md` sections 4 and 7; the first step of the C++ leg). Within the decisions above, with
these choices of implementation:
* `eval2` translates each L2 code object into a host Python function and runs it, rather than
  interpreting the tree. Temporaries are host locals that `Release` deletes; the exception edge is
  generated code; local, cell and free variables are the host's own, so the host compiler checks
  resolve-names a second time (eval2 refuses a code object whose slot tables differ from L2's).
  This keeps the A+ hygiene by construction (no interpreter loop holding references between
  statements) and runs the corpus in about 20 seconds. The `gc.get_referrers` checking mode is
  still to do.
* The grammar refined while implementing it (docs/l2.md section 4): operands are constants or
  temporaries only; `Loop` owns what it `holds` and has an `orelse` with `EndLoop`; `Copy` and
  `Locals`; `Yield` consumes its value; no `retain`. `protocol-ops` is part of `to-anf`.
* resolve-names agrees with CPython's code objects on the corpus and on every module of the easy
  three's closures, except where L1 differs on purpose (PEP 709's inlined comprehensions, PEP 695
  scopes, unlowered `async` bodies). Four rules found along the way: keyword-only parameters come
  before `*args` in `co_varnames`; cell parameters come first in `co_cellvars`; a `try`'s `else`
  block precedes its handlers in first-appearance order; loading the name `super` uses `__class__`.
  The frontend no longer marks a PEP 563 module's `__annotate__` functions as reading the class
  namespace (CPython's evaluate only strings and have no `__classdict__`).
* `make eval2-corpus` (in `make check` and CI): 62 of 75 cases, every case `eval1` passes and
  three more, the lifetime cases included; `pipeline/tests/test_l2.py` holds the release-point
  probes measured on 3.15.2.
* `make targets-eval2` (in `make check` and CI): the easy three print their recorded output
  under eval2, each with its whole closure. In closure mode every module is lowered to L2 and
  compiled before the program starts (P-1's rule for L1, which the host's own lazy imports also
  require); a function the staging refused or the lock lists as unsupported compiles to a
  refusal (S-4); a staged text is found by the site the calling code object names, so eval2 keeps
  no frame stack of its own.
* The A+ hygiene is in: the checking mode audits every release (`eval2.Interpreter(audit=True)`),
  and 31 kinds of release point are generated probes, each at module level and in a function, all
  equal to CPython and clean under the audit. The probes found an L1 bug: the `with` desugaring
  kept the manager, the bound `__enter__` and the value in synthetic variables until the frame
  ended; it now deletes them where CPython's stack drops them, which `eval1` gains as well. With
  this, step 1 of the C++ leg (the L2 leg) is done; step 2 is lifetimes in the model and
  `object.hpp` (task 3).

**2026-11-02 — lifetimes in the reference model** (task 3; review log RL-20, RL-49; case C-9-08).
* The model counts references: `RefObject` and `RefDict` (an instance dict as an object of its
  own) carry counts that every holder owns, and an object dies at zero with CPython 3.15.2's
  order, measured: its finaliser, its `__slots__` (the most-derived class's first, each class's
  sorted by name, as `type_new` stores them; this said declaration order until review RL-178),
  then its instance attributes in the order of the class's shared keys.
* Shared keys are per class: the sorted `__static_attributes__`, then each name the first time any
  instance stores it or tries to delete it (a failed `del obj.y` inserts `y`; found by the
  Hypothesis machine). So an instance's attributes die in an order that is not its own assignment
  order, and the runtime must keep the per-class key order, beside the per-instance insertion
  order that `vars()` iterates. A dict made by exposure stays split (key order); one installed by
  `obj.__dict__ = d` is ordinary (insertion order).
* A class mutation stores the new value and takes a new version before it releases the old one
  (`type_setattro`), so `CacheEntry.found` can be borrowed: the model holds no count for it and
  fails if an object dies while an entry a live class still validates names it, or if a cached
  lookup reads a dead `found`. A test injects the opposite order and the check fires.
* The oracle compares death logs after every operation (tagged values, `drop`, descriptors that
  die when replaced); the self-test compares about 300 deaths per 5,000 operations.

**2026-11-02 — `object.hpp` from the model** (task 3; design section 3 rev 459). The header is
`runtime/include/bella/object.hpp`, written rule for rule from `refmodel/objects.py`,
single-threaded first as task 3 says. Choices made in writing it, all reversible:
* A 16-byte object header with a plain 32-bit count, a flags word and the object's kind (dealloc
  dispatches on the kind; there are no virtual functions); biased counting, atomics and RCU come
  with threads, as the draft (`docs/drafts/object.hpp.draft`, kept as that target) lays them out.
* Classes are disposed (they leave the live classes and release their attributes, newest class
  first) but not freed: a class's MRO holds itself, so freeing is the cycle collector's (D-04).
* Instance fields, instance dicts and class attributes use standard containers (a vector, and an
  insertion-ordered map of interned names); the compact layouts are phase-2 work.
* A class attribute the model holds as a Python callable (`__get__`, `__set__`, `__getattr__`,
  `__del__`) is a native function object; finalisers that resurrect are refused as not yet
  modelled.
* The checking mode (`heap().checking`) does what the model does: every cached read is compared
  with the generic lookup, and an object dying while an entry a live class still validates names
  it is a ModelError; the quarantine keeps dead objects' memory so a stale read is caught.
Evidence: `make object-test` (in `make check` and both CI jobs) runs the oracle's random programs
three ways in lockstep, the model, CPython and the header through `runtime/tests/object_binding.cpp`
with `ctypes`, comparing every outcome, every death and every attribute after every operation
(six seeds of 5,000 operations locally, about 320 deaths and 108,000 cache hits each; 1,000 more
under AddressSanitizer and UBSan). The second half of task 3's done-when, C-3-01..12 under the
compiled runner, waits for the emitter.

**2026-11-02 — after the L2 and lifetimes reviews** (astra-low-08, gemini-4-argon-high-07; review
log RL-169 to RL-187). Defects fixed within the design; the rules they settle:
* Ownership across user code: a lookup owns what it found while user code runs, as CPython's
  `_PyType_LookupRef` does: the `__getattr__` hook until the operation ends, a descriptor and
  its method while that method runs, a finaliser while it runs. Cache entries stay borrowed
  (RL-20). The header's tests now include user code that empties the class it runs from,
  without quarantine, under ASan (RL-169, RL-187).
* Slot tables: a fast-local slot is allocated where CPython's code generator first emits a
  load, store or delete of the name, dead code included; an annotation alone makes a name local
  without a slot (RL-173). A scope's `global` declarations stop its children from capturing an
  enclosing function's binding (RL-174).
* Release order: a statement's operands die in the reverse of the order CPython's stack holds
  them (STORE\_SUBSCR: key, container, value; STORE\_ATTR: owner, value), and a discarded result
  after its operands (RL-182 to RL-184). An object's `__slots__` die sorted by name per class
  (RL-178).
* Synthetic variables are stack values. A chained comparison's operand is an L2 temporary with
  no slot; a decorator's value moves into a temporary where it is applied; a `match` drops its
  pattern temporaries once the pattern has matched, and after each failed case; a `with`
  statement drops what it holds on every failing path; and when an exception leaves a region,
  the synthetic variables it stored die after its temporaries, newest first (an inlined
  comprehension's iterator and result included). They keep their slots otherwise: invisible,
  and empty when the frame ends (RL-171, RL-172, RL-180, RL-181, RL-185, RL-186). Open: an
  inlined comprehension's iterator dies after its partial result instead of before (`TODO.md`).
* L2 and `wf2`: `return` consumes its value, so a `finally` is checked with what every path into
  it holds (RL-179); unreachable statements are dropped by `to-anf` (RL-177).
* `eval2`'s hygiene: no helper frame stays in a traceback (RL-170); the builtins that read the
  calling frame are recognised by identity at every call (RL-175, about 15 % slower on the
  targets); generated code names nothing a program can rebind (RL-176).

**2026-11-02 — step 3 of the C++ leg: the runtime types and the emitter** (author).
* Where built-in behaviour lives: a C++ core and a Python prelude. C++ holds storage and the hot
  primitives: `Obj`, `int`, `str` (PEP 393), `tuple`, `list`, `dict`, hashing, iteration, the
  call protocol, the exception carrier and the type objects. Whatever is defined by other Python
  operations is Python in `runtime/prelude/` (`__build_class__` and `match` are there already;
  `print`, the containers' `repr`, the exception classes and their `__str__`, `sorted`, `min`,
  `max` and the like join them), compiled by Bella like any program and checked against CPython
  through `eval1` and `eval2`. Less C++ to trust; the prelude is as slow as boxed phase-1 code
  until types reach L3. Rejected: all in C++ (CPython's way), and nearly all in Python over a few
  intrinsics.
* Order: 3a the emitter, from L2, and the runtime core: C-3-01..03 and 05..11 and the slice
  examples compiled, with a compiled-corpus baseline that may only grow; 3b generators (state
  machines, decided) and compiled imports: C-3-04; 3c the cycle collector and weak references,
  in the model first: C-3-12, which closes task 3; then gate 1a.1.
* Taken with it, reversible: one C++ translation unit per module and the runtime as a prebuilt
  library (C++20 modules once compile time is measured); the toy L1 emitter retires when the
  slice examples pass through L2.

**2026-11-03 — typed code stays in phase 2; its types will come from annotations and guards**
(author).
* Until phase 2 the compiled program is an exact C++ rendering of CPython's evaluation: every
  value boxed, every operation a protocol call, every call through the generic path. That is
  where the plan is, not a defect. Decision 3 of `docs/l2.md` stands for phase 1.
* When phase 2 brings types, they come from the annotations the strict type checker accepts
  (design section 2), with exactness checked where values enter a typed function (`int` admits
  `bool` and subclasses that override operators, so a typed version runs only for an exact `int`,
  and the boxed body takes the rest) and Bella's own flow analysis proving what stays exact
  inside. Unannotated code (most of the standard library) stays boxed until inference reaches it.
  This reverses, for phase 2, decision 3's rejection of the checker's types. Rejected: Bella's
  own inference alone (proves less, more work first); annotations as exact contracts (a
  deviation from CPython: `f(True)` for `f(x: int)` is common).
* No veneer: the generated code shows the operation it performs. Overloading C++ operators so
  that boxed dispatch reads like `t3 + t5` was proposed and dropped, because it would hide the
  very cost phase 2 removes.

**2026-11-03 — after the compiled-classes reviews** (astra-low-09, gemini-4-argon-high-08; review
log RL-188 to RL-219; `pipeline/tests/test_review_2026_11_03.py`). Fixes that leave the design
intact, and how they were made:
* `finally` runs once, outside its `try`'s catch: a leaving `return`, `break`, `continue` or loop
  end notes its completion and jumps past the `try`; the exception edge runs the block with the
  exception being handled and rethrows it (RL-192, RL-193).
* Names: every name the emitter makes matches one pattern; a Python name that matches it, or that
  C++ reserves, is escaped injectively; code, function and string names are readable, contain no
  `__`, and do not depend on the hash seed (RL-207, RL-219).
* A name CPython has and the runtime lacks is refused, never NameError or AttributeError: a table
  recorded from the pinned CPython (`tools/cpython_names.py`, checked by `make verify`) is
  consulted when a lookup finds nothing, before `__getattr__` (RL-211, RL-212). The same table
  gives the kind of each built-in attribute, so a method the runtime cannot yet present as CPython
  does (a slot wrapper) refuses its repr and type (RL-218).
* The prelude's exports look like CPython's builtins: a function is a `builtin_function_or_method`,
  a class is immutable; its methods of the C++ types check their receiver (RL-217, RL-218).
* `__getattr__` is called as CPython's `call_attribute` calls it, after the AttributeError is
  dropped, model first (RL-214); the exception frame guards record into is owned by the `PyError`
  that carries it (RL-215); the frontend's stack values die on a function's exception edge before
  its frame is recorded (RL-213).

**2026-11-03 — step 3a.3: one dict type** (design section 3; `docs/emitter.md` section 3a).
* `object.hpp`'s `DictObject` is CPython's compact dict with any key, its hash and `==` supplied
  by the runtime through hooks (identity and text without it, so `make object-test` still runs the
  header alone); the runtime's `Dict` is the same type, and `Kind::PyDict` is gone. An instance's
  `__dict__` is therefore an ordinary dict, as the design's `DictObject` already said.
* An exposed dict stays split while CPython's does, measured on 3.15.2 and modelled first
  (`RefDict.store`, `popitem_`, `clear_`, `copy_`, `owner`): a non-`str` key and `popitem` make it
  ordinary; `clear` keeps it split only while its values are embedded in the live object.
* Views are objects of their own (`Kind::DictView`); what they cannot do yet is refused.

**2026-11-03 — operators on the built-in types** (`docs/emitter.md` section 1). The protocol is
`abstract.c`'s: number slots first, then sequence slots (concatenation, repetition), then a
refusal when the recorded table (`tools/cpython_names.py`, the `binop`, `iop` and `cmp` entries)
says CPython handles that pair of types, else CPython's TypeError. Sets use `setobject.c`'s
algorithms, so a result's iteration order is CPython's.

**2026-11-03 — D-12: where a frame enters a traceback** (review log D-12, RL-221 to RL-227;
`docs/emitter.md` section 1; case C-3-30). Decided by the author as recommended, in two parts:
* Now: a frame is recorded where the exception arrives in it, as CPython's `PyTraceBack_Here` at
  the `error:` label does: at the frame's first catch that sees it (`frame.arrived(e)`, the
  catch's first statement), or at its guard when nothing there catches it, before any handler
  code moves the line on. The `PyError` says which frame has recorded the throw, so the frame's
  own re-raises add nothing, a bare `raise` adds nothing in the frame that re-raises, leaving a
  frame lets the caller record the call, and `raise e` adds an entry. Nothing is added to a path
  without an exception, and an exception the runtime raises and catches inside itself makes no
  entry. Code CPython runs without a frame (the prelude, an inlined comprehension) is marked
  (`Code::shown`) and never recorded. The uncaught report prints the chain, and stdout is flushed
  before it.
* With step 3c: a caught exception keeps its frame's locals (RL-222). The entry will hold a
  frame object that takes the locals at exit only if something still holds it; that delays
  release and allocates nothing lasting, but an exception stored in its own frame's local makes a
  cycle CPython frees only in its collector, so it waits for the collector. Until then those
  locals die at the return, earlier than in CPython.

**2026-11-03 — A subclass of a built-in type is that type's object** (step 3b; decided by the
author, option A of two). An instance of a program's subclass of `dict` (then `int`, `str`,
`tuple`, `list`) is an object of the built-in's kind whose class is the subclass, with the
subclass's attribute storage (its slots, an instance `__dict__`) beside the built-in's data, as
CPython lays it out. Every operation tells an object of the type (`PyDict_Check`, subclasses
included) from exactly the type (`PyDict_CheckExact`) where CPython does, and reaches a
subclass's overrides where CPython does. Measured on 3.15.2: `d[k]` and `d[k] = v` call the
subclass's `__getitem__`/`__setitem__`, `dict.__getitem__` its `__missing__`, a class body
stores through a `__prepare__`'d subclass's `__setitem__`; `update`, `{**d}`, `**d`, `copy`,
`dict(d)` and `d | e` take the dict's own entries unless the subclass overrides `__iter__`, then
`keys()` and `__getitem__`; `copy` and `|` return a plain dict, `fromkeys` the subclass. An `int`
subclass's instance is a boxed int that carries its class; arithmetic on it returns plain ints.
Release order, `subtype_dealloc` then the base's dealloc: the slots, the instance dict, then the
built-in's data (measured: slot, attribute, the dict's entries in order, each key before its
value). Rejected, option B: an ordinary instance holding a hidden built-in object, which every
consumer of a real dict would have to unwrap; one that missed it would answer wrongly instead of
refusing. Model first (`refmodel`), one type at a time, each with a conformance case: `dict` and
`int` first, for `enum` (`_EnumDict`, `IntFlag`).

**2026-11-04 — the author on compiled imports' open points.** Confirmed: `sys.path` is the program's directory (D-18); an ImportWarning has no effect until a `warnings` module loads, then is refused, which is to be looked at again when warnings exist; `_abc` holds strong references until step 3c, when it takes weak ones. The implementation stays `bella`, and programs should know.

**2026-11-05 — the author on the two left open.** `__spec__.cached` and `sys.implementation.cache_tag` are None (D-16 extended), as recommended. `hash()` keeps 63 bits "as long as it's deterministic and functions as hash in general", so the big-int port stays where it is planned; D-22 records it. The condition was not met when it was given: a `__hash__` returning `hash(s)` gave a number the table did not use for `s`, and a proxy key missed half the time. Every hash now fits at one point (`hash_of`), so all readers see one number.

**2026-11-05 — `_abc` (C-7-19).** `runtime/src/abc.cpp` ports `Modules/_abc.c` line by line, with classes in its sets where CPython has weak references, as the author confirmed on 2026-11-04. Taken here: `_get_dump` refuses a set with entries, since what it would show are the references; an unhashable class's error still names `weakref.ReferenceType`, as CPython's does; an object no reference could name is not in a set. A view of a class's `__dict__` needs a dict and a class has a `NameMap`, whose order and versions the caches rely on, so the first view makes a dict that follows the class (`RefClass.class_dict`, `ClassObject::dict_view`). Its second count of each value is always dropped first, so no finaliser can tell (model test `test_a_view_of_a_class_dict_changes_no_death`). The earlier `keys()` returned a list, an approximation this ends.

**2026-11-05 — subscripting a class, `types.GenericAlias` (C-3-36).** `Objects/genericaliasobject.c` is in Python in `runtime/prelude/bootstrap.py`, beside `SimpleNamespace`, and presents as CPython's type (`present_as_c_types`). Its `tp_getattro`, which passes every name but its own on to the origin, is the runtime's (`ClassObject::forwards_attributes`, inherited, checked in `getattr_impl`): a program's class overriding `__getattribute__` stays \[P2+\], and a Python `__getattr__` could not do it, since it runs only after this class's own `__doc__` and `__eq__` have been found. `X | Y` with an alias is refused until `types.UnionType` exists. `dir()` of a class or an object is written with it, a built-in type's names coming from the table of CPython's, since the runtime has only those it has written.

**2026-11-05 — `bytes` and `bytearray` (C-3-37).** `runtime/src/bytes.cpp`, in C++ as CPython's are: one struct for both, every method but `%`, which comes with `str %`. The codecs are what CPython has as fast paths, UTF-8, ASCII, Latin-1 and utf-8-sig, each error range and handler ported from `stringlib/codecs.h` and `unicodeobject.c`. By the phase-1 manifest a name outside its codecs is a LookupError (D-20), and UTF-16 and UTF-32, which it lists, stop by name until written. Text streams now write as UTF-8 mode says (D-15): stdout `surrogateescape`, stderr `backslashreplace`. A class derived from either stays refused, as for `str` and `list`, since it needs attribute storage beside the octets; `memoryview` exists as a name and refuses to be made, \[P2+\].

**2026-11-05 — sorting, and the iterating builtins (C-3-38).** `runtime/src/sort.cpp` is `Objects/listobject.c`'s sort line for line, powersort and galloping included, because which pairs are compared and in what order is what a program's `__lt__` sees; the comparison logs of about 150 inputs are compared byte for byte (`pipeline/tests/test_iteration_builtins.py`). A comparison that raises is held in the sort's state and rethrown once the list is whole again, where CPython's C returns -1 and goes to `fail`. Of CPython's special-case compares only those a program can tell from the general one are kept: `unsafe_object_compare`, which asks again on NotImplemented, and `unsafe_tuple_compare`. `reversed`, `enumerate`, `zip`, `map`, `filter` and `min`, `max`, `sum`, `any`, `all` are Python (`runtime/prelude/iterating.py`), a module of its own because a class with a `__new__` needs `staticmethod` in the builtins, which `builtins.py` puts there only when it finishes. A class derived from them works as a program's own would.

**2026-11-05 — `-fno-tree-pta` for a program's units.** The generated body of C-3-36, one function of 3143 lines with 631 temporaries that have destructors, took GCC 16's `-O1` over 25 minutes and made 24 MB of object code. Without the pass it takes 15 seconds and 1.2 MB. Measured against the default on `fib` and on a workload of objects, dicts and exceptions, the run time is within the noise (3%), and `-fno-tree-sra` does as well; `-fno-thread-jumps` and `-fno-tree-dominator-opts` do not help. The cause inside GCC was not looked for.

**2026-11-04 — finalisers at exit see whole namespaces (RL-281).** `clear_modules` follows `finalize_modules`: sys's special names go, `sys.modules` is emptied, every finaliser reachable from the namespaces runs, then the namespaces are cleared. Rebinding each global to None as it went, as the first version did, made a `__del__` read its own globals as None. Without the collector, a walk from the namespaces stands for `_PyGC_CollectNoFail`; step 3c replaces it. A finaliser runs once (`RefObject.finalize`, PEP 442).

**2026-11-04 — a name a built-in type has of its own is never a base's (RL-310).** A special method CPython keeps in a built-in type's dict and the runtime does not is refused where it is read, instead of answered by `object`'s. `overrides_builtin` walks the MRO for the same reason: the built-in's slot wins over a mixin after it, whether the runtime has the method yet or not.

**2026-11-03 — compiled imports keep CPython's split** (step 3b, `docs/emitter.md` section 4a; case
C-8-10). `runtime/src/imports.cpp` is the C half (`IMPORT_NAME`, `__import__`, `IMPORT_FROM`,
`import *`, the module type), and `runtime/prelude/bootstrap.py` is `importlib._bootstrap`, CPython's
own text with marked changes, run as `_frozen_importlib`. The closed world's registry stands for
`sys.meta_path`, so a `ModuleSpec` and a `SourceFileLoader` are CPython's classes, and what a module's
namespace shows is CPython's. Rejected: the machinery in C++ alone, which would restate 600 lines of
`_bootstrap` with their order of effects and messages, and importing a shim that keeps
`_ModuleLock`, which needs weak references (3c) and threads for nothing a one-thread program can
see. The build finds the program's modules statically, as CPython's finders would, and compiles each
as a unit of its own. E-04 and E-06 keep replacing `__import__` and writing `sys.modules` out of a
program's own code; the runtime follows CPython on those paths because the standard library writes
`sys.modules`, and the case stays inside the dialect. Taken here, for the author to overrule: `sys.path` is `[program directory]` until
the standard library compiles (D-18 says only that it reflects the build); `__spec__.cached` used
3.15's `cpython-315` tag (overruled 2026-11-05: None, D-16); an ImportWarning has no effect
until a `warnings` module is loaded, since nothing else can change the default filters that ignore
it, and is refused from then on. The standard library follows P-1: a program's build compiles its
whole reachable closure, the library's units at `-O0` while speed is not a goal (a fifth of the compile
time; the program's own stay at `-O1`).

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

**2026-11-05 — big ints (C-6-10, ends D-22).** `runtime/src/bn.inc` is SEL's `bn` at `f6df7ff` with no change yet but a header, as decided on 2026-11-02, and `runtime/src/bigint.cpp` is the Python layer on it, written from `Objects/longobject.c` and `Objects/rangeobject.c`. Taken here: `int.hpp` gained `try_add` and its kin, which say that a result does not fit, because `x * 31 & MASK` in a loop must not throw at each step; `int_add` and its kin stay on them for the differential test. A subclass's value beyond the immediates lives in the `IntInstance` as limbs and a sign and not as a `BigInt` it holds, so "its value is no object" (decision 2026-11-03) stays true and nothing changes for the model. A `BigInt` holds a `std::vector` for now: the design's inline limbs, and `bn`'s entry points writing into them (the first change the decision of 2026-11-02 names), come with the first measurement that asks, since they change the speed and not the numbers. A left shift or a power beyond 2**40 bits stops by name; CPython has no such limit and memory decides there. Past `MAX_LONG_DIGITS`, a shift is CPython's own OverflowError. `hash()` returns any int, so hashes are CPython's own and D-22 is gone; the number is not reused. Also found on the way and fixed: `n in range` for an int subclass or a non-int searched by arithmetic or stopped, where CPython iterates (a subclass's `__eq__` is asked); `sys.exit(2**32 + 3)` took the low bits and now does as `parse_exit_code` does; `range.index`'s message was an older CPython's; `Range`'s length overflowed for bounds 2**64 apart; `slice`'s and `range`'s attributes are `member_descriptor`s, and these and `getset_descriptor`s have their repr. New with it: `bin`, `oct`, `hex`, `divmod`, `pow` (with a modulus and inverses), `round`, `int.to_bytes`, `int.from_bytes`, `bit_length`, `bit_count`, `is_integer`, `as_integer_ratio`, `conjugate`, `real`, `imag`, `numerator`, `denominator`, `slice.indices`, `sys.maxsize`, `sys.set_int_max_str_digits`, `sys.get_int_max_str_digits`.

**2026-11-05 — `frozendict` (C-6-11).** A frozendict is a dict with a flag (`FROZEN_DICT`) and its own class, as CPython's `PyFrozenDict_Type` shares `PyDictObject` and `PyAnyDict_Check` covers both: the same table, views and iterators, so that what reads a dict reads it without a word changed. What writes one asks `is_dict` or `is_exact_dict`. No change to the reference model: a frozendict's table is the modelled table, filled while it is being made and never again, with nothing new for look-ups, caches or lifetimes to depend on; `frozen_hash` is a memo of a value that cannot change. A subclass's `__init__` runs and cannot fill it, so everything is done in `__new__`, as CPython's `frozendict_new` does. The depth guard while hashing is 10000 where CPython's is the C stack, and is listed in `docs/emitter.md`. Found on the way and fixed: a wrapper descriptor called on the wrong object now says "requires a 'dict' object" (`dict.__len__(1)`), `del x[k]` says "does not support" unless an index reaches `PySequence_DelItem`, and "got multiple values for keyword argument" names a function as `_PyObject_FunctionStr` does (`__main__.f()`). New with it: `dict.__reversed__`, the three views' `__reversed__` and the three reverse iterators.

**2026-11-05 — `itertools` in Python (C-7-20).** The module is written in Python from `Modules/itertoolsmodule.c`, like `zip` and `map` before it, because a class written in Python gets subclassing, attribute storage and layout conflicts from the object model with nothing to port, and a slow correct path is fine; it can move to C++ type by type when a measurement asks. Taken here: a built-in module may be written in Python (`NATIVE_IN_PYTHON`), run at the first import in a namespace of its own, so that importing it costs nothing to a program that does not, and its helpers are not in the module a program sees. Two primitives exist for it alone, `_held_once` and `_tuple_set`, because the C recycles a result tuple when nothing else holds it and a finaliser can tell: the tuple it keeps is what keeps the last items alive. A slot's name decides when it is released, since a class's slots are released in name order, hence `_a_` and `_b_` where the C's dealloc is not alphabetical. `_tee_dataobject` has a `__del__`, which CPython's does not, to walk a long chain instead of recursing, as `teedataobject_safe_decref` does. Also: `MemoryError` exists now; the names table knows a type by its short name when it has a module in its own (`table_name`), so such a class refuses what CPython's has and it lacks, `types.GenericAlias` included; `__slots__`, `__firstlineno__` and `__static_attributes__` are removed from the prelude's classes, so `hasattr(zip, "__slots__")` is False; `delattr(int, "__doc__")` says "cannot set", as CPython does.

**2026-11-05 — `_operator` in Python (C-7-21).** As `itertools`, for the same reasons, so `operator` is the standard library's own file over it. What the C calls from `Python/abstract.c` is the operator a Python statement compiles to, so most of the module is one line each; the exceptions are `PySequence_Concat` and `PySequence_InPlaceConcat`, which are not `+` and which the runtime gives, and the searches, which are ported. The types are named for `operator`, as CPython's are, and the functions for `_operator`. `_compare_digest` keeps `_tscmp`'s shape, a loop over all of b with no early exit, which is what a Python loop can promise of its timing and no more. Found on the way and fixed: `1 @ 2` and `@=` go through the dispatch and name their own operator, `**=` is named so, and a `__length_hint__` below zero says what 3.15 says.

**2026-11-05 — weak references and resurrection (C-9-10, step 3c's first half).** The model first: `RefWeak`, a list in CPython's order on each object, and `dealloc` holding a count across the finaliser, so that a count left over means the object lives on; the oracle drives them against CPython (`weak_new`, `weak_call`, `weak_drop`, `revive`, `release_kept`) and `make object-test` drives the header in lockstep with both. Taken here: the lists are off to the side and not in the object, because the header has no word for them and few objects have one (two flags say to look); and `weakref.ref` is a prelude class over those records and not a C++ kind, because a program subclasses it (`KeyedRef`, `WeakMethod`) and the object model then gives it storage with nothing to port. Both are for phase 2 to change if a measurement asks. `_tee_dataobject` and everything else that holds a `__del__` for its own reasons keep working, since the finaliser path is the one programs use. Found on the way and fixed: `==` and `hash` of bound methods compare function and object, as `method_richcompare` does, for built-in methods too; `__weakref__` and `__dict__` belong to `object` as descriptors and print so (`<attribute '__weakref__'>`), and go before a class's members (type_ready's order); a member descriptor says "readonly attribute" (`range.start`, `slice.step`, `ref.__callback__`) and has `__get__` and `__set__`; `reversed` asks `PySequence_Check`, which a proxy and a mappingproxy do not pass; `ReferenceError` exists. `collections`, `copy` and `functools` import past `_weakref` now, as far as `_thread` and `complex`.

**2026-11-05 — float (C-6-12).** Before `_thread`, because its `TIMEOUT_MAX` is a float and a stand-in for that name would be an approximation. Boxed: a `Float` object holds the double, and a subclass's instance adds the storage `IntInstance` has (phase 2's unboxing is the immediates' question, not this one's). What the C leaves to `dtoa.c`, the digits, comes from `<charconv>` as decided on 2026-11-02, with one place that needed more: `round(x, n)` for `n < 0` takes `x`'s exact decimal expansion and rounds it by hand, half to even, since `to_chars` takes no negative precision and `_Py_dg_dtoa`'s mode 3 does. Comparison with an int is exact by a shorter road than `float_richcompare`'s: below 2**53 the int is a double, beyond that the float's floor is an int and what is left of the float breaks a tie. The results are the same, and C-6-12 and the sweeps of `pipeline/tests/test_float.py` compare them with CPython on generated values. Found on the way and fixed: a class's own operator method that returned NotImplemented reached the table of operators the runtime lacks, and stopped a program CPython answers with a TypeError; a getset and a member have `__name__`, `__qualname__` and `__objclass__`; `tuple.index` and `tuple.count` exist.

**2026-11-05 — `_thread` with one thread (C-7-22).** The manifest's shim, written from the C as far as one thread can tell: an RLock's owner and a handle's ident are the real thread's, a timed wait on a lock the thread itself holds really takes its timeout and says no, and a blocking wait that nothing could end stops by name rather than hanging, since hanging would be right only with signals, which are not there yet. Creating a thread stops with the milestone's name, as spec section 7 says. Found on the way and fixed: `__slots__` members share `member_descriptor` with the C++ getsets, and the `__set__`, `__delete__`, `__name__`, `__qualname__` and `__objclass__` given to that class in the two commits before this one read them as getsets, so that calling one on a slot crashed the program. A slot now knows its class, and `member_get`, `member_set`, `member_repr` and `descr_check` are there. `getattr`, `setattr`, `delattr` and `hasattr` with a name that is no string said so in 3.12's words, not 3.15's. A function's `__annotate__` is writable, and a function has `__type_params__`, which `reprlib` copies.

**2026-11-05 — `_collections` (C-7-23), and what writing it showed.** `deque`, `defaultdict`, `_tuplegetter` and `_count_elements` are in `runtime/prelude/_collections.py`, ported from the C for what a program can tell: which operations move the iterator's `state` (`reverse` and `d[i] = x` do not), the order in which items die, and the sequence slots' place after a reflected number method. `OrderedDict` stops by name: `collections` imports and a program that does not use it runs, and a pure-Python one would differ in its types (`odict_iterator`) and its `__dict__`. Three things beyond the module. List slice assignment did not exist, and exists now, with its release orders. A field of a prelude class written through `self._x = ...` ran a subclass's `__setattr__`, in every prelude class since `itertools`; `native_slot` in `ops.cpp` stops that for all of them at once, rather than each class going around it. Py_ReprEnter's list is shared with the containers' repr (`builtins.py`), since `defaultdict(self_ref)` depends on it. Seen and not done, for the commits after this one: `set`'s named methods; most of `str`'s; subclasses of `tuple`, `list` and `str`; `complex`. And the exit walk finalises a list's items first to last, where CPython's teardown releases them last to first: step 3c's second half replaces the walk, so it is noted there and not patched here.

**2026-11-06 — `set`'s named methods (C-6-13), and what a walk found.** `union`, `intersection`, `difference`, `symmetric_difference` and their `_update` forms, `isdisjoint`, `issubset`, `issuperset`, `copy`, `clear`, `pop`, `__init__`, ported from the C, including which iterables are hashed and which have their stored hashes read. What a set iterates in is part of what a program sees under a seed, so `pipeline/tests/test_sets.py` walks sets through generated operations and prints them whole, and that found three defects older than these methods. `set_add_entry` reuses the last dummy slot it passes, where the runtime reused the first, written from an older CPython's behaviour; the C says `freeslot = entry`, and a walk says so too. An exact dict's update does one big resize at the start. `difference_update` shrinks a table of more than a quarter dummies. And a set display of constants is not what inserting them leaves: CPython folds it to a frozenset constant and updates an empty set from that, or iterates the constant itself right before GET_ITER. Rather than port the optimizer's idea of a constant, the frontend asks the pinned compiler what it did with the display, which is exact by construction, since the pin is the reference.

**2026-11-06 — `str`'s methods on ASCII (C-6-14).** `lower`, `upper`, `title` and their kin and the `is...` predicates are written for ASCII and stop by name on anything else, because the alternative, passing other characters through unchanged, would be right often enough to go unnoticed. The Unicode database stays open (D-8). `translate` follows `unicode_fast_translate` and its fallback, since a program's mapping can count its lookups, and CPython's messages are kept with their typos ("translatetable", "mustbe"): those are what it says.

**2026-11-06 — the format mini-language and `str.format` (C-6-15).** Written from `Objects/unicode_formatter.c`, `Objects/stringlib/unicode_format.h` and `Python/pystrtod.c`, in `runtime/src/format.cpp`. The digits come from `<charconv>` as decided on 2026-11-02: `dtoa_digits` turns a `to_chars` result into what `_Py_dg_dtoa`'s modes 0, 2 and 3 return, trailing zeros left off, and `format_float_short`'s layout runs on that. `string.Formatter` runs on the standard library's `string` over a small `_string`, whose iterators step the same parsers `str.format` uses. `pipeline/tests/test_format.py` sweeps generated specifications over generated numbers against CPython, because the flags meet each other in the C in ways a list of examples would not reach.

**2026-11-06 — `str %` (C-6-16).** `Objects/unicode_format.c` as it stands in 3.15.2, whose messages now name the argument at fault ("format argument 1: %d requires a real number, not str"). What counts as a mapping is `PyMapping_Check`, so `"x" % []` is `"x"` and `"x" % 1` an error, and a deque, with only sequence slots, is no mapping. A format character beyond ASCII in an error stops by name, since which words it gets depends on whether it is printable, which needs the Unicode database. `bytes %` is `_PyBytes_FormatEx`, its own function, and stops by name until it is written.

**2026-11-06 — `complex` (C-6-17).** `Objects/complexobject.c` as it stands in 3.15.2, with its mixed real forms (`float + complex` leaves the imaginary part alone, so `-0.0 + complex(-0.0, -0.0)` keeps its signs) and C11 Annex G's recoveries. libm's results are what they are on the machine, as for `float ** float`, so case C-6-17 rounds those it records and `pipeline/tests/test_complex.py` compares every digit live. The C's three deprecation warnings stop by name until `warnings` exists: `__complex__` returning a strict subclass's instance, and `complex()` given a complex as `real` or `imag`.

**2026-11-06 — `typing.Union` (C-3-39).** `Objects/unionobject.c` in Python, in `bootstrap.py` beside GenericAlias, since `type.__or__` must work before anything imports `typing`. `is_unionable` has no type alias or sentinel to ask about until those exist. What is not unionable goes to `typing._type_check`, as in the C, so it stops by name until `_typing` exists, and in a program whose closure lacks `typing` after that too: closed-world compilation decides what a run may import. `disallow_instantiation` and `mapping_getitem` on `ClassObject` say what a class statement cannot: no `tp_new`, and a `__getitem__` that is `mp_subscript` alone.
