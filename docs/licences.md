# Licence register

The rule (CLAUDE.md): anything linked into a shipped artefact is MIT, BSD or ISC; tools and
test-only dependencies may differ. This register lists the components the plan would ship under
another licence, or whose source is still to be chosen. The author decided on 2026-11-01 that
work proceeds meanwhile and each entry is settled when it becomes worth it, one by one; the
decision then goes into `docs/DECISIONS.md` and the entry's status here.

Claims marked *to verify* were not checked against the licence text when the entry was written.

| Id | Component | Licence | Ships in | Status | Options and notes |
| --- | --- | --- | --- | --- | --- |
| L-01 | CPython's pure-Python standard library, compiled into the artefact (112 modules in the closure), and code ported from CPython's C sources (the `_sre` engine, the dict and set table algorithms) | PSF License 2.0 | every artefact | open | Permissive and BSD-style, but not named by the rule. Admit it by name, keeping the notice |
| L-02 | zlib, behind the mapped `zlib` module (reached by itsdangerous and `shutil`) | zlib License | artefacts that import `zlib` | open | Permissive, not named by the rule. Admit it, or map `zlib` onto miniz (MIT; *to verify*). `docs/targets.md` section 5, item 4 |
| L-03 | Unicode Character Database tables (Unicode 17.0.0, CPython 3.15.2's version), generated from the data files: case mappings and properties for the `str` methods (\[P1\]), and later `unicodedata` (\[P2+\]) | Unicode License v3 | every artefact (`str` methods) | open | Permissive, not named by the rule. Admit it with its notice |
| L-04 | The hash primitives behind `_md5`, `_sha1`, `_sha2`, `_sha3`, `_blake2` and `_hmac` | BearSSL (MIT) or libsodium (ISC), as spec section 7 says; or HACL\*, as CPython vendors it (MIT according to its file headers, `docs/targets.md`) | artefacts that import `hashlib` or `hmac` | open (a choice, not a conflict) | HACL\* would keep the digests bit-identical to CPython's own built-in path. `docs/targets.md` section 5, item 5 |
| L-05 | The big-integer backend of `int` | libtommath (public domain or Unlicense; *to verify*), if taken instead of own code | every artefact | open | Own code (Karatsuba above 64 limbs, Knuth's division), or admit libtommath. `TODO.md` task 4 |
| L-06 | `float` formatting and parsing with CPython's results (`repr`, `float(str)`) | CPython's `dtoa.c` is David M. Gay's code under a permissive notice (*to verify*); Ryu and Dragonbox are Apache-2.0 or Boost (*to verify*) | every artefact that uses `float` | open | Port Gay's code (as CPython does), admit an alternative, or write own. Needed when `float` enters the slice |
| L-07 | OpenSSL, behind `_hashlib` | Apache-2.0 | — | settled 2026-11-01 | Omitted: `hashlib` and `hmac` run as in a CPython built without OpenSSL (deviation D-20) |

Named in the design and believed to comply, to confirm when each is adopted: PCRE2 (BSD), yyjson
(MIT), libuv (MIT), xenium (MIT), BearSSL (MIT), libsodium (ISC). The libraries of the target
programs are MIT or BSD-3 (`docs/targets.md`).
