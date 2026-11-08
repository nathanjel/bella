# Staging prototype (Gate 0 task 5)

*2026-11-01. The prototype that design section 11 asks for before the first program relies on
staging, and the implementation of review log D-5 (annotations at runtime) as decision S-1
changed it. Revised the same day after reviews astra-low-05 and gemini-4-argon-high-04, and on 2026-11-02
after astra-low-06 and gemini-4-argon-high-05 (section 8). Everything
below is reproduced by `make staging-check` (section 10) on the pinned CPython 3.15.2.*

## 1. Summary

Spec section 8 stages definition-time code. A dry run at build time yields the code that
`dataclasses` and `namedtuple` generate with `exec` and `eval`. At runtime the module bodies run
in full, and the generated code is compiled code rather than `exec`. The prototype answers three
questions:

* **Which mechanism.** Stage-time `exec` keyed by call site and text was compared with compiler
  intrinsics for the known users. Staged texts were chosen, with build-time probes for
  `namedtuple` calls with literal fields (the author confirmed this, decision S-5).
  * The comparison is one of coverage and maintenance cost. The intrinsic prototype covers
    `namedtuple` only, so the 6 \[P1\] cases it fails do not show that intrinsics could not
    cover them.
  * Staged texts need no knowledge of the library. Intrinsics would copy CPython's templates
    for every version (section 5).
* **Does it hold.** Under a replay model that has no `exec`, the 60 \[P1\] conformance cases and
  the three phase-1 targets print CPython's output, and the [P2+] cases the model can refuse are
  refused. In the model:
  * `exec` and `eval` run only staged code;
  * `annotationlib` is the phase-1 shim;
  * the D-20 omissions are blocked.

  The dry runs are deterministic across hash seeds. The conclusion is narrower than "staging is
  sound": these programs reproduce CPython's output under this model. The reviews found probes
  where an earlier version gave wrong output or refused what CPython runs. They are fixed, and
  each probe now runs as a test against CPython (section 8).
* **Annotations.** The compiler generates a second entry point for each `__annotate__`, which
  evaluates the same expressions against the globals and cells it is given (decision S-1). The
  `annotationlib` shim calls it where CPython re-runs `__code__`. FORWARDREF and STRING are
  therefore CPython's, `ForwardRef` objects for names not bound yet included. The generator is
  prototyped here and checked against CPython for every annotate function of the closure
  (section 6).

This is a model, not the compiler:

* The staged code and the entry points run as CPython bytecode compiled at build time, the
  stand-in for the C++ the compiler will emit. Compiling them through L1 to C++ is task 4.
* `eval1` cannot run a class yet, so the replay model replaces the done-when's "`eval1` plus the
  staged artefact".
* The other half of staging, the layouts the compiler may take as facts, is not prototyped.

## 2. What phase 1 needs, measured

The easy targets on their normal runs reach one string `eval`/`exec` site between them:
`collections.namedtuple`'s `eval` (2, 1 and 3 calls), always while a module is defined.
`dataclasses` is never loaded on those runs. It is in their closures, though: argparse imports
`_colorize` lazily, and `_colorize` defines 15 dataclasses.

The dry run of the standard library's phase-1 closure (`closure.lock.json`, 175 modules, run in
the phase-1 configuration) stages 23 `namedtuple` texts and 15 `dataclasses` texts. It
generates 103 entry points for annotate and PEP 695 evaluate functions. The only two annotate
functions without one are hand-written, in `dataclasses` and in typing's TypedDict, and both
answer every format themselves. Fourteen `exec`, `eval` or `compile` sites in the closure stage
nothing of the standard library's own and are refused at runtime if reached with a text the
build did not see:

| Site | Reached when | In phase 1 |
| --- | --- | --- |
| `annotationlib` `ForwardRef.evaluate`, `get_annotations` (`eval_str`) | evaluating the text of a reference or annotation | the shim refuses, \[P2+\] (C-3-23) |
| `annotationlib` `ForwardRef.__forward_code__` | `typing` building a reference from a string (it compiles it eagerly) | staged when a module body does it (a quoted annotation in `Optional["Node"]`, a `NamedTuple` under PEP 563); otherwise refused with `[P2+]` (manifest `[unstaged]`) |
| `ast.parse`, `codeop`, `dis` | parsing source at runtime | E-01 (`ast.parse` is in `[lazy_unsupported]`, `codeop` a shim) |
| `gettext.c2py` | loading a catalogue with a Plural-Forms header | refused by the manifest's `[refused]` table, \[P2+\] (C-7-16) |
| `hashlib` module body, line 291 | a built-in digest is missing | never: every digest is mapped |
| `inspect._signature_fromstr` | the signature of a C function | E-01 refusal |

Module bodies in the closure read two inputs between them: `subprocess` reads
`_PYTHON_SUBPROCESS_USE_POSIX_SPAWN` when it is imported, and `optparse` (a root since 2026-11-08)
reads `LANGUAGE`, `LC_ALL`, `LC_MESSAGES` and `LANG` through `gettext`, whose translation lookups
its module body runs for its messages. That is what the recorder sees since
the review's A5-3 fix, which tests show records a body's own reads, reads through a helper and
directory listings. It does not see existence checks (`os.path.exists`, `os.stat`), clock reads
or random seeding. So this is an inventory of what it records, not proof that module bodies read
nothing else.

## 3. What was built

| File | What it is |
| --- | --- |
| `pipeline/staging/dryrun.py` | The dry run. It imports the manifest closure, the program's modules and the entry script (as `__bella_entry__`, reported as `__main__`, so the main guard stays false), discards their output, and records every `exec`, `eval` and `compile` with its call site, operation, text, parameters and outcome. Every module loaded from outside the standard library is the program's, its lazy imports resolved. It also records inputs, runs the probes, and generates the entry points. It writes the reviewable artefact (JSON, with every source it depends on, by content) and the compiled one (marshal). |
| `pipeline/staging/run.py` | The runner: build (both dry runs, cached in `build/staging/` while their sources are unchanged), then run `python SCRIPT` with the replay installed. It serves as `harness.py check --runner` and `run_targets.py check --runner`. |
| `pipeline/staging/boot/sitecustomize.py` | The replay model. It replaces `exec`/`eval`/`compile`, blocks the D-20 omissions, serves the shims, applies `[refused]` and `[unstaged]`, refuses the locks' unsupported functions and `inspect`'s signatures (S-2). It imports nothing start-up has not imported. |
| `pipeline/staging/annotations.py` | The entry-point generator, for annotate and PEP 695 evaluate functions, and its build-time checks against CPython (section 6) |
| `pipeline/staging/annotate_rt.py` | The name loads the entry points use, one per opcode |
| `pipeline/staging/scan.py` | Static facts: exec sites named as frames name them, and literal `namedtuple` calls (import aliases resolved) |
| `pipeline/staging/intrinsics.py` | Mechanism 2: the compiler's copy of namedtuple's template |
| `pipeline/staging/check.py` | `make staging-check` |
| `runtime/shims/annotationlib.py` | CPython 3.15.2's module with eight changes, each marked `bella:` |
| `pipeline/tests/test_staging.py` | The refusals the corpus cannot show, the review probes replayed against CPython, regressions for A5-1 to A5-4, the generator against a corpus of scope shapes and under mutation, the scanner, the template |
| `conformance/cases/` | C-8-08 and C-8-09 (staged dataclass, namedtuple), C-3-21 (`__annotate__` formats, exception arguments), C-3-22 (FORWARDREF and STRING with names not bound yet, \[P1\]), C-3-23, C-3-24 and C-7-16 (the \[P2+\] boundaries), C-7-17 (a catalogue without plural forms) |

The conformance harness gained `check --status`. `verify` now also runs every \[P1\] case that
declares no deviation in the phase-1 configuration, and fails it if the output changes (F-1).
The manifest gained `[refused]` and `[unstaged]`; `tools/closure.py` scans a shim's own source,
and `ast.unparse` is \[P1\] (`_ast_unparse` compiled), since the shim's FORWARDREF and STRING
call it.

## 4. The contract as implemented

* **Key.** A staged text is found by the function it is called from (`module:qualname`, as the
  frame names it), the operation (`exec`, `eval` or `compile`) and the source as given, `str` or
  `bytes`, before any preprocessing.
  * It is compiled with the caller's `__future__` flags and the builtin's own preprocessing:
    `eval` strips leading spaces and tabs, and bytes are decoded by their PEP 263 declaration.
    The dry run runs that same code, in the caller's context, so what it discovers is what
    CPython would (A6-2). For `compile`, the key
    also holds the mode, file name, flags, optimisation level and module name. At runtime the
    flags and the optimisation level must match, or the call is refused.
  * A `compile` stages its outcome: the code, or the exception with its arguments. That is how
    `typing`'s eager compile of a string forward reference works, `SyntaxError` included.
  * The JSON records each text's SHA-256 for review; the replay matches on the full text.
  * The line is not in the key: a shim's lines differ from CPython's module's, and the rest
    identifies the code. An artefact belongs to one pin, one script (by its real path), one
    optimisation level and one content of each source, and is rebuilt when any changes.
* **Hit.** At runtime the library still builds the text: `dataclasses` and `namedtuple` run
  unchanged. Only the `exec`/`eval` call is answered, with the staged code, run with the
  namespaces it was given. Definition-time effects therefore happen at runtime, once, in
  CPython's order: `__init_subclass__` running twice for `slots=True`, `__set_name__`,
  class-body statements, a counting default factory, decorator order. C-8-08 prints them.
* **Miss.** Any other text, and any code object that a staged `compile` did not return, stop the
  program with the E-01 refusal.
  * No `except` clause, `finally` block or `atexit` handler sees it. Output is flushed, and the
    model exits with status 70 (provisional).
  * The message names the site, for example `E-01: exec at
    dataclasses:_FuncBuilder.add_fns_to_class:499 of a text the dry run did not stage`.
  * A dataclass made inside a function is refused only when no identical text was staged. That
    is the rule; `bella-lint` warns about such definitions (S-3).
* **In a compiled program** (`runtime/src/staged.cpp`, `staged_tables` in `pipeline/build.py`) each recorded text of a site in the
  program's closure is lowered through L2 and compiled into the binary, one unit per distinct text. A hit runs its body in a
  `Module` made for the call, as long-lived as its functions: its globals are the dict given, and its builtins are what that
  dict's `__builtins__` said at that moment, as `_PyEval_BuiltinsFromGlobals` does. A program's own module body is only dry-run
  when its source could stage anything; otherwise its texts miss and stop with E-01, as any unstaged text does.
* **Policy refusals.** A function in the manifest's `[refused]` table is refused when it is
  called, malformed input included (`gettext.c2py("bad")` is refused, not a catchable
  `ValueError`), and whether or not its text was staged. C-7-16 needs the latter: the dry run of
  its module body loads the catalogue, so the text is staged.
* **Probes.** A `namedtuple` call with literal fields (by position or by keyword), anywhere in
  the program's or the closure's source, is made once at build time, so its text is staged even
  inside a function.
* **Unsupported functions.** The replay refuses what the closure locks list as unsupported, as
  phase 1 does; without that, the model hid that `ast.unparse` was one of them (G4 3.2).
  Computed fields still hit when they spell a staged text, and are refused otherwise.
* **Code and layouts are separate contracts** (S-3). Staged code is compiled from exactly the
  text CPython would execute, in its compilation context, and runs only when the runtime text is
  that text. An input can make it miss but not make it run the wrong code. A layout (field set,
  bases, descriptors, MRO) is a fact compiled code would rely on, which exact text does not
  establish. Spec v0.10 section 8 keeps the input rule for layouts. This prototype uses none,
  and the layout obligation stays open (`TODO.md`).
* **Scaffolding**, which belongs to the model and not to the contract:
  * The model does not reject what the compiler rejects at build time. A program's own `exec`
    or `eval` is E-01 there; in the model only the runtime half shows. A staged `compile`'s code
    object may run anywhere, since it needs no compiler.
  * The import system and `traceback`'s caret parsing keep the real `exec`/`compile`.
  * An entry point is found through `annotate.__code__`, which in Bella is attached by the
    compiler.
  * The model makes some objects visible: `sitecustomize` in `sys.modules`, the shim finder in
    `sys.meta_path`, `annotationlib._bella`, and `inspect.__loader__` (wrapped for the S-2
    refusal).
  * A traceback through an entry point shows its helper frames.
  * The shims other than `annotationlib` are not written yet. The dry run imports CPython's
    real modules for them and drops texts from modules phase 1 does not have (`ssl`,
    `selectors`, `concurrent.futures`, which real `asyncio` imports).
  * A hand-written `__annotate__` reaching FORWARDREF's fallback is called once with
    VALUE_WITH_FAKE_GLOBALS and the real globals. If it raises `NotImplementedError`, the answer
    is VALUE, as in CPython; otherwise the program is refused, after that call.

## 5. Mechanisms compared

| | Staged texts, with probes (chosen) | Intrinsics (`namedtuple` only) |
| --- | --- | --- |
| \[P1\] corpus, 60 cases | 60 pass | 54 pass. C-3-13, C-3-22, C-7-07 and C-8-08 are refused at a `dataclasses` text; C-7-02 and C-7-14 at `inspect`'s computed `_FrameInfo`, which `traceback` and `unittest` reach |
| Phase-1 targets | 3 of 3 | 3 of 3 (none builds a dataclass) |
| `namedtuple` texts of the stdlib closure | 23 of 23 | 22 of 23: `inspect._FrameInfo`'s fields are computed (`('frame',) + Traceback._fields`) |
| `dataclasses` texts of the stdlib closure | 15 of 15 | 0 of 15: not implemented |
| Literal `namedtuple` inside a function | staged by a probe | generated |
| Recognising the calls | none needed | by binding: `_pydecimal`'s `from collections import namedtuple as _namedtuple` was missed until aliases were resolved |
| Per CPython version | the artefact is rebuilt (sites carry line numbers); no library logic is copied | as left, plus the template of `collections.namedtuple` (lines 388 to 447), and for dataclasses 516 of `dataclasses.py`'s 1,826 lines (`_process_class` and its seven helpers) |

Staged texts reuse the pinned library's own generator and preserve the calls that have effects.
Intrinsics re-derive what CPython computes, and would diverge silently when CPython changes its
templates. The one thing intrinsics handled that staged texts did not, literal calls inside
functions, the probes now cover.

## 6. Annotations (D-5, decision S-1)

* **The function.** CPython's compiler-generated `__annotate__` answers VALUE and
  VALUE_WITH_FAKE_GLOBALS. It raises `NotImplementedError` for FORWARDREF and STRING (C-3-21
  prints this), and Bella's does the same.
* **The fallback.** `call_annotate_function` then re-runs `annotate.__code__` against
  substitute globals and cells. For STRING every name is a `_Stringifier`. For FORWARDREF, real
  names are real values and missing ones become `_Stringifier`s turned into `ForwardRef`s; a
  second run has no globals at all.
* **The entry point** (`annotations.py`) is what the compiler generates instead: a function
  `__annotate__(format, globals, cells)` that evaluates the same expressions in the same order.
  Every name load is done as its opcode does it (`annotate_rt.py`): `LOAD_GLOBAL`, `LOAD_DEREF`,
  and in class scope `LOAD_FROM_DICT_OR_GLOBALS` and `LOAD_FROM_DICT_OR_DEREF`. That includes
  which `__getitem__` and `__missing__` run. It also includes PEP 810 lazy imports: one found by
  a global load or in a class namespace is resolved and written back, and one in a cell is not. The generator works from the source, as the compiler
  will. It knows:
  * scopes and bindings: `global`, also in a class body; `nonlocal`; type parameters; a walrus
    in a comprehension, but not in a lambda inside it;
  * name mangling, of names and attribute names (not keyword-argument names), of a method's
    bindings, and of type parameters (a class's own bounds and defaults are not mangled);
  * which module and class annotations are conditional, and their indices: all of a module's,
    only those under a compound statement in a class;
  * `*args: *Ts` and the two result shapes.
* **The shim** (`runtime/shims/annotationlib.py`) is CPython's module with eight marked changes:
  * the three function rebuilds call the entry point;
  * `_build_closure` reads the entry point's free variables;
  * `ForwardRef.evaluate` of an expression and `eval_str=True` refuse with `[P2+]`;
  * `__resolved_str__` fixes names on a copy of the tree instead of re-parsing its string;
  * FORWARDREF of a hand-written annotate function does what CPython's code does when that
    function raises `NotImplementedError`;
  * the header.

  An annotate function the compiler did not generate has no entry point. If its fallback needs
  the re-run, it is refused. The same entry points serve PEP 695 evaluate functions: type-alias
  values, bounds, constraints and defaults.
* **Identity.** An entry point is filed under its function's file, qualified name, first line,
  and a hash of every instruction's source position (`annotate_rt.entry_key`), which the replay
  computes the same way for a live function. Two definitions with one name on one line therefore
  differ, and a duplicate identity is declined, never overwritten (A6-1).
* **Checked at build time**, for every annotate function. An entry point is kept only if both
  checks agree:
  * its loads (kind, name, order) are the bytecode's;
  * under STRING's and under FORWARDREF's second-run environment, it returns or raises what
    re-running CPython's code does.

  Breaking name resolution or the conditional indices makes the checks fail, and the tests
  mutate the generator to prove it. Over the closure and the corpus no annotate or evaluate
  function mismatches; 2 are declined, the hand-written ones.
* **Evidence.**
  * C-3-13, C-3-21 and C-3-22 print CPython's output under the replay. C-3-22 covers a
    self-referential dataclass, names defined later, class attributes, private names, a closure
    variable before and after binding, conditional module annotations, an annotation with an
    effect, and exceptions with their arguments.
  * C-3-23 is refused.
  * The generator's own corpus covers the remaining shapes: type parameters, nested classes,
    `global`, `nonlocal`, `*Ts`.

## 7. Findings

* **F-1 (fixed).** C-7-09 printed `IsoCalendarDate(...)` in the phase-1 configuration and
  `datetime.IsoCalendarDate(...)` on CPython. Phase 1 uses the pure-Python `_pydatetime`.
  * The case now declares D-20, and `verify` runs every \[P1\] case in the phase-1
    configuration.
  * D-20 names the difference. Since the review, D-20 accepts only the listed differences.
* **F-2 (decided, S-1).** A dataclass whose annotation names its own class reads FORWARDREF
  before the name is bound. The entry point makes this \[P1\] (C-3-22).
* **F-3 (decided, S-2).** A dataclass's generated docstring calls `inspect.signature`, which
  needs function metadata. It is \[P2+\] (C-3-24, refused in the model where `inspect` reads it).
* **F-4 (decided, S-4).** `gettext.c2py` executes a text derived from a catalogue, so such a
  catalogue is refused with `[P2+]` (C-7-16). A catalogue without Plural-Forms loads (C-7-17).

## 8. Reviews of 2026-11-01

Findings A5-1 to A5-5 were all reproduced before anything changed, and are review log RL-88 to
RL-92:

* **A5-1.** An `eval` could run code staged for an `exec` at the same site. The key now
  includes the operation, and the caller's flags are checked.
* **A5-2.** Changing an imported module's annotation reused a stale artefact. The artefact now
  lists every source it was made from, by content, and is rebuilt when one changes.
* **A5-3.** The input recorder dropped a module body's own reads, because an importer is always
  further down the stack. Only the frame that performed the operation decides now.
* **A5-4.** A crashed harness could pass the evidence gate. A non-zero exit or a missing summary
  now fails it, and a refusal is checked as a refusal: exit 70 and the line.
* **A5-5.** Recorded exceptions were rebuilt from their text, losing `args`. The build-time
  tables are gone with S-1, and exceptions are the real ones (C-3-21, C-3-22).

The review's comments on S-1 to S-5 are reflected in sections 1, 4, 5 and 6, and in D-20's
wording.

Review gemini-4-argon-high-04's findings were reproduced on `b838bc5` in a separate worktree, then
on the working tree, and are review log RL-99 to RL-112. Its probes now run as one test that
replays each and compares it with CPython:

* **3.1.** `typing` compiles every string forward reference when it builds one, and the shim
  refused there. That broke `Optional["Node"]` and every `NamedTuple` or `TypedDict` under PEP
  563. `compile()` is now staged, and the refusal is on `evaluate` of an expression.
* **3.2.** The shim calls `ast.unparse` (made \[P1\]) and, in `__resolved_str__`, `ast.parse`
  (replaced by fixing a copy of the tree). The closure tool now scans shims, and the replay now
  refuses unsupported functions.
* **3.3.** The entry was dry-run under its file stem. Its own sites missed, an entry named like
  a stdlib module collided with it, and `-P` was ignored.
* **3.4.** Sibling modules, and lazily imported ones, were not covered.
* **3.5.** FORWARDREF refused hand-written annotate functions and PEP 695 evaluate functions
  that CPython answers. The scan missed keyword `namedtuple` arguments and `builtins.exec`, and
  `exec(text, closure=...)` dropped `closure`.

Review astra-low-06, on the revision, is review log RL-113 to RL-121, each probe now a test:

* **A6-1.** Two type aliases named alike on one line shared an evaluator identity, and the
  replay printed the wrong one. Identities now include the instructions' source positions.
* **A6-2.** The dry run compiled strings in its own context, a file with PEP 563, not the
  caller's.
* **A6-3.** `eval`'s whitespace stripping and the decoding of bytes by declaration were missing.
* **A6-4.** Private attribute names were not mangled. The build caught it and declined; the
  runtime now says so.
* **Notes.** `[refused]` acts on entry to the function; the lock names a shim's own source;
  the description of misses is corrected.

Review gemini-4-argon-high-05, on the same revision, is review log RL-122 to RL-135. Its 3.2
and 3.7.3 were A6's. Its probes now run as tests:

* **3.1.** Lazy imports leaked unresolved into FORWARDREF; the loads now resolve them as
  CPython's interpreter does.
* **3.3 and 3.4.** PEP 695 evaluate functions under PEP 563, and starred `TypeVarTuple`
  defaults.
* **3.5.** Owner matching for `IfExp` and f-strings; mangling of a method's bindings and of
  type parameters; a class body's `global`; a walrus in a lambda.
* **3.6.** Artefacts now belong to one script and one optimisation level.
* **3.7.** A `NamedTuple`'s parenthesised targets are not fields. Running a staged `compile`'s
  code stays allowed, by design (RL-133).

## 9. Decisions (2026-11-01, author)

* **S-1:** the compiler-generated second entry point, as proposed. FORWARDREF and STRING with
  names not bound yet are \[P1\]; evaluating the text of a reference or annotation stays \[P2+\].
* **S-2:** function signatures at runtime stay out of phase 1, to be revisited with item 1 of
  `docs/targets.md` section 5. The boundary is C-3-24.
* **S-3:** as proposed. A runtime text the dry run did not stage is refused, and `bella-lint`
  warns about dataclasses made inside functions. Spec section 8 states the input rule for
  layouts, separately from code.
* **S-4:** catalogues with Plural-Forms are refused until a target needs them.
* **S-5:** staged texts with probes are confirmed. They are to be revisited later: the author
  has the idea of using the GCC compiler within the program (`TODO.md`, Later).

## 10. Reproduce

```
uv run make staging-check      # determinism, the P1 corpus, the P2+ refusals, the targets, the comparison
uv run python pipeline/tests/test_staging.py
uv run python pipeline/staging/run.py conformance/cases/C-3-22_forwardref_unbound_name.py   # any program
uv run python pipeline/staging/run.py --mechanism intrinsics conformance/cases/C-8-09_staged_namedtuple.py
```

The standard library's artefact is `build/staging/stdlib-<key>.json`. Its `sources` list is
what makes it current, and its `annotate_entry_points` hold every generated entry point's
source. Each program's artefact is under `build/staging/programs/`.
