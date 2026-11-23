Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-23. Verbatim. Tag A43 in the review log. Range `4cbedcc..2c342bc`:
the exit as CPython's `finalize_modules` sequence (`2c342bc`, RL-514, C-9-13), the step that changes what programs do
broadly (the author's rule of 2026-11-22), and A42's fixes (`ab557b8`) as a second pass. Run non-interactively (standard
input closed) in its own worktree (`bella-r43`), the prompt worded as conformance. Probes (`r43-probes/codex/`) stayed in
that worktree; the session ran the 41 rows of the findings and their controls again before any verdict and got the same
outputs byte for byte (review log, A43).

---

# A43 · Bella conformance review

Compared detached commit `2c342bc` against CPython 3.15.2, reviewing `4cbedcc..2c342bc`. The paths below are relative to `r43-probes/codex/`. For each `DIR/ROW`, from the checkout root:

```sh
ulimit -v 8000000
export PYTHONHASHSEED=0
p=r43-probes/codex/$DIR/prog.py
exe=$(timeout 600 ./r43-build "$p")
timeout 120 .venv/bin/python "$p" "$ROW"
timeout 120 "$exe" "$ROW"
```

Across 28 builds and 102 process pairs, 36 rows demonstrate the 14 findings below. Two further differences fall under D-01 and D-06, nine rows reached named stops, and 55 matched byte for byte. Each row directory holds the two raw streams and exit statuses. Output blocks show complete lines, including the final newline. Unless specified, both stderr streams are empty and both exit statuses are 0.

## A43-01 · Medium · A nonempty gc.garbage loses its shutdown warning

`runtime/src/call.cpp:3735`. Row `gcwarning/warn`. Minimal program:

```python
import gc, warnings
warnings.simplefilter('always', ResourceWarning)
gc.garbage.append('retained')
```

Both stdout streams are empty. CPython writes this line to stderr, while Bella's stderr is empty:

```text
gc:0: ResourceWarning: gc: 1 uncollectable objects at shutdown; use gc.set_debug(gc.DEBUG_UNCOLLECTABLE) to list them
```

CPython calls `_PyGC_DumpShutdownStats` at `Python/pylifecycle.c:1952`, after the first no-fail collection and before wiping the surviving modules. Bella goes straight from that collection to recounting module references. The list has one entry inserted explicitly, so the warning is independent of the collector's counts.

## A43-02 · Medium · An invalid hex call executes the grouping argument's Python code

`runtime/src/bytes.cpp:628`. Rows `hex/bytes` and `hex/array`. Minimal differing call:

```python
class N:
    def __index__(self):
        print('index')
        return 1
try:
    b'ab'.hex(bytes_per_sep=N(), wat=1)
except TypeError:
    print('TypeError')
```

The full rows each include three invalid-call controls first. CPython stdout is `TypeError\nTypeError\nTypeError\nTypeError\n`. Bella stdout is `TypeError\nTypeError\nTypeError\nindex\nTypeError\n`. Substituting a bytearray gives the same difference. The shared method converts each recognized keyword as it scans the keyword array. CPython's argument parser rejects the unknown keyword before the conversion can call `__index__`.

## A43-03 · High · A stream installed by a late finaliser misses its flush and its exit status

`runtime/src/call.cpp:4427` and `:4437`. Rows `lateflush/ok` and `lateflush/fail`. The failing program reduces to:

```python
import os, sys
class Stream:
    closed = False
    def flush(self, w=os.write, E=OSError):
        w(1, b'flush\n')
        raise E('late flush')
class Install:
    def __del__(self, s=sys, stream=Stream(), w=os.write):
        w(1, b'install\n')
        s.stdout = stream
def setup():
    x = Install()
    x.cycle = x
    sys.holder = x
setup()
```

On `fail`, CPython writes `install\nflush\n` and exits **120**. Bella writes `install\n` and exits **0**. Both stderr streams are empty. On `ok`, the flush returns normally, producing the same stdout difference with both statuses 0. CPython runs its second `flush_std_files` after `finalize_modules` and inspects the streams then installed. Bella delays that check until after interpreter-state teardown, restricts it to streams with an `_io` type in their ancestry, and discards the return value.

## A43-04 · High · User attributes on the bootstrap modules retain their values through process exit

`runtime/src/call.cpp:3745`. Rows `bootstrap/internal` and `bootstrap/external`. Minimal program:

```python
import os, _frozen_importlib
class Mark:
    def __del__(self, w=os.write):
        w(1, b'released\n')
_frozen_importlib.test_holder = Mark()
```

CPython stdout is `released\n`. Bella stdout is empty. Replacing the module with `_frozen_importlib_external` gives the same result. The shutdown code copies the namespace and clears the copy. The original dictionary, which also owns the arbitrary user attribute, remains reachable from the interpreter's roots. Neither program introspects the bootstrap namespace or holds a weak reference to a module.

## A43-05 · Medium · sys.is_finalizing() changes too late

`runtime/src/call.cpp:3706` and `:1322`. Minimal program for `flag/path`:

```python
import os, sys
class P:
    def __del__(self, w=os.write, f=sys.is_finalizing):
        w(1, b'finalizing\n' if f() else b'running\n')
sys.path_hooks = P()
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| `flag/path` | `finalizing\n` | `running\n` |
| `flag/cycle` (first exit collection) | `finalizing\n` | `running\n` |
| `flag/callback` (first collection's callbacks) | `start True\nstop True\n` | `start False\nstop False\n` |
| `flag/flush` (replacement stdout) | `running\nfinalizing\n` | `running\nrunning\n` |

CPython sets the finalizing state at `Python/pylifecycle.c:2418`, before the shutdown flush, the first collection and the release of path hooks. Bella uses the same boolean for this query and for module shutdown, and sets it only after restoring the standard streams.

## A43-06 · High · Releasing gc.garbage and gc.callbacks misses acyclic members' finalisers

`runtime/src/call.cpp:3768`, `runtime/prelude/gc.py:50`. Rows `reduce/garbage`, `reduce/callback`, and `exit/garbage`. Minimal program:

```python
import gc, os
class P:
    def __call__(self, *args):
        pass
    def __del__(self, w=os.write):
        w(1, b'P\n')
gc.garbage.append(P())  # same result with gc.callbacks
```

CPython stdout is `P\n` for both reduced rows. Bella stdout is empty. In `exit/garbage` CPython writes `False True True True\n` (including that both print and stdout have cleared), and Bella writes nothing. CPython's final release of the list can destroy its acyclic contents immediately. Bella decrefs the GC state's list slots, but the hidden gc prelude namespace still owns the lists it bound at import. That namespace is an interpreter root. The cyclic controls in `roots/garbage` and `roots/callback` are silent on both sides.

## A43-07 · High · An instance created by a finaliser loses its own finaliser's default argument

`runtime/src/call.cpp:3657` and `runtime/src/core.cpp:362`. Rows `fresh/default`, `reduce/cycle`, `reduce/kept`, `roots/newcycle`. Minimal shape:

```python
import os
class Child:
    def __del__(self, w=os.write):
        self.sink(1, b'entered\n')
        w(1, b'default\n')
class Parent:
    def __del__(self, cls=Child, sink=os.write):
        item = cls()
        item.sink = sink
        item.loop = item
        sink(1, b'created\n')
x = Parent()
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| `fresh/default` | `created\nentered\ndefault\n` | `created\n` |
| `reduce/cycle`, `reduce/kept` | `begin\nend\nP\n` | `begin\nend\n` |
| `roots/newcycle` | `False False\nTrue True\n` | `False False\n` |

The new self-cycle survives the collection in which the parent creates it. Bella's post-finaliser reachability check starts from the interpreter roots. A newly allocated, already isolated cycle is outside that trace, so it cannot protect the method reached through the child's class. The function clearer erases its defaults. The next collection cannot bind the finaliser call. The `fresh/bare` control removes the default and writes through the instance alone: both runtimes write `created\nentered\n`. An acyclic child in `reduce/immediate` also agrees.

## A43-08 · Medium · A namespace held directly by sys outlives the clearing of builtins

`runtime/src/call.cpp:3587`, `:3760`. Rows `phase/ns` and `imports/namespace`. Minimal program in three files:

```python
# observer.py
import os, builtins
class Watch:
    def __del__(self, w=os.write, b=builtins.__dict__):
        w(1, b'print cleared\n' if b.get('print') is None else b'print available\n')

# leaf.py
from observer import Watch
x = Watch()

# prog.py
import sys
def pin():
    import leaf
    sys.saved = leaf.__dict__
pin()
```

In `phase/ns` CPython writes `print available\n`, Bella `print cleared\n`. In `imports/namespace` CPython writes `False True False True\n`, Bella `False True True True\n`. When CPython clears the sys attribute, the namespace loses its last reference and releases its values before builtins are cleared. Bella had marked the module gone but left its dictionary attached to the immortal module because another reference existed then. Clearing sys releases that other reference without settling the pending namespace. The next trace is after both dictionaries have been cleared.

## A43-09 · Medium · Module wiping skips a string key's hash method

`runtime/src/call.cpp:3617`. Rows `key/visible` and `key/_private`. Minimal program:

```python
import os, sys
class K(str):
    armed = False
    def __hash__(self, h=str.__hash__, w=os.write):
        if self.armed:
            w(1, b'hash\n')
        return h(self)
sys.__dict__[K('visible')] = 123
K.armed = True
```

CPython writes `hash\n`; Bella stdout is empty. A key beginning with a single underscore gives the same result. CPython's `_PyModule_ClearDict` sets the value through `PyDict_SetItem`, invoking the subclass's hash. Bella exchanges the value directly in the entry and skips the callback in either pass.

## A43-10 · High · A successful write to the original stdout disappears

`runtime/src/call.cpp:3760` and `:4432`. Rows `pipe/open`, `buffer/noctx`, `buffer/ctx`, `imports/buffer`. Minimal shape, with an empty `data.py`:

```python
import os, sys
def setup():
    import data
    class Early:
        def __del__(self, out=sys.stdout, w=os.write):
            w(2, b'before\n')
            out.write('text\n')
            w(2, b'after\n')
    data.early = Early()
setup()
```

For `pipe/open`, `pipe/run.py` launches each command with stdout connected to a pipe and retains stderr separately. CPython stdout is `text\n`, Bella stdout is empty, and **both** stderr streams are `before\nafter\n`. Explicitly calling `out.flush()` immediately after the write gives `text\n` on both. The write returned normally and the reader stayed open.

| Regular-file capture | CPython stdout | Bella stdout |
|---|---|---|
| `buffer/noctx` | `before\nafter\ntext\n` | `before\nafter\n` |
| `buffer/ctx` | `before\nafter\ntext\nlate\n` | `before\nafter\nlate\n` |
| `imports/buffer` | `False False False False\nbuffered\nlate\n` | `False False False False\nlate\n` |

In `drain/observe`, a context value's finaliser checks a weak reference to the original stream. CPython stdout is `text\n` and stderr is `gone\n`. Bella stdout is empty and stderr is `unfinalized\n`: the stream is still alive and `gc.is_finalized(stream)` is false. In `streamheld/ctx`, `streamheld/sys`, and `streamheld/handler`, the program also holds the writing class in a context variable, a sys attribute, or a registered codec error handler. CPython stdout is `text\n`, Bella stdout is empty, and both stderr streams are `after\n`.

The bytes are buffered after the ordinary shutdown flush. CPython's destruction of the original stream drains them before the context value is released. Bella's final flush loop looks the stream up in the already-cleared sys dictionary, so it cannot drain the original buffer. The probes establish that automatic draining also failed on this ownership path. They do not identify which individual I/O layer first missed its finalisation.

## A43-11 · Medium · An unsuccessful import retains its globals past an explicit collection

`runtime/src/call.cpp:3725`, `runtime/src/core.cpp:195`. Rows `failed/direct`, `failed/held`, `exit/failed`. Minimal program:

```python
# watcher.py
import os
class P:
    def __del__(self, w=os.write):
        w(1, b'dropped\n')

# bad.py
from watcher import P
x = P()
raise ValueError('bad')

# prog.py
import os, gc
try:
    import bad
except ValueError:
    pass
os.write(1, b'caught\n')
gc.collect()
os.write(1, b'after collect\n')
```

| Row | CPython stdout | Bella stdout |
|---|---|---|
| `failed/direct` | `dropped\ncaught\nafter collect\n` | `caught\nafter collect\ndropped\n` |
| `failed/held` (save exception, then delete it after the first marker) | `caught\ndropped\nafter collect\n` | `caught\nafter collect\ndropped\n` |
| `exit/failed` | `False False False False\nafter\n` | `after\nFalse False False False\n` |

Import machinery removes the failed module's entry. CPython releases the ordinary namespace value when the exception's last frame reference goes away. Bella keeps the failed module's namespace attached until shutdown marks all modules removed and calls `settle`. The program observes the lifetime of an ordinary instance. It never manipulates the module cache or observes the module's identity.

## A43-12 · High · A Python exception while clearing sys.modules aborts the process

`runtime/src/call.cpp:3720`. Row `modkey/alias`. The complete program:

```python
import sys
import os
class K(str):
    active = False
    def __hash__(self, base=str.__hash__, w=os.write, E=ValueError):
        if self.active:
            w(1, b'hash\n')
            raise E('module key')
        return base(self)
k=K('additional_module')
sys.modules[k]=sys
K.active=True
```

Both write `hash\n` to stdout. CPython exits **0** and writes:

```text
Exception ignored while removing modules:
Traceback (most recent call last):
  File "/home/nathan/workspaces/nth/bella-r43/r43-probes/codex/modkey/prog.py", line 8, in __hash__
ValueError: module key
```

Bella dies from **SIGABRT** (shell status **134**). Its entire stderr is:

```text
terminate called after throwing an instance of 'bella::PyError'
```

The program adds an alias for sys. The failing set-to-None is performed by shutdown itself. CPython's `finalize_remove_modules` checks `PyObject_SetItem` and reports its error through `PyErr_FormatUnraisable`. Bella's `dict_set` propagates the Python exception past the shutdown boundary. Both commands were rerun with a 120-second subprocess timeout to capture the child's stderr separately from GNU timeout's signal diagnostic.

## A43-13 · Medium · A module registered during shutdown misses the surviving-module wipe

`runtime/src/call.cpp:3709` and `:3740`. Row `newmodule/insert`. With an empty `data.py`:

```python
import os, sys, types, builtins
class Watch:
    def __del__(self, w=os.write, s=sys, b=builtins.__dict__):
        w(1, '{} {}\n'.format(s.__dict__.get('stdout') is None,
                               b.get('print') is None).encode())
class Maker:
    def __del__(self, s=sys, M=types.ModuleType, W=Watch, w=os.write):
        m = M('late_module')
        m.item = W()
        s.saved = m
        s.modules['late_module'] = m
        w(1, b'created\n')
def install():
    import data
    data.obj = Maker()
install()
```

CPython stdout is `created\nFalse False\n`. Bella stdout is `created\nTrue False\n`. CPython appends the module to its weaklist as it processes the new entry and later wipes the namespace while stdout is available. Bella snapshots the modules before any entry is replaced. Its removal loop sees the insertion, but its surviving-module loop uses the earlier snapshot. The value survives until wiping sys releases the saved module.

## A43-14 · High · A second sys.modules entry fails to keep a module's namespace alive

`runtime/src/call.cpp:3559` and `:3722`. Row `alias/keep`. Three files:

```python
# observer.py
import os, builtins
class P:
    def __del__(self, w=os.write, b=builtins.__dict__):
        w(1, b'original\n' if b.get('open') is not None else b'restored\n')

# data.py
from observer import P
x = P()

# prog.py
import os, sys
class K(str):
    def __hash__(self, h=str.__hash__, s=sys, final=sys.is_finalizing, w=os.write):
        if final():
            s.kept = s.modules['zz_alias']
            w(1, b'kept\n')
        return h(self)
def setup():
    import data
    sys.modules[K('zz_alias')] = data
setup()
```

CPython stdout is `kept\nrestored\n`. Bella stdout is `original\nkept\n`. When shutdown processes the alias, its key saves the module in sys. CPython still has the namespace and releases the observer after restoring builtins. Bella excludes **all** edges out of sys.modules in its referrer count. Processing the first entry therefore releases the namespace despite the outstanding alias. The value is already gone while the original builtin `open` is available.

## Checks that matched

All 55 matching rows agreed on stdout, stderr and exit status byte for byte.

- **Module ownership.** A package submodule kept by a closure, a default argument, an instance through its base class, or a dictionary nested in another module matched. So did a function-local import with a plain module alias, a dynamically created module, and a closure surviving `sys.exit(7)`. On the uncaught-exception path the finaliser output and status 1 agreed. Its traceback differed only by the excluded source-line rendering.
- **Interpreter state.** A cached result held through `functools.lru_cache`, a suspended generator in sys, an exception with its traceback in sys, an atexit argument and a `weakref.finalize` callback matched. So did acyclic callables registered with codec search and error handling, context values, and acyclic observers in warning filters and the once registry. Cyclic GC-list controls, resurrection into a list, a finaliser attempting an import, a nested explicit collection, and a callback on a weak reference to an initially unreachable cycle also matched. With GC disabled the delayed-cycle flag probe agreed. A finaliser raising `ValueError` produced the same exception class, traceback location and status, apart from the function address.
- **Output and warnings.** The original stdout drained when a global finaliser or an initial-collection finaliser wrote in the `phase` controls. Storing the bound write method on the instance also matched. The explicit pipe flush delivered the bytes on both sides. With the read end closed before launch, the buffered finaliser row produced the same stderr and status 0. Both suppressed the shutdown GC warning under `DEBUG_SAVEALL`.
- **Scale and library shutdown.** A 150,000-deep list chain, 160 linked modules, 3,000 classes, 2,500 suspended generators and 2,500 kept exceptions all ended with matching output and status 0 within the run limit. A program importing all the requested standard-library modules and exercising JSON, regular expressions and decimal formatting printed `["aaa", "1.20"]` and exited 0 on both.
- **A42.** Clearing a closed generator's traceback frames twice, releasing an iterator after one `struct.iter_unpack` item, BLAKE2 buffer cleanup after an invalid salt, and both base32/base64 buffers being held during a raising `canonical` conversion all matched. Separator grouping with an index conversion that modifies a bytearray matched, as did the invalid-keyword controls for `binascii.hexlify`. The direct frame-object paths reached the excluded named introspection stop.
