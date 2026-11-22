Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-22. Verbatim. Tag A39 in the review log. The first review under the author's
rule of that day (a review for steps that change runtime semantics broadly, small steps batched into one): its range is `7f7c267..2996062`,
four steps together, run non-interactively (standard input closed) in its own worktree (`bella-r39`) at `2996062`: the order of a `match`
case's stores, the fixes of review A38 (RL-859 to RL-874), a generator expression's iterable and iterator (RL-488), and the stack the
program runs on (Question 28). Its probes (`r39-probes/codex/`) stayed in that worktree. 11 findings; each was run on both sides by the
session before any verdict (review log, A39).

---

# A39 · CPython 3.15.2 conformance review of 7f7c267..2996062

All row paths below are relative to `r39-probes/codex`. From the checkout, build with `./r39-build "$PWD/r39-probes/codex/SUITE/prog.py"`, then run the printed executable with ROW as its sole argument. The reference command is `PYTHONHASHSEED=0 .venv/bin/python "$PWD/r39-probes/codex/SUITE/prog.py" ROW`. Both runs use seed zero, a 120-second timeout and an 8,000,000 KiB address-space limit. Rows with a shell-limit prefix use the argument after the underscore. Each row directory holds both raw streams and both shell-style statuses. Unless stated otherwise the reported rows exit 0 with empty stderr.

## A39-01 · Medium · Throwing into a fresh generator expression keeps the iterator alive in the handler

`pipeline/l1/frontend.py:1914`, `pipeline/l2/lower.py:386`. Reproduce with `gen/throwV`. The minimal shape is an iterable whose `__iter__` returns a fresh iterator with a printing finalizer, followed by `g = (x for x in source); g.throw(ValueError)` inside a try whose handler prints the exception class. The tested program also logs destruction of the source. CPython prints these lines:

```
drop iterator
ValueError NoneType
drop source
```

Bella prints:

```
ValueError NoneType
drop iterator
drop source
```

The additional row `lifetime/throw-0` reproduces the same order with a KeyError instance. The iterator is a second helper parameter until the generated loop starts. An injected exception bypasses the move out of that parameter. The saved exception frame therefore retains a local that CPython had on its evaluation stack and discarded during unwinding. This is specifically the exception path before the first resume. Rows `throwK`, `throwG` and `throwS` have the same reversal with KeyboardInterrupt, GeneratorExit and StopIteration respectively.

A separately run reduction is `reduced/unstarted`:

```python
class It:
    def __next__(self): raise StopIteration
    def __del__(self): print('iterator')
class Src:
    def __iter__(self): return It()
g = (1 for item in Src())
try: g.throw(ValueError)
except ValueError: print('handler')
print('return')
```

CPython prints `iterator, handler, return` on separate lines. Bella prints `handler, iterator, return`. In the snippets using `T(label)` below, the definition is:

```python
class T:
    def __init__(self, label): self.label = label
    def __del__(self): print(self.label)
```

## A39-02 · Medium · PEP 479 translation releases the generator's locals while its cause is still visible

`runtime/src/generator.cpp:466`, `runtime/src/core.cpp:1187`. Run `reduced/stop`. With a class T whose finalizer prints its label, the executed branch is:

```python
g = (1 for item in [T('source-item')])
next(g)
try:
    g.throw(StopIteration)
except RuntimeError as e:
    print('handler', type(e.__cause__).__name__)
print('return')
```

CPython prints `handler StopIteration\nsource-item\nreturn\n`. Bella prints `source-item\nhandler StopIteration\nreturn\n`. The generated frame records the injected StopIteration before conversion. At frame exit the runtime searches the replacement RuntimeError's traceback for the frame to receive its locals. The frame belongs to the cause's traceback, so this search misses it and generator cleanup releases the item. The separate iterable, iterator and item in `gen/throwstartedS` distinguish the early local releases from the correctly timed iterator release.

## A39-03 · Medium · A prelude built-in acquires an extra receiver as a call or context-manager hook

`runtime/src/call.cpp:184` and `runtime/src/call.cpp:2077`. Run `reduced/call` or `reduced/enter`:

```python
class C:
    def __repr__(self): return 'instance'
    __call__ = __enter__ = __exit__ = print

C()(42)
# The other row executes: with C(): pass
```

For the call CPython prints `42\n`, Bella `instance 42\n`. For the with statement CPython prints `\nNone None None\n`, Bella `instance\ninstance None None None\n`. Both fast paths bind an internal PyFunction without checking whether it represents a module-level built-in. The general descriptor path in types.cpp:217 already makes this distinction. Matrix rows are `slots/call`, `slots/enter` and `slots/exit`, variant `print plain`.

## A39-04 · High · Assignment through a descriptor bypasses binding of its setter

`runtime/include/bella/object.hpp:1746`. Run `reduced/set`:

```python
class D:
    __set__ = staticmethod(lambda owner, value: print(value))
class H:
    d = D()
try: H().d = 42
except TypeError: print('TypeError')
```

CPython prints `42\n`, Bella `TypeError\n`. The assignment path calls the raw class entry with three arguments, including the descriptor. CPython binds that entry to the descriptor first and calls the result with the owner instance and value. The same cause affects `slots/set` for callable objects, class methods, properties and static partials. For the plain callable object the recorded argument types are `('Holder', 'int')` versus `('C', 'Holder', 'int')`. A setter can silently receive the wrong arguments even when assignment succeeds.

## A39-05 · Medium · Binding a classmethod with a noncallable payload raises too early

`runtime/prelude/builtins.py:599`, `runtime/src/types.cpp:1944`. Run `reduced/hintbind` and `reduced/hint`:

```python
import operator
class C: __length_hint__ = classmethod(None)
try: print(type(C().__length_hint__).__name__)
except TypeError: print('TypeError')
# In the second row the try body is: print(operator.length_hint(C(), 19))
```

CPython prints `method\n` and `19\n` respectively. Bella prints `TypeError\n` in both. The prelude uses the public method constructor, which checks callability. CPython's internal classmethod binding makes a bound method first. Its invocation fails inside the part of length_hint that substitutes the default. The `none class` and `property class` variants of `slots/length_hint` both reproduce this.

This also suppresses a program callback. With `sys.unraisablehook` printing the exception class, `C.__del__ = classmethod(None); x = C(); del x; print('after')` prints `unraisable TypeError\nafter\n` under CPython and `after\n` under Bella. The latter discards the binding failure at `runtime/src/call.cpp:3412`, before the finalizer invocation that would report it. Rows `lastrows/none-class` and `lastrows/prop-class` reproduce this effect.

## A39-06 · Medium · The generator-expression traceback points to its opening line on iteration and resumed throw

`pipeline/l1/frontend.py:1872`, `pipeline/l1/frontend.py:1911`. Run `trace/next` and `trace/resumed`. The multiline expression in the saved program is:

```python
    g=(                          # 14
        check(x,'elem')          # 15
        for x in S()             # 16
        if check(x,'if')         # 17
        for y in check(x,'later')# 18
    )
```

In `next`, S.__next__ raises LookupError. In `resumed`, one yield succeeds and the caller throws ValueError. Both runtimes have empty stdout and exit 1. These are the stderr frame sequences, outermost first, with the exception on the last line of stderr:

| Row | CPython | Bella |
| --- | --- | --- |
| next | module 25, f 24, genexpr **16**, __next__ 8, LookupError | module 25, f 24, genexpr **14**, __next__ 8, LookupError |
| resumed | module 25, f 23, genexpr **15**, ValueError | module 25, f 23, genexpr **14**, ValueError |

The lowering creates a For and a Yield without their own source positions and fills missing locations from the entire expression. Calls inside the element, condition and later iterable retain their own locations. The raw stderr files preserve the full tracebacks, including CPython's source excerpts.

## A39-07 · Medium · Zero-argument super() in a generator expression loses its first argument

`pipeline/l1/frontend.py:910`. Run `contexts/super`. The operation is:

```python
class C:
    def method(self):
        return next(super() for i in (1,))
try: C().method()
except BaseException as e: print(type(e).__name__)
```

CPython prints `TypeError\n`. Bella prints `RuntimeError\n`. The class pass records a generator expression as a function with no first argument. The subsequent super rewrite passes the missing-argument sentinel. CPython has a first argument, the tuple in this row, and rejects it when checking its relationship to C.

The stronger `more/super` row uses an iterable instance of C itself: `def __iter__(self): return iter([1])` and `return next(super().__self__ is self for x in self)`. CPython prints `True\n`, Bella `RuntimeError\n`.

## A39-08 · Medium · An untaken generator-expression branch changes destruction order after break

`pipeline/l1/frontend.py:1947`, `pipeline/l1/frontend.py:1969`. Run `breakcell/observe`. With T printing its label on destruction:

```python
def f():
    if r == 'never':
        g = (next(g) for x in [1])
        return
    g = (T('result') for x in [T('source')])
    for v in g: break
    print('return')
```

CPython prints `return\nsource\nresult\n`, Bella `return\nresult\nsource\n`. The outer transformer visits the whole if statement, hoisting the helper that closes over g ahead of the if. Its closure keeps g's cell alive as the frame releases v. CPython makes no such helper on the path taken. The control `more/cell` makes g a cell using an untaken lambda instead, and both sides release the source first. The broader `gen/break` row also distinguishes the iterator, loop item, source, and yielded result.

## A39-09 · Medium · A 20,000-call wrapped recursion succeeds where CPython raises RecursionError on the default stack

`runtime/src/core.cpp:716`, `runtime/src/core.cpp:737`. Run `stack/cached-100000-20000` or `stack/part-100000-20000` with the default shell stack (8192 KiB soft, unlimited hard). The tested recursion for the first row reduces to:

```python
import functools, sys
sys.setrecursionlimit(100000)
@functools.lru_cache(None)
def cached(n): return cached(n-1) if n else 0
for depth in (20000, 4):
    try: print(cached(depth))
    except RecursionError: print('RecursionError')
```

CPython prints `RecursionError\n0\n`, Bella `0\n0\n`. The partial variant calls `part(n-1)` through `part=functools.partial(through)`. The same rows agree with the shell stack unlimited, and differ at recursion limit 300000 with the default shell. The tested depth is 20000 in all four default-shell rows. These wrappers involve native recursion under CPython. Moving Bella onto its larger stack and measuring the guard there allows the compiled calls to finish. The shell's 1 MiB *soft-only* limit reproduces the default-shell direction for both wrappers. These policy-dependent results are distinguished from interpreter recursion-counter errors.

## A39-10 · Medium · With a constrained native stack Bella raises RecursionError on shallow-enough inputs CPython completes

`runtime/src/core.cpp:674`, `runtime/src/core.cpp:717`. Start each side under `ulimit -s 1024` and run `stack/prog.py plain-100000-20000` (the artifact directory is `stack/limit-s1024_plain-100000-20000`). Minimal operation:

```python
import sys
sys.setrecursionlimit(100000)
def f(n): return f(n-1) if n else 0
for n in (20000, 4):
    try: print(f(n))
    except RecursionError: print('RecursionError')
```

CPython prints `0\n0\n`, Bella `RecursionError\n0\n`. The native-stack guard applies to each compiled Python call. The hard-limit cap prevents the larger alternate stack in this configuration. The recovery call succeeds. This is an observable consequence of the chosen stack policy below the review's depth cutoffs. Related rows, with exact outputs below (each pair lists first and recovery line):

| Shell limit | Rows in stack/ | CPython stdout | Bella stdout |
| --- | --- | --- | --- |
| -s 1024 | closure, method (100000-20000) | 0, 0 | RecursionError, 0 |
| -s 1024 | sort (100000-20000) | 1, 1 | RecursionError, 1 |
| -s 1024 | cmp (10000-3000) | True, True | RecursionError, True |
| -s 1024 | loads, dumps, copy, regex (10000-3000) | 1, 1 | RecursionError, 1 |
| -s 65536 | regex (10000-3000) | 1, 1 | RecursionError, 1 |
| -s 65536 | cached, part (100000-20000) | 0, 0 | RecursionError, 0 |

With the default shell limit, project policies of 1 and 2 MiB also give the plain, method and dumps differences above, and 16 MiB gives the method and dumps differences. Those programs and both outputs are in the corresponding `config-N` directories. A policy smaller than the existing process stack leaves execution on that stack (core.cpp:720).

The 20,000-level yield-from chain also distinguishes a **reference interpreter crash** from a compiled failure. Run `stackedge/chain-close`, `chain-drop`, `chain-throw` or `chain-next`. The chain is `def chain(n): yield from chain(n-1)` with a base case that yields 1. The program prints `created`, advances once and prints the result, then closes, deletes, throws ValueError into, or exhausts the generator. Under a 1 MiB soft-only limit CPython prints `created\n1\n` and dies from SIGSEGV (139) on close, drop and throw. Bella prints `created\n1\ndone\n` for close and drop, and `created\n1\nValueError\ndone\n` for throw, exiting 0. Under a 1 MiB hard limit CPython has those same three crashes but finishes the next row with StopIteration. Bella prints `created\nRecursionError\ndone\n` for all four, hitting the native guard on the *first* advance. Stderr is empty in these rows. At the default shell limit all four rows agree.

## A39-11 · Medium · A positive stack size overflows before the hard-limit cap is applied

`runtime/src/core.cpp:711`, `runtime/src/core.cpp:718`. In `config-wrap/bella.toml`, `[platform] main_stack_mib = 17592186044416` (2⁴⁴) is a positive integer representable in signed 64-bit TOML. Use the plain recursive program in A39-10. Build first, then start **both** sides with `ulimit -s 65536; ulimit -Ss 1024` in their respective shells. The row is `soft1024-hard65536_plain-100000-20000`.

CPython prints `0\n0\n`. Bella prints `RecursionError\n0\n`. The policy loader accepts the value. Unsigned left shift by 20 in the MiB-to-byte conversion produces zero on this target. The subsequent minimum with the 64 MiB hard limit therefore selects zero and execution stays on the original 1 MiB stack. This is independently distinguishable from an inability to reserve the requested space. With `config-1024` and the **same hard and soft limits**, Bella caps the request to 64 MiB and prints `0\n0\n`, matching CPython. `config-huge` also reproduces the wrong outcome for 2⁶⁴ MiB.


### Stack row index

These are all paired stack rows with different stdout or status in the stack-policy findings, including the additional depths. Rows are grouped by shell setting and by the output they produced. A slash in an output cell denotes a newline. Unless a status appears in the cell, both statuses were 0 and both stderr files were empty. `stackedge` is listed separately above. The ordinary `stack` rows with CPython status 139 are the same suspended-chain cleanup seen in that reduction.

| Suite and shell prefix | Arguments (each is a separate run) | CPython stdout | Bella stdout |
| --- | --- | --- | --- |
| config-1, default | `method-100000-20000`, `plain-100000-20000` | 0 / 0 | RecursionError / 0 |
| config-1, default | `dumps-10000-3000` | 1 / 1 | RecursionError / 1 |
| config-1024, default | `cached-100000-20000` | RecursionError / 0 | 0 / 0 |
| config-16, default | `method-100000-20000` | 0 / 0 | RecursionError / 0 |
| config-16, default | `dumps-10000-3000` | 1 / 1 | RecursionError / 1 |
| config-2, default | `method-100000-20000`, `plain-100000-20000` | 0 / 0 | RecursionError / 0 |
| config-2, default | `dumps-10000-3000` | 1 / 1 | RecursionError / 1 |
| config-huge, default | `method-100000-20000`, `plain-100000-20000` | 0 / 0 | RecursionError / 0 |
| config-huge, default | `dumps-10000-3000` | 1 / 1 | RecursionError / 1 |
| config-huge, soft1024-hard65536 | `plain-100000-20000` | 0 / 0 | RecursionError / 0 |
| config-wrap, default | `plain-100000-20000` | 0 / 0 | RecursionError / 0 |
| config-wrap, soft1024-hard65536 | `plain-100000-20000` | 0 / 0 | RecursionError / 0 |
| stack, default | `cached-100000-20000`, `cached-300000-20000`, `cached-300000-22000`, `part-100000-20000`, `part-300000-20000`, `part-300000-22000` | RecursionError / 0 | 0 / 0 |
| stack, limit-Ss1024 | `cached-100000-20000`, `cached-300000-22000`, `part-100000-20000`, `part-300000-22000` | RecursionError / 0 | 0 / 0 |
| stack, limit-Ss1024 | `gen-100000-20000`, `gen-300000-22000` | empty (status 139) | 1 / 1 |
| stack, limit-s1024 | `closure-100000-20000`, `closure-300000-22000`, `method-100000-20000`, `method-300000-22000`, `plain-100000-20000`, `plain-300000-22000` | 0 / 0 | RecursionError / 0 |
| stack, limit-s1024 | `copy-10000-3000`, `copy-100000-4000`, `copy-1500-700`, `copy-300000-4500`, `dumps-10000-3000`, `dumps-100000-4000`, `dumps-1500-700`, `dumps-300000-4500`, `loads-10000-3000`, `loads-100000-4000`, `loads-1500-700`, `loads-300000-4500`, `regex-10000-3000`, `regex-100000-4000`, `regex-1500-700`, `regex-300000-4500`, `sort-100000-20000`, `sort-300000-22000` | 1 / 1 | RecursionError / 1 |
| stack, limit-s1024 | `cmp-10000-3000`, `cmp-100000-4000`, `cmp-300000-4500` | True / True | RecursionError / True |
| stack, limit-s1024 | `gen-100000-20000`, `gen-300000-22000` | empty (status 139) | RecursionError / 1 |
| stack, limit-s65536 | `cached-100000-20000`, `cached-300000-22000`, `part-100000-20000`, `part-300000-22000` | 0 / 0 | RecursionError / 0 |
| stack, limit-s65536 | `regex-10000-3000`, `regex-100000-4000`, `regex-300000-4500` | 1 / 1 | RecursionError / 1 |

## Coverage and limits

The Linux memory observation was reproducible in `process/mem-10000`, `mem-10001` and `mem-10002`. With a 2048-byte local bytearray per recursive call, both processes increased RSS by more than 4 MiB and the smaller recovery call succeeded. After unwinding, CPython's RSS fell by more than 4 MiB and Bella's did not. This measures process resident pages, which include allocator and stack storage. It does not establish that Python objects leaked, and no exact RSS value is counted as a finding.

Zero, negative, boolean, float, string, array, table and date policy values reached a build-time ValueError. Build diagnostics are in the corresponding `config-*/build.err`. The direct yield-in-generator-expression syntax probe received CPython's SyntaxError and Bella's build refusal for the same construct. The unconditional staged exec probe ran on both sides. The six conditional exec rows named their staging stop. Dynamic parsing, subprocess, os.popen and frame introspection stops are outside the finding count. Tracebacks were compared by frame names and line numbers as well as raw streams. Printed addresses and omitted source excerpts are excluded as requested.

Across 807 paired rows, 680 matched byte for byte on stdout, stderr and status. Each special-method matrix row contains 36 independent installations of a hook (12 values, plain or wrapped in staticmethod or classmethod). Build-only outcomes are outside those counts.

## Checks that agreed

- All 68 FileIO and direct pipe rows matched. They cover all permutations of the valid binary mode letters, the opener's path and numeric flags, clearing an inheritable descriptor, a closed descriptor, an opener exception, False, a negative descriptor, an oversized integer and an index-only object. All 18 additional `pipe` rows matched. These arrange actual SIGALRM delivery during a blocking read or write for the nine raw, buffered and text I/O paths. One handler makes the pipe ready and returns. The other makes it ready and calls `os.close(-1)` to raise an actual OS error while a LookupError is being handled. Both sides printed the same handler state, result or errno, and exception context.
- All 12 `match` rows, the 48 runnable `patterns` rows and the separately staged exec row matched. They covered destructor order and values seen by guards across failed cases, false and raising guards, subject aliasing, nonlocal and global stores, body exits and finally. The larger matrix included sequence, starred, mapping-rest, positional and keyword class, OR, AS, value, singleton and wildcard patterns over multiple lines, with methods, closures, generators, class and module bodies, lambda defaults, with statements and loops over generators.
- Generator reentry raised ValueError on both sides. Early termination by any, all, membership, next, short zip and islice matched in the tested rows. Explicit close and dropping after multiple yield counts matched. So did element, condition, `__next__` and later-iterable failures at different turns, except for the multiline traceback position reported above. Name and qualname, running and suspended flags, yield-from, locals, vars, dir, globals and the active exception agreed. String, bytes, dict, set, range, file and generator sources matched, as did nested expressions, a lambda, a default, a decorator, a class body, self and walrus capture. The 18 list/set/dict controls for defaults, decorators, lambdas, super in a method, walrus targets and nesting matched.
- The slot matrix agreed for iteration, next, length, truth, repr, str, hash, rich comparison, containment, indexed read/write, index and numeric conversion, format, set_name, init_subclass, class subscription, missing keys, reversal, filesystem paths, bytes, rounding, negation and forward, reflected and in-place addition. The descriptor getter row agreed after excluding object addresses. The individual hook values, argument-type logs, result classes and exception classes are in `slots` and `lastrows`.
- Main-thread and native-thread identity relationships matched. Both sides passed the shell's limits to children started by posix_spawn and system. In the unmodified shell the child observed 8192 KiB soft and unlimited hard. The deeper recursion tests included ordinary functions, methods, closures, delegated generators, sort keys, lru_cache and partial wrappers, recursive special methods, deep copy, JSON in both directions, comparison and regular-expression compilation. Small recovery calls agreed in the reported early-limit cases. The alarm and interval-timer rows with returning, raising and recursive handlers matched, including delivery during active recursion.
- Falling off the end, `os._exit(33)`, abort and terminating signals produced the same shell statuses. The sys.exit rows at depth 1 and 20000 agreed for no argument, None, positive, negative and oversized integers, bool, str, bytes, tuple, list, float, and objects with a successful or raising __str__. The two depths of uncaught LookupError and KeyboardInterrupt agreed on status, exception class and traceback frame sequences. SystemExit in an atexit callback or an exit-time finalizer also agreed on the process status and reported exception class.
