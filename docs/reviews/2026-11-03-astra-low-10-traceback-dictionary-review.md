# Traceback Dictionary Review

Date: 2026-11-03

Reviewer: astra-low

Sequence: 10

Reviewed range: `f12af861c6c6c62853811a97c775ac9fb273441b..e827a479b08607756ac2c6b96ae6f2195563f79b` (8 commits, main).

The restart used a clean tree at the requested endpoint and fresh programs on CPython 3.15.2. I reproduced 13 findings below. The strongest new dictionary failures are a leaked value on failed insertion and a setdefault that can overwrite an existing value after invoking equality twice. The new traceback-entry mechanism passed the ordinary and nested propagation cases I tried; the remaining report failures involve a missing handler-header location, invalid/stale exception linkage state, and an exception-string failure that aborts reporting.

The report distinguishes inherited helpers from regressions or newly introduced mechanisms. In particular, the context/exception-field representation, pop wrapper, except-tuple validation and list-membership reference bug already existed at the previous endpoint. They are included because they directly affect the exception, dict and operator contracts requested for this round. These are not claims that all 13 defects were introduced in the eight commits.

## Verification

```sh
uv run python --version
uv run make check JOBS=4
```

The interpreter is CPython **3.15.2**. The full make command exited zero using local **GCC 16.2.1**:

- 448 tests passed, including the prior-review regression suite.
- All 143 recorded expectations reproduced; the generated CPython names table verified.
- Corpus baselines held: compiled 19/77, eval1 60/77, eval2 63/77.
- Closure, target closure, lint, staging, recorded targets, and the three easy targets through eval1/eval2 passed their checks.
- Object/model differential and its sanitizer/reentrancy checks passed. Float and integer differentials reported zero unexpected mismatches.
- The slice had four passes and the documented fact_big.py promotion failure.

The full check retained the existing later-target closure diagnostics and toolchain probe limitations; its exit status was zero. Docker was not rebuilt and GitHub CI was not inspected. CLAUDE.md makes the pinned Docker toolchain authoritative for C++; the observations here are from the stated local compiler.

Fresh probes also matched CPython for: bare raise through a called function; an inner handled exception inside a finally; a bare re-raise after that inner handler; repeated explicit raise of one exception; clearing a traceback before a bare re-raise; exceptions from inlined comprehensions; a cyclic explicit-cause chain with suppression explicitly controlled; dict lookup after equality clears or changes the table; live view values; ordinary dictionary key/value destruction order; and split-dict clearing and destruction after the instance dies. These positive results are bounded tests, not a proof over those mechanisms.

The refused facilities and known RL-222/RL-225 gaps in the request are excluded. Generator execution remains refused, so no generator-body traceback equivalence is claimed. Only this review file is added; the generated slice artifact changed by make check is restored to the endpoint version.

## Reproduction conventions

All commands run from the repository root. Create the temporary directory once:

```sh
mkdir -p /tmp/bella-review10
```

Save each Python block at the filename stated immediately above it, then run its two commands. Each result was observed in a separate process with PYTHONHASHSEED=0. Outputs are stdout unless labeled stderr; empty streams are identified. For traceback examples the CPython stderr below is complete, including source echoes, so the accepted D-06 source-text omission is visible and is not counted as a defect. A10 identifiers are local to this review.

## A10-1 — Medium: An error in an except header retains the preceding raise line

Location: `pipeline/backend/cpp.py:492; pipeline/l1/frontend.py:1956; pipeline/l2/lower.py:238`.

The exception being matched is correctly recorded at line 3. Evaluating the next handler header raises NameError at line 4, but its entry also names line 3. L1 discards the ExceptHandler location, and the emitter evaluates h.match without advancing frame.line. This is a missing handler boundary: each expression here occupies one line, and the result is the preceding statement’s line, not the start of a multi-line expression covered by RL-225.

Save as `/tmp/bella-review10/handler_expression_line.py`:

```python
def f():
    try:
        raise ValueError('v')
    except missing:
        pass
f()
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/bella-review10/handler_expression_line.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/bella-review10/handler_expression_line.py
```

CPython 3.15.2: exit 1.

No stdout.

Stderr:

```text
Traceback (most recent call last):
  File "/tmp/bella-review10/handler_expression_line.py", line 3, in f
    raise ValueError('v')
ValueError: v

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/tmp/bella-review10/handler_expression_line.py", line 6, in <module>
    f()
    ~^^
  File "/tmp/bella-review10/handler_expression_line.py", line 4, in f
    except missing:
           ^^^^^^^
NameError: name 'missing' is not defined
```

Bella compiled: exit 1.

No stdout.

Stderr:

```text
Traceback (most recent call last):
  File "/tmp/bella-review10/handler_expression_line.py", line 3, in f
ValueError: v

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/tmp/bella-review10/handler_expression_line.py", line 6, in <module>
  File "/tmp/bella-review10/handler_expression_line.py", line 3, in f
NameError: name 'missing' is not defined
```

Suggested fix: Carry the handler header’s location into L1/L2 and set the frame line before evaluating the match expression and validating its result.

## A10-2 — Medium: Raising a reused exception preserves stale context and can create a context cycle

Location: `runtime/src/core.cpp:478, especially :483`.

raise only assigns __context__ if it was absent or None. CPython replaces a previous context with the exception currently being handled and breaks a cycle that the new link would create. Bella preserves the first context in the first example and retains the back-link in the second. These are context-graph differences, independent of the deferred frame-local retention in RL-222. The underlying raise helper predates this range; the new chained report depends on its correctness.

Save as `/tmp/bella-review10/context_reuse.py`:

```python
e=ValueError('v')
for cls in (KeyError,TypeError):
    try:
        try: raise cls('outer')
        except Exception: raise e
    except ValueError as caught:
        print(type(caught.__context__).__name__)
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/bella-review10/context_reuse.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/bella-review10/context_reuse.py
```

CPython 3.15.2: exit 0.

Stdout:

```text
KeyError
TypeError
```

Bella compiled: exit 0.

Stdout:

```text
KeyError
KeyError
```

Save as `/tmp/bella-review10/context_cycle.py`:

```python
a=ValueError('a');b=TypeError('b')
try:
    try: raise a
    except ValueError: raise b
except TypeError:
    try: raise a
    except ValueError:
        print(a.__context__ is b,b.__context__ is None)
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/bella-review10/context_cycle.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/bella-review10/context_cycle.py
```

CPython 3.15.2: exit 0.

Stdout:

```text
True True
```

Bella compiled: exit 0.

Stdout:

```text
True False
```

Suggested fix: Implement the pinned interpreter’s context update and cycle-breaking sequence before throwing the carrier. Test reused exceptions both through caught attribute inspection and through an uncaught chained report.

## A10-3 — Medium: Exception linkage fields are ordinary attributes instead of validated descriptors

Location: `runtime/src/types.cpp:874; runtime/src/core.cpp:518; runtime/src/types.cpp:755`.

The runtime installs __cause__, __context__ and __traceback__ as class values, and writes them through ordinary instance storage. Consequently raise ... from 1 raises the requested ValueError instead of rejecting the cause, assigning a cause fails to set __suppress_context__, and integer assignments to all three linkage fields are accepted. This inherited representation is now observable through the new chain-report mechanism; it also permits invalid state that a correct reporter should never receive.

Save as `/tmp/bella-review10/cause_validation.py`:

```python
try: raise ValueError('v') from 1
except Exception as e: print(type(e).__name__)
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/bella-review10/cause_validation.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/bella-review10/cause_validation.py
```

CPython 3.15.2: exit 0.

Stdout:

```text
TypeError
```

Bella compiled: exit 0.

Stdout:

```text
ValueError
```

Save as `/tmp/bella-review10/cause_suppress.py`:

```python
e=ValueError('v')
e.__cause__=KeyError('k')
print(e.__suppress_context__)
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/bella-review10/cause_suppress.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/bella-review10/cause_suppress.py
```

CPython 3.15.2: exit 0.

Stdout:

```text
True
```

Bella compiled: exit 0.

Stdout:

```text
False
```

Save as `/tmp/bella-review10/cause_assign_bad.py`:

```python
e=ValueError('v')
for name in ('__cause__','__context__','__traceback__'):
    try:setattr(e,name,1);print('accepted')
    except TypeError:print('TypeError')
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/bella-review10/cause_assign_bad.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/bella-review10/cause_assign_bad.py
```

CPython 3.15.2: exit 0.

Stdout:

```text
TypeError
TypeError
TypeError
```

Bella compiled: exit 0.

Stdout:

```text
accepted
accepted
accepted
```

Suggested fix: Install the BaseException linkage descriptors with CPython’s accepted values, validation errors and side effects. Validate a raise-from class before constructing it, and route with_traceback through the same traceback validation. Keep the cause setter’s automatic suppression behavior separate from explicitly setting suppression back to False.

## A10-4 — High: An exception whose __str__ raises aborts the reporter

Location: `runtime/src/call.cpp:1242`.

print_one calls str_of without protecting the formatting operation. The ValueError from E.__str__ escapes while the top-level PyError is already being reported, so the binary aborts instead of completing an exception report. CPython emits E: <exception str() failed> and exits 1. This does not use __notes__, custom traceback modules or imports. The unprotected string conversion was inherited from the previous reporter; it remains in the new chained reporter.

Save as `/tmp/bella-review10/report_str_raises.py`:

```python
class E(Exception):
    def __str__(self): raise ValueError('str failed')
raise E()
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/bella-review10/report_str_raises.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/bella-review10/report_str_raises.py
```

CPython 3.15.2: exit 1.

No stdout.

Stderr:

```text
Traceback (most recent call last):
  File "/tmp/bella-review10/report_str_raises.py", line 3, in <module>
    raise E()
E: <exception str() failed>
```

Bella compiled: terminated by SIGABRT (process return code -6).

No stdout.

Stderr:

```text
Traceback (most recent call last):
  File "/tmp/bella-review10/report_str_raises.py", line 3, in <module>
terminate called after throwing an instance of 'bella::PyError'
```

Suggested fix: Use a safe exception-string conversion that catches formatting failures and produces CPython’s fallback. Preserve the original traceback/exception while doing so, and add a differential test for the uncaught report and the unraisable report.

## A10-5 — High: A rejected dictionary insertion retains the value forever

Location: `runtime/include/bella/object.hpp:433`.

dict_store increments value before dict_put probes the table. If key equality raises, no guard owns that extra count and it is never released. In this example the value is not stored anywhere, yet its finalizer never runs. CPython releases it before entering the handler. This is not a traceback-local cycle: the raising method belongs to the key, and its frame never contains V(). The moved dictionary implementation introduces this ownership boundary.

Save as `/tmp/bella-review10/dict_store_raise.py`:

```python
class V:
    def __del__(self): print('del value')
class K:
    def __hash__(self): return 1
    def __eq__(self,o): raise ValueError('eq')
d={K():1}
try: d[K()]=V()
except ValueError: print('caught')
print('after')
d.clear()
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/bella-review10/dict_store_raise.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/bella-review10/dict_store_raise.py
```

CPython 3.15.2: exit 0.

Stdout:

```text
del value
caught
after
```

Bella compiled: exit 0.

Stdout:

```text
caught
after
```

Suggested fix: Hold the prospective table reference in RAII storage and transfer it only when insertion or replacement commits. Make dict_put’s ownership contract explicit on exceptions, and test equality failure during both insert and replacement.

## A10-6 — Medium: setdefault repeats equality and can replace an existing value

Location: `runtime/src/call.cpp:709, especially :712 and :715`.

setdefault first performs dict_find and then a separate dict_store. A key comparison therefore runs twice on a miss. If equality changes between those calls, the second probe replaces a value that CPython leaves untouched, instead of inserting the new key. The reproduction prints the final dictionary values and callback count, so this is more than an extra harmless comparison.

Save as `/tmp/bella-review10/dict_setdefault_change.py`:

```python
count=0
class K:
    def __hash__(self):return 1
    def __eq__(self,o):
        global count
        count+=1
        return count==2
d={K():1}
print(d.setdefault(K(),2),list(d.values()),count)
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/bella-review10/dict_setdefault_change.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/bella-review10/dict_setdefault_change.py
```

CPython 3.15.2: exit 0.

Stdout:

```text
2 [1, 2] 1
```

Bella compiled: exit 0.

Stdout:

```text
2 [2] 2
```

Suggested fix: Provide a single lookup-and-insert operation for setdefault, following the pinned algorithm’s callback/restart rules. Reuse the lookup result when safe instead of issuing a second semantic lookup.

## A10-7 — Medium: dict.pop hashes and looks up the key twice

Location: `runtime/src/call.cpp:644, especially :646 and :653`.

pop first reads with dict_get and then deletes through dict_del, which independently computes the hash and probes again. CPython performs one hash operation for the pop. The extra callback can raise, leaving the dictionary unchanged when CPython has returned and removed the value. This inherited wrapper remains around the new dictionary implementation.

Save as `/tmp/bella-review10/dict_pop_effect.py`:

```python
d={};calls=0
class K:
    def __hash__(self):
        global calls
        calls+=1
        if calls==3: raise ValueError('extra hash')
        return 1
k=K();d[k]=4
try: print(d.pop(k))
except ValueError: print('ValueError')
print(len(d))
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/bella-review10/dict_pop_effect.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/bella-review10/dict_pop_effect.py
```

CPython 3.15.2: exit 0.

Stdout:

```text
4
0
```

Bella compiled: exit 0.

Stdout:

```text
ValueError
1
```

Suggested fix: Use the existing ownership-returning dict_pop primitive after computing the hash once; handle missing/default cases from that result. Avoid a separate read-before-delete lookup.

## A10-8 — Medium: Copying an exact dictionary unnecessarily compares its keys again

Location: `runtime/include/bella/object.hpp:500`.

dict_copy_into reinserts each entry using dict_put. Although it reuses stored hashes, it compares colliding keys again. The measured CPython copy of this compact, deletion-free dictionary copies the table without those callbacks. Re-running user equality can change the copy’s contents or make an otherwise successful copy raise.

Save as `/tmp/bella-review10/dict_copy_eq.py`:

```python
class K:
    def __hash__(self):return 1
    def __eq__(self,o):print('eq');return False
d={K():1,K():2}
print('copy')
e=d.copy()
print(len(e))
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/bella-review10/dict_copy_eq.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/bella-review10/dict_copy_eq.py
```

CPython 3.15.2: exit 0.

Stdout:

```text
eq
copy
2
```

Bella compiled: exit 0.

Stdout:

```text
eq
copy
eq
2
```

Suggested fix: Reproduce the exact-dict copy fast path and its ownership increments without invoking user equality. Preserve the pinned distinctions between clean compact copies, sparse tables and split copies.

## A10-9 — Medium: dict.fromkeys rehashes keys from an exact dictionary

Location: `runtime/src/call.cpp:752, especially :757`.

fromkeys always constructs an iterator and inserts its yielded keys through dict_set, recomputing each hash. CPython has a stored-hash path for an exact dictionary input. The example shows the additional callback explicitly. This operation is implemented; it does not call the refused dict constructor.

Save as `/tmp/bella-review10/dict_fromkeys_hash.py`:

```python
class K:
    def __hash__(self):print('hash');return 1
k=K();d={k:1}
print('copy')
e=dict.fromkeys(d,2)
print(len(e))
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/bella-review10/dict_fromkeys_hash.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/bella-review10/dict_fromkeys_hash.py
```

CPython 3.15.2: exit 0.

Stdout:

```text
hash
copy
1
```

Bella compiled: exit 0.

Stdout:

```text
hash
copy
hash
1
```

Suggested fix: Add the exact-dict path using the stored hash, with corresponding tests for exact-set input and for the generic iterable path. Preserve the measured callback and mutation behavior of each path.

## A10-10 — Medium: Dictionary iterators yield an extra key after a same-size mutation

Location: `runtime/src/ops.cpp:1016`.

The iterator remembers the original used count but not the number of entries still expected. Deleting an already-yielded key and adding a new key preserves size, so Bella yields a third entry from a dictionary that had two entries at iterator creation. CPython raises RuntimeError at that point. RL-199/A9-12’s size-change fix covers a different case; this also applies to the newly introduced view iterator branches sharing this code.

Save as `/tmp/bella-review10/iter_same_size.py`:

```python
d={'a':1,'b':2};it=iter(d)
print(next(it))
del d['a'];d['c']=3
print(next(it))
try:print(next(it))
except Exception as e:print(type(e).__name__)
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/bella-review10/iter_same_size.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/bella-review10/iter_same_size.py
```

CPython 3.15.2: exit 0.

Stdout:

```text
a
b
RuntimeError
```

Bella compiled: exit 0.

Stdout:

```text
a
b
c
```

Suggested fix: Track the iterator’s remaining-entry count as well as expected size and position. Follow CPython’s exhaustion and keys-changed error behavior; a dictionary-wide version check would incorrectly reject permitted value replacement.

## A10-11 — Medium: An invalid except tuple is accepted when an earlier element matches

Location: `runtime/src/core.cpp:531`.

exception_matches returns as soon as an element matches. CPython first validates the handler tuple and rejects its non-exception entry, even when ValueError occurs first. Bella enters a handler that the interpreter rejects. This inherited handler-validation defect affects the newly audited exception path.

Save as `/tmp/bella-review10/handler_match_error.py`:

```python
try:
    try: raise ValueError('v')
    except (ValueError,42): print('matched')
except Exception as e: print(type(e).__name__)
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/bella-review10/handler_match_error.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/bella-review10/handler_match_error.py
```

CPython 3.15.2: exit 0.

Stdout:

```text
TypeError
```

Bella compiled: exit 0.

Stdout:

```text
matched
```

Suggested fix: Separate validation of the exception specification from matching. Implement the pinned CHECK_EXC_MATCH validation order, including tuple shape, before selecting a handler.

## A10-12 — High: List membership loses a held reference when equality raises

Location: `runtime/src/ops.cpp:363, especially :367`.

The membership loop manually increments the current element before invoking equality, then decrements it only on success. An exception skips that decrement. After the handler and del a, the element remains alive in Bella and its finalizer never runs. This inherited operator defect was found while checking the current operators claim; it is not a regression attributed to fd6ad46.

Save as `/tmp/bella-review10/list_contains_raise.py`:

```python
class K:
    def __eq__(self,o):raise ValueError('v')
    def __del__(self):print('del')
a=[K()]
try: 1 in a
except ValueError: print('caught')
del a
print('after')
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/bella-review10/list_contains_raise.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/bella-review10/list_contains_raise.py
```

CPython 3.15.2: exit 0.

Stdout:

```text
caught
del
after
```

Bella compiled: exit 0.

Stdout:

```text
caught
after
```

Suggested fix: Replace the manual pair with an owning guard whose destructor runs on the exceptional path, and include raising equality/truth conversion in operator lifetime tests.

## A10-13 — Low: The excessive-positional-argument message omits were with keyword-only arguments

Location: `runtime/src/call.cpp:237`.

When given_kwonly is nonzero, the formatter substitutes kwpart for the entire suffix containing was/were. CPython includes were before given in this case. The new argument-message implementation therefore still differs on a valid binding-error path.

Save as `/tmp/bella-review10/keyword_only_count.py`:

```python
def f(a,/,b,*,c):pass
try:f(1,2,3,c=4)
except TypeError as e:print(str(e))
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/bella-review10/keyword_only_count.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/bella-review10/keyword_only_count.py
```

CPython 3.15.2: exit 0.

Stdout:

```text
f() takes 2 positional arguments but 3 positional arguments (and 1 keyword-only argument) were given
```

Bella compiled: exit 0.

Stdout:

```text
f() takes 2 positional arguments but 3 positional arguments (and 1 keyword-only argument) given
```

Suggested fix: Append the keyword-only clause and grammatical verb independently, using the pinned wording for singular/plural combinations and defaults.

## Assessment of the approach

D-12’s choice to record at the first catch is supported by the nested-finally and re-raise probes. It needs a complete inventory of places that execute Python while matching or reporting an exception. A handler expression is one such boundary; safe exception formatting is another. Tests that compare only stdout and exit status cannot establish traceback contents, so retain the new report differential and add these cases to it.

The compact dictionary and shared instance-dict representation are a useful consolidation. The ordinary release-order and live-view probes support the chosen representation. Its remaining failures are at ownership and callback boundaries: a single Python operation can become two lookups, and a raw count can survive an exception. Add the failed-insertion case to the model as well as the header, as required by the repository’s model-first rule. The setdefault, copy, fromkeys and pop cases should compare callback sequences and final contents, not just success results on string keys.

The previous review’s supplied regression cases pass in the full suite. The unfinished cases above should be recorded alongside that evidence; the passing suite does not yet establish the general claim that every implemented operator and exception path either matches CPython or refuses.
