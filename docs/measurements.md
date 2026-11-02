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

## 2026-11-02 — The compile scope of the easy three (Gate 0 task 4, review log D-10)

**Question.** Should a stage compile its target's whole closure, or only what the closed world
reaches? And what does the L1 frontend lack for either choice? The closure is the inventory of
what may run. The code the target executes on its inputs is a lower bound of what must compile.

**Method.** `python tools/scope.py --target <name> [--variant="<argv>" ...]` on the pinned
CPython 3.15.2 writes `targets/scope/<name>.json`.
* The closure is the target's lock (`targets/closure/<name>.lock.json`): the program, the
  compiled standard-library modules and the shims written so far.
* A code object is one function, method, lambda, generator expression, class body or module
  body (`compile` of each source, walked through `co_consts`). Its lines are the distinct lines
  of `co_lines()`.
* Executed means `sys.monitoring` saw a PY_START, or the module was imported. The run uses
  `-X frozen_modules=off`, so that start-up modules (`os`, `codecs`, `posixpath`, ...) count
  under their real paths.
* The frontend's verdict: each executed unit (one code object's definition, or a module body
  without its definitions) is lowered alone by `pipeline/l1/frontend.py`. Only the first
  construct that stops a unit shows.
* The census lists every construct a unit uses in its own code, for executed units and for the
  whole closure. "L1 lacks it" is the frontend's verdict on a one-line sample of the construct,
  so the table cannot drift from the frontend.

**Scope.**

| Target | Closure: modules, code objects, lines | Executed (all runs) | Share |
| --- | --- | --- | --- |
| `cli_easy_slugs`, recorded run | 73, 3,607, 35,360 | 253, 6,816 lines, 35 modules | 7.0 %, 19.3 % |
| `cli_easy_slugs`, four runs (recorded, `--help`, a bad `--max-length`, `--separator _ --no-lowercase`) | | 403, 8,650 lines, 39 modules | 11.2 %, 24.5 % |
| `service_easy_tokens`, recorded run | 93, 4,221, 40,745 | 257, 4,489 lines, 49 modules | 6.1 %, 11.0 % |
| `data_easy_sales`, recorded run | 94, 4,621, 45,044 | 219, 5,126 lines, 44 modules | 4.7 %, 11.4 % |

The help and error paths add 60 % to the code objects `cli_easy_slugs` runs (`argparse`'s
formatter, `shutil.get_terminal_size`, `textwrap`). What the closed world reaches lies between
the two columns. Measuring it needs a call graph, which nobody has built.

**The frontend today.** Units of the executed code that lower to L1: 193 of 379
(`cli_easy_slugs`), 72 of 246 and 98 of 215. The first blocker of the rest is mostly `class`
(90 units), `import` and `from ... import` (43), and parameter kinds (29).

**The census of `cli_easy_slugs`.** These are the constructs its executed code uses and L1
lacks, with the number of executed units that use each:
* `class` 116, of which bases 90, decorators 19, annotations 17, keywords (`metaclass=`) 7;
  zero-argument `super()` / `__class__` 15.
* `import` 39 and `from ... import` 29, of which `*` 13, `as` 4, relative 4, `a.b` 1; lazy
  (PEP 810) 5.
* Parameters: keyword-only 33, `**kwargs` 33, `*args` 26, positional-only 17. Calls with `**`
  9 and with `*` 7.
* Several assignment targets 9, set displays 9, bytes 7, lambdas 6, starred displays 2,
  Ellipsis 2.
* Generator expressions 9, dict and set comprehensions 3, a generator function 1, `yield from`
  1 (in the `--help` path).
* `async def` 2 and a PEP 695 `type` alias 1.

The whole closure adds `match` (10 units), starred targets (5), dict unpacking in displays (5)
and a t-string (1). It also has generator functions in 94 units where the executed code has
one, and `async def` in 40 units where it has 2. The other two targets need the same list, plus
more `metaclass=` (24 units in `service_easy_tokens`, from `typing`) and `yield from` (29 in its
closure).

**Found on the way.**
* The two executed `async def` units are module bodies. `types` defines its coroutine probes
  only in the fallback of `from _types import *`, which never runs. `_collections_abc` runs
  them at import: `async def _coro(): pass; _coro = _coro(); coroutine = type(_coro)`, the
  same for an async generator, and `type(sys._getframe().f_locals)`. `async` is outside phase
  1 (design section 11), and `_types` (core) exports all four types.
* The frontend silently drops three things today, against the rule that nothing is
  approximated: function annotations, module-level annotations (`x: int` becomes `pass`,
  `x: int = 1` an assignment), and PEP 695 type parameters on a `def`. Fourteen executed units
  have function annotations, among them the target's own `slugify` and `main`. The fix lowers
  them, it does not refuse them: task 4 models PEP 649 `__annotate__` (step A6 of the plan).
* Executed code reaches the interpreter through `sys._getframemodulename` (`namedtuple`, from
  `shutil`'s module body), `getattr`/`setattr`/`delattr` with computed names (18, 12 and 4
  units), `__dict__` (12), `__mro__` (6), `sys.modules` (5), and `exec` and `eval` through the
  staged `dataclasses` and `namedtuple` texts. The C++ runtime has to answer each of them, and
  each is already in the spec's tier table or in staging.

**What it does not show.** The four runs are not every input. The help and error paths show
how much a run misses, and the closed-world reachable set is not measured. A unit is one code
object, so the frontend's verdict hides everything behind a unit's first blocker; the census
shows it. The census is syntactic: it cannot see whether a call is `super()` or a name bound
to it, or which semantics a construct needs (`__prepare__` namespaces, `__set_name__`). For
the shim `annotationlib`, CPython runs its own module during the measurement, so the shim's
code objects never count as executed.

**Repeat it.** `uv run python tools/scope.py --target cli_easy_slugs --variant=--help
"--variant=data/lines.txt --max-length x" "--variant=data/lines.txt --separator _
--no-lowercase"`, and the same with `--target service_easy_tokens` and `--target
data_easy_sales`.
