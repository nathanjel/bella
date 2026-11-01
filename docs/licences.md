# Licence register

The rule (CLAUDE.md): anything linked into a shipped artefact is MIT, BSD or ISC; tools and
test-only dependencies may differ. This register lists the components the plan would ship under
another licence, or whose source is still to be chosen. The author decided on 2026-11-01 that
work proceeds meanwhile and each entry is settled when it becomes worth it, one by one; the
decision then goes into `docs/DECISIONS.md` and the entry's status here.

Claims marked *to verify* were not checked against the licence text when the entry was written.

| Id | Component | Licence | Ships in | Status | Options and notes |
| --- | --- | --- | --- | --- | --- |
| L-01 | CPython's pure-Python standard library, compiled into the artefact (112 modules in the closure), and code ported from CPython's C sources (the dict and set table algorithms; the `_sre` engine is L-08) | PSF License 2.0 | every artefact | open | Permissive and BSD-style, but not named by the rule. Admit it by name, keeping the notice |
| L-02 | zlib, behind the mapped `zlib` module (reached by itsdangerous and `shutil`) | zlib License | artefacts that import `zlib` | open | Permissive, not named by the rule. Admit it, or map `zlib` onto miniz (MIT; *to verify*). `docs/targets.md` section 5, item 4 |
| L-03 | Unicode Character Database tables (Unicode 17.0.0, CPython 3.15.2's version), generated from the data files: case mappings and properties for the `str` methods, and the `unicodedata` module (both \[P1\]; `unicodedata` since review log D-8: names, decompositions, normalisation, properties, grapheme clusters) | Unicode License v3 | every artefact (`str` methods; `unicodedata`, which `re`, `traceback` and `urllib.parse` import) | open | Permissive, not named by the rule. Admit it with its notice. The module's C code, if ported (`Modules/unicodedata.c`, copyright CNRI), comes under CPython's licence stack, as L-01 and L-08 (*to verify*) |
| L-04 | The hash primitives behind `_md5`, `_sha1`, `_sha2`, `_sha3`, `_blake2` and `_hmac` | BearSSL (MIT) or libsodium (ISC), as spec section 7 says; or HACL\*, as CPython vendors it (MIT according to its file headers, `docs/targets.md`) | artefacts that import `hashlib` or `hmac` | open (a choice, not a conflict) | HACL\* would keep the digests bit-identical to CPython's own built-in path. `docs/targets.md` section 5, item 5 |
| L-05 | The big-integer backend of `int` | libtommath (public domain or Unlicense; *to verify*), if taken instead of own code | every artefact | open | Own code (Karatsuba above 64 limbs, Knuth's division), or admit libtommath. `TODO.md` task 4 |
| L-06 | `float` formatting and parsing with CPython's results (`repr`, `float(str)`) | CPython's `dtoa.c` is David M. Gay's code under a permissive notice (*to verify*); Ryu and Dragonbox are Apache-2.0 or Boost (*to verify*) | every artefact that uses `float` | open | Port Gay's code (as CPython does), admit an alternative, or write own. Needed when `float` enters the slice |
| L-08 | The regex engine: a C++ port of CPython's `_sre` (`Modules/_sre/`), and the compiled `re` package it serves (`re/__init__.py`, `_parser.py`, `_compiler.py`, `_constants.py`); review log D-9 | Secret Labs AB, copyright 1997-2001: "This version of the SRE library can be redistributed under CNRI's Python 1.6 license. For any other use, please contact Secret Labs AB" (`re/__init__.py` lines 6-9 and `sre.c` lines 27-30, read in 3.15.2); later changes under the PSF License 2.0 | every artefact that imports `re` (all six targets) | open | CNRI's licence is part of CPython's licence stack and allows derivative works that keep its notice (*to verify* against CPython's `LICENSE`). It is not named by the rule, and whether a port into another product is the redistribution the notice allows or "any other use" is the question to settle. Options: admit it by name with the notices, as every CPython distribution carries them; or write an engine of our own with `_sre`'s exact semantics |
| L-07 | OpenSSL, behind `_hashlib` | Apache-2.0 | — | settled 2026-11-01 | Omitted: `hashlib` and `hmac` run as in a CPython built without OpenSSL (deviation D-20) |

Named in the design and believed to comply, to confirm when each is adopted: yyjson
(MIT), libuv (MIT), xenium (MIT), BearSSL (MIT), libsodium (ISC). PCRE2 left the plan with
review log D-9. The libraries of the target programs are MIT or BSD-3 (`docs/targets.md`).
