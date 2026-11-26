# Review F48 (2026-11-26): the decisions of Questions 33 to 48 and the code of 2026-11-24 and 25

*Reviewer: Claude agents in two workflows, asked for by the author when the session's model changed from Opus 5.5 to Fable 5.2
("please review recent (q33 and later) questions, recommendations and decisions, and code built over last 2 days").
Recorded in `review-log.md` as RL-958 to RL-1101; the verdict of each is there. The findings below are the
reviewers' words, not the project's: each was checked by a second agent told to refute it, and the ones the log says were
reproduced by hand were run again by the session itself.*

**How it ran.** A worktree of main's head `f4ba545` with a reflinked build cache; reviewers compiled only through a wrapper
(`r48_both.py`: one program with many rows, built once in one of two slots, each row run under CPython 3.15.2 and compiled).
The first workflow gave one reviewer each to Questions 33 to 48 (the question as put, its facts measured again, its options and
recommendation, the words it produced, its follow-through), eleven to the code by area, and two to the whole (the import chain
since Question 43; the sixteen decisions and the queue together), all on Fable 5.2, with a verifier behind each finding. The
author stopped it ("we can't run dynamic workflows all using fable on this scale") when 25 of the 29 reviewers and 22 verifiers
had finished. Their results were taken from the run's journal; the second workflow ran on Sonnet 5.5 (the four code reviews that
had not reported, continued from their probes, and a verifier for up to three findings at a time) and Haiku 5.5 (checks of
quotations and counts for the low findings about records). Duplicates were merged by hand first: 25 findings share
a subject with another and have one row. The completeness critic of the first design was not run.

**Counts.** 169 findings (143 from the first run, 26 from the continued reviews), 144 subjects: 4 Known, 3 Not a defect, 33 Open, 9 Open (a test), 6 Open (cost), 61 Open (the author's), 28 Open (the records).
Fifteen assessments (kinds `other` and `missing-option`, and three points about the queue) had no second reviewer and are
marked so in the log.

**What a severity means here.** high: a compiled \[P1\] program behaves differently from CPython with nothing registered, or
a decision rests on a false fact, or a recommendation is unsound in a way that changes what should be built. medium: words of the
spec, a deviation or a decision false or incomplete, a test that does not hold what it claims, documents contradicting each
other. low: the rest. The reviewers' probes are kept in the review worktree (`review/<label>/`) until the fixes' tests have
taken their rows.


## q33: Question 33

### F48-q33-1 (RL-958): D-31 says marshal.loads never returns anything different; a set comes back iterating in another order

*words, reported as medium*; where: docs/dialect-spec.md:243 (D-31); docs/deviations.toml:197; TODO.md:871; docs/DECISIONS.md:1892; against section 2's first table (docs/dialect-spec.md:26, D-05)

A set is written with its elements sorted by each element's own dump (marshal.c:647-654), and that dump carries the flags and interned codes inside the element. So where flags differ the elements are written in another order (a third way the bytes differ, unnamed by D-31), and the set `loads` builds from them iterates in another order where two elements meet in the table: standard output of a [P1] program (section 2, container iteration order, D-05), which D-31 says never differs. An int below 2**62 has no count compiled, so of two programs CPython tells apart the port must get one wrong.

Evidence: CPython 3.15.2, review/q33/cpy/setload.py: frozenset([(a,), (b,)]) with a=70000, b=70011 (hash & 7 is 2 for both tuples):
both ints held outside: 3e02000000a901e970110100a901e97b110100 -> list(loads(...)) = [(70000,), (70011,)]
after `del b` (B held by its tuple only): 3e02000000a901697b110100a901e970110100 -> list(loads(...)) = [(70011,), (70000,)]
"the loaded sets are equal: True | they iterate in the same order: False"
cpy/setload_str.py with PYTHONHASHSEED=0 (the harness's seed): {'zzzz', 'aaaa'}, both literals: 3c02000000da0461616161da047a7a7a7a -> ['zzzz', 'aaaa']; 'aaaa' made at run time: 3c02000000da047a7a7a7afa0461616161 -> ['aaaa', 'zzzz'].
Compiled (marshal itself is not ported, so no compiled dump exists): probe setident, row order, SAME on both sides (`b then a: [(70011,), (70000,)]`): sets iterate by insertion where elements meet, so a compiled loads follows the stream as CPython's does. Probe ident, row imm: `int('1099511627776') twice:` CPython False, compiled True (runtime/include/bella/object.hpp:63, a 63-bit immediate): the two programs above hand a compiled dumps the same words.

Probe: review/q33/setident row order; review/q33/ident row imm; review/q33/cpy/setload.py, setload_str.py, setorder2.py (CPython only)

Suggested: Reword D-31 in the spec, the register and the TODO item: a set's elements may be written in another order, and a set loaded from such bytes may iterate in another order; only equal values hold. It widens a registered difference, so it is the author's (of the four options only C is free of it).

> Verifier: **confirmed** (medium). D-31 (dialect-spec.md:243, deviations.toml:197) and TODO.md:870-871 say v3+ bytes differ "in type bytes and in back-reference numbers, never in length or in what marshal.loads returns". CPython sorts a set's elements by each element's own dump, flags included (marshal.c:646-711), so other counts can reorder them and the equal set loaded iterates otherwise where two meet in the table: a section 2 observable (D-05). Conditional (7.4% of int-tuple pairs); v2 unaffected; marshal is not ported, so words only. Corrections: C and D are free of it, not only C; DECISIONS:1892 is not false.

### F48-q33-2 (RL-959): D-31's 'never in length' is false wherever D-03's identity differs, and cannot be made true for ints of 32 to 62 bits

*inconsistency, reported as medium*; where: docs/dialect-spec.md:243 (D-31) against :218 (D-03 as widened by Question 37, same day); docs/deviations.toml:197; TODO.md:871; runtime/include/bella/object.hpp:63

A second meeting of one object is a five-byte back-reference (marshal.c:398-411; the table is keyed by pointer, :789), so a dump's length follows identity. D-03, widened the same day, accepts identity differences in either direction and calls one that changes another observable a defect. So each accepted D-03 row changes a dump's length, which D-31 says never happens. For an int of 32 to 62 bits no port can fix it: `x = 2**40; [x, x]` and `[int(s), int(s)]` are the same words compiled, 21 and 27 bytes under CPython. D-31's rule, by the compiled program's reference count, is silent for a value with no count; its own observable (12345678) is one.

Evidence: CPython 3.15.2, review/q33/cpy/length.py, bytes of a list holding one object twice / two equal objects: int 2**40 21/27; float 19/23; bytes with BytesIO(x).getvalue() 26/37; str with StringIO(t).getvalue() 23/31; bytes with struct.unpack 20/25; tuple of constants 22/29; `loads()[0] is loads()[1]` True/False.
Compiled: `.venv/bin/python r48_both.py review/q33/ident --rows review/q33/ident/rows.txt` (93 identity shapes, 11 differ; ident/out.txt), CPython / compiled:
row imm: int('1099511627776') twice False/True; int('12345678') twice False/True; int(2**62-1) twice False/True; int(-2**62) twice False/True; int('1025') twice False/True (int(2**62) twice False/False)
row lib: BytesIO(x).getvalue() is x True/False; StringIO(t).getvalue() is t False/True; struct.unpack('5s', y)[0] is y False/True
row consts: pair() is pair() True/False
row copies_tuple: +n is n True/False; abs(n) is n True/False (n = 10**30)
docs/dialect-spec.md:218: "Where an identity difference changes another observable, it is a defect, not this deviation".

Probe: review/q33/ident rows imm, lib, consts, copies_tuple; review/q33/cpy/length.py (CPython only)

Suggested: For the author: widen D-31 (where D-03's identity differs a back-reference stands for an object's bytes, or the other way, so the length differs), state the flag of a value that has no count, and except D-31 in D-03's last sentence.

> Verifier: **confirmed** (medium). D-31's "never in length" (spec :243, deviations.toml:197, TODO.md:871) cannot hold: a second meeting of one object is 5 bytes, keyed by pointer (marshal.c:398-411, 789), so length follows identity, which D-03 lets differ and whose last sentence calls a defect. For an int with v >= 2**31 or v < -2**31 inside the immediate range no port can agree. Corrections: nothing compiled shows it yet (import marshal stops, status 70; the words bind a port still to be written); no length change where the object's own bytes are five (ints in 32 bits: 12345678, 1025); -2**31 is unaffected, -2**62 is.

### F48-q33-3 (RL-960): Option A makes the compiled program's own counts visible; the record does not say so, and 'B differs more often' is unmeasured

*other, reported as low*; where: docs/DECISIONS.md:1892; docs/deviations.toml:201; TODO.md:872-873; docs/dialect-spec.md:79 (E-05)

Under A, `marshal.dumps(x)[0] >= 0x80` reads 'x has more than one reference in the compiled program', the fact E-05 excludes as sys.getrefcount. The bytes then follow the compiler's reference handling: by the register's own note a function's local already differs in its first byte, and any pass that removes a count changes a program's output. The planned test prints the bytes, so compiled it pins the counts. The entry calls B 'a deviation that differs more often' with no measurement (none is possible yet), and with Finding 2 A needs a rule over the value for every int below 2**62 anyway.

Evidence: docs/dialect-spec.md:79, E-05: "... `gc.get_referents`, `sys.getrefcount`, ..." with the rationale "No CPython object graph exists".
docs/deviations.toml:201 (D-31's note): "a compiled function's local holds its own reference; CPython 3.15 borrows one".
pipeline/l2/grammar.py:80-82: `class Load(Op)`: "A new reference to what the name holds".
TODO.md:872-873: "`pipeline`'s own shape of the case: a row a process, the bytes printed".
docs/DECISIONS.md:1892: "B (a port with the flags by a rule over the value alone, a deviation that differs more often)"; no number beside it, and nothing compiled exists to take one from.
CPython's own bit moves the same way: review/q33/cpy/facts1.py, `marshal.dumps((1, 'a'))` is 2902e901000000da0161 passed directly and a902e901000000da0161 once a global holds the tuple; cpy/dis1.py, the same constant has a count of 2 once a second function of the module has it.
Not measured: the runtime's counts themselves (sys.getrefcount is E-05); read from the L2 grammar only.

Suggested: Say in D-31's note and the TODO item that the bits are the compiled program's own and may change between builds of the compiler; have the test hold what D-31 promises, not the compiled bytes. Whether B's stability is preferred is the author's.

Minor, one line each, not verified:

- docs/DECISIONS.md:1892 says "The question in TODO had said ... that the version is 5": the TODO text (added in 005bd8d, removed by 2d6762c) says "at the default version" and has no number.
- docs/dialect-spec.md:243 and docs/DECISIONS.md:1892 leave `dump` out of "exact at version 2 and below"; docs/deviations.toml:197 and TODO.md:869 have it.
- TODO.md:123 still reads "`marshal` and `zipimport` (Question 33)": answered, and zipimport was Question 34.
- TODO.md:868 does not name `allow_code=False`: CPython raises ValueError ("marshalling code objects is disallowed", "unmarshalling code objects is disallowed", measured) before it touches the code object, so that path can be exact and is not a stop.
- TODO.md:868 does not name RL-399's residue: the stop row `_frozen_importlib_external.marshal` (pipeline/tests/test_review_2026_11_10.py:157), runtime/prelude/bootstrap_external.py:26 ("the runtime has no marshal"), tools/missing_names.py:42 NOT_IMPORTED; restoring that import would put marshal into sys.modules at start (D-30's fifteen).
- The entry records no recommendation; the entries of Questions 39, 43, 44 and 46 do.
- D-31's parenthesis "where the counts differ (an object a global holds, ...)" lists CPython's measured rows, and the register's observable is CPython's side only; a global's object is read with a new reference on both sides (LOAD_NAME; L2's Load), so that one probably does not differ. Not measurable until the port exists.

Covered: Reviewed at f4ba545: docs/DECISIONS.md:1892, commit 2d6762c (TODO, DECISIONS, deviations.toml, spec), spec rows :147, :243, :349, deviations.toml:196-201, TODO.md:868-876, :123, :885. Overall: the decision (A) is sound, every measurement in the entry holds, and marshal is not ported yet (queued as decided), so the findings are about D-31's words, which the port will be built from. Builds used: 2 of 6.

1. Facts, all re-measured on CPython 3.15.2 (GIL build), review/q33/cpy/facts1.py, also as an imported module and with -c: marshal.version 6; a global list db01000000e94e61bc00; a temporary and a function's local 5b01000000e94e61bc00; [held, y, y] ends 7202000000 and [[1000], y, y] ends 7201000000, 30 bytes each, equal values loaded; marshal.dumps((1, 'a')) is 2902e901000000da0161; versions 0 to 2 give the same bytes for the global and the temporary, 3 to 6 do not. All hold. The reasons, from v3.15.2 source (fetched into review/q33/src_*) and dis (cpy/dis1.py): w_ref (marshal.c:386-396, _PyObject_IsUniquelyReferenced, interned strs always; pycore_object.h:184-187), LOAD_FAST_BORROW for the local, LOAD_CONST borrows (bytecodes.c:312-315), LOAD_NAME takes a reference (:2244-2248). All hold. "Nothing in the closure imports it but importlib._bootstrap_external": parsed every source module of closure.lock.json (183) and of the six targets' locks (160) and grepped targets/vendor: one import, importlib/_bootstrap_external.py:30. Holds.
2. "Exact at version 2 and below": cpy/v2.py, eight values built shared, held and interned against fresh copies: 0 of 8 differ at versions 0, 1, 2 and 7 of 8 at 3 to 6; agrees with the source. Holds.
3. Options and the choice: A to D span the space; no exact option exists (CPython's bit depends even on whether another function of the module has an equal constant). Use counted now: the standard library outside tests has 9 files using marshal, 5 for code objects and 4 for profiler statistics; the venv has pytest's .pyc; in this machine's uv cache scrapy/exporters.py and reportlab/pdfbase/cidfonts.py dump plain data and load it back, which A keeps working and C or D would stop. The choice of A is supported.
4. Words: Findings 1 and 2. The rest of D-31 and the section 7 row are true on CPython's side; register and spec agree but for `dump` (minor); the lint rule as written also covers Findings 1 and 2.
5. Follow-through: queued at TODO.md:868 as decided, nothing dropped. Compiled today: `import marshal` stops with "bella: not implemented: importing 'marshal' (the standard library: step 3b)", exit 70 (probe ident row marshal; inside a try as well, setident row tryimport); `_frozen_importlib_external.marshal` stops with "(CPython has it; the runtime does not yet)". Honest stops, not findings.
6. Consistency: Question 37/D-03 (Finding 2), E-05 (Finding 3), Question 34 (zipimport after marshal: consistent), Question 32 (the stop at import: holds), D-30 ('marshal' in sys.modules True under CPython, False compiled, as D-30 says), D-05 (probe setident row order: SAME).

Probes and scripts are in review/q33/ (cpy/*.py CPython only; ident/ and setident/ with prog.py, rows.txt, out.txt).

Not covered: REPORT.md was not written: the Write tool refused a report file for this agent ("return findings as text"), so the full account is in this result and the probe folders only. The question as it was put to the author in the session, and what was recommended there: not in the repository, and reading the session files was refused; reviewed from the record alone (DECISIONS, TODO, the commit). Anything about a compiled marshal: it does not exist, so Findings 1 and 2 rest on CPython's bytes and source, the runtime's representation of ints (object.hpp:63) and the identity the compiled program has today; no compiled dump was seen. The runtime's counts for a global, a local and a constant were not measured (sys.getrefcount is E-05), only read from pipeline/l2/grammar.py. Not looked at: marshal.load and dump on a program's own file object (the calls they make), deep nesting, malformed data, the audit events; a count of use beyond this machine (PyPI at large, GitHub).


## q34: Question 34

### F48-q34-1 (RL-961): find_spec and get_filename unmarshal a .pyc member's code, so "specs" are not all in the reading half

*wrong-fact, reported as medium*; where: docs/DECISIONS.md:1894; docs/dialect-spec.md:147 (the v0.31 row); TODO.md:879-883

The entry splits zipimport into reading and making code (get_code, exec_module, load_module), and the row makes specs [P1]. In 3.15.2 get_filename, and find_spec through spec_from_file_location, call _get_module_code(compile_source=False), which skips only a source: for a .pyc member it runs marshal.loads. With code objects stopping by name (Question 33), a compiled program stops in find_spec and get_filename for every module whose .pyc in the archive is fresh (.pyc-only archives, eggs with both). The row promises specs there, and the planned case row (find_spec on a source archive) would not hold it. The answer depends on the .pyc's content, so the call cannot simply be skipped.

Evidence: Lib/zipimport.py:166 `_, _, modpath = _get_module_code(self, fullname, compile_source=False)`; :828 `if not isbytecode and not compile_source:` returns early; :746 `code = marshal.loads(data[16:])`. CPython, calls counted (review/q34/cpy/facts1.py, facts1.out): src-only `get_filename('mod') compile=0 marshal.loads=0`; pyc-only `get_filename('mod') compile=0 marshal.loads=1 -> '<tmp>/a_pyc.zip/mod.pyc'` and `find_spec('mod') compile=0 marshal.loads=1`; both: `find_spec('mod') compile=0 marshal.loads=1`. Compiled, CPython's text with marshal.loads as a stand-in stop (p2_gen/out.txt): `ROW ['spec', 'a_pyc.zip', 'mod']: SAME (status 70)` with `q34 stand-in stop: marshal.loads of a code object (E-02)`; the same for `filename a_pyc.zip mod`, `filename a_both.zip mod`, `spec a_both.zip pkg`. CPython's real module on those rows (p2_gen/cpython_real.txt): `find_spec mod: 'a_pyc.zip/mod.pyc'`, `get_filename mod: 'a_both.zip/mod.pyc'`. A stale .pyc beside its source: `get_filename mod: 'a_stale.zip/mod.py'`; a bad magic and no source: `ZipImportError: module load failed: bad magic number in 'only': b'abcd'` (both SAME compiled).

Probe: review/q34/p2_zi (rows filename and spec over a_pyc.zip, a_both.zip, a_stale.zip; output in review/q34/p2_gen/out.txt); review/q34/cpy/facts1.py

Suggested: Ask the author before the step: either the row says specs and file names of a module found as a fresh .pyc stop (E-02), with case rows for .pyc-only, fresh and stale pairs; or marshal gives a code object its names-and-counts side, so only running it stops (touches Question 33).

> Verifier: **confirmed** (medium). Confirmed as a wording finding, not a behaviour one (marshal and zipimport cannot be imported compiled at f4ba545). In CPython 3.15.2 get_filename, and find_spec through it, run marshal.loads on a .pyc member that passes its header checks (.pyc-only, a timestamp .pyc matching its source, a hash-based .pyc). Under Question 33's plan (code objects stop by name) both calls stop for such a module, while spec row 147 lists "specs" as [P1] and names only get_code, exec_module, load_module as stopping, and TODO puts get_filename and find_spec in the reading half. Overstated: the planned case is not said to be a source archive; it just has no .pyc row. Cover: None records it (review-log has zipimport only in RL-604; TODO 877-884 and DECISIONS 1894 say nothing of a .pyc under get_filename or find_spec). The stop itself would be covered by spec row 147, "`marshal` [P1] but for code objects (E-02)", and the v0.31 note, "what makes code stops by name (E-01, E-02)"; the same row's "(its directory, members, sources, packages and specs)" and TODO.md:879-880, "The reading half runs as CPython's code: ... `get_filename`, `find_spec`", are the incomplete words.

### F48-q34-2 (RL-962): The spec row names load_module, which no loader of CPython 3.15.2 has

*wrong-fact, reported as medium*; where: docs/dialect-spec.md:147; docs/DECISIONS.md:1894; TODO.md:881

The row says what makes code (get_code, exec_module, load_module) stops by name. No loader of CPython 3.15.2 has load_module: not zipimporter, not _LoaderBasics, not importlib.abc.Loader. Under CPython zipimporter(p).load_module('mod') raises AttributeError, and CPython's text compiled does the same. A step that follows the row adds a method CPython lacks: hasattr True where CPython says False, a stop where CPython raises. In the repository the word occurs only in these three texts of Question 34.

Evidence: `.venv/bin/python -c "import importlib.abc, importlib.machinery, zipimport, _frozen_importlib_external as e; ..."` prints `zipimporter.load_module False`, `_LoaderBasics.load_module False`, `abc.Loader.load_module False`, `SourceFileLoader.load_module False`. `grep -n load_module` over the pin's Lib/zipimport.py and Lib/importlib/_bootstrap_external.py: no line. cpy/facts1.out: `zipimporter methods: ['_get_files', 'create_module', 'exec_module', 'find_spec', 'get_code', 'get_data', 'get_filename', 'get_resource_reader', 'get_source', 'invalidate_caches', 'is_package']`. cpy/facts2.out: `load_module: AttributeError 'zipimporter' object has no attribute 'load_module'`. Compiled with the copy of CPython's text, p2 row `args`, SAME on both sides: `load_module: raises AttributeError: 'zipimporter' object has no attribute 'load_module'`. `grep -n load_module docs/dialect-spec.md docs/DECISIONS.md TODO.md runtime/prelude/bootstrap*.py`: dialect-spec.md:147, DECISIONS.md:1894, TODO.md:881 and nothing else.

Probe: review/q34/p2_zi, row args; review/q34/cpy/facts1.py and facts2.py

Suggested: Take load_module out of the row, the decision entry and the TODO item; a case row can hold that the attribute is absent.

> Verifier: **confirmed** (medium). docs/dialect-spec.md:147, docs/DECISIONS.md:1894 and TODO.md:881 (all from 4c470e5) name load_module among zipimport's code-making methods that stop by name. CPython 3.15.2 has none on zipimporter, _LoaderBasics or any importlib loader (3.13/3.14 had it); the call raises AttributeError, compiled too. Corrected: the word also occurs in RL-274 (review-log.md:547, "a load_module that 3.15 removed") and its test, so the text contradicts a recorded fact; "a step adds the method" is a risk only (the TODO compiles CPython's text). Decision A does not rest on it; step unbuilt.

### F48-q34-3 (RL-963): Three import-system helpers the entry says the runtime has are missing or different; exec_module would raise AttributeError, not stop

*wrong-fact, reported as medium*; where: docs/DECISIONS.md:1894; TODO.md:877-884; runtime/prelude/bootstrap_external.py:101-108; runtime/prelude/bootstrap.py:412 and 1423-1429

The entry says the reading half is plain Python over helpers "which the runtime's own bootstrap_external.py has". Compiled, three are not: _path_stat refuses with an E-04 message and is the first call of zipimporter.__init__; _verbose_message is absent and _read_directory calls it unconditionally; _LoaderBasics.exec_module, which zipimporter inherits, is the prelude's own body (self.name, _bella_exec), not CPython's get_code. So the step is more than one more frozen module, and left as queued exec_module raises an AttributeError a program can catch where the decision says it stops by name. Making _path_stat real also moves the stops of _path_isfile, _path_isdir and _calc_mode.

Evidence: p1_deps/out.txt, compiled: row `helpers` status 70 `bella: not implemented: the import system's _path_stat (a path finder's search: the closed world is resolved at build time, E-04)` (Lib/zipimport.py:73 `st = _bootstrap_external._path_stat(path)`; runtime/prelude/bootstrap_external.py:108); row `attr _frozen_importlib _verbose_message` status 70 `bella: not implemented: _frozen_importlib._verbose_message (CPython has it; the runtime does not yet)` (zipimport.py:506, no condition); row `basics`: CPython `ImportError cannot load module 'mod' when get_code() returns None`, compiled `AttributeError: 'NoCode' object has no attribute 'name'` at `<frozen importlib._bootstrap_external>`, line 751. p2_gen/out.txt row `exec a_src.zip mod`: DIFF, CPython status 70 `q34 stand-in stop: compile of a source (E-01)`, compiled status 0 `exec_module mod: raises AttributeError: 'zipimporter' object has no attribute 'name'`. runtime/prelude/bootstrap.py:1428-1429: `self.get_filename(module.__name__)` then `_call_with_frames_removed(_bella_exec, self.name, module)`. Also absent: `_validate_hash_pyc` (row `attr`, status 70; the code half only).

Probe: review/q34/p1_deps (rows helpers, attr, verbose, basics; out.txt); review/q34/p2_zi, row exec a_src.zip mod

Suggested: Add the three prelude changes to the TODO item, with a case row for exec_module of a source member, and correct the clause in the decision entry.

> Verifier: **confirmed** (medium). Confirmed, narrowed. DECISIONS.md:1894's clause is false for `_path_stat` (a refusal, E-04; zipimporter.__init__'s first call) and omits `_verbose_message` (absent; `_read_directory` calls it unconditionally). Both stop by name, so the TODO's case shows them at its first row. Only `exec_module` passes unseen: inherited from the prelude's `_LoaderBasics`, it raises a catchable AttributeError for a member whose code comes from a source, where spec row 147 says it stops; a .pyc member stops in get_filename. Nothing compiled is wrong today (zipimport does not import); the author's answer A stands. Cover: Partial only, for one of the three: docs/DECISIONS.md:1957 "a name absent for want of work (`_verbose_message`, still "not yet")", held by pipeline/tests/test_module_locks.py:83; it does not say zipimport needs it. Nothing in review-log.md, TODO.md, the spec or deviations.toml names `_path_stat` or `_LoaderBasics.exec_module` for zipimport. E-04 covers a program's own loaders, so the `_LoaderBasics` subclass rows are not a present [P1] defect.

### F48-q34-4 (RL-964): TODO lists get_resource_reader as running though it needs zipfile ([P2+]); what a zstd member does is left unsaid

*inconsistency, reported as medium*; where: TODO.md:879-882; docs/dialect-spec.md:147; manifest.toml [lazy_unsupported] and [omissions]; tools/closure.py:44-51 and 112

TODO puts get_resource_reader in "the reading half runs as CPython's code". Its body imports importlib.readers, which imports zipfile ([P2+] in the same row): 22 modules outside the manifest in all. By the closure tool's rule the function becomes unsupported, so it stops and cannot run. The _zstd import sits under `except Exception`, an optional edge, which the rule sends to [omissions]: a zstd member then raises a ZipImportError a program can catch, where the pin, which has _zstd, returns the data. TODO says "a zstd member as [P2+]", which reads as a stop. The spec row says members are [P1] and names neither.

Evidence: cpy/closure_edges.out (tools/closure.py's scan_module over the pin's Lib/zipimport.py): `line  211 lazy      importlib.readers ... func='zipimporter.get_resource_reader' in manifest: False`; `line  611 optional  _zstd ... func='_get_zstd_decompressor_class' in manifest: False`. Lib/importlib/resources/readers.py:10 `import zipfile`; importing importlib.readers under CPython adds 22 modules the manifest lacks (zipfile, zipfile._path, importlib.resources.*, bz2, lzma, compression.zstd and others). tools/closure.py:44-51: a lazy edge outside the manifest needs [lazy_unsupported], an optional one [omissions] ("the import resolves to ImportError at runtime, as if not installed"); :112 `IMPORT_ERROR_NAMES = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}`. Compiled, p1 row `imp importlib.readers`: `ModuleNotFoundError: No module named 'importlib.readers'`. CPython, cpy/facts2.out: `zstd member: b'zstd data zstd data '`. With the import failing, p2 row `data a_src.zip`, the same on both sides: `get_data 'z.txt': raises ZipImportError: could not decompress zstd data`.

Probe: review/q34/cpy/closure_edges.out and facts2.py; review/q34/p1_deps, rows imp; review/q34/p2_zi, row data a_src.zip

Suggested: Move get_resource_reader to the stops in the TODO item and name it in the row; decide whether a zstd member stops or raises CPython's error without _zstd, and say it in the row (a deviation entry if it is the error).

> Verifier: **confirmed** (medium). TODO.md:879-880 lists `get_resource_reader` among what "runs as CPython's code". Its body imports `importlib.readers`, which imports `zipfile` ([P2+] in the same row; 22 modules outside the manifest). By spec section 7 (:155) the function is unsupported. For a zstd member TODO says "[P2+]": the closure tool asks for `_zstd` in [omissions], giving a catchable ZipImportError (a D-20 consequence not listed), while CPython's line undeclared stops. Spec row and DECISIONS:1894 name neither. Corrected: the tool's rule bites only once zipimport is `compiled` (now `core`, unscanned), and then fails closed; the reviewer's zstd row was a stand-in. Cover: None records it: grep of get_resource_reader, importlib.readers, zstd in review-log.md, DECISIONS.md, deviations.toml finds only TODO.md:880-881 itself. The rule that decides it is dialect-spec.md:155: "inside a function it belongs to the outermost function that contains it, which the manifest declares unsupported when the import's target is outside the manifest". D-20 would cover a _zstd omission in kind but ends "Only the differences listed here are accepted".

Minor, one line each, not verified:

- The decision entry does not say which option was recommended; the entries of Questions 39 and 43 to 46 do ("Recommended was ...").
- TODO.md:123 still reads "`marshal` and `zipimport` (Question 33)", and the older bullet at TODO.md:885-891 still offers the alternative the decision closed ("or a stop where a zip archive is on `sys.path`").
- runtime/src/call.cpp:4187 gives "CPython's holds zipimport's class, which phase 1 lacks" as the reason sys.path_hooks is absent; with the step phase 1 has the class, and the reason left is E-04 and D-30.
- get_code and exec_module of a module the archive lacks raise ZipImportError and make no code (p2 rows `code a_src.zip nope` and `exec a_src.zip nope`, SAME): the stop belongs where code is made, not at the method, and a case row would hold that.
- The entry's "over _io, time, zlib": time serves only the .pyc freshness check (_parse_dostime), which is on the code side, and the reading half also imports struct for the Zip64 extra (Lib/zipimport.py:468).
- Real code reads zipimport._zip_directory_cache, .archive and .prefix (pkgutil.py:180-181; pip's vendored distlib and pkg_resources): the case could hold the cache's keys beside the rows already planned.

Covered: Question 34 is queued, not built (TODO.md:877-884), so this is a review of the facts, the words and what the step will meet. Two builds used of six.

Verdict: option A is sound and its central premise holds; four medium findings narrow the words, none overturns the answer.

Read: DECISIONS.md:1894, commit 4c470e5 (TODO, DECISIONS, spec row and v0.31), the question as first put in TODO (2d6762c), E-01, E-02, E-04, D-16, D-18, D-30, D-31, manifest.toml and tools/closure.py's rules, the prelude's two import modules, review-log rows RL-604, RL-954, RL-955, RL-957, and the headings of the decisions of 2026-11-24 and 25. No contradiction with Questions 32, 33, 40, 43 or 47.

Facts that hold on CPython 3.15.2:
- zipimport is frozen, is in sys.modules at start (also under -I -S), and sys.path_hooks[0] is its class.
- Its tracebacks name `<frozen zipimport>`.
- get_code and exec_module compile a source or unmarshal a .pyc.
- Nothing in the closure imports it (closure.lock.json has no edge; in the stdlib only pkgutil, outside the manifest).
- Compiled, `import zipimport` stops with status 70, as the entry says.

Probe 1 (review/q34/p1_deps, 38 rows): each name and facility CPython's text needs. All present and agreeing except those in findings 3 and 4. A stop inside a compiled stdlib function cannot be caught (rows parse, unsup).

Probe 2 (review/q34/p2_zi; scripts and outputs in review/q34/p2_gen, 54 rows over 24 archives): CPython's own Lib/zipimport.py with six marked stand-ins, compiled as a module of the program. Under CPython alone the copy prints what the real module prints on every row but the stand-ins. Compiled, 53 rows are SAME: Zip64 forms, cp437 names, paths inside an archive, twelve broken archives, the directory cache, specs of source members, module_from_spec. The one DIFF is finding 3's exec_module.

Registered already and not reported: a spec's cached is None (D-16), zipimport absent from sys.modules until imported (D-30), sys.path_hooks and an archive on sys.path (E-04, D-18).

Options: A, B and C cover the ground. The question carried no count of use (the author's rule on evidence dates from 2026-11-25, a day later). Counted locally now: no target and no .venv package imports zipimport; pkgutil and pip's vendored pkg_resources and distlib do, and they read the directory cache, .archive, .prefix and the class as a registry key. That is the reading half, which only A gives, so the evidence supports the answer.

deviations.toml has no entry for Question 34 and needs none as decided, unless a zstd member becomes CPython's error (finding 4).

Not covered: - REPORT.md was not written: this agent's harness refuses report files (the Write call was rejected), and I did not go round it. The full account is this return; the scripts and raw outputs are in review/q34/ (cpy/, p1_deps/, p2_zi/, p2_gen/).
- The chat text in which the question was put and the recommendation made: the permission system refused the session transcript, so "how it was put" and "who recommended what" are judged from the DECISIONS entry and TODO only.
- Nothing compiled of the real step exists yet: the true stops of marshal.loads and of compile inside a compiled zipimport, the `<frozen zipimport>` file name and line numbers compiled, and zipimport.__spec__ and __file__ compiled are untested. The copy ran as a module of the program, not as a frozen module.
- CPython's C sources: none was fetched or needed; every statement is from the pinned build's Lib/zipimport.py and Lib/importlib/*.py, or from a run.
- Hash-based .pyc files, archives over 4 GiB, non-UTF-8 file system encodings and Windows separators.
- A wider count of use (large PyPI packages, GitHub): only the local stdlib, .venv, targets/ and the interpreter's own site-packages were searched.


## q35: Question 35

### F48-q35-1 (RL-965): sys.getsizeof(x, object=y) takes the keyword where CPython raises TypeError

*defect, reported as high*; where: runtime/src/call.cpp:1365-1368 (sys_getsizeof, since 1dab41b of 2026-11-06); the function Question 35's step is to edit

`sys_getsizeof` takes `object` from position 0 and then lets a keyword `object` replace it, with no check that it was given twice. CPython raises `TypeError: argument for getsizeof() given by name ('object') and position (1)`; compiled, the call answers for the keyword's object. High only by the round's scale (a [P1] call differs, nothing registered; D-08 covers wording, not whether a call raises): the form is contrived, the defect is older than the question and is the only instance in `sys`. Reported because the entry says "the errors are CPython's" and the step edits this function. Every other error and argument row agrees.

Evidence: runtime/src/call.cpp:1365-1368: `Obj object = a.npos > 0 ? a.pos(0) : Obj{}, ...; for (...) { ... if (name == "object") object = a.kw(k);`
`.venv/bin/python r48_both.py review/q35/p1 --rows review/q35/p1/rows.txt`, row `args` (Neg.__sizeof__ returns -1, P.__sizeof__ returns 100):
CPython: `object twice -> raised TypeError` / `object twice, the other way -> raised TypeError`
compiled: `object twice -> 'int'` (type(sys.getsizeof(Neg(), object=P())).__name__) / `object twice, the other way -> raised ValueError` (sys.getsizeof(P(), object=Neg()))
CPython alone, `sys.getsizeof([], object='abc')`: `TypeError: argument for getsizeof() given by name ('object') and position (1)`.
Row `errors` (24 rows: negative, None, a non-int, an __index__ object, 2**70, a TypeError subclass, KeyError, a __get__ that raises; each with and without a default): SAME. The other 8 rows of `args`: SAME. `c_str` has the check (call.cpp:1495-1497). pipeline/tests/test_sys_surface.py has `sys.getsizeof(x=1)`, not this row; no review-log row names it.

Probe: review/q35/p1, row args (output in review/q35/p1/out.txt)

Suggested: Fix with the step: the "given by name and position" TypeError before the keyword is taken; a row in pipeline/tests/test_sys_surface.py; a review-log row.

> Verifier: **confirmed** (low). Reproduced; nothing covers or records it. `sys.getsizeof(x, object=y)` (also via `*a, **{"object": y}` or an alias) compiled answers for `y` and calls `type(y).__sizeof__`; CPython 3.15.2 raises TypeError and calls nothing. `runtime/src/call.cpp:1365-1368` lets the keyword replace position 0 unchecked. The reviewer's facts are exact; only the weight is corrected: the lines are from `1dab41b` (2026-11-06), not the two days under review, CPython always refuses the call, and Question 35's decision is not affected (its step is not built). High by the letter of the scale; I would defend low. Fix with the step.

> Verifier: **confirmed** (low). Real and uncovered. `sys_getsizeof` (runtime/src/call.cpp:1365-1368, from 1dab41b of 2026-11-06) lets a keyword `object` replace the positional one: with exactly two arguments CPython raises TypeError before any `__sizeof__` runs; compiled, the keyword object's `__sizeof__` is called and its answer or error is the call's. Reachable without a type error (`**kw` passes strict mypy). The reviewer's facts hold; Question 35's decision rests on nothing false. High by the scale's letter; I defend low: older than the range, one parameter given twice, a one-line fix with Q35's step.

### F48-q35-2 (RL-966): "No deviation" leaves the sizes out of the register the lint is to be written from

*inconsistency, reported as medium*; where: docs/DECISIONS.md:1896 ("So no deviation"); docs/deviations.toml:2-3 and no entry; docs/dialect-spec.md:38, 43, 210; TODO.md:106-108

Section 2 makes a size difference "not a defect"; but the entry treats the second table's row and a register entry as alternatives. Every other row of that table naming something a program can call has an entry with a lint status (D-01 to D-04, D-06, D-07; the author kept D-03 and D-07 the same day). The sizes are the only such row without one, against the register's header and section 10, and the lint section 2 promises for a read of these numbers has no record to be written from. The record does not show that "no register entry" was put to the author: the options of Questions 35 and 41 are the numbers and the row's words.

Evidence: `grep -c -i "sizeof\|basicsize\|itemsize" docs/deviations.toml` -> 0
docs/deviations.toml:2-3: "The conformance harness and bella-lint read this file. A difference from the reference CPython (bella.toml, 3.15.2) that is not listed here is a defect."
docs/dialect-spec.md:210: "No deviation ships undocumented; the register is the only place a compiled program is allowed to differ."
docs/dialect-spec.md:43, of the second table's items: "`bella-lint` reports the read."
TODO.md:106-108: "Write `bella-lint` as an `ast` walker over `docs/deviations.toml` and the tier table". TODO.md:774 notes "Left: bella-lint's rule" for D-03; nothing like it for the sizes.
Section 11, for a row of the same table: "D-01 | `id()` returns a runtime address that differs from CPython's ... | Accepted (decision 1) | Yes: any `id(` call".
DECISIONS.md:1896: "the question in TODO had offered the runtime's own sizes only as a registered deviation, which missed it ... So no deviation".
Reads a lint would report, in the development environment: mypy/build.py:4681, mypy/memprofile.py:64 (sys.getsizeof).

Suggested: Ask the author: an entry (next id D-34; accepted; lint yes: a call of sys.getsizeof, a read of __sizeof__, __basicsize__, __itemsize__), or the author's word that a second-table row needs none, with the register's header and the lint's TODO item saying where such a rule is kept.

> Verifier: **confirmed** (low). Confirmed in substance, at low severity, not medium. The sizes have no entry in docs/deviations.toml, so no lint field, and no TODO line says where bella-lint's rule for a size read is kept (TODO:106-108 names deviations.toml and the tier table as its sources). Three parts fall: "So no deviation" follows section 10's own rule (an entry is for a first-table difference); the row has had no entry since the phase-0 import, so Question 35 did not create the gap; and spec:38, 43 and 181 are a record of the lint's promise. Left: one entry, or one line on where that rule lives. Cover: Partly recorded, not covered. "No deviation" is itself a recorded decision: DECISIONS.md:1916 "Question 35 (A) made the compiled program's sizes its own, with no deviation, on the reading that section 2's \"`sys.getsizeof` values\" covers `__sizeof__`, `__basicsize__` and `__itemsize__` ... the reading was put as its own question ... The author's words: \"A\"", and spec:210 "A difference inside the first table that the project chooses to keep gets a register entry". Nothing in the register, review log, TODO or DECISIONS records where the lint's rule for a read of a size is kept.

### F48-q35-3 (RL-967): Not put: __basicsize__ and __itemsize__ exact from the names table, which RL-592 needs anyway

*missing-option, reported as medium*; where: docs/DECISIONS.md:1896 (options A to C, and the sentence on RL-592); tools/cpython_names.py:76, 125, 131, 138; TODO.md:508 and 833-835; spec v0.37

Option B bundled sizes that need models of allocation history with two constants of a type that need only a table. The table half was not offered alone, though the project does that for the sibling layout numbers: `__dictoffset__` and `__weakrefoffset__` come from the names table and type_new's rule and are CPython's when compiled. The entry's RL-592 sentence is inexact: the runtime already knows "which types have fields"; what RL-592 lacks is each C type's tp_basicsize, the number `__basicsize__` shows. So the step as decided keeps CPython's number inside the runtime and shows another. Neither name is read outside tests in CPython's library; keeping the stop was a third way.

Evidence: tools/cpython_names.py:76 `return t if t.__basicsize__ != base.__basicsize__ or t.__itemsize__ != base.__itemsize__ else base`; :125 `OFFSETS[key] = f"{t.__dictoffset__},{t.__weakrefoffset__}"`; :131 and :138 read both again.
TODO.md:508: "`type.__dictoffset__` and `__weakrefoffset__` ...: a C type's from the names table (`offsets:`), a class's by type_new_alloc's rule".
Probe review/q35/p1, row `offsets`: SAME for 13 types, e.g. `type 264 368 0x80805d02`, `Exception 16 0 0x40005502`, `A -1 -32 0x561c`.
Probe review/q35/p2, row `reduce` (class P(property); __slotnames__ of k names; P().__reduce_ex__(2)): CPython `4 TypeError`, `5 TypeError`, `6 state {'__doc__': None}`, `7 state {'__doc__': None}`; compiled TypeError for all four (RL-592, open). property.__basicsize__ is 64 = 16 + 8*6. Objects/typeobject.c, object_getstate_default: `if (Py_TYPE(obj)->tp_basicsize > basicsize)`.
grep -E "__basicsize__|__itemsize__" over CPython's Lib outside test/: no hit; over the venv's site-packages: mypy/stubtest.py:522-536 only (it compares two types' layouts by them).

Probe: review/q35/p1 row offsets; review/q35/p2 row reduce

Suggested: Ask the author before the step writes the two attributes: CPython's numbers from the names table (exact, no run-time cost, RL-592's table at once; v0.37's row then loses the two names), the runtime's own as decided, or the stop kept. Correct the entry's RL-592 sentence.

> Verifier: **confirmed** (medium). Questions 35 and 41 offered the runtime's own numbers, CPython's for all four names with allocation models, or the stop for all four. For type.__basicsize__ and __itemsize__ alone, CPython's numbers from a names-table row plus type_new's rule (as __flags__, __dictoffset__, __weakrefoffset__ are given) was not put. The entry's RL-592 sentence names the wrong fact: the runtime has "which types have fields" (state: rows); RL-592 lacks tp_basicsize. Corrections: the runtime holds only yes/no facts today, the number enters only with RL-592's fix; the split breaks CPython's object.__sizeof__(x) == type(x).__basicsize__, which the question must state. Cover: None covers the finding. The behaviour is covered by docs/dialect-spec.md:38 (v0.37, Question 41: A): "`sys.getsizeof` values and the sizes they are made from (`__sizeof__`, a type's `__basicsize__` and `__itemsize__`) ... Implementation detail: the compiled program's own sizes, not CPython's". The probe's reduce row is RL-592, recorded Open: "Low: the names table could hold the sizes". The exact numbers for the attribute are nowhere put or rejected (git log -S"__basicsize__" over TODO, DECISIONS, spec, review log: four commits, none).

### F48-q35-4 (RL-968): The corpus holds CPython's Struct.__sizeof__() number; three preludes answer with CPython's figures

*follow-through, reported as low*; where: conformance/cases/C-7-36_struct.py:21 and its recording; runtime/prelude/_struct.py:577-578; runtime/prelude/_io.py:2093-2096 and 2611-2614; TODO.md:826-835

The entry's account of the state (a flat 64 and 163 stops) leaves out the types that answer today by formulas copying CPython's struct sizes: `Struct` and the buffered streams give CPython's exact figures compiled, `BytesIO` nearly (RL-552). Case C-7-36, in the compiled baseline, prints `s.__sizeof__()` and its recording holds 128, so the harness compares a number v0.37 calls the compiled program's own. The step's item says "relations only, never a number" and names "the preludes' types with buffers", but neither Struct nor C-7-36's row: either Struct keeps CPython's figure (option B's way for some types) or C-7-36 fails until its row is changed and recorded again.

Evidence: runtime/prelude/_struct.py:577-578: `def __sizeof__(self) -> int: return 64 + 32 * (len(_ready(self)[0]) + 1)`; CPython Modules/_struct.c:2546-2553: `size_t size = _PyObject_SIZE(Py_TYPE(self)) + sizeof(formatcode); for (...) { size += sizeof(formatcode); }`.
Probe review/q35/p2, row `struct`: SAME on nine formats (`'' 96 112`, `'>Q' 128 144`, `'bhilq' 256 272`, twenty b `736 752`; __sizeof__() then sys.getsizeof).
Row `io`: `Buffered 4248 252 162` on both sides (runtime/prelude/_io.py:2093-2096, 152 plus the buffer's size); BytesIO: CPython 64, 198, 64, 64; compiled 65, 165, 165, 64 (_io.py:2611-2614).
conformance/cases/C-7-36_struct.py:21: `print(s.format, s.size, s.pack(1), s.unpack(...), repr(s), s.__sizeof__(), ...)`; conformance/expected/C-7-36_struct.json: `>Q 8 b'\x00\x00\x00\x00\x00\x00\x00\x01' (5,) Struct('>Q') 128 Struct _struct struct error`; conformance/evalc-baseline.txt:144: `C-7-36_struct.py`. TODO.md:826-835 names neither.

Probe: review/q35/p2 rows struct and io

Suggested: Name it in the step: C-7-36's row reduced to a relation or dropped, the case recorded again from CPython, and one rule for the preludes' __sizeof__ that answer today (Struct, the buffered streams, BytesIO).

> Verifier: **confirmed** (low). Holds, as a low follow-through. C-7-36 (compiled baseline, stdout compared byte for byte) prints s.__sizeof__() and records 128, a number section 2 (v0.37) calls the compiled program's own; it passes only because _struct.py:578 computes CPython's figure. Five types answer __sizeof__ today (Struct, three buffered streams, BytesIO); TODO.md:826-836 names neither Struct nor the case, and TODO.md:787 says "no type answers it yet". Overstated: the entry cites RL-552/553; "exact" holds for the exact types only (a __slots__ subclass differs); "relations only" describes the step's new case. Cover: None covers or records the finding itself. Adjacent only: RL-552 "No change ... `__sizeof__` is where those values come from ... the runtime's is its own" and RL-553 "As RL-552: a size is the runtime's own number" (BytesIO, BufferedReader); section 2: "`sys.getsizeof` values and the sizes they are made from ... the compiled program's own sizes, not CPython's" covers a difference in a number, not a case that compares one.

### F48-q35-5 (RL-969): The relations the entry says a program may rely on are not CPython's as worded

*words, reported as low*; where: docs/DECISIONS.md:1896 ("the relations a program may rely on hold (a longer list is not smaller, ...)"); TODO.md:827-830 (the case's list)

"a longer list is not smaller" (the entry) and "a str's grows with its text" (the TODO's case list, "CPython passes it") do not hold under CPython in general: a list's size goes by its allocation and a str's by its kind, and the step means the runtime's list to go by capacity too. What holds is narrower: one list that only grows by append never shrinks; text of one kind grows with its length. The spec's row promises no relation at all (line 43 keeps only identity relationships inside the guarantee), so "may rely on" is the entry's, not the specification's.

Evidence: review/q35/notes/facts2.py under CPython 3.15.2: `appended 5: 5 120   [0]*6: 6 104  longer is smaller: True`; `str: 51 60 64 61` ("a"*10, "Ā", "\U00010000", "\xe9"); `popped to 5: 5 248  vs fresh [0]*6: 104`; `dict 6: 352 dict after deleting to 1: 352 fresh 1: 224`.
Probe review/q35/p1, row `relations`, CPython: `one list growing never shrinks: True` / `a longer list is not smaller: False` / `a str grows with its text (ASCII): True (any text): False` / `own n at least n: True`.
CPython Objects/listobject.c:3603-3613: `res += (size_t)self->allocated * sizeof(PyObject *);`. TODO.md:831: "list and bytearray by capacity".

Probe: review/q35/p1 row relations; review/q35/notes/facts2.py

Suggested: Reword the entry's parenthesis and the TODO's case list to relations that hold (the same list growing; text of one kind; a __sizeof__ returning n gives at least n). The recording will catch a wrong row.

> Verifier: **confirmed** (low). Confirmed as wording, low. DECISIONS.md:1896 ("a longer list is not smaller") and TODO.md:827-828 ("a str's grows with its text", "CPython passes it") are not true of CPython 3.15.2 in general: a once-appended list is 88 bytes, [0, 0] is 72; 'a'*5 is 46, chr(0x100) is 60. Correction to the reviewer: "text of one kind grows" fails too (chr(0xE9) 61, chr(0xE9)*2 59); what holds: ASCII text, one container that only grows, lists made alike. The spec promises no size relation (lines 38, 43; RL-553). The step is not built and the decision does not rest on the words.

Minor, one line each, not verified:

- Option A says sys.getsizeof "adds the runtime's header before the object". The runtime has none: struct Object (runtime/include/bella/object.hpp:112) begins the object and the collector's candidates are a side vector (object.hpp:248). The +16 at call.cpp:1383 (from 1dab41b) is CPython's collector header by imitation; the TODO's "checked against the runtime's own header" will find 0, and then sys.getsizeof(x) == x.__sizeof__().
- The entry records no recommendation (Questions 39 and 43 to 47 do), and the question as put is not in the repository, so who recommended what cannot be checked from the record.
- bytearray.__alloc__() (the capacity; a stop today, pipeline/tests/argument_counts_stops.txt:103) is a number of the same family that v0.37's row does not name.
- Rows that hold today's stops and go stale with the step, beyond the sweep's list the TODO names: pipeline/tests/test_review_2026_11_03.py:72-74, test_bytes.py:103, test_collections.py:283-284; docs/emitter.md:472 gives "it counts the C's blocks" as the reason deque.__sizeof__ refuses, a reason the decision removes.
- unittest.mock computes MagicMock's __sizeof__ as object.__sizeof__(self) (mock.py:2099); not in the manifest, noted for when it is. With collections' Python OrderedDict.__sizeof__ (replaced by the C type) it is the only use of the four names in CPython's library outside tests.
- The entry's "for a heap type the managed dict and weak-reference slots" follows the type's flags in the source (_PyType_PreHeaderSize), not heapness; it holds in practice (of 439 types reached from object, no static one has either flag), and the source adds nothing for a static type object itself (sys.getsizeof(int) == type.__sizeof__(int) == 424).

Covered: The entry (DECISIONS.md:1896) sentence by sentence; commit fbe5df4 (it changes only TODO.md and DECISIONS.md: the decision is queued, nothing is implemented, and no later commit touches the area); Question 41's entry and 56196b0 for consistency; the spec's section 2 row, v0.37, sections 10 and 11; docs/deviations.toml; TODO.md's item (826-835) and its neighbours; review-log rows RL-335, RL-346, RL-552, RL-553, RL-592; the existing tests and cases that name the four attributes. Verdict: the core decision (the runtime's own numbers for __sizeof__ and sys.getsizeof) is sound and consistent with section 2 as it stood, with RL-552/RL-553 and with Question 41; option B's cost is described fairly; the TODO item queues what was decided. FACTS, all confirmed. Under CPython 3.15.2: 56, 88, 43, 40; 132 for a class whose __sizeof__ returns 100 (116 with __slots__); the ValueError and the TypeError; object's __basicsize__ 16 against list's 40. Source read (v3.15.2, fetched into review/q35/cpython-src, only read): _PySys_GetSizeOf, sys_getsizeof, _PyType_PreHeaderSize, object___sizeof___impl, list___sizeof___impl, Struct___sizeof___impl, bytesio_sizeof, object_getstate_default; the entry's account of them is right. Compiled (2 builds of 6; probes review/q35/p1 with 22 rows and review/q35/p2 with 4, outputs in their out.txt): 64 64 64 64 (and 64 for 31 kinds of object), 116 for the class, and list/object/str/type.__sizeof__, type.__basicsize__ and type.__itemsize__ stopping by name with an honest message; argument_counts_stops.txt has 163 __sizeof__ rows of 182. Beyond the number, what a program sees of sys.getsizeof was swept: 24 error rows with and without a default, 10 argument rows, a descriptor's __get__ called once, a callable object, static and class methods, __getattr__ not asked, an instance attribute ignored, the method called once, the order temporaries are finalised in: all agree but finding 1. Use of the four names was counted in CPython's library, the development environment, the targets and the cases.

Not covered: REPORT.md was not written: the harness refused a report file from a subagent (Write answered "Subagents should return findings as text, not write report files"), and I did not work around it. The full account is this output; the evidence is on disk in review/q35/p1 and review/q35/p2 (prog.py, rows.txt, out.txt with both sides), review/q35/notes (CPython-only measurements) and review/q35/cpython-src. Also not covered: the question as it was put to the author (it is not in the repository; the TODO's draft was replaced by the answer); the step itself, since nothing is implemented to hold against the words; Question 41's wording beyond consistency (another reviewer's); GitHub-wide counts of use; the eval1 and eval2 legs and the lean profile.


## q36: Question 36

### F48-q36-1 (RL-1011, with the same subject): The runtime's own C modules never go at the exit; CPython's do, a weak reference shows it, and since D-19 ended nothing registers it

*defect, reported as high*; where: runtime/src/call.cpp:3569-3595 (from 25e2f67); docs/DECISIONS.md:1922 (Question 36's step) and :1936 (Question 44); docs/dialect-spec.md:196 and :247; docs/deviations.toml:50 (D-07's note)

25e2f67 left the runtime's own modules immortal, and its exit takes each for alive for good (call.cpp:3593). CPython 3.15.2 collects a C module nothing else holds right after sys.modules is emptied (math, time, zlib, cmath, unicodedata, _collections, atexit, _weakref measured). A program sees it: a weak reference that sys keeps has its callback run under CPython and never compiled. D-19's note registered this ('a weak reference to a module never dies') until Question 44 ended D-19 on the claim that nothing of it can be seen; C-9-13's row `weak` holds such a callback as promised under D-07. Narrow in weight, but unregistered, and three sentences of the records are false.

Evidence: `.venv/bin/python r48_both.py review/q36/p2 --rows review/q36/p2/rows.txt`, row `exit_native math sys` (`sys.kept_reference = weakref.ref(math, callback)`, the local name dropped): CPython stdout `end of program` / `math died`; compiled `end of program`. Same DIFF for time, zlib, cmath, unicodedata, _collections, atexit, _weakref. Controls SAME: plain (a program module), json, collections, __main__, a ModuleType print `... died` on both; gc, itertools, errno, sys print nothing on either. p3 row `weakstate math plain` (a finaliser of an object sys keeps reads a plain weak reference): CPython `its module is gone`, compiled `its module is still there` (also time, zlib, unicodedata). `python -v review/q36/scratch/exitmod2.py math drop`: `# cleanup[2] removing math`, `math died`, `# destroy math`, then the first `# cleanup[3] wiping`. call.cpp:3593 `if (met.serial == 0) return met.module;`. DECISIONS.md:1922 'each step of `finalize_modules` lets go of what CPython's does'; :1936 'nothing of D-19 is left that a program can see'; deviations.toml:50 'The runtime follows CPython 3.15.2's order today'; DECISIONS.md:1788-1792 (what is not exact at the exit) lacks it; the old note: `git show be1407c:docs/deviations.toml`, line 127.

Probe: review/q36/p2, rows `exit_native <module> sys` (8 modules, with controls); review/q36/p3, rows `weakstate <module> plain`; review/q36/scratch/exitmod2.py (CPython alone)

Suggested: Ask the author: register it (a clause in D-07, or 'a module of the program's' in section 9; a line in the exit's list; the two DECISIONS sentences corrected), or clear a native module's weak references at the exit's collection where CPython's module goes. A row beside C-9-13's `weak` either way.

### F48-q36-2 (RL-970): design.md has nothing of the step, and its collector paragraph states an invariant the step ended

*follow-through, reported as low*; where: docs/design.md:800 (section 10.4, the collector's paragraphs); runtime/src/core.cpp:428-443, 450, 491-493; commit 25e2f67

25e2f67 changed design.md in one comment line. What it built (a module's two counts, refs and `holders`; the dead module kept as its holders' way to their globals; the exit by counts; the collector not walking a namespace whose module sys.modules holds under its own name) is in DECISIONS, the code's comments and the model only. design.md:800 still states the collector's invariant as 'Each kind's traverse names exactly the counted references its release lets go of', which no longer holds for a module, a function, a frame object and a traceback entry. The rule itself looks sound (probed; the model's self-test catches its mutation); design.md, the authority on how things are built, lacks it.

Evidence: `git show --stat 25e2f67 -- docs/design.md`: `docs/design.md | 2 +-` (the IMMORTAL flag's comment). `grep -n "holders\|hold_globals\|rooted" docs/design.md`: no output. design.md:800: 'Each kind's traverse names exactly the counted references its release lets go of, the tracked ones among them, and its clear is CPython's `tp_clear`'. runtime/src/core.cpp:439-440: `void visit_globals(const Module* m, std::vector<Object*>& out) {` / `if (m == nullptr || (m->flags & IMMORTAL) || rooted_namespace(m)) return;`, while `release_globals` (runtime.hpp:253-260) does `decref(m->dict)`; core.cpp:493 (the module's own traverse): `if (!m->holds_namespace || rooted_namespace(m)) return;`.

Probe: review/q36/mut (the model's self-test on a scratch copy with `rooted()` made true without the table: MISMATCH, as it should); review/q36/p1 rows `named`, `renamed_main`

Suggested: A paragraph in design.md section 10.4 beside the collector's two: the module's two counts, the rooted rule and why it is sound (the interpreter's table is a root); give 'exactly' its exception.

> Verifier: **confirmed** (low). design.md has no paragraph for the module-count, holders or rooted-namespace rule from 25e2f67. Its only change in that commit is the IMMORTAL flag's comment. design.md:800 still says 'Each kind's traverse names exactly the counted references its release lets go of', and the module traverse does not do that for a rooted namespace, which it skips at core.cpp:493. The rule itself is recorded in DECISIONS.md:1921-1923 and the code, so the gap is in design.md only.

### F48-q36-3 (RL-971): The C function that holds `__main__` is cited under a name CPython 3.15.2 does not have

*wrong-fact, reported as low*; where: docs/DECISIONS.md:1921; runtime/src/call.cpp:3969 (25e2f67), 4377 and 4380

The entry and two comments name the C function that holds `__main__` during the run as `_PyRun_SimpleFileObject`, with a local `m`. CPython 3.15.2 has no function of that name: it is `_PyRun_SimpleFile` (Python/pythonrun.c:481), and the local is `main_module` (taken at 487, released at 548). The fact itself holds (the run keeps `__main__` until the file's run is over, before finalisation) and the exit rows for `__main__` agree compiled, so nothing built is wrong; but the citation was not read from the pinned source, which the project's rule asks for.

Evidence: Fetched https://raw.githubusercontent.com/python/cpython/v3.15.2/Python/pythonrun.c to review/q36/cpython/ (Include/patchlevel.h of the tag: `PY_VERSION "3.15.2"`). `grep -n SimpleFile Python_pythonrun.c`: `84: result = _PyRun_SimpleFile(fp, filename, closeit, flags);`, `481:_PyRun_SimpleFile(FILE *fp, PyObject *filename, int closeit,`, and no `SimpleFileObject`; line 487 `PyObject *main_module = PyImport_AddModuleRef("__main__");`, line 548 `Py_XDECREF(main_module);`. docs/DECISIONS.md:1921: '`__main__` is held by the start while the program runs, as `_PyRun_SimpleFileObject` holds it.' runtime/src/call.cpp:3969 (25e2f67): `// _PyRun_SimpleFileObject's `m`: held while the program runs`; :4377 (8ec5cce): `// _PyRun_SimpleFileObject's `done:` ...`; :4380 `// and its `m` let go of (Py_XDECREF(m))`.

Probe: review/q36/cpython/Python_pythonrun.c (read only); review/q36/p2 rows `exit_native __main__ sys|global|both` (SAME)

Suggested: Correct the name (`_PyRun_SimpleFile`, local `main_module`) in the entry and the comments with the next edit of call.cpp.

> Verifier: **confirmed** (low). docs/DECISIONS.md:1921 and runtime/src/call.cpp:3969, 4377, 4380 cite `_PyRun_SimpleFileObject` and local `m`; CPython 3.15.2 has `_PyRun_SimpleFile` (Python/pythonrun.c:481) with local `main_module` (487, Py_XDECREF at 548). The mechanism cited (main held until the file's run ends, `done:` pops __file__) is correct; only the name is false. Wording/comment only; the :4377 comment predates the window (8ec5cce).

Minor, one line each, not verified:

- docs/DECISIONS.md:1898 does not record what was recommended (B, with C as the fallback, per the question as put); the entries from Question 43 on say 'Recommended was'.
- docs/dialect-spec.md:247: D-19 'ended on 2026-11-25 (the author's decisions, Questions 36 and 43)'; the decision that ended it is Question 44 (DECISIONS.md:1936), and Question 36 was answered on 2026-11-24.
- TODO.md:555-557 still reads 'the exit is finalize_modules' sequence with its collections, over a trace in CPython's view since modules and classes are immortal here'; the trace went with 25e2f67 and classes are counted since C-3-12.
- docs/emitter.md:366-368, whose second half ad18417 edited, still says that at exit 'each module's globals are released in insertion order, the modules in sys.modules order and then those it no longer holds, oldest first', which is neither the exit's steps since H4 nor true of counted modules.
- The C++ of the step (Module, PyFunction in runtime.hpp and core.cpp) is outside `make object-test`'s lockstep with the model (runtime/tests/object_differential.py:103 runs World(cycles=cycles), without modules=True); C-9-14 and the review rows are what hold it to the model, which is how RL-945 ('the header had gone beyond the model') got through to a reviewer.
- conformance/expected/C-9-14_when_a_module_dies.json has only the first line of the case's two-line `# source:` header (the recorder's doing, older than the step).
- CPython's own comment in finalize_modules ('All C extension modules actually end up here, since they are kept alive in the interpreter state') does not describe 3.15.2's math: `python -v` shows `# destroy math` before the first `# cleanup[3] wiping`. The runtime's comment at call.cpp:3569-3571 follows that comment and not the measurement.

Covered: VERDICT: Question 36 is sound. It was put straight, its facts hold, the options were complete, B was right by the project's rules, and what was built does what the decision and the spec's new sentence say for a module of the program's. The one substantial thing is Finding 1 (the runtime's own C modules at the exit, unregistered since D-19 ended); Findings 2 and 3 are small.

HOW IT WAS PUT: read the question as shown to the author and the answer in the session's transcript (local file, read only): put 2026-11-24T18:39Z with a table of four measurements, source fragments, options A/B/C and the recommendation B (C as fallback); the author's words 'B seems valid' (18:52Z) are quoted exactly in DECISIONS.md:1898.

FACTS, measured again under CPython 3.15.2 (review/q36/p1 rows q_nocycle, q_class, q_moduletype, q_kept): a failed import's globals with no cycle go when the except clause ends; with a class in the module at gc.collect(); a ModuleType at del with its weak reference dead; a function kept from a failed import reads its own namespace after a re-import. All four hold and compiled at f4ba545 agrees. `_load_unlocked`'s `del sys.modules[spec.name]` is at Lib/importlib/_bootstrap.py:860, its local `module` at 843. The three source lines the question cited at fbe5df4 are as quoted; D-19's old words and the spec's old premise are quoted as they stood. CPython's C read (tag v3.15.2, fetched to review/q36/cpython): module_dealloc/traverse/clear, func_clear, frame_dealloc, finalize_modules and its steps, pythonrun.c; the entry's statements hold but for Finding 3's name.

COMPILED PROBES: 4 builds, 168 rows (outputs in review/q36/notes/p?_both.txt), 136 SAME. p1 (69 rows): the four measurements; what runs in a module that is gone (generator, nested functions, a class made later, globals(), an import, warnings with its registry); how long the exception keeps the module (kept, traceback kept or set to None, with_traceback(None), last or first entry alone, clear_frames, exc_info, contextlib.suppress, finally, re-raise); nested and chained failures; a package whose __init__ raises after importing a submodule, twice; from-import of a failing submodule; importlib.import_module and __import__; a circular pair; 21 bound methods and attributes of a module, super, AttributeError.obj, a module __getattr__; the weak-reference API; modules named like those in sys.modules, renamed, nameless; growth of 200,000 ModuleTypes; four exit rows. p2 (65): an unclosed file of a failed module (ResourceWarning at CPython's moment and line); 2,000 failing imports with and without a cycle (by hand on the binary: flat without, bounded at about 85 MB with, after 20,000 and 40,000); a lazy import that fails; a failed import in a generator suspended in the except clause; module_from_spec; module reprs; the exit rows of Finding 1. p3 (12): Finding 1's second observable. p4 (22): 17 kinds of thing a failing module gives away and what each keeps; gc.garbage under DEBUG_SAVEALL; a collection inside the except clause.
The 32 DIFF rows: 12 are Finding 1; 5 are gc.collect()'s number (D-04's note); 2 are D-20's tracemalloc line; 1 is the uncaught exception's report on stderr (D-06, D-28; stdout agrees); 8 are stops by name (traceback.tb_frame twice, object.__sizeof__, gc.is_tracked, a ModuleType subclass's instance, import array three times); 4 are my first probe importing by a computed name outside the closed world (run again in p2 with static imports: agree). C-9-14's recorded output is what CPython prints today, and the case is in the compiled and eval2 baselines.

MODEL FIRST: refmodel has RefModule, RefFunction, hold_globals, release_globals, rooted, the oracle's and the stateful test's module operations as the entry says. The session's first edits of the step were the model (22:00:59Z), its test (22:01:32Z), then the case (22:13:24Z). `python -m refmodel.selftest --iterations 20000` green on two seeds of mine (1, 20261126). On a scratch copy (review/q36/mut) the self-test fails, as it should, when rooted() ignores the table and when a function also holds its module object: the test can fail and holds both claims.

OPTIONS AND RECOMMENDATION: complete as far as I can see (the narrower cut, counting from the moment a module leaves sys.modules, had been weighed and needs counts that do not exist; an exclusion does not fit an edge that is the ordinary shape of a missing optional dependency one level down, with unbounded growth). Cost was described fairly. The residue foreseen did not arise and another did (the import system's frames, Question 43); the entry says so.

WORDS AND FOLLOW-THROUGH: spec lines 196 and 247 and v0.39, deviations.toml (D-19 gone as D-22 is; D-04 and D-07 read), TODO (the step's item gone, successors done), review-log RL-933 (Done; `exit/failed` in the A43 test's rows), emitter.md, design.md. A ModuleType subclass stops by name as the entry says ([P2+] by RL-270). Start and exit of a program importing json, argparse and collections: 0.11 to 0.12 s wall compiled at the head (7 runs), agreeing with the entry's 0.12 s.

Not covered: REPORT.md was not written: the harness refused a report file from a sub-agent (the Write tool's rule), and I did not work around it. The full account is this output; the probes, their rows and both sides' outputs are on disk under review/q36/ (p1 to p4, notes/p?_both.txt, notes/p?_cpython.txt, scratch/, mut/, cpython/).

Not checked: the cost figures against 6f0f149 (0.6% and 2% for a function made and dropped, the 0.5% and 0.6% fewer, the 6.3% of the collector's walk, the 51% of start and exit) and the compiled half of the question's table at fbe5df4: both need a build of an older commit, which this review may not make. The implementation's code in depth (another reviewer's): the exit's rewrite in call.cpp beyond the lines quoted, imports.cpp, error paths, the staged texts' records (RL-945's ground), a build with fidelity lean. The stateful (Hypothesis) test and every test that needs pytest or a build; the eval1 and eval2 legs; the claim that H4's and A43/A44's rows were run again with the step. What the import system's frames hold other than through lifetimes (traceback.tb_frame stops by name compiled; Question 43's ground). Threads and a ModuleType subclass's lifetime (outside [P1]). Questions 43 and 44 beyond what touches Question 36: Finding 1 is partly Question 44's and may be reported there too. In Finding 1 I did not establish which native modules CPython keeps in every program (it depends on what else imports them); the eight named are measured with the probing program as their only importer.


## q37: Question 37

### F48-q37-1 (RL-972): A NaN that CPython's compiler folds: values differ compiled, and "identity only" is false for it

*defect, reported as high*; where: docs/DECISIONS.md:1906 (last sentence); docs/deviations.toml:24; TODO.md:776-783; docs/reviews/review-log.md:1035 (RL-623); pipeline/backend/cpp.py:215

`def fnan() -> float: return 1e999 - 1e999`: CPython folds it to one constant (co_consts is (inf, nan)); compiled makes a new float at each call. For a NaN that is not identity only: containment, list.index and remove, dict lookup, set length and tuple equality differ, two rows by an exception. Nothing registers it (D-03 is about equal values; a NaN equals nothing). It falsifies "What the folding gets wrong stays identity only" (DECISIONS, TODO, the register's note) and RL-623's "Only identity shows it". The queued step's case list has tuple rows only, and the backend keys every NaN as one constant where CPython keeps two occurrences apart.

Evidence: p1 row nanconst, p3 row nan (CPython | compiled):
fnan() in [fnan()]: True | False
[fnan()].index(fnan()): 0 | raised ValueError
{fnan(): 1}.get(fnan()): 1 | None
len({fnan(), fnan()}): 1 | 2
(fnan(),) == (fnan(),): True | False
fnantuple() == fnantuple(), return (1e999 - 1e999, 1): True | False
items = [fnan(), 1.0]; items.remove(fnan()): left 1 | raised ValueError
-(1e999 - 1e999), 1e999 * 0, 1e999 / 1e999, each in a list of itself: True | False
a loop appending 1e999 - 1e999 three times, count of the first and set length: 3, 1 | 0, 3
Same on both sides: len({1e999 - 1e999: 'a', 1e999 - 1e999: 'b'}) is 2 (two occurrences are two objects under CPython); float('nan') in [float('nan')] is False.
Emitter.const run alone under CPython: nan -> `rt::float_constant(nan)`, -inf -> `rt::float_constant(-inf)` (neither is C++); the key is ('float', value.hex()), 'nan' for every NaN.
grep of the spec, deviations.toml, TODO and the review log for a NaN's identity or folding: nothing.

Probe: review/q37/p1 row nanconst; review/q37/p3 row nan

Suggested: Give the folding step these rows as its case (one occurrence is one object, two occurrences are two), say whether a lone constant operation is folded, and change the three sentences to "identity only, but for a NaN".

> Verifier: **confirmed** (medium). A NaN from an operation CPython's compiler folds is one object per occurrence under CPython and a new float per evaluation compiled. For a NaN that is not identity only: `in`, index, count, remove, dict lookup, set length and tuple/list equality all differ. The sentences 'What the folding gets wrong stays identity only' (DECISIONS 1906, TODO 783, D-03 note) and RL-623's 'Only identity shows it' are false for NaN. The folding step itself is queued, so the difference is known as an instance of RL-623. New and unrecorded: the false sentences, no NaN rows in the queued case list, and the backend k ... Cover: Partly known: TODO 776-783 'Tuples of constants folded ... What folding gets wrong is identity only and stays under D-03' and RL-623 (queued); D-03's last sentence itself calls a value-visible difference a defect. No text covers NaN.

### F48-q37-2 (RL-973): The cut by direction was not put: where CPython gives the object back and compiled copies, exact is the cheaper behaviour (RL-699)

*missing-option, reported as medium*; where: docs/DECISIONS.md:1906; review-log RL-699; runtime/prelude/_io.py:2383, 2396

The entry sorts its seven rows by direction: RL-623 and RL-699 are one object under CPython and a new one compiled, five are the other way. B makes RL-623 exact and accepts RL-699; no option's cost is in the entry. In the five rows accepting is the costless choice (exact adds a copy). In RL-699's direction the compiled program does the extra work: BytesIO holds bytearray(initial_bytes) and getvalue returns bytes(buf[:size]), three copies where CPython makes none. The same direction outside the seven rows, found by a sweep: 15 int operations copy an int beyond the immediates, and a class's __name__ is a new str at each read.

Evidence: p4 (ms, CPython | compiled; how often the result is the argument):
200 getvalue() of an unwritten BytesIO, 64 KiB: 0 | 664; 200 | 0 times
200 BytesIO(x).read(), 64 KiB: 0 | 674
the same at 16 MiB: 0 | the row timed out after 120 s (the 64 KiB lines read with PYTHONUNBUFFERED=1 from the built binary)
200 StringIO(s).getvalue(), 2 MiB: 531 | 7; 0 | 200 times
20000 of +x, x = 2**400000 + 7: 1 | 52; 20000 | 0 times
20000 of abs(x), round(x), x.__index__(): 1-2 | 51-55
p1 row int, at 10**30, 2**62 and 2**63: +x, abs(x), x.real, x.numerator, x.conjugate(), x.__index__(), x.__int__(), x.__trunc__(), x.__floor__(), x.__ceil__(), round(x), round(x, 0), math.floor(x), math.trunc(x), x.as_integer_ratio()[0] are x under CPython and a new int compiled (45 rows).
p2 row names: C.__name__ is C.__name__ True | False; X.__name__ = name; X.__name__ is name True | False.
_io.py:2383 `self._a_buf = bytearray(initial_bytes)`; :2396 `return bytes(self._a_buf[:self._c_string_size])`.

Probe: review/q37/p4; review/q37/p1 row int; review/q37/p2 row names

Suggested: Put it to the author as a follow-up to B: exact where CPython gives the object back and we copy (BytesIO's initial bytes, the int identities, a class's name), accepted the other way.

### F48-q37-3 (RL-974): D-03's last sentence does not decide the case where the `is` stands in another module

*words, reported as medium*; where: docs/dialect-spec.md:35 and :218; docs/deviations.toml:20

"Where an identity difference changes another observable, it is a defect, not this deviation": three programs with no `is` of their own print other values compiled. argparse with a default and a help equal to SUPPRESS; optparse with the literals 'SUPPRESSUSAGE' and 'SUPPRESSHELP' (the new direction: optparse.py:803 is "SUPPRESS"+"HELP", which only CPython folds and interns); a module's own str sentinel. By the sentence they are defects, by decision 1 the deviation; to the letter the sentence takes the deviation back. The row also reads as taking away what programs rely on and the runtime keeps: a value read back is the object stored, and sys.intern.

Evidence: p1 row argparse: add_argument('--a', default='==SUPPRESS=='); add_argument('--b', help='==SUPPRESS==')
CPython: Namespace(a='==SUPPRESS==', b=None), help lists --a A and --b B ==SUPPRESS==
compiled: Namespace(b=None), help lists --a A only
p2 row sentinel: OptionParser(usage='SUPPRESSUSAGE'); add_option('-a', help='SUPPRESSHELP'); add_option('-b', help='shown')
CPython: Options: -b B shown
compiled: Usage: SUPPRESSUSAGE Options: -a A SUPPRESSHELP -b B shown
othermod.lookup('<missing>') with MISSING = '<missing>' and `default is MISSING` in othermod: <missing> | absent
Kept by the runtime: p1 row flow, 7 types by 24 ways of storing, passing and returning, all the same object on both sides; sys.intern(a) is sys.intern(b) True on both.
cp/stdlib_is.py: in the manifest's 146 pure-Python modules, 20 identity tests on a module-level str, int or tuple (argparse.SUPPRESS 14, optparse 4, encodings 1, random 1); cp/static_is.py: 23 in the whole library, none in the venv's 904 files.

Probe: review/q37/p1 rows argparse, flow, intern; review/q37/p2 row sentinel

Suggested: The author's words for the last sentence: a difference that shows through `is`, `is not` or `id()` on such values, whoever wrote the test, is the deviation; one that shows with no identity test is a defect. Add what a program may rely on.

> Verifier: **confirmed** (medium). D-03's last sentence ('Where an identity difference changes another observable, it is a defect') does not say whose `is` counts. argparse with default/help equal to SUPPRESS, optparse with literals 'SUPPRESSUSAGE'/'SUPPRESSHELP' (the identical-less-often direction), and another module's `default is MISSING` print other values compiled with no `is` of the program's own. By the sentence they are defects; by D-03's first clause and decision 1 they are the accepted deviation. The words are incomplete and need the author's wording. Correction: sys.intern is kept only for intern(a) is intern(b); `sy ... Cover: None for these. D-03 note: 'The boundary is Question 29's' (extra __hash__ calls); spec 218 'code that depends on it is wrong by the dialect's standards' and a lint that reaches the program's own `is`, not the library's.

### F48-q37-4 (RL-975): The list of types is narrower than what differs: constant slices, Decimal, timedelta

*words, reported as medium*; where: docs/dialect-spec.md:35 and :218 (the lint); docs/deviations.toml:20-24; TODO.md:773-783

Section 2 names seven types (int, float, complex, str, bytes, tuple, frozenset) and the lint the same seven. Equal immutable values of other types differ too: a slice of constants is one constant under CPython (codegen.c:5829, not flowgraph.c) and a new slice compiled; Decimal(d) is d under the C module and a copy in _pydecimal; +td and abs(td) are new under the C module and td itself in _pydatetime. These are neither accepted by the words nor queued, and no other deviation names them. Sections 2 and 11 also differ: only section 2 has the type list and "whether a constant is one object".

Evidence: p1 (CPython | compiled):
row const 39: k[1:2] evaluated twice, k.__getitem__ returning its argument: True | False
row const 40: k[1:2, 3] twice: True | False
row decimal 0: Decimal(d) is d: True | False
row datetime 0, 1: +td is td, abs(td) is td: False | True
Agreeing outside the seven (rows other, fdict, fraction): range, frozendict, re.Pattern, Fraction, bound methods, list[int], unions.
Inside the words but named in neither row (row const 24, 25, 29): 'ab ' + 'cd', 'hello, world'[1:4] and -1.5 are one object under CPython and a new one at each evaluation compiled.
codegen.c:5829 `if (is_constant_slice(s)) { ... PySlice_New(start, stop, step); ... ADDOP_LOAD_CONST_NEW(c, LOC(s), slice);`
grep decimal|datetime docs/deviations.toml: only D-20's IsoCalendarDate repr.

Probe: review/q37/p1 rows const, decimal, datetime, other

Suggested: Reword to "immutable values, such as ..." or add the three; add the constant slice to the folding step; make section 11's row and the register say what section 2's says.

> Verifier: **covered** (low). Rows reproduce (constant slice, Decimal(d) is d, +td/abs(td)), but D-03 in deviations.toml and spec section 11 say 'equal immutable values' with no type list and 'a library function may give back ... or the other way', which covers Decimal and timedelta; slices fall under 'whether a constant is one object' and the D-03 note's 'inexact folding stays covered'. Residue (low): spec section 2's row has the seven-type parenthesis and 'whether a constant is one object' that section 11's row lacks, the lint list is the same seven, and the queued folding step (flowgraph.c functions only) omits the cons ... Cover: deviations.toml D-03 summary: 'is between equal immutable values may differ from CPython's in either direction ... a library function may give back the object it was given where CPython's makes an equal new one, or the other way'; spec section 2 'whether a constant is one object'.

### F48-q37-5 (RL-976): Section 2 still promises every identity relationship, beside the widened row

*inconsistency, reported as medium*; where: docs/dialect-spec.md:34 and :43; docs/deviations.toml:11 (D-01 observable); docs/DECISIONS.md:25 (decision 1)

The row above D-03's says "every equality and inequality CPython shows between address-derived values MUST hold in the compiled program"; the paragraph under the table says a decision on an identity relationship (a is b, membership in an identity-keyed dictionary) is inside the guarantee "because relationships are preserved under renaming"; D-01's `observable` and decision 1 say the same. The widened row beside them says `is` between equal values of seven types MAY differ either way. The contradiction is older than Question 37, but v0.33 rewrote and widened the neighbouring row and left the MUST standing.

Evidence: p1 row seven 11, 12, with a = pair(); b = pair():
id(a) == id(b), id(BytesIO(x).getvalue()) == id(x), id(StringIO(s).getvalue()) == id(s):
CPython (True, True, False) | compiled (False, False, True)
seen = {id(a): 'first'}; seen[id(b)] = 'second'; (id(b) in {id(a): 1}, len(seen)):
CPython (True, 1) | compiled (False, 2)
spec:43 "a decision on an identity relationship (a is b, membership in an identity-keyed dictionary) is inside it, because relationships are preserved under renaming"
deviations.toml:11 `observable = "unobservable in value; identity relationships are preserved up to a consistent renaming within one run"`
DECISIONS.md:25 "Accept the address and identity deviations; identity relationships are preserved up to renaming."

Probe: review/q37/p1 row seven

Suggested: Add "but for the identities D-03 leaves free" in the four places (the spec's words are the author's).

> Verifier: **confirmed** (medium). Spec section 2 (dialect-spec.md:34 MUST, :43 'a is b ... inside it, because relationships are preserved under renaming'), deviations.toml:11 (D-01 observable) and DECISIONS.md:25 promise every identity relationship, but D-03 / row :35 let `is` between equal immutable values (and so id equality and id-keyed dict membership) differ either way. The four places do not except D-03's identities. Pre-existing, left standing when v0.33 widened the neighbouring row. Words only; compiled behaviour is covered by D-03. Cover: None. D-03 / row :35 cover the compiled behaviour only; nothing records the clash between them and :34/:43/D-01/decision 1. Strongest case for the work: specific row and D-03 override the general promise, and D-03 says an identity difference changing another observable is a defect.

### F48-q37-6 (RL-959, with the same subject): D-31 (Question 33, the same day) says marshal's bytes never differ in length; D-03's identities change the length

*inconsistency, reported as medium*; where: docs/dialect-spec.md:243; docs/deviations.toml:197; TODO.md:868-871; docs/DECISIONS.md:1892 ("at equal length")

D-31: the bytes differ "in type bytes and in back-reference numbers, never in length or in what marshal.loads returns". CPython's w_ref (marshal.c:383) keys its table by the object's address and writes a five-byte reference for an object already written, so the length depends on whether two equal values are one object, which D-03 leaves free in both directions. marshal is not built yet, so this is a prediction for the queued port and a contradiction in the words now: either "never in length" is false or these are what D-03's last sentence calls a defect. Question 33's case rows have no such pair.

Evidence: cp/marsh.py under CPython 3.15.2, len(marshal.dumps([a, b])):
[pair(), pair()], a is b: 22; two equal tuples that are two objects: 29
[x, BytesIO(x).getvalue()], a is b: 22; two equal bytes, two objects: 29
[s, StringIO(s).getvalue()], two objects: 31; [s, s]: 23
[big, +big], a is b: 29; [big, big + 0], two objects: 43
In each pair the compiled program has the other identity (p1 row seven 0, 1, 5; row int 1).
marshal.c:383 w_ref: `entry = _Py_hashtable_get_entry(p->hashtable, v); if (entry != NULL) { ... w_byte(TYPE_REF, p); w_long((int)w, p); return 1; }`; :789 the table is made with `_Py_hashtable_hash_ptr`, `_Py_hashtable_compare_direct`.
p3 row marshal compiled: `bella: not implemented: importing 'marshal' (the standard library: step 3b)`, status 70.

Probe: review/q37/cp/marsh.py; review/q37/p3 row marshal

Suggested: Add to D-31's words the case where two equal values are one object on one side and two on the other, and put such a pair among the marshal step's case rows.

### F48-q37-7 (RL-977): "CPython already warns about code that depends on it" is false for all the widening added, and the lint is partial, not "Yes"

*words, reported as medium*; where: docs/dialect-spec.md:35 (reason) and :218 (lint column); docs/deviations.toml:23-24 (lint = "yes", note)

CPython warns only where an operand of `is` is a literal (codegen.c:1860, check_is_arg); none of the decision's seven rows warns. The lint is given as "Yes: `is` or `is not` where an operand is a literal, or its declared type is" one of the seven; the register has `partial` and D-03 says `yes`. Eleven programs differ compiled with no operand that is a literal or declared one of the seven: parameters declared object, a type parameter, a union with None, Sequence[int], Hashable; operator.is_; unittest's assertIs; a memo on `key is not self.key`. To the letter the first half also takes `x is None`.

Evidence: cp/warns.py, compile() with every warning recorded:
x is 1, 'a', b'a', 1.5, 2j, (), (1, 2): "is" with '<type>' literal. Did you mean "=="?
x is -1, x is frozenset(), x is None, x is True: none
pair() is pair(); io.BytesIO(x).getvalue() is x; io.StringIO(s).getvalue() is s; os.path.splitroot(p)[2] is p; f.mode is m; t.newlines is t.newlines; struct.unpack('5s', x)[0] is x; a is b: none
p3 row lint (CPython | compiled):
same(pair(), pair()), a: object, b: object: True | False
same_generic, a type parameter: True | False
same_optional, tuple[int, int] | None: True | False
same_sequence, Sequence[int]: True | False
operator.is_(pair(), pair()): True | False
unittest's assertIs(pair(), pair()): failures=0 | failures=1
a memo that recomputes when `key is not self.key`, runs after three calls: 1 | 3
copy.deepcopy([[a], [b]]), the two copies one object: True | False

Probe: review/q37/cp/warns.py; review/q37/p3 row lint

Suggested: Reword the reason ("CPython warns where an operand is a literal") and set lint = "partial", naming what it cannot see: an operand declared object, a type parameter, a union or a protocol, and operator.is_.

> Verifier: **confirmed** (medium). 'CPython already warns about code that depends on it' (spec :35, :271, deviations.toml D-03 note) is true only for a literal operand (codegen.c check_is_arg: constants other than None/True/False/Ellipsis, and tuples of constants), not for the library-function rows, `a is b`, operator.is_ or assertIs. The lint is `Yes`/lint='yes' but a static rule on literals/declared types is silent on 11 differing shapes (object, type parameter, X|None, Sequence, Hashable, operator.is_, assertIs, memo, deepcopy); it should be `partial`, and the literal half should exclude None/True/False/... as CPython does.  ... Cover: None. No RL, TODO or DECISIONS text says the warning is literal-only or the lint partial; TODO.md:773-775 lists the lint rule as 'Left'. Strongest case for the work: 'already warns' read as the classic literal case, the lint wording was approved by the author in Question 37 (DECISIONS.md:1906), and  ...

### F48-q37-8 (RL-978): The folding step as queued leaves out part of what CPython folds and names a mechanism that would merge unequal constants

*follow-through, reported as low*; where: TODO.md:776-783; docs/DECISIONS.md:1906; pipeline/backend/cpp.py:214-222; docs/deviations.toml:154 (D-25)

Nothing is built; these are for the step. (1) fold_tuple_of_constants gives up above 30 items; a longer tuple is still one constant, by fold_constant_seq_into_load_const, which neither document names. (2) "The folded value a module constant (K_n)": the backend keys a tuple constant by the tuple, so (1, 2), (1.0, 2.0) and (True, 2) are one K_n, and (0.0,) and (-0.0,): values, not identity. Unreachable from source today. (3) The rows for `x in [1, 2]`, `for x in [1, 2]`, `x in {1, 2}` and "the counts of objects made" have nothing a case can print. (4) Folding a quotient of two long literals ends a clause of D-25; TODO does not say.

Evidence: flowgraph.c:1540 `if (seq_size > _PY_STACK_USE_GUIDELINE) { return SUCCESS; }`; :1590 fold_constant_seq_into_load_const, called at :2605 (INTRINSIC_LIST_TO_TUPLE) and :2617.
p1 row const 13: a tuple of 35 ints, flong() is flong(): CPython True | compiled False.
Emitter.const run alone under CPython (no build):
(1, 2) -> K_1, (1.0, 2.0) -> K_1, (True, 2) -> K_1, (0.0,) -> K_5, (-0.0,) -> K_5
K_1 = rt::tuple_new({Obj::small(1), Obj::small(2)}).release();
cpp.py:220-222 `if type(value) is tuple and all(_supported_constant(v) for v in value): ... return self.lazy(("tuple", value), ...)`
CPython keeps them apart, p1 row const 16-19: ftup_float() is ftup_int() False; types float, int, bool; ((0.0,), (-0.0,)).
pipeline/l1/grammar.py:50 Const has no tuple value, so the path is not reached today.
D-25: "a quotient or remainder of two integer literals of that length, which CPython's compiler folds, is computed when the program runs, and looks".
flowgraph.c:2009: `~` on a bool is not folded (its DeprecationWarning at each run, measured), so an inexact fold is not always identity only.

Probe: review/q37/p1 row const

Suggested: Name fold_constant_seq_into_load_const in the step; key folded constants as CPython's _PyCode_ConstantKey does and put (1, 2) beside (1.0, 2.0) and (0.0,) beside (-0.0,) in the case; move the unobservable rows to a design test; end D-25's clause with it.

> Verifier: **refuted** (low). Substance holds, but one quotation is not verbatim: the finding quotes "The folded value a module constant (K_n)"; TODO.md:782 reads "the folded value a module constant (`K_n`, `init_constants()`)". Verified: flowgraph.c:1540 gives up above _PY_STACK_USE_GUIDELINE (=30, pycore_compile.h:24); fold_constant_seq_into_load_const (1590) is called at 2605 and 2617; a 35-item literal tuple is one constant in CPython (codegen.c starunpack_helper_impl's big branch emits LIST_TO_TUPLE). Emitter.const output matches exactly. p1 const 13: CPython True, compiled False; const 16-19 match. D-25 quote occurs  ...

Minor, one line each, not verified:

- REPORT.md was not written: this session's Write tool refuses report files from a sub-agent, and I did not go round it. The full account is in these fields; every probe, its rows and both sides' outputs are under review/q37/ (p1 to p4 with out.txt; cp/ and bl/ per group; cpython-src/).
- What holds: the entry's seven rows are as it says on both sides, every pair equal (p1 row seven); the four function names, TODO's line numbers (1529, 1697, 1946, 2035) and the four limits (128 bits, 256, 4096, 1024) are flowgraph.c's at v3.15.2; CPython's constant sharing is the same from source and from a cached .pyc (cp/pyc).
- docs/deviations.toml:24: "RL-699 to RL-704" takes in RL-702 and RL-703, which are not identity rows and are Fixed; DECISIONS and the commit message say "RL-699 to RL-701, RL-704". The same note says reviews A28 and A32 "found the other direction": two of the seven rows are the other direction, five are the old direction for other kinds.
- The entry names no recommendation, where the entries of Questions 39, 43, 44 and 46 say "Recommended was ..."; so who recommended what cannot be read from the record.
- Section 2's row says "a tuple of constants is made at each evaluation", which decision B itself ends: the row needs a new version when the folding step lands.
- pipeline/tests/test_review_2026_11_22_a32.py:5-7 and test_review_2026_11_21_a28.py:10 still say the identity rows wait for the author.
- No case or test holds the widened D-03, and the class was not swept before the words were written (the standing rule: a generated sweep of the class, kept as a test). p1 and p2 are such a sweep, 748 rows compared and 143 differing, and can be its seed.
- Inside the words, worth knowing: sys.intern(a) is not a compiled (a copy is interned; sys.intern(a) is sys.intern(b) holds on both sides); a BytesIO that was written to gives a new bytes at each getvalue() where CPython gives one object; CPython 3.15.2's small ints are one object from -5 to 1024 (measured), compiled up to the immediates.
- The lint's first half, "an operand is a literal", read to the letter flags `x is None`; CPython's own rule leaves out None, True, False and Ellipsis (cp/warns.py).

Covered: Read: the decision entry (docs/DECISIONS.md:1906), commit ec32f5b's whole diff, the spec's two rows and v0.33, deviations.toml D-01, D-03, D-25, D-31, TODO's two items and the marshal item, the review-log rows RL-623, RL-626, RL-699 to RL-704, RL-719, RL-720, the entries of Questions 29, 33 and 35, the backend's constant code (pipeline/backend/cpp.py:189-233) and BytesIO in runtime/prelude/_io.py. CPython's C read from v3.15.2 copies in review/q37/cpython-src: flowgraph.c (the folding functions, their call sites and limits), codegen.c (check_is_arg, codegen_slice), codeobject.c (should_intern_string), marshal.c (w_ref).

Measured under CPython 3.15.2 alone (review/q37/cp): the seven rows; which constants are one object within a function, between functions of a module, across modules and from a .pyc; small ints (-5 to 1024), interned strs, the empty tuple, str and bytes; which `is` forms the compiler warns about; marshal's length against identity; identity tests on immutable module constants in the manifest's 146 pure-Python modules, in the whole library (1038 files) and in the venv (904 files).

Compiled against CPython, four builds of six: p1 and p2, a sweep of 748 rows in 25 groups of which operation gives its argument back (str 87, bytes 51, int 156, float 48, complex 13, tuple 34, frozenset 20, constants 41, the empty and one-character values 36, names 17, other types 54) and of what identity could change besides `is` (a tuple's kept hash and the program's __hash__ calls 31, a frozenset's weak reference 19, a NaN in a list, dict, tuple and set 41 + 13, which of two equal keys is kept 44, storing, passing and returning 7 types by 24 ways, sentinels in argparse, optparse and a module of the program); p3, the lint's words against eleven programs and more shapes of a folded NaN; p4, the cost of four rows. 143 of the 748 rows differ; all but those of findings 1, 3 and 4 are inside D-03's words. Tuple, frozenset and float operations give the argument back exactly where CPython does (the one tuple row that differs is Question 29's, queued).

Each finding was searched for in the review log, DECISIONS and TODO before it was written; none is recorded there. Tracked files of the checkout are untouched (git status shows only .slots/, r48_both.py, review/).

Not covered: How the question was put in the conversation and which option was recommended: the repository does not have it, and reading the session's transcript was refused by the permission system, so options and recommendation are judged from the DECISIONS entry alone. REPORT.md: not written (the Write tool refuses report files from a sub-agent). The eval1 and eval2 legs and a lean-fidelity build: only the compiled exact build was probed. The folding pass, the marshal port and Question 29's step are not built, so finding 6 and finding 8 are about words and a queued step, not about behaviour. The test suite and the conformance corpus were not run; docs/design.md was searched for the subject, not read whole. Library functions beyond those swept (codecs, json, pathlib, re's internals, collections, itertools). Times in p4 are single runs on a shared host: the orders of magnitude are meant, not the figures. Two builds of the budget were not used.


## q38: Question 38

### F48-q38-1 (RL-979): Option B's stated effect is false for most class calls; built as worded it makes agreeing programs differ

*wrong-fact, reported as high*; where: docs/DECISIONS.md:1908; docs/dialect-spec.md:232 and :357; docs/deviations.toml:112; TODO.md:747-752; commit aff1dd2

The entry records B as "two entries for a class's call that enters a Python `__init__`, agreeing from a site's third call"; D-17 and TODO word it without condition. CPython takes two only in CALL_ALLOC_AND_ENTER_INIT, installed only for a call written with positional arguments, to a class whose metaclass is `type`, whose `__new__` is object's and whose `__init__` has no *args, **kwargs or keyword-only parameter. Every other class call takes one entry at every call: a keyword or unpacking in the call, an Exception/list/dict/int/str subclass, a Python `__new__`, a metaclass (abc.ABC), a call from C. Compiled agrees with CPython on these today; the queued rule would make them differ.

Evidence: Python/specialize.c v3.15.2: 1681 `if (Py_TYPE(tp) != &PyType_Type) goto generic`; 1684 `if (tp->tp_new == PyBaseObject_Type.tp_new)`; 1474 `if ((flags & (CO_VARKEYWORDS | CO_VARARGS)) || code->co_kwonlyargcount)`; _Py_Specialize_CallKw (1915-1941) has no class branch.
counts2/both.out, entries taken at eight calls of one site, CPython | compiled: `Plain()` 1x1 2x7 | 1x8. SAME at 1x8 on both: OneArg(x=1), OneArg(*ARGS), OneArg(**KW), Default(x=1), init(*args), init(**kw), init(*, k), Exception / list / dict / int / str subclass, __new__ and __init__, metaclass, abc.ABC, type.__call__, partial, map, operator.call. counts3: dataclass(x=1) 2x8 SAME, Generic alias 2x8 SAME.
Default limit, nothing set (counts2, rows nodes): `limit 1000 | Keyword 601 nodes: built`, `Keyword 991 nodes: built`, `Failure 991 nodes: built`: SAME on both sides; `Positional 601`: CPython RecursionError, compiled built.
cpy-explore/survey.py manifest.toml: `121 modules; {'total': 341, 'two possible': 198, 'metaclass': 56, "__new__ not object's": 42, '__init__ parameters': 45}`

Probe: review/q38/counts2 (rows entries e_plain, e_bases, e_meta; nodes), review/q38/counts3 (entries e_data, e_gen), review/q38/cpy-explore/survey.py

Suggested: Do not build TODO.md:747 as worded. Put it back to the author with these facts; if B stands: two entries only for calls CPython's instruction can serve, D-17 naming them, and case rows that hold the other shapes at one.

> Verifier: **confirmed** (high). B's wording (DECISIONS:1908, D-17, TODO:747) counts two entries for every class call entering a Python __init__. CPython takes two only via CALL_ALLOC_AND_ENTER_INIT: positional call, metaclass type, object's __new__, __init__ without *args/**kwargs/kw-only, class not written to. All other class calls take one and compiled agrees today; the step as worded would make them differ 2x. 'Most' is too strong by class count (198 of 341 classes in the manifest's modules can be served, 42% cannot) but true for every keyword/star call. Cover: none. Same verdict for c10-2 and s2-1.

### F48-q38-2 (RL-980): CPython 3.15.2 enters several kinds of frame without checking the limit; a compiled program raises RecursionError there, and nothing registers it

*defect, reported as high*; where: docs/dialect-spec.md:232 (D-17's row); docs/deviations.toml:112; pipeline/tests/test_recursion_counts.py (the sweep cannot see it)

D-17 lists where CPython's count differs, but CPython also enters some frames with no check of the limit: `f(*args)` or `f(**kw)` of a Python function, a bound method object called with a keyword, a generator resumed by `for` or `yield from`, and, until its frame stack's block is full, a property getter or `__getitem__` by subscript. A compiled program raises RecursionError at the limit there. At the default limit, nothing set, 1 100 generators chained in a loop yield their value under CPython and raise RecursionError compiled. The project's sweep cannot see it: each of its levels makes a plain, checked call. Nothing records it.

Evidence: Python/bytecodes.c v3.15.2: `_PUSH_FRAME` (4628) does `tstate->py_recursion_remaining--` and tests nothing; `_CHECK_RECURSION_REMAINING` (4611) is part of CALL_PY_EXACT_ARGS, CALL_KW_PY and CALL_ALLOC_AND_ENTER_INIT, and not of CALL_EX_PY (5763), CALL_KW_BOUND_METHOD (5542), LOAD_ATTR_PROPERTY (3070), BINARY_OP_SUBSCR_GETITEM (1366), FOR_ITER_GEN (4118), SEND_GEN (1740).
unchecked/both.out (each recursion stops itself at 20 000):
ROW ['stop', 'f(k, *args)', '60']: DIFF. CPython `f(k, *args) | limit 60 | 20000`, compiled `f(k, *args) | limit 60 | RecursionError`. The same for `f(k, **kw)` and `bound method called with a keyword`, and under 1000.
ROW ['reach', 'property']: DIFF. CPython `levels under limits 60, 60, 150, 1000: [152, 152, 152, 1094]`, compiled `[57, 57, 147, 997]`.
ROW ['reach', '__getitem__ by subscript']: CPython `[141, 141, 287, 1017]`, compiled `[57, 57, 147, 997]`.
ROW ['chain', 'yield from', '1100']: DIFF. CPython `yield from 1100 generators, limit 1000 | [1]`, compiled `... | RecursionError`; also 2000, 5000 and the `for` chains; 900 is SAME.
Controls SAME (RecursionError both): plain, keyword, method, method(k, *args).
Without a stop the f(*args) recursion ended CPython with status 139 under a 2 GB cap (cpy-explore/overshoot.py).

Probe: review/q38/unchecked (all 30 rows), review/q38/cpy-explore/overshoot.py and unchecked.py

Suggested: Ask the author: register in D-17 that a compiled program holds every frame to the limit where CPython 3.15.2 does not, with a case, or decide otherwise; consider a report upstream (not checked whether upstream knows).

> Verifier: **confirmed** (medium). D-17's list of where CPython counts otherwise omits frames CPython 3.15.2 pushes with no limit check: starred/double-starred Python calls, bound-method objects called with keywords, generators resumed by for/yield from, and (until its frame-stack block fills) property getters and __getitem__ by subscript. Pure recursions through them run past the limit on CPython (f(*args) 20000 levels under limit 60; 5000 chained generators under 1000; endless ends in SIGSEGV) and raise RecursionError compiled. q43's 'same level, last frame differs by one' and q42's 'narrow' hold only when a checked call is i ...

### F48-q38-3 (RL-981): For the measured shape too CPython's count depends on its interpreter's state; D-17 names only "first calls" and the planned case would not see the rest

*words, reported as medium*; where: docs/dialect-spec.md:232; docs/deviations.toml:112; docs/DECISIONS.md:1908; TODO.md:749-751; docs/reviews/review-log.md:1051 (RL-639)

A plain class called positionally takes one entry, not two, under CPython: (1) at a site's first call only, so agreement starts at the second call, not the third; (2) whenever its frame stack's block is full, one level in 82 for a minimal `__init__`, one in 37 with thirty locals; (3) when one entry is left; (4) for 52 calls after the class's dict was written, so a class that counts its instances takes one entry 52 times in 53; (5) at a site that calls two classes. D-17 names only (1). The planned case (limits 60 and 150, a two-line `__init__`) passes whatever is built for 2 to 5. `sys.setrecursionlimit` refuses another limit inside `__init__` too.

Evidence: counts2: `Plain() | 1x1 2x7`; pycore_code.h:454 `#define ADAPTIVE_WARMUP_VALUE 1`.
cpy-explore/chunk.py, warm sites: `Made limit 60: 29 61: 29 62: 30 150: 74 1000: 502`, a one-entry level at limits [163, 326, 489, ...]; `Wide ... 150: 75 1000: 505`, at [77, 150, 223, ...]. bytecodes.c:4778 `EXIT_IF(!_PyThreadState_HasStackSpace(tstate, code->co_framesize + _Py_InitCleanup.co_framesize))`.
cpy-explore/node_max.py: `limit 1000 | longest chain CPython builds: 505 | a count of two a level allows (1000 - 2) // 2 = 499`.
bytecodes.c:4612 `DEOPT_IF(tstate->py_recursion_remaining <= 1)`; counts2 `depth d_made 'counted without a call'`, limits 60, 60, 61: CPython [30, 29, 30, ...].
counts2: `class attribute written in __init__ | 1x1 2x1 1x52 2x1 1x52 2x1 1x22` (compiled 1x130); its depth [55, 55, 57, 145, 144, 987], a plain function's [57, 57, 58, 147, 147, 997].
counts2: `two classes in turn | the first class: 2x53 3x12 | the second: 3x53 2x12` (one entry is the helper's frame).
counts3 `setlimit - class`: `the lowest limit accepted:` CPython [6, 7, 7, 7, 7, 7], compiled [6, 6, 6, 6, 6, 6].

Probe: review/q38/counts2 (entries e_plain; depth d_made), review/q38/counts3 (setlimit), review/q38/cpy-explore (chunk.py, node_max.py, dynamic.py)

Suggested: Name the four other situations in D-17 (or decide them), write "second" for "third" in DECISIONS, RL-639 and TODO, and give the case a row for each: a wider `__init__`, limit 61, a class written to, a site with two classes.

> Verifier: **confirmed** (medium). For a plain positional class call CPython's count also depends on its interpreter state beyond D-17's 'first calls': warm-up is one call (agreement from the second, not 'third'); full frame-stack block (one level in 82, 37 with thirty locals); one entry left; 52 of 53 calls for a class that writes to its own attributes; a site calling two classes; setrecursionlimit lowest accepted 7 vs 6 inside __init__. All unrecorded. Case (4) is further evidence for q38-1; others are 1-11 level differences. 'Third' is imprecise but not false. Cover: D-17 names only 'a call site's first calls, before CPython specialises them'; DECISIONS:1908 'Copying CPython's warm-up was not offered: it follows its adaptive interpreter's counters per instruction' (partial, warm-up only).

### F48-q38-4 (RL-982): The options left out the direction of what each leaves, and the option between A and B

*missing-option, reported as medium*; where: docs/DECISIONS.md:1908

Two options were put, A (words) and B (two entries); the entry records no recommendation, where those of Questions 43 and 47 do. Not put: (a) with A the compiled count is never above CPython's, so a program CPython completes cannot get a RecursionError from a constructor; with B it can, wherever CPython takes one entry (findings 1 and 3), and "agreeing from a site's third call" hid that; (b) the option in between: two entries only where CPython's instruction can serve the call, the state-dependent rest in words; (c) any evidence that programs depend on the depth a constructor recursion reaches.

Evidence: docs/DECISIONS.md:1908: `The options were A (words only: the counter's one entry a call, and the constructor, a site's first calls and the import frames named) and B (two entries for a class's call that enters a Python __init__, agreeing from a site's third call; words for the rest). The author's words: "B".` No `Recommended was` (lines 1934 and 1954 have one).
Direction, measured at the default limit: counts2 rows nodes, `Keyword 601`, `Failure 991`, `Counted 601`: built under CPython and compiled today; two entries a call need more than 1000 for 601 nodes. cpy-explore/node_max.py: CPython builds 505 positional nodes, two a level allow 499.
CPython's own test asserts only that the error comes: Lib/test/test_class.py:814-827 (v3.15.2), testClassCallRecursionLimit, with the comment `Each call to C() consumes 2 levels, so offset by 1.`

Probe: review/q38/counts2 (nodes), review/q38/cpy-explore/node_max.py

Suggested: Put A, the option in between and B to the author again with the measurements of findings 1 and 3, and record the recommendation.

### F48-q38-5 (RL-983): decimal and datetime operations take entries where CPython's C takes none; neither D-17 nor D-20 names it

*words, reported as medium*; where: docs/dialect-spec.md:232 (D-17) and :249 (D-20); docs/deviations.toml:112 and :124

`decimal` and `datetime` are compiled from `_pydecimal` and `_pydatetime`, so an operation is 2 to 9 Python calls deep where CPython's C needs no entry. At the default limit, nothing set, a recursion 994 deep that multiplies a Decimal or moves a date at each level completes under CPython and ends in RecursionError compiled; a program's `tzinfo.utcoffset` is entered 1 to 3 entries deeper. CPython with `_decimal` and `_datetime` blocked agrees with the compiled program, so it is D-20's; but D-20 lists the differences observed (RL-98) and lacks this one, and D-17's list of where the depth differs lacks it too.

Evidence: counts2, rows bottom b_num, entries an operation needs as the last thing a recursion does, CPython | compiled: `Decimal + Decimal | [1, 1, 1]` | `[4, 4, 4]`; Decimal / Decimal 1 | 5; datetime + timedelta 1 | 6; datetime.timestamp 1 | 8; datetime.now 1 | 9. Rows entries e_dates: `tzinfo.utcoffset from str(datetime)` 1x8 | 4x8.
counts3: ROW ['natural', '-', 'decimal', '994']: DIFF. CPython `limit 1000 | decimal 994 levels: 2549`, compiled `limit 1000 | decimal 994 levels: RecursionError`. ROW ['natural', '-', 'datetime', '994']: CPython `2002-09-21`, compiled RecursionError. 990 levels: SAME.
With `PYTHONPATH=conformance/simulate BELLA_SIMULATE_BLOCK=_decimal,_datetime` CPython prints `decimal 994 levels: RecursionError` and the compiled program's entry counts (counts2/cpython_blocked.out; one row differs, timedelta.total_seconds 2 against 3, by finding 2's property getters).
The same by the missing OpenSSL module: hashlib.new [2, 2, 2] | [3, 3, 3], hmac.new [6, 6, 6] | [5, 5, 5] (counts3, bottom b_hash).

Probe: review/q38/counts2 (bottom b_num, entries e_dates, cpython_blocked.out), review/q38/counts3 (natural, bottom b_hash)

Suggested: Add a clause to D-20's list (or D-17's): an operation of decimal or datetime needs entries of the limit, so a recursion near it ends in RecursionError where CPython completes.

> Verifier: **confirmed** (medium). decimal (compiled from _pydecimal) and datetime (from _pydatetime) take 2-9 Python entries per operation where CPython's C takes one or none; a recursion within ~10 levels of the default limit multiplying a Decimal or moving a date completes under CPython (994 levels) and ends in RecursionError compiled. CPython with _decimal/_datetime blocked agrees with compiled. Neither D-20 (names only IsoCalendarDate repr; says unlisted _pydatetime differences are defects; _pydecimal not named) nor D-17's list names it. Words incomplete; practical effect narrow. Cover: No cover. Closest: D-20 'Only the differences listed here are accepted: another difference between `_pydatetime` and the C accelerator is a defect until it is listed' (RL-98) and spec :134 'Pure-Python fallbacks ... are compiled as ordinary modules'; D-17's list (first calls, __init__ pair, import f ...

### F48-q38-6 (RL-984): D-17's lint says "Yes: setrecursionlimit"; the differences show without that call

*words, reported as low*; where: docs/dialect-spec.md:232 (last column); docs/deviations.toml:115

The row promises a lint on `setrecursionlimit`. The differences of findings 1, 2, 3 and 5 show at the default limit in programs that never call it, so that lint flags none of them.

Evidence: Rows that differ under `limit 1000` with no setrecursionlimit on their way: counts2 `nodes Positional 601` (CPython RecursionError, compiled built); unchecked `chain 'yield from' 1100` (CPython [1], compiled RecursionError); counts3 `natural - decimal 994` (CPython 2549, compiled RecursionError). docs/deviations.toml:115 `lint = "yes"`; the spec's row ends `| Yes: `setrecursionlimit` |`.

Probe: review/q38/counts2, review/q38/counts3, review/q38/unchecked

Suggested: Reword to "Partial" with what the lint catches, or name what else it looks at (an `except RecursionError`).

> Verifier: **confirmed** (low). The spec's D-17 row (docs/dialect-spec.md:232, last column) reads "Yes: `setrecursionlimit`" and docs/deviations.toml:115 reads lint = "yes" in the [deviations.D-17] block (starts line 111). The three cited rows differ as stated, and none of their programs calls setrecursionlimit on the path: counts2 nodes Positional 601 (CPython RecursionError, compiled built); unchecked chain 'yield from' 1100 (CPython [1], compiled RecursionError); counts3 natural - decimal 994 (CPython 2549, compiled RecursionError). The finding's lint claim holds in a stronger form: no lint rule for setrecursionlimit exis ...

Minor, one line each, not verified:

- pipeline/tests/test_recursion_counts.py:12-14 still says "(RL-639, open)" and "one more on the calls made before the instruction specialises": it is one fewer, and only the first call.
- D-17's row and the register state the count of two in the present tense while f4ba545 counts one (counts2, row direct); it is queued in TODO, but the row has no "not yet".
- The entry at docs/DECISIONS.md:1908 records no recommendation, unlike the entries of Questions 43 and 47.
- D-17 says "the depth a program reaches with a given limit differs"; the limit sys.setrecursionlimit refuses differs as well (counts3, row setlimit - class: 7 under CPython, 6 compiled).
- Outside Question 38, not checked against docs/staging.md: a dataclass or NamedTuple class in a program module imported only inside a function stops the compiled program with "E-01: exec at dataclasses:_FuncBuilder.add_fns_to_class of a text the dry run did not stage" (counts2, rows e_lib, b_lib, d_bases); pipeline/build.py:437 runs the program's dry run with no program modules. Imported at module level the same classes work (counts3).
- review/q38/entries is an early CPython-only version of the probe and was never built; review/q38/counts is the build that stopped at the [P2+] override.

Covered: Reviewed at f4ba545: docs/DECISIONS.md:1908, the whole diff of aff1dd2 (words only: TODO, DECISIONS, deviations.toml, dialect-spec.md, review-log.md), the current D-17 row and register entry after Questions 43 and 47, section 8's Resources sentence, v0.34 and v0.42, RL-639 and RL-883, TODO.md:747, pipeline/tests/test_recursion_counts.py. The count of two is not built; it is queued, as the entry says.

How: CPython 3.15.2 alone (JIT available, not enabled; GIL build; ulimit -s 8192), CPython's C read from v3.15.2 (Python/bytecodes.c, specialize.c, ceval.c, ceval_macros.h, pystate.c, pycore_code.h, pycore_backoff.h, pycore_interpframe.h, in review/q38/cpython-src), and four builds through r48_both.py: counts (lost: the program stopped at a [P2+] __getattribute__ override before any row), counts2 (224 rows), counts3 (65 rows), unchecked (30 rows). Each folder has both.out and a table.txt of both sides.

Facts of the entry that hold, measured again: Made() from module level under 60 twice and 150: CPython [30, 29, 74, 74], compiled [58, 58, 148, 148]; a plain function [58, 58, 148, 148] on both; the sweep's __init__ row CPython [29, 28, 73, 73], compiled [57, 57, 147, 147] (RL-639's numbers); lru_cache and partial 20 000 deep under a limit of 100 000: RecursionError under CPython, 20000 compiled (RL-883); the second entry is the shim frame's (bytecodes.c:4808-4811); a compiled program takes one entry for every class call today. D-17's "some hundreds of thousands of plain calls": the compiled binary finishes 300 000 and raises at 380 000. RL-883's rewording ("at another depth, or not at all") is true. Spec row, register and Resources sentence agree with each other.

The project's sweep: its other 52 rows are SAME at this commit.

Neighbours that agree compiled (entries per shape, or entries needed as the last thing a recursion does): class body, generic class's parameter scope, class-body comprehension, type alias value, __annotations__, __set_name__, __init_subclass__, __class_getitem__, __instancecheck__, __subclasscheck__, match class pattern, __setattr__, __delattr__, __missing__, __set__, __delete__, __del__, __next__ in for, __exit__, nested generators, generator expressions, metaclass __call__, enum _missing_, __subclasshook__, Mapping.get, deepcopy, cached_property, singledispatch, contextmanager, json object_hook, re.sub with a function, OrderedDict, namedtuple, Counter, deque, heapq, bisect, struct, json, re, warnings, print, sorted, isinstance of an ABC, copy.copy, logging to a handler, and imports of what is imported (statement, dotted, from a module, from a package, importlib.import_module('sys') at 5 on both, __import__).

Consistency: Questions 43 and 47 narrowed the import clause and the five import rows agree; Question 42 touched only the threads' stack.

Not covered: REPORT.md was not written: the Write tool refused it ("Subagents should return findings as text, not write report files") and I did not go around the refusal. This output is the full account; the evidence is on disk under review/q38/ (counts2/both.out and table.txt, counts3/both.out and table.txt, unchecked/both.out and table.txt, counts2/cpython_blocked.out, cpy-explore/*.py, cpython-src/, cpython-tests/). If the file is wanted, it can be written from this output.

Not examined: the facts of D-17's import clause (the finder's and the locks' frames, Questions 43 and 47) beyond five rows; whether upstream CPython knows the unchecked frame entries of finding 2 or changed them after 3.15.2; LOAD_ATTR_GETATTRIBUTE_OVERRIDDEN (a __getattribute__ override is [P2+]); coroutines (async is [P2+]); threads; CPython with its JIT enabled; any count of real programs that depend on the depth a constructor recursion reaches; the run-time cost of either option. Two of the six builds were not used.


## q39: Question 39

### F48-q39-1 (RL-985): "A file left open is flushed and closed" depends on the order D-07 frees; CPython itself does not always flush, and file contents already differ compiled

*wrong-fact, reported as high*; where: docs/dialect-spec.md:195 (section 9); docs/deviations.toml D-07 summary; docs/DECISIONS.md:1910 ("What must stay CPython's ... programs rely on it")

The entry says what must stay CPython's is which objects are finalised, 'a file left open is flushed and closed ... and programs rely on it'; the spec and D-07's summary carry that parenthesis. Flushing is not a matter of which: a text file's three layers are all finalised either way, and the data arrives only if the text layer goes before the raw file, which is 'the order among them' that the same sentence frees. CPython 3.15.2 itself loses the data in a six-line program, and compiled programs differ from CPython in a file's contents in 11 of 15 simple rows, one of them losing data that CPython writes.

Evidence: CPython alone, review/q39/x1_files/nogc_min.py: `import gc; gc.disable(); def f(): pass; out = open('nogc_min.txt', 'w'); out.write('DATA')` leaves an empty file; without gc.disable(), or without the function, it holds DATA. why.py order (a file hanging off a dropped cycle): `raw __del__`, `buffered __del__`, `text __del__`, file empty. p1_sweep f_raw_hook: file b'' on both sides.
Compiled: `.venv/bin/python r48_both.py review/q39/p5_files --rows review/q39/p5_files/rows.txt` (build 6, both.txt). File contents, CPython / compiled:
lib_file (a library module's global log file; a global of the main module writes a last line in __del__): b'DATABYE' / b'DATA', the finaliser gets ValueError
list_file_first (held = [f, trailer]): b'DATABYE' / b'DATA'
list_trailer_first: b'DATA' / b'DATABYE'
main_file_lib_holds: b'DATA' / b'DATABYE'
nogc_file_made_first: b'' / b'DATABYE'
list_layers (held = [raw, buffered, text], a RawIOBase of the program's): b'DATA' / b''
list_layers_reversed: b'' / b'DATA'
4 rows agree (plain globals in both orders, a dict's values, instance attributes). Rerun on the built binary: the same.

Probe: review/q39/p5_files (rows lib_file, list_file_first, list_layers, nogc_file_made_first); review/q39/x1_files (nogc_min.py, why.py, shapes.py)

Suggested: Ask the author what is promised for a file left open: drop the parenthesis and point to section 9's 'with is the only guaranteed resource discipline', or promise it as an order (a file's layers outermost first) and register that contents may differ from CPython's.

> Verifier: **confirmed** (medium). The parenthesis 'a file left open is flushed and closed' (spec :195, D-07 summary, DECISIONS:1910 'programs rely on it') is an unconditional promise that CPython 3.15.2 itself breaks (gc.disable() plus a def leaves the file empty). The compiled file-content differences in p5_files are all order effects D-07 already frees (trailers writing into the file, a hand-layered raw/buffered/text list), and both sides finalise the same objects. So the wording is overstated, but no runtime defect and no decision rests on it. Reported high is too strong. Cover: Partly covered by spec :195 and D-07: 'the order among them, and the step of the exit ... are unspecified (D-07)'. Not covered: the flush caveat. grep 'flushed|left open' in docs finds none.

### F48-q39-2 (RL-986): CPython's language reference guarantees one order at exit (single-underscore globals first), the one the `alive` row checks; the entry quotes the sentence before it and says 'unspecified in CPython too'

*wrong-fact, reported as high*; where: docs/DECISIONS.md:1910; docs/dialect-spec.md:37 and :222; docs/deviations.toml D-07 note

The author's condition for B was 'programs don't care as cpython does not promise'; the entry answers 'it does', citing the reference's warning that a finaliser's globals may be deleted or None. The next sentence of that paragraph is a guarantee: single-underscore globals are deleted before other globals. That is the order of the `alive` row, which the entry calls 'the order inside a module's wiping that D-07 leaves free'. So 'Unspecified in CPython too' is false for it. And the reference leaves open which objects are finalised, the half the spec's row says is not unspecified. The guarantee is recorded nowhere in docs/ or TODO.md.

Evidence: Doc/reference/datamodel.rst of v3.15.2, lines 2082-2089 (review/q39/src_cpython/Doc_reference_datamodel.rst): '__del__() can be executed during interpreter shutdown. As a consequence, the global variables it needs to access (including other modules) may already have been deleted or set to None. Python guarantees that globals whose name begins with a single underscore are deleted from their module before other globals are deleted; if no other references to such globals exist, this may help in assuring that imported modules are still available at the time when the __del__() method is called.' Line 2046: 'It is not guaranteed that __del__() methods are called for objects that still exist when the interpreter exits.'
docs/dialect-spec.md:37: 'Unspecified in CPython too; which objects are finalised is not (D-07)'.
`grep -rn 'single underscore\|guarantees that globals' docs TODO.md`: only review A43's text about a key's hash.
The runtime keeps the guarantee today: p1_sweep row w_side_kept, SAME on both sides: 'side._private: side.LABEL='side' side.helper=True', then 'side.public: side.LABEL=None side.helper=False'.

Probe: review/q39/p1_sweep, row w_side_kept; review/q39/src_cpython

Suggested: Put to the author: promise the single-underscore order (documented by CPython, implemented, and free for an exit that does not wipe at all), and reword 'Unspecified in CPython too' in sections 2 and 11 and in the register's note.

> Verifier: **confirmed** (medium). CPython's reference (Doc/reference/datamodel.rst v3.15.2 lines 2082-2089) guarantees single-underscore globals are deleted before other globals, and _PyModule_ClearDict implements it in two passes. The spec (:37, :222), D-07's note and DECISIONS:1910 say the order is 'unspecified in CPython too' and cite only the preceding warning sentence. The runtime keeps the guarantee (w_side_kept SAME, C-9-13 'alive' row). The cited fact is incomplete and the spec words are false for this one order; the guarantee is recorded nowhere in docs or TODO. B's outcome is not refuted, but the author's condition ( ...

### F48-q39-3 (RL-987): 'Which objects are finalised is CPython's' fails in four measured rows; the class is listed as known in the entry of 2026-11-23 but is neither registered nor queued

*defect, reported as high*; where: runtime/src/call.cpp:3733-3748 (finalize_at_exit); runtime/prelude/posix.py:1362, _csv.py:67, _struct.py:755; docs/DECISIONS.md:1791; docs/dialect-spec.md:195

An object whose only holder is a built-in module's own state is finalised at exit under CPython and never compiled: a callable given to os.register_at_fork, a _csv.Dialect subclass's object given to csv.register_dialect, a str subclass's object used as a struct format. So is a new object that a late finaliser stores in sys's dict. No deviation covers them, and D-07 now says which objects are finalised is CPython's. The entry of 2026-11-23 lists the class ('the state of a C module ... stays alive here as a root ... No case reaches it') as known and not exact; Question 39's words promised it the next day without an exception. The shapes are rare.

Evidence: p1_sweep (build 2) w_at_fork: CPython 'held by os.register_at_fork: LABEL='main' modules=False open=False print=False stdout=False', compiled no line. w_csv_dialect: CPython 'csv dialect: finalised', compiled no line. p3_sweep (build 4) w_struct_cache (struct.calcsize(Text('i'))): CPython 'a str subclass's object: finalised', compiled no line. p2_sweep (build 3) mk_hook_sys (sys.excepthook is a function of the main module; a global's finaliser stores a new object in sys.__dict__): CPython prints 'maker's child: LABEL='a copy' modules=False open=False print=False stdout=False stderr=False', compiled does not. Rerun on the built binaries: the same.
Read: finalize_at_exit lets go of four states by name (runtime/src/call.cpp:3743-3748: _contextvars, _codecs, gc, _warnings); _at_fork (prelude/posix.py:1362), _dialects (_csv.py:67) and _cache (_struct.py:755) are module-level names of preludes. CPython: Py_CLEAR(interp->before_forkers) at Python/pystate.c:883, before the last collection (900); PyDict_Clear(interp->sysdict) at 924, where the runtime has nothing after clear_module_dict(sys->dict) (call.cpp:3733). Modules/_csv.c and _struct.c not read.
docs/DECISIONS.md:1791 has the known gap; TODO.md:557 only points back at 'the known gaps'.

Probe: review/q39/p1_sweep rows w_at_fork, w_csv_dialect; review/q39/p3_sweep row w_struct_cache; review/q39/p2_sweep row mk_hook_sys

Suggested: Fix (let go of the three states where CPython does, clear sys's dict at the end) or register the class with the author's decision; keep a sweep of the preludes' module-level containers as a test (binascii._reverse_tables not tried).

> Verifier: **known** (low). The os.register_at_fork, csv dialect and struct-cache rows reproduce (CPython finalises, compiled never) but are instances of the gap DECISIONS:1791 lists as 'not exact, known and listed': 'The state of a C module that CPython frees with its module stays alive here as a root, for example _csv's dialects. No case reaches it.' TODO:557-558 points at it; fork is [P2+]. What remains is a words conflict with D-07 / section 9's unconditional 'which objects are finalised is CPython's'. One residue is in no document: a late finaliser storing a new object in sys.__dict__ (mk_hook_sys), because nothing  ... Cover: DECISIONS.md:1791 'The state of a C module that CPython frees with its module stays alive here as a root, for example `_csv`'s dialects. No case reaches it.' (list headed 'What is not exact, known and listed'); TODO.md:557-558 'the known gaps that entry and the one of 2026-11-23 list'; RL-326 'to lo ...

### F48-q39-4 (RL-988): 'The runtime follows CPython 3.15.2's order today' is false in 34 of 126 simple permutations; the recommended A could not have been kept

*wrong-fact, reported as medium*; where: docs/deviations.toml D-07 note; docs/dialect-spec.md v0.35 entry; pipeline/tests/test_exit_steps.py:6 and :33; conformance/cases/C-9-13 docstring; docs/DECISIONS.md:1910

A was recommended on 'the exit is CPython 3.15.2's own sequence ... C-9-13's rows agree compiled', and the register's note, the version entry and the design test say the runtime follows CPython's order. The steps are CPython's; the order of finalisers inside one collection is the collector's (D-04, as the entry of 2026-11-23 and the case's own comment say), and at exit nearly every object dies inside one collection. Objects in a global list or tuple, under gc.disable(), or spread over two modules are finalised in another order than CPython's. The test holds CPython's order only for rows with one object a collection. A would have promised an order the runtime does not have.

Evidence: `.venv/bin/python r48_both.py review/q39/p4_order --rows review/q39/p4_order/rows.txt` (build 5): 126 rows `<kind>_<order of making>_<order of binding>` of three objects with finalisers; 92 SAME, 34 DIFF (cpython.txt and compiled.txt beside it):
list_abc_abc: CPython 'c b a', compiled 'a b c' (a global list: 9 of 9; a tuple: 9 of 9)
nogc_cba_abc: CPython 'c b a', compiled 'a b c' (gc.disable(): 7 of 9)
two_abc_abc: CPython 'a c b', compiled 'b a c' (a and c globals of the main module, b of an imported one: 9 of 9)
Agreeing kinds: plain, aged, chain, dictv, late, cls, inst, cyc, cycd, side.
docs/deviations.toml, D-07's note: 'The runtime follows CPython 3.15.2's order today (H4, RL-514; finalize_modules' steps)'. Spec v0.35: 'though the runtime follows CPython 3.15.2's order'. pipeline/tests/test_exit_steps.py:33 `test_the_exit_keeps_cpython_order`. The case, line 145: '# alone: two in one collection have no order (D-04)'.
Also: what sys.displayhook or sys.breakpointhook holds is finalised with stdout=False compiled and True under CPython (p1_sweep w_displayhook; p2_sweep x_breakpointhook_obj, x_two_hooks); those names are missing from the runtime's sys, which is queued (TODO.md:124).

Probe: review/q39/p4_order (all rows; cpython.txt against compiled.txt)

Suggested: Reword the note, the v0.35 entry and the test's docstring: the steps are CPython's, the order within a step's collection is the collector's (D-04). Add to the entry that A was not deliverable as described.

> Verifier: **confirmed** (medium). The steps of the exit are CPython's, but 'the runtime follows CPython 3.15.2's order today' (D-07 note, spec v0.35 entry, test_exit_steps.py lines 6-8, C-9-13 docstring, TODO.md:743) is false in 34 of 126 simple placements: list, tuple, gc.disable() and two-module placements finalise in the collector's order. The behaviour is covered by D-07; the words are not. Option A was not chosen, so no decision rests on it. Cover: D-07 (accepted): 'the order in which objects still alive at exit are finalised, and the step...'; spec line 195 'unspecified (D-07)'. displayhook/breakpointhook part known: TODO.md:124 queues the 22 names of sys.

### F48-q39-5 (RL-989): The answer to the author's question joined order and step; 'sharpened' widened D-07; a one-directional cut was not put and no use was counted

*missing-option, reported as medium*; where: docs/DECISIONS.md:1910; docs/deviations.toml D-07 (summary, lint); docs/dialect-spec.md:195

D-07 read 'finalisation order of module globals at exit'. It now also frees 'the step ... (what it still finds of its module's globals, sys and the builtins)': a later runtime may hand a finaliser None where CPython hands it its module's function. That is a widening, recorded as 'kept and sharpened'. The author asked whether programs care; the answer cited the reference and 'the order has changed between versions' and counted nothing. That change (3.4) was made so that finalisers find their globals, and CPython's notes say why. An option that keeps the faster exit was not put: a finaliser finds at least what CPython's finds. The lint stayed 'no' without being put.

Evidence: Doc/whatsnew/3.4.rst in the v3.15.2 tree, lines 1825-1830: 'module globals are no longer forcibly set to None during interpreter shutdown in most cases, instead relying on the normal operation of the cyclic garbage collector. This avoids a whole class of interpreter-shutdown-time errors, usually involving __del__ methods, that have plagued Python since the cyclic GC was first introduced.' Python/import.c of v3.3.0 (PyImport_Cleanup) wipes __main__ first; finalize_modules has the same steps in 3.8.0, 3.12.0 and 3.15.2 (3.15.2 adds _PyImport_ClearLazyModules).
Measured, both sides the same (p1_sweep w_three, w_side, w_data): a module's globals are finalised with LABEL, print and sys.stdout there. p1_sweep t_named: a NamedTemporaryFile left open is removed on both sides.
`python -I review/q39/x2_evidence/scan.py <Lib of 3.15.2>` (tests left out): '42 __del__ methods; 29 read a global or builtin name directly; 23 call a method of self; 14 bind something as a default argument'.
Question 37, the same day, widened D-03's lint with its words; D-04 has a partial rule (classes with __del__ that can form cycles).

Probe: review/q39/x2_evidence (scan.py); review/q39/p1_sweep rows w_three, w_side, w_data, t_named; review/q39/src_cpython_doc, src_cpython_old

Suggested: Put the narrower cut to the author with this evidence (free only towards 'finds more than CPython'); record the change of D-07's reach as a widening; decide the lint.

### F48-q39-6 (RL-990): Weak-reference callbacks at exit are held by the P1 case as a promise but are not in the spec's words, and whether one is called is decided by order

*words, reported as medium*; where: docs/dialect-spec.md:195; conformance/cases/C-9-13_the_steps_of_the_exit.py (rows weak, weak_main, cmodule); TODO.md item as of 5496d9a

The entry and the TODO item say the case keeps 'which finalisers run, which never do, a weak reference's callback called'. The spec promises only which objects are finalised, and a callback is no finaliser of an object alive at exit. Under CPython whether it is called depends on where the reference and its referent sit (8 of 16 placements), so it is an effect of the order D-07 frees; a [P1] case holds what the spec does not say. All 16 agree compiled today. Also unnamed in the words: whether an exception in a finaliser is reported (standard error may be gone by then), and other modules' globals, where the parenthesis says 'its module's'.

Evidence: p2_sweep (build 3), rows wk_<the referent's place>_<the reference's place> over main, sys, a module kept from sys, a dropped cycle: 16 rows, all SAME. 'callback: called' in wk_main_sys, wk_main_kept, wk_sys_sys, wk_kept_sys, wk_kept_kept, wk_cycle_main, wk_cycle_sys, wk_cycle_kept; not in the other eight (wk_main_main, wk_sys_main, wk_kept_main, ...).
p1_sweep w_raiser: 'raiser: finalised', then 'Exception ignored while calling deallocator <function Raiser.__del__ at 0x...>' and KeyError, on both sides; w_raiser_hook (sys.excepthook a function of the main module): 'raiser: finalised' and no report, on both sides.
The case's row cmodule: 'late: binascii.hexlify=False os.path.join=False', names of other modules.
TODO.md at 5496d9a: 'The case keeps what section 9 promises: ... which objects are never finalised (`warnings`, `gc_callbacks`), and that a weak reference's callback is called'. docs/dialect-spec.md:195 has no word on weak references at exit.

Probe: review/q39/p2_sweep rows wk_*; review/q39/p1_sweep rows w_raiser, w_raiser_hook

Suggested: Ask the author on which side of D-07 weak-reference callbacks at exit fall and say it in section 9; name the report of a finaliser's exception; change 'its module's globals' to 'modules' globals'.

> Verifier: **confirmed** (medium). Case C-9-13 holds a weak reference's callback called (row weak) and not called (row weak_main) as P1 expectations, but whether it is called depends on where referent and reference sit relative to the exit's steps (8 of 16 placements), which D-07 declares unspecified. Spec section 9 says nothing on weak references at exit; only DECISIONS.md:1910 and TODO record that the case holds it. Minor: 'its module's globals' wording; a finaliser exception's report at exit is unnamed. Compiled behaviour agrees on all 16 and is covered by D-07. Cover: DECISIONS.md:1910: 'the rows' promise (which finalisers run, which never do, a weak reference's callback called) stays the case' records the case's content as decided, but not the contradiction with D-07 or the spec words; spec section 9 line 195 covers only 'which of the objects still alive are the ...

Minor, one line each, not verified:

- The split dropped a value that is neither order nor step: the abc row's 'registered: True True' (issubclass and isinstance through the ABC) is reduced to the tag 'registered' in the case; the two values are now only in the design test.
- 'The order has changed between CPython versions' is true as far as I could confirm for 3.3 to 3.4 only; finalize_modules has the same steps in 3.8.0, 3.12.0 and 3.15.2.
- RL-289 and RL-326 still carry 'Not a defect, D-07' from the old words; RL-326's shape agrees now (p1_sweep w_maker), except the late variant in finding 3 (p2_sweep mk_hook_sys).
- docs/design.md has no word on the exit; the runtime's 'current choice' lives in DECISIONS, the register's note and a test's docstring.
- pipeline/tests/test_exit_steps.py returns without a word when g++ is missing, so it passes without comparing anything there.
- p3_sweep d30_order: `os` precedes the program's first import in the compiled sys.modules although that module is what imports os; not investigated, possibly a stale observable in D-30.

Covered: Read: the entry (docs/DECISIONS.md:1910-1912), both commits' diffs (5496d9a, 293c2dc), the spec rows changed (lines 37, 195, 222, v0.35), docs/deviations.toml D-07, D-04 and D-30, TODO.md's item before and after, the entries of 2026-11-20 (RL-514) and 2026-11-23/24 (H4, A43), review-log rows RL-289, RL-326, RL-514, RL-923 to RL-936, RL-943 to RL-947, the case with its package, its record and the old record, pipeline/tests/test_exit_steps.py, and finalize_at_exit with the exit's entry in runtime/src/call.cpp. CPython 3.15.2's source fetched and read: Python/pylifecycle.c (_Py_Finalize, finalize_modules and its steps), Python/pystate.c (interpreter_clear), Objects/moduleobject.c (_PyModule_ClearDict, module_dealloc), Doc/reference/datamodel.rst, Doc/whatsnew/3.4.rst; for the claim about versions, Python/import.c of v3.3.0 and v3.8.0 and Python/pylifecycle.c of v3.12.0.

What holds: (1) the case's record is straight: under CPython the case with BELLA_CASE_STEPS prints the old record plus the one added line 'asker: finalised', and without it the new record, on btrfs and on tmpfs; compiled, both modes equal CPython (build 1, review/q39/p0_case). (2) ruff and a cold mypy are clean on the case and the design test. (3) The two sentences the entry quotes from the language reference are there. (4) The exit's steps are implemented with care: of 163 rows in three sweeps 144 agree, among them all 16 placements of a weak reference and its referent, all 15 resurrections, 24 of 25 finalisers that make a new object, print in a finaliser, logging's file, tempfile, signal handlers and atexit callbacks. (5) The author's B was the better of the two options put (finding 4 shows A could not have been kept).

Compiled, six builds through r48_both.py, outputs saved as both.txt in each folder: p0_case (the case, both modes), p1_sweep (66 rows: files left open, holders, ways out), p2_sweep (71 rows: weak references, finalisers that make objects or come back, sys's names), p3_sweep (26 rows: print in finalisers, logging, module order, what preludes hold), p4_order (126 permutations of order), p5_files (15 rows of file contents). CPython alone: 21 shapes of a file left open (x1_files), what decides the order among a module's globals (x3_order), a count of the standard library's __del__ methods (x2_evidence).

Differences seen and not reported: traceback text and addresses (D-06, D-28, D-01); stops by name (sys.path_hooks, sys.setprofile, a subclass of the module type); p1_sweep f_log_cycle (order inside a dropped cycle, D-04).

Not covered: REPORT.md was not written: the Write tool refused a report file in this session ('Subagents should return findings as text'), and I did not route around it; the full account is in this output and in the probes' both.txt files under review/q39/. The question as put in chat is not in the repository, so I judged it by the entry's account of it. I did not run pytest; the design test's comparison I made by hand from build 1. Not looked at: the lean mode, threads and async, eval1 and eval2 (the case is in neither baseline), the Docker image and CI. I measured CPython's orders of finalisers and did not derive them from Python/gc.c; Modules/_csv.c and Modules/_struct.c were not read, so those two rows are measurements only. Whether D-30 changes the exit's order is open: my rows (p3_sweep d30_*) agree, because in the compiled sys.modules `os` comes before a module that is the program's first import and itself imports os (row d30_order: '__main__ os q39lib' on both sides); I did not find out why, though D-30 says os is not there at the first statement. 'The order has changed between CPython versions' was checked for 3.3 against 3.8, 3.12 and 3.15.2 only.


## q40: Question 40

### F48-q40-1 (RL-991): A buffered writer hands a program's raw write() a bytes, CPython a memoryview: the twin of the difference the decision found, neither registered nor queued

*defect, reported as high*; where: runtime/prelude/_io.py:1460-1465 and :1496; docs/dialect-spec.md:119 and :361; TODO.md:806-808; docs/DECISIONS.md:1914

The entry found that BufferedReader hands a program's RawIOBase.readinto a memoryview under CPython and a bytearray compiled, and B makes the handed view [P1]. The same C file does it on the way out: _bufferedwriter_raw_write calls raw.write with a read-only memoryview (obj None). The prelude hands bytes, for BufferedWriter, BufferedRandom and BufferedRWPair. A raw write() that calls a bytes method on its argument works compiled and raises AttributeError under CPython; one that keeps its argument reads other octets later. The row's parenthesis, v0.36 and the TODO item name readinto alone; no RL, deviation or TODO line has the writer.

Evidence: CPython v3.15.2 Modules/_io/bufferedio.c:1984-1996: `PyBuffer_FillInfo(&buf, NULL, start, len, 1, PyBUF_CONTIG_RO)`; `memobj = PyMemoryView_FromBuffer(&buf);` `res = PyObject_CallMethodOneArg(self->raw, &_Py_ID(write), memobj);`. Prelude: `def _bf_raw_write(self: _Buffered, data: bytes)`, `res = self._a_raw.write(data)`.
.venv/bin/python r48_both.py review/q40/p1 --rows review/q40/p1/rows.txt (review/q40/p1/out.txt):
ROW ['raw_write'] DIFF. CPython: `write is handed a memoryview of 3 b'abc'`; compiled: `write is handed a bytes of 3 b'abc'`.
ROW ['raw_write_decode'] DIFF. CPython: `write: no decode on a memoryview`; compiled: `write: b.decode() gives abc`.
ROW ['raw_write_kept'] DIFF. CPython: `what the first write was handed, read after the second: b'XYZ'`; compiled: `b'abc'`.
p3 ROW ['BufferedRandom.write', 'b'] DIFF. CPython: `memoryview of 3 | readonly: True | obj: None`; compiled: `bytes of 3 | readonly: no such attribute`.
grep -n -i "_bf_raw_write\|raw.write\|hands a\|handed a" TODO.md docs/reviews/review-log.md docs/deviations.toml: only the readinto half (TODO.md:808) and RL-474, RL-751 (what write answers).
Same class, by grep of PyMemoryView_From over the v3.15.2 tree: Python/marshal.c:908, marshal.load calls file.readinto(view) (marshal [P1] since v0.30, port queued).

Probe: review/q40/p1 rows raw_write, raw_write_kept, raw_write_decode, rwpair; review/q40/p3 rows 'BufferedRandom.write'

Suggested: Add the writer to the TODO item and, in the author's words, to the row's parenthesis; case rows for BufferedWriter, BufferedRandom and BufferedRWPair; a line in marshal's TODO item for what load hands readinto.

> Verifier: **confirmed** (medium). A BufferedWriter, BufferedRandom or BufferedRWPair hands a program's raw write() a bytes; CPython hands a read-only memoryview with obj None (bufferedio.c:1976-1996). A kept argument reads later octets under CPython, and bytes methods work compiled but not under CPython. The spec's general clause 'a view where CPython hands one to the program' already makes it [P1], but its parenthesis, v0.36, Question 40's entry and TODO.md:806-808 name readinto alone, so the queued step omits the writer. marshal.load's readinto(view) is a future port, not a present difference. Cover: Partly: spec row 'a view where CPython hands one to the program (a buffered stream calling a program's own readinto)' makes the writer [P1] by its general clause; TODO.md:806-808 'a buffered stream handing a program's own readinto a memoryview' names readinto only

### F48-q40-2 (RL-992): Five places answer a view with a TypeError where CPython takes it (int, float, bytearray ordering, os.setxattr, os.readinto); none stops by name

*defect, reported as high*; where: runtime/prelude/posix.py:2093-2096 and :2354-2357; runtime/src/ops.cpp:671; docs/dialect-spec.md:119; TODO.md:804-805; pipeline/tests/test_memoryview.py (CONSUMERS)

The row (v0.29, again v0.36) makes a view [P1] wherever bytes-like data is taken and wherever CPython writes into a buffer. A generated sweep of 188 consumers outside the test's 51, each with three kinds of view (564 rows): 469 agree, 84 stop by name, 11 differ silently, in five places: int(view), float(view), bytearray <, <=, >, >= a view (and bytearray.__eq__(a, view) called directly), os.setxattr(p, n, view), os.readinto(fd, view). Each agrees for bytes and bytearray. os.readinto is a buffer written into that the TODO item does not name (os.readv and os.preadv, which it names, stop). Older than the two days; not in the review log.

Evidence: r48_both.py review/q40/p3 --rows review/q40/p3/rows.txt, CPython | compiled (both status 0):
int c: 12 | TypeError;  int bad c: ValueError | TypeError
float c: 1.5 | TypeError;  float nan c: 'nan' | TypeError
bytearray ordered c: (True, True, False, False) | TypeError
bytearray methods c: (False, True, True, False) | (NotImplemented, NotImplemented, NotImplemented, NotImplemented)
sorted c: ['memoryview', 'bytearray'] | TypeError
os.setxattr c: b'value' | TypeError
os.readinto w: (5, b'12345.') | TypeError
Rows b (bytes) and a (bytearray) of each: SAME. The 564 rows: review/q40/p2/out.txt.
CPython v3.15.2: Objects/abstract.c:1581 and Objects/floatobject.c:205 `PyObject_GetBuffer(.., PyBUF_SIMPLE)`; Objects/bytearrayobject.c:1240 "Bytearrays can be compared to anything that supports the buffer API"; Modules/posixmodule.c:15626 `value: Py_buffer`, :12095 `buffer: Py_buffer(accept={rwbuffer})`.
Runtime: posix.py:2093-2096 and :2354-2357 ask `_has_slot(x, "__buffer__")` and otherwise raise TypeError; the prelude's memoryview has no __buffer__ (conformance/names-baseline.txt:142) and these two lack the `_is_view` test the other converters have (posix.py:1214, :2062, :628). ops.cpp:671: `is_kind(a, Kind::ByteArray) && is_bytes_like(b)`.

Probe: review/q40/p2 (all rows), review/q40/p3 (rows int, float, 'bytearray ordered', 'bytearray methods', sorted, os.setxattr, os.readinto)

Suggested: Register in the review log; take the view in the five (or stop by name until the step); name os.readinto in the TODO item; add p2's generated consumers to test_memoryview.py.

> Verifier: **confirmed** (high). Four places answer a view with a TypeError where CPython takes it, with nothing registered and no stop by name: int(view), float(view), bytearray <, <=, >, >= view (and bytearray.__eq__/__ne__/__lt__/__ge__(a, view) giving NotImplemented), os.setxattr(p, n, view). All agree for bytes and bytearray. The fifth, os.readinto(fd, writable view), is known: TODO.md:804-805 queues 'the rest CPython writes into: sweep the preludes for w* arguments'; it is not named and raises TypeError rather than a stop. DECISIONS 2026-11-22 says a view is taken wherever bytes-like data is taken and each consumer is d ... Cover: os.readinto only: TODO.md:804-805 'the rest CPython writes into: sweep the preludes for `w*` arguments'. The other four: none found in TODO, DECISIONS, review-log, deviations

### F48-q40-3 (RL-993): "Released after the call, as CPython's does" is false: CPython does not release the view it hands a raw stream; what TODO queues is a difference nobody decided

*wrong-fact, reported as medium*; where: TODO.md:806-808; docs/dialect-spec.md:119; docs/DECISIONS.md:1914 (option B)

TODO queues "a buffered stream handing a program's own readinto a memoryview over its buffer, released after the call, as CPython's does". CPython 3.15.2 only drops its reference: a view the program kept is not released, has obj None, and is the stream's buffer itself (a write through it changes what the stream reads next). After a read larger than the buffer it points into storage CPython gave away: one write through such a view crashed CPython. Releasing at return is a sound choice, but it differs where CPython answers, so it needs the author's decision and a D-nn; the entry records no such question. The row's subject (a view of bytes or of a bytearray) does not fit a view of no object.

Evidence: v3.15.2 Modules/_io/bufferedio.c:1628-1642: `/* NOTE: the buffer needn't be released as its object is NULL. */` `memobj = PyMemoryView_FromBuffer(&buf);` `res = PyObject_CallMethodOneArg(self->raw, &_Py_ID(readinto), memobj);` `Py_DECREF(memobj);` and no release.
p1 ROW ['raw_readinto_kept'], CPython side: `readinto is handed a memoryview of 8` / `read(1): b'a'` / `the kept object after the call: length 8 first four b'abcd'` / `after a write through the kept object the stream reads: b'Zcd'` (compiled: a bytearray, and b'bcd').
CPython alone, review/q40/cp1/handed.py (handed.out): `readinto: memoryview 8 None False B` (type, len, obj, readonly, format); `after the call: 8 None b'abcd'`; later `kept first view now: b'efgh'`; under BufferedReader.readinto(bytearray(32)) the raw is handed views with obj None and `resized while the kept view lives` (no export on the caller's bytearray).
review/q40/cp1/kept.py: read(20) over a buffer of 8, then `first[0:1] = b"Z"` through the kept view: `the kept view: released? no; obj None readonly False len 16`, then `Segmentation fault (core dumped)`, exit status 139 (run once; kept.out). bufferedio.c:1809-1837: the generic read hands views of a PyBytesWriter's storage.

Probe: review/q40/p1 row raw_readinto_kept; review/q40/cp1 (CPython alone)

Suggested: Correct the TODO sentence; put the kept view to the author (released at return as a registered deviation, or another choice) with these rows; the case prints type, obj, readonly and len inside the call only.

> Verifier: **confirmed** (low). TODO.md:806-808 says the buffered stream hands readinto a memoryview 'released after the call, as CPython's does'. CPython does not release it: bufferedio.c:1628-1642 notes the buffer needn't be released (object NULL), makes the view, calls readinto, and only Py_DECREFs it. A kept view stays usable with obj None and aliases the stream's buffer; a write through it changes what the stream reads next. Releasing at return would be an unregistered deviation, but no decision rests on the clause: Question 40's entry and the spec say only that a view is handed. The fix is to correct the clause and ask ...

### F48-q40-4 (RL-994): "All of a one-dimensional view of octets" is not all: cast stays [P2+] even where it changes nothing (cast("B")), and the row is still a list

*words, reported as low*; where: docs/dialect-spec.md:119 and :361; docs/DECISIONS.md:1914; the message of 5b1d923

The entry's title, the commit ("The bytes row now agrees with the Builtins row") and v0.36 say all of such a view is [P1]; the row keeps cast [P2+] whole. Read so, the cut is well defined (without cast only format B is reachable over bytes and bytearray). But m.cast("B") of such a view is such a view, and it is how the standard library writes a readinto (6 of its 9 cast calls outside tests); after the step a program's readinto is handed a view, and one written that way stops at cast. The record shows no option with it. Against it: no use in .venv's packages. The row also still enumerates and omits ==, hash, iteration, obj and nbytes, which are [P1] only by the Builtins row.

Evidence: p1 ROW ['cast_B'] and ['stdlib_idiom'] (`with memoryview(target) as view, view.cast("B") as byte_view: byte_view[:3] = b"abc"`): CPython `b'abcdef'` and `b'abc\x00\x00\x00'`; compiled, status 70: `bella: not implemented: memoryview.cast (CPython has it; the runtime does not yet)`.
CPython alone (review/q40/cp1/handed2.py): `m.cast("B") == m` True, `m.cast("B").obj is m.obj` True.
grep -rn "\.cast(" over Lib of 3.15.2 without test, idlelib, ctypes: compression/_common/_streams.py:67 `with memoryview(b) as view, view.cast("B") as byte_view:`; ssl.py:1323; _pyio.py:730 and :1187; wave.py:594; multiprocessing/connection.py:199 (all to B); subprocess.py:397 (b); re/_compiler.py:407 (I; replaced, manifest.toml:155); multiprocessing/synchronize.py:391 (i). None of the six is a phase-1 module.
grep over .venv/lib/python3.15/site-packages outside typeshed for .cast("B") or .cast('B'): 0 lines.

Probe: review/q40/p1 rows cast_B, cast_b, cast_c, stdlib_idiom

Suggested: Ask the author whether cast("B") in one dimension joins the step; otherwise reword v0.36's "all" (all but cast) and let the row say its list is not the limit.

> Verifier: **confirmed** (low). Record facts hold. The spec row (dialect-spec.md:119) says cast and the buffer protocol on a program's own classes are [P2+], and the row omits ==, hash, iteration, obj and nbytes. v0.36 (line 361) and the 5b1d923 message say all of a one-dimensional octet view is [P1]. Quote nit: DECISIONS:1914 has lowercase 'all', not the finding's 'All'. Stdlib grep over CPython 3.15.2 Lib (excluding test, idlelib, ctypes, site-packages) gives 9 cast lines; 6 cast to 'B' (_streams:67, ssl:1323, _pyio:730 and :1187, wave:594, multiprocessing/connection:199). The venv site-packages has 0 cast('B') lines. CPyt ...

### F48-q40-5 (RL-995): The exporters: io.BytesIO.getbuffer is the one other source of such a view in the phase-1 modules; it stays a stop, hashlib.file_digest of a BytesIO with it, and the record shows no option for it

*missing-option, reported as low*; where: docs/dialect-spec.md:66 and :119; runtime/prelude/_io.py:2398-2401; docs/DECISIONS.md:1914

In the modules of phase 1 one more thing gives a one-dimensional view of octets: io.BytesIO.getbuffer() (array and mmap are not in the manifest). The Builtins row leaves it [P2+] ("over bytes and bytearray"); the bytes row's list of what is [P2+] does not name it; the runtime stops with "[P2+]". hashlib.file_digest, which is [P1], calls it for a BytesIO and so stops. The stop is honest, but the author chose B because "it needs to be solid early on", and the entry's options are about what a view can do, none about where a view comes from.

Evidence: p1 ROW ['file_digest_bytesio']: CPython `hashlib.file_digest(BytesIO) -> 'ba7816bf8f01'`; compiled, status 70: `bella: not implemented: BytesIO.getbuffer (a memoryview: the buffer protocol, [P2+])`. ROW ['file_digest_file']: SAME (it passes the bytearray, Lib/hashlib.py:254).
Lib/hashlib.py:234-236: `if hasattr(fileobj, "getbuffer"):` `# io.BytesIO object, use zero-copy buffer` `digestobj.update(fileobj.getbuffer())`.
grep "getbuffer()" over Lib outside tests: hashlib 1, pickle 1, multiprocessing 7.
pipeline/tests/test_io.py:286 holds the stop; DECISIONS.md:1623 lists "[P2+] `BytesIO.getbuffer`" among three facilities. grep -n getbuffer docs/dialect-spec.md: nothing.

Probe: review/q40/p1 rows file_digest_bytesio, file_digest_file, getbuffer

Suggested: Ask the author; if it stays out, name a view of another object (BytesIO.getbuffer) in the row's [P2+] list so both rows say the same, and note that file_digest of a BytesIO stops.

### F48-q40-6 (RL-996): The queue and the row lean on sockets, which are [P2+]

*inconsistency, reported as low*; where: TODO.md:801 and :804; docs/dialect-spec.md:119 against :146; manifest.toml:109; docs/DECISIONS.md:1890 (Question 32)

The TODO item gives as the step's place "Before the 1c ports that need it (socket)" and lists socket.recv_into and recvfrom_into under "Case first, CPython passing"; the [P1] row names recv_into as an example. Sockets are [P2+]: section 7's Network row, the manifest's shim, and Question 32 of the same day (the socket shim: the import succeeds, the rest is [P2+]). So no port of 1c needs a view to write into, and recv_into can have no compiled case in phase 1.

Evidence: TODO.md:801 `Before the 1c ports that need it (socket).` and :804 `socket.recv_into` and `recvfrom_into`.
docs/dialect-spec.md:146 `| Network | socket, ssl, http.client, ... | [P2+]`.
manifest.toml:109 `socket = "import succeeds for logging.handlers type hints; sockets are [P2+]"`.
TODO.md:121 `the asyncio and socket shims (the manifest: the import succeeds, the rest is [P2+])`.
A search of the manifest's 121 compiled modules in Lib for readinto(, pack_into(, recv_into(, readv( and memoryview( gives 16 lines; the only write into a view is shutil._copyfileobj_readinto (shutil.py:237-239), taken on Windows alone (shutil.py:340-341 `elif _WINDOWS and file_size > 0:`); hashlib.file_digest passes the bytearray (hashlib.py:254 `size = fileobj.readinto(buf)`), tempfile passes the caller's buffer on.

Suggested: Drop "(socket)" as the reason and the two socket functions from the step (they come with sockets); in the row take recv_into out of the examples or mark it as arriving with socket.

> Verifier: **refuted** (low). The record facts hold: TODO.md:801 says 'Before the 1c ports that need it (socket).', TODO.md:804 has socket.recv_into and recvfrom_into, the Network row (spec:146) is [P2+], manifest.toml:109 is exact, DECISIONS:1890 is Question 32, and shutil.py:237-239 and 340-341 and hashlib.py:254 are as cited. The count is wrong: the stated search (readinto(, pack_into(, recv_into(, readv(, memoryview( over the manifest's 121 compiled modules) gives 18 lines, not 16. Dropping the 2 comment lines (hashlib:239, urllib/parse:943) gives 16, but the finding does not say that. Quote nits: the spec:146 quote dr ...

### F48-q40-7 (RL-997): __buffer__ and __release_buffer__ are queued "of the view itself"; those of bytes and bytearray, which make exactly such views, are not, and the Buffer ABC answers False for all three types

*follow-through, reported as low*; where: docs/DECISIONS.md:1914; TODO.md:802; conformance/names-baseline.txt:65-68 and :142-143; TODO.md:816

The entry adds "__buffer__ and __release_buffer__ of the view itself". bytes.__buffer__, bytearray.__buffer__ and bytearray.__release_buffer__ make the very views the row is about and are methods of the row's types ("All methods"); they are in the missing-names list, and the TODO item does not say whether they come with the step. Meanwhile isinstance(x, collections.abc.Buffer) is False compiled for bytes, bytearray and memoryview and True under CPython, silently: an instance of the open vars() item (TODO.md:816), which the step as queued would mend for memoryview alone.

Evidence: p1 ROW ['bytes_buffer']: CPython `bytes.__buffer__ -> b'abc'`; compiled, status 70: `bella: not implemented: bytes.__buffer__ (CPython has it; the runtime does not yet)`. ROW ['bytearray_buffer']: the same for bytearray.__buffer__.
p1 ROW ['abc_buffer'] DIFF, both status 0: CPython `Buffer: True True True False`; compiled `Buffer: False False False False` (bytes, bytearray, memoryview, str).
conformance/names-baseline.txt:65 `bytearray:__buffer__`, :66 `bytearray:__release_buffer__`, :68 `bytes:__buffer__`, :142 `memoryview:__buffer__`, :143 `memoryview:__release_buffer__`.
CPython alone (cp1/handed2.py): `b"abc".__buffer__(0)` is a memoryview with obj b'abc', readonly True; `bytearray.__buffer__(0)` holds the bytearray's size (`BufferError Existing exports of data: object cannot be re-sized`) until `ba.__release_buffer__(view)`.

Probe: review/q40/p1 rows bytes_buffer, bytearray_buffer, view_buffer, abc_buffer

Suggested: Say in the TODO item whether bytes' and bytearray's come with the step; a row for collections.abc.Buffer in the case.

> Verifier: **confirmed** (low). Record facts hold. DECISIONS:1914 says __buffer__ and __release_buffer__ 'of the view itself'. TODO.md:802 lists the view's __buffer__ and __release_buffer__, and no TODO line mentions bytes.__buffer__ or bytearray.__buffer__ (grep). names-baseline.txt has bytearray:__buffer__ (65), bytearray:__release_buffer__ (66), bytes:__buffer__ (68), memoryview:__buffer__ (142) and memoryview:__release_buffer__ (143), all exact. Runtime check: bytes has __buffer__ but no __release_buffer__ (the finding does not claim it does). Recorded probe: bytes.__buffer__ and bytearray.__buffer__ stop compiled (statu ...

Minor, one line each, not verified:

- The entry does not say what was recommended (those of Questions 39 and 43 to 47 do), nor a cost, nor a use count for the six: in Lib outside tests toreadonly is called once (pickle.py:1549) and __buffer__/__release_buffer__ directly never.
- The entry quotes the stops as "the runtime does not yet"; four of the six read so (hex, count, index, toreadonly); slice assignment stops as "memoryview slice assignment" and the writable buffers as "a memoryview as a writable buffer (...)" (review/q40/p1/out.txt).
- runtime/prelude/_io.py:7-8 says "a raw object of the program's stops by name"; it is handed a bytearray (p1 row raw_readinto), which is what the decision found.
- The stop for a program's own codec reads "it is given a memoryview (the buffer protocol: step 3b)" (p1 row codec): an internal step's name, and memoryview exists since 2026-11-22; the registry is [P2+], so the stop itself is right.
- memoryview._from_flags (conformance/names-baseline.txt:144) is named by neither the row nor the TODO item; compiled it stops by name (p1 row from_flags).
- docs/dialect-spec.md section 1 still says "This is v0.13"; the history is at v0.42.

Covered: Question 40's entry (docs/DECISIONS.md:1914), commit 5b1d923 whole (TODO.md, DECISIONS.md, dialect-spec.md; nothing built, and no later commit touches runtime/prelude/memoryview.py or _io.py), the row and v0.36 (dialect-spec.md:66, :119, :361), TODO.md:797-809, the decisions it stands on (2026-11-14, 2026-11-22, review A40), deviations.toml (no memoryview entry, and B needs none), design.md:802, memoryview.py read whole, the buffer converters of _io.py, posix.py and _struct.py, test_memoryview.py, C-6-25, names-baseline.txt. FACTS: every measurement of the entry holds again under CPython 3.15.2 and compiled (p1, 38 rows): hex, count, index, toreadonly, slice assignment, BytesIO.readinto(view) and struct.pack_into(view) stop by name, item assignment agrees, a raw readinto is handed a memoryview by CPython and a bytearray compiled; the two v0.29 rows disagreed as said; TODO's ValueError and TypeError for assignment hold. CPython's C was read at the tag v3.15.2 for every statement about it (bufferedio.c, memoryobject.c, typeobject.c, unicodeobject.c, marshal.c, bytearrayobject.c, abstract.c, floatobject.c, posixmodule.c). OPTIONS: B is the exact option, has no run-time cost that the code suggests and needs no deviation; I found no better answer to the question as a whole, only edges that were not put (findings 3, 4, 5). THE CUT: formats (only B without cast), cast, strided views (188 further consumers, p2), exporters of the phase-1 modules, what CPython hands a program (grep of PyMemoryView_From over the whole tree). CONSISTENCY: Question 35 (__sizeof__ with its step) agrees; Questions 32 and 33 in findings 6 and 1. Three of six builds used: review/q40/p1, p2, p3 (prog.py, rows.txt, out.txt each); CPython-alone probes in review/q40/cp1; CPython's sources in review/q40/cpython-tree and review/q40/cpython-src. No tracked file of the worktree was changed.

Not covered: How the question was worded to the author, what was recommended and whether costs were shown: the chat is not in the repository and reading the session transcript was refused by the permission system, so only the entry's own account was checked. REPORT.md was not written: the Write tool refused a report file in this session ("return findings as text"), so this answer is the full account and the evidence is in the probe folders under review/q40/. Not examined: the reference model's "Buffers" and the hold (RL-702) for the queued consumers; released views and callbacks that release a view on the 188 new consumers; lifetimes. No make, pytest or test module was run. Use counts beyond the standard library and the packages in .venv (no outside search was made).


## q41: Question 41

### F48-q41-1 (RL-998): An exact __basicsize__ and __itemsize__ (or an exclusion) was not among the options; their three sibling layout numbers are already CPython's from the runtime's own table

*missing-option, reported as medium*; where: docs/DECISIONS.md:1896 and :1916 (the options); docs/dialect-spec.md:38; TODO.md:826-836; runtime/src/types.cpp:1836-1877; runtime/src/cpython_names.inc; tools/cpython_names.py:76, 131, 138

Question 35 offered all four names as the runtime's own (A), all as CPython's with models of over-allocation (B), or all stopping (C); Question 41 only whether the row names the three attributes. The models concern __sizeof__ alone. __basicsize__ and __itemsize__ are one constant a type: the runtime already answers __flags__, __dictoffset__ and __weakrefoffset__ as CPython's from its generated table, the tool that writes the table already reads both numbers, a class's follow by a one-line rule, and RL-592 needs the same number. That cut was not put. Nor was an exclusion, though nothing in CPython's library, the targets or the corpus reads the two attributes.

Evidence: p1: __dictoffset__, __weakrefoffset__, __flags__ of 150 library types and 29 classes, 537 rows, all SAME (set.__weakrefoffset__ 192, type.__dictoffset__ 264, a plain class -1 and -32); row `attr builtins int __basicsize__`: CPython 24, compiled `bella: not implemented: type.__basicsize__`, status 70. cpython_names.inc: 417 `flags:` and 417 `offsets:` rows; 33 `itemsize:`, 242 `state:`, 198 `solid:` rows hold yes or no only. tools/cpython_names.py:76 `return t if t.__basicsize__ != base.__basicsize__ or t.__itemsize__ != base.__itemsize__ else base`. CPython Objects/typeobject.c:4714 `slotoffset = ctx->base->tp_basicsize`, :4759-4760 `type->tp_basicsize = slotoffset; type->tp_itemsize = ctx->base->tp_itemsize`; cpy/basicrule.py under 3.15.2: 138 bases, 565 classes made, 0 off "the base's plus 8 a slot". cpy/getstate.py: a class over property (__basicsize__ 64) raises TypeError from __reduce_ex__(2) until __slotnames__ has 6 names, (64-16)/8, so RL-592 needs the number, not the yes/no of the `state:` rows (the entry calls it "facts about which types have fields beyond object's"). Use: grep of the pin's Lib outside test and idlelib, the targets and conformance/cases: 0 reads of either attribute; venv packages: only mypy/stubtest.py:522, `t1.__basicsize__ != t2.__basicsize__ or t1.__itemsize__ != t2.__itemsize__`. The runtime's struct sizes and use beyond this machine were not measured.

Probe: review/q41/p1 (rows `attr ...`: 537 of offsets and flags, 10 of the two sizes); review/q41/cpy/basicrule.py and getstate.py (CPython alone)

Suggested: Before Question 35's step builds the two attributes from the runtime's structs, put to the author: (a) exact, from the names table and type_new_descriptors' rule, as the offsets and flags are; (b) an exclusion or stop, since nothing reads them; (c) as decided. The row's parenthesis follows the answer.

> Verifier: **confirmed** (medium). Questions 35 and 41 never put CPython's numbers for type.__basicsize__ and __itemsize__ alone: a names-table row per C type (tools/cpython_names.py:76,131,138 reads both, writes only yes/no rows) and, for a class, __base__'s plus 8 a __slots__ entry, as __flags__ and the two offsets are given. Cost unstated by the reviewer: CPython's object.__sizeof__(x) == type(x).__basicsize__ then fails beside the runtime's own __sizeof__. No reader in the installed library, targets or corpus. RL-592's need of the number is already recorded; only Question 35's sentence on it is wrong. Medium at its low edge. Cover: Nothing records the cut as put or rejected. Partly recorded: RL-592 (review-log.md:1004, Open): "It needs each C type's `tp_basicsize`, which the runtime does not have (sizes are its own, by the specification) ... Low: the names table could hold the sizes"; TODO.md:932-933: "the default state's size test over a C type with fields needs the type's size". The behaviour itself is covered by dialect-spec.md:38 (v0.37, Question 41 A): "`sys.getsizeof` values and the sizes they are made from (`__sizeof__`, a type's `__basicsize__` and `__itemsize__`) ... the compiled program's own sizes, not CPython's" - the row the two questions produced, so it does not answer a finding about their options.

### F48-q41-2 (RL-999): A [P1] case of the compiled baseline holds CPython's Struct.__sizeof__() number, and the Struct and buffered-stream preludes compute CPython's C sizes, against the row's "the compiled program's own sizes, not CPython's"

*test, reported as medium*; where: conformance/cases/C-7-36_struct.py:21; conformance/expected/C-7-36_struct.json; conformance/evalc-baseline.txt:144; runtime/prelude/_struct.py:577-578; runtime/prelude/_io.py:2093-2096 and 2611-2614; docs/dialect-spec.md:38 and :43; TODO.md:826-836

C-7-36 prints struct.Struct(">Q").__sizeof__() and its authoritative expectation records 128, so a compiled program must give CPython's number. It does, because the prelude repeats the C's arithmetic with CPython's struct sizes, as the buffered streams' prelude does. Since v0.37 the row names __sizeof__ among what may differ, "the compiled program's own sizes, not CPython's", and section 2 says the harness compares the first table only. The queued step (own sizes; its case "relations only, never a number") names neither Struct nor C-7-36: built as written, it leaves Struct's number CPython's or turns C-7-36 red. Question 39 moved rows of this kind out of C-9-13 the same day.

Evidence: C-7-36_struct.py:21 `print(s.format, s.size, s.pack(1), s.unpack(...), repr(s), s.__sizeof__(), type(s).__name__, ...)`; the expectation's first line `>Q 8 b'\x00\x00\x00\x00\x00\x00\x00\x01' (5,) Struct('>Q') 128 Struct _struct struct error`, 'status': 'P1', 'authoritative': True. _struct.py:578 `return 64 + 32 * (len(_ready(self)[0]) + 1)`; _io.py:2096 `return 152 + (self._g_buffer_size if bytearray.__len__(self._f_buffer) else 0)`; under CPython struct.Struct.__basicsize__ is 64 and io.BufferedReader.__basicsize__ 152. p2 `raw struct`: SAME on both sides, `[96, 128, 128, 192, 160, 128, 288]` for '', 'b', '>Q', 'bhi', '3s2xi', '10p', '<bhiqfd'; `raw buffered`: SAME, `4248 4248 664`; `raw bytesio`: CPython `64 64 197`, compiled `65 165 165` (RL-552, no change). Spec :43 "the conformance harness (section 10) compares exactly the first table, nothing more". TODO.md:831-832 lists "list and bytearray by capacity, dict and set by table, str, bytes, int by digits, tuple, the preludes' types with buffers". grep of TODO.md, DECISIONS.md and the review log for Struct's __sizeof__ or this number of C-7-36: nothing. _collections.py:705 and :1303 stop with "the size of the C's blocks" and "the C's node and fast-node table sizes".

Probe: review/q41/p2 rows `raw struct`, `raw buffered`, `raw bytesio`

Suggested: Take the number out of C-7-36's line (a relation, or the result's type) and record it again from CPython; add Struct, the buffered classes, deque and OrderedDict to the list of Question 35's step in TODO.

> Verifier: **confirmed** (low). Confirmed, narrowed. conformance/cases/C-7-36_struct.py:21 prints struct.Struct(">Q").__sizeof__() and the authoritative [P1] expectation holds 128 (all three baselines). It is the only second-table number the corpus holds, against spec :43 and :204 (the harness compares the first table and nothing else). The queued Question 35 step names neither Struct nor C-7-36. Overstated: the buffered classes are already in the step ("the preludes' types with buffers"), deque and OrderedDict are among its 163 stops, and the row permits equality, so nothing behaves wrongly. Low, not medium. Cover: No cover for the core (C-7-36's number; Struct absent from the step). Partial, for the rest: TODO.md:830-834 "a `__sizeof__` per kind whose storage varies (list and bytearray by capacity, dict and set by table, str, bytes, int by digits, tuple, the preludes' types with buffers) ... and the stop rows of the argument counts sweep (163 of its 182 stops)" queues the buffered classes, BytesIO, deque and OrderedDict; RL-552/RL-553 "No change ... a size is the runtime's own number (the specification's unobservable values)" close the differing BytesIO and deriving-class numbers; dialect-spec.md:38 puts `__sizeof__` in the MAY-differ table, so equality is permitted.

### F48-q41-3 (RL-1000): The decision says there are relations between sizes a program may rely on; the row promises none, and the queued case would hold them

*inconsistency, reported as low*; where: docs/DECISIONS.md:1896 and :1910; docs/dialect-spec.md:34, :38, :43; TODO.md:827-830

Question 35's entry says "the relations a program may rely on hold (a longer list is not smaller, a program's __sizeof__ is what getsizeof starts from)", and the queued case adds "a str's grows with its text" and "object's __basicsize__ is not more than list's". The row as Question 41 worded it says only that the numbers are the compiled program's own, and section 2 puts a program that decides on a second-table number outside the guarantee. The id() row shows how a promise of relations is written; this row has none, and neither option of Question 41 raised it. A conformance case with those rows holds what the spec leaves free, which Question 39 ruled out for D-07.

Evidence: DECISIONS.md:1896 as quoted. Spec :43 "A program that decides on the numeric value of a second-table item is outside the guarantee"; :34 (id) "every equality and inequality CPython shows between address-derived values MUST hold in the compiled program; only the numbers may differ". TODO.md:827-830 "Case first (CPython passes it): relations only, never a number (a longer list's size is not smaller, a str's grows with its text, a program's __sizeof__ returning n gives getsizeof at least n, ...)". DECISIONS.md:1910 "their order and steps move to a design test that holds the runtime's current choice". C-7-28_sys_surface.py:41 already holds `sys.getsizeof(object()) > 0`. Today, queued with the flat 64 (runtime/src/call.cpp:1375), p1 row `relations`: CPython True seven times; compiled `longer list not smaller True`, `longer list larger False`, `str grows with its text False`, `own n gives at least n True`, `bigger int larger False`, `wider text larger False`, `dict grows False`.

Probe: review/q41/p1 row `relations`

Suggested: Ask the author whether any relation between sizes is promised. If so it goes into the row in the author's words; if not, the queued case's relation rows belong in a design test, as C-9-13's order rows did.

> Verifier: **confirmed** (low). Question 35's entry (DECISIONS.md:1896) says "the relations a program may rely on hold", and TODO.md:827-830 queues a case whose rows are relations between sizes. The spec's row (:38) promises none, :43 puts a decision on a second-table number outside the guarantee, and no recorded option of Q35 or Q41 names a relation; Q39 moved such rows out of C-9-13. Added: CPython itself does not keep the two named relations in general, only for chosen pairs. Today's compiled output is the queued flat 64 and stops by name, no finding. The error and int rows are first-table and not in question.

### F48-q41-4 (RL-1001): Section 2 says bella-lint reports the read of a second-table value; no rule for the size names is recorded anywhere

*follow-through, reported as low*; where: docs/dialect-spec.md:43; docs/deviations.toml (no entry; header line 3); TODO.md:106-108 and :826-836; docs/design.md:38

The spec says of second-table values "`bella-lint` reports the read", and the linter is to walk docs/deviations.toml and the tier table. Question 35 decided "no deviation", so the register has no entry for sizes, and neither the TODO item nor the tier table names sys.getsizeof, __sizeof__, __basicsize__ or __itemsize__, which Question 41 put into the row. Every other second-table row a program can read has a register entry with a lint status (D-01, D-02, D-03, D-04, D-06, D-07). The register's header also says a difference from CPython not listed there is a defect, which by section 2 these are not.

Evidence: Spec :43 "...because relationships are preserved under renaming; `bella-lint` reports the read." TODO.md:106-108 "Write `bella-lint` as an `ast` walker over `docs/deviations.toml` and the tier table". deviations.toml:2-3 "A difference from the reference CPython (bella.toml, 3.15.2) that is not listed here is a defect." `grep -c "sizeof\|basicsize\|itemsize" docs/deviations.toml` prints 0; D-04's note there: "(a lint rule for a gc.collect() result, get_count() or get_stats() that reaches output is to come with bella-lint)". DECISIONS.md:1896 "So no deviation"; the question as it stood in TODO before fbe5df4 had offered "the runtime's own sizes as a registered deviation". design.md:38 lists the linter's tier reports: no size name among them.

Suggested: One line where the linter will find it: a register entry with lint = "yes" for the four names, or a line in TODO's item for Question 35; and narrow the register header's sentence to the first table.

> Verifier: **confirmed** (low). Confirmed, low, with corrections. Spec :43 says bella-lint reports the read of a second-table value and row :38 (v0.37) names the four size names; Question 35 decided "no deviation", so neither the register nor TODO (:826-836, :106-108) carries a lint line, where the same days' D-03 (:774) and D-31 (:873) items do. Overstated: the spec's own row and sentence are the rule; thread and performance rows also have no entry, and D-07 is lint "no"; the sentence, the getsizeof gap and the register header all date from 2026-11-01. A register entry would contradict Q35 and spec :210; a TODO line fits.

Minor, one line each, not verified:

- REPORT.md was not written: the Write tool refused it in this session ("Subagents should return findings as text, not write report files"), and I did not go around the refusal. The full account is this output; probes, their outputs and the fetched CPython sources are in review/q41/ (p1, p2, cpy, src_cpython).
- The entry of Question 41 (and of 35) records the options and the author's answer but not what was recommended; of the entries of 2026-11-24 only Question 39's does, those of 2026-11-25 all do.
- docs/dialect-spec.md:5 still says "This is v0.13" while the history ends at v0.42; docs/deviations.toml:1 says "dialect specification v0.7". Older than Question 41, untouched by v0.37.
- "the sizes they are made from (`__sizeof__`, a type's `__basicsize__` and `__itemsize__`)": getsizeof also adds what lies before the object (_PyType_PreHeaderSize, Include/internal/pycore_object.h:853-861), which is none of the three named. True enough as a summary.
- sys.getsizeof(x) answers 64 where x.__sizeof__() stops by name (32 of 34 kinds of object in p1 row `kinds`); queued with Question 35's step (TODO.md:833, "the flat 64 goes"), not a finding.
- My six p1 rows of a dataclass with slots defined inside a function stop with E-01 (exec of a text the dry run did not stage): a flaw of the probe, repeated at module level in p2, where all seven agree.

Covered: Read: the entries of Question 41 (docs/DECISIONS.md:1916) and Question 35 (:1896), commit 56196b0 in full (the row at docs/dialect-spec.md:38, the version entry at :363, TODO.md:826-827), TODO's items that touch sizes (:787, :808, :817, :826-836), RL-552, RL-553, RL-592, RL-567, RL-599, the older decisions on type flags, offsets, solid bases and the argument-count sweep, docs/deviations.toml, sections 2, 4 (E-03, E-05) and 10 of the spec, and the entries of Questions 29 to 47 for contact with this one (39 and 40 touch it; 33, 37, 38, 42 to 47 do not).

Result on the decision itself: the row is character for character option A of the entry, the version entry and the TODO line agree with it, nothing was built from it and nothing was dropped or widened. No compiled [P1] behaviour was found that differs from CPython outside what the row, a stop by name or an open review-log row covers.

Facts measured again, all holding. CPython 3.15.2 (review/q41/cpy/facts.py): getsizeof of [], [1, 2, 3], "ab", 10**30 is 56, 88, 43, 40; an own __sizeof__ of 100 gives 132; compiled 64 four times and 116 (p1 rows `numbers`, `own`). CPython's source at v3.15.2, fetched and read: Python/sysmodule.c:1932-1980 (_PySys_GetSizeOf: the TypeError, the ValueError, size + presize), :1995-2007 (the default only for a TypeError), Objects/typeobject.c:8522-8537 (object.__sizeof__ is tp_basicsize plus ob_size * tp_itemsize), :7217-7231, :4708-4760, :7979-8025, Include/internal/pycore_object.h:853-861. The flat 64 and the +16: runtime/src/call.cpp:1375, :1383. 163 of the 182 lines of pipeline/tests/argument_counts_stops.txt are __sizeof__; type.__basicsize__ and type.__itemsize__ stop by name. The errors are CPython's: p1 row `semantics` agrees on every line but the header's 16 against 32.

Compiled, two builds of the six allowed. p1 (583 rows, 550 SAME): the numbers, 34 kinds of object, seven relations, getsizeof's semantics (a __sizeof__ returning True, an int subclass, an __index__ object, a float; staticmethod, classmethod, instance attribute, metaclass, __getattr__, call counts, negative with and without a default, keywords), hasattr and dir, eight lay-out conflicts (all SAME), eleven __sizeof__ calls, 537 rows of __dictoffset__, __weakrefoffset__ and __flags__ over 150 library types and 29 classes (all SAME), ten rows of __basicsize__ and __itemsize__ (all stop). The 33 DIFF are sizes, stops by name and my six dataclass rows inside a function. p2 (112 rows, 110 SAME): raw __sizeof__ of the three library types that answer today, seven dataclass(slots=True) classes at module level, and for 101 objects whether a weak reference and a __dict__ agree with the type's offsets. The two DIFF are BytesIO's sizes (RL-552).

What else shows a size, checked: memoryview.nbytes and itemsize, struct.calcsize, Struct.size, sys.maxsize, sys.int_info and sys.hash_info agree (p1 row `data`); sys.getallocatedblocks stops by name; tracemalloc is E-03, sys.getrefcount and gc.get_objects E-05; array, resource and mmap are not in the manifest (D-20); pickle is [P2+]. In CPython's library outside its tests only collections.OrderedDict.__sizeof__ calls sys.getsizeof, only it and unittest.mock define a __sizeof__, and only dataclasses reads the offsets.

Not covered: How Question 41 was put in the chat and what was recommended: the entry does not record it and I have no other source. The runtime's own sizes themselves: Question 35's step is queued, not built, so nothing of "the compiled program's own sizes" could be probed, nor whether its relations will hold, nor what the runtime's structs would give for __basicsize__ (finding 1 says what may follow, not what was seen). Use of __basicsize__ and __itemsize__ beyond CPython's library, the six targets, the corpus and this venv's packages: no count over PyPI or public code, which the author's rule on evidence asks for. __sizeof__ of each of the 163 types (eleven tried), the names table's types beyond the 150 swept (417 in all), lean mode, and eval1 and eval2 legs. Whether the q35 reviewer reports finding 1 or the RL-592 remark from Question 35's side: I did not read other reviewers' folders. REPORT.md: not written, the Write tool refused report files in this session.


## q42: Question 42

### F48-q42-1 (RL-1002): The measurement's CPython figure (990) is the ceiling of what was tried, not CPython's depth

*wrong-fact, reported as medium*; where: docs/DECISIONS.md:1918; TODO.md:675-676; commit message of 6f0f149

The entry gives 'CPython 990 in the main thread and in a thread' as the deepest list json.dumps takes at the default limit; TODO.md and the commit message state it as CPython's reach ('reaches 990 levels under CPython'). The limit does not bound this walk in 3.15.2: the C encoder's guard is a stack-pointer check. CPython takes 57 973 levels in the main thread and 57 955 in a thread (8 MiB), 14 265 on a 2 MiB thread. '990 on the 256 MiB stack' beside it reads as parity: compiled takes 27 891 there, under half of CPython on 8 MiB. The compiled 800 and 100 hold. B does not rest on the figure, but TODO says the threads' size is decided 'from this analysis'.

Evidence: review/q42/cpy/json_depth.py main|thread (limit 1000, bisection): soft limit 8192: 57973 / 57955; ulimit -Ss 2048: 14275 / 14265; -Ss 262144: 1863823 / 1863836; -Ss unlimited: thread 14265 (glibc's 2 MiB). Source v3.15.2: Modules/_json.c:1606 `if (_Py_EnterRecursiveCall(" while encoding a JSON object"))`; Include/internal/pycore_ceval.h:211-218 `_Py_MakeRecCheck`: `return here_addr < _tstate->c_stack_soft_limit && ...`, no counter; Python/thread_pthread.h:41 `#define THREAD_STACK_SIZE 0 /* use default stack size */`. Compiled (p1 binary, `deepest json-list 100000`): default 27891; ulimit -s 8192: 848 (800 ok, 900 RecursionError); ulimit -s 2048: 194 (100 ok, 200 RecursionError); 9619 bytes a level against CPython's 144. r48_both row ['walk','json-list','100',...,'50000']: CPython ok at every depth, compiled RecursionError at 50000 only. Row ['deepest','json-list','200000']: CPython 57967, compiled 27891. Outputs: p1/out.txt, p1/direct.txt, cpy/outputs.txt.

Probe: review/q42/p1 rows 'walk json-list ...' and 'deepest json-list 200000'; review/q42/cpy/json_depth.py

Suggested: Correct DECISIONS.md:1918 and TODO.md:675-676 with the measured figures; say the limit does not bound a C walk, and that parity on it in a thread would take about 557 MiB at 9.6 KiB a level.

> Verifier: **confirmed** (medium). DECISIONS.md:1918, TODO.md:675-676 and the 6f0f149 commit message present 'CPython 990' as json.dumps's depth at the default limit. 990 was only the top of the set tried. CPython 3.15.2 reaches about 57,900 (main and thread, 8 MiB) and 14,265 on 2 MiB, because _json.c's guard is a stack-pointer check, not the counter. Compiled on 256 MiB reaches 27,891, under half of CPython on 8 MiB. The compiled 800 and 100 hold. Decision B is unaffected, since the real gap on 2 MiB (100 vs 14,265) is larger. The entry does say 'tried', but TODO and the commit do not.

### F48-q42-2 (RL-980, with the same subject): D-17's list misses the calls CPython 3.15.2 pushes without checking the limit: a starred call recurses past it

*words, reported as medium*; where: docs/dialect-spec.md:232 (D-17); docs/deviations.toml:112; docs/DECISIONS.md:1908 (Question 38); the Resources sentence Question 42 rewrote cites it

D-17 names two places where CPython counts otherwise (a site's first calls; the import system's frames). A third is not named: CPython's specialised CALL_EX_PY and CALL_KW_BOUND_METHOD push a frame with no check of the limit, so a recursion whose every call is f(*t), f(**d) or a bound-method object with keywords is never stopped (2 000 000 levels at limit 1000; an endless one ends by SIGSEGV), where the compiled program raises RecursionError at the limit. Any plain Python call a level hides it, which is why the 53-shape sweep (count() at every level) agrees. Narrow, and CPython's side looks like a defect, but nothing registers it. It is Question 38's text, met while measuring.

Evidence: p2 (41 shapes, no other call a level; limit 500, given up at 3000): 28 SAME. DIFF with CPython 'no error, 3000 levels' and compiled 'RecursionError at 496': f(*tuple), f(*list), f(n, *tuple), f(**dict), f(*tuple, **dict), lambda(*tuple), nested(*tuple), bound(n=n), Class.m(*tuple), Class.static(*tuple). Row ['f(*tuple)','1000','100000']: CPython 'no error, 100000 levels', compiled 'RecursionError at 996'. Also self[n]: 503 against 496; Class(n): 251 against 496 (queued, TODO.md:747); __getattribute__ stops by name. cpy/starred2.py 1000 2000000: 'f(*(n + 1,)) limit 1000 asked 2000000: returned 2000000'. cpy/runaway.py under ulimit -v 2097152: status 139. Python/bytecodes.c v3.15.2: CALL_PY_GENERAL (4498-4506) has `_CHECK_RECURSION_REMAINING +`; CALL_EX_PY (5763-5771) is `... _PY_FRAME_EX + _SAVE_RETURN_OFFSET + _PUSH_FRAME;`; _PUSH_FRAME (4628-4641) only does `tstate->py_recursion_remaining--;`. pipeline/tests/test_recursion_counts.py: every `go_*` calls `count()`.

Probe: review/q42/p2, rows 'f(*tuple) 500 3000' to 'Class.static(*tuple) 500 3000' and the four rows at 1000 100000; review/q42/cpy/starred2.py, runaway.py

Suggested: Ask the author: register it in D-17 (my expectation) or copy it. Either way a case with shapes that make no other call a level; test_recursion_counts.py cannot see it as written.

### F48-q42-3 (RL-1003): The main thread's words, said to agree with the runtime, omit that the stack is never smaller than the process's own; RL-884 says the opposite

*words, reported as medium*; where: docs/dialect-spec.md:183 (section 8, Resources); docs/DECISIONS.md:1918; runtime/src/core.cpp:982-990; docs/reviews/review-log.md RL-884

Section 8: 'the main thread's stack is 256 MiB ... no larger than the process's hard limit on its stack allows, unless the policy file says otherwise', and the entry says these words agree with the runtime. The runtime gives the larger of the process's own stack and min(policy, hard limit), and the process's own when the reservation fails. So a policy of 2 MiB under a default shell leaves the program on 8 MiB; with an unlimited soft limit the stack is larger than 256 MiB; under an address-space limit the program silently has 8 MiB. RL-884 says 'a policy of 1, 2 or 16 MiB the compiled program has that much stack': false for 1 and 2. The behaviour is reasonable; the words are incomplete.

Evidence: runtime/src/core.cpp:985 `if (!process_stack(have_low, have) || want <= have) return body(arg);`, 990 `if (region == MAP_FAILED) return body(arg);`. p3 is p1 with bella.toml `[platform] main_stack_mib = 2`. r48_both rows: ['deepest','json-list','100000'] compiled 846; ['shape','plain','1000000','400000'] compiled 10855: the 8 MiB figures (p1 under ulimit -s 8192: 848 and 10876). p3 binary directly: ulimit -Ss 4096: 410; -Ss 2048 or 1024: 194 (2 MiB: the policy); ulimit -s 1024: 85; -Ss unlimited: 100000 (all asked). p1 binary, `shape plain 100000000 <bound>`: default 356683; hard 65536: 88962; ulimit -Ss unlimited: 3000000 reached (the bound); ulimit -v 307200: 10864; ulimit -v 1048576: 356683. Review A39's text had it: 'A policy smaller than the existing process stack leaves execution on that stack'. So the entry's '100 on 2 MiB' was a ulimit run, not a policy. Outputs: p3/out.txt, p1/direct.txt.

Probe: review/q42/p3 (all rows); review/q42/p1/direct.txt, last two sections

Suggested: The words are the author's: offer 'the larger of the stack its process gives it and 256 MiB (or the policy's figure), within the process's hard limit'. Correct RL-884's sentence.

> Verifier: **confirmed** (medium). Section 8 and DECISIONS.md:1918 say the main stack is 256 MiB, bounded by the hard limit, unless the policy says otherwise. core.cpp:985 and :990 give the larger of the process's own stack and min(policy, hard limit), and the process's own stack when mmap fails. A 2 MiB policy under a default shell leaves 8 MiB. An unlimited soft limit gives more than 256 MiB. An address-space limit silently gives 8 MiB. RL-884 and DECISIONS:1698 say a policy of 1 or 2 MiB gives that much stack, which is false. design.md:804 covers only the hard-limit case. The behaviour is reasonable and the words are the aut ... Cover: Partial. design.md:804: 'where that is no more than the stack the process has, nothing is switched' (hard-limit case only). The codex A39 review file line 212 says 'A policy smaller than the existing process stack leaves execution on that stack', but RL-884 and the spec do not.

### F48-q42-4 (RL-1004): Assessment: the limit is real in kind and artificial in degree: frames grow with a function's length, invoke adds 384 bytes, and C walks run as compiled Python

*other, reported as medium*; where: pipeline/backend/cpp.py:722-730 (a block's temporaries); runtime/src/call.cpp:112-195 (invoke); runtime/prelude/_json.py:621-790; TODO.md:666-677

A compiled call being a native call is sound, and CPython's own C has the same limit. What makes it bite: (1) every value a function produces has its own 8-byte slot for the whole function, so a frame grows about 123 bytes a simple statement (464 bytes for none, 10 192 for 80; re._parser._parse 34 512); (2) invoke's two frames add 384 bytes to every call; (3) CPython's C walks run as compiled Python preludes: 3.8 to 14.3 KiB a level against CPython's 64 to 257 bytes, while the runtime's native walks (tuple hash 79, list == 655) are at CPython's depth. Inherent is only that a Python frame is on the native stack, so a raised limit, and a thread, depend on stack size.

Evidence: Bytes a level = 8 MiB / (depth under ulimit -s 16384 - depth under 8192), limit 10**8. plain 752 = f_plain 368 + invoke(init list) 80 + invoke(Obj, Args) 304 (prologues, tools/frames.sh); json.dumps 9619 = _encode_obj 4160 + _encode_list 4688 + 2 x 384. p4, k = 0/10/20/40/80 statements: frames 464/1728/2928/5392/10192, levels on 8 MiB 9652/3875/2471/1417/773; the same with the statements after the call; 464 with them in a helper. f_encode_list declares 149 temporaries and 15 locals and uses 571 distinct stack slots. p1: keyword 960, method 1152, with 1760, property 3985, map 4879, lru_cache 5936; CPython's C stack a level: 0 for Python calls, property 756, map 772, lru_cache 563, sorted 5326. Walks, levels on 8 MiB CPython/compiled: json.dumps 57970/848, json.loads 65219/968, repr list 74473/1864, list == 47391/12468, tuple hash 130369/102233. At limit 1000 on 2 MiB: lru_cache 317, partial 346, map 387, property 473 (CPython 995 each). 10 364 functions of one binary: median frame 496, p90 1728, p99 6112. fib(32): 3.2 s compiled, 0.39 s CPython. A CPython thread with stack_size(53248) reaches 99 995 levels at limit 100 000. p1/direct.txt, p4/direct.txt, tools/frames-p1.tsv, cpy/outputs.txt.

Probe: review/q42/p1 and p4 (binaries run under ulimit -s; tools/direct_p1.sh reruns p1's); review/q42/tools/frames.sh

Suggested: Correct TODO.md:668-670 ('about 690 bytes', '4 to 8 KiB a level') with these figures. The analysis it asks for is answered: slots never reused, and invoke. Approaches: the next finding.

### F48-q42-5 (RL-1005): Assessment, approaches: reuse slots and a thin invoke first (no run-time cost); json's walk native; grow the stack in segments for threads; not heap frames

*other, reported as low*; where: TODO.md:666-677 (Later: the stack a compiled program needs); runtime/src/core.cpp:954-1010 (on_main_stack); runtime/src/call.cpp:2827-2838 (enter_frame)

None was tried (the runtime cannot be rebuilt in this review); effects are estimates. A: give temporaries a stack discipline, or first a block a statement: a frame the size of the deepest expression; no run-time cost; the order live temporaries die in on unwinding must be kept. B: a thin invoke for plain functions: up to 384 bytes a call. C: _json's walk in C++ (67 times CPython's today). D: at the stack check, run the callee on a new segment; on_main_stack has the mechanism. A thread then needs no size and threading.stack_size(n) can be honoured. E: heap frames for every function: CPython's depth exactly, a new function model. F: larger reservations: silent 8 MiB under ulimit -v.

Evidence: A: p4's helper rows (frame 464 whatever k) show a frame without the statements' slots; pipeline/backend/cpp.py:722-730 `region` declares a block's temporaries once at its head ('Ref ' + ', '.join(...)), and already per `try` block. B: invoke(Obj, Args) is one 304-byte frame for every kind of callable (call.cpp:112-193); the function case is `return fn->entry(fn, a);` (116-119). C: native walks measured at 79 and 655 bytes a level. D: core.cpp:954-1010 (MainStackEntry, makecontext, swapcontext, `entry->error = std::current_exception()`); the check is in enter_frame (call.cpp:2827-2838), inside the callee's frame, and would have to come before it; cost of a switch not measured. F: p1 under ulimit -v 307200 reaches 10864 plain calls (the 8 MiB figure) with no message; kernel Documentation/mm/overcommit-accounting.rst:48 'In mode 2 the MAP_NORESERVE flag is ignored' (not run: this host is mode 1); no madvise in runtime/src, so touched pages stay resident; and 256 MiB still gives json.dumps 27891 levels against CPython's 57970 on 8 MiB.

Probe: review/q42/p4 rows 'helper k 3000 20000' and p4/direct.txt; review/q42/p1/direct.txt

Suggested: A and B first, independent of the rest; C when a port needs deep data; choose between D and F at the threads milestone with A and B measured (I expect D); E only if phase 2 does not depend on native calls.

Minor, one line each, not verified:

- The decision itself is sound and done as decided: B removed a number nothing implemented (git grep thread_stack at 6f0f149~1 finds only bella.toml:20); the spec sentence, both rows 16, v0.38, bella.toml and the TODO note agree with each other and with deviations.toml, and the author's words are in TODO verbatim.
- DECISIONS records the options and the author's words for Question 42 but not which option was recommended; the question's text is not in the repository before the answering commit (git log -S"Question 42" finds 6f0f149 first), so the recommendation could not be checked. The entries for Questions 35 to 47 are the same in this.
- TODO.md:668-670 figures are stale or partial: 'about 690 bytes' holds for the smallest function only (752 to 5 936 by shape of call, 10 564 for 80 statements); 'a prelude's walk takes 4 to 8 KiB a level' is 3.8 to 14.3 KiB now (json.dumps of dicts 14 315).
- The entries of Questions 28 and 42 explain CPython's depth on json.dumps by 'its Python frames are on the heap'; the walk measured is CPython's C encoder, which has no Python frame a level (144 bytes of C stack).
- self[n] recursing with no other call: CPython reaches 503 at limit 500, compiled 496 (p2); small, of finding 2's class, cause not established.
- Decision 16's original 'platform defaults: 2 MiB threads' (dialect-spec.md:286, column 3) was not the platform's default under a finite soft limit: glibc gives a thread the soft limit (8 MiB here, measured), 2 MiB only when it is unlimited. Question 42's entry has it right.
- bella.toml: thread_stack_mib left because nothing read it; [runtime] recursion_limit, int_max_str_digits, hash_randomisation, utf8_mode, assertions and [reference] dialect = "v0.7" (the spec is at v0.42) are equally unread by pipeline/ and tools/ (grep of every tomllib reader).
- A bella.toml that still has thread_stack_mib builds without a word (p3 has thread_stack_mib = 64): the policy reader takes no notice of unknown keys.
- No function of the p1 binary has a frame near the 192 KiB the stack watch keeps back (core.cpp:935; largest 56 864, the cmath prelude's module body), so the watch holds today; by the linear law of p4 a function of about 1 500 simple statements would pass it (not tested).
- Creating a thread stops by name with a right message ('bella: not implemented: creating a thread (the threads milestone, [P2+])', status 70), and threading.stack_size agrees with CPython on 7 values (p1 row 'stacksize': SAME).
- Side effect on the host: cpy/runaway.py makes CPython 3.15.2 end by SIGSEGV, as it is meant to show; two core dumps of about 71 MB each are with systemd-coredump (root-owned, not mine to remove).

Covered: Read: DECISIONS.md:1918 (Question 42), 1677 (Question 28), 1908 (Question 38) and row 16; the whole diff of 6f0f149; spec section 8 Resources, D-17 (spec and deviations.toml), decision row 16, v0.28, v0.34, v0.38, v0.42; bella.toml; TODO.md:666-677 and 747-758; design.md:804; review log RL-624, RL-642, RL-883 to RL-885 and review A39's text; cases C-8-20 and C-8-21; runtime/src/core.cpp:899-1010, call.cpp:112-260, 2827-2840, 3936-3962, 4385-4438; runtime.hpp:760-870; closed_world.py:249-264; runtime/prelude/_thread.py and _json.py:621-790; pipeline/backend/cpp.py:722-745; pipeline/examples/out/fib.cpp; the generated prelude__json.cpp; pipeline/tests/test_recursion_counts.py. CPython v3.15.2 sources fetched and read: Python/thread_pthread.h, Modules/_json.c, Include/internal/pycore_ceval.h, Python/bytecodes.c, Python/ceval.c.

Check 1, facts, each measured again. CPython 3.15.2: json.dumps depth in the main thread and in a thread under four soft limits and under six threading.stack_size values; a thread's stack follows the soft limit (true); Python frames on the heap (999 995 levels at limit 10**6). Compiled: 990 / 800 / 100 confirmed, real depths 27 891 / 848 / 194. Nothing read thread_stack_mib (true); closed_world.py reads main_stack_mib (true).
Check 2, options: A, B, C were the real choices for words about something not built; I found no better one, and B is sound by the project's rules.
Check 3, words: findings 1 and 3; the clause on other threads says nothing a program can see yet, which is right for [P2+].
Check 4, follow-through: all five things the entry says were done are done; nothing dropped or widened.
Check 5, consistency: no conflict with Questions 28, 38 (D-17's 'some hundreds of thousands of plain calls': 356 683 measured) or 47 (D-33 also waits for threads).

Builds: 4 of 6. p1 (25 call shapes, 14 walks, thread, stack_size; 30 rows), p2 (41 recursion shapes with no other call a level; 46 rows), p3 (p1 with a 2 MiB policy file; 6 rows), p4 (generated: frame size against statement count, a tree walker, fib; 18 rows). Each folder has prog.py, rows.txt and out.txt. The p1, p3 and p4 binaries were then run directly under ulimit -s, -Ss, -Hs and -v; outputs in p1/direct.txt and p4/direct.txt, and tools/direct_p1.sh reruns p1's (about 7 minutes, no build). Frame sizes are read from prologues with tools/frames.sh; tools/frames-p1.tsv has all 15 316 functions of the p1 binary. CPython-only scripts and their outputs are in cpy/ (outputs.txt).

Not covered: REPORT.md was not written. The Write tool refused it ("Subagents should return findings as text, not write report files"), and I did not route around the refusal. The full account is therefore in the findings above, with the assessment as findings 4 (diagnosis) and 5 (approaches) where the task asked for one; the raw outputs and scripts are under review/q42/ (p1 to p4, cpy, tools).

Not done: aarch64 (every figure is x86-64 with the checkout's GCC); none of approaches A to E was tried, since the runtime may not be rebuilt here, so the slot-reuse estimate rests on slot counts in three functions and p4's helper rows; strict overcommit (vm.overcommit_memory = 2) was read in the kernel's documentation, not run; the cost of a context switch for segments was not measured; the lean build, sanitizer builds and the six targets were not run; the fib timing was taken on a loaded host (load 5 to 6), three runs a side.

Not established: why a property recursing with no other call agrees with the compiled program although CPython's LOAD_ATTR_PROPERTY has no check in the source; why CPython reaches 503 through self[n]; which option was recommended to the author (not on record). Question 38's own follow-through (the count of two) was only seen to be queued.


## q43: Question 43

### F48-q43-1 (RL-1006): "The text is already CPython's" was not measured: 71 of 144 functions had another body and the lock machinery was absent, as the prelude's own header said

*wrong-fact, reported as medium*; where: the question as put (review/q43/question-as-put.txt); docs/DECISIONS.md:1934 and 1951; docs/design.md:810; runtime/prelude/bootstrap.py docstring at 25e2f67

The recommendation rested on "The text is already CPython's" and predicted that after B "D-17's clause narrows to the finder's frames ... a program sees that only in a RecursionError at the limit". At 25e2f67, of CPython's 188 function names 144 were in the preludes: 73 with CPython's body, 71 with another (four of the five on the question's stack row); 44 were absent, 29 of them the lock machinery, as the prelude's docstring said. So RL-950 was foreseeable and belonged in the question; RL-948, RL-949, RL-955, RL-957 are older text differences a diff would have listed (they exist under A too); RL-954 was not foreseeable from frames. B stands; the cost was Questions 47, 48, D-33 and three corrections.

Evidence: review/q43/census/census2.py (AST bodies, docstrings apart) on `git show 25e2f67:runtime/prelude/bootstrap.py` and `bootstrap_external.py` against Lib/importlib/_bootstrap.py and _bootstrap_external.py: `188 qualified names in CPython's two files; 144 also in the preludes: 73 with CPython's body (docstrings apart), 71 with another body; 44 absent`. Differing: _find_and_load, _find_and_load_unlocked, _load_unlocked, _LoaderBasics.exec_module, _find_spec, ... Absent: _ModuleLock.*, _ModuleLockManager.*, _get_module_lock, _WeakValueDictionary.*, _BlockingOnManager.*, ... At head: `152 also in the preludes: 92 with CPython's body, 60 with another body; 36 absent`; census3.py: 7 functions differ with no `bella:` line (_path_isdir, _path_abspath, FileFinder.__init__, spec_from_file_location, _classify_pyc, PathFinder.invalidate_caches, _fix_up_module). Prelude docstring at 25e2f67, lines 16-18: "A program has one thread in phase 1, so a module lock is always this thread's own: taking it waits for nothing and never deadlocks"; `grep -c bella:` there: 46 and 19. DECISIONS.md:1951 ("What the step's entry said wrong") corrects the step's entry; design.md:810 still states the premise without a number. Output kept in review/q43/census/census.txt.

Probe: review/q43/census (census2.py, census3.py, census.txt)

Suggested: Make it a checked fact: let make verify fail when a function paired by tools/bootstrap_frames.py has a body that is not CPython's and no `bella:` line, and put the counts in design.md.

> Verifier: **known** (low). Counts reproduce (25e2f67: 188/144/73 same/71 other/44 absent; head 152/92/60/36), and four of the five stack-row functions differ, but the false premise is already recorded: DECISIONS.md:1951, RL-950 (D-33), RL-948, Q48; design.md:810 is already corrected at head, so the finding's claim that it still states the premise is false. Residue: only about 3 real unmarked differences remain (_fix_up_module extra __cached__ line, _classify_pyc dropped verbose messages, invalidate_caches/RL-957); the finding's 7 includes false positives. Cover: DECISIONS.md:1951 'What the step's entry said wrong ... RL-950 shows otherwise for the locks'; RL-950 'Question 43's answer (B) named only the finder's frames ... the locks run in one thread as they are' (Registered D-33); TODO.md:845 Question 48 (rewritten functions)

### F48-q43-2 (RL-1007): The question said "the tracebacks agree today"; RL-668, open since 2026-11-21, says they do not

*wrong-fact, reported as medium*; where: the question as put (review/q43/question-as-put.txt); docs/DECISIONS.md:1934; docs/reviews/review-log.md:1080; TODO.md:903

The question listed three rows and said of remove_importlib_frames "That is why the tracebacks agree today"; DECISIONS repeats it, and the stack row was called "new, and nothing registers it". CPython trims only at the import statement and __import__. A traceback through importlib.import_module keeps the six entries, and the review log already held that as a confirmed, open difference of the same cause (RL-668), with B's fix queued in TODO. So there were four rows, the fourth the widest: the stderr report of any error under import_module. Option A's cost ("words only") and "C is reasonable ... all three rows are rare" rested on the short list. It argued for B, so the answer stands.

Evidence: review-log.md:1080: `| RL-668 | A31-12 | importlib.import_module of a module that raises shows none of importlib's six frames | Confirmed: 41 traceback entries under CPython and 35 compiled ... | Confirmed | Open, a step of its own`. TODO.md:903-907: "the bootstrap's functions as shown frames, and the removal for the import statement the runtime's to do". DECISIONS.md:1934: "The tracebacks of a failed import agree today, as CPython trims them". CPython 3.15.2, probe p1 row uncaught_byname, stderr: `File ".../importlib/__init__.py", line 88, in import_module`, then `<frozen importlib._bootstrap>` 1389 _gcd_import, 1353 _find_and_load, 1249 _find_and_load_unlocked, 857 _load_unlocked, `<frozen importlib._bootstrap_external>` 751 exec_module, 491 _call_with_frames_removed, then the module; compiled at head the same entries (D-06 apart). `grep -rl "import_module("`: 7 stdlib files (tests, importlib and idlelib apart), 15 in .venv site-packages, targets/vendor/mistune/plugins/__init__.py.

Probe: review/q43/p1, rows uncaught_byname, tb_byname_parent, tb_byname_imp, tb_byname_nested

Suggested: Add a correcting line to DECISIONS (as line 1951 corrects the step's entry): tracebacks through importlib.import_module differed (RL-668) and the step fixed them.

> Verifier: **confirmed** (medium). The question and DECISIONS.md:1934 ('The tracebacks of a failed import agree today, as CPython trims them') were false at 25e2f67 for importlib.import_module (RL-668, open then). Nothing corrects that sentence (DECISIONS:1951 corrects other points). New residue: RL-668 (review-log.md:1080) and TODO.md:903 still say Open although C-8-22 fixed it and head agrees compiled, so the documents contradict each other. B stands. Cover: RL-668 and TODO.md:903 record the difference but not the false sentence in the question and DECISIONS:1934

### F48-q43-3 (RL-980, with the same subject): D-17 does not name the callees CPython enters without a check of the limit; repr(module) shows it in the import system

*words, reported as medium*; where: docs/dialect-spec.md section 11, D-17 (line 232); docs/deviations.toml:112

CPython 3.15.2 pushes the frame of a specialised property read, a Python __getitem__ and a starred call without checking the recursion limit, so from a site's second use such a callee runs as frame limit+1; a compiled program raises RecursionError. D-17's list of where CPython counts otherwise names a site's first calls and the import system's finder, code reading and locks, not this. After Question 43's step the import system shows it: repr(module) reads the property spec.has_location. Only a callee that is the last frame differs, by one; recursions through such frames reach the same level with the same traceback. Older than Question 43 (the words are Question 38's) and not caused by it.

Evidence: Python/bytecodes.c (v3.15.2, in review/q43/cpython-src): macros LOAD_ATTR_PROPERTY (3070-3077), BINARY_OP_SUBSCR_GETITEM (1366-1372) and CALL_EX_PY end in _PUSH_FRAME (4628-4637, `tstate->py_recursion_remaining--;`) without _CHECK_RECURSION_REMAINING (4611), which CALL_PY_EXACT_ARGS has. CPython alone, review/q43/p4/unchecked.py, the callee as frame 61 under a limit of 60: `call first use RecursionError, after 20 uses RecursionError`; property, item, star, starstar: `first use RecursionError, after 20 uses runs`. Both sides, probe p4: `property, the site's first read` SAME (RecursionError); `property, the site read before`: CPython `read`, compiled `RecursionError`; `item, the site read before`: the same; `repr of a module, one read before`: CPython `read`, compiled `RecursionError`. Probe p5 `leaves star` and `leaves starstar`: CPython `runs`, compiled `RecursionError`; its ten `levels` rows (plain, star, kw, property, item under 60 and 61, with the traceback's length and end) SAME. Probe p3 row warm: `repr of a module` 65 against 64, `spec.parent` 67 against 66, `property` 67 against 66; call, method, from-import, import_module SAME.

Probe: review/q43/p4 rows `limit ...`; review/q43/p5 rows `leaves ...` and `levels ...`; review/q43/p3 row warm

Suggested: The author's: D-17 names it, or the runtime lets a property getter, a Python __getitem__ and a starred call's callee in at limit+1 (agreeing from a site's second use, as the __init__ count agrees from the third).

### F48-q43-4 (RL-1008): The run-time cost was put as "only when the program imports a module for the first time": false, and not measured

*cost, reported as low*; where: the question as put (review/q43/question-as-put.txt); docs/DECISIONS.md:1944

The question: "At run time: a few instructions per frame, and only when the program imports a module for the first time." The import system's Python functions also run, each with a linked frame since the step, at every execution of `from package import name` (_handle_fromlist), at every importlib.import_module call for a module already imported (four frames) and at every repr() of a module. The step's entry words it better but omits import_module and repr and gives no figure, where Questions 30 and 36 were answered with measured costs. The frames are CPython's own design and I claim no regression: there is no figure from before the step to compare with.

Evidence: Python/import.c:4134-4141: `if (has_path) { final_mod = PyObject_CallMethodObjArgs(IMPORTLIB(interp), &_Py_ID(_handle_fromlist), mod, fromlist, IMPORT_FUNC(interp), NULL);`. Probe p1 row stack_getattr, both sides, the second `from pkgg import lazyname as again`: `[('prog.py', 405, '<module>'), ('prog.py', 173, 'stack_getattr'), ('<frozen importlib._bootstrap>', 1414, '_handle_fromlist'), ('__init__.py', 5, '__getattr__')]`. Probe p3 row warm, both sides: `call 66`, `from-import 66`, `import_module 63`. Probe p3 row timing (the built binary against CPython, four runs, ns each): a from-import of a package's name 2871-3009 against 448-479; import_module of a loaded module 8798-8920 against 587-654; repr(module) 13854-14551 against 950-1326; a plain call 332-381 against 39-41 (library units are built -O0, pipeline/build.py:145). DECISIONS.md:1944: "which run once for each module a program imports and for a from-import of a package's names".

Probe: review/q43/p1 row stack_getattr; review/q43/p3 rows warm and timing

Suggested: Reword the step's entry (every from-import of a package's names, every import_module call, every module repr) and take one figure against 25e2f67 when costs are next measured.

### F48-q43-5 (RL-1009): RL-668 was fixed by the step and is still open in the log, in TODO and in a test that skips its row

*follow-through, reported as low*; where: docs/reviews/review-log.md:1080; TODO.md:903; pipeline/tests/test_subclass_data.py:46-47

The step changed only RL-933 in the review log. RL-668 (importlib's frames in a traceback through importlib.import_module) still reads "Open, a step of its own", TODO still lists it under "Open from review A31", and test_the_reduced_programs_of_review_a31 still skips selection 11 as open. The reviewer's program agrees now. The row cannot simply be switched on: it imports `badmodule`, which the test never writes, so under CPython it would end with an uncaught ModuleNotFoundError.

Evidence: `git show 0c25f5e -- docs/reviews/review-log.md` changes the RL-933 row only. review-log.md:1080: `| RL-668 | ... | Confirmed | Open, a step of its own: ...`. TODO.md:903: `* **Open from review A31** (2026-11-21, night): importlib's frames in a traceback (RL-668).` test_subclass_data.py:46-47: `# the report's reduced programs: selection 11 is RL-668 (importlib's frames in a traceback), which is open` and `EXAMPLES_OPEN = {11}`; in the test: `if row in EXAMPLES_OPEN: continue`. Probe p2 row a31_row_11 (selection 11's text with a badmodule.py that raises ZeroDivisionError beside it), SAME on both sides: `10 ['a31_row_11', 'go', 'import_module', '_gcd_import', '_find_and_load', '_find_and_load_unlocked', '_load_unlocked', 'exec_module', '_call_with_frames_removed', '<module>']`. `grep -rn badmodule pipeline/tests` finds subclass_data_examples.txt:98 only.

Probe: review/q43/p2 row a31_row_11

Suggested: Close RL-668 as fixed (C-8-22's by-name rows hold it), trim TODO.md:903, and write badmodule.py in the test and empty EXAMPLES_OPEN, or point its comment to C-8-22.

> Verifier: **confirmed** (low). RL-668 was fixed by Question 43's step (0c25f5e) but still reads open: the step changed only the RL-933 row of review-log.md. RL-668 stays 'Open, a step of its own' (review-log.md:1080), TODO.md:903 still lists it under 'Open from review A31', and test_subclass_data.py:46-47 keeps EXAMPLES_OPEN = {11}, skipped at line 98. The row cannot be switched on as is: the test folder holds only prog.py, and under CPython row 11 ends with an uncaught ModuleNotFoundError for 'badmodule' (exit 1), while with badmodule.py beside it CPython exits 0 with the 10-entry stack. The probe's SAME is confirmed in re ...

### F48-q43-6 (RL-1010): C-8-22 holds one half of the trimming rule

*test, reported as low*; where: conformance/cases/C-8-22_the_import_systems_frames.py and conformance/cases/importframes/

The decision asked for "each trimming rule of a traceback" and the case's docstring states the rule (all entries for an ImportError, otherwise a stretch that ends in _call_with_frames_removed). Its rows only ever remove: value, import error, missing; the by-name rows have no trimming. No row leaves an import statement or __import__ with an import-system entry that must stay, so a runtime that dropped every such entry at __import__'s exit would pass C-8-22, and no other test holds it. The implementation is right on my three rows.

Evidence: Probe p2, all SAME on both sides: tb_getattr_raises `[('prog.py', 14, 'tb_getattr_raises'), ('<frozen importlib._bootstrap>', 1414, '_handle_fromlist'), ('__init__.py', 3, '__getattr__')]`; tb_fromlist_nonstr `[('prog.py', 25, 'tb_fromlist_nonstr'), ('<frozen importlib._bootstrap>', 1408, '_handle_fromlist')]` with "Item in ``from list'' must be str, not int"; tb_all_nonstr `[('prog.py', 38, 'tb_all_nonstr'), ('starbad.py', 1, '<module>'), ('<frozen importlib._bootstrap>', 1412, '_handle_fromlist'), ('<frozen importlib._bootstrap>', 1408, '_handle_fromlist')]`. C-8-22's rows: plain, nested, parent, fromlist, by_name, deep, warns, value, import_error, missing, by_name_missing, by_name_value. `grep -rn _handle_fromlist pipeline/tests/*.py conformance/cases/*.py`: a list of names (test_review_2026_11_10.py:953) and C-8-22's header only.

Probe: review/q43/p2 rows tb_getattr_raises, tb_fromlist_nonstr, tb_all_nonstr

Suggested: Add three rows to C-8-22: a module __getattr__ raising ValueError under a from-import, a from-list item that is no str, an __all__ item that is no str.

> Verifier: **confirmed** (low). C-8-22 holds only the removing half of the trimming rule. Its twelve rows (plain, nested, parent, fromlist, by_name, deep, warns, value, import_error, missing, by_name_missing, by_name_value) are the case's for-loop tuple, and no row covers a module __getattr__ raising under a from-import, a from-list item that is no str, or an __all__ item that is no str; _handle_fromlist appears in pipeline/tests only as a name in a list (test_review_2026_11_10.py:953) and in the case header (C-8-22 line 5). The three probe rows print the quoted outputs under CPython and the compiled binary in the same run ( ...

### F48-q43-7 (RL-1059, with the same subject): The prelude's _fix_up_module sets __cached__, which CPython 3.15.2's text does not

*defect, reported as low*; where: runtime/prelude/bootstrap_external.py:876 (from cea5c1e, 2026-11-09)

A line of the prelude is neither the pin's nor marked `bella:`: `ns['__cached__'] = cpathname` in _fix_up_module. CPython 3.15.2's function sets __spec__, __loader__ and __file__ only, and neither of its two files contains `__cached__`. Nothing in the runtime calls the function, so only a program that calls this private function sees it. It is the one program-visible instance I found of the class in Finding 1: an unmarked line that is not CPython's, which the frames table then maps to the line before it.

Evidence: Probe p4 row fixup (`importlib._bootstrap_external._fix_up_module(ns, "made", "/nowhere/made.py")`, then `print(sorted(ns))`): CPython `['__file__', '__loader__', '__spec__']`, compiled `['__cached__', '__file__', '__loader__', '__spec__']`. `grep -n __cached__` over Lib/importlib/_bootstrap.py and _bootstrap_external.py of 3.15.2: nothing (lines 1555-1557 of the latter set the three names). runtime/prelude/bootstrap_external.py:876: `        ns['__cached__'] = cpathname`. `git log -S"ns['__cached__'] = cpathname" -- runtime/prelude/bootstrap_external.py`: cea5c1e, 2026-11-09. `grep -n _fix_up_module runtime/src/*.cpp`: nothing.

Probe: review/q43/p4 row fixup

Suggested: Delete the line; it is not 3.15.2's.

Minor, one line each, not verified:

- RL-950's row says _find_and_load "takes _ModuleLockManager(name) (_bootstrap.py:1339)"; 3.15.2's line 1339 is `lock = _get_module_lock(name)` and _ModuleLockManager is used at 821 and 886 only. The effect the row names is right.
- DECISIONS.md:1934 says _load_unlocked's local `module` keeps the failed module; exec_module's parameter `module` (_bootstrap_external.py:746) holds it too on the same f_back chain. No consequence.
- CPython's _load_unlocked calls _verbose_message after the module's body (_bootstrap.py:870), a frame the prelude never enters and D-17's "before the module's body" does not cover; I found no way for a program to see it (the body's own frames are deeper).
- Section 11's paragraph on D-19 credits "Questions 36 and 43" with its end; DECISIONS has Question 44's answer end it.
- Question 38 wrote "its import system's frames" into D-17 (v0.34, 2026-11-24) a day before Question 43, though RL-668's TODO item of 2026-11-21 already queued counting them; v0.42 narrowed it. Churn, no contradiction.
- The question called option C reasonable "since all three rows are rare in real programs" with no count of real use; the evidence rule was set later the same day (Question 46).
- census3.py prints eight functions without a `bella:` line; one (BuiltinImporter.exec_module) has its note on a comment after the docstring, outside the function's span, so seven.

Covered: Verdict: the answer B is sound by the project's own rules, the step does what B says, and the record of the recommendation (B) and of the author's words ("q43: B please") matches the transcript. What is wrong is in the question as put (Findings 1, 2, 4); none of it would have turned B into another answer.

Read: the question as put, which is not in the repository (taken from the session's own transcript and saved as review/q43/question-as-put.txt; put 2026-11-25T01:50Z, answered 11:17Z); DECISIONS.md:1934, 1944, 1951; commits 7bb3e4b and 0c25f5e (stat; the TODO, review-log and baseline diffs); TODO's items for Questions 43, 47, 48 and RL-954/955; design.md:810; the spec's Imports row, E-02 to E-06, sections 8, 9, 11 (D-17, D-25, D-33, the D-19 paragraph), v0.34 to v0.42; deviations.toml D-17 and D-33; review-log RL-632, RL-639, RL-668, RL-933 to RL-957; C-8-22 with its modules and expectation, C-9-14, test_subclass_data.py.

Facts measured again under CPython 3.15.2, all holding: the failed module's weak reference dies only when the kept exception goes (by statement, by name, __import__, importlib.__import__, a from-import, a submodule, a failing parent, nested, lazy); the five entries at 1353, 1249, 857, 751, 491; the depth 51 (my row has one frame more: 50); _bootstrap.py:843, 857, 860; the prelude's _load_unlocked at 353 and cpp.py:326 at 25e2f67. Read in CPython's source (fetched into review/q43/cpython-src/): take_ownership (Python/frame.c:48-90), remove_importlib_frames at Python/import.c:3694 and its three callers, is_internal_filename (Python/_warnings.c:934), Python/bytecodes.c.

Compiled at head: 6 builds (p3 twice, since my own probe held a [P2+] __getattribute__ class), 91 rows in review/q43/p1 to p5 (prog.py, rows.txt, result.txt each): the stack through every import route (plain, a parent, three levels, relative, from-import, star import, by name, __import__, importlib.__import__, lazy, a module __getattr__ asked by _handle_fromlist and by _find_and_load_unlocked); depths through each route and the depth named in setrecursionlimit's message; tracebacks and both halves of the trimming rule; errors raised in _sanity_check, _resolve_name, _calc___package__ and _find_and_load_unlocked; warnings' stacklevel 1 to 9 and skip_file_prefixes; a DeprecationWarning from a package's __getattr__; logging's stacklevel and stack_info; unittest's report; the failed module's spec and loader; the importer's locals kept through the import frames by a kept traceback. All agree but Findings 3 and 7; every other difference is D-06, D-12, an E-02 stop (sys._getframe) or my probe's own (find_spec of a package the closed world does not hold).

Options: I found no better option that was not put. An exclusion does not fit (a program does not choose to see these frames, and the report of an uncaught exception shows them); keeping the module alive without frames would approximate; the wider cut with the locks was put the same day as Question 47 once known. Words: no spec row came from Question 43 itself; section 9's bullet (Question 44) holds on every lifetime row; deviations.toml D-17 agrees with the spec's row; D-25 still excepts importlib's code from signal looks (pipeline/backend/cpp.py:715-720), consistent with the step.

Not covered: REPORT.md was not written: this session's Write tool refused it ("Subagents should return findings as text, not write report files") and I did not work around that. The account is this result; the evidence is in review/q43 (question-as-put.txt, census/census.txt, cpython-src/, p1 to p5 with result.txt, p4/unchecked.py and p4/coldprop.py for CPython alone).

Not covered: the implementation's code line by line (tools/bootstrap_frames.py, mark_frames, imports.cpp's trimming, the table's entries), which is another reviewer's; I tested its behaviour on about 25 distinct lines of CPython's two files and found none wrong. Questions 47 and 48 and D-33's words and measurements (the lock rows, the 12 calls, 68 against 72, the 27 code objects). The compiled side of the question's three rows at 25e2f67: no build of an old commit is allowed, so "compiled: 56" and "module died already in the except clause" are taken from the record, with which RL-668 and the step's diff are consistent. The cost of the linked frames against the commit before the step (Finding 4 has today's figures only). eval1 and eval2 on C-8-22 (it is in the compiled baseline only). A signal arriving inside the import system's functions (D-25), threads, anything [P2+]. Whether Question 38's reviewer reports Finding 3 as well: it belongs to D-17 as much as to this question.


## q44: Question 44

### F48-q44-1 (RL-1011): D-19 ended with a difference still visible: at the exit a weak reference to a built-in module is never cleared

*wrong-fact, reported as high*; where: docs/DECISIONS.md:1936 (Question 44, commit ad18417); docs/dialect-spec.md:196, :247, D-07 at :195 and :222; runtime/include/bella/runtime.hpp:212; docs/deviations.toml (D-19's deleted note)

The entry says nothing of D-19 is left that a program can see, since a runtime module in sys.modules 'lives on both sides'. At the exit CPython itself takes every module out of sys.modules and frees a built-in module nothing else holds, so the callback of a weak reference that outlives it (held by sys, as C-9-13's `weak` row holds one) is called; compiled, the runtime's own modules are immortal and it never is. D-07 promises that which objects are finalised is CPython's, and D-19's deleted note ('a weak reference to a module never dies') was the only registration. Options A, B and C differ only in when the words change; keeping D-19 narrowed to this (Question 36's own answer) was not put.

Evidence: review/q44/p4, one build, 132 modules, one a row; sys.__dict__ holds weakref.ref(module, callback), the callback writes with os.write. `.venv/bin/python r48_both.py review/q44/p4 --rows review/q44/p4/rows.txt`
ROW ['math']: DIFF. CPython, status 0: `the end` / `  died: math!`. Compiled, status 0: `the end`.
The same for 42 of 53 built-in modules (atexit binascii cmath gc grp pwd time unicodedata zlib _bisect _blake2 _collections _contextvars _csv _functools _heapq _json _locale _md5 _opcode _operator _random _sha1 _sha2 _sha3 _sre _stat _statistics _string _struct _typing math _hmac _frozen_importlib_external _imp _signal _warnings _weakref _tokenize _suggestions _ast _types); 10 are called on neither side; marshal stops by name. All 79 Python modules agree (73 called on both sides). What a built-in module's namespace holds is finalised on both (p2 x_attr, 16 SAME).
CPython: Python/pylifecycle.c finalize_remove_modules; Objects/moduleobject.c module_dealloc (FT_CLEAR_WEAKREFS first). runtime/include/bella/runtime.hpp:212 'The runtime's own ... are immortal'. Use: no weak reference to a module by text patterns in the stdlib (694 files) or the environment (993).

Probe: review/q44/p4, row `math` and 41 more (both.txt); first seen in review/q44/p1, rows `x_weak <module>`

Suggested: Ask the author: D-19 kept narrowed to the runtime's own modules (or a D-07 clause, or an exclusion on the evidence), or their weak references cleared at the exit's step where CPython frees them. Add a C-9-13 row either way; reword spec lines 196 and 247.

> Verifier: **confirmed** (high). At the exit CPython frees a built-in module nothing else holds and calls the callback of a weak reference that outlives it; compiled, the runtime's own modules are immortal and it never is. Q44's 'nothing of D-19 is left that a program can see' and spec :196/:247 are false for this; D-19's deleted note ('a weak reference to a module never dies') was the only registration; D-07 promises which objects are finalised is CPython's. Numbers: 42 built-in modules differ (marshal stops by name, not a defect), 10 built-in are called on neither side, all 79 Python modules agree (73 called on both). Narro ... Cover: none. DECISIONS.md:1791 ('state of a C module ... No case reaches it') concerns state, not the module's weak references; old D-19 note was deleted by Q44 (DECISIONS.md:1936).

### F48-q44-2 (RL-1012): A kept deepest traceback entry of a failed import releases the module's namespace last (the entry's own hold, from 25e2f67)

*defect, reported as high*; where: runtime/src/core.cpp:376-382; runtime/include/bella/runtime.hpp:300; refmodel/objects.py:1344-1345; docs/DECISIONS.md:1921; docs/dialect-spec.md:196; commit 25e2f67 (Question 36's step)

Section 9 now says a module whose body raised goes, with what only it held, exactly when CPython's would. When the entry of the failing module's own frame is the last thing holding the chain (a traceback walked to its deepest entry and kept), CPython finalises the module's namespace right after the module, before the frames further out; compiled finalises it after all of them. The compiled traceback entry holds the namespace itself and lets go of it after tb_frame (added by 25e2f67); CPython's entry holds only tb_next and tb_frame. No cycle, no collection, not the exit: D-04 and D-07 do not cover it. The reach is narrow; the fix costs nothing at run time.

Evidence: review/q44/p2, ROW ['tbinner','bad_plain'] (a function returns the deepest entry of the failed import's traceback; then `del tb`):
CPython: the entry dropped ['bad_plain!', 'bad_plain.held', 'importer.local']
compiled: the entry dropped ['bad_plain!', 'importer.local', 'bad_plain.held']
ROW ['tbinner','bad_outer']: CPython ['bad_plain!', 'bad_plain.held', 'bad_outer!', 'bad_outer.held', 'importer.local']; compiled ['bad_plain!', 'bad_outer!', 'bad_outer.held', 'importer.local', 'bad_plain.held'].
10 rows differ (p2 tbinner x4, tbexc x3; p1 h_tbwalk x bad_outer x3); controls agree (a namespace in a cycle, a live module, every row that lets the entries go from the head).
runtime/src/core.cpp:377-380: `// tb_dealloc: the deeper entries, then the frame (its function's globals last)` `t->next = Ref{}; t->frame_obj = Ref{}; t->module.reset();`
CPython Python/traceback.c tb_dealloc: `Py_XDECREF(tb->tb_next); Py_XDECREF(tb->tb_frame);` and nothing else; Objects/frameobject.c frame_dealloc clears f_funcobj before f_back.
refmodel/objects.py:1344: a RefFunction 'stands for a frame object and a traceback entry too, which hold their globals the same way'; DECISIONS.md:1921 says the same.

Probe: review/q44/p2, rows `tbinner bad_plain`, `tbinner bad_outer`, `tbinner pkgok.badsub`, `tbinner bad_order`, `tbexc ...`; review/q44/p1, rows `h_tbwalk <form> bad_outer`

Suggested: Fix: the entry lets go of its own hold before tb_frame, or takes none where it has a frame object. Correct the model's sentence and DECISIONS 1921. Add kept-deepest-entry rows to C-9-14, whose rows only release the exception at the end of the except clause.

> Verifier: **confirmed** (high). A traceback entry made by 25e2f67 holds its module's namespace itself (GlobalsRef module) and lets go of it after tb_frame, where CPython's tb_dealloc releases only tb_next and tb_frame, the frame's f_funcobj (globals) going before f_back. When the deepest entry of a failed import's traceback is the last holder, the namespace and what only it held are finalised after the frames further out (and after the next module), not right after the module. DECISIONS 1921 and the model's docstring are inexact for the entry. Narrow reach; fix not tested (read-only checkout). Cover: none. D-04 (cycles) and D-07 (exit) do not apply; C-9-14 has no kept-entry row; no review-log/TODO entry.

### F48-q44-3 (RL-1013): importlib.util.module_from_spec of a built-in module's spec is the imported module itself, where CPython makes a second one that dies

*defect, reported as medium*; where: runtime/src/imports.cpp:1424; docs/DECISIONS.md:1936 (the premise); docs/dialect-spec.md:78 (E-04); conformance/cases/C-7-52_importlib.py

The entry treats a runtime module as only ever the object in sys.modules, which a program cannot take out. Under CPython `importlib.util.module_from_spec(importlib.util.find_spec('math'))` makes a second module object, never in sys.modules, which goes when the program lets go of it. Compiled it is the imported module itself: `second is first`, a name set on it shows on `math`, and a weak reference to it never dies (`_imp.create_builtin: one module per name`). A Python module's spec agrees in full. E-04 names finders and loaders from importlib.abc, reload and writes to sys.modules, not this, and C-7-52 holds module_from_spec and find_spec as [P1].

Evidence: review/q44/p5, ROW ['math','create']:
CPython: `the same object: False` ... `a name set on the second shows on the first: False` / `the second let go of []` / `collected ['second math!']` / `alive ['spare']`
compiled: `the same object: True` ... `a name set on the second shows on the first: True` / `collected []` / `alive ['second math', 'spare']`
20 rows differ: math time errno itertools _json posix gc zlib binascii _struct, created, and created then run with spec.loader.exec_module. sys and builtins agree (one object under CPython too); json and the program's own module agree (a second object, its body run again, its death).
runtime/src/imports.cpp:1424 `Ref i_bella_create_builtin(Obj, Args a) {        // _imp.create_builtin: one module per name`. CPython Python/import.c create_builtin runs the module's init again unless it is a cached single-phase module, sys or builtins.
Use: module_from_spec's call sites in the stdlib without tests (sysconfig, profiling) and the environment (pytest, two) all take file specs.

Probe: review/q44/p5, rows `<module> create` and `<module> exec` for math, time, errno, itertools, _json, posix, gc, zlib, binascii, _struct

Suggested: Ask the author with finding 1: an exclusion (E-04 names a second object of a built-in module made from its spec; the evidence shows none in use) or a new module per call. Until then a stop by name, since a write to the 'copy' now changes the real module.

> Verifier: **confirmed** (medium). importlib.util.module_from_spec(find_spec(name)) for a built-in module other than sys and builtins gives under CPython a new module object (not in sys.modules, dies when let go); compiled it is the imported module itself (_imp.create_builtin 'one module per name'), so a write to the 'copy' changes the real module and no weak reference to it dies. CPython 3.15.2 returns the same object only for builtins and sys (checked over all 101 builtin module names), which is what compiled does. E-04 names customisation of the import system, not this; unregistered; a stop, a new module per call or an exclu ... Cover: none. E-04 (spec :78) lists finders/loaders from importlib.abc, reload, writes to sys.modules; C-7-52 holds module_from_spec as [P1] with file specs only; grep of review-log, TODO, DECISIONS, deviations finds nothing on module_from_spec of a built-in spec.

### F48-q44-4 (RL-1014): "The program cannot see them" is false for compiled code: a weak reference to f.__code__ outlives the function (and a built-in module's function its deletion)

*wrong-fact, reported as medium*; where: docs/DECISIONS.md:1936; docs/dialect-spec.md:179 (section 8), :196 (section 9), :76 (E-02)

The entry keeps D-19's last claim as unobservable: 'Compiled code and class layouts as immortal metadata ... the program cannot see them'; section 8 still says 'immortal metadata invisible to the program'. Since v0.14 `f.__code__` is a [P1] object and takes weak references: under CPython the code object of an imported module's function dies with its last holder, compiled it never does. E-02 speaks of a code object's names, equality and identity, not its lifetime; D-19's deleted note was the only registration. Likewise `del math.sqrt`: the function dies under CPython and lives compiled (sys.getsizeof the other way). Everything a program's module makes does agree (24 kinds).

Evidence: review/q44/p3, ROW ['code','imported'] (`r = weakref.ref(spare2.value.__code__)`; `del spare2.value`): CPython `function deleted: dead`, compiled `function deleted: alive`, alive still after gc.collect(). Also code nested, lambda, method (4 rows); ['code','main'] agrees (alive on both).
review/q44/p2, ROW ['bf','math','sqrt'] (`r = weakref.ref(math.sqrt)`; `del math.sqrt`): CPython `dead True`, compiled `dead False`; also time.sleep, gc.get_stats. ROW ['bf','sys','getsizeof']: CPython `dead False`, compiled `dead True`.
p3 `def` rows, 24 kinds deleted from an imported module and watched by weak references and finalisers (function with defaults, closure, lambda, lru_cache, partial; class plain, __slots__, metaclass, subclass and base, exception, with an instance, dataclass, Enum, NamedTuple, namedtuple, TypedDict, Protocol, ABC, descriptors): all SAME.
DECISIONS.md:1936; dialect-spec.md:179, :196 ('and so is everything created while a module initialises'). Use: no weak reference to a code object by text patterns in the stdlib or the environment.

Probe: review/q44/p3, rows `code imported`, `code nested`, `code lambda`, `code method`; review/q44/p2, rows `bf math sqrt`, `bf time sleep`, `bf gc get_stats`, `bf sys getsizeof`

Suggested: Reword the entry and section 8 to what is seen (a code object does not die with its function) and have the author register or exclude it; E-02's row is the natural place. Nothing to build if excluded.

> Verifier: **confirmed** (medium). Code objects (f.__code__, [P1] since v0.14/C-3-46) and function objects of built-in modules do not die with their holders compiled. A weak reference to the code of a deleted imported function stays alive (CPython dead), and so does one to `math.sqrt` after `del math.sqrt`. `sys.getsizeof` goes the other way (dead compiled, alive under CPython). Spec section 8 ('immortal metadata invisible to the program') and DECISIONS.md:1936 ('the program cannot see them') are therefore false. No E-nn, D-nn, review-log RL, TODO or DECISIONS entry covers it. D-19 was the only registration and was removed in a ...

Minor, one line each, not verified:

- docs/dialect-spec.md:247 says D-19 'ended on 2026-11-25 (the author's decisions, Questions 36 and 43)'; the decision that ended it is Question 44 (DECISIONS.md:1936), Question 36 was answered on 2026-11-24, and Question 43's entry says the words 'follow as Question 44'.
- docs/design.md:386 ('a module-level def is one immortal FunctionObject') and :591 ('functions, classes and modules created at initialisation are immortal') still stand in the living design text, and docs/drafts/object.hpp.draft:30 and :124 still name D-19; all older than ad18417, which changed design.md:167 only.
- `import decimal` compiled leaves `sys.modules['_pydecimal'] is decimal` true where CPython has no `_pydecimal` entry (review/q44/p2, row `decimal`): decimal.py:109's own `sys.modules[__name__] = _pydecimal`, the one write to sys.modules of the standard library that a compiled program reaches; D-20 lists nothing for decimal. Not D-19's.
- The entry says a dropped ModuleType 'never died' before 25e2f67, where Question 36's entry measured 'compiled at the exit'; not measured again.
- refmodel/objects.py:1344-1345 states that a traceback entry holds its globals as a function does; CPython's entry holds tb_next and tb_frame only (part of finding 2, listed here because the model comes before the header).

Covered: Five builds of six, 494 rows, each run under CPython 3.15.2 and compiled (review/q44/p1..p5, full output in each both.txt). 
FACTS of the entry, each measured again: D-19's old summary, note and premise read in `git show ad18417`. A `types.ModuleType` dies as CPython's (16 rows: dropped, held, namespace kept, self-reference, a pair, 1000 in a loop, `__init__` again, `__new__` alone, proxy, finalize, weak containers, in and out of sys.modules, a module from a ModuleSpec): SAME; a subclass stops by name. A failed import: 130 rows over 13 failing modules (plain, raising from a function, holding itself, ImportError, SystemExit, a chained exception, an uncaught nested failure, a kept generator, finalize on itself, raising in a class body, keeping its own exception, a failing package with a submodule, a failing submodule) x four import forms x nine ways of holding the exception, plus a lazy import, a circular import, the order of a namespace's finalisers, a kept generator and a kept function as last holders: all SAME except finding 2. The exit with a failed import's exception or function kept, and uncaught: SAME on standard output. The recordings of C-9-05, C-3-82 and C-9-14 reproduce under CPython and ad18417 changed only their `spec` lines; all three are in conformance/evalc-baseline.txt. 'design.md already says it': design.md:188. D-22's precedent: dialect-spec.md:251.
CPython's source read (fetched from the v3.15.2 tag into review/q44/cpython-src, read only): moduleobject.c (module_dealloc, module_traverse, module_clear), pylifecycle.c (finalize_modules), frameobject.c (frame_dealloc, frame_tp_clear), frame.c (take_ownership), traceback.c and cpython/traceback.h, import.c (create_builtin).
The runtime's own modules: weak references mid-run (19 modules, SAME); the exit sweep of 132 modules (finding 1); what a built-in module's namespace or a registered csv dialect holds at the exit (SAME); a second module object from a spec (finding 3).
What a module makes while it initialises: 24 kinds, all SAME; code objects and built-in functions (finding 4).
OPTIONS and record: given what the entry believed, A was the consistent choice, and ending D-19 hours before Question 43's step is recorded openly as a defect being fixed; the options were incomplete because of the false premise (finding 1). The author's words are quoted in the entry; I could not check them against the conversation.
WORDS: section 9's bullet clause by clause (false in findings 1, 2 and 4; true for defaults and closure at `del f`, for what runs in a module holding the namespace and not the module, and for every other row), section 11's paragraph, v0.39's line, deviations.toml (D-19 gone, agrees with the spec), emitter.md, design.md:167.
FOLLOW-THROUGH: the runtime no longer names D-19, the model's two mentions are in the past tense, TODO's item is closed consistently. No case or test holds a module's weak reference at the exit, a module made from a built-in's spec, or a kept deepest traceback entry.
CONSISTENCY: Question 39 (D-07) and Question 36 ('D-19 narrowed') against finding 1; the `gc.collect()` count of a collected import chain (27 against 20, the lock objects D-33 leaves out) is covered by the decision of 2026-11-14 that gc's numbers are the runtime's own (D-04), so it is not a finding; E-02, E-04, E-06 read against each difference.

Not covered: REPORT.md was not written: the Write tool refused it for a subagent ('return findings as text, not write report files'), and I did not go around the refusal; the full account is this output, and every row's two outputs are in review/q44/p1 to p5 (prog.py, rows.txt, both.txt). 
Not examined: the eval1 and eval2 legs, a `lean` build, anything through make or pytest; C-9-14 itself was not run compiled through the harness (my rows repeat its shapes). The builds before 25e2f67 and before 0c25f5e were not rebuilt, so what the entries say compiled did then (a dropped ModuleType 'never died', a failed import's module dying when the import ended) is taken from the entries. How the question was worded to the author in the conversation: only DECISIONS, TODO and the commit were read. `ModuleType` subclasses, `traceback.tb_frame`, `gc.is_tracked` (queued, TODO H3), `generator.gi_code` and `import marshal` (queued, Question 33) each stop by name and were not followed further. Use counts beyond CPython's standard library and the development environment (PyPI, GitHub) for weak references to modules or code objects and for module_from_spec with a built-in module's spec: the counts given are by text patterns only and can miss indirect uses. Threads, signals, other platforms. One build was left unused.


## q45: Question 45

### F48-q45-1 (RL-1015): E-05 names one way to a class's dict; CPython has more, the runtime follows three of them, and a write there differs silently

*wrong-fact, reported as high*; where: docs/DECISIONS.md:1938 and commit 5ec495e's message ("the other way to that object"); docs/dialect-spec.md:79, 369; runtime/src/types.cpp:3434, 2337; runtime/src/gc.cpp:201; docs/reviews/review-log.md:901 (RL-489), TODO.md:962

The entry and the commit call `gc.get_referents` "the other way to that object", and E-05's clause names only the proxy's `|`. Under CPython 3.15.2 a program is also handed the class's own dict by `object.__getstate__(C)`, by `gc.garbage` under DEBUG_SAVEALL, by `C.__dict__ == types.MappingProxyType(own)` (a gap in gh-152405's guard) and by `C.__annotate__.__closure__[0].cell_contents`. The runtime hands its view out on the first three on purpose, and a write there differs compiled, silently, with nothing covering it; the fourth is RL-489, open, whose fix opens it. E-05's reason holds for every way alike, so the words should name the write, not one way.

Evidence: CPython alone (review/q45/explore/routes.py, cell.py): each way returns the object gc.get_referents(C.__dict__) returns. v3.15.2 source: typeobject.c:8139, 7995 (object.__getstate__ -> PyObject_GenericGetDict), 4854 (PyCell_Set(cell, dict)); descrobject.c:1242-1258 (an exact mappingproxy passes the guard).
`.venv/bin/python r48_both.py review/q45/p1 --rows review/q45/p1/rows.txt`, rows route:getstate, route:type_getstate, saveall, route:eq_own_proxy, route:ne_own_proxy: DIFF, status 0 both sides:
 CPython   handed: ['dict'] / after d['y'] = 42: 42 True 42 42
 compiled  handed: ['dict'] / after d['y'] = 42: 42 True None None
(saveall: "in gc.garbage: 1 class, 1 dict of it" on both, then the same second line.)
review/q45/p3, row getstate_seen (no proxy operator in the program; hasattr, in dir, in vars, an instance; del; in vars):
 CPython   True True True 42 / deleted / False
 compiled  False False True None / AttributeError / True
Rows cell, cell_write: CPython `dict True 1`, `written / True 42`; compiled `mappingproxy False 1`, `TypeError / False None` (RL-489, review-log.md:901, TODO.md:962).
Runtime: types.cpp:3434 "PyObject_GenericGetDict of a type: its own dict, which is never empty" (25461ef, 2026-11-22); gc.cpp:201 (RL-937, 2026-11-24); types.cpp:2337.

Probe: review/q45/p1 rows route:getstate, route:type_getstate, saveall, route:eq_own_proxy, route:ne_own_proxy; review/q45/p3 rows getstate_seen, cell, cell_write

Suggested: Ask the author to word E-05 by the write (a class's own dict, however the program came by it), the ways as examples; add a dated correction of "the other way" to the entry; note on RL-489's TODO item that its fix opens the cell's way.

> Verifier: **confirmed** (medium). Confirmed, at medium, not high. E-05 (v0.40) excludes writing a class's own dict only "where a reflected operator of its mapping proxy hands it out", and DECISIONS.md:1938 and commit 5ec495e call gc.get_referents "the other way to that object". CPython 3.15.2 also hands that dict out by object.__getstate__(C), by C.__dict__ ==/!= MappingProxyType(own mapping), and by gc.garbage under DEBUG_SAVEALL. The runtime follows all three on purpose; a write there differs silently. The decision stands (its type-cache reason holds for each way); the words are incomplete. The cell way is RL-489, known. Cover: Partial only. E-05 (dialect-spec.md:79): "writing a class's own dict where a reflected operator of its mapping proxy hands it out (`mappingproxy.__or__`)" with the reason "what CPython's class finds after such a write depends on its type cache": the reason fits every way, the clause names one. RL-489 (review-log.md:901): "`__classdictcell__` held a mappingproxy | Confirmed ... | Open | Not in the round's commit; TODO lists it" and TODO.md:962 cover the cell's way as known. Nothing records object.__getstate__(C), the comparison with another proxy, or gc.garbage under DEBUG_SAVEALL.

> Verifier: **confirmed** (medium). Confirmed as a wording finding; I would defend medium, not high. DECISIONS.md:1938 and commit 5ec495e call gc.get_referents "the other way" to a class's own dict. CPython 3.15.2 also hands it out by object.__getstate__(C), gc.garbage under DEBUG_SAVEALL, a comparison with an exact mappingproxy of the program's own, and the annotation cell. A write on the first three differs compiled, cold only, for E-05's own reason. E-05's words can be read to cover the comparison, not the first two; the cell is RL-489, open. Question 45's answer A does not rest on the aside and stands; the remedy is E-05 worded by the write. Cover: Partial only. E-05 (docs/dialect-spec.md:79): "writing a class's own dict where a reflected operator of its mapping proxy hands it out (`mappingproxy.__or__`)" covers the comparison with an own proxy on a fair reading, not object.__getstate__(C) or gc.garbage. review-log.md:901: "RL-489 ... `__classdictcell__` held a mappingproxy | Confirmed ... | Open" and TODO.md:962 record the cell. review-log.md:1356 (RL-944) records only the reflected `|` and "`gc.get_referents(C.__dict__)` reaches the same object, under E-05". Nothing in docs/deviations.toml.

### F48-q45-2 (RL-1016): The new clause is the one item of E-05 a compiled program is neither refused nor stopped on; the spec and the entry do not say so, and a stop was not put

*missing-option, reported as medium*; where: docs/dialect-spec.md:71 (section 4's first sentence) and :79; docs/DECISIONS.md:1938 (against 1942, Question 46); runtime/src/ops.cpp:125, 1800, 1812; TODO.md (no item)

Section 4 says each exclusion "is a compile-time error" and "Nothing on this list is approximated at runtime". E-05's other reachable items stop by name; the clause of v0.40 does not: the compiled program runs on with another answer and a class whose dict and attributes disagree from then on. The entry does not say that A leaves this as it was, that no lint rule can exist, or that no stop is queued (Question 46's row and entry, the same day, say what is checked). A with a stop was not put. Read, not built: a mark on the view tested at the five hand-out places costs nothing on dict writes but stops read-only use too; a test at the write could share `is_dict`'s flag test.

Evidence: docs/dialect-spec.md:71 (quoted in the claim); :79 has no word on enforcement; E-06's row: "(refused at compile time where the module's text binds it)".
Probe review/q45/p1, compiled, status 70: `bella: not implemented: gc.get_referents (CPython's object graph, E-05)`; the same for gc.get_referrers and gc.get_objects.
Same probe, status 0 on both sides, CPython | compiled:
 fresh         42 42 42 | 42 None None
 delete        False None | False 1
 del_then_del  AttributeError / None False | deleted / None False
 clear         0 None | 0 1
 subclass      5 5 True | None None True
 method        called | AttributeError
 update        ['v', 'w', 'y'] [1, 2, None, 3] | ['v', 'w', 'y'] [None, None, 1, None]
 route:ror     after d['y'] = 42: 42 True 42 42 | 42 True None None
Read-only use agrees today (rows readonly, in_step, identity; p3 getstate_read: SAME).
Hand-out places: runtime/src/ops.cpp:125; types.cpp:2349-2350, 2337, 3434; gc.cpp:201. `is_dict` (runtime.hpp:997) tests the kind and FROZEN_DICT at ops.cpp:1800 and 1812; Flag's bit 15 is unused (object.hpp:89-95).
TODO.md has no item for a stop or a lint rule.

Probe: review/q45/p1 rows fresh, delete, del_then_del, clear, subclass, method, update, route:ror, route:referents, route:referrers, route:objects

Suggested: Ask the author: the clause as it is, with the row saying the program is not refused and what it then sees, or a stop (at the hand-out, or at the write after measuring it); record "no lint rule" in the entry as Question 31's does.

> Verifier: **confirmed** (medium). E-05's clause of v0.40 is neither refused nor stopped: the write compiles, exits 0 and gives another answer, with the class's dict and attributes disagreeing after. Section 4's opening sentence (spec :71) is false for it; E-05's row (:79) and the Question 45 entry (DECISIONS :1938) say nothing of a stop, a lint rule or that nothing was built, where E-06's row and the Question 46 and 31 entries do. Corrections: E-06's dynamic rebinding also runs on (42 vs 0), but is recorded; "A with a stop was not put" is true only of the record, and B's wording did name the cost of a write test; the stop sketch is unbuilt, and dict methods bypass ops.cpp:1800/1812. Cover: None for the wording. The behaviour itself is covered by E-05 (docs/dialect-spec.md:79): "and writing a class's own dict where a reflected operator of its mapping proxy hands it out (`mappingproxy.__or__`)"; RL-944 records only "Excluded (E-05) | The author's decision of 2026-11-25 (Question 45: A)". TODO.md has no item for a stop or lint rule, and reviews A46 and W47 do not raise it.

### F48-q45-3 (RL-1017): CPython's own source treats the hand-out as a defect (gh-152405); the entry does not cite it, and `|` and a gap in the `==` guard are open on main

*other, reported as low*; where: Objects/descrobject.c v3.15.2:1065-1074, 1165-1166, 1237-1258 (review/q45/src_descrobject); main as fetched 2026-11-26 (review/q45/src_descr_main); docs/DECISIONS.md:1938

CPython's source gives a stronger reason for the exclusion than the type cache, and the entry does not cite it: a comment warns that mappingproxy methods must not give access to the underlying mapping, and since gh-152405 `mappingproxy_richcompare` sends a copy because a write to a type's dict can crash the interpreter. `mappingproxy_or` has no such guard in v3.15.2 or on main as fetched 2026-11-26, and the `==` guard lets a mappingproxy over a mapping of the program's through (Finding 1). If upstream closes `|` as it closed `==`, E-05's named way describes nothing at the next pin, while `object.__getstate__(cls)`, the cell and `gc.garbage` stay.

Evidence: Objects/descrobject.c, v3.15.2 (review/q45/src_descrobject): 1165-1166 "WARNING: mappingproxy methods must not give access to the underlying mapping"; 1237-1241 "We have to guard the mutable `dict` instances, because it can otherwise mutate the type's `__dict__` entries and cause crashes. ... See gh-152405 for the details."; 1065-1074 mappingproxy_or unwraps both operands and calls PyNumber_Or.
main (review/q45/src_descr_main, fetched 2026-11-26): mappingproxy_or at 1074-1083 is the same text; mappingproxy_richcompare is identical to v3.15.2's (diff of the two functions: no difference). 3.14 has no guard.
CPython 3.15.2, review/q45/p1 row route:eq_own_proxy: `handed: ['dict']`, then `42 True 42 42` (the write reaches the class through `==`); row route:eq (a plain object of the program's): `handed: ['dict']`, `42 False None None` (a copy), SAME compiled.
The runtime's proxy_compare cites gh-152405 (runtime/src/types.cpp:2328-2330). I searched no tracker and sent nothing.

Probe: review/q45/p1 rows route:eq_own_proxy, route:ne_own_proxy, route:eq, route:ne

Suggested: Cite the two comments in the entry; add an item beside Question 31's upstream note (tracker searched first, text shown to the author, filed from his account only on his go-ahead).

> Verifier: **confirmed** (low). Facts hold: descrobject.c v3.15.2 guards == over an exact dict (1237-1258, gh-152405, "cause crashes") and leaves | (1065-1074) and == against another proxy unguarded, on main too; the Q45 entry and E-05 cite neither. Corrections: gh-152405 is already cited at DECISIONS.md:1216 and types.cpp:2329; upstream knows | (the issue's first comment names mappingproxy_or; PR gh-152449 closed unmerged; members: "leave the code as is"), so no upstream item is due; C-3-73 catches a change at a pin bump. New: on 3.15.2 such a write can end in SIGSEGV. Action: one sentence in the entry. Cover: Partly recorded, not covered. docs/DECISIONS.md:1216 (2026-11-13): "`mappingproxy_richcompare` in 3.15.2 (gh-152405) hands an exact dict to a dict, a frozendict or another proxy only; anything else is compared with a copy". The compiled difference on the | rows is E-05: "writing a class's own dict where a reflected operator of its mapping proxy hands it out (`mappingproxy.__or__`)". No TODO or RL entry for an upstream item or for the comments; conformance/cases/C-3-73 prints `other is BACKING` from a reflected __ror__, so make verify fails at a pin where | is guarded.

### F48-q45-4 (RL-1018): No case or test holds what stays [P1] at this edge

*test, reported as low*; where: pipeline/tests/test_review_2026_11_25_a45.py:15 and ROWS; pipeline/tests/review_a45/; conformance/cases/C-3-73_a_mappingproxys_operators.py:115-117, 136-140

The decision excludes the write and leaves the rest as CPython's: the dict a program is handed is the class's one dict, an exact dict, the same object by each way and in step with the class. That agrees compiled today and no case or test holds it for a class's dict: C-3-73's rows on what the other operand is given are of the program's own proxy, and the A45 test kept three of the reviewer's five programs, not A45-02's; its docstring still calls RL-944 and RL-946 "the author's". A change to the view or to the hand-out places would go unseen.

Evidence: review/q45/p1, SAME on both sides: readonly `True True 1 True True` (type is dict, same length, d["x"], same order, equal to the proxy); in_step `True 1 / False z` (cls.z = 1 and del cls.x show in the dict); identity `True True True` (the dict by `|`, by `g | proxy` and by object.__getstate__ is one object). review/q45/p3: getstate_read `dict 1 ['x'] / 2 True`, SAME.
pipeline/tests/test_review_2026_11_25_a45.py: ROWS has moddir, modname, textlocals; line 15: "RL-944 (a class's dict written through the proxy's reflected `|`) and RL-946 (a rebound `__builtins__`) are the author's."
conformance/cases/C-3-73_a_mappingproxys_operators.py:117 `proxy | Sees(), Sees() | proxy` and 136 `proxy == Peek()` use `proxy` over BACKING; 115-116 and 140 are the ordinary merge and the copy for class K.

Probe: review/q45/p1 rows readonly, in_step, identity; review/q45/p3 row getstate_read

Suggested: Keep A45-02's program as a row that only reads (and the stop's message, if Finding 2 ends in a stop); bring the docstring up to date.

> Verifier: **confirmed** (low). Holds, narrowed. E-05 (v0.40) excludes only the write; the reads agree compiled (14 hand-out routes, 21 rows SAME). No case or test holds that a class's dict handed out is one object by each way, that it follows the class afterwards, or object.__getstate__(cls); Question 45's commit changed documents only. Overstated: test_missing_names.py's PROXY already holds the handed-out type's name for a class's proxy, and the view following the class is held through the proxy (the same object), so only a change at the hand-out places would go unseen. The docstring predates both answers.

Minor, one line each, not verified:

- E-05's words "a reflected operator of its mapping proxy" put the reflection on the wrong side for the commonest form: in `C.__dict__ | g` the proxy's operator is the plain one and g's is reflected; in `g | C.__dict__` g's plain `__or__` is called a second time with the dict (p1 row route:or: handed ['mappingproxy', 'dict']); an OrderedDict or defaultdict subclass is given it in `__init__` (rows route:orderedsub, route:defaultsub). The parenthetical names `__or__`; `__ror__` is the same C function. The entry's own sentence has it right.
- The entry's "read 1,000 times" and "cached three times" are true but more than needed, and one look-up is not enough: two make CPython's cache hold a name, one does not (p1 rows warm:2 `1 1 1 2`, warm:1 `2 2 2 2`, miss:2 `None None 42`, miss:1 `42 42 42`), because a class's first look-up takes the cache slot before it assigns the version tag (typeobject.c:6356, 6407, 6430). "Already holds" and "depends on its type cache" are right; "looked up before" would not be.
- "CPython's own result is not fixed by the program's text" holds in the strict sense: review/q45/explore/evict.py, one text, PYTHONHASHSEED=0, 40 runs each: 40 of 40 print 1 with no other look-ups; after 500 look-ups of other names 22 print 1 and 18 print 2 (the slot is taken from the name's address, typeobject.c:53-55).
- No count of real use is in the entry (Questions 46 and 47 have one). Local only, by grep: no `|` with a class's `__dict__` or `vars(cls)` as an operand, no `object.__getstate__` of a class and no DEBUG_SAVEALL in CPython's standard library outside its tests (1,038 files), the environment's packages (904) or targets/ (75).
- E-06's rationale "CPython already rejects the second" (assignment to attributes of built-in types) is not true of a built-in type's dict handed out by the proxy: p1 row builtin, CPython `dict / 1 1 1 True / 1` (int.zz and (5).zz are 1), compiled `dict / 1 None None False / 1`. E-05's clause covers it now.
- `sys.getrefcount`, which E-05 names, stops with "(CPython has it; the runtime does not yet)" (p1 row route:getrefcount); Question 47's entry queues the names under an exclusion, so not new.
- A program that calls `object.__getstate__` without `copyreg` in its closure stops with "importing 'copyreg' (the standard library: step 3b)" (probe p2, four rows); TODO.md:500 records it.

Covered: Verdict: the decision (an exclusion) is sound and every measurement in the entry holds; the findings are about one false statement of fact, the completeness of the words, and enforcement.

How: read docs/DECISIONS.md:1927-1960, commit 5ec495e's four files, the spec's section 4 and version lines, RL-944, RL-937, RL-489, TODO.md, the A45 review file and test, C-3-73 and C-3-82's entry, and the runtime's view (object.hpp:923-999, 2415-2422; types.cpp:2275-2350, 3431-3437; ops.cpp:125, 1800-1812; gc.cpp:193-203). Fetched and read CPython v3.15.2's Objects/descrobject.c and typeobject.c (review/q45/src_*), and descrobject.c of main, 3.15 and 3.14. Three builds of six: p1 (52 rows: 18 SAME, 34 DIFF), p2 (5 rows, stopped for want of copyreg), p3 (p2 with copyreg, 5 rows). Outputs: review/q45/p1/out.txt, p2/out.txt, p3/out.txt, explore/*.out.

1. Facts: all six measurements of the entry reproduce on both sides (p1 rows fresh, delete, add, warm:1000, miss:3, merge). Source statements confirmed by reading: mappingproxy_or (descrobject.c:1065-1074); _PyType_LookupStackRefAndVersion answers from the cache, a NULL value included (typeobject.c:6354-6395); find_name_in_mro goes past it (6193); a stale miss turns into 42 after an unrelated `cls.z = 5` (row set_other), so no PyType_Modified at the dict write. \"Not fixed by the program's text\" confirmed by repeated runs. False: \"the other way to that object\" (Finding 1).
2. Options: A, B and C are described accurately as far as the source shows; exactness is not available since CPython's answer varies from run to run, so an exclusion is the right kind of answer and the recommendation was sound. Left out: the other ways (Finding 1), a stop (Finding 2), CPython's own view of the hand-out (Finding 3), a count of use (minor). The record of recommendation and answer matches the commit.
3. Words: true for the way they name, incomplete, no mechanism of Bella's; docs/deviations.toml has no entry and needs none; enforcement and lint status unstated.
4. Follow-through: the commit changed the row, v0.40's line, RL-944's verdict and TODO's item, nothing else; nothing was to be built; nothing holds it (Finding 4).
5. Consistency: checked against Question 46 (same day, says what is checked), RL-937 and the sweep of 2026-11-22 (the runtime's own hand-outs), RL-489 (open), C-3-82 and Question 44 (consistent).

Ways measured under CPython that do not hand the dict out: `proxy |= g`, `proxy == g` and `!=` (a copy), `g == proxy`, `proxy < g`, `.keys() == g`, `.items() | g`, `proxy & g`, a frozendict, UserDict or ChainMap subclass on the right of `|`, `.copy()`, `copy.copy(proxy)`, `vars(C)`, `type.__dict__[\"__dict__\"].__get__(C)`, `object.__getattribute__(C, \"__dict__\")`, a metaclass inheriting another class's `__dict__` descriptor, `.keys().mapping`, `.get.__self__`, an iterator's `__reduce__`, `__class_getitem__`, `reversed`, `dict(proxy)`, `object.__reduce_ex__(C, n)`, `object.__setattr__(C, ...)`.

Not covered: REPORT.md was not written: the Write tool refused it (\"Subagents should return findings as text, not write report files\"), and I did not go round that with a shell write. The full account is in these fields; the probes, their outputs and the fetched sources are under review/q45/ (p1, p2, p3, explore, src_*).

Not examined: `ctypes` beyond the dynamic import (compiled stops at it; no static `import ctypes` build); the cost of a stop under Finding 2 (read from the source, not built or measured); the compiled program after such a write beyond the rows listed (I read set_attr, del_attr and release_class_dict and saw the view keep counts of its own, but ran no sanitizer build and no finaliser-order rows); an immortal class's view beyond the one `builtin` row; GitHub or PyPI counts of use (local trees only); the upstream tracker (nothing searched or sent; the issue number is the one in CPython's comment); how the question was worded to the author in chat (only the entry's record of it); Questions 29 to 48 except where they touch this one.


## q46: Question 46

### F48-q46-1 (RL-1019): `del __builtins__` was left out of E-06 as "measured, it agrees"; it does not: CPython raises KeyError where the compiled program runs

*wrong-fact, reported as high*; where: docs/DECISIONS.md:1942 ("a deletion is not excluded, since measured it agrees"); docs/reviews/review-log.md:1358 (RL-946, "a deletion agrees and is not refused"); pipeline/l1/frontend.py:85-94, :108 (Store only); pipeline/tests/test_builtins_binding.py:70; docs/dialect-spec.md:80 (silent on deleting); commit 3bee7db

The entry narrowed the draft the author answered: a deletion is not excluded, "since measured it agrees". Only a function made afterwards was measured. CPython reads the namespace's `__builtins__` again at every C-level import (PyImport_Import, Python/import.c:4649-4657), so after `del __builtins__` (or globals().pop, delattr) the statement `class C[T]`, `Generic[T]`, `TypeVar(bound=)`, `time.strptime`, `time.tzset` and `__reduce_ex__(2)`, called from that module's code, raise KeyError('__builtins__'). Compiled, all of them run. The program is neither refused nor excluded, uses [P1] things only, and nothing registers the difference.

Evidence: review/q46/p1del and p6del2 (r48_both.py, out.txt). CPython | compiled:
del-body: `body KeyError ('__builtins__',)` | `body 2022`
del-before (function made before the deletion): `KeyError ('__builtins__',)` | `2020`
del-after: KeyError | `2021`
del-tzset: KeyError | `None`
del-imported (an imported module deleting its own): KeyError | `2020`
del-reduce: `copyreg imported False` on both; KeyError | `tuple`
del-pop (globals().pop): KeyError | `2020`
p6del2 row del: `class Box(Generic[T]) KeyError ('__builtins__',)`, `class Box2[U] KeyError ...`, `TypeVar(bound=int) KeyError ...` | `Box`, `Box2`, `B`; rows delattr and del-item the same.
Controls and the entry's own rows (function, class body, lambda made after; the namespace; NameError on a read; an import after) are SAME.
Source (v3.15.2): import.c:4653 `builtins = PyObject_GetItem(globals, &_Py_ID(__builtins__));` 4655 `// XXX Fall back to interp->builtins or sys.modules['builtins']?`; callers timemodule.c:994, :1172, typeobject.c:7926, typevarobject.c:338, :2317, :2375.
Use: no deletion of the name in 10,613 files searched (tools/literal.py); GitHub code search `"del __builtins__" language:python`: 1,506 files, the first page CTF jails and judge sandboxes.

Probe: p1del rows del-body, del-before, del-after, del-tzset, del-imported, del-reduce, del-pop, del-datetime; p6del2 rows del, delattr, del-item

Suggested: Ask the author: E-06 names deleting too, as the draft did (refuse `del __builtins__` at module scope, a REFUSED row, drop it from ALLOWED), or the runtime's C-level imports look at the caller's namespace. Correct DECISIONS 1942 and RL-946 either way.

> Verifier: **confirmed** (high). Reproduced; nothing covers it. `del __builtins__` at module scope (also `globals().pop`, `delattr`) is neither refused nor excluded, and DECISIONS 1942, RL-946, commit 3bee7db and the check's docstring say a deletion agrees. Only builtin look-ups in functions made afterwards were measured. Under CPython that module's code then gets KeyError('__builtins__') from C paths importing through PyImport_Import: `class C[T]`, `Generic[T]`, `TypeVar(bound=)`, `time.strptime`, `tzset`. Compiled, all run. Overstated: `__reduce_ex__(2)` differs only before `copyreg` is imported. Real use: none found; the fix is small. Cover: None. E-06 names only "rebinding a module's `__builtins__`", and DECISIONS 1942 itself says "a deletion is not excluded, since measured it agrees". No D-nn row, TODO entry or stop applies. Nearest record, not a cover: RL-486 (closed) "Not a defect: seen only by a program that replaces `builtins.__import__`, which E-04 excludes" (same C function, another observable; its "seen only by" does not hold here). The side row `twice` (NameError.name None after a second del) is known: RL-498, open.

### F48-q46-2 (RL-1020): Three bindings written in a module's text pass check_builtins_binding, and the program runs on the standard builtins

*defect, reported as medium*; where: pipeline/l1/frontend.py:112-116 (visit_AnnAssign), :127-129 (visit_alias); pipeline/tests/test_builtins_binding.py:6; docs/dialect-spec.md:80, :371; docs/DECISIONS.md:1942

The check lets three textual bindings through: (a) a walrus in the subscript or attribute target of an annotation without a value (visit_AnnAssign visits only the annotation; CPython evaluates the target's object and subscript); (b) `from m import *` where m's `__all__` names `__builtins__` and m answers through a module `__getattr__`; (c) `import pkg.__builtins__`, which sets the package's attribute to the submodule. The test's "each way a module binds the name is refused" and the spec's "refused at compile time where the module's text binds it" are false for them. All are inside E-06, so excluded, but each is decidable at compile time at no run-time cost.

Evidence: p3ann: `box[(__builtins__ := {"len": fake_len})]: int`, then a function made after returning len([]). CPython: `subscript a function made after 42 the name is a dict True`; compiled: `subscript a function made after 0 the name is a dict False`. Row attribute (`(__builtins__ := {...}).a: int`) the same. check_builtins_binding(ast.parse(...)) passes both; with a value (`box[(__builtins__ := 1)]: int = 2`) it refuses.
p4star star-getattr: CPython `a function made after 42 the name is a dict False`, compiled `a function made after 0 the name is a dict True`. Row submodule: CPython `after module 42 True`, compiled `after module 0 False`. Row star (an ordinary module: the name becomes the builtins' dict) is SAME.
frontend.py:113-114: `if node.value is None:                   # `__builtins__: T` binds nothing` / `self.visit(node.annotation)`.
A sweep of 42 forms through the check (walrus in a default, base, class keyword, decorator, f-string, generator expression; except*; with-tuple; starred; dotted and lazy imports; every match capture; global in a class body or nested): every other binding refused, every non-binding passed.

Probe: p3ann rows subscript, attribute; p4star rows star-getattr, submodule

Suggested: Fix (a): with no value, visit a subscript target's object and slice and an attribute target's object; add both rows to REFUSED. For (b) and (c) refuse from the closed world (a module named `__builtins__`; an `__all__` naming it) or list them as not checked.

> Verifier: **confirmed** (low). Confirmed only for (a): visit_AnnAssign (frontend.py:112-116) skips a non-simple target's expressions when there is no value, so a module-scope walrus binding __builtins__ in `box[(__builtins__ := d)]: int` or `(__builtins__ := d).a: int` is not refused. That contradicts the test docstring (test_builtins_binding.py:6) and spec line 80 ("refused at compile time where the module's text binds it"). (b) star import and (c) `import pkg.__builtins__` are dynamic routes, covered by DECISIONS.md:1942 "excluded and not checked" and RL-946 "Excluded (E-06)". Low: the form is pathological and already ins ... Cover: (b)/(c): DECISIONS.md:1942 "What reaches the name dynamically (...) is excluded and not checked"; RL-946 "Excluded (E-06)". (a): none (the decision's list of refused forms omits it and says "an annotation without a value binds nothing").

### F48-q46-3 (RL-1021): What is "excluded and not checked" is silently ignored at run time, and section 4 of the spec says the opposite of every exclusion

*words, reported as medium*; where: docs/dialect-spec.md:71 (section 4's opening), :80 (E-06); docs/DECISIONS.md:1942 ("excluded and not checked"; "so that no program runs on builtins CPython's would not have")

The routes the decision leaves unchecked are silently ignored: the write lands in the namespace and functions made afterwards keep the standard builtins, with no error and no stop. The decision records the choice, so this is not a new difference; but the spec says of every exclusion "Each exclusion is a compile-time error ... Nothing on this list is approximated at runtime", and E-06's row does not say what such a program sees. Three unrefused forms are literal in the text (`X.__builtins__ = v`), and the entry's purpose clause does not hold. A stop by name (the look where a function is made, without B's records) was not among the options put.

Evidence: p2dyn, CPython | compiled:
globals: `body 0 before 0 after 42 class body 42 lambda 42 True generator [42] comprehension [0]` | `body 0 before 0 after 0 class body 0 lambda 0 False generator [0] comprehension [0]`
vars, locals, update, setattr, moddict: `one made after 42 its builtins are mine True the namespace has mine True` | `one made after 0 its builtins are mine False the namespace has mine True`
attribute (`sys.modules[__name__].__builtins__ = custom`) and main (`__main__.__builtins__ = custom`): 42 | 0, the same lines
other-attribute (`mother.__builtins__ = custom`): `one it makes now 42 True` | `one it makes now 0 False`
empty (`globals()["__builtins__"] = {}`): `an empty dict NameError` | `an empty dict 0`
same (the builtins' own dict as the value): SAME.
tools/literal.py over 10,613 files: one literal attribute store, a real rebinding (profiling/sampling/_sync_coordinator.py:190, under E-03); of five literal-key forms two are not namespaces (mypy/semanal.py:617, twisted/python/failure.py:330), so only the attribute form could be refused without refusing wrongly.

Probe: p2dyn rows globals, vars, locals, update, setattr, attribute, main, moddict, module-value, empty, other, other-attribute

Suggested: The author's text: say in E-06 (or section 4's opening) that the unrefused routes are not detected and what a program then sees. Consider refusing a literal attribute store and a constant-name setattr with the others. A stop for the rest costs the look where a function is made.

> Verifier: **confirmed** (medium). One verdict for q46-3 and c10-docs-consistency-4. The choice is known (DECISIONS.md:1938, :1942; RL-944 and RL-946 "Excluded"), but the wording is false. Section 4's lead ("each exclusion a compile-time error; nothing approximated at runtime") does not hold. 12 dynamic E-06 forms (globals, vars, locals, update, setattr, attribute, main, moddict, module-value, empty, other, other-attribute) and the E-05 reflected `|` write (rows `e05 or` and `e05 method`) run to status 0 with an answer CPython does not give. E-05's and E-06's rows do not say what a program sees. Writes into the builtins end in  ... Cover: DECISIONS.md:1942 "What reaches the name dynamically ... is excluded and not checked"; RL-946 "Excluded (E-06)"; RL-944 "Excluded (E-05)"; Question 45 option A. These cover the choice, not section 4's lead or the E-05 and E-06 rows.

### F48-q46-4 (RL-1022): The evidence count reproduces in substance; three of its figures do not

*wrong-fact, reported as low*; where: docs/DECISIONS.md:1940 ("CPython's own tests have one"), :1942 ("9,533 Python files", "twenty name it nowhere")

The conclusion holds: no module rebinds its own `__builtins__` in the standard library, the environment, the vendored libraries or the thirty packages (the frontend's own check refuses 0 of 10,613 files), and GitHub's counts are 9,744 and 30,816. Three figures do not reproduce: the thirty newest wheels hold 8,859 Python files, not 9,533 (the difference, 674, is exactly google-genai's count); twenty-four packages name it nowhere, not twenty (the entry itself lists six that do); and `test_annotationlib.py`'s one is a class attribute of an object standing in for a function, not a module rebinding its own, so CPython's tests have none. All err on the cautious side. Deletions were not counted.

Evidence: review/q46/tools/fetch.py and scanzip.py (the newest wheels, all uploaded by 2026-11-25, read as archives, nothing run): `TOTAL 8859 python files; 6 packages name it` (ipython, numpy, pydantic, scrapy, setuptools, twisted); `google_genai: 674 files, 0 name it`.
facts/scan.py: standard library `694 files, 12 mention it, 0 refused by the check`; site-packages `993 files, 12 mention it, 0 refused`; targets/vendor `67 files, 0 mention it`.
CPython v3.15.2 Lib/test/test_annotationlib.py:1676 `__builtins__ = {"int": int}` in the body of `class Annotate:` inside `def outer():`, beside `__globals__ = {"MyClass": MyClass}` and `__closure__ = (types.CellType(str),)`.
`gh api search/code`: q=`"__builtins__ =" language:python` gives 9744; q=`"\"__builtins__\": {}" language:python` gives 30816. GitHub's tree of v3.15.2: 1302 .py files under Lib/test.

Suggested: Correct the three figures in the entry, or say which archives gave 9,533. No change to the decision follows.

> Verifier: **confirmed** (low). The conclusion holds, but three figures in DECISIONS.md:1940 and :1942 do not reproduce. The newest wheels of the thirty packages hold 8,859 Python files, not 9,533 (the difference, 674, is exactly google-genai's count, so it may be counted twice). Six packages name `__builtins__`, so 24 name it nowhere, not twenty. test_annotationlib.py:1676 is a class attribute in `class Annotate` inside `def outer()`, not a module rebinding its own `__builtins__`, so CPython's tests have none. No decision change follows.

### F48-q46-5 (RL-1023): The refusal names a line and no file; in an imported module the line is another file's

*other, reported as low*; where: pipeline/l1/frontend.py:101-103 (refuse); pipeline/build.py:987-988; docs/dialect-spec.md:71 ("reported at the file and line that uses it")

A binding of `__builtins__` in an imported module of the program is refused (the check runs on every module, as it should), but the message gives only a line: a four-line prog.py is refused with "(line 7)". Section 4 says an exclusion is reported at the file and line that uses it. D-10's check words its message the same way, so this is the frontend's habit and not new with this step; it shows here because E-06's is the first exclusion refused in every module of the closure.

Evidence: p5ref: prog.py (4 lines) imports mref.py, whose line 7 is `__builtins__ = {"len": _fake}`. Under CPython prog.py prints 42. `.venv/bin/python r48_both.py review/q46/p5ref x` printed `BUILD FAILED (DialectError): E-06: assigning to `__builtins__` (rebinding a module's builtins is excluded) (line 7)` (kept in p5ref/observed.txt, copied from the terminal). frontend.py:102-103 builds the message from `getattr(node, 'lineno', '?')` alone; build.py:988 prints `bella: refused: {exc}`. D-10's: `D-10: '{kind}' leaving a finally block is a compile-time error (line {st.lineno})`.

Probe: p5ref

Suggested: Name the file in a DialectError where lower() knows it, for D-10 as well; the expected line in test_the_command_refuses_it changes with it.

Minor, one line each, not verified:

- REPORT.md was not written: the Write tool refused a report file from a subagent ('return findings as text'). The full account is this return; every probe's prog.py, rows.txt and out.txt are under review/q46/ (p1del, p2dyn, p3ann, p4star, p5ref, p6del2), the CPython-only measurements under facts/, the scan scripts under tools/, the fetched C sources under cpython-src/.
- First entry (DECISIONS 1940), 'a module's frame keeps the builtins it started with': true for names, but after a rebinding the body and functions made before it use the new `__builtins__`'s `__import__` for C-level imports (facts/m5.py: time.strptime from both gives `RuntimeError fake import called`). Inside the excluded act now; it matters only if B is ever built, which would be wider than described.
- v0.41's 'which CPython's functions made afterwards take as their builtins' leaves out the module's own generator expressions (`[42]` against a comprehension's `[0]`, p2dyn row globals) and the C-level imports.
- Assigning to an attribute of `builtins` (E-06's first clause, older than this step) is not refused at compile time either: `builtins.len = f` ends compiled with status 70 and `bella: not implemented: the report of an exception when sys.stderr cannot be written ...`, which names neither E-06 nor the assignment (p2dyn rows mut-attr, mut-main, mut-setattr, mut-dict, mut-imported, mut-del).
- A second `del __builtins__` raises NameError with `name` None compiled (p1del row del-twice; p2dyn rows del-unbound, del-unbound-global for any name): that is RL-498, already open in the review log and TODO.
- `_PyDict_LoadBuiltinsFromGlobals` takes any object that is not a module as it is (dictobject.c:2718-2722), not only 'a dict as itself'.
- Question 45's addition to E-05 the same day is likewise an exclusion nothing checks, so the point about section 4's opening sentence (Finding 3) applies to it too.
- review/q46/pypi/wheels holds 97 MB of downloaded wheels (data only, never run); it can be deleted once the count is no longer needed.

Covered: Both DECISIONS entries (1940, 1942), commits 987af17 and 3bee7db (stat and diff), the spec's E-06 row, section 4's opening and the v0.41 entry, RL-946, TODO (B's step is gone, nothing else queued), docs/deviations.toml (exclusions are not in it; nothing there covers Finding 1), docs/design.md (no mention of the check), and the A45, A46 and W47 review files for earlier mentions.

Facts: every row of the first entry measured again under CPython 3.15.2 (facts/m1.py to m5.py): body 0, before 0, after/class body/lambda 42 42 42, `after.__builtins__ is __builtins__` True, a module as the value 7, an empty dict NameError, a deletion 0, the main module's a module and an imported one's a dict. All hold. The compiled side of the same rows, through the routes that are not refused (p2dyn), gives 0, 0, 0, False, 0, 0 as the entry says; the reads agree (p1del row read); namedtuple's `'__builtins__': {}` is honoured (row staged). funcobject.c:197 and `_PyDict_LoadBuiltinsFromGlobals` read in the fetched 3.15.2 sources, with import.c, typevarobject.c, timemodule.c and typeobject.c; `load_global` and `fn_builtins` read in the runtime.

Evidence count: the standard library (694), the environment (993) and the vendored libraries (67) scanned with the frontend's own check and by mention; the newest wheels of the thirty named packages fetched from PyPI and scanned as archives; the two GitHub counts and the 1,302 test files re-queried.

The refusal: 42 forms through check_builtins_binding directly, and six builds (p1del 15 rows, p2dyn 22, p3ann 3, p4star 4, p5ref refused, p6del2 5).

Options and recommendation: A, B and C were a fair set. B was recommended on exactness before any count of use; the author asked for the count twice and chose A on it, which fits the author's stated preference; the record of who said what reads straight. What was missing from the question is in Findings 1 and 3: CPython's second reader of `__builtins__`, and a stop by name as a fourth option. The decision for A itself is sound. No conflict found with Questions 29 to 48.

Not covered: REPORT.md could not be written (the Write tool refuses report files from a subagent); nothing else of the task's output is missing.

Not examined: the source distributions of the thirty packages (wheels were taken, so the record's 9,533 could not be matched to an archive set); the GitHub sample of thirty files; CPython's 1,302 test files other than test_annotationlib.py (GitHub's search of the repository's Lib on the default branch finds the phrase only there and in profiling/sampling/_sync_coordinator.py). The conversation in which the question was put: only what DECISIONS, TODO and the commits record. pipeline/tests/test_builtins_binding.py was read, not run (it builds). The eval1 and eval2 legs and fidelity lean were not run. Other C-level imports after a deletion (pickle, array's reduction, warnings with a source) and B's cost, which was never built or measured.


## q47: Question 47

### F48-q47-1 (RL-1024): D-33 does not say that an import no longer calls what a program put in _thread, _weakref or _imp

*words, reported as medium*; where: docs/dialect-spec.md:245 (D-33); docs/deviations.toml:211

CPython's lock code reads _thread.RLock, allocate_lock, get_ident, _weakref.ref, _imp.acquire_lock and release_lock from those modules each time it runs (_bootstrap.py:253-254, 310, 373, 435, 459, 461). A program that assigns one is called at every first import, at an import that finds its module initialising and (for _imp) when the lock goes. Compiled, the assignment is taken and never called. Plain names and plain import statements: no str subclass, no name of _frozen_importlib. D-33's words do not say it, E-04 and E-06 do not cover it, and no record mentions it.

Evidence: review/q47/p2 (`.venv/bin/python r48_both.py review/q47/p2 --rows review/q47/p2/rows.txt`, kept as out.txt). DIFF rows, status 0 on both sides:
patch thread: CPython `a first import: 4 ['_thread.RLock', '_thread.allocate_lock', '_thread.get_ident', '_thread.get_ident']`, `a module that imports itself: 6 [...]`, `a body that raised: 4 [...]`; compiled `0 []` for each.
patch weakref: CPython `a first import: 1 ['_weakref.ref']`; compiled `0 []`.
patch imp: CPython `a first import: 10 ['_imp.acquire_lock', '_imp.release_lock', ...]`, `the exception released: 2`; compiled `0 []` everywhere.
patch none: SAME. Both sides print True for `_thread.get_ident is get_ident`, so the assignment is taken.
grep for get_ident, allocate_lock, acquire_lock in the spec, the register, the review log, TODO, DECISIONS and the W47 document: no hit about this. grep of the stdlib, .venv site-packages and targets for such an assignment: none.

Probe: review/q47/p2, rows patch thread, patch weakref, patch imp, patch all, patch none

Suggested: Reword: add a clause to D-33 and its lint cell (an import does not call what a program put in place of _thread.RLock, allocate_lock, get_ident, _weakref.ref, _imp.acquire_lock, release_lock). No code.

> Verifier: **confirmed** (medium). D-33 does not say that the lock code's calls to _thread.RLock, allocate_lock, get_ident, _weakref.ref, _imp.acquire_lock and release_lock (read from those modules at each call) are not made. A program that replaced one sees no call compiled. Words of the registered deviation are incomplete; no code defect.

### F48-q47-2 (RL-1025): weakref.ref.__subclasses__() silently lacks the lock machinery's KeyedRef; W47 said a stop holds it

*defect, reported as medium*; where: runtime/src/types.cpp:1476-1483; docs/dialect-spec.md:127 and :245; docs/reviews/2026-11-25-claude-workflow-47-review.md:27 and :43

CPython's weakref.ref.__subclasses__() lists _frozen_importlib's KeyedRef, the lock table's class (_bootstrap.py:70). The spec's `type` row calls __subclasses__() complete. W47's verdicts 16 and 32 say the difference is held by the runtime's stop for a built-in type's __subclasses__ (types.cpp:1479, read): read, not run. The stop tests !c->heap_type, and the weak reference is a class of a prelude, so it answers with a list that lacks the class. list, RuntimeError and object do stop. D-33 does not mention it. The same gap beyond the locks: _io._IOBase's subclasses come in the reverse of CPython's order.

Evidence: review/q47/p6 (out.txt):
ref: CPython `ReferenceType [('_frozen_importlib', '_WeakValueDictionary.__init__.<locals>.KeyedRef')]`; compiled `ReferenceType []`, status 0.
ref-weakref: CPython the same class, then `('weakref', 'WeakMethod'), ('weakref', 'KeyedRef')`; compiled only the two of weakref.
iobase: CPython `[('_io', '_TextIOBase'), ('_io', '_BufferedIOBase'), ('_io', '_RawIOBase')]`; compiled `[('_io', '_RawIOBase'), ('_io', '_BufferedIOBase'), ('_io', '_TextIOBase')]`.
review/q47/p4, subclasses list: compiled status 70, `bella: not implemented: the subclasses of the built-in type 'list': CPython's list names its own classes` (RuntimeError and object the same); subclasses ref: compiled `[]`, status 0.
types.cpp:1479: `if (!c->heap_type) throw NotImplemented("the subclasses of the built-in type '" ...`.
W47 document, line 27: "It is held by the runtime's stop for a built-in type's __subclasses__ (runtime/src/types.cpp:1479, read)".

Probe: review/q47/p6, rows ref, ref-weakref, iobase; review/q47/p4, rows subclasses list|RuntimeError|ref|object

Suggested: Fix: let the stop cover the types the runtime writes as prelude classes (refuse_in already asks prelude_classes()), or name KeyedRef in D-33. Register the order of _IOBase's subclasses as a log row of its own.

> Verifier: **confirmed** (high). weakref.ref.__subclasses__() silently omits _frozen_importlib's KeyedRef because the stop at types.cpp:1479 tests !heap_type and weakref.ref is a prelude class. W47 verdicts 16 and 32 say a stop holds it; false for prelude classes. _io._IOBase.__subclasses__() order is reversed against CPython. The spec row says complete, D-33 does not mention either.

### F48-q47-3 (RL-1026): test_module_locks.py holds three of D-33's ten statements and says it holds each

*test, reported as medium*; where: pipeline/tests/test_module_locks.py:4-15; docs/reviews/review-log.md:1368 (RL-956)

The docstring says the test holds each part of what the register says. Its rows hold the fourteen names, the two code objects and that one __hash__ call falls in _get_module_lock. Held by no test: the counts (twice, twice) and when the second pair comes, __eq__, _imp.lock_held(), the other routes (importlib.__import__, a lazy import, import_module's exact str), the callbacks' ignored exceptions, _lock_unlock_module's argument (RL-956 is Registered with no row) and D-17's lock frames. A port that left out __import__ calling _lock_unlock_module would pass, though the docstring says every row then agrees and D-33 ends.

Evidence: test_module_locks.py:5-6: "The register says what a program sees of that, and this test holds each part"; :15: "When the threads milestone brings CPython's locks, every row agrees with CPython and D-33 ends; this test then goes." Its rows (lines 57-71): name, other, hash, plain, varnames.
`grep -ln '_lock_unlock_module\|lock_held' pipeline/tests/*.py conformance/cases -r`: no test calls _lock_unlock_module with an argument CPython refuses, none reads lock_held inside a name's method. `grep -rln 'D-17' pipeline/tests conformance/cases`: nothing.
review-log.md:1368: "Registered (D-33) | D-33's words say it".
Rows with both sides recorded in review/q47/p1/out.txt: `calls plain` CPython 16 calls (2 in _get_module_lock, 2 in cb, held=True) against 8 compiled; `lul list` CPython `TypeError: cannot use 'list' as a dict key (unhashable type: 'list')` against `None`; `deep stmt` ok to 68 against 73; `drop 79` CPython's "Exception ignored while calling weakref callback <function _get_module_lock.<locals>.cb ...>" against nothing.

Probe: review/q47/p1, rows calls *, lul *, deep *, drop *

Suggested: Add rows from review/q47/p1 (calls ..., lul list|S, deep stmt|mod, drop 79; q47log.py gives each call its caller and lock_held), or reword the docstring and RL-956 to what is held.

> Verifier: **confirmed** (low). The docstring of test_module_locks.py ("this test holds each part") overstates: it holds the 14 names, `other`, one __hash__ row, `plain` and the two code objects. Counts, __eq__, lock_held, other routes, ignored callback exceptions, _lock_unlock_module's argument (RL-956) and D-17's frames are registered in D-33 but held by no test. deviations.toml's own note states the true scope, so this is docstring wording. Cover: deviations.toml D-33 observable: "`pipeline/tests/test_module_locks.py` holds the names, the reviewer's row and the code objects"

### F48-q47-4 (RL-1027): Option B's cost was given as CPython's 12 calls; compiled, a lock cycle costs two to three first imports (C stands)

*cost, reported as low*; where: docs/DECISIONS.md:1954; TODO.md:679-687

The entry gives B as about 400 lines of CPython's text and 12 Python calls more for each first import (both true) and records no reason for recommending C over the exact option. Measured: CPython's lock text, lines 52 to 482 unchanged, runs today as a module of a compiled program and agrees with CPython on 16 rows. But a lock made, taken, released and dropped costs 211 to 394 microseconds compiled against 4 to 8 under CPython, and a first import of a one-line module 76 to 168 compiled. B now would more than triple the cost of a first import. That is a sound reason for C, and it is not in the record.

Evidence: review/q47/p3 (locks_copy.py is _bootstrap.py 52-482 and 1118-1128, unchanged): 15 of 16 rows SAME. Row S on both sides: `hash m in _get_module_lock:395 held=True`, `:416`, then `cb:411`, `cb:412`; `depth 74` ok and `75` RecursionError on both; `drop 79` differs only in the address and the file path of the same report.
review/q47/p5, microseconds, CPython / compiled (shared host, load 13 to 15):
a lock made, taken, released and dropped: 4.34 / 211.00 (three more runs 4.0-4.8 / 228-394; p4: 7.5 / 324-330)
a first import of a one-line module (40 of them): 68.63 / 76.40 (more runs 70-78 / 81-168)
_ModuleLock('m') made and dropped: 0.44 / 30.91
acquire and release of one _ModuleLock: 2.60 / 119.50
_thread.RLock(): 0.38 / 9.66; with an RLock: 0.17 / 17.63
an instance of a class of the program's: 0.34 / 7.42
review/q47/facts/f6.py under CPython: `12 lock machinery calls; 6 of _ImportLockContext`. Not tested: the text inside the bootstrap prelude at start, where _thread and _weakref are not imported yet (D-30).

Probe: review/q47/p3 (all rows); review/q47/p5 (all rows); review/q47/p4, row time 20000

Suggested: Add the compiled figure and the reason to the DECISIONS entry and to TODO's item, so that B is not taken up early on the strength of 12 calls.

### F48-q47-5 (RL-1028): The refusal that TODO queues for RL-954 was not among Question 47's options

*missing-option, reported as low*; where: docs/DECISIONS.md:1954; TODO.md:857-867; runtime/src/call.cpp:686-688

D-33's longest sentence (the name's __hash__ and __eq__, the callbacks, lock_held) registers a silent difference for an import by a str subclass with methods of its own. For the same shape of edge the runtime already stops (an attribute name of that kind, call.cpp:688), and TODO puts that very refusal as one of two options of a later question (RL-954, after Question 48). It was not put with Question 47, where it would have made that part of D-33 a stop at no cost for an exact str. If the later answer is the refusal, about half of the D-33 row is dead three days after it was written. No count of real use of such names was taken.

Evidence: runtime/src/call.cpp:688: `throw NotImplemented("an attribute name of a subclass of str with a __hash__ or __eq__ of its own (CPython has it; the runtime does not yet)");`
TODO.md:864-867: "Then put RL-954 to the author: register what the finder calls, or refuse an import by a name whose type is a str subclass with methods of its own, as an attribute name of that kind is refused".
DECISIONS.md:1954: "The options were A (words now ...), B (CPython's locks now ...) and C (A now, B with the threads milestone)."
review/q47/p1, `calls plain`, CPython's side: every call the lock code makes on a program's object is a method of such a name: `hash sample in _get_module_lock:438 held=True`, `:459`, `cb:454`, `cb:455`; `calls import_module` (an exact str reaches the lock) is SAME with 0 calls.

Probe: review/q47/p1, rows calls plain, calls import_module

Suggested: Ask the author: put RL-954's question (register or refuse) before more work on D-33's words, with a count of use, as was done for Question 46.

### F48-q47-6 (RL-1029): The entry's compiled recursion figure does not reproduce (72 is 73), and its GitHub counts do not hold together

*wrong-fact, reported as low*; where: docs/DECISIONS.md:1954

The entry: a recursion with an import at its bottom reaches 68 levels under a limit of 80 against 72, CPython's finder going 10 below _find_and_load. CPython's 68 holds; compiled it is 73 with the decision's runtime, and with 10 frames against the compiled body's 5 a difference of 4 cannot be. The 10 is for a first import from a directory; the next goes 9 (69 against 73). The GitHub counts (_ModuleLock 2,660 files, _get_module_lock 45, most of them copies of _bootstrap.py) cannot be counts on one index, since every copy holds both names. The conclusion drawn from them stands on what I read.

Evidence: review/q47/p2 (a one-line sample.py, the program's first import from its directory, limit 80): `depth 68` SAME ok; `depth 69` to `73` DIFF, CPython RecursionError, compiled ok; `depth 74` SAME RecursionError.
`git diff --stat 02b6d07 f4ba545`: TODO.md, review-log.md and test_review_2026_11_10.py only, so the runtime is the decision's.
review/q47/facts/f7.py (CPython, sys.setprofile): `{'first import from the directory': (10, '_path_stat'), 'second import from the directory': (9, '_path_isabs')}`; review/q47/p1 `depth first`: ok to 69 against 73.
`gh api -X GET search/code -f q='<name> language:Python' --jq .total_count` on 2026-11-26: _ModuleLock 6528, _blocking_on 7168, _module_locks 5640, _get_module_lock 5552; `_get_module_lock filename:_bootstrap.py` 4096; outside _bootstrap.py and test_locks.py 98, of which the first 30 are copies under other names (Brython, RustPython, pyqtdeploy) and one reimplementation (pipelime). gevent's _patch_thread_common.py:57-93 reads importlib._bootstrap._ModuleLock, as the entry says.

Probe: review/q47/p2, rows depth 64..76; review/q47/p1, rows depth first *

Suggested: Correct 72 to 73 in the entry and say which import the 10 belongs to; give the GitHub figures as what one search showed, not as file counts.

> Verifier: **confirmed** (low). docs/DECISIONS.md:1954 (Question 47) says a recursion with an import at its bottom reaches 68 levels under a limit of 80 against 72 compiled. At f4ba545 CPython's 68 holds, compiled reaches 73 (difference 5, not 4). The 10 frames below _find_and_load belong to the first import from a directory (the second goes 9). The GitHub counts (_ModuleLock 2,660, _get_module_lock 45, mostly copies of _bootstrap.py) cannot be one index, since every copy holds both names. The conclusion stands; the figures appear only in this entry.

### F48-q47-7 (RL-1030): Four places where D-33's words are not exact

*words, reported as low*; where: docs/dialect-spec.md:245; docs/deviations.toml:211 and :215

(1) 'Twice when CPython takes the lock': once, with an __eq__, when a live lock exists. (2) The lock goes 'after the import; after a module's body raised': a module not found through importlib.__import__ also keeps its lock until the exception is released. (3) The names 'stop the program': for a read. A deletion raises a catchable AttributeError where CPython deletes, and that is the stop's general gap (a not-yet name and two names of sys do the same), recorded nowhere. (4) A write of the names is taken and never used: a replaced _get_module_lock or _lock_unlock_module is called by CPython's import and never compiled (E-04 in spirit, not in its words).

Evidence: review/q47/p1/out.txt, CPython's side. `calls raise-again`, the second import: `hash raising in _get_module_lock:438 held=True`, `eq raising==raising in _get_module_lock:438 held=True`, no :459 and no cb. `calls missing-importlib`: `after the except clause, the exception kept 0`, then `released 2` with `hash nosuch_q47 in cb:454`, `cb:455`; `calls missing` (the builtin): both inside `raised ModuleNotFoundError 12`.
review/q47/p2: `del lock` CPython `deleted _module_locks`, compiled `AttributeError: 'module' object has no attribute '_module_locks'`, status 0; `del notyet` the same for _verbose_message; review/q47/p4: `del displayhook` and `del _git` on sys the same; `del maxsize` SAME.
p2 `set getlock`: CPython `a first import: 3 ['_get_module_lock(sample)', 'acquire', 'release']`, compiled `0 []`; `set lul`: CPython `a module that imports itself: 1 ['_lock_unlock_module(selfimp)']`, compiled `0 []`.
The register's 'three times' for __eq__: facts/f6.py gives 3 for a body `import pk3.sub`; p1 `calls pkg` (`from pk import sub`) gives 4.

Probe: review/q47/p1, rows calls raise-again, calls missing-importlib, calls missing, calls pkg; review/q47/p2, rows del *, set *; review/q47/p4, rows del *

Suggested: Reword clauses (1) and (2); for (3) open a log row on deleting a name the runtime lacks (stop, as a read does); for (4) one clause in D-33 or E-04.

> Verifier: **confirmed** (low). All four word-level points hold. (1) 'twice when CPython takes the lock' (dialect-spec:245, deviations.toml:211) is right for a fresh lock (hash at _get_module_lock:438 and :459), but a live lock gives one hash and one __eq__ (raise-again, second import). (2) A module not found through importlib.__import__ keeps its lock until the exception is released: cb:454/455 come after KEPT.clear(); compiled releases 0. The quoted 'after the import; after a module's body raised' is in both files. (3) The spec says 'stops the program' (the finding's 'stop the program' is inflected), and deleting a name th ...

### F48-q47-8 (RL-1031): Three records beside the decision are stale or wrong (TODO's item, RL-950, RL-955)

*inconsistency, reported as low*; where: TODO.md:840-844 and :857-862; docs/reviews/review-log.md:1362 (RL-950) and :1367 (RL-955)

TODO's done item and RL-950 say D-17's clause was narrowed to what the import system enters and leaves before a module's body runs, locks included: the draft W47 showed wrong, against the committed clause. RL-950 says _find_and_load takes _ModuleLockManager(name) at line 1339; that line is `lock = _get_module_lock(name)`, and _ModuleLockManager is used only by _exec (821) and _load (886), which neither D-33 nor TODO's port list names. RL-955 and TODO say the compiled program hashes the name in none of three functions, for a spec made with an exact str; it hashes in _load_unlocked as CPython does and the spec's name is the subclass.

Evidence: TODO.md:841-842: "D-17's import clause narrowed to what CPython's import system enters and leaves before a module's body runs (its path finder, its module locks, its reading of the code)"; dialect-spec.md:232: "its module locks, which also run when an import finds its module initialising and when a lock goes (D-33)".
review-log.md:1362: "`_find_and_load` takes `_ModuleLockManager(name)` (`_bootstrap.py:1339`)"; the pinned file, line 1339: `            lock = _get_module_lock(name)`; grep _ModuleLockManager there: 413 (the class), 821, 886.
review-log.md:1367: "CPython hashes the name in `_init_module_attrs` twice, `_load_unlocked` three times and `_find_and_load_unlocked` once after the spec is found; compiled in none of them"; TODO.md:860: "compiled `__hash__` 4".
review/q47/p1, `calls plain`, compiled: `__import__ 8`, among them `hash sample in _load_unlocked:850 held=False`, `:868`, `:869`; its last line is `42 S S` on both sides (the types of m.__name__ and m.__spec__.name). Missing compiled are only `_init_module_attrs:761`, `:770` and `_find_and_load_unlocked:1263` (and the finder's and the locks').

Probe: review/q47/p1, row calls plain

Suggested: Correct the three rows; RL-955's matters most, since TODO tells its fix to start from that description.

> Verifier: **confirmed** (low). The quotations are in TODO:841-842, dialect-spec:232, RL-950 (1362) and RL-955 (1367). RL-950's line 1339 is `lock = _get_module_lock(name)` inside _find_and_load (def at 1302); _ModuleLockManager is used in code only at 821 (_exec) and 886 (_load), so the claim stands. The finding's grep list omits the comment at 339, so it names 3 hits where grep gives 4. RL-955's 'compiled in none of them' is wrong for _load_unlocked: compiled hashes sample at 850, 868 and 869, as CPython does; the spec's name is S on both sides ('42 S S'). Missing compiled hashes are 761, 770, 1263 plus the finder and lock ...

Minor, one line each, not verified:

- REPORT.md was not written: the harness refused the file (reports are to be returned as text). The full account is this answer; every probe folder under review/q47 (p1 to p6, facts, cpython-src, github) keeps prog.py, rows.txt and the wrapper's out.txt.
- The committed D-33 row is about three times the draft the author answered 'C please' to. The entry says so; nothing records that the author read the final row (the spec's words are the author's).
- TODO's item for B names __import__ calling _lock_unlock_module; PyImport_GetModule calls it too (Python/import.c:370 of v3.15.2; the runtime's get_initialized_module, imports.cpp:149). When _setup binds _thread and _weakref, D-30's list of the start's modules changes.
- For RL-955's sweep, not the locks: __lazy_import__(S, globals()) hashes the name twice under CPython and once compiled when the lazy object is made (p1, calls lazy); CPython hashes a package's name at _handle_fromlist:1414 and the compiled program does not (p1, calls pkg).
- Outside Question 47, from p6: property, staticmethod and types.GenericAlias answer __subclasses__() with [] where CPython lists abc.abstractproperty, abc.abstractstaticmethod and collections.abc._CallableGenericAlias, classes of modules its start imports. D-30 covers it in substance; its words name only sys.modules.
- By-product of p5, outside Question 47: an instance of a program's own class costs 7.4 microseconds compiled against 0.34 under CPython on this host, a call of a program's function 0.80 against 0.23.
- D-33's clause on a signal handler's exception inside a weakref callback was not run again: it needs timing, and W47's programs are not kept.

Covered: Verdict: the decision is sound and nothing found changes the answer; C is the right option of the three. Facts: every measurement of the entry (DECISIONS.md:1954-1960) run again under CPython 3.15.2 (the hash row, _ModuleLock, the two code objects, 68 levels, 12 calls and 6 by sys.setprofile, 10 and 4 frames, the local-code search); all hold but the compiled 72 and the GitHub counts (finding 6). _bootstrap.py's cited lines read in the pinned stdlib; Python/import.c of v3.15.2 fetched and read; GitHub counts by the REST search and two public files read. Words: every clause of the D-33 row and of D-17's import clause on both sides in review/q47/p1 (308 rows, 227 SAME, 81 DIFF, each DIFF read): all 63 names of CPython's _bootstrap (exactly the fourteen stop with D-33's words, eight others with 'not yet'), eight routes to a name, fifteen import shapes with a logging str subclass (each call with its caller, line and lock_held: the only CPython-only callers besides RL-954's and RL-955's are _get_module_lock and cb, and compiled never sees lock_held true), _lock_unlock_module with eight arguments, twelve code-object fields of eleven functions (only co_nlocals and co_varnames of the two differ), and the recursion reach under a limit of 80 for eleven import shapes (a built-in module agrees, 72 and 72; an import that finds its module initialising is 68 against 73). The hunt for unlisted traces: p2 (replaced functions of _thread, _weakref, _imp; deletions; writes) and p6, p4 (__subclasses__). Options: p3 (B's text runs unchanged), p5 (what it costs). The spec row against the register (identical), v0.42's entry, absent_name and ABSENT_BY_ENTRY, the test and the A46 test's LOCKS, TODO's three items, design.md's paragraph, RL-948 to RL-957, D-30, D-25, E-02, E-04 to E-06. Six builds used, all through r48_both.py; no tracked file of the checkout was touched.

Not covered: No test of the repository was run (test_module_locks.py, the A46 test, C-8, C-9): what they hold was judged by reading and by my own rows. A signal handler's exception inside a lock callback (timing). Whether CPython's lock text runs inside the bootstrap prelude at start; p3 runs it as a module of a program. The chat in which the question was put: the record of the recommendation and of 'C please' is DECISIONS' own. GitHub's web code search, which may be where the entry's counts came from; the profiler 'muru' was not looked up. Fidelity lean, and anything with threads. RL-954, RL-955 and RL-957 themselves and Question 48's evidence in the W47 document. Timings are from a shared host under load: the ratios are robust, the absolute figures are not. REPORT.md does not exist (see minor).


## q48: Question 48

### F48-q48-1 (RL-1032): D-34's set is not 25: eight more code objects differ the same way, and "149 code objects, 27 differ" is false

*words, reported as high*; where: draft D-34 (the count and both lists); Question 48's background sentence; runtime/prelude/bootstrap.py:1405-1574; docs/reviews/review-log.md RL-948; docs/DECISIONS.md 2026-11-25 "The code objects (RL-948, in part)"; TODO.md:845-846

The loader classes _LoaderBasics, SourceLoader, FileLoader and SourceFileLoader are defined in bootstrap.py but belong to _frozen_importlib_external, where a program reaches them (importlib.machinery.SourceFileLoader, any module's __loader__). Reached there, eight more code objects have the runtime's co_nlocals and co_varnames: _LoaderBasics.exec_module (it runs) and seven that refuse: SourceLoader.get_source, .get_code, FileLoader.get_data, .get_resource_reader (the function under @_check_name), SourceFileLoader.path_stats, ._cache_bytecode, .set_data. So 33, not 25. And 20 of the question's "149 code objects" are lines that say <absent> on both sides: 129 were compared.

Evidence: review/q48/p1 (r48_both.py, 238 rows), rows `code E <name>`, CPython -> compiled: SourceLoader.get_code co_nlocals 15 -> 2, co_varnames ('self','fullname','source_path','source_mtime','source_bytes','source_hash','hash_based','check_source','bytecode_path','st','data','exc_details','flags','bytes_data','code_object') -> ('self','fullname'); SourceLoader.get_source 5 -> 2; FileLoader.get_data 3 -> 2; SourceFileLoader.path_stats 3 -> 2, ._cache_bytecode 5 -> 4, .set_data 9 -> 4; _LoaderBasics.exec_module 3 -> 2 ('code' gone); FileLoader.get_resource_reader.cell0 3 -> 2 ('FileReader' gone). review/q48/p3 row `natural` gives the same through type(helper.__loader__). Whole sweep (p1/code_summary.txt): 180 rows = every function and class member of CPython's two modules, reached where CPython has it; 33 stop by name (25 of D-33, 8 "not yet"), 98 SAME, 49 differ = 2 locks + the question's 27 + 19 loader methods + 1 (an address in a repr). For the 25 themselves: 675 attribute lines compared; differing: co_varnames 25, co_nlocals 24, co_argcount 1 and signature 1 (both _setup), nothing else. So "exactly these attributes" holds for the 25 (PathFinder.discover's co_nlocals agrees), and "exactly these 25" does not.

Probe: review/q48/p1 rows `code E SourceLoader.get_code`, `code E FileLoader.get_data` and the like (p1/code_summary.txt); review/q48/p3 row `natural`

Suggested: Recount with each function reached in the module CPython defines it in; list the eight in D-34 (27 refused, 6 that run) or fix them; correct "149" in RL-948, the DECISIONS entry and TODO.md.

> Verifier: **confirmed** (medium). The A46 sweep looks up 20 of its names in _bootstrap, where CPython has none of them (the source loaders, _check_name and others live in _bootstrap_external), and compares <absent> with <absent>. So 129 code objects are compared, not 149. Reached where CPython has them, 36 of 148 differ (not 29), plus one wrapped function. Seven methods are in neither LOCKS nor REWRITTEN: FileLoader.get_data, SourceFileLoader._cache_bytecode/path_stats/set_data, SourceLoader.get_code/get_source, _LoaderBasics.exec_module. The eighth is the function under FileLoader.get_resource_reader. Question 48's 27 is 35 a ... Cover: None for these functions: RL-948 'Partly fixed' lists the 27 by group without them. The class is known: RL-948 and TODO.md:845 'Question 48'. Question 48 is unanswered in the repo at f4ba545.

### F48-q48-2 (RL-1033): The import system's primitives dereference a module name that is not a str: SIGSEGV where CPython raises or returns

*defect, reported as high*; where: runtime/src/imports.cpp:304-305, 523-524, 1421, 1426; runtime/src/core.cpp:589; runtime/prelude/_imp.py:183; runtime/prelude/bootstrap.py:72, 434, 443-446, 628, 1429, 1590

as_str returns nullptr unless given a str, and the primitives the import preludes call use it unchecked. A module name that is not a str ends a compiled program with SIGSEGV where CPython raises TypeError or ImportError, or returns: _find_spec and FrozenImporter.exec_module (two of D-34's five), BuiltinImporter's find_spec, is_package, get_code, get_source and create_module, importlib.util.spec_from_loader (CPython returns a spec) and module_from_spec. _imp.create_builtin hands the primitive the spec where it takes a name, so it crashes for every spec, a valid ModuleSpec included. Older than the range (lines of 2026-11-04 and 11-09); not in the review log or TODO.

Evidence: review/q48/p4: 22 entry points x 9 kinds of name (int, None, bytes, float, list, tuple, two str subclasses, str), a row a process, 198 rows. CPython never crashes; compiled 68 rows end with status -11. E.g. `builtin.find_spec int`: CPython "raised TypeError", compiled status -11 with no result line; `builtin.is_package none`: CPython "raised ImportError"; `spec_from_loader int`: CPython "returns True"; `_imp.create_builtin str` (SimpleNamespace(name='sys')): CPython "returns 'module'", compiled -11. review/q48/p5 `create_builtin_modulespec` (ModuleSpec('sys', BuiltinImporter, origin='built-in')): CPython "returns module", compiled -11; `builtin_find_spec_none`: CPython "raised TypeError is_builtin() argument must be str, not None", compiled -11. review/q48/p3 `tb findspec2` (_bootstrap._find_spec(7, None)): compiled -11. coredumpctl info of one run: "#0 bella::i_bella_is_builtin ... #4 bella::prelude_bootstrap::f_BuiltinImporter_find_spec". imports.cpp:1421: `const std::string& name = as_str(a.pos(0))->text;`; core.cpp:589: `if (!v.is_object() || v.object()->kind != Kind::Str) return nullptr;`; _imp.py:183: `return _bella_create_builtin(spec)`.

Probe: review/q48/p4 (rows.txt, out.txt); review/q48/p5 rows create_builtin_modulespec, builtin_find_spec_none; review/q48/p3 row `tb findspec2`

Suggested: Fix: raise what CPython's C raises, and pass spec.name in _imp.create_builtin. Sweep every `as_str(a.pos(i))->` of runtime/src as a class (22 in imports.cpp) and keep p4's sweep as a test.

> Verifier: **confirmed** (high). i_bella_is_builtin, i_bella_create_builtin, _bella_find and _bella_exec dereference as_str(a.pos(0))->text unchecked (as_str returns nullptr for a non-str). With an int, None or bytes name, BuiltinImporter.find_spec, is_package, get_code, get_source and create_module, FrozenImporter.exec_module, _bootstrap._find_spec and importlib.util.spec_from_loader(7, BuiltinImporter) end with SIGSEGV where CPython raises TypeError or ImportError, or returns a spec. _imp.create_builtin passes the spec where the primitive takes a name, so it crashes for every spec, a valid ModuleSpec('sys', ...) included. A ... Cover: None for the crash. grep of review-log, DECISIONS, TODO and deviations.toml finds nothing on non-str module names in the import primitives. The 50 names: DECISIONS 2026-11-06 says importing one the runtime lacks 'stops by name', which does not cover the importer's ImportError/None answers; D-20 does ...

### F48-q48-3 (RL-1034): "The functions cannot run in a closed world" is false for at least three of the twenty, and the option that fits them was not put

*unsound-recommendation, reported as medium*; where: Question 48's recommendation and options A-C; draft D-34's first sentence; runtime/prelude/bootstrap_external.py:157-161, 470-492; TODO.md:850-852 (the options planned)

The reason given for A, "the functions cannot run in a closed world" (the draft: "cannot do in a closed world what CPython's text does"), is false for at least three of the twenty. CPython's own text of WindowsRegistryFinder.find_spec and ._search_registry (with ._open_registry) and of _write_atomic, compiled unchanged, does what CPython does and has CPython's code objects; today they stop the program where CPython raises a catchable NameError or writes the file. The option that fits, CPython's text where it runs as it is (A46's own fix for _make_relax_case; listed in TODO.md), was not put: B was that text behind a refusal. A stands for the rest. B's "about 370 lines" is the whole text (367); 79 are there already.

Evidence: review/q48/p3: cptext.py holds Lib/importlib/_bootstrap_external.py:200-219 and 672-727 verbatim, as a module of the program. Rows `wrf search`, `wrf open`, `atomic write`, `atomic nodir`, `atomic ontodir`: SAME (NameError; "returns None / b'data' / left behind []"; FileNotFoundError; IsADirectoryError). `wrf find_spec`: both sides "raised NameError name 'winreg' is not defined" and the DeprecationWarning (DIFF only in the warning's file name: the script's full path against prog.py). `wrf code` and `atomic code`, compiled: the copied text "_search_registry 2 6 ('cls','fullname','registry_key','key','hkey','filepath')", "find_spec 4 8 (...)", "3 6 ('path','data','mode','path_tmp','fd','file')"; the import system's own in the same binary "2 2 ('cls','fullname')", "4 4", "3 3". review/q48/p1 `stop 9`, `stop 10`, `stop 14`: compiled exit 70; CPython NameError, NameError, and "None / b'data'". static/lines.py: the twenty are 367 lines in CPython's text, 79 in the prelude, difference 288. Caveat: measured as a program's module (winreg bound in a branch that never runs, _os = posix imported at its top), not inside the prelude.

Probe: review/q48/p3 rows `wrf *`, `atomic *`; review/q48/p1 rows `stop 9`, `stop 10`, `stop 14`

Suggested: Put the narrower cut to the author: CPython's text for the functions where it runs as it is, D-34 for the rest; drop "cannot" from the entry. Look at the three bytecode functions the same way when marshal lands.

> Verifier: **confirmed** (medium). 'Cannot run in a closed world' is false for WindowsRegistryFinder.find_spec and ._search_registry: CPython's own text runs as it is (NameError 'winreg', DeprecationWarning first) with CPython's code objects. It is refused by choice. _write_atomic runs too, but needs _os, which the prelude does not bind (compiled _bootstrap_external._os stops 'the runtime does not yet'), so there it depends on binding _os at start (D-30). The 367-line vs 79-line counts are right. The draft D-34 and the question's options are not in the repo, so those words could not be checked. The finding's measurement is of a ... Cover: The principle is known: TODO.md:845-855 lists 'CPython's text where it can run' as an option and applies it to cache_from_source/source_from_cache; RL-948 did the same for _make_relax_case. Its application to these three is not recorded, and no D-nn names them.

### F48-q48-4 (RL-1090, with the same subject): __globals__ of the nineteen methods of the four loader classes is the other module's namespace

*words, reported as medium*; where: runtime/prelude/bootstrap.py:1405-1582; docs/dialect-spec.md section 3, row "Functions, reflection" ([P1] for __globals__ and __closure__); draft D-34

__globals__ is [P1]. The 19 methods of _LoaderBasics, SourceLoader, FileLoader and SourceFileLoader have _frozen_importlib's namespace as __globals__, where CPython's have _frozen_importlib_external's. The two functions under @_check_name (FileLoader.get_filename and .get_resource_reader, in __closure__[0]) also say __module__ == '_frozen_importlib': the loop at bootstrap.py:1578 sets the wrappers' only. Nothing registered covers either, the draft does not say it, and the A46 sweep looks at neither attribute.

Evidence: review/q48/p3 row `globals`: for each of the 19, "module's own globals:" (f.__globals__ is importlib._bootstrap_external.cache_from_source.__globals__) is True under CPython and False compiled, and "SOURCE_SUFFIXES in them:" True and False; the methods of SourcelessFileLoader, ExtensionFileLoader, PathFinder and FileFinder say True on both sides. review/q48/p1 rows `code E FileLoader.get_data` and the like: "__globals__.__name__ importlib._bootstrap_external" against "importlib._bootstrap" (21 lines: 19 methods and 2 cells); "FileLoader.get_filename.cell0 __module__ '_frozen_importlib_external'" against "'_frozen_importlib'", the same for FileLoader.get_resource_reader.cell0. p3 row `natural`: "get_resource_reader's own function 2 3 (...) _frozen_importlib_external" against "2 2 ('self', 'module') ... _frozen_importlib".

Probe: review/q48/p3 rows `globals`, `natural`; review/q48/p1 rows `code E FileLoader.*`, `code E SourceLoader.*`

Suggested: Fix (make the classes in the module they belong to; set the wrapped functions' __module__) or name it in D-34. Ask the author which.

> Verifier: **confirmed** (high). The 19 methods of _LoaderBasics, SourceLoader, FileLoader and SourceFileLoader have _frozen_importlib's namespace as __globals__ (CPython: _frozen_importlib_external's); the two functions in FileLoader.get_filename and get_resource_reader's _check_name cells also say __module__ '_frozen_importlib' (the loop at bootstrap.py:1578 sets the wrappers' only). __globals__ is [P1] (spec section 3); nothing registered or queued covers it. D-34's draft is not in the repo at f4ba545, so what it omits could not be read.

### F48-q48-5 (RL-1035): "(E-04)" is the reason of nine of the twenty, and "twenty stop when called" is not the list of what stops

*words, reported as medium*; where: draft D-34, "twenty stop the program when called (E-04)"; runtime/prelude/bootstrap_external.py and bootstrap.py, every _bella_refuse

By the stops' own messages E-04 is the reason of nine; four say E-02 (bytecode); seven say neither (importlib.metadata outside the manifest, importlib.resources [P2+], the Windows registry twice, extension modules twice, "writes no bytecode"). The sentence also reads as the list of what a closed world does without, and it is not: 34 functions of the two preludes refuse outright, 15 of them outside the twenty (the seven of finding 1 and eight whose code objects happen to agree, such as _path_stat, ExtensionFileLoader.exec_module, NamespaceLoader.get_code). The bare `_install` is ambiguous: CPython has one in each module, and _frozen_importlib's is absent here with "not yet".

Evidence: review/q48/p1 rows `stop 1` to `stop 20`, compiled standard error, all exit 70: "PathFinder.find_spec (a path finder's search: the closed world is resolved at build time, E-04)"; "the import system's _compile_bytecode (bytecode: a compiled program has none, E-02)"; "PathFinder.find_distributions (importlib.metadata is outside the phase-1 manifest)"; "NamespaceLoader.get_resource_reader (importlib.resources is [P2+])"; "WindowsRegistryFinder (the Windows registry: the targets are posix)"; "ExtensionFileLoader.create_module (an extension module: a compiled program has none)"; "the import system's _write_atomic (a compiled program writes no bytecode)". Rows `stop 21` to `stop 28`: eight more refusals outside the list, exit 70. Row `code B _install`: "not implemented: _frozen_importlib._install (CPython has it; the runtime does not yet)". Row `stop 8` (FileFinder._find_children) prints "made generator" before the stop: it stops at the first next, not at the call. AST count of _bella_refuse: bootstrap.py 12 functions, bootstrap_external.py 22 outright and 3 in part.

Probe: review/q48/p1 rows `stop 1` to `stop 28`, `code B _install`

Suggested: Define the set as the functions whose code objects differ, name each with its module, and give each group its own reason, as the stops do.

> Verifier: **confirmed** (medium). Of the twenty refusals nine cite E-04, four E-02, seven neither (metadata outside manifest, resources [P2+], registry x2, extension modules x2, no bytecode written); 15 further functions of the two preludes refuse outside the twenty; FileFinder._find_children stops at the first next, not at the call; bare _install is ambiguous (_frozen_importlib._install is absent with 'not yet'). The draft's sentence is not in the repo at f4ba545, so only the facts are verified; E-04's row names neither bytecode, the registry nor extension modules.

### F48-q48-6 (RL-1032, with the same subject): The A46 sweep compares <absent> with <absent> for 20 of its 149 lines, and holds no co_flags

*test, reported as medium*; where: pipeline/tests/test_review_2026_11_25_a46.py:16, 69-73, 100; pipeline/tests/review_a46/codeobjects/prog.txt:7-8, 36, 43

The sweep looks up a name of the table under bootstrap.py in _bootstrap. 23 of its 150 names are of the loader classes and helpers CPython has only in _bootstrap_external, and neither side finds them in _bootstrap: 20 print <absent> on both sides and 3 print nothing. The test compares 129 code objects, not 149, and passes whatever those 23 are; its docstring says every function the table names is reached by name on both sides. ATTRS also lacks co_flags, which E-02 lists among the [P1] names and counts (my sweep found no co_flags difference in 147 rows). D-34 would be held by this test.

Evidence: review/q48/a46_cpython: the test's own program with NAMES written as table_names() writes them, built and run on both sides, row `all`: "lines: CPython 149 compiled 149"; "<absent> lines: CPython 20 compiled 20 the same names: True"; "code objects compared: 129"; "differ: 29" (exactly OPEN). Absent on both sides: _bootstrap.SourceLoader.get_code, .get_source, .path_mtime, .path_stats, .set_data, .source_to_code, ._cache_bytecode; _bootstrap.FileLoader.get_data, .get_filename, .get_resource_reader; _bootstrap.SourceFileLoader._cache_bytecode, .path_stats, .set_data; _bootstrap._LoaderBasics.create_module, .exec_module, .is_package; _bootstrap._check_name, ._get_cached, ._path_split, .cache_from_source. Silent on both: FileLoader.__init__, __eq__, __hash__ (getattr(None, '__eq__', None) is a method wrapper without __code__). prog.txt:36 `obj = getattr(obj, part, None)`, :43 `elif obj is None: print(where, "<absent>")`. review/q48/p3 row `absent`: each of the eight names "in _bootstrap: False in _bootstrap_external: True", SAME on both sides.

Probe: review/q48/a46_cpython row `all`; review/q48/p3 row `absent`

Suggested: Reach each name in the module CPython defines it in (the table's file says which), fail when both sides say <absent>, add co_flags. OPEN then grows by seven, eight with the function under the decorator.

### F48-q48-7 (RL-1036): What a program sees of the five that run, which "do the closed world's part of it" does not say

*words, reported as medium*; where: draft D-34, the clause on the five and the last sentence; runtime/prelude/bootstrap.py:626-628, 1609-1622, 1934; runtime/prelude/bootstrap_external.py:690-704; RL-957

invalidate_caches: PathFinder.invalidate_caches() called directly shows it too; sys.modules lacks 42 modules, not one; D-20 does not cover it (with the module not installed CPython's call raises ModuleNotFoundError; here it returns None). _find_spec uses `path` for the built-in finder only. FrozenImporter.exec_module runs a module CPython does not hold frozen (CPython: ImportError), and a traceback through it says line 1092 for CPython's 1093: its missing `spec` is the prelude's doing, since CPython's two lines run as they are. discover's co_nlocals is CPython's. Three of _setup's missing locals return with D-33's B, so "permanent" is not so for them.

Evidence: review/q48/p1 `inv` and `invpf`: CPython "importlib.metadata in sys.modules True / new modules 42" (re, typing, collections, enum, functools, ast, pathlib, email and others), compiled "False / new modules 0". CPython alone with sys.modules['importlib.metadata'] = None, then importlib.invalidate_caches(): "ModuleNotFoundError import of importlib.metadata halted; None in sys.modules". p1 `rawspec helper missing` (_find_spec('helper', ['/nonexistent-directory-q48'])): CPython "None", compiled "name='helper' loader=SourceFileLoader origin='helper.py' ..."; `rawspec sub pkg`: CPython a spec named 'sub', compiled "None". review/q48/p5 `frozen_exec_helper`: CPython "raised ImportError No such frozen object named 'helper'", compiled "helper body runs / returns None VALUE 41". review/q48/p3 `tb fexec`: CPython "<frozen importlib._bootstrap> line 1093 in exec_module", compiled "line 1092"; bootstrap.py:626 `name = module.__spec__.name`, CPython's 1092-1093 `spec = module.__spec__` / `name = spec.name`. p1 `code E PathFinder.discover`: only co_varnames differs. p1 `setup` (_setup(sys, _imp)): CPython AssertionError, compiled "TypeError _setup() takes 1 positional argument but 2 were given".

Probe: review/q48/p1 rows inv, invpf, rawspec *, setup, `code E PathFinder.discover`; review/q48/p5 row frozen_exec_helper; review/q48/p3 row `tb fexec`

Suggested: Say per function what differs beyond the names, or point to the entry that covers it (E-04, D-16, the decision of 2026-11-12). Give FrozenImporter.exec_module CPython's first two lines; ask the author whether it refuses a module that is not frozen.

> Verifier: **confirmed** (medium). Partly known, partly covered, partly new. invalidate_caches omission is RL-957 (Open) but its cover D-20 is wrong (a not-installed module would make CPython raise ModuleNotFoundError; compiled returns None) and it is also seen via PathFinder.invalidate_caches() and 42-45 missing modules. _find_spec ignoring path is by design (E-04, registry decision 2026-11-03). New: FrozenImporter.exec_module runs a compiled non-frozen module where CPython raises ImportError, and traceback line 1092 vs CPython 1093 (prelude merges two lines; fixable). discover's co_nlocals is CPython's (only co_varnames diffe ... Cover: RL-957 (review-log.md:1369, Open, 'with Question 48') for invalidate_caches; DECISIONS 2026-11-03 'The closed world's registry stands for sys.meta_path' and E-04 for _find_spec's path; DECISIONS.md:1958 'B with the threads milestone ... _setup binding _thread and _weakref' for three of _setup's loca ...

Minor, one line each, not verified:

- Side effect on the host: the crashing rows of p3, p4 and p5 (about 75 runs) each left a core file of about 1.3 MB with systemd-coredump under /var/lib/systemd/coredump, owned by root; I could not remove them.
- A sketch of words that would be true (the text is the author's): define the set as the functions of the two modules whose co_varnames after the parameters, and so co_nlocals, are not CPython's; name each with its module, in groups with their own reasons; six run (the five and _LoaderBasics.exec_module); N is 33 as things stand, 30 if the three of finding 3 become CPython's text; state the lint status (partial: a read of __code__, __globals__ or __closure__ of a name taken from importlib.machinery or the two bootstrap modules, not one reached through __loader__).
- RL-957 cites Lib/importlib/_bootstrap_external.py:1198-1200; the two lines are 1199 and 1200 (1198 is blank). Its "(D-20)" is the reason for the omission, not a cover: see finding 7.
- The question says the difference under A is permanent. FileLoader.get_data and SourceLoader.get_source stop with "step 3b: reading files", so they are waiting for work, not registered for good.
- PathFinder.discover lists the program's modules that lie in a sys.path entry, and a compiled sys.path is the script's directory alone (p3 row `syspath`): 3 specs against CPython's 221 (p1 row `discover top`). Decided on 2026-11-12 in DECISIONS; section 11 of the spec does not have it.
- importlib.util.find_spec of a standard-library module the program does not import stops ("importing 'colorsys' (the standard library: step 3b)", p5), where the idiom `find_spec(name) is not None` expects an answer. An honest stop, not a finding; D-34's "does the closed world's part" should not read as if it returned None.
- Stop messages: _exec's says "importlib.reload" on a direct call too; WindowsRegistryFinder's names no method; every one begins "not implemented", the E-04 and E-02 ones included.
- _setup's co_argcount differs as well (1 for 2); the draft's "takes the one argument" covers it without naming the attribute.
- In p1 the default of spec_from_file_location shows in inspect.signature as an object's address on both sides; it is the only other signature line that differs and is not a difference.

Covered: Verdict on (d): A (register) still stands for most of the set, but the draft is neither true nor complete as written; findings 1 and 3 to 7 are its defects, and finding 2 is a crash found on the way.

Read: the question as put (in the session's record: background, sample table, evidence, options A to C, the recommendation; recommended A, answered A, the record is straight), TODO.md's entry and commit 434dfec, RL-948, RL-957, the DECISIONS entries of 2026-11-25, E-02, E-04, D-16, D-20, D-30, D-33 in the spec and docs/deviations.toml, the decision of 2026-11-12 on discovery, C-8-13, the A46 test and its probe, both preludes against the pinned interpreter's own Lib/importlib/_bootstrap.py and _bootstrap_external.py, runtime/src/imports.cpp for the primitives, and the recorded local evidence in docs/reviews/2026-11-25-claude-workflow-47-review.md.

Static, CPython only (review/q48/static): both preludes compiled by CPython's compiler and compared by qualified name with CPython's text; line counts of the twenty; an AST count of the functions that refuse.

Compiled, five builds of twelve, a row a process on both sides: p1 (238 rows: 180 code rows over every function and class member of CPython's two modules with every [P1] attribute of the code object and the function, closures followed, inspect.signature; invalidate_caches twice; 11 find_spec, 9 _find_spec, 3 discover, 3 FrozenImporter.exec_module, a loader's exec_module, _setup; 28 stops); a46_cpython (the A46 test's own sweep); p3 (17 rows: CPython's text of four refused functions compiled, __globals__ by identity, the loaders through __loader__, sys.path, tracebacks through three of the five); p4 (198 rows: 22 import entry points with 9 kinds of name); p5 (9 confirmations).

What holds: for the 25 the differing [P1] attributes are exactly co_varnames (25), co_nlocals (24) and _setup's co_argcount and signature; all twenty stop with exit 70 and the five run; inspect.signature agrees but for _setup; RL-957 reproduces; the local part of the evidence agrees with my grep of Lib and .venv for co_nlocals and co_varnames (dis, inspect's argument prefix, pdb, mock's write; execnet, pluggy, hypothesis).

Not covered: REPORT.md does not exist: the harness's Write tool refused it ("Subagents should return findings as text, not write report files"), and I did not go around the refusal. The full account is this output; every probe, its rows and both sides' output are under review/q48/ (p1/out.txt and p1/code_summary.txt, a46_cpython/out.txt, p3/out.txt, p4/out.txt, p5/out.txt, static/, gen_rows.py, parse_out.py, show_rows.py).

The GitHub part (31 code searches) and the PyPI part (34 packages) of the evidence were not repeated. The evidence was counted for the question's 27 names; for the eight more of finding 1 nothing was counted, by me either.

Option C's cost (changes to the frames tool, the frontend and the backend) was not checked against the frontend or backend.

Not compiled: CPython's text of the three bytecode functions, SourcelessFileLoader.get_code, the two extension loaders and the eight of finding 1 (marshal and reading files are not there yet). Whether CPython's WindowsRegistryFinder and _write_atomic compile inside the prelude, as opposed to a program's module, was not measured: the checkout is read-only.

Of the crash class only the four primitives the import preludes call with a program's argument were run; the other `as_str(a.pos(i))->` sites of runtime/src were not.

Not looked at: fidelity lean, aarch64, nested functions reached only by a call beyond FileFinder.path_hook's hook.

D-34's committed words, its deviations.toml entry, the spec's version entry and the DECISIONS entry do not exist at f4ba545 (TODO.md still says "put to the author"), so follow-through and the lint status could not be checked; the draft gives no lint status.


## c01-classes-counted: classes as counted objects (756222f)

### F48-c01-classes-counted-1 (RL-1037): fromhex on a bytes/bytearray subclass returns the base type and skips the subclass constructor

*defect, reported as high*; where: runtime/src/bytes.cpp fromhex_m (last line); probe q1 row fromhex; p8 fromhex; p6/p7 bytes and bytearray rows

B1.fromhex, B2.fromhex and B3.fromhex (subclasses of bytes, bytearray, bytes with a printing __new__) all return exact bytes in the compiled program: B2.fromhex is not even a bytearray, B3.__new__ never runs. CPython returns instances of the subclass and calls its constructor. No stop, deviation or log entry covers it.

Evidence: q1 row fromhex. CPython: 'B3.__new__ bytes' then 'B1 B2 B3'. Compiled: 'bytes bytes bytes'. Code: `return cls == Obj::of(types().bytearray) ? new_bytearray(out) : bytes_new(out);`

Probe: q1 fromhex; p8 fromhex

Suggested: Call the subclass with the result when cls is not exactly bytes or bytearray, as CPython does; add a case row.

> Verifier: **confirmed** (high). bytes.fromhex and bytearray.fromhex called on a subclass return the exact base type and never call the subclass's constructor; CPython returns subclass instances and runs B3.__new__. Code: runtime/src/bytes.cpp fromhex_m last line. Nothing registered.

### F48-c01-classes-counted-2 (RL-1070, with the same subject): os.register_at_fork callbacks keep their module's namespace, and what is stored on it, from the exit's finalisation

*defect, reported as high*; where: runtime/prelude/posix.py:1362 (_at_fork list); probes q1 at_fork, p11 at_fork_*, p12 logging_*/random_*/threading_*, p14 fork_local_import, p15 from_import_handler

A finaliser of an object reachable only from a module (or the main module) whose function is registered with os.register_at_fork never runs at the exit. logging, random and threading register at import, so e.g. a logging.Handler subclass with __del__ on the root logger is never finalised. CPython runs it. D-07 says which objects are finalised is CPython's; C-9-13 has no row for it. Files are still flushed.

Evidence: q1 at_fork: global Fin with __del__ writing via os.write, os.register_at_fork(before=hook), print end. CPython: 'end' + 'del of GLOBAL'. Compiled: 'end' only. p12 logging_handler: CPython prints "del of the program's handler", compiled does not. The _at_fork list is a global of a prelude namespace, which DECISIONS 2026-11-24 'The roots' treats as a root.

Probe: q1 at_fork; p12 logging_handler; p14 fork_local_import

Suggested: Make the exit's collection not root the at-fork list (or clear it before the module wipe, as CPython frees it with the interpreter); add a C-9-13 row.

> Verifier: **confirmed** (high). An object reachable only from the namespace of a function registered with os.register_at_fork is never finalised at exit (CPython finalises it). Narrowed: logging's own hooks cause it only when logging is imported inside a function; a module-level import is SAME. Cover: Nearest: DECISIONS 2026-11-23 'The state of a C module that CPython frees with its module stays alive here as a root ... No case reaches it.' It is about C module state, not interpreter state, and its last sentence is now false; no C-9-13 row has register_at_fork.

### F48-c01-classes-counted-3 (RL-1038): A metaclass __del__ assigned after class creation is silently never run; the decision claims a stop

*unsound-recommendation, reported as high*; where: docs/DECISIONS.md 2026-11-24 'A stop' (metaclass with __del__), TODO.md:563; probes q1 meta_del_later, p2 meta_del_later/meta_del_setattr/meta_del_on_base_assigned, p8 late meta

Only a __del__ in the metaclass body stops (type_new). Meta.__del__ = f, setattr(Meta, '__del__', f) or assigning it on the metaclass's base after classes exist runs nothing and does not stop, so the compiled program silently differs.

Evidence: q1 meta_del_later: class Meta(type), class K(metaclass=Meta), Meta.__del__ = lambda cls: print('meta del', cls.__name__), del K, gc.collect(), print end. CPython: 'meta del K' then 'end'. Compiled: 'end'. Body form stops with status 70 (honest).

Probe: q1 meta_del_later; p2 meta_del_later

Suggested: Stop at the assignment of __del__ on a type that is some class's metaclass (or run it); correct the DECISIONS/TODO words.

> Verifier: **confirmed** (high). A metaclass __del__ added by assignment or setattr after classes exist is silently never run and does not stop; only a __del__ present at class creation stops (types.cpp type_new). DECISIONS 'A stop' and TODO.md:563 are true but incomplete. Very rare in practice. Cover: Known only for the body form: DECISIONS 2026-11-24 'A stop. A metaclass of the program's with __del__ ... type_new stops by name' and TODO.md:563; late assignment not recorded anywhere.

### F48-c01-classes-counted-4 (RL-1039): Creating a class with a deep base chain takes 2^depth time

*defect, reported as high*; where: runtime/src/types.cpp:604-627 solid_base/tp_base; probes q1 gens, p7 odd many_generations

solid_base(c) recurses into solid_base(tp_base(c)) while tp_base(c) calls solid_base(b) for each base, doubling the work per level. A chain built at run time by type() or class statements in a function costs about 4x per two classes; 30 classes time out. CPython takes 2 ms for 60. Not introduced by 756222f (code from 2e0b1d3); module-level chains are staged and fast.

Evidence: q1 gens: compiled make-times n=14 0.013 s, 18 0.216 s, 20 0.764 s, 22 3.4 s; rows gens 30 and 60 time out at 120 s; CPython 0.002 s. callgrind at n=14: solid_base and tp_base carry the instructions.

Probe: q1 gens 30

Suggested: Memoise the solid base per class or let solid_base of a single-base class use the base's solid base once; add a depth-60 case.

> Verifier: **confirmed** (high). solid_base(c) (types.cpp:604) recurses into solid_base(tp_base(c)) and tp_base calls solid_base(b) again, so a single-base chain costs 2^depth. Worse than claimed: a 40-deep module-level chain also times out compiled, so 'module-level chains are staged and fast' holds only for shallow ones. Not recorded anywhere. Depths under 15 cost under 50 ms.

### F48-c01-classes-counted-5 (RL-1040): A finaliser's first read of its dying class's __mro__ or __dict__ keeps the class one collection longer

*defect, reported as medium*; where: runtime/src/types.cpp type_mro_attr 1814-1819 (lazy mro_tuple), ClassObject::dict_view; probes q1 mro_in_del, q4, q2, p3 mro, p8 finaliser read_mro/read_getmro/call_singledispatch/read_getattr_static slot, callback read_mro, p9 first *

When a __del__ or weakref callback of an object on a cycle with its class reads type(self).__mro__ (also inspect.getmro, singledispatch dispatch, or sorted(k.__dict__) for a __slots__ class with an inherited __del__) for the first time, the class dies in the second collection in compiled, the first in CPython. Reading __mro__/__dict__ of that class once before the drop makes them agree, so the cause is the tuple/view made lazily after the collector found the class (my reading of the code). Arguably D-04, but RL-929's words say a finaliser's new objects do not keep the class.

Evidence: q4 mro_none. CPython: 'dead after one: True after two: True [2]'. Compiled: 'dead after one: False after two: True [2]'. q4 mro_pre SAME; mro_pre_other_class DIFF. q1 mro_in_del counts 47/0 vs 36/7.

Probe: q4 mro_none; q2 inherited_slots

Suggested: Make the MRO tuple and dict view at class creation (as tp_mro/tp_dict exist), or exclude objects first made in a finaliser from resurrecting a dead class; or record it as part of D-04.

> Verifier: **confirmed** (medium). A __del__ on a cycle with its class that reads type(self).__mro__ for the first time (or __dict__ for a slots subclass with inherited __del__) leaves the class alive after the first gc.collect() compiled and dead in CPython; the lazily made mro_tuple (type_mro_attr, types.cpp:1814) is a new object holding the class. Reading it once beforehand agrees. Arguably D-04's 'different moment', but spec says gc.collect() is complete and RL-929 covers only the exit's path; the words need a decision. Cover: possibly D-04: 'reference cycles are collected at a different moment' (not clearly covering it); RL-929: 'A finaliser's new object does not keep what it holds of a dead class through the collection' (fixed for the exit only)

### F48-c01-classes-counted-6 (RL-1041): Attributes stored on importlib's classes are never finalised at exit; DECISIONS words on immortal classes are wrong for them

*wrong-fact, reported as medium*; where: docs/DECISIONS.md 2026-11-24 'Immortal still'; probes p9 exit modulespec/pathfinder/sourceloader/builtinimporter, p10, p11 ModuleSpec..NamespaceLoader

The entry says immortal runtime classes 'stand for CPython's C types'. importlib's ModuleSpec, PathFinder, FileFinder, loaders are Python heap types in CPython and die at the exit; here a function of the main module hung on one keeps the main module's globals alive, so its finalisers never run. Not covered by D-07 ('which objects are finalised is CPython's').

Evidence: p11 ModuleSpec: global Fin with __del__, importlib.machinery.ModuleSpec.my_hook = hook. CPython: 'end of ModuleSpec' + 'del a global of the main module'. Compiled: 'end of ModuleSpec' only. Same for PathFinder, FileFinder, SourceFileLoader, BuiltinImporter, FrozenImporter, NamespaceLoader.

Probe: p11 ModuleSpec; p10 function_on_pathfinder

Suggested: Correct the words, and either let the exit's collection reach those classes' attributes or register it as a deviation.

> Verifier: **confirmed** (medium). DECISIONS 2026-11-24 'Immortal still' says the runtime's own classes stand for CPython's C types; importlib's ModuleSpec, PathFinder, FileFinder, SourceFileLoader, BuiltinImporter, FrozenImporter and NamespaceLoader are heap types in CPython (flag checked) and die at the exit. Here they are immortal, so a function of the main module stored on one keeps its globals and the finalisers never run. TODO.md:565 records the immortality ('as a C type is') but with the same wrong premise and not this effect; D-07 says which objects are finalised is CPython's. Cover: TODO.md:565 'a class the runtime's own code makes (a prelude's, the bootstrap's) is immortal, as a C type is' (partial: immortality known, premise and effect not)

### F48-c01-classes-counted-7 (RL-1042): The model's __class__-assignment test does not hold the counts

*test, reported as low*; where: refmodel/tests/test_cases.py:1455-1505 (test_an_object_given_a_class_of_its_layout...), refmodel/objects.py set_class ~1003

Removing set_class's incref(cls)/decref(old) (mutation M11), or tp_mro replacement's release of the old MRO (M16), leaves test_cases and selftest (two seeds) green; the test checks values and cache misses, never counts or a collection. Compiled programs stop at both features ([P2+]), so only the model is exposed.

Evidence: review/c01-classes-counted/mut/mutations.txt: M11 and M16 'cases: passes; selftest: passes; selftest seed 7: passes'. M08 and M19 are redundant with each other (both applied: test_cases fails, rerun here).

Probe: mut M11, M16

Suggested: Add a collection and weakref check to the set_class test (A dies after the assignment, B lives while the object does).

> Verifier: **confirmed** (low). RefObject.set_class (refmodel/objects.py 1014-1016: incref(cls); self.cls = cls; decref(old)) and RefClass._hold_mro (734-737, decref of the old MRO) have no test holding their counts. The set_class test (test_cases.py 1455-1505) checks values and cache misses only. The M16 survivor belongs to the reassign-bases tests (1376, 1410), not the set_class test, so the proposed action covers M11 only. Model-only; compiled programs stop at __class__ assignment ([P2+]).

Minor, one line each, not verified:

- p1 sizeof: stops with 'not implemented: object.__sizeof__' (known, TODO).
- p3 type_params and basicsize rows stop by name (type.__type_params__, type.__basicsize__ not yet).
- p6/p7 super and ModuleType rows stop: 'subclassing the built-in type super', 'a subclass of the module type (step 3b)'.
- p4 dataclass_* rows stop with E-01 exec not staged: a function-local @dataclass is not reached by the dry run (staging property).
- gc.collect() return values differ (CPython 41-77 vs 36-67 for dropped classes): covered by D-04 and the 2026-11-14 decision.
- p5/p9 exit order of finalisers differs (D-07).
- p3 instantiate/object_dict_of_other differ only in stderr addresses and paths.
- D-04 row in dialect-spec section 11 (line 219) is 'Partial: classes with __del__ that can form cycles' and does not mention the class lifetime changes of 756222f.

Covered: Reran all 15 earlier probes (p1-p15) with r48_both.py; the DIFF counts matched the saved outputs (out2.txt). Classified every DIFF row: stops by name (__sizeof__, __type_params__, __basicsize__, subclassing super and the module type, sys.addaudithook/setprofile, path_hooks, __class__ and __bases__ assignment, a metaclass __del__ in the class body, dataclass/namedtuple built in a function whose text the dry run did not stage), covered deviations (D-07 exit finaliser order, D-04 and the 2026-11-14 decision for gc.collect() counts, D-28 and path differences in stderr), and the seven findings. New probes q1-q4 (4 of 8 builds): reductions plus gc.collect return values, weak sets/dicts/WeakMethod/finalize/bound-method refs to classes, exception classes, NamedTuple, nested __class__ cells, __init_subclass__, a metaclass's __init__ registry, class weakref callbacks, gc disabled with 3000 classes ...

Not covered: Did not trace the exit code or the collector to confirm the causes of findings 2, 5, 6 beyond reading the named lines. Did not build the pre-756222f commit, so I cannot say whether finding 5 pre-dates it (finding 4 does, from 2e0b1d3). Did not run the runtime's own tests (forbidden) or measure the DECISIONS cost claims. Memory growth in loops only from the p7 loop rows (SAME). Not swept: threads, copy/pickle of classes, functools.cache on methods, typing generics beyond NamedTuple, dataclasses defined at module level in a fresh probe, fetching CPython C sources (behaviour was established by ru ...


## c02-proxy-and-a44: the class dict's proxy and review A44's fixes (6ed9635, de4e40c)

### F48-c02-proxy-and-a44-1 (RL-1043): A class with no MRO is accepted as a base; its subclass gets an MRO without object (RL-940's fix)

*defect, reported as high*; where: commit de4e40c; runtime/include/bella/object.hpp:1040-1042 (c3), runtime/src/types.cpp:1484-1493 (type_mro), refmodel/objects.py:507-509 (_c3); review log RL-940

Since de4e40c a class under a metaclass other than `type` has an empty MRO while its mro() runs, and keeps it when mro() fails (the hook can keep the class). CPython refuses such a class as a base: type.mro() raises TypeError "Cannot extend an incomplete type". The runtime's c3 and the model's _c3 have no such check and merge the empty MRO, so a subclass made inside the hook, or from a class a failed hook left behind, is created with __mro__ == (D, C): none of C's ancestors, no `object`. It joins C's subclasses and keeps that MRO after C is finished. Recorded nowhere. By the diff, C had its C3 order at that point before the fix (the older commit was not run).

Evidence: CPython v3.15.2 Objects/typeobject.c:3482-3488 (mro_implementation_unlocked): `if (lookup_tp_mro(base) == NULL) { PyErr_Format(PyExc_TypeError, "Cannot extend an incomplete type '%.100s'", base->tp_name);`
f1 escape_ok_then_use_in_hook: CPython `subclass in hook raised TypeError` / `['C', 'Base', 'object'] []`; compiled `subclass in hook ['D', 'C']` / `['C', 'Base', 'object'] ['D']`.
f1 escape_failed_subclass: CPython `subclass of the half-made class raised TypeError` / `plain subclass raised TypeError`; compiled `(['D', 'C'], True, ['C', 'D'])` / `plain subclass ['P', 'C']`.
h1 (48 of 56 rows differ; CPython prints `refused ...` / `no class was made`), compiled for type('D', (c,), {}): `failed_type issubclass` -> `False False True` for (D, Base), (D, object), (D, C); `failed_type inherited` -> AttributeError; `failed_type instance` -> TypeError cannot create 'D' instances; `failed subclasses` -> `['D'] []`. No crash seen.
Model under CPython: C = RefClass('C', (Base,), mro_hook=True); RefClass('D', (C,)).mro -> ['D', 'C'].
grep -i 'incomplete type' over runtime/, refmodel/ and review-log.md: nothing.

Probe: f1 (rows escape_failed_subclass, escape_ok_then_use_in_hook); h1 (all 56 rows)

Suggested: Fix, the model first: a base with no MRO refuses in type.mro() as CPython has it (TypeError), then the header; add these rows to test_review_2026_11_24_a44.py and a review-log row beside RL-940.

> Verifier: **confirmed** (high). Since de4e40c a class under a metaclass other than `type` that is waiting for its MRO (inside its mro() hook, or left behind by a failed hook) is accepted as a base. A subclass is then created with an MRO lacking the base's ancestors (no `object`) and keeps it. CPython's type.mro() raises TypeError 'Cannot extend an incomplete type'. Neither c3 (object.hpp:1040) nor the model's _c3 checks for it. Not recorded anywhere. Fix the model first, then the header.

### F48-c02-proxy-and-a44-2 (RL-1044): Assigning a class's __module__ leaves __firstlineno__ in its dict

*defect, reported as high*; where: runtime/src/types.cpp:1698-1702 (set_type_module); older than both commits (2c9a06a/bd49090, 2026-11-02); clause C-3-27

CPython's type_set_module pops `__firstlineno__` from the type's dict before it stores `__module__`; the runtime's set_type_module only stores. After any assignment of a class's `__module__` (the same value too, by setattr, or through the getset) `C.__firstlineno__` gives the line where CPython raises AttributeError, and `C.__dict__` has one key more. `__firstlineno__` is in C-3-27 [P1]; nothing in the spec, deviations.toml, the review log or TODO names this. Older than both commits (the function is of 2026-11-02); the proxy sweep showed it. Small in reach: functools.update_wrapper on a class, dataclasses.make_dataclass, set_module decorators.

Evidence: CPython v3.15.2 Objects/typeobject.c:1685-1689: `if (PyDict_Pop(dict, &_Py_ID(__firstlineno__), NULL) < 0) { return -1; } return PyDict_SetItem(dict, &_Py_ID(__module__), value);`
runtime/src/types.cpp:1700-1701: `check_special(c, v, "__module__"); c->set_attr(N("__module__"), v);`
f1 module_drops_firstlineno: CPython `after False elsewhere ['__module__', '__static_attributes__', '__dict__', '__weakref__', '__doc__']` / `attribute raised AttributeError`; compiled `after True elsewhere ['__module__', '__firstlineno__', '__static_attributes__', '__dict__', '__weakref__', '__doc__']` / `attribute 254`.
f1 module_same_value (C.__module__ = C.__module__): CPython `after False`; compiled `after True`.
f1 module_setattr_routes: CPython `setattr False` / `descriptor False`; compiled `setattr True` / `descriptor True`.
p1 order: the same key left in a held proxy's listing.
grep firstlineno in review-log.md, DECISIONS.md, dialect-spec.md: nothing about it.

Probe: f1 (rows module_drops_firstlineno, module_same_value, module_setattr_routes); p1 (row order)

Suggested: Fix: drop `__firstlineno__` when present before the store, as type_set_module does; a row in C-3-27 (or a test) first; a new review-log row.

> Verifier: **confirmed** (high). set_type_module (types.cpp:1698-1702) only stores `__module__`. CPython's type_set_module first pops `__firstlineno__` from the type's dict. After any assignment of a class's `__module__` (also the same value, setattr, or the getset descriptor), compiled `C.__firstlineno__` still answers where CPython raises AttributeError, and `C.__dict__` keeps the key. `__firstlineno__` is P1 via C-3-27's case; nothing registered covers this. Reach is small: update_wrapper on a class, set_module-style decorators.

### F48-c02-proxy-and-a44-3 (RL-1045): RL-937 is recorded as fixed, and gc.garbage under DEBUG_SAVEALL still differs for a dead class

*follow-through, reported as medium*; where: runtime/src/gc.cpp:191-204 (save_to_garbage); docs/reviews/review-log.md:1349 (RL-937); docs/deviations.toml:29 (D-04's note); pipeline/tests/review_a44/collect

RL-937 is 'Fixed', but the fix covers the reviewer's two predicates only. For a dead class under DEBUG_SAVEALL: (1) the bases' tuple of a class with no base written, `(object,)`, is still missing, though RL-937's title names the bases tuples; (2) tuples of atoms the class holds (`__slots__`' value, `__static_attributes__`, a `(1, 'x')` attribute) are in the compiled list and not in CPython's, against the comment the fix added in gc.cpp ("stays out"); (3) the class comes before its dict, where CPython lists the dict first. D-04's note makes gc's numbers the runtime's own and does not name gc.garbage's contents; the test holds two membership predicates.

Evidence: g1: 30 class shapes, each sorted and in order; 20 of 60 rows same.
`nobase sorted`: CPython `4`: `class Child`, `dict __dict__,...,mark`, `tuple Child,object`, `tuple object`; compiled `3`, no `tuple object` (also type_call_nobase, nested, init_subclass).
`slots sorted`: compiled has `tuple str,str` more; `mutable_attrs sorted`: `tuple int,str` more.
f1 saveall_static_attributes: CPython `['tuple cell']`; compiled `['tuple str,str']`.
f1 saveall_atoms_tuple (an instance cycle, no class): CPython `['O', 'list', 'tuple int,list']`; compiled adds `frozenset` and `tuple int,str`.
`plain order`: CPython `tuple Base`, `dict ...`, `class Child`, `tuple Child,Base,object`; compiled `tuple Base`, `class Child`, `dict ...`, `tuple Child,Base,object`.
gc.cpp:196-197: "A tuple of untracked objects only, as __static_attributes__' or ht_slots, is untracked by CPython's collection and stays out".
deviations.toml:29: "what gc.collect() returns, gc.get_count(), gc.get_stats() and the numbers gc.callbacks are given are the runtime's own".
Also seen, already known: no closure tuples (`tuple cell`), a `mappingproxy` in the dict cell (RL-489, open).

Probe: g1 (all rows); f1 (rows saveall_static_attributes, saveall_atoms_tuple)

Suggested: Ask the author: either gc.garbage's contents under DEBUG_SAVEALL join D-04's note as the runtime's own (RL-937 then 'in part'), or finish the class ((object,), CPython's untracked tuples, dict before class) with a sweep kept as a test. Correct the gc.cpp comment either way.

> Verifier: **confirmed** (medium). RL-937 is marked Fixed, but under DEBUG_SAVEALL a dead class still differs. (1) The `(object,)` bases tuple of a class with no base written is missing; this is a real defect. (2) Tuples and frozensets of atoms (`__slots__`' value, `__static_attributes__`, an instance's `(1,'x')`) are in the compiled gc.garbage, though the gc.cpp comment and RL-937's text say they 'stay out'. The untracking rules are partly known as queued: `is_tracked()` stays a stop, 'to be measured first'. (3) The class comes before its dict where CPython lists the dict first. D-04 does not name gc.garbage's contents, and th ... Cover: Partly: DECISIONS.md:1732 'is_tracked() stays a stop: CPython untracks tuples and dicts by rules of its own, to be measured first' (for the untracked atom tuples); D-04 'order among themselves' (finalisation order only); RL-489 for the mappingproxy

### F48-c02-proxy-and-a44-4 (RL-1046): The decision for C-3-82 names a condition CPython 3.15.2 does not have, and the case has no row for it

*wrong-fact, reported as medium*; where: docs/DECISIONS.md:1873 (2026-11-24, C-3-82); conformance/cases/C-3-82_when_a_class_dies.py:37; commit 6ed9635

DECISIONS (2026-11-24, C-3-82) says a class dies while its proxy is held when its dict names nothing of it: "(no method's `__class__` cell, no slot, no `__dict__` or `__weakref__` descriptor of its own)". The last condition is false for 3.15.2: those two getsets are object's, shared by every class, and do not name the class, so a class with no base written dies too. The case's docstring repeats it. The runtime agrees with CPython on all of it, but the case's only shapes are `class B(A)` and one with super(): a class with no base written, and a slot that keeps its class, are held by no case or test.

Evidence: CPython 3.15.2, run: `class K: x = 1`, `class L: pass`: `K.__dict__['__dict__'].__objclass__` -> `<class 'object'>`; `K.__dict__['__dict__'] is L.__dict__['__dict__']` -> True; `p = K.__dict__; del K; gc.collect(); len(p)` -> 0; the same with `__slots__ = ('a',)` -> 6 (kept).
C-3-82 case line 37: "A class whose dict names nothing of it: no method, no slot, no dict or weakref descriptor of its own."
p2 `keeps_*`, 38 class shapes, both sides agree on 37 (one is a named stop, E-01): keeps_no_base, keeps_slots_dict_only, keeps_slots_weakref_only, keeps_type_call_no_base, keeps_method_plain -> `class alive False proxy 0`; keeps_slots, keeps_slots_sub, keeps_method_super, keeps_method_dunder_class, keeps_staticmethod_super -> `class alive True proxy full`.
The runtime's own comment at weakref_getset (runtime/src/types.cpp) says "CPython's belongs to object, whichever class it is put in".

Probe: p2 (rows keeps_*)

Suggested: Reword the decision's parenthesis and the case's docstring; add case rows for a class with no base written, a class with a slot (kept by its proxy) and a method that does not name its class.

> Verifier: **confirmed** (medium). DECISIONS 2026-11-24 (C-3-82, line 1873) and the case docstring (line 37) name a condition CPython 3.15.2 lacks: a class's `__dict__`/`__weakref__` getsets are object's shared ones and keep no class; only a slot or a `__class__` cell does. The runtime agrees with CPython; the case has no row for a base-less class, a slotted class or a method not naming its class.

### F48-c02-proxy-and-a44-5 (RL-1047): TODO's record of the class's basic weak reference says less than what happens

*words, reported as low*; where: TODO.md:567-572; docs/DECISIONS.md:1849; runtime/src/abc.cpp:118-135; runtime/prelude/_weakref.py:130-140; RL-938

The gap is recorded as open (TODO.md:567-572, DECISIONS.md:1849), but TODO says only that "a metaclass's `__hash__` can run once more than CPython's". Measured: it runs at every `hash(weakref.ref(K))` while the program holds no reference, and an `issubclass` answer differs: when the program hashed the class's reference before the metaclass got a `__hash__`, CPython's `_abc` keeps missing its cache with the kept hash and asks the subclass hook again, while compiled finds the entry and answers from the cache. That is RL-938's row in the other direction, which RL-938's fix does not reach.

Evidence: f1 weak_hash_twice: CPython `hash called`, `5`, `5`, `True 1`; compiled `hash called`, `5`, `hash called`, `5`, `True 0`.
f1 abc_answer_after_refhash (hash(weakref.ref(C)); issubclass(Old, A); M.__hash__ = lambda cls: 12; print(issubclass(C, A)); accept[0] = True; print(issubclass(C, A))): CPython `False`, `True`; compiled `False`, `False`.
a1 abc_refhash_first: CPython `again`, `hash`, `False`, `third`, `hash`, `False`; compiled `again`, `hash`, `hash`, `False`, `third`, `False`.
a1 abc_lookup_then_refhash (`hash(weakref.ref(C)) == 12` after _abc kept the hash and M.__hash__ changed): CPython `False` with no call; compiled `hash`, `True`.
a1 abc_counted, abc_minus_one: one more `hash` line at each hash(weakref.ref(K)).
The other five abc rows of a1 agree (a metaclass that logs __hash__ and __eq__ through every _abc operation, a __hash__ that raises, a dead class and a new one).

Probe: a1 (rows abc_refhash_first, abc_lookup_then_refhash, abc_counted, abc_minus_one); f1 (rows weak_hash_twice, abc_answer_after_refhash)

Suggested: Reword the TODO entry (an answer can differ, not only a count). When it is done, the class's reference should read and fill ClassObject::reference_hash; these four rows are its test.

> Verifier: **confirmed** (low). The TODO entry (TODO.md:567-572) and DECISIONS.md:1849 say the class's basic weak reference is missing and that a metaclass's __hash__ 'can run once more' than CPython's; all quotations are present as quoted. The wording understates the gap: the answer of issubclass can differ (f1 abc_answer_after_refhash: CPython False/True, compiled False/False). Cited code is there at runtime/src/abc.cpp:124-128 (reference_hash, RL-938) and runtime/prelude/_weakref.py:130-140 (__hash__). Severity low kept.

### F48-c02-proxy-and-a44-6 (RL-1048): A built-in type's proxy looks a key up by its text

*defect, reported as low*; where: runtime/src/types.cpp:2224-2231 (proxy_getitem), 2241-2245 (proxy_contains), 2252-2258 (proxy_get); the path 6ed9635 kept for immortal classes

For an immortal class (a built-in type's `__dict__`) the proxy's `[]`, `get` and `in` hash the key and then look it up by its text if it is a str, and answer 'absent' if it is not. A dict looks up by hash and `__eq__`. So a key that is not a str but equals one is not found, a str subclass whose `__hash__` differs is found where CPython misses, and a str subclass's `__eq__` is never called. Older than the range; C-3-82 kept this path on purpose under a comment that says "every reading is its mapping's". A counted class's proxy agrees with CPython on the same keys.

Evidence: types.cpp:2225-2228: `dict_key_hash(a.pos(0)); const Str* k = as_str(a.pos(0)); if (k != nullptr) if (const Obj* v = c->attrs.find(intern(k->text))) return Ref::share(*v);`
p1 keys_builtin, on int.__dict__:
K('real') (an object whose __hash__ and __eq__ are the text's): CPython `K getitem getset_descriptor`, `calls ['hash', 'eq']`, `K in True`; compiled `K getitem raised KeyError`, `calls ['hash']`, `K in False`.
SK('real') (a str subclass that logs): CPython `calls ['hash', 'eq']`; compiled `calls ['hash']`.
Bad('real') (a str subclass whose __hash__ is 7): CPython `bad hash (False, 'NoneType')`; compiled `bad hash (True, 'getset_descriptor')`.
p1 keys_exact (the same keys on a class of the program's): same on both sides.

Probe: p1 (rows keys_builtin, keys_exact)

Suggested: Low priority: read the view for these three methods when the key is not an exact str, or register the difference; a review-log row either way.

> Verifier: **confirmed** (low). For an immortal class's proxy (a built-in type's `__dict__`), `[]`, `get` and `in` hash the key then match by str text only, never by hash identity or __eq__. Non-str keys equal to a name are not found, a str subclass's __eq__ is not called, and a str subclass with a different __hash__ is found where CPython misses. Own-class proxies agree.

Minor, one line each, not verified:

- Inside mro(), cls.__dictoffset__ and cls.__weakrefoffset__ are already non-zero for a class that inherits its dict; CPython's are still 0 there, before type_ready_inherit (m1 rows `sizes`, four shapes).
- list(d), sorted(d) and [*d] of a dict subclass that overrides __len__ do not ask __len__ for the length hint (CPython logs ['iter', 'len'], compiled ['iter']), also through a MappingProxyType over it. Older than the range (f1 list_of_proxy_len, p1 proxy_of_subclass).
- Part of finding 1's class: where the hook of D returns its own tuple, CPython makes D and D() raises TypeError (cannot create 'D' instances); compiled makes the instance (h1 rows inhook_explicit instance*).
- DECISIONS says C-3-82's `annotated` row differs under eval1 (the class lives until its annotate function goes) and the case is in two baselines only; TODO does not carry this as open.
- functools.update_wrapper(cls, other_cls) stops at type.__type_params__ (a named stop), so the third route of f1 module_setattr_routes could not be compared.
- Named stops met, all honest: type.__getattribute__, type.__text_signature__, type.__type_params__ (read and write), gc.is_tracked, importing pickle, a dataclass made in a function (E-01).

Covered: Eight builds, 441 rows, every row run under CPython 3.15.2 and compiled with r48_both.py; outputs are in each probe folder's out.txt under review/c02-proxy-and-a44/ (showdiff.py prints the differing rows). CPython's C was read from v3.15.2 sources fetched into cpython-src/ (Objects/typeobject.c and others), never run.

Result in short: both commits hold on their own subjects. C-3-82 agreed on every neighbour (p1: 40 of 47 rows same, p2: 62 of 63; the rest are named stops or findings 2 and 6, which are older code). RL-938 to RL-942 agreed on every neighbour not already recorded as open. What did not hold is finding 1 (a gap the RL-940 fix opened) and finding 3 (RL-937 fixed in part).

- C-3-82 (6ed9635): the diff of types.cpp, core.cpp, runtime.hpp, the model and its test; the case (CPython reproduces its recorded stdout). p1/p2: five routes to the proxy, a proxy kept after the class dies, three views and five iterators taken before the death, copy, | on both sides, |=, reversed, repr, equality; iteration while the class changes; key order with the view made early and late; the special writes (__annotations__, __doc__, __abstractmethods__, __annotate__, names); keys that log __hash__ and __eq__; MappingProxyType over a dict, a dict subclass overriding everything, defaultdict, OrderedDict, ChainMap, UserDict, frozendict, a custom mapping, 13 refused arguments; deaths with and without a view; a finaliser reading the proxy during the clear; resurrection; 38 class shapes for "does the dict name its class"; the proxies of 18 library classes while the program changes them.
- RL-940/941: m1 (54 actions inside or after the hook on four class shapes: 94 of 100 rows same, four differ only in __dictoffset__, two are named stops) and f1 (mro as static method, class method, property, callable object, None, on the meta-metaclass, two levels of super().mro(), hook order, an order C3 refuses in use).
- RL-938: a1, nine rows. RL-939: a1, 18 rows, all same. RL-942: a1 (eight rows) and x1 (53 holders of a finalised object at the exit: 52 same, one by D-06).
- RL-937: g1 (30 shapes, contents and order).
- Read: review A44, its review-log rows, the DECISIONS entries of 2026-11-24 for both commits, test_review_2026_11_24_a44.py and its ten programs (each row compares both sides and can fail). The two model tests of these commits pass under CPython.

Not covered: - REPORT.md was not written: the Write tool refused it ("Subagents should return findings as text, not write report files"), and I did not work around that. The full account is this result plus the probe folders (prog.py, rows.txt, out.txt in m1, p1, p2, g1, a1, x1, f1, h1).
- The cost figures in both DECISIONS entries (9% faster, 3% and 10% slower, "none measured") were not measured again.
- pipeline/tests/test_review_2026_11_24_a44.py and the conformance legs were not run (they build); C-3-82 under eval1 and eval2 was not run.
- The exit's code (collect_at_exit, deduce_unreachable with cpython_view) was checked by rows, not read to the end. "No other static table of the runtime's holds an object a program made" got a grep, not a proof.
- A prelude class's proxy made while the class was still counted (its annotation scope's cell reads the view without bringing it in step) was reasoned about from the code only.
- The older commit was never built, so "before the fix" in finding 1 is read from the diff.
- __bases__ assignment under a metaclass with mro() (a named stop), threads and the lean fidelity.


## c03-modules-counted: module objects counted (25e2f67)

### F48-c03-modules-counted-1 (RL-1049): gc.garbage lists a collected module's namespace dict before the module under CPython, after it compiled

*defect, reported as low*; where: p10 rows mod_me_first, mod_x_first, mod_only_me, mod_vars_first, mod_list, pair, ns; p5 row saveall; runtime collector order for Module and its dict (runtime/src/core.cpp)

Under gc.DEBUG_SAVEALL, a collected module cycle gives gc.garbage as [dict, module, ...] in CPython 3.15.2 and [module, dict, ...] compiled, for every variant tried. The set, the counts and the deaths agree; only the list order differs. An instance cycle and a dict-only cycle agree. The model's oracle sorts each collection's deaths, so it cannot see this. D-04 speaks of finalisation order, not the unreachable list's order, and the commit message's 'same garbage in the same order' concerns rooted skip versus no skip, not CPython.

Evidence: p10 row mod_only_me: m = types.ModuleType('m'); m.me = m; del m; DEBUG_SAVEALL collect; print(kinds(gc.garbage)). CPython ['dict', 'module'], compiled ['module', 'dict']. pair: CPython ['dict','module','dict','module'], compiled ['module','dict','module','dict']. p5 saveall: CPython ['dict','module','Marker'], compiled ['module','dict','Marker'].

Probe: p10 (all rows), p5 saveall

Suggested: Order the module's dict before the module in the collector's list as CPython has it, or widen D-04's words to cover gc.garbage's order. Low: only visible through DEBUG_SAVEALL.

> Verifier: **confirmed** (low). Under DEBUG_SAVEALL a collected module cycle gives gc.garbage as [module, dict, ...] compiled and [dict, module, ...] in CPython (set and counts agree). Only the module/dict pair is reversed. Not covered in words: D-04/spec 191 speak of finalisation order, not the list's order. Cover: partial: D-04 'their members are finalised in a different order'; spec line 191 'finalisers ... in an unspecified order'; design.md 798 'The oracle compares a collection's deaths ... as a multiset'. None names gc.garbage's order; no RL/TODO entry.

### F48-c03-modules-counted-2 (RL-1050): m.__class__ = types.ModuleType raises TypeError compiled; CPython allows it

*defect, reported as low*; where: runtime/src/ops.cpp:1457 (setattr on a Module, __class__); p8 row dunders

Assigning ModuleType itself to a module's __class__ is allowed in CPython (object_set_class: both types are subtypes of module). The runtime tests !c->heap_type before anything else and raises 'TypeError: __class__ assignment only supported for mutable types or ModuleType subclasses'. Real subclasses stop by name ([P2+] __class__ assignment; the class statement stops with 'a subclass of the module type (step 3b)'), so only the no-op assignment gives a wrong error where a stop or CPython's behaviour is expected. __class__ assignment is [P2+] (spec lines 57, 102).

Evidence: p8 row dunders, last statements: CPython carries on past m.__class__ = types.ModuleType and prints the two later TypeErrors; compiled exits 1 with 'File prog.py, line 162, in row_dunders / TypeError: __class__ assignment only supported for mutable types or ModuleType subclasses'. Everything before that line in the row (repr of nameless and non-str-named modules, error texts, __init__ again, __new__ without init, copy, readonly __dict__) agrees.

Probe: p8 row dunders

Suggested: Accept ModuleType (a module type to a module) as a no-op, or stop by name like the other [P2+] cases.

> Verifier: **confirmed** (low). m.__class__ = types.ModuleType succeeds in CPython (both types are module subtypes) but raises a TypeError compiled ('__class__ assignment only supported for mutable types or ModuleType subclasses', ops.cpp ~1452, !c->heap_type tested first). __class__ assignment is [P2+], so it should stop by name, as the ModuleType-subclass case does, rather than raise a false error. Cover: [P2+] rows in spec lines 57 and 102 cover the feature, not the wrong error; nothing in review-log, TODO or DECISIONS about the ModuleType case.

### F48-c03-modules-counted-3 (RL-1051): 'Checked by the selftest' for the rooted skip is true only of the dedicated unit test

*test, reported as low*; where: docs/DECISIONS.md ~line 1925 ('The collector does not walk a rooted namespace', 'checked by the selftest'); refmodel/selftest.py; refmodel/tests/test_cases.py test_a_module_is_a_counted_object

An unsound rooted() (rooted whenever the module is alive and holds its namespace, even when sys.modules does not hold it) survives refmodel.selftest at make test's setting (--iterations 3000, default seed) and at 5000 iterations; it is caught only at 20000 iterations (seeds 0, 1) or on 2 of 8 seeds at 6000. The dedicated test_a_module_is_a_counted_object does catch it. rooted() answered true only 44 times of 221 calls over 8 seeds at 6000. On the compiled side no test names rooted_namespace (grep of pipeline/ and conformance/ finds nothing); only the corpus holds it. My randomised sweep p3 (25 seeds, rooted and unrooted, explicit and automatic collections) agrees with CPython everywhere, so  ...

Evidence: Mutation runs on the checkout's refmodel under CPython only: review/c03-modules-counted/model/mutate.py output 'always rooted while alive and holding (unsound) seeds 8 failed 2'; 'never rooted' and 'rooted without the alive/holds test' fail 0 (the first by design, the others possibly equivalent). A run at seed 20261031: 'mutant survives 3000', 'mutant survives 5000'. test_cases mutation: 'always rooted ... FAILS AssertionError', 'inverted FAILS', 'never rooted passes'.

Probe: model/mutate.py, scratchpad mut2.py and mut3.py

Suggested: Say in DECISIONS that the unit test, not the random selftest, holds the skip; or add a rooted-and-garbage world to the selftest's default run.

> Verifier: **confirmed** (low). DECISIONS ~1923 says the rooted skip is 'checked by the selftest'. The random selftest at make test (3000) and CI (5000), default seed, does not catch an unsound rooted(); it does at 20000 (make selftest). The dedicated unit test test_a_module_is_a_counted_object catches it, so the skip is held, but the words are imprecise. Words only; no defect shown. Cover: DECISIONS: 'In the model first (RefModule.rooted), checked by the selftest' (imprecise, true only at 20000). No RL/TODO entry.

Minor, one line each, not verified:

- p4 wrcb/sig/plain dead and live: order of 'called' against 'fn callback', cause is the caller's argument temporary (RL-695, Question 30, queued); p9 shows plain callee lifetime agrees.
- p7/p8 sub, res (ModuleType subclass) and co (coroutines): stop by name ('a subclass of the module type (step 3b)', 'running the coroutine coro'), not defects; their CPython-side behaviour was recorded in p7/p8 out.txt for when they are implemented.
- p8 dunders: object.__sizeof__ stops by name in the first build (p7), the second build (p8) took it out of the row.
- DECISIONS 'What is left' paragraph of 2026-11-25 still says C-9-14 waits for Question 43; superseded by 0c25f5e (C-9-14 compiled, my p1 giver row and C-9-14 agree). Historical wording, not checked further.
- C-9-14 does not exercise the rooted skip (no successfully imported module in a collection), a module whose weak reference list has two callbacks, or the exit; those are held by A43's rows, p3 and p5 here.

Covered: Reran every probe of the stopped reviewer with r48_both.py, no new build for them: p1 (29 rows), p2 (21), p3 (30 incl. 25 random sweep rows), p4 (86 function-lets-go-of-itself rows), p5 (12), p6 (3). Classified every DIFF row. Exit-order-only rows (p1 exit_giver_twice, exit_cycle; p2 x_exit, gens_exit, wcount, attrs): I checked the multisets of lines are equal, so D-07. p2 x_native: E-04 (write to sys.modules). p2 dc: E-01 staging stop, the dry run (no-argument run) never reached the row, p3 runs the same module and agrees. p3 genx and tbfunc: TODO 'What a frame object does not have yet' item (b), f_funcobj. p4 getattribute: [P2+] stop. p4 wrcb, sig, plain: RL-695 and Question 30 (the caller's argument temporary), shown by my p9, where the callee reference itself agrees in 9 call shapes (all SAME). p5 uncaught and delraises: D-06 traceback format. p5 saveall: Finding 1. My own probes, 4  ...

Not covered: Pickling and copy of functions whose module is dead; importlib.reload and any del sys.modules beyond what p2 already shows (E-04); threads ([P2+]); the cost figures (0.22 s to 0.12 s, +0.6%), which are c11's. I did not mutate the compiled runtime's rooted_namespace, since no source edits or extra builds were allowed, so its soundness rests on reading the code (a fresh look-up at each visit, no cached flag) and on the p3 sweep. I did not check the DECISIONS 'What is left' paragraph (a failed module dies when the import ends, waits for Question 43) as stale words, although commit 0c25f5e and p1  ...


## c04-a45-fixes: review A45's fixes (cf5304d, eb3b38b)

### F48-c04-a45-fixes-1 (RL-1052): dir(x) sorts the names as text: a str subclass's own __lt__ is neither called nor obeyed (the neighbour RL-947's fix left; RL-836's class)

*defect, reported as high*; where: runtime/src/imports.cpp:2437-2441 (b_dir with an argument; written 2026-11-04, older than the range). CPython: Objects/object.c:2252-2256 (_dir_object)

RL-947 made dir(module) run no extra code of the program's, but the other half of dir() is still not CPython's. With an argument, b_dir orders the names by std::stable_sort on their text, where _dir_object sorts the list with PyList_Sort. A name that is a str subclass with its own __lt__ has it called and obeyed under CPython and not compiled: the calls are missing and the order of the result can differ. dir() without an argument is right (line 2427 uses the list's own sort; p8_last class_dir_noarg prints the same lt lines on both sides). Nothing registered covers it; not in the review log, TODO or DECISIONS. Narrow: it needs such a name among a module's keys or in what a __dir__ returns.

Evidence: imports.cpp:2441: std::stable_sort(items.begin(), items.end(), [](Obj x, Obj y) { return as_str(x)->text < as_str(y)->text; });
object.c:2252-2256: sorted = PySequence_List(result); ... if (PyList_Sort(sorted)) {

.venv/bin/python r48_both.py review/c04-a45-fixes/p6_more --rows review/c04-a45-fixes/p6_more/rows.txt, row reversed_order (class Rev(str) with __lt__ reversed; a class's __dir__, a module's __dir__ function, a module's keys):
  CPython : ['c', 'b', 'a'] / ['c', 'b', 'a'] / ['c', 'b', 'a'] ['b', 'a', 'c']
  compiled: ['a', 'b', 'c'] / ['a', 'b', 'c'] / ['a', 'b', 'c'] ['b', 'a', 'c']

p1_dir row lt_keys (ModuleType with two keys of class K(str) whose __lt__ prints): CPython prints 'lt public __name__', 'lt public __spec__', 'lt apple __package__', 'lt apple public', 'lt apple __spec__' between 'listing' and the list; compiled prints none (same list). p1_dir row lt_class_dir: four lt lines against none. p3_locals row dir_sorts (dir of __main__ with two such globals): ten lt lines against none, while sorted(globals()) in the same row calls them on both sides.

Probe: p1_dir (lt_keys, lt_class_dir, non_str), p3_locals (dir_sorts), p6_more (reversed_order), p8_last (class_dir_noarg)

Suggested: Fix: sort with list_sort_m in b_dir as line 2427 does and drop the stop "dir() of names that are not all str (list.sort: step 3b)", which that sort turns into CPython's TypeError; add the lt_keys and reversed_order rows to review_a45/moddir.

> Verifier: **confirmed** (high). dir(x) with an argument sorts names by their text (std::stable_sort in b_dir, imports.cpp:2441); CPython's _dir_object uses PyList_Sort. A str-subclass name's own __lt__ is neither called nor obeyed, so side effects and the result order differ. The non-str stop would disappear with the fix. Narrow trigger.

### F48-c04-a45-fixes-2 (RL-1053): A lambda or generator expression inside a generator expression gets '.<locals>' in its __qualname__

*defect, reported as high*; where: pipeline/l1/frontend.py:1031 with qualname() at 996-1000 (same rule at 2381-2386); rule from 2026-11-02, older than the range. CPython: Python/compile.c:289-301 (compiler_set_qualname)

Found by the task's sweep of __qualname__; not of the two days' work. The frontend enters a generator expression as a scope of kind "function", and qualname() puts '.<locals>.' after every such scope. CPython adds '.<locals>' only when the parent scope is a function, an async function or a lambda; a comprehension scope's children get '<parent>.<name>'. So __qualname__, __code__.co_qualname and repr() of a lambda or of a nested generator expression made inside a generator expression differ, at function, module and class level. A lambda in a lambda, in a list, set or dict comprehension, and generic functions and classes agree. Nothing registered covers it; not in the review log or TODO.

Evidence: frontend.py:1031: self.stack.append(("function", n.bella_qualname, frozenset(), n.bella_first, in_class))
frontend.py:1000: return f"{qual}.<locals>.{name}" if kind == "function" else f"{qual}.{name}"
compile.c:289-301: if (parent->u_scope_type == COMPILE_SCOPE_FUNCTION || ... ASYNC_FUNCTION || ... LAMBDA) { ... ".<locals>" ... } else { base = Py_NewRef(parent->u_metadata.u_qualname); }

p3_locals row qual_in_genexpr:
  CPython : qual_in_genexpr.<locals>.<genexpr>.<lambda> qual_in_genexpr.<locals>.<genexpr>.<genexpr> ...
            <function qual_in_genexpr.<locals>.<genexpr>.<lambda> <generator object qual_in_genexpr.<locals>.<genexpr>.<genexpr>
            <genexpr>.<lambda> <genexpr>.<genexpr> CLASS_GEN.<genexpr>.<lambda> CLASS_GEN.<lambda>
  compiled: qual_in_genexpr.<locals>.<genexpr>.<locals>.<lambda> qual_in_genexpr.<locals>.<genexpr>.<locals>.<genexpr> ...
            <function qual_in_genexpr.<locals>.<genexpr>.<locals>.<lambda> <generator object qual_in_genexpr.<locals>.<genexpr>.<locals>.<genexpr>
            <genexpr>.<locals>.<lambda> <genexpr>.<locals>.<genexpr> CLASS_GEN.<genexpr>.<locals>.<lambda> CLASS_GEN.<lambda>
Also p2_name row main_attrs and p6_more row qual_more.

Probe: p3_locals (qual_in_genexpr), p2_name (main_attrs), p6_more (qual_more)

Suggested: Fix: give the generator expression a scope kind of its own in qualname() (no '.<locals>' after it), with a conformance case first; register RL.

> Verifier: **confirmed** (high). A lambda or generator expression inside a generator expression gets '.<locals>' after '<genexpr>' in __qualname__, co_qualname and repr, because the frontend treats the genexpr scope as kind 'function' (frontend.py:996-1000, 1031, 2381-2386). CPython compile.c adds '.<locals>' only for FUNCTION, ASYNC_FUNCTION and LAMBDA parents.

### F48-c04-a45-fixes-3 (RL-1054): repr() of a class and of its instance uses __qualname__ where CPython uses the type's name, when __module__ is 'builtins' or not a str

*defect, reported as high*; where: runtime/src/ops.cpp:974-981 (type_repr_of, 2026-11-04) and runtime/src/types.cpp:1536-1543 (object_repr, 2026-11-02); older than the range. CPython: Objects/typeobject.c:2434-2462 (type_repr), 7538-7559 (object_repr)

Found by the task's sweep of names after rebinding __name__; not of the two days' work. Both functions print the qualified name whatever the module is. CPython prints '<class mod.qualname>' only when __module__ is a str other than 'builtins'; otherwise it prints tp_name, the class's __name__. So a class whose __module__ is 'builtins', not a str, or absent (made after the module's __name__ was deleted or set to a non-str) and whose qualified name is not its name (nested, made in a function, or __qualname__ assigned) has another repr compiled, and so has an instance with the default repr. Narrow, but default reprs are [P1] and nothing registered covers it (D-02 is the address only).

Evidence: ops.cpp:981: return str_new("<class '" + prefix + c->qualname + "'>");
types.cpp:1543: return str_new("<" + mod + c->qualname + " object at " + buf + ">");
typeobject.c:2458-2463: if (mod != NULL && !_PyUnicode_Equal(mod, &_Py_ID(builtins))) { result = PyUnicode_FromFormat("<class '%U.%U'>", mod, name); } else { result = PyUnicode_FromFormat("<class '%s'>", type->tp_name); }

p3_locals row class_repr (classes made in a function), CPython against compiled:
  <class 'Inner'>                 | <class 'class_repr.<locals>.Outer.Inner'>     (__module__ = "builtins" in the body)
  <class 'Other'>                 | <class 'class_repr.<locals>.Outer.Other'>     (__module__ = 5)
  <class 'Outer'> <Outer Outer    | <class 'Q.R'> <Q.R Outer                      (__qualname__ = "Q.R"; then an instance's repr)
  <class 'N'> <N Q.R              | <class 'Q.R'> <Q.R Q.R                        (after __name__ = "N")
p2_name row main_renamed (class made after del globals()['__name__'], then with __name__ = 5):
  CPython <class 'D'>, <class 'E'>; compiled <class 'main_renamed.<locals>.D'>, <class 'main_renamed.<locals>.E'>

Probe: p3_locals (class_repr), p2_name (main_renamed)

Suggested: Fix: the type's __name__ in the branch without a module, in type_repr_of and object_repr; keep the class_repr row as a test; register RL.

> Verifier: **confirmed** (high). repr of a class (type_repr_of, ops.cpp:974-981) and the default repr of an instance (object_repr, types.cpp:1536-1543) print __qualname__ where CPython prints tp_name (the type's name) when __module__ is 'builtins', not a str, or absent. Differs for nested classes, classes made in functions, or an assigned __qualname__. Narrow trigger; D-02 covers only the address.

### F48-c04-a45-fixes-4 (RL-1055): The A45 test does not hold the frame object's half of RL-945 nor the unwritten-names merge of RL-947

*test, reported as medium*; where: pipeline/tests/test_review_2026_11_25_a45.py, pipeline/tests/review_a45/textlocals and moddir; the code they should hold: runtime/src/core.cpp:1511-1516, runtime/src/call.cpp:2663-2668, runtime/src/imports.cpp:2336-2368

(a) cf5304d adds a branch to frame_ends (a text's top-level frame object takes the text's locals as f_locals) and one to i_traceback_names (the suggestion reads them from the frame object once the record let go); DECISIONS names both. The three textlocals rows are dataclass rows whose texts never raise, so no row can tell whether the branches are there. The only test where a text with its own locals raises (test_system_modules.py:83) prints the message and drops the exception at once. (b) The control moddir/native uses math, which has no name the runtime has not written: names-baseline.txt has module-level lines for sys (50) and builtins (3) only. So the row holds the deleted name and nothing of the rewritten merge, and no test lists sys in full.

Evidence: review_a45/textlocals/prog.txt rows: saveall, methods, frozen (two @dataclass classes; no raise, no traceback).
review_a45/moddir/prog.txt, native(): names = dir(math) ... del math.tau ... ; awk -F: '{print $1}' conformance/names-baseline.txt | sort | uniq -c gives sys 50, builtins 3 and no other native module (the rest are types).
grep over pipeline/tests and conformance/cases for texts run with separate locals: test_system_modules.py:78-83, test_staging.py:239, test_staged_compile.py:28 and 31, test_review_2026_11_10.py:300 and 567; none keeps an exception past the text or asks for a suggestion.

Rows of mine that do observe the branches, all SAME on both sides today: p4_text raise ('caught', 'locals dropped', 'released in-frame', 'exception dropped'), inner_raise, inner_dropped; p6_more eval_raise, back_chain; p5_suggest after_dropped ('locals dropped', "NameError: name 'lengthy_nam' is not defined. Did you mean: 'lengthy_name'?", 'released held', 'exception dropped'), caught_inside, cleared. p1_dir native_sys and p6_more native_direct list sys.
I could not build without the fix (read-only checkout), so that these rows fail without the branches rests on reading the code.

Probe: p4_text, p5_suggest, p6_more (eval_raise, back_chain, native_direct), p1_dir (native_sys)

Suggested: Add the p4_text rows raise, inner_raise, inner_dropped and the p5_suggest rows after_dropped, caught_inside to review_a45/textlocals (the text at module level, so the dry run stages it), and a sys row to moddir.

> Verifier: **confirmed** (medium). The A45 test (pipeline/tests/test_review_2026_11_25_a45.py) holds the gc.garbage half of RL-945 (textlocals/saveall) and the no-hash half of RL-947 (moddir/subclass), but not the frame-object f_locals branch (core.cpp frame_ends, call.cpp i_traceback_names) nor the merge of native-module names not yet written (only sys and builtins have any; math in the 'native' row has none). No row raises or asks for a suggestion, and no A45/A46 row lists sys. No behaviour differs today; it is a gap in the guard. Behaviour is held only by the reviewer's own probes.

### F48-c04-a45-fixes-5 (RL-1061, with the same subject): sys's namespace is not in CPython's order, and RL-951's record ('All 47 native modules agree') does not say sys is left out

*inconsistency, reported as medium*; where: docs/DECISIONS.md:1948; docs/reviews/review-log.md:1363 (RL-951); runtime/src/imports.cpp:2356-2363 (the merge in module_dir_m); runtime/src/cpython_names.inc (CPYTHON_MODULE_ORDER has sys)

Of A46's fix, met through the task's 'module.__dir__() of native modules'. RL-951 and DECISIONS say a native module's namespace is laid out in CPython's order and that all 47 agree. The order table also has sys, builtins, _abc, _types and the import system's two. builtins is known and open (RL-492, TODO.md:948). sys is recorded nowhere, and its namespace is in the runtime's own order: list(vars(sys)), iteration over sys.__dict__ and sys.__dir__() differ from CPython's, with nothing registered. In sys.__dir__() the 50 names the runtime has not written come in one block after __spec__, because the merge gives up at the first key out of CPython's order. _abc and _types agree.

Evidence: p8_last row sys_vars, list(vars(sys))[:12]:
  CPython : ['__name__', '__doc__', '__package__', '__loader__', '__spec__', 'addaudithook', 'audit', 'breakpointhook', '_clear_internal_caches', '_clear_type_cache', '_current_frames', '_current_exceptions']
  compiled: ['__name__', '__doc__', '__package__', '__loader__', '__spec__', 'argv', 'orig_argv', 'exit', 'intern', 'exc_info', 'exception', 'excepthook']

p6_more row native_direct: sys.__dir__() has the same 120 names on both sides in another order (compiled starts ..., '__spec__', 'addaudithook', 'breakpointhook', '_clear_internal_caches', ... the unwritten names, then 'exit', 'intern', 'exc_info', ...); '_abc True True' and '_types True True' with equal lists on both sides.

DECISIONS.md:1948 ends: "All 47 native modules agree; 39 did not." pipeline/tests/review_a46/nativeorder/prog.txt imports the 47; sys is only used for argv there.
grep for 'vars(sys)', 'sys.__dir__', "sys's namespace", 'sys.__dict__' in review-log.md, TODO.md, DECISIONS.md, dialect-spec.md, deviations.toml, design.md: no hit.

Probe: p8_last (sys_vars), p6_more (native_direct)

Suggested: Lay sys out with order_as_cpython as the 47 are, or register the difference beside RL-492; say in the RL-951 row and in DECISIONS which native modules are not among the 47; add sys to the nativeorder sweep.

### F48-c04-a45-fixes-6 (RL-1056): Slips in A45's records: RL-947's 'exact-str keys', RL-945's 'func_new', and three probes eb3b38b draws on that are kept nowhere

*words, reported as low*; where: docs/reviews/review-log.md:1359 (RL-947), 1357 (RL-945), line 67 (the A45 row as eb3b38b changed it)

RL-947's fix column says the missing names are found 'among the exact-str keys'; the code takes every str key, a subclass's too (as_str), as its own comment and DECISIONS say. RL-945 cites '_PyFunction_FromConstructor and func_new'; the second place that sets func_globals and func_builtins (funcobject.c:197-210) is in PyFunction_NewWithQualName, func_new_impl starting at 1105 (the fact itself is right). eb3b38b records what three unnamed probes of the reviewer gave, and the programs are in no file: not in the 'verbatim' review file, not in review_a45, and the worktree bella-r45 is gone. I rebuilt the third from its description and it agrees with the log's reading (D-04).

Evidence: imports.cpp:2340-2342: std::unordered_set<std::string_view> present; ... if (const Str* s = e.key.is_unset() ? nullptr : as_str(e.key)) present.insert(s->text);   (runtime.hpp:872: as_str 'nullptr unless a str'; is_exact_str is another function, line 424)
funcobject.c:157: PyFunction_NewWithQualName(PyObject *code, PyObject *globals, PyObject *qualname) ... 197: builtins = _PyDict_LoadBuiltinsFromGlobals(globals); ... 209-210: op->func_globals = globals; op->func_builtins = builtins;
git show --stat eb3b38b: docs/reviews/review-log.md | 2 +- (one file); ls the working checkout-r4*: only bella-r48.

p8_last rows exit_cycle and collect_cycle (a ModuleType in a cycle holding open('prog.py', 'rb')):
  CPython : ResourceWarning: unclosed file <_io.FileIO name='prog.py' mode='rb' closefd=True>
  compiled: ResourceWarning: unclosed file <_io.BufferedReader name='prog.py'>
row no_cycle: <_io.BufferedReader name='prog.py'> on both sides. The other lines that differ there are D-20's 'Enable tracemalloc' line and the recorded path.

Probe: p8_last (exit_cycle, collect_cycle, collect_text, no_cycle)

Suggested: Reword the two rows; keep a review's unnamed probes beside its file (or as test rows) when the log draws a conclusion from them.

> Verifier: **confirmed** (low). Wording slips in A45's records, all three quotations checked. (1) RL-947 (review-log.md:1359) says the names are found 'among the exact-str keys'; runtime/src/imports.cpp:2340-2342 takes every str key via as_str (core.cpp:589 returns non-null for any Str kind), so the RL-947 text is wrong. The comment at imports.cpp:2335-2336 ('the str keys (a subclass's read as stored)') is right, but DECISIONS.md:1930 says only 'found missing by their text' and does not mention subclasses, so the finding's 'as DECISIONS say' is an overstatement. (2) RL-945 (review-log.md:1357) cites '_PyFunction_FromConstruc ...

Minor, one line each, not verified:

- The three fixes of cf5304d themselves held in every row: 176 rows over eight probes, 148 SAME; of the 28 that differ none is caused by the commit's code (11 are findings 1, 2, 3 and 5's sys rows; 7 stop by name; 1 is D-08; 4 are D-04/D-13/D-20; 5 are p7_stdlib's shim and omitted-accelerator modules).
- object.__getattribute__(module, 'nope'): CPython "'module' object has no attribute 'nope'", compiled "module 'sample' has no attribute 'nope'" (p1_dir row descriptor; wording, D-08). runtime/src/types.cpp:557 builds it from Module::name, which after RL-943's fix stays '?' for a module made with a str subclass's name (by reading, not run).
- m.__dir__(1): CPython '__dir__() takes no arguments (1 given)', compiled '__dir__() takes 0 positional arguments but 1 were given' (p1_dir row descriptor; wording, D-08).
- The stop text 'dir() of names that are not all str (list.sort: step 3b)' (imports.cpp:2440) names list.sort as missing; the runtime has it and uses it thirteen lines above.
- dir(annotationlib) lists four names of the shim's own (_bella, _bella_refuse_text, _bella_refuse_eval, _bella_ast_expr): 42 names against CPython's 38 (p7_stdlib). The spec says the shim has 'every public name' and of _collections_abc 'Its namespace is CPython's'; tools/missing_names.py's surplus list looks at native modules only, so a shim's extra names are noticed by nothing.
- p7_stdlib: m.__dir__() of 78 manifest modules, 73 the same on both sides in content and order (traceback, logging, unittest.result, threading, _thread, posix, _io among them); datetime, decimal, hashlib and hmac differ as the omitted C accelerators and _hashlib explain (D-20).
- REPORT.md was not written: this session's Write tool refuses report files for a subagent ('return findings as text'), and I did not go around it. Each probe folder under review/c04-a45-fixes/ has prog.py, rows.txt and out.txt with both sides' full output; cpython_src/ has the fetched C files.

Covered: Commits cf5304d and eb3b38b at f4ba545, by reading the diff and the code around it and by nine builds through r48_both.py (eight probes, 176 rows; every probe folder has prog.py, rows.txt, out.txt). CPython's C was read from files fetched from the v3.15.2 tag (moduleobject.c, object.c, funcobject.c, frame.c, compile.c, typeobject.c, descrobject.c), never from memory.

RL-943 (a module's name), p2_name, 23 rows, 21 SAME: a str subclass's object as the name with __name__ replaced, deleted, the namespace cleared, __init__ again (exact, twice with subclass objects, by keyword with a tracked doc), release order, identity, a module in a cycle, ModuleType.__new__ alone, messages and e.name for seven kinds of name; then __main__ (attributes; __name__ rebound, deleted, 5, a subclass's object, and __module__ of what is made then), an imported module (spec, package, loader, qualnames, renamed, from-import of a missing name with e.name, e.name_from, repr with and without __spec__, __file__, __loader__), a package and submodule (relative imports after renaming, the sys.modules fall-back of 'from pkg import sub' by the package's present __name__), a module whose body raised and is imported again, a module taken out of sys.modules and re-imported, ModuleType reprs and argument errors, six native modules, math renamed, ModuleType.__init__ on an imported module. The two DIFF rows are findings 2 and 3.

RL-945 (a text's locals), p4_text 12 rows, p5_suggest 10 rows, p6_more 4 rows, all SAME: functions, classes, lambdas, generators, bound methods and closures made by a text and kept; the text raising with the exception kept; caught inside and kept or dropped; held through f_back; eval; locals(), vars(), dir(), globals() inside the text and written through; a class body, function, comprehension, generator expression and lambda in the text reading a name of its locals; builtins of the text's own and their release order; a cycle through the locals; one dict for both; dict displays as arguments; two runs over one locals; a text in a class body; dataclasses (slots, order, frozen, kw_only) and a namedtuple's __new__; the name suggestion from a text's frame while it runs, after it ended, after the locals were dropped, after clear_frames, in a class body, for self.x. Read: hold_globals, release_globals, let_go_of_namespace, the counted pair, the module's destroyer and traverser, frame_ends, take_ownership, i_traceback_names, frame_locals, from_frame, run.

RL-947 (dir of a module), p1_dir 18 rows and parts of p3, p6, p7, p8: keys with counting __hash__/__eq__ (SAME, also an instance's dir()), with __lt__ (finding 1); __dir__ at module level and __all__; module.__dir__() and ModuleType.__dir__(m); eleven kinds of value under __dir__; names added, deleted, cleared, astral and lone-surrogate names; a lazy import not resolved by dir(); a module in an import cycle; a package; __main__; math changed; sys, builtins, _abc, _types in full; m.__dir__() of 78 manifest modules.

locals(), vars(), dir() without an argument, p3_locals 17 rows: module level (read and written through), class body (also a __prepare__ mapping), functions (all parameter kinds, cells, free variables, a deleted cell, __class__, private names, lambdas, generators, generator expressions, after comprehensions and a walrus, exception and with variables, a class body in a function, generic functions), an imported module's body, argument errors: all SAME except the two rows inside a comprehension, which stop by name.

The test file and its three programs row by row; the A45 review file and the rows RL-943 to RL-947 against the C they cite; a rebuild of the third unnamed probe of eb3b38b. Each candidate finding was grepped in review-log.md, TODO.md, DECISIONS.md, the spec and deviations.toml before it was kept.

Not covered: RL-944 and RL-946 themselves (Questions 45 and 46) beyond the C that RL-944's row cites. The first two of the reviewer's three unnamed probes (a class's dict in gc.garbage; a failed import's function and a ModuleType in a cycle): kept nowhere, not rebuilt. A build without the fix to see the new rows fail (read-only checkout, r48_both.py only), so finding 4 (a) rests on reading rows and code. Module subclasses in sys.modules (the runtime stops at the subclass; writes to sys.modules are E-04). exec and eval with the frame's locals inside a function, and locals that are a mapping but no dict (both stop by name). A lean build; texts' locals in large cycles under the collector's load; the cost of the changed inline paths of hold_globals and release_globals. Whether findings 1 to 3 have further sites of the same class elsewhere in the runtime (other places that sort names as text, or print a qualified name where the C prints tp_name) was not swept. REPORT.md does not exist: the Write tool refused a report file in this session, so the account is this output plus the out.txt files under review/c04-a45-fixes/.


## c05-import-frames: the import system's frames (0c25f5e)

### F48-c05-import-frames-1 (RL-1057): The import system's own warnings lost CPython's stack level when its frames became shown

*defect, reported as high*; where: runtime/prelude/bootstrap.py:1877 and 1883 (_calc___package__); runtime/src/imports.cpp:167-170 (runtime_warning); runtime/prelude/_warnings.py:574; docs/DECISIONS.md line 1944; commit 0c25f5e

CPython's `_calc___package__` warns with `stacklevel=3` (`_bootstrap.py:1440-1442`, `1447-1449`), charging the caller of `importlib.__import__`. The prelude calls `_bella_import_warning(msg)`, which has no stack level. Since the step `_calc___package__` has a frame, so both warnings are charged to `<frozen importlib._bootstrap>` 1440/1447, module `importlib._bootstrap`: under the starting filters the DeprecationWarning CPython prints is not printed at all. Before the step the frame was hidden and the caller was charged (by reading the diff; the older commit was not built). DECISIONS 1944 says "`warnings` needed nothing". Narrow: only `importlib.__import__` with a level.

Evidence: `.venv/bin/python r48_both.py review/c05-import-frames/p3 --rows review/c05-import-frames/p3/rows.txt`
ROW ['package','default'], `importlib.__import__("s_plain", {"__package__": "pk", "__spec__": FakeSpec()}, None, ("value",), 1)`: CPython stderr `prog.py:93: DeprecationWarning: __package__ != __spec__.parent ('pk' != 'other')`; compiled stderr empty.
ROW ['package','always'] (showwarning replaced): CPython `warning DeprecationWarning __package__ != __spec__.parent ('pk' != 'other') prog.py 93`; compiled `... <frozen importlib._bootstrap> 1440`.
ROW ['noparent','always']: CPython `warning ImportWarning can't resolve package from __spec__ or __package__, ... prog.py 101`; compiled `... <frozen importlib._bootstrap> 1447`.
Control `package_c default` (builtin `__import__`, the C path): the warning is printed on both sides.
p1: rows `args c03 c04 c08 c09 c12 c14 c15 c17 c18` differ the same way, the only 9 of 440 caught rows that differ.
Code: bootstrap.py:1877 `_bella_import_warning("__package__ != __spec__.parent " f"(...)", "DeprecationWarning")`; CPython 1440-1442 `_warnings.warn(..., DeprecationWarning, stacklevel=3)`; imports.cpp:169 `invoke(warning_function(false), {msg.get(), Obj::of(exception_class(category))})`.
No case or test holds either warning's place: `grep -rn "__spec__.parent" pipeline/tests conformance/cases` finds only a print in imppkg/plain.py.

Probe: p3: package default, package always, noparent always, package_c default; p1: args c03 c04 c08 c09 c12 c14 c15 c17 c18

Suggested: Fix: give `_bella_import_warning` a stack level and pass CPython's 3 at the two sites (no run-time cost); add the two rows to C-8-22 or a test; correct the sentence in DECISIONS 1944.

> Verifier: **confirmed** (high). importlib.__import__ with level>0 and a __package__ differing from __spec__.parent (or neither set) warns from _calc___package__ with no stack level: the warning is charged to <frozen importlib._bootstrap> 1440/1447, so the DeprecationWarning CPython prints under default filters (prog.py:93, stacklevel=3) is not printed compiled. Introduced when the prelude's frames became shown (0c25f5e). Narrow reach; no cover; DECISIONS 1944 'warnings needed nothing' is false for these two calls.

### F48-c05-import-frames-2 (RL-1032, with the same subject): The A46 code-object sweep never reaches 23 of the table's functions; 7 of them differ and are missing from Question 48

*test, reported as medium*; where: pipeline/tests/test_review_2026_11_25_a46.py (docstring lines 15-18, table_names); docs/DECISIONS.md line 1950; docs/reviews/review-log.md RL-948; TODO.md:845-855 (Question 48)

`table_names()` asks for each function in its prelude's module, but 23 functions of `bootstrap.py` are `_bootstrap_external`'s by the table's own `file` (`_LoaderBasics` 3, `SourceLoader` 7, `FileLoader` 6, `SourceFileLoader` 3, four helpers). `importlib._bootstrap` has none of them on either side: 20 print `<absent>` and agree, 3 print nothing. So "of the 149 code objects ... 29 differ" counts 20 lines that are no code object. Reached where a program reaches them (`importlib._bootstrap_external`, `module.__loader__`), 7 more differ in `co_nlocals` and `co_varnames`: 36 differ, and Question 48's 25 lack six refused functions and `_LoaderBasics.exec_module`. The question is unanswered, so the list can still be corrected.

Evidence: p3 row `a46 x` (the test's program and names unchanged): 149 lines each side, 29 differ (exactly OPEN), 20 are `<absent>` on both, e.g. `_bootstrap.SourceLoader.get_code <absent>`, `_bootstrap._LoaderBasics.exec_module <absent>`.
p3 row `has x`: `SourceLoader in _bootstrap: False in _bootstrap_external: True` on both sides (the same for SourceFileLoader, FileLoader, _LoaderBasics, _check_name, _get_cached, _path_split, cache_from_source).
p3 row `moved x` (the 23 asked for in `_bootstrap_external`), 8 differ, 7 new:
FileLoader.get_data: CPython co_nlocals=3 ('self','path','file'), compiled 2 ('self','path')
SourceLoader.get_code: 15 against 2 ('self','fullname')
SourceLoader.get_source: 5 against 2
SourceFileLoader.path_stats: 3 against 2; ._cache_bytecode: 5 against 4; .set_data: 9 against 4
_LoaderBasics.exec_module: 3 ('self','module','code') against 2 ('self','module')
(the eighth, cache_from_source, is in OPEN already). Row `has x` gives the same seven through `type(t_plain.__loader__).__mro__`.
A traceback shows them too, p2 row `sp exec_wrong` (`spec.loader.exec_module(types.ModuleType("another"))`): CPython `exec_module 747, get_code 821, _check_name_wrapper 394`; compiled `exec_module 747, _check_name_wrapper 394`.

Probe: p3: a46 x, moved x, has x; p2: sp exec_wrong

Suggested: Fix the test: take the module from each row's `file`, fail on a name CPython lacks; add the seven to REWRITTEN and to Question 48's text before it is answered; correct the counts in DECISIONS 1950, RL-948 and TODO.

### F48-c05-import-frames-3 (RL-1058): Three lines of the table are wrong and show in tracebacks; `--check` regenerates by the same rule and cannot see them

*defect, reported as medium*; where: tools/bootstrap_frames.py:57-75 (line_map) and --check; runtime/prelude/bootstrap.py:1614, 628, 1620-1622, 188; runtime/prelude/bootstrap_frames.json

A rewritten stretch takes the first CPython line it replaces, right only where nothing stops. `_find_spec`'s `raise ImportError("sys.meta_path is None...")` (prelude 1614) is mapped to 1142, CPython's is 1144; `FrozenImporter.exec_module`'s `_bella_exec` (628) to 1092, CPython's `exec` is 1095; `_find_spec`'s finder calls (1620-1622) to 1157, CPython's call is 1164; `ModuleSpec.cached`'s call (188) to 620 for 622 (not observable). Only `_LoaderBasics.exec_module` has a `# cpython:`. `make verify` regenerates the table by the same rule, so it passes. Each is one line number in a traceback; every other mapped line I checked is right.

Evidence: audit/audit.py (CPython alone; every table function's AST against CPython's): `161 definitions, 96 identical in AST with every node's line right, 65 differing, 1 flagged`; flagged: `SAME statement, WRONG line: prelude 1614 -> 1142, CPython's is at 1144`. Table rows: `_find_spec ... [1614, 1142] ... [1620, 1157], [1621, 1157], [1622, 1157]`; `FrozenImporter.exec_module [[624, 1090], [625, 1091], [626, 1092], [627, 1092], [628, 1092]]`.
p4 rows `late`, `late_cycle` (a finaliser calling `importlib.import_module("t_never")` after the exit began; tb_lineno of each entry):
CPython: `ImportError: sys.meta_path is None, Python is likely shutting down at lines [88, 1389, 1353, 1238, 1144]`
compiled: `... at lines [88, 1389, 1353, 1238, 1142]`
p5 rows `rec N` (`import importlib.util` at the bottom of a recursion, limit 80; depths differ by D-17 and are not reported, the lines do not depend on them):
rec 60 CPython: `[1353, 1249, 857, 1095, 15, 11, 1353, 1238, 1164, 906, 665, 508]`
rec 60 compiled: `[1353, 1249, 857, 1092, 2, 3, 1353, 1249, 857, 1092, 85, 1338]`
rec 55 compiled: `[..., 1353, 1238, 1157, 906, 665, 508]`
`.venv/bin/python tools/bootstrap_frames.py --check` prints `bootstrap_frames: agree with CPython 3.15.2`.

Probe: audit/audit.out; p4: late, late_cycle; p5: rec 55 to rec 63

Suggested: Fix: `# cpython: 1144`, `1095`, `1164`, `622` on the four lines; make the tool refuse a non-equal stretch holding a call or a raise without an explicit `# cpython:`, so the check can fail.

> Verifier: **confirmed** (medium). Three (four) lines of bootstrap_frames.json are wrong: _find_spec's shutdown raise 1614 maps to 1142 (CPython 1144), the finder call 1620-1622 to 1157 (CPython 1164), FrozenImporter.exec_module's _bella_exec 628 to 1092 (CPython's exec is 1095), ModuleSpec.cached 188 to 620 (622, not observed). tools/bootstrap_frames.py --check regenerates by the same first-line rule so it cannot fail. Visible only as a traceback/stack line number of an import-system frame.

### F48-c05-import-frames-4 (RL-1059): `_fix_up_module` and `_bless_my_loader` in bootstrap_external.py are CPython 3.14's text, with no `bella:`

*wrong-fact, reported as medium*; where: runtime/prelude/bootstrap_external.py:876 and 425-465, docstring lines 6-7; tools/bootstrap_frames.py:10-12; docs/design.md section 10 ("The import system's frames"); commit cea5c1e (2026-11-09, older than the step)

The prelude, the step's tool and design.md say the text is CPython 3.15.2's except where a line says `bella:`. `_fix_up_module` sets `ns['__cached__'] = cpathname`, which 3.15.2 does not (3.14.0 does, line 1525); `_bless_my_loader` lacks 3.15.2's lines 637-639 (the `__main__` case), as 3.14.0 does. Neither says `bella:`. Compiled, `_fix_up_module` sets `__cached__`; `_bless_my_loader` for `__main__` globals stops with a message about a DeprecationWarning that 3.15.2 does not issue, or raises ValueError where CPython returns None. Private helpers, small effect; the point is that the stated premise is unchecked. 46 more unmarked stretches are plain `_bella_refuse` or `_os_getcwd` rewrites.

Evidence: audit/unmarked.py (differing stretches with no `bella:` on or above them): `48 functions`; among them `_fix_up_module [delete] prelude 876: ns['__cached__'] = cpathname  CPython: (nothing)` and `_bless_my_loader [insert] CPython 638: if spec is None and module_globals.get('__name__') == '__main__': | return loader`.
CPython 3.15.2 `_bootstrap_external.py:1554-1557` sets `__spec__`, `__loader__`, `__file__` only; `grep -n __cached__` over its `_bootstrap.py` and `_bootstrap_external.py` finds nothing. v3.14.0 (fetched to cpython-314/, only read) has `ns['__cached__'] = cpathname` at 1525 and no `__main__` case.
p5:
ROW ['fix'] `_fix_up_module(ns, "m", "/nowhere/m.py", "/nowhere/m.pyc")`: CPython `names set ['__file__', '__loader__', '__spec__'] cached <not set>`; compiled `names set ['__cached__', '__file__', '__loader__', '__spec__'] cached /nowhere/m.pyc`
ROW ['bless_main_loader'] `_bless_my_loader({"__name__": "__main__", "__spec__": None, "__loader__": Loader()})`: CPython `blessed <the loader>`; compiled status 70, `bella: not implemented: _bless_my_loader's DeprecationWarning for a module without __spec__.loader (...)`
ROW ['bless_main_none']: CPython `blessed None`; compiled `ValueError Module globals is missing a __spec__.loader`
ROW ['bless_plain'] (control): SAME.

Probe: audit/unmarked.out; p5: fix, bless_main_loader, bless_main_none, bless_plain

Suggested: Fix both functions to 3.15.2's text; make `tools/bootstrap_frames.py --check` fail on a non-equal stretch with neither `bella:` nor a `_bella_` call, which holds the sentence mechanically.

> Verifier: **confirmed** (medium). Two functions in the bootstrap_external prelude are not 3.15.2's text and say nothing: _fix_up_module sets ns['__cached__'] (3.14's), and _bless_my_loader lacks the __main__ case (lines 637-639), so compiled it stops with a DeprecationWarning refusal or raises ValueError where CPython returns the loader/None. The prelude docstring, tool header and design.md claim the text is unchanged except where marked 'bella:'. Numbers: c05 is right (two functions among 48 unmarked-differing; the other 46 are _bella_refuse stops or _os_* rewrites). c06-7 and q43-7 name only _fix_up_module because their coun ...

Minor, one line each, not verified:

- runtime/prelude/bootstrap.py:20-22 says an ImportWarning "is refused" once a warnings module could have changed the filters; it is issued through the _warnings prelude and shown (p3, row `noparent always`).
- importlib.util.find_spec("t_plain.sub"): the `raise ... from e` written over three lines is at line 96 compiled and 94 under CPython (p2, row `sp find_spec_notpkg`); RL-494's open class, seen in the standard library.
- C-8-22 holds stack levels 1 and 2 from one body and five tracebacks, but no row for importlib.__import__, module __getattr__ under _handle_fromlist, a lazy import's first use or the import system's own warnings; p1/gen.py and p2/gen.py generate the class's sweep and could be kept as its test.
- traceback.extract_tb entries have no colno or end_colno and end_lineno equals lineno for every frame compiled, where CPython has them for the import system's frames too (p2, row `sp fmt_im`); not of this step, and I did not find it under D-06's words ("traceback line text").
- A row I first took for an anomaly is not one: compiled `rec 68` in p5 shows a single entry at line 60, which is importlib/__init__.py:60 running under the recursion because the package is not imported at start (D-30).

Covered: Five builds of 25 used (p1 to p5, all through r48_both.py); 816 rows, 744 agree outright and the other 72 are each accounted for (the four findings, the harness's main file name, D-06's source lines, [P2+] stops, D-17 depths, one slip of my own probe).

Table, mechanically (audit/audit.py, CPython alone): all 158 rows, 161 definitions; every definition lands on a CPython definition of its name (getters, setters, POSIX variants); for the 96 functions whose AST is CPython's, every node's lineno and end_lineno; for the 65 others a statement-by-statement alignment listing how each line was mapped (audit/audit.out). audit/unmarked.py and audit/surface.py: unmarked differences, signatures, decorators, docstrings, class bases, module-level assignments, names CPython lacks.

p1 (451 rows, 431 SAME): 23 routes (import a, import a.b, import a.b as c, from a import name, from a import b, from a.b import name, from . import x and from .x import name in a package, import_module plain/dotted/with package, __import__ and importlib.__import__ plain/dotted/fromlist/level) by 9 outcomes (success with extract_stack, sys.exception() and warnings.warn at stack levels 1 to 9 in the body; no such module; ValueError; explicit cause; implicit context; ImportError with attributes; circular from-import of a missing name; circular attribute read; nested failing import); 7 routes again in a class body and in an except clause; module level; no such name, not a package, no parent, bad relative imports, import * over a bad __all__; 51 rows of wrong argument types and values. Observed: extract_tb entries, type, str, name, path, name_from, msg, __suppress_context__, __notes__, cause and context chains with their entries, sys.exc_info.

p2 (260 rows, 241 SAME): a lazy import's first use (8 forms by 9 outcomes, in a function and at module level, relative in a package); module __getattr__ under _handle_fromlist and _find_and_load_unlocked; a package without __spec__; imports inside __init__; three levels; module repr through _module_repr; an exception carrying an earlier import's entries raised again in a new import (trimmed as CPython trims it); exec_module called by the program; logging stack levels and stack_info; traceback formatting; 60 lifetime rows (10 routes by 6 ways of holding the exception or its traceback), all SAME.

p3 (22 rows): the A46 sweep reproduced and the functions it missed; the warnings of finding 1; SystemExit, KeyboardInterrupt, ExceptionGroup and a program's ImportError subclass from a body and from __getattr__ (SAME); sys.modules after failures (SAME). p4 (32 rows, 29 SAME): imports in a generator, generator expression, comprehension, lambda, closure, finally, with body, __enter__, __exit__, contextmanager, property, __del__, atexit; a package importing its submodules in __getattr__; import * over __all__; a module importing itself; a failed import repeated; the late import. p5 (51 rows): finding 4 and the lines of finding 3.

Read against CPython's source (fetched v3.15.2 Python/import.c and Python/_warnings.c, only read): remove_importlib_frames, PyImport_ImportModuleLevelObject, PyImport_GetModule, _PyImport_TryLoadLazySubmodule against runtime/src/imports.cpp (the port is link for link and the entry points call the prelude where the C calls it); setup_context against the _warnings prelude; mark_frames, the code record in pipeline/backend/cpp.py, pipeline/build.py's key.

DECISIONS 1944-1952: 147 functions (66 and 81) at 0c25f5e right; the baselines right; "import_module has no such exit and keeps them" right; "warnings needed nothing" is finding 1; "149 code objects, 29 differ" is finding 2. The tracked checkout is untouched.

Not covered: REPORT.md was not written: the Write tool refused a report file in this session ("Subagents should return findings as text"), and I did not work around it. The full account is in this output; the probes, generators, both.out files and audit scripts are under review/c05-import-frames/ (p1 to p5, audit/, cpython-src/, cpython-314/, normal.py, split.py, run_cpython.py).

The older commit was not built, so "before the step: no entry on any stack, a depth of 56" was not rerun, and that finding 1 is a regression rests on reading the diff of pipeline/backend/cpp.py.

Not examined: the eval1 and eval2 legs, a lean build, aarch64, the cost of the linked frames; signals in importlib's code (D-25), recursion depth (D-17), the module locks (D-33), names that are str subclasses (RL-954, RL-955), by instruction or because already open; the two ImportWarnings of _find_and_load_unlocked (1260, 1266), which need __class__ assignment on a module ([P2+] stop) or a write to sys.modules (E-04), so only read; A46's other fixes (native modules' order, the decorators); pkgutil, unittest's loaders, importlib.resources; gc.collect() counts after failed imports; frame objects (E-02).


## c06-a46-fixes: review A46's fixes (477dddc)

### F48-c06-a46-fixes-1 (RL-1032, with the same subject): The code-object sweep never compares 19 functions; eight more differ, so RL-948's '29 of 149' and Question 48's '27 ... the other 25' are short

*wrong-fact, reported as high*; where: pipeline/tests/test_review_2026_11_25_a46.py:69-73 (table_names) and review_a46/codeobjects/prog.txt; TODO.md:845-855 (Question 48); docs/DECISIONS.md:1950; review-log RL-948 and RL-949

table_names() looks each function up in the module named after the prelude that defines it. bootstrap.py also holds 25 functions CPython defines in _bootstrap_external (FileLoader, SourceLoader, SourceFileLoader, _LoaderBasics, ...); under importlib._bootstrap they are '<absent>' on both sides, which counts as agreeing. 19 code objects are never compared, nor the functions behind the wrappers. Reached in CPython's module, 36 of 148 differ, not 29, plus one wrapped function: eight differing functions are in neither LOCKS nor REWRITTEN, so Question 48's '27 ... the other 25' is 35 and 33. '149 code objects' counts 20 <absent> lines. RL-949's 'seven methods' are nine, for the same reason.

Evidence: p4-sweep, build 4. Row astest (the test's reach): 129 real code objects, 29 differ (exactly OPEN), 20 lines '<absent>' on both sides, e.g. '_bootstrap.SourceLoader.get_code <absent>' under CPython and compiled. Row athome (each name in the module of the table's `file`): 148 code objects, 36 differ; 9 wrapped functions, 1 differs. The eight outside OPEN, co_nlocals CPython / compiled: FileLoader.get_data 3 ('self','path','file') / 2; the function FileLoader.get_resource_reader wraps 3 ('self','module','FileReader') / 2; SourceFileLoader._cache_bytecode 5 / 4; SourceFileLoader.path_stats 3 / 2; SourceFileLoader.set_data 9 / 4; SourceLoader.get_code 15 ('self','fullname','source_path',...,'code_object') / 2 ('self','fullname'); SourceLoader.get_source 5 / 2; _LoaderBasics.exec_module 3 ('self','module','code') / 2. Never compared by the test: FileLoader.__eq__, __hash__, __init__, get_data, get_filename, get_resource_reader; SourceFileLoader._cache_bytecode, path_stats, set_data; SourceLoader._cache_bytecode, get_code, get_source, path_mtime, path_stats, set_data, source_to_code; _LoaderBasics.create_module, exec_module, is_package. CPython alone (cpy/codeobjects): the test's own program with the table's names prints those 20 '<absent>' lines.

Probe: p4-sweep, rows astest and athome; cpy/codeobjects (CPython alone)

Suggested: Reach each name in the module of the table's `file`; fail on <absent> or a non-code object on CPython's side; follow a wrapper's closure to what it wraps. Add the eight to REWRITTEN and to Question 48's text and counts before its answer is carried out.

### F48-c06-a46-fixes-2 (RL-1060): An argument error names a function by its code object's qualname, not by the function's __qualname__ (functools.wraps wrappers, and the nine decorated loader methods)

*defect, reported as high*; where: runtime/src/call.cpp:253 (bind: `who` from c.qualname), used at 286, 293, 316, 336; shown by runtime/prelude/bootstrap.py _wrap and the decorators of 477dddc

CPython words the binder's TypeErrors with func->func_qualname (Python/ceval.c 1815-1963 of v3.15.2, fetched and read), which functools.wraps, update_wrapper, the import system's _wrap or an assignment change. The runtime takes the code object's qualname. So a functools.wraps wrapper called with wrong arguments ([P1], spec section 3, Functions: 'functools.wraps metadata') gives another message, and since this commit so do the nine decorated loader methods. General and older than the commit; not in the review log or TODO; the commit's test has no wrong-arity row for a _requires_* wrapper. repr() of the function and a generator's __qualname__ agree.

Evidence: p2-order row qual, p4-sweep row qual2, p1-decor rows 'builtin-odd get_code args', 'frozen-odd get_source args', filename.
CPython: wraps none ("area() missing 1 required positional argument: 'x'",)
compiled: wraps none ("deco.<locals>.wrapper() missing 1 required positional argument: 'x'",)
CPython: renamed two ('Renamed.g() takes 1 positional argument but 2 were given',)
compiled: renamed two ('g() takes 1 positional argument but 2 were given',)
CPython: kwonly none ("target() missing 1 required keyword-only argument: 'k'",)  [functools.update_wrapper]
compiled: kwonly none ("kwonly() missing 1 required keyword-only argument: 'k'",)
CPython: two raised TypeError ('BuiltinImporter.get_code() takes 2 positional arguments but 3 were given',)
compiled: two raised TypeError ('_requires_builtin.<locals>._requires_builtin_wrapper() takes 2 positional arguments but 3 were given',)
CPython: class call no self raised TypeError ("FileLoader.get_filename() missing 1 required positional argument: 'self'",)
compiled: ... ("_check_name.<locals>._check_name_wrapper() missing 1 required positional argument: 'self'",)
Also a method, a classmethod and a lambda with __qualname__ assigned, and an unexpected or repeated keyword. runtime/src/call.cpp:253: std::string who = std::string(c.qualname) + "()";

Probe: p2-order row qual; p4-sweep row qual2; p1-decor rows 'builtin-odd get_code args', 'frozen-odd get_source args', filename

Suggested: A conformance case first (a functools.wraps wrapper called with too few, too many and unknown keyword arguments), then take `who` from the function's own qualname; grep the other messages built from code.qualname.

> Verifier: **confirmed** (high). bind() (runtime/src/call.cpp:253) words every argument TypeError with the code object's qualname; CPython 3.15.2 ceval.c uses func->func_qualname (1815-1963), which functools.wraps, an assigned __qualname__ or the import system's _wrap change. So a functools.wraps wrapper, a function with assigned __qualname__ and the nine decorated loader methods give another message. Spec section 3 lists functools.wraps metadata as [P1]; no exclusion, deviation, review-log, TODO or DECISIONS entry covers it.

### F48-c06-a46-fixes-3 (RL-1033, with the same subject): The rewritten test of _requires_builtin_wrapper: SIGSEGV for a name that is no str, and ImportError for 50 names of sys.builtin_module_names

*defect, reported as high*; where: runtime/prelude/bootstrap.py:72 (the wrapper), 434 (find_spec), 443 (create_module); runtime/src/imports.cpp:1419-1423 (i_bella_is_builtin); review-log RL-949

The wrapper is CPython's text but for its test, `_bella_is_builtin(fullname)`, noted as `fullname not in sys.builtin_module_names`. It is not that: (a) i_bella_is_builtin dereferences as_str() unchecked, so a name that is no str ends the program with SIGSEGV in get_code, get_source, is_package, find_spec and create_module, where CPython raises ImportError or TypeError; (b) for the 50 names of sys.builtin_module_names the runtime does not write (array, marshal, select, ...) the three methods raise ImportError where CPython answers None, None, False, though the program's own sys.builtin_module_names lists them; (c) a replaced tuple is ignored. Older than the commit, kept by it; RL-949's rows try sys and nope only.

Evidence: p1-decor rows 'builtin get_code|get_source|is_package', 'builtin-odd get_code int|none|bytes|tuple|list|names'; p4-sweep rows 'odd ...'; p2-order row impnone.
CPython: int raised ImportError ('1 is not a built-in module',) name=1 ... [('<frozen importlib._bootstrap>', '_requires_builtin_wrapper', 506)]
compiled: status -11, no output (also None, b'sys', ('sys',), ['sys'], 1.5, object())
CPython: find_spec-int raised TypeError ('is_builtin() argument must be str, not int',) | compiled: status -11
CPython: create-int raised ImportError ('5 is not a built-in module',) | compiled: status -11
CPython: get_code _asyncio -> None ; is_package _asyncio -> False
compiled: get_code _asyncio raised ImportError ("'_asyncio' is not a built-in module",) name='_asyncio' ... '_requires_builtin_wrapper', 506   (the same for 50 of the 101 names)
Both sides: is_builtin array 1 True  ('array' in sys.builtin_module_names); find_spec array: CPython ('array', 'built-in', True), compiled None.
sys.builtin_module_names = ('nope',): CPython nope -> None, sys raised ImportError; compiled the reverse.
runtime/src/imports.cpp:1421: const std::string& name = as_str(a.pos(0))->text;
D-20 lists what it accepts ('only the differences listed here') and has none of this.

Probe: p1-decor rows 'builtin ...' and 'builtin-odd ...'; p4-sweep rows 'odd ...'; p2-order row impnone

Suggested: Fix the crash now: a type check in i_bella_is_builtin with _imp.is_builtin's TypeError. Then CPython's line in the wrapper and create_module (start-up can keep its own test), or an entry saying what the 50 names answer: the author's.

### F48-c06-a46-fixes-4 (RL-1061): RL-951's fix leaves out sys and builtins, the only native modules with unfilled names, so __dir__'s rank merge never works as design.md says

*inconsistency, reported as medium*; where: runtime/src/imports.cpp:1427-1428 and module_dir_m (2327 on); runtime/src/call.cpp:4317-4340; docs/design.md:812; review-log RL-951; docs/DECISIONS.md:1948; pipeline/tests/review_a46/nativeorder/prog.txt

order_as_cpython runs only in _bella_create_builtin; sys and builtins are returned before it and keep the runtime's order. They are the only native modules with unfilled names (names-baseline: sys 50, builtins 3), so the rank merge the commit added to module_dir_m, and design.md's sentence on it, hold for no module: on sys the first key (argv, rank 108) is followed by exit (rank 16) and the unfilled names left are flushed there. sys.__dir__() has CPython's 120 names in another order; nothing records sys (builtins: RL-492, open). RL-951 says Fixed, DECISIONS 'All 47 native modules agree'. The test's list of 47 is written by hand and omits _abc, _types, sys, builtins.

Evidence: p2-order, build 2, 115 rows. The 49 modules of the registry: 'fwd <module>' 49 SAME (list(vars(m)), m.__dir__(), m.__dict__ iteration, dir(m)); 'rev ALL' and 'heavy ALL' SAME (imports reversed; after 41 library imports); 'mut <module>' 49 SAME (add, delete, set again, pop, setdefault, update). CPython alone (cpy/stable.py): each module's order is the table's whether imported alone or after some fifty imports. Rows 'fwd sys', 'fwd builtins': DIFF.
CPython sys.__dir__(): [..., '__spec__', 'addaudithook', 'audit', 'breakpointhook', ..., 'displayhook', 'exception', 'exc_info', 'excepthook', 'exit', ...]
compiled sys.__dir__(): [..., '__spec__', 'addaudithook', 'breakpointhook', (48 more unfilled names), 'argv', 'orig_argv', '_home', '__interactivehook__', 'exit', 'intern', 'exc_info', 'exception', ...]
compiled list(vars(sys)): [..., '__spec__', 'argv', 'orig_argv', 'exit', 'intern', 'exc_info', 'exception', 'excepthook', ...]; CPython vars 120, compiled 70, the 70 in another relative order.
compiled list(vars(builtins)): [..., 'str', 'type', 'bool', 'range', ...]; CPython: [..., '__build_class__', '__import__', '__lazy_import__', 'abs', ...].
runtime/src/imports.cpp:1427-1428 return sys and builtins before line 1437's order_as_cpython.

Probe: p2-order rows 'fwd sys', 'fwd builtins', 'rev ...', 'heavy ...', 'mut ...', 'sysmut ...', 'bltmut ...'; cpy/stable.py

Suggested: Lay out sys and builtins by the table at the end of start-up (its rows exist; closes RL-492), or record both as open in RL-951 and design.md. Build the test's module list from closure.lock.json, and add a row that reaches the merge.

> Verifier: **confirmed** (medium). sys and builtins are returned by _bella_create_builtin (imports.cpp:1427-1428) before order_as_cpython (1437), so their namespaces stay in the runtime's order. sys.__dir__(): same 120 names, 113 positions differ; vars(sys): 70 of CPython's 120 names (the 50 are the names-baseline's), 65 positions differ. builtins: order differs (known, RL-492 open, TODO.md:948); its 6 site names are excluded by the spec's Builtins row. RL-951/DECISIONS:1948 'All 47 native modules agree' do not say sys/builtins are outside; sys is recorded nowhere. Correct counts: table has 54 names but math.integer is _math_in ... Cover: builtins only: RL-492 'Open' and TODO.md:948 'the builtins' namespace in CPython's order'; site names: spec section 3 Builtins row. sys: nothing.

### F48-c06-a46-fixes-5 (RL-1062): _make_relax_case's case-insensitive branch names _os, which the prelude does not define: NameError (new with this commit)

*defect, reported as medium*; where: runtime/prelude/bootstrap_external.py:53; pyproject.toml:45; review-log RL-948 ('CPython's text, which runs on linux as it is')

The commit made _make_relax_case CPython's text ('which runs on linux as it is', RL-948). Its first branch returns a function that reads `_os.environ`, and bootstrap_external.py defines no `_os` (it uses _os_getcwd and _os_fspath; `_frozen_importlib_external._os` stops by name). So the function made for a case-insensitive platform raises NameError where CPython answers False or True: a wrong exception, not a stop. Reached by a program that sets sys.platform and calls the private function, so rare; but new with this commit (before, the prelude returned the constant function), and ruff does not see it, since pyproject.toml excludes the two bootstrap preludes.

Evidence: p4-sweep row relaxwin (sys.platform set, then e._make_relax_case()()):
CPython: win32 67 ('key',) False | darwin 67 ('key',) False | cygwin 67 ('key',) False | linux 71 () False
compiled: win32 raised NameError ("name '_os' is not defined",) | darwin the same | cygwin the same | linux 71 () False
p3-lines row relax-odd: compiled NameError at ('<frozen importlib._bootstrap_external>', '_relax_case', 69). CPython side of p3-lines row relax: with PYTHONCASEOK in posix.environ the answer is True for the platform's key type (bytes for darwin, str for win32).
runtime/prelude/bootstrap_external.py:53: return not sys.flags.ignore_environment and key in _os.environ
`grep -n '\b_os\.' runtime/prelude/bootstrap_external.py`: line 53 and three comments.
pyproject.toml:45: extend-exclude = [..., "runtime/prelude/bootstrap.py", "runtime/prelude/bootstrap_external.py"]
Control: _get_supported_file_loaders agrees in every row tried (p3-lines row loaders: result, list identities, sys.platform ios/tvos/watchos/darwin/win32, a replaced _imp.extension_suffixes, _imp.create_dynamic deleted and put back).

Probe: p4-sweep row relaxwin; p3-lines rows relax, relax-odd, loaders

Suggested: Give the prelude CPython's `_os` (the posix module as a global, which also ends the stop on _frozen_importlib_external._os), or mark the line `bella:` with a stop by name. Add the three platforms to the test's relax row.

> Verifier: **confirmed** (low). runtime/prelude/bootstrap_external.py:53 (CPython's text since 477dddc) reads _os.environ in the case-insensitive branch of _make_relax_case; the prelude defines no _os, so on a reassigned sys.platform of win32/darwin/cygwin/ios the function made raises NameError where CPython returns False. Only reachable by assigning sys.platform and calling the private _make_relax_case; real linux runs the else branch and agrees. It is the only genuine undefined name in the file (ruff F821). RL-948's 'runs on linux as it is' is literally true. Severity low, not medium: wrong exception rather than a stop, ne ... Cover: Stop by name for reading _frozen_importlib_external._os only; DECISIONS.md:1950/RL-948 'CPython's text, which runs on linux as it is' does not claim other platforms.

### F48-c06-a46-fixes-6 (RL-1063): ModuleSpec.cached's getter reports line 620 for its call of _get_cached; CPython 622

*defect, reported as medium*; where: runtime/prelude/bootstrap.py:188; runtime/prelude/bootstrap_frames.json (ModuleSpec.cached); pipeline/tests/review_a46/getters/prog.txt; review-log RL-952

RL-952 gave each property's getter its own lines, and the first lines are right. But the getter of `cached` calls _get_cached on a line the prelude rewrote (`_get_cached(...)` for `_bootstrap_external._get_cached(...)`), and the table gives a rewritten stretch the first CPython line it replaces: 620 (`if _bootstrap_external is None:`), where CPython's call is on 622. A traceback or a stack through the getter shows 620. The test's `raised` row calls each getter with object(), which fails on the first statement, so it cannot see this. The remedy the tool already has is a trailing `# cpython: 622`.

Evidence: p3-lines row deep (a ModuleSpec with origin=5 and has_location True, then spec.cached):
CPython: cached with an int origin AttributeError ("'int' object has no attribute 'endswith'",) [('<frozen importlib._bootstrap>', 'cached', 622), ('<frozen importlib._bootstrap_external>', '_get_cached', 359)]
compiled: ... [('<frozen importlib._bootstrap>', 'cached', 620), ('<frozen importlib._bootstrap_external>', '_get_cached', 359)]
runtime/prelude/bootstrap_frames.json, ModuleSpec.cached: [[183,616],[184,617],[185,618],[186,619],[187,620],[188,620],[189,623],[191,625],[192,626],[193,627]]
Everything else on the three properties agrees (rows props, raise-get, raise-set, deep): co_firstlineno 616/625, 629, 637/641; raising in each getter (618, 632, 639) and setter (627, 643, also by assignment with a __bool__ that raises); parent at 633; fdel None; no setter, no deleter messages. Static (cpy/frames_static.py): over all 158 functions every line whose text occurs once on both sides maps to it and every first line to CPython's first line; 0 problems. cpy/stretches.txt lists the 89 prelude code lines given a CPython line of other text (FrozenImporter.exec_module's _bella_exec is given 1092, CPython's exec is on 1095: read, not run).

Probe: p3-lines rows deep, props, raise-get, raise-set; cpy/frames_static.py, cpy/stretches.txt

Suggested: `# cpython: 622` on bootstrap.py:188, the table regenerated, and a row in getters that raises below the call. Walk cpy/stretches.txt for the other rewritten lines that are calls.

> Verifier: **confirmed** (low). ModuleSpec.cached's getter reports line 620 for its _get_cached call where CPython reports 622: bootstrap.py:188 is a line the closed world rewrote (`_get_cached(...)` for `_bootstrap_external._get_cached(...)`) with no `# cpython: 622` override, so the table gives it the first line of the replaced stretch. RL-952's getters test cannot see it. Reach is very narrow (an exception raised through the getter).

### F48-c06-a46-fixes-7 (RL-1059, with the same subject): _bootstrap_external._fix_up_module sets __cached__, which CPython 3.15.2's text does not

*defect, reported as low*; where: runtime/prelude/bootstrap_external.py:876; pipeline/tests/test_review_2026_11_10.py (test_the_bootstrap_preludes_keep_the_pins_parameters_and_docstrings)

_bootstrap_external._fix_up_module in the prelude ends with `ns['__cached__'] = cpathname`. CPython 3.15.2's function sets __spec__, __loader__ and __file__ only (Lib/importlib/_bootstrap_external.py:1555-1557); the line is an older release's. No `bella:` note marks it, and no test compares the preludes' bodies with the pin: the one that turned the night red compares parameters and docstrings. Of the 57 prelude lines inside the table's functions that are not CPython's text and carry no note, this is the only one that is neither a stop, an _os_* helper nor part of a noted stretch.

Evidence: p3-lines row fixup (e._fix_up_module(ns, 'm', '/nowhere/m.py', '/nowhere/__pycache__/m.pyc'), then sorted(ns)):
CPython: ['__file__', '__loader__', '__spec__'] <absent> /nowhere/m.py SourceFileLoader /nowhere/__pycache__/m.pyc
compiled: ['__cached__', '__file__', '__loader__', '__spec__'] /nowhere/__pycache__/m.pyc /nowhere/m.py SourceFileLoader /nowhere/__pycache__/m.pyc
Without the fourth argument: CPython ['__file__', '__loader__', '__spec__'] <absent>; compiled ['__cached__', ...] None.
runtime/prelude/bootstrap_external.py:876: ns['__cached__'] = cpathname
.venv/bin/python review/c06-a46-fixes/cpy/unmarked.py: 57 lines, 876 among them.

Probe: p3-lines row fixup; cpy/unmarked.py

Suggested: Delete the line. Keep a check beside the parameters test that every prelude line differing from the pin's function carries a `bella:` note (cpy/unmarked.py is a start).

### F48-c06-a46-fixes-8 (RL-1064): tools/missing_names.py does not import _thread, which joined the names table with this commit

*follow-through, reported as low*; where: tools/missing_names.py:115 against tools/cpython_names.py:310; conformance/names-baseline.txt

The commit put _thread, the manifest's one shim of a built-in, into the names table (tools/cpython_names.py:310 now takes core, mapped and shim), so its absent names stop by name. tools/missing_names.py still builds its program from the manifest's mapped and core lists (line 115) and compares a module's names only for the modules that program prints. _thread's rows are therefore compared in neither direction (missing, surplus), and conformance/names-baseline.txt, which the commit did not touch, cannot notice a _thread name that goes missing. Nothing is missing today.

Evidence: tools/missing_names.py:115: modules = [m for m in manifest["mapped"] + manifest["core"] if m not in NOT_IMPORTED and m not in ("builtins", "sys")]
tools/cpython_names.py:310: native = sorted(n for n, m in lock["modules"].items() if m["status"] in ("core", "mapped", "shim") and m["kind"] == "builtin")
closure.lock.json: the only built-in with status shim is _thread.
p2-order row 'fwd _thread': SAME, 34 names in vars(_thread) on both sides, so the gap hides nothing now.
`git show --stat 477dddc`: conformance/names-baseline.txt is not among the 25 files.

Probe: p2-order row 'fwd _thread' (the rest by reading)

Suggested: Take the tool's module list from the lock with the same three statuses, or share one function with cpython_names.py.

> Verifier: **confirmed** (low). tools/missing_names.py builds its module list from manifest mapped+core only (line 115), and _thread is in neither list: it appears only in the [phase1.shim] table (manifest.toml line 108). cpython_names.py line 310 takes core, mapped and shim builtins, so the names table has 34 _thread rows (runtime/src/cpython_names.inc) that missing_names.py never compares in either direction. commit 477dddc does not touch conformance/names-baseline.txt (its 25 files were listed) and the baseline has no _thread rows. Nothing is missing today: the stored p2-order output (review/c06-a46-fixes/p2-order/out.txt ...

Minor, one line each, not verified:

- _imp.is_builtin, is_frozen, is_frozen_package, init_frozen, find_frozen and get_frozen_object given None say 'must be str, not NoneType'; CPython says 'not None' (_PyArg_BadArgument, Python/getargs.c:663-670, read). runtime/prelude/_imp.py:47-48, 88. p2-order row impnone; also through FrozenImporter.get_source(None) in p1-decor. The other preludes' messages of this shape were not swept.
- The function a _check_name wrapper wraps has __module__ '_frozen_importlib' for FileLoader.get_filename and get_resource_reader (CPython '_frozen_importlib_external'), and FileLoader.get_filename.__globals__['__name__'] is 'importlib._bootstrap' (CPython 'importlib._bootstrap_external'): the class lives in bootstrap.py. p1-decor rows 'attrs 6', 'attrs 7', globals.
- ExtensionFileLoader.get_filename.__code__ is FileLoader.get_filename.__code__: True in CPython, False compiled (one copy of _check_name per prelude). p1-decor row extension.
- f4ba545's test docstring and comment cite 'D-34' (pipeline/tests/test_review_2026_11_10.py:1061, 1065); the register in docs/deviations.toml and the spec ends at D-33 at that commit.
- _get_cached tests the literals '.py' and '.pyc' where CPython reads SOURCE_SUFFIXES and BYTECODE_SUFFIXES (runtime/prelude/bootstrap.py:1394, 1399; read only, and for '.py' the answer is None either way under D-16). Its code object agrees, so it is in no list of rewritten functions.
- By reading module_dir_m: once a program deletes and sets again keys in rising rank, the unfilled names CPython has before them are listed after them. No module can show it today (finding 4), so it is not run.
- The DECISIONS entry and RL-951 count '47 native modules'; closure.lock.json has 51 built-in module objects (49 made by _bella_create_builtin, sys, builtins). _abc and _types agree but are in no test row.
- REPORT.md was not written: this session's Write tool refuses a report file from a sub-agent ('return findings as text'), and I did not work around it. The full account is this output; every program, row file and both sides' output is in the probe folders.

Covered: Read: the whole diff of 477dddc (both preludes, call.cpp's cpython_order_of and order_as_cpython, imports.cpp's i_bella_create_builtin and module_dir_m, tools/bootstrap_frames.py, tools/cpython_names.py, the A46 test and its five programs), design.md's paragraph, the DECISIONS entry, TODO's Question 48, review A46, RL-947 to RL-957, and f4ba545. Four builds of 25, all through r48_both.py; folders under review/c06-a46-fixes/ each hold prog.py, rows.txt and out.txt.

p1-decor (55 rows): each of the nine decorated methods: names, qualnames, module, docstring, __wrapped__, __dict__, defaults, annotations, the code object's names and counts, the closure and the wrapped function, classmethod.__wrapped__, bound methods and reprs; get_filename with 40 argument shapes (right, wrong, None, keywords, extra arguments, int, tuple, list, bytes, dict, str subclasses with __eq__/__ne__/__hash__, objects without `name`, through the class and a subclass, loaders with an int or tuple name); get_resource_reader's refusals; ExtensionFileLoader; the three BuiltinImporter methods over all 101 built-in names and 7 others, odd arguments, a replaced sys.builtin_module_names; the FrozenImporter methods over the 29 frozen names and 8 others, a patched _imp.is_frozen; the decorators and _wrap on a program's own functions and objects. All tracebacks and lines agree but for findings 1 to 3 and the minor list.

p2-order (115 rows): list(vars(m)), m.__dir__(), m.__dict__ iteration and dir(m) for all 51 native modules, imported forwards, in reverse and after 41 library imports; add, delete, re-add, pop, setdefault, update on each of the 49 registry modules; sys and builtins separately. CPython alone (cpy/stable.py): the order of each module is the table's under two import histories. The table: recorded inside the probe process, consistent per module with the names table, sorted for the binary search; `tools/cpython_names.py --check` and `tools/bootstrap_frames.py --check` run and agree, so make verify catches a stale table when the pin or the lock changes.

p3-lines (10 rows): the three properties (getter, setter, no deleter): code objects, raising in each, by call and by attribute access; _make_relax_case over 12 platform names and four PYTHONCASEOK states; _get_supported_file_loaders; _fix_up_module; _get_cached. Static: cpy/frames_static.py (the whole frames table against both texts, 0 problems), cpy/stretches.py, cpy/unmarked.py.

p4-sweep (11 rows): the code objects of every function of the frames table, reached as the test reaches them and where CPython has them, with the functions behind the wrappers.

Stale tables: tools/missing_names.py, the test's module list, the unmarked-lines sweep; a grep for the removed helpers (_check_builtin, _check_frozen) and the old refusals' words found nothing left. CPython's C read from v3.15.2 sources fetched into src-ceval and src-getargs (src-import and src-moduleobject fetched, not needed for a claim).

Not covered: The inner lines of the other 150 functions of the frames table by running them (statically only); the import-frames reviewer has that area. order_as_cpython under a failing or re-entrant import of a native module and at exit (C-9-13's clearing order). The 'must be X, not <type>' messages of the other preludes for None (only _imp's six run). Whether a program-replaced builtins.__import__ can see FrozenImporter.exec_module's line (the table row read, not run). refmodel/objects.py, object.hpp and types.cpp in the commit are comment changes: read, not tested. The A46 test module itself was not run (it builds); its rows were re-derived in my probes. Nothing before the commit was built, so 'older than the commit' is from reading the diff. Whether the user's 'answer A' is Question 48's answer I do not know; finding 1 matters either way. REPORT.md does not exist (see the last minor line).


## c07-d33-stops: D-33's stops and their table (02b6d07)

### F48-c07-d33-stops-1 (RL-1065): D-33's stop holds for a read only: a store to one of the fourteen names is kept and ignored by the import system, and a delete raises AttributeError

*defect, reported as medium*; where: docs/deviations.toml D-33 and docs/dialect-spec.md:245 ("stops the program with a message naming D-33"); runtime/src/ops.cpp:1465-1466 (store), 1520-1522 (delete); pipeline/tests/test_module_locks.py (its name rows are reads)

D-33 says the lock machinery's fourteen names stop the program. Every read I tried does: all 14 by attribute, getattr with a default, hasattr, object.__getattribute__, a str-subclass name and before a module __getattr__; from-import and the module's six aliases for some of them. A store does not: `_bootstrap._get_module_lock = f` is kept and never called, where CPython calls f at the next first import; `_module_locks = Spy()` likewise. A delete raises an AttributeError the program can catch, where CPython deletes. The runtime already stops a store it cannot honour in these modules (refuse_bootstrap_assignment, for the names it keeps). The test holds reads only.

Evidence: Probe p1, one build, 468 rows (p1/out.txt): .venv/bin/python r48_both.py review/c07-d33-stops/p1 --rows review/c07-d33-stops/p1/rows.txt
ROW ['wrap','x'] (setattr(_bootstrap, '_get_module_lock', wrapper); import sample1): CPython status 0 `RuntimeError the program's _get_module_lock was called for sample1 ['sample1']`; compiled status 0 `imported 41 []`.
ROW ['spy','x'] (_module_locks = Spy(); import sample2; print(Spy.hits > 0)): CPython `imported 42 True`; compiled `imported 42 False`.
ROW ['deltry','_module_locks'], and so for each of the 14: CPython `deleted`; compiled status 0 `AttributeError 'module' object has no attribute '_module_locks'`.
ROW ['set', each of the 14]: SAME `5 True 5` (the program reads its own value back).
Reads, each of the 14 on routes attr, default, hasattr, try, strsub, objga, hook: compiled status 70 `bella: not implemented: _frozen_importlib.<name> (a module lock: the import system takes none until the threads milestone, D-33)`.
ops.cpp:1465-1466: `if (auto* m = ...; bootstrap_hides(m, name)) refuse_bootstrap_assignment(m, name);` then `dict_set(program_dict(...), Obj::of(name), value);`

Probe: p1: rows wrap, spy, deltry, del, set, and the read routes

Suggested: Stop a store to and a delete of a name in ABSENT_BY_ENTRY with D-33's words (both off the hot path) and add a store and a delete row per name to the test; or say in D-33 and in its lint words that a store is kept and not read.

> Verifier: **confirmed** (medium). D-33's stop holds for reads only. For each of the 14 lock names, a store is kept and the import never calls it (CPython calls a replaced _get_module_lock at the next first import), and a delete raises a catchable AttributeError where CPython deletes (14 of 14 DIFF; `set` is SAME for all 14). The same delete defect hits any name CPython has and the runtime lacks in a tabled module (sys.displayhook, sys.settrace, builtins.aiter, _frozen_importlib._verbose_message; the ops.cpp:1520-1522 module branch). test_module_locks.py holds reads only. Findings 1 and 2 are one defect: finding 1 is the 14 nam ... Cover: None for stores or deletes. D-33 says the lock machinery "stops the program with a message naming D-33", and its test column says "Partial: the lock machinery's names read from importlib._bootstrap". RL-419 ("a deletion raises CPython's error, an assignment stops by name") covers only the runtime's  ...

### F48-c07-d33-stops-2 (RL-1065, with the same subject): Deleting a module name CPython has and the runtime lacks raises AttributeError instead of stopping, in every tabled module

*defect, reported as medium*; where: runtime/src/ops.cpp:1514-1523 (older than the range; D-33's fourteen names meet it)

The module branch of delattr has no refusal: a name not in the dict raises AttributeError. For a name CPython's module has and the runtime lacks (sys.displayhook, sys.settrace, sys.getrefcount, sys.breakpointhook, builtins.aiter, _frozen_importlib._verbose_message, the fourteen) CPython deletes it and goes on; the compiled program gets an exception CPython never raises, and can catch it. A read of the same name stops, and DECISIONS 2026-11-12 (line 1157) says "A name of CPython's that was never there still stops". The names are outside [P1] or excluded (E-03, E-05), so the project's answer elsewhere is the stop.

Evidence: Probe p2 (p2/out.txt). Row: try: delattr(m, name); print('deleted') / except AttributeError as e: print('AttributeError', e); then print(hasattr(m, name)).
ROW ['ndel','sys','displayhook']: CPython status 0 `deleted`, `False`; compiled status 70, standard output `AttributeError 'module' object has no attribute 'displayhook'`, standard error `bella: not implemented: sys.displayhook (CPython has it; the runtime does not yet)` (from the hasattr after it).
The same pair for sys getrefcount, settrace, gettrace; builtins aiter; boot _verbose_message; boot _module_locks (rows of out.txt), and for sys breakpointhook, sys __displayhook__ and boot _thread (run by hand with the binary p2 built).
Controls SAME: ndel sys maxsize (`deleted`, `False`); ndel sys no_such, ndel _imp no_such, ndel boot no_such (AttributeError on both sides).
ops.cpp:1520-1522: `if (bootstrap_hides(...) || !dict_del(program_dict(...), Obj::of(name))) raise_attribute_error(obj, name, "'" + type_of(obj)->name + "' object has no attribute '" + name->text + "'");`

Probe: p2: rows ndel

Suggested: Where dict_del fails for a module, ask what the read asks (tabled, cpython_has, not was_filled) and stop through absent_name before raising AttributeError; no cost when the delete succeeds. One row per kind of module in a test.

### F48-c07-d33-stops-3 (RL-1066): The runtime's __import__ calls its own _find_and_load and _handle_fromlist and never _lock_unlock_module: a program's replacement in _bootstrap is not called

*defect, reported as low*; where: runtime/src/imports.cpp:159-162 (call_bootstrap), 1510, 1513, 1539; CPython v3.15.2 Python/import.c:335-336, 3942, 4139-4140

CPython's import.c looks _find_and_load, _handle_fromlist and _lock_unlock_module up on the importlib module at each call, so a program that replaces one sees it called. The runtime calls the functions it took at start (the intrinsics), and never calls _lock_unlock_module (TODO line 683 has that with the threads milestone). Replacements of the functions the prelude's own text calls are honoured. After `del _bootstrap._find_and_load` CPython's next import raises AttributeError; compiled imports. I found no record of it; E-04 names replacing `__import__` and sys.meta_path, not a store to an attribute of the import system's modules. Older than the range, outside the commit.

Evidence: Probe p2 (p2/out.txt), `patch <function> <how>`: read the function, store a wrapper that notes the call and calls the original, import, print whether it ran.
patch _find_and_load plain: CPython `41`, `True ['_find_and_load']`; compiled `41`, `False []`.
patch _handle_fromlist pkg: CPython `2`, `True ['_handle_fromlist']`; compiled `2`, `False []`.
patch _lock_unlock_module circ: CPython `2`, `True ['_lock_unlock_module']`; compiled `2`, `False []`.
delthen _find_and_load: CPython `AttributeError module 'importlib._bootstrap' has no attribute '_find_and_load'`; compiled `imported 41`.
SAME, the wrapper runs on both: _find_and_load_unlocked, _load_unlocked, _find_spec, _init_module_attrs, module_from_spec, _resolve_parents, _gcd_import, _sanity_check, _call_with_frames_removed.
CPython v3.15.2 Python/import.c (cpython-src/import.c) 335-336: `PyObject_CallMethodOneArg(IMPORTLIB(interp), &_Py_ID(_lock_unlock_module), name)`; 3942: `mod = PyObject_CallMethodObjArgs(IMPORTLIB(interp), find_and_load, abs_name, IMPORT_FUNC(interp), NULL);`; 4139-4140 the same for _handle_fromlist.
imports.cpp:159-161: `Ref call_bootstrap(const char* fn, ...) { Ref f = builtin(fn); return invoke(f.get(), args); }`

Probe: p2: rows patch, delthen

Suggested: The author's choice: name it under E-04 and stop such a store, as for the names the runtime keeps; or look the three up on the module as import.c does (one dict lookup per import that reaches them).

> Verifier: **confirmed** (low). The runtime's __import__ calls _find_and_load and _handle_fromlist as taken at start (intrinsics, via call_bootstrap and builtin(), imports.cpp:159-162, 1510, 1513, 1539). CPython looks them up on the importlib module at each call (import.c:3942, 4139-4140; _lock_unlock_module at 335-336). A program's replacement of any of the three is ignored, and after `del _bootstrap._find_and_load` the next import works where CPython raises AttributeError. The _lock_unlock_module part is known (TODO.md:683); E-04's heading is the closest cover but its list does not name a store to an attribute of the impor ... Cover: Partial. TODO.md:683 "`__import__` calls `_lock_unlock_module` for a module still initialising, as `import.c` does", queued with the threads milestone, makes the _lock_unlock_module row known. E-04 "Import-system customisation: ..., replacing `__import__`, ..." is the nearest, but the list does not  ...

### F48-c07-d33-stops-4 (RL-1067): The test cannot see a fifteenth name, an entry too many or a dead entry; the list is kept by hand in three places

*test, reported as low*; where: pipeline/tests/test_module_locks.py:29-31, 48-50 and 89-90; runtime/src/call.cpp:1849-1858; docs/deviations.toml D-33

LOCK_NAMES is a literal, and nothing compares it, ABSENT_BY_ENTRY or D-33's list with CPython's _bootstrap.py or with each other. The test fails when one of the fourteen starts to exist or leaves CPython, or when the words change. It does not fail when CPython's lock machinery gains a name (a pin bump: the name would say "not yet"), when the table gets an entry beyond the fourteen other than _verbose_message, or when a key matches no name of CPYTHON_NAMES (the static_assert checks the order only). The `plain` row cannot fail on anything the locks do. Today the three lists are equal and exactly the lock machinery's names.

Evidence: static/owners.py under CPython 3.15.2 (which top-level definitions of importlib/_bootstrap.py load each module-level name): each of the fourteen is used only by the lock classes and functions and by _setup, _find_and_load, _lock_unlock_module, _find_spec (_ImportLockContext), _exec and _load (_ModuleLockManager); `names used only by the fourteen (or by nobody) that are not among them:` prints nothing.
A script over call.cpp's keys, the test's tuple and the names in D-33's summary printed `14 {'MODULE_LOCKS'} True` (count, reason, sorted), `True` (the three lists equal), `every key is in CPYTHON_NAMES: True`, and MODULE_LOCKS == WHY.
Probe p3 is the test's own PROG and sample.py with its 18 rows (p3/out.txt): each side gives what the test's CPYTHON and COMPILED tables say: 14 name rows status 70 with D-33's words; other `_frozen_importlib._verbose_message (CPython has it; the runtime does not yet)`; hash `42` against `hash during lock lookup`; plain SAME `42`; varnames 5 and 1 locals against 6 and 2.
test_module_locks.py:29: `LOCK_NAMES = ("_BlockingOnManager", ...)`; 48-50: `class Plain(str): def __hash__(self) -> int: return super().__hash__()`.

Probe: p3 (the test's own program); static/owners.py

Suggested: Derive the set in the test from the pinned _bootstrap.py and read ABSENT_BY_ENTRY's keys from call.cpp, comparing both with LOCK_NAMES (about 30 lines, no build).

> Verifier: **confirmed** (low). Confirmed as stated. The test's LOCK_NAMES (pipeline/tests/test_module_locks.py:29-31) is a literal and nothing in the test, tools or docs reads ABSENT_BY_ENTRY (runtime/src/call.cpp:1849-1856), CPYTHON_NAMES or D-33's list. So the test cannot catch an extra or dead ABSENT_BY_ENTRY entry, a fifteenth CPython lock name, or a key missing from CPYTHON_NAMES. The three lists are equal today: 14 keys, 14 test names, 14 D-33 names, all keys present in cpython_names.inc. CPython's _bootstrap.py ownership script prints nothing for 'names used only by the fourteen not among them'. The probe p3 has 18 r ...

### F48-c07-d33-stops-5 (RL-1068): The two import-system modules' names are never noted as filled: after a program's own delete, a read stops with false words

*defect, reported as low*; where: runtime/src/call.cpp:2081-2083 (tabled includes is_bootstrap_prelude, then !was_filled); note_filled only at call.cpp:4367-4369, imports.cpp:1438 and 542

`was_filled` is always false for `_frozen_importlib` and `_frozen_importlib_external`: nothing calls note_filled for them. So after a program deletes a name the runtime has, a read of it stops with "CPython has it; the runtime does not yet", where CPython answers False or AttributeError; and a program that stores one of the fourteen and deletes it again gets D-33's stop. DECISIONS 2026-11-12 ("A name the program deleted") says such a name is absent as in CPython and calls the other outcome "a stop that blames the runtime". It is a stop, so nothing goes on wrongly; the words are false. Older than the range.

Evidence: Probe p1 (p1/out.txt).
ROW ['delhas','_find_and_load'] (delattr(M, name), then print(hasattr(M, name))): CPython status 0 `False`; compiled status 70 `bella: not implemented: _frozen_importlib._find_and_load (CPython has it; the runtime does not yet)`. The same for _lock_unlock_module, _bootstrap_external and __name__.
ROW ['setdel','_module_locks'] (setattr(M, name, 5); delattr(M, name); print(hasattr(M, name))): CPython `False`; compiled status 70 `bella: not implemented: _frozen_importlib._module_locks (a module lock: the import system takes none until the threads milestone, D-33)`; so for all 14.
Control, probe p2: ndel sys maxsize is SAME (`deleted`, `False`): sys is noted (call.cpp:4368).
call.cpp:2081-2082: `bool tabled = (it != native_modules().end() && it->second == m) || is_bootstrap_prelude(m);` `if (tabled && cpython_has(mod, name->text) && !was_filled(m, name->text))`. note_filled is called at call.cpp:4367-4369 (builtins, sys, the main module), imports.cpp:1438 (a native module) and 542 (a program's module), nowhere for the two.

Probe: p1: rows delhas, setdel

Suggested: Call note_filled for the two modules where start-up ends (beside hide_bootstrap_names, call.cpp:4341) and keep delhas as a test row.

> Verifier: **confirmed** (low). note_filled is never called for _frozen_importlib or _frozen_importlib_external. After a program deletes a name the module holds (_find_and_load, _lock_unlock_module, _bootstrap_external, __name__, _imp, _gcd_import, _handle_fromlist, __spec__), a read or hasattr stops with "CPython has it; the runtime does not yet" where CPython gives False. The words are false (DECISIONS 2026-11-13 calls this "a stop that blames the runtime"); the stop itself is safe. Correction: the suggested fix (note_filled at start) cures only names present at start. The 14 lock names are never in the dict, so set-then-d ... Cover: None. DECISIONS 2026-11-13 "A name the program deleted" records native modules, sys, builtins and program modules, not the two import-system modules. No TODO or review-log text found by grep for was_filled, note_filled or deleted names.

### F48-c07-d33-stops-6 (RL-1069): absent_name does not word every stop for a name of CPython's the runtime lacks

*wrong-fact, reported as low*; where: docs/design.md:810, docs/DECISIONS.md:1956, the commit message of 02b6d07; runtime/src/call.cpp:2117 and 2122, runtime/src/posix.cpp:1149 with runtime/prelude/posix.py:472 and 1668

The three texts say absent_name "words every stop for a name of CPython's the runtime lacks". Three sites word their own: a name read as a global (refuse_absent_global), posix's functions (p_refuse, whose prelude already passes a reason of its own: `_absent("fork", " ([P2+]: ...)")`), and a missing operator. So ABSENT_BY_ENTRY is a second mechanism for giving such a stop its reason, and DECISIONS' plan to put the names under an exclusion into "the same table" would not reach a builtin read by its bare name. The five sites the commit changed give the earlier words for every name outside the table.

Evidence: Probe p2 (p2/out.txt). ROW ['global'] (print(type(aiter).__name__) in a function): compiled status 70 `bella: not implemented: the name 'aiter' (CPython has it; the runtime does not yet)`. ROW ['ndel','builtins','aiter'] ends, at its hasattr, with `bella: not implemented: builtins.aiter (CPython has it; the runtime does not yet)` (through absent_name).
call.cpp:2122: `throw NotImplemented("the name '" + name->text + "' (CPython has it; the runtime does not yet)");`
posix.cpp:1149: `Ref p_refuse(Args a) { throw NotImplemented(as_str(a.pos(0))->text + " (CPython has it; the runtime does not yet)"); }`
runtime/prelude/posix.py:1668: `fork = _absent("fork", " ([P2+]: a process made by fork is a later phase, spec sections 3 and 7; posix_spawn starts a program)")`
design.md:810: "`absent_name` (`runtime/src/call.cpp`) words every stop for a name of CPython's the runtime lacks".

Probe: p2: rows global, ndel builtins aiter

Suggested: Reword to "every stop for an attribute of a module or of a type"; when the exclusions' names go into the table, send refuse_absent_global through it too (key builtins:name).

> Verifier: **confirmed** (low). The sentence 'absent_name words every stop for a name of CPython's the runtime lacks' (design.md:810, DECISIONS.md:1956, commit 02b6d07) is overbroad: it holds only for attributes of a module or type. refuse_absent_global (call.cpp:2119-2122), the operator stop (2117) and posix p_refuse (posix.cpp:1149; prelude _absent with its own reason) word their own. No program-visible effect; the queued exclusion names (sys.settrace, getrefcount, co_consts) are attributes and do go through absent_name, so the claim about the plan missing bare builtins is speculative. Reword to 'every stop for an attribut ...

Minor, one line each, not verified:

- RL-950's verdict says "`_find_and_load` takes `_ModuleLockManager(name)` (`_bootstrap.py:1339`)": line 1339 of 3.15.2's text is `lock = _get_module_lock(name)`; `_ModuleLockManager` is used by `_exec` (821) and `_load` (886) only. The test's docstring has it right.
- CPython also takes the module's lock in `_load(spec)` and `_exec(spec, module)` (`with _ModuleLockManager(...)`); D-33 names two occasions. `_load` is absent ("not yet") and `_exec` is refused (E-04), so nothing shows today; when `_load` is written it needs D-33's cover or the lock.
- MODULE_LOCKS' words call `_thread`, `_weakref`, `_List`, `_WeakValueDictionary` and `_ImportLockContext` (the global import lock's context manager) "a module lock".
- `unittest.mock.patch.object` reads `target.__dict__[name]` first (unittest/mock.py:1470), so on these modules it meets RL-419's stop for the namespace as a whole, not D-33's words; pytest's monkeypatch reads `getattr(target, name, NOTSET)` (_pytest/monkeypatch.py:254) and meets D-33's. Read, not built.
- `types.ModuleType.__getattribute__(M, name)` stops with `module.__getattribute__ (CPython has it; the runtime does not yet)` for any name (p1, route modga): another absence, honest.
- ABSENT_BY_ENTRY's static_assert allows two equal keys and does not ask that a key be a name of CPYTHON_NAMES.
- The A46 test's `OPEN & set(cpython) - differ` does not report a name of OPEN that the frames table no longer has; today none is missing (p4).

Covered: Commit 02b6d07's diff of runtime/src/call.cpp read whole (absent_name, ABSENT_BY_ENTRY, the five call sites in refuse_in, refuse_shadowed, refuse_absent_attribute, refuse_absent_data_descriptor) with every caller (module_getattr at imports.cpp:2224, which refuses before the module's __getattr__ and whatever `suppress` says; generic_getattr; lazy_getattr; type lookups; dir). Five builds of 15, all through r48_both.py; outputs are p1..p5/out.txt under review/c07-d33-stops/.

The lookup: sound, no finding. The key is scope + ":" + name, found by lower_bound under the comparison the static_assert checks and matched by equality, so a prefix cannot match; a table key has one colon, so no other (scope, name) builds it; absent_name is reached only after cpython_has found the same key. The scope is the module's md_name (not __name__) for a native module or one of the two bootstrap modules by identity, a built-in or prelude class's name, or `_frozen_importlib.<Class>`. Rows that agree with CPython (p1): `_threa`, `_thread_`, `_ModuleLoc`, `_ModuleLockX`, `_module_lock`, `_weakrefs`, `_Lis`, `_List_`, `_thread:`, `:_thread`, `_frozen_importlib:_thread`, the empty name, `_thread.x`; the names on `_frozen_importlib_external` and on a program's types.ModuleType("_frozen_importlib"); getattr of ModuleSpec, hasattr of BuiltinImporter, an instance of ModuleSpec. All six aliases of the module are one object and give the same stop, also after the program set __name__.

The routes (p1: 14 names and 8 "not yet" names by 14 routes, 468 rows): attribute, getattr with a default, hasattr, try/except AttributeError, a str-subclass name, object.__getattribute__, from-import (both module names), `import ... as b; b.X`, and a read with a module __getattr__ set all stop with D-33's words; vars(), __dict__ and dir() stop for the namespace as a whole (RL-419; CPython's dir lists all fourteen); __import__ with a fromlist reads nothing and agrees; a store then a read gives the program's value back, as CPython. hasattr and getattr with a default stop for the fourteen exactly as for _verbose_message, _load, _install, _object_name, _builtin_from_name, _install_external_importers and _warnings with their "not yet" words: that is the runtime's existing rule (DECISIONS 2026-11-12, hasattr(sys, "_getframe")), the spec has no sentence on it, and I report no finding. except BaseException and finally do not see the stop (p2). _imp.lock_held() around acquire_lock/release_lock and _lock_unlock_module("sample1") agree.

The list: derived from CPython's _bootstrap.py (static/owners.py) and compared with call.cpp's keys, the test's tuple and D-33's summary: the same fourteen, nothing else; _lock_unlock_module is the machinery's fifteenth name and the prelude keeps it. No standard-library module outside _bootstrap.py (tests apart) and no package of the venv uses any of them (grep). deviations.toml's D-33 summary equals the spec row's cell.

The tests: test_module_locks.py read, its own program run as p3 (all 18 rows as its tables say). test_review_2026_11_25_a46.py: LOCKS | REWRITTEN is the earlier OPEN (29 = 2 + 27, disjoint, all in bootstrap_frames.json); its codeobjects program run as p4 with the table's 150 names: 149 lines a side, 29 differ, exactly OPEN, none of OPEN agrees. p5: the lines of _find_and_load's frame where the prelude lost the lock (a body that raises, a stack listed in a body, a circular import, a missing module, None in sys.modules; 7 rows) all agree. design.md:810's sentence on the mechanism checked (finding 6).

Not covered: REPORT.md was not written: the harness refused the file ("Subagents should return findings as text, not write report files"), and I did not go round that refusal. The full account is this output; each probe folder has prog.py, rows.txt and the whole run in out.txt, and static/ and tools/ hold the CPython-only scripts.

D-33's words and the decision itself (another reviewer's): the counts of __hash__ and __eq__, the weakref callbacks, _imp.lock_held() during an import, the 12 calls, the GitHub counts. pytest, make and the test modules themselves were not run (not permitted): I ran the two tests' programs through r48_both.py and applied their comparisons by hand. unittest.mock.patch.object and pytest's monkeypatch were read, not built. Not tried: a lazy import of one of the names, a star import of the module, a program that calls module.__init__ on the bootstrap module (which resets the md_name the scope is built from). The class-scope callers (refuse_in, refuse_shadowed, refuse_absent_data_descriptor) were read and compared in the diff, not swept by a probe of their own; no key of ABSENT_BY_ENTRY has a class scope. Finding 2's class was shown for sys, builtins and the bootstrap module, not for each of the 47 native modules. The nightly CI result for this commit was not read.


## c08-a43-abc-exit: review A43's fixes, `_abc`'s weak references and the exit's case (de36608, 293c2dc)

### F48-c08-a43-abc-exit-1 (RL-1070): At-fork handlers are never let go of at exit: with `from logging import ...` a program's globals are not finalised and a file left open stays empty

*defect, reported as high*; where: runtime/prelude/posix.py:1362-1372 (_at_fork); runtime/src/call.cpp:3743-3748 (finalize_at_exit's releases); D-07 (docs/deviations.toml:46-50, spec section 9); docs/DECISIONS.md:1791

Handlers given to os.register_at_fork are never released at exit, so every namespace one reaches is never finalised. CPython clears its three lists in interpreter_clear, before the last collection; the runtime keeps them in the posix prelude (a root), and finalize_at_exit releases only the context, the codec registry, gc's lists and the warnings' state. logging, threading and random register at import. A program that writes `from logging import getLogger` and puts a lambda filter, or a handler or formatter of its own class, on a logger gets no global of its main module finalised; a file left open there stays empty. So does one that registers its own function. D-07 promises the opposite.

Evidence: cmp.py p8_logging build/compiled/prog-9df97acec3b6e7ff/prog rows.txt; each child's main module ends `held = F(..); out = open(name, "w"); out.write("text of " + ROW)`.
from_filter (`from logging import getLogger; getLogger("app").addFilter(lambda record: True)`): CPython `child: fin a global of the main module` / `file: 19 bytes, b'text of from_filter'`; compiled no fin line, `file: 0 bytes, b''`. from_handler, from_formatter, from_thread: the same. SAME: control, from_plain, from_basic, import_handler (`import logging`), from_random.
p5_reach (prog-f72991e72f386abe) x_main_func (`os.register_at_fork(before=hook)`): CPython `txt file: 19 bytes, b'text of x_main_func'`, compiled `txt file: 0 bytes, b''`; x_client, x_lambda, x_lib_top alike.
CPython: Modules/posixmodule.c:8500-8506 (interp->before_forkers, after_forkers_child, after_forkers_parent); Python/pystate.c:883-885 Py_CLEAR of the three, :900 the last collection. Lib/logging/__init__.py:274, threading.py:1780, random.py:1013.
Runtime: runtime/prelude/posix.py:1362 `_at_fork: list[object] = []`, :1372 append; runtime/src/call.cpp:3743-3748 releases _contextvars, _codecs, gc, _warnings only.
Record: docs/DECISIONS.md:1791 "The state of a C module ... stays alive here as a root, for example `_csv`'s dialects. No case reaches it."; grep at_fork finds nothing in TODO.md, review-log.md, deviations.toml.

Probe: p8_logging rows from_filter, from_handler, from_formatter, from_thread; p5_reach rows x_main_func, x_client, x_lambda, x_client_local, x_lib_top; p3_exit2 rows fork_*; p4_exit3 rows thr_excepthook, thr_stash, thr_attr; p2_exit row h_at_fork

Suggested: Fix: let go of posix._at_fork where interpreter_clear does (beside release_state("_codecs", ...), before the collection at call.cpp:3745), with a case row like from_filter. Then correct DECISIONS:1791's 'No case reaches it'.

> Verifier: **confirmed** (high). Handlers registered with os.register_at_fork (also by logging, threading and random at import) are kept in posix's prelude list, which finalize_at_exit never releases. CPython clears them in interpreter_clear before the last collection. Every namespace a handler reaches is therefore never finalised, so after `from logging import getLogger` plus a lambda filter or a main-program Handler/Formatter subclass, a global holding an open file is not flushed and the file stays empty. This contradicts D-07 and spec section 9 ('a file left open is flushed and closed'). DECISIONS:1791's 'No case reaches i ... Cover: None. D-07 promises the opposite. DECISIONS:1791 ('The state of a C module ... stays alive here as a root ... No case reaches it') concerns C-module state, whereas the at-fork lists are interpreter state, and its 'no case reaches it' is false. grep of at_fork in TODO.md, review-log.md, deviations.to ...

### F48-c08-a43-abc-exit-2 (RL-1071): atexit runs a second round in CPython 3.15.2; 'One round is all there is' is false

*wrong-fact, reported as high*; where: runtime/src/call.cpp:4392-4408; docs/DECISIONS.md:948 (2026-11-10, atexit and the end of a program)

make_pre_finalization_calls is a loop in 3.15.2: after the handlers it goes round again while atexit's list is not empty. Clearing the list after a round frees what the registrations held, so a handler that a finaliser registers there is called in a second round. The runtime calls the handlers once. DECISIONS (2026-11-10) and call.cpp:4395 state one round as a fact; it was measured only for a registration a handler makes itself, which is dropped on both sides. Narrow reach: it needs a finaliser that registers. One path is the program's first weakref.finalize made in such a finaliser: its exit call never comes compiled.

Evidence: Python/pylifecycle.c:2272-2378: `should_continue = (interp_has_threads(interp) || interp_has_atexit_callbacks(interp) || interp_has_pending_calls(interp) || has_subinterpreters)`; runtime/src/call.cpp:4408 one `_atexit_call`; docs/DECISIONS.md:948 "One round is all there is: the list is cleared after the handlers ran, so a registration made by one is dropped (measured)".
cmp.py p2_exit build/compiled/prog-7b6006b01369aeca/prog rows.txt, row h_atexit_round2_arg (`atexit.register(noop, Registers(..))`, whose __del__ registers a handler): CPython `fin a handler's argument, registering` / `late handler called` / `fin argument of a handler registered by a handler's argument`; compiled the first line only. h_atexit_round2 alike. h_atexit_inside (a handler registers): SAME.
cmp.py p3_exit2 build/compiled/prog-1e878a0578f8792d/prog rows.txt: atexit_finalize: CPython `child: the finalize's callback ran at exit`, compiled no such line; atexit_round2_file: CPython `file: 83 bytes, b"opened by a finaliser of a handler's argument; written by the handler it registered"`, compiled `file: 0 bytes, b''`.

Probe: p2_exit rows h_atexit_round2, h_atexit_round2_arg, h_atexit_inside; p3_exit2 rows atexit_finalize, atexit_round2_file

Suggested: Fix (loop while the prelude's list is not empty after _atexit_call, threading._shutdown again each round) or ask the author to register it; correct DECISIONS:948 and the comment at call.cpp:4395 either way.

> Verifier: **confirmed** (high). In 3.15.2, make_pre_finalization_calls loops while atexit's callback list is non-empty. Clearing the list after a round frees the registrations' arguments, and a finaliser that registers there gets its handler called in a further round. The runtime does one round, and DECISIONS:948 ('One round is all there is') and call.cpp:4395 state that as fact. It holds only for a handler's own registration. Reach is narrow: it needs a finaliser that registers during the exit. One case is the program's first weakref.finalize made in such a finaliser, whose exit callback never runs compiled. Cover: None. D-07 covers order and step only, and atexit is [P1] (spec lines 67 and 143). grep of 'second round', 'one round' and 'round 2' in the review log, TODO, DECISIONS and design finds only DECISIONS:948 itself, which is the false statement.

### F48-c08-a43-abc-exit-3 (RL-1072): D-07's promise has exceptions that DECISIONS lists and nothing registers

*words, reported as medium*; where: docs/deviations.toml:46-50 (D-07); docs/dialect-spec.md:195, :222; docs/DECISIONS.md:1791 and :1910 (Question 39)

D-07 as sharpened (Question 39, spec v0.35) says which objects are finalised at exit is CPython's, with no exception. The DECISIONS entry of the day before lists one as known: what a runtime-owned module's state holds is a root and never goes. Question 39's entry does not mention it, and neither the spec nor deviations.toml carries it. Beside finding 1 it is reached by: a registration made with atexit after the handlers ran (CPython's _PyAtExit_Fini frees it), a value under a non-str key of sys's dict or of any C module's dict, and _struct's cache. None is likely in a program; the words are what is wrong.

Evidence: docs/deviations.toml:46-50 (D-07: "which objects are finalised is CPython's"); docs/DECISIONS.md:1791 (listed, "No case reaches it"), :1910 (Question 39, no mention). Python/pystate.c:893 `_PyAtExit_Fini(interp)`, :924 `PyDict_Clear(interp->sysdict)`.
cmp.py p2_exit build/compiled/prog-7b6006b01369aeca/prog rows.txt:
h_atexit_late (a global's finaliser registers `noop` with a new object): CPython `fin a global, registering` / `fin argument of a handler registered by a global`; compiled the first line only. h_atexit_late_sys alike.
h_sys_nonstr (`sys.__dict__[5] = F(..)`): CPython `fin under an int key of sys`; compiled no such line.
h_struct (struct.calcsize of a str subclass with __del__): CPython `fin a format of a str subclass`; compiled no such line.
cmp.py p4_exit3 build/compiled/prog-ad2a7e90390291b8/prog rows.txt: 39 rows `c:<module>` (38 C modules and sys; `mod.__dict__[5] = F(..)`): CPython `fin under an int key of math`, compiled no such line; the attribute beside it is finalised on both sides. In a module of the program's such a key is finalised on both sides (p2_exit h_nonstr_key, h_nonstr_key_kept: order only).

Probe: p2_exit rows h_atexit_late, h_atexit_late_sys, h_sys_nonstr, h_struct; p4_exit3 rows c:*

Suggested: Ask the author: name the exception in D-07 (what the interpreter's state and the runtime's own modules hold, beyond what finalize_at_exit releases), or make the releases (atexit._callbacks after the last round; the dicts' non-str keys).

> Verifier: **confirmed** (medium). D-07 (deviations.toml:46-50, spec 37/195/222) says which objects are finalised is CPython's, with no exception. Question 39's entry carries no exception either. DECISIONS:1791, written the day before, lists 'C-module state kept as a root; No case reaches it' as known, and that last claim is false. Not recorded anywhere: a registration made with atexit after the last round (CPython's _PyAtExit_Fini frees it), non-str keys in sys's dict or a C module's dict, and _struct's cache. The words of D-07 are incomplete and the 1791 note is partly wrong. Overlaps findings 1 and 2, which are code fixes. Cover: Partial: DECISIONS:1791 'The state of a C module that CPython frees with its module stays alive here as a root ... No case reaches it' lists the root idea as known. It is not in D-07, the spec or deviations.toml, it does not name the atexit-late, sys/C-module non-str-key or _struct items, and its 'n ...

### F48-c08-a43-abc-exit-4 (RL-1073): Words written in de36608 that the behaviour contradicts (C-7-19, abc.cpp, C-9-13)

*words, reported as low*; where: conformance/cases/C-7-19_abc.py:8-9, :503; runtime/src/abc.cpp:9; conformance/cases/C-9-13_the_steps_of_the_exit.py:14

Three statements are false. C-7-19's docstring and section comment say a look-up 'makes a reference of its own, so a metaclass's __hash__ and __eq__ run at each one': a look-up takes the class's basic reference and the hash is asked once, as the case's own record shows and as abc.cpp's header and DECISIONS say. abc.cpp:9 says COLLECTION_FLAGS 'have no reader until match is compiled': match is compiled and reads them. C-9-13's docstring says what the warning filters or gc.callbacks hold 'is never finalised': only what is in a cycle; an object that only the list holds is finalised on both sides.

Evidence: conformance/cases/C-7-19_abc.py:8-9 and :503; `PYTHONHASHSEED=0 .venv/bin/python conformance/cases/C-7-19_abc.py | tail -7` gives `subclass: True ['hash Seen', 'eq Seen Seen']` then `again: True ['eq Seen Seen']` (no hash). Objects/typeobject.c:9799 `PyWeakref_NewRef((PyObject *)type, NULL)`; Objects/weakrefobject.c:192 `if (self->hash != -1) return self->hash;`.
runtime/src/abc.cpp:9 against runtime/prelude/match.py:43 `return bool(_type_flags(type(subject)) & _SEQUENCE)`; p1_abc row match is SAME: `before: neither neither neither 0 0`, `after: sequence 1 2 sequence 1 2 mapping 7 32 32 64`.
conformance/cases/C-9-13_the_steps_of_the_exit.py:14 against p2_exit rows h_gc_lists (`fin in gc.garbage`, `fin in gc.callbacks`) and h_warn_filter (`fin in a warning filter`), SAME on both sides; runtime/src/call.cpp:3567 has it right ("whose cycles no collection meets any more").

Probe: p1_abc row match; p2_exit rows h_gc_lists, h_warn_filter

Suggested: Reword the three (the case's two lines to 'a look-up asks with the class's basic reference: its hash once, __eq__ each time'; drop abc.cpp:9's clause; 'what they hold in a cycle').

> Verifier: **confirmed** (low). Three quoted sentences are as the finding gives them, and the three claims they make are false as stated. (1) conformance/cases/C-7-19_abc.py:8-9 and :503 say a look-up 'makes a reference of its own, so a metaclass's __hash__ and __eq__ run at each one'. CPython's own run of the case gives 'subclass: True ['hash Seen', 'eq Seen Seen']' and 'again: True ['eq Seen Seen']' (hash asked once, eq each time), and Objects/typeobject.c:9799 makes the class's basic weak reference, which weakrefobject.c:192 keeps the hash of; DECISIONS 2026-11-24 line 1841 says 'its hash is computed once and kept'. (2) r ...

### F48-c08-a43-abc-exit-5 (RL-1074): The kept hash outlives an assignment to __bases__; CPython's does not (RL-938, the TODO entry's words)

*inconsistency, reported as low*; where: runtime/src/abc.cpp:123-127 (ClassObject::reference_hash); TODO.md:567-572; review-log RL-938

CPython keeps a class's hash in its basic weak reference, which its bases' lists of subclasses hold. type_set_bases takes the class out of every old base's list and puts it into every new one's, so the reference dies and the next look-up asks the metaclass's __hash__ again. The runtime's hash is a field of the class and stays. Assigning other bases stops by name, assigning the bases a class has does not, so the difference is reachable: fewer __hash__ calls and other _get_dump sizes. TODO's open entry names the cause but says the hash 'can run once more than CPython's'; here it runs three times fewer.

Evidence: Objects/typeobject.c:2005-2006 `remove_all_subclasses(type, old_bases); res = add_all_subclasses(type, new_bases);`, :9799, :9819 `PyDict_SetItem(subclasses, key, ref)`.
cmp.py p5_reach build/compiled/prog-f72991e72f386abe/prog rows.txt, row same_bases (metaclass H logs __hash__ and returns cls.h; `c.h = 2; c.__bases__ = (B1,)`):
CPython `the same bases assigned: False (0, 1, 2) ['hash C', 'hash C', 'hash C']`, `hash changed, the same bases assigned: True (0, 3, 2) ['hash E', 'hash E']`
compiled `the same bases assigned: False (0, 1, 1) []`, `hash changed, the same bases assigned: True (0, 2, 1) []`
p1_abc row bases (other bases): compiled `bella: not implemented: assigning a class's __bases__ other bases than it has (a new MRO for every lookup)`.
TODO.md:567-572; p1_abc row program_ref behaves as that entry says (one `hash C` more compiled).

Probe: p5_reach row same_bases; p1_abc rows bases, program_ref

Suggested: Add to the TODO entry (and RL-938's row) that an assignment to __bases__ forgets the hash in CPython; when the basic reference is modelled, reset reference_hash there.

> Verifier: **confirmed** (low). Mechanism and quotations hold. abc.cpp:123-127 (ClassObject::reference_hash, filled once and kept) and TODO.md:567-572 (the open entry 'can run once more than CPython's') are as quoted; RL-938 is at review-log.md:1350. CPython's type_set_bases_unlocked (typeobject.c:2005-2006, remove_all_subclasses then add_all_subclasses) and the weak reference at :9799/:9819 are as cited, so the basic reference is replaced on assignment and the next look-up asks __hash__ again. Re-running the existing binary on the p5_reach rows same_bases gives the finding's quoted outputs exactly, both sides. Compiled 'the ...

Minor, one line each, not verified:

- `__abc_tpflags__ = 1 << 70` in an ABC's body: CPython raises OverflowError at the class's creation, compiled makes the class (runtime/src/abc.cpp:232-234 reads small ints only). p1_abc row init: `flags 1180591620717411303424 raised OverflowError` against `gave (False, 0)`.
- `type(C._abc_impl).__flags__` has bit 10 (Py_TPFLAGS_BASETYPE) set compiled and clear in CPython, though deriving from it raises TypeError on both sides. p1_abc row impl: `made: _abc_data _abc_data False` against `True`.
- An `import` statement in a finaliser that runs after sys and the builtins are wiped raises TypeError in CPython ('NoneType' object is not callable) and AttributeError compiled ('NoneType' object has no attribute 'get'): the class differs, not only the words. p7_imports row sys. Whether D-07's 'what it still finds' covers it is the author's call; the five other steps agree.
- Noted, not a finding (D-04): a buffered file that only a collected cycle holds loses its text under CPython (0 bytes: the raw file is finalised before its buffer) and keeps it compiled (15 bytes). p2_exit rows f_cycle, f_cycle_disabled. Row f_two (two handles on one file) differs by order alone (D-07).
- C-9-13 without BELLA_CASE_STEPS reduces each line to its tag, so the `abc` row's `registered: True True` is recorded as `registered`: the two answers of issubclass and isinstance are held only by pipeline/tests/test_exit_steps.py.
- The full account was to go to review/c08-a43-abc-exit/REPORT.md; the Write tool of this session refuses report files, so it is not there. The probes (prog.py, rows.txt) and each comparison's output (cmp.txt; p1_abc/both.txt) are in the folder, with cmp.py and CPython's sources under cpython-src/.

Covered: Eight builds through r48_both.py (p1_abc to p8_logging, 463 rows in all); every other run was CPython 3.15.2 alone or a binary one of those builds made, compared by cmp.py in my folder (each row under both, normalised as conformance/harness.py's mask_stderr does, addresses cut).

Read: Modules/_abc.c, Lib/abc.py, Objects/weakrefobject.c (hash, compare, the basic reference), Objects/typeobject.c (type_set_bases, add_subclass), Python/pylifecycle.c (_Py_Finalize, make_pre_finalization_calls, finalize_modules and its steps, flush_std_files), Python/pystate.c (interpreter_clear), Objects/moduleobject.c (_PyModule_ClearDict), Modules/atexitmodule.c, Python/gc.c (_PyGC_DumpShutdownStats), all fetched at v3.15.2 and only read. In the checkout: runtime/src/abc.cpp whole, set_contains_by in set.cpp, runtime/prelude/_weakref.py and atexit.py, call.cpp:3540-3750 and :4330-4435, gc.cpp:150-200, both cases with their records, both tests, review-log rows RL-923 to RL-938, the DECISIONS entries of 2026-11-10 (atexit), 2026-11-23 (H4) and 2026-11-24 (A43, Question 39), D-07 in the spec and the register.

_abc compiled against CPython (p1_abc 26 rows, p5_reach 2): the registry's walk order under chosen metaclass hashes with deaths between (5 rows); weak holding (a registered, a cached and a refused class die; 300 turns of make, register, drop; the ABC dies first; 200 new classes afterwards); _get_dump, both resets, the token; the negative cache's version; the hook's answers and the six steps; __instancecheck__ with a lying __class__ (28 kinds of value); the kept hash and a metaclass's __eq__; a __hash__ that raises or is None; cycles; _abc_init by hand and on an instance; __abc_tpflags__; abstract methods (messages, update_abstractmethods, __abstractmethods__ set, deleted, of odd types); match after Sequence.register and Mapping.register; __subclasses__ from a metaclass; _abc_data. All agree but findings 4 and 5 and two minor lines; no prelude frame shows in a traceback.

The exit: 63 rows of who holds an object, 10 of atexit, 28 of flushing and statuses, 19 of files left open (p2_exit); 196 generated rows of a weak reference's callback (7 places for the object, 7 for the reference, 4 callbacks: all agree, in order too); gc's shutdown warning in 14 settings and the late flush in 8 (all agree, so RL-923 and RL-925 hold in their class); 42 built-in modules' attributes one by one; imports from a handler and from finalisers at five steps; handlers that raise (a group, a cause, a context, a repr that raises, SystemExit, KeyboardInterrupt); tempfile's directory and file removed at exit (agree). Every row of test_review_2026_11_23_a43.py run under CPython alone to see what it shows: five rows print nothing by design (negatives), none ends early.

Not covered: Nothing was built at 2c342bc or de36608, so the review log's statement that A43's 41 rows reproduced, and RL-935's 'CPython does the same where its table is full at that insert', are unchecked. The timings of the DECISIONS entry (2.5%, 8%) were not measured. Not run: rows that write to sys.modules (E-04, so RL-934 to RL-936's class), gc.freeze (E-05), assignments to the builtins (E-06), signals during the exit, the lean fidelity, the exit under eval1 and eval2, refmodel's side of the collector. A ModuleType subclass, sys.addaudithook, gc.is_tracked and an import of colorsys or marshal stop by name, so those rows show nothing. Whether the corpus or any of the six targets meets finding 1 was not looked at. I did not read the other reviewers' folders (q39 covers Question 39 itself); overlap with them is possible. REPORT.md was not written: this session's Write tool refuses report files; the account is this output and the folder's cmp.txt files.


## c09-tests-and-cases: the tests and cases of the two days

### F48-c09-tests-and-cases-1 (RL-1032, with the same subject): The A46 code-object sweep never compares the source loaders, and Question 48's 27 functions are 34

*wrong-fact, reported as high*; where: pipeline/tests/test_review_2026_11_25_a46.py:70-74 (table_names) and :96-100; TODO.md:845 (Question 48); docs/DECISIONS.md:1950; review log RL-948; docs/reviews/2026-11-25-claude-workflow-47-review.md:153-155

table_names() maps every name of the frames table's bootstrap.py section to the module _bootstrap, but that prelude also holds _LoaderBasics, SourceLoader, FileLoader and SourceFileLoader, which a program reaches in _bootstrap_external. So 20 of the sweep's 149 lines are '<absent>' on both sides and 19 methods are never compared. Reached where CPython defines them, 7 of the 19 differ in co_nlocals/co_varnames ([P1] by RL-948's own reading) and are in no list. 'Of the 149 code objects 29 differ' is really 129 compared, and 36 of 148 differ. Question 48 was put, and answered, on 27 where there are 34, and its evidence calls two of the missing ones 'outside the list'.

Evidence: p1: `.venv/bin/python r48_both.py review/c09-tests-and-cases/p1 --rows review/c09-tests-and-cases/p1/rows.txt` (row `all` is the test's program exactly as the test generates it; then one row per function of CPython's two modules). Row all: 149 lines a side; 20 are e.g. `_bootstrap.SourceLoader.get_code <absent>` on BOTH sides; 129 compared with a code object, 29 differ = OPEN exactly. Rows `one _bootstrap_external X`, co_nlocals CPython/compiled: SourceLoader.get_code 15/2; SourceFileLoader.set_data 9/4; SourceLoader.get_source 5/2; SourceFileLoader._cache_bytecode 5/4; FileLoader.get_data 3/2; SourceFileLoader.path_stats 3/2; _LoaderBasics.exec_module 3/2 (('self','module','code') against ('self','module')). runtime/prelude/bootstrap.py:1405-1559 defines the four classes; bootstrap_external.py:496-499 `FileLoader = _bootstrap.FileLoader` etc. TODO.md:845: "27 of the 149 code objects ... the bytecode cache (7)". W47 review :153-155: "Nearest cases, both outside the list: ... `__loader__.get_code.__code__.co_nlocals` (15), `__loader__.set_data.__code__.co_nlocals` (9) ... these are `SourceLoader.get_code` and `SourceFileLoader.set_data`".

Probe: review/c09-tests-and-cases/p1: row `all` and the rows `one _bootstrap_external <name>` (out.txt; tools/parse_p1.py prints the summary)

Suggested: Look a bootstrap.py name up in _bootstrap_external when _bootstrap lacks it; make '<absent>' on CPython's side fail the test; add the seven to Question 48 (or make them CPython's text) and tell the author the question was answered on an incomplete list.

### F48-c09-tests-and-cases-2 (RL-1075): RL-924's class has more members: bytes and bytearray split/rsplit convert maxsplit before refusing an unknown keyword

*defect, reported as high*; where: runtime/src/bytes.cpp:311-320 (split_args); pipeline/tests/review_a43/hex/prog.txt and ROWS['hex'] in test_review_2026_11_23_a43.py; review log RL-924

RL-924 was fixed in hex_m and is held by the reviewer's three hex rows; no sweep of the class was made. A sweep of 135 built-in calls, each given an argument whose __index__/__int__/__float__/__bool__ log themselves and an unknown keyword: CPython refuses all 135 before converting anything; compiled, bytes.split and bytearray.rsplit run the program's __index__ first and then raise the TypeError. The one helper of the four methods converts maxsplit as it meets it, as hex_m did. Narrow (the call is a TypeError either way), but it is the same unregistered difference RL-924 was, so high only by the rubric's letter.

Evidence: p2: `.venv/bin/python r48_both.py review/c09-tests-and-cases/p2 --rows review/c09-tests-and-cases/p2/rows.txt`: 127 of 135 rows SAME, 6 stop by name (memoryview.hex twice, memoryview.cast, binascii.b2a_uu, b2a_qp, a2b_qp), 2 DIFF:
ROW ['27'] CPython `27 bytes.split kw | TypeError []`, compiled `27 bytes.split kw | TypeError ['index']` (the call: b"a b".split(maxsplit=R(1), bogus=1))
ROW ['28'] CPython `28 bytearray.rsplit kw | TypeError []`, compiled `28 bytearray.rsplit kw | TypeError ['index']`.
bytes.cpp:315 `maxsplit = a.npos > 1 ? ssize_arg(a.pos(1)) : -1;` and :318-319 `else if (a.kwnames[k] == N("maxsplit") && a.npos < 2) maxsplit = ssize_arg(a.kw(k));` then `else unexpected_keyword(...)`. str.cpp:213 collects the arguments first and agrees (rows 24 to 26 SAME). Only rows 27 and 28 were run; bytes.rsplit, bytearray.split and the positional form pass the same lines by reading.

Probe: review/c09-tests-and-cases/p2: rows 27 and 28 (out.txt)

Suggested: Fix split_args as hex_m was fixed (check the keywords, then convert) and keep p2's table of calls as the kept sweep of RL-924.

> Verifier: **confirmed** (medium). bytes.split/rsplit and bytearray.split/rsplit (shared helper split_args, runtime/src/bytes.cpp:311-321) convert maxsplit with ssize_arg (running the program's __index__) before refusing an unknown keyword; CPython's clinic refuses first. TypeError either way, but a program's __index__ runs. New member of RL-924's class (fixed only for hex). Rubric letter says high; I would defend medium (RL-924 itself was rated Medium). Cover: none; DECISIONS.md:1831 and review-log RL-924 cover only bytes.hex/bytearray.hex

### F48-c09-tests-and-cases-3 (RL-1061, with the same subject): RL-951's sweep of 'all 47 native modules' leaves out seven modules of the runtime's own order table, and sys is not in CPython's order

*test, reported as medium*; where: pipeline/tests/review_a46/nativeorder/prog.txt; test_review_2026_11_25_a46.py docstring; review log RL-951; docs/DECISIONS.md (review A46's fixes); runtime/src/cpython_names.inc CPYTHON_MODULE_ORDER; runtime/src/imports.cpp:1437

The probe's module list is written by hand (47 imports); CPYTHON_MODULE_ORDER has 54 modules. Left out: _abc, _types, builtins, math.integer, sys and the two import-system modules. Run on both sides: _abc, _types and math.integer agree; sys.__dir__() has the same 120 names with 113 positions different, and vars(sys) is in another order; builtins differs too (already open as RL-492); the two import modules stop by name. order_as_cpython runs only in the import that runs a prelude's body, which sys never passes. A module added later is not swept either. I did not check what the spec promises of the order of sys's names, hence medium.

Evidence: p4: `.venv/bin/python r48_both.py review/c09-tests-and-cases/p4 --rows review/c09-tests-and-cases/p4/rows.txt`. ROW ['sys','dir'] DIFF: CPython `['__name__','__doc__','__package__','__loader__','__spec__','addaudithook','audit','breakpointhook',...` ending `'stdout','_home','__interactivehook__']`; compiled `[...,'addaudithook','breakpointhook','_clear_internal_caches',...` ending `'implementation','__stdin__','stdin','__stdout__','stdout']`; 120 names each, the same set, 113 positions differ. ROW ['sys','vars'] DIFF (70 names against 120; the common names start `audit, exception, exc_info, excepthook, exit` under CPython and `argv, orig_argv, exit, intern, exc_info` compiled). ROW ['builtins','dir'] DIFF (CPython `__import__, __lazy_import__, abs, all`; compiled `aiter, anext, str, type, bool`). _abc, _types, math.integer: SAME on dir and vars. The table has 54 distinct modules, the probe 47 `import` lines. RL-951: "All 47 agree". runtime/src/call.cpp:474 `native_module_named("sys")`. No record of sys's order found in the review log, TODO, DECISIONS or deviations.toml.

Probe: review/c09-tests-and-cases/p4: rows `sys dir`, `sys vars`, `builtins dir` (out.txt)

Suggested: Generate the probe's module list from the table so that no module is left out; order sys at the start as the others are at their import, or record it beside RL-492.

### F48-c09-tests-and-cases-4 (RL-1076): Only A46's fixes got a generated sweep; RL-923 to RL-947 are held by the reviewer's rows and controls alone

*follow-through, reported as medium*; where: pipeline/tests/test_review_2026_11_23_a43.py, test_review_2026_11_24_a44.py, test_review_2026_11_25_a45.py (docstrings and ROWS); review log RL-923 to RL-947

The standing rule asks for a generated sweep of a confirmed defect's class, kept as a test. The A43, A44 and A45 tests are, by their own docstrings, the reviewer's probes with the reviewer's controls. Findings of a plain class with one instance's rows: RL-924 (hex rows; the class has two more members, finding 2), RL-931, RL-943 and RL-947 (an exact str against a str subclass's object: one probe each), RL-926 (a program's value on a namespace the runtime keeps: the two import modules only), RL-934 (an exception inside one exit step: one row), RL-939 and RL-941 (one row each). I swept RL-947's class and it is clean, but no test keeps that sweep.

Evidence: A43 docstring: "The programs are the reviewer's own probes ... the rows that differed and agree now, with the reviewer's controls beside them"; A44: "the rows that differed, with the reviewer's controls beside them"; A45: "each the reviewer's program with controls beside it". ROWS: hex (bytes, array, hexlify), key (visible, _private), modname (replaced, kept, reinit), moddir (subclass, native, plain), bootstrap (internal, external), modkey (alias), slotname (clear), mrotuple (building, identity). p3 (RL-947's class: 101 dict, set, OrderedDict, module and object operations, each with a str subclass's key and an object's key, counting __hash__ and __eq__): `.venv/bin/python r48_both.py review/c09-tests-and-cases/p3 --rows review/c09-tests-and-cases/p3/rows.txt`: 192 of 202 rows SAME, the other 10 stop by name (`dir() of names that are not all str`, `a subclass of str as a keyword's name`). p2: finding 2. Sweeps for RL-926, RL-934, RL-939 and RL-941 were not run by me.

Probe: review/c09-tests-and-cases/p3 (all rows) and p2

Suggested: Keep p2 and p3 as tests (tables of calls, one build each); write the sweeps for RL-926 and RL-934 with the next step on the exit.

> Verifier: **confirmed** (low). A43, A44, A45 tests hold only the reviewers' probes with controls, as their docstrings honestly say; no generated sweep of the classes of RL-924/926/931/934/939/941/943/947 is kept. p3 (RL-947's class) is clean and is not kept. Finding 2 shows RL-924's class did have unswept members. But the 'standing rule' is in the author's memory, not a repo document, and no test claims more than it holds, so low rather than medium. The other instances' classes were not swept by anyone. Cover: not recorded as known or decided; closest: DECISIONS.md:1959 (RL-955 'a defect to fix with a sweep of the class')

### F48-c09-tests-and-cases-5 (RL-1077): Ten rows of the A43 and A44 tests print nothing on either side, and the pipe probe's 'flush' row is never run

*test, reported as low*; where: pipeline/tests/test_review_2026_11_23_a43.py ROWS (exit, gcwarning, roots, pipe); test_review_2026_11_24_a44.py ROWS (exitname, external); pipeline/tests/review_a43/pipe/prog.txt

Under CPython these rows give empty standard output, empty standard error and status 0: a43 exit/warning, gcwarning/save, roots/garbage, roots/callback, roots/warning; a44 exitname/normal, qual, cycle, external/normal, cycle. Each is right as a row (the defect was a finaliser that ran where CPython runs none), but it passes for any program that prints nothing, and nothing shows that the row reached its set-up: the `# reaches:` check that same() got after RL-562 is not in these tests. review_a43/pipe/prog.txt reads a second row, 'flush', which ROWS does not list.

Evidence: review/c09-tests-and-cases/tools/cpy_rows.py (CPython alone, every row of the A43 to A46 probes, hash seeds 0 and 12345): `a43/exit/warning: status 0 stdout-lines 0 stderr-lines 0 EMPTY NO-STDOUT`, and the same for the nine others; no row differs between the seeds or between two runs, and none prints an address or a path on standard output. pipe/prog.txt: `def __del__(self, out=sys.stdout, w=os.write, flush=sys.argv[1]=='flush'):`; ROWS: `"pipe": ("open",)`. CPython prints `before / text / after` for flush and `before / after / text` for open. pipeline/tests/test_review_2026_11_19.py:671: "a program says what it has to reach ("# reaches: text"): two runs that end alike before it prove nothing (RL-562)". The flush row was not run compiled.

Probe: review/c09-tests-and-cases/work/cpy_rows.json (CPython side only)

Suggested: Give each empty row a line it must print before the exit and check CPython printed it; add `flush` to pipe's rows.

> Verifier: **confirmed** (low). Ten rows of the A43 and A44 tests (a43 exit/warning, gcwarning/save, roots/garbage, roots/callback, roots/warning; a44 exitname/normal, qual, cycle, external/normal, external/cycle) give empty stdout, empty stderr and status 0 under CPython alone. Checked with a fresh run at PYTHONHASHSEED=0 and 12345: the same ten, nothing else empty. No '# reaches:' check exists in test_review_2026_11_23_a43.py or test_review_2026_11_24_a44.py (the only 'reaches' in the a44 module is prose in its docstring); the check lives in test_review_2026_11_19.py:672 and same() uses it. ROWS 'pipe' is ('open',) at test ...

### F48-c09-tests-and-cases-6 (RL-1078): C-7-19's docstring contradicts its own recording, and a test names a D-34 that is registered nowhere

*words, reported as low*; where: conformance/cases/C-7-19_abc.py:9 (de36608); conformance/expected/C-7-19_abc.json; pipeline/tests/test_review_2026_11_10.py:1061 and :1065 (f4ba545)

C-7-19's docstring says "a look-up makes a reference of its own, so a metaclass's __hash__ and __eq__ run at each one". Its recording shows no hash at the second look-up, RL-938 of the same day rests on the hash being kept, and DECISIONS says "A look-up makes no reference for a class". Separately, the test changed in f4ba545 says `_setup` differs "(D-34)": there is no D-34 in the spec, deviations.toml, DECISIONS or TODO at that commit; the register ends at D-33.

Evidence: C-7-19's expected stdout: `subclass: True ['hash Seen', 'eq Seen Seen']`, then `again: True ['eq Seen Seen']` and `instance: True ['eq Seen Seen']`. docs/DECISIONS.md (2026-11-24, `_abc`): "A look-up makes no reference for a class. CPython looks up with the class's basic weak reference ... so its hash is computed once and kept". `grep -n "D-34" docs/dialect-spec.md docs/deviations.toml docs/DECISIONS.md TODO.md` prints nothing; test_review_2026_11_10.py:1065: `written_out = {"_setup": "builtin_names"}    # start-up's own: the runtime calls it (D-34)`.

Suggested: Reword C-7-19's docstring (the hash is kept from the first look-up; __eq__ runs at each) and record it again; register D-34 with Question 48's answer or take the id out of the test.

> Verifier: **confirmed** (low). C-7-19's docstring (conformance/cases/C-7-19_abc.py:9, from commit de36608 per git blame) says 'a look-up makes a reference of its own, so a metaclass's __hash__ and __eq__ run at each one'. Its recording has 'subclass: True ['hash Seen', 'eq Seen Seen']', 'again: True ['eq Seen Seen']' and 'instance: True ['eq Seen Seen']' (no hash at the later look-ups). docs/DECISIONS.md:1841 (2026-11-24) says 'A look-up makes no reference for a class ... so its hash is computed once and kept'. 'D-34' appears in no spec, deviations, DECISIONS, TODO, conformance, runtime, refmodel or pipeline file except pip ...

Minor, one line each, not verified:

- A46 test: OPEN holds names, not differences, so an OPEN function whose code object comes to differ in another way still passes.
- A46 test, line 99: for a name only the compiled side prints, the message's `cpython[name]` raises KeyError, so the test fails with a KeyError and not with its own message.
- C-9-13 as recorded reduces every child line to its tag, the abc row's `registered: True True` too, so the corpus no longer holds those two values (test_exit_steps.py does).
- The recorded JSON's `source` field keeps only the first line of a `# source:` header that runs over several lines (C-8-22, C-9-13, C-9-14, C-3-82).
- C-8-22's `where()` prints `__init__.py` for three different files (importlib's, importframes/parent's, importframes/other's).
- Each build test of the range returns at once when g++ is missing (50 test modules do): it reports a pass with nothing run. CI has the compiler, so nothing is hidden there.
- REPORT.md is not in my folder: the Write tool refuses report files from a subagent, and I did not go around it. This output is the full account; the probes, rows, raw outputs and helper scripts are under review/c09-tests-and-cases/ (p1 to p6, tools/, work/).

Covered: Rule 1 (expectations only from CPython): every change of an expected/*.json since 2026-11-23 23:00 is in a commit that changes its case (2c342bc, de36608, 6ed9635, 293c2dc, 25e2f67, ad18417, 0c25f5e). I took conformance/ out of each commit with git archive and ran harness.py verify under 3.15.2: all ten case-at-commit pairs reproduce, and the seven at the head do too, without and with bytecode caches. ad18417 changed only the spec header line of three cases and their recordings. Clean.

Rule 2 (structured observables): read C-3-82, C-7-19's new rows, C-8-22 with importframes/, C-9-13 with exitpkg/, C-9-14 with dyingpkg/. No str(exc) of a built-in exception, no address, size, timing, listing order or free hash seed; deaths of one collection are printed sorted. Clean.

Rule 3: read the A43, A44, A45 and A46 tests, test_module_locks.py, test_exit_steps.py, test_builtins_binding.py, the four new tests of refmodel/tests/test_cases.py (run under CPython: pass) and the diffs of test_stateful.py and test_abc.py. Ran CPython's side of every probe row under two hash seeds. Swept 44 ways of binding __builtins__ through check_builtins_binding: every form in a module's text that rebinds it under CPython is refused; only computed ones (globals()[...], setattr on the module, a star-import) are not, which E-06's words leave out.

Rule 4: findings 2 and 4, with two class sweeps built and run (p2: 135 calls; p3: 202 rows).

Rule 5 (A46's OPEN): by the code and by a real run (p1), a name outside OPEN that differs fails, an OPEN name that agrees fails, and all 29 OPEN names are printed by CPython and differ today. The hole is finding 1.

Rule 6 (baselines): ran the range's seven cases under eval1 and eval2 through a copy of the harness: every case listed passes on that leg and every case not listed fails there, so none is missing from a baseline it passes. Compiled: C-8-22 (p5) and C-9-14 (p6) agree with CPython.

Six builds used (p1 to p6). Nothing tracked was modified.

Not covered: The compiled sides of the A43, A44 and A45 probes, of test_exit_steps.py and test_module_locks.py, and of C-3-12, C-3-82, C-7-19 and C-9-13 (no builds left; pytest and make were not allowed). The nightly CI's result was not read (no outside calls about the repository). refmodel.selftest and the hypothesis run of test_stateful.py were read, not run. conformance/names-baseline.txt and names-surplus.txt did not change in the range and were not checked against the D-33 stops. Not run: sweeps for RL-926, RL-934, RL-939 and RL-941; the pipe/flush row compiled; the positional, bytes.rsplit and bytearray.split variants of finding 2 (same lines by reading only). For finding 3 I did not check what the spec promises of the order of sys's names. No CPython C source was fetched, and nothing here states what the C does. REPORT.md was not written (the Write tool refused a report file from a subagent).


## c10-docs-consistency: the documents of the two days against each other

### F48-c10-docs-consistency-1 (RL-1011, with the same subject): D-19 was ended on a false premise: the runtime's own modules are still immortal, and a program sees it at the exit

*wrong-fact, reported as high*; where: docs/dialect-spec.md:196 (section 9, v0.39), :247 (section 11), :222 (D-07); docs/DECISIONS.md:1936 (Question 44), :1920, :1791; docs/design.md:75

Spec section 9 says "A module object is reference-counted like any other object" and section 11 "there is no difference left to list". Question 44's reason: the runtime's own modules "live until the exit, but a program can take none out of `sys.modules` (E-04), and while one is there it lives on both sides". At the exit CPython takes them out itself and a C module dies; compiled it never does (DECISIONS:1920 "stay immortal"; design.md:75). A weak reference's callback shows it, and D-07 promises "which objects are finalised is CPython's". DECISIONS:1791 listed the gap on 2026-11-23 ("No case reaches it"); it is in no TODO or register entry.

Evidence: `.venv/bin/python r48_both.py review/c10-docs-consistency/p2 --rows review/c10-docs-consistency/p2/rows.txt` (saved as p2/out.txt). Row `exit math` (`sys.kept_reference = weakref.ref(math, callback)`, the local name deleted, nothing written to sys.modules): CPython stdout `end of program` / `math died`; compiled `end of program` only. The same DIFF for `exit time` and `exit zlib`. Controls SAME: `exit json` (`json died` on both), `exit plainmod` (the program's own module, died on both), `exit itertools` (no callback on either). Second trace, rows `spec atexit`, `spec itertools`, `spec _bisect`, `spec math`, `spec zlib` (`importlib.util.module_from_spec(importlib.util.find_spec(name))` called twice): `first is second` is False under CPython (two module objects) and True compiled (one); `spec json` and `spec plainmod` SAME. Quotes: docs/dialect-spec.md:247 "Module objects are counted now (section 9), so there is no difference left to list"; docs/DECISIONS.md:1791 "The state of a C module that CPython frees with its module stays alive here as a root ... No case reaches it."

Probe: review/c10-docs-consistency/p2, rows `exit math`, `exit time`, `exit zlib`, `spec atexit`

Suggested: Put to the author as a correction of Question 44: native modules die at the exit as CPython's do, or a register entry says they live to the end of the process; reword section 9's sentence and section 11's paragraph to match; add the `exit math` row to a case.

### F48-c10-docs-consistency-2 (RL-979, with the same subject): Two recursion-limit entries for a constructor call hold only where CPython specialises the call; D-17's words and the queued step leave out the calls it never specialises

*unsound-recommendation, reported as high*; where: docs/dialect-spec.md:232 (D-17, v0.34); docs/deviations.toml:112; docs/DECISIONS.md:1908 (Question 38: B); TODO.md:747; docs/reviews/review-log.md:1051 (RL-639)

D-17 says the counter takes "two for a class's call that enters a Python `__init__`, as CPython's specialised call does" and names as CPython's exceptions only "a call site's first calls"; option B was put as "agreeing from a site's third call". CPython 3.15.2 specialises only a positional call of a class with no metaclass, no `__new__`, no built-in base that brings its own, and an `__init__` without `*args`, `**kwargs` or keyword-only parameters. Every other constructor call takes one entry for good. Compiled takes one everywhere today, so the queued step as worded makes the plain call agree and turns the others, which agree today, into differences D-17 does not name.

Evidence: review/c10-docs-consistency/cpython-src/specialize.c:1655-1702 (`specialize_class_call`: `if (Py_TYPE(tp) != &PyType_Type) goto generic;`, `if (tp->tp_new == PyBaseObject_Type.tp_new)`), 1472-1481 (`function_kind`: CO_VARARGS, CO_VARKEYWORDS or co_kwonlyargcount is not simple), 1915 (`_Py_Specialize_CallKw` has no class branch). `.venv/bin/python -I review/c10-docs-consistency/cpy/facts4.py` and `facts5.py` (depth a recursion through the constructor reaches under a limit of 60, four runs): positional `Made()` [30, 29, 29, 29]; keyword `Made(n=...)` [58, 58, 58, 58]; starred `Made(*a)` [58, 58, 58, 58]; `__init__(self, *a)` 58; `__init__(self, *, k=0)` 58; `__init__(self, **kw)` 58; a Python `__new__` 58; a metaclass 58; an Exception subclass 58; a list subclass 58. Probe p1 (p1/out.txt), compiled: every shape [58, 58, 58, 58]. Rows `d17 varinit`, `d17 kwonlyinit`, `d17 new`, `d17 meta`, `d17 exc`, `d17 list`: SAME today. Row `d17 pos`: DIFF, CPython `pos [30, 29, 29, 29]`, compiled `pos [58, 58, 58, 58]` (the known one, TODO.md:747).

Probe: review/c10-docs-consistency/p1, rows `d17 pos`, `d17 kw`, `d17 varinit`, `d17 kwonlyinit`, `d17 new`, `d17 meta`, `d17 exc`, `d17 list`; cpy/facts4.py, cpy/facts5.py

Suggested: Before the step is built, ask the author: count two only under specialize_class_call's conditions (positional call, metaclass `type`, object's tp_new, an `__init__` without star or keyword-only parameters) and name the residue in D-17; or option A. One test row a shape.

### F48-c10-docs-consistency-3 (RL-959, with the same subject): D-31's "never in their length" cannot hold beside D-03

*wrong-fact, reported as medium*; where: docs/deviations.toml:197; docs/dialect-spec.md:243 (D-31, v0.30), :218 (D-03); TODO.md:868-871; docs/DECISIONS.md:1892 (Question 33)

D-31 says the bytes of `marshal.dumps` at version 3 and above differ from CPython's "in type bytes ... and in the numbers of the back-references after it, never in their length". A back-reference replaces an object met again by five bytes, and CPython finds it by identity, which D-03 registers as differing in both directions. An int up to 63 bits is an immediate compiled, so `[x, x]` and `[a, b]` with equal ints are one input there, while CPython's outputs for the two differ in length; a constant tuple returned twice is one object in CPython and two compiled. D-03's last sentence makes such a change a defect. The port is not written yet.

Evidence: review/c10-docs-consistency/cpython-src/marshal.c:399-411 (`w_ref`: an entry found by the object's address is written as `w_byte(TYPE_REF, p); w_long((int)w, p);`). `.venv/bin/python -I review/c10-docs-consistency/cpy/facts1.py`: `x = int("1099511627776"); marshal.dumps([x, x])` is 21 bytes, `5b02000000ec030000000000000000047200000000`; two equal objects `[a, b]` 27 bytes, `5b02000000ec03000000000000000004ec03000000000000000004`; `[pair(), pair()]` with `def pair(): return (11, 22)` 22 bytes, the second a back-reference; floats 19 against 23, strs 20 against 25, bytes 21 against 27, tuples 22 against 29. Probe p1 (p1/out.txt): row `d03 int40` (`int("1099511627776") is int("1099511627776")`) CPython False, compiled True; row `d03 pair` (`pair() is pair()`) CPython True, compiled False. runtime/include/bella/object.hpp:63: "Obj: a tagged word: a 63-bit integer immediate". The examples D-31's `observable` quotes are right as measured (cpy/facts6.py), and `marshal.version` is 6.

Probe: review/c10-docs-consistency/p1, rows `d03 int40`, `d03 pair`; cpy/facts1.py, cpy/facts6.py

Suggested: Reword D-31 before the case is written: the bytes follow the program's counts and identities (D-03), so their length can differ too; `loads` gives equal values. Tell the author: "at equal length" was part of what Question 33's option A was put with.

### F48-c10-docs-consistency-4 (RL-1021, with the same subject): Section 4 promises a compile-time error for every exclusion and no approximation; E-05's and E-06's new clauses run on with other results

*inconsistency, reported as medium*; where: docs/dialect-spec.md:71 (section 4), :79 (E-05, v0.40), :80 (E-06, v0.41); docs/DECISIONS.md:1938 (Question 45), :1942 (Question 46); docs/reviews/review-log.md:1356 (RL-944)

Section 4 opens: "Each exclusion is a compile-time error with an id ... Nothing on this list is approximated at runtime." The clause E-05 got in v0.40 (a class's dict written through its proxy's `|`) and the dynamic forms of E-06's v0.41 clause ("excluded and not checked") are neither refused nor stopped: the compiled program ends with status 0 and an answer CPython does not give. Question 45's option A was put beside `gc.get_referents`, which stops by name. E-06's older clause, reached by `setattr(builtins, "len", f)`, ends in a stop that names neither E-06 nor the cause. No TODO item, lint item or test holds any of it.

Evidence: Probe p1 (`.venv/bin/python r48_both.py review/c10-docs-consistency/p1 --rows review/c10-docs-consistency/p1/rows.txt`, saved as p1/out.txt). Row `e05 or`: CPython `42 42 42 True` / `False None False`; compiled `42 None None True` / `False 1 False`, status 0. Row `e05 method` (`types.MappingProxyType.__ror__` called directly): the same pair. Rows `e06 globals` (`globals()["__builtins__"] = table`), `e06 setattr`, `e06 vars`: CPython `after: 42`, compiled `after: 0`, status 0. Rows `e06 battr`, `e06 bdict`: CPython `after: 42` / `here: 42`; compiled status 70, `bella: not implemented: the report of an exception when sys.stderr cannot be written (CPython writes the object's address and reference count to the C stream)`. Row `delb` SAME, as the decision says. `.venv/bin/python -I cpy/facts3.py`: `proxy | g` hands out the class's dict and `proxy == g` a copy, so E-05's own fact is right. runtime/prelude/gc.py:189 and :92: `gc.get_referents` stops with "(CPython's object graph, E-05)". docs/DECISIONS.md:1942: "What reaches the name dynamically ... is excluded and not checked."

Probe: review/c10-docs-consistency/p1, rows `e05 or`, `e05 method`, `e06 globals`, `e06 setattr`, `e06 vars`, `e06 battr`, `e06 bdict`

Suggested: Ask the author: a stop with E-05's id where mappingproxy's `|` hands a class's dict to an operand that is no mapping (no cost on dict writes; not among Question 45's options), likewise for a store of `__builtins__` into a module's namespace; or reword section 4's lead and queue the lint rules.

### F48-c10-docs-consistency-5 (RL-1009, with the same subject): RL-668 is fixed by Question 43's step and still open in the review log and in TODO

*follow-through, reported as low*; where: docs/reviews/review-log.md:1080; TODO.md:903-908; docs/DECISIONS.md:1944

RL-668 (importlib's six frames missing from a traceback through `importlib.import_module`) is still "Open, a step of its own" in the review log and "Open from review A31" in TODO, with the step described as to do. Question 43's step (`0c25f5e`, 2026-11-25) did it: the recorded case C-8-22 holds exactly those six frames and is in the compiled baseline. Neither the row nor the TODO item was closed with the step.

Evidence: docs/reviews/review-log.md:1080: "| RL-668 | A31-12 | `importlib.import_module` of a module that raises shows none of importlib's six frames | ... | Confirmed | Open, a step of its own". TODO.md:903-908: "A step of its own, with the recursion limit's count of those frames (RL-639): the bootstrap's functions as shown frames, and the removal for the import statement the runtime's to do." conformance/expected/C-8-22_the_import_systems_frames.json, the row of `importlib.import_module("importframes.by_name_value")`: `_gcd_import`, ('<frozen importlib._bootstrap>', 1353, '_find_and_load'), (1249, '_find_and_load_unlocked'), (857, '_load_unlocked'), ('<frozen importlib._bootstrap_external>', 751, 'exec_module'), (491, '_call_with_frames_removed'), ('by_name_value.py', 1, '<module>'). conformance/evalc-baseline.txt:222: `C-8-22_the_import_systems_frames.py`.

Suggested: Fix: RL-668 to Fixed, naming C-8-22; take the first half out of TODO's item (its second half, the class RL-698, stays open).

> Verifier: **confirmed** (low). RL-668 is still open in review-log.md:1080 and TODO.md:903-908 although Question 43's step (0c25f5e, 2025-11-25 commit date Nov 25) made C-8-22 hold its six frames. The recorded expectation for importlib.import_module('importframes.by_name_value') lists exactly _gcd_import, _find_and_load, _find_and_load_unlocked, _load_unlocked, exec_module, _call_with_frames_removed, and C-8-22 is in evalc-baseline.txt:222. DECISIONS.md:1944 is the decision paragraph of the step. Neither the log row nor the TODO item was closed; TODO's Question 43 entry (line 837) says Done without naming RL-668, so no exist ...

### F48-c10-docs-consistency-6 (RL-1079): A test at the head names D-34, which does not exist

*inconsistency, reported as low*; where: pipeline/tests/test_review_2026_11_10.py:1061, :1065 (commit f4ba545); docs/deviations.toml:210; TODO.md:845

The head commit's test names a deviation "D-34" for `_setup`'s parameters. The register ends at D-33 in both copies and nothing else in the checkout has the id. `_setup` is one of Question 48's 27 functions, and Question 48 is put and not answered, so the comment gives a register number to a difference the author has not decided.

Evidence: `grep -rn "D-34" --include=*.py --include=*.md --include=*.toml --include=*.cpp --include=*.hpp .` (review/ and build/ left out) finds two lines: pipeline/tests/test_review_2026_11_10.py:1061 "pin's parameters too; `_setup` alone differs, taking what the runtime's start gives it (D-34)." and :1065 `written_out = {"_setup": "builtin_names"}    # start-up's own: the runtime calls it (D-34)`. `git show f4ba545` adds both. docs/deviations.toml:210 `[deviations.D-33]` is the last entry; docs/dialect-spec.md:245 the last row. TODO.md:845: "Question 48: ... put to the author 2026-11-25". pipeline/tests/test_review_2026_11_25_a46.py, REWRITTEN, holds `_bootstrap._setup`.

Suggested: Reword the two comments to name Question 48 until the author has answered and an entry exists.

### F48-c10-docs-consistency-7 (RL-1080): The "queue's item on names under an exclusion" is not in the queue, and those stops say "not yet"

*follow-through, reported as low*; where: docs/DECISIONS.md:1956; TODO.md (no such item); runtime/src/call.cpp:1863

DECISIONS says of the new table of stop reasons: "The same table is where the queue's item on names under an exclusion (sys.settrace, sys.getrefcount, code.co_consts) goes." TODO has no such item and never had one. Meanwhile the stop for a name the spec excludes (E-02, E-03, E-05) says "CPython has it; the runtime does not yet", which promises what the spec rules out.

Evidence: docs/DECISIONS.md:1956 (quoted in the claim). `grep -n "settrace" TODO.md`: no line; `getrefcount` and `co_consts` appear only inside the history lines 601 and 509; `git log -S"settrace" -- TODO.md`: no commit. Probe p1 (p1/out.txt), compiled, status 70: row `stop sys settrace`: `bella: not implemented: sys.settrace (CPython has it; the runtime does not yet)`; the same words for `stop sys getrefcount`, `stop sys setprofile`, `stop code co_consts`, `stop code co_code`. Row `stop boot _ModuleLock` gives D-33's reason, as documented. runtime/src/call.cpp:1863 has the default reason. conformance/names-baseline.txt:205 and :220 list `sys:getrefcount` and `sys:settrace` among the names the runtime lacks.

Probe: review/c10-docs-consistency/p1, rows `stop sys settrace`, `stop sys getrefcount`, `stop sys setprofile`, `stop code co_consts`, `stop code co_code`

Suggested: Register: write the item into TODO (the table can give E-nn reasons as it gives D-33's), or do it with the next step that touches call.cpp.

> Verifier: **confirmed** (low). The queue's item on names under an exclusion is not in TODO.md: grep finds no 'settrace' line, 'git log -S settrace -- TODO.md' gives no commit, and 'getrefcount' (TODO.md:601) and 'co_consts' (TODO.md:509) occur only in history lines. DECISIONS.md:1956 quote is verbatim. The stop for an excluded name reads 'CPython has it; the runtime does not yet' (call.cpp:1863 default), and the probe shows it for sys.settrace, sys.getrefcount, sys.setprofile, code.co_consts and code.co_code, all status 70. The spec excludes settrace/setprofile under E-03, getrefcount under E-05, co_consts/co_code under E-0 ...

### F48-c10-docs-consistency-8 (RL-1081): What the documents say of themselves went stale, and nothing keeps the register's two copies in step

*words, reported as low*; where: docs/dialect-spec.md:7, :153, :223; docs/deviations.toml:1-3, :56; docs/README.md:12, :23; docs/reviews/review-log.md:1579

What the documents say of themselves is stale, and nothing keeps the register's two copies in step. The spec says "This is v0.13" (its log ends at v0.42); deviations.toml and docs/README.md say v0.7; the toml's header says the harness and bella-lint read it, and no code does; the review log says the next id is RL-923 (the last is RL-957); section 7 says 175 modules are recorded in closure.lock.json (183). The one disagreement between the copies that a script finds is D-08's lint.

Evidence: docs/dialect-spec.md:7 "This is v0.13"; :373 "v0.42 (2026-11-25, ...". docs/deviations.toml:1 "# Deviation register (dialect specification v0.7, section 11), machine-readable."; :2 "# The conformance harness and bella-lint read this file." docs/README.md:12 "dialect specification v0.7". `grep -rln "deviations" --include=*.py pipeline tools conformance refmodel validation runtime`: four files, each a comment or a docstring; conformance/harness.py keeps its own SIMULATIONS. My script over both copies (ids, status, lint): all rows agree but D-08, spec "Detectable by lint: No" (:223), toml `lint = "yes"` (:56). docs/reviews/review-log.md:1579 "Number its findings on from the last ID (`RL-923` next)". closure.lock.json: "module_count": 183; docs/dialect-spec.md:153 "175 modules ... recorded in `closure.lock.json`".

Suggested: Fix in one pass, and add a small test that reads both copies of the register (ids, status, lint).

> Verifier: **refuted** (low). The stale self-descriptions are confirmed: spec:7 'This is v0.13' with v0.42 at :373; deviations.toml:1 and README.md:12 say v0.7; toml:2 says the harness and bella-lint read the file and no code reads it (only a README/comment mention); review-log:1579 'RL-923 next' while RL-957 is last; spec:153 '175 modules ... recorded in closure.lock.json' while the lock's module_count and modules dict both give 183. Refuted in part: the claim that the one disagreement between the copies is D-08's lint is wrong. A row-by-row script also finds D-20, which is in deviations.toml (line 123) but has no row in  ...

Minor, one line each, not verified:

- docs/dialect-spec.md:247 gives "Questions 36 and 43" for D-19's end; the decision that ended it is Question 44 (docs/DECISIONS.md:1936).
- TODO.md:123 "`marshal` and `zipimport` (Question 33)": zipimport is Question 34. Both are queued three times (TODO.md:123, :868 and :877, and the older :885, which still offers "or a stop where a zip archive is on `sys.path`", closed by Question 34).
- RL-943, RL-945 and RL-947 are "Fixed" without naming their test (pipeline/tests/test_review_2026_11_25_a45.py holds them); RL-944's row ends at "Excluded (E-05)" with no note of Question 45; that test's line 15 still says RL-944 and RL-946 "are the author's".
- `Lib/_pyio.py:2444` is cited for the assert (docs/DECISIONS.md:1904, TODO.md:981); in the pinned library the assert is line 2446 and 2444 is `skip_bytes = int(self._b2cratio * chars_to_skip)`. The number goes into the upstream report.
- RL-950 (docs/reviews/review-log.md:1362) says `_find_and_load` takes `_ModuleLockManager(name)` at `_bootstrap.py:1339`; in 3.15.2 that line is `lock = _get_module_lock(name)`, and `_ModuleLockManager` is used at lines 821 and 886.
- The A43 row of the reviews-received table says "Eleven are of the exit step"; by its own list ten are (10 + 1 + 2 + 1 = 14). Written 2026-11-23, just before the range.
- D-03's and section 2's example "a tuple of constants is made at each evaluation" stops being true with the folding the same Question 37 decided; TODO's folding item (TODO.md:776) does not say the words go with it.
- The `bytes`, `bytearray` row (docs/dialect-spec.md:119, v0.36) names `recv_into` among the [P1] places a view is written into; `socket` is [P2+] in section 7.

Covered: Read whole: docs/dialect-spec.md, docs/deviations.toml, docs/DECISIONS.md 1876-1960, the diffs of TODO.md and docs/design.md over de36608^..f4ba545, review-log rows RL-923 to RL-957 and the reviews-received table (every linked review file exists). Each spec version entry v0.30 to v0.42 was checked against the text it names (D-03, D-07, D-17, D-31, D-32, D-33, E-05, E-06, D-19's paragraph, section 2's sizes and identity rows, section 8's Resources, section 9, decision 16, the memoryview rows, the Persistence row): all thirteen describe text that is there. Every register entry's id, status and lint was compared between the spec's table and deviations.toml by a script; the entries changed in the range also word for word.

Re-measured under CPython 3.15.2 and found right: marshal.version 6 and D-31's quoted bytes; the fourteen lock names; `_find_and_load`'s six locals; `_lock_unlock_module([])` a TypeError; D-33's hash counts (twice in `_get_module_lock`, twice in `cb`, with `_imp.lock_held()` true; none through `import_module`; `cb`'s two after `del` of a kept exception); getsizeof 56, 88, 43, 40 and 132; 32 modules at start; E-05's `|` against `==`.

Counts I made and found right: D-30's 15 modules in its order (compiled, p1 row `start`); 14 names in ABSENT_BY_ENTRY; 158 functions in bootstrap_frames.json (74 + 84); REWRITTEN 27 = 11 + 7 + 2 + 3 + 4, 25 without the two cache functions; 47 modules in the native-order sweep; 1c's 28 modules = 21 + 1 + 2 + 2 + 2; 236 baseline lines of 239 cases; 22 C-8 and 14 C-9 cases; \"some hundreds of thousands\" of calls on the default stack (p1 row `d17 stack`).

`check_builtins_binding` was read and run over 80 binding forms against CPython's symbol table (cpy/e06_sweep.py): it refuses what DECISIONS lists. Answered questions 29 to 47 were checked against TODO: each is done or queued with what was decided, but for findings 4, 5 and 7. Two builds used: p1 (48 rows) and p2 (14 rows); outputs in review/c10-docs-consistency/p1/out.txt and p2/out.txt, CPython measurements in cpy/*.out, CPython sources read in cpython-src/.

Not covered: REPORT.md was not written: the harness refused the file write (\"Subagents should return findings as text, not write report files\"), and I did not work around it. This output carries the full account; the probes, their outputs and the CPython measurements are in review/c10-docs-consistency/ (p1, p2, cpy, cpython-src).

Not examined: the review files A44 to A46 and W47 beyond their existence and the table's summaries (W47's 37 observables were not run again, only D-33's). The \"149 code objects\", \"29 differ\" and \"all 47 native modules agree\" need the tests' own builds, which I did not run. docs/licences.md, CLAUDE.md and README.md were not changed in the range (CLAUDE.md has no exclusion range to go stale); docs/emitter.md's one changed sentence was read, not tested. The compiled behaviour behind C-9-13's split, C-9-14, C-8-22 and the module-locks test, beyond the rows of p1 and p2. Whether `importlib.util.module_from_spec` of a built-in module is inside the dialect under E-04 (finding 1's second trace). DECISIONS before line 1876 and the spec's older rows, except where a sentence of the range pointed at them.


## c11-run-time-cost: the run-time cost of the two days' steps

### F48-c11-run-time-cost-1 (RL-1082): A failed attribute read throws three times: hasattr/getattr-default/except AttributeError cost 22 us against 80-560 ns; design.md says getattr with a default never throws

*cost, reported as medium*; where: runtime/src/ops.cpp optional_getattr (try { getattr } catch); runtime/src/call.cpp refuse_absent_attribute hook; docs/design.md line 536

For an instance or class, a missed attribute read costs 130.8k instructions (22 us): execute<Instance> throws, raise throws, getattr catches and rethrows, optional_getattr catches again. Modules do not throw (module_getattr suppress), so they cost 1.5 us. design.md line 536 states the runtime never throws for getattr with a default and that a pass rewrites try/except idioms, and that a throw costs 1.7 us; measured raise/catch is 6.1 us and getattr-with-default throws. Origin 2026-11-04, before the window, but it is the largest hot-path cost measured.

Evidence: p3 rows attrmiss 20000 k (ns per miss, CPython/compiled): 0 try:p.zzz 559/22273; 1 hasattr(p) 80/23304; 2 getattr(p,'zzz',1) 110/21861; 4 hasattr(P) 115/16001; 3 hasattr(module) 151/1527; 6 hasattr hit 155/711. cg.miss1k.out: 130.8k instr per miss, _Unwind_RaiseException 29%, intern 16%, cpython_find only 3%; throw counts 1012/1049, rethrow 1043. p1 exc 100000: 6091 vs 209 ns.

Probe: p3 row attrmiss 20000 2

Suggested: Give optional_getattr a non-throwing path for Instance/class without __getattr__ (return Unset, as module_getattr(suppress) does) and use it in hasattr/getattr default; correct the sentence in design.md 536 (or implement it).

> Verifier: **confirmed** (medium). For an instance or class, hasattr and getattr-with-default throw and catch the AttributeError (about 21 us per miss against CPython's 0.1 us); only modules take a no-throw path (about 1 us). design.md:536, l2.md:384-387 and DECISIONS.md:482 say these use sentinels and never throw, which is false. Performance is not semantics (spec section 1), so the defect is the words; the try/except idiom pass is already planned (TODO.md:662). Cover: None for hasattr/getattr-default. TODO.md:662 plans a try/except idiom pass for phase 2 (known only for the try row). The docs claim the opposite: 'the runtime never throws for a miss it expects (... `getattr` with a default ...)'.

### F48-c11-run-time-cost-2 (RL-1083): rooted_namespace (25e2f67) interns __name__ and does two dict probes for every function, frame and traceback the collector visits

*cost, reported as medium*; where: runtime/src/core.cpp rooted_namespace / visit_globals

Each visit_globals call costs 417 instructions (intern("__name__") builds a std::string and hashes: 193; two exact_str_get: 169) and a collection visits each function many times (mark, scan, give back, collect_white, deduce_unreachable, clear). DECISIONS says the 6.3% walk cost was removed; this per-visit cost stays and was not measured for a heap that holds many methods or churns classes (counted classes now die through the collector).

Evidence: p3 mem_class 1000 5 (cg.memcls.out): 102,832 calls = 42.9M instr = 9.0% of the run. p1 mkclass5 4000 gc on (cg3.mk5gc.out): rooted_namespace 85.8M = 6.4% of run, 17.8% of the collector; 39.8 us per class with gc off vs 64.2 us with gc on. p1 gcwalk 5 100 20 (cg.gcwalk.out): visit_globals 33% of the collection loop (93,517 calls, 406 each).

Probe: p1 gcwalk 5 100 20; p3 mem_class 1000 5

Suggested: (a) static const Str* const for "__name__" (-46%); better (b) cache the verdict per Module with a collection serial, or a rooted flag kept where the import system stores/deletes sys.modules entries (program writes are E-04).

> Verifier: **confirmed** (low). rooted_namespace pays intern("__name__") plus two dict probes on every visit_globals call. Re-annotating the reviewer's callgrind files gives 9.0% of p3 mem_class 1000 5, 6.4% of p1 mkclass5 4000, and 32% of the p1 gcwalk 5 100 20 run. The per-call figure is 280 to 410 instr, and mem_class has 153,255 calls, not 102,832. No false words and no semantic difference; DECISIONS.md:1923 states no cost for the look-up that remains. Cover: DECISIONS.md:1923 ('The collector does not walk a rooted namespace', 6.3% removed) covers the earlier cost only. TODO.md:691: 'When speed becomes a goal'. Spec section 1: 'Performance ... Not semantics'.

### F48-c11-run-time-cost-3 (RL-1084): Every new-attribute store (self.a = a) and class-attribute store runs the 20,000-row CPython names table

*cost, reported as low*; where: runtime/src/ops.cpp:1437/1500/1535 setattr, types.cpp type_setattr_generic, runtime/src/call.cpp refuse_absent_data_descriptor, cpython_find

When the class lacks the name, setattr calls refuse_absent_data_descriptor, which for each non-heap class of the MRO (object) builds "object:name" in a std::string and binary-searches CPYTHON_NAMES, only to refuse names that are members/getsets CPython's type has. 1.25k instructions per instance store, 2.5k per class-attribute store. Pre-window (2026-11-03); 477dddc/02b6d07 only added docs/order rows and throw-path text.

Evidence: p1 inst 20000 (cg2.inst.out): 18.4k instr and 4.2 us per P(i,i) vs CPython 161 ns; refuse_absent_data_descriptor 1.25k x 2 stores = 14%. p1 setattr0 100000 (cg3.setattr0.out): 4.2k instr per C.x = i, 64% in the table, 4 intern calls 16%; 754 ns vs 69. p3 newattr 20000: 6.3 us vs 176 ns.

Probe: p1 inst 20000; p3 newattr 20000

Suggested: Precompute per C type the interned names that are member/getset descriptors (or a per-class bool false for classes deriving only from object) and test a pointer; no table search on the store path.

> Verifier: **confirmed** (low). Every first store of an instance attribute and every class-attribute store runs refuse_absent_data_descriptor, which does a cpython_find table search over the non-heap classes of the MRO. That is about 1.3k instr per instance store and 2.5k per class store. For a class store it runs even when the class already has the name, because the metaclass lacks it. It is 9 to 14% of instance creation and 39% of a class store, not the 64% claimed. No false words and no semantic difference. Cover: RL-255 (review-log.md:521) is why the check exists. design.md:507 plans an inline cache for setattr. Spec section 1: performance is not semantics. TODO.md:691: 'When speed becomes a goal'. No cost note anywhere.

### F48-c11-run-time-cost-4 (RL-1085): import sys and import builtins throw twice per import: 22 us against 0.7 us for import math

*cost, reported as low*; where: runtime/src/imports.cpp ensure_initialized / spec_is_initializing (optional_attr on the spec)

CPython's sys.__spec__ and builtins.__spec__ have no _initializing (verified under .venv/bin/python; False for every other module), so spec_is_initializing takes the throwing optional_getattr path (finding 1): two throws per import, 133k instructions. Pre-window (2026-11-04) but on the repeated-import path the task names, left by 0c25f5e/25e2f67.

Evidence: p3 imp_native 20000 k (CPython/compiled ns): math 185/659, time 191/711, _io 203/712, builtins 182/21663; p1 imp 100000: 152 vs 21908; cg.imp.out: 76% of instructions in ensure_initialized, 3170 raise + 3030 execute<Instance> throws per 3000 imports.

Probe: p3 row imp_native 20000 1

Suggested: Use the non-throwing optional_getattr of finding 1, or read the spec's own dict entry _initializing directly in ensure_initialized.

> Verifier: **confirmed** (low). import sys and import builtins cost about 22 us compiled (CPython 0.17 us; import math 0.86 us) because spec_is_initializing (imports.cpp:135) takes the throwing optional_getattr path on a ModuleSpec that lacks _initializing, which CPython's sys and builtins specs do. One throw pair per import, about 131k instructions. Not covered; DECISIONS.md:482 says expected misses use sentinels. Reading the spec's dict directly would change semantics for custom specs; prefer a generic non-throwing lookup. Cover: No entry for this cost. docs/dialect-spec.md:41 'Performance, memory footprint, start-up time | Not semantics'; DECISIONS.md:482 'the runtime uses sentinels for the misses it expects'.

### F48-c11-run-time-cost-5 (RL-1086): A Python call, an instance creation and each interned literal build std::strings (bind's who, refuse_getattribute_override, intern, Str::index)

*cost, reported as low*; where: runtime/src/call.cpp:248 bind; types.cpp:633 refuse_getattribute_override; object.hpp intern(), Str::index()

bind() builds std::string who = qualname + "()", a std::vector<Ref*> and a std::vector<std::string> on every call though only the error paths use them (f1(s) = 2.2k instr, 391 ns vs 59 ns; bind is 2.3k of 8k instr in _handle_fromlist). refuse_getattribute_override interns "__getattribute__" at every instance creation (1.1k instr). intern(string_view) copies into a std::string key per lookup (~190 instr, even on a hit). Str::index() builds a u32string for every Str. Pre-window; the window's own work is below this noise.

Evidence: p1 call 300000 (cg3.call_300000.out): 307,111 basic_string(char const*) from bind, 94M of 877M instr. cg2.inst.out: refuse_getattribute_override 23.2M/20,394 instances. cg3.imppkg_20000.out: bind 46.3M of 160.4M in _handle_fromlist.

Probe: p1 rows call, inst

Suggested: Build who lazily in the error branches; static const Str* const for literal names; heterogeneous (is_transparent) lookup in intern; ASCII fast path in Str::index().

> Verifier: **confirmed** (low). Every Python call builds std::string who plus a heap std::vector<Ref*> in bind though only error paths use them (call.cpp:248); every instance creation interns '__getattribute__' (types.cpp:633, twice per instance); N() and intern(string_view) copy into a std::string per lookup with no per-site cache; Str::index builds a u32string for every Str. Numbers corrected: who costs 370M of 877M instr (42%, about 1.2k per call), not 94M; refuse_getattribute_override is 1.1k per call, 2.3k per instance. Cover: None for these costs. docs/dialect-spec.md:41 'Performance, memory footprint, start-up time | Not semantics'.

### F48-c11-run-time-cost-6 (RL-1087): Start-up is 109M instructions, 40 ms, 27 MB resident and a 38.7 MB binary for hello; 29% is interning and per-class table searches done at every start

*cost, reported as low*; where: runtime start-up (intern, Str::index, make_class cpython_has, note_prelude_class)

hello: 0.040 s (CPython 0.010), RSS 27.5 MB (CPython 11.5), file 38.7 MB (text 34.4 MB, .rodata 2.7 MB, CPYTHON_NAMES 346 KB, CPYTHON_DOCS 95 KB). Inclusive: intern 24% (Str::index 14.1M of it), cpython_find 5.5% (final/weakref/__new__/flags asked per class made), note_prelude_class 3.1%, finalize_at_exit 4.8%. None is from the six steps: order_as_cpython (477dddc) is 0.44% (0.48M), the frames and counted modules are not visible; but it is work a build-time table would remove.

Evidence: hello/cg.hello.out; /usr/bin/time on prog-61ab23ccbf009556: 0.04 s 27.5 MB; p3 start 0.05 s 41.8 MB.

Probe: hello

Suggested: Emit the interned names and the per-built-in-type final/weakref/flags/__new__ answers as constexpr rows at build time.

> Verifier: **confirmed** (low). hello takes 0.03-0.04 s (CPython 0.01), 27.5 MB RSS (CPython about 11), a 38.7 MB file, 109M instructions; intern 23.9% plus cpython_find 5.5% is 29.4%, from table lookups done at every start. One figure is wrong: Str::index is 14.1M in total but only 7.4M of it is under intern (6.6M is str_new); order_as_cpython does not appear in the hello profile, so its 0.44% cannot be checked there. Cover: None specific. docs/dialect-spec.md:41 'Performance, memory footprint, start-up time | Not semantics'.

### F48-c11-run-time-cost-7 (RL-1088): Dead program classes cost a collection each: 24 us for a 5-method class, and the exit finalizes at 121k instructions per live class

*cost, reported as low*; where: 756222f (classes counted); object.hpp class_clear/class_dealloc/unregister; call.cpp finalize_at_exit

Classes now die only in a collection (as CPython's); churn costs 39.8 us (gc off) vs 64.2 us (gc on) per 5-method class (CPython 8.4 us). Scaling with live classes is not worse than CPython's (both +70% at 10000 live): compiled 25.3/29.3/42.9 us at 0/2000/10000 live (CPython 6.2/6.4/10.7), from the linear std::erase(heap().classes) and leave_bases' erase from object's subclasses. Instance creation and gc.collect() with 10000 live classes are flat (1133/1101 ns; 3.7/4.5 us).

Evidence: p1 mkclass0/1/5 20000 gc off/on: 20.6/23.9, 25.9/35.0, 39.8/64.2 us; p4 churn rows and inst/collect_only rows (out1.txt); p3 mem_class 1000 5: finalize_at_exit 121M instr, 25% of run.

Probe: p4 rows churn 0/2000/10000

Suggested: Mostly finding 2; optionally swap-with-last in heap().classes (not observable) and keep subclasses order (CPython keeps creation order).

> Verifier: **covered** (none). Measurements reproduce (5-method class 67/41 us gc on/off vs CPython 8 us; churn 25.7 to 42.9 us at 0 to 10000 live vs CPython 6.0 to 9.2, same +70%; exit finalize_at_exit 25% of a 1000-class run, linear in classes). But it is a performance cost with no observable difference. Even with gc off the class costs 41 us vs 8, so the cost is creation, not just collection. Not a defect. Cover: docs/dialect-spec.md section 3 'Performance, memory footprint, start-up time | Not semantics'; DECISIONS 2026-11-24 C-3-12 'Cost.' paragraph (accepts 'a class among the candidates of each collection'); TODO.md 'When speed becomes a goal: find the hot paths it refuses' and 'Speeds seen measuring revi ...

### F48-c11-run-time-cost-8 (RL-1089): Memory per object is 2 to 3.4 times CPython's (function 984 B, instance 426 B, 5-method class 7.6 KB); the window adds almost none

*cost, reported as low*; where: runtime/include/bella/runtime.hpp PyFunction, object.hpp Instance/ClassObject

Resident bytes per retained object after gc.collect(), CPython/compiled: instance 128/426; closure 420/984; ModuleType with one attr 327/610; class 0 methods 2205/1685; 1 method 2797/3250; 5 methods 4675/7585 (about 1.2 KB per method vs 0.45 KB). Window growth: ClassObject::cleared 1 byte, Module holders/holds_namespace/serial 24 bytes, GlobalsRef 8 bytes as the Ref it replaced. The per-function size is PyFunction's ~12 Ref fields.

Evidence: p3 rows mem_class/mem_inst/mem_func/mem_mod (p3/out1.txt, bytes/turn).

Probe: p3 rows mem_*

Suggested: Optional: move PyFunction's rarely used fields (annotations, annotate, type_params, kwdefaults, dict, doc) behind one lazily allocated block.

> Verifier: **covered** (none). Memory numbers reproduce (instance 128/426, closure 420/984, module 327/610, 5-method class 4505/7610 B, CPython/compiled) but the stated cause is wrong. PyFunction is 152 B; make_function (call.cpp:242-243) also allocates fresh 104 B Str objects for __name__ and __qualname__ per function, where CPython shares the code's constants, which is about 290 B of strings per function; and the def with a return annotation makes two functions (the function and its __annotate__). The proposed lazy-field block would save about 48 B of ~450 B per function. Declared unobservable. Cover: docs/dialect-spec.md section 3: 'Performance, memory footprint, start-up time | Not semantics' and 'sys.getsizeof values and the sizes they are made from ... Implementation detail'; 'is between equal immutable values (int, float, ... str ...)' may differ

Minor, one line each, not verified:

- p3 cycles 20000: R differs (CPython 2012, compiled 66, gc.collect() return value): covered by D-12's note in deviations.toml (the runtime's own numbers), not a finding.
- design.md line 536 says a throw costs about 1.7 us; measured raise/catch of a ValueError is 6.1 us compiled (p1 exc), 12.1 us through a function (p1 excf): the figure is stale.
- The mappingproxy of an immortal class still does intern(k->text) for every probed key (6ed9635 kept it): each distinct string probed through a built-in type's __dict__ proxy creates an immortal Str; unmeasured, rare use.
- refuse_absent_attribute runs cpython_find (string build + binary search per MRO class, plus bootstrap_class_scope's std::string for heap classes) on every attribute miss: 3% of a miss today, only matters once finding 1 removes the throws.
- p1 'method' row: a method call is 1191 ns vs 64 ns (5.4k instr); not attributed to a window step (bind + string building, finding 5).
- ClassObject::dispose copies attrs.items() (a vector) at every program-class release: O(attrs) per class death; negligible next to the collection.
- Callgrind on the p1 and p3 binaries gives per-op instruction counts that are stable (0.1%); wall-clock rows differed 10-30% between runs on the shared host, so only the instruction figures are quoted for ratios.

Covered: Reused the earlier c11 probes (p1 hot-path rows, p2 collector rows, hello) and its callgrind files without rebuilding; reran p1 at larger n against the built binary; added callgrind runs (cg2.*, cg3.*) for inst, call, method, setattr0, imppkg, impos, imp, mkclass1/5; built two new probes (p3: memory per class/instance/function/module, first and repeated imports of program and native modules, ModuleType, failed attribute reads, new-attribute stores, cycles, gc with live classes; p4: class churn against 0/2000/10000 live classes, instance creation and collect-only with live classes). All DIFF rows of p1..p4 differ only in T (time) lines except p3 cycles (gc.collect() count 2012 vs 66), covered by D-12's note in deviations.toml; no stop or exit 70. Read all six diffs (saved as diff_*.txt in the c11 folder). Per step, free or negligible: 756222f (incref/decref of the class per instance, <0.2 ...

Not covered: Old commits cannot be built, so before/after comparisons are argued from the diffs and the current binary's instruction counts; the author's 0.3%/0.6% figures were not reproduced. Not measured: many modules at exit (only 30 small ones), threads, -O1 vs -O2 program flags, dataclass/namedtuple creation, the cost of a failing import and of sys.modules churn, the mappingproxy read in a loop (only argued from the diff; the immortal-class path interns every probed key, an unmeasured immortal-entry growth), wall-clock differences under 5% (instruction counts used instead; host load was 4-5 of 16 CPUs ...


## s1-import-chain: everything a program sees of the import system, both sides

### F48-s1-import-chain-1 (RL-1090): __globals__ of the import system's functions is the runtime's whole namespace; _tuple_set mutates a tuple

*defect, reported as high*; where: runtime/prelude/bootstrap.py and bootstrap_external.py namespaces, reached through any function's __globals__ (probe p4 rows leak count/tuple/external/names; p2 rows globals count/names/external/loader)

[P1] __globals__ of a function of importlib._bootstrap shows 153 names where CPython's has 63: 24 _bella_* names, _tuple_set, _held_once, __intrinsics__, GenericAlias, Union, SimpleNamespace, _ga_*, _union_* (112 names CPython lacks, 22 it has missing, __builtins__ among them). g['_tuple_set'](t,0,99) changes a tuple in place. _bootstrap_external's FileFinder.__init__.__globals__ has 111 names (4 _bella) vs 80 and no __builtins__. 19 methods of _bootstrap_external's classes (_LoaderBasics, SourceLoader, FileLoader, SourceFileLoader) have __globals__['__name__'] == 'importlib._bootstrap' (CPython: importlib._bootstrap_external) and SourceFileLoader.get_filename.__globals__ is ModuleSpec.__ini ...

Evidence: p4 leak tuple. CPython: 'found False' then '(1, 2, 3) True True'. Compiled: 'found True' then '(99, 2, 3) False False'. p4 leak count: CPython 'name importlib._bootstrap len 63 bella 0 tuple_set False', compiled 'len 153 bella 24 tuple_set True'. p4 leak external: 'len 80 bella 0 builtins True' vs 'len 111 bella 4 builtins False'. p2 globals loader: 'importlib._bootstrap_external False' vs 'importlib._bootstrap True'. Controls SAME: importlib.util.find_spec.__globals__ (28 names), p7 54 built-in/types classes' member functions, p6 46 modules.

Probe: review/s1-import-chain/p4 rows 'leak count', 'leak tuple', 'leak external', 'leak names'; p2 rows 'globals *'

Suggested: Fix: give the prelude functions of both modules a globals object that holds only CPython's names (or stop __globals__ by name for them); sweep the class like RL-536 and keep a test; register nothing.

> Verifier: **confirmed** (high). [P1] __globals__ of the import system's prelude functions is the runtime's whole namespace: 153 names (CPython 63) for _bootstrap, 111 (80) for _bootstrap_external, no __builtins__, runtime primitives reachable (_tuple_set mutates a tuple in place, breaking its hash), and 19 methods of _bootstrap_external's classes report __name__ 'importlib._bootstrap'. Partly known: RL-419 records the names in the namespaces and stops dir/vars/__dict__ of the module; the __globals__ route, tuple primitive, __name__ and __builtins__ are new. RL-536 fixed the same route for two intrinsics. Cover: RL-419: 'What the runtime keeps in the two namespaces for itself (89 and 10 names) is no attribute of the modules ... dir(), vars() and __dict__ of the two modules stop by name'; roadmap 'moving the runtime's own names out of the two modules' (DECISIONS 2026-11-10) - covers the names being there, no ...

### F48-s1-import-chain-2 (RL-1091): Traceback line of a multi-line raise ... from (or parenthesised raise) is the last operand's line, not the statement's

*defect, reported as high*; where: compiled traceback line attribution; shows in the import system's own tracebacks (importlib.util.find_spec, NamespacePath._get_parent_path)

For a raise statement spanning lines with a cause, or a parenthesised raise, tb lineno compiled is the line of the cause or exception expression where CPython reports the raise's own line. raise X(\n..\n) with no from agrees; from None agrees. D-06 covers only the line's text, not its number; nothing registered covers it. Also visible in CPython's library text: importlib.util.find_spec('pmod.child') entry is <frozen importlib.util>:94 under CPython, :96 compiled; _bootstrap_external _get_parent_path 1100 vs 1103.

Evidence: p4 rows tbline: 'from [2]' vs '[5]'; 'paren [1]' vs '[2]'; 'causefirst [2]' vs '[3]' (relative to co_firstlineno; extract_tb). p4 'uncaught': CPython 'File .../prog.py, line 92, in raise_from' + '    raise KeyError(' ; compiled 'File "prog.py", line 95, in raise_from'. p2 mlraise from [35,4] vs [35,6], from_own_line [26,2] vs [26,5], parenthesised [18,1] vs [18,2]; plain and keyword SAME. p1: 'step0 traceback [..., <frozen importlib.util>:94:find_spec]' vs ':96'.

Probe: review/s1-import-chain/p4 rows 'tbline from|paren|causefirst', 'uncaught'; p2 rows 'mlraise *'

Suggested: Fix: a raise statement's traceback line is the statement's first line (RAISE_VARARGS has the statement's location); add a case with the four shapes.

> Verifier: **known** (low). A raise statement spanning lines with a cause (or parenthesised) is reported at the last operand's first line (cause / parenthesised expression), CPython at the raise's own line; shows in <frozen importlib.util> entries (94 vs 96). Reproduced, but it is an instance of the open, queued RL-494/RL-225 class (multi-line statement lines; 'raise ( ... )' is named); only the 'raise X(...) from e' shape is not listed there and should be added. Cover: RL-494: 'The line of a traceback entry inside a statement of several lines: ... raise ( ... ) ... CPython has ... the line of the raise; compiled the statement's or expression's first line | Open'; TODO.md 943 'A step of its own: ... the frontend gives each expression its first line'; RL-225 open.

### F48-s1-import-chain-3 (RL-1057, with the same subject): Warnings from importlib.__import__ are attributed to the import system, not the caller

*defect, reported as high*; where: runtime/prelude/bootstrap.py _calc___package__ (_bella_import_warning in place of _warnings.warn(..., stacklevel=3))

A DeprecationWarning '__package__ != __spec__.parent' or ImportWarning "can't resolve package ..." raised by importlib.__import__ is shown at the caller's file and line under CPython, with its source line; compiled attributes it to <frozen importlib._bootstrap>:1440 / :1447, so with default filters the DeprecationWarning is not shown at all. The builtin __import__ agrees apart from the file name. Not in the spec, decisions or review log; C-8-22 holds stacklevel from a module body only.

Evidence: p3 warn package: CPython stderr 'prog.py:13: DeprecationWarning: __package__ != __spec__.parent (\'other\' != \'ppkg\')' + source line; compiled stderr empty. warn package_always: compiled '<frozen importlib._bootstrap>:1440: DeprecationWarning: ...' vs 'prog.py:23'. warn fallback_always: compiled '<frozen importlib._bootstrap>:1447: ImportWarning: ...' vs 'prog.py:19'. warn package_c (builtin __import__): 'prog.py:15: DeprecationWarning: __package__ != __spec__.parent' on both sides, path aside.

Probe: review/s1-import-chain/p3 rows 'warn package', 'warn package_always', 'warn fallback_always'

Suggested: Fix: attribute these warnings as CPython's stacklevel=3 with _is_internal_frame skipping does; add rows to C-8-22; or register.

> Verifier: **confirmed** (high). DeprecationWarning '__package__ != __spec__.parent' and ImportWarning 'can't resolve package...' from importlib.__import__ are charged to <frozen importlib._bootstrap>:1440/1447 without source line (DeprecationWarning then hidden by default filters) where CPython charges the caller's file and line; builtin __import__ agrees. Cause: _bella_import_warning is runtime_warning at stacklevel 1, and since Q43's step (0c25f5e) the prelude's frames are shown, so level 1 is _calc___package__ itself; C-8-22 covers stacklevel only from a module body and 'warnings needed nothing' does not hold for these si ...

### F48-s1-import-chain-4 (RL-1032, with the same subject): A46's code-object sweep and its test skip 25 of 74 bootstrap.py table entries; 7 differ and are in no list (D-34 / Question 48 incomplete)

*test, reported as medium*; where: pipeline/tests/test_review_2026_11_25_a46.py table_names() and review_a46/codeobjects/prog.txt; TODO.md Question 48; RL-948

table_names() maps every entry of the table's bootstrap.py to module _bootstrap, but 25 of 74 entries have file <frozen importlib._bootstrap_external> (_LoaderBasics, SourceLoader, FileLoader, SourceFileLoader methods, _check_name, _get_cached, _path_split, cache_from_source). The probe reaches _bootstrap.SourceLoader.get_code with getattr(...,None), gets None, and show() prints nothing for a non-code object, so they are never compared. Reached by their real names, 7 differ in co_nlocals and co_varnames and are in neither LOCKS, REWRITTEN (27), Question 48 nor the D-34 list: SourceLoader.get_code (15 locals vs 2), SourceLoader.get_source (5/2), SourceFileLoader.set_data (9/4), SourceFileLoad ...

Evidence: python3 over runtime/prelude/bootstrap_frames.json: 25 entries under bootstrap.py with file _bootstrap_external. p1 rows 'get external SourceLoader.!get_code' etc: CPython co_varnames ('self','fullname','source_path',...,'code_object') nlocals 15; compiled ('self','fullname') nlocals 2. TODO.md line 845: '27 of the 149 code objects'.

Probe: review/s1-import-chain/p1 rows 'get external SourceLoader.!get_code|get_source', 'FileLoader.!get_data', 'SourceFileLoader.!path_stats|_cache_bytecode|set_data', '_LoaderBasics.!exec_module'

Suggested: Fix the mapping (use each entry's own file), add the 7 to OPEN, and put them to the author with Question 48 (they refuse by name, so they are among the 20 refused); D-34's list needs them.

> Verifier: **confirmed** (medium). A46's codeobjects sweep never compares 19 loader methods that the table lists under bootstrap.py with file _bootstrap_external. The program reaches them as _bootstrap.X, which is absent, so both sides print <absent> (not silence, as claimed); FileLoader.__init__, __eq__ and __hash__ print nothing. The finding said 25, but 4 module functions among them are also compared under _bootstrap_external, so it is 19. Reached by their real names, 7 differ in co_nlocals and co_varnames and are in neither LOCKS, REWRITTEN, Question 48 nor RL-948's 29 of 149. Their __globals__ also differs on all 19 (impor ...

### F48-s1-import-chain-5 (RL-1092): __firstlineno__ of 15 import-system classes is the prelude's line, inconsistent with the methods' CPython lines

*inconsistency, reported as low*; where: classes of runtime/prelude/bootstrap.py and bootstrap_external.py (32 rows incl. importlib.machinery re-exports and aliases)

RL-952 and C-8-22 gave the functions CPython's co_firstlineno; the classes' __firstlineno__ stayed the prelude's. In no entry. SourceFileLoader.__firstlineno__ (1559) is greater than its own methods' co_firstlineno (942 and up).

Evidence: CPython / compiled: ModuleSpec 547/114, BuiltinImporter 892/421, FrozenImporter 942/472, PathFinder 1180/679, FileFinder 1321/764, SourceFileLoader 938/1559, SourcelessFileLoader 983/502, ExtensionFileLoader 1008/514, NamespaceLoader 1150/650, NamespacePath 1061/561, WindowsRegistryFinder 672/470, AppleFrameworkLoader 1491/847, FileLoader 900/1525, SourceLoader 754/1432, _LoaderBasics 729/1405. p4 lineno: class vs min method line True/True... compiled 'SourceFileLoader _frozen_importlib_external 1559 942 False'.

Probe: p4 row lineno; p3 row 'reflect firstlineno'; p1 32 rows 'get ... __firstlineno__'

Suggested: Give the classes CPython's __firstlineno__ from the same table, or register.

> Verifier: **confirmed** (low). The __firstlineno__ of the import system's prelude classes is the prelude's line, not CPython's: ModuleSpec 114 vs 547, BuiltinImporter 421 vs 892, FrozenImporter 472 vs 942, PathFinder 679 vs 1180, FileFinder 764 vs 764... see reproduction; every class checked differs. CPython's numbers are the class lines of importlib/_bootstrap*.py. The 'inconsistent with the methods' lines' part is not general (in CPython BuiltinImporter/FrozenImporter also sit above their decorator wrappers' lines); the real claim is the plain difference from CPython, SourceFileLoader 1559 vs 938 being the visible symptom ...

### F48-s1-import-chain-6 (RL-1093): Stops for names E-04 excludes say 'the runtime does not yet'

*words, reported as low*; where: runtime/src/call.cpp ABSENT_BY_ENTRY (only the 14 lock names); sys.path_hooks and kin

sys.path_hooks (5 rows) stops with '(CPython has it; the runtime does not yet)' although E-04 excludes it; likewise sys.get_lazy_imports, sys.get_lazy_imports_filter, sys.lazy_modules (D-18 says the lazy mode is always normal but gives no answer). The 11 absent names of the two bootstrap modules (_load, _install, _verbose_message, _object_name, _builtin_from_name, _install_external_importers, _warnings, marshal, _os, _validate_timestamp_pyc, _validate_hash_pyc) are honest not-yet stops; only three are named in Question 47's entry.

Evidence: p1 row 'get sys path_hooks': compiled exit 70 'bella: not implemented: sys.path_hooks (CPython has it; the runtime does not yet)'.

Probe: p1 rows 'sys path_hooks', 'get sys path_hooks', 'chain sys get_lazy_imports'

Suggested: Add sys.path_hooks (E-04) to ABSENT_BY_ENTRY; decide get_lazy_imports under D-18.

> Verifier: **confirmed** (low). sys.path_hooks stops with 'CPython has it; the runtime does not yet' although E-04 (spec line 78) names sys.path_hooks, sys.set_lazy_imports and sys.set_lazy_imports_filter as excluded; set_lazy_imports gives the same wording (not in the finding). call.cpp ABSENT_BY_ENTRY, whose comment says it is for names left out by a registered difference, holds only the 14 D-33 lock names. get_lazy_imports, get_lazy_imports_filter and lazy_modules are not named by E-04; D-18 says the mode is always normal without saying what get_lazy_imports does, so those are an undecided gap rather than a wrong reason.  ... Cover: conformance/names-baseline.txt lists sys:path_hooks etc. as absent only; no record of the stop's wording.

### F48-s1-import-chain-7 (RL-1061, with the same subject): vars(sys) and vars(builtins) are not in CPython's order (RL-951 swept 47 native modules, not these)

*defect, reported as low*; where: sys and builtins module namespaces

list(vars(sys)) starts '__spec__, argv, orig_argv, exit' compiled vs '__spec__, addaudithook, audit, breakpointhook' under CPython; the common names are not in the same relative order. builtins starts 'str, type, bool, range' vs '__build_class__, __import__, __lazy_import__, abs'. The 8 other native modules probed agree.

Evidence: p8 sys: CPython 120 names, compiled 70, 'common order equal False'; builtins 163 vs 154, order equal False; _imp,_io,_warnings,_signal,_codecs,_abc,posix,time SAME.

Probe: review/s1-import-chain/p8 rows sys, builtins

Suggested: Add sys and builtins to CPYTHON_MODULE_ORDER and order_as_cpython; extend RL-951's test.

> Verifier: **confirmed** (low). vars(sys) and vars(builtins) are not in CPython's order. builtins is already recorded (RL-492 Open, TODO.md:948), so the new part is sys. The reviewer's action is partly wrong: sys and builtins are already in CPYTHON_MODULE_ORDER (120 and 157 rows). The fix is to run order_as_cpython on them, since i_bella_create_builtin returns them before it, and to add them to RL-951's hand-written list of 47. RL-951 and DECISIONS:1948 say 'All 47 native modules agree' without saying these two are outside that set. Cover: builtins: review-log RL-492 'the candidates come in the order of the builtins' namespace, which is not CPython's order here' (Open), TODO.md:948 'the builtins' namespace in CPython's order (RL-492)'. sys: nothing records the order of vars(sys); the 50 missing sys names are in the names baseline only ...

### F48-s1-import-chain-8 (RL-1094): A ModuleType subclass has its own __dict__ descriptor

*defect, reported as low*; where: class layout of a subclass of types.ModuleType (importlib.util._LazyModule)

'__dict__' in vars(class M(types.ModuleType)) is True compiled, False under CPython; vars(_LazyModule) has a trailing '__dict__'. SimpleNamespace and Exception subclasses agree.

Evidence: p4 modsub module: CPython "dict False weakref False ['__doc__','__firstlineno__','__module__','__static_attributes__']"; compiled 'dict True ...' with '__dict__' in the list. p1 get util _LazyModule: trailing '__dict__' compiled.

Probe: p4 rows 'modsub module', 'modsub lazy'

Suggested: Do not give a ModuleType subclass a second __dict__ getset.

> Verifier: **confirmed** (low). A class derived from types.ModuleType gets its own __dict__ getset in its namespace, so '__dict__' in vars(class M(types.ModuleType)) is True compiled and False under CPython. importlib.util._LazyModule shows the same. Only the class's own namespace differs: dir(M) agrees, and vars(types.ModuleType)['__dict__'] is a member_descriptor on both sides. The [P1] Attribute access row says a class adds a __dict__ only when its base provides none. Instances of such a subclass stop by name compiled ('a subclass of the module type (step 3b)', imports.cpp:2378), so the difference is reachable only throug ... Cover: None for the extra descriptor. RL-270 says 'a ModuleType subclass stays [P2+]' and the step 3b stop covers instances only. Neither registers or stops the class definition.

Minor, one line each, not verified:

- importlib._bootstrap.__doc__ and _bootstrap_external.__doc__ differ ('Core implementation of import.' / 'Core implementation of path-based import.' vs the runtime's own text); p3 reflect doc; covered by nothing.
- annotationlib has a visible module attribute _bella (dir 'annotate_freevars','annotate_with','refuse','set_class'); CPython has none; set_class is refused by name ([P2+] __class__ assignment); p6 annot, p1 modattrs annotationlib (vars head).
- sys.modules['_imp'].__spec__ has _initializing False compiled, absent under CPython (vars(spec) gains '_initializing'); p4 imp, p1 modattrs _imp.
- D-16's words name cache_from_source only: source_from_cache('a.pyc') also raises NotImplementedError (CPython ValueError) and _get_cached/spec.cached give None (p1 chain util source_from_cache s:a.pyc).
- sys.path_importer_cache is {} compiled (DECISIONS 2026-11-08) but the spec's E-04/D-18 words do not say so; p1 sys path_importer_cache, sys cache_after.
- importlib.abc, importlib.readers, importlib.simple, importlib.resources, importlib.metadata are ModuleNotFoundError compiled (E-04 names importlib.abc; resources [P2+]); p2 names abc/resources/metadata/readers/simple, p3 optional.
- _datetime: import raises ModuleNotFoundError and util.find_spec('_datetime') is None compiled where CPython imports it (manifest omits the C accelerator for _pydatetime); p1 modattrs _datetime.
- D-17/lazy: p2 route lazy deep is 79 CPython vs 78 compiled at limit 90 (one extra counted frame on a lazy import's first use); the other 7 routes' depth agree.
- p5 builtin sig / builtin lazy: inspect.signature(builtins.__import__) and (__lazy_import__) stop on __text_signature__ (names-baseline.txt, known).
- sys.__breakpointhook__, __displayhook__, __interactivehook__, builtins.__build_class__, aiter/anext/exit/quit/help/license/copyright/credits are absent from vars/dir (names-baseline, known).

Covered: Inventory done on the prior reviewer's probes plus my own. Reran p1 (1113 rows), p2 (89), p3 (25) with r48_both.py (no build): same rows differ as before (516, 27, 20 differ; four p1 rows differ between runs only by an mtime, an id() and a sentinel address). Built five new probes (p4 minimal reproductions, p5 sys.modules additions and import-builtin attributes, p6 __globals__ by module, p7 54 builtin/types classes, p8 namespace order); 5 of 8 builds. p1's 516 differing rows: 288 stops by name (zipimport 85, 'does not yet' 78, D-33 locks 62, path finder E-04 20, other named E-01/E-02/[P2+]/files 28, module outside the build 9, namespace as a whole 6), 92 D-16 cached-only, 136 other = 17 code-type members (E-02), 2 D-33 code objects (_find_and_load, _lock_unlock_module), 30 D-34/Question 48 (27 functions + 3 util aliases), 11 more D-16, 6 D-18, 1 D-30, 2 D-34 (_setup signature, invalidate_ ...

Not covered: REPORT.md (refused by the tool; content is here). Not every attribute of every one of the 86 modules was compared (modattrs covers 7 module attributes and the spec's 12). inspect.signature through the 78 'not yet' stops (__text_signature__ of builtins, in names-baseline) was not compared. No CPython C source was fetched; every CPython claim is a run of 3.15.2. Stops hide what follows them (zip archives on sys.path, namespace packages, reload). Threads, -X options, a different working directory were not run. p2 'route lazy deep' (depth inside a lazily imported module's body at limit 90: CPython ...


## s2-coherence-and-plan: the sixteen decisions together, and the queue

### F48-s2-coherence-and-plan-1 (RL-979, with the same subject): Question 38's rule (two recursion entries for a class's call that enters a Python __init__) is wrong for most call shapes, and D-17 already states it

*unsound-recommendation, reported as high*; where: docs/DECISIONS.md:1908; docs/dialect-spec.md:232; docs/deviations.toml:112; TODO.md:747-752; pipeline/tests/test_recursion_counts.py:331,361

B was recommended ('closes the 2x gap, the common case, for almost nothing') on one measured shape. CPython takes two entries only where its specialiser applies: metaclass exactly type, no __new__ but object's, __init__ a plain function without *args, **kwargs or keyword-only parameters, a positional call, one class a site. Of 15 class-call shapes probed it takes two in 4; 8 agree with the compiled program today, 7 of them because CPython takes one, and those become 28 against 56 if the step is built as D-17's words say. D-17's list of where CPython counts otherwise omits all of this, and its 'two' is not what the runtime does yet. The planned case is one row.

Evidence: probe1 (r48_both.py --rows rows.txt; limit 60, three measurements a process), CPython / compiled: plain, slots, defaults, type_self 29,28,28 / 56,56,56 (DIFF). keyword and via_map 56,55,55 / 56,56,56. with_new, exception (class Error(Exception)), list_subclass, star_call, star_def, abc_metaclass, kwonly_init, function 56,56,56 on both (SAME). metaclass_call 28 on both. two_classes_one_site 23,23,23 / 28,28,28. CPython v3.15.2 Python/specialize.c (fetched): 1681 `if (Py_TYPE(tp) != &PyType_Type) { goto generic; }`; 1684 `if (tp->tp_new == PyBaseObject_Type.tp_new) {` then 1696 `specialize(instr, CALL_ALLOC_AND_ENTER_INIT)`; 1646 `if (kind != SIMPLE_FUNCTION)` fails (function_kind: CO_VARKEYWORDS | CO_VARARGS or co_kwonlyargcount); _Py_Specialize_CallKw (1915) has no class path (1937 `CALL_KW_NON_PY`). Python/bytecodes.c:4808-4811, _CREATE_INIT_FRAME: 'Account for pushing the extra frame' `tstate->py_recursion_remaining--;`. test_recursion_counts.py: the only row is `"__init__": Made` (331), in NOT_COMPARED (361). In TODO, DECISIONS and the review log a grep for CALL_KW, SIMPLE_FUNCTION and polymorphic finds nothing; CALL_ALLOC_AND_ENTER_INIT occurs only in the three records of RL-639's one row.

Probe: probe1: rows function, plain, keyword, with_new, exception, list_subclass, slots, defaults, star_call, star_def, metaclass_call, type_self, via_map, two_classes_one_site, abc_metaclass, kwonly_init

Suggested: Do not build as worded. Either words only (one entry; D-17 says where CPython takes two), or B narrowed to the static conditions with the 16 shapes added to test_recursion_counts.py first. Correct D-17's sentence in the spec and the register either way.

### F48-s2-coherence-and-plan-2 (RL-1095): marshal and zipimport (Questions 33, 34) were recommended as ports with no count of use; counted, nothing local uses what the ports give, and they now stand before 1c's gate

*unsound-recommendation, reported as medium*; where: docs/DECISIONS.md:1892,1894; docs/dialect-spec.md:147,243 (D-31); TODO.md:123,868-884

Both questions recommended the port ('D drops a module that is mostly exact', 'C stops the common call'; 'C would be consistent too') without counting who calls them; the author's rule (evidence first, exclude when unused) came a day later. Counted: in the manifest's 115 compiled modules, the venv's 993 files and targets/vendor, every marshal call handles a code object (which stops by name under the same decision) or a profile (E-03), and zipimporter is made only inside zipimport.py. Nothing in the closure imports either. They are two of the gate's work items. Question 33 did not offer the form the manifest uses for subprocess: the import succeeds, the calls stop by name.

Evidence: review/s2-coherence-and-plan/usage_count.out (tools/usage_count.py; text search, nothing run). `marshal.dumps/dump/loads/load(`: manifest's compiled modules 0; rest of Lib without tests 12 = importlib/_bootstrap_external.py 3, zipimport.py 1, pkgutil.py 1, modulefinder.py 1 (code objects), pstats.py 3, profile.py 1, profiling/ 2 (profilers); venv 2 = _pytest/assertion/rewrite.py:309 `fp.write(marshal.dumps(co))`, :381 `co = marshal.load(fp)`; targets/vendor 0. `zipimporter(`: 2, both in zipimport.py; other mentions pkgutil.py:176-207 (outside the manifest), comments in linecache.py:213 and importlib/resources/_common.py:32, pydoc.py:550. probe1 rows marshal, zipimport: CPython `[1, 'a']` and `zipimporter`; compiled status 70, `bella: not implemented: importing 'marshal' (the standard library: step 3b)`, `importing 'zipimport' (a frozen module of CPython's the build does not compile: step 3b)`. TODO.md:123 lists both under the gate's to-do. Estimates in the questions as put (session transcript, not in the repository): about a day and about half a day. Not gathered: public code; marshal on plain data exists in the wild.

Probe: probe1: rows marshal, zipimport

Suggested: Put 33 and 34 to the author again with the count before the ports are written: marshal as an import that succeeds with calls that stop by name (or [P2+]), zipimport under E-04 or as the stub; D-31 and its lint rule wait for a program that needs them.

> Verifier: **confirmed** (low). The counts reproduce: no manifest module, no venv package (but _pytest's code-object cache) and no vendored target uses marshal or zipimporter beyond importlib, profilers and code objects, and both modules now stop by name (exit 70) in compiled form. No usage count is recorded for Q33/Q34, and they predate the author's evidence rule (Q46). But the claim is overstated: Q34 option B (a stub whose every call stops) and Q33 option C and D were offered, and the questions state that nothing in the closure uses them. They are author decisions among stated options, and both modules sit in the manifest ... Cover: Not covered as a count. Decided by the author: DECISIONS.md:1892 "The options were A ... B ... C (`dumps` at version 3 and above stopping by name) and D (`marshal` excluded). The author's words: "A""; :1894 "The options were A ... B (a stub whose every call stops) and C (`zipimport` added to E-04).. ...

### F48-s2-coherence-and-plan-3 (RL-1096): Question 40's recommendation gave '1c's socket needs it' as a reason; the manifest says socket is an import-only shim, and the spec now lists recv_into as [P1] beside a [P2+] socket

*inconsistency, reported as medium*; where: docs/DECISIONS.md:1914; TODO.md:800-805 against TODO.md:121; docs/dialect-spec.md:119 against :146; manifest.toml:109; closure.lock.json (socket)

The question as put said 'socket, which 1c needs, uses writable views' and 'B ... 1c's socket needs it'; DECISIONS and TODO then ordered the memoryview step 'before the 1c ports that need it (socket)' and listed socket.recv_into and recvfrom_into as consumers to do. In phase 1 socket is a shim whose import succeeds and nothing more, reached only lazily from uuid. Spec row 119 (v0.36) names recv_into as [P1] while row 146 keeps socket [P2+]; TODO:800 contradicts TODO:121. None of the manifest's 115 compiled modules writes through a view on Linux. The decision can stand on the author's own reason; its place in the queue and the row's words cannot.

Evidence: manifest.toml:109 `socket = "import succeeds for logging.handlers type hints; sockets are [P2+]"`. closure.lock.json: socket status `shim`, reached_by `uuid:lazy:595`, no edges. TODO.md:121 'the `asyncio` and `socket` shims (the manifest: the import succeeds, the rest is [P2+])'; TODO.md:801 'Before the 1c ports that need it (socket).' spec:119 'wherever CPython writes into a buffer (`readinto`, `recv_into`, `pack_into`, `os.readv` and the like)'; spec:146 'Network | `socket`, `ssl`, ... | [P2+]'. usage_count.out: `.recv_into(`/`.recvfrom_into(` in Lib only in socket.py 1, ssl.py 2, asyncio 8; `memoryview(` in manifest modules 10 times: base64 3 and urllib/parse 2 copy out, hashlib.py:252-254 gives readinto the bytearray, pathlib:994 writes a view out, re/_compiler:407 is replaced (manifest.toml:129), shutil.py:237 is reached only by `elif _WINDOWS and file_size > 0:` (340). probe1 row socket: compiled `bella: not implemented: importing 'socket' (the standard library: step 3b)`. probe2: `import logging.handlers` compiled gives `ModuleNotFoundError: No module named 'logging.handlers'`, status 1 (D-20: outside the manifest), so the shim's stated reason is stale too.

Probe: probe1: row socket; probe2: rows handlers, control

Suggested: Row 119: drop recv_into or point to the socket's row. TODO:800: drop '(socket)' and the socket consumers; queue the step after the gate, or earlier on the author's word alone. Ask whether logging.handlers is meant to be outside phase 1.

> Verifier: **refuted** (medium). The core facts hold: socket is a shim (lock: status shim, reached_by uuid:lazy:595, no edges); spec row 119 names recv_into [P1] while row 146 keeps socket [P2+]; TODO:121 and TODO:801 disagree. Refuted on two quotations and one count. (1) 'socket, which 1c needs, uses writable views' and 'B ... 1c's socket needs it' appear nowhere in the repo (grep across md/toml/txt). DECISIONS:1914 says 'the 1c ports that need it (TODO)', without '(socket)', which is TODO:801's wording. (2) 'manifest's 115 compiled modules': manifest [phase1].compiled lists 121 names; the lock has 121 compiled, 119 with a p ...

### F48-s2-coherence-and-plan-4 (RL-1097): The queue has no order; most of the answered and unbuilt work is not gate work, and 1c's gate is near

*follow-through, reported as medium*; where: TODO.md:734 (the section the steps sit in), 117-126 (the gate), 747-919; docs/design.md:840

The eight answered, unbuilt steps (Questions 29, 30, 33, 34, 35, 37's folding, 38, 40) are bullets under 'Open from reviews S22 and A22 (2026-11-19)' in no sequence; the only ordering words are the wrong ones of TODO:801. Each does have a case named first (38 only a test row). By the questions' own estimates about six to eight days of them are off the gate's list (30: 2-3 days and a review of every call; 40: 1-2; 29, 35, 37: a day each) against three to six on it. The gate is close: every [P1] case is in the compiled baseline, and five rows written for its missing cases agree today. Nothing else in the queue closes phase 1.

Evidence: grep of TODO.md for 'before the 1c', 'after 1c', 'next after', 'queue': only line 801. conformance/evalc-baseline.txt has 236 of 239 cases; outside it C-7-04 (`# status: P2+`), X-4-01, X-4-02. probe1: rows uuid, secrets, tstring SAME; unittest_runner (TestLoader, TextTestRunner at verbosity 2 over a pass, failure, error, skip, expected failure, subtest) and logging_more ('{' and '$' formatters, a filter, NullHandler, LoggerAdapter, exc_info, FileHandler) DIFF only in the traceback's source lines (`    raise KeyError("k")`, `    ~~~~^^^^`), which D-06 covers. What blocks the gate (TODO.md:121-126): the asyncio and socket import-only shims (probe1 rows asyncio, socket stop at the import), marshal and zipimport, 22 names of sys, the cases, the sweep as a test, a full run. Estimates are the questions' as put (session transcript; DECISIONS records none); Question 36's '2-3 days' was committed seven hours after its answer, so they are weights.

Probe: probe1: rows uuid, secrets, tstring, unittest_runner, logging_more, asyncio, socket

Suggested: One ordered list in TODO, the gate's items first, then memoryview, then the call steps, sizes and folding last. Put the 22 names of sys as one question with a count each.

### F48-s2-coherence-and-plan-5 (RL-1098): The stack analysis is filed under Later while Questions 30, 29 and 38, which rewrite what it is to measure, are queued now

*follow-through, reported as medium*; where: TODO.md:666-677 (Later) against TODO.md:910-919 (Question 30), 762-772 (Question 29), 747-752 (Question 38)

The author flagged the stack twice ('something off in the general design'). TODO puts the analysis under Later and names its subject: where a frame's bytes go, 'the guards, the argument arrays, what the lowering keeps alive across a call'. Question 30's step changes exactly that (temporaries moved into invoke, an Args protocol of owned arguments, every example regenerated, a codex review of every call), Question 29 changes call_ex's arguments, Question 38 the depth counter. Nothing links them. If the analysis then moves frames or argument arrays, the call protocol is rewritten and reviewed twice.

Evidence: TODO.md:670-672: 'To analyse: where the bytes of a frame go (the guards, the argument arrays, what the lowering keeps alive across a call), whether deep recursion should have frames off the native stack, and whether the preludes' walks should be loops or leaner native code; then revise the approach.' TODO.md:673-677: the threads milestone 'decides the threads' size from this analysis, not before it'. TODO.md:914-919: 'the compiler marks an argument that is a temporary of the call and moves it into `invoke`; the `Args` protocol says which arguments are owned; ... the caller lets go only of what was not taken ... `pipeline/examples/out` regenerated, a codex review after it (every call).' TODO.md:767: '`call_ex` (`runtime/src/call.cpp`) passes the tuple's own items, not a copy, and notes the tuple for the call (saved and restored around it)'. No link either way: lines 910-919 and 762-772 do not contain the word stack, and lines 666-677 name neither Question 29 or 30 nor RL-626 or RL-695 (grep counts 0, 0, 0).

Suggested: Do the measuring half of the analysis (where the about 690 bytes of a compiled call go) before Question 30's step and design the Args protocol with its result; Questions 29 and 30 as one step.

### F48-s2-coherence-and-plan-6 (RL-1099): RL-955's sweep is queued before RL-954's question, though one answer to it (refuse such a name, as attribute names already are) makes the sweep and D-33's call counts unnecessary

*follow-through, reported as medium*; where: TODO.md:857-867; runtime/src/call.cpp:686-688; docs/dialect-spec.md:245 (D-33); review-log RL-954, RL-955

TODO says 'First RL-955: find each difference of the prelude's text, make it CPython's, and keep a sweep ... Then put RL-954 to the author', one of whose options is to refuse an import by a name whose type is a str subclass with methods of its own. The runtime already stops exactly that object as an attribute name, so the same exotic input is stopped in one place and modelled call by call in another. If the author takes the refusal, RL-955's work and the part of D-33 about how often __hash__ and __eq__ run hold nothing reachable. Nine of the last 35 findings need such an object. Locally no such class is used as a module name, and importlib.import_module hands on an exact str.

Evidence: call.cpp:686-688: `if (!is_exact_str(v) && (type_lookup(type_of(v), intern("__hash__")) != type_lookup(types().str, intern("__hash__")) || ...__eq__...)) throw NotImplemented("an attribute name of a subclass of str with a __hash__ or __eq__ of its own (CPython has it; the runtime does not yet)");`. str_subclasses.out (tools/str_subclasses.py, AST over Lib without tests, the venv, targets/vendor): 9 classes with a direct base str, 2 define __hash__, __eq__ or __add__: importlib/metadata/_text.py FoldedCase and tomlkit/items.py String; neither is a module name. D-33's own words: '`importlib.import_module` passes an exact str', so the object arrives only through `__import__` and `importlib.__import__`. Review log rows whose trigger is a str subclass's object: RL-931, 939, 942, 943, 950, 954 by their own words, and RL-947, 953, 955 about the same name's methods.

Suggested: Put RL-954's question first, as one decision for the class (a str subclass with methods of its own wherever the runtime takes a name), with the count, as at Question 46; do RL-955 only if the answer keeps such names.

### F48-s2-coherence-and-plan-7 (RL-1100): The reviews are converging on the steps and not on the backlog: the count per review is the reviewer's budget, and what it finds is older and more exotic each time

*other, reported as medium*; where: docs/reviews/review-log.md:63-67 and rows RL-923 to RL-957; the reports of A43 to A46

Findings per review: A43 14 (7 high, 7 medium by the reviewer), A44 6 (2 high, 4 medium), A45 5 and A46 5 (no severities), W47 4. Findings of the step itself fall (about 11, 6, 2, 1) while findings older than the reviewed range rise (1, 0, 3, 4): a five-minute low-effort run reports about five things wherever it points. Of the 35, 30 need a finaliser or write during the exit (13), a str subclass's object as a name (9), importlib's private functions (8), or a metaclass hook or gc.DEBUG_SAVEALL (5); the other five are RL-924, 933, 944, 946, 951. Of the 14 findings of A45, A46 and W47, six were fixed, four closed by four questions, three are open.

Evidence: rl_stats.out (tools/rl_stats.py over the log). Severities from the reports' headings ('## A43-03 · High ·' ...; A45 and A46 have none; the log has no severity column). 'Older' by the rows' own words: RL-943 'Of `module_init_m`, older than the range'; RL-946, 947, 948, 950, 951 'Older than the range'; RL-949 'Before the step the entry was missing altogether'; RL-945 and RL-952 'Of the step'. A46's report header: 'The run took five minutes (78,618 tokens)'. git show --stat: the step 0c25f5e 404 insertions; A46's fixes 477dddc 2,794 insertions, of them runtime/src/cpython_names.inc 2,216 (RL-951, the order of a native module's names, with a sort at each such import); Question 47's commit 02b6d07 558. Groups: exit RL-923, 925-932, 934-936, 942; str subclass RL-931, 939, 942, 943, 947, 950, 953, 954, 955; importlib RL-926, 948, 949, 950, 952, 953, 956, 957; metaclass or SAVEALL RL-937, 938, 940, 941, 945. RL-944 and 946 were excluded on the author's decisions; RL-933 and 951 a plain program can see.

Suggested: At each verdict record the kind: of the step; older and plainly visible; or needing an exotic object. Fix the first two, decide the third by class with a count. Close a step when its review finds nothing of the step. Name the decided classes in the reviewer's prompt.

### F48-s2-coherence-and-plan-8 (RL-1101): Records that say open where the work is done, and one open row no TODO item carries

*follow-through, reported as low*; where: docs/reviews/review-log.md:1080 (RL-668), 1054 (RL-642), 550 (RL-277), 1038 (RL-626), 1107 (RL-695); TODO.md:903, 789, 932, 885, 786; manifest.toml:109

RL-668 is still 'Confirmed ... Open, a step of its own' in the log and 'Open from review A31' in TODO, though Question 43's step did it (C-8-22 holds the tracebacks through importlib.import_module and is in the compiled baseline). RL-642 is 'Open' while its own text says decided and done on 2026-11-22. TODO lists RL-702 and RL-583 as open; the log has both Fixed 2026-11-23. RL-277 is Open and TODO names it nowhere. TODO:885 repeats Questions 33 and 34's items with superseded figures (50 names of sys against 22). RL-626 and RL-695 kept their old status words where RL-623 and RL-639 were updated.

Evidence: open_rows.out (tools/open_rows.py: every log row whose status is not closed, and how often TODO names its id). review-log.md:1080 'Confirmed | Open, a step of its own: the import system's frames are Python frames in CPython'; TODO.md:903 '**Open from review A31** (2026-11-21, night): importlib's frames in a traceback (RL-668)'; conformance/cases/C-8-22_the_import_systems_frames.py:11 '`importlib.import_module`, which calls the import system without the statement, keeps them', and line 222 of conformance/evalc-baseline.txt (not run again by me). review-log.md:1054 status 'Open', text '... Decided by the author on 2026-11-22 (Question 28: B) and done the same day'. TODO.md:789 '**Open from review A32, with the buffer step (RL-702):**' against the log's 'Fixed 2026-11-23 with its class' and TODO.md:798 'RL-702 and RL-583, done 2026-11-23'. review-log.md:550 RL-277 'Confirmed | Open | Known gap (`docs/emitter.md` section 5): the runtime has no SyntaxError class yet'; `grep -c RL-277 TODO.md` is 0. RL-436, the other Open row without its number in TODO, is carried at TODO.md:601.

Suggested: Close RL-668 and RL-642 in the log, strike TODO:903, 789, the RL-583 half of 932, and 885; give RL-277 an item or a verdict; update RL-626's and RL-695's status words.

> Verifier: **refuted** (low). Most record facts check out: RL-668 Open (Confirmed) and TODO:903; RL-642 status Open with the 'Decided ... 2026-11-22 ... done the same day' text; RL-626 and RL-695 keep status Open/Confirmed though decided; RL-702 and RL-583 Fixed 2026-11-23 vs TODO:789/932; RL-277 has no TODO mention; RL-436 is carried at TODO:601. Refuted on a count: three Open rows have no TODO id (RL-277, RL-436 and RL-642), not 'the other' one. 'Superseded' (50 vs 22 names of sys) is unclear: they are different measures.

Minor, one line each, not verified:

- Assessment, revisit before it is built: Question 38's two entries (finding 1); marshal and zipimport, to be put again with the count (finding 2); the recv_into words and the place of the memoryview step (finding 3); Question 29's keepers other than the cache's key; the scope of Question 37's folding.
- Assessment, reorder: 1c's gate first (two import-only shims, the decided form of marshal and zipimport, the 22 names of sys as one batched question, the cases, the sweep as a test, the full run); then memoryview for its own sake; the measuring half of the stack analysis before Questions 30 and 29 as one step, Question 38 with them or as words; RL-954's question before RL-955's sweep; sizes and folding last.
- Assessment, stop doing: recommending the exact build before counting use (of Questions 33 to 48 the recommendation was to build or port in eight: 33, 34, 35, 36, 38, 40, 43, 46, as in 29 and 30 of the same round; use was first counted at Question 46, at the author's request; the author overrode a recommendation three times, 39 and 46 toward promising less and 37 toward the folding); fixing older exotic-trigger findings the day they arrive; writing the spec and register in the present tense for queued behaviour; one register entry per instance for the import system's internals.
- Question 29 against D-03 as widened twenty minutes later (DECISIONS:1900 against 1906, spec:218): of the rows that differ in Question 29's measurement seven are identity only (`.args is t` and its kin, itemgetter's reduce, partial) and three are the cache's __hash__ counts; only the three are outside D-03 now (probe1 row starred_args: `True True` against `False True`). TODO:762 still lists every keeper as the step.
- Question 37's folding grew between the question and TODO: put as 'a compiler pass that mirrors fold_tuple_of_constants, about a day', recommended for Later; TODO:776-783 has four functions of flowgraph.c and four limits. It changes identity only, which the same decision declares free (probe1 row pair: True against False).
- The spec is ahead of the runtime with no mark: probe1 rows marshal, zipimport, mv_hex, mv_slice_store, mv_readinto, sizeof_method, basicsize stop with status 70 and getsizeof prints 'a longer list is larger: False', for what v0.30 to v0.37 call [P1] or decided. All queued in TODO, so not a defect; D-17's sentence (finding 1) is the one that states behaviour.
- hashlib.file_digest over a BytesIO stops compiled: `bella: not implemented: BytesIO.getbuffer (a memoryview: the buffer protocol, [P2+])` (probe1 row file_digest; CPython prints the digest). hashlib is a manifest module; Question 40's list of consumers does not name getbuffer.
- D-33's last clause (two code objects without the local `lock`) and Question 48's D-34 (25 more) register the same kind of difference; one sentence under E-02 or E-04 would cover both and the next one found.
- Question 39 relaxes what the author decided for RL-514 on 2026-11-14 ('exact, with the collector'): the entry says so and keeps the order as a design test, so nothing is silent; H4 (707 lines) and A43's fixes (998) now hold a choice, not a promise.
- docs/DECISIONS.md records 'Recommended was' for six of the sixteen questions (39, 43, 44, 45, 46, 47) and an estimate for none; the other recommendations and all estimates exist only in the session's transcript.
- Question 32's gate names 'logging's handlers and formatters' (TODO:125): logging.handlers and logging.config are outside the manifest (closure.lock.json has only `logging`; probe2), so the cases can cover only the handlers of logging/__init__.py.

Covered: Read: docs/DECISIONS.md lines 1882 to 1960 (every entry of 2026-11-24 and 25); TODO.md lines 1 to 330 and 520 to 986 in full, 330 to 520 (history of the C++ leg) skimmed; the review log's table of reviews and rows RL-923 to RL-957 in full, with the older rows they point to (RL-277, 436, 583, 626, 639, 642, 668, 695, 702); the reports of A43 to A46 (headers, headings, coverage notes) and W47's outline; docs/dialect-spec.md sections 2, 4, 11 in full and the named rows of 7 and 8; docs/deviations.toml D-17 and D-31 to D-33; docs/targets.md sections 1 and 2; docs/design.md:840; manifest.toml's core, shim and adaptation tables; closure.lock.json and targets/closure-summary.json by script. The sixteen questions as they were put, from the working session's transcript, for what was recommended and estimated (DECISIONS records that for six only). Two builds: probe1 (35 rows on both sides: sixteen shapes of a recursion through a class's call; the state today of what spec v0.30 to v0.37 describe; five rows for the gate's missing cases) and probe2 (2 rows: import logging.handlers); full outputs in probe1/both.out and probe2/both.out. CPython alone: the same shapes; CPython's Python/specialize.c and Python/bytecodes.c at v3.15.2, fetched into cpython-src/ and read. Counts of use by text and AST search over CPython's Lib (tests apart), the venv's 993 files and targets/vendor (usage_count.out, str_subclasses.out). The review log parsed for counts, statuses and each open row's presence in TODO (rl_stats.out, open_rows.out). On the five points asked: (1) no two decisions promise a program contradictory things; the contradictions found are spec row 119 against 146 and TODO:800 against 121 (finding 3), with the overlaps listed as minor; (2) findings 1, 2 and the stop-doing line; (3) findings 4 and 5: each step has a case named first, none has a place in an order; (4) finding 7; (5) finding 8: RL-277 is the only Open row TODO does not carry.

Not covered: REPORT.md does not exist: the harness refused the file (Write returned 'Subagents should return findings as text, not write report files'), and I did not work around the refusal. The full account is therefore in these fields; the evidence files are in review/s2-coherence-and-plan/ (probe1/, probe2/, tools/, cpython-src/, usage_count.out, str_subclasses.out, rl_stats.out, open_rows.out). Not examined: each question on its own merits beyond Question 38's measurement, the code built on 2026-11-24 and 25, and whether any test can fail (other reviewers' tasks). No public code search and no package downloads: all counts of use are local, and the thirty packages of Question 46's search are no longer on the machine. The cost figures of the built steps (Questions 36 and 43) were not measured again. No compiled frame was measured for the stack analysis. TODO.md lines 330 to 520 were skimmed, not read; a search of the whole file for ordering words found only the places named. What the asyncio and socket import-only shims and the 22 names of sys each take was not tried. Reviews before A43 were counted from the log's table, not read. RL-668 being done rests on C-8-22's text and its place in the compiled baseline; I did not run it.
