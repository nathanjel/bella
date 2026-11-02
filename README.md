# Bella

Bella compiles Python to readable C++26 through intent-level IR passes, keeping CPython 3.15's
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
| `tools/closure.py` + `manifest.toml` | Phase-1 standard-library closure: an inventory of every module the phase-1 library imports (computed, not read), with per-API scoping and declared omissions. Closed means accounted for, not compiled | closed on CPython 3.15.2 (175 modules); CI requires the committed lock to match |
| `refmodel/` | Executable reference model of the object model (promoted fields, `__dict__` exposure, descriptors, inline caches) tested against CPython; cache soundness is checked by comparing lookup plans, so user hooks run once | agrees on ~40k random ops per seed; design findings recorded |
| `conformance/` | Harness (`record`, `verify`, `check`; fail closed; \[P2+\] and deviation cases) and 57 corpus cases plus 2 excluded constructs, from the reviews, CPython 3.15 changes and every \[P1\] row of spec sections 3 and 7 | recorded on 3.15.2 (authoritative); `make verify` reproduces all 58 expectations |
| `pipeline/` | L1 (PyCore) grammar, desugaring passes with `PassSpec` records, `eval1`, L2 with explicit lifetimes and `eval2`, the C++ emitter from L2 (`docs/emitter.md`), `pipeline/build.py`, end-to-end slice | the slice's 4 integer programs agree CPython == eval1 == compiled C++ (BigInt XFAIL); the corpus compiled is `make compiled-corpus` |
| `runtime/` | `object.hpp` (the object model, from `refmodel/`), `int.hpp` (exact `int` fast paths), `runtime.hpp` and `src/` (the runtime core), `prelude/` (built-ins written in Python, compiled into every program) | step 3a.1 of the C++ leg: functions, closures, exceptions, strings, tuples, lists and dicts; classes next |
| `runtime/probes/` | 20 C++23/26 feature probes; `make probes` reports what the toolchain supports | run on GCC 16 in Docker |
| `validation/` | Range-certificate checkers (interval arithmetic; Z3) with three verdicts: proved, refuted, unknown; clause C-9-1 | passing; only PROVED removes a check |
| `targets/` | The six target programs (CLI, data, service × easy, tricky) with vendored libraries at pinned commits, fixed inputs and recorded output; `docs/targets.md` is the comparison and recommendation | recorded on 3.15.2 (authoritative), identical under two hash seeds and under the phase-1 omissions |
| `TODO.md` | Gate 0, first increment: six tasks with acceptance criteria | — |

## Quick start

```bash
# pinned toolchain (GCC 16, CPython 3.15.2, locked deps)
docker build -t bella .
docker run --rm bella            # = make check

# on a developer machine with uv 0.13.6: the same uv-managed CPython 3.15.2 build as the image,
# so Python-side runs (closure, record, refmodel) are pinned; the image remains the reference
# for anything that depends on the C++ compiler
uv sync --extra dev
uv run make test                 # pytest, then the model self-check
uv run make closure
uv run make record
uv run make targets-check        # the six target programs against their recording
# another 3.15.x and any g++ (non-authoritative runs)
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
                 CPython 3.15.2 ◀── conformance harness ──▶ compiled program
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
`docs/reviews/review-log.md` (every review finding and its verdict), `TODO.md` (what is next),
then `CLAUDE.md` (how to work in this repository).
