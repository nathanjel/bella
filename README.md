# Bella

Bella compiles Python to readable C++26 through intent-level IR passes, keeping CPython 3.14's
semantics exactly (arbitrary-precision `int`, insertion-ordered `dict`, Python's attribute
lookup, finaliser timing) and replacing the interpreter with a native runtime that has no GIL.
Target toolchain: the newest GCC at `-std=c++26`, Linux x86-64 and aarch64. Licence: MIT.

**Status (2026-10-31): phase 0, pre-compiler.** The architecture has been through three external
review rounds (`docs/reviews/`); this repository holds the executable Gate-0 artefacts the
third review asked for. Nothing here compiles a real program yet.

## What is here

| Path | What | State |
| --- | --- | --- |
| `docs/` | The three design documents (Markdown exports), decisions, the deviation register as data, the reviews | current |
| `tools/closure.py` + `manifest.toml` | Phase-1 standard-library closure: mechanically closed, with per-API scoping and declared omissions | closed on CPython 3.13; **must be rerun on 3.14.8** |
| `refmodel/` | Executable reference model of the object model (promoted fields, `__dict__` exposure, descriptors, inline caches) tested against CPython | agrees on ~40k random ops per seed; two design findings recorded |
| `conformance/` | Harness and 24 corpus cases, one per demonstrated behaviour from the reviews | recorded on 3.13 (non-authoritative) |
| `pipeline/` | L1 (PyCore) grammar, desugaring passes with `PassSpec` records, `eval1`, pass manager, toy C++ emitter, end-to-end slice | 3 integer programs agree CPython == eval1 == C++; BigInt is XFAIL |
| `runtime/include/bella/int.hpp` | Exact `int` fast paths (63-bit immediates, floor semantics), differentially tested with UBSan | promotion to BigInt not implemented |
| `runtime/probes/` | 20 C++23/26 feature probes; `make probes` reports what the toolchain supports | run on GCC 16 in Docker |
| `validation/` | Range-certificate checkers (interval arithmetic; Z3); clause C-9-1 | passing |
| `TODO.md` | Gate 0, first increment: five tasks with acceptance criteria | — |

## Quick start

```bash
# pinned toolchain (GCC 16, CPython 3.14.8, locked deps)
docker build -t bella .
docker run --rm bella            # = make check

# on a developer machine with any recent g++ and Python >= 3.13 (non-authoritative runs)
make test                        # pytest if installed, then the stdlib-only model self-check
python3 tools/closure.py --allow-unpinned
python3 conformance/harness.py record --allow-unpinned
make slice CXXSTD=c++23          # the toy end-to-end slice
make int-test CXXSTD=c++23
```

## How the pieces fit

```
Python source ──parse──▶ L0 (ast) ──desugar passes──▶ L1 PyCore ──▶ eval1 (reference semantics)
                                                          │
                                                          └──▶ toy C++ emitter ──▶ g++ ──▶ binary
                 CPython 3.14.8 ◀── conformance harness ──▶ compiled program
                 refmodel (object model) ◀── random programs ──▶ CPython
```

* The **dialect specification** says what correct means; the harness compares a compiled program
  with CPython on exactly the observables it lists, with the masks the deviation register allows.
* The **reference model** is the object model written as a Python program that must be
  indistinguishable from CPython; the real `object.hpp` is written from it.
* The **pass framework** refuses passes without stated obligations; every lowering carries a
  proof status (tested → validated → proved).
* The **closure tool** keeps the phase-1 library promise honest: every module the dialect
  promises has every import it executes accounted for.

## Reading order

`docs/dialect-spec.md` (what), `docs/design.md` (how), `docs/DECISIONS.md` (what was decided),
`TODO.md` (what is next), then `CLAUDE.md` (how to work in this repository).
