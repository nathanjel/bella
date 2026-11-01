# Staging prototype (Gate 0 task 5)

*2026-11-01. The prototype that design section 11 asks for before the first program relies on
staging, and the implementation of review log D-5 (annotations at runtime). Everything below is
reproduced by `make staging-check` (section 9) on the pinned CPython 3.15.2.*

## 1. Summary

Spec section 8 stages definition-time code: a dry run at build time yields the code that
`dataclasses` and `namedtuple` generate with `exec` and `eval`. At runtime the module bodies run
in full, and the generated code is compiled code rather than `exec`. The prototype answers three
questions:

* **Which mechanism.** Stage-time `exec` keyed by call site and text was compared with compiler
  intrinsics for the known users. **Staged texts were chosen**, together with build-time probes
  for `namedtuple` calls with literal fields. Intrinsics generated no `dataclasses` text and
  missed a computed `namedtuple` in `inspect`, so 5 of the 58 \[P1\] cases fail with them.
  They would also copy 516 lines of `dataclasses.py` and namedtuple's template for every
  CPython version (section 5).
* **Does it hold.** All 58 \[P1\] conformance cases and the three phase-1 targets print
  CPython's output under a replay model that has no `exec`. In the model, `exec` and `eval` run
  only staged code, `annotationlib` is the phase-1 shim, and the D-20 omissions are blocked. The
  two new cases pin the definition-time effects: C-8-08 (`@dataclass`) and C-8-09
  (`namedtuple`, `NamedTuple`). Both dry runs are deterministic across hash seeds.
* **D-5.** The `annotationlib` shim answers STRING and FORWARDREF without re-running a code
  object. Its STRING answers come from tables computed at build time by CPython's own fallback
  code (section 6). Spec v0.7 had the generated `__annotate__` answer STRING itself; CPython's
  raises `NotImplementedError` there (C-3-21). Spec v0.9 corrects this.

The run also found a D-20 effect that nothing tested (section 7, F-1, fixed). It found four
questions for the author (section 8), the first of which is significant. Under D-5 as decided,
every `@dataclass` whose annotation names its own class is refused.

This is a model, not the compiler. The staged code runs as CPython bytecode compiled at build
time, the stand-in for the C++ the compiler will emit. `eval1` cannot run a class yet, so the
replay model replaces the done-when's "`eval1` plus the staged artefact". Section 4 lists what
in the model is scaffolding.

## 2. What phase 1 needs, measured

The easy targets on their normal runs reach one string `eval`/`exec` site between them:
`collections.namedtuple`'s `eval` (2, 1 and 3 calls), always while a module is defined.
`dataclasses` is never loaded on those runs. It is in their closures, though: argparse imports
`_colorize` lazily, and `_colorize` defines 15 dataclasses. A program that prints its usage in
colour would reach it.

The dry run of the standard library's phase-1 closure (`closure.lock.json`, 175 modules, run in
the phase-1 configuration) stages 23 `namedtuple` texts and 15 `dataclasses` texts. All come
from module bodies, and none depends on the hash seed. The closure has 13 other `exec`, `eval`
or `compile` sites that stage nothing. They are refused at runtime if reached:

| Site | Reached when | In phase 1 |
| --- | --- | --- |
| `annotationlib` `ForwardRef.evaluate`, `get_annotations` (`eval_str`) | evaluating annotation text | the shim refuses, \[P2+\] |
| `ast.parse`, `codeop`, `dis` | parsing source at runtime | E-01 (`ast.parse` is in `[lazy_unsupported]`, `codeop` a shim) |
| `gettext.c2py` | loading a `.mo` catalogue with a Plural-Forms header | E-01 refusal: the text comes from data (S-4) |
| `hashlib` module body, line 291 | a built-in digest is missing | never: every digest is mapped |
| `inspect._signature_fromstr` | the signature of a C function | E-01 refusal |

Module bodies in the closure read one input between them: `subprocess` reads
`_PYTHON_SUBPROCESS_USE_POSIX_SPAWN` when it is imported (a phase-1 shim). The build-time
annotation tables cover 102 `__annotate__` functions in the closure; none is unstable.

## 3. What was built

| File | What it is |
| --- | --- |
| `pipeline/staging/dryrun.py` | The dry run. It imports the manifest closure, the program's modules and the entry script (under its own name, so the main guard stays false), discards their output, and records every `exec`/`eval` text with its call site, flags and the module body that produced it. It also records inputs and runs the probes. It writes the reviewable artefact (JSON) and the compiled one (marshal). |
| `pipeline/staging/run.py` | The runner: build (both dry runs, cached in `build/staging/`), then run `python SCRIPT` with the replay installed. It serves as `harness.py check --runner` and `run_targets.py check --runner`. |
| `pipeline/staging/boot/sitecustomize.py` | The replay model. It replaces `exec`/`eval`/`compile`, blocks the D-20 omissions and serves the shims. It imports nothing that start-up has not imported. |
| `pipeline/staging/annotations.py` | Build-time answers to annotationlib's `__code__` fallbacks (section 6) |
| `pipeline/staging/scan.py` | Static facts: exec sites named as frames name them, and literal `namedtuple` calls (import aliases resolved) |
| `pipeline/staging/intrinsics.py` | Mechanism 2: the compiler's copy of namedtuple's template |
| `pipeline/staging/check.py` | `make staging-check` |
| `runtime/shims/annotationlib.py` | CPython 3.15.2's module with four replacements, each marked `bella:` |
| `pipeline/tests/test_staging.py` | The refusals the corpus cannot show, the tables against CPython, the scanner, the template |
| `conformance/cases/C-8-08`, `C-8-09`, `C-3-21`, `C-3-22` | Staged dataclass, staged namedtuple, `__annotate__` formats, and the \[P2+\] FORWARDREF boundary |

The conformance harness gained `check --status`. `verify` now also runs every \[P1\] case that
declares no deviation in the phase-1 configuration, and fails it if the output changes (F-1).

## 4. The contract as implemented

* **Key.** A staged text is found by call site (`module:qualname:line`, as the frame names it)
  and by the text itself. The JSON records each text's SHA-256 for review. The replay matches
  on the full text, so there is nothing to collide. The text is compiled at build time with the
  caller's `__future__` flags, as `exec` would compile it.
* **Hit.** At runtime the library still builds the text: `dataclasses` and `namedtuple` run
  unchanged. Only the `exec`/`eval` call is answered with the staged code, run with the
  namespaces it was given. Definition-time effects (`__init_subclass__` running twice for
  `slots=True`, `__set_name__`, class-body statements, a counting default factory, decorator
  order) therefore happen at runtime, once, in CPython's order. C-8-08 prints them.
* **Miss.** Any other text, any code object and any `compile` stop the program with the E-01
  refusal. No `except` clause, `finally` block or `atexit` handler sees it. Output is flushed,
  and the model exits with status 70 (provisional). The message names the site, for example
  `E-01: exec at dataclasses:_FuncBuilder.add_fns_to_class:499 of a text the dry run did not
  stage`.
* **Probes.** A `namedtuple` call with literal fields, anywhere in the program's or the
  closure's source, is made once at build time. Its text is staged even inside a function.
  Computed fields still hit when they spell a staged text, and are refused otherwise.
* **Soundness.** Staged code is compiled from exactly the text CPython would execute, and it
  runs only when the runtime text is that text. A build-time input therefore cannot make code
  staging wrong; it can only make it miss. Spec section 8's rule on recorded inputs matters for
  the other half of staging, the layouts (field sets, MROs) the compiler may use as facts, which
  this prototype does not use (S-3).
* **Scaffolding**, which belongs to the model and not to the contract:
  * The import system and `traceback`'s caret parsing keep the real `exec`/`compile`.
  * The shim finds its table through `annotate.__code__`, which in Bella is metadata the
    compiler attaches to the function it generates.
  * The model makes some objects visible: `sitecustomize` in `sys.modules`, the shim finder in
    `sys.meta_path`, and `annotationlib._bella`.
  * The shims other than `annotationlib` are not written yet. The dry run imports CPython's
    real modules for them and drops texts from modules phase 1 does not have (`ssl`,
    `selectors`, `concurrent.futures`, which real `asyncio` imports).
  * The input recorder sees only `open`, directory listings, processes, sockets and
    `os.environ` reads; it does not see clock reads or random seeding.
  * The STRING and FORWARDREF fallbacks of PEP 695 evaluate functions are refused.

## 5. Mechanisms compared

| | Staged texts, with probes (chosen) | Intrinsics |
| --- | --- | --- |
| \[P1\] corpus, 58 cases | 58 pass | 53 pass: C-3-13, C-7-07 and C-8-08 are refused at a `dataclasses` text, C-7-02 and C-7-14 at `inspect`'s computed `_FrameInfo` (which `traceback` and `unittest` reach) |
| C-8-08 `@dataclass` | passes | refused at `dataclasses:_FuncBuilder.add_fns_to_class:499` |
| C-8-09 `namedtuple`, `NamedTuple` | passes | passes |
| Phase-1 targets | 3 of 3 | 3 of 3 (none builds a dataclass) |
| `namedtuple` texts of the stdlib closure | 23 of 23 | 22 of 23: `inspect._FrameInfo`'s fields are computed (`('frame',) + Traceback._fields`) |
| `dataclasses` texts of the stdlib closure | 15 of 15 | 0 of 15 |
| Literal `namedtuple` inside a function | staged by a probe | generated |
| Recognition | none needed | by binding: `_pydecimal`'s `from collections import namedtuple as _namedtuple` was missed until aliases were resolved |
| Per CPython version | nothing: CPython's own text is recorded | the template of `collections.namedtuple` (lines 388 to 447), and for dataclasses 516 of `dataclasses.py`'s 1,826 lines (`_process_class` and its seven helpers) |

Staged texts need no knowledge of the library and cover any `exec` user a program brings
(attrs, for instance). Intrinsics, by contrast, re-derive what CPython already computes and
diverge silently when CPython changes. The only advantage of intrinsics was that they handle
literal calls inside functions, and the probes give staged texts the same reach.

## 6. Annotations (review log D-5)

* **The function.** CPython's compiler-generated `__annotate__` answers VALUE and
  VALUE_WITH_FAKE_GLOBALS. It raises `NotImplementedError` for FORWARDREF and STRING (C-3-21
  prints this). Bella's must do the same; spec v0.9 says so.
* **STRING.** `call_annotate_function` first evaluates the annotations once with the real
  globals; this probe has visible effects, which C-3-21 prints. It then re-runs
  `annotate.__code__` with globals in which every name is a `_Stringifier`. That result depends
  only on the code, so `annotations.py` computes it at build time. It runs annotationlib's own
  `_StringifierDict`, `_build_closure` and `_stringify_single`, on the pinned interpreter,
  against the code object compiled exactly as the import system compiles the module. The shim
  keeps the probe and returns the table. An exception from that run is recorded and re-raised.
  A form that would not be the same at runtime is marked unstable, and the shim refuses STRING
  for it: a set of strings (whose order depends on the hash seed) or a lambda (whose repr holds
  an address).
* **FORWARDREF.** When every name resolves, CPython's first re-run computes what VALUE computes,
  so the shim evaluates VALUE. When VALUE raises something other than `NameError`, CPython's
  first re-run raises it too, and the result is whatever the second re-run (no globals) does.
  The table records whether that run raises, and what. Anything else needs `ForwardRef` objects
  built from `__code__`, and is refused with `[P2+]`.
* **Evidence.** C-3-13 and C-3-21 pass under the replay. `test_staging.py` checks the tables
  against CPython's runtime answers for a spread of annotation shapes: unions, string forms,
  `Callable`, `Literal`, closures, class scope, a module, a raising annotation, unstable ones.
  C-3-22 is refused.

## 7. Findings

* **F-1 (fixed).** C-7-09 printed `IsoCalendarDate(...)` in the phase-1 configuration and
  `datetime.IsoCalendarDate(...)` on CPython. Phase 1 uses the pure-Python `_pydatetime`, whose
  repr has no module prefix. This is an effect of D-20 that its list did not name, and no check
  saw it, because the harness ran only the cases that declare D-20 in that configuration. Fixed
  three ways: the case declares D-20, `verify` runs every \[P1\] case in the phase-1
  configuration, and D-20 names the effect (spec section 11, `docs/deviations.toml`).
* **F-2.** `@dataclass class Node: next: Node | None` reads its annotations in the FORWARDREF
  format before the class statement binds `Node`. Under D-5 that is \[P2+\], so phase 1 refuses
  every self-referential dataclass, `NamedTuple` and `TypedDict` (C-3-22). See S-1.
* **F-3.** Reading `__doc__` on a dataclass without a docstring calls `inspect.signature`, which
  needs a function's `__code__` (\[X\], spec section 4). The cases avoid it. See S-2.
* **F-4.** `gettext.c2py` executes a text derived from a catalogue's Plural-Forms header, so
  plural translations from `.mo` files are refused at runtime. See S-4.

## 8. Open for the author

* **S-1 FORWARDREF with a name not bound yet (F-2).** This one matters.
  * Option 1, D-5 as decided: such annotations stay \[P2+\], and self-referential dataclasses
    need quoted annotations in phase 1.
  * Option 2: the compiler generates, next to each `__annotate__`, an entry point that evaluates
    the same expressions against a mapping and cells it is given. That is exactly what CPython's
    fallback gets by re-running `__code__`. The shim then runs CPython's own FORWARDREF and
    STRING code unchanged, the build-time tables become unnecessary, and only
    `ForwardRef.evaluate` of an expression stays \[P2+\].
  * Recommendation: option 2, because self-referential dataclasses are ordinary typed Python.
    It needs a conformance case first, and the second entry point in the L2 grammar.
* **S-2 Function signatures at runtime (F-3).** This ties to item 1 of `docs/targets.md`
  section 5, which D-7 moved after phase 1, but phase-1 code reaches it too.
  * Option 1: refuse a dataclass's generated docstring in phase 1, with a lint rule.
  * Option 2: give compiled functions the signature record item 1 proposes, now.
  * Recommendation: option 1 now, revisited with item 1.
* **S-3 Classes made at runtime, and the input rule.** A dataclass made inside a function, or
  any text the dry run cannot see, is refused (E-01). The question is whether that is the
  phase-1 rule, with a `bella-lint` warning for `@dataclass` and `make_dataclass` inside
  functions. Separately, spec section 8's rule on inputs could be stated for layout facts, since
  code staging cannot go wrong through an input (section 4). Recommendation: yes to both.
* **S-4 `gettext` plurals (F-4).**
  * Option 1: an adaptation of `gettext` that interprets the parsed Plural-Forms expression
    instead of executing it.
  * Option 2: refuse it, with a lint rule.
  * Recommendation: option 2 until a target needs translations.
* **S-5 Confirm the mechanism**, staged texts with probes. Spec v0.9 section 8 states it. The
  design said the prototype decides; this asks you to confirm.

## 9. Reproduce

```
uv run make staging-check      # determinism, the P1 corpus and C-3-22, the targets, the comparison
uv run python pipeline/tests/test_staging.py
uv run python pipeline/staging/run.py conformance/cases/C-8-08_staged_dataclass.py   # any program
uv run python pipeline/staging/run.py --mechanism intrinsics conformance/cases/C-8-09_staged_namedtuple.py
```

The standard library's artefact is `build/staging/stdlib-<key>.json`, rebuilt when the lock,
the manifest, the shims or the staging code change. Each program's artefact is under
`build/staging/programs/`.
