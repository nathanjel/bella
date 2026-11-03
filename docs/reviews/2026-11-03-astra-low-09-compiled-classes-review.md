# Compiled Classes Review

Date: 2026-11-03

Reviewer: astra-low

Sequence: 09

Reviewed range: `d28b25606840edeed5ccdcae4d1207b3c2773634..f12af861c6c6c62853811a97c775ac9fb273441b`

Feature commits: `99d5633`, `2c9a06a`; refusal fix: `f12af86`. The intervening prior-review fixes and build changes are included in the range.

The L2-to-C++ path and the division between a storage/runtime core and a compiled Python prelude remain a workable approach. The examples, class cases and corpus baseline are useful milestones. They do not yet support the broader claims of exact cleanup, class construction and protocol dispatch. I reproduced 23 findings below, including process termination on ordinary Python error paths, cleanup executing twice, incorrect reference lifetimes, and valid programs that fail to compile.

The highest priority is to make ownership and Python exceptions explicit at runtime boundaries and in emitted control flow. The next increment should extend differential coverage around user callbacks, rejected calls and abrupt exits before treating the class/runtime layer as a trusted base for imports. A table copied from CPython needs its callback ownership, error paths and stored-hash fast paths as well as its probing/order algorithm. Likewise, some container formatting behavior needs a narrow runtime primitive even when the formatting remains in Python.

## Verification and scope

The baseline interpreter was measured with `uv run python --version`: **Python 3.15.2**. C++ tests used the local **GCC 16.2.1**. Docker and GitHub CI were not independently rerun/inspected. Per CLAUDE.md, the pinned Docker image remains the authoritative C++ toolchain; these local results should also be reproduced there before fixing them.

```sh
uv run make -j4 --output-sync=target JOBS=4 lint test compiled-corpus object-test slice
```

This completed successfully:

- Ruff and all three mypy checks passed.
- 334 tests passed; the reference model passed 3,000 operations over 50 worlds.
- The compiled corpus preserved its 15/76 baseline.
- The object differential passed 3,000 operations, 199 deaths and 63,897 cache hits; its sanitizer run passed 1,020 operations and 70 deaths. The reentrancy differential also passed under ASan/UBSan.
- All slice results were as expected: four compiled passes and the documented bigint failure for fact_big.py.

The separate programs below were run on that interpreter and on `pipeline/build.py --run`. A separate sanitized build of A9-1 confirmed the invalid access at ops.cpp:294. The standard sanitizer tests passing and that targeted failure are both observed results.

Known deferred features are excluded: real instance-dict exposure, imports, generators, cycle collection, weak references, resurrection, super, custom metaclasses, builtin-type subclasses, the bigint/float wrapper and the remaining builtin inventory. Findings concern behavior already implemented or claimed, rather than absent names. No implementation, expectation, decision or review-log change is proposed by this file; A9 identifiers are local review identifiers.

All commands run from the repository root. Save each Python block at the filename in the command immediately following it. Tests fix PYTHONHASHSEED to zero in both processes. Unless a result says otherwise, exit status is zero and the displayed text is stdout. A negative process return code in the original Python harness denotes a signal; those cases are named explicitly below. Address-bearing unraisable diagnostics are summarized rather than used as expected output.

## A9-1 — High: List comparison uses invalid element positions after a callback

Location: `runtime/src/ops.cpp:286, especially :290 and :294`.

sequence_compare caches the initial length, calls user equality, and then indexes the vectors again without checking their current lengths. The equality callback empties both lists. The ordinary compiled program terminates with SIGSEGV; a separate ASan/UBSan build identifies a null-reference/read at ops.cpp:294. CPython returns False. The callback also removes the containers’ ownership of the compared elements, so the comparison must hold its own references while calling user code.

Reproduction (`/tmp/a9_list_compare_mutation.py`):

```python
a=[]; b=[]
class C:
    def __eq__(self, other):
        a.clear();b.clear()
        return False
    def __lt__(self, other): return True
a.extend([C(),1]);b.extend([C(),2])
print(a<b)
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_list_compare_mutation.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_list_compare_mutation.py
```

CPython 3.15.2: exit 0.

```text
False
```

Bella compiled: terminated by SIGSEGV.

No stdout.

Suggested fix: Follow the pinned list comparison algorithm: own the current elements across callbacks, check current lengths on each iteration and after the equality scan, and only access a position that is still present. Add this case to the compiled differential tests.

## A9-2 — High: Unbound native methods accept a receiver of the wrong type

Location: `runtime/src/call.cpp:54, :59 and :482`.

The unbound method-descriptor branch checks that a first argument exists, then passes it directly to the native method. There is no owner/type check before list storage is accessed. This ordinary invalid Python call must raise a catchable TypeError; the compiled program terminates with SIGSEGV.

Reproduction (`/tmp/a9_wrong_receiver.py`):

```python
try: list.append(1,2)
except TypeError: print('TypeError')
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_wrong_receiver.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_wrong_receiver.py
```

CPython 3.15.2: exit 0.

```text
TypeError
```

Bella compiled: terminated by SIGSEGV.

No stdout.

Suggested fix: Record the descriptor’s owning type and validate the receiver before invoking its native implementation. Apply the check both to direct descriptor calls and descriptor binding.

## A9-3 — High: set.discard reads an absent positional argument

Location: `runtime/src/set.cpp:184 and :189`.

discard and remove only reject keywords, then read a.pos(0) without checking npos. The zero-argument discard call terminates with SIGSEGV rather than reaching the Python exception handler. This is separate from receiver validation: the receiver here is a genuine set.

Reproduction (`/tmp/a9_wrong_set_arity.py`):

```python
try: set().discard()
except TypeError: print('TypeError')
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_wrong_set_arity.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_wrong_set_arity.py
```

CPython 3.15.2: exit 0.

```text
TypeError
```

Bella compiled: terminated by SIGSEGV.

No stdout.

Suggested fix: Check exactly one positional argument before reading it, as set_add_m already does. Audit the other native entry points for the same missing count check.

## A9-4 — High: Exceptions from finalizers escape destruction

Location: `runtime/include/bella/object.hpp:929, especially :936; Ref destruction at :147`.

dealloc calls the Python finalizer without an exception boundary. On an explicit del its exception becomes an ordinary uncaught program exception. When the same operation runs from a C++ Ref destructor, it terminates the process with SIGABRT. CPython reports the finalizer exception as unraisable and continues. Neither example resurrects an object or depends on cycle collection.

Reproduction (`/tmp/a9_del_raises.py`):

```python
class C:
    def __del__(self):
        print('finalizer')
        raise ValueError('bad')
x=C();del x
print('after')
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_del_raises.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_del_raises.py
```

CPython 3.15.2: exit 0.

```text
finalizer
after
```

CPython reports an ignored/unraisable ValueError from __del__ on stderr.

Bella compiled: exit 1.

```text
finalizer
```

stderr contains an ordinary traceback ending in `ValueError: bad`.

Reproduction (`/tmp/a9_finalizer_exception_destructor.py`):

```python
class C:
    def __del__(self): raise ValueError('bad')
def f():
    x=C()
f()
print('after')
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_finalizer_exception_destructor.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_finalizer_exception_destructor.py
```

CPython 3.15.2: exit 0.

```text
after
```

CPython reports an ignored/unraisable ValueError from __del__ on stderr.

Bella compiled: terminated by SIGABRT.

No stdout.

stderr: `terminate called after throwing an instance of 'bella::PyError'`.

Suggested fix: Implement the unraisable-exception boundary around finalization, preserve and restore any already-active exception state, and finish releasing the instance. C++ RAII destruction must not propagate a Python exception.

## A9-5 — High: A finally block can execute twice on return

Location: `pipeline/backend/cpp.py:346, :374 and :392`.

The return path writes the finalbody inline inside the generated outer try. If that cleanup raises, the same try’s catch(...) executes the finalbody again. A Python return overridden by a finally exception must execute that finally once.

Reproduction (`/tmp/a9_finally_return_raise.py`):

```python
def f():
    try: return 1
    finally:
        print('finally')
        raise ValueError('bad')
try: f()
except ValueError: print('caught')
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_finally_return_raise.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_finally_return_raise.py
```

CPython 3.15.2: exit 0.

```text
finally
caught
```

Bella compiled: exit 0.

```text
finally
finally
caught
```

Suggested fix: Represent pending return/break/continue completion explicitly, or generate control flow that puts an entered finalbody outside its own exception catch. Test nested cleanup and exceptions raised by cleanup on each exit kind.

## A9-6 — High: The exceptional finally path has no handled Python exception

Location: `pipeline/backend/cpp.py:392; compare the Handling scope at :423`.

The catch(...) used for finally runs its body without installing the caught Python exception as the active handled exception. A bare raise therefore raises RuntimeError, and a replacement exception loses its __context__. This is a distinct issue from running cleanup twice: neither reproduction returns from the try.

Reproduction (`/tmp/a9_finally_reraise.py`):

```python
try:
    try: raise ValueError('original')
    finally: raise
except BaseException as e: print(type(e).__name__)
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_finally_reraise.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_finally_reraise.py
```

CPython 3.15.2: exit 0.

```text
ValueError
```

Bella compiled: exit 0.

```text
RuntimeError
```

Reproduction (`/tmp/a9_finally_exception_context.py`):

```python
try:
    try: raise ValueError('first')
    finally: raise TypeError('second')
except TypeError as e:
    print(type(e.__context__).__name__)
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_finally_exception_context.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_finally_exception_context.py
```

CPython 3.15.2: exit 0.

```text
ValueError
```

Bella compiled: exit 0.

```text
NoneType
```

Suggested fix: Catch PyError separately and establish a scoped Handling state while executing the finalbody. Preserve the separate handling policy for internal refusals and other C++ exceptions.

## A9-7 — High: Unpacking retains its consumed source until scope exit

Location: `pipeline/backend/cpp.py:296 and :479; runtime/src/ops.cpp:822`.

L2 marks the unpack source as consumed, but take_obj merely borrows its Obj. The source temporary remains an owning Ref, retaining the original list and both objects until module teardown. Consequently del a and del b do not run either finalizer at the specified point.

Reproduction (`/tmp/a9_unpack_lifetime.py`):

```python
class O:
    def __init__(self,n): self.n=n
    def __del__(self): print('del',self.n)

a,b=[O('a'),O('b')]
del a
del b
print('after')
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_unpack_lifetime.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_unpack_lifetime.py
```

CPython 3.15.2: exit 0.

```text
del a
del b
after
```

Bella compiled: exit 0.

```text
after
del b
del a
```

Suggested fix: Transfer the consumed source into an owning unpack operation, or introduce an explicit scope that releases the source at CPython’s point on both success and failure. Do not leave a consumed L2 operand owning a reference.

## A9-8 — High: A failed set insertion leaks the candidate reference

Location: `runtime/src/set.cpp:87 and :113`.

set_add increments the candidate’s count before probing and calls user equality without an owning guard for that increment. If equality raises, the increment is never undone. The rejected candidate’s finalizer is absent even after the set is explicitly deleted. CPython drops that candidate when the handled exception is cleared, before the following statement.

Reproduction (`/tmp/a9_set_exception_leak_fixed.py`):

```python
class O:
    def __init__(self,n): self.n=n
    def __del__(self): print('del',self.n)

class C(O):
    def __hash__(self): return 1
    def __eq__(self, other): raise ValueError('bad')
s={C('first')}
try: s.add(C('second'))
except ValueError: print('caught')
print('after')
del s
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_set_exception_leak_fixed.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_set_exception_leak_fixed.py
```

CPython 3.15.2: exit 0.

```text
caught
del second
after
del first
```

Bella compiled: exit 0.

```text
caught
after
del first
```

Suggested fix: Use an owning Ref for the prospective table reference and transfer it only once insertion succeeds. Ensure equality, hashing and allocation failure paths release every temporary owned reference.

## A9-9 — High: Invalid base lists escape as an uncaught C++ exception

Location: `runtime/src/types.cpp:351`.

make_class throws bella::TypeError for the duplicate/inconsistent base list. That model exception is not translated into rt::PyError at this boundary, so Python except TypeError cannot catch it and the process terminates with SIGABRT. This uses only ordinary user classes and the supported type metaclass.

Reproduction (`/tmp/a9_duplicate_base.py`):

```python
class A: pass
try:
    class B(A,A): pass
    print('created')
except TypeError: print('TypeError')
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_duplicate_base.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_duplicate_base.py
```

CPython 3.15.2: exit 0.

```text
TypeError
```

Bella compiled: terminated by SIGABRT.

No stdout.

stderr: `terminate called after throwing an instance of 'bella::TypeError'`, followed by `what(): inconsistent MRO`.

Suggested fix: Validate duplicate bases in CPython’s order and translate model-level class construction errors into the corresponding Python exceptions. Audit the boundary for other model error types.

## A9-10 — Medium: Callable-instance dispatch consults an instance shadow of __call__

Location: `runtime/src/call.cpp:88, especially :94`.

The non-PyFunction special-method path uses ordinary getattr(f, "__call__"). That consults the instance dictionary, although implicit call dispatch must bind the attribute found on the type. The example’s staticmethod on the class returns 1, but Bella invokes the instance attribute returning 2.

Reproduction (`/tmp/a9_call_special_shadow.py`):

```python
class C:
    @staticmethod
    def __call__(): return 1
c=C()
c.__call__=lambda:2
print(c())
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_call_special_shadow.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_call_special_shadow.py
```

CPython 3.15.2: exit 0.

```text
1
```

Bella compiled: exit 0.

```text
2
```

Suggested fix: Bind the already-found type attribute through its descriptor protocol, without looking up __call__ on the instance. Reuse the same special-method binding helper used by other implicit operations.

## A9-11 — Medium: list.pop silently treats non-immediate indices as zero

Location: `runtime/src/call.cpp:489`.

The ternary expression substitutes zero for every non-immediate argument. pop(True) therefore removes the wrong element, and pop("bad") mutates the list instead of raising TypeError. Objects implementing __index__ need the same conversion path.

Reproduction (`/tmp/a9_bool_as_index.py`):

```python
a=[1,2]
print(a.pop(True))
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_bool_as_index.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_bool_as_index.py
```

CPython 3.15.2: exit 0.

```text
2
```

Bella compiled: exit 0.

```text
1
```

Reproduction (`/tmp/a9_bad_pop_index.py`):

```python
a=[1,2]
try: print(a.pop('bad'))
except TypeError: print('TypeError')
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_bad_pop_index.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_bad_pop_index.py
```

CPython 3.15.2: exit 0.

```text
TypeError
```

Bella compiled: exit 0.

```text
1
```

Suggested fix: Use the Python integer-index protocol, including bool and __index__, and perform its error and bounds checks before modifying the list.

## A9-12 — Medium: Set and dictionary iterators ignore size changes

Location: `runtime/src/ops.cpp:790 and :811; iterator state in runtime/include/bella/runtime.hpp`.

Neither iterator compares the current used count with an expected count. The set path checks a negative position, but the shown mutation never changes that field. Both examples yield 1 after a size-changing mutation instead of raising RuntimeError.

Reproduction (`/tmp/a9_set_mutation.py`):

```python
s={1,2}
it=iter(s)
s.add(3)
try: print(next(it))
except RuntimeError: print('RuntimeError')
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_set_mutation.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_set_mutation.py
```

CPython 3.15.2: exit 0.

```text
RuntimeError
```

Bella compiled: exit 0.

```text
1
```

Reproduction (`/tmp/a9_dict_mutation.py`):

```python
s={1:1,2:2}
it=iter(s)
s[3]=3
try: print(next(it))
except RuntimeError: print('RuntimeError')
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_dict_mutation.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_dict_mutation.py
```

CPython 3.15.2: exit 0.

```text
RuntimeError
```

Bella compiled: exit 0.

```text
1
```

Suggested fix: Track CPython’s expected size and iteration state, including persistent failure and exhaustion behavior. Distinguish size/key changes from dictionary value replacement, which is allowed during iteration.

## A9-13 — Medium: Sequence ordering discards a rich comparison’s result object

Location: `runtime/src/ops.cpp:294 and :306`.

sequence_compare returns bool and truth-tests the final differing elements’ ordering result. CPython list and tuple ordering return that rich comparison object directly: both lines print 42, not True. The equality scan still needs truth conversion; the final ordering result does not.

Reproduction (`/tmp/a9_list_rich_result.py`):

```python
class C:
    def __eq__(self,other): return False
    def __lt__(self,other): return 42
print([C()]<[C()])
print((C(),)<(C(),))
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_list_rich_result.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_list_rich_result.py
```

CPython 3.15.2: exit 0.

```text
42
42
```

Bella compiled: exit 0.

```text
True
True
```

Suggested fix: Return Ref from the sequence comparison helper. Return Boolean objects for the length/equality cases and pass through the final element ordering result unchanged.

## A9-14 — Medium: __len__ result conversion differs between len and truth

Location: `runtime/src/ops.cpp:392; runtime/src/call.cpp:370`.

truth rejects a bool returned by __len__, although len accepts it. Both paths reject an object with a valid __index__. CPython accepts these results and applies the length conversion and range rules.

Reproduction (`/tmp/a9_len_bool.py`):

```python
class C:
    def __len__(self): return True
c=C()
try: print(len(c),bool(c))
except TypeError: print('TypeError')
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_len_bool.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_len_bool.py
```

CPython 3.15.2: exit 0.

```text
1 True
```

Bella compiled: exit 0.

```text
TypeError
```

Reproduction (`/tmp/a9_len_index.py`):

```python
class I:
    def __index__(self): return 2
class C:
    def __len__(self): return I()
try: print(len(C()))
except TypeError: print('TypeError')
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_len_index.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_len_index.py
```

CPython 3.15.2: exit 0.

```text
2
```

Bella compiled: exit 0.

```text
TypeError
```

Suggested fix: Share a measured CPython-compatible length-result conversion helper between len and truth, covering bool, __index__, negative values and overflow.

## A9-15 — Medium: Copying exact sets and dictionaries calls __hash__ again

Location: `runtime/src/set.cpp:141, especially :150; runtime/src/ops.cpp:870 and :897`.

The exact-container paths enumerate stored entries but then use ordinary insertion, which recomputes their hashes. CPython reuses the stored hashes in these copies. These extra calls can have visible effects or raise exceptions; preserving iteration order alone does not establish equivalence of the copied table algorithm.

Reproduction (`/tmp/a9_set_hash_copy.py`):

```python
class C:
    def __hash__(self): print('hash');return 1
x=C();s={x}
print('copy')
t=set(s)
print(len(t))
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_set_hash_copy.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_set_hash_copy.py
```

CPython 3.15.2: exit 0.

```text
hash
copy
1
```

Bella compiled: exit 0.

```text
hash
copy
hash
1
```

Reproduction (`/tmp/a9_dict_hash_copy.py`):

```python
class C:
    def __hash__(self): print('hash');return 1
x=C();s={x:1}
print('copy')
t={**s}
print(len(t))
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_dict_hash_copy.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_dict_hash_copy.py
```

CPython 3.15.2: exit 0.

```text
hash
copy
1
```

Bella compiled: exit 0.

```text
hash
copy
hash
1
```

Suggested fix: Provide insertion/merge paths accepting a stored hash and use the appropriate exact-set and exact-dict fast paths. Keep user-provided iterable/mapping paths distinct and test hash/equality callback counts as well as final table order.

## A9-16 — Medium: An empty dictionary skips the key hash operation

Location: `runtime/src/core.cpp:432`.

dict_get returns early when its table has no indices, before invoking hash_of. CPython still hashes the lookup key. The missing callback is visible in the example and also matters when hashing raises.

Reproduction (`/tmp/a9_empty_dict_hash.py`):

```python
class C:
    def __hash__(self): print('hash');return 1
print(C() in {})
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_empty_dict_hash.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_empty_dict_hash.py
```

CPython 3.15.2: exit 0.

```text
hash
False
```

Bella compiled: exit 0.

```text
False
```

Suggested fix: Calculate and validate the hash before the empty-table result. Exercise contains, indexing and get on fresh empty dictionaries with callback-bearing and unhashable keys.

## A9-17 — Medium: Dictionary repr snapshots entries before invoking user repr

Location: `runtime/prelude/builtins.py:196; runtime/src/call.cpp:594`.

The prelude uses self.items(), whose compiled implementation builds a list snapshot. A value’s __repr__ adds another entry; CPython’s repr visits it, while Bella omits it. Replacing the snapshot with an ordinary dict view iterator is not sufficient: that iterator has size-change checks, whereas the builtin repr follows its own entry-walk behavior.

Reproduction (`/tmp/a9_dict_repr_mutation.py`):

```python
d={}
class C:
    def __repr__(self):
        d['b']=2
        return 'C'
d['a']=C()
print(d)
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_dict_repr_mutation.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_dict_repr_mutation.py
```

CPython 3.15.2: exit 0.

```text
{'a': C, 'b': 2}
```

Bella compiled: exit 0.

```text
{'a': C}
```

Suggested fix: Expose the narrow entry-walk primitive required by CPython’s repr, with ownership across callbacks and the measured mutation behavior, then keep formatting in the Python prelude. Add callback mutation tests to the prelude differential.

## A9-18 — Medium: __slots__ validation rejects valid names and accepts invalid ones

Location: `runtime/src/types.cpp:320, especially :324`.

The implementation rejects every duplicate slot name, although CPython permits repeated ordinary names. Conversely, it never checks that an ordinary slot string is an identifier, so "not-valid" is accepted. These examples do not use the deferred __weakref__ facility.

Reproduction (`/tmp/a9_duplicate_slot.py`):

```python
try:
    class C: __slots__=('x','x')
    print('created')
except TypeError: print('TypeError')
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_duplicate_slot.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_duplicate_slot.py
```

CPython 3.15.2: exit 0.

```text
created
```

Bella compiled: exit 0.

```text
TypeError
```

Reproduction (`/tmp/a9_invalid_slot.py`):

```python
try:
    class C: __slots__=('not-valid',)
    print('created')
except TypeError: print('TypeError')
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_invalid_slot.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_invalid_slot.py
```

CPython 3.15.2: exit 0.

```text
TypeError
```

Bella compiled: exit 0.

```text
created
```

Suggested fix: Implement CPython’s identifier validation and its specific duplicate handling, including the distinct __dict__ rule. Preserve the resulting descriptor/storage behavior for repeated ordinary slot names rather than assuming all duplicates are invalid.

## A9-19 — Medium: classmethod requires a descriptor where CPython accepts a callable

Location: `runtime/prelude/builtins.py:138`.

The prelude calls the wrapped object’s __get__. A callable instance need not implement __get__, yet CPython classmethod binds the owner to it. Bella raises AttributeError for that supported use.

Reproduction (`/tmp/a9_classmethod_callable.py`):

```python
class F:
    def __call__(self, cls): return cls.__name__
class C:
    method=classmethod(F())
try: print(C.method())
except AttributeError: print('AttributeError')
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_classmethod_callable.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_classmethod_callable.py
```

CPython 3.15.2: exit 0.

```text
C
```

Bella compiled: exit 0.

```text
AttributeError
```

Suggested fix: Use a bound-method construction primitive that can bind an arbitrary callable to the owner, and verify descriptor-wrapped callables against the pinned interpreter.

## A9-20 — Medium: C++ name generation collides with user identifiers

Location: `pipeline/backend/cpp.py:36, :45 and :317`.

The internal-name pattern omits endedN, so a user local ended1 collides with a loop flag. Separately, replacing double underscores by _U_ is not injective: _A__b and _A_U_b become the same C++ identifier. Both valid Python programs fail during C++ compilation.

Reproduction (`/tmp/a9_flag_collision.py`):

```python
def f():
    ended1=3
    for i in []: pass
    else: print(ended1)
f()
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_flag_collision.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_flag_collision.py
```

CPython 3.15.2: exit 0.

```text
3
```

Bella compiled: exit 1.

No stdout.

C++ compilation fails because `ended1` is declared both as a `Ref` and as a loop Boolean; subsequent errors include `could not convert ended1 from bella::Ref to bool`.

Reproduction (`/tmp/a9_unary_collision.py`):

```python
def f():
    _A__b=1
    _A_U_b=2
    print(_A__b,_A_U_b)
f()
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_unary_collision.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_unary_collision.py
```

CPython 3.15.2: exit 0.

```text
1 2
```

Bella compiled: exit 1.

No stdout.

C++ compilation fails with `error: redeclaration of bella::Ref py__A_U_b`.

Suggested fix: Allocate names per generated scope, reserve all user and compiler names together, and use an injective escaping scheme. Include helper arrays, exception variables, loop flags and return storage in that allocator.

## A9-21 — Medium: NotImplemented has the wrong truth behavior

Location: `runtime/src/ops.cpp:376`.

The generic singleton case makes every singleton except None true. On the pinned CPython 3.15.2, bool(NotImplemented) raises TypeError; Bella returns True.

Reproduction (`/tmp/a9_notimplemented_bool.py`):

```python
try: print(bool(NotImplemented))
except TypeError: print('TypeError')
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_notimplemented_bool.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_notimplemented_bool.py
```

CPython 3.15.2: exit 0.

```text
TypeError
```

Bella compiled: exit 0.

```text
True
```

Suggested fix: Handle NotImplemented explicitly in truth conversion before the generic singleton case, using the pinned exception behavior.

## A9-22 — Medium: abs uses ordering and unary operators instead of __abs__

Location: `runtime/src/call.cpp:629`.

The builtin implements abs as a comparison with zero followed by unary plus or minus. That fails for an ordinary instance defining __abs__, although CPython prints 42. It can also invoke unrelated user operators with different side effects.

Reproduction (`/tmp/a9_abs_protocol.py`):

```python
class C:
    def __abs__(self): return 42
try: print(abs(C()))
except TypeError: print('TypeError')
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_abs_protocol.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_abs_protocol.py
```

CPython 3.15.2: exit 0.

```text
42
```

Bella compiled: exit 0.

```text
TypeError
```

Suggested fix: Dispatch the absolute-value protocol directly, retaining native numeric fast paths only where they have the same behavior.

## A9-23 — Low: Function docstrings are discarded, including property documentation

Location: `runtime/src/call.cpp:146; Code metadata emitted by pipeline/backend/cpp.py`.

make_function always initializes __doc__ to None. The frontend’s function docstring therefore never reaches the runtime. This is visible directly and through the claimed property prelude, which derives its documentation from the getter.

Reproduction (`/tmp/a9_function_doc.py`):

```python
def f():
    "a docstring"
print(f.__doc__)
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_function_doc.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_function_doc.py
```

CPython 3.15.2: exit 0.

```text
a docstring
```

Bella compiled: exit 0.

```text
None
```

Reproduction (`/tmp/a9_factory_doc.py`):

```python
class C:
    @property
    def p(self):
        "property doc"
        return 1
print(C.p.__doc__)
```

```sh
PYTHONHASHSEED=0 uv run python /tmp/a9_factory_doc.py
PYTHONHASHSEED=0 uv run python pipeline/build.py --run /tmp/a9_factory_doc.py
```

CPython 3.15.2: exit 0.

```text
property doc
```

Bella compiled: exit 0.

```text
None
```

Suggested fix: Carry the function docstring through emitted Code metadata and initialize the function’s __doc__ from it. Include plain functions and property/staticmethod/classmethod metadata in the differential tests.

## Implications for the documents and next increment

`docs/emitter.md` and TODO agree on the current compiled baseline and on what remains for 3a.3/3b/3c. The construction and dispatch sequences described in emitter.md are useful implementation maps, but their exactness wording currently overstates the observed behavior: A9-5/A9-6 contradict the cleanup description, A9-9/A9-18 contradict class validation equivalence, and A9-10/A9-13/A9-14/A9-19/A9-22 contradict the general protocol claim. Record confirmed defects as open work rather than using the passing C-3-05..11 cases as evidence for every boundary of those mechanisms.

The core/prelude decision does not need to be reversed. A9-17 identifies a concrete limit of expressing builtin dictionary repr through ordinary Python dict iteration: its callback/mutation semantics require a more specific primitive. A9-15 similarly calls for the stored-hash operations of the chosen table design, rather than a different table design. A9-7 shows that L2’s consumption contract needs an emitter-level ownership check in addition to wf2.

I would gate the next broad runtime increment on focused compiled regressions for these findings, with callbacks that mutate operands or raise, and with comparisons of exception types, callback counts, finalizer order and return objects. The existing object/model differential remains valuable, but it does not cover the new native container code or emitted completion paths responsible for these failures.
