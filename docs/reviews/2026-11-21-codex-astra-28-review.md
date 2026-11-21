Codex `gpt-6.2-astra` at low reasoning effort, 2026-11-21, the cross-check the author asked for after each step. Verbatim. Tag A28 in the
review log. Its range is `ebf460e..2977264`, three commits, run non-interactively (standard input closed) in its own worktree (`bella-r28`) at
`2977264`: a tuple keeps its hash (RL-574, C-6-24) first, then the fixes of A27. Its probes (`r28-probes/codex/`) stayed in that worktree.
Six findings; each program was run on both sides by the session before any verdict (review log, A28).

---

# A28 conformance review · ebf460e..2977264

Six confirmed findings. Two affect control flow: a deep tuple can kill the process during hashing (A28-03), and a cached call with starred arguments can raise before entering the function (A28-05). Each probe directory under `r28-probes/codex/` contains the source and separate stdout, stderr and shell status for CPython 3.15.2 and Bella at `2977264`. Both ran with `PYTHONHASHSEED=0`.

## A28-03 · High · Hashing a deeply nested tuple can terminate the process

At `runtime/src/core.cpp:635`, `tuple_hash` descends through `hash_of` without checking the remaining native stack. CPython checks `_Py_EnterRecursiveCall(" while hashing a tuple")` before descending (`Objects/tupleobject.c:387`).

```python
import os
t = ()
for _ in range(100000):
    t = (t,)
try:
    hash(t)
except RecursionError:
    print("RecursionError", flush=True)
else:
    print("hashed", flush=True)
os._exit(0)
```

With `ulimit -s 1024` applied to both processes, CPython prints `RecursionError` and exits 0. Bella produces empty stdout and dies from SIGSEGV (shell status 139). Both stderr files are empty. The immediate exit isolates hashing from tuple destruction. With the session's default 8192 KiB stack, the same program prints `hashed` and exits 0 on both sides. Evidence: `r28-probes/codex/deep1m/` and `deep/`.

A second run of A28-03 at 300,000 levels reproduces the same `RecursionError` versus SIGSEGV under the default 8192 KiB stack, with empty stderr on both sides (`deep300/`).

## A28-05 · High · An untyped LRU cache rehashes the elements of a prehashed star-argument tuple

`runtime/prelude/_functools.py:573` slices the wrapper's arguments to construct `given`. For an untyped call without keywords, `_make_key` then uses that new tuple. CPython's `lru_cache_make_key` (`Modules/_functoolsmodule.c:1255`) can retain the caller's exact star tuple as the key, including its cached hash. In this example the extra hash prevents the function from running at all.

```python
from functools import lru_cache
class K:
    def __hash__(self):
        if armed: raise ValueError
        return 1
@lru_cache(2)
def f(x): return 42
armed = False
t = (K(),)
hash(t)
armed = True
try: print(f(*t))
except ValueError: print('ValueError')
print(tuple(f.cache_info()))
```

| | stdout line 1 | stdout line 2 | stderr | status |
|---|---|---|---|---|
| CPython | `42` | `(0, 1, 2, 1)` | empty | 0 |
| Bella | `ValueError` | `(0, 0, 2, 0)` | empty | 0 |

The counting variant also reproduces with two positional arguments and with an unbounded cache. The `typed=True` control agrees. Evidence: `r28-probes/codex/starfail/` and `star/`.

## A28-02 · Medium · A constant tuple is rebuilt on each call

`pipeline/backend/cpp.py:1133` emits a runtime `build_tuple` for this literal. CPython loads the same tuple from the function's constants on both calls. Retaining a hash on each allocated tuple cannot preserve sharing between these two calls.

```python
def pair():
    return (11, 22)
print(pair() is pair())
```

CPython prints `True`; Bella prints `False`. Both exit 0 with empty stderr. The two operands are simultaneously live. Evidence: `r28-probes/codex/constant/`.

## A28-04 · Medium · An ignored ResourceWarning calls user code at shutdown

`runtime/src/imports.cpp:630` reads the current `warn` attribute when finalizing an unclosed file during shutdown. The ordinary path at line 627 uses the retained warning function. CPython applies its ignore filter without calling the replacement.

```python
import _warnings, warnings
warnings.simplefilter('ignore', ResourceWarning)
def replacement(*a): print('replacement', flush=True)
_warnings.warn = replacement
f = open(__file__)
```

CPython produces empty stdout. Bella prints `replacement`. Both exit 0 with empty stderr. This observes whether an arbitrary callback runs, independent of finalizer order at exit. Evidence: `r28-probes/codex/exitwarn/`.

## A28-06 · Medium · The A27 first-store failure test raises before the store

At `pipeline/tests/test_review_2026_11_21_a27.py:63`, the test raises on the second collision with the existing key. The first comparison is the initial lookup. After the user function returns, `runtime/prelude/_functools.py:700` looks up the key again to check for a reentrant insertion. This is where the second comparison raises. The first insertion of the new link, at line 710, requires the **third** comparison. Both failures leave exactly the cache statistics asserted in the test comment, so those statistics cannot distinguish the branches.

The instrumented program prints the call and comparison order. Target 4 allows insertion to succeed.

```python
from functools import lru_cache
class K:
    def __init__(self,n):self.n=n
    def __hash__(self):return 0
    def __eq__(self,o):
        events.append('eq')
        if events.count('eq')==target:raise ValueError
        return self.n==o.n
class R:
    def __del__(self):events.append('del')
@lru_cache(3)
def h(k):
    events.append('call')
    return R()
for target in (2,3,4):
    events=[]
    h(K(1))
    events.clear()
    try:h(K(2))
    except ValueError:pass
    print(target,events,tuple(h.cache_info()))
    h.cache_clear()
```

CPython and Bella each print the following, with empty stderr and exit status 0.

```text
2 ['eq', 'call', 'eq', 'del'] (0, 2, 3, 1)
3 ['eq', 'call', 'eq', 'eq', 'del'] (0, 2, 3, 1)
4 ['eq', 'call', 'eq', 'eq'] (0, 2, 3, 2)
```

A regression confined to cleanup after the fresh link's failed store can pass the A27 row. Evidence: `r28-probes/codex/firststore/`.

## A28-01 · Medium · The harness accepts a changed application diagnostic

At `conformance/harness.py:190`, the warning-path rule strips the directory from ordinary stderr. This program uses the identity difference in A28-02 to select its diagnostic. Run with identical arguments, it would pass the harness.

```python
import sys
def names():
    return ("demo.py",)
path="/home/nathan/workspaces/nth/bella-r28/conformance/cases/demo.py" if names() is names() else "demo.py"
print(path + ":7: phase: done",file=sys.stderr)
```

Both stdout files are empty and both processes exit 0. The raw stderr files contain one line each.

```text
CPython: /home/nathan/workspaces/nth/bella-r28/conformance/cases/demo.py:7: phase: done
Bella:   demo.py:7: phase: done
```

The application prints `phase` itself. The regular expression at line 72 accepts any identifier as the warning category. Calling the actual `mask_stderr` on each capture returned `demo.py:7: phase: done\n` for both. Evidence: `r28-probes/codex/mask_same/`.

## Checks that agreed

- **Containers.** For colliding tuple keys, the observed hash and equality call sequences agreed for dict lookup and insertion through `setdefault`, `pop`, updates, `fromkeys`, copies, equality and resize. Set membership, updates, copies, equality, union, intersection, difference, symmetric difference and conversion to frozenset agreed. Counter, defaultdict and OrderedDict agreed. The larger collision probe used ten keys inserted in opposite orders (`containers/`, `tables/`).
- **Types and hash failures.** The named tuple, slotted tuple subclass, subclass with its own hash, struct_time and stat_result agreed on the observed calls through hashing, equality, nested frozensets, shallow/deep copy and container operations. The version_info singleton's identity and repeated hash agreed. A non-integer hash result followed by a valid result, a returned -1, a large integer, a changing hash and repeated attempts on a tuple reaching itself through a list agreed (`types/`, `hashes/`, `creation2/`).
- **Tuple producers.** The dynamic literal, iterable conversion, exact-tuple conversion, slice, concatenation, repetition, ordinary function arguments, partial and exception arguments, MRO, bases, defaults, divmod, partition, popitem, enumerate, zip, map with two inputs, sorted items, struct unpack and regex groups agreed on the tested identity relationships, hash reuse and equality. Star-unpacking and the shape and unhashability of an os.walk row also agreed (`creation2/`, `walk/`). The original creation probe reached a named stop at `co_consts`; the second probe ran all the later rows.
- **Recycled tuples.** The mixed retain/release sequence agreed for enumerate, zip with one and two inputs, strict zip with three inputs, pairwise, product, both combinations iterators, permutations, zip_longest, and ordinary and reversed dict and OrderedDict items. The probe included repeated and unequal elements, a hash that raises on the second result, and hashing a retained result after advancing (`recycle/`).
- **Bounded cache.** Reentrant same-key insertion, filling or clearing during the call, a user exception, the observed key/result finalizer order, stored traceback identity, cache statistics, and caching a generator agreed. Clearing the cache inside the oldest key's comparison reached the missing-key pop and agreed, including finalizer order. The actual failing first insertion agreed when the third comparison raised. Inherited, replaced, noncallable, None and deleted index methods, an int subclass and bool agreed. The coroutine row reached a named stop (`cache/`, `miss/`, `orphan/`, `firststore/`).
- **Warnings during execution.** Replacing or deleting the warning functions and display hooks, a display hook that raises, changing or deleting filters, and replacing or removing the modules produced the same observed calls and exception classes for binary line buffering, a bool passed to open or os.stat, and unclosed-file finalization. Raw stderr differed only by the registered D-20 tracemalloc hint in that matrix. A shadow warnings module deleting `_warnings.warn_explicit` and replacing the module entry on the first compiler warning still displayed both warnings in order. Binary line buffering also agreed with the low-level module entry set to None. The relative-import fallback displayed its ImportWarning with the low-level warn name replaced by a raising function (`warnings/`, `startup/`, `coldwarn/`, `importwarn/`).
