Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-23. Verbatim. Tag A41 in the review log. Range `7355673..256985b`: the
cycle collector (the model by trial deletion, the header's collector, the runtime's kinds and the gc module). Run
non-interactively (standard input closed) in its own worktree (`bella-r41`). The first run was stopped by the provider's
filter after six findings (its third item spoke of memory safety); a second run in the same worktree, the item reworded
as conformance, covered the rest and wrote part two. Probes (`r41-probes/codex/`, `r41-probes/codex2/`) stayed in that
worktree. Each finding's rows were run on both sides by the session before any verdict (review log, A41).

---

# A41 — cycle collector conformance at 256985b

## A41-01 · High · A collection callback can start another collection

**Location** `runtime/src/gc.cpp:97` (`run_collection`), `runtime/include/bella/object.hpp:2841`. The reentrancy guard covers trial deletion and finalisation, but the runtime invokes both callback phases outside its lifetime. A callback can therefore run application callbacks again while the outer callback is still active.

**Reproducer** (`r41-probes/codex/callbacks/prog.py`)

```python
import gc, sys
gc.disable()
seen = []
def callback(phase, info):
    seen.append(phase)
    if phase == sys.argv[1] and seen.count(phase) == 1:
        gc.collect()
gc.callbacks.append(callback)
gc.collect()
gc.callbacks.clear()
print(seen)
```

Built with `./r41-build r41-probes/codex/callbacks/prog.py`. Ran `PYTHONHASHSEED=0 .venv/bin/python r41-probes/codex/callbacks/prog.py ROW` and the returned binary with the same row and seed. Both exited 0 with empty stderr for each row.

| Row | CPython stdout | Bella stdout |
|---|---|---|
| start | `['start', 'stop']` | `['start', 'start', 'stop', 'stop']` |
| stop | `['start', 'stop']` | `['start', 'stop', 'start', 'stop']` |

## A41-02 · High · A cyclic generator's finally suite runs after clear or stays suspended

**Location** `runtime/include/bella/object.hpp:2786`. The finalisation pass requires a class-level `__del__` and dispatches to instance finalisers. It has no dispatch for a generator's native finaliser. CPython finalises the suspended generator before deciding what was resurrected. In Bella the list can already be empty when releasing its generator triggers the close. If a peer resurrects the generator, the close can be skipped altogether.

**Minimal program** (the `gen` row of `sequence/prog.py`, with the selector removed)

```python
import gc, weakref
gc.disable()
saved, seen = [], []
def gen(box):
    try:
        yield
    finally:
        saved.append(box)
        seen.append(len(box))
def make():
    box = []
    g = gen(box)
    box.append(g)
    next(g)
    return weakref.ref(g)
w = make()
gc.collect()
print(seen, [len(b) for b in saved], w() is None)
```

Built `./r41-build r41-probes/codex/sequence/prog.py`, then ran the source with the pinned Python and the returned binary with each row as argv[1], as in A41-01. Both processes exited 0 with empty stderr in both rows.

| Row | Observable | CPython stdout | Bella stdout |
|---|---|---|---|
| gen | Size seen inside finally, size of the saved list afterwards, generator weakref dead | `[1] [1] False` | `[0] [0] True` |
| genlive | A peer saves itself and its delegating generator. The delegate logs its close. The program reads `gi_suspended` on the saved generator. | `['closed'] False` | `[] True` |

## A41-03 · Medium · The refcount finaliser sees itself as already finalised

**Location** `runtime/include/bella/object.hpp:2261`, exposed by `runtime/src/gc.cpp:130` (`g_is_finalized`). On release of the last reference Bella sets `FINALIZED` before calling the finaliser. CPython's `Objects/object.c:579` (`PyObject_CallFinalizer`) sets it after the call returns. CPython's cyclic path does set it before the call, which makes the two paths distinguishable.

```python
import gc, weakref
gc.disable()
seen, saved = [], []
class R:
    def __del__(self):
        seen.append(gc.is_finalized(self))
        saved.append(self)
r = R()
w = weakref.ref(r)
del r
gc.collect()
print(seen, gc.is_finalized(saved[0]))
saved[0].me = saved[0]
saved.clear()
gc.collect()
print(w() is None, seen)
```

Ran `lifetime/prog.py refcount` with the two commands in A41-01, substituting the probe directory. Both exited 0 with empty stderr.

| CPython stdout | Bella stdout |
|---|---|
| `[False] True` | `[True] True` |
| `True [False]` | `True [True]` |

The `cyclic` control inserts `r.me = r` before the first deletion. It printed the Bella column on both runtimes. Both correctly ran the finaliser only once.

## A41-04 · High · A resurrected BytesIO remains open after cyclic finalisation

**Location** `runtime/prelude/_io.py:504`, called by `runtime/include/bella/object.hpp:2789`. The prelude skips the finaliser body for exact BytesIO, StringIO and BufferedRWPair because their reference-count deallocators skip it. CPython's cyclic pass calls the inherited `tp_finalize` directly. Bella marks the stream finalised, then returns from its finaliser without closing it.

```python
import gc, io
gc.disable()
saved = []
class R:
    def __del__(self): saved.append(self)
r = R()
f = io.BytesIO(b'x')
r.f = f
f.r = r
del f, r
gc.collect()
print(saved[0].f.closed, gc.is_finalized(saved[0].f))
```

Ran `extra/prog.py ioflag` as in A41-01. CPython printed `True True`. Bella printed `False True`. Both exited 0 with empty stderr.

## A41-05 · High · Internal cleanup finalisers discard state that survives resurrection

**Location** `runtime/include/bella/object.hpp:2789`, `runtime/prelude/memoryview.py:61`, `runtime/prelude/_contextvars.py:112`. Bella represents destruction of private implementation objects with Python `__del__` methods. The cyclic pass invokes those methods before the resurrection check. CPython releases a managed buffer during clear/deallocation and releases a context mapping with its nodes. A surviving group still owns both resources.

**Buffer reproducer** (`export/prog.py revive`)

```python
import gc
gc.disable()
saved = []
class B(bytearray):
    def __del__(self): saved.append(self)
b = B(b'a')
b.v = memoryview(b)
del b
gc.collect()
b = saved.pop()
print(b.v.tobytes())
try: b.append(98)
except BufferError: print('export held')
else: print('resize allowed')
b.v.release()
```

Both printed `b'a'`. CPython then printed `export held`. Bella printed `resize allowed`. The live view has already lost its exporter's resize protection.

**Context reproducer** (`resources/prog.py context`)

```python
import contextvars, gc
gc.disable()
saved = []
class R:
    def __del__(self): saved.append(self)
key = contextvars.ContextVar('key')
def make():
    ctx = contextvars.Context()
    r = R()
    ctx.run(key.set, r)
    r.ctx = ctx
make()
gc.collect()
print(len(saved), len(saved[0].ctx), saved[0].ctx.get(key) is saved[0])
```

CPython printed `1 1 True`. Bella printed `1 0 False`. Bella's private `_Vars.__del__` popped every binding in the resurrected context. Both reproducers used the commands in A41-01 with their respective probe paths. All four runs exited 0 with empty stderr.

## A41-06 · High · A regular-expression scanner's subject is finalised while CPython keeps it alive

**Location** `runtime/prelude/_sre.py:704`, `runtime/include/bella/object.hpp:2457`. CPython's `Modules/_sre/sre.c:2805` visits the scanner's type and pattern. The subject held in its native scanning state contributes a reference count that cyclic GC does not subtract. Bella traverses the scanner's subject slot and its private buffer holder. It therefore treats a subject-to-scanner cycle as unreachable and runs user code that CPython never runs during the explicit collection.

```python
import gc, re, weakref
gc.disable()
saved = []
class B(bytearray):
    def __del__(self): saved.append(self)
b = B(b'a')
b.scan = re.compile(b'.').scanner(b)
w = weakref.ref(b)
del b
gc.collect()
print(len(saved), w() is None)
if saved:
    try: saved[0].append(98)
    except BufferError: print('export held')
    else: print('resize allowed')
```

Ran `resources/prog.py scanner` as in A41-01. CPython printed `0 False`. Bella printed `1 False`, then `resize allowed`. The first line distinguishes the traversal defect independently of buffer cleanup. Both exited 0 with empty stderr.


---

# A41, part two · 256985b

## A41-07 · High · Enabling DEBUG_SAVEALL in the start callback silently discards the garbage

At `runtime/src/gc.cpp:90`, Bella samples the debug flags before calling the start callbacks. At `runtime/include/bella/object.hpp:2829`, the deletion pass calls clear unconditionally. CPython checks the current SAVEALL flag during deletion, so the program can retrieve the finalised object from gc.garbage. This row completes normally on both sides, including the stop callback that resets the flags.

```python
import gc, weakref
gc.disable()
gc.collect()
seen = []
class Node:
    def __del__(self): seen.append('dead')
def phase(p, info):
    gc.set_debug(gc.DEBUG_SAVEALL if p == 'start' else 0)
n = Node()
n.link = n
w = weakref.ref(n)
del n
gc.callbacks.append(phase)
gc.collect()
gc.callbacks.clear()
print(seen, any(type(x) is Node for x in gc.garbage), w() is None)
```

Ran `PYTHONHASHSEED=0 .venv/bin/python r41-probes/codex2/phase/prog.py saveall`, built with `./r41-build r41-probes/codex2/phase/prog.py`, and ran the printed binary with `saveall` and the same seed. CPython printed `['dead'] True True`. Bella printed `['dead'] False True`. Both exited 0 with empty stderr. Full outputs are in `r41-probes/codex2/phase/saveall/`.

Three further rows share the same one-time flag check. Built `./r41-build r41-probes/codex2/flags/prog.py` and ran each selector as above. All three printed `True` on CPython and `False` on Bella. All six processes exited 0 with empty process stderr.

| Row | What the program tests |
|---|---|
| fromdel | The object's own finaliser sets SAVEALL. The stop callback resets it. The program tests whether the object reached gc.garbage. |
| stats | The start callback sets DEBUG_STATS. The program captures sys.stderr during collection and looks for a line starting with `gc: collecting`. |
| collectable | The start callback sets DEBUG_COLLECTABLE. The captured output is tested for a line starting with `gc: collectable`. |

CPython reads the current flags at each of these points in `Python/gc.c:1095`, `1483` and `1554` respectively. The diagnostic tests branch on the presence of the message, independently of its counts, duration and addresses.

## A41-08 · High · Cyclic GC closes a directory iterator that its resurrected owner can still use

Bella models `ScandirIterator` as an instance at `runtime/prelude/posix.py:357`. The collector visits its path fields, including the original path assigned at `runtime/prelude/posix.py:2118`, and calls its close-and-warn finaliser at `runtime/prelude/posix.py:393`. CPython's `Modules/posixmodule.c:17229` defines the iterator without the GC flag. Its reference to the path counts towards the path's lifetime, and cyclic GC never calls the iterator's finaliser.

```python
import gc, os
gc.disable()
saved = []
class Owner:
    def __del__(self): saved.append(self)
n = Owner()
n.self = n
n.it = os.scandir('.')
del n
gc.collect()
it = saved.pop().it
print(next(it, None) is not None, gc.is_finalized(it))
it.close()
```

Built `./r41-build r41-probes/codex2/directory/prog.py` and ran the pinned interpreter and printed binary with each row as argv[1], from the nonempty checkout, with hash seed 0. The other three rows use a str subclass as the path and store the iterator back on it. Each finaliser logs `'path'`. All eight processes exited 0 with empty stderr. Each ⏎ marks a stdout line break.

| Row | CPython stdout | Bella stdout |
|---|---|---|
| owned | `True False` | `False True` |
| path-drop | `[] False` ⏎ `[] False 0` | `['path'] True` ⏎ `['path'] True 0` |
| path-hold | `[] False` ⏎ `True True` ⏎ `[] False 0` | `[] False` ⏎ `True True` ⏎ `['path'] True 0` |
| path-revive | `[] False` ⏎ `[] False 0` | `['path'] False` ⏎ `['path'] False 1` ⏎ `False` |

In the last row Bella runs a user finaliser that CPython never reaches during collection. The resurrected path still owns the iterator, but its next read reports exhaustion.

## Coverage and matching results

Compared 187 pairs of runs. In 175 pairs stdout, stderr and exit status all matched byte for byte. Eight differing rows support the two findings above. Three local slotted-dataclass rows in `payload` hit a named staging stop. The module-level slotted dataclass with a weakref slot in `record` ran successfully in all three ownership modes. The remaining difference was permitted automatic-collection timing in `during-lean/automatic`. Both sides printed all 4,000 deaths. CPython observed deaths before the explicit collection, as did exact Bella. Lean Bella first observed them at the explicit collection.

Each directory under `r41-probes/codex2/` contains its program and a directory per selector with the six raw output and status files. Builds used `timeout 600 ./r41-build DIR/prog.py`, adding `--fidelity lean` for the two directories ending in `-lean`. Runs used `ulimit -v 8000000`, hash seed 0 and a 120-second timeout per process. These comparisons cover deaths and usable surviving state during execution.

| Probe | Checks that matched |
|---|---|
| edges · 75 | Drop, external hold then release, and resurrection for 25 edges. These included a count step, starmap, compress, dropwhile, takewhile, filterfalse, combinations with replacement, a dict item iterator's cached pair after clearing the dict, the closure tuple, function doc/name/annotate fields, a weakref subclass, WeakMethod, a weak proxy callback, contextmanager, closing, nullcontext, a partial over a bound method, a bound built-in, an unstarted generator's arguments, AttributeError.obj, StopIteration.value after clearing args, frozendict, and cmp_to_key's wrapper. |
| payload and record · 51 successful rows | Built-in subclass payloads carried the back-reference in their actual list, dict, tuple, set or frozenset data. Surviving instances retained the tagged element. Also checked an ABC-registered list subclass, a Flag combination removed from its class cache, a property getter and defaultdict factory bound to the tag, reversed dict views, frozenset iteration, a tee backlog spanning two blocks, a transferred ExitStack, IncrementalNewlineDecoder, an OrderedDict view and the slotted dataclass. |
| suspended · 9 | An exception thrown into a suspended generator, an object sent through yield from, and a partly consumed generator expression. Each held generator yielded the expected owner after collection. The death logs and weakref observations matched after release and resurrection. |
| sequence2 · 5 | A finaliser replaced its old peer with a newly linked group. A bound weakref.finalize callback pinned its target until invoked. A weak callback tried to detach a finalizer for the same target. An unraisable hook recovered the raising finaliser's owner through a plain weakref. A weak callback revived one group while dropping the external reference to another. |
| stress and stress-lean · 14 | Slotted finalisable nodes in 10,000- and 100,000-node rings and in chains downstream from a self-cycle. Every node logged exactly one death and the tail weakref died. A finaliser recursed 650 calls and returned 650. A candidate held only by a list was accessible through its weakref before the list was cleared and dead immediately afterwards. Both builds also printed all 2,500 loop-created objects' deaths. |
| during and during-lean | A finaliser removed the last reference to its child while the collector was running. Its weakref was already dead inside the finaliser. A weak callback released a candidate through a container, then made 600 more short-lived objects. Both builds agreed on the intermediate state and final totals. The 4,000-death loop also matched byte for byte in exact mode. |
| arguments · 16 | Combined positional and keyword errors for all eleven functions, including error classes and messages. Also checked duplicate generation and unknown keyword handling, reentrant threshold conversion and its visible side effects on failure, signed debug-flag boundaries and bool conversion, enable/disable return types, independence of get_stats snapshots, and rebinding gc.callbacks while retaining and mutating the original list. |
