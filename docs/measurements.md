# Measurements

Dated performance observations. Each says what was measured, how to repeat it, and what it does
not show. They are snapshots of the toy pipeline, not claims about Bella's finished performance.

## 2026-11-01 — Mandelbrot, integer fixed point: CPython, Nuitka, the toy emitter

**Program.** `pipeline/examples/mandelbrot.py`, scaled to 800×600 points with an iteration
limit of 256 (about 33.5 million loop iterations), with its per-row `print` removed. It uses 12
fractional bits of integer fixed point, because the toy emitter has no `float` yet. Negative
products make Python's floor division part of the hot path.

**Machine.** Intel Xeon D-2141I (8 cores, 16 threads, 2.2 GHz), Fedora 44, host
`g++ (GCC) 16.2.1`; best of 3 runs (CPython, Nuitka) or 5 runs (C++).

| Version | Best time | vs CPython |
| --- | --- | --- |
| CPython 3.15.2 (the pinned build) | 7.64 s | 1.0× |
| Nuitka 4.3.4 on the same CPython, default build | 7.70 s | 1.0× |
| Nuitka 4.3.4, `--lto=yes` | 7.63 s | 1.0× |
| Bella toy emitter, generated C++ built with `g++ -std=c++26 -O2` | 0.38 s | 20× |
| Hand-written C++ with plain `int64_t` (a reference, not Bella output) | 0.14 s | 53× |

All five printed `points inside: 121373 total escape time: 33550291`.

**Why.** Nuitka 4.3.4 (the stable release on 2026-11-01; it supports the pinned
python-build-standalone 3.15.2) compiles `escape_time` to C, but its arithmetic stays generic
operations on boxed Python integers (`BINARY_OPERATION_MULT_OBJECT_OBJECT_OBJECT`), which is what
CPython 3.15's specialising interpreter already runs. Bella uses the annotations: `int` becomes
`bella::Int`, an unboxed word whose every operation checks for overflow, so the result stays
exact. The gap to the hand-written version is the cost of those checks, which range analysis is
meant to remove where it can prove the values small (design document, sections 4 and 9).

**What it does not show.** One integer microbenchmark, where boxing dominates; Nuitka's gains
usually show in code dominated by calls and attribute access. Nuitka compiles nearly all of
Python with full CPython compatibility, while the toy pipeline handles a small integer subset
and refuses the rest. The C++ was built with the host GCC, not the pinned image's 16.2.0.

**Repeat it.**
1. Copy `pipeline/examples/mandelbrot.py`, set `width = 800`, `height = 600`, `limit = 256`, and
   replace `print(y, row)` with `pass`.
2. Bella: `lower`, `check` and `emit` it as `pipeline/slice.py` does, then build the C++ with
   `g++ -std=c++26 -O2 -I runtime/include`.
3. Nuitka: in a separate virtual environment on the pinned interpreter, `pip install nuitka`,
   then `python -m nuitka [--lto=yes] <copy>.py`, and run the `.sh` wrapper it writes (a
   python-build-standalone interpreter needs the environment it sets).
4. Time each run and compare the outputs.
