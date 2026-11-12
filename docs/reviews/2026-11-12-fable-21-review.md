Claude Fable 5.2, as a review agent of the working session, 2026-11-12, asked by the author to review the last commits made
under Claude Opus 5.5. The report's own text; its findings, which it gave as a JSON list, are set out here as a numbered
list, their wording unchanged. Tag F21 in the review log. Its range is `6519433..3234866` (three commits: 49d248c, 203814f,
3234866). It read and probed only (a check chain was running on the host): CPython evidence is from the pinned interpreter and
the pin's C source, and the Bella side of every finding was reproduced afterwards by the session, compiled (review log, F21).

---

**Coverage.** I reviewed the three commits in range in full: 49d248c (C-7-80 cmath), 203814f (C-7-81 unicodedata) and 3234866 (C-6-21). Of e062987 and 6519433 I read only the functions the range touches again (`encode_utf_wide`, `decode_fallback`, `i_codecs_call`) and skimmed the C-3-68 diff once; no findings come from them.

**Constraints.** Read and probe only: no Bella build, no `make`, no pytest, nothing edited under the repo. CPython evidence comes from `.venv/bin/python -I` (3.15.2) and the pin's C source. Every Bella-side claim is from reading the code, so the "differs from CPython" findings are PLAUSIBLE on the Bella side until a compiled run. Line numbers are at commit 3234866.

**What held up.** `unicodedata.cpp` matches `Modules/unicodedata.c` (DAWG and grapheme sections are textually identical under `diff -w`). The unicodedata prelude's argument handling gave 0 differences against CPython's module over about 4,600 calls, run under CPython with the C algorithms stubbed. `cmath.py` matches `cmathmodule.c`'s errno handling function by function.

## Findings

1. **`runtime/src/slots.cpp:374`** — PLAUSIBLE, pre-existing in the touched `init_slots()`: the diff gives bytes/bytearray their own `__len__`/`__iter__`/`__contains__`/`__getitem__`, but `bytes.__hash__` and `frozenset.__hash__` are still the generic `own_hash`, which re-dispatches through `hash_of()` to a subclass's override.

   Scenario: `class H(bytes): def __hash__(self): return super().__hash__()`. CPython 3.15.2: `hash(H(b'abc')) == hash(b'abc')` is True (probed; same for a frozenset subclass). Bella: `own_hash` -> `hash_of` -> `full_hash` breaks out at core.cpp:445 because the class has its own `__hash__` -> `call_special(v, '__hash__')` -> `H.__hash__` -> `super().__hash__()` -> `own_hash` again: unbounded recursion. `bytes.__hash__(Odd(b'abc'))` with C-3-64's `Odd` would return 5, not the bytes hash. RL-310 fixed this pattern for int. Deeper fix: `bytes_hash_slot` and `frozenset_hash_slot` that compute the base hash, as `tuple_hash_slot` and `str_hash_slot` do.

2. **`runtime/prelude/_codecs.py:530`** — `namereplace_errors` returns `end` as the new position; `PyCodec_NameReplaceErrors` returns its loop index `imax`, which is `start` when the clamped end is not past start (CPython side CONFIRMED).

   Scenario: `codecs.namereplace_errors(UnicodeEncodeError('ascii', 'a\xe9c', 2, 1, 'why'))`: CPython gives `('', 2)`, and also `('', 2)` for (start, end) = (2, 0) and (3, 1). The prelude's `_params` yields start=2, end=1, the loop does not run, and it returns `('', 1)`. backslashreplace and xmlcharrefreplace do return end in CPython, so the port copied the wrong sibling. Fix: return i.

3. **`runtime/src/bytes.cpp:690`** — namereplace reads the name tables directly, so the first use does not import unicodedata; CPython's handler fetches the name C API through `PyCapsule_Import`, which leaves `'unicodedata'` in `sys.modules` (CPython side CONFIRMED).

   Scenario: `import sys; '\xe9'.encode('ascii', 'namereplace'); print('unicodedata' in sys.modules)` prints True on CPython 3.15.2 (False before the call; the same after `codecs.namereplace_errors` on a UnicodeEncodeError). Bella's `encode_fallback` -> `unicode_name()` and the prelude's `_codecs_call('charname')` never touch the import system, so it would print False. Decode-side TypeError paths import nothing in CPython either, so only the encode path differs.

4. **`runtime/src/unicodedata.cpp:1605`** — PLAUSIBLE hardening: the 'substring' primitive is labelled `PyUnicode_Substring` but omits its clamps, and 'next_break' indexes the state tuple and the string unchecked; both trust prelude slots a program can write.

   Scenario: `seg = next(unicodedata.iter_graphemes('ab')); seg._c_end = 10**9; str(seg)` loops `s->at(i)` far past the string's units. `it._b_state = ()` (or an int) makes `next(it)` index `st[0..6]` of an empty vector, or cast a small int to `Tuple*`. In CPython these attributes do not exist (AttributeError), and `PyUnicode_Substring` clamps end, raises IndexError for negatives and returns '' for start >= length. Unreachable through the public API; reachable because prelude slots are ordinary slot members. Fix: port the three clamps and check the state's kind and size.

5. **`runtime/src/unicodedata.cpp:1563`** — PLAUSIBLE, low: `text()` answers category, bidirectional, east_asian_width, block and the two break properties with interned strings, where the C makes a new str each call (`PyUnicode_FromString`).

   Scenario: `unicodedata.category('a') is unicodedata.category('a')` is False on CPython 3.15.2 (probed; also False for `east_asian_width('a')` vs `('b')`, both 'Na'). Bella would give True. C-7-81 already treats identity as an observable for `normalize()`. One-character answers are cached singletons in CPython, so only the multi-character ones differ.

6. **`docs/DECISIONS.md:1126`** — The C-6-21 entry says `test_the_unicode_database_in_the_builtins` compares the words of every new path, but namereplace is in no word-comparing test, and C-7-29's handler table was not extended to it.

   Scenario: `DATABASE_IN_BUILTINS` (pipeline/tests/test_str_methods.py:73) has no namereplace row. C-7-29 line 107 runs ignore/replace/xmlcharrefreplace/backslashreplace/surrogate* over enc/dec/translate errors and odd ranges, but not `namereplace_errors`. C-6-21 prints only exception classes for two in-range calls. The wrong position above (and any wrong TypeError wording) passes every leg.

7. **`runtime/src/unicodedata.cpp:1571`** — Efficiency (the per-call cost TODO.md already lists as left): every unicodedata call walks a chain of up to ~25 `std::string` comparisons in `dispatch()`, and a per-character property makes three primitive calls.

   Scenario: `unicodedata.category(ch)` per character runs `_one`, then `_character`, which calls `_ucd_call('length')` (one failed compare short of the whole chain) and `ord()`, then `_ucd_call('category')`. Each grapheme step packs and unpacks a 7-int tuple (unicodedata.py:428). DECISIONS records the sweep at 11m38s against CPython's 26s. Cheaper: one Builtin per operation as other modules do, a single 'char' primitive, and the break state kept in a native field.

8. **`runtime/src/unicode.cpp:71`** — Efficiency: `decimal_and_space_to_ascii` returns `std::string` by value, so the ASCII case now copies the text on every `int(str)`; `int_from_text` used to take `s->text` by reference.

   Scenario: types.cpp:1060: `int('12345678901234567890')` allocates and copies before parsing (CSV- and JSON-style loops over `int()`); float and complex gain a second copy on top of `without_underscores`'. Cheaper: branch at the call site (`s->ascii ? s->text : transformed buffer`), or return `const std::string&` with an out-buffer.

9. **`runtime/src/unicodedata.cpp:97`** — Reuse: the runtime now carries two copies of str's type properties, CPython's own type records (`unicodetype_db.inc`, read here only for decimal/digit/numeric/XID) and the range tables in `unicode_tables.inc` behind unicode.cpp's predicates.

   Scenario: `is_identifier` (unicode.cpp:92) and `str.isidentifier` binary-search `UNICODE_XID_START`, while `unicodedata.isxidstart` reads `gettyperecord(ch)->flags`; `decimal_and_space_to_ascii` mixes `unicode_is_space` (ranges) with `unicode_to_decimal` (records). Two generators (tools/unicode_tables.py, tools/unicodedata_source.py) must stay in step at a pin move, and about 430 KB of duplicate table source ships in every binary. The records' flag masks and tables could answer every predicate in unicode.cpp in O(1).

10. **`runtime/prelude/cmath.py:548`** — Reuse: cmath.py and unicodedata.py each re-type the METH_O and `_PyArg_CheckPositional` helpers (`_one`, `_positional`, `_fastcall`) that about twenty other preludes already carry; cmath.py's are math.py's lines 74-87 with the module name changed.

    Scenario: cmath.py:548-562 and unicodedata.py:42-56 are further copies of the same message text; cmath.py also re-defines `_isnan`/`_isinf`/`_copysign`/`_log1p` next to math.py's. A wording fix has to be made in every file. `_unpack_keywords` is already installed 'in every such file' by `fill_in_python`; the other two calling conventions could be shared the same way.

11. **`runtime/src/slots.cpp:381`** — Simplification: after the new bytes/bytearray loop, the `t.bytes` and `t.bytearray` entries in the generic `own_len`/`own_iter`/`own_contains`/`own_getitem` loops are dead, because `slot()` returns early when the name is already set.

    Scenario: Lines 381-386 still list both types; a reader takes `own_len` to be `bytes.__len__`, and reordering the loops would silently bring back the defect C-3-64's new rows cover. Drop the two types from those lists.

12. **`runtime/src/unicodedata.cpp:1547`** — Reuse: `capsule_class()` re-implements `no_instances_yet("PyCapsule")` from imports.cpp, which `_types.CapsuleType` already uses.

    Scenario: Two places create the PyCapsule type by the same two lines (`builtin_class`, then `builtin_type` if cls is null). A change to how an instance-less C type is made (flags, `__module__`) has to be made in both, or `types.CapsuleType` and `type(unicodedata._ucnhash_CAPI)` differ by import order. Export `no_instances_yet` and call it.

13. **`runtime/prelude/_codecs.py:8`** — Stale module docstring: it still lists 'the namereplace handler (it needs the Unicode database)' under 'Not written', though this range implements it at line 518.

    Scenario: The next reader, or a grep for remaining stops, takes namereplace for a refusal. e062987 edited this same sentence for UTF-16/32; 3234866 did not.

14. **`pipeline/tests/test_str_methods.py:109`** — Conventions (bella/CLAUDE.md: 'Without pytest, every test module runs directly'): the direct-run blocks do not call the tests this range adds.

    Scenario: `python3 -m pipeline.tests.test_str_methods` runs only PROGRAMS, never `test_the_unicode_database_in_the_builtins`; the `__main__` list at test_system_modules.py:1620 has neither `test_cmath` nor `test_unicodedata`. A run without pytest reports success without exercising C-6-21, C-7-80 or C-7-81's word comparisons.

15. **`runtime/prelude/unicodedata.py:32`** — Maintainability: `unidata_version = "17.0.0"` and `_NAME_MAXLEN = 256` are hand-copied from the .inc files, and tools/unicodedata_source.py stamps 'CPython 3.15.2' / 'Unicode 17.0.0' as literals and names a SHA-256 it never checks.

    Scenario: At a pin move, `--check` passes against whatever tree is given, the header comments still say 3.15.2/17.0.0, and the prelude keeps the old version string until a compiled case fails. tools/unicode_tables.py takes the version from the pinned interpreter; this tool could read `UNIDATA_VERSION` and `NAME_MAXLEN` from the headers it copies.
